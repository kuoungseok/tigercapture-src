from __future__ import annotations

import datetime as _dt
import json
import os
import subprocess
import sys
import threading
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TRACE_ENV = "TIGERCAPTURE_STARTUP_TRACE"
TRACE_LOG_NAME = "startup_flicker_trace.jsonl"

_LOG_LOCK = threading.RLock()
_ACTIVE_TRACE_LOCK = threading.RLock()
_ACTIVE_TRACE: "StartupFlickerTracer | None" = None
_ORIGINAL_POPEN = subprocess.Popen
_POPEN_PATCHED = False


def startup_trace_log_path() -> Path:
    try:
        from app.paths import runtime_log_dir

        return runtime_log_dir() / TRACE_LOG_NAME
    except Exception:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TigerCapture" / "logs" / TRACE_LOG_NAME


def startup_trace_enabled() -> bool:
    value = os.environ.get(TRACE_ENV)
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return repr(value)


def reset_startup_trace_log() -> Path:
    path = startup_trace_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def log_startup_trace(event: str, **payload: Any) -> None:
    path = startup_trace_log_path()
    row = {
        "ts": _dt.datetime.now().isoformat(timespec="milliseconds"),
        "pid": os.getpid(),
        "event": event,
        **{key: _json_safe(value) for key, value in payload.items()},
    }
    try:
        with _LOG_LOCK:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int
    exe: str


@dataclass(frozen=True)
class NativeWindowInfo:
    hwnd: int
    pid: int
    title: str
    class_name: str
    rect: tuple[int, int, int, int]
    visible: bool


def _query_native_window(hwnd: int, *, visible_only: bool = False) -> NativeWindowInfo | None:
    if sys.platform != "win32" or not hwnd:
        return None
    try:
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

        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetClassNameW.restype = ctypes.c_int
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL

        visible = bool(user32.IsWindowVisible(hwnd))
        if visible_only and not visible:
            return None
        title_len = user32.GetWindowTextLengthW(hwnd)
        title_buf = ctypes.create_unicode_buffer(max(title_len + 1, 1))
        user32.GetWindowTextW(hwnd, title_buf, len(title_buf))
        class_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, class_buf, len(class_buf))
        pid = wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return NativeWindowInfo(
            hwnd=int(hwnd),
            pid=int(pid.value),
            title=str(title_buf.value),
            class_name=str(class_buf.value),
            rect=(int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)),
            visible=visible,
        )
    except Exception:
        return None


def _windows_processes() -> dict[int, ProcessInfo]:
    if sys.platform != "win32":
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        MAX_PATH = 260

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", ctypes.c_wchar * MAX_PATH),
            ]

        kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32FirstW.restype = wintypes.BOOL
        kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
        kernel32.Process32NextW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if snapshot == INVALID_HANDLE_VALUE:
            return {}
        try:
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            result: dict[int, ProcessInfo] = {}
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                pid = int(entry.th32ProcessID)
                result[pid] = ProcessInfo(
                    pid=pid,
                    ppid=int(entry.th32ParentProcessID),
                    exe=str(entry.szExeFile),
                )
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
            return result
        finally:
            kernel32.CloseHandle(snapshot)
    except Exception as exc:
        log_startup_trace("trace.process_snapshot_error", error=repr(exc))
        return {}


def _windows_native_windows() -> dict[int, NativeWindowInfo]:
    if sys.platform != "win32":
        return {}
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)

        EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL

        result: dict[int, NativeWindowInfo] = {}

        def _callback(hwnd: int, _lparam: int) -> bool:
            try:
                info = _query_native_window(int(hwnd), visible_only=True)
                if info is not None:
                    result[int(hwnd)] = info
            except Exception:
                return True
            return True

        user32.EnumWindows(EnumWindowsProc(_callback), 0)
        return result
    except Exception as exc:
        log_startup_trace("trace.window_snapshot_error", error=repr(exc))
        return {}


def _qt_widget_key(widget: Any) -> int:
    try:
        import shiboken6

        ptr = shiboken6.getCppPointer(widget)
        if ptr:
            return int(ptr[0])
    except Exception:
        pass
    return id(widget)


def _is_descendant_process(pid: int, processes: dict[int, ProcessInfo], ancestor_pid: int) -> bool:
    seen: set[int] = set()
    current = int(pid)
    for _ in range(32):
        info = processes.get(current)
        if info is None:
            return False
        parent = int(info.ppid)
        if parent == ancestor_pid:
            return True
        if parent in seen or parent <= 0:
            return False
        seen.add(parent)
        current = parent
    return False


class StartupFlickerTracer:
    def __init__(self, reason: str, duration_ms: int = 6000, poll_ms: int = 50) -> None:
        self.reason = reason
        self.duration_ms = max(500, int(duration_ms))
        # This tracer runs alongside the GUI thread during exactly the
        # period users complain about.  Full process/window scans at 40-50ms
        # can themselves make Qt miss timers and trigger DWM Ghost windows,
        # especially while Codex/Git are also spawning helpers. Keep polling
        # coarse and rely on WinEventHook for app-related window events.
        self.poll_ms = max(250, int(poll_ms))
        self.trace_id = f"{int(time.time() * 1000)}-{os.getpid()}"
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._base_processes: dict[int, ProcessInfo] = {}
        self._seen_processes: set[int] = set()
        self._base_windows: dict[int, NativeWindowInfo] = {}
        self._seen_windows: set[int] = set()
        self._seen_window_events: set[tuple[int, int]] = set()
        self._seen_qt_widgets: set[int] = set()
        self._qt_timer = None
        self._win_event_hooks: list[Any] = []
        self._win_event_proc = None
        self._stopped = False

    def start(self) -> None:
        self._base_processes = _windows_processes()
        self._seen_processes = set(self._base_processes)
        self._base_windows = _windows_native_windows()
        self._seen_windows = set(self._base_windows)
        self._install_win_event_hooks()
        log_startup_trace(
            "trace.start",
            trace_id=self.trace_id,
            reason=self.reason,
            duration_ms=self.duration_ms,
            baseline_process_count=len(self._base_processes),
            baseline_window_count=len(self._base_windows),
        )
        self._thread = threading.Thread(
            target=self._native_poll_loop,
            name="TigerCaptureStartupTrace",
            daemon=True,
        )
        self._thread.start()
        self._install_qt_polling()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._stop.set()
        try:
            timer = self._qt_timer
            if timer is not None and threading.current_thread() is threading.main_thread():
                timer.stop()
        except Exception:
            pass
        self._uninstall_win_event_hooks()
        log_startup_trace("trace.stop", trace_id=self.trace_id, reason=self.reason)
        with _ACTIVE_TRACE_LOCK:
            global _ACTIVE_TRACE
            if _ACTIVE_TRACE is self:
                _ACTIVE_TRACE = None

    def _native_poll_loop(self) -> None:
        deadline = time.monotonic() + (self.duration_ms / 1000.0)
        while not self._stop.is_set() and time.monotonic() < deadline:
            self._poll_native_once()
            time.sleep(self.poll_ms / 1000.0)
        self.stop()

    def _poll_native_once(self) -> None:
        processes = _windows_processes()
        for pid, info in processes.items():
            if pid in self._seen_processes:
                continue
            self._seen_processes.add(pid)
            app_related = _is_descendant_process(pid, processes, os.getpid())
            if not app_related:
                continue
            parent = processes.get(info.ppid)
            log_startup_trace(
                "process.new",
                trace_id=self.trace_id,
                reason=self.reason,
                app_related=app_related,
                parent=asdict(parent) if parent else None,
                **asdict(info),
            )

        windows = _windows_native_windows()
        for hwnd, info in windows.items():
            if hwnd in self._seen_windows:
                continue
            self._seen_windows.add(hwnd)
            title = str(info.title or "")
            if info.pid != os.getpid() and "TigerCapture" not in title:
                continue
            proc = processes.get(info.pid)
            log_startup_trace(
                "native_window.new",
                trace_id=self.trace_id,
                reason=self.reason,
                process=asdict(proc) if proc else None,
                **asdict(info),
            )

    def _install_win_event_hooks(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            EVENT_SYSTEM_FOREGROUND = 0x0003
            EVENT_OBJECT_CREATE = 0x8000
            EVENT_OBJECT_SHOW = 0x8002
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
                }.get(int(code), str(code))

            def _callback(_hook, event, hwnd, object_id, child_id, event_thread, event_time) -> None:
                try:
                    if self._stopped or int(object_id) != OBJID_WINDOW or not int(hwnd):
                        return
                    event_code = int(event)
                    hwnd_int = int(hwnd)
                    key = (event_code, hwnd_int)
                    if key in self._seen_window_events:
                        return
                    self._seen_window_events.add(key)
                    info = _query_native_window(hwnd_int, visible_only=False)
                    if info is None:
                        return
                    if (
                        info.pid == 0
                        and not info.visible
                        and not str(info.title or "").strip()
                        and not str(info.class_name or "").strip()
                    ):
                        return
                    title = str(info.title or "")
                    if info.pid != os.getpid() and "TigerCapture" not in title:
                        return
                    processes = _windows_processes()
                    proc = processes.get(info.pid)
                    parent = processes.get(proc.ppid) if proc is not None else None
                    app_related = info.pid == os.getpid() or _is_descendant_process(info.pid, processes, os.getpid())
                    log_startup_trace(
                        "native_window.event",
                        trace_id=self.trace_id,
                        reason=self.reason,
                        event_code=event_code,
                        event_name=_event_name(event_code),
                        child_id=int(child_id),
                        event_thread=int(event_thread),
                        event_time=int(event_time),
                        app_related=app_related,
                        process=asdict(proc) if proc else None,
                        parent=asdict(parent) if parent else None,
                        **asdict(info),
                    )
                except Exception as exc:
                    log_startup_trace("trace.window_event_error", trace_id=self.trace_id, error=repr(exc))

            proc = WinEventProc(_callback)
            self._win_event_proc = proc
            for event_code in (EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, EVENT_SYSTEM_FOREGROUND):
                hook = user32.SetWinEventHook(
                    event_code,
                    event_code,
                    None,
                    proc,
                    0,
                    0,
                    WINEVENT_OUTOFCONTEXT,
                )
                if hook:
                    self._win_event_hooks.append(hook)
            log_startup_trace(
                "trace.window_event_hooks",
                trace_id=self.trace_id,
                count=len(self._win_event_hooks),
            )
        except Exception as exc:
            log_startup_trace("trace.window_event_hook_error", trace_id=self.trace_id, error=repr(exc))

    def _uninstall_win_event_hooks(self) -> None:
        if sys.platform != "win32" or not self._win_event_hooks:
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
            user32.UnhookWinEvent.restype = wintypes.BOOL
            for hook in list(self._win_event_hooks):
                try:
                    user32.UnhookWinEvent(hook)
                except Exception:
                    pass
        finally:
            self._win_event_hooks = []
            self._win_event_proc = None

    def _install_qt_polling(self) -> None:
        try:
            from PySide6.QtCore import QTimer
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                return
            timer = QTimer(app)
            timer.setInterval(max(80, self.poll_ms * 2))
            timer.timeout.connect(self._poll_qt_once)
            timer.start()
            self._qt_timer = timer
            QTimer.singleShot(self.duration_ms + 250, timer.stop)
        except Exception as exc:
            log_startup_trace("trace.qt_poll_error", trace_id=self.trace_id, error=repr(exc))

    def _poll_qt_once(self) -> None:
        try:
            from PySide6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is None:
                return
            for widget in app.topLevelWidgets():
                key = _qt_widget_key(widget)
                if key in self._seen_qt_widgets:
                    continue
                self._seen_qt_widgets.add(key)
                geom = widget.geometry()
                log_startup_trace(
                    "qt_window.new",
                    trace_id=self.trace_id,
                    reason=self.reason,
                    widget_class=type(widget).__name__,
                    object_name=widget.objectName(),
                    title=widget.windowTitle(),
                    visible=widget.isVisible(),
                    geometry=(geom.x(), geom.y(), geom.width(), geom.height()),
                )
        except Exception as exc:
            log_startup_trace("trace.qt_snapshot_error", trace_id=self.trace_id, error=repr(exc))


def start_startup_flicker_trace(
    reason: str,
    *,
    duration_ms: int = 6000,
    poll_ms: int = 50,
    reset_log: bool = False,
) -> StartupFlickerTracer | None:
    if reset_log:
        reset_startup_trace_log()
    with _ACTIVE_TRACE_LOCK:
        global _ACTIVE_TRACE
        if _ACTIVE_TRACE is not None:
            _ACTIVE_TRACE.stop()
        tracer = StartupFlickerTracer(reason, duration_ms=duration_ms, poll_ms=poll_ms)
        _ACTIVE_TRACE = tracer
        tracer.start()
        return tracer


def active_trace_id() -> str | None:
    with _ACTIVE_TRACE_LOCK:
        return _ACTIVE_TRACE.trace_id if _ACTIVE_TRACE is not None else None


def install_subprocess_trace() -> None:
    global _POPEN_PATCHED
    if _POPEN_PATCHED:
        return

    def _traced_popen(*args: Any, **kwargs: Any):
        trace_id = active_trace_id()
        if trace_id:
            command = args[0] if args else kwargs.get("args")
            log_startup_trace(
                "subprocess.popen.before",
                trace_id=trace_id,
                command=command,
                cwd=kwargs.get("cwd"),
                shell=kwargs.get("shell"),
                creationflags=kwargs.get("creationflags"),
                startupinfo=repr(kwargs.get("startupinfo")),
                stack="".join(traceback.format_stack(limit=8)),
            )
        proc = _ORIGINAL_POPEN(*args, **kwargs)
        trace_id = active_trace_id()
        if trace_id:
            log_startup_trace(
                "subprocess.popen.after",
                trace_id=trace_id,
                child_pid=getattr(proc, "pid", None),
            )
        return proc

    subprocess.Popen = _traced_popen  # type: ignore[assignment]
    _POPEN_PATCHED = True


def cleanup_hidden_qt_orphan_windows(owner: Any, reason: str = "") -> int:
    """Reparent hidden, parentless Qt widgets that should not be OS windows.

    QMenu popups and visible main windows are legitimate top-level widgets.
    Hidden QLabel/QFrame/QPushButton/QWidget objects with no parent are not;
    on Windows they can allocate tiny native windows while the editor is
    being assembled, which looks like flicker. Reparenting keeps the object
    alive but removes it from the top-level window list.
    """
    try:
        from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMenu, QWidget

        app = QApplication.instance()
        if app is None or owner is None:
            return 0
        count = 0
        for widget in list(app.topLevelWidgets()):
            if widget is owner:
                continue
            try:
                if not isinstance(widget, QWidget):
                    continue
                if widget.isVisible() or widget.parentWidget() is not None:
                    continue
                if isinstance(widget, (QMenu, QDialog, QMainWindow)):
                    continue
                title = str(widget.windowTitle() or "")
                if title:
                    continue
                geom = widget.geometry()
                log_startup_trace(
                    "qt_window.orphan_reparent",
                    reason=reason,
                    widget_class=type(widget).__name__,
                    object_name=widget.objectName(),
                    geometry=(geom.x(), geom.y(), geom.width(), geom.height()),
                )
                widget.hide()
                widget.setParent(owner)
                count += 1
            except RuntimeError:
                continue
            except Exception as exc:
                log_startup_trace("qt_window.orphan_cleanup_item_error", reason=reason, error=repr(exc))
        if count:
            log_startup_trace("qt_window.orphan_cleanup_done", reason=reason, count=count)
        return count
    except Exception as exc:
        log_startup_trace("qt_window.orphan_cleanup_error", reason=reason, error=repr(exc))
        return 0
