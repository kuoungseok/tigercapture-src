from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_TITLE_FILTERS = ("TigerCapture", "Tiger Studio", "Tiger")
DEFAULT_PROCESS_FILTERS = ("TigerCapture.exe", "TigerStudio.exe")


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


def _rect_dict(rect: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = rect
    return {
        "left": int(left),
        "top": int(top),
        "right": int(right),
        "bottom": int(bottom),
        "width": max(0, int(right) - int(left)),
        "height": max(0, int(bottom) - int(top)),
    }


def _norm_process_name(exe: str) -> str:
    return Path(str(exe or "")).name.casefold()


def _matches_filters(
    row: dict[str, Any],
    *,
    title_filters: tuple[str, ...],
    process_filters: tuple[str, ...],
    pid_filters: set[int],
    watch_all: bool,
) -> bool:
    if watch_all:
        return True
    pid = int(row.get("pid", 0) or 0)
    if pid in pid_filters:
        return True
    title = str(row.get("title") or "").casefold()
    if any(str(token).casefold() in title for token in title_filters if str(token).strip()):
        return True
    process_name = _norm_process_name(str(row.get("process_exe") or ""))
    if any(process_name == str(token).casefold() for token in process_filters if str(token).strip()):
        return True
    return False


def _windows_processes() -> dict[int, dict[str, Any]]:
    try:
        from app.startup_trace import _windows_processes as _startup_windows_processes

        return {
            int(pid): {"pid": int(info.pid), "ppid": int(info.ppid), "exe": str(info.exe)}
            for pid, info in _startup_windows_processes().items()
        }
    except Exception:
        return {}


def _winapi_snapshot(
    *,
    include_children: bool,
    title_filters: tuple[str, ...],
    process_filters: tuple[str, ...],
    pid_filters: set[int],
    watch_all: bool,
) -> dict[str, Any]:
    if sys.platform != "win32":
        return {
            "foreground_hwnd": 0,
            "cursor": {"x": 0, "y": 0},
            "mouse": {"left": False, "right": False, "middle": False},
            "windows": [],
        }

    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
    user32.EnumChildWindows.restype = wintypes.BOOL
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.IsZoomed.argtypes = [wintypes.HWND]
    user32.IsZoomed.restype = wintypes.BOOL
    user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    user32.GetCursorPos.restype = wintypes.BOOL
    user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    user32.GetAsyncKeyState.restype = ctypes.c_short

    process_map = _windows_processes()
    rows: list[dict[str, Any]] = []
    top_level_rows: dict[int, dict[str, Any]] = {}
    foreground = int(user32.GetForegroundWindow() or 0)

    def _read_window(hwnd: int, *, parent_hwnd: int = 0, top_hwnd: int = 0, depth: int = 0) -> dict[str, Any] | None:
        rect = RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        title_len = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(max(title_len + 1, 1))
        user32.GetWindowTextW(hwnd, title_buf, len(title_buf))
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, len(class_buf))
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc = process_map.get(int(pid.value), {})
        row = {
            "hwnd": int(hwnd),
            "parent_hwnd": int(parent_hwnd),
            "top_hwnd": int(top_hwnd or hwnd),
            "depth": int(depth),
            "pid": int(pid.value),
            "process_exe": str(proc.get("exe") or ""),
            "process_name": _norm_process_name(str(proc.get("exe") or "")),
            "title": str(title_buf.value),
            "class_name": str(class_buf.value),
            "rect": _rect_dict((int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))),
            "visible": bool(user32.IsWindowVisible(hwnd)),
            "minimized": bool(user32.IsIconic(hwnd)),
            "maximized": bool(user32.IsZoomed(hwnd)),
            "foreground": int(hwnd) == foreground,
        }
        return row

    def _add_children(top_hwnd: int) -> None:
        def _child_callback(child_hwnd: int, _lparam: int) -> bool:
            child = _read_window(int(child_hwnd), parent_hwnd=int(top_hwnd), top_hwnd=int(top_hwnd), depth=1)
            if child is not None:
                rows.append(child)
            return True

        user32.EnumChildWindows(int(top_hwnd), EnumChildProc(_child_callback), 0)

    def _top_callback(hwnd: int, _lparam: int) -> bool:
        row = _read_window(int(hwnd))
        if row is None:
            return True
        if not _matches_filters(
            row,
            title_filters=title_filters,
            process_filters=process_filters,
            pid_filters=pid_filters,
            watch_all=watch_all,
        ):
            return True
        rows.append(row)
        top_level_rows[int(hwnd)] = row
        if include_children:
            _add_children(int(hwnd))
        return True

    user32.EnumWindows(EnumWindowsProc(_top_callback), 0)
    cursor = POINT()
    user32.GetCursorPos(ctypes.byref(cursor))

    def _key_down(vk: int) -> bool:
        return bool(int(user32.GetAsyncKeyState(vk)) & 0x8000)

    return {
        "foreground_hwnd": foreground,
        "cursor": {"x": int(cursor.x), "y": int(cursor.y)},
        "mouse": {
            "left": _key_down(0x01),
            "right": _key_down(0x02),
            "middle": _key_down(0x04),
        },
        "windows": rows,
    }


def summarize_ticks(ticks: list[dict[str, Any]]) -> dict[str, Any]:
    if not ticks:
        return {
            "tick_count": 0,
            "created_hwnds": [],
            "destroyed_hwnds": [],
            "appeared_hwnds": [],
            "disappeared_hwnds": [],
            "rect_changes": [],
            "visibility_changes": [],
            "minimized_changes": [],
            "foreground_changes": [],
            "left_mouse_transitions": [],
            "mouse_release_correlations": [],
        }

    def _window_map(tick: dict[str, Any]) -> dict[int, dict[str, Any]]:
        result: dict[int, dict[str, Any]] = {}
        for row in tick.get("windows") or []:
            try:
                result[int(row.get("hwnd"))] = dict(row)
            except Exception:
                continue
        return result

    first = _window_map(ticks[0])
    last = _window_map(ticks[-1])
    all_hwnds = sorted({hwnd for tick in ticks for hwnd in _window_map(tick)})
    first_hwnds = set(first)
    last_hwnds = set(last)
    final_tick_index = int(ticks[-1].get("tick", len(ticks) - 1) or 0)

    lifecycle: dict[int, dict[str, Any]] = {}
    for tick in ticks:
        windows = _window_map(tick)
        for hwnd, row in windows.items():
            entry = lifecycle.setdefault(
                hwnd,
                {
                    "hwnd": hwnd,
                    "first_seen_tick": tick.get("tick"),
                    "first_seen_elapsed_ms": tick.get("elapsed_ms"),
                    "first_seen": row,
                    "last_seen_tick": tick.get("tick"),
                    "last_seen_elapsed_ms": tick.get("elapsed_ms"),
                    "last_seen": row,
                },
            )
            entry["last_seen_tick"] = tick.get("tick")
            entry["last_seen_elapsed_ms"] = tick.get("elapsed_ms")
            entry["last_seen"] = row

    appeared_hwnds: list[dict[str, Any]] = []
    disappeared_hwnds: list[dict[str, Any]] = []
    for hwnd in all_hwnds:
        entry = lifecycle.get(hwnd, {})
        first_seen_tick = int(entry.get("first_seen_tick") or 0)
        last_seen_tick = int(entry.get("last_seen_tick") or 0)
        if first_seen_tick > int(ticks[0].get("tick", 0) or 0):
            appeared_hwnds.append(
                {
                    "hwnd": hwnd,
                    "first_seen_tick": entry.get("first_seen_tick"),
                    "first_seen_elapsed_ms": entry.get("first_seen_elapsed_ms"),
                    "window": entry.get("first_seen"),
                }
            )
        if last_seen_tick < final_tick_index:
            disappeared_hwnds.append(
                {
                    "hwnd": hwnd,
                    "last_seen_tick": entry.get("last_seen_tick"),
                    "last_seen_elapsed_ms": entry.get("last_seen_elapsed_ms"),
                    "window": entry.get("last_seen"),
                }
            )

    rect_changes: list[dict[str, Any]] = []
    visibility_changes: list[dict[str, Any]] = []
    minimized_changes: list[dict[str, Any]] = []
    for hwnd in all_hwnds:
        previous: dict[str, Any] | None = None
        for tick in ticks:
            row = _window_map(tick).get(hwnd)
            if row is None:
                continue
            if previous is not None:
                if row.get("rect") != previous.get("rect"):
                    rect_changes.append(
                        {
                            "tick": tick.get("tick"),
                            "elapsed_ms": tick.get("elapsed_ms"),
                            "hwnd": hwnd,
                            "title": row.get("title"),
                            "class_name": row.get("class_name"),
                            "before": previous.get("rect"),
                            "after": row.get("rect"),
                        }
                    )
                if row.get("visible") != previous.get("visible"):
                    visibility_changes.append(
                        {
                            "tick": tick.get("tick"),
                            "elapsed_ms": tick.get("elapsed_ms"),
                            "hwnd": hwnd,
                            "title": row.get("title"),
                            "before": previous.get("visible"),
                            "after": row.get("visible"),
                        }
                    )
                if row.get("minimized") != previous.get("minimized"):
                    minimized_changes.append(
                        {
                            "tick": tick.get("tick"),
                            "elapsed_ms": tick.get("elapsed_ms"),
                            "hwnd": hwnd,
                            "title": row.get("title"),
                            "before": previous.get("minimized"),
                            "after": row.get("minimized"),
                        }
                    )
            previous = row

    foreground_changes: list[dict[str, Any]] = []
    mouse_transitions: list[dict[str, Any]] = []
    previous_foreground = ticks[0].get("foreground_hwnd")
    previous_left = bool((ticks[0].get("mouse") or {}).get("left"))
    for tick in ticks[1:]:
        foreground = tick.get("foreground_hwnd")
        if foreground != previous_foreground:
            foreground_changes.append(
                {
                    "tick": tick.get("tick"),
                    "elapsed_ms": tick.get("elapsed_ms"),
                    "before": previous_foreground,
                    "after": foreground,
                }
            )
            previous_foreground = foreground
        left = bool((tick.get("mouse") or {}).get("left"))
        if left != previous_left:
            mouse_transitions.append(
                {
                    "tick": tick.get("tick"),
                    "elapsed_ms": tick.get("elapsed_ms"),
                    "button": "left",
                    "before": previous_left,
                    "after": left,
                    "cursor": tick.get("cursor"),
                    "foreground_hwnd": tick.get("foreground_hwnd"),
                }
            )
            previous_left = left

    created = [last[hwnd] for hwnd in sorted(last_hwnds - first_hwnds)]
    destroyed = [first[hwnd] for hwnd in sorted(first_hwnds - last_hwnds)]
    mouse_release_correlations: list[dict[str, Any]] = []
    for transition in mouse_transitions:
        if transition.get("button") != "left" or transition.get("after") is not False:
            continue
        elapsed = int(transition.get("elapsed_ms") or 0)
        before_ms = elapsed - 250
        after_ms = elapsed + 1250
        mouse_release_correlations.append(
            {
                "release_tick": transition.get("tick"),
                "release_elapsed_ms": transition.get("elapsed_ms"),
                "cursor": transition.get("cursor"),
                "foreground_hwnd_at_release": transition.get("foreground_hwnd"),
                "appeared_hwnds": [
                    row
                    for row in appeared_hwnds
                    if before_ms <= int(row.get("first_seen_elapsed_ms") or 0) <= after_ms
                ],
                "disappeared_hwnds": [
                    row
                    for row in disappeared_hwnds
                    if before_ms <= int(row.get("last_seen_elapsed_ms") or 0) <= after_ms
                ],
                "foreground_changes": [
                    row
                    for row in foreground_changes
                    if before_ms <= int(row.get("elapsed_ms") or 0) <= after_ms
                ],
                "visibility_changes": [
                    row
                    for row in visibility_changes
                    if before_ms <= int(row.get("elapsed_ms") or 0) <= after_ms
                ],
            }
        )
    return {
        "tick_count": len(ticks),
        "duration_ms": ticks[-1].get("elapsed_ms", 0),
        "created_hwnds": created,
        "destroyed_hwnds": destroyed,
        "appeared_hwnds": appeared_hwnds,
        "disappeared_hwnds": disappeared_hwnds,
        "rect_changes": rect_changes,
        "visibility_changes": visibility_changes,
        "minimized_changes": minimized_changes,
        "foreground_changes": foreground_changes,
        "left_mouse_transitions": mouse_transitions,
        "mouse_release_correlations": mouse_release_correlations,
        "first_tick_window_count": len(first),
        "last_tick_window_count": len(last),
    }


def run_probe(
    *,
    duration_s: float,
    interval_ms: int,
    out_dir: Path,
    include_children: bool,
    title_filters: tuple[str, ...],
    process_filters: tuple[str, ...],
    pid_filters: set[int],
    watch_all: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ticks_path = out_dir / "window_lifecycle_ticks.jsonl"
    summary_path = out_dir / "window_lifecycle_summary.json"
    ticks_path.write_text("", encoding="utf-8")

    start = time.perf_counter()
    deadline = start + max(0.25, float(duration_s))
    interval = max(0.001, int(interval_ms) / 1000.0)
    ticks: list[dict[str, Any]] = []
    tick_index = 0
    with ticks_path.open("a", encoding="utf-8", errors="replace") as fh:
        while time.perf_counter() < deadline:
            now = time.perf_counter()
            snapshot = _winapi_snapshot(
                include_children=include_children,
                title_filters=title_filters,
                process_filters=process_filters,
                pid_filters=pid_filters,
                watch_all=watch_all,
            )
            row = {
                "event": "tick",
                "generated_at": _dt.datetime.now().isoformat(timespec="milliseconds"),
                "monitor_pid": os.getpid(),
                "tick": tick_index,
                "elapsed_ms": int(round((now - start) * 1000.0)),
                **snapshot,
            }
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            ticks.append(row)
            tick_index += 1
            sleep_for = interval - (time.perf_counter() - now)
            if sleep_for > 0:
                time.sleep(sleep_for)

    summary = {
        "schema": "tigercapture.window_lifecycle_probe.v1",
        "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "ticks_path": str(ticks_path.resolve()),
        "summary_path": str(summary_path.resolve()),
        "duration_s": float(duration_s),
        "interval_ms": int(interval_ms),
        "include_children": bool(include_children),
        "title_filters": list(title_filters),
        "process_filters": list(process_filters),
        "pid_filters": sorted(pid_filters),
        "watch_all": bool(watch_all),
        **summarize_ticks(ticks),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record top-level/native window handles, sizes, foreground, and mouse state every tick."
    )
    parser.add_argument("--duration", type=float, default=20.0, help="Probe duration in seconds.")
    parser.add_argument("--interval-ms", type=int, default=33, help="Sampling interval in milliseconds.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "debugCapture" / "window_lifecycle_probe",
        help="Directory for ticks JSONL and summary JSON.",
    )
    parser.add_argument("--include-children", action="store_true", help="Also record child/native renderer windows.")
    parser.add_argument(
        "--title-contains",
        action="append",
        default=None,
        help="Window title substring filter. Repeatable. Defaults to TigerCapture/Tiger Studio/Tiger.",
    )
    parser.add_argument(
        "--process-name",
        action="append",
        default=None,
        help="Process executable basename filter. Repeatable.",
    )
    parser.add_argument("--pid", action="append", type=int, default=None, help="Specific process id to record.")
    parser.add_argument("--watch-all", action="store_true", help="Record every native top-level window.")
    parser.add_argument("--print-summary", action="store_true", help="Print summary JSON after capture.")
    args = parser.parse_args()

    title_filters = tuple(args.title_contains or DEFAULT_TITLE_FILTERS)
    process_filters = tuple(args.process_name or DEFAULT_PROCESS_FILTERS)
    pid_filters = {int(pid) for pid in (args.pid or []) if int(pid) > 0}
    summary = run_probe(
        duration_s=float(args.duration),
        interval_ms=int(args.interval_ms),
        out_dir=args.out_dir,
        include_children=bool(args.include_children),
        title_filters=title_filters,
        process_filters=process_filters,
        pid_filters=pid_filters,
        watch_all=bool(args.watch_all),
    )
    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"summary: {summary['summary_path']}")
        print(f"ticks: {summary['ticks_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
