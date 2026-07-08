"""AR/PBR main-preview diagnostics and depth-view actions."""
from __future__ import annotations

from typing import Any

from app.actions.editor_adapter_ar_pbr_base import ArPbrBaseAdapterMixin
from app.ar_pbr.preview_diagnostics import preview_diagnostics_payload


class ArPbrDepthAdapterMixin(ArPbrBaseAdapterMixin):
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

    @staticmethod
    def _normalize_depth_view_mode(mode: Any) -> str:
        from app.ar_pbr.depth_view import normalize_depth_view_mode

        return normalize_depth_view_mode(mode)

    def _ar_pbr_player_depth_view_mode(self, player: Any) -> str:
        getter = getattr(player, "ar_pbr_depth_view_mode", None)
        if callable(getter):
            try:
                return self._normalize_depth_view_mode(getter())
            except Exception:
                pass
        return self._normalize_depth_view_mode(getattr(player, "_ar_pbr_depth_view_mode_value", "off"))

    def _refresh_ar_pbr_depth_view_preview(self) -> None:
        owner = self.owner
        if owner is None:
            return
        player = getattr(owner, "_player", None)
        if player is not None:
            try:
                setattr(player, "_last_preview_frame_cache", None)
            except Exception:
                pass
            set_position = getattr(player, "set_position", None)
            if callable(set_position):
                try:
                    set_position(int(getattr(player, "_position_ms", 0) or 0))
                    return
                except Exception:
                    pass
        for name in ("_refresh_preview_canvas_interaction_hook", "_update_preview_placeholder"):
            fn = getattr(owner, name, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
        gl = getattr(owner, "_preview_gl", None)
        update = getattr(gl, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def ar_pbr_preview_depth_view_get(self) -> dict[str, Any]:
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        mode = self._ar_pbr_player_depth_view_mode(player) if player is not None else "off"
        diagnostics = getattr(player, "_ar_pbr_last_diagnostics", None) if player is not None else None
        depth_diag = diagnostics.get("depth_view") if isinstance(diagnostics, dict) else None
        return {
            "viewer": "main_preview",
            "mode": mode,
            "enabled": mode != "off",
            "last_depth_view": depth_diag if isinstance(depth_diag, dict) else {},
        }

    def ar_pbr_preview_depth_view_set(self, mode: str = "grayscale", refresh: bool = True) -> dict[str, Any]:
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        if player is None:
            raise ValueError("preview player not found")
        before = self._ar_pbr_player_depth_view_mode(player)
        canonical = self._normalize_depth_view_mode(mode)
        setter = getattr(player, "set_ar_pbr_depth_view_mode", None)
        if callable(setter):
            canonical = self._normalize_depth_view_mode(setter(canonical))
        else:
            setattr(player, "_ar_pbr_depth_view_mode_value", canonical)
            try:
                setattr(player, "_last_preview_frame_cache", None)
            except Exception:
                pass
        if bool(refresh):
            self._refresh_ar_pbr_depth_view_preview()
        return {
            "viewer": "main_preview",
            "before": before,
            "mode": canonical,
            "enabled": canonical != "off",
            "refreshed": bool(refresh),
        }
