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
