from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.color_picker_widget import (
    ColorPaletteStrip,
    ColorPickerButton,
    normalized_color_text,
)


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_shared_color_picker_normalizes_and_emits_alpha_color() -> None:
    _app()
    picker = ColorPickerButton("#123456")
    selected: list[str] = []
    picker.color_selected.connect(selected.append)

    assert picker.choose_color("#8044AA22")
    assert picker.color() == "#8044AA22"
    assert selected == ["#8044AA22"]
    assert not picker.choose_color("not-a-color")
    assert normalized_color_text("#abcdef") == "#FFABCDEF"


def test_shared_palette_strip_exposes_and_emits_visible_swatches() -> None:
    _app()
    palette = ColorPaletteStrip(colors=["#112233", "#445566"])
    selected: list[str] = []
    palette.color_selected.connect(selected.append)

    assert palette.colors() == ["#FF112233", "#FF445566"]
    assert len(palette.findChildren(type(palette._buttons[0]))) == 2
    assert palette.choose_color("#445566")
    assert selected == ["#FF445566"]


def test_painter_ui_color_fields_expose_synchronized_pickers() -> None:
    _app()
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    assert inspector.fill_color_picker.choose_color("#123456")
    assert inspector.fill_edit.text() == "#FF123456"
    assert inspector.stroke_color_picker.choose_color("#80112233")
    assert inspector.stroke_edit.text() == "#80112233"
    assert inspector.multi_fill_color_picker.choose_color("#334455")
    assert inspector.multi_fill_edit.text() == "#FF334455"
    assert inspector.text_range_color_picker.choose_color("#AA556677")
    assert inspector.text_range_color_edit.text() == "#AA556677"
    assert inspector.shared_color_palette.colors()
    assert inspector.shared_color_palette.choose_color("#4C74DB")
    assert inspector.fill_edit.text() == "#FF4C74DB"


def test_painter_ui_appearance_boards_expose_color_pickers() -> None:
    _app()
    from app.painter_ui_appearance_editor import PainterUIAppearanceDialog

    dialog = PainterUIAppearanceDialog({"fill": "#FFFFFFFF"})
    assert dialog.paint_color_picker.choose_color("#102030")
    assert dialog.paint_color_edit.text() == "#FF102030"
    assert dialog.gradient_stop_color_picker.choose_color("#80405060")
    assert dialog.gradient_stop_color_edit.text() == "#80405060"
    assert dialog.effect_color_picker.choose_color("#40223344")
    assert dialog.effect_color_edit.text() == "#40223344"


def test_motion_board_picker_applies_to_selected_shape_and_text() -> None:
    _app()
    from app.motion_designer.schema import MotionComposition
    from app.motion_designer.ui.window import MotionDesignerWindow

    window = MotionDesignerWindow(
        MotionComposition(width=640, height=360, duration_ms=1000)
    )
    assert window.viewer_header.color_picker._presentation == "portrait"
    assert window.viewer_header.color_palette._presentation == "portrait"
    assert window.viewer_header.color_picker.height() == 68
    assert all(button.height() == 68 for button in window.viewer_header.color_palette._buttons)
    assert not window.viewer_header.color_palette.grab().toImage().isNull()
    assert not window.viewer_header.color_picker.isEnabled()

    window._add_layer("rectangle")
    shape = window.controller.composition.layers[-1]
    assert window.viewer_header.color_picker.isEnabled()
    assert window.viewer_header.color_picker.choose_color("#FF224466")
    assert shape.id == window.controller.composition.layers[-1].id
    assert window.controller.composition.layers[-1].source.params["fill"] == "#FF224466"
    assert window.viewer_header.color_palette.isEnabled()
    assert window.viewer_header.color_palette.choose_color("#4C74DB")
    assert window.controller.composition.layers[-1].source.params["fill"] == "#FF4C74DB"

    window._add_layer("text")
    assert window.viewer_header.color_picker.choose_color("#FFAA5500")
    assert window.controller.composition.layers[-1].source.params["fill"] == "#FFAA5500"
