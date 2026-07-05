from __future__ import annotations

from types import SimpleNamespace

from app.typo_layout import (
    TextBlockLayout,
    aligned_line_origin,
    background_rect_for_block,
    clamp_opacity,
    glyph_pivot,
    make_text_preview_font,
    measure_text_block,
    resolve_text_fill_color,
)


class _FakeMetrics:
    def height(self) -> int:
        return 20

    def horizontalAdvance(self, text: str) -> int:
        return len(text) * 10


def test_measure_text_block_preserves_preview_math():
    layout = measure_text_block("A\nABCD", _FakeMetrics(), 1.5, 100.0, 80.0)

    assert layout.lines == ["A", "ABCD"]
    assert layout.line_height == 30
    assert layout.total_height == 60
    assert layout.widest == 40
    assert layout.block_x == 80.0
    assert layout.block_y == 50.0


def test_background_rect_and_alignment_helpers_match_inline_formula():
    layout = TextBlockLayout(
        lines=["x"],
        line_height=30,
        total_height=60,
        widest=100,
        block_x=200.5,
        block_y=120.5,
    )

    assert background_rect_for_block(layout, 8) == (192, 112, 116, 76)
    assert aligned_line_origin(layout, 40, 1, 12, "left") == (200.5, 162.5)
    assert aligned_line_origin(layout, 40, 1, 12, "right") == (260.5, 162.5)
    assert aligned_line_origin(layout, 40, 1, 12, "center") == (230.5, 162.5)


def test_color_opacity_and_glyph_pivot_helpers():
    assert clamp_opacity(-0.25) == 0.0
    assert clamp_opacity(0.4) == 0.4
    assert clamp_opacity(1.5) == 1.0

    assert resolve_text_fill_color("#111111") == "#111111"
    assert resolve_text_fill_color("#111111", "#222222") == "#222222"
    assert resolve_text_fill_color("#111111", "#222222", mono=True) == "#111111"
    assert resolve_text_fill_color(None, None) == "#FFFFFF"

    assert glyph_pivot(10.0, 20, 50.0, 12, 24, 0.5, 0.25) == (20.0, 44.0)


def test_make_text_preview_font_copies_style_fields():
    style = SimpleNamespace(
        font_family="Arial",
        font_size=24,
        font_weight=700,
        letter_spacing=2.5,
    )

    font = make_text_preview_font(style)

    assert font.family() == "Arial"
    assert font.pointSize() == 24
    assert int(font.weight()) == 700
