"""Transcript reflow helpers for reviewed ripple cuts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment, TranscriptWord


@dataclass(frozen=True)
class TranscriptCutRange:
    start_ms: int
    end_ms: int
    id: str = ""

    @property
    def duration_ms(self) -> int:
        return max(0, int(self.end_ms) - int(self.start_ms))


def normalize_transcript_cut_ranges(cut_ranges: Sequence[Mapping[str, Any]]) -> tuple[TranscriptCutRange, ...]:
    ranges: list[TranscriptCutRange] = []
    for idx, row in enumerate(cut_ranges, start=1):
        start = row.get("original_start_ms", row.get("start_ms", row.get("applied_start_ms", 0)))
        end = row.get("original_end_ms", row.get("end_ms", row.get("applied_end_ms", 0)))
        start_ms = max(0, int(start or 0))
        end_ms = max(start_ms + 1, int(end or 0))
        ranges.append(TranscriptCutRange(start_ms=start_ms, end_ms=end_ms, id=str(row.get("id") or f"cut_{idx:03d}")))
    ranges.sort(key=lambda item: (item.start_ms, item.end_ms))
    merged: list[TranscriptCutRange] = []
    for item in ranges:
        if not merged or item.start_ms > merged[-1].end_ms:
            merged.append(item)
            continue
        previous = merged[-1]
        merged[-1] = TranscriptCutRange(
            start_ms=previous.start_ms,
            end_ms=max(previous.end_ms, item.end_ms),
            id=",".join(part for part in (previous.id, item.id) if part),
        )
    return tuple(merged)


def _overlaps(start_ms: int, end_ms: int, cut: TranscriptCutRange) -> bool:
    return int(end_ms) > cut.start_ms and int(start_ms) < cut.end_ms


def _shift_ms(value: int, cuts: Sequence[TranscriptCutRange]) -> int:
    shift = sum(cut.duration_ms for cut in cuts if cut.end_ms <= int(value))
    return max(0, int(value) - shift)


def _remaining_intervals(start_ms: int, end_ms: int, cuts: Sequence[TranscriptCutRange]) -> list[tuple[int, int]]:
    intervals = [(int(start_ms), int(end_ms))]
    for cut in cuts:
        next_intervals: list[tuple[int, int]] = []
        for left, right in intervals:
            if not _overlaps(left, right, cut):
                next_intervals.append((left, right))
                continue
            if left < cut.start_ms:
                next_intervals.append((left, cut.start_ms))
            if cut.end_ms < right:
                next_intervals.append((cut.end_ms, right))
        intervals = [(left, right) for left, right in next_intervals if right > left]
        if not intervals:
            break
    return intervals


def _reflow_word(word: TranscriptWord, cuts: Sequence[TranscriptCutRange]) -> TranscriptWord | None:
    if any(_overlaps(word.start_ms, word.end_ms, cut) for cut in cuts):
        return None
    return TranscriptWord(
        text=word.text,
        start_ms=_shift_ms(word.start_ms, cuts),
        end_ms=max(_shift_ms(word.start_ms, cuts) + 1, _shift_ms(word.end_ms, cuts)),
        confidence=word.confidence,
    )


def _reflow_word_segment(segment: TranscriptSegment, cuts: Sequence[TranscriptCutRange]) -> TranscriptSegment | None:
    words = tuple(word for raw in segment.words if (word := _reflow_word(raw, cuts)) is not None)
    if not words:
        return None
    return TranscriptSegment(
        id=segment.id,
        start_ms=min(word.start_ms for word in words),
        end_ms=max(word.end_ms for word in words),
        text=" ".join(word.text for word in words),
        speaker=segment.speaker,
        words=words,
    )


def _reflow_untimed_segment(segment: TranscriptSegment, cuts: Sequence[TranscriptCutRange]) -> tuple[TranscriptSegment, ...]:
    intervals = _remaining_intervals(segment.start_ms, segment.end_ms, cuts)
    out: list[TranscriptSegment] = []
    for idx, (start_ms, end_ms) in enumerate(intervals, start=1):
        shifted_start = _shift_ms(start_ms, cuts)
        shifted_end = max(shifted_start + 1, _shift_ms(end_ms, cuts))
        suffix = "" if len(intervals) == 1 else f"_part{idx:03d}"
        out.append(
            TranscriptSegment(
                id=f"{segment.id}{suffix}",
                start_ms=shifted_start,
                end_ms=shifted_end,
                text=segment.text,
                speaker=segment.speaker,
            )
        )
    return tuple(out)


def reflow_transcript_after_cuts(
    document: TranscriptDocument,
    cut_ranges: Sequence[Mapping[str, Any]],
    *,
    created_by: str = "transcript_reflow",
) -> TranscriptDocument:
    """Return a revised transcript after reviewed ripple-delete ranges.

    Ranges are interpreted in the original transcript timeline. Word-timed
    segments remove overlapping words and shift all later words by removed
    duration. Untimed segments preserve text while splitting only their time
    ranges, because the helper cannot safely infer partial text without words.
    """
    cuts = normalize_transcript_cut_ranges(cut_ranges)
    if not cuts:
        return document
    segments: list[TranscriptSegment] = []
    for segment in document.segments:
        if segment.words:
            reflowed = _reflow_word_segment(segment, cuts)
            if reflowed is not None:
                segments.append(reflowed)
        else:
            segments.extend(_reflow_untimed_segment(segment, cuts))
    return TranscriptDocument(
        id=document.id,
        source_media_id=document.source_media_id,
        language=document.language,
        created_by=created_by,
        segments=tuple(sorted(segments, key=lambda item: (item.start_ms, item.end_ms, item.id))),
        metadata={
            **dict(document.metadata),
            "reflow": {
                "source_created_by": document.created_by,
                "cut_count": len(cuts),
                "removed_ms": sum(cut.duration_ms for cut in cuts),
                "cut_ids": [cut.id for cut in cuts],
            },
        },
    )


__all__ = [
    "TranscriptCutRange",
    "normalize_transcript_cut_ranges",
    "reflow_transcript_after_cuts",
]
