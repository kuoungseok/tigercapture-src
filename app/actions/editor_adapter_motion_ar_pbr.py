"""Focused Motion Designer AR/PBR, camera, light, and depth actions."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.motion_designer.ar_pbr_source import (
    create_ar_pbr_layer,
    create_camera_layer,
    create_light_layer,
    set_depth_group,
)
from app.motion_designer.commands import find_layer
from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionComposition


def _set_animated(container: dict[str, Any], key: str, value: Any, *, time_ms: int | None = None) -> None:
    current = container.get(key)
    inferred = "vector3" if isinstance(value, (list, tuple)) and len(value) >= 3 else "scalar"
    if isinstance(value, bool):
        inferred = "bool"
    prop = AnimatedProperty.from_dict(current if current is not None else value, value_type=inferred)
    if time_ms is None:
        prop.default = value
    else:
        replacement = Keyframe(time_ms=max(0, int(time_ms)), value=value)
        existing = next((row for row in prop.keyframes if row.time_ms == replacement.time_ms), None)
        if existing is not None:
            replacement.id = existing.id
            prop.keyframes[prop.keyframes.index(existing)] = replacement
        else:
            prop.keyframes.append(replacement)
        prop.keyframes.sort(key=lambda row: (row.time_ms, row.id))
    container[str(key)] = prop.to_dict()


def _apply_changes(container: dict[str, Any], changes: Mapping[str, Any], *, time_ms: int | None = None) -> None:
    for key, value in changes.items():
        if isinstance(value, Mapping) and not ({"default", "keyframes", "value_type"} & set(value)):
            nested = container.get(key)
            if not isinstance(nested, dict):
                nested = {}
                container[str(key)] = nested
            _apply_changes(nested, value, time_ms=time_ms)
        elif isinstance(value, Mapping) and ({"default", "keyframes", "value_type"} & set(value)):
            container[str(key)] = dict(value)
        else:
            _set_animated(container, str(key), value, time_ms=time_ms)


class MotionArPbrAdapterMixin:
    def motion_ar_pbr_add(
        self,
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
        layer = create_ar_pbr_layer(
            Path(asset_path), width=composition.width, height=composition.height,
            duration_ms=composition.duration_ms, name=name or Path(asset_path).stem,
            start_ms=start_ms, end_ms=end_ms or composition.duration_ms, params=params,
        )
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Add Motion AR/PBR Object",
            "layer": layer.to_dict(),
            "renderer": "existing_ar_pbr_full_gpu_service",
        }

    def motion_ar_pbr_set_material(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
        time_ms: int | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != "ar_pbr":
            raise ValueError(f"motion layer is not AR/PBR: {layer_id}")
        material = layer.source.params.setdefault("material", {})
        _apply_changes(material, changes, time_ms=time_ms)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Set Motion AR/PBR Material", "material": dict(material)}

    def motion_camera_add(
        self,
        *,
        composition_id: str,
        name: str = "Camera",
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = create_camera_layer(duration_ms=composition.duration_ms, name=name, params=params)
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Add Motion Camera", "layer": layer.to_dict()}

    def motion_camera_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
        time_ms: int | None = None,
    ) -> dict[str, Any]:
        return self._motion_ar_pbr_control_update(
            composition_id=composition_id, layer_id=layer_id, expected_type="camera",
            changes=changes, time_ms=time_ms, undo_label="Update Motion Camera",
        )

    def motion_light_add(
        self,
        *,
        composition_id: str,
        name: str = "Key Light",
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = create_light_layer(duration_ms=composition.duration_ms, name=name, params=params)
        composition.layers.append(layer)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Add Motion Light", "layer": layer.to_dict()}

    def motion_light_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        changes: Mapping[str, Any],
        time_ms: int | None = None,
    ) -> dict[str, Any]:
        return self._motion_ar_pbr_control_update(
            composition_id=composition_id, layer_id=layer_id, expected_type="light",
            changes=changes, time_ms=time_ms, undo_label="Update Motion Light",
        )

    def _motion_ar_pbr_control_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        expected_type: str,
        changes: Mapping[str, Any],
        time_ms: int | None,
        undo_label: str,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        layer = find_layer(composition, layer_id)
        if layer.layer_type != expected_type:
            raise ValueError(f"motion layer is not {expected_type}: {layer_id}")
        _apply_changes(layer.source.params, changes, time_ms=time_ms)
        composition.revision += 1
        self._motion_sync_owner()
        return {"changed": True, "undo_label": undo_label, "layer": layer.to_dict()}

    def motion_depth_group_set(
        self,
        *,
        composition_id: str,
        member_layer_ids: list[str],
        group_id: str = "",
        depth_source_id: str = "",
        depth_frame_path: str = "",
        occlusion: bool = True,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"motion composition not found: {composition_id}")
        row = set_depth_group(
            composition, group_id=group_id, member_layer_ids=member_layer_ids,
            depth_source_id=depth_source_id, depth_frame_path=depth_frame_path, occlusion=occlusion,
        )
        self._motion_sync_owner()
        return {"changed": True, "undo_label": "Set Motion Depth Group", "depth_group": row}

    def motion_ar_pbr_diagnostics(self, *, layer_id: str = "") -> dict[str, Any]:
        from app.motion_designer.adapters.ar_pbr import ar_pbr_diagnostics

        return ar_pbr_diagnostics(layer_id)


__all__ = ["MotionArPbrAdapterMixin"]
