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


def test_dialog_canvas_drop_inserts_and_orders_instance_slot() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        inspect_ui_component_instance_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        update_ui_object,
    )

    document = create_ui_document(900, 640)
    document, card_root = add_ui_object(
        document, kind="frame", name="Card", width=420, height=160
    )
    document, slot_source = add_ui_object(
        document,
        kind="frame",
        name="Actions",
        parent_id=card_root["id"],
        width=360,
        height=80,
    )
    document, slot_source = update_ui_object(
        document,
        slot_source["id"],
        {"layout": {"mode": "horizontal", "spacing": 12}},
    )
    for name, x in (("Left", 20), ("Right", 220)):
        document, _child = add_ui_object(
            document,
            kind="rectangle",
            name=name,
            parent_id=slot_source["id"],
            x=x,
            y=30,
            width=40,
            height=40,
        )
    document, card = convert_ui_object_to_component(
        document, root_object_id=card_root["id"], name="Card"
    )
    document, _definition = define_ui_component_slot(
        document,
        component_id=card["id"],
        source_object_id=slot_source["id"],
        property_name="Actions",
    )
    document, instance = instantiate_ui_component(
        document, component_id=card["id"], x=300, y=120
    )
    report = inspect_ui_component_instance_slot(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Actions",
    )
    document, outsider = add_ui_object(
        document,
        kind="ellipse",
        name="Dropped",
        x=700,
        y=300,
        width=40,
        height=40,
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    undo_count = len(dialog._undo_labels)
    slot_children = sorted(
        (
            row
            for row in document["objects"]
            if row["id"] in report["child_ids"]
        ),
        key=lambda row: row["x"],
    )
    target_x = (
        float(slot_children[0]["x"])
        + float(slot_children[0]["width"]) * 0.5
        + float(slot_children[1]["x"])
        + float(slot_children[1]["width"]) * 0.5
    ) * 0.5 - 20.0

    dialog._move_and_reparent_painter_ui_objects(
        {outsider["id"]: {"x": target_x, "y": 150.0}},
        report["slot_object_id"],
        [outsider["id"]],
    )

    updated_report = inspect_ui_component_instance_slot(
        dialog._painter_ui_document,
        instance_root_id=instance["root_object_id"],
        property_name="Actions",
    )
    assert updated_report["child_ids"][1] == outsider["id"]
    dropped = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
    )
    assert dropped["parent_id"] == report["slot_object_id"]
    assert dropped["x"] == target_x
    assert len(dialog._undo_labels) == undo_count + 1
    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
    )
    assert restored["parent_id"] == ""
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_real_canvas_pointer_drag_drops_layer_into_instance_slot() -> None:
    app = _app()
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_components import (
        convert_ui_object_to_component,
        define_ui_component_slot,
        inspect_ui_component_instance_slot,
        instantiate_ui_component,
    )
    from app.painter_ui_document import (
        add_ui_object,
        create_ui_document,
        select_ui_object,
    )

    document = create_ui_document(900, 640)
    document, card_root = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=80,
        y=80,
        width=420,
        height=180,
    )
    document, slot_source = add_ui_object(
        document,
        kind="frame",
        name="Actions",
        parent_id=card_root["id"],
        x=110,
        y=130,
        width=340,
        height=80,
    )
    document, card = convert_ui_object_to_component(
        document,
        root_object_id=card_root["id"],
        name="Card",
    )
    document, _definition = define_ui_component_slot(
        document,
        component_id=card["id"],
        source_object_id=slot_source["id"],
        property_name="Actions",
    )
    document, instance = instantiate_ui_component(
        document,
        component_id=card["id"],
        x=360,
        y=300,
    )
    slot_report = inspect_ui_component_instance_slot(
        document,
        instance_root_id=instance["root_object_id"],
        property_name="Actions",
    )
    document, outsider = add_ui_object(
        document,
        kind="ellipse",
        name="Dropped action",
        x=120,
        y=390,
        width=52,
        height=52,
    )
    document = select_ui_object(document, outsider["id"])

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 640, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.resize(1280, 820)
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.show()
    app.processEvents()
    dialog._refresh_painter_ui_overlay()
    overlay = dialog._painter_ui_overlay
    overlay.fit_all()
    app.processEvents()
    current_outsider = next(
        row
        for row in overlay._document["objects"]
        if row["id"] == outsider["id"]
    )
    current_slot = next(
        row
        for row in overlay._document["objects"]
        if row["id"] == slot_report["slot_object_id"]
    )
    outsider_rect = overlay._object_rect(current_outsider)
    # Ellipse center/right-side points are Arc gizmos. Start from ordinary
    # filled geometry so this is a move gesture, not an arc edit gesture.
    start = outsider_rect.topLeft().toPoint()
    start.setX(int(outsider_rect.left() + outsider_rect.width() * 0.35))
    start.setY(int(outsider_rect.top() + outsider_rect.height() * 0.65))
    assert overlay._arc_handle_at(
        current_outsider,
        outsider_rect,
        QPointF(start),
    ) == ""
    target = overlay._object_rect(current_slot).center().toPoint()
    undo_count = len(dialog._undo_labels)

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(overlay, target)
    app.processEvents()
    if not overlay._hierarchy_drop_preview_id:
        app.sendEvent(
            overlay,
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(target),
                QPointF(overlay.mapToGlobal(target)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        app.processEvents()
    assert overlay._hierarchy_drop_preview_id == current_slot["id"], (
        overlay._interaction,
        overlay._active_object_id,
        overlay.object_ids_at(float(target.x()), float(target.y())),
    )
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()

    dropped = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
    )
    assert dropped["parent_id"] == current_slot["id"]
    assert len(dialog._undo_labels) == undo_count + 1
    updated_slot = inspect_ui_component_instance_slot(
        dialog._painter_ui_document,
        instance_root_id=instance["root_object_id"],
        property_name="Actions",
    )
    assert outsider["id"] in updated_slot["child_ids"]
    dropped_overlay_row = next(
        row
        for row in dialog._painter_ui_overlay._document["objects"]
        if row["id"] == outsider["id"]
    )
    dropped_slot_row = next(
        row
        for row in dialog._painter_ui_overlay._document["objects"]
        if row["id"] == current_slot["id"]
    )
    assert dialog._painter_ui_overlay._object_rect(dropped_slot_row).contains(
        dialog._painter_ui_overlay._object_rect(dropped_overlay_row).center()
    )
    dialog._undo()
    restored = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == outsider["id"]
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
