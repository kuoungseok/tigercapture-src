from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg"}
ACTOR_SUFFIXES = {".json", ".atlas", ".skel", ".moc3", ".model3.json"}
PROJECT_SUFFIXES = {".tgp", ".json"}
EXPORT_BAKED_KIND_TARGETS = {
    "effect": "video_filter",
    "transition": "video_transition",
    "title": "text_overlay",
    "caption_style": "text_overlay",
    "sticker": "text_overlay",
    "motion": "timeline_motion",
    "audio": "audio_mix",
    "color": "color_grade",
    "actor": "actor_overlay",
    "template": "template_orchestration",
}


def _walk_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for child in value.values():
            out.extend(_walk_strings(child))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for child in value:
            out.extend(_walk_strings(child))
        return out
    return []


def _walk_numbers_by_key(value: Any, keys: set[str]) -> list[float]:
    if isinstance(value, dict):
        out: list[float] = []
        for key, child in value.items():
            if str(key) in keys:
                try:
                    out.append(float(child))
                except Exception:
                    pass
            out.extend(_walk_numbers_by_key(child, keys))
        return out
    if isinstance(value, list):
        out: list[float] = []
        for child in value:
            out.extend(_walk_numbers_by_key(child, keys))
        return out
    return []


def project_summary_from_file(path: Path | str) -> dict[str, Any]:
    project_path = Path(path)
    text = ""
    raw: Any = {}
    try:
        text = project_path.read_text(encoding="utf-8", errors="replace")
        raw = json.loads(text) if text.strip().startswith(("{", "[")) else {}
    except Exception:
        raw = {}
        try:
            text = project_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = project_path.name
    strings = [project_path.name, *_walk_strings(raw)]
    joined = " ".join(strings).casefold() or text.casefold()
    suffixes: dict[str, int] = {}
    video_count = audio_count = actor_count = 0
    for item in strings:
        lower = str(item).casefold()
        suffix = Path(lower).suffix
        if lower.endswith(".model3.json"):
            suffix = ".model3.json"
        if suffix:
            suffixes[suffix] = suffixes.get(suffix, 0) + 1
        if suffix in VIDEO_SUFFIXES:
            video_count += 1
        elif suffix in AUDIO_SUFFIXES:
            audio_count += 1
        elif suffix in ACTOR_SUFFIXES:
            actor_count += 1
    duration_ms_values = _walk_numbers_by_key(raw, {"duration_ms", "timeline_out_ms", "end_ms", "out_ms"})
    duration_s_values = _walk_numbers_by_key(raw, {"duration_s"})
    duration_s = max(duration_s_values or [0.0])
    if duration_ms_values:
        duration_s = max(duration_s, max(duration_ms_values) / 1000.0)
    if duration_s <= 0:
        duration_s = 60.0
    return {
        "path": str(project_path),
        "duration_s": duration_s,
        "shortform": duration_s <= 90.0 or any(word in joined for word in ("short", "reel", "tiktok")),
        "vertical": any(word in joined for word in ("vertical", "portrait", "shorts", "reel", "tiktok")),
        "media_count": max(video_count + audio_count + actor_count, len([s for s in strings if "." in s])),
        "video_count": video_count,
        "audio_count": audio_count,
        "actor_count": actor_count,
        "suffixes": suffixes,
        "has_audio": audio_count > 0 or "audio" in joined or "voice" in joined or "music" in joined,
        "audio_only": audio_count > 0 and video_count == 0,
        "gameplay": any(word in joined for word in ("game", "capture", "stream", "play")),
        "dialogue": any(word in joined for word in ("voice", "dialogue", "podcast", "talk")),
        "tutorial": any(word in joined for word in ("tutorial", "howto", "guide", "step", "hotkey")),
        "product": any(word in joined for word in ("product", "demo", "review", "shop")),
        "review": "review" in joined or "compare" in joined,
        "broll": "broll" in joined or "b-roll" in joined or "cutaway" in joined,
        "reaction": "reaction" in joined or "meme" in joined,
        "live2d": "live2d" in joined,
        "spine": "spine" in joined,
        "news": "news" in joined,
        "ranking": "ranking" in joined or "top10" in joined,
        "anime": "anime" in joined,
        "mobile": "mobile" in joined,
        "food": "food" in joined,
        "podcast": "podcast" in joined,
        "patch_note": "patch" in joined and "note" in joined,
    }


def build_report(project_paths: list[Path]) -> dict[str, Any]:
    from app.preset_library import (
        one_click_preset_plan,
        preset_ecosystem_report,
        preset_pack_marketplace_report,
    )

    projects = []
    for path in project_paths:
        summary = project_summary_from_file(path)
        plan = one_click_preset_plan(summary)
        export_parity = preset_plan_export_parity(plan)
        projects.append({
            "path": str(path),
            "summary": summary,
            "plan_ids": [preset.id for preset in plan],
            "plan_names": [preset.name for preset in plan],
            "template_first": bool(plan and plan[0].kind == "template"),
            "export_parity": export_parity,
        })
    return {
        "preset_ecosystem": preset_ecosystem_report(),
        "preset_packs": preset_pack_marketplace_report(),
        "projects": projects,
        "ok": (
            all(project.get("template_first") for project in projects)
            and all(dict(project.get("export_parity", {}) or {}).get("ok") for project in projects)
        ) if projects else True,
    }


def preset_plan_export_parity(plan: list[Any]) -> dict[str, Any]:
    """Classify whether preset plan steps have known preview/export bake targets."""
    kind_counts: dict[str, int] = {}
    bake_targets: set[str] = set()
    unknown_kinds: set[str] = set()
    export_critical_ids: list[str] = []
    for preset in plan:
        kind = str(getattr(preset, "kind", "") or "")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
        target = EXPORT_BAKED_KIND_TARGETS.get(kind)
        if target:
            bake_targets.add(target)
            if kind in {"effect", "transition", "title", "caption_style", "sticker", "motion", "audio", "color", "actor"}:
                export_critical_ids.append(str(getattr(preset, "id", "") or ""))
        else:
            unknown_kinds.add(kind or "unknown")
    return {
        "ok": not unknown_kinds,
        "kind_counts": dict(sorted(kind_counts.items())),
        "bake_targets": sorted(bake_targets),
        "unknown_kinds": sorted(unknown_kinds),
        "export_critical_ids": export_critical_ids,
        "notes": (
            "Every preset kind in the plan maps to an export-baked target."
            if not unknown_kinds
            else "Some preset kinds do not have a known export-baked target."
        ),
    }


def discover_project_files(root: Path | str, *, limit: int = 5) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        return []
    ignored_parts = {
        ".git",
        ".venv",
        "__pycache__",
        "debugCapture",
        "build",
        "dist",
        "installer_output",
        "native",
    }
    candidates: list[Path] = []
    for path in root_path.rglob("*"):
        if len(candidates) >= int(limit):
            break
        if not path.is_file() or path.suffix.casefold() not in PROJECT_SUFFIXES:
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        name = path.name.casefold()
        if "preset" in name or "report" in name or "tree" in name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:24000].casefold()
        except Exception:
            text = ""
        if path.suffix.casefold() == ".tgp" or any(
            marker in text
            for marker in (
                "video_tracks",
                "audio_tracks",
                "spine_actor_tracks",
                "live2d_actor_tracks",
                "timeline_in_ms",
                "project_settings",
            )
        ):
            candidates.append(path)
    return candidates[: int(limit)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a preset/template application QA report for real project files.")
    parser.add_argument("projects", nargs="*", type=Path, help="Project JSON/TGP files to summarize.")
    parser.add_argument("--discover-root", type=Path, action="append", help="Root directory to scan for project files when explicit projects are not supplied.")
    parser.add_argument("--limit", type=int, default=5, help="Maximum auto-discovered project files.")
    parser.add_argument("--output", "-o", type=Path, help="Optional JSON report path.")
    args = parser.parse_args()
    project_paths = [path for path in args.projects if path.exists()]
    if not project_paths:
        roots = args.discover_root or [REPO_ROOT / "qa_corpus", REPO_ROOT]
        seen: set[Path] = set()
        for root in roots:
            for path in discover_project_files(root, limit=max(1, args.limit - len(project_paths))):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    project_paths.append(path)
                if len(project_paths) >= args.limit:
                    break
            if len(project_paths) >= args.limit:
                break
    report = build_report(project_paths)
    report["discovered_projects"] = [str(path) for path in project_paths]
    payload = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
