"""Broadcast and live-output Python action namespace registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_broadcast_actions(registry: Any) -> None:
    """Register broadcast/live target actions without growing the core registry."""
    registry.register_adapter_action(
        "broadcast.live_target.summary",
        "Return Live Target presets and output preflight for Program Output.",
        "broadcast",
        "broadcast_live_target_summary",
        params_schema=schema_object(
            {
                "target_id": {"type": "string"},
                "server_url": {"type": "string"},
                "stream_key": {"type": "string"},
                "output_path": {"type": "string"},
                "video_bitrate_kbps": {"type": "integer", "minimum": 500},
                "include_audio": {"type": "boolean"},
                "audio_source_kind": {
                    "type": "string",
                    "enum": ["none", "silence", "project_audio_bus", "dshow_device", "file", ""],
                },
                "audio_device_name": {"type": "string"},
                "audio_file": {"type": "string"},
                "auto_reconnect": {"type": "boolean"},
                "max_retries": {"type": "integer", "minimum": 0, "maximum": 20},
                "width": {"type": "integer", "minimum": 1},
                "height": {"type": "integer", "minimum": 1},
                "fps": {"type": "number", "minimum": 1},
            }
        ),
        mutating=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="live target presets and preflight would be returned",
    )
    registry.register_adapter_action(
        "broadcast.live_target.select",
        "Select the active Live Target for Program Output.",
        "broadcast",
        "select_broadcast_live_target",
        params_schema=schema_object(
            {
                "target_id": {"type": "string"},
                "server_url": {"type": "string"},
                "stream_key": {"type": "string"},
                "output_path": {"type": "string"},
                "video_bitrate_kbps": {"type": "integer", "minimum": 500},
                "include_audio": {"type": "boolean"},
                "audio_source_kind": {
                    "type": "string",
                    "enum": ["none", "silence", "project_audio_bus", "dshow_device", "file", ""],
                },
                "audio_device_name": {"type": "string"},
                "audio_file": {"type": "string"},
                "auto_reconnect": {"type": "boolean"},
                "max_retries": {"type": "integer", "minimum": 0, "maximum": 20},
            },
            required=("target_id",),
        ),
        required=("target_id",),
        undo_label="Select broadcast live target",
        async_kind="broadcast",
        dry_summary="live target selection would be saved",
    )
    registry.register_adapter_action(
        "broadcast.live_target.troubleshoot",
        "Return platform-specific troubleshooting guidance for a Live Target error.",
        "broadcast",
        "broadcast_live_target_troubleshooting",
        params_schema=schema_object(
            {
                "target_id": {"type": "string"},
                "platform_error_kind": {"type": "string"},
                "platform_error_message": {"type": "string"},
                "last_error": {"type": "string"},
                "stderr_tail": {"type": "string"},
                "state": {"type": "string"},
            }
        ),
        mutating=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="live target troubleshooting guidance would be returned",
    )
    registry.register_adapter_action(
        "broadcast.release_readiness",
        "Return VTuber/broadcast alpha and commercial readiness diagnostics.",
        "broadcast",
        "broadcast_release_readiness",
        params_schema=schema_object({"root": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast commercial-readiness diagnostics would be returned",
    )
    registry.register_adapter_action(
        "broadcast.platform_evidence_checklist",
        "Return operator checklist for remaining broadcast platform evidence.",
        "broadcast",
        "broadcast_platform_evidence_checklist",
        params_schema=schema_object({"root": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        async_kind="broadcast",
        dry_summary="broadcast platform evidence checklist would be returned",
    )
    registry.register_adapter_action(
        "broadcast.platform_evidence.register",
        "Register redacted manual broadcast platform evidence after a real check.",
        "broadcast",
        "register_broadcast_platform_evidence",
        params_schema=schema_object(
            {
                "check_id": {"type": "string", "enum": ["private_rtmp_ingest", "discord_window_share"]},
                "platform": {"type": "string"},
                "evidence_path": {"type": "string"},
                "notes": {"type": "string"},
                "confirm_redacted": {"type": "boolean"},
                "root": {"type": "string"},
                "artifact_path": {"type": "string"},
            },
            required=("check_id", "platform", "confirm_redacted"),
        ),
        required=("check_id", "platform", "confirm_redacted"),
        mutating=True,
        requires_owner=False,
        requires_review=True,
        async_kind="broadcast",
        dry_summary="redacted broadcast platform evidence would be registered",
    )
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
