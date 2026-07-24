from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_studio_slider_click_jumps_to_pointer_position() -> None:
    _qt_app()
    from app.studio_slider import StudioSlider

    slider = StudioSlider("accent")
    slider.setRange(0, 100)
    slider.resize(220, 30)
    slider.show()

    assert slider.minimumHeight() >= 30
    assert slider.cursor().shape() == Qt.CursorShape.OpenHandCursor
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(166, 2))

    assert 70 <= slider.value() <= 78


def test_studio_slider_drag_uses_full_widget_height_as_hit_area() -> None:
    _qt_app()
    from app.studio_slider import StudioSlider

    slider = StudioSlider("accent")
    slider.setRange(0, 100)
    slider.resize(220, 30)
    slider.show()

    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(14, 1))
    assert slider.cursor().shape() == Qt.CursorShape.ClosedHandCursor
    QTest.mouseMove(slider, QPoint(206, 28))
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(206, 28))

    assert slider.cursor().shape() == Qt.CursorShape.OpenHandCursor
    assert slider.value() >= 95


def test_studio_slider_led_pulses_while_dragging_and_fades_after_release() -> None:
    _qt_app()
    from app.studio_slider import StudioSlider

    slider = StudioSlider("audio")
    slider.setRange(0, 100)
    slider.resize(220, 30)
    slider.show()

    QTest.mousePress(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(80, 15))

    assert slider._studio_led_level >= 0.99
    assert slider._studio_led_timer.isActive()

    QTest.mouseMove(slider, QPoint(120, 15))
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(120, 15))

    for _index in range(70):
        slider._advance_led_animation()

    assert slider._studio_led_level == 0.0
    assert not slider._studio_led_timer.isActive()
