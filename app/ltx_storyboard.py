"""LTX-style storyboard and shot-card planning.

This module keeps the feature local-first and deterministic.  It does not call
LTX, download models, or mutate a project.  It gives Tiger Studio a product
surface inspired by LTX Studio: prompt -> shot cards -> reviewable timeline
operations.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
import os
import re
from typing import Any

from app.ai_edit_plan import (
    EditOperation,
    EditPlan,
    ReviewCard,
    normalize_operations,
    stable_json_dumps,
)


LTX_STORYBOARD_SCHEMA_VERSION = 1
LTX_STORYBOARD_CLAIM_LEVEL = "ltx_inspired_local_shot_cards_not_ltx_cloud_parity"
STORYBOARD_PROMPT_TOKENS = (
    "storyboard",
    "shot card",
    "shot cards",
    "shot plan",
    "scene plan",
    "camera plan",
    "retake",
    "variation",
    "ltx",
    "스토리보드",
    "콘티",
    "샷",
    "장면",
    "카메라",
    "리테이크",
    "변형",
)
_EDIT_PLAN_FORBIDDEN_KEYS = {
    "code",
    "command",
    "commands",
    "exec",
    "eval",
    "function",
    "mutation",
    "project_mutation",
    "python",
    "script",
    "shell",
    "subprocess",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return list(value)
    return []


def _int_ms(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(round(float(value))))
    except Exception:
        return max(0, int(fallback))


def _slug(value: str, fallback: str = "shot") -> str:
    text = re.sub(r"[^0-9A-Za-z가-힣]+", "_", str(value or "").strip()).strip("_").casefold()
    return text[:48] or fallback


def _edit_plan_safe_payload(value: Any) -> Any:
    """Rename keys that the AI EditPlan safety gate forbids everywhere."""
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for raw_key, child in value.items():
            key = str(raw_key)
            safe_key = f"provider_{key}" if key.casefold() in _EDIT_PLAN_FORBIDDEN_KEYS else key
            safe[safe_key] = _edit_plan_safe_payload(child)
        return safe
    if isinstance(value, (list, tuple)):
        return [_edit_plan_safe_payload(item) for item in value]
    return value


def prompt_requests_storyboard(prompt: str) -> bool:
    """Return True when a natural-language request is asking for shot planning."""
    text = " ".join(str(prompt or "").casefold().split())
    if not text:
        return False
    return any(token.casefold() in text for token in STORYBOARD_PROMPT_TOKENS)


def _text_blob(prompt: str, project_summary: Mapping[str, Any], media_items: Iterable[Mapping[str, Any]]) -> str:
    parts: list[str] = [str(prompt or "")]
    for value in project_summary.values():
        if isinstance(value, (str, int, float, bool)):
            parts.append(str(value))
    for segment in _as_list(project_summary.get("transcript_segments")):
        row = _as_dict(segment)
        parts.append(str(row.get("text") or ""))
    for item in media_items:
        row = _as_dict(item)
        for key in ("id", "name", "kind", "path"):
            parts.append(str(row.get(key) or ""))
        for key in ("tags", "object_tags", "people", "dialogue"):
            value = row.get(key)
            if isinstance(value, (list, tuple, set)):
                parts.extend(str(entry) for entry in value)
            elif value:
                parts.append(str(value))
    return " ".join(parts).casefold()


def ltx_storyboard_provider_state(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return optional external-provider wiring without requiring it."""
    source = env if env is not None else os.environ
    endpoint = str(source.get("TIGERCAPTURE_LTX_STORYBOARD_ENDPOINT") or "").strip()
    command = str(source.get("TIGERCAPTURE_LTX_STORYBOARD_COMMAND") or "").strip()
    workflow = str(source.get("TIGERCAPTURE_LTX_STORYBOARD_WORKFLOW") or "").strip()
    configured = bool(endpoint or command or workflow)
    return {
        "id": "ltx_storyboard_provider",
        "configured": configured,
        "available": configured,
        "endpoint": endpoint,
        "command": command,
        "workflow": workflow,
        "mode": "external_provider_contract" if configured else "local_rule_based",
        "cloud_required": False,
        "notes": [
            "External LTX/ComfyUI/storyboard providers may fill richer shot cards later.",
            "Built-in mode stays local and deterministic.",
        ],
    }


@dataclass(frozen=True)
class ShotCard:
    id: str
    index: int
    title: str
    prompt: str
    start_ms: int
    duration_ms: int
    shot_type: str
    camera_angle: str
    camera_motion: str
    subject: str
    source_media_id: str = ""
    source_query: str = ""
    transition_hint: str = "match_cut"
    audio_intent: str = "keep_original"
    actor_intent: str = "none"
    color_intent: str = "natural_pop"
    style_tags: tuple[str, ...] = field(default_factory=tuple)
    template_ids: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.78
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.id).strip():
            raise ValueError("shot id is required")
        if self.index <= 0:
            raise ValueError("shot index must be positive")
        if self.start_ms < 0 or self.duration_ms <= 0:
            raise ValueError("shot time range must be positive")
        if not str(self.title).strip() or not str(self.prompt).strip():
            raise ValueError("shot title and prompt are required")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("shot confidence must be in [0, 1]")

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "index": int(self.index),
            "title": self.title,
            "prompt": self.prompt,
            "start_ms": int(self.start_ms),
            "duration_ms": int(self.duration_ms),
            "end_ms": int(self.end_ms),
            "shot_type": self.shot_type,
            "camera_angle": self.camera_angle,
            "camera_motion": self.camera_motion,
            "subject": self.subject,
            "source_media_id": self.source_media_id,
            "source_query": self.source_query,
            "transition_hint": self.transition_hint,
            "audio_intent": self.audio_intent,
            "actor_intent": self.actor_intent,
            "color_intent": self.color_intent,
            "style_tags": list(self.style_tags),
            "template_ids": list(self.template_ids),
            "confidence": float(self.confidence),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StoryboardPlan:
    id: str
    prompt: str
    title: str
    intent: str
    aspect_ratio: str
    duration_ms: int
    shot_cards: tuple[ShotCard, ...]
    style_bible: Mapping[str, Any]
    provider: str = "rule_based"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: int = LTX_STORYBOARD_SCHEMA_VERSION
    claim_level: str = LTX_STORYBOARD_CLAIM_LEVEL

    def __post_init__(self) -> None:
        if int(self.schema_version) != LTX_STORYBOARD_SCHEMA_VERSION:
            raise ValueError(f"unsupported storyboard schema: {self.schema_version}")
        if not str(self.id).strip():
            raise ValueError("storyboard id is required")
        if not self.shot_cards:
            raise ValueError("storyboard needs at least one shot card")
        seen: set[str] = set()
        for card in self.shot_cards:
            if card.id in seen:
                raise ValueError(f"duplicate shot id: {card.id}")
            seen.add(card.id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": int(self.schema_version),
            "id": self.id,
            "prompt": self.prompt,
            "title": self.title,
            "intent": self.intent,
            "aspect_ratio": self.aspect_ratio,
            "duration_ms": int(self.duration_ms),
            "provider": self.provider,
            "claim_level": self.claim_level,
            "ready": bool(self.shot_cards),
            "shot_count": len(self.shot_cards),
            "shot_cards": [card.to_dict() for card in self.shot_cards],
            "style_bible": dict(self.style_bible),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_stable_json(self) -> str:
        return stable_json_dumps(self.to_dict())


def _infer_intent(text: str, summary: Mapping[str, Any]) -> str:
    if any(token in text for token in ("tutorial", "how to", "screen", "cursor", "button", "강의", "튜토리얼")):
        return "screen_tutorial"
    if any(token in text for token in ("product", "review", "launch", "commerce", "제품", "리뷰")):
        return "product_demo"
    if any(token in text for token in ("podcast", "talk", "interview", "speech", "quote", "dialogue")) or summary.get("dialogue"):
        return "dialogue_story"
    if any(token in text for token in ("gameplay", "game", "highlight", "meme", "게임")):
        return "gameplay_highlight"
    if any(token in text for token in ("podcast", "talk", "interview", "speech", "대화", "스피치")) or summary.get("dialogue"):
        return "dialogue_story"
    if any(token in text for token in ("shorts", "tiktok", "reels", "vertical", "숏츠", "릴스")):
        return "shortform_social"
    return "creator_story"


def _style_bible(intent: str, aspect_ratio: str) -> dict[str, Any]:
    presets = {
        "screen_tutorial": {
            "palette": ["#6EA8FF", "#8A7CFF", "#FF6F61"],
            "mood": "clean screen-studio polish",
            "typography": "compact bold captions",
            "pacing": "clear step beats",
        },
        "product_demo": {
            "palette": ["#FFB84D", "#5BE7C4", "#FF6F61"],
            "mood": "warm product clarity",
            "typography": "benefit-first labels",
            "pacing": "hook proof call-to-action",
        },
        "gameplay_highlight": {
            "palette": ["#7B61FF", "#44C2FF", "#FFDD55"],
            "mood": "high-energy highlight",
            "typography": "short punchy captions",
            "pacing": "fast payoff beats",
        },
        "dialogue_story": {
            "palette": ["#5BE7C4", "#6EA8FF", "#B46CFF"],
            "mood": "clear dialogue chaptering",
            "typography": "readable lower-third captions",
            "pacing": "chaptered conversational flow",
        },
    }
    base = dict(presets.get(intent, {
        "palette": ["#8A7CFF", "#5BE7C4", "#FF6F61"],
        "mood": "creator polish",
        "typography": "bold readable captions",
        "pacing": "hook detail payoff",
    }))
    base["aspect_ratio"] = aspect_ratio
    base["safe_area"] = "vertical_caption_safe" if aspect_ratio == "9:16" else "standard_action_safe"
    return base


def _shot_templates(intent: str) -> list[dict[str, str]]:
    templates = {
        "screen_tutorial": [
            {"title": "Hook", "shot_type": "hook_closeup", "angle": "eye_level", "motion": "gentle_push", "transition": "match_cut"},
            {"title": "Show the problem", "shot_type": "screen_detail", "angle": "over_the_shoulder", "motion": "cursor_follow_zoom", "transition": "smooth_zoom"},
            {"title": "Action step", "shot_type": "action_step", "angle": "screen_flat", "motion": "snap_zoom", "transition": "button_match_cut"},
            {"title": "Result reveal", "shot_type": "result_reveal", "angle": "wide_ui", "motion": "ease_out_zoom", "transition": "soft_flash"},
            {"title": "Wrap up", "shot_type": "cta", "angle": "eye_level", "motion": "static_locked", "transition": "end_card"},
        ],
        "product_demo": [
            {"title": "Promise", "shot_type": "hook_closeup", "angle": "eye_level", "motion": "gentle_push", "transition": "match_cut"},
            {"title": "Feature detail", "shot_type": "product_feature", "angle": "macro_detail", "motion": "slow_slide", "transition": "shape_wipe"},
            {"title": "Proof", "shot_type": "proof_detail", "angle": "three_quarter", "motion": "static_locked", "transition": "match_cut"},
            {"title": "Before and after", "shot_type": "comparison", "angle": "split_view", "motion": "slide_compare", "transition": "split_reveal"},
            {"title": "Call to action", "shot_type": "cta", "angle": "hero_wide", "motion": "gentle_push", "transition": "end_card"},
        ],
        "gameplay_highlight": [
            {"title": "Set the stakes", "shot_type": "establishing", "angle": "wide_gameplay", "motion": "static_locked", "transition": "hard_cut"},
            {"title": "Build-up", "shot_type": "action_peak", "angle": "center_subject", "motion": "speed_ramp", "transition": "beat_cut"},
            {"title": "Impact", "shot_type": "impact", "angle": "close_action", "motion": "snap_zoom", "transition": "flash_cut"},
            {"title": "Replay detail", "shot_type": "replay_detail", "angle": "detail_crop", "motion": "slow_push", "transition": "match_cut"},
            {"title": "Payoff", "shot_type": "payoff", "angle": "wide_gameplay", "motion": "bounce_zoom", "transition": "end_card"},
        ],
        "dialogue_story": [
            {"title": "Opening quote", "shot_type": "host_closeup", "angle": "eye_level", "motion": "static_locked", "transition": "match_cut"},
            {"title": "Chapter point", "shot_type": "chapter_beat", "angle": "medium", "motion": "gentle_push", "transition": "chapter_card"},
            {"title": "Key quote", "shot_type": "quote_highlight", "angle": "closeup", "motion": "punch_in", "transition": "match_cut"},
            {"title": "Context", "shot_type": "b_roll", "angle": "supporting_visual", "motion": "slow_slide", "transition": "soft_wipe"},
            {"title": "Takeaway", "shot_type": "cta", "angle": "eye_level", "motion": "static_locked", "transition": "end_card"},
        ],
    }
    return list(templates.get(intent, [
        {"title": "Hook", "shot_type": "hook", "angle": "eye_level", "motion": "gentle_push", "transition": "match_cut"},
        {"title": "Detail", "shot_type": "detail", "angle": "medium", "motion": "slow_slide", "transition": "smooth_zoom"},
        {"title": "Action", "shot_type": "action", "angle": "center_subject", "motion": "snap_zoom", "transition": "beat_cut"},
        {"title": "Payoff", "shot_type": "payoff", "angle": "wide", "motion": "ease_out_zoom", "transition": "soft_flash"},
        {"title": "End card", "shot_type": "cta", "angle": "eye_level", "motion": "static_locked", "transition": "end_card"},
    ]))


def _target_duration_ms(summary: Mapping[str, Any], target_duration_ms: int | None) -> int:
    if target_duration_ms:
        return max(8_000, int(target_duration_ms))
    duration_s = float(summary.get("duration_s", 0) or 0)
    if duration_s <= 0:
        return 45_000
    if duration_s > 120:
        return 60_000
    return max(12_000, min(90_000, int(round(duration_s * 1000))))


def _media_source_for_shot(media_items: Sequence[Mapping[str, Any]], index: int) -> tuple[str, str, str]:
    if not media_items:
        return "", "", "timeline"
    row = _as_dict(media_items[(index - 1) % len(media_items)])
    media_id = str(row.get("id") or row.get("path") or row.get("name") or f"media_{index:03d}")
    subject = str(
        row.get("subject")
        or next((str(item) for item in _as_list(row.get("object_tags")) if str(item).strip()), "")
        or next((str(item) for item in _as_list(row.get("people")) if str(item).strip()), "")
        or row.get("name")
        or "main subject"
    )
    query_parts = [str(row.get("name") or ""), str(row.get("kind") or "")]
    for key in ("tags", "object_tags", "people"):
        query_parts.extend(str(item) for item in _as_list(row.get(key)))
    return media_id, " ".join(part for part in query_parts if part).strip(), subject


def _segment_for_shot(segments: Sequence[Mapping[str, Any]], index: int) -> Mapping[str, Any]:
    if not segments:
        return {}
    return _as_dict(segments[(index - 1) % len(segments)])


def _template_ids_for_intent(intent: str, summary: Mapping[str, Any], media_items: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    try:
        from app.creator_asset_packs import creator_asset_recommendation_board

        board = creator_asset_recommendation_board(summary, media_items, limit=4)
        ids = [str(card.get("id") or "") for card in _as_list(board.get("cards")) if str(card.get("id") or "")]
    except Exception:
        ids = []
    fallback = {
        "screen_tutorial": ["tutorial-click-polish", "screenstudio-wallpaper"],
        "product_demo": ["product-review-clean"],
        "gameplay_highlight": ["gameplay-stream-pop"],
        "dialogue_story": ["podcast-chapter-soft"],
    }.get(intent, ["caption-word-pop"])
    return tuple(dict.fromkeys([*ids, *fallback]) )


def build_ltx_storyboard_plan(
    prompt: str,
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] = (),
    *,
    target_duration_ms: int | None = None,
    aspect_ratio: str = "9:16",
    provider: str = "rule_based",
) -> StoryboardPlan:
    """Build a deterministic LTX-style storyboard plan."""
    summary = _as_dict(project_summary)
    media = [_as_dict(item) for item in media_items if isinstance(item, Mapping)]
    text = _text_blob(prompt, summary, media)
    intent = _infer_intent(text, summary)
    templates = _shot_templates(intent)
    segments = [_as_dict(row) for row in _as_list(summary.get("transcript_segments"))]
    shot_count = max(4, min(6, max(len(segments), len(templates))))
    duration_ms = _target_duration_ms(summary, target_duration_ms)
    base = duration_ms // shot_count
    remainder = duration_ms - base * shot_count
    template_ids = _template_ids_for_intent(intent, summary, media)
    style_bible = _style_bible(intent, aspect_ratio)
    provider_state = ltx_storyboard_provider_state()
    warnings: list[str] = []
    if not media:
        warnings.append("no_media_items_storyboard_uses_timeline_placeholder")
    if not segments:
        warnings.append("no_transcript_segments_storyboard_uses_prompt_arcs")
    if provider_state.get("configured"):
        warnings.append("external_provider_configured_but_builtin_planner_used_until_executor_is_wired")
    shot_cards: list[ShotCard] = []
    cursor = 0
    prompt_seed = " ".join(str(prompt or "").split()) or "Create a polished creator edit."
    for idx in range(1, shot_count + 1):
        template = templates[(idx - 1) % len(templates)]
        segment = _segment_for_shot(segments, idx)
        media_id, source_query, source_subject = _media_source_for_shot(media, idx)
        shot_duration = base + (1 if idx <= remainder else 0)
        subject = str(segment.get("text") or source_subject or template["title"])
        title = str(segment.get("title") or template["title"])
        if segment.get("text"):
            title = f"{template['title']}: {str(segment.get('text'))[:46]}"
        audio_intent = "dialogue_sync" if segment.get("text") or summary.get("dialogue") else "music_or_original_audio"
        actor_intent = "match_dialogue_mouth_eye_head" if summary.get("dialogue") else "none"
        shot_cards.append(
            ShotCard(
                id=f"shot_{idx:03d}_{_slug(template['shot_type'])}",
                index=idx,
                title=title,
                prompt=f"{prompt_seed} | {template['title']} | {subject}",
                start_ms=cursor,
                duration_ms=max(900, shot_duration),
                shot_type=template["shot_type"],
                camera_angle=template["angle"],
                camera_motion=template["motion"],
                subject=subject,
                source_media_id=media_id,
                source_query=source_query,
                transition_hint=template["transition"],
                audio_intent=audio_intent,
                actor_intent=actor_intent,
                color_intent=str(style_bible.get("mood") or "creator polish"),
                style_tags=tuple(str(item) for item in (intent, template["shot_type"], aspect_ratio)),
                template_ids=template_ids[:3],
                confidence=0.84 if segment or media else 0.72,
                warnings=tuple(["transcript_wrapped_from_available_segments"] if segments and idx > len(segments) else []),
                metadata={
                    "source_segment_id": str(segment.get("id") or ""),
                    "source_segment_start_ms": _int_ms(segment.get("start_ms")) if segment else None,
                    "source_segment_end_ms": _int_ms(segment.get("end_ms")) if segment else None,
                },
            )
        )
        cursor += shot_cards[-1].duration_ms
    title = {
        "screen_tutorial": "Screen Tutorial Shot Plan",
        "product_demo": "Product Demo Shot Plan",
        "gameplay_highlight": "Gameplay Highlight Shot Plan",
        "dialogue_story": "Dialogue Story Shot Plan",
        "shortform_social": "Shortform Social Shot Plan",
    }.get(intent, "Creator Story Shot Plan")
    return StoryboardPlan(
        id=f"ltx_storyboard_{_slug(intent)}",
        prompt=str(prompt or ""),
        title=title,
        intent=intent,
        aspect_ratio=aspect_ratio,
        duration_ms=sum(card.duration_ms for card in shot_cards),
        shot_cards=tuple(shot_cards),
        style_bible=style_bible,
        provider=provider,
        warnings=tuple(warnings),
        metadata={
            "provider_state": provider_state,
            "local_first": True,
            "cloud_required": False,
            "shot_planner": "deterministic_ltx_inspired",
            "template_ids": list(template_ids),
        },
    )


def storyboard_to_edit_plan(plan: StoryboardPlan) -> EditPlan:
    """Convert shot cards into a safe review-first EditPlan."""
    operations: list[EditOperation] = []
    template_ids = [str(item) for item in _as_list(plan.metadata.get("template_ids")) if str(item)]
    if template_ids:
        operations.append(
            EditOperation(
                type="apply_preset",
                target="project_workflow",
                params={
                    "preset_id": template_ids[0],
                    "template_ids": template_ids[:4],
                    "mode": "review_only",
                    "source": "ltx_storyboard",
                },
                metadata={"storyboard_id": plan.id},
                source="ltx_storyboard",
                reason="Stage the closest local creator template collection for the storyboard.",
                quality_score=82,
            )
        )
    if plan.aspect_ratio in {"9:16", "1:1"}:
        operations.append(
            EditOperation(
                type="set_reframe",
                target="storyboard_variant",
                params={
                    "aspect_ratio": plan.aspect_ratio,
                    "safe_area": plan.style_bible.get("safe_area", "vertical_caption_safe"),
                    "mode": "review_only",
                },
                metadata={"storyboard_id": plan.id},
                source="ltx_storyboard",
                reason="Prepare storyboard output framing.",
                quality_score=84,
            )
        )
    for card in plan.shot_cards:
        common_params = {
            "shot_id": card.id,
            "shot_index": card.index,
            "shot_type": card.shot_type,
            "camera_angle": card.camera_angle,
            "camera_motion": card.camera_motion,
            "transition_hint": card.transition_hint,
            "source_media_id": card.source_media_id,
            "source_query": card.source_query,
            "style_tags": list(card.style_tags),
            "actor_intent": card.actor_intent,
            "audio_intent": card.audio_intent,
            "color_intent": card.color_intent,
        }
        operations.append(
            EditOperation(
                type="create_short_candidate",
                target="review_cards",
                start_ms=card.start_ms,
                end_ms=card.end_ms,
                text=card.title,
                params={
                    **common_params,
                    "candidate_index": card.index,
                    "label": card.title,
                    "storyboard_prompt": card.prompt,
                },
                metadata={"storyboard_id": plan.id, "shot_id": card.id},
                source="ltx_storyboard_shot_card",
                reason="Stage this shot card as a reviewable timeline range.",
                confidence=card.confidence,
                quality_score=int(round(card.confidence * 100)),
            )
        )
        operations.append(
            EditOperation(
                type="add_marker",
                target="timeline_markers",
                text=f"Shot {card.index}: {card.title}",
                params={
                    **common_params,
                    "ms": card.start_ms,
                    "end_ms": card.end_ms,
                    "label": f"Shot {card.index}: {card.title}",
                    "color": "#8A7CFF",
                },
                metadata={"storyboard_id": plan.id, "shot_id": card.id},
                source="ltx_storyboard_marker",
                reason="Add a storyboard marker so the shot is visible on the timeline.",
                quality_score=88,
            )
        )
        if card.shot_type in {"hook_closeup", "screen_detail", "action_step", "product_feature", "impact", "quote_highlight"}:
            operations.append(
                EditOperation(
                    type="add_auto_zoom",
                    target="selected_video",
                    start_ms=card.start_ms,
                    end_ms=card.end_ms,
                    params={
                        **common_params,
                        "mode": card.camera_motion,
                        "strength": "medium",
                        "review_only": True,
                    },
                    metadata={"storyboard_id": plan.id, "shot_id": card.id},
                    source="ltx_storyboard_camera",
                    reason="Translate shot-card camera motion into reviewable auto-zoom intent.",
                    quality_score=80,
                )
            )
        if card.shot_type in {"hook_closeup", "cta", "comparison", "quote_highlight"}:
            operations.append(
                EditOperation(
                    type="add_callout",
                    target="selected_video",
                    start_ms=card.start_ms,
                    end_ms=min(card.end_ms, card.start_ms + max(1500, card.duration_ms // 2)),
                    text=card.title,
                    params={
                        **common_params,
                        "style": "ltx_shot_label",
                        "review_only": True,
                    },
                    metadata={"storyboard_id": plan.id, "shot_id": card.id},
                    source="ltx_storyboard_callout",
                    reason="Show the shot intention as an optional on-screen label.",
                    quality_score=76,
                )
            )
    operations.append(
        EditOperation(
            type="add_render_queue_job",
            target="render_queue",
            start_ms=0,
            end_ms=plan.duration_ms,
            params={
                "variant": "ltx_storyboard_review",
                "format": "mp4",
                "aspect_ratio": plan.aspect_ratio,
                "label": plan.title,
                "requires_user_review": True,
            },
            metadata={"storyboard_id": plan.id},
            source="ltx_storyboard_delivery",
            reason="Prepare a review-only render handoff after shot-card approval.",
            quality_score=78,
        )
    )
    normalized = normalize_operations([operation.with_id("") for operation in operations])
    cards: list[ReviewCard] = []
    for shot in plan.shot_cards:
        op_ids = tuple(
            operation.id
            for operation in normalized
            if _as_dict(operation.metadata).get("shot_id") == shot.id
        )
        cards.append(
            ReviewCard(
                id=f"card_{shot.id}",
                title=f"Shot {shot.index}: {shot.title}",
                operation_ids=op_ids,
                quality_score=int(round(shot.confidence * 100)),
                reason="Review this shot card before applying any timeline operation.",
                metadata=shot.to_dict(),
            )
        )
    return EditPlan(
        id=f"{plan.id}_edit_plan",
        intent="ltx_storyboard_review",
        summary=f"{plan.title}: {len(plan.shot_cards)} shot card(s) staged as reviewable edit operations.",
        operations=normalized,
        warnings=plan.warnings,
        requires_review=True,
        review_cards=tuple(cards),
        quality_score=84,
        metadata={
            "storyboard": _edit_plan_safe_payload(plan.to_dict()),
            "review_only": True,
            "local_first": True,
            "claim_level": plan.claim_level,
        },
        provider=plan.provider,
    )


def storyboard_review_panel_model(plan_or_payload: StoryboardPlan | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(plan_or_payload, StoryboardPlan):
        payload = plan_or_payload.to_dict()
    else:
        payload = dict(plan_or_payload or {})
    shots = [_as_dict(row) for row in _as_list(payload.get("shot_cards"))]
    rows = []
    for shot in shots:
        rows.append({
            "id": shot.get("id"),
            "label": f"{int(shot.get('index', 0) or 0):02d} {shot.get('title', '')}",
            "ready": True,
            "summary": f"{shot.get('shot_type')} · {shot.get('camera_motion')} · {shot.get('transition_hint')}",
            "start_ms": int(shot.get("start_ms", 0) or 0),
            "end_ms": int(shot.get("end_ms", 0) or 0),
            "source_media_id": shot.get("source_media_id", ""),
            "payload": shot,
        })
    provider_state = _as_dict(_as_dict(payload.get("metadata")).get("provider_state"))
    return {
        "ok": bool(rows),
        "ready": bool(rows),
        "kind": "ltx_storyboard",
        "label": "Shot cards",
        "summary": f"{len(rows)} shot card(s), {payload.get('intent', 'creator_story')}, {payload.get('aspect_ratio', '9:16')}",
        "cards": rows,
        "card_count": len(rows),
        "provider": provider_state,
        "claim_level": payload.get("claim_level", LTX_STORYBOARD_CLAIM_LEVEL),
        "actions": [
            {"id": "review_ltx_storyboard", "label": "Review shot cards", "enabled": bool(rows)},
            {"id": "apply_ltx_storyboard_markers", "label": "Add shot markers", "enabled": bool(rows)},
            {"id": "create_ltx_storyboard_variant", "label": "Create storyboard variant", "enabled": bool(rows)},
        ],
    }


def storyboard_apply_payload(plan: StoryboardPlan) -> dict[str, Any]:
    """Materialize storyboard EditPlan operations into the normal safe payload."""
    from app.ai_edit_apply import build_ai_script_apply_payload

    edit_plan = storyboard_to_edit_plan(plan)
    result = build_ai_script_apply_payload(edit_plan)
    payload = dict(result.payload)
    payload["storyboard_id"] = plan.id
    payload["claim_level"] = plan.claim_level
    payload["review_only"] = True
    payload["counts"] = dict(result.counts)
    payload["warnings"] = list(result.warnings)
    return payload


def _float01(value: Any, fallback: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return max(0.0, min(1.0, float(fallback)))


def _motion_zoom_profile(shot: Mapping[str, Any]) -> dict[str, Any]:
    motion = str(shot.get("camera_motion") or "").casefold()
    shot_type = str(shot.get("shot_type") or "").casefold()
    profile = {
        "mode": motion or "gentle_push",
        "zoom_scale": 1.18,
        "target_x_norm": 0.5,
        "target_y_norm": 0.46,
        "target_w_norm": 0.84,
        "target_h_norm": 0.84,
        "easing": "smooth_pop",
        "motion_blur": 0.10,
        "enabled": motion not in {"static_locked", "locked", "none"},
    }
    if motion in {"snap_zoom", "punch_in", "impact"} or shot_type in {"impact", "quote_highlight"}:
        profile.update({
            "zoom_scale": 1.55,
            "target_w_norm": 0.64,
            "target_h_norm": 0.64,
            "motion_blur": 0.18,
        })
    elif motion in {"cursor_follow_zoom", "button_match_cut"} or shot_type in {"screen_detail", "action_step"}:
        profile.update({
            "zoom_scale": 1.42,
            "target_y_norm": 0.42,
            "target_w_norm": 0.70,
            "target_h_norm": 0.70,
            "motion_blur": 0.14,
        })
    elif motion in {"slow_slide", "slide_compare"}:
        profile.update({
            "zoom_scale": 1.22,
            "target_x_norm": 0.52,
            "target_w_norm": 0.82,
            "target_h_norm": 0.82,
            "pan_from_x_norm": 0.46,
            "pan_to_x_norm": 0.56,
            "easing": "cinematic",
        })
    elif motion in {"speed_ramp", "bounce_zoom"}:
        profile.update({
            "zoom_scale": 1.48,
            "target_w_norm": 0.68,
            "target_h_norm": 0.68,
            "easing": "snappy",
            "motion_blur": 0.22,
        })
    elif motion in {"ease_out_zoom", "gentle_push"}:
        profile.update({
            "zoom_scale": 1.24,
            "target_w_norm": 0.80,
            "target_h_norm": 0.80,
        })
    if shot_type in {"host_closeup", "hook_closeup"}:
        profile["target_y_norm"] = 0.40
    elif shot_type in {"product_feature", "proof_detail", "macro_detail"}:
        profile["target_y_norm"] = 0.50
    elif shot_type in {"cta", "payoff"}:
        profile["target_y_norm"] = 0.45
    return profile


def storyboard_effect_materialization_payload(
    plan_or_payload: StoryboardPlan | Mapping[str, Any],
    apply_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return concrete, review-first effects implied by the shot cards.

    The storyboard itself is a planning surface.  This payload is the bridge
    toward real editor behavior: normalized zoom windows, callout labels, and
    template links that UI adapters can stage without guessing from prose.
    """

    payload = plan_or_payload.to_dict() if isinstance(plan_or_payload, StoryboardPlan) else dict(plan_or_payload or {})
    shots = [_as_dict(row) for row in _as_list(payload.get("shot_cards"))]
    style = _as_dict(payload.get("style_bible"))
    palette = [str(item) for item in _as_list(style.get("palette")) if str(item).strip()] or ["#8A7CFF", "#5BE7C4", "#FF6F61"]
    source_sidecars = [_as_dict(row) for row in _as_list(_as_dict(apply_payload).get("sidecars")) if isinstance(row, Mapping)]
    zoom_windows: list[dict[str, Any]] = []
    callouts: list[dict[str, Any]] = []
    template_links: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []
    for index, shot in enumerate(shots, start=1):
        shot_id = str(shot.get("id") or f"shot_{index:02d}")
        start_ms = _int_ms(shot.get("start_ms"))
        end_ms = max(start_ms + 1, _int_ms(shot.get("end_ms"), start_ms + _int_ms(shot.get("duration_ms"), 3000)))
        duration_ms = max(1, end_ms - start_ms)
        profile = _motion_zoom_profile(shot)
        if bool(profile.get("enabled")):
            zoom_in_ms = min(620, max(220, duration_ms // 4))
            zoom_out_ms = min(680, max(240, duration_ms // 4))
            zoom = {
                "id": f"{shot_id}_zoom",
                "shot_id": shot_id,
                "label": f"Shot {int(shot.get('index', index) or index)} camera",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "duration_ms": duration_ms,
                "camera_motion": str(shot.get("camera_motion") or profile.get("mode") or "gentle_push"),
                "zoom_scale": float(profile.get("zoom_scale", 1.18) or 1.18),
                "target_x_norm": _float01(profile.get("target_x_norm"), 0.5),
                "target_y_norm": _float01(profile.get("target_y_norm"), 0.46),
                "target_w_norm": _float01(profile.get("target_w_norm"), 0.84),
                "target_h_norm": _float01(profile.get("target_h_norm"), 0.84),
                "zoom_in_ms": zoom_in_ms,
                "zoom_out_ms": zoom_out_ms,
                "easing": str(profile.get("easing") or "smooth_pop"),
                "motion_blur": float(profile.get("motion_blur", 0.0) or 0.0),
                "source": "ltx_storyboard_effect_materialization",
                "review_only": True,
            }
            if profile.get("pan_from_x_norm") is not None:
                zoom["pan_from_x_norm"] = _float01(profile.get("pan_from_x_norm"), 0.46)
                zoom["pan_to_x_norm"] = _float01(profile.get("pan_to_x_norm"), 0.56)
            zoom_windows.append(zoom)
            effect_rows.append({
                "id": zoom["id"],
                "kind": "zoom_window",
                "shot_id": shot_id,
                "label": zoom["label"],
                "summary": f"{zoom['camera_motion']} x{zoom['zoom_scale']:.2f}",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "accent": palette[(index - 1) % len(palette)],
            })
        callout_enabled = str(shot.get("shot_type") or "").casefold() in {
            "hook_closeup",
            "cta",
            "comparison",
            "quote_highlight",
            "result_reveal",
            "payoff",
        }
        if callout_enabled:
            callout_end = min(end_ms, start_ms + max(1400, duration_ms // 2))
            callout = {
                "id": f"{shot_id}_callout",
                "shot_id": shot_id,
                "label": str(shot.get("title") or f"Shot {index}"),
                "text": str(shot.get("title") or f"Shot {index}"),
                "start_ms": start_ms,
                "end_ms": callout_end,
                "style": "ltx_shot_label",
                "accent": palette[(index - 1) % len(palette)],
                "position": "lower_third" if payload.get("aspect_ratio") != "9:16" else "safe_top",
                "source": "ltx_storyboard_effect_materialization",
                "review_only": True,
            }
            callouts.append(callout)
            effect_rows.append({
                "id": callout["id"],
                "kind": "callout",
                "shot_id": shot_id,
                "label": callout["label"],
                "summary": callout["style"],
                "start_ms": start_ms,
                "end_ms": callout_end,
                "accent": callout["accent"],
            })
        for raw_template in _as_list(shot.get("template_ids"))[:3]:
            template_id = str(raw_template or "").strip()
            if not template_id:
                continue
            template_links.append({
                "id": f"{shot_id}_{_slug(template_id, 'template')}",
                "shot_id": shot_id,
                "template_id": template_id,
                "label": str(shot.get("title") or f"Shot {index}"),
                "start_ms": start_ms,
                "end_ms": end_ms,
                "source": "ltx_storyboard_effect_materialization",
                "review_only": True,
            })
    warnings: list[str] = []
    if not zoom_windows:
        warnings.append("no_zoom_windows_from_storyboard")
    if not callouts:
        warnings.append("no_callouts_from_storyboard")
    return {
        "ok": bool(shots),
        "ready": bool(zoom_windows or callouts or template_links),
        "kind": "ltx_storyboard_effect_materialization",
        "storyboard_id": str(payload.get("id") or ""),
        "claim_level": payload.get("claim_level", LTX_STORYBOARD_CLAIM_LEVEL),
        "apply_mode": "review_first",
        "zoom_windows": zoom_windows,
        "callouts": callouts,
        "template_links": template_links,
        "effect_rows": effect_rows,
        "source_sidecar_count": len(source_sidecars),
        "counts": {
            "shots": len(shots),
            "zoom_windows": len(zoom_windows),
            "callouts": len(callouts),
            "template_links": len(template_links),
            "effect_rows": len(effect_rows),
            "source_sidecars": len(source_sidecars),
        },
        "warnings": warnings,
    }


def storyboard_template_recommendations(
    plan_or_payload: StoryboardPlan | Mapping[str, Any],
    *,
    limit: int = 8,
) -> dict[str, Any]:
    """Return shot-specific preset/template recommendations for the review UI."""
    payload = plan_or_payload.to_dict() if isinstance(plan_or_payload, StoryboardPlan) else dict(plan_or_payload or {})
    shots = [_as_dict(row) for row in _as_list(payload.get("shot_cards"))]
    style = _as_dict(payload.get("style_bible"))
    cards: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for shot in shots:
        shot_id = str(shot.get("id") or "")
        shot_label = f"Shot {int(shot.get('index', 0) or 0)}: {shot.get('title', '')}".strip()
        template_ids = [str(item) for item in _as_list(shot.get("template_ids")) if str(item).strip()]
        if not template_ids:
            template_ids = [f"{payload.get('intent', 'creator')}-polish"]
        for template_id in template_ids:
            key = (shot_id, template_id)
            if key in seen:
                continue
            seen.add(key)
            cards.append(
                {
                    "id": f"{shot_id}_{_slug(template_id, 'template')}",
                    "shot_id": shot_id,
                    "template_id": template_id,
                    "label": shot_label,
                    "reason": (
                        f"{shot.get('shot_type', 'shot')} / {shot.get('camera_motion', 'camera')} "
                        f"matches {template_id}"
                    ),
                    "start_ms": int(shot.get("start_ms", 0) or 0),
                    "end_ms": int(shot.get("end_ms", 0) or 0),
                    "accent": (style.get("palette") or ["#8A7CFF"])[len(cards) % max(1, len(style.get("palette") or ["#8A7CFF"]))],
                    "apply_mode": "review_first",
                    "source": "ltx_storyboard_template_recommendation",
                }
            )
            if len(cards) >= max(1, int(limit)):
                break
        if len(cards) >= max(1, int(limit)):
            break
    return {
        "ok": bool(cards),
        "ready": bool(cards),
        "kind": "ltx_storyboard_template_recommendations",
        "card_count": len(cards),
        "cards": cards,
        "global_template_ids": list(dict.fromkeys(str(item) for shot in shots for item in _as_list(shot.get("template_ids")) if str(item))),
        "claim_level": payload.get("claim_level", LTX_STORYBOARD_CLAIM_LEVEL),
    }


def build_ltx_storyboard_variations(
    plan: StoryboardPlan,
    *,
    modes: Sequence[str] = ("dynamic", "calm", "product", "tutorial"),
) -> dict[str, Any]:
    """Create reviewable alternate shot-card versions without mutating the source."""
    mode_config = {
        "dynamic": {
            "label": "Dynamic retake",
            "camera_motion": "snap_zoom",
            "transition_hint": "beat_cut",
            "mood": "fast punchy creator cut",
            "template_suffix": "dynamic",
        },
        "calm": {
            "label": "Calm retake",
            "camera_motion": "gentle_push",
            "transition_hint": "soft_wipe",
            "mood": "clean calm explanation",
            "template_suffix": "calm",
        },
        "product": {
            "label": "Product retake",
            "camera_motion": "slow_slide",
            "transition_hint": "shape_wipe",
            "mood": "product clarity and proof",
            "template_suffix": "product",
        },
        "tutorial": {
            "label": "Tutorial retake",
            "camera_motion": "cursor_follow_zoom",
            "transition_hint": "button_match_cut",
            "mood": "screen tutorial clarity",
            "template_suffix": "tutorial",
        },
    }
    variations: list[dict[str, Any]] = []
    for raw_mode in modes:
        mode = str(raw_mode or "").strip().casefold()
        cfg = mode_config.get(mode)
        if not cfg:
            continue
        cards: list[ShotCard] = []
        for card in plan.shot_cards:
            template_ids = tuple(
                dict.fromkeys([*card.template_ids, f"ltx-{cfg['template_suffix']}-retake"])
            )
            cards.append(
                replace(
                    card,
                    id=f"{card.id}_{mode}",
                    camera_motion=str(cfg["camera_motion"]),
                    transition_hint=str(cfg["transition_hint"]),
                    color_intent=str(cfg["mood"]),
                    style_tags=tuple(dict.fromkeys([*card.style_tags, mode, "retake"])),
                    template_ids=template_ids[:4],
                    metadata={**dict(card.metadata), "variation_mode": mode, "source_shot_id": card.id},
                )
            )
        style = dict(plan.style_bible)
        style["mood"] = str(cfg["mood"])
        style["variation_mode"] = mode
        variant = replace(
            plan,
            id=f"{plan.id}_{mode}",
            title=f"{plan.title} - {cfg['label']}",
            shot_cards=tuple(cards),
            style_bible=style,
            metadata={**dict(plan.metadata), "variation_mode": mode, "source_storyboard_id": plan.id},
        )
        edit_plan = storyboard_to_edit_plan(variant)
        variations.append(
            {
                "id": variant.id,
                "mode": mode,
                "label": str(cfg["label"]),
                "summary": f"{len(variant.shot_cards)} shot card(s), {cfg['mood']}",
                "storyboard": variant.to_dict(),
                "edit_plan": edit_plan.to_dict(),
                "operation_count": len(edit_plan.operations),
                "review_card_count": len(edit_plan.review_cards),
                "claim_level": variant.claim_level,
            }
        )
    return {
        "ok": bool(variations),
        "ready": bool(variations),
        "kind": "ltx_storyboard_variations",
        "variation_count": len(variations),
        "variations": variations,
        "source_storyboard_id": plan.id,
        "claim_level": plan.claim_level,
    }


def ltx_storyboard_report(
    prompt: str,
    project_summary: Mapping[str, Any] | None = None,
    media_items: Iterable[Mapping[str, Any]] = (),
    *,
    target_duration_ms: int | None = None,
    aspect_ratio: str = "9:16",
) -> dict[str, Any]:
    plan = build_ltx_storyboard_plan(
        prompt,
        project_summary,
        media_items,
        target_duration_ms=target_duration_ms,
        aspect_ratio=aspect_ratio,
    )
    edit_plan = storyboard_to_edit_plan(plan)
    panel = storyboard_review_panel_model(plan)
    apply_payload = storyboard_apply_payload(plan)
    variations = build_ltx_storyboard_variations(plan)
    template_recommendations = storyboard_template_recommendations(plan)
    effect_materialization = storyboard_effect_materialization_payload(plan, apply_payload)
    return {
        "ok": bool(plan.shot_cards and edit_plan.operations and panel.get("ready")),
        "storyboard": plan.to_dict(),
        "edit_plan": edit_plan.to_dict(),
        "apply_payload": apply_payload,
        "variations": variations,
        "template_recommendations": template_recommendations,
        "effect_materialization": effect_materialization,
        "review_panel": panel,
        "summary": {
            "shot_cards": len(plan.shot_cards),
            "edit_operations": len(edit_plan.operations),
            "review_cards": len(edit_plan.review_cards),
            "apply_markers": len(_as_list(apply_payload.get("timeline_markers"))),
            "apply_sidecars": len(_as_list(apply_payload.get("sidecars"))),
            "effect_zoom_windows": int(_as_dict(effect_materialization.get("counts")).get("zoom_windows", 0) or 0),
            "effect_callouts": int(_as_dict(effect_materialization.get("counts")).get("callouts", 0) or 0),
            "variations": int(variations.get("variation_count", 0) or 0),
            "template_recommendations": int(template_recommendations.get("card_count", 0) or 0),
            "claim_level": plan.claim_level,
            "real_ltx_cloud": False,
            "provider_configured": bool(ltx_storyboard_provider_state().get("configured")),
        },
    }
