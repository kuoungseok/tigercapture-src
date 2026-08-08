from __future__ import annotations

from app.motion_designer.text_selectors import (
    STANDARD_RANGE_SELECTOR_CONTRACT,
    convert_legacy_selector,
    evaluate_selector_weights,
)
from app.motion_designer.typography_motion import evaluate_glyph_motion, selector_units
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.validation import validate_composition
from app.actions.registry import ActionRegistry


def _standard(**values):
    return {
        "selector_contract": STANDARD_RANGE_SELECTOR_CONTRACT,
        "selector_units": "percentage",
        "selector_based_on": "characters",
        "selector_start": 0.0,
        "selector_end": 100.0,
        "selector_offset": 0.0,
        "selector_shape": "square",
        "selector_smoothness": 0.0,
        "selector_amount": 100.0,
        "selector_mode": "add",
        **values,
    }


def test_standard_offset_moves_range_instead_of_rotating_animation_order() -> None:
    units = selector_units("ABCD", "character")
    base = evaluate_selector_weights(units, _standard(selector_end=25.0))
    moved = evaluate_selector_weights(units, _standard(selector_end=25.0, selector_offset=25.0))
    assert [weight for _, weight in base] == [1.0, 0.0, 0.0, 0.0]
    assert [weight for _, weight in moved] == [0.0, 1.0, 0.0, 0.0]


def test_standard_index_units_and_characters_excluding_spaces() -> None:
    motion = evaluate_glyph_motion(
        "A B",
        _standard(
            selector_units="index",
            selector_based_on="characters_excluding_spaces",
            selector_start=1.0,
            selector_end=2.0,
            properties={"position": [20.0, 0.0]},
        ),
        0.0,
        1000.0,
    )
    assert 0 not in motion
    assert 1 not in motion
    assert motion[2].offset_x == 20.0


def test_standard_square_smoothness_feathers_range_edges() -> None:
    units = selector_units("ABCDEFGH", "character")
    hard = [weight for _, weight in evaluate_selector_weights(
        units, _standard(selector_start=25.0, selector_end=75.0),
    )]
    soft = [weight for _, weight in evaluate_selector_weights(
        units,
        _standard(selector_start=25.0, selector_end=75.0, selector_smoothness=100.0),
    )]
    assert set(hard) == {0.0, 1.0}
    assert any(0.0 < weight < 1.0 for weight in soft)


def test_standard_selector_modes_follow_ordered_truth_table() -> None:
    units = selector_units("ABCD", "character")
    config = _standard(selectors=[
        _standard(selector_end=75.0),
        _standard(selector_start=25.0, selector_end=50.0, selector_mode="subtract"),
        _standard(selector_start=50.0, selector_end=100.0, selector_mode="intersect"),
    ])
    assert [weight for _, weight in evaluate_selector_weights(units, config)] == [0.0, 0.0, 1.0, 0.0]


def test_legacy_conversion_is_explicit_and_reports_lossy_fields() -> None:
    legacy = {
        "unit": "word",
        "selector_start": 0.25,
        "selector_end": 0.75,
        "selector_offset": 0.5,
        "smoothness": 0.6,
        "properties": {"position": [10, 0]},
    }
    converted, warnings = convert_legacy_selector(legacy)
    assert legacy["selector_start"] == 0.25
    assert converted["selector_contract"] == STANDARD_RANGE_SELECTOR_CONTRACT
    assert converted["selector_based_on"] == "words"
    assert converted["selector_start"] == 25.0
    assert converted["selector_end"] == 75.0
    assert converted["selector_offset"] == 0.0
    assert converted["animation_smoothing"] == 0.6
    assert len(warnings) == 2


def test_legacy_selector_result_is_unchanged_without_conversion() -> None:
    legacy = {
        "selector_start": 0.0,
        "selector_end": 0.5,
        "selector_offset": 0.5,
        "properties": {"position": [10, 0]},
    }
    motion = evaluate_glyph_motion("ABCD", legacy, 0.0, 1000.0)
    assert set(motion) == {0, 1}
    assert motion[0].offset_x == 10.0


def test_standard_selector_validation_and_conversion_action() -> None:
    layer = MotionLayer(
        id="title",
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "TIGER",
            "text_animation": {
                "selector_offset": 0.25,
                "smoothness": 0.5,
                "properties": {"opacity": 0.0},
            },
        }),
        out_ms=1000,
    )
    composition = MotionComposition(id="selector-test", duration_ms=1000, layers=[layer])
    assert validate_composition(composition).ok

    class Owner:
        def __init__(self):
            self._motion_compositions = {composition.id: composition}

    result = ActionRegistry(Owner()).execute(
        "motion.text.animator.selector.convert",
        {"composition_id": composition.id, "layer_id": layer.id},
    )
    assert result.ok
    assert result.result["selector"]["selector_contract"] == STANDARD_RANGE_SELECTOR_CONTRACT
    assert len(result.result["warnings"]) == 2
    assert validate_composition(composition).ok


def test_standard_selector_validation_rejects_unknown_contract_values() -> None:
    layer = MotionLayer(
        layer_type="text",
        source=SourceRef(kind="typography", params={
            "text": "TIGER",
            "text_animation": _standard(selector_units="pixels"),
        }),
        out_ms=1000,
    )
    report = validate_composition(MotionComposition(duration_ms=1000, layers=[layer]))
    assert not report.ok
    assert any(issue.code == "invalid_typography_selector" for issue in report.issues)
