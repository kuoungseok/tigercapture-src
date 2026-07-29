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
    readiness = {
        (row["target_type"], row["target_id"]): row
        for row in contract["readiness"]
    }
    from app.painter_ui_delivery import ui_object_delivery_statuses

    objects = []
    for row in selected:
        token_details = []
        for property_path, token_id in row.get("token_bindings", {}).items():
            token = token_by_id.get(str(token_id))
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
                }
            )
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
