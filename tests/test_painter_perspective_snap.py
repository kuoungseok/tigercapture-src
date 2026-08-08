from __future__ import annotations

import math
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_two_point_ruler_chooses_closest_vanishing_direction() -> None:
    from app.painter_perspective_snap import (
        choose_perspective_direction,
        perspective_directions,
    )

    state = {
        "mode": 2,
        "left_vp": [-1.0, 0.5],
        "right_vp": [2.0, 0.5],
    }
    anchor = (50.0, 80.0)
    directions = perspective_directions(anchor, 100, 100, state)
    chosen = choose_perspective_direction(anchor, (80.0, 65.0), directions)
    assert chosen is not None and chosen[0] == "right_vp"


def test_projected_samples_remain_collinear_with_locked_ruler_axis() -> None:
    from app.painter_perspective_snap import project_to_direction

    anchor = (10.0, 10.0)
    direction = (2.0, 1.0)
    projected = [
        project_to_direction(anchor, point, direction)
        for point in ((20.0, 17.0), (30.0, 9.0), (42.0, 35.0))
    ]
    for x, y in projected:
        assert math.isclose((x - anchor[0]) * direction[1], (y - anchor[1]) * direction[0])


def test_one_and_three_point_modes_expose_documented_axes() -> None:
    from app.painter_perspective_snap import perspective_directions

    one = perspective_directions(
        (50, 50),
        100,
        100,
        {"mode": 1, "center_vp": [0.5, 0.2]},
    )
    assert {name for name, _direction in one} == {"center_vp", "horizontal", "vertical"}
    three = perspective_directions(
        (50, 50),
        100,
        100,
        {
            "mode": 3,
            "left_vp": [-1.0, 0.5],
            "right_vp": [2.0, 0.5],
            "vertical_vp": [0.5, -2.0],
        },
    )
    assert {name for name, _direction in three} == {
        "left_vp",
        "right_vp",
        "vertical_vp",
    }


def test_canvas_mouse_and_tablet_sample_path_locks_axis_until_pen_up() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.drawing import DrawingCanvas
    from app.painter_stylus import mouse_stylus_sample

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(200, 100)
    canvas.set_tool("pen")
    canvas.set_perspective_guides(
        enabled=True,
        snap=True,
        mode=1,
        center_vp=(0.5, 0.0),
    )
    size = canvas.canvas_content_size()
    width, height = size.width(), size.height()
    committed = []
    canvas.stroke_added.connect(committed.append)
    sample = mouse_stylus_sample()
    canvas._begin_current_stroke(QPointF(width * 0.5, height * 0.8), sample)
    canvas._append_current_stroke_sample(QPointF(width * 0.54, height * 0.45), sample, force=True)
    canvas._append_current_stroke_sample(QPointF(width * 0.9, height * 0.3), sample, force=True)
    assert canvas.perspective_guide_state()["active_stroke_axis"] == "center_vp"
    canvas._finish_current_stroke()
    assert len(committed) == 1
    xs = [point[0] for point in committed[0].points]
    assert all(abs(value - 0.5) < 1e-6 for value in xs)
    assert canvas.perspective_guide_state()["active_stroke_axis"] == ""
    canvas.deleteLater()
    app.processEvents()
