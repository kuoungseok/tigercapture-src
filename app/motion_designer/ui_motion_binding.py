"""Stable bindings between external UI objects and Motion compositions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Mapping

from .schema import MotionComposition, new_motion_id


UI_MOTION_BINDINGS_KEY = "ui_motion_bindings"
UI_MOTION_BINDING_SCHEMA = "tigerstudio.motion.ui_binding.v1"
UI_MOTION_BINDING_VERSION = 1

UI_MOTION_SCOPES = (
    "component_state",
    "transition",
    "entrance",
    "exit",
    "loop",
)
UI_COMPONENT_STATES = (
    "normal",
    "hover",
    "pressed",
    "focused",
    "disabled",
    "selected",
)
UI_MOTION_DELIVERY_POLICIES = (
    "native_only",
    "native_preferred",
    "bake_allowed",
)
UI_MOTION_NATIVE_UMG_PROPERTIES = {
    "position",
    "scale",
    "rotation",
    "opacity",
}
UI_MOTION_MATERIAL_PROPERTIES = {
    "fill",
    "stroke",
    "corner_radius",
    "progress",
}
UI_MOTION_PROPERTIES = (
    *sorted(UI_MOTION_NATIVE_UMG_PROPERTIES),
    *sorted(UI_MOTION_MATERIAL_PROPERTIES),
)
UI_MOTION_UMG_TRIGGERS = {
    "click": "clicked",
    "clicked": "clicked",
    "pointer_enter": "hovered",
    "hovered": "hovered",
    "pointer_leave": "unhovered",
    "unhovered": "unhovered",
    "pointer_down": "pressed",
    "pressed": "pressed",
    "pointer_up": "released",
    "released": "released",
}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    rows: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text and text not in rows:
            rows.append(text)
    return rows


@dataclass(slots=True)
class UIMotionBinding:
    id: str = field(default_factory=lambda: new_motion_id("ui_binding"))
    source_document_id: str = ""
    source_object_id: str = ""
    source_component_id: str = ""
    host_layer_id: str = ""
    layer_ids: list[str] = field(default_factory=list)
    property_names: list[str] = field(default_factory=list)
    scope: str = "transition"
    trigger: str = ""
    from_state: str = ""
    to_state: str = ""
    animation_name: str = "TigerUITransition"
    autoplay: bool = False
    loop: bool = False
    delivery_policy: str = "native_preferred"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": UI_MOTION_BINDING_SCHEMA,
            "version": UI_MOTION_BINDING_VERSION,
            "id": self.id,
            "source_document_id": self.source_document_id,
            "source_object_id": self.source_object_id,
            "source_component_id": self.source_component_id,
            "host_layer_id": self.host_layer_id,
            "layer_ids": list(self.layer_ids),
            "property_names": list(self.property_names),
            "scope": self.scope,
            "trigger": self.trigger,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "animation_name": self.animation_name,
            "autoplay": bool(self.autoplay),
            "loop": bool(self.loop),
            "delivery_policy": self.delivery_policy,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "UIMotionBinding":
        scope = str(value.get("scope") or "transition").strip().casefold()
        policy = str(
            value.get("delivery_policy") or "native_preferred"
        ).strip().casefold()
        return cls(
            id=str(value.get("id") or new_motion_id("ui_binding")),
            source_document_id=str(value.get("source_document_id") or ""),
            source_object_id=str(value.get("source_object_id") or ""),
            source_component_id=str(value.get("source_component_id") or ""),
            host_layer_id=str(value.get("host_layer_id") or ""),
            layer_ids=_string_list(value.get("layer_ids")),
            property_names=[
                name.casefold() for name in _string_list(value.get("property_names"))
            ],
            scope=scope if scope in UI_MOTION_SCOPES else scope,
            trigger=str(value.get("trigger") or "").strip().casefold(),
            from_state=str(value.get("from_state") or "").strip().casefold(),
            to_state=str(value.get("to_state") or "").strip().casefold(),
            animation_name=str(
                value.get("animation_name") or "TigerUITransition"
            ).strip(),
            autoplay=bool(value.get("autoplay", False)),
            loop=bool(value.get("loop", False)),
            delivery_policy=policy,
            metadata=deepcopy(
                dict(value.get("metadata"))
                if isinstance(value.get("metadata"), Mapping)
                else {}
            ),
        )


def ui_motion_bindings(composition: MotionComposition) -> list[UIMotionBinding]:
    rows = composition.metadata.get(UI_MOTION_BINDINGS_KEY)
    if not isinstance(rows, list):
        return []
    return [
        UIMotionBinding.from_dict(row)
        for row in rows
        if isinstance(row, Mapping)
    ]


def set_ui_motion_bindings(
    composition: MotionComposition,
    bindings: list[UIMotionBinding],
) -> None:
    composition.metadata[UI_MOTION_BINDINGS_KEY] = [
        binding.to_dict() for binding in bindings
    ]


def upsert_ui_motion_binding(
    composition: MotionComposition,
    value: Mapping[str, Any],
) -> UIMotionBinding:
    binding = UIMotionBinding.from_dict(value)
    rows = ui_motion_bindings(composition)
    for index, current in enumerate(rows):
        if current.id == binding.id:
            rows[index] = binding
            break
    else:
        rows.append(binding)
    set_ui_motion_bindings(composition, rows)
    return binding


def remove_ui_motion_binding(
    composition: MotionComposition,
    binding_id: str,
) -> bool:
    rows = ui_motion_bindings(composition)
    kept = [row for row in rows if row.id != str(binding_id)]
    if len(kept) == len(rows):
        return False
    set_ui_motion_bindings(composition, kept)
    return True


def _binding_properties(
    composition: MotionComposition,
    binding: UIMotionBinding,
) -> set[str]:
    if binding.property_names:
        return set(binding.property_names)
    layer_ids = set(binding.layer_ids)
    properties: set[str] = set()
    for layer in composition.layers:
        if layer.id not in layer_ids:
            continue
        for name, prop in layer.transform.properties().items():
            if prop.enabled and prop.keyframes:
                properties.add(name)
    return properties


def validate_ui_motion_bindings(
    composition: MotionComposition,
) -> dict[str, Any]:
    from .interactive_button import button_component

    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    layer_ids = {layer.id for layer in composition.layers}
    bindings = ui_motion_bindings(composition)
    seen_ids: set[str] = set()
    animation_owners: dict[tuple[str, str], str] = {}

    def issue(
        collection: list[dict[str, str]],
        code: str,
        message: str,
        path: str,
    ) -> None:
        collection.append({"code": code, "message": message, "path": path})

    for index, binding in enumerate(bindings):
        path = f"metadata.{UI_MOTION_BINDINGS_KEY}[{index}]"
        if binding.id in seen_ids:
            issue(errors, "duplicate_ui_motion_binding_id", binding.id, f"{path}.id")
        seen_ids.add(binding.id)
        if not binding.source_object_id:
            issue(
                errors,
                "missing_ui_source_object",
                "UI motion binding requires a stable source_object_id.",
                f"{path}.source_object_id",
            )
        if binding.scope not in UI_MOTION_SCOPES:
            issue(
                errors,
                "invalid_ui_motion_scope",
                f"Unsupported UI motion scope: {binding.scope}",
                f"{path}.scope",
            )
        if binding.delivery_policy not in UI_MOTION_DELIVERY_POLICIES:
            issue(
                errors,
                "invalid_ui_motion_delivery_policy",
                f"Unsupported delivery policy: {binding.delivery_policy}",
                f"{path}.delivery_policy",
            )
        if not binding.layer_ids:
            issue(
                errors,
                "empty_ui_motion_layers",
                "UI motion binding requires at least one target layer.",
                f"{path}.layer_ids",
            )
        for layer_index, layer_id in enumerate(binding.layer_ids):
            if layer_id not in layer_ids:
                issue(
                    errors,
                    "missing_ui_motion_layer",
                    f"Unknown UI motion layer: {layer_id}",
                    f"{path}.layer_ids[{layer_index}]",
                )
        if binding.host_layer_id and binding.host_layer_id not in layer_ids:
            issue(
                errors,
                "missing_ui_motion_host_layer",
                f"Unknown UI motion host layer: {binding.host_layer_id}",
                f"{path}.host_layer_id",
            )
        host_layer_id = (
            binding.host_layer_id
            or (
                binding.source_object_id
                if binding.source_object_id in layer_ids
                else ""
            )
            or (binding.layer_ids[0] if binding.layer_ids else "")
        )
        host_layer = next(
            (layer for layer in composition.layers if layer.id == host_layer_id),
            None,
        )
        if (
            binding.trigger
            and host_layer is not None
            and button_component(host_layer) is None
        ):
            issue(
                errors if binding.delivery_policy == "native_only" else warnings,
                "ui_motion_host_requires_interactive_component",
                "Triggered UMG motion requires an interactive host component.",
                f"{path}.host_layer_id",
            )
        unknown_properties = set(binding.property_names) - set(UI_MOTION_PROPERTIES)
        for name in sorted(unknown_properties):
            issue(
                errors,
                "unsupported_ui_motion_property",
                f"Unsupported UI motion property: {name}",
                f"{path}.property_names",
            )
        if binding.scope in {"component_state", "transition"}:
            if binding.to_state not in UI_COMPONENT_STATES:
                issue(
                    errors,
                    "invalid_ui_motion_to_state",
                    "State motion requires a supported to_state.",
                    f"{path}.to_state",
                )
        if binding.scope == "transition" and binding.from_state not in UI_COMPONENT_STATES:
            issue(
                errors,
                "invalid_ui_motion_from_state",
                "Transition motion requires a supported from_state.",
                f"{path}.from_state",
            )
        if not binding.animation_name:
            issue(
                errors,
                "missing_ui_animation_name",
                "UI motion binding requires an animation_name.",
                f"{path}.animation_name",
            )
        if binding.trigger and binding.trigger not in UI_MOTION_UMG_TRIGGERS:
            issue(
                errors if binding.delivery_policy == "native_only" else warnings,
                "ui_motion_trigger_adapter_required",
                f"Trigger requires a non-UMG or custom adapter: {binding.trigger}",
                f"{path}.trigger",
            )

        properties = _binding_properties(composition, binding)
        material = properties & UI_MOTION_MATERIAL_PROPERTIES
        if material and binding.delivery_policy == "native_only":
            issue(
                errors,
                "ui_motion_requires_material",
                "Native-only delivery cannot represent: "
                + ", ".join(sorted(material)),
                f"{path}.property_names",
            )
        elif material:
            issue(
                warnings,
                "ui_motion_material_fallback",
                "UI Material or deterministic bake is required for: "
                + ", ".join(sorted(material)),
                f"{path}.property_names",
            )

        for layer_id in binding.layer_ids:
            for property_name in properties:
                key = (layer_id, property_name)
                owner = animation_owners.get(key)
                if owner is not None and owner != binding.animation_name:
                    issue(
                        errors,
                        "conflicting_ui_motion_track",
                        f"{layer_id}.{property_name} belongs to multiple UI animations.",
                        path,
                    )
                animation_owners[key] = binding.animation_name

    return {
        "schema": "tigerstudio.motion.ui_binding.preflight.v1",
        "ok": not errors,
        "composition_id": composition.id,
        "binding_count": len(bindings),
        "errors": errors,
        "warnings": warnings,
        "bindings": [binding.to_dict() for binding in bindings],
    }


def ui_animation_name(
    composition: MotionComposition,
    layer_id: str,
    property_name: str,
) -> str:
    for binding in ui_motion_bindings(composition):
        if layer_id not in binding.layer_ids:
            continue
        properties = _binding_properties(composition, binding)
        if property_name in properties:
            return binding.animation_name
    return ""


__all__ = [
    "UI_COMPONENT_STATES",
    "UI_MOTION_BINDINGS_KEY",
    "UI_MOTION_BINDING_SCHEMA",
    "UI_MOTION_BINDING_VERSION",
    "UI_MOTION_DELIVERY_POLICIES",
    "UI_MOTION_MATERIAL_PROPERTIES",
    "UI_MOTION_NATIVE_UMG_PROPERTIES",
    "UI_MOTION_PROPERTIES",
    "UI_MOTION_SCOPES",
    "UI_MOTION_UMG_TRIGGERS",
    "UIMotionBinding",
    "remove_ui_motion_binding",
    "set_ui_motion_bindings",
    "ui_animation_name",
    "ui_motion_bindings",
    "upsert_ui_motion_binding",
    "validate_ui_motion_bindings",
]
