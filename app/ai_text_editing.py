"""Deterministic MVP planners for AI text and one-click editing.

The helpers here do not call cloud APIs, download models, execute arbitrary
code, or mutate projects. They only produce validated EditPlan objects.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping, Sequence

from app.ai_edit_plan import (
    EditOperation,
    EditPlan,
    ReviewCard,
    TranscriptDocument,
    TranscriptSegment,
    build_edit_plan,
    normalize_operations,
)
from app.retake_detection import plan_remove_mistakes, plan_remove_retakes


DEFAULT_TARGET = "selected_video_linked_audio"
DEFAULT_CAPTION_STYLE = "caption-capcut-word-pop"

ENGLISH_FILLER_PATTERNS = (
    "you know",
    "sort of",
    "kind of",
    "i mean",
    "um",
    "uh",
    "er",
    "ah",
    "like",
    "basically",
    "actually",
)

KOREAN_FILLER_PATTERNS = (
    "그러니까",
    "그니까",
    "음",
    "어",
    "그",
    "뭐",
    "저기",
    "약간",
    "이제",
)

_TAG_RE = re.compile(r"<[^>]+>")
_SRT_TIME_RE = re.compile(r"\s*(\d+):(\d+):(\d+)[,.](\d{1,3})\s*")
_VTT_TIME_RE = re.compile(r"\s*(?:(\d+):)?(\d+):(\d+)[,.](\d{1,3})\s*")


def _parse_timecode_ms(value: str) -> int:
    raw = str(value or "").strip()
    match = _SRT_TIME_RE.match(raw) or _VTT_TIME_RE.match(raw)
    if not match:
        raise ValueError(f"invalid transcript timecode: {value!r}")
    groups = match.groups()
    if len(groups) == 4:
        hh_raw, mm_raw, ss_raw, ms_raw = groups
    else:
        raise ValueError(f"invalid transcript timecode: {value!r}")
    hh = int(hh_raw or 0)
    mm = int(mm_raw)
    ss = int(ss_raw)
    ms = int(str(ms_raw).ljust(3, "0")[:3])
    return hh * 3_600_000 + mm * 60_000 + ss * 1000 + ms


def _clean_cue_text(lines: Sequence[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    text = _TAG_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _make_document(
    *,
    rows: Sequence[tuple[int, int, str]],
    document_id: str,
    source_media_id: str,
    language: str,
    created_by: str,
    source_format: str,
) -> TranscriptDocument:
    segments = []
    for idx, (start_ms, end_ms, text) in enumerate(rows, start=1):
        if end_ms <= start_ms:
            end_ms = start_ms + 1200
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                id=f"seg_{idx:03d}",
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )
    return TranscriptDocument(
        id=document_id,
        source_media_id=source_media_id,
        language=language,
        created_by=created_by,
        segments=tuple(segments),
        metadata={"source_format": source_format},
    )


def parse_srt_text(
    text: str,
    *,
    document_id: str = "transcript_srt",
    source_media_id: str = "media_001",
    language: str = "und",
    created_by: str = "imported_srt",
) -> TranscriptDocument:
    """Parse SRT text into a validated TranscriptDocument."""
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    rows: list[tuple[int, int, str]] = []
    for block in re.split(r"\n\s*\n", normalized):
        lines = [line.strip("\ufeff ") for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        start_raw, end_raw = [part.strip().split(" ", 1)[0] for part in lines[0].split("-->", 1)]
        cue_text = _clean_cue_text(lines[1:])
        if cue_text:
            rows.append((_parse_timecode_ms(start_raw), _parse_timecode_ms(end_raw), cue_text))
    return _make_document(
        rows=rows,
        document_id=document_id,
        source_media_id=source_media_id,
        language=language,
        created_by=created_by,
        source_format="srt",
    )


def parse_vtt_text(
    text: str,
    *,
    document_id: str = "transcript_vtt",
    source_media_id: str = "media_001",
    language: str = "und",
    created_by: str = "imported_vtt",
) -> TranscriptDocument:
    """Parse WebVTT text into a validated TranscriptDocument."""
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    rows: list[tuple[int, int, str]] = []
    lines = [line.strip("\ufeff ") for line in normalized.split("\n")]
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line or line.upper().startswith("WEBVTT") or line.startswith(("NOTE", "STYLE", "REGION")):
            idx += 1
            continue
        if "-->" not in line and idx + 1 < len(lines) and "-->" in lines[idx + 1]:
            idx += 1
            line = lines[idx].strip()
        if "-->" not in line:
            idx += 1
            continue
        start_raw, end_raw = [part.strip().split(" ", 1)[0] for part in line.split("-->", 1)]
        idx += 1
        cue_lines = []
        while idx < len(lines) and lines[idx].strip():
            cue_lines.append(lines[idx])
            idx += 1
        cue_text = _clean_cue_text(cue_lines)
        if cue_text:
            rows.append((_parse_timecode_ms(start_raw), _parse_timecode_ms(end_raw), cue_text))
    return _make_document(
        rows=rows,
        document_id=document_id,
        source_media_id=source_media_id,
        language=language,
        created_by=created_by,
        source_format="vtt",
    )


def parse_transcript_text(
    text: str,
    *,
    source_format: str = "auto",
    document_id: str = "transcript_import",
    source_media_id: str = "media_001",
    language: str = "und",
) -> TranscriptDocument:
    fmt = source_format.casefold().strip()
    sample = str(text or "").lstrip("\ufeff \t\r\n")
    if fmt == "auto":
        fmt = "vtt" if sample.upper().startswith("WEBVTT") else "srt"
    if fmt == "vtt":
        return parse_vtt_text(text, document_id=document_id, source_media_id=source_media_id, language=language)
    if fmt == "srt":
        return parse_srt_text(text, document_id=document_id, source_media_id=source_media_id, language=language)
    raise ValueError(f"unsupported transcript format: {source_format}")


def _segment_by_id(document: TranscriptDocument, segment_id: str) -> TranscriptSegment:
    for segment in document.segments:
        if segment.id == segment_id:
            return segment
    raise KeyError(f"unknown transcript segment id: {segment_id}")


def text_range_to_time_range(
    document: TranscriptDocument,
    segment_id: str,
    start_char: int,
    end_char: int,
) -> tuple[int, int]:
    """Map a selected character range inside a segment to media time."""
    segment = _segment_by_id(document, segment_id)
    text_len = max(1, len(segment.text))
    start = max(0, min(int(start_char), text_len))
    end = max(start + 1, min(int(end_char), text_len))
    if segment.words:
        cursor = 0
        selected_word_times = []
        for word in segment.words:
            word_text = str(word.text)
            word_start = segment.text.find(word_text, cursor)
            if word_start < 0:
                word_start = cursor
            word_end = word_start + len(word_text)
            cursor = word_end
            if word_end > start and word_start < end:
                selected_word_times.append((word.start_ms, word.end_ms))
        if selected_word_times:
            return min(item[0] for item in selected_word_times), max(item[1] for item in selected_word_times)
    duration = segment.end_ms - segment.start_ms
    mapped_start = segment.start_ms + int(round(duration * (start / text_len)))
    mapped_end = segment.start_ms + int(round(duration * (end / text_len)))
    return mapped_start, max(mapped_start + 1, mapped_end)


def map_text_ranges_to_time_ranges(
    document: TranscriptDocument,
    selections: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ranges = []
    for selection in selections:
        segment_id = str(selection.get("segment_id") or "")
        start_ms, end_ms = text_range_to_time_range(
            document,
            segment_id,
            int(selection.get("start_char", 0) or 0),
            int(selection.get("end_char", 0) or 0),
        )
        ranges.append({"segment_id": segment_id, "start_ms": start_ms, "end_ms": end_ms})
    return ranges


def _filler_regex(patterns: Sequence[str]) -> re.Pattern[str]:
    parts = []
    for pattern in sorted(patterns, key=len, reverse=True):
        escaped = re.escape(pattern)
        if re.fullmatch(r"[A-Za-z ]+", pattern):
            parts.append(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])")
        else:
            parts.append(escaped)
    return re.compile("|".join(parts), re.IGNORECASE)


def detect_filler_ranges(
    document: TranscriptDocument,
    *,
    languages: Sequence[str] = ("en", "ko"),
) -> list[dict[str, Any]]:
    patterns = []
    langs = {item.casefold() for item in languages}
    if "en" in langs or "english" in langs:
        patterns.extend(ENGLISH_FILLER_PATTERNS)
    if "ko" in langs or "korean" in langs:
        patterns.extend(KOREAN_FILLER_PATTERNS)
    if not patterns:
        return []
    regex = _filler_regex(patterns)
    ranges: list[dict[str, Any]] = []
    for segment in document.segments:
        for match in regex.finditer(segment.text):
            start_ms, end_ms = text_range_to_time_range(document, segment.id, match.start(), match.end())
            ranges.append(
                {
                    "segment_id": segment.id,
                    "text": match.group(0),
                    "start_char": match.start(),
                    "end_char": match.end(),
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                }
            )
    return ranges


def plan_text_range_cut(
    document: TranscriptDocument,
    *,
    segment_id: str,
    start_char: int,
    end_char: int,
    target: str = DEFAULT_TARGET,
    plan_id: str = "plan_text_range_cut",
) -> EditPlan:
    start_ms, end_ms = text_range_to_time_range(document, segment_id, start_char, end_char)
    segment = _segment_by_id(document, segment_id)
    return build_edit_plan(
        plan_id=plan_id,
        intent="ripple_cut_text_range",
        summary="Create a reviewed ripple cut from selected transcript text.",
        operations=[
            EditOperation(
                type="ripple_cut_text_range",
                target=target,
                start_ms=start_ms,
                end_ms=end_ms,
                text=segment.text[start_char:end_char],
                params={"segment_id": segment_id, "start_char": int(start_char), "end_char": int(end_char)},
                source="transcript_selection",
                reason="Selected transcript text maps to this media range.",
                quality_score=90,
            )
        ],
        quality_score=90,
        metadata={"transcript_id": document.id, "mutation_mode": "review_only_plan"},
    )


def plan_remove_filler_words(
    document: TranscriptDocument,
    *,
    target: str = DEFAULT_TARGET,
    plan_id: str = "plan_remove_filler_words",
) -> EditPlan:
    ranges = detect_filler_ranges(document)
    operations = [
        EditOperation(
            type="delete_time_range",
            target=target,
            start_ms=item["start_ms"],
            end_ms=item["end_ms"],
            text=item["text"],
            params={
                "source_operation": "remove_filler_words",
                "segment_id": item["segment_id"],
                "start_char": item["start_char"],
                "end_char": item["end_char"],
            },
            source="deterministic_filler_detector",
            reason=f"Detected filler word: {item['text']}",
            quality_score=80,
        )
        for item in ranges
    ]
    warnings = [] if operations else ["no_filler_words_detected"]
    return build_edit_plan(
        plan_id=plan_id,
        intent="remove_filler_words",
        summary=f"Remove {len(operations)} detected Korean/English filler word range(s).",
        operations=operations,
        warnings=warnings,
        quality_score=85 if operations else 70,
        metadata={"transcript_id": document.id, "detector": "ko_en_starter_dictionary"},
    )


def plan_remove_silences(
    silence_intervals: Sequence[Mapping[str, Any]],
    *,
    min_duration_ms: int = 700,
    target: str = DEFAULT_TARGET,
    plan_id: str = "plan_remove_silences",
) -> EditPlan:
    operations = []
    for interval in silence_intervals:
        start_ms = int(interval.get("start_ms", 0) or 0)
        end_ms = int(interval.get("end_ms", 0) or 0)
        duration = max(0, end_ms - start_ms)
        if duration < min_duration_ms:
            continue
        operations.append(
            EditOperation(
                type="delete_time_range",
                target=target,
                start_ms=start_ms,
                end_ms=end_ms,
                params={"source_operation": "remove_silence", "min_duration_ms": int(min_duration_ms)},
                source="supplied_silence_intervals",
                reason=f"Silence interval is {duration} ms.",
                quality_score=88,
            )
        )
    return build_edit_plan(
        plan_id=plan_id,
        intent="remove_silence",
        summary=f"Remove {len(operations)} supplied silence interval(s) at or above {min_duration_ms} ms.",
        operations=operations,
        warnings=[] if operations else ["no_silence_intervals_over_threshold"],
        quality_score=88 if operations else 70,
        metadata={"min_duration_ms": int(min_duration_ms)},
    )


def plan_transcript_to_captions(
    document: TranscriptDocument,
    *,
    style_preset_id: str = DEFAULT_CAPTION_STYLE,
    target: str = "subtitle_track",
    plan_id: str = "plan_transcript_to_captions",
) -> EditPlan:
    rows = [
        {
            "segment_id": segment.id,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "text": segment.text,
            "style_preset_id": style_preset_id,
        }
        for segment in document.segments
    ]
    operation = EditOperation(
        type="create_subtitles",
        target=target,
        style_preset_id=style_preset_id,
        params={"rows": rows, "replace_existing": False, "source_transcript_id": document.id},
        source="transcript_document",
        reason="Generate styled subtitle rows from transcript segments while keeping transcript data separate.",
        quality_score=90 if rows else 60,
    )
    return build_edit_plan(
        plan_id=plan_id,
        intent="create_subtitles_from_transcript",
        summary=f"Create {len(rows)} styled subtitle row(s) from transcript segments.",
        operations=[operation] if rows else [],
        warnings=[] if rows else ["no_transcript_segments"],
        quality_score=90 if rows else 60,
        metadata={"transcript_id": document.id, "style_preset_id": style_preset_id},
    )


def _operation_count(plan_or_operations: EditPlan | Iterable[EditOperation]) -> int:
    if isinstance(plan_or_operations, EditPlan):
        return len(plan_or_operations.operations)
    return len(list(plan_or_operations))


def _operation_ids_by_source(operations: Sequence[EditOperation], *sources: str) -> tuple[str, ...]:
    wanted = set(sources)
    return tuple(operation.id for operation in operations if operation.source in wanted)


def _operation_ids_by_type(operations: Sequence[EditOperation], *types: str) -> tuple[str, ...]:
    wanted = set(types)
    return tuple(operation.id for operation in operations if operation.type in wanted)


def _recipe_plan(
    *,
    plan_id: str,
    intent: str,
    summary: str,
    operations: Sequence[EditOperation],
    cards: Sequence[ReviewCard],
    quality_score: int,
    warnings: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> EditPlan:
    return EditPlan(
        id=plan_id,
        intent=intent,
        summary=summary,
        operations=tuple(operations),
        warnings=tuple(warnings or []),
        review_cards=tuple(cards),
        requires_review=True,
        quality_score=quality_score,
        metadata={
            "recipe_mode": "one_click_reviewable",
            "llm_provider": "future_optional_disabled",
            "plan_layering": ["recipe_intent", "deterministic_operations", "review_cards", "apply_later"],
            **dict(metadata or {}),
        },
    )


def _normalize_recipe_operations(operations: Sequence[EditOperation]) -> tuple[EditOperation, ...]:
    return normalize_operations([operation.with_id("") for operation in operations])


def clean_tutorial_recipe(
    document: TranscriptDocument,
    *,
    silence_intervals: Sequence[Mapping[str, Any]] = (),
    target: str = DEFAULT_TARGET,
    style_preset_id: str = "caption-tutorial-compact",
) -> EditPlan:
    silence_plan = plan_remove_silences(silence_intervals, min_duration_ms=700, target=target)
    filler_plan = plan_remove_filler_words(document, target=target)
    retake_plan = plan_remove_retakes(document)
    mistake_plan = plan_remove_mistakes(document)
    caption_plan = plan_transcript_to_captions(document, style_preset_id=style_preset_id)
    operations = [
        *silence_plan.operations,
        *filler_plan.operations,
        *retake_plan.operations,
        *mistake_plan.operations,
        *caption_plan.operations,
        EditOperation(
            type="add_chapter_markers",
            target="timeline_markers",
            params={"source_transcript_id": document.id, "max_chapters": 6},
            source="recipe_clean_tutorial",
            reason="Stage chapter markers for tutorial review.",
            quality_score=76,
        ),
        EditOperation(
            type="add_auto_zoom",
            target="selected_video",
            params={"source": "cursor_events", "mode": "review_suggestions"},
            source="recipe_clean_tutorial",
            reason="Suggest cursor-based zooms for screen-recording clarity.",
            quality_score=72,
        ),
    ]
    normalized_operations = _normalize_recipe_operations(operations)
    cards = [
        ReviewCard(
            id="card_cleanup",
            title="Cleanup",
            operation_ids=_operation_ids_by_source(
                normalized_operations,
                "supplied_silence_intervals",
                "deterministic_filler_detector",
                "retake_detection",
                "mistake_detection",
            ),
            quality_score=84,
            reason="Silence and filler removals should be reviewed before timeline apply.",
        ),
        ReviewCard(
            id="card_captions",
            title="Captions",
            operation_ids=_operation_ids_by_type(normalized_operations, "create_subtitles"),
            quality_score=90,
            reason="Captions are generated from transcript rows and remain separate from transcript data.",
        ),
    ]
    return _recipe_plan(
        plan_id="recipe_clean_tutorial",
        intent="clean_tutorial",
        summary="One-click clean tutorial recipe: remove pauses, remove filler words, create captions, stage chapters and zooms.",
        operations=normalized_operations,
        cards=cards,
        quality_score=86,
        warnings=[*silence_plan.warnings, *filler_plan.warnings, *retake_plan.warnings, *mistake_plan.warnings, *caption_plan.warnings],
        metadata={"transcript_id": document.id, "recipe": "clean_tutorial"},
    )


def shorts_recipe(
    document: TranscriptDocument,
    *,
    target_duration_ms: int = 45_000,
    style_preset_id: str = DEFAULT_CAPTION_STYLE,
) -> EditPlan:
    candidates = []
    for idx, segment in enumerate(document.segments[:3], start=1):
        end_ms = min(segment.end_ms + target_duration_ms, max(document.segments[-1].end_ms if document.segments else segment.end_ms, segment.end_ms))
        candidates.append(
            EditOperation(
                type="create_short_candidate",
                target="review_cards",
                start_ms=segment.start_ms,
                end_ms=max(segment.end_ms, end_ms),
                text=segment.text,
                params={"candidate_index": idx, "source_segment_id": segment.id, "reason_code": "transcript_opening_or_beat"},
                source="recipe_shorts",
                reason="Transcript segment is staged as a reviewable Short candidate.",
                quality_score=max(68, 86 - idx * 4),
            )
        )
    operations = [
        *candidates,
        EditOperation(
            type="set_reframe",
            target="shorts_variant",
            params={"aspect_ratio": "9:16", "safe_area": "vertical_caption_safe"},
            source="recipe_shorts",
            reason="Stage vertical reframe for selected Short candidates.",
            quality_score=82,
        ),
        *plan_transcript_to_captions(document, style_preset_id=style_preset_id).operations,
        EditOperation(
            type="add_render_queue_job",
            target="render_queue",
            params={"variant": "shorts_review", "format": "mp4", "requires_user_pick": True},
            source="recipe_shorts",
            reason="Prepare render queue job after candidate review.",
            quality_score=78,
        ),
    ]
    normalized_operations = _normalize_recipe_operations(operations)
    return _recipe_plan(
        plan_id="recipe_shorts",
        intent="shorts",
        summary=f"One-click Shorts recipe: stage {len(candidates)} candidate(s), 9:16 reframe, captions, and render queue handoff.",
        operations=normalized_operations,
        cards=[
            ReviewCard(
                id=f"card_short_{idx:03d}",
                title=f"Short Candidate {idx}",
                operation_ids=tuple(
                    operation.id
                    for operation in normalized_operations
                    if operation.type == "create_short_candidate"
                    and int(operation.params.get("candidate_index", 0) or 0) == idx
                ),
                quality_score=max(68, 86 - idx * 4),
                reason="Candidate is heuristic-only in MVP and needs user review.",
                metadata={"candidate_index": idx},
            )
            for idx, _ in enumerate(candidates, start=1)
        ],
        quality_score=80,
        warnings=[] if candidates else ["no_transcript_segments_for_shorts"],
        metadata={"transcript_id": document.id, "recipe": "shorts"},
    )


def product_demo_recipe(
    document: TranscriptDocument,
    *,
    style_preset_id: str = "caption-ui-demo-soft-glass",
) -> EditPlan:
    caption_plan = plan_transcript_to_captions(document, style_preset_id=style_preset_id)
    first_segment = document.segments[0] if document.segments else None
    operations = [
        EditOperation(
            type="apply_preset",
            target="project_workflow",
            params={"preset_id": "template-product-demo-clean", "mode": "review_only"},
            source="recipe_product_demo",
            reason="Stage a product demo workflow preset for review.",
            quality_score=82,
        ),
        *caption_plan.operations,
        EditOperation(
            type="add_auto_zoom",
            target="selected_video",
            params={"source": "cursor_events", "mode": "product_focus"},
            source="recipe_product_demo",
            reason="Suggest product-focused zooms for review.",
            quality_score=74,
        ),
        EditOperation(
            type="add_render_queue_job",
            target="render_queue",
            params={"variant": "product_demo_review", "format": "mp4"},
            source="recipe_product_demo",
            reason="Prepare render job after plan review.",
            quality_score=78,
        ),
    ]
    warnings = list(caption_plan.warnings)
    if first_segment:
        operations.insert(
            2,
            EditOperation(
                type="add_callout",
                target="selected_video",
                start_ms=first_segment.start_ms,
                end_ms=first_segment.end_ms,
                text=first_segment.text,
                params={"style": "product_feature_callout", "source_segment_id": first_segment.id},
                source="recipe_product_demo",
                reason="Stage first transcript beat as a feature callout.",
                quality_score=78,
            ),
        )
    else:
        warnings.append("product_demo_callout_skipped_no_transcript_segment")
    normalized_operations = _normalize_recipe_operations(operations)
    return _recipe_plan(
        plan_id="recipe_product_demo",
        intent="product_demo",
        summary="One-click product demo recipe: preset, captions, callout, product zooms, and render queue handoff.",
        operations=normalized_operations,
        cards=[
            ReviewCard(
                id="card_product_demo",
                title="Product Demo",
                operation_ids=tuple(operation.id for operation in normalized_operations),
                quality_score=82,
                reason="Recipe layers a preset, transcript captions, and reviewable visual suggestions.",
            )
        ],
        quality_score=82,
        warnings=warnings,
        metadata={"transcript_id": document.id, "recipe": "product_demo"},
    )


def clean_tutorial(
    document: TranscriptDocument,
    *,
    silence_intervals: Sequence[Mapping[str, Any]] = (),
    target: str = DEFAULT_TARGET,
    style_preset_id: str = "caption-tutorial-compact",
) -> EditPlan:
    return clean_tutorial_recipe(
        document,
        silence_intervals=silence_intervals,
        target=target,
        style_preset_id=style_preset_id,
    )


def shorts(
    document: TranscriptDocument,
    *,
    target_duration_ms: int = 45_000,
    style_preset_id: str = DEFAULT_CAPTION_STYLE,
) -> EditPlan:
    return shorts_recipe(
        document,
        target_duration_ms=target_duration_ms,
        style_preset_id=style_preset_id,
    )


def product_demo(
    document: TranscriptDocument,
    *,
    style_preset_id: str = "caption-ui-demo-soft-glass",
) -> EditPlan:
    return product_demo_recipe(document, style_preset_id=style_preset_id)
