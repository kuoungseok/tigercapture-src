from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage

from app.simple_video_player import PlayerState


class ProjectPlayer(QObject):
    """Multi-track player with layered fall-through playback.

    Tracks are ordered from **first-added (bottom)** to **last-added (top)**.
    At any time ``t`` the topmost track that has a source, where ``t`` is
    within its duration and not inside a cut segment, is the one we render.
    This means cuts in the top track "reveal" whatever is below; tracks that
    end early leave the underlying track visible through the remainder.

    Speed segments apply to whichever track is currently being rendered.
    Project duration = max of all tracks' durations.
    """

    frame_ready = Signal(QImage)
    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(object)
    error_occurred = Signal(str)

    REFERENCE_FPS = 30.0

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tracks: list = []  # list of VideoTrack (first-added first)
        self._caps: dict = {}
        self._fps: dict = {}
        self._total_frames: dict = {}
        self._last_rendered_track_id: int | None = None
        self._last_rendered_frame_idx: int = -1
        self._position_ms: int = 0
        self._duration_ms: int = 0
        self._state: PlayerState = PlayerState.STOPPED
        self._current_segment_speed: float = 1.0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

    # ---------------- tracks ----------------

    def refresh_tracks(self, tracks: list) -> None:
        """Rebuild caps based on the given ordered track list. Preserves caps
        for tracks whose source hasn't changed. Recomputes duration for each
        track from its video file."""
        import cv2

        new_ids = {t.id for t in tracks}
        # Release removed tracks
        for tid in list(self._caps.keys()):
            if tid not in new_ids:
                self._release_cap(tid)

        for t in tracks:
            if t.source_path is None:
                self._release_cap(t.id)
                t.duration_ms = 0
                continue
            # If cap exists and path matches, keep it; else reopen
            cap = self._caps.get(t.id)
            need_open = cap is None
            if not need_open:
                # No way to compare cached path — assume paths unchanged unless
                # user loaded new; callers call refresh_tracks after any change
                pass
            if need_open:
                cap = cv2.VideoCapture(str(t.source_path))
                if not cap.isOpened():
                    self.error_occurred.emit(f"Cannot open {t.source_path}")
                    continue
                self._caps[t.id] = cap
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                self._fps[t.id] = fps
                self._total_frames[t.id] = total_frames
                if fps > 0:
                    t.duration_ms = int(total_frames / fps * 1000)

        self._tracks = list(tracks)
        new_duration = max(
            (
                getattr(t, "offset_ms", 0) + t.duration_ms
                for t in tracks
                if t.source_path is not None
            ),
            default=0,
        )
        self._duration_ms = new_duration
        self.duration_changed.emit(self._duration_ms)
        # Clamp position
        if self._position_ms > self._duration_ms:
            self._position_ms = self._duration_ms
        self._render_frame_at(self._position_ms, force_seek=True)

    def _release_cap(self, track_id: int) -> None:
        cap = self._caps.pop(track_id, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        self._fps.pop(track_id, None)
        self._total_frames.pop(track_id, None)

    # ---------------- active track cascade ----------------

    def _active_track_at(self, pos_ms: int):
        """Return topmost track that should render at ``pos_ms``, cascading
        past cuts / past-end / before-start. None if all layers are empty at
        this time. ``pos_ms`` is project timeline time."""
        for t in reversed(self._tracks):
            if t.source_path is None:
                continue
            if t.id not in self._caps:
                continue
            offset = getattr(t, "offset_ms", 0)
            local = pos_ms - offset
            if local < 0 or local >= t.duration_ms:
                continue
            in_cut = False
            for cut in t.cuts:
                if cut.start_ms <= local < cut.end_ms:
                    in_cut = True
                    break
            if in_cut:
                continue
            return t
        return None

    @staticmethod
    def _speed_at(track, pos_ms: int) -> float:
        """``pos_ms`` is project time; speed segments are stored track-local."""
        local = pos_ms - getattr(track, "offset_ms", 0)
        for seg in track.speed_segments:
            if seg.start_ms <= local < seg.end_ms:
                return seg.speed
        return 1.0

    # ---------------- playback ----------------

    def play(self) -> None:
        if not self._caps:
            return
        self._update_interval()
        self._timer.start()
        self._set_state(PlayerState.PLAYING)

    def pause(self) -> None:
        self._timer.stop()
        self._set_state(PlayerState.PAUSED)

    def toggle(self) -> None:
        if self._state is PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self) -> None:
        self._timer.stop()
        self._set_state(PlayerState.STOPPED)

    def release(self) -> None:
        self._timer.stop()
        for tid in list(self._caps.keys()):
            self._release_cap(tid)

    def _set_state(self, state: PlayerState) -> None:
        if state is not self._state:
            self._state = state
            self.state_changed.emit(state)

    def _update_interval(self) -> None:
        track = self._active_track_at(self._position_ms)
        speed = self._speed_at(track, self._position_ms) if track else 1.0
        self._current_segment_speed = speed
        interval = 1000.0 / (self.REFERENCE_FPS * max(0.05, speed))
        self._timer.setInterval(max(1, int(round(interval))))

    def _tick(self) -> None:
        if self._duration_ms <= 0:
            self.pause()
            return
        advance_ms = int(round(1000.0 / self.REFERENCE_FPS))
        new_pos = self._position_ms + advance_ms
        if new_pos >= self._duration_ms:
            self._position_ms = self._duration_ms
            self.position_changed.emit(self._position_ms)
            self.pause()
            return
        self._position_ms = new_pos
        # Check if segment speed changed
        track = self._active_track_at(new_pos)
        new_speed = self._speed_at(track, new_pos) if track else 1.0
        if abs(new_speed - self._current_segment_speed) > 1e-4:
            self._current_segment_speed = new_speed
            self._update_interval()
        self._render_frame_at(new_pos)
        self.position_changed.emit(new_pos)

    # ---------------- seek / rendering ----------------

    def set_position(self, ms: int) -> None:
        ms = max(0, min(int(ms), self._duration_ms))
        self._position_ms = ms
        self._render_frame_at(ms, force_seek=True)
        self.position_changed.emit(ms)

    def _render_frame_at(self, pos_ms: int, force_seek: bool = False) -> None:
        import cv2

        track = self._active_track_at(pos_ms)
        if track is None:
            self._emit_blank()
            self._last_rendered_track_id = None
            return
        cap = self._caps[track.id]
        fps = self._fps[track.id]
        if fps <= 0:
            return
        local_ms = pos_ms - getattr(track, "offset_ms", 0)
        frame_idx = int(local_ms / 1000.0 * fps)
        # Sequential read optimization: only seek when necessary
        need_seek = (
            force_seek
            or track.id != self._last_rendered_track_id
            or frame_idx != self._last_rendered_frame_idx + 1
        )
        if need_seek:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, bgr = cap.read()
        if not ret or bgr is None:
            return
        self._last_rendered_track_id = track.id
        self._last_rendered_frame_idx = frame_idx
        h, w = bgr.shape[:2]
        rgb = np.ascontiguousarray(bgr[:, :, ::-1])
        qimg = QImage(
            rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888
        ).copy()
        self.frame_ready.emit(qimg)

    def _emit_blank(self) -> None:
        # Small dark image to indicate "all tracks transparent/ended here"
        qimg = QImage(16, 9, QImage.Format.Format_RGB888)
        qimg.fill(Qt.GlobalColor.black)
        self.frame_ready.emit(qimg)

    # ---------------- getters ----------------

    def position(self) -> int:
        return self._position_ms

    def duration(self) -> int:
        return self._duration_ms

    def state(self) -> PlayerState:
        return self._state
