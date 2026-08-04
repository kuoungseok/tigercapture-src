from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("TIGERSTUDIO_PAINTER_PANEL_SETTINGS", "0")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _nested_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600, name="Desktop")
    document, root = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=80,
        y=60,
        width=420,
        height=320,
    )
    document, group = add_ui_object(
        document,
        kind="group",
        name="Header",
        parent_id=root["id"],
        x=100,
        y=90,
        width=360,
        height=120,
    )
    document, text = add_ui_object(
        document,
        kind="text",
        name="Title",
        parent_id=group["id"],
        x=120,
        y=110,
        width=220,
        height=52,
        content={"text": "Tiger Studio"},
    )
    document, badge = add_ui_object(
        document,
        kind="ellipse",
        name="Badge",
        parent_id=group["id"],
        x=120,
        y=110,
        width=80,
        height=52,
    )
    return document, root, group, text, badge


def test_selection_navigation_walks_parent_and_topmost_deep_child() -> None:
    from app.painter_ui_document import select_ui_object
    from app.painter_ui_selection_navigation import (
        select_deep_ui_object,
        select_parent_ui_object,
        ui_selection_path,
    )

    document, root, group, text, badge = _nested_document()
    document = select_ui_object(document, text["id"])
    assert [row["id"] for row in ui_selection_path(document)] == [
        root["id"],
        group["id"],
        text["id"],
    ]

    document, parent_report = select_parent_ui_object(document)
    assert parent_report["selected_object_id"] == group["id"]
    assert document["selection"]["object_id"] == group["id"]

    document, deep_report = select_deep_ui_object(document, root["id"])
    assert deep_report["selected_object_id"] == badge["id"]
    assert document["selection"]["object_id"] == badge["id"]

    document = select_ui_object(document, root["id"])
    document, root_report = select_parent_ui_object(document)
    assert root_report["selected_object_id"] == root["id"]
    assert document["selection"]["object_id"] == root["id"]


def test_breadcrumb_emits_requested_ancestor_and_hides_for_root() -> None:
    app = _app()
    from PySide6.QtWidgets import QPushButton, QWidget

    from app.painter_ui_document import select_ui_object
    from app.painter_ui_selection_breadcrumb import (
        PainterUISelectionBreadcrumb,
    )

    document, root, group, text, _badge = _nested_document()
    document = select_ui_object(document, text["id"])
    host = QWidget()
    host.resize(900, 700)
    breadcrumb = PainterUISelectionBreadcrumb(host)
    requested: list[str] = []
    breadcrumb.object_requested.connect(requested.append)
    breadcrumb.set_document(document)
    host.show()
    app.processEvents()

    buttons = breadcrumb.findChildren(
        QPushButton,
        "PainterUIBreadcrumbItem",
    )
    assert [button.text() for button in buttons] == [
        "Card",
        "Header",
        "Title",
    ]
    buttons[1].click()
    assert requested == [group["id"]]
    assert breadcrumb.isVisible()
    assert breadcrumb.width() > 140
    assert breadcrumb.height() == 30

    breadcrumb.set_document(select_ui_object(document, root["id"]))
    app.processEvents()
    assert not breadcrumb.isVisible()
    host.close()
    host.deleteLater()
    app.processEvents()


def test_paint_dialog_places_selection_breadcrumb_in_canvas_chrome() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, QRect

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import select_ui_object

    document, _root, _group, text, _badge = _nested_document()
    document = select_ui_object(document, text["id"])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 480, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1200, 800)
    dialog.show()
    dialog._set_canvas_workspace_mode("ui_design")
    breadcrumb = dialog._painter_ui_selection_breadcrumb
    breadcrumb.set_document(document)
    app.processEvents()

    assert breadcrumb.parentWidget() is dialog._canvas_mode_bar
    assert dialog._canvas_mode_bar.layout().indexOf(breadcrumb) >= 0
    breadcrumb_rect = QRect(
        breadcrumb.mapToGlobal(QPoint(0, 0)),
        breadcrumb.size(),
    )
    canvas_rect = QRect(
        dialog._canvas_host.mapToGlobal(QPoint(0, 0)),
        dialog._canvas_host.size(),
    )
    assert not breadcrumb_rect.intersects(canvas_rect)

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_overlay_hit_stack_returns_topmost_then_ancestors() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, root, group, text, badge = _nested_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 760)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()

    rect = overlay._object_rect(badge)
    point = QPointF(rect.center())
    hits = overlay.object_ids_at(point.x(), point.y())
    assert hits[:4] == [
        badge["id"],
        text["id"],
        group["id"],
        root["id"],
    ]
    overlay.set_edit_scope(group["id"])
    assert overlay.edit_scope_id() == group["id"]
    assert overlay.object_ids_at(point.x(), point.y())[:3] == [
        badge["id"],
        text["id"],
        group["id"],
    ]
    assert root["id"] not in overlay.object_ids_at(point.x(), point.y())
    assert overlay._row_in_edit_scope(badge)
    assert not overlay._row_in_edit_scope(root)
    exit_requests: list[bool] = []
    overlay.edit_scope_exit_requested.connect(
        lambda: exit_requests.append(True)
    )
    QTest.keyClick(overlay, Qt.Key.Key_Escape)
    assert exit_requests == [True]

    overlay.set_edit_scope("")
    enter_requests: list[str] = []
    overlay.edit_scope_enter_requested.connect(enter_requests.append)
    group_rect = overlay._object_rect(group)
    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(
            round(group_rect.right() - 4),
            round(group_rect.bottom() - 4),
        ),
    )
    assert enter_requests == [group["id"]]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_selection_navigation_actions_share_dialog_selection_state() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, root, group, _text, badge = _nested_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._refresh_painter_ui_overlay()
    registry = ActionRegistry(owner=dialog)

    parent = registry.execute(
        "paint.ui.selection.parent",
        {"object_id": badge["id"]},
    ).to_dict()
    assert parent["ok"]
    assert parent["result"]["selection_navigation"][
        "selected_object_id"
    ] == group["id"]

    deep = registry.execute(
        "paint.ui.selection.deep_select",
        {"object_id": root["id"]},
    ).to_dict()
    assert deep["ok"]
    assert deep["result"]["selection_navigation"][
        "selected_object_id"
    ] == badge["id"]
    assert deep["result"]["ui_design"]["selected_object_id"] == badge["id"]

    revision = dialog._painter_ui_document["revision"]
    entered_root = registry.execute(
        "paint.ui.selection.scope.enter",
        {"object_id": root["id"]},
    ).to_dict()
    assert entered_root["ok"]
    assert entered_root["result"]["selection_scope"]["scope_stack"] == [
        root["id"]
    ]
    entered_group = registry.execute(
        "paint.ui.selection.scope.enter",
        {"object_id": group["id"]},
    ).to_dict()
    assert entered_group["ok"]
    assert entered_group["result"]["selection_scope"]["scope_stack"] == [
        root["id"],
        group["id"],
    ]
    assert dialog._painter_ui_overlay.edit_scope_id() == group["id"]
    assert dialog._painter_ui_document["revision"] == revision

    inspected = registry.execute(
        "paint.ui.selection.scope.inspect",
        {},
    ).to_dict()
    assert inspected["ok"]
    assert inspected["result"]["selection_scope"]["scope_id"] == group["id"]

    exited = registry.execute(
        "paint.ui.selection.scope.exit",
        {},
    ).to_dict()
    assert exited["ok"]
    assert exited["result"]["selection_scope"]["scope_id"] == root["id"]
    assert exited["result"]["selection_scope"][
        "exited_scope_id"
    ] == group["id"]
    assert dialog._painter_ui_document["revision"] == revision

    invalid = registry.execute(
        "paint.ui.selection.deep_select",
        {"x": 100},
    ).to_dict()
    assert not invalid["ok"]
    assert "requires both x and y" in invalid["error"]

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
