from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_figma_text_resize_modes_compute_distinct_geometry() -> None:
    _app()
    from app.painter_ui_text_layout import text_content_geometry

    style = {"font_family": "Arial", "font_size": 20, "line_height": 1.2}
    auto_width = text_content_geometry(
        "Tiger Studio", style, mode="auto_width", width=30, height=10
    )
    auto_height = text_content_geometry(
        "Tiger Studio text wraps here",
        style,
        mode="auto_height",
        width=90,
        height=10,
    )
    fixed = text_content_geometry(
        "Tiger Studio", style, mode="fixed_size", width=90, height=44
    )

    assert auto_width[0] > 30
    assert auto_height[0] == 90
    assert auto_height[1] > 24
    assert fixed == (90, 44)
