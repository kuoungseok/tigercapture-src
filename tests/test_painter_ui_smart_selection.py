from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _spacing_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(900, 600, name="Desktop")
    rows = []
    for index, (x, width) in enumerate(((10, 20), (70, 30), (170, 40))):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Item {index + 1}",
            x=float(x),
            y=80.0,
            width=float(width),
            height=40.0,
        )
        rows.append(row)
    document["selection"] = {
        "object_id": rows[-1]["id"],
        "object_ids": [row["id"] for row in rows],
    }
    return document, rows


def test_spacing_inspection_and_explicit_tidy_plan() -> None:
    from app.painter_ui_smart_selection import (
        inspect_ui_selection_spacing,
        plan_ui_selection_tidy,
    )

    document, rows = _spacing_document()
    report = inspect_ui_selection_spacing(document)

    assert report["eligible"] is True
    assert report["axis"] == "horizontal"
    assert report["gaps"] == [40.0, 70.0]
    assert report["uniform"] is False
    assert report["gap"] is None
    assert report["suggested_gap"] == 55.0

    plan = plan_ui_selection_tidy(
        document,
        axis="horizontal",
        gap=12.0,
    )
    assert plan["gap"] == 12.0
    assert plan["changes_by_id"] == {
        rows[0]["id"]: {"x": 10.0},
        rows[1]["id"]: {"x": 42.0},
        rows[2]["id"]: {"x": 84.0},
    }


def test_spacing_rejects_locked_or_cross_parent_selection() -> None:
    from app.painter_ui_smart_selection import inspect_ui_selection_spacing

    document, rows = _spacing_document()
    document["objects"][0]["locked"] = True
    report = inspect_ui_selection_spacing(document)
    assert report["eligible"] is False
    assert report["reason"] == "Locked objects cannot be tidied."

    document["objects"][0]["locked"] = False
    document["objects"][1]["parent_id"] = "different-parent"
    report = inspect_ui_selection_spacing(document)
    assert report["eligible"] is False
    assert report["reason"] == "Tidy Up requires one parent container."


def test_multi_inspector_exposes_tidy_request_without_mutating_document() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, _rows = _spacing_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, object]] = []
    inspector.selection_tidy_requested.connect(
        lambda axis, gap: emitted.append((axis, gap))
    )

    assert inspector.multi_tidy_button.isEnabled()
    assert inspector.multi_gap_spin.value() == -1.0
    assert inspector.multi_gap_spin.specialValueText() == "—"
    inspector.multi_tidy_button.click()

    assert emitted == [("auto", None)]
    assert document["objects"][1]["x"] == 70.0
    inspector.deleteLater()
    app.processEvents()


def test_tidy_action_is_one_undoable_shared_batch_mutation() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, rows = _spacing_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.ui.selection.tidy",
        {"axis": "horizontal", "gap": 20.0},
    )

    assert result.ok
    assert result.result["tidy"]["axis"] == "horizontal"
    assert result.result["tidy"]["gap"] == 20.0
    assert result.result["updated_object_ids"] == [
        row["id"] for row in rows
    ]
    positions = {
        row["id"]: row["x"]
        for row in dialog._painter_ui_document["objects"]
    }
    assert positions == {
        rows[0]["id"]: 10.0,
        rows[1]["id"]: 50.0,
        rows[2]["id"]: 100.0,
    }
    assert dialog._undo_labels[-1] == "Tidy UI selection"
    dialog._undo()
    restored = {
        row["id"]: row["x"]
        for row in dialog._painter_ui_document["objects"]
    }
    assert restored == {
        rows[0]["id"]: 10.0,
        rows[1]["id"]: 70.0,
        rows[2]["id"]: 170.0,
    }
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
