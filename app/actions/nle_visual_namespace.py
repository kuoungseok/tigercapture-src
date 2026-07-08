"""Final Cut-style NLE visual feedback action registration."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def _optional_int(params: dict[str, Any], key: str) -> int | None:
    if key not in params or params.get(key) in (None, ""):
        return None
    return _as_int(params.get(key))


def register_visual_feedback_actions(registry: Any) -> None:
    """Register UI-ready magnetic, connected-clip, and role-lane feedback actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.connected_clips.anchor_overlay",
            "Return connected-clip anchor line descriptors for timeline drawing.",
            "timeline",
            params_schema=schema_object(
                {
                    "selected_track_id": {"type": "integer"},
                    "selected_clip_id": {"type": "integer"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.connected_clips.anchor_overlay",
            adapter.connected_anchor_overlay(
                selected_track_id=_optional_int(params, "selected_track_id"),
                selected_clip_id=_optional_int(params, "selected_clip_id"),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.role_lanes.filter_model",
            "Return a role-lane filter model with visible/dimmed clip sets.",
            "timeline",
            params_schema=schema_object(
                {
                    "focused_role": {"type": "string"},
                    "include_empty_roles": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.role_lanes.filter_model",
            adapter.role_lane_filter_model(
                focused_role=str(params.get("focused_role")) if "focused_role" in params else None,
                include_empty_roles=bool(params.get("include_empty_roles", True)),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.magnetic_storyline.drag_preview",
            "Simulate Final Cut-style magnetic drag feedback without mutating the timeline.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "target_start_ms": {"type": "integer"},
                    "snap_threshold_ms": {"type": "integer", "minimum": 0},
                },
                required=("track_id", "clip_id", "target_start_ms"),
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.magnetic_storyline.drag_preview",
            adapter.magnetic_drag_preview(
                track_id=_as_int(params.get("track_id"), -1),
                clip_id=_as_int(params.get("clip_id"), -1),
                target_start_ms=_as_int(params.get("target_start_ms"), 0),
                snap_threshold_ms=_as_int(params.get("snap_threshold_ms", 120), 120),
            ),
        ),
    )


__all__ = ["register_visual_feedback_actions"]
