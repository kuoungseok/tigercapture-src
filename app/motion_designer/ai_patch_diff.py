"""Human-reviewable before/after summaries for Motion AI patches."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .ai_generation import validate_motion_ai_patch
from .schema import AnimatedProperty, MotionComposition


MOTION_AI_PATCH_DIFF_SCHEMA = "tigerstudio.motion.ai.patch_diff.v1"


def _source_default(value: Any) -> Any:
    if isinstance(value, Mapping) and (
        "default" in value or "keyframes" in value
    ):
        return AnimatedProperty.from_dict(value).default
    return value


def build_motion_ai_patch_diff(
    composition: MotionComposition,
    patch: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = validate_motion_ai_patch(patch, composition=composition)
    layers = {item.id: item for item in composition.layers}
    rows: list[dict[str, Any]] = []
    affected_ids: set[str] = set()
    interval_start = composition.duration_ms
    interval_end = 0
    for operation in normalized["operations"]:
        layer = layers[operation["layer_id"]]
        params = operation["params"]
        op_type = operation["type"]
        if op_type == "set_text":
            property_name = "Text"
            before = layer.source.params.get("text", "")
            after = params["text"]
        elif op_type == "set_timing":
            property_name = "Timing"
            before = [layer.in_ms, layer.out_ms]
            after = [int(params["in_ms"]), int(params["out_ms"])]
        elif op_type == "set_transform":
            property_name = str(params["property"]).replace("_", " ").title()
            before = getattr(layer.transform, str(params["property"])).default
            after = params["value"]
        elif op_type == "set_source_param":
            parameter = str(params["parameter"])
            property_name = parameter.replace("_", " ").title()
            before = _source_default(layer.source.params.get(parameter))
            after = params["value"]
        elif op_type == "set_behavior":
            property_name = "Behavior"
            before = [item.to_dict() for item in layer.behaviors]
            after = [params["behavior"]]
        else:
            property_name = "Visibility"
            before = bool(layer.visible)
            after = bool(params["visible"])
        affected_ids.add(layer.id)
        interval_start = min(interval_start, layer.in_ms)
        interval_end = max(interval_end, layer.out_ms)
        rows.append({
            "operation_id": operation["id"],
            "operation": op_type,
            "layer_id": layer.id,
            "layer_name": layer.name,
            "property": property_name,
            "before": before,
            "after": after,
            "reason": operation["reason"],
        })
    if not rows:
        interval_start = 0
        interval_end = 0
    return {
        "schema": MOTION_AI_PATCH_DIFF_SCHEMA,
        "composition_id": composition.id,
        "base_revision": composition.revision,
        "patch_id": normalized["id"],
        "summary": normalized["summary"],
        "operation_count": len(rows),
        "affected_layer_count": len(affected_ids),
        "affected_layer_ids": sorted(affected_ids),
        "affected_range_ms": [interval_start, interval_end],
        "preview_from_ms": max(0, interval_start - 500),
        "rows": rows,
        "warnings": list(normalized["warnings"]),
    }


__all__ = ["MOTION_AI_PATCH_DIFF_SCHEMA", "build_motion_ai_patch_diff"]
