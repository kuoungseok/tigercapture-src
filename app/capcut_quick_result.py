"""CapCut-style quick-result recommendation and quality gates."""
from __future__ import annotations

from typing import Any, Iterable, Mapping


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_preset_exists(preset_id: str) -> bool:
    try:
        from app.preset_library import preset_by_id

        return preset_by_id(preset_id) is not None
    except Exception:
        return False


def _bundle_from_input(
    bundle_or_summary: Mapping[str, Any] | None,
    media_items: Iterable[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    source = _as_dict(bundle_or_summary)
    if any(key in source for key in ("project_settings_patch", "subtitle_rows", "timeline_markers", "render_queue_jobs")):
        return dict(source)
    try:
        from app.capcut_workflow import capcut_creator_apply_bundle

        return capcut_creator_apply_bundle(source, list(media_items or _as_list(source.get("media_items"))))
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "summary": source,
            "subtitle_rows": [],
            "timeline_markers": [],
            "render_queue_jobs": [],
        }


def _recommend_template(summary: Mapping[str, Any], bundle: Mapping[str, Any]) -> dict[str, Any]:
    workflow_ids = [str(item) for item in _as_list(bundle.get("workflow_preset_ids")) if str(item).strip()]
    has_captions = bool(_as_list(bundle.get("subtitle_rows")) or summary.get("has_captions"))
    needs_shorts = bool(summary.get("needs_shorts") or float(summary.get("duration_s", 0) or 0) > 90)
    screen_recording = bool(summary.get("screen_recording") or summary.get("tutorial") or summary.get("howto"))
    subject_reframe = bool(_as_dict(bundle.get("project_settings_patch")).get("capcut_creator_workflow", {}).get("subject_reframe"))
    choices: list[tuple[str, str, str]] = []
    if needs_shorts:
        choices.append(("template-capcut-long-to-shorts", "Long recording to Shorts", "Project is long enough to need ranked short ranges."))
    if has_captions or summary.get("has_audio") or summary.get("dialogue"):
        choices.append(("template-capcut-auto-caption-shorts", "Captioned Shorts", "Audio/dialogue can become readable word-pop captions."))
    if screen_recording:
        choices.append(("template-screenstudio-capcut-click-short", "Screen recording short", "Screen recording benefits from cursor, click, and caption polish."))
    if subject_reframe:
        choices.append(("template-capcut-subject-reframe", "Subject reframe", "Subject-aware vertical output is available."))
    choices.append(("template-capcut-social-publish-kit", "Social publish kit", "Prepare copy, thumbnail, captions, and platform defaults."))
    for preset_id, label, reason in choices:
        if preset_id in workflow_ids or _safe_preset_exists(preset_id):
            return {
                "id": preset_id,
                "label": label,
                "reason": reason,
                "exists": _safe_preset_exists(preset_id),
            }
    return {
        "id": workflow_ids[0] if workflow_ids else "",
        "label": "Quick creator result",
        "reason": "Use the first available creator workflow preset.",
        "exists": bool(workflow_ids),
    }


def capcut_one_click_quality_model(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Score whether a one-click CapCut-style result is actually usable."""
    bundle = _bundle_from_input(bundle_or_summary, media_items)
    summary = _as_dict(bundle.get("summary") or bundle_or_summary)
    subtitles = _as_list(bundle.get("subtitle_rows"))
    markers = _as_list(bundle.get("timeline_markers"))
    jobs = _as_list(bundle.get("render_queue_jobs"))
    publish = _as_dict(bundle.get("publish_package"))
    review = _as_dict(bundle.get("review_panel"))
    handoff = _as_dict(bundle.get("publish_handoff"))
    recipe = _as_dict(bundle.get("edit_recipe"))
    caption_beats = _as_dict(bundle.get("caption_beat_plan"))
    hook_plan = _as_dict(bundle.get("hook_score_plan"))
    project_settings = _as_dict(bundle.get("project_settings_patch"))
    workflow = _as_dict(project_settings.get("capcut_creator_workflow"))
    try:
        from app.capcut_publish import capcut_publish_review_model

        publish_review = capcut_publish_review_model(bundle)
    except Exception:
        publish_review = {}

    checks = {
        "has_explained_recipe": int(recipe.get("step_count", 0) or 0) >= 5,
        "has_hook_or_short_range": bool(markers or _as_list(hook_plan.get("hooks"))),
        "caption_rows_ready": bool(subtitles),
        "caption_beats_ready": int(caption_beats.get("beat_count", 0) or 0) >= min(3, max(1, len(subtitles))),
        "vertical_export_ready": int(project_settings.get("canvas_height", 0) or 0) >= 1920,
        "reframe_defaults_ready": bool(workflow.get("subject_reframe")),
        "render_jobs_ready": bool(jobs),
        "publish_copy_ready": bool(_as_dict(handoff.get("clipboard_payloads")).get("title")),
        "publish_review_ready": bool(publish_review.get("ready") or publish.get("ready")),
        "safe_apply_review_ready": int(review.get("card_count", 0) or 0) >= 7,
    }
    scores = {
        "hook": 100 if checks["has_hook_or_short_range"] else 45,
        "caption": 100 if checks["caption_rows_ready"] and checks["caption_beats_ready"] else (70 if checks["caption_rows_ready"] else 35),
        "pacing": 100 if markers and jobs else (75 if markers else 45),
        "format": 100 if checks["vertical_export_ready"] else 55,
        "delivery": 100 if checks["publish_copy_ready"] and checks["publish_review_ready"] else 60,
        "safety": 100 if checks["safe_apply_review_ready"] and checks["has_explained_recipe"] else 65,
    }
    score = round(sum(scores.values()) / max(1, len(scores)), 2)
    return {
        "ok": all(checks.values()),
        "score": score,
        "checks": checks,
        "scores": scores,
        "summary": {
            "subtitle_rows": len(subtitles),
            "short_ranges": len(markers),
            "render_jobs": len(jobs),
            "recipe_steps": int(recipe.get("step_count", 0) or 0),
            "review_cards": int(review.get("card_count", 0) or 0),
            "publish_ready": bool(publish.get("ready")),
        },
        "next_actions": [] if all(checks.values()) else [
            "Add transcript/caption rows before one-click export.",
            "Generate short ranges and render jobs before treating the result as ready.",
            "Review publish copy and thumbnail before export handoff.",
        ],
    }


def capcut_quick_result_model(
    bundle_or_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the first-result recommendation shown to creator workflows."""
    bundle = _bundle_from_input(bundle_or_summary, media_items)
    summary = _as_dict(bundle.get("summary") or bundle_or_summary)
    quality = capcut_one_click_quality_model(bundle)
    recommendation = _recommend_template(summary, bundle)
    subtitles = _as_list(bundle.get("subtitle_rows"))
    markers = _as_list(bundle.get("timeline_markers"))
    jobs = _as_list(bundle.get("render_queue_jobs"))
    project_settings = _as_dict(bundle.get("project_settings_patch"))
    review = _as_dict(bundle.get("review_panel"))
    publish_handoff = _as_dict(bundle.get("publish_handoff"))
    beginner_rows = [
        {
            "id": "template",
            "label": "Pick the first polished template",
            "ready": bool(recommendation.get("id") and recommendation.get("exists")),
            "value": recommendation.get("label", ""),
        },
        {
            "id": "captions",
            "label": "Add readable captions",
            "ready": bool(subtitles),
            "count": len(subtitles),
        },
        {
            "id": "pacing",
            "label": "Mark the best short range",
            "ready": bool(markers),
            "count": len(markers),
        },
        {
            "id": "vertical_format",
            "label": "Prepare vertical export",
            "ready": int(project_settings.get("canvas_width", 0) or 0) == 1080
            and int(project_settings.get("canvas_height", 0) or 0) >= 1920,
            "value": f"{project_settings.get('canvas_width', 0)}x{project_settings.get('canvas_height', 0)}",
        },
        {
            "id": "publish_package",
            "label": "Prepare title, copy, and export jobs",
            "ready": bool(jobs) and bool(_as_dict(publish_handoff.get("clipboard_payloads")).get("title")),
            "count": len(jobs),
        },
    ]
    visible_feedback = [
        {"id": "template_badge", "label": "Template badge", "ready": bool(recommendation.get("id"))},
        {"id": "timeline_markers", "label": "Timeline marker chips", "ready": bool(markers), "count": len(markers)},
        {"id": "caption_rows", "label": "Caption rows", "ready": bool(subtitles), "count": len(subtitles)},
        {"id": "render_queue_jobs", "label": "Render queue job badges", "ready": bool(jobs), "count": len(jobs)},
        {"id": "review_cards", "label": "Review cards", "ready": int(review.get("card_count", 0) or 0) >= 7, "count": int(review.get("card_count", 0) or 0)},
    ]
    beginner_default_ready = all(bool(row.get("ready")) for row in beginner_rows)
    visible_feedback_count = sum(1 for row in visible_feedback if row.get("ready"))
    cards = [
        {
            "id": "recommended_template",
            "label": "Recommended template",
            "ready": bool(recommendation.get("id") and recommendation.get("exists")),
            "value": recommendation,
        },
        {
            "id": "what_will_happen",
            "label": "What will happen",
            "ready": bool(subtitles or markers or jobs),
            "rows": [
                {"id": "captions", "label": "Apply captions", "ready": bool(subtitles), "count": len(subtitles)},
                {"id": "shorts", "label": "Mark short ranges", "ready": bool(markers), "count": len(markers)},
                {"id": "exports", "label": "Queue social exports", "ready": bool(jobs), "count": len(jobs)},
            ],
        },
        {
            "id": "beginner_default_path",
            "label": "Beginner default path",
            "ready": beginner_default_ready,
            "rows": beginner_rows,
        },
        {
            "id": "quality",
            "label": "One-click quality",
            "ready": bool(quality.get("ok")),
            "score": quality.get("score", 0),
            "rows": [
                {"id": key, "label": key.replace("_", " ").title(), "ready": bool(value)}
                for key, value in _as_dict(quality.get("checks")).items()
            ],
        },
    ]
    actions = [
        {"id": "quick_create", "label": "Quick Create", "enabled": bool(bundle.get("ok"))},
        {"id": "apply_best_defaults", "label": "Apply best defaults", "enabled": beginner_default_ready},
        {"id": "preview_best_short", "label": "Preview best short", "enabled": bool(markers), "ms": int(_as_dict(markers[0] if markers else {}).get("start_ms", 0) or 0)},
        {"id": "queue_exports", "label": "Queue exports", "enabled": bool(jobs), "count": len(jobs)},
        {"id": "copy_publish_copy", "label": "Copy publish copy", "enabled": bool(_as_dict(_as_dict(bundle.get("publish_handoff")).get("clipboard_payloads")).get("title"))},
    ]
    ready = bool(bundle.get("ok") and quality.get("score", 0) >= 80 and recommendation.get("id"))
    return {
        "ok": True,
        "ready": ready,
        "score": quality.get("score", 0),
        "recommendation": recommendation,
        "cards": cards,
        "card_count": len(cards),
        "actions": actions,
        "quality": quality,
        "summary": {
            "template_id": recommendation.get("id", ""),
            "template_exists": bool(recommendation.get("exists")),
            "subtitle_rows": len(subtitles),
            "short_ranges": len(markers),
            "render_jobs": len(jobs),
            "quality_score": quality.get("score", 0),
            "ready_actions": sum(1 for action in actions if action.get("enabled")),
            "beginner_default_path_ready": beginner_default_ready,
            "beginner_default_steps": len(beginner_rows),
            "visible_feedback_count": visible_feedback_count,
        },
        "visible_feedback": visible_feedback,
    }
