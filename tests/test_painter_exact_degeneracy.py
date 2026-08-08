from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_tiny_nonzero_vectors_and_scales_are_not_reclassified_as_zero() -> None:
    from app.painter_3d_blockout import _normalized
    from app.painter_perspective_snap import _unit
    from app.painter_pixel_transform import PixelTransform, selection_transform_matrix

    assert _normalized((1.0e-12, 0.0, 0.0)) == (1.0, 0.0, 0.0)
    assert _normalized((0.0, 0.0, 0.0)) == (0.0, 0.0, 0.0)
    assert _unit((1.0e-12, 0.0)) == (1.0, 0.0)
    transform = selection_transform_matrix(
        10,
        10,
        PixelTransform(scale_x=1.0e-12, scale_y=1.0),
    )
    assert transform.m11() == pytest.approx(1.0e-12)
    with pytest.raises(ValueError, match="transform width must be positive"):
        selection_transform_matrix(0, 10, PixelTransform())


def test_nearby_pressure_controls_remain_distinct_unless_exactly_equal() -> None:
    from app.painter_brush_dynamics import map_pressure, normalize_pressure_curve

    curve = normalize_pressure_curve([[0.5, 0.2], [0.5 + 1.0e-10, 0.8]])
    assert [row for row in curve if 0.0 < row[0] < 1.0] == [
        [0.5, 0.2],
        [0.5 + 1.0e-10, 0.8],
    ]
    duplicate = normalize_pressure_curve([[0.5, 0.2], [0.5, 0.8]])
    assert [row for row in duplicate if row[0] == 0.5] == [[0.5, 0.8]]
    settings = {
        "enabled": True,
        "pressure_min": 0,
        "pressure_max": 100,
        "pressure_curve": [[0.0, 0.0], *curve, [1.0, 1.0]],
    }
    assert map_pressure(0.5 + 0.5e-10, settings) == pytest.approx(0.5)
    assert map_pressure(0.5 + 1.0e-10, settings) == pytest.approx(0.8)


def test_near_plane_intersection_uses_nonzero_denominator() -> None:
    from app.painter_3d_blockout import _clip_camera_polygon_near

    clipped = _clip_camera_polygon_near(
        [(0.0, 1.0 - 1.0e-8, 0.0), (10.0, 1.0 + 1.0e-8, 0.0)],
        near=1.0,
    )
    assert clipped[0][0] == pytest.approx(5.0)
    assert clipped[0][1] == 1.0


def test_tiny_valid_segment_and_rotation_are_preserved() -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.drawing import PaintDialog, _distance_to_segment, create_blank_paint_pixmap

    assert _distance_to_segment(
        QPointF(0.001, 0.0), QPointF(0.0, 0.0), QPointF(0.001, 0.0)
    ) == pytest.approx(0.0)
    assert PaintDialog._normalized_canvas_rotation(1.0e-9) == pytest.approx(1.0e-9)
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "#445566"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    dialog.show()
    _app().processEvents()
    dialog._set_canvas_rotation(1.0e-9)
    dialog._update_canvas_geometry()
    assert dialog._bg_label.isHidden()
    assert not dialog.canvas._view_background_pixmap.isNull()
    dialog.close()
