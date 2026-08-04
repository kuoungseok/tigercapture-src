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
    assert toolbar.zoom_button.isHidden()
    assert toolbar.view_buttons["selection"].parentWidget() is toolbar.zoom_popover

    toolbar.sync_density(900)
    assert not toolbar.tool_buttons["ellipse"].isHidden()
    assert not toolbar.tool_buttons["image"].isHidden()
    assert toolbar.zoom_button.isHidden()
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


def test_text_tool_uses_t_mark_and_official_figma_primary_order() -> None:
    _app()
    from app.drawing import _PAINT_DIALOG_QSS
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    layout = toolbar.layout()
    text_button = toolbar.tool_buttons["text"]

    assert text_button.text() == "T"
    assert text_button.icon().isNull()
    text_rule = _PAINT_DIALOG_QSS.split(
        'QPushButton#PainterUIFloatingToolButton[painterTextTool="true"] {',
        1,
    )[1].split("}", 1)[0]
    assert "color: #e4e8ee;" in text_rule
    assert text_button.accessibleName() == "텍스트 (T)"
    assert layout.indexOf(toolbar.tool_buttons["path"]) < layout.indexOf(text_button)
    assert layout.indexOf(text_button) < layout.indexOf(toolbar.comment_button)
    assert layout.indexOf(toolbar.comment_button) < layout.indexOf(
        toolbar.resources_button
    )
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


def test_creation_tools_group_exposes_pen_and_pencil() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar._tool_actions["pencil"].trigger()

    assert emitted == ["pencil"]
    assert toolbar.tool_buttons["pencil"] is toolbar.tool_buttons["path"]
    assert toolbar.tool_buttons["pencil"].isChecked()
    assert toolbar.tool_buttons["pencil"].defaultAction().data() == "pencil"
    assert not toolbar.tool_buttons["pencil"].icon().isNull()
    toolbar.deleteLater()


def test_floating_toolbar_exposes_dedicated_scale_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar._tool_actions["scale"].trigger()

    assert emitted == ["scale"]
    assert toolbar.tool_buttons["scale"].isChecked()
    assert toolbar.tool_buttons["scale"] is toolbar.tool_buttons["select"]
    toolbar.deleteLater()


def test_floating_toolbar_exposes_hand_pan_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    toolbar._tool_actions["pan"].trigger()

    assert emitted == ["pan"]
    assert toolbar.tool_buttons["pan"].isChecked()
    assert not toolbar.tool_buttons["pan"].icon().isNull()
    assert "손 도구" in toolbar.tool_buttons["pan"].accessibleName()
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
    toolbar._tool_actions["arrow"].trigger()
    toolbar._tool_actions["image"].trigger()

    assert emitted == ["ellipse", "polygon", "star", "arrow", "image"]
    assert toolbar.tool_buttons["image"].isChecked()
    assert toolbar.tool_buttons["ellipse"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["polygon"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["star"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["arrow"] is toolbar.tool_buttons["rectangle"]
    assert toolbar.tool_buttons["image"] is toolbar.tool_buttons["rectangle"]
    toolbar.deleteLater()


def test_floating_toolbar_matches_figma_region_tool_groups() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)

    assert toolbar.tool_buttons["select"] is toolbar.tool_buttons["pan"]
    assert toolbar.tool_buttons["pan"] is toolbar.tool_buttons["scale"]
    assert toolbar.tool_buttons["frame"] is toolbar.tool_buttons["section"]
    assert toolbar.tool_buttons["section"] is toolbar.tool_buttons["slice"]
    assert toolbar.tool_buttons["rectangle"] is toolbar.tool_buttons["arrow"]
    assert toolbar.tool_buttons["arrow"] is toolbar.tool_buttons["image"]

    toolbar._tool_actions["section"].trigger()
    toolbar._tool_actions["slice"].trigger()
    toolbar._tool_actions["arrow"].trigger()
    assert emitted == ["section", "slice", "arrow"]
    assert toolbar.tool_buttons["arrow"].isChecked()
    assert toolbar.snap_button.isHidden()
    assert toolbar.motion_actor_button.isHidden()
    toolbar.deleteLater()


def test_frame_group_keeps_visible_active_state_and_roomy_spacing() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    frame_button = toolbar.tool_buttons["frame"]
    toolbar._tool_actions["frame"].trigger()

    assert frame_button.isChecked()
    assert frame_button.property("activeTool") is True
    assert toolbar.tool_buttons["select"].property("activeTool") is False
    assert toolbar.layout().spacing() >= 6
    assert toolbar.layout().contentsMargins().left() >= 8
    assert frame_button.width() >= 42
    toolbar.deleteLater()


def test_split_button_arrow_selects_the_current_group_tool() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[str] = []
    toolbar.tool_requested.connect(emitted.append)
    frame_button = toolbar.tool_buttons["frame"]

    frame_button.menu().aboutToShow.emit()
    assert emitted == ["frame"]
    assert frame_button.isChecked()
    assert frame_button.property("activeTool") is True

    toolbar._tool_actions["section"].trigger()
    assert frame_button.defaultAction().data() == "section"
    toolbar._tool_actions["select"].trigger()
    frame_button.menu().aboutToShow.emit()
    assert emitted[-1] == "section"
    assert frame_button.property("activeTool") is True
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


def test_floating_toolbar_focus_button_emits_checked_state() -> None:
    _app()
    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    toolbar = PainterUIFloatingToolbar()
    emitted: list[bool] = []
    toolbar.focus_mode_changed.connect(emitted.append)

    toolbar.focus_mode_button.click()

    assert emitted == [True]
    assert toolbar.focus_mode_button.isChecked()
    assert not toolbar.focus_mode_button.icon().isNull()
    toolbar.deleteLater()


def test_floating_toolbar_uses_fast_visible_tooltips() -> None:
    app = _app()
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_toolbar import PainterUIFloatingToolbar

    parent = QWidget()
    parent.resize(900, 600)
    toolbar = PainterUIFloatingToolbar(parent)
    parent.show()
    toolbar.show()
    toolbar.place_in_parent()
    toolbar._tool_actions["pan"].trigger()
    button = toolbar.tool_buttons["pan"]

    assert toolbar._fast_tooltip_timer.interval() <= 100
    assert "손 도구" in str(button.property("painter_ui_help_text"))
    toolbar.eventFilter(button, QEvent(QEvent.Type.Enter))
    toolbar._show_pending_tooltip()
    app.processEvents()

    assert toolbar._fast_tooltip.isVisible()
    assert "손 도구" in toolbar._fast_tooltip.text()
    assert "color: #f4f7fb" in toolbar._fast_tooltip.styleSheet()
    assert (
        toolbar._fast_tooltip.geometry().bottom()
        < toolbar.geometry().top()
    )

    toolbar.eventFilter(button, QEvent(QEvent.Type.Leave))
    assert not toolbar._fast_tooltip.isVisible()
    parent.deleteLater()
    app.processEvents()


def test_region_and_shape_tools_create_real_document_rows() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(1440, 900, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._set_painter_ui_tool("frame")
    assert not dialog._paint_ui_inspector.frame_presets_panel.isHidden()
    inspector_syncs: list[object] = []
    dialog._paint_ui_inspector.set_document = inspector_syncs.append

    dialog._create_painter_ui_frame_preset("iPhone 17", 402, 874)
    frame = dialog._painter_ui_document["objects"][-1]
    assert frame["kind"] == "frame"
    assert frame["name"] == "iPhone 17"
    assert (frame["width"], frame["height"]) == (402.0, 874.0)
    assert (frame["x"], frame["y"]) == (0.0, 0.0)
    assert frame["style"]["fill"] == "#FFFFFF"
    assert frame["style"]["stroke"] == "#00000000"
    assert frame["style"]["stroke_width"] == 0.0

    dialog._create_painter_ui_object_from_rect("frame", -120, -80, 320, 240)
    custom_frame = dialog._painter_ui_document["objects"][-1]
    assert custom_frame["name"] == "Frame 1"
    assert (custom_frame["x"], custom_frame["y"]) == (-120.0, -80.0)
    assert custom_frame["style"]["fill"] == "#FFFFFF"
    assert dialog._painter_ui_overlay.tool() == "select"
    assert inspector_syncs
    dialog._create_painter_ui_object_from_rect("frame", 40, 44, 280, 180)
    frame_2 = dialog._painter_ui_document["objects"][-1]
    assert frame_2["name"] == "Frame 2"

    dialog._set_painter_ui_tool("rectangle")
    dialog._create_painter_ui_object_from_rect("rectangle", 80, 80, 80, 60)
    rectangle = dialog._painter_ui_document["objects"][-1]
    assert rectangle["name"] == "Rectangle 1"
    assert rectangle["parent_id"] == frame_2["id"]
    assert rectangle["style"]["fill"] == "#D9D9D9"
    assert rectangle["style"]["stroke_width"] == 0.0
    assert dialog._painter_ui_overlay.tool() == "rectangle"
    assert dialog._paint_ui_inspector.selection_content_stack.currentWidget() is (
        dialog._paint_ui_inspector.shape_selection_scroll
    )
    shape_panel = dialog._paint_ui_inspector.shape_selection_panel
    assert shape_panel.geometry_controls["width"].value() == 80.0
    shape_panel.geometry_controls["width"].setValue(96.0)
    shape_panel.geometry_controls["width"].editingFinished.emit()
    rectangle = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == rectangle["id"]
    )
    assert rectangle["width"] == 96.0
    layer_names = [
        dialog._paint_ui_inspector.layer_list.item(index).text()
        for index in range(dialog._paint_ui_inspector.layer_list.count())
    ]
    frame_label = next(name for name in layer_names if name.strip() == "Frame 2")
    rectangle_label = next(
        name for name in layer_names if name.strip() == "Rectangle 1"
    )
    assert len(rectangle_label) - len(rectangle_label.lstrip()) >= 4
    assert len(rectangle_label) - len(rectangle_label.lstrip()) > (
        len(frame_label) - len(frame_label.lstrip())
    )
    assert inspector_syncs

    dialog._create_painter_ui_section_from_rect(20, 30, 800, 600)
    section = dialog._painter_ui_document["sections"][-1]
    assert (section["x"], section["y"]) == (20.0, 30.0)
    assert (section["width"], section["height"]) == (800.0, 600.0)

    dialog._create_painter_ui_object_from_rect("arrow", 10, 10, 160, 60)
    arrow = dialog._painter_ui_document["objects"][-1]
    assert arrow["kind"] == "line"
    assert arrow["content"]["arrow_end"] is True

    dialog._create_painter_ui_object_from_rect("slice", 40, 50, 200, 120)
    export_slice = dialog._painter_ui_document["objects"][-1]
    assert export_slice["kind"] == "frame"
    assert export_slice["content"]["export_slice"] is True
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
