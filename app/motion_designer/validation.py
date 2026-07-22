"""Validation for Motion Designer documents."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Iterable, Mapping, Sequence

from .schema import AnimatedProperty, MotionComposition


VECTOR_BOOLEAN_OPERATIONS = {"union", "subtract", "intersect", "exclude", "xor"}
VECTOR_ANIMATED_PARAMS = {
    "path", "width", "height", "radius", "sides", "inner_ratio", "shape_rotation",
    "fill", "stroke", "stroke_width", "gradient", "trim", "repeater",
}
TYPOGRAPHY_ANIMATED_PARAMS = {
    "text", "font_family", "font_size", "font_weight", "font_axes", "fill",
    "stroke", "stroke_width", "letter_spacing", "line_height", "text_animation",
    "text_path", "text_path_offset",
}


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    path: str = ""
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path, "severity": self.severity}


@dataclass(slots=True)
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "issues": [issue.to_dict() for issue in self.issues]}


def _default_value(value: Any) -> Any:
    if isinstance(value, Mapping) and ("default" in value or "keyframes" in value):
        return value.get("default")
    return value


def _valid_point(value: Any) -> bool:
    return (
        isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        and len(value) >= 2
        and all(isinstance(item, (int, float)) and isfinite(float(item)) for item in value[:2])
    )


def _validate_vector_path(data: Any, path: str, issues: list[ValidationIssue], *, closed_minimum: int = 2) -> None:
    if not isinstance(data, Mapping):
        issues.append(ValidationIssue("invalid_vector_path", "Vector path must be an object.", path))
        return
    points = data.get("points")
    minimum = 3 if bool(data.get("closed", True)) else closed_minimum
    if not isinstance(points, list) or len(points) < minimum:
        issues.append(ValidationIssue(
            "invalid_vector_path", f"Vector path requires at least {minimum} points.", f"{path}.points",
        ))
        return
    for index, point in enumerate(points):
        point_path = f"{path}.points[{index}]"
        if not isinstance(point, Mapping) or not _valid_point(point.get("position")):
            issues.append(ValidationIssue("invalid_vector_point", "Vector point position must be finite x/y.", point_path))
            continue
        for tangent in ("in", "out"):
            if tangent in point and not _valid_point(point.get(tangent)):
                issues.append(ValidationIssue(
                    "invalid_vector_tangent", "Vector tangent must be finite x/y.", f"{point_path}.{tangent}",
                ))


def _validate_vector_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type != "shape":
        return
    params = layer.source.params
    shape = str(_default_value(params.get("shape", "rectangle")) or "rectangle").lower()
    if shape not in {"rectangle", "ellipse", "polygon", "star", "path"}:
        issues.append(ValidationIssue("invalid_vector_primitive", f"Unsupported vector primitive: {shape}", f"{path}.source.params.shape"))
    if "path" in params:
        _validate_vector_path(_default_value(params.get("path")), f"{path}.source.params.path", issues)
    if shape in {"polygon", "star"}:
        sides = _default_value(params.get("sides", 5))
        if not isinstance(sides, (int, float)) or not 3 <= int(sides) <= 128:
            issues.append(ValidationIssue("invalid_vector_sides", "Polygon/star sides must be between 3 and 128.", f"{path}.source.params.sides"))
    boolean = _default_value(params.get("boolean"))
    if boolean is not None:
        if not isinstance(boolean, Mapping):
            issues.append(ValidationIssue("invalid_vector_boolean", "Vector Boolean must be an object.", f"{path}.source.params.boolean"))
        else:
            operation = str(boolean.get("operation") or "union").lower()
            if operation not in VECTOR_BOOLEAN_OPERATIONS:
                issues.append(ValidationIssue("invalid_vector_boolean", f"Unsupported Boolean operation: {operation}", f"{path}.source.params.boolean.operation"))
            for index, item in enumerate(boolean.get("paths", [])):
                _validate_vector_path(item, f"{path}.source.params.boolean.paths[{index}]", issues, closed_minimum=3)
    trim = _default_value(params.get("trim"))
    if trim is not None:
        if not isinstance(trim, Mapping):
            issues.append(ValidationIssue("invalid_vector_trim", "Vector trim must be an object.", f"{path}.source.params.trim"))
        else:
            for key, default in (("start", 0.0), ("end", 1.0)):
                value = trim.get(key, default)
                if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                    issues.append(ValidationIssue("invalid_vector_trim", f"Trim {key} must be between 0 and 1.", f"{path}.source.params.trim.{key}"))
    repeater = _default_value(params.get("repeater"))
    if repeater is not None:
        count = repeater.get("count", 1) if isinstance(repeater, Mapping) else None
        if not isinstance(count, (int, float)) or not 1 <= int(count) <= 512:
            issues.append(ValidationIssue("invalid_vector_repeater", "Repeater count must be between 1 and 512.", f"{path}.source.params.repeater.count"))
    for name in VECTOR_ANIMATED_PARAMS:
        value = params.get(name)
        if not isinstance(value, Mapping) or not ("default" in value or "keyframes" in value):
            continue
        prop = AnimatedProperty.from_dict(value)
        key_path = f"{path}.source.params.{name}"
        times = [key.time_ms for key in prop.keyframes]
        if times != sorted(times):
            issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
        key_ids = [key.id for key in prop.keyframes]
        if len(key_ids) != len(set(key_ids)):
            issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))


def _validate_typography_layer(layer, path: str, issues: list[ValidationIssue]) -> None:
    if layer.layer_type != "text":
        return
    from app.typo_animations import REGISTRY

    params = layer.source.params
    font_size = _default_value(params.get("font_size", 72))
    if not isinstance(font_size, (int, float)) or float(font_size) <= 0:
        issues.append(ValidationIssue(
            "invalid_typography_font_size", "Typography font size must be positive.",
            f"{path}.source.params.font_size",
        ))
    axes = _default_value(params.get("font_axes", {}))
    if axes is not None and not isinstance(axes, Mapping):
        issues.append(ValidationIssue(
            "invalid_typography_axes", "Variable font axes must be an object.",
            f"{path}.source.params.font_axes",
        ))
    elif isinstance(axes, Mapping):
        for name, value in axes.items():
            if len(str(name)) != 4 or not isinstance(value, (int, float)) or not isfinite(float(value)):
                issues.append(ValidationIssue(
                    "invalid_typography_axis", "Variable font axis tags require four characters and a finite value.",
                    f"{path}.source.params.font_axes.{name}",
                ))
    text_path = _default_value(params.get("text_path"))
    if text_path is not None:
        _validate_vector_path(text_path, f"{path}.source.params.text_path", issues, closed_minimum=2)
    animation = _default_value(params.get("text_animation", {}))
    if animation is not None and not isinstance(animation, Mapping):
        issues.append(ValidationIssue(
            "invalid_typography_animation", "Typography animation must be an object.",
            f"{path}.source.params.text_animation",
        ))
    elif isinstance(animation, Mapping):
        for phase in ("in", "hold", "out"):
            animation_id = str(animation.get(phase) or "none")
            if animation_id not in REGISTRY:
                issues.append(ValidationIssue(
                    "invalid_typography_animation", f"Unknown typography animation: {animation_id}",
                    f"{path}.source.params.text_animation.{phase}",
                ))
        unit = str(animation.get("unit") or "character")
        if unit not in {"character", "word", "line"}:
            issues.append(ValidationIssue(
                "invalid_typography_selector", f"Unsupported typography selector unit: {unit}",
                f"{path}.source.params.text_animation.unit",
            ))
        start = animation.get("selector_start", 0.0)
        end = animation.get("selector_end", 1.0)
        if not all(isinstance(value, (int, float)) and 0 <= float(value) <= 1 for value in (start, end)) or float(start) > float(end):
            issues.append(ValidationIssue(
                "invalid_typography_selector", "Typography selector range must satisfy 0 <= start <= end <= 1.",
                f"{path}.source.params.text_animation",
            ))
        for name in ("in_duration_ms", "out_duration_ms", "stagger_ms"):
            value = animation.get(name, 0)
            if not isinstance(value, (int, float)) or float(value) < 0:
                issues.append(ValidationIssue(
                    "invalid_typography_timing", f"Typography {name} must be non-negative.",
                    f"{path}.source.params.text_animation.{name}",
                ))
    for name in TYPOGRAPHY_ANIMATED_PARAMS:
        value = params.get(name)
        if not isinstance(value, Mapping) or not ("default" in value or "keyframes" in value):
            continue
        prop = AnimatedProperty.from_dict(value)
        key_path = f"{path}.source.params.{name}"
        times = [key.time_ms for key in prop.keyframes]
        if times != sorted(times):
            issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
        key_ids = [key.id for key in prop.keyframes]
        if len(key_ids) != len(set(key_ids)):
            issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))


def validate_composition(composition: MotionComposition) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if composition.width <= 0 or composition.height <= 0:
        issues.append(ValidationIssue("invalid_size", "Composition dimensions must be positive.", "viewport"))
    if composition.fps <= 0:
        issues.append(ValidationIssue("invalid_fps", "Composition fps must be positive.", "fps"))
    if composition.duration_ms <= 0:
        issues.append(ValidationIssue("invalid_duration", "Composition duration must be positive.", "duration_ms"))

    ids = [layer.id for layer in composition.layers]
    duplicate_ids = {layer_id for layer_id in ids if ids.count(layer_id) > 1}
    for layer_id in sorted(duplicate_ids):
        issues.append(ValidationIssue("duplicate_layer_id", f"Duplicate layer id: {layer_id}", "layers"))

    id_set = set(ids)
    layers_by_id = {layer.id: layer for layer in composition.layers}
    boolean_operands: dict[str, list[str]] = {}
    for index, layer in enumerate(composition.layers):
        boolean = _default_value(layer.source.params.get("boolean"))
        if not isinstance(boolean, Mapping):
            continue
        refs = [str(value or "") for value in boolean.get("operand_layer_ids", []) if str(value or "")]
        boolean_operands[layer.id] = refs
        for operand_index, operand_id in enumerate(refs):
            operand_path = f"layers[{index}].source.params.boolean.operand_layer_ids[{operand_index}]"
            if operand_id == layer.id:
                issues.append(ValidationIssue(
                    "vector_boolean_self_reference", "A Boolean layer cannot consume itself.", operand_path,
                ))
            elif operand_id not in id_set:
                issues.append(ValidationIssue(
                    "missing_vector_boolean_operand", f"Unknown Boolean operand: {operand_id}", operand_path,
                ))
            elif layers_by_id[operand_id].layer_type != "shape":
                issues.append(ValidationIssue(
                    "invalid_vector_boolean_operand", "Boolean operands must be shape layers.", operand_path,
                ))

    cycle_nodes: set[str] = set()

    def visit_boolean(node: str, stack: tuple[str, ...]) -> None:
        if node in stack:
            cycle_nodes.update((*stack[stack.index(node):], node))
            return
        for operand_id in boolean_operands.get(node, []):
            if operand_id in boolean_operands:
                visit_boolean(operand_id, (*stack, node))

    for layer_id in boolean_operands:
        visit_boolean(layer_id, ())
    for layer_id in sorted(cycle_nodes):
        issues.append(ValidationIssue(
            "vector_boolean_cycle", f"Boolean operand cycle includes: {layer_id}", "layers",
        ))
    parent_by_id: dict[str, str] = {}
    for layer in composition.layers:
        parent_by_id.setdefault(layer.id, layer.parent_id)
    for index, layer in enumerate(composition.layers):
        path = f"layers[{index}]"
        if layer.out_ms <= layer.in_ms:
            issues.append(ValidationIssue("invalid_layer_range", "Layer out_ms must be after in_ms.", path))
        if layer.parent_id and layer.parent_id not in id_set:
            issues.append(ValidationIssue("missing_parent", f"Unknown parent: {layer.parent_id}", f"{path}.parent_id"))
        seen: set[str] = set()
        node = layer.id
        while node:
            if node in seen:
                issues.append(ValidationIssue("parent_cycle", f"Parent cycle includes: {node}", f"{path}.parent_id"))
                break
            seen.add(node)
            node = parent_by_id.get(node, "")
        for prop_name, prop in layer.transform.properties().items():
            times = [key.time_ms for key in prop.keyframes]
            if times != sorted(times):
                issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", f"{path}.transform.{prop_name}"))
            key_ids = [key.id for key in prop.keyframes]
            if len(key_ids) != len(set(key_ids)):
                issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", f"{path}.transform.{prop_name}"))
        for collection_name, items in (("effects", layer.effects), ("masks", layer.masks)):
            item_ids = [item.id for item in items]
            if len(item_ids) != len(set(item_ids)):
                issues.append(ValidationIssue(
                    f"duplicate_{collection_name[:-1]}_id",
                    f"{collection_name.title()} ids must be unique.",
                    f"{path}.{collection_name}",
                ))
            for item_index, item in enumerate(items):
                for param_name, prop in item.params.items():
                    key_path = f"{path}.{collection_name}[{item_index}].params.{param_name}"
                    times = [key.time_ms for key in prop.keyframes]
                    if times != sorted(times):
                        issues.append(ValidationIssue("unsorted_keyframes", "Keyframes must be time sorted.", key_path))
                    key_ids = [key.id for key in prop.keyframes]
                    if len(key_ids) != len(set(key_ids)):
                        issues.append(ValidationIssue("duplicate_keyframe_id", "Keyframe ids must be unique.", key_path))
                if collection_name == "masks":
                    tracking = item.metadata.get("tracking_cache")
                    if isinstance(tracking, Mapping):
                        track_path = f"{path}.masks[{item_index}].metadata.tracking_cache"
                        mode = str(tracking.get("mode") or "point")
                        if mode not in {"point", "planar"}:
                            issues.append(ValidationIssue(
                                "invalid_mask_tracking_mode",
                                "Mask tracking mode must be point or planar.",
                                f"{track_path}.mode",
                            ))
                        samples = [row for row in tracking.get("samples", []) if isinstance(row, Mapping)]
                        times = [int(row.get("time_ms", 0) or 0) for row in samples]
                        if times != sorted(times):
                            issues.append(ValidationIssue(
                                "unsorted_mask_tracking_samples",
                                "Mask tracking samples must be time sorted.",
                                f"{track_path}.samples",
                            ))
                        if tracking.get("enabled", True) and not samples:
                            issues.append(ValidationIssue(
                                "empty_mask_tracking_cache",
                                "Mask tracking is enabled but has no cached samples.",
                                f"{track_path}.samples",
                                severity="warning",
                            ))
        _validate_vector_layer(layer, path, issues)
        _validate_typography_layer(layer, path, issues)
    return ValidationReport(issues)


def validate_all(compositions: Iterable[MotionComposition]) -> ValidationReport:
    issues: list[ValidationIssue] = []
    seen: set[str] = set()
    for index, composition in enumerate(compositions):
        if composition.id in seen:
            issues.append(ValidationIssue("duplicate_composition_id", composition.id, f"motion_compositions[{index}]"))
        seen.add(composition.id)
        for issue in validate_composition(composition).issues:
            issue.path = f"motion_compositions[{index}].{issue.path}".rstrip(".")
            issues.append(issue)
    return ValidationReport(issues)
