from __future__ import annotations

import os

from PySide6.QtWidgets import QApplication

from app.motion_designer.export_renderer import MotionExportRenderer
from app.motion_designer.precomposition import set_embedded_composition
from app.motion_designer.schema import (
    MotionComposition,
    MotionLayer,
    MotionTransform,
    SourceRef,
    animated,
)
from app.motion_designer.ui.window import MotionDocumentController


def _shape_composition() -> MotionComposition:
    layer = MotionLayer(
        id="shape",
        name="Shape",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={
                "primitive": "rectangle",
                "width": 12,
                "height": 12,
                "fill": "#55d6a8",
                "stroke_width": 0,
            },
        ),
        out_ms=1000,
    )
    layer.transform.position.default = [8.0, 8.0]
    return MotionComposition(
        id="level_0",
        name="Level 0",
        width=16,
        height=16,
        duration_ms=1000,
        layers=[layer],
    )


def _instance(child: MotionComposition, layer_id: str) -> MotionLayer:
    layer = MotionLayer(
        id=layer_id,
        name=layer_id,
        layer_type="precomp",
        source=SourceRef(kind="motion_composition"),
        transform=MotionTransform(
            position=animated([0.0, 0.0], "vector2"),
            anchor=animated([0.0, 0.0], "vector2"),
        ),
        out_ms=1000,
    )
    set_embedded_composition(layer, child)
    return layer


def test_three_level_nested_composition_and_hundred_instances_render() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication.instance() or QApplication([])
    level_0 = _shape_composition()
    level_1 = MotionComposition(
        id="level_1",
        name="Level 1",
        width=16,
        height=16,
        duration_ms=1000,
        layers=[_instance(level_0, "nested_0")],
    )
    level_2 = MotionComposition(
        id="level_2",
        name="Level 2",
        width=16,
        height=16,
        duration_ms=1000,
        layers=[_instance(level_1, "nested_1")],
    )
    frame = MotionExportRenderer().render_rgba_array(level_2, 0)
    assert int(frame[:, :, 3].sum()) > 10_000

    instances = MotionComposition(
        id="hundred_instances",
        name="Hundred Instances",
        width=160,
        height=160,
        duration_ms=1000,
        layers=[],
    )
    for index in range(100):
        layer = _instance(level_0, f"instance_{index:03d}")
        layer.transform.position.default = [
            float((index % 10) * 16),
            float((index // 10) * 16),
        ]
        instances.layers.append(layer)
    output = MotionExportRenderer().render_rgba_array(instances, 0)
    assert int(output[:, :, 3].sum()) > 1_000_000


def test_motion_document_controller_supports_five_hundred_undo_steps() -> None:
    composition = _shape_composition()
    controller = MotionDocumentController(composition, lambda _value: None)
    original_name = controller.composition.layers[0].name
    for index in range(500):
        controller.update_layer("shape", {"name": f"Shape {index:03d}"})
    assert controller.composition.layers[0].name == "Shape 499"
    assert controller._history_index == 500
    for _index in range(500):
        controller.undo()
    assert controller._history_index == 0
    assert controller.composition.layers[0].name == original_name
