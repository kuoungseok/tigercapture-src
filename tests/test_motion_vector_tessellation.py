from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.adapters.shape import render_shape
from app.motion_designer.schema import MotionLayer, SourceRef
from app.motion_designer.vector_tessellation import (
    VECTOR_TESSELLATION_CACHE, build_vector_painter_path,
)
from app.motion_designer.vector_gpu import VECTOR_GPU_MESH_CACHE, build_vector_gpu_packet
from app.motion_designer.vector_gpu_renderer import MotionVectorGpuRenderer
from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.schema import MotionComposition


def _rect(left: float, top: float, right: float, bottom: float) -> dict:
    return {"closed": True, "points": [
        {"position": [left, top]}, {"position": [right, top]},
        {"position": [right, bottom]}, {"position": [left, bottom]},
    ]}


def test_tessellation_cache_and_boolean_operations() -> None:
    QApplication.instance() or QApplication([])
    VECTOR_TESSELLATION_CACHE.clear()
    params = {
        "width": 160, "height": 100, "shape": "path", "path": _rect(0, 0, 100, 100),
        "boolean": {"operation": "intersect", "paths": [_rect(50, 0, 150, 100)]},
    }
    first = build_vector_painter_path(params)
    second = build_vector_painter_path(params)
    assert first == second
    assert VECTOR_TESSELLATION_CACHE.misses == 1
    assert VECTOR_TESSELLATION_CACHE.hits == 1
    assert not first.contains(QPointF(25, 50))
    assert first.contains(QPointF(75, 50))
    assert not first.contains(QPointF(125, 50))


def test_trim_and_repeater_render_on_shared_shape_source() -> None:
    QApplication.instance() or QApplication([])
    line_path = {"closed": False, "points": [
        {"position": [10, 20]}, {"position": [30, 20]},
    ]}
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 120, "height": 40, "shape": "path", "path": line_path,
        "fill": "#00000000", "stroke": "#ffffff", "stroke_width": 4,
        "cap": "round", "repeater": {"count": 3, "offset": [30, 0]},
    }))
    image = render_shape(layer, 0).convertToFormat(QImage.Format_RGBA8888)
    assert image.pixelColor(10, 20).alpha() > 200
    assert image.pixelColor(40, 20).alpha() > 200
    assert image.pixelColor(70, 20).alpha() > 200
    layer.source.params["trim"] = {"start": 0.0, "end": .5}
    trimmed = render_shape(layer, 0).convertToFormat(QImage.Format_RGBA8888)
    assert trimmed.pixelColor(10, 20).alpha() > 200
    assert trimmed.pixelColor(28, 20).alpha() == 0


def test_star_gradient_and_rounded_rectangle_preserve_existing_shape_rendering() -> None:
    QApplication.instance() or QApplication([])
    star = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 160, "height": 160, "shape": "star", "sides": 5,
        "inner_ratio": .45, "stroke_width": 0,
        "gradient": {"type": "linear", "start": [0, 0], "end": [1, 0], "stops": [
            {"position": 0, "color": "#ff0000"}, {"position": 1, "color": "#0000ff"},
        ]},
    }))
    image = render_shape(star, 0)
    assert image.pixelColor(80, 80).alpha() > 200
    rounded = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 100, "height": 60, "shape": "rectangle", "radius": 18,
        "fill": "#00ff00", "stroke_width": 0,
    }))
    rounded_image = render_shape(rounded, 0)
    assert rounded_image.pixelColor(50, 30).green() > 200
    assert rounded_image.pixelColor(1, 1).alpha() == 0


def _triangle_contains(point: tuple[float, float], triangle: list[tuple[float, float]]) -> bool:
    def cross(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    values = [cross(triangle[index], triangle[(index + 1) % 3], point) for index in range(3)]
    return not (any(value < -1e-6 for value in values) and any(value > 1e-6 for value in values))


def _mesh_contains(packet, point: tuple[float, float]) -> bool:
    rows = [
        (packet.mesh.vertices[index], packet.mesh.vertices[index + 1])
        for index in range(0, len(packet.mesh.vertices), 6)
    ]
    return any(_triangle_contains(point, rows[index:index + 3]) for index in range(0, len(rows), 3))


def test_gpu_mesh_cache_preserves_boolean_holes() -> None:
    QApplication.instance() or QApplication([])
    VECTOR_GPU_MESH_CACHE.clear()
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 100, "height": 100, "shape": "path", "path": _rect(0, 0, 100, 100),
        "fill": "#40a0c0", "stroke_width": 0,
        "boolean": {"operation": "subtract", "paths": [_rect(25, 25, 75, 75)]},
    }))
    first, reason = build_vector_gpu_packet(layer)
    second, second_reason = build_vector_gpu_packet(layer)
    assert reason == second_reason == ""
    assert first is not None and second is not None
    assert first.mesh == second.mesh
    assert VECTOR_GPU_MESH_CACHE.misses == 1
    assert VECTOR_GPU_MESH_CACHE.hits == 1
    assert _mesh_contains(first, (10, 10)) is True
    assert _mesh_contains(first, (50, 50)) is False


def test_gpu_vector_packets_are_preview_opt_in_and_keep_painter_parity() -> None:
    QApplication.instance() or QApplication([])
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 100, "height": 60, "shape": "rectangle",
        "fill": "#2080a0", "stroke": "#102030", "stroke_width": 3,
    }), out_ms=1000)
    layer.transform.position.default = [60, 40]
    composition = MotionComposition(width=120, height=80, duration_ms=1000, layers=[layer])
    export_graph = build_render_graph(composition, 0)
    preview_graph = build_render_graph(composition, 0, include_vector_gpu=True)
    assert export_graph.nodes[0].vector_gpu_packet is None
    assert export_graph.diagnostics["vector_gpu_requested"] is False
    assert preview_graph.nodes[0].vector_gpu_packet is not None
    assert preview_graph.nodes[0].image is None
    assert preview_graph.diagnostics["vector_gpu_packet_count"] == 1
    assert MotionVectorGpuRenderer.can_draw(preview_graph) == (True, "")
    assert render_graph_image(export_graph) == render_graph_image(preview_graph)
    assert preview_graph.nodes[0].image is not None


def test_radial_gradient_reports_explicit_gpu_fallback() -> None:
    QApplication.instance() or QApplication([])
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 100, "height": 60, "shape": "rectangle", "fill": "#ffffff",
        "stroke_width": 0,
        "gradient": {"type": "radial", "stops": [[0, "#ffffff"], [1, "#000000"]]},
    }), out_ms=1000)
    composition = MotionComposition(width=120, height=80, duration_ms=1000, layers=[layer])
    graph = build_render_graph(composition, 0, include_vector_gpu=True)
    assert graph.nodes[0].vector_gpu_packet is None
    assert graph.nodes[0].vector_gpu_reason == "radial_gradient"
    assert MotionVectorGpuRenderer.can_draw(graph) == (False, "radial_gradient")
