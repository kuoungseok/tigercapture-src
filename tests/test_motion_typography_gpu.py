from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.typography_gpu import (
    TypographyGlyphAtlas,
    build_typography_gpu_packet,
)


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _text_layer(**params) -> MotionLayer:
    values = {
        "text": "TIGER TIGER",
        "width": 640,
        "height": 180,
        "font_family": "Segoe UI",
        "font_size": 92,
        "fill": "#f4f7fb",
        "padding": 12,
    }
    values.update(params)
    return MotionLayer(
        name="Title",
        layer_type="text",
        source=SourceRef(kind="typography", params=values),
        out_ms=2000,
    )


def _rgba(image: QImage) -> np.ndarray:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(converted.constBits(), dtype=np.uint8).reshape(
        converted.height(), converted.bytesPerLine(),
    )
    return rows[:, : converted.width() * 4].reshape(
        converted.height(), converted.width(), 4,
    ).copy()


def test_typography_gpu_packet_reuses_bounded_glyph_atlas() -> None:
    app = _app()
    atlas = TypographyGlyphAtlas(page_size=256, max_pages=2)
    layer = _text_layer()
    first, reason = build_typography_gpu_packet(layer, 0, atlas=atlas)
    assert reason == "" and first is not None
    assert len(first.instances) == 10
    assert 1 <= len(first.pages) <= 2
    revisions = {page.key: page.revision for page in first.pages}
    misses = atlas.cache_misses
    second, reason = build_typography_gpu_packet(layer, 500, atlas=atlas)
    assert reason == "" and second is not None
    assert {page.key: page.revision for page in second.pages} == revisions
    assert atlas.cache_misses == misses
    assert atlas.cache_hits >= 10
    assert atlas.diagnostics()["glyph_atlas_entries"] == len(set("TIGER"))
    app.processEvents()


def test_preview_graph_lazily_uses_typography_packet_and_keeps_painter_parity() -> None:
    app = _app()
    layer = _text_layer(text_animation={
        "in": "slide-up-in",
        "hold": "none",
        "out": "none",
        "in_duration_ms": 1000,
        "out_duration_ms": 0,
        "unit": "character",
        "stagger_ms": 30,
    })
    layer.transform.position.default = [640, 360]
    composition = MotionComposition(width=1280, height=720, duration_ms=2000, layers=[layer])
    gpu_graph = build_render_graph(composition, 700, include_vector_gpu=True)
    assert gpu_graph.nodes[0].typography_gpu_packet is not None
    assert gpu_graph.nodes[0].image is None
    assert gpu_graph.diagnostics["typography_gpu_packet_count"] == 1
    gpu_fallback = _rgba(render_graph_image(gpu_graph))
    painter = _rgba(render_graph_image(build_render_graph(composition, 700)))
    assert np.array_equal(gpu_fallback, painter)
    app.processEvents()


def test_typography_gpu_reports_explicit_fallback_for_painter_only_styles() -> None:
    app = _app()
    stroke_packet, stroke_reason = build_typography_gpu_packet(_text_layer(stroke_width=2), 0)
    shadow_packet, shadow_reason = build_typography_gpu_packet(
        _text_layer(shadow_color="#88000000"), 0,
    )
    background_packet, background_reason = build_typography_gpu_packet(
        _text_layer(background_color="#22272e"), 0,
    )
    assert stroke_packet is None and stroke_reason == "typography_stroke"
    assert shadow_packet is None and shadow_reason == "typography_shadow"
    assert background_packet is None and background_reason == "typography_background"
    app.processEvents()


def test_typography_gpu_falls_back_instead_of_dropping_glyphs_when_atlas_is_full() -> None:
    app = _app()
    atlas = TypographyGlyphAtlas(page_size=128, max_pages=1)
    packet, reason = build_typography_gpu_packet(
        _text_layer(text="ABCDEFGHIJKLMN", font_size=104),
        0,
        atlas=atlas,
    )
    assert packet is None
    assert reason == "glyph_atlas_capacity"
    app.processEvents()
