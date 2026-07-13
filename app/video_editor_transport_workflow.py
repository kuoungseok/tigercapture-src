from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from app.i18n import tr
from app.simple_video_player import PlayerState
from app.video_editor_popouts import PreviewPopoutWindow


def _format_ms(ms: int) -> str:
    total = max(0, int(ms)) // 1000
    m, s = divmod(total, 60)
    return f"{m}:{s:02d}"


def _ms_to_timecode(ms: int) -> str:
    total_s = ms // 1000
    mm = total_s // 60
    ss = total_s % 60
    ff = (ms % 1000) // 10
    return f"{mm:02d}:{ss:02d}:{ff:02d}"


def _toggle_play(self) -> None:
    if self._player.state() is PlayerState.PLAYING:
        self._player.pause()
        return
    self._ensure_playback_rate_for_play()
    audition = self._clip_audition_range()
    if audition is None:
        self._player.play()
        return
    start, end, restore = audition
    if start != restore:
        self._player.set_position(start)
    play_until = getattr(self._player, "play_until", None)
    if callable(play_until):
        play_until(end, return_to_ms=restore)
        flash = getattr(self, "_flash_status", None)
        if callable(flash):
            flash(f"Audition range {_format_ms(start)}-{_format_ms(end)}; returns to playhead")
    else:
        self._player.play()


def _stop_transport(self) -> None:
    player = getattr(self, "_player", None)
    if player is None:
        return
    if hasattr(player, "set_shuttle_rate"):
        player.set_shuttle_rate(1.0)
    self._jkl_transport_rate = 1.0
    if hasattr(player, "stop"):
        player.stop()
    elif hasattr(player, "pause"):
        player.pause()
    self._set_transport_speed_label(1.0)


def _ensure_playback_rate_for_play(self) -> None:
    """Normalize J/K/L shuttle state before a plain Play action."""
    try:
        rate = float(getattr(self, "_jkl_transport_rate", 0.0) or 0.0)
    except Exception:
        rate = 0.0
    if rate > 0.0:
        return
    player = getattr(self, "_player", None)
    self._jkl_transport_rate = 1.0
    if player is not None and hasattr(player, "set_shuttle_rate"):
        try:
            player.set_shuttle_rate(1.0)
        except Exception:
            pass
    self._set_transport_speed_label(1.0)


def _on_jog_delta(self, frames: int) -> None:
    """Inner ring rotated ??advance the playhead by ``frames``
    frames (signed). Uses ``REFERENCE_FPS = 30`` like the rest of
    the player so each jog tick is ~33 ms ??matches the visual
    granularity of the timeline ruler at default zoom."""
    if not self._tracks:
        return
    ms_per_frame = 1000.0 / 30.0  # ProjectPlayer.REFERENCE_FPS
    new_pos = self._player.position() + int(round(frames * ms_per_frame))
    self._player.set_position(new_pos)


def _on_shuttle_speed_changed(self, speed: float) -> None:
    """Outer ring rotated ??set the player's shuttle rate. ``0``
    pauses; positive values resume play at that multiplier;
    negative values clamp to pause until the player gains reverse
    playback support."""
    self._player.set_shuttle_rate(speed)
    self._jkl_transport_rate = float(speed) if speed > 0.0 else 0.0
    self._set_transport_speed_label(self._jkl_transport_rate)
    state_attr = getattr(self._player, "state", None)
    state = state_attr() if callable(state_attr) else state_attr
    if speed <= 0.0:
        self._player.pause()
    elif state is not PlayerState.PLAYING:
        self._player.play()


def _next_jkl_rate(current_rate: float) -> float:
    steps = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
    try:
        current = abs(float(current_rate))
    except Exception:
        current = 0.0
    for step in steps:
        if current < step - 1e-6:
            return step
    return steps[-1]


def _jkl_reverse_jog_ms(rate: float) -> int:
    try:
        magnitude = abs(float(rate))
    except Exception:
        magnitude = 1.0
    return int(round(1000.0 * max(1.0, min(32.0, magnitude))))


def _set_transport_speed_label(self, rate: float) -> None:
    label = getattr(self, "current_speed_label", None)
    if label is None:
        return
    try:
        value = float(rate)
    except Exception:
        value = 0.0
    label.setText(f"{value:g}x")
    if hasattr(label, "setToolTip"):
        label.setToolTip(f"{tr('veditor.current_speed', speed=f'{value:g}')} - click for speed menu")
    popout = getattr(self, "_preview_popout", None)
    if popout is not None and hasattr(popout, "set_speed_label"):
        try:
            popout.set_speed_label(value)
        except Exception:
            pass


def _show_viewer_speed_menu(self) -> None:
    button = getattr(self, "current_speed_label", None)
    if button is None:
        return
    menu = QMenu(self)
    menu.addSection("Playback speed")
    rates = (0.25, 0.5, 1.0, 1.5, 2.0, 4.0, 8.0, 16.0)
    current = float(getattr(self, "_jkl_transport_rate", 0.0) or 0.0)
    if current <= 0.0:
        current = 1.0
    for rate in rates:
        act = menu.addAction(f"{rate:g}x")
        act.setCheckable(True)
        act.setChecked(abs(current - rate) < 1e-6)
        act.triggered.connect(lambda _checked=False, r=rate: self._set_viewer_playback_rate(r))
    menu.addSeparator()
    pause_act = menu.addAction("Pause")
    pause_act.triggered.connect(lambda _checked=False: self._apply_jkl_transport("k"))
    try:
        menu.exec(button.mapToGlobal(QPoint(0, button.height())))
    except Exception:
        menu.exec(QCursor.pos())


def _set_viewer_playback_rate(self, rate: float) -> None:
    try:
        rate = max(0.25, min(16.0, float(rate)))
    except Exception:
        rate = 1.0
    player = getattr(self, "_player", None)
    self._jkl_transport_rate = rate
    if player is not None and hasattr(player, "set_shuttle_rate"):
        player.set_shuttle_rate(rate)
    self._set_transport_speed_label(rate)
    try:
        self._flash_status(f"Playback speed {rate:g}x")
    except Exception:
        pass


def _fit_viewer_preview_from_button(self) -> None:
    fit = getattr(self, "_scale_preview_to_fit", None)
    if callable(fit):
        fit()
    sync_gl = getattr(self, "_sync_preview_gl_geometry", None)
    if callable(sync_gl):
        try:
            sync_gl()
        except Exception:
            pass
    gl = getattr(self, "_preview_gl", None)
    if gl is not None:
        try:
            gl.update()
        except Exception:
            pass
    canvas = getattr(self, "_drawing_canvas", None)
    if canvas is not None:
        try:
            canvas.update()
        except Exception:
            pass
    popout = getattr(self, "_preview_popout", None)
    fit_popout = getattr(popout, "fit_to_view", None) if popout is not None else None
    if callable(fit_popout):
        try:
            fit_popout()
        except Exception:
            pass
    try:
        self._flash_status("Viewer fit applied")
    except Exception:
        pass


def _show_viewer_compare_menu(self) -> None:
    button = getattr(self, "viewer_compare_btn", None)
    if button is None:
        return
    track = self._active_track() if hasattr(self, "_active_track") else None
    mode = str(getattr(track, "preview_color_compare_mode", "") or "").casefold()
    labels_enabled = bool(getattr(track, "preview_compare_labels_enabled", True))
    menu = QMenu(self)
    off_act = menu.addAction("Off")
    off_act.setCheckable(True)
    off_act.setChecked(mode == "")
    off_act.triggered.connect(lambda _checked=False: self._set_viewer_compare_mode(""))
    split_act = menu.addAction("Before / After Split")
    split_act.setCheckable(True)
    split_act.setChecked(mode == "split")
    split_act.triggered.connect(lambda _checked=False: self._set_viewer_compare_mode("split"))
    wipe_act = menu.addAction("Wipe Reveal")
    wipe_act.setCheckable(True)
    wipe_act.setChecked(mode == "split")
    wipe_act.triggered.connect(lambda _checked=False: self._set_viewer_compare_mode("split"))
    before_act = menu.addAction("Original Only")
    before_act.setCheckable(True)
    before_act.setChecked(mode == "before")
    before_act.triggered.connect(lambda _checked=False: self._set_viewer_compare_mode("before"))
    menu.addSeparator()
    label_act = menu.addAction("Show Before | After labels")
    label_act.setCheckable(True)
    label_act.setChecked(labels_enabled)
    label_act.triggered.connect(lambda checked=False: self._set_viewer_compare_labels_enabled(bool(checked)))
    try:
        menu.exec(button.mapToGlobal(QPoint(0, button.height())))
    except Exception:
        menu.exec(QCursor.pos())


def _set_viewer_compare_mode(self, mode: str) -> None:
    track = self._active_track() if hasattr(self, "_active_track") else None
    if track is None:
        return
    wanted = str(mode or "").casefold()
    if wanted not in {"before", "split"}:
        wanted = ""
    try:
        setattr(track, "preview_color_compare_mode", wanted)
        if not hasattr(track, "preview_compare_labels_enabled"):
            setattr(track, "preview_compare_labels_enabled", True)
    except Exception:
        pass
    self._sync_color_compare_buttons()
    self._sync_viewer_compare_button()
    try:
        if hasattr(self._player, "clear_preview_prerender_cache"):
            self._player.clear_preview_prerender_cache()
        self._player.refresh_current_frame()
    except Exception:
        pass
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    try:
        label = "Comparison off" if not wanted else "Comparison: Before | After"
        self._flash_status(label)
    except Exception:
        pass


def _set_viewer_compare_labels_enabled(self, enabled: bool) -> None:
    track = self._active_track() if hasattr(self, "_active_track") else None
    if track is None:
        return
    try:
        setattr(track, "preview_compare_labels_enabled", bool(enabled))
    except Exception:
        pass
    self._sync_viewer_compare_button()
    try:
        self._drawing_canvas.update()
    except Exception:
        pass


def _sync_viewer_compare_button(self) -> None:
    button = getattr(self, "viewer_compare_btn", None)
    if button is None:
        return
    track = self._active_track() if hasattr(self, "_active_track") else None
    mode = str(getattr(track, "preview_color_compare_mode", "") or "").casefold()
    if mode == "split":
        text = "Split"
        tip = "Comparison Templates: Before | After split"
    elif mode == "before":
        text = "Before"
        tip = "Comparison Templates: Before preview"
    else:
        text = "Compare"
        tip = "Comparison Templates"
    try:
        button.setText(text)
        button.setToolTip(tip)
        button.setProperty("active", bool(mode))
        button.style().unpolish(button)
        button.style().polish(button)
    except Exception:
        pass


def _sync_ar_pbr_depth_view_button(self) -> None:
    button = getattr(self, "viewer_depth_btn", None)
    if button is None:
        return
    player = getattr(self, "_player", None)
    mode = "off"
    getter = getattr(player, "ar_pbr_depth_view_mode", None) if player is not None else None
    if callable(getter):
        try:
            mode = str(getter() or "off")
        except Exception:
            mode = "off"
    try:
        button.blockSignals(True)
        button.setChecked(mode != "off")
        try:
            button.setText(_depth_view_button_text(mode))
        except Exception:
            pass
        button.setToolTip(
            "Show AR/PBR depth matte"
            if mode == "off"
            else f"Depth view: {_depth_view_button_label(mode)}; click to cycle Matte / Distance / Plane / Off"
        )
        button.setProperty("active", mode != "off")
        button.style().unpolish(button)
        button.style().polish(button)
    except Exception:
        pass
    finally:
        try:
            button.blockSignals(False)
        except Exception:
            pass


def _toggle_ar_pbr_depth_view(self, checked: bool = False) -> None:
    del checked
    player = getattr(self, "_player", None)
    if player is None:
        return
    mode = _next_depth_view_mode("off")
    getter = getattr(player, "ar_pbr_depth_view_mode", None)
    if callable(getter):
        try:
            mode = _next_depth_view_mode(str(getter() or "off"))
        except Exception:
            mode = "matte"
    setter = getattr(player, "set_ar_pbr_depth_view_mode", None)
    if callable(setter):
        try:
            mode = str(setter(mode) or mode)
        except Exception:
            mode = "off"
    else:
        try:
            setattr(player, "_ar_pbr_depth_view_mode_value", mode)
            setattr(player, "_last_preview_frame_cache", None)
        except Exception:
            pass
    try:
        clear = getattr(player, "clear_preview_prerender_cache", None)
        if callable(clear):
            clear()
    except Exception:
        pass
    try:
        refresh = getattr(player, "refresh_current_frame", None)
        if callable(refresh):
            refresh()
    except Exception:
        pass
    self._sync_ar_pbr_depth_view_button()
    try:
        self._drawing_canvas.update()
    except Exception:
        pass
    try:
        self._flash_status(
            f"Depth view: {_depth_view_button_label(mode)}"
            if mode != "off"
            else "Depth view off"
        )
    except Exception:
        pass


def _next_depth_view_mode(current: str) -> str:
    from app.ar_pbr.depth_view import normalize_depth_view_mode

    mode = normalize_depth_view_mode(current)
    if mode == "off":
        return "matte"
    if mode == "matte":
        return "distance"
    if mode == "distance":
        return "plane"
    return "off"


def _depth_view_button_text(mode: str) -> str:
    from app.ar_pbr.depth_view import normalize_depth_view_mode

    canonical = normalize_depth_view_mode(mode)
    if canonical == "off":
        return "Depth"
    if canonical == "distance":
        return "Dist"
    if canonical == "plane":
        return "Plane"
    if canonical == "heat":
        return "Heat"
    return "Matte"


def _depth_view_button_label(mode: str) -> str:
    from app.ar_pbr.depth_view import normalize_depth_view_mode

    canonical = normalize_depth_view_mode(mode)
    labels = {
        "off": "Off",
        "matte": "Matte",
        "distance": "Distance",
        "plane": "Plane",
        "heat": "Heat",
        "inverted_grayscale": "Inverted",
    }
    return labels.get(canonical, canonical)


def _apply_jkl_transport(self, command: str) -> bool:
    is_text_focus = getattr(self, "_is_text_focus", None)
    if callable(is_text_focus) and is_text_focus():
        return False
    player = getattr(self, "_player", None)
    if player is None:
        return False
    cmd = str(command or "").lower()
    flash = getattr(self, "_flash_status", None)

    if cmd == "k":
        self._jkl_transport_rate = 0.0
        if hasattr(player, "set_shuttle_rate"):
            player.set_shuttle_rate(0.0)
        if hasattr(player, "pause"):
            player.pause()
        _set_transport_speed_label(self, 0.0)
        if callable(flash):
            flash("Shuttle pause")
        return True

    if cmd == "l":
        current = float(getattr(self, "_jkl_transport_rate", 0.0) or 0.0)
        rate = 1.0 if current <= 0.0 else _next_jkl_rate(current)
        self._jkl_transport_rate = rate
        if hasattr(player, "set_shuttle_rate"):
            player.set_shuttle_rate(rate)
        if hasattr(player, "play"):
            player.play()
        _set_transport_speed_label(self, rate)
        if callable(flash):
            flash(f"Shuttle forward {rate:g}x")
        return True

    if cmd == "j":
        current = float(getattr(self, "_jkl_transport_rate", 0.0) or 0.0)
        magnitude = (
            _next_jkl_rate(abs(current))
            if current < 0.0
            else 1.0
        )
        rate = -magnitude
        self._jkl_transport_rate = rate
        if hasattr(player, "set_shuttle_rate"):
            player.set_shuttle_rate(0.0)
        if hasattr(player, "pause"):
            player.pause()
        current_pos = int(player.position()) if hasattr(player, "position") else 0
        duration = int(player.duration()) if hasattr(player, "duration") else current_pos
        new_pos = _bounded_seek_position(
            current_pos,
            -_jkl_reverse_jog_ms(rate),
            duration,
        )
        if hasattr(player, "set_position"):
            player.set_position(new_pos)
        ensure_visible = getattr(self, "_ensure_playhead_visible", None)
        if callable(ensure_visible):
            ensure_visible()
        _set_transport_speed_label(self, rate)
        if callable(flash):
            flash(f"Reverse jog {rate:g}x")
        return True

    return False


def _step_timeline_frames(self, frames: int) -> bool:
    is_text_focus = getattr(self, "_is_text_focus", None)
    if callable(is_text_focus) and is_text_focus():
        return False
    player = getattr(self, "_player", None)
    if player is None or not hasattr(player, "set_position"):
        return False
    try:
        frame_count = int(frames)
    except Exception:
        frame_count = 0
    if frame_count == 0:
        return False

    if hasattr(player, "set_shuttle_rate"):
        player.set_shuttle_rate(0.0)
    if hasattr(player, "pause"):
        player.pause()
    self._jkl_transport_rate = 0.0

    settings = getattr(self, "_project_settings", {}) or {}
    delta_ms = frame_count * _timeline_frame_ms(settings)
    current = int(player.position()) if hasattr(player, "position") else 0
    duration = int(player.duration()) if hasattr(player, "duration") else current
    target = _bounded_seek_position(current, delta_ms, duration)
    player.set_position(target)
    ensure_visible = getattr(self, "_ensure_playhead_visible", None)
    if callable(ensure_visible):
        ensure_visible()
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        sign = "+" if frame_count > 0 else "-"
        flash(f"Frame step {sign}{abs(frame_count)}")
    return True


def _toggle_preview_popout(self) -> None:
    """Open a separate top-level preview window (for multi-monitor
    full-screen viewing), or close it and return focus here."""
    if self._preview_popout is not None:
        self._preview_popout.close()
        return
    popout = PreviewPopoutWindow()
    popout.closed.connect(self._on_preview_popout_closed)
    popout.toggle_play_requested.connect(self._toggle_play)
    popout.dock_requested.connect(popout.close)
    popout.stop_requested.connect(self._stop_transport)
    popout.prev_frame_requested.connect(lambda: self._step_timeline_frames(-1))
    popout.next_frame_requested.connect(lambda: self._step_timeline_frames(1))
    popout.mark_in_requested.connect(self._mark_in_at_playhead)
    popout.mark_out_requested.connect(self._mark_out_at_playhead)
    popout.clear_range_requested.connect(self._clear_active_selection)
    popout.marker_requested.connect(self._add_marker_at_playhead)
    popout.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    # Seed the popout with the latest frame if one is cached, so
    # users don't see a black box until the next tick.
    if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
        popout.update_frame(self._preview_pixmap.toImage())
    else:
        latest_qimg = self._latest_preview_qimage()
        if latest_qimg is not None:
            popout.update_frame(latest_qimg)
    popout.show()
    try:
        popout.set_playing(self._player.state() is PlayerState.PLAYING)
    except Exception:
        pass
    try:
        popout.set_time_text(self.time_label.text())
        popout.set_speed_label(self.current_speed_label.text())
    except Exception:
        pass
    self._preview_popout = popout
    self._refresh_preview_popout_overlay_hooks()
    self._refresh_preview_qimage_mode()
    self.popout_btn.setProperty("popped", True)
    self.popout_btn.setToolTip(tr("veditor.popout.tooltip_docked"))
    self.popout_btn.style().unpolish(self.popout_btn)
    self.popout_btn.style().polish(self.popout_btn)


def _on_preview_popout_closed(self) -> None:
    self._preview_popout = None
    self._refresh_preview_qimage_mode()
    self.popout_btn.setProperty("popped", False)
    self.popout_btn.setToolTip(tr("veditor.popout.tooltip"))
    self.popout_btn.style().unpolish(self.popout_btn)
    self.popout_btn.style().polish(self.popout_btn)


def _timeline_frame_ms(settings: dict | None = None) -> int:
    settings = settings or {}
    try:
        fps = float(settings.get("fps") or 30.0)
    except Exception:
        fps = 30.0
    return max(1, int(round(1000.0 / max(1.0, fps))))


def _bounded_seek_position(current_ms: int, delta_ms: int, project_duration_ms: int) -> int:
    duration = max(0, int(project_duration_ms))
    return max(0, min(duration, int(current_ms) + int(delta_ms)))
