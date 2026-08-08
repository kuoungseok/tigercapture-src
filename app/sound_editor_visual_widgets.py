"""Reusable visual widgets for the renewed sound editor."""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget
from PySide6.QtWidgets import QGridLayout

from app.audio_tracks import AudioClip
from app.icons import app_icon, icon_size


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOUND_JOG_DIAL_TEXTURE = _PROJECT_ROOT / "resources" / "ui" / "sound_editor" / "jog_dial_metal_sparse_base.png"


def _fmt_ms(ms: int | float | None) -> str:
    try:
        value = max(0, int(ms or 0))
    except Exception:
        value = 0
    s = value // 1000
    return f"{s // 60}:{s % 60:02d}"


class _MiniSoundGraph(QWidget):
    """Small non-interactive audio visual used to make each tab legible."""

    value_edited = Signal(int, float)
    dynamics_edited = Signal(float, float)

    def __init__(self, kind: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kind = kind
        self._values: tuple[float, ...] = ()
        self._drag_index: int | None = None
        self._hover_index: int | None = None
        self._pulse_index: int | None = None
        self._pulse_started = 0.0
        self._pulse_duration_s = 0.46
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(16)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self.setMinimumHeight(44)
        self.setMaximumHeight(50)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        if kind in {"eq", "dyn", "fx", "ai"}:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        if kind == "eq":
            self.setToolTip("Drag EQ points to tune Low, Mid, and High gain. Double-click a point to reset it.")
        elif kind == "dyn":
            self.setToolTip("Drag the knee for threshold, or the right point for ratio. Double-click a point to reset it.")
        elif kind == "fx":
            self.setToolTip("Drag FX points to tune Reverb, Delay, and De-esser. Double-click a point to reset it.")
        elif kind == "ai":
            self.setToolTip("Drag AI macro points to tune Air, Clarity, Warmth, Width, Punch, and Excite. Double-click a point to reset it.")

    def set_values(self, *values: float) -> None:
        self._values = tuple(float(v or 0.0) for v in values)
        self.update()

    def _plot_rect(self) -> QRectF:
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        return rect.adjusted(10.0, 8.0, -10.0, -8.0)

    def _eq_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        vals = (self._values + (0.0, 0.0, 0.0))[:3]
        points: list[QPointF] = []
        for i, gain in enumerate(vals):
            x = plot.left() + plot.width() * i / 2.0
            y = plot.center().y() - max(-12.0, min(12.0, gain)) / 12.0 * plot.height() * 0.42
            points.append(QPointF(x, y))
        return points

    def _nearest_eq_index(self, pos: QPointF) -> int:
        points = self._eq_points()
        if not points:
            return 0
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.35, index) for index, point in enumerate(points)]
        return min(distances)[1]

    def _eq_gain_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        normalized = (plot.center().y() - y) / (plot.height() * 0.42)
        return max(-12.0, min(12.0, normalized * 12.0))

    def _emit_eq_edit(self, index: int, y: float) -> None:
        self.value_edited.emit(max(0, min(2, int(index))), round(self._eq_gain_from_y(float(y)), 1))

    def _dyn_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
        ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
        knee_x = plot.left() + plot.width() * ((threshold + 60.0) / 60.0)
        low = QPointF(plot.left(), plot.bottom())
        knee = QPointF(knee_x, plot.bottom() - plot.height() * 0.58)
        high = QPointF(plot.right(), knee.y() - plot.height() * (0.30 / ratio))
        return [low, knee, high]

    def _nearest_dyn_index(self, pos: QPointF) -> int:
        points = self._dyn_points()
        handles = ((0, points[1]), (1, points[2]))
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.6, index) for index, point in handles]
        return min(distances)[1]

    def _dyn_threshold_from_x(self, x: float) -> float:
        plot = self._plot_rect()
        if plot.width() <= 0:
            return -20.0
        normalized = max(0.0, min(1.0, (float(x) - plot.left()) / plot.width()))
        return -60.0 + normalized * 60.0

    def _dyn_ratio_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 4.0
        knee_y = plot.bottom() - plot.height() * 0.58
        distance = max(plot.height() * 0.015, knee_y - float(y))
        ratio = plot.height() * 0.30 / distance
        return max(1.0, min(20.0, ratio))

    def _emit_dyn_edit(self, handle_index: int, pos: QPointF) -> None:
        threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
        ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
        if int(handle_index) == 0:
            threshold = self._dyn_threshold_from_x(pos.x())
        else:
            ratio = self._dyn_ratio_from_y(pos.y())
        self.dynamics_edited.emit(round(threshold, 1), round(ratio, 1))

    def _fx_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        vals = (self._values + (0.0, 0.0, 0.0))[:3]
        baseline = plot.bottom() - plot.height() * 0.24
        points = [QPointF(plot.left(), baseline)]
        for index, value in enumerate(vals):
            normalized = max(0.0, min(1.0, float(value) / 100.0))
            x = plot.left() + plot.width() * (index + 1.0) / 4.0
            y = plot.bottom() - plot.height() * (0.14 + normalized * 0.74)
            points.append(QPointF(x, y))
        points.append(QPointF(plot.right(), baseline))
        return points

    def _nearest_fx_index(self, pos: QPointF) -> int:
        handles = self._fx_points()[1:4]
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.55, index) for index, point in enumerate(handles)]
        return min(distances)[1]

    def _fx_value_from_y(self, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        normalized = (plot.bottom() - float(y)) / plot.height()
        return max(0.0, min(100.0, (normalized - 0.14) / 0.74 * 100.0))

    def _emit_fx_edit(self, index: int, y: float) -> None:
        self.value_edited.emit(max(0, min(2, int(index))), round(self._fx_value_from_y(float(y)), 0))

    @staticmethod
    def _ai_max_values() -> tuple[float, ...]:
        return (8.0, 100.0, 100.0, 200.0, 100.0, 100.0)

    def _ai_points(self, plot: QRectF | None = None) -> list[QPointF]:
        plot = plot or self._plot_rect()
        max_values = self._ai_max_values()
        vals = (self._values + (0.0,) * len(max_values))[: len(max_values)]
        points: list[QPointF] = []
        for index, value in enumerate(vals):
            normalized = max(0.0, min(1.0, float(value) / max_values[index]))
            x = plot.left() + plot.width() * (index + 0.5) / len(max_values)
            y = plot.bottom() - plot.height() * (0.10 + normalized * 0.78)
            points.append(QPointF(x, y))
        return points

    def _nearest_ai_index(self, pos: QPointF) -> int:
        points = self._ai_points()
        distances = [(abs(pos.x() - point.x()) + abs(pos.y() - point.y()) * 0.48, index) for index, point in enumerate(points)]
        return min(distances)[1]

    def _ai_value_from_y(self, index: int, y: float) -> float:
        plot = self._plot_rect()
        if plot.height() <= 0:
            return 0.0
        max_value = self._ai_max_values()[max(0, min(len(self._ai_max_values()) - 1, int(index)))]
        normalized = (plot.bottom() - float(y)) / plot.height()
        value = max(0.0, min(1.0, (normalized - 0.10) / 0.78)) * max_value
        return round(value, 1 if int(index) == 0 else 0)

    def _emit_ai_edit(self, index: int, y: float) -> None:
        index = max(0, min(len(self._ai_max_values()) - 1, int(index)))
        self.value_edited.emit(index, self._ai_value_from_y(index, float(y)))

    def _reset_handle(self, index: int) -> None:
        if self._kind == "eq":
            self.value_edited.emit(max(0, min(2, int(index))), 0.0)
            return
        if self._kind == "dyn":
            threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
            ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
            if int(index) == 0:
                threshold = -20.0
            else:
                ratio = 4.0
            self.dynamics_edited.emit(round(threshold, 1), round(ratio, 1))
            return
        if self._kind == "fx":
            defaults = (20.0, 20.0, 40.0)
            reset_index = max(0, min(2, int(index)))
            self.value_edited.emit(reset_index, defaults[reset_index])
            return
        if self._kind == "ai":
            defaults = (0.0, 0.0, 0.0, 100.0, 0.0, 0.0)
            reset_index = max(0, min(len(defaults) - 1, int(index)))
            self.value_edited.emit(reset_index, defaults[reset_index])


    def _nearest_index(self, pos: QPointF) -> int | None:
        if self._kind == "eq":
            return self._nearest_eq_index(pos)
        if self._kind == "dyn":
            return self._nearest_dyn_index(pos)
        if self._kind == "fx":
            return self._nearest_fx_index(pos)
        if self._kind == "ai":
            return self._nearest_ai_index(pos)
        return None

    def _set_hover_index(self, index: int | None) -> None:
        if self._hover_index == index:
            return
        self._hover_index = index
        self.update()

    def _active_index(self) -> int | None:
        return self._drag_index if self._drag_index is not None else self._hover_index

    def _tick_pulse(self) -> None:
        if self._pulse_index is None:
            self._pulse_timer.stop()
            return
        if time.monotonic() - self._pulse_started >= self._pulse_duration_s:
            self._pulse_index = None
            self._pulse_timer.stop()
        self.update()

    def _start_release_pulse(self, index: int | None) -> None:
        if index is None:
            return
        self._pulse_index = int(index)
        self._pulse_started = time.monotonic()
        if not self._pulse_timer.isActive():
            self._pulse_timer.start()
        self.update()

    def _pulse_amount(self, index: int) -> float:
        if self._pulse_index != index:
            return 0.0
        elapsed = time.monotonic() - self._pulse_started
        if elapsed >= self._pulse_duration_s:
            return 0.0
        t = max(0.0, min(1.0, 1.0 - elapsed / self._pulse_duration_s))
        return t * t * (3.0 - 2.0 * t)

    def _pin_emphasis(self, index: int) -> float:
        if self._active_index() == index:
            return 1.0
        return self._pulse_amount(index)

    def mousePressEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton:
            if self._kind == "eq":
                self._drag_index = self._nearest_eq_index(event.position())
                self._emit_eq_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._kind == "dyn":
                self._drag_index = self._nearest_dyn_index(event.position())
                self._emit_dyn_edit(self._drag_index, event.position())
                event.accept()
                return
            if self._kind == "fx":
                self._drag_index = self._nearest_fx_index(event.position())
                self._emit_fx_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._kind == "ai":
                self._drag_index = self._nearest_ai_index(event.position())
                self._emit_ai_edit(self._drag_index, event.position().y())
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._kind in {"eq", "dyn", "fx", "ai"}:
            index = self._nearest_index(event.position())
            if index is not None:
                self._reset_handle(index)
                self._start_release_pulse(index)
                self._drag_index = None
                self._hover_index = None
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._kind in {"eq", "dyn", "fx", "ai"}:
            if self._drag_index is None:
                self._set_hover_index(self._nearest_index(event.position()))
            if self._drag_index is not None and self._kind == "eq":
                self._emit_eq_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "dyn":
                self._emit_dyn_edit(self._drag_index, event.position())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "fx":
                self._emit_fx_edit(self._drag_index, event.position().y())
                event.accept()
                return
            if self._drag_index is not None and self._kind == "ai":
                self._emit_ai_edit(self._drag_index, event.position().y())
                event.accept()
                return
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._drag_index is not None and event.button() == Qt.MouseButton.LeftButton:
            if self._kind == "eq":
                self._emit_eq_edit(self._drag_index, event.position().y())
            elif self._kind == "dyn":
                self._emit_dyn_edit(self._drag_index, event.position())
            elif self._kind == "fx":
                self._emit_fx_edit(self._drag_index, event.position().y())
            elif self._kind == "ai":
                self._emit_ai_edit(self._drag_index, event.position().y())
            self._start_release_pulse(self._drag_index)
            self._hover_index = None
            self._drag_index = None
            event.accept()
            self.update()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:  # pragma: no cover - visual QA
        self._set_hover_index(None)
        super().leaveEvent(event)

    def _accent_color(self, index: int | None = None) -> QColor:
        palettes = {
            "eq": ("#6CCFA6", "#72B9DC", "#D8B35F"),
            "dyn": ("#DDB25D", "#D58272"),
            "fx": ("#A981E0", "#62B9D3", "#D47F8A"),
            "ai": ("#77B8E8", "#8ED59D", "#D9B75F", "#B48BE8", "#D88499", "#65D0C2"),
        }
        colors = palettes.get(self._kind) or ("#AEB6C2",)
        idx = max(0, min(len(colors) - 1, int(index or 0)))
        return QColor(colors[idx])

    def _line_gradient(self, start: QPointF, end: QPointF, accent: QColor | None = None) -> QLinearGradient:
        grad = QLinearGradient(start, end)
        left = QColor("#858E98")
        mid = QColor("#C1C8CF")
        right = QColor("#8F969D")
        for col, alpha in ((left, 198), (mid, 232), (right, 198)):
            col.setAlpha(alpha)
        grad.setColorAt(0.0, left)
        if accent is not None and accent.isValid():
            acc = QColor(accent)
            acc.setAlpha(224)
            soft = QColor(accent)
            soft.setAlpha(154)
            grad.setColorAt(0.38, soft)
            grad.setColorAt(0.55, acc)
            grad.setColorAt(0.72, soft)
        else:
            grad.setColorAt(0.50, mid)
        grad.setColorAt(1.0, right)
        return grad

    def _draw_path(
        self,
        p: QPainter,
        points: list[QPointF],
        plot: QRectF,
        *,
        width: float = 2.15,
        accent: QColor | None = None,
    ) -> None:
        if len(points) < 2:
            return
        accent = QColor(accent or self._accent_color())
        shadow_pen = QPen(QColor(0, 0, 0, 118), width + 1.65)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        shadow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(shadow_pen)
        p.drawPolyline(points)
        glow = QColor(accent)
        glow.setAlpha(42)
        under_glow = QPen(glow, width + 1.35)
        under_glow.setCapStyle(Qt.PenCapStyle.RoundCap)
        under_glow.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(under_glow)
        p.drawPolyline(points)
        line_pen = QPen(
            QBrush(self._line_gradient(QPointF(plot.left(), plot.center().y()), QPointF(plot.right(), plot.center().y()), accent)),
            width,
        )
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        line_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(line_pen)
        p.drawPolyline(points)
        accent_hi = QColor(accent)
        accent_hi.setAlpha(112)
        accent_pen = QPen(accent_hi, max(0.7, width * 0.46))
        accent_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        accent_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(accent_pen)
        p.drawPolyline([QPointF(point.x(), point.y() - 0.2) for point in points])
        highlight = QColor(255, 255, 255, 56)
        hi_pen = QPen(highlight, max(0.65, width * 0.36))
        hi_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        hi_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(hi_pen)
        p.drawPolyline([QPointF(point.x(), point.y() - 0.75) for point in points])

    @staticmethod
    def _draw_pin(
        p: QPainter,
        point: QPointF,
        *,
        radius: float = 3.7,
        emphasis: float = 0.0,
        accent: QColor | None = None,
    ) -> None:
        emphasis = max(0.0, min(1.0, float(emphasis)))
        accent = QColor(accent or QColor("#AEB6C2"))
        radius += 0.55 * emphasis
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, int(120 + 15 * emphasis)))
        p.drawEllipse(QPointF(point.x(), point.y() + 1.2), radius + 0.9, radius + 0.9)
        halo = QColor(accent)
        halo.setAlpha(int(42 + 42 * emphasis))
        p.setBrush(halo)
        p.drawEllipse(point, radius + 1.7 + 0.4 * emphasis, radius + 1.7 + 0.4 * emphasis)
        pin = QRadialGradient(QPointF(point.x() - 1.2, point.y() - 1.4), radius + 2.1)
        core = QColor(
            int((59 + accent.red() * 0.12) + (82 - 59) * emphasis),
            int((66 + accent.green() * 0.10) + (88 - 66) * emphasis),
            int((75 + accent.blue() * 0.10) + (98 - 75) * emphasis),
        )
        mid = QColor(
            int(37 + (46 - 37) * emphasis),
            int(42 + (53 - 42) * emphasis),
            int(49 + (64 - 49) * emphasis),
        )
        pin.setColorAt(0.0, core)
        pin.setColorAt(0.58, mid)
        pin.setColorAt(1.0, QColor("#171B20"))
        p.setBrush(QBrush(pin))
        rim = QColor(accent)
        rim.setAlpha(int(162 + 70 * emphasis))
        p.setPen(QPen(rim, 0.85 + 0.2 * emphasis))
        p.drawEllipse(point, radius, radius)
        p.setPen(QPen(QColor(255, 255, 255, int(42 + 26 * emphasis)), 0.75))
        p.drawPoint(QPointF(point.x() - 1.2, point.y() - 1.2))

    def _active_point_label(self, index: int, point: QPointF) -> str:
        if self._kind == "eq":
            names = ("Low", "Mid", "High")
            values = (self._values + (0.0, 0.0, 0.0))[:3]
            return f"{names[index]} {float(values[index]):.1f} dB"
        if self._kind == "dyn":
            if index == 0:
                threshold = max(-60.0, min(0.0, self._values[0] if self._values else -20.0))
                return f"Threshold {threshold:.1f} dB"
            ratio = max(1.0, min(20.0, self._values[1] if len(self._values) > 1 else 4.0))
            return f"Ratio {ratio:.1f}:1"
        if self._kind == "fx":
            names = ("Reverb", "Delay", "De-ess")
            values = (self._values + (0.0, 0.0, 0.0))[:3]
            return f"{names[index]} {float(values[index]):.0f}%"
        if self._kind == "ai":
            names = ("Air", "Clarity", "Warmth", "Width", "Punch", "Excite")
            values = (self._values + (0.0,) * len(names))[: len(names)]
            suffix = " dB" if index == 0 else "%"
            return f"{names[index]} {float(values[index]):.1f}{suffix}" if index == 0 else f"{names[index]} {float(values[index]):.0f}{suffix}"
        return ""

    def _draw_active_label(self, p: QPainter, plot: QRectF, index: int, point: QPointF) -> None:
        label = self._active_point_label(index, point)
        if not label:
            return
        font = p.font()
        font.setPixelSize(8)
        font.setBold(True)
        p.setFont(font)
        metrics = p.fontMetrics()
        width = min(plot.width() - 6.0, float(metrics.horizontalAdvance(label) + 12))
        height = 16.0
        x = point.x() + 7.0
        if x + width > plot.right():
            x = point.x() - width - 7.0
        x = max(plot.left() + 2.0, min(x, plot.right() - width - 2.0))
        y = point.y() - height - 8.0
        if y < plot.top() + 2.0:
            y = point.y() + 8.0
        rect = QRectF(x, y, width, height)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QColor(34, 39, 46, 226))
        bg.setColorAt(1.0, QColor(20, 23, 28, 236))
        p.setPen(QPen(QColor(220, 226, 236, 58), 0.8))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, 4.0, 4.0)
        p.setPen(QColor("#DCE2EA"))
        p.drawText(rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0.0, QColor(29, 34, 40, 168))
        bg.setColorAt(1.0, QColor(16, 18, 20, 210))
        p.setPen(QPen(QColor(178, 186, 202, 38), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 6.0, 6.0)

        plot = self._plot_rect()
        p.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
        for i in range(1, 4):
            y = plot.top() + plot.height() * i / 4.0
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        for i in range(1, 5):
            x = plot.left() + plot.width() * i / 5.0
            p.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))

        if self._kind == "eq":
            points = self._eq_points(plot)
            active = self._active_index()
            self._draw_path(p, points, plot, accent=self._accent_color(1))
            for index, point in enumerate(points):
                self._draw_pin(p, point, emphasis=self._pin_emphasis(index), accent=self._accent_color(index))
            if active is not None and 0 <= active < len(points):
                self._draw_active_label(p, plot, active, points[active])
            return

        if self._kind == "dyn":
            low, knee, high = self._dyn_points(plot)
            active = self._active_index()
            self._draw_path(p, [low, knee, high], plot, width=1.65, accent=self._accent_color(0))
            p.setPen(QPen(QColor(220, 226, 236, 64), 0.85))
            p.drawLine(QPointF(knee.x(), plot.top()), QPointF(knee.x(), plot.bottom()))
            self._draw_pin(p, knee, radius=3.5, emphasis=self._pin_emphasis(0), accent=self._accent_color(0))
            self._draw_pin(p, high, radius=3.0, emphasis=self._pin_emphasis(1), accent=self._accent_color(1))
            if active == 0:
                self._draw_active_label(p, plot, active, knee)
            elif active == 1:
                self._draw_active_label(p, plot, active, high)
            return

        if self._kind == "fx":
            points = self._fx_points(plot)
            active = self._active_index()
            self._draw_path(p, points, plot, width=1.45, accent=self._accent_color(0))
            for index, point in enumerate(points[1:4]):
                self._draw_pin(p, point, radius=2.8, emphasis=self._pin_emphasis(index), accent=self._accent_color(index))
            if active is not None and 0 <= active < 3:
                self._draw_active_label(p, plot, active, points[active + 1])
            return

        if self._kind == "ai":
            points = self._ai_points(plot)
            max_values = self._ai_max_values()
            vals = (self._values + (0.0,) * len(max_values))[: len(max_values)]
            bar_w = max(12.0, plot.width() / 12.0)
            active = self._active_index()
            p.setPen(Qt.PenStyle.NoPen)
            baseline = plot.bottom() - plot.height() * 0.06
            p.setPen(QPen(QColor(220, 226, 236, 22), 1.0))
            p.drawLine(QPointF(plot.left(), baseline), QPointF(plot.right(), baseline))
            for i, (value, point) in enumerate(zip(vals, points)):
                normalized = max(0.035, min(1.0, float(value) / max_values[i]))
                h = plot.height() * (0.10 + normalized * 0.78)
                bar = QRectF(point.x() - bar_w * 0.5, plot.bottom() - h, bar_w, h)
                grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
                top = self._accent_color(i)
                top.setAlpha(206 if i != 3 else 226)
                bottom = QColor("#242A31")
                bottom.setAlpha(218)
                mid = QColor(top)
                mid.setAlpha(96)
                grad.setColorAt(0.0, top)
                grad.setColorAt(0.62, mid)
                grad.setColorAt(1.0, bottom)
                p.setBrush(QBrush(grad))
                p.setPen(QPen(QColor(220, 226, 236, 34), 0.75))
                p.drawRoundedRect(bar, 2.4, 2.4)
                self._draw_pin(p, point, radius=2.55, emphasis=self._pin_emphasis(i), accent=self._accent_color(i))
            if active is not None and 0 <= active < len(points):
                self._draw_active_label(p, plot, active, points[active])
            return

        values = self._values or (0.0,)
        count = max(1, len(values))
        bar_w = max(10.0, plot.width() / max(8.0, count * 2.4))
        p.setPen(Qt.PenStyle.NoPen)
        for i, value in enumerate(values):
            normalized = max(0.035, min(1.0, float(value)))
            x = plot.left() + plot.width() * (float(i) + 0.5) / float(count)
            h = plot.height() * (0.10 + normalized * 0.78)
            bar = QRectF(x - bar_w * 0.5, plot.bottom() - h, bar_w, h)
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            top = QColor("#B7C8A2" if i % 2 else "#9AA8BD")
            top.setAlpha(170)
            bottom = QColor("#252A31")
            bottom.setAlpha(210)
            grad.setColorAt(0.0, top)
            grad.setColorAt(1.0, bottom)
            p.setBrush(QBrush(grad))
            p.setPen(QPen(QColor(220, 226, 236, 42), 0.75))
            p.drawRoundedRect(bar, 2.5, 2.5)
            self._draw_pin(p, QPointF(bar.center().x(), bar.top()), radius=2.6, accent=self._accent_color(i))

class _SoundJogShuttle05(QWidget):
    """Speed Editor-inspired deck: transport stack, matte jog wheel, key bank."""

    position_changed = Signal(int)
    playing_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._position_ms = 0
        self._duration_ms = 1
        self._level = 0.0
        self._playing = False
        self._dial_pressed = False
        self._slot_anim_tick = 0
        self._slot_glow_values: list[float] = [0.0] * 8
        self._slot_decay_delays: list[int] = [0] * 8
        self._slot_anim_timer = QTimer(self)
        self._slot_anim_timer.setInterval(55)
        self._slot_anim_timer.timeout.connect(self._tick_slot_animation)
        self._dial_texture = QPixmap(str(_SOUND_JOG_DIAL_TEXTURE)) if _SOUND_JOG_DIAL_TEXTURE.is_file() else QPixmap()
        self.setObjectName("SoundJogShuttle05")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(126)
        self.setMaximumHeight(142)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        root = QHBoxLayout(self)
        root.setContentsMargins(10, 15, 10, 15)
        root.setSpacing(0)
        stack = QGridLayout()
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setHorizontalSpacing(6)
        stack.setVerticalSpacing(7)
        self._prev_btn = self._transport_button("previous", "Step back")
        self._play_btn = self._transport_button("play", "Play / pause")
        self._stop_btn = self._transport_button("stop", "Stop and return to start")
        self._next_btn = self._transport_button("next", "Step forward")
        self._prev_btn.clicked.connect(lambda: self._step(-1000))
        self._play_btn.clicked.connect(self._toggle_play)
        self._stop_btn.clicked.connect(self._stop)
        self._next_btn.clicked.connect(lambda: self._step(1000))
        self._play_btn.setProperty("transport", "play")
        stack.addWidget(self._prev_btn, 0, 0)
        stack.addWidget(self._play_btn, 0, 1)
        stack.addWidget(self._stop_btn, 1, 0)
        stack.addWidget(self._next_btn, 1, 1)
        root.addLayout(stack)
        root.addStretch(1)
        self._refresh_transport_icons()

    def _transport_button(self, icon: str, tooltip: str) -> QPushButton:
        button = QPushButton("", self)
        button.setObjectName("SoundJogButton")
        button.setIcon(app_icon(icon, size=14, color="#D7DAE7"))
        button.setIconSize(icon_size(13))
        button.setToolTip(tooltip)
        button.setFixedSize(36, 29)
        return button

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self._duration_ms = max(1, int(getattr(clip, "effective_length_ms", 0) or getattr(clip, "duration_ms", 0) or 1))
        self._position_ms = max(0, min(self._duration_ms, int(getattr(clip, "_se_jog_ms", 0) or 0))) if clip is not None else 0
        self._playing = bool(getattr(clip, "_se_jog_playing", False)) if clip is not None else False
        self._level = self._derive_level(clip)
        if self._playing:
            self._bump_active_slot_glow(strong=True)
            self._slot_anim_timer.start()
        else:
            self._slot_glow_values = [0.0] * 8
            self._slot_decay_delays = [0] * 8
            self._slot_anim_timer.stop()
        self._refresh_transport_icons()
        self.update()

    def _derive_level(self, clip: AudioClip | None) -> float:
        if clip is None:
            return 0.0
        waveform = getattr(clip, "waveform", None)
        try:
            if waveform is not None and int(getattr(waveform, "size", 0) or 0) > 0:
                peak = float(abs(waveform).max())
                return max(0.05, min(1.0, peak))
        except Exception:
            pass
        try:
            return max(0.05, min(1.0, float(getattr(clip, "gain", 1.0) or 1.0) / 1.5))
        except Exception:
            return 0.2

    def _ring_values(self, count: int = 36) -> list[float]:
        waveform = getattr(self._clip, "waveform", None) if self._clip is not None else None
        if waveform is None or not getattr(waveform, "size", 0):
            return [0.24 if i % 3 else 0.42 for i in range(count)]
        try:
            import numpy as np

            data = np.asarray(waveform, dtype=np.float32)
            mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
            if not mono.size:
                return [0.24 if i % 3 else 0.42 for i in range(count)]
            idx = np.linspace(0, mono.size - 1, count, dtype=np.int32)
            vals = np.abs(mono[idx])
            peak = max(float(vals.max()), 0.005)
            return [max(0.16, min(1.0, float(v) / peak)) for v in vals]
        except Exception:
            return [0.24 if i % 3 else 0.42 for i in range(count)]

    def _deck_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(94.0, 12.0, -35.0, -12.0)

    def _dial_rect(self) -> QRectF:
        deck = self._deck_rect()
        meter = self._meter_rect()
        available = QRectF(deck.left(), deck.top(), max(80.0, meter.left() - deck.left() - 18.0), deck.height())
        size = max(66.0, min(available.height() * 0.88, available.width() * 0.25))
        cx = available.right() - size * 0.62
        cy = available.center().y() + 2.0
        return QRectF(cx - size * 0.5, cy - size * 0.5, size, size)

    def _aux_key_rects(self) -> list[QRectF]:
        deck = self._deck_rect()
        dial = self._dial_rect()
        left = deck.left() + 12.0
        top = deck.top() + 34.0
        cols = 4
        gap = 5.0
        available = max(145.0, min(236.0, dial.left() - left - 22.0))
        key_w = max(34.0, min(52.0, (available - gap * (cols - 1)) / cols))
        key_h = max(22.0, min(29.0, (deck.height() - 52.0 - gap) / 2.0))
        return [
            QRectF(left + col * (key_w + gap), top + row * (key_h + gap), key_w, key_h)
            for row in range(2)
            for col in range(cols)
        ]

    def _aux_dial_rects(self) -> list[QRectF]:
        """Compatibility shim for older tests; these are now rectangular deck keys."""
        return self._aux_key_rects()

    def _display_rect(self) -> QRectF:
        deck = self._deck_rect()
        keys = self._aux_key_rects()
        dial = self._dial_rect()
        key_right = max((r.right() for r in keys), default=deck.left() + 190.0)
        left = key_right + 18.0
        right = max(left + 94.0, dial.left() - 18.0)
        width = min(260.0, right - left)
        return QRectF(left, deck.top() + 45.0, width, 46.0)

    def _mode_key_rects(self) -> list[tuple[str, QRectF, bool]]:
        dial = self._dial_rect()
        width = max(38.0, min(50.0, dial.width() * 0.32))
        gap = 5.0
        total = width * 3.0 + gap * 2.0
        left = dial.center().x() - total * 0.5
        top = max(self._deck_rect().top() + 17.0, dial.top() - 4.0)
        return [
            ("SHUT", QRectF(left, top, width, 22.0), False),
            ("JOG", QRectF(left + width + gap, top, width, 22.0), True),
            ("SCRL", QRectF(left + (width + gap) * 2.0, top, width, 22.0), False),
        ]

    def _aux_dial_specs(self) -> list[tuple[str, float, QColor]]:
        clip = self._clip
        gain = 0.5
        fade_in = 0.0
        fade_out = 0.0
        speed = 0.5
        pitch = 0.5
        ai_amount = 0.0
        if clip is not None:
            try:
                gain = max(0.0, min(1.0, float(getattr(clip, "gain", 1.0) or 1.0) / 2.0))
            except Exception:
                gain = 0.5
            try:
                fade_in = max(0.0, min(1.0, float(getattr(clip, "fade_in_ms", 0) or 0) / 5000.0))
                fade_out = max(0.0, min(1.0, float(getattr(clip, "fade_out_ms", 0) or 0) / 5000.0))
            except Exception:
                fade_in = fade_out = 0.0
            try:
                speed = (float(getattr(clip, "_se_speed", 1.0) or 1.0) - 0.5) / 1.5
                speed = max(0.0, min(1.0, speed))
            except Exception:
                speed = 0.5
            try:
                pitch = (float(getattr(clip, "_se_pitch", 0.0) or 0.0) + 12.0) / 24.0
                pitch = max(0.0, min(1.0, pitch))
            except Exception:
                pitch = 0.5
            try:
                ai = (getattr(clip, "effects", {}) or {}).get("ai_master", {}) or {}
                ai_values = [
                    float(ai.get("air", 0.0) or 0.0) / 8.0,
                    float(ai.get("clarity", 0.0) or 0.0) / 100.0,
                    float(ai.get("warmth", 0.0) or 0.0) / 100.0,
                    float(ai.get("width", 100.0) or 100.0) / 200.0,
                    float(ai.get("punch", 0.0) or 0.0) / 100.0,
                    float(ai.get("excite", 0.0) or 0.0) / 100.0,
                ]
                ai_amount = max(0.0, min(1.0, sum(ai_values) / max(1, len(ai_values))))
            except Exception:
                ai_amount = 0.0
        return [
            ("GAIN", gain, QColor(118, 145, 123, 198)),
            ("PAN", 0.5, QColor(90, 139, 154, 164)),
            ("IN", fade_in, QColor(118, 145, 123, 164)),
            ("OUT", fade_out, QColor(164, 150, 105, 176)),
            ("SPD", speed, QColor(90, 139, 154, 194)),
            ("PCH", pitch, QColor(136, 121, 160, 186)),
            ("AI", ai_amount, QColor(164, 99, 94, 186)),
            ("LVL", max(0.0, min(1.0, self._level)), QColor(164, 150, 105, 192)),
        ]

    def _meter_rect(self) -> QRectF:
        rect = QRectF(self.rect())
        return QRectF(rect.right() - 25.0, rect.top() + 16.0, 10.0, rect.height() - 32.0)

    def _normalized_position(self) -> float:
        return max(0.0, min(1.0, self._position_ms / max(1, self._duration_ms)))

    def _slot_index(self, slot_count: int = 8) -> int:
        active = int(round(self._normalized_position() * slot_count)) % slot_count
        if self._playing:
            active = (active + self._slot_anim_tick // 4) % slot_count
        return active

    def _ensure_slot_buffers(self, slot_count: int = 8) -> None:
        if len(self._slot_glow_values) != slot_count:
            self._slot_glow_values = [0.0] * slot_count
        if len(self._slot_decay_delays) != slot_count:
            self._slot_decay_delays = [0] * slot_count

    def _bump_active_slot_glow(self, *, strong: bool = False) -> None:
        slot_count = 8
        self._ensure_slot_buffers(slot_count)
        active = self._slot_index(slot_count)
        peak = 1.0 if strong else 0.84
        self._slot_glow_values[active] = max(self._slot_glow_values[active], peak)
        self._slot_decay_delays[active] = 0

    def _seed_power_down_glow(self) -> None:
        slot_count = 8
        self._ensure_slot_buffers(slot_count)
        active = self._slot_index(slot_count)
        for offset, value in enumerate((1.0, 0.78, 0.58, 0.38, 0.22, 0.12)):
            index = (active - offset) % slot_count
            self._slot_glow_values[index] = max(self._slot_glow_values[index], value)
            self._slot_decay_delays[index] = offset * 2

    def _advance_led_afterglow(self) -> None:
        slot_count = 8
        self._ensure_slot_buffers(slot_count)
        if self._playing:
            self._slot_decay_delays = [0] * slot_count
            for index, value in enumerate(self._slot_glow_values):
                self._slot_glow_values[index] = max(0.0, float(value) * 0.78)
            active = self._slot_index(slot_count)
            self._slot_glow_values[active] = 1.0
            self._slot_glow_values[(active - 1) % slot_count] = max(self._slot_glow_values[(active - 1) % slot_count], 0.52)
            return
        for index, value in enumerate(self._slot_glow_values):
            if self._slot_decay_delays[index] > 0:
                self._slot_decay_delays[index] -= 1
                continue
            self._slot_glow_values[index] = max(0.0, float(value) * 0.72)

    def _has_visible_afterglow(self) -> bool:
        return any(float(value) > 0.025 for value in self._slot_glow_values)

    def _set_position_ms(self, value: int, *, emit: bool = True) -> None:
        value = max(0, min(self._duration_ms, int(value)))
        if value == self._position_ms:
            return
        self._position_ms = value
        self._slot_anim_tick = (self._slot_anim_tick + 2) % 10000
        if not self._playing:
            self._bump_active_slot_glow()
            if not self._slot_anim_timer.isActive():
                self._slot_anim_timer.start()
        if self._clip is not None:
            setattr(self._clip, "_se_jog_ms", value)
        self.update()
        if emit:
            self.position_changed.emit(value)

    def _set_playing(self, playing: bool) -> None:
        playing = bool(playing)
        if self._playing == playing:
            return
        self._playing = playing
        if self._clip is not None:
            setattr(self._clip, "_se_jog_playing", playing)
        if playing:
            self._bump_active_slot_glow(strong=True)
            self._slot_anim_timer.start()
        else:
            self._seed_power_down_glow()
            if not self._slot_anim_timer.isActive():
                self._slot_anim_timer.start()
        self._refresh_transport_icons()
        self.update()
        self.playing_changed.emit(playing)

    def _refresh_transport_icons(self) -> None:
        if not hasattr(self, "_play_btn"):
            return
        icon_name = "pause" if self._playing else "play"
        self._play_btn.setIcon(app_icon(icon_name, size=14, color="#FFFFFF" if self._playing else "#D7DAE7"))
        self._play_btn.setIconSize(icon_size(13))
        self._play_btn.setProperty("playing", bool(self._playing))
        self._play_btn.style().unpolish(self._play_btn)
        self._play_btn.style().polish(self._play_btn)

    def _toggle_play(self) -> None:
        self._set_playing(not self._playing)

    def _tick_slot_animation(self) -> None:
        self._slot_anim_tick = (self._slot_anim_tick + 1) % 10000
        self._advance_led_afterglow()
        if not self._playing and not self._has_visible_afterglow():
            self._slot_anim_timer.stop()
        self.update()

    def _step(self, delta_ms: int) -> None:
        self._set_position_ms(self._position_ms + int(delta_ms))

    def _stop(self) -> None:
        self._set_playing(False)
        self._set_position_ms(0)

    def _position_from_point(self, point: QPointF) -> int:
        dial = self._dial_rect()
        center = dial.center()
        angle = math.atan2(point.y() - center.y(), point.x() - center.x())
        normalized = (angle + math.pi * 1.25) / (math.pi * 1.5)
        normalized = max(0.0, min(1.0, normalized))
        return int(round(normalized * self._duration_ms))

    def mousePressEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._dial_rect().contains(event.position()):
            self._dial_pressed = True
            self._set_position_ms(self._position_from_point(event.position()))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._dial_pressed:
            self._set_position_ms(self._position_from_point(event.position()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if self._dial_pressed and event.button() == Qt.MouseButton.LeftButton:
            self._dial_pressed = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        if event.button() == Qt.MouseButton.LeftButton and self._dial_rect().contains(event.position()):
            self._set_playing(not self._playing)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        delta = 250 if event.angleDelta().y() > 0 else -250
        self._step(delta)
        event.accept()

    def _draw_deck_key(self, p: QPainter, rect: QRectF, label: str, value: float, accent: QColor) -> None:
        value = max(0.0, min(1.0, float(value)))
        grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        grad.setColorAt(0.0, QColor(34, 40, 47, 235))
        grad.setColorAt(1.0, QColor(18, 22, 27, 245))
        p.setBrush(grad)
        p.setPen(QPen(QColor(82, 92, 104, 96), 0.85))
        p.drawRoundedRect(rect, 4.5, 4.5)

        fill = QRectF(rect.left() + 5.0, rect.bottom() - 5.0, max(4.0, (rect.width() - 10.0) * value), 1.8)
        accent_line = QColor(accent)
        accent_line.setAlpha(186)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(accent_line)
        p.drawRoundedRect(fill, 1.0, 1.0)

        font = p.font()
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(218, 224, 234, 170))
        p.drawText(rect.adjusted(1.0, 1.0, -1.0, -3.0), Qt.AlignmentFlag.AlignCenter, label)

    def _draw_mode_key(self, p: QPainter, rect: QRectF, label: str, active: bool) -> None:
        fill = QColor(176, 182, 180, 218) if active else QColor(22, 27, 33, 235)
        border = QColor(230, 235, 236, 70) if active else QColor(82, 92, 104, 72)
        p.setPen(QPen(border, 0.85))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 4.0, 4.0)
        font = p.font()
        font.setPixelSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(24, 27, 29, 230) if active else QColor(206, 214, 225, 145))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_slotted_jog_dial(self, p: QPainter, dial: QRectF) -> None:
        center = dial.center()
        radius = dial.width() * 0.5

        metal = dial.adjusted(radius * 0.13, radius * 0.13, -radius * 0.13, -radius * 0.13)
        texture_used = not self._dial_texture.isNull()
        if texture_used:
            texture_rect = dial.adjusted(-radius * 0.20, -radius * 0.20, radius * 0.20, radius * 0.20)
            source = QRectF(self._dial_texture.rect()).adjusted(115.0, 115.0, -115.0, -115.0)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            p.save()
            clip = QPainterPath()
            clip.addEllipse(texture_rect.adjusted(1.0, 1.0, -1.0, -1.0))
            p.setClipPath(clip)
            p.drawPixmap(texture_rect, self._dial_texture, source)
            p.restore()
        else:
            p.setPen(QPen(QColor(5, 7, 9, 220), 1.0))
            p.setBrush(QColor(8, 10, 13, 235))
            p.drawEllipse(dial.adjusted(-8.0, -8.0, 8.0, 8.0))

            outer = dial.adjusted(radius * 0.02, radius * 0.02, -radius * 0.02, -radius * 0.02)
            outer_grad = QRadialGradient(center, radius)
            outer_grad.setColorAt(0.0, QColor(44, 48, 50, 222))
            outer_grad.setColorAt(0.58, QColor(28, 31, 33, 240))
            outer_grad.setColorAt(0.84, QColor(10, 12, 14, 250))
            outer_grad.setColorAt(1.0, QColor(4, 5, 6, 255))
            p.setPen(QPen(QColor(225, 230, 236, 34), 1.0))
            p.setBrush(QBrush(outer_grad))
            p.drawEllipse(outer)

            metal_grad = QRadialGradient(
                QPointF(center.x() - radius * 0.14, center.y() - radius * 0.18),
                radius * 0.90,
            )
            metal_grad.setColorAt(0.0, QColor(178, 181, 174, 220))
            metal_grad.setColorAt(0.25, QColor(108, 112, 110, 232))
            metal_grad.setColorAt(0.54, QColor(57, 62, 62, 242))
            metal_grad.setColorAt(0.78, QColor(88, 91, 86, 232))
            metal_grad.setColorAt(1.0, QColor(18, 20, 21, 252))
            p.setPen(QPen(QColor(240, 244, 245, 28), 0.8))
            p.setBrush(QBrush(metal_grad))
            p.drawEllipse(metal)

            for i in range(80):
                angle = math.radians(i * 360.0 / 80.0)
                p.setPen(QPen(QColor(245, 247, 242, 4 if i % 5 else 7), 0.22))
                start = QPointF(
                    center.x() + math.cos(angle) * radius * 0.18,
                    center.y() + math.sin(angle) * radius * 0.18,
                )
                end = QPointF(
                    center.x() + math.cos(angle) * radius * 0.69,
                    center.y() + math.sin(angle) * radius * 0.69,
                )
                p.drawLine(start, end)

            for scale, alpha in ((0.28, 10), (0.48, 12), (0.69, 15)):
                p.setPen(QPen(QColor(255, 255, 255, alpha), 0.45))
                inset = radius * (1.0 - scale)
                p.drawEllipse(dial.adjusted(inset, inset, -inset, -inset))

        slot_count = 8
        self._ensure_slot_buffers(slot_count)
        active_index = self._slot_index(slot_count)
        slot_radius = radius * 0.82
        slot_w = max(1.35, radius * 0.022)
        slot_h = max(3.4, radius * 0.052)

        for i in range(slot_count):
            angle_deg = -90.0 + i * 360.0 / slot_count
            angle = math.radians(angle_deg)
            slot_center = QPointF(
                center.x() + math.cos(angle) * slot_radius,
                center.y() + math.sin(angle) * slot_radius,
            )
            intensity = max(0.0, min(1.0, float(self._slot_glow_values[i])))

            p.save()
            p.translate(slot_center)
            p.rotate(angle_deg + 90.0)
            slot = QRectF(-slot_w * 0.5, -slot_h * 0.5, slot_w, slot_h)
            if intensity > 0.025:
                warm_peak = i == active_index and intensity > 0.82
                bloom_radius = max(slot_w, slot_h) * (2.8 + intensity * 3.2)
                bloom = QRadialGradient(QPointF(0.0, 0.0), bloom_radius)
                bloom_color = QColor(255, 222, 124, int(150 * intensity)) if warm_peak else QColor(102, 228, 177, int(92 * intensity))
                bloom.setColorAt(0.0, bloom_color)
                fade = QColor(bloom_color)
                fade.setAlpha(0)
                bloom.setColorAt(1.0, fade)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(bloom))
                p.drawEllipse(QRectF(-bloom_radius, -bloom_radius, bloom_radius * 2.0, bloom_radius * 2.0))

                halo = QColor(255, 226, 143, int(120 * intensity)) if warm_peak else QColor(96, 217, 169, int(82 * intensity))
                p.setBrush(halo)
                p.drawRoundedRect(slot.adjusted(-3.2, -2.8, 3.2, 2.8), slot_w * 0.95, slot_w * 0.95)

            p.setPen(QPen(QColor(0, 0, 0, 118), 0.45))
            if intensity > 0.025:
                if i == active_index and intensity > 0.82:
                    fill = QColor(255, 235, 158, int(226 + 29 * intensity))
                else:
                    fill = QColor(110, 230, 176, int(118 + 118 * intensity))
            else:
                fill = QColor(5, 6, 7, 132)
            p.setBrush(fill)
            p.drawRoundedRect(slot, slot_w * 0.45, slot_w * 0.45)
            if intensity > 0.025:
                p.setPen(QPen(QColor(255, 252, 220, int(90 + 125 * intensity)), 0.42 if intensity > 0.75 else 0.32))
                p.drawLine(QPointF(0.0, slot.top() + 1.2), QPointF(0.0, slot.bottom() - 1.2))
            p.restore()

        if not texture_used:
            cap = QRectF(center.x() - radius * 0.11, center.y() - radius * 0.11, radius * 0.22, radius * 0.22)
            cap_grad = QRadialGradient(cap.center(), cap.width() * 0.58)
            cap_grad.setColorAt(0.0, QColor(168, 170, 164, 36))
            cap_grad.setColorAt(0.54, QColor(78, 82, 80, 64))
            cap_grad.setColorAt(1.0, QColor(18, 20, 21, 118))
            p.setPen(QPen(QColor(240, 244, 245, 18), 0.55))
            p.setBrush(QBrush(cap_grad))
            p.drawEllipse(cap)
        if self._playing:
            p.setPen(QPen(QColor(104, 144, 128, 108), 0.9))
            p.setBrush(Qt.BrushStyle.NoBrush)
            active_ring = (
                dial.adjusted(radius * 0.23, radius * 0.23, -radius * 0.23, -radius * 0.23)
                if texture_used
                else metal.adjusted(radius * 0.08, radius * 0.08, -radius * 0.08, -radius * 0.08)
            )
            p.drawEllipse(active_ring)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

        panel_grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        panel_grad.setColorAt(0.0, QColor(20, 24, 30, 246))
        panel_grad.setColorAt(1.0, QColor(10, 13, 16, 248))
        p.setPen(QPen(QColor(178, 186, 202, 32), 1.0))
        p.setBrush(panel_grad)
        p.drawRoundedRect(rect, 8.0, 8.0)

        deck = self._deck_rect()
        deck_grad = QLinearGradient(deck.topLeft(), deck.bottomLeft())
        deck_grad.setColorAt(0.0, QColor(25, 30, 36, 235))
        deck_grad.setColorAt(1.0, QColor(13, 17, 21, 244))
        p.setPen(QPen(QColor(178, 186, 202, 34), 1.0))
        p.setBrush(deck_grad)
        p.drawRoundedRect(deck, 8.0, 8.0)
        p.setPen(QPen(QColor(220, 225, 238, 18), 0.8))
        p.drawLine(QPointF(deck.left() + 10.0, deck.top() + 2.0), QPointF(deck.right() - 10.0, deck.top() + 2.0))

        font = p.font()
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(150, 160, 172, 118))
        p.drawText(QRectF(deck.left() + 13.0, deck.top() + 9.0, 92.0, 16.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "EDIT KEYS")
        p.drawText(QRectF(self._display_rect().left(), deck.top() + 9.0, 92.0, 16.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "TRANSPORT")

        for aux_rect, (label, value, accent) in zip(self._aux_key_rects(), self._aux_dial_specs()):
            self._draw_deck_key(p, aux_rect, label, value, accent)

        display = self._display_rect()
        p.setPen(QPen(QColor(85, 95, 108, 72), 0.9))
        p.setBrush(QColor(8, 11, 14, 226))
        p.drawRoundedRect(display, 5.0, 5.0)
        font = p.font()
        font.setPixelSize(16)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(198, 211, 206, 218))
        p.drawText(display.adjusted(9.0, 4.0, -8.0, -18.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{_fmt_ms(self._position_ms)}")
        font.setPixelSize(7)
        font.setBold(False)
        p.setFont(font)
        p.setPen(QColor(150, 160, 172, 115))
        p.drawText(display.adjusted(9.0, 23.0, -8.0, -4.0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"of {_fmt_ms(self._duration_ms)}  jog ready")
        rail_left = display.left()
        rail_top = display.bottom() + 12.0
        rail_w = display.width()
        for row, color in enumerate((QColor(118, 145, 123, 142), QColor(90, 139, 154, 132), QColor(164, 150, 105, 126))):
            y = rail_top + row * 10.0
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(8, 10, 12, 155))
            p.drawRoundedRect(QRectF(rail_left, y, rail_w, 3.4), 1.7, 1.7)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(rail_left, y, rail_w * (0.72 - row * 0.16), 3.4), 1.7, 1.7)

        self._draw_slotted_jog_dial(p, self._dial_rect())

        meter = self._meter_rect()
        p.setPen(QPen(QColor(178, 186, 202, 32), 1.0))
        p.setBrush(QColor(8, 10, 12, 190))
        p.drawRoundedRect(meter.adjusted(-4.0, -4.0, 4.0, 4.0), 4.0, 4.0)
        bars = 12
        active = int(round(max(0.0, min(1.0, self._level)) * bars))
        gap = 2.0
        bar_h = (meter.height() - gap * (bars - 1)) / bars
        for index in range(bars):
            y = meter.bottom() - (index + 1) * bar_h - index * gap
            bar = QRectF(meter.left(), y, meter.width(), max(1.0, bar_h))
            if index < active:
                if index >= 10:
                    color = QColor(236, 117, 102, 232)
                elif index >= 8:
                    color = QColor(229, 192, 103, 226)
                else:
                    color = QColor(132, 218, 157, 216)
            else:
                color = QColor(74, 80, 90, 72)
            p.setPen(Qt.PenStyle.NoPen)
            if active > 0 and index == active - 1:
                bloom = QColor(color)
                bloom.setAlpha(92)
                p.setBrush(bloom)
                p.drawRoundedRect(bar.adjusted(-4.0, -2.6, 4.0, 2.6), 2.4, 2.4)
                bloom.setAlpha(38)
                p.setBrush(bloom)
                p.drawRoundedRect(bar.adjusted(-7.0, -4.5, 7.0, 4.5), 3.2, 3.2)
            p.setBrush(color)
            p.drawRoundedRect(bar, 1.5, 1.5)
            if index < active:
                p.setPen(QPen(QColor(255, 255, 228, 56 if index < active - 1 else 112), 0.55))
                p.drawLine(QPointF(bar.left() + 1.2, bar.top() + 1.0), QPointF(bar.right() - 1.2, bar.top() + 1.0))
                p.setPen(Qt.PenStyle.NoPen)
        p.end()

class _MiniWaveformStrip(QWidget):
    """Compact waveform evidence strip for the renewed sound editor."""

    zoom_requested = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._zoom_factor = 1.0
        self._scroll_norm = 0.0
        self._drag_start_x: float | None = None
        self._drag_start_scroll = 0.0
        self._playhead_source_ms = -1
        self._last_gap_count = 0
        self._playback_drop_marks: list[int] = []
        self.setObjectName("SoundWaveformStrip")
        self.setMinimumHeight(86)
        self.setMaximumHeight(104)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self._zoom_buttons: dict[float, QPushButton] = {}
        self._build_zoom_buttons()

    def _build_zoom_buttons(self) -> None:
        for text, factor in (("Fit", 1.0), ("2x", 2.0), ("4x", 4.0), ("8x", 8.0)):
            button = QPushButton(text, self)
            button.setObjectName("SoundWaveZoomButton")
            button.setFixedSize(32 if text == "Fit" else 30, 18)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, f=factor: self.zoom_requested.emit(f))
            self._zoom_buttons[factor] = button
        self._refresh_zoom_buttons()
        self._layout_zoom_buttons()

    def zoom_buttons(self) -> dict[float, QPushButton]:
        return self._zoom_buttons

    def _layout_zoom_buttons(self) -> None:
        if not self._zoom_buttons:
            return
        ordered = [self._zoom_buttons[factor] for factor in (1.0, 2.0, 4.0, 8.0)]
        gap = 4
        total = sum(button.width() for button in ordered) + gap * (len(ordered) - 1)
        x = max(9, self.width() - total - 12)
        y = 4
        for button in ordered:
            button.move(x, y)
            button.raise_()
            x += button.width() + gap

    def _refresh_zoom_buttons(self) -> None:
        for zoom, button in self._zoom_buttons.items():
            selected = abs(float(zoom) - float(self._zoom_factor)) < 0.01
            button.setProperty("selected", bool(selected))
            button.style().unpolish(button)
            button.style().polish(button)

    def resizeEvent(self, event) -> None:  # pragma: no cover - visual QA
        self._layout_zoom_buttons()
        super().resizeEvent(event)

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self._scroll_norm = 0.0
        if clip is None:
            self._playhead_source_ms = -1
        else:
            local_ms = int(getattr(clip, "_se_jog_ms", 0) or 0)
            trim_start = int(getattr(clip, "trim_start_ms", 0) or 0)
            self._playhead_source_ms = max(0, trim_start + local_ms)
        self._playback_drop_marks = []
        self.update()

    def picture_sync_marker_count(self) -> int:
        clip = self._clip
        markers = getattr(clip, "_picture_sync_markers", None) if clip is not None else None
        return len(markers or [])

    def refresh(self) -> None:
        self.update()

    def zoom_factor(self) -> float:
        return float(self._zoom_factor)

    def set_zoom_factor(self, factor: float) -> None:
        self._zoom_factor = max(1.0, min(16.0, float(factor or 1.0)))
        if self._zoom_factor <= 1.001:
            self._scroll_norm = 0.0
        elif self._playhead_source_ms >= 0:
            self._ensure_source_visible(self._playhead_source_ms, center=True)
        self._refresh_zoom_buttons()
        self.update()

    def zoom_in(self) -> None:
        self.set_zoom_factor(self._zoom_factor * 2.0)

    def zoom_out(self) -> None:
        self.set_zoom_factor(self._zoom_factor / 2.0)

    def _trim_window_ms(self) -> tuple[int, int, int, int]:
        clip = self._clip
        if clip is None:
            return 0, 1, 0, 1
        trim_start = int(getattr(clip, "trim_start_ms", 0) or 0)
        trim_end = int(getattr(clip, "trim_end_ms", getattr(clip, "duration_ms", 0)) or 0)
        duration = max(1, int(getattr(clip, "duration_ms", 0) or 0))
        if trim_end <= trim_start:
            trim_end = duration
        trim_end = max(trim_start + 1, min(duration, trim_end))
        full = max(1, trim_end - trim_start)
        visible = max(1, int(round(full / max(1.0, self._zoom_factor))))
        if visible >= full:
            return trim_start, trim_end, trim_start, trim_end
        max_offset = full - visible
        offset = int(round(max_offset * max(0.0, min(1.0, self._scroll_norm))))
        return trim_start + offset, trim_start + offset + visible, trim_start, trim_end

    def set_playhead_source_ms(self, source_ms: int, *, center: bool = False) -> None:
        self._playhead_source_ms = max(0, int(source_ms))
        self._ensure_source_visible(self._playhead_source_ms, center=center)
        self.update()

    def clear_playhead(self) -> None:
        self._playhead_source_ms = -1
        self.update()

    def dropout_count(self) -> int:
        return int(self._last_gap_count)

    def set_playback_drop_marks(self, marks: list[int] | tuple[int, ...]) -> None:
        self._playback_drop_marks = sorted({max(0, int(mark)) for mark in list(marks or [])})[-80:]
        self.update()

    def playback_drop_count(self) -> int:
        return len(self._playback_drop_marks)

    def _ensure_source_visible(self, source_ms: int, *, center: bool = False) -> None:
        if self._zoom_factor <= 1.001 or self._clip is None:
            return
        view_start, view_end, trim_start, trim_end = self._trim_window_ms()
        full = max(1, trim_end - trim_start)
        visible = max(1, view_end - view_start)
        if visible >= full:
            self._scroll_norm = 0.0
            return
        margin = max(20, int(visible * 0.12))
        if not center and view_start + margin <= source_ms <= view_end - margin:
            return
        target_offset = int(source_ms) - trim_start - visible // 2
        target_offset = max(0, min(full - visible, target_offset))
        self._scroll_norm = target_offset / max(1, full - visible)

    def wheelEvent(self, event) -> None:  # pragma: no cover - visual QA
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()
        event.accept()

    def mousePressEvent(self, event) -> None:  # pragma: no cover - visual QA
        if event.button() == Qt.MouseButton.LeftButton and self._zoom_factor > 1.001:
            self._drag_start_x = float(event.position().x())
            self._drag_start_scroll = float(self._scroll_norm)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # pragma: no cover - visual QA
        if self._drag_start_x is not None and self._zoom_factor > 1.001:
            width = max(1.0, float(self.width()))
            delta_norm = (self._drag_start_x - float(event.position().x())) / width
            self._scroll_norm = max(0.0, min(1.0, self._drag_start_scroll + delta_norm * 1.35))
            self.update()
            event.accept()
            return
        if self._zoom_factor > 1.001:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # pragma: no cover - visual QA
        if self._drag_start_x is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_x = None
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._zoom_factor > 1.001 else Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(root.topLeft(), root.bottomLeft())
        bg.setColorAt(0.0, QColor(25, 29, 34, 206))
        bg.setColorAt(1.0, QColor(13, 15, 17, 230))
        p.setPen(QPen(QColor(178, 186, 202, 28), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(root, 6.0, 6.0)

        clip = self._clip
        plot = root.adjusted(9.0, 18.0, -9.0, -13.0)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
        p.drawLine(QPointF(plot.left(), plot.center().y()), QPointF(plot.right(), plot.center().y()))

        title_font = p.font()
        title_font.setPixelSize(8)
        title_font.setBold(True)
        p.setFont(title_font)
        p.setPen(QColor("#A7AFBA"))
        label = "waveform"
        if clip is not None:
            view_start, view_end, trim_start, trim_end = self._trim_window_ms()
            if self._zoom_factor > 1.001:
                label = f"waveform  {_fmt_ms(view_start)}-{_fmt_ms(view_end)}  {self._zoom_factor:.0f}x"
            else:
                label = f"waveform  {_fmt_ms(trim_start)}-{_fmt_ms(trim_end)}  fit"
        p.drawText(root.adjusted(9, 3, -9, -root.height() + 14), Qt.AlignmentFlag.AlignLeft, label)

        wf = getattr(clip, "waveform", None) if clip is not None else None
        if wf is None or not getattr(wf, "size", 0):
            p.setPen(QColor("#6F7782"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "waveform pending")
            return

        try:
            import numpy as np

            data = np.asarray(wf, dtype=np.float32)
            mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
            if not mono.size:
                return
            view_start, view_end, trim_start, trim_end = self._trim_window_ms()
            duration = max(1, int(getattr(clip, "duration_ms", 0) or 0))
            start_i = max(0, min(mono.size - 1, int(mono.size * view_start / duration)))
            end_i = max(start_i + 1, min(mono.size, int(mono.size * max(view_end, view_start + 1) / duration)))
            mono = mono[start_i:end_i]
            if not mono.size:
                return
            count = max(2, int(plot.width()))
            edges = np.linspace(0, mono.size, count + 1, dtype=np.int32)
            env = np.zeros(count, dtype=np.float32)
            for i in range(count):
                lo = int(max(0, min(mono.size - 1, edges[i])))
                hi = int(max(lo + 1, min(mono.size, edges[i + 1])))
                segment = mono[lo:hi]
                env[i] = float(np.max(np.abs(segment))) if segment.size else 0.0
            peak = max(float(np.max(env)), 0.005)
            cy = plot.center().y()
            amp = max(9.0, plot.height() * 0.46)
            pts_top: list[QPointF] = []
            pts_bot: list[QPointF] = []
            for i, val in enumerate(env):
                x = plot.left() + i / max(count - 1, 1) * plot.width()
                h = max(0.0, min(1.0, float(val) / peak)) * amp
                pts_top.append(QPointF(x, cy - h))
                pts_bot.append(QPointF(x, cy + h))

            path = QPainterPath()
            if pts_top and pts_bot:
                path.moveTo(pts_top[0])
                for point in pts_top[1:]:
                    path.lineTo(point)
                for point in reversed(pts_bot):
                    path.lineTo(point)
                path.closeSubpath()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(118, 145, 123, 42))
                p.drawPath(path)

            median = float(np.quantile(env, 0.62)) if env.size else 0.0
            threshold = max(0.018, median * 0.34)
            min_gap_px = max(2, int(round(plot.width() * 0.0018)))
            gaps: list[tuple[int, int]] = []
            start = -1
            for i, value in enumerate(env):
                if float(value) <= threshold:
                    if start < 0:
                        start = i
                elif start >= 0:
                    if i - start >= min_gap_px:
                        gaps.append((start, i))
                    start = -1
            if start >= 0 and count - start >= min_gap_px:
                gaps.append((start, count))
            filtered_gaps: list[tuple[int, int]] = []
            for start_i_px, end_i_px in gaps:
                left_context = env[max(0, start_i_px - 8):start_i_px]
                right_context = env[end_i_px:min(count, end_i_px + 8)]
                left_peak = float(left_context.max()) if left_context.size else 0.0
                right_peak = float(right_context.max()) if right_context.size else 0.0
                context_peak = max(left_peak, right_peak)
                if context_peak < threshold * 1.7 and median > threshold * 1.35:
                    continue
                filtered_gaps.append((start_i_px, end_i_px))
            self._last_gap_count = len(filtered_gaps)
            for start_i_px, end_i_px in filtered_gaps:
                left = plot.left() + start_i_px / max(count - 1, 1) * plot.width()
                right = plot.left() + max(start_i_px + 1, end_i_px - 1) / max(count - 1, 1) * plot.width()
                gap_rect = QRectF(left, plot.top(), max(1.5, right - left), plot.height())
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(214, 96, 86, 34))
                p.drawRoundedRect(gap_rect, 1.5, 1.5)
            if filtered_gaps:
                p.setPen(QColor(214, 126, 112, 176))
                gap_label = f"source dips {len(filtered_gaps)}"
                p.drawText(QRectF(plot.right() - 112.0, root.top() + 3.0, 104.0, 12.0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, gap_label)

            p.setPen(QPen(QColor(142, 218, 158, 226), 1.15))
            p.drawPolyline(pts_top)
            p.setPen(QPen(QColor(105, 181, 218, 190), 0.85))
            p.drawPolyline(pts_bot)

            picture_markers = [
                row for row in list(getattr(clip, "_picture_sync_markers", []) or [])
                if view_start <= int(row.get("source_ms", -1) or -1) <= view_end
            ][:24]
            marker_colors = {
                "clip": QColor(232, 238, 246, 174),
                "transition": QColor(191, 159, 255, 196),
                "fade": QColor(157, 214, 154, 188),
                "motion": QColor(111, 188, 224, 190),
                "title": QColor(236, 196, 114, 188),
                "speed": QColor(212, 159, 114, 184),
                "repair": QColor(236, 128, 124, 190),
            }
            for marker in picture_markers:
                source_ms = int(marker.get("source_ms", 0) or 0)
                ratio = (source_ms - view_start) / max(1, view_end - view_start)
                x = plot.left() + max(0.0, min(1.0, ratio)) * plot.width()
                kind = str(marker.get("kind") or "clip")
                color = marker_colors.get(kind, QColor(232, 238, 246, 168))
                p.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 88), 3.0))
                p.drawLine(QPointF(x, plot.top() + 3.0), QPointF(x, plot.bottom() - 3.0))
                p.setPen(QPen(color, 1.05))
                p.drawLine(QPointF(x, plot.top() - 3.0), QPointF(x, plot.bottom() + 2.0))
                p.setBrush(color)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(x, plot.top() - 5.0), 2.3, 2.3)
            if picture_markers:
                p.setPen(QColor(190, 206, 224, 212))
                first_label = str(picture_markers[0].get("label") or "sync")[:18]
                p.drawText(
                    QRectF(plot.left() + 4.0, root.top() + 3.0, 176.0, 12.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"picture sync {len(getattr(clip, '_picture_sync_markers', []) or [])}: {first_label}",
                )

            fade_in = int(getattr(clip, "fade_in_ms", 0) or 0)
            fade_out = int(getattr(clip, "fade_out_ms", 0) or 0)
            eff = max(1, view_end - view_start)
            if fade_in > 0:
                visible_fade = max(0, min(view_end, trim_start + fade_in) - view_start)
                w = min(plot.width(), plot.width() * visible_fade / eff)
                grad = QLinearGradient(QPointF(plot.left(), 0), QPointF(plot.left() + w, 0))
                grad.setColorAt(0.0, QColor(0, 0, 0, 110))
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.fillRect(QRectF(plot.left(), plot.top(), w, plot.height()), grad)
            if fade_out > 0:
                fade_start = trim_end - fade_out
                visible_fade = max(0, view_end - max(view_start, fade_start))
                w = min(plot.width(), plot.width() * visible_fade / eff)
                grad = QLinearGradient(QPointF(plot.right() - w, 0), QPointF(plot.right(), 0))
                grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(0, 0, 0, 110))
                p.fillRect(QRectF(plot.right() - w, plot.top(), w, plot.height()), grad)
            if self._zoom_factor > 1.001:
                full = max(1, trim_end - trim_start)
                visible = max(1, view_end - view_start)
                rail = QRectF(plot.left(), root.bottom() - 8.0, plot.width(), 3.0)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 255, 255, 24))
                p.drawRoundedRect(rail, 1.5, 1.5)
                thumb_w = max(18.0, rail.width() * visible / full)
                max_left = max(0.0, rail.width() - thumb_w)
                thumb = QRectF(rail.left() + max_left * self._scroll_norm, rail.top(), thumb_w, rail.height())
                p.setBrush(QColor(142, 218, 158, 140))
                p.drawRoundedRect(thumb, 1.5, 1.5)
            visible_preview_drops = [
                mark for mark in self._playback_drop_marks
                if view_start <= int(mark) <= view_end
            ]
            for mark in visible_preview_drops:
                ratio = (int(mark) - view_start) / max(1, view_end - view_start)
                x = plot.left() + max(0.0, min(1.0, ratio)) * plot.width()
                band = QRectF(x - 2.0, plot.top(), 4.0, plot.height())
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(240, 176, 70, 80))
                p.drawRoundedRect(band, 2.0, 2.0)
                p.setPen(QPen(QColor(244, 191, 88, 220), 1.0))
                p.drawLine(QPointF(x, plot.top() - 1.0), QPointF(x, plot.bottom() + 2.0))
            if visible_preview_drops:
                p.setPen(QColor(245, 196, 96, 220))
                p.drawText(
                    QRectF(plot.left(), root.top() + 3.0, 128.0, 12.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    f"preview drops {len(self._playback_drop_marks)}",
                )
            if self._playhead_source_ms >= 0 and view_start <= self._playhead_source_ms <= view_end:
                ratio = (self._playhead_source_ms - view_start) / max(1, view_end - view_start)
                x = plot.left() + max(0.0, min(1.0, ratio)) * plot.width()
                p.setPen(QPen(QColor(255, 93, 82, 230), 1.55))
                p.drawLine(QPointF(x, plot.top() - 2.0), QPointF(x, plot.bottom() + 3.0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(255, 93, 82, 230))
                top_marker = QPainterPath()
                top_marker.moveTo(QPointF(x, plot.top() - 2.0))
                top_marker.lineTo(QPointF(x - 4.0, plot.top() - 8.0))
                top_marker.lineTo(QPointF(x + 4.0, plot.top() - 8.0))
                top_marker.closeSubpath()
                p.drawPath(top_marker)
                p.setPen(QColor(255, 185, 176, 218))
                p.drawText(
                    QRectF(max(plot.left(), x + 5.0), plot.top() - 14.0, 64.0, 12.0),
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    _fmt_ms(self._playhead_source_ms),
                )
        except Exception:
            self._last_gap_count = 0
            p.setPen(QColor("#6F7782"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "waveform unavailable")

class _MiniSpectrumStrip(QWidget):
    """Small spectrum / level evidence strip derived from the active clip."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self.setObjectName("SoundSpectrumStrip")
        self.setMinimumHeight(42)
        self.setMaximumHeight(48)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.update()

    def refresh(self) -> None:
        self.update()

    @staticmethod
    def _spectrum_from_waveform(waveform: Any, count: int = 28) -> tuple[list[float], float]:
        import numpy as np

        data = np.asarray(waveform, dtype=np.float32)
        mono = (data[0] + data[1]) * 0.5 if data.ndim == 2 and data.shape[0] == 2 else data.ravel()
        if mono.size < 8:
            return [], 0.0
        mono = mono[-min(mono.size, 2048):]
        level = float(np.sqrt(np.mean(np.square(mono)))) if mono.size else 0.0
        centered = mono - float(np.mean(mono))
        window = np.hanning(centered.size).astype(np.float32)
        mag = np.abs(np.fft.rfft(centered * window)).astype(np.float32)
        if mag.size <= 2:
            return [], level
        mag = mag[1:]
        edges = np.geomspace(1, max(2, mag.size), count + 1).astype(np.int32)
        bins: list[float] = []
        for i in range(count):
            lo = int(max(0, min(mag.size - 1, edges[i] - 1)))
            hi = int(max(lo + 1, min(mag.size, edges[i + 1])))
            bins.append(float(np.mean(mag[lo:hi])))
        peak = max(max(bins), 1e-5)
        return [max(0.02, min(1.0, value / peak)) for value in bins], level

    def paintEvent(self, event) -> None:  # pragma: no cover - visual QA
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        root = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        bg = QLinearGradient(root.topLeft(), root.bottomLeft())
        bg.setColorAt(0.0, QColor(24, 27, 31, 196))
        bg.setColorAt(1.0, QColor(11, 13, 15, 224))
        p.setPen(QPen(QColor(178, 186, 202, 24), 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(root, 5.5, 5.5)

        label_font = p.font()
        label_font.setPixelSize(8)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QColor("#9EA7B3"))
        p.drawText(root.adjusted(8, 3, -8, -root.height() + 14), Qt.AlignmentFlag.AlignLeft, "spectrum / level")

        clip = self._clip
        plot = root.adjusted(8.0, 17.0, -74.0, -7.0)
        meter = QRectF(root.right() - 58.0, plot.top(), 48.0, plot.height())
        bins: list[float] = []
        level = 0.0
        try:
            import numpy as np

            spectrum = getattr(clip, "spectrum_bins", None) if clip is not None else None
            if spectrum is not None and getattr(spectrum, "size", 0):
                raw = np.asarray(spectrum, dtype=np.float32).ravel()
                peak = max(float(raw.max()), 1e-5)
                step = max(1, int(len(raw) / 28))
                bins = [max(0.02, min(1.0, float(raw[i:i + step].mean()) / peak)) for i in range(0, len(raw), step)][:28]
                wf = getattr(clip, "waveform", None)
                if wf is not None and getattr(wf, "size", 0):
                    level = float(np.sqrt(np.mean(np.square(np.asarray(wf, dtype=np.float32)))))
            else:
                wf = getattr(clip, "waveform", None) if clip is not None else None
                if wf is not None and getattr(wf, "size", 0):
                    bins, level = self._spectrum_from_waveform(wf)
        except Exception:
            bins = []
            level = 0.0

        if not bins:
            p.setPen(QColor("#68717D"))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "spectrum pending")
            return

        count = len(bins)
        gap = 2.0
        bar_w = max(2.0, (plot.width() - gap * (count - 1)) / max(1, count))
        for i, value in enumerate(bins):
            x = plot.left() + i * (bar_w + gap)
            h = max(2.0, plot.height() * (0.16 + float(value) * 0.82))
            bar = QRectF(x, plot.bottom() - h, bar_w, h)
            grad = QLinearGradient(bar.topLeft(), bar.bottomLeft())
            if i < count * 0.38:
                top = QColor("#7FD79A")
            elif i < count * 0.72:
                top = QColor("#6CB9DA")
            elif i < count * 0.90:
                top = QColor("#D8B35F")
            else:
                top = QColor("#D9806D")
            top.setAlpha(212)
            mid = QColor(top)
            mid.setAlpha(106)
            grad.setColorAt(0.0, top)
            grad.setColorAt(0.55, mid)
            grad.setColorAt(1.0, QColor(38, 43, 49, 230))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(bar, 1.6, 1.6)

        safe_level = max(0.0, min(1.0, float(level) * 3.0))
        p.setPen(QPen(QColor(255, 255, 255, 28), 1.0))
        p.drawRoundedRect(meter, 3.0, 3.0)
        p.setPen(QPen(QColor(216, 179, 95, 68), 0.75))
        p.drawLine(QPointF(meter.left() + 2.0, meter.top() + meter.height() * 0.42), QPointF(meter.right() - 2.0, meter.top() + meter.height() * 0.42))
        p.setPen(QPen(QColor(217, 128, 109, 76), 0.75))
        p.drawLine(QPointF(meter.left() + 2.0, meter.top() + meter.height() * 0.18), QPointF(meter.right() - 2.0, meter.top() + meter.height() * 0.18))
        fill = QRectF(meter.left() + 2.0, meter.bottom() - 2.0 - (meter.height() - 4.0) * safe_level, meter.width() - 4.0, (meter.height() - 4.0) * safe_level)
        level_grad = QLinearGradient(fill.topLeft(), fill.bottomLeft())
        if safe_level >= 0.82:
            level_grad.setColorAt(0.0, QColor(217, 128, 109, 224))
            level_grad.setColorAt(0.28, QColor(216, 179, 95, 192))
        elif safe_level >= 0.58:
            level_grad.setColorAt(0.0, QColor(216, 179, 95, 214))
            level_grad.setColorAt(0.28, QColor(126, 215, 154, 172))
        else:
            level_grad.setColorAt(0.0, QColor(126, 215, 154, 214))
            level_grad.setColorAt(0.28, QColor(108, 185, 218, 128))
        level_grad.setColorAt(0.58, QColor(126, 215, 154, 128))
        level_grad.setColorAt(1.0, QColor(58, 64, 72, 220))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(level_grad)
        p.drawRoundedRect(fill, 2.0, 2.0)
