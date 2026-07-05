"""Bring a window to foreground and send a simple hotkey."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import time


VK = {
    "ctrl": 0x11,
    "shift": 0x10,
    "alt": 0x12,
    "esc": 0x1B,
    "enter": 0x0D,
    "space": 0x20,
    "f7": 0x76,
    "f1": 0x70,
}
VK.update({chr(code): code for code in range(ord("a"), ord("z") + 1)})
VK.update({str(number): ord(str(number)) for number in range(10)})


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a hotkey to a visible window.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--keys", required=True, help="Example: ctrl+shift+f7")
    args = parser.parse_args()
    hwnd = _find_window_by_pid(args.pid)
    if not hwnd:
        print({"ok": False, "error": "window_not_found"})
        return 2
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.25)
    keys = []
    for item in args.keys.split("+"):
        key_name = item.strip().casefold()
        if key_name not in VK:
            print({"ok": False, "error": "unsupported_key", "key": key_name})
            return 2
        keys.append(VK[key_name])
    for key in keys:
        _key_event(key, True)
    for key in reversed(keys):
        _key_event(key, False)
    print({"ok": True, "hwnd": hwnd, "keys": args.keys})
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


def _key_event(vk: int, down: bool) -> None:
    user32 = ctypes.windll.user32
    flags = 0 if down else 2
    user32.keybd_event(vk, 0, flags, 0)


if __name__ == "__main__":
    raise SystemExit(main())
