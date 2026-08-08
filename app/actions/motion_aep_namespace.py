"""Registered actions for safe, dependency-free AEP inspection."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_motion_aep_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "motion.aep.inspect",
        "Inspect an After Effects AEP without executing expressions or plug-ins.",
        "motion",
        "motion_aep_inspect",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "include_tree": {"type": "boolean", "default": False},
            },
            required=("path",),
        ),
        required=("path",),
        mutating=False,
        changed=False,
        requires_owner=False,
    )


__all__ = ["register_motion_aep_actions"]
