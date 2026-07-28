"""Action adapter for Motion Designer nested compositions."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.motion_designer.precomposition import (
    create_precomposition,
    embedded_composition,
    publish_precomp_property,
    set_embedded_composition,
    set_precomp_override,
    set_precomp_published_value,
)
from app.motion_designer.schema import MotionComposition
from app.motion_designer.validation import validate_composition


class MotionPrecompAdapterMixin:
    def motion_controller_create(
        self,
        *,
        composition_id: str,
        name: str = "Controller",
        position: Sequence[float] | None = None,
    ) -> dict[str, Any]:
        from app.motion_designer.controllers import create_controller_layer

        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        composition = MotionComposition.from_dict(source.to_dict())
        layer = create_controller_layer(
            composition,
            name=name,
            position=list(position)[:2] if position is not None else None,
        )
        report = validate_composition(composition)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[composition.id] = composition
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Create Motion Controller",
            "payload": {
                "composition": composition.to_dict(),
                "controller": layer.to_dict(),
            },
            "validation": report.to_dict(),
        }

    def motion_controller_link(
        self,
        *,
        composition_id: str,
        target_layer_id: str,
        target_property: str,
        controller_layer_id: str,
        controller_property: str,
    ) -> dict[str, Any]:
        from app.motion_designer.controllers import link_controller_property

        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        composition = MotionComposition.from_dict(source.to_dict())
        link = link_controller_property(
            composition,
            target_layer_id=target_layer_id,
            target_property=target_property,
            controller_layer_id=controller_layer_id,
            controller_property=controller_property,
        )
        report = validate_composition(composition)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[composition.id] = composition
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Link Motion Controller",
            "payload": {
                "composition": composition.to_dict(),
                "link": link,
            },
            "validation": report.to_dict(),
        }

    def motion_property_publish(
        self,
        *,
        composition_id: str,
        layer_id: str,
        property_name: str,
        name: str = "",
    ) -> dict[str, Any]:
        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        composition = MotionComposition.from_dict(source.to_dict())
        publication = publish_precomp_property(
            composition,
            layer_id,
            property_name,
            name=name,
        )
        report = validate_composition(composition)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[composition.id] = composition
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Publish Motion Property",
            "payload": {
                "composition": composition.to_dict(),
                "published_property": publication,
            },
            "validation": report.to_dict(),
        }

    def motion_precomp_published_value_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        publication_id: str,
        value: Any,
    ) -> dict[str, Any]:
        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        composition = MotionComposition.from_dict(source.to_dict())
        layer = next(
            (row for row in composition.layers if row.id == str(layer_id)),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        prop = set_precomp_published_value(
            layer,
            publication_id,
            value,
        )
        composition.revision += 1
        report = validate_composition(composition)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[composition.id] = composition
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Published Property",
            "payload": {
                "composition": composition.to_dict(),
                "published_value": prop.to_dict(),
            },
            "validation": report.to_dict(),
        }

    def motion_precomp_create(
        self,
        *,
        composition_id: str,
        layer_ids: Sequence[str],
        name: str = "Pre-compose",
    ) -> dict[str, Any]:
        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        parent = MotionComposition.from_dict(source.to_dict())
        child, layer = create_precomposition(parent, layer_ids, name=name)
        for candidate in (child, parent):
            report = validate_composition(candidate)
            if not report.ok:
                raise ValueError(report.issues[0].message)
        store[child.id] = child
        store[parent.id] = parent
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Pre-compose Layers",
            "payload": {
                "composition": parent.to_dict(),
                "nested_composition": child.to_dict(),
                "precomp_layer": layer.to_dict(),
            },
            "validation": {"ok": True, "issues": []},
        }

    def motion_precomp_inspect(
        self,
        *,
        composition_id: str,
        layer_id: str,
    ) -> dict[str, Any]:
        composition = self._motion_store().get(str(composition_id))
        if composition is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        layer = next(
            (row for row in composition.layers if row.id == str(layer_id)),
            None,
        )
        child = embedded_composition(layer) if layer is not None else None
        if child is None:
            raise ValueError(f"Layer is not a pre-composition: {layer_id}")
        return {
            "composition_id": composition.id,
            "layer_id": layer.id,
            "nested_composition": child.to_dict(),
            "overrides": dict(layer.source.params.get("overrides") or {}),
        }

    def motion_precomp_override_set(
        self,
        *,
        composition_id: str,
        layer_id: str,
        child_layer_id: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        store = self._motion_store()
        source = store.get(str(composition_id))
        if source is None:
            raise ValueError(f"Unknown composition: {composition_id}")
        parent = MotionComposition.from_dict(source.to_dict())
        layer = next(
            (row for row in parent.layers if row.id == str(layer_id)),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        override = set_precomp_override(layer, child_layer_id, changes)
        parent.revision += 1
        report = validate_composition(parent)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[parent.id] = parent
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Set Pre-compose Override",
            "payload": {
                "composition": parent.to_dict(),
                "override": override,
            },
            "validation": report.to_dict(),
        }

    def motion_precomp_refresh(
        self,
        *,
        composition_id: str,
        layer_id: str,
        nested_composition_id: str,
    ) -> dict[str, Any]:
        store = self._motion_store()
        parent_source = store.get(str(composition_id))
        child = store.get(str(nested_composition_id))
        if parent_source is None or child is None:
            raise ValueError("Unknown parent or nested composition")
        parent = MotionComposition.from_dict(parent_source.to_dict())
        layer = next(
            (row for row in parent.layers if row.id == str(layer_id)),
            None,
        )
        if layer is None:
            raise ValueError(f"Unknown layer: {layer_id}")
        set_embedded_composition(layer, child)
        parent.revision += 1
        report = validate_composition(parent)
        if not report.ok:
            raise ValueError(report.issues[0].message)
        store[parent.id] = parent
        self._motion_sync_owner()
        return {
            "changed": True,
            "undo_label": "Refresh Pre-compose",
            "payload": {"composition": parent.to_dict()},
            "validation": report.to_dict(),
        }


__all__ = ["MotionPrecompAdapterMixin"]
