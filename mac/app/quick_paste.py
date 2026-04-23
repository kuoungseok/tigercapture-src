"""macOS quick-paste: drop a file onto the clipboard and simulate
⌘V into the previously-focused application.

- ``copy_file_to_clipboard`` uses the same Qt MIME path the Windows
  version does — most macOS apps that accept dropped/pasted files can
  read the ``file://`` URL from ``NSPasteboard``.
- ``paste_into_window`` activates the target app by PID via
  ``NSRunningApplication.activateWithOptions_`` and synthesizes ⌘V via
  ``CGEventPost``. Requires Accessibility permission — without it,
  CGEventPost silently fails and no paste happens.

The ``hwnd`` parameter is repurposed on macOS: the Windows version
stored a real HWND there; here we store the PID of the target app (see
``foreground_tracker.py``).
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QGuiApplication

try:
    from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
    _HAS_APPKIT = True
except Exception:
    NSRunningApplication = None  # type: ignore[assignment]
    NSApplicationActivateIgnoringOtherApps = 1 << 1  # fallback literal
    _HAS_APPKIT = False

try:
    from Quartz import (
        CGEventCreateKeyboardEvent,
        CGEventPost,
        CGEventSetFlags,
        kCGEventFlagMaskCommand,
        kCGHIDEventTap,
    )
    _HAS_QUARTZ = True
except Exception:
    _HAS_QUARTZ = False

# macOS virtual keycode for 'v'
_KC_V = 9


def copy_file_to_clipboard(path: Path) -> None:
    """Place a file URL on the clipboard.

    Uses Qt's cross-platform clipboard so macOS apps read the file from
    NSPasteboard's NSFilenamesPboardType / public.file-url.
    """
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    QGuiApplication.clipboard().setMimeData(mime)


def paste_into_window(hwnd: int, delay_s: float = 0.15) -> bool:
    """Activate target app (identified by PID in ``hwnd``) and send ⌘V.

    Returns True when the keystroke was posted; False when we couldn't
    resolve / activate the app. Silently degrades if Accessibility
    permission hasn't been granted (keystroke is posted but the OS
    drops it — the user will see the app activate but nothing pasted).
    """
    if not hwnd:
        return False

    if _HAS_APPKIT:
        try:
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(
                int(hwnd)
            )
            if app is None:
                return False
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        except Exception:
            return False
    else:
        return False

    # Brief settle after activation before synthesizing the shortcut,
    # otherwise the first app's responder chain can miss the key.
    time.sleep(delay_s)

    if not _HAS_QUARTZ:
        return False
    try:
        down = CGEventCreateKeyboardEvent(None, _KC_V, True)
        up = CGEventCreateKeyboardEvent(None, _KC_V, False)
        CGEventSetFlags(down, kCGEventFlagMaskCommand)
        CGEventSetFlags(up, kCGEventFlagMaskCommand)
        CGEventPost(kCGHIDEventTap, down)
        CGEventPost(kCGHIDEventTap, up)
        return True
    except Exception:
        return False
