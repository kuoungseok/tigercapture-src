"""External Windows application capture helpers.

This module is deliberately independent from the editor UI.  It backs the
Action/MCP surface for commands such as "capture Chrome" or "record an
external tool window for five seconds" without adding a new visible Tiger
Studio panel.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any
from uuid import uuid4

from PIL import Image


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
MAX_WINDOW_VIDEO_DURATION_MS = 300_000
MAX_WINDOW_VIDEO_SESSION_MS = 14_400_000
DEFAULT_WINDOW_VIDEO_SESSION_MS = 600_000
WGC_WINDOW_BACKENDS = {"wgc", "wgc_window", "windows_capture", "window_wgc"}
VISIBLE_WINDOW_BACKENDS = {"visible", "pil", "crop"}


@dataclass(frozen=True)
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    process_name: str
    process_path: str
    rect: tuple[int, int, int, int]
    visible: bool
    minimized: bool

    @property
    def width(self) -> int:
        return max(0, int(self.rect[2]) - int(self.rect[0]))

    @property
    def height(self) -> int:
        return max(0, int(self.rect[3]) - int(self.rect[1]))

    def to_dict(self) -> dict[str, Any]:
        return {
            "hwnd": int(self.hwnd),
            "title": self.title,
            "pid": int(self.pid),
            "process_name": self.process_name,
            "process_path": self.process_path,
            "rect": list(self.rect),
            "width": self.width,
            "height": self.height,
            "visible": bool(self.visible),
            "minimized": bool(self.minimized),
        }


@dataclass
class WindowVideoCaptureSession:
    session_id: str
    path: Path
    started_at: float
    requested_max_duration_ms: int
    fps: int
    backend: str
    window: dict[str, Any]
    stop_event: threading.Event
    done_event: threading.Event
    thread: threading.Thread | None = None
    status: str = "starting"
    result: dict[str, Any] | None = None
    error: str = ""
    finished_at: float = 0.0


_window_video_sessions: dict[str, WindowVideoCaptureSession] = {}
_window_video_sessions_lock = threading.RLock()


def list_capture_windows(
    *,
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    include_invisible: bool = False,
    limit: int = 100,
) -> dict[str, Any]:
    """Return visible top-level Windows windows matching optional filters."""

    if os.name != "nt":
        return {
            "schema": "tigerstudio.capture.windows.v1",
            "platform_supported": False,
            "windows": [],
            "count": 0,
        }
    rows = _enumerate_windows(include_invisible=bool(include_invisible))
    filtered: list[WindowInfo] = []
    for row in rows:
        if not _matches_window(row, title_contains=title_contains, process_contains=process_contains, pid=pid):
            continue
        if row.width <= 0 or row.height <= 0:
            continue
        filtered.append(row)
    cap = max(1, min(500, _int(limit, 100)))
    return {
        "schema": "tigerstudio.capture.windows.v1",
        "platform_supported": True,
        "count": len(filtered),
        "windows": [row.to_dict() for row in filtered[:cap]],
    }


def save_window_screenshot(
    *,
    path: str | Path = "",
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    hwnd: int = 0,
    backend: str = "auto",
    activate: bool = False,
) -> dict[str, Any]:
    info = find_capture_window(
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        hwnd=hwnd,
        include_invisible=False,
    )
    image, backend_used = capture_window_image(info.hwnd, backend=backend, activate=activate)
    out = Path(path or _default_capture_path("window_screenshot", ".png")).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    return {
        "schema": "tigerstudio.capture.window_screenshot.v1",
        "path": str(out.resolve()),
        "backend": backend_used,
        "window": info.to_dict(),
    }


def record_window_video(
    *,
    path: str | Path = "",
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    hwnd: int = 0,
    duration_ms: int = 3000,
    fps: int = 15,
    backend: str = "auto",
    activate: bool = False,
    crf: int = 23,
) -> dict[str, Any]:
    return _record_window_video_frames(
        path=path,
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        hwnd=hwnd,
        duration_ms=duration_ms,
        fps=fps,
        backend=backend,
        activate=activate,
        crf=crf,
        stop_event=None,
        session_id="",
        max_duration_ms=MAX_WINDOW_VIDEO_DURATION_MS,
        report_requested_duration=True,
    )


def start_window_video_capture(
    *,
    session_id: str = "",
    path: str | Path = "",
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    hwnd: int = 0,
    max_duration_ms: int = DEFAULT_WINDOW_VIDEO_SESSION_MS,
    fps: int = 15,
    backend: str = "auto",
    activate: bool = False,
    crf: int = 23,
) -> dict[str, Any]:
    """Start an ownerless external-window recording session.

    The caller stops it later with :func:`stop_window_video_capture`.  A hard
    max duration is still required so MCP/AI callers cannot leave ffmpeg running
    indefinitely if the external workflow never reports completion.
    """

    info = find_capture_window(
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        hwnd=hwnd,
        include_invisible=False,
    )
    session_key = _session_id(session_id)
    duration_value = max(1, min(MAX_WINDOW_VIDEO_SESSION_MS, _int(max_duration_ms, DEFAULT_WINDOW_VIDEO_SESSION_MS)))
    fps_value = max(1, min(60, _int(fps, 15)))
    out = _normalize_video_path(path or _default_capture_path("window_capture_session", ".mp4"))
    stop_event = threading.Event()
    done_event = threading.Event()
    session = WindowVideoCaptureSession(
        session_id=session_key,
        path=out,
        started_at=time.time(),
        requested_max_duration_ms=duration_value,
        fps=fps_value,
        backend=str(backend or "auto"),
        window=info.to_dict(),
        stop_event=stop_event,
        done_event=done_event,
    )

    with _window_video_sessions_lock:
        existing = _window_video_sessions.get(session_key)
        if existing is not None and existing.thread is not None and existing.thread.is_alive():
            raise RuntimeError(f"capture session already running: {session_key}")
        _window_video_sessions[session_key] = session

    def _run() -> None:
        session.status = "recording"
        try:
            session.result = _record_window_video_frames(
                path=out,
                title_contains="",
                process_contains="",
                pid=0,
                hwnd=info.hwnd,
                duration_ms=duration_value,
                fps=fps_value,
                backend=backend,
                activate=activate,
                crf=crf,
                stop_event=stop_event,
                session_id=session_key,
                max_duration_ms=MAX_WINDOW_VIDEO_SESSION_MS,
                report_requested_duration=False,
            )
            stopped_by = str((session.result or {}).get("stopped_by") or "")
            if stopped_by == "request":
                session.status = "stopped"
            elif stopped_by == "source_closed":
                session.status = "source_closed"
            else:
                session.status = "completed"
        except Exception as exc:
            session.error = str(exc)
            session.status = "failed"
        finally:
            session.finished_at = time.time()
            done_event.set()

    thread = threading.Thread(
        target=_run,
        name=f"TigerCaptureWindowVideo-{session_key}",
        daemon=True,
    )
    session.thread = thread
    thread.start()
    return {
        "schema": "tigerstudio.capture.window_video_session.v1",
        "session_id": session_key,
        "status": session.status,
        "path": str(out.resolve()),
        "max_duration_ms": duration_value,
        "fps": fps_value,
        "backend": str(backend or "auto"),
        "stop_policy": "call capture.window.video.stop; hard timeout stops at max_duration_ms",
        "window": info.to_dict(),
    }


def stop_window_video_capture(
    *,
    session_id: str = "",
    wait_ms: int = 30_000,
) -> dict[str, Any]:
    session = _resolve_window_video_session(session_id)
    session.stop_event.set()
    wait_value = max(0, min(120_000, _int(wait_ms, 30_000)))
    thread = session.thread
    if thread is not None and wait_value > 0:
        thread.join(wait_value / 1000.0)
    return window_video_capture_status(session_id=session.session_id)


def window_video_capture_status(*, session_id: str = "") -> dict[str, Any]:
    with _window_video_sessions_lock:
        if session_id:
            session = _window_video_sessions.get(_session_id(session_id))
            if session is None:
                raise RuntimeError(f"capture session not found: {session_id}")
            return {
                "schema": "tigerstudio.capture.window_video_session_status.v1",
                "sessions": [_session_status_dict(session)],
                "count": 1,
            }
        sessions = [_session_status_dict(row) for row in _window_video_sessions.values()]
    return {
        "schema": "tigerstudio.capture.window_video_session_status.v1",
        "sessions": sessions,
        "count": len(sessions),
    }


def _record_window_video_frames(
    *,
    path: str | Path = "",
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    hwnd: int = 0,
    duration_ms: int = 3000,
    fps: int = 15,
    backend: str = "auto",
    activate: bool = False,
    crf: int = 23,
    stop_event: threading.Event | None = None,
    session_id: str = "",
    max_duration_ms: int = MAX_WINDOW_VIDEO_DURATION_MS,
    report_requested_duration: bool = True,
) -> dict[str, Any]:
    info = find_capture_window(
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        hwnd=hwnd,
        include_invisible=False,
    )
    backend_text = str(backend or "auto").strip().lower()
    if backend_text in WGC_WINDOW_BACKENDS or (backend_text in {"", "auto"} and _prefer_wgc_window(info)):
        try:
            return _record_window_video_wgc(
                info=info,
                path=path,
                duration_ms=duration_ms,
                fps=fps,
                activate=activate,
                crf=crf,
                stop_event=stop_event,
                session_id=session_id,
                max_duration_ms=max_duration_ms,
                report_requested_duration=report_requested_duration,
            )
        except Exception:
            if backend_text in WGC_WINDOW_BACKENDS:
                raise
    duration_value = max(1, min(max(1, _int(max_duration_ms, MAX_WINDOW_VIDEO_DURATION_MS)), _int(duration_ms, 3000)))
    fps_value = max(1, min(60, _int(fps, 15)))
    frame_count = max(1, int(round(duration_value / 1000.0 * fps_value)))
    out = _normalize_video_path(path or _default_capture_path("window_capture", ".mp4"))
    if out.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        out = out.with_suffix(".mp4")
    out.parent.mkdir(parents=True, exist_ok=True)

    first, backend_used = capture_window_image(info.hwnd, backend=backend, activate=activate)
    first = first.convert("RGB")
    width, height = _even_size(first.width, first.height)
    if (first.width, first.height) != (width, height):
        first = first.resize((width, height), Image.Resampling.BICUBIC)

    ffmpeg = _ffmpeg_exe()
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{width}x{height}",
        "-r",
        str(fps_value),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        str(max(0, min(51, _int(crf, 23)))),
        "-pix_fmt",
        "yuv420p",
        str(out),
    ]

    from app.subprocess_utils import merge_hidden_subprocess_kwargs

    proc = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        **merge_hidden_subprocess_kwargs(),
    )
    assert proc.stdin is not None
    started = time.perf_counter()
    frames_written = 0
    stopped_by = "duration"
    try:
        for index in range(frame_count):
            if stop_event is not None and stop_event.is_set() and frames_written > 0:
                stopped_by = "request"
                break
            frame = first if index == 0 else capture_window_image(info.hwnd, backend=backend, activate=False)[0]
            if frame.mode != "RGB":
                frame = frame.convert("RGB")
            if frame.size != (width, height):
                frame = frame.resize((width, height), Image.Resampling.BICUBIC)
            proc.stdin.write(frame.tobytes("raw", "RGB"))
            frames_written += 1
            target_time = started + ((index + 1) / float(fps_value))
            sleep_for = target_time - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    stderr = b""
    try:
        stderr = proc.stderr.read() if proc.stderr is not None else b""
    except Exception:
        stderr = b""
    code = proc.wait(timeout=30)
    if code != 0:
        tail = stderr.decode("utf-8", errors="replace")[-1600:]
        raise RuntimeError(tail or f"ffmpeg exited {code}")
    actual_duration_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
    return {
        "schema": "tigerstudio.capture.window_video.v1",
        "path": str(out.resolve()),
        "backend": backend_used,
        "encoder": "ffmpeg_rawvideo_libx264",
        "duration_ms": duration_value if report_requested_duration else actual_duration_ms,
        "requested_duration_ms": duration_value,
        "actual_duration_ms": actual_duration_ms,
        "fps": fps_value,
        "frames": frames_written,
        "width": width,
        "height": height,
        "stopped_by": stopped_by,
        "session_id": str(session_id or ""),
        "window": info.to_dict(),
    }


def _record_window_video_wgc(
    *,
    info: WindowInfo,
    path: str | Path = "",
    duration_ms: int = 3000,
    fps: int = 15,
    activate: bool = False,
    crf: int = 23,
    stop_event: threading.Event | None = None,
    session_id: str = "",
    max_duration_ms: int = MAX_WINDOW_VIDEO_DURATION_MS,
    report_requested_duration: bool = True,
) -> dict[str, Any]:
    if activate:
        _activate_window(info.hwnd)
        time.sleep(0.08)
    duration_value = max(1, min(max(1, _int(max_duration_ms, MAX_WINDOW_VIDEO_DURATION_MS)), _int(duration_ms, 3000)))
    fps_value = max(1, min(60, _int(fps, 15)))
    frame_count = max(1, int(round(duration_value / 1000.0 * fps_value)))
    out = _normalize_video_path(path or _default_capture_path("window_capture", ".mp4"))
    out.parent.mkdir(parents=True, exist_ok=True)

    source = _WgcWindowFrameSource(info.hwnd)
    source.start()
    try:
        first = source.wait_for_first_frame(timeout_s=3.0).convert("RGB")
        width, height = _even_size(first.width, first.height)
        if (first.width, first.height) != (width, height):
            first = first.resize((width, height), Image.Resampling.BICUBIC)

        ffmpeg = _ffmpeg_exe()
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps_value),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            str(max(0, min(51, _int(crf, 23)))),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]

        from app.subprocess_utils import merge_hidden_subprocess_kwargs

        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            **merge_hidden_subprocess_kwargs(),
        )
        assert proc.stdin is not None
        started = time.perf_counter()
        frames_written = 0
        stopped_by = "duration"
        last = first
        try:
            for index in range(frame_count):
                if stop_event is not None and stop_event.is_set() and frames_written > 0:
                    stopped_by = "request"
                    break
                source_error = source.error_message()
                if source_error:
                    raise RuntimeError(source_error)
                if source.is_closed() and frames_written > 0:
                    stopped_by = "source_closed"
                    break
                if index == 0:
                    frame = first
                else:
                    frame = source.latest_frame() or last
                if frame.mode != "RGB":
                    frame = frame.convert("RGB")
                if frame.size != (width, height):
                    frame = frame.resize((width, height), Image.Resampling.BICUBIC)
                last = frame
                proc.stdin.write(frame.tobytes("raw", "RGB"))
                frames_written += 1
                target_time = started + ((index + 1) / float(fps_value))
                sleep_for = target_time - time.perf_counter()
                if sleep_for > 0:
                    time.sleep(sleep_for)
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass
        stderr = b""
        try:
            stderr = proc.stderr.read() if proc.stderr is not None else b""
        except Exception:
            stderr = b""
        code = proc.wait(timeout=30)
        if code != 0:
            tail = stderr.decode("utf-8", errors="replace")[-1600:]
            raise RuntimeError(tail or f"ffmpeg exited {code}")
        actual_duration_ms = max(0, int(round((time.perf_counter() - started) * 1000)))
        return {
            "schema": "tigerstudio.capture.window_video.v1",
            "path": str(out.resolve()),
            "backend": "wgc_window",
            "encoder": "ffmpeg_rawvideo_libx264",
            "duration_ms": duration_value if report_requested_duration else actual_duration_ms,
            "requested_duration_ms": duration_value,
            "actual_duration_ms": actual_duration_ms,
            "fps": fps_value,
            "frames": frames_written,
            "width": width,
            "height": height,
            "stopped_by": stopped_by,
            "session_id": str(session_id or ""),
            "window": info.to_dict(),
        }
    finally:
        source.stop()


def find_capture_window(
    *,
    title_contains: str = "",
    process_contains: str = "",
    pid: int = 0,
    hwnd: int = 0,
    include_invisible: bool = False,
) -> WindowInfo:
    if os.name != "nt":
        raise RuntimeError("external window capture is only available on Windows")
    hwnd_value = _int(hwnd, 0)
    if hwnd_value:
        info = _window_info(hwnd_value)
        if info is None:
            raise RuntimeError(f"window handle not found: {hwnd_value}")
        if not include_invisible and not info.visible:
            raise RuntimeError(f"window is not visible: {hwnd_value}")
        return info
    matches = list_capture_windows(
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        include_invisible=include_invisible,
        limit=20,
    )["windows"]
    if not matches:
        label = title_contains or process_contains or (str(pid) if pid else "window")
        raise RuntimeError(f"capture window not found: {label}")
    first = matches[0]
    return WindowInfo(
        hwnd=_int(first.get("hwnd"), 0),
        title=str(first.get("title") or ""),
        pid=_int(first.get("pid"), 0),
        process_name=str(first.get("process_name") or ""),
        process_path=str(first.get("process_path") or ""),
        rect=tuple(int(v) for v in list(first.get("rect") or [0, 0, 0, 0])[:4]),  # type: ignore[arg-type]
        visible=bool(first.get("visible", True)),
        minimized=bool(first.get("minimized", False)),
    )


def capture_window_image(hwnd: int, *, backend: str = "auto", activate: bool = False) -> tuple[Image.Image, str]:
    info = find_capture_window(hwnd=_int(hwnd, 0), include_invisible=True)
    if activate:
        _activate_window(info.hwnd)
        time.sleep(0.08)
        info = find_capture_window(hwnd=info.hwnd, include_invisible=True)
    if info.minimized:
        raise RuntimeError("window is minimized; restore it or pass activate=true")
    if info.width <= 0 or info.height <= 0:
        raise RuntimeError(f"invalid window rect: {info.rect}")

    backend_text = str(backend or "auto").strip().lower()
    if backend_text in WGC_WINDOW_BACKENDS:
        return _capture_wgc_window_frame(info.hwnd), "wgc_window"
    if backend_text in {"", "auto"} and _prefer_wgc_window(info):
        try:
            return _capture_wgc_window_frame(info.hwnd), "wgc_window"
        except Exception:
            pass
    if backend_text in {"", "auto", *VISIBLE_WINDOW_BACKENDS}:
        try:
            return _capture_visible_crop(info.rect), "visible_crop"
        except Exception:
            if backend_text not in {"", "auto"}:
                raise
            return _capture_printwindow(info.hwnd), "printwindow"
    if backend_text == "printwindow":
        return _capture_printwindow(info.hwnd), "printwindow"
    if backend_text == "mss":
        return _capture_mss(info.rect), "mss"
    raise ValueError("backend must be auto, wgc_window, visible, pil, crop, mss, or printwindow")


class _WgcWindowFrameSource:
    def __init__(self, hwnd: int) -> None:
        self.hwnd = int(hwnd)
        self._lock = threading.Lock()
        self._first_frame = threading.Event()
        self._closed = threading.Event()
        self._wgc = None
        self._latest: Image.Image | None = None
        self._error = ""
        self._stop_requested = False

    def start(self) -> None:
        try:
            from windows_capture import WindowsCapture
        except Exception as exc:
            raise RuntimeError("windows-capture is required for wgc_window backend") from exc

        wgc = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            window_hwnd=self.hwnd,
        )
        source = self

        @wgc.event
        def on_frame_arrived(frame, control):
            if source._stop_requested:
                try:
                    control.stop()
                except Exception:
                    pass
                return
            try:
                image = _wgc_frame_to_image(frame)
            except Exception as exc:
                source._error = str(exc)
                source._first_frame.set()
                source._closed.set()
                try:
                    control.stop()
                except Exception:
                    pass
                return
            with source._lock:
                source._latest = image
            source._first_frame.set()

        @wgc.event
        def on_closed():
            source._closed.set()

        self._wgc = wgc
        wgc.start_free_threaded()

    def wait_for_first_frame(self, timeout_s: float = 3.0) -> Image.Image:
        if not self._first_frame.wait(max(0.1, float(timeout_s))):
            raise RuntimeError("wgc_window timed out waiting for first frame")
        if self._error:
            raise RuntimeError(self._error)
        frame = self.latest_frame()
        if frame is None:
            raise RuntimeError("wgc_window produced no frame")
        return frame

    def latest_frame(self) -> Image.Image | None:
        with self._lock:
            if self._latest is None:
                return None
            return self._latest.copy()

    def is_closed(self) -> bool:
        return self._closed.is_set()

    def error_message(self) -> str:
        return str(self._error or "")

    def stop(self) -> None:
        self._stop_requested = True
        wgc = self._wgc
        if wgc is not None:
            try:
                wgc.stop()
            except Exception:
                pass
        self._closed.wait(0.5)


def _enumerate_windows(*, include_invisible: bool) -> list[WindowInfo]:
    user32 = ctypes.windll.user32
    rows: list[WindowInfo] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        info = _window_info(int(hwnd))
        if info is None:
            return True
        if not include_invisible and not info.visible:
            return True
        if not info.title.strip():
            return True
        rows.append(info)
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return rows


def _window_info(hwnd: int) -> WindowInfo | None:
    if os.name != "nt" or not hwnd:
        return None
    user32 = ctypes.windll.user32
    if not user32.IsWindow(hwnd):
        return None
    title = _window_title(hwnd)
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    rect = _window_rect(hwnd)
    process_path = _query_process_path(int(pid.value))
    process_name = Path(process_path).name if process_path else ""
    return WindowInfo(
        hwnd=int(hwnd),
        title=title,
        pid=int(pid.value),
        process_name=process_name,
        process_path=process_path,
        rect=rect,
        visible=bool(user32.IsWindowVisible(hwnd)),
        minimized=bool(user32.IsIconic(hwnd)),
    )


def _window_title(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = max(0, int(user32.GetWindowTextLengthW(hwnd)))
    buffer = ctypes.create_unicode_buffer(length + 1 if length else 512)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return str(buffer.value or "")


def _window_rect(hwnd: int) -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    rect = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return (int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3]))


def _query_process_path(pid: int) -> str:
    if os.name != "nt" or not pid:
        return ""
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        size = wt.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return str(buffer.value if ok else "")
    except Exception:
        return ""
    finally:
        kernel32.CloseHandle(handle)


def _matches_window(info: WindowInfo, *, title_contains: str, process_contains: str, pid: int) -> bool:
    title_needle = str(title_contains or "").strip().casefold()
    process_needle = str(process_contains or "").strip().casefold()
    pid_value = _int(pid, 0)
    if title_needle and title_needle not in info.title.casefold():
        return False
    if process_needle:
        haystack = f"{info.process_name} {info.process_path}".casefold()
        if process_needle not in haystack:
            return False
    if pid_value and int(info.pid) != pid_value:
        return False
    return True


def _activate_window(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass


def _capture_visible_crop(rect: tuple[int, int, int, int]) -> Image.Image:
    from PIL import ImageGrab

    left, top, right, bottom = rect
    return ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).convert("RGB")


def _capture_mss(rect: tuple[int, int, int, int]) -> Image.Image:
    import mss

    left, top, right, bottom = rect
    with mss.mss() as sct:
        shot = sct.grab({"left": left, "top": top, "width": right - left, "height": bottom - top})
    return Image.frombytes("RGB", shot.size, shot.rgb)


def _capture_wgc_window_frame(hwnd: int) -> Image.Image:
    source = _WgcWindowFrameSource(_int(hwnd, 0))
    source.start()
    try:
        return source.wait_for_first_frame(timeout_s=3.0)
    finally:
        source.stop()


def _wgc_frame_to_image(frame: Any) -> Image.Image:
    import numpy as np

    buf = frame.frame_buffer
    if len(buf.shape) < 3 or buf.shape[2] < 3:
        raise RuntimeError("wgc_window frame buffer is not RGB/BGRA")
    rgb = np.ascontiguousarray(buf[:, :, [2, 1, 0]])
    return Image.fromarray(rgb, "RGB")


def _prefer_wgc_window(info: WindowInfo) -> bool:
    haystack = f"{info.title} {info.process_name} {info.process_path}".casefold()
    return any(
        token in haystack
        for token in (
            "unrealeditor",
            "unreal editor",
            "ue4editor",
            "ue5editor",
        )
    )


def _capture_printwindow(hwnd: int) -> Image.Image:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    left, top, right, bottom = _window_rect(hwnd)
    width, height = max(1, right - left), max(1, bottom - top)
    hwnd_dc = user32.GetWindowDC(hwnd)
    mem_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bitmap = gdi32.CreateCompatibleBitmap(hwnd_dc, width, height)
    old_obj = gdi32.SelectObject(mem_dc, bitmap)
    try:
        user32.PrintWindow(hwnd, mem_dc, 2)
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(bmi), 0)
        return Image.frombuffer("RGBA", (width, height), buffer, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi32.SelectObject(mem_dc, old_obj)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(hwnd, hwnd_dc)


def _ffmpeg_exe() -> str:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe

        return str(Path(get_ffmpeg_exe()).resolve())
    except Exception:
        return "ffmpeg"


def _default_capture_path(prefix: str, suffix: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("debugCapture") / f"{prefix}_{stamp}{suffix}"


def _normalize_video_path(path: str | Path) -> Path:
    out = Path(path).expanduser()
    if out.suffix.lower() not in {".mp4", ".mov", ".mkv"}:
        out = out.with_suffix(".mp4")
    return out


def _session_id(value: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        raw = f"window_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in raw)
    return cleaned[:96] or f"window_capture_{uuid4().hex[:8]}"


def _resolve_window_video_session(session_id: str = "") -> WindowVideoCaptureSession:
    with _window_video_sessions_lock:
        if session_id:
            session = _window_video_sessions.get(_session_id(session_id))
            if session is None:
                raise RuntimeError(f"capture session not found: {session_id}")
            return session
        active = [
            row
            for row in _window_video_sessions.values()
            if row.thread is not None and row.thread.is_alive()
        ]
        if len(active) == 1:
            return active[0]
        if not active:
            raise RuntimeError("no active capture session")
        raise RuntimeError("multiple active capture sessions; pass session_id")


def _session_status_dict(session: WindowVideoCaptureSession) -> dict[str, Any]:
    thread = session.thread
    running = bool(thread is not None and thread.is_alive())
    elapsed_ms = max(0, int(round((time.time() - session.started_at) * 1000)))
    result = dict(session.result or {})
    error = str(session.error or "")
    return {
        "session_id": session.session_id,
        "status": "recording" if running and session.status in {"starting", "recording"} else session.status,
        "running": running,
        "path": str(session.path.resolve()),
        "elapsed_ms": elapsed_ms,
        "max_duration_ms": int(session.requested_max_duration_ms),
        "fps": int(session.fps),
        "backend": session.backend,
        "window": dict(session.window or {}),
        "result": result,
        "error": error,
    }


def _even_size(width: int, height: int) -> tuple[int, int]:
    return max(2, int(width) - int(width) % 2), max(2, int(height) - int(height) % 2)


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD),
        ("biWidth", wt.LONG),
        ("biHeight", wt.LONG),
        ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD),
        ("biCompression", wt.DWORD),
        ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG),
        ("biYPelsPerMeter", wt.LONG),
        ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]
