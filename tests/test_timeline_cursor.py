from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication

from app import timeline_cursor


def test_trim_modes_use_horizontal_resize_cursor_without_qapplication():
    for mode in ("ripple", "roll", "slip", "slide", "trim", "trim_tool"):
        assert timeline_cursor._timeline_tool_cursor(mode) == Qt.CursorShape.SizeHorCursor


def test_hand_modes_use_open_hand_cursor_without_qapplication():
    assert timeline_cursor._timeline_tool_cursor("grab") == Qt.CursorShape.OpenHandCursor
    assert timeline_cursor._timeline_tool_cursor("move") == Qt.CursorShape.OpenHandCursor
    assert timeline_cursor._timeline_tool_cursor("pan") == Qt.CursorShape.OpenHandCursor


def test_custom_cursor_cache_reuses_cursor_instances():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    timeline_cursor._TIMELINE_CURSOR_CACHE.clear()

    first = timeline_cursor._timeline_tool_cursor("blade", phase=0)
    second = timeline_cursor._timeline_tool_cursor("scissors", phase=2)
    alternate_phase = timeline_cursor._timeline_tool_cursor("blade_tool", phase=1)

    assert isinstance(first, QCursor)
    assert first is second
    assert alternate_phase is timeline_cursor._timeline_tool_cursor("split", phase=3)
    assert first is not alternate_phase
    assert set(timeline_cursor._TIMELINE_CURSOR_CACHE) == {("scissors", 0), ("scissors", 1)}


def test_custom_icon_modes_return_qcursor():
    app = QApplication.instance() or QApplication([])
    assert app is not None
    timeline_cursor._TIMELINE_CURSOR_CACHE.clear()

    for mode in ("select", "zoom", "zoom_tool", "color_picker", "eyedropper", "ai", "assistant"):
        assert isinstance(timeline_cursor._timeline_tool_cursor(mode), QCursor)
