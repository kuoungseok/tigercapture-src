"""Nested composition contract and deterministic pre-compose operations."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .schema import (
    AnimatedProperty,
    MotionComposition,
    MotionLayer,
    MotionTransform,
    SourceRef,
    animated,
    new_motion_id,
)
from .keyframes import evaluate_property

PRECOMP_LAYER_TYPE = "precomp"
PRECOMP_SOURCE_KIND = "motion_composition"
PRECOMP_CONTRACT = "tigerstudio.motion.precomp.v1"


def embedded_composition(layer: MotionLayer) -> MotionComposition | None:
    if (
        layer.layer_type != PRECOMP_LAYER_TYPE
        or layer.source.kind != PRECOMP_SOURCE_KIND
    ):
        return None
    value = layer.source.params.get("composition")
    return MotionComposition.from_dict(value) if isinstance(value, Mapping) else None


def set_embedded_composition(
    layer: MotionLayer,
    composition: MotionComposition,
) -> None:
    layer.layer_type = PRECOMP_LAYER_TYPE
    layer.source.kind = PRECOMP_SOURCE_KIND
    layer.source.uri = composition.id
    layer.source.params["contract"] = PRECOMP_CONTRACT
    layer.source.params["composition"] = composition.to_dict()


def create_precomposition(
    parent: MotionComposition,
    layer_ids: Sequence[str],
    *,
    name: str = "Pre-compose",
) -> tuple[MotionComposition, MotionLayer]:
    requested = [str(value) for value in layer_ids]
    if not requested or len(requested) != len(set(requested)):
        raise ValueError("Pre-compose requires unique selected layer ids")
    selected = [layer for layer in parent.layers if layer.id in requested]
    if len(selected) != len(requested):
        missing = sorted(set(requested) - {layer.id for layer in selected})
        raise ValueError(f"Unknown pre-compose layers: {', '.join(missing)}")
    selected_ids = {layer.id for layer in selected}
    insert_at = min(parent.layers.index(layer) for layer in selected)
    child_layers = [
        MotionLayer.from_dict(layer.to_dict())
        for layer in selected
    ]
    for layer in child_layers:
        if layer.parent_id not in selected_ids:
            layer.parent_id = ""
        matte_id = str(layer.metadata.get("matte_layer_id") or "")
        if matte_id and matte_id not in selected_ids:
            layer.metadata.pop("matte_layer_id", None)
            layer.metadata.pop("matte_mode", None)
            layer.metadata.pop("matte_inverted", None)
    child = MotionComposition(
        id=new_motion_id("composition"),
        name=str(name or "Pre-compose"),
        width=parent.width,
        height=parent.height,
        fps=parent.fps,
        duration_ms=parent.duration_ms,
        layers=child_layers,
        metadata={
            "document_contract": PRECOMP_CONTRACT,
            "parent_composition_id": parent.id,
        },
    )
    precomp_layer = MotionLayer(
        id=new_motion_id("layer"),
        name=child.name,
        layer_type=PRECOMP_LAYER_TYPE,
        source=SourceRef(
            kind=PRECOMP_SOURCE_KIND,
            uri=child.id,
            params={
                "contract": PRECOMP_CONTRACT,
                "composition": child.to_dict(),
                "overrides": {},
            },
        ),
        transform=MotionTransform(
            position=animated([0.0, 0.0], "vector2"),
            anchor=animated([0.0, 0.0], "vector2"),
        ),
        in_ms=min(layer.in_ms for layer in selected),
        out_ms=max(layer.out_ms for layer in selected),
    )
    parent.layers = [
        layer for layer in parent.layers
        if layer.id not in selected_ids
    ]
    parent.layers.insert(insert_at, precomp_layer)
    parent.revision += 1
    return child, precomp_layer


def apply_precomp_overrides(
    layer: MotionLayer,
    composition: MotionComposition,
    time_ms: float = 0.0,
) -> MotionComposition:
    candidate = MotionComposition.from_dict(composition.to_dict())
    published_values = layer.source.params.get("published_values")
    published_values = (
        published_values if isinstance(published_values, Mapping) else {}
    )
    publications = candidate.metadata.get("published_properties")
    publications = publications if isinstance(publications, list) else []
    from .graph_editing import layer_graph_property, store_layer_graph_property

    for publication in publications:
        if not isinstance(publication, Mapping):
            continue
        publication_id = str(publication.get("id") or "")
        value_data = published_values.get(publication_id)
        if not isinstance(value_data, Mapping):
            continue
        child_layer = next(
            (
                row for row in candidate.layers
                if row.id == str(publication.get("layer_id") or "")
            ),
            None,
        )
        if child_layer is None:
            continue
        property_name = str(publication.get("property_name") or "")
        target = layer_graph_property(child_layer, property_name)
        if target is None:
            continue
        instance_property = AnimatedProperty.from_dict(
            value_data,
            value_type=target.value_type,
        )
        target.default = evaluate_property(instance_property, time_ms)
        target.keyframes = []
        store_layer_graph_property(child_layer, property_name, target)
    overrides = layer.source.params.get("overrides")
    if not isinstance(overrides, Mapping):
        return candidate
    for child_layer in candidate.layers:
        changes = overrides.get(child_layer.id)
        if not isinstance(changes, Mapping):
            continue
        data = child_layer.to_dict()
        for key, value in changes.items():
            if key == "transform" and isinstance(value, Mapping):
                transform = deepcopy(data.get("transform") or {})
                transform.update(deepcopy(dict(value)))
                data["transform"] = transform
            elif key in {
                "visible", "blend_mode", "in_ms", "out_ms", "time_scale",
                "reverse", "source", "metadata",
            }:
                data[key] = deepcopy(value)
        candidate.layers[candidate.layers.index(child_layer)] = (
            MotionLayer.from_dict(data)
        )
    return candidate


def publish_precomp_property(
    composition: MotionComposition,
    layer_id: str,
    property_name: str,
    *,
    name: str = "",
) -> dict[str, Any]:
    from .graph_editing import layer_graph_property

    layer = next(
        (row for row in composition.layers if row.id == str(layer_id)),
        None,
    )
    if layer is None:
        raise ValueError(f"Unknown layer: {layer_id}")
    prop = layer_graph_property(layer, property_name)
    if prop is None:
        raise ValueError(f"Unknown publishable property: {property_name}")
    rows = composition.metadata.get("published_properties")
    rows = [dict(row) for row in rows] if isinstance(rows, list) else []
    existing = next(
        (
            row for row in rows
            if row.get("layer_id") == layer.id
            and row.get("property_name") == str(property_name)
        ),
        None,
    )
    publication = existing or {
        "id": new_motion_id("published"),
        "layer_id": layer.id,
        "property_name": str(property_name),
    }
    publication.update({
        "name": str(name or f"{layer.name} {property_name.title()}"),
        "value_type": prop.value_type,
        "default": prop.default,
    })
    if existing is None:
        rows.append(publication)
    composition.metadata["published_properties"] = rows
    composition.revision += 1
    return publication


def set_precomp_published_value(
    layer: MotionLayer,
    publication_id: str,
    value: Any,
) -> AnimatedProperty:
    child = embedded_composition(layer)
    if child is None:
        raise ValueError("Layer is not a pre-composition")
    rows = child.metadata.get("published_properties")
    publication = next(
        (
            row for row in rows
            if isinstance(row, Mapping)
            and str(row.get("id") or "") == str(publication_id)
        ),
        None,
    ) if isinstance(rows, list) else None
    if publication is None:
        raise ValueError(f"Unknown published property: {publication_id}")
    prop = (
        AnimatedProperty.from_dict(value, value_type=str(
            publication.get("value_type") or "scalar",
        ))
        if isinstance(value, Mapping)
        else AnimatedProperty(
            value_type=str(publication.get("value_type") or "scalar"),
            default=value,
        )
    )
    values = layer.source.params.get("published_values")
    values = deepcopy(dict(values)) if isinstance(values, Mapping) else {}
    values[str(publication_id)] = prop.to_dict()
    layer.source.params["published_values"] = values
    return prop


def set_precomp_override(
    layer: MotionLayer,
    child_layer_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    child = embedded_composition(layer)
    if child is None:
        raise ValueError("Layer is not a pre-composition")
    if not any(row.id == str(child_layer_id) for row in child.layers):
        raise ValueError(f"Unknown nested layer: {child_layer_id}")
    overrides = layer.source.params.get("overrides")
    overrides = deepcopy(dict(overrides)) if isinstance(overrides, Mapping) else {}
    current = overrides.get(str(child_layer_id))
    current = deepcopy(dict(current)) if isinstance(current, Mapping) else {}
    current.update(deepcopy(dict(changes)))
    overrides[str(child_layer_id)] = current
    layer.source.params["overrides"] = overrides
    return current


__all__ = [
    "PRECOMP_CONTRACT",
    "PRECOMP_LAYER_TYPE",
    "PRECOMP_SOURCE_KIND",
    "apply_precomp_overrides",
    "create_precomposition",
    "embedded_composition",
    "publish_precomp_property",
    "set_embedded_composition",
    "set_precomp_override",
    "set_precomp_published_value",
]
