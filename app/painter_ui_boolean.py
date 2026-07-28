"""Editable Boolean vector groups for Painter UI."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)


UI_BOOLEAN_OPERATIONS = {"union", "subtract", "intersect", "exclude"}


def normalize_ui_boolean(value: object) -> dict[str, Any]:
    row = value if isinstance(value, Mapping) else {}
    operation = str(row.get("operation") or "union").strip().casefold()
    if operation not in UI_BOOLEAN_OPERATIONS:
        operation = "union"
    return {
        "enabled": bool(row.get("enabled", False)),
        "operation": operation,
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


def set_ui_boolean(
    value: Mapping[str, Any] | None,
    object_id: str,
    operation: str,
    operand_ids: list[str],
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
    content["boolean"] = {
        "enabled": True,
        "operation": operation,
        "operand_ids": operands,
    }
    return update_ui_object(document, row["id"], {"content": content})


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
    "inspect_ui_boolean",
    "normalize_ui_boolean",
    "release_ui_boolean",
    "set_ui_boolean",
]
