from __future__ import annotations

import copy
import os


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _document():
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_objects,
    )

    document = create_ui_document(900, 640)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Frame target",
        x=430,
        y=120,
        width=320,
        height=360,
    )
    document, card = add_ui_object(
        document,
        kind="rectangle",
        name="Move me",
        x=90,
        y=210,
        width=150,
        height=100,
    )
    document = select_ui_objects(
        document, [card["id"]], primary_object_id=card["id"]
    )
    return document, frame, card


def test_frame_accepts_hierarchy_children_with_deterministic_order() -> None:
    from app.painter_ui_document import move_ui_objects_in_hierarchy

    document, frame, card = _document()
    updated = move_ui_objects_in_hierarchy(
        document,
        [card["id"]],
        target_parent_id=frame["id"],
        placement="inside",
    )
    rows = sorted(updated["objects"], key=lambda row: row["z_index"])

    moved = next(row for row in rows if row["id"] == card["id"])
    assert moved["parent_id"] == frame["id"]
    assert rows.index(moved) == rows.index(
        next(row for row in rows if row["id"] == frame["id"])
    ) + 1


def test_canvas_move_previews_and_emits_frame_reparent() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, frame, card = _document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(1100, 760)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted = []
    overlay.objects_move_reparent_requested.connect(
        lambda changes, target, selected: emitted.append(
            (changes, target, selected)
        )
    )
    start = overlay._object_rect(card).center().toPoint()
    target = overlay._object_rect(frame).center().toPoint()

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, target)
    app.processEvents()

    assert overlay._hierarchy_drop_preview_id == frame["id"]
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()
    assert emitted
    assert emitted[-1][1] == frame["id"]
    assert emitted[-1][2] == [card["id"]]
    overlay.close()
    overlay.deleteLater()


def test_dialog_canvas_reparent_is_one_undo_step() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, frame, card = _document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    undo_count = len(dialog._undo_labels)

    dialog._move_and_reparent_painter_ui_objects(
        {card["id"]: {"x": 500.0, "y": 220.0}},
        frame["id"],
        [card["id"]],
    )

    moved = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == card["id"]
    )
    assert moved["parent_id"] == frame["id"]
    assert (moved["x"], moved["y"]) == (500.0, 220.0)
    assert len(dialog._undo_labels) == undo_count + 1
    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == card["id"]
    )
    assert restored["parent_id"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_layer_list_drop_plan_distinguishes_before_inside_after() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    from app.painter_ui_inspector import PainterUILayerList

    layers = PainterUILayerList()
    item = QListWidgetItem("Frame")
    item.setData(Qt.ItemDataRole.UserRole, "frame-1")
    item.setData(int(Qt.ItemDataRole.UserRole) + 1, "frame")
    layers.addItem(item)
    layers.resize(280, 160)
    layers.show()
    app.processEvents()
    rect = layers.visualItemRect(item)

    assert layers._hierarchy_drop_plan(rect.topLeft())[1] == "before"
    assert layers._hierarchy_drop_plan(rect.center())[1] == "inside"
    assert layers._hierarchy_drop_plan(rect.bottomLeft())[1] == "after"
    layers.close()
    layers.deleteLater()
