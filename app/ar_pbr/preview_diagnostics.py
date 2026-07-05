"""Pure AR/PBR preview diagnostics payload builders."""
from __future__ import annotations

from typing import Any, Mapping


def _int_pair(value: Any) -> list[int]:
    try:
        return [int(value[0]), int(value[1])]
    except Exception:
        return [0, 0]


def _track_id(track: Mapping[str, Any]) -> str:
    return str(track.get("id") or "")


def _first_packet_cache_id(gl_diagnostics: Mapping[str, Any]) -> str:
    rows = gl_diagnostics.get("items") if isinstance(gl_diagnostics, Mapping) else None
    if not isinstance(rows, list):
        return ""
    for item in rows:
        if isinstance(item, Mapping) and item.get("packet_cache_id"):
            return str(item.get("packet_cache_id") or "")
    return ""


def overlay_item_diagnostics(item: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics = item.get("diagnostics") if isinstance(item.get("diagnostics"), Mapping) else {}
    return {
        "track_id": str(item.get("track_id") or ""),
        "packet_cache_id": str(item.get("packet_cache_id") or ""),
        "triangle_count": int(item.get("triangle_count", 0) or 0),
        "pbr_triangle_count": int(item.get("pbr_triangle_count", 0) or 0),
        "diagnostics": dict(diagnostics),
    }


def overlay_diagnostics_payload(
    *,
    items: list[Mapping[str, Any]],
    painter_diagnostics: Mapping[str, Any] | None = None,
    failed: bool = False,
    painter_ready: bool = False,
) -> dict[str, Any]:
    return {
        "item_count": int(len(items)),
        "failed": bool(failed),
        "painter_ready": bool(painter_ready),
        "vbo": dict(painter_diagnostics or {}),
        "items": [overlay_item_diagnostics(item) for item in items],
    }


def preview_diagnostics_payload(
    *,
    tracks: list[Mapping[str, Any]],
    active_tracks: list[Mapping[str, Any]],
    player_diagnostics: Mapping[str, Any] | None = None,
    gl_diagnostics: Mapping[str, Any] | None = None,
    frame_size: Any = None,
    preview_gl_available: bool = False,
) -> dict[str, Any]:
    player_row = dict(player_diagnostics or {})
    gl_row = dict(gl_diagnostics or {})
    packet_cache_id = str(player_row.get("packet_cache_id") or _first_packet_cache_id(gl_row))
    return {
        "track_count": len(tracks),
        "active_track_count": len(active_tracks),
        "active_track_ids": [_track_id(track) for track in active_tracks],
        "preview_frame_size": _int_pair(frame_size),
        "preview_gl_available": bool(preview_gl_available),
        "packet_cache_id": packet_cache_id,
        "packet_cache_hit": bool(player_row.get("packet_cache_hit", False)),
        "playback_optimized": bool(player_row.get("playback_optimized", False)),
        "renderer_mode": str(player_row.get("mode") or ""),
        "player": player_row,
        "gl": gl_row,
    }
