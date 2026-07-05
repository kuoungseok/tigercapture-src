"""Transcript cleanup for editable-script generation."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
import re
from typing import Any

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment


DEFAULT_GLOSSARY: dict[str, str] = {
    "오비에스": "OBS",
    "obs": "OBS",
    "에프에프엠펙": "FFmpeg",
    "ffmpeg": "FFmpeg",
    "타임 라인": "타임라인",
    "타임라인": "타임라인",
    "버튜버": "VTuber",
    "브이튜버": "VTuber",
    "라이브 투디": "Live2D",
    "live2d": "Live2D",
    "스파인": "Spine",
    "spine": "Spine",
    "쉐이더": "shader",
    "셰이더": "shader",
    "코덱스": "Codex",
}

_SPACE_RE = re.compile(r"\s+")


def _replace_case_insensitive(text: str, source: str, replacement: str) -> tuple[str, int]:
    pattern = re.compile(re.escape(source), re.IGNORECASE)
    return pattern.subn(replacement, text)


def apply_glossary(text: str, glossary: Mapping[str, str] | None = None) -> tuple[str, list[dict[str, str]]]:
    cleaned = str(text or "")
    hits: list[dict[str, str]] = []
    for raw_source, raw_replacement in (glossary or DEFAULT_GLOSSARY).items():
        source = str(raw_source)
        replacement = str(raw_replacement)
        if not source:
            continue
        cleaned, count = _replace_case_insensitive(cleaned, source, replacement)
        if count:
            hits.append({"source": source, "replacement": replacement, "count": str(count)})
    return cleaned, hits


def normalize_transcript_sentence(text: str, *, glossary: Mapping[str, str] | None = None) -> tuple[str, list[dict[str, str]]]:
    cleaned = _SPACE_RE.sub(" ", str(text or "").strip())
    cleaned, hits = apply_glossary(cleaned, glossary)
    cleaned = cleaned.strip(" ,")
    if cleaned and cleaned[-1] not in ".?!…":
        cleaned += "."
    if cleaned and cleaned[0].isascii() and cleaned[0].isalpha():
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned, hits


def cleanup_transcript_document(
    document: TranscriptDocument,
    *,
    glossary: Mapping[str, str] | None = None,
    paragraph_gap_ms: int = 1200,
) -> TranscriptDocument:
    segments: list[TranscriptSegment] = []
    glossary_hits: list[dict[str, Any]] = []
    previous: TranscriptSegment | None = None
    paragraph_index = 1
    for segment in document.segments:
        if previous is not None:
            speaker_changed = bool(segment.speaker and previous.speaker and segment.speaker != previous.speaker)
            if segment.start_ms - previous.end_ms >= paragraph_gap_ms or speaker_changed:
                paragraph_index += 1
        cleaned_text, hits = normalize_transcript_sentence(segment.text, glossary=glossary)
        for hit in hits:
            glossary_hits.append({"segment_id": segment.id, **hit})
        metadata = {"paragraph": paragraph_index}
        segments.append(replace(segment, text=cleaned_text, words=segment.words, speaker=segment.speaker))
        previous = segment
    return TranscriptDocument(
        id=document.id,
        source_media_id=document.source_media_id,
        language=document.language,
        created_by="transcript_cleanup",
        segments=tuple(segments),
        metadata={
            **dict(document.metadata),
            "cleanup": {
                "punctuation_restored": True,
                "paragraph_gap_ms": int(paragraph_gap_ms),
                "paragraph_count": paragraph_index if segments else 0,
                "glossary_hits": glossary_hits,
            },
        },
    )


__all__ = [
    "DEFAULT_GLOSSARY",
    "apply_glossary",
    "cleanup_transcript_document",
    "normalize_transcript_sentence",
]
