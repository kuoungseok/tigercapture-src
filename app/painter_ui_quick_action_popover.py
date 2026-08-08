"""Transient command palette for Painter UI Design."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from app.icons import app_icon
from app.painter_i18n import painter_text
from app.painter_ui_quick_actions import search_painter_ui_quick_actions


class PainterUIQuickActionPopover(QFrame):
    action_requested = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIQuickActionPopover")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._document: dict[str, Any] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 8)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel(painter_text("Quick Actions"))
        title.setObjectName("PainterUIQuickActionTitle")
        header.addWidget(title)
        header.addStretch(1)
        hint = QLabel("Ctrl+/")
        hint.setObjectName("PainterUIQuickActionHint")
        header.addWidget(hint)
        root.addLayout(header)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("PainterUIQuickActionSearch")
        self.search_edit.setPlaceholderText(
            painter_text(
                "Search commands, layers, pages, components, variables"
            )
        )
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(
            app_icon("search", size=14, color="#9DA9B8"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_edit.textChanged.connect(self._refresh_results)
        self.search_edit.installEventFilter(self)
        root.addWidget(self.search_edit)

        self.result_list = QListWidget()
        self.result_list.setObjectName("PainterUIQuickActionResults")
        self.result_list.setUniformItemSizes(True)
        self.result_list.setTextElideMode(
            Qt.TextElideMode.ElideRight
        )
        self.result_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.result_list.itemActivated.connect(self._request_item)
        self.result_list.itemDoubleClicked.connect(self._request_item)
        self.result_list.installEventFilter(self)
        root.addWidget(self.result_list, 1)

        self.empty_label = QLabel(painter_text("No matching actions"))
        self.empty_label.setObjectName("PainterUIQuickActionEmpty")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        root.addWidget(self.empty_label)

        self.setStyleSheet(
            """
            QFrame#PainterUIQuickActionPopover {
                background: #171B22;
                border: 1px solid #3A4351;
                border-radius: 7px;
            }
            QLabel#PainterUIQuickActionTitle {
                color: #F2F5F8;
                font-size: 13px;
                font-weight: 600;
            }
            QLabel#PainterUIQuickActionHint {
                color: #8D99A8;
                background: #222833;
                border: 1px solid #333C49;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
            }
            QLineEdit#PainterUIQuickActionSearch {
                min-height: 32px;
                color: #EDF2F7;
                background: #0F1319;
                border: 1px solid #465365;
                border-radius: 5px;
                padding: 0 8px;
                selection-background-color: #356DB2;
            }
            QLineEdit#PainterUIQuickActionSearch:focus {
                border-color: #6EA8E8;
            }
            QListWidget#PainterUIQuickActionResults {
                color: #DCE3EB;
                background: transparent;
                border: 0;
                outline: 0;
            }
            QListWidget#PainterUIQuickActionResults::item {
                min-height: 31px;
                border-radius: 4px;
                padding: 2px 7px;
            }
            QListWidget#PainterUIQuickActionResults::item:selected {
                color: #FFFFFF;
                background: #294B70;
            }
            QListWidget#PainterUIQuickActionResults::item:disabled {
                color: #687381;
            }
            QLabel#PainterUIQuickActionEmpty {
                color: #8793A2;
                min-height: 72px;
            }
            """
        )
        self.hide()

    def open_for_document(
        self,
        value: Mapping[str, Any],
        *,
        query: str = "",
    ) -> None:
        self._document = dict(value)
        self.search_edit.setText(str(query))
        self._refresh_results()
        self._place()
        self.show()
        self.raise_()
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def set_document(self, value: Mapping[str, Any]) -> None:
        self._document = dict(value)
        if self.isVisible():
            self._refresh_results()

    def toggle_for_document(self, value: Mapping[str, Any]) -> None:
        if self.isVisible():
            self.hide()
            return
        self.open_for_document(value)

    def _refresh_results(self) -> None:
        report = search_painter_ui_quick_actions(
            self._document,
            self.search_edit.text(),
        )
        self.result_list.clear()
        for row in report["results"]:
            shortcut = str(row.get("shortcut") or "")
            suffix = f"    {shortcut}" if shortcut else ""
            item = QListWidgetItem(
                f"{row['label']}  ·  {row['detail']}{suffix}"
            )
            item.setData(Qt.ItemDataRole.UserRole, dict(row))
            item.setFlags(
                item.flags()
                if row["enabled"]
                else item.flags() & ~Qt.ItemFlag.ItemIsEnabled
            )
            self.result_list.addItem(item)
        self.empty_label.setVisible(self.result_list.count() == 0)
        self.result_list.setVisible(self.result_list.count() > 0)
        if self.result_list.count():
            for index in range(self.result_list.count()):
                item = self.result_list.item(index)
                if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.result_list.setCurrentItem(item)
                    break

    def _request_item(self, item: QListWidgetItem) -> None:
        if not item.flags() & Qt.ItemFlag.ItemIsEnabled:
            return
        payload = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return
        self.hide()
        self.action_requested.emit(payload)

    def _request_current(self) -> None:
        item = self.result_list.currentItem()
        if item is not None:
            self._request_item(item)

    def _move_current(self, delta: int) -> None:
        count = self.result_list.count()
        if not count:
            return
        start = self.result_list.currentRow()
        for offset in range(1, count + 1):
            row = (start + delta * offset) % count
            item = self.result_list.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                self.result_list.setCurrentRow(row)
                return

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() == Qt.Key.Key_Escape:
                self.hide()
                return True
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
                self._request_current()
                return True
            if event.key() == Qt.Key.Key_Down:
                self._move_current(1)
                return True
            if event.key() == Qt.Key.Key_Up:
                self._move_current(-1)
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place()

    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(520, max(120, parent.width() - 16))
        height = min(390, max(120, parent.height() - 32))
        self.resize(width, height)
        self.move(
            max(8, (parent.width() - width) // 2),
            max(24, min(88, (parent.height() - height) // 4)),
        )


__all__ = ["PainterUIQuickActionPopover"]
