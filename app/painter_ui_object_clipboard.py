"""Stable-ID-safe whole-object clipboard for Painter UI Design mode."""
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


UI_OBJECT_CLIPBOARD_SCHEMA = "tigerstudio.painter.ui.object_clipboard.v1"


def copy_ui_selection_payload(
    value: Mapping[str, Any],
    *,
    object_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
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
    existing = {str(row["id"]): row for row in document["objects"]}
    if not requested or any(item not in existing for item in requested):
        raise PainterUIDocumentError("Cannot copy UI selection: missing_object")
    root_ids = _selected_root_ids(document, requested)
    subtree_ids = _subtree_ids(document, root_ids)
    subtree_set = set(subtree_ids)
    interactions = [
        copy.deepcopy(row)
        for row in document["interactions"]
        if str(row.get("source_object_id") or "") in subtree_set
    ]
    return {
        "schema": UI_OBJECT_CLIPBOARD_SCHEMA,
        "source_document_id": str(document["document_id"]),
        "source_artboard_id": str(existing[root_ids[0]]["artboard_id"]),
        "root_object_ids": root_ids,
        "objects": [copy.deepcopy(existing[item]) for item in subtree_ids],
        "interactions": interactions,
    }


def paste_ui_selection_payload(
    value: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    artboard_id: str = "",
    parent_id: str = "",
    offset_x: float = 12.0,
    offset_y: float = 12.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if str(payload.get("schema") or "") != UI_OBJECT_CLIPBOARD_SCHEMA:
        raise PainterUIDocumentError("Unsupported UI object clipboard payload")
    source_rows = [
        copy.deepcopy(row)
        for row in payload.get("objects", [])
        if isinstance(row, Mapping) and str(row.get("id") or "")
    ]
    if not source_rows:
        raise PainterUIDocumentError("Cannot paste UI selection: empty_clipboard")
    source_by_id = {str(row["id"]): row for row in source_rows}
    root_ids = [
        str(item)
        for item in payload.get("root_object_ids", [])
        if str(item) in source_by_id
    ]
    if not root_ids:
        raise PainterUIDocumentError("Cannot paste UI selection: missing_roots")
    target_artboard = str(artboard_id or document["active_artboard_id"])
    if target_artboard not in {str(row["id"]) for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target_artboard}")
    if parent_id and parent_id not in {str(row["id"]) for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI parent object not found: {parent_id}")
    available_components = {str(row["id"]) for row in document["components"]}
    required_components = {
        str(row.get("component_id") or "")
        for row in source_rows
        if str(row.get("component_role") or "") == "instance"
        and str(row.get("component_id") or "")
    }
    missing_components = sorted(required_components - available_components)
    if missing_components:
        raise PainterUIDocumentError(
            "Cannot paste linked Instances without their components: "
            + ", ".join(missing_components)
        )

    used_ids = _all_nested_ids(document)
    object_id_map = {
        source_id: _next_stable_id("ui-object", used_ids)
        for source_id in source_by_id
    }
    created: list[dict[str, Any]] = []
    next_z = max(
        [int(row.get("z_index") or 0) for row in document["objects"]] or [-1]
    ) + 1
    for source in source_rows:
        source_id = str(source["id"])
        nested_ids = {
            nested_id
            for key, item in source.items()
            if key != "id"
            for nested_id in _all_nested_ids(item)
            if nested_id not in object_id_map
        }
        nested_map = {
            nested_id: _next_stable_id("ui-copy", used_ids)
            for nested_id in sorted(nested_ids)
        }
        clone = _replace_ids(source, {**nested_map, **object_id_map})
        assert isinstance(clone, dict)
        clone["id"] = object_id_map[source_id]
        clone["artboard_id"] = target_artboard
        source_parent = str(source.get("parent_id") or "")
        clone["parent_id"] = (
            object_id_map[source_parent]
            if source_parent in object_id_map
            else str(parent_id or "")
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
        created.append(clone)
    document["objects"].extend(created)

    interaction_id_map: dict[str, str] = {}
    created_interactions: list[dict[str, Any]] = []
    for source in payload.get("interactions", []):
        if not isinstance(source, Mapping):
            continue
        source_object_id = str(source.get("source_object_id") or "")
        if source_object_id not in object_id_map:
            continue
        clone = _replace_ids(copy.deepcopy(source), object_id_map)
        assert isinstance(clone, dict)
        interaction_id = _next_stable_id("ui-interaction", used_ids)
        interaction_id_map[str(source.get("id") or "")] = interaction_id
        clone["id"] = interaction_id
        created_interactions.append(clone)
    document["interactions"].extend(created_interactions)
    created_root_ids = [object_id_map[item] for item in root_ids]
    document["selection"] = {
        "object_id": created_root_ids[-1],
        "object_ids": created_root_ids,
    }
    document["revision"] += 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise PainterUIDocumentError(
            "Invalid UI object paste: " + ", ".join(validation["errors"])
        )
    return document, {
        "schema": "tigerstudio.painter.ui.object_paste.v1",
        "created_root_object_ids": created_root_ids,
        "created_object_ids": [object_id_map[item] for item in source_by_id],
        "object_id_map": object_id_map,
        "interaction_id_map": interaction_id_map,
    }


__all__ = [
    "UI_OBJECT_CLIPBOARD_SCHEMA",
    "copy_ui_selection_payload",
    "paste_ui_selection_payload",
]
