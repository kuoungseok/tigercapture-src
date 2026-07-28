"""QPainterPath tessellation and Boolean cache for vector sources."""
from __future__ import annotations

from collections import OrderedDict
import json
from typing import Any, Mapping

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath, QPainterPathStroker

from .vector_shapes import VectorPath, evaluate_source_param, flatten_path, path_from_params, trim_polylines


def painter_path_from_vector(path: VectorPath) -> QPainterPath:
    result = QPainterPath()
    if not path.points:
        return result
    result.setFillRule(Qt.OddEvenFill if path.fill_rule == "odd_even" else Qt.WindingFill)
    result.moveTo(*path.points[0].position)
    segment_count = len(path.points) if path.closed else len(path.points) - 1
    for index in range(segment_count):
        start = path.points[index]
        end = path.points[(index + 1) % len(path.points)]
        control1 = QPointF(
            start.position[0] + start.out_tangent[0],
            start.position[1] + start.out_tangent[1],
        )
        control2 = QPointF(
            end.position[0] + end.in_tangent[0],
            end.position[1] + end.in_tangent[1],
        )
        if start.out_tangent == (0.0, 0.0) and end.in_tangent == (0.0, 0.0):
            result.lineTo(*end.position)
        else:
            result.cubicTo(control1, control2, QPointF(*end.position))
    if path.closed:
        result.closeSubpath()
    return result


def combine_painter_paths(paths: list[QPainterPath], operation: str) -> QPainterPath:
    if not paths:
        return QPainterPath()
    result = QPainterPath(paths[0])
    for path in paths[1:]:
        normalized = str(operation or "union").lower()
        if normalized == "subtract":
            result = result.subtracted(path)
        elif normalized == "intersect":
            result = result.intersected(path)
        elif normalized in {"exclude", "xor"}:
            intersection = result.intersected(path)
            result = result.united(path).subtracted(intersection)
        else:
            result = result.united(path)
    return result


def offset_painter_path(
    path: QPainterPath,
    amount: float,
    join: str = "round",
) -> QPainterPath:
    distance = float(amount)
    if path.isEmpty() or abs(distance) <= 1e-6:
        return QPainterPath(path)
    stroker = QPainterPathStroker()
    stroker.setWidth(abs(distance) * 2.0)
    stroker.setJoinStyle({
        "miter": Qt.MiterJoin,
        "bevel": Qt.BevelJoin,
    }.get(str(join).lower(), Qt.RoundJoin))
    outline = stroker.createStroke(path)
    return (
        path.united(outline)
        if distance > 0.0
        else path.subtracted(outline)
    ).simplified()


def _trimmed_path(path: VectorPath, start: float, end: float, offset: float, tolerance: float) -> QPainterPath:
    result = QPainterPath()
    points = flatten_path(path, tolerance=tolerance)
    for segment in trim_polylines(points, start, end, offset, closed=path.closed):
        result.moveTo(*segment[0])
        for point in segment[1:]:
            result.lineTo(*point)
    return result


class VectorTessellationCache:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = max(1, int(capacity))
        self._items: OrderedDict[str, QPainterPath] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def clear(self) -> None:
        self._items.clear()
        self.hits = 0
        self.misses = 0

    def get(self, key_data: Mapping[str, Any], factory) -> QPainterPath:
        key = json.dumps(key_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        cached = self._items.pop(key, None)
        if cached is not None:
            self.hits += 1
            self._items[key] = cached
            return QPainterPath(cached)
        self.misses += 1
        path = factory()
        self._items[key] = QPainterPath(path)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return QPainterPath(path)


VECTOR_TESSELLATION_CACHE = VectorTessellationCache()


def build_vector_painter_path(params: Mapping[str, Any], time_ms: float = 0.0,
                              *, tolerance: float = .5) -> QPainterPath:
    base = path_from_params(params, time_ms)
    boolean_data = evaluate_source_param(params, "boolean", time_ms, {})
    paths = [base]
    operation = "union"
    if isinstance(boolean_data, Mapping):
        operation = str(boolean_data.get("operation") or "union")
        for row in boolean_data.get("paths", []):
            if isinstance(row, Mapping):
                paths.append(VectorPath.from_dict(row))
    trim = evaluate_source_param(params, "trim", time_ms, {})
    trim = trim if isinstance(trim, Mapping) else {}
    start = float(trim.get("start", 0.0) or 0.0)
    end = float(trim.get("end", 1.0) if trim.get("end", 1.0) is not None else 1.0)
    offset = float(trim.get("offset", 0.0) or 0.0)
    offset_data = evaluate_source_param(params, "offset_path", time_ms, {})
    offset_data = offset_data if isinstance(offset_data, Mapping) else {}
    offset_amount = float(offset_data.get("amount", 0.0) or 0.0)
    offset_join = str(offset_data.get("join") or "round").lower()
    key_data = {
        "paths": [path.to_dict() for path in paths],
        "operation": operation,
        "trim": [start, end, offset],
        "offset_path": [offset_amount, offset_join],
        "tolerance": float(tolerance),
    }

    def build() -> QPainterPath:
        if (
            len(paths) == 1
            and abs(offset_amount) <= 1e-6
            and (start > 0.0 or end < 1.0 or offset != 0.0)
        ):
            return _trimmed_path(paths[0], start, end, offset, tolerance)
        combined = combine_painter_paths([painter_path_from_vector(path) for path in paths], operation)
        combined = offset_painter_path(combined, offset_amount, offset_join)
        if start <= 0.0 and end >= 1.0 and offset == 0.0:
            return combined
        result = QPainterPath()
        for polygon in combined.toSubpathPolygons():
            points = [(point.x(), point.y()) for point in polygon]
            for segment in trim_polylines(points, start, end, offset, closed=True):
                result.moveTo(*segment[0])
                for point in segment[1:]:
                    result.lineTo(*point)
        return result

    return VECTOR_TESSELLATION_CACHE.get(key_data, build)
