"""Transcript-to-timeline operation planning without editor-widget coupling."""
from __future__ import annotations

from typing import Any

from app.ai_edit_plan import TranscriptDocument
from app.ai_text_editing import text_range_to_time_range
from app.transcript_document import segment_by_id


def build_delete_text_range_intents(
    document: TranscriptDocument,
    *,
    segment_id: str,
    start_char: int,
    end_char: int,
) -> dict[str, Any]:
    start_ms, end_ms = text_range_to_time_range(document, segment_id, start_char, end_char)
    segment = segment_by_id(document, segment_id)
    return {
        "ok": True,
        "kind": "transcript_delete_text_range",
        "source": {
            "transcript_id": document.id,
            "segment_id": segment_id,
            "start_char": int(start_char),
            "end_char": int(end_char),
            "text": segment.text[int(start_char):int(end_char)],
        },
        "time_range": {"start_ms": start_ms, "end_ms": end_ms},
        "cut_intents": [
            {
                "id": f"transcript-delete-{segment_id}-{start_char}-{end_char}",
                "type": "ripple_cut_text_range",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "source_transcript_id": document.id,
                "source_segment_id": segment_id,
            }
        ],
        "required_actions": ["ai.apply_reviewed_cuts"],
        "requires_review": True,
    }


def build_sentence_move_clip_move_intents(
    document: TranscriptDocument,
    *,
    source_segment_id: str,
    before_segment_id: str | None = None,
    after_segment_id: str | None = None,
    destination_ms: int | None = None,
) -> dict[str, Any]:
    """Build unresolved linked clip-move intents from transcript sentence order.

    This intentionally returns action intent data rather than mutating timeline
    clips. A later action adapter resolves which linked video/audio clips
    intersect the source sentence range and executes the registered split/move
    actions.
    """
    source = segment_by_id(document, source_segment_id)
    if destination_ms is None:
        if before_segment_id:
            destination_ms = segment_by_id(document, before_segment_id).start_ms
        elif after_segment_id:
            destination_ms = segment_by_id(document, after_segment_id).end_ms
        else:
            return {
                "ok": False,
                "kind": "transcript_sentence_move",
                "warnings": ["missing_destination"],
                "requires_review": True,
            }
    raw_destination_ms = max(0, int(destination_ms))
    duration_ms = source.end_ms - source.start_ms
    destination_after_source_removal_ms = raw_destination_ms - duration_ms if raw_destination_ms > source.end_ms else raw_destination_ms
    delta_ms = destination_after_source_removal_ms - source.start_ms
    warnings: list[str] = []
    if source.start_ms <= raw_destination_ms <= source.end_ms:
        warnings.append("destination_inside_source_range")
    return {
        "ok": not warnings,
        "kind": "transcript_sentence_move",
        "source": {
            "transcript_id": document.id,
            "segment_id": source_segment_id,
            "text": source.text,
        },
        "source_range": {"start_ms": source.start_ms, "end_ms": source.end_ms, "duration_ms": duration_ms},
        "destination": {
            "requested_ms": raw_destination_ms,
            "after_source_removal_ms": destination_after_source_removal_ms,
            "before_segment_id": before_segment_id or "",
            "after_segment_id": after_segment_id or "",
        },
        "clip_move": {
            "delta_ms": delta_ms,
            "strict_links": True,
            "resolve_by_time_range": True,
        },
        "required_registered_actions": ["timeline.split", "clip.move_linked"],
        "action_steps": [
            {"action": "timeline.split", "params": {"at_ms": source.start_ms}},
            {"action": "timeline.split", "params": {"at_ms": source.end_ms}},
            {
                "action": "clip.move_linked",
                "params": {
                    "source_range_start_ms": source.start_ms,
                    "source_range_end_ms": source.end_ms,
                    "delta_ms": delta_ms,
                    "strict_links": True,
                    "resolve_clip_ids": True,
                },
            },
        ],
        "warnings": warnings,
        "requires_review": True,
    }


__all__ = [
    "build_delete_text_range_intents",
    "build_sentence_move_clip_move_intents",
]
