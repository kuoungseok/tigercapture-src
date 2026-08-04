from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_preview_window_renders_active_artboard_and_supports_both_modes() -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_preview_window import PainterUIPreviewWindow

    document = create_ui_document(390, 844, name="Mobile")
    preview = PainterUIPreviewWindow(document, mode="preview")
    preview.open_mode()
    app.processEvents()
    assert preview.isVisible()
    assert preview._mode == "preview"
    assert preview.image_label.pixmap() is not None
    assert not preview.image_label.pixmap().isNull()
    preview.close()

    presentation = PainterUIPreviewWindow(
        document,
        mode="presentation",
    )
    presentation.open_mode()
    app.processEvents()
    assert presentation.isVisible()
    assert presentation._mode == "presentation"
    assert presentation.isFullScreen()
    presentation.close()
    app.processEvents()


def test_focus_preview_menu_opens_real_output_windows() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    controls = dialog._painter_ui_focus_controls_island

    controls.preview_action.trigger()
    app.processEvents()
    preview = dialog._painter_ui_output_windows[-1]
    assert preview._mode == "preview"
    assert preview.isVisible()
    preview.close()
    app.processEvents()

    controls.presentation_action.trigger()
    app.processEvents()
    presentation = dialog._painter_ui_output_windows[-1]
    assert presentation._mode == "presentation"
    assert presentation.isFullScreen()
    presentation.close()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_preview_window_applies_prototype_device_and_background() -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_preview_window import PainterUIPreviewWindow

    document = create_ui_document(390, 844, name="Mobile")
    window = PainterUIPreviewWindow(
        document,
        prototype_settings={
            "device": {
                "name": "iPhone 17",
                "width": 402,
                "height": 874,
                "family": "iphone",
                "orientation": "portrait",
            },
            "background": "#123456",
        },
    )
    assert window._background == "#123456"
    assert window._image.width() > 402
    assert window._image.height() > 874
    window.open_mode()
    app.processEvents()
    assert window.image_label.pixmap() is not None
    window.close()
    app.processEvents()
