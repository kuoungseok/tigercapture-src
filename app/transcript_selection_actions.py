"""Selection-scoped transcript actions for captions, zooms, and highlights."""
from __future__ import annotations

from collections.abc import Sequence

from app.ai_edit_plan import EditOperation, EditPlan, ReviewCard, TranscriptDocument, build_edit_plan
from app.ai_text_editing import DEFAULT_CAPTION_STYLE, text_range_to_time_range
from app.transcript_document import segment_by_id


def build_selection_scoped_edit_plan(
    document: TranscriptDocument,
    *,
    segment_id: str,
    start_char: int,
    end_char: int,
    actions: Sequence[str] = ("caption", "zoom", "highlight"),
    caption_style_id: str = DEFAULT_CAPTION_STYLE,
    plan_id: str = "plan_selection_scoped_edit",
) -> EditPlan:
    start_ms, end_ms = text_range_to_time_range(document, segment_id, start_char, end_char)
    segment = segment_by_id(document, segment_id)
    selected_text = segment.text[max(0, int(start_char)):max(0, int(end_char))].strip() or segment.text
    action_set = {str(action).casefold() for action in actions}
    operations: list[EditOperation] = []
    common_metadata = {
        "source_transcript_id": document.id,
        "source_segment_id": segment_id,
        "start_char": int(start_char),
        "end_char": int(end_char),
        "selection_text": selected_text,
    }
    if "caption" in action_set or "captions" in action_set:
        operations.append(
            EditOperation(
                type="create_subtitles",
                target="subtitle_track",
                style_preset_id=caption_style_id,
                params={
                    "rows": [
                        {
                            "segment_id": segment_id,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "text": selected_text,
                            "style_preset_id": caption_style_id,
                        }
                    ],
                    "replace_existing": False,
                    **common_metadata,
                },
                source="transcript_selection_actions",
                reason="Create captions only for the selected transcript range.",
                quality_score=90,
            )
        )
    if "zoom" in action_set or "auto_zoom" in action_set:
        operations.append(
            EditOperation(
                type="add_auto_zoom",
                target="selected_video",
                start_ms=start_ms,
                end_ms=end_ms,
                params={"mode": "selection_scoped", "zoom": 1.18, **common_metadata},
                source="transcript_selection_actions",
                reason="Apply zoom only while the selected transcript range is spoken.",
                quality_score=84,
            )
        )
    if "highlight" in action_set or "emphasis" in action_set or "callout" in action_set:
        operations.append(
            EditOperation(
                type="add_callout",
                target="selected_video",
                start_ms=start_ms,
                end_ms=end_ms,
                text=selected_text,
                params={"label": selected_text, "style": "selection_highlight", **common_metadata},
                source="transcript_selection_actions",
                reason="Apply emphasis/highlight only to the selected transcript range.",
                quality_score=84,
            )
        )
    operation_ids = tuple(f"op_{idx:03d}_{operation.type}" for idx, operation in enumerate(operations, start=1))
    return build_edit_plan(
        plan_id=plan_id,
        intent="selection_scoped_edit",
        summary=f"Apply {len(operations)} scoped operation(s) to selected transcript text.",
        operations=operations,
        warnings=[] if operations else ["no_selection_scoped_actions"],
        review_cards=[
            ReviewCard(
                id="card_selection_scope",
                title="Selection-scoped changes",
                operation_ids=operation_ids,
                quality_score=86 if operations else 60,
                reason="Every operation is constrained to the selected transcript media range.",
                metadata=common_metadata,
            )
        ]
        if operations
        else [],
        quality_score=86 if operations else 60,
        metadata=common_metadata,
    )


__all__ = ["build_selection_scoped_edit_plan"]
