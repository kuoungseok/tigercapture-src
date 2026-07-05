from __future__ import annotations

from app.project_player import _interpolate_pip_params


def _active_pip_track(self):
    active_id = getattr(self, "_active_track_id", None)
    if active_id is None:
        return None
    return self._find_track(active_id)


def _pip_sliders(self):
    return (
        (self._pip_x_slider, "pip_x", 100.0),
        (self._pip_y_slider, "pip_y", 100.0),
        (self._pip_scale_slider, "pip_scale", 100.0),
        (self._pip_opacity_slider, "pip_opacity", 100.0),
    )


def _refresh_pip_panel(self) -> None:
    """Show / populate the PIP panel when a non-bottom track is active."""
    if not hasattr(self, "_pip_section_host"):
        return
    track = _active_pip_track(self)
    track_idx = self._tracks.index(track) if track is not None and track in self._tracks else -1
    visible = (track is not None) and (track_idx > 0)
    self._pip_section_host.setVisible(visible)
    if not visible:
        return

    for slider, attr, scale in _pip_sliders(self):
        slider.blockSignals(True)
        default = 0.5 if attr in ("pip_x", "pip_y") else 0.3 if attr == "pip_scale" else 1.0
        value = int(round(float(getattr(track, attr, default)) * scale))
        slider.setValue(value)
        slider.blockSignals(False)
    self._pip_x_val.setText(str(self._pip_x_slider.value()))
    self._pip_y_val.setText(str(self._pip_y_slider.value()))
    self._pip_scale_val.setText(str(self._pip_scale_slider.value()))
    self._pip_opacity_val.setText(str(self._pip_opacity_slider.value()))
    self._pip_enable_btn.blockSignals(True)
    self._pip_enable_btn.setChecked(bool(getattr(track, "pip_enabled", False)))
    self._pip_enable_btn.blockSignals(False)

    pip_on = bool(getattr(track, "pip_enabled", False))
    for slider in (
        self._pip_x_slider,
        self._pip_y_slider,
        self._pip_scale_slider,
        self._pip_opacity_slider,
    ):
        slider.setEnabled(pip_on)
    _refresh_pip_kf_list(self, track)


def _sync_pip_sliders_to_position(self, pos_ms: int) -> None:
    """Update PIP sliders to show interpolated values at the current playhead."""
    if not hasattr(self, "_pip_x_slider"):
        return
    track = _active_pip_track(self)
    if track is None or not getattr(track, "pip_enabled", False):
        return
    kfs = getattr(track, "pip_keyframes", [])
    if not kfs:
        return
    x, y, scale, opacity = _interpolate_pip_params(kfs, pos_ms, track)
    for slider, value in (
        (self._pip_x_slider, x),
        (self._pip_y_slider, y),
        (self._pip_scale_slider, scale),
        (self._pip_opacity_slider, opacity),
    ):
        slider.blockSignals(True)
        slider.setValue(int(round(value * 100)))
        slider.blockSignals(False)


def _on_pip_enable_toggled(self, checked: bool) -> None:
    track = _active_pip_track(self)
    if track is None:
        return
    track.pip_enabled = checked
    for slider in (
        self._pip_x_slider,
        self._pip_y_slider,
        self._pip_scale_slider,
        self._pip_opacity_slider,
    ):
        slider.setEnabled(checked)
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._refresh_player_tracks()
    self._register_change("pip enable")


def _on_pip_slider_changed(self, attr: str, value: int) -> None:
    """Record PIP slider edits either as static values or keyed poses."""
    track = _active_pip_track(self)
    if track is None:
        return
    normalized = value / 100.0
    setattr(track, attr, normalized)

    kfs = getattr(track, "pip_keyframes", [])
    if kfs:
        pos_ms = self._player.position()
        existing = next((kf for kf in kfs if abs(kf["ms"] - pos_ms) <= 50), None)
        if existing is not None:
            existing["x"] = float(track.pip_x)
            existing["y"] = float(track.pip_y)
            existing["scale"] = float(track.pip_scale)
            existing["opacity"] = float(track.pip_opacity)
        else:
            kfs.append(
                {
                    "ms": pos_ms,
                    "x": float(track.pip_x),
                    "y": float(track.pip_y),
                    "scale": float(track.pip_scale),
                    "opacity": float(track.pip_opacity),
                }
            )
            track.pip_keyframes = sorted(kfs, key=lambda kf: kf["ms"])
        _refresh_pip_kf_list(self, track)
        row = self._track_rows.get(track.id)
        if row is not None:
            row.update()

    self._player.refresh_current_frame()


def _refresh_pip_kf_list(self, track) -> None:
    """Repopulate the keyframe QListWidget from track.pip_keyframes."""
    if not hasattr(self, "_pip_kf_list"):
        return
    self._pip_kf_list.clear()
    kfs = sorted(getattr(track, "pip_keyframes", []), key=lambda kf: kf["ms"])
    for kf in kfs:
        tc = self._ms_to_timecode(kf["ms"])
        label = f"{tc}  X:{kf['x']:.2f}  Y:{kf['y']:.2f}  S:{kf['scale']:.2f}"
        self._pip_kf_list.addItem(label)


def _pip_add_keyframe(self) -> None:
    """Capture current playhead position + slider values as a PIP keyframe."""
    track = _active_pip_track(self)
    if track is None or not getattr(track, "pip_enabled", False):
        return
    pos_ms = self._player.position()
    keyframe = {
        "ms": pos_ms,
        "x": float(track.pip_x),
        "y": float(track.pip_y),
        "scale": float(track.pip_scale),
        "opacity": float(track.pip_opacity),
    }
    kfs = [kf for kf in list(getattr(track, "pip_keyframes", [])) if abs(kf["ms"] - pos_ms) > 50]
    kfs.append(keyframe)
    track.pip_keyframes = sorted(kfs, key=lambda kf: kf["ms"])
    _refresh_pip_kf_list(self, track)
    self._refresh_player_tracks()
    self._register_change("pip keyframe add")


def _pip_delete_keyframe(self) -> None:
    """Remove the selected keyframe from the active track."""
    track = _active_pip_track(self)
    if track is None:
        return
    row = self._pip_kf_list.currentRow()
    if row < 0:
        return
    kfs = sorted(getattr(track, "pip_keyframes", []), key=lambda kf: kf["ms"])
    if row < len(kfs):
        kfs.pop(row)
    track.pip_keyframes = kfs
    _refresh_pip_kf_list(self, track)
    self._refresh_player_tracks()
    self._register_change("pip keyframe delete")
