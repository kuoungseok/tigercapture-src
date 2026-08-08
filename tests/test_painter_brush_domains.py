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


def test_brush_detail_domains_are_strict_integers_and_clamped() -> None:
    from app.painter_brush_domains import normalize_brush_detail_integer

    cases = {
        "hardness": (0, 1, 101, 100),
        "spacing": (0, 1, 201, 200),
        "angle": (-181, -180, 181, 180),
        "roundness": (0, 10, 101, 100),
        "pressure_response": (0, 25, 251, 250),
    }
    for field, (low_input, low, high_input, high) in cases.items():
        assert normalize_brush_detail_integer(low_input, field=field) == low
        assert normalize_brush_detail_integer(high_input, field=field) == high
        for invalid in (True, 1.0, "1", None):
            with pytest.raises(TypeError):
                normalize_brush_detail_integer(invalid, field=field)


def test_brush_width_uses_persisted_product_domain() -> None:
    from app.painter_brush_domains import (
        BRUSH_WIDTH_DEFAULT_PX,
        normalize_brush_width_px,
    )

    assert BRUSH_WIDTH_DEFAULT_PX == 6.0
    assert normalize_brush_width_px(0) == 1.0
    assert normalize_brush_width_px(12.5) == 12.5
    assert normalize_brush_width_px(6000) == 5000.0
    for invalid in (True, "6", None):
        with pytest.raises(TypeError):
            normalize_brush_width_px(invalid)
    for invalid in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            normalize_brush_width_px(invalid)


def test_brush_detail_settings_validate_numeric_and_boolean_fields() -> None:
    from app.painter_brush_domains import normalize_brush_detail_settings

    assert normalize_brush_detail_settings(
        {"hardness": 0, "spacing": 999, "flip_x": True}
    )["hardness"] == 1
    assert normalize_brush_detail_settings(
        {"hardness": 0, "spacing": 999, "flip_x": True}
    )["spacing"] == 200
    with pytest.raises(TypeError, match="flip_x"):
        normalize_brush_detail_settings({"flip_x": 1})
    with pytest.raises(TypeError, match="hardness"):
        normalize_brush_detail_settings({"hardness": "100"})


def test_live_canvas_uses_shared_brush_detail_domains() -> None:
    _app()
    from app.drawing import DrawingCanvas

    canvas = DrawingCanvas()
    canvas.set_brush_detail(
        hardness=0, spacing=999, angle=-999, roundness=0, pressure_response=999
    )
    assert canvas._brush_hardness == 1
    assert canvas._brush_spacing == 200
    assert canvas._brush_angle == -180
    assert canvas._brush_roundness == 10
    assert canvas._brush_pressure_response == 250


def test_invalid_saved_brush_width_fails_before_document_mutation(tmp_path: Path) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=321, standalone=True,
    )
    before = (dialog._canvas_document_size, dialog._time_ms, dialog._pen_width)
    payload = {
        "schema": "tigerstudio.painter.document.v3",
        "format_version": 3,
        "document": {"width": 128, "height": 96, "time_ms": 999},
        "brush": {"width": "invalid"},
        "layers": [{"layer_id": "replacement", "name": "Replacement"}],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "invalid_brush_width.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
    with pytest.raises(TypeError, match="brush width"):
        dialog.open_document_from_path(path)
    assert (dialog._canvas_document_size, dialog._time_ms, dialog._pen_width) == before
    dialog.close()


def test_invalid_saved_brush_detail_fails_before_document_mutation(tmp_path: Path) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[], time_ms=321, standalone=True,
    )
    before = (
        dialog._canvas_document_size,
        dialog._time_ms,
        dict(dialog._brush_detail_settings),
    )
    payload = {
        "schema": "tigerstudio.painter.document.v3",
        "format_version": 3,
        "document": {"width": 128, "height": 96, "time_ms": 999},
        "brush": {"detail": {"hardness": "invalid"}},
        "layers": [{"layer_id": "replacement", "name": "Replacement"}],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "invalid_brush_detail.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
    with pytest.raises(TypeError, match="hardness"):
        dialog.open_document_from_path(path)
    assert (
        dialog._canvas_document_size,
        dialog._time_ms,
        dict(dialog._brush_detail_settings),
    ) == before
    dialog.close()
