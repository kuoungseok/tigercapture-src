"""Circular knob widget for the sound editor UI.

Reusable component with the three input modes the spec calls for:

- Vertical drag (100 px ≈ full range); Shift = 10× precision, Ctrl =
  100× precision, Shift+Ctrl stacks to 1000× precision.
- Mouse wheel (1 % of range per notch by default, shift / ctrl slow).
- Double-click resets to the default value.
- Right-click pops a numeric input dialog.

Other features
--------------
- Color variants (``'blue'``, ``'green'``, ``'orange'``) matching the
  TigerCapture accent palette; any hex string works too.
- Bipolar mode (Pan-style): centered at 12 o'clock with the value arc
  growing toward either side.
- Logarithmic scale for frequency-like parameters.
- Custom formatter callback for the on-screen value string.

Visual layers, drawn via QPainter (mirrors the SVG structure in the
design reference):

1. Outer track ring (grey, 270° span from 7.5 o'clock CW).
2. Value arc (accent color, grows with the value).
3. Knob body (radial gradient).
4. Indicator line from near-center to the rim at the current angle.
5. Label (uppercase) + formatted value, stacked below the knob.
"""
from __future__ import annotations

import math
from typing import Callable

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPen,
    QRadialGradient,
    QWheelEvent,
)
from PySide6.QtWidgets import QInputDialog, QWidget


# Knob angular range: 12 o'clock is 0°, positive angles rotate clockwise.
# The value arc sweeps from -135° (7:30 position) to +135° (4:30).
KNOB_MIN_ANGLE = -135.0
KNOB_MAX_ANGLE = 135.0
KNOB_ANGLE_SPAN = KNOB_MAX_ANGLE - KNOB_MIN_ANGLE  # 270°


# All semantic knob colours collapse to brand orange so the editor
# surface reads as a single accent. The "blue / green / orange / red"
# names are kept as call-site identifiers — callers don't need to
# change — but every name resolves to an orange-family hue.
_COLOR_NAMES = {
    "blue": QColor("#ff7a4a"),     # legacy "blue knob" → orange-light
    "green": QColor("#D85A30"),    # legacy "green knob" → brand orange
    "orange": QColor("#D85A30"),
    "red": QColor("#e54646"),      # destructive only
}


def _resolve_color(c) -> QColor:
    if isinstance(c, QColor):
        return c
    if isinstance(c, str):
        named = _COLOR_NAMES.get(c)
        if named is not None:
            return named
        return QColor(c)
    return QColor("#D85A30")


class KnobWidget(QWidget):
    """A single circular knob. Emits ``valueChanged`` on every change
    (during drag + wheel) and ``editingFinished`` when a drag releases
    or a direct-input dialog commits a new value."""

    valueChanged = Signal(float)
    editingFinished = Signal(float)

    # Widget geometry
    KNOB_SIZE = 72                 # diameter of the knob circle
    CELL_WIDTH = 88                # total widget width (room for text)
    CELL_HEIGHT = 118              # knob + label row + value row

    def __init__(
        self,
        *,
        label: str,
        value: float,
        minimum: float,
        maximum: float,
        default: float,
        unit: str = "",
        color="blue",
        bipolar: bool = False,
        logarithmic: bool = False,
        formatter: Callable[[float], str] | None = None,
        tier: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label = label
        self._value = float(value)
        self._min = float(minimum)
        self._max = float(maximum)
        self._default = float(default)
        self._unit = unit
        self._color = _resolve_color(color)
        self._bipolar = bipolar
        self._log = logarithmic
        self._formatter = formatter
        self._tier = tier

        self._drag_start_y: float = 0.0
        self._drag_start_value: float = 0.0
        self._dragging: bool = False

        self.setFixedSize(self.CELL_WIDTH, self.CELL_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)
        self.setToolTip(self._tooltip_text())

    # -------- public API --------

    def value(self) -> float:
        return self._value

    def setValue(self, value: float, *, emit: bool = True) -> None:
        clamped = max(self._min, min(self._max, float(value)))
        if abs(clamped - self._value) < 1e-9:
            return
        self._value = clamped
        self.update()
        self.setToolTip(self._tooltip_text())
        if emit:
            self.valueChanged.emit(self._value)

    def setLabel(self, label: str) -> None:
        self._label = label
        self.update()

    def setDefault(self, default: float) -> None:
        self._default = float(default)

    # -------- helpers --------

    def _tooltip_text(self) -> str:
        lines = [
            f"{self._label}: {self._format_value()}",
            "Drag ↕ · Wheel · Shift = fine · Ctrl = finer",
            "Double-click = reset · Right-click = enter value",
        ]
        return "\n".join(lines)

    def _value_to_angle(self, value: float) -> float:
        if self._max <= self._min:
            return KNOB_MIN_ANGLE
        if self._log:
            # Guard against non-positive values in log scale.
            lo = max(self._min, 1e-9)
            hi = max(self._max, lo * 1.0001)
            v = max(value, lo)
            norm = (math.log(v) - math.log(lo)) / (math.log(hi) - math.log(lo))
        else:
            norm = (value - self._min) / (self._max - self._min)
        norm = max(0.0, min(1.0, norm))
        return KNOB_MIN_ANGLE + norm * KNOB_ANGLE_SPAN

    def _format_value(self) -> str:
        if self._formatter is not None:
            try:
                return self._formatter(self._value)
            except Exception:
                pass
        if abs(self._value) >= 100:
            s = f"{self._value:.0f}"
        elif abs(self._value) >= 10:
            s = f"{self._value:.1f}"
        else:
            s = f"{self._value:.2f}"
        return f"{s}{self._unit}" if self._unit else s

    # -------- painting --------

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background cell (dark panel with subtle border)
        painter.fillRect(self.rect(), QColor("#0f0f14"))
        painter.setPen(QPen(QColor("#2a2a30"), 1))
        painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 8, 8)

        # Knob center
        cx = self.width() / 2.0
        cy = 14 + self.KNOB_SIZE / 2.0
        r_ring = self.KNOB_SIZE / 2.0 - 2.0
        r_body = self.KNOB_SIZE / 2.0 - 12.0

        # --- outer track: 270° grey arc from 7:30 CW to 4:30 ---
        track_pen = QPen(QColor("#2a2a30"))
        track_pen.setWidth(3)
        track_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(track_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Qt arc: 0° = 3 o'clock, positive = CCW. Our 12 o'clock = Qt's 90°.
        # Our "min angle" = -135° (CW from top) = Qt's (90 + 135) = 225°.
        # We sweep CW by 270°, which is negative span in Qt's CCW convention.
        qt_start = int((90.0 - KNOB_MIN_ANGLE) * 16)
        qt_span = int(-KNOB_ANGLE_SPAN * 16)
        painter.drawArc(
            int(cx - r_ring), int(cy - r_ring),
            int(r_ring * 2), int(r_ring * 2),
            qt_start, qt_span,
        )

        # --- value arc: accent-colored, grows with the value ---
        cur_angle = self._value_to_angle(self._value)
        if self._bipolar:
            # Start at 12 o'clock, grow toward the current position on
            # either side. "0" in our angle domain corresponds to 12.
            from_angle = min(0.0, cur_angle)
            span_deg = abs(cur_angle)
        else:
            from_angle = KNOB_MIN_ANGLE
            span_deg = cur_angle - KNOB_MIN_ANGLE
        if span_deg > 0:
            arc_pen = QPen(self._color)
            arc_pen.setWidth(3)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            painter.drawArc(
                int(cx - r_ring), int(cy - r_ring),
                int(r_ring * 2), int(r_ring * 2),
                int((90.0 - from_angle) * 16),
                int(-span_deg * 16),
            )

        # --- knob body: radial gradient ---
        grad = QRadialGradient(cx, cy - r_body * 0.4, r_body * 1.8)
        grad.setColorAt(0.0, QColor("#3a3a3e"))
        grad.setColorAt(1.0, QColor("#16161a"))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor("#3a3a3e"), 1))
        painter.drawEllipse(
            int(cx - r_body), int(cy - r_body),
            int(r_body * 2), int(r_body * 2),
        )

        # --- indicator line: from just-inside-body to the rim ---
        a_rad = math.radians(cur_angle)
        # 12 o'clock points up (-y in Qt), positive angle rotates CW.
        dx, dy = math.sin(a_rad), -math.cos(a_rad)
        tip_x = cx + dx * (r_body - 2)
        tip_y = cy + dy * (r_body - 2)
        root_x = cx + dx * (r_body - 12)
        root_y = cy + dy * (r_body - 12)
        ind_pen = QPen(self._color)
        ind_pen.setWidth(3)
        ind_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(ind_pen)
        painter.drawLine(int(root_x), int(root_y), int(tip_x), int(tip_y))

        # Bipolar: small center dot at 12 o'clock, inside the track.
        if self._bipolar:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(200, 200, 210))
            dot_r = 1.5
            painter.drawEllipse(
                int(cx - dot_r), int(cy - r_ring - dot_r),
                int(dot_r * 2), int(dot_r * 2),
            )

        # --- label (uppercase, tertiary grey) ---
        label_rect = QRect(0, int(cy + r_ring + 4), self.width(), 12)
        painter.setPen(QColor("#8a8a92"))
        f = painter.font()
        f.setPixelSize(9)
        f.setBold(True)
        f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, 0.8)
        painter.setFont(f)
        painter.drawText(
            label_rect, Qt.AlignmentFlag.AlignCenter, self._label.upper()
        )

        # --- formatted value (accent color) ---
        val_rect = QRect(0, int(cy + r_ring + 18), self.width(), 16)
        painter.setPen(self._color)
        f2 = painter.font()
        f2.setPixelSize(11)
        f2.setBold(True)
        painter.setFont(f2)
        painter.drawText(val_rect, Qt.AlignmentFlag.AlignCenter, self._format_value())

    # -------- interaction --------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_y = event.position().y()
            self._drag_start_value = self._value
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._prompt_direct_input()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            return
        dy = self._drag_start_y - event.position().y()
        sensitivity = self._sensitivity(event.modifiers())
        delta = dy * sensitivity
        if self._log:
            # In log scale we accelerate on wider ranges so the drag
            # still feels like "100 px covers the full sweep".
            lo = max(self._min, 1e-9)
            hi = max(self._max, lo * 1.0001)
            start_norm = (
                (math.log(max(self._drag_start_value, lo)) - math.log(lo))
                / (math.log(hi) - math.log(lo))
            )
            new_norm = max(0.0, min(1.0, start_norm + dy / 100.0
                                    * (0.1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0)
                                    * (0.1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else 1.0)))
            new_value = math.exp(
                math.log(lo) + new_norm * (math.log(hi) - math.log(lo))
            )
        else:
            new_value = self._drag_start_value + delta
        self.setValue(new_value)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.editingFinished.emit(self._value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setValue(self._default)
            self.editingFinished.emit(self._value)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        step = (self._max - self._min) / 100.0
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            step *= 0.1
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step *= 0.1
        direction = 1.0 if event.angleDelta().y() > 0 else -1.0
        if self._log:
            lo = max(self._min, 1e-9)
            hi = max(self._max, lo * 1.0001)
            cur_norm = (
                (math.log(max(self._value, lo)) - math.log(lo))
                / (math.log(hi) - math.log(lo))
            )
            new_norm = max(0.0, min(1.0, cur_norm + direction * 0.01
                * (0.1 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0)
                * (0.1 if event.modifiers() & Qt.KeyboardModifier.ControlModifier else 1.0)))
            new_val = math.exp(
                math.log(lo) + new_norm * (math.log(hi) - math.log(lo))
            )
        else:
            new_val = self._value + direction * step
        self.setValue(new_val)
        self.editingFinished.emit(self._value)
        event.accept()

    def _sensitivity(self, modifiers) -> float:
        base = (self._max - self._min) / 100.0
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            base *= 0.1
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            base *= 0.1
        return base

    def _prompt_direct_input(self) -> None:
        unit = f" ({self._unit})" if self._unit else ""
        value, ok = QInputDialog.getDouble(
            self,
            self._label,
            f"Value{unit}:",
            self._value,
            self._min,
            self._max,
            4,
        )
        if ok:
            self.setValue(float(value))
            self.editingFinished.emit(self._value)


# ================= Built-in value formatters =================


def fmt_db(v: float) -> str:
    """dB formatter — shows ``-∞`` at / below -60 dB (UI mute floor)."""
    if v <= -60:
        return "-∞ dB"
    return f"{v:+.1f} dB"


def fmt_pan(v: float) -> str:
    """Pan formatter: -100..0..+100 → L100..Center..R100."""
    if abs(v) < 0.5:
        return "Center"
    return f"R{abs(v):.0f}" if v > 0 else f"L{abs(v):.0f}"


def fmt_seconds(v: float) -> str:
    return f"{v:.2f} s"


def fmt_percentage(v: float) -> str:
    return f"{v:.0f} %"


def fmt_hz(v: float) -> str:
    return f"{v / 1000:.1f} kHz" if v >= 1000 else f"{v:.0f} Hz"


def fmt_semitones(v: float) -> str:
    prefix = "+" if v > 0 else ""
    return f"{prefix}{v:.0f} st"


def fmt_speed(v: float) -> str:
    return f"{v:.2f}×"
