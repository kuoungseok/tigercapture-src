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


def test_zoom_percent_uses_strict_integer_tiger_product_domain() -> None:
    from app.painter_zoom import normalize_painter_zoom_percent

    assert normalize_painter_zoom_percent(0) == 25
    assert normalize_painter_zoom_percent(25) == 25
    assert normalize_painter_zoom_percent(800) == 800
    assert normalize_painter_zoom_percent(801) == 800
    for invalid in (True, False, 25.0, 25.5, "100", None):
        with pytest.raises(TypeError):
            normalize_painter_zoom_percent(invalid)


def test_zoom_factor_requires_finite_number_and_uses_same_domain() -> None:
    from app.painter_zoom import normalize_painter_zoom_factor

    assert normalize_painter_zoom_factor(0) == 0.25
    assert normalize_painter_zoom_factor(0.25) == 0.25
    assert normalize_painter_zoom_factor(1) == 1.0
    assert normalize_painter_zoom_factor(8) == 8.0
    assert normalize_painter_zoom_factor(9) == 8.0
    for invalid in (True, False, "1", None):
        with pytest.raises(TypeError):
            normalize_painter_zoom_factor(invalid)
    for invalid in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="finite"):
            normalize_painter_zoom_factor(invalid)


def test_gpu_capability_reports_the_shared_zoom_capacity() -> None:
    from app.painter_opengl import painter_canvas_gpu_capabilities
    from app.painter_zoom import PAINTER_ZOOM_MAX_PERCENT

    assert (
        painter_canvas_gpu_capabilities()["high_zoom_canvas"]["max_zoom_percent"]
        == PAINTER_ZOOM_MAX_PERCENT
    )


def test_live_canvas_and_dialog_zero_zoom_clamp_to_25_percent() -> None:
    _app()
    from app.drawing import DrawingCanvas, PaintDialog, create_blank_paint_pixmap

    canvas = DrawingCanvas()
    canvas.set_view_zoom_percent(0)
    assert canvas._view_zoom_percent == 25

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._set_zoom_percent(0)
    assert dialog.zoom_slider.value() == 25
    assert dialog._canvas_zoom == 0.25
    assert dialog.canvas._view_zoom_percent == 25
    dialog.close()


def test_canvas_pose_zero_zoom_uses_same_25_percent_contract() -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._canvas_pose_slots[0] = {
        "zoom": 0,
        "pan": [0, 0],
        "rotation_degrees": 0.0,
    }
    dialog._recall_canvas_pose(1)
    assert dialog._canvas_zoom == 0.25
    assert dialog.zoom_slider.value() == 25
    dialog.close()


def test_canvas_pan_clamp_is_symmetric_and_zero_when_content_fits() -> None:
    _app()
    from PySide6.QtCore import QPoint, QSize

    from app.drawing import PaintDialog

    assert PaintDialog._clamped_canvas_pan(
        QPoint(999, -999), canvas_size=QSize(300, 200), host_size=QSize(100, 80)
    ) == QPoint(100, -60)
    assert PaintDialog._clamped_canvas_pan(
        QPoint(-999, 999), canvas_size=QSize(300, 200), host_size=QSize(100, 80)
    ) == QPoint(-100, 60)
    assert PaintDialog._clamped_canvas_pan(
        QPoint(30, -20), canvas_size=QSize(80, 60), host_size=QSize(100, 80)
    ) == QPoint(0, 0)


def test_invalid_document_zoom_fails_before_painter_state_mutation(tmp_path: Path) -> None:
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=321,
        standalone=True,
    )
    before = (
        dialog._canvas_document_size,
        dialog._time_ms,
        tuple(layer.layer_id for layer in dialog._paint_layers),
        dialog._canvas_zoom,
        dict(dialog._output_settings),
    )
    payload = {
        "schema": "tigerstudio.painter.document.v3",
        "format_version": 3,
        "document": {"width": 128, "height": 96, "time_ms": 999},
        "view": {"zoom": "invalid"},
        "layers": [{"layer_id": "replacement", "name": "Replacement"}],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "invalid_zoom.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))

    with pytest.raises(TypeError, match="zoom factor"):
        dialog.open_document_from_path(path)
    after = (
        dialog._canvas_document_size,
        dialog._time_ms,
        tuple(layer.layer_id for layer in dialog._paint_layers),
        dialog._canvas_zoom,
        dict(dialog._output_settings),
    )
    assert after == before
    dialog.close()
