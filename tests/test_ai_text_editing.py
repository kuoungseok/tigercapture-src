from __future__ import annotations

import json

import pytest


SRT_SAMPLE = """1
00:00:01,000 --> 00:00:03,000
Um today we explain materials.

2
00:00:04,000 --> 00:00:06,000
어 이제 base color를 연결합니다.
"""


VTT_SAMPLE = """WEBVTT

intro
00:00:01.000 --> 00:00:02.500
Hello <b>world</b>

00:00:03.000 --> 00:00:04.000
Product demo beat
"""


def test_parse_srt_and_vtt_to_transcript_documents():
    from app.ai_text_editing import parse_srt_text, parse_vtt_text

    srt = parse_srt_text(SRT_SAMPLE, document_id="srt_doc", language="en")
    vtt = parse_vtt_text(VTT_SAMPLE, document_id="vtt_doc", language="en")

    assert srt.id == "srt_doc"
    assert len(srt.segments) == 2
    assert srt.segments[0].start_ms == 1000
    assert srt.segments[0].end_ms == 3000
    assert srt.segments[1].text.startswith("어 이제")
    assert vtt.metadata["source_format"] == "vtt"
    assert vtt.segments[0].text == "Hello world"


def test_text_range_mapping_and_filler_detection():
    from app.ai_text_editing import detect_filler_ranges, parse_srt_text, text_range_to_time_range

    document = parse_srt_text(SRT_SAMPLE)
    start_ms, end_ms = text_range_to_time_range(document, "seg_001", 0, 2)
    fillers = detect_filler_ranges(document)

    assert 1000 <= start_ms < end_ms <= 3000
    assert {item["text"].casefold() for item in fillers} >= {"um", "어", "이제"}
    assert all(item["end_ms"] > item["start_ms"] for item in fillers)


def test_filler_silence_and_caption_plans_are_valid():
    from app.ai_text_editing import (
        parse_srt_text,
        plan_remove_filler_words,
        plan_remove_silences,
        plan_transcript_to_captions,
    )

    document = parse_srt_text(SRT_SAMPLE)
    filler_plan = plan_remove_filler_words(document)
    silence_plan = plan_remove_silences(
        [{"start_ms": 3000, "end_ms": 4200}, {"start_ms": 7000, "end_ms": 7300}],
        min_duration_ms=700,
    )
    caption_plan = plan_transcript_to_captions(document)

    assert filler_plan.intent == "remove_filler_words"
    assert len(filler_plan.operations) >= 3
    assert all(operation.type == "delete_time_range" for operation in filler_plan.operations)
    assert len(silence_plan.operations) == 1
    assert silence_plan.operations[0].start_ms == 3000
    assert caption_plan.operations[0].type == "create_subtitles"
    assert len(caption_plan.operations[0].params["rows"]) == 2


def test_recipe_helpers_return_valid_layered_plans():
    from app.ai_text_editing import clean_tutorial_recipe, parse_srt_text, product_demo_recipe, shorts_recipe

    document = parse_srt_text(SRT_SAMPLE)
    clean = clean_tutorial_recipe(document, silence_intervals=[{"start_ms": 3000, "end_ms": 4200}])
    shorts = shorts_recipe(document)
    product = product_demo_recipe(document)

    for plan in (clean, shorts, product):
        payload = plan.to_dict()
        operation_ids = {operation["id"] for operation in payload["operations"]}
        card_operation_ids = [op_id for card in payload["review_cards"] for op_id in card["operation_ids"]]
        assert payload["requires_review"] is True
        assert payload["review_cards"]
        assert card_operation_ids
        assert set(card_operation_ids) <= operation_ids
        assert 0 <= payload["quality_score"] <= 100
        assert payload["metadata"]["recipe_mode"] == "one_click_reviewable"
        assert payload["operations"]

    clean_cards = {card.id: set(card.operation_ids) for card in clean.review_cards}
    clean_ops_by_id = {operation.id: operation for operation in clean.operations}
    assert clean_cards["card_cleanup"]
    assert all(clean_ops_by_id[op_id].type == "delete_time_range" for op_id in clean_cards["card_cleanup"])
    assert any(clean_ops_by_id[op_id].type == "create_subtitles" for op_id in clean_cards["card_captions"])
    for card in shorts.review_cards:
        assert len(card.operation_ids) == 1
        op = next(operation for operation in shorts.operations if operation.id == card.operation_ids[0])
        assert op.type == "create_short_candidate"
    assert set(product.review_cards[0].operation_ids) == {operation.id for operation in product.operations}
    assert any(operation.type == "add_auto_zoom" for operation in clean.operations)
    assert any(operation.type == "create_short_candidate" for operation in shorts.operations)
    assert any(operation.type == "add_callout" for operation in product.operations)


def test_malformed_plan_rejection_and_stable_serialization():
    from app.ai_edit_plan import EditPlanValidationError, validate_edit_plan_json
    from app.ai_text_editing import parse_srt_text, plan_transcript_to_captions

    document = parse_srt_text(SRT_SAMPLE)
    plan = plan_transcript_to_captions(document)
    stable_once = plan.to_stable_json()
    stable_twice = plan.to_stable_json()

    assert stable_once == stable_twice
    restored = validate_edit_plan_json(json.dumps(plan.to_dict(), ensure_ascii=False))
    assert restored.to_stable_json() == stable_once

    with pytest.raises(EditPlanValidationError):
        validate_edit_plan_json(
            json.dumps(
                {
                    "id": "bad",
                    "intent": "bad",
                    "summary": "bad",
                    "operations": [{"type": "run_python", "target": "project"}],
                    "warnings": [],
                    "requires_review": True,
                }
            )
        )


def test_operation_specific_validation_rejects_malformed_mvp_operations():
    from app.ai_edit_plan import EditPlanValidationError, validate_edit_plan_json

    def assert_rejected(operation, **extra):
        payload = {
            "id": "bad",
            "intent": "bad",
            "summary": "bad",
            "operations": [operation],
            "warnings": [],
            "requires_review": True,
            **extra,
        }
        with pytest.raises(EditPlanValidationError):
            validate_edit_plan_json(json.dumps(payload, ensure_ascii=False))

    for op_type in ("delete_time_range", "keep_time_range", "ripple_cut_text_range", "create_short_candidate"):
        assert_rejected({"type": op_type, "target": "selected_video_linked_audio", "start_ms": 1000})

    assert_rejected(
        {
            "type": "create_subtitles",
            "target": "subtitle_track",
            "params": {"rows": [{"start_ms": 1000, "end_ms": 2000}]},
        }
    )
    assert_rejected({"type": "add_render_queue_job", "target": "timeline", "params": {"variant": "demo"}})
    assert_rejected({"type": "add_callout", "target": "selected_video", "start_ms": 1000, "end_ms": 2000, "params": {}})
    assert_rejected({"type": "add_callout", "target": "selected_video", "text": "Feature", "params": {}})
    assert_rejected({"type": "add_live2d_dialogue", "target": "actor_lane", "params": {}})
    assert_rejected({"type": "add_spine_dialogue", "target": "actor_lane", "params": {}})


def test_product_demo_empty_transcript_skips_callout_and_validates():
    from app.ai_edit_plan import TranscriptDocument, validate_edit_plan_json
    from app.ai_text_editing import product_demo_recipe

    document = TranscriptDocument(id="empty", source_media_id="media_empty", segments=())
    plan = product_demo_recipe(document)
    operation_ids = {operation.id for operation in plan.operations}

    assert "product_demo_callout_skipped_no_transcript_segment" in plan.warnings
    assert not any(operation.type == "add_callout" for operation in plan.operations)
    assert set(plan.review_cards[0].operation_ids) == operation_ids
    assert validate_edit_plan_json(plan.to_stable_json()).to_stable_json() == plan.to_stable_json()


def test_plan_parser_rejects_bad_review_cards_and_warnings():
    from app.ai_edit_plan import EditPlanValidationError, validate_edit_plan_json

    base = {
        "id": "bad",
        "intent": "bad",
        "summary": "bad",
        "operations": [{"type": "delete_time_range", "target": "selected_video_linked_audio", "start_ms": 0, "end_ms": 100}],
    }
    for extra in (
        {"review_cards": ["not_an_object"]},
        {"review_cards": [{"id": "card", "title": "Card", "operation_ids": "op_001_delete_time_range"}]},
        {"warnings": "not_a_list"},
        {"warnings": [{"not": "a string"}]},
    ):
        payload = {**base, **extra}
        with pytest.raises(EditPlanValidationError):
            validate_edit_plan_json(json.dumps(payload, ensure_ascii=False))
    with pytest.raises(EditPlanValidationError):
        validate_edit_plan_json(
            json.dumps(
                {
                    "id": "bad",
                    "intent": "bad",
                    "summary": "bad",
                    "operations": [{"type": "delete_time_range", "target": "project", "params": {"shell": "rm"}}],
                }
            )
        )


def test_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_ai_text_editing

    out = tmp_path / "ai_text_editing_qa.json"
    monkeypatch.setattr("sys.argv", ["qa_ai_text_editing.py", "--out", str(out)])

    assert qa_ai_text_editing.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["checks"]["malformed_plan_rejection"] is True
    assert report["summary"]["recipe_operations"] > 0
