"""Component definition and instance services for Painter UI documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping


UI_COMPONENT_ROLES = ("none", "definition", "instance")
UI_COMPONENT_STATES = (
    "normal",
    "hover",
    "pressed",
    "focused",
    "disabled",
    "selected",
)
_STRUCTURAL_FIELDS = {
    "id",
    "artboard_id",
    "parent_id",
    "z_index",
    "component_id",
    "component_role",
    "component_source_object_id",
    "instance_overrides",
    "component_properties",
    "component_property_bindings",
    "component_scope_id",
    "component_scope_source_object_id",
}


def normalize_ui_component_role(value: object) -> str:
    role = str(value or "none").strip().casefold()
    return role if role in UI_COMPONENT_ROLES else "none"


def normalize_ui_instance_overrides(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(path): copy.deepcopy(item)
        for path, item in value.items()
        if str(path or "").strip()
    }


def normalize_ui_component_properties(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(name): copy.deepcopy(item)
        for name, item in value.items()
        if str(name or "").strip()
    }


def normalize_ui_component_property_bindings(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(path): str(property_name)
        for path, property_name in value.items()
        if str(path or "").strip() and str(property_name or "").strip()
    }


def normalize_ui_component_property_definitions(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    definitions: dict[str, Any] = {}
    for name, raw in value.items():
        property_name = str(name or "").strip()
        if not property_name:
            continue
        row = dict(raw) if isinstance(raw, Mapping) else {"default": raw}
        property_type = str(row.get("type") or "text").strip().casefold()
        values = [
            str(item)
            for item in row.get("values", [])
            if str(item or "").strip()
        ]
        if property_type == "enum" and not values:
            values = list(UI_COMPONENT_STATES) if property_name == "state" else []
        default = copy.deepcopy(row.get("default"))
        if default is None and values:
            default = values[0]
        definitions[property_name] = {
            "type": property_type,
            "default": default,
            "values": values,
            "description": str(row.get("description") or ""),
        }
    return definitions


def default_ui_component_property_definitions() -> dict[str, Any]:
    return {
        "state": {
            "type": "enum",
            "default": "normal",
            "values": list(UI_COMPONENT_STATES),
            "description": "Interactive component state",
        }
    }


def normalize_ui_component_state_overrides(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, Any] = {}
    for state, source_rows in value.items():
        state_name = str(state or "").strip().casefold()
        if not state_name or not isinstance(source_rows, Mapping):
            continue
        result[state_name] = {
            str(source_id): copy.deepcopy(dict(changes))
            for source_id, changes in source_rows.items()
            if str(source_id or "").strip() and isinstance(changes, Mapping)
        }
    return result


def component_property_defaults(component: Mapping[str, Any]) -> dict[str, Any]:
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    return {
        name: copy.deepcopy(row.get("default"))
        for name, row in definitions.items()
    }


def _component_family_id(component: Mapping[str, Any]) -> str:
    return str(component.get("base_component_id") or component.get("id") or "")


def _component_source_map(
    document: Mapping[str, Any],
    component: Mapping[str, Any],
) -> dict[str, str]:
    metadata = component.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    stored = metadata.get("variant_source_map")
    if isinstance(stored, Mapping):
        result = {
            str(canonical_id): str(source_id)
            for canonical_id, source_id in stored.items()
            if str(canonical_id or "") and str(source_id or "")
        }
        if result:
            return result
    root_id = str(component.get("root_object_id") or "")
    objects = {row["id"]: row for row in document["objects"]}
    result: dict[str, str] = {}

    def visit(source_id: str, path: str) -> None:
        result[path] = source_id
        children = [
            row
            for row in document["objects"]
            if str(row.get("parent_id") or "") == source_id
        ]
        children.sort(
            key=lambda row: (int(row.get("z_index") or 0), str(row["id"]))
        )
        for index, child in enumerate(children):
            visit(str(child["id"]), f"{path}/{index}")

    if root_id in objects:
        visit(root_id, "root")
    return result


def _next_id(prefix: str, rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    return f"{prefix}-{serial}"


def _subtree_ids(document: Mapping[str, Any], root_id: str) -> list[str]:
    children: dict[str, list[Mapping[str, Any]]] = {}
    for row in document["objects"]:
        children.setdefault(str(row.get("parent_id") or ""), []).append(row)
    for rows in children.values():
        rows.sort(key=lambda item: (int(item.get("z_index") or 0), str(item["id"])))
    ordered: list[str] = []

    def visit(object_id: str) -> None:
        ordered.append(object_id)
        for child in children.get(object_id, []):
            visit(str(child["id"]))

    visit(str(root_id))
    return ordered


def _component_scope_source_id(
    row: Mapping[str, Any],
    component_id: str,
) -> str:
    if str(row.get("component_scope_id") or "") == str(component_id):
        return str(row.get("component_scope_source_object_id") or "")
    return str(row.get("component_source_object_id") or "")


def _nested_instance_ancestor(
    row: Mapping[str, Any],
    objects: Mapping[str, Mapping[str, Any]],
    *,
    outer_component_id: str,
    outer_root_id: str,
) -> Mapping[str, Any] | None:
    current: Mapping[str, Any] | None = row
    while current is not None and str(current.get("id") or "") != outer_root_id:
        if (
            str(current.get("component_role") or "") == "instance"
            and str(current.get("component_id") or "") != outer_component_id
        ):
            return current
        current = objects.get(str(current.get("parent_id") or ""))
    return None


def _flatten_changes(
    value: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key)
        if not prefix and name in _STRUCTURAL_FIELDS:
            continue
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(item, Mapping) and name in {
            "style",
            "content",
            "layout",
            "constraints",
            "token_bindings",
            "accessibility",
        }:
            flattened.update(_flatten_changes(item, prefix=path))
        else:
            flattened[path] = copy.deepcopy(item)
    return flattened


def merge_ui_instance_overrides(
    row: Mapping[str, Any],
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    overrides = normalize_ui_instance_overrides(row.get("instance_overrides"))
    overrides.update(_flatten_changes(changes))
    return overrides


def _apply_path(row: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in str(path).split(".") if part]
    if not parts or parts[0] in _STRUCTURAL_FIELDS:
        return
    target = row
    for part in parts[:-1]:
        current = target.get(part)
        if not isinstance(current, Mapping):
            current = {}
        else:
            current = dict(current)
        target[part] = current
        target = current
    target[parts[-1]] = copy.deepcopy(value)


def apply_ui_instance_overrides(row: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(row))
    for path, value in normalize_ui_instance_overrides(
        row.get("instance_overrides")
    ).items():
        _apply_path(result, path, value)
    return result


def convert_ui_object_to_component(
    value: Mapping[str, Any],
    *,
    root_object_id: str,
    name: str = "",
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_component,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    objects = {row["id"]: row for row in document["objects"]}
    root = objects.get(str(root_object_id))
    if root is None:
        raise PainterUIDocumentError(f"UI object not found: {root_object_id}")
    if root["component_role"] == "instance":
        raise PainterUIDocumentError("A component instance cannot become a definition")
    if root["component_role"] == "definition" and root["component_id"]:
        component = next(
            row
            for row in document["components"]
            if row["id"] == root["component_id"]
        )
        return document, copy.deepcopy(component)

    document, component = add_ui_component(
        document,
        name=name or str(root["name"]),
        root_object_id=str(root_object_id),
        description=description,
        property_definitions=default_ui_component_property_definitions(),
    )
    member_ids = set(_subtree_ids(document, str(root_object_id)))
    original_objects = {
        row["id"]: copy.deepcopy(row) for row in document["objects"]
    }
    for row in document["objects"]:
        if row["id"] not in member_ids:
            continue
        nested = _nested_instance_ancestor(
            original_objects[row["id"]],
            original_objects,
            outer_component_id=component["id"],
            outer_root_id=str(root_object_id),
        )
        if nested is not None:
            row["component_scope_id"] = component["id"]
            row["component_scope_source_object_id"] = row["id"]
            continue
        row["component_id"] = component["id"]
        row["component_role"] = "definition"
        row["component_source_object_id"] = row["id"]
        row["component_scope_id"] = ""
        row["component_scope_source_object_id"] = ""
        row["instance_overrides"] = {}
        row["component_properties"] = {}
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component definition: " + ", ".join(validation["errors"])
        )
    document["selection"] = {
        "object_id": str(root_object_id),
        "object_ids": [str(root_object_id)],
    }
    return document, copy.deepcopy(component)


def instantiate_ui_component(
    value: Mapping[str, Any],
    *,
    component_id: str,
    artboard_id: str = "",
    x: float | None = None,
    y: float | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    component = next(
        (row for row in document["components"] if row["id"] == component_id),
        None,
    )
    if component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    objects = {row["id"]: row for row in document["objects"]}
    source_root = objects.get(component["root_object_id"])
    if source_root is None:
        raise PainterUIDocumentError(
            f"UI component root not found: {component['root_object_id']}"
        )
    target_artboard = str(artboard_id or document["active_artboard_id"])
    if target_artboard not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target_artboard}")

    source_ids = _subtree_ids(document, source_root["id"])
    source_rows = [objects[object_id] for object_id in source_ids]
    id_map: dict[str, str] = {}
    existing = list(document["objects"])
    for source in source_rows:
        new_id = _next_id("ui-object", existing)
        id_map[source["id"]] = new_id
        existing.append({"id": new_id})

    target_x = float(source_root["x"]) + 32.0 if x is None else float(x)
    target_y = float(source_root["y"]) + 32.0 if y is None else float(y)
    offset_x = target_x - float(source_root["x"])
    offset_y = target_y - float(source_root["y"])
    created: list[dict[str, Any]] = []
    next_z = max(
        [int(row["z_index"]) for row in document["objects"]] or [-1]
    ) + 1
    for source in source_rows:
        clone = copy.deepcopy(source)
        clone["id"] = id_map[source["id"]]
        clone["artboard_id"] = target_artboard
        clone["parent_id"] = id_map.get(source["parent_id"], "")
        clone["x"] = float(source["x"]) + offset_x
        clone["y"] = float(source["y"]) + offset_y
        clone["z_index"] = next_z
        next_z += 1
        nested = _nested_instance_ancestor(
            source,
            objects,
            outer_component_id=component_id,
            outer_root_id=source_root["id"],
        )
        if nested is not None:
            clone["component_scope_id"] = component_id
            clone["component_scope_source_object_id"] = source["id"]
        else:
            clone["component_id"] = component_id
            clone["component_role"] = "instance"
            clone["component_source_object_id"] = source["id"]
            clone["component_scope_id"] = ""
            clone["component_scope_source_object_id"] = ""
        clone["instance_overrides"] = {}
        clone["component_property_bindings"] = {}
        clone["component_properties"] = (
            component_property_defaults(component)
            if source["id"] == source_root["id"]
            else {}
        )
        if source["id"] == source_root["id"]:
            clone["name"] = f"{component['name']} Instance"
        created.append(clone)
    document["objects"].extend(created)
    root_id = id_map[source_root["id"]]
    document["selection"] = {"object_id": root_id, "object_ids": [root_id]}
    document["revision"] += 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component instance: " + ", ".join(validation["errors"])
        )
    return document, {
        "component_id": component_id,
        "root_object_id": root_id,
        "object_ids": [id_map[source_id] for source_id in source_ids],
    }


def sync_ui_component_instances(
    value: Mapping[str, Any],
    component_id: str,
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value) if normalize else copy.deepcopy(dict(value))
    component = next(
        (row for row in document["components"] if row["id"] == component_id),
        None,
    )
    if component is None:
        return document
    objects = {row["id"]: row for row in document["objects"]}
    source_root = objects.get(component["root_object_id"])
    if source_root is None:
        return document
    source_ids = _subtree_ids(document, source_root["id"])
    sources = {
        object_id: objects[object_id]
        for object_id in source_ids
        if object_id in objects
    }
    instance_roots = [
        row
        for row in document["objects"]
        if row["component_id"] == component_id
        and row["component_role"] == "instance"
        and row["component_source_object_id"] == source_root["id"]
    ]
    for instance_root in instance_roots:
        by_id = {row["id"]: index for index, row in enumerate(document["objects"])}
        member_ids = _subtree_ids(document, instance_root["id"])
        members: dict[str, dict[str, Any]] = {}
        for object_id in member_ids:
            if object_id not in by_id:
                continue
            member = document["objects"][by_id[object_id]]
            source_key = _component_scope_source_id(member, component_id)
            if source_key:
                members[source_key] = member
        stale_ids = {
            row["id"]
            for source_id, row in members.items()
            if source_id not in sources
        }
        if stale_ids:
            document["objects"] = [
                row for row in document["objects"] if row["id"] not in stale_ids
            ]
            members = {
                source_id: row
                for source_id, row in members.items()
                if source_id in sources
            }
        offset_x = float(instance_root["x"]) - float(source_root["x"])
        offset_y = float(instance_root["y"]) - float(source_root["y"])
        for source_id in source_ids:
            source = sources[source_id]
            instance = members.get(source_id)
            if instance is None:
                new_id = _next_id("ui-object", document["objects"])
                instance = copy.deepcopy(source)
                instance["id"] = new_id
                instance["artboard_id"] = instance_root["artboard_id"]
                source_parent_id = str(source["parent_id"] or "")
                instance["parent_id"] = (
                    members[source_parent_id]["id"]
                    if source_parent_id in members
                    else instance_root["id"]
                )
                instance["z_index"] = (
                    max(
                        [int(row["z_index"]) for row in document["objects"]]
                        or [-1]
                    )
                    + 1
                )
                instance["component_id"] = component_id
                instance["component_role"] = "instance"
                instance["component_source_object_id"] = source_id
                instance["component_scope_id"] = ""
                instance["component_scope_source_object_id"] = ""
                nested = _nested_instance_ancestor(
                    source,
                    sources,
                    outer_component_id=component_id,
                    outer_root_id=source_root["id"],
                )
                if nested is not None:
                    instance["component_id"] = source["component_id"]
                    instance["component_role"] = source["component_role"]
                    instance["component_source_object_id"] = source[
                        "component_source_object_id"
                    ]
                    instance["component_scope_id"] = component_id
                    instance["component_scope_source_object_id"] = source_id
                instance["instance_overrides"] = {}
                instance["component_properties"] = {}
                document["objects"].append(instance)
                members[source_id] = instance
            preserved = {
                key: copy.deepcopy(instance[key])
                for key in _STRUCTURAL_FIELDS
                if key in instance
            }
            synced = copy.deepcopy(source)
            synced.update(preserved)
            synced["x"] = float(source["x"]) + offset_x
            synced["y"] = float(source["y"]) + offset_y
            if source_id == source_root["id"]:
                synced["name"] = instance["name"]
            synced = apply_ui_instance_overrides(synced)
            by_id = {
                row["id"]: index for index, row in enumerate(document["objects"])
            }
            document["objects"][by_id[instance["id"]]] = synced
    return document


def create_ui_component_variant(
    value: Mapping[str, Any],
    *,
    component_id: str,
    name: str = "",
    offset_x: float | None = None,
    variant_key: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        add_ui_component,
        normalize_ui_document,
        update_ui_component,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    components = {row["id"]: row for row in document["components"]}
    source_component = components.get(str(component_id))
    if source_component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    family_id = _component_family_id(source_component)
    family = components.get(family_id)
    if family is None:
        raise PainterUIDocumentError(f"UI component family not found: {family_id}")
    objects = {row["id"]: row for row in document["objects"]}
    source_root = objects.get(source_component["root_object_id"])
    if source_root is None:
        raise PainterUIDocumentError(
            f"UI component root not found: {source_component['root_object_id']}"
        )
    source_ids = _subtree_ids(document, source_root["id"])
    id_map: dict[str, str] = {}
    reserved = list(document["objects"])
    for source_id in source_ids:
        new_id = _next_id("ui-object", reserved)
        id_map[source_id] = new_id
        reserved.append({"id": new_id})
    delta_x = (
        float(offset_x)
        if offset_x is not None
        else float(source_root["width"]) + 48.0
    )
    created: list[dict[str, Any]] = []
    variant_bindings: dict[str, dict[str, str]] = {}
    for source_id in source_ids:
        clone = copy.deepcopy(objects[source_id])
        clone["id"] = id_map[source_id]
        clone["parent_id"] = id_map.get(str(clone["parent_id"]), "")
        clone["x"] = float(clone["x"]) + delta_x
        clone["component_id"] = ""
        clone["component_role"] = "none"
        clone["component_source_object_id"] = ""
        clone["instance_overrides"] = {}
        clone["component_properties"] = {}
        variant_bindings[clone["id"]] = (
            normalize_ui_component_property_bindings(
                clone.get("component_property_bindings")
            )
        )
        clone["component_property_bindings"] = {}
        created.append(clone)
    document["objects"].extend(created)

    source_map = _component_source_map(document, source_component)
    inverse_source_map = {
        source_id: canonical_id
        for canonical_id, source_id in source_map.items()
    }
    variant_source_map = {
        inverse_source_map[source_id]: id_map[source_id]
        for source_id in source_ids
        if source_id in inverse_source_map
    }
    metadata = copy.deepcopy(dict(source_component.get("metadata") or {}))
    metadata["variant_key"] = str(
        variant_key or name or f"Variant {len(family['variant_ids']) + 1}"
    )
    metadata["variant_source_map"] = variant_source_map
    state_overrides: dict[str, Any] = {}
    for state, source_rows in normalize_ui_component_state_overrides(
        source_component.get("state_overrides")
    ).items():
        state_overrides[state] = {
            id_map[source_id]: copy.deepcopy(changes)
            for source_id, changes in source_rows.items()
            if source_id in id_map
        }
    document, variant = add_ui_component(
        document,
        name=name or f"{family['name']} Variant {len(family['variant_ids']) + 1}",
        root_object_id=id_map[source_root["id"]],
        base_component_id=family_id,
        description=str(source_component.get("description") or ""),
        property_definitions=source_component["property_definitions"],
    )
    created_ids = set(id_map.values())
    for row in document["objects"]:
        if row["id"] not in created_ids:
            continue
        row["component_id"] = variant["id"]
        row["component_role"] = "definition"
        row["component_source_object_id"] = row["id"]
        row["component_property_bindings"] = copy.deepcopy(
            variant_bindings.get(row["id"], {})
        )
    document, variant = update_ui_component(
        document,
        variant["id"],
        {
            "metadata": metadata,
            "state_overrides": state_overrides,
        },
    )
    family_variants = list(family["variant_ids"])
    if variant["id"] not in family_variants:
        family_variants.append(variant["id"])
    document, _family = update_ui_component(
        document,
        family_id,
        {"variant_ids": family_variants},
    )
    document["selection"] = {
        "object_id": variant["root_object_id"],
        "object_ids": [variant["root_object_id"]],
    }
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component variant: " + ", ".join(validation["errors"])
        )
    return document, copy.deepcopy(variant)


def switch_ui_component_instance_variant(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
    target_component_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    components = {row["id"]: row for row in document["components"]}
    objects = {row["id"]: row for row in document["objects"]}
    instance_root = objects.get(str(instance_root_id))
    if instance_root is None or instance_root["component_role"] != "instance":
        raise PainterUIDocumentError(
            f"Component instance not found: {instance_root_id}"
        )
    current_component = components.get(instance_root["component_id"])
    target_component = components.get(str(target_component_id))
    if current_component is None or target_component is None:
        raise PainterUIDocumentError("Component variant target is missing")
    nested_scope_id = str(instance_root.get("component_scope_id") or "")
    if (
        not nested_scope_id
        and _component_family_id(current_component) != _component_family_id(
            target_component
        )
    ):
        raise PainterUIDocumentError("Component variants belong to different families")
    target_root = objects.get(target_component["root_object_id"])
    if target_root is None:
        raise PainterUIDocumentError("Target component root is missing")

    current_map = _component_source_map(document, current_component)
    current_inverse = {
        source_id: canonical_id
        for canonical_id, source_id in current_map.items()
    }
    target_map = _component_source_map(document, target_component)
    target_inverse = {
        source_id: canonical_id
        for canonical_id, source_id in target_map.items()
    }
    member_ids = _subtree_ids(document, instance_root["id"])
    members_by_canonical = {
        current_inverse[row["component_source_object_id"]]: row
        for object_id in member_ids
        if (row := objects.get(object_id)) is not None
        and row["component_source_object_id"] in current_inverse
    }
    target_source_ids = _subtree_ids(document, target_root["id"])
    target_sources = {source_id: objects[source_id] for source_id in target_source_ids}
    instance_id_by_canonical = {
        canonical_id: row["id"]
        for canonical_id, row in members_by_canonical.items()
    }
    for source_id in target_source_ids:
        canonical_id = target_inverse.get(source_id)
        if canonical_id and canonical_id not in instance_id_by_canonical:
            instance_id_by_canonical[canonical_id] = _next_id(
                "ui-object",
                [
                    *document["objects"],
                    *({"id": value} for value in instance_id_by_canonical.values()),
                ],
            )

    offset_x = float(instance_root["x"]) - float(target_root["x"])
    offset_y = float(instance_root["y"]) - float(target_root["y"])
    replacement: list[dict[str, Any]] = []
    next_z = max(
        [int(row["z_index"]) for row in document["objects"]] or [-1]
    ) + 1
    for source_id in target_source_ids:
        canonical_id = target_inverse.get(source_id)
        if not canonical_id:
            continue
        source = target_sources[source_id]
        existing = members_by_canonical.get(canonical_id)
        row = copy.deepcopy(source)
        row["id"] = instance_id_by_canonical[canonical_id]
        parent_source = str(source["parent_id"] or "")
        parent_canonical = target_inverse.get(parent_source, "")
        row["parent_id"] = instance_id_by_canonical.get(parent_canonical, "")
        if source_id == target_root["id"] and nested_scope_id:
            row["parent_id"] = str(instance_root.get("parent_id") or "")
        row["artboard_id"] = instance_root["artboard_id"]
        row["z_index"] = int(existing["z_index"]) if existing else next_z
        if existing is None:
            next_z += 1
        row["x"] = float(source["x"]) + offset_x
        row["y"] = float(source["y"]) + offset_y
        row["component_id"] = target_component["id"]
        row["component_role"] = "instance"
        row["component_source_object_id"] = source_id
        row["component_scope_id"] = nested_scope_id
        row["component_scope_source_object_id"] = (
            str((existing or {}).get("component_scope_source_object_id") or "")
            if nested_scope_id
            else ""
        )
        row["instance_overrides"] = copy.deepcopy(
            (existing or {}).get("instance_overrides") or {}
        )
        row["component_property_bindings"] = {}
        row["component_properties"] = {}
        if source_id == target_root["id"]:
            row["name"] = str(instance_root["name"])
            properties = component_property_defaults(target_component)
            properties.update(
                {
                    key: copy.deepcopy(item)
                    for key, item in normalize_ui_component_properties(
                        instance_root.get("component_properties")
                    ).items()
                    if key in target_component["property_definitions"]
                }
            )
            row["component_properties"] = properties
        replacement.append(apply_ui_instance_overrides(row))
    old_member_ids = set(member_ids)
    document["objects"] = [
        row for row in document["objects"] if row["id"] not in old_member_ids
    ]
    document["objects"].extend(replacement)
    document["selection"] = {
        "object_id": str(instance_root_id),
        "object_ids": [str(instance_root_id)],
    }
    document["revision"] += 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component variant switch: " + ", ".join(validation["errors"])
        )
    return document, {
        "root_object_id": str(instance_root_id),
        "component_id": target_component["id"],
        "object_ids": [row["id"] for row in replacement],
    }


def detach_ui_component_instance(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
    create_local_component: bool = False,
    name: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    objects = {row["id"]: row for row in document["objects"]}
    root = objects.get(str(instance_root_id))
    if root is None or root["component_role"] != "instance":
        raise PainterUIDocumentError(
            f"Component instance not found: {instance_root_id}"
        )
    member_ids = _subtree_ids(document, root["id"])
    resolved = {
        row["id"]: row
        for row in resolve_ui_component_document(document)["objects"]
    }
    for index, row in enumerate(document["objects"]):
        if row["id"] not in member_ids:
            continue
        local = copy.deepcopy(resolved[row["id"]])
        local.pop("resolved_component_properties", None)
        local.pop("resolved_component_state", None)
        local["component_id"] = ""
        local["component_role"] = "none"
        local["component_source_object_id"] = ""
        local["instance_overrides"] = {}
        local["component_properties"] = {}
        document["objects"][index] = local
    document["selection"] = {
        "object_id": str(instance_root_id),
        "object_ids": [str(instance_root_id)],
    }
    document["revision"] += 1
    local_component: dict[str, Any] | None = None
    if create_local_component:
        document, local_component = convert_ui_object_to_component(
            document,
            root_object_id=str(instance_root_id),
            name=name or f"{root['name']} Local",
        )
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid detached component instance: "
            + ", ".join(validation["errors"])
        )
    return document, {
        "root_object_id": str(instance_root_id),
        "object_ids": member_ids,
        "local_component_id": (
            str(local_component["id"]) if local_component is not None else ""
        ),
    }


def define_ui_component_property(
    value: Mapping[str, Any],
    *,
    component_id: str,
    property_name: str,
    definition: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    component = next(
        (row for row in document["components"] if row["id"] == component_id),
        None,
    )
    if component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    definitions[str(property_name)] = dict(definition)
    component["property_definitions"] = normalize_ui_component_property_definitions(
        definitions
    )
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component property: " + ", ".join(validation["errors"])
        )
    document["revision"] += 1
    return document, copy.deepcopy(component["property_definitions"][str(property_name)])


def bind_ui_component_property(
    value: Mapping[str, Any],
    *,
    component_id: str,
    source_object_id: str,
    property_name: str,
    target_path: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    component = next(
        (row for row in document["components"] if row["id"] == component_id),
        None,
    )
    if component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    if str(property_name) not in component["property_definitions"]:
        raise PainterUIDocumentError(
            f"Component property not found: {property_name}"
        )
    member_ids = set(_subtree_ids(document, component["root_object_id"]))
    source = next(
        (
            row
            for row in document["objects"]
            if row["id"] == source_object_id and row["id"] in member_ids
        ),
        None,
    )
    if source is None:
        raise PainterUIDocumentError(
            f"Component source object not found: {source_object_id}"
        )
    bindings = normalize_ui_component_property_bindings(
        source.get("component_property_bindings")
    )
    bindings[str(target_path)] = str(property_name)
    source["component_property_bindings"] = bindings
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component property binding: "
            + ", ".join(validation["errors"])
        )
    document["revision"] += 1
    return document, copy.deepcopy(bindings)


def set_ui_component_state_override(
    value: Mapping[str, Any],
    *,
    component_id: str,
    state: str,
    source_object_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    component = next(
        (row for row in document["components"] if row["id"] == component_id),
        None,
    )
    if component is None:
        raise PainterUIDocumentError(f"UI component not found: {component_id}")
    source = next(
        (
            row
            for row in document["objects"]
            if row["id"] == source_object_id
            and row["component_id"] == component_id
            and row["component_role"] == "definition"
        ),
        None,
    )
    if source is None:
        raise PainterUIDocumentError(
            f"Component source object not found: {source_object_id}"
        )
    state_name = str(state or "normal").strip().casefold()
    overrides = normalize_ui_component_state_overrides(
        component.get("state_overrides")
    )
    overrides.setdefault(state_name, {})[str(source_object_id)] = copy.deepcopy(
        dict(changes)
    )
    component["state_overrides"] = overrides
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component state override: " + ", ".join(validation["errors"])
        )
    document["revision"] += 1
    return document, copy.deepcopy(overrides[state_name][str(source_object_id)])


def set_ui_instance_component_property(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
    property_name: str,
    property_value: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    root = next(
        (row for row in document["objects"] if row["id"] == instance_root_id),
        None,
    )
    if root is None or root["component_role"] != "instance":
        raise PainterUIDocumentError(f"Component instance not found: {instance_root_id}")
    component = next(
        row for row in document["components"] if row["id"] == root["component_id"]
    )
    definitions = normalize_ui_component_property_definitions(
        component.get("property_definitions")
    )
    definition = definitions.get(str(property_name))
    if definition is None:
        raise PainterUIDocumentError(
            f"Component property not found: {property_name}"
        )
    if definition["type"] == "enum" and definition["values"]:
        if str(property_value) not in definition["values"]:
            raise PainterUIDocumentError(
                f"Invalid component property value: {property_name}={property_value}"
            )
    if definition["type"] == "instance_swap" and str(property_value) not in {
        row["id"] for row in document["components"]
    }:
        raise PainterUIDocumentError(
            f"Invalid component swap target: {property_name}={property_value}"
        )
    properties = component_property_defaults(component)
    properties.update(normalize_ui_component_properties(root.get("component_properties")))
    properties[str(property_name)] = copy.deepcopy(property_value)
    root["component_properties"] = properties
    if definition["type"] == "instance_swap":
        component_sources = set(
            _subtree_ids(document, component["root_object_id"])
        )
        bound_source_ids = {
            row["id"]
            for row in document["objects"]
            if row["id"] in component_sources
            and normalize_ui_component_property_bindings(
                row.get("component_property_bindings")
            ).get("component_id")
            == str(property_name)
        }
        nested_roots = [
            row["id"]
            for row in document["objects"]
            if row["id"] in set(_subtree_ids(document, root["id"]))
            and row["component_scope_id"] == component["id"]
            and row["component_scope_source_object_id"] in bound_source_ids
            and row["component_role"] == "instance"
        ]
        for nested_root_id in nested_roots:
            document, _ = switch_ui_component_instance_variant(
                document,
                instance_root_id=nested_root_id,
                target_component_id=str(property_value),
            )
        root = next(
            row for row in document["objects"] if row["id"] == instance_root_id
        )
        root["component_properties"] = properties
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component instance property: " + ", ".join(validation["errors"])
        )
    document["revision"] += 1
    return document, copy.deepcopy(properties)


def inspect_ui_component_instance_overrides(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
) -> dict[str, Any]:
    """Return the explicit local differences for one component instance."""
    from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document

    document = normalize_ui_document(value)
    objects = {row["id"]: row for row in document["objects"]}
    root = objects.get(str(instance_root_id))
    if root is None or root["component_role"] != "instance":
        raise PainterUIDocumentError(
            f"Component instance not found: {instance_root_id}"
        )
    component = next(
        (
            row
            for row in document["components"]
            if row["id"] == root["component_id"]
        ),
        None,
    )
    if (
        component is None
        or root["component_source_object_id"] != component["root_object_id"]
    ):
        raise PainterUIDocumentError(
            f"Component instance root not found: {instance_root_id}"
        )

    overrides: list[dict[str, Any]] = []
    defaults = component_property_defaults(component)
    properties = normalize_ui_component_properties(
        root.get("component_properties")
    )
    for name in sorted(set(defaults) | set(properties)):
        value_item = copy.deepcopy(properties.get(name, defaults.get(name)))
        default_item = copy.deepcopy(defaults.get(name))
        if value_item == default_item:
            continue
        overrides.append(
            {
                "kind": "component_property",
                "object_id": root["id"],
                "object_name": root["name"],
                "property_path": f"component_properties.{name}",
                "label": name,
                "value": value_item,
                "default": default_item,
            }
        )

    for object_id in _subtree_ids(document, root["id"]):
        row = objects.get(object_id)
        if row is None:
            continue
        for path, item in sorted(
            normalize_ui_instance_overrides(
                row.get("instance_overrides")
            ).items()
        ):
            overrides.append(
                {
                    "kind": "object_property",
                    "object_id": row["id"],
                    "object_name": row["name"],
                    "property_path": path,
                    "label": path,
                    "value": copy.deepcopy(item),
                    "default": None,
                }
            )
    return {
        "instance_root_id": root["id"],
        "component_id": component["id"],
        "component_name": component["name"],
        "count": len(overrides),
        "overrides": overrides,
    }


def reset_ui_component_instance_override(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
    object_id: str,
    property_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset one explicit instance override to its component definition."""
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    objects = {row["id"]: row for row in document["objects"]}
    root = objects.get(str(instance_root_id))
    if root is None or root["component_role"] != "instance":
        raise PainterUIDocumentError(
            f"Component instance not found: {instance_root_id}"
        )
    component = next(
        (
            row
            for row in document["components"]
            if row["id"] == root["component_id"]
        ),
        None,
    )
    if (
        component is None
        or root["component_source_object_id"] != component["root_object_id"]
    ):
        raise PainterUIDocumentError(
            f"Component instance root not found: {instance_root_id}"
        )
    path = str(property_path or "").strip()
    target_id = str(object_id or instance_root_id)
    member_ids = set(_subtree_ids(document, root["id"]))
    if target_id not in member_ids:
        raise PainterUIDocumentError(
            f"Object is not in component instance: {target_id}"
        )

    changed = False
    if path.startswith("component_properties."):
        property_name = path.removeprefix("component_properties.")
        defaults = component_property_defaults(component)
        properties = normalize_ui_component_properties(
            root.get("component_properties")
        )
        if property_name in defaults:
            if properties.get(property_name) != defaults[property_name]:
                properties[property_name] = copy.deepcopy(defaults[property_name])
                changed = True
        elif property_name in properties:
            properties.pop(property_name)
            changed = True
        root["component_properties"] = properties
    else:
        target = objects[target_id]
        overrides = normalize_ui_instance_overrides(
            target.get("instance_overrides")
        )
        if path in overrides:
            overrides.pop(path)
            target["instance_overrides"] = overrides
            changed = True
    if not changed:
        raise PainterUIDocumentError(
            f"Component instance override not found: {property_path}"
        )

    document = sync_ui_component_instances(
        document,
        component["id"],
        normalize=False,
    )
    document["selection"] = {
        "object_id": target_id,
        "object_ids": [target_id],
    }
    document["revision"] += 1
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component override reset: "
            + ", ".join(validation["errors"])
        )
    return document, inspect_ui_component_instance_overrides(
        document,
        instance_root_id=root["id"],
    )


def reset_all_ui_component_instance_overrides(
    value: Mapping[str, Any],
    *,
    instance_root_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reset every local property in one instance while keeping it linked."""
    from app.painter_ui_document import (
        PainterUIDocumentError,
        normalize_ui_document,
        validate_ui_document,
    )

    document = normalize_ui_document(value)
    objects = {row["id"]: row for row in document["objects"]}
    root = objects.get(str(instance_root_id))
    if root is None or root["component_role"] != "instance":
        raise PainterUIDocumentError(
            f"Component instance not found: {instance_root_id}"
        )
    component = next(
        (
            row
            for row in document["components"]
            if row["id"] == root["component_id"]
        ),
        None,
    )
    if (
        component is None
        or root["component_source_object_id"] != component["root_object_id"]
    ):
        raise PainterUIDocumentError(
            f"Component instance root not found: {instance_root_id}"
        )
    for object_id in _subtree_ids(document, root["id"]):
        member = objects.get(object_id)
        if member is None:
            continue
        member["instance_overrides"] = {}
        member["component_properties"] = {}
    root["component_properties"] = component_property_defaults(component)
    document = sync_ui_component_instances(
        document,
        component["id"],
        normalize=False,
    )
    document["selection"] = {
        "object_id": root["id"],
        "object_ids": [root["id"]],
    }
    document["revision"] += 1
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid component override reset: "
            + ", ".join(validation["errors"])
        )
    return document, inspect_ui_component_instance_overrides(
        document,
        instance_root_id=root["id"],
    )


def resolve_ui_component_document(
    value: Mapping[str, Any],
    *,
    normalize: bool = True,
) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = (
        normalize_ui_document(value)
        if normalize
        else copy.deepcopy(dict(value))
    )
    components = {row["id"]: row for row in document["components"]}
    objects = {row["id"]: row for row in document["objects"]}
    instance_roots = []
    for row in document["objects"]:
        if row["component_role"] != "instance":
            continue
        component = components.get(row["component_id"])
        if component is None:
            continue
        if row["component_source_object_id"] == component["root_object_id"]:
            instance_roots.append(row)
    for root in instance_roots:
        component = components[root["component_id"]]
        properties = component_property_defaults(component)
        properties.update(
            normalize_ui_component_properties(root.get("component_properties"))
        )
        state = str(properties.get("state") or "normal").strip().casefold()
        state_rows = normalize_ui_component_state_overrides(
            component.get("state_overrides")
        ).get(state, {})
        for object_id in _subtree_ids(document, root["id"]):
            row = objects.get(object_id)
            if row is None:
                continue
            scope_source_id = _component_scope_source_id(
                row,
                component["id"],
            )
            changes = state_rows.get(scope_source_id)
            resolved = copy.deepcopy(row)
            source = objects.get(scope_source_id)
            if source is not None:
                for path, property_name in (
                    normalize_ui_component_property_bindings(
                        source.get("component_property_bindings")
                    ).items()
                ):
                    if (
                        path != "component_id"
                        and property_name in properties
                    ):
                        _apply_path(
                            resolved,
                            path,
                            copy.deepcopy(properties[property_name]),
                        )
            if isinstance(changes, Mapping):
                for path, item in _flatten_changes(changes).items():
                    _apply_path(resolved, path, item)
            resolved = apply_ui_instance_overrides(resolved)
            resolved["resolved_component_properties"] = copy.deepcopy(properties)
            resolved["resolved_component_state"] = state
            objects[object_id] = resolved
    document["objects"] = [objects[row["id"]] for row in document["objects"]]
    return document


__all__ = [
    "bind_ui_component_property",
    "UI_COMPONENT_ROLES",
    "UI_COMPONENT_STATES",
    "apply_ui_instance_overrides",
    "component_property_defaults",
    "convert_ui_object_to_component",
    "create_ui_component_variant",
    "default_ui_component_property_definitions",
    "detach_ui_component_instance",
    "define_ui_component_property",
    "instantiate_ui_component",
    "inspect_ui_component_instance_overrides",
    "merge_ui_instance_overrides",
    "normalize_ui_component_properties",
    "normalize_ui_component_property_bindings",
    "normalize_ui_component_property_definitions",
    "normalize_ui_component_role",
    "normalize_ui_component_state_overrides",
    "normalize_ui_instance_overrides",
    "resolve_ui_component_document",
    "reset_all_ui_component_instance_overrides",
    "reset_ui_component_instance_override",
    "set_ui_component_state_override",
    "set_ui_instance_component_property",
    "switch_ui_component_instance_variant",
    "sync_ui_component_instances",
]
