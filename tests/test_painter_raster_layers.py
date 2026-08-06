from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_canvas_composites_raster_surfaces_in_paint_layer_order() -> None:
    app = _app()
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas
    from app.painter_raster_layers import transparent_raster

    bottom = transparent_raster(80, 40)
    bottom.fill(QColor("#C83232"))
    top = transparent_raster(80, 40)
    top_painter = QPainter(top)
    try:
        top_painter.fillRect(QRect(40, 0, 40, 40), QColor("#285ADC"))
    finally:
        top_painter.end()

    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.set_layer_view(
        {"bottom": True, "top": True},
        {"bottom": 100, "top": 100},
        {},
        ["bottom", "top"],
        {},
        raster_images={"bottom": bottom, "top": top},
    )
    output = QImage(80, 40, QImage.Format.Format_ARGB32_Premultiplied)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    try:
        canvas._paint_committed_strokes_qpainter(painter, [], 80, 40, 0)
    finally:
        painter.end()

    assert output.pixelColor(20, 20).name() == "#c83232"
    assert output.pixelColor(60, 20).name() == "#285adc"
    canvas.deleteLater()
    app.processEvents()


def test_raster_layer_visibility_opacity_and_mask_share_canvas_contract() -> None:
    app = _app()
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas
    from app.painter_raster_layers import transparent_raster

    image = transparent_raster(100, 50)
    image.fill(QColor("#40C878"))
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.set_layer_view(
        {"paint": True},
        {"paint": 50},
        {"paint": [(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)]},
        ["paint"],
        {},
        raster_images={"paint": image},
    )
    output = QImage(100, 50, QImage.Format.Format_ARGB32_Premultiplied)
    output.fill(Qt.GlobalColor.transparent)
    painter = QPainter(output)
    try:
        canvas._paint_committed_strokes_qpainter(painter, [], 100, 50, 0)
    finally:
        painter.end()

    assert output.pixelColor(25, 25).alpha() == 0
    assert 126 <= output.pixelColor(75, 25).alpha() <= 129
    canvas.deleteLater()
    app.processEvents()


def test_raster_helpers_round_trip_png_without_sharing_storage() -> None:
    _app()
    from PySide6.QtGui import QColor, QImage

    from app.painter_raster_layers import (
        copy_raster_map,
        raster_png_bytes,
        transparent_raster,
    )

    source = transparent_raster(32, 18)
    source.setPixelColor(7, 9, QColor("#A142CC"))
    copied = copy_raster_map({"layer": source})
    copied["layer"].setPixelColor(7, 9, QColor("#FFFFFF"))
    assert source.pixelColor(7, 9).name() == "#a142cc"
    encoded = raster_png_bytes(source)
    assert encoded
    restored = QImage.fromData(encoded, "PNG")
    assert restored.size() == source.size()
    assert restored.pixelColor(7, 9).name() == "#a142cc"


def test_raster_dimensions_reject_invalid_values_instead_of_creating_one_pixel() -> None:
    _app()
    from app.painter_raster_layers import normalized_raster, transparent_raster

    with pytest.raises(ValueError, match="raster width must be positive"):
        transparent_raster(0, 16)
    with pytest.raises(TypeError, match="raster height must be an integer"):
        normalized_raster(None, 16, 2.5)


def test_raster_has_pixels_reads_argb32_alpha_not_hidden_rgb() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.painter_raster_layers import raster_has_pixels, transparent_raster

    image = transparent_raster(5, 3)
    image.setPixelColor(2, 1, QColor(200, 100, 50, 0))
    assert raster_has_pixels(image) is False
    image.setPixelColor(2, 1, QColor(200, 100, 50, 1))
    assert raster_has_pixels(image) is True


def test_png_overlay_matches_raster_layer_order_opacity_and_mask() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import PaintLayer, compose_pil_paint_overlays
    from app.painter_raster_layers import transparent_raster

    bottom = transparent_raster(40, 20)
    bottom.fill(QColor("#CC2020"))
    top = transparent_raster(40, 20)
    top.fill(QColor("#2040CC"))
    overlay = compose_pil_paint_overlays(
        frame_size=(40, 20),
        paint_layers=[
            PaintLayer(layer_id="bottom", name="Bottom"),
            PaintLayer(
                layer_id="top",
                name="Top",
                opacity=50,
                mask=[(0.5, 0.0), (1.0, 0.0), (1.0, 1.0), (0.5, 1.0)],
                mask_enabled=True,
            ),
        ],
        layer_rasters={"bottom": bottom, "top": top},
    )

    assert overlay.getpixel((5, 10))[:3] == (204, 32, 32)
    mixed = overlay.getpixel((35, 10))
    assert 116 <= mixed[0] <= 120
    assert 47 <= mixed[1] <= 49
    assert 116 <= mixed[2] <= 120
    assert mixed[3] == 255


def test_import_and_selection_cut_paste_use_regular_raster_layers(tmp_path) -> None:
    app = _app()
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_raster_layers import transparent_raster

    source = transparent_raster(20, 10)
    source.fill(QColor("#34C8FF"))
    path = tmp_path / "swatch.png"
    assert source.save(str(path), "PNG")
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(100, 100, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    report = dialog.import_image_as_paint_layer(path)
    layer_id = report["layer_id"]
    assert dialog._paint_layer_by_id(layer_id) is not None
    assert not dialog.result_stickers()
    assert dialog._paint_layer_rasters[layer_id].pixelColor(50, 50).name() == "#34c8ff"

    dialog.canvas.select_rectangle(0.4, 0.4, 0.6, 0.6)
    dialog._copy_selected_layer()
    dialog._cut_selected_layer()
    assert dialog._paint_layer_rasters.get(layer_id) is None
    dialog._undo()
    assert dialog._paint_layer_rasters[layer_id].pixelColor(50, 50).name() == "#34c8ff"
    layer_count = len(dialog._paint_layers)
    dialog._paste_layer_clipboard()
    assert len(dialog._paint_layers) == layer_count + 1
    pasted_id = dialog._paint_layers[-1].layer_id
    assert dialog._paint_layer_rasters[pasted_id].pixelColor(50, 50).name() == "#34c8ff"
    assert dialog._paint_layer_rasters[pasted_id].pixelColor(10, 10).alpha() == 0
    QApplication.clipboard().clear()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_small_raster_edit_uses_layer_delta_history_not_document_raster_copy(
    monkeypatch,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    import app.painter_raster_layers as raster_layers

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(3840, 2160, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._new_paint_layer("Second")

    def reject_full_map_copy(_images):
        raise AssertionError("small raster edits must not snapshot every raster layer")

    monkeypatch.setattr(raster_layers, "copy_raster_map", reject_full_map_copy)
    assert dialog._fill_document("solid", color1=QColor("#8050C8"))
    command = dialog._undo_stack[-1]
    assert command["kind"] == "raster_replace"
    assert command["layer_id"] == dialog._active_paint_layer_id
    dialog._undo()
    assert dialog._paint_layer_raster(dialog._active_paint_layer_id) is None
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
