"""AR/PBR asset-preview lighting and material actions."""
from __future__ import annotations

from typing import Any

from app.actions.editor_adapter_ar_pbr_base import ArPbrBaseAdapterMixin


class ArPbrSettingsAdapterMixin(ArPbrBaseAdapterMixin):
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
