from __future__ import annotations

from app.timeline_model import FadeSegment


def _build_fade_card(self):
    from app.effect_cards import FadeCard

    self.fade_card = FadeCard()
    return self.fade_card


def _on_workbench_fade_in_changed(self, ms: int) -> None:
    target = self._workbench_panel.current_target()
    if target is None:
        return
    ms = max(0, int(ms))
    if target[0] == "video":
        self._set_video_track_leading_fade(target[1], ms)
    elif target[0] == "audio":
        track, clip = target[1], target[2]
        clip.fade_in_ms = ms
        row = self._audio_rows.get(track.id)
        if row is not None:
            row.update()
        self._on_audio_track_changed(track.id)
    elif target[0] == "audio_source":
        clip = target[1]
        clip.fade_in_ms = ms


def _on_workbench_fade_out_changed(self, ms: int) -> None:
    target = self._workbench_panel.current_target()
    if target is None:
        return
    ms = max(0, int(ms))
    if target[0] == "video":
        self._set_video_track_trailing_fade(target[1], ms)
    elif target[0] == "audio":
        track, clip = target[1], target[2]
        clip.fade_out_ms = ms
        row = self._audio_rows.get(track.id)
        if row is not None:
            row.update()
        self._on_audio_track_changed(track.id)
    elif target[0] == "audio_source":
        clip = target[1]
        clip.fade_out_ms = ms


def _set_video_track_leading_fade(self, track, ms: int) -> None:
    """Materialise the inspector's Fade In slider as a leading fade."""
    fades = list(track.fades or [])
    fades = [fade for fade in fades if not (fade.start_ms <= 0 and fade.kind == "in")]
    if ms > 0:
        fades.append(FadeSegment(start_ms=0, end_ms=ms, kind="in"))
    fades.sort(key=lambda fade: fade.start_ms)
    track.fades = fades
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._player.set_position(self._player.position())


def _set_video_track_trailing_fade(self, track, ms: int) -> None:
    """Materialise the inspector's Fade Out slider as a trailing fade."""
    duration = int(getattr(track, "duration_ms", 0) or 0)
    if duration <= 0:
        return
    fades = list(track.fades or [])
    fades = [
        fade
        for fade in fades
        if not (fade.end_ms >= duration - 100 and fade.kind == "out")
    ]
    if ms > 0:
        start = max(0, duration - ms)
        fades.append(FadeSegment(start_ms=start, end_ms=duration, kind="out"))
    fades.sort(key=lambda fade: fade.start_ms)
    track.fades = fades
    row = self._track_rows.get(track.id)
    if row is not None:
        row.update()
    self._player.set_position(self._player.position())


def _on_workbench_volume_changed(self, db: float) -> None:
    target = self._workbench_panel.current_target()
    if target is None or target[0] != "audio":
        return
    track = target[1]
    track.master_volume = float(db)
    self._audio_mixer.update_track(track)
    row = self._audio_rows.get(track.id)
    if row is not None:
        row.update()


def _current_fade_multiplier(self, pos_ms: int) -> float:
    """Return active-track fade brightness multiplier at project time."""
    track = self._active_track()
    if track is None or not track.fades:
        return 1.0
    local = pos_ms - getattr(track, "offset_ms", 0)
    for fade in track.fades:
        if not fade.contains(local):
            continue
        span = fade.duration_ms
        if span <= 0:
            return 1.0
        t = (local - fade.start_ms) / span
        kind = getattr(fade, "kind", "both")
        if kind == "in":
            return t
        if kind == "out":
            return 1.0 - t
        return 1.0 - 2.0 * abs(t - 0.5)
    return 1.0
