from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.motion_designer.adapters.typography import render_typography
from app.motion_designer.schema import MotionLayer, SourceRef
from app.motion_designer.typography_fonts import typography_preflight
from app.motion_designer.typography_motion import evaluate_glyph_motion, selector_units
from app.actions.registry import ActionRegistry


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


def test_selector_character_units_follow_unicode_grapheme_boundaries() -> None:
    text = "A🇰🇷👍🏽👨‍👩‍👧‍👦B"
    units = selector_units(text, "character")
    assert [text[row.start:row.end] for row in units] == [
        "A", "🇰🇷", "👍🏽", "👨‍👩‍👧‍👦", "B",
    ]


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


def test_text_animator_stack_composites_range_properties_and_ordering() -> None:
    config = {
        "animators": [
            {
                "id": "left",
                "unit": "character",
                "selector_start": 0.0,
                "selector_end": 0.5,
                "properties": {
                    "position": [12, -4],
                    "rotation": 15,
                    "fill": "#ff3344",
                },
            },
            {
                "id": "all",
                "unit": "character",
                "selector_start": 0.0,
                "selector_end": 1.0,
                "randomize_order": True,
                "random_seed": 42,
                "properties": {
                    "scale": [1.5, 0.75],
                    "opacity": 0.8,
                    "tracking": 6,
                    "blur": 3,
                },
            },
        ],
    }
    first = evaluate_glyph_motion("ABCD", config, 0, 1000)
    second = evaluate_glyph_motion("ABCD", config, 0, 1000)
    assert first == second
    assert first[0].offset_x == 12
    assert first[1].rotation_deg == 15
    assert first[0].color_override == "#ff3344"
    assert first[2].offset_x == 0
    assert all(value.scale_x == 1.5 for value in first.values())
    assert all(value.opacity == 0.8 for value in first.values())
    assert all(value.tracking == 6 for value in first.values())
    assert all(value.blur_px == 3 for value in first.values())


def test_text_selector_shapes_weight_animator_properties() -> None:
    motion = evaluate_glyph_motion(
        "ABCD",
        {
            "animators": [{
                "selector_shape": "ramp_up",
                "selector_amount": 1.0,
                "properties": {"position": [100, 0], "opacity": 0.0},
            }],
        },
        0,
        1000,
    )
    assert motion[0].offset_x < motion[3].offset_x
    assert motion[0].opacity > motion[3].opacity


def test_text_animator_stack_actions_add_update_and_remove() -> None:
    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    layer = _layer(text_animation={})
    layer.id = "title"
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    added = registry.execute(
        "motion.text.animator.add",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "animator": {
                "name": "Accent",
                "selector_end": 0.5,
                "properties": {"position": [0, -20]},
            },
        },
    )
    assert added.ok
    animator_id = added.result["animator"]["id"]
    assert registry.execute(
        "motion.text.animator.update",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "animator_id": animator_id,
            "changes": {"smoothness": 0.75},
        },
    ).ok
    assert registry.execute(
        "motion.text.animator.remove",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "animator_id": animator_id,
        },
    ).ok


def test_typography_panel_adds_editable_animator_stack() -> None:
    from app.motion_designer.ui.typography_panel import TypographyPanel

    app = QApplication.instance() or QApplication([])
    panel = TypographyPanel()
    layer = _layer(text_animation={})
    panel.set_layer(layer)
    emitted = []
    panel.source_changed.connect(emitted.append)
    panel._add_animator()
    panel.glyph_x.setValue(24)
    panel.glyph_tracking.setValue(8)
    panel.glyph_blur.setValue(4)
    assert panel.animator_list.count() == 2
    assert emitted[-1]["text_animators"][0]["properties"]["position"][0] == 24
    assert emitted[-1]["text_animators"][0]["properties"]["tracking"] == 8
    assert emitted[-1]["text_animators"][0]["properties"]["blur"] == 4
    panel.deleteLater()
    app.processEvents()
