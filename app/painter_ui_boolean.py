"""Editable Boolean vector groups for Painter UI."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    add_ui_object,
    normalize_ui_document,
    remove_ui_object,
    select_ui_objects,
    update_ui_object,
)


UI_BOOLEAN_OPERATIONS = {"union", "subtract", "intersect", "exclude"}
UI_BOOLEAN_OPERAND_KINDS = {
    "rectangle",
    "ellipse",
    "path",
    "frame",
    "polygon",
    "star",
    "arc",
}


def normalize_ui_boolean(value: object) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    operation = str(row.get("operation") or "union").strip().casefold()
    if operation not in UI_BOOLEAN_OPERATIONS:
        operation = "union"
    return {
        "enabled": bool(row.get("enabled", False)),
        "operation": operation,
        "group": bool(row.get("group", False)),
        "operand_ids": [
            str(item)
            for item in row.get("operand_ids", [])
            if str(item or "")
        ],
    }


def inspect_ui_boolean(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    return {
        "object_id": row["id"],
        "revision": document["revision"],
        **normalize_ui_boolean((row.get("content") or {}).get("boolean")),
    }


def inspect_ui_boolean_selection(
    value: Mapping[str, Any] | None,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    selected_ids = list(document["selection"]["object_ids"])
    by_id = {row["id"]: row for row in document["objects"]}
    rows = [by_id[item] for item in selected_ids if item in by_id]
    primary_id = str(document["selection"]["object_id"] or "")
    primary = by_id.get(primary_id)
    primary_boolean = (
        normalize_ui_boolean((primary.get("content") or {}).get("boolean"))
        if primary is not None
        else normalize_ui_boolean(None)
    )
    if (
        len(rows) == 1
        and primary is not None
        and primary_boolean["enabled"]
        and primary_boolean["group"]
    ):
        return {
            "mode": "group",
            "eligible": True,
            "reason": "",
            "group_id": primary_id,
            "operation": primary_boolean["operation"],
            "operand_ids": list(primary_boolean["operand_ids"]),
            "selection_ids": selected_ids,
        }
    reason = ""
    if len(rows) < 2:
        reason = "select_two_shapes"
    elif any(bool(row["locked"]) for row in rows):
        reason = "locked_operand"
    elif len({row["artboard_id"] for row in rows}) != 1:
        reason = "mixed_artboard"
    elif len({row["parent_id"] for row in rows}) != 1:
        reason = "mixed_parent"
    elif any(row["kind"] not in UI_BOOLEAN_OPERAND_KINDS for row in rows):
        reason = "unsupported_kind"
    return {
        "mode": "selection",
        "eligible": not reason,
        "reason": reason,
        "group_id": "",
        "operation": "",
        "operand_ids": [],
        "selection_ids": selected_ids,
    }


def set_ui_boolean(
    value: Mapping[str, Any] | None,
    object_id: str,
    operation: str,
    operand_ids: list[str],
    *,
    group: bool | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    by_id = {row["id"]: row for row in document["objects"]}
    row = by_id.get(str(object_id))
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    operation = str(operation).strip().casefold()
    if operation not in UI_BOOLEAN_OPERATIONS:
        raise PainterUIDocumentError(
            f"Unsupported UI Boolean operation: {operation}"
        )
    operands: list[str] = []
    for candidate in operand_ids:
        operand = by_id.get(str(candidate))
        if operand is None:
            raise PainterUIDocumentError(
                f"UI Boolean operand not found: {candidate}"
            )
        if operand["id"] == row["id"]:
            raise PainterUIDocumentError("Boolean group cannot contain itself")
        if operand["artboard_id"] != row["artboard_id"]:
            raise PainterUIDocumentError(
                f"UI Boolean operand artboard mismatch: {candidate}"
            )
        if operand["kind"] not in {
            "rectangle",
            "ellipse",
            "path",
            "frame",
        }:
            raise PainterUIDocumentError(
                f"Unsupported UI Boolean operand kind: {operand['kind']}"
            )
        if operand["id"] not in operands:
            operands.append(operand["id"])
    if len(operands) < 2:
        raise PainterUIDocumentError(
            "UI Boolean operation requires at least two operands"
        )
    content = copy.deepcopy(dict(row.get("content") or {}))
    current = normalize_ui_boolean(content.get("boolean"))
    content["boolean"] = {
        "enabled": True,
        "operation": operation,
        "group": current["group"] if group is None else bool(group),
        "operand_ids": operands,
    }
    return update_ui_object(document, row["id"], {"content": content})


def compose_ui_boolean(
    value: Mapping[str, Any] | None,
    operation: str,
    operand_ids: list[str],
    *,
    name: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a Figma-style Boolean group from selected sibling objects."""
    document = normalize_ui_document(value)
    by_id = {row["id"]: row for row in document["objects"]}
    requested = list(dict.fromkeys(str(item or "") for item in operand_ids))
    rows: list[dict[str, Any]] = []
    for object_id in requested:
        row = by_id.get(object_id)
        if row is None:
            raise PainterUIDocumentError(
                f"UI Boolean operand not found: {object_id}"
            )
        rows.append(row)
    if len(rows) < 2:
        raise PainterUIDocumentError(
            "UI Boolean composition requires at least two objects"
        )
    if any(bool(row["locked"]) for row in rows):
        raise PainterUIDocumentError(
            "Locked UI objects cannot enter a Boolean group"
        )
    if len({row["artboard_id"] for row in rows}) != 1:
        raise PainterUIDocumentError(
            "UI Boolean operands must share one artboard"
        )
    if len({row["parent_id"] for row in rows}) != 1:
        raise PainterUIDocumentError(
            "UI Boolean operands must share one parent"
        )
    invalid = [
        row["id"]
        for row in rows
        if row["kind"] not in UI_BOOLEAN_OPERAND_KINDS
    ]
    if invalid:
        raise PainterUIDocumentError(
            "Unsupported UI Boolean operand kind: " + ", ".join(invalid)
        )
    ordered = sorted(rows, key=lambda row: (int(row["z_index"]), row["id"]))
    left = min(float(row["x"]) for row in ordered)
    top = min(float(row["y"]) for row in ordered)
    right = max(float(row["x"]) + float(row["width"]) for row in ordered)
    bottom = max(float(row["y"]) + float(row["height"]) for row in ordered)
    style_source = max(
        ordered,
        key=lambda row: (int(row["z_index"]), row["id"]),
    )
    operation_value = str(operation or "union").strip().casefold()
    if operation_value not in UI_BOOLEAN_OPERATIONS:
        raise PainterUIDocumentError(
            f"Unsupported UI Boolean operation: {operation}"
        )
    document, group_row = add_ui_object(
        document,
        kind="path",
        name=str(name or f"{operation_value.title()} Group"),
        artboard_id=str(ordered[0]["artboard_id"]),
        parent_id=str(ordered[0]["parent_id"]),
        x=left,
        y=top,
        width=max(1.0, right - left),
        height=max(1.0, bottom - top),
        style=copy.deepcopy(dict(style_source.get("style") or {})),
        content={
            "boolean": {
                "enabled": True,
                "operation": operation_value,
                "group": True,
                "operand_ids": [row["id"] for row in ordered],
            }
        },
    )
    return document, group_row


def release_ui_boolean(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    row = next(
        (item for item in document["objects"] if item["id"] == str(object_id)),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    boolean = normalize_ui_boolean((row.get("content") or {}).get("boolean"))
    if boolean["enabled"] and boolean["group"]:
        operands = list(boolean["operand_ids"])
        document, _report = remove_ui_object(document, row["id"])
        document = select_ui_objects(
            document,
            operands,
            primary_object_id=operands[-1] if operands else "",
        )
        return document
    content = copy.deepcopy(dict(row.get("content") or {}))
    content["boolean"] = normalize_ui_boolean(None)
    document, _updated = update_ui_object(
        document,
        row["id"],
        {"content": content},
    )
    return document


__all__ = [
    "UI_BOOLEAN_OPERATIONS",
    "UI_BOOLEAN_OPERAND_KINDS",
    "compose_ui_boolean",
    "inspect_ui_boolean",
    "inspect_ui_boolean_selection",
    "normalize_ui_boolean",
    "release_ui_boolean",
    "set_ui_boolean",
]
