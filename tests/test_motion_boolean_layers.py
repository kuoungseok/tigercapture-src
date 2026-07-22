from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.motion_designer.boolean_layers import (
    consumed_boolean_operand_ids, resolve_boolean_layer, would_create_boolean_cycle,
)
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.render_graph import build_render_graph
from app.motion_designer.schema import AnimatedProperty, Keyframe, MotionComposition, MotionLayer, SourceRef
from app.motion_designer.validation import validate_composition


def _app() -> QApplication:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    return QApplication.instance() or QApplication([])


def _boolean_composition() -> tuple[MotionComposition, MotionLayer, MotionLayer]:
    target = MotionLayer(
        name="Boolean Result",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 80, "height": 60, "shape": "rectangle",
            "fill": "#ffffff", "stroke_width": 0,
        }),
        out_ms=1100,
    )
    target.transform.position.default = [50, 40]
    operand = MotionLayer(
        name="Cutout",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "width": 28, "height": 28, "shape": "ellipse",
            "fill": "#ffffff", "stroke_width": 0,
        }),
        out_ms=1100,
    )
    operand.transform.position = AnimatedProperty(value_type="vector2", default=[68, 40], keyframes=[
        Keyframe(time_ms=0, value=[68, 40]),
        Keyframe(time_ms=1000, value=[40, 40]),
    ])
    target.source.params["boolean"] = {
        "operation": "subtract",
        "operand_layer_ids": [operand.id],
        "hide_operands": True,
    }
    return MotionComposition(
        width=100, height=80, duration_ms=1000, layers=[target, operand],
    ), target, operand


def test_linked_boolean_operand_uses_live_transform_and_is_consumed() -> None:
    app = _app()
    composition, target, operand = _boolean_composition()
    renderer = MotionExportRenderer()
    start = renderer.render_rgba_array(composition, 0)
    end = renderer.render_rgba_array(composition, 1000)
    assert start[40, 68, 3] == 0
    assert start[40, 40, 3] > 200
    assert end[40, 40, 3] == 0
    assert end[40, 68, 3] > 200
    graph = build_render_graph(composition, 500)
    assert [node.layer_id for node in graph.nodes] == [target.id]
    assert graph.diagnostics["boolean_operand_count"] == 1
    states = {state.id: state for state in evaluate_composition(composition, 500)}
    assert consumed_boolean_operand_ids(composition, states) == {operand.id}
    resolved = resolve_boolean_layer(composition, target, states)
    assert resolved.source.params["boolean"]["resolved_operand_layer_ids"] == [operand.id]
    app.processEvents()


def test_boolean_links_validate_missing_references_and_cycles() -> None:
    composition, target, operand = _boolean_composition()
    assert not would_create_boolean_cycle(composition, target.id, operand.id)
    operand.source.params["boolean"] = {
        "operation": "union", "operand_layer_ids": [target.id], "hide_operands": True,
    }
    assert would_create_boolean_cycle(composition, target.id, operand.id)
    report = validate_composition(composition)
    assert not report.ok
    assert any(issue.code == "vector_boolean_cycle" for issue in report.issues)
    operand.source.params["boolean"]["operand_layer_ids"] = ["missing"]
    report = validate_composition(composition)
    assert any(issue.code == "missing_vector_boolean_operand" for issue in report.issues)
