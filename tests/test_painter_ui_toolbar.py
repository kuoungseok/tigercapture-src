from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_floating_toolbar_emits_intents_and_reflows() -> None:
    app = _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    parent = QWidget()
    parent.resize(900, 600)
    toolbar = PainterUIFloatingToolbar(parent)
    tools: list[str] = []
    fits: list[str] = []
    toolbar.tool_requested.connect(tools.append)
    toolbar.fit_requested.connect(fits.append)
    toolbar.show()
    toolbar.tool_buttons["frame"].click()
    toolbar.view_buttons["selection"].click()
    toolbar.place_in_parent()
    app.processEvents()

    assert tools == ["frame"]
    assert fits == ["selection"]
    assert toolbar.y() + toolbar.height() <= parent.height()
    assert abs(
        toolbar.x() - ((parent.width() - toolbar.width()) // 2)
    ) <= 1

    toolbar.sync_density(400)
    assert toolbar.tool_buttons["ellipse"].isHidden()
    assert toolbar.tool_buttons["image"].isHidden()
    assert toolbar.view_buttons["selection"].isHidden()

    toolbar.sync_density(900)
    assert not toolbar.tool_buttons["ellipse"].isHidden()
    assert not toolbar.tool_buttons["image"].isHidden()
    assert not toolbar.view_buttons["selection"].isHidden()
    toolbar.deleteLater()
    parent.deleteLater()


def test_floating_toolbar_tracks_active_tool_without_emitting() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)
    toolbar.set_active_tool("text")

    assert toolbar.tool_buttons["text"].isChecked()
    assert not toolbar.tool_buttons["select"].isChecked()
    assert emitted == []
    toolbar.deleteLater()
