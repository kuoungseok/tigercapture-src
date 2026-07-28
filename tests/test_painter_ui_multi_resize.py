from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _multi_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(500, 400, name="Desktop")
    document, first = add_ui_object(
        document,
        kind="rectangle",
        name="First",
        x=40,
        y=50,
        width=100,
        height=60,
    )
    document, second = add_ui_object(
        document,
        kind="rectangle",
        name="Second",
        x=220,
        y=150,
        width=80,
        height=50,
    )
    document["selection"] = {
        "object_id": first["id"],
        "object_ids": [first["id"], second["id"]],
    }
    return document, first, second


def test_multi_selection_draws_common_bounds_and_resizes_as_one_group() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, first, second = _multi_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(1000, 760)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()

    rows = overlay._multi_transform_rows()
    bounds = overlay._selection_bounds(rows)
    assert len(rows) == 2
    assert not bounds.isNull()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)

    handle = overlay._handle_rects(bounds)["se"].center().toPoint()
    target = QPoint(handle.x() + 120, handle.y() + 80)
    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=handle,
    )
    assert overlay._interaction == "resize_multi"
    QTest.mouseMove(overlay, target)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=target,
    )
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert set(changes) == {first["id"], second["id"]}
    assert changes[first["id"]]["x"] == first["x"]
    assert changes[first["id"]]["y"] == first["y"]
    assert changes[first["id"]]["width"] > first["width"]
    assert changes[second["id"]]["x"] > second["x"]
    assert changes[second["id"]]["height"] > second["height"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_multi_resize_is_disabled_for_locked_or_cross_artboard_selection() -> None:
    app = _app()
    from app.painter_ui_document import add_ui_artboard, update_ui_object
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, first, second = _multi_document()
    document, _locked = update_ui_object(
        document,
        second["id"],
        {"locked": True},
    )
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    assert overlay._multi_transform_rows() == []

    document, artboard = add_ui_artboard(
        document,
        name="Other",
        width=320,
        height=480,
    )
    document, _moved = update_ui_object(
        document,
        second["id"],
        {
            "locked": False,
            "artboard_id": artboard["id"],
            "parent_id": "",
        },
    )
    overlay.set_document(document)
    assert overlay._multi_transform_rows() == []
    overlay.deleteLater()
    app.processEvents()


def test_batch_property_action_is_one_undoable_shared_mutation() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, first, second = _multi_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(500, 400, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.property.batch_set",
        {
            "changes_by_id": {
                first["id"]: {"x": 60.0, "width": 130.0},
                second["id"]: {"x": 260.0, "width": 110.0},
            }
        },
    )

    assert result.ok
    assert result.result["updated_object_ids"] == [
        first["id"],
        second["id"],
    ]
    assert dialog._undo_labels[-1] == "Edit UI objects"
    rows = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert rows[first["id"]]["x"] == 60.0
    assert rows[second["id"]]["width"] == 110.0
    assert rows[first["id"]]["constraints"]["left"] == 60.0
    dialog._undo()
    restored = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert restored[first["id"]]["x"] == first["x"]
    assert restored[second["id"]]["width"] == second["width"]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
