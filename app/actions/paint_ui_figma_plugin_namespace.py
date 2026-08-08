"""Actions for FP1 metadata-only Figma plugin package management."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


PLUGIN_CONTEXT = {
    "plugin_roots": {"type": "array", "items": {"type": "string"}},
    "install_root": {"type": "string"},
}


def register_paint_ui_figma_plugin_actions(registry: Any) -> None:
    for action_id, description, method, properties, required in (
        (
            "paint.ui.figma_plugin.validate",
            "Validate a Figma plugin manifest without executing JavaScript.",
            "paint_ui_figma_plugin_validate",
            {"path": {"type": "string"}},
            ("path",),
        ),
        (
            "paint.ui.figma_plugin.list",
            "List locally discovered Figma plugin packages and compatibility blockers.",
            "paint_ui_figma_plugin_list",
            dict(PLUGIN_CONTEXT),
            (),
        ),
        (
            "paint.ui.figma_plugin.inspect",
            "Inspect one local Figma plugin package without executing it.",
            "paint_ui_figma_plugin_inspect",
            {"plugin_id": {"type": "string"}, **PLUGIN_CONTEXT},
            ("plugin_id",),
        ),
    ):
        registry.register_adapter_action(
            action_id,
            description,
            "paint",
            method,
            params_schema=schema_object(properties, required=required),
            required=required,
            mutating=False,
            changed=False,
            requires_owner=False,
        )

    registry.register_adapter_action(
        "paint.ui.figma_plugin.install",
        "Install a validated Figma plugin package without executing JavaScript.",
        "paint",
        "paint_ui_figma_plugin_install",
        params_schema=schema_object(
            {"path": {"type": "string"}, **PLUGIN_CONTEXT}, required=("path",)
        ),
        required=("path",),
        mutating=True,
        changed=True,
        destructive=True,
        requires_owner=False,
        requires_review=True,
        dry_summary="Validated Figma plugin metadata and files would be copied to local storage; code would not run",
    )
    registry.register_adapter_action(
        "paint.ui.figma_plugin.remove",
        "Remove a Figma plugin package from Painter local storage.",
        "paint",
        "paint_ui_figma_plugin_remove",
        params_schema=schema_object(
            {"plugin_id": {"type": "string"}, **PLUGIN_CONTEXT},
            required=("plugin_id",),
        ),
        required=("plugin_id",),
        mutating=True,
        changed=True,
        destructive=True,
        requires_review=True,
        requires_owner=False,
        dry_summary="The selected locally installed Figma plugin package would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.figma_plugin.run",
        "Run an installed plugin through the limited FP2 Figma API sandbox.",
        "paint",
        "paint_ui_figma_plugin_run",
        params_schema=schema_object(
            {
                "plugin_id": {"type": "string"},
                "timeout_ms": {"type": "integer", "minimum": 50, "maximum": 2000},
                **PLUGIN_CONTEXT,
            },
            required=("plugin_id",),
        ),
        required=("plugin_id",),
        mutating=True,
        changed=True,
        undo_label="Run Figma plugin",
        dry_summary="The selected plugin would run in the restricted FP2 process and apply one atomic Painter document edit",
    )


__all__ = ["register_paint_ui_figma_plugin_actions"]
