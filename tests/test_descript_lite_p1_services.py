from __future__ import annotations

import json

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment, TranscriptWord


def _sample_document() -> TranscriptDocument:
    return TranscriptDocument(
        id="doc_test",
        source_media_id="clip_a",
        language="en",
        segments=(
            TranscriptSegment(
                id="seg_001",
                start_ms=1000,
                end_ms=4200,
                text="alpha beta gamma",
                words=(
                    TranscriptWord("alpha", 1000, 1400),
                    TranscriptWord("beta", 1600, 2100),
                    TranscriptWord("gamma", 2600, 3200),
                ),
            ),
            TranscriptSegment(id="seg_002", start_ms=5000, end_ms=6200, text="move me"),
        ),
    )


def test_reflow_transcript_after_reviewed_cut_removes_words_and_shifts_time() -> None:
    from app.transcript_reflow import reflow_transcript_after_cuts

    reflowed = reflow_transcript_after_cuts(
        _sample_document(),
        [{"id": "cut_beta", "original_start_ms": 1500, "original_end_ms": 2500}],
    )

    assert reflowed.created_by == "transcript_reflow"
    assert reflowed.metadata["reflow"]["removed_ms"] == 1000
    assert reflowed.segments[0].text == "alpha gamma"
    assert [word.text for word in reflowed.segments[0].words] == ["alpha", "gamma"]
    assert reflowed.segments[0].words[-1].start_ms == 1600
    assert reflowed.segments[1].start_ms == 4000


def test_transcript_timeline_ops_build_reviewable_delete_and_sentence_move_intents() -> None:
    from app.transcript_timeline_ops import build_delete_text_range_intents, build_sentence_move_clip_move_intents

    document = _sample_document()
    delete_intents = build_delete_text_range_intents(document, segment_id="seg_001", start_char=6, end_char=10)
    move_intents = build_sentence_move_clip_move_intents(document, source_segment_id="seg_002", before_segment_id="seg_001")

    assert delete_intents["requires_review"] is True
    assert delete_intents["cut_intents"][0]["type"] == "ripple_cut_text_range"
    assert delete_intents["time_range"] == {"start_ms": 1600, "end_ms": 2100}
    assert move_intents["required_registered_actions"] == ["timeline.split", "clip.move_linked"]
    assert move_intents["clip_move"]["strict_links"] is True
    assert move_intents["clip_move"]["delta_ms"] < 0
    assert "app/video_editor_window.py" not in json.dumps(move_intents)


def test_selection_scoped_plan_targets_only_selected_text_range() -> None:
    from app.transcript_selection_actions import build_selection_scoped_edit_plan

    plan = build_selection_scoped_edit_plan(_sample_document(), segment_id="seg_001", start_char=11, end_char=16)

    assert plan.intent == "selection_scoped_edit"
    assert [operation.type for operation in plan.operations] == ["create_subtitles", "add_auto_zoom", "add_callout"]
    for operation in plan.operations:
        assert operation.params["source_segment_id"] == "seg_001"
        assert operation.params["selection_text"] == "gamma"
    subtitle_rows = plan.operations[0].params["rows"]
    assert subtitle_rows == [
        {
            "segment_id": "seg_001",
            "start_ms": 2600,
            "end_ms": 3200,
            "text": "gamma",
            "style_preset_id": "caption-capcut-word-pop",
        }
    ]


def test_transcript_edit_surface_and_script_edit_model_own_selection_workflow() -> None:
    from app.ai_script_edit_panel import ScriptEditPanelModel
    from app.transcript_edit_surface import TranscriptEditSurface

    document = _sample_document()
    surface = TranscriptEditSurface(document)
    selection = surface.select_text_range("seg_001", 11, 16)
    scoped = surface.build_selection_scoped_plan()
    move_preview = surface.build_sentence_move_preview(source_segment_id="seg_002", before_segment_id="seg_001")

    assert selection["text"] == "gamma"
    assert [operation.type for operation in scoped.operations] == ["create_subtitles", "add_auto_zoom", "add_callout"]
    assert move_preview["required_registered_actions"] == ["timeline.split", "clip.move_linked"]
    assert surface.preview()["video_editor_window_dependency"] is False

    model = ScriptEditPanelModel(source_media_id="clip_a", language="en")
    model.set_transcript_document(document)
    assert model.transcript_edit_preview()["owner"] == "ScriptEditPanelModel"
    assert model.select_transcript_range("seg_001", 11, 16)["text"] == "gamma"
    model_plan = model.generate_selection_scoped_plan()
    assert model.current_plan is model_plan
    assert model.selected_operation_ids() == [operation.id for operation in model_plan.operations]
    model_move = model.build_sentence_move_preview(source_segment_id="seg_002", before_segment_id="seg_001")
    assert model_move["clip_move"]["strict_links"] is True
    reflowed = model.apply_transcript_reflow([{"id": "cut_beta", "original_start_ms": 1500, "original_end_ms": 2500}])
    assert reflowed.segments[0].text == "alpha gamma"


def test_descript_lite_p1_services_cli_writes_report(tmp_path, monkeypatch, capsys) -> None:
    from tools import qa_descript_lite_p1_services

    out = tmp_path / "p1_services.json"
    monkeypatch.setattr("sys.argv", ["qa_descript_lite_p1_services.py", "--out", str(out)])

    assert qa_descript_lite_p1_services.main() == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    stdout = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["score"] == 100
    assert stdout["ok"] is True
