"""Repair and normalize a TigerCapture `.tgp` project copy.

The original file is never modified. By default this writes
`<name>.repaired.tgp` next to the input and prints a report.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_TOP_LEVEL: dict[str, Any] = {
    "version": "1.1",
    "app": "TigerCapture",
    "px_per_sec": 70.0,
    "playhead_ms": 0,
    "global_in_ms": -1,
    "global_out_ms": -1,
    "project_settings": {},
    "video_tracks": [],
    "audio_tracks": [],
    "subtitles": [],
    "media_pool": [],
    "strokes": [],
    "bubbles": [],
    "stickers": [],
    "timeline_markers": [],
    "lut": {"path": "", "strength": 1.0},
    "export": {},
    "proxy": {"enabled": False, "dir": None},
    "spine_actor_tracks": [],
    "live2d_actor_tracks": [],
    "next_actor_id": 1,
    "next_live2d_id": 1,
}


VIDEO_CLIP_DEFAULTS: dict[str, Any] = {
    "source_duration_ms": 0,
    "timeline_in_ms": 0,
    "source_in_ms": 0,
    "source_out_ms": 0,
    "fades": [],
    "zoom_actors": [],
    "typography_actors": [],
    "speed_segments": [],
    "masks": [],
    "node_graph": None,
    "transition_out_type": "",
    "transition_out_ms": 500,
    "video_filters": None,
    "chroma_key": None,
    "stabilizer": None,
    "bg_removal": None,
    "nested_child_clips": [],
    "nested_child_tracks": [],
    "nested_audio_tracks": [],
    "nested_spine_actor_tracks": [],
    "nested_live2d_actor_tracks": [],
}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _path_exists(raw: Any) -> bool:
    return bool(raw and Path(str(raw)).exists())


def _normalize_video_clip(clip: dict[str, Any], changes: list[str]) -> dict[str, Any]:
    out = dict(clip or {})
    for key, default in VIDEO_CLIP_DEFAULTS.items():
        if key not in out:
            out[key] = deepcopy(default)
            changes.append(f"video clip {out.get('id', '?')}: filled {key}")
    out["timeline_in_ms"] = max(0, int(out.get("timeline_in_ms") or 0))
    out["source_in_ms"] = max(0, int(out.get("source_in_ms") or 0))
    out["source_duration_ms"] = max(0, int(out.get("source_duration_ms") or 0))
    out["source_out_ms"] = int(out.get("source_out_ms") or 0)
    if out["source_out_ms"] <= out["source_in_ms"]:
        duration = out["source_duration_ms"] or 1000
        out["source_out_ms"] = max(out["source_in_ms"] + 1, duration)
        changes.append(f"video clip {out.get('id', '?')}: repaired source_out_ms")
    out["fades"] = _as_list(out.get("fades"))
    out["zoom_actors"] = _as_list(out.get("zoom_actors"))
    out["typography_actors"] = _as_list(out.get("typography_actors"))
    out["speed_segments"] = _as_list(out.get("speed_segments"))
    out["masks"] = _as_list(out.get("masks"))
    out["nested_child_clips"] = [
        _normalize_video_clip(child, changes)
        for child in _as_list(out.get("nested_child_clips"))
        if isinstance(child, dict)
    ]
    out["nested_child_tracks"] = [
        [
            _normalize_video_clip(child, changes)
            for child in _as_list(track)
            if isinstance(child, dict)
        ]
        for track in _as_list(out.get("nested_child_tracks"))
    ]
    out["nested_audio_tracks"] = [
        [
            _normalize_audio_clip(child, changes)
            for child in _as_list(track)
            if isinstance(child, dict)
        ]
        for track in _as_list(out.get("nested_audio_tracks"))
    ]
    return out


def _normalize_audio_clip(clip: dict[str, Any], changes: list[str]) -> dict[str, Any]:
    out = dict(clip or {})
    clip_id = out.get("id", "?")
    defaults = {
        "duration_ms": 0,
        "offset_ms": 0,
        "trim_start_ms": 0,
        "trim_end_ms": 0,
        "fade_in_ms": 0,
        "fade_out_ms": 0,
        "fades": [],
        "volume_points": [],
        "effects": {},
        "gain": 1.0,
    }
    for key, default in defaults.items():
        if key not in out:
            out[key] = deepcopy(default)
            changes.append(f"audio clip {clip_id}: filled {key}")
    out["duration_ms"] = max(0, int(out.get("duration_ms") or 0))
    out["offset_ms"] = max(0, int(out.get("offset_ms") or 0))
    out["trim_start_ms"] = max(0, int(out.get("trim_start_ms") or 0))
    out["trim_end_ms"] = int(out.get("trim_end_ms") or 0)
    if out["trim_end_ms"] <= out["trim_start_ms"]:
        out["trim_end_ms"] = out["duration_ms"] or out["trim_start_ms"] + 1
        changes.append(f"audio clip {clip_id}: repaired trim_end_ms")
    out["fades"] = _as_list(out.get("fades"))
    out["volume_points"] = _as_list(out.get("volume_points"))
    out["effects"] = dict(out.get("effects") or {})
    out["gain"] = float(out.get("gain") or 1.0)
    return out


def _normalize_actor_tracks(tracks: Any, kind: str, changes: list[str]) -> list[dict[str, Any]]:
    fixed: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(tracks)):
        if not isinstance(raw, dict):
            changes.append(f"{kind} track {idx}: dropped non-object track")
            continue
        track = dict(raw)
        if "clips" not in track or not isinstance(track.get("clips"), list):
            track["clips"] = []
            changes.append(f"{kind} track {track.get('id', idx)}: filled clips")
        if kind == "live2d" and "blends" not in track:
            track["blends"] = []
            changes.append(f"live2d track {track.get('id', idx)}: filled blends")
        fixed.append(track)
    return fixed


def _drop_missing_media(doc: dict[str, Any], changes: list[str]) -> None:
    media_pool = []
    for raw in _as_list(doc.get("media_pool")):
        if _path_exists(raw):
            media_pool.append(raw)
        else:
            changes.append(f"media_pool: dropped missing {raw}")
    doc["media_pool"] = media_pool

    for track in _as_list(doc.get("video_tracks")):
        clips = []
        for clip in _as_list(track.get("clips")):
            raw = clip.get("source_path") or track.get("source_path")
            if _path_exists(raw):
                clips.append(clip)
            else:
                changes.append(f"video track {track.get('id', '?')}: dropped missing clip {clip.get('id', '?')}")
        track["clips"] = clips

    for track in _as_list(doc.get("audio_tracks")):
        clips = []
        for clip in _as_list(track.get("clips")):
            if _path_exists(clip.get("source_path")):
                clips.append(clip)
            else:
                changes.append(f"audio track {track.get('id', '?')}: dropped missing clip {clip.get('id', '?')}")
        track["clips"] = clips


def repair_project_doc(raw_doc: dict[str, Any], *, drop_missing_media: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    doc = deepcopy(raw_doc)
    changes: list[str] = []
    for key, default in DEFAULT_TOP_LEVEL.items():
        if key not in doc:
            doc[key] = deepcopy(default)
            changes.append(f"filled top-level {key}")
    doc["app"] = "TigerCapture"
    doc["version"] = str(doc.get("version") or "1.1")
    doc["saved_at"] = datetime.now(timezone.utc).isoformat()

    # De-duplicate media pool without changing order.
    seen: set[str] = set()
    media_pool: list[str] = []
    for raw in _as_list(doc.get("media_pool")):
        value = str(raw)
        if value and value not in seen:
            media_pool.append(value)
            seen.add(value)
    if media_pool != doc.get("media_pool"):
        changes.append("media_pool: removed duplicates/non-list values")
    doc["media_pool"] = media_pool

    video_tracks: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(doc.get("video_tracks"))):
        if not isinstance(raw, dict):
            changes.append(f"video track {idx}: dropped non-object track")
            continue
        track = dict(raw)
        track.setdefault("id", idx + 1)
        track.setdefault("display_name", "")
        track.setdefault("offset_ms", 0)
        track["clips"] = [
            _normalize_video_clip(clip, changes)
            for clip in _as_list(track.get("clips"))
            if isinstance(clip, dict)
        ]
        video_tracks.append(track)
    doc["video_tracks"] = video_tracks

    audio_tracks: list[dict[str, Any]] = []
    for idx, raw in enumerate(_as_list(doc.get("audio_tracks"))):
        if not isinstance(raw, dict):
            changes.append(f"audio track {idx}: dropped non-object track")
            continue
        track = dict(raw)
        track.setdefault("id", idx + 1)
        track.setdefault("display_name", "")
        track.setdefault("volume", 1.0)
        track["clips"] = [
            _normalize_audio_clip(clip, changes)
            for clip in _as_list(track.get("clips"))
            if isinstance(clip, dict)
        ]
        audio_tracks.append(track)
    doc["audio_tracks"] = audio_tracks

    doc["spine_actor_tracks"] = _normalize_actor_tracks(doc.get("spine_actor_tracks"), "spine", changes)
    doc["live2d_actor_tracks"] = _normalize_actor_tracks(doc.get("live2d_actor_tracks"), "live2d", changes)

    if drop_missing_media:
        _drop_missing_media(doc, changes)

    from tools.qa_project_audit import _collect_paths, _missing, _summarize, _actor_asset_audit

    paths = _collect_paths(doc)
    report = {
        "ok": not _missing(paths),
        "changes": changes,
        "summary": _summarize(doc),
        "missing": _missing(paths),
        "actor_assets": _actor_asset_audit(doc),
    }
    if any(not row.get("ok", False) for row in report["actor_assets"]):
        report["ok"] = False
    report["repair_guidance"] = _repair_guidance(report)
    return doc, report


def _missing_preview(missing: dict[str, list[str]], *, limit: int = 8) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for kind, values in sorted((missing or {}).items()):
        for path in values or []:
            rows.append({"kind": str(kind), "path": str(path)})
            if len(rows) >= limit:
                return rows
    return rows


def _actor_failure_preview(
    actor_assets: list[dict[str, Any]],
    *,
    limit: int = 6,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in actor_assets or []:
        if asset.get("ok", False):
            continue
        path = ""
        for key in ("model_path", "skel_path", "atlas_path", "texture_path"):
            if asset.get(key):
                path = str(asset.get(key))
                break
        rows.append({
            "kind": str(asset.get("kind") or ""),
            "track_id": asset.get("track_id"),
            "clip_index": asset.get("clip_index"),
            "path": path,
            "issues": [str(issue) for issue in asset.get("issues", []) or []][:6],
        })
        if len(rows) >= limit:
            break
    return rows


def _candidate_paths_from_roots(roots: list[Path]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            root = Path(root)
            candidates = [root] if root.is_file() else list(root.rglob("*.tgp"))
        except Exception:
            candidates = []
        for path in candidates:
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            name = path.name.lower()
            if (
                "autosave" not in name
                and ".tigercapture_recovery" not in str(path.parent).lower()
                and ".recovery" not in str(path.parent).lower()
            ):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    return paths


def audit_recovery_candidates(
    paths: list[Path],
    *,
    limit: int = 20,
    drop_missing_media: bool = False,
) -> dict[str, Any]:
    """Inspect autosave/recovery project files and rank newest readable ones."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        p = Path(path)
        row: dict[str, Any] = {
            "path": str(p),
            "readable": False,
            "ok": False,
            "mtime": 0.0,
            "size": 0,
            "error": "",
        }
        try:
            st = p.stat()
            row["mtime"] = float(st.st_mtime)
            row["size"] = int(st.st_size)
            raw_doc = json.loads(p.read_text(encoding="utf-8"))
            _doc, report = repair_project_doc(raw_doc, drop_missing_media=drop_missing_media)
            missing = report.get("missing", {}) or {}
            missing_count = sum(len(v or []) for v in missing.values())
            changes = list(report.get("changes", []) or [])
            actor_assets = list(report.get("actor_assets", []) or [])
            actor_failed_count = sum(1 for asset in actor_assets if not asset.get("ok", False))
            guidance = report.get("repair_guidance", {}) or {}
            row.update({
                "readable": True,
                "ok": bool(report.get("ok")),
                "summary": report.get("summary", {}),
                "changes_count": len(report.get("changes", []) or []),
                "changes_preview": [str(change) for change in changes[:8]],
                "missing_count": int(missing_count),
                "missing_by_kind": {
                    str(kind): len(values or [])
                    for kind, values in sorted(missing.items())
                },
                "missing_preview": _missing_preview(missing),
                "actor_assets_ok": all(
                    bool(asset.get("ok", False))
                    for asset in actor_assets
                ),
                "actor_failed_count": int(actor_failed_count),
                "actor_failures_preview": _actor_failure_preview(actor_assets),
                "guidance_actions": [
                    str(action) for action in guidance.get("actions", []) or []
                ],
            })
        except Exception as exc:
            row["error"] = str(exc) or repr(exc)
        rows.append(row)

    rows.sort(key=lambda r: (bool(r.get("readable")), float(r.get("mtime") or 0.0)), reverse=True)
    rows = rows[:max(1, int(limit))]
    best = next((r for r in rows if r.get("readable") and r.get("ok")), None)
    if best is None:
        best = next((r for r in rows if r.get("readable")), None)
    report = {
        "ok": best is not None,
        "best": best,
        "candidates": rows,
    }
    report["product_summary"] = productize_recovery_report(report)
    return report


def _candidate_health(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "level": "none",
            "score": 0,
            "recommended_action": "No readable recovery file was found.",
            "reason": "No candidate could be loaded.",
        }
    if not row.get("readable"):
        return {
            "level": "unreadable",
            "score": 0,
            "recommended_action": "Skip this candidate and inspect a newer readable autosave.",
            "reason": str(row.get("error") or "The project JSON could not be read."),
        }
    missing_count = int(row.get("missing_count", 0) or 0)
    changes_count = int(row.get("changes_count", 0) or 0)
    actor_ok = bool(row.get("actor_assets_ok", True))
    score = 100
    score -= min(45, missing_count * 15)
    score -= min(20, changes_count * 2)
    if not actor_ok:
        score -= 25
    score = max(0, score)
    if row.get("ok") and score >= 80:
        level = "open_safe"
        action = "Open this recovery copy first."
        reason = "It is readable, passes repair audit, and has no major missing dependencies."
    elif missing_count:
        level = "needs_relink"
        action = "Run Relink before serious editing."
        reason = f"{missing_count} referenced media/model path(s) are missing."
    elif not actor_ok:
        level = "actor_assets_need_review"
        action = "Open cautiously and inspect Live2D/Spine clips."
        reason = "One or more actor model dependencies failed audit."
    else:
        level = "repair_recommended"
        action = "Open the repaired copy and save a clean project version."
        reason = "The candidate is readable but needed schema repair."
    return {
        "level": level,
        "score": score,
        "recommended_action": action,
        "reason": reason,
    }


def productize_recovery_report(report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in report.get("candidates", []) or []:
        enriched = dict(row)
        enriched["health"] = _candidate_health(row)
        rows.append(enriched)
    best = report.get("best")
    best_health = _candidate_health(best)
    return {
        "ok": bool(report.get("ok")),
        "best_path": str(best.get("path")) if isinstance(best, dict) else "",
        "best_health": best_health,
        "message": best_health["recommended_action"],
        "candidates": rows,
    }


def _repair_guidance(report: dict[str, Any]) -> dict[str, Any]:
    missing = report.get("missing", {}) or {}
    missing_count = sum(len(values or []) for values in missing.values())
    actor_failed = sum(
        1 for row in report.get("actor_assets", []) or []
        if not row.get("ok", False)
    )
    changes_count = len(report.get("changes", []) or [])
    actions: list[str] = []
    if missing_count:
        actions.append("Open Relink and resolve missing media/model paths.")
    if actor_failed:
        actions.append("Inspect Live2D/Spine model dependencies before export.")
    if changes_count:
        actions.append("Save the repaired copy as a new clean project version.")
    if not actions:
        actions.append("Project is structurally healthy; continue editing.")
    return {
        "missing_count": missing_count,
        "actor_failed": actor_failed,
        "changes_count": changes_count,
        "actions": actions,
        "severity": "high" if missing_count or actor_failed else "low",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path, nargs="?")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--drop-missing-media", action="store_true")
    parser.add_argument(
        "--list-recovery",
        nargs="*",
        type=Path,
        help="Scan autosave/recovery .tgp files under the given roots.",
    )
    args = parser.parse_args()

    if args.list_recovery is not None:
        roots = args.list_recovery
        if not roots:
            try:
                from app.paths import default_save_dir
                roots = [default_save_dir()]
            except Exception:
                roots = [Path.home()]
        paths = _candidate_paths_from_roots(list(roots))
        report = audit_recovery_candidates(
            paths,
            drop_missing_media=args.drop_missing_media,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    if args.project is None:
        parser.error("project is required unless --list-recovery is used")

    source = args.project
    out = args.out or source.with_name(source.stem + ".repaired" + source.suffix)
    report_path = args.report or out.with_suffix(".repair_report.json")
    raw_doc = json.loads(source.read_text(encoding="utf-8"))
    doc, report = repair_project_doc(raw_doc, drop_missing_media=args.drop_missing_media)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    report.update({"source": str(source), "out": str(out)})
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"repaired: {out}")
    print(f"report: {report_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
