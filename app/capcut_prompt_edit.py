"""Local-first prompt-to-edit planning for CapCut-style creator workflows.

This is not a generative editor.  It is the deterministic safety layer that
keeps prompt editing useful when no local LLM is configured and gives provider
plans a benchmarkable contract when one is available later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class PromptEditBenchmarkCase:
    id: str
    prompt: str
    project_summary: Mapping[str, Any]
    media_items: tuple[Mapping[str, Any], ...]
    expected_operations: tuple[str, ...]


PROMPT_EDIT_BENCHMARK_CASES: tuple[PromptEditBenchmarkCase, ...] = (
    PromptEditBenchmarkCase(
        "screen_tutorial_short",
        "Make this screen recording into a polished vertical tutorial with captions, cursor emphasis, and Shorts export.",
        {
            "duration_s": 188,
            "screen_recording": True,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 4000, "end_ms": 18000, "text": "Here is the fastest way to export."},
                {"start_ms": 72000, "end_ms": 94000, "text": "Click the button and keep it in frame."},
            ],
        },
        (
            {
                "name": "screen tutorial.mp4",
                "kind": "video",
                "tags": ["tutorial", "screen-recording"],
                "object_tags": ["cursor", "button"],
            },
        ),
        ("caption_rows", "subject_reframe", "cursor_polish", "short_exports", "publish_handoff"),
    ),
    PromptEditBenchmarkCase(
        "product_review",
        "Create a clean product review clip with pro/con labels, voice cleanup, thumbnail, and TikTok/Reels copies.",
        {
            "duration_s": 96,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 1000, "end_ms": 16000, "text": "This is the part I liked most."},
                {"start_ms": 24000, "end_ms": 45000, "text": "Here are the tradeoffs."},
            ],
        },
        (
            {
                "name": "product review.mp4",
                "kind": "video",
                "tags": ["product", "review"],
                "object_tags": ["product", "hands"],
                "dialogue": ["liked most", "tradeoffs"],
            },
        ),
        ("caption_rows", "voice_cleanup", "asset_recommendations", "publish_handoff", "thumbnail_candidate"),
    ),
    PromptEditBenchmarkCase(
        "gameplay_highlight",
        "Turn this gameplay capture into a high-energy meme highlight with reaction assets, fast cuts, and a vertical export.",
        {
            "duration_s": 52,
            "screen_recording": False,
            "has_audio": True,
            "dialogue": False,
            "transcript_segments": [],
        },
        (
            {
                "name": "snow gameplay highlight.mp4",
                "kind": "video",
                "tags": ["gameplay", "meme"],
                "object_tags": ["character", "snow"],
            },
        ),
        ("subject_reframe", "asset_recommendations", "short_exports", "motion_pacing"),
    ),
    PromptEditBenchmarkCase(
        "podcast_chapter",
        "Cut the long podcast into chaptered clips, keep dialogue clean, add captions, and prepare review notes.",
        {
            "duration_s": 1240,
            "has_audio": True,
            "dialogue": True,
            "transcript_segments": [
                {"start_ms": 10000, "end_ms": 42000, "text": "Today we start with setup."},
                {"start_ms": 420000, "end_ms": 462000, "text": "The second lesson is pacing."},
                {"start_ms": 860000, "end_ms": 910000, "text": "Here is the final checklist."},
            ],
        },
        (
            {
                "name": "podcast episode.wav",
                "kind": "audio",
                "tags": ["podcast", "dialogue"],
                "dialogue": ["setup", "pacing", "checklist"],
            },
        ),
        ("caption_rows", "voice_cleanup", "chapter_markers", "collab_handoff", "short_exports"),
    ),
)


def _text_blob(prompt: str, project_summary: Mapping[str, Any], media_items: Iterable[Mapping[str, Any]]) -> str:
    parts = [str(prompt or "")]
    for value in project_summary.values():
        if isinstance(value, (str, int, float, bool)):
            parts.append(str(value))
    for segment in project_summary.get("transcript_segments", []) or []:
        if isinstance(segment, Mapping):
            parts.append(str(segment.get("text") or ""))
    for item in media_items:
        if not isinstance(item, Mapping):
            continue
        for key in ("name", "kind"):
            parts.append(str(item.get(key) or ""))
        for key in ("tags", "object_tags", "dialogue"):
            values = item.get(key, [])
            if isinstance(values, (list, tuple, set)):
                parts.extend(str(value) for value in values)
            elif values:
                parts.append(str(values))
    return " ".join(parts).casefold()


def capcut_prompt_to_edit_plan(
    prompt: str,
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    from app.capcut_workflow import capcut_creator_apply_bundle
    from app.creator_asset_packs import creator_asset_recommendation_board

    project = dict(project_summary or {})
    media = [dict(item) for item in media_items if isinstance(item, Mapping)]
    bundle = capcut_creator_apply_bundle(project, media, include_review_panel=False)
    workflow_patch = {}
    project_settings_patch = bundle.get("project_settings_patch") if isinstance(bundle.get("project_settings_patch"), Mapping) else {}
    if isinstance(project_settings_patch.get("capcut_creator_workflow"), Mapping):
        workflow_patch = dict(project_settings_patch.get("capcut_creator_workflow") or {})
    text = _text_blob(prompt, project, media)
    transcript_count = len(project.get("transcript_segments", []) or [])
    duration_s = float(project.get("duration_s", 0) or 0)
    operations: list[dict[str, Any]] = []

    def add_operation(operation_id: str, label: str, ready: bool, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        operations.append({
            "id": operation_id,
            "label": label,
            "ready": bool(ready),
            "reason": reason,
            "payload": dict(payload or {}),
        })

    wants_caption = any(token in text for token in ("caption", "subtitle", "자막", "words", "word"))
    if wants_caption or transcript_count:
        add_operation(
            "caption_rows",
            "Caption rows",
            bool(bundle.get("subtitle_rows")),
            "transcript_or_caption_prompt",
            {"rows": len(bundle.get("subtitle_rows", []) or [])},
        )

    wants_vertical = any(token in text for token in ("short", "shorts", "tiktok", "reels", "vertical", "세로"))
    wants_subject = wants_vertical or any(token in text for token in ("frame", "subject", "keep", "center", "인물"))
    if wants_subject:
        reframe_payload = workflow_patch.get("subject_reframe") if isinstance(workflow_patch.get("subject_reframe"), Mapping) else {}
        add_operation(
            "subject_reframe",
            "Subject reframe",
            bool(reframe_payload.get("ok")),
            "vertical_or_subject_prompt",
            reframe_payload,
        )

    if any(token in text for token in ("cursor", "click", "button", "screen recording", "screen-recording", "tutorial")):
        add_operation(
            "cursor_polish",
            "Cursor polish",
            True,
            "screen_tutorial_prompt",
            {"emphasis": "click_ripple", "auto_zoom_bias": "cursor_or_button"},
        )

    if any(token in text for token in ("voice", "dialogue", "podcast", "noise", "cleanup", "보이스", "대화")) or bool(project.get("dialogue")):
        add_operation(
            "voice_cleanup",
            "Voice cleanup",
            True,
            "dialogue_or_voice_prompt",
            {"normalize_lufs": -16.0, "dialogue_cleanup": "moderate"},
        )

    if any(token in text for token in ("product", "review", "meme", "gameplay", "beauty", "fitness", "asset", "sticker")):
        board = creator_asset_recommendation_board(project, media)
        add_operation(
            "asset_recommendations",
            "Asset recommendations",
            bool(board.get("ok")),
            "creator_asset_prompt",
            {"primary_collection_id": board.get("primary_collection_id", ""), "cards": int(board.get("card_count", 0) or 0)},
        )

    if duration_s > 180 or any(token in text for token in ("chapter", "podcast", "long", "episode")):
        add_operation(
            "chapter_markers",
            "Chapter markers",
            bool(bundle.get("timeline_markers")),
            "longform_or_chapter_prompt",
            {"markers": len(bundle.get("timeline_markers", []) or [])},
        )

    if any(token in text for token in ("fast", "energy", "highlight", "meme", "cut")):
        add_operation(
            "motion_pacing",
            "Motion pacing",
            True,
            "pacing_prompt",
            {"cut_density": "medium_fast", "beat_sync": True},
        )

    if wants_vertical or duration_s > 45 or any(token in text for token in ("export", "publish", "tiktok", "reels", "shorts")):
        add_operation(
            "short_exports",
            "Short exports",
            bool(bundle.get("render_queue_jobs")),
            "publish_or_short_prompt",
            {"jobs": len(bundle.get("render_queue_jobs", []) or [])},
        )

    if any(token in text for token in ("thumbnail", "cover", "publish", "tiktok", "reels", "shorts")):
        publish_package = bundle.get("publish_package") if isinstance(bundle.get("publish_package"), Mapping) else {}
        add_operation(
            "thumbnail_candidate",
            "Thumbnail candidate",
            bool(publish_package.get("thumbnail_frames")),
            "publish_thumbnail_prompt",
            {"frames": len(publish_package.get("thumbnail_frames", []) or [])},
        )

    if any(token in text for token in ("publish", "tiktok", "reels", "shorts", "copy", "hashtag")):
        handoff = bundle.get("publish_handoff") if isinstance(bundle.get("publish_handoff"), Mapping) else {}
        add_operation(
            "publish_handoff",
            "Publish handoff",
            bool(handoff.get("ready")),
            "social_publish_prompt",
            {"actions": len(handoff.get("actions", []) or [])},
        )

    if any(token in text for token in ("review notes", "review", "handoff", "collab", "share")):
        add_operation(
            "collab_handoff",
            "Collab handoff",
            True,
            "review_or_handoff_prompt",
            {"local_first": True, "cloud_required": False},
        )

    ready_count = sum(1 for row in operations if row.get("ready"))
    return {
        "kind": "capcut_prompt_to_edit_plan",
        "ok": bool(operations) and ready_count == len(operations),
        "prompt": str(prompt or ""),
        "operation_count": len(operations),
        "ready_operation_count": ready_count,
        "operations": operations,
        "operation_ids": [str(row.get("id") or "") for row in operations],
        "explainability": [
            {"operation_id": row["id"], "reason": row["reason"], "ready": bool(row["ready"])}
            for row in operations
        ],
        "safe_apply": {
            "mode": "review_first",
            "destructive": False,
            "requires_user_confirmation": True,
        },
    }


def capcut_prompt_edit_benchmark_report() -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    total_expected = 0
    total_matched = 0
    for case in PROMPT_EDIT_BENCHMARK_CASES:
        plan = capcut_prompt_to_edit_plan(case.prompt, case.project_summary, case.media_items)
        actual = set(plan.get("operation_ids", []) or [])
        expected = set(case.expected_operations)
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        matched = len(expected & actual)
        total_expected += len(expected)
        total_matched += matched
        cases.append({
            "id": case.id,
            "prompt": case.prompt,
            "ok": not missing and bool(plan.get("ok")),
            "expected_operations": sorted(expected),
            "actual_operations": sorted(actual),
            "missing": missing,
            "extra": extra,
            "matched": matched,
            "expected_count": len(expected),
            "plan": plan,
        })
    score = round(100.0 * total_matched / max(1, total_expected), 2)
    return {
        "kind": "capcut_prompt_edit_benchmark",
        "ok": all(bool(case.get("ok")) for case in cases),
        "score": score,
        "summary": {
            "cases": len(cases),
            "passing_cases": sum(1 for case in cases if case.get("ok")),
            "expected_operations": total_expected,
            "matched_operations": total_matched,
            "safe_apply_cases": sum(1 for case in cases if (case.get("plan", {}).get("safe_apply") or {}).get("mode") == "review_first"),
        },
        "cases": cases,
    }
