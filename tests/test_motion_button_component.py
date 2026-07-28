from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
import pytest

from app.actions.registry import ActionRegistry
from app.motion_designer.evaluator import evaluate_composition
from app.motion_designer.interactive_button import (
    BUTTON_STATES,
    ButtonAction,
    button_component,
    create_button_component,
    update_button_component_data,
)
from app.motion_designer.schema import MotionComposition, MotionLayer, SourceRef
from app.motion_designer.ui.window import MotionDesignerWindow
from app.motion_designer.validation import validate_composition


class Owner:
    def __init__(self) -> None:
        self._motion_compositions = {}


def _shape_layer() -> MotionLayer:
    layer = MotionLayer(
        name="CTA",
        layer_type="shape",
        source=SourceRef(
            kind="shape",
            params={"shape": "rectangle", "width": 360, "height": 120, "fill": "#287a92"},
        ),
        out_ms=2000,
    )
    layer.transform.position.default = [400.0, 300.0]
    return layer


def test_button_component_round_trips_and_changes_evaluated_transform() -> None:
    layer = _shape_layer()
    component = create_button_component(layer)
    assert set(component.states) == set(BUTTON_STATES)
    component.active_state = "pressed"
    update_button_component_data(component, {
        "state": "pressed",
        "state_style": {
            "position_offset": [4.0, 8.0],
            "scale_multiplier": [0.9, 0.85],
            "rotation_offset": 2.0,
            "opacity_multiplier": 0.8,
        },
    })
    layer.metadata["interactive_component"] = component.to_dict()
    composition = MotionComposition(duration_ms=2000, layers=[layer])

    restored = MotionComposition.from_dict(composition.to_dict())
    state = evaluate_composition(restored, 0)[0]
    assert state.position == [404.0, 308.0]
    assert state.scale == [0.9, 0.85]
    assert state.rotation == 2.0
    assert state.opacity == 0.8
    assert button_component(restored.layers[0]).active_state == "pressed"
    assert validate_composition(restored).ok


def test_button_effect_actions_round_trip() -> None:
    layer = _shape_layer()
    component = create_button_component(layer)
    component.actions["clicked"] = [
        ButtonAction(action_type="play_animation", name="cta_burst"),
        ButtonAction(action_type="play_sound", resource_uri="click.wav"),
        ButtonAction(action_type="emit_event", name="open_store"),
    ]
    layer.metadata["interactive_component"] = component.to_dict()

    restored = button_component(
        MotionComposition.from_dict(
            MotionComposition(layers=[layer]).to_dict()
        ).layers[0]
    )
    assert restored is not None
    assert [item.action_type for item in restored.actions["clicked"]] == [
        "play_animation",
        "play_sound",
        "emit_event",
    ]


def test_button_component_on_group_transforms_child_and_supports_preview_override() -> None:
    group = MotionLayer(name="Button Group", layer_type="group", out_ms=2000)
    child = _shape_layer()
    child.parent_id = group.id
    create_button_component(group)
    composition = MotionComposition(duration_ms=2000, layers=[group, child])

    normal = {item.id: item for item in evaluate_composition(composition, 0)}
    hover = {
        item.id: item
        for item in evaluate_composition(
            composition,
            0,
            interaction_states={group.id: "hover"},
        )
    }
    assert normal[group.id].scale == [1.0, 1.0]
    assert hover[group.id].scale == [1.04, 1.04]
    assert hover[child.id].matrix != normal[child.id].matrix
    halfway = {
        item.id: item
        for item in evaluate_composition(
            composition,
            0,
            interaction_states={
                group.id: {
                    "from_state": "normal",
                    "state": "hover",
                    "progress": 0.5,
                    "easing": "linear",
                },
            },
        )
    }
    assert halfway[group.id].scale == pytest.approx([1.02, 1.02])


def test_button_actions_create_edit_preview_and_remove_component() -> None:
    owner = Owner()
    registry = ActionRegistry(owner)
    created = registry.execute(
        "motion.composition.create",
        {"name": "Buttons", "duration_ms": 2000},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    added = registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": _shape_layer().to_dict()},
    )
    layer_id = added.result["payload"]["composition"]["layers"][0]["id"]

    dry = registry.execute(
        "motion.button.create",
        {"composition_id": composition_id, "layer_id": layer_id},
        dry_run=True,
    )
    assert dry.ok
    assert button_component(owner._motion_compositions[composition_id].layers[0]) is None

    created_button = registry.execute(
        "motion.button.create",
        {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "transition_duration_ms": 160,
            "easing": "spring",
            "hit_padding": 18,
        },
    )
    assert created_button.ok
    inspected = registry.execute(
        "motion.button.inspect",
        {"composition_id": composition_id, "layer_id": layer_id},
    )
    assert inspected.result["is_button"] is True
    assert inspected.result["component"]["transition"]["duration_ms"] == 160

    updated = registry.execute(
        "motion.button.update",
        {
            "composition_id": composition_id,
            "layer_id": layer_id,
            "changes": {
                "state": "hover",
                "state_style": {"scale_multiplier": [1.12, 1.12]},
            },
        },
    )
    assert updated.ok
    assert registry.execute(
        "motion.button.state.set",
        {"composition_id": composition_id, "layer_id": layer_id, "state": "hover"},
    ).ok
    assert evaluate_composition(owner._motion_compositions[composition_id], 0)[0].scale == [1.12, 1.12]
    assert registry.execute(
        "motion.button.remove",
        {"composition_id": composition_id, "layer_id": layer_id},
        confirm_destructive=True,
    ).ok


def test_button_panel_edits_selected_layer_and_preserves_undo() -> None:
    existing = QCoreApplication.instance()
    if existing is not None and not isinstance(existing, QApplication):
        pytest.skip("A non-GUI Qt application already owns this test process")
    app = QApplication.instance() or QApplication([])
    layer = _shape_layer()
    window = MotionDesignerWindow(
        MotionComposition(width=960, height=540, duration_ms=2000, layers=[layer])
    )
    assert not window.canvas.hasMouseTracking()
    assert not window.canvas.viewport().hasMouseTracking()
    window._select_layer(layer.id)
    assert window.inspector_tabs.indexOf(window.button) >= 0
    window._create_button_component()
    assert button_component(window.controller.composition.layers[0]) is not None
    assert window.canvas.hasMouseTracking()
    assert window.canvas.viewport().hasMouseTracking()
    window.canvas._set_button_preview_state(layer.id, "hover")
    assert window.canvas._button_preview_states[layer.id]["state"] == "hover"

    window._set_button_state("pressed")
    window._update_button_component({
        "state": "pressed",
        "state_style": {
            "position_offset": [0.0, 6.0],
            "scale_multiplier": [0.92, 0.92],
            "rotation_offset": 0.0,
            "opacity_multiplier": 1.0,
        },
    })
    state = evaluate_composition(window.controller.composition, 0)[0]
    assert state.position == [400.0, 306.0]
    assert state.scale == [0.92, 0.92]
    window.resize(1100, 720)
    window.show()
    window.inspector_tabs.setCurrentWidget(window.button)
    app.processEvents()
    image = window.button.grab().toImage()
    assert not image.isNull()
    assert image.pixelColor(2, 2).lightness() < 90
    window.controller.undo()
    assert evaluate_composition(window.controller.composition, 0)[0].scale == [0.96, 0.96]
    window.close()
    app.processEvents()
