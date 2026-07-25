from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


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
    assert int(np.count_nonzero(occupied)) > 100
    assert float(np.std(channels["height"][occupied])) > 0.003
    assert float(np.std(channels["normal"][..., 0])) > 0.001
