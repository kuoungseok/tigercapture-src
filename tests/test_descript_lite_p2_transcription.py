from __future__ import annotations

import json


RAW_SEGMENTS = [
    {
        "id": "seg_001",
        "start_ms": 0,
        "end_ms": 2000,
        "text": "obs 타임 라인 export",
        "words": [
            {"text": "obs", "start_ms": 0, "end_ms": 400, "confidence": 0.91},
            {"text": "타임", "start_ms": 500, "end_ms": 900, "confidence": 0.88},
            {"text": "라인", "start_ms": 900, "end_ms": 1200, "confidence": 0.86},
            {"text": "export", "start_ms": 1300, "end_ms": 1800, "confidence": 0.92},
        ],
    },
    {"id": "seg_002", "start_ms": 3200, "end_ms": 5200, "text": "라이브 투디 shader check"},
]


def test_editable_script_builder_adds_words_speakers_punctuation_and_glossary() -> None:
    from app.transcription_providers import build_editable_script_document, segments_to_word_timed_document

    word_doc = segments_to_word_timed_document(RAW_SEGMENTS, document_id="doc", source_media_id="clip", language="ko-en")
    editable = build_editable_script_document(
        RAW_SEGMENTS,
        speaker_turns=[
            {"speaker": "speaker_1", "start_ms": 0, "end_ms": 2200},
            {"speaker": "speaker_2", "start_ms": 3000, "end_ms": 5400},
        ],
        document_id="doc",
        source_media_id="clip",
        language="ko-en",
    )

    assert word_doc.segments[0].words[0].text == "obs"
    assert word_doc.segments[0].words[0].confidence == 0.91
    assert word_doc.segments[1].words[-1].end_ms == 5200
    assert [segment.speaker for segment in editable.segments] == ["speaker_1", "speaker_2"]
    assert "OBS" in editable.segments[0].text
    assert "Live2D" in editable.segments[1].text
    assert all(segment.text.endswith(".") for segment in editable.segments)
    assert editable.metadata["cleanup"]["paragraph_count"] == 2


def test_script_edit_model_prepares_current_document_for_editing() -> None:
    from app.ai_script_edit_panel import ScriptEditPanelModel
    from app.transcription_providers import segments_to_word_timed_document

    model = ScriptEditPanelModel(source_media_id="clip", language="ko-en")
    model.set_transcript_document(segments_to_word_timed_document(RAW_SEGMENTS, document_id="doc", source_media_id="clip"))
    prepared = model.prepare_editable_script(
        speaker_turns=[
            {"speaker": "speaker_1", "start_ms": 0, "end_ms": 2200},
            {"speaker": "speaker_2", "start_ms": 3000, "end_ms": 5400},
        ]
    )

    assert model.document is prepared
    assert model.transcript_surface.document is prepared
    assert prepared.metadata["cleanup"]["punctuation_restored"] is True
    assert prepared.segments[0].speaker == "speaker_1"


def test_local_ml_transcribe_source_requests_word_timestamps() -> None:
    source = __import__("pathlib").Path("app/local_ml.py").read_text(encoding="utf-8")

    assert "word_timestamps=True" in source
    assert "'words': words" in source
    assert "configure_local_whisper_model.py" in source


def test_descript_lite_p2_transcription_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_descript_lite_p2_transcription

    out = tmp_path / "p2_transcription.json"
    monkeypatch.setattr("sys.argv", ["qa_descript_lite_p2_transcription.py", "--out", str(out)])

    assert qa_descript_lite_p2_transcription.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["score"] == 100
    assert stdout["ok"] is True
