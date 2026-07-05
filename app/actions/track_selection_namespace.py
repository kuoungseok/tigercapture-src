"""Track focus and selection action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_track_selection_actions(registry: Any) -> None:
    """Register adapter-backed track, clip selection, and range selection actions."""
    registry.register_adapter_action(
        "track.reorder",
        "Move a video or audio track to another index.",
        "track",
        "reorder_track",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "index": {"type": "integer", "minimum": 0},
            },
            required=("track_id", "index"),
        ),
        required=("track_id", "index"),
        undo_label="Reorder track",
        dry_summary="track would be reordered",
    )
    registry.register_adapter_action(
        "track.set_state",
        "Set video/audio track state such as lock, mute, volume, pan, or PIP.",
        "track",
        "set_track_state",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "locked": {"type": "boolean"},
                "muted": {"type": "boolean"},
                "volume": {"type": "number"},
                "pan": {"type": "number"},
                "label": {"type": "string"},
                "bus_id": {"type": "string"},
                "pip_enabled": {"type": "boolean"},
                "pip_x": {"type": "number"},
                "pip_y": {"type": "number"},
                "pip_scale": {"type": "number"},
                "pip_opacity": {"type": "number"},
            },
            required=("track_id",),
            additional_properties=True,
        ),
        required=("track_id",),
        undo_label="Set track state",
        dry_summary="track state would change",
    )
    registry.register_adapter_action(
        "track.lock",
        "Lock or unlock a video or audio track.",
        "track",
        "set_track_lock",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "locked": {"type": "boolean"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Lock track",
        dry_summary="track lock state would change",
    )
    registry.register_adapter_action(
        "track.mute",
        "Mute or unmute a video or audio track.",
        "track",
        "set_track_mute",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "muted": {"type": "boolean"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Mute track",
        dry_summary="track mute state would change",
    )
    registry.register_adapter_action(
        "track.rename",
        "Rename a video or audio track strip.",
        "track",
        "rename_track",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "name": {"type": "string"},
            },
            required=("track_id", "name"),
        ),
        required=("track_id", "name"),
        undo_label="Rename track",
        dry_summary="track would be renamed",
    )
    registry.register_adapter_action(
        "track.select",
        "Set the active video or audio track, optionally selecting its first clip.",
        "track",
        "select_track",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "select_first_clip": {"type": "boolean"},
                "mode": {"type": "string", "enum": ["replace", "add", "toggle", "remove"]},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        mutating=True,
        undo_label="Select track",
        dry_summary="track focus would change",
    )
    registry.register_adapter_action(
        "clip.select",
        "Select one video or audio clip.",
        "clip",
        "select_clip",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "mode": {"type": "string", "enum": ["replace", "add", "toggle", "remove"]},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        mutating=True,
        undo_label="Select clip",
        dry_summary="clip selection would change",
    )
    registry.register_adapter_action(
        "timeline.select_all",
        "Select all clips on video, audio, or all tracks.",
        "timeline",
        "select_all",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio", "all"]},
                "track_id": {"type": "integer"},
            }
        ),
        mutating=True,
        undo_label="Select all clips",
        dry_summary="timeline clips would be selected",
    )
    registry.register_adapter_action(
        "selection.set",
        "Set the current editor selection.",
        "selection",
        "set_selection",
        params_schema=schema_object(
            {
                "kind": {"type": "string", "enum": ["video", "audio"]},
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "mode": {"type": "string", "enum": ["replace", "add", "toggle", "remove", "clear"]},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        mutating=True,
        undo_label="Set selection",
        dry_summary="selection would change",
    )
    registry.register_adapter_action(
        "selection.clear",
        "Clear the current editor selection.",
        "selection",
        "clear_selection",
        mutating=True,
        undo_label="Clear selection",
        dry_summary="selection would be cleared",
    )
    registry.register_adapter_action(
        "selection.select_range",
        "Select video clips that overlap a project time range.",
        "selection",
        "select_range",
        params_schema=schema_object(
            {
                "start_ms": {"type": "integer", "minimum": 0},
                "end_ms": {"type": "integer", "minimum": 1},
                "track_id": {"type": "integer"},
                "mode": {"type": "string", "enum": ["replace", "add", "toggle", "remove"]},
                "include_partial": {"type": "boolean"},
            },
            required=("start_ms", "end_ms"),
        ),
        required=("start_ms", "end_ms"),
        mutating=True,
        undo_label="Select clip range",
        dry_summary="timeline clip range would be selected",
    )
