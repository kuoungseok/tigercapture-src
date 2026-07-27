from __future__ import annotations

import os


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _alpha_bounds(image):
    from PySide6.QtCore import QRect

    bounds = QRect()
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            point = QRect(x, y, 1, 1)
            bounds = point if bounds.isNull() else bounds.united(point)
    return bounds


def test_ui_color_and_font_use_css_rgba_and_document_scale() -> None:
    _app()
    from PySide6.QtGui import QFont

    from app.painter_ui_style_renderer import ui_color, ui_font

    color = ui_color("#11223344")
    assert color.getRgb() == (17, 34, 51, 68)
    font = ui_font(
        QFont(),
        {"font_size": 18, "font_weight": 600, "font_family": "Arial"},
        1.5,
    )
    assert font.pixelSize() == 27
    assert int(font.weight()) == 600
    assert font.family() == "Arial"


def test_object_shadow_renders_outside_source_geometry() -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    from app.painter_ui_style_renderer import draw_ui_object_shadow

    image = QImage(220, 140, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    rendered = draw_ui_object_shadow(
        painter,
        QRectF(60, 35, 100, 55),
        "rectangle",
        {
            "radius": 12,
            "shadow": {
                "x": 0,
                "y": 8,
                "blur": 15,
                "spread": 2,
                "color": "#10203099",
            },
        },
    )
    painter.end()

    bounds = _alpha_bounds(image)
    assert rendered is True
    assert bounds.left() < 60
    assert bounds.right() > 159
    assert bounds.bottom() > 89
    assert image.pixelColor(110, 98).alpha() > 0


def test_text_renderer_applies_alignment_weight_and_line_height() -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QFont, QImage, QPainter

    from app.painter_ui_style_renderer import draw_ui_text_block

    image = QImage(260, 140, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    report = draw_ui_text_block(
        painter,
        QRectF(0, 0, 240, 120),
        "RIGHT\nALIGNED",
        {
            "font_size": 20,
            "font_weight": 700,
            "text_align": "right",
            "line_height": 1.8,
            "text_color": "#F4C65EFF",
            "text_shadow": {
                "x": 2,
                "y": 3,
                "blur": 0,
                "spread": 0,
                "color": "#00000088",
            },
        },
        QFont(),
    )
    painter.end()

    bounds = _alpha_bounds(image)
    assert report["alignment"] == "right"
    assert report["font_weight"] == 700
    assert report["line_count"] == 2
    assert report["line_height"] == 1.8
    assert report["layout_height"] > report["font_pixel_size"] * 2
    assert bounds.left() > 80
    assert 228 <= bounds.right() <= 240


def test_canvas_object_renderer_calls_shared_style_renderer(monkeypatch) -> None:
    app = _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QImage, QPainter

    import app.painter_ui_workspace as workspace
    from app.painter_ui_document import add_ui_object, create_ui_document

    document = create_ui_document(390, 844, name="Phone")
    document, row = add_ui_object(
        document,
        kind="button",
        name="CTA",
        x=24,
        y=32,
        width=220,
        height=64,
        style={
            "fill": "#334455",
            "font_weight": 600,
            "text_align": "center",
            "shadow": {"x": 0, "y": 6, "blur": 12, "color": "#00000066"},
        },
        content={"text": "Continue"},
    )
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        workspace,
        "draw_ui_object_shadow",
        lambda _painter, _rect, kind, style, **_kwargs: calls.append(
            ("shadow", (kind, dict(style)))
        ),
    )
    monkeypatch.setattr(
        workspace,
        "draw_ui_text_block",
        lambda _painter, _rect, text, style, _font, **_kwargs: calls.append(
            ("text", (text, dict(style)))
        ),
    )
    overlay = workspace.PainterUIDesignOverlay()
    overlay.resize(600, 700)
    overlay.set_document(document)
    image = QImage(600, 700, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    overlay._paint_object(painter, row)
    painter.end()

    assert calls[0][0] == "shadow"
    assert calls[0][1][0] == "button"
    assert calls[1][0] == "text"
    assert calls[1][1][0] == "Continue"
    assert calls[1][1][1]["text_align"] == "center"
    overlay.deleteLater()
    app.processEvents()


def test_layer_and_background_blur_render_real_pixel_blending() -> None:
    _app()
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.painter_ui_style_renderer import (
        blur_ui_image,
        draw_ui_background_blur,
        ui_blur_radius,
    )

    source = QImage(80, 40, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(QColor("#000000"))
    painter = QPainter(source)
    painter.fillRect(QRectF(40, 0, 40, 40), QColor("#FFFFFF"))
    painter.end()
    blurred = blur_ui_image(source, 6)
    assert 0 < blurred.pixelColor(39, 20).red() < 255
    assert 0 < blurred.pixelColor(40, 20).red() < 255

    surface = source.copy()
    painter = QPainter(surface)
    style = {
        "radius": 4,
        "effects": [{"type": "background_blur", "radius": 6}],
    }
    assert draw_ui_background_blur(
        painter,
        surface,
        QRectF(24, 4, 32, 32),
        "rectangle",
        style,
    )
    painter.end()
    assert 0 < surface.pixelColor(39, 20).red() < 255
    assert ui_blur_radius(style, "background_blur") == 6
