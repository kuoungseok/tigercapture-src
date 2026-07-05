from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from app.screenstudio_polish import normalize_cursor_events, screenstudio_interaction_report


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def cursor_sidecar_path_for_video(video_path: str | Path) -> Path:
    path = Path(video_path)
    return Path(str(path) + ".cursor.json")


def normalize_sidecar_events(events: Iterable[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for ev in normalize_cursor_events(events or []):
        row = {
            "t_ms": int(ev.t_ms),
            "x_norm": round(_clamp01(ev.x_norm), 6),
            "y_norm": round(_clamp01(ev.y_norm), 6),
            "kind": str(ev.kind or "move"),
        }
        if ev.visible is False:
            row["visible"] = False
        if ev.label:
            row["label"] = ev.label
        if ev.hit_role:
            row["hit_role"] = ev.hit_role
        if ev.hit_label:
            row["hit_label"] = ev.hit_label
        if ev.cursor_style:
            row["cursor_style"] = ev.cursor_style
        if ev.animation:
            row["animation"] = ev.animation
        rows.append(row)
    return rows


def build_cursor_sidecar_payload(
    events: Iterable[Mapping[str, Any]] | None,
    *,
    video_path: str | Path | None = None,
    duration_ms: int = 0,
    frame_w: int = 1920,
    frame_h: int = 1080,
    source: str = "manual_capture",
) -> dict[str, Any]:
    rows = normalize_sidecar_events(events)
    if int(duration_ms or 0) <= 0 and rows:
        duration_ms = max(int(row.get("t_ms", 0) or 0) for row in rows) + 1000
    report = screenstudio_interaction_report(
        rows,
        duration_ms=max(0, int(duration_ms or 0)),
        frame_w=max(1, int(frame_w or 1920)),
        frame_h=max(1, int(frame_h or 1080)),
        include_parity=False,
    )
    return {
        "version": 1,
        "kind": "screenstudio_cursor_sidecar",
        "source": str(source or "manual_capture"),
        "video_path": str(video_path or ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": max(0, int(duration_ms or 0)),
        "frame_w": max(1, int(frame_w or 1920)),
        "frame_h": max(1, int(frame_h or 1080)),
        "counts_for_qa": bool(report.get("ok")),
        "events": rows,
        "qa": {
            "ok": bool(report.get("ok")),
            "readiness": int(report.get("readiness", 0) or 0),
            "counts": dict(report.get("counts") or {}),
            "auto_zoom_count": int(report.get("auto_zoom_count", 0) or 0),
            "warnings": list(report.get("warnings", []) or []),
        },
    }


def write_cursor_sidecar(
    video_path: str | Path,
    events: Iterable[Mapping[str, Any]] | None,
    *,
    out_path: str | Path | None = None,
    duration_ms: int = 0,
    frame_w: int = 1920,
    frame_h: int = 1080,
    source: str = "manual_capture",
) -> tuple[Path, dict[str, Any]]:
    target = Path(out_path) if out_path else cursor_sidecar_path_for_video(video_path)
    payload = build_cursor_sidecar_payload(
        events,
        video_path=video_path,
        duration_ms=duration_ms,
        frame_w=frame_w,
        frame_h=frame_h,
        source=source,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, payload


def load_sidecar_template(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("sidecar template must be a JSON object")
    if str(payload.get("kind") or "") != "screenstudio_cursor_sidecar_template":
        raise ValueError("sidecar template kind must be screenstudio_cursor_sidecar_template")
    return dict(payload)


def write_cursor_sidecar_from_template(
    template_path: str | Path,
    *,
    out_path: str | Path | None = None,
    duration_ms: int = 0,
    frame_w: int = 1920,
    frame_h: int = 1080,
) -> tuple[Path, dict[str, Any]]:
    template = load_sidecar_template(template_path)
    video_path = str(template.get("source_path") or "").strip()
    if not video_path:
        raise ValueError("sidecar template is missing source_path")
    target = Path(out_path) if out_path else Path(str(template.get("target_sidecar_path") or "") or cursor_sidecar_path_for_video(video_path))
    events = template.get("events")
    if not isinstance(events, list):
        raise ValueError("sidecar template events must be an array")
    return write_cursor_sidecar(
        video_path,
        events,
        out_path=target,
        duration_ms=max(0, int(template.get("duration_ms", duration_ms) or duration_ms or 0)),
        frame_w=max(1, int(template.get("frame_w", frame_w) or frame_w or 1920)),
        frame_h=max(1, int(template.get("frame_h", frame_h) or frame_h or 1080)),
        source=f"template:{Path(template_path)}",
    )


def load_event_file(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw = payload.get("events", payload if isinstance(payload, list) else [])
    if not isinstance(raw, list):
        raise ValueError("event file must contain an events array or a top-level array")
    return [dict(row) for row in raw if isinstance(row, Mapping)]


def _screen_rect_from_tuple(rect: Sequence[int] | None, user32: Any | None = None) -> tuple[int, int, int, int]:
    if rect and len(rect) >= 4:
        x, y, w, h = [int(v) for v in rect[:4]]
        return x, y, max(1, w), max(1, h)
    if user32 is not None:
        try:
            x = int(user32.GetSystemMetrics(76))  # SM_XVIRTUALSCREEN
            y = int(user32.GetSystemMetrics(77))  # SM_YVIRTUALSCREEN
            w = int(user32.GetSystemMetrics(78))  # SM_CXVIRTUALSCREEN
            h = int(user32.GetSystemMetrics(79))  # SM_CYVIRTUALSCREEN
            if w > 0 and h > 0:
                return x, y, w, h
        except Exception:
            pass
        try:
            w = int(user32.GetSystemMetrics(0))  # SM_CXSCREEN
            h = int(user32.GetSystemMetrics(1))  # SM_CYSCREEN
            if w > 0 and h > 0:
                return 0, 0, w, h
        except Exception:
            pass
    return 0, 0, 1, 1


def capture_windows_cursor_sidecar_events(
    *,
    duration_ms: int,
    screen_rect: Sequence[int] | None = None,
    sample_ms: int = 33,
    capture_hotkeys: bool = False,
) -> list[dict[str, Any]]:
    """Capture cursor/click/drag/release events on Windows without extra deps.

    This is intentionally conservative: it samples cursor position plus mouse
    button transitions.  Hotkey capture is opt-in and records only modifier
    combinations such as Ctrl+K, not raw typed text.
    """
    try:
        import ctypes
        from ctypes import wintypes
    except Exception as exc:  # pragma: no cover - platform guard
        raise RuntimeError("Windows cursor capture requires ctypes") from exc

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    user32 = ctypes.windll.user32
    rect_x, rect_y, rect_w, rect_h = _screen_rect_from_tuple(screen_rect, user32)
    end_at = time.monotonic() + max(1, int(duration_ms or 0)) / 1000.0
    started = time.monotonic()
    last_pos: tuple[float, float] | None = None
    left_down = False
    dragging = False
    events: list[dict[str, Any]] = []
    interval = max(0.01, int(sample_ms or 33) / 1000.0)
    active_hotkeys: set[str] = set()
    modifier_keys = [
        (0x11, "Ctrl"),
        (0x10, "Shift"),
        (0x12, "Alt"),
    ]
    key_candidates = [
        *[(code, chr(code)) for code in range(0x30, 0x3A)],
        *[(code, chr(code)) for code in range(0x41, 0x5B)],
        *[(0x70 + idx, f"F{idx + 1}") for idx in range(12)],
        (0x09, "Tab"),
        (0x0D, "Enter"),
        (0x1B, "Esc"),
        (0x20, "Space"),
    ]

    def append(kind: str, x_norm: float, y_norm: float) -> None:
        events.append(
            {
                "t_ms": int(round((time.monotonic() - started) * 1000)),
                "x_norm": round(_clamp01(x_norm), 6),
                "y_norm": round(_clamp01(y_norm), 6),
                "kind": kind,
            }
        )

    def append_hotkey(label: str, x_norm: float, y_norm: float) -> None:
        events.append(
            {
                "t_ms": int(round((time.monotonic() - started) * 1000)),
                "x_norm": round(_clamp01(x_norm), 6),
                "y_norm": round(_clamp01(y_norm), 6),
                "kind": "hotkey",
                "label": label,
            }
        )

    while time.monotonic() < end_at:
        point = POINT()
        if user32.GetCursorPos(ctypes.byref(point)):
            x_norm = (int(point.x) - rect_x) / rect_w
            y_norm = (int(point.y) - rect_y) / rect_h
            inside = 0.0 <= x_norm <= 1.0 and 0.0 <= y_norm <= 1.0
            pressed = bool(user32.GetAsyncKeyState(0x01) & 0x8000)
            if inside:
                if pressed and not left_down:
                    append("click", x_norm, y_norm)
                    dragging = False
                elif pressed and left_down and last_pos is not None:
                    dx = abs(x_norm - last_pos[0])
                    dy = abs(y_norm - last_pos[1])
                    if (dx + dy) > 0.015:
                        append("drag", x_norm, y_norm)
                        dragging = True
                elif not pressed and left_down:
                    append("release", x_norm, y_norm)
                    dragging = False
                elif last_pos is None or abs(x_norm - last_pos[0]) + abs(y_norm - last_pos[1]) > 0.02:
                    append("move", x_norm, y_norm)
                last_pos = (x_norm, y_norm)
            left_down = pressed
            if capture_hotkeys and last_pos is not None:
                modifiers = [label for code, label in modifier_keys if bool(user32.GetAsyncKeyState(code) & 0x8000)]
                combos: set[str] = set()
                if modifiers:
                    for code, label in key_candidates:
                        if label in modifiers:
                            continue
                        if bool(user32.GetAsyncKeyState(code) & 0x8000):
                            combos.add("+".join([*modifiers, label]))
                for combo in sorted(combos - active_hotkeys):
                    append_hotkey(combo, last_pos[0], last_pos[1])
                active_hotkeys = combos
        time.sleep(interval)
    if left_down and last_pos is not None:
        append("release", last_pos[0], last_pos[1])
    return events
