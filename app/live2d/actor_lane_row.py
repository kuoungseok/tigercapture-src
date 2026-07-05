"""Live2DActor LaneRow — timeline row widget for Live2D actor clips."""
from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QPoint, QRect, QMimeData, QUrl
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
    QPolygon,
)
from PySide6.QtWidgets import QWidget, QMenu, QFileDialog, QMessageBox

from app.style import studio_chrome_qss
from app.actor_loading_status import actor_clip_badge, actor_clip_status
from app.live2d.actor_track import Live2DActorTrack, Live2DActorClip, Live2DBlend
from app.timeline_ruler import TimelineRuler
from app.studio_theme import (
    STUDIO_ACTION_HI,
    STUDIO_PLAYHEAD,
    paint_studio_clip_block,
    paint_studio_clip_label,
    paint_studio_playhead,
)


_BG           = QColor("#101010")
_CLIP         = QColor(55, 61, 66, 128)
_CLIP_SEL     = QColor(75, 80, 86, 154)
_CLIP_BORDER  = QColor(150, 157, 166, 112)
_TEXT         = QColor("#E8EAEE")
_PLAYHEAD     = STUDIO_PLAYHEAD
_TIMELINE_MARGIN = int(TimelineRuler.MARGIN)   # keep actor rows aligned with TimelineRuler/TrackRow
_LABEL_W      = _TIMELINE_MARGIN
_HEADER_W     = _TIMELINE_MARGIN  # backwards-compatible name for timing origin
_DROP         = QColor("#B8C0CA")
_KEY_COLORS = (
    QColor("#9AA6B6"),
    QColor("#889989"),
    QColor("#A8977E"),
    QColor("#A196AD"),
)


def _key_time_ms(keyframe) -> int | None:
    try:
        return max(0, int(round(float(getattr(keyframe, "time_ms", 0) or 0))))
    except Exception:
        if isinstance(keyframe, dict):
            try:
                return max(0, int(round(float(keyframe.get("time_ms", keyframe.get("ms", 0)) or 0))))
            except Exception:
                return None
    return None


class Live2DActorLaneRow(QWidget):
    """Single timeline lane for Live2D actor clips."""

    HEADER_W = _HEADER_W
    TIMELINE_MARGIN = _TIMELINE_MARGIN

    clip_changed        = Signal()
    clip_double_clicked = Signal(object)   # Live2DActorClip
    video_mocap_requested = Signal(object)  # Live2DActorClip
    motion_storyboard_requested = Signal(object)  # Live2DActorClip
    performance_source_mapping_requested = Signal(object)  # Live2DActorClip

    def __init__(self, track: Live2DActorTrack, parent=None):
        super().__init__(parent)
        self._track    = track
        self._px_per_sec: float = 100.0
        self._playhead_ms: int  = 0
        self._selected: Optional[Live2DActorClip] = None
        self._drag_clip: Optional[Live2DActorClip] = None
        self._drag_start_x: int = 0
        self._drag_orig_start: int = 0
        self._lane_index: int = 1
        self._drop_x: Optional[int] = None
        self._drag_blend: Optional[Live2DBlend] = None
        self._drag_blend_orig_center: int = 0

        self.setFixedHeight(28)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

    @property
    def track(self) -> Live2DActorTrack:
        return self._track

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(1.0, px)
        self.update()

    def set_playhead(self, ms: int) -> None:
        self._playhead_ms = ms
        self.update()

    def set_lane_index(self, index: int) -> None:
        lane = max(1, int(index))
        if lane == self._lane_index:
            return
        self._lane_index = lane
        self.update()

    def _preferred_width(self) -> int:
        span_ms = max((c.end_ms for c in self._track.clips), default=0)
        return max(300, _TIMELINE_MARGIN + int(span_ms / 1000.0 * self._px_per_sec) + 80)

    # ── coords ────────────────────────────────────────────────────────────

    def _ms_to_x(self, ms: int) -> int:
        return _TIMELINE_MARGIN + int(ms / 1000.0 * self._px_per_sec)

    def _x_to_ms(self, x: float) -> int:
        return max(0, int((x - _TIMELINE_MARGIN) / self._px_per_sec * 1000))

    # ── paint ─────────────────────────────────────────────────────────────

    def _paintEvent_legacy(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, _BG)
        p.fillRect(0, 0, _LABEL_W, h, QColor("#151515"))
        p.setPen(QColor("#2B2B2B"))
        p.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)

        # Track label (overlaid at left, matching TrackRow style)
        p.setPen(_TEXT)
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(4, h - 8, self._track.label)

        # Clips
        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = self._ms_to_x(clip.end_ms)
            cw = max(4, x2 - x1)
            fill = _CLIP_SEL if clip is self._selected else _CLIP
            p.fillRect(x1, 2, cw, h - 4, fill)

            # Blend-in ramp (left edge triangle)
            if clip.blend_in_ms > 0:
                from PySide6.QtGui import QLinearGradient, QPolygon
                from PySide6.QtCore import QPoint as _QP
                bw = min(cw, self._ms_to_x(clip.start_ms + clip.blend_in_ms) - x1)
                grad = QLinearGradient(x1, 0, x1 + bw, 0)
                grad.setColorAt(0.0, QColor(0, 0, 0, 160))
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.fillRect(x1, 2, bw, h - 4, grad)

            # Blend-out ramp (right edge)
            if clip.blend_out_ms > 0:
                from PySide6.QtGui import QLinearGradient
                bw = min(cw, self._ms_to_x(clip.end_ms) - self._ms_to_x(clip.end_ms - clip.blend_out_ms))
                grad = QLinearGradient(x2 - bw, 0, x2, 0)
                grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(0, 0, 0, 160))
                p.fillRect(x2 - bw, 2, bw, h - 4, grad)

            p.setPen(QPen(_CLIP_BORDER, 1))
            p.drawRect(x1, 2, cw, h - 4)
            badge = actor_clip_badge(clip)
            if badge and cw > 30:
                text, color = badge
                bw = 28 if len(text) <= 3 else 36
                br = QRect(max(x1 + 4, x2 - bw - 4), 5, min(bw, cw - 8), 14)
                p.fillRect(br, QColor(color))
                p.setPen(QColor("#FFFFFF"))
                p.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, text)
                msg = actor_clip_status(clip).get("message", "")
                if msg:
                    self.setToolTip(msg)

            if clip.model_path:
                name = os.path.basename(clip.model_path).replace(".model3.json", "")
                lbl  = f"{name} / {clip.motion_group}" if clip.motion_group else name
            else:
                lbl = "Live2D (더블클릭으로 설정)"
            p.setPen(_TEXT)
            p.setFont(QFont("Segoe UI", 8))
            p.setClipRect(x1 + 3, 0, cw - 6, h)
            p.drawText(x1 + 3, h - 8, lbl)
            p.setClipping(False)

        # Blend markers
        for blend in self._track.blends:
            bx = self._ms_to_x(blend.center_ms)
            bw = max(4, self._ms_to_x(blend.center_ms + blend.duration_ms // 2) - bx)
            # Fade zone overlay on both sides
            from PySide6.QtGui import QLinearGradient
            g1 = QLinearGradient(bx - bw, 0, bx, 0)
            g1.setColorAt(0.0, QColor(200, 160, 60, 0))
            g1.setColorAt(1.0, QColor(200, 160, 60, 80))
            p.fillRect(bx - bw, 2, bw, h - 4, g1)
            g2 = QLinearGradient(bx, 0, bx + bw, 0)
            g2.setColorAt(0.0, QColor(200, 160, 60, 80))
            g2.setColorAt(1.0, QColor(200, 160, 60, 0))
            p.fillRect(bx, 2, bw, h - 4, g2)
            # Diamond marker at center
            from PySide6.QtGui import QPolygon
            from PySide6.QtCore import QPoint as _QP
            cy = h // 2
            sz = 5
            diamond = QPolygon([
                _QP(bx, cy - sz), _QP(bx + sz, cy),
                _QP(bx, cy + sz), _QP(bx - sz, cy),
            ])
            p.setBrush(QColor("#c8a03c"))
            p.setPen(QPen(QColor("#ffe080"), 1))
            p.drawPolygon(diamond)
            p.setBrush(Qt.BrushStyle.NoBrush)

        # Drop indicator (vertical line when dragging over)
        if self._drop_x is not None:
            p.setPen(QPen(_DROP, 2))
            p.drawLine(self._drop_x, 1, self._drop_x, h - 1)

        # Playhead
        px = self._ms_to_x(self._playhead_ms)
        p.setPen(QPen(_PLAYHEAD, 1))
        p.drawLine(px, 0, px, h)
        p.end()

    # ── mouse ─────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, _BG)
        lane_rect = QRect(0, 0, _LABEL_W, h)
        lane_grad = QLinearGradient(lane_rect.topLeft(), lane_rect.bottomLeft())
        lane_grad.setColorAt(0.0, QColor("#171819"))
        lane_grad.setColorAt(1.0, QColor("#101111"))
        p.fillRect(lane_rect, lane_grad)
        p.setPen(QColor("#242424"))
        p.drawLine(_LABEL_W - 1, 0, _LABEL_W - 1, h)
        p.setPen(QColor(255, 255, 255, 14))
        p.drawLine(0, 0, _LABEL_W - 1, 0)
        tab_rect = QRect(14, 5, 86, max(18, h - 10))
        tab_grad = QLinearGradient(tab_rect.topLeft(), tab_rect.bottomLeft())
        tab_grad.setColorAt(0.0, QColor(255, 255, 255, 7))
        tab_grad.setColorAt(1.0, QColor(0, 0, 0, 10))
        p.setPen(QPen(QColor(255, 255, 255, 15), 1))
        p.setBrush(QBrush(tab_grad))
        p.drawRoundedRect(tab_rect, 3, 3)
        p.setPen(QPen(QColor(0, 0, 0, 38), 1))
        p.drawLine(tab_rect.right(), tab_rect.top() + 5, tab_rect.right(), tab_rect.bottom() - 5)
        label_font = QFont("Segoe UI Variable", 12)
        label_font.setWeight(QFont.Weight.Medium)
        p.setFont(label_font)
        p.setPen(QColor("#D8DADD") if self._selected is not None else QColor("#9A9A9A"))
        lane_index = max(1, int(getattr(self, "_lane_index", 1) or 1))
        p.drawText(tab_rect, Qt.AlignmentFlag.AlignCenter, f"L{lane_index}")
        role_font = QFont("Segoe UI Variable", 10)
        role_font.setWeight(QFont.Weight.Normal)
        p.setFont(role_font)
        p.setPen(QColor("#7E7E7E"))
        p.drawText(
            QRect(112, 6, _LABEL_W - 126, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Live2D",
        )

        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = self._ms_to_x(clip.end_ms)
            cw = max(4, x2 - x1)
            clip_rect = QRect(x1, 3, cw, h - 6)
            fill = _CLIP_SEL if clip is self._selected else _CLIP
            paint_studio_clip_block(
                p,
                clip_rect,
                selected=clip is self._selected,
                active=clip is self._selected,
                fill=fill,
                highlight=STUDIO_ACTION_HI,
                edge=_CLIP_BORDER,
            )

            if clip.blend_in_ms > 0:
                bw = min(cw, self._ms_to_x(clip.start_ms + clip.blend_in_ms) - x1)
                grad = QLinearGradient(x1, 0, x1 + bw, 0)
                grad.setColorAt(0.0, QColor(0, 0, 0, 112))
                grad.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.fillRect(QRect(x1 + 1, 4, max(1, bw), h - 8), grad)

            if clip.blend_out_ms > 0:
                bw = min(cw, self._ms_to_x(clip.end_ms) - self._ms_to_x(clip.end_ms - clip.blend_out_ms))
                grad = QLinearGradient(x2 - bw, 0, x2, 0)
                grad.setColorAt(0.0, QColor(0, 0, 0, 0))
                grad.setColorAt(1.0, QColor(0, 0, 0, 112))
                p.fillRect(QRect(x2 - bw, 4, max(1, bw), h - 8), grad)

            badge = actor_clip_badge(clip)
            if badge and cw > 30:
                text, color = badge
                bw = 28 if len(text) <= 3 else 36
                br = QRect(max(x1 + 5, x2 - bw - 5), 6, min(bw, cw - 10), 13)
                badge_color = QColor(color)
                badge_color.setAlpha(178)
                p.setPen(QPen(QColor(255, 255, 255, 34), 1))
                p.setBrush(badge_color)
                p.drawRoundedRect(br, 3, 3)
                p.setPen(QColor("#FFFFFF"))
                p.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
                p.drawText(br, Qt.AlignmentFlag.AlignCenter, text)
                msg = actor_clip_status(clip).get("message", "")
                if msg:
                    self.setToolTip(msg)

            if clip.model_path:
                name = os.path.basename(clip.model_path).replace(".model3.json", "")
                lbl = f"{name} / {clip.motion_group}" if clip.motion_group else name
            else:
                lbl = "Live2D (double-click to set)"
            paint_studio_clip_label(p, clip_rect.adjusted(-2, -8, 0, 0), lbl)

            key_series = (
                getattr(clip, "kf_pos_x", []),
                getattr(clip, "kf_pos_y", []),
                getattr(clip, "kf_scale", []),
                getattr(clip, "kf_opacity", []),
            )
            key_y = max(7, min(h - 7, clip_rect.center().y() + 5))
            for series_index, series in enumerate(key_series):
                color = QColor(_KEY_COLORS[series_index])
                color.setAlpha(190 if clip is self._selected else 132)
                p.setPen(QPen(QColor(8, 8, 8, 150), 0.8))
                p.setBrush(color)
                for keyframe in list(series or []):
                    key_ms = _key_time_ms(keyframe)
                    if key_ms is None:
                        continue
                    kx = self._ms_to_x(int(clip.start_ms) + key_ms)
                    if kx < clip_rect.left() + 3 or kx > clip_rect.right() - 3:
                        continue
                    y = key_y - 4 + min(3, series_index)
                    p.drawPolygon(QPolygon([
                        QPoint(kx, y - 3),
                        QPoint(kx + 3, y),
                        QPoint(kx, y + 3),
                        QPoint(kx - 3, y),
                    ]))

        for blend in self._track.blends:
            bx = self._ms_to_x(blend.center_ms)
            bw = max(4, self._ms_to_x(blend.center_ms + blend.duration_ms // 2) - bx)
            g1 = QLinearGradient(bx - bw, 0, bx, 0)
            g1.setColorAt(0.0, QColor(200, 160, 60, 0))
            g1.setColorAt(1.0, QColor(216, 200, 158, 42))
            p.fillRect(bx - bw, 3, bw, h - 6, g1)
            g2 = QLinearGradient(bx, 0, bx + bw, 0)
            g2.setColorAt(0.0, QColor(216, 200, 158, 42))
            g2.setColorAt(1.0, QColor(200, 160, 60, 0))
            p.fillRect(bx, 3, bw, h - 6, g2)
            cy = h // 2
            sz = 4
            diamond = QPolygon([
                QPoint(bx, cy - sz), QPoint(bx + sz, cy),
                QPoint(bx, cy + sz), QPoint(bx - sz, cy),
            ])
            p.setBrush(QColor(216, 200, 158, 146))
            p.setPen(QPen(QColor(245, 233, 200, 128), 1))
            p.drawPolygon(diamond)
            p.setBrush(Qt.BrushStyle.NoBrush)

        if self._drop_x is not None:
            drop = QColor(_DROP)
            drop.setAlpha(150)
            p.setPen(QPen(drop, 1.2))
            p.drawLine(self._drop_x, 1, self._drop_x, h - 1)

        px = self._ms_to_x(self._playhead_ms)
        paint_studio_playhead(p, px, 0, h, show_handle=False)
        p.end()

    def mouseDoubleClickEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            clip = self._clip_at(e.position().x())
            if clip:
                self.clip_double_clicked.emit(clip)

    def mousePressEvent(self, e: QMouseEvent):
        x = e.position().x()
        if e.button() == Qt.MouseButton.LeftButton:
            # Check if clicking on a blend marker first
            blend = self._blend_at(x)
            if blend:
                self._drag_blend = blend
                self._drag_start_x = int(x)
                self._drag_blend_orig_center = blend.center_ms
                self.update()
                return
            clip = self._clip_at(x)
            self._selected = clip
            if clip:
                self._drag_clip      = clip
                self._drag_start_x   = int(x)
                self._drag_orig_start = clip.start_ms
            else:
                # Empty space between clips → create blend
                self._try_create_blend(self._x_to_ms(x))
            self.update()
        elif e.button() == Qt.MouseButton.RightButton:
            blend = self._blend_at(x)
            if blend:
                self._show_blend_menu(e.globalPosition().toPoint(), blend)
            else:
                self._show_menu(
                    e.globalPosition().toPoint(),
                    self._clip_at(x),
                    x,
                )

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_blend and e.buttons() & Qt.MouseButton.LeftButton:
            dx = int(e.position().x()) - self._drag_start_x
            delta_ms = int(dx / self._px_per_sec * 1000)
            self._drag_blend.center_ms = max(0, self._drag_blend_orig_center + delta_ms)
            self.update()
            self.clip_changed.emit()
        elif self._drag_clip and e.buttons() & Qt.MouseButton.LeftButton:
            dx = int(e.position().x()) - self._drag_start_x
            delta_ms = int(dx / self._px_per_sec * 1000)
            self._drag_clip.start_ms = max(0, self._drag_orig_start + delta_ms)
            self.update()
            self.clip_changed.emit()

    def mouseReleaseEvent(self, _):
        self._drag_clip = None
        self._drag_blend = None

    # ── drag & drop ───────────────────────────────────────────────────────

    def dragEnterEvent(self, e: QDragEnterEvent):
        if self._accepts(e.mimeData()):
            e.acceptProposedAction()
            self._drop_x = int(e.position().x())
            self.update()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if self._accepts(e.mimeData()):
            e.acceptProposedAction()
            self._drop_x = int(e.position().x())
            self.update()

    def dragLeaveEvent(self, e):
        self._drop_x = None
        self.update()

    def dropEvent(self, e: QDropEvent):
        self._drop_x = None
        start_ms = self._x_to_ms(e.position().x())
        if e.mimeData().hasFormat("application/x-live2d-actor-new"):
            # Empty actor — model will be assigned later via editor
            self._create_clip("", start_ms)
            e.acceptProposedAction()
        else:
            path = self._model_path_from_mime(e.mimeData())
            if path:
                self._create_clip(path, start_ms)
                e.acceptProposedAction()
        self.update()

    @staticmethod
    def _accepts(mime: QMimeData) -> bool:
        if mime.hasFormat("application/x-live2d-model"):
            return True
        if mime.hasFormat("application/x-live2d-actor-new"):
            return True
        if mime.hasUrls():
            try:
                from app.live2d.compat import is_live2d_candidate
                return any(is_live2d_candidate(u.toLocalFile()) for u in mime.urls())
            except Exception:
                return any(u.toLocalFile().endswith(".model3.json")
                           for u in mime.urls())
        return False

    @staticmethod
    def _model_path_from_mime(mime: QMimeData) -> str:
        if mime.hasFormat("application/x-live2d-model"):
            return bytes(mime.data("application/x-live2d-model")).decode("utf-8")
        if mime.hasUrls():
            for u in mime.urls():
                p = u.toLocalFile()
                try:
                    from app.live2d.compat import is_live2d_candidate
                    if is_live2d_candidate(p):
                        return p
                except Exception:
                    if p.endswith(".model3.json"):
                        return p
        return ""

    def _create_clip(self, path: str, start_ms: int) -> None:
        if path:
            try:
                from app.live2d.compat import model_support_error
                error = model_support_error(path)
                if error:
                    QMessageBox.warning(self, "Live2D", error)
                    return
            except Exception:
                pass
        motion_group = ""
        try:
            from app.live2d.compat import normalize_live2d_model_path
            meta_path = normalize_live2d_model_path(path) or path
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
            motions = data.get("FileReferences", {}).get("Motions", {})
            if motions:
                motion_group = list(motions.keys())[0]
                for g in motions:
                    if "idle" in g.lower():
                        motion_group = g
                        break
        except Exception:
            pass
        clip = Live2DActorClip(
            model_path   = path,
            motion_group = motion_group,
            start_ms     = start_ms,
            duration_ms  = 3000,
        )
        self._track.clips.append(clip)
        self._selected = clip
        self.update()
        self.clip_changed.emit()

    def _clip_at(self, x: float) -> Optional[Live2DActorClip]:
        for clip in self._track.clips:
            x1 = self._ms_to_x(clip.start_ms)
            x2 = max(x1 + 4, self._ms_to_x(clip.end_ms))
            if x1 <= x <= x2:
                return clip
        return None

    def _blend_at(self, x: float) -> Optional[Live2DBlend]:
        """Return the blend marker whose diamond is within 8px of x."""
        for blend in self._track.blends:
            if abs(self._ms_to_x(blend.center_ms) - x) <= 8:
                return blend
        return None

    def _try_create_blend(self, click_ms: int) -> None:
        """Create a blend marker if click_ms is between two adjacent clips."""
        sorted_clips = sorted(self._track.clips, key=lambda c: c.start_ms)
        for i in range(len(sorted_clips) - 1):
            a = sorted_clips[i]
            b = sorted_clips[i + 1]
            gap_start = a.end_ms
            gap_end   = b.start_ms
            # Also allow clicking near the boundary of overlapping/adjacent clips
            zone_start = a.end_ms - 200
            zone_end   = b.start_ms + 200
            if zone_start <= click_ms <= zone_end:
                center = (a.end_ms + b.start_ms) // 2
                blend = Live2DBlend(center_ms=center, duration_ms=500)
                self._track.blends.append(blend)
                self.update()
                self.clip_changed.emit()
                return

    # ── context menu ──────────────────────────────────────────────────────

    def _show_menu(self, gpos: QPoint, clip: Optional[Live2DActorClip],
                   click_x: float) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))
        performance_source_act = menu.addAction("Performance Source Mapping...") if clip else None
        add_act   = menu.addAction("Live2D 클립 추가...")
        status_act = menu.addAction("로딩/QA 상태 보기") if clip else None
        video_mocap_act = menu.addAction("영상 모션 매핑...") if clip else None
        storyboard_act = menu.addAction("모션 자동 스토리보드") if clip else None
        probe_act = menu.addAction("격리 렌더 Probe") if clip else None
        prerender_act = menu.addAction("프리렌더 캐시 생성") if clip else None
        quarantine_act = menu.addAction("Known Failure로 격리") if clip else None
        open_folder_act = menu.addAction("모델 폴더 열기") if clip else None
        blend_act = menu.addAction("⚡ 블랜드 설정...") if clip else None
        del_act   = menu.addAction("클립 삭제") if clip else None
        if clip and not getattr(clip, "model_path", ""):
            for action in (status_act, storyboard_act, probe_act, prerender_act, quarantine_act, open_folder_act):
                if action is not None:
                    action.setEnabled(False)
        act = menu.exec(gpos)
        if act == add_act:
            self._import_clip(self._x_to_ms(click_x))
        elif status_act and act == status_act and clip:
            self._show_clip_diagnostics(clip)
        elif performance_source_act and act == performance_source_act and clip:
            self._selected = clip
            self.update()
            self.performance_source_mapping_requested.emit(clip)
        elif video_mocap_act and act == video_mocap_act and clip:
            self._selected = clip
            self.update()
            self.video_mocap_requested.emit(clip)
        elif storyboard_act and act == storyboard_act and clip:
            self._selected = clip
            self.update()
            self.motion_storyboard_requested.emit(clip)
        elif probe_act and act == probe_act and clip:
            self._probe_clip(clip)
        elif prerender_act and act == prerender_act and clip:
            self._prerender_clip(clip)
        elif quarantine_act and act == quarantine_act and clip:
            self._quarantine_clip(clip)
        elif open_folder_act and act == open_folder_act and clip:
            self._open_clip_folder(clip)
        elif blend_act and act == blend_act and clip:
            self._edit_blend(clip)
        elif del_act and act == del_act and clip:
            self._evict_model(clip)
            self._track.clips.remove(clip)
            if self._selected is clip:
                self._selected = None
            self.update()
            self.clip_changed.emit()

    def _show_clip_diagnostics(self, clip: Live2DActorClip) -> None:
        try:
            from app.actor_loading_cache import actor_loading_cache_report
            status = actor_clip_status(clip)
            report = actor_loading_cache_report()
            rows = [
                row for row in report.get("entries", []) or []
                if str(row.get("path", "")) in {str(getattr(clip, "model_path", "")), str(status.get("path", ""))}
            ][:3]
            text = {
                "clip_status": status,
                "recent_cache_entries": rows,
            }
            QMessageBox.information(self, "Live2D Actor Diagnostics", json.dumps(text, ensure_ascii=False, indent=2, default=str))
        except Exception as exc:
            QMessageBox.warning(self, "Live2D", f"진단 표시 실패:\n{exc}")

    def _probe_clip(self, clip: Live2DActorClip) -> None:
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server, write_actor_probe_report
            payload = default_actor_preview_frame_server().probe_frame("live2d", clip.model_path, width=320, height=320)
            out = write_actor_probe_report(Path("debugCapture") / "actor_probe_live2d_clip.json", payload)
            QMessageBox.information(self, "Live2D Probe", f"{payload.get('status', 'unknown')}\n{out}")
        except Exception as exc:
            QMessageBox.warning(self, "Live2D Probe", str(exc))

    def _prerender_clip(self, clip: Live2DActorClip) -> None:
        try:
            from app.actor_preview_frame_server import default_actor_preview_frame_server
            payload = default_actor_preview_frame_server().prerender_preview(
                "live2d",
                clip.model_path,
                width=360,
                height=360,
                duration_ms=max(1000, int(getattr(clip, "duration_ms", 1000) or 1000)),
                limit_frames=12,
            )
            QMessageBox.information(self, "Live2D Prerender", f"{payload.get('status', 'unknown')}\nframes={payload.get('frame_count', 0)}")
        except Exception as exc:
            QMessageBox.warning(self, "Live2D Prerender", str(exc))

    def _quarantine_clip(self, clip: Live2DActorClip) -> None:
        try:
            from app.actor_known_failures import add_actor_known_failure
            entry = add_actor_known_failure(kind="live2d", path=clip.model_path)
            QMessageBox.information(self, "Live2D", f"Known failure updated:\n{entry.get('id')}")
        except Exception as exc:
            QMessageBox.warning(self, "Live2D", str(exc))

    def _open_clip_folder(self, clip: Live2DActorClip) -> None:
        try:
            os.startfile(str(Path(clip.model_path).parent))
        except Exception:
            pass

    @staticmethod
    def _evict_model(clip: Live2DActorClip) -> None:
        """Remove the clip's cached model from the offscreen renderer."""
        try:
            from app.live2d.actor_track import _OffscreenRenderer
            try:
                from app.live2d.compat import normalize_live2d_model_path
                model_path = normalize_live2d_model_path(clip.model_path) or clip.model_path
            except Exception:
                model_path = clip.model_path
            _OffscreenRenderer.instance().evict_model(model_path, id(clip))
        except Exception:
            pass

    def _show_blend_menu(self, gpos: QPoint, blend: Live2DBlend) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))
        edit_act = menu.addAction("✏️ 블랜드 편집...")
        del_act  = menu.addAction("블랜드 삭제")
        act = menu.exec(gpos)
        if act == edit_act:
            self._edit_blend_marker(blend)
        elif act == del_act:
            self._track.blends.remove(blend)
            self.update()
            self.clip_changed.emit()

    def _edit_blend_marker(self, blend: Live2DBlend) -> None:
        from PySide6.QtWidgets import (QDialog, QFormLayout, QSpinBox,
                                        QComboBox, QDialogButtonBox)
        dlg = QDialog(self)
        dlg.setWindowTitle("블랜드 설정")
        dlg.setStyleSheet(studio_chrome_qss(""))
        form = QFormLayout(dlg)

        spin = QSpinBox()
        spin.setRange(100, 5000)
        spin.setSuffix(" ms")
        spin.setValue(blend.duration_ms)

        combo = QComboBox()
        for c in ("smoothstep", "linear", "ease_in", "ease_out"):
            combo.addItem(c)
        idx = combo.findText(blend.curve)
        if idx >= 0:
            combo.setCurrentIndex(idx)

        form.addRow("지속 시간", spin)
        form.addRow("커브", combo)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            blend.duration_ms = spin.value()
            blend.curve = combo.currentText()
            self.update()
            self.clip_changed.emit()

    def _edit_blend(self, clip: Live2DActorClip) -> None:
        from PySide6.QtWidgets import (QDialog, QFormLayout, QSpinBox,
                                        QComboBox, QDialogButtonBox)
        dlg = QDialog(self)
        dlg.setWindowTitle("블랜드 설정")
        dlg.setStyleSheet(studio_chrome_qss(""))
        form = QFormLayout(dlg)

        spin_in = QSpinBox()
        spin_in.setRange(0, 10000)
        spin_in.setSuffix(" ms")
        spin_in.setValue(clip.blend_in_ms)

        spin_out = QSpinBox()
        spin_out.setRange(0, 10000)
        spin_out.setSuffix(" ms")
        spin_out.setValue(clip.blend_out_ms)

        combo = QComboBox()
        for c in ("smoothstep", "linear", "ease_in", "ease_out"):
            combo.addItem(c)
        idx = combo.findText(clip.blend_curve)
        if idx >= 0:
            combo.setCurrentIndex(idx)

        form.addRow("페이드 인", spin_in)
        form.addRow("페이드 아웃", spin_out)
        form.addRow("커브", combo)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                 QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        form.addRow(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            clip.blend_in_ms  = spin_in.value()
            clip.blend_out_ms = spin_out.value()
            clip.blend_curve  = combo.currentText()
            self.update()
            self.clip_changed.emit()

    def _import_clip(self, start_ms: int) -> None:
        from app.live2d.live2d_viewer import _SAMPLES_DIR
        path, _ = QFileDialog.getOpenFileName(
            self, "Live2D 모델 선택", _SAMPLES_DIR,
            "Live2D Model (*.model3.json *.model3.json.bytes *.json *.unitypackage);;All Files (*)"
        )
        if not path:
            return
        try:
            from app.live2d.compat import model_support_error
            error = model_support_error(path)
            if error:
                QMessageBox.warning(self, "Live2D", error)
                return
        except Exception:
            pass

        # Parse motion groups from model3.json
        motion_group = ""
        motion_idx   = 0
        duration_ms  = 3000
        try:
            from app.live2d.compat import normalize_live2d_model_path
            meta_path = normalize_live2d_model_path(path) or path
            with open(meta_path, encoding="utf-8") as f:
                data = json.load(f)
            motions = data.get("FileReferences", {}).get("Motions", {})
            if motions:
                motion_group = list(motions.keys())[0]
                # prefer "Idle" if available
                for g in motions:
                    if "idle" in g.lower():
                        motion_group = g
                        break
        except Exception:
            pass

        clip = Live2DActorClip(
            model_path   = path,
            motion_group = motion_group,
            motion_idx   = 0,
            start_ms     = start_ms,
            duration_ms  = duration_ms,
        )
        self._track.clips.append(clip)
        self._selected = clip
        self.update()
        self.clip_changed.emit()
