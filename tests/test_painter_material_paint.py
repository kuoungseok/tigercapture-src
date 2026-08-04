from __future__ import annotations

import os
import json
from pathlib import Path

import numpy as np


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_material_brush_capability_discloses_authored_nonphysical_model() -> None:
    from app.painter_material_paint import brush_material_capability

    compatible = brush_material_capability("bristle_oil")
    fallback = brush_material_capability("round")
    assert compatible["relief_model"] == "tiger_authored_stylized_relief_v1"
    assert compatible["coefficient_source"] == "authored_style_preset_not_measured_physical_media"
    assert compatible["physical_media_claim"] is False
    assert compatible["external_brush_parity_claim"] is False
    assert fallback["fallback"] == "stylized_reduced_relief"


def test_gaussian_blur_has_a_real_fallback_when_opencv_is_unavailable(monkeypatch) -> None:
    import sys

    from app.painter_material_paint import _blur, material_raster_backend_status

    monkeypatch.setitem(sys.modules, "cv2", None)
    before = material_raster_backend_status()
    source = np.zeros((17, 17), dtype=np.float32)
    source[8, 8] = 1.0
    blurred = _blur(source, 2.0)
    status = material_raster_backend_status()
    assert blurred.shape == source.shape
    assert blurred.dtype == np.float32
    assert 0.0 < float(blurred[8, 8]) < 1.0
    assert float(blurred[8, 7]) > 0.0
    assert status["backend"] == "pillow"
    assert status["fallback_count"] == before["fallback_count"] + 1
    assert "ModuleNotFoundError" in status["last_fallback_error"]
    assert "cv2" in status["last_fallback_error"]


def test_polyline_and_weighted_segment_have_deterministic_pillow_fallback(
    monkeypatch,
) -> None:
    import sys
    from app.painter_material_paint import (
        _draw_polyline,
        _draw_weighted_segment,
        material_raster_backend_status,
    )

    monkeypatch.setitem(sys.modules, "cv2", None)
    first = np.zeros((32, 32), dtype=np.float32)
    second = np.zeros_like(first)
    _draw_polyline(first, [(3, 4), (27, 25)], 5)
    _draw_polyline(second, [(3, 4), (27, 25)], 5)
    assert first.dtype == np.float32
    assert first.shape == (32, 32)
    assert np.array_equal(first, second)
    assert 0 < int(np.count_nonzero(first)) < first.size

    weighted = np.zeros_like(first)
    _draw_weighted_segment(weighted, (3, 4), (27, 25), 5, 0.25)
    assert weighted.dtype == np.float32
    assert weighted.shape == first.shape
    assert 0.0 < float(weighted.max()) <= 0.25
    assert np.array_equal(weighted > 0.0, first > 0.0)
    status = material_raster_backend_status()
    assert status["backend"] == "pillow"
    assert status["fallback_count"] >= 3
    assert "cv2" in status["last_fallback_error"].casefold()


def test_material_channels_are_authored_from_strokes() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import (
        material_paint_signature,
        rasterize_material_channels,
    )

    layer = PaintLayer(
        layer_id="material-1",
        name="Impasto",
        layer_type="material",
        material_settings={"thickness": 0.8, "roughness": 0.42},
    )
    stroke = Stroke(
        points=[(0.1, 0.7), (0.45, 0.25), (0.9, 0.55)],
        width_px=18.0,
        brush_style="bristle_oil",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=0.9,
        material_thickness=0.84,
        material_wetness=0.32,
        material_gloss=0.38,
        material_roughness=0.46,
    )

    channels = rasterize_material_channels([stroke], [layer], width=192, height=108)
    assert channels["active"] is True
    assert channels["stroke_count"] == 1
    assert channels["height"].shape == (108, 192)
    assert channels["normal"].shape == (108, 192, 3)
    assert channels["direction"].shape == (108, 192, 2)
    assert channels["soft_shadow"].shape == (108, 192)
    assert float(np.max(channels["height"])) > 0.0
    assert float(np.ptp(channels["normal"][..., 0])) > 0.0
    assert float(np.ptp(channels["roughness"])) > 0.0

    first = material_paint_signature([stroke], [layer], width=192, height=108)
    stroke.material_thickness = 0.22
    second = material_paint_signature([stroke], [layer], width=192, height=108)
    assert first != second


def test_negative_depth_excavates_and_plow_displaces_existing_relief() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("depth", "Depth", layer_type="material")
    common = {
        "width_px": 28,
        "brush_style": "palette_knife",
        "layer_id": layer.layer_id,
        "material_enabled": True,
        "material_load": 1.0,
        "material_thickness": 1.0,
        "brush_engine_version": 2,
        "point_pressure": [1.0, 1.0],
        "point_load": [1.0, 1.0],
    }
    negative = Stroke(
        points=[(0.15, 0.5), (0.85, 0.5)],
        material_negative_depth=True,
        **common,
    )
    carved = rasterize_material_channels([negative], [layer], width=180, height=120)
    assert float(np.min(carved["signed_height"])) < 0.0
    assert float(np.max(carved["excavation"])) > 0.0
    assert carved["negative_depth_supported"] is True

    under = Stroke(points=[(0.12, 0.5), (0.88, 0.5)], **common)
    no_plow = Stroke(points=[(0.5, 0.12), (0.5, 0.88)], material_plow=0.0, **common)
    full_plow = Stroke(points=[(0.5, 0.12), (0.5, 0.88)], material_plow=1.0, **common)
    flat = rasterize_material_channels([under, no_plow], [layer], width=180, height=120)
    displaced = rasterize_material_channels([under, full_plow], [layer], width=180, height=120)
    assert not np.array_equal(flat["signed_height"], displaced["signed_height"])
    assert displaced["plow_supported"] is True

    from app.painter_material_paint import merge_material_channels_into_generated

    merged = merge_material_channels_into_generated(
        {
            "maps": {
                "height": np.zeros((120, 180), dtype=np.float32),
                "normal": np.full((120, 180, 3), 0.5, dtype=np.float32),
                "roughness": np.full((120, 180), 0.7, dtype=np.float32),
                "ao": np.ones((120, 180), dtype=np.float32),
            }
        },
        carved,
    )
    assert merged["material_paint"]["height_encoding"] == "signed_neutral_0_5"
    occupied = carved["coverage"] > 0.0
    assert float(np.min(merged["maps"]["height"][occupied])) < 0.5


def test_material_channels_merge_with_texture_lab_maps() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import (
        merge_material_channels_into_generated,
        rasterize_material_channels,
    )

    layer = PaintLayer("m", "Material", layer_type="material")
    stroke = Stroke(
        points=[(0.2, 0.5), (0.8, 0.5)],
        width_px=12,
        layer_id="m",
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
    )
    channels = rasterize_material_channels([stroke], [layer], width=96, height=64)
    base = {
        "maps": {
            "height": np.zeros((64, 96), dtype=np.float32),
            "normal": np.full((64, 96, 3), 0.5, dtype=np.float32),
            "roughness": np.full((64, 96), 0.9, dtype=np.float32),
            "ao": np.ones((64, 96), dtype=np.float32),
        }
    }
    merged = merge_material_channels_into_generated(base, channels)
    assert merged["material_paint"]["native_channels"] is True
    assert merged["material_paint"]["stroke_count"] == 1
    assert float(np.max(merged["maps"]["height"])) > 0.0
    assert not np.array_equal(merged["maps"]["normal"], base["maps"]["normal"])


def test_oil_styles_generate_distinct_relief_profiles() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer(
        "oil",
        "Oil Relief",
        layer_type="material",
        material_settings={
            "load": 0.95,
            "thickness": 0.92,
            "wetness": 0.24,
            "gloss": 0.42,
            "roughness": 0.44,
        },
    )

    def render(style: str) -> np.ndarray:
        stroke = Stroke(
            points=[(0.1, 0.5), (0.9, 0.5)],
            width_px=34,
            brush_style=style,
            layer_id=layer.layer_id,
            material_enabled=True,
            material_load=0.95,
            material_thickness=0.92,
            material_wetness=0.24,
            material_gloss=0.42,
            material_roughness=0.44,
            brush_engine_version=2,
            bristle_count=14,
            brush_seed=1776,
            point_pressure=[0.9, 0.86],
            point_load=[1.0, 0.78],
        )
        return rasterize_material_channels(
            [stroke],
            [layer],
            width=240,
            height=120,
        )["height"]

    impasto = render("impasto_oil")
    knife = render("palette_knife")
    stipple = render("stipple_oil")

    assert not np.allclose(impasto, knife)
    assert not np.allclose(knife, stipple)
    assert not np.allclose(impasto, stipple)
    assert np.count_nonzero(stipple > 0.0) < np.count_nonzero(impasto > 0.0)
    assert float(np.percentile(knife[knife > 0.02], 25)) > 0.02


def test_palette_knife_relief_uses_pressure_load_tilt_and_shared_normal_stage() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("knife", "Knife", layer_type="material")

    def render(*, pressure: float, load: float, tilt_x: float) -> dict[str, object]:
        stroke = Stroke(
            points=[(0.18, 0.52), (0.50, 0.48), (0.82, 0.52)],
            width_px=34,
            brush_style="palette_knife",
            layer_id=layer.layer_id,
            material_enabled=True,
            material_load=1.0,
            material_thickness=0.92,
            point_pressure=[pressure] * 3,
            point_load=[load] * 3,
            point_tilt_x=[tilt_x] * 3,
            point_tilt_y=[0.0] * 3,
            point_rotation=[0.72] * 3,
            point_tangential_pressure=[0.25] * 3,
        )
        return rasterize_material_channels([stroke], [layer], width=220, height=120)

    light = render(pressure=0.25, load=0.35, tilt_x=0.0)
    loaded = render(pressure=0.95, load=1.0, tilt_x=0.0)
    tilted = render(pressure=0.95, load=1.0, tilt_x=0.75)
    assert float(np.sum(loaded["height"])) > float(np.sum(light["height"]))
    assert not np.allclose(loaded["height"], tilted["height"])
    assert float(np.ptp(loaded["normal"][..., 0])) > 0.0
    assert loaded["normal"].dtype == np.float32
    assert loaded["ao"].dtype == np.float32


def test_material_normal_respects_directx_and_opengl_output_conventions() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("format", "Format", layer_type="material")
    stroke = Stroke(
        points=[(0.2, 0.7), (0.48, 0.24), (0.84, 0.58)],
        width_px=30,
        brush_style="palette_knife",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
        point_pressure=[0.6, 1.0, 0.7],
        point_load=[1.0, 0.8, 0.6],
    )
    directx_channels = rasterize_material_channels(
        [stroke],
        [layer],
        width=160,
        height=100,
        surface_settings={"normal_format": "unreal_directx"},
    )
    opengl_channels = rasterize_material_channels(
        [stroke],
        [layer],
        width=160,
        height=100,
        surface_settings={"normal_format": "opengl"},
    )
    directx = directx_channels["normal"]
    opengl = opengl_channels["normal"]
    assert np.allclose(directx[..., 0], opengl[..., 0], atol=1.0e-6)
    assert np.allclose(directx[..., 1], 1.0 - opengl[..., 1], atol=1.0e-6)
    assert np.allclose(directx[..., 2], opengl[..., 2], atol=1.0e-6)
    assert np.allclose(
        directx_channels["shading"],
        opengl_channels["shading"],
        atol=1.0e-6,
    )


def test_artist_relief_shading_remains_readable_under_front_light() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("readable", "Readable", layer_type="material")
    stroke = Stroke(
        points=[(0.12, 0.68), (0.34, 0.26), (0.58, 0.64), (0.88, 0.34)],
        width_px=36,
        brush_style="impasto_oil",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=0.96,
        material_thickness=0.94,
        brush_engine_version=2,
        bristle_count=16,
        brush_seed=731,
        point_pressure=[0.55, 1.0, 0.72, 0.46],
        point_load=[1.0, 0.9, 0.7, 0.5],
    )
    channels = rasterize_material_channels(
        [stroke],
        [layer],
        width=220,
        height=130,
        light_elevation_deg=85.0,
    )
    occupied = channels["coverage"] > 0.0
    assert channels["shading_profile"] == "painter_artist_relief_readability_v1"
    assert float(np.ptp(channels["shading"][occupied])) > 0.0


def test_opaque_impasto_buries_underpaint_relief() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("oil", "Oil", layer_type="material")
    underpaint = Stroke(
        points=[(0.05, 0.5), (0.95, 0.5)],
        width_px=30,
        brush_style="palette_knife",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
        brush_engine_version=2,
        brush_seed=10,
    )
    overpaint = Stroke(
        points=[(0.5, 0.05), (0.5, 0.95)],
        width_px=34,
        brush_style="impasto_oil",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
        brush_engine_version=2,
        brush_seed=11,
        bristle_count=16,
    )
    under = rasterize_material_channels(
        [underpaint],
        [layer],
        width=180,
        height=140,
    )["height"]
    combined = rasterize_material_channels(
        [underpaint, overpaint],
        [layer],
        width=180,
        height=140,
    )["height"]
    crossing = (slice(63, 77), slice(82, 98))
    over_only = rasterize_material_channels(
        [overpaint],
        [layer],
        width=180,
        height=140,
    )["height"]
    assert float(np.mean(combined[crossing] - over_only[crossing])) < float(
        np.mean(under[crossing])
    ) * 0.45


def test_material_layer_ui_and_stroke_contract(tmp_path: Path) -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    layer = dialog._new_material_paint_layer("Oil Relief")
    dialog._set_material_settings(
        {"thickness": 0.91, "roughness": 0.37, "gloss": 0.46},
        layer_id=layer.layer_id,
    )
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=22,
        brush_style="impasto_oil",
        source_tool="pen",
    )
    dialog._on_stroke_added(stroke)
    app.processEvents()

    state = dialog.painter_action_state()
    active = next(row for row in state["layers"] if row["active"])
    assert active["layer_type"] == "material"
    assert active["material_settings"]["thickness"] == 0.91
    assert state["material_preview"]["enabled"] is True
    assert state["material_preview"]["stroke_count"] == 1
    saved_stroke = dialog.canvas.embedded_strokes()[-1]
    assert saved_stroke.material_enabled is True
    assert saved_stroke.brush_engine_version == 2
    assert len(saved_stroke.point_pressure) == len(saved_stroke.points)
    assert len(saved_stroke.point_load) == len(saved_stroke.points)
    assert saved_stroke.bristle_count >= 7
    assert saved_stroke.point_pressure == [1.0, 1.0]
    assert saved_stroke.material_thickness == 0.91
    assert saved_stroke.material_roughness == 0.37
    assert dialog._material_options_button.isVisible()
    pbr_settings = dialog._pbr_texture_settings_payload()
    assert pbr_settings["preview_parallax_enabled"] is True
    assert pbr_settings["preview_parallax_strength"] >= 0.70
    assert pbr_settings["preview_parallax_depth"] >= 0.05
    assert pbr_settings["preview_parallax_steps"] >= 28

    dialog.canvas.repaint()
    initial_preview = dict(dialog._material_preview_cache or {})
    initial_signature = initial_preview.get("signature")
    initial_image_key = initial_preview.get("image").cacheKey()
    initial_render_size = dialog.canvas.stable_render_size()
    initial_background_size = dialog._bg_label.pixmap().size()
    dialog._set_zoom_percent(200)
    app.processEvents()
    dialog.canvas.repaint()
    zoomed_preview = dict(dialog._material_preview_cache or {})
    assert dialog.canvas.stable_render_size() == initial_render_size
    assert zoomed_preview.get("signature") == initial_signature
    assert zoomed_preview.get("image").cacheKey() == initial_image_key
    assert dialog._bg_label.pixmap().size() == initial_background_size
    assert dialog._bg_label.width() > dialog._bg_label.pixmap().width()

    output = tmp_path / "material_preview.png"
    payload = dialog.preview_pbr_map_to_path(output, allow_cpu=True)
    assert output.exists()
    assert payload["painter_source"]["material_paint"]["native_channels"] is True
    export_dir = tmp_path / "maps"
    exported = dialog.export_pbr_maps_to_path(
        export_dir,
        maps=("height", "normal", "roughness", "ao"),
        packed=False,
        allow_cpu=True,
    )
    assert exported["material_paint"]["native_channels"] is True
    assert set(exported["files"]) == {"height", "normal", "roughness", "ao"}
    assert Path(exported["manifest_path"]).exists()
    assert exported["transaction"]["committed"] is True
    manifest = json.loads(Path(exported["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["output_dir"] == str(export_dir)
    assert all(str(export_dir) in path for path in manifest["files"].values())
    assert "tiger-stage" not in json.dumps(manifest)
    dialog.close()


def test_material_live_segment_matches_committed_v2_brush_contract() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_stylus import StylusSample

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._new_material_paint_layer("Live Material")
    dialog._pen_style = "palette_knife"
    dialog.canvas.set_pen_style("palette_knife")
    captured_live = []
    captured_final = []
    original_paint = dialog.canvas._paint_stroke
    dialog.canvas._paint_stroke = (
        lambda _painter, stroke, _w, _h, **_kwargs: captured_live.append(stroke)
    )
    dialog.canvas.stroke_added.connect(captured_final.append)
    sample = StylusSample(
        pressure=0.82,
        tilt_x=0.35,
        tilt_y=-0.2,
        rotation=0.68,
        tangential_pressure=0.2,
    )
    try:
        dialog.canvas._begin_current_stroke(QPointF(80.0, 120.0), sample)
        dialog.canvas._append_current_stroke_sample(QPointF(150.0, 135.0), sample)
        dialog.canvas._append_current_stroke_sample(QPointF(220.0, 105.0), sample)
        dialog.canvas._append_current_stroke_sample(QPointF(290.0, 150.0), sample)
        dialog.canvas._finish_current_stroke()
        app.processEvents()
    finally:
        dialog.canvas._paint_stroke = original_paint

    assert captured_live
    assert captured_final
    live = captured_live[-1]
    final = captured_final[-1]
    assert live.brush_engine_version == final.brush_engine_version == 2
    assert live.material_enabled is final.material_enabled is True
    assert live.brush_seed == final.brush_seed
    assert live.brush_style == final.brush_style == "palette_knife"
    assert live.points == final.points[-2:]
    assert live.point_pressure == final.point_pressure[-2:]
    assert live.point_load == final.point_load[-2:]
    assert live.brush_sample_offset == len(final.points) - 2
    assert live.brush_authored_stroke_start is False
    dialog.close()


def test_material_live_preview_pixels_match_committed_stroke() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas, PaintDialog, create_blank_paint_pixmap
    from app.painter_stylus import StylusSample

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    dialog.resize(1000, 720)
    dialog._new_material_paint_layer("Live Pixel Parity")
    dialog._pen_style = "bristle_oil"
    dialog.canvas.set_pen_style("bristle_oil")
    app.processEvents()

    sample = StylusSample(
        pressure=0.78,
        tilt_x=0.24,
        tilt_y=-0.18,
        rotation=0.61,
        tangential_pressure=0.12,
    )
    dialog.canvas._begin_current_stroke(QPointF(90.0, 140.0), sample)
    for point in (
        QPointF(150.0, 112.0),
        QPointF(225.0, 158.0),
        QPointF(310.0, 104.0),
        QPointF(390.0, 148.0),
    ):
        dialog.canvas._append_current_stroke_sample(point, sample)

    live = dialog.canvas._live_stroke_cache_image.copy()
    committed = []
    dialog.canvas.stroke_added.connect(committed.append)
    dialog.canvas._finish_current_stroke()
    assert committed

    final = QImage(live.size(), QImage.Format.Format_ARGB32_Premultiplied)
    final.fill(Qt.GlobalColor.transparent)
    painter = QPainter(final)
    try:
        DrawingCanvas._paint_stroke(
            painter,
            committed[-1],
            final.width(),
            final.height(),
        )
    finally:
        painter.end()

    assert live == final
    dialog.close()
