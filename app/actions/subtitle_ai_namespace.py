"""Whisper-based subtitle transcription action.

Wraps AISubtitleWorkflow.generate_headless so an AI agent driving the editor
through the automation bridge can transcribe the active source video and
append subtitles in one call, without opening the WhisperDialog UI.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.actions.result import ActionResult, error_result, ok_result
from app.actions.schema import ActionSpec, schema_object


def register_subtitle_ai_actions(registry: Any) -> None:
    spec = ActionSpec(
        "subtitle.transcribe_whisper",
        "Transcribe the active/first source video with Whisper and append the resulting subtitles.",
        "subtitle",
        params_schema=schema_object(
            {
                "source_path": {"type": "string", "description": "Optional explicit video path; defaults to the active track's source."},
                "language": {"type": "string", "description": "Optional ISO language code; empty means auto-detect."},
                "model_size": {"type": "string", "description": "Whisper model size (tiny/base/small/medium/large-v3)."},
            }
        ),
        mutating=True,
        destructive=False,
        requires_owner=True,
        supports_dry_run=False,
    )

    def _handler(params: Mapping[str, Any], dry_run: bool) -> ActionResult:
        owner = registry.owner
        if owner is None:
            return error_result("subtitle.transcribe_whisper", "no editor owner")
        outcome = owner.generate_ai_subtitles_headless(
            source_path=str(params.get("source_path") or "") or None,
            language=str(params.get("language") or ""),
            model_size=str(params.get("model_size") or "small"),
        )
        if not outcome.get("ok"):
            return error_result("subtitle.transcribe_whisper", str(outcome.get("error") or "transcription_failed"))
        return ok_result("subtitle.transcribe_whisper", outcome, changed=bool(outcome.get("count")))

    registry.register(spec, _handler)


__all__ = ["register_subtitle_ai_actions"]
