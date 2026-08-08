"""Adjustment-layer scope contract shared by UI, render, and automation."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schema import MotionComposition, MotionLayer


ADJUSTMENT_SCOPE_KEY = "adjustment_scope"
ADJUSTMENT_SCOPE_ALL_BELOW = "all_below"
ADJUSTMENT_SCOPE_SELECTED_BELOW = "selected_layers_below"
ADJUSTMENT_SCOPE_MODES = {
    ADJUSTMENT_SCOPE_ALL_BELOW,
    ADJUSTMENT_SCOPE_SELECTED_BELOW,
}
NON_RENDERING_LAYER_TYPES = {"group", "null", "camera", "light", "adjustment"}


def adjustment_scope(layer: MotionLayer) -> dict[str, Any]:
    raw = layer.metadata.get(ADJUSTMENT_SCOPE_KEY)
    raw = raw if isinstance(raw, dict) else {}
    mode = str(raw.get("mode") or ADJUSTMENT_SCOPE_ALL_BELOW)
    if mode not in ADJUSTMENT_SCOPE_MODES:
        mode = ADJUSTMENT_SCOPE_ALL_BELOW
    layer_ids = list(dict.fromkeys(
        str(item) for item in raw.get("layer_ids", []) if str(item)
    ))
    return {"mode": mode, "layer_ids": layer_ids}


def eligible_adjustment_target_ids(
    composition: MotionComposition,
    adjustment_layer_id: str,
) -> list[str]:
    result: list[str] = []
    for layer in composition.layers:
        if layer.id == adjustment_layer_id:
            break
        if layer.layer_type not in NON_RENDERING_LAYER_TYPES:
            result.append(layer.id)
    return result


def normalize_adjustment_scope(
    composition: MotionComposition,
    layer: MotionLayer,
    *,
    mode: str,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    if layer.layer_type != "adjustment":
        raise ValueError("Adjustment scope requires an adjustment layer")
    normalized_mode = str(mode or ADJUSTMENT_SCOPE_ALL_BELOW)
    if normalized_mode not in ADJUSTMENT_SCOPE_MODES:
        raise ValueError(f"Unsupported adjustment scope mode: {normalized_mode}")
    eligible = set(eligible_adjustment_target_ids(composition, layer.id))
    normalized_ids = [
        item for item in dict.fromkeys(str(value) for value in layer_ids)
        if item in eligible
    ]
    return {"mode": normalized_mode, "layer_ids": normalized_ids}


def set_adjustment_scope(
    composition: MotionComposition,
    layer: MotionLayer,
    *,
    mode: str,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    value = normalize_adjustment_scope(
        composition,
        layer,
        mode=mode,
        layer_ids=layer_ids,
    )
    layer.metadata[ADJUSTMENT_SCOPE_KEY] = value
    return value


__all__ = [
    "ADJUSTMENT_SCOPE_ALL_BELOW",
    "ADJUSTMENT_SCOPE_KEY",
    "ADJUSTMENT_SCOPE_MODES",
    "ADJUSTMENT_SCOPE_SELECTED_BELOW",
    "adjustment_scope",
    "eligible_adjustment_target_ids",
    "normalize_adjustment_scope",
    "set_adjustment_scope",
]
