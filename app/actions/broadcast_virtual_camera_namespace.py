"""Broadcast virtual-camera and OBS bridge action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def _obs_bridge_schema(*, password: bool) -> dict[str, dict[str, Any]]:
    schema: dict[str, dict[str, Any]] = {
        "discover": {"type": "boolean"},
        "installed_backends": {"type": "object"},
        "obs_executable": {"type": "string"},
        "obs_path": {"type": "string"},
        "program_window_title": {"type": "string"},
        "scene_name": {"type": "string"},
        "source_name": {"type": "string"},
        "websocket_enabled": {"type": "boolean"},
        "use_websocket": {"type": "boolean"},
        "websocket_host": {"type": "string"},
        "websocket_port": {"type": "integer", "minimum": 0, "maximum": 65535},
        "websocket_password_present": {"type": "boolean"},
    }
    if password:
        schema["websocket_password"] = {"type": "string"}
    return schema


def register_broadcast_virtual_camera_actions(registry: Any) -> None:
    registry.register_adapter_action(
        "broadcast.virtual_camera.plan",
        "Return the Discord/video-call virtual-camera output plan for Program Output.",
        "broadcast",
        "broadcast_virtual_camera_plan",
        params_schema=schema_object(
            {
                "backend": {"type": "string"},
                "preferred_backend": {"type": "string"},
                "discover": {"type": "boolean"},
                "installed_backends": {"type": "object"},
                "obs_executable": {"type": "string"},
                "obs_path": {"type": "string"},
                "program_window_title": {"type": "string"},
                "scene_name": {"type": "string"},
                "source_name": {"type": "string"},
                "websocket_enabled": {"type": "boolean"},
                "use_websocket": {"type": "boolean"},
                "websocket_host": {"type": "string"},
                "websocket_port": {"type": "integer", "minimum": 0, "maximum": 65535},
                "websocket_password_present": {"type": "boolean"},
            },
            additional_properties=True,
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="virtual-camera output plan would be returned",
    )
    registry.register_adapter_action(
        "broadcast.virtual_camera.obs_bridge_plan",
        "Return the OBS Window Capture plus Virtual Camera bridge plan.",
        "broadcast",
        "broadcast_obs_virtual_camera_bridge_plan",
        params_schema=schema_object(_obs_bridge_schema(password=False), additional_properties=True),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="OBS virtual-camera bridge plan would be returned",
    )
    registry.register_adapter_action(
        "broadcast.virtual_camera.obs_bridge_gate",
        "Return the confirmed OBS Virtual Camera bridge execution gate.",
        "broadcast",
        "broadcast_obs_virtual_camera_bridge_execution_gate",
        params_schema=schema_object(
            {"confirm": {"type": "boolean"}, **_obs_bridge_schema(password=False), "obsws_available": {"type": "boolean"}},
            additional_properties=True,
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="OBS virtual-camera bridge execution gate would be returned",
    )
    registry.register_adapter_action(
        "broadcast.virtual_camera.obs_bridge_dry_run",
        "Return OBS WebSocket scene/source/virtual-camera operations without executing.",
        "broadcast",
        "broadcast_obs_virtual_camera_bridge_dry_run",
        params_schema=schema_object(
            {"confirm": {"type": "boolean"}, **_obs_bridge_schema(password=False), "obsws_available": {"type": "boolean"}},
            additional_properties=True,
        ),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="OBS virtual-camera bridge operations would be returned",
    )
    registry.register_adapter_action(
        "broadcast.virtual_camera.obs_bridge_execute",
        "Execute confirmed OBS WebSocket scene/source/virtual-camera setup.",
        "broadcast",
        "broadcast_obs_virtual_camera_bridge_execute",
        params_schema=schema_object(
            {"confirm": {"type": "boolean"}, **_obs_bridge_schema(password=True), "obsws_available": {"type": "boolean"}},
            additional_properties=True,
        ),
        mutating=True,
        requires_owner=False,
        requires_review=True,
        changed=False,
        async_kind="broadcast",
        dry_summary="confirmed OBS virtual-camera bridge setup would execute",
    )
