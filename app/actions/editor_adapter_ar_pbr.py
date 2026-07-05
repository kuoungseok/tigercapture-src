"""AR/PBR action adapter helpers."""
from __future__ import annotations

from typing import Any

from app.ar_pbr.preview_diagnostics import preview_diagnostics_payload


class ArPbrAdapterMixin:
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

    def ar_pbr_preview_diagnostics(self) -> dict[str, Any]:
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        player_diagnostics = getattr(player, "_ar_pbr_last_diagnostics", None)
        if not isinstance(player_diagnostics, dict):
            player_diagnostics = {}
        gl = getattr(owner, "_preview_gl", None)
        gl_diagnostics: dict[str, Any] = {}
        overlay_diag = getattr(gl, "ar_pbr_overlay_diagnostics", None)
        if callable(overlay_diag):
            try:
                row = overlay_diag()
                if isinstance(row, dict):
                    gl_diagnostics = row
            except Exception as exc:
                gl_diagnostics = {"error": f"{type(exc).__name__}: {exc}"}
        active_tracks = self._ar_pbr_active_tracks()
        return preview_diagnostics_payload(
            tracks=self._ar_pbr_tracks(),
            active_tracks=active_tracks,
            player_diagnostics=player_diagnostics,
            gl_diagnostics=gl_diagnostics,
            frame_size=getattr(owner, "_preview_gl_frame_size", None),
            preview_gl_available=gl is not None,
        )

    def ar_pbr_preview_view_get(self) -> dict[str, Any]:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ValueError("AR/PBR preview window not found")
        gl_widget = getattr(window, "_gl_widget", None)
        state = getattr(window, "_state", None) or getattr(gl_widget, "state", None)
        if state is None:
            raise ValueError("AR/PBR preview state not ready")
        return {
            "window": "ar_pbr_preview",
            "view": self._state_payload(state),
        }

    def ar_pbr_preview_view_set(
        self,
        *,
        zoom: float | None = None,
        zoom_factor: float | None = None,
        camera_z: float | None = None,
        pitch: float | None = None,
        yaw: float | None = None,
        roll: float | None = None,
        pan_x: float | None = None,
        pan_y: float | None = None,
        pan_z: float | None = None,
        fit_first: bool = True,
        hide_environment_background: bool = False,
    ) -> dict[str, Any]:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ValueError("AR/PBR preview window not found")
        gl_widget = getattr(window, "_gl_widget", None)
        state = getattr(window, "_state", None) or getattr(gl_widget, "state", None)
        if state is None:
            raise ValueError("AR/PBR preview state not ready")
        before = self._state_payload(state)
        if bool(hide_environment_background):
            setter = getattr(window, "_set_environment_background_visible", None)
            if callable(setter):
                setter(False, emit=False)
            elif gl_widget is not None and hasattr(gl_widget, "set_environment_background_visible"):
                gl_widget.set_environment_background_visible(False)
        if bool(fit_first):
            fit = getattr(window, "fit_view", None)
            if callable(fit):
                fit()
            elif gl_widget is not None and hasattr(gl_widget, "fit_current_view"):
                gl_widget.fit_current_view()
            for key in ("pan_x", "pan_y", "pan_z"):
                try:
                    setattr(state, key, 0.0)
                except Exception:
                    pass
        current_zoom = float(getattr(state, "zoom", before["zoom"]) or before["zoom"] or 1.0)
        factor = self._coerce_optional_float(zoom_factor)
        if factor is not None:
            current_zoom *= max(0.01, min(100.0, factor))
        absolute_zoom = self._coerce_optional_float(zoom)
        if absolute_zoom is not None:
            current_zoom = absolute_zoom
        state.zoom = self._clamp(current_zoom, 0.03, 40.0)
        for key, value, minimum, maximum in (
            ("camera_z", camera_z, 0.2, 20.0),
            ("pitch", pitch, -180.0, 180.0),
            ("yaw", yaw, -360.0, 360.0),
            ("roll", roll, -180.0, 180.0),
            ("pan_x", pan_x, -20.0, 20.0),
            ("pan_y", pan_y, -20.0, 20.0),
            ("pan_z", pan_z, -20.0, 20.0),
        ):
            number = self._coerce_optional_float(value)
            if number is not None:
                setattr(state, key, self._clamp(number, minimum, maximum))
        if gl_widget is not None:
            try:
                gl_widget.auto_fit_enabled = False
                gl_widget.auto_fit_pending = False
            except Exception:
                pass
            update = getattr(gl_widget, "update", None)
            if callable(update):
                update()
        sync = getattr(window, "sync_controls", None)
        if callable(sync):
            sync()
        show = getattr(window, "show", None)
        if callable(show):
            show()
        raise_fn = getattr(window, "raise_", None)
        if callable(raise_fn):
            raise_fn()
        activate = getattr(window, "activateWindow", None)
        if callable(activate):
            activate()
        return {
            "window": "ar_pbr_preview",
            "fit_first": bool(fit_first),
            "background_hidden": bool(hide_environment_background),
            "before": before,
            "after": self._state_payload(state),
        }

    # Scene-lighting / material / tone / depth settings bridge. The preview
    # window already owns lighting_settings()/apply_lighting_settings(); these
    # actions expose that same surface to automation without touching the UI.
    _SETTINGS_CONTROL_KEYS = frozenset({"activate", "show"})

    def _ar_pbr_settings_window(self) -> Any:
        window = self._latest_ar_pbr_preview_window()
        if window is None:
            raise ValueError("AR/PBR preview window not found")
        getter = getattr(window, "lighting_settings", None)
        applier = getattr(window, "apply_lighting_settings", None)
        if not callable(getter) or not callable(applier):
            raise ValueError("AR/PBR preview settings not available")
        return window

    def ar_pbr_preview_settings_get(self) -> dict[str, Any]:
        window = self._ar_pbr_settings_window()
        return {
            "window": "ar_pbr_preview",
            "settings": dict(window.lighting_settings() or {}),
        }

    def ar_pbr_preview_settings_set(self, **params: Any) -> dict[str, Any]:
        window = self._ar_pbr_settings_window()
        before = dict(window.lighting_settings() or {})
        settings = {
            key: value
            for key, value in params.items()
            if value is not None and key not in self._SETTINGS_CONTROL_KEYS
        }
        window.apply_lighting_settings(settings, emit=True)
        show = getattr(window, "show", None)
        if callable(show):
            show()
        raise_fn = getattr(window, "raise_", None)
        if callable(raise_fn):
            raise_fn()
        activate = getattr(window, "activateWindow", None)
        if callable(activate):
            activate()
        return {
            "window": "ar_pbr_preview",
            "applied": sorted(settings.keys()),
            "before": before,
            "after": dict(window.lighting_settings() or {}),
        }

    @staticmethod
    def _ar_pbr_surface_payload(settings: dict[str, Any]) -> dict[str, Any]:
        return {
            "render_profile": str(settings.get("render_profile") or "authored"),
            "hdri_id": str(settings.get("hdri_id") or ""),
            "hdri_path": str(settings.get("hdri_path") or ""),
            "ibl_exposure": float(settings.get("ibl_exposure", 1.1) or 0.0),
            "ibl_rotation": float(settings.get("ibl_rotation", 0.0) or 0.0),
            "surface_override_strength": float(settings.get("surface_override_strength", 0.0) or 0.0),
            "surface_roughness": float(settings.get("surface_roughness", 0.45) or 0.45),
            "surface_metallic": float(settings.get("surface_metallic", 0.0) or 0.0),
            "surface_reflectance": float(settings.get("surface_reflectance", 0.5) or 0.5),
            "clearcoat_strength": float(settings.get("clearcoat_strength", 0.0) or 0.0),
            "clearcoat_roughness": float(settings.get("clearcoat_roughness", 0.12) or 0.12),
            "clearcoat_ior": float(settings.get("clearcoat_ior", 1.5) or 1.5),
        }

    def ar_pbr_preview_surface_get(self) -> dict[str, Any]:
        window = self._ar_pbr_settings_window()
        settings = dict(window.lighting_settings() or {})
        return {
            "window": "ar_pbr_preview",
            "surface": self._ar_pbr_surface_payload(settings),
        }

    def ar_pbr_preview_surface_set(
        self,
        *,
        render_profile: str | None = None,
        hdri_id: str | None = None,
        hdri_path: str | None = None,
        ibl_exposure: float | None = None,
        ibl_rotation: float | None = None,
        surface_override_strength: float | None = None,
        surface_roughness: float | None = None,
        surface_metallic: float | None = None,
        surface_reflectance: float | None = None,
        clearcoat_strength: float | None = None,
        clearcoat_roughness: float | None = None,
        clearcoat_ior: float | None = None,
        activate: bool = True,
        show: bool = True,
    ) -> dict[str, Any]:
        window = self._ar_pbr_settings_window()
        before_settings = dict(window.lighting_settings() or {})
        settings = {
            key: value
            for key, value in {
                "render_profile": render_profile,
                "hdri_id": hdri_id,
                "hdri_path": hdri_path,
                "ibl_exposure": ibl_exposure,
                "ibl_rotation": ibl_rotation,
                "surface_override_strength": surface_override_strength,
                "surface_roughness": surface_roughness,
                "surface_metallic": surface_metallic,
                "surface_reflectance": surface_reflectance,
                "clearcoat_strength": clearcoat_strength,
                "clearcoat_roughness": clearcoat_roughness,
                "clearcoat_ior": clearcoat_ior,
            }.items()
            if value is not None
        }
        window.apply_lighting_settings(settings, emit=True)
        if bool(show):
            show_fn = getattr(window, "show", None)
            if callable(show_fn):
                show_fn()
        raise_fn = getattr(window, "raise_", None)
        if bool(show) and callable(raise_fn):
            raise_fn()
        activate_fn = getattr(window, "activateWindow", None)
        if bool(activate) and callable(activate_fn):
            activate_fn()
        after_settings = dict(window.lighting_settings() or {})
        return {
            "window": "ar_pbr_preview",
            "applied": sorted(settings.keys()),
            "before": self._ar_pbr_surface_payload(before_settings),
            "after": self._ar_pbr_surface_payload(after_settings),
        }

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
