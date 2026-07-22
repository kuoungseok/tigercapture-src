"""Focused Motion Designer MMD source actions."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.mmd_source import MMD_SOURCE_KIND, create_mmd_layer, update_mmd_params


class MotionMMDAdapterMixin:
    def motion_mmd_add(
        self,
        *,
        composition_id: str,
        model_path: str,
        motion_path: str = "",
        name: str = "",
        start_ms: int = 0,
        end_ms: int = 0,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = create_mmd_layer(
            Path(model_path), motion_path=Path(motion_path) if motion_path else None,
            width=composition.width, height=composition.height,
            duration_ms=composition.duration_ms, name=name or Path(model_path).stem,
            start_ms=start_ms, end_ms=end_ms or composition.duration_ms, params=params,
        )
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Add Motion MMD Actor",
            "layer": layer.to_dict(),
            "renderer": "mmd_toon_opengl",
        }

    def motion_mmd_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != MMD_SOURCE_KIND:
            raise ValueError(f"motion layer is not an MMD actor: {layer_id}")
        update_mmd_params(layer, changes)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Update Motion MMD Actor", "layer": layer.to_dict()}

    def motion_mmd_motion_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        motion_path: str,
    ) -> dict[str, Any]:
        return self.motion_mmd_update(
            composition_id=composition_id,
            layer_id=layer_id,
            changes={"asset": {"motion_path": str(Path(motion_path).expanduser().resolve())}},
        )

    def motion_mmd_diagnostics(self, *, layer_id: str = "") -> dict[str, Any]:
        from app.motion_designer.adapters.mmd import mmd_diagnostics

        return mmd_diagnostics(layer_id)


__all__ = ["MotionMMDAdapterMixin"]
