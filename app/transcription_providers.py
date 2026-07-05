"""Local-first transcription provider contracts for editable scripts."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import importlib.util
from typing import Any

from app.ai_edit_plan import TranscriptDocument, TranscriptSegment, TranscriptWord
from app.transcript_cleanup import cleanup_transcript_document


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def _words_from_row(row: Mapping[str, Any], *, segment_start_ms: int, segment_end_ms: int) -> tuple[TranscriptWord, ...]:
    words: list[TranscriptWord] = []
    raw_words = list(row.get("words") or [])
    if raw_words:
        for raw in raw_words:
            if not isinstance(raw, Mapping):
                continue
            text = str(raw.get("text") or "").strip()
            if not text:
                continue
            start_ms = max(segment_start_ms, int(raw.get("start_ms", segment_start_ms) or segment_start_ms))
            end_ms = min(segment_end_ms, max(start_ms + 1, int(raw.get("end_ms", start_ms + 1) or start_ms + 1)))
            confidence = raw.get("confidence")
            words.append(
                TranscriptWord(
                    text=text,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=None if confidence is None else float(confidence),
                )
            )
        return tuple(words)
    tokens = [part for part in str(row.get("text") or "").split() if part]
    if not tokens:
        return ()
    duration = max(1, segment_end_ms - segment_start_ms)
    step = max(1, duration // len(tokens))
    for idx, token in enumerate(tokens):
        start_ms = segment_start_ms + idx * step
        end_ms = segment_end_ms if idx == len(tokens) - 1 else min(segment_end_ms, start_ms + step)
        words.append(TranscriptWord(text=token, start_ms=start_ms, end_ms=max(start_ms + 1, end_ms), confidence=None))
    return tuple(words)


def segments_to_word_timed_document(
    segments: Sequence[Mapping[str, Any]],
    *,
    document_id: str = "editable_script",
    source_media_id: str = "media_001",
    language: str = "und",
    created_by: str = "transcription_provider",
) -> TranscriptDocument:
    rows: list[TranscriptSegment] = []
    estimated_words = 0
    provider_words = 0
    for idx, row in enumerate(segments, start=1):
        start_ms = max(0, int(row.get("start_ms", 0) or 0))
        end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1) or start_ms + 1))
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        words = _words_from_row(row, segment_start_ms=start_ms, segment_end_ms=end_ms)
        if row.get("words"):
            provider_words += len(words)
        else:
            estimated_words += len(words)
        rows.append(
            TranscriptSegment(
                id=str(row.get("id") or f"seg_{idx:03d}"),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
                speaker=None if row.get("speaker") is None else str(row.get("speaker")),
                words=words,
            )
        )
    return TranscriptDocument(
        id=document_id,
        source_media_id=source_media_id,
        language=language,
        created_by=created_by,
        segments=tuple(rows),
        metadata={
            "word_timing": {
                "provider_words": provider_words,
                "estimated_words": estimated_words,
                "source": "provider_words" if provider_words else "estimated_from_segment_duration",
            }
        },
    )


def assign_speaker_labels(
    document: TranscriptDocument,
    speaker_turns: Sequence[Mapping[str, Any]] | None = None,
) -> TranscriptDocument:
    if not speaker_turns:
        return TranscriptDocument(
            id=document.id,
            source_media_id=document.source_media_id,
            language=document.language,
            created_by=document.created_by,
            segments=tuple(
                TranscriptSegment(
                    id=segment.id,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    text=segment.text,
                    speaker=segment.speaker or "speaker_1",
                    words=segment.words,
                )
                for segment in document.segments
            ),
            metadata={**dict(document.metadata), "diarization": {"source": "default_single_speaker", "speaker_count": 1}},
        )
    labeled: list[TranscriptSegment] = []
    speakers: set[str] = set()
    for segment in document.segments:
        best_speaker = segment.speaker or "speaker_1"
        best_overlap = 0
        for turn in speaker_turns:
            turn_start = int(turn.get("start_ms", 0) or 0)
            turn_end = int(turn.get("end_ms", turn_start) or turn_start)
            overlap = max(0, min(segment.end_ms, turn_end) - max(segment.start_ms, turn_start))
            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = str(turn.get("speaker") or best_speaker)
        speakers.add(best_speaker)
        labeled.append(
            TranscriptSegment(
                id=segment.id,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=segment.text,
                speaker=best_speaker,
                words=segment.words,
            )
        )
    return TranscriptDocument(
        id=document.id,
        source_media_id=document.source_media_id,
        language=document.language,
        created_by=document.created_by,
        segments=tuple(labeled),
        metadata={**dict(document.metadata), "diarization": {"source": "speaker_turns", "speaker_count": len(speakers)}},
    )


def build_editable_script_document(
    segments: Sequence[Mapping[str, Any]],
    *,
    speaker_turns: Sequence[Mapping[str, Any]] | None = None,
    document_id: str = "editable_script",
    source_media_id: str = "media_001",
    language: str = "und",
    glossary: Mapping[str, str] | None = None,
) -> TranscriptDocument:
    document = segments_to_word_timed_document(
        segments,
        document_id=document_id,
        source_media_id=source_media_id,
        language=language,
        created_by="editable_script_builder",
    )
    document = assign_speaker_labels(document, speaker_turns=speaker_turns)
    return cleanup_transcript_document(document, glossary=glossary)


def transcription_provider_readiness() -> dict[str, Any]:
    try:
        from app.local_ml import local_ml_backend_status

        whisper_status = dict((local_ml_backend_status().get("capabilities") or {}).get("whisper_transcription") or {})
    except Exception as exc:
        whisper_status = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": True,
        "word_timestamp_contract": True,
        "faster_whisper_installed": _module_available("faster_whisper"),
        "whisperx_installed": _module_available("whisperx"),
        "diarization_provider_slots": {
            "pyannote_audio": _module_available("pyannote.audio"),
            "speechbrain": _module_available("speechbrain"),
            "imported_speaker_turns": True,
        },
        "local_whisper": whisper_status,
        "runtime_model_ready": bool(whisper_status.get("available")),
    }


__all__ = [
    "assign_speaker_labels",
    "build_editable_script_document",
    "segments_to_word_timed_document",
    "transcription_provider_readiness",
]
