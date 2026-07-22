"""Serializable command helpers for animation mutations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .schema import Keyframe, MotionBehaviorRef, MotionComposition


def find_layer(composition: MotionComposition, layer_id: str):
    layer = next((item for item in composition.layers if item.id == layer_id), None)
    if layer is None:
        raise ValueError(f"Unknown layer: {layer_id}")
    return layer


def set_keyframe(composition: MotionComposition, layer_id: str, property_name: str, keyframe: Keyframe) -> None:
    layer = find_layer(composition, layer_id)
    prop = layer.transform.properties().get(property_name)
    if prop is None:
        raise ValueError(f"Unknown animated property: {property_name}")
    prop.keyframes = [item for item in prop.keyframes if item.id != keyframe.id and item.time_ms != keyframe.time_ms]
    prop.keyframes.append(keyframe)
    prop.keyframes.sort(key=lambda item: (item.time_ms, item.id))
    composition.revision += 1


def delete_keyframe(composition: MotionComposition, layer_id: str, property_name: str, keyframe_id: str) -> None:
    layer = find_layer(composition, layer_id)
    prop = layer.transform.properties().get(property_name)
    if prop is None:
        raise ValueError(f"Unknown animated property: {property_name}")
    before = len(prop.keyframes)
    prop.keyframes = [item for item in prop.keyframes if item.id != keyframe_id]
    if len(prop.keyframes) == before:
        raise ValueError(f"Unknown keyframe: {keyframe_id}")
    composition.revision += 1


def add_behavior(composition: MotionComposition, layer_id: str, behavior: MotionBehaviorRef) -> None:
    find_layer(composition, layer_id).behaviors.append(behavior)
    composition.revision += 1
