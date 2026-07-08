"""AR/PBR viewport transform gizmo actions."""
from __future__ import annotations

from typing import Any

from app.actions.editor_adapter_ar_pbr_base import ArPbrBaseAdapterMixin


class ArPbrGizmoAdapterMixin(ArPbrBaseAdapterMixin):
    def ar_pbr_gizmo_state(self) -> dict[str, Any]:
        owner = self._require_owner()
        tracks = self._ar_pbr_tracks()
        active_tracks = self._ar_pbr_active_tracks()
        visible_id = str(getattr(owner, "_ar_pbr_gizmo_visible_track_id", "") or "")
        selected_id = str(getattr(owner, "_selected_ar_pbr_track_id", "") or "")
        active_ids = [str(track.get("id") or "") for track in active_tracks]
        return {
            "track_count": len(tracks),
            "active_track_ids": active_ids,
            "selected_track_id": selected_id,
            "visible_track_id": visible_id,
            "visible": bool(visible_id and visible_id in active_ids),
            "tracks": [
                {
                    "id": str(track.get("id") or ""),
                    "asset_path": str(track.get("asset_path") or track.get("path") or ""),
                    "start_ms": int(track.get("start_ms", 0) or 0),
                    "end_ms": int(track.get("end_ms", 0) or 0),
                    "active": str(track.get("id") or "") in active_ids,
                }
                for track in tracks
                if isinstance(track, dict)
            ],
        }

    def ar_pbr_gizmo_show(self, *, track_id: str = "") -> dict[str, Any]:
        owner = self._require_owner()
        track = self._ar_pbr_pick_gizmo_track(track_id)
        if track is None:
            raise ValueError("AR/PBR track not found")
        resolved_id = str(track.get("id") or "")
        if not resolved_id:
            raise ValueError("AR/PBR track has no id")
        owner._selected_ar_pbr_track_id = resolved_id
        owner._ar_pbr_gizmo_visible_track_id = resolved_id
        owner._ar_pbr_gizmo_drag = None
        row_select = getattr(owner, "_set_ar_pbr_row_selection", None)
        if callable(row_select):
            try:
                row_select(resolved_id)
            except Exception:
                pass
        self._ar_pbr_refresh_gizmo_overlay()
        state = self.ar_pbr_gizmo_state()
        state["track_id"] = resolved_id
        return state

    def ar_pbr_gizmo_hide(self) -> dict[str, Any]:
        owner = self._require_owner()
        owner._ar_pbr_gizmo_visible_track_id = ""
        owner._ar_pbr_gizmo_drag = None
        end_depth_cue = getattr(owner, "_end_ar_pbr_depth_interaction_cue", None)
        if callable(end_depth_cue):
            try:
                end_depth_cue()
            except Exception:
                pass
        self._ar_pbr_refresh_gizmo_overlay()
        return self.ar_pbr_gizmo_state()
