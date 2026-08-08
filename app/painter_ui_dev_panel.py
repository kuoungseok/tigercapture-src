"""Compact Inspect/Dev panel for Painter UI Designer."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.painter_i18n import painter_text
from app.i18n import current_language


_DEV_TRANSLATIONS = {
    "ko": {
        "Inspect / Dev": "검사 / 개발",
        "Select a UI object to inspect developer values.": "개발 값을 확인할 UI 객체를 선택하세요.",
        "Ready for development": "개발 준비 완료",
        "Handoff note": "전달 메모",
        "Update status": "상태 업데이트",
        "Delivery": "전달 판정",
        "Pinned annotations": "고정 주석",
        "Add developer note": "개발 메모 추가",
        "Add": "추가",
        "Compare revision": "리비전 비교",
        "Measurements are shown for the selection bounds.": "선택 영역 경계의 측정값을 표시합니다.",
    },
    "ja": {
        "Inspect / Dev": "検査 / 開発",
        "Ready for development": "開発準備完了",
        "Delivery": "配信判定",
        "Pinned annotations": "固定注釈",
        "Add": "追加",
    },
    "zh": {
        "Inspect / Dev": "检查 / 开发",
        "Ready for development": "开发就绪",
        "Delivery": "交付判定",
        "Pinned annotations": "固定注释",
        "Add": "添加",
    },
}

_DEV_EXTRA_TRANSLATIONS = {
    "ko": {
        "Variables": "\ubcc0\uc218",
        "No variables are bound.": "\uc5f0\uacb0\ub41c \ubcc0\uc218\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.",
        "Developer values": "\uac1c\ubc1c\uc790 \uac12",
        "Copy": "\ubcf5\uc0ac",
        "Adapter unavailable": "\uc5b4\ub311\ud130\ub97c \uc0ac\uc6a9\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4",
        "Component": "\ucef4\ud3ec\ub10c\ud2b8",
        "Open Playground": "\ud50c\ub808\uc774\uadf8\ub77c\uc6b4\ub4dc \uc5f4\uae30",
        "States": "\uc0c1\ud0dc",
        "Note": "\uba54\ubaa8",
        "Measurement": "\uce21\uc815",
        "Update": "\uc218\uc815",
        "Delete": "\uc0ad\uc81c",
    },
    "ja": {
        "Variables": "\u5909\u6570",
        "Developer values": "\u958b\u767a\u8005\u5024",
        "Copy": "\u30b3\u30d4\u30fc",
        "Adapter unavailable": "\u30a2\u30c0\u30d7\u30bf\u30fc\u306f\u5229\u7528\u3067\u304d\u307e\u305b\u3093",
        "Component": "\u30b3\u30f3\u30dd\u30fc\u30cd\u30f3\u30c8",
        "Open Playground": "\u30d7\u30ec\u30a4\u30b0\u30e9\u30a6\u30f3\u30c9\u3092\u958b\u304f",
        "States": "\u72b6\u614b",
        "Note": "\u30e1\u30e2",
        "Measurement": "\u8a08\u6e2c",
        "Update": "\u66f4\u65b0",
        "Delete": "\u524a\u9664",
    },
    "zh": {
        "Variables": "\u53d8\u91cf",
        "Developer values": "\u5f00\u53d1\u8005\u503c",
        "Copy": "\u590d\u5236",
        "Adapter unavailable": "\u9002\u914d\u5668\u4e0d\u53ef\u7528",
        "Component": "\u7ec4\u4ef6",
        "Open Playground": "\u6253\u5f00\u8bd5\u9a8c\u573a",
        "States": "\u72b6\u6001",
        "Note": "\u5907\u6ce8",
        "Measurement": "\u6d4b\u91cf",
        "Update": "\u66f4\u65b0",
        "Delete": "\u5220\u9664",
    },
}


def _text(source: str) -> str:
    translated = painter_text(source)
    if translated != source:
        return translated
    language = current_language()
    return _DEV_EXTRA_TRANSLATIONS.get(language, {}).get(
        source,
        _DEV_TRANSLATIONS.get(language, {}).get(source, source),
    )


class PainterUIDevPanel(QWidget):
    ready_set_requested = Signal(str, str, bool, str)
    annotation_add_requested = Signal(str, str, str, str)
    annotation_update_requested = Signal(str, object)
    annotation_remove_requested = Signal(str)
    revision_compare_requested = Signal()
    component_playground_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIDevPanel")
        self._report: dict[str, Any] = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget > QWidget { background: transparent; }"
        )
        self.scroll_area.viewport().setAutoFillBackground(False)
        body = QWidget()
        body.setObjectName("PainterUIDevPanelBody")
        self.scroll_area.setWidget(body)
        outer.addWidget(self.scroll_area)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        title = QLabel(_text("Inspect / Dev"))
        title.setObjectName("PaintSectionTitle")
        layout.addWidget(title)
        self.summary = QLabel(
            _text("Select a UI object to inspect developer values.")
        )
        self.summary.setObjectName("PaintMuted")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        self.ready_card = QFrame()
        self.ready_card.setObjectName("PainterUIDevCard")
        ready_layout = QVBoxLayout(self.ready_card)
        ready_layout.setContentsMargins(7, 7, 7, 7)
        ready_layout.setSpacing(5)
        self.ready_check = QCheckBox(_text("Ready for development"))
        self.ready_note = QLineEdit()
        self.ready_note.setPlaceholderText(_text("Handoff note"))
        self.ready_button = QPushButton(_text("Update status"))
        self.ready_button.clicked.connect(self._emit_ready)
        ready_layout.addWidget(self.ready_check)
        ready_layout.addWidget(self.ready_note)
        ready_layout.addWidget(self.ready_button)
        layout.addWidget(self.ready_card)

        self.metrics = QLabel("")
        self.metrics.setObjectName("PainterUIDevMetrics")
        self.metrics.setWordWrap(True)
        layout.addWidget(self.metrics)

        delivery_title = QLabel(_text("Delivery"))
        delivery_title.setObjectName("PaintSectionTitle")
        layout.addWidget(delivery_title)
        self.delivery_list = QListWidget()
        self.delivery_list.setMaximumHeight(126)
        layout.addWidget(self.delivery_list)

        variables_title = QLabel(_text("Variables"))
        variables_title.setObjectName("PaintSectionTitle")
        layout.addWidget(variables_title)
        self.variable_list = QListWidget()
        self.variable_list.setMaximumHeight(92)
        layout.addWidget(self.variable_list)

        self.component_title = QLabel(_text("Component"))
        self.component_title.setObjectName("PaintSectionTitle")
        layout.addWidget(self.component_title)
        self.component_list = QListWidget()
        self.component_list.setMaximumHeight(118)
        layout.addWidget(self.component_list)
        self.component_button = QPushButton(_text("Open Playground"))
        self.component_button.clicked.connect(self._emit_component_playground)
        layout.addWidget(self.component_button)

        code_title = QLabel(_text("Developer values"))
        code_title.setObjectName("PaintSectionTitle")
        layout.addWidget(code_title)
        code_header = QHBoxLayout()
        self.snippet_combo = QComboBox()
        self.snippet_combo.currentIndexChanged.connect(self._show_snippet)
        self.copy_button = QPushButton(_text("Copy"))
        self.copy_button.clicked.connect(self._copy_snippet)
        code_header.addWidget(self.snippet_combo, 1)
        code_header.addWidget(self.copy_button)
        layout.addLayout(code_header)
        self.snippet_status = QLabel("")
        self.snippet_status.setObjectName("PaintMuted")
        self.snippet_status.setWordWrap(True)
        layout.addWidget(self.snippet_status)
        self.snippet_view = QTextEdit()
        self.snippet_view.setReadOnly(True)
        self.snippet_view.setMaximumHeight(132)
        self.snippet_view.setStyleSheet(
            "QTextEdit {"
            " background: #0D131B;"
            " color: #DCE5F0;"
            " border: 1px solid #2C394A;"
            " border-radius: 4px;"
            " padding: 4px;"
            " font-family: Consolas, monospace;"
            " font-size: 10px;"
            " selection-background-color: #315A88;"
            "}"
        )
        layout.addWidget(self.snippet_view)

        annotation_title = QLabel(_text("Pinned annotations"))
        annotation_title.setObjectName("PaintSectionTitle")
        layout.addWidget(annotation_title)
        annotation_row = QHBoxLayout()
        self.annotation_kind = QComboBox()
        self.annotation_kind.addItem(_text("Note"), "note")
        self.annotation_kind.addItem(_text("Measurement"), "measurement")
        self.annotation_edit = QLineEdit()
        self.annotation_edit.setPlaceholderText(_text("Add developer note"))
        self.annotation_button = QPushButton(_text("Add"))
        self.annotation_button.clicked.connect(self._emit_annotation)
        self.annotation_update_button = QPushButton(_text("Update"))
        self.annotation_update_button.clicked.connect(
            self._emit_annotation_update
        )
        self.annotation_remove_button = QPushButton(_text("Delete"))
        self.annotation_remove_button.clicked.connect(
            self._emit_annotation_remove
        )
        annotation_row.addWidget(self.annotation_kind)
        annotation_row.addWidget(self.annotation_edit, 1)
        layout.addLayout(annotation_row)
        self.annotation_list = QListWidget()
        self.annotation_list.setMaximumHeight(96)
        self.annotation_list.currentItemChanged.connect(
            self._load_annotation
        )
        layout.addWidget(self.annotation_list)
        annotation_actions = QHBoxLayout()
        annotation_actions.addWidget(self.annotation_button)
        annotation_actions.addWidget(self.annotation_update_button)
        annotation_actions.addWidget(self.annotation_remove_button)
        layout.addLayout(annotation_actions)

        self.compare_button = QPushButton(_text("Compare revision"))
        self.compare_button.clicked.connect(self.revision_compare_requested)
        layout.addWidget(self.compare_button)
        layout.addStretch(1)
        self.set_report(None)

    def _snippet(self) -> Mapping[str, Any] | None:
        value = self.snippet_combo.currentData()
        return value if isinstance(value, Mapping) else None

    def _show_snippet(self, *_args) -> None:
        row = self._snippet()
        available = bool(row and row.get("available"))
        code = str(row.get("code") or "") if row else ""
        self.snippet_view.setPlainText(code)
        self.copy_button.setEnabled(available and bool(code))
        self.snippet_view.setVisible(available and bool(code))
        if row is None:
            self.snippet_status.clear()
            return
        unsupported = [str(item) for item in row.get("unsupported") or []]
        if not available:
            self.snippet_status.setText(_text("Adapter unavailable"))
        elif unsupported:
            self.snippet_status.setText(
                f"{row.get('adapter', '')}\n"
                + ", ".join(unsupported)
            )
        else:
            self.snippet_status.setText(str(row.get("adapter") or ""))

    def _copy_snippet(self) -> None:
        row = self._snippet()
        code = str(row.get("code") or "") if row else ""
        if code:
            QApplication.clipboard().setText(code)

    def _emit_component_playground(self) -> None:
        row = self._selection()
        component = row.get("component") if row else None
        if isinstance(component, Mapping) and component.get("id"):
            self.component_playground_requested.emit(str(component["id"]))

    def _selection(self) -> Mapping[str, Any] | None:
        rows = self._report.get("objects")
        return rows[0] if isinstance(rows, list) and len(rows) == 1 else None

    def _emit_ready(self) -> None:
        row = self._selection()
        if row is None:
            return
        self.ready_set_requested.emit(
            "object",
            str(row.get("id") or ""),
            self.ready_check.isChecked(),
            self.ready_note.text().strip(),
        )

    def _emit_annotation(self) -> None:
        row = self._selection()
        text = self.annotation_edit.text().strip()
        if row is None or not text:
            return
        self.annotation_add_requested.emit(
            "object",
            str(row.get("id") or ""),
            text,
            str(self.annotation_kind.currentData() or "note"),
        )
        self.annotation_edit.clear()

    def _selected_annotation(self) -> Mapping[str, Any] | None:
        item = self.annotation_list.currentItem()
        value = item.data(256) if item is not None else None
        return value if isinstance(value, Mapping) else None

    def _load_annotation(self, current, _previous=None) -> None:
        value = current.data(256) if current is not None else None
        annotation = value if isinstance(value, Mapping) else {}
        selected = bool(annotation)
        self.annotation_update_button.setEnabled(selected)
        self.annotation_remove_button.setEnabled(selected)
        if not selected:
            return
        self.annotation_edit.setText(str(annotation.get("text") or ""))
        index = self.annotation_kind.findData(
            str(annotation.get("kind") or "note")
        )
        self.annotation_kind.setCurrentIndex(max(0, index))

    def _emit_annotation_update(self) -> None:
        annotation = self._selected_annotation()
        text = self.annotation_edit.text().strip()
        if annotation is None or not text:
            return
        self.annotation_update_requested.emit(
            str(annotation.get("id") or ""),
            {
                "text": text,
                "kind": str(self.annotation_kind.currentData() or "note"),
            },
        )

    def _emit_annotation_remove(self) -> None:
        annotation = self._selected_annotation()
        if annotation is not None:
            self.annotation_remove_requested.emit(
                str(annotation.get("id") or "")
            )

    def set_report(self, report: Mapping[str, Any] | None) -> None:
        self._report = dict(report or {})
        objects = self._report.get("objects")
        objects = objects if isinstance(objects, list) else []
        single = objects[0] if len(objects) == 1 else None
        enabled = single is not None
        for control in (
            self.ready_check,
            self.ready_note,
            self.ready_button,
            self.annotation_edit,
            self.annotation_button,
            self.annotation_kind,
        ):
            control.setEnabled(enabled)
        self.delivery_list.clear()
        self.variable_list.clear()
        self.component_list.clear()
        self.snippet_combo.clear()
        self.annotation_list.clear()
        self.annotation_update_button.setEnabled(False)
        self.annotation_remove_button.setEnabled(False)
        if not objects:
            self.summary.setText(
                _text("Select a UI object to inspect developer values.")
            )
            self.metrics.clear()
            self.ready_check.setChecked(False)
            self.ready_note.clear()
            self._show_snippet()
            self._set_component_visible(False)
            return
        if len(objects) > 1:
            self.summary.setText(
                painter_text("{count} objects selected").format(count=len(objects))
            )
            self.metrics.setText(
                _text("Measurements are shown for the selection bounds.")
            )
            self._show_snippet()
            self._set_component_visible(False)
            return
        row = single or {}
        self.summary.setText(
            f"{row.get('name', 'UI Object')}  ·  {row.get('kind', '')}"
        )
        ready = row.get("ready") if isinstance(row.get("ready"), Mapping) else {}
        self.ready_check.setChecked(bool(ready.get("ready")))
        self.ready_note.setText(str(ready.get("note") or ""))
        geometry = row.get("geometry") if isinstance(row.get("geometry"), Mapping) else {}
        self.metrics.setText(
            "X {x:.0f}  Y {y:.0f}  W {width:.0f}  H {height:.0f}\n"
            "{tokens} tokens  ·  {interactions} interactions".format(
                x=float(geometry.get("x") or 0),
                y=float(geometry.get("y") or 0),
                width=float(geometry.get("width") or 0),
                height=float(geometry.get("height") or 0),
                tokens=len(row.get("tokens") or []),
                interactions=len(row.get("interaction_ids") or []),
            )
        )
        for delivery in row.get("delivery") or []:
            target = str(delivery.get("target") or "").replace("_", " ").title()
            disposition = str(delivery.get("display_disposition") or "")
            item = QListWidgetItem(f"{target}  ·  {disposition}")
            item.setToolTip(str(delivery.get("reason") or ""))
            self.delivery_list.addItem(item)
        for token in row.get("tokens") or []:
            mode = str(token.get("mode_name") or token.get("mode_id") or "")
            value = token.get("resolved_value")
            item = QListWidgetItem(
                f"{token.get('property', '')}  \u00b7  {token.get('name', '')}"
                f"\n{mode}  \u00b7  {value}"
            )
            chain = " \u2192 ".join(token.get("alias_chain") or [])
            item.setToolTip(
                f"{token.get('collection_name', '')}\n{chain}"
            )
            self.variable_list.addItem(item)
        if not row.get("tokens"):
            item = QListWidgetItem(_text("No variables are bound."))
            self.variable_list.addItem(item)
        component = row.get("component")
        component = component if isinstance(component, Mapping) else {}
        self._set_component_visible(bool(component))
        if component:
            self.component_list.addItem(
                f"{component.get('name', '')}  \u00b7  "
                f"{component.get('role', '')}"
            )
            for variant in component.get("variants") or []:
                marker = "\u25cf" if variant.get("active") else "\u25cb"
                self.component_list.addItem(
                    f"{marker} {variant.get('name', '')}"
                )
            for name, definition in (
                component.get("property_definitions") or {}
            ).items():
                value = (component.get("property_values") or {}).get(name)
                self.component_list.addItem(
                    f"{name}: {value}  \u00b7  {definition.get('type', '')}"
                )
            states = component.get("states") or []
            if states:
                self.component_list.addItem(
                    _text("States") + ": " + ", ".join(states)
                )
        for snippet in row.get("developer_snippets") or []:
            label = str(snippet.get("label") or snippet.get("target") or "")
            if not snippet.get("available"):
                label += "  \u00b7  N/A"
            self.snippet_combo.addItem(label, dict(snippet))
        self._show_snippet()
        for annotation in self._report.get("annotations") or []:
            kind = str(annotation.get("kind") or "note").title()
            item = QListWidgetItem(
                f"{kind}  \u00b7  {annotation.get('text') or ''}"
            )
            item.setToolTip(str(annotation.get("id") or ""))
            item.setData(256, dict(annotation))
            self.annotation_list.addItem(item)

    def _set_component_visible(self, visible: bool) -> None:
        self.component_title.setVisible(visible)
        self.component_list.setVisible(visible)
        self.component_button.setVisible(visible)


__all__ = ["PainterUIDevPanel"]
