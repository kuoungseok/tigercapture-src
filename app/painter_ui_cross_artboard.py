"""Cross-artboard duplication for responsive Painter UI authoring."""
from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    validate_ui_document,
)


def _next_stable_id(prefix: str, used: set[str]) -> str:
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    value = f"{prefix}-{serial}"
    used.add(value)
    return value


def _selected_root_ids(
    document: Mapping[str, Any],
    selected_ids: list[str],
) -> list[str]:
    selected = set(selected_ids)
    by_id = {str(row["id"]): row for row in document["objects"]}
    roots: list[str] = []
    for object_id in selected_ids:
        row = by_id.get(object_id)
        if row is None:
            continue
        parent_id = str(row.get("parent_id") or "")
        seen: set[str] = set()
        while parent_id and parent_id not in seen:
            if parent_id in selected:
                break
            seen.add(parent_id)
            parent = by_id.get(parent_id)
            parent_id = str((parent or {}).get("parent_id") or "")
        else:
            roots.append(object_id)
    return roots


def _subtree_ids(
    document: Mapping[str, Any],
    root_ids: list[str],
) -> list[str]:
    included = set(root_ids)
    by_id = {str(row["id"]): row for row in document["objects"]}
    changed = True
    while changed:
        before = len(included)
        included.update(
            str(row["id"])
            for row in document["objects"]
            if str(row.get("parent_id") or "") in included
        )
        for object_id in tuple(included):
            row = by_id.get(object_id, {})
            boolean = (row.get("content") or {}).get("boolean") or {}
            mask = row.get("mask") or {}
            included.update(
                str(item)
                for item in boolean.get("operand_ids", [])
                if str(item) in by_id
            )
            included.update(
                str(item)
                for item in mask.get("target_ids", [])
                if str(item) in by_id
            )
        changed = len(included) != before
    return [
        str(row["id"])
        for row in document["objects"]
        if str(row["id"]) in included
    ]


def _next_artboard_id(
    document: Mapping[str, Any],
    source_artboard_id: str,
) -> str:
    ids = [str(row["id"]) for row in document["artboards"]]
    try:
        index = ids.index(source_artboard_id)
    except ValueError:
        return ""
    return ids[index + 1] if index + 1 < len(ids) else ""


def inspect_cross_artboard_duplicate(
    value: Mapping[str, Any] | None,
    *,
    object_ids: list[str] | None = None,
    target_artboard_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    requested_ids = [
        str(item)
        for item in (
            object_ids
            if object_ids is not None
            else document["selection"]["object_ids"]
        )
        if str(item or "")
    ]
    by_id = {str(row["id"]): row for row in document["objects"]}
    rows = [by_id[item] for item in requested_ids if item in by_id]
    source_ids = {str(row["artboard_id"]) for row in rows}
    reason = ""
    if not rows:
        reason = "select_objects"
    elif len(rows) != len(requested_ids):
        reason = "missing_object"
    elif any(bool(row.get("locked")) for row in rows):
        reason = "locked_object"
    elif len(source_ids) != 1:
        reason = "mixed_artboard"
    source_artboard_id = next(iter(source_ids), "")
    target = str(target_artboard_id or "")
    if not reason and not target:
        target = _next_artboard_id(document, source_artboard_id)
        if not target:
            reason = "no_next_artboard"
    artboards = {
        str(row["id"]): row
        for row in document["artboards"]
    }
    if not reason and target not in artboards:
        reason = "missing_target_artboard"
    if not reason and target == source_artboard_id:
        reason = "same_artboard"
    roots = _selected_root_ids(document, requested_ids) if not reason else []
    subtree = _subtree_ids(document, roots) if roots else []
    target_row = artboards.get(target, {})
    return {
        "schema": "tigerstudio.painter.ui.cross_artboard_duplicate.v1",
        "eligible": not reason,
        "reason": reason,
        "source_artboard_id": source_artboard_id,
        "target_artboard_id": target,
        "target_artboard_name": str(target_row.get("name") or ""),
        "selected_object_ids": requested_ids,
        "root_object_ids": roots,
        "subtree_object_ids": subtree,
    }


def _all_nested_ids(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key == "id" and isinstance(item, str) and item:
                result.add(item)
            result.update(_all_nested_ids(item))
    elif isinstance(value, list):
        for item in value:
            result.update(_all_nested_ids(item))
    return result


def _replace_ids(value: object, id_map: Mapping[str, str]) -> object:
    if isinstance(value, Mapping):
        return {
            key: _replace_ids(item, id_map)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_ids(item, id_map) for item in value]
    if isinstance(value, str):
        return id_map.get(value, value)
    return copy.deepcopy(value)


def duplicate_ui_selection_to_artboard(
    value: Mapping[str, Any] | None,
    *,
    object_ids: list[str] | None = None,
    target_artboard_id: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    inspection = inspect_cross_artboard_duplicate(
        document,
        object_ids=object_ids,
        target_artboard_id=target_artboard_id,
    )
    if not inspection["eligible"]:
        raise PainterUIDocumentError(
            "Cannot duplicate UI selection to artboard: "
            + str(inspection["reason"])
        )

    subtree_ids = list(inspection["subtree_object_ids"])
    subtree_set = set(subtree_ids)
    source_by_id = {
        str(row["id"]): row
        for row in document["objects"]
        if str(row["id"]) in subtree_set
    }
    used_ids = _all_nested_ids(document)
    object_id_map = {
        object_id: _next_stable_id("ui-object", used_ids)
        for object_id in subtree_ids
    }
    nested_id_maps: dict[str, dict[str, str]] = {}
    for object_id in subtree_ids:
        nested_source = {
            nested_id
            for key, item in source_by_id[object_id].items()
            if key != "id"
            for nested_id in _all_nested_ids(item)
            if nested_id not in object_id_map
        }
        nested_id_maps[object_id] = {
            source_id: _next_stable_id("ui-copy", used_ids)
            for source_id in sorted(nested_source)
        }
    target_artboard_id = str(inspection["target_artboard_id"])
    target_focus_orders = {
        int((row.get("accessibility") or {}).get("focus_order") or 0)
        for row in document["objects"]
        if str(row["artboard_id"]) == target_artboard_id
    }
    reset_focus_ids: list[str] = []
    created: list[dict[str, Any]] = []
    next_z = max(
        [int(row.get("z_index") or 0) for row in document["objects"]]
        or [-1]
    ) + 1
    for source_id in subtree_ids:
        source = source_by_id[source_id]
        clone = _replace_ids(
            source,
            {
                **nested_id_maps[source_id],
                **object_id_map,
            },
        )
        assert isinstance(clone, dict)
        clone["id"] = object_id_map[source_id]
        clone["artboard_id"] = target_artboard_id
        clone["parent_id"] = object_id_map.get(
            str(source.get("parent_id") or ""),
            "",
        )
        clone["z_index"] = next_z
        next_z += 1
        if str(source.get("component_role") or "") == "definition":
            clone["component_role"] = "instance"
            clone["component_source_object_id"] = source_id
            clone["component_property_bindings"] = {}
            clone["instance_overrides"] = {}
        elif str(source.get("component_source_object_id") or ""):
            clone["component_source_object_id"] = str(
                source["component_source_object_id"]
            )
        if str(source.get("component_scope_source_object_id") or ""):
            clone["component_scope_source_object_id"] = str(
                source["component_scope_source_object_id"]
            )
        accessibility = dict(clone.get("accessibility") or {})
        focus_order = int(accessibility.get("focus_order") or 0)
        if focus_order > 0 and focus_order in target_focus_orders:
            accessibility["focus_order"] = 0
            reset_focus_ids.append(str(clone["id"]))
        elif focus_order > 0:
            target_focus_orders.add(focus_order)
        clone["accessibility"] = accessibility
        created.append(clone)

    document["objects"].extend(created)
    interaction_id_map: dict[str, str] = {}
    created_interactions: list[dict[str, Any]] = []
    source_artboard_id = str(inspection["source_artboard_id"])
    for source in list(document["interactions"]):
        source_object_id = str(source.get("source_object_id") or "")
        if source_object_id not in object_id_map:
            continue
        clone = copy.deepcopy(source)
        new_id = _next_stable_id("ui-interaction", used_ids)
        interaction_id_map[str(source["id"])] = new_id
        clone["id"] = new_id
        clone["source_object_id"] = object_id_map[source_object_id]
        target_object_id = str(source.get("target_object_id") or "")
        if target_object_id in object_id_map:
            clone["target_object_id"] = object_id_map[target_object_id]
        if str(source.get("target_artboard_id") or "") == source_artboard_id:
            clone["target_artboard_id"] = target_artboard_id
        created_interactions.append(clone)
    document["interactions"].extend(created_interactions)

    new_root_ids = [
        object_id_map[object_id]
        for object_id in inspection["root_object_ids"]
    ]
    document["active_artboard_id"] = target_artboard_id
    document["selection"] = {
        "object_id": new_root_ids[-1],
        "object_ids": new_root_ids,
    }
    document["revision"] = int(document.get("revision") or 0) + 1
    updated = normalize_ui_document(document)
    validation = validate_ui_document(updated)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid cross-artboard duplicate: "
            + ", ".join(validation["errors"])
        )
    return updated, {
        **inspection,
        "created_root_object_ids": new_root_ids,
        "created_object_ids": [
            object_id_map[object_id]
            for object_id in subtree_ids
        ],
        "object_id_map": object_id_map,
        "interaction_id_map": interaction_id_map,
        "focus_order_reset_object_ids": reset_focus_ids,
        "revision": updated["revision"],
    }


__all__ = [
    "duplicate_ui_selection_to_artboard",
    "inspect_cross_artboard_duplicate",
]
