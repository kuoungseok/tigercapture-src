"""Small persistent preview-frame cache for Live2D/Spine actors."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def actor_prerender_root() -> Path:
    root = ROOT / "debugCapture" / "actor_prerender_cache"
    root.mkdir(parents=True, exist_ok=True)
    return root


def actor_prerender_key(kind: str, path: str, *, width: int, height: int, duration_ms: int, fps: int) -> str:
    p = Path(path)
    try:
        st = p.stat()
        material = f"{kind}|{p.resolve()}|{st.st_mtime_ns}|{st.st_size}|{width}x{height}|{duration_ms}|{fps}"
    except Exception:
        material = f"{kind}|{path}|{width}x{height}|{duration_ms}|{fps}"
    return hashlib.sha1(material.encode("utf-8", "replace")).hexdigest()[:18]


def _manifest_path(folder: Path) -> Path:
    return folder / "manifest.json"


def _write_manifest(folder: Path, payload: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    _manifest_path(folder).write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _sample_positions(duration_ms: int, fps: int, limit_frames: int | None = None) -> list[int]:
    duration_ms = max(1, int(duration_ms or 1))
    fps = max(1, min(60, int(fps or 12)))
    frame_count = max(1, int(round(duration_ms / 1000.0 * fps)))
    if limit_frames is not None:
        frame_count = min(frame_count, max(1, int(limit_frames)))
    if frame_count <= 1:
        return [0]
    return [
        max(0, min(duration_ms, int(round(duration_ms * idx / (frame_count - 1)))))
        for idx in range(frame_count)
    ]


def _spine_defaults(path: str) -> tuple[str, str]:
    try:
        from tools.test_spine_resources import _find_atlas, _pick_animation
        from app.spine_editor.spine_json_parser import load_spine_file

        skel = load_spine_file(path)
        atlas = _find_atlas(Path(path))
        return (str(atlas) if atlas else "", _pick_animation(skel))
    except Exception:
        return "", ""


def prerender_actor_preview(
    kind: str,
    path: str,
    *,
    width: int = 360,
    height: int = 360,
    fps: int = 12,
    duration_ms: int = 1000,
    limit_frames: int | None = None,
) -> dict[str, Any]:
    """Render a short PNG sequence for faster actor previews and diagnostics."""
    started = time.perf_counter()
    from app.actor_compat_repair import repair_actor_model_path

    kind = str(kind or "").lower()
    repair = repair_actor_model_path(kind, path)
    load_path = str(repair.get("path") or path)
    key = actor_prerender_key(kind, load_path, width=width, height=height, duration_ms=duration_ms, fps=fps)
    folder = actor_prerender_root() / key
    frames: list[dict[str, Any]] = []
    status = "pass"
    error = ""
    try:
        if kind == "live2d":
            import os

            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            from PySide6.QtWidgets import QApplication
            from app.live2d.actor_track import Live2DActorClip

            QApplication.instance() or QApplication([])
            clip = Live2DActorClip(model_path=load_path, start_ms=0, duration_ms=max(1, int(duration_ms)))
            for index, pos_ms in enumerate(_sample_positions(duration_ms, fps, limit_frames)):
                img = clip.render_frame(width, height, pos_ms)
                if img is None:
                    status = "render_none"
                    frames.append({"index": index, "pos_ms": pos_ms, "path": "", "nonblank": False})
                    continue
                out = folder / f"frame_{index:04d}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(out)
                bbox = img.getchannel("A").getbbox()
                frames.append({"index": index, "pos_ms": pos_ms, "path": str(out), "nonblank": bbox is not None})
        elif kind == "spine":
            from app.spine_editor.actor_track import SpineActorClip

            atlas_path, anim = _spine_defaults(load_path)
            clip = SpineActorClip(
                skel_path=load_path,
                atlas_path=atlas_path,
                anim_name=anim,
                start_ms=0,
                duration_ms=max(1, int(duration_ms)),
            )
            for index, pos_ms in enumerate(_sample_positions(duration_ms, fps, limit_frames)):
                img = clip.render_frame(width, height, pos_ms, fast_preview=True)
                if img is None:
                    status = "render_none"
                    frames.append({"index": index, "pos_ms": pos_ms, "path": "", "nonblank": False})
                    continue
                out = folder / f"frame_{index:04d}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                img.save(out)
                bbox = img.getchannel("A").getbbox()
                frames.append({"index": index, "pos_ms": pos_ms, "path": str(out), "nonblank": bbox is not None})
        else:
            status = "fail"
            error = f"unknown actor kind: {kind}"
    except Exception as exc:
        status = "crash"
        error = f"{type(exc).__name__}: {exc}"
    if status == "pass" and any(not row.get("nonblank") for row in frames):
        status = "blank"
    payload = {
        "ok": status == "pass",
        "status": status,
        "kind": kind,
        "source_path": str(path),
        "load_path": load_path,
        "key": key,
        "folder": str(folder),
        "frame_count": len(frames),
        "frames": frames,
        "width": int(width),
        "height": int(height),
        "fps": int(fps),
        "duration_ms": int(duration_ms),
        "repair": repair,
        "error": error,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
    }
    _write_manifest(folder, payload)
    try:
        from app.actor_loading_cache import record_actor_load

        record_actor_load(kind, load_path, status=status, stage="ready" if status == "pass" else "error", prerender=payload)
    except Exception:
        pass
    return payload


def actor_prerender_cache_report(root: Path | None = None) -> dict[str, Any]:
    base = root or actor_prerender_root()
    manifests = sorted(base.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    entries: list[dict[str, Any]] = []
    for manifest in manifests:
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    counts: dict[str, int] = {}
    for row in entries:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return {
        "ok": True,
        "path": str(base),
        "summary": {
            "entries": len(entries),
            "status_counts": dict(sorted(counts.items())),
            "frames": sum(int(row.get("frame_count", 0) or 0) for row in entries),
        },
        "entries": entries,
    }


def _paths_match(request_path: str, entry: dict[str, Any]) -> bool:
    candidates = {
        str(entry.get("source_path") or ""),
        str(entry.get("load_path") or ""),
    }
    repair = entry.get("repair") if isinstance(entry.get("repair"), dict) else {}
    candidates.add(str(repair.get("original_path") or ""))
    candidates.add(str(repair.get("path") or ""))
    try:
        req = str(Path(request_path).resolve())
    except Exception:
        req = str(request_path)
    normalized = set()
    for value in candidates:
        if not value:
            continue
        normalized.add(value)
        try:
            normalized.add(str(Path(value).resolve()))
        except Exception:
            pass
    return req in normalized or str(request_path) in normalized


def _pick_frame(frames: list[dict[str, Any]], local_ms: int, duration_ms: int) -> Path | None:
    valid = [row for row in frames if isinstance(row, dict) and row.get("path")]
    if not valid:
        return None
    duration_ms = max(1, int(duration_ms or 1))
    local_ms = max(0, min(duration_ms, int(local_ms or 0)))
    best = min(valid, key=lambda row: abs(int(row.get("pos_ms", 0) or 0) - local_ms))
    path = Path(str(best.get("path") or ""))
    return path if path.exists() else None


def cached_actor_preview_frame(
    kind: str,
    path: str,
    *,
    width: int,
    height: int,
    local_ms: int = 0,
    duration_ms: int = 1000,
):
    """Return a cached RGBA PIL actor preview frame when an exact cache exists."""
    report = actor_prerender_cache_report()
    for entry in report.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("status") or "") != "pass":
            continue
        if str(entry.get("kind") or "").lower() != str(kind or "").lower():
            continue
        if int(entry.get("width", 0) or 0) != int(width) or int(entry.get("height", 0) or 0) != int(height):
            continue
        if not _paths_match(path, entry):
            continue
        frame_path = _pick_frame(list(entry.get("frames", []) or []), local_ms, duration_ms)
        if frame_path is None:
            continue
        try:
            from PIL import Image

            return Image.open(frame_path).convert("RGBA")
        except Exception:
            continue
    return None
