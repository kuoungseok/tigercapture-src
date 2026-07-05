"""Panel-owned transcript edit surface model.

This module is intentionally independent from VideoEditorWindow. It gives the
Script Edit panel a small, testable surface for word/sentence selection,
reviewable deletion, sentence-move intent preview, scoped effects, and
post-cut transcript reflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.ai_edit_plan import EditPlan, TranscriptDocument
from app.ai_text_editing import plan_text_range_cut, text_range_to_time_range
from app.transcript_document import segment_by_id, transcript_summary
from app.transcript_reflow import reflow_transcript_after_cuts
from app.transcript_selection_actions import build_selection_scoped_edit_plan
from app.transcript_timeline_ops import build_delete_text_range_intents, build_sentence_move_clip_move_intents


@dataclass(frozen=True)
class TranscriptTextSelection:
    segment_id: str
    start_char: int
    end_char: int
    text: str
    start_ms: int
    end_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_char": int(self.start_char),
            "end_char": int(self.end_char),
            "text": self.text,
            "start_ms": int(self.start_ms),
            "end_ms": int(self.end_ms),
        }


class TranscriptEditSurface:
    """Small state holder for panel-owned transcript edits."""

    def __init__(self, document: TranscriptDocument | None = None) -> None:
        self.document = document
        self.selection: TranscriptTextSelection | None = None

    def set_document(self, document: TranscriptDocument | None) -> None:
        self.document = document
        self.selection = None

    def _require_document(self) -> TranscriptDocument:
        if self.document is None:
            raise ValueError("transcript edit surface requires a transcript document")
        return self.document

    def select_text_range(self, segment_id: str, start_char: int, end_char: int) -> dict[str, Any]:
        document = self._require_document()
        segment = segment_by_id(document, segment_id)
        text_len = max(1, len(segment.text))
        start = max(0, min(int(start_char), text_len))
        end = max(start + 1, min(int(end_char), text_len))
        start_ms, end_ms = text_range_to_time_range(document, segment_id, start, end)
        self.selection = TranscriptTextSelection(
            segment_id=segment_id,
            start_char=start,
            end_char=end,
            text=segment.text[start:end],
            start_ms=start_ms,
            end_ms=end_ms,
        )
        return self.selection.to_dict()

    def clear_selection(self) -> None:
        self.selection = None

    def _selection_or_kwargs(
        self,
        *,
        segment_id: str | None = None,
        start_char: int | None = None,
        end_char: int | None = None,
    ) -> TranscriptTextSelection:
        if segment_id is not None:
            return TranscriptTextSelection(**self.select_text_range(segment_id, int(start_char or 0), int(end_char or 0)))
        if self.selection is None:
            raise ValueError("select transcript text before building a selection edit")
        return self.selection

    def build_delete_selection_plan(self) -> EditPlan:
        document = self._require_document()
        selection = self._selection_or_kwargs()
        return plan_text_range_cut(
            document,
            segment_id=selection.segment_id,
            start_char=selection.start_char,
            end_char=selection.end_char,
        )

    def build_delete_selection_intents(self) -> dict[str, Any]:
        document = self._require_document()
        selection = self._selection_or_kwargs()
        return build_delete_text_range_intents(
            document,
            segment_id=selection.segment_id,
            start_char=selection.start_char,
            end_char=selection.end_char,
        )

    def build_selection_scoped_plan(self, actions: Sequence[str] = ("caption", "zoom", "highlight")) -> EditPlan:
        document = self._require_document()
        selection = self._selection_or_kwargs()
        return build_selection_scoped_edit_plan(
            document,
            segment_id=selection.segment_id,
            start_char=selection.start_char,
            end_char=selection.end_char,
            actions=actions,
        )

    def build_sentence_move_preview(
        self,
        *,
        source_segment_id: str,
        before_segment_id: str | None = None,
        after_segment_id: str | None = None,
        destination_ms: int | None = None,
    ) -> dict[str, Any]:
        document = self._require_document()
        return build_sentence_move_clip_move_intents(
            document,
            source_segment_id=source_segment_id,
            before_segment_id=before_segment_id,
            after_segment_id=after_segment_id,
            destination_ms=destination_ms,
        )

    def reflow_after_cuts(self, cut_ranges: Sequence[dict[str, Any]]) -> TranscriptDocument:
        document = self._require_document()
        self.document = reflow_transcript_after_cuts(document, cut_ranges)
        self.selection = None
        return self.document

    def preview(self) -> dict[str, Any]:
        document = self.document
        return {
            "ok": document is not None,
            "document": {} if document is None else transcript_summary(document),
            "selection": {} if self.selection is None else self.selection.to_dict(),
            "capabilities": {
                "delete_selection": document is not None and self.selection is not None,
                "selection_scoped_effects": document is not None and self.selection is not None,
                "sentence_move_preview": document is not None,
                "post_cut_reflow": document is not None,
            },
            "owner": "ScriptEditPanelModel",
            "video_editor_window_dependency": False,
        }


__all__ = ["TranscriptEditSurface", "TranscriptTextSelection"]
