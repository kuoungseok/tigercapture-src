"""Transient Boolean commands for a compatible UI multi-selection."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text


class PainterUIBooleanContextBar(QFrame):
    command_requested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIBooleanContextBar")
        self.setAccessibleName(painter_text("Boolean operations"))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._state: dict[str, Any] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(3)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("PainterUIVectorContextSummary")
        self.summary_label.setAccessibleName(painter_text("Boolean selection"))
        layout.addWidget(self.summary_label)
        layout.addWidget(self._separator())
        self.operation_buttons: dict[str, QPushButton] = {}
        for label, command, icon_name, shortcut in (
            ("Union selection", "union", "boolean-union", "Alt+Shift+U"),
            ("Subtract selection", "subtract", "boolean-subtract", "Alt+Shift+S"),
            ("Intersect selection", "intersect", "boolean-intersect", "Alt+Shift+I"),
            ("Exclude selection", "exclude", "boolean-exclude", "Alt+Shift+E"),
        ):
            button = self._button(label, command, icon_name)
            button.setToolTip(f"{painter_text(label)}  {shortcut}")
            button.setCheckable(True)
            self.operation_buttons[command] = button
            layout.addWidget(button)
        layout.addWidget(self._separator())
        self.release_button = self._button(
            "Ungroup Boolean group",
            "release",
            "scissors",
        )
        layout.addWidget(self.release_button)
        self.flatten_button = self._button(
            "Flatten",
            "flatten",
            "flatten",
        )
        self.flatten_button.setToolTip(
            f"{painter_text('Flatten')}  Alt+Shift+F"
        )
        layout.addWidget(self.flatten_button)
        self.hide()

    def _button(self, label: str, command: str, icon_name: str) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("PainterUIVectorContextButton")
        button.setFixedSize(28, 26)
        button.setIcon(app_icon(icon_name, size=13, color="#E5EBF4"))
        button.setIconSize(icon_size(13))
        button.setToolTip(painter_text(label))
        button.setAccessibleName(painter_text(label))
        button.clicked.connect(
            lambda _checked=False, value=command: self.command_requested.emit(
                value
            )
        )
        return button

    @staticmethod
    def _separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("PainterUIToolbarSeparator")
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFixedSize(7, 20)
        return separator

    def set_state(self, value: Mapping[str, Any] | None) -> None:
        self._state = dict(value or {})
        if not self._state.get("eligible"):
            self.hide()
            return
        mode = str(self._state.get("mode") or "selection")
        count = len(self._state.get("selection_ids") or [])
        if mode == "group":
            count = len(self._state.get("operand_ids") or [])
            self.summary_label.setText(
                f"{painter_text('Boolean group')}  {count}"
            )
        else:
            self.summary_label.setText(
                f"{count}  {painter_text('selected')}"
            )
        self.setAccessibleDescription(self.summary_label.text())
        active = str(self._state.get("operation") or "")
        for operation, button in self.operation_buttons.items():
            button.setChecked(mode == "group" and operation == active)
        self.release_button.setVisible(mode == "group")
        self.flatten_button.setVisible(mode == "group")
        self.show()
        self.raise_()

    def state(self) -> dict[str, Any]:
        return dict(self._state)

    def place_above(self, anchor: QWidget, *, gap: int = 6) -> None:
        parent = self.parentWidget()
        if parent is None or not self.isVisible():
            return
        self.adjustSize()
        anchor_point = anchor.mapTo(parent, anchor.rect().topLeft())
        x = anchor_point.x() + (anchor.width() - self.width()) // 2
        x = max(8, min(x, parent.width() - self.width() - 8))
        y = max(8, anchor_point.y() - self.height() - int(gap))
        self.move(x, y)
        self.raise_()


__all__ = ["PainterUIBooleanContextBar"]
