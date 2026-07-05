from __future__ import annotations

import json

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment


def _cleanup_document() -> TranscriptDocument:
    return TranscriptDocument(
        id="cleanup_doc",
        source_media_id="clip_cleanup",
        language="en-ko",
        segments=(
            TranscriptSegment(id="seg_001", start_ms=1000, end_ms=2600, text="we need to export the timeline"),
            TranscriptSegment(id="seg_002", start_ms=3200, end_ms=5200, text="we need to export the timeline"),
            TranscriptSegment(id="seg_003", start_ms=7000, end_ms=8700, text="wait wait let me try again"),
            TranscriptSegment(id="seg_004", start_ms=9000, end_ms=11000, text="now the export is correct"),
        ),
    )


def test_retake_and_mistake_detectors_emit_reviewable_cut_candidates() -> None:
    from app.retake_detection import (
        detect_mistake_candidates,
        detect_retake_candidates,
        plan_remove_mistakes,
        plan_remove_retakes,
    )

    document = _cleanup_document()
    retakes = detect_retake_candidates(document)
    mistakes = detect_mistake_candidates(document)
    retake_plan = plan_remove_retakes(document)
    mistake_plan = plan_remove_mistakes(document)

    assert [candidate.segment_id for candidate in retakes] == ["seg_001"]
    assert retakes[0].keep_segment_id == "seg_002"
    assert [candidate.segment_id for candidate in mistakes] == ["seg_003"]
    assert all(operation.type == "delete_time_range" for operation in retake_plan.operations)
    assert all(operation.type == "delete_time_range" for operation in mistake_plan.operations)
    assert retake_plan.review_cards[0].operation_ids == tuple(operation.id for operation in retake_plan.operations)
    assert mistake_plan.review_cards[0].operation_ids == tuple(operation.id for operation in mistake_plan.operations)


def test_clean_tutorial_includes_p3_retake_and_mistake_cleanup() -> None:
    from app.ai_text_editing import clean_tutorial

    plan = clean_tutorial(_cleanup_document())
    sources = {operation.source for operation in plan.operations}

    assert {"retake_detection", "mistake_detection"} <= sources
    assert any(operation.params.get("source_operation") == "retake_detection" for operation in plan.operations)
    assert any(operation.params.get("source_operation") == "mistake_detection" for operation in plan.operations)


def test_script_edit_model_can_generate_retake_and_mistake_plans() -> None:
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel(source_media_id="clip_cleanup", language="en")
    model.set_transcript_document(_cleanup_document())
    retake = model.generate_plan("remove_retakes")
    mistake = model.generate_plan("remove_mistakes")

    assert retake.intent == "remove_retakes"
    assert len(retake.operations) == 1
    assert mistake.intent == "remove_mistakes"
    assert len(mistake.operations) == 1


def test_descript_lite_p3_cleanup_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_descript_lite_p3_cleanup

    out = tmp_path / "p3_cleanup.json"
    monkeypatch.setattr("sys.argv", ["qa_descript_lite_p3_cleanup.py", "--out", str(out)])

    assert qa_descript_lite_p3_cleanup.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["score"] == 100
    assert stdout["ok"] is True
