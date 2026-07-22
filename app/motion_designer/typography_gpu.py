"""GPU-preview packets backed by a persistent raster glyph atlas."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, cos, floor, radians, sin
from typing import Mapping

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath

from app.typo_animations import GlyphTransform

from .adapters.typography import (
    _path_samples,
    _point_on_polyline,
)
from .schema import MotionLayer
from .typography_layout import (
    ShapedGlyph,
    build_typography_layout,
    line_origin_x,
    visual_glyphs,
)
from .typography_motion import evaluate_glyph_motion
from .vector_shapes import evaluate_source_param


@dataclass(slots=True)
class TypographyGpuPage:
    key: str
    revision: int
    width: int
    height: int
    image: QImage


@dataclass(frozen=True, slots=True)
class TypographyGpuInstance:
    page_key: str
    uv: tuple[float, float, float, float]
    offset: tuple[float, float]
    size: tuple[float, float]
    matrix: tuple[float, float, float, float, float, float]
    color: tuple[float, float, float, float]
    opacity: float


@dataclass(slots=True)
class TypographyGpuPacket:
    width: int
    height: int
    pages: tuple[TypographyGpuPage, ...]
    instances: tuple[TypographyGpuInstance, ...]


@dataclass(frozen=True, slots=True)
class _GlyphEntry:
    page_index: int
    x: int
    y: int
    width: int
    height: int
    offset_x: float
    offset_y: float


class _AtlasPage:
    def __init__(self, key: str, size: int) -> None:
        self.key = key
        self.size = int(size)
        self.image = QImage(self.size, self.size, QImage.Format_RGBA8888_Premultiplied)
        self.image.fill(Qt.transparent)
        self.revision = 0
        self.cursor_x = 1
        self.cursor_y = 1
        self.row_height = 0

    def reserve(self, width: int, height: int) -> tuple[int, int] | None:
        if width + 2 > self.size or height + 2 > self.size:
            return None
        if self.cursor_x + width + 1 > self.size:
            self.cursor_x = 1
            self.cursor_y += self.row_height + 1
            self.row_height = 0
        if self.cursor_y + height + 1 > self.size:
            return None
        position = self.cursor_x, self.cursor_y
        self.cursor_x += width + 1
        self.row_height = max(self.row_height, height)
        return position

    def add(self, bitmap: QImage, x: int, y: int) -> None:
        painter = QPainter(self.image)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.drawImage(x, y, bitmap)
        painter.end()
        self.revision += 1


class TypographyGlyphAtlas:
    def __init__(self, *, page_size: int = 1024, max_pages: int = 8) -> None:
        self.page_size = max(128, int(page_size))
        self.max_pages = max(1, int(max_pages))
        self.generation = 1
        self._pages: list[_AtlasPage] = []
        self._entries: dict[tuple[object, ...], _GlyphEntry] = {}
        self._missing: set[tuple[object, ...]] = set()
        self.cache_hits = 0
        self.cache_misses = 0
        self.last_error = ""

    @staticmethod
    def _font_key(font: QFont) -> tuple[object, ...]:
        axes = tuple(sorted(
            (tag.toString(), float(font.variableAxisValue(tag))) for tag in font.variableAxisTags()
        ))
        return font.toString(), axes

    @staticmethod
    def _bitmap(path: QPainterPath) -> tuple[QImage, float, float] | None:
        bounds = path.boundingRect()
        if path.isEmpty() or bounds.width() <= 0.0 or bounds.height() <= 0.0:
            return None
        left = int(floor(bounds.left())) - 2
        top = int(floor(bounds.top())) - 2
        right = int(ceil(bounds.right())) + 2
        bottom = int(ceil(bounds.bottom())) + 2
        image = QImage(
            max(1, right - left),
            max(1, bottom - top),
            QImage.Format_RGBA8888_Premultiplied,
        )
        image.fill(Qt.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.translate(-left, -top)
        painter.fillPath(path, QColor(255, 255, 255, 255))
        painter.end()
        return image, float(left), float(top)

    def _new_page(self) -> _AtlasPage:
        page = _AtlasPage(f"glyph-atlas-{self.generation}-{len(self._pages)}", self.page_size)
        self._pages.append(page)
        return page

    def clear(self) -> None:
        self.generation += 1
        self._pages.clear()
        self._entries.clear()
        self._missing.clear()
        self.last_error = ""

    def _glyph(self, key: tuple[object, ...], path: QPainterPath) -> _GlyphEntry | None:
        cached = self._entries.get(key)
        if cached is not None:
            self.cache_hits += 1
            return cached
        if key in self._missing:
            self.cache_hits += 1
            return None
        self.cache_misses += 1
        rendered = self._bitmap(path)
        if rendered is None:
            self._missing.add(key)
            return None
        bitmap, offset_x, offset_y = rendered
        if bitmap.width() + 2 > self.page_size or bitmap.height() + 2 > self.page_size:
            self.last_error = "glyph_atlas_glyph_too_large"
            return None
        page_index = -1
        position = None
        for index, page in enumerate(self._pages):
            position = page.reserve(bitmap.width(), bitmap.height())
            if position is not None:
                page_index = index
                break
        if position is None:
            if len(self._pages) >= self.max_pages:
                self.last_error = "glyph_atlas_capacity"
                return None
            page = self._new_page()
            page_index = len(self._pages) - 1
            position = page.reserve(bitmap.width(), bitmap.height())
        if position is None:
            return None
        x, y = position
        self._pages[page_index].add(bitmap, x, y)
        entry = _GlyphEntry(
            page_index,
            x,
            y,
            bitmap.width(),
            bitmap.height(),
            offset_x,
            offset_y,
        )
        self._entries[key] = entry
        return entry

    def glyph(self, font: QFont, grapheme: str) -> _GlyphEntry | None:
        from .adapters.typography import TYPOGRAPHY_GLYPH_CACHE

        key = (*self._font_key(font), str(grapheme))
        return self._glyph(key, TYPOGRAPHY_GLYPH_CACHE.path(font, grapheme))

    def shaped_glyph(self, glyph: ShapedGlyph) -> _GlyphEntry | None:
        return self._glyph(
            ("shaped", glyph.raw_font, int(glyph.glyph_index), glyph.cluster_text),
            glyph.path,
        )

    def page(self, index: int) -> TypographyGpuPage:
        page = self._pages[index]
        return TypographyGpuPage(page.key, page.revision, page.size, page.size, page.image)

    def pages_for_keys(self, keys: set[str]) -> tuple[TypographyGpuPage, ...]:
        return tuple(
            TypographyGpuPage(page.key, page.revision, page.size, page.size, page.image)
            for page in self._pages if page.key in keys
        )

    def diagnostics(self) -> dict[str, int]:
        return {
            "glyph_atlas_pages": len(self._pages),
            "glyph_atlas_entries": len(self._entries),
            "glyph_atlas_hits": self.cache_hits,
            "glyph_atlas_misses": self.cache_misses,
        }


TYPOGRAPHY_GLYPH_ATLAS = TypographyGlyphAtlas()


def _glyph_matrix(
    origin: QPointF,
    size: tuple[float, float],
    motion: GlyphTransform,
    *,
    angle: float = 0.0,
    baseline_path: bool = False,
) -> tuple[float, float, float, float, float, float]:
    pivot_x = 0.0 if baseline_path else size[0] * motion.pivot_x
    pivot_y = -size[1] * 0.5 if baseline_path else size[1] * motion.pivot_y
    theta = radians(float(angle) + float(motion.rotation_deg))
    a = cos(theta) * float(motion.scale_x)
    b = sin(theta) * float(motion.scale_x)
    c = -sin(theta) * float(motion.scale_y)
    d = cos(theta) * float(motion.scale_y)
    target_x = origin.x() + pivot_x + float(motion.offset_x)
    target_y = origin.y() + pivot_y + float(motion.offset_y)
    return (
        a,
        b,
        c,
        d,
        target_x - a * pivot_x - c * pivot_y,
        target_y - b * pivot_x - d * pivot_y,
    )


def _color(value: str, fallback: QColor) -> tuple[float, float, float, float]:
    color = QColor(str(value)) if value else QColor(fallback)
    if not color.isValid():
        color = QColor(fallback)
    return color.redF(), color.greenF(), color.blueF(), color.alphaF()


def _instance(
    atlas: TypographyGlyphAtlas,
    glyph: ShapedGlyph,
    origin: QPointF,
    glyph_height: float,
    motion: GlyphTransform,
    fill: QColor,
    *,
    angle: float = 0.0,
    baseline_path: bool = False,
    offset: tuple[float, float] = (0.0, 0.0),
) -> TypographyGpuInstance | None:
    entry = atlas.shaped_glyph(glyph)
    if entry is None:
        return None
    page = atlas.page(entry.page_index)
    return TypographyGpuInstance(
        page_key=page.key,
        uv=(
            entry.x / page.width,
            entry.y / page.height,
            entry.width / page.width,
            entry.height / page.height,
        ),
        offset=(entry.offset_x + offset[0], entry.offset_y + offset[1]),
        size=(float(entry.width), float(entry.height)),
        matrix=_glyph_matrix(
            origin,
            (glyph.advance, glyph_height),
            motion,
            angle=angle,
            baseline_path=baseline_path,
        ),
        color=_color(str(motion.color_override or ""), fill),
        opacity=max(0.0, min(1.0, float(motion.opacity))),
    )


def build_typography_gpu_packet(
    layer: MotionLayer,
    time_ms: float,
    *,
    atlas: TypographyGlyphAtlas = TYPOGRAPHY_GLYPH_ATLAS,
    _retry_after_clear: bool = False,
) -> tuple[TypographyGpuPacket | None, str]:
    atlas.last_error = ""
    if layer.layer_type != "text":
        return None, "non_typography_layer"
    if layer.effects:
        return None, "typography_effects"
    if layer.masks:
        return None, "typography_masks"
    params = layer.source.params
    background = QColor(str(evaluate_source_param(params, "background_color", time_ms, "transparent")))
    if background.isValid() and background.alpha() > 0:
        return None, "typography_background"
    stroke_width = max(0.0, float(evaluate_source_param(
        params,
        "stroke_width",
        time_ms,
        evaluate_source_param(params, "outline_width", time_ms, 0.0),
    )))
    if stroke_width > 0.0:
        return None, "typography_stroke"
    shadow = QColor(str(evaluate_source_param(params, "shadow_color", time_ms, "transparent")))
    if shadow.isValid() and shadow.alpha() > 0:
        return None, "typography_shadow"

    layout = build_typography_layout(layer, time_ms)
    text = layout.text
    metrics = layout.metrics
    padding = layout.padding
    line_height = layout.line_height
    width = layout.width
    height = layout.height
    fill = QColor(str(evaluate_source_param(
        params,
        "fill",
        time_ms,
        evaluate_source_param(params, "color", time_ms, "#ffffff"),
    )))
    if not fill.isValid():
        fill = QColor("#ffffff")
    animation = evaluate_source_param(params, "text_animation", time_ms, {})
    animation = animation if isinstance(animation, Mapping) else {}
    motions = evaluate_glyph_motion(text, animation, time_ms, max(1, layer.out_ms - layer.in_ms))
    text_path = evaluate_source_param(params, "text_path", time_ms, None)
    text_path = text_path if isinstance(text_path, Mapping) else None
    instances: list[TypographyGpuInstance] = []

    if text_path is not None:
        points = _path_samples(text_path)
        path_length = sum(
            ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
            for start, end in zip(points, points[1:])
        )
        glyphs = visual_glyphs(layout.lines)
        total_advance = sum(glyph.advance for glyph in glyphs)
        path_offset = float(evaluate_source_param(params, "text_path_offset", time_ms, 0.5) or 0.0)
        cursor = max(0.0, min(path_length, path_offset * path_length - total_advance * 0.5))
        for glyph in glyphs:
            point, angle = _point_on_polyline(points, cursor + glyph.advance * 0.5)
            instance = _instance(
                atlas,
                glyph,
                point,
                metrics.height(),
                motions.get(glyph.source_index, GlyphTransform.identity()),
                fill,
                angle=angle,
                baseline_path=True,
                offset=(-glyph.advance * 0.5, -glyph.baseline),
            )
            if instance is not None:
                instances.append(instance)
            elif atlas.last_error:
                if not _retry_after_clear:
                    atlas.clear()
                    return build_typography_gpu_packet(
                        layer,
                        time_ms,
                        atlas=atlas,
                        _retry_after_clear=True,
                    )
                return None, atlas.last_error
            cursor += glyph.advance
    else:
        align = str(evaluate_source_param(
            params,
            "alignment",
            time_ms,
            evaluate_source_param(params, "align", time_ms, "center"),
        )).lower()
        block_height = line_height * len(layout.lines)
        top = padding + max(0.0, (height - padding * 2.0 - block_height) * 0.5)
        for line_index, line in enumerate(layout.lines):
            x = line_origin_x(line, width, padding, align)
            for glyph in line.glyphs:
                instance = _instance(
                    atlas,
                    glyph,
                    QPointF(x + glyph.position.x(), top + line_index * line_height),
                    line.height,
                    motions.get(glyph.source_index, GlyphTransform.identity()),
                    fill,
                )
                if instance is not None:
                    instances.append(instance)
                elif atlas.last_error:
                    if not _retry_after_clear:
                        atlas.clear()
                        return build_typography_gpu_packet(
                            layer,
                            time_ms,
                            atlas=atlas,
                            _retry_after_clear=True,
                        )
                    return None, atlas.last_error

    page_keys = {instance.page_key for instance in instances}
    pages = atlas.pages_for_keys(page_keys)
    return TypographyGpuPacket(width, height, pages, tuple(instances)), ""
