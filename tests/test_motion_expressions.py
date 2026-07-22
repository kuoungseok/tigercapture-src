from __future__ import annotations

import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.expressions import (
    EXPRESSION_KEY,
    bake_procedural_transform,
    expression_issues,
    set_layer_expression,
    validate_expression_tree,
)
from app.motion_designer.schema import MotionComposition, MotionLayer


def _composition() -> MotionComposition:
    leader = MotionLayer(id="leader", name="Leader", out_ms=2000)
    leader.transform.position.default = [100.0, 50.0]
    follower = MotionLayer(id="follower", name="Follower", out_ms=2000)
    follower.transform.position.default = [0.0, 0.0]
    return MotionComposition(id="comp", width=640, height=360, duration_ms=2000, layers=[leader, follower])


def test_structured_expression_links_property_and_time_without_eval() -> None:
    composition = _composition()
    set_layer_expression(composition.layers[1], "position", {
        "op": "add",
        "left": {"op": "property", "layer_id": "leader", "property": "position"},
        "right": {"op": "vector", "items": [
            {"op": "multiply", "left": {"op": "time"}, "right": 10.0},
            25.0,
        ]},
    })
    state = {item.id: item for item in evaluate_composition(composition, 500.0)}["follower"]
    assert state.position == pytest.approx([105.0, 75.0])


def test_expression_supports_base_clamp_and_remap() -> None:
    composition = _composition()
    composition.layers[1].transform.opacity.default = 0.25
    set_layer_expression(composition.layers[1], "opacity", {
        "op": "clamp",
        "value": {"op": "remap", "value": {"op": "time"},
                  "in_min": 0.0, "in_max": 2.0, "out_min": 0.0, "out_max": 2.0},
        "min": {"op": "base"}, "max": 1.0,
    })
    state = {item.id: item for item in evaluate_composition(composition, 1000.0)}["follower"]
    assert state.opacity == pytest.approx(1.0)


def test_invalid_operation_and_dependency_cycle_are_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported expression operation"):
        validate_expression_tree({"op": "python", "code": "open('x')"})
    composition = _composition()
    set_layer_expression(composition.layers[0], "rotation", {
        "op": "property", "layer_id": "follower", "property": "rotation",
    })
    set_layer_expression(composition.layers[1], "rotation", {
        "op": "property", "layer_id": "leader", "property": "rotation",
    })
    issues = expression_issues(composition)
    assert {issue.code for issue in issues} == {"expression_cycle"}


def test_bake_procedural_transform_removes_expression_and_matches_samples() -> None:
    composition = _composition()
    follower = composition.layers[1]
    set_layer_expression(follower, "rotation", {
        "op": "multiply", "left": {"op": "time"}, "right": 30.0,
    })
    expected = {time: {item.id: item for item in evaluate_composition(composition, time)}["follower"].rotation
                for time in (0.0, 500.0, 1000.0)}
    result = bake_procedural_transform(composition, "follower", sample_fps=2.0)
    assert result["keyframes"] > 0
    assert EXPRESSION_KEY not in follower.metadata
    for time, value in expected.items():
        state = {item.id: item for item in evaluate_composition(composition, time)}["follower"]
        assert state.rotation == pytest.approx(value)


def test_expression_actions_validate_atomically_and_bake() -> None:
    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {"comp": _composition()}

    owner = Owner()
    registry = ActionRegistry(owner)
    invalid = registry.execute("motion.expression.set", {
        "composition_id": "comp", "layer_id": "follower", "property_name": "rotation",
        "expression": {"op": "unknown"},
    })
    assert not invalid.ok
    assert EXPRESSION_KEY not in owner._motion_compositions["comp"].layers[1].metadata
    assigned = registry.execute("motion.expression.set", {
        "composition_id": "comp", "layer_id": "follower", "property_name": "rotation",
        "expression": {"op": "multiply", "left": {"op": "time"}, "right": 12.0},
    })
    assert assigned.ok
    assert registry.execute("motion.expression.validate", {"composition_id": "comp"}).result["ok"]
    assert registry.execute("motion.expression.list", {
        "composition_id": "comp", "layer_id": "follower",
    }).result["count"] == 1
    baked = registry.execute("motion.expression.bake", {
        "composition_id": "comp", "layer_id": "follower", "sample_fps": 4.0,
    })
    assert baked.ok and baked.result["keyframes"] > 0
    assert "expressions" in baked.result["cleared"]
    action_ids = {item["id"] for item in registry.list_actions()}
    assert {"motion.expression.set", "motion.expression.validate", "motion.expression.bake"} <= action_ids
