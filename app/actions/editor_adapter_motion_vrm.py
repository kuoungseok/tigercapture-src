"""Focused Motion Designer VRM/MToon avatar actions."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.motion_designer.commands import find_layer
from app.motion_designer.vrm_source import VRM_SOURCE_KIND, create_vrm_layer, update_vrm_params
from app.vtuber.vrm_renderer import VRM_RENDERER_GPU


class MotionVRMAdapterMixin:
    def motion_vrm_add(
        self,
        *,
        composition_id: str,
        avatar_path: str,
        name: str = "",
        start_ms: int = 0,
        end_ms: int = 0,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = create_vrm_layer(
            Path(avatar_path), width=composition.width, height=composition.height,
            duration_ms=composition.duration_ms, name=name or Path(avatar_path).stem,
            start_ms=start_ms, end_ms=end_ms or composition.duration_ms, params=params,
        )
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Add Motion VRM Avatar",
            "layer": layer.to_dict(),
            "renderer": VRM_RENDERER_GPU,
        }

    def motion_vrm_update(
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
        if layer.layer_type != VRM_SOURCE_KIND:
            raise ValueError(f"motion layer is not a VRM avatar: {layer_id}")
        update_vrm_params(layer, changes)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Update Motion VRM Avatar", "layer": layer.to_dict()}

    def motion_vrm_pose_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        pose: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self.motion_vrm_update(
            composition_id=composition_id,
            layer_id=layer_id,
            changes={"pose": dict(pose)},
        )

    def motion_vrm_diagnostics(self, *, layer_id: str = "") -> dict[str, Any]:
        from app.motion_designer.adapters.vrm import vrm_diagnostics

        return vrm_diagnostics(layer_id)


__all__ = ["MotionVRMAdapterMixin"]
