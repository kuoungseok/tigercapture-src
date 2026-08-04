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


def _grid_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(900, 600, name="Desktop")
    rows = []
    for index, (x, y, width, height) in enumerate(
        (
            (10.0, 20.0, 20.0, 20.0),
            (80.0, 25.0, 30.0, 15.0),
            (14.0, 100.0, 25.0, 25.0),
            (90.0, 110.0, 10.0, 20.0),
        )
    ):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Grid {index + 1}",
            x=x,
            y=y,
            width=width,
            height=height,
        )
        rows.append(row)
    document["selection"] = {
        "object_id": rows[-1]["id"],
        "object_ids": [row["id"] for row in rows],
    }
    return document, rows


def _uniform_grid_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(500, 400, name="Desktop")
    rows = []
    for index, (x, y) in enumerate(
        ((40.0, 40.0), (100.0, 40.0), (40.0, 100.0), (100.0, 100.0))
    ):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Cell {index + 1}",
            x=x,
            y=y,
            width=40.0,
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
    # Figma's Tidy up uses the most common spacing value. When every gap is
    # unique, the first encountered value wins instead of averaging them.
    assert report["suggested_gap"] == 40.0

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


def test_tidy_uses_mode_and_tolerates_one_pixel_rounding() -> None:
    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_smart_selection import inspect_ui_selection_spacing

    document = create_ui_document(900, 600, name="Desktop")
    rows = []
    for index, x in enumerate((10.0, 50.0, 89.0, 129.0)):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Rounded {index + 1}",
            x=x,
            y=20.0,
            width=20.0,
            height=20.0,
        )
        rows.append(row)
    document["selection"] = {
        "object_id": rows[-1]["id"],
        "object_ids": [row["id"] for row in rows],
    }

    report = inspect_ui_selection_spacing(document, axis="horizontal")

    assert report["gaps"] == [20.0, 19.0, 20.0]
    assert report["suggested_gap"] == 20.0
    assert report["uniform"] is True


def test_distribution_keeps_outer_objects_fixed() -> None:
    from app.painter_ui_smart_selection import plan_ui_selection_distribution

    document, rows = _spacing_document()
    plan = plan_ui_selection_distribution(document, axis="horizontal")

    assert plan["eligible"] is True
    assert plan["gap"] == 55.0
    assert rows[0]["id"] not in plan["changes_by_id"]
    assert rows[-1]["id"] not in plan["changes_by_id"]
    assert plan["changes_by_id"] == {
        rows[1]["id"]: {"x": 85.0},
    }


def test_one_dimensional_smart_reorder_preserves_hierarchy_order() -> None:
    from app.painter_ui_smart_selection import plan_ui_smart_reorder

    document, rows = _spacing_document()
    tidy = {
        rows[0]["id"]: {"x": 10.0},
        rows[1]["id"]: {"x": 70.0},
        rows[2]["id"]: {"x": 140.0},
    }
    for row in document["objects"]:
        row.update(tidy[row["id"]])
    hierarchy_before = [row["id"] for row in document["objects"]]

    plan = plan_ui_smart_reorder(
        document,
        marked_ids=[rows[2]["id"]],
        target_index=0,
        axis="horizontal",
    )

    assert plan["reordered_object_ids"] == [
        rows[2]["id"],
        rows[0]["id"],
        rows[1]["id"],
    ]
    assert plan["changes_by_id"] == {
        rows[2]["id"]: {"x": 10.0},
        rows[0]["id"]: {"x": 90.0},
        rows[1]["id"]: {"x": 150.0},
    }
    assert [row["id"] for row in document["objects"]] == hierarchy_before


def test_two_dimensional_tidy_builds_grid_from_top_left() -> None:
    from app.painter_ui_smart_selection import (
        inspect_ui_selection_spacing,
        plan_ui_selection_tidy,
    )

    document, rows = _grid_document()
    report = inspect_ui_selection_spacing(document, axis="auto")

    assert report["axis"] == "grid"
    assert report["grid_rows"] == [
        [rows[0]["id"], rows[1]["id"]],
        [rows[2]["id"], rows[3]["id"]],
    ]
    assert report["horizontal_gaps"] == [50.0, 51.0]
    assert report["vertical_gaps"] == [60.0]
    assert report["horizontal_gap"] == 50.0
    assert report["vertical_gap"] == 60.0

    plan = plan_ui_selection_tidy(document, axis="auto")

    assert plan["changes_by_id"] == {
        rows[0]["id"]: {"x": 10.0, "y": 20.0},
        rows[1]["id"]: {"x": 85.0, "y": 20.0},
        rows[2]["id"]: {"x": 10.0, "y": 100.0},
        rows[3]["id"]: {"x": 85.0, "y": 100.0},
    }


def test_two_dimensional_tidy_accepts_distinct_axis_gaps() -> None:
    from app.painter_ui_smart_selection import plan_ui_selection_tidy

    document, rows = _grid_document()
    plan = plan_ui_selection_tidy(
        document,
        axis="auto",
        gap={"horizontal": 12.0, "vertical": 18.0},
    )

    assert plan["horizontal_gap"] == 12.0
    assert plan["vertical_gap"] == 18.0
    assert plan["changes_by_id"][rows[0]["id"]] == {"x": 10.0, "y": 20.0}
    assert plan["changes_by_id"][rows[1]["id"]] == {"x": 47.0, "y": 20.0}
    assert plan["changes_by_id"][rows[2]["id"]] == {"x": 10.0, "y": 58.0}
    assert plan["changes_by_id"][rows[3]["id"]] == {"x": 47.0, "y": 58.0}


def test_grid_smart_reorder_inserts_into_existing_row() -> None:
    from app.painter_ui_smart_selection import plan_ui_smart_grid_reorder

    document, rows = _uniform_grid_document()
    hierarchy_before = [row["id"] for row in document["objects"]]

    plan = plan_ui_smart_grid_reorder(
        document,
        marked_id=rows[0]["id"],
        target_row=1,
        target_column=2,
    )

    assert plan["grid_rows"] == [
        [rows[1]["id"]],
        [rows[2]["id"], rows[3]["id"], rows[0]["id"]],
    ]
    assert plan["changes_by_id"][rows[0]["id"]]["x"] > plan["changes_by_id"][rows[3]["id"]]["x"]
    assert [row["id"] for row in document["objects"]] == hierarchy_before


def test_grid_smart_reorder_control_swaps_two_positions() -> None:
    from app.painter_ui_smart_selection import plan_ui_smart_grid_reorder

    document, rows = _uniform_grid_document()

    plan = plan_ui_smart_grid_reorder(
        document,
        marked_id=rows[0]["id"],
        target_row=0,
        target_column=0,
        swap_target_id=rows[3]["id"],
    )

    assert plan["grid_rows"] == [
        [rows[3]["id"], rows[1]["id"]],
        [rows[2]["id"], rows[0]["id"]],
    ]
    assert plan["changes_by_id"][rows[3]["id"]] == {"x": 40.0, "y": 40.0}
    assert plan["changes_by_id"][rows[0]["id"]] == {"x": 100.0, "y": 100.0}


def test_smart_duplicate_reflow_places_row_copy_after_source() -> None:
    from app.painter_ui_duplicate import duplicate_ui_selection
    from app.painter_ui_smart_selection import (
        capture_ui_smart_layout,
        plan_ui_smart_mutation_reflow,
    )

    document, rows = _uniform_grid_document()
    document["selection"] = {
        "object_id": rows[0]["id"],
        "object_ids": [rows[0]["id"], rows[1]["id"]],
    }
    layout = capture_ui_smart_layout(document)
    duplicated, report = duplicate_ui_selection(
        document, object_ids=[rows[0]["id"]], offset_x=0, offset_y=0
    )
    plan = plan_ui_smart_mutation_reflow(
        duplicated, layout=layout, duplicate_id_map=report["object_id_map"]
    )
    clone = report["object_id_map"][rows[0]["id"]]
    assert plan["changes_by_id"][clone] == {"x": 100.0}
    assert plan["changes_by_id"][rows[1]["id"]] == {"x": 160.0}


def test_smart_grid_delete_moves_lower_layer_up() -> None:
    from app.painter_ui_document import remove_ui_object
    from app.painter_ui_smart_selection import (
        capture_ui_smart_layout,
        plan_ui_smart_mutation_reflow,
    )

    document, rows = _uniform_grid_document()
    layout = capture_ui_smart_layout(document)
    deleted, _result = remove_ui_object(document, rows[0]["id"])
    plan = plan_ui_smart_mutation_reflow(
        deleted, layout=layout, removed_ids=[rows[0]["id"]]
    )
    assert plan["changes_by_id"][rows[2]["id"]] == {"x": 40.0, "y": 40.0}


def test_smart_grid_resize_uses_largest_row_height_and_preserves_gap() -> None:
    from app.painter_ui_smart_selection import (
        capture_ui_smart_layout,
        plan_ui_smart_mutation_reflow,
    )

    document, rows = _uniform_grid_document()
    layout = capture_ui_smart_layout(document)
    rows_by_id = {row["id"]: row for row in document["objects"]}
    rows_by_id[rows[0]["id"]]["height"] = 70.0
    plan = plan_ui_smart_mutation_reflow(
        document, layout=layout, resize=True
    )
    assert plan["changes_by_id"][rows[2]["id"]]["y"] == 130.0
    assert plan["changes_by_id"][rows[3]["id"]]["y"] == 130.0


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


def test_multi_inspector_exposes_distinct_grid_spacing() -> None:
    app = _app()
    from app.painter_ui_inspector import PainterUIInspector

    document, _rows = _grid_document()
    inspector = PainterUIInspector()
    inspector.set_document(document)
    emitted: list[tuple[str, object]] = []
    inspector.selection_tidy_requested.connect(
        lambda axis, gap: emitted.append((axis, gap))
    )

    assert inspector.multi_gap_spin.prefix() == "H "
    assert inspector.multi_gap_spin.value() == 50.0
    assert inspector.multi_gap_y_spin.isVisibleTo(inspector)
    assert inspector.multi_gap_y_spin.prefix() == "V "
    assert inspector.multi_gap_y_spin.value() == 60.0
    inspector.multi_tidy_button.click()

    assert emitted == [
        ("auto", {"horizontal": 50.0, "vertical": 60.0})
    ]
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


def test_grid_tidy_is_one_undoable_shared_batch_mutation() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    document, rows = _grid_document()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(900, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = document

    dialog._tidy_painter_ui_selection(
        "auto",
        {"horizontal": 12.0, "vertical": 18.0},
    )

    by_id = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert (by_id[rows[1]["id"]]["x"], by_id[rows[1]["id"]]["y"]) == (
        47.0,
        20.0,
    )
    assert (by_id[rows[3]["id"]]["x"], by_id[rows[3]["id"]]["y"]) == (
        47.0,
        58.0,
    )
    assert dialog._undo_labels[-1] == "Tidy UI selection"

    dialog._undo()

    restored = {
        row["id"]: row
        for row in dialog._painter_ui_document["objects"]
    }
    assert (restored[rows[1]["id"]]["x"], restored[rows[1]["id"]]["y"]) == (
        80.0,
        25.0,
    )
    assert (restored[rows[3]["id"]]["x"], restored[rows[3]["id"]]["y"]) == (
        90.0,
        110.0,
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
