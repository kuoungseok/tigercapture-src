from __future__ import annotations

from app.actions.registry import ActionRegistry
from app.motion_designer.controllers import (
    create_controller_layer,
    link_controller_property,
)
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.schema import MotionComposition, MotionLayer
from app.motion_designer.validation import validate_composition


def test_controller_null_drives_matching_transform_property() -> None:
    target = MotionLayer(
        id="target",
        name="Target",
        layer_type="shape",
        out_ms=1000,
    )
    composition = MotionComposition(
        id="controllers",
        width=320,
        height=180,
        duration_ms=1000,
        layers=[target],
    )
    controller = create_controller_layer(
        composition,
        name="Position Control",
        position=[220.0, 70.0],
    )
    link_controller_property(
        composition,
        target_layer_id=target.id,
        target_property="position",
        controller_layer_id=controller.id,
        controller_property="position",
    )
    states = {row.id: row for row in evaluate_composition(composition, 0)}
    assert states[target.id].position == [220.0, 70.0]
    assert validate_composition(composition).ok


def test_controller_actions_create_and_link() -> None:
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
        {
            "composition_id": composition_id,
            "layer": MotionLayer(
                id="target",
                layer_type="shape",
                out_ms=1000,
            ).to_dict(),
        },
    ).ok
    controller = registry.execute(
        "motion.controller.create",
        {
            "composition_id": composition_id,
            "name": "Main Controller",
            "position": [400.0, 300.0],
        },
    )
    assert controller.ok
    controller_id = controller.result["payload"]["controller"]["id"]
    linked = registry.execute(
        "motion.controller.link",
        {
            "composition_id": composition_id,
            "target_layer_id": "target",
            "target_property": "position",
            "controller_layer_id": controller_id,
            "controller_property": "position",
        },
    )
    assert linked.ok
