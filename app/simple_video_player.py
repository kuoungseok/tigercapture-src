from __future__ import annotations

from enum import Enum
from pathlib import Path

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage


class PlayerState(Enum):
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


class SimpleVideoPlayer(QObject):
    """OpenCV-backed video player that emits QImage frames.

    Bypasses Qt Multimedia's QMediaPlayer + QVideoWidget pipeline entirely
    (which is unreliable on some Windows systems). Decoding happens on the
    main thread via ``QTimer`` at the target playback fps.
    """

    frame_ready = Signal(QImage)
    position_changed = Signal(int)  # ms
    duration_changed = Signal(int)  # ms
    state_changed = Signal(object)  # PlayerState
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._cap = None
        self._path: Path | None = None
        self._fps: float = 30.0
        self._duration_ms: int = 0
        self._total_frames: int = 0
        self._speed: float = 1.0
        self._state: PlayerState = PlayerState.STOPPED

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._advance_frame)

    # ---------- source / lifecycle ----------

    def set_source(self, path: Path | None) -> None:
        self._release()
        if path is None:
            self._set_state(PlayerState.STOPPED)
            self._path = None
            self.duration_changed.emit(0)
            return
        try:
            import cv2

            cap = cv2.VideoCapture(str(path))
            if not cap.isOpened():
                self.error_occurred.emit(f"Cannot open: {path}")
                return
            self._cap = cap
            self._path = Path(path)
            self._fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            self._total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            self._duration_ms = (
                int(self._total_frames / self._fps * 1000) if self._fps > 0 else 0
            )
            self.duration_changed.emit(self._duration_ms)
            self._set_state(PlayerState.PAUSED)
            self._emit_current_frame()
        except Exception as exc:  # noqa: BLE001
            self.error_occurred.emit(str(exc))

    def release(self) -> None:
        self._release()

    def _release(self) -> None:
        self._timer.stop()
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    # ---------- transport ----------

    def play(self) -> None:
        if self._cap is None:
            return
        self._update_timer_interval()
        self._timer.start()
        self._set_state(PlayerState.PLAYING)

    def pause(self) -> None:
        if self._cap is None:
            return
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

    # ---------- seek / speed ----------

    def set_position(self, ms: int) -> None:
        if self._cap is None or self._fps <= 0:
            return
        import cv2

        ms = max(0, min(int(ms), self._duration_ms))
        frame_idx = int(ms / 1000.0 * self._fps)
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        self._emit_current_frame()

    def set_speed(self, speed: float) -> None:
        self._speed = max(0.05, min(32.0, float(speed)))
        if self._state is PlayerState.PLAYING:
            self._update_timer_interval()

    def _update_timer_interval(self) -> None:
        target_interval = 1000.0 / max(1.0, self._fps * self._speed)
        self._timer.setInterval(max(1, int(round(target_interval))))

    # ---------- state / frames ----------

    def position(self) -> int:
        if self._cap is None:
            return 0
        import cv2

        frame_idx = self._cap.get(cv2.CAP_PROP_POS_FRAMES)
        return (
            int(frame_idx / self._fps * 1000) if self._fps > 0 else 0
        )

    def duration(self) -> int:
        return self._duration_ms

    def state(self) -> PlayerState:
        return self._state

    def _set_state(self, state: PlayerState) -> None:
        if state is not self._state:
            self._state = state
            self.state_changed.emit(state)

    def _advance_frame(self) -> None:
        if self._cap is None:
            return
        import cv2

        ret, frame = self._cap.read()
        if not ret:
            self.pause()
            return
        self._emit_frame(frame)
        self.position_changed.emit(self.position())

    def _emit_current_frame(self) -> None:
        """Read the frame at the current position without advancing the
        reader permanently (re-seeks one frame back after read)."""
        if self._cap is None:
            return
        import cv2

        before_idx = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
        ret, frame = self._cap.read()
        if not ret:
            return
        # Restore the reader so the next play() tick reads this frame again
        self._cap.set(cv2.CAP_PROP_POS_FRAMES, before_idx)
        self._emit_frame(frame)
        self.position_changed.emit(
            int(before_idx / self._fps * 1000) if self._fps > 0 else 0
        )

    def _emit_frame(self, bgr_frame: np.ndarray) -> None:
        h, w = bgr_frame.shape[:2]
        rgb = np.ascontiguousarray(bgr_frame[:, :, ::-1])
        qimg = QImage(
            rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888
        ).copy()
        self.frame_ready.emit(qimg)
