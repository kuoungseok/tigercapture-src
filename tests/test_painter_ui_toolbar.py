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
    parent.show()
    toolbar.show()
    toolbar.tool_buttons["frame"].click()
    toolbar.zoom_button.click()
    app.processEvents()
    assert toolbar.zoom_popover.isVisible()
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
    assert not toolbar.tool_buttons["ellipse"].isHidden()
    assert not toolbar.tool_buttons["image"].isHidden()
    assert not toolbar.zoom_button.isHidden()
    assert toolbar.view_buttons["selection"].parentWidget() is toolbar.zoom_popover

    toolbar.sync_density(900)
    assert not toolbar.tool_buttons["ellipse"].isHidden()
    assert not toolbar.tool_buttons["image"].isHidden()
    assert not toolbar.zoom_button.isHidden()
    toolbar.deleteLater()
    parent.deleteLater()


def test_zoom_popover_emits_percent_and_transient_indicator() -> None:
    app = _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    parent = QWidget()
    parent.resize(720, 480)
    toolbar = PainterUIFloatingToolbar(parent)
    zooms: list[float] = []
    toolbar.zoom_requested.connect(zooms.append)
    parent.show()
    toolbar.show()
    toolbar.place_in_parent()
    toolbar.zoom_button.click()
    app.processEvents()

    toolbar.zoom_popover.percent_spin.setValue(175)
    toolbar.zoom_popover.percent_spin.editingFinished.emit()
    assert zooms == [175.0]

    toolbar.zoom_popover.set_zoom_percent(100)
    toolbar.zoom_popover.zoom_in_button.click()
    toolbar.zoom_popover.zoom_out_button.click()
    assert zooms[-2:] == [125.0, 100.0]
    assert not toolbar.zoom_popover.zoom_in_button.icon().isNull()
    assert not toolbar.zoom_popover.zoom_out_button.icon().isNull()

    toolbar.zoom_popover.hide()
    toolbar.set_zoom_percent(212.4)
    app.processEvents()
    assert toolbar.zoom_indicator.text() == "212%"
    assert toolbar.zoom_indicator.isVisible()
    assert (
        toolbar.zoom_indicator.geometry().bottom()
        < toolbar.geometry().top()
    )

    parent.deleteLater()
    app.processEvents()


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


def test_floating_toolbar_exposes_dedicated_vector_pen_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar.tool_buttons["path"].click()

    assert emitted == ["path"]
    assert toolbar.tool_buttons["path"].isChecked()
    assert toolbar.tool_buttons["path"] is not toolbar.tool_buttons["rectangle"]
    toolbar.deleteLater()


def test_floating_toolbar_exposes_dedicated_scale_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar.tool_buttons["scale"].click()

    assert emitted == ["scale"]
    assert toolbar.tool_buttons["scale"].isChecked()
    assert not toolbar.tool_buttons["select"].isChecked()
    toolbar.deleteLater()


def test_floating_toolbar_exposes_hand_pan_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar.tool_buttons["pan"].click()

    assert emitted == ["pan"]
    assert toolbar.tool_buttons["pan"].isChecked()
    assert not toolbar.tool_buttons["pan"].icon().isNull()
    assert "Hand" in toolbar.tool_buttons["pan"].accessibleName()
    toolbar.deleteLater()


def test_floating_toolbar_group_flyouts_switch_tools() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)
    toolbar._tool_actions["ellipse"].trigger()
    toolbar._tool_actions["polygon"].trigger()
    toolbar._tool_actions["star"].trigger()
    toolbar._tool_actions["arc"].trigger()
    toolbar._tool_actions["image"].trigger()

    assert emitted == ["ellipse", "polygon", "star", "arc", "image"]
    assert toolbar.tool_buttons["image"].isChecked()
    assert toolbar.tool_buttons["ellipse"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["polygon"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["star"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["arc"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["image"] is toolbar.tool_buttons["text"]
    toolbar.deleteLater()


def test_floating_toolbar_guide_menu_emits_intents_and_syncs_state() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    visibility: list[bool] = []
    locked: list[bool] = []
    cleared: list[bool] = []
    reset: list[bool] = []
    toolbar.guide_visibility_changed.connect(visibility.append)
    toolbar.guide_lock_changed.connect(locked.append)
    toolbar.guide_clear_requested.connect(lambda: cleared.append(True))
    toolbar.ruler_origin_reset_requested.connect(lambda: reset.append(True))

    toolbar.guide_visibility_action.setChecked(False)
    toolbar.guide_lock_action.setChecked(True)
    toolbar.guide_clear_action.trigger()
    toolbar.ruler_origin_reset_action.trigger()
    assert visibility == [False]
    assert locked == [True]
    assert cleared == [True]
    assert reset == [True]

    toolbar.set_guide_state(visible=True, locked=False)
    assert toolbar.guide_visibility_action.isChecked()
    assert not toolbar.guide_lock_action.isChecked()
    assert visibility == [False]
    assert locked == [True]
    toolbar.deleteLater()
