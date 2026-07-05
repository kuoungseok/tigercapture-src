from __future__ import annotations

import json

from app.descript_lite_readiness import DESCRIPT_LITE_PRIORITY_ORDER, build_descript_lite_readiness_report


def _area(report: dict, area_id: str) -> dict:
    return next(row for row in report["areas"] if row["id"] == area_id)


def test_descript_lite_readiness_preserves_user_priority_order() -> None:
    report = build_descript_lite_readiness_report()

    assert report["kind"] == "descript_lite_readiness"
    assert report["ok"] is True
    assert report["priority_order"] == list(DESCRIPT_LITE_PRIORITY_ORDER)
    assert [row["id"] for row in report["areas"]] == list(DESCRIPT_LITE_PRIORITY_ORDER)
    assert [row["label"].split(".", 1)[0] for row in report["areas"]] == ["1", "2", "3", "4", "5", "6", "7"]
    assert report["descript_lite_claim_ready"] is True
    assert report["price_149_plus_defense_ready"] is True


def test_descript_lite_text_editing_gate_is_honest_about_remaining_core_work() -> None:
    report = build_descript_lite_readiness_report()
    text_area = _area(report, "text_based_timeline_editing")
    checks = {row["id"]: row for row in text_area["checks"]}

    assert checks["reviewed_video_audio_ripple_cut"]["ready"] is True
    assert checks["selection_delete_ripple_plan"]["ready"] is True
    assert checks["sentence_move_to_clip_move"]["ready"] is True
    assert checks["selection_caption_zoom_highlight"]["ready"] is True
    assert checks["transcript_auto_reorder"]["ready"] is True
    assert checks["panel_owned_transcript_editor"]["ready"] is True
    assert text_area["claim_ready"] is True
    assert text_area["blockers"] == []


def test_descript_lite_cleanup_and_audio_gates_track_speech_enhance_evidence() -> None:
    report = build_descript_lite_readiness_report()
    cleanup_area = _area(report, "one_click_cleanup")
    audio_area = _area(report, "studio_sound_audio")
    cleanup_checks = {row["id"]: row for row in cleanup_area["checks"]}
    audio_checks = {row["id"]: row for row in audio_area["checks"]}

    assert cleanup_checks["filler_word_plan"]["ready"] is True
    assert cleanup_checks["silence_plan"]["ready"] is True
    assert cleanup_checks["retake_detection"]["ready"] is True
    assert cleanup_checks["mistake_repeat_detection"]["ready"] is True
    assert cleanup_area["claim_ready"] is True
    assert audio_checks["noise_reduction"]["ready"] is True
    assert audio_checks["speech_enhance_contract"]["ready"] is True
    assert "regenerative_studio_sound" in audio_area["blockers"] or audio_area["claim_ready"] is True


def test_descript_lite_transcription_contract_and_runtime_evidence_are_ready() -> None:
    report = build_descript_lite_readiness_report()
    transcription_area = _area(report, "transcription_quality")
    checks = {row["id"]: row for row in transcription_area["checks"]}

    assert checks["whisperx_word_engine"]["ready"] is True
    assert checks["speaker_diarization_engine"]["ready"] is True
    assert checks["punctuation_paragraph_cleanup"]["ready"] is True
    assert checks["mixed_language_glossary"]["ready"] is True
    assert checks["runtime_transcription_model_evidence"]["ready"] is True
    assert transcription_area["claim_ready"] is True


def test_descript_lite_readiness_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_descript_lite_readiness

    out = tmp_path / "descript_lite_readiness.json"
    monkeypatch.setattr("sys.argv", ["qa_descript_lite_readiness.py", "--out", str(out)])

    assert qa_descript_lite_readiness.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "descript_lite_readiness"
    assert payload["descript_lite_claim_ready"] is True
    assert stdout["ok"] is True
