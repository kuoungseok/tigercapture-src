"""Action adapter for Motion Designer Puppet Mesh deformation."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.puppet_mesh import (
    add_puppet_pin,
    bind_puppet_pin_to_rig,
    configure_puppet_tear_repair,
    create_alpha_adaptive_puppet_mesh,
    create_grid_puppet_mesh,
    delete_puppet_pin,
    layer_puppet_mesh,
    puppet_mesh_diagnostics,
    remove_puppet_mesh,
    update_puppet_pin,
)
from app.motion_designer.schema import MotionLayer


class MotionPuppetAdapterMixin:
    def _motion_puppet_mutate(
        self,
        composition_id: str,
        layer_id: str,
        operation,
        undo_label: str,
    ) -> dict[str, Any]:
        service = self._motion_service()
        composition = service.get(str(composition_id))
        source = next(
            (layer for layer in composition.layers if layer.id == str(layer_id)),
            None,
        )
        if source is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        candidate = MotionLayer.from_dict(source.to_dict())
        payload = dict(operation(candidate) or {})
        result = service.update_layer(
            composition.id,
            source.id,
            {"metadata": candidate.metadata},
        )
        result.undo_label = undo_label
        result.payload.update(payload)
        if not result.validation.ok:
            raise ValueError(result.validation.issues[0].message)
        self._motion_commit(service)
        self._motion_sync_owner()
        return result.to_dict()

    def motion_puppet_inspect(
        self,
        *,
        composition_id: str,
        layer_id: str,
        time_ms: int = 0,
    ) -> dict[str, Any]:
        composition = self._motion_service().get(str(composition_id))
        layer = next(
            (row for row in composition.layers if row.id == str(layer_id)),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        mesh = layer_puppet_mesh(layer)
        return {
            "composition_id": composition.id,
            "layer_id": layer.id,
            "mesh": mesh.to_dict() if mesh is not None else None,
            "diagnostics": (
                puppet_mesh_diagnostics(mesh, time_ms)
                if mesh is not None
                else None
            ),
        }

    def motion_puppet_mesh_create(
        self,
        *,
        composition_id: str,
        layer_id: str,
        columns: int = 8,
        rows: int = 8,
        adaptive: bool = True,
        alpha_threshold: int = 4,
    ) -> dict[str, Any]:
        def operation(layer):
            creator = (
                create_alpha_adaptive_puppet_mesh
                if adaptive
                else create_grid_puppet_mesh
            )
            kwargs = {"columns": columns, "rows": rows}
            if adaptive:
                kwargs["alpha_threshold"] = alpha_threshold
            return {"mesh": creator(layer, **kwargs).to_dict()}

        return self._motion_puppet_mutate(
            composition_id,
            layer_id,
            operation,
            "Create Puppet Mesh",
        )

    def motion_puppet_mesh_remove(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        def operation(layer):
            if not remove_puppet_mesh(layer):
                raise ValueError("Layer has no puppet mesh")
            return {"layer_id": layer.id}

        return self._motion_puppet_mutate(
            composition_id, layer_id, operation, "Remove Puppet Mesh",
        )

    def motion_puppet_repair_configure(
        self,
        *,
        composition_id: str,
        layer_id: str,
        enabled: bool = True,
        max_edge_stretch: float = 6.0,
    ) -> dict[str, Any]:
        return self._motion_puppet_mutate(
            composition_id,
            layer_id,
            lambda layer: {
                "tear_repair": configure_puppet_tear_repair(
                    layer,
                    enabled=enabled,
                    max_edge_stretch=max_edge_stretch,
                ),
            },
            "Configure Puppet Tear Repair",
        )

    def motion_puppet_pin_add(
        self,
        *,
        composition_id: str,
        layer_id: str,
        kind: str,
        position: Sequence[float],
        name: str = "",
        radius: float = 0.35,
        strength: float = 1.0,
    ) -> dict[str, Any]:
        return self._motion_puppet_mutate(
            composition_id,
            layer_id,
            lambda layer: {
                "pin": add_puppet_pin(
                    layer,
                    kind=kind,
                    position=position,
                    name=name,
                    radius=radius,
                    strength=strength,
                ).to_dict(),
            },
            "Add Puppet Pin",
        )

    def motion_puppet_pin_update(
        self,
        *,
        composition_id: str,
        layer_id: str,
        pin_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        return self._motion_puppet_mutate(
            composition_id,
            layer_id,
            lambda layer: {
                "pin": update_puppet_pin(
                    layer, pin_id, changes,
                ).to_dict(),
            },
            "Update Puppet Pin",
        )

    def motion_puppet_pin_bind_rig(
        self,
        *,
        composition_id: str,
        layer_id: str,
        pin_id: str,
        rig_id: str,
        bone_id: str,
    ) -> dict[str, Any]:
        return self._motion_puppet_mutate(
            composition_id,
            layer_id,
            lambda layer: {
                "pin": bind_puppet_pin_to_rig(
                    layer,
                    pin_id,
                    rig_id=rig_id,
                    bone_id=bone_id,
                ).to_dict(),
            },
            "Bind Puppet Pin to Rig",
        )

    def motion_puppet_pin_delete(
        self,
        *,
        composition_id: str,
        layer_id: str,
        pin_id: str,
    ) -> dict[str, Any]:
        def operation(layer):
            if not delete_puppet_pin(layer, pin_id):
                raise ValueError(f"Unknown puppet pin: {pin_id}")
            return {"pin_id": str(pin_id)}

        return self._motion_puppet_mutate(
            composition_id, layer_id, operation, "Delete Puppet Pin",
        )


__all__ = ["MotionPuppetAdapterMixin"]
