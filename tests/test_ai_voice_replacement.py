from __future__ import annotations

import json


def _document():
    from app.ai_edit_plan import TranscriptDocument, TranscriptSegment

    return TranscriptDocument(
        id="doc",
        source_media_id="clip",
        language="ko-en",
        created_by="test",
        segments=(
            TranscriptSegment(
                id="seg_001",
                start_ms=1000,
                end_ms=2300,
                text="Original sentence.",
                speaker="speaker_1",
            ),
        ),
    )


def test_sentence_voice_replacement_plan_uses_safe_replace_operation() -> None:
    from app.ai_voice_replacement import build_sentence_voice_replacement_plan, voice_clone_consent_contract

    plan = build_sentence_voice_replacement_plan(
        _document(),
        segment_id="seg_001",
        replacement_text="Updated sentence.",
    )
    missing = voice_clone_consent_contract()

    assert plan.requires_review is True
    assert plan.operations[0].type == "replace_audio_range"
    assert plan.operations[0].params["preview_required"] is True
    assert plan.operations[0].params["fallback"] == "adr_recording_cue"
    assert missing["allows_custom_voice_generation"] is False


def test_ai_voice_replacement_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_ai_voice_replacement

    out = tmp_path / "voice_replacement.json"
    monkeypatch.setattr("sys.argv", ["qa_ai_voice_replacement.py", "--out", str(out)])

    assert qa_ai_voice_replacement.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ai_voice_replacement_contract_ready"] is True
    assert stdout["ok"] is True
