from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_pencil_points_become_smoothed_editable_vector_network() -> None:
    _app()
    from app.painter_ui_pencil import pencil_vector_object

    result = pencil_vector_object(
        [(10, 20), (20, 24), (30, 34), (40, 28), (50, 42)],
        smoothing=0.55,
    )
    network = result["content"]["vector_network"]

    assert (result["x"], result["y"]) == (10.0, 20.0)
    assert result["width"] == 40.0
    assert result["height"] == 22.0
    assert len(network["nodes"]) >= 3
    assert all(segment["kind"] == "cubic" for segment in network["segments"])
    assert network["closed"] is False
    assert result["content"]["vector_paths"]


def test_pencil_tool_previews_drag_and_creates_path_layer() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    dialog._set_painter_ui_tool("pencil")
    overlay = dialog._painter_ui_overlay
    overlay.resize(900, 700)
    overlay.show()
    app.processEvents()
    viewport, _scale = overlay._artboard_viewport()
    points = [
        QPoint(round(viewport.left() + x), round(viewport.top() + y))
        for x, y in ((100, 100), (125, 112), (150, 95), (180, 130))
    ]

    QTest.mousePress(overlay, Qt.MouseButton.LeftButton, pos=points[0])
    for point in points[1:]:
        QTest.mouseMove(overlay, point, delay=4)
    assert overlay._interaction == "pencil_draw"
    assert len(overlay._pencil_points) >= 4
    QTest.mouseRelease(overlay, Qt.MouseButton.LeftButton, pos=points[-1])
    app.processEvents()

    row = dialog._painter_ui_document["objects"][-1]
    assert row["kind"] == "path"
    assert row["name"] == "Pencil 1"
    assert row["style"]["stroke_cap"] == "round"
    assert row["content"]["pencil_smoothing"] == 0.55
    assert row["content"]["vector_network"]["segments"]
    assert overlay.tool() == "pencil"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_pen_and_pencil_keyboard_shortcuts_switch_tools() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(800, 600, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_canvas_workspace_mode("ui_design")
    overlay = dialog._painter_ui_overlay
    overlay.show()
    overlay.setFocus()

    QTest.keyClick(overlay, Qt.Key.Key_P)
    assert overlay.tool() == "path"
    QTest.keyClick(overlay, Qt.Key.Key_P, Qt.KeyboardModifier.ShiftModifier)
    assert overlay.tool() == "pencil"
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
