"""Final Cut-style audition action registration helpers."""
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
    if key not in params or params.get(key) is None:
        return None
    return _as_int(params.get(key), 0)


def register_audition_actions(registry: Any) -> None:
    """Register audition actions without growing the general NLE namespace."""

    adapter = registry.adapter
    registry.register(
        ActionSpec(
            "timeline.auditions.status",
            "Return Final Cut-style audition/take groups and active-take diagnostics.",
            "timeline",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result("timeline.auditions.status", adapter.auditions_status()),
    )
    registry.register(
        ActionSpec(
            "timeline.audition.compare",
            "Return a UI-ready Final Cut-style audition picker model for a host clip.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                },
                required=("track_id", "clip_id"),
                additional_properties=True,
            ),
            supports_dry_run=False,
        ),
        lambda params, _dry: ok_result(
            "timeline.audition.compare",
            adapter.audition_compare(
                track_id=_as_int(params.get("track_id"), -1),
                clip_id=_as_int(params.get("clip_id"), -1),
            ),
        ),
    )
    registry.register(
        ActionSpec(
            "timeline.audition.add_take",
            "Add or replace a candidate take inside a host clip audition without exposing hidden timeline lanes.",
            "timeline",
            params_schema=schema_object(
                {
                    "host_track_id": {"type": "integer"},
                    "host_clip_id": {"type": "integer"},
                    "take_track_id": {"type": "integer"},
                    "take_clip_id": {"type": "integer"},
                    "take_id": {"type": "string"},
                    "label": {"type": "string"},
                    "source_path": {"type": "string"},
                    "source_duration_ms": {"type": "integer"},
                    "source_in_ms": {"type": "integer"},
                    "source_out_ms": {"type": "integer"},
                    "switch_to_take": {"type": "boolean"},
                },
                required=("host_track_id", "host_clip_id"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Add audition take",
        ),
        lambda params, dry: _timeline_audition_add_take(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.audition.switch_take",
            "Switch a host clip to one of its stored audition takes.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "take_id": {"type": "string"},
                },
                required=("track_id", "clip_id", "take_id"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Switch audition take",
        ),
        lambda params, dry: _timeline_audition_switch_take(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.audition.rename_take",
            "Rename a stored audition take for picker/comparison clarity.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "take_id": {"type": "string"},
                    "label": {"type": "string"},
                },
                required=("track_id", "clip_id", "take_id", "label"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Rename audition take",
        ),
        lambda params, dry: _timeline_audition_rename_take(registry, params, dry),
    )
    registry.register(
        ActionSpec(
            "timeline.audition.remove_take",
            "Remove a stored audition take while keeping at least one safe active take.",
            "timeline",
            params_schema=schema_object(
                {
                    "track_id": {"type": "integer"},
                    "clip_id": {"type": "integer"},
                    "take_id": {"type": "string"},
                    "switch_to_take_id": {"type": "string"},
                },
                required=("track_id", "clip_id", "take_id"),
                additional_properties=True,
            ),
            mutating=True,
            requires_owner=True,
            supports_dry_run=True,
            undo_label="Remove audition take",
        ),
        lambda params, dry: _timeline_audition_remove_take(registry, params, dry),
    )


def _timeline_audition_add_take(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.add_audition_take(
        host_track_id=_as_int(params.get("host_track_id"), -1),
        host_clip_id=_as_int(params.get("host_clip_id"), -1),
        take_track_id=_optional_int(params, "take_track_id"),
        take_clip_id=_optional_int(params, "take_clip_id"),
        take_id=str(params.get("take_id") or ""),
        label=str(params.get("label") or ""),
        source_path=str(params.get("source_path") or ""),
        source_duration_ms=_as_int(params.get("source_duration_ms"), 0),
        source_in_ms=_as_int(params.get("source_in_ms"), 0),
        source_out_ms=_as_int(params.get("source_out_ms"), 0),
        switch_to_take=bool(params.get("switch_to_take", False)),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.audition.add_take",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_audition_switch_take(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.switch_audition_take(
        track_id=_as_int(params.get("track_id"), -1),
        clip_id=_as_int(params.get("clip_id"), -1),
        take_id=str(params.get("take_id") or ""),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.audition.switch_take",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_audition_rename_take(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.rename_audition_take(
        track_id=_as_int(params.get("track_id"), -1),
        clip_id=_as_int(params.get("clip_id"), -1),
        take_id=str(params.get("take_id") or ""),
        label=str(params.get("label") or ""),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.audition.rename_take",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


def _timeline_audition_remove_take(registry: Any, params: dict[str, Any], dry_run: bool):
    result = registry.adapter.remove_audition_take(
        track_id=_as_int(params.get("track_id"), -1),
        clip_id=_as_int(params.get("clip_id"), -1),
        take_id=str(params.get("take_id") or ""),
        switch_to_take_id=str(params.get("switch_to_take_id") or ""),
        dry_run=bool(dry_run),
    )
    return ok_result(
        "timeline.audition.remove_take",
        result,
        dry_run=bool(dry_run),
        changed=False if dry_run else bool(result.get("changed")),
    )


__all__ = ["register_audition_actions"]
