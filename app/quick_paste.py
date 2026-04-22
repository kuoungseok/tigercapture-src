from __future__ import annotations

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from PySide6.QtGui import QGuiApplication


_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

_VK_CONTROL = 0x11
_VK_V = 0x56
_KEYEVENTF_KEYUP = 0x0002
_INPUT_KEYBOARD = 1
_SW_RESTORE = 9


def copy_file_to_clipboard(path: Path) -> None:
    """Place a file reference on the clipboard as CF_HDROP.

    Works with any editor that accepts paste-as-file-upload (Confluence,
    Jira, Slack, Discord, Kakao, Outlook, Office, Notion, ...).
    """
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    QGuiApplication.clipboard().setMimeData(mime)


def paste_into_window(hwnd: int, delay_s: float = 0.12) -> bool:
    """Bring ``hwnd`` to the foreground, then synthesize Ctrl+V.

    Returns True when SendInput reports the events were injected. False when
    ``hwnd`` is no longer a valid window.
    """
    if not hwnd or not _user32.IsWindow(hwnd):
        return False

    _focus_foreground(hwnd)
    time.sleep(delay_s)
    _send_ctrl_v()
    return True


def _focus_foreground(hwnd: int) -> None:
    """SetForegroundWindow has restrictions; use AttachThreadInput to bypass.
    Silently tolerates failures and falls back to SetForegroundWindow alone.
    """
    current_tid = _kernel32.GetCurrentThreadId()
    target_tid = _user32.GetWindowThreadProcessId(hwnd, None)
    attached = False
    if target_tid and current_tid != target_tid:
        attached = bool(_user32.AttachThreadInput(current_tid, target_tid, True))
    try:
        _user32.ShowWindow(hwnd, _SW_RESTORE)
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
        _user32.SetFocus(hwnd)
    finally:
        if attached:
            _user32.AttachThreadInput(current_tid, target_tid, False)


def _send_ctrl_v() -> None:
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", wintypes.WORD),
            ("wScan", wintypes.WORD),
            ("dwFlags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("padding", ctypes.c_char * 32)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]

    keys = [
        (_VK_CONTROL, 0),
        (_VK_V, 0),
        (_VK_V, _KEYEVENTF_KEYUP),
        (_VK_CONTROL, _KEYEVENTF_KEYUP),
    ]
    inputs = (INPUT * len(keys))()
    for i, (vk, flags) in enumerate(keys):
        inputs[i].type = _INPUT_KEYBOARD
        inputs[i].ki = KEYBDINPUT(
            wVk=vk, wScan=0, dwFlags=flags, time=0, dwExtraInfo=None
        )
    _user32.SendInput(len(keys), ctypes.byref(inputs), ctypes.sizeof(INPUT))
