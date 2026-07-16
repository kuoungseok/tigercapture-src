"""Unreal Engine Link Python action namespace registrations."""
from __future__ import annotations

from typing import Any

from app.actions.result import ok_result
from app.actions.schema import ActionSpec, schema_object
from app.unreal_link_reference_paths import unreal_link_reference_report


def register_unreal_link_actions(registry: Any) -> None:
    """Register read-only actions for local Unreal Engine Link development context."""
    registry.register(
        ActionSpec(
            "unreal.link.reference_status",
            "Return local read-only reference roots for Unreal Engine Link development.",
            "unreal",
            result_schema=schema_object(
                {
                    "note": {"type": "string"},
                    "env_overrides": {"type": "object"},
                    "roots": {"type": "object"},
                }
            ),
            mutating=False,
            requires_owner=False,
            supports_dry_run=False,
        ),
        lambda _params, _dry: ok_result(
            "unreal.link.reference_status",
            unreal_link_reference_report(),
        ),
    )


__all__ = ["register_unreal_link_actions"]
