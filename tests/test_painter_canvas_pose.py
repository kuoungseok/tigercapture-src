from __future__ import annotations

import math
import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_canvas_pose_transform_round_trips_document_coordinates() -> None:
    _app()
    from PySide6.QtCore import QPointF, QSize

    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(100, 200)
    canvas.set_view_pose(
        rotation_degrees=90.0,
        content_size=QSize(200, 100),
    )

    document_point = QPointF(37.5, 62.25)
    view_point = canvas.map_canvas_to_view(document_point)
    restored = canvas.map_view_to_canvas(view_point)

    assert math.isclose(restored.x(), document_point.x(), abs_tol=1e-6)
    assert math.isclose(restored.y(), document_point.y(), abs_tol=1e-6)
    assert canvas.canvas_contains_view_point(view_point)


def test_rotated_mouse_stroke_is_saved_in_document_coordinates() -> None:
    app = _app()
    from PySide6.QtCore import QEvent, QPointF, QSize, Qt
    from PySide6.QtGui import QMouseEvent

    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(100, 200)
    canvas.set_view_pose(
        rotation_degrees=90.0,
        content_size=QSize(200, 100),
    )
    canvas.set_tool("pen")
    emitted = []
    canvas.stroke_added.connect(emitted.append)

    first = canvas.map_canvas_to_view(QPointF(20, 40))
    second = canvas.map_canvas_to_view(QPointF(160, 60))
    for event_type, point, buttons in (
        (
            QEvent.Type.MouseButtonPress,
            first,
            Qt.MouseButton.LeftButton,
        ),
        (
            QEvent.Type.MouseMove,
            second,
            Qt.MouseButton.LeftButton,
        ),
        (
            QEvent.Type.MouseButtonRelease,
            second,
            Qt.MouseButton.NoButton,
        ),
    ):
        event = QMouseEvent(
            event_type,
            point,
            point,
            Qt.MouseButton.LeftButton,
            buttons,
            Qt.KeyboardModifier.NoModifier,
        )
        app.sendEvent(canvas, event)

    assert len(emitted) == 1
    assert emitted[0].points[0] == (0.1, 0.4)
    assert emitted[0].points[-1] == (0.8, 0.6)


def test_canvas_pose_slots_restore_rotation_zoom_and_pan() -> None:
    app = _app()
    from PySide6.QtCore import QPoint

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(
            640,
            360,
            "transparent",
        ),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    dialog._set_zoom_percent(150)
    dialog._set_canvas_pan(QPoint(12, -8))
    dialog._set_canvas_rotation(32.0)
    dialog._save_canvas_pose(1)

    dialog._set_zoom_percent(100)
    dialog._set_canvas_pan(QPoint(0, 0))
    dialog._reset_canvas_rotation()
    dialog._recall_canvas_pose(1)

    state = dialog.painter_action_state()["view"]
    assert state["rotation_degrees"] == 32.0
    assert state["zoom_percent"] == 150
    assert dialog._canvas_pose_slots[0]["rotation_degrees"] == 32.0
    assert dialog._bg_label.isHidden()

    payload = dialog._painter_document_payload()
    assert payload["view"]["rotation_degrees"] == 32.0
    assert payload["view"]["pose_slots"][0]["zoom"] == 1.5

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_canvas_pose_drag_snaps_and_alt_drag_is_temporary() -> None:
    app = _app()
    from PySide6.QtCore import QPoint, Qt

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    host = dialog._canvas_host
    center = dialog._canvas_rotation_center_in_host().toPoint()
    start = QPoint(center.x() + 100, center.y())
    diagonal = QPoint(center.x() + 70, center.y() + 70)

    dialog._begin_canvas_rotation(
        host,
        start,
        Qt.KeyboardModifier.NoModifier,
    )
    dialog._update_canvas_rotation_drag(
        host,
        diagonal,
        Qt.KeyboardModifier.ShiftModifier,
    )
    dialog._finish_canvas_rotation_drag()
    assert dialog._canvas_rotation_degrees == 45.0

    center = dialog._canvas_rotation_center_in_host().toPoint()
    start = QPoint(center.x() + 100, center.y())
    down = QPoint(center.x(), center.y() + 100)
    dialog._begin_canvas_rotation(
        host,
        start,
        Qt.KeyboardModifier.AltModifier,
    )
    dialog._update_canvas_rotation_drag(
        host,
        down,
        Qt.KeyboardModifier.AltModifier,
    )
    assert dialog._canvas_rotation_degrees == 135.0
    dialog._finish_canvas_rotation_drag()
    assert dialog._canvas_rotation_degrees == 45.0

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_rotation_reuses_retained_stroke_cache() -> None:
    _app()
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke

    strokes = [
        Stroke(points=[(0.1, index / 20.0), (0.9, index / 20.0)])
        for index in range(1, 10)
    ]
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(320, 180)
    canvas.set_strokes_snapshot(strokes)
    calls = {"count": 0}

    def count_stroke(*_args, **_kwargs):
        calls["count"] += 1

    canvas._paint_stroke = count_stroke
    target = QImage(320, 180, QImage.Format.Format_ARGB32_Premultiplied)
    painter = QPainter(target)
    try:
        canvas._paint_strokes_with_cpu_cache(
            painter,
            strokes,
            320,
            180,
            0,
        )
        assert calls["count"] == len(strokes)
        canvas.set_view_pose(
            rotation_degrees=47.0,
            content_size=QSize(320, 180),
        )
        canvas._paint_strokes_with_cpu_cache(
            painter,
            strokes,
            320,
            180,
            0,
        )
        assert calls["count"] == len(strokes)
    finally:
        painter.end()
