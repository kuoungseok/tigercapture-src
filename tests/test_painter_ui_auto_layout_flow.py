from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _flow_document(mode: str = "horizontal"):
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(800, 600)
    document, parent = add_ui_object(
        document,
        kind="frame",
        x=20,
        y=30,
        width=400,
        height=240,
    )
    document["objects"][0]["layout"] = {"mode": mode, "gap": 10}
    child_ids: list[str] = []
    for width in (40, 50, 60):
        document, child = add_ui_object(
            document,
            kind="rectangle",
            parent_id=parent["id"],
            width=width,
            height=30,
        )
        child_ids.append(child["id"])
    return document, parent["id"], child_ids


def test_reorder_auto_layout_child_changes_flow_order_not_coordinates() -> None:
    from app.painter_ui_auto_layout_flow import (
        inspect_auto_layout_child,
        reorder_auto_layout_child,
    )

    document, _parent_id, child_ids = _flow_document()
    original_xy = {
        row["id"]: (row["x"], row["y"])
        for row in document["objects"]
        if row["id"] in child_ids
    }
    original_slots = sorted(
        row["z_index"] for row in document["objects"] if row["id"] in child_ids
    )
    updated, report = reorder_auto_layout_child(
        document,
        child_ids[0],
        target_index=2,
    )

    assert report["changed"] is True
    assert report["ordered_child_ids"] == [child_ids[1], child_ids[2], child_ids[0]]
    assert inspect_auto_layout_child(updated, child_ids[0])["index"] == 2
    assert sorted(
        row["z_index"] for row in updated["objects"] if row["id"] in child_ids
    ) == original_slots
    assert {
        row["id"]: (row["x"], row["y"])
        for row in updated["objects"]
        if row["id"] in child_ids
    } == original_xy


def test_reorder_boundary_is_noop_without_revision() -> None:
    from app.painter_ui_auto_layout_flow import reorder_auto_layout_child

    document, _parent_id, child_ids = _flow_document("vertical")
    revision = document["revision"]
    updated, report = reorder_auto_layout_child(
        document,
        child_ids[0],
        delta=-1,
    )
    assert report["changed"] is False
    assert updated["revision"] == revision


def test_absolute_child_and_instance_contents_are_not_reorderable() -> None:
    from app.painter_ui_auto_layout_flow import inspect_auto_layout_child

    document, parent_id, child_ids = _flow_document()
    child = next(row for row in document["objects"] if row["id"] == child_ids[0])
    child["layout"] = {"positioning": "absolute"}
    assert inspect_auto_layout_child(document, child_ids[0])["blocker"] == (
        "absolute_child_out_of_flow"
    )
    child["layout"] = {"positioning": "auto"}
    parent = next(row for row in document["objects"] if row["id"] == parent_id)
    parent["component_role"] = "instance"
    assert inspect_auto_layout_child(document, child_ids[0])["blocker"] == (
        "component_instance_order_locked"
    )


def test_switch_flow_changes_resolved_axis() -> None:
    from app.painter_ui_auto_layout_flow import set_auto_layout_flow
    from app.painter_ui_constraints import resolve_ui_constraints

    document, parent_id, child_ids = _flow_document("horizontal")
    horizontal = resolve_ui_constraints(document)
    updated, report = set_auto_layout_flow(document, parent_id, "vertical")
    vertical = resolve_ui_constraints(updated)

    assert report["changed"] is True
    assert horizontal[child_ids[1]]["x"] > horizontal[child_ids[0]]["x"]
    assert horizontal[child_ids[1]]["y"] == horizontal[child_ids[0]]["y"]
    assert vertical[child_ids[1]]["x"] == vertical[child_ids[0]]["x"]
    assert vertical[child_ids[1]]["y"] > vertical[child_ids[0]]["y"]


def test_canvas_drag_emits_flow_index_instead_of_geometry() -> None:
    _app()
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _parent_id, child_ids = _flow_document("horizontal")
    document["selection"] = {
        "object_id": child_ids[0],
        "object_ids": [child_ids[0]],
    }
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 700)
    overlay.set_document(document)
    overlay.show()
    by_id = {row["id"]: row for row in overlay._document["objects"]}
    start = overlay._object_rect(by_id[child_ids[0]]).center().toPoint()
    end = overlay._object_rect(by_id[child_ids[2]]).center().toPoint()
    reorder_events: list[tuple[str, int]] = []
    geometry_events: list[tuple] = []
    overlay.auto_layout_reorder_requested.connect(
        lambda object_id, index: reorder_events.append((object_id, index))
    )
    overlay.object_geometry_requested.connect(
        lambda *args: geometry_events.append(args)
    )

    overlay._begin_object_move(by_id[child_ids[0]], start)
    overlay.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(end),
            QPointF(end),
            QPointF(end),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=end)

    assert reorder_events == [(child_ids[0], 2)]
    assert geometry_events == []
    overlay.close()


def test_dialog_arrow_keys_reorder_on_axis_and_ignore_cross_axis() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_auto_layout_flow import inspect_auto_layout_child

    document, _parent_id, child_ids = _flow_document("horizontal")
    document["selection"] = {
        "object_id": child_ids[1],
        "object_ids": [child_ids[1]],
    }
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    dialog._refresh_painter_ui_overlay()
    revision = document["revision"]

    dialog._handle_painter_ui_key_command("down", False)
    assert dialog._painter_ui_document["revision"] == revision
    dialog._handle_painter_ui_key_command("right", False)
    assert inspect_auto_layout_child(
        dialog._painter_ui_document,
        child_ids[1],
    )["index"] == 2
    assert dialog._painter_ui_document["revision"] == revision + 1
    dialog.close()
    app.processEvents()
