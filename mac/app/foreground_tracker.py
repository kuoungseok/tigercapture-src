"""macOS foreground tracker.

Polls the frontmost application via ``NSWorkspace`` and, when
Accessibility permission is granted, also resolves its focused window
title via the AX API. Keeps the same ``ForegroundInfo`` dataclass
shape + ``changed`` signal as the Windows version so the rest of the
app is platform-agnostic.

Without Accessibility permission, ``title`` falls back to empty and
``short_label`` shows just the app name — that's still enough for the
"paste into previous app" flow to work (CGEventPost + app activation).

Identifying "our own" windows: on Windows the controller passes HWNDs.
On macOS we don't have a sensible cross-boundary window handle, so we
treat "frontmost app == GifCam itself" as own-window by comparing the
frontmost app's bundle identifier / PID against the current process.
The controller's ``is_own_window`` callable is accepted but ignored.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import QObject, QTimer, Signal

try:
    from AppKit import NSWorkspace
    _HAS_APPKIT = True
except Exception:  # pragma: no cover — missing pyobjc in dev shell
    NSWorkspace = None  # type: ignore[assignment]
    _HAS_APPKIT = False

try:
    # Accessibility (AX*) lives in the ApplicationServices framework
    # (HIServices sub-framework). pyobjc exposes the symbols at the
    # top level of the ``ApplicationServices`` module.
    from ApplicationServices import (  # type: ignore[import-not-found]
        AXUIElementCreateApplication,
        AXUIElementCopyAttributeValue,
    )
    _HAS_AX = True
except Exception:  # pragma: no cover
    AXUIElementCreateApplication = None  # type: ignore[assignment]
    AXUIElementCopyAttributeValue = None  # type: ignore[assignment]
    _HAS_AX = False


@dataclass(frozen=True)
class ForegroundInfo:
    hwnd: int           # On macOS: PID of the frontmost application
    title: str          # Focused window title (may be empty without AX perm)
    process_name: str   # App localized name, e.g. "Safari"

    @property
    def short_label(self) -> str:
        if not self.process_name and not self.title:
            return ""
        if not self.title:
            return self.process_name
        trimmed_title = self.title[:40] + "…" if len(self.title) > 40 else self.title
        if not self.process_name:
            return trimmed_title
        return f"{self.process_name}  —  {trimmed_title}"


class ForegroundTracker(QObject):
    """Polls NSWorkspace frontmostApplication at ~200 ms.

    ``is_own_window`` is accepted for API compatibility with the Windows
    version but ignored: on macOS we check PID equality against the
    current process instead.
    """

    changed = Signal(object)  # ForegroundInfo | None

    def __init__(
        self,
        is_own_window=None,  # unused on macOS; kept for signature parity
        parent: QObject | None = None,
        interval_ms: int = 200,
    ) -> None:
        super().__init__(parent)
        _ = is_own_window
        self._own_pid = os.getpid()
        self._last_other: ForegroundInfo | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def last_other(self) -> ForegroundInfo | None:
        return self._last_other

    def _poll(self) -> None:
        if not _HAS_APPKIT:
            return
        try:
            ws = NSWorkspace.sharedWorkspace()
            app = ws.frontmostApplication()
            if app is None:
                return
            pid = int(app.processIdentifier())
            if pid == self._own_pid:
                return
            name = str(app.localizedName() or "")
            title = _frontmost_window_title(pid) if _HAS_AX else ""
            info = ForegroundInfo(hwnd=pid, title=title, process_name=name)
        except Exception:
            return

        if info != self._last_other:
            self._last_other = info
            self.changed.emit(info)


def _frontmost_window_title(pid: int) -> str:
    """Use the Accessibility API to read the focused window's title.

    Returns "" when the AX permission hasn't been granted (first launch)
    or when the app provides no title. Never raises.
    """
    if not _HAS_AX:
        return ""
    try:
        app_ref = AXUIElementCreateApplication(pid)
        if app_ref is None:
            return ""
        err, window = AXUIElementCopyAttributeValue(
            app_ref, "AXFocusedWindow", None
        )
        if err != 0 or window is None:
            return ""
        err, title = AXUIElementCopyAttributeValue(
            window, "AXTitle", None
        )
        if err != 0 or title is None:
            return ""
        return str(title)
    except Exception:
        return ""
