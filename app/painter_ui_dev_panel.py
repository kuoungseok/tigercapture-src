"""Compact Inspect/Dev panel for Painter UI Designer."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
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


def _text(source: str) -> str:
    translated = painter_text(source)
    if translated != source:
        return translated
    return _DEV_TRANSLATIONS.get(current_language(), {}).get(source, source)


class PainterUIDevPanel(QWidget):
    ready_set_requested = Signal(str, str, bool, str)
    annotation_add_requested = Signal(str, str, str)
    revision_compare_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIDevPanel")
        self._report: dict[str, Any] = {}
        layout = QVBoxLayout(self)
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

        annotation_title = QLabel(_text("Pinned annotations"))
        annotation_title.setObjectName("PaintSectionTitle")
        layout.addWidget(annotation_title)
        annotation_row = QHBoxLayout()
        self.annotation_edit = QLineEdit()
        self.annotation_edit.setPlaceholderText(_text("Add developer note"))
        self.annotation_button = QPushButton(_text("Add"))
        self.annotation_button.clicked.connect(self._emit_annotation)
        annotation_row.addWidget(self.annotation_edit, 1)
        annotation_row.addWidget(self.annotation_button)
        layout.addLayout(annotation_row)
        self.annotation_list = QListWidget()
        self.annotation_list.setMaximumHeight(96)
        layout.addWidget(self.annotation_list)

        self.compare_button = QPushButton(_text("Compare revision"))
        self.compare_button.clicked.connect(self.revision_compare_requested)
        layout.addWidget(self.compare_button)
        layout.addStretch(1)
        self.set_report(None)

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
        self.annotation_add_requested.emit("object", str(row.get("id") or ""), text)
        self.annotation_edit.clear()

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
        ):
            control.setEnabled(enabled)
        self.delivery_list.clear()
        self.annotation_list.clear()
        if not objects:
            self.summary.setText(
                _text("Select a UI object to inspect developer values.")
            )
            self.metrics.clear()
            self.ready_check.setChecked(False)
            self.ready_note.clear()
            return
        if len(objects) > 1:
            self.summary.setText(
                painter_text("{count} objects selected").format(count=len(objects))
            )
            self.metrics.setText(
                _text("Measurements are shown for the selection bounds.")
            )
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
        for annotation in self._report.get("annotations") or []:
            item = QListWidgetItem(str(annotation.get("text") or ""))
            item.setToolTip(str(annotation.get("id") or ""))
            self.annotation_list.addItem(item)


__all__ = ["PainterUIDevPanel"]
