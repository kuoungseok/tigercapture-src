from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from app.startup_trace import startup_trace_log_path

    TRACE_PATH = startup_trace_log_path()
except Exception:
    TRACE_PATH = ROOT / "logs" / "startup_flicker_trace.jsonl"


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"event": "parse_error", "raw": line})
    return rows


def _brief_command(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value[:5])
    return str(value or "")


def _is_suspicious_window(row: dict[str, Any]) -> bool:
    if row.get("app_related") is False:
        return False
    title = str(row.get("title") or "").strip().lower()
    class_name = str(row.get("class_name") or "").strip().lower()
    proc = row.get("process")
    exe = ""
    if isinstance(proc, dict):
        exe = str(proc.get("exe") or "").lower()
    if "console" in class_name or "terminal" in class_name:
        return True
    if exe in {"conhost.exe", "cmd.exe", "powershell.exe"}:
        return True
    if title in {"python", "python.exe", "cmd", "cmd.exe", "powershell", "windows powershell"}:
        return True
    if title == "" and exe in {"python.exe", "pythonw.exe"}:
        return True
    return False


def analyze(path: Path = TRACE_PATH) -> str:
    rows = _load_rows(path)
    if not rows:
        return f"No startup trace rows found at {path}"

    counts = Counter(str(row.get("event") or "") for row in rows)
    lines = [
        f"Trace: {path}",
        f"Rows: {len(rows)}",
        "Events:",
    ]
    for event, count in counts.most_common():
        lines.append(f"  {event}: {count}")

    lines.append("")
    lines.append("Timeline:")
    for idx, row in enumerate(rows[:240], start=1):
        event = str(row.get("event") or "")
        ts = str(row.get("ts") or "")
        if event.startswith("controller.") or event.startswith("video_editor.") or event.startswith("launcher."):
            lines.append(f"  {idx:03d} {ts} {event}")
        elif event == "subprocess.popen.before":
            lines.append(
                f"  {idx:03d} {ts} subprocess: {_brief_command(row.get('command'))} "
                f"flags={row.get('creationflags')}"
            )
        elif event == "process.new":
            lines.append(
                f"  {idx:03d} {ts} process: pid={row.get('pid')} "
                f"ppid={row.get('ppid')} exe={row.get('exe')}"
            )
        elif event == "process.external_new" and idx <= 40:
            parent = row.get("parent") if isinstance(row.get("parent"), dict) else {}
            lines.append(
                f"  {idx:03d} {ts} external process: pid={row.get('pid')} "
                f"ppid={row.get('ppid')} exe={row.get('exe')} "
                f"parent_exe={parent.get('exe') if isinstance(parent, dict) else ''}"
            )
        elif event == "native_window.new":
            proc = row.get("process") if isinstance(row.get("process"), dict) else {}
            marker = " *" if _is_suspicious_window(row) else ""
            lines.append(
                f"  {idx:03d} {ts} window{marker}: hwnd={row.get('hwnd')} "
                f"pid={row.get('pid')} exe={proc.get('exe') if isinstance(proc, dict) else ''} "
                f"class={row.get('class_name')!r} title={row.get('title')!r} "
                f"visible={row.get('visible')} rect={row.get('rect')}"
            )
        elif event == "native_window.event":
            proc = row.get("process") if isinstance(row.get("process"), dict) else {}
            parent = row.get("parent") if isinstance(row.get("parent"), dict) else {}
            marker = " *" if _is_suspicious_window(row) else ""
            lines.append(
                f"  {idx:03d} {ts} win-event{marker}: {row.get('event_name')} "
                f"hwnd={row.get('hwnd')} pid={row.get('pid')} "
                f"exe={proc.get('exe') if isinstance(proc, dict) else ''} "
                f"parent={parent.get('exe') if isinstance(parent, dict) else ''} "
                f"class={row.get('class_name')!r} title={row.get('title')!r} "
                f"visible={row.get('visible')} rect={row.get('rect')} "
                f"app_related={row.get('app_related')}"
            )
        elif event == "qt_window.new":
            lines.append(
                f"  {idx:03d} {ts} qt: {row.get('widget_class')} "
                f"title={row.get('title')!r} visible={row.get('visible')} geometry={row.get('geometry')}"
            )

    suspicious = [
        row for row in rows
        if row.get("event") in {"native_window.new", "native_window.event"} and _is_suspicious_window(row)
    ]
    app_window_events = [
        row for row in rows
        if row.get("event") == "native_window.event" and bool(row.get("app_related"))
    ]
    subprocesses = [row for row in rows if row.get("event") == "subprocess.popen.before"]
    processes = [row for row in rows if row.get("event") == "process.new"]
    external_processes = [row for row in rows if row.get("event") == "process.external_new"]
    lines.append("")
    lines.append("Likely cause hints:")
    if suspicious:
        lines.append("  Suspicious transient console/terminal-like windows were detected:")
        for row in suspicious[:20]:
            proc = row.get("process") if isinstance(row.get("process"), dict) else {}
            parent = row.get("parent") if isinstance(row.get("parent"), dict) else {}
            lines.append(
                f"  - event={row.get('event_name', row.get('event'))} "
                f"exe={proc.get('exe') if isinstance(proc, dict) else ''} "
                f"parent={parent.get('exe') if isinstance(parent, dict) else ''} "
                f"pid={row.get('pid')} class={row.get('class_name')!r} "
                f"title={row.get('title')!r} app_related={row.get('app_related')}"
            )
    elif app_window_events:
        lines.append(
            "  No suspicious app-related console/helper windows detected; "
            "app-related native events are normal editor/show/titlebar events."
        )
    elif subprocesses:
        lines.append("  No console-like native window was sampled, but subprocess calls occurred during the trace.")
    elif processes:
        lines.append("  New processes appeared without a logged Python subprocess call; likely Qt/native library or OS helper.")
    else:
        lines.append("  No new external process/window was sampled. Flicker may be a Qt top-level widget or compositor repaint.")
    if external_processes:
        lines.append(f"  Ignored unrelated system/tool processes: {len(external_processes)}")
    if app_window_events:
        lines.append(f"  App-related native window events: {len(app_window_events)}")

    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(analyze())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
