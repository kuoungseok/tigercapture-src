from __future__ import annotations


def _refresh_preview_soft(self, track=None) -> None:
    if track is not None:
        row = getattr(self, "_track_rows", {}).get(getattr(track, "id", None))
        if row is not None:
            row.update()
    try:
        self._player.refresh_current_frame()
    except Exception:
        pass

import os
from time import monotonic

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from app.video_editor_color_widgets import apply_lut


def _preview_cpu_frame_consumers_active(self) -> bool:
    """Return True when a live CPU QImage preview is currently required."""
    if getattr(self, "_preview_popout", None) is not None:
        return True
    cpw = getattr(self, "_color_page_window", None)
    if cpw is not None and cpw.isVisible():
        return True
    return False


def _preview_qimage_primary_active(self) -> bool:
    mode = os.environ.get("TIGERCAPTURE_PREVIEW_QIMAGE", "auto").strip().lower()
    if mode in {"1", "true", "yes", "on", "always"}:
        return True
    if mode in {"0", "false", "no", "off", "never"}:
        return False
    if bool(getattr(self, "_preview_gl_overlay_required", False)):
        return False
    return self._preview_cpu_frame_consumers_active()


def _refresh_preview_qimage_mode(self) -> None:
    """Keep ProjectPlayer's QImage signal on only for active CPU consumers.

    ``TIGERCAPTURE_PREVIEW_QIMAGE`` accepts ``1/on/true`` to force the
    legacy CPU path on, ``0/off/false`` to force it off, and defaults to
    auto. Auto keeps QImage enabled until the GL surface has accepted a
    frame, then disables it unless popout/scopes-style consumers need it.
    """
    player = getattr(self, "_player", None)
    if player is None or not hasattr(player, "set_qimage_frame_enabled"):
        return
    mode = os.environ.get("TIGERCAPTURE_PREVIEW_QIMAGE", "auto").strip().lower()
    if mode in {"1", "true", "yes", "on", "always"}:
        enabled = True
    elif mode in {"0", "false", "no", "off", "never"}:
        enabled = False
    else:
        gl = getattr(self, "_preview_gl", None)
        frame_w, frame_h = getattr(self, "_preview_gl_frame_size", (0, 0))
        gpu_ready = (
            gl is not None
            and gl.isVisible()
            and int(frame_w) > 0
            and int(frame_h) > 0
        )
        overlay_required = bool(getattr(self, "_preview_gl_overlay_required", False))
        enabled = ((not gpu_ready) and not overlay_required) or self._preview_cpu_frame_consumers_active()
    try:
        player.set_qimage_frame_enabled(enabled)
    except Exception:
        pass


def _latest_preview_qimage(self) -> QImage | None:
    rgb = self._current_preview_rgb()
    if rgb is None:
        return None
    return self._qimage_from_preview_rgb(rgb)


@staticmethod
def _qimage_from_preview_rgb(rgb) -> QImage | None:
    """Convert a cached preview RGB array into an owning QImage copy."""
    try:
        import numpy as np

        arr = np.asarray(rgb)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return None
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        arr = np.ascontiguousarray(arr[:, :, :3])
        h, w = arr.shape[:2]
        return QImage(
            arr.data, w, h, arr.strides[0], QImage.Format.Format_RGB888
        ).copy()
    except Exception:
        return None


def _on_frame_ready(self, qimg: QImage) -> None:
    # In audio-only projects the player still ticks (so AudioMixer
    # stays synced) and emits blank frames. Don't clobber the
    # "???Sound only" placeholder in that case.
    has_video = any(
        t.source_path is not None or bool(t.clips)
        for t in self._tracks
    )
    has_actor = any(
        bool(getattr(t, "clips", None) or [])
        for t in getattr(self, "_live2d_actor_tracks", []) or []
    ) or any(
        bool(getattr(t, "clips", None) or [])
        for t in getattr(self, "_spine_actor_tracks", []) or []
    ) or bool(getattr(self, "_ar_pbr_tracks", []) or []) or bool(getattr(self, "_mmd_tracks", []) or [])
    if not (has_video or has_actor):
        return
    self._clear_preview_placeholder()
    # Apply 3D LUT if one is loaded.
    if self._lut_data is not None:
        try:
            import numpy as np
            _qimg_lut = qimg.convertToFormat(QImage.Format.Format_RGB888)
            _ptr = _qimg_lut.constBits()
            _arr = np.frombuffer(_ptr, dtype=np.uint8).reshape(
                _qimg_lut.height(), _qimg_lut.width(), 3
            ).copy()
            _arr = apply_lut(_arr, self._lut_data, self._lut_strength)
            _h, _w = _arr.shape[:2]
            qimg = QImage(
                _arr.tobytes(), _w, _h, _w * 3, QImage.Format.Format_RGB888
            ).copy()
        except Exception:
            pass
    # Keep the clean original in _preview_pixmap so PaintDialog sees the
    # real frame; fade is applied only to the displayed scaled copy
    # inside _scale_preview_to_fit.
    if self._preview_qimage_primary_active() and not bool(getattr(self, "_preview_gl_overlay_required", False)):
        gl = getattr(self, "_preview_gl", None)
        if gl is not None and gl.isVisible():
            try:
                gl.hide()
            except Exception:
                pass
    self._preview_pixmap = QPixmap.fromImage(qimg)
    if self._preview_tab_guard_active():
        self._restore_preview_if_tab_switch_blank()
    else:
        self._remember_good_preview_pixmap()
    self._scale_preview_to_fit()
    self._remember_good_preview_pixmap()
    self._refresh_preview_qimage_mode()
    self._update_subtitle_overlay(self._player.position())
    # Drawing canvas + subtitle overlay sit above both the QLabel
    # and the GL preview surface. Raise them every frame so any
    # auto-stacking from Qt doesn't put them behind.
    self._drawing_canvas.raise_()
    self._subtitle_overlay.raise_()
    self._drawing_canvas.update()
    # Mirror the frame to the pop-out window when one is open.
    if self._preview_popout is not None:
        try:
            self._preview_popout.update_frame(qimg)
        except Exception:
            pass
    # DaVinci-style live node thumbnails ??push the latest frame
    # to the workbench's NodeGraph at ~10 Hz. Skip when the player
    # is in a black/blank region (no active clip at current position)
    # so clip deletions don't wipe out the node thumbnails.
    pos = self._player.position()
    _has_active = any(
        int(c.timeline_in_ms) <= pos <= int(c.timeline_out_ms)
        for t in self._tracks
        for c in getattr(t, "clips", [])
        if getattr(c, "source_path", None) is not None
    )
    if not _has_active:
        return
    from time import monotonic
    now_ms = monotonic() * 1000.0
    last_ms = getattr(self, "_last_node_thumb_ms", 0.0)
    if now_ms - last_ms >= 100.0:
        self._last_node_thumb_ms = now_ms
        wb = getattr(self, "_workbench_panel", None)
        if wb is not None and self._preview_pixmap is not None:
            try:
                wb.set_node_thumbnail(self._preview_pixmap)
            except Exception:
                pass


def _ensure_preview_gl(self):
    gl = getattr(self, "_preview_gl", None)
    if gl is not None:
        return gl
    host = getattr(self, "_preview_host", None)
    if host is None:
        return None
    try:
        from app.opengl_preview import OpenGLPreviewWidget

        gl = OpenGLPreviewWidget(host)
        try:
            gl.spine_overlay_failed.connect(self._on_spine_gpu_overlay_failed)
        except Exception:
            pass
        gl.setAcceptDrops(True)
        gl.installEventFilter(self)
        gl.setCursor(Qt.CursorShape.PointingHandCursor)
        gl.hide()
        self._preview_gl = gl
        return gl
    except Exception:
        self._preview_gl = None
        return None


def _on_gpu_frame_ready(self, rgb, grade) -> None:
    """Hand the raw RGB ndarray + optional ColorGrade to the OpenGL
    preview surface.

    ``grade`` is either a ``ColorGrade`` object (passed directly from
    ProjectPlayer for GPU shader grading) or ``None`` (frame is already
    fully composited CPU-side).  Legacy dict hints are also handled for
    backwards compatibility.
    """
    if rgb is None:
        return
    try:
        h, w = rgb.shape[:2]
        self._preview_gl_frame_size = (int(w), int(h))
    except Exception:
        pass
    self._clear_preview_placeholder()

    # Resolve the grade object: accept ColorGrade directly or from a
    # legacy hint dict (the blur_sigma hint path has been removed).
    _real_grade = grade
    _spine_items = []
    _ar_pbr_items = []
    _mmd_items = []
    _clip_effects = None
    if isinstance(grade, dict):
        _real_grade = grade.get("grade", None)
        _spine_items = list(grade.get("spine_items") or [])
        _ar_pbr_items = list(grade.get("ar_pbr_items") or [])
        _mmd_items = list(grade.get("mmd_items") or [])
        _clip_effects = grade.get("clip_effects")
    _overlay_required = bool(_spine_items or _ar_pbr_items or _mmd_items)
    self._preview_gl_overlay_required = _overlay_required

    if self._preview_qimage_primary_active() and not _overlay_required:
        gl_existing = getattr(self, "_preview_gl", None)
        if gl_existing is not None and gl_existing.isVisible():
            try:
                gl_existing.hide()
            except Exception:
                pass
        return
    gl = self._ensure_preview_gl()
    if gl is None:
        return
    if not gl.isVisible():
        gl.show()
        self._sync_preview_gl_geometry()
    gl.set_blur(0.0)  # blur is CPU-applied; shader blur is disabled
    if hasattr(gl, "set_clip_effects"):
        try:
            gl.set_clip_effects(_clip_effects)
        except Exception:
            pass
    if hasattr(gl, "set_spine_overlay_items"):
        try:
            gl.set_spine_overlay_items(_spine_items)
        except Exception:
            pass
    if hasattr(gl, "set_ar_pbr_overlay_items"):
        try:
            gl.set_ar_pbr_overlay_items(_ar_pbr_items)
        except Exception:
            pass
    if hasattr(gl, "set_mmd_overlay_items"):
        try:
            gl.set_mmd_overlay_items(_mmd_items)
        except Exception:
            pass

    # Apply 3D LUT using precomputed cache (fast array indexing)
    _lut_cache = getattr(self, "_lut_cache", None)
    if _lut_cache is not None:
        try:
            import numpy as _np
            lut_strength = getattr(self, "_lut_strength", 1.0)
            _is_float = rgb.dtype in (_np.float32, _np.float64)
            _max_1 = _is_float and float(rgb.max()) <= 1.01
            if _is_float:
                rgb_u8 = _np.clip(rgb * (255 if _max_1 else 1), 0, 255).astype(_np.uint8)
            else:
                rgb_u8 = _np.asarray(rgb, dtype=_np.uint8)
            # Fast lookup: cache[r, g, b] ??new [r, g, b]
            r, g, b = rgb_u8[:,:,0], rgb_u8[:,:,1], rgb_u8[:,:,2]
            lut_out = _lut_cache[r, g, b]  # shape (H, W, 3)
            if lut_strength < 1.0:
                lut_out = (rgb_u8 * (1 - lut_strength) + lut_out * lut_strength).astype(_np.uint8)
            if _is_float:
                rgb = lut_out.astype(rgb.dtype) / (255.0 if _max_1 else 1.0)
            else:
                rgb = lut_out
        except Exception:
            pass
    if (
        self._preview_tab_guard_active()
        and self._active_renderable_clip_at_current_position()
        and self._rgb_looks_like_blank_preview(rgb)
    ):
        last_rgb = getattr(self, "_last_good_preview_rgb", None)
        if last_rgb is not None and not self._rgb_looks_like_blank_preview(last_rgb):
            try:
                import numpy as _np
                rgb = _np.ascontiguousarray(last_rgb)
            except Exception:
                rgb = last_rgb
    try:
        import numpy as _np
        self._latest_preview_rgb = _np.ascontiguousarray(rgb)
        if (
            self._active_renderable_clip_at_current_position()
            and not self._rgb_looks_like_blank_preview(rgb)
        ):
            self._last_good_preview_rgb = _np.ascontiguousarray(rgb).copy()
    except Exception:
        self._latest_preview_rgb = rgb
        if (
            self._active_renderable_clip_at_current_position()
            and not self._rgb_looks_like_blank_preview(rgb)
        ):
            self._last_good_preview_rgb = rgb
    if self._preview_popout is not None:
        try:
            qimg = self._qimage_from_preview_rgb(rgb)
            if qimg is not None and not qimg.isNull():
                self._preview_popout.update_frame(qimg)
        except Exception:
            pass
    feeder = getattr(self, "_feed_broadcast_output_frame", None)
    if callable(feeder):
        feeder(rgb)
    gl.update_frame(rgb, _real_grade)
    # The GL surface is a child over the QLabel.  Clear the label again
    # after the GL update so a stale "Start your edit" pixmap cannot stay
    # visible behind a smaller GL frame.
    self._clear_preview_placeholder()
    self._sync_overlay_to_video_rect()
    self._sync_color_power_window_overlay()
    self._update_subtitle_overlay(self._player.position())
    try:
        self._drawing_canvas.raise_()
        self._subtitle_overlay.raise_()
        self._drawing_canvas.update()
    except Exception:
        pass
    self._refresh_preview_qimage_mode()

    # Forward live frame + grade to the Color Page window when open.
    cpw = getattr(self, "_color_page_window", None)
    if cpw is not None and cpw.isVisible():
        try:
            cpw.update_frame(rgb, _real_grade)
        except Exception:
            pass


def _on_spine_gpu_overlay_failed(self, reason: str = "") -> None:
    player = getattr(self, "_player", None)
    if player is None or not hasattr(player, "set_spine_gpu_overlay_enabled"):
        return
    try:
        player.set_spine_gpu_overlay_enabled(False)
        player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._flash_status(str(reason or "Spine GPU overlay fallback: CPU preview"))
    except Exception:
        pass
