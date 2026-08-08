"""Focused Motion Designer Live2D and Spine actor actions."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.motion_designer.actor_source import (
    ACTOR_SOURCE_KINDS,
    LIVE2D_SOURCE_KIND,
    SPINE_SOURCE_KIND,
    create_actor_layer,
    update_actor_params,
)
from app.motion_designer.commands import find_layer


class MotionActorAdapterMixin:
    def _motion_actor_add(
        self,
        kind: str,
        *,
        composition_id: str,
        asset_path: str,
        name: str = "",
        start_ms: int = 0,
        end_ms: int = 0,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = create_actor_layer(
            kind,
            Path(asset_path),
            width=composition.width,
            height=composition.height,
            duration_ms=composition.duration_ms,
            name=name or Path(asset_path).stem,
            start_ms=start_ms,
            end_ms=end_ms or composition.duration_ms,
            params=params,
        )
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": f"Add Motion {'Live2D' if kind == LIVE2D_SOURCE_KIND else 'Spine'} Actor",
            "layer": layer.to_dict(),
            "renderer": "existing_tiger_actor_runtime",
        }

    def motion_live2d_add(self, **kwargs) -> dict[str, Any]:
        return self._motion_actor_add(LIVE2D_SOURCE_KIND, **kwargs)

    def motion_spine_add(self, **kwargs) -> dict[str, Any]:
        return self._motion_actor_add(SPINE_SOURCE_KIND, **kwargs)

    def motion_actor_update(
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
        if layer.layer_type not in ACTOR_SOURCE_KINDS:
            raise ValueError(f"motion layer is not a Live2D/Spine actor: {layer_id}")
        update_actor_params(layer, changes)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Update Motion Actor", "layer": layer.to_dict()}

    def motion_actor_lipsync_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        cues: list[Mapping[str, Any]],
        source_id: str = "",
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type not in ACTOR_SOURCE_KINDS:
            raise ValueError(f"motion layer is not a Live2D/Spine actor: {layer_id}")
        normalized = sorted(
            (dict(row) for row in cues if isinstance(row, Mapping)),
            key=lambda row: (int(row.get("start_ms", 0) or 0), int(row.get("end_ms", 0) or 0)),
        )
        layer.metadata["lip_sync_cues"] = normalized
        layer.metadata["voice_timing_source_id"] = str(source_id or "")
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Motion Actor Lip Sync",
            "layer_id": layer.id,
            "cue_count": len(normalized),
        }

    def motion_actor_diagnostics(self, *, layer_id: str = "") -> dict[str, Any]:
        from app.motion_designer.adapters.live2d import live2d_diagnostics
        from app.motion_designer.adapters.spine import spine_diagnostics

        if layer_id:
            return live2d_diagnostics(layer_id) or spine_diagnostics(layer_id)
        return {"live2d": live2d_diagnostics(), "spine": spine_diagnostics()}


__all__ = ["MotionActorAdapterMixin"]
