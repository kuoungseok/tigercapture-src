"""Stable-ID-safe same-artboard duplication for Painter UI objects."""
from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from app.painter_ui_cross_artboard import (
    _all_nested_ids,
    _next_stable_id,
    _replace_ids,
    _selected_root_ids,
    _subtree_ids,
)
from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    validate_ui_document,
)


def duplicate_ui_selection(
    value: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
    offset_x: float = 12.0,
    offset_y: float = 12.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Duplicate complete selected hierarchies on their current artboard."""
    document = normalize_ui_document(value)
    requested = [
        str(item)
        for item in (
            object_ids
            if object_ids is not None
            else document["selection"]["object_ids"]
        )
        if str(item)
    ]
    by_id = {str(row["id"]): row for row in document["objects"]}
    selected = [by_id[item] for item in requested if item in by_id]
    if not selected:
        raise PainterUIDocumentError("Cannot duplicate UI selection: no_selection")
    if len(selected) != len(requested):
        raise PainterUIDocumentError("Cannot duplicate UI selection: missing_object")
    if any(bool(row.get("locked")) for row in selected):
        raise PainterUIDocumentError("Cannot duplicate UI selection: locked_object")
    artboard_ids = {str(row["artboard_id"]) for row in selected}
    if len(artboard_ids) != 1:
        raise PainterUIDocumentError("Cannot duplicate UI selection: mixed_artboard")

    root_ids = _selected_root_ids(document, requested)
    subtree_ids = _subtree_ids(document, root_ids)
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

    artboard_id = next(iter(artboard_ids))
    existing_focus_orders = {
        int((row.get("accessibility") or {}).get("focus_order") or 0)
        for row in document["objects"]
        if str(row["artboard_id"]) == artboard_id
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
            {**nested_id_maps[source_id], **object_id_map},
        )
        assert isinstance(clone, dict)
        clone["id"] = object_id_map[source_id]
        clone["artboard_id"] = artboard_id
        source_parent_id = str(source.get("parent_id") or "")
        clone["parent_id"] = object_id_map.get(
            source_parent_id,
            source_parent_id,
        )
        clone["x"] = float(source["x"]) + float(offset_x)
        clone["y"] = float(source["y"]) + float(offset_y)
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
        if focus_order > 0 and focus_order in existing_focus_orders:
            accessibility["focus_order"] = 0
            reset_focus_ids.append(str(clone["id"]))
        elif focus_order > 0:
            existing_focus_orders.add(focus_order)
        clone["accessibility"] = accessibility
        created.append(clone)
    document["objects"].extend(created)

    interaction_id_map: dict[str, str] = {}
    created_interactions: list[dict[str, Any]] = []
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
        created_interactions.append(clone)
    document["interactions"].extend(created_interactions)

    created_root_ids = [object_id_map[item] for item in root_ids]
    document["selection"] = {
        "object_id": created_root_ids[-1],
        "object_ids": created_root_ids,
    }
    document["revision"] = int(document.get("revision") or 0) + 1
    updated = normalize_ui_document(document)
    validation = validate_ui_document(updated)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI duplicate: " + ", ".join(validation["errors"])
        )
    return updated, {
        "schema": "tigerstudio.painter.ui.duplicate.v1",
        "source_object_ids": requested,
        "root_object_ids": root_ids,
        "created_root_object_ids": created_root_ids,
        "created_object_ids": [object_id_map[item] for item in subtree_ids],
        "object_id_map": object_id_map,
        "interaction_id_map": interaction_id_map,
        "focus_order_reset_object_ids": reset_focus_ids,
        "offset": [float(offset_x), float(offset_y)],
        "revision": updated["revision"],
    }


__all__ = ["duplicate_ui_selection"]
