"""Stable-ID developer handoff state and inspection for Painter UI documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from app.painter_ui_document import normalize_ui_document, validate_ui_document
from app.painter_ui_measurements import inspect_ui_selection_measurements
from app.painter_ui_motion_bridge import resolved_ui_geometry


DEV_HANDOFF_SCHEMA = "tigerstudio.painter.ui.dev_handoff.v1"
DEV_INSPECT_SCHEMA = "tigerstudio.painter.ui.dev.inspect.v1"
_TARGET_KINDS = ("section", "artboard", "component", "object")


def normalize_ui_dev_handoff(value: object) -> dict[str, Any]:
    raw = value if isinstance(value, Mapping) else {}
    readiness = []
    seen_ready: set[tuple[str, str]] = set()
    for row in raw.get("readiness", []):
        if not isinstance(row, Mapping):
            continue
        target_type = str(row.get("target_type") or "").strip().casefold()
        target_id = str(row.get("target_id") or "").strip()
        key = (target_type, target_id)
        if target_type not in _TARGET_KINDS or not target_id or key in seen_ready:
            continue
        seen_ready.add(key)
        readiness.append(
            {
                "target_type": target_type,
                "target_id": target_id,
                "ready": bool(row.get("ready", False)),
                "note": str(row.get("note") or "").strip(),
            }
        )
    annotations = []
    seen_annotations: set[str] = set()
    for index, row in enumerate(raw.get("annotations", [])):
        if not isinstance(row, Mapping):
            continue
        annotation_id = str(row.get("id") or f"ui-dev-annotation-{index + 1}")
        if annotation_id in seen_annotations:
            continue
        target_type = str(row.get("target_type") or "object").strip().casefold()
        target_id = str(row.get("target_id") or "").strip()
        if target_type not in _TARGET_KINDS or not target_id:
            continue
        seen_annotations.add(annotation_id)
        annotations.append(
            {
                "id": annotation_id,
                "target_type": target_type,
                "target_id": target_id,
                "text": str(row.get("text") or "").strip(),
                "kind": str(row.get("kind") or "note").strip().casefold(),
                "visible": bool(row.get("visible", True)),
            }
        )
    return {
        "schema": DEV_HANDOFF_SCHEMA,
        "readiness": readiness,
        "annotations": annotations,
    }


def _document_with_contract(
    value: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    contract = normalize_ui_dev_handoff(
        document["linked_targets"].get("dev_handoff")
    )
    document["linked_targets"]["dev_handoff"] = contract
    return document, contract


def _target_row(
    document: Mapping[str, Any],
    target_type: str,
    target_id: str,
) -> Mapping[str, Any]:
    key = {
        "section": "sections",
        "artboard": "artboards",
        "component": "components",
        "object": "objects",
    }.get(target_type)
    if key is None:
        raise ValueError(f"Unsupported developer target type: {target_type}")
    row = next(
        (item for item in document[key] if str(item["id"]) == target_id),
        None,
    )
    if row is None:
        raise ValueError(f"Unknown {target_type} target: {target_id}")
    return row


def set_ui_dev_ready(
    value: Mapping[str, Any] | None,
    *,
    target_type: str,
    target_id: str,
    ready: bool,
    note: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, contract = _document_with_contract(value)
    kind = str(target_type or "").strip().casefold()
    stable_id = str(target_id or "").strip()
    target = _target_row(document, kind, stable_id)
    row = {
        "target_type": kind,
        "target_id": stable_id,
        "ready": bool(ready),
        "note": str(note or "").strip(),
    }
    contract["readiness"] = [
        existing
        for existing in contract["readiness"]
        if (existing["target_type"], existing["target_id"]) != (kind, stable_id)
    ]
    contract["readiness"].append(row)
    document["revision"] += 1
    document["linked_targets"]["dev_handoff"] = contract
    return normalize_ui_document(document), {
        **row,
        "target_name": str(target.get("name") or stable_id),
    }


def add_ui_dev_annotation(
    value: Mapping[str, Any] | None,
    *,
    target_type: str,
    target_id: str,
    text: str,
    kind: str = "note",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, contract = _document_with_contract(value)
    normalized_type = str(target_type or "").strip().casefold()
    stable_id = str(target_id or "").strip()
    _target_row(document, normalized_type, stable_id)
    message = str(text or "").strip()
    if not message:
        raise ValueError("Developer annotation text is required")
    used = {row["id"] for row in contract["annotations"]}
    serial = 1
    while f"ui-dev-annotation-{serial}" in used:
        serial += 1
    annotation = {
        "id": f"ui-dev-annotation-{serial}",
        "target_type": normalized_type,
        "target_id": stable_id,
        "text": message,
        "kind": str(kind or "note").strip().casefold(),
        "visible": True,
    }
    contract["annotations"].append(annotation)
    document["revision"] += 1
    document["linked_targets"]["dev_handoff"] = contract
    return normalize_ui_document(document), copy.deepcopy(annotation)


def update_ui_dev_annotation(
    value: Mapping[str, Any] | None,
    annotation_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document, contract = _document_with_contract(value)
    target = next(
        (
            row
            for row in contract["annotations"]
            if row["id"] == str(annotation_id)
        ),
        None,
    )
    if target is None:
        raise ValueError(f"Developer annotation not found: {annotation_id}")
    for key in ("text", "kind"):
        if key in changes:
            target[key] = str(changes[key] or "").strip()
    if "visible" in changes:
        target["visible"] = bool(changes["visible"])
    if not target["text"]:
        raise ValueError("Developer annotation text is required")
    document["revision"] += 1
    document["linked_targets"]["dev_handoff"] = contract
    return normalize_ui_document(document), copy.deepcopy(target)


def remove_ui_dev_annotation(
    value: Mapping[str, Any] | None,
    annotation_id: str,
) -> dict[str, Any]:
    document, contract = _document_with_contract(value)
    before = len(contract["annotations"])
    contract["annotations"] = [
        row for row in contract["annotations"] if row["id"] != str(annotation_id)
    ]
    if len(contract["annotations"]) == before:
        raise ValueError(f"Developer annotation not found: {annotation_id}")
    document["revision"] += 1
    document["linked_targets"]["dev_handoff"] = contract
    return normalize_ui_document(document)


def _alias_chain(
    token_id: str,
    token_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    chain: list[str] = []
    current = str(token_id or "")
    while current and current not in chain:
        chain.append(current)
        row = token_by_id.get(current)
        current = str(row.get("alias_token_id") or "") if row else ""
    return chain


def _token_resolution(
    token_id: str,
    *,
    token_by_id: Mapping[str, Mapping[str, Any]],
    collection_by_id: Mapping[str, Mapping[str, Any]],
    artboard_modes: Mapping[str, str],
) -> dict[str, Any]:
    chain = _alias_chain(token_id, token_by_id)
    terminal = token_by_id.get(chain[-1]) if chain else None
    collection = (
        collection_by_id.get(str(terminal.get("collection_id") or ""))
        if terminal
        else None
    )
    mode_id = (
        str(
            artboard_modes.get(
                str(collection.get("id") or ""),
                collection.get("default_mode_id") or "",
            )
        )
        if collection
        else ""
    )
    mode = next(
        (
            row
            for row in collection.get("modes", [])
            if str(row.get("id") or "") == mode_id
        ),
        None,
    )
    mode_values = dict(terminal.get("mode_values") or {}) if terminal else {}
    resolved_value = (
        copy.deepcopy(mode_values[mode_id])
        if mode_id in mode_values
        else copy.deepcopy(terminal.get("value"))
        if terminal
        else None
    )
    return {
        "collection_name": str(collection.get("name") or "") if collection else "",
        "mode_id": mode_id,
        "mode_name": str(mode.get("name") or "") if mode else "",
        "resolved_token_id": str(terminal.get("id") or "") if terminal else "",
        "resolved_value": resolved_value,
        "alias_cycle": bool(
            chain
            and token_by_id.get(chain[-1])
            and str(token_by_id[chain[-1]].get("alias_token_id") or "") in chain
        ),
    }


def _component_context(
    document: Mapping[str, Any],
    row: Mapping[str, Any],
) -> dict[str, Any]:
    component_id = str(row.get("component_id") or "")
    if not component_id:
        return {}
    component_by_id = {item["id"]: item for item in document["components"]}
    component = component_by_id.get(component_id)
    if component is None:
        return {}
    family_id = str(component.get("base_component_id") or component["id"])
    family = component_by_id.get(family_id, component)
    variant_ids = [family_id, *family.get("variant_ids", [])]
    variants = [
        {
            "id": variant["id"],
            "name": variant["name"],
            "active": variant["id"] == component_id,
        }
        for variant_id in variant_ids
        if (variant := component_by_id.get(variant_id)) is not None
    ]
    properties = dict(row.get("component_properties") or {})
    if not properties and str(row.get("component_role") or "") == "instance":
        object_by_id = {item["id"]: item for item in document["objects"]}
        current = row
        while current and not properties:
            if (
                str(current.get("component_role") or "") == "instance"
                and str(current.get("component_id") or "") == component_id
            ):
                properties = dict(current.get("component_properties") or {})
            current = object_by_id.get(str(current.get("parent_id") or ""))
    from app.painter_ui_components import component_property_defaults

    resolved_properties = component_property_defaults(component)
    resolved_properties.update(copy.deepcopy(properties))
    return {
        "id": component["id"],
        "name": component["name"],
        "role": str(row.get("component_role") or "none"),
        "family_id": family_id,
        "variants": variants,
        "property_definitions": copy.deepcopy(
            component.get("property_definitions") or {}
        ),
        "property_values": resolved_properties,
        "states": sorted((component.get("state_overrides") or {}).keys()),
    }


def inspect_ui_dev_handoff(
    value: Mapping[str, Any] | None,
    *,
    object_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    document, contract = _document_with_contract(value)
    requested = list(
        object_ids
        if object_ids is not None
        else document["selection"]["object_ids"]
    )
    selected_ids = {str(item) for item in requested}
    selected = [row for row in document["objects"] if row["id"] in selected_ids]
    geometry = resolved_ui_geometry(document)
    token_by_id = {row["id"]: row for row in document["tokens"]}
    collection_by_id = {
        row["id"]: row for row in document["variable_collections"]
    }
    artboard_by_id = {row["id"]: row for row in document["artboards"]}
    readiness = {
        (row["target_type"], row["target_id"]): row
        for row in contract["readiness"]
    }
    from app.painter_ui_delivery import ui_object_delivery_statuses

    objects = []
    for row in selected:
        token_details = []
        artboard = artboard_by_id.get(row["artboard_id"], {})
        artboard_modes = dict(artboard.get("variable_modes") or {})
        for property_path, token_id in row.get("token_bindings", {}).items():
            token = token_by_id.get(str(token_id))
            resolution = _token_resolution(
                str(token_id),
                token_by_id=token_by_id,
                collection_by_id=collection_by_id,
                artboard_modes=artboard_modes,
            )
            token_details.append(
                {
                    "property": str(property_path),
                    "token_id": str(token_id),
                    "name": str(token.get("name") or token_id) if token else "",
                    "value": copy.deepcopy(token.get("value")) if token else None,
                    "collection_id": str(token.get("collection_id") or "")
                    if token
                    else "",
                    "scope": list(token.get("scope") or []) if token else [],
                    "alias_chain": _alias_chain(str(token_id), token_by_id),
                    **resolution,
                }
            )
        from app.painter_ui_dev_snippets import inspect_ui_dev_snippets

        objects.append(
            {
                "id": row["id"],
                "name": row["name"],
                "kind": row["kind"],
                "geometry": copy.deepcopy(geometry.get(row["id"], {})),
                "layout": copy.deepcopy(row["layout"]),
                "style": copy.deepcopy(row["style"]),
                "typography": {
                    key: copy.deepcopy(row["style"].get(key))
                    for key in (
                        "font_family",
                        "font_size",
                        "font_weight",
                        "line_height",
                        "text_align",
                    )
                    if key in row["style"]
                },
                "accessibility": copy.deepcopy(row.get("accessibility") or {}),
                "tokens": token_details,
                "interaction_ids": [
                    interaction["id"]
                    for interaction in document["interactions"]
                    if interaction["source_object_id"] == row["id"]
                ],
                "component": _component_context(document, row),
                "ready": copy.deepcopy(
                    readiness.get(
                        ("object", row["id"]),
                        {
                            "target_type": "object",
                            "target_id": row["id"],
                            "ready": False,
                            "note": "",
                        },
                    )
                ),
                "delivery": ui_object_delivery_statuses(document, row["id"])[
                    "targets"
                ],
                "developer_snippets": inspect_ui_dev_snippets(
                    document,
                    row["id"],
                )["snippets"],
            }
        )
    annotations = [
        copy.deepcopy(row)
        for row in contract["annotations"]
        if row["target_id"] in selected_ids
    ]
    validation = validate_ui_document(document)
    return {
        "schema": DEV_INSPECT_SCHEMA,
        "document_id": document["document_id"],
        "revision": document["revision"],
        "selection_count": len(objects),
        "objects": objects,
        "measurements": inspect_ui_selection_measurements(
            document,
            object_ids=list(selected_ids),
        ),
        "annotations": annotations,
        "validation": validation,
    }


__all__ = [
    "DEV_HANDOFF_SCHEMA",
    "DEV_INSPECT_SCHEMA",
    "add_ui_dev_annotation",
    "inspect_ui_dev_handoff",
    "normalize_ui_dev_handoff",
    "remove_ui_dev_annotation",
    "set_ui_dev_ready",
    "update_ui_dev_annotation",
]
