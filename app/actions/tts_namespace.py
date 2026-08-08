"""TTS sidecar setup action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_tts_actions(registry: Any) -> None:
    """Register local TTS provider setup/status actions."""
    any_object = {"type": "object", "additionalProperties": True}
    voice_params = {
        "provider_id": {"type": "string"},
        "model_name": {"type": "string"},
        "subtitle_indices": {"type": "array", "items": {"type": "integer"}},
        "output_dir": {"type": "string"},
        "track_id": {"type": "integer"},
        "track_name": {"type": "string"},
        "language": {"type": "string"},
        "style": {"type": "string"},
        "style_weight": {"type": "number"},
        "sdp_ratio": {"type": "number"},
        "noise": {"type": "number"},
        "noisew": {"type": "number"},
        "length": {"type": "number"},
        "timeout_s": {"type": "number"},
        "auto_start_server": {"type": "boolean"},
        "server_wait_timeout_s": {"type": "number"},
        "apply_actor_lipsync": {"type": "boolean"},
        "actor_track_id": {"type": "integer"},
        "actor_clip_index": {"type": "integer"},
        "lipsync_param_id": {"type": "string"},
        "lipsync_form_param_id": {"type": "string"},
        "lipsync_open_value": {"type": "number"},
        "lipsync_include_blink": {"type": "boolean"},
        "lipsync_blink_left_param_id": {"type": "string"},
        "lipsync_blink_right_param_id": {"type": "string"},
        "lipsync_blink_interval_ms": {"type": "integer"},
        "lipsync_blink_duration_ms": {"type": "integer"},
    }
    registry.register_adapter_action(
        "tts.provider.status",
        "Report local TTS sidecar readiness.",
        "tts",
        "tts_provider_status",
        params_schema=schema_object({"provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS provider status would be read",
    )
    registry.register_adapter_action(
        "tts.provider.select",
        "Select the active local TTS provider for Voice Lab.",
        "tts",
        "tts_select_provider",
        params_schema=schema_object({"provider_id": {"type": "string"}}, required=("provider_id",)),
        required=("provider_id",),
        requires_owner=False,
        undo_label="Select TTS provider",
        dry_summary="active TTS provider would be selected",
    )
    registry.register_adapter_action(
        "tts.setup.instructions",
        "Return user-facing TTS setup instructions.",
        "tts",
        "tts_setup_instructions",
        params_schema=schema_object({"provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS setup instructions would be read",
    )
    registry.register_adapter_action(
        "tts.setup.view",
        "Return the UI-ready Voice Lab TTS setup model.",
        "tts",
        "tts_setup_view",
        params_schema=schema_object({"provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS setup view model would be read",
    )
    registry.register_adapter_action(
        "tts.voice_library.catalog",
        "List every Voice Lab voice library entry, including ready providers and planned adapters.",
        "tts",
        "tts_voice_library_catalog",
        params_schema=schema_object({}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="Voice Lab voice library catalog would be listed",
    )
    registry.register_adapter_action(
        "tts.voice_lab.open",
        "Open or raise the standalone Voice Lab window from the Workbench Audio dock.",
        "tts",
        "tts_voice_lab_open",
        params_schema=schema_object({"activate": {"type": "boolean"}}, additional_properties=True),
        mutating=False,
        changed=False,
        async_kind="ui",
        dry_summary="Voice Lab window would be opened or raised",
    )
    registry.register_adapter_action(
        "tts.install.plan",
        "Return the safe local TTS install plan without running it.",
        "tts",
        "tts_install_plan",
        params_schema=schema_object({"install_root": {"type": "string"}, "provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS install plan would be prepared",
    )
    registry.register_adapter_action(
        "tts.install.execution_gate",
        "Return the explicit confirmation gate for installing the TTS sidecar.",
        "tts",
        "tts_install_execution_gate",
        params_schema=schema_object({"install_root": {"type": "string"}, "provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS install confirmation gate would be prepared",
    )
    registry.register_adapter_action(
        "tts.server.start_plan",
        "Return the local TTS server start command without launching it.",
        "tts",
        "tts_server_start_plan",
        params_schema=schema_object({"provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS server start plan would be prepared",
    )
    registry.register_adapter_action(
        "tts.server.ensure_running",
        "Check the local TTS server, start it if needed, and wait until it is ready.",
        "tts",
        "tts_server_ensure_running",
        params_schema=schema_object(
            {
                "auto_start": {"type": "boolean"},
                "wait_timeout_s": {"type": "number"},
            }
        ),
        mutating=True,
        requires_owner=False,
        undo_label="Start TTS server",
        async_kind="tts_start",
        dry_summary="TTS server readiness would be checked and the sidecar would auto-start if needed",
    )
    registry.register_adapter_action(
        "tts.connect_installed_sidecar",
        "Connect an existing Style-Bert-VITS2 install as the local TTS provider.",
        "tts",
        "tts_connect_installed_sidecar",
        params_schema=schema_object(
            {
                "root_path": {"type": "string"},
                "provider_id": {"type": "string"},
                "endpoint": {"type": "string"},
                "auto_start": {"type": "boolean"},
            },
            required=("root_path",),
        ),
        required=("root_path",),
        requires_owner=False,
        undo_label="Connect TTS sidecar",
        dry_summary="existing TTS sidecar would be connected",
    )
    model_training_params = {
        "model_name": {"type": "string"},
        "source_audio_dir": {"type": "string"},
        "overwrite": {"type": "boolean"},
    }
    registry.register_adapter_action(
        "tts.model.training.plan",
        "Return the local Style-Bert-VITS2 voice-model training plan.",
        "tts",
        "tts_model_training_plan",
        params_schema=schema_object(model_training_params),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS model training plan would be prepared",
    )
    registry.register_adapter_action(
        "tts.model.training.execution_gate",
        "Return the explicit confirmation gate for creating a local TTS voice model.",
        "tts",
        "tts_model_training_execution_gate",
        params_schema=schema_object(model_training_params),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS model training confirmation gate would be prepared",
    )
    registry.register_adapter_action(
        "tts.model.training.prepare_workspace",
        "Create Data/<model>/raw and optionally copy source audio for local voice-model training.",
        "tts",
        "tts_model_training_prepare_workspace",
        params_schema=schema_object(model_training_params, required=("model_name",)),
        required=("model_name",),
        requires_owner=False,
        undo_label="Prepare TTS model workspace",
        async_kind="tts_model_training_prepare",
        dry_summary="TTS model training workspace would be prepared",
    )
    registry.register_adapter_action(
        "tts.model.training.launch_dataset",
        "Launch the Style-Bert-VITS2 Dataset UI for slicing and transcription.",
        "tts",
        "tts_model_training_launch_dataset",
        params_schema=schema_object(model_training_params),
        requires_owner=False,
        undo_label="Launch TTS Dataset UI",
        async_kind="tts_model_training_dataset",
        dry_summary="Style-Bert-VITS2 Dataset UI would be launched",
    )
    registry.register_adapter_action(
        "tts.model.training.launch_train",
        "Launch the Style-Bert-VITS2 Train UI for preprocessing and model training.",
        "tts",
        "tts_model_training_launch_train",
        params_schema=schema_object(model_training_params),
        requires_owner=False,
        undo_label="Launch TTS Train UI",
        async_kind="tts_model_training_train",
        dry_summary="Style-Bert-VITS2 Train UI would be launched",
    )
    registry.register_adapter_action(
        "tts.model.training.register_result",
        "Validate a completed model_assets/<model> folder and refresh Voice Lab availability.",
        "tts",
        "tts_model_training_register_result",
        params_schema=schema_object({"model_name": {"type": "string"}}, required=("model_name",)),
        required=("model_name",),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="completed TTS model asset would be validated",
    )
    registry.register_adapter_action(
        "tts.voice.list",
        "List local TTS voice models available to Voice Lab.",
        "tts",
        "tts_voice_list",
        params_schema=schema_object({"provider_id": {"type": "string"}}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS voice models would be listed",
    )
    registry.register_adapter_action(
        "tts.subtitle.plan",
        "Preview subtitle-to-voice generation rows and target track.",
        "tts",
        "tts_subtitle_plan",
        params_schema=schema_object(
            {
                "model_name": {"type": "string"},
                "provider_id": {"type": "string"},
                "subtitle_indices": {"type": "array", "items": {"type": "integer"}},
                "output_dir": {"type": "string"},
                "track_id": {"type": "integer"},
                "track_name": {"type": "string"},
            }
        ),
        mutating=False,
        requires_owner=True,
        changed=False,
        dry_summary="subtitle-to-voice plan would be read",
    )
    registry.register_adapter_action(
        "tts.subtitle.generate_to_timeline",
        "Generate TTS wav files from project subtitles, place them on a dialogue audio track, and optionally bake actor lip-sync.",
        "tts",
        "tts_generate_subtitle_track",
        params_schema=schema_object(
            {
                **voice_params,
                "replace_existing": {"type": "boolean"},
            }
        ),
        undo_label="Generate subtitle TTS track",
        async_kind="tts_generate",
        dry_summary="project subtitles would be synthesized and placed on an audio track",
    )
    registry.register_adapter_action(
        "tts.dialogue.plan_actor_take",
        "Return selectable Live2D, TTS voice, and placement choices for an AI dialogue take.",
        "tts",
        "tts_dialogue_plan_actor_take",
        params_schema=schema_object(
            {
                "dialogue_text": {"type": "string"},
                "provider_id": {"type": "string"},
                "lines": {"type": "array", "items": any_object},
                "start_ms": {"type": "integer"},
                "default_duration_ms": {"type": "integer"},
                "gap_ms": {"type": "integer"},
                "chars_per_second": {"type": "number"},
            },
            additional_properties=True,
        ),
        mutating=False,
        requires_owner=True,
        changed=False,
        dry_summary="dialogue actor-take choices would be listed",
    )
    registry.register_adapter_action(
        "tts.dialogue.generate_actor_take",
        "Create dialogue subtitles, generate TTS audio, and bake Live2D mouth/blink keys in one action.",
        "tts",
        "tts_dialogue_generate_actor_take",
        params_schema=schema_object(
            {
                **voice_params,
                "dialogue_text": {"type": "string"},
                "lines": {"type": "array", "items": any_object},
                "start_ms": {"type": "integer"},
                "default_duration_ms": {"type": "integer"},
                "gap_ms": {"type": "integer"},
                "chars_per_second": {"type": "number"},
                "create_subtitles": {"type": "boolean"},
                "replace_existing": {"type": "boolean"},
                "actor_target_id": {"type": "string"},
                "apply_actor_placement": {"type": "boolean"},
                "apply_actor_motion": {"type": "boolean"},
                "actor_motion_style": {"type": "string"},
                "actor_motion_interval_ms": {"type": "integer"},
                "placement_preset": {"type": "string"},
                "size_preset": {"type": "string"},
                "canvas_width": {"type": "integer"},
                "canvas_height": {"type": "integer"},
                "placement_sample_ms": {"type": "integer"},
                "placement_replace_transform_keyframes": {"type": "boolean"},
            },
            additional_properties=True,
        ),
        undo_label="Generate TTS actor dialogue take",
        async_kind="tts_generate",
        dry_summary="dialogue text would create subtitles, TTS clips, and Live2D mouth/blink animation",
    )
    registry.register_adapter_action(
        "tts.subtitle.apply_actor_lipsync",
        "Bake subtitle or generated TTS clip timing into a selected Live2D actor mouth and blink parameter track.",
        "tts",
        "tts_apply_actor_lipsync",
        params_schema=schema_object(
            {
                "actor_track_id": {"type": "integer"},
                "actor_clip_index": {"type": "integer"},
                "rows": {"type": "array", "items": any_object},
                "replace_existing": {"type": "boolean"},
                "use_generated_clips": {"type": "boolean"},
                "mouth_param_id": {"type": "string"},
                "mouth_form_param_id": {"type": "string"},
                "open_value": {"type": "number"},
                "include_blink": {"type": "boolean"},
                "blink_left_param_id": {"type": "string"},
                "blink_right_param_id": {"type": "string"},
                "blink_interval_ms": {"type": "integer"},
                "blink_duration_ms": {"type": "integer"},
            },
            required=("actor_track_id",),
            additional_properties=True,
        ),
        required=("actor_track_id",),
        undo_label="Apply TTS actor lip-sync",
        dry_summary="TTS/subtitle timing would be baked into the selected Live2D actor with mouth and blink keys",
    )


__all__ = ["register_tts_actions"]
