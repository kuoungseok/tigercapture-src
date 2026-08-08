from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_bristle_engine_discloses_authored_nonphysical_model() -> None:
    from app.painter_brush_engine_v2 import BRISTLE_ENGINE_MODEL_CONTRACT

    assert BRISTLE_ENGINE_MODEL_CONTRACT["deterministic_replay_claim"] is True
    assert BRISTLE_ENGINE_MODEL_CONTRACT["physical_bristle_claim"] is False
    assert BRISTLE_ENGINE_MODEL_CONTRACT["paint_rheology_claim"] is False
    assert BRISTLE_ENGINE_MODEL_CONTRACT["external_brush_engine_parity_claim"] is False


def test_bristle_lanes_follow_path_normal_and_deplete_load() -> None:
    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import bristle_lane_paths

    stroke = Stroke(
        points=[(0.1, 0.5), (0.5, 0.5), (0.9, 0.5)],
        width_px=24,
        brush_style="impasto_oil",
        brush_engine_version=2,
        point_pressure=[0.6, 1.0, 0.7],
        point_load=[1.0, 0.9, 0.8],
        bristle_count=12,
        brush_seed=41,
        load_depletion=0.5,
    )
    lanes = bristle_lane_paths(stroke, width=200, height=100)
    assert len(lanes) >= 8
    assert all(len(lane) == 3 for lane in lanes)
    assert len({round(lane[1][1], 2) for lane in lanes}) > 4
    assert all(lane[-1][3] < lane[0][3] for lane in lanes)


def test_bristle_lanes_follow_tablet_tilt_direction() -> None:
    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import bristle_lane_paths

    base = Stroke(
        points=[(0.2, 0.5), (0.5, 0.5), (0.8, 0.5)],
        width_px=30,
        brush_style="bristle_oil",
        brush_engine_version=2,
        point_pressure=[0.8, 0.8, 0.8],
        bristle_count=12,
    )
    tilted = Stroke(
        **{
            **base.__dict__,
            "point_tilt": [0.8, 0.8, 0.8],
            "point_tilt_x": [0.7, 0.7, 0.7],
            "point_tilt_y": [-0.4, -0.4, -0.4],
        }
    )
    base_lanes = bristle_lane_paths(base, width=200, height=100)
    tilted_lanes = bristle_lane_paths(tilted, width=200, height=100)
    base_center = base_lanes[len(base_lanes) // 2][1]
    tilted_center = tilted_lanes[len(tilted_lanes) // 2][1]
    assert tilted_center[0] > base_center[0]
    assert tilted_center[1] < base_center[1]


def test_missing_bristle_pressure_is_constant_full_pressure_not_fabricated_partial_input() -> None:
    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import bristle_lane_paths

    common = {
        "points": [(0.2, 0.5), (0.5, 0.5), (0.8, 0.5)],
        "width_px": 20,
        "brush_style": "bristle_oil",
        "brush_engine_version": 2,
        "bristle_count": 10,
        "brush_seed": 17,
    }
    missing = bristle_lane_paths(Stroke(**common), width=200, height=100)
    explicit = bristle_lane_paths(
        Stroke(**common, point_pressure=[1.0, 1.0, 1.0]),
        width=200,
        height=100,
    )
    assert missing == explicit


def test_bristle_load_depletion_depends_on_travel_not_tablet_sample_count() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import bristle_lane_paths

    common = {
        "width_px": 20,
        "brush_style": "bristle_oil",
        "brush_engine_version": 2,
        "bristle_count": 10,
        "brush_seed": 17,
        "load_depletion": 0.7,
    }
    coarse = Stroke(points=[(0.1, 0.5), (0.9, 0.5)], **common)
    dense = Stroke(
        points=[(0.1 + 0.8 * index / 32.0, 0.5) for index in range(33)],
        **common,
    )

    coarse_lanes = bristle_lane_paths(coarse, width=200, height=100)
    dense_lanes = bristle_lane_paths(dense, width=200, height=100)

    assert len(coarse_lanes) == len(dense_lanes)
    assert [lane[-1][3] for lane in dense_lanes] == pytest.approx(
        [lane[-1][3] for lane in coarse_lanes]
    )


def test_load_depletion_uses_exact_document_pixel_travel() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import depleted_load_curve

    stroke = Stroke(
        points=[(0.10, 0.50), (0.60, 0.50)],
        point_load=[1.0, 1.0],
        load_depletion=0.8,
        load_dryout_px=200.0,
        material_resaturation=0.0,
    )

    # The path moves 100 document pixels: 50% of the 200 px dryout distance.
    assert depleted_load_curve(stroke, width=200, height=100) == pytest.approx(
        [1.0, 0.6]
    )


def test_segmented_load_depletion_preserves_full_stroke_travel() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import (
        depleted_load_curve,
        incremental_stroke_segments,
    )

    stroke = Stroke(
        points=[(0.10, 0.50), (0.40, 0.50), (0.60, 0.50)],
        brush_style="bristle_oil",
        brush_engine_version=2,
        point_load=[1.0, 1.0, 1.0],
        load_depletion=0.8,
        load_dryout_px=200.0,
    )
    full = depleted_load_curve(stroke, width=200, height=100)
    segments = incremental_stroke_segments(stroke, width=200, height=100)
    segmented = [
        depleted_load_curve(segment, width=200, height=100)
        for segment in segments
    ]

    assert segmented[0] == pytest.approx(full[:2])
    assert segmented[1] == pytest.approx(full[1:])


def test_sparse_sensor_curves_are_normalized_before_live_segment_split() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import (
        depleted_load_curve,
        incremental_stroke_segments,
        normalize_curve,
        normalize_signed_curve,
    )

    stroke = Stroke(
        points=[(0.10, 0.50), (0.30, 0.50), (0.60, 0.50), (0.90, 0.50)],
        brush_style="bristle_oil",
        brush_engine_version=2,
        point_pressure=[0.2, 0.9],
        point_tilt_x=[-0.5, 0.75],
        point_rotation=[0.1, 0.8],
        point_load=[1.0, 0.2],
        load_depletion=0.8,
        load_dryout_px=200.0,
    )
    segments = incremental_stroke_segments(stroke, width=200, height=100)
    full_load = depleted_load_curve(stroke, width=200, height=100)
    full_pressure = normalize_curve(stroke.point_pressure, len(stroke.points), 1.0)
    full_tilt_x = normalize_signed_curve(stroke.point_tilt_x, len(stroke.points))
    full_rotation = normalize_curve(stroke.point_rotation, len(stroke.points), 0.5)

    for index, segment in enumerate(segments):
        assert depleted_load_curve(segment, width=200, height=100) == pytest.approx(
            full_load[index : index + 2]
        )
        assert segment.point_pressure == pytest.approx(
            full_pressure[index : index + 2]
        )
        assert segment.point_tilt_x == pytest.approx(full_tilt_x[index : index + 2])
        assert segment.point_rotation == pytest.approx(
            full_rotation[index : index + 2]
        )


def test_incremental_bristle_segments_preserve_cumulative_document_travel() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import incremental_stroke_segments

    stroke = Stroke(
        points=[(0.1, 0.2), (0.4, 0.2), (0.4, 0.7)],
        brush_style="bristle_oil",
        brush_engine_version=2,
        brush_travel_offset_px=7.0,
    )
    segments = incremental_stroke_segments(stroke, width=200, height=100)

    assert len(segments) == 2
    assert segments[0].brush_travel_offset_px == pytest.approx(7.0)
    assert segments[1].brush_travel_offset_px == pytest.approx(67.0)


def test_explicit_bristle_count_uses_the_published_engine_capacity() -> None:
    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import (
        BRISTLE_ENGINE_MODEL_CONTRACT,
        bristle_lane_paths,
    )

    count = BRISTLE_ENGINE_MODEL_CONTRACT["max_explicit_bristle_count"]
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=80,
        brush_style="bristle_oil",
        brush_engine_version=2,
        bristle_count=count,
        brush_seed=4,
    )

    lanes = bristle_lane_paths(stroke, width=240, height=120)

    assert len(lanes) == count


def test_bristle_v2_color_and_material_use_authored_strands() -> None:
    _app()
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import PaintLayer, Stroke
    from app.painter_brush_engine_v2 import paint_bristle_v2
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("material-v2", "Bristle V2", layer_type="material")
    stroke = Stroke(
        points=[(0.1, 0.7), (0.36, 0.24), (0.68, 0.66), (0.92, 0.3)],
        color=(212, 106, 24),
        width_px=28,
        brush_style="bristle_oil",
        layer_id=layer.layer_id,
        brush_engine_version=2,
        point_pressure=[0.42, 0.96, 0.72, 0.36],
        point_load=[1.0, 0.94, 0.72, 0.48],
        bristle_count=18,
        brush_seed=73,
        load_depletion=0.32,
        material_enabled=True,
        material_load=0.9,
        material_thickness=0.88,
        material_roughness=0.42,
    )
    image = QImage(240, 140, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        assert paint_bristle_v2(painter, stroke, 240, 140, QColor(212, 106, 24, 255))
    finally:
        painter.end()
    assert any(
        image.pixelColor(x, y).alpha() > 0
        for y in range(0, image.height(), 4)
        for x in range(0, image.width(), 4)
    )

    channels = rasterize_material_channels([stroke], [layer], width=240, height=140)
    occupied = channels["height"] > 0.005
    assert channels["stroke_count"] == 1
    assert int(np.count_nonzero(occupied)) > 0
    assert float(np.ptp(channels["height"][occupied])) > 0.0
    assert float(np.ptp(channels["normal"][..., 0])) > 0.0


def test_zero_alpha_artwork_remains_fully_transparent_for_tip_and_bristle_paths() -> None:
    _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke
    from app.painter_brush_engine_v2 import paint_bristle_v2

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.set_pen_opacity(0)
    assert canvas._pen_opacity == 0

    image = QImage(160, 80, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        tip = Stroke(
            points=[(0.1, 0.5), (0.9, 0.5)],
            color=(220, 80, 40),
            opacity=0,
            width_px=24,
            brush_style="marker",
        )
        DrawingCanvas._paint_stroke(painter, tip, image.width(), image.height())
        bristle = Stroke(
            points=[(0.1, 0.3), (0.9, 0.3)],
            color=(220, 80, 40),
            opacity=0,
            width_px=24,
            brush_style="bristle_oil",
            brush_engine_version=2,
            bristle_count=12,
        )
        assert paint_bristle_v2(
            painter,
            bristle,
            image.width(),
            image.height(),
            QColor(220, 80, 40, 0),
        )
    finally:
        painter.end()

    assert all(
        image.pixelColor(x, y).alpha() == 0
        for y in range(image.height())
        for x in range(image.width())
    )


def test_zero_pressure_or_load_leaves_no_color_deposit_for_every_v2_style() -> None:
    _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import Stroke
    from app.painter_brush_engine_v2 import BRISTLE_V2_STYLES, paint_bristle_v2

    for style in sorted(BRISTLE_V2_STYLES):
        for pressure, load in (([0.0, 0.0], [1.0, 1.0]), ([1.0, 1.0], [0.0, 0.0])):
            stroke = Stroke(
                points=[(0.1, 0.5), (0.9, 0.5)],
                color=(220, 80, 40),
                opacity=255,
                width_px=24,
                brush_style=style,
                brush_engine_version=2,
                bristle_count=12,
                point_pressure=pressure,
                point_load=load,
            )
            image = QImage(160, 80, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            try:
                assert paint_bristle_v2(
                    painter,
                    stroke,
                    image.width(),
                    image.height(),
                    QColor(220, 80, 40, 255),
                )
            finally:
                painter.end()

            assert all(
                image.pixelColor(x, y).alpha() == 0
                for y in range(image.height())
                for x in range(image.width())
            ), (style, pressure, load)


def test_panel_icon_may_visualize_zero_alpha_stroke_without_mutating_artwork() -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        color=(220, 80, 40),
        opacity=0,
        width_px=24,
        layer_id="paint-layer-1",
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(160, 80, "transparent"),
        initial_strokes=[stroke],
        time_ms=0,
        standalone=True,
    )
    with_stroke = dialog._paint_panel_row_icon(
        visible=True,
        layer_id="paint-layer-1",
    ).pixmap(58, 30).toImage()
    assert dialog.canvas.embedded_strokes()[0].opacity == 0
    dialog.canvas.set_strokes_snapshot([])
    without_stroke = dialog._paint_panel_row_icon(
        visible=True,
        layer_id="paint-layer-1",
    ).pixmap(58, 30).toImage()

    assert with_stroke != without_stroke
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_material_stipple_is_opaque_distinct_and_uses_matching_relief_dabs() -> None:
    _app()
    import numpy as np
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import PaintLayer, Stroke
    from app.painter_brush_engine_v2 import (
        AUTO_BRISTLE_DENSITY_PER_PIXEL,
        paint_bristle_v2,
        stipple_dabs,
    )
    from app.painter_material_paint import rasterize_material_channels

    layer = PaintLayer("stipple", "Stipple", layer_type="material")
    stroke = Stroke(
        points=[(0.49, 0.50), (0.51, 0.505)],
        color=(174, 36, 28),
        width_px=28,
        brush_style="stipple_oil",
        layer_id=layer.layer_id,
        brush_engine_version=2,
        brush_seed=901,
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
    )
    image = QImage(180, 120, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        assert paint_bristle_v2(painter, stroke, 180, 120, QColor(174, 36, 28, 255))
    finally:
        painter.end()

    dabs = stipple_dabs(stroke, width=180, height=120)
    assert len(dabs) == round(stroke.width_px * AUTO_BRISTLE_DENSITY_PER_PIXEL)
    opaque_pixels = sum(
        image.pixelColor(x, y).alpha() >= 245
        for y in range(image.height())
        for x in range(image.width())
    )
    painted_pixels = sum(
        image.pixelColor(x, y).alpha() > 0
        for y in range(image.height())
        for x in range(image.width())
    )
    continuous = QImage(180, 120, QImage.Format.Format_ARGB32_Premultiplied)
    continuous.fill(Qt.GlobalColor.transparent)
    continuous_painter = QPainter(continuous)
    continuous_stroke = Stroke(**{**stroke.__dict__, "brush_style": "bristle_oil"})
    try:
        assert paint_bristle_v2(
            continuous_painter,
            continuous_stroke,
            180,
            120,
            QColor(174, 36, 28, 255),
        )
    finally:
        continuous_painter.end()
    assert opaque_pixels > 0
    assert painted_pixels > 0
    assert image != continuous

    channels = rasterize_material_channels([stroke], [layer], width=180, height=120)
    continuous_channels = rasterize_material_channels(
        [continuous_stroke], [layer], width=180, height=120
    )
    relief_pixels = int(np.count_nonzero(channels["height"] > 0.01))
    assert relief_pixels > 0
    assert not np.array_equal(channels["height"], continuous_channels["height"])
