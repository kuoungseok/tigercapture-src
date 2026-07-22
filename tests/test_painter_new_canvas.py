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
