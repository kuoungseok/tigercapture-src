from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.adapters.shape import render_shape
from app.motion_designer.path_morph import (
    normalize_path_correspondence,
    set_layer_path_morph,
)
from app.motion_designer.schema import (
    AnimatedProperty,
    Keyframe,
    MotionComposition,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.validation import validate_composition
from app.motion_designer.vector_shapes import evaluate_source_param


def _path(points: list[list[float]]) -> dict:
    return {
        "closed": True,
        "fill_rule": "winding",
        "points": [{"position": point} for point in points],
    }


RECTANGLE = _path([[20, 20], [100, 20], [100, 100], [20, 100]])
TRIANGLE = _path([[60, 10], [110, 105], [10, 105]])


def _layer() -> MotionLayer:
    return MotionLayer(
        id="logo",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "width": 120,
                "height": 120,
                "shape": "path",
                "path": RECTANGLE,
                "fill": "#ffffff",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )


def test_path_morph_auto_corresponds_topology_and_renders_midpoint() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    layer = _layer()
    report = set_layer_path_morph(
        layer,
        [
            {"time_ms": 0, "path": RECTANGLE, "interpolation": "linear"},
            {"time_ms": 1000, "path": TRIANGLE, "interpolation": "linear"},
        ],
    )
    assert report["point_count"] == 4
    value = evaluate_source_param(layer.source.params, "path", 500, None)
    assert len(value["points"]) == 4
    assert not render_shape(layer, 500).isNull()
    composition = MotionComposition(
        id="morph",
        width=120,
        height=120,
        duration_ms=1000,
        layers=[layer],
    )
    assert validate_composition(composition).ok


def test_path_morph_validation_rejects_silent_topology_truncation() -> None:
    layer = _layer()
    layer.source.params["path"] = AnimatedProperty(
        value_type="path",
        default=RECTANGLE,
        keyframes=[
            Keyframe(time_ms=0, value=RECTANGLE),
            Keyframe(time_ms=1000, value=TRIANGLE),
        ],
    ).to_dict()
    report = validate_composition(MotionComposition(
        id="invalid_morph",
        duration_ms=1000,
        layers=[layer],
    ))
    assert not report.ok
    assert "path_morph_topology_mismatch" in {
        issue.code for issue in report.issues
    }


def test_path_morph_action_and_explicit_correspondence_contract() -> None:
    normalized = normalize_path_correspondence([RECTANGLE, TRIANGLE])
    assert [len(path["points"]) for path in normalized] == [4, 4]

    class Owner:
        def __init__(self):
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": _layer().to_dict()},
    ).ok
    result = registry.execute(
        "motion.vector.path_morph.set",
        {
            "composition_id": composition_id,
            "layer_id": "logo",
            "keyframes": [
                {"time_ms": 0, "path": RECTANGLE},
                {"time_ms": 1000, "path": TRIANGLE},
            ],
            "auto_correspond": True,
        },
    )
    assert result.ok
    assert result.result["path_morph"]["point_count"] == 4
