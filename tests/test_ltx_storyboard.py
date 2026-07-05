from __future__ import annotations

import json


def _project():
    return {
        "duration_s": 184,
        "screen_recording": True,
        "has_audio": True,
        "dialogue": True,
        "transcript_segments": [
            {"id": "seg_001", "start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
            {"id": "seg_002", "start_ms": 64000, "end_ms": 84000, "text": "Watch how the app keeps the important button in frame."},
            {"id": "seg_003", "start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for Shorts."},
        ],
    }


def _media():
    return [
        {
            "id": "screen-demo-1",
            "name": "screen tutorial recording.mp4",
            "kind": "video",
            "tags": ["screen-recording", "tutorial"],
            "object_tags": ["cursor", "button", "timeline"],
            "people": ["host"],
        }
    ]


def test_ltx_storyboard_builds_reviewable_shot_cards():
    from app.ltx_storyboard import build_ltx_storyboard_plan

    plan = build_ltx_storyboard_plan(
        "Make this a polished Screen Studio style tutorial with cursor zooms.",
        _project(),
        _media(),
    )

    assert plan.intent == "screen_tutorial"
    assert plan.claim_level == "ltx_inspired_local_shot_cards_not_ltx_cloud_parity"
    assert len(plan.shot_cards) >= 4
    assert plan.shot_cards[0].camera_motion
    assert plan.shot_cards[0].transition_hint
    assert plan.shot_cards[0].source_media_id == "screen-demo-1"
    assert plan.style_bible["safe_area"] == "vertical_caption_safe"
    assert json.loads(plan.to_stable_json())["shot_count"] == len(plan.shot_cards)


def test_ltx_storyboard_converts_to_valid_edit_plan():
    from app.ai_edit_plan import validate_edit_plan_json
    from app.ltx_storyboard import build_ltx_storyboard_plan, storyboard_to_edit_plan

    storyboard = build_ltx_storyboard_plan("Create a vertical product tutorial.", _project(), _media())
    edit_plan = storyboard_to_edit_plan(storyboard)
    restored = validate_edit_plan_json(edit_plan.to_stable_json())

    assert restored.intent == "ltx_storyboard_review"
    assert restored.requires_review is True
    assert len(restored.review_cards) == len(storyboard.shot_cards)
    assert any(operation.type == "create_short_candidate" for operation in restored.operations)
    assert any(operation.type == "add_marker" for operation in restored.operations)
    assert any(operation.type == "add_auto_zoom" for operation in restored.operations)
    assert restored.metadata["claim_level"] == "ltx_inspired_local_shot_cards_not_ltx_cloud_parity"


def test_ltx_storyboard_apply_payload_variations_and_templates():
    from app.ltx_storyboard import (
        build_ltx_storyboard_plan,
        build_ltx_storyboard_variations,
        storyboard_effect_materialization_payload,
        storyboard_apply_payload,
        storyboard_template_recommendations,
    )

    storyboard = build_ltx_storyboard_plan("Storyboard this into shot cards.", _project(), _media())
    apply_payload = storyboard_apply_payload(storyboard)
    effects = storyboard_effect_materialization_payload(storyboard, apply_payload)
    variations = build_ltx_storyboard_variations(storyboard)
    templates = storyboard_template_recommendations(storyboard)

    assert len(apply_payload["timeline_markers"]) >= len(storyboard.shot_cards)
    assert apply_payload["sidecars"]
    assert apply_payload["review_only"] is True
    assert effects["ready"] is True
    assert effects["counts"]["zoom_windows"] >= 1
    assert effects["counts"]["callouts"] >= 1
    assert effects["source_sidecar_count"] == len(apply_payload["sidecars"])
    assert variations["variation_count"] >= 3
    assert all(row["edit_plan"]["requires_review"] for row in variations["variations"])
    assert templates["card_count"] >= 3
    assert templates["cards"][0]["apply_mode"] == "review_first"


def test_ltx_storyboard_provider_contract_is_optional(monkeypatch):
    from app.ltx_storyboard import ltx_storyboard_provider_state

    monkeypatch.delenv("TIGERCAPTURE_LTX_STORYBOARD_ENDPOINT", raising=False)
    monkeypatch.delenv("TIGERCAPTURE_LTX_STORYBOARD_COMMAND", raising=False)
    assert ltx_storyboard_provider_state()["configured"] is False

    monkeypatch.setenv("TIGERCAPTURE_LTX_STORYBOARD_ENDPOINT", "http://127.0.0.1:8188")
    state = ltx_storyboard_provider_state()
    assert state["configured"] is True
    assert state["cloud_required"] is False


def test_ltx_storyboard_qa_tool_passes(tmp_path):
    from tools.qa_ltx_storyboard import run_ltx_storyboard_qa

    out = tmp_path / "ltx_storyboard_qa.json"
    report = run_ltx_storyboard_qa(out=out)

    assert report["ok"] is True
    assert report["checks"]["honest_claim"] is True
    assert report["summary"]["shot_cards"] >= 4
    assert out.exists()


def test_ltx_storyboard_corpus_qa_tool_passes(tmp_path):
    from tools.qa_ltx_storyboard_corpus import run_ltx_storyboard_corpus_qa

    out = tmp_path / "ltx_storyboard_corpus_qa.json"
    report = run_ltx_storyboard_corpus_qa(out=out)

    assert report["ok"] is True
    assert report["case_count"] >= 5
    assert report["failed"] == 0
    assert out.exists()


def test_script_edit_prompt_can_generate_storyboard_without_transcript():
    from app.ai_script_edit_panel import ScriptEditPanelModel

    model = ScriptEditPanelModel(language="en")
    plan = model.generate_plan_from_prompt(
        "Storyboard this recording into shot cards and retakes.",
        project_summary=_project(),
        media_items=_media(),
    )

    assert plan.intent == "ltx_storyboard_review"
    assert plan.requires_review is True
    assert len(plan.operations) >= 8
    assert plan.metadata["prompt_resolved_action"] == "ltx_storyboard"


def test_capcut_creator_bundle_surfaces_ltx_storyboard():
    from app.capcut_workflow import capcut_creator_apply_bundle, capcut_creator_review_panel_model

    bundle = capcut_creator_apply_bundle(_project(), _media())
    panel = capcut_creator_review_panel_model(bundle)

    assert bundle["ltx_storyboard"]["ready"] is True
    assert bundle["ltx_storyboard"]["shot_count"] >= 4
    assert bundle["ltx_storyboard_edit_plan"]["requires_review"] is True
    assert bundle["ltx_storyboard_apply_payload"]["timeline_markers"]
    assert bundle["ltx_storyboard_effect_materialization"]["ready"] is True
    assert bundle["ltx_storyboard_effect_materialization"]["counts"]["zoom_windows"] >= 1
    assert bundle["ltx_storyboard_variations"]["variation_count"] >= 3
    assert bundle["ltx_storyboard_template_recommendations"]["card_count"] >= 3
    assert len(bundle["timeline_markers"]) >= bundle["ltx_storyboard"]["shot_count"]
    assert any(card["id"] == "ltx_storyboard" for card in panel["cards"])
    assert panel["counts"]["ltx_storyboard_shots"] >= 4
    assert panel["counts"]["ltx_storyboard_variations"] >= 3


def test_capcut_apply_persists_ltx_storyboard_sidecar():
    from app.capcut_apply import capcut_apply_bundle_to_project
    from app.capcut_workflow import capcut_creator_apply_bundle

    bundle = capcut_creator_apply_bundle(_project(), _media())
    result = capcut_apply_bundle_to_project({"project_settings": {}, "timeline_markers": []}, bundle)
    package = result.project_doc["capcut_creator_package"]
    workflow = result.project_doc["project_settings"]["capcut_creator_workflow"]

    assert result.ok is True
    assert package["ltx_storyboard"]["ready"] is True
    assert package["ltx_storyboard_apply_payload"]["timeline_markers"]
    assert package["ltx_storyboard_effect_materialization"]["counts"]["zoom_windows"] >= 1
    assert workflow["ltx_storyboard_ready"] is True
    assert workflow["ltx_storyboard_zoom_windows"] >= 1
    assert workflow["ltx_storyboard_variations"] >= 3
