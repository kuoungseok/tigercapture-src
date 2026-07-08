"""Shared AR/PBR action adapter helpers."""
from __future__ import annotations

from typing import Any


class ArPbrBaseAdapterMixin:
    def _latest_ar_pbr_preview_window(self) -> Any | None:
        owner = self._require_owner()
        windows = list(getattr(owner, "_ar_pbr_preview_windows", []) or [])
        is_valid = getattr(owner, "_qt_object_valid", None)
        for window in reversed(windows):
            if window is None:
                continue
            if callable(is_valid):
                try:
                    if not is_valid(window):
                        continue
                except Exception:
                    pass
            return window
        registry = getattr(owner, "_ar_pbr_preview_window_registry", None)
        if isinstance(registry, dict):
            for window in reversed(list(registry.values())):
                if window is not None:
                    return window
        return None

    @staticmethod
    def _coerce_optional_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(float(minimum), min(float(maximum), float(value)))

    @staticmethod
    def _state_payload(state: Any) -> dict[str, Any]:
        return {
            "pitch": float(getattr(state, "pitch", 0.0) or 0.0),
            "yaw": float(getattr(state, "yaw", 0.0) or 0.0),
            "roll": float(getattr(state, "roll", 0.0) or 0.0),
            "zoom": float(getattr(state, "zoom", 0.0) or 0.0),
            "camera_z": float(getattr(state, "camera_z", 0.0) or 0.0),
            "pan_x": float(getattr(state, "pan_x", 0.0) or 0.0),
            "pan_y": float(getattr(state, "pan_y", 0.0) or 0.0),
            "pan_z": float(getattr(state, "pan_z", 0.0) or 0.0),
        }

    def _ar_pbr_tracks(self) -> list[dict[str, Any]]:
        owner = self.owner
        tracks = getattr(owner, "_ar_pbr_tracks", None) if owner is not None else None
        if tracks is None and owner is not None:
            tracks = []
            setattr(owner, "_ar_pbr_tracks", tracks)
        return tracks if isinstance(tracks, list) else []

    def _ar_pbr_find_track(self, track_id: str) -> dict[str, Any] | None:
        wanted = str(track_id or "")
        if not wanted:
            return None
        for track in self._ar_pbr_tracks():
            if isinstance(track, dict) and str(track.get("id") or "") == wanted:
                return track
        return None

    def _ar_pbr_active_tracks(self) -> list[dict[str, Any]]:
        owner = self._require_owner()
        active = getattr(owner, "_ar_pbr_active_tracks_at_playhead", None)
        if callable(active):
            try:
                rows = active()
                if isinstance(rows, list):
                    return [row for row in rows if isinstance(row, dict)]
            except Exception:
                pass
        return [row for row in self._ar_pbr_tracks() if isinstance(row, dict)]

    def _ar_pbr_pick_gizmo_track(self, track_id: str = "") -> dict[str, Any] | None:
        if track_id:
            return self._ar_pbr_find_track(track_id)
        owner = self._require_owner()
        selected_id = str(getattr(owner, "_selected_ar_pbr_track_id", "") or "")
        selected = self._ar_pbr_find_track(selected_id)
        if selected is not None:
            return selected
        active_tracks = self._ar_pbr_active_tracks()
        if active_tracks:
            return active_tracks[0]
        tracks = self._ar_pbr_tracks()
        return tracks[0] if tracks else None

    def _ar_pbr_refresh_gizmo_overlay(self) -> None:
        owner = self.owner
        if owner is None:
            return
        canvas = getattr(owner, "_drawing_canvas", None)
        update = getattr(canvas, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass
        popout = getattr(owner, "_preview_popout", None)
        if popout is not None:
            try:
                overlay = popout.overlay_canvas()
                overlay_update = getattr(overlay, "update", None)
                if callable(overlay_update):
                    overlay_update()
            except Exception:
                pass
