"""Shared Graph Editor property and tangent mutation helpers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any
from math import sqrt

from .schema import AnimatedProperty, MotionLayer
from .time_remap import TIME_REMAP_CONTRACT, layer_time_remap


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
    normalized = str(mode or "auto").lower()
    if normalized == "linear":
        keyframe.interpolation = "linear"
        keyframe.in_tangent = (0.667, 1.0)
        keyframe.out_tangent = (0.333, 0.0)
    elif normalized == "hold":
        keyframe.interpolation = "hold"
    else:
        keyframe.interpolation = "bezier"
        if normalized == "auto":
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
    keyframe.metadata["tangent_mode"] = normalized
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


__all__ = [
    "layer_graph_property",
    "store_layer_graph_property",
    "set_roving_keyframes",
    "update_keyframe_tangent",
]
