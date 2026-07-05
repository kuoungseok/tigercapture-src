from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.startup_trace import (  # noqa: E402
    ProcessInfo,
    _is_descendant_process,
    _query_native_window,
    _windows_native_windows,
    _windows_processes,
)
from app.paths import runtime_log_dir  # noqa: E402


LOG_PATH = runtime_log_dir() / "visible_window_trace.jsonl"


def _set_log_path(path: Path | str | None) -> None:
    if path is None:
        return
    global LOG_PATH
    LOG_PATH = Path(path).expanduser().resolve()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return repr(value)


def _log(event: str, **payload: Any) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _dt.datetime.now().isoformat(timespec="milliseconds"),
        "monitor_pid": os.getpid(),
        "event": event,
        **{k: _json_safe(v) for k, v in payload.items()},
    }
    with LOG_PATH.open("a", encoding="utf-8", errors="replace") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _parent_chain(pid: int, processes: dict[int, ProcessInfo], limit: int = 12) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    seen: set[int] = set()
    current = int(pid)
    for _ in range(limit):
        info = processes.get(current)
        if info is None:
            break
        chain.append(asdict(info))
        parent = int(info.ppid)
        if parent <= 0 or parent in seen:
            break
        seen.add(parent)
        current = parent
    return chain


def _is_related(pid: int, processes: dict[int, ProcessInfo], roots: set[int]) -> bool:
    if int(pid) in roots:
        return True
    return any(_is_descendant_process(int(pid), processes, root) for root in roots)


def _launch_command(command: list[str] | None) -> subprocess.Popen | None:
    if not command:
        return None
    env = os.environ.copy()
    env["TIGERCAPTURE_STARTUP_TRACE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen(command, cwd=str(ROOT), env=env)
    _log("launch.started", command=command, child_pid=proc.pid)
    return proc


def _install_hooks(roots: set[int], seen_events: set[tuple[int, int]]) -> tuple[list[Any], Any]:
    if sys.platform != "win32":
        return [], None

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    EVENT_SYSTEM_FOREGROUND = 0x0003
    EVENT_OBJECT_CREATE = 0x8000
    EVENT_OBJECT_SHOW = 0x8002
    EVENT_OBJECT_HIDE = 0x8003
    OBJID_WINDOW = 0
    WINEVENT_OUTOFCONTEXT = 0x0000

    WinEventProc = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD,
    )

    user32.SetWinEventHook.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HMODULE,
        WinEventProc,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    user32.SetWinEventHook.restype = wintypes.HANDLE

    def _event_name(code: int) -> str:
        return {
            EVENT_SYSTEM_FOREGROUND: "foreground",
            EVENT_OBJECT_CREATE: "object_create",
            EVENT_OBJECT_SHOW: "object_show",
            EVENT_OBJECT_HIDE: "object_hide",
        }.get(int(code), str(code))

    def _callback(_hook, event, hwnd, object_id, child_id, event_thread, event_time) -> None:
        try:
            if int(object_id) != OBJID_WINDOW or not int(hwnd):
                return
            event_code = int(event)
            hwnd_int = int(hwnd)
            key = (event_code, hwnd_int)
            if key in seen_events:
                return
            seen_events.add(key)
            info = _query_native_window(hwnd_int, visible_only=False)
            if info is None:
                return
            processes = _windows_processes()
            proc = processes.get(info.pid)
            parent = processes.get(proc.ppid) if proc is not None else None
            _log(
                "window.event",
                event_code=event_code,
                event_name=_event_name(event_code),
                child_id=int(child_id),
                event_thread=int(event_thread),
                event_time=int(event_time),
                related=_is_related(info.pid, processes, roots),
                process=asdict(proc) if proc else None,
                parent=asdict(parent) if parent else None,
                parent_chain=_parent_chain(info.pid, processes),
                **asdict(info),
            )
        except Exception as exc:
            _log("hook.error", error=repr(exc))

    callback = WinEventProc(_callback)
    hooks: list[Any] = []
    for event_code in (EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, EVENT_OBJECT_HIDE, EVENT_SYSTEM_FOREGROUND):
        hook = user32.SetWinEventHook(event_code, event_code, None, callback, 0, 0, WINEVENT_OUTOFCONTEXT)
        if hook:
            hooks.append(hook)
    _log("hooks.installed", count=len(hooks))
    return hooks, callback


def _pump_messages_once() -> None:
    if sys.platform != "win32":
        time.sleep(0.01)
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    PM_REMOVE = 0x0001

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    msg = MSG()
    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    time.sleep(0.01)


def _uninstall_hooks(hooks: list[Any]) -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
    user32.UnhookWinEvent.restype = wintypes.BOOL
    for hook in hooks:
        try:
            user32.UnhookWinEvent(hook)
        except Exception:
            pass


def trace_visible_windows(
    duration_s: float,
    command: list[str] | None = None,
    *,
    log_path: Path | None = None,
) -> int:
    _set_log_path(log_path)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    roots = {os.getpid()}
    child = _launch_command(command)
    if child is not None:
        roots.add(int(child.pid))

    baseline_windows = _windows_native_windows()
    seen_windows = set(baseline_windows)
    seen_events: set[tuple[int, int]] = set()
    hooks, callback_ref = _install_hooks(roots, seen_events)
    _ = callback_ref
    _log(
        "trace.start",
        duration_s=duration_s,
        roots=sorted(roots),
        baseline_window_count=len(baseline_windows),
    )

    deadline = time.monotonic() + max(1.0, float(duration_s))
    try:
        while time.monotonic() < deadline:
            processes = _windows_processes()
            for hwnd, info in _windows_native_windows().items():
                if hwnd in seen_windows:
                    continue
                seen_windows.add(hwnd)
                proc = processes.get(info.pid)
                parent = processes.get(proc.ppid) if proc is not None else None
                _log(
                    "window.snapshot_new",
                    related=_is_related(info.pid, processes, roots),
                    process=asdict(proc) if proc else None,
                    parent=asdict(parent) if parent else None,
                    parent_chain=_parent_chain(info.pid, processes),
                    **asdict(info),
                )
            _pump_messages_once()
    finally:
        _uninstall_hooks(hooks)
        _log("trace.stop", roots=sorted(roots))
        if child is not None and child.poll() is None:
            _log("launch.still_running", child_pid=child.pid)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace short-lived visible/native Windows windows.")
    parser.add_argument("--duration", type=float, default=12.0)
    parser.add_argument("--log-path", type=Path, default=None)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command or [])
    if command and command[0] == "--":
        command = command[1:]
    return trace_visible_windows(args.duration, command or None, log_path=args.log_path)


if __name__ == "__main__":
    raise SystemExit(main())
