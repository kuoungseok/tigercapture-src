from __future__ import annotations

import os

import pytest


def test_shared_painter_dimensions_are_strict_and_preserve_small_values() -> None:
    from app.painter_dimensions import (
        finite_real,
        nonnegative_real,
        positive_integer,
        positive_real,
    )

    assert positive_integer(1, field="width") == 1
    assert positive_real(1.0e-12, field="physical width") == 1.0e-12
    assert nonnegative_real(0.0, field="bleed") == 0.0
    assert finite_real(-1.0e-12, field="offset") == -1.0e-12
    with pytest.raises(TypeError, match="not bool"):
        positive_integer(True, field="width")
    with pytest.raises(TypeError, match="must be an integer"):
        positive_integer(1.5, field="width")
    with pytest.raises(ValueError, match="must be positive"):
        positive_real(0.0, field="physical width")
    with pytest.raises(ValueError, match="must be nonnegative"):
        nonnegative_real(-1.0e-12, field="bleed")
    with pytest.raises(ValueError, match="must be finite"):
        finite_real(float("nan"), field="offset")


def test_canvas_view_and_export_dimensions_do_not_use_one_pixel_fallbacks(tmp_path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QApplication

    from app.drawing import (
        DrawingCanvas,
        PaintDialog,
        create_blank_paint_pixmap,
        export_paint_png,
    )

    app = QApplication.instance() or QApplication([])
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    with pytest.raises(ValueError, match="view content width must be positive"):
        canvas.set_view_pose(rotation_degrees=0.0, content_size=QSize(0, 10))
    with pytest.raises(ValueError, match="stable render width must be positive"):
        canvas.stable_render_size(width=0, height=10)

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(16, 16, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    with pytest.raises(ValueError, match="export height must be positive"):
        dialog.export_png_to_path(tmp_path / "invalid.png", width=8, height=0)
    with pytest.raises(ValueError, match="PNG export width must be positive"):
        export_paint_png(tmp_path / "invalid-direct.png", frame_size=(0, 8))
    with pytest.raises(TypeError, match="PNG export width must be an integer"):
        export_paint_png(tmp_path / "invalid-direct.png", frame_size=(8.5, 8))
    dialog.close()
    canvas.deleteLater()
    dialog.deleteLater()
    app.processEvents()
