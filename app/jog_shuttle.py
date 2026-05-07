"""Sony PVW-2800-style jog / shuttle wheel.

Two concentric rings on a single circular widget:

- **Outer ring (shuttle)**: rotate to set a playback rate. The position
  is *persistent* — release the cursor and the rate stays. Emits
  ``shuttle_speed_changed(float)`` whenever the angle crosses a step.
  Sony's classic 6-step layout (±1×, ±2×, ±4×, ±8×, ±16×, ±32×) maps
  symmetrically to ±150° around 12 o'clock; outside that the wheel
  caps. Centre of the dial = pause (rate 0.0); 12 o'clock = 1.0×.

- **Inner ring (jog)**: rotate to scrub frame-by-frame. Spring-loaded
  back to 12 o'clock on release. Emits ``jog_delta(int)`` on every
  angle tick — the integer is the *signed frame delta* the editor
  should advance the playhead by. Magnitude is small (1-2 frames per
  tick) so the host plays catch-up smoothly.

Visual:
- Brushed-aluminium radial gradient on both rings (light → mid →
  dark → mid → light), evoking Sony's 80s/90s broadcast deck look.
- Tiger Orange tick mark on each ring at the current angle.
- Centre hub with a small Tiger Orange status dot when shuttle ≠ 0.

Sizes:
- ``JogShuttleWidget(size=200)`` — main control
- ``JogShuttleWidget(size=80)``  — mini variant for tight layouts

The widget is purely visual + signal-emitting; it doesn't touch a
player. The editor wires ``shuttle_speed_changed`` to its player's
rate setter and ``jog_delta`` to ``set_position`` increments.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QConicalGradient,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget


# Sony PVW-2800 shuttle steps (rate magnitudes). Negative direction
# is the same set negated. ±0 is the dead-centre stop.
_SHUTTLE_STEPS: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)

# How far from 12-o'clock the shuttle can swing before clamping.
# 150° maps the 6 steps over the outer ring symmetrically (one step
# per ~25° on each side).
_SHUTTLE_RANGE_DEG: float = 150.0

# Jog ring is more sensitive — every 6° of rotation produces one
# frame's worth of delta, so a quick wrist flick is a few frames.
_JOG_DEG_PER_FRAME: float = 6.0


def _shuttle_speed_for_angle(angle_deg: float) -> float:
    """Map a signed shuttle angle (-_SHUTTLE_RANGE_DEG ..
    +_SHUTTLE_RANGE_DEG) to a play rate. ``angle_deg < 0`` plays
    backward; ``angle_deg == 0`` is paused (rate 0.0). The mapping is
    discrete (one of the Sony steps) so the wheel snaps audibly to
    each gear instead of producing analog-mush rates."""
    a = max(-_SHUTTLE_RANGE_DEG, min(_SHUTTLE_RANGE_DEG, float(angle_deg)))
    sign = 1 if a >= 0 else -1
    mag = abs(a)
    if mag < (_SHUTTLE_RANGE_DEG / (len(_SHUTTLE_STEPS) * 2)):
        return 0.0
    # Bucket index in [1, len(_SHUTTLE_STEPS)] — first step is the
    # ±1× gear, last is ±32×. Linear bucket on the magnitude.
    step_size = _SHUTTLE_RANGE_DEG / len(_SHUTTLE_STEPS)
    idx = min(len(_SHUTTLE_STEPS) - 1, int(mag / step_size))
    return sign * _SHUTTLE_STEPS[idx]


class JogShuttleWidget(QWidget):
    """Custom QWidget rendering a jog + shuttle dial.

    See module docstring for behaviour. Emits:
        shuttle_speed_changed(float)  — new rate (0 == pause; signed)
        jog_delta(int)                — frame delta during jog drag
    """

    shuttle_speed_changed = Signal(float)
    jog_delta = Signal(int)

    # Hub diameter ratios — relative to widget size so 80px and 200px
    # variants share the same visual proportions.
    _OUTER_R_RATIO = 0.50
    _INNER_R_RATIO = 0.32
    _HUB_R_RATIO = 0.14

    def __init__(self, size: int = 200, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(int(size), int(size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(False)

        # State.
        self._shuttle_deg: float = 0.0           # -150..+150
        self._jog_deg: float = 0.0               # current rotation, snaps back on release
        self._dragging: str | None = None        # "jog" | "shuttle" | None
        self._drag_anchor_deg: float = 0.0
        self._drag_start_value: float = 0.0      # widget-state at press
        self._jog_accumulated: float = 0.0       # for emitting integer frame deltas

        # Spring-back animation for jog ring.
        self._jog_anim_timer = QTimer(self)
        self._jog_anim_timer.setInterval(16)
        self._jog_anim_timer.timeout.connect(self._tick_jog_spring_back)

    # ------------------------------------------------------------------
    #  Public state
    # ------------------------------------------------------------------

    def shuttle_speed(self) -> float:
        return _shuttle_speed_for_angle(self._shuttle_deg)

    def reset_shuttle(self) -> None:
        """Centre the shuttle ring (rate 0). Used when playback ends
        or the user clicks Stop — reflects the deck-style "shuttle
        snaps to centre when you take your hand off Stop"."""
        if abs(self._shuttle_deg) > 0.5:
            self._shuttle_deg = 0.0
            self.update()
            self.shuttle_speed_changed.emit(0.0)

    # ------------------------------------------------------------------
    #  Painting
    # ------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        cx = rect.width() / 2.0
        cy = rect.height() / 2.0
        # Background — keeps the widget transparent for parents that
        # already draw a darker panel beneath.
        p.fillRect(rect, Qt.GlobalColor.transparent)

        outer_r = min(cx, cy) * self._OUTER_R_RATIO * 2.0  # diameter
        inner_r = min(cx, cy) * self._INNER_R_RATIO * 2.0
        hub_r = min(cx, cy) * self._HUB_R_RATIO * 2.0

        # Outer ring (shuttle) ----
        self._draw_brushed_ring(
            p, cx, cy,
            outer_radius=outer_r / 2.0,
            inner_radius=inner_r / 2.0 + 4,
            base_color=QColor("#9a9aa0"),
        )
        # Tick at the shuttle angle.
        self._draw_ring_tick(
            p, cx, cy,
            outer_r / 2.0 - 6, inner_r / 2.0 + 8,
            self._shuttle_deg, QColor("#D85A30"),
        )
        # Step markers — small notches at each Sony gear angle.
        for i in range(1, len(_SHUTTLE_STEPS) + 1):
            step_size = _SHUTTLE_RANGE_DEG / len(_SHUTTLE_STEPS)
            for sign in (-1, +1):
                self._draw_ring_notch(
                    p, cx, cy,
                    outer_r / 2.0 - 2, outer_r / 2.0 - 8,
                    sign * step_size * i, QColor(0, 0, 0, 90),
                )

        # Inner ring (jog) ----
        self._draw_brushed_ring(
            p, cx, cy,
            outer_radius=inner_r / 2.0,
            inner_radius=hub_r / 2.0 + 2,
            base_color=QColor("#7a7a82"),
        )
        # Jog tick — finer than shuttle's, since the inner ring is smaller.
        self._draw_ring_tick(
            p, cx, cy,
            inner_r / 2.0 - 4, hub_r / 2.0 + 4,
            self._jog_deg, QColor("#D85A30"),
        )

        # Centre hub ----
        hub_rect = QRectF(cx - hub_r / 2.0, cy - hub_r / 2.0, hub_r, hub_r)
        hub_grad = QRadialGradient(cx, cy, hub_r / 2.0)
        hub_grad.setColorAt(0.0, QColor("#3a3a40"))
        hub_grad.setColorAt(1.0, QColor("#1a1a1e"))
        p.setBrush(QBrush(hub_grad))
        p.setPen(QPen(QColor(0, 0, 0, 200), 1))
        p.drawEllipse(hub_rect)
        # Status dot — Tiger Orange when shuttle is engaged.
        if abs(self.shuttle_speed()) > 0.01:
            dot_r = hub_r * 0.18
            p.setBrush(QBrush(QColor("#D85A30")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx, cy), dot_r, dot_r)

        # Speed readout below the dial — only when the widget is big
        # enough that text is legible (~140 px+).
        if self.width() >= 140:
            speed = self.shuttle_speed()
            text = "PAUSE" if speed == 0.0 else f"{speed:+.0f}×"
            p.setPen(QColor("#aaaaaa"))
            font = QFont(p.font())
            font.setPixelSize(max(9, int(self.width() * 0.07)))
            font.setBold(True)
            p.setFont(font)
            p.drawText(rect, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter, text)

        p.end()

    def _draw_brushed_ring(
        self, p: QPainter, cx: float, cy: float,
        outer_radius: float, inner_radius: float,
        base_color: QColor,
    ) -> None:
        """A donut filled with a conical gradient that fakes the
        brushed-aluminium look — alternating light/dark stripes
        encircling the centre."""
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), outer_radius, outer_radius)
        inner_path = QPainterPath()
        inner_path.addEllipse(QPointF(cx, cy), inner_radius, inner_radius)
        donut = path.subtracted(inner_path)

        grad = QConicalGradient(cx, cy, 90.0)
        light = base_color.lighter(140)
        mid = base_color
        dark = base_color.darker(135)
        for stop in (0.0, 0.25, 0.5, 0.75, 1.0):
            # Cycle through light/dark to fake brushed metal.
            shade = light if int(stop * 8) % 2 == 0 else dark
            grad.setColorAt(stop, shade)
        p.setBrush(QBrush(grad))
        # Subtle outer rim — black, for the inset feel.
        p.setPen(QPen(QColor(0, 0, 0, 180), 1))
        p.drawPath(donut)

    def _draw_ring_tick(
        self, p: QPainter, cx: float, cy: float,
        outer_r: float, inner_r: float,
        angle_deg: float, color: QColor,
    ) -> None:
        """Draw a Tiger-Orange wedge at ``angle_deg`` (0° = 12 o'clock,
        positive = clockwise)."""
        # Convert to Qt's "0° = 3 o'clock, ccw positive" convention.
        a = math.radians(90.0 - angle_deg)
        x1 = cx + math.cos(a) * outer_r
        y1 = cy - math.sin(a) * outer_r
        x2 = cx + math.cos(a) * inner_r
        y2 = cy - math.sin(a) * inner_r
        pen = QPen(color, max(2.0, self.width() * 0.012))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _draw_ring_notch(
        self, p: QPainter, cx: float, cy: float,
        outer_r: float, inner_r: float,
        angle_deg: float, color: QColor,
    ) -> None:
        a = math.radians(90.0 - angle_deg)
        x1 = cx + math.cos(a) * outer_r
        y1 = cy - math.sin(a) * outer_r
        x2 = cx + math.cos(a) * inner_r
        y2 = cy - math.sin(a) * inner_r
        p.setPen(QPen(color, 1.2))
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    # ------------------------------------------------------------------
    #  Mouse handling
    # ------------------------------------------------------------------

    def _angle_from_pos(self, pos) -> float:
        """Cursor angle in degrees, measured CW from 12 o'clock.
        Returns NaN equivalent (None) when the cursor is on the centre."""
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        dx = pos.x() - cx
        dy = pos.y() - cy
        if abs(dx) < 1e-3 and abs(dy) < 1e-3:
            return 0.0
        # atan2(dx, -dy) gives 0 at 12 o'clock and rotates CW.
        return math.degrees(math.atan2(dx, -dy))

    def _which_ring(self, pos) -> str | None:
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        r = math.hypot(pos.x() - cx, pos.y() - cy)
        outer = min(cx, cy) * self._OUTER_R_RATIO
        inner = min(cx, cy) * self._INNER_R_RATIO
        hub = min(cx, cy) * self._HUB_R_RATIO
        if hub <= r <= inner:
            return "jog"
        if inner < r <= outer:
            return "shuttle"
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        ring = self._which_ring(pos)
        if ring is None:
            return
        self._dragging = ring
        self._drag_anchor_deg = self._angle_from_pos(pos)
        self._drag_start_value = (
            self._shuttle_deg if ring == "shuttle" else self._jog_deg
        )
        self._jog_accumulated = 0.0
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self._jog_anim_timer.stop()  # cancel any spring-back in progress

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is None:
            return
        a = self._angle_from_pos(event.position().toPoint())
        delta = _wrap_angle(a - self._drag_anchor_deg)

        if self._dragging == "shuttle":
            new_angle = max(
                -_SHUTTLE_RANGE_DEG,
                min(_SHUTTLE_RANGE_DEG, self._drag_start_value + delta),
            )
            old_speed = self.shuttle_speed()
            self._shuttle_deg = new_angle
            new_speed = self.shuttle_speed()
            if abs(new_speed - old_speed) > 1e-6:
                self.shuttle_speed_changed.emit(new_speed)
            self.update()
        elif self._dragging == "jog":
            self._jog_deg = self._drag_start_value + delta
            # Emit ``jog_delta(±N)`` whenever the rotation crosses one
            # more multiple of ``_JOG_DEG_PER_FRAME``. ``_jog_accumulated``
            # remembers the last reported frame count for THIS drag —
            # zeroed in mousePress so a fresh drag starts clean.
            target_frames = int(self._jog_deg / _JOG_DEG_PER_FRAME)
            already_emitted = int(self._jog_accumulated)
            if target_frames != already_emitted:
                self.jog_delta.emit(target_frames - already_emitted)
                self._jog_accumulated = float(target_frames)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging == "jog":
            # Spring back to neutral.
            self._jog_anim_timer.start()
        self._dragging = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    # ------------------------------------------------------------------
    #  Spring-back animation
    # ------------------------------------------------------------------

    def _tick_jog_spring_back(self) -> None:
        # Exponential decay toward 0 — fast enough that the UI feels
        # snappy, slow enough that the eye sees the motion.
        if abs(self._jog_deg) < 0.5:
            self._jog_deg = 0.0
            self._jog_anim_timer.stop()
            self.update()
            return
        self._jog_deg *= 0.78
        self.update()


def _wrap_angle(deg: float) -> float:
    """Bring an angle delta into ``[-180, 180]`` so a drag that crosses
    the 12 o'clock seam doesn't suddenly flip sign."""
    while deg > 180:
        deg -= 360
    while deg < -180:
        deg += 360
    return deg
