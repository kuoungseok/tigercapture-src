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

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
    QRadialGradient,
    QWheelEvent,
)
from PySide6.QtWidgets import QInputDialog, QLayout, QSizePolicy, QWidget


# Knob angular range: 12 o'clock is 0°, positive angles rotate clockwise.
# The value arc sweeps from -135° (7:30 position) to +135° (4:30).
KNOB_MIN_ANGLE = -135.0
KNOB_MAX_ANGLE = 135.0
KNOB_ANGLE_SPAN = KNOB_MAX_ANGLE - KNOB_MIN_ANGLE  # 270°


# Semantic knob colours are intentionally muted so dense editor panels
# read like the reference UI: dark chrome first, functional colour second.
_COLOR_NAMES = {
    "blue": QColor("#8E98A8"),
    "green": QColor("#87A495"),
    "orange": QColor("#A89584"),
    "red": QColor("#B66A6A"),      # destructive only
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
        self._drag_moved: bool = False

        # Wheel events fire one editingFinished per notch — collapse a
        # burst of wheel ticks into a single trailing emit so heavy
        # slots (waveform refresh, EQ recompute) only run once when the
        # user stops scrolling.
        self._wheel_emit_timer = QTimer(self)
        self._wheel_emit_timer.setSingleShot(True)
        self._wheel_emit_timer.setInterval(120)
        self._wheel_emit_timer.timeout.connect(
            lambda: self.editingFinished.emit(self._value)
        )

        self.setFixedSize(self.CELL_WIDTH, self.CELL_HEIGHT)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
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

        # Background cell: soft glass tile, not a flat debugging box.
        tile = self.rect().adjusted(1, 1, -1, -1)
        bg = QLinearGradient(tile.topLeft(), tile.bottomRight())
        bg.setColorAt(0.0, QColor(255, 255, 255, 20))
        bg.setColorAt(1.0, QColor(255, 255, 255, 7))
        painter.setPen(QPen(QColor(126, 141, 198, 44), 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(tile, 15, 15)

        # Knob center
        cx = self.width() / 2.0
        cy = 14 + self.KNOB_SIZE / 2.0
        r_ring = self.KNOB_SIZE / 2.0 - 2.0
        r_body = self.KNOB_SIZE / 2.0 - 12.0

        # --- outer track: 270° grey arc from 7:30 CW to 4:30 ---
        track_pen = QPen(QColor(255, 255, 255, 36))
        track_pen.setWidth(5)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
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
            arc_pen.setWidth(5)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            painter.drawArc(
                int(cx - r_ring), int(cy - r_ring),
                int(r_ring * 2), int(r_ring * 2),
                int((90.0 - from_angle) * 16),
                int(-span_deg * 16),
            )

        # --- knob body: radial gradient ---
        grad = QRadialGradient(cx - r_body * 0.25, cy - r_body * 0.45, r_body * 1.9)
        grad.setColorAt(0.0, QColor("#4B5165"))
        grad.setColorAt(0.45, QColor("#252A3A"))
        grad.setColorAt(1.0, QColor("#10131E"))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor(255, 255, 255, 54), 1))
        painter.drawEllipse(
            int(cx - r_body), int(cy - r_body),
            int(r_body * 2), int(r_body * 2),
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 38))
        painter.drawEllipse(
            int(cx - r_body * 0.46), int(cy - r_body * 0.60),
            int(r_body * 0.54), int(r_body * 0.28),
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
        ind_pen.setWidth(4)
        ind_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(ind_pen)
        painter.drawLine(int(root_x), int(root_y), int(tip_x), int(tip_y))

        # Bipolar: small center dot at 12 o'clock, inside the track.
        if self._bipolar:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#E8EAF4"))
            dot_r = 1.5
            painter.drawEllipse(
                int(cx - dot_r), int(cy - r_ring - dot_r),
                int(dot_r * 2), int(dot_r * 2),
            )

        # --- label (uppercase, tertiary grey) ---
        label_rect = QRect(0, int(cy + r_ring + 4), self.width(), 12)
        painter.setPen(QColor("#A7ADC2"))
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
        value_bg = QRect(14, int(cy + r_ring + 17), self.width() - 28, 18)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 16))
        painter.drawRoundedRect(value_bg, 8, 8)
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
            self._drag_moved = False
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
        # Only drag while the left button is actually held — if Qt
        # missed the release (focus stolen, popup, etc.) we cancel
        # rather than tracking hover-only motion.
        if not self._dragging:
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            return
        dy = self._drag_start_y - event.position().y()
        if abs(dy) >= 1.0:
            self._drag_moved = True
        new_value = self._value_from_drag_delta(dy, event.modifiers())
        self.setValue(new_value)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Only commit when the drag actually moved the value. A
            # bare click (no drag) and the first press of a
            # double-click both leave _drag_moved=False — skipping the
            # emit prevents a "blip" before mouseDoubleClickEvent
            # resets to the default value.
            if self._drag_moved:
                self.editingFinished.emit(self._value)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            # The press that started this double-click flipped on
            # _dragging; clear it so the trailing release doesn't
            # re-emit after we reset.
            self._dragging = False
            self._drag_moved = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.setValue(self._default)
            self.editingFinished.emit(self._value)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Use the same modifier semantics as drag so wheel and drag
        # feel symmetric (Shift = 10×, Ctrl = 100×, both = 1000×).
        mods = event.modifiers()
        step_scale = self._precision_scale(mods)
        direction = 1.0 if event.angleDelta().y() > 0 else -1.0
        if self._log:
            lo = max(self._min, 1e-9)
            hi = max(self._max, lo * 1.0001)
            cur_norm = (
                (math.log(max(self._value, lo)) - math.log(lo))
                / (math.log(hi) - math.log(lo))
            )
            new_norm = max(0.0, min(1.0, cur_norm + direction * 0.01 * step_scale))
            new_val = math.exp(
                math.log(lo) + new_norm * (math.log(hi) - math.log(lo))
            )
        else:
            step = (self._max - self._min) / 100.0 * step_scale
            new_val = self._value + direction * step
        self.setValue(new_val)
        # Coalesce rapid wheel notches: one trailing editingFinished
        # after the user stops scrolling, not one per notch.
        self._wheel_emit_timer.start()
        event.accept()

    def _precision_scale(self, modifiers) -> float:
        """Common modifier-to-precision map for drag + wheel.
        No modifier = 1×, Shift = 0.1×, Ctrl = 0.01×, Shift+Ctrl = 0.001×.
        """
        scale = 1.0
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            scale *= 0.1
        if modifiers & Qt.KeyboardModifier.ControlModifier:
            scale *= 0.01
        return scale

    def _sensitivity(self, modifiers) -> float:
        return (self._max - self._min) / 100.0 * self._precision_scale(modifiers)

    def _value_from_drag_delta(self, dy: float, modifiers) -> float:
        """Compute the new value for a vertical drag of ``dy`` pixels.
        Shared between linear + log paths so modifier behavior matches.
        """
        if self._log:
            lo = max(self._min, 1e-9)
            hi = max(self._max, lo * 1.0001)
            start_norm = (
                (math.log(max(self._drag_start_value, lo)) - math.log(lo))
                / (math.log(hi) - math.log(lo))
            )
            new_norm = max(
                0.0, min(1.0, start_norm + (dy / 100.0) * self._precision_scale(modifiers))
            )
            return math.exp(
                math.log(lo) + new_norm * (math.log(hi) - math.log(lo))
            )
        return self._drag_start_value + dy * self._sensitivity(modifiers)

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


class FlowLayout(QLayout):
    """A QHBoxLayout that wraps to a new row when it runs out of width.

    Mirrors Qt's official ``Flow Layout`` example (Qt docs / examples
    repo) so knob rows stay on a single line whenever the parent has
    room, and fold gracefully onto a second row when the sound-editor
    window is squeezed narrow — no horizontal scrollbar, no clipped
    knobs.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        margin: int = 0,
        h_spacing: int = 8,
        v_spacing: int = 8,
    ) -> None:
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self._h_space = h_spacing
        self._v_space = v_spacing
        self._items: list = []

    def __del__(self) -> None:  # type: ignore[override]
        while self._items:
            self._items.pop()

    # ---- QLayout overrides ----

    def addItem(self, item) -> None:  # noqa: N802 (Qt naming)
        self._items.append(item)

    def horizontalSpacing(self) -> int:  # noqa: N802
        return self._h_space

    def verticalSpacing(self) -> int:  # noqa: N802
        return self._v_space

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x = effective.x()
        y = effective.y()
        line_height = 0
        for item in self._items:
            w = item.widget()
            space_x = self._h_space
            space_y = self._v_space
            if w is not None:
                style = w.style()
                space_x = max(space_x, style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal,
                ))
                space_y = max(space_y, style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Vertical,
                ))
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective.right() and line_height > 0:
                x = effective.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y() + m.bottom()


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
