"""CapCut parity gap tracker.

This module is deliberately not a marketing claim.  It summarizes where
TigerCapture already has CapCut-like creator workflow scaffolding and where the
product still needs real UX, assets, integrations, or corpus validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CapCutParityArea:
    id: str
    label: str
    capcut_strength: str
    tiger_state: str
    target_score: int
    remaining: tuple[str, ...]
    next_actions: tuple[str, ...]


CAPCUT_PARITY_AREAS: tuple[CapCutParityArea, ...] = (
    CapCutParityArea(
        "template_ecosystem",
        "Template / preset ecosystem",
        "Large trend-driven template, transition, sticker, caption, music, and social packs.",
        "Built-in CapCut-style caption, title, transition, audio, reframe, and social publish presets exist, but the catalog is still small.",
        90,
        (
            "Trend-sized template volume is not comparable to CapCut yet.",
            "Preset previews need more true A/B result demonstrations.",
            "Template discovery still needs stronger category and intent browsing.",
        ),
        (
            "Add more short-form template packs by use case: tutorial, gameplay, product, reaction, meme, music, education.",
            "Add before/after preview storyboards for every high-level template.",
            "Track template usage and failed apply reasons in QA.",
        ),
    ),
    CapCutParityArea(
        "ai_one_click_agent",
        "AI one-click creator agent",
        "Creator-agent flows can turn media or product references into ready social videos.",
        "Deterministic creator planning, local-ML hooks, safe apply bundles, and review panels exist; generative planning remains optional and guarded.",
        90,
        (
            "Rule-based mode is reliable but not as broad as a generative creative agent.",
            "Local LLM/provider setup is optional, so the default must stay useful without it.",
            "One-click output quality needs more real creator corpus scoring.",
        ),
        (
            "Create a local-first prompt-to-edit benchmark with expected timeline operations.",
            "Add generated plan explainability and downgrade paths when no model is configured.",
            "Score one-click outputs for hook, caption readability, pacing, and export readiness.",
        ),
    ),
    CapCutParityArea(
        "captions_voice",
        "Captions / voice / cleanup",
        "Auto captions, caption templates, voice effects, TTS/custom voice, enhance voice, and noise reduction are first-class creator features.",
        "Auto-caption style contracts, subtitle rows, voice cleanup, loudness, and stem separation hooks exist; TTS/custom voice is not a finished product workflow.",
        90,
        (
            "TTS/custom voice and multilingual voice translation are not product-complete.",
            "Caption editing is improving but not as frictionless as mobile-first editors.",
            "Noise/enhance quality needs more real sample QA.",
        ),
        (
            "Add a caption/voice quick panel with language, style, voice cleanup, and export checks in one place.",
            "Add local TTS provider abstraction and unavailable-provider messaging.",
            "Expand Korean/English caption corpus validation.",
        ),
    ),
    CapCutParityArea(
        "social_publish_commerce",
        "Social publish / commerce handoff",
        "CapCut and its business tooling connect edits to social formats, copy, product assets, and publish handoff.",
        "Shorts/TikTok/Reels export plans, copy payloads, hashtags, thumbnail candidates, and render jobs are generated locally.",
        90,
        (
            "Direct platform publishing and commerce catalog integrations are not present.",
            "Per-platform compliance/status feedback is still a local checklist.",
            "Thumbnail, title, and copy variants need stronger UI review.",
        ),
        (
            "Build a publish package browser with title/caption/hashtag/thumbnail variants.",
            "Add provider slots for optional platform upload/share links.",
            "Add per-platform safe-zone and duration warnings in export.",
        ),
    ),
    CapCutParityArea(
        "cloud_mobile_collaboration",
        "Cloud / mobile / collaboration",
        "CapCut is strong because projects, assets, templates, and workflows travel across web/mobile/cloud.",
        "TigerCapture is local-first desktop software; this is intentional, but it is a CapCut parity gap.",
        90,
        (
            "No mobile editor, cloud project sync, workspace comments, or collaborative asset library.",
            "Share links are planned as provider slots, not a hosted product service.",
            "Template ecosystem is local/package based, not marketplace scale.",
        ),
        (
            "Keep local-first as a positioning advantage, but document cloud/mobile as out-of-scope until chosen.",
            "Add optional share-link provider contracts for exported packages.",
            "Add collaboration-safe project manifest and relink validation before any cloud work.",
        ),
    ),
    CapCutParityArea(
        "stock_music_sfx",
        "Stock media / music / SFX",
        "CapCut users get fast access to trendy music, sound effects, stickers, and stock-like creator assets.",
        "TigerCapture has presets and audio processing, but not a licensed stock/music/SFX ecosystem.",
        90,
        (
            "No built-in licensed music/SFX catalog.",
            "No trend-aware asset feed.",
            "Sticker and motion asset packs are still limited.",
        ),
        (
            "Add a local asset-pack format for stickers, SFX, loops, and backgrounds.",
            "Seed royalty-free starter packs with clear license metadata.",
            "Expose asset pack search beside Media Pool and presets.",
        ),
    ),
    CapCutParityArea(
        "beginner_default_result",
        "Beginner default result path",
        "CapCut feels good because basic imports quickly become captioned, vertical, polished exports.",
        "TigerCapture has richer editor identity, Media Pool, Workbench, actors, QA, and templates; the default path still needs to feel simpler.",
        90,
        (
            "Too many advanced surfaces can distract first-time creator workflows.",
            "The best default template needs stronger automatic selection.",
            "Empty states and preset-apply feedback still need polish.",
        ),
        (
            "Make the first imported screen recording show an obvious quick-result recommendation.",
            "Add persistent visual feedback when presets/AI bundles affect the timeline.",
            "Keep Media Pool and Workbench visible while reducing decision count.",
        ),
    ),
)


MOBILE_TEMPLATE_PARITY_AREA = CapCutParityArea(
    "mobile_template_scale",
    "Mobile templates / safe-zone exports",
    "CapCut feels mobile-native because vertical templates, captions, covers, and platform safe zones are ready by default.",
    "Tiger Studio now has a local-first mobile template catalog, platform safe zones, and deterministic short-form recommendations without cloud sync.",
    90,
    (
        "This covers local desktop export/template readiness, not a mobile app.",
        "Real creator corpus scoring still needs to confirm the templates feel good in use.",
        "More trend packs can be added without changing the cloud-excluded scope.",
    ),
    (
        "Use the mobile template catalog when recommending Shorts/TikTok/Reels edits.",
        "Add visual mobile safe-zone overlays in export and preset previews.",
        "Track template apply failures and real creator corpus outcomes by platform.",
    ),
)


def _default_project_summary() -> dict[str, Any]:
    return {
        "duration_s": 184,
        "shortform": False,
        "screen_recording": True,
        "has_audio": True,
        "dialogue": True,
        "transcript_segments": [
            {"start_ms": 8000, "end_ms": 22000, "text": "Here is the fastest way to make a polished demo."},
            {"start_ms": 64000, "end_ms": 84000, "text": "Keep the important button in frame."},
            {"start_ms": 125000, "end_ms": 151000, "text": "Export the result for Shorts."},
        ],
    }


def _default_media_items() -> list[dict[str, Any]]:
    return [
        {
            "id": "screen-demo",
            "name": "screen demo recording.mp4",
            "kind": "video",
            "duration_s": 184,
            "object_tags": ["cursor", "button", "app"],
            "dialogue": ["Make this into a polished tutorial short."],
            "tags": ["screen-recording", "tutorial"],
        },
        {
            "id": "gameplay-short",
            "name": "gameplay highlight.mp4",
            "kind": "video",
            "duration_s": 42,
            "object_tags": ["character", "snow"],
            "dialogue": ["Watch this moment."],
            "tags": ["gameplay", "short-form"],
        },
    ]


def _safe_creator_report(project_summary: Mapping[str, Any] | None, media_items: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    try:
        from app.capcut_workflow import capcut_creator_workflow_report

        return capcut_creator_workflow_report(project_summary or _default_project_summary(), list(media_items or _default_media_items()))
    except Exception as exc:
        return {"ok": False, "score": 0, "error": str(exc), "summary": {}}


def _preset_inventory() -> dict[str, Any]:
    try:
        from app.preset_library import CAPCUT_CREATOR_WORKFLOW_PRESETS, preset_library_summary, preset_preview_storyboard

        summary = preset_library_summary()
        capcut_presets = list(CAPCUT_CREATOR_WORKFLOW_PRESETS)
        storyboards = [preset_preview_storyboard(preset) for preset in capcut_presets]
        return {
            "ok": True,
            "capcut_builtin_presets": len(capcut_presets),
            "capcut_builtin_templates": sum(1 for preset in capcut_presets if getattr(preset, "kind", "") == "template"),
            "capcut_tagged_presets": int((summary.get("tags") or {}).get("capcut", 0) or 0),
            "capcut_preview_storyboards": len(storyboards),
            "capcut_preview_bake_targets": sorted({
                str(target)
                for storyboard in storyboards
                for target in list(storyboard.get("bake_targets", []) or [])
            }),
            "total_presets": int(summary.get("total", 0) or 0),
            "by_kind": dict(summary.get("by_kind", {}) or {}),
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "capcut_builtin_presets": 0,
            "capcut_builtin_templates": 0,
            "capcut_tagged_presets": 0,
            "capcut_preview_storyboards": 0,
            "capcut_preview_bake_targets": [],
            "total_presets": 0,
            "by_kind": {},
        }


def _creator_asset_inventory() -> dict[str, Any]:
    try:
        from app.creator_asset_packs import creator_asset_pack_report

        return creator_asset_pack_report()
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "score": 0,
            "summary": {"assets": 0, "built_in_assets": 0},
            "by_kind": {},
        }


def _publish_review_inventory(creator_report: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from app.capcut_publish import capcut_publish_manifest, capcut_publish_review_model
        from app.capcut_workflow import capcut_creator_apply_bundle

        bundle = creator_report.get("apply_bundle") if isinstance(creator_report.get("apply_bundle"), dict) else {}
        evidence = creator_report.get("evidence") if isinstance(creator_report.get("evidence"), dict) else {}
        if not bundle:
            bundle = evidence.get("apply_bundle") if isinstance(evidence.get("apply_bundle"), dict) else {}
        if not bundle:
            bundle = capcut_creator_apply_bundle(_default_project_summary(), _default_media_items())
        review = capcut_publish_review_model(bundle)
        manifest = capcut_publish_manifest(bundle, export_paths=["exports/capcut_shorts/demo_short_01.mp4"])
        return {
            "ok": bool(review.get("ok") and manifest.get("ok")),
            "ready": bool(review.get("ready") and manifest.get("ready")),
            "score": 100 if bool(review.get("ready") and manifest.get("ready")) else 72,
            "summary": {
                **dict(review.get("summary", {}) or {}),
                "provider_count": int(review.get("provider_count", 0) or 0),
                "configured_provider_count": int(review.get("configured_provider_count", 0) or 0),
                "quick_upload_count": int(review.get("quick_upload_count", 0) or 0),
                "ready_quick_upload_count": int(review.get("ready_quick_upload_count", 0) or 0),
                "api_upload_provider_count": int(review.get("api_upload_provider_count", 0) or 0),
            },
            "review": review,
            "manifest": manifest,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _quick_result_inventory(creator_report: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from app.capcut_quick_result import capcut_one_click_quality_model, capcut_quick_result_model
        from app.capcut_workflow import capcut_creator_apply_bundle

        bundle = creator_report.get("apply_bundle") if isinstance(creator_report.get("apply_bundle"), dict) else {}
        if not bundle:
            bundle = capcut_creator_apply_bundle(_default_project_summary(), _default_media_items())
        quick = capcut_quick_result_model(bundle)
        quality = capcut_one_click_quality_model(bundle)
        return {
            "ok": bool(quick.get("ok") and quality.get("checks")),
            "ready": bool(quick.get("ready") and quality.get("score", 0) >= 80),
            "score": float(quality.get("score", 0) or 0),
            "summary": dict(quick.get("summary", {}) or {}),
            "quick_result": quick,
            "quality": quality,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _voice_workflow_inventory(creator_report: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from app.capcut_voice import capcut_voice_manifest, capcut_voice_workflow_model
        from app.capcut_workflow import capcut_creator_apply_bundle

        bundle = creator_report.get("apply_bundle") if isinstance(creator_report.get("apply_bundle"), dict) else {}
        if not bundle:
            bundle = capcut_creator_apply_bundle(_default_project_summary(), _default_media_items())
        workflow = capcut_voice_workflow_model(bundle)
        manifest = capcut_voice_manifest(bundle)
        return {
            "ok": bool(workflow.get("ok") and manifest.get("ok")),
            "ready": bool(workflow.get("ready") and workflow.get("score", 0) >= 85),
            "score": float(workflow.get("score", 0) or 0),
            "summary": {
                **dict(workflow.get("summary", {}) or {}),
                "provider_count": int(workflow.get("provider_count", 0) or 0),
                "configured_provider_count": int(workflow.get("configured_provider_count", 0) or 0),
            },
            "workflow": workflow,
            "manifest": manifest,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _prompt_edit_inventory() -> dict[str, Any]:
    try:
        from app.capcut_prompt_edit import capcut_prompt_edit_benchmark_report

        report = capcut_prompt_edit_benchmark_report()
        return {
            "ok": bool(report.get("ok")),
            "ready": bool(report.get("ok") and float(report.get("score", 0) or 0) >= 85),
            "score": float(report.get("score", 0) or 0),
            "summary": dict(report.get("summary", {}) or {}),
            "report": report,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _collab_handoff_inventory(creator_report: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from app.capcut_collaboration import capcut_collab_handoff_manifest, capcut_collab_review_model
        from app.capcut_workflow import capcut_creator_apply_bundle

        bundle = creator_report.get("apply_bundle") if isinstance(creator_report.get("apply_bundle"), dict) else {}
        if not bundle:
            bundle = capcut_creator_apply_bundle(_default_project_summary(), _default_media_items())
        review = capcut_collab_review_model(bundle, _default_media_items(), search_roots=["media", "exports"])
        manifest = capcut_collab_handoff_manifest(bundle, _default_media_items(), search_roots=["media", "exports"])
        return {
            "ok": bool(review.get("ok") and manifest.get("ok")),
            "ready": bool(review.get("ready") and review.get("score", 0) >= 85),
            "score": float(review.get("score", 0) or 0),
            "summary": {
                **dict(review.get("summary", {}) or {}),
                "provider_count": int(review.get("provider_count", 0) or 0),
                "configured_provider_count": int(review.get("configured_provider_count", 0) or 0),
            },
            "review": review,
            "manifest": manifest,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _cloud_handoff_inventory(collab_inventory: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from app.capcut_cloud_handoff import capcut_cloud_handoff_report

        manifest = collab_inventory.get("manifest") if isinstance(collab_inventory.get("manifest"), dict) else {}
        report = capcut_cloud_handoff_report(manifest)
        return {
            "ok": bool(report.get("ok")),
            "ready": bool(report.get("ok") and float(report.get("score", 0) or 0) >= 85),
            "score": float(report.get("score", 0) or 0),
            "summary": dict(report.get("summary", {}) or {}),
            "report": report,
        }
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _mobile_template_inventory(
    project_summary: Mapping[str, Any] | None,
    media_items: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    try:
        from app.capcut_mobile_templates import capcut_mobile_template_parity_report

        return capcut_mobile_template_parity_report(project_summary or _default_project_summary(), list(media_items or _default_media_items()))
    except Exception as exc:
        return {"ok": False, "ready": False, "score": 0, "error": str(exc), "summary": {}}


def _score_area(
    area_id: str,
    creator_report: Mapping[str, Any],
    inventory: Mapping[str, Any],
    asset_inventory: Mapping[str, Any],
    publish_inventory: Mapping[str, Any],
    quick_inventory: Mapping[str, Any],
    voice_inventory: Mapping[str, Any],
    prompt_inventory: Mapping[str, Any],
    collab_inventory: Mapping[str, Any],
    cloud_inventory: Mapping[str, Any],
    mobile_template_inventory: Mapping[str, Any] | None = None,
) -> int:
    summary = creator_report.get("summary", {}) if isinstance(creator_report.get("summary"), dict) else {}
    creator_score = float(creator_report.get("score", 0) or 0)
    capcut_presets = int(inventory.get("capcut_builtin_presets", 0) or 0)
    capcut_templates = int(inventory.get("capcut_builtin_templates", 0) or 0)
    tagged_presets = int(inventory.get("capcut_tagged_presets", 0) or 0)
    capcut_storyboards = int(inventory.get("capcut_preview_storyboards", 0) or 0)
    asset_summary = asset_inventory.get("summary", {}) if isinstance(asset_inventory.get("summary"), dict) else {}
    asset_count = int(asset_summary.get("assets", 0) or 0)
    asset_score = float(asset_inventory.get("score", 0) or 0)
    asset_storyboards = int(asset_summary.get("preview_storyboards", 0) or 0)
    covered_intents = int(asset_summary.get("covered_intents", 0) or 0)
    asset_collections = int(asset_summary.get("collection_shelves", 0) or 0)
    ready_asset_collections = int(asset_summary.get("ready_collection_shelves", 0) or 0)
    recommendation_cards = int(asset_summary.get("recommendation_cards", 0) or 0)
    asset_by_kind = asset_inventory.get("by_kind", {}) if isinstance(asset_inventory.get("by_kind"), dict) else {}
    publish_summary = publish_inventory.get("summary", {}) if isinstance(publish_inventory.get("summary"), dict) else {}
    quick_summary = quick_inventory.get("summary", {}) if isinstance(quick_inventory.get("summary"), dict) else {}
    quick_score = float(quick_inventory.get("score", 0) or quick_summary.get("quality_score", 0) or 0)
    voice_summary = voice_inventory.get("summary", {}) if isinstance(voice_inventory.get("summary"), dict) else {}
    voice_score = float(voice_inventory.get("score", 0) or 0)
    prompt_summary = prompt_inventory.get("summary", {}) if isinstance(prompt_inventory.get("summary"), dict) else {}
    prompt_score = float(prompt_inventory.get("score", 0) or 0)
    collab_summary = collab_inventory.get("summary", {}) if isinstance(collab_inventory.get("summary"), dict) else {}
    collab_score = float(collab_inventory.get("score", 0) or 0)
    cloud_summary = cloud_inventory.get("summary", {}) if isinstance(cloud_inventory.get("summary"), dict) else {}
    cloud_score = float(cloud_inventory.get("score", 0) or 0)
    mobile_inventory = mobile_template_inventory or {}
    mobile_summary = mobile_inventory.get("summary", {}) if isinstance(mobile_inventory.get("summary"), dict) else {}
    mobile_score = float(mobile_inventory.get("score", 0) or 0)
    trend_template_packs = int(mobile_summary.get("trend_template_packs", 0) or 0)
    trend_storyboards = int(mobile_summary.get("trend_storyboards", 0) or 0)
    creator_corpus_score = float(mobile_summary.get("creator_corpus_average_score", 0) or 0)

    if area_id == "template_ecosystem":
        score = 50 + min(18, capcut_presets) + min(10, capcut_templates * 2) + min(6, tagged_presets // 5) + min(4, asset_count // 8)
        if capcut_storyboards >= capcut_presets and capcut_presets:
            score += 3
        if asset_storyboards >= asset_count and asset_count:
            score += 2
        if int(mobile_summary.get("template_count", 0) or 0) >= 100:
            score += 4
        if int(mobile_summary.get("category_count", 0) or 0) >= 12:
            score += 3
        if mobile_score >= 90:
            score += 2
        if trend_template_packs >= 200:
            score += 3
        if trend_storyboards >= trend_template_packs and trend_template_packs:
            score += 2
        if creator_corpus_score >= 85:
            score += 2
        return min(94, score)
    if area_id == "ai_one_click_agent":
        score = 56
        if creator_score >= 85:
            score += 10
        if int(summary.get("review_panel_cards", 0) or 0) >= 4:
            score += 5
        if int(summary.get("materialized_render_queue_jobs", summary.get("applied_render_jobs", 0)) or 0) > 0:
            score += 4
        if quick_score >= 80:
            score += 6
        if prompt_score >= 85:
            score += 4
        if int(prompt_summary.get("passing_cases", 0) or 0) >= 4:
            score += 3
        return min(87, score)
    if area_id == "captions_voice":
        caption_rows = int(summary.get("subtitle_rows", summary.get("applied_subtitles", 0)) or 0)
        score = 58 + (8 if caption_rows else 0) + (6 if capcut_presets >= 6 else 0) + (4 if inventory.get("ok") else 0)
        if voice_score >= 85:
            score += 8
        if int(voice_summary.get("provider_count", 0) or 0) >= 8:
            score += 4
        if int(voice_summary.get("configured_provider_count", 0) or 0) >= 5:
            score += 3
        if int(voice_summary.get("ready_card_count", 0) or 0) >= 4:
            score += 2
        if int(voice_summary.get("enabled_action_count", 0) or 0) >= 4:
            score += 2
        if int(voice_summary.get("manifest_operations", 0) or 0) >= 4:
            score += 1
        if not bool(voice_summary.get("cloud_required", True)):
            score += 1
        return min(92, score)
    if area_id == "social_publish_commerce":
        score = 54
        if int(summary.get("publish_variants", 0) or 0) >= 3:
            score += 8
        if bool(summary.get("publish_handoff_ready")):
            score += 6
        if bool(summary.get("publish_package_ready")):
            score += 5
        if bool(publish_inventory.get("ready")):
            score += 8
        if int(publish_summary.get("provider_count", 0) or 0) >= 6:
            score += 4
        ready_quick_uploads = int(publish_summary.get("ready_quick_upload_count", publish_summary.get("ready_quick_uploads", 0)) or 0)
        api_upload_providers = int(publish_summary.get("api_upload_provider_count", publish_summary.get("api_upload_providers", 0)) or 0)
        if ready_quick_uploads >= 3:
            score += 4
        if api_upload_providers >= 3:
            score += 2
        if bool(publish_summary.get("quick_upload_package_ready")):
            score += 1
        return min(92, score)
    if area_id == "cloud_mobile_collaboration":
        score = 24
        if collab_score >= 85:
            score += 10
        if int(collab_summary.get("provider_count", 0) or 0) >= 8:
            score += 5
        if int(collab_summary.get("configured_provider_count", 0) or 0) >= 5:
            score += 4
        if bool(collab_summary.get("package_ready")):
            score += 5
        if int(collab_summary.get("network_provider_count", 1) or 0) == 0:
            score += 4
        if cloud_score >= 85:
            score += 6
        if int(cloud_summary.get("provider_count", 0) or 0) >= 7:
            score += 3
        if bool(cloud_summary.get("configured_dry_run_ready")):
            score += 3
        if bool(cloud_summary.get("default_safe_by_default")):
            score += 2
        if bool(cloud_summary.get("local_package_writer_contract_ready")):
            score += 4
        return min(68, score)
    if area_id == "mobile_template_scale":
        score = 46
        if mobile_score >= 90:
            score += 16
        if int(mobile_summary.get("template_count", 0) or 0) >= 100:
            score += 10
        if int(mobile_summary.get("category_count", 0) or 0) >= 12:
            score += 7
        if int(mobile_summary.get("platform_profiles", 0) or 0) >= 3:
            score += 7
        if int(mobile_summary.get("safe_area_profiles", 0) or 0) >= 3:
            score += 5
        if int(mobile_summary.get("ready_mobile_export_profiles", 0) or 0) >= 3:
            score += 4
        if int(mobile_summary.get("recommendation_count", 0) or 0) >= 5:
            score += 3
        if trend_template_packs >= 200:
            score += 4
        if int(mobile_summary.get("trend_family_count", 0) or 0) >= 6:
            score += 2
        if creator_corpus_score >= 85:
            score += 3
        return min(96, score)
    if area_id == "stock_music_sfx":
        score = 34
        if asset_score >= 90:
            score += 14
        if asset_count >= 18:
            score += 8
        if asset_count >= 40:
            score += 8
        if asset_count >= 60:
            score += 5
        if asset_count >= 80:
            score += 4
        if asset_count >= 100:
            score += 4
        if covered_intents >= 8:
            score += 4
        if covered_intents >= 12:
            score += 3
        if asset_storyboards >= asset_count and asset_count:
            score += 3
        if asset_collections >= 10 and ready_asset_collections >= asset_collections:
            score += 5
        if recommendation_cards >= 6:
            score += 4
        if int(asset_by_kind.get("sfx", 0) or 0) >= 24:
            score += 2
        if int(asset_by_kind.get("loop", 0) or 0) >= 20:
            score += 2
        if int(asset_by_kind.get("sticker", 0) or 0) >= 24:
            score += 1
        if int(asset_by_kind.get("background", 0) or 0) >= 24:
            score += 1
        return min(92, score)
    if area_id == "beginner_default_result":
        score = 54
        if bool(summary.get("quick_create_ready")):
            score += 7
        if int(summary.get("recommendation_steps", 0) or 0) >= 3:
            score += 5
        if capcut_templates >= 4:
            score += 4
        if bool(quick_inventory.get("ready")):
            score += 8
        if bool(quick_summary.get("template_exists")):
            score += 3
        if float(quick_summary.get("quality_score", quick_inventory.get("score", 0)) or 0) >= 90:
            score += 5
        if bool(quick_summary.get("beginner_default_path_ready")):
            score += 4
        if int(quick_summary.get("visible_feedback_count", 0) or 0) >= 4:
            score += 3
        if int(quick_summary.get("ready_actions", 0) or 0) >= 5:
            score += 2
        return min(94, score)
    return 50


def build_capcut_parity_next_report(
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
    *,
    exclude_cloud: bool = False,
) -> dict[str, Any]:
    """Build a deterministic CapCut parity gap report.

    ``ok`` means the tracker can run and exposes honest gaps.  It does not mean
    CapCut parity is complete; use ``parity_ready`` for that.
    """
    creator_report = _safe_creator_report(project_summary, media_items)
    inventory = _preset_inventory()
    asset_inventory = _creator_asset_inventory()
    publish_inventory = _publish_review_inventory(creator_report)
    quick_inventory = _quick_result_inventory(creator_report)
    voice_inventory = _voice_workflow_inventory(creator_report)
    prompt_inventory = _prompt_edit_inventory()
    collab_inventory = _collab_handoff_inventory(creator_report)
    cloud_inventory = (
        {
            "ok": True,
            "ready": False,
            "score": 0,
            "summary": {"excluded_by_scope": True, "provider_count": 0},
            "report": {"ok": True, "excluded_by_scope": True},
        }
        if exclude_cloud
        else _cloud_handoff_inventory(collab_inventory)
    )
    mobile_template_inventory = _mobile_template_inventory(project_summary, media_items)
    areas: list[dict[str, Any]] = []
    area_specs = list(CAPCUT_PARITY_AREAS)
    if exclude_cloud:
        area_specs = [area for area in area_specs if area.id != "cloud_mobile_collaboration"]
    area_specs.append(MOBILE_TEMPLATE_PARITY_AREA)
    for area in area_specs:
        score = _score_area(
            area.id,
            creator_report,
            inventory,
            asset_inventory,
            publish_inventory,
            quick_inventory,
            voice_inventory,
            prompt_inventory,
            collab_inventory,
            cloud_inventory,
            mobile_template_inventory,
        )
        areas.append({
            "id": area.id,
            "label": area.label,
            "score": score,
            "target_score": area.target_score,
            "gap": max(0, area.target_score - score),
            "ok": score >= area.target_score,
            "capcut_strength": area.capcut_strength,
            "tiger_state": area.tiger_state,
            "remaining": list(area.remaining),
            "next_actions": list(area.next_actions),
        })
    average = round(sum(int(area["score"]) for area in areas) / max(1, len(areas)), 2)
    largest_gaps = sorted(areas, key=lambda row: int(row.get("gap", 0) or 0), reverse=True)
    parity_ready = all(bool(row.get("ok")) for row in areas)
    checks = {
        "creator_workflow_report_builds": bool(creator_report.get("summary")),
        "preset_inventory_builds": bool(inventory.get("ok")),
        "creator_asset_pack_report_builds": bool(asset_inventory.get("ok")),
        "publish_review_report_builds": bool(publish_inventory.get("ok")),
        "quick_result_report_builds": bool(quick_inventory.get("ok")),
        "voice_workflow_report_builds": bool(voice_inventory.get("ok")),
        "prompt_edit_report_builds": bool(prompt_inventory.get("ok")),
        "collab_handoff_report_builds": bool(collab_inventory.get("ok")),
        "mobile_template_report_builds": bool(mobile_template_inventory.get("ok")),
        "mobile_template_catalog_large_enough": int((mobile_template_inventory.get("summary", {}) or {}).get("template_count", 0) or 0) >= 100,
        "mobile_safe_area_profiles_ready": int((mobile_template_inventory.get("summary", {}) or {}).get("safe_area_profiles", 0) or 0) >= 3,
        "mobile_trend_catalog_ready": int((mobile_template_inventory.get("summary", {}) or {}).get("trend_template_packs", 0) or 0) >= 200,
        "mobile_creator_corpus_ready": float((mobile_template_inventory.get("summary", {}) or {}).get("creator_corpus_average_score", 0) or 0) >= 85,
        "areas_cover_core_capcut_gaps": len(areas) >= 7,
        "does_not_claim_full_parity": not parity_ready,
    }
    if exclude_cloud:
        checks["cloud_scope_excluded"] = True
        checks["cloud_mobile_area_removed"] = not any(row["id"] == "cloud_mobile_collaboration" for row in areas)
    else:
        checks["cloud_handoff_report_builds"] = bool(cloud_inventory.get("ok"))
        checks["cloud_mobile_gap_explicit"] = any(
            row["id"] == "cloud_mobile_collaboration"
            and int(row["score"]) < int(row["target_score"])
            for row in areas
        )
    return {
        "kind": "capcut_parity_next",
        "ok": all(checks.values()),
        "score": average,
        "parity_ready": parity_ready,
        "release_ready": False,
        "scope": {
            "exclude_cloud": bool(exclude_cloud),
            "cloud_note": "Cloud/mobile sync is excluded by request; this scope scores local mobile exports and template scale." if exclude_cloud else "",
        },
        "summary": {
            "areas": len(areas),
            "average_score": average,
            "largest_gap": largest_gaps[0]["id"] if largest_gaps else "",
            "cloud_excluded": bool(exclude_cloud),
            "capcut_builtin_presets": int(inventory.get("capcut_builtin_presets", 0) or 0),
            "capcut_builtin_templates": int(inventory.get("capcut_builtin_templates", 0) or 0),
            "capcut_tagged_presets": int(inventory.get("capcut_tagged_presets", 0) or 0),
            "capcut_preview_storyboards": int(inventory.get("capcut_preview_storyboards", 0) or 0),
            "creator_assets": int((asset_inventory.get("summary", {}) or {}).get("assets", 0) or 0),
            "creator_asset_preview_storyboards": int((asset_inventory.get("summary", {}) or {}).get("preview_storyboards", 0) or 0),
            "creator_asset_intents": int((asset_inventory.get("summary", {}) or {}).get("covered_intents", 0) or 0),
            "creator_asset_collections": int((asset_inventory.get("summary", {}) or {}).get("collection_shelves", 0) or 0),
            "creator_asset_recommendations": int((asset_inventory.get("summary", {}) or {}).get("recommendation_cards", 0) or 0),
            "publish_providers": int((publish_inventory.get("summary", {}) or {}).get("provider_count", 0) or 0),
            "publish_quick_uploads": int((publish_inventory.get("summary", {}) or {}).get("ready_quick_upload_count", (publish_inventory.get("summary", {}) or {}).get("ready_quick_uploads", 0)) or 0),
            "publish_api_upload_slots": int((publish_inventory.get("summary", {}) or {}).get("api_upload_provider_count", (publish_inventory.get("summary", {}) or {}).get("api_upload_providers", 0)) or 0),
            "publish_quick_upload_package_ready": bool((publish_inventory.get("summary", {}) or {}).get("quick_upload_package_ready")),
            "quick_result_score": float(quick_inventory.get("score", 0) or 0),
            "voice_workflow_score": float(voice_inventory.get("score", 0) or 0),
            "voice_providers": int((voice_inventory.get("summary", {}) or {}).get("provider_count", 0) or 0),
            "prompt_edit_score": float(prompt_inventory.get("score", 0) or 0),
            "prompt_edit_cases": int((prompt_inventory.get("summary", {}) or {}).get("cases", 0) or 0),
            "collab_handoff_score": float(collab_inventory.get("score", 0) or 0),
            "collab_providers": int((collab_inventory.get("summary", {}) or {}).get("provider_count", 0) or 0),
            "cloud_handoff_score": float(cloud_inventory.get("score", 0) or 0),
            "cloud_handoff_providers": int((cloud_inventory.get("summary", {}) or {}).get("provider_count", 0) or 0),
            "cloud_package_writer_ready": bool((cloud_inventory.get("summary", {}) or {}).get("local_package_writer_contract_ready")),
            "mobile_template_score": float(mobile_template_inventory.get("score", 0) or 0),
            "mobile_template_count": int((mobile_template_inventory.get("summary", {}) or {}).get("template_count", 0) or 0),
            "mobile_template_categories": int((mobile_template_inventory.get("summary", {}) or {}).get("category_count", 0) or 0),
            "mobile_safe_area_profiles": int((mobile_template_inventory.get("summary", {}) or {}).get("safe_area_profiles", 0) or 0),
            "mobile_ready_templates": int((mobile_template_inventory.get("summary", {}) or {}).get("ready_templates", 0) or 0),
            "mobile_export_profiles": int((mobile_template_inventory.get("summary", {}) or {}).get("mobile_export_profiles", 0) or 0),
            "mobile_trend_template_packs": int((mobile_template_inventory.get("summary", {}) or {}).get("trend_template_packs", 0) or 0),
            "mobile_trend_families": int((mobile_template_inventory.get("summary", {}) or {}).get("trend_family_count", 0) or 0),
            "mobile_trend_storyboards": int((mobile_template_inventory.get("summary", {}) or {}).get("trend_storyboards", 0) or 0),
            "mobile_creator_corpus_scenarios": int((mobile_template_inventory.get("summary", {}) or {}).get("creator_corpus_scenarios", 0) or 0),
            "mobile_creator_corpus_score": float((mobile_template_inventory.get("summary", {}) or {}).get("creator_corpus_average_score", 0) or 0),
            "creator_workflow_score": creator_report.get("score", 0),
        },
        "checks": checks,
        "truth": (
            "This cloud-excluded CapCut report scores local mobile export and template scale, not cloud/mobile sync."
            if exclude_cloud
            else "This is a CapCut gap tracker, not a full parity claim."
        ),
        "areas": areas,
        "largest_gaps": largest_gaps[:5],
        "next_actions": [
            action
            for row in largest_gaps[:4]
            for action in list(row.get("next_actions", []) or [])[:2]
        ],
        "evidence": {
            "creator_workflow": {
                "ok": bool(creator_report.get("ok")),
                "score": creator_report.get("score", 0),
                "summary": creator_report.get("summary", {}),
            },
            "preset_inventory": inventory,
            "creator_asset_packs": asset_inventory,
            "publish_review": publish_inventory,
            "quick_result": quick_inventory,
            "voice_workflow": voice_inventory,
            "prompt_edit": prompt_inventory,
            "collab_handoff": collab_inventory,
            "cloud_handoff": cloud_inventory,
            "mobile_templates": mobile_template_inventory,
        },
    }
