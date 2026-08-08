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
    "polygon",
    "star",
    "arc",
    "text",
}


def is_ui_boolean_operand(row: Mapping[str, Any]) -> bool:
    """Return whether a normalized Painter object can enter a Boolean group."""
    return str(row.get("kind") or "") in UI_BOOLEAN_OPERAND_KINDS


def is_ui_boolean_group(row: Mapping[str, Any]) -> bool:
    boolean = normalize_ui_boolean((row.get("content") or {}).get("boolean"))
    return bool(boolean["enabled"] and boolean["group"])


def _validate_ui_boolean_operand(
    row: Mapping[str, Any],
    *,
    context: str = "",
) -> None:
    if is_ui_boolean_operand(row):
        return
    suffix = f": {context}" if context else ""
    raise PainterUIDocumentError(
        f"Unsupported UI Boolean operand kind: {row.get('kind')}{suffix}"
    )


def _boolean_reaches_object(
    by_id: Mapping[str, Mapping[str, Any]],
    start_id: str,
    target_id: str,
    visited: set[str] | None = None,
) -> bool:
    """Return whether Boolean operand references can reach ``target_id``."""
    current_id = str(start_id or "")
    target = str(target_id or "")
    if not current_id or not target:
        return False
    if current_id == target:
        return True
    seen = set(visited or ())
    if current_id in seen:
        return False
    seen.add(current_id)
    row = by_id.get(current_id)
    if row is None:
        return False
    boolean = normalize_ui_boolean((row.get("content") or {}).get("boolean"))
    if not boolean["enabled"] or not boolean["group"]:
        return False
    return any(
        _boolean_reaches_object(by_id, operand_id, target, seen)
        for operand_id in boolean["operand_ids"]
    )


def _boolean_group_style(row: Mapping[str, Any]) -> dict[str, Any]:
    style = copy.deepcopy(dict(row.get("style") or {}))
    if row.get("kind") == "text":
        text_fill = style.get("text_color") or "#000000FF"
        style["fill"] = text_fill
        style["fills"] = [
            {
                "type": "solid",
                "visible": True,
                "opacity": 1.0,
                "color": text_fill,
                "blend_mode": "normal",
            }
        ]
    return style


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
    elif any(not is_ui_boolean_operand(row) for row in rows):
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
        if _boolean_reaches_object(by_id, operand["id"], row["id"]):
            raise PainterUIDocumentError(
                "Boolean operand cycle is not allowed"
            )
        if operand["artboard_id"] != row["artboard_id"]:
            raise PainterUIDocumentError(
                f"UI Boolean operand artboard mismatch: {candidate}"
            )
        _validate_ui_boolean_operand(operand, context=operand["id"])
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
        if not is_ui_boolean_operand(row)
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
    operation_value = str(operation or "union").strip().casefold()
    if operation_value not in UI_BOOLEAN_OPERATIONS:
        raise PainterUIDocumentError(
            f"Unsupported UI Boolean operation: {operation}"
        )
    style_source = (
        ordered[0]
        if operation_value == "subtract"
        else ordered[-1]
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
        style=_boolean_group_style(style_source),
        content={
            "boolean": {
                "enabled": True,
                "operation": operation_value,
                "group": True,
                "operand_ids": [row["id"] for row in ordered],
            }
        },
    )
    operand_set = {row["id"] for row in ordered}
    for row in document["objects"]:
        if row["id"] in operand_set:
            row["parent_id"] = group_row["id"]
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
        parent_id = str(row.get("parent_id") or "")
        parent = next(
            (
                candidate
                for candidate in document["objects"]
                if candidate["id"] == parent_id
            ),
            None,
        )
        parent_boolean = (
            normalize_ui_boolean((parent.get("content") or {}).get("boolean"))
            if parent is not None
            else normalize_ui_boolean(None)
        )
        if (
            parent is not None
            and parent_boolean["enabled"]
            and parent_boolean["group"]
            and row["id"] in parent_boolean["operand_ids"]
        ):
            expanded: list[str] = []
            for candidate_id in parent_boolean["operand_ids"]:
                if candidate_id == row["id"]:
                    expanded.extend(operands)
                else:
                    expanded.append(candidate_id)
            parent_content = copy.deepcopy(dict(parent.get("content") or {}))
            parent_content["boolean"] = {
                **parent_boolean,
                "operand_ids": expanded,
            }
            parent["content"] = parent_content
        for candidate in document["objects"]:
            if candidate["id"] in operands:
                candidate["parent_id"] = parent_id
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


def flatten_ui_boolean(
    value: Mapping[str, Any] | None,
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Destructively replace one Boolean group with one editable vector path."""
    from PySide6.QtCore import QRectF

    from app.painter_ui_boolean_geometry import (
        qpath_to_vector_network,
        resolve_ui_boolean_path,
    )

    document = normalize_ui_document(value)
    by_id = {row["id"]: row for row in document["objects"]}
    row = by_id.get(str(object_id))
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    if not is_ui_boolean_group(row):
        raise PainterUIDocumentError("UI object is not a Boolean group")
    rect_for = lambda candidate: QRectF(
        float(candidate["x"]),
        float(candidate["y"]),
        float(candidate["width"]),
        float(candidate["height"]),
    )
    path = resolve_ui_boolean_path(document["objects"], row, rect_for)
    if path is None or path.isEmpty():
        raise PainterUIDocumentError(
            "Cannot flatten an empty Boolean result"
        )
    bounds = path.boundingRect()
    content = copy.deepcopy(dict(row.get("content") or {}))
    content.pop("boolean", None)
    content["vector_network"] = qpath_to_vector_network(path, bounds)
    content["converted_from_kind"] = "boolean"

    boolean = normalize_ui_boolean((row.get("content") or {}).get("boolean"))
    # Delete each direct operand through the document API.  Besides deleting
    # its descendants, this also cleans masks, sections, interactions,
    # component records, and linked-target references.  A raw objects-list
    # filter would leave those records dangling after Flatten.
    for operand_id in list(boolean["operand_ids"]):
        if any(candidate["id"] == operand_id for candidate in document["objects"]):
            document, _removed = remove_ui_object(document, operand_id)

    document, flattened = update_ui_object(
        document,
        row["id"],
        {
            "name": str(row.get("name") or "Vector"),
            "kind": "path",
            "x": float(bounds.left()),
            "y": float(bounds.top()),
            "width": max(1e-6, float(bounds.width())),
            "height": max(1e-6, float(bounds.height())),
            "rotation": 0.0,
            "content": content,
        },
    )
    flattened = next(
        candidate
        for candidate in document["objects"]
        if candidate["id"] == row["id"]
    )
    return document, flattened


__all__ = [
    "UI_BOOLEAN_OPERATIONS",
    "UI_BOOLEAN_OPERAND_KINDS",
    "compose_ui_boolean",
    "flatten_ui_boolean",
    "inspect_ui_boolean",
    "inspect_ui_boolean_selection",
    "is_ui_boolean_group",
    "is_ui_boolean_operand",
    "normalize_ui_boolean",
    "release_ui_boolean",
    "set_ui_boolean",
]
