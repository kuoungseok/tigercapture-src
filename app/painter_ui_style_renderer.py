"""Deterministic style rendering helpers for Painter UI objects."""
from __future__ import annotations

import html
import math
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QGradient,
    QImage,
    QImageReader,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QTransform,
    QTextCharFormat,
    QTextLayout,
    QTextOption,
)
from PySide6.QtSvg import QSvgRenderer


def ui_composition_mode(value: object):
    """Map Painter/Figma blend names to the closest deterministic Qt mode."""
    normalized = str(value or "normal").strip().casefold().replace("-", "_")
    return {
        "multiply": QPainter.CompositionMode.CompositionMode_Multiply,
        "screen": QPainter.CompositionMode.CompositionMode_Screen,
        "overlay": QPainter.CompositionMode.CompositionMode_Overlay,
        "darken": QPainter.CompositionMode.CompositionMode_Darken,
        "lighten": QPainter.CompositionMode.CompositionMode_Lighten,
        "color_dodge": QPainter.CompositionMode.CompositionMode_ColorDodge,
        "color_burn": QPainter.CompositionMode.CompositionMode_ColorBurn,
        "hard_light": QPainter.CompositionMode.CompositionMode_HardLight,
        "soft_light": QPainter.CompositionMode.CompositionMode_SoftLight,
        "difference": QPainter.CompositionMode.CompositionMode_Difference,
        "exclusion": QPainter.CompositionMode.CompositionMode_Exclusion,
        "linear_dodge": QPainter.CompositionMode.CompositionMode_Plus,
    }.get(
        normalized,
        QPainter.CompositionMode.CompositionMode_SourceOver,
    )


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


def _pattern_image(value: object) -> QImage:
    row = value if isinstance(value, Mapping) else {}
    size = max(4, min(128, int(round(float(row.get("scale") or 12.0)))))
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    background = ui_color(row.get("background"), "#FFFFFFFF")
    foreground = ui_color(row.get("foreground"), "#C8D2E0FF")
    image.fill(background)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    kind = str(row.get("kind") or "dots").casefold()
    if kind == "checker":
        half = max(1, size // 2)
        painter.fillRect(0, 0, half, half, foreground)
        painter.fillRect(half, half, size - half, size - half, foreground)
    elif kind == "stripes":
        painter.setPen(QPen(foreground, max(1.0, size * 0.24)))
        painter.drawLine(-size // 2, size, size // 2, 0)
        painter.drawLine(size // 2, size, size + size // 2, 0)
    elif kind == "grid":
        painter.setPen(QPen(foreground, max(1.0, size * 0.08)))
        painter.drawLine(0, 0, size, 0)
        painter.drawLine(0, 0, 0, size)
    else:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(foreground)
        radius = max(1.0, size * 0.15)
        painter.drawEllipse(QPointF(size * 0.5, size * 0.5), radius, radius)
    painter.end()
    return image


@lru_cache(maxsize=48)
def _load_media_frame(path_text: str, frame_time_ms: int = 0) -> QImage:
    path = Path(str(path_text or "")).expanduser()
    if not path.is_file():
        return QImage()
    suffix = path.suffix.casefold()
    if suffix in {".mp4", ".mov", ".webm", ".mkv", ".avi"}:
        try:
            import cv2

            capture = cv2.VideoCapture(str(path))
            if frame_time_ms > 0:
                capture.set(cv2.CAP_PROP_POS_MSEC, float(frame_time_ms))
            ok, frame = capture.read()
            capture.release()
            if ok and frame is not None:
                rgba = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                return QImage(
                    rgba.data,
                    int(rgba.shape[1]),
                    int(rgba.shape[0]),
                    int(rgba.strides[0]),
                    QImage.Format.Format_RGBA8888,
                ).copy()
        except Exception:
            return QImage()
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    return reader.read()


def _media_brush(paint: Mapping[str, Any], rect: QRectF) -> QBrush:
    source = str(paint.get("source_path") or paint.get("poster_path") or "")
    image = _load_media_frame(source, int(float(paint.get("frame_time_ms") or 0.0)))
    if image.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return QBrush(_pattern_image({"kind": "checker", "scale": 12}))
    mode = str(paint.get("fit") or "fill").casefold()
    if mode == "tile":
        brush = QBrush(image)
        brush.setTransform(QTransform.fromTranslate(rect.left(), rect.top()))
        return brush
    target_w = max(1, min(4096, int(round(rect.width()))))
    target_h = max(1, min(4096, int(round(rect.height()))))
    target = QImage(target_w, target_h, QImage.Format.Format_ARGB32_Premultiplied)
    target.fill(Qt.GlobalColor.transparent)
    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    if mode == "stretch":
        destination = QRectF(0, 0, target_w, target_h)
    else:
        keep = Qt.AspectRatioMode.KeepAspectRatio
        scaled = image.size().scaled(target_w, target_h, keep)
        if mode == "fill" and (scaled.width() < target_w or scaled.height() < target_h):
            scaled = image.size().scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatioByExpanding)
        destination = QRectF(
            (target_w - scaled.width()) * 0.5,
            (target_h - scaled.height()) * 0.5,
            scaled.width(),
            scaled.height(),
        )
    painter.drawImage(destination, image)
    painter.end()
    brush = QBrush(target)
    brush.setTransform(QTransform.fromTranslate(rect.left(), rect.top()))
    return brush


def _paint_brush(paint: Mapping[str, Any], rect: QRectF | None) -> QBrush:
    paint_type = str(paint.get("type") or "solid").casefold()
    opacity = max(0.0, min(1.0, float(paint.get("opacity", 1.0) or 0.0)))
    if paint_type == "pattern":
        brush = QBrush(_pattern_image(paint.get("pattern")))
        if rect is not None:
            brush.setTransform(QTransform.fromTranslate(rect.left(), rect.top()))
        return brush
    if paint_type in {"image", "video"} and rect is not None:
        return _media_brush(paint, rect)
    if paint_type in {"linear", "radial"} and isinstance(paint.get("gradient"), Mapping):
        gradient_style = paint["gradient"]
        stops = _gradient_stops(gradient_style.get("stops"))
        start = _gradient_point(gradient_style.get("start"), (0.0, 0.5))
        end = _gradient_point(gradient_style.get("end"), (1.0, 0.5))
        if paint_type == "radial":
            radius = math.hypot(end.x() - start.x(), end.y() - start.y())
            gradient: QGradient = QRadialGradient(start, max(0.0001, radius))
        else:
            gradient = QLinearGradient(start, end)
        gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
        for position, color in stops:
            color.setAlphaF(color.alphaF() * opacity)
            gradient.setColorAt(position, color)
        return QBrush(gradient)
    color = ui_color(paint.get("color"), "#00000000")
    color.setAlphaF(color.alphaF() * opacity)
    return QBrush(color)


def ui_fill_brush(
    style: Mapping[str, Any],
    rect: QRectF | None = None,
) -> QBrush:
    paints = style.get("fills")
    if isinstance(paints, list):
        visible = [
            row for row in paints
            if isinstance(row, Mapping) and row.get("visible", True)
        ]
        if visible:
            if len(visible) == 1 or rect is None:
                return _paint_brush(visible[0], rect)
            width = max(1, min(4096, int(round(rect.width()))))
            height = max(1, min(4096, int(round(rect.height()))))
            surface = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
            surface.fill(Qt.GlobalColor.transparent)
            painter = QPainter(surface)
            local_rect = QRectF(0, 0, width, height)
            for paint in reversed(visible):
                painter.setCompositionMode(
                    ui_composition_mode(paint.get("blend_mode"))
                )
                painter.fillRect(local_rect, _paint_brush(paint, local_rect))
            painter.end()
            brush = QBrush(surface)
            brush.setTransform(QTransform.fromTranslate(rect.left(), rect.top()))
            return brush
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
        or str(content.get("vector_render_path") or "").strip()
    )


def has_ui_figma_expanded_stroke_geometry(content: object) -> bool:
    """Return whether imported Figma strokeGeometry is an exact outline."""

    if not isinstance(content, Mapping):
        return False
    metadata = content.get("figma_stroke_geometry")
    return (
        isinstance(metadata, Mapping)
        and str(metadata.get("representation") or "").casefold()
        == "expanded_outline"
        and bool(_svg_geometry_rows(content.get("vector_stroke_geometry")))
    )


@lru_cache(maxsize=64)
def _read_ui_vector_svg_asset(
    path_text: str,
    modified_ns: int,
    size: int,
) -> bytes:
    del modified_ns
    if size <= 0 or size > 16 * 1024 * 1024:
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError:
        return b""


def _draw_ui_vector_svg_asset(
    painter: QPainter,
    rect: QRectF,
    path_text: object,
) -> bool:
    path = Path(str(path_text or "")).expanduser()
    try:
        stat = path.stat()
    except OSError:
        return False
    if not path.is_file() or path.suffix.casefold() != ".svg":
        return False
    data = _read_ui_vector_svg_asset(
        str(path.resolve()),
        int(stat.st_mtime_ns),
        int(stat.st_size),
    )
    if not data:
        return False
    renderer = QSvgRenderer(QByteArray(data))
    if not renderer.isValid():
        return False
    renderer.render(painter, rect)
    return True


def draw_ui_vector_paths(
    painter: QPainter,
    rect: QRectF,
    content: object,
    style: Mapping[str, Any],
    *,
    scale: float = 1.0,
) -> bool:
    """Render Figma SVG path geometry without substituting a bounding box."""
    if not isinstance(content, Mapping):
        return False
    if _draw_ui_vector_svg_asset(
        painter,
        rect,
        content.get("vector_render_path"),
    ):
        return True
    if isinstance(content.get("vector_network"), Mapping):
        from app.painter_ui_vector_network import vector_network_to_qpath

        path = vector_network_to_qpath(content["vector_network"], rect)
        if path.isEmpty():
            return False
        fill = ui_color(style.get("fill"), "#506884")
        stroke = ui_color(style.get("stroke"), "#00000000")
        # ``path`` is already in screen space (``rect`` carries the current
        # view scale), but this stroke width is the raw authored value - every
        # other stroke in this file's caller multiplies by the view scale, so
        # skipping it here only matched at 100% zoom and looked too thin/thick
        # everywhere else.
        stroke_width = max(0.0, float(style.get("stroke_width") or 0.0)) * max(
            0.0, float(scale)
        )
        painter.save()
        if fill.alpha() > 0:
            painter.fillPath(path, ui_fill_brush(style))
        if stroke.alpha() > 0 and stroke_width > 0.0:
            pen = QPen(stroke, stroke_width)
            pen.setCapStyle(
                {
                    "round": Qt.PenCapStyle.RoundCap,
                    "square": Qt.PenCapStyle.SquareCap,
                }.get(
                    str(style.get("stroke_cap") or "").casefold(),
                    Qt.PenCapStyle.FlatCap,
                )
            )
            pen.setJoinStyle(
                {
                    "round": Qt.PenJoinStyle.RoundJoin,
                    "bevel": Qt.PenJoinStyle.BevelJoin,
                }.get(
                    str(style.get("stroke_join") or "").casefold(),
                    Qt.PenJoinStyle.MiterJoin,
                )
            )
            dash_values = style.get("stroke_dash")
            if isinstance(dash_values, list):
                pen.setDashPattern(
                    [max(0.0, float(value)) for value in dash_values]
                )
            painter.strokePath(path, pen)
        painter.restore()
        return True
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
    stroke_geometry = content.get("figma_stroke_geometry")
    expanded_stroke_geometry = (
        isinstance(stroke_geometry, Mapping)
        and str(stroke_geometry.get("representation") or "").casefold()
        == "expanded_outline"
    )
    source_viewport = (
        stroke_geometry.get("viewport")
        if isinstance(stroke_geometry, Mapping)
        and isinstance(stroke_geometry.get("viewport"), Mapping)
        else {}
    )
    # ``vector_fill_geometry``/``vector_paths`` are authored-document-space
    # coordinates (e.g. a 386x335 hexagon), not screen pixels. ``rect`` is
    # already view-scaled, so at 100% zoom the two happen to match and this
    # was invisible - but a pane fit to a much smaller/larger zoom (like the
    # UMG Widget View preview, fit to its own panel rather than 1:1) declared
    # a viewBox of the SCREEN rect while the path data still spans the full
    # document size, inflating every boolean-result shape by 1/scale.
    fallback_width = rect.width() / max(0.0001, float(scale))
    fallback_height = rect.height() / max(0.0001, float(scale))
    source_width = max(
        0.0001,
        float(source_viewport.get("width", fallback_width) or fallback_width),
    )
    source_height = max(
        0.0001,
        float(source_viewport.get("height", fallback_height) or fallback_height),
    )
    expanded_stroke_rows = (
        [row for row in stroke_rows if "z" in row["path"].casefold()]
        if expanded_stroke_geometry
        else []
    )
    centerline_stroke_rows = (
        [row for row in stroke_rows if row not in expanded_stroke_rows]
        if expanded_stroke_geometry
        else stroke_rows
    )
    # Figma REST strokeGeometry is normally an expanded outline, not a
    # centerline to stroke again. Filling its closed subpaths preserves
    # individual edge weights, inside/outside alignment, joins, caps, and
    # dashes exactly. Keep an open-path fallback for older/synthetic payloads.
    expanded_stroke_markup = "".join(
        (
            f'<path d="{html.escape(row["path"], quote=True)}" '
            f'fill="{stroke.name()}" fill-opacity="{stroke.alphaF():.6f}" '
            f'fill-rule="{row["fill_rule"]}" stroke="none"/>'
        )
        for row in expanded_stroke_rows
    )
    centerline_stroke_markup = "".join(
        (
            f'<path d="{html.escape(row["path"], quote=True)}" fill="none" '
            f'stroke="{stroke.name()}" stroke-opacity="{stroke.alphaF():.6f}" '
            f'stroke-width="{stroke_width:.6f}" stroke-linecap="{cap}" '
            f'stroke-linejoin="{join}" '
            f'stroke-miterlimit="{max(0.0, float(style.get("stroke_miter_limit") or 4.0)):.6f}"'
            f"{dash_attribute}/>"
        )
        for row in centerline_stroke_rows
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'overflow="visible" '
        f'width="{source_width:.6f}" height="{source_height:.6f}" '
        f'viewBox="0 0 {source_width:.6f} {source_height:.6f}">'
        f"<defs>{gradient_markup}</defs>"
        f"{fill_markup}{centerline_stroke_markup}</svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        return False
    renderer.render(painter, rect)
    if expanded_stroke_markup:
        individual_weights = style.get("individual_stroke_weights")
        stroke_extent = max(
            [stroke_width]
            + (
                [
                    max(0.0, float(value or 0.0))
                    for value in individual_weights.values()
                ]
                if isinstance(individual_weights, Mapping)
                else []
            )
        )
        logical_scale = max(
            rect.width() / source_width,
            rect.height() / source_height,
        )
        padding = max(2.0, math.ceil(stroke_extent * logical_scale + 2.0))
        logical_width = max(1.0, rect.width() + padding * 2.0)
        logical_height = max(1.0, rect.height() + padding * 2.0)
        raster_scale = min(
            1.0,
            4096.0 / logical_width,
            4096.0 / logical_height,
            math.sqrt((16.0 * 1024.0 * 1024.0) / (logical_width * logical_height)),
        )
        surface_width = max(1, int(math.ceil(logical_width * raster_scale)))
        surface_height = max(1, int(math.ceil(logical_height * raster_scale)))
        target = QRectF(
            padding * raster_scale,
            padding * raster_scale,
            rect.width() * raster_scale,
            rect.height() * raster_scale,
        )
        stroke_surface = QImage(
            surface_width,
            surface_height,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        stroke_surface.fill(Qt.GlobalColor.transparent)
        stroke_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" overflow="visible" '
            f'width="{source_width:.6f}" height="{source_height:.6f}" '
            f'viewBox="0 0 {source_width:.6f} {source_height:.6f}">'
            f"{expanded_stroke_markup}</svg>"
        )
        stroke_renderer = QSvgRenderer(
            QByteArray(stroke_svg.encode("utf-8"))
        )
        stroke_painter = QPainter(stroke_surface)
        stroke_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        stroke_renderer.render(stroke_painter, target)
        stroke_painter.end()

        stroke_align = str(style.get("stroke_align") or "center").casefold()
        if fill_rows and stroke_align in {"inside", "outside"}:
            mask_markup = "".join(
                (
                    f'<path d="{html.escape(row["path"], quote=True)}" '
                    f'fill="#FFFFFF" fill-rule="{row["fill_rule"]}"/>'
                )
                for row in fill_rows
            )
            mask_svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" overflow="visible" '
                f'width="{source_width:.6f}" height="{source_height:.6f}" '
                f'viewBox="0 0 {source_width:.6f} {source_height:.6f}">'
                f"{mask_markup}</svg>"
            )
            mask_surface = QImage(
                surface_width,
                surface_height,
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            mask_surface.fill(Qt.GlobalColor.transparent)
            mask_painter = QPainter(mask_surface)
            mask_painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            QSvgRenderer(QByteArray(mask_svg.encode("utf-8"))).render(
                mask_painter,
                target,
            )
            mask_painter.end()
            compositor = QPainter(stroke_surface)
            compositor.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_DestinationIn
                if stroke_align == "inside"
                else QPainter.CompositionMode.CompositionMode_DestinationOut
            )
            compositor.drawImage(0, 0, mask_surface)
            compositor.end()
        painter.drawImage(
            QRectF(
                rect.left() - padding,
                rect.top() - padding,
                logical_width,
                logical_height,
            ),
            stroke_surface,
        )
    return True


def ui_font(base_font: QFont, style: Mapping[str, Any], scale: float = 1.0) -> QFont:
    from app.font_fallback import registered_design_font_family
    from app.painter_ui_typography import apply_ui_font_axes

    font = QFont(base_font)
    pixel_size = max(1, int(round(float(style.get("font_size") or 14.0) * scale)))
    weight = max(100, min(900, int(style.get("font_weight") or 400)))
    font.setPixelSize(pixel_size)
    font.setWeight(QFont.Weight(weight))
    family = str(style.get("font_family") or "").strip()
    if family:
        font.setFamily(registered_design_font_family(family))
    apply_ui_font_axes(font, style.get("font_axes"))
    return font


def ui_text_alignment(style: Mapping[str, Any]) -> str:
    alignment = str(style.get("text_align") or "left").strip().casefold()
    return alignment if alignment in {"left", "center", "right"} else "left"


def ui_text_vertical_alignment(style: Mapping[str, Any]) -> str:
    alignment = str(
        style.get("text_vertical_align")
        or style.get("vertical_align")
        or "center"
    ).strip().casefold()
    return alignment if alignment in {"top", "center", "bottom"} else "center"


def _ui_line_height(style: Mapping[str, Any]) -> tuple[float, str]:
    try:
        value = float(style.get("line_height") or 0.0)
    except (TypeError, ValueError):
        value = 0.0
    unit = str(style.get("line_height_unit") or "").strip().casefold()
    if unit in {"px", "pixel", "pixels"} or value > 4.0:
        return max(0.0, value), "px"
    return max(0.5, min(4.0, value or 1.2)), "ratio"


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
        and str(
            row.get("blur_type", row.get("blurType")) or "normal"
        ).casefold()
        != "progressive"
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
        painter.setCompositionMode(
            ui_composition_mode(shadow.get("blend_mode"))
        )
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
        painter.setCompositionMode(
            ui_composition_mode(shadow.get("blend_mode"))
        )
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
    line_height_unit: str,
    wrap_mode: QTextOption.WrapMode,
    vertical_alignment: str,
    text_ranges: object = None,
    text_range_scale: float = 1.0,
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
            # QTextCharFormat has no setFontPixelSize in PySide6.  Build a
            # QFont from the already-resolved base font so Figma character
            # ranges retain pixel sizing without converting through DPI-
            # dependent point sizes.
            range_font = QFont(font)
            if values.get("font_family"):
                from app.font_fallback import registered_design_font_family

                range_font.setFamily(
                    registered_design_font_family(str(values["font_family"]))
                )
            if values.get("font_size") is not None:
                range_font.setPixelSize(
                    max(
                        1,
                        int(
                            round(
                                float(values["font_size"])
                                * max(0.001, float(text_range_scale))
                            )
                        ),
                    )
                )
            if values.get("font_weight") is not None:
                range_font.setWeight(
                    QFont.Weight(
                        max(100, min(900, int(values["font_weight"])))
                    )
                )
            range_font.setItalic(bool(values.get("italic", False)))
            range_font.setUnderline(bool(values.get("underline", False)))
            char_format = QTextCharFormat()
            char_format.setFont(range_font)
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
    option.setWrapMode(wrap_mode)
    layout.setTextOption(option)
    layout.beginLayout()
    lines = []
    while True:
        line = layout.createLine()
        if not line.isValid():
            break
        line.setLineWidth(max(1.0, rect.width()))
        lines.append(line)

    heights = [float(line.height()) for line in lines]
    if str(line_height_unit) == "px":
        line_advances = [max(1.0, float(line_height))] * max(
            0, len(heights) - 1
        )
    else:
        spacing = max(0.5, min(4.0, float(line_height)))
        line_advances = [height * spacing for height in heights[:-1]]
    total_height = (
        heights[-1] + sum(line_advances) if heights else 0.0
    )
    if vertical_alignment == "top":
        y = rect.top()
    elif vertical_alignment == "bottom":
        y = rect.bottom() - total_height
    else:
        y = rect.top() + (rect.height() - total_height) * 0.5
    y = max(rect.top(), y)
    for index, (line, _height) in enumerate(zip(lines, heights)):
        if alignment == "right":
            x = rect.right() - float(line.naturalTextWidth())
        elif alignment == "center":
            x = rect.center().x() - float(line.naturalTextWidth()) * 0.5
        else:
            x = rect.left()
        line.setPosition(QPointF(x, y))
        if index < len(line_advances):
            y += line_advances[index]
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
    text_resize: str = "",
) -> dict[str, Any]:
    font = ui_font(base_font, style, scale)
    alignment = ui_text_alignment(style)
    vertical_alignment = ui_text_vertical_alignment(style)
    line_height, line_height_unit = _ui_line_height(style)
    resize_mode = str(text_resize or "").strip().casefold().replace("-", "_")
    if "text_padding" in style and style.get("text_padding") is not None:
        padding_value = float(style.get("text_padding") or 0.0)
    else:
        padding_value = 0.0 if resize_mode == "auto_width" else 6.0
    padding = max(0.0, padding_value * scale)
    wrap_mode = (
        QTextOption.WrapMode.NoWrap
        if resize_mode == "auto_width"
        else QTextOption.WrapMode.WordWrap
    )
    text_rect = rect.adjusted(padding, 0.0, -padding, 0.0)
    layout, lines, total_height = _layout_text(
        str(text),
        font,
        text_rect,
        alignment,
        line_height * scale if line_height_unit == "px" else line_height,
        line_height_unit,
        wrap_mode,
        vertical_alignment,
        text_ranges,
        scale,
    )

    painter.save()
    if resize_mode != "auto_width":
        painter.setClipRect(rect)
    shadows = _style_shadow_effects(style, "drop_shadow")
    if not shadows:
        shadow = style.get("text_shadow")
        shadows = [shadow] if isinstance(shadow, Mapping) else []
    for shadow in shadows:
        shadow_color = ui_color(shadow.get("color"), "#00000066")
        if shadow_color.alpha() > 0:
            painter.setCompositionMode(
                ui_composition_mode(shadow.get("blend_mode"))
            )
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
        "line_height_unit": line_height_unit,
        "layout_height": total_height,
        "effective_padding": padding_value,
        "wrap_mode": (
            "no_wrap"
            if wrap_mode == QTextOption.WrapMode.NoWrap
            else "word_wrap"
        ),
        "vertical_alignment": vertical_alignment,
    }


__all__ = [
    "draw_ui_object_inner_shadows",
    "draw_ui_object_shadow",
    "draw_ui_text_block",
    "draw_ui_vector_paths",
    "has_ui_figma_expanded_stroke_geometry",
    "has_ui_vector_geometry",
    "ui_fill_brush",
    "ui_composition_mode",
    "ui_color",
    "ui_font",
    "ui_text_alignment",
    "ui_text_vertical_alignment",
]
