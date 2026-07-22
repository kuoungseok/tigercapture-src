from __future__ import annotations

from collections import OrderedDict
from math import atan2, degrees, hypot
from typing import Any, Mapping

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen

from app.motion_designer.schema import MotionLayer
from app.motion_designer.source_frame import transparent_image
from app.motion_designer.typography_layout import (
    build_typography_layout,
    line_origin_x,
    source_indices as _source_indices,
    typography_font as _font,
    visual_glyphs,
    wrap_text as _wrap_text,
)
from app.motion_designer.typography_motion import evaluate_glyph_motion
from app.motion_designer.vector_shapes import (
    VectorPath, evaluate_source_param, flatten_path,
)
from app.typo_animations import GlyphTransform


class TypographyGlyphCache:
    def __init__(self, capacity: int = 2048) -> None:
        self.capacity = max(64, int(capacity))
        self._items: OrderedDict[tuple[object, ...], QPainterPath] = OrderedDict()

    def path(self, font: QFont, grapheme: str) -> QPainterPath:
        axes = tuple(sorted(
            (tag.toString(), font.variableAxisValue(tag)) for tag in font.variableAxisTags()
        ))
        key = (font.toString(), axes, grapheme)
        cached = self._items.get(key)
        if cached is not None:
            self._items.move_to_end(key)
            return QPainterPath(cached)
        path = QPainterPath()
        path.addText(0.0, QFontMetricsF(font).ascent(), font, grapheme)
        self._items[key] = QPainterPath(path)
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)
        return path

    def clear(self) -> None:
        self._items.clear()


TYPOGRAPHY_GLYPH_CACHE = TypographyGlyphCache()


def _paint_glyph(
    painter: QPainter, path: QPainterPath, origin: QPointF, size: tuple[float, float],
    motion: GlyphTransform, fill: QColor, stroke: QColor, stroke_width: float,
    shadow: QColor, shadow_offset: tuple[float, float],
    *, angle: float = 0.0, baseline_path: bool = False,
) -> None:
    painter.save()
    painter.setOpacity(max(0.0, min(1.0, motion.opacity)))
    pivot_x = 0.0 if baseline_path else size[0] * motion.pivot_x
    pivot_y = -size[1] * .5 if baseline_path else size[1] * motion.pivot_y
    painter.translate(origin.x() + pivot_x + motion.offset_x, origin.y() + pivot_y + motion.offset_y)
    painter.rotate(angle + motion.rotation_deg)
    painter.scale(motion.scale_x, motion.scale_y)
    painter.translate(-pivot_x, -pivot_y)
    if shadow.isValid() and shadow.alpha() > 0:
        shifted = QPainterPath(path)
        shifted.translate(shadow_offset[0], shadow_offset[1])
        painter.fillPath(shifted, shadow)
    if stroke_width > 0 and stroke.isValid():
        painter.strokePath(path, QPen(stroke, stroke_width * 2.0))
    color = QColor(motion.color_override) if motion.color_override else fill
    painter.fillPath(path, color if color.isValid() else fill)
    painter.restore()


def _path_samples(path_data: Mapping[str, Any]) -> list[tuple[float, float]]:
    try:
        path = VectorPath.from_dict(path_data)
    except (TypeError, ValueError):
        return []
    return flatten_path(path, tolerance=.45)


def _point_on_polyline(points: list[tuple[float, float]], distance: float) -> tuple[QPointF, float]:
    if len(points) < 2:
        return QPointF(), 0.0
    remaining = max(0.0, float(distance))
    for start, end in zip(points, points[1:]):
        length = hypot(end[0] - start[0], end[1] - start[1])
        if remaining <= length or length <= 1e-9:
            amount = 0.0 if length <= 1e-9 else remaining / length
            point = QPointF(start[0] + (end[0] - start[0]) * amount,
                            start[1] + (end[1] - start[1]) * amount)
            return point, degrees(atan2(end[1] - start[1], end[0] - start[0]))
        remaining -= length
    start, end = points[-2], points[-1]
    return QPointF(*end), degrees(atan2(end[1] - start[1], end[0] - start[0]))


def render_typography(layer: MotionLayer, time_ms: float = 0.0):
    params = layer.source.params
    layout = build_typography_layout(layer, time_ms)
    text = layout.text
    metrics = layout.metrics
    padding = layout.padding
    line_height = layout.line_height
    width = layout.width
    height = layout.height
    image = transparent_image(layout.width, layout.height)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.TextAntialiasing)
    background = QColor(str(evaluate_source_param(params, "background_color", time_ms, "transparent")))
    if background.isValid() and background.alpha() > 0:
        painter.setPen(QPen(Qt.NoPen))
        painter.setBrush(background)
        radius = float(evaluate_source_param(params, "background_radius", time_ms, 0.0))
        painter.drawRoundedRect(QRectF(0, 0, width, height), radius, radius)

    fill = QColor(str(evaluate_source_param(params, "fill", time_ms,
                                             evaluate_source_param(params, "color", time_ms, "#ffffff"))))
    stroke = QColor(str(evaluate_source_param(params, "stroke", time_ms,
                                               evaluate_source_param(params, "outline_color", time_ms, "#000000"))))
    stroke_width = max(0.0, float(evaluate_source_param(
        params, "stroke_width", time_ms,
        evaluate_source_param(params, "outline_width", time_ms, 0.0),
    )))
    shadow = QColor(str(evaluate_source_param(params, "shadow_color", time_ms, "transparent")))
    shadow_offset = (
        float(evaluate_source_param(params, "shadow_offset_x", time_ms, 0.0)),
        float(evaluate_source_param(params, "shadow_offset_y", time_ms, 0.0)),
    )
    animation = evaluate_source_param(params, "text_animation", time_ms, {})
    animation = animation if isinstance(animation, Mapping) else {}
    motions = evaluate_glyph_motion(text, animation, time_ms, max(1, layer.out_ms - layer.in_ms))
    text_path = evaluate_source_param(params, "text_path", time_ms, None)
    text_path = text_path if isinstance(text_path, Mapping) else None

    if not animation and text_path is None:
        align = str(evaluate_source_param(params, "alignment", time_ms,
                                          evaluate_source_param(params, "align", time_ms, "center"))).lower()
        block_height = line_height * len(layout.lines)
        top = padding + max(0.0, (height - padding * 2.0 - block_height) * .5)
        path = QPainterPath()
        for line_index, line in enumerate(layout.lines):
            x = line_origin_x(line, width, padding, align)
            y = top + line_index * line_height
            for glyph in line.glyphs:
                positioned = QPainterPath(glyph.path)
                positioned.translate(x + glyph.position.x(), y)
                path.addPath(positioned)
        if shadow.isValid() and shadow.alpha() > 0:
            shifted = QPainterPath(path)
            shifted.translate(*shadow_offset)
            painter.fillPath(shifted, shadow)
        if stroke_width > 0:
            painter.strokePath(path, QPen(stroke, stroke_width * 2.0))
        painter.fillPath(path, fill)
        painter.end()
        return image

    if text_path is not None:
        points = _path_samples(text_path)
        lengths = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(points, points[1:])]
        path_length = sum(lengths)
        glyphs = visual_glyphs(layout.lines)
        total_advance = sum(glyph.advance for glyph in glyphs)
        offset = float(evaluate_source_param(params, "text_path_offset", time_ms, .5) or 0.0)
        cursor = max(0.0, min(path_length, offset * path_length - total_advance * .5))
        for glyph in glyphs:
            point, angle = _point_on_polyline(points, cursor + glyph.advance * .5)
            path = QPainterPath(glyph.path)
            path.translate(-glyph.advance * .5, -glyph.baseline)
            _paint_glyph(painter, path, point, (glyph.advance, metrics.height()),
                         motions.get(glyph.source_index, GlyphTransform.identity()), fill, stroke,
                         stroke_width, shadow, shadow_offset, angle=angle, baseline_path=True)
            cursor += glyph.advance
        painter.end()
        return image

    align = str(evaluate_source_param(params, "alignment", time_ms,
                                      evaluate_source_param(params, "align", time_ms, "center"))).lower()
    block_height = line_height * len(layout.lines)
    top = padding + max(0.0, (height - padding * 2.0 - block_height) * .5)
    for line_index, line in enumerate(layout.lines):
        x = line_origin_x(line, width, padding, align)
        for glyph in line.glyphs:
            _paint_glyph(
                painter, glyph.path,
                QPointF(x + glyph.position.x(), top + line_index * line_height),
                (glyph.advance, line.height),
                motions.get(glyph.source_index, GlyphTransform.identity()),
                fill, stroke, stroke_width, shadow, shadow_offset,
            )
    painter.end()
    return image
