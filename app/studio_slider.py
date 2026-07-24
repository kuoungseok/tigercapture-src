from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPen, QBrush
from PySide6.QtWidgets import QSlider, QWidget


class StudioSlider(QSlider):
    """Shared horizontal editor slider with the renewed soft-glass shape."""

    _RAIL_INSET = 8.0

    def __init__(
        self,
        kind: str = "neutral",
        parent: QWidget | None = None,
        *,
        orientation: Qt.Orientation = Qt.Orientation.Horizontal,
    ) -> None:
        super().__init__(orientation, parent)
        self._studio_slider_kind = kind
        self._studio_dragging = False
        self._studio_hovering = False
        self._studio_led_level = 0.0
        self._studio_led_phase = 0.0
        self._studio_led_timer = QTimer(self)
        self._studio_led_timer.setInterval(33)
        self._studio_led_timer.timeout.connect(self._advance_led_animation)
        if orientation == Qt.Orientation.Horizontal:
            self.setMinimumHeight(30)
            self.setMaximumHeight(32)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def set_kind(self, kind: str) -> None:
        self._studio_slider_kind = kind
        self.update()

    def kind(self) -> str:
        return self._studio_slider_kind

    def _rail_left_right(self) -> tuple[float, float]:
        rect = self.rect().adjusted(int(self._RAIL_INSET), 0, -int(self._RAIL_INSET), 0)
        left = float(rect.left())
        right = float(rect.right())
        if right <= left:
            right = left + 1.0
        return left, right

    def _position_ratio(self, x: float) -> float:
        left, right = self._rail_left_right()
        ratio = (float(x) - left) / max(1.0, right - left)
        ratio = max(0.0, min(1.0, ratio))
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        return ratio

    def _value_from_x(self, x: float) -> int:
        span = max(0, self.maximum() - self.minimum())
        return int(round(self.minimum() + self._position_ratio(x) * span))

    def _handle_x(self) -> float:
        left, right = self._rail_left_right()
        span = max(1, self.maximum() - self.minimum())
        ratio = (self.value() - self.minimum()) / span
        ratio = max(0.0, min(1.0, float(ratio)))
        if self.invertedAppearance():
            ratio = 1.0 - ratio
        return left + (right - left) * ratio

    def _led_color(self) -> QColor:
        colors = {
            "audio": "#7EF0C6",
            "temperature": "#88C7FF",
            "tint": "#D58BFF",
            "accent": "#FFE1A0",
            "neutral": "#FFE7B8",
        }
        return QColor(colors.get(self._studio_slider_kind, "#FFE1A0"))

    def _wake_led(self, level: float = 1.0) -> None:
        self._studio_led_level = max(self._studio_led_level, max(0.0, min(1.0, float(level))))
        if not self._studio_led_timer.isActive():
            self._studio_led_timer.start()
        self.update()

    def _advance_led_animation(self) -> None:
        target = 1.0 if self._studio_dragging or self.isSliderDown() else 0.0
        speed = 0.22 if target > self._studio_led_level else 0.085
        self._studio_led_level += (target - self._studio_led_level) * speed
        self._studio_led_phase = (self._studio_led_phase + 0.19) % math.tau
        if target <= 0.0 and self._studio_led_level < 0.015:
            self._studio_led_level = 0.0
            self._studio_led_timer.stop()
        self.update()

    def _set_from_mouse_x(self, x: float) -> None:
        value = max(self.minimum(), min(self.maximum(), self._value_from_x(x)))
        self.setSliderPosition(value)
        if self.hasTracking():
            self.setValue(value)
        if self._studio_dragging:
            self._wake_led(1.0)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.orientation() != Qt.Orientation.Horizontal or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._studio_dragging = True
        self._studio_hovering = True
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.setSliderDown(True)
        self._wake_led(1.0)
        self._set_from_mouse_x(event.position().x())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.orientation() == Qt.Orientation.Horizontal and self._studio_dragging:
            self._set_from_mouse_x(event.position().x())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.orientation() == Qt.Orientation.Horizontal and self._studio_dragging:
            if event.button() == Qt.MouseButton.LeftButton:
                self._set_from_mouse_x(event.position().x())
                if not self.hasTracking():
                    self.setValue(self.sliderPosition())
                self._studio_dragging = False
                self.setSliderDown(False)
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                event.accept()
                return
        super().mouseReleaseEvent(event)

    def enterEvent(self, event) -> None:  # pragma: no cover - visual interaction
        if self.orientation() == Qt.Orientation.Horizontal:
            self._studio_hovering = True
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # pragma: no cover - visual interaction
        if self.orientation() == Qt.Orientation.Horizontal and not self._studio_dragging:
            self._studio_hovering = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        if self.orientation() != Qt.Orientation.Horizontal:
            super().paintEvent(event)
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(int(self._RAIL_INSET), 0, -int(self._RAIL_INSET), 0)
        cy = r.center().y()
        left = float(r.left())
        right = float(r.right())
        hx = self._handle_x()

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

        active = self._studio_dragging or self._studio_hovering or self.hasFocus()
        if active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(186, 197, 211, 36 if not self._studio_dragging else 58))
            p.drawEllipse(QPointF(hx, cy), 11.8, 11.8)
            p.setPen(QPen(QColor(225, 232, 242, 74 if not self._studio_dragging else 115), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(hx, cy), 9.4, 9.4)

        led_level = max(0.0, min(1.0, self._studio_led_level))
        if led_level > 0.001:
            pulse = 0.68 + math.sin(self._studio_led_phase) * 0.32
            led_alpha = led_level * pulse
            led_color = self._led_color()
            glow_half = max(26.0, min(72.0, (right - left) * 0.16))
            glow_left = max(left, hx - glow_half)
            glow_right = min(right, hx + glow_half)

            def _local_led_gradient(alpha_scale: float) -> QLinearGradient:
                grad = QLinearGradient(QPointF(glow_left, cy), QPointF(glow_right, cy))
                edge = QColor(led_color)
                edge.setAlpha(0)
                shoulder = QColor(led_color)
                shoulder.setAlpha(int(56 * led_alpha * alpha_scale))
                hot = QColor("#FFF7D8")
                hot.setAlpha(int(142 * led_alpha * alpha_scale))
                grad.setColorAt(0.0, edge)
                grad.setColorAt(0.30, shoulder)
                grad.setColorAt(0.50, hot)
                grad.setColorAt(0.70, shoulder)
                grad.setColorAt(1.0, edge)
                return grad

            for width, alpha_scale in ((10.0, 0.45), (5.8, 0.72), (2.2, 1.0)):
                local_glow_pen = QPen(QBrush(_local_led_gradient(alpha_scale)), width)
                local_glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(local_glow_pen)
                p.drawLine(QPointF(glow_left, cy), QPointF(glow_right, cy))

            p.setPen(Qt.PenStyle.NoPen)
            glow_outer = QColor(led_color)
            glow_outer.setAlpha(int(34 * led_alpha))
            p.setBrush(glow_outer)
            p.drawEllipse(QPointF(hx, cy), 16.0, 16.0)
            glow_inner = QColor(led_color)
            glow_inner.setAlpha(int(58 * led_alpha))
            p.setBrush(glow_inner)
            p.drawEllipse(QPointF(hx, cy), 10.8, 10.8)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 115))
        p.drawEllipse(QPointF(hx, cy + 1.2), 8.8, 8.8)
        p.setBrush(QColor("#87909B"))
        p.setPen(QPen(QColor(218, 224, 232, 165), 1.1))
        p.drawEllipse(QPointF(hx, cy), 7.4, 7.4)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 72))
        p.drawEllipse(QPointF(hx - 1.9, cy - 2.0), 1.9, 1.9)
        p.setBrush(QColor(35, 40, 47, 110))
        p.drawEllipse(QPointF(hx, cy), 2.7, 2.7)
        if led_level > 0.001:
            led_core = self._led_color()
            led_core.setAlpha(int(135 + 95 * led_level))
            p.setBrush(led_core)
            p.setPen(QPen(QColor(245, 250, 255, int(90 + 80 * led_level)), 0.9))
            p.drawEllipse(QPointF(hx, cy), 3.1, 3.1)
        p.setPen(QPen(QColor(235, 240, 247, 130), 1.0))
        p.drawLine(QPointF(hx - 2.4, cy - 3.0), QPointF(hx - 2.4, cy + 3.0))
        p.drawLine(QPointF(hx + 2.4, cy - 3.0), QPointF(hx + 2.4, cy + 3.0))
