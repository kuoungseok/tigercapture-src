from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _row_document(*, uniform: bool = True):
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(500, 320, name="Desktop")
    rows = []
    positions = (40.0, 100.0, 150.0) if uniform else (40.0, 110.0, 180.0)
    widths = (40.0, 30.0, 50.0)
    for index, (x, width) in enumerate(zip(positions, widths)):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Item {index + 1}",
            x=x,
            y=80.0,
            width=width,
            height=50.0,
        )
        rows.append(row)
    document["selection"] = {
        "object_id": rows[-1]["id"],
        "object_ids": [row["id"] for row in rows],
    }
    return document, rows


def _grid_document():
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


def _uneven_grid_document():
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(500, 400, name="Desktop")
    rows = []
    for index, (x, y) in enumerate(
        ((40.0, 40.0), (40.0, 100.0), (100.0, 100.0))
    ):
        document, row = add_ui_object(
            document,
            kind="rectangle",
            name=f"Uneven cell {index + 1}",
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


def test_smart_handles_require_equal_spacing() -> None:
    _app()
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)

    nonuniform, _rows = _row_document(uniform=False)
    overlay.set_document(nonuniform)
    assert overlay._smart_selection_report() is None
    assert overlay._smart_selection_gap_handles() == []

    uniform, _rows = _row_document(uniform=True)
    overlay.set_document(uniform)
    report = overlay._smart_selection_report()
    handles = overlay._smart_selection_gap_handles()
    assert report is not None
    assert report["axis"] == "horizontal"
    assert report["gap"] == 20.0
    assert len(handles) == 2
    assert {handle["axis"] for handle in handles} == {"horizontal"}


def test_horizontal_smart_handle_drag_updates_all_gaps_once() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.set_tool("select")
    overlay.show()
    app.processEvents()

    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)
    handle = overlay._smart_selection_gap_handles()[0]["rect"].center().toPoint()
    _viewport, scale = overlay._artboard_viewport()
    target = QPoint(handle.x() + round(10.0 * scale), handle.y())

    QTest.mouseMove(overlay, handle)
    assert overlay._smart_selection_hovered is True
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
    assert overlay._interaction == "smart_gap_horizontal"
    QTest.mouseMove(overlay, target, delay=1)
    assert overlay._smart_gap_label.endswith("px")
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert set(changes) == {row["id"] for row in rows}
    ordered = [changes[row["id"]] for row in rows]
    first_gap = ordered[1]["x"] - (ordered[0]["x"] + rows[0]["width"])
    second_gap = ordered[2]["x"] - (ordered[1]["x"] + rows[1]["width"])
    assert abs(first_gap - 30.0) <= 1.0
    assert abs(second_gap - first_gap) < 0.001
    assert overlay._interaction == ""
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_grid_smart_selection_exposes_both_handle_axes() -> None:
    _app()
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, _rows = _grid_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)

    report = overlay._smart_selection_report()
    handles = overlay._smart_selection_gap_handles()
    assert report is not None
    assert report["axis"] == "grid"
    assert {handle["axis"] for handle in handles} == {
        "horizontal",
        "vertical",
    }
    assert len(handles) == 4


def test_grid_drag_inserts_item_into_existing_row() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _grid_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }
    last_rect = overlay._object_rect(
        next(row for row in overlay._document["objects"] if row["id"] == rows[3]["id"])
    )
    target = QPoint(round(last_rect.right() + 15.0), round(last_rect.center().y()))

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=centers[rows[0]["id"]])
    QTest.mouseMove(overlay, target, delay=1)
    assert overlay._interaction == "smart_reorder"
    assert overlay._smart_reorder_indicator_mode == "insert"
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert changes[rows[0]["id"]]["y"] == 100.0
    assert changes[rows[0]["id"]]["x"] > changes[rows[3]["id"]]["x"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_grid_control_drag_swaps_with_nearest_item() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _grid_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=centers[rows[0]["id"]])
    QTest.mouseMove(overlay, centers[rows[3]["id"]], delay=1)
    assert overlay._interaction == "smart_reorder"
    overlay._preview_smart_reorder(
        QPointF(centers[rows[3]["id"]]),
        Qt.KeyboardModifier.ControlModifier,
    )
    assert overlay._smart_reorder_indicator_mode == "swap"
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        centers[rows[3]["id"]],
    )
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert changes[rows[0]["id"]] == {"x": 100.0, "y": 100.0}
    assert changes[rows[3]["id"]] == {"x": 40.0, "y": 40.0}
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_grid_drag_from_single_item_row_keeps_insert_indicator_valid() -> None:
    app = _app()
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _uneven_grid_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=centers[rows[0]["id"]])
    QTest.mouseMove(overlay, centers[rows[2]["id"]], delay=1)
    assert overlay._interaction == "smart_reorder"
    overlay._preview_smart_reorder(
        QPointF(centers[rows[2]["id"]]),
        Qt.KeyboardModifier.NoModifier,
    )

    assert overlay._smart_reorder_indicator_mode == "insert"
    assert overlay._smart_reorder_indicator is not None
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=centers[rows[2]["id"]])
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_center_rings_mark_multiple_layers_in_one_dimension() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }

    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=centers[rows[0]["id"]],
    )
    QTest.mouseClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        centers[rows[1]["id"]],
    )

    assert overlay._smart_marked_ids == {rows[0]["id"], rows[1]["id"]}
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_one_dimensional_multiple_marked_layers_resize_and_reflow_once() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    overlay._smart_marked_ids = {rows[0]["id"], rows[1]["id"]}
    marked_rows = [
        row for row in overlay._multi_transform_rows()
        if row["id"] in overlay._smart_marked_ids
    ]
    bounds = overlay._selection_bounds(marked_rows)
    handle = overlay._handle_rects(bounds)["e"].center().toPoint()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
    assert overlay._interaction == "smart_resize_multi"
    QTest.mouseMove(overlay, QPoint(handle.x() + 24, handle.y()), delay=1)
    QTest.mouseRelease(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=QPoint(handle.x() + 24, handle.y()),
    )
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert changes[rows[0]["id"]]["width"] > rows[0]["width"]
    assert changes[rows[1]["id"]]["width"] > rows[1]["width"]
    first_right = changes[rows[0]["id"]]["x"] + changes[rows[0]["id"]]["width"]
    assert changes[rows[1]["id"]]["x"] - first_right == 20.0
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_one_dimensional_double_click_marks_every_layer() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    center = overlay._smart_selection_center_handles()[0]["rect"].center().toPoint()

    QTest.mouseDClick(overlay, Qt.MouseButton.LeftButton, pos=center)
    assert overlay._smart_marked_ids == {row["id"] for row in rows}
    assert overlay.smart_marked_object_ids() == [row["id"] for row in rows]
    assert overlay._interaction == ""
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_smart_marked_keyboard_commands_keep_delete_and_duplicate_distinct() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    commands: list[tuple[str, bool]] = []
    overlay.key_command.connect(
        lambda command, coarse: commands.append((command, coarse))
    )
    center = overlay._smart_selection_center_handles()[0]["rect"].center().toPoint()
    QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=center)

    QTest.keyClick(overlay, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClick(overlay, Qt.Key.Key_Backspace)

    assert commands == [("duplicate", False), ("delete", False)]
    assert overlay.smart_marked_object_ids() == [rows[0]["id"]]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_smart_marks_are_pruned_when_selection_contract_changes() -> None:
    _app()
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.set_document(document)
    overlay._smart_marked_ids = {rows[0]["id"], rows[1]["id"]}
    document["selection"] = {
        "object_id": rows[2]["id"],
        "object_ids": [rows[2]["id"]],
    }

    overlay.set_document(document)

    assert overlay._smart_marked_ids == set()
    assert overlay.smart_marked_object_ids() == []


def test_grid_shift_double_click_marks_row_then_double_click_marks_all() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _grid_document()
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }

    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier,
        centers[rows[0]["id"]],
    )
    assert overlay._smart_marked_ids == {rows[0]["id"], rows[1]["id"]}

    QTest.mouseDClick(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=centers[rows[0]["id"]],
    )
    assert overlay._smart_marked_ids == {row["id"] for row in rows}
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_center_ring_drag_reorders_positions_with_blue_indicator() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, rows = _row_document(uniform=True)
    overlay = PainterUIDesignOverlay()
    overlay.resize(900, 650)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)
    centers = {
        handle["object_id"]: handle["rect"].center().toPoint()
        for handle in overlay._smart_selection_center_handles()
    }
    first_rect = overlay._object_rect(
        next(row for row in overlay._document["objects"] if row["id"] == rows[0]["id"])
    )
    target = QPoint(round(first_rect.left() - 12.0), round(first_rect.center().y()))

    QTest.mousePress(
        overlay,
        Qt.MouseButton.LeftButton,
        pos=centers[rows[2]["id"]],
    )
    assert overlay._smart_marked_ids == {rows[2]["id"]}
    assert overlay._interaction == "smart_reorder_pending"
    QTest.mouseMove(overlay, target, delay=1)
    assert overlay._interaction == "smart_reorder"
    assert not overlay._smart_reorder_indicator.isNull()
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    app.processEvents()

    assert len(emitted) == 1
    changes = emitted[0]
    assert changes[rows[2]["id"]]["x"] == 40.0
    assert changes[rows[0]["id"]]["x"] == 110.0
    assert changes[rows[1]["id"]]["x"] == 170.0
    assert [row["id"] for row in overlay._document["objects"]] == [
        row["id"] for row in document["objects"]
    ]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()
