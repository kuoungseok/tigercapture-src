from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _dialog():
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    return PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )


def test_painting_color_board_uses_requested_order_and_default() -> None:
    app = _app()
    dialog = _dialog()
    dialog.show()
    app.processEvents()

    tabs = dialog._paint_color_tabs
    assert [tabs.tabText(index) for index in range(tabs.count())] == [
        "Presets",
        "Color Control",
    ]
    assert tabs.currentIndex() == 1
    if dialog._paint_color_panel.height() < 240:
        assert dialog._paint_color_wheel_frame.isHidden()
        assert all(spin.isVisible() for spin in dialog._color_numeric_spins)
    else:
        assert dialog.color_wheel.isVisible()
    assert not hasattr(dialog, "_paint_color_depth_preview")
    assert dialog._paint_palette_preset_board is not None
    dialog.close()


def test_preset_swatch_updates_brush_color_directly() -> None:
    app = _app()
    dialog = _dialog()
    board = dialog._paint_palette_preset_board

    skin_tones = next(preset for preset in board.presets() if preset.key == "skin_tones")
    assert len(skin_tones.colors) == 30
    assert len(
        [
            button
            for button in board._swatch_buttons
            if button.toolTip().startswith("Skin Tones")
        ]
    ) == 30

    board.select_preset("botanical")
    app.processEvents()
    chosen = next(
        button
        for button in board._swatch_buttons
        if button.toolTip().startswith("Botanical Study")
    )
    chosen.click()
    app.processEvents()
    assert dialog._pen_color.isValid()
    assert dialog._pen_color.name().upper() == "#E8D9B5"
    dialog.close()


def test_oil_colour_card_activates_native_normal_material_paint() -> None:
    app = _app()
    dialog = _dialog()
    board = dialog._paint_palette_preset_board
    oil = next(
        preset for preset in board.presets() if preset.key == "oil_colour_studies"
    )
    assert len(oil.colors) == 30
    assert oil.columns == 3
    assert oil.recommended_brush_style == "palette_knife"

    chosen = next(
        button
        for button in board._swatch_buttons
        if button.toolTip().startswith("Oil Colour Studies")
    )
    chosen.click()
    app.processEvents()

    layer = dialog._active_paint_layer()
    assert layer.layer_type == "material"
    assert layer.material_settings["thickness"] == 0.90
    assert layer.material_settings["roughness"] == 0.44
    assert dialog._pen_style == "palette_knife"
    assert dialog._material_preview_enabled is True
    assert dialog._pen_color.name().upper() == oil.colors[0]

    dialog._pen_style = "impasto_oil"
    dialog.canvas.set_pen_style("impasto_oil")
    second = [
        button
        for button in board._swatch_buttons
        if button.toolTip().startswith("Oil Colour Studies")
    ][1]
    second.click()
    app.processEvents()
    assert dialog._pen_style == "impasto_oil"
    assert dialog._pen_color.name().upper() == oil.colors[1]
    dialog.close()


def test_color_control_disc_and_palette_match_reference_structure() -> None:
    app = _app()
    dialog = _dialog()
    dialog.show()
    app.processEvents()

    disc = dialog.color_wheel
    center, _radius = disc._disc_geometry()
    red = disc._marker_point(0.0, 1.0)
    cyan = disc._marker_point(180.0, 1.0)
    assert red.x() > center.x()
    assert cyan.x() < center.x()
    assert len(dialog._palette_btns) == 20
    assert dialog._palette_harmony_combo.itemText(0) == "Complementary"
    assert dialog.custom_color_btn.isHidden()
    dialog._painter_localizer.refresh()
    assert dialog._paint_color_heading.text() == "Colors"
    first = dialog._palette_btns[0]
    second = dialog._palette_btns[1]
    assert second.geometry().left() == first.geometry().right() + 1
    assert "border-radius: 0px" in first.styleSheet()
    dialog.close()


def test_color_control_fits_current_inspector_height_without_manual_scroll() -> None:
    app = _app()
    dialog = _dialog()
    dialog.resize(1100, 700)
    dialog.show()
    app.processEvents()
    dialog._sync_color_panel_layout()
    app.processEvents()

    scroll = dialog._paint_inspector_controls_scroll
    panel = dialog._paint_color_panel
    assert dialog._paint_inspector_frame.isVisible()
    assert dialog._paint_inspector_frame.width() >= 280
    assert panel.height() <= scroll.viewport().height() + 2
    if panel.height() < 240:
        assert dialog._paint_color_wheel_frame.isHidden()
        assert all(spin.isVisible() for spin in dialog._color_numeric_spins)
    else:
        assert dialog.color_wheel.height() <= panel.height() - 250
    assert scroll.verticalScrollBar().maximum() <= 4
    last_swatch = dialog._palette_btns[-1]
    assert last_swatch.geometry().right() < dialog._paint_color_matrix_frame.width()

    compact_width = dialog._paint_inspector_frame.width()
    dialog.resize(1932, 1080)
    app.processEvents()
    dialog._ensure_paint_inspector_visible()
    app.processEvents()
    assert dialog._paint_inspector_frame.width() > compact_width
    assert dialog._paint_inspector_frame.width() >= 400
    dialog.close()
