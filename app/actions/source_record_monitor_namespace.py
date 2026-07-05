"""Source and Record monitor action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_source_record_monitor_actions(registry: Any) -> None:
    """Register Source monitor and Record monitor state/mutation actions."""
    registry.register_adapter_action(
        "source_monitor.state",
        "Return the current Source monitor media and In/Out state.",
        "source_monitor",
        "source_monitor_state",
        mutating=False,
        requires_owner=True,
        changed=False,
        dry_summary="source monitor state would be listed",
    )
    registry.register_adapter_action(
        "source_monitor.load_media",
        "Load a media item into the Source monitor.",
        "source_monitor",
        "load_source_monitor",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "media_id": {"type": "string"},
                "name": {"type": "string"},
                "kind": {"type": "string", "enum": ["video", "audio", "image", "actor", "unknown"]},
                "duration_ms": {"type": "integer", "minimum": 1},
                "source_in_ms": {"type": "integer", "minimum": 0},
                "source_out_ms": {"type": "integer", "minimum": 1},
            },
            additional_properties=True,
        ),
        mutating=True,
        requires_owner=True,
        undo_label="Load source monitor",
        dry_summary="media would be loaded into the Source monitor",
    )
    registry.register_adapter_action(
        "source_monitor.set_in",
        "Set the Source monitor In point.",
        "source_monitor",
        "set_source_monitor_in",
        params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
        required=("ms",),
        mutating=True,
        requires_owner=True,
        undo_label="Set source In",
        dry_summary="source monitor In would move",
    )
    registry.register_adapter_action(
        "source_monitor.set_out",
        "Set the Source monitor Out point.",
        "source_monitor",
        "set_source_monitor_out",
        params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
        required=("ms",),
        mutating=True,
        requires_owner=True,
        undo_label="Set source Out",
        dry_summary="source monitor Out would move",
    )
    registry.register_adapter_action(
        "source_monitor.clear",
        "Clear the Source monitor.",
        "source_monitor",
        "clear_source_monitor",
        mutating=True,
        requires_owner=True,
        undo_label="Clear source monitor",
        dry_summary="source monitor would clear",
    )
    registry.register_adapter_action(
        "record_monitor.state",
        "Return the current Record monitor In/Out state.",
        "record_monitor",
        "record_monitor_state",
        mutating=False,
        requires_owner=True,
        changed=False,
        dry_summary="record monitor state would be listed",
    )
    registry.register_adapter_action(
        "record_monitor.set_in",
        "Set the Record monitor In point.",
        "record_monitor",
        "set_record_monitor_in",
        params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
        required=("ms",),
        mutating=True,
        requires_owner=True,
        undo_label="Set record In",
        dry_summary="record monitor In would move",
    )
    registry.register_adapter_action(
        "record_monitor.set_out",
        "Set the Record monitor Out point.",
        "record_monitor",
        "set_record_monitor_out",
        params_schema=schema_object({"ms": {"type": "integer", "minimum": 0}}, required=("ms",)),
        required=("ms",),
        mutating=True,
        requires_owner=True,
        undo_label="Set record Out",
        dry_summary="record monitor Out would move",
    )
    registry.register_adapter_action(
        "record_monitor.clear",
        "Clear the Record monitor In/Out range.",
        "record_monitor",
        "clear_record_monitor",
        mutating=True,
        requires_owner=True,
        undo_label="Clear record monitor",
        dry_summary="record monitor would clear",
    )
