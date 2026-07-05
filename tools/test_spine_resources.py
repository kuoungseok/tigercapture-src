"""Scan and render-test Spine resources through TigerCapture's actor path."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _find_atlas(skel_path: Path) -> Path | None:
    stem = skel_path.with_suffix("")
    exact = Path(str(stem).replace(".skel", "") + ".atlas")
    if exact.exists():
        return exact
    atlases = sorted(skel_path.parent.glob("*.atlas"))
    return atlases[0] if atlases else None


def _pick_animation(skel) -> str:
    if not getattr(skel, "animations", None):
        return ""
    names = sorted(skel.animations.keys())
    lowered = {name.lower(): name for name in names}
    for preferred in ("idle", "wait", "loop", "action", "walk", "run"):
        if preferred in lowered:
            return lowered[preferred]
    return names[0]


def _test_one(path: Path, width: int, height: int) -> dict[str, Any]:
    from app.spine_editor.actor_track import SpineActorClip
    from app.spine_editor.spine_json_parser import load_spine_file, load_atlas_pages

    result: dict[str, Any] = {
        "path": str(path),
        "status": "fail",
        "version": "",
        "atlas": "",
        "pages": 0,
        "bones": 0,
        "slots": 0,
        "animations": 0,
        "nonblank": False,
        "error": "",
    }
    try:
        if path.suffix.lower() == ".skel":
            try:
                from app.spine_editor.spine_json_parser import detect_spine_binary_version
                result["version"] = detect_spine_binary_version(path)
            except Exception:
                pass
        skel = load_spine_file(str(path))
        result["bones"] = len(getattr(skel, "bones", []) or [])
        result["slots"] = len(getattr(skel, "slots", []) or [])
        result["animations"] = len(getattr(skel, "animations", {}) or {})
        anim = _pick_animation(skel)
        atlas = _find_atlas(path)
        if atlas:
            result["atlas"] = str(atlas)
            result["pages"] = len(load_atlas_pages(str(atlas)))
        clip = SpineActorClip(
            skel_path=str(path),
            atlas_path=str(atlas) if atlas else "",
            anim_name=anim,
            start_ms=0,
            duration_ms=3000,
        )
        img = clip.render_frame(width, height, 0)
        if img is None:
            result["status"] = "render_none"
            return result
        bbox = img.getchannel("A").getbbox()
        result["nonblank"] = bbox is not None
        result["bbox"] = bbox
        result["status"] = "pass" if bbox else "blank"
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        if "Unsupported Spine binary" in str(exc):
            result["status"] = "unsupported"
        return result


def _bbox_center(bbox: tuple[int, int, int, int] | None) -> tuple[float, float] | None:
    if not bbox:
        return None
    left, top, right, bottom = bbox
    return ((float(left) + float(right)) * 0.5, (float(top) + float(bottom)) * 0.5)


def _sample_positions(duration_ms: int, samples: int) -> list[int]:
    samples = max(2, int(samples or 5))
    duration_ms = max(1, int(duration_ms or 1))
    return sorted({
        max(0, min(duration_ms, int(round(duration_ms * idx / (samples - 1)))))
        for idx in range(samples)
    })


def _pick_skin_names(skel: Any, max_skins: int) -> list[str]:
    names = sorted(str(name) for name in (getattr(skel, "skins", {}) or {}))
    if not names:
        return ["default"]
    ordered: list[str] = []
    for preferred in ("default",):
        if preferred in names:
            ordered.append(preferred)
    for name in names:
        lowered = name.lower()
        if name not in ordered and ("full-skin" in lowered or lowered.startswith("full")):
            ordered.append(name)
    for name in names:
        if name not in ordered:
            ordered.append(name)
    return ordered[: max(1, int(max_skins or 1))]


def _skin_slot_summary(skel: Any, skin_name: str) -> dict[str, Any]:
    skins = getattr(skel, "skins", {}) or {}
    merged: dict[str, dict[str, Any]] = {}
    for slot_name, atts in (skins.get("default", {}) or {}).items():
        merged[str(slot_name)] = dict(atts or {})
    if skin_name != "default":
        for slot_name, atts in (skins.get(skin_name, {}) or {}).items():
            merged.setdefault(str(slot_name), {}).update(dict(atts or {}))
    slots = list(getattr(skel, "slots", []) or [])
    slots_with_attachment = 0
    attachment_count = 0
    missing_slot_attachments: list[str] = []
    for slot in slots:
        slot_name = str(getattr(slot, "name", "") or "")
        attachment_name = str(getattr(slot, "attachment", "") or "")
        slot_atts = merged.get(slot_name, {})
        attachment_count += len(slot_atts)
        if attachment_name and attachment_name in slot_atts:
            slots_with_attachment += 1
        elif attachment_name:
            missing_slot_attachments.append(f"{slot_name}:{attachment_name}")
    return {
        "skin_name": skin_name,
        "slot_count": len(slots),
        "slot_maps": len(merged),
        "attachment_count": attachment_count,
        "slots_with_attachment": slots_with_attachment,
        "missing_slot_attachments": missing_slot_attachments[:20],
    }


def _skin_combinations(skin_names: list[str], *, max_combinations: int = 4) -> list[list[str]]:
    non_default = [name for name in skin_names if name and name != "default"]
    combos: list[list[str]] = []
    for name in non_default:
        combos.append([name])
    for idx, first in enumerate(non_default):
        for second in non_default[idx + 1:]:
            combos.append([first, second])
            if len(combos) >= max_combinations:
                return combos[:max_combinations]
    return combos[:max_combinations]


def _merge_skin_combo(skel: Any, names: list[str]) -> str:
    combo_name = "__qa_combo__" + "__".join(name.replace("/", "_") for name in names)
    merged: dict[str, dict[str, Any]] = {}
    for name in names:
        for slot_name, attachments in (getattr(skel, "skins", {}) or {}).get(name, {}).items():
            merged.setdefault(str(slot_name), {}).update(dict(attachments or {}))
    if merged:
        skel.skins[combo_name] = merged
    return combo_name


def _render_combo_sample(
    skel: Any,
    path: Path,
    atlas: Path | None,
    *,
    skin_name: str,
    anim_name: str,
    pos_ms: int,
    width: int,
    height: int,
) -> tuple[Any, tuple[int, int, int, int] | None]:
    from PIL import Image

    from app.spine_editor.spine_json_parser import atlas_is_pma, load_atlas, load_atlas_pages
    from app.spine_editor.spine_renderer import SpineRenderer

    atlas_data = load_atlas(str(atlas)) if atlas else {}
    pages = []
    if atlas:
        for page in load_atlas_pages(str(atlas)):
            page_path = atlas.parent / page
            pages.append(Image.open(page_path).convert("RGBA") if page_path.exists() else None)
    renderer = SpineRenderer(skel, atlas_data, pages, pma=atlas_is_pma(str(atlas)) if atlas else False)
    anim = skel.animations.get(anim_name)
    anim_time = 0.0
    if anim is not None:
        duration = max(0.001, float(getattr(anim, "duration", 1.0) or 1.0))
        anim_time = min(duration, max(0.0, float(pos_ms) / 1000.0))
    bounds = renderer.visual_bounds(skin_name)
    scale = 1.0
    offset_x = 0.0
    offset_y = 0.0
    if bounds:
        min_x, min_y, max_x, max_y = bounds
        visual_w = max(1.0, max_x - min_x)
        visual_h = max(1.0, max_y - min_y)
        scale = max(0.02, min(20.0, min(width * 0.82 / visual_w, height * 0.82 / visual_h)))
        center_x = (min_x + max_x) / 2.0
        center_y = (min_y + max_y) / 2.0
        offset_x = -center_x * scale
        offset_y = -center_y * scale
    img = renderer.render(
        width=width,
        height=height,
        scale=scale,
        anim_name=anim_name,
        time=anim_time,
        skin_name=skin_name,
        offset_x=offset_x,
        offset_y=offset_y,
    )
    bbox = img.getchannel("A").getbbox() if img is not None else None
    return img, bbox


def sweep_one(
    path: Path,
    width: int,
    height: int,
    *,
    samples: int = 5,
    max_animations: int = 4,
    max_skins: int = 4,
    max_skin_combinations: int = 4,
) -> dict[str, Any]:
    """Sample multiple frames across Spine skin/animation variants for corpus QA."""
    from app.spine_editor.actor_track import SpineActorClip
    from app.spine_editor.spine_json_parser import load_spine_file

    result: dict[str, Any] = {
        "path": str(path),
        "status": "fail",
        "sample_count": 0,
        "blank_frames": 0,
        "skins_tested": 0,
        "animations": [],
        "skin_slot_summaries": [],
        "skin_combinations": [],
        "error": "",
    }
    try:
        skel = load_spine_file(str(path))
        names = sorted(getattr(skel, "animations", {}) or {})
        if not names:
            result["status"] = "no_animation"
            result["skin_slot_summaries"] = [
                _skin_slot_summary(skel, skin_name)
                for skin_name in _pick_skin_names(skel, max_skins)
            ]
            return result
        atlas = _find_atlas(path)
        skin_names = _pick_skin_names(skel, max_skins)
        result["skins_tested"] = len(skin_names)
        result["skin_slot_summaries"] = [
            _skin_slot_summary(skel, skin_name)
            for skin_name in skin_names
        ]
        for skin_name in skin_names:
            for anim_name in names[: max(1, int(max_animations or 1))]:
                anim = skel.animations[anim_name]
                duration_ms = max(1, int(float(getattr(anim, "duration", 1.0) or 1.0) * 1000.0))
                clip = SpineActorClip(
                    skel_path=str(path),
                    atlas_path=str(atlas) if atlas else "",
                    anim_name=str(anim_name),
                    skin_name=str(skin_name),
                    start_ms=0,
                    duration_ms=duration_ms,
                    loop=False,
                )
                frames: list[dict[str, Any]] = []
                previous_center: tuple[float, float] | None = None
                max_center_jump = 0.0
                for pos_ms in _sample_positions(duration_ms, samples):
                    img = clip.render_frame(width, height, pos_ms)
                    bbox = None
                    if img is not None:
                        bbox = img.getchannel("A").getbbox()
                    center = _bbox_center(bbox)
                    if center is not None and previous_center is not None:
                        dx = center[0] - previous_center[0]
                        dy = center[1] - previous_center[1]
                        max_center_jump = max(max_center_jump, (dx * dx + dy * dy) ** 0.5)
                    if center is not None:
                        previous_center = center
                    frames.append({
                        "pos_ms": int(pos_ms),
                        "nonblank": bbox is not None,
                        "bbox": list(bbox) if bbox is not None else None,
                    })
                blank_count = sum(1 for frame in frames if not frame["nonblank"])
                result["sample_count"] += len(frames)
                result["blank_frames"] += blank_count
                result["animations"].append({
                    "skin_name": skin_name,
                    "name": anim_name,
                    "duration_ms": duration_ms,
                    "blank_frames": blank_count,
                    "max_center_jump": round(max_center_jump, 3),
                    "frames": frames,
                })
        combo_names = _skin_combinations(skin_names, max_combinations=max_skin_combinations)
        first_anim = names[0]
        first_duration_ms = max(
            1,
            int(float(getattr(skel.animations[first_anim], "duration", 1.0) or 1.0) * 1000.0),
        )
        for combo in combo_names:
            combo_skin = _merge_skin_combo(skel, combo)
            frames: list[dict[str, Any]] = []
            for pos_ms in _sample_positions(first_duration_ms, min(samples, 3)):
                _img, bbox = _render_combo_sample(
                    skel,
                    path,
                    atlas,
                    skin_name=combo_skin,
                    anim_name=first_anim,
                    pos_ms=pos_ms,
                    width=width,
                    height=height,
                )
                frames.append({
                    "pos_ms": int(pos_ms),
                    "nonblank": bbox is not None,
                    "bbox": list(bbox) if bbox is not None else None,
                })
            blank_count = sum(1 for frame in frames if not frame["nonblank"])
            result["sample_count"] += len(frames)
            result["blank_frames"] += blank_count
            result["skin_combinations"].append({
                "skins": combo,
                "combo_skin": combo_skin,
                "animation": first_anim,
                "blank_frames": blank_count,
                "frames": frames,
            })
        result["status"] = "pass" if result["blank_frames"] == 0 else "blank"
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def _looks_like_spine_json(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:2048]
    except Exception:
        return False
    return '"bones"' in head or '"skeleton"' in head or '"slots"' in head


def _preferred_spine_model_path(path: Path) -> Path:
    if path.suffix.lower() != ".skel":
        return path
    json_peer = path.with_suffix(".json")
    if json_peer.exists() and _looks_like_spine_json(json_peer):
        return json_peer
    return path


def _candidates(root: Path) -> list[Path]:
    if root.is_file():
        path = _preferred_spine_model_path(root)
        if path.suffix.lower() == ".skel" or _looks_like_spine_json(path):
            return [path]
        return []
    results: list[Path] = []
    seen: set[Path] = set()
    for pattern in ("*.skel", "*.json"):
        for path in root.rglob(pattern):
            path = _preferred_spine_model_path(path)
            if path.suffix.lower() == ".json" and not _looks_like_spine_json(path):
                continue
            if path in seen:
                continue
            seen.add(path)
            results.append(path)
    return sorted(results)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--width", type=int, default=720)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    root = Path(args.root)
    candidates = _candidates(root)
    if args.limit > 0:
        candidates = candidates[: args.limit]
    print(f"candidates={len(candidates)}")

    results = []
    counts: dict[str, int] = {}
    for idx, path in enumerate(candidates, 1):
        result = _test_one(path, args.width, args.height)
        results.append(result)
        status = result["status"]
        counts[status] = counts.get(status, 0) + 1
        detail = ""
        if result.get("error"):
            version = f" version={result.get('version')}" if result.get("version") else ""
            detail = f"{version} error={result['error']}"
        elif status in ("pass", "blank"):
            version = f" version={result.get('version')}" if result.get("version") else ""
            detail = (
                f"{version} bones={result['bones']} slots={result['slots']} "
                f"anims={result['animations']} pages={result['pages']}"
            )
        print(f"[{idx}/{len(candidates)}] {status} {path}{detail}")

    print("summary=" + json.dumps(counts, ensure_ascii=False, sort_keys=True))
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(
            json.dumps({"summary": counts, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
