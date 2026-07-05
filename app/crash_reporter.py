"""Crash breadcrumbs and lightweight recovery hooks.

This module is intentionally UI-free: it can be imported from main startup,
Qt widgets, QA tools, and tests without pulling in PySide.  The goal is to
leave enough context after a crash to answer "what did I just do?".
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import threading
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any, Callable


_MAX_ACTIONS = max(20, int(os.environ.get("TIGERCAPTURE_ACTION_LOG_MAX", "200")))
_lock = threading.RLock()
_recent_actions: deque[dict[str, Any]] = deque(maxlen=_MAX_ACTIONS)
_log_dir: Path | None = None
_action_log_path: Path | None = None
_crash_report_path: Path | None = None
_emergency_autosave_callback: Callable[[str], Any] | None = None
_installed = False
_writing_crash_report = False


def default_log_dir() -> Path:
    try:
        from app.paths import runtime_log_dir

        return runtime_log_dir()
    except Exception:
        return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TigerCapture" / "logs"


def _ensure_paths() -> tuple[Path, Path, Path]:
    global _log_dir, _action_log_path, _crash_report_path
    with _lock:
        if _log_dir is None or _action_log_path is None or _crash_report_path is None:
            configure_crash_reporting(default_log_dir())
        assert _log_dir is not None
        assert _action_log_path is not None
        assert _crash_report_path is not None
        return _log_dir, _action_log_path, _crash_report_path


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    try:
        json.dumps(value)
        return value
    except Exception:
        return repr(value)


def configure_crash_reporting(log_dir: str | Path) -> None:
    global _log_dir, _action_log_path, _crash_report_path
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    with _lock:
        _log_dir = path
        _action_log_path = path / "recent_actions.jsonl"
        _crash_report_path = path / "crash_report_latest.json"


def record_action(event: str, **data: Any) -> None:
    """Append one user/system breadcrumb to memory and JSONL.

    Callers must be able to use this from error paths, so all failures are
    swallowed.  The log is capped in memory and append-only on disk.
    """
    if not event:
        return
    row = {
        "at": _now(),
        "event": str(event),
        "data": _jsonable(data),
    }
    try:
        with _lock:
            _recent_actions.append(row)
            path = _action_log_path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8", errors="replace") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def latest_crash_report_path() -> Path:
    _log_dir, _action_log_path, report_path = _ensure_paths()
    return report_path


def latest_actions_path() -> Path:
    _log_dir, action_log_path, _report_path = _ensure_paths()
    return action_log_path


def load_crash_report(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path is not None else latest_crash_report_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _crash_report_max_age_seconds() -> int:
    raw = os.environ.get("TIGERCAPTURE_CRASH_REPORT_MAX_AGE_HOURS", "168")
    try:
        hours = float(raw)
    except Exception:
        hours = 168.0
    if hours <= 0:
        return 0
    return int(hours * 3600)


def _is_actionable_crash_report(report: dict[str, Any]) -> bool:
    if not isinstance(report, dict) or not report:
        return False
    status = str(report.get("status") or "").strip().casefold()
    if status in {"seen", "dismissed", "handled", "recovered"}:
        return False
    exc = report.get("exception")
    if not isinstance(exc, dict):
        return False
    exc_type = str(exc.get("type") or "").strip()
    return bool(exc_type)


def _seen_marker_path(path: Path | None = None) -> Path:
    report_path = Path(path) if path is not None else latest_crash_report_path()
    return report_path.with_suffix(report_path.suffix + ".seen")


def mark_crash_report_seen(path: str | Path | None = None) -> None:
    report_path = Path(path) if path is not None else latest_crash_report_path()
    marker = _seen_marker_path(report_path)
    report = load_crash_report(report_path)
    try:
        report_mtime = report_path.stat().st_mtime
    except Exception:
        report_mtime = 0.0
    try:
        marker.write_text(
            json.dumps(
                {
                    "seen_at": _now(),
                    "report": str(report_path),
                    "report_mtime": report_mtime,
                    "exception": (report.get("exception") or {}) if isinstance(report, dict) else {},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def has_unseen_crash_report(path: str | Path | None = None) -> bool:
    report_path = Path(path) if path is not None else latest_crash_report_path()
    if not report_path.exists():
        return False
    report = load_crash_report(report_path)
    if not _is_actionable_crash_report(report):
        return False
    max_age = _crash_report_max_age_seconds()
    if max_age > 0:
        try:
            if time.time() - report_path.stat().st_mtime > max_age:
                return False
        except Exception:
            return False
    marker = _seen_marker_path(report_path)
    if not marker.exists():
        return True
    try:
        return report_path.stat().st_mtime > marker.stat().st_mtime
    except Exception:
        return True


def recent_actions(limit: int = 80) -> list[dict[str, Any]]:
    with _lock:
        rows = list(_recent_actions)
    return rows[-max(1, int(limit)):]


def repro_steps_from_report(report: dict[str, Any]) -> list[str]:
    actions = list(report.get("recent_actions", []) or [])
    steps: list[str] = []
    for action in actions[-80:]:
        if not isinstance(action, dict):
            continue
        event = str(action.get("event") or "")
        data = action.get("data") if isinstance(action.get("data"), dict) else {}
        if event == "timeline.drop_live2d":
            steps.append(f"Drop Live2D actor at {data.get('start_ms')} ms: {data.get('path', '')}")
        elif event == "timeline.drop_spine":
            steps.append(f"Drop Spine actor at {data.get('start_ms')} ms: {data.get('path', '')}")
        elif event == "actor.open_live2d_editor":
            steps.append(f"Open Live2D editor for clip {data.get('start_ms')}..{data.get('end_ms')}")
        elif event == "actor.open_spine_editor":
            steps.append(f"Open Spine editor for clip {data.get('start_ms')}..{data.get('end_ms')}")
        elif event == "actor.load_live2d.stage":
            steps.append(
                f"Live2D load stage {data.get('stage', '-')}: "
                f"{data.get('path', '')} {data.get('status', '')}"
            )
        elif event == "actor.load_spine.stage":
            steps.append(
                f"Spine load stage {data.get('stage', '-')}: "
                f"{data.get('path', '')} {data.get('status', '')}"
            )
        elif event.startswith("node_graph."):
            steps.append(event.replace("node_graph.", "Node Graph: ") + f" {data}")
        elif event.startswith("autosave."):
            continue
        elif event:
            steps.append(f"{event} {data}")
    return steps[-40:]


def actor_context_from_actions(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract the latest actor-specific breadcrumb context for crash triage."""
    latest_open: dict[str, Any] | None = None
    latest_load: dict[str, Any] | None = None
    latest_drop: dict[str, Any] | None = None
    for action in actions or []:
        if not isinstance(action, dict):
            continue
        event = str(action.get("event") or "")
        data = action.get("data") if isinstance(action.get("data"), dict) else {}
        row = {"at": action.get("at"), "event": event, "data": data}
        if event in {"actor.open_live2d_editor", "actor.open_spine_editor"}:
            latest_open = row
        elif event in {"actor.load_live2d.stage", "actor.load_spine.stage"}:
            latest_load = row
        elif event in {"timeline.drop_live2d", "timeline.drop_spine"}:
            latest_drop = row
    return {
        "latest_open": latest_open,
        "latest_load": latest_load,
        "latest_drop": latest_drop,
        "actor_related": bool(latest_open or latest_load or latest_drop),
    }


def export_repro_bundle(
    report_path: str | Path | None = None,
    out_path: str | Path | None = None,
) -> Path | None:
    report_source = Path(report_path) if report_path is not None else latest_crash_report_path()
    report = load_crash_report(report_source)
    if not report:
        return None
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if out_path is None:
        out = Path(__file__).resolve().parents[1] / "debugCapture" / "repro" / f"crash_repro_{stamp}.json"
    else:
        out = Path(out_path)
    payload = {
        "created_at": _now(),
        "source_report": str(report_source),
        "exception": report.get("exception", {}),
        "emergency_autosave": report.get("emergency_autosave", {}),
        "steps": repro_steps_from_report(report),
        "actor_context": report.get("actor_context") or actor_context_from_actions(list(report.get("recent_actions", []) or [])),
        "recent_actions": list(report.get("recent_actions", []) or []),
        "traceback_tail": str(report.get("traceback", ""))[-4000:],
    }
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        record_action("crash_report.repro_exported", path=str(out))
        return out
    except Exception:
        return None


def set_emergency_autosave_callback(callback: Callable[[str], Any] | None) -> None:
    global _emergency_autosave_callback
    with _lock:
        _emergency_autosave_callback = callback


def write_crash_report(exc_type, exc_value, tb) -> Path | None:
    """Write the latest crash report and return its path when possible."""
    global _writing_crash_report
    with _lock:
        if _writing_crash_report:
            return None
        _writing_crash_report = True
        report_path = _crash_report_path
        autosave_callback = _emergency_autosave_callback
    if report_path is None:
        with _lock:
            _writing_crash_report = False
        return None

    autosave_result: str | None = None
    autosave_error: str | None = None
    if autosave_callback is not None and os.environ.get("TIGERCAPTURE_DISABLE_CRASH_AUTOSAVE") != "1":
        try:
            result = autosave_callback("crash")
            autosave_result = str(result) if result else None
        except Exception as exc:
            autosave_error = repr(exc)

    actions = recent_actions(120)
    payload = {
        "version": 1,
        "status": "unseen",
        "created_at": _now(),
        "cwd": os.getcwd(),
        "python": sys.version,
        "exception": {
            "type": getattr(exc_type, "__name__", str(exc_type)),
            "message": str(exc_value),
        },
        "traceback": "".join(traceback.format_exception(exc_type, exc_value, tb)),
        "recent_actions": actions,
        "actor_context": actor_context_from_actions(actions),
        "emergency_autosave": {
            "path": autosave_result,
            "error": autosave_error,
        },
    }
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
            errors="replace",
        )
        record_action("crash_report.written", path=str(report_path))
        return report_path
    except Exception:
        return None
    finally:
        with _lock:
            _writing_crash_report = False


def install_crash_reporter(log_dir: str | Path, *, prior_excepthook=None) -> None:
    """Install a sys.excepthook wrapper that writes JSON crash context."""
    global _installed
    configure_crash_reporting(log_dir)
    if _installed:
        return
    _installed = True
    chained = prior_excepthook or sys.excepthook

    def _hook(exc_type, exc_value, tb) -> None:
        try:
            write_crash_report(exc_type, exc_value, tb)
        finally:
            if chained is not None:
                chained(exc_type, exc_value, tb)
            else:
                sys.__excepthook__(exc_type, exc_value, tb)

    sys.excepthook = _hook
