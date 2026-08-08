from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_grid_size_uses_strict_shared_tiger_domain() -> None:
    from app.painter_grid import normalize_painter_grid_size_px

    assert normalize_painter_grid_size_px(0) == 4
    assert normalize_painter_grid_size_px(4) == 4
    assert normalize_painter_grid_size_px(512) == 512
    assert normalize_painter_grid_size_px(999) == 512
    for invalid in (True, False, 4.0, "64", None):
        with pytest.raises(TypeError):
            normalize_painter_grid_size_px(invalid)


def test_canvas_and_dialog_zero_grid_size_share_four_pixel_minimum() -> None:
    _app()
    from app.drawing import DrawingCanvas, PaintDialog, create_blank_paint_pixmap

    canvas = DrawingCanvas()
    canvas.set_grid_options(size_px=0)
    assert canvas.grid_options()["size_px"] == 4
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    assert dialog._set_grid_options(size_px=0)["size_px"] == 4
    assert dialog.canvas.grid_options()["size_px"] == 4
    dialog.close()


def test_invalid_document_grid_fails_before_state_mutation(tmp_path: Path) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=321, standalone=True,
    )
    before = (dialog._canvas_document_size, dialog._time_ms, dialog._grid_size_px)
    payload = {
        "schema": "tigerstudio.painter.document.v3",
        "format_version": 3,
        "document": {"width": 128, "height": 96, "time_ms": 999},
        "view": {"grid_size_px": "invalid"},
        "layers": [{"layer_id": "replacement", "name": "Replacement"}],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "invalid_grid.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
    with pytest.raises(TypeError, match="grid size"):
        dialog.open_document_from_path(path)
    assert (dialog._canvas_document_size, dialog._time_ms, dialog._grid_size_px) == before
    dialog.close()
