"""Small VideoEditorWindow-local widgets extracted from the main window module."""
from __future__ import annotations

import math

from PySide6.QtCore import QByteArray, QMimeData, QPoint, QPointF, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDrag, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QPushButton, QToolButton

from app.effect_cards import SPINE_MIME_TYPE
from app.icons import app_icon, icon_size


class _PreviewSurfaceLabel(QLabel):
    """Preview QLabel whose pixmap/text does not inflate the editor minimum size."""

    def minimumSizeHint(self) -> QSize:  # pragma: no cover - covered by UI QA
        return QSize(0, 0)

    def sizeHint(self) -> QSize:  # pragma: no cover - covered by UI QA
        return QSize(0, 0)

_ANTS_OWNER: str = ""

def _draw_marching_ants(painter: "QPainter", rect: "QRect", offset: int) -> None:
    """Draw the selected-clip outline.

    The old animated dashed border read like a debug selection marquee in
    product screenshots. Keep the function name for callers, but render a
    quiet catalog-style outline that still works on dark clips and thumbnails.
    """
    r = rect.adjusted(1, 1, -2, -2)
    if r.width() <= 0 or r.height() <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 104), 2))
    painter.drawRoundedRect(r.adjusted(0, 0, 0, 0), 3, 3)
    painter.setPen(QPen(QColor(226, 230, 236, 118), 1.1))
    painter.drawRoundedRect(r.adjusted(1, 1, -1, -1), 2, 2)
    painter.setPen(QPen(QColor(255, 91, 76, 150), 1.2))
    painter.drawLine(r.left() + 5, r.top() + 2, r.right() - 5, r.top() + 2)
    painter.restore()


class _DraggableLive2DButton(QPushButton):
    """Toolbar button: click=add actor, double-click=open editor, drag=place at position."""

    double_clicked = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._drag_start = None
        self._click_count = 0

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (self._drag_start is not None
                and e.buttons() & Qt.MouseButton.LeftButton):
            dist = (e.position().toPoint() - self._drag_start).manhattanLength()
            if dist > 8:
                self._drag_start = None
                from PySide6.QtGui import QDrag, QPixmap
                from PySide6.QtCore import QMimeData, QByteArray
                mime = QMimeData()
                mime.setData("application/x-live2d-actor-new", QByteArray(b"1"))
                pm = QPixmap(80, 22)
                pm.fill(QColor("#2a2a5a"))
                from PySide6.QtGui import QPainter as _P
                p = _P(pm)
                p.setPen(QColor("#c0c0e0"))
                p.drawPixmap(7, 4, app_icon("live2d", size=14, color="#c0c0e0").pixmap(icon_size(14)))
                p.drawText(pm.rect().adjusted(22, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, "Live2D")
                p.end()
                drag = QDrag(self)
                drag.setMimeData(mime)
                drag.setPixmap(pm)
                drag.setHotSpot(pm.rect().center())
                drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(e)


class _DraggableSpineButton(QPushButton):
    """Toolbar button: click=add actor, double-click=open editor, drag=place at position."""

    double_clicked = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._drag_start = None

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position().toPoint()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if (
            self._drag_start is not None
            and e.buttons() & Qt.MouseButton.LeftButton
        ):
            dist = (e.position().toPoint() - self._drag_start).manhattanLength()
            if dist > 8:
                self._drag_start = None
                from PySide6.QtCore import QByteArray, QMimeData
                from PySide6.QtGui import QDrag, QPainter as _P, QPixmap

                mime = QMimeData()
                mime.setData(SPINE_MIME_TYPE, QByteArray(b"1"))
                pm = QPixmap(80, 22)
                pm.fill(QColor("#3a2a2a"))
                p = _P(pm)
                p.setPen(QColor("#ffe0c0"))
                p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "Spine")
                p.end()
                drag = QDrag(self)
                drag.setMimeData(mime)
                drag.setPixmap(pm)
                drag.setHotSpot(pm.rect().center())
                drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(e)


class _AnimatedTimelineToolButton(QToolButton):
    """Painted timeline tool tile with Screen-Studio-like animated icon motion."""

    _ACCENTS = {
        "select": "#F3F5F8",
        "blade": "#F3F5F8",
        "ripple": "#F3F5F8",
        "roll": "#F3F5F8",
        "slip": "#F3F5F8",
        "slide": "#F3F5F8",
    }

    def __init__(self, mode: str, icon_name: str, parent=None) -> None:
        super().__init__(parent)
        self._mode = str(mode or "")
        self._icon_name = str(icon_name or "cursor")
        self._accent = QColor(self._ACCENTS.get(self._mode, "#F3F5F8"))
        self._phase = 0.0
        self._hover = False
        self._animation_suspended = False
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(33)
        self._anim_timer.timeout.connect(self._tick_icon_animation)
        self.toggled.connect(lambda _checked: self._sync_icon_animation())

    def set_timeline_icon(self, icon_name: str, color: str = "#D7DAE7") -> None:
        self._icon_name = str(icon_name or self._icon_name)
        if color:
            try:
                self._accent = QColor(color)
            except Exception:
                pass
        self.setIcon(QIcon())
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hover = True
        self._sync_icon_animation()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._hover = False
        self._sync_icon_animation()
        super().leaveEvent(event)

    def _sync_icon_animation(self) -> None:
        if self._animation_suspended:
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            return
        active = bool(self._hover or self.isChecked() or self.isDown())
        if active and not self._anim_timer.isActive():
            self._anim_timer.start()
        elif not active and self._anim_timer.isActive():
            self._anim_timer.stop()
            self._phase = 0.0
            self.update()

    def set_animation_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if suspended == self._animation_suspended:
            return
        self._animation_suspended = suspended
        if suspended:
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            return
        self._sync_icon_animation()

    def _tick_icon_animation(self) -> None:
        self._phase = (self._phase + 0.055) % 1.0
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        active = bool(self._hover or self.isChecked() or self.isDown())
        pulse = 0.0
        if active:
            pulse = (math.sin(self._phase * math.tau) + 1.0) * 0.5
        accent = QColor(self._accent)
        glow = QColor(accent)
        glow.setAlpha(18 if active else 0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        radius = 13 + int(5 * pulse)
        painter.drawEllipse(QPoint(rect.center().x(), rect.center().y()), radius, radius)
        if self._icon_name in {"cursor", "select", "pointer"}:
            self._paint_animated_cursor(painter, rect, active, pulse)
        else:
            self._paint_animated_app_icon(painter, rect, active, pulse)
        painter.end()

    def _paint_animated_cursor(self, painter: QPainter, rect: QRect, active: bool, pulse: float) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        lift = -2.0 - 2.5 * pulse if active else 0.0
        drift = 1.4 * math.sin(self._phase * math.tau) if active else 0.0
        s = min(rect.width(), rect.height()) * (0.56 + (0.05 * pulse if active else 0.0))
        ox = cx - s * 0.42 + drift
        oy = cy - s * 0.44 + lift
        path = QPainterPath()
        path.moveTo(ox + s * 0.18, oy + s * 0.02)
        path.lineTo(ox + s * 0.86, oy + s * 0.54)
        path.lineTo(ox + s * 0.55, oy + s * 0.61)
        path.lineTo(ox + s * 0.71, oy + s * 0.94)
        path.lineTo(ox + s * 0.52, oy + s * 1.02)
        path.lineTo(ox + s * 0.38, oy + s * 0.68)
        path.lineTo(ox + s * 0.15, oy + s * 0.86)
        path.closeSubpath()
        shadow = QPainterPath(path)
        painter.save()
        painter.translate(1.5, 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 120))
        painter.drawPath(shadow)
        painter.restore()
        grad = QLinearGradient(QPointF(ox, oy), QPointF(ox + s, oy + s))
        grad.setColorAt(0.0, QColor("#FFFFFF"))
        grad.setColorAt(0.52, QColor("#DDE2FF"))
        grad.setColorAt(1.0, QColor("#F3F5F8") if active else QColor("#BFC6DA"))
        painter.setBrush(grad)
        painter.setPen(QPen(QColor(255, 255, 255, 190), 1.3))
        painter.drawPath(path)
        if active:
            trail = QColor(self._accent)
            trail.setAlpha(90)
            painter.setPen(QPen(trail, 1.4))
            for idx in range(3):
                t = (self._phase + idx * 0.23) % 1.0
                x = rect.left() + 8 + t * (rect.width() - 16)
                y = rect.bottom() - 10 - idx * 5 - pulse * 3
                painter.drawLine(QPointF(x, y), QPointF(x + 6, y - 2))
            sparkle = QColor("#F3F5F8")
            sparkle.setAlpha(110 + int(90 * pulse))
            painter.setPen(QPen(sparkle, 1.2))
            sx = rect.right() - 10 - 5 * pulse
            sy = rect.top() + 10 + 4 * math.sin(self._phase * math.tau)
            painter.drawLine(QPointF(sx - 3, sy), QPointF(sx + 3, sy))
            painter.drawLine(QPointF(sx, sy - 3), QPointF(sx, sy + 3))

    def _paint_animated_app_icon(self, painter: QPainter, rect: QRect, active: bool, pulse: float) -> None:
        size = 20 + int(4 * pulse if active else 0)
        pix = app_icon(
            self._icon_name,
            size=size,
            color="#FFFFFF" if self.isChecked() else "#D7DAE7",
        ).pixmap(icon_size(size))
        painter.save()
        painter.translate(rect.center())
        if active and self._icon_name in {"scissors", "blade"}:
            painter.rotate(-8 + 16 * pulse)
        elif active and self._icon_name in {"ripple", "roll"}:
            painter.translate(0, math.sin(self._phase * math.tau) * 1.8)
        painter.drawPixmap(QRect(-size // 2, -size // 2, size, size), pix)
        painter.restore()


