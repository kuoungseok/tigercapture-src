from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_create_blank_paint_pixmap_supports_solid_and_transparent_backgrounds() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import create_blank_paint_pixmap

    white = create_blank_paint_pixmap(320, 180, "#FFFFFF")
    assert white.width() == 320
    assert white.height() == 180
    assert white.toImage().pixelColor(10, 10) == QColor("#FFFFFF")

    transparent = create_blank_paint_pixmap(64, 64, "transparent")
    pixel = transparent.toImage().pixelColor(0, 0)
    assert pixel.alpha() == 0

    default_blank = create_blank_paint_pixmap(64, 64)
    assert default_blank.toImage().pixelColor(32, 32).alpha() == 0


def test_new_canvas_dialog_reports_template_and_custom_size() -> None:
    app = _app()
    from app.drawing import NewCanvasDialog

    dialog = NewCanvasDialog(default_size=(1080, 1920), default_background="transparent")
    app.processEvents()

    request = dialog.canvas_request()
    assert request["width"] == 1080
    assert request["height"] == 1920
    assert request["background"] == "transparent"
    assert "Vertical" in request["template"]

    dialog.width_spin.setValue(1234)
    dialog.height_spin.setValue(777)
    app.processEvents()

    request = dialog.canvas_request()
    assert request["width"] == 1234
    assert request["height"] == 777
    assert request["template"] == "Custom"
    dialog.close()


def test_new_canvas_defaults_to_empty_transparency_with_display_only_checkerboard() -> None:
    app = _app()
    from app.drawing import NewCanvasDialog, PaintDialog, create_blank_paint_pixmap

    setup = NewCanvasDialog()
    assert setup.canvas_request()["background"] == "transparent"
    setup.close()

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    assert dialog._background_layer_present is False
    assert dialog._bg_pixmap_source.toImage().pixelColor(20, 20).alpha() == 0
    assert dialog._display_background_pixmap().toImage().pixelColor(20, 20).alpha() == 255
    assert dialog.canvas.embedded_strokes() == []
    assert [layer.name for layer in dialog._paint_layers] == ["Layer 1"]

    dialog._new_paint_layer()
    assert dialog.canvas.embedded_strokes() == []
    assert [layer.name for layer in dialog._paint_layers] == ["Layer 1", "Layer 2"]
    assert dialog._background_layer_present is False

    assert dialog._fill_document("solid", color1="#336699")
    assert dialog._background_layer_present is True
    assert dialog._bg_pixmap_source.toImage().pixelColor(20, 20).alpha() == 255
    dialog.close()


def test_photoshop_selection_modes_and_layer_reorder_change_document_state() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    dialog._set_tool("rect_select")
    assert dialog._selection_options_widget.isVisible()
    dialog.canvas.select_rectangle(0.05, 0.05, 0.35, 0.35)
    first_points = dialog.canvas.selection_snapshot()
    dialog._set_selection_combine_mode("add")
    dialog.canvas.select_rectangle(0.55, 0.55, 0.9, 0.9)
    assert dialog.canvas.selection_snapshot() != first_points
    assert dialog.painter_action_state()["selection"]["combine_mode"] == "add"

    dialog.canvas.set_strokes_snapshot(
        [Stroke(points=[(0.1, 0.1), (0.2, 0.2)], layer_id="paint-layer-1")]
    )
    dialog._new_paint_layer("Top")
    top_id = dialog._active_paint_layer_id
    dialog.canvas.add_stroke_direct(
        Stroke(points=[(0.7, 0.7), (0.8, 0.8)], layer_id=top_id)
    )
    dialog._update_layer_list()
    assert dialog._layer_list.item(0).data(Qt.ItemDataRole.UserRole) == top_id

    moved = dialog._layer_list.takeItem(1)
    dialog._layer_list.insertItem(0, moved)
    dialog._on_layer_rows_moved()

    assert [layer.layer_id for layer in dialog._paint_layers] == [top_id, "paint-layer-1"]
    assert [
        stroke.layer_id for stroke in dialog._visible_strokes_for_export()
    ] == [top_id, "paint-layer-1"]
    dialog.close()


def test_standalone_painter_hides_video_annotation_tools() -> None:
    app = _app()
    from app.drawing import (
        BRUSH_LIBRARY_PRESETS,
        PaintDialog,
        create_blank_paint_pixmap,
    )

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    assert dialog.windowTitle() == "Painter - Tiger Studio"
    assert dialog.bubble_btn.isHidden()
    assert dialog.sticker_btn.isHidden()
    assert dialog.editor_object_btn.isHidden()
    assert dialog.cutout_btn.isHidden()

    dialog.close()


def test_standalone_painter_initial_size_respects_available_screen(monkeypatch) -> None:
    _app()
    from PySide6.QtCore import QRect

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    monkeypatch.setattr(
        PaintDialog,
        "_available_painter_geometry",
        lambda self, parent=None: QRect(0, 0, 800, 600),
    )

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )

    assert dialog.width() <= 752
    assert dialog.height() <= 536
    assert dialog.minimumWidth() <= 752
    assert dialog.minimumHeight() <= 536
    dialog.move(2000, 2000)
    dialog._fit_painter_window_to_screen()
    assert dialog.x() + dialog.width() <= 800
    assert dialog.y() + dialog.height() <= 600

    dialog.close()


def test_standalone_painter_pauses_repaints_while_window_moves() -> None:
    app = _app()
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QMoveEvent

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    assert dialog.updatesEnabled()
    dialog.moveEvent(QMoveEvent(QPoint(40, 48), QPoint(32, 40)))
    assert getattr(dialog, "_move_refresh_paused", False) is True
    assert not dialog.updatesEnabled()

    dialog._finish_window_move_refresh_pause()
    assert getattr(dialog, "_move_refresh_paused", False) is False
    assert dialog.updatesEnabled()

    dialog.close()


def test_standalone_painter_uses_vector_icons_and_compact_palette() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, QSize, Qt
    from PySide6.QtWidgets import QComboBox, QListView, QListWidget

    from app.drawing import (
        BRUSH_LIBRARY_PRESETS,
        BRUSH_PANEL_PRESET_CELL_SIZE,
        BRUSH_POPUP_PRESET_CELL_SIZE,
        BRUSH_PRESET_ICON_SIZE,
        PaintDialog,
        create_blank_paint_pixmap,
    )
    from app.i18n import tr

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    dialog.resize(1100, 640)
    app.processEvents()
    app.processEvents()

    assert dialog.isSizeGripEnabled()
    assert getattr(dialog, "_dialog_buttons", None) is None
    assert dialog.minimumWidth() <= 760
    assert dialog.canvas.embedded_strokes() == []
    assert dialog.painter_action_state()["view"]["zoom_percent"] == 100
    assert dialog.undo_btn.text() == "↶"
    assert dialog.undo_btn.width() <= 34
    assert dialog.redo_btn.text() == "↷"
    assert dialog.redo_btn.width() <= 34
    assert dialog.export_png_btn.text() == ""
    assert not dialog.export_png_btn.icon().isNull()
    assert dialog.zoom_slider.isHidden()
    assert dialog.zoom_out_btn.isHidden()
    assert dialog.zoom_in_btn.isHidden()
    assert dialog.zoom_fit_btn.isHidden()
    assert "Zoom In" in [
        action.text().replace("&", "")
        for action in dialog._painter_view_menu.actions()
    ]
    assert dialog._paint_inspector_controls.parentWidget() is not None
    assert dialog._paint_inspector_controls_scroll.maximumHeight() <= 330
    assert dialog._paint_inspector_controls_scroll.width() <= 300
    assert dialog._tool_rail.width() == 40
    assert dialog.tool_collapse_btn.toolTip() == "Collapse toolbar"
    assert dialog.tool_close_btn.toolTip() == "Close toolbar"
    assert dialog.tool_collapse_btn.isVisible() is False
    assert dialog.tool_close_btn.isVisible() is False
    assert dialog._tool_rail_grip.isVisible()
    assert dialog._tool_button_host.isVisible()
    assert dialog._tool_swatch_panel.isVisible()
    assert dialog._paint_toolbar_order == [
        "move",
        "rect_marquee",
        "ellipse_marquee",
        "magic_select",
        "crop",
        "brush",
        "eraser",
        "fill",
        "path",
        "hand",
        "fit",
        "quick_mask",
        "mirror_x",
        "mirror_y",
        "3d_blockout",
    ]
    assert dialog.select_btn.toolTip() == "Move / Select Objects (V)"
    assert dialog.magic_select_btn.toolTip() == "Magic Select / Select by Color (W)"
    assert dialog.fill_tool_btn.toolTip() == "Paint Bucket / Fill (G)"
    assert dialog.quick_mask_rail_btn.toolTip() == "Quick Mask Mode (Q)"
    assert len(dialog._painter_tool_shortcuts) == 7
    assert dialog.foreground_swatch_btn.toolTip().startswith("Foreground color")
    assert dialog.background_swatch_btn.toolTip().startswith("Background color")
    assert dialog.select_btn.text() == ""
    assert dialog.select_btn.toolTip() == "Move / Select Objects (V)"
    assert dialog.pan_btn.text() == ""
    assert dialog.pan_btn.toolTip() == "Hand / Pan Canvas (H)"
    assert dialog.rect_select_btn.text() == ""
    assert dialog.rect_select_btn.toolTip() == "Rectangular Marquee (M)"
    assert dialog.ellipse_select_btn.text() == ""
    assert dialog.ellipse_select_btn.toolTip() == "Elliptical Marquee"
    assert dialog.magic_select_btn.text() == ""
    assert dialog.magic_select_btn.toolTip() == "Magic Select / Select by Color (W)"
    assert dialog.crop_btn.text() == ""
    assert dialog.crop_btn.toolTip() == "Crop Tool (C)"
    assert dialog.pen_btn.text() == ""
    assert dialog.pen_btn.toolTip() == "Brush Tool (B)"
    assert "preset" not in dialog.pen_btn.toolTip().casefold()
    assert dialog._brush_preset_button.objectName() == "PaintBrushPresetButton"
    assert dialog._brush_preset_button.toolTip() == "Open Brush Presets"
    assert not dialog._brush_preset_button.icon().isNull()
    assert dialog.eraser_btn.text() == ""
    assert dialog.eraser_btn.toolTip()
    assert not dialog.select_btn.icon().isNull()
    assert not dialog.pan_btn.icon().isNull()
    assert not dialog.rect_select_btn.icon().isNull()
    assert not dialog.ellipse_select_btn.icon().isNull()
    assert not dialog.magic_select_btn.icon().isNull()
    assert not dialog.crop_btn.icon().isNull()
    assert not dialog.mirror_x_btn.icon().isNull()
    assert not dialog.mirror_y_btn.icon().isNull()
    assert not dialog.pen_btn.icon().isNull()
    assert not dialog.eraser_btn.icon().isNull()
    assert not dialog.path_btn.icon().isNull()
    assert dialog.fill_tool_btn.text() == ""
    assert dialog.fill_tool_btn.toolTip() == "Paint Bucket / Fill (G)"
    assert not dialog.fill_tool_btn.icon().isNull()
    assert dialog.zoom_fit_rail_btn.text() == ""
    assert dialog.zoom_fit_rail_btn.toolTip() == "Fit Canvas to Window (Ctrl+0)"
    assert not dialog.zoom_fit_rail_btn.icon().isNull()
    assert dialog.quick_mask_rail_btn.text() == ""
    assert dialog.quick_mask_rail_btn.toolTip() == "Quick Mask Mode (Q)"
    assert not dialog.quick_mask_rail_btn.icon().isNull()
    dialog._set_tool_rail_collapsed(True)
    app.processEvents()
    assert dialog._tool_rail.width() <= 34
    assert dialog._tool_button_host.isVisible() is False
    assert dialog._tool_swatch_panel.isVisible() is False
    assert dialog.tool_close_btn.isVisible() is False
    assert dialog.tool_collapse_btn.toolTip() == "Expand toolbar"
    dialog._set_tool_rail_collapsed(False)
    app.processEvents()
    assert dialog._tool_rail.width() == 40
    assert dialog._tool_button_host.isVisible()
    assert dialog._tool_swatch_panel.isVisible()
    dialog._swap_painter_foreground_background()
    app.processEvents()
    assert dialog.foreground_swatch_btn.toolTip().startswith("Foreground color")
    assert hasattr(dialog, "brush_library_list")
    assert dialog.brush_library_list.viewMode() == QListView.ViewMode.IconMode
    assert dialog.brush_library_list.count() == len(BRUSH_LIBRARY_PRESETS)
    assert dialog.brush_library_list.iconSize() == BRUSH_PRESET_ICON_SIZE
    assert dialog.brush_library_list.gridSize() == BRUSH_PANEL_PRESET_CELL_SIZE
    assert dialog._brush_panel_stack.currentWidget() is dialog._brush_library_page
    assert dialog._brush_library_selector.currentText() == "Tiger Studio Brushes"
    assert dialog._brush_category_list.item(0).text() == "All Brushes"
    assert dialog._brush_filter_combo.findText("My Favorites") >= 0
    assert dialog._brush_filter_combo.findText("Watercolor") >= 0
    assert dialog._brush_filter_combo.findText("Thick Paint") >= 0
    assert dialog._brush_library_preview.pixmap() is not None
    dialog._set_brush_tab("settings")
    assert dialog._brush_panel_stack.currentWidget() is dialog._brush_controls_page
    dialog._set_brush_tab("presets")
    dialog._brush_search_edit.setText("watercolor")
    app.processEvents()
    assert 0 < dialog.brush_library_list.count() < len(BRUSH_LIBRARY_PRESETS)
    assert all(
        "watercolor" in dialog.brush_library_list.item(row).toolTip().casefold()
        for row in range(dialog.brush_library_list.count())
    )
    dialog._brush_search_edit.clear()
    app.processEvents()
    assert dialog.brush_library_list.count() == len(BRUSH_LIBRARY_PRESETS)
    assert dialog._paint_brush_detail_panel.parent() is dialog._paint_inspector_controls
    assert dialog._brush_detail_category_buttons["Brush Tip Shape"].isChecked()
    assert dialog._brush_detail_category_buttons["Smoothing"].isChecked()
    assert dialog.brush_style_combo.findData("real_wet_oil") >= 0
    assert dialog.width_slider.value() == int(dialog._pen_width)
    assert dialog.brush_hardness_slider.value() == 100
    assert dialog.brush_spacing_slider.value() == 25
    assert dialog.brush_roundness_slider.value() == 100
    assert dialog._brush_detail_preview.pixmap() is not None
    assert not dialog._brush_detail_preview.pixmap().isNull()
    brush_styles = {str(row["style"]) for row in BRUSH_LIBRARY_PRESETS}
    assert {
        "loaded_oil",
        "impasto_oil",
        "oil_smear",
        "soft_oil_glaze",
        "real_wet_oil",
        "bristle_oil",
        "dry_oil",
        "palette_knife",
        "textured_chalk",
    } <= brush_styles
    assert {
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "rigger_oil",
        "scumble_oil",
        "stipple_oil",
        "knife_scrape_oil",
    } <= brush_styles
    dialog._brush_preset_button.click()
    app.processEvents()
    assert dialog._brush_preset_menu is not None
    assert dialog.pen_btn.isDown() is False
    dialog._brush_preset_menu.close()
    brush_menu = dialog._build_brush_button_menu()
    brush_popup_list = brush_menu.findChild(QListWidget, "PaintBrushPopupList")
    brush_popup_category = brush_menu.findChild(QComboBox, "PaintBrushPopupCategory")
    assert brush_popup_list is not None
    assert brush_popup_category is not None
    assert brush_popup_category.findText("Pro Oils") >= 0
    assert brush_popup_category.findText("Water Media") >= 0
    assert brush_popup_category.findText("Concept") >= 0
    assert brush_popup_list.viewMode() == QListView.ViewMode.IconMode
    assert brush_popup_list.iconSize() == BRUSH_PRESET_ICON_SIZE
    assert brush_popup_list.gridSize() == BRUSH_POPUP_PRESET_CELL_SIZE
    assert brush_popup_list.count() == len(BRUSH_LIBRARY_PRESETS)
    assert brush_popup_list.item(0).text() == ""
    assert BRUSH_LIBRARY_PRESETS[0]["name"] in brush_popup_list.item(0).toolTip()
    assert not brush_popup_list.item(0).icon().isNull()
    brush_popup_list.itemClicked.emit(brush_popup_list.item(0))
    app.processEvents()
    assert dialog.pen_btn.isChecked()
    assert int(dialog._pen_width) == BRUSH_LIBRARY_PRESETS[0]["width"]
    assert dialog.canvas._pen_style == BRUSH_LIBRARY_PRESETS[0]["style"]
    assert dialog._pen_opacity == int(BRUSH_LIBRARY_PRESETS[0]["opacity"] * 255 / 100)
    assert dialog._brush_detail_settings["hardness"] == BRUSH_LIBRARY_PRESETS[0]["hardness"]
    assert dialog._brush_detail_settings["spacing"] == BRUSH_LIBRARY_PRESETS[0]["spacing"]
    assert dialog._brush_recent_list.count() == 1
    dialog._toggle_active_brush_favorite()
    assert dialog._brush_favorite_btn.text() == "★"
    dialog._brush_filter_combo.setCurrentIndex(
        dialog._brush_filter_combo.findData("favorites")
    )
    app.processEvents()
    assert dialog.brush_library_list.count() == 1
    dialog._brush_filter_combo.setCurrentIndex(0)
    assert "Brush:" in dialog._tool_status_label.text()
    assert dialog.selection_aspect_combo.parent() is dialog._selection_options_widget
    assert dialog.crop_apply_btn.parent() is dialog._selection_action_widget
    assert dialog.magic_tolerance_slider.parent() is dialog._magic_options_widget
    assert dialog._tool_options_host.parent().objectName() == "PaintTopBar"
    assert dialog._tool_options_host.height() <= 34
    assert dialog.quick_mask_btn.isHidden()
    assert dialog.grid_view_btn.isHidden()
    assert dialog.snap_grid_btn.isHidden()
    assert dialog.undo_btn.isHidden()
    assert dialog.redo_btn.isHidden()
    assert dialog.export_png_btn.isHidden()
    assert dialog._paint_status_bar.height() <= 24
    assert dialog._status_zoom_spin.value() == 100
    assert dialog._status_document_label.text() == "640 x 360 px"
    assert dialog._paint_brush_detail_panel.isHidden()
    assert dialog._paint_reference_panel.isHidden()
    assert dialog._paint_3d_blockout_panel.isHidden()
    assert not hasattr(dialog, "toggle_channel_visibility_btn")
    assert dialog._layer_channel_path_tabs.count() == 3
    assert [
        dialog._layer_channel_path_tabs.tabText(i)
        for i in range(dialog._layer_channel_path_tabs.count())
    ] == [tr("paint.tab.layers"), tr("paint.tab.channels"), tr("paint.tab.paths")]
    assert not hasattr(dialog, "_paint_panel_tab_buttons")
    assert dialog._layer_channel_path_tabs.tabBar().isVisible()
    assert dialog._layer_channel_path_tabs.tabBar().usesScrollButtons() is False
    assert dialog._paint_layer_dock_panel.minimumHeight() >= 340
    assert dialog._layer_channel_path_tabs.minimumHeight() >= 280
    assert dialog._layer_list.minimumHeight() >= 126
    assert dialog._channel_list.minimumHeight() >= 150
    assert dialog._path_list.minimumHeight() >= 170
    assert dialog._layer_filter_icon_strip.isVisible()
    assert all(btn.isVisible() for btn in dialog._layer_filter_tiny_buttons)
    assert dialog.layer_new_btn.text() == ""
    assert dialog.layer_duplicate_btn.text() == ""
    assert dialog.layer_copy_btn.text() == ""
    assert dialog.layer_paste_btn.text() == ""
    assert dialog.layer_delete_btn.text() == ""
    assert not dialog.layer_new_btn.icon().isNull()
    dialog._show_painter_tab("paths")
    app.processEvents()
    assert dialog._layer_channel_path_tabs.currentIndex() == 2
    menu_labels = [
        action.text().replace("&", "")
        for action in dialog._painter_menu_bar.actions()
    ]
    assert menu_labels == ["File", "Edit", "Image", "Layer", "Select", "View", "Window"]
    assert "Brush Settings" in [
        action.text().replace("&", "")
        for action in dialog._painter_brush_menu.actions()
    ]
    assert "PBR Texture Lab..." in [
        action.text().replace("&", "")
        for action in dialog._painter_image_menu.actions()
    ]
    assert "Export PBR Maps..." in [
        action.text().replace("&", "")
        for action in dialog._painter_image_menu.actions()
    ]
    assert "PBR Texture Lab..." in [
        action.text().replace("&", "")
        for action in dialog._painter_window_menu.actions()
    ]
    assert "Brush" in [
        action.text().replace("&", "")
        for action in dialog._painter_window_menu.actions()
    ]
    assert dialog.layer_filter_combo.currentText() == tr("paint.layer.filter_kind")
    assert len(dialog._layer_filter_tiny_buttons) == 6
    assert all(not btn.isVisible() for btn in dialog._layer_filter_tiny_buttons)
    assert dialog.layer_blend_combo.currentText() == tr("paint.layer.blend_normal")
    assert dialog._layer_opacity_value.value() == 100
    assert dialog._layer_fill_value.text() == "100%"
    assert dialog._layer_fill_label.geometry().top() > dialog._layer_lock_label.geometry().bottom()
    assert not dialog._layer_lock_all_btn.isChecked()
    assert dialog._channel_list.item(0).text() == "RGB"
    assert not dialog._channel_list.item(0).icon().isNull()
    assert "eye icon" in dialog._channel_list.item(0).toolTip()
    assert not (dialog._channel_list.item(0).flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert not hasattr(dialog, "pbr_preview_mode_combo")
    assert not hasattr(dialog, "pbr_normal_format_combo")
    assert not hasattr(dialog, "pbr_preview_label")
    assert dialog._paint_color_wheel_frame.isHidden()
    assert dialog._paint_color_tabs.count() == 4
    assert [
        dialog._paint_color_tabs.tabText(index)
        for index in range(dialog._paint_color_tabs.count())
    ] == ["Color", "Swatches", "Gradients", "Patterns"]
    assert dialog.photoshop_color_field.isVisible()
    dialog.photoshop_color_field._drag_target = "hue"
    dialog.photoshop_color_field._pick(
        QPointF(
            dialog.photoshop_color_field._hue_rect().center().x(),
            dialog.photoshop_color_field._hue_rect().center().y(),
        )
    )
    app.processEvents()
    assert 170 <= dialog._pen_color.hue() <= 190
    dialog.photoshop_color_field._drag_target = "field"
    dialog.photoshop_color_field._pick(
        QPointF(
            dialog.photoshop_color_field._field_rect().right(),
            dialog.photoshop_color_field._field_rect().top(),
        )
    )
    app.processEvents()
    assert dialog._pen_color.saturation() >= 250
    assert dialog._pen_color.value() >= 250
    assert dialog._paint_color_matrix_frame.isVisible() is False
    dialog._paint_color_tabs.setCurrentIndex(1)
    app.processEvents()
    assert dialog._paint_color_matrix_frame.isVisible()
    assert dialog._paint_color_matrix_frame.height() <= 90
    dialog._paint_color_tabs.setCurrentIndex(0)
    assert dialog._color_preview.width() <= 48
    assert dialog._paint_mixer_label.text() == "Mixer"
    assert dialog.saturation_slider.isHidden()
    assert dialog.hue_slider.isHidden()
    assert dialog.value_slider.isHidden()
    assert dialog._recent_color_btns[0].width() <= 32
    assert dialog._paint_harmony_label.isHidden()
    assert len(dialog._palette_btns) == 8
    assert dialog._palette_btns[0].width() <= 48
    assert "shade" in dialog._palette_btns[0].toolTip().lower()
    scroll = dialog._paint_inspector_controls_scroll
    assert dialog._layer_channel_path_tabs.parent() is dialog._paint_layer_dock_panel
    assert dialog._paint_layer_dock_panel.height() >= 300
    assert dialog._paint_export_note is None
    layer_labels = [
        dialog._layer_list.item(idx).text()
        for idx in range(dialog._layer_list.count())
    ]
    assert not any("Strokes" in label for label in layer_labels)
    assert dialog._layer_list.item(0).data(Qt.ItemDataRole.UserRole + 1) == "none"
    assert dialog._layer_list.iconSize() == QSize(58, 30)
    assert dialog._channel_list.iconSize() == QSize(58, 30)
    assert not dialog.copy_channel_btn.icon().isNull()
    assert dialog.copy_channel_btn.text() == ""
    assert not dialog.commit_path_btn.icon().isNull()
    assert dialog.commit_path_btn.text() == ""
    assert dialog._layer_channel_path_tabs.tabIcon(0).isNull()
    color_bottom = dialog._paint_color_panel.mapToGlobal(
        dialog._paint_color_panel.rect().bottomLeft()
    ).y()
    layer_top = dialog._paint_layer_dock_panel.mapToGlobal(
        dialog._paint_layer_dock_panel.rect().topLeft()
    ).y()
    assert color_bottom < layer_top or scroll.verticalScrollBar().isVisible()
    bar = scroll.verticalScrollBar()
    assert bar.value() >= dialog._paint_color_panel.y() - 2
    margins = dialog._paint_inspector_controls.layout().contentsMargins()
    assert margins.right() >= 6
    if bar.isVisible():
        color_right = dialog._paint_color_panel.mapToGlobal(
            dialog._paint_color_panel.rect().topRight()
        ).x()
        bar_left = bar.mapToGlobal(bar.rect().topLeft()).x()
        assert color_right < bar_left
    dialog.resize(760, 560)
    app.processEvents()
    dialog._sync_color_panel_layout()
    assert dialog._paint_color_wheel_frame.isHidden()
    assert dialog._paint_color_panel.minimumHeight() == 148
    assert dialog._paint_color_panel.maximumHeight() == 194

    dialog.close()


def test_painter_oil_brush_renders_textured_preview_and_export(tmp_path: Path) -> None:
    _app()
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import (
        DrawingCanvas,
        Stroke,
        compose_pil_frame_with_overlays,
        render_strokes_to_png,
    )

    stroke = Stroke(
        points=[
            (0.08, 0.72),
            (0.24, 0.28),
            (0.44, 0.62),
            (0.64, 0.22),
            (0.88, 0.38),
        ],
        color=(230, 78, 32),
        opacity=230,
        width_px=30,
        brush_style="impasto_oil",
    )

    preview = QImage(320, 180, QImage.Format.Format_ARGB32)
    preview.fill(0)
    painter = QPainter(preview)
    try:
        DrawingCanvas._paint_stroke(painter, stroke, 320, 180)
    finally:
        painter.end()

    preview_colors = set()
    preview_alpha_pixels = 0
    for y in range(0, preview.height(), 2):
        for x in range(0, preview.width(), 2):
            color = preview.pixelColor(x, y)
            if color.alpha() <= 0:
                continue
            preview_alpha_pixels += 1
            preview_colors.add((color.red(), color.green(), color.blue(), color.alpha()))
    assert preview_alpha_pixels > 180
    assert len(preview_colors) > 14

    out_path = tmp_path / "wet_oil.png"
    assert render_strokes_to_png([stroke], 320, 180, str(out_path))
    exported = QImage(str(out_path))
    assert not exported.isNull()
    assert any(
        exported.pixelColor(x, y).alpha() > 0
        for y in range(0, exported.height(), 3)
        for x in range(0, exported.width(), 3)
    )

    from PIL import Image

    pil = compose_pil_frame_with_overlays(
        frame=Image.new("RGBA", (320, 180), (0, 0, 0, 0)),
        strokes=[stroke],
        subtitles=[],
        time_ms=0,
    )
    assert pil.getbbox() is not None


def test_painter_pro_oil_brushes_render_distinct_textures() -> None:
    _app()
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke

    styles = (
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "rigger_oil",
        "scumble_oil",
        "stipple_oil",
        "knife_scrape_oil",
    )
    signatures: set[tuple[int, int, int]] = set()
    for style in styles:
        image = QImage(300, 100, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            DrawingCanvas._paint_stroke(
                painter,
                Stroke(
                    points=[(0.06, 0.72), (0.30, 0.28), (0.58, 0.66), (0.92, 0.34)],
                    color=(214, 84, 38),
                    opacity=236,
                    width_px=28,
                    brush_style=style,
                ),
                image.width(),
                image.height(),
            )
        finally:
            painter.end()
        alpha_count = 0
        color_count: set[tuple[int, int, int, int]] = set()
        alpha_sum = 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                pixel = image.pixelColor(x, y)
                if pixel.alpha() <= 0:
                    continue
                alpha_count += 1
                alpha_sum += pixel.alpha()
                color_count.add((pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()))
        assert alpha_count > 24, style
        assert len(color_count) > 3, style
        signatures.add((alpha_count, len(color_count), alpha_sum // max(1, alpha_count)))
    assert len(signatures) == len(styles)


def test_painter_designer_brush_catalog_renders_all_profiles() -> None:
    _app()
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke
    from app.painter_brush_catalog import (
        DESIGNER_BRUSH_PRESETS,
        DESIGNER_BRUSH_STYLE_IDS,
    )

    assert len(DESIGNER_BRUSH_PRESETS) >= 20
    assert {
        "soft_round",
        "graphite_pencil",
        "technical_ink",
        "watercolor_wash",
        "gouache_flat",
        "airbrush_soft",
        "hair_strand",
        "foliage_scatter",
        "cloud_smoke",
        "rock_ground",
        "fabric_grunge",
        "paint_splatter",
        "pixel_square",
    } <= DESIGNER_BRUSH_STYLE_IDS

    signatures: set[tuple[int, int]] = set()
    for style in DESIGNER_BRUSH_STYLE_IDS:
        image = QImage(240, 84, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        try:
            DrawingCanvas._paint_stroke(
                painter,
                Stroke(
                    points=[(0.08, 0.70), (0.34, 0.26), (0.62, 0.68), (0.92, 0.30)],
                    color=(76, 142, 208),
                    opacity=232,
                    width_px=24,
                    brush_style=style,
                ),
                image.width(),
                image.height(),
            )
        finally:
            painter.end()
        alpha_count = 0
        alpha_sum = 0
        for y in range(0, image.height(), 2):
            for x in range(0, image.width(), 2):
                pixel_alpha = image.pixelColor(x, y).alpha()
                if pixel_alpha > 0:
                    alpha_count += 1
                    alpha_sum += pixel_alpha
        assert alpha_count > 8, style
        signatures.add((alpha_count, alpha_sum // max(1, alpha_count)))
    assert len(signatures) >= len(DESIGNER_BRUSH_STYLE_IDS) - 2


def test_standalone_painter_starts_with_photoshop_style_layers_and_paths(monkeypatch, tmp_path) -> None:
    app = _app()
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtWidgets import QApplication, QInputDialog

    from app.drawing import (
        PAINT_CLIPBOARD_MIME,
        PaintDialog,
        Stroke,
        create_blank_paint_pixmap,
    )
    from app.i18n import tr

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    layer_labels = [dialog._layer_list.item(i).text() for i in range(dialog._layer_list.count())]
    assert any("Layer 1" in label for label in layer_labels)
    assert any(tr("paint.layer.background") in label for label in layer_labels)
    assert dialog._path_list.item(0).text().startswith("Work Path")
    assert dialog._build_canvas_context_menu().actions()[0].text() == "Copy"

    dialog._set_tool("pan")
    assert dialog.pan_btn.isChecked()
    dialog._set_tool("rect_select")
    assert dialog.rect_select_btn.isChecked()
    assert dialog.selection_aspect_combo.isEnabled()
    dialog._set_tool("ellipse_select")
    assert dialog.ellipse_select_btn.isChecked()
    dialog._set_tool("crop")
    assert dialog.crop_btn.isChecked()
    assert dialog.crop_apply_btn.isEnabled() is False
    dialog._set_tool("magic_select")
    assert dialog.magic_select_btn.isChecked()
    assert dialog.magic_tolerance_slider.isEnabled()
    dialog._set_quick_mask_enabled(True)
    assert dialog.quick_mask_btn.isChecked()
    dialog._set_grid_options(visible=True, snap=True, size_px=32)
    assert dialog.grid_view_btn.isChecked()
    assert dialog.snap_grid_btn.isChecked()
    assert dialog.canvas.grid_options()["size_px"] == 32
    dialog._set_zoom_percent(200)
    dialog._pan_canvas_by(QPoint(40, 20))
    assert dialog._canvas_pan != QPoint(0, 0)
    dialog._zoom_fit()
    assert dialog._canvas_pan == QPoint(0, 0)
    dialog._set_zoom_percent(800)
    app.processEvents()
    pixel_grid = dialog.canvas.pixel_grid_state()
    assert pixel_grid["visible"] is True
    assert pixel_grid["stride_x"] >= 1
    assert pixel_grid["cell_width_px"] > 0
    state = dialog.painter_action_state()
    assert state["view"]["zoom_percent"] == 800
    assert state["view"]["pixel_grid_visible"] is True
    dialog._zoom_fit()

    dialog._new_paint_layer()
    active_layer_id = dialog._active_paint_layer_id
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Ink cleanup", True),
    )
    dialog._rename_layer_item(dialog._layer_list.currentItem())
    assert dialog._active_paint_layer().name == "Ink cleanup"
    assert dialog._set_layer_color_label(active_layer_id, "violet") is True
    assert dialog._active_paint_layer().color_label == "violet"
    assert dialog.painter_action_state()["layers"][-1]["color_label"] == "violet"
    color_item = next(
        dialog._layer_list.item(i)
        for i in range(dialog._layer_list.count())
        if dialog._layer_list.item(i).data(Qt.ItemDataRole.UserRole) == active_layer_id
    )
    assert color_item.data(Qt.ItemDataRole.UserRole + 1) == "violet"

    dialog._on_stroke_added(
        Stroke(points=[(0.1, 0.1), (0.2, 0.2)], layer_id="paint-layer-1")
    )
    assert dialog.canvas.embedded_strokes()[-1].layer_id == active_layer_id

    dialog.layer_opacity_slider.setValue(45)
    assert dialog._active_paint_layer().opacity == 45

    dialog._layer_lock_all_btn.setChecked(True)
    app.processEvents()
    assert dialog._active_paint_layer().locked is True
    locked_count = len(dialog.canvas.embedded_strokes())
    dialog._on_stroke_added(
        Stroke(points=[(0.3, 0.3), (0.4, 0.4)], layer_id=active_layer_id)
    )
    assert len(dialog.canvas.embedded_strokes()) == locked_count
    locked_layer_count = len(dialog._paint_layers)
    dialog._delete_layer(active_layer_id)
    assert len(dialog._paint_layers) == locked_layer_count
    assert dialog._tool_status_label.text() == tr("paint.layer.locked_status")
    dialog._layer_lock_all_btn.setChecked(False)
    app.processEvents()
    assert dialog._active_paint_layer().locked is False

    dialog._copy_selected_layer()
    clipboard_mime = QApplication.clipboard().mimeData()
    assert clipboard_mime.hasFormat(PAINT_CLIPBOARD_MIME)
    assert clipboard_mime.hasImage()
    dialog._paint_clipboard = None
    layers_before_paste = len(dialog._paint_layers)
    strokes_before_paste = len(dialog.canvas.embedded_strokes())
    dialog._paste_layer_clipboard()
    app.processEvents()
    assert len(dialog._paint_layers) == layers_before_paste + 1
    assert len(dialog.canvas.embedded_strokes()) == strokes_before_paste + 1
    QApplication.clipboard().clear()

    from PySide6.QtGui import QColor, QImage
    import app.drawing as drawing_module

    clipboard_dir = tmp_path / "paint_clipboard"
    monkeypatch.setattr(drawing_module, "PAINT_CLIPBOARD_IMAGE_DIR", clipboard_dir)
    image = QImage(80, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor("#34c8ff"))
    QApplication.clipboard().setImage(image)
    paste_action = next(
        action
        for action in dialog._build_canvas_context_menu().actions()
        if action.text() == "Paste"
    )
    assert paste_action.isEnabled()
    stickers_before_paste = len(dialog.result_stickers())
    dialog._paste_layer_clipboard()
    app.processEvents()
    assert len(dialog.result_stickers()) == stickers_before_paste + 1
    pasted_sticker = dialog.result_stickers()[-1]
    assert Path(pasted_sticker.png_path).exists()
    assert pasted_sticker.width_norm > 0
    assert pasted_sticker.height_norm > 0
    assert dialog._selected_layer_id == f"sticker:{len(dialog.result_stickers()) - 1}"

    dialog._copy_selected_layer()
    sticker_copy_mime = QApplication.clipboard().mimeData()
    assert sticker_copy_mime.hasFormat(PAINT_CLIPBOARD_MIME)
    assert sticker_copy_mime.hasImage()

    stickers_before_cut = len(dialog.result_stickers())
    dialog._cut_selected_layer()
    app.processEvents()
    assert len(dialog.result_stickers()) == stickers_before_cut - 1
    assert QApplication.clipboard().mimeData().hasImage()
    dialog._paste_layer_clipboard()
    app.processEvents()
    assert len(dialog.result_stickers()) == stickers_before_cut
    QApplication.clipboard().clear()

    red_item = next(
        dialog._channel_list.item(i)
        for i in range(dialog._channel_list.count())
        if dialog._channel_list.item(i).text() == "Red"
    )
    dialog._select_channel_item(red_item)
    assert dialog._selected_channel == "Red"
    assert dialog._channel_visibility["Red"] is True
    dialog._toggle_channel_item_visibility(red_item)
    assert dialog._channel_visibility["Red"] is False
    assert dialog._channel_visibility["RGB"] is False
    assert dialog._selected_channel == "Red"
    assert dialog._copy_channel_image("Red") is True
    assert QApplication.clipboard().mimeData().hasImage()
    assert dialog._paste_channel_image("Alpha") is True
    red_item = next(
        dialog._channel_list.item(i)
        for i in range(dialog._channel_list.count())
        if dialog._channel_list.item(i).text() == "Red"
    )
    assert not red_item.icon().isNull()

    dialog.canvas._path_points = [QPointF(10, 10), QPointF(40, 40), QPointF(60, 12)]
    dialog._update_path_list()
    assert "3 pts" in dialog._path_list.item(0).text()
    dialog.canvas.commit_path(closed=True)
    app.processEvents()
    assert dialog.canvas.embedded_strokes()[-1].source_tool == "path"
    assert dialog.canvas.embedded_strokes()[-1].closed_path is True
    assert dialog.canvas.has_active_selection() is True
    assert dialog.canvas.selection_point_count() == 3
    phase = dialog.canvas._selection_phase
    dialog.canvas._advance_selection_march()
    assert dialog.canvas._selection_phase != phase
    assert dialog._path_list.count() >= 2
    assert any(
        "Selection" in dialog._path_list.item(i).text()
        for i in range(dialog._path_list.count())
    )
    dialog.canvas.clear_selection()
    dialog._update_path_list()
    saved_path_item = next(
        dialog._path_list.item(i)
        for i in range(dialog._path_list.count())
        if str(dialog._path_list.item(i).data(Qt.ItemDataRole.UserRole)).startswith("path:")
    )
    dialog._path_list.setCurrentItem(saved_path_item)
    dialog._select_path_item(saved_path_item)
    dialog._make_selection_from_selected_path()
    assert dialog.canvas.has_active_selection() is True
    assert dialog.canvas.selection_point_count() == 3
    dialog._invert_selection()
    assert dialog.canvas.selection_inverted() is True
    dialog._selection_to_path()
    assert dialog._path_list.count() >= 3
    assert len(dialog._undo_labels) >= 1
    dialog._select_all()
    assert dialog.canvas.selection_point_count() == 4
    assert dialog._mask_selected_layer_from_selection() is True
    assert dialog._active_paint_layer().mask_enabled is True
    assert len(dialog._active_paint_layer().mask) == 4
    dialog._deselect()
    assert dialog.canvas.has_active_selection() is False

    dialog._set_selection_aspect_mode("square")
    assert dialog._selection_aspect_mode == "square"
    dialog.canvas.select_rectangle(0.1, 0.1, 0.45, 0.35, shape="rect", aspect="square")
    dialog._update_tool_option_controls()
    assert dialog.canvas.selection_point_count() == 4
    assert dialog.crop_apply_btn.isEnabled() is True
    dialog.canvas.select_rectangle(0.1, 0.1, 0.45, 0.35, shape="ellipse", aspect="free")
    assert dialog.canvas.selection_point_count() == 32

    strokes_before_mirror = len(dialog.canvas.embedded_strokes())
    dialog._set_mirror_enabled(x=True, y=False)
    assert dialog.mirror_x_btn.isChecked()
    dialog._on_stroke_added(
        Stroke(points=[(0.1, 0.2), (0.2, 0.25)], source_tool="pen")
    )
    assert len(dialog.canvas.embedded_strokes()) == strokes_before_mirror + 2
    assert dialog.canvas.embedded_strokes()[-1].points[0][0] == 0.9

    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 0.5, shape="rect", aspect="free")
    assert dialog._crop_to_selection() is True
    assert dialog._canvas_document_size == (320, 180)
    assert dialog._resize_image_document(800, 450) is True
    assert dialog._canvas_document_size == (800, 450)
    assert dialog._resize_canvas_document(1000, 600) is True
    assert dialog._canvas_document_size == (1000, 600)

    dialog.close()


def test_standalone_painter_can_delete_background_to_checkerboard_alpha() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    dialog._selected_layer_id = "background"
    dialog._update_layer_list()
    assert dialog._layer_list.currentItem().data(Qt.ItemDataRole.UserRole) == "background"
    dialog._delete_selected_layer()
    app.processEvents()

    layer_ids = [
        dialog._layer_list.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dialog._layer_list.count())
    ]
    assert "background" not in layer_ids
    assert dialog._background_layer_present is False
    assert dialog._export_background_pixmap() is None

    checker = dialog._display_background_pixmap().toImage()
    assert checker.pixelColor(1, 1) != checker.pixelColor(25, 1)

    dialog._undo()
    app.processEvents()
    restored_layer_ids = [
        dialog._layer_list.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dialog._layer_list.count())
    ]
    assert "background" in restored_layer_ids
    assert dialog._background_layer_present is True
    assert dialog._export_background_pixmap() is not None

    dialog.close()
