"""AR/PBR viewport gizmo action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_ar_pbr_gizmo_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "ar_pbr.gizmo.state",
        "Return AR/PBR viewport transform gizmo selection state.",
        "ar_pbr",
        "ar_pbr_gizmo_state",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR viewport gizmo state would be returned",
    )
    registry.register_adapter_action(
        "ar_pbr.gizmo.show",
        "Show the AR/PBR viewport transform gizmo for a placed 3D object.",
        "ar_pbr",
        "ar_pbr_gizmo_show",
        params_schema=schema_object({"track_id": {"type": "string"}}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR viewport gizmo would be shown for the target track",
    )
    registry.register_adapter_action(
        "ar_pbr.gizmo.hide",
        "Hide the AR/PBR viewport transform gizmo.",
        "ar_pbr",
        "ar_pbr_gizmo_hide",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="AR/PBR viewport gizmo would be hidden",
    )
