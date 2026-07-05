"""Script Edit panel for transcript-driven AI edit plans.

The model is dependency-light and testable without launching the editor. The
Qt widget is a thin view/controller over that model.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import replace
from html import escape as _html_escape
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QInputDialog,
    QScrollArea,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.ai_edit_apply import operation_ids_for_review_cards
from app.ai_edit_plan import EditPlan, TranscriptDocument
from app.ai_providers import (
    ai_provider_readiness,
    generate_selected_provider_plan,
    is_ai_provider_status_prompt,
    provider_state_label,
    provider_snapshot,
    provider_interaction_model,
    provider_setup_instructions,
    provider_status_label,
    provider_user_label,
    provider_user_state,
    save_ai_provider_preference,
    save_local_llm_provider_config,
    selected_ai_provider_id,
    saved_local_llm_config,
)
from app.ai_text_editing import (
    DEFAULT_CAPTION_STYLE,
    clean_tutorial,
    parse_transcript_text,
    plan_remove_filler_words,
    plan_remove_silences,
    plan_text_range_cut,
    plan_transcript_to_captions,
    product_demo,
    shorts,
)
from app.icons import app_icon, icon_size
from app.style import editor_scrollbar_qss
from app.transcript_edit_surface import TranscriptEditSurface


SCRIPT_EDIT_ACTIONS: tuple[tuple[str, str], ...] = (
    ("transcript_to_captions", "Transcript to Captions"),
    ("remove_filler_words", "Remove Filler Words"),
    ("remove_silences", "Remove Silences"),
    ("remove_retakes", "Remove Retakes"),
    ("remove_mistakes", "Remove Mistakes"),
    ("text_range_cut", "Text Range Cut"),
    ("clean_tutorial", "Clean Tutorial"),
    ("shorts", "Shorts"),
    ("product_demo", "Product Demo"),
)


def _format_ms(ms: int | None) -> str:
    value = max(0, int(ms or 0))
    seconds, millis = divmod(value, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minute:02d}:{sec:02d}.{millis:03d}"
    return f"{minute:02d}:{sec:02d}.{millis:03d}"


def _format_srt_ms(ms: int | None) -> str:
    value = max(0, int(ms or 0))
    seconds, millis = divmod(value, 1000)
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    return f"{hours:02d}:{minute:02d}:{sec:02d},{millis:03d}"


def _segments_to_srt_text(segments: Sequence[Mapping[str, Any]]) -> str:
    rows: list[str] = []
    for idx, row in enumerate(segments or [], start=1):
        text = " ".join(str(row.get("text") or "").split())
        if not text:
            continue
        start_ms = max(0, int(row.get("start_ms", 0) or 0))
        end_ms = max(start_ms + 1, int(row.get("end_ms", start_ms + 1000) or start_ms + 1000))
        rows.append(f"{idx}\n{_format_srt_ms(start_ms)} --> {_format_srt_ms(end_ms)}\n{text}")
    return "\n\n".join(rows)


def _parse_silence_intervals_text(text: str) -> list[dict[str, int]]:
    intervals: list[dict[str, int]] = []
    for raw_line in str(text or "").replace(";", "\n").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for sep in ("-->", "-", ","):
            if sep in line:
                left, right = [part.strip() for part in line.split(sep, 1)]
                break
        else:
            continue
        try:
            start_ms = int(round(float(left)))
            end_ms = int(round(float(right)))
        except Exception:
            continue
        if end_ms > start_ms >= 0:
            intervals.append({"start_ms": start_ms, "end_ms": end_ms})
    return intervals


def edit_plan_preview(plan: EditPlan | None) -> dict[str, Any]:
    if plan is None:
        return {
            "summary": "No plan generated.",
            "operation_counts": {},
            "affected_duration_ms": 0,
            "warnings": [],
            "review_cards": [],
            "operations": [],
        }
    counts = Counter(operation.type for operation in plan.operations)
    affected_duration_ms = 0
    for operation in plan.operations:
        if operation.start_ms is not None and operation.end_ms is not None:
            affected_duration_ms += max(0, int(operation.end_ms) - int(operation.start_ms))
    return {
        "id": plan.id,
        "intent": plan.intent,
        "summary": plan.summary,
        "requires_review": plan.requires_review,
        "quality_score": plan.quality_score,
        "operation_counts": dict(sorted(counts.items())),
        "affected_duration_ms": affected_duration_ms,
        "warnings": list(plan.warnings),
        "review_cards": [card.to_dict() for card in plan.review_cards],
        "operations": [operation.to_dict() for operation in plan.operations],
    }


class ScriptEditPanelModel:
    """Pure-Python state and planning API for Script Edit."""

    def __init__(
        self,
        *,
        source_media_id: str = "media_001",
        language: str = "und",
    ) -> None:
        self.source_media_id = str(source_media_id or "media_001")
        self.language = str(language or "und")
        self.document: TranscriptDocument | None = None
        self.transcript_surface = TranscriptEditSurface()
        self.current_plan: EditPlan | None = None
        self.silence_intervals: list[dict[str, int]] = []
        self._selected_operation_ids: list[str] = []
        self._selected_card_ids: list[str] = []

    def import_transcript_text(
        self,
        text: str,
        *,
        source_format: str = "auto",
        document_id: str = "script_edit_transcript",
        source_media_id: str | None = None,
        language: str | None = None,
    ) -> TranscriptDocument:
        document = parse_transcript_text(
            text,
            source_format=source_format,
            document_id=document_id,
            source_media_id=source_media_id or self.source_media_id,
            language=language or self.language,
        )
        self.document = document
        self.transcript_surface.set_document(document)
        self.current_plan = None
        self._selected_operation_ids = []
        self._selected_card_ids = []
        return document

    def import_transcript_file_path(
        self,
        path: str | Path,
        *,
        source_format: str = "auto",
        document_id: str | None = None,
        language: str | None = None,
    ) -> TranscriptDocument:
        transcript_path = Path(path)
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp949"):
            try:
                text = transcript_path.read_text(encoding=encoding)
                break
            except Exception:
                text = ""
        if not text:
            raise ValueError(f"could not read transcript file: {transcript_path}")
        fmt = source_format
        if fmt == "auto" and transcript_path.suffix.casefold() == ".vtt":
            fmt = "vtt"
        elif fmt == "auto" and transcript_path.suffix.casefold() == ".srt":
            fmt = "srt"
        return self.import_transcript_text(
            text,
            source_format=fmt,
            document_id=document_id or f"script_edit_{transcript_path.stem}",
            language=language,
        )

    def set_transcript_document(self, document: TranscriptDocument) -> None:
        self.document = document
        self.transcript_surface.set_document(document)
        self.current_plan = None
        self._selected_operation_ids = []
        self._selected_card_ids = []

    def clear_transcript_context(self, *, clear_plan: bool = False) -> None:
        """Clear transcript state without implying the user asked for subtitles."""
        self.document = None
        self.transcript_surface.set_document(None)
        if clear_plan:
            self.current_plan = None
            self._selected_operation_ids = []
            self._selected_card_ids = []

    def set_silence_intervals(self, intervals: Sequence[Mapping[str, Any]]) -> None:
        cleaned: list[dict[str, int]] = []
        for interval in intervals:
            try:
                start_ms = max(0, int(interval.get("start_ms", 0) or 0))
                end_ms = max(start_ms + 1, int(interval.get("end_ms", start_ms + 1) or start_ms + 1))
            except Exception:
                continue
            cleaned.append({"start_ms": start_ms, "end_ms": end_ms})
        self.silence_intervals = cleaned

    def _require_document(self) -> TranscriptDocument:
        if self.document is None:
            raise ValueError("import a transcript before generating a Script Edit plan")
        return self.document

    def generate_plan(self, action: str, **kwargs: Any) -> EditPlan:
        action_id = str(action or "").strip().casefold().replace(" ", "_")
        if action_id in {"ltx_storyboard", "storyboard", "shot_cards", "shot_card", "scene_plan"}:
            from app.ltx_storyboard import build_ltx_storyboard_plan, storyboard_to_edit_plan

            summary = dict(kwargs.get("project_summary") or {})
            if self.document is not None:
                segments = [segment.to_dict() for segment in self.document.segments]
                summary.setdefault("transcript_segments", segments)
                summary.setdefault("dialogue", bool(segments))
                summary.setdefault("has_audio", bool(segments))
                if segments:
                    summary.setdefault("duration_s", max(row.get("end_ms", 0) for row in segments) / 1000.0)
            media_items = kwargs.get("media_items") or summary.get("media_items") or []
            prompt = str(
                kwargs.get("prompt")
                or summary.get("creator_prompt")
                or summary.get("prompt")
                or "Create reviewable shot cards for this edit."
            )
            aspect_ratio = str(kwargs.get("aspect_ratio") or summary.get("aspect_ratio") or "9:16")
            storyboard = build_ltx_storyboard_plan(prompt, summary, media_items, aspect_ratio=aspect_ratio)
            plan = storyboard_to_edit_plan(storyboard)
            metadata = dict(plan.metadata or {})
            metadata.update(
                {
                    "prompt_text": prompt,
                    "prompt_mode": "local_rule_based_storyboard",
                    "prompt_resolved_action": action_id,
                    "provider_id": "rule_based",
                    "local_llm_required": False,
                }
            )
            plan = replace(plan, metadata=metadata, provider="rule_based")
            self.current_plan = plan
            self._selected_operation_ids = [operation.id for operation in plan.operations]
            self._selected_card_ids = [card.id for card in plan.review_cards]
            return plan
        document = self._require_document()
        style_preset_arg = kwargs.get("style_preset_id")
        style_preset_id = str(style_preset_arg or DEFAULT_CAPTION_STYLE)
        if action_id in {"caption", "captions", "transcript_to_captions", "create_subtitles"}:
            plan = plan_transcript_to_captions(document, style_preset_id=style_preset_id)
        elif action_id in {"remove_filler", "remove_filler_words", "fillers"}:
            plan = plan_remove_filler_words(document)
        elif action_id in {"remove_silence", "remove_silences", "silence"}:
            min_duration_ms = int(kwargs.get("min_duration_ms", 700) or 700)
            plan = plan_remove_silences(self.silence_intervals, min_duration_ms=min_duration_ms)
        elif action_id in {"remove_retake", "remove_retakes", "retake", "retakes"}:
            from app.retake_detection import plan_remove_retakes

            plan = plan_remove_retakes(document)
        elif action_id in {"remove_mistake", "remove_mistakes", "mistake", "mistakes", "false_start", "false_starts"}:
            from app.retake_detection import plan_remove_mistakes

            plan = plan_remove_mistakes(document)
        elif action_id in {"text_range_cut", "ripple_cut_text_range", "cut_text_range"}:
            segment_id = str(kwargs.get("segment_id") or (document.segments[0].id if document.segments else ""))
            if not segment_id:
                raise ValueError("text_range_cut requires at least one transcript segment")
            start_char = int(kwargs.get("start_char", 0) or 0)
            end_char = int(kwargs.get("end_char", len(next(seg.text for seg in document.segments if seg.id == segment_id))) or 0)
            plan = plan_text_range_cut(document, segment_id=segment_id, start_char=start_char, end_char=end_char)
        elif action_id == "clean_tutorial":
            plan = clean_tutorial(
                document,
                silence_intervals=self.silence_intervals,
                style_preset_id=str(style_preset_arg or "caption-tutorial-compact"),
            )
        elif action_id == "shorts":
            plan = shorts(
                document,
                target_duration_ms=int(kwargs.get("target_duration_ms", 45_000) or 45_000),
                style_preset_id=style_preset_id,
            )
        elif action_id == "product_demo":
            plan = product_demo(document, style_preset_id=str(style_preset_arg or "caption-ui-demo-soft-glass"))
        else:
            raise ValueError(f"unsupported Script Edit action: {action}")
        self.current_plan = plan
        self._selected_operation_ids = [operation.id for operation in plan.operations]
        self._selected_card_ids = [card.id for card in plan.review_cards]
        return plan

    def resolve_prompt_action(self, prompt: str) -> str:
        """Map an editing prompt to the best local deterministic recipe.

        This is deliberately small and transparent. A future local LLM can
        replace only this resolver while keeping the same safe EditPlan boundary.
        """
        text = " ".join(str(prompt or "").casefold().split())
        if not text:
            return "clean_tutorial"

        def has(*tokens: str) -> bool:
            return any(token.casefold() in text for token in tokens)

        words = set(text.split())
        try:
            from app.ltx_storyboard import prompt_requests_storyboard

            if prompt_requests_storyboard(text):
                return "ltx_storyboard"
        except Exception:
            pass
        wants_shorts = has("쇼츠", "릴스", "short", "shorts", "tiktok", "틱톡", "세로", "vertical", "reels", "유튜브쇼츠")
        wants_product = has("제품", "데모", "광고", "런칭", "출시", "후기", "리뷰", "product", "demo", "launch", "ad ", "review")
        wants_cleanup = has("정리", "깔끔", "다듬", "튜토리얼", "강의", "설명", "tutorial", "clean", "polish", "딸각", "보기 좋게")
        wants_filler = has("군더더기", "필러", "말버릇", "filler", "um", "uh") or bool({"음", "어", "이제"} & words)
        wants_silence = has("무음", "침묵", "공백", "pause", "silence", "silent")
        wants_caption = has("자막", "캡션", "caption", "captions", "subtitle", "subtitles")
        wants_cut = has("잘라", "자르", "컷", "삭제", "앞부분", "뒷부분", "인트로", "아웃트로", "cut", "remove", "delete", "trim")
        wants_zoom_cursor = has("줌", "확대", "커서", "마우스", "클릭", "자동줌", "zoom", "cursor", "click", "highlight")
        wants_broll = has("b-roll", "broll", "비롤", "컷어웨이", "callout", "콜아웃", "강조")
        wants_chapters = has("챕터", "목차", "구간", "chapter", "chapters", "marker", "markers")

        if wants_shorts:
            return "shorts"
        if wants_product:
            return "product_demo"
        if wants_zoom_cursor or wants_broll or wants_chapters:
            return "clean_tutorial"
        if wants_cleanup or (wants_caption and (wants_filler or wants_silence)):
            return "clean_tutorial"
        if wants_filler:
            return "remove_filler_words"
        if wants_silence:
            return "remove_silences"
        if wants_caption:
            return "transcript_to_captions"
        if wants_cut:
            return "text_range_cut"
        return "clean_tutorial"

    def generate_plan_from_prompt(self, prompt: str, **kwargs: Any) -> EditPlan:
        action_id = self.resolve_prompt_action(prompt)
        plan = self.generate_plan(action_id, prompt=prompt, **kwargs)
        metadata = dict(plan.metadata or {})
        metadata.update(
            {
                "prompt_text": str(prompt or "").strip(),
                "prompt_mode": "local_rule_based",
                "prompt_resolved_action": action_id,
                "provider_id": "rule_based",
                "local_llm_required": False,
            }
        )
        plan = replace(plan, metadata=metadata, provider="rule_based")
        self.current_plan = plan
        self._selected_operation_ids = [operation.id for operation in plan.operations]
        self._selected_card_ids = [card.id for card in plan.review_cards]
        return plan

    def set_selected_operation_ids(self, operation_ids: Sequence[str]) -> None:
        self._selected_operation_ids = [str(item) for item in operation_ids]

    def set_selected_card_ids(self, card_ids: Sequence[str]) -> None:
        self._selected_card_ids = [str(item) for item in card_ids]

    def selected_operation_ids(self, *, include_cards: bool = True) -> list[str]:
        plan = self.current_plan
        selected = set(self._selected_operation_ids)
        if include_cards and plan is not None:
            selected.update(operation_ids_for_review_cards(plan, self._selected_card_ids))
            return [operation.id for operation in plan.operations if operation.id in selected]
        return list(self._selected_operation_ids)

    def selected_card_ids(self) -> list[str]:
        return list(self._selected_card_ids)

    def preview(self) -> dict[str, Any]:
        return edit_plan_preview(self.current_plan)

    def select_transcript_range(self, segment_id: str, start_char: int, end_char: int) -> dict[str, Any]:
        return self.transcript_surface.select_text_range(segment_id, start_char, end_char)

    def generate_delete_selection_plan(self) -> EditPlan:
        plan = self.transcript_surface.build_delete_selection_plan()
        self.current_plan = plan
        self._selected_operation_ids = [operation.id for operation in plan.operations]
        self._selected_card_ids = [card.id for card in plan.review_cards]
        return plan

    def generate_selection_scoped_plan(self, actions: Sequence[str] = ("caption", "zoom", "highlight")) -> EditPlan:
        plan = self.transcript_surface.build_selection_scoped_plan(actions)
        self.current_plan = plan
        self._selected_operation_ids = [operation.id for operation in plan.operations]
        self._selected_card_ids = [card.id for card in plan.review_cards]
        return plan

    def build_sentence_move_preview(
        self,
        *,
        source_segment_id: str,
        before_segment_id: str | None = None,
        after_segment_id: str | None = None,
        destination_ms: int | None = None,
    ) -> dict[str, Any]:
        return self.transcript_surface.build_sentence_move_preview(
            source_segment_id=source_segment_id,
            before_segment_id=before_segment_id,
            after_segment_id=after_segment_id,
            destination_ms=destination_ms,
        )

    def apply_transcript_reflow(self, cut_ranges: Sequence[dict[str, Any]]) -> TranscriptDocument:
        document = self.transcript_surface.reflow_after_cuts(cut_ranges)
        self.document = document
        self.current_plan = None
        self._selected_operation_ids = []
        self._selected_card_ids = []
        return document

    def transcript_edit_preview(self) -> dict[str, Any]:
        return self.transcript_surface.preview()

    def prepare_editable_script(
        self,
        *,
        speaker_turns: Sequence[Mapping[str, Any]] | None = None,
        glossary: Mapping[str, str] | None = None,
    ) -> TranscriptDocument:
        document = self._require_document()
        from app.transcription_providers import build_editable_script_document

        prepared = build_editable_script_document(
            [segment.to_dict() for segment in document.segments],
            speaker_turns=speaker_turns,
            document_id=document.id,
            source_media_id=document.source_media_id,
            language=document.language,
            glossary=glossary,
        )
        self.set_transcript_document(prepared)
        return prepared


class ScriptEditPanel(QWidget):
    plan_generated = Signal(object)
    preview_requested = Signal(object)
    apply_selected_requested = Signal(object)
    apply_all_requested = Signal()
    apply_cuts_requested = Signal(object)
    provider_setup_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None, *, model: ScriptEditPanelModel | None = None) -> None:
        super().__init__(parent)
        self.model = model or ScriptEditPanelModel()
        self.setObjectName("ScriptEditPanel")
        self.setMinimumWidth(0)
        self._loading_provider_combo = False
        self._review_mode = False
        self._external_provider_setup_handler = None
        self._apply_studio_style()
        self._build_ui()
        self._refresh_provider_status()
        self._refresh_transcript_rows()
        self._refresh_plan_view()

    def set_external_provider_setup_handler(self, handler: Any | None) -> None:
        """Let an owning editor open richer provider setup flows."""
        self._external_provider_setup_handler = handler if callable(handler) else None

    def _apply_studio_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#ScriptEditPanel {
                background: #101112;
                color: #E6EAF2;
                font-size: 10px;
                font-family: "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
            }
            QScrollArea#ScriptEditScrollArea {
                background: transparent;
                border: 0;
            }
            QWidget#ScriptEditScrollContent {
                background: transparent;
            }
            QLabel#ScriptEditSummary {
                color: #AEB5BF;
                font-weight: 620;
                letter-spacing: 0px;
            }
            QPlainTextEdit#ScriptEditPromptInput,
            QWidget#ScriptEditPanel QPlainTextEdit,
            QWidget#ScriptEditPanel QLineEdit,
            QWidget#ScriptEditPanel QSpinBox,
            QWidget#ScriptEditPanel QComboBox,
            QComboBox#ScriptEditProviderCombo {
                color: #DCE2EA;
                background: #121417;
                border: 1px solid #292E35;
                border-radius: 5px;
                padding: 4px 7px;
                selection-background-color: #4A5568;
                selection-color: #FFFFFF;
            }
            QWidget#ScriptEditPanel QPlainTextEdit:focus,
            QWidget#ScriptEditPanel QLineEdit:focus,
            QWidget#ScriptEditPanel QComboBox:focus {
                border: 1px solid #566171;
                background: #15181D;
            }
            QWidget#ScriptEditPanel QListWidget {
                color: #DCE2EA;
                background: #101112;
                border: 1px solid #24282F;
                border-radius: 5px;
                padding: 3px;
                outline: 0;
            }
            QWidget#ScriptEditPanel QListWidget::item {
                color: #DCE2EA;
                background: rgba(255, 255, 255, 8);
                border: 1px solid #252B33;
                border-radius: 4px;
                margin: 2px 0;
                padding: 5px;
            }
            QWidget#ScriptEditPanel QListWidget::item:selected,
            QWidget#ScriptEditPanel QListWidget::item:hover {
                background: #1B2027;
                border-color: #566171;
            }
            QWidget#ScriptEditPanel QPushButton#PrimaryToolButton {
                color: #F2F5FA;
                background: #2A3038;
                border: 1px solid #48515E;
                border-radius: 5px;
                padding: 5px 9px;
                font-weight: 680;
            }
            QWidget#ScriptEditPanel QPushButton#ToolButton,
            QWidget#ScriptEditPanel QToolButton#ScriptEditProviderSetupButton {
                color: #DCE2EA;
                background: #15181D;
                border: 1px solid #2B3037;
                border-radius: 5px;
                padding: 5px 8px;
                font-weight: 620;
            }
            QWidget#ScriptEditPanel QPushButton#DangerToolButton {
                color: #F4E9E6;
                background: #352522;
                border: 1px solid #6C4D45;
                border-radius: 5px;
                padding: 5px 9px;
                font-weight: 680;
            }
            QWidget#ScriptEditPanel QPushButton:hover,
            QWidget#ScriptEditPanel QToolButton:hover {
                border-color: #68717E;
                background-color: #20252B;
            }
            QWidget#ScriptEditPanel QScrollBar::add-line:vertical,
            QWidget#ScriptEditPanel QScrollBar::sub-line:vertical {
                height: 0;
            }
            """
            + editor_scrollbar_qss("QWidget#ScriptEditPanel")
        )

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("ScriptEditScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget(self._scroll_area)
        content.setObjectName("ScriptEditScrollContent")
        content.setMinimumWidth(0)
        body = QVBoxLayout(content)
        body.setContentsMargins(6, 6, 6, 6)
        body.setSpacing(5)
        self._scroll_area.setWidget(content)
        root.addWidget(self._scroll_area, stretch=1)

        prompt_label = QLabel("AI 편집 프롬프트", content)
        self._prompt_label = prompt_label
        prompt_label.setObjectName("ScriptEditSummary")
        prompt_label.setWordWrap(True)
        body.addWidget(prompt_label)

        self._provider_host = QWidget(content)
        provider_row = QHBoxLayout(self._provider_host)
        provider_row.setContentsMargins(0, 0, 0, 0)
        provider_row.setSpacing(4)
        self._provider_combo = QComboBox(self._provider_host)
        self._provider_combo.setObjectName("ScriptEditProviderCombo")
        self._provider_combo.setMinimumHeight(24)
        self._provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        provider_row.addWidget(self._provider_combo, stretch=1)
        self._provider_setup_btn = QToolButton(self._provider_host)
        self._provider_setup_btn.setObjectName("ScriptEditProviderSetupButton")
        self._provider_setup_btn.setIcon(app_icon("settings", size=12, color="#DDE3EA"))
        self._provider_setup_btn.setIconSize(icon_size(12))
        self._provider_setup_btn.setFixedSize(24, 24)
        self._provider_setup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._provider_setup_btn.setToolTip("선택한 AI 설치/연결 방법")
        self._provider_setup_btn.clicked.connect(self._show_provider_setup_dialog)
        provider_row.addWidget(self._provider_setup_btn)
        self._provider_detail_label = QLabel("", content)
        self._provider_detail_label.setObjectName("ScriptEditSummary")
        self._provider_detail_label.setTextFormat(Qt.TextFormat.RichText)
        self._provider_detail_label.setWordWrap(False)
        self._provider_detail_label.setMaximumHeight(18)
        body.addWidget(self._provider_host)
        body.addWidget(self._provider_detail_label)

        self._prompt_input = QPlainTextEdit(content)
        self._prompt_input.setObjectName("ScriptEditPromptInput")
        self._prompt_input.setPlaceholderText(
            "예: 군더더기 빼고 자막 만들어줘 / 쇼츠 후보 만들어줘 / 제품 데모처럼 정리해줘"
        )
        self._prompt_input.setMinimumHeight(52)
        self._prompt_input.setMaximumHeight(70)
        body.addWidget(self._prompt_input)

        self._prompt_action_host = QWidget(content)
        prompt_row = QHBoxLayout(self._prompt_action_host)
        prompt_row.setContentsMargins(0, 0, 0, 0)
        prompt_row.setSpacing(4)
        prompt_btn = QPushButton("AI Plan", self._prompt_action_host)
        self._prompt_btn = prompt_btn
        prompt_btn.setObjectName("PrimaryToolButton")
        prompt_btn.setIcon(app_icon("ai-script", size=13, color="#DDE3EA"))
        prompt_btn.setIconSize(icon_size(13))
        prompt_btn.setMinimumHeight(26)
        prompt_btn.clicked.connect(self.generate_from_prompt)
        prompt_row.addWidget(prompt_btn)
        self._prompt_mode_label = QLabel("Local AI 없음: 규칙 모드로 안전하게 플랜 생성", self._prompt_action_host)
        self._prompt_mode_label.setObjectName("ScriptEditSummary")
        self._prompt_mode_label.setWordWrap(False)
        self._prompt_mode_label.setMaximumHeight(18)
        prompt_row.addWidget(self._prompt_mode_label, stretch=1)
        body.addWidget(self._prompt_action_host)

        self._transcript_tools_host = QWidget(content)
        import_row = QGridLayout(self._transcript_tools_host)
        import_row.setContentsMargins(0, 0, 0, 0)
        import_row.setHorizontalSpacing(4)
        import_row.setVerticalSpacing(4)
        self._format_combo = QComboBox(self._transcript_tools_host)
        self._format_combo.setMinimumHeight(26)
        for fmt in ("auto", "srt", "vtt"):
            self._format_combo.addItem(fmt.upper(), fmt)
        import_row.addWidget(self._format_combo, 0, 0)
        import_text_btn = QPushButton("대본 불러오기", self._transcript_tools_host)
        self._import_text_btn = import_text_btn
        import_text_btn.setObjectName("ToolButton")
        import_text_btn.setMinimumHeight(26)
        import_text_btn.clicked.connect(self.import_transcript_from_text)
        import_row.addWidget(import_text_btn, 0, 1)
        import_media_btn = QPushButton("음성인식", self._transcript_tools_host)
        self._import_media_btn = import_media_btn
        import_media_btn.setObjectName("ToolButton")
        import_media_btn.setMinimumHeight(26)
        import_media_btn.setIcon(app_icon("ai-script", size=12, color="#DDE3EA"))
        import_media_btn.setIconSize(icon_size(12))
        import_media_btn.clicked.connect(self._choose_media_for_transcription)
        import_row.addWidget(import_media_btn, 1, 0)
        import_file_btn = QPushButton("파일", self._transcript_tools_host)
        self._import_file_btn = import_file_btn
        import_file_btn.setObjectName("ToolButton")
        import_file_btn.setMinimumHeight(26)
        import_file_btn.clicked.connect(self._choose_transcript_file)
        import_row.addWidget(import_file_btn, 1, 1)
        import_row.setColumnStretch(0, 1)
        import_row.setColumnStretch(1, 1)
        body.addWidget(self._transcript_tools_host)

        self._transcript_input = QPlainTextEdit(content)
        self._transcript_input.setPlaceholderText("SRT 또는 WebVTT 대본을 붙여넣으세요.")
        self._transcript_input.setMinimumHeight(70)
        body.addWidget(self._transcript_input)

        self._segments_list = QListWidget(content)
        self._segments_list.setMinimumHeight(86)
        self._segments_list.currentRowChanged.connect(self._sync_range_controls_to_segment)
        body.addWidget(self._segments_list)

        form_host = QWidget(content)
        self._manual_controls_host = form_host
        form = QFormLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(5)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        self._action_combo = QComboBox(form_host)
        self._action_combo.setMinimumHeight(24)
        for action_id, label in SCRIPT_EDIT_ACTIONS:
            self._action_combo.addItem(label, action_id)
        form.addRow("수동 레시피", self._action_combo)
        self._style_edit = QLineEdit(DEFAULT_CAPTION_STYLE, form_host)
        self._style_edit.setMinimumHeight(24)
        form.addRow("자막 스타일", self._style_edit)
        self._min_silence_spin = QSpinBox(form_host)
        self._min_silence_spin.setRange(100, 30_000)
        self._min_silence_spin.setValue(700)
        self._min_silence_spin.setSuffix(" ms")
        self._min_silence_spin.setMinimumHeight(24)
        form.addRow("무음 기준", self._min_silence_spin)
        range_row = QHBoxLayout()
        range_row.setSpacing(4)
        self._range_start_spin = QSpinBox(form_host)
        self._range_start_spin.setRange(0, 100_000)
        self._range_start_spin.setMinimumHeight(24)
        self._range_end_spin = QSpinBox(form_host)
        self._range_end_spin.setRange(1, 100_000)
        self._range_end_spin.setMinimumHeight(24)
        range_row.addWidget(self._range_start_spin)
        range_row.addWidget(self._range_end_spin)
        form.addRow("텍스트 범위", range_row)
        body.addWidget(form_host)

        self._silence_input = QPlainTextEdit(content)
        self._silence_input.setPlaceholderText("선택: 무음 구간(ms)을 줄마다 입력: 3000-4200")
        self._silence_input.setMinimumHeight(42)
        self._silence_input.setMaximumHeight(56)
        body.addWidget(self._silence_input)

        self._manual_generate_host = QWidget(content)
        generate_row = QHBoxLayout(self._manual_generate_host)
        generate_row.setContentsMargins(0, 0, 0, 0)
        generate_row.setSpacing(4)
        generate_btn = QPushButton("수동 플랜", self._manual_generate_host)
        self._manual_generate_btn = generate_btn
        generate_btn.setObjectName("PrimaryToolButton")
        generate_btn.setMinimumHeight(26)
        generate_btn.clicked.connect(self.generate_current_action)
        generate_row.addWidget(generate_btn)
        preview_btn = QPushButton("미리보기", self._manual_generate_host)
        self._manual_preview_btn = preview_btn
        preview_btn.setObjectName("ToolButton")
        preview_btn.setMinimumHeight(26)
        preview_btn.clicked.connect(lambda: self.preview_requested.emit(self.model.current_plan))
        generate_row.addWidget(preview_btn)
        body.addWidget(self._manual_generate_host)

        self._review_hint_label = QLabel("AI Plan 검토: 적용할 카드와 작업만 체크한 뒤 아래 적용 버튼을 누르세요.", content)
        self._review_hint_label.setObjectName("ScriptEditSummary")
        self._review_hint_label.setWordWrap(True)
        self._review_hint_label.setVisible(False)
        body.addWidget(self._review_hint_label)

        self._summary_label = QLabel("", content)
        self._summary_label.setWordWrap(True)
        self._summary_label.setObjectName("ScriptEditSummary")
        body.addWidget(self._summary_label)

        self._warnings_list = QListWidget(content)
        self._warnings_list.setMinimumHeight(46)
        self._warnings_list.setMaximumHeight(62)
        body.addWidget(self._warnings_list)

        self._cards_list = QListWidget(content)
        self._cards_list.setMinimumHeight(78)
        self._cards_list.itemChanged.connect(self._sync_selected_from_ui)
        body.addWidget(self._cards_list)

        self._operations_list = QListWidget(content)
        self._operations_list.setMinimumHeight(116)
        self._operations_list.itemChanged.connect(self._sync_selected_from_ui)
        body.addWidget(self._operations_list)
        body.addStretch(1)

        apply_row = QHBoxLayout()
        apply_row.setSpacing(4)
        apply_selected_btn = QPushButton("선택 적용", self)
        apply_selected_btn.setObjectName("PrimaryToolButton")
        apply_selected_btn.setMinimumHeight(28)
        apply_selected_btn.clicked.connect(self._emit_apply_selected)
        apply_row.addWidget(apply_selected_btn)
        apply_all_btn = QPushButton("전체 적용", self)
        apply_all_btn.setObjectName("ToolButton")
        apply_all_btn.setMinimumHeight(28)
        apply_all_btn.clicked.connect(self.apply_all_requested.emit)
        apply_row.addWidget(apply_all_btn)
        apply_cuts_btn = QPushButton("컷 실제 적용", self)
        apply_cuts_btn.setObjectName("DangerToolButton")
        apply_cuts_btn.setMinimumHeight(28)
        apply_cuts_btn.setToolTip("선택된 삭제/컷 제안을 실제 타임라인 ripple cut으로 적용합니다.")
        apply_cuts_btn.clicked.connect(self._emit_apply_cuts)
        apply_row.addWidget(apply_cuts_btn)
        root.addLayout(apply_row)

    def import_transcript_from_text(self) -> TranscriptDocument:
        fmt = str(self._format_combo.currentData() or "auto")
        document = self.model.import_transcript_text(self._transcript_input.toPlainText(), source_format=fmt)
        self._refresh_transcript_rows()
        self._refresh_plan_view()
        return document

    def import_transcript_file_path(self, path: str | Path, *, source_format: str = "auto") -> TranscriptDocument:
        document = self.model.import_transcript_file_path(path, source_format=source_format)
        try:
            self._transcript_input.setPlainText(Path(path).read_text(encoding="utf-8-sig"))
        except Exception:
            pass
        self._refresh_transcript_rows()
        self._refresh_plan_view()
        return document

    def _choose_transcript_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import transcript",
            str(Path.home()),
            "Transcript files (*.srt *.vtt);;All files (*.*)",
        )
        if path:
            self.import_transcript_file_path(path, source_format=str(self._format_combo.currentData() or "auto"))

    def _choose_media_for_transcription(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Local speech recognition",
            str(Path.home()),
            "Media files (*.mp4 *.mov *.mkv *.avi *.webm *.mp3 *.wav *.m4a *.flac *.aac *.ogg);;All files (*.*)",
        )
        if path:
            self.import_transcript_from_media_path(path)

    def import_transcript_from_media_path(self, path: str | Path, *, language: str = "") -> TranscriptDocument | None:
        try:
            from app.local_ml import local_ml_transcribe_media
        except Exception as exc:
            self._prompt_mode_label.setText(f"로컬 음성인식 사용 불가: {exc}")
            return None
        result = local_ml_transcribe_media(path, language=language or "")
        if not result.get("ok"):
            reason = str(result.get("reason") or "unknown")
            actions = result.get("actions") or []
            action_text = f" / {actions[0]}" if actions else ""
            self._prompt_mode_label.setText(f"로컬 음성인식 대기: {reason}{action_text}")
            return None
        segments = [row for row in (result.get("segments") or []) if isinstance(row, Mapping)]
        srt_text = _segments_to_srt_text(segments)
        if not srt_text:
            self._prompt_mode_label.setText("로컬 음성인식 결과가 비어 있습니다.")
            return None
        self._format_combo.setCurrentIndex(max(0, self._format_combo.findData("srt")))
        self._transcript_input.setPlainText(srt_text)
        document = self.model.import_transcript_text(
            srt_text,
            source_format="srt",
            document_id=f"script_edit_{Path(path).stem}_local_stt",
            language=str(result.get("language") or language or self.model.language),
        )
        self._prompt_mode_label.setText(f"로컬 음성인식 완료: {len(document.segments)}개 구간")
        self._refresh_transcript_rows()
        self._refresh_plan_view()
        return document

    def clear_transcript_context(self, *, clear_plan: bool = False) -> None:
        self.model.clear_transcript_context(clear_plan=clear_plan)
        self._transcript_input.clear()
        self._segments_list.clear()
        self._range_start_spin.setRange(0, 100_000)
        self._range_end_spin.setRange(1, 100_000)
        self._range_start_spin.setValue(0)
        self._range_end_spin.setValue(1)
        if clear_plan:
            self._refresh_plan_view()

    def set_silence_intervals(self, intervals: Sequence[Mapping[str, Any]]) -> None:
        self.model.set_silence_intervals(intervals)
        self._silence_input.setPlainText("\n".join(f"{item['start_ms']}-{item['end_ms']}" for item in self.model.silence_intervals))

    def _collect_plan_kwargs(self) -> dict[str, Any]:
        parsed_silences = _parse_silence_intervals_text(self._silence_input.toPlainText())
        if parsed_silences:
            self.model.set_silence_intervals(parsed_silences)
        return {
            "style_preset_id": self._style_edit.text().strip() or DEFAULT_CAPTION_STYLE,
            "min_duration_ms": self._min_silence_spin.value(),
            "segment_id": self._selected_segment_id(),
            "start_char": self._range_start_spin.value(),
            "end_char": self._range_end_spin.value(),
        }

    def generate_from_prompt(self) -> EditPlan:
        prompt = self._prompt_input.toPlainText().strip()
        provider_id = self._selected_provider_id()
        if is_ai_provider_status_prompt(prompt, provider_id):
            state = provider_user_state(provider_id=provider_id)
            plan = EditPlan(
                id="provider_status_only",
                intent="prompt_only_edit_request",
                summary=f"{state.get('selected_label', 'AI')} 상태: {state.get('headline')}",
                operations=(),
                warnings=("provider status only",),
                quality_score=45,
                metadata={
                    "prompt_text": prompt,
                    "prompt_mode": "command_only",
                    "provider_id": provider_id,
                    "effective_generation_provider": state.get("effective_generation_provider"),
                    "transcript_required": False,
                    "status_detail": state.get("detail"),
                    "next_action": state.get("next_action"),
                },
            )
            self.model.current_plan = plan
            self.model.set_selected_operation_ids([])
            self.model.set_selected_card_ids([])
            self._prompt_mode_label.setText(self._provider_status_short_text(provider_id))
            self._prompt_mode_label.setToolTip(self._provider_status_text(provider_id))
            self._refresh_plan_view()
            self.plan_generated.emit(plan)
            return plan
        if self.model.document is None:
            self.import_transcript_from_text()
        plan = self.model.generate_plan_from_prompt(prompt, **self._collect_plan_kwargs())
        provider_result = generate_selected_provider_plan(prompt, plan, document=self.model.document)
        provider_note = ""
        if provider_result.ok and provider_result.plan is not None:
            plan = provider_result.plan
            self.model.current_plan = plan
            self.model.set_selected_operation_ids([operation.id for operation in plan.operations])
            self.model.set_selected_card_ids([card.id for card in plan.review_cards])
            provider_note = f"{provider_user_label(provider_result.provider)}가 만든 플랜"
        elif provider_result.provider != "rule_based":
            provider_note = str(provider_result.reason or "").strip()
        resolved = str((plan.metadata or {}).get("prompt_resolved_action") or "")
        idx = self._action_combo.findData(resolved)
        if idx >= 0:
            self._action_combo.setCurrentIndex(idx)
        provider_label = self._provider_status_short_text(self._selected_provider_id())
        suffix = provider_note or f"기본 자동 규칙: {resolved or plan.intent}"
        full_status = f"{self._provider_status_text(self._selected_provider_id())} | {suffix}"
        display_suffix = "규칙 모드로 플랜 생성" if provider_note and len(provider_note) > 24 else suffix
        self._prompt_mode_label.setText(self._compact_status_text(display_suffix, limit=34))
        self._prompt_mode_label.setToolTip(full_status)
        self._refresh_plan_view()
        self.plan_generated.emit(plan)
        return plan

    def generate_current_action(self) -> EditPlan:
        if self.model.document is None:
            self.import_transcript_from_text()
        plan = self.model.generate_plan(
            str(self._action_combo.currentData() or "transcript_to_captions"),
            **self._collect_plan_kwargs(),
        )
        self._refresh_plan_view()
        self.plan_generated.emit(plan)
        return plan

    def selected_operation_ids(self, *, include_cards: bool = True) -> list[str]:
        self._sync_selected_from_ui()
        return self.model.selected_operation_ids(include_cards=include_cards)

    def selected_card_ids(self) -> list[str]:
        self._sync_selected_from_ui()
        return self.model.selected_card_ids()

    def current_plan(self) -> EditPlan | None:
        return self.model.current_plan

    def select_transcript_range(self, segment_id: str, start_char: int, end_char: int) -> dict[str, Any]:
        selection = self.model.select_transcript_range(segment_id, start_char, end_char)
        self._range_start_spin.setValue(int(selection["start_char"]))
        self._range_end_spin.setValue(int(selection["end_char"]))
        return selection

    def generate_selection_scoped_plan(self, actions: Sequence[str] = ("caption", "zoom", "highlight")) -> EditPlan:
        plan = self.model.generate_selection_scoped_plan(actions)
        self._refresh_plan_view()
        self.plan_generated.emit(plan)
        return plan

    def build_sentence_move_preview(
        self,
        *,
        source_segment_id: str,
        before_segment_id: str | None = None,
        after_segment_id: str | None = None,
        destination_ms: int | None = None,
    ) -> dict[str, Any]:
        return self.model.build_sentence_move_preview(
            source_segment_id=source_segment_id,
            before_segment_id=before_segment_id,
            after_segment_id=after_segment_id,
            destination_ms=destination_ms,
        )

    def apply_transcript_reflow(self, cut_ranges: Sequence[dict[str, Any]]) -> TranscriptDocument:
        document = self.model.apply_transcript_reflow(cut_ranges)
        self._refresh_transcript_rows()
        self._refresh_plan_view()
        return document

    def prepare_editable_script(
        self,
        *,
        speaker_turns: Sequence[Mapping[str, Any]] | None = None,
        glossary: Mapping[str, str] | None = None,
    ) -> TranscriptDocument:
        document = self.model.prepare_editable_script(speaker_turns=speaker_turns, glossary=glossary)
        self._refresh_transcript_rows()
        self._refresh_plan_view()
        return document

    def set_review_mode(self, enabled: bool = True) -> None:
        """Switch the panel from script-entry mode to Plan review/apply mode."""
        self._review_mode = bool(enabled)
        edit_widgets = (
            "_prompt_label",
            "_provider_host",
            "_prompt_input",
            "_prompt_action_host",
            "_transcript_tools_host",
            "_transcript_input",
            "_segments_list",
            "_manual_controls_host",
            "_silence_input",
            "_manual_generate_host",
        )
        for name in edit_widgets:
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(not self._review_mode)
        hint = getattr(self, "_review_hint_label", None)
        if hint is not None:
            hint.setVisible(self._review_mode)
            if self._review_mode:
                hint.setText(self._review_hint_for_plan(self.model.current_plan))
        if self._review_mode:
            self.setMinimumWidth(680)
        else:
            self.setMinimumWidth(0)

    def set_plan(self, plan: EditPlan | None) -> None:
        self.model.current_plan = plan
        if plan is not None:
            self.model.set_selected_operation_ids([operation.id for operation in plan.operations])
            self.model.set_selected_card_ids([card.id for card in plan.review_cards])
        hint = getattr(self, "_review_hint_label", None)
        if hint is not None and getattr(self, "_review_mode", False):
            hint.setText(self._review_hint_for_plan(plan))
        self._refresh_plan_view()

    def _review_hint_for_plan(self, plan: EditPlan | None) -> str:
        if plan is None:
            return "AI Plan 검토: 먼저 Plan을 만든 뒤 적용할 카드와 작업만 체크하세요."
        metadata = dict(getattr(plan, "metadata", {}) or {})
        prompt_text = " ".join(str(metadata.get("prompt_text") or "").split())
        prompt_mode = str(metadata.get("prompt_mode") or "").casefold()
        if prompt_mode == "command_only" or getattr(plan, "intent", "") == "prompt_only_edit_request":
            suffix = f" 입력한 명령: {prompt_text}" if prompt_text else ""
            return (
                "AI 명령 검토: 이 화면은 자막 입력창이 아니라 편집 작업 확인 화면입니다."
                f"{suffix} 작업이 없으면 아직 실제 타임라인 변경이 적용되지 않습니다."
            )
        if prompt_text:
            return f"AI Plan 검토: `{prompt_text}` 요청으로 만든 작업입니다. 체크한 항목만 적용됩니다."
        return "AI Plan 검토: 적용할 카드와 작업만 체크한 뒤 아래 적용 버튼을 누르세요."

    def _selected_segment_id(self) -> str:
        item = self._segments_list.currentItem()
        if item is not None:
            return str(item.data(Qt.ItemDataRole.UserRole) or "")
        if self.model.document and self.model.document.segments:
            return self.model.document.segments[0].id
        return ""

    def _refresh_transcript_rows(self) -> None:
        self._segments_list.clear()
        document = self.model.document
        if document is None:
            return
        for segment in document.segments:
            label = f"{segment.id}  {_format_ms(segment.start_ms)}-{_format_ms(segment.end_ms)}  {segment.text}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, segment.id)
            self._segments_list.addItem(item)
        if self._segments_list.count() and self._segments_list.currentRow() < 0:
            self._segments_list.setCurrentRow(0)

    def _sync_range_controls_to_segment(self, row: int) -> None:
        document = self.model.document
        if document is None or row < 0 or row >= len(document.segments):
            return
        segment = document.segments[row]
        text_len = max(1, len(segment.text))
        self._range_start_spin.setRange(0, text_len - 1)
        self._range_end_spin.setRange(1, text_len)
        self._range_start_spin.setValue(0)
        self._range_end_spin.setValue(text_len)

    def _refresh_plan_view(self) -> None:
        plan = self.model.current_plan
        preview = edit_plan_preview(plan)
        counts = preview.get("operation_counts") or {}
        counts_text = ", ".join(f"{key}: {value}" for key, value in counts.items()) or "no operations"
        prompt_only = False
        if plan is not None:
            metadata = dict(getattr(plan, "metadata", {}) or {})
            prompt_only = (
                str(metadata.get("prompt_mode") or "").casefold() == "command_only"
                or getattr(plan, "intent", "") == "prompt_only_edit_request"
            )
        if prompt_only and not (getattr(plan, "operations", ()) if plan is not None else ()):
            self._summary_label.setText(
                f"{preview.get('summary')}\n"
                "아직 적용할 작업이 없습니다. 이 명령은 자막으로 변환되지 않았고, Review에서 실제 변경도 발생하지 않습니다."
            )
        else:
            self._summary_label.setText(
                f"{preview.get('summary')}\n"
                f"Operations: {counts_text} | Affected: {_format_ms(preview.get('affected_duration_ms', 0))} | "
                f"Quality: {preview.get('quality_score', 0)}"
            )
        self._warnings_list.clear()
        for warning in preview.get("warnings") or []:
            self._warnings_list.addItem(str(warning))

        self._cards_list.blockSignals(True)
        self._cards_list.clear()
        for card in preview.get("review_cards") or []:
            op_count = len(card.get("operation_ids") or [])
            score = int(card.get("quality_score", 0) or 0)
            reason = str(card.get("reason") or "").strip()
            label = f"{card.get('title') or card.get('id')}  |  작업 {op_count}개  |  점수 {score}"
            if reason:
                label = f"{label}\n{reason}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, str(card.get("id") or ""))
            item.setToolTip(reason or label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._cards_list.addItem(item)
        self._cards_list.blockSignals(False)

        self._operations_list.blockSignals(True)
        self._operations_list.clear()
        for operation in preview.get("operations") or []:
            span = ""
            if operation.get("start_ms") is not None and operation.get("end_ms") is not None:
                span = f" {_format_ms(operation.get('start_ms'))}-{_format_ms(operation.get('end_ms'))}"
            op_type = str(operation.get("type") or "")
            reason = str(operation.get("reason", "") or "")
            text = str(operation.get("text", "") or "").strip()
            preview_text = f" - {text[:52]}" if text else ""
            item = QListWidgetItem(f"{op_type}{span}{preview_text}\n{reason}")
            item.setData(Qt.ItemDataRole.UserRole, str(operation.get("id") or ""))
            item.setToolTip(f"{operation.get('id')}  {op_type}{span}\n{reason}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self._operations_list.addItem(item)
        self._operations_list.blockSignals(False)
        self._sync_selected_from_ui()

    def _refresh_provider_status(self) -> None:
        try:
            statuses = ai_provider_readiness()
            snapshot = provider_snapshot()
            mcp = snapshot.get("automation_mcp") or {}
            self._provider_status = statuses
            combo = getattr(self, "_provider_combo", None)
            if combo is not None:
                self._loading_provider_combo = True
                combo.blockSignals(True)
                combo.clear()
                for provider_id in snapshot.get("provider_order") or statuses.keys():
                    row = statuses.get(str(provider_id)) or {}
                    if not row:
                        continue
                    combo.addItem(
                        f"{provider_user_label(str(provider_id))} ({provider_state_label(row)})",
                        str(provider_id),
                    )
                current = selected_ai_provider_id()
                idx = combo.findData(current)
                if idx < 0:
                    idx = combo.findData("rule_based")
                combo.setCurrentIndex(max(0, idx))
                combo.blockSignals(False)
            lines = [
                f"{row.get('label')}: {'ready' if row.get('available') else 'not ready'} - {row.get('reason')}"
                for row in statuses.values()
            ]
            if mcp:
                lines.append(f"MCP server: {mcp.get('server_command')}")
                lines.append("MCP tools: " + ", ".join(str(item) for item in mcp.get("tool_names") or []))
            self._prompt_mode_label.setToolTip("\n".join(lines))
            self._update_provider_status_labels()
            self._loading_provider_combo = False
        except Exception as exc:
            self._loading_provider_combo = False
            self._provider_status = {}
            self._prompt_mode_label.setText(f"AI Provider: rule-based fallback ({exc})")

    def _selected_provider_id(self) -> str:
        combo = getattr(self, "_provider_combo", None)
        if combo is not None and combo.currentIndex() >= 0:
            value = combo.currentData()
            if value:
                return str(value)
        return selected_ai_provider_id()

    def _provider_status_text(self, provider_id: str | None = None) -> str:
        selected = str(provider_id or selected_ai_provider_id())
        state = provider_user_state(provider_id=selected)
        detail = str(state.get("detail") or "").strip()
        next_action = str(state.get("next_action") or "").strip()
        parts = [str(state.get("headline") or provider_status_label()).strip()]
        if detail:
            parts.append(detail)
        if next_action:
            parts.append(f"다음: {next_action}")
        return " ".join(part for part in parts if part)

    def _provider_status_short_text(self, provider_id: str | None = None) -> str:
        selected = str(provider_id or selected_ai_provider_id())
        state = provider_user_state(provider_id=selected)
        label = str(state.get("selected_label") or provider_user_label(selected)).strip()
        badge = str(state.get("mode_badge") or state.get("provider_state") or "").strip()
        effective = str(state.get("effective_label") or "").strip()
        parts = [label]
        if badge:
            parts.append(badge)
        if effective and effective != label:
            parts.append(effective)
        text = " · ".join(part for part in parts if part)
        return text if len(text) <= 44 else text[:43].rstrip() + "..."

    def _compact_status_text(self, text: str, *, limit: int = 54) -> str:
        clean = " ".join(str(text or "").split())
        return clean if len(clean) <= limit else clean[: max(0, limit - 3)].rstrip() + "..."

    def _visible_with_hidden_contract_text(self, visible: str, hidden: str) -> str:
        return (
            f"{_html_escape(str(visible or ''))}"
            f"<span style=\"font-size:0px;color:transparent\"> "
            f"{_html_escape(str(hidden or ''))}</span>"
        )

    def _update_provider_status_labels(self) -> None:
        provider_id = self._selected_provider_id()
        row = (getattr(self, "_provider_status", None) or {}).get(provider_id) or {}
        state = provider_user_state(provider_id=provider_id)
        text = self._provider_status_text(provider_id)
        short_text = self._provider_status_short_text(provider_id)
        interaction = provider_interaction_model(provider_id, row)
        detail = getattr(self, "_provider_detail_label", None)
        if detail is not None:
            detail.setText(self._visible_with_hidden_contract_text(short_text, text))
            detail.setToolTip(text)
        self._prompt_mode_label.setText(short_text)
        self._prompt_mode_label.setToolTip(text)
        prompt_btn = getattr(self, "_prompt_btn", None)
        if prompt_btn is not None:
            prompt_btn.setText(str(state.get("action_label") or interaction.get("run_label") or "AI Plan"))
            prompt_btn.setToolTip(str(interaction.get("summary") or text))
        prompt = getattr(self, "_prompt_input", None)
        if prompt is not None:
            prompt.setPlaceholderText(str(state.get("placeholder") or interaction.get("placeholder") or prompt.placeholderText()))

    def _on_provider_changed(self, *_args: Any) -> None:
        provider_id = self._selected_provider_id()
        if not getattr(self, "_loading_provider_combo", False):
            save_ai_provider_preference(provider_id)
        self._update_provider_status_labels()

    def _show_provider_setup_dialog(self) -> None:
        provider_id = self._selected_provider_id()
        handler = getattr(self, "_external_provider_setup_handler", None)
        if callable(handler) and provider_id in {"qwen_local", "claude_mcp", "local_llm"}:
            self.provider_setup_requested.emit(provider_id)
            handler(provider_id)
            return
        if provider_id == "local_llm":
            self._show_local_llm_setup_dialog()
            return
        info = provider_setup_instructions(provider_id)
        message = QMessageBox(self)
        message.setWindowTitle(str(info.get("title") or "AI 연결 안내"))
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(str(info.get("summary") or "선택한 AI 연결 방법입니다."))
        message.setInformativeText(str(info.get("body") or ""))
        message.setDetailedText(
            "\n".join(
                str(value)
                for key, value in info.items()
                if key not in {"title", "summary", "body", "primary_action"} and value
            )
        )
        message.exec()

    def _show_local_llm_setup_dialog(self) -> bool:
        current = str(saved_local_llm_config().get("command") or "").strip()
        command, ok = QInputDialog.getText(
            self,
            "로컬 LLM 설정",
            "EditPlan JSON을 stdout으로 반환하는 로컬 LLM 실행 명령:",
            QLineEdit.EchoMode.Normal,
            current,
        )
        if not ok:
            return False
        command = str(command or "").strip()
        if not command:
            QMessageBox.information(
                self,
                "로컬 LLM 설정",
                "실행 명령이 비어 있습니다. 로컬 LLM을 사용하려면 runner 명령을 입력해야 합니다.",
            )
            return False
        saved = save_local_llm_provider_config(command=command)
        try:
            save_ai_provider_preference("local_llm")
        except Exception:
            pass
        self._refresh_provider_status()
        if not saved:
            QMessageBox.warning(self, "로컬 LLM 설정", "실행 명령을 앱 설정에 저장하지 못했습니다.")
            return False
        row = (getattr(self, "_provider_status", None) or ai_provider_readiness()).get("local_llm") or {}
        if row.get("available"):
            QMessageBox.information(
                self,
                "로컬 LLM 연결 완료",
                "로컬 LLM 실행 명령을 저장했고, 지금부터 AI Plan 생성에 사용할 수 있습니다.",
            )
            return True
        QMessageBox.warning(
            self,
            "로컬 LLM 확인 필요",
            "실행 명령은 저장했지만, 현재 실행 파일을 찾지 못했습니다. 명령의 첫 번째 실행 파일 경로 또는 PATH 등록을 확인하세요.",
        )
        return False

    def _checked_ids(self, list_widget: QListWidget) -> list[str]:
        ids: list[str] = []
        for idx in range(list_widget.count()):
            item = list_widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(str(item.data(Qt.ItemDataRole.UserRole) or ""))
        return [item for item in ids if item]

    def _sync_selected_from_ui(self, *_args: Any) -> None:
        self.model.set_selected_operation_ids(self._checked_ids(self._operations_list))
        self.model.set_selected_card_ids(self._checked_ids(self._cards_list))

    def _emit_apply_selected(self) -> None:
        self.apply_selected_requested.emit(self.selected_operation_ids(include_cards=True))

    def _emit_apply_cuts(self) -> None:
        self.apply_cuts_requested.emit(self.selected_operation_ids(include_cards=True))
