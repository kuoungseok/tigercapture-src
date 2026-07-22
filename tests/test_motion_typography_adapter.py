from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.schema import MotionLayer, SourceRef
from app.motion_designer.typography_fonts import typography_preflight
from app.motion_designer.typography_motion import evaluate_glyph_motion, selector_units


def _layer(**params) -> MotionLayer:
    values = {
        "text": "TIGER", "width": 420, "height": 160,
        "font_family": "Segoe UI", "font_size": 76, "fill": "#ffffff",
        "text_animation": {
            "in": "typewriter-in", "hold": "none", "out": "none",
            "in_duration_ms": 800, "out_duration_ms": 0,
            "unit": "character", "stagger_ms": 80,
        },
    }
    values.update(params)
    return MotionLayer(layer_type="text", source=SourceRef(kind="typography", params=values), out_ms=2000)


def _alpha_sum(image) -> int:
    rgba = image.convertToFormat(QImage.Format_RGBA8888)
    return sum(rgba.pixelColor(x, y).alpha() for y in range(rgba.height()) for x in range(rgba.width()))


def test_selector_units_support_grapheme_word_and_line_ranges() -> None:
    assert len(selector_units("한글 AB", "character")) == 5
    assert [(row.start, row.end) for row in selector_units("한글 AB", "word")] == [(0, 2), (3, 5)]
    assert [(row.start, row.end) for row in selector_units("첫줄\n둘째", "line")] == [(0, 2), (3, 5)]


def test_selector_range_and_stagger_leave_unselected_glyphs_unchanged() -> None:
    config = {
        "in": "fade-in", "in_duration_ms": 1000, "out_duration_ms": 0,
        "unit": "word", "selector_start": 0.0, "selector_end": .5,
        "stagger_ms": 100,
    }
    motion = evaluate_glyph_motion("ONE TWO", config, 0, 2000)
    assert all(motion[index].opacity == 0 for index in range(3))
    assert all(index not in motion for index in range(4, 7))


def test_per_glyph_animation_changes_shared_typography_render_over_time() -> None:
    QApplication.instance() or QApplication([])
    layer = _layer()
    hidden = render_typography(layer, 0)
    visible = render_typography(layer, 900)
    assert _alpha_sum(hidden) < _alpha_sum(visible) * .3


def test_text_on_path_and_variable_font_preflight() -> None:
    QApplication.instance() or QApplication([])
    layer = _layer(
        text="CURVED TITLE", text_animation={},
        text_path={"closed": False, "points": [
            {"position": [30, 110], "out": [100, -80]},
            {"position": [390, 110], "in": [-100, -80]},
        ]},
        text_path_offset=.5,
        font_axes={"wght": 650},
    )
    image = render_typography(layer, 0)
    assert _alpha_sum(image) > 10000
    report = typography_preflight(layer.source.params)
    assert report["resolved_family"]
    assert report["invalid_axes"] == []
    invalid = typography_preflight({"font_family": "__missing_font__", "font_axes": {"bad": "x"}})
    assert invalid["fallback_used"] is True
    assert invalid["invalid_axes"] == ["bad"]
