"""Shared UX feedback copy and lightweight state helpers.

The editor has many independent panels. Keeping empty/progress/failure wording
centralized makes the app feel like one product instead of several widgets that
all invent their own status language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UXState:
    title: str
    body: str = ""
    action: str = ""
    tone: str = "neutral"  # neutral | active | success | warning | error

    def plain_text(self) -> str:
        return "\n".join(part for part in (self.title, self.body, self.action) if part)


def media_pool_empty_state(*, total: int, visible: int, query: str = "", kind_label: str = "All") -> UXState:
    total = max(0, int(total))
    visible = max(0, int(visible))
    query = str(query or "").strip()
    kind_label = str(kind_label or "All")
    if total <= 0:
        return UXState(
            "Drop media here",
            "Video, audio, and actor files appear as compact, draggable tiles.",
            "Right-click or drop files to import.",
            "active",
        )
    if visible <= 0:
        detail = f"Filter: {kind_label}"
        if query:
            detail += f" / Search: {query}"
        return UXState(
            "No matching media",
            detail,
            "Clear search or switch the media filter.",
            "warning",
        )
    return UXState(
        f"{visible} of {total} media visible",
        f"Filter: {kind_label}",
        "Drag a tile to the timeline.",
        "neutral",
    )


def audio_mixer_empty_state(track_count: int) -> UXState:
    if int(track_count or 0) <= 0:
        return UXState(
            "No audio tracks",
            "Add audio to the timeline to show mixer strips, LUFS, spectrum, and stereo scope.",
            "Drop audio in the Media Pool or import from the Sound Editor.",
            "active",
        )
    return UXState(f"{int(track_count)} audio track(s)", "Mixer strips are synced to the timeline.", tone="neutral")


def progress_state(action: str, current: int | None = None, total: int | None = None) -> UXState:
    action = str(action or "Working")
    if current is None or total in (None, 0):
        return UXState(action, "In progress...", tone="active")
    current_i = max(0, int(current))
    total_i = max(1, int(total))
    pct = min(100, round(current_i * 100 / total_i))
    return UXState(action, f"{current_i}/{total_i} ({pct}%)", tone="active")


def failure_state(area: str, message: Any, *, hint: str = "") -> UXState:
    msg = " ".join(str(message or "").replace("\r", "\n").split())
    if len(msg) > 180:
        msg = msg[:177].rstrip() + "..."
    area = str(area or "Operation")
    return UXState(
        f"{area} failed",
        msg or "No error detail was provided.",
        hint or "Check diagnostics, paths, and retry when the source is available.",
        "error",
    )


def scope_status_state(diag: dict[str, Any]) -> UXState:
    warnings = [str(w) for w in (diag.get("warnings") or []) if str(w)]
    p01 = float(diag.get("luma_ire_p01", 0.0) or 0.0)
    p99 = float(diag.get("luma_ire_p99", 0.0) or 0.0)
    sat95 = float(diag.get("saturation_p95", 0.0) or 0.0)
    body = f"Luma {p01:.1f}-{p99:.1f} IRE / Sat95 {sat95:.2f}"
    if warnings:
        return UXState("Scopes need attention", body, ", ".join(warnings[:3]), "warning")
    return UXState("Scopes nominal", body, tone="success")


def color_management_state(validation: dict[str, Any]) -> UXState:
    errors = [str(v) for v in (validation.get("errors") or []) if str(v)]
    warnings = [str(v) for v in (validation.get("warnings") or []) if str(v)]
    active = validation.get("active_luts") or []
    summary = validation.get("summary") or []
    if errors:
        return UXState("Color setup invalid", "; ".join(errors[:2]), "Fix project color settings before export.", "error")
    if warnings:
        return UXState("Color setup warning", "; ".join(warnings[:2]), "Review color management before delivery.", "warning")
    lut_text = ", ".join(str(v) for v in active) if active else "No active LUT"
    return UXState("Color setup ready", lut_text, " / ".join(str(v) for v in summary[-2:]), "success")


def tone_stylesheet(*, foreground: bool = True) -> str:
    """QSS fragment for widgets that expose a `tone` dynamic property."""
    role = "color" if foreground else "background"
    return (
        f"[tone=\"neutral\"] {{ {role}: #8A8A8A; }}"
        f"[tone=\"active\"] {{ {role}: #C8C8C8; }}"
        f"[tone=\"success\"] {{ {role}: #5DCAA5; }}"
        f"[tone=\"warning\"] {{ {role}: #E0B45C; }}"
        f"[tone=\"error\"] {{ {role}: #E54646; }}"
    )


def apply_state_to_label(label: Any, state: UXState, *, tooltip: bool = True) -> None:
    """Best-effort Qt label update without making this module depend on Qt."""
    try:
        label.setText(state.plain_text())
        label.setProperty("tone", state.tone)
        label.style().unpolish(label)
        label.style().polish(label)
        if tooltip:
            label.setToolTip(state.plain_text())
    except Exception:
        pass
