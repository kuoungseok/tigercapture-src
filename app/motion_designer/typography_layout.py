"""Shared Qt-shaped typography layout for Painter and OpenGL preview paths."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from PySide6.QtCore import QPointF
from PySide6.QtGui import (
    QFont,
    QFontMetricsF,
    QPainterPath,
    QRawFont,
    QTextLayout,
)

from .schema import MotionLayer
from .typography_fonts import apply_variable_axes, resolve_font_family
from .vector_shapes import evaluate_source_param


@dataclass(slots=True)
class ShapedGlyph:
    """One already-shaped glyph positioned relative to its line's top edge."""

    raw_font: QRawFont
    glyph_index: int
    source_index: int
    cluster_text: str
    position: QPointF
    advance: float
    baseline: float
    path: QPainterPath


@dataclass(slots=True)
class ShapedLine:
    text: str
    source_start: int
    width: float
    ascent: float
    height: float
    glyphs: tuple[ShapedGlyph, ...]


@dataclass(slots=True)
class TypographyLayout:
    text: str
    font: QFont
    metrics: QFontMetricsF
    padding: float
    line_height: float
    width: int
    height: int
    lines: tuple[ShapedLine, ...]


def typography_font(params: Mapping[str, Any], time_ms: float) -> QFont:
    family, _fallback = resolve_font_family(str(evaluate_source_param(
        params, "font_family", time_ms, "Noto Sans KR",
    )))
    font = QFont(family)
    font.setPixelSize(max(1, int(evaluate_source_param(params, "font_size", time_ms, 72))))
    weight = int(evaluate_source_param(
        params,
        "font_weight",
        time_ms,
        700 if evaluate_source_param(params, "bold", time_ms, False) else 400,
    ))
    font.setWeight(QFont.Weight(max(100, min(900, int(round(weight / 100.0) * 100)))))
    font.setItalic(bool(evaluate_source_param(params, "italic", time_ms, False)))
    font.setUnderline(bool(evaluate_source_param(params, "underline", time_ms, False)))
    font.setLetterSpacing(QFont.AbsoluteSpacing, max(0.0, float(evaluate_source_param(
        params, "letter_spacing", time_ms, 0.0,
    ))))
    axes = evaluate_source_param(params, "font_axes", time_ms, {})
    apply_variable_axes(font, axes if isinstance(axes, Mapping) else {})
    return font


def _split_long_token(token: str, metrics: QFontMetricsF, max_width: float) -> list[str]:
    rows: list[str] = []
    current = ""
    for char in token:
        candidate = current + char
        if current and metrics.horizontalAdvance(candidate) > max_width:
            rows.append(current)
            current = char
        else:
            current = candidate
    if current:
        rows.append(current)
    return rows or [""]


def wrap_text(text: str, metrics: QFontMetricsF, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if metrics.horizontalAdvance(candidate) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            if metrics.horizontalAdvance(word) > max_width:
                chunks = _split_long_token(word, metrics, max_width)
                lines.extend(chunks[:-1])
                current = chunks[-1]
            else:
                current = word
        lines.append(current)
    return lines or [""]


def source_indices(text: str, lines: list[str]) -> list[int]:
    indices: list[int] = []
    cursor = 0
    for line in lines:
        found = text.find(line, cursor) if line else cursor
        found = cursor if found < 0 else found
        indices.append(found)
        cursor = found + len(line)
        while cursor < len(text) and text[cursor] == "\n":
            cursor += 1
    return indices


def shape_line(text: str, font: QFont, source_start: int = 0) -> ShapedLine:
    if not text:
        metrics = QFontMetricsF(font)
        return ShapedLine("", source_start, 0.0, metrics.ascent(), metrics.height(), ())

    layout = QTextLayout(text, font)
    layout.beginLayout()
    line = layout.createLine()
    layout.endLayout()
    if not line.isValid():
        metrics = QFontMetricsF(font)
        return ShapedLine(text, source_start, metrics.horizontalAdvance(text),
                          metrics.ascent(), metrics.height(), ())

    try:
        retrieval = QTextLayout.GlyphRunRetrievalFlag.RetrieveAll
        runs = line.glyphRuns(-1, -1, retrieval)
    except (AttributeError, TypeError):
        runs = line.glyphRuns()

    shaped: list[ShapedGlyph] = []
    for run in runs:
        raw_font = run.rawFont()
        glyph_indexes = list(run.glyphIndexes())
        positions = list(run.positions())
        string_indexes = list(run.stringIndexes())
        advances = list(raw_font.advancesForGlyphIndexes(glyph_indexes))
        for order, (glyph_index, position) in enumerate(zip(glyph_indexes, positions)):
            local_index = string_indexes[order] if order < len(string_indexes) else min(
                len(text) - 1, order,
            )
            baseline = float(position.y())
            path = raw_font.pathForGlyph(int(glyph_index))
            path.translate(0.0, baseline)
            advance = abs(float(advances[order].x())) if order < len(advances) else 0.0
            shaped.append(ShapedGlyph(
                raw_font=raw_font,
                glyph_index=int(glyph_index),
                source_index=source_start + max(0, int(local_index)),
                cluster_text=text[max(0, int(local_index)):max(0, int(local_index)) + 1],
                position=QPointF(float(position.x()), 0.0),
                advance=advance,
                baseline=baseline,
                path=path,
            ))

    return ShapedLine(
        text=text,
        source_start=source_start,
        width=float(line.naturalTextWidth()),
        ascent=float(line.ascent()),
        height=float(line.height()),
        glyphs=tuple(shaped),
    )


def build_typography_layout(layer: MotionLayer, time_ms: float) -> TypographyLayout:
    params = layer.source.params
    text = str(evaluate_source_param(params, "text", time_ms, layer.name))
    font = typography_font(params, time_ms)
    metrics = QFontMetricsF(font)
    padding = max(0.0, float(evaluate_source_param(params, "padding", time_ms, 10.0)))
    requested_width = float(evaluate_source_param(params, "width", time_ms, 0.0) or 0.0)
    wrap_width = max(1.0, requested_width - padding * 2.0) if requested_width else max(
        1.0,
        max((metrics.horizontalAdvance(line) for line in text.splitlines()), default=1.0),
    )
    line_texts = wrap_text(text, metrics, wrap_width) if requested_width else (
        text.splitlines() or [""]
    )
    starts = source_indices(text, line_texts)
    shaped_lines = tuple(
        shape_line(line_text, font, starts[index])
        for index, line_text in enumerate(line_texts)
    )
    line_height = metrics.height() * max(0.5, min(4.0, float(evaluate_source_param(
        params, "line_height", time_ms, 1.2,
    ))))
    content_width = max((line.width for line in shaped_lines), default=1.0)
    width = max(1, int(round(requested_width or content_width + padding * 2.0)))
    requested_height = float(evaluate_source_param(params, "height", time_ms, 0.0) or 0.0)
    height = max(1, int(round(
        requested_height or line_height * len(shaped_lines) + padding * 2.0,
    )))
    return TypographyLayout(
        text=text,
        font=font,
        metrics=metrics,
        padding=padding,
        line_height=line_height,
        width=width,
        height=height,
        lines=shaped_lines,
    )


def line_origin_x(line: ShapedLine, width: int, padding: float, alignment: str) -> float:
    if alignment == "left":
        return padding
    if alignment == "right":
        return width - padding - line.width
    return (width - line.width) * 0.5


def visual_glyphs(lines: tuple[ShapedLine, ...]) -> list[ShapedGlyph]:
    """Flatten lines in visual left-to-right order for placement on a path."""
    result: list[ShapedGlyph] = []
    for line in lines:
        result.extend(sorted(line.glyphs, key=lambda glyph: glyph.position.x()))
    return result
