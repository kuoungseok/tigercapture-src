"""Deterministic style rendering helpers for Painter UI objects."""
from __future__ import annotations

import html
import math
from typing import Any, Mapping

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGradient,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTextCharFormat,
    QTextLayout,
    QTextOption,
)
from PySide6.QtSvg import QSvgRenderer


def ui_color(value: object, fallback: str = "#000000") -> QColor:
    """Parse UI colors as CSS-style RGB/RGBA rather than Qt's ARGB shorthand."""
    text = str(value or "").strip()
    if text.startswith("#") and len(text) == 9:
        try:
            return QColor(
                int(text[1:3], 16),
                int(text[3:5], 16),
                int(text[5:7], 16),
                int(text[7:9], 16),
            )
        except ValueError:
            pass
    color = QColor(text)
    return color if color.isValid() else QColor(fallback)


def _gradient_point(
    value: object,
    fallback: tuple[float, float],
) -> QPointF:
    value = value if isinstance(value, Mapping) else {}
    return QPointF(
        float(value.get("x", fallback[0])),
        float(value.get("y", fallback[1])),
    )


def _gradient_stops(value: object) -> list[tuple[float, QColor]]:
    if not isinstance(value, list):
        return []
    stops: list[tuple[float, QColor]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        try:
            position = max(0.0, min(1.0, float(row.get("position", 0.0))))
        except (TypeError, ValueError):
            position = 0.0
        stops.append((position, ui_color(row.get("color"), "#00000000")))
    return sorted(stops, key=lambda item: item[0])


def ui_fill_brush(
    style: Mapping[str, Any],
    rect: QRectF | None = None,
) -> QBrush:
    paints = style.get("fills")
    if isinstance(paints, list):
        visible = next(
            (
                row
                for row in paints
                if isinstance(row, Mapping) and row.get("visible", True)
            ),
            None,
        )
        if visible is not None:
            paint_type = str(visible.get("type") or "solid").casefold()
            opacity = max(
                0.0,
                min(1.0, float(visible.get("opacity", 1.0) or 0.0)),
            )
            if paint_type in {"linear", "radial"} and isinstance(
                visible.get("gradient"),
                Mapping,
            ):
                style = {
                    **dict(style),
                    "fill_gradient": visible["gradient"],
                }
            else:
                color = ui_color(visible.get("color"), "#00000000")
                color.setAlphaF(color.alphaF() * opacity)
                return QBrush(color)
    gradient_style = style.get("fill_gradient")
    if not isinstance(gradient_style, Mapping):
        return QBrush(ui_color(style.get("fill"), "#506884"))
    stops = _gradient_stops(gradient_style.get("stops"))
    if not stops:
        return QBrush(ui_color(style.get("fill"), "#506884"))
    start = _gradient_point(gradient_style.get("start"), (0.0, 0.5))
    end = _gradient_point(gradient_style.get("end"), (1.0, 0.5))
    gradient_type = str(gradient_style.get("type") or "linear").casefold()
    if gradient_type == "radial":
        radius = math.hypot(end.x() - start.x(), end.y() - start.y())
        gradient: QGradient = QRadialGradient(start, max(0.0001, radius))
    else:
        gradient = QLinearGradient(start, end)
    gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
    for position, color in stops:
        gradient.setColorAt(position, color)
    return QBrush(gradient)


def _svg_geometry_rows(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, str]] = []
    for row in value:
        if isinstance(row, Mapping):
            path = str(row.get("path") or "").strip()
            winding = str(row.get("winding_rule") or "nonzero").casefold()
        else:
            path = str(row).strip()
            winding = "nonzero"
        if path:
            result.append(
                {
                    "path": path,
                    "fill_rule": "evenodd" if winding == "evenodd" else "nonzero",
                }
            )
    return result


def has_ui_vector_geometry(content: object) -> bool:
    if not isinstance(content, Mapping):
        return False
    return bool(
        _svg_geometry_rows(content.get("vector_fill_geometry"))
        or _svg_geometry_rows(content.get("vector_stroke_geometry"))
        or _svg_geometry_rows(content.get("vector_paths"))
    )


def draw_ui_vector_paths(
    painter: QPainter,
    rect: QRectF,
    content: object,
    style: Mapping[str, Any],
) -> bool:
    """Render Figma SVG path geometry without substituting a bounding box."""
    if not isinstance(content, Mapping):
        return False
    fill_rows = _svg_geometry_rows(content.get("vector_fill_geometry"))
    stroke_rows = _svg_geometry_rows(content.get("vector_stroke_geometry"))
    if not fill_rows:
        fill_rows = _svg_geometry_rows(content.get("vector_paths"))
    if (
        not (fill_rows or stroke_rows)
        or rect.width() <= 0.0
        or rect.height() <= 0.0
    ):
        return False

    fill = ui_color(style.get("fill"), "#506884")
    stroke = ui_color(style.get("stroke"), "#00000000")
    stroke_width = max(0.0, float(style.get("stroke_width") or 0.0))
    gradient_style = style.get("fill_gradient")
    gradient_markup = ""
    fill_value = fill.name()
    fill_opacity = fill.alphaF()
    if isinstance(gradient_style, Mapping):
        stops = _gradient_stops(gradient_style.get("stops"))
        start = _gradient_point(gradient_style.get("start"), (0.0, 0.5))
        end = _gradient_point(gradient_style.get("end"), (1.0, 0.5))
        if stops:
            stop_markup = "".join(
                (
                    f'<stop offset="{position:.6f}" '
                    f'stop-color="{color.name()}" '
                    f'stop-opacity="{color.alphaF():.6f}"/>'
                )
                for position, color in stops
            )
            if str(gradient_style.get("type") or "").casefold() == "radial":
                radius = math.hypot(
                    end.x() - start.x(),
                    end.y() - start.y(),
                )
                gradient_markup = (
                    '<radialGradient id="uiFill" '
                    f'cx="{start.x():.6f}" cy="{start.y():.6f}" '
                    f'r="{max(0.0001, radius):.6f}">'
                    f"{stop_markup}</radialGradient>"
                )
            else:
                gradient_markup = (
                    '<linearGradient id="uiFill" '
                    f'x1="{start.x():.6f}" y1="{start.y():.6f}" '
                    f'x2="{end.x():.6f}" y2="{end.y():.6f}">'
                    f"{stop_markup}</linearGradient>"
                )
            fill_value = "url(#uiFill)"
            fill_opacity = 1.0
    fill_markup = "".join(
        (
            f'<path d="{html.escape(row["path"], quote=True)}" '
            f'fill="{fill_value}" fill-opacity="{fill_opacity:.6f}" '
            f'fill-rule="{row["fill_rule"]}" stroke="none"/>'
        )
        for row in fill_rows
    )
    cap = {
        "round": "round",
        "square": "square",
    }.get(str(style.get("stroke_cap") or "").casefold(), "butt")
    join = {
        "round": "round",
        "bevel": "bevel",
    }.get(str(style.get("stroke_join") or "").casefold(), "miter")
    dash_values = style.get("stroke_dash")
    dash_values = dash_values if isinstance(dash_values, list) else []
    dash = " ".join(str(max(0.0, float(value))) for value in dash_values)
    dash_attribute = (
        f' stroke-dasharray="{html.escape(dash, quote=True)}"' if dash else ""
    )
    stroke_markup = "".join(
        (
            f'<path d="{html.escape(row["path"], quote=True)}" fill="none" '
            f'stroke="{stroke.name()}" stroke-opacity="{stroke.alphaF():.6f}" '
            f'stroke-width="{stroke_width:.6f}" stroke-linecap="{cap}" '
            f'stroke-linejoin="{join}" '
            f'stroke-miterlimit="{max(0.0, float(style.get("stroke_miter_limit") or 4.0)):.6f}"'
            f"{dash_attribute}/>"
        )
        for row in stroke_rows
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{rect.width():.6f}" height="{rect.height():.6f}" '
        f'viewBox="0 0 {rect.width():.6f} {rect.height():.6f}">'
        f"<defs>{gradient_markup}</defs>"
        f"{fill_markup}{stroke_markup}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return False
    renderer.render(painter, rect)
    return True


def ui_font(base_font: QFont, style: Mapping[str, Any], scale: float = 1.0) -> QFont:
    font = QFont(base_font)
    pixel_size = max(1, int(round(float(style.get("font_size") or 14.0) * scale)))
    weight = max(100, min(900, int(style.get("font_weight") or 400)))
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(weight))
    family = str(style.get("font_family") or "").strip()
    if family:
        font.setFamily(family)
    return font


def ui_text_alignment(style: Mapping[str, Any]) -> str:
    alignment = str(style.get("text_align") or "left").strip().casefold()
    return alignment if alignment in {"left", "center", "right"} else "left"


def _shape_path(kind: str, rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    if kind == "ellipse":
        path.addEllipse(rect)
    else:
        path.addRoundedRect(rect, radius, radius)
    return path


def _style_shadow_effects(
    style: Mapping[str, Any],
    effect_type: str,
) -> list[Mapping[str, Any]]:
    effects = style.get("effects")
    if isinstance(effects, list):
        rows = [
            row
            for row in effects
            if isinstance(row, Mapping)
            and str(row.get("type") or "").casefold() == effect_type
        ]
        if rows:
            return rows
    shadow = style.get("shadow")
    if effect_type == "drop_shadow" and isinstance(shadow, Mapping):
        return [shadow]
    return []


def ui_blur_radius(
    style: Mapping[str, Any],
    effect_type: str,
    *,
    scale: float = 1.0,
) -> float:
    effects = style.get("effects")
    if not isinstance(effects, list):
        return 0.0
    radii = [
        max(0.0, float(row.get("radius") or 0.0))
        for row in effects
        if isinstance(row, Mapping)
        and str(row.get("type") or "").casefold() == effect_type
    ]
    return max(radii, default=0.0) * max(0.001, float(scale))


def blur_ui_image(image: QImage, radius: float) -> QImage:
    """Apply deterministic Gaussian blur while preserving straight RGBA."""
    if image.isNull() or radius <= 0.0:
        return image.copy()
    import cv2
    import numpy as np

    source = image.convertToFormat(QImage.Format.Format_RGBA8888)
    view = np.frombuffer(source.bits(), dtype=np.uint8).reshape(
        source.height(),
        source.bytesPerLine() // 4,
        4,
    )[:, : source.width(), :]
    blurred = cv2.GaussianBlur(
        view,
        (0, 0),
        sigmaX=max(0.01, float(radius)),
        sigmaY=max(0.01, float(radius)),
        borderType=cv2.BORDER_REPLICATE,
    )
    return QImage(
        blurred.data,
        source.width(),
        source.height(),
        int(blurred.strides[0]),
        QImage.Format.Format_RGBA8888,
    ).copy()


def draw_ui_background_blur(
    painter: QPainter,
    surface: QImage,
    rect: QRectF,
    kind: str,
    style: Mapping[str, Any],
    *,
    scale: float = 1.0,
) -> bool:
    radius = ui_blur_radius(
        style,
        "background_blur",
        scale=scale,
    )
    if radius <= 0.0 or surface.isNull() or kind in {"group", "line", "path"}:
        return False
    crop = rect.adjusted(
        -radius * 2.0,
        -radius * 2.0,
        radius * 2.0,
        radius * 2.0,
    ).toAlignedRect().intersected(surface.rect())
    if crop.isEmpty():
        return False
    blurred = blur_ui_image(surface.copy(crop), radius)
    shape_radius = max(0.0, float(style.get("radius") or 0.0) * scale)
    painter.save()
    painter.setClipPath(_shape_path(kind, rect, shape_radius))
    painter.drawImage(QPointF(float(crop.x()), float(crop.y())), blurred)
    painter.restore()
    return True


def _draw_outer_shadow(
    painter: QPainter,
    rect: QRectF,
    kind: str,
    style: Mapping[str, Any],
    shadow: Mapping[str, Any],
    *,
    scale: float,
) -> bool:
    color = ui_color(shadow.get("color"), "#00000066")
    if color.alpha() <= 0:
        return False
    offset_x = float(shadow.get("x") or 0.0) * scale
    offset_y = float(shadow.get("y") or 0.0) * scale
    blur = max(0.0, float(shadow.get("blur") or 0.0) * scale)
    spread = float(shadow.get("spread") or 0.0) * scale
    base_rect = rect.translated(offset_x, offset_y).adjusted(
        -spread,
        -spread,
        spread,
        spread,
    )
    radius = max(0.0, float(style.get("radius") or 0.0) * scale + spread)
    bands = max(1, min(10, int(math.ceil(blur / 3.0))))
    if kind == "line":
        width = max(
            1.0,
            float(style.get("stroke_width") or 2.0) * scale + spread * 2.0,
        )
        for index in range(bands, -1, -1):
            amount = blur * index / max(1, bands)
            band_color = QColor(color)
            fade = (1.0 - index / (bands + 1.0)) ** 2
            band_color.setAlpha(max(1, int(round(color.alpha() * fade))))
            painter.setPen(QPen(band_color, width + amount * 2.0))
            painter.drawLine(base_rect.topLeft(), base_rect.bottomRight())
    else:
        for index in range(bands, -1, -1):
            amount = blur * index / max(1, bands)
            band_color = QColor(color)
            fade = (1.0 - index / (bands + 1.0)) ** 2
            band_color.setAlpha(max(1, int(round(color.alpha() * fade))))
            painter.setBrush(band_color)
            expanded = base_rect.adjusted(-amount, -amount, amount, amount)
            painter.drawPath(_shape_path(kind, expanded, radius + amount))
    return True


def draw_ui_object_shadow(
    painter: QPainter,
    rect: QRectF,
    kind: str,
    style: Mapping[str, Any],
    *,
    scale: float = 1.0,
) -> bool:
    shadows = _style_shadow_effects(style, "drop_shadow")
    if not shadows or kind in {"group", "text"}:
        return False
    scale = max(0.001, float(scale))
    painter.save()
    painter.setPen(Qt.PenStyle.NoPen)
    rendered = False
    for shadow in shadows:
        rendered = (
            _draw_outer_shadow(
                painter,
                rect,
                kind,
                style,
                shadow,
                scale=scale,
            )
            or rendered
        )
    painter.restore()
    return rendered


def draw_ui_object_inner_shadows(
    painter: QPainter,
    rect: QRectF,
    kind: str,
    style: Mapping[str, Any],
    *,
    scale: float = 1.0,
) -> bool:
    shadows = _style_shadow_effects(style, "inner_shadow")
    if not shadows or kind in {"group", "text", "line", "path"}:
        return False
    scale = max(0.001, float(scale))
    radius = max(0.0, float(style.get("radius") or 0.0) * scale)
    clip_path = _shape_path(kind, rect, radius)
    painter.save()
    painter.setClipPath(clip_path)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    rendered = False
    for shadow in shadows:
        color = ui_color(shadow.get("color"), "#00000066")
        if color.alpha() <= 0:
            continue
        offset_x = float(shadow.get("x") or 0.0) * scale
        offset_y = float(shadow.get("y") or 0.0) * scale
        blur = max(0.0, float(shadow.get("blur") or 0.0) * scale)
        spread = float(shadow.get("spread") or 0.0) * scale
        bands = max(1, min(10, int(math.ceil(blur / 3.0))))
        shifted = rect.translated(offset_x, offset_y).adjusted(
            spread,
            spread,
            -spread,
            -spread,
        )
        for index in range(bands, -1, -1):
            amount = blur * (index + 1) / max(1, bands)
            band_color = QColor(color)
            fade = (1.0 - index / (bands + 1.0)) ** 2
            band_color.setAlpha(max(1, int(round(color.alpha() * fade))))
            painter.setPen(QPen(band_color, max(1.0, amount * 2.0)))
            painter.drawPath(_shape_path(kind, shifted, radius))
        rendered = True
    painter.restore()
    return rendered


def _layout_text(
    text: str,
    font: QFont,
    rect: QRectF,
    alignment: str,
    line_height: float,
    text_ranges: object = None,
) -> tuple[QTextLayout, list[Any], float]:
    normalized_text = (
        text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\u2028")
    )
    layout = QTextLayout(normalized_text, font)
    formats: list[QTextLayout.FormatRange] = []
    if isinstance(text_ranges, list):
        for row in text_ranges:
            if not isinstance(row, Mapping):
                continue
            start = max(0, int(row.get("start") or 0))
            end = max(start, int(row.get("end") or start))
            values = row.get("style")
            values = values if isinstance(values, Mapping) else {}
            if end <= start or not values:
                continue
            char_format = QTextCharFormat()
            if values.get("font_family"):
                char_format.setFontFamily(str(values["font_family"]))
            if values.get("font_size") is not None:
                char_format.setFontPixelSize(
                    max(1.0, float(values["font_size"]))
                )
            if values.get("font_weight") is not None:
                char_format.setFontWeight(int(values["font_weight"]))
            char_format.setFontItalic(bool(values.get("italic", False)))
            char_format.setFontUnderline(bool(values.get("underline", False)))
            if values.get("color"):
                char_format.setForeground(
                    ui_color(values["color"], "#F2F5F9")
                )
            format_range = QTextLayout.FormatRange()
            format_range.start = start
            format_range.length = end - start
            format_range.format = char_format
            formats.append(format_range)
    if formats:
        layout.setFormats(formats)
    option = QTextOption()
    option.setWrapMode(QTextOption.WrapMode.WordWrap)
    layout.setTextOption(option)
    layout.beginLayout()
    lines = []
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1.0, rect.width()))
        lines.append(line)

    spacing = max(0.5, min(4.0, float(line_height)))
    heights = [float(line.height()) for line in lines]
    total_height = (
        heights[-1] + sum(height * spacing for height in heights[:-1])
        if heights
        else 0.0
    )
    y = rect.top() + max(0.0, (rect.height() - total_height) * 0.5)
    for line, height in zip(lines, heights):
        if alignment == "right":
            x = rect.right() - float(line.naturalTextWidth())
        elif alignment == "center":
            x = rect.center().x() - float(line.naturalTextWidth()) * 0.5
        else:
            x = rect.left()
        line.setPosition(QPointF(x, y))
        y += height * spacing
    layout.endLayout()
    return layout, lines, total_height


def draw_ui_text_block(
    painter: QPainter,
    rect: QRectF,
    text: str,
    style: Mapping[str, Any],
    base_font: QFont,
    *,
    scale: float = 1.0,
    text_ranges: object = None,
) -> dict[str, Any]:
    font = ui_font(base_font, style, scale)
    alignment = ui_text_alignment(style)
    line_height = max(0.5, min(4.0, float(style.get("line_height") or 1.2)))
    padding = max(0.0, float(style.get("text_padding") or 6.0) * scale)
    text_rect = rect.adjusted(padding, 0.0, -padding, 0.0)
    layout, lines, total_height = _layout_text(
        str(text),
        font,
        text_rect,
        alignment,
        line_height,
        text_ranges,
    )

    painter.save()
    painter.setClipRect(rect)
    shadows = _style_shadow_effects(style, "drop_shadow")
    if not shadows:
        shadow = style.get("text_shadow")
        shadows = [shadow] if isinstance(shadow, Mapping) else []
    for shadow in shadows:
        shadow_color = ui_color(shadow.get("color"), "#00000066")
        if shadow_color.alpha() > 0:
            offset = QPointF(
                float(shadow.get("x") or 0.0) * scale,
                float(shadow.get("y") or 0.0) * scale,
            )
            blur = max(0.0, float(shadow.get("blur") or 0.0) * scale)
            bands = min(6, int(math.ceil(blur / 2.5)))
            for index in range(bands, 0, -1):
                radius = blur * index / max(1, bands)
                band_color = QColor(shadow_color)
                fade = (1.0 - index / (bands + 1.0)) ** 2
                band_color.setAlpha(
                    max(1, int(round(shadow_color.alpha() * fade * 0.35)))
                )
                painter.setPen(band_color)
                for step in range(8):
                    angle = math.tau * step / 8.0
                    layout.draw(
                        painter,
                        offset
                        + QPointF(
                            math.cos(angle) * radius,
                            math.sin(angle) * radius,
                        ),
                    )
            painter.setPen(shadow_color)
            layout.draw(
                painter,
                offset,
            )
    painter.setPen(ui_color(style.get("text_color"), "#F2F5F9"))
    layout.draw(painter, QPointF())
    painter.restore()
    return {
        "alignment": alignment,
        "font_pixel_size": font.pixelSize(),
        "font_weight": int(font.weight()),
        "line_count": len(lines),
        "line_height": line_height,
        "layout_height": total_height,
    }


__all__ = [
    "draw_ui_object_inner_shadows",
    "draw_ui_object_shadow",
    "draw_ui_text_block",
    "ui_fill_brush",
    "ui_color",
    "ui_font",
    "ui_text_alignment",
]
