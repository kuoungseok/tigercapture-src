from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
import pytest

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.schema import AnimatedProperty, MotionComposition, MotionEffectRef, MotionLayer, MotionMaskRef, SourceRef


def _composition() -> MotionComposition:
    layer = MotionLayer(
        name="Red",
        layer_type="shape",
        source=SourceRef(kind="shape", params={"width": 80, "height": 60, "fill": "#ff0000", "stroke_width": 0}),
        out_ms=1000,
        blend_mode="normal",
    )
    layer.transform.position.default = [100, 50]
    layer.transform.opacity.default = .5
    return MotionComposition(width=200, height=100, duration_ms=1000, fps=2, layers=[layer])


def _app():
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def test_premultiplied_rgba_and_revision_cache(tmp_path: Path) -> None:
    app = _app()
    composition = _composition()
    renderer = MotionExportRenderer()
    rgba = renderer.render_rgba_array(composition, 0)
    pixel = rgba[50, 100]
    assert 110 <= int(pixel[3]) <= 140
    assert int(pixel[0]) <= int(pixel[3]) + 1
    assert int(pixel[1]) == 0
    path = renderer.save_png(composition, 0, tmp_path / "alpha.png")
    assert path.is_file()
    cached_red = renderer.render_rgba_array(composition, 0)[50, 100].copy()
    composition.layers[0].source.params["fill"] = "#00ff00"
    composition.revision += 1
    revised_green = renderer.render_rgba_array(composition, 0)[50, 100]
    assert int(cached_red[0]) > 100 and int(cached_red[1]) == 0
    assert int(revised_green[1]) > 100 and int(revised_green[0]) == 0
    app.processEvents()


def test_export_renderer_registers_application_fonts(monkeypatch) -> None:
    _app()
    calls = 0

    def loaded() -> tuple[str, ...]:
        nonlocal calls
        calls += 1
        return ("Test Sans",)

    monkeypatch.setattr("app.font_fallback.load_application_ui_fonts", loaded)
    MotionExportRenderer()
    assert calls == 1


def test_png_sequence_and_mp4_smoke(tmp_path: Path) -> None:
    app = _app()
    composition = _composition()
    composition.width, composition.height = 64, 64
    composition.duration_ms = 500
    composition.layers[0].transform.position.default = [32, 32]
    renderer = MotionExportRenderer()
    frames = renderer.export_png_sequence(composition, tmp_path / "frames", fps=2)
    assert len(frames) == 1 and frames[0].is_file()
    mp4 = renderer.export_mp4(composition, tmp_path / "motion.mp4", fps=2)
    assert mp4.is_file() and mp4.stat().st_size > 0
    app.processEvents()


def test_anchor_and_alpha_mask_affect_shared_render_graph() -> None:
    app = _app()
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 80, "height": 60, "fill": "#00ff00", "stroke_width": 0}), out_ms=1000)
    layer.transform.position.default = [0, 0]
    layer.transform.anchor.default = [0, 0]
    layer.masks.append(MotionMaskRef(kind="rectangle", params={
        "x": AnimatedProperty(default=0), "y": AnimatedProperty(default=0),
        "width": AnimatedProperty(default=40), "height": AnimatedProperty(default=60),
    }))
    composition = MotionComposition(width=100, height=80, duration_ms=1000, layers=[layer])
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    assert rgba[10, 10, 3] > 200
    assert rgba[10, 60, 3] == 0
    app.processEvents()


def test_animated_layer_effect_changes_shared_render_output() -> None:
    app = _app()
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 60, "height": 40, "fill": "#804020", "stroke_width": 0}), out_ms=1000)
    layer.transform.position.default = [40, 30]
    layer.effects.append(MotionEffectRef(kind="saturation", params={
        "amount": AnimatedProperty(default=0.0),
    }))
    composition = MotionComposition(width=80, height=60, duration_ms=1000, layers=[layer])
    pixel = MotionExportRenderer().render_rgba_array(composition, 0)[30, 40]
    assert abs(int(pixel[0]) - int(pixel[1])) <= 2
    assert abs(int(pixel[1]) - int(pixel[2])) <= 2
    app.processEvents()


def test_adjustment_layer_and_track_matte_are_composited_in_layer_order() -> None:
    app = _app()
    content = MotionLayer(name="Content", layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 80, "height": 60, "fill": "#804020", "stroke_width": 0}), out_ms=1000)
    content.transform.position.default = [40, 30]
    matte = MotionLayer(name="Matte", layer_type="shape", source=SourceRef(kind="shape", params={
        "width": 40, "height": 60, "fill": "#ffffff", "stroke_width": 0}), out_ms=1000)
    matte.transform.position.default = [20, 30]
    content.metadata.update({"matte_layer_id": matte.id, "matte_mode": "alpha"})
    adjustment = MotionLayer(name="Grade", layer_type="adjustment", out_ms=1000)
    adjustment.effects.append(MotionEffectRef(kind="saturation", params={
        "amount": AnimatedProperty(default=0.0),
    }))
    composition = MotionComposition(width=80, height=60, duration_ms=1000,
                                    layers=[content, matte, adjustment])
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    visible = rgba[30, 15]
    clipped = rgba[30, 65]
    assert visible[3] > 200
    assert abs(int(visible[0]) - int(visible[1])) <= 2
    assert abs(int(visible[1]) - int(visible[2])) <= 2
    assert clipped[3] == 0
    app.processEvents()


def test_normal_layers_do_not_allocate_full_composition_surfaces(monkeypatch) -> None:
    app = _app()
    import app.motion_designer.render_graph as render_graph

    calls = 0
    original = render_graph._node_surface

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(render_graph, "_node_surface", counted)
    MotionExportRenderer().render_frame(_composition(), 0)
    assert calls == 0
    app.processEvents()
