"""Action adapter for Motion Designer source-time remapping."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.time_remap import (
    apply_time_remap_preset,
    clear_layer_time_remap,
    set_layer_time_remap,
    time_remap_diagnostics,
)


class MotionTimeAdapterMixin:
    def motion_frame_blending_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        mode: str,
        source_fps: float = 0.0,
    ) -> dict[str, Any]:
        from app.motion_designer.frame_blending import set_layer_frame_blending

        service = self._motion_service()
        result = service.update_layer(
            composition_id,
            layer_id,
            {"metadata": self._motion_time_metadata(
                service.get(composition_id),
                layer_id,
                lambda layer: set_layer_frame_blending(
                    layer,
                    mode,
                    source_fps=source_fps,
                ),
            )},
        )
        result.undo_label = "Set Frame Blending"
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_frame_blending_preflight(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        from app.motion_designer.frame_blending import frame_blending_preflight

        composition = self._motion_service().get(composition_id)
        layer = next(
            (row for row in composition.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        return frame_blending_preflight(layer)

    def motion_graph_roving_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        property_name: str,
        keyframe_ids: Sequence[str],
        enabled: bool = True,
    ) -> dict[str, Any]:
        from app.motion_designer.graph_editing import set_roving_keyframes
        from app.motion_designer.schema import MotionLayer

        service = self._motion_service()
        composition = service.get(composition_id)
        layer = next(
            (row for row in composition.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        candidate = MotionLayer.from_dict(layer.to_dict())
        keyframes = set_roving_keyframes(
            candidate,
            property_name,
            keyframe_ids,
            enabled=enabled,
        )
        result = service.update_layer(
            composition_id,
            layer_id,
            {
                "transform": candidate.transform.to_dict(),
                "source": candidate.source.to_dict(),
                "metadata": candidate.metadata,
            },
        )
        result.undo_label = "Set Roving Keyframes"
        result.payload["keyframes"] = keyframes
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_graph_tangent_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        property_name: str,
        keyframe_id: str,
        mode: str = "auto",
        in_tangent: Sequence[float] | None = None,
        out_tangent: Sequence[float] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.graph_editing import update_keyframe_tangent

        service = self._motion_service()
        composition = service.get(composition_id)
        layer = next(
            (row for row in composition.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        from app.motion_designer.schema import MotionLayer

        candidate = MotionLayer.from_dict(layer.to_dict())
        keyframe = update_keyframe_tangent(
            candidate,
            property_name,
            keyframe_id,
            mode=mode,
            in_tangent=in_tangent,
            out_tangent=out_tangent,
        )
        result = service.update_layer(
            composition_id,
            layer_id,
            {
                "transform": candidate.transform.to_dict(),
                "source": candidate.source.to_dict(),
                "metadata": candidate.metadata,
            },
        )
        result.undo_label = "Update Graph Tangent"
        result.payload["keyframe"] = keyframe
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_time_remap_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        keyframes: Sequence[Mapping[str, Any]],
        default: float = 0.0,
    ) -> dict[str, Any]:
        service = self._motion_service()
        result = service.update_layer(
            composition_id,
            layer_id,
            {"metadata": self._motion_time_metadata(
                service.get(composition_id),
                layer_id,
                lambda layer: set_layer_time_remap(
                    layer,
                    keyframes,
                    default=default,
                ),
            )},
        )
        result.undo_label = "Set Time Remap"
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_time_remap_preset(
        self,
        *,
        composition_id: str,
        layer_id: str,
        preset: str,
    ) -> dict[str, Any]:
        service = self._motion_service()
        result = service.update_layer(
            composition_id,
            layer_id,
            {"metadata": self._motion_time_metadata(
                service.get(composition_id),
                layer_id,
                lambda layer: apply_time_remap_preset(layer, preset),
            )},
        )
        result.undo_label = "Apply Time Remap Preset"
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_time_remap_clear(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        service = self._motion_service()
        result = service.update_layer(
            composition_id,
            layer_id,
            {"metadata": self._motion_time_metadata(
                service.get(composition_id),
                layer_id,
                clear_layer_time_remap,
            )},
        )
        result.undo_label = "Clear Time Remap"
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_time_remap_inspect(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_service().get(composition_id)
        layer = next(
            (row for row in composition.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        return time_remap_diagnostics(layer)

    @staticmethod
    def _motion_time_metadata(composition, layer_id: str, operation):
        layer = next(
            (row for row in composition.layers if row.id == layer_id),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        from app.motion_designer.schema import MotionLayer

        candidate = MotionLayer.from_dict(layer.to_dict())
        operation(candidate)
        return candidate.metadata


__all__ = ["MotionTimeAdapterMixin"]
