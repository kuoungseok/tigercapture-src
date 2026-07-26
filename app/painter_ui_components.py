"""Component definition and instance services for Painter UI documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping


UI_COMPONENT_ROLES = ("none", "definition", "instance")
_STRUCTURAL_FIELDS = {
    "id",
    "artboard_id",
    "parent_id",
    "z_index",
    "component_id",
    "component_role",
    "component_source_object_id",
    "instance_overrides",
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
    )
    member_ids = set(_subtree_ids(document, str(root_object_id)))
    for row in document["objects"]:
        if row["id"] not in member_ids:
            continue
        row["component_id"] = component["id"]
        row["component_role"] = "definition"
        row["component_source_object_id"] = row["id"]
        row["instance_overrides"] = {}
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
        clone["component_id"] = component_id
        clone["component_role"] = "instance"
        clone["component_source_object_id"] = source["id"]
        clone["instance_overrides"] = {}
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
        members = {
            document["objects"][by_id[object_id]]["component_source_object_id"]:
            document["objects"][by_id[object_id]]
            for object_id in member_ids
            if object_id in by_id
        }
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
                instance["instance_overrides"] = {}
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


__all__ = [
    "UI_COMPONENT_ROLES",
    "apply_ui_instance_overrides",
    "convert_ui_object_to_component",
    "instantiate_ui_component",
    "merge_ui_instance_overrides",
    "normalize_ui_component_role",
    "normalize_ui_instance_overrides",
    "sync_ui_component_instances",
]
