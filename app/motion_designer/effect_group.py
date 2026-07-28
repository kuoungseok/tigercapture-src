"""Scoped effect-stack contract for non-rendering group layers."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .schema import MotionComposition, MotionLayer


EFFECT_GROUP_KEY = "effect_group"
EFFECT_GROUP_DESCENDANTS = "descendants"
EFFECT_GROUP_SELECTED = "selected_descendants"
EFFECT_GROUP_MODES = {EFFECT_GROUP_DESCENDANTS, EFFECT_GROUP_SELECTED}


def descendant_layer_ids(
    composition: MotionComposition,
    group_layer_id: str,
    *,
    renderable_only: bool = True,
) -> list[str]:
    by_parent: dict[str, list[MotionLayer]] = {}
    for layer in composition.layers:
        by_parent.setdefault(layer.parent_id, []).append(layer)
    result: list[str] = []
    pending = list(by_parent.get(group_layer_id, ()))
    while pending:
        layer = pending.pop(0)
        if not renderable_only or layer.layer_type not in {
            "group", "null", "camera", "light", "adjustment",
        }:
            result.append(layer.id)
        pending[0:0] = by_parent.get(layer.id, ())
    return result


def effect_group_scope(layer: MotionLayer) -> dict[str, Any]:
    raw = layer.metadata.get(EFFECT_GROUP_KEY)
    raw = raw if isinstance(raw, dict) else {}
    mode = str(raw.get("mode") or EFFECT_GROUP_DESCENDANTS)
    if mode not in EFFECT_GROUP_MODES:
        mode = EFFECT_GROUP_DESCENDANTS
    return {
        "enabled": bool(raw.get("enabled", True)),
        "mode": mode,
        "layer_ids": list(dict.fromkeys(
            str(item) for item in raw.get("layer_ids", ()) if str(item)
        )),
    }


def set_effect_group_scope(
    composition: MotionComposition,
    layer: MotionLayer,
    *,
    enabled: bool = True,
    mode: str = EFFECT_GROUP_DESCENDANTS,
    layer_ids: Iterable[str] = (),
) -> dict[str, Any]:
    if layer.layer_type != "group":
        raise ValueError("Effect-group scope requires a group layer")
    normalized_mode = str(mode or EFFECT_GROUP_DESCENDANTS)
    if normalized_mode not in EFFECT_GROUP_MODES:
        raise ValueError(f"Unsupported effect-group scope mode: {normalized_mode}")
    eligible_order = descendant_layer_ids(composition, layer.id)
    eligible = set(eligible_order)
    selected = [
        value
        for value in dict.fromkeys(str(item) for item in layer_ids)
        if value in eligible
    ]
    value = {
        "enabled": bool(enabled),
        "mode": normalized_mode,
        "layer_ids": selected,
    }
    layer.metadata[EFFECT_GROUP_KEY] = value
    return value


def resolved_effect_group_target_ids(
    composition: MotionComposition,
    layer: MotionLayer,
) -> list[str]:
    value = effect_group_scope(layer)
    if not value["enabled"]:
        return []
    eligible = descendant_layer_ids(composition, layer.id)
    if value["mode"] == EFFECT_GROUP_SELECTED:
        selected = set(value["layer_ids"])
        return [layer_id for layer_id in eligible if layer_id in selected]
    return eligible


__all__ = [
    "EFFECT_GROUP_DESCENDANTS",
    "EFFECT_GROUP_KEY",
    "EFFECT_GROUP_MODES",
    "EFFECT_GROUP_SELECTED",
    "descendant_layer_ids",
    "effect_group_scope",
    "resolved_effect_group_target_ids",
    "set_effect_group_scope",
]
