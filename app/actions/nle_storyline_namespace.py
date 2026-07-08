"""Final Cut-style storyline, connected clip, and role action registration."""
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


def register_storyline_actions(registry: Any) -> None:
    """Register magnetic storyline, connected clip, and role-lane actions."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.magnetic_storyline.status",
            "Return Final Cut-style magnetic storyline gap/overlap diagnostics.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "min_gap_ms": {"type": "integer", "minimum": 1},
                },
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.magnetic_storyline.status",
            adapter.magnetic_storyline_status(
                track_id=_as_int(params.get("track_id")) if "track_id" in params else None,
                min_gap_ms=_as_int(params.get("min_gap_ms", 1), 1),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.magnetic_storyline.apply",
            "Close storyline gaps while preserving clip order and moving linked audio with the video clip.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "min_gap_ms": {"type": "integer", "minimum": 1},
                    "include_linked_audio": {"type": "boolean"},
                    "pull_first_to_zero": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Apply magnetic storyline",
        ),
        lambda params, dry: _timeline_magnetic_storyline_apply(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.connected_clips.status",
            "Return Final Cut-style connected clip parent/child diagnostics and offset health.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.connected_clips.status", adapter.connected_clips_status()),
    )
    registry.register(
        ActionSpec(
            "timeline.connected_clips.connect",
            "Attach a child clip to a parent storyline clip while preserving a connected offset.",
            "timeline",
            params_schema=schema_object(
                {
                    "child_track_id": {"type": "integer"},
                    "child_clip_id": {"type": "integer"},
                    "parent_track_id": {"type": "integer"},
                    "parent_clip_id": {"type": "integer"},
                    "at_ms": {"type": "integer"},
                    "role": {"type": "string"},
                    "role_color": {"type": "string"},
                },
                required=("child_track_id", "child_clip_id"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Connect clip to storyline",
        ),
        lambda params, dry: _timeline_connected_clip_connect(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.role_colors.status",
            "Return timeline role-color palette and per-clip role counts.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.role_colors.status", adapter.role_colors_status()),
    )
    registry.register(
        ActionSpec(
            "timeline.role_lanes.status",
            "Return role-aware lane grouping for Final Cut-style timeline displays.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.role_lanes.status", adapter.role_lanes_status()),
    )
    registry.register(
        ActionSpec(
            "timeline.role_lanes.focus",
            "Set or clear the focused role lane used by timeline UI and AI review summaries.",
            "timeline",
            params_schema=schema_object(
                {
                    "role": {"type": "string"},
                    "clear": {"type": "boolean"},
                },
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Set role lane focus",
        ),
        lambda params, dry: _timeline_role_lanes_focus(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.clip_role.set",
            "Set a clip's NLE role and role color for role-aware timeline display.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "role": {"type": "string"},
                    "role_color": {"type": "string"},
                },
                required=("track_id", "clip_id", "role"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Set clip role",
        ),
        lambda params, dry: _timeline_clip_role_set(registry, params, dry),
    )


def _timeline_magnetic_storyline_apply(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.apply_magnetic_storyline(
        track_id=_as_int(params.get("track_id")) if "track_id" in params else None,
        min_gap_ms=_as_int(params.get("min_gap_ms", 1), 1),
        include_linked_audio=bool(params.get("include_linked_audio", True)),
        pull_first_to_zero=bool(params.get("pull_first_to_zero", False)),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.magnetic_storyline.apply",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_connected_clip_connect(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.connect_clip_to_storyline(
        child_track_id=_as_int(params.get("child_track_id"), -1),
        child_clip_id=_as_int(params.get("child_clip_id"), -1),
        parent_track_id=_optional_int(params, "parent_track_id"),
        parent_clip_id=_optional_int(params, "parent_clip_id"),
        at_ms=_optional_int(params, "at_ms"),
        role=str(params.get("role") or "b_roll"),
        role_color=str(params.get("role_color") or ""),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.connected_clips.connect",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_clip_role_set(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.set_clip_role(
        track_id=_as_int(params.get("track_id"), -1),
        clip_id=_as_int(params.get("clip_id"), -1),
        role=str(params.get("role") or "primary"),
        role_color=str(params.get("role_color") or ""),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.clip_role.set",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_role_lanes_focus(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.set_role_lane_focus(
        role=str(params.get("role") or ""),
        clear=bool(params.get("clear", False)),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.role_lanes.focus",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


__all__ = ["register_storyline_actions"]
