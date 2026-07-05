from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontMetrics


@dataclass(frozen=True)
class TextBlockLayout:
    lines: list[str]
    line_height: int
    total_height: int
    widest: int
    block_x: float
    block_y: float


def make_text_preview_font(style) -> QFont:
    font = QFont(style.font_family, int(style.font_size))
    font.setWeight(QFont.Weight(int(style.font_weight)))
    if style.letter_spacing:
        font.setLetterSpacing(
            QFont.SpacingType.AbsoluteSpacing,
            float(style.letter_spacing),
        )
    return font


def measure_text_block(text: str, fm: QFontMetrics, line_height_scale: float, cx: float, cy: float) -> TextBlockLayout:
    lines = text.split("\n") if text else [text]
    line_h = int(fm.height() * float(line_height_scale))
    total_h = max(line_h, line_h * len(lines))
    widest = max((fm.horizontalAdvance(ln) for ln in lines), default=0)
    return TextBlockLayout(
        lines=lines,
        line_height=line_h,
        total_height=total_h,
        widest=widest,
        block_x=cx - widest / 2.0,
        block_y=cy - total_h / 2.0,
    )


def background_rect_for_block(layout: TextBlockLayout, padding: int) -> tuple[int, int, int, int]:
    pad = max(0, int(padding))
    return (
        int(layout.block_x - pad),
        int(layout.block_y - pad),
        int(layout.widest + 2 * pad),
        int(layout.total_height + 2 * pad),
    )


def aligned_line_origin(
    layout: TextBlockLayout,
    line_width: int,
    line_index: int,
    ascent: int,
    alignment: str,
) -> tuple[float, float]:
    if alignment == "left":
        lx = layout.block_x
    elif alignment == "right":
        lx = layout.block_x + (layout.widest - line_width)
    else:
        lx = layout.block_x + (layout.widest - line_width) / 2.0
    ly = layout.block_y + line_index * layout.line_height + ascent
    return lx, ly


def clamp_opacity(value) -> float:
    return max(0.0, min(1.0, float(value)))


def resolve_text_fill_color(style_color: str | None, override: str | None = None, *, mono: bool = False) -> str:
    if mono:
        return style_color or "#FFFFFF"
    return override or style_color or "#FFFFFF"


def glyph_pivot(
    glyph_x: float,
    glyph_width: int,
    baseline_y: float,
    ascent: int,
    height: int,
    pivot_x: float,
    pivot_y: float,
) -> tuple[float, float]:
    return (
        glyph_x + glyph_width * float(pivot_x),
        (baseline_y - ascent) + height * float(pivot_y),
    )


__all__ = [
    "TextBlockLayout",
    "make_text_preview_font",
    "measure_text_block",
    "background_rect_for_block",
    "aligned_line_origin",
    "clamp_opacity",
    "resolve_text_fill_color",
    "glyph_pivot",
]
