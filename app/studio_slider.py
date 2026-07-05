from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QBrush
from PySide6.QtWidgets import QSlider, QWidget


class StudioSlider(QSlider):
    """Shared horizontal editor slider with the renewed soft-glass shape."""

    def __init__(
        self,
        kind: str = "neutral",
        parent: QWidget | None = None,
        *,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
    ) -> None:
        super().__init__(orientation, parent)
        self._studio_slider_kind = kind
        if orientation == Qt.Orientation.Horizontal:
            self.setMinimumHeight(22)
            self.setMaximumHeight(24)
        self.setMouseTracking(True)

    def set_kind(self, kind: str) -> None:
        self._studio_slider_kind = kind
        self.update()

    def kind(self) -> str:
        return self._studio_slider_kind

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        if self.orientation() != Qt.Orientation.Horizontal:
            super().paintEvent(event)
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(8, 0, -8, 0)
        cy = r.center().y()
        left = float(r.left())
        right = float(r.right())
        width = max(1.0, right - left)
        denom = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / denom
        hx = left + width * max(0.0, min(1.0, float(ratio)))

        def _rail_gradient() -> QLinearGradient:
            grad = QLinearGradient(QPointF(left, cy), QPointF(right, cy))
            kind = self._studio_slider_kind
            if kind == "temperature":
                grad.setColorAt(0.0, QColor("#3E8BE8"))
                grad.setColorAt(0.48, QColor("#AEB7C6"))
                grad.setColorAt(1.0, QColor("#E4A244"))
            elif kind == "tint":
                grad.setColorAt(0.0, QColor("#55A86D"))
                grad.setColorAt(0.50, QColor("#9BA7B4"))
                grad.setColorAt(1.0, QColor("#B855B8"))
            elif kind == "audio":
                grad.setColorAt(0.0, QColor("#587C67"))
                grad.setColorAt(0.50, QColor("#9BA7B4"))
                grad.setColorAt(1.0, QColor("#B7C8A2"))
            elif kind == "accent":
                grad.setColorAt(0.0, QColor("#6B7788"))
                grad.setColorAt(0.52, QColor("#BAC2CE"))
                grad.setColorAt(1.0, QColor("#7F8FB0"))
            else:
                grad.setColorAt(0.0, QColor(174, 183, 198, 52))
                grad.setColorAt(0.50, QColor(216, 222, 231, 120))
                grad.setColorAt(1.0, QColor(174, 183, 198, 52))
            return grad

        shadow_pen = QPen(QColor(0, 0, 0, 150), 4.2)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(shadow_pen)
        p.drawLine(QPointF(left, cy + 0.7), QPointF(right, cy + 0.7))

        base_pen = QPen(QColor(255, 255, 255, 28), 2.2)
        base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(base_pen)
        p.drawLine(QPointF(left, cy), QPointF(right, cy))

        rail_pen = QPen(QBrush(_rail_gradient()), 2.4)
        rail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(rail_pen)
        p.drawLine(QPointF(left, cy), QPointF(right, cy))

        hi_pen = QPen(QColor(255, 255, 255, 95), 1.0)
        hi_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(hi_pen)
        p.drawLine(QPointF(left, cy - 0.8), QPointF(hx, cy - 0.8))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 115))
        p.drawEllipse(QPointF(hx, cy + 1.2), 6.9, 6.9)
        p.setBrush(QColor("#87909B"))
        p.setPen(QPen(QColor(218, 224, 232, 165), 1.1))
        p.drawEllipse(QPointF(hx, cy), 5.8, 5.8)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 72))
        p.drawEllipse(QPointF(hx - 1.7, cy - 1.8), 1.7, 1.7)
        p.setBrush(QColor(35, 40, 47, 110))
        p.drawEllipse(QPointF(hx, cy), 2.3, 2.3)
