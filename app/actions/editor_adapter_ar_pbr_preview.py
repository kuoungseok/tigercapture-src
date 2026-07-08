"""AR/PBR asset-preview camera actions."""
from __future__ import annotations

from typing import Any

from app.actions.editor_adapter_ar_pbr_base import ArPbrBaseAdapterMixin


class ArPbrPreviewAdapterMixin(ArPbrBaseAdapterMixin):
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
