from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QColor, QImage, QPainter
import pytest

from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.effect_group import set_effect_group_scope
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.typography_gpu_renderer import MotionTypographyGpuRenderer
from app.motion_designer.vector_gpu_renderer import MotionVectorGpuRenderer
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


def test_adjustment_layer_can_target_selected_lower_layers_only() -> None:
    app = _app()
    selected = MotionLayer(
        id="selected",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 30, "height": 30, "fill": "#ff2000", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    selected.transform.position.default = [20, 20]
    untouched = MotionLayer(
        id="untouched",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 30, "height": 30, "fill": "#0040ff", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    untouched.transform.position.default = [60, 20]
    adjustment = MotionLayer(
        id="grade",
        layer_type="adjustment",
        effects=[MotionEffectRef(kind="saturation", params={
            "amount": AnimatedProperty(default=0.0),
        })],
        metadata={
            "adjustment_scope": {
                "mode": "selected_layers_below",
                "layer_ids": [selected.id, "missing", "grade"],
            },
        },
        out_ms=1000,
    )
    composition = MotionComposition(
        width=80,
        height=40,
        duration_ms=1000,
        layers=[selected, untouched, adjustment],
    )
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    left = rgba[20, 20]
    right = rgba[20, 60]
    assert max(int(left[0]), int(left[1]), int(left[2])) - min(
        int(left[0]), int(left[1]), int(left[2])
    ) <= 2
    assert int(right[2]) > int(right[0]) + 100
    app.processEvents()


def test_effect_group_applies_stack_only_to_selected_descendants() -> None:
    app = _app()
    group = MotionLayer(id="group", name="Effect Group", layer_type="group", out_ms=1000)
    group.effects = [MotionEffectRef(kind="saturation", params={
        "amount": AnimatedProperty(default=0.0),
    })]
    selected = MotionLayer(
        id="selected_child",
        parent_id=group.id,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 24, "height": 24, "fill": "#ff2000", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    selected.transform.position.default = [16, 16]
    other_child = MotionLayer(
        id="other_child",
        parent_id=group.id,
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 24, "height": 24, "fill": "#20ff00", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    other_child.transform.position.default = [48, 16]
    outside = MotionLayer(
        id="outside",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 24, "height": 24, "fill": "#2040ff", "stroke_width": 0,
        }),
        out_ms=1000,
    )
    outside.transform.position.default = [80, 16]
    composition = MotionComposition(
        width=96,
        height=32,
        duration_ms=1000,
        layers=[selected, other_child, outside, group],
    )
    scope = set_effect_group_scope(
        composition,
        group,
        mode="selected_descendants",
        layer_ids=[selected.id, outside.id, "missing"],
    )
    assert scope["layer_ids"] == [selected.id]
    rgba = MotionExportRenderer().render_rgba_array(composition, 0)
    selected_pixel = rgba[16, 16]
    other_pixel = rgba[16, 48]
    outside_pixel = rgba[16, 80]
    assert max(map(int, selected_pixel[:3])) - min(map(int, selected_pixel[:3])) <= 2
    assert int(other_pixel[1]) > int(other_pixel[0]) + 100
    assert int(outside_pixel[2]) > int(outside_pixel[0]) + 100
    app.processEvents()


def test_light_noise_shadow_and_stylize_effects_are_deterministic() -> None:
    _app()
    source = QImage(64, 64, QImage.Format_RGBA8888_Premultiplied)
    source.fill(QColor(0, 0, 0, 0))
    painter = QPainter(source)
    painter.fillRect(16, 16, 32, 32, QColor("#506070"))
    painter.end()

    def pixels(image: QImage) -> np.ndarray:
        straight = image.convertToFormat(QImage.Format_RGBA8888)
        rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
            straight.height(), straight.bytesPerLine(),
        )
        return rows[:, : straight.width() * 4].reshape(
            straight.height(), straight.width(), 4,
        ).copy()

    shadow = apply_effects(source, [MotionEffectRef(kind="drop_shadow", params={
        "offset_x": AnimatedProperty(default=8.0),
        "offset_y": AnimatedProperty(default=8.0),
        "radius": AnimatedProperty(default=3.0),
        "opacity": AnimatedProperty(default=1.0),
        "color": AnimatedProperty(default="#101820"),
    })], 0)
    assert pixels(shadow)[52, 52, 3] > 0

    sweep = apply_effects(source, [MotionEffectRef(kind="light_sweep", params={
        "center_x": AnimatedProperty(default=0.5),
        "center_y": AnimatedProperty(default=0.5),
        "angle": AnimatedProperty(default=0.0),
        "width": AnimatedProperty(default=0.2),
        "softness": AnimatedProperty(default=0.5),
        "intensity": AnimatedProperty(default=1.0),
        "color": AnimatedProperty(default="#ffffff"),
    })], 0)
    assert int(pixels(sweep)[32, 32, :3].max()) > int(pixels(source)[32, 32, :3].max())

    noise_effect = MotionEffectRef(kind="fractal_noise", params={
        "amount": AnimatedProperty(default=0.8),
        "scale": AnimatedProperty(default=16.0),
        "octaves": AnimatedProperty(default=3.0),
        "contrast": AnimatedProperty(default=1.2),
        "evolution": AnimatedProperty(default=0.0),
        "speed": AnimatedProperty(default=1.0),
        "seed": AnimatedProperty(default=42.0),
    })
    noise_a = pixels(apply_effects(source, [noise_effect], 250))
    noise_b = pixels(apply_effects(source, [noise_effect], 250))
    noise_c = pixels(apply_effects(source, [noise_effect], 750))
    assert np.array_equal(noise_a, noise_b)
    assert not np.array_equal(noise_a, noise_c)

    gradient = QImage(64, 8, QImage.Format_RGBA8888_Premultiplied)
    gradient_pixels = np.zeros((8, 64, 4), dtype=np.uint8)
    gradient_pixels[..., :3] = np.arange(64, dtype=np.uint8)[None, :, None] * 4
    gradient_pixels[..., 3] = 255
    gradient = QImage(
        gradient_pixels.data,
        64,
        8,
        gradient_pixels.strides[0],
        QImage.Format_RGBA8888,
    ).copy()
    posterized = pixels(apply_effects(
        gradient,
        [MotionEffectRef(kind="posterize", params={
            "levels": AnimatedProperty(default=4.0),
            "amount": AnimatedProperty(default=1.0),
        })],
        0,
    ))
    assert len(np.unique(posterized[..., 0])) <= 4


def test_craft_style_is_deterministic_and_changes_over_time() -> None:
    from app.motion_designer.craft_style import make_craft_style_effect

    _app()
    source = QImage(96, 64, QImage.Format_RGBA8888_Premultiplied)
    source.fill(QColor("#78899a"))

    def pixels(image: QImage) -> np.ndarray:
        straight = image.convertToFormat(QImage.Format_RGBA8888)
        rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
            straight.height(), straight.bytesPerLine(),
        )
        return rows[:, : straight.width() * 4].reshape(
            straight.height(), straight.width(), 4,
        ).copy()

    effect = make_craft_style_effect(
        {"seed": 83, "grain_amount": 0.4, "weave_x": 3.0},
        preset="handmade",
    )
    first = pixels(apply_effects(source, [effect], 250))
    repeated = pixels(apply_effects(source, [effect], 250))
    later = pixels(apply_effects(source, [effect], 750))
    assert np.array_equal(first, repeated)
    assert not np.array_equal(first, later)
    assert np.all(first[..., 3] == 255)


def test_gpu_only_preview_backends_fall_back_when_effects_are_active() -> None:
    shape = MotionLayer(
        id="shape_effect",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 64, "height": 64, "fill": "#ffffff",
        }),
        effects=[MotionEffectRef(kind="light_sweep")],
        out_ms=1000,
    )
    shape_graph = build_render_graph(
        MotionComposition(width=64, height=64, duration_ms=1000, layers=[shape]),
        0,
        include_vector_gpu=True,
    )
    assert MotionVectorGpuRenderer.can_draw(shape_graph) == (
        False,
        "effects_require_raster",
    )

    text = MotionLayer(
        id="text_effect",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "FX", "width": 128, "height": 64,
        }),
        effects=[MotionEffectRef(kind="posterize")],
        out_ms=1000,
    )
    text_graph = build_render_graph(
        MotionComposition(width=128, height=64, duration_ms=1000, layers=[text]),
        0,
        include_vector_gpu=True,
    )
    assert MotionTypographyGpuRenderer.can_draw(text_graph) == (
        False,
        "effects_require_raster",
    )


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
