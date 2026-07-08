"""Video editor workflow glue for NLE role-lane filtering."""
from __future__ import annotations

from typing import Any


def _role_filter_model(owner: Any, *, focused_role: str | None = None) -> dict[str, Any]:
    from app.nle_visual_feedback import build_role_lane_filter_model

    focus = str(getattr(owner, "_nle_role_lane_focus", "") or "") if focused_role is None else str(focused_role or "")
    return build_role_lane_filter_model(
        getattr(owner, "_tracks", []) or [],
        focused_role=focus,
    )


def refresh_nle_role_filter_bar(self) -> None:
    bar = getattr(self, "_nle_role_filter_bar", None)
    if bar is None:
        return
    try:
        bar.set_model(_role_filter_model(self))
    except Exception:
        try:
            bar.setVisible(False)
        except Exception:
            pass


def apply_nle_role_focus_to_rows(self, role: str = "") -> None:
    text = str(role or "").strip()
    if text:
        try:
            from app.nle_connected_clips import normalize_clip_role

            text = normalize_clip_role(text, fallback="primary")
        except Exception:
            text = text.casefold().replace("-", "_").replace(" ", "_")
    setattr(self, "_nle_role_lane_focus", text)
    for row in list((getattr(self, "_track_rows", {}) or {}).values()):
        setter = getattr(row, "set_focused_clip_role", None)
        if callable(setter):
            setter(text)


def set_nle_role_lane_focus_from_ui(self, role: str = "") -> None:
    current = str(getattr(self, "_nle_role_lane_focus", "") or "")
    requested = str(role or "").strip()
    clear = not requested or requested == current
    registry_fn = getattr(self, "_ensure_python_action_registry", None)
    if callable(registry_fn):
        try:
            registry = registry_fn()
            registry.execute(
                "timeline.role_lanes.focus",
                {"role": requested, "clear": clear},
            )
        except Exception:
            apply_nle_role_focus_to_rows(self, "" if clear else requested)
    else:
        apply_nle_role_focus_to_rows(self, "" if clear else requested)
    refresh_nle_role_filter_bar(self)
    update_status = getattr(self, "_update_timeline_status", None)
    if callable(update_status):
        update_status()
    flash = getattr(self, "_flash_status", None)
    if callable(flash):
        focus = str(getattr(self, "_nle_role_lane_focus", "") or "")
        flash("Timeline role filter: All" if not focus else f"Timeline role filter: {focus.replace('_', ' ').title()}")


__all__ = [
    "apply_nle_role_focus_to_rows",
    "refresh_nle_role_filter_bar",
    "set_nle_role_lane_focus_from_ui",
]
