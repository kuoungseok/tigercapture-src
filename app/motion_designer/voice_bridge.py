"""Voice Lab subtitle timing bridge for text reveal and actor lip-sync cues."""
from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .composer_bridge import TIMING_SOURCES_KEY
from .schema import MotionComposition, MotionLayer, new_motion_id


def _time_ms(row: Mapping[str, Any], key: str, fallback: int) -> int:
    if key in row:
        return int(row.get(key, fallback) or fallback)
    seconds_key = key.replace("_ms", "")
    if seconds_key in row:
        return int(round(float(row.get(seconds_key, 0.0) or 0.0) * 1000.0))
    return int(fallback)


def _tokens(text: str) -> list[str]:
    return re.findall(r"\S+", str(text or ""))


def _distributed_words(text: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    words = _tokens(text)
    if not words:
        return []
    weights = [max(1, len(re.sub(r"\W", "", word, flags=re.UNICODE))) for word in words]
    total = max(1, sum(weights))
    span = max(len(words), end_ms - start_ms)
    output: list[dict[str, Any]] = []
    cursor = start_ms
    consumed = 0
    for index, (word, weight) in enumerate(zip(words, weights)):
        consumed += weight
        next_cursor = end_ms if index == len(words) - 1 else start_ms + int(round(span * consumed / total))
        output.append({"kind": "word", "text": word, "start_ms": cursor, "end_ms": max(cursor + 1, next_cursor),
                       "estimated": True})
        cursor = next_cursor
    return output


def _timed_units(rows: Sequence[Mapping[str, Any]] | None, kind: str, sentence_start: int,
                 sentence_end: int) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows or []:
        start = _time_ms(row, "start_ms", sentence_start)
        end = max(start + 1, _time_ms(row, "end_ms", sentence_end))
        output.append({
            "kind": kind, "text": str(row.get("text") or row.get("word") or row.get("phoneme") or ""),
            "start_ms": start, "end_ms": end, "estimated": bool(row.get("estimated", False)),
        })
    return output


def voice_timing_source(rows: Sequence[Mapping[str, Any]], *, timeline_start_ms: int = 0,
                        source_id: str = "") -> dict[str, Any]:
    offset = max(0, int(timeline_start_ms))
    sentences: list[dict[str, Any]] = []
    words: list[dict[str, Any]] = []
    phonemes: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        raw_start = _time_ms(row, "start_ms", 0)
        raw_end = max(raw_start + 1, _time_ms(row, "end_ms", raw_start + int(row.get("duration_ms", 1000) or 1000)))
        start, end = offset + raw_start, offset + raw_end
        text = str(row.get("display_text") or row.get("text") or row.get("tts_text") or "")
        sentences.append({"kind": "sentence", "index": index, "text": text, "start_ms": start, "end_ms": end})
        explicit_words = row.get("words") if isinstance(row.get("words"), Sequence) and not isinstance(row.get("words"), (str, bytes)) else None
        current_words = _timed_units(explicit_words, "word", raw_start, raw_end) if explicit_words else _distributed_words(text, raw_start, raw_end)
        for unit in current_words:
            unit["start_ms"] += offset
            unit["end_ms"] += offset
            unit["sentence_index"] = index
        words.extend(current_words)
        explicit_phonemes = row.get("phonemes") if isinstance(row.get("phonemes"), Sequence) and not isinstance(row.get("phonemes"), (str, bytes)) else None
        current_phonemes = _timed_units(explicit_phonemes, "phoneme", raw_start, raw_end)
        for unit in current_phonemes:
            unit["start_ms"] += offset
            unit["end_ms"] += offset
            unit["sentence_index"] = index
        phonemes.extend(current_phonemes)
    end_ms = max((row["end_ms"] for row in sentences), default=offset)
    return {
        "id": str(source_id or new_motion_id("voice_timing")),
        "kind": "voice", "priority": 110, "structured": True,
        "timeline_start_ms": offset, "duration_ms": max(0, end_ms - offset),
        "sentences": sentences, "words": words, "phonemes": phonemes,
        "metadata": {"schema": "tigerstudio.motion.voice_timing.v1",
                     "word_timing": "explicit" if any(not row.get("estimated") for row in words) else "estimated",
                     "phoneme_timing": "explicit" if phonemes else "unavailable"},
    }


def attach_voice_timing(composition: MotionComposition, timing: Mapping[str, Any], *,
                        text_layer: MotionLayer | None = None, actor_layer: MotionLayer | None = None) -> None:
    sources = dict(composition.metadata.get(TIMING_SOURCES_KEY) or {})
    sources[str(timing["id"])] = dict(timing)
    composition.metadata[TIMING_SOURCES_KEY] = sources
    if text_layer is not None:
        text_layer.metadata["voice_timing_source_id"] = str(timing["id"])
        text_layer.source.params["text_reveal_timing"] = {
            "source_id": str(timing["id"]), "unit": "word", "events": list(timing.get("words") or []),
        }
    if actor_layer is not None:
        cues = list(timing.get("phonemes") or timing.get("words") or [])
        actor_layer.metadata["voice_timing_source_id"] = str(timing["id"])
        actor_layer.metadata["lip_sync_cues"] = cues


def import_voice_timing(composition: MotionComposition, rows: Sequence[Mapping[str, Any]], *,
                        timeline_start_ms: int = 0, source_id: str = "",
                        text_layer: MotionLayer | None = None,
                        actor_layer: MotionLayer | None = None) -> dict[str, Any]:
    timing = voice_timing_source(rows, timeline_start_ms=timeline_start_ms, source_id=source_id)
    attach_voice_timing(composition, timing, text_layer=text_layer, actor_layer=actor_layer)
    return timing


__all__ = ["attach_voice_timing", "import_voice_timing", "voice_timing_source"]
