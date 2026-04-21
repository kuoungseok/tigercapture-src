from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QScreen


_LOG_ENABLED = True


def _log(msg: str) -> None:
    if _LOG_ENABLED:
        print(f"[recorder] {msg}", file=sys.stderr, flush=True)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


def _resolve_wgc_monitor_index(target: QScreen) -> int:
    """Return the 1-based WGC monitor index for the given QScreen.

    Matches by the physical rectangle reported by Windows against each
    QScreen's ``geometry() * devicePixelRatio``. Falls back to 1 (primary).
    """
    try:
        enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(_RECT),
            wintypes.LPARAM,
        )
        monitors: list[tuple[int, _RECT]] = []

        def callback(_hmon, _hdc, lprc, _lparam):
            info = _MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
            if ctypes.windll.user32.GetMonitorInfoW(_hmon, ctypes.byref(info)):
                monitors.append((len(monitors) + 1, info.rcMonitor))
            return True

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, enum_proc(callback), 0)

        g = target.geometry()
        dpr = float(target.devicePixelRatio())
        target_phys = (
            int(round(g.x() * dpr)),
            int(round(g.y() * dpr)),
            int(round((g.x() + g.width()) * dpr)),
            int(round((g.y() + g.height()) * dpr)),
        )
        for idx, r in monitors:
            rect = (r.left, r.top, r.right, r.bottom)
            if all(abs(a - b) <= 4 for a, b in zip(rect, target_phys)):
                return idx
    except Exception:
        pass
    return 1


class FrameRecorder(QObject):
    """Windows Graphics Capture (WGC) based recorder.

    A WGC worker thread owned by ``windows-capture`` crops & converts each
    arriving monitor frame and stores it as the "current" snapshot. A Qt
    ``QTimer`` on the main thread samples the current snapshot at the target
    fps and appends the result to the frame list.

    This decouples grab (WGC, GPU-accelerated) from recording cadence,
    yielding constant fps output even when the screen is static, and high
    throughput for large regions since the heavy work is off the main thread.
    """

    frame_captured = Signal(int, int)
    finished_recording = Signal(list, int, int)
    error = Signal(str)

    def __init__(self, rect: QRect, fps: int, include_cursor: bool = False) -> None:
        super().__init__()
        self._rect = QRect(rect)
        self._fps = max(1, int(fps))
        self._include_cursor = bool(include_cursor)
        self._frames: list[Image.Image] = []
        self._paused = False
        self._stopped = False

        self._current_frame: Image.Image | None = None
        self._wgc = None
        self._crop_rect: tuple[int, int, int, int] | None = None
        self._target_screen: QScreen | None = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._tick_timer.setInterval(max(1, int(round(1000 / self._fps))))
        self._tick_timer.timeout.connect(self._tick)

        self._start_time = 0.0
        self._pause_began = 0.0
        self._paused_total = 0.0

    @property
    def target_fps(self) -> int:
        return self._fps

    def isRunning(self) -> bool:
        return self._tick_timer.isActive()

    def start(self) -> None:
        self._frames = []
        self._paused = False
        self._paused_total = 0.0
        self._pause_began = 0.0

        screen = (
            QGuiApplication.screenAt(self._rect.topLeft())
            or QGuiApplication.screenAt(self._rect.center())
            or QGuiApplication.primaryScreen()
        )
        self._target_screen = screen
        monitor_index = _resolve_wgc_monitor_index(screen)

        origin = screen.geometry().topLeft()
        dpr = float(screen.devicePixelRatio())
        x1 = int(round((self._rect.x() - origin.x()) * dpr))
        y1 = int(round((self._rect.y() - origin.y()) * dpr))
        x2 = int(round((self._rect.x() + self._rect.width() - origin.x()) * dpr))
        y2 = int(round((self._rect.y() + self._rect.height() - origin.y()) * dpr))
        self._crop_rect = (x1, y1, x2, y2)

        try:
            from windows_capture import WindowsCapture

            wgc = WindowsCapture(
                cursor_capture=self._include_cursor,
                draw_border=False,
                monitor_index=monitor_index,
            )

            recorder = self

            @wgc.event
            def on_frame_arrived(frame, control):
                if recorder._stopped:
                    try:
                        control.stop()
                    except Exception:
                        pass
                    return
                recorder._handle_wgc_frame(frame)

            @wgc.event
            def on_closed():
                _log("WGC session closed")

            wgc.start_free_threaded()
            self._wgc = wgc
        except Exception as exc:  # noqa: BLE001
            _log(f"WGC start failed: {exc}")
            self.error.emit(f"WGC 시작 실패: {exc}")
            return

        self._start_time = time.perf_counter()
        self._tick_timer.start()
        _log(
            f"start (WGC) rect=({self._rect.x()},{self._rect.y()} "
            f"{self._rect.width()}x{self._rect.height()}) fps={self._fps} "
            f"interval={self._tick_timer.interval()}ms monitor_idx={monitor_index}"
        )

    def _handle_wgc_frame(self, frame) -> None:
        """Called from WGC thread. Cheap crop + BGRA→RGB, cache result."""
        if self._crop_rect is None:
            return
        try:
            buf = frame.frame_buffer
            h, w = buf.shape[:2]
            x1, y1, x2, y2 = self._crop_rect
            x1 = max(0, min(x1, w))
            y1 = max(0, min(y1, h))
            x2 = max(x1 + 1, min(x2, w))
            y2 = max(y1 + 1, min(y2, h))
            cropped = buf[y1:y2, x1:x2]
            rgb = np.ascontiguousarray(cropped[:, :, [2, 1, 0]])
            img = Image.fromarray(rgb, "RGB")
            self._current_frame = img
        except Exception as exc:
            _log(f"frame conversion failed: {exc}")

    def set_paused(self, paused: bool) -> None:
        if paused == self._paused:
            return
        now = time.perf_counter()
        if paused:
            self._pause_began = now
        else:
            if self._pause_began > 0.0:
                self._paused_total += now - self._pause_began
                self._pause_began = 0.0
        self._paused = paused

    def request_stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._tick_timer.stop()
        try:
            if self._wgc is not None:
                self._wgc.stop()
        except Exception:
            pass

        now = time.perf_counter()
        if self._pause_began > 0.0:
            self._paused_total += now - self._pause_began
            self._pause_began = 0.0
        total_ms = max(0, int((now - self._start_time - self._paused_total) * 1000))
        actual_fps = (
            int(round(len(self._frames) * 1000 / total_ms))
            if total_ms > 0
            else self._fps
        )
        _log(
            f"stop frames={len(self._frames)} duration={total_ms}ms "
            f"actual_fps={actual_fps} (target {self._fps})"
        )
        self.finished_recording.emit(list(self._frames), actual_fps, total_ms)

    def _tick(self) -> None:
        if self._paused or self._stopped:
            return
        current = self._current_frame
        if current is None:
            return
        self._frames.append(current)
        now = time.perf_counter()
        elapsed_ms = max(0, int((now - self._start_time - self._paused_total) * 1000))
        n = len(self._frames)
        if n == 1 or n % 30 == 0:
            _log(f"frame #{n} elapsed={elapsed_ms}ms")
        self.frame_captured.emit(n, elapsed_ms)
