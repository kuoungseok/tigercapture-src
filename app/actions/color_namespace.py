"""Project color-management action registration."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object


def register_color_management_actions(registry: Any) -> None:
    registry.register(
        ActionSpec(
            "color.management.get",
            "Return project HDR, ACES, OCIO, LUT, and display-transform settings.",
            "color",
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "color.management.get",
            registry.adapter.project_color_management_get(),
        ),
    )
    registry.register_adapter_action(
        "color.management.set",
        "Set project HDR, ACES, OCIO, LUT, and display-transform settings.",
        "color",
        "project_color_management_set",
        params_schema=schema_object(
            {
                "settings": {"type": "object", "additionalProperties": True},
                "merge": {"type": "boolean"},
            },
            required=("settings",),
        ),
        required=("settings",),
        undo_label="Set project color management",
        dry_summary="project color management would change",
    )


__all__ = ["register_color_management_actions"]
