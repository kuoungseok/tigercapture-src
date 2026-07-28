"""Canvas-local commands shown only while editing a UI vector path."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text


class PainterUIVectorContextBar(QFrame):
    command_requested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIVectorContextBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._state: dict[str, Any] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(3)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("PainterUIVectorContextSummary")
        layout.addWidget(self.summary_label)
        layout.addWidget(self._separator())
        self.line_button = self._button("Straight", "line", "line")
        self.curve_button = self._button("Bezier", "curve", "motion")
        self.split_button = self._button("Split", "split", "scissors")
        self.close_button = self._button("Close", "toggle_closed", "link")
        self.delete_button = self._button(
            "Delete node",
            "delete_node",
            "trash",
        )
        layout.addWidget(self.line_button)
        layout.addWidget(self.curve_button)
        layout.addWidget(self.split_button)
        layout.addWidget(self.close_button)
        layout.addWidget(self.delete_button)
        layout.addWidget(self._separator())
        self.exit_button = self._button("Exit vector edit", "exit", "x")
        layout.addWidget(self.exit_button)
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
        object_id = str(self._state.get("object_id") or "")
        if not object_id:
            self.hide()
            return
        node_id = str(self._state.get("node_id") or "")
        segment_id = str(self._state.get("segment_id") or "")
        node_count = int(self._state.get("node_count") or 0)
        self.summary_label.setText(
            f"{painter_text('Vector')}  {node_count} "
            f"{painter_text('nodes')}"
        )
        for button in (self.line_button, self.curve_button, self.split_button):
            button.setEnabled(bool(segment_id))
        self.delete_button.setEnabled(bool(node_id))
        closed = bool(self._state.get("closed", False))
        self.close_button.setIcon(
            app_icon(
                "unlink" if closed else "link",
                size=13,
                color="#E5EBF4",
            )
        )
        self.close_button.setToolTip(
            painter_text("Open path" if closed else "Close path")
        )
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


__all__ = ["PainterUIVectorContextBar"]
