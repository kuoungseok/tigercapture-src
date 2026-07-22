from __future__ import annotations

import os


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


def test_standalone_painter_hides_video_annotation_tools() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    assert dialog.windowTitle() == "Painter - TigerCapture"
    assert dialog.bubble_btn.isHidden()
    assert dialog.sticker_btn.isHidden()
    assert dialog.editor_object_btn.isHidden()
    assert dialog.cutout_btn.isHidden()

    dialog.close()


def test_standalone_painter_uses_vector_icons_and_compact_palette() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
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

    assert dialog.isSizeGripEnabled()
    assert dialog.minimumWidth() <= 760
    assert dialog._tool_rail.width() <= 56
    assert dialog.select_btn.text() == ""
    assert dialog.select_btn.toolTip() == "Select / Move"
    assert dialog.pan_btn.text() == ""
    assert dialog.pan_btn.toolTip() == "Pan canvas"
    assert dialog.pen_btn.text() == ""
    assert dialog.pen_btn.toolTip()
    assert dialog.eraser_btn.text() == ""
    assert dialog.eraser_btn.toolTip()
    assert not dialog.select_btn.icon().isNull()
    assert not dialog.pan_btn.icon().isNull()
    assert not dialog.pen_btn.icon().isNull()
    assert not dialog.eraser_btn.icon().isNull()
    assert not dialog.path_btn.icon().isNull()
    assert dialog.brush_library_list.parent() is not dialog._tool_rail
    assert dialog._layer_channel_path_tabs.count() == 4
    assert [
        dialog._layer_channel_path_tabs.tabText(i)
        for i in range(dialog._layer_channel_path_tabs.count())
    ] == [tr("paint.tab.layers"), tr("paint.tab.channels"), tr("paint.tab.paths"), "History"]
    menu_labels = [
        action.text().replace("&", "")
        for action in dialog._painter_menu_bar.actions()
    ]
    assert menu_labels == ["File", "Edit", "View", "Image", "Layer", "Select", "Path", "Window"]
    assert dialog.layer_filter_combo.currentText() == tr("paint.layer.filter_kind")
    assert dialog.layer_blend_combo.currentText() == tr("paint.layer.blend_normal")
    assert dialog._layer_opacity_value.text() == "100%"
    assert dialog._layer_fill_value.text() == "100%"
    assert not dialog._layer_lock_all_btn.isChecked()
    assert dialog._channel_list.item(0).text() == "RGB"
    assert not dialog._channel_list.item(0).icon().isNull()
    assert dialog.color_wheel.width() <= 112
    assert dialog._color_preview.width() <= 48
    assert dialog._recent_color_btns[0].width() <= 32
    assert dialog._palette_btns[0].width() <= 38
    scroll = dialog._paint_inspector_controls_scroll
    assert scroll.geometry().bottom() < dialog._layer_channel_path_tabs.geometry().top()
    margins = dialog._paint_inspector_controls.layout().contentsMargins()
    assert margins.right() >= 12
    bar = scroll.verticalScrollBar()
    if bar.isVisible():
        color_right = dialog._paint_color_panel.mapToGlobal(
            dialog._paint_color_panel.rect().topRight()
        ).x()
        bar_left = bar.mapToGlobal(bar.rect().topLeft()).x()
        assert color_right < bar_left

    dialog.close()


def test_standalone_painter_starts_with_photoshop_style_layers_and_paths(monkeypatch) -> None:
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
    dialog._set_zoom_percent(200)
    dialog._pan_canvas_by(QPoint(40, 20))
    assert dialog._canvas_pan != QPoint(0, 0)
    dialog._zoom_fit()
    assert dialog._canvas_pan == QPoint(0, 0)

    dialog._new_paint_layer()
    active_layer_id = dialog._active_paint_layer_id
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Ink cleanup", True),
    )
    dialog._rename_layer_item(dialog._layer_list.currentItem())
    assert dialog._active_paint_layer().name == "Ink cleanup"

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
    dialog._paint_clipboard = None
    layers_before_paste = len(dialog._paint_layers)
    strokes_before_paste = len(dialog.canvas.embedded_strokes())
    dialog._paste_layer_clipboard()
    app.processEvents()
    assert len(dialog._paint_layers) == layers_before_paste + 1
    assert len(dialog.canvas.embedded_strokes()) == strokes_before_paste + 1
    QApplication.clipboard().clear()

    red_item = next(
        dialog._channel_list.item(i)
        for i in range(dialog._channel_list.count())
        if dialog._channel_list.item(i).text() == "Red"
    )
    dialog._toggle_channel_item_visibility(red_item)
    assert dialog._channel_visibility["Red"] is False
    assert dialog._channel_visibility["RGB"] is False
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
    assert dialog._history_list.count() >= 2
    dialog._select_all()
    assert dialog.canvas.selection_point_count() == 4
    dialog._deselect()
    assert dialog.canvas.has_active_selection() is False

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
