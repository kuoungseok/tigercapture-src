"""Click one exact Win32 dialog button during unattended external-app QA."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json


user32 = ctypes.windll.user32
BM_CLICK = 0x00F5


def _text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--parent-title", default="")
    args = parser.parse_args()
    children: list[dict] = []
    parents: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_windows(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == args.pid and (
            not args.parent_title or _text(hwnd) == args.parent_title
        ):
            parents.append(int(hwnd))
        return True

    user32.EnumWindows(enum_windows, 0)
    target = 0

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_children(hwnd, _):
        nonlocal target
        row = {
            "hwnd": int(hwnd),
            "text": _text(hwnd),
            "class": _class_name(hwnd),
            "visible": bool(user32.IsWindowVisible(hwnd)),
        }
        children.append(row)
        if not target and row["class"] == "Button" and row["text"] == args.text and row["visible"]:
            target = int(hwnd)
        return True

    for parent in parents:
        user32.EnumChildWindows(parent, enum_children, 0)
    if not target:
        print(json.dumps({"clicked": False, "children": children}, ensure_ascii=False))
        return 1
    user32.SendMessageW(target, BM_CLICK, 0, 0)
    print(json.dumps({"clicked": True, "target": target, "children": children}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
