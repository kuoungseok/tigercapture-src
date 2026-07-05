"""Transcript document helpers shared by Descript-lite services."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment, TranscriptWord


def transcript_word_from_dict(payload: Mapping[str, Any]) -> TranscriptWord:
    return TranscriptWord(
        text=str(payload.get("text") or ""),
        start_ms=int(payload.get("start_ms", 0) or 0),
        end_ms=int(payload.get("end_ms", 0) or 0),
        confidence=None if payload.get("confidence") is None else float(payload.get("confidence")),
    )


def transcript_segment_from_dict(payload: Mapping[str, Any]) -> TranscriptSegment:
    return TranscriptSegment(
        id=str(payload.get("id") or ""),
        start_ms=int(payload.get("start_ms", 0) or 0),
        end_ms=int(payload.get("end_ms", 0) or 0),
        text=str(payload.get("text") or ""),
        speaker=None if payload.get("speaker") is None else str(payload.get("speaker")),
        words=tuple(transcript_word_from_dict(row) for row in list(payload.get("words") or [])),
    )


def transcript_document_from_dict(payload: Mapping[str, Any]) -> TranscriptDocument:
    return TranscriptDocument(
        id=str(payload.get("id") or ""),
        source_media_id=str(payload.get("source_media_id") or "media_001"),
        language=str(payload.get("language") or "und"),
        created_by=str(payload.get("created_by") or "manual"),
        segments=tuple(transcript_segment_from_dict(row) for row in list(payload.get("segments") or [])),
        metadata=dict(payload.get("metadata") or {}),
    )


def segment_by_id(document: TranscriptDocument, segment_id: str) -> TranscriptSegment:
    for segment in document.segments:
        if segment.id == segment_id:
            return segment
    raise KeyError(f"unknown transcript segment id: {segment_id}")


def iter_transcript_words(document: TranscriptDocument) -> Iterable[tuple[TranscriptSegment, TranscriptWord]]:
    for segment in document.segments:
        for word in segment.words:
            yield segment, word


def transcript_text(document: TranscriptDocument) -> str:
    return "\n".join(segment.text for segment in document.segments)


def transcript_duration_ms(document: TranscriptDocument) -> int:
    if not document.segments:
        return 0
    return max(segment.end_ms for segment in document.segments) - min(segment.start_ms for segment in document.segments)


def transcript_summary(document: TranscriptDocument) -> dict[str, Any]:
    word_count = sum(len(segment.words) for segment in document.segments)
    return {
        "id": document.id,
        "source_media_id": document.source_media_id,
        "language": document.language,
        "segments": len(document.segments),
        "word_timed_segments": sum(1 for segment in document.segments if segment.words),
        "words": word_count,
        "duration_ms": transcript_duration_ms(document),
    }


__all__ = [
    "iter_transcript_words",
    "segment_by_id",
    "transcript_document_from_dict",
    "transcript_duration_ms",
    "transcript_segment_from_dict",
    "transcript_summary",
    "transcript_text",
    "transcript_word_from_dict",
]
