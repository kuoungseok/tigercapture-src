from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np
from PIL import Image

from app.subprocess_utils import hidden_subprocess_kwargs
from PySide6.QtCore import QObject, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QScreen
from PySide6.QtWidgets import QApplication


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

    Matches by the Windows device name (``\\\\.\\DISPLAYn``) rather than
    physical rectangles, because per-monitor DPI makes the logical→physical
    rect math unreliable (each screen has its own DPR and logical
    coordinates don't stack linearly across them). Falls back to 1.
    """
    try:
        enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(_RECT),
            wintypes.LPARAM,
        )
        # Enumerate in the same order WGC uses, record (1-based idx, device_name).
        monitors: list[tuple[int, str, _RECT]] = []

        def callback(_hmon, _hdc, _lprc, _lparam):
            info = _MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
            if ctypes.windll.user32.GetMonitorInfoW(_hmon, ctypes.byref(info)):
                monitors.append(
                    (len(monitors) + 1, info.szDevice, info.rcMonitor)
                )
            return True

        ctypes.windll.user32.EnumDisplayMonitors(0, 0, enum_proc(callback), 0)

        # Primary match: device name == QScreen.name() (e.g. "\\.\DISPLAY2")
        target_name = target.name()
        for idx, dev_name, _r in monitors:
            if dev_name and target_name and dev_name == target_name:
                return idx

        # Fallback: physical-point match. Take the center of the screen in
        # logical coords, ask Windows which monitor it belongs to.
        try:
            class _POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            g = target.geometry()
            dpr = float(target.devicePixelRatio())
            cx = int(round((g.x() + g.width() / 2) * dpr))
            cy = int(round((g.y() + g.height() / 2) * dpr))
            hmon = ctypes.windll.user32.MonitorFromPoint(
                _POINT(cx, cy), 2  # MONITOR_DEFAULTTONEAREST
            )
            info = _MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(_MONITORINFOEXW)
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                for idx, dev_name, _r in monitors:
                    if dev_name == info.szDevice:
                        return idx
        except Exception:
            pass
    except Exception:
        pass
    return 1


_MODIFIER_VKS = {
    "Ctrl": (0x11, 0xA2, 0xA3),
    "Shift": (0x10, 0xA0, 0xA1),
    "Alt": (0x12, 0xA4, 0xA5),
    "Win": (0x5B, 0x5C),
}

_PRIMARY_KEY_LABELS: tuple[tuple[int, str], ...] = (
    *((0x70 + idx, f"F{idx + 1}") for idx in range(24)),
    (0x25, "Left"),
    (0x26, "Up"),
    (0x27, "Right"),
    (0x28, "Down"),
    (0x0D, "Enter"),
    (0x1B, "Esc"),
    (0x09, "Tab"),
    (0x20, "Space"),
    (0x08, "Backspace"),
    (0x2E, "Delete"),
    (0x2D, "Insert"),
    (0x24, "Home"),
    (0x23, "End"),
    (0x21, "Page Up"),
    (0x22, "Page Down"),
    (0x2C, "Print"),
    (0x5A, "Z"),
    (0x58, "X"),
    (0x43, "C"),
    (0x56, "V"),
    (0x41, "A"),
    (0x53, "S"),
    (0x50, "P"),
    (0x4F, "O"),
    (0x4E, "N"),
    (0x57, "W"),
    (0x59, "Y"),
    *((0x30 + idx, str(idx)) for idx in range(10)),
)

_PRIVACY_SAFE_SINGLE_KEYS = {
    "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
    "F13", "F14", "F15", "F16", "F17", "F18", "F19", "F20", "F21", "F22", "F23", "F24",
    "Left", "Up", "Right", "Down", "Enter", "Esc", "Tab", "Space", "Backspace",
    "Delete", "Insert", "Home", "End", "Page Up", "Page Down", "Print",
}


def _hotkey_label_from_pressed(pressed_vks: set[int] | frozenset[int]) -> str:
    """Return a tutorial-safe hotkey label from currently pressed VK codes.

    Single letter/number text entry is intentionally ignored unless Ctrl/Alt/
    Shift/Win is part of the chord; Screen Studio-style key overlays should not
    become a text logger.
    """
    pressed = {int(v) for v in pressed_vks}
    modifiers = [
        label
        for label, codes in _MODIFIER_VKS.items()
        if any(code in pressed for code in codes)
    ]
    primary = ""
    modifier_codes = {code for codes in _MODIFIER_VKS.values() for code in codes}
    for vk, label in _PRIMARY_KEY_LABELS:
        if vk in pressed and vk not in modifier_codes:
            primary = label
            break
    if not primary:
        return ""
    if not modifiers and primary not in _PRIVACY_SAFE_SINGLE_KEYS:
        return ""
    return " + ".join([*modifiers, primary])


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
    # Legacy signal — kept for the macOS recorder which still buffers
    # the full frame list. Windows always uses the streaming path
    # below now, so this never fires from this class.
    finished_recording = Signal(list, int, int)
    # Streaming recorder result: (temp_mp4_path, fps, duration_ms).
    # Path is empty on cancel / failure.
    finished_recording_streamed = Signal(str, int, int)
    error = Signal(str)

    def __init__(self, rect: QRect, fps: int, include_cursor: bool = False) -> None:
        super().__init__()
        self._rect = QRect(rect)
        self._fps = max(1, int(fps))
        self._include_cursor = bool(include_cursor)
        # Frame count, NOT a frame list — streaming sends each frame
        # straight to ffmpeg's stdin so RAM stays bounded regardless of
        # recording length.
        self._frame_count: int = 0
        self._paused = False
        self._stopped = False

        self._current_frame: Image.Image | None = None
        self._wgc = None
        self._crop_rect: tuple[int, int, int, int] | None = None
        self._target_screen: QScreen | None = None

        # Streaming encoder state.
        self._enc_proc: subprocess.Popen | None = None
        self._enc_path: Path | None = None
        self._enc_size: tuple[int, int] | None = None
        self._enc_stderr_log: str | None = None
        self._cursor_events: list[dict] = []
        self._last_cursor_event: dict | None = None
        self._last_mouse_down: bool = False
        self._last_key_combo: str = ""
        self._last_key_event_ms: int = -10_000

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
        self._frame_count = 0
        self._paused = False
        self._paused_total = 0.0
        self._pause_began = 0.0
        # Encoder is lazy-spawned on first frame (we need the actual
        # captured dimensions for the rawvideo input header).
        self._enc_proc = None
        self._enc_path = None
        self._enc_size = None
        self._cursor_events = []
        self._last_cursor_event = None
        self._last_mouse_down = False
        self._last_key_combo = ""
        self._last_key_event_ms = -10_000

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
                # Screen Studio-style cursor polish needs a clean video plate.
                # Cursor position/clicks are sampled into a sidecar and then
                # re-rendered by preview/export with smoothing, scale and rings.
                cursor_capture=False,
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
        n_frames = self._frame_count
        actual_fps = (
            int(round(n_frames * 1000 / total_ms))
            if total_ms > 0
            else self._fps
        )

        # Finalise the streaming encoder — close stdin, wait for ffmpeg
        # to flush the moov atom, then hand the resulting temp .mp4
        # path to the controller.
        path = self._finalize_encoder()
        _log(
            f"stop frames={n_frames} duration={total_ms}ms "
            f"actual_fps={actual_fps} (target {self._fps}) path={path or '<none>'}"
        )
        self.finished_recording_streamed.emit(path, actual_fps, total_ms)

    def _ensure_encoder(self, w: int, h: int) -> bool:
        """Lazy-spawn the ffmpeg subprocess on the first frame. Returns
        ``False`` on failure — caller should drop the frame in that
        case. Output is a temp .mp4 the controller decodes back into a
        frame list (or, eventually, hands directly to the video editor
        as a track source).
        """
        if self._enc_proc is not None:
            return True
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception as exc:
            _log(f"ffmpeg lookup failed: {exc}")
            return False
        fd, path_str = tempfile.mkstemp(
            suffix=".mp4", prefix="tigercapture_capture_",
        )
        os.close(fd)
        # yuv420p requires even width AND height. The capture region
        # can have odd dims (a 1-pixel boundary mismatch from DPR
        # rounding is common), so we pad up to the next even with a
        # 1-px black border via the ``pad`` filter — keeps full input
        # pixels visible and adds at most 2 px of total padding.
        cmd = [
            ffmpeg_exe,
            "-y",
            "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{w}x{h}",
            "-r", str(self._fps),
            "-i", "-",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2:0:0:black",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            path_str,
        ]
        # Capture stderr to a sibling .log so when ffmpeg dies we can
        # actually see why instead of just seeing "Errno 22" on the
        # broken pipe later.
        stderr_log_path = path_str + ".ffmpeg.log"
        try:
            stderr_fh = open(stderr_log_path, "w", encoding="utf-8")
            self._enc_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=stderr_fh,
                **hidden_subprocess_kwargs(),
            )
            self._enc_stderr_log = stderr_log_path
        except Exception as exc:
            _log(f"ffmpeg spawn failed: {exc}")
            try:
                os.unlink(path_str)
            except OSError:
                pass
            return False
        self._enc_path = Path(path_str)
        self._enc_size = (w, h)
        _log(f"ffmpeg streaming started → {path_str} ({w}x{h}@{self._fps})")
        return True

    def _finalize_encoder(self) -> str:
        """Close stdin and wait for ffmpeg to write the moov atom.
        Returns the temp file path on success, empty string on failure
        or if no frames were ever written. On failure, dumps the
        encoder's stderr capture into our log so the actual cause is
        visible."""
        if self._enc_proc is None:
            return ""
        proc = self._enc_proc
        path = self._enc_path
        stderr_log = self._enc_stderr_log
        self._enc_proc = None
        self._enc_stderr_log = None
        try:
            if proc.stdin is not None:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                _log("ffmpeg finalize timeout — killing")
                proc.kill()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
        except Exception as exc:
            _log(f"ffmpeg finalize error: {exc}")
        ok = (
            path is not None
            and path.exists()
            and path.stat().st_size > 0
            and proc.returncode == 0
        )
        # Mirror ffmpeg's stderr into our log so failures are diagnosable.
        if stderr_log is not None:
            try:
                with open(stderr_log, "r", encoding="utf-8") as fh:
                    msg = fh.read().strip()
                if msg:
                    _log(f"ffmpeg stderr:\n{msg}")
                os.unlink(stderr_log)
            except OSError:
                pass
        if not ok:
            if path is not None:
                try:
                    path.unlink()
                except OSError:
                    pass
            return ""
        self._write_cursor_sidecar(path)
        return str(path)

    def _left_mouse_down(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            # VK_LBUTTON high bit indicates the button is currently down.
            return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
        except Exception:
            return False

    def _pressed_virtual_keys(self) -> set[int]:
        if sys.platform != "win32":
            return set()
        try:
            vks = {code for codes in _MODIFIER_VKS.values() for code in codes}
            vks.update(vk for vk, _label in _PRIMARY_KEY_LABELS)
            return {
                int(vk)
                for vk in vks
                if ctypes.windll.user32.GetAsyncKeyState(int(vk)) & 0x8000
            }
        except Exception:
            return set()

    def _sample_keyboard_event(self, elapsed_ms: int, x_norm: float, y_norm: float, visible: bool) -> None:
        label = _hotkey_label_from_pressed(self._pressed_virtual_keys())
        if label == self._last_key_combo:
            return
        if not label:
            self._last_key_combo = ""
            return
        # Suppress tiny chord transitions such as Ctrl -> Ctrl+Shift+P when the
        # OS reports modifier state a few milliseconds apart.
        if int(elapsed_ms) - int(self._last_key_event_ms) < 80:
            return
        self._last_key_combo = label
        self._last_key_event_ms = int(elapsed_ms)
        self._cursor_events.append(
            {
                "t_ms": int(elapsed_ms),
                "x_norm": round(max(0.0, min(1.0, float(x_norm))), 5),
                "y_norm": round(max(0.0, min(1.0, float(y_norm))), 5),
                "kind": "hotkey" if " + " in label else "key",
                "label": label,
                "visible": bool(visible),
            }
        )

    @staticmethod
    def _cursor_fx_for_role(role: str, kind: str = "move") -> tuple[str, str]:
        role_l = str(role or "").casefold().replace(" ", "_").replace("-", "_")
        mapping = {
            "blade_tool": ("scissors", "snip"),
            "cut_tool": ("scissors", "snip"),
            "split_tool": ("scissors", "snip"),
            "select_tool": ("pointer", "click_pop"),
            "button": ("hand", "hover_breathe"),
            "primary_button": ("hand", "click_pop"),
            "text_field": ("ibeam", "text_focus"),
            "zoom_tool": ("zoom", "zoom_pulse"),
            "drag_handle": ("grab", "drag_trail"),
            "slider": ("grab", "drag_trail"),
            "trim_tool": ("trim", "trim_nudge"),
            "color_picker": ("color_picker", "pick"),
            "ai_tool": ("magic_ai", "spark"),
        }
        style, animation = mapping.get(role_l, ("pointer", ""))
        if not animation and str(kind or "").casefold() in {"click", "down", "release"}:
            animation = "click_pop"
        return style, animation

    @staticmethod
    def _classify_qt_widget_hit(pos) -> dict:
        """Return optional Smart Cursor FX metadata for TigerCapture's own UI."""
        try:
            widget = QApplication.widgetAt(pos)
        except Exception:
            widget = None
        if widget is None:
            return {}
        texts: list[str] = []
        role = ""
        hit_label = ""
        cur = widget
        for _ in range(6):
            if cur is None:
                break
            for attr in ("objectName", "toolTip", "accessibleName", "accessibleDescription"):
                try:
                    value = getattr(cur, attr)()
                except Exception:
                    value = ""
                if value:
                    texts.append(str(value))
            try:
                value = cur.property("cursor_fx_role")
            except Exception:
                value = None
            if value and not role:
                role = str(value)
            try:
                value = cur.property("tool_role")
            except Exception:
                value = None
            if value and not role:
                role = str(value)
            try:
                value = cur.text()
            except Exception:
                value = ""
            if value:
                texts.append(str(value))
                if not hit_label:
                    hit_label = str(value)
            cur = cur.parentWidget() if hasattr(cur, "parentWidget") else None
        joined = " ".join(texts).casefold()
        if not role:
            if any(token in joined for token in ("blade", "scissors", "cut", "split", "분할", "가위", "자르")):
                role = "blade_tool"
            elif any(token in joined for token in ("select", "선택")):
                role = "select_tool"
            elif any(token in joined for token in ("zoom", "줌", "확대")):
                role = "zoom_tool"
            elif any(token in joined for token in ("trim", "ripple", "roll", "slip", "slide")):
                role = "trim_tool"
            elif any(token in joined for token in ("color", "colour", "grade", "색", "컬러")):
                role = "color_picker"
            elif any(token in joined for token in ("ai", "assist", "magic", "프롬프트")):
                role = "ai_tool"
            elif any(token in joined for token in ("text", "caption", "title", "자막", "타이틀")):
                role = "text_field"
        try:
            class_name = widget.metaObject().className().casefold()
        except Exception:
            class_name = type(widget).__name__.casefold()
        if not role:
            if "lineedit" in class_name or "textedit" in class_name or "plaintextedit" in class_name:
                role = "text_field"
            elif "slider" in class_name or "spinbox" in class_name or "combobox" in class_name:
                role = "slider"
            elif "button" in class_name:
                role = "button"
        if not role:
            return {}
        style, animation = FrameRecorder._cursor_fx_for_role(role)
        return {
            "hit_role": role,
            "hit_label": hit_label[:80],
            "cursor_style": style,
            "animation": animation,
        }

    def _sample_cursor_event(self, elapsed_ms: int) -> None:
        if not self._include_cursor:
            return
        try:
            pos = QCursor.pos()
            rx = (pos.x() - self._rect.x()) / max(1, self._rect.width())
            ry = (pos.y() - self._rect.y()) / max(1, self._rect.height())
            visible = 0.0 <= rx <= 1.0 and 0.0 <= ry <= 1.0
            previous_down = bool(self._last_mouse_down)
            down = self._left_mouse_down()
            if down and not previous_down:
                kind = "click"
            elif down and previous_down:
                kind = "drag"
            elif previous_down and not down:
                kind = "release"
            else:
                kind = "move"
            event = {
                "t_ms": int(elapsed_ms),
                "x_norm": round(max(0.0, min(1.0, float(rx))), 5),
                "y_norm": round(max(0.0, min(1.0, float(ry))), 5),
                "kind": kind,
                "visible": bool(visible),
            }
            hit = self._classify_qt_widget_hit(pos) if visible else {}
            if hit:
                # Click/down/release events should use a click-specific
                # animation; hover/move events keep the softer role animation.
                style, animation = self._cursor_fx_for_role(str(hit.get("hit_role") or ""), kind=kind)
                hit["cursor_style"] = style
                hit["animation"] = animation or str(hit.get("animation") or "")
                event.update(hit)
            self._last_mouse_down = down
            self._sample_keyboard_event(elapsed_ms, event["x_norm"], event["y_norm"], visible)
            last = self._last_cursor_event
            if (
                last is not None
                and kind == "move"
                and last.get("kind") == "move"
                and last.get("hit_role", "") == event.get("hit_role", "")
                and last.get("cursor_style", "") == event.get("cursor_style", "")
                and abs(float(last.get("x_norm", 0.5)) - event["x_norm"]) < 0.002
                and abs(float(last.get("y_norm", 0.5)) - event["y_norm"]) < 0.002
                and int(event["t_ms"]) - int(last.get("t_ms", 0)) < 240
            ):
                return
            self._cursor_events.append(event)
            self._last_cursor_event = event
        except Exception as exc:
            _log(f"cursor sample failed: {exc}")

    def _write_cursor_sidecar(self, path: Path) -> None:
        if not self._cursor_events:
            return
        sidecar = Path(str(path) + ".cursor.json")
        payload = {
            "version": 2,
            "source": "tigercapture_recorder",
            "schema_features": ["cursor_fx_role", "cursor_style", "cursor_animation"],
            "include_cursor": bool(self._include_cursor),
            "rect": {
                "x": int(self._rect.x()),
                "y": int(self._rect.y()),
                "w": int(self._rect.width()),
                "h": int(self._rect.height()),
            },
            "fps": int(self._fps),
            "events": self._cursor_events,
        }
        try:
            sidecar.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            _log(f"cursor sidecar written → {sidecar}")
        except Exception as exc:
            _log(f"cursor sidecar write failed: {exc}")

    def _tick(self) -> None:
        if self._paused or self._stopped:
            return
        current = self._current_frame
        if current is None:
            return
        w, h = current.size
        if not self._ensure_encoder(w, h):
            return
        # Drop the rare frame whose dimensions don't match the encoder
        # input — happens if the source resolution changes mid-record.
        if self._enc_size != (w, h):
            return
        try:
            assert self._enc_proc is not None and self._enc_proc.stdin is not None
            self._enc_proc.stdin.write(current.tobytes())
        except (BrokenPipeError, ValueError, OSError) as exc:
            # ffmpeg has died — most likely it rejected the input
            # arguments at startup. Stop trying every frame and surface
            # the failure so the user gets an error dialog instead of
            # an ever-growing log of broken-pipe writes.
            _log(f"ffmpeg pipe write failed: {exc} — aborting capture")
            self._stopped = True
            self._tick_timer.stop()
            try:
                if self._wgc is not None:
                    self._wgc.stop()
            except Exception:
                pass
            self.error.emit(
                "Capture encoder died. Check logs/tigercapture.log for ffmpeg errors."
            )
            return
        self._frame_count += 1
        now = time.perf_counter()
        elapsed_ms = max(0, int((now - self._start_time - self._paused_total) * 1000))
        self._sample_cursor_event(elapsed_ms)
        n = self._frame_count
        if n == 1 or n % 30 == 0:
            _log(f"frame #{n} elapsed={elapsed_ms}ms")
        self.frame_captured.emit(n, elapsed_ms)
