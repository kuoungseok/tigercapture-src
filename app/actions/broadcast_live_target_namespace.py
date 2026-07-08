"""Broadcast Live Target action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def _live_target_schema() -> dict[str, dict[str, Any]]:
    return {
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
    }


def register_broadcast_live_target_actions(registry: Any) -> None:
    summary_schema = {
        **_live_target_schema(),
        "width": {"type": "integer", "minimum": 1},
        "height": {"type": "integer", "minimum": 1},
        "fps": {"type": "number", "minimum": 1},
    }
    registry.register_adapter_action(
        "broadcast.live_target.summary",
        "Return Live Target presets and output preflight for Program Output.",
        "broadcast",
        "broadcast_live_target_summary",
        params_schema=schema_object(summary_schema),
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
        params_schema=schema_object(_live_target_schema(), required=("target_id",)),
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
