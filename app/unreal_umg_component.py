"""Schema 18 reusable-component contract for Tiger Studio UMG documents."""
from __future__ import annotations

import json
from typing import Any, Mapping


TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION = 18
UMG_COMPONENT_PROPERTY_TYPES = frozenset(
    {"text", "boolean", "number", "enum", "instance_swap", "slot"}
)
UMG_STATIC_COMPONENT_BINDINGS = {
    "text": frozenset({"content.text"}),
    "boolean": frozenset({"visible"}),
}


def _schema_version(document: Mapping[str, Any]) -> int:
    value = document.get("SchemaVersion")
    return (
        value
        if isinstance(value, int) and not isinstance(value, bool)
        else 0
    )


def _typed_rows(
    document: Mapping[str, Any],
    name: str,
    *,
    required: bool,
    container_reason: str,
    row_reason: str,
) -> tuple[list[Mapping[str, Any]], list[str]]:
    if name not in document:
        return ([], [container_reason] if required else [])
    value = document.get(name)
    if not isinstance(value, list):
        return [], [container_reason]
    rows: list[Mapping[str, Any]] = []
    reasons: list[str] = []
    for row in value:
        if isinstance(row, Mapping):
            rows.append(row)
        else:
            reasons.append(row_reason)
    return rows, reasons


def inspect_umg_component_records(document: object) -> dict[str, Any]:
    """Read schema-18 containers without silently filtering malformed rows."""

    if not isinstance(document, Mapping):
        return {
            "components": [],
            "component_instances": [],
            "component_layers": [],
            "reasons": [],
        }
    schema_version = _schema_version(document)
    required = schema_version >= TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION
    components, component_reasons = _typed_rows(
        document,
        "Components",
        required=required,
        container_reason="umg_components_record_invalid",
        row_reason="umg_component_record_invalid",
    )
    instances, instance_reasons = _typed_rows(
        document,
        "ComponentInstances",
        required=required,
        container_reason="umg_component_instances_record_invalid",
        row_reason="umg_component_instance_record_invalid",
    )
    if schema_version < TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION and (
        components or instances
    ):
        component_reasons.append("umg_components_require_schema_18")
    component_layers: list[Mapping[str, Any]] = []
    for component in components:
        value = component.get("Layers")
        if not isinstance(value, list):
            component_reasons.append("umg_component_layers_record_invalid")
            continue
        for layer in value:
            if isinstance(layer, Mapping):
                component_layers.append(layer)
            else:
                component_reasons.append("umg_component_layer_record_invalid")
    return {
        "components": components,
        "component_instances": instances,
        "component_layers": component_layers,
        "reasons": sorted(set([*component_reasons, *instance_reasons])),
    }


def _string_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        return None
    return list(value)


def _json_object(value: object) -> Mapping[str, Any] | None:
    if not isinstance(value, str):
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, Mapping) else None


def validate_umg_component_contract(document: object) -> list[str]:
    """Validate typed component identity, references, bindings, and slots."""

    if not isinstance(document, Mapping):
        return []
    records = inspect_umg_component_records(document)
    reasons = list(records["reasons"])
    if _schema_version(document) < TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION:
        return sorted(set(reasons))

    raw_screen_layers = document.get("Layers")
    screen_layers = (
        [row for row in raw_screen_layers if isinstance(row, Mapping)]
        if isinstance(raw_screen_layers, list)
        else []
    )
    screen_layer_ids = {
        str(row.get("Id") or "") for row in screen_layers if row.get("Id")
    }
    components = list(records["components"])
    component_ids = [str(row.get("Id") or "") for row in components]
    if any(not component_id for component_id in component_ids):
        reasons.append("umg_component_id_missing")
    if len(set(component_ids)) != len(component_ids):
        reasons.append("umg_component_id_duplicate")
    component_id_set = set(component_ids) - {""}
    slots_by_component: dict[str, set[str]] = {}
    properties_by_component: dict[str, dict[str, dict[str, Any]]] = {}
    variants_by_component: dict[str, dict[str, Any]] = {}
    definition_layer_ids: set[str] = set()
    definition_layer_owner: dict[str, str] = {}
    component_root_by_id: dict[str, str] = {}
    dependency_graph: dict[str, list[str]] = {}
    nested_markers: list[
        tuple[str, Mapping[str, Any], list[Mapping[str, Any]], set[str]]
    ] = []

    for component in components:
        component_id = str(component.get("Id") or "")
        if not isinstance(component.get("Name"), str):
            reasons.append("umg_component_name_invalid")
        root_layer_id = str(component.get("RootLayerId") or "")
        component_root_by_id[component_id] = root_layer_id
        layers = component.get("Layers")
        layers = layers if isinstance(layers, list) else []
        local_ids = [
            str(layer.get("Id") or "")
            for layer in layers
            if isinstance(layer, Mapping)
        ]
        if any(not layer_id for layer_id in local_ids):
            reasons.append("umg_component_layer_id_missing")
        if len(set(local_ids)) != len(local_ids):
            reasons.append("umg_component_layer_id_duplicate")
        if not root_layer_id or root_layer_id not in local_ids:
            reasons.append("umg_component_root_layer_missing")
        if definition_layer_ids.intersection(local_ids):
            reasons.append("umg_component_layer_owned_by_multiple_definitions")
        definition_layer_ids.update(local_ids)
        for layer_id in local_ids:
            definition_layer_owner[layer_id] = component_id
        base_component_id = str(component.get("BaseComponentId") or "")
        if base_component_id and base_component_id not in component_id_set:
            reasons.append("umg_component_base_missing")
        variant_values = _json_object(component.get("VariantValuesJson"))
        if variant_values is None:
            reasons.append("umg_component_variant_values_json_invalid")
            variant_values = {}
        elif any(
            not isinstance(name, str)
            or not name
            or not isinstance(value, str)
            for name, value in variant_values.items()
        ):
            reasons.append("umg_component_variant_values_invalid")
        variants_by_component[component_id] = dict(variant_values)
        dependencies = _string_list(component.get("DependencyComponentIds"))
        if dependencies is None:
            reasons.append("umg_component_dependencies_invalid")
            dependencies = []
        if any(item not in component_id_set for item in dependencies):
            reasons.append("umg_component_dependency_missing")
        if component_id and component_id in dependencies:
            reasons.append("umg_component_dependency_self_reference")
        dependency_graph[component_id] = dependencies
        for layer in layers:
            if not isinstance(layer, Mapping):
                continue
            try:
                payload = json.loads(str(layer.get("PayloadJson") or "{}"))
            except (TypeError, ValueError):
                payload = {}
            marker = (
                payload.get("component_instance")
                if isinstance(payload, Mapping)
                else None
            )
            if marker is None:
                continue
            if not isinstance(marker, Mapping):
                reasons.append("umg_nested_component_instance_marker_invalid")
                continue
            target_component_id = str(marker.get("component_id") or "")
            if str(marker.get("id") or "") != str(layer.get("Id") or ""):
                reasons.append("umg_nested_component_instance_id_mismatch")
            if target_component_id not in component_id_set:
                reasons.append("umg_nested_component_instance_target_missing")
            if target_component_id not in dependencies:
                reasons.append("umg_nested_component_dependency_missing")
            marker_property_values = marker.get("property_values")
            if not isinstance(marker_property_values, Mapping):
                reasons.append("umg_nested_component_property_values_invalid")
                marker_property_values = {}
            if not isinstance(marker.get("resolved_overrides"), Mapping):
                reasons.append("umg_nested_component_overrides_invalid")
            slot_contents = marker.get("slot_contents")
            if not isinstance(slot_contents, list):
                reasons.append("umg_nested_component_slot_contents_invalid")
                slot_contents = []
            nested_markers.append(
                (
                    target_component_id,
                    marker_property_values,
                    slot_contents,
                    set(local_ids),
                )
            )

        raw_properties = component.get("Properties")
        if not isinstance(raw_properties, list):
            reasons.append("umg_component_properties_record_invalid")
            raw_properties = []
        property_names: set[str] = set()
        property_specs: dict[str, dict[str, Any]] = {}
        for prop in raw_properties:
            if not isinstance(prop, Mapping):
                reasons.append("umg_component_property_record_invalid")
                continue
            name = str(prop.get("Name") or "")
            kind = str(prop.get("Type") or "")
            if not name:
                reasons.append("umg_component_property_name_missing")
            if name in property_names:
                reasons.append("umg_component_property_name_duplicate")
            property_names.add(name)
            if kind not in UMG_COMPONENT_PROPERTY_TYPES:
                reasons.append("umg_component_property_type_invalid")
            elif kind in {"number", "instance_swap"}:
                reasons.append(
                    "umg_component_property_runtime_unsupported:"
                    f"{kind}"
                )
            if not isinstance(prop.get("Description"), str):
                reasons.append("umg_component_property_description_invalid")
            try:
                default_value = json.loads(prop.get("DefaultValueJson"))
            except (TypeError, ValueError):
                reasons.append("umg_component_property_default_json_invalid")
                default_value = None
            property_values = _string_list(prop.get("Values"))
            if property_values is None:
                reasons.append("umg_component_property_values_invalid")
                property_values = []
            property_specs[name] = {
                "type": kind,
                "default": default_value,
                "values": property_values,
            }
            if kind == "text" and not isinstance(default_value, str):
                reasons.append("umg_component_property_text_default_invalid")
            elif kind == "boolean" and not isinstance(default_value, bool):
                reasons.append("umg_component_property_boolean_default_invalid")
            elif kind == "number" and (
                not isinstance(default_value, (int, float))
                or isinstance(default_value, bool)
            ):
                reasons.append("umg_component_property_number_default_invalid")
            elif kind in {"enum", "instance_swap"} and not isinstance(
                default_value, str
            ):
                reasons.append("umg_component_property_string_default_invalid")
            if (
                kind == "enum"
                and property_values
                and str(default_value) not in property_values
            ):
                reasons.append("umg_component_property_enum_default_invalid")
            bindings = prop.get("Bindings")
            if not isinstance(bindings, list):
                reasons.append("umg_component_property_bindings_record_invalid")
                bindings = []
            for binding in bindings:
                if not isinstance(binding, Mapping):
                    reasons.append("umg_component_property_binding_record_invalid")
                    continue
                layer_id = str(binding.get("LayerId") or "")
                target_path = str(binding.get("TargetPath") or "")
                if layer_id not in local_ids:
                    reasons.append("umg_component_property_binding_layer_missing")
                supported_paths = UMG_STATIC_COMPONENT_BINDINGS.get(kind)
                if supported_paths is None or target_path not in supported_paths:
                    reasons.append(
                        "umg_component_property_binding_runtime_unsupported:"
                        f"{kind or 'missing'}:{target_path or 'missing'}"
                    )
        properties_by_component[component_id] = property_specs

        raw_slots = component.get("Slots")
        if not isinstance(raw_slots, list):
            reasons.append("umg_component_slots_record_invalid")
            raw_slots = []
        slot_names: set[str] = set()
        for slot in raw_slots:
            if not isinstance(slot, Mapping):
                reasons.append("umg_component_slot_record_invalid")
                continue
            slot_name = str(slot.get("Name") or "")
            slot_layer_id = str(slot.get("LayerId") or "")
            if not slot_name:
                reasons.append("umg_component_slot_name_missing")
            if slot_name in slot_names:
                reasons.append("umg_component_slot_name_duplicate")
            slot_names.add(slot_name)
            if slot_layer_id not in local_ids:
                reasons.append("umg_component_slot_layer_missing")
            if not isinstance(slot.get("ExposeOnInstanceOnly"), bool):
                reasons.append("umg_component_slot_exposure_invalid")
        slots_by_component[component_id] = slot_names

    for (
        target_component_id,
        marker_property_values,
        slot_contents,
        owner_layer_ids,
    ) in nested_markers:
        property_specs = properties_by_component.get(target_component_id, {})
        variant_values = variants_by_component.get(target_component_id, {})
        allowed_property_names = {
            *property_specs,
            *variant_values,
            *slots_by_component.get(target_component_id, set()),
        }
        if any(
            name not in allowed_property_names
            for name in marker_property_values
        ):
            reasons.append("umg_component_instance_property_name_unknown")
        for name, value in marker_property_values.items():
            spec = property_specs.get(str(name))
            if spec is None:
                continue
            kind = str(spec["type"])
            if kind == "text" and not isinstance(value, str):
                reasons.append("umg_component_instance_text_value_invalid")
            elif kind == "boolean" and not isinstance(value, bool):
                reasons.append("umg_component_instance_boolean_value_invalid")
            elif kind == "number" and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                reasons.append("umg_component_instance_number_value_invalid")
            elif kind in {"enum", "instance_swap"} and not isinstance(
                value, str
            ):
                reasons.append("umg_component_instance_string_value_invalid")
            if (
                kind == "enum"
                and spec["values"]
                and str(value) not in spec["values"]
            ):
                reasons.append("umg_component_instance_enum_value_invalid")
        if any(
            marker_property_values.get(name) != value
            for name, value in variant_values.items()
        ):
            reasons.append("umg_component_instance_variant_tuple_mismatch")
        seen_slots: set[str] = set()
        for slot in slot_contents:
            if not isinstance(slot, Mapping):
                reasons.append("umg_nested_component_slot_content_invalid")
                continue
            slot_name = str(slot.get("SlotName") or "")
            if slot_name in seen_slots:
                reasons.append("umg_nested_component_slot_content_duplicate")
            seen_slots.add(slot_name)
            if slot_name not in slots_by_component.get(
                target_component_id, set()
            ):
                reasons.append("umg_nested_component_slot_missing")
            roots = _string_list(slot.get("RootLayerIds"))
            if roots is None:
                reasons.append("umg_nested_component_slot_roots_invalid")
            elif any(root not in owner_layer_ids for root in roots):
                reasons.append("umg_nested_component_slot_root_missing")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(component_id: str) -> None:
        if component_id in visited:
            return
        if component_id in visiting:
            reasons.append("umg_component_dependency_cycle")
            return
        visiting.add(component_id)
        for dependency in dependency_graph.get(component_id, []):
            visit(dependency)
        visiting.remove(component_id)
        visited.add(component_id)

    for component_id in dependency_graph:
        visit(component_id)

    instances = list(records["component_instances"])
    instance_ids: set[str] = set()
    implicit_definition_placement_ids: set[str] = set()
    for instance in instances:
        instance_id = str(instance.get("Id") or "")
        component_id = str(instance.get("ComponentId") or "")
        layer_id = str(instance.get("LayerId") or "")
        parent_id = str(instance.get("ParentId") or "")
        if not instance_id or instance_id in instance_ids:
            reasons.append(
                "umg_component_instance_id_missing"
                if not instance_id
                else "umg_component_instance_id_duplicate"
            )
        instance_ids.add(instance_id)
        if component_id not in component_id_set:
            reasons.append("umg_component_instance_component_missing")
        if not layer_id or layer_id not in screen_layer_ids:
            reasons.append("umg_component_instance_layer_missing")
        if instance_id != layer_id:
            reasons.append("umg_component_instance_stable_id_mismatch")
        if parent_id and parent_id not in screen_layer_ids:
            reasons.append("umg_component_instance_parent_missing")
        property_values = _json_object(instance.get("PropertyValuesJson"))
        if property_values is None:
            reasons.append("umg_component_instance_property_values_json_invalid")
            property_values = {}
        property_specs = properties_by_component.get(component_id, {})
        variant_values = variants_by_component.get(component_id, {})
        allowed_property_names = {
            *property_specs,
            *variant_values,
            *slots_by_component.get(component_id, set()),
        }
        if any(name not in allowed_property_names for name in property_values):
            reasons.append("umg_component_instance_property_name_unknown")
        for name, value in property_values.items():
            spec = property_specs.get(str(name))
            if spec is None:
                continue
            kind = str(spec["type"])
            if kind == "text" and not isinstance(value, str):
                reasons.append("umg_component_instance_text_value_invalid")
            elif kind == "boolean" and not isinstance(value, bool):
                reasons.append("umg_component_instance_boolean_value_invalid")
            elif kind == "number" and (
                not isinstance(value, (int, float)) or isinstance(value, bool)
            ):
                reasons.append("umg_component_instance_number_value_invalid")
            elif kind in {"enum", "instance_swap"} and not isinstance(
                value, str
            ):
                reasons.append("umg_component_instance_string_value_invalid")
            if (
                kind == "enum"
                and spec["values"]
                and str(value) not in spec["values"]
            ):
                reasons.append("umg_component_instance_enum_value_invalid")
        if any(
            property_values.get(name) != value
            for name, value in variant_values.items()
        ):
            reasons.append("umg_component_instance_variant_tuple_mismatch")
        if _json_object(instance.get("ResolvedOverridesJson")) is None:
            reasons.append("umg_component_instance_overrides_json_invalid")
        is_implicit_definition_placement = bool(
            definition_layer_owner.get(layer_id) == component_id
            and component_root_by_id.get(component_id) == layer_id
        )
        if is_implicit_definition_placement:
            implicit_definition_placement_ids.add(layer_id)
            expected_defaults = {
                name: property_spec["default"]
                for name, property_spec in property_specs.items()
            }
            expected_defaults.update(variant_values)
            if dict(property_values) != expected_defaults:
                reasons.append(
                    "umg_implicit_component_property_values_not_default"
                )
        slot_contents = instance.get("SlotContents")
        if not isinstance(slot_contents, list):
            reasons.append("umg_component_instance_slot_contents_record_invalid")
            slot_contents = []
        seen_slots: set[str] = set()
        for slot in slot_contents:
            if not isinstance(slot, Mapping):
                reasons.append("umg_component_instance_slot_content_record_invalid")
                continue
            slot_name = str(slot.get("SlotName") or "")
            if slot_name in seen_slots:
                reasons.append("umg_component_instance_slot_content_duplicate")
            seen_slots.add(slot_name)
            if slot_name not in slots_by_component.get(component_id, set()):
                reasons.append("umg_component_instance_slot_missing")
            roots = _string_list(slot.get("RootLayerIds"))
            if roots is None:
                reasons.append("umg_component_instance_slot_roots_invalid")
            elif any(root not in screen_layer_ids for root in roots):
                reasons.append("umg_component_instance_slot_root_missing")
    leaked_definition_ids = (
        definition_layer_ids.intersection(screen_layer_ids)
        - implicit_definition_placement_ids
    )
    if leaked_definition_ids:
        reasons.append("umg_component_definition_layer_leaked_to_screen")
    return sorted(set(reasons))


__all__ = [
    "TIGER_UMG_COMPONENT_DOCUMENT_SCHEMA_VERSION",
    "UMG_COMPONENT_PROPERTY_TYPES",
    "UMG_STATIC_COMPONENT_BINDINGS",
    "inspect_umg_component_records",
    "validate_umg_component_contract",
]
