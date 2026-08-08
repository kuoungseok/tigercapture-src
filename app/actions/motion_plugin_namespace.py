"""Registered actions for declarative Motion plugins and template packs."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


PLUGIN_CONTEXT_PROPERTIES = {
    "plugin_roots": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Optional plugin roots. Defaults to built-in and per-user roots.",
    },
}


def register_motion_plugin_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "motion.plugin.list",
        "List discovered declarative Motion Designer plugins.",
        "motion",
        "motion_plugin_list",
        params_schema=schema_object(PLUGIN_CONTEXT_PROPERTIES),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.plugin.inspect",
        "Inspect one declarative Motion Designer plugin.",
        "motion",
        "motion_plugin_inspect",
        params_schema=schema_object({
            "plugin_id": {"type": "string"},
            **PLUGIN_CONTEXT_PROPERTIES,
        }, required=("plugin_id",)),
        required=("plugin_id",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.plugin.validate",
        "Validate a Motion Designer plugin manifest without loading code.",
        "motion",
        "motion_plugin_validate",
        params_schema=schema_object({"path": {"type": "string"}}, required=("path",)),
        required=("path",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    for action_id, title, method in (
        ("motion.plugin.enable", "Enable a validated Motion Designer plugin.", "motion_plugin_enable"),
        ("motion.plugin.disable", "Disable a Motion Designer plugin.", "motion_plugin_disable"),
    ):
        registry.register_adapter_action(
            action_id,
            title,
            "motion",
            method,
            params_schema=schema_object({
                "plugin_id": {"type": "string"},
                **PLUGIN_CONTEXT_PROPERTIES,
            }, required=("plugin_id",)),
            required=("plugin_id",),
            mutating=True,
            changed=True,
            requires_owner=False,
            dry_summary=f"{title.rstrip('.')} state would be persisted; runtime loading would wait for restart",
        )
    registry.register_adapter_action(
        "motion.template_pack.validate",
        "Validate a declarative Motion Designer template pack.",
        "motion",
        "motion_template_pack_validate",
        params_schema=schema_object({"path": {"type": "string"}}, required=("path",)),
        required=("path",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )
    registry.register_adapter_action(
        "motion.template_pack.install",
        "Safely install a validated Motion Designer template pack.",
        "motion",
        "motion_template_pack_install",
        params_schema=schema_object({
            "path": {"type": "string"},
            "replace": {"type": "boolean"},
        }, required=("path",)),
        required=("path",),
        mutating=True,
        destructive=True,
        requires_review=True,
        changed=True,
        requires_owner=False,
        dry_summary="Validated template pack would be installed in durable Motion Designer storage",
    )


__all__ = ["register_motion_plugin_actions"]
