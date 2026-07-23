"""Adapter methods for the AR/PBR image texture-map lab."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from app.actions.editor_adapter_ar_pbr_base import ArPbrBaseAdapterMixin
from app.ar_pbr.texture_map_lab import export_texture_maps, render_plane_preview, substrate_export_plan


class ArPbrTextureLabAdapterMixin(ArPbrBaseAdapterMixin):
    def ar_pbr_texture_lab_open(self, *, image_path: str) -> dict[str, Any]:
        owner = self._require_owner()
        path = Path(str(image_path or "")).expanduser()
        if not path.exists():
            raise FileNotFoundError(str(path))
        from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

        windows = getattr(owner, "_ar_pbr_texture_lab_windows", None)
        if not isinstance(windows, list):
            windows = []
            setattr(owner, "_ar_pbr_texture_lab_windows", windows)
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
            if Path(str(getattr(window, "image_path", ""))).expanduser() == path:
                window.show()
                window.raise_()
                window.activateWindow()
                return {"window": "ar_pbr_texture_lab", "reused": True, "image_path": str(path)}
        window = ArPbrTextureMapLabWindow(path, owner)
        windows.append(window)
        window.show()
        window.raise_()
        window.activateWindow()
        flash = getattr(owner, "_flash_status", None)
        if callable(flash):
            try:
                flash(f"AR/PBR texture lab opened: {path.name}")
            except Exception:
                pass
        return {"window": "ar_pbr_texture_lab", "reused": False, "image_path": str(path)}

    def ar_pbr_texture_lab_preview(
        self,
        *,
        image_path: str,
        output_path: str | None = None,
        preview_mode: str = "material",
        width: int = 768,
        height: int | None = None,
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return render_plane_preview(
            image_path,
            settings,
            preview_mode=preview_mode,
            output_path=output_path,
            width=width,
            height=height,
        )

    def ar_pbr_texture_lab_export(
        self,
        *,
        image_path: str,
        output_dir: str | None = None,
        settings: Mapping[str, Any] | None = None,
        maps: Sequence[str] | None = None,
        packed_layouts: Sequence[str] | None = None,
        max_size: int | None = None,
    ) -> dict[str, Any]:
        return export_texture_maps(
            image_path,
            output_dir,
            settings,
            maps=maps,
            packed_layouts=packed_layouts,
            max_size=max_size,
        )

    def ar_pbr_texture_lab_substrate_plan(
        self,
        *,
        settings: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        return substrate_export_plan(settings)
