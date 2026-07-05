"""Selection movement, alignment, snap, and ripple-delete action registrations."""
from __future__ import annotations

from typing import Any, Mapping

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def register_selection_movement_actions(registry: Any) -> None:
    """Register selection nudge, alignment, snapping, and ripple-delete actions."""
    registry.register(
        ActionSpec(
            "selection.move",
            "Move all selected video clips by a timeline delta, including linked audio.",
            "selection",
            params_schema=schema_object(
                {
                    "delta_ms": {"type": "integer"},
                    "strict_links": {"type": "boolean"},
                },
                required=("delta_ms",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Move selected clips",
        ),
        lambda params, dry: _selection_move(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "selection.nudge",
            "Nudge all selected video clips by a small timeline delta, including linked audio.",
            "selection",
            params_schema=schema_object(
                {
                    "delta_ms": {"type": "integer"},
                    "strict_links": {"type": "boolean"},
                },
                required=("delta_ms",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Nudge selected clips",
        ),
        lambda params, dry: _selection_nudge(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "selection.nudge_frames",
            "Nudge all selected video clips by a whole-frame delta, including linked audio.",
            "selection",
            params_schema=schema_object(
                {
                    "frames": {"type": "integer"},
                    "fps": {"type": "number"},
                    "strict_links": {"type": "boolean"},
                },
                required=("frames",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Nudge selected clips by frames",
        ),
        lambda params, dry: _selection_nudge_frames(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.nudge",
            "Alias for nudging the current timeline selection by a delta, including linked audio.",
            "timeline",
            params_schema=schema_object(
                {
                    "delta_ms": {"type": "integer"},
                    "strict_links": {"type": "boolean"},
                },
                required=("delta_ms",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Nudge timeline selection",
        ),
        lambda params, dry: _timeline_nudge(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.nudge_frames",
            "Alias for nudging the current timeline selection by a whole-frame delta.",
            "timeline",
            params_schema=schema_object(
                {
                    "frames": {"type": "integer"},
                    "fps": {"type": "number"},
                    "strict_links": {"type": "boolean"},
                },
                required=("frames",),
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Nudge timeline selection by frames",
        ),
        lambda params, dry: _timeline_nudge_frames(registry, params, dry),
    )
    align_schema = schema_object(
        {
            "edge": {"type": "string", "enum": ["start", "end", "in", "out", "left", "right"]},
            "strict_links": {"type": "boolean"},
        },
        additional_properties=True,
    )
    registry.register(
        ActionSpec(
            "selection.align_to_playhead",
            "Align selected clips to the current playhead, including linked audio.",
            "selection",
            params_schema=align_schema,
            mutating=True,
            requires_owner=True,
            undo_label="Align selection to playhead",
        ),
        lambda params, dry: _selection_align_to_playhead(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "selection.align_to_marker",
            "Align selected clips to a timeline marker, including linked audio.",
            "selection",
            params_schema=schema_object(
                {
                    "direction": {"type": "string", "enum": ["next", "previous", "prev", "nearest", "closest"]},
                    "from_ms": {"type": "integer", "minimum": 0},
                    "id": {"type": "string"},
                    "marker_id": {"type": "string"},
                    "index": {"type": "integer", "minimum": 0},
                    "label": {"type": "string"},
                    "ms": {"type": "integer", "minimum": 0},
                    "tolerance_ms": {"type": "integer", "minimum": 0},
                    "edge": {"type": "string", "enum": ["start", "end", "in", "out", "left", "right"]},
                    "strict_links": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Align selection to marker",
        ),
        lambda params, dry: _selection_align_to_marker(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "selection.snap_to_nearest",
            "Align selected clips to the nearest enabled snap target, including linked audio.",
            "selection",
            params_schema=schema_object(
                {
                    "edge": {"type": "string", "enum": ["start", "end", "in", "out", "left", "right"]},
                    "from_ms": {"type": "integer", "minimum": 0},
                    "strict_links": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            undo_label="Snap selection",
        ),
        lambda params, dry: _selection_snap_to_nearest(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "selection.ripple_delete",
            "Ripple-delete selected video clips and their linked audio.",
            "selection",
            params_schema=schema_object(
                {"include_linked_audio": {"type": "boolean"}},
                additional_properties=True,
            ),
            mutating=True,
            destructive=True,
            requires_owner=True,
            requires_review=True,
            undo_label="Ripple delete selection",
        ),
        lambda params, dry: _selection_ripple_delete(registry, params, dry),
    )


def _selection_move_common(registry: Any, action_id: str, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "delta_ms" not in params:
        return error_result(action_id, "delta_ms is required", dry_run=dry_run)
    try:
        result = registry.adapter.move_selection(
            delta_ms=_as_int(params.get("delta_ms")),
            strict_links=bool(params.get("strict_links", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result(action_id, str(exc), dry_run=dry_run)
    return ok_result(
        action_id,
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("video_move_count") or result.get("linked_audio_count")),
    )


def _selection_move(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _selection_move_common(registry, "selection.move", params, dry_run)


def _selection_nudge(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _selection_move_common(registry, "selection.nudge", params, dry_run)


def _timeline_nudge(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _selection_move_common(registry, "timeline.nudge", params, dry_run)


def _selection_nudge_frames_common(registry: Any, action_id: str, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    frames = _as_int(params.get("frames"), 0)
    fps = max(1.0, _as_float(params.get("fps"), 30.0))
    next_params = dict(params)
    next_params["delta_ms"] = int(round(frames * 1000.0 / fps))
    result = _selection_move_common(registry, action_id, next_params, dry_run)
    if result.ok and isinstance(result.result, Mapping):
        enriched = dict(result.result)
        enriched["frames"] = frames
        enriched["fps"] = fps
        enriched["frame_delta_ms"] = next_params["delta_ms"]
        return ok_result(action_id, enriched, dry_run=result.dry_run, changed=result.changed)
    return result


def _selection_nudge_frames(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _selection_nudge_frames_common(registry, "selection.nudge_frames", params, dry_run)


def _timeline_nudge_frames(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    return _selection_nudge_frames_common(registry, "timeline.nudge_frames", params, dry_run)


def _selection_align_to_playhead(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.align_selection_to_playhead(
            edge=str(params.get("edge") or "start"),
            strict_links=bool(params.get("strict_links", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("selection.align_to_playhead", str(exc), dry_run=dry_run)
    move = dict(result.get("move") or {})
    return ok_result(
        "selection.align_to_playhead",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(move.get("video_move_count") or move.get("linked_audio_count")),
    )


def _selection_align_to_marker(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.align_selection_to_marker(
            direction=str(params.get("direction") or "nearest"),
            from_ms=_as_int(params.get("from_ms"), -1) if "from_ms" in params else None,
            id=str(params.get("id") or ""),
            marker_id=str(params.get("marker_id") or ""),
            ms=_as_int(params.get("ms"), -1) if "ms" in params else None,
            index=_as_int(params.get("index"), -1) if "index" in params else None,
            label=str(params.get("label") or ""),
            tolerance_ms=_as_int(params.get("tolerance_ms"), 250),
            edge=str(params.get("edge") or "start"),
            strict_links=bool(params.get("strict_links", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("selection.align_to_marker", str(exc), dry_run=dry_run)
    move = dict(result.get("move") or {})
    return ok_result(
        "selection.align_to_marker",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(move.get("video_move_count") or move.get("linked_audio_count")),
    )


def _selection_snap_to_nearest(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.snap_selection_to_nearest(
            edge=str(params.get("edge") or "start"),
            from_ms=_as_int(params.get("from_ms"), -1) if "from_ms" in params else None,
            strict_links=bool(params.get("strict_links", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("selection.snap_to_nearest", str(exc), dry_run=dry_run)
    move = dict(result.get("move") or {})
    return ok_result(
        "selection.snap_to_nearest",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(move.get("video_move_count") or move.get("linked_audio_count")),
    )


def _selection_ripple_delete(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    try:
        result = registry.adapter.ripple_delete_selection(
            include_linked_audio=bool(params.get("include_linked_audio", True)),
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        return error_result("selection.ripple_delete", str(exc), dry_run=dry_run)
    return ok_result(
        "selection.ripple_delete",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("deleted_video_count") or result.get("deleted_linked_audio_count")),
    )
