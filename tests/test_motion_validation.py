from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.validation import validate_composition


def test_duplicate_ids_and_parent_cycles_are_rejected() -> None:
    a = MotionLayer(id="same", parent_id="b")
    b = MotionLayer(id="b", parent_id="same")
    duplicate = MotionLayer(id="same")
    report = validate_composition(MotionComposition(layers=[a, b, duplicate]))
    codes = {issue.code for issue in report.issues}
    assert report.ok is False
    assert "duplicate_layer_id" in codes
    assert "parent_cycle" in codes


def test_invalid_vector_path_trim_and_repeater_are_rejected() -> None:
    layer = MotionLayer(layer_type="shape", source=SourceRef(kind="shape", params={
        "shape": "path", "path": {"closed": True, "points": [{"position": [0, 0]}]},
        "trim": {"start": -0.1, "end": 1.2},
        "repeater": {"count": 900},
    }))
    report = validate_composition(MotionComposition(layers=[layer]))
    codes = {issue.code for issue in report.issues}
    assert report.ok is False
    assert "invalid_vector_path" in codes
    assert "invalid_vector_trim" in codes
    assert "invalid_vector_repeater" in codes


def test_invalid_typography_selector_font_axis_and_text_path_are_rejected() -> None:
    layer = MotionLayer(layer_type="text", source=SourceRef(kind="typography", params={
        "font_size": 0,
        "font_axes": {"weight": "heavy"},
        "text_animation": {"in": "missing-animation", "unit": "sentence",
                           "selector_start": .8, "selector_end": .2, "stagger_ms": -1},
        "text_path": {"closed": False, "points": [{"position": [0, 0]}]},
    }))
    report = validate_composition(MotionComposition(layers=[layer]))
    codes = {issue.code for issue in report.issues}
    assert {"invalid_typography_font_size", "invalid_typography_axis",
            "invalid_typography_animation", "invalid_typography_selector",
            "invalid_typography_timing", "invalid_vector_path"} <= codes
