"""Qt-free deterministic MotionComposition evaluator."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .audio_reactive import evaluate_layer_transform
from .advanced_motion import project_layer_matrix
from .constraints import apply_look_at, point_on_path
from .schema import MotionComposition, MotionLayer


@dataclass(slots=True)
class EvaluatedLayer:
    id: str
    name: str
    active: bool
    local_time_ms: float
    position: list[float]
    scale: list[float]
    rotation: float
    opacity: float
    anchor: list[float]
    matrix: tuple[float, float, float, float, float, float]
    source: dict[str, Any]
    blend_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "active": self.active, "local_time_ms": self.local_time_ms,
                "position": self.position, "scale": self.scale, "rotation": self.rotation, "opacity": self.opacity,
                "anchor": self.anchor, "matrix": list(self.matrix), "source": self.source, "blend_mode": self.blend_mode}


def remap_layer_time(layer: MotionLayer, composition_time_ms: float) -> float:
    duration = max(1.0, float(layer.out_ms - layer.in_ms))
    elapsed = (float(composition_time_ms) - layer.in_ms) * layer.time_scale
    mode = str(layer.metadata.get("time_mode", "clamp"))
    if mode == "loop":
        elapsed %= duration
    elif mode == "ping_pong":
        cycle = elapsed % (duration * 2.0)
        elapsed = duration - abs(duration - cycle)
    else:
        elapsed = max(0.0, min(duration, elapsed))
    if layer.reverse:
        elapsed = duration - elapsed
    return float(layer.source_in_ms) + elapsed


def _local_matrix(values: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    sx, sy = float(values["scale"][0]), float(values["scale"][1])
    angle = math.radians(float(values["rotation"]))
    cosine, sine = math.cos(angle), math.sin(angle)
    x, y = float(values["position"][0]), float(values["position"][1])
    return cosine * sx, sine * sx, -sine * sy, cosine * sy, x, y


def multiply_affine(parent, child):
    pa, pb, pc, pd, ptx, pty = parent
    ca, cb, cc, cd, ctx, cty = child
    return (pa * ca + pc * cb, pb * ca + pd * cb, pa * cc + pc * cd, pb * cc + pd * cd,
            pa * ctx + pc * cty + ptx, pb * ctx + pd * cty + pty)


def evaluate_composition(composition: MotionComposition, time_ms: float) -> list[EvaluatedLayer]:
    solo_ids = {layer.id for layer in composition.layers if layer.solo}
    values_by_id: dict[str, dict[str, Any]] = {}
    layers_by_id = {layer.id: layer for layer in composition.layers}
    for layer in composition.layers:
        values = evaluate_layer_transform(layer, time_ms)
        values_by_id[layer.id] = values
    from .expressions import apply_composition_expressions

    apply_composition_expressions(composition, time_ms, values_by_id)
    for layer in composition.layers:
        constraint = layer.metadata.get("constraint")
        if isinstance(constraint, dict):
            target = values_by_id.get(str(constraint.get("target_id") or ""))
            if constraint.get("kind") == "look_at" and target:
                apply_look_at(values_by_id[layer.id], target, offset_degrees=float(constraint.get("offset", 0.0)))
            elif constraint.get("kind") == "follow_path":
                values_by_id[layer.id]["position"] = point_on_path(list(constraint.get("points") or []), float(constraint.get("progress", 0.0)))

    matrix_cache: dict[str, tuple[float, float, float, float, float, float]] = {}
    def world_matrix(layer: MotionLayer, stack: set[str] | None = None):
        if layer.id in matrix_cache:
            return matrix_cache[layer.id]
        stack = set(stack or ())
        if layer.id in stack:
            return _local_matrix(values_by_id[layer.id])
        stack.add(layer.id)
        local = _local_matrix(values_by_id[layer.id])
        parent = layers_by_id.get(layer.parent_id)
        matrix_cache[layer.id] = multiply_affine(world_matrix(parent, stack), local) if parent else local
        return matrix_cache[layer.id]

    evaluated: list[EvaluatedLayer] = []
    for layer in composition.layers:
        values = values_by_id[layer.id]
        active = layer.visible and layer.in_ms <= time_ms < layer.out_ms and (not solo_ids or layer.id in solo_ids)
        evaluated.append(EvaluatedLayer(
            id=layer.id, name=layer.name, active=active, local_time_ms=remap_layer_time(layer, time_ms),
            position=list(values["position"]), scale=list(values["scale"]), rotation=float(values["rotation"]),
            opacity=max(0.0, min(1.0, float(values["opacity"]))), anchor=list(values["anchor"]),
            matrix=project_layer_matrix(
                world_matrix(layer),
                composition=composition,
                layer=layer,
                time_ms=time_ms,
            ),
            source=layer.source.to_dict(), blend_mode=layer.blend_mode,
        ))
    return evaluated
