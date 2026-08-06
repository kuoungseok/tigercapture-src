from __future__ import annotations

import os

import pytest


def test_rounded_dab_uses_exact_capsule_geometry_without_pixel_caps() -> None:
    from app.painter_stroke_geometry import rounded_dab_corner_radius

    assert rounded_dab_corner_radius(40.0, 30.0) == 15.0
    assert rounded_dab_corner_radius(0.25, 0.1) == 0.05
    for values in ((0, 1), (1, 0), (-1, 1)):
        with pytest.raises(ValueError, match="positive"):
            rounded_dab_corner_radius(*values)
    for values in ((True, 1), (1, "bad")):
        with pytest.raises(TypeError):
            rounded_dab_corner_radius(*values)


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
    assert sample.rotation == 0.25
    assert sample.tangential_pressure == -0.42


def test_qt_rotation_uses_signed_centered_contract_and_missing_channels_are_neutral() -> None:
    from app.painter_stylus import StylusSample, tablet_stylus_sample

    class RotationEvent:
        def __init__(self, degrees: float) -> None:
            self.degrees = degrees

        def pressure(self):
            return 0.0

        def rotation(self):
            return self.degrees

    assert StylusSample().pressure == 0.0
    assert StylusSample().rotation == 0.5
    assert tablet_stylus_sample(RotationEvent(0.0)).rotation == 0.5
    assert tablet_stylus_sample(RotationEvent(90.0)).rotation == 0.75
    assert tablet_stylus_sample(RotationEvent(-90.0)).rotation == 0.25
    missing = tablet_stylus_sample(object())
    assert missing.pressure == 0.0
    assert missing.rotation == 0.5

    class NonFiniteEvent:
        def pressure(self):
            return float("nan")

        def rotation(self):
            return float("inf")

    nonfinite = tablet_stylus_sample(NonFiniteEvent())
    assert nonfinite.pressure == 0.0
    assert nonfinite.rotation == 0.5


def test_real_qtablet_event_object_follows_qt_channel_contract() -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QInputDevice, QPointingDevice, QTabletEvent

    from app.painter_stylus import tablet_stylus_sample

    capabilities = (
        QInputDevice.Capability.Position
        | QInputDevice.Capability.Pressure
        | QInputDevice.Capability.XTilt
        | QInputDevice.Capability.YTilt
        | QInputDevice.Capability.Rotation
        | QInputDevice.Capability.TangentialPressure
    )
    device = QPointingDevice(
        "Tiger QA Stylus",
        701,
        QInputDevice.DeviceType.Stylus,
        QPointingDevice.PointerType.Pen,
        capabilities,
        1,
        3,
    )
    event = QTabletEvent(
        QEvent.Type.TabletMove,
        device,
        QPointF(10.0, 20.0),
        QPointF(30.0, 40.0),
        0.6,
        30.0,
        -15.0,
        0.2,
        90.0,
        0.0,
        Qt.KeyboardModifier.NoModifier,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
    )
    sample = tablet_stylus_sample(event)
    assert sample.pressure == pytest.approx(0.6)
    assert sample.tilt_x == pytest.approx(0.5)
    assert sample.tilt_y == pytest.approx(-0.25)
    assert sample.rotation == pytest.approx(0.75)
    assert sample.tangential_pressure == pytest.approx(0.2)


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
    from app.painter_stroke_geometry import (
        ACTION_STROKE_SAMPLING_MODEL_CONTRACT,
        smooth_action_points,
    )

    assert ACTION_STROKE_SAMPLING_MODEL_CONTRACT["tablet_input_model_claim"] is False
    assert ACTION_STROKE_SAMPLING_MODEL_CONTRACT["external_brush_path_parity_claim"] is False

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


def test_action_smoothing_preserves_caller_budget_above_legacy_hidden_cap() -> None:
    from app.painter_stroke_geometry import smooth_action_points

    controls = [
        {"x": index / 99.0, "y": 0.25 if index % 2 else 0.75}
        for index in range(100)
    ]
    points = smooth_action_points(
        controls,
        samples_per_segment=24,
        max_points=2300,
    )
    assert 2048 < len(points) <= 2300


def test_action_smoothing_preserves_every_source_control_when_inputs_exceed_default_budget() -> None:
    from app.painter_stroke_geometry import smooth_action_points

    controls = [
        {
            "x": index / 699.0,
            "y": (index % 17) / 16.0,
            "pressure": (index % 11) / 10.0,
        }
        for index in range(700)
    ]

    points = smooth_action_points(controls)

    assert len(points) == len(controls)
    assert [row["x"] for row in points] == [row["x"] for row in controls]
    assert [row["y"] for row in points] == [row["y"] for row in controls]
    assert [row["pressure"] for row in points] == [row["pressure"] for row in controls]


def test_action_smoothing_uses_remaining_default_budget_across_complete_path() -> None:
    from app.painter_stroke_geometry import smooth_action_points

    controls = [
        {"x": index / 99.0, "y": (index % 13) / 12.0}
        for index in range(100)
    ]

    points = smooth_action_points(controls)

    assert len(points) == 512
    cursor = 0
    for control in controls:
        while points[cursor]["x"] != control["x"] or points[cursor]["y"] != control["y"]:
            cursor += 1
        cursor += 1
    assert cursor <= len(points)


def test_action_smoothing_rejects_noninteger_sampling_controls() -> None:
    import pytest

    from app.painter_stroke_geometry import smooth_action_points

    controls = [{"x": 0.0, "y": 0.0}, {"x": 0.5, "y": 1.0}, {"x": 1.0, "y": 0.0}]

    with pytest.raises(
        ValueError,
        match="samples_per_segment and max_points must be integers",
    ):
        smooth_action_points(controls, samples_per_segment=8.5)
    with pytest.raises(
        ValueError,
        match="samples_per_segment and max_points must be integers",
    ):
        smooth_action_points(controls, max_points=512.5)
    with pytest.raises(
        ValueError,
        match="samples_per_segment and max_points must be integers",
    ):
        smooth_action_points(controls[:2], samples_per_segment=8.5)


def test_gpu_canvas_only_accepts_semantically_mapped_default_round_strokes() -> None:
    import pytest

    from app.drawing import Stroke
    from app.painter_opengl import (
        PainterOpenGLUnavailable,
        _collect_canvas_gpu_strokes,
        canvas_stroke_gpu_signature,
    )

    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=1.0,
        opacity=0,
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
    assert payload["width"] == 1.0
    assert payload["dynamic_widths"] == []
    assert payload["points"][0] == (20.0, 50.0)
    assert payload["color"][3] == 0.0

    signature = canvas_stroke_gpu_signature(
        [stroke],
        width=200,
        height=100,
        time_ms=0,
    )
    stroke.point_pressure = [1.0, 1.0]
    assert signature == canvas_stroke_gpu_signature(
        [stroke],
        width=200,
        height=100,
        time_ms=0,
    )
    stroke.brush_dynamics = {"enabled": True}
    assert signature != canvas_stroke_gpu_signature(
        [stroke], width=200, height=100, time_ms=0
    )
    with pytest.raises(PainterOpenGLUnavailable, match="authored brush dynamics"):
        _collect_canvas_gpu_strokes(
            [stroke], width=200, height=100, time_ms=0,
            layer_visibility={}, layer_opacity={}, layer_masks={},
        )
    stroke.brush_dynamics = {}
    for style in ("marker", "highlighter"):
        stroke.brush_style = style
        with pytest.raises(PainterOpenGLUnavailable, match="unsupported brush style"):
            _collect_canvas_gpu_strokes(
                [stroke], width=200, height=100, time_ms=0,
                layer_visibility={}, layer_opacity={}, layer_masks={},
            )
    stroke.brush_style = "round"
    stroke.width_px = 0.25
    with pytest.raises(PainterOpenGLUnavailable, match="canonical CPU renderer"):
        _collect_canvas_gpu_strokes(
            [stroke], width=200, height=100, time_ms=0,
            layer_visibility={}, layer_opacity={}, layer_masks={},
        )
    stroke.width_px = 1.0
    stroke.points = [(-0.01, 0.5), (0.9, 0.5)]
    with pytest.raises(PainterOpenGLUnavailable, match="stroke point 0 x"):
        _collect_canvas_gpu_strokes(
            [stroke], width=200, height=100, time_ms=0,
            layer_visibility={}, layer_opacity={}, layer_masks={},
        )


def test_gpu_canvas_session_recreates_a_lost_context_once(monkeypatch) -> None:
    import app.painter_opengl as painter_opengl

    released: list[str] = []

    class Surface:
        def __init__(self, name: str) -> None:
            self.name = name

        def destroy(self) -> None:
            released.append(f"surface:{self.name}")

    class Context:
        def __init__(self, name: str, *, active: bool) -> None:
            self.name = name
            self.active = active

        def makeCurrent(self, _surface) -> bool:
            return self.active

        def doneCurrent(self) -> None:
            released.append(f"context:{self.name}")

    created = iter(
        (
            (Surface("first"), Context("first", active=False)),
            (Surface("second"), Context("second", active=True)),
        )
    )
    monkeypatch.setattr(painter_opengl, "_make_offscreen_context", lambda: next(created))
    session = painter_opengl._PainterCanvasOffscreenSession()

    first_surface, first_context = session.make_current()
    assert first_surface.name == first_context.name == "first"
    second_surface, second_context = session.make_current()
    assert second_surface.name == second_context.name == "second"
    assert released == ["context:first", "surface:first"]
    assert session.telemetry() == {
        "closed": False,
        "context_creations": 2,
        "context_activation_failures": 1,
        "context_recoveries": 1,
        "context_recovery_failures": 0,
        "last_context_error": "QOpenGLContext.makeCurrent returned false",
        "context_retained": True,
        "surface_retained": True,
    }
    session.close()
    assert released[-2:] == ["context:second", "surface:second"]
