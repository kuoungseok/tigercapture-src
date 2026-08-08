from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _press(widget, point) -> None:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QMouseEvent

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        point,
        point,
        point,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    assert _app().sendEvent(widget, event)


@pytest.mark.parametrize("size", [140, 176])
@pytest.mark.parametrize("saturation,value", [(0, 0), (0, 255), (255, 255), (127, 193)])
def test_color_wheel_selector_and_pointer_mapping_are_inverse(
    size: int,
    saturation: int,
    value: int,
) -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import PainterColorWheel

    wheel = PainterColorWheel()
    wheel.set_display_size(size)
    wheel.set_color(QColor.fromHsv(217, saturation, value))
    point = wheel._selector_point()
    weights = wheel._triangle_weights(point)

    assert weights is not None
    assert min(weights) >= -1e-12
    wheel._pick(point)
    assert abs(wheel._sat - saturation) <= 1
    assert abs(wheel._val - value) <= 1


@pytest.mark.parametrize("size", [140, 176])
def test_color_wheel_real_mouse_events_map_known_triangle_positions(size: int) -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.drawing import PainterColorWheel

    wheel = PainterColorWheel()
    wheel.set_display_size(size)
    wheel._hue = 217
    scale = max(1.0, size / 112.0)
    radius = size / 2.0 - 24.0 * scale
    expected = (
        QPointF(size / 2.0 + radius * 0.78, size / 2.0),
        QPointF(size / 2.0 - radius * 0.52, size / 2.0 - radius * 0.64),
        QPointF(size / 2.0 - radius * 0.52, size / 2.0 + radius * 0.64),
    )
    actual = wheel._triangle_points()
    for point, target in zip(actual, expected):
        assert point.x() == pytest.approx(target.x())
        assert point.y() == pytest.approx(target.y())

    centroid = QPointF(
        sum(point.x() for point in expected) / 3.0,
        sum(point.y() for point in expected) / 3.0,
    )

    def just_inside(point: QPointF) -> QPointF:
        return QPointF(
            point.x() + (centroid.x() - point.x()) * 1e-6,
            point.y() + (centroid.y() - point.y()) * 1e-6,
        )

    _press(wheel, just_inside(expected[0]))
    assert abs(wheel._sat - 255) <= 1 and abs(wheel._val - 255) <= 1
    _press(wheel, just_inside(expected[1]))
    assert wheel._sat <= 1 and abs(wheel._val - 255) <= 1
    _press(wheel, just_inside(expected[2]))
    assert wheel._val == 0
    _press(wheel, centroid)
    assert abs(wheel._sat - 127) <= 1
    assert abs(wheel._val - 170) <= 1


@pytest.mark.parametrize("size", [(190, 78), (320, 96)])
@pytest.mark.parametrize("saturation,value", [(0, 0), (0, 255), (255, 255), (127, 193)])
def test_photoshop_field_selector_and_pointer_mapping_are_inverse(
    size: tuple[int, int],
    saturation: int,
    value: int,
) -> None:
    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QColor

    from app.drawing import PainterPhotoshopColorField

    field = PainterPhotoshopColorField()
    field.setFixedSize(*size)
    field.set_color(QColor.fromHsv(217, saturation, value))
    rect = field._field_rect()
    point = QPointF(
        rect.left() + saturation / 255.0 * rect.width(),
        rect.top() + (1.0 - value / 255.0) * rect.height(),
    )
    field._drag_target = "field"
    field._pick(point)

    assert rect.width() >= 8
    assert rect.height() >= 8
    assert abs(field._sat - saturation) <= 1
    assert abs(field._val - value) <= 1


@pytest.mark.parametrize("size", [(190, 78), (320, 96)])
def test_photoshop_field_real_mouse_events_cover_corners_and_clamp(
    size: tuple[int, int],
) -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.drawing import PainterPhotoshopColorField

    field = PainterPhotoshopColorField()
    field.setFixedSize(*size)
    expected_width = max(8, size[0] - 24)
    expected_height = max(8, size[1] - 2)
    rect = field._field_rect()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (
        1.0,
        1.0,
        float(expected_width),
        float(expected_height),
    )
    for point, expected in (
        (QPointF(1.0, 1.0), (0, 255)),
        (QPointF(1.0 + expected_width, 1.0), (255, 255)),
        (QPointF(1.0, 1.0 + expected_height), (0, 0)),
        (QPointF(1.0 + expected_width, 1.0 + expected_height), (255, 0)),
        (QPointF(-10.0, -10.0), (0, 255)),
    ):
        _press(field, point)
        assert (field._sat, field._val) == expected

    hue_rect = field._hue_rect()
    _press(field, QPointF(hue_rect.center().x(), hue_rect.center().y()))
    assert abs(field._hue - 179) <= 1


def test_photoshop_field_eight_pixel_structural_floor_is_reachable() -> None:
    _app()
    from app.drawing import PainterPhotoshopColorField

    class TinyLogicalField(PainterPhotoshopColorField):
        def width(self) -> int:
            return 10

        def height(self) -> int:
            return 2

    rect = TinyLogicalField()._field_rect()
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (1.0, 1.0, 8.0, 8.0)


def test_color_input_geometry_uses_qt_logical_coordinates_at_two_x_scale() -> None:
    code = """
import json, os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app.drawing import PainterColorWheel, PainterPhotoshopColorField
app = QApplication.instance() or QApplication([])
wheel = PainterColorWheel()
wheel.set_display_size(140)
field = PainterPhotoshopColorField()
field.setFixedSize(190, 78)
point = QPointF(167.0, 77.0)
event = QMouseEvent(QEvent.Type.MouseButtonPress, point, point, point, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
app.sendEvent(field, event)
print(json.dumps({
    'dpr': app.primaryScreen().devicePixelRatio(),
    'wheel': [wheel.width(), wheel.height()],
    'triangle': [[p.x(), p.y()] for p in wheel._triangle_points()],
    'field': [field._field_rect().width(), field._field_rect().height()],
    'picked': [field._sat, field._val],
}))
"""
    reports = []
    for scale in ("1", "2"):
        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        env["QT_SCALE_FACTOR"] = scale
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=os.getcwd(),
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        reports.append(json.loads(result.stdout.strip().splitlines()[-1]))

    assert [report["dpr"] for report in reports] == [1.0, 2.0]
    for report in reports:
        assert report["wheel"] == [140, 140]
        assert report["field"] == [166.0, 76.0]
        assert report["picked"] == [255, 0]
        assert len({tuple(point) for point in report["triangle"]}) == 3
    assert reports[0]["triangle"] == reports[1]["triangle"]
