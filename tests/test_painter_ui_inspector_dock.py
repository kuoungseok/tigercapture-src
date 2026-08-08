from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_frame_tool_replaces_page_properties_with_frame_presets() -> None:
    app = _app()
    from PySide6.QtWidgets import QPushButton
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    inspector.set_document(create_ui_document(1440, 900))
    assert not inspector.page_properties_panel.isHidden()
    assert inspector.frame_presets_panel.isHidden()

    inspector.set_active_tool_context("frame")
    assert inspector.page_properties_panel.isHidden()
    assert not inspector.frame_presets_panel.isHidden()
    assert inspector.frame_presets_panel.title.text() == "프레임"

    emitted: list[tuple[str, int, int]] = []
    inspector.frame_preset_requested.connect(
        lambda name, width, height: emitted.append((name, width, height))
    )
    smartphone_group = inspector.frame_presets_panel._groups_host
    first_rows = smartphone_group.findChildren(QPushButton)
    next(
        button
        for button in first_rows
        if button.accessibleName() == "iPhone 17"
    ).click()
    assert emitted == [("iPhone 17", 402, 874)]

    panel = inspector.frame_presets_panel
    assert panel._group_toggles[0].isChecked()
    assert not panel._group_rows[0].isHidden()
    panel._group_toggles[1].click()
    assert not panel._group_toggles[0].isChecked()
    assert panel._group_rows[0].isHidden()
    assert panel._group_toggles[1].isChecked()
    assert not panel._group_rows[1].isHidden()
    assert sum(not row.isHidden() for row in panel._group_rows) == 1

    inspector.set_active_tool_context("section")
    assert inspector.frame_presets_panel.title.text() == "섹션"
    assert inspector.frame_presets_panel.help.isVisibleTo(inspector)
    inspector.set_active_tool_context("select")
    assert inspector.frame_presets_panel.isHidden()
    assert not inspector.page_properties_panel.isHidden()
    inspector.deleteLater()
    app.processEvents()


def test_ui_design_inspector_uses_remaining_vertical_dock_space() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 700, "#F5F5F5"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    layout = dialog._paint_inspector_controls_layout
    inspector_index = layout.indexOf(dialog._paint_ui_inspector)

    assert layout.stretch(inspector_index) == 1
    assert layout.stretch(dialog._paint_inspector_tail_stretch_index) == 0

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_selected_frame_exposes_compact_editing_inspector() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, frame = add_ui_object(
        create_ui_document(1440, 1024),
        kind="frame",
        name="Desktop - 1",
        x=12,
        y=24,
        width=1440,
        height=1024,
    )
    inspector = PainterUIInspector()
    geometries: list[tuple[str, dict]] = []
    arrangements: list[tuple[str, str]] = []
    properties: list[tuple[str, dict]] = []
    inspector.geometry_changed.connect(
        lambda object_id, changes: geometries.append(
            (object_id, dict(changes))
        )
    )
    inspector.arrange_requested.connect(
        lambda object_id, command: arrangements.append(
            (object_id, command)
        )
    )
    inspector.properties_changed.connect(
        lambda object_id, changes: properties.append((object_id, dict(changes)))
    )
    inspector.set_document(document)

    panel = inspector.frame_selection_panel
    assert not panel.isHidden()
    assert inspector.object_properties_host.isHidden()
    assert panel.title.text() == "Desktop - 1"
    assert panel.geometry_controls["x"].value() == 12.0
    assert panel.geometry_controls["y"].value() == 24.0
    assert panel.width_spin.value() == 1440.0
    assert panel.height_spin.value() == 1024.0
    assert panel.fill_editor.paints()[0]["type"] == "solid"
    assert panel.stroke_editor.paints() == []

    panel.width_spin.setValue(1280.0)
    panel.width_spin.editingFinished.emit()
    assert geometries[-1][0] == frame["id"]
    assert geometries[-1][1]["width"] == 1280.0
    panel.align_buttons["hcenter"].click()
    assert arrangements[-1] == (frame["id"], "hcenter")
    panel.fill_editor._paints[0]["type"] = "pattern"
    panel.fill_editor._paints[0]["pattern"] = {
        "kind": "grid",
        "foreground": "#000000FF",
        "background": "#FFFFFFFF",
        "scale": 8,
        "source_id": "",
    }
    panel.fill_editor._commit()
    assert properties[-1][0] == frame["id"]
    assert properties[-1][1]["style"]["fills"][0]["type"] == "pattern"
    inspector.deleteLater()
    app.processEvents()


def test_selected_frame_exposes_auto_and_manual_umg_panel_kind() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, frame = add_ui_object(
        create_ui_document(640, 360),
        kind="frame",
        name="HUD Stack",
        x=24,
        y=24,
        width=480,
        height=260,
    )
    document, _child = add_ui_object(
        document,
        kind="button",
        name="Continue",
        parent_id=frame["id"],
        x=48,
        y=180,
        width=180,
        height=48,
    )
    document["selection"] = {
        "object_id": frame["id"],
        "object_ids": [frame["id"]],
    }
    inspector = PainterUIInspector()
    changes: list[tuple[str, dict]] = []
    inspector.properties_changed.connect(
        lambda object_id, payload: changes.append(
            (str(object_id), dict(payload))
        )
    )
    inspector.set_document(document)

    selector = inspector.frame_selection_panel.umg_panel_selector
    state = inspector.frame_selection_panel.umg_panel_state()
    assert state["requested"] == "auto"
    assert state["effective"] == "Overlay"
    assert state["policy"] == "auto"
    assert state["enabled"] is True
    assert "UOverlaySlot" in state["reason_text"]

    selector.mode_combo.setCurrentIndex(
        selector.mode_combo.findData("canvas")
    )
    assert changes[-1][0] == frame["id"]
    assert changes[-1][1]["layout"]["umg_panel_mode"] == "canvas"

    from app.painter_ui_document import update_ui_object

    flow_document, _report = update_ui_object(
        document,
        frame["id"],
        {"layout": {"mode": "horizontal", "umg_panel_mode": "canvas"}},
    )
    inspector.set_document(flow_document)
    flow_state = inspector.frame_selection_panel.umg_panel_state()
    assert flow_state["effective"] == "Horizontal"
    assert flow_state["policy"] == "layout"
    assert flow_state["enabled"] is False

    leaf_document, leaf = add_ui_object(
        create_ui_document(640, 360),
        kind="frame",
        name="Metric Card",
        x=32,
        y=32,
        width=240,
        height=120,
        style={"fill": "#FFFFFFFF", "radius": 12.0},
    )
    inspector.set_document(leaf_document)
    leaf_state = inspector.frame_selection_panel.umg_panel_state()
    assert leaf_state["effective"] == "None"
    assert leaf_state["policy"] == "not_applicable"
    assert leaf_state["enabled"] is False
    assert "직계 자식이 없어" in leaf_state["reason_text"]
    assert inspector._selected_id() == leaf["id"]

    inspector.deleteLater()
    app.processEvents()


def test_selected_group_uses_the_same_umg_panel_selector_contract() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, group = add_ui_object(
        create_ui_document(640, 360),
        kind="group",
        name="Overlay Group",
        x=20,
        y=20,
        width=400,
        height=240,
    )
    document, _child = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=group["id"],
        x=40,
        y=40,
        width=180,
        height=32,
        content={"text": "Title"},
    )
    document["selection"] = {
        "object_id": group["id"],
        "object_ids": [group["id"]],
    }
    inspector = PainterUIInspector()
    changes: list[tuple[str, dict]] = []
    inspector.properties_changed.connect(
        lambda object_id, payload: changes.append(
            (str(object_id), dict(payload))
        )
    )
    inspector.set_document(document)

    selector = inspector.auto_layout_umg_panel_control
    state = selector.state()
    assert state["effective"] == "Overlay"
    assert state["enabled"] is True
    assert state["status"] == "Auto → Overlay"
    selector.mode_combo.setCurrentIndex(
        selector.mode_combo.findData("canvas")
    )
    assert changes[-1][0] == group["id"]
    assert changes[-1][1]["layout"]["umg_panel_mode"] == "canvas"

    inspector.deleteLater()
    app.processEvents()


def test_selected_shape_swaps_shell_to_shape_inspector() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    document, frame = add_ui_object(
        create_ui_document(1440, 900),
        kind="frame",
        name="Desktop",
        x=100,
        y=100,
        width=900,
        height=600,
    )
    document, rectangle = add_ui_object(
        document,
        kind="rectangle",
        name="Rectangle 1",
        parent_id=frame["id"],
        x=160,
        y=180,
        width=240,
        height=120,
        style={"fill": "#D9D9D9", "radius": 8},
    )
    inspector = PainterUIInspector()
    geometries: list[tuple[str, dict]] = []
    properties: list[tuple[str, dict]] = []
    inspector.geometry_changed.connect(
        lambda object_id, changes: geometries.append(
            (object_id, dict(changes))
        )
    )
    inspector.properties_changed.connect(
        lambda object_id, changes: properties.append(
            (object_id, dict(changes))
        )
    )
    inspector.set_document(document)

    panel = inspector.shape_selection_panel
    assert inspector.selection_content_stack.currentWidget() is (
        inspector.shape_selection_scroll
    )
    assert panel.geometry_controls["width"].value() == 240.0
    assert "Desktop" in panel.parent_hint.text()
    assert panel.fill_editor.paints()[0]["color"] == "#D9D9D9"
    assert set(panel.header_buttons) == {
        "properties", "component", "appearance", "more"
    }
    assert all(not button.icon().isNull() for button in panel.align_buttons.values())

    panel.geometry_controls["width"].setValue(320.0)
    panel.geometry_controls["width"].editingFinished.emit()
    assert geometries[-1][0] == rectangle["id"]
    assert geometries[-1][1]["width"] == 320.0
    panel.flip_horizontal_button.click()
    assert properties[-1][0] == rectangle["id"]
    assert properties[-1][1]["content"]["flip_x"] is True
    panel.corner_mode_button.setChecked(True)
    panel.corner_controls["top_left"].setValue(4.0)
    panel.corner_controls["top_right"].setValue(12.0)
    panel.corner_controls["top_right"].editingFinished.emit()
    radii = properties[-1][1]["style"]["corner_radii"]
    assert radii["top_left"] == 4.0
    assert radii["top_right"] == 12.0
    inspector.deleteLater()
    app.processEvents()


def test_page_style_menu_opens_text_style_depth_and_emits_style() -> None:
    app = _app()
    from app.painter_ui_document import create_ui_document
    from app.painter_ui_inspector import PainterUIInspector

    inspector = PainterUIInspector()
    inspector.set_document(create_ui_document(1440, 900))
    kinds = [
        str(action.data() or "")
        for action in inspector.page_style_menu.actions()
    ]
    assert kinds == ["text", "color", "effect", "layout_grid"]

    created: list[dict] = []
    inspector.style_add_requested.connect(
        lambda values: created.append(dict(values))
    )
    inspector._open_text_style_dialog()
    dialog = inspector._text_style_dialog
    assert dialog.isVisible()
    dialog.name_edit.setText("Typography / Body")
    dialog.description_edit.setText("Default body copy")
    dialog.size_spin.setValue(16.0)
    dialog.line_height_spin.setValue(24.0)
    dialog.letter_spacing_spin.setValue(1.5)
    dialog.create_button.click()
    assert created[-1]["kind"] == "text"
    assert created[-1]["name"] == "Typography / Body"
    assert created[-1]["properties"]["font_size"] == 16.0
    assert created[-1]["properties"]["line_height"] == 24.0
    assert created[-1]["properties"]["letter_spacing"] == 1.5
    inspector.deleteLater()
    app.processEvents()


def test_text_style_dialog_registers_style_in_painter_document() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    inspector = dialog._paint_ui_inspector
    inspector._open_text_style_dialog()
    style_dialog = inspector._text_style_dialog
    style_dialog.name_edit.setText("Typography / Body")
    style_dialog.size_spin.setValue(16.0)
    style_dialog.create_button.click()
    styles = dialog._painter_ui_document["styles"]
    assert styles[-1]["kind"] == "text"
    assert styles[-1]["name"] == "Typography / Body"
    assert styles[-1]["properties"]["font_size"] == 16.0
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_inspector_dock_window_preserves_the_canonical_widget() -> None:
    app = _app()
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_inspector_dock import PainterUIInspectorDockWindow

    window = PainterUIInspectorDockWindow()
    content = QWidget()
    requested: list[bool] = []
    window.dock_requested.connect(lambda: requested.append(True))

    window.attach(content)
    assert window.scroll_area.widget() is content
    assert content.parent() is window.scroll_area.viewport()
    assert window.take() is content
    assert content.parent() is None

    window.attach(content)
    window.show()
    app.processEvents()
    window.close()
    app.processEvents()
    assert requested == [True]
    assert window.isVisible()

    window.hide()
    content.deleteLater()
    window.deleteLater()


def test_inspector_dock_window_closes_when_its_owner_closes() -> None:
    app = _app()
    import shiboken6
    from PySide6.QtWidgets import QWidget

    from app.painter_ui_inspector_dock import PainterUIInspectorDockWindow

    owner = QWidget()
    window = PainterUIInspectorDockWindow(owner)
    content = QWidget()
    requested: list[bool] = []
    window.dock_requested.connect(lambda: requested.append(True))
    window.attach(content)
    owner.show()
    window.show()
    app.processEvents()

    owner.close()
    app.processEvents()

    assert not shiboken6.isValid(window) or not window.isVisible()
    assert requested == []
    owner.deleteLater()
    app.processEvents()


def test_ui_inspector_resizes_detaches_and_restores_on_mode_change() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1500, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._painter_ui_navigator.set_auto_hide(True)
    dialog.show()
    app.processEvents()

    assert not dialog._paint_ui_inspector.is_auto_hide()
    assert not dialog._paint_ui_inspector.is_collapsed()
    assert dialog._paint_inspector_frame.maximumWidth() > 420
    assert not dialog._paint_ui_inspector.is_collapsed()
    assert not dialog._paint_ui_inspector.dock_button.isVisible()
    assert (
        dialog._set_painter_ui_inspector_width(
            340,
            user_initiated=True,
        )
        == 340
    )
    assert dialog._paint_inspector_frame.minimumWidth() == 180
    assert dialog._paint_inspector_frame.maximumWidth() > 420
    assert abs(dialog._paint_inspector_frame.width() - 340) <= 2

    dialog._paint_ui_inspector.set_auto_hide(True)
    assert dialog._paint_inspector_frame.maximumWidth() == 0
    assert not dialog._paint_ui_inspector.dock_button.isVisible()
    dialog._paint_ui_inspector.set_auto_hide(False)
    assert dialog._paint_inspector_frame.minimumWidth() == 180
    assert dialog._paint_inspector_frame.maximumWidth() > 420
    assert abs(dialog._paint_inspector_frame.width() - 340) <= 2

    dialog._detach_painter_ui_inspector()
    app.processEvents()
    window = dialog._painter_ui_inspector_dock_window
    assert dialog._painter_ui_inspector_detached is True
    assert (
        dialog._paint_ui_inspector.parent()
        is window.scroll_area.viewport()
    )
    assert window.isVisible()
    assert not dialog._paint_inspector_frame.isVisible()
    from app.i18n import current_language
    from app.painter_i18n import painter_text

    assert dialog._paint_ui_inspector.dock_button.toolTip() == painter_text(
        "Dock inspector",
        current_language(),
    )

    dialog._dock_painter_ui_inspector()
    app.processEvents()
    assert dialog._painter_ui_inspector_detached is False
    assert dialog._paint_ui_inspector.parent() is dialog._paint_inspector_controls
    assert dialog._paint_inspector_frame.isVisible()
    assert dialog._paint_inspector_frame.minimumWidth() == 180
    assert dialog._paint_inspector_frame.maximumWidth() > 420
    assert abs(dialog._paint_inspector_frame.width() - 340) <= 2

    dialog._detach_painter_ui_inspector()
    dialog._set_canvas_workspace_mode("paint")
    app.processEvents()
    assert dialog._painter_ui_inspector_detached is False
    assert not window.isVisible()
    assert dialog._paint_inspector_frame.isVisible()

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_inspector_presentation_action_switches_all_three_modes() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    registry = ActionRegistry(owner=dialog)

    auto = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "auto_hide"},
    )
    assert auto.ok
    assert auto.result["inspector_presentation"] == {
        "mode": "auto_hide",
        "auto_hide": True,
        "detached": False,
    }
    assert dialog._paint_inspector_frame.maximumWidth() == 0

    pinned = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "pinned"},
    )
    assert pinned.ok
    assert pinned.result["inspector_presentation"]["mode"] == "pinned"
    assert not dialog._paint_ui_inspector.is_collapsed()

    floating = registry.execute(
        "paint.ui.inspector.presentation",
        {"mode": "floating"},
    )
    app.processEvents()
    assert floating.ok
    assert floating.result["inspector_presentation"] == {
        "mode": "floating",
        "auto_hide": False,
        "detached": True,
    }
    assert dialog._painter_ui_inspector_dock_window.isVisible()

    dialog._dock_painter_ui_inspector()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_navigator_presentation_action_switches_all_three_modes() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            390,
            844,
            "#F5F7FA",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    registry = ActionRegistry(owner=dialog)

    auto = registry.execute(
        "paint.ui.navigator.presentation",
        {"mode": "auto_hide"},
    )
    assert auto.ok
    assert auto.result["navigator_presentation"] == {
        "mode": "auto_hide",
        "auto_hide": True,
        "detached": False,
    }
    assert (
        dialog._painter_ui_navigator.maximumWidth()
        == dialog._painter_ui_navigator.RAIL_WIDTH
    )

    pinned = registry.execute(
        "paint.ui.navigator.presentation",
        {"mode": "pinned"},
    )
    assert pinned.ok
    assert pinned.result["navigator_presentation"]["mode"] == "pinned"
    assert not dialog._painter_ui_navigator.is_collapsed()

    floating = registry.execute(
        "paint.ui.navigator.presentation",
        {"mode": "floating"},
    )
    app.processEvents()
    assert floating.ok
    assert floating.result["navigator_presentation"] == {
        "mode": "floating",
        "auto_hide": False,
        "detached": True,
    }
    assert dialog._painter_ui_navigator_dock_window.isVisible()

    dialog._dock_painter_ui_navigator()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_workspace_splitter_freely_resizes_both_side_panels() -> None:
    app = _app()
    from PySide6.QtWidgets import QSplitter

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(390, 844, "#F5F7FA"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1500, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._paint_ui_inspector.set_auto_hide(False)
    dialog.show()
    app.processEvents()
    dialog._painter_ui_navigator.set_collapsed(False)
    app.processEvents()

    splitter = dialog._paint_workspace_layout
    assert isinstance(splitter, QSplitter)
    assert splitter.count() == 4
    assert (
        dialog._painter_ui_navigator.minimumWidth()
        == dialog._painter_ui_navigator.MIN_EXPANDED_WIDTH
    )
    assert dialog._painter_ui_navigator.maximumWidth() > 320
    assert dialog._paint_inspector_frame.minimumWidth() == 180
    assert dialog._paint_inspector_frame.maximumWidth() > 420

    navigator_before = dialog._painter_ui_navigator.width()
    splitter.moveSplitter(splitter.handle(2).x() + 88, 2)
    app.processEvents()
    inspector_after_navigator = dialog._paint_inspector_frame.width()
    splitter.moveSplitter(splitter.handle(3).x() - 64, 3)
    app.processEvents()

    assert dialog._painter_ui_navigator.width() != navigator_before
    assert (
        abs(
            dialog._paint_inspector_frame.width()
            - inspector_after_navigator
        )
        >= 8
    )
    assert (
        dialog._painter_ui_panel_state["navigator_width"]
        == dialog._painter_ui_navigator.width()
    )
    assert (
        dialog._painter_ui_panel_state["inspector_width"]
        == dialog._paint_inspector_frame.width()
    )
    assert dialog._canvas_frame.width() >= 280

    assert dialog._painter_ui_navigator.set_expanded_width(480) == 480
    assert (
        dialog._set_painter_ui_inspector_width(
            620,
            user_initiated=True,
        )
        == 620
    )
    app.processEvents()
    assert dialog._painter_ui_navigator.expanded_width() == 480
    assert dialog._paint_inspector_expanded_width == 620
    assert dialog._paint_inspector_frame.width() >= 180

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_ui_workspace_defaults_to_visible_navigator_and_inspector() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            390,
            844,
            "#F5F7FA",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1400, 900)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()

    assert not dialog._painter_ui_navigator.is_auto_hide()
    assert not dialog._painter_ui_navigator.is_collapsed()
    assert (
        dialog._painter_ui_navigator.width()
        >= dialog._painter_ui_navigator.MIN_EXPANDED_WIDTH
    )
    assert dialog._painter_ui_navigator.width() <= 300
    assert not dialog._paint_ui_inspector.is_auto_hide()
    assert not dialog._paint_ui_inspector.is_collapsed()
    assert dialog._paint_ui_inspector.isVisible()
    assert dialog._paint_inspector_frame.width() >= 180

    dialog._toggle_painter_ui_navigator()
    app.processEvents()
    assert dialog._painter_ui_navigator.is_auto_hide()
    assert dialog._painter_ui_navigator.is_collapsed()
    assert (
        dialog._painter_ui_navigator.maximumWidth()
        == dialog._painter_ui_navigator.RAIL_WIDTH
    )

    dialog._toggle_painter_ui_navigator()
    app.processEvents()
    navigator_popover = dialog._painter_ui_navigator_popover
    assert navigator_popover.isVisible()
    assert navigator_popover.contains(dialog._painter_ui_navigator)
    assert dialog._painter_ui_navigator.is_collapsed()

    dialog._pin_painter_ui_navigator()
    app.processEvents()
    assert not dialog._painter_ui_navigator.is_collapsed()
    assert dialog._paint_workspace_layout.indexOf(
        dialog._painter_ui_navigator
    ) == 1

    dialog._toggle_painter_ui_inspector()
    app.processEvents()
    assert dialog._paint_ui_inspector.is_collapsed()
    dialog._toggle_painter_ui_inspector()
    app.processEvents()
    assert dialog._painter_ui_quick_properties.isVisible()
    assert dialog._painter_ui_quick_properties.contains(
        dialog._paint_ui_inspector
    )

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
