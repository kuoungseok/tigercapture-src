from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase, QImage, QRawFont
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.schema import MotionLayer, SourceRef
from app.motion_designer.typography_gpu import TypographyGlyphAtlas, build_typography_gpu_packet
from app.motion_designer.typography_layout import build_typography_layout


ARABIC = "\u0627\u0644\u0633\u0644\u0627\u0645"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _layer(text: str, **params) -> MotionLayer:
    values = {
        "text": text,
        "width": 720,
        "height": 220,
        "font_family": "Segoe UI",
        "font_size": 88,
        "fill": "#f4f7fb",
        "padding": 16,
        "text_animation": {
            "in": "slide-up-in",
            "hold": "none",
            "out": "none",
            "in_duration_ms": 900,
            "out_duration_ms": 0,
            "unit": "character",
            "stagger_ms": 20,
        },
    }
    values.update(params)
    return MotionLayer(
        name="Shaped Text",
        layer_type="text",
        source=SourceRef(kind="typography", params=values),
        out_ms=2000,
    )


def _load_contextual_font() -> str:
    candidates = (
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    for path in candidates:
        if not path.is_file():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            return families[0]
    pytest.skip("No contextual Arabic test font is available")


def _alpha_sum(image: QImage) -> int:
    converted = image.convertToFormat(QImage.Format_RGBA8888)
    return sum(
        converted.pixelColor(x, y).alpha()
        for y in range(converted.height())
        for x in range(converted.width())
    )


def test_qt_layout_preserves_contextual_arabic_glyphs_and_source_indexes() -> None:
    _app()
    family = _load_contextual_font()
    layout = build_typography_layout(_layer(ARABIC, font_family=family), 700)
    glyphs = list(layout.lines[0].glyphs)
    assert glyphs
    assert all(0 <= glyph.source_index < len(ARABIC) for glyph in glyphs)
    assert [glyph.position.x() for glyph in glyphs] == sorted(
        (glyph.position.x() for glyph in glyphs), reverse=True,
    )

    raw_indexes = QRawFont.fromFont(layout.font).glyphIndexesForString(ARABIC)
    shaped_indexes = [glyph.glyph_index for glyph in glyphs]
    assert shaped_indexes != raw_indexes
    assert any(glyph.source_index > 0 for glyph in glyphs)


def test_painter_and_gpu_consume_the_same_mixed_direction_shaped_layout() -> None:
    _app()
    family = _load_contextual_font()
    text = f"TIGER {ARABIC}"
    layer = _layer(text, font_family=family)
    layout = build_typography_layout(layer, 700)
    expected_visible = sum(not glyph.path.isEmpty() for line in layout.lines for glyph in line.glyphs)

    atlas = TypographyGlyphAtlas(page_size=512, max_pages=4)
    packet, reason = build_typography_gpu_packet(layer, 700, atlas=atlas)
    assert reason == "" and packet is not None
    assert len(packet.instances) == expected_visible
    assert atlas.diagnostics()["glyph_atlas_entries"] > len(set("TIGER"))
    assert _alpha_sum(render_typography(layer, 700)) > 10000


def test_text_path_uses_shaped_arabic_glyphs_without_isolating_characters() -> None:
    _app()
    family = _load_contextual_font()
    layer = _layer(
        ARABIC,
        font_family=family,
        text_animation={},
        text_path={
            "closed": False,
            "points": [
                {"position": [40, 150], "out": [140, -100]},
                {"position": [680, 150], "in": [-140, -100]},
            ],
        },
        text_path_offset=0.5,
    )
    layout = build_typography_layout(layer, 0)
    packet, reason = build_typography_gpu_packet(
        layer,
        0,
        atlas=TypographyGlyphAtlas(page_size=512, max_pages=4),
    )
    assert reason == "" and packet is not None
    assert len(packet.instances) == sum(
        not glyph.path.isEmpty() for line in layout.lines for glyph in line.glyphs
    )
    assert _alpha_sum(render_typography(layer, 0)) > 10000
