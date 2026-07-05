"""Timeline row widget for AR/PBR 3D object tracks."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QMenu, QWidget

from app.studio_theme import (
    STUDIO_ACTION_HI,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
)
from app.style import studio_chrome_qss
from app.timeline_ruler import TimelineRuler


AR_PBR_MIN_CLIP_MS = 250
_BG = QColor("#101010")
_CLIP = QColor(40, 62, 96, 132)
_CLIP_SEL = QColor(55, 86, 136, 172)
_CLIP_BORDER = QColor(102, 158, 255, 138)
_LABEL_W = int(TimelineRuler.MARGIN)
_TIMELINE_MARGIN = int(TimelineRuler.MARGIN)


def ar_pbr_track_start_ms(track: dict[str, Any]) -> int:
    try:
        return max(0, int(track.get("start_ms", 0) or 0))
    except Exception:
        return 0


def ar_pbr_track_end_ms(track: dict[str, Any]) -> int:
    start = ar_pbr_track_start_ms(track)
    try:
        end = int(track.get("end_ms", start) or start)
    except Exception:
        end = start
    return max(start + AR_PBR_MIN_CLIP_MS, end)


def set_ar_pbr_track_range(track: dict[str, Any], start_ms: int, end_ms: int) -> None:
    start = max(0, int(start_ms or 0))
    end = max(start + AR_PBR_MIN_CLIP_MS, int(end_ms or 0))
    track["start_ms"] = start
    track["end_ms"] = end
    track["duration_ms"] = end - start


def ar_pbr_track_label(track: dict[str, Any]) -> str:
    asset = str(track.get("asset_path") or "")
    name = Path(asset).stem if asset else ""
    return name or str(track.get("id") or "3D Object")


class ArPbrActorLaneRow(QWidget):
    """Single timeline lane representing one AR/PBR object track."""

    HEADER_W = _LABEL_W
    TIMELINE_MARGIN = _TIMELINE_MARGIN

    track_changed = Signal(dict)
    track_change_committed = Signal(dict, str)
    track_selected = Signal(dict)
    track_double_clicked = Signal(dict)
    track_delete_requested = Signal(dict)

    def __init__(self, track: dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self._track = track
        self._px_per_sec: float = 100.0
        self._playhead_ms: int = 0
        self._selected = False
        self._dragging = False
        self._drag_start_x = 0
        self._drag_orig_start = 0
        self._drag_orig_end = 0
        self._resize_side = ""
        self._lane_index = 1
        self._dirty_drag = False

        self.setFixedHeight(28)
        self.setMouseTracking(True)

    @property
    def track(self) -> dict[str, Any]:
        return self._track

    def set_track(self, track: dict[str, Any]) -> None:
        self._track = track
        self.update()

    def set_selected(self, selected: bool) -> None:
        next_selected = bool(selected)
        if self._selected == next_selected:
            return
        self._selected = next_selected
        self.update()

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(1.0, float(px or 1.0))
        self.update()

    def set_playhead(self, ms: int) -> None:
        self._playhead_ms = max(0, int(ms or 0))
        self.update()

    def set_lane_index(self, index: int) -> None:
        lane = max(1, int(index or 1))
        if lane == self._lane_index:
            return
        self._lane_index = lane
        self.update()

    def _start_ms(self) -> int:
        return ar_pbr_track_start_ms(self._track)

    def _end_ms(self) -> int:
        return ar_pbr_track_end_ms(self._track)

    def _set_range(self, start_ms: int, end_ms: int) -> None:
        set_ar_pbr_track_range(self._track, start_ms, end_ms)

    def _preferred_width(self) -> int:
        return max(300, _TIMELINE_MARGIN + int(self._end_ms() / 1000.0 * self._px_per_sec) + 80)

    def _ms_to_x(self, ms: int) -> int:
        return _TIMELINE_MARGIN + int(max(0, ms) / 1000.0 * self._px_per_sec)

    def _clip_rect(self) -> QRect:
        x1 = self._ms_to_x(self._start_ms())
        x2 = max(x1 + 8, self._ms_to_x(self._end_ms()))
        return QRect(x1, 3, x2 - x1, self.height() - 6)

    def _hit(self, x: float) -> str:
        rect = self._clip_rect()
        if not rect.contains(QPoint(int(x), rect.center().y())):
            return ""
        if int(x) - rect.left() <= 7:
            return "left"
        if rect.right() - int(x) <= 7:
            return "right"
        return "body"

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        painter.fillRect(0, 0, w, h, _BG)
        lane_rect = QRect(0, 0, _LABEL_W, h)
        lane_grad = QLinearGradient(lane_rect.topLeft(), lane_rect.bottomLeft())
        lane_grad.setColorAt(0.0, QColor("#171819"))
        lane_grad.setColorAt(1.0, QColor("#101111"))
        painter.fillRect(lane_rect, lane_grad)
        painter.setPen(QColor("#242424"))
        painter.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)
        painter.setPen(QColor(255, 255, 255, 14))
        painter.drawLine(0, 0, _LABEL_W - 1, 0)

        tab_rect = QRect(14, 5, 86, max(18, h - 10))
        tab_grad = QLinearGradient(tab_rect.topLeft(), tab_rect.bottomLeft())
        tab_grad.setColorAt(0.0, QColor(255, 255, 255, 7))
        tab_grad.setColorAt(1.0, QColor(0, 0, 0, 10))
        painter.setPen(QPen(QColor(255, 255, 255, 15), 1))
        painter.setBrush(QBrush(tab_grad))
        painter.drawRoundedRect(tab_rect, 3, 3)

        label_font = QFont("Segoe UI Variable", 12)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        painter.setPen(QColor("#D6E7FF") if self._selected else QColor("#9A9A9A"))
        painter.drawText(tab_rect, Qt.AlignmentFlag.AlignCenter, f"3D{self._lane_index}")
        painter.setFont(QFont("Segoe UI Variable", 10))
        painter.setPen(QColor("#7E7E7E"))
        painter.drawText(QRect(112, 6, _LABEL_W - 126, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "AR/PBR")

        clip_rect = self._clip_rect()
        paint_studio_clip_block(
            painter,
            clip_rect,
            selected=self._selected,
            active=self._selected,
            fill=_CLIP_SEL if self._selected else _CLIP,
            highlight=STUDIO_ACTION_HI,
            edge=_CLIP_BORDER,
        )
        paint_studio_clip_label(painter, clip_rect.adjusted(-2, -8, 0, 0), ar_pbr_track_label(self._track))

        badge_rect = QRect(max(clip_rect.left() + 5, clip_rect.right() - 34), 6, min(30, clip_rect.width() - 10), 13)
        if badge_rect.width() > 18:
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.setBrush(QColor(102, 158, 255, 160))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "3D")

        paint_studio_playhead(painter, self._ms_to_x(self._playhead_ms), 0, h, show_handle=False)
        painter.end()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._hit(event.position().x()):
            self.track_double_clicked.emit(self._track)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            zone = self._hit(event.position().x())
            self._selected = bool(zone)
            if zone:
                self.track_selected.emit(self._track)
                self._dragging = True
                self._dirty_drag = False
                self._resize_side = zone if zone in {"left", "right"} else ""
                self._drag_start_x = int(event.position().x())
                self._drag_orig_start = self._start_ms()
                self._drag_orig_end = self._end_ms()
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            delta_ms = int((int(event.position().x()) - self._drag_start_x) / self._px_per_sec * 1000)
            if self._resize_side == "left":
                self._set_range(
                    min(self._drag_orig_end - AR_PBR_MIN_CLIP_MS, max(0, self._drag_orig_start + delta_ms)),
                    self._drag_orig_end,
                )
            elif self._resize_side == "right":
                self._set_range(
                    self._drag_orig_start,
                    max(self._drag_orig_start + AR_PBR_MIN_CLIP_MS, self._drag_orig_end + delta_ms),
                )
            else:
                duration = self._drag_orig_end - self._drag_orig_start
                start = max(0, self._drag_orig_start + delta_ms)
                self._set_range(start, start + duration)
            self._dirty_drag = True
            self.track_changed.emit(self._track)
            self.update()
            return
        zone = self._hit(event.position().x())
        if zone in {"left", "right"}:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, _event) -> None:
        if self._dragging and self._dirty_drag:
            self.track_change_committed.emit(
                self._track,
                "move 3d object" if not self._resize_side else "trim 3d object",
            )
        self._dragging = False
        self._dirty_drag = False
        self._resize_side = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))
        edit_act = menu.addAction("Open AR/PBR Viewer")
        delete_act = menu.addAction("Delete 3D object")
        folder_act = menu.addAction("Open asset folder")
        if not str(self._track.get("asset_path") or ""):
            folder_act.setEnabled(False)
        action = menu.exec(global_pos)
        if action == edit_act:
            self.track_double_clicked.emit(self._track)
        elif action == delete_act:
            self.track_delete_requested.emit(self._track)
        elif action == folder_act:
            try:
                import os

                os.startfile(str(Path(str(self._track.get("asset_path") or "")).parent))
            except Exception:
                pass
