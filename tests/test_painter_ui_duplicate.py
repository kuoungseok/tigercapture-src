from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _hierarchy_document():
    from app.painter_ui_document import (
        add_ui_interaction,
        add_ui_object,
        create_ui_document,
        select_ui_objects,
        update_ui_object,
    )

    document = create_ui_document(800, 600)
    document, frame = add_ui_object(
        document,
        kind="frame",
        name="Card",
        x=120,
        y=100,
        width=280,
        height=220,
    )
    document, child = add_ui_object(
        document,
        kind="button",
        name="Action",
        parent_id=frame["id"],
        x=160,
        y=240,
        width=160,
        height=48,
    )
    document, _updated = update_ui_object(
        document,
        child["id"],
        {"accessibility": {"focus_order": 1, "role": "button"}},
    )
    document, interaction = add_ui_interaction(
        document,
        source_object_id=child["id"],
        trigger="click",
        action="set_visibility",
        target_object_id=frame["id"],
    )
    document = select_ui_objects(
        document,
        [frame["id"]],
        primary_object_id=frame["id"],
    )
    return document, frame, child, interaction


def test_duplicate_preserves_hierarchy_references_and_stable_ids() -> None:
    from app.painter_ui_duplicate import duplicate_ui_selection

    document, frame, child, interaction = _hierarchy_document()
    updated, report = duplicate_ui_selection(
        document,
        offset_x=24,
        offset_y=32,
    )

    object_map = report["object_id_map"]
    copied_frame = next(
        row for row in updated["objects"] if row["id"] == object_map[frame["id"]]
    )
    copied_child = next(
        row for row in updated["objects"] if row["id"] == object_map[child["id"]]
    )
    copied_interaction = next(
        row
        for row in updated["interactions"]
        if row["id"] == report["interaction_id_map"][interaction["id"]]
    )
    assert copied_frame["x"] == frame["x"] + 24
    assert copied_frame["y"] == frame["y"] + 32
    assert copied_child["parent_id"] == copied_frame["id"]
    assert copied_child["x"] == child["x"] + 24
    assert copied_interaction["source_object_id"] == copied_child["id"]
    assert copied_interaction["target_object_id"] == copied_frame["id"]
    assert copied_child["accessibility"]["focus_order"] == 0
    assert updated["selection"]["object_ids"] == [copied_frame["id"]]


def test_duplicate_does_not_mutate_source_document() -> None:
    from app.painter_ui_duplicate import duplicate_ui_selection

    document, _frame, _child, _interaction = _hierarchy_document()
    before = copy.deepcopy(document)
    duplicate_ui_selection(document)
    assert document == before


def test_duplicate_action_is_undoable_and_persistent(tmp_path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, frame, _child, _interaction = _hierarchy_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.object.duplicate",
        {
            "object_ids": [frame["id"]],
            "offset_x": 20,
            "offset_y": 0,
        },
    ).to_dict()
    assert result["ok"] is True
    assert len(dialog._painter_ui_document["objects"]) == 4
    dialog._undo()
    assert len(dialog._painter_ui_document["objects"]) == 2
    dialog._redo()
    assert len(dialog._painter_ui_document["objects"]) == 4
    document_path = tmp_path / "duplicate.tspaint"
    saved = registry.execute(
        "paint.document.save",
        {"path": str(document_path)},
    ).to_dict()
    assert saved["ok"] is True
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    assert len(restored._painter_ui_document["objects"]) == 4
    restored.close()
    restored.deleteLater()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_alt_drag_duplicates_then_moves_the_copy() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, frame, _child, _interaction = _hierarchy_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)
    dialog._set_canvas_workspace_mode("ui_design")
    dialog.resize(1100, 760)
    dialog.show()
    dialog._refresh_painter_ui_overlay()
    app.processEvents()
    overlay = dialog._painter_ui_overlay
    source = next(
        row
        for row in overlay._document["objects"]
        if row["id"] == frame["id"]
    )
    rect = overlay._object_rect(source)
    start = rect.center().toPoint()
    end = QPoint(start.x() + 90, start.y() + 45)

    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.AltModifier,
        start,
    )
    QTest.mouseMove(overlay, end)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.AltModifier,
        end,
    )
    app.processEvents()

    assert len(dialog._painter_ui_document["objects"]) == 4
    copied_id = dialog._painter_ui_document["selection"]["object_id"]
    copied = next(
        row
        for row in dialog._painter_ui_document["objects"]
        if row["id"] == copied_id
    )
    assert copied_id != frame["id"]
    assert copied["x"] > frame["x"] + 40
    assert copied["y"] > frame["y"] + 15
    assert dialog._painter_ui_document["selection"]["object_ids"] == [
        copied_id
    ]
    dialog._undo()
    assert len(dialog._painter_ui_document["objects"]) == 2
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
