from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.glass_material import (
    GLASS_CONTRACT,
    glass_effect,
    make_glass_effect,
)
from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _shape(name: str, color: str, width: int, height: int, x: float, y: float) -> MotionLayer:
    layer = MotionLayer(
        name=name,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": width,
            "height": height,
            "fill": color,
            "stroke_width": 0,
        }),
        out_ms=3000,
    )
    layer.transform.position.default = [x, y]
    return layer


def _composition() -> MotionComposition:
    left = _shape("Left", "#e44c4c", 80, 90, 40, 45)
    right = _shape("Right", "#3d71da", 80, 90, 120, 45)
    glass = _shape("Glass", "#ffffff", 100, 58, 80, 45)
    glass.effects.append(make_glass_effect({
        "blur_radius": 8.0,
        "refraction": 6.0,
        "dispersion": 1.2,
        "driver_x": 1.5,
    }, preset="glossy"))
    return MotionComposition(
        width=160,
        height=90,
        duration_ms=3000,
        fps=30,
        layers=[left, right, glass],
    )


def test_glass_contract_round_trips_as_one_motion_effect() -> None:
    effect = make_glass_effect({"blur_radius": 12.0}, preset="frosted")
    assert glass_effect([effect]) is effect
    assert effect.metadata["contract"] == GLASS_CONTRACT
    assert effect.metadata["preset"] == "frosted"
    assert effect.params["blur_radius"].default == 12.0


def test_glass_reads_backdrop_and_preserves_outside_pixels() -> None:
    _app()
    composition = _composition()
    rendered = MotionExportRenderer().render_frame(composition, 700, use_cache=False)
    assert rendered.pixelColor(80, 45) != QImage(1, 1, QImage.Format_RGBA8888).pixelColor(0, 0)
    assert rendered.pixelColor(5, 5).red() > rendered.pixelColor(5, 5).blue()
    assert rendered.pixelColor(155, 5).blue() > rendered.pixelColor(155, 5).red()
    center = rendered.pixelColor(80, 45)
    assert center.red() > 30 and center.blue() > 30


def test_glass_preview_export_pixel_parity() -> None:
    _app()
    composition = _composition()
    preview_graph = build_render_graph(
        composition,
        825,
        include_vector_gpu=True,
        render_quality="preview",
        output_size=(160, 90),
    )
    assert preview_graph.nodes[-1].vector_gpu_reason == "backdrop_glass_requires_raster"
    preview = render_graph_image(preview_graph)
    exported = MotionExportRenderer().render_frame(
        composition,
        825,
        width=160,
        height=90,
        use_cache=False,
    )
    assert preview == exported


def test_glass_quality_selects_deterministic_blur_pyramid() -> None:
    from app.motion_designer.glass_renderer import render_glass_surface

    _app()
    backdrop = QImage(1200, 600, QImage.Format_RGBA8888_Premultiplied)
    backdrop.fill(QColor("#163c61"))
    painter = QPainter(backdrop)
    for x in range(0, 1200, 32):
        painter.fillRect(x, 0, 16, 600, QColor("#e8a94b"))
    painter.end()
    mask = QImage(1200, 600, QImage.Format_RGBA8888_Premultiplied)
    mask.fill(QColor("#ffffff"))
    effect = make_glass_effect({"blur_radius": 18.0}, preset="frosted")
    effect.metadata["quality"] = "draft"
    draft_a = render_glass_surface(backdrop, mask, effect, 500)
    draft_b = render_glass_surface(backdrop, mask, effect, 500)
    effect.metadata["quality"] = "final"
    final = render_glass_surface(backdrop, mask, effect, 500)
    assert draft_a == draft_b
    assert draft_a != final


def test_overlapping_glass_layers_composite_in_order() -> None:
    _app()
    composition = _composition()
    renderer = MotionExportRenderer()
    one = renderer.render_frame(composition, 900, use_cache=False)
    second = _shape("Glass 2", "#ffffff", 74, 42, 96, 48)
    second.effects.append(make_glass_effect({
        "blur_radius": 14.0,
        "refraction": 8.0,
        "tint": "#ffb7dc",
        "tint_strength": 0.3,
    }, preset="tinted"))
    composition.layers.append(second)
    composition.revision += 1
    two = renderer.render_frame(composition, 900, use_cache=False)
    assert one != two
    assert two.pixelColor(96, 48).alpha() > 0
