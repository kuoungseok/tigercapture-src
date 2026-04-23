"""macOS FrameRecorder backed by ScreenCaptureKit (macOS 12.3+).

Mirrors the Windows ``windows-capture`` (WGC) design:

- SCStream owns a background dispatch queue that delivers CMSampleBuffers.
- Each buffer is converted (BGRA → RGB) and stored as ``_current_frame``.
- A main-thread ``QTimer`` at ``fps`` samples the current frame and
  appends a copy to the list. This decouples grab cadence from target
  fps, yielding a stable recording even when the screen is static.

Signals / constructor match ``app/recorder.py`` exactly so the shared
``controller.py`` wires up the Mac version identically.

Requires:
- macOS 12.3 Monterey or newer (ScreenCaptureKit)
- Screen Recording permission (System Settings → Privacy & Security
  → Screen Recording). First run triggers the system prompt
  automatically; until the user approves and restarts the app, frames
  never arrive and ``error`` is emitted after a short timeout.
"""
from __future__ import annotations

import ctypes
import sys
import time

import numpy as np
from PIL import Image
from PySide6.QtCore import QEventLoop, QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QScreen

try:
    import objc
    from Foundation import NSObject
    from ScreenCaptureKit import (
        SCContentFilter,
        SCShareableContent,
        SCStream,
        SCStreamConfiguration,
        SCStreamOutputTypeScreen,
    )
    from CoreMedia import CMSampleBufferGetImageBuffer
    from CoreVideo import (
        CVPixelBufferGetBaseAddress,
        CVPixelBufferGetBytesPerRow,
        CVPixelBufferGetHeight,
        CVPixelBufferGetWidth,
        CVPixelBufferLockBaseAddress,
        CVPixelBufferUnlockBaseAddress,
        kCVPixelBufferLock_ReadOnly,
        kCVPixelFormatType_32BGRA,
    )
    from Quartz import CGRectMake
    from AppKit import NSScreen

    _HAS_SCK = True
except Exception as _exc:  # pragma: no cover — dev shell without pyobjc
    _IMPORT_ERR = _exc
    _HAS_SCK = False


_LOG_ENABLED = True


def _log(msg: str) -> None:
    if _LOG_ENABLED:
        print(f"[recorder-mac] {msg}", file=sys.stderr, flush=True)


def _fetch_shareable_content(timeout_s: float = 3.0):
    """Block the Qt event loop until SCShareableContent resolves.

    Returns (content, error). SCK's API is async-only; we spin a local
    ``QEventLoop`` so the main thread stays responsive while waiting.
    """
    loop = QEventLoop()
    result: dict = {"content": None, "error": None, "done": False}

    def handler(content, error):
        result["content"] = content
        result["error"] = error
        result["done"] = True
        loop.quit()

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(int(timeout_s * 1000))

    # excludingDesktopWindows=False, onScreenWindowsOnly=True
    SCShareableContent.getShareableContentExcludingDesktopWindows_onScreenWindowsOnly_completionHandler_(
        False, True, handler
    )
    loop.exec()
    timer.stop()
    return result["content"], result["error"]


def _display_id_for_qscreen(target: QScreen) -> int | None:
    """Resolve the CGDirectDisplayID for a Qt QScreen.

    Uses NSScreen's ``NSScreenNumber`` device description key, which is
    documented as the ``CGDirectDisplayID`` of the backing display.

    Matching strategy: compare origin points. Qt reports QScreen
    geometry with top-left origin and NSScreen reports frames with
    bottom-left origin, but on single-display setups origin is (0,0)
    for both — and for multi-display, both systems preserve relative
    x offsets which is enough to disambiguate. Falls back to the main
    display's ID.
    """
    if not _HAS_SCK:
        return None
    try:
        screens = NSScreen.screens()
        main_h = 0.0
        if screens:
            # macOS "global height" = max(frame.origin.y + frame.height)
            main_h = max(
                float(s.frame().origin.y + s.frame().size.height) for s in screens
            )

        tg = target.geometry()
        tx = tg.x()
        tw = tg.width()
        th = tg.height()

        best = None
        best_score = 1e18
        for s in screens:
            f = s.frame()
            # Convert NSScreen frame to Qt-style top-left origin.
            qt_x = int(f.origin.x)
            qt_y = int(main_h - f.origin.y - f.size.height)
            qt_w = int(f.size.width)
            qt_h = int(f.size.height)
            dx = abs(qt_x - tx)
            dy = abs(qt_y - tg.y())
            dw = abs(qt_w - tw)
            dh = abs(qt_h - th)
            score = dx + dy + dw + dh
            if score < best_score:
                best_score = score
                best = s

        if best is None:
            return None
        desc = best.deviceDescription()
        num = desc.objectForKey_("NSScreenNumber")
        if num is None:
            return None
        return int(num)
    except Exception as exc:
        _log(f"display resolution failed: {exc}")
        return None


def _cvpixelbuffer_to_pil(sample_buffer) -> Image.Image | None:
    """Zero-copy-ish conversion: CMSampleBuffer → CVPixelBuffer → PIL RGB.

    For 32BGRA (the format we ask SCStream for), we map the base
    address via ctypes, build a numpy view, trim the row-padding
    (``bytesPerRow`` > ``width*4`` on some displays), swap BGR→RGB,
    and hand the resulting contiguous array to PIL.
    """
    pb = CMSampleBufferGetImageBuffer(sample_buffer)
    if pb is None:
        return None

    locked = False
    try:
        if CVPixelBufferLockBaseAddress(pb, kCVPixelBufferLock_ReadOnly) != 0:
            return None
        locked = True

        w = int(CVPixelBufferGetWidth(pb))
        h = int(CVPixelBufferGetHeight(pb))
        bpr = int(CVPixelBufferGetBytesPerRow(pb))
        base = CVPixelBufferGetBaseAddress(pb)
        if base is None:
            return None
        base_addr = int(base)
        if base_addr == 0:
            return None

        total = bpr * h
        buf_type = ctypes.c_ubyte * total
        buf = buf_type.from_address(base_addr)
        arr = np.frombuffer(buf, dtype=np.uint8).reshape(h, bpr // 4, 4)
        # Trim any row padding then drop alpha and swap to RGB.
        rgb = np.ascontiguousarray(arr[:, :w, [2, 1, 0]])
        return Image.fromarray(rgb, "RGB")
    except Exception as exc:
        _log(f"pixel buffer convert failed: {exc}")
        return None
    finally:
        if locked:
            CVPixelBufferUnlockBaseAddress(pb, kCVPixelBufferLock_ReadOnly)


if _HAS_SCK:

    class _StreamOutput(NSObject):
        """SCStreamOutput delegate — called on SCK's dispatch queue."""

        def initWithCallback_(self, cb):
            self = objc.super(_StreamOutput, self).init()
            if self is None:
                return None
            self._cb = cb
            return self

        # Selector shape matches: -stream:didOutputSampleBuffer:ofType:
        def stream_didOutputSampleBuffer_ofType_(
            self, stream, sample_buffer, sample_type
        ):
            if sample_type != SCStreamOutputTypeScreen:
                return
            try:
                self._cb(sample_buffer)
            except Exception as exc:
                _log(f"output cb raised: {exc}")

else:

    class _StreamOutput:  # type: ignore[no-redef]
        pass


class FrameRecorder(QObject):
    """Drop-in replacement for the Windows FrameRecorder, backed by SCK."""

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
        self._stream = None
        self._output_delegate = None
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
        if not _HAS_SCK:
            self.error.emit(
                f"ScreenCaptureKit unavailable (pyobjc load failed: {_IMPORT_ERR})"
            )
            return

        self._frames = []
        self._paused = False
        self._paused_total = 0.0
        self._pause_began = 0.0

        screen = (
            QGuiApplication.screenAt(self._rect.topLeft())
            or QGuiApplication.screenAt(self._rect.center())
            or QGuiApplication.primaryScreen()
        )
        if screen is None:
            self.error.emit("No QScreen available for region")
            return
        self._target_screen = screen

        display_id = _display_id_for_qscreen(screen)
        if display_id is None:
            self.error.emit("Could not resolve CGDirectDisplayID for target screen")
            return

        content, err = _fetch_shareable_content()
        if content is None:
            msg = str(err) if err is not None else "SCShareableContent returned nil"
            self.error.emit(
                f"Screen Recording permission not granted? ({msg}). Enable it "
                "under System Settings → Privacy & Security → Screen Recording."
            )
            return

        sc_display = None
        for d in content.displays():
            if int(d.displayID()) == int(display_id):
                sc_display = d
                break
        if sc_display is None:
            self.error.emit(f"No SCDisplay for CGDirectDisplayID {display_id}")
            return

        # Compute crop in the display's local coords (top-left origin, points).
        origin = screen.geometry().topLeft()
        dpr = float(screen.devicePixelRatio())
        local_x = float(self._rect.x() - origin.x())
        local_y = float(self._rect.y() - origin.y())
        local_w = float(self._rect.width())
        local_h = float(self._rect.height())

        out_w = max(1, int(round(local_w * dpr)))
        out_h = max(1, int(round(local_h * dpr)))

        try:
            # Exclude our own app windows from the capture so our overlays
            # (recording border, control bar) aren't recorded.
            our_apps = []
            try:
                from AppKit import NSRunningApplication
                pid = NSRunningApplication.currentApplication().processIdentifier()
                for a in content.applications():
                    if int(a.processID()) == int(pid):
                        our_apps.append(a)
            except Exception:
                pass

            sc_filter = (
                SCContentFilter.alloc().initWithDisplay_excludingApplications_exceptingWindows_(
                    sc_display, our_apps, []
                )
            )

            cfg = SCStreamConfiguration.alloc().init()
            cfg.setWidth_(out_w)
            cfg.setHeight_(out_h)
            cfg.setSourceRect_(CGRectMake(local_x, local_y, local_w, local_h))
            cfg.setDestinationRect_(CGRectMake(0, 0, out_w, out_h))
            cfg.setPixelFormat_(kCVPixelFormatType_32BGRA)
            cfg.setShowsCursor_(self._include_cursor)
            cfg.setQueueDepth_(5)
            # Ask for ~60fps; QTimer downsamples to target fps.
            try:
                from CoreMedia import CMTimeMake
                cfg.setMinimumFrameInterval_(CMTimeMake(1, 60))
            except Exception:
                pass

            stream = SCStream.alloc().initWithFilter_configuration_delegate_(
                sc_filter, cfg, None
            )

            delegate = _StreamOutput.alloc().initWithCallback_(self._handle_sck_frame)
            success, add_err = stream.addStreamOutput_type_sampleHandlerQueue_error_(
                delegate, SCStreamOutputTypeScreen, None, None
            )
            if not success:
                self.error.emit(
                    f"addStreamOutput failed: {add_err}"
                )
                return

            def _start_handler(err):
                if err is not None:
                    self.error.emit(f"SCStream startCapture failed: {err}")

            stream.startCaptureWithCompletionHandler_(_start_handler)
            self._stream = stream
            self._output_delegate = delegate
        except Exception as exc:
            _log(f"SCStream start failed: {exc}")
            self.error.emit(f"SCStream 시작 실패: {exc}")
            return

        self._start_time = time.perf_counter()
        self._tick_timer.start()
        _log(
            f"start (SCK) rect=({self._rect.x()},{self._rect.y()} "
            f"{self._rect.width()}x{self._rect.height()}) fps={self._fps} "
            f"out={out_w}x{out_h} display_id={display_id}"
        )

    def _handle_sck_frame(self, sample_buffer) -> None:
        """Called from SCK dispatch queue."""
        if self._stopped:
            return
        img = _cvpixelbuffer_to_pil(sample_buffer)
        if img is not None:
            self._current_frame = img

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
            if self._stream is not None:
                def _stop_handler(err):
                    if err is not None:
                        _log(f"SCStream stop err: {err}")
                self._stream.stopCaptureWithCompletionHandler_(_stop_handler)
        except Exception as exc:
            _log(f"stream stop failed: {exc}")

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
