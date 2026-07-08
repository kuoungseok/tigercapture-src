"""Audio action registrations for the Python action registry."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_audio_actions(registry: Any) -> None:
    """Register audio extraction, clip edit, and track mix actions."""
    registry.register_adapter_action(
        "audio.extract_from_video",
        "Extract the audio stream from a video clip into a timeline audio track.",
        "audio",
        "extract_audio_from_video",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "audio_track_id": {"type": "integer"},
                "at_ms": {"type": "integer", "minimum": 0},
                "link": {"type": "boolean"},
                "name": {"type": "string"},
            }
        ),
        undo_label="Extract audio from video",
        async_kind="audio_extract",
        dry_summary="audio stream would be extracted from a video clip",
    )
    registry.register_adapter_action(
        "audio.clip.split",
        "Split an audio clip at project time.",
        "audio",
        "split_audio_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "at_ms": {"type": "integer", "minimum": 0},
            },
            required=("track_id", "clip_id", "at_ms"),
        ),
        required=("track_id", "clip_id", "at_ms"),
        undo_label="Split audio clip",
        dry_summary="audio clip would be split",
    )
    registry.register_adapter_action(
        "audio.clip.trim",
        "Trim an audio clip source range.",
        "audio",
        "trim_audio_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "trim_start_ms": {"type": "integer", "minimum": 0},
                "trim_end_ms": {"type": "integer", "minimum": 1},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Trim audio clip",
        dry_summary="audio clip would be trimmed",
    )
    registry.register_adapter_action(
        "audio.clip.delete",
        "Delete an audio clip.",
        "audio",
        "delete_audio_clip",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "clip_id": {"type": "integer"}},
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        destructive=True,
        requires_review=True,
        undo_label="Delete audio clip",
        dry_summary="audio clip would be deleted",
    )
    registry.register_adapter_action(
        "audio.clip.set_gain",
        "Set audio clip gain.",
        "audio",
        "set_audio_clip_gain",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "gain": {"type": "number", "minimum": 0},
            },
            required=("track_id", "clip_id", "gain"),
        ),
        required=("track_id", "clip_id", "gain"),
        undo_label="Set audio clip gain",
        dry_summary="audio clip gain would change",
    )
    registry.register_adapter_action(
        "audio.track.set_mix",
        "Set audio track volume and pan.",
        "audio",
        "set_audio_track_mix",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "volume": {"type": "number"},
                "pan": {"type": "number"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Set audio track mix",
        dry_summary="audio track mix would change",
    )
    registry.register_adapter_action(
        "audio.track.set_volume",
        "Set one audio track volume fader.",
        "audio",
        "set_audio_track_volume",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "volume": {"type": "number", "minimum": 0, "maximum": 1.5}},
            required=("track_id", "volume"),
        ),
        required=("track_id", "volume"),
        undo_label="Set audio track volume",
        dry_summary="audio track volume would change",
    )
    registry.register_adapter_action(
        "audio.track.set_pan",
        "Set one audio track pan value.",
        "audio",
        "set_audio_track_pan",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "pan": {"type": "number", "minimum": -1, "maximum": 1}},
            required=("track_id", "pan"),
        ),
        required=("track_id", "pan"),
        undo_label="Set audio track pan",
        dry_summary="audio track pan would change",
    )
    registry.register_adapter_action(
        "audio.track.mute",
        "Mute or unmute one audio track without changing its fader value.",
        "audio",
        "set_audio_track_mute",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "muted": {"type": "boolean"}},
            required=("track_id", "muted"),
        ),
        required=("track_id", "muted"),
        undo_label="Set audio track mute",
        dry_summary="audio track mute state would change",
    )
    registry.register_adapter_action(
        "audio.track.solo",
        "Solo or unsolo one audio track.",
        "audio",
        "set_audio_track_solo",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "solo": {"type": "boolean"}},
            required=("track_id", "solo"),
        ),
        required=("track_id", "solo"),
        undo_label="Set audio track solo",
        dry_summary="audio track solo state would change",
    )
    registry.register_adapter_action(
        "audio.track.set_type",
        "Set one audio track role/type badge such as dialogue, music, sfx, or ambience.",
        "audio",
        "set_audio_track_type",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "track_type": {"type": "string"}},
            required=("track_id", "track_type"),
        ),
        required=("track_id", "track_type"),
        undo_label="Set audio track type",
        dry_summary="audio track type badge would change",
    )
    registry.register_adapter_action(
        "audio.track.insert.set",
        "Set one audio track insert slot state for EQ, dynamics, or FX.",
        "audio",
        "set_audio_track_insert",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "slot": {"type": "string"},
                "enabled": {"type": "boolean"},
                "bypassed": {"type": "boolean"},
            },
            required=("track_id", "slot"),
        ),
        required=("track_id", "slot"),
        undo_label="Set audio track insert",
        dry_summary="audio track insert slot would change",
    )
    registry.register_adapter_action(
        "audio.track.send.set_level",
        "Set one audio track send level.",
        "audio",
        "set_audio_track_send_level",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "send_id": {"type": "string"},
                "level": {"type": "number", "minimum": 0, "maximum": 1},
            },
            required=("track_id", "send_id", "level"),
        ),
        required=("track_id", "send_id", "level"),
        undo_label="Set audio send level",
        dry_summary="audio track send level would change",
    )
    registry.register_adapter_action(
        "audio.track.route_to_bus",
        "Route one audio track to a mixer bus.",
        "audio",
        "route_audio_track_to_bus",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "bus_id": {"type": "string"}},
            required=("track_id", "bus_id"),
        ),
        required=("track_id", "bus_id"),
        undo_label="Route audio track",
        dry_summary="audio track bus route would change",
    )
    registry.register_adapter_action(
        "audio.track.meter.state",
        "Read deterministic audio track meter, peak hold, and clip LED state.",
        "audio",
        "audio_track_meter_state",
        params_schema=schema_object({"track_id": {"type": "integer"}}),
        mutating=False,
        changed=False,
        dry_summary="audio track meter state would be read",
    )
    registry.register_adapter_action(
        "audio.automation.state",
        "Read audio mixer automation read/write state and lane points.",
        "audio",
        "audio_automation_state",
        params_schema=schema_object({"track_id": {"type": "integer"}}),
        mutating=False,
        changed=False,
        dry_summary="audio automation state would be read",
    )
    registry.register_adapter_action(
        "audio.automation.write",
        "Write or update one audio automation point and enable write/read state.",
        "audio",
        "write_audio_automation",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "parameter": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "value": {"type": "number"},
                "read": {"type": "boolean"},
                "write": {"type": "boolean"},
            },
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Write audio automation",
        dry_summary="audio automation would change",
    )
    registry.register_adapter_action(
        "audio.automation.clear",
        "Clear audio automation points for one track.",
        "audio",
        "clear_audio_automation",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "parameter": {"type": "string"}},
            required=("track_id",),
        ),
        required=("track_id",),
        undo_label="Clear audio automation",
        dry_summary="audio automation would be cleared",
    )
    registry.register_adapter_action(
        "audio.mixer.snapshot.save",
        "Save the current audio mixer state as a restorable snapshot.",
        "audio",
        "save_audio_mixer_snapshot",
        params_schema=schema_object({"snapshot_id": {"type": "string"}, "name": {"type": "string"}}),
        undo_label="Save audio mixer snapshot",
        dry_summary="audio mixer snapshot would be saved",
    )
    registry.register_adapter_action(
        "audio.mixer.snapshot.apply",
        "Apply a saved audio mixer snapshot.",
        "audio",
        "apply_audio_mixer_snapshot",
        params_schema=schema_object({"snapshot_id": {"type": "string"}}, required=("snapshot_id",)),
        required=("snapshot_id",),
        undo_label="Apply audio mixer snapshot",
        dry_summary="audio mixer snapshot would be applied",
    )
    registry.register_adapter_action(
        "audio.mixer.snapshot.compare",
        "Compare the current audio mixer state against a saved snapshot.",
        "audio",
        "compare_audio_mixer_snapshot",
        params_schema=schema_object({"snapshot_id": {"type": "string"}}, required=("snapshot_id",)),
        required=("snapshot_id",),
        mutating=False,
        changed=False,
        dry_summary="audio mixer snapshot would be compared",
    )
    registry.register_adapter_action(
        "audio.mixer.state",
        "Read the current audio mixer state for local AI planning.",
        "audio",
        "audio_mixer_state",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="audio mixer state would be read",
    )
    registry.register_adapter_action(
        "audio.sound_editor.jog_shuttle.state",
        "Read the Workbench Sound Editor jog shuttle state for an audio clip.",
        "audio",
        "sound_editor_jog_shuttle_state",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "clip_id": {"type": "integer"}},
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        mutating=False,
        changed=False,
        dry_summary="sound editor jog shuttle state would be read",
    )
    registry.register_adapter_action(
        "audio.sound_editor.jog_shuttle.set",
        "Set the Workbench Sound Editor jog shuttle position and playback preview state.",
        "audio",
        "set_sound_editor_jog_shuttle",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "position_ms": {"type": "integer", "minimum": 0},
                "normalized_position": {"type": "number", "minimum": 0, "maximum": 1},
                "step_ms": {"type": "integer"},
                "playing": {"type": "boolean"},
                "focus_workbench": {"type": "boolean"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Set sound editor jog shuttle",
        dry_summary="sound editor jog shuttle would change",
    )
    registry.register_adapter_action(
        "audio.sound_editor.advanced_lab.state",
        "Read the inline Workbench Sound Editor Advanced Lab state.",
        "audio",
        "sound_editor_advanced_lab_state",
        params_schema=schema_object(
            {"track_id": {"type": "integer"}, "clip_id": {"type": "integer"}},
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        mutating=False,
        changed=False,
        dry_summary="sound editor advanced lab state would be read",
    )
    registry.register_adapter_action(
        "audio.sound_editor.advanced_lab.set",
        "Expand or collapse the inline Workbench Sound Editor Advanced Lab.",
        "audio",
        "set_sound_editor_advanced_lab",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "expanded": {"type": "boolean"},
                "focus_workbench": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "expanded"),
        ),
        required=("track_id", "clip_id", "expanded"),
        undo_label="Set sound editor advanced lab",
        dry_summary="sound editor advanced lab would change",
    )
    registry.register_adapter_action(
        "audio.sound_editor.apply_effects",
        "Apply renewed Sound Editor basic controls and effect state to an audio clip.",
        "audio",
        "apply_sound_editor_effects",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "basic": {"type": "object"},
                "effects": {"type": "object"},
                "merge": {"type": "boolean"},
                "focus_workbench": {"type": "boolean"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Apply sound editor effects",
        dry_summary="sound editor basic/effect state would be applied",
    )
    registry.register_adapter_action(
        "audio.sound_editor.apply_ai_preset",
        "Apply a Sound Editor AI Master preset to an audio clip.",
        "audio",
        "apply_sound_editor_ai_preset",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "preset": {"type": "string"},
                "focus_workbench": {"type": "boolean"},
            },
            required=("track_id", "clip_id", "preset"),
        ),
        required=("track_id", "clip_id", "preset"),
        undo_label="Apply sound editor AI preset",
        dry_summary="sound editor AI Master preset would be applied",
    )
    registry.register_adapter_action(
        "audio.loudness_report",
        "Read a loudness and true-peak diagnostic report for an audio clip.",
        "audio",
        "audio_loudness_report",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "target_lufs": {"type": "number"},
                "true_peak_limit_db": {"type": "number"},
                "tolerance_lufs": {"type": "number"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        mutating=False,
        changed=False,
        dry_summary="audio loudness report would be calculated",
    )
    registry.register_adapter_action(
        "audio.separate_stems",
        "Separate an audio clip into vocals and instrumental stems.",
        "audio",
        "separate_audio_stems",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "output_root": {"type": "string"},
                "prefer_demucs": {"type": "boolean"},
                "add_to_timeline": {"type": "boolean"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        undo_label="Separate audio stems",
        async_kind="audio_stem_separation",
        dry_summary="audio clip would be separated into vocals and instrumental stems",
    )
    registry.register_adapter_action(
        "audio.export_clip",
        "Export an edited Sound Editor audio clip.",
        "audio",
        "export_audio_clip",
        params_schema=schema_object(
            {
                "track_id": {"type": "integer"},
                "clip_id": {"type": "integer"},
                "out_path": {"type": "string"},
                "format": {"type": "string"},
                "quality_id": {"type": "string"},
            },
            required=("track_id", "clip_id"),
        ),
        required=("track_id", "clip_id"),
        mutating=False,
        async_kind="audio_export",
        dry_summary="edited audio clip would be exported",
    )
