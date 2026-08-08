from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import QLabel, QMenu, QSizePolicy, QWidget

from app.audio_tracks import AudioClip, AudioTrack, is_audio_path, is_video_path
from app.effect_cards import FADE_MIME_TYPE, FadeCard
from app.i18n import tr
from app.studio_slider import StudioSlider
from app.studio_theme import paint_studio_clip_block, paint_studio_playhead
from app.style import (
    COLOR_ACCENT_ORANGE,
    COLOR_BG_L3,
    COLOR_BG_L5,
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
)
from app.timeline_drop_payloads import fade_duration_from_mime as _drop_fade_duration_from_mime
from app.timeline_model import FadeSegment
from app.timeline_ruler import DEFAULT_PX_PER_SEC, MAX_PX_PER_SEC, MIN_PX_PER_SEC
from app.timeline_striped_host import StripedHost
from app.video_editor_audio_shared import _ANTS_OWNER, _block_signals, _draw_marching_ants
from app.video_editor_audio_style import (
    AUDIO_AMBER,
    AUDIO_BG,
    AUDIO_GREEN,
    AUDIO_RED,
    AUDIO_TEXT_DIM,
)


class AudioTrackRow(QWidget):
    """Multi-clip timeline row for an ``AudioTrack``.

    One row = one AudioTrack. Multiple AudioClips belonging to that
    track are drawn side-by-side on the bar area; each can be dragged,
    selected, faded, and split independently.

    The row header shows the track's master volume slider. Per-clip
    interactions (drag / selection / fade / context menu / double-click
    for sound editor) target the clip the user actually clicks on.
    """

    clicked = Signal(int)                 # track_id
    volume_changed = Signal(int, float)   # track_id, master volume
    row_context_menu = Signal(int, QPoint)   # track_id, global_pos (clicked on empty area)
    clip_context_menu = Signal(int, int, QPoint)  # track_id, clip_id, global_pos
    load_source_requested = Signal(int)   # track_id ??empty-row click
    media_dropped = Signal(int, object)   # track_id, Path ??any media for routing
    track_changed = Signal(int)           # track_id ??clips were mutated
    clip_selection_changed = Signal(int, int, int, int)  # track_id, clip_id, start, end
    open_editor_requested = Signal(int, int)  # track_id, clip_id
    position_requested = Signal(int, int)  # track_id, project ms

    MARGIN = 180
    CLIP_LEFT = 180   # same as MARGIN, left meters removed (now in mixer panel)
    LABEL_H = 0
    BAR_H = 42
    SPECTRUM_H = 0
    PADDING = 4

    BAR_COLOR = QColor("#283028")
    BAR_BORDER = QColor(116, 126, 116, 86)
    BAR_COLOR_EMPTY = QColor("#242424")
    BAR_COLOR_ACTIVE = QColor("#303830")

    FADE_EDGE_GRAB_PX = 6
    PLAYHEAD_GRAB_PX = 9

    def __init__(self, track: AudioTrack) -> None:
        super().__init__()
        self.track = track
        self._is_active: bool = False
        self._active_clip_id: int | None = None
        self._lane_index: int = 1
        self._march_offset: int = 0   # marching-ants animation offset
        self._position_ms: int = 0
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._dragging_playhead: bool = False

        # Active interaction state. ``_interaction_clip`` points to the
        # AudioClip the user is currently manipulating (drag / select /
        # fade-resize); cleared on mouse release.
        self._interaction_clip: AudioClip | None = None
        self._dragging_offset: bool = False
        self._drag_start_x: int = 0
        self._drag_start_offset_ms: int = 0
        self._resizing_fade: FadeSegment | None = None
        self._resizing_clip: AudioClip | None = None
        self._resize_side: str = ""
        self._resize_orig_start: int = 0
        self._resize_orig_end: int = 0
        self._waveform_errors: dict[int, str] = {}  # clip_id ??reason
        # Realtime L/R level meters (0.0??.0, peak-hold decay)
        self._level_l: float = 0.0
        self._level_r: float = 0.0
        # Volume envelope drag state
        self._env_drag_clip: AudioClip | None = None
        self._env_drag_idx: int = -1       # index into clip.volume_points (-1 = new)
        self._env_drag_active: bool = False
        # Hover tracking for audio-fade edge handles.
        self._hover_audio_fade_key: tuple | None = None    # (id(clip), id(fade))
        self._hover_audio_fade_side: str = ""

        self.setFixedHeight(self.LABEL_H + self.BAR_H + self.SPECTRUM_H + self.PADDING)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAcceptDrops(True)

        _audio_name = track.display_name or tr("veditor.audio.track_empty")
        self._name_label = QLabel(_audio_name, self)
        self._name_label.setStyleSheet(
            f"color: {COLOR_TEXT_SECONDARY}; font-weight: 600; font-size: 11px; background: transparent;"
        )
        self._name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._volume_slider = StudioSlider("audio", self)
        self._volume_slider.setMinimum(0)
        self._volume_slider.setMaximum(150)
        self._volume_slider.setValue(int(round(track.volume * 100)))
        self._volume_slider.setFixedWidth(110)
        self._volume_slider.setToolTip(tr("veditor.audio.volume"))
        self._volume_slider.valueChanged.connect(self._on_volume_slider_changed)
        self._name_label.hide()
        self._volume_slider.hide()

        self._reposition_header()

    # ---- geometry / state helpers ----

    def deselect_clip(self) -> None:
        """Clear the active clip selection (called when video clip is selected)."""
        if self._active_clip_id is not None:
            self._active_clip_id = None
            self._march_offset = 0
            self.update()

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self.update()

    def set_active(self, active: bool) -> None:
        if self._is_active == active:
            return
        self._is_active = active
        self.update()

    def set_position(self, ms: int) -> None:
        self._position_ms = max(0, int(ms))
        self.update()

    def refresh_from_track(self) -> None:
        _n = self.track.display_name or tr("veditor.audio.track_empty")
        self._name_label.setText(_n)
        with _block_signals(self._volume_slider):
            self._volume_slider.setValue(int(round(self.track.volume * 100)))
        self.update()

    def set_lane_index(self, index: int) -> None:
        lane = max(1, int(index))
        if lane == self._lane_index:
            return
        self._lane_index = lane
        self.update()

    def set_waveform_error(self, clip_id: int, reason: str) -> None:
        self._waveform_errors[clip_id] = reason or "decode failed"
        self.update()

    def clear_waveform_error(self, clip_id: int) -> None:
        self._waveform_errors.pop(clip_id, None)

    def _preferred_width(self) -> int:
        span = self.track.extent_ms()
        return int(span / 1000.0 * self._px_per_sec) + 2 * self.MARGIN + 40

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_header()

    def _reposition_header(self) -> None:
        if self.LABEL_H <= 0:
            self._name_label.setGeometry(0, 0, 0, 0)
            self._volume_slider.setGeometry(0, 0, 0, 0)
            return
        self._name_label.setGeometry(
            self.CLIP_LEFT, 3,
            max(50, self.width() - self.CLIP_LEFT - self._volume_slider.width() - self.MARGIN * 2),
            self.LABEL_H - 4,
        )
        self._volume_slider.setGeometry(
            self.width() - self._volume_slider.width() - self.MARGIN,
            (self.LABEL_H - self._volume_slider.sizeHint().height()) // 2,
            self._volume_slider.width(),
            self._volume_slider.sizeHint().height(),
        )

    def _project_ms_to_x(self, ms: int) -> int:
        return int(self.CLIP_LEFT + ms / 1000.0 * self._px_per_sec)

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.CLIP_LEFT) / self._px_per_sec * 1000))

    def _playhead_hit(self, pos: QPoint) -> bool:
        row_bottom = self.LABEL_H + self.BAR_H + self.SPECTRUM_H
        if pos.y() < self.LABEL_H - 8 or pos.y() > row_bottom + 8:
            return False
        px = self._project_ms_to_x(self._position_ms)
        return abs(pos.x() - px) <= self.PLAYHEAD_GRAB_PX

    # ---- per-clip hit testing ----

    def _clip_bar_rect(self, clip: AudioClip) -> QRect:
        bar_y = self.LABEL_H
        x1 = self._project_ms_to_x(clip.offset_ms)
        x2 = self._project_ms_to_x(clip.offset_ms + clip.effective_length_ms)
        return QRect(x1, bar_y, max(2, x2 - x1), self.BAR_H)

    @staticmethod
    def _audio_clip_effects_active(clip: AudioClip) -> bool:
        effects = getattr(clip, "effects", None)
        if not isinstance(effects, dict):
            return False
        for key, state in effects.items():
            if not isinstance(state, dict):
                continue
            if bool(state.get("enabled")):
                return True
            if key == "ai_master" and str(state.get("preset", "") or "").lower() not in {"", "custom", "none"}:
                return True
            if key == "loudness" and bool(state.get("target_lufs")):
                return True
            if key == "dialogue_cleanup" and any(
                state.get(name) not in (None, False, 0, 0.0, "")
                for name in ("strength", "noise_reduction", "de_reverb", "clarity")
            ):
                return True
        return False

    @staticmethod
    def _paint_small_badge(
        painter: QPainter,
        rect: QRect,
        label: str,
        color_a: str,
        color_b: str,
    ) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(color_a))
        grad.setColorAt(1.0, QColor(color_b))
        painter.setPen(QPen(QColor(255, 255, 255, 82), 1))
        painter.setBrush(QBrush(grad))
        painter.drawRoundedRect(rect, 6, 6)
        f = painter.font()
        f.setPixelSize(8)
        f.setBold(True)
        painter.setFont(f)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)
        painter.restore()

    def _clip_at_pos(self, pos: QPoint) -> AudioClip | None:
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        for clip in self.track.clips:
            if clip.source_path is None:
                continue
            r = self._clip_bar_rect(clip)
            if r.left() <= pos.x() <= r.right():
                return clip
        return None

    def _x_to_clip_local_ms(self, clip: AudioClip, x: int) -> int:
        project_ms = self._x_to_project_ms(x)
        local = project_ms - clip.offset_ms
        return max(0, min(clip.effective_length_ms, local))

    def _clip_local_ms_to_x(self, clip: AudioClip, local_ms: int) -> int:
        return self._project_ms_to_x(clip.offset_ms + local_ms)

    def _fade_edge_at(self, clip: AudioClip, x: int, y: int):
        bar_y = self.LABEL_H
        if y < bar_y or y > bar_y + self.BAR_H:
            return None, ""
        for fade in clip.fades:
            local_start = fade.start_ms - clip.trim_start_ms
            local_end = fade.end_ms - clip.trim_start_ms
            fx1 = self._clip_local_ms_to_x(clip, local_start)
            fx2 = self._clip_local_ms_to_x(clip, local_end)
            if abs(x - fx1) <= self.FADE_EDGE_GRAB_PX:
                return fade, "left"
            if abs(x - fx2) <= self.FADE_EDGE_GRAB_PX:
                return fade, "right"
        return None, ""

    def _fade_under(self, clip: AudioClip, pos: QPoint):
        if pos.y() < self.LABEL_H or pos.y() > self.LABEL_H + self.BAR_H:
            return None
        local_ms = self._x_to_clip_local_ms(clip, pos.x())
        source_ms = clip.trim_start_ms + local_ms
        for fade in clip.fades:
            if fade.start_ms <= source_ms < fade.end_ms:
                return fade
        return None

    # ---- mouse ----

    def _on_volume_slider_changed(self, value: int) -> None:
        vol = max(0.0, min(1.5, value / 100.0))
        self.track.volume = vol
        self.volume_changed.emit(self.track.id, vol)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        y = pos.y()
        mods = event.modifiers()

        # Right-click dispatches to fade menu / clip menu / row menu.
        if event.button() == Qt.MouseButton.RightButton:
            clip = self._clip_at_pos(pos)
            if clip is not None:
                # Check if right-clicking on an envelope point first
                bar_rect = self._clip_bar_rect(clip)
                env_idx = self._envelope_hit_test(clip, bar_rect, pos)
                if env_idx >= 0:
                    from PySide6.QtWidgets import QMenu
                    m = QMenu(self)
                    act_del = m.addAction("?ъ씤????젣")
                    act_clr = m.addAction("Reset envelope")
                    chosen = m.exec(event.globalPosition().toPoint())
                    pts = getattr(clip, "volume_points", None) or []
                    if chosen is act_del and 0 <= env_idx < len(pts):
                        pts.pop(env_idx)
                        self.update()
                    elif chosen is act_clr:
                        clip.volume_points = []
                        self.update()
                    return
                fade = self._fade_under(clip, pos)
                if fade is not None:
                    self._show_fade_menu(clip, fade, event.globalPosition().toPoint())
                    return
                self.clip_context_menu.emit(
                    self.track.id, clip.id, event.globalPosition().toPoint()
                )
                return
            self.row_context_menu.emit(self.track.id, event.globalPosition().toPoint())
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return
        self.clicked.emit(self.track.id)
        if y < self.LABEL_H:
            return

        # Empty row ??request to load an audio file.
        if not self.track.is_loaded:
            self.load_source_requested.emit(self.track.id)
            return

        if self._playhead_hit(pos):
            self._dragging_playhead = True
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.position_requested.emit(self.track.id, self._x_to_project_ms(x))
            event.accept()
            return

        clip = self._clip_at_pos(pos)
        if clip is None:
            return
        self._active_clip_id = clip.id
        self._interaction_clip = clip
        # Notify the window so it can take ants ownership away from video.
        self.clip_selection_changed.emit(
            self.track.id, clip.id,
            getattr(clip, "selection_start_ms", -1),
            getattr(clip, "selection_end_ms", -1),
        )
        self.update()

        # 0. Volume envelope: Ctrl+click adds a point; dragging existing
        #    points moves them; right-click on a point deletes it.
        if mods & Qt.KeyboardModifier.ControlModifier:
            bar_rect = self._clip_bar_rect(clip)
            if bar_rect.contains(pos):
                t = self._clip_local_norm(clip, x, bar_rect)
                v = self._envelope_vol(bar_rect, y)
                pts = getattr(clip, "volume_points", None)
                if pts is None:
                    clip.volume_points = []
                    pts = clip.volume_points
                pts.append((round(t, 4), round(v, 3)))
                pts.sort(key=lambda p: p[0])
                self.update()
                return
        bar_rect = self._clip_bar_rect(clip)
        if bar_rect.contains(pos):
            idx = self._envelope_hit_test(clip, bar_rect, pos)
            if idx >= 0:
                self._env_drag_clip = clip
                self._env_drag_idx = idx
                self._env_drag_active = True
                self.setCursor(Qt.CursorShape.SizeAllCursor)
                return

        # 1. Fade edge resize takes priority.
        fade, side = self._fade_edge_at(clip, x, y)
        if fade is not None:
            self._resizing_fade = fade
            self._resizing_clip = clip
            self._resize_side = side
            self._resize_orig_start = fade.start_ms
            self._resize_orig_end = fade.end_ms
            self._drag_start_x = x
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return

        # Option C: legacy Shift+drag clip-local range select removed.
        # Industry NLEs use click-to-select on clips; Shift toggles add
        # to the multi-clip selection set instead.

        # 2. Else drag the clip on the project timeline.
        self._dragging_offset = True
        self._drag_start_x = x
        self._drag_start_offset_ms = clip.offset_ms
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        x = pos.x()
        clip = self._interaction_clip

        if self._dragging_playhead:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            self.position_requested.emit(self.track.id, self._x_to_project_ms(x))
            event.accept()
            return

        # Volume envelope drag
        if self._env_drag_active and self._env_drag_clip is not None:
            ec = self._env_drag_clip
            bar_rect = self._clip_bar_rect(ec)
            t = round(self._clip_local_norm(ec, x, bar_rect), 4)
            v = round(self._envelope_vol(bar_rect, pos.y()), 3)
            pts = getattr(ec, "volume_points", None) or []
            if 0 <= self._env_drag_idx < len(pts):
                pts[self._env_drag_idx] = (t, v)
                pts.sort(key=lambda p: p[0])
                self._env_drag_idx = next(
                    (i for i, p in enumerate(pts) if p == (t, v)), self._env_drag_idx
                )
            self.update()
            return

        if self._resizing_fade is not None and clip is not None:
            delta_ms = int((x - self._drag_start_x) / max(self._px_per_sec, 0.001) * 1000)
            fade = self._resizing_fade
            # Fade start/end are in source-ms (absolute within the source
            # file), so their valid range is [clip.trim_start_ms, clip.effective_trim_end_ms].
            if self._resize_side == "left":
                new_start = max(
                    clip.trim_start_ms,
                    min(fade.end_ms - 100, self._resize_orig_start + delta_ms),
                )
                fade.start_ms = new_start
            else:
                new_end = min(
                    clip.effective_trim_end_ms,
                    max(fade.start_ms + 100, self._resize_orig_end + delta_ms),
                )
                fade.end_ms = new_end
            self.update()
            self.track_changed.emit(self.track.id)
            return

        if self._dragging_offset and clip is not None:
            dx = x - self._drag_start_x
            d_ms = int(dx / max(self._px_per_sec, 0.001) * 1000)
            new_offset = max(0, self._drag_start_offset_ms + d_ms)
            if new_offset != clip.offset_ms:
                clip.offset_ms = new_offset
                self.track_changed.emit(self.track.id)
                self.update()
            return

        # Idle hover: cursor hinting + edge-handle hover highlight.
        prev_key = self._hover_audio_fade_key
        prev_side = self._hover_audio_fade_side
        hover_clip = self._clip_at_pos(pos)
        if self._playhead_hit(pos):
            self._hover_audio_fade_key = None
            self._hover_audio_fade_side = ""
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            if prev_key is not None:
                self.update()
            return
        if hover_clip is not None:
            fade, side = self._fade_edge_at(hover_clip, x, pos.y())
            if fade is not None:
                self._hover_audio_fade_key = (id(hover_clip), id(fade))
                self._hover_audio_fade_side = side
                self.setCursor(Qt.CursorShape.SizeHorCursor)
                if (prev_key != self._hover_audio_fade_key
                        or prev_side != self._hover_audio_fade_side):
                    self.update()
                return
        self._hover_audio_fade_key = None
        self._hover_audio_fade_side = ""
        if prev_key is not None:
            self.update()
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, _event) -> None:
        if self._hover_audio_fade_key is not None:
            self._hover_audio_fade_key = None
            self._hover_audio_fade_side = ""
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_offset = False
        self._dragging_playhead = False
        self._resizing_fade = None
        self._resizing_clip = None
        self._resize_side = ""
        self._interaction_clip = None
        if self._env_drag_active:
            self._env_drag_active = False
            self._env_drag_clip = None
            self._env_drag_idx = -1
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        pos = event.position().toPoint()
        clip = self._clip_at_pos(pos)
        if clip is None:
            return
        # Double-click on a fade ??delete that fade.
        fade = self._fade_under(clip, pos)
        if fade is not None:
            try:
                clip.fades.remove(fade)
            except ValueError:
                return
            self.update()
            self.track_changed.emit(self.track.id)
            return
        # Else open the sound editor for this clip.
        self.open_editor_requested.emit(self.track.id, clip.id)

    # ---- drag & drop ----

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        md = event.mimeData()
        if md.hasFormat(FADE_MIME_TYPE):
            event.acceptProposedAction()
            return
        if md.hasUrls():
            for u in md.urls():
                p = Path(u.toLocalFile())
                if is_audio_path(p) or is_video_path(p):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self.dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        md = event.mimeData()
        pos = event.position().toPoint()

        if md.hasFormat(FADE_MIME_TYPE):
            clip = self._clip_at_pos(pos)
            if clip is None or clip.source_path is None or clip.effective_length_ms <= 0:
                event.ignore()
                return
            dur_ms = _drop_fade_duration_from_mime(
                md,
                default_ms=FadeCard.DEFAULT_DURATION_MS,
            )
            dur_ms = max(100, dur_ms)
            center_local = self._x_to_clip_local_ms(clip, pos.x())
            # FadeSegments are stored in source-ms (absolute within
            # source file) so they survive trim / split correctly.
            source_center = clip.trim_start_ms + center_local
            start = max(clip.trim_start_ms, source_center - dur_ms // 2)
            end = min(clip.effective_trim_end_ms, start + dur_ms)
            if end <= start:
                event.ignore()
                return
            clip.fades.append(FadeSegment(start, end))
            clip.fades.sort(key=lambda f: f.start_ms)
            self.update()
            self.track_changed.emit(self.track.id)
            self.clicked.emit(self.track.id)
            event.acceptProposedAction()
            return

        if not md.hasUrls():
            event.ignore()
            return
        for u in md.urls():
            p = Path(u.toLocalFile())
            if is_audio_path(p) or is_video_path(p):
                self.media_dropped.emit(self.track.id, p)
                event.acceptProposedAction()
                return
        event.ignore()

    # ---- fade menu (per-fade, on right-click) ----

    def _show_fade_menu(self, clip: AudioClip, fade, global_pos) -> None:
        menu = QMenu(self)
        act_in = menu.addAction(tr("veditor.fade_menu.in"))
        act_in.setCheckable(True)
        act_in.setChecked(getattr(fade, "kind", "both") == "in")
        act_out = menu.addAction(tr("veditor.fade_menu.out"))
        act_out.setCheckable(True)
        act_out.setChecked(getattr(fade, "kind", "both") == "out")
        act_both = menu.addAction(tr("veditor.fade_menu.both"))
        act_both.setCheckable(True)
        act_both.setChecked(getattr(fade, "kind", "both") == "both")
        menu.addSeparator()
        act_del = menu.addAction(tr("veditor.fade_menu.delete"))
        chosen = menu.exec(global_pos)
        if chosen is act_in:
            fade.kind = "in"
        elif chosen is act_out:
            fade.kind = "out"
        elif chosen is act_both:
            fade.kind = "both"
        elif chosen is act_del:
            try:
                clip.fades.remove(fade)
            except ValueError:
                pass
        else:
            return
        self.update()
        self.track_changed.emit(self.track.id)

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Header bg
        if self.LABEL_H > 0:
            if self._is_active:
                painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L5))
            else:
                painter.fillRect(0, 0, self.width(), self.LABEL_H, QColor(COLOR_BG_L3))
        # Bar + spectrum area: 80% audio-tinted stripe ??fills full widget
        # width so it extends to the scroll end identical to the video track.
        bar_y = self.LABEL_H
        full_bar = QRect(0, bar_y, self.width(), self.BAR_H + self.SPECTRUM_H)
        StripedHost._draw_stripes(
            painter, full_bar,
            StripedHost.BG_80_AUDIO, StripedHost.STRIPE_80_AUDIO,
        )
        painter.fillRect(
            full_bar.adjusted(self.MARGIN, 3, 0, -3),
            QColor(255, 255, 255, 2),
        )
        label_col = QRect(0, 0, self.MARGIN, self.height())
        label_grad = QLinearGradient(label_col.topLeft(), label_col.bottomLeft())
        label_grad.setColorAt(0.0, QColor("#171819"))
        label_grad.setColorAt(1.0, QColor("#101111"))
        painter.fillRect(label_col, label_grad)
        body_rect = QRect(0, bar_y, self.MARGIN, self.BAR_H + self.SPECTRUM_H)
        body_grad = QLinearGradient(body_rect.topLeft(), body_rect.bottomLeft())
        body_grad.setColorAt(0.0, QColor("#161717"))
        body_grad.setColorAt(1.0, QColor("#111111"))
        painter.fillRect(body_rect, body_grad)
        painter.setPen(QColor(255, 255, 255, 14))
        painter.drawLine(0, body_rect.top(), self.MARGIN - 1, body_rect.top())
        painter.setPen(QColor("#242424"))
        painter.drawLine(self.MARGIN - 1, 0, self.MARGIN - 1, self.height())
        painter.drawLine(0, body_rect.bottom(), self.MARGIN - 1, body_rect.bottom())
        accent = QColor("#C7CBD0" if self._is_active else "#6D7074")
        accent.setAlpha(82 if self._is_active else 22)
        painter.fillRect(0, body_rect.top() + 8, 2, max(12, body_rect.height() - 16), accent)
        tab_rect = QRect(14, body_rect.top() + 5, 86, max(18, body_rect.height() - 10))
        tab_grad = QLinearGradient(tab_rect.topLeft(), tab_rect.bottomLeft())
        tab_grad.setColorAt(0.0, QColor(255, 255, 255, 7 if self._is_active else 4))
        tab_grad.setColorAt(1.0, QColor(0, 0, 0, 10))
        painter.setPen(QPen(QColor(255, 255, 255, 15 if self._is_active else 8), 1))
        painter.setBrush(QBrush(tab_grad))
        painter.drawRoundedRect(tab_rect, 3, 3)
        painter.setPen(QPen(QColor(0, 0, 0, 38), 1))
        painter.drawLine(tab_rect.right(), tab_rect.top() + 5, tab_rect.right(), tab_rect.bottom() - 5)
        label_font = QFont(painter.font())
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(12)
        label_font.setWeight(QFont.Weight.Medium)
        painter.setFont(label_font)
        painter.setPen(QColor("#D8DADD") if self._is_active else QColor("#9A9A9A"))
        label_y = bar_y + max(0, (self.BAR_H - 16) // 2)
        painter.drawText(
            QRect(tab_rect.left(), label_y, tab_rect.width(), 16),
            Qt.AlignmentFlag.AlignCenter,
            f"A{self._lane_index}",
        )
        label_font.setFamily("Segoe UI Variable")
        label_font.setPixelSize(10)
        label_font.setWeight(QFont.Weight.Normal)
        painter.setFont(label_font)
        painter.setPen(QColor("#7E7E7E"))
        painter.drawText(
            QRect(112, label_y, self.MARGIN - 126, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Audio",
        )
        track = self.track
        if not track.is_loaded:
            painter.setPen(QPen(QColor(COLOR_BORDER_DEFAULT), 1, Qt.PenStyle.DashLine))
            rect = QRect(self.MARGIN, bar_y + 4, self.width() - 2 * self.MARGIN, self.BAR_H - 8)
            painter.drawRect(rect)
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.audio.drop_hint")
            )
            return

        # Each clip renders independently.
        for clip in track.clips:
            if clip.source_path is None:
                continue
            self._paint_clip(painter, clip)

        # Spectrum strip below the waveform bar.
        spec_y = self.LABEL_H + self.BAR_H
        self._paint_spectrum_strip(painter, spec_y)

        # Playhead spans the full row including spectrum.
        px = self._project_ms_to_x(self._position_ms)
        paint_studio_playhead(
            painter,
            px,
            bar_y - 2,
            bar_y + self.BAR_H + self.SPECTRUM_H + 2,
            show_handle=False,
        )

    def _paint_clip(self, painter: QPainter, clip: AudioClip) -> None:
        bar_rect = self._clip_bar_rect(clip)
        is_active_clip = (clip.id == self._active_clip_id)
        color = self.BAR_COLOR_ACTIVE if is_active_clip else self.BAR_COLOR
        paint_studio_clip_block(
            painter,
            bar_rect,
            selected=is_active_clip,
            active=is_active_clip,
            fill=color,
            highlight=QColor("#53695A"),
            edge=self.BAR_BORDER,
        )
        # Marching ants on selected (active) audio clip (only when audio owns selection)
        if is_active_clip and _ANTS_OWNER == "audio":
            painter.save()
            _draw_marching_ants(painter, bar_rect, self._march_offset)
            painter.restore()

        # Catalog-style waveform: a thin line over the audio rail, not
        # a filled scope shape. This keeps the rail quiet while still
        # proving the extracted audio is present.
        mid_y = bar_rect.top() + int(bar_rect.height() * 0.62)
        wf = clip.waveform
        err = self._waveform_errors.get(clip.id)
        if wf is not None and wf.size > 0:
            import numpy as _np
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
            n = wf.shape[1] if is_stereo else len(wf)
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = max(2, min(5, (bar_rect.height() - 10) // 4))
            # Visible pixel range (clamp to widget width for speed)
            x_start = max(bar_rect.left() + 1, 0)
            x_end = min(bar_rect.right() - 1, self.width())
            if x_end > x_start and n > 0:
                # Vectorised bucket lookup for every visible x-pixel
                xs = _np.arange(x_start, x_end, dtype=_np.float64)
                src_s = trim_start_s + (xs - bar_rect.left()) / max(self._px_per_sec, 0.001)
                buckets = (src_s * WAVEFORM_BUCKETS_PER_SEC).astype(_np.int32)
                valid = (buckets >= 0) & (buckets < n)
                bc = _np.clip(buckets, 0, n - 1)

                if is_stereo:
                    l_raw = _np.where(valid, wf[0, bc], 0.0)
                    r_raw = _np.where(valid, wf[1, bc], 0.0)
                    m_raw = (l_raw + r_raw) * 0.5

                else:
                    m_raw = _np.where(valid, wf[bc], 0.0)
                peak_max = max(float(m_raw.max()), 0.005)
                m_h = (m_raw / peak_max) ** 0.58 * half_h
                pts = [QPointF(float(xs[i]), float(mid_y - m_h[i])) for i in range(len(xs))]
                painter.save()
                painter.setClipRect(bar_rect.adjusted(3, 3, -3, -3))
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(204, 232, 202, 136), 0.75))
                painter.drawPolyline(QPolygonF(pts))
                painter.setPen(QPen(QColor(0, 0, 0, 22), 0.8))
                painter.drawLine(x_start, mid_y + 1, x_end, mid_y + 1)
                painter.restore()
        elif err:
            painter.setPen(QPen(QColor(200, 80, 80, 200), 1, Qt.PenStyle.DashLine))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)
            painter.setPen(QColor(230, 140, 140, 230))
            f = painter.font(); f.setPixelSize(10); f.setBold(True); painter.setFont(f)
            painter.drawText(
                bar_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignCenter,
                "decode failed",
            )
        else:
            painter.setPen(QPen(QColor(200, 230, 200, 70), 0.75))
            painter.drawLine(bar_rect.left() + 3, mid_y, bar_rect.right() - 3, mid_y)

        # Filename stays as a quiet top label so it does not bury the
        # thin waveform line.
        painter.setPen(QColor(232, 238, 228, 142))
        f = painter.font(); f.setPixelSize(9); f.setBold(False); painter.setFont(f)
        painter.drawText(
            bar_rect.adjusted(6, 3, -6, -bar_rect.height() // 2),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
            clip.display_name,
        )

        # Cuts ??clip-local ms domain, dark overlay.
        for cut in clip.cuts:
            cx1 = self._clip_local_ms_to_x(clip, cut.start_ms)
            cx2 = self._clip_local_ms_to_x(clip, cut.end_ms)
            cut_rect = QRect(cx1, bar_rect.top(), max(1, cx2 - cx1), bar_rect.height())
            painter.fillRect(cut_rect, QColor(30, 30, 30, 210))
            if cut_rect.width() > 24:
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(cut_rect, Qt.AlignmentFlag.AlignCenter, tr("veditor.cut_label"))

        # FadeSegment actors ??in source-ms domain.
        for fade in clip.fades:
            self._paint_fade_segment(painter, clip, fade, bar_rect)

        if getattr(clip, "volume_points", None):
            self._paint_volume_envelope(painter, clip, bar_rect)

        if self._audio_clip_effects_active(clip) and bar_rect.width() >= 34:
            badge = QRect(bar_rect.right() - 32, bar_rect.top() + 5, 27, 15)
            self._paint_small_badge(painter, badge, "AUD", "#78F29B", "#2D8DFF")

    # ---- Level meters ----

    def set_level(self, l: float, r: float) -> None:
        """Update peak levels (0.0??.0) and repaint the header strip."""
        # Soft decay so the meter falls gradually
        self._level_l = max(l, self._level_l * 0.85)
        self._level_r = max(r, self._level_r * 0.85)
        self.update()

    def _paint_level_meters(self, painter: QPainter) -> None:
        """Draw L/R level meter bars in the LEFT fixed zone ??always visible."""
        bar_w = 13
        pad = 2
        gap = 2
        top = pad
        h = self.LABEL_H + self.BAR_H - pad * 2
        if h <= 0:
            return
        x_l = pad
        x_r = pad + bar_w + gap
        for level, x, label in ((self._level_l, x_l, "L"), (self._level_r, x_r, "R")):
            painter.fillRect(x, top, bar_w, h, QColor(AUDIO_BG))
            fill_h = int(level * h)
            if fill_h > 0:
                if level < 0.70:
                    color = QColor(AUDIO_GREEN)
                elif level < 0.90:
                    color = QColor(AUDIO_AMBER)
                else:
                    color = QColor(AUDIO_RED)
                painter.fillRect(x, top + h - fill_h, bar_w, fill_h, color)
            painter.setPen(QPen(QColor(120, 126, 132, 94), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x, top, bar_w - 1, h - 1)
            f = painter.font(); f.setPixelSize(8); f.setBold(True); painter.setFont(f)
            painter.setPen(QColor(AUDIO_TEXT_DIM))
            painter.drawText(x + 2, top + 1, bar_w - 2, 9, 0, label)

    def _paint_spectrum_strip(self, painter: QPainter, y: int) -> None:
        """Draw 64-bar FFT spectrum below the waveform clip area."""
        try:
            self.__paint_spectrum_strip_impl(painter, y)
        except Exception:
            pass

    def __paint_spectrum_strip_impl(self, painter: QPainter, y: int) -> None:
        import numpy as _np
        h = self.SPECTRUM_H - 4
        total_w = self.width() - 2 * self.MARGIN
        if total_w <= 0 or h <= 0:
            return

        # Background already drawn by bar+spectrum stripe in paintEvent header

        # Collect first clip with spectrum data and its bar extent
        clip_x1 = self.MARGIN
        clip_x2 = self.MARGIN
        bins = None
        for clip in self.track.clips:
            sb = getattr(clip, "spectrum_bins", None)
            if sb is not None and sb.size > 0:
                bins = sb
                br = self._clip_bar_rect(clip)
                clip_x1 = br.left()
                clip_x2 = br.right()
                break

        # Draw clip-extent background and placeholder text
        clip_w = max(0, clip_x2 - clip_x1)
        if clip_w > 0:
            painter.fillRect(clip_x1, y, clip_w, self.SPECTRUM_H, QColor(21, 23, 21, 98))
        painter.setPen(QPen(QColor(46, 48, 46), 1))
        painter.drawRect(self.MARGIN, y, total_w - 1, self.SPECTRUM_H - 1)

        if bins is None:
            if clip_w > 20:
                f = painter.font(); f.setPixelSize(9); painter.setFont(f)
                painter.setPen(QColor(116, 122, 116))
                painter.drawText(
                    QRect(clip_x1, y, clip_w, self.SPECTRUM_H),
                    Qt.AlignmentFlag.AlignCenter, "?ㅽ럺?몃읆 遺꾩꽍 以?.."
                )
                placeholder_rect = QRect(clip_x1, y, clip_w, self.SPECTRUM_H)
                painter.fillRect(placeholder_rect, QColor(21, 23, 21, 180))
                painter.setPen(QColor(116, 122, 116))
                painter.drawText(
                    placeholder_rect,
                    Qt.AlignmentFlag.AlignCenter,
                    "analyzing spectrum...",
                )
            return

        if clip_w <= 0:
            return

        n = len(bins)
        bar_w = max(1, clip_w // n)
        gap = 1
        for i in range(n):
            mag = float(bins[i])
            bar_h = max(0, int(mag * h))
            bx = clip_x1 + i * (bar_w + gap)
            if bx + bar_w > clip_x2:
                break
            by = y + self.SPECTRUM_H - 2 - bar_h
            if mag < 0.60:
                color = QColor(AUDIO_GREEN)
            elif mag < 0.85:
                color = QColor(AUDIO_AMBER)
            else:
                color = QColor(AUDIO_RED)
            painter.fillRect(bx, by, bar_w, bar_h, color)

        # Frequency axis labels within clip extent
        f = painter.font(); f.setPixelSize(8); painter.setFont(f)
        painter.setPen(QColor(AUDIO_TEXT_DIM))
        for label, frac in (("20Hz", 0.0), ("200", 0.3), ("2k", 0.6), ("20k", 1.0)):
            lx = clip_x1 + int(frac * (clip_w - bar_w))
            if lx < clip_x2:
                painter.drawText(lx, y + self.SPECTRUM_H - 2, label)

    # ---- Volume envelope ----

    _ENV_COLOR = QColor(255, 220, 80, 220)     # yellow-orange line
    _ENV_POINT_R = 4                            # handle radius px
    _ENV_LINE_W = 2
    _ENVELOPE_GRAB_PX = 8                      # hit-test radius for existing points

    def _envelope_y(self, bar_rect: QRect, vol: float) -> int:
        """Map volume [0,2] to a y pixel inside ``bar_rect``.
        vol=0 ??bottom, vol=1 ??centre, vol=2 ??top."""
        h = bar_rect.height() - 2
        clamped = max(0.0, min(2.0, float(vol)))
        return bar_rect.bottom() - 1 - int(clamped / 2.0 * h)

    def _envelope_vol(self, bar_rect: QRect, y: int) -> float:
        """Inverse of _envelope_y: pixel ??volume [0,2]."""
        h = bar_rect.height() - 2
        if h <= 0:
            return 1.0
        frac = (bar_rect.bottom() - 1 - y) / h
        return max(0.0, min(2.0, frac * 2.0))

    def _clip_local_norm(self, clip: AudioClip, x_px: int, bar_rect: QRect) -> float:
        """x pixel ??normalised [0,1] position within the clip."""
        bw = max(1, bar_rect.width() - 2)
        t = (x_px - bar_rect.left() - 1) / bw
        return max(0.0, min(1.0, t))

    def _eval_envelope(self, clip: AudioClip, t_norm: float) -> float:
        """Interpolate the volume envelope at ``t_norm`` [0,1]."""
        pts = getattr(clip, "volume_points", None) or []
        if not pts:
            return 1.0
        if t_norm <= pts[0][0]:
            return pts[0][1]
        if t_norm >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            t0, v0 = pts[i]
            t1, v1 = pts[i + 1]
            if t0 <= t_norm <= t1:
                if t1 == t0:
                    return v0
                alpha = (t_norm - t0) / (t1 - t0)
                return v0 + alpha * (v1 - v0)
        return 1.0

    def _paint_volume_envelope(self, painter: QPainter, clip: AudioClip, bar_rect: QRect) -> None:
        pts = getattr(clip, "volume_points", None) or []
        bw = bar_rect.width() - 2
        if bw <= 0:
            return
        painter.save()
        painter.setClipRect(bar_rect)
        line_pen = QPen(self._ENV_COLOR, self._ENV_LINE_W)
        painter.setPen(line_pen)
        # Build screen-space polyline from all points (add sentinel
        # endpoints at t=0 and t=1 so the line always spans the clip).
        def _px(t: float) -> int:
            return bar_rect.left() + 1 + int(t * bw)
        anchor_pts = []
        if not pts or pts[0][0] > 0:
            anchor_pts.append((0.0, (pts[0][1] if pts else 1.0)))
        anchor_pts.extend(pts)
        if not pts or pts[-1][0] < 1:
            anchor_pts.append((1.0, (pts[-1][1] if pts else 1.0)))
        for i in range(len(anchor_pts) - 1):
            t0, v0 = anchor_pts[i]
            t1, v1 = anchor_pts[i + 1]
            x0, y0 = _px(t0), self._envelope_y(bar_rect, v0)
            x1, y1 = _px(t1), self._envelope_y(bar_rect, v1)
            painter.drawLine(x0, y0, x1, y1)
        # Draw handles for editable points.
        painter.setBrush(self._ENV_COLOR)
        painter.setPen(QPen(QColor(40, 40, 40), 1))
        r = self._ENV_POINT_R
        for t, v in pts:
            cx, cy = _px(t), self._envelope_y(bar_rect, v)
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        painter.restore()

    def _envelope_hit_test(self, clip: AudioClip, bar_rect: QRect, pos: QPoint) -> int:
        """Return index of the envelope point under ``pos``, or -1."""
        pts = getattr(clip, "volume_points", None) or []
        bw = bar_rect.width() - 2
        if bw <= 0:
            return -1
        for i, (t, v) in enumerate(pts):
            cx = bar_rect.left() + 1 + int(t * bw)
            cy = self._envelope_y(bar_rect, v)
            if abs(pos.x() - cx) <= self._ENVELOPE_GRAB_PX and abs(pos.y() - cy) <= self._ENVELOPE_GRAB_PX:
                return i
        return -1

    def _paint_fade_segment(self, painter: QPainter, clip: AudioClip, fade, bar_rect: QRect) -> None:
        local_start = fade.start_ms - clip.trim_start_ms
        local_end = fade.end_ms - clip.trim_start_ms
        fx1 = self._clip_local_ms_to_x(clip, local_start)
        fx2 = self._clip_local_ms_to_x(clip, local_end)
        if fx2 <= fx1:
            return
        kind = getattr(fade, "kind", "both")
        painter.save()
        painter.setClipRect(bar_rect)
        if kind == "in":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(0, 0, 0, 220))
            g.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        elif kind == "out":
            g = QLinearGradient(fx1, 0, fx2, 0)
            g.setColorAt(0.0, QColor(216, 90, 48, 0))
            g.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), fx2 - fx1, bar_rect.height(), g)
        else:
            mid = (fx1 + fx2) // 2
            g_out = QLinearGradient(fx1, 0, mid, 0)
            g_out.setColorAt(0.0, QColor(216, 90, 48, 0))
            g_out.setColorAt(1.0, QColor(0, 0, 0, 220))
            painter.fillRect(fx1, bar_rect.top(), mid - fx1, bar_rect.height(), g_out)
            g_in = QLinearGradient(mid, 0, fx2, 0)
            g_in.setColorAt(0.0, QColor(0, 0, 0, 220))
            g_in.setColorAt(1.0, QColor(216, 90, 48, 0))
            painter.fillRect(mid, bar_rect.top(), fx2 - mid, bar_rect.height(), g_in)
        painter.restore()
        pen = QPen(QColor(COLOR_ACCENT_ORANGE)); pen.setWidth(2)
        painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(fx1, bar_rect.top(), max(1, fx2 - fx1), bar_rect.height())

        # Edge trim handles (always visible ??DAW-style). Hover / drag
        # detection mirrors TrackRow's scheme.
        hover_key = (id(clip), id(fade))
        is_hover = self._hover_audio_fade_key == hover_key
        is_drag = (
            self._resizing_fade is fade
            and self._resizing_clip is clip
        )
        left_hot = (is_hover and self._hover_audio_fade_side == "left") \
            or (is_drag and self._resize_side == "left")
        right_hot = (is_hover and self._hover_audio_fade_side == "right") \
            or (is_drag and self._resize_side == "right")

        def _one(x: int, hot: bool) -> None:
            if is_drag and hot:
                w = 8; color = QColor("#ff7a4a")
            elif hot:
                w = 6; color = QColor("#ff7a4a")
            else:
                w = 4; color = QColor(255, 150, 80, 210)
            painter.fillRect(x - w // 2, bar_rect.top(), w, bar_rect.height(), color)
            painter.setPen(QPen(QColor(255, 255, 255, 220), 1))
            n = max(2, w - 2)
            painter.drawLine(
                x - n // 2, bar_rect.top() + 2,
                x + n // 2, bar_rect.top() + 2,
            )
            painter.drawLine(
                x - n // 2, bar_rect.top() + bar_rect.height() - 3,
                x + n // 2, bar_rect.top() + bar_rect.height() - 3,
            )

        _one(fx1, left_hot)
        _one(fx2, right_hot)
