"""Hover-wheel numeric controls for Painter brush parameters."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSpinBox, QWidget


class PainterHoverWheelSpinBox(QSpinBox):
    """A spin box that responds to the wheel without requiring a prior click."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._wheel_remainder = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)

    def fit_display_text(
        self,
        text: str,
        *,
        minimum_px: int = 72,
        chrome_px: int = 38,
    ) -> int:
        """Reserve enough width for the full value, suffix, and step buttons."""
        text_width = int(self.fontMetrics().horizontalAdvance(str(text)))
        width = max(int(minimum_px), text_width + int(chrome_px))
        self.setFixedWidth(width)
        return width

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        delta = int(event.angleDelta().y())
        if delta == 0:
            delta = int(event.pixelDelta().y()) * 8
        self._wheel_remainder += delta
        notches = int(self._wheel_remainder / 120)
        if notches:
            self._wheel_remainder -= notches * 120
            multiplier = (
                5
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                else 1
            )
            self.setValue(self.value() + notches * self.singleStep() * multiplier)
        event.accept()


__all__ = ["PainterHoverWheelSpinBox"]
