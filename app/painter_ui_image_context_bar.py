"""Transient canvas controls for a selected Painter UI image fill."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text


class PainterUIImageContextBar(QFrame):
    command_requested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIImageContextBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._state: dict[str, Any] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(3)
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("PainterUIVectorContextSummary")
        layout.addWidget(self.summary_label)
        layout.addWidget(self._separator())
        self.mode_buttons: dict[str, QPushButton] = {}
        for label, mode, icon_name in (
            ("Fit", "fit", "fit"),
            ("Fill", "fill", "image"),
            ("Stretch", "stretch", "scale"),
            ("Tile", "tile", "grid"),
        ):
            button = self._button(label, mode, icon_name)
            button.setCheckable(True)
            self.mode_buttons[mode] = button
            layout.addWidget(button)
        layout.addWidget(self._separator())
        self.focal_button = self._button(
            "Edit focal point",
            "focal",
            "target",
        )
        self.focal_button.setCheckable(True)
        layout.addWidget(self.focal_button)
        self.original_button = self._button(
            "Original size",
            "original_size",
            "maximize",
        )
        layout.addWidget(self.original_button)
        self.replace_button = self._button(
            "Replace image",
            "replace",
            "repeat",
        )
        layout.addWidget(self.replace_button)
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
        self.summary_label.setText(painter_text("Image"))
        active = str(self._state.get("image_fit") or "fit")
        for mode, button in self.mode_buttons.items():
            button.setChecked(mode == active)
        self.focal_button.setEnabled(active == "fill")
        if active != "fill":
            self.focal_button.setChecked(False)
        self.original_button.setEnabled(
            int(self._state.get("original_width") or 0) > 0
            and int(self._state.get("original_height") or 0) > 0
        )
        self.show()
        self.raise_()

    def set_focal_editing(self, enabled: bool) -> None:
        self.focal_button.blockSignals(True)
        self.focal_button.setChecked(
            bool(enabled) and self.focal_button.isEnabled()
        )
        self.focal_button.blockSignals(False)

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


__all__ = ["PainterUIImageContextBar"]
