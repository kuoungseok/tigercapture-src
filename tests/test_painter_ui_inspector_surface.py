from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_object_inspector_scroll_surface_keeps_dark_styled_background() -> None:
    app = _app()
    from PySide6.QtCore import Qt

    from app.drawing import _PAINT_DIALOG_QSS
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    inspector.setStyleSheet(_PAINT_DIALOG_QSS)
    inspector.resize(420, 760)
    inspector.show()
    app.processEvents()

    assert inspector.object_properties_host.objectName() == (
        "PainterUIObjectPropertiesHost"
    )
    assert inspector.object_properties_host.testAttribute(
        Qt.WidgetAttribute.WA_StyledBackground
    )
    assert inspector.object_properties_scroll.viewport().objectName() == (
        "PainterUIObjectPropertiesViewport"
    )
    assert inspector.object_properties_scroll.viewport().testAttribute(
        Qt.WidgetAttribute.WA_StyledBackground
    )
    assert "QWidget#PainterUIObjectPropertiesViewport" in _PAINT_DIALOG_QSS
    assert "QWidget#PainterUIObjectPropertiesHost" in _PAINT_DIALOG_QSS
    inspector.close()
