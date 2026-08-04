from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


class _WheelEvent:
    def __init__(self, delta: int, modifiers) -> None:
        from PySide6.QtCore import QPoint

        self._delta = int(delta)
        self._modifiers = modifiers
        self._accepted = False
        self._zero = QPoint(0, 0)

    def angleDelta(self):
        from PySide6.QtCore import QPoint

        return QPoint(0, self._delta)

    def pixelDelta(self):
        return self._zero

    def modifiers(self):
        return self._modifiers

    def accept(self) -> None:
        self._accepted = True


def test_hover_wheel_spin_changes_without_focus_and_shift_accelerates() -> None:
    _app()
    from PySide6.QtCore import Qt

    from app.painter_wheel_controls import PainterHoverWheelSpinBox

    spin = PainterHoverWheelSpinBox()
    spin.setRange(1, 100)
    spin.setValue(20)
    spin.clearFocus()
    normal = _WheelEvent(120, Qt.KeyboardModifier.NoModifier)
    spin.wheelEvent(normal)
    assert spin.value() == 21
    assert normal._accepted is True
    assert spin.hasFocus() is False

    accelerated = _WheelEvent(-120, Qt.KeyboardModifier.ShiftModifier)
    spin.wheelEvent(accelerated)
    assert spin.value() == 16


def test_hover_wheel_spin_can_reserve_full_numeric_display_width() -> None:
    _app()
    from app.painter_wheel_controls import PainterHoverWheelSpinBox

    spin = PainterHoverWheelSpinBox()
    width = spin.fit_display_text("2048 px", minimum_px=88)
    assert width >= 88
    assert spin.minimumWidth() == width
    assert spin.maximumWidth() == width


def test_painter_top_size_and_opacity_use_hover_wheel_controls() -> None:
    app = _app()
    from PySide6.QtCore import QPoint

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_wheel_controls import PainterHoverWheelSpinBox

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    assert isinstance(dialog._top_brush_size_spin, PainterHoverWheelSpinBox)
    assert isinstance(dialog._top_brush_opacity_spin, PainterHoverWheelSpinBox)
    assert dialog._top_brush_size_spin.width() >= 88
    assert dialog._top_brush_opacity_spin.width() >= 76
    dialog._top_brush_size_spin.setValue(2048)
    dialog._top_brush_opacity_spin.setValue(100)
    assert dialog._top_brush_size_spin.text() == "2048 px"
    assert dialog._top_brush_opacity_spin.text() == "100%"
    dialog._show_quick_palette(QPoint(20, 20))
    app.processEvents()
    menu = dialog._quick_palette_menu
    assert isinstance(
        menu.findChild(PainterHoverWheelSpinBox, "PaintQuickBrushSizeSpin"),
        PainterHoverWheelSpinBox,
    )
    assert isinstance(
        menu.findChild(PainterHoverWheelSpinBox, "PaintQuickBrushOpacitySpin"),
        PainterHoverWheelSpinBox,
    )
    menu.close()
    dialog.close()
