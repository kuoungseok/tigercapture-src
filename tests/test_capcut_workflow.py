from __future__ import annotations

import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_capcut_creator_report_covers_ten_product_areas():
    from app.capcut_workflow import CAPCUT_CREATOR_AREAS, capcut_creator_workflow_report

    report = capcut_creator_workflow_report(
        {
            "duration_s": 186,
            "has_audio": True,
            "dialogue": True,
            "screen_recording": True,
            "transcript_segments": [
                {"start_ms": 1000, "end_ms": 12000, "text": "How do you make this look good fast?"},
                {"start_ms": 41000, "end_ms": 62000, "text": "Watch the subject stay in frame."},
            ],
            "subject_detections": [
                {"t_ms": 0, "x_norm": 0.42, "y_norm": 0.46, "confidence": 0.92},
                {"t_ms": 1000, "x_norm": 0.58, "y_norm": 0.50, "confidence": 0.88},
            ],
        },
        [
            {
                "name": "tutorial demo.mp4",
                "kind": "video",
                "object_tags": ["cursor", "button"],
                "people": ["host"],
                "dialogue": ["make this look good fast"],
            }
        ],
    )

    ids = {row["id"] for row in report["areas"]}
    assert report["ok"] is True
    assert report["summary"]["areas"] == 10
    assert ids == {area.id for area in CAPCUT_CREATOR_AREAS}
    assert report["score"] >= 95
    assert report["areas"][1]["detail"]["candidates"]
    assert report["areas"][2]["detail"]["sample_hits"][0]["name"] == "tutorial demo.mp4"
    assert report["apply_simulation"]["ok"] is True
    assert report["summary"]["applied_subtitles"] >= 1
    assert report["summary"]["materialized_render_queue_jobs"] >= 1
    assert report["summary"]["edit_recipe_steps"] >= 6
    assert report["summary"]["publish_variants"] >= 3
    assert report["summary"]["review_panel_cards"] >= 7
    assert report["summary"]["review_panel_ready"] is True
    assert report["summary"]["publish_handoff_actions"] >= 5
    assert report["summary"]["publish_handoff_ready"] is True
    assert report["summary"]["quick_create_ready"] is True
    assert report["summary"]["quick_result_cards"] >= 3
    assert report["summary"]["quick_result_score"] >= 80
    assert report["summary"]["voice_workflow_cards"] >= 5
    assert report["summary"]["voice_workflow_score"] >= 85
    assert report["summary"]["voice_providers"] >= 8
    assert report["summary"]["prompt_edit_operations"] >= 3
    assert report["summary"]["prompt_edit_ready_operations"] == report["summary"]["prompt_edit_operations"]
    assert report["summary"]["collab_handoff_cards"] >= 5
    assert report["summary"]["collab_handoff_score"] >= 85
    assert report["summary"]["collab_providers"] >= 8
    assert report["quick_create"]["primary_action"]["id"] == "quick_create"


def test_creator_polish_coverage_qa_tool_writes_report(tmp_path):
    from tools.qa_creator_polish_coverage import run_creator_polish_coverage_qa

    out = tmp_path / "creator_polish_coverage.json"
    report = run_creator_polish_coverage_qa(out)

    assert report["ok"] is True
    assert out.exists()
    assert report["summary"]["passing_sections"] == report["summary"]["sections"]
    assert report["sections"]["preset_preview"]["ok"] is True
    assert report["sections"]["screenstudio_defaults"]["ok"] is True
    assert report["sections"]["capcut_quick_create"]["ok"] is True
    assert report["sections"]["stability_hooks"]["ok"] is True


def test_capcut_short_plans_social_export_and_smart_search_are_deterministic():
    from app.capcut_workflow import (
        capcut_caption_beat_plan,
        capcut_caption_timeline_rows,
        capcut_creator_apply_bundle,
        capcut_creator_edit_recipe,
        capcut_creator_review_panel_model,
        capcut_hook_score_plan,
        capcut_long_to_shorts_plan,
        capcut_multi_platform_publish_plan,
        capcut_publish_handoff_plan,
        capcut_publish_package_plan,
        capcut_quick_create_button_model,
        capcut_short_export_jobs,
        capcut_smart_media_index,
        capcut_smart_media_search,
        capcut_social_export_plan,
        capcut_subject_reframe_plan,
    )

    project = {
        "duration_s": 240,
        "has_audio": True,
        "transcript_segments": [
            {"start_ms": 8000, "end_ms": 24000, "text": "Why this shortcut matters"},
            {"start_ms": 85000, "end_ms": 112000, "text": "A quiet setup segment"},
            {"start_ms": 156000, "end_ms": 183000, "text": "Best trick for a clean export"},
        ],
    }
    shorts = capcut_long_to_shorts_plan(project, target_count=2)
    export = capcut_social_export_plan(project, platform="tiktok")
    reframe = capcut_subject_reframe_plan(project, detections=[{"t_ms": 400, "x_norm": 0.7, "y_norm": 0.4}])
    captions = capcut_caption_timeline_rows(project)
    beats = capcut_caption_beat_plan(project)
    hooks = capcut_hook_score_plan(project)
    publish = capcut_publish_package_plan(project, [{"name": "horse gameplay.mp4", "object_tags": ["horse"], "kind": "video"}])
    variants = capcut_multi_platform_publish_plan(project, [{"name": "horse gameplay.mp4", "object_tags": ["horse"], "kind": "video"}])
    recipe = capcut_creator_edit_recipe(project, [{"name": "horse gameplay.mp4", "object_tags": ["horse"], "kind": "video"}])
    jobs = capcut_short_export_jobs(project, source_path="demo.mp4", project_path="demo.tgp", output_dir="")
    bundle = capcut_creator_apply_bundle(project, [{"name": "horse gameplay.mp4", "object_tags": ["horse"], "kind": "video"}])
    panel = capcut_creator_review_panel_model(bundle)
    handoff = capcut_publish_handoff_plan(bundle)
    quick = capcut_quick_create_button_model({**bundle, "review_panel": panel, "publish_handoff": handoff})
    index = capcut_smart_media_index([
        {"name": "horse gameplay.mp4", "kind": "video", "object_tags": ["horse", "snow"], "dialogue": ["clean export"]},
        {"name": "voice bed.wav", "kind": "audio", "tags": ["music"]},
    ])
    hits = capcut_smart_media_search(index, "horse export")

    assert shorts["needs_shorts"] is True
    assert shorts["candidates"][0]["reason"] == "dialogue_hook"
    assert export["export_settings"]["canvas_height"] == 1920
    assert export["duration_over_limit"] is True
    assert reframe["mode"] == "subject_aware"
    assert captions[0]["style_preset_id"] == "caption-capcut-word-pop"
    assert beats["beats"][0]["beat_type"] == "hook"
    assert hooks["top_hook"]["reason"] in {"question_hook", "how_to_hook", "payoff_hook", "strong_statement"}
    assert publish["ready"] is True
    assert publish["thumbnail_frames"]
    assert variants["variant_count"] >= 3
    assert variants["recommended_platform"] in {"shorts", "tiktok", "reels"}
    assert recipe["ready"] is True
    assert recipe["step_count"] >= 6
    assert recipe["steps"][0]["type"] == "trim"
    assert panel["ready"] is True
    assert panel["card_count"] >= 7
    assert panel["primary_action"]["id"] == "apply_creator_recipe"
    ltx_card = next(card for card in panel["cards"] if card["id"] == "ltx_storyboard")
    assert ltx_card["label"] == "샷카드"
    assert "템플릿" in ltx_card["summary"]
    assert handoff["ready"] is True
    assert quick["enabled"] is True
    assert quick["summary"]["ready_steps"] >= 3
    assert quick["options"]["queue_exports"] is True
    assert "hashtags" in handoff["clipboard_payloads"]
    assert "#horse" in publish["hashtags"]
    assert jobs[0]["create_kwargs"]["format_id"] == "mp4"
    from app.render_queue import RenderQueueJob

    queue_job = RenderQueueJob.create(**jobs[0]["create_kwargs"])
    assert queue_job.out_ms > queue_job.in_ms
    assert queue_job.format_id == "mp4"
    assert bundle["project_settings_patch"]["canvas_height"] == 1920
    assert bundle["subtitle_rows"]
    assert bundle["hook_score_plan"]["ready"] is True
    assert bundle["caption_beat_plan"]["beat_count"] >= 1
    assert bundle["publish_package"]["ready"] is True
    assert bundle["edit_recipe"]["ready"] is True
    assert bundle["publish_variants"]["variant_count"] >= 3
    assert bundle["review_panel"]["ready"] is True
    assert bundle["publish_handoff"]["ready"] is True
    assert bundle["timeline_markers"]
    assert bundle["render_queue_jobs"][0]["create_kwargs"]["quality_id"] == "high"
    assert hits[0]["name"] == "horse gameplay.mp4"


def test_capcut_apply_bundle_merges_project_doc_without_duplicates():
    from app.capcut_apply import capcut_apply_bundle_to_project, capcut_apply_preview
    from app.capcut_workflow import capcut_creator_apply_bundle

    project = {
        "project_settings": {"name": "Manual project", "fps": 30.0},
        "export": {"format_id": "gif"},
        "subtitles": [{"text": "Manual note", "start_ms": 0, "end_ms": 900}],
        "timeline_markers": [{"ms": 500, "color": "#FFFFFF", "label": "Manual"}],
    }
    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 130,
            "has_audio": True,
            "transcript_segments": [
                {"start_ms": 1000, "end_ms": 7000, "text": "Why this opener works"},
                {"start_ms": 40000, "end_ms": 53000, "text": "Best moment for a short"},
            ],
        },
        [{"name": "demo screen.mp4", "kind": "video", "object_tags": ["cursor", "button"]}],
        target_count=2,
    )

    preview = capcut_apply_preview(project, bundle)
    first = capcut_apply_bundle_to_project(project, bundle)
    second = capcut_apply_bundle_to_project(first.project_doc, bundle)
    replaced = capcut_apply_bundle_to_project(first.project_doc, bundle, replace_existing=True)

    assert preview["adds"]["subtitles"] == 2
    assert first.ok is True
    assert first.project_doc["project_settings"]["canvas_height"] == 1920
    assert first.project_doc["project_settings"]["capcut_creator_workflow"]["caption_style_runs"]
    assert first.project_doc["capcut_creator_package"]["publish_package"]["ready"] is True
    assert first.project_doc["capcut_creator_package"]["edit_recipe"]["ready"] is True
    assert first.project_doc["capcut_creator_package"]["publish_variants"]["variant_count"] >= 3
    assert first.project_doc["capcut_creator_package"]["review_panel"]["ready"] is True
    assert first.project_doc["capcut_creator_package"]["publish_handoff"]["ready"] is True
    assert first.counts["creator_package_updated"] == 1
    assert first.project_doc["export"]["resolution"] == [1080, 1920]
    assert first.project_doc["export"]["burn_captions"] is True
    assert any(row["text"] == "Manual note" for row in first.project_doc["subtitles"])
    assert len(first.project_doc["capcut_short_ranges"]) == 2
    assert len(first.project_doc["render_queue_jobs"]) == 2
    assert first.project_doc["render_queue_jobs"][0]["create_kwargs"]["format_id"] == "mp4"
    assert second.counts["subtitles_added"] == 0
    assert second.counts["render_queue_jobs_added"] == 0
    assert len(replaced.project_doc["subtitles"]) == len(first.project_doc["subtitles"])
    assert any(row["label"] == "Manual" for row in replaced.project_doc["timeline_markers"])


def test_capcut_staged_render_jobs_can_be_added_to_render_queue(tmp_path):
    from app.capcut_apply import (
        capcut_add_render_jobs_to_store,
        capcut_apply_bundle_to_project,
        capcut_render_queue_jobs_from_payload,
    )
    from app.capcut_workflow import capcut_creator_apply_bundle
    from app.render_queue import RenderQueueStore

    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 120,
            "has_audio": True,
            "transcript_segments": [
                {"start_ms": 5000, "end_ms": 15000, "text": "Best opening hook"},
                {"start_ms": 64000, "end_ms": 74000, "text": "Second short candidate"},
            ],
        },
        target_count=2,
    )
    applied = capcut_apply_bundle_to_project({}, bundle)
    staged = capcut_render_queue_jobs_from_payload(applied.project_doc)
    queue_path = tmp_path / "render_queue.json"
    store = RenderQueueStore(queue_path)

    first = capcut_add_render_jobs_to_store(store, applied.project_doc)
    second = capcut_add_render_jobs_to_store(store, applied.project_doc)
    loaded = RenderQueueStore(queue_path)

    assert len(staged) == 2
    assert staged[0].format_id == "mp4"
    assert "CapCut short candidate" in staged[0].diagnostics
    assert first["added"] == 2
    assert first["ok"] is True
    assert second["added"] == 0
    assert second["skipped"] == 2
    assert len(loaded.jobs) == 2
    assert loaded.jobs[0].quality_id == "high"


def test_project_subtitle_roundtrip_preserves_capcut_style_and_show_box():
    from app.overlay_layer import SubtitleLayer
    from app.project_io import _load_subtitles, _subtitle_to_dict
    from app.subtitles import Subtitle

    layer = SubtitleLayer()
    editor = SimpleNamespace(_subtitle_panel=SimpleNamespace(layer=layer))
    source = Subtitle(
        start_ms=1200,
        end_ms=3400,
        text="Styled caption",
        show_box=False,
        style={
            "preset_id": "caption-capcut-word-pop",
            "source": "capcut_creator_workflow",
            "word_highlight": True,
        },
    )

    payload = _subtitle_to_dict(source)
    _load_subtitles(editor, [payload])
    restored = layer.items()

    assert payload["show_box"] is False
    assert len(restored) == 1
    assert restored[0].text == "Styled caption"
    assert restored[0].show_box is False
    assert restored[0].style["preset_id"] == "caption-capcut-word-pop"
    assert restored[0].style["word_highlight"] is True


def test_capcut_presets_are_searchable_and_in_one_click_plan():
    from app.preset_library import one_click_preset_plan, preset_ecosystem_report, search_presets

    captions = search_presets("자동자막 캡컷", kind="caption_style")
    templates = search_presets("capcut social export", kind="template")
    plan = [preset.id for preset in one_click_preset_plan({"capcut": True, "shortform": True, "auto_caption": True})]
    ecosystem = preset_ecosystem_report()

    assert any(p.id == "caption-capcut-word-pop" for p in captions)
    assert any(p.id == "template-capcut-social-publish-kit" for p in templates)
    assert "template-capcut-auto-caption-shorts" in plan
    assert "template-capcut-long-to-shorts" in plan
    assert ecosystem["topic_coverage"]["capcut"]["ok"] is True
    assert "template-capcut-auto-caption-shorts" in ecosystem["one_click_plans"]["capcut"]


def test_capcut_creator_qa_tool_writes_report(tmp_path, monkeypatch):
    from tools import qa_capcut_creator_workflow

    out = tmp_path / "capcut_qa.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_creator_workflow.py", "--out", str(out)],
    )

    assert qa_capcut_creator_workflow.main() == 0
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["ok"] is True
    assert report["summary"]["areas"] == 10
    assert report["summary"]["subtitle_rows"] >= 1
    assert report["summary"]["render_queue_jobs"] >= 1
    assert report["summary"]["hook_candidates"] >= 1
    assert report["summary"]["caption_beats"] >= 1
    assert report["summary"]["publish_package_ready"] is True
    assert report["summary"]["review_panel_ready"] is True
    assert report["summary"]["publish_handoff_ready"] is True
    assert report["summary"]["applied_render_jobs"] >= 1
    assert report["summary"]["materialized_render_queue_jobs"] >= 1
    assert report["apply_simulation"]["ok"] is True
    assert report["apply_bundle"]["project_settings_patch"]["canvas_height"] == 1920


def test_capcut_parity_next_report_tracks_remaining_gaps(tmp_path, monkeypatch):
    from app.capcut_parity import build_capcut_parity_next_report
    from tools import qa_capcut_parity_next

    report = build_capcut_parity_next_report()
    assert report["ok"] is True
    assert report["kind"] == "capcut_parity_next"
    assert report["parity_ready"] is False
    assert report["truth"] == "This is a CapCut gap tracker, not a full parity claim."
    assert report["summary"]["capcut_builtin_templates"] >= 4
    assert report["summary"]["capcut_preview_storyboards"] >= 10
    assert report["summary"]["publish_providers"] >= 6
    assert report["summary"]["quick_result_score"] >= 80
    assert report["summary"]["voice_workflow_score"] >= 85
    assert report["summary"]["voice_providers"] >= 8
    assert report["summary"]["prompt_edit_score"] >= 85
    assert report["summary"]["prompt_edit_cases"] >= 4
    assert report["summary"]["collab_handoff_score"] >= 85
    assert report["summary"]["collab_providers"] >= 8
    assert report["summary"]["cloud_handoff_score"] >= 85
    assert report["summary"]["cloud_handoff_providers"] >= 7
    assert report["summary"]["creator_assets"] >= 100
    assert report["summary"]["creator_asset_preview_storyboards"] >= report["summary"]["creator_assets"]
    assert report["summary"]["creator_asset_intents"] >= 12
    assert report["summary"]["creator_asset_collections"] >= 10
    assert report["summary"]["creator_asset_recommendations"] >= 6
    assert report["checks"]["publish_review_report_builds"] is True
    assert report["checks"]["quick_result_report_builds"] is True
    assert report["checks"]["voice_workflow_report_builds"] is True
    assert report["checks"]["prompt_edit_report_builds"] is True
    assert report["checks"]["collab_handoff_report_builds"] is True
    assert report["checks"]["cloud_handoff_report_builds"] is True
    assert any(row["id"] == "cloud_mobile_collaboration" and row["score"] < 90 for row in report["areas"])
    assert any(row["id"] == "stock_music_sfx" and row["score"] >= 80 for row in report["areas"])
    assert any(row["id"] == "ai_one_click_agent" and row["gap"] > 0 for row in report["areas"])

    out = tmp_path / "capcut_parity.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_parity_next.py", "--out", str(out)],
    )
    assert qa_capcut_parity_next.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["parity_ready"] is False


def test_capcut_parity_can_exclude_cloud_and_score_mobile_templates(tmp_path, monkeypatch):
    from app.capcut_mobile_templates import (
        capcut_creator_corpus_quality_report,
        capcut_mobile_template_parity_report,
        capcut_trend_template_catalog,
    )
    from app.capcut_parity import build_capcut_parity_next_report
    from tools import qa_capcut_parity_next

    trend = capcut_trend_template_catalog()
    corpus = capcut_creator_corpus_quality_report()
    assert trend["ok"] is True
    assert trend["summary"]["trend_pack_count"] >= 200
    assert trend["summary"]["trend_family_count"] >= 6
    assert trend["summary"]["storyboard_count"] == trend["summary"]["trend_pack_count"]
    assert corpus["ok"] is True
    assert corpus["summary"]["scenario_count"] >= 12
    assert corpus["summary"]["average_score"] >= 85

    mobile = capcut_mobile_template_parity_report(
        {"duration_s": 42, "screen_recording": True, "dialogue": True},
        [{"name": "tutorial screen capture.mp4", "tags": ["tutorial", "screen-recording"], "object_tags": ["cursor"]}],
    )
    assert mobile["ok"] is True
    assert mobile["score"] >= 90
    assert mobile["summary"]["template_count"] >= 100
    assert mobile["summary"]["category_count"] >= 12
    assert mobile["summary"]["safe_area_profiles"] >= 3
    assert mobile["summary"]["trend_template_packs"] >= 200
    assert mobile["summary"]["creator_corpus_average_score"] >= 85
    assert mobile["checks"]["no_cloud_dependency"] is True
    assert mobile["checks"]["trend_catalog_ready"] is True
    assert mobile["checks"]["creator_corpus_ready"] is True

    report = build_capcut_parity_next_report(exclude_cloud=True)
    assert report["ok"] is True
    assert report["scope"]["exclude_cloud"] is True
    assert report["summary"]["cloud_excluded"] is True
    assert report["summary"]["mobile_template_score"] >= 90
    assert report["summary"]["mobile_template_count"] >= 100
    assert report["summary"]["mobile_template_categories"] >= 12
    assert report["summary"]["mobile_safe_area_profiles"] >= 3
    assert report["summary"]["mobile_trend_template_packs"] >= 200
    assert report["summary"]["mobile_creator_corpus_score"] >= 85
    assert report["checks"]["cloud_scope_excluded"] is True
    assert report["checks"]["cloud_mobile_area_removed"] is True
    assert report["checks"]["mobile_trend_catalog_ready"] is True
    assert report["checks"]["mobile_creator_corpus_ready"] is True
    assert not any(row["id"] == "cloud_mobile_collaboration" for row in report["areas"])
    assert any(row["id"] == "mobile_template_scale" and row["score"] >= 90 for row in report["areas"])

    out = tmp_path / "capcut_parity_no_cloud.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_parity_next.py", "--exclude-cloud", "--out", str(out)],
    )
    assert qa_capcut_parity_next.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["scope"]["exclude_cloud"] is True
    assert written["summary"]["mobile_template_count"] >= 100


def test_creator_asset_pack_catalog_and_qa_tool(tmp_path, monkeypatch):
    from app.creator_asset_packs import (
        creator_asset_collection_shelves,
        creator_asset_pack_report,
        creator_asset_recommendation_board,
        search_creator_assets,
    )
    from tools import qa_creator_asset_packs

    report = creator_asset_pack_report()
    assert report["ok"] is True
    assert report["summary"]["assets"] >= 100
    assert report["summary"]["generated_extension_assets"] >= 40
    assert report["summary"]["preview_storyboards"] >= report["summary"]["assets"]
    assert report["summary"]["preview_ready_assets"] >= report["summary"]["assets"]
    assert report["summary"]["covered_intents"] >= 12
    assert report["summary"]["collection_shelves"] >= 10
    assert report["summary"]["ready_collection_shelves"] == report["summary"]["collection_shelves"]
    assert report["summary"]["recommendation_cards"] >= 6
    assert report["targets"]["sticker"]["ok"] is True
    assert report["targets"]["background"]["ok"] is True
    assert report["targets"]["sfx"]["ok"] is True
    assert report["targets"]["loop"]["ok"] is True
    assert report["intent_coverage"]["tutorial"]["ok"] is True
    assert report["intent_coverage"]["product"]["ok"] is True

    hits = search_creator_assets("capcut cursor click", kind="sfx")
    assert hits
    assert hits[0]["kind"] == "sfx"
    assert "license_id" in hits[0]
    review_hits = search_creator_assets("product review pro con", kind="sticker")
    assert review_hits
    assert review_hits[0]["id"] == "sticker-pro-con-toggle"
    beauty_hits = search_creator_assets("beauty fashion camera", kind="sfx")
    assert beauty_hits
    assert beauty_hits[0]["id"] == "sfx-camera-shutter"

    shelves = creator_asset_collection_shelves()
    assert len(shelves) >= 10
    assert all(shelf["ready"] for shelf in shelves)
    board = creator_asset_recommendation_board(
        {"screen_recording": True, "transcript_segments": [{"text": "clean product tutorial with cursor clicks"}]},
        [{"name": "product tutorial.mp4", "kind": "video", "tags": ["product", "tutorial"], "object_tags": ["cursor"]}],
    )
    assert board["ok"] is True
    assert board["card_count"] >= 6
    assert board["cards"][0]["drag_payload"]["type"] == "creator_asset_collection"

    out = tmp_path / "creator_assets.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_creator_asset_packs.py", "--out", str(out)],
    )
    assert qa_creator_asset_packs.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["assets"] >= 100


def test_capcut_prompt_edit_benchmark_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_prompt_edit import capcut_prompt_edit_benchmark_report, capcut_prompt_to_edit_plan
    from tools import qa_capcut_prompt_edit

    plan = capcut_prompt_to_edit_plan(
        "Make a product review short with captions, voice cleanup, thumbnail and Reels copy.",
        {
            "duration_s": 88,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [{"start_ms": 0, "end_ms": 4000, "text": "This is the best part."}],
        },
        [{"name": "product review.mp4", "kind": "video", "tags": ["product", "review"], "object_tags": ["product"]}],
    )
    assert plan["ok"] is True
    assert "caption_rows" in plan["operation_ids"]
    assert "voice_cleanup" in plan["operation_ids"]
    assert "publish_handoff" in plan["operation_ids"]
    assert plan["safe_apply"]["mode"] == "review_first"

    report = capcut_prompt_edit_benchmark_report()
    assert report["ok"] is True
    assert report["score"] >= 85
    assert report["summary"]["passing_cases"] >= 4
    assert report["summary"]["safe_apply_cases"] == report["summary"]["cases"]

    out = tmp_path / "prompt_edit.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_prompt_edit.py", "--out", str(out)],
    )
    assert qa_capcut_prompt_edit.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["matched_operations"] == written["summary"]["expected_operations"]


def test_capcut_publish_review_contract_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_publish import capcut_publish_manifest, capcut_publish_review_model, capcut_write_quick_upload_package, publish_provider_contracts
    from app.capcut_workflow import capcut_creator_apply_bundle
    from tools import qa_capcut_publish_review

    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 184,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the app keeps the important button in frame."},
            ],
        },
        [{"name": "screen demo.mp4", "kind": "video", "object_tags": ["cursor", "button"]}],
    )
    review = capcut_publish_review_model(bundle, export_paths=[tmp_path / "short.mp4"])
    providers = publish_provider_contracts()
    manifest = capcut_publish_manifest(bundle, export_paths=[tmp_path / "short.mp4"])
    package_result = capcut_write_quick_upload_package(bundle, tmp_path / "quick-upload", export_paths=[tmp_path / "short.mp4"])

    assert review["ready"] is True
    assert review["summary"]["copy_ready"] is True
    assert review["provider_count"] >= 12
    assert review["configured_provider_count"] >= 8
    assert review["ready_quick_upload_count"] >= 3
    assert review["api_upload_provider_count"] >= 3
    assert any(row["id"] == "quick_upload_tiktok" and row["configured"] is True for row in providers)
    assert any(row["id"] == "quick_upload_instagram" and row["configured"] is True for row in providers)
    assert any(row["id"] == "quick_upload_x" and row["configured"] is True for row in providers)
    assert all(not row["configured"] for row in providers if row["kind"] == "api_upload")
    assert any(row["id"] == "share_link_provider" and row["configured"] is False for row in providers)
    assert manifest["ready"] is True
    assert manifest["export_paths"] == [str(tmp_path / "short.mp4")]
    assert len(manifest["quick_uploads"]) >= 3
    assert package_result["ok"] is True
    assert package_result["upload_attempted"] is False
    assert package_result["file_count"] >= 10
    assert (tmp_path / "quick-upload" / "tiktok_post.txt").exists()
    assert (tmp_path / "quick-upload" / "instagram_post.txt").exists()
    assert (tmp_path / "quick-upload" / "x_post.txt").exists()
    panel = bundle["review_panel"]
    assert any(card["id"] == "publish_review" for card in panel["cards"])
    assert panel["counts"]["publish_providers"] >= 12

    out = tmp_path / "publish_review.json"
    package_dir = tmp_path / "qa-quick-upload"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_publish_review.py", "--out", str(out), "--package-dir", str(package_dir)],
    )
    assert qa_capcut_publish_review.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["provider_count"] >= 12
    assert written["summary"]["ready_quick_upload_count"] >= 3
    assert written["summary"]["quick_upload_package_written"] is True
    assert written["summary"]["quick_upload_package_file_count"] >= 10
    assert (package_dir / "package_index.json").exists()


def test_capcut_quick_result_contract_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_quick_result import capcut_one_click_quality_model, capcut_quick_result_model
    from app.capcut_workflow import capcut_creator_apply_bundle
    from tools import qa_capcut_quick_result

    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 184,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the first result look good."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the app keeps the important button in frame."},
                {"start_ms": 125000, "end_ms": 151000, "text": "The final export is already formatted for Shorts."},
            ],
        },
        [{"name": "screen demo.mp4", "kind": "video", "object_tags": ["cursor", "button"]}],
    )
    quick = capcut_quick_result_model(bundle)
    quality = capcut_one_click_quality_model(bundle)

    assert quick["ready"] is True
    assert quick["summary"]["template_exists"] is True
    assert quick["summary"]["ready_actions"] >= 4
    assert quick["summary"]["beginner_default_path_ready"] is True
    assert quick["summary"]["beginner_default_steps"] >= 5
    assert quick["summary"]["visible_feedback_count"] >= 4
    assert quality["score"] >= 80
    assert quality["checks"]["publish_review_ready"] is True
    assert any(card["id"] == "quick_result" for card in bundle["review_panel"]["cards"])
    assert bundle["review_panel"]["counts"]["quick_result_score"] >= 80

    out = tmp_path / "quick_result.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_quick_result.py", "--out", str(out)],
    )
    assert qa_capcut_quick_result.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["quality_score"] >= 80


def test_capcut_voice_workflow_contract_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_voice import capcut_voice_manifest, capcut_voice_workflow_model, voice_provider_contracts
    from app.capcut_workflow import capcut_creator_apply_bundle
    from tools import qa_capcut_voice_workflow

    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 184,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make captions feel polished."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Voice cleanup and captions should be reviewable together."},
                {"start_ms": 125000, "end_ms": 151000, "text": "Optional TTS stays disabled until configured."},
            ],
        },
        [{"name": "screen demo.mp4", "kind": "video", "object_tags": ["cursor", "button"]}],
    )
    workflow = capcut_voice_workflow_model(bundle, language="ko")
    manifest = capcut_voice_manifest(bundle, language="ko")
    providers = voice_provider_contracts()

    assert workflow["ready"] is True
    assert workflow["score"] >= 85
    assert workflow["summary"]["subtitle_rows"] >= 3
    assert workflow["summary"]["ready_card_count"] >= 4
    assert workflow["summary"]["enabled_action_count"] >= 4
    assert workflow["summary"]["manifest_operations"] >= 4
    assert workflow["provider_count"] >= 8
    assert workflow["configured_provider_count"] >= 5
    assert manifest["ready"] is True
    assert any(row["id"] == "system_tts_slot" and row["configured"] is False for row in providers)
    assert any(card["id"] == "voice_workflow" for card in bundle["review_panel"]["cards"])
    assert bundle["review_panel"]["counts"]["voice_workflow_score"] >= 85

    out = tmp_path / "voice_workflow.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_voice_workflow.py", "--out", str(out)],
    )
    assert qa_capcut_voice_workflow.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["provider_count"] >= 8


def test_capcut_collab_handoff_contract_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_collaboration import (
        capcut_collab_handoff_manifest,
        capcut_collab_provider_contracts,
        capcut_collab_review_model,
    )
    from app.capcut_workflow import capcut_creator_apply_bundle
    from tools import qa_capcut_collab_handoff

    media = [
        {
            "id": "screen-demo-1",
            "name": "screen demo.mp4",
            "path": "media/screen demo.mp4",
            "kind": "video",
            "duration_s": 184,
            "object_tags": ["cursor", "button"],
        }
    ]
    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 184,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make a shareable review."},
                {"start_ms": 64000, "end_ms": 84000, "text": "The handoff keeps media relink and review notes explicit."},
                {"start_ms": 125000, "end_ms": 151000, "text": "Cloud and mobile slots stay disabled until configured."},
            ],
        },
        media,
    )
    review = capcut_collab_review_model(bundle, media, search_roots=["media", "exports"])
    manifest = capcut_collab_handoff_manifest(bundle, media, search_roots=["media", "exports"])
    providers = capcut_collab_provider_contracts()

    assert review["ready"] is True
    assert review["score"] >= 85
    assert review["summary"]["media_count"] == 1
    assert review["provider_count"] >= 8
    assert review["configured_provider_count"] >= 5
    assert manifest["ready"] is True
    assert manifest["relink_manifest"]["media_count"] == 1
    assert any(row["id"] == "workspace_sync_slot" and row["configured"] is False for row in providers)
    assert any(card["id"] == "collab_handoff" for card in bundle["review_panel"]["cards"])
    assert bundle["review_panel"]["counts"]["collab_handoff_score"] >= 85

    out = tmp_path / "collab_handoff.json"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_collab_handoff.py", "--out", str(out)],
    )
    assert qa_capcut_collab_handoff.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["provider_count"] >= 8


def test_capcut_cloud_handoff_contract_and_qa_tool(tmp_path, monkeypatch):
    from app.capcut_cloud_handoff import (
        capcut_cloud_handoff_plan,
        capcut_cloud_handoff_report,
        capcut_cloud_provider_contracts,
        capcut_write_cloud_ready_package,
    )
    from app.capcut_collaboration import capcut_collab_handoff_manifest
    from app.capcut_workflow import capcut_creator_apply_bundle
    from tools import qa_capcut_cloud_handoff

    media = [{"id": "screen-demo-1", "name": "screen demo.mp4", "path": "media/screen demo.mp4", "kind": "video"}]
    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 184,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Make this review package shareable."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Keep upload and private links gated."},
            ],
        },
        media,
    )
    manifest = capcut_collab_handoff_manifest(bundle, media, search_roots=["media", "exports"])
    providers = capcut_cloud_provider_contracts()
    default_plan = capcut_cloud_handoff_plan(manifest)
    configured_plan = capcut_cloud_handoff_plan(
        manifest,
        configured_providers=["google_drive"],
        destinations={"google_drive": "TigerCapture Reviews"},
        user_consent=True,
    )
    report = capcut_cloud_handoff_report(manifest)
    package_result = capcut_write_cloud_ready_package(manifest, tmp_path / "cloud-package")

    assert any(row["id"] == "google_drive" and row["configured"] is False for row in providers)
    assert any(row["id"] == "microsoft_onedrive" for row in providers)
    assert any(row["id"] == "dropbox" for row in providers)
    assert any(row["id"] == "webdav" for row in providers)
    assert default_plan["safe_by_default"] is True
    assert default_plan["ready"] is False
    assert default_plan["privacy_gate"]["requires_user_consent"] is True
    assert default_plan["privacy_gate"]["private_link_default"] is True
    assert configured_plan["ready"] is True
    assert configured_plan["share_policy"]["link_ready"] is True
    assert configured_plan["privacy_gate"]["no_tokens_in_manifest"] is True
    assert report["ok"] is True
    assert report["score"] >= 90
    assert package_result["ok"] is True
    assert package_result["upload_attempted"] is False
    assert package_result["includes_original_media"] is False
    assert package_result["file_count"] >= 6
    assert (tmp_path / "cloud-package" / "manifest.json").exists()
    assert (tmp_path / "cloud-package" / "README.txt").read_text(encoding="utf-8").startswith("TigerCapture cloud-ready")

    out = tmp_path / "cloud_handoff.json"
    package_dir = tmp_path / "qa-cloud-package"
    monkeypatch.setattr(
        "sys.argv",
        ["qa_capcut_cloud_handoff.py", "--out", str(out), "--package-dir", str(package_dir)],
    )
    assert qa_capcut_cloud_handoff.main() == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["ok"] is True
    assert written["summary"]["provider_count"] >= 7
    assert written["summary"]["local_package_written"] is True
    assert written["summary"]["local_package_file_count"] >= 6
    assert (package_dir / "package_index.json").exists()


def test_creator_assist_panel_renders_current_editor_bundle():
    from PySide6.QtWidgets import QApplication

    from app.capcut_workflow import capcut_creator_apply_bundle
    from app.creator_assist_panel import CreatorAssistPanel

    QApplication.instance() or QApplication([])
    bundle = capcut_creator_apply_bundle(
        {
            "duration_s": 142,
            "has_audio": True,
            "dialogue": True,
            "screen_recording": True,
            "transcript_segments": [
                {"start_ms": 1500, "end_ms": 8000, "text": "How to make this clip look better fast"},
                {"start_ms": 41000, "end_ms": 52000, "text": "Best moment for a short export"},
            ],
        },
        [{"name": "capture tutorial.mp4", "kind": "video", "object_tags": ["cursor", "button"]}],
        target_count=2,
    )

    panel = CreatorAssistPanel()
    panel.set_bundle(bundle)

    assert panel.apply_btn.isEnabled()
    assert panel.quick_btn.isEnabled()
    assert panel.preview_btn.isEnabled()
    assert panel.queue_btn.isEnabled()
    assert panel.copy_btn.isEnabled()
    assert panel._cards.count() >= 7
    assert "쇼츠" in panel._summary.text()
    assert "빠른 제작" in panel._quick_flow.text()
    panel.set_busy(True, "빠른 제작 실행 중")
    assert "실행 중" in panel._run_status.text()
    panel.set_busy(False)
    panel.set_last_result({
        "subtitles": 2,
        "markers": 1,
        "settings": 1,
        "queued": 2,
        "storyboard_zoom_windows": 3,
        "storyboard_callouts": 2,
        "storyboard_templates": 1,
    })
    assert "마지막 결과" in panel._run_status.text()
    assert "큐 2" in panel._run_status.text()
    assert "템플릿 1" in panel._run_status.text()
    panel._option_checks["subtitles"].setChecked(False)
    assert panel.selected_apply_options()["subtitles"] is False
    panel.select_quick_create_options()
    assert all(panel.selected_apply_options().values())
    assert "쇼츠 마커" in panel._apply_preview.text()
    assert "샷카드" in panel._apply_preview.text()
    assert "템플릿" in panel._apply_preview.text()


def test_creator_assist_preview_uses_existing_global_marker_flow(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_CREATOR_ASSIST_ENABLED", "1")

    class Player:
        def __init__(self) -> None:
            self.position_ms = 0

        def set_position(self, ms: int) -> None:
            self.position_ms = int(ms)

    editor = SimpleNamespace(
        _creator_assist_bundle={
            "timeline_markers": [
                {"start_ms": 1200, "end_ms": 9800, "label": "Hook"},
            ],
        },
        _capcut_short_ranges=[],
        _player=Player(),
        _global_in_ms=-1,
        _global_out_ms=-1,
        _status="",
    )

    def set_global_in(ms: int) -> None:
        editor._global_in_ms = int(ms)

    def set_global_out(ms: int) -> None:
        editor._global_out_ms = int(ms)

    editor._set_global_in = set_global_in
    editor._set_global_out = set_global_out
    editor._update_time_label = lambda: None
    editor._flash_status = lambda text: setattr(editor, "_status", text)

    VideoEditorWindow._preview_creator_assist_short(editor)

    assert editor._global_in_ms == 1200
    assert editor._global_out_ms == 9800
    assert editor._player.position_ms == 1200
    assert "쇼츠 미리보기" in editor._status


def test_creator_assist_apply_respects_selected_options(monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED", "1")

    calls = []
    editor = SimpleNamespace(
        _creator_assist_bundle={
            "ok": True,
            "subtitle_rows": [{"text": "Caption"}],
            "timeline_markers": [{"start_ms": 100, "end_ms": 900}],
            "render_queue_jobs": [{"create_kwargs": {"label": "Short"}}],
            "project_settings_patch": {"canvas_height": 1920},
            "publish_package": {"ready": True},
            "edit_recipe": {"ready": True},
            "publish_variants": {"ready": True},
            "review_panel": {"ready": True},
            "publish_handoff": {"ready": True},
        },
        _creator_assist_panel=SimpleNamespace(
            selected_apply_options=lambda: {
                "subtitles": False,
                "markers": True,
                "settings": False,
                "queue_exports": False,
            }
        ),
        _player=SimpleNamespace(position=lambda: 0),
    )
    editor._analyze_creator_assist = lambda: editor._creator_assist_bundle
    editor._creator_assist_selected_options = lambda: {
        "subtitles": False,
        "markers": True,
        "settings": False,
        "queue_exports": False,
    }
    editor._apply_creator_assist_subtitles = lambda bundle, emit_changed=True: calls.append(("subtitles", emit_changed)) or 1
    editor._apply_creator_assist_markers = lambda bundle: calls.append(("markers", True)) or 1
    editor._apply_creator_assist_settings = lambda bundle: calls.append(("settings", True))
    editor._stage_creator_assist_render_jobs = lambda bundle: calls.append(("queue", True)) or {"added": 1, "skipped": 0}
    editor._update_subtitle_overlay = lambda pos: calls.append(("overlay", pos))
    editor._register_change = lambda label: calls.append(("undo", label))
    editor._flash_status = lambda text: setattr(editor, "_status", text)

    VideoEditorWindow._apply_creator_assist_bundle(editor)

    assert ("markers", True) in calls
    assert ("undo", "creator assist apply") in calls
    assert not any(row[0] == "subtitles" for row in calls)
    assert not any(row[0] == "settings" for row in calls)
    assert not any(row[0] == "queue" for row in calls)
    assert editor._capcut_short_ranges == [{"start_ms": 100, "end_ms": 900}]


def test_creator_assist_storyboard_effects_stage_zoom_and_callout_actors(tmp_path, monkeypatch):
    from app.ltx_storyboard import (
        build_ltx_storyboard_plan,
        storyboard_apply_payload,
        storyboard_effect_materialization_payload,
    )
    from app.timeline_model import VideoClip
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED", "1")

    summary = {
        "duration_s": 90,
        "screen_recording": True,
        "dialogue": True,
        "transcript_segments": [
            {"id": "seg_001", "start_ms": 0, "end_ms": 9000, "text": "Open the media pool."},
            {"id": "seg_002", "start_ms": 18000, "end_ms": 30000, "text": "Drag the clip onto the timeline."},
        ],
    }
    media = [{"id": "screen-001", "name": "screen tutorial.mp4", "kind": "video", "object_tags": ["cursor", "button"]}]
    plan = build_ltx_storyboard_plan("Storyboard this as screen tutorial shot cards.", summary, media)
    apply_payload = storyboard_apply_payload(plan)
    effects = storyboard_effect_materialization_payload(plan, apply_payload)
    clip = VideoClip(
        id=1,
        source_path=tmp_path / "missing.mp4",
        source_duration_ms=90000,
        timeline_in_ms=0,
        source_in_ms=0,
    )
    project_settings_seen = {}
    editor = SimpleNamespace(
        _project_settings={},
        _export_resolution=(1280, 720),
        _player=SimpleNamespace(set_project_settings=lambda settings: project_settings_seen.update(settings)),
        _track_rows={},
    )
    track = SimpleNamespace(id=1, typography_actors=[], zoom_actors=[])
    editor._screenstudio_polish_targets = lambda: [(track, clip)]
    editor._refresh_player_tracks = lambda: None
    editor._frame_size_for_storyboard_clip = lambda clip_arg: VideoEditorWindow._frame_size_for_storyboard_clip(editor, clip_arg)
    editor._storyboard_zoom_actor_for_clip = VideoEditorWindow._storyboard_zoom_actor_for_clip
    editor._sync_storyboard_zoom_visual_actors = (
        lambda track_arg, clip_arg, actors: VideoEditorWindow._sync_storyboard_zoom_visual_actors(
            editor,
            track_arg,
            clip_arg,
            actors,
        )
    )
    editor._stage_storyboard_callout_actors = (
        lambda track_arg, clip_arg, rows: VideoEditorWindow._stage_storyboard_callout_actors(
            editor,
            track_arg,
            clip_arg,
            rows,
        )
    )

    result = VideoEditorWindow._stage_creator_assist_storyboard_effects(
        editor,
        {"ltx_storyboard_effect_materialization": effects},
    )

    assert result["zoom_windows"] >= 1
    assert result["callouts"] >= 1
    assert clip.zoom_actors
    assert track.typography_actors
    assert track.zoom_actors
    assert all(
        getattr(actor, "ltx_storyboard_source", "") == "ltx_storyboard_callout"
        for actor in track.typography_actors
    )
    assert all(actor.is_configured() for actor in clip.zoom_actors)
    assert clip.screenstudio_polish["ltx_storyboard_auto_zoom_actor_ids"]
    assert clip.screenstudio_polish["ltx_storyboard_visual_zoom_actor_ids"]
    assert editor._project_settings["creator_assist"]["ltx_storyboard_effect_materialization"]["ready"] is True
    assert project_settings_seen["creator_assist"]["ltx_storyboard_effect_counts"]["zoom_windows"] >= 1

    second = VideoEditorWindow._stage_creator_assist_storyboard_effects(
        editor,
        {"ltx_storyboard_effect_materialization": effects},
    )

    assert second["callouts"] == result["callouts"]
    assert len(track.typography_actors) == result["callouts"]


def test_creator_assist_storyboard_templates_stage_real_workflow_presets(monkeypatch):
    from app.timeline_model import VideoClip
    from app.video_editor_window import VideoEditorWindow

    clip = VideoClip(id=7, source_duration_ms=60000, timeline_in_ms=0, source_in_ms=0)
    track = SimpleNamespace(id=3, clips=[clip])
    project_settings_seen = {}
    applied = []
    editor = SimpleNamespace(
        _project_settings={},
        _selected_clips=[],
        _active_track_id=None,
        _player=SimpleNamespace(set_project_settings=lambda settings: project_settings_seen.update(settings)),
    )
    editor._screenstudio_polish_targets = lambda: [(track, clip)]

    def fake_apply(preset, *, depth=0, at_ms=None):
        applied.append((
            preset.id,
            int(at_ms),
            int(getattr(editor, "_workflow_forced_track_id", -1)),
            list(getattr(editor, "_selected_clips", [])),
        ))
        return True

    editor._apply_editor_preset_object = fake_apply
    bundle = {
        "ltx_storyboard_effect_materialization": {
            "template_links": [
                {"template_id": "screenstudio-wallpaper", "start_ms": 1000, "shot_id": "shot_001"},
                {"template_id": "screenstudio-wallpaper", "start_ms": 1000, "shot_id": "shot_001_dup"},
                {"template_id": "missing-collection", "start_ms": 2000, "shot_id": "shot_missing"},
                {"template_id": "tutorial-click-polish", "start_ms": 3000, "shot_id": "shot_002"},
            ],
        }
    }

    result = VideoEditorWindow._stage_creator_assist_storyboard_templates(
        editor,
        bundle,
        targets=[(track, clip)],
    )

    assert result["applied"] == 2
    assert result["missing"] == 1
    assert result["skipped"] == 1
    assert [row[0] for row in applied] == [
        "template-screenstudio-wallpaper-demo",
        "template-screenstudio-click-to-cut",
    ]
    assert applied[0][1:] == (1000, 3, [(3, 7)])
    assert editor._selected_clips == []
    assert editor._project_settings["creator_assist"]["ltx_storyboard_applied_templates"]
    assert project_settings_seen["creator_assist"]["ltx_storyboard_applied_template_keys"]

    second = VideoEditorWindow._stage_creator_assist_storyboard_templates(
        editor,
        bundle,
        targets=[(track, clip)],
    )

    assert second["applied"] == 0
    assert len(applied) == 2


def test_creator_assist_queue_stages_jobs_directly(tmp_path, monkeypatch):
    from app.render_queue import RenderQueueStore
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_APPLY_BUNDLE_ENABLED", "1")

    class Panel:
        def __init__(self) -> None:
            self._store = RenderQueueStore(tmp_path / "render_queue.json")
            self.refresh_count = 0

        def refresh_from_store(self) -> None:
            self.refresh_count += 1

    panel = Panel()
    job_path = tmp_path / "short.mp4"
    editor = SimpleNamespace(
        _creator_assist_bundle={
            "render_queue_jobs": [
                {
                    "create_kwargs": {
                        "label": "Short candidate",
                        "out_path": str(job_path),
                        "in_ms": 1000,
                        "out_ms": 9000,
                        "project_path": "demo.tgp",
                        "source_path": "demo.mp4",
                        "format_id": "mp4",
                        "quality_id": "high",
                    }
                }
            ]
        },
        _capcut_render_queue_jobs=[],
        _render_queue_panel=panel,
        _render_queue_section_host=object(),
        _opened=False,
    )
    editor._analyze_creator_assist = lambda: editor._creator_assist_bundle
    editor._set_collapsible_host_open = lambda _host, opened: setattr(editor, "_opened", bool(opened))

    result = VideoEditorWindow._stage_creator_assist_render_jobs(editor)

    assert result["added"] == 1
    assert result["skipped"] == 0
    assert panel.refresh_count == 1
    assert editor._opened is True
    assert panel._store.jobs[0].label == "Short candidate"


def test_creator_assist_analysis_merges_local_ml_subject_detection(tmp_path, monkeypatch):
    from app.video_editor_window import VideoEditorWindow

    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_CREATOR_ASSIST_ENABLED", "1")
    monkeypatch.setenv("TIGERCAPTURE_CAPCUT_LOCAL_ML_ENABLED", "1")

    media = tmp_path / "screen_capture.mp4"
    media.write_bytes(b"placeholder")

    def fake_local_summary(path, *, include_transcript=False, sample_count=3):
        assert str(path) == str(media)
        return {
            "subject_detections": [
                {"t_ms": 0, "x_norm": 0.72, "y_norm": 0.42, "confidence": 0.9},
            ],
            "object_tags": ["foreground_region", "button"],
            "screen_recording": True,
            "media_items": [
                {
                    "name": media.name,
                    "path": str(media),
                    "kind": "video",
                    "object_tags": ["foreground_region", "button"],
                    "tags": ["screen-recording"],
                }
            ],
            "local_ml_analysis": {"ok": True, "cloud_enabled": False},
            "local_ml_backend_status": {"mode": "local", "api_required": False},
        }

    monkeypatch.setattr("app.local_ml.local_ml_capcut_project_summary", fake_local_summary)
    editor = SimpleNamespace(
        _creator_assist_bundle={},
        _creator_assist_panel=None,
    )
    editor._creator_assist_project_summary = lambda: {
        "duration_s": 120,
        "duration_ms": 120000,
        "has_audio": True,
        "dialogue": True,
        "transcript_segments": [
            {"start_ms": 1000, "end_ms": 7000, "text": "Watch this fast setup"},
        ],
        "media_items": [{"name": media.name, "path": str(media), "kind": "video"}],
        "source_path": str(media),
    }
    editor._creator_assist_local_media_path = lambda summary: str(media)
    editor._flash_status = lambda text: setattr(editor, "_status", text)

    bundle = VideoEditorWindow._analyze_creator_assist(editor)

    assert bundle["ok"] is True
    assert bundle["local_ml_analysis"]["ok"] is True
    assert bundle["local_ml_backend_status"]["mode"] == "local"
    assert bundle["project_settings_patch"]["capcut_creator_workflow"]["subject_reframe"]["mode"] == "subject_aware"
    assert any("foreground_region" in chip for chip in bundle["search_chips"])


def test_capcut_caption_short_quality_model_scores_ready_project():
    from app.capcut_workflow import capcut_caption_short_quality_model

    report = capcut_caption_short_quality_model(
        {
            "duration_s": 184,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make the result look good."},
                {"start_ms": 64000, "end_ms": 84000, "text": "Watch how the cursor stays inside the important frame."},
                {"start_ms": 125000, "end_ms": 151000, "text": "The final export is already ready for Shorts."},
            ],
        }
    )

    assert report["ok"] is True
    assert report["score"] == 100
    assert report["summary"]["caption_rows"] == 3
    assert report["summary"]["short_candidates"] == 3
