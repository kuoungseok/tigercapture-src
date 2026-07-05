"""Probe VSeeFace start-screen click targets and stop when the VMC port opens."""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
from pathlib import Path
import subprocess
import time


MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

DEFAULT_CANDIDATES = [
    # VSeeFace v1.13 start UI: lower action row, title bar included.
    (0.08, 0.78, "lower_left_action_high"),
    (0.08, 0.82, "lower_left_action"),
    (0.08, 0.88, "lower_left_action_low"),
    (0.17, 0.78, "left_secondary_high"),
    (0.17, 0.82, "left_secondary"),
    (0.17, 0.88, "left_secondary_low"),
    (0.32, 0.78, "lower_mid_left_high"),
    (0.32, 0.84, "lower_mid_left"),
    (0.50, 0.78, "lower_center_high"),
    (0.50, 0.84, "lower_center"),
    (0.72, 0.78, "lower_mid_right_high"),
    (0.72, 0.84, "lower_mid_right"),
    (0.88, 0.78, "lower_right_high"),
    (0.88, 0.84, "lower_right"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Click likely VSeeFace action targets until a UDP port opens.")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--port", type=int, default=39540)
    parser.add_argument("--out", default="debugCapture/vseeface_click_probe.json")
    parser.add_argument("--wait", type=float, default=2.0)
    parser.add_argument("--double", action="store_true", dest="double_click")
    args = parser.parse_args()

    hwnd = _find_window_by_pid(args.pid)
    if not hwnd:
        return _write(args.out, {"ok": False, "error": "window_not_found"}, 2)
    rect = _window_rect(hwnd)
    report = {
        "schema": "tigerstudio.vtuber.vseeface_click_probe.v1",
        "pid": args.pid,
        "hwnd": hwnd,
        "rect": rect,
        "port": args.port,
        "double_click": args.double_click,
        "attempts": [],
        "ready": False,
    }
    if _is_port_open(args.port):
        report["ready"] = True
        return _write(args.out, report, 0)

    for x_norm, y_norm, label in DEFAULT_CANDIDATES:
        point = _point_from_rect(rect, x_norm, y_norm)
        _click_window(hwnd, point[0], point[1], args.double_click)
        time.sleep(args.wait)
        port_open = _is_port_open(args.port)
        report["attempts"].append({
            "label": label,
            "normalized": [x_norm, y_norm],
            "screen": point,
            "port_open": port_open,
        })
        if port_open:
            report["ready"] = True
            break
    return _write(args.out, report, 0 if report["ready"] else 2)


def _write(path: str, data: dict, code: int) -> int:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ready": data.get("ready", False), "out": str(out), "attempts": len(data.get("attempts", [])), "error": data.get("error", "")}, ensure_ascii=False))
    return code


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


def _point_from_rect(rect: list[int], x_norm: float, y_norm: float) -> list[int]:
    left, top, right, bottom = rect
    return [int(left + (right - left) * x_norm), int(top + (bottom - top) * y_norm)]


def _click_window(hwnd: int, x: int, y: int, double_click: bool) -> None:
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 5)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    _click(x, y)
    if double_click:
        time.sleep(0.08)
        _click(x, y)


def _click(x: int, y: int) -> None:
    user32 = ctypes.windll.user32
    user32.SetCursorPos(x, y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _is_port_open(port: int) -> bool:
    completed = subprocess.run(["netstat", "-ano", "-p", "udp"], capture_output=True, text=True, timeout=10, check=False)
    needle = f":{int(port)}"
    for line in (completed.stdout or "").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0].upper() == "UDP" and needle in parts[1]:
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
