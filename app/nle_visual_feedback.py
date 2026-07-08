"""UI-ready Final Cut-style NLE visual feedback contracts.

The functions here are pure.  They convert track/clip-like objects into small
JSON-ready payloads for timeline drawing, Python Actions, QA, and future UI
renewal work without reaching into Qt widgets.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.nle_connected_clips import (
    ROLE_COLORS,
    ROLE_LABELS,
    build_connected_clip_status,
    infer_clip_role,
    normalize_clip_role,
    role_color_for,
)
from app.nle_role_lanes import build_role_lane_status


CONNECTED_ANCHOR_OVERLAY_SCHEMA = "tigerstudio.nle.connected_anchor_overlay.v1"
ROLE_LANE_FILTER_SCHEMA = "tigerstudio.nle.role_lane_filter_model.v1"
MAGNETIC_DRAG_PREVIEW_SCHEMA = "tigerstudio.nle.magnetic_drag_preview.v1"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _attr(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _track_id(track: Any, index: int = 0) -> int:
    return _int(_attr(track, "id", index), index)


def _clip_id(clip: Any, index: int = 0) -> int:
    return _int(_attr(clip, "id", index), index)


def _clip_start(clip: Any) -> int:
    return _int(_attr(clip, "timeline_in_ms", 0), 0)


def _clip_end(clip: Any) -> int:
    explicit = _attr(clip, "timeline_out_ms", None)
    if explicit is not None:
        return max(_clip_start(clip), _int(explicit, _clip_start(clip)))
    source_out = _int(_attr(clip, "source_out_ms", 0), 0)
    source_in = _int(_attr(clip, "source_in_ms", 0), 0)
    duration = max(0, source_out - source_in)
    if duration <= 0:
        duration = _int(_attr(clip, "source_duration_ms", _attr(clip, "duration_ms", 0)), 0)
    return _clip_start(clip) + max(0, duration)


def _clips(track: Any) -> list[Any]:
    return [clip for clip in list(_attr(track, "clips", []) or []) if clip is not None]


def _track_label(track: Any, fallback: str) -> str:
    return str(_attr(track, "display_name", "") or _attr(track, "label", "") or _attr(track, "name", "") or fallback)


def _selected_match(
    *,
    selected_track_id: int | None,
    selected_clip_id: int | None,
    track_id: int,
    clip_id: int,
) -> bool:
    if selected_track_id is None and selected_clip_id is None:
        return False
    if selected_track_id is not None and _int(selected_track_id, -1) != track_id:
        return False
    if selected_clip_id is not None and _int(selected_clip_id, -1) != clip_id:
        return False
    return True


def build_connected_anchor_overlay(
    tracks: Sequence[Any],
    *,
    selected_track_id: int | None = None,
    selected_clip_id: int | None = None,
) -> dict[str, Any]:
    """Return timeline anchor-line descriptors for connected clips."""

    track_rows = list(tracks or [])
    track_order = {_track_id(track, index): index for index, track in enumerate(track_rows)}
    track_labels = {
        _track_id(track, index): _track_label(track, f"Track {_track_id(track, index)}")
        for index, track in enumerate(track_rows)
    }
    parent_index: dict[tuple[int, int], Any] = {}
    for track_index, track in enumerate(track_rows):
        tid = _track_id(track, track_index)
        for clip_index, clip in enumerate(_clips(track)):
            parent_index[(tid, _clip_id(clip, clip_index))] = clip

    status = build_connected_clip_status(track_rows)
    anchors: list[dict[str, Any]] = []
    for row in list(status.get("connected") or []):
        child_tid = _int(row.get("child_track_id"), -1)
        child_cid = _int(row.get("child_clip_id"), -1)
        parent_tid = _int(row.get("parent_track_id"), -1)
        parent_cid = _int(row.get("parent_clip_id"), -1)
        child = parent_index.get((child_tid, child_cid))
        parent = parent_index.get((parent_tid, parent_cid))
        child_start = _clip_start(child) if child is not None else _int(row.get("current_start_ms"), 0)
        child_end = _clip_end(child) if child is not None else child_start
        parent_start = _clip_start(parent) if parent is not None else None
        parent_end = _clip_end(parent) if parent is not None else None
        expected = row.get("expected_start_ms")
        expected_ms = _int(expected, child_start) if expected is not None else None
        delta_ms = child_start - expected_ms if expected_ms is not None else 0
        missing_parent = bool(row.get("missing_parent"))
        in_sync = bool(row.get("in_sync"))
        state = "missing_parent" if missing_parent else ("ok" if in_sync else "offset_mismatch")
        role = str(row.get("role") or infer_clip_role({}, child) if child is not None else "b_roll")
        color = role_color_for(role, str(row.get("role_color") or ""))
        selected = _selected_match(
            selected_track_id=selected_track_id,
            selected_clip_id=selected_clip_id,
            track_id=child_tid,
            clip_id=child_cid,
        ) or _selected_match(
            selected_track_id=selected_track_id,
            selected_clip_id=selected_clip_id,
            track_id=parent_tid,
            clip_id=parent_cid,
        )
        anchors.append(
            {
                "id": f"{parent_tid}:{parent_cid}->{child_tid}:{child_cid}",
                "state": state,
                "line_style": "missing" if missing_parent else ("solid" if in_sync else "warning"),
                "selected": bool(selected),
                "color": color,
                "role": normalize_clip_role(role, fallback="b_roll"),
                "label": ROLE_LABELS.get(normalize_clip_role(role, fallback="b_roll"), role),
                "parent": {
                    "track_id": parent_tid,
                    "clip_id": parent_cid,
                    "lane_index": track_order.get(parent_tid, -1),
                    "track_label": track_labels.get(parent_tid, ""),
                    "start_ms": parent_start,
                    "end_ms": parent_end,
                },
                "child": {
                    "track_id": child_tid,
                    "clip_id": child_cid,
                    "lane_index": track_order.get(child_tid, -1),
                    "track_label": track_labels.get(child_tid, ""),
                    "start_ms": child_start,
                    "end_ms": child_end,
                },
                "anchor_ms": expected_ms if expected_ms is not None else child_start,
                "connected_offset_ms": _int(row.get("connected_offset_ms"), 0),
                "delta_ms": delta_ms,
                "tooltip": (
                    "Missing parent clip"
                    if missing_parent
                    else (
                        "Connected clip is offset by "
                        f"{delta_ms:+d} ms" if not in_sync else "Connected clip anchor"
                    )
                ),
            }
        )

    return {
        "schema": CONNECTED_ANCHOR_OVERLAY_SCHEMA,
        "ready": True,
        "track_count": len(track_rows),
        "anchor_count": len(anchors),
        "issue_count": _int(status.get("issue_count"), 0),
        "selected_track_id": selected_track_id,
        "selected_clip_id": selected_clip_id,
        "anchors": anchors,
        "role_colors": status.get("role_colors", {}),
    }


def build_role_lane_filter_model(
    tracks: Sequence[Any],
    *,
    focused_role: str = "",
    include_empty_roles: bool = True,
) -> dict[str, Any]:
    """Return a role filter model suitable for a Final Cut-style role panel."""

    focus = str(focused_role or "").strip()
    normalized_focus = normalize_clip_role(focus, fallback="primary") if focus else ""
    status = build_role_lane_status(tracks, focused_role=normalized_focus)
    lanes_by_role = {str(row.get("role") or ""): dict(row) for row in list(status.get("lanes") or [])}
    role_order = list(lanes_by_role)
    if include_empty_roles:
        for role in ROLE_COLORS:
            if role not in role_order:
                role_order.append(role)

    filters: list[dict[str, Any]] = []
    visible_clips: list[dict[str, int]] = []
    hidden_clips: list[dict[str, int]] = []
    for role in role_order:
        lane = lanes_by_role.get(role, {"role": role, "clips": [], "clip_count": 0, "duration_ms": 0})
        visible = not normalized_focus or role == normalized_focus
        clips = [
            {"track_id": _int(clip.get("track_id"), -1), "clip_id": _int(clip.get("clip_id"), -1)}
            for clip in list(lane.get("clips") or [])
        ]
        if visible:
            visible_clips.extend(clips)
        else:
            hidden_clips.extend(clips)
        filters.append(
            {
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "color": role_color_for(role, str(lane.get("color") or "")),
                "clip_count": _int(lane.get("clip_count"), 0),
                "duration_ms": _int(lane.get("duration_ms"), 0),
                "connected_count": _int(lane.get("connected_count"), 0),
                "audition_count": _int(lane.get("audition_count"), 0),
                "active": bool(visible),
                "focused": bool(normalized_focus and role == normalized_focus),
                "dimmed": bool(normalized_focus and role != normalized_focus),
                "empty": _int(lane.get("clip_count"), 0) <= 0,
            }
        )

    return {
        "schema": ROLE_LANE_FILTER_SCHEMA,
        "ready": True,
        "focused_role": normalized_focus,
        "filter_count": len(filters),
        "active_filter_count": sum(1 for row in filters if row["active"]),
        "visible_clip_count": len(visible_clips),
        "hidden_clip_count": len(hidden_clips),
        "filters": filters,
        "visible_clips": visible_clips,
        "hidden_clips": hidden_clips,
        "lane_status": status,
    }


def _find_track_and_clip(tracks: Sequence[Any], *, track_id: int, clip_id: int) -> tuple[Any | None, Any | None]:
    wanted_track = _int(track_id, -1)
    wanted_clip = _int(clip_id, -1)
    for track_index, track in enumerate(tracks or []):
        if _track_id(track, track_index) != wanted_track:
            continue
        for clip_index, clip in enumerate(_clips(track)):
            if _clip_id(clip, clip_index) == wanted_clip:
                return track, clip
    return None, None


def _nearest_snap(target_start_ms: int, boundaries: Sequence[int], threshold: int) -> dict[str, Any]:
    best: tuple[int, int] | None = None
    for boundary in boundaries:
        distance = abs(_int(boundary, 0) - target_start_ms)
        if distance > threshold:
            continue
        candidate = (distance, _int(boundary, 0))
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return {"applied": False, "from_ms": target_start_ms, "to_ms": target_start_ms, "distance_ms": None}
    return {
        "applied": True,
        "from_ms": target_start_ms,
        "to_ms": best[1],
        "boundary_ms": best[1],
        "distance_ms": best[0],
    }


def build_magnetic_drag_preview(
    tracks: Sequence[Any],
    *,
    track_id: int,
    clip_id: int,
    target_start_ms: int,
    snap_threshold_ms: int = 120,
) -> dict[str, Any]:
    """Simulate a drag in a magnetic storyline without mutating the timeline."""

    track, target_clip = _find_track_and_clip(tracks, track_id=track_id, clip_id=clip_id)
    if track is None or target_clip is None:
        return {
            "schema": MAGNETIC_DRAG_PREVIEW_SCHEMA,
            "ready": False,
            "reason": "clip_not_found",
            "track_id": _int(track_id, -1),
            "clip_id": _int(clip_id, -1),
            "placements": [],
        }
    if bool(_attr(track, "locked", False)):
        return {
            "schema": MAGNETIC_DRAG_PREVIEW_SCHEMA,
            "ready": False,
            "reason": "track_locked",
            "track_id": _int(track_id, -1),
            "clip_id": _int(clip_id, -1),
            "placements": [],
        }

    threshold = max(0, _int(snap_threshold_ms, 120))
    requested = max(0, _int(target_start_ms, 0))
    target_tid = _int(track_id, -1)
    target_cid = _int(clip_id, -1)
    other_clips = [clip for clip in _clips(track) if _clip_id(clip) != target_cid]
    boundaries: list[int] = []
    for clip in other_clips:
        boundaries.extend([_clip_start(clip), _clip_end(clip)])
    snap = _nearest_snap(requested, boundaries, threshold)
    snapped = max(0, _int(snap.get("to_ms"), requested))

    items: list[dict[str, Any]] = []
    for index, clip in enumerate(_clips(track)):
        cid = _clip_id(clip, index)
        original_start = _clip_start(clip)
        duration = max(0, _clip_end(clip) - original_start)
        proposed_start = snapped if cid == target_cid else original_start
        items.append(
            {
                "track_id": target_tid,
                "clip_id": cid,
                "original_start_ms": original_start,
                "duration_ms": duration,
                "proposed_start_ms": proposed_start,
                "target": cid == target_cid,
            }
        )

    placements: list[dict[str, Any]] = []
    cursor = 0
    for item in sorted(items, key=lambda row: (_int(row["proposed_start_ms"], 0), 0 if row["target"] else 1, _int(row["clip_id"], 0))):
        proposed_start = max(0, _int(item["proposed_start_ms"], 0))
        adjusted_start = max(proposed_start, cursor)
        duration = max(0, _int(item["duration_ms"], 0))
        adjusted_end = adjusted_start + duration
        original_start = _int(item["original_start_ms"], 0)
        placements.append(
            {
                "track_id": target_tid,
                "clip_id": _int(item["clip_id"], -1),
                "target": bool(item["target"]),
                "original_start_ms": original_start,
                "proposed_start_ms": proposed_start,
                "adjusted_start_ms": adjusted_start,
                "adjusted_end_ms": adjusted_end,
                "duration_ms": duration,
                "delta_ms": adjusted_start - original_start,
                "pushed_by_magnetic": bool((not item["target"]) and adjusted_start != original_start),
                "target_collision_adjusted": bool(item["target"] and adjusted_start != proposed_start),
            }
        )
        cursor = max(cursor, adjusted_end)

    target_placement = next((row for row in placements if row["target"]), None)
    pushed = [row for row in placements if row["pushed_by_magnetic"]]
    feedback = "snap" if bool(snap.get("applied")) else "free"
    if pushed:
        feedback = "push"
    if target_placement and bool(target_placement.get("target_collision_adjusted")):
        feedback = "collision"
    return {
        "schema": MAGNETIC_DRAG_PREVIEW_SCHEMA,
        "ready": True,
        "track_id": target_tid,
        "clip_id": target_cid,
        "requested_start_ms": requested,
        "snapped_start_ms": snapped,
        "snap_threshold_ms": threshold,
        "snap": snap,
        "feedback": feedback,
        "target_adjusted_start_ms": _int(target_placement.get("adjusted_start_ms"), snapped) if target_placement else snapped,
        "target_adjusted_end_ms": _int(target_placement.get("adjusted_end_ms"), snapped) if target_placement else snapped,
        "pushed_clip_count": len(pushed),
        "changed_clip_count": sum(1 for row in placements if _int(row.get("delta_ms"), 0) != 0),
        "placements": placements,
    }


__all__ = [
    "CONNECTED_ANCHOR_OVERLAY_SCHEMA",
    "MAGNETIC_DRAG_PREVIEW_SCHEMA",
    "ROLE_LANE_FILTER_SCHEMA",
    "build_connected_anchor_overlay",
    "build_magnetic_drag_preview",
    "build_role_lane_filter_model",
]
