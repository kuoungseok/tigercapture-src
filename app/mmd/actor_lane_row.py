"""Timeline row widget for MMD actor tracks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QMimeData, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QMenu, QWidget

from app.mmd.project_tracks import (
    MMD_MIME_TYPE,
    MMD_MIN_CLIP_MS,
    mmd_paths_from_mime,
    mmd_track_end_ms,
    mmd_track_label,
    mmd_track_start_ms,
    set_mmd_track_range,
)
from app.studio_theme import (
    STUDIO_ACTION_HI,
    STUDIO_PLAYHEAD,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
)
from app.style import studio_chrome_qss
from app.timeline_ruler import TimelineRuler


_BG = QColor("#101010")
_CLIP = QColor(64, 44, 66, 132)
_CLIP_SEL = QColor(90, 58, 96, 168)
_CLIP_BORDER = QColor(255, 111, 174, 124)
_DROP = QColor("#FF9BC8")
_TIMELINE_MARGIN = int(TimelineRuler.MARGIN)
_LABEL_W = _TIMELINE_MARGIN
_HEADER_W = _TIMELINE_MARGIN


class MMDActorLaneRow(QWidget):
    """Single timeline lane representing one MMD actor track."""

    HEADER_W = _HEADER_W
    TIMELINE_MARGIN = _TIMELINE_MARGIN

    track_changed = Signal(dict)
    track_change_committed = Signal(dict, str)
    track_selected = Signal(dict)
    track_double_clicked = Signal(dict)
    track_duplicate_requested = Signal(dict)
    track_delete_requested = Signal(dict)
    motion_browse_requested = Signal(dict)
    physics_toggle_requested = Signal(dict, bool)
    model_dropped = Signal(list, int)

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
        self._drop_x: int | None = None
        self._drop_label = ""
        self._dirty_drag = False

        self.setFixedHeight(28)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

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
        return mmd_track_start_ms(self._track)

    def _end_ms(self) -> int:
        return mmd_track_end_ms(self._track)

    def _set_range(self, start_ms: int, end_ms: int) -> None:
        set_mmd_track_range(self._track, start_ms, end_ms)

    def _preferred_width(self) -> int:
        return max(300, _TIMELINE_MARGIN + int(self._end_ms() / 1000.0 * self._px_per_sec) + 80)

    def _ms_to_x(self, ms: int) -> int:
        return _TIMELINE_MARGIN + int(max(0, ms) / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: float) -> int:
        return max(0, int((float(x) - _TIMELINE_MARGIN) / self._px_per_sec * 1000))

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
        painter.setPen(QColor("#FFD5E7") if self._selected else QColor("#9A9A9A"))
        painter.drawText(tab_rect, Qt.AlignmentFlag.AlignCenter, f"M{self._lane_index}")
        role_font = QFont("Segoe UI Variable", 10)
        painter.setFont(role_font)
        painter.setPen(QColor("#7E7E7E"))
        painter.drawText(QRect(112, 6, _LABEL_W - 126, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "MMD")

        clip_rect = self._clip_rect()
        fill = _CLIP_SEL if self._selected else _CLIP
        paint_studio_clip_block(
            painter,
            clip_rect,
            selected=self._selected,
            active=self._selected,
            fill=fill,
            highlight=STUDIO_ACTION_HI,
            edge=_CLIP_BORDER,
        )

        paint_studio_clip_label(painter, clip_rect.adjusted(-2, -8, 0, 0), mmd_track_label(self._track))

        badge_rect = QRect(max(clip_rect.left() + 5, clip_rect.right() - 42), 6, min(38, clip_rect.width() - 10), 13)
        if badge_rect.width() > 18:
            painter.setPen(QPen(QColor(255, 255, 255, 34), 1))
            painter.setBrush(QColor(255, 111, 174, 155))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, "MMD")

        if self._drop_x is not None:
            drop = QColor(_DROP)
            drop.setAlpha(150)
            painter.setPen(QPen(drop, 1.2))
            painter.drawLine(self._drop_x, 1, self._drop_x, h - 1)
            if self._drop_label:
                metrics = painter.fontMetrics()
                pad_x = 7
                label_w = min(96, metrics.horizontalAdvance(self._drop_label) + pad_x * 2)
                label_rect = QRect(
                    min(max(_LABEL_W + 4, self._drop_x + 5), max(_LABEL_W + 4, w - label_w - 6)),
                    5,
                    label_w,
                    15,
                )
                painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
                painter.setBrush(QColor(255, 111, 174, 165))
                painter.drawRoundedRect(label_rect, 4, 4)
                painter.setPen(QColor("#FFFFFF"))
                painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._drop_label)

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
            self._show_context_menu(event.globalPosition().toPoint(), int(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            delta_ms = int((int(event.position().x()) - self._drag_start_x) / self._px_per_sec * 1000)
            if self._resize_side == "left":
                self._set_range(
                    min(self._drag_orig_end - MMD_MIN_CLIP_MS, max(0, self._drag_orig_start + delta_ms)),
                    self._drag_orig_end,
                )
            elif self._resize_side == "right":
                self._set_range(
                    self._drag_orig_start,
                    max(self._drag_orig_start + MMD_MIN_CLIP_MS, self._drag_orig_end + delta_ms),
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
            self.track_change_committed.emit(self._track, "move mmd actor" if not self._resize_side else "trim mmd actor")
        self._dragging = False
        self._dirty_drag = False
        self._resize_side = ""
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._accepts(event.mimeData()):
            self._drop_x = int(event.position().x())
            self._drop_label = self._drop_label_for_mime(event.mimeData())
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if self._accepts(event.mimeData()):
            self._drop_x = int(event.position().x())
            self._drop_label = self._drop_label_for_mime(event.mimeData())
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, _event) -> None:
        self._drop_x = None
        self._drop_label = ""
        self.update()

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_x = None
        self._drop_label = ""
        paths = self._paths_from_mime(event.mimeData())
        if paths:
            self.model_dropped.emit(paths, self._x_to_ms(event.position().x()))
            event.acceptProposedAction()
        else:
            event.ignore()
        self.update()

    def _show_context_menu(self, global_pos: QPoint, click_x: int) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))
        edit_act = menu.addAction("Open MMD Actor Editor")
        motion_act = menu.addAction("Change VMD motion...")
        playback = self._track.get("playback") if isinstance(self._track.get("playback"), dict) else {}
        physics_enabled = bool(playback.get("enable_physics", True))
        physics_act = menu.addAction("Disable physics" if physics_enabled else "Enable physics")
        duplicate_act = menu.addAction("Duplicate MMD actor")
        delete_act = menu.addAction("Delete MMD actor")
        folder_act = menu.addAction("Open model folder")
        if not str(self._track.get("model_path") or ""):
            folder_act.setEnabled(False)
        action = menu.exec(global_pos)
        if action == edit_act:
            self.track_double_clicked.emit(self._track)
        elif action == motion_act:
            self.motion_browse_requested.emit(self._track)
        elif action == physics_act:
            self.physics_toggle_requested.emit(self._track, not physics_enabled)
        elif action == duplicate_act:
            self.track_duplicate_requested.emit(self._track)
        elif action == delete_act:
            self.track_delete_requested.emit(self._track)
        elif action == folder_act:
            try:
                os.startfile(str(Path(str(self._track.get("model_path") or "")).parent))
            except Exception:
                pass

    @staticmethod
    def _accepts(mime: QMimeData) -> bool:
        return bool(MMDActorLaneRow._paths_from_mime(mime))

    @staticmethod
    def _paths_from_mime(mime: QMimeData) -> list[Path]:
        return mmd_paths_from_mime(mime)

    @staticmethod
    def _drop_label_for_mime(mime: QMimeData) -> str:
        try:
            from app.mmd.project_tracks import split_mmd_paths

            models, motions = split_mmd_paths(mmd_paths_from_mime(mime))
        except Exception:
            models, motions = [], []
        if motions and not models:
            return "MOTION"
        if models and motions:
            return "ACTOR+VMD"
        if models:
            return "ACTOR"
        return "MMD"


MMD_MODEL_MIME = MMD_MIME_TYPE
