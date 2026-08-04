from __future__ import annotations

import copy
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_m14_selection_has_edge_and_corner_resize_handles() -> None:
    _app()
    from PySide6.QtCore import QPointF, QRectF, Qt

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=100,
        y=100,
        width=200,
        height=100,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    selected = next(item for item in overlay._document["objects"] if item["id"] == row["id"])
    rect = overlay._object_rect(selected)

    assert set(overlay._handle_rects(rect)) == {
        "nw", "n", "ne", "e", "se", "s", "sw", "w"
    }

    overlay._interaction = "resize"
    overlay._active_object_id = row["id"]
    overlay._active_handle = "e"
    overlay._original_rect = QRectF(rect)
    resized = overlay._resize_rect(
        QPointF(rect.right() + 80.0, rect.center().y()),
        Qt.KeyboardModifier.NoModifier,
    )
    assert resized.left() == rect.left()
    assert resized.height() == rect.height()
    assert resized.width() > rect.width()

    proportional = overlay._resize_rect(
        QPointF(rect.right() + 80.0, rect.center().y()),
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert abs(proportional.width() / proportional.height() - 2.0) < 0.001


def test_m14_single_layer_alignment_uses_its_parent_frame() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, frame = add_ui_object(
        create_ui_document(800, 600),
        kind="frame",
        x=100,
        y=80,
        width=400,
        height=300,
    )
    document, child = add_ui_object(
        document,
        kind="rectangle",
        parent_id=frame["id"],
        x=150,
        y=120,
        width=100,
        height=50,
    )
    document["selection"] = {
        "object_id": child["id"],
        "object_ids": [child["id"]],
    }
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)

    dialog._align_painter_ui_object(child["id"], "left")
    aligned = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["id"] == child["id"]
    )
    assert aligned["x"] == 100.0

    dialog._align_painter_ui_object(child["id"], "bottom")
    aligned = next(
        row for row in dialog._painter_ui_document["objects"]
        if row["id"] == child["id"]
    )
    assert aligned["y"] == 330.0
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_m14_arrow_nudge_moves_the_complete_selection() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_document import add_ui_object, create_ui_document

    document, first = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=40,
        y=50,
        width=100,
        height=60,
    )
    document, second = add_ui_object(
        document,
        kind="ellipse",
        x=220,
        y=150,
        width=80,
        height=50,
    )
    document["selection"] = {
        "object_id": first["id"],
        "object_ids": [first["id"], second["id"]],
    }
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_ui_document = copy.deepcopy(document)

    dialog._handle_painter_ui_key_command("right", False)
    moved = {row["id"]: row for row in dialog._painter_ui_document["objects"]}
    assert moved[first["id"]]["x"] == 41.0
    assert moved[second["id"]]["x"] == 221.0

    dialog._handle_painter_ui_key_command("down", True)
    moved = {row["id"]: row for row in dialog._painter_ui_document["objects"]}
    assert moved[first["id"]]["y"] == 60.0
    assert moved[second["id"]]["y"] == 160.0
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_m14_object_snap_and_grid_snap_are_independent() -> None:
    _app()
    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    assert overlay.object_snap_enabled() is True
    assert overlay.snap_enabled() is False
    assert overlay._snap(13.0) == 13.0
    overlay.set_snap(True, 8.0)
    assert overlay._snap(13.0) == 16.0


def test_m14_official_alignment_shortcuts_dispatch_commands() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_workspace import PainterUIDesignOverlay

    overlay = PainterUIDesignOverlay()
    overlay.show()
    app.processEvents()
    emitted: list[tuple[str, bool]] = []
    overlay.key_command.connect(
        lambda command, coarse: emitted.append((command, coarse))
    )

    for key, command in (
        (Qt.Key.Key_A, "align_left"),
        (Qt.Key.Key_H, "align_hcenter"),
        (Qt.Key.Key_D, "align_right"),
        (Qt.Key.Key_W, "align_top"),
        (Qt.Key.Key_V, "align_vcenter"),
        (Qt.Key.Key_S, "align_bottom"),
    ):
        QTest.keyClick(overlay, key, Qt.KeyboardModifier.AltModifier)
        assert emitted[-1] == (command, False)
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def _send_rotation_move(overlay, point, modifiers) -> None:
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    local = QPointF(point)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        local,
        QPointF(overlay.mapToGlobal(point)),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        modifiers,
    )
    QApplication.sendEvent(overlay, event)


def test_m15_rotation_uses_figma_sign_and_shift_fifteen_degree_snap() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, row = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=300,
        y=200,
        width=120,
        height=80,
    )
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    selected = next(item for item in overlay._document["objects"] if item["id"] == row["id"])
    rect = overlay._object_rect(selected)
    handle = overlay._rotation_handle_rect(rect).center().toPoint()
    pivot = rect.center().toPoint()

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
    clockwise = QPoint(pivot.x() + 60, pivot.y() - 22)
    _send_rotation_move(
        overlay,
        clockwise,
        Qt.KeyboardModifier.ShiftModifier,
    )
    assert selected["rotation"] == -75.0
    assert overlay._rotation_label == "-75°"
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=clockwise)

    document["objects"][0]["rotation"] = 0.0
    overlay.set_document(document)
    overlay.set_snap(True, 8.0)
    selected = overlay._document["objects"][0]
    rect = overlay._object_rect(selected)
    handle = overlay._rotation_handle_rect(rect).center().toPoint()
    pivot = rect.center().toPoint()
    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
    _send_rotation_move(
        overlay,
        QPoint(pivot.x() + 60, pivot.y() - 22),
        Qt.KeyboardModifier.NoModifier,
    )
    assert -72.0 < selected["rotation"] < -68.0
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=clockwise)
    overlay.close()
    overlay.deleteLater()
    app.processEvents()


def test_m15_multi_selection_rotates_around_common_center() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.painter_ui_document import add_ui_object, create_ui_document
    from app.painter_ui_workspace import PainterUIDesignOverlay

    document, first = add_ui_object(
        create_ui_document(800, 600),
        kind="rectangle",
        x=100,
        y=200,
        width=100,
        height=60,
    )
    document, second = add_ui_object(
        document,
        kind="ellipse",
        x=300,
        y=200,
        width=100,
        height=60,
    )
    document["selection"] = {
        "object_id": first["id"],
        "object_ids": [first["id"], second["id"]],
    }
    overlay = PainterUIDesignOverlay()
    overlay.resize(800, 600)
    overlay.set_document(document)
    overlay.show()
    app.processEvents()
    bounds = overlay._selection_bounds(overlay._multi_transform_rows())
    handle = overlay._rotation_handle_rect(bounds).center().toPoint()
    pivot = bounds.center().toPoint()
    emitted: list[dict] = []
    overlay.objects_changes_requested.connect(emitted.append)

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=handle)
    assert overlay._interaction == "rotate_multi"
    target = QPoint(pivot.x() + 80, pivot.y())
    QTest.mouseMove(overlay, target)
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=target)
    assert emitted
    assert set(emitted[-1]) == {first["id"], second["id"]}
    assert abs(emitted[-1][first["id"]]["rotation"] + 90.0) < 0.5
    assert abs(emitted[-1][second["id"]]["rotation"] + 90.0) < 0.5
    assert emitted[-1][first["id"]]["y"] != first["y"]
    assert emitted[-1][second["id"]]["y"] != second["y"]
    overlay.close()
    overlay.deleteLater()
    app.processEvents()
