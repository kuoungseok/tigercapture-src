"""Cached vector meshes consumed directly by the Motion OpenGL preview."""
from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
from math import cos, radians, sin
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QPainterPathStroker

from .schema import MotionLayer
from .vector_shapes import evaluate_source_param, repeater_instances
from .vector_tessellation import build_vector_painter_path


@dataclass(frozen=True, slots=True)
class VectorGpuMesh:
    key: str
    vertices: tuple[float, ...]
    triangle_count: int

    @property
    def vertex_count(self) -> int:
        return len(self.vertices) // 6


@dataclass(frozen=True, slots=True)
class VectorGpuInstance:
    matrix: tuple[float, float, float, float, float, float]
    opacity: float
    color: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0)


@dataclass(frozen=True, slots=True)
class VectorGpuPacket:
    mesh: VectorGpuMesh
    instances: tuple[VectorGpuInstance, ...]
    width: float
    height: float


class VectorGpuMeshCache:
    def __init__(self, capacity: int = 256) -> None:
        self.capacity = max(1, int(capacity))
        self._items: OrderedDict[str, VectorGpuMesh] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def clear(self) -> None:
        self._items.clear()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> VectorGpuMesh | None:
        value = self._items.pop(key, None)
        if value is None:
            self.misses += 1
            return None
        self.hits += 1
        self._items[key] = value
        return value

    def put(self, mesh: VectorGpuMesh) -> VectorGpuMesh:
        self._items.pop(mesh.key, None)
        self._items[mesh.key] = mesh
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return mesh


VECTOR_GPU_MESH_CACHE = VectorGpuMeshCache()


def _color(value: Any, fallback: str) -> QColor:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        channels = [float(channel) for channel in value]
        if len(channels) >= 3:
            scale = 1.0 if max(channels[:3]) <= 1.0 else 255.0
            alpha = channels[3] if len(channels) >= 4 else scale
            return QColor.fromRgbF(
                channels[0] / scale, channels[1] / scale, channels[2] / scale, alpha / scale,
            )
    color = QColor(str(value if value is not None else fallback))
    return color if color.isValid() else QColor(fallback)


def _premultiplied(color: QColor) -> tuple[float, float, float, float]:
    alpha = color.alphaF()
    return color.redF() * alpha, color.greenF() * alpha, color.blueF() * alpha, alpha


def _gradient_color(
    gradient: Mapping[str, Any] | Sequence[Any] | None,
    fill: QColor,
    x: float,
    y: float,
    width: float,
    height: float,
) -> tuple[float, float, float, float]:
    if not gradient:
        return _premultiplied(fill)
    if isinstance(gradient, Sequence) and not isinstance(gradient, (str, bytes)):
        stops = [
            (index / max(1, len(gradient) - 1), _color(value, "#ffffff"))
            for index, value in enumerate(gradient)
        ]
        start, end = (0.0, 0.0), (width, height)
    else:
        data = gradient if isinstance(gradient, Mapping) else {}
        raw_stops = list(data.get("stops") or [])
        stops = []
        for index, stop in enumerate(raw_stops):
            if isinstance(stop, Mapping):
                stops.append((float(stop.get("position", 0.0)), _color(stop.get("color"), "#ffffff")))
            elif isinstance(stop, Sequence) and len(stop) >= 2:
                stops.append((float(stop[0]), _color(stop[1], "#ffffff")))
            else:
                stops.append((index / max(1, len(raw_stops) - 1), _color(stop, "#ffffff")))
        raw_start = list(data.get("start") or [0.0, 0.0])
        raw_end = list(data.get("end") or [1.0, 1.0])
        start = float(raw_start[0]) * width, float(raw_start[1]) * height
        end = float(raw_end[0]) * width, float(raw_end[1]) * height
    if not stops:
        return _premultiplied(fill)
    stops.sort(key=lambda item: item[0])
    dx, dy = end[0] - start[0], end[1] - start[1]
    denominator = dx * dx + dy * dy
    amount = 0.0 if denominator <= 1e-9 else ((x - start[0]) * dx + (y - start[1]) * dy) / denominator
    amount = max(0.0, min(1.0, amount))
    left, right = stops[0], stops[-1]
    for index in range(1, len(stops)):
        if amount <= stops[index][0]:
            left, right = stops[index - 1], stops[index]
            break
    span = right[0] - left[0]
    mix = 0.0 if abs(span) <= 1e-9 else (amount - left[0]) / span
    a, b = left[1], right[1]
    mixed = QColor.fromRgbF(
        a.redF() + (b.redF() - a.redF()) * mix,
        a.greenF() + (b.greenF() - a.greenF()) * mix,
        a.blueF() + (b.blueF() - a.blueF()) * mix,
        a.alphaF() + (b.alphaF() - a.alphaF()) * mix,
    )
    return _premultiplied(mixed)


def _primitive_triangles(mode: int, values: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    triangles: list[tuple[float, float]] = []
    if mode == 4:
        limit = len(values) - len(values) % 3
        source = [values[index:index + 3] for index in range(0, limit, 3)]
    elif mode == 5:
        source = []
        for index in range(2, len(values)):
            a, b = values[index - 2], values[index - 1]
            source.append([b, a, values[index]] if index % 2 else [a, b, values[index]])
    elif mode == 6:
        source = [[values[0], values[index - 1], values[index]] for index in range(2, len(values))]
    else:
        return triangles
    for triangle in source:
        area = (
            (triangle[1][0] - triangle[0][0]) * (triangle[2][1] - triangle[0][1])
            - (triangle[1][1] - triangle[0][1]) * (triangle[2][0] - triangle[0][0])
        )
        if abs(area) > 1e-8:
            triangles.extend((float(row[0]), float(row[1])) for row in triangle)
    return triangles


def _tessellate(path: QPainterPath) -> list[tuple[float, float]]:
    try:
        from OpenGL import GLU
    except Exception:
        return []
    contours: list[list[tuple[float, float, float]]] = []
    for polygon in path.toSubpathPolygons():
        points = [(float(point.x()), float(point.y()), 0.0) for point in polygon]
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) >= 3:
            contours.append(points)
    if not contours:
        return []
    primitives: list[tuple[int, list[tuple[float, float, float]]]] = []
    current_mode = [0]
    current_vertices: list[tuple[float, float, float]] = []
    errors: list[int] = []

    def begin(mode) -> None:
        current_mode[0] = int(mode)
        current_vertices.clear()

    def vertex(value) -> None:
        current_vertices.append((float(value[0]), float(value[1]), float(value[2])))

    def end() -> None:
        primitives.append((current_mode[0], list(current_vertices)))

    def combine(coords, _data, _weights):
        return float(coords[0]), float(coords[1]), float(coords[2])

    def error(code) -> None:
        errors.append(int(code))

    tessellator = GLU.gluNewTess()
    callbacks = (
        (GLU.GLU_TESS_BEGIN, begin),
        (GLU.GLU_TESS_VERTEX, vertex),
        (GLU.GLU_TESS_END, end),
        (GLU.GLU_TESS_COMBINE, combine),
        (GLU.GLU_TESS_ERROR, error),
    )
    for callback, handler in callbacks:
        GLU.gluTessCallback(tessellator, callback, handler)
    winding = GLU.GLU_TESS_WINDING_ODD if path.fillRule() == Qt.OddEvenFill else GLU.GLU_TESS_WINDING_NONZERO
    GLU.gluTessProperty(tessellator, GLU.GLU_TESS_WINDING_RULE, winding)
    GLU.gluTessBeginPolygon(tessellator, None)
    for contour in contours:
        GLU.gluTessBeginContour(tessellator)
        for point in contour:
            GLU.gluTessVertex(tessellator, point, point)
        GLU.gluTessEndContour(tessellator)
    GLU.gluTessEndPolygon(tessellator)
    GLU.gluDeleteTess(tessellator)
    if errors:
        return []
    triangles: list[tuple[float, float]] = []
    for mode, values in primitives:
        triangles.extend(_primitive_triangles(mode, values))
    return triangles


def _stroke_path(path: QPainterPath, params: Mapping[str, Any], time_ms: float) -> QPainterPath:
    width = float(evaluate_source_param(params, "stroke_width", time_ms, 2.0))
    if width <= 0.0:
        return QPainterPath()
    stroker = QPainterPathStroker()
    stroker.setWidth(width)
    cap = str(evaluate_source_param(params, "cap", time_ms, "square")).lower()
    join = str(evaluate_source_param(params, "join", time_ms, "miter")).lower()
    stroker.setCapStyle({"round": Qt.RoundCap, "flat": Qt.FlatCap}.get(cap, Qt.SquareCap))
    stroker.setJoinStyle({"round": Qt.RoundJoin, "bevel": Qt.BevelJoin}.get(join, Qt.MiterJoin))
    dash = evaluate_source_param(params, "dash", time_ms, [])
    if isinstance(dash, Sequence) and not isinstance(dash, (str, bytes)) and dash:
        stroker.setDashPattern([max(0.01, float(value)) for value in dash])
        stroker.setDashOffset(float(evaluate_source_param(
            params,
            "dash_offset",
            time_ms,
            0.0,
        )))
    return stroker.createStroke(path)


def _mesh_key(path: QPainterPath, params: Mapping[str, Any], time_ms: float) -> str:
    polygons = [
        [[round(point.x(), 4), round(point.y(), 4)] for point in polygon]
        for polygon in path.toSubpathPolygons()
    ]
    payload = {
        "polygons": polygons,
        "fill_rule": int(path.fillRule().value),
        "fill": evaluate_source_param(params, "fill", time_ms, "#3f8fba"),
        "gradient": evaluate_source_param(params, "gradient", time_ms, None),
        "stroke": evaluate_source_param(params, "stroke", time_ms, "#20242b"),
        "stroke_width": evaluate_source_param(params, "stroke_width", time_ms, 2.0),
        "cap": evaluate_source_param(params, "cap", time_ms, "square"),
        "join": evaluate_source_param(params, "join", time_ms, "miter"),
        "dash": evaluate_source_param(params, "dash", time_ms, []),
        "dash_offset": evaluate_source_param(params, "dash_offset", time_ms, 0.0),
        "stroke_gradient": evaluate_source_param(
            params,
            "stroke_gradient",
            time_ms,
            None,
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)
    return sha256(encoded.encode("ascii")).hexdigest()


def _append_colored_triangles(
    output: list[float],
    points: list[tuple[float, float]],
    color_for_point,
) -> None:
    for x, y in points:
        output.extend((x, y, *color_for_point(x, y)))


def _repeat_matrix(width: float, height: float, instance: Mapping[str, Any]) -> tuple[float, ...]:
    translate = list(instance.get("translate") or [0.0, 0.0])
    scale = list(instance.get("scale") or [1.0, 1.0])
    angle = radians(float(instance.get("rotation", 0.0) or 0.0))
    cosine, sine = cos(angle), sin(angle)
    a, b = cosine * float(scale[0]), sine * float(scale[0])
    c, d = -sine * float(scale[1]), cosine * float(scale[1])
    center_x, center_y = width * 0.5, height * 0.5
    tx = center_x + float(translate[0]) - a * center_x - c * center_y
    ty = center_y + float(translate[1]) - b * center_x - d * center_y
    return a, b, c, d, tx, ty


def build_vector_gpu_packet(layer: MotionLayer, time_ms: float = 0.0) -> tuple[VectorGpuPacket | None, str]:
    if layer.layer_type != "shape" or layer.source.kind != "shape":
        return None, "non_vector_layer"
    if layer.effects or layer.masks:
        return None, "layer_effect_or_mask"
    params = layer.source.params
    taper = evaluate_source_param(params, "stroke_taper", time_ms, None)
    if isinstance(taper, Mapping) and taper and (
        abs(float(taper.get("start", 1.0) or 0.0) - 1.0) > 1e-6
        or abs(float(taper.get("end", 1.0) or 0.0) - 1.0) > 1e-6
        or bool(taper.get("profile"))
    ):
        return None, "variable_width_stroke"
    gradient = evaluate_source_param(params, "gradient", time_ms, None)
    if isinstance(gradient, Mapping) and str(gradient.get("type") or "linear").lower() == "radial":
        return None, "radial_gradient"
    stroke_gradient = evaluate_source_param(
        params,
        "stroke_gradient",
        time_ms,
        None,
    )
    if (
        isinstance(stroke_gradient, Mapping)
        and str(stroke_gradient.get("type") or "linear").lower() == "radial"
    ):
        return None, "radial_stroke_gradient"
    path = build_vector_painter_path(params, time_ms)
    if path.isEmpty():
        return None, "empty_path"
    key = _mesh_key(path, params, time_ms)
    mesh = VECTOR_GPU_MESH_CACHE.get(key)
    width = max(1.0, float(evaluate_source_param(params, "width", time_ms, 400.0)))
    height = max(1.0, float(evaluate_source_param(params, "height", time_ms, 220.0)))
    if mesh is None:
        vertices: list[float] = []
        trim = evaluate_source_param(params, "trim", time_ms, {})
        partial_trim = isinstance(trim, Mapping) and (
            float(trim.get("start", 0.0) or 0.0) > 0.0
            or float(trim.get("end", 1.0) if trim.get("end", 1.0) is not None else 1.0) < 1.0
            or float(trim.get("offset", 0.0) or 0.0) != 0.0
        )
        fill = _color(evaluate_source_param(params, "fill", time_ms, "#3f8fba"), "#3f8fba")
        if not partial_trim and fill.alpha() > 0:
            fill_triangles = _tessellate(path)
            if not fill_triangles:
                return None, "fill_tessellation_failed"
            _append_colored_triangles(
                vertices,
                fill_triangles,
                lambda x, y: _gradient_color(gradient, fill, x, y, width, height),
            )
        stroke = _color(evaluate_source_param(params, "stroke", time_ms, "#20242b"), "#20242b")
        if stroke.alpha() > 0:
            stroke_triangles = _tessellate(_stroke_path(path, params, time_ms))
            if stroke_triangles:
                stroke_gradient = evaluate_source_param(
                    params,
                    "stroke_gradient",
                    time_ms,
                    None,
                )
                _append_colored_triangles(
                    vertices,
                    stroke_triangles,
                    lambda x, y: _gradient_color(
                        stroke_gradient,
                        stroke,
                        x,
                        y,
                        width,
                        height,
                    ),
                )
        if not vertices:
            return None, "empty_mesh"
        mesh = VECTOR_GPU_MESH_CACHE.put(VectorGpuMesh(key, tuple(vertices), len(vertices) // 18))
    repeater = evaluate_source_param(params, "repeater", time_ms, {})
    rows = repeater_instances(repeater if isinstance(repeater, Mapping) else {})
    instances = tuple(
        VectorGpuInstance(_repeat_matrix(width, height, row), float(row.get("opacity", 1.0)))
        for row in rows
    )
    return VectorGpuPacket(mesh, instances, width, height), ""
