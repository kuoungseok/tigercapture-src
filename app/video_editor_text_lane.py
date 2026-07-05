"""Dedicated typography timeline lane widget."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QMouseEvent, QPainter, QPen, QBrush
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.i18n import tr
from app.timeline_drop_payloads import text_clip_duration_from_mime
from app.timeline_lane_paint import TIMELINE_BG_80, TIMELINE_STRIPE_80, draw_timeline_stripes
from app.timeline_ruler import DEFAULT_PX_PER_SEC, MAX_PX_PER_SEC, MIN_PX_PER_SEC, MIN_TRACK_WIDTH
from app.typography import TEXT_CLIP_MIME, TextClip, TextTrack


class TextLaneRow(QWidget):
    """Dedicated timeline lane for text clips."""

    MARGIN = 180
    ROW_HEIGHT = 58
    EDGE_GRIP_PX = 8
    MIN_CLIP_MS = 200

    clip_double_clicked = Signal(int)
    clip_context_menu = Signal(int, object)
    clips_changed = Signal()

    def __init__(self, track: TextTrack) -> None:
        super().__init__()
        self.track = track
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._duration_ms: int = 0
        self._hover_clip_id: int | None = None
        self._hover_edge: str | None = None
        self._active_clip_id: int | None = None
        self._drag_mode: str | None = None
        self._drag_anchor_ms: int = 0
        self._drag_orig_start_ms: int = 0
        self._drag_orig_end_ms: int = 0

        self.setFixedHeight(self.ROW_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self.setToolTip(tr("veditor.typo_lane.hint"))

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()
        self.update()

    def set_project_duration(self, ms: int) -> None:
        self._duration_ms = max(0, int(ms))
        self._recalc_width()
        self.update()

    def set_min_width(self, w: int) -> None:
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, int(w)))
        self.update()

    def _recalc_width(self) -> None:
        span_ms = max(self._duration_ms, self.track.extent_ms())
        w = int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN
        self.setMinimumWidth(max(MIN_TRACK_WIDTH, w))

    def _ms_to_x(self, ms: int) -> int:
        return int(self.MARGIN + max(0, ms) / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def _clip_rect(self, clip: TextClip) -> QRect:
        x0 = self._ms_to_x(clip.start_ms)
        x1 = self._ms_to_x(clip.end_ms)
        return QRect(x0, 6, max(2, x1 - x0), self.ROW_HEIGHT - 12)

    def _hit_clip(self, pos: QPoint) -> tuple[TextClip | None, str]:
        for clip in reversed(self.track.clips):
            rect = self._clip_rect(clip)
            if not rect.contains(pos):
                continue
            if pos.x() - rect.left() <= self.EDGE_GRIP_PX:
                return clip, "left"
            if rect.right() - pos.x() <= self.EDGE_GRIP_PX:
                return clip, "right"
            return clip, "body"
        return None, ""

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw_timeline_stripes(painter, self.rect(), TIMELINE_BG_80, TIMELINE_STRIPE_80)
        label_col = QRect(0, 0, self.MARGIN, self.height())
        painter.fillRect(label_col, QColor("#151515"))
        painter.setPen(QColor("#2B2B2B"))
        painter.drawLine(self.MARGIN - 1, 0, self.MARGIN - 1, self.height())
        font = QFont(painter.font())
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#CFCFCF"))
        label_y = max(0, (self.height() - 16) // 2)
        painter.drawText(
            QRect(12, label_y, 26, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "T1",
        )
        font.setPixelSize(9)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#858585"))
        painter.drawText(
            QRect(42, label_y, self.MARGIN - 54, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Text",
        )
        for clip in self.track.clips:
            self._paint_clip(painter, clip)

        from app import tier

        if tier.is_locked("export.typography") and len(self.track.clips) > 0:
            self._paint_pro_export_badge(painter)

    def _paint_pro_export_badge(self, painter: QPainter) -> None:
        text = tr("veditor.typo_lane.pro_export_badge")
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        pad_x, pad_y = 8, 3
        chip_w = metrics.horizontalAdvance(text) + pad_x * 2
        chip_h = metrics.height() + pad_y * 2
        chip_rect = QRect(
            self.width() - chip_w - 8,
            (self.height() - chip_h) // 2,
            chip_w,
            chip_h,
        )
        painter.setBrush(QColor(20, 20, 28, 220))
        painter.setPen(QPen(QColor("#D8A030"), 1))
        painter.drawRoundedRect(chip_rect, 6, 6)
        painter.setPen(QPen(QColor("#FFD080")))
        painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _paint_clip(self, painter: QPainter, clip: TextClip) -> None:
        rect = self._clip_rect(clip)
        if rect.width() < 2:
            return
        grad = QLinearGradient(rect.left(), 0, rect.right(), 0)
        grad.setColorAt(0.0, QColor(216, 90, 48, 180))
        grad.setColorAt(1.0, QColor(184, 63, 173, 180))
        painter.setBrush(QBrush(grad))
        border = QColor("#ff7a4a") if clip.id == self._active_clip_id else QColor("#D85A30")
        painter.setPen(QPen(border, 2))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        painter.setPen(QPen(QColor("#FFFFFF")))
        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(
            rect.adjusted(6, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            "T",
        )

        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        preview = clip.display_text()
        if len(preview) > 22:
            preview = preview[:22] + "..."
        painter.drawText(
            rect.adjusted(20, 4, -6, -18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            preview,
        )

        bar_margin = 5
        bar_rect = QRect(
            rect.left() + bar_margin,
            rect.bottom() - 8,
            max(1, rect.width() - 2 * bar_margin),
            4,
        )
        total_s = max(0.001, clip.duration_s)
        in_ratio = max(0.0, min(1.0, clip.animation.in_duration / total_s))
        out_ratio = max(0.0, min(1.0, clip.animation.out_duration / total_s))
        if in_ratio + out_ratio > 1.0:
            scale = 1.0 / (in_ratio + out_ratio)
            in_ratio *= scale
            out_ratio *= scale

        in_w = int(bar_rect.width() * in_ratio)
        out_w = int(bar_rect.width() * out_ratio)
        hold_w = max(0, bar_rect.width() - in_w - out_w)
        if in_w > 0:
            painter.fillRect(QRect(bar_rect.left(), bar_rect.top(), in_w, bar_rect.height()), QColor("#ff7a4a"))
        if hold_w > 0:
            painter.fillRect(
                QRect(bar_rect.left() + in_w, bar_rect.top(), hold_w, bar_rect.height()),
                QColor(255, 255, 255, 70),
            )
        if out_w > 0:
            painter.fillRect(
                QRect(bar_rect.right() - out_w, bar_rect.top(), out_w, bar_rect.height()),
                QColor("#b04722"),
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        clip, zone = self._hit_clip(pos)
        if clip is None:
            return
        self._active_clip_id = clip.id
        self._drag_anchor_ms = self._x_to_ms(pos.x())
        self._drag_orig_start_ms = int(clip.start_ms)
        self._drag_orig_end_ms = int(clip.end_ms)
        if zone == "left":
            self._drag_mode = "resize_l"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "right":
            self._drag_mode = "resize_r"
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self._drag_mode = "move"
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._drag_mode and self._active_clip_id is not None:
            clip = self.track.find(self._active_clip_id)
            if clip is None:
                self._drag_mode = None
                return
            delta_ms = self._x_to_ms(pos.x()) - self._drag_anchor_ms
            if self._drag_mode == "move":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                duration = self._drag_orig_end_ms - self._drag_orig_start_ms
                clip.start_ms = new_start
                clip.end_ms = new_start + duration
            elif self._drag_mode == "resize_l":
                new_start = max(0, self._drag_orig_start_ms + delta_ms)
                clip.start_ms = min(new_start, clip.end_ms - self.MIN_CLIP_MS)
            elif self._drag_mode == "resize_r":
                clip.end_ms = max(
                    clip.start_ms + self.MIN_CLIP_MS,
                    self._drag_orig_end_ms + delta_ms,
                )
            self._recalc_width()
            self.clips_changed.emit()
            self.update()
            return

        _, zone = self._hit_clip(pos)
        if zone in ("left", "right"):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif zone == "body":
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._drag_mode is not None:
            self.track.clips.sort(key=lambda c: c.start_ms)
            self.clips_changed.emit()
        self._drag_mode = None
        self._active_clip_id = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        clip, _zone = self._hit_clip(event.position().toPoint())
        if clip is not None:
            self.clip_double_clicked.emit(clip.id)

    def contextMenuEvent(self, event) -> None:
        clip, _zone = self._hit_clip(event.pos())
        if clip is None:
            event.ignore()
            return
        self.clip_context_menu.emit(clip.id, event.globalPos())
        event.accept()

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(TEXT_CLIP_MIME):
            event.acceptProposedAction()
            return
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(TEXT_CLIP_MIME):
            super().dropEvent(event)
            return
        duration_ms = text_clip_duration_from_mime(mime, default_ms=2000)
        drop_ms = self._x_to_ms(event.position().toPoint().x())
        clip = TextClip(
            start_ms=max(0, drop_ms),
            end_ms=max(0, drop_ms) + max(self.MIN_CLIP_MS, duration_ms),
        )
        self.track.add_clip(clip)
        self._recalc_width()
        self.clips_changed.emit()
        self.update()
        event.acceptProposedAction()
        self.clip_double_clicked.emit(clip.id)
