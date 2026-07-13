"""Music Lab action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_music_actions(registry: Any) -> None:
    """Register AI-facing Music Lab composition and render actions."""
    composition_id = {"composition_id": {"type": "string"}}
    prompt_schema = {
        "prompt": {"type": "string"},
        "duration_ms": {"type": "integer", "minimum": 4000},
        "genre": {"type": "string"},
        "mood": {"type": "string"},
        "bpm": {"type": "integer", "minimum": 48, "maximum": 180},
        "key": {"type": "string"},
        "include_fx": {"type": "boolean"},
    }
    registry.register_adapter_action(
        "music.compose",
        "Create a structured Music Lab composition from a prompt.",
        "music",
        "music_compose",
        params_schema=schema_object(prompt_schema),
        undo_label="Compose music",
        async_kind="music_compose",
        dry_summary="music composition would be generated",
    )
    registry.register_adapter_action(
        "music.arrange.create",
        "Create a sectioned music arrangement from a prompt.",
        "music",
        "music_arrange_create",
        params_schema=schema_object(prompt_schema),
        undo_label="Create music arrangement",
        async_kind="music_arrange",
        dry_summary="music arrangement would be generated",
    )
    registry.register_adapter_action(
        "music.section.set",
        "Edit one section of a Music Lab composition.",
        "music",
        "music_section_set",
        params_schema=schema_object(
            {
                **composition_id,
                "section_name": {"type": "string"},
                "index": {"type": "integer", "minimum": 0},
                "name": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
                "intensity": {"type": "number", "minimum": 0, "maximum": 1},
                "chord_progression": {"type": "array", "items": {"type": "string"}},
                "backend": {"type": "string"},
                "ai_provider": {"type": "string"},
                "soundfont_path": {"type": "string"},
                "drum_kit_path": {"type": "string"},
                "sample_library_policy": {
                    "type": "string",
                    "enum": ["auto", "sample_kit_first", "soundfont_only", "procedural_only"],
                },
            },
            required=("composition_id",),
        ),
        required=("composition_id",),
        undo_label="Edit music section",
        dry_summary="music section would change",
    )
    registry.register_adapter_action(
        "music.track.create",
        "Add a MIDI/instrument track to a Music Lab composition.",
        "music",
        "music_track_create",
        params_schema=schema_object(
            {
                **composition_id,
                "role": {"type": "string"},
                "instrument": {"type": "string"},
                "volume": {"type": "number", "minimum": 0, "maximum": 1.5},
                "pan": {"type": "number", "minimum": -1, "maximum": 1},
            },
            required=("composition_id", "role"),
        ),
        required=("composition_id", "role"),
        undo_label="Create music track",
        dry_summary="music track would be added",
    )
    registry.register_adapter_action(
        "music.track.set_instrument",
        "Set one Music Lab track instrument label.",
        "music",
        "music_track_set_instrument",
        params_schema=schema_object(
            {**composition_id, "track_id": {"type": "string"}, "instrument": {"type": "string"}},
            required=("composition_id", "track_id", "instrument"),
        ),
        required=("composition_id", "track_id", "instrument"),
        undo_label="Set music instrument",
        dry_summary="music track instrument would change",
    )
    registry.register_adapter_action(
        "midi.clip.create",
        "Create a MIDI clip in a Music Lab composition track.",
        "midi",
        "midi_clip_create",
        params_schema=schema_object(
            {
                **composition_id,
                "track_id": {"type": "string"},
                "section_name": {"type": "string"},
                "start_ms": {"type": "integer", "minimum": 0},
                "duration_ms": {"type": "integer", "minimum": 1},
                "clip_id": {"type": "string"},
            },
            required=("composition_id", "track_id"),
        ),
        required=("composition_id", "track_id"),
        undo_label="Create MIDI clip",
        dry_summary="MIDI clip would be created",
    )
    registry.register_adapter_action(
        "midi.clip.write_notes",
        "Write note events to a MIDI clip.",
        "midi",
        "midi_clip_write_notes",
        params_schema=schema_object(
            {
                **composition_id,
                "track_id": {"type": "string"},
                "clip_id": {"type": "string"},
                "notes": {"type": "array"},
                "replace": {"type": "boolean"},
            },
            required=("composition_id", "track_id", "clip_id", "notes"),
            additional_properties=True,
        ),
        required=("composition_id", "track_id", "clip_id", "notes"),
        undo_label="Write MIDI notes",
        dry_summary="MIDI note events would be written",
    )
    registry.register_adapter_action(
        "midi.clip.write_chords",
        "Write chord triads to a MIDI clip.",
        "midi",
        "midi_clip_write_chords",
        params_schema=schema_object(
            {
                **composition_id,
                "track_id": {"type": "string"},
                "clip_id": {"type": "string"},
                "chords": {"type": "array"},
                "key": {"type": "string"},
                "octave": {"type": "integer"},
                "replace": {"type": "boolean"},
            },
            required=("composition_id", "track_id", "clip_id", "chords"),
            additional_properties=True,
        ),
        required=("composition_id", "track_id", "clip_id", "chords"),
        undo_label="Write MIDI chords",
        dry_summary="MIDI chord events would be written",
    )
    registry.register_adapter_action(
        "midi.clip.quantize",
        "Quantize one MIDI clip to a beat grid.",
        "midi",
        "midi_clip_quantize",
        params_schema=schema_object(
            {
                **composition_id,
                "track_id": {"type": "string"},
                "clip_id": {"type": "string"},
                "grid": {"type": "string"},
                "quantize_duration": {"type": "boolean"},
            },
            required=("composition_id", "track_id", "clip_id"),
        ),
        required=("composition_id", "track_id", "clip_id"),
        undo_label="Quantize MIDI clip",
        dry_summary="MIDI clip would be quantized",
    )
    registry.register_adapter_action(
        "music.render.preview",
        "Render a Music Lab composition to a WAV preview. Built-in renderers are draft/starter quality; backend=production requires a configured external renderer.",
        "music",
        "music_render_preview",
        params_schema=schema_object(
            {
                **composition_id,
                "output_dir": {"type": "string"},
                "backend": {"type": "string"},
                "ai_provider": {"type": "string"},
                "soundfont_path": {"type": "string"},
                "drum_kit_path": {"type": "string"},
                "sample_library_policy": {
                    "type": "string",
                    "enum": ["auto", "sample_kit_first", "soundfont_only", "procedural_only"],
                },
                "render_stems": {"type": "boolean"},
            },
        ),
        async_kind="music_render",
        dry_summary="music WAV preview mix would be rendered",
    )
    registry.register_adapter_action(
        "music.render.backends",
        "Read available Music Lab render backends, quality tiers, and production renderer readiness.",
        "music",
        "music_render_backends",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="music render backend status would be read",
    )
    registry.register_adapter_action(
        "music.export_midi",
        "Export a Music Lab composition as a standard MIDI file.",
        "music",
        "music_export_midi",
        params_schema=schema_object(
            {
                **composition_id,
                "output_path": {"type": "string"},
                "output_dir": {"type": "string"},
            }
        ),
        mutating=False,
        changed=False,
        undo_label="Export music MIDI",
        async_kind="music_export",
        dry_summary="music composition would be exported as MIDI",
    )
    registry.register_adapter_action(
        "music.render_to_timeline",
        "Render a Music Lab composition and add stems to timeline audio tracks. Draft/starter renderers are not modern production music.",
        "music",
        "music_render_to_timeline",
        params_schema=schema_object(
            {
                **composition_id,
                "output_dir": {"type": "string"},
                "at_ms": {"type": "integer", "minimum": 0},
                "roles": {"type": "array", "items": {"type": "string"}},
                "create_mix": {"type": "boolean"},
                "update_existing": {"type": "boolean"},
                "backend": {"type": "string"},
                "ai_provider": {"type": "string"},
                "soundfont_path": {"type": "string"},
                "drum_kit_path": {"type": "string"},
                "sample_library_policy": {
                    "type": "string",
                    "enum": ["auto", "sample_kit_first", "soundfont_only", "procedural_only"],
                },
            },
        ),
        undo_label="Render music to timeline",
        async_kind="music_render",
        dry_summary="music stems would be rendered and added to timeline",
    )
    registry.register_adapter_action(
        "music.compose_to_timeline",
        "Create a Music Lab arrangement, render draft/starter audio or configured production audio, add it to timeline tracks, and balance the mixer.",
        "music",
        "music_compose_to_timeline",
        params_schema=schema_object(
            {
                **prompt_schema,
                "output_dir": {"type": "string"},
                "at_ms": {"type": "integer", "minimum": 0},
                "roles": {"type": "array", "items": {"type": "string"}},
                "create_mix": {"type": "boolean"},
                "auto_balance": {"type": "boolean"},
                "update_existing": {"type": "boolean"},
                "backend": {"type": "string"},
                "ai_provider": {"type": "string"},
                "soundfont_path": {"type": "string"},
                "drum_kit_path": {"type": "string"},
                "sample_library_policy": {
                    "type": "string",
                    "enum": ["auto", "sample_kit_first", "soundfont_only", "procedural_only"],
                },
            }
        ),
        undo_label="Compose music to timeline",
        async_kind="music_render",
        dry_summary="music would be composed, rendered, added to timeline, and balanced",
    )
    registry.register_adapter_action(
        "music.regenerate_section",
        "Regenerate one Music Lab section with a new mood or intensity.",
        "music",
        "music_regenerate_section",
        params_schema=schema_object(
            {
                **composition_id,
                "section_name": {"type": "string"},
                "mood": {"type": "string"},
                "intensity": {"type": "number", "minimum": 0, "maximum": 1},
                "backend": {"type": "string"},
                "ai_provider": {"type": "string"},
                "soundfont_path": {"type": "string"},
                "drum_kit_path": {"type": "string"},
                "sample_library_policy": {
                    "type": "string",
                    "enum": ["auto", "sample_kit_first", "soundfont_only", "procedural_only"],
                },
            },
            required=("composition_id", "section_name"),
        ),
        required=("composition_id", "section_name"),
        undo_label="Regenerate music section",
        async_kind="music_compose",
        dry_summary="music section would be regenerated",
    )
    registry.register_adapter_action(
        "music.mixer.auto_balance",
        "Set timeline mixer defaults for Music Lab tracks.",
        "music",
        "music_mixer_auto_balance",
        params_schema=schema_object(
            {
                "composition_id": {"type": "string"},
                "track_ids": {"type": "array", "items": {"type": "integer"}},
            }
        ),
        undo_label="Auto-balance music mixer",
        dry_summary="music mixer faders would be balanced",
    )
    registry.register_adapter_action(
        "music.apply_master_fx",
        "Apply Sound Editor EQ/Dynamics/FX/AI Master state to rendered Music Lab mix or stem clips.",
        "music",
        "music_apply_master_fx",
        params_schema=schema_object(
            {
                "composition_id": {"type": "string"},
                "role": {"type": "string"},
                "effects": {"type": "object"},
                "merge": {"type": "boolean"},
                "focus_workbench": {"type": "boolean"},
            },
            required=("effects",),
        ),
        required=("effects",),
        undo_label="Apply Composer master FX",
        dry_summary="Sound Editor effects would be applied to rendered Composer audio",
    )
    registry.register_adapter_action(
        "music.state",
        "Read Music Lab composition state.",
        "music",
        "music_state",
        params_schema=schema_object({"composition_id": {"type": "string"}}),
        mutating=False,
        changed=False,
        dry_summary="music composition state would be read",
    )
