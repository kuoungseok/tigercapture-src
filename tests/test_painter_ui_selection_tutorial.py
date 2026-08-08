from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _nested_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Frame 1",
        x=100,
        y=100,
        width=420,
        height=320,
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        name="Rectangle 1",
        parent_id=frame["id"],
        x=170,
        y=160,
        width=120,
        height=90,
    )
    document["selection"] = {"object_id": "", "object_ids": []}
    return document, frame, child


def test_tutorial_click_selects_parent_and_control_click_deep_selects() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _nested_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )
    point = QPoint(
        int(overlay._object_rect(child).center().x()),
        int(overlay._object_rect(child).center().y()),
    )

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=point)
    assert emitted[-1] == (frame["id"], "replace")
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=point)

    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        point,
    )
    assert emitted[-1] == (child["id"], "replace")
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        point,
    )
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_shift_click_toggles_the_parent_level_target() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _nested_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )
    point = QPoint(
        int(overlay._object_rect(child).center().x()),
        int(overlay._object_rect(child).center().y()),
    )

    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        point,
    )
    assert emitted[-1] == (frame["id"], "toggle")
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_double_click_and_enter_descend_one_level() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import select_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _nested_document()
    document = select_ui_object(document, frame["id"])
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    selected: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: selected.append((object_id, mode))
    )
    point = QPoint(
        int(overlay._object_rect(child).center().x()),
        int(overlay._object_rect(child).center().y()),
    )

    QTest.mouseDClick(overlay, Qt.MouseButton.LeftButton, pos=point)
    assert selected[-1] == (child["id"], "replace")

    selected.clear()
    QTest.keyClick(overlay, Qt.Key.Key_Return)
    assert selected[-1] == (child["id"], "replace")
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_marquee_is_top_level_unless_control_is_held() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _nested_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )
    frame_rect = overlay._object_rect(frame)
    start = QPoint(int(frame_rect.left() - 15), int(frame_rect.top() - 15))
    end = QPoint(int(frame_rect.right() + 15), int(frame_rect.bottom() + 15))

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)
    assert emitted == [(frame["id"], "replace")]

    emitted.clear()
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        start,
    )
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        end,
    )
    assert emitted == [
        (frame["id"], "replace"),
        (child["id"], "add"),
    ]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_escape_clears_selection() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import select_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, _child = _nested_document()
    document = select_ui_object(document, frame["id"])
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )

    QTest.keyClick(overlay, Qt.Key.Key_Escape)
    assert emitted == [("", "replace")]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_shift_enter_selects_parent_and_tab_walks_siblings() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, select_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, child = _nested_document()
    document, sibling = add_ui_object(
        document,
        kind="ellipse",
        name="Ellipse 1",
        parent_id=frame["id"],
        x=330,
        y=160,
        width=100,
        height=90,
    )
    document = select_ui_object(document, child["id"])
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, str]] = []
    overlay.object_selection_requested.connect(
        lambda object_id, mode: emitted.append((object_id, mode))
    )

    QTest.keyClick(
        overlay,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert emitted[-1] == (frame["id"], "replace")

    emitted.clear()
    QTest.keyClick(
        overlay,
        Qt.Key.Key_Tab,
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert emitted[-1] == (sibling["id"], "replace")

    document = select_ui_object(document, sibling["id"])
    overlay.set_document(document)
    emitted.clear()
    QTest.keyClick(overlay, Qt.Key.Key_Tab)
    assert emitted[-1] == (child["id"], "replace")
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_tutorial_select_layer_menu_uses_layers_order_and_includes_locked() -> None:
    _app()
    from PySide6.QtWidgets import QMenu

    from app.painter_ui_document import add_ui_object, update_ui_object
    from app.painter_ui_select_layer_menu import add_ui_select_layer_menu
    from app.painter_ui_selection_navigation import ui_select_layer_rows

    document, frame, child = _nested_document()
    document, locked = add_ui_object(
        document,
        kind="ellipse",
        name="Locked Ellipse",
        parent_id=frame["id"],
        x=170,
        y=160,
        width=120,
        height=90,
    )
    document, locked = update_ui_object(
        document,
        locked["id"],
        {"locked": True},
    )
    document, hidden = add_ui_object(
        document,
        kind="rectangle",
        name="Hidden Rectangle",
        parent_id=frame["id"],
        x=170,
        y=160,
        width=120,
        height=90,
    )
    document, hidden = update_ui_object(
        document,
        hidden["id"],
        {"visible": False},
    )
    hit_ids = [hidden["id"], locked["id"], child["id"], frame["id"]]

    rows = ui_select_layer_rows(document, hit_ids)
    assert [row["id"] for row in rows] == [
        frame["id"],
        locked["id"],
        child["id"],
    ]

    selected: list[str] = []
    root_menu = QMenu()
    submenu = add_ui_select_layer_menu(
        root_menu,
        document,
        hit_ids,
        selected.append,
    )
    assert submenu is not None
    actions = submenu.actions()
    assert [action.data() for action in actions] == [
        frame["id"],
        locked["id"],
        child["id"],
    ]
    assert actions[1].property("painter_ui_locked_layer") is True
    assert not actions[1].icon().isNull()
    actions[1].trigger()
    assert selected == [locked["id"]]
    root_menu.deleteLater()


def test_tutorial_canvas_context_menu_builds_select_layer_at_pointer() -> None:
    app = _app()
    from PySide6.QtCore import QPoint

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, frame, child = _nested_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()
    overlay = dialog._painter_ui_overlay
    child_center = overlay._object_rect(child).center().toPoint()
    global_point = overlay.mapToGlobal(QPoint(child_center))

    menu = dialog._show_canvas_context_menu(global_point, execute=False)
    submenu = menu.findChild(type(menu), "PainterUISelectLayerMenu")
    assert submenu is not None
    assert [action.data() for action in submenu.actions()] == [
        frame["id"],
        child["id"],
    ]
    submenu.actions()[1].trigger()
    assert dialog._painter_ui_document["selection"]["object_id"] == child["id"]
    menu.deleteLater()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_tutorial_layers_panel_hover_and_modifier_selection_rules() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object
    from app.painter_ui_inspector import PainterUIInspector

    document, frame, first = _nested_document()
    document, second = add_ui_object(
        document,
        kind="ellipse",
        name="Ellipse 1",
        parent_id=frame["id"],
        x=310,
        y=160,
        width=90,
        height=90,
    )
    document, third = add_ui_object(
        document,
        kind="text",
        name="Text 1",
        parent_id=frame["id"],
        x=310,
        y=280,
        width=90,
        height=40,
    )
    document["selection"] = {"object_id": "", "object_ids": []}
    inspector = PainterUIInspector()
    inspector.resize(360, 720)
    inspector.set_hierarchy_document(document)
    inspector._tabs.setCurrentWidget(inspector.layers_page)
    inspector.show()
    app.processEvents()
    layer_list = inspector.layer_list
    layer_list.show()
    app.processEvents()

    items = {
        str(layer_list.item(index).data(Qt.ItemDataRole.UserRole)): (
            layer_list.item(index)
        )
        for index in range(layer_list.count())
    }
    hovered: list[str] = []
    inspector.layer_hover_changed.connect(hovered.append)
    third_rect = layer_list.visualItemRect(items[third["id"]])
    QTest.mouseMove(layer_list.viewport(), QPoint(1, 1), delay=10)
    QTest.mouseMove(layer_list.viewport(), third_rect.center(), delay=10)
    assert hovered[-1] == third["id"]
    QTest.mouseMove(
        layer_list.viewport(),
        QPoint(layer_list.viewport().width() - 2, layer_list.viewport().height() - 2),
    )
    assert hovered[-1] == ""

    emitted: list[tuple[list[str], str]] = []
    inspector.selection_changed.connect(
        lambda ids, primary: emitted.append((list(ids), primary))
    )
    first_rect = layer_list.visualItemRect(items[first["id"]])
    third_rect = layer_list.visualItemRect(items[third["id"]])
    QTest.mouseClick(
        layer_list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=first_rect.center(),
    )
    QTest.mouseClick(
        layer_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        third_rect.center(),
    )
    assert set(emitted[-1][0]) == {first["id"], second["id"], third["id"]}

    second_rect = layer_list.visualItemRect(items[second["id"]])
    QTest.mouseClick(
        layer_list.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        second_rect.center(),
    )
    assert set(emitted[-1][0]) == {first["id"], third["id"]}
    inspector.close()
    inspector.deleteLater()
    app.processEvents()


def test_tutorial_layers_hover_is_forwarded_to_canvas_outline() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, _frame, child = _nested_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.resize(1280, 800)
    dialog.show()
    dialog._painter_ui_navigator.select_section("file")
    dialog._painter_ui_navigator.show()
    app.processEvents()
    layer_list = dialog._paint_ui_inspector.layer_list
    target_item = next(
        layer_list.item(index)
        for index in range(layer_list.count())
        if str(layer_list.item(index).data(Qt.ItemDataRole.UserRole)) == child["id"]
    )
    # Mouse delivery itself is covered by the visible standalone panel test
    # above. Emit the list's canonical hover event here to verify the real
    # PaintDialog signal chain without depending on the offscreen platform's
    # dock/viewport exposure rules.
    layer_list.itemEntered.emit(target_item)
    assert dialog._painter_ui_overlay.layer_hover_object_id() == child["id"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
