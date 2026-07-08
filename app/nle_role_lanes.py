"""Role-aware lane contracts for Final Cut-style timeline polish."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.nle_connected_clips import ROLE_LABELS, build_role_color_status, infer_clip_role, role_color_for


ROLE_LANES_SCHEMA = "tigerstudio.nle.role_lanes.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _clip_end(clip: Any) -> int:
    explicit = _attr(clip, "timeline_out_ms", None)
    if explicit is not None:
        return _int(explicit, _int(_attr(clip, "timeline_in_ms", 0), 0))
    start = _int(_attr(clip, "timeline_in_ms", 0), 0)
    source_out = _int(_attr(clip, "source_out_ms", 0), 0)
    source_in = _int(_attr(clip, "source_in_ms", 0), 0)
    duration = max(0, source_out - source_in)
    if duration <= 0:
        duration = _int(_attr(clip, "source_duration_ms", 0), 0)
    return start + duration


def build_role_lane_status(
    tracks: Sequence[Any],
    *,
    focused_role: str = "",
) -> dict[str, Any]:
    lanes: dict[str, dict[str, Any]] = {}
    for track in tracks or []:
        track_id = _int(_attr(track, "id", -1), -1)
        for clip in list(_attr(track, "clips", []) or []):
            role = infer_clip_role(track, clip)
            lane = lanes.setdefault(
                role,
                {
                    "role": role,
                    "label": ROLE_LABELS.get(role, role),
                    "color": role_color_for(role, _attr(clip, "role_color", "")),
                    "clip_count": 0,
                    "connected_count": 0,
                    "audition_count": 0,
                    "duration_ms": 0,
                    "clips": [],
                },
            )
            start = _int(_attr(clip, "timeline_in_ms", 0), 0)
            end = max(start, _clip_end(clip))
            lane["clip_count"] += 1
            lane["duration_ms"] += max(0, end - start)
            if _attr(clip, "connected_parent_clip_id", None) is not None:
                lane["connected_count"] += 1
            if list(_attr(clip, "audition_takes", []) or []):
                lane["audition_count"] += 1
            lane["clips"].append(
                {
                    "track_id": track_id,
                    "clip_id": _int(_attr(clip, "id", 0), 0),
                    "start_ms": start,
                    "end_ms": end,
                    "connected": _attr(clip, "connected_parent_clip_id", None) is not None,
                    "audition_take_count": len(list(_attr(clip, "audition_takes", []) or [])),
                    "active_take_id": str(_attr(clip, "audition_active_take_id", "") or ""),
                }
            )
    ordered = sorted(lanes.values(), key=lambda row: (-_int(row.get("duration_ms"), 0), str(row.get("role") or "")))
    focus = str(focused_role or "").strip()
    return {
        "schema": ROLE_LANES_SCHEMA,
        "ready": True,
        "focused_role": focus,
        "lane_count": len(ordered),
        "clip_count": sum(_int(row.get("clip_count"), 0) for row in ordered),
        "lanes": ordered,
        "role_colors": build_role_color_status(tracks),
    }


def role_lane_contract_evidence(action_ids: Sequence[str] | None = None) -> dict[str, Any]:
    action_set = {str(action_id) for action_id in (action_ids or []) if str(action_id or "").strip()}
    required = {"timeline.role_lanes.status", "timeline.role_lanes.focus"}
    return {
        "schema": "tigerstudio.nle.role_lane_contract.v1",
        "ok": required <= action_set,
        "required_actions": sorted(required),
        "available_actions": sorted(required & action_set),
    }
