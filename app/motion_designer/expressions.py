"""Deterministic, data-only expressions for Motion Designer transforms.

Expressions are JSON-compatible operation trees.  They deliberately do not
accept source code, Python callables, or JavaScript strings.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, MutableMapping, Sequence

from .schema import Keyframe, MotionComposition, MotionLayer


EXPRESSION_KEY = "expressions"
EXPRESSION_PROPERTIES = ("position", "scale", "rotation", "opacity", "anchor")
SUPPORTED_OPERATIONS = {
    "value", "base", "time", "index", "property", "audio", "beat",
    "add", "subtract", "multiply", "divide", "clamp", "remap",
    "sin", "cos", "negate", "component", "vector",
}
MAX_EXPRESSION_DEPTH = 32
MAX_EXPRESSION_NODES = 512


class MotionExpressionError(ValueError):
    pass


class MotionExpressionCycleError(MotionExpressionError):
    pass


@dataclass(slots=True, frozen=True)
class ExpressionIssue:
    code: str
    message: str
    layer_id: str = ""
    property_name: str = ""


def layer_expressions(layer: MotionLayer) -> dict[str, Any]:
    rows = layer.metadata.get(EXPRESSION_KEY, {})
    return dict(rows) if isinstance(rows, Mapping) else {}


def set_layer_expression(layer: MotionLayer, property_name: str, expression: Any) -> None:
    name = str(property_name or "").strip().lower()
    if name not in EXPRESSION_PROPERTIES:
        raise MotionExpressionError(f"unsupported expression property: {name}")
    validate_expression_tree(expression)
    rows = layer_expressions(layer)
    rows[name] = expression
    layer.metadata[EXPRESSION_KEY] = rows


def clear_layer_expression(layer: MotionLayer, property_name: str = "") -> int:
    rows = layer_expressions(layer)
    if not rows:
        return 0
    name = str(property_name or "").strip().lower()
    if name:
        removed = int(name in rows)
        rows.pop(name, None)
    else:
        removed = len(rows)
        rows.clear()
    if rows:
        layer.metadata[EXPRESSION_KEY] = rows
    else:
        layer.metadata.pop(EXPRESSION_KEY, None)
    return removed


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _number(value: Any, label: str = "value") -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise MotionExpressionError(f"{label} must be a finite number")
    return float(value)


def _numeric_value(value: Any, label: str = "value") -> float | list[float]:
    if _is_sequence(value):
        return [_number(item, label) for item in value]
    return _number(value, label)


def _broadcast_binary(left: Any, right: Any, operation, label: str) -> float | list[float]:
    left_value = _numeric_value(left, label)
    right_value = _numeric_value(right, label)
    if isinstance(left_value, list) or isinstance(right_value, list):
        left_items = left_value if isinstance(left_value, list) else [left_value]
        right_items = right_value if isinstance(right_value, list) else [right_value]
        size = max(len(left_items), len(right_items))
        if len(left_items) not in {1, size} or len(right_items) not in {1, size}:
            raise MotionExpressionError(f"{label} vector sizes are incompatible")
        return [operation(left_items[index % len(left_items)], right_items[index % len(right_items)])
                for index in range(size)]
    return operation(left_value, right_value)


def _walk_expression(expression: Any, *, depth: int = 0, counter: list[int] | None = None):
    if depth > MAX_EXPRESSION_DEPTH:
        raise MotionExpressionError(f"expression exceeds maximum depth {MAX_EXPRESSION_DEPTH}")
    counter = counter if counter is not None else [0]
    counter[0] += 1
    if counter[0] > MAX_EXPRESSION_NODES:
        raise MotionExpressionError(f"expression exceeds maximum node count {MAX_EXPRESSION_NODES}")
    if isinstance(expression, Mapping):
        operation = str(expression.get("op") or "").strip().lower()
        if operation not in SUPPORTED_OPERATIONS:
            raise MotionExpressionError(f"unsupported expression operation: {operation or '<missing>'}")
        yield expression
        for key, value in expression.items():
            if key == "op":
                continue
            if isinstance(value, Mapping):
                yield from _walk_expression(value, depth=depth + 1, counter=counter)
            elif _is_sequence(value):
                for item in value:
                    if isinstance(item, Mapping):
                        yield from _walk_expression(item, depth=depth + 1, counter=counter)
    elif _is_sequence(expression):
        for item in expression:
            if isinstance(item, (Mapping, list, tuple)):
                yield from _walk_expression(item, depth=depth + 1, counter=counter)
            else:
                _number(item)
    else:
        _number(expression)


def validate_expression_tree(expression: Any) -> None:
    nodes = list(_walk_expression(expression))
    for node in nodes:
        operation = str(node.get("op") or "").lower()
        if operation == "property":
            name = str(node.get("property") or "").strip().lower()
            if name not in EXPRESSION_PROPERTIES:
                raise MotionExpressionError(f"unsupported property reference: {name}")
        elif operation in {"add", "subtract", "multiply", "divide"}:
            if "left" not in node or "right" not in node:
                raise MotionExpressionError(f"{operation} requires left and right")
        elif operation == "clamp" and "value" not in node:
            raise MotionExpressionError("clamp requires value")
        elif operation == "remap":
            required = {"value", "in_min", "in_max", "out_min", "out_max"}
            if not required.issubset(node):
                raise MotionExpressionError("remap requires value, in_min, in_max, out_min, and out_max")
        elif operation in {"sin", "cos", "negate", "component"} and "value" not in node:
            raise MotionExpressionError(f"{operation} requires value")
        elif operation == "vector" and not isinstance(node.get("items"), list):
            raise MotionExpressionError("vector requires an items array")


def _expression_dependencies(expression: Any, current_layer_id: str) -> set[tuple[str, str]]:
    dependencies: set[tuple[str, str]] = set()
    for node in _walk_expression(expression):
        if str(node.get("op") or "").lower() != "property" or bool(node.get("base", False)):
            continue
        layer_id = str(node.get("layer_id") or current_layer_id)
        dependencies.add((layer_id, str(node.get("property") or "").lower()))
    return dependencies


def expression_issues(composition: MotionComposition) -> list[ExpressionIssue]:
    layer_ids = {layer.id for layer in composition.layers}
    expressions: dict[tuple[str, str], Any] = {}
    issues: list[ExpressionIssue] = []
    for layer in composition.layers:
        for property_name, expression in layer_expressions(layer).items():
            name = str(property_name).lower()
            if name not in EXPRESSION_PROPERTIES:
                issues.append(ExpressionIssue("invalid_expression_property", f"Unsupported expression property: {name}", layer.id, name))
                continue
            try:
                validate_expression_tree(expression)
            except MotionExpressionError as exc:
                issues.append(ExpressionIssue("invalid_expression", str(exc), layer.id, name))
                continue
            expressions[(layer.id, name)] = expression
            for dependency_layer, dependency_name in _expression_dependencies(expression, layer.id):
                if dependency_layer not in layer_ids:
                    issues.append(ExpressionIssue("missing_expression_layer", f"Unknown expression layer: {dependency_layer}", layer.id, name))
                elif dependency_name not in EXPRESSION_PROPERTIES:
                    issues.append(ExpressionIssue("invalid_expression_property", f"Unsupported expression property: {dependency_name}", layer.id, name))

    visiting: list[tuple[str, str]] = []
    visited: set[tuple[str, str]] = set()
    cycle_nodes: set[tuple[str, str]] = set()

    def visit(node: tuple[str, str]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle_nodes.update(visiting[visiting.index(node):])
            cycle_nodes.add(node)
            return
        visiting.append(node)
        for dependency in _expression_dependencies(expressions[node], node[0]):
            if dependency in expressions:
                visit(dependency)
        visiting.pop()
        visited.add(node)

    for node in expressions:
        visit(node)
    for layer_id, property_name in sorted(cycle_nodes):
        issues.append(ExpressionIssue(
            "expression_cycle", f"Expression dependency cycle includes {layer_id}.{property_name}",
            layer_id, property_name,
        ))
    return issues


@dataclass(slots=True)
class _ExpressionContext:
    composition: MotionComposition
    time_ms: float
    base_values: Mapping[str, Mapping[str, Any]]
    resolved_values: MutableMapping[str, MutableMapping[str, Any]]
    expressions: Mapping[tuple[str, str], Any]
    layer_indexes: Mapping[str, int]
    resolving: list[tuple[str, str]]


def _audio_value(context: _ExpressionContext, node: Mapping[str, Any], current_layer_id: str, *, beat: bool) -> float:
    from .audio_reactive import binding_value_at, layer_bindings

    layer_id = str(node.get("layer_id") or current_layer_id)
    layer = next((item for item in context.composition.layers if item.id == layer_id), None)
    if layer is None:
        raise MotionExpressionError(f"unknown audio expression layer: {layer_id}")
    binding_id = str(node.get("binding_id") or "")
    channel = str(node.get("channel") or ("beat" if beat else "amplitude")).lower()
    binding = next((item for item in layer_bindings(layer)
                    if (binding_id and item.id == binding_id) or (not binding_id and item.channel == channel)), None)
    if binding is None:
        return 0.0
    value = float(binding_value_at(binding, context.time_ms))
    threshold = float(node.get("threshold", 0.5))
    return 1.0 if beat and value >= threshold else value


def _evaluate_node(expression: Any, context: _ExpressionContext, current: tuple[str, str]) -> Any:
    if not isinstance(expression, Mapping):
        return _numeric_value(expression)
    operation = str(expression.get("op") or "").lower()
    if operation == "value":
        return _numeric_value(expression.get("value", 0.0))
    if operation == "base":
        name = str(expression.get("property") or current[1]).lower()
        return context.base_values[current[0]][name]
    if operation == "time":
        units = str(expression.get("units") or "seconds").lower()
        return context.time_ms if units in {"ms", "milliseconds"} else context.time_ms / 1000.0
    if operation == "index":
        offset = int(expression.get("offset", 0) or 0)
        return float(context.layer_indexes[current[0]] + offset)
    if operation == "property":
        layer_id = str(expression.get("layer_id") or current[0])
        name = str(expression.get("property") or "").lower()
        if bool(expression.get("base", False)):
            return context.base_values[layer_id][name]
        return _resolve_property((layer_id, name), context)
    if operation in {"audio", "beat"}:
        return _audio_value(context, expression, current[0], beat=operation == "beat")
    if operation in {"add", "subtract", "multiply", "divide"}:
        left = _evaluate_node(expression["left"], context, current)
        right = _evaluate_node(expression["right"], context, current)
        operations = {
            "add": lambda a, b: a + b,
            "subtract": lambda a, b: a - b,
            "multiply": lambda a, b: a * b,
            "divide": lambda a, b: a / b if abs(b) > 1e-12 else 0.0,
        }
        return _broadcast_binary(left, right, operations[operation], operation)
    if operation == "clamp":
        value = _evaluate_node(expression["value"], context, current)
        minimum = _evaluate_node(expression.get("min", 0.0), context, current)
        maximum = _evaluate_node(expression.get("max", 1.0), context, current)
        return _broadcast_binary(_broadcast_binary(value, minimum, max, "clamp"), maximum, min, "clamp")
    if operation == "remap":
        value = _number(_evaluate_node(expression["value"], context, current), "remap value")
        in_min = _number(_evaluate_node(expression["in_min"], context, current), "remap in_min")
        in_max = _number(_evaluate_node(expression["in_max"], context, current), "remap in_max")
        out_min = _number(_evaluate_node(expression["out_min"], context, current), "remap out_min")
        out_max = _number(_evaluate_node(expression["out_max"], context, current), "remap out_max")
        amount = 0.0 if abs(in_max - in_min) <= 1e-12 else (value - in_min) / (in_max - in_min)
        if bool(expression.get("clamp", True)):
            amount = max(0.0, min(1.0, amount))
        return out_min + (out_max - out_min) * amount
    if operation in {"sin", "cos", "negate"}:
        value = _evaluate_node(expression["value"], context, current)
        unary = {"sin": math.sin, "cos": math.cos, "negate": lambda item: -item}[operation]
        numeric = _numeric_value(value)
        return [unary(item) for item in numeric] if isinstance(numeric, list) else unary(numeric)
    if operation == "component":
        value = _numeric_value(_evaluate_node(expression["value"], context, current))
        if not isinstance(value, list):
            return value
        index = int(expression.get("index", 0) or 0)
        if not 0 <= index < len(value):
            raise MotionExpressionError(f"component index out of range: {index}")
        return value[index]
    if operation == "vector":
        return [_number(_evaluate_node(item, context, current), "vector component")
                for item in expression.get("items", [])]
    raise MotionExpressionError(f"unsupported expression operation: {operation or '<missing>'}")


def _coerce_property(value: Any, property_name: str) -> Any:
    if property_name in {"position", "scale", "anchor"}:
        result = _numeric_value(value, property_name)
        if not isinstance(result, list) or len(result) != 2:
            raise MotionExpressionError(f"{property_name} expression must return a 2D vector")
        return result
    return _number(value, property_name)


def _resolve_property(node: tuple[str, str], context: _ExpressionContext) -> Any:
    layer_id, property_name = node
    if layer_id not in context.resolved_values:
        raise MotionExpressionError(f"unknown expression layer: {layer_id}")
    if property_name not in EXPRESSION_PROPERTIES:
        raise MotionExpressionError(f"unsupported expression property: {property_name}")
    expression = context.expressions.get(node)
    if expression is None:
        return context.resolved_values[layer_id][property_name]
    if node in context.resolving:
        cycle = " -> ".join(f"{lid}.{name}" for lid, name in (*context.resolving, node))
        raise MotionExpressionCycleError(f"expression dependency cycle: {cycle}")
    context.resolving.append(node)
    try:
        value = _coerce_property(_evaluate_node(expression, context, node), property_name)
        context.resolved_values[layer_id][property_name] = value
        return value
    finally:
        context.resolving.pop()


def apply_composition_expressions(
    composition: MotionComposition,
    time_ms: float,
    values_by_id: MutableMapping[str, MutableMapping[str, Any]],
) -> None:
    issues = expression_issues(composition)
    if issues:
        raise MotionExpressionError(issues[0].message)
    expressions = {
        (layer.id, name): expression
        for layer in composition.layers
        for name, expression in layer_expressions(layer).items()
    }
    if not expressions:
        return
    base_values = {
        layer_id: {name: list(value) if isinstance(value, list) else value for name, value in values.items()}
        for layer_id, values in values_by_id.items()
    }
    context = _ExpressionContext(
        composition=composition,
        time_ms=float(time_ms),
        base_values=base_values,
        resolved_values=values_by_id,
        expressions=expressions,
        layer_indexes={layer.id: index for index, layer in enumerate(composition.layers)},
        resolving=[],
    )
    for node in expressions:
        _resolve_property(node, context)


def bake_procedural_transform(
    composition: MotionComposition,
    layer_id: str,
    *,
    sample_fps: float | None = None,
) -> dict[str, Any]:
    """Bake the final procedural transform and clear inputs that were sampled."""
    from .audio_reactive import AUDIO_REACTIVE_KEY
    from .evaluator import evaluate_composition

    layer = next((item for item in composition.layers if item.id == layer_id), None)
    if layer is None:
        raise MotionExpressionError(f"unknown layer: {layer_id}")
    expressions = layer_expressions(layer)
    had_behaviors = bool(layer.behaviors)
    had_audio = bool(layer.metadata.get(AUDIO_REACTIVE_KEY))
    if not expressions and not had_behaviors and not had_audio:
        return {"keyframes": 0, "cleared": []}
    fps = max(1.0, min(120.0, float(sample_fps or composition.fps)))
    step = 1000.0 / fps
    composition_times: list[float] = []
    cursor = float(max(0, layer.in_ms))
    end = float(min(composition.duration_ms, layer.out_ms))
    while cursor < end:
        composition_times.append(cursor)
        cursor += step
    if not composition_times or composition_times[-1] != end:
        composition_times.append(end)
    samples: list[tuple[int, Any]] = []
    seen_local_times: set[int] = set()
    for composition_time in composition_times:
        state = next(item for item in evaluate_composition(composition, composition_time) if item.id == layer_id)
        local_time = int(round(state.local_time_ms))
        if local_time in seen_local_times:
            continue
        seen_local_times.add(local_time)
        samples.append((local_time, state))
    for property_name, prop in layer.transform.properties().items():
        prop.keyframes = [
            Keyframe(
                time_ms=local_time,
                value=(list(getattr(state, property_name)) if property_name in {"position", "scale", "anchor"}
                       else float(getattr(state, property_name))),
                interpolation="linear",
                metadata={"baked_from": "motion_procedural"},
            )
            for local_time, state in samples
        ]
    cleared: list[str] = []
    if expressions:
        layer.metadata.pop(EXPRESSION_KEY, None)
        cleared.append("expressions")
    if had_behaviors:
        layer.behaviors = []
        cleared.append("behaviors")
    if had_audio:
        layer.metadata.pop(AUDIO_REACTIVE_KEY, None)
        cleared.append("audio_reactive")
    composition.revision += 1
    return {"keyframes": len(samples) * len(EXPRESSION_PROPERTIES), "cleared": cleared}


__all__ = [
    "EXPRESSION_KEY", "EXPRESSION_PROPERTIES", "ExpressionIssue",
    "MotionExpressionCycleError", "MotionExpressionError", "SUPPORTED_OPERATIONS",
    "apply_composition_expressions", "bake_procedural_transform", "clear_layer_expression",
    "expression_issues", "layer_expressions", "set_layer_expression", "validate_expression_tree",
]
