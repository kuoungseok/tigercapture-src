"""TTS sidecar setup action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


def register_tts_actions(registry: Any) -> None:
    """Register local TTS provider setup/status actions."""
    any_object = {"type": "object", "additionalProperties": True}
    voice_params = {
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
    }
    registry.register_adapter_action(
        "tts.provider.status",
        "Report local TTS sidecar readiness.",
        "tts",
        "tts_provider_status",
        params_schema=schema_object({}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS provider status would be read",
    )
    registry.register_adapter_action(
        "tts.setup.instructions",
        "Return user-facing TTS setup instructions.",
        "tts",
        "tts_setup_instructions",
        params_schema=schema_object({}),
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
        params_schema=schema_object({}),
        mutating=False,
        requires_owner=False,
        changed=False,
        dry_summary="TTS setup view model would be read",
    )
    registry.register_adapter_action(
        "tts.install.plan",
        "Return the safe local TTS install plan without running it.",
        "tts",
        "tts_install_plan",
        params_schema=schema_object({"install_root": {"type": "string"}}),
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
        params_schema=schema_object({"install_root": {"type": "string"}}),
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
        params_schema=schema_object({}),
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
    registry.register_adapter_action(
        "tts.voice.list",
        "List local TTS voice models available to Voice Lab.",
        "tts",
        "tts_voice_list",
        params_schema=schema_object({}),
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
        "tts.subtitle.apply_actor_lipsync",
        "Bake subtitle or generated TTS clip timing into a selected Live2D actor mouth parameter track.",
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
            },
            required=("actor_track_id",),
            additional_properties=True,
        ),
        required=("actor_track_id",),
        undo_label="Apply TTS actor lip-sync",
        dry_summary="TTS/subtitle timing would be baked into the selected Live2D actor",
    )


__all__ = ["register_tts_actions"]
