from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.paths import runtime_log_dir  # noqa: E402

LOG_PATH = runtime_log_dir() / "visible_window_trace.jsonl"


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            rows.append({"event": "parse_error", "raw": line})
    return rows


def _exe(row: dict[str, Any]) -> str:
    proc = row.get("process") if isinstance(row.get("process"), dict) else {}
    return str(proc.get("exe") or "")


def _parent(row: dict[str, Any]) -> str:
    parent = row.get("parent") if isinstance(row.get("parent"), dict) else {}
    return str(parent.get("exe") or "")


def _is_user_visible(row: dict[str, Any]) -> bool:
    if row.get("visible") is not True:
        return False
    rect = row.get("rect")
    if not isinstance(rect, list) or len(rect) != 4:
        return True
    try:
        w = int(rect[2]) - int(rect[0])
        h = int(rect[3]) - int(rect[1])
    except Exception:
        return True
    return w > 8 and h > 8


def _is_console_like(row: dict[str, Any]) -> bool:
    exe = _exe(row).casefold()
    title = str(row.get("title") or "").casefold()
    cls = str(row.get("class_name") or "").casefold()
    return (
        exe in {"cmd.exe", "conhost.exe", "powershell.exe", "windowsterminal.exe", "openconsole.exe"}
        or "console" in cls
        or "terminal" in cls
        or title in {"cmd", "cmd.exe", "powershell", "windows powershell"}
    )


def analyze(path: Path = LOG_PATH) -> str:
    rows = _load(path)
    if not rows:
        return f"No visible window trace found at {path}"
    counts = Counter(str(r.get("event") or "") for r in rows)
    window_rows = [
        r for r in rows
        if r.get("event") in {"window.event", "window.snapshot_new"}
    ]
    visible_rows = [r for r in window_rows if _is_user_visible(r)]
    related_rows = [r for r in window_rows if bool(r.get("related"))]
    console_rows = [r for r in window_rows if _is_console_like(r)]
    visible_console_rows = [r for r in visible_rows if _is_console_like(r)]
    by_exe = Counter(_exe(r) for r in window_rows)
    by_visible_exe = Counter(_exe(r) for r in visible_rows)

    lines = [
        f"Trace: {path}",
        f"Rows: {len(rows)}",
        "Events:",
    ]
    for event, count in counts.most_common():
        lines.append(f"  {event}: {count}")
    lines.extend([
        "",
        f"Window events/snapshots: {len(window_rows)}",
        f"User-visible window rows: {len(visible_rows)}",
        f"Related window rows: {len(related_rows)}",
        f"Console-like window rows: {len(console_rows)}",
        f"Visible console-like rows: {len(visible_console_rows)}",
        "",
        "By process:",
    ])
    for exe, count in by_exe.most_common(20):
        lines.append(f"  {exe or '<unknown>'}: {count}")
    lines.append("")
    lines.append("Visible by process:")
    for exe, count in by_visible_exe.most_common(20):
        lines.append(f"  {exe or '<unknown>'}: {count}")

    lines.append("")
    lines.append("Timeline:")
    for idx, row in enumerate(window_rows[:160], start=1):
        marker = []
        if _is_user_visible(row):
            marker.append("visible")
        if bool(row.get("related")):
            marker.append("related")
        if _is_console_like(row):
            marker.append("console")
        tag = f" [{' '.join(marker)}]" if marker else ""
        lines.append(
            f"  {idx:03d} {row.get('ts')} {row.get('event')} "
            f"{row.get('event_name', '')}{tag} "
            f"exe={_exe(row)} parent={_parent(row)} "
            f"class={row.get('class_name')!r} title={row.get('title')!r} "
            f"visible={row.get('visible')} rect={row.get('rect')}"
        )

    if visible_console_rows:
        lines.append("")
        lines.append("Likely visible console flash source:")
        for row in visible_console_rows[:20]:
            chain = row.get("parent_chain") if isinstance(row.get("parent_chain"), list) else []
            chain_text = " <- ".join(str(item.get("exe")) for item in chain if isinstance(item, dict))
            lines.append(
                f"  - {row.get('ts')} exe={_exe(row)} parent={_parent(row)} "
                f"title={row.get('title')!r} class={row.get('class_name')!r} chain={chain_text}"
            )
    elif visible_rows:
        lines.append("")
        lines.append("Visible non-console windows were captured; inspect timeline above.")
    else:
        lines.append("")
        lines.append("No user-visible top-level windows were captured during this trace.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a visible window startup trace.")
    parser.add_argument("path", nargs="?", type=Path, default=LOG_PATH)
    args = parser.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(analyze(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
