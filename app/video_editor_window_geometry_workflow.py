from __future__ import annotations

import time

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

from app.editor_observability import append_ux_event as _append_ux_event
from app.video_editor_preset_browser_widgets import PresetPreviewSwatch as _PresetPreviewSwatch
from app.video_editor_preset_cards import _StudioPresetTile
from app.video_editor_window_widgets import _AnimatedTimelineToolButton


def _preview_frame_rect_in_label(self, src_w: int, src_h: int) -> QRect:
    label_w = self._preview_label.width()
    label_h = self._preview_label.height()
    if label_w <= 0 or label_h <= 0 or src_w <= 0 or src_h <= 0:
        return QRect(0, 0, max(0, label_w), max(0, label_h))
    pad = max(6, min(14, min(label_w, label_h) // 30))
    inner_w = max(1, label_w - pad * 2)
    inner_h = max(1, label_h - pad * 2)
    scale = min(inner_w / src_w, inner_h / src_h)
    vw = max(1, int(src_w * scale))
    vh = max(1, int(src_h * scale))
    return QRect((label_w - vw) // 2, (label_h - vh) // 2, vw, vh)


def _sync_overlay_to_video_rect(self) -> None:
    host = self._preview_host
    label_w = self._preview_label.width()
    label_h = self._preview_label.height()
    if label_w <= 0 or label_h <= 0:
        return
    if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
        src_w = self._preview_pixmap.width()
        src_h = self._preview_pixmap.height()
    else:
        src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
    if src_w <= 0 or src_h <= 0:
        self._drawing_canvas.setGeometry(0, 0, host.width(), host.height())
        return
    r = self._preview_frame_rect_in_label(int(src_w), int(src_h))
    self._drawing_canvas.setGeometry(r.x(), r.y(), r.width(), r.height())


def moveEvent(self, event) -> None:
    super(type(self), self).moveEvent(event)
    if self.isVisible():
        self._begin_window_move_guard()


def _scale_preview_to_fit(self) -> None:
    if self._preview_pixmap is None or self._preview_pixmap.isNull():
        src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
        if int(src_w or 0) > 0 and int(src_h or 0) > 0:
            self._sync_preview_gl_geometry()
            self._sync_overlay_to_video_rect()
            try:
                self._drawing_canvas.update()
            except Exception:
                pass
        return
    avail = self._preview_label.size()
    if avail.width() <= 0 or avail.height() <= 0:
        return
    frame_rect = self._preview_frame_rect_in_label(
        self._preview_pixmap.width(),
        self._preview_pixmap.height(),
    )
    if frame_rect.width() <= 0 or frame_rect.height() <= 0:
        return
    scaled = self._preview_pixmap.scaled(
        frame_rect.size(),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    # Blend to black by the active fade's multiplier so the preview
    # matches what the exporter produces.
    mult = self._current_fade_multiplier(self._player.position())
    if mult < 0.999:
        faded = QPixmap(scaled.size())
        faded.fill(Qt.GlobalColor.black)
        p = QPainter(faded)
        p.setOpacity(max(0.0, min(1.0, mult)))
        p.drawPixmap(0, 0, scaled)
        p.end()
        scaled = faded
    canvas = QPixmap(avail.width(), avail.height())
    canvas.fill(Qt.GlobalColor.transparent)
    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    x = frame_rect.x() + (frame_rect.width() - scaled.width()) // 2
    y = frame_rect.y() + (frame_rect.height() - scaled.height()) // 2
    frame_rect = QRect(x, y, scaled.width(), scaled.height())
    p.setPen(Qt.PenStyle.NoPen)
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(frame_rect), 8, 8)
    p.setClipPath(clip_path)
    p.drawPixmap(frame_rect.topLeft(), scaled)
    p.setClipping(False)
    p.setPen(QPen(QColor(255, 255, 255, 28), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(frame_rect.adjusted(0, 0, -1, -1), 8, 8)
    p.end()
    self._preview_label.setPixmap(canvas)
    self._sync_overlay_to_video_rect()


def _sync_preview_gl_geometry(self) -> None:
    """Position the GL preview widget exactly where the QLabel
    sits ??same parent, so just mirror the label's geometry. Called
    on host resize and the first frame after a track is loaded."""
    gl = getattr(self, "_preview_gl", None)
    if gl is None:
        return
    lbl = self._preview_label
    src_w, src_h = getattr(self, "_preview_gl_frame_size", (0, 0))
    if int(src_w) > 0 and int(src_h) > 0:
        r = self._preview_frame_rect_in_label(int(src_w), int(src_h))
        gl.setGeometry(lbl.x() + r.x(), lbl.y() + r.y(), r.width(), r.height())
    else:
        gl.setGeometry(lbl.x(), lbl.y(), lbl.width(), lbl.height())
    gl.raise_()
    # Ensure the always-on-top overlays (drawing canvas, subtitle)
    # stay above the GL surface.
    if hasattr(self, "_drawing_canvas"):
        self._drawing_canvas.raise_()
    if hasattr(self, "_subtitle_overlay"):
        self._subtitle_overlay.raise_()
    toast = getattr(self, "_workflow_apply_toast", None)
    if toast is not None:
        try:
            toast.raise_()
        except Exception:
            pass


def _begin_window_move_guard(self) -> None:
    """Keep native titlebar moves responsive by pausing nonessential ticks."""
    if not getattr(self, "_window_move_guard_active", False):
        self._window_move_guard_active = True
        self._window_move_guard_started_at = time.perf_counter()
        stats = {
            "blade_dash": 0,
            "timeline_tool_buttons": 0,
            "preset_tiles": 0,
            "preset_swatches": 0,
            "audio_mixer": 0,
        }
        blade_timer = getattr(self, "_blade_dash_timer", None)
        self._window_move_guard_blade_was_active = bool(
            blade_timer is not None and blade_timer.isActive()
        )
        if self._window_move_guard_blade_was_active:
            blade_timer.stop()
            stats["blade_dash"] = 1
        for btn in self.findChildren(_AnimatedTimelineToolButton):
            try:
                btn.set_animation_suspended(True)
                stats["timeline_tool_buttons"] += 1
            except Exception:
                pass
        for tile in self.findChildren(_StudioPresetTile):
            try:
                tile.set_window_move_suspended(True)
                stats["preset_tiles"] += 1
            except Exception:
                pass
        for swatch in self.findChildren(_PresetPreviewSwatch):
            try:
                swatch.set_window_move_suspended(True)
                stats["preset_swatches"] += 1
            except Exception:
                pass
        mixer_panel = getattr(self, "_audio_mixer_panel", None)
        if mixer_panel is not None and hasattr(mixer_panel, "set_window_move_suspended"):
            try:
                mixer_panel.set_window_move_suspended(True)
                stats["audio_mixer"] = 1
            except Exception:
                pass
        player = getattr(self, "_player", None)
        if player is not None and hasattr(player, "set_window_move_guard"):
            player.set_window_move_guard(True)
        self._window_move_guard_stats = stats
        try:
            _append_ux_event("window.move_guard.begin", **stats)
        except Exception:
            pass
    restore = getattr(self, "_window_move_guard_restore_timer", None)
    if restore is not None:
        restore.start(180)


def _end_window_move_guard(self) -> None:
    if not getattr(self, "_window_move_guard_active", False):
        return
    self._window_move_guard_active = False
    player = getattr(self, "_player", None)
    if player is not None and hasattr(player, "set_window_move_guard"):
        player.set_window_move_guard(False)
    for btn in self.findChildren(_AnimatedTimelineToolButton):
        try:
            btn.set_animation_suspended(False)
        except Exception:
            pass
    for tile in self.findChildren(_StudioPresetTile):
        try:
            tile.set_window_move_suspended(False)
        except Exception:
            pass
    for swatch in self.findChildren(_PresetPreviewSwatch):
        try:
            swatch.set_window_move_suspended(False)
        except Exception:
            pass
    mixer_panel = getattr(self, "_audio_mixer_panel", None)
    if mixer_panel is not None and hasattr(mixer_panel, "set_window_move_suspended"):
        try:
            mixer_panel.set_window_move_suspended(False)
        except Exception:
            pass
    blade_timer = getattr(self, "_blade_dash_timer", None)
    if (
        getattr(self, "_window_move_guard_blade_was_active", False)
        and blade_timer is not None
        and not blade_timer.isActive()
    ):
        blade_timer.start()
    elapsed_ms = 0
    try:
        elapsed_ms = int(round((time.perf_counter() - self._window_move_guard_started_at) * 1000.0))
    except Exception:
        elapsed_ms = 0
    try:
        _append_ux_event(
            "window.move_guard.end",
            elapsed_ms=elapsed_ms,
            **(getattr(self, "_window_move_guard_stats", {}) or {}),
        )
    except Exception:
        pass
    self._window_move_guard_blade_was_active = False
    self._window_move_guard_stats = {}


def resizeEvent(self, event) -> None:
    super(type(self), self).resizeEvent(event)
    self._refresh_command_bar_responsive()
    self._scale_preview_to_fit()
    if (
        self._preview_pixmap is None
        and hasattr(self, "_preview_placeholder_kind")
        and not self._preview_has_renderable_content()
    ):
        self._preview_label.setPixmap(
            self._draw_preview_placeholder(self._preview_placeholder_kind)
        )
    elif self._preview_has_renderable_content():
        self._clear_preview_placeholder()
    if self._subtitle_overlay.isVisible():
        self._reposition_subtitle_overlay()
    self._sync_overlay_to_video_rect()
    self._sync_color_power_window_overlay()
    self._sync_preview_gl_geometry()
    self._resync_bubbles_to_preview()
    self._resync_stickers_to_preview()
    overlay_payload = getattr(self, "_preset_preview_overlay_payload", None)
    if isinstance(overlay_payload, dict):
        self._show_preset_overlay_preview(
            str(overlay_payload.get("kind", "")),
            dict(overlay_payload.get("payload", {}) or {}),
            str(overlay_payload.get("label", "")),
        )
    # Re-layout the active text clip overlay on canvas resize.
    if hasattr(self, "_text_track"):
        self._update_text_clip_overlay(self._player.position())
    # Timeline stretches to viewport width too
    if hasattr(self, "_tracks_scroll"):
        self._update_tracks_host_width()

