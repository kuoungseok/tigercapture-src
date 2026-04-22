from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal


_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
_user32.GetWindowThreadProcessId.restype = wintypes.DWORD


@dataclass(frozen=True)
class ForegroundInfo:
    hwnd: int
    title: str
    process_name: str

    @property
    def short_label(self) -> str:
        """Short display text like 'chrome.exe' or 'chrome.exe — <page title>'."""
        if not self.process_name and not self.title:
            return ""
        if not self.title:
            return self.process_name
        trimmed_title = self.title[:40] + "…" if len(self.title) > 40 else self.title
        if not self.process_name:
            return trimmed_title
        return f"{self.process_name}  —  {trimmed_title}"


class ForegroundTracker(QObject):
    """Polls the Windows foreground window at ~200 ms and remembers the last
    non-owned window so it can be used as a "paste target" later.

    Owners identify their own top-level windows by passing a predicate that
    returns True for HWNDs belonging to this app.
    """

    changed = Signal(object)  # ForegroundInfo | None

    def __init__(
        self,
        is_own_window,  # Callable[[int], bool]
        parent: QObject | None = None,
        interval_ms: int = 200,
    ) -> None:
        super().__init__(parent)
        self._is_own = is_own_window
        self._last_other: ForegroundInfo | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def last_other(self) -> ForegroundInfo | None:
        return self._last_other

    def _poll(self) -> None:
        try:
            hwnd = _user32.GetForegroundWindow()
        except Exception:
            return
        if not hwnd:
            return
        try:
            if self._is_own(int(hwnd)):
                return
        except Exception:
            return

        title = _window_title(hwnd)
        process_name = _window_process_name(hwnd)
        info = ForegroundInfo(
            hwnd=int(hwnd), title=title, process_name=process_name
        )
        if info != self._last_other:
            self._last_other = info
            self.changed.emit(info)


def _window_title(hwnd: int) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value or ""


def _window_process_name(hwnd: int) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
    finally:
        _kernel32.CloseHandle(handle)
    return ""
