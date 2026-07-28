from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.glass_material import (
    GLASS_CONTRACT,
    glass_effect,
    make_glass_effect,
)
from app.motion_designer.glass_runtime import resolve_glass_driver
from app.motion_designer.render_graph import build_render_graph, render_graph_image
from app.motion_designer.preview_renderer import MotionPreviewWidget
from app.motion_designer.schema import (
    Keyframe,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.tiled_renderer import (
    render_graph_tiled,
    tiled_render_preflight,
)


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


def test_glass_preview_scaling_preserves_original_alpha_bounds() -> None:
    from app.motion_designer.glass_renderer import render_glass_surface

    _app()
    backdrop = QImage(1280, 720, QImage.Format_RGBA8888_Premultiplied)
    backdrop.fill(QColor("#24677f"))
    mask = QImage(1280, 720, QImage.Format_RGBA8888_Premultiplied)
    mask.fill(0)
    painter = QPainter(mask)
    painter.fillRect(270, 160, 740, 390, QColor("#ffffff"))
    painter.end()
    effect = make_glass_effect(
        {"blur_radius": 18.0, "refraction": 10.0},
        preset="liquid_cta",
    )
    effect.metadata["quality"] = "preview"

    rendered = render_glass_surface(backdrop, mask, effect, 750)

    assert rendered.pixelColor(269, 300).alpha() == 0
    assert rendered.pixelColor(270, 300).alpha() > 0
    assert rendered.pixelColor(1009, 300).alpha() > 0
    assert rendered.pixelColor(1010, 300).alpha() == 0


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


def test_glass_runtime_driver_is_ephemeral_and_clamped() -> None:
    effect = make_glass_effect(
        {"driver_x": 0.5, "driver_y": -0.25},
        preset="glossy",
    )
    effect.metadata["driver"] = {"source": "pointer", "strength": 2.0}
    before = (
        effect.params["driver_x"].default,
        effect.params["driver_y"].default,
        dict(effect.metadata["driver"]),
    )

    assert resolve_glass_driver(effect, {"pointer": (0.75, -0.5)}) == (
        2.0,
        -1.25,
    )
    assert resolve_glass_driver(effect, {"pointer": (99.0, -99.0)}) == (
        10.0,
        -10.0,
    )
    assert (
        effect.params["driver_x"].default,
        effect.params["driver_y"].default,
        dict(effect.metadata["driver"]),
    ) == before
    effect.params["driver_x"].keyframes = [
        Keyframe(time_ms=0, value=0.0),
        Keyframe(time_ms=1000, value=2.0),
    ]
    assert resolve_glass_driver(
        effect,
        {"pointer": (0.5, 0.0)},
        time_ms=500,
    )[0] == pytest.approx(2.0)
    effect.metadata["driver"]["source"] = "manual"
    assert resolve_glass_driver(
        effect,
        {"pointer": (10.0, 10.0)},
        time_ms=500,
    ) == pytest.approx((1.0, -0.25))


def test_render_graph_applies_runtime_driver_without_changing_document() -> None:
    _app()
    composition = _composition()
    effect = glass_effect(composition.layers[-1].effects)
    assert effect is not None
    effect.metadata["driver"] = {"source": "pointer", "strength": 2.0}
    revision = composition.revision
    default_x = effect.params["driver_x"].default

    still_graph = build_render_graph(
        composition,
        825,
        render_quality="preview",
        runtime_inputs={"pointer": (0.0, 0.0)},
    )
    moved_graph = build_render_graph(
        composition,
        825,
        render_quality="preview",
        runtime_inputs={"pointer": (1.0, -1.0)},
    )

    assert still_graph.nodes[-1].glass_driver_override == (1.5, 0.0)
    assert moved_graph.nodes[-1].glass_driver_override == (3.5, -2.0)
    assert render_graph_image(still_graph) != render_graph_image(moved_graph)
    assert composition.revision == revision
    assert effect.params["driver_x"].default == default_x


def test_preview_pointer_driver_uses_composition_viewport_coordinates() -> None:
    _app()
    preview = MotionPreviewWidget()
    preview.resize(400, 200)
    preview.set_composition(_composition())
    preview.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(378.0, 100.0),
            QPointF(378.0, 100.0),
            QPointF(378.0, 100.0),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    pointer = preview.runtime_glass_inputs()["pointer"]
    assert pointer[0] == pytest.approx(1.0, abs=0.02)
    assert pointer[1] == pytest.approx(0.0, abs=0.02)
    preview.deleteLater()


def test_glass_viewport_raster_preserves_scaled_visual_contract() -> None:
    import numpy as np

    _app()
    graph = build_render_graph(
        _composition(),
        825,
        render_quality="preview",
    )
    full = render_graph_image(graph)
    reduced = render_graph_image(graph, output_size=(80, 45))
    reference = full.scaled(
        80,
        45,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).convertToFormat(QImage.Format_RGBA8888)
    actual = reduced.convertToFormat(QImage.Format_RGBA8888)

    def rgba(image: QImage) -> np.ndarray:
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(),
            image.bytesPerLine(),
        )
        return rows[:, : image.width() * 4].reshape(
            image.height(),
            image.width(),
            4,
        )

    difference = np.abs(
        rgba(reference).astype(np.int16) - rgba(actual).astype(np.int16)
    )
    interior = difference[2:-2, 2:-2]
    assert reduced.size().toTuple() == (80, 45)
    assert float(interior[..., :3].mean()) < 5.0
    assert float(interior[..., 3].mean()) < 1.0


def test_preview_viewport_raster_is_limited_to_glass_only_effect_graphs() -> None:
    _app()
    preview = MotionPreviewWidget()
    composition = _composition()
    graph = build_render_graph(composition, 500)
    assert preview._preview_raster_size(
        graph,
        QRectF(0.0, 0.0, 716.0, 403.0),
    ) == (716, 403)

    composition.layers[0].effects.append(
        MotionEffectRef(kind="brightness_contrast")
    )
    mixed_graph = build_render_graph(composition, 500)
    assert preview._preview_raster_size(
        mixed_graph,
        QRectF(0.0, 0.0, 716.0, 403.0),
    ) is None
    preview.deleteLater()


def test_glass_tiled_render_is_seam_safe_and_deterministic() -> None:
    import numpy as np

    _app()
    composition = _composition()
    graph = build_render_graph(
        composition,
        825,
        render_quality="export",
    )
    full = render_graph_image(graph).convertToFormat(QImage.Format_RGBA8888)
    tiled, report = render_graph_tiled(
        graph,
        tile_size=64,
    )
    tiled = tiled.convertToFormat(QImage.Format_RGBA8888)
    repeated, repeated_report = render_graph_tiled(
        graph,
        tile_size=64,
    )
    repeated = repeated.convertToFormat(QImage.Format_RGBA8888)

    def rgba(image: QImage) -> np.ndarray:
        rows = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(),
            image.bytesPerLine(),
        )
        return rows[:, : image.width() * 4].reshape(
            image.height(),
            image.width(),
            4,
        )

    difference = np.abs(
        rgba(full).astype(np.int16) - rgba(tiled).astype(np.int16)
    )
    assert report["ok"] is True
    assert report["tile_count"] == 6
    assert report["full_frame_intermediate_avoided"] is True
    assert float(difference.mean()) < 0.2
    assert tiled == repeated
    assert report == repeated_report


def test_export_renderer_honors_explicit_tiled_glass_policy() -> None:
    _app()
    composition = _composition()
    composition.metadata["tiled_export"] = {
        "contract": "tigerstudio.motion.tiled_export.v1",
        "enabled": True,
        "tile_size": 64,
    }
    composition.revision += 1
    renderer = MotionExportRenderer()
    image = renderer.render_frame(
        composition,
        825,
        use_cache=False,
    )
    assert not image.isNull()
    assert renderer.last_tiled_report["ok"] is True
    assert renderer.last_tiled_report["tile_size"] == 64


def test_tiled_glass_preflight_rejects_unbounded_full_frame_effects() -> None:
    composition = _composition()
    composition.layers[0].effects.append(
        MotionEffectRef(kind="brightness_contrast")
    )
    report = tiled_render_preflight(build_render_graph(composition, 500))
    assert report["ok"] is False
    assert "effect_requires_full_frame:brightness_contrast" in report["issues"]
