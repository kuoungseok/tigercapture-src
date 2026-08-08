from __future__ import annotations

from app.motion_designer.expressions import EXPRESSION_KEY
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.validation import validate_composition


def test_validation_reports_cross_layer_expression_cycle_with_stable_code() -> None:
    first = MotionLayer(id="first")
    second = MotionLayer(id="second")
    first.metadata[EXPRESSION_KEY] = {
        "scale": {"op": "property", "layer_id": "second", "property": "scale"},
    }
    second.metadata[EXPRESSION_KEY] = {
        "scale": {"op": "property", "layer_id": "first", "property": "scale"},
    }
    report = validate_composition(MotionComposition(layers=[first, second]))
    cycle_issues = [issue for issue in report.issues if issue.code == "expression_cycle"]
    assert len(cycle_issues) == 2
    assert all("metadata.expressions.scale" in issue.path for issue in cycle_issues)
