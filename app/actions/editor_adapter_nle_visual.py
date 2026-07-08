"""Final Cut-style NLE visual feedback adapter methods."""
from __future__ import annotations

from typing import Any


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        return int(default)


class NleVisualFeedbackAdapterMixin:
    """Adapter methods for UI-ready NLE visual feedback contracts."""

    def connected_anchor_overlay(
        self,
        *,
        selected_track_id: int | None = None,
        selected_clip_id: int | None = None,
    ) -> dict[str, Any]:
        from app.nle_visual_feedback import build_connected_anchor_overlay

        return build_connected_anchor_overlay(
            getattr(self._require_owner(), "_tracks", []) or [],
            selected_track_id=selected_track_id,
            selected_clip_id=selected_clip_id,
        )

    def role_lane_filter_model(
        self,
        *,
        focused_role: str | None = None,
        include_empty_roles: bool = True,
    ) -> dict[str, Any]:
        from app.nle_visual_feedback import build_role_lane_filter_model

        owner = self._require_owner()
        focus = str(getattr(owner, "_nle_role_lane_focus", "") or "") if focused_role is None else str(focused_role or "")
        return build_role_lane_filter_model(
            getattr(owner, "_tracks", []) or [],
            focused_role=focus,
            include_empty_roles=bool(include_empty_roles),
        )

    def magnetic_drag_preview(
        self,
        *,
        track_id: int,
        clip_id: int,
        target_start_ms: int,
        snap_threshold_ms: int = 120,
    ) -> dict[str, Any]:
        from app.nle_visual_feedback import build_magnetic_drag_preview

        return build_magnetic_drag_preview(
            getattr(self._require_owner(), "_tracks", []) or [],
            track_id=_int(track_id, -1),
            clip_id=_int(clip_id, -1),
            target_start_ms=_int(target_start_ms, 0),
            snap_threshold_ms=max(0, _int(snap_threshold_ms, 120)),
        )


__all__ = ["NleVisualFeedbackAdapterMixin"]
