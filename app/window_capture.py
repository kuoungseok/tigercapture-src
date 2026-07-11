"""External Windows application capture helpers.

This module is deliberately independent from the editor UI.  It backs the
Action/MCP surface for commands such as "capture Chrome" or "record OBS for
five seconds" without adding a new visible Tiger Studio panel.
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
import time
from typing import Any

from PIL import Image


PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9


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
    info = find_capture_window(
        title_contains=title_contains,
        process_contains=process_contains,
        pid=pid,
        hwnd=hwnd,
        include_invisible=False,
    )
    duration_value = max(1, min(300_000, _int(duration_ms, 3000)))
    fps_value = max(1, min(60, _int(fps, 15)))
    frame_count = max(1, int(round(duration_value / 1000.0 * fps_value)))
    out = Path(path or _default_capture_path("window_capture", ".mp4")).expanduser()
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
        stdout=subprocess.PIPE,
        **merge_hidden_subprocess_kwargs(),
    )
    assert proc.stdin is not None
    started = time.perf_counter()
    frames_written = 0
    try:
        for index in range(frame_count):
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
    return {
        "schema": "tigerstudio.capture.window_video.v1",
        "path": str(out.resolve()),
        "backend": backend_used,
        "encoder": "ffmpeg_rawvideo_libx264",
        "duration_ms": duration_value,
        "fps": fps_value,
        "frames": frames_written,
        "width": width,
        "height": height,
        "window": info.to_dict(),
    }


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
    if backend_text in {"", "auto", "visible", "pil", "crop"}:
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
    raise ValueError("backend must be auto, visible, pil, crop, mss, or printwindow")


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
