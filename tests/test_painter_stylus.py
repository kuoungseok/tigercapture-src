from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _TabletEvent:
    def pressure(self):
        return 0.37

    def xTilt(self):
        return 30.0

    def yTilt(self):
        return -15.0

    def rotation(self):
        return 270.0

    def tangentialPressure(self):
        return -0.42


def test_tablet_sample_normalizes_pressure_tilt_rotation_and_barrel() -> None:
    from app.painter_stylus import tablet_stylus_sample

    sample = tablet_stylus_sample(_TabletEvent())
    assert sample.pressure == 0.37
    assert sample.tilt_x == 0.5
    assert sample.tilt_y == -0.25
    assert 0.39 < sample.tilt < 0.40
    assert sample.rotation == 0.75
    assert sample.tangential_pressure == -0.42


def test_canvas_stroke_keeps_stylus_channels_until_signal() -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.drawing import DrawingCanvas
    from app.painter_stylus import StylusSample

    canvas = DrawingCanvas(lambda: 1234, lambda: [])
    canvas.resize(200, 100)
    canvas.set_tool("pen")
    emitted = []
    canvas.stroke_added.connect(emitted.append)
    canvas._begin_current_stroke(
        QPointF(20, 40),
        StylusSample(
            pressure=0.25,
            tilt=0.4,
            tilt_x=0.5,
            tilt_y=-0.25,
            rotation=0.75,
            tangential_pressure=-0.4,
        ),
    )
    canvas._append_current_stroke_sample(
        QPointF(160, 60),
        StylusSample(
            pressure=0.9,
            tilt=0.2,
            tilt_x=-0.2,
            tilt_y=0.1,
            rotation=0.1,
            tangential_pressure=0.3,
        ),
    )
    canvas._finish_current_stroke()

    assert len(emitted) == 1
    stroke = emitted[0]
    assert stroke.points == [(0.1, 0.4), (0.8, 0.6)]
    assert stroke.point_pressure == [0.25, 0.9]
    assert stroke.point_tilt_x == [0.5, -0.2]
    assert stroke.point_tilt_y == [-0.25, 0.1]
    assert stroke.point_rotation == [0.75, 0.1]
    assert stroke.point_tangential_pressure == [-0.4, 0.3]


def test_action_smoothing_interpolates_signed_stylus_channels() -> None:
    from app.painter_stroke_geometry import smooth_action_points

    points = smooth_action_points(
        [
            {"x": 0.1, "y": 0.2, "tilt_x": -1.0, "tilt_y": 0.6},
            {"x": 0.5, "y": 0.4, "tilt_x": 0.0, "tilt_y": 0.0},
            {"x": 0.9, "y": 0.2, "tilt_x": 1.0, "tilt_y": -0.6},
        ],
        samples_per_segment=4,
    )
    assert len(points) > 3
    assert points[0]["tilt_x"] == -1.0
    assert points[-1]["tilt_x"] == 1.0
    assert all(-1.0 <= row["tilt_x"] <= 1.0 for row in points)


def test_gpu_canvas_payload_and_signature_retain_stylus_dynamics() -> None:
    from app.drawing import Stroke
    from app.painter_opengl import (
        _collect_canvas_gpu_strokes,
        canvas_stroke_gpu_signature,
    )

    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=20,
        point_pressure=[0.2, 1.0],
        point_tilt_x=[0.5, -0.5],
        point_tilt_y=[-0.25, 0.25],
    )
    payload = _collect_canvas_gpu_strokes(
        [stroke],
        width=200,
        height=100,
        time_ms=0,
        layer_visibility={},
        layer_opacity={},
        layer_masks={},
    )[0]
    assert payload["dynamic_widths"][0] < payload["dynamic_widths"][1]
    assert payload["points"][0] != (20.0, 50.0)

    signature = canvas_stroke_gpu_signature(
        [stroke],
        width=200,
        height=100,
        time_ms=0,
    )
    stroke.point_pressure = [1.0, 1.0]
    assert signature != canvas_stroke_gpu_signature(
        [stroke],
        width=200,
        height=100,
        time_ms=0,
    )
