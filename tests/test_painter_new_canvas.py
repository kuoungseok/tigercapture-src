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
    app.processEvents()

    assert dialog._tool_rail.width() <= 56
    assert dialog.select_btn.text() == ""
    assert dialog.select_btn.toolTip() == "Select / Move"
    assert dialog.pen_btn.text() == ""
    assert dialog.pen_btn.toolTip()
    assert dialog.eraser_btn.text() == ""
    assert dialog.eraser_btn.toolTip()
    assert not dialog.select_btn.icon().isNull()
    assert not dialog.pen_btn.icon().isNull()
    assert not dialog.eraser_btn.icon().isNull()
    assert not dialog.path_btn.icon().isNull()
    assert dialog.brush_library_list.parent() is not dialog._tool_rail
    assert dialog._layer_channel_path_tabs.count() == 3
    assert [
        dialog._layer_channel_path_tabs.tabText(i)
        for i in range(dialog._layer_channel_path_tabs.count())
    ] == [tr("paint.tab.layers"), tr("paint.tab.channels"), tr("paint.tab.paths")]
    assert dialog._channel_list.item(0).text() == "RGB"
    assert dialog.color_wheel.width() <= 112
    assert dialog._color_preview.width() <= 48
    assert dialog._recent_color_btns[0].width() <= 32
    assert dialog._palette_btns[0].width() <= 38

    dialog.close()


def test_standalone_painter_starts_with_photoshop_style_layers_and_paths() -> None:
    app = _app()
    from PySide6.QtCore import QPointF

    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

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
    assert any("Background" in label for label in layer_labels)
    assert dialog._path_list.item(0).text().startswith("Work Path")

    dialog._new_paint_layer()
    active_layer_id = dialog._active_paint_layer_id
    dialog._on_stroke_added(
        Stroke(points=[(0.1, 0.1), (0.2, 0.2)], layer_id="paint-layer-1")
    )
    assert dialog.canvas.embedded_strokes()[-1].layer_id == active_layer_id

    dialog.layer_opacity_slider.setValue(45)
    assert dialog._active_paint_layer().opacity == 45

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
