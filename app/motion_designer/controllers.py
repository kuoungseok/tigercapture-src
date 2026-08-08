"""Controller Null creation and safe property-link helpers."""
from __future__ import annotations

from typing import Any

from .expressions import clear_layer_expression, set_layer_expression
from .graph_editing import layer_graph_property
from .schema import MotionComposition, MotionLayer, SourceRef

CONTROLLER_CONTRACT = "tigerstudio.motion.controller.v1"


def create_controller_layer(
    composition: MotionComposition,
    *,
    name: str = "Controller",
    position: list[float] | None = None,
) -> MotionLayer:
    layer = MotionLayer(
        name=str(name or "Controller"),
        layer_type="null",
        source=SourceRef(
            kind="controller",
            params={"contract": CONTROLLER_CONTRACT},
        ),
        out_ms=composition.duration_ms,
        metadata={
            "controller": {
                "contract": CONTROLLER_CONTRACT,
                "published": [],
            },
        },
    )
    layer.transform.position.default = list(position or [
        composition.width * 0.5,
        composition.height * 0.5,
    ])
    composition.layers.append(layer)
    composition.revision += 1
    return layer


def link_controller_property(
    composition: MotionComposition,
    *,
    target_layer_id: str,
    target_property: str,
    controller_layer_id: str,
    controller_property: str,
) -> dict[str, Any]:
    target = next(
        (row for row in composition.layers if row.id == str(target_layer_id)),
        None,
    )
    controller = next(
        (
            row for row in composition.layers
            if row.id == str(controller_layer_id)
        ),
        None,
    )
    if target is None or controller is None:
        raise ValueError("Unknown target or controller layer")
    if controller.layer_type != "null" or not isinstance(
        controller.metadata.get("controller"),
        dict,
    ):
        raise ValueError("Controller layer must be a Controller Null")
    target_prop = layer_graph_property(target, target_property)
    controller_prop = layer_graph_property(controller, controller_property)
    if target_prop is None or controller_prop is None:
        raise ValueError("Unknown target or controller property")
    if target_prop.value_type != controller_prop.value_type:
        raise ValueError(
            "Controller and target properties require matching value types",
        )
    expression = {
        "op": "property",
        "layer_id": controller.id,
        "property": str(controller_property),
    }
    set_layer_expression(target, target_property, expression)
    published = controller.metadata["controller"].setdefault("published", [])
    row = {
        "target_layer_id": target.id,
        "target_property": str(target_property),
        "controller_property": str(controller_property),
    }
    if row not in published:
        published.append(row)
    composition.revision += 1
    return row


def unlink_controller_property(
    composition: MotionComposition,
    *,
    target_layer_id: str,
    target_property: str,
) -> bool:
    target = next(
        (row for row in composition.layers if row.id == str(target_layer_id)),
        None,
    )
    if target is None:
        raise ValueError(f"Unknown target layer: {target_layer_id}")
    removed = bool(clear_layer_expression(target, target_property))
    if removed:
        for layer in composition.layers:
            controller = layer.metadata.get("controller")
            if not isinstance(controller, dict):
                continue
            controller["published"] = [
                row for row in controller.get("published", [])
                if not (
                    row.get("target_layer_id") == target.id
                    and row.get("target_property") == str(target_property)
                )
            ]
        composition.revision += 1
    return removed


__all__ = [
    "CONTROLLER_CONTRACT",
    "create_controller_layer",
    "link_controller_property",
    "unlink_controller_property",
]
