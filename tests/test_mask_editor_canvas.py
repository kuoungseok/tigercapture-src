import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from app.mask_editor_window import _FrameCanvas


def _app():
    return QApplication.instance() or QApplication([])


def test_canvas_undo_redo_restores_mask_and_polygon_points():
    _app()
    canvas = _FrameCanvas(np.zeros((16, 16, 3), dtype=np.uint8))
    canvas._mask = np.zeros((16, 16), dtype=np.uint8)
    canvas._points = [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]
    canvas._push_history()

    canvas._mask[5, 5] = 255
    canvas._points.append((0.1, 0.2))

    assert canvas.undo_mask()
    assert canvas._mask[5, 5] == 0
    assert canvas.current_polygon_points() == [(0.1, 0.1), (0.2, 0.1), (0.2, 0.2)]

    assert canvas.redo_mask()
    assert canvas._mask[5, 5] == 255
    assert canvas.current_polygon_points()[-1] == (0.1, 0.2)


def test_canvas_foreground_and_background_brush_edit_bitmap_mask():
    _app()
    canvas = _FrameCanvas(np.zeros((32, 32, 3), dtype=np.uint8))
    canvas.set_brush_radius(3)

    canvas._paint_brush(QPoint(16, 16), foreground=True)
    assert canvas.current_mask() is not None
    assert int(canvas.current_mask().sum()) > 0

    canvas._paint_brush(QPoint(16, 16), foreground=False)
    assert int(canvas.current_mask()[16, 16]) == 0
