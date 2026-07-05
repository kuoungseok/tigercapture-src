"""Timeline marker action registrations."""
from __future__ import annotations

from typing import Any, Mapping

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


def register_marker_actions(registry: Any) -> None:
    """Register timeline marker create/list/remove/move/jump actions."""
    marker_spec = ActionSpec(
        "timeline.marker.add",
        "Add a timeline marker.",
        "timeline",
        params_schema=schema_object(
            {
                "ms": {"type": "integer", "minimum": 0},
                "label": {"type": "string"},
                "color": {"type": "string"},
                "id": {"type": "string"},
            },
            required=("ms",),
        ),
        mutating=True,
        requires_owner=True,
        undo_label="Add marker",
    )
    registry.register(marker_spec, lambda params, dry: _marker_add(registry, params, dry))
    registry.register(
        ActionSpec(
            "marker.add",
            "Alias for timeline.marker.add.",
            "timeline",
            params_schema=marker_spec.params_schema,
            mutating=True,
            requires_owner=True,
            undo_label="Add marker",
        ),
        lambda params, dry: _marker_add_alias(registry, params, dry),
    )
    registry.register_adapter_action(
        "timeline.marker.list",
        "List timeline markers.",
        "timeline",
        "list_markers",
        mutating=False,
        changed=False,
        dry_summary="timeline markers would be listed",
    )
    registry.register_adapter_action(
        "timeline.marker.remove",
        "Remove a timeline marker by id, index, label, or time.",
        "timeline",
        "remove_marker",
        params_schema=schema_object(
            {
                "id": {"type": "string"},
                "marker_id": {"type": "string"},
                "index": {"type": "integer", "minimum": 0},
                "label": {"type": "string"},
                "ms": {"type": "integer", "minimum": 0},
                "tolerance_ms": {"type": "integer", "minimum": 0},
            },
            additional_properties=True,
        ),
        undo_label="Remove marker",
        dry_summary="timeline marker would be removed",
    )
    registry.register_adapter_action(
        "timeline.marker.move",
        "Move a timeline marker by id, index, label, or time.",
        "timeline",
        "move_marker",
        params_schema=schema_object(
            {
                "new_ms": {"type": "integer", "minimum": 0},
                "id": {"type": "string"},
                "marker_id": {"type": "string"},
                "index": {"type": "integer", "minimum": 0},
                "label": {"type": "string"},
                "ms": {"type": "integer", "minimum": 0},
                "tolerance_ms": {"type": "integer", "minimum": 0},
            },
            required=("new_ms",),
            additional_properties=True,
        ),
        required=("new_ms",),
        undo_label="Move marker",
        dry_summary="timeline marker would move",
    )
    registry.register_adapter_action(
        "timeline.marker.jump",
        "Jump the playhead to a timeline marker.",
        "timeline",
        "jump_marker",
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
            },
            additional_properties=True,
        ),
        undo_label="Jump to marker",
        dry_summary="playhead would jump to a marker",
    )


def _marker_add(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    if "ms" not in params:
        return error_result("timeline.marker.add", "ms is required", dry_run=dry_run)
    if dry_run:
        return registry._dry_result("timeline.marker.add", params, "timeline marker would be added")
    return ok_result(
        "timeline.marker.add",
        registry.adapter.add_marker(
            ms=_as_int(params.get("ms"), 0),
            label=str(params.get("label") or ""),
            color=str(params.get("color") or "#8A7CFF"),
            marker_id=str(params.get("id") or ""),
        ),
        changed=True,
    )


def _marker_add_alias(registry: Any, params: Mapping[str, Any], dry_run: bool) -> ActionResult:
    result = _marker_add(registry, params, dry_run)
    if result.ok:
        return ok_result(
            "marker.add",
            result.result,
            warnings=result.warnings,
            dry_run=result.dry_run,
            changed=result.changed,
        )
    return error_result(
        "marker.add",
        result.error,
        result=result.result,
        warnings=result.warnings,
        dry_run=dry_run,
    )
