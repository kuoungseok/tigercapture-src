"""Resolve linked vector Boolean operands without UI or Qt dependencies."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .schema import MotionComposition, MotionLayer
from .vector_shapes import (
    VectorPath, VectorPoint, evaluate_source_param, path_from_params,
)


def linked_boolean_operand_ids(layer: MotionLayer, time_ms: float = 0.0) -> list[str]:
    boolean = evaluate_source_param(layer.source.params, "boolean", time_ms, {})
    if not isinstance(boolean, Mapping):
        return []
    output: list[str] = []
    for value in boolean.get("operand_layer_ids", []):
        layer_id = str(value or "")
        if layer_id and layer_id != layer.id and layer_id not in output:
            output.append(layer_id)
    return output


def would_create_boolean_cycle(
    composition: MotionComposition,
    target_layer_id: str,
    operand_layer_id: str,
) -> bool:
    if not target_layer_id or target_layer_id == operand_layer_id:
        return True
    layers = {layer.id: layer for layer in composition.layers}
    pending = [operand_layer_id]
    visited: set[str] = set()
    while pending:
        layer_id = pending.pop()
        if layer_id == target_layer_id:
            return True
        if layer_id in visited:
            continue
        visited.add(layer_id)
        layer = layers.get(layer_id)
        if layer is not None:
            pending.extend(linked_boolean_operand_ids(layer))
    return False


def _map_point(matrix, point: tuple[float, float]) -> tuple[float, float]:
    a, b, c, d, tx, ty = matrix
    return a * point[0] + c * point[1] + tx, b * point[0] + d * point[1] + ty


def _inverse_affine(matrix):
    a, b, c, d, tx, ty = matrix
    determinant = a * d - b * c
    if abs(determinant) <= 1e-10:
        return None
    ia, ib = d / determinant, -b / determinant
    ic, identity = -c / determinant, a / determinant
    return ia, ib, ic, identity, -(ia * tx + ic * ty), -(ib * tx + identity * ty)


def _source_size(layer: MotionLayer, time_ms: float) -> tuple[float, float]:
    params = layer.source.params
    return (
        max(1.0, float(evaluate_source_param(params, "width", time_ms, 400.0))),
        max(1.0, float(evaluate_source_param(params, "height", time_ms, 220.0))),
    )


def _path_in_target_space(path: VectorPath, operand, target, operand_size, target_size) -> VectorPath | None:
    target_inverse = _inverse_affine(target.matrix)
    if target_inverse is None:
        return None
    operand_anchor = (
        float(operand.anchor[0]) * operand_size[0],
        float(operand.anchor[1]) * operand_size[1],
    )
    target_anchor = (
        float(target.anchor[0]) * target_size[0],
        float(target.anchor[1]) * target_size[1],
    )

    def convert(point: tuple[float, float]) -> tuple[float, float]:
        operand_draw = (point[0] - operand_anchor[0], point[1] - operand_anchor[1])
        world = _map_point(operand.matrix, operand_draw)
        target_draw = _map_point(target_inverse, world)
        return target_draw[0] + target_anchor[0], target_draw[1] + target_anchor[1]

    points: list[VectorPoint] = []
    for point in path.points:
        position = convert(point.position)
        incoming = convert((
            point.position[0] + point.in_tangent[0],
            point.position[1] + point.in_tangent[1],
        ))
        outgoing = convert((
            point.position[0] + point.out_tangent[0],
            point.position[1] + point.out_tangent[1],
        ))
        points.append(VectorPoint(
            position=position,
            in_tangent=(incoming[0] - position[0], incoming[1] - position[1]),
            out_tangent=(outgoing[0] - position[0], outgoing[1] - position[1]),
        ))
    return VectorPath(points=points, closed=path.closed, fill_rule=path.fill_rule)


def resolve_boolean_layer(
    composition: MotionComposition,
    layer: MotionLayer,
    states: Mapping[str, Any],
) -> MotionLayer:
    target = states.get(layer.id)
    if target is None:
        return layer
    boolean = evaluate_source_param(layer.source.params, "boolean", target.local_time_ms, {})
    if not isinstance(boolean, Mapping):
        return layer
    operand_ids = linked_boolean_operand_ids(layer, target.local_time_ms)
    if not operand_ids:
        return layer
    layers = {item.id: item for item in composition.layers}
    target_size = _source_size(layer, target.local_time_ms)
    paths = [dict(row) for row in boolean.get("paths", []) if isinstance(row, Mapping)]
    resolved_ids: list[str] = []
    for operand_id in operand_ids:
        operand_layer = layers.get(operand_id)
        operand_state = states.get(operand_id)
        if (
            operand_layer is None
            or operand_layer.layer_type != "shape"
            or operand_state is None
            or not operand_state.active
        ):
            continue
        path = path_from_params(operand_layer.source.params, operand_state.local_time_ms)
        if not path.closed:
            continue
        transformed = _path_in_target_space(
            path,
            operand_state,
            target,
            _source_size(operand_layer, operand_state.local_time_ms),
            target_size,
        )
        if transformed is not None:
            paths.append(transformed.to_dict())
            resolved_ids.append(operand_id)
    if not resolved_ids:
        return layer
    resolved = MotionLayer.from_dict(layer.to_dict())
    resolved_boolean = dict(boolean)
    resolved_boolean["paths"] = paths
    resolved_boolean["resolved_operand_layer_ids"] = resolved_ids
    resolved.source.params["boolean"] = resolved_boolean
    return resolved


def consumed_boolean_operand_ids(
    composition: MotionComposition,
    states: Mapping[str, Any],
) -> set[str]:
    consumed: set[str] = set()
    for layer in composition.layers:
        state = states.get(layer.id)
        if state is None or not state.active:
            continue
        boolean = evaluate_source_param(layer.source.params, "boolean", state.local_time_ms, {})
        if not isinstance(boolean, Mapping) or not bool(boolean.get("hide_operands", True)):
            continue
        consumed.update(linked_boolean_operand_ids(layer, state.local_time_ms))
    return consumed
