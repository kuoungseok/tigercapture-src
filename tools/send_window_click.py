"""Bring a window to foreground and send a mouse click at a normalized point."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import time


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a mouse click to a visible window.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--x", type=float, required=True, help="Normalized client x, 0..1")
    parser.add_argument("--y", type=float, required=True, help="Normalized client y, 0..1")
    parser.add_argument("--double", action="store_true", dest="double_click")
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    hwnd = _find_window_by_pid(args.pid)
    if not hwnd:
        print({"ok": False, "error": "window_not_found"})
        return 2
    rect = _window_rect(hwnd)
    if rect[2] <= rect[0] or rect[3] <= rect[1]:
        print({"ok": False, "error": "invalid_window_rect", "hwnd": hwnd, "rect": rect})
        return 2

    x_norm = min(1.0, max(0.0, args.x))
    y_norm = min(1.0, max(0.0, args.y))
    left, top, right, bottom = rect
    x = int(left + (right - left) * x_norm)
    y = int(top + (bottom - top) * y_norm)

    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(args.delay)
    _click(x, y)
    if args.double_click:
        time.sleep(0.08)
        _click(x, y)
    print({"ok": True, "hwnd": hwnd, "rect": rect, "x": x, "y": y, "normalized": [x_norm, y_norm], "double": args.double_click})
    return 0


def _find_window_by_pid(pid: int) -> int:
    user32 = ctypes.windll.user32
    matches: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        window_pid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if int(window_pid.value) == int(pid):
            matches.append(int(hwnd))
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return matches[0] if matches else 0


def _window_rect(hwnd: int) -> list[int]:
    user32 = ctypes.windll.user32
    rect = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return [int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])]


def _click(x: int, y: int) -> None:
    user32 = ctypes.windll.user32
    user32.SetCursorPos(x, y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


if __name__ == "__main__":
    raise SystemExit(main())
