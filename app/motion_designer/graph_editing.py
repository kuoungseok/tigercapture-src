"""Shared Graph Editor property and tangent mutation helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from math import sqrt

from .schema import AnimatedProperty, MotionLayer
from .time_remap import TIME_REMAP_CONTRACT, layer_time_remap
from .temporal_interpolation import TEMPORAL_AUTO_CONTRACT
from .spatial_interpolation import SPATIAL_BEZIER_CONTRACT, auto_spatial_tangents


def layer_graph_property(
    layer: MotionLayer,
    property_name: str,
) -> AnimatedProperty | None:
    name = str(property_name)
    if name == "time_remap":
        return layer_time_remap(layer)
    if name.startswith("source:"):
        value = layer.source.params.get(name.split(":", 1)[1])
        if isinstance(value, Mapping) and (
            "default" in value or "keyframes" in value
        ):
            return AnimatedProperty.from_dict(value)
        return None
    return layer.transform.properties().get(name)


def store_layer_graph_property(
    layer: MotionLayer,
    property_name: str,
    prop: AnimatedProperty,
) -> None:
    name = str(property_name)
    if name == "time_remap":
        layer.metadata["time_remap"] = {
            "contract": TIME_REMAP_CONTRACT,
            "enabled": True,
            "property": prop.to_dict(),
        }
    elif name.startswith("source:"):
        layer.source.params[name.split(":", 1)[1]] = prop.to_dict()


def update_keyframe_tangent(
    layer: MotionLayer,
    property_name: str,
    keyframe_id: str,
    *,
    mode: str = "auto",
    in_tangent: Sequence[float] | None = None,
    out_tangent: Sequence[float] | None = None,
) -> dict[str, Any]:
    prop = layer_graph_property(layer, property_name)
    if prop is None:
        raise ValueError(f"Unknown graph property: {property_name}")
    keyframe = next(
        (row for row in prop.keyframes if row.id == str(keyframe_id)),
        None,
    )
    if keyframe is None:
        raise ValueError(f"Unknown keyframe: {keyframe_id}")
    normalized = str(mode or "standard_auto").lower()
    if normalized == "auto":
        normalized = "tiger_smooth"
    if normalized == "linear":
        keyframe.interpolation = "linear"
        keyframe.in_tangent = (0.667, 1.0)
        keyframe.out_tangent = (0.333, 0.0)
    elif normalized == "hold":
        keyframe.interpolation = "hold"
    else:
        keyframe.interpolation = "bezier"
        if normalized == "tiger_smooth":
            keyframe.in_tangent = (0.667, 1.0)
            keyframe.out_tangent = (0.333, 0.0)
        if in_tangent is not None:
            keyframe.in_tangent = (
                max(0.0, min(1.0, float(in_tangent[0]))),
                float(in_tangent[1]),
            )
        if out_tangent is not None:
            keyframe.out_tangent = (
                max(0.0, min(1.0, float(out_tangent[0]))),
                float(out_tangent[1]),
            )
        if normalized == "continuous":
            if out_tangent is not None:
                keyframe.in_tangent = (
                    1.0 - keyframe.out_tangent[0],
                    1.0 - keyframe.out_tangent[1],
                )
            elif in_tangent is not None:
                keyframe.out_tangent = (
                    1.0 - keyframe.in_tangent[0],
                    1.0 - keyframe.in_tangent[1],
                )
            else:
                keyframe.in_tangent = (
                    1.0 - keyframe.out_tangent[0],
                    1.0 - keyframe.out_tangent[1],
                )
    keyframe.metadata["tangent_mode"] = normalized
    keyframe.metadata["tangent_contract"] = (
        "legacy_tiger_smooth_temporal_bezier_v1"
        if normalized == "tiger_smooth"
        else TEMPORAL_AUTO_CONTRACT
        if normalized == "standard_auto"
        else "temporal_bezier_v1"
    )
    store_layer_graph_property(layer, property_name, prop)
    return keyframe.to_dict()


def set_roving_keyframes(
    layer: MotionLayer,
    property_name: str,
    keyframe_ids: Sequence[str],
    *,
    enabled: bool = True,
) -> list[dict[str, Any]]:
    prop = layer_graph_property(layer, property_name)
    if prop is None:
        raise ValueError(f"Unknown graph property: {property_name}")
    requested = {str(value) for value in keyframe_ids}
    rows = sorted(prop.keyframes, key=lambda row: (row.time_ms, row.id))
    if len(rows) < 3:
        raise ValueError("Roving requires at least three keyframes")
    for index, row in enumerate(rows):
        row.metadata["roving"] = bool(
            enabled
            and row.id in requested
            and index not in {0, len(rows) - 1}
        )

    def distance(left: Any, right: Any) -> float:
        left_values = list(left) if isinstance(left, (list, tuple)) else [left]
        right_values = (
            list(right) if isinstance(right, (list, tuple)) else [right]
        )
        if len(left_values) != len(right_values):
            return 1.0
        return sqrt(sum(
            (float(a) - float(b)) ** 2
            for a, b in zip(left_values, right_values)
        ))

    anchor = 0
    while anchor < len(rows) - 1:
        end = anchor + 1
        while end < len(rows) - 1 and rows[end].metadata.get("roving"):
            end += 1
        if end - anchor > 1:
            segment = rows[anchor:end + 1]
            distances = [
                distance(left.value, right.value)
                for left, right in zip(segment, segment[1:])
            ]
            total = sum(distances)
            elapsed = 0.0
            duration = rows[end].time_ms - rows[anchor].time_ms
            for offset, row in enumerate(segment[1:-1], start=1):
                elapsed += distances[offset - 1]
                ratio = (
                    elapsed / total
                    if total > 1e-9
                    else offset / (len(segment) - 1)
                )
                row.time_ms = round(rows[anchor].time_ms + duration * ratio)
        anchor = end
    prop.keyframes = sorted(rows, key=lambda row: (row.time_ms, row.id))
    store_layer_graph_property(layer, property_name, prop)
    return [row.to_dict() for row in prop.keyframes]


def update_keyframe_spatial_tangent(
    layer: MotionLayer,
    property_name: str,
    keyframe_id: str,
    *,
    mode: str = "auto",
    in_tangent: Sequence[float] | None = None,
    out_tangent: Sequence[float] | None = None,
) -> dict[str, Any]:
    prop = layer_graph_property(layer, property_name)
    if prop is None or prop.value_type not in {"vector2", "vector3"}:
        raise ValueError("Spatial tangents require a vector2 or vector3 property")
    rows = sorted(prop.keyframes, key=lambda row: (row.time_ms, row.id))
    index = next((i for i, row in enumerate(rows) if row.id == str(keyframe_id)), -1)
    if index < 0:
        raise ValueError(f"Unknown keyframe: {keyframe_id}")
    keyframe = rows[index]
    size = len(list(keyframe.value))

    def tangent(value: Sequence[float] | None, fallback: Sequence[float]) -> list[float]:
        source = list(value) if value is not None else list(fallback)
        if len(source) != size:
            raise ValueError(f"Spatial tangent requires {size} components")
        return [float(component) for component in source]

    normalized = str(mode or "auto").lower()
    current_in = tangent(keyframe.metadata.get("spatial_in_tangent"), [0.0] * size)
    current_out = tangent(keyframe.metadata.get("spatial_out_tangent"), [0.0] * size)
    if normalized == "auto":
        current_in, current_out = auto_spatial_tangents(rows, index)
    elif normalized == "linear":
        current_in = current_out = [0.0] * size
    else:
        current_in = tangent(in_tangent, current_in)
        current_out = tangent(out_tangent, current_out)
        if normalized == "continuous":
            if out_tangent is not None:
                current_in = [-value for value in current_out]
            elif in_tangent is not None:
                current_out = [-value for value in current_in]
        elif normalized != "broken":
            raise ValueError(f"Unsupported spatial tangent mode: {mode}")
    keyframe.metadata.update({
        "spatial_tangent_mode": normalized,
        "spatial_in_tangent": current_in,
        "spatial_out_tangent": current_out,
    })
    prop.metadata["spatial_interpolation"] = SPATIAL_BEZIER_CONTRACT
    store_layer_graph_property(layer, property_name, prop)
    return keyframe.to_dict()


__all__ = [
    "layer_graph_property",
    "store_layer_graph_property",
    "set_roving_keyframes",
    "update_keyframe_tangent",
    "update_keyframe_spatial_tangent",
]
