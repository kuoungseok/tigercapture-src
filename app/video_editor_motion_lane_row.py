"""Compact main-timeline lane for one Motion Clip."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QMenu, QWidget

from app.motion_designer.clip import MotionClip
from app.timeline_ruler import TimelineRuler


class MotionLaneRow(QWidget):
    clip_changed = Signal(dict)
    clip_change_committed = Signal(dict, str)
    clip_selected = Signal(dict)
    clip_double_clicked = Signal(dict)
    duplicate_requested = Signal(dict)
    delete_requested = Signal(dict)

    def __init__(self, clip: dict, parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self._px_per_sec = 52.0
        self._playhead_ms = 0
        self._selected = False
        self._drag_mode = ""
        self._drag_start_x = 0.0
        self._original = MotionClip.from_dict(clip)
        self.setFixedHeight(28)
        self.setMouseTracking(True)

    def set_px_per_sec(self, value: float) -> None:
        self._px_per_sec = max(1.0, float(value))
        self.update()

    def set_playhead(self, value: int) -> None:
        self._playhead_ms = int(value)
        self.update()

    def set_selected(self, value: bool) -> None:
        self._selected = bool(value)
        self.update()

    def _x(self, ms: int) -> int:
        return int(TimelineRuler.MARGIN + ms / 1000.0 * self._px_per_sec)

    def _rect(self) -> QRect:
        clip = MotionClip.from_dict(self.clip)
        x1, x2 = self._x(clip.start_ms), self._x(clip.end_ms)
        return QRect(x1, 3, max(10, x2 - x1), self.height() - 6)

    def _preferred_width(self) -> int:
        return max(300, self._x(MotionClip.from_dict(self.clip).end_ms) + 80)

    def _hit(self, x: float) -> str:
        rect = self._rect()
        if not rect.contains(QPoint(int(x), rect.center().y())):
            return ""
        if int(x) - rect.left() < 7:
            return "left"
        if rect.right() - int(x) < 7:
            return "right"
        return "body"

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#101216"))
        painter.fillRect(QRect(0, 0, int(TimelineRuler.MARGIN), self.height()), QColor("#171a20"))
        painter.setPen(QColor("#aeb6c1"))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        painter.drawText(
            QRect(12, 0, int(TimelineRuler.MARGIN) - 18, self.height()),
            Qt.AlignVCenter,
            "MOTION ACTOR",
        )
        rect = self._rect()
        painter.setPen(QPen(QColor("#7ce0bd") if self._selected else QColor("#397a68"), 1))
        painter.setBrush(QColor(38, 100, 85, 205 if self._selected else 150))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QColor("#edf7f3"))
        painter.drawText(rect.adjusted(8, 0, -48, 0), Qt.AlignVCenter, str(self.clip.get("name") or "Motion Clip"))
        badge = QRect(max(rect.left() + 4, rect.right() - 42), rect.top() + 4, 36, 14)
        painter.setBrush(QColor("#13241f"))
        painter.drawRoundedRect(badge, 3, 3)
        painter.drawText(badge, Qt.AlignCenter, "ACT")
        painter.setPen(QPen(QColor("#f4b860"), 1))
        x = self._x(self._playhead_ms)
        painter.drawLine(x, 0, x, self.height())
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return
        self._drag_mode = self._hit(event.position().x())
        self._selected = bool(self._drag_mode)
        if self._selected:
            self._drag_start_x = event.position().x()
            self._original = MotionClip.from_dict(self.clip)
            self.clip_selected.emit(self.clip)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._drag_mode:
            return
        delta_ms = int((event.position().x() - self._drag_start_x) / self._px_per_sec * 1000)
        clip = MotionClip.from_dict(self._original.to_dict())
        if self._drag_mode == "body":
            clip.start_ms = max(0, self._original.start_ms + delta_ms)
        elif self._drag_mode == "left":
            new_start = max(0, min(self._original.end_ms - 100, self._original.start_ms + delta_ms))
            consumed = new_start - self._original.start_ms
            clip.start_ms = new_start
            clip.duration_ms = self._original.duration_ms - consumed
            clip.source_in_ms = max(0, self._original.source_in_ms + int(consumed * clip.time_scale))
        else:
            clip.duration_ms = max(100, self._original.duration_ms + delta_ms)
        self.clip.clear()
        self.clip.update(clip.to_dict())
        self.clip_changed.emit(self.clip)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode and event.button() == Qt.LeftButton:
            self.clip_change_committed.emit(self.clip, "Edit Motion Clip")
        self._drag_mode = ""

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._hit(event.position().x()):
            self.clip_double_clicked.emit(self.clip)

    def contextMenuEvent(self, event) -> None:
        if not self._hit(event.pos().x()):
            return
        menu = QMenu(self)
        duplicate = menu.addAction("Duplicate")
        delete = menu.addAction("Delete")
        chosen = menu.exec(event.globalPos())
        if chosen is duplicate:
            self.duplicate_requested.emit(self.clip)
        elif chosen is delete:
            self.delete_requested.emit(self.clip)
