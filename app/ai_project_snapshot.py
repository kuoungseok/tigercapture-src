"""Read-only project snapshots for AI/agent planning."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
import hashlib
from typing import Any


AI_PROJECT_SNAPSHOT_SCHEMA_VERSION = 1


def _int(value: Any, fallback: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(fallback)


def _bool(value: Any) -> bool:
    return bool(value)


def _clip_end_ms(clip: Any, start_ms: int) -> int:
    out = getattr(clip, "timeline_out_ms", None)
    if out is not None:
        return max(start_ms, _int(out, start_ms))
    return start_ms + max(0, _int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0)))


def _audio_end_ms(clip: Any, start_ms: int) -> int:
    return start_ms + max(0, _int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0)))


def _media_kind(path: str) -> str:
    suffix = Path(path).suffix.casefold()
    if suffix in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".mpg", ".mpeg", ".wmv", ".gif"}:
        return "video"
    if suffix in {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp2", ".wma"}:
        return "audio"
    if suffix in {".skel", ".json", ".atlas"}:
        return "actor"
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        return "image"
    return "unknown"


def _hash_snapshot(snapshot: dict[str, Any]) -> str:
    import json

    clone = {key: value for key, value in snapshot.items() if key != "snapshot_hash"}
    raw = json.dumps(clone, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _video_tracks(editor: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_index, track in enumerate(getattr(editor, "_tracks", []) or []):
        clips: list[dict[str, Any]] = []
        for clip_index, clip in enumerate(getattr(track, "clips", []) or []):
            start = _int(getattr(clip, "timeline_in_ms", getattr(clip, "offset_ms", 0)))
            end = _clip_end_ms(clip, start)
            path = str(getattr(clip, "source_path", "") or "")
            clips.append(
                {
                    "id": _int(getattr(clip, "id", clip_index + 1), clip_index + 1),
                    "index": clip_index,
                    "source_path": path,
                    "name": Path(path).name if path else "",
                    "timeline_in_ms": start,
                    "timeline_out_ms": end,
                    "duration_ms": max(0, end - start),
                    "source_in_ms": _int(getattr(clip, "source_in_ms", 0)),
                    "source_out_ms": _int(getattr(clip, "source_out_ms", 0)),
                    "speed": float(getattr(clip, "speed", 1.0) or 1.0),
                    "has_zoom": bool(getattr(clip, "zoom_actors", None)),
                    "has_cursor_events": bool(getattr(clip, "cursor_events", None)),
                    "has_filters": bool(getattr(clip, "video_filters", None) or getattr(clip, "chroma_key", None)),
                }
            )
        rows.append(
            {
                "id": _int(getattr(track, "id", track_index + 1), track_index + 1),
                "index": track_index,
                "locked": _bool(getattr(track, "locked", False)),
                "muted": _bool(getattr(track, "muted", False)),
                "clips": clips,
            }
        )
    return rows


def _audio_tracks(editor: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for track_index, track in enumerate(getattr(editor, "_audio_tracks", []) or []):
        clips: list[dict[str, Any]] = []
        for clip_index, clip in enumerate(getattr(track, "clips", []) or []):
            start = _int(getattr(clip, "offset_ms", 0))
            end = _audio_end_ms(clip, start)
            path = str(getattr(clip, "source_path", "") or "")
            clips.append(
                {
                    "id": _int(getattr(clip, "id", clip_index + 1), clip_index + 1),
                    "index": clip_index,
                    "source_path": path,
                    "name": Path(path).name if path else "",
                    "offset_ms": start,
                    "end_ms": end,
                    "duration_ms": max(0, end - start),
                    "trim_start_ms": _int(getattr(clip, "trim_start_ms", 0)),
                    "trim_end_ms": _int(getattr(clip, "trim_end_ms", 0)),
                    "volume_db": float(getattr(clip, "volume_db", 0.0) or 0.0),
                }
            )
        rows.append(
            {
                "id": _int(getattr(track, "id", track_index + 1), track_index + 1),
                "index": track_index,
                "locked": _bool(getattr(track, "locked", False)),
                "muted": _bool(getattr(track, "muted", False)),
                "clips": clips,
            }
        )
    return rows


def _subtitles(editor: Any) -> list[dict[str, Any]]:
    panel = getattr(editor, "_subtitle_panel", None)
    if panel is None or not hasattr(panel, "subtitles"):
        return []
    rows: list[dict[str, Any]] = []
    try:
        subtitles = panel.subtitles()
    except Exception:
        return []
    for idx, sub in enumerate(subtitles or []):
        text = str(getattr(sub, "text", "") or "")
        rows.append(
            {
                "id": str(getattr(sub, "id", "") or f"subtitle_{idx + 1}"),
                "start_ms": _int(getattr(sub, "start_ms", 0)),
                "end_ms": _int(getattr(sub, "end_ms", 0)),
                "text": text,
                "text_len": len(text),
            }
        )
    return rows


def _media_pool_items(editor: Any, limit: int) -> list[dict[str, Any]]:
    pool = getattr(editor, "_media_pool", None)
    if pool is None or not hasattr(pool, "items"):
        return []
    try:
        paths = list(pool.items() or [])
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(paths[: max(0, int(limit))]):
        path = str(raw or "")
        rows.append(
            {
                "id": f"media_{idx + 1}",
                "path": path,
                "name": Path(path).name if path else "",
                "kind": _media_kind(path),
            }
        )
    return rows


def _selected_clips(editor: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in list(getattr(editor, "_selected_clips", []) or []):
        if isinstance(raw, dict):
            rows.append(
                {
                    "track_kind": str(raw.get("track_kind") or raw.get("kind") or "video"),
                    "track_id": _int(raw.get("track_id")),
                    "clip_id": _int(raw.get("clip_id")),
                }
            )
            continue
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)) and len(raw) >= 2:
            rows.append({"track_id": _int(raw[0]), "clip_id": _int(raw[1])})
    return rows


def _current_position_ms(editor: Any) -> int:
    player = getattr(editor, "_player", None)
    if player is None or not hasattr(player, "position"):
        return 0
    try:
        return max(0, _int(player.position()))
    except Exception:
        return 0


def project_duration_ms(snapshot: dict[str, Any]) -> int:
    end = 0
    for track_key in ("video_tracks", "audio_tracks"):
        for track in snapshot.get(track_key) or []:
            for clip in track.get("clips") or []:
                end = max(end, _int(clip.get("timeline_out_ms", clip.get("end_ms", 0))))
    for row in snapshot.get("subtitles") or []:
        end = max(end, _int(row.get("end_ms", 0)))
    for marker in snapshot.get("markers") or []:
        end = max(end, _int(marker.get("end_ms", marker.get("ms", 0))))
    return end


def build_project_snapshot_from_editor(editor: Any, *, media_limit: int = 200) -> dict[str, Any]:
    video_tracks = _video_tracks(editor)
    audio_tracks = _audio_tracks(editor)
    subtitles = _subtitles(editor)
    markers = [dict(row) for row in list(getattr(editor, "_timeline_markers", []) or []) if isinstance(row, dict)]
    snapshot: dict[str, Any] = {
        "schema_version": AI_PROJECT_SNAPSHOT_SCHEMA_VERSION,
        "source": "TigerCapture",
        "project_path": str(getattr(editor, "_project_path", "") or ""),
        "current_position_ms": _current_position_ms(editor),
        "video_tracks": video_tracks,
        "audio_tracks": audio_tracks,
        "subtitles": subtitles,
        "markers": markers,
        "media_pool": _media_pool_items(editor, media_limit),
        "selected_clips": _selected_clips(editor),
        "settings": {
            "screenstudio_mode": bool((getattr(editor, "_project_settings", {}) or {}).get("screenstudio_mode")),
            "language": str((getattr(editor, "_project_settings", {}) or {}).get("language") or ""),
        },
    }
    snapshot["duration_ms"] = project_duration_ms(snapshot)
    snapshot["locks"] = {
        "locked_video_track_ids": [
            row["id"] for row in video_tracks if row.get("locked") and row.get("clips")
        ],
        "locked_audio_track_ids": [
            row["id"] for row in audio_tracks if row.get("locked") and row.get("clips")
        ],
    }
    snapshot["summary"] = {
        "video_track_count": len(video_tracks),
        "audio_track_count": len(audio_tracks),
        "video_clip_count": sum(len(row.get("clips") or []) for row in video_tracks),
        "audio_clip_count": sum(len(row.get("clips") or []) for row in audio_tracks),
        "subtitle_count": len(subtitles),
        "marker_count": len(markers),
        "media_pool_count": len(snapshot["media_pool"]),
        "selected_clip_count": len(snapshot["selected_clips"]),
    }
    snapshot["snapshot_hash"] = _hash_snapshot(snapshot)
    return snapshot


def minimal_project_snapshot(duration_ms: int = 0) -> dict[str, Any]:
    snapshot = {
        "schema_version": AI_PROJECT_SNAPSHOT_SCHEMA_VERSION,
        "source": "TigerCapture",
        "project_path": "",
        "current_position_ms": 0,
        "duration_ms": max(0, _int(duration_ms)),
        "video_tracks": [],
        "audio_tracks": [],
        "subtitles": [],
        "markers": [],
        "media_pool": [],
        "selected_clips": [],
        "settings": {},
        "locks": {"locked_video_track_ids": [], "locked_audio_track_ids": []},
        "summary": {},
    }
    snapshot["snapshot_hash"] = _hash_snapshot(snapshot)
    return snapshot
