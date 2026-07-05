from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.style import editor_scrollbar_qss


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


class CreatorAssistPanel(QWidget):
    """Editor-side creator workflow review panel.

    This intentionally avoids a template-first launcher flow. It reviews the
    current editor/media-pool state and exposes creator actions inside the
    normal TigerCapture workspace.
    """

    analyze_requested = Signal()
    apply_requested = Signal()
    preview_short_requested = Signal()
    queue_exports_requested = Signal()
    copy_publish_requested = Signal()
    open_templates_requested = Signal()
    quick_create_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(0)
        self._bundle: dict[str, Any] = {}
        self._panel_model: dict[str, Any] = {}
        self.setObjectName("CreatorAssistPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        self._summary = QLabel("현재 미디어풀과 타임라인을 분석해 자막, 쇼츠 구간, 리프레임, 게시 문안을 제안합니다.")
        self._summary.setWordWrap(True)
        self._summary.setObjectName("CreatorAssistSummary")
        root.addWidget(self._summary)

        self._cards = QListWidget()
        self._cards.setObjectName("CreatorAssistCards")
        self._cards.setMinimumHeight(118)
        self._cards.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._cards.currentItemChanged.connect(lambda *_: self._refresh_detail())
        root.addWidget(self._cards, stretch=1)

        self._detail = QLabel("아직 분석 전입니다.")
        self._detail.setObjectName("CreatorAssistDetail")
        self._detail.setWordWrap(True)
        self._detail.setMinimumHeight(42)
        root.addWidget(self._detail)

        option_row = QHBoxLayout()
        option_row.setSpacing(5)
        self._option_checks: dict[str, QCheckBox] = {}
        for key, label in (
            ("subtitles", "자막"),
            ("markers", "쇼츠"),
            ("settings", "출력"),
            ("queue_exports", "큐"),
        ):
            check = QCheckBox(label)
            check.setObjectName("CreatorAssistOption")
            check.setChecked(True)
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            check.toggled.connect(self._refresh_apply_preview)
            self._option_checks[key] = check
            option_row.addWidget(check)
        if "storyboard" not in self._option_checks:
            check = QCheckBox("Shots")
            check.setObjectName("CreatorAssistOption")
            check.setChecked(True)
            check.setCursor(Qt.CursorShape.PointingHandCursor)
            check.toggled.connect(self._refresh_apply_preview)
            self._option_checks["storyboard"] = check
            option_row.addWidget(check)
        option_row.addStretch(1)
        root.addLayout(option_row)

        self._apply_preview = QLabel("분석 후 적용할 항목을 선택할 수 있습니다.")
        self._apply_preview.setObjectName("CreatorAssistDetail")
        self._apply_preview.setWordWrap(True)
        root.addWidget(self._apply_preview)

        self._quick_flow = QLabel("빠른 제작은 현재 프로젝트 분석 후 사용할 수 있습니다.")
        self._quick_flow.setObjectName("CreatorAssistDetail")
        self._quick_flow.setWordWrap(True)
        root.addWidget(self._quick_flow)

        self._run_status = QLabel("대기 중")
        self._run_status.setObjectName("CreatorAssistRunStatus")
        self._run_status.setWordWrap(True)
        root.addWidget(self._run_status)

        actions = QGridLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setHorizontalSpacing(4)
        actions.setVerticalSpacing(4)
        self.analyze_btn = QPushButton("분석")
        self.quick_btn = QPushButton("빠른 제작")
        self.apply_btn = QPushButton("적용")
        self.preview_btn = QPushButton("미리보기")
        self.queue_btn = QPushButton("큐 추가")
        self.copy_btn = QPushButton("복사")
        for idx, btn in enumerate((
            self.analyze_btn,
            self.quick_btn,
            self.apply_btn,
            self.preview_btn,
            self.queue_btn,
            self.copy_btn,
        )):
            btn.setObjectName("ToolButton")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(28)
            actions.addWidget(btn, idx // 2, idx % 2)
        actions.setColumnStretch(0, 1)
        actions.setColumnStretch(1, 1)
        root.addLayout(actions)

        self.analyze_btn.clicked.connect(self.analyze_requested.emit)
        self.quick_btn.clicked.connect(self.quick_create_requested.emit)
        self.apply_btn.clicked.connect(self.apply_requested.emit)
        self.preview_btn.clicked.connect(self.preview_short_requested.emit)
        self.queue_btn.clicked.connect(self.queue_exports_requested.emit)
        self.copy_btn.clicked.connect(self.copy_publish_requested.emit)
        self._apply_studio_style()
        self.set_bundle({})

    def _apply_studio_style(self) -> None:
        self.setStyleSheet(
            """
            QWidget#CreatorAssistPanel {
                background: #101112;
                color: #E6EAF2;
                font-family: "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
                font-size: 10px;
            }
            QLabel#CreatorAssistSummary {
                color: #AEB5BF;
                font-size: 10px;
                line-height: 1.25;
            }
            QLabel#CreatorAssistDetail {
                color: #BAC1CB;
                background: #121417;
                border: 1px solid #252A31;
                border-radius: 5px;
                padding: 6px 7px;
                line-height: 1.22;
            }
            QLabel#CreatorAssistRunStatus {
                color: #9FA7B1;
                background: #0E0F10;
                border: 1px solid #24282E;
                border-radius: 5px;
                padding: 5px 7px;
            }
            QListWidget#CreatorAssistCards {
                color: #DCE2EA;
                background: #0F1012;
                border: 1px solid #24282F;
                border-radius: 5px;
                padding: 3px;
                outline: none;
            }
            QListWidget#CreatorAssistCards::item {
                color: #DCE2EA;
                background: #15181D;
                border: 1px solid #282D35;
                border-radius: 4px;
                padding: 5px 6px;
                margin: 2px 1px;
            }
            QListWidget#CreatorAssistCards::item:selected,
            QListWidget#CreatorAssistCards::item:hover {
                color: #F2F5FA;
                background: #1D2228;
                border-color: #566171;
            }
            QCheckBox#CreatorAssistOption {
                color: #D2D8E0;
                spacing: 5px;
                font-size: 10px;
                font-weight: 650;
            }
            QCheckBox#CreatorAssistOption::indicator {
                width: 13px;
                height: 13px;
                border-radius: 3px;
                border: 1px solid #444B55;
                background: #15181D;
            }
            QCheckBox#CreatorAssistOption::indicator:checked {
                background: #5C6878;
                border-color: #8792A1;
            }
            QPushButton#ToolButton {
                color: #DCE2EA;
                background: #15181D;
                border: 1px solid #2B3037;
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 10px;
                font-weight: 650;
            }
            QPushButton#ToolButton:hover {
                background: #20252B;
                border-color: #68717E;
            }
            QPushButton#ToolButton:pressed {
                background: #111316;
                border-color: #515A66;
            }
            QPushButton#ToolButton:disabled {
                color: #5E6670;
                background: #111316;
                border-color: #22262C;
            }
            """
            + editor_scrollbar_qss("QWidget#CreatorAssistPanel")
        )

    def set_bundle(self, bundle: Mapping[str, Any] | None) -> None:
        self._bundle = dict(bundle or {})
        self._panel_model = _as_dict(self._bundle.get("review_panel"))
        self._cards.clear()
        cards = [_as_dict(card) for card in _as_list(self._panel_model.get("cards"))]
        for card in cards:
            label = str(card.get("label") or card.get("id") or "Card")
            summary = str(card.get("summary") or "")
            ready = "준비" if bool(card.get("ready")) else "확인"
            item = QListWidgetItem(f"{ready}  {label}\n{summary}")
            item.setData(Qt.ItemDataRole.UserRole, card)
            self._cards.addItem(item)
        counts = _as_dict(self._panel_model.get("counts"))
        if self._bundle:
            parts = [
                f"쇼츠 {int(counts.get('short_candidates', 0) or 0)}개",
                f"자막 비트 {int(counts.get('caption_beats', 0) or 0)}개",
                f"내보내기 {int(counts.get('render_jobs', 0) or 0)}개",
            ]
            self._summary.setText("Creator Assist: " + " · ".join(parts))
        else:
            self._summary.setText("현재 미디어풀과 타임라인을 분석해 자막, 쇼츠 구간, 리프레임, 게시 문안을 제안합니다.")
        has_bundle = bool(self._bundle.get("ok") or cards)
        try:
            from app.capcut_workflow import capcut_quick_create_button_model

            quick = capcut_quick_create_button_model({
                **self._bundle,
                "review_panel": self._panel_model,
            })
        except Exception:
            quick = {"enabled": False, "steps": [], "summary": {}}
        ready_steps = [str(step.get("label") or "") for step in _as_list(quick.get("steps")) if _as_dict(step).get("ready")]
        if ready_steps:
            self._quick_flow.setText("빠른 제작: " + " → ".join(ready_steps[:4]))
        elif has_bundle:
            self._quick_flow.setText("빠른 제작: 적용 가능한 자막, 쇼츠, 출력 항목을 더 확인하세요.")
        else:
            self._quick_flow.setText("빠른 제작은 현재 프로젝트 분석 후 사용할 수 있습니다.")
        self.quick_btn.setEnabled(bool(quick.get("enabled")))
        self.apply_btn.setEnabled(has_bundle and any(self.selected_apply_options().values()))
        self.preview_btn.setEnabled(bool(_as_list(self._bundle.get("timeline_markers"))))
        self.queue_btn.setEnabled(bool(_as_list(self._bundle.get("render_queue_jobs"))))
        handoff = _as_dict(self._bundle.get("publish_handoff"))
        self.copy_btn.setEnabled(bool(_as_dict(handoff.get("clipboard_payloads")).get("title")))
        self._refresh_apply_preview()
        if self._cards.count():
            self._cards.setCurrentRow(0)
        else:
            self._detail.setText("아직 분석 전입니다.")

    def bundle(self) -> dict[str, Any]:
        return dict(self._bundle)

    def selected_apply_options(self) -> dict[str, bool]:
        return {
            key: bool(check.isChecked())
            for key, check in self._option_checks.items()
        }

    def select_quick_create_options(self) -> None:
        for check in self._option_checks.values():
            check.setChecked(True)
        self._refresh_apply_preview()

    def set_busy(self, busy: bool, message: str = "") -> None:
        text = message or ("빠른 제작 실행 중..." if busy else "대기 중")
        self._run_status.setText(text)
        for btn in (self.analyze_btn, self.quick_btn, self.apply_btn, self.preview_btn, self.queue_btn, self.copy_btn):
            btn.setEnabled(False if busy else btn.isEnabled())
        if not busy:
            self.set_bundle(self._bundle)

    def set_last_result(self, result: Mapping[str, Any] | None) -> None:
        data = _as_dict(result)
        if not data:
            self._run_status.setText("대기 중")
            return
        parts = []
        for key, label in (
            ("subtitles", "자막"),
            ("markers", "쇼츠"),
            ("settings", "설정"),
            ("queued", "큐"),
            ("storyboard_zoom_windows", "줌"),
            ("storyboard_callouts", "콜아웃"),
            ("storyboard_templates", "템플릿"),
        ):
            if key in data:
                parts.append(f"{label} {data.get(key)}")
        message = " · ".join(parts) if parts else str(data.get("message") or "적용 완료")
        self._run_status.setText("마지막 결과: " + message)

    def _refresh_apply_preview(self) -> None:
        if not self._bundle:
            self._apply_preview.setText("분석 후 적용할 항목을 선택할 수 있습니다.")
            if hasattr(self, "apply_btn"):
                self.apply_btn.setEnabled(False)
            return
        options = self.selected_apply_options()
        subtitle_count = len(_as_list(self._bundle.get("subtitle_rows")))
        marker_count = len(_as_list(self._bundle.get("timeline_markers")))
        queue_count = len(_as_list(self._bundle.get("render_queue_jobs")))
        storyboard = _as_dict(self._bundle.get("ltx_storyboard"))
        storyboard_effects = _as_dict(self._bundle.get("ltx_storyboard_effect_materialization"))
        storyboard_effect_counts = _as_dict(storyboard_effects.get("counts"))
        storyboard_variations = _as_dict(self._bundle.get("ltx_storyboard_variations"))
        storyboard_templates = _as_dict(self._bundle.get("ltx_storyboard_template_recommendations"))
        shot_count = int(storyboard.get("shot_count", 0) or 0)
        zoom_count = int(storyboard_effect_counts.get("zoom_windows", 0) or 0)
        callout_count = int(storyboard_effect_counts.get("callouts", 0) or 0)
        variation_count = int(storyboard_variations.get("variation_count", 0) or 0)
        template_count = int(storyboard_templates.get("card_count", 0) or 0)
        has_settings = bool(_as_dict(self._bundle.get("project_settings_patch")) or _as_dict(self._bundle.get("export_settings")))
        parts: list[str] = []
        if options.get("storyboard"):
            parts.append(
                f"샷카드 {shot_count}개 · 줌 {zoom_count}개 · 콜아웃 {callout_count}개 · "
                f"리테이크 {variation_count}개 · 템플릿 {template_count}개"
            )
        if options.get("subtitles"):
            parts.append(f"자막 {subtitle_count}개")
        if options.get("markers"):
            parts.append(f"쇼츠 마커 {marker_count}개")
        if options.get("settings"):
            parts.append("출력/리프레임 설정" if has_settings else "출력 설정 없음")
        if options.get("queue_exports"):
            parts.append(f"렌더 큐 {queue_count}개")
        self._apply_preview.setText("적용 예정: " + (" | ".join(parts) if parts else "선택된 항목 없음"))
        if hasattr(self, "apply_btn"):
            self.apply_btn.setEnabled(any(options.values()))

    def _refresh_detail(self) -> None:
        item = self._cards.currentItem()
        if item is None:
            self._detail.setText("선택된 카드가 없습니다.")
            return
        card = _as_dict(item.data(Qt.ItemDataRole.UserRole))
        rows = _as_list(card.get("rows"))
        detail = str(card.get("summary") or card.get("label") or "준비됨")
        if rows:
            first = _as_dict(rows[0])
            first_label = str(first.get("label") or first.get("text") or first.get("hook_text") or "").strip()
            if first_label:
                detail = f"{detail}\n첫 항목: {first_label}"
        if str(card.get("kind") or "") == "ltx_storyboard":
            effects = _as_dict(card.get("effect_materialization"))
            effect_counts = _as_dict(effects.get("counts"))
            variations = _as_list(card.get("variations"))
            templates = _as_list(card.get("template_recommendations"))
            detail = (
                f"{detail}\n"
                f"줌 {int(effect_counts.get('zoom_windows', 0) or 0)}개 | "
                f"콜아웃 {int(effect_counts.get('callouts', 0) or 0)}개 | "
                f"리테이크 {len(variations)}개 | 템플릿 추천 {len(templates)}개 | "
                "검토 후 타임라인에 반영됩니다."
            )
        self._detail.setText(detail)
