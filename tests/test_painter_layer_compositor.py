from __future__ import annotations

import os

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_clipping_layer_uses_previous_sibling_alpha() -> None:
    _app()
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QPainter

    from app.drawing import PaintLayer
    from app.painter_layer_compositor import composite_layer_images
    from app.painter_raster_layers import transparent_raster

    base = transparent_raster(40, 20)
    painter = QPainter(base)
    try:
        painter.fillRect(QRect(0, 0, 20, 20), QColor("#42C878"))
    finally:
        painter.end()
    clipped = transparent_raster(40, 20)
    clipped.fill(QColor("#315FE0"))
    output = composite_layer_images(
        [
            PaintLayer("base", "Base"),
            PaintLayer("clip", "Clip", clipping=True),
        ],
        {"base": base, "clip": clipped},
        40,
        20,
    )
    assert output.pixelColor(10, 10).name() == "#315fe0"
    assert output.pixelColor(30, 10).alpha() == 0


def test_layer_compositor_rejects_invalid_raster_dimensions() -> None:
    from app.painter_layer_compositor import composite_layer_images

    with pytest.raises(ValueError, match="compositor width must be positive"):
        composite_layer_images([], {}, 0, 8)


def test_group_opacity_and_extended_blend_modes_are_composited() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import PaintLayer
    from app.painter_layer_compositor import composite_layer_images
    from app.painter_raster_layers import transparent_raster

    backdrop = transparent_raster(20, 20)
    backdrop.fill(QColor("#808080"))
    child = transparent_raster(20, 20)
    child.fill(QColor("#8080FF"))
    output = composite_layer_images(
        [
            PaintLayer("back", "Backdrop"),
            PaintLayer("group", "Group", node_type="group", opacity=50),
            PaintLayer(
                "child",
                "Child",
                parent_id="group",
                blend_mode="multiply",
            ),
        ],
        {"back": backdrop, "child": child},
        20,
        20,
    )
    color = output.pixelColor(10, 10)
    assert 127 <= color.red() <= 129
    assert 127 <= color.green() <= 129
    assert 190 <= color.blue() <= 192

    multiplied = composite_layer_images(
        [
            PaintLayer("back", "Backdrop"),
            PaintLayer("child", "Child", blend_mode="multiply"),
        ],
        {"back": backdrop, "child": child},
        20,
        20,
    ).pixelColor(10, 10)
    assert 63 <= multiplied.red() <= 65
    assert 63 <= multiplied.green() <= 65
    assert 127 <= multiplied.blue() <= 129


def test_hidden_group_hides_children_without_mutating_sources() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import PaintLayer
    from app.painter_layer_compositor import composite_layer_images
    from app.painter_raster_layers import transparent_raster

    source = transparent_raster(12, 12)
    source.fill(QColor("#F08030"))
    output = composite_layer_images(
        [
            PaintLayer("group", "Group", node_type="group", visible=False),
            PaintLayer("child", "Child", parent_id="group"),
        ],
        {"child": source},
        12,
        12,
    )
    assert output.pixelColor(6, 6).alpha() == 0
    assert source.pixelColor(6, 6).name() == "#f08030"


def test_raster_layer_mask_takes_priority_and_preserves_gray_alpha() -> None:
    _app()
    from PySide6.QtGui import QColor

    from app.drawing import PaintLayer
    from app.painter_layer_compositor import composite_layer_images
    from app.painter_layer_masks import alpha8_mask, paint_mask_circle
    from app.painter_raster_layers import transparent_raster

    layer = PaintLayer(
        "paint-layer-1",
        "Paint",
        mask=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        mask_enabled=True,
    )
    source = transparent_raster(20, 20)
    source.fill(QColor(220, 80, 30, 255))
    mask = paint_mask_circle(alpha8_mask(20, 20, 0), (10, 10), 4, 128)
    output = composite_layer_images(
        [layer],
        {layer.layer_id: source},
        20,
        20,
        layer_masks={layer.layer_id: mask},
    )
    assert output.pixelColor(10, 10).alpha() in range(127, 130)
    assert output.pixelColor(1, 1).alpha() == 0


def test_canvas_and_png_export_share_advanced_layer_compositor() -> None:
    app = _app()
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas, PaintLayer, compose_pil_paint_overlays
    from app.painter_raster_layers import transparent_raster

    base = transparent_raster(48, 24)
    painter = QPainter(base)
    try:
        painter.fillRect(QRect(0, 0, 30, 24), QColor("#C05040"))
    finally:
        painter.end()
    clipped = transparent_raster(48, 24)
    clipped.fill(QColor("#40A0D0"))
    layers = [
        PaintLayer("group", "Group", node_type="group", opacity=70),
        PaintLayer("base", "Base", parent_id="group"),
        PaintLayer(
            "clip",
            "Clip",
            parent_id="group",
            clipping=True,
            blend_mode="screen",
        ),
    ]
    rasters = {"base": base, "clip": clipped}
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.set_layer_view(
        {row.layer_id: row.visible for row in layers},
        {row.layer_id: row.opacity for row in layers},
        {},
        [row.layer_id for row in layers],
        {},
        raster_images=rasters,
        layers=layers,
    )
    canvas_image = QImage(48, 24, QImage.Format.Format_ARGB32_Premultiplied)
    canvas_image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas_image)
    try:
        canvas._paint_committed_strokes_qpainter(painter, [], 48, 24, 0)
    finally:
        painter.end()
    exported = compose_pil_paint_overlays(
        frame_size=(48, 24), paint_layers=layers, layer_rasters=rasters
    )
    for point in ((5, 12), (29, 12), (40, 12)):
        qt = canvas_image.pixelColor(*point)
        assert exported.getpixel(point) == (qt.red(), qt.green(), qt.blue(), qt.alpha())
    canvas.deleteLater()
    app.processEvents()
