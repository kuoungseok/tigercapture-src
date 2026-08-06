"""Serializable interactive button components for Motion Designer layers."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import cos, exp, pi
from typing import Any, Mapping

from .schema import MotionLayer


BUTTON_COMPONENT_KEY = "interactive_component"
BUTTON_COMPONENT_VERSION = 2
BUTTON_STATES = ("normal", "hover", "pressed", "disabled", "focused")
BUTTON_EASINGS = ("linear", "ease_out", "ease_in_out", "spring")
BUTTON_ACTION_TYPES = (
    "emit_event",
    "play_animation",
    "play_sound",
    "set_opacity",
    "set_visibility",
    "set_material_scalar",
)


@dataclass(slots=True)
class ButtonAction:
    action_type: str = "emit_event"
    target_id: str = ""
    name: str = ""
    resource_uri: str = ""
    value: Any = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.action_type,
            "target_id": self.target_id,
            "name": self.name,
            "resource_uri": self.resource_uri,
            "value": deepcopy(self.value),
            "parameters": deepcopy(self.parameters),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ButtonAction":
        action_type = str(data.get("type") or "emit_event").lower()
        if action_type not in BUTTON_ACTION_TYPES:
            raise ValueError(f"Unsupported button action: {action_type}")
        return cls(
            action_type=action_type,
            target_id=str(data.get("target_id") or ""),
            name=str(data.get("name") or ""),
            resource_uri=str(data.get("resource_uri") or ""),
            value=deepcopy(data.get("value")),
            parameters=deepcopy(
                dict(data.get("parameters"))
                if isinstance(data.get("parameters"), Mapping)
                else {}
            ),
        )


@dataclass(slots=True)
class ButtonStateStyle:
    position_offset: list[float] = field(default_factory=lambda: [0.0, 0.0])
    scale_multiplier: list[float] = field(default_factory=lambda: [1.0, 1.0])
    rotation_offset: float = 0.0
    opacity_multiplier: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_offset": [float(self.position_offset[0]), float(self.position_offset[1])],
            "scale_multiplier": [float(self.scale_multiplier[0]), float(self.scale_multiplier[1])],
            "rotation_offset": float(self.rotation_offset),
            "opacity_multiplier": float(self.opacity_multiplier),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ButtonStateStyle":
        row = data if isinstance(data, Mapping) else {}
        position = list(row.get("position_offset") or [0.0, 0.0])
        scale = list(row.get("scale_multiplier") or [1.0, 1.0])
        return cls(
            position_offset=[
                float(position[0]) if position else 0.0,
                float(position[1]) if len(position) > 1 else 0.0,
            ],
            scale_multiplier=[
                float(scale[0]) if scale else 1.0,
                float(scale[1]) if len(scale) > 1 else float(scale[0]) if scale else 1.0,
            ],
            rotation_offset=float(row.get("rotation_offset", 0.0) or 0.0),
            opacity_multiplier=max(0.0, min(1.0, float(row.get("opacity_multiplier", 1.0) or 0.0))),
        )


def default_button_states() -> dict[str, ButtonStateStyle]:
    return {
        "normal": ButtonStateStyle(),
        "hover": ButtonStateStyle(
            position_offset=[0.0, -2.0],
            scale_multiplier=[1.04, 1.04],
        ),
        "pressed": ButtonStateStyle(
            position_offset=[0.0, 3.0],
            scale_multiplier=[0.96, 0.96],
        ),
        "disabled": ButtonStateStyle(opacity_multiplier=0.45),
        "focused": ButtonStateStyle(scale_multiplier=[1.02, 1.02]),
    }


@dataclass(slots=True)
class ButtonComponent:
    active_state: str = "normal"
    initial_state: str = "normal"
    transition_duration_ms: int = 120
    easing: str = "ease_out"
    hit_padding: float = 12.0
    states: dict[str, ButtonStateStyle] = field(default_factory=default_button_states)
    triggers: dict[str, str] = field(default_factory=lambda: {
        "pointer_enter": "hover",
        "pointer_down": "pressed",
        "pointer_up": "hover",
        "pointer_leave": "normal",
        "focus": "focused",
        "disable": "disabled",
    })
    actions: dict[str, list[ButtonAction]] = field(default_factory=lambda: {
        "clicked": [ButtonAction(action_type="emit_event", name="clicked")],
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "button",
            "version": BUTTON_COMPONENT_VERSION,
            "active_state": self.active_state,
            "initial_state": self.initial_state,
            "transition": {
                "duration_ms": int(self.transition_duration_ms),
                "easing": self.easing,
            },
            "hit_area": {
                "mode": "layer_bounds",
                "padding": float(self.hit_padding),
            },
            "states": {
                state: self.states.get(state, ButtonStateStyle()).to_dict()
                for state in BUTTON_STATES
            },
            "triggers": dict(self.triggers),
            "actions": {
                trigger: [action.to_dict() for action in actions]
                for trigger, actions in self.actions.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ButtonComponent":
        row = data if isinstance(data, Mapping) else {}
        transition = row.get("transition") if isinstance(row.get("transition"), Mapping) else {}
        hit_area = row.get("hit_area") if isinstance(row.get("hit_area"), Mapping) else {}
        state_rows = row.get("states") if isinstance(row.get("states"), Mapping) else {}
        defaults = default_button_states()
        states = {
            state: ButtonStateStyle.from_dict(
                state_rows.get(state)
                if isinstance(state_rows.get(state), Mapping)
                else defaults[state].to_dict()
            )
            for state in BUTTON_STATES
        }
        active_state = str(row.get("active_state") or "normal").lower()
        initial_state = str(row.get("initial_state") or "normal").lower()
        easing = str(transition.get("easing") or "ease_out").lower()
        trigger_rows = row.get("triggers") if isinstance(row.get("triggers"), Mapping) else {}
        triggers = {
            str(key): str(value)
            for key, value in trigger_rows.items()
            if str(value) in BUTTON_STATES
        }
        action_rows = row.get("actions") if isinstance(row.get("actions"), Mapping) else {}
        actions = {
            str(trigger): [
                ButtonAction.from_dict(action)
                for action in rows
                if isinstance(action, Mapping)
            ]
            for trigger, rows in action_rows.items()
            if isinstance(rows, list)
        }
        return cls(
            active_state=active_state if active_state in BUTTON_STATES else "normal",
            initial_state=initial_state if initial_state in BUTTON_STATES else "normal",
            transition_duration_ms=max(
                0, min(5000, int(transition.get("duration_ms", 120) or 0))
            ),
            easing=easing if easing in BUTTON_EASINGS else "ease_out",
            hit_padding=max(0.0, min(500.0, float(hit_area.get("padding", 12.0) or 0.0))),
            states=states,
            triggers=triggers or {
                "pointer_enter": "hover",
                "pointer_down": "pressed",
                "pointer_up": "hover",
                "pointer_leave": "normal",
                "focus": "focused",
                "disable": "disabled",
            },
            actions=actions or {
                "clicked": [ButtonAction(action_type="emit_event", name="clicked")],
            },
        )


def button_component(layer: MotionLayer) -> ButtonComponent | None:
    raw = layer.metadata.get(BUTTON_COMPONENT_KEY)
    if not isinstance(raw, Mapping) or str(raw.get("type") or "") != "button":
        return None
    return ButtonComponent.from_dict(raw)


def set_button_component(layer: MotionLayer, component: ButtonComponent) -> None:
    layer.metadata[BUTTON_COMPONENT_KEY] = component.to_dict()


def create_button_component(layer: MotionLayer, **changes: Any) -> ButtonComponent:
    component = ButtonComponent()
    update_button_component_data(component, changes)
    set_button_component(layer, component)
    return component


def remove_button_component(layer: MotionLayer) -> bool:
    return layer.metadata.pop(BUTTON_COMPONENT_KEY, None) is not None


def update_button_component_data(
    component: ButtonComponent,
    changes: Mapping[str, Any],
) -> ButtonComponent:
    if "active_state" in changes:
        state = str(changes["active_state"]).lower()
        if state not in BUTTON_STATES:
            raise ValueError(f"Unsupported button state: {state}")
        component.active_state = state
    if "initial_state" in changes:
        state = str(changes["initial_state"]).lower()
        if state not in BUTTON_STATES:
            raise ValueError(f"Unsupported initial button state: {state}")
        component.initial_state = state
    if "transition_duration_ms" in changes:
        component.transition_duration_ms = max(
            0, min(5000, int(changes["transition_duration_ms"]))
        )
    if "easing" in changes:
        easing = str(changes["easing"]).lower()
        if easing not in BUTTON_EASINGS:
            raise ValueError(f"Unsupported button easing: {easing}")
        component.easing = easing
    if "hit_padding" in changes:
        component.hit_padding = max(0.0, min(500.0, float(changes["hit_padding"])))
    if "state" in changes or "state_style" in changes:
        state = str(changes.get("state") or component.active_state).lower()
        if state not in BUTTON_STATES:
            raise ValueError(f"Unsupported button state: {state}")
        current = component.states[state].to_dict()
        style_changes = changes.get("state_style")
        if not isinstance(style_changes, Mapping):
            raise ValueError("state_style must be an object")
        current.update(deepcopy(dict(style_changes)))
        component.states[state] = ButtonStateStyle.from_dict(current)
    if "actions" in changes:
        rows = changes["actions"]
        if not isinstance(rows, Mapping):
            raise ValueError("actions must be an object keyed by trigger")
        component.actions = {
            str(trigger): [
                ButtonAction.from_dict(action)
                for action in action_rows
                if isinstance(action, Mapping)
            ]
            for trigger, action_rows in rows.items()
            if isinstance(action_rows, list)
        }
    return component


def apply_button_state(
    layer: MotionLayer,
    values: dict[str, Any],
    state: str | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    component = button_component(layer)
    if component is None:
        return values
    transition = state if isinstance(state, Mapping) else None
    requested_state = str(
        transition.get("state") if transition is not None else state or component.active_state
    ).lower()
    if requested_state not in BUTTON_STATES:
        requested_state = component.active_state
    style = component.states[requested_state]
    if transition is not None:
        from_state = str(transition.get("from_state") or component.active_state).lower()
        if from_state not in BUTTON_STATES:
            from_state = component.active_state
        progress = max(0.0, min(1.0, float(transition.get("progress", 1.0) or 0.0)))
        progress = _ease_button_progress(
            progress,
            str(transition.get("easing") or component.easing),
        )
        style = _blend_button_styles(component.states[from_state], style, progress)
    result = dict(values)
    result["position"] = [
        float(values["position"][0]) + float(style.position_offset[0]),
        float(values["position"][1]) + float(style.position_offset[1]),
    ]
    result["scale"] = [
        float(values["scale"][0]) * float(style.scale_multiplier[0]),
        float(values["scale"][1]) * float(style.scale_multiplier[1]),
    ]
    result["rotation"] = float(values["rotation"]) + float(style.rotation_offset)
    result["opacity"] = float(values["opacity"]) * float(style.opacity_multiplier)
    return result


def _ease_button_progress(progress: float, easing: str) -> float:
    value = max(0.0, min(1.0, float(progress)))
    if easing == "linear":
        return value
    if easing == "ease_in_out":
        return 4.0 * value ** 3 if value < 0.5 else 1.0 - ((-2.0 * value + 2.0) ** 3) / 2.0
    if easing == "spring":
        return max(0.0, min(1.12, 1.0 - exp(-6.0 * value) * cos(4.5 * pi * value)))
    return 1.0 - (1.0 - value) ** 3


def _blend_button_styles(
    start: ButtonStateStyle,
    end: ButtonStateStyle,
    progress: float,
) -> ButtonStateStyle:
    def blend(left: float, right: float) -> float:
        return float(left) + (float(right) - float(left)) * progress

    return ButtonStateStyle(
        position_offset=[
            blend(start.position_offset[0], end.position_offset[0]),
            blend(start.position_offset[1], end.position_offset[1]),
        ],
        scale_multiplier=[
            blend(start.scale_multiplier[0], end.scale_multiplier[0]),
            blend(start.scale_multiplier[1], end.scale_multiplier[1]),
        ],
        rotation_offset=blend(start.rotation_offset, end.rotation_offset),
        opacity_multiplier=blend(start.opacity_multiplier, end.opacity_multiplier),
    )


__all__ = [
    "BUTTON_COMPONENT_KEY",
    "BUTTON_COMPONENT_VERSION",
    "BUTTON_ACTION_TYPES",
    "BUTTON_EASINGS",
    "BUTTON_STATES",
    "ButtonComponent",
    "ButtonAction",
    "ButtonStateStyle",
    "apply_button_state",
    "button_component",
    "create_button_component",
    "remove_button_component",
    "set_button_component",
    "update_button_component_data",
]
