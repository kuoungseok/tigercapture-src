"""Qt-free vector shape model and deterministic geometry helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, pi, radians, sin
from typing import Any, Mapping, Sequence

from .keyframes import evaluate_property
from .schema import AnimatedProperty


Point = tuple[float, float]


def _point(value: Sequence[float] | None, default: Point = (0.0, 0.0)) -> Point:
    values = list(value or default)
    if len(values) < 2:
        return default
    return float(values[0]), float(values[1])


@dataclass(slots=True)
class VectorPoint:
    position: Point = (0.0, 0.0)
    in_tangent: Point = (0.0, 0.0)
    out_tangent: Point = (0.0, 0.0)

    def to_dict(self) -> dict[str, list[float]]:
        return {
            "position": list(self.position),
            "in": list(self.in_tangent),
            "out": list(self.out_tangent),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | Sequence[float]) -> "VectorPoint":
        if not isinstance(data, Mapping):
            return cls(position=_point(data))
        return cls(
            position=_point(data.get("position")),
            in_tangent=_point(data.get("in")),
            out_tangent=_point(data.get("out")),
        )


@dataclass(slots=True)
class VectorPath:
    points: list[VectorPoint] = field(default_factory=list)
    closed: bool = True
    fill_rule: str = "winding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "closed": bool(self.closed),
            "fill_rule": self.fill_rule,
            "points": [point.to_dict() for point in self.points],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "VectorPath":
        data = data if isinstance(data, Mapping) else {}
        return cls(
            points=[VectorPoint.from_dict(item) for item in data.get("points", [])],
            closed=bool(data.get("closed", True)),
            fill_rule=str(data.get("fill_rule") or "winding"),
        )


def evaluate_source_param(params: Mapping[str, Any], key: str, time_ms: float, default: Any) -> Any:
    value = params.get(key, default)
    if isinstance(value, Mapping) and ("default" in value or "keyframes" in value):
        return evaluate_property(AnimatedProperty.from_dict(value), time_ms)
    return value


def primitive_path(kind: str, width: float, height: float, params: Mapping[str, Any] | None = None) -> VectorPath:
    params = params or {}
    width, height = max(1.0, float(width)), max(1.0, float(height))
    cx, cy = width * .5, height * .5
    rx, ry = max(0.0, width * .5 - 1.0), max(0.0, height * .5 - 1.0)
    normalized = str(kind or "rectangle").lower()
    if normalized == "ellipse":
        kappa = 0.5522847498307936
        return VectorPath(points=[
            VectorPoint((cx + rx, cy), (0.0, -ry * kappa), (0.0, ry * kappa)),
            VectorPoint((cx, cy + ry), (rx * kappa, 0.0), (-rx * kappa, 0.0)),
            VectorPoint((cx - rx, cy), (0.0, ry * kappa), (0.0, -ry * kappa)),
            VectorPoint((cx, cy - ry), (-rx * kappa, 0.0), (rx * kappa, 0.0)),
        ])
    if normalized in {"polygon", "star"}:
        sides = max(3, min(128, int(params.get("sides", 5) or 5)))
        inner_ratio = max(.01, min(.99, float(params.get("inner_ratio", .45) or .45)))
        rotation = radians(float(params.get("rotation", -90.0) or -90.0))
        count = sides * 2 if normalized == "star" else sides
        points: list[VectorPoint] = []
        for index in range(count):
            angle = rotation + index * 2.0 * pi / count
            radius_factor = inner_ratio if normalized == "star" and index % 2 else 1.0
            points.append(VectorPoint((
                cx + cos(angle) * rx * radius_factor,
                cy + sin(angle) * ry * radius_factor,
            )))
        return VectorPath(points=points)
    radius = max(0.0, min(min(rx, ry), float(params.get("radius", 0.0) or 0.0)))
    if radius > 0.0:
        kappa = 0.5522847498307936
        left, top, right, bottom = 1.0, 1.0, width - 1.0, height - 1.0
        return VectorPath(points=[
            VectorPoint((left + radius, top), in_tangent=(-radius * kappa, 0.0)),
            VectorPoint((right - radius, top), out_tangent=(radius * kappa, 0.0)),
            VectorPoint((right, top + radius), in_tangent=(0.0, -radius * kappa)),
            VectorPoint((right, bottom - radius), out_tangent=(0.0, radius * kappa)),
            VectorPoint((right - radius, bottom), in_tangent=(radius * kappa, 0.0)),
            VectorPoint((left + radius, bottom), out_tangent=(-radius * kappa, 0.0)),
            VectorPoint((left, bottom - radius), in_tangent=(0.0, radius * kappa)),
            VectorPoint((left, top + radius), out_tangent=(0.0, -radius * kappa)),
        ])
    return VectorPath(points=[
        VectorPoint((1.0, 1.0)),
        VectorPoint((width - 1.0, 1.0)),
        VectorPoint((width - 1.0, height - 1.0)),
        VectorPoint((1.0, height - 1.0)),
    ])


def default_pen_path(width: float, height: float) -> VectorPath:
    width, height = max(1.0, float(width)), max(1.0, float(height))
    return VectorPath(closed=False, points=[
        VectorPoint((width * .12, height * .70), out_tangent=(width * .18, -height * .48)),
        VectorPoint(
            (width * .50, height * .35),
            in_tangent=(-width * .18, -height * .08),
            out_tangent=(width * .18, height * .08),
        ),
        VectorPoint((width * .88, height * .62), in_tangent=(-width * .18, height * .34)),
    ])


def path_from_params(params: Mapping[str, Any], time_ms: float = 0.0) -> VectorPath:
    width = float(evaluate_source_param(params, "width", time_ms, 400.0))
    height = float(evaluate_source_param(params, "height", time_ms, 220.0))
    kind = str(evaluate_source_param(params, "shape", time_ms, "rectangle"))
    path_data = evaluate_source_param(params, "path", time_ms, None)
    if isinstance(path_data, Mapping) and path_data.get("points"):
        return VectorPath.from_dict(path_data)
    if kind == "path":
        return default_pen_path(width, height)
    evaluated = {
        "sides": evaluate_source_param(params, "sides", time_ms, 5),
        "inner_ratio": evaluate_source_param(params, "inner_ratio", time_ms, .45),
        "rotation": evaluate_source_param(params, "shape_rotation", time_ms, -90.0),
        "radius": evaluate_source_param(params, "radius", time_ms, 0.0),
    }
    return primitive_path(kind, width, height, evaluated)


def _add(a: Point, b: Point) -> Point:
    return a[0] + b[0], a[1] + b[1]


def _mid(a: Point, b: Point) -> Point:
    return (a[0] + b[0]) * .5, (a[1] + b[1]) * .5


def _distance_to_line(point: Point, start: Point, end: Point) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if length <= 1e-9:
        return hypot(point[0] - start[0], point[1] - start[1])
    return abs(dy * point[0] - dx * point[1] + end[0] * start[1] - end[1] * start[0]) / length


def _flatten_cubic(start: Point, control1: Point, control2: Point, end: Point,
                   tolerance: float, depth: int = 0) -> list[Point]:
    if depth >= 14 or max(
        _distance_to_line(control1, start, end),
        _distance_to_line(control2, start, end),
    ) <= tolerance:
        return [start, end]
    p01, p12, p23 = _mid(start, control1), _mid(control1, control2), _mid(control2, end)
    p012, p123 = _mid(p01, p12), _mid(p12, p23)
    center = _mid(p012, p123)
    left = _flatten_cubic(start, p01, p012, center, tolerance, depth + 1)
    right = _flatten_cubic(center, p123, p23, end, tolerance, depth + 1)
    return [*left[:-1], *right]


def flatten_path(path: VectorPath, tolerance: float = .5) -> list[Point]:
    if len(path.points) < 2:
        return [point.position for point in path.points]
    output: list[Point] = []
    segment_count = len(path.points) if path.closed else len(path.points) - 1
    for index in range(segment_count):
        start = path.points[index]
        end = path.points[(index + 1) % len(path.points)]
        points = _flatten_cubic(
            start.position,
            _add(start.position, start.out_tangent),
            _add(end.position, end.in_tangent),
            end.position,
            max(.01, float(tolerance)),
        )
        output.extend(points if not output else points[1:])
    if path.closed and output and output[-1] != output[0]:
        output.append(output[0])
    return output


def _extract_polyline(points: list[Point], start_length: float, end_length: float) -> list[Point]:
    if len(points) < 2 or end_length <= start_length:
        return []
    lengths = [0.0]
    for left, right in zip(points, points[1:]):
        lengths.append(lengths[-1] + hypot(right[0] - left[0], right[1] - left[1]))
    output: list[Point] = []
    for index, (left_length, right_length) in enumerate(zip(lengths, lengths[1:])):
        if right_length < start_length or left_length > end_length:
            continue
        segment_length = max(1e-9, right_length - left_length)
        local_start = max(0.0, min(1.0, (start_length - left_length) / segment_length))
        local_end = max(0.0, min(1.0, (end_length - left_length) / segment_length))
        if local_end < 0.0 or local_start > 1.0:
            continue
        a, b = points[index], points[index + 1]
        start = (a[0] + (b[0] - a[0]) * local_start, a[1] + (b[1] - a[1]) * local_start)
        end = (a[0] + (b[0] - a[0]) * local_end, a[1] + (b[1] - a[1]) * local_end)
        if not output or output[-1] != start:
            output.append(start)
        if output[-1] != end:
            output.append(end)
    return output


def trim_polylines(points: list[Point], start: float, end: float, offset: float = 0.0,
                   *, closed: bool = False) -> list[list[Point]]:
    if len(points) < 2:
        return []
    total = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:]))
    if total <= 1e-9:
        return []
    span = float(end) - float(start)
    if abs(span) >= 1.0 - 1e-9:
        return [list(points)]
    start_value = float(start) + float(offset)
    end_value = float(end) + float(offset)
    if closed:
        start_value %= 1.0
        end_value %= 1.0
        ranges = [(start_value, end_value)] if end_value >= start_value else [
            (start_value, 1.0), (0.0, end_value),
        ]
    else:
        start_value = max(0.0, min(1.0, start_value))
        end_value = max(0.0, min(1.0, end_value))
        ranges = [(start_value, end_value)] if end_value > start_value else []
    return [segment for begin, finish in ranges
            if len(segment := _extract_polyline(points, begin * total, finish * total)) >= 2]


def repeater_instances(data: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    data = data if isinstance(data, Mapping) else {}
    count = max(1, min(512, int(data.get("count", 1) or 1)))
    offset = _point(data.get("offset"))
    rotation = float(data.get("rotation", 0.0) or 0.0)
    scale = _point(data.get("scale"), (1.0, 1.0))
    opacity_start = max(0.0, min(1.0, float(data.get("opacity_start", 1.0) or 0.0)))
    opacity_end = max(0.0, min(1.0, float(data.get("opacity_end", opacity_start) or 0.0)))
    rows = []
    for index in range(count):
        opacity = opacity_end if index == count - 1 else (
            opacity_start + (opacity_end - opacity_start) * index / max(1, count - 1)
        )
        rows.append({
            "index": index,
            "translate": [offset[0] * index, offset[1] * index],
            "rotation": rotation * index,
            "scale": [scale[0] ** index, scale[1] ** index],
            "opacity": opacity,
        })
    return rows
