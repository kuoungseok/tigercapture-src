"""Provider-neutral document model for Painter's general UI Designer."""
from __future__ import annotations

import copy
from typing import Any, Mapping


UI_DOCUMENT_SCHEMA = "tigerstudio.painter.ui.v1"
UI_DOCUMENT_VERSION = 1
UI_OBJECT_KINDS = {
    "frame",
    "group",
    "rectangle",
    "ellipse",
    "line",
    "path",
    "text",
    "image",
    "button",
    "progress",
}
UI_DELIVERY_TARGETS = (
    "asset_export",
    "design_handoff",
    "review_prototype",
    "unreal_umg",
)


class PainterUIDocumentError(ValueError):
    pass


def _positive(value: Any, default: float) -> float:
    try:
        return max(1.0, float(value))
    except (TypeError, ValueError):
        return float(default)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _next_id(prefix: str, rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    return f"{prefix}-{serial}"


def _default_delivery_profiles() -> list[dict[str, Any]]:
    return [
        {"id": target, "target": target, "enabled": True, "settings": {}}
        for target in UI_DELIVERY_TARGETS
    ]


def create_ui_document(
    width: int = 1920,
    height: int = 1080,
    *,
    name: str = "Main",
) -> dict[str, Any]:
    artboard_id = "artboard-1"
    return {
        "schema": UI_DOCUMENT_SCHEMA,
        "version": UI_DOCUMENT_VERSION,
        "document_id": "ui-document-1",
        "revision": 0,
        "active_artboard_id": artboard_id,
        "selection": {"object_id": "", "object_ids": []},
        "artboards": [
            {
                "id": artboard_id,
                "name": str(name or "Main"),
                "width": max(1, int(width)),
                "height": max(1, int(height)),
                "x": 0.0,
                "y": 0.0,
                "background": "#FFFFFF",
                "breakpoint": "custom",
                "orientation": "landscape" if width >= height else "portrait",
                "safe_area": {"left": 0, "top": 0, "right": 0, "bottom": 0},
            }
        ],
        "objects": [],
        "components": [],
        "tokens": [],
        "interactions": [],
        "delivery_profiles": _default_delivery_profiles(),
        "linked_targets": {},
    }


def _normalize_artboard(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    width = _positive(row.get("width"), 1920.0)
    height = _positive(row.get("height"), 1080.0)
    safe = row.get("safe_area")
    safe = safe if isinstance(safe, Mapping) else {}
    return {
        "id": str(row.get("id") or f"artboard-{index + 1}"),
        "name": str(row.get("name") or f"Artboard {index + 1}"),
        "width": int(round(width)),
        "height": int(round(height)),
        "x": _number(row.get("x")),
        "y": _number(row.get("y")),
        "background": str(row.get("background") or "#FFFFFF"),
        "breakpoint": str(row.get("breakpoint") or "custom"),
        "orientation": str(
            row.get("orientation")
            or ("landscape" if width >= height else "portrait")
        ),
        "safe_area": {
            key: max(0, int(_number(safe.get(key))))
            for key in ("left", "top", "right", "bottom")
        },
    }


def _normalize_object(
    row: Mapping[str, Any],
    index: int,
    default_artboard_id: str,
) -> dict[str, Any]:
    kind = str(row.get("kind") or "rectangle").strip().casefold()
    style = row.get("style")
    content = row.get("content")
    constraints = row.get("constraints")
    layout = row.get("layout")
    return {
        "id": str(row.get("id") or f"ui-object-{index + 1}"),
        "kind": kind,
        "name": str(row.get("name") or kind.replace("_", " ").title()),
        "artboard_id": str(row.get("artboard_id") or default_artboard_id),
        "parent_id": str(row.get("parent_id") or ""),
        "x": _number(row.get("x")),
        "y": _number(row.get("y")),
        "width": _positive(row.get("width"), 160.0),
        "height": _positive(row.get("height"), 64.0),
        "rotation": _number(row.get("rotation")),
        "opacity": max(0.0, min(1.0, _number(row.get("opacity"), 1.0))),
        "visible": bool(row.get("visible", True)),
        "locked": bool(row.get("locked", False)),
        "z_index": int(_number(row.get("z_index"), index)),
        "style": copy.deepcopy(dict(style)) if isinstance(style, Mapping) else {},
        "content": copy.deepcopy(dict(content)) if isinstance(content, Mapping) else {},
        "constraints": (
            copy.deepcopy(dict(constraints))
            if isinstance(constraints, Mapping)
            else {"horizontal": "left", "vertical": "top"}
        ),
        "layout": copy.deepcopy(dict(layout)) if isinstance(layout, Mapping) else {},
        "component_id": str(row.get("component_id") or ""),
        "variant": str(row.get("variant") or ""),
        "accessibility": copy.deepcopy(
            dict(row.get("accessibility"))
            if isinstance(row.get("accessibility"), Mapping)
            else {}
        ),
    }


def normalize_ui_document(
    value: Mapping[str, Any] | None,
    *,
    fallback_width: int = 1920,
    fallback_height: int = 1080,
) -> dict[str, Any]:
    raw = copy.deepcopy(dict(value)) if isinstance(value, Mapping) else {}
    raw_artboards = [
        row for row in raw.get("artboards", []) if isinstance(row, Mapping)
    ]
    if not raw_artboards:
        raw_artboards = create_ui_document(
            fallback_width,
            fallback_height,
        )["artboards"]
    artboards = [
        _normalize_artboard(row, index) for index, row in enumerate(raw_artboards)
    ]
    active_artboard_id = str(raw.get("active_artboard_id") or artboards[0]["id"])
    if active_artboard_id not in {row["id"] for row in artboards}:
        active_artboard_id = artboards[0]["id"]
    raw_objects = [
        row for row in raw.get("objects", []) if isinstance(row, Mapping)
    ]
    objects = [
        _normalize_object(row, index, active_artboard_id)
        for index, row in enumerate(raw_objects)
    ]
    selection = raw.get("selection")
    selection = selection if isinstance(selection, Mapping) else {}
    selected_id = str(selection.get("object_id") or "")
    object_by_id = {row["id"]: row for row in objects}
    raw_selected_ids = selection.get("object_ids")
    if not isinstance(raw_selected_ids, list):
        raw_selected_ids = [selected_id] if selected_id else []
    selected_ids: list[str] = []
    for value in raw_selected_ids:
        candidate = str(value or "")
        row = object_by_id.get(candidate)
        if (
            candidate
            and row is not None
            and row["artboard_id"] == active_artboard_id
            and candidate not in selected_ids
        ):
            selected_ids.append(candidate)
    selected_row = object_by_id.get(selected_id)
    if (
        selected_row is None
        or selected_row["artboard_id"] != active_artboard_id
    ):
        selected_id = ""
    if selected_id and selected_id not in selected_ids:
        selected_ids.append(selected_id)
    if not selected_id and selected_ids:
        selected_id = selected_ids[-1]
    profiles = [
        copy.deepcopy(dict(row))
        for row in raw.get("delivery_profiles", [])
        if isinstance(row, Mapping)
    ]
    known_targets = {str(row.get("target") or "") for row in profiles}
    profiles.extend(
        row
        for row in _default_delivery_profiles()
        if row["target"] not in known_targets
    )
    return {
        "schema": UI_DOCUMENT_SCHEMA,
        "version": UI_DOCUMENT_VERSION,
        "document_id": str(raw.get("document_id") or "ui-document-1"),
        "revision": max(0, int(_number(raw.get("revision"), 0))),
        "active_artboard_id": active_artboard_id,
        "selection": {
            "object_id": selected_id,
            "object_ids": selected_ids,
        },
        "artboards": artboards,
        "objects": objects,
        "components": copy.deepcopy(list(raw.get("components") or [])),
        "tokens": copy.deepcopy(list(raw.get("tokens") or [])),
        "interactions": copy.deepcopy(list(raw.get("interactions") or [])),
        "delivery_profiles": profiles,
        "linked_targets": copy.deepcopy(dict(raw.get("linked_targets") or {})),
    }


def validate_ui_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    errors: list[str] = []
    warnings: list[str] = []
    artboard_ids = [row["id"] for row in document["artboards"]]
    object_ids = [row["id"] for row in document["objects"]]
    if len(set(artboard_ids)) != len(artboard_ids):
        errors.append("duplicate_artboard_id")
    if len(set(object_ids)) != len(object_ids):
        errors.append("duplicate_object_id")
    object_by_id = {row["id"]: row for row in document["objects"]}
    artboard_id_set = set(artboard_ids)
    for row in document["objects"]:
        if row["kind"] not in UI_OBJECT_KINDS:
            errors.append(f"unsupported_object_kind:{row['id']}:{row['kind']}")
        if row["artboard_id"] not in artboard_id_set:
            errors.append(f"missing_artboard:{row['id']}:{row['artboard_id']}")
        parent_id = row["parent_id"]
        if parent_id and parent_id not in object_by_id:
            errors.append(f"missing_parent:{row['id']}:{parent_id}")
        if (
            parent_id
            and parent_id in object_by_id
            and object_by_id[parent_id]["artboard_id"] != row["artboard_id"]
        ):
            errors.append(f"parent_artboard_mismatch:{row['id']}:{parent_id}")
        if parent_id == row["id"]:
            errors.append(f"self_parent:{row['id']}")
        if row["opacity"] <= 0.0:
            warnings.append(f"fully_transparent:{row['id']}")
        if not row["visible"]:
            warnings.append(f"hidden:{row['id']}")
    for object_id in object_ids:
        seen: set[str] = set()
        current = object_by_id.get(object_id)
        while current and current["parent_id"]:
            parent_id = current["parent_id"]
            if parent_id in seen:
                errors.append(f"parent_cycle:{object_id}")
                break
            seen.add(parent_id)
            current = object_by_id.get(parent_id)
    return {
        "schema": "tigerstudio.painter.ui.validation.v1",
        "ok": not errors,
        "errors": sorted(set(errors)),
        "warnings": sorted(set(warnings)),
        "artboard_count": len(artboard_ids),
        "object_count": len(object_ids),
        "component_count": len(document["components"]),
        "token_count": len(document["tokens"]),
        "revision": document["revision"],
    }


def inspect_ui_document(value: Mapping[str, Any]) -> dict[str, Any]:
    document = normalize_ui_document(value)
    return {
        "schema": "tigerstudio.painter.ui.inspect.v1",
        "document": copy.deepcopy(document),
        "validation": validate_ui_document(document),
        "active_artboard_id": document["active_artboard_id"],
        "selected_object_id": document["selection"]["object_id"],
        "selected_object_ids": list(document["selection"]["object_ids"]),
        "delivery_targets": list(UI_DELIVERY_TARGETS),
    }


def _revised(document: Mapping[str, Any]) -> dict[str, Any]:
    updated = normalize_ui_document(document)
    updated["revision"] += 1
    return updated


def add_ui_artboard(
    value: Mapping[str, Any],
    *,
    name: str = "",
    width: int = 1920,
    height: int = 1080,
    breakpoint: str = "custom",
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    artboard_id = _next_id("artboard", document["artboards"])
    row = _normalize_artboard(
        {
            "id": artboard_id,
            "name": name or f"Artboard {len(document['artboards']) + 1}",
            "width": width,
            "height": height,
            "breakpoint": breakpoint,
        },
        len(document["artboards"]),
    )
    document["artboards"].append(row)
    document["active_artboard_id"] = artboard_id
    document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = []
    return _revised(document), copy.deepcopy(row)


def update_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["artboards"]):
        if row["id"] != artboard_id:
            continue
        merged = {**row, **dict(changes), "id": row["id"]}
        updated_row = _normalize_artboard(merged, index)
        document["artboards"][index] = updated_row
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI artboard not found: {artboard_id}")


def remove_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if len(document["artboards"]) <= 1:
        raise PainterUIDocumentError("A UI document must keep at least one artboard")
    if artboard_id not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {artboard_id}")
    removed_objects = [
        row["id"] for row in document["objects"] if row["artboard_id"] == artboard_id
    ]
    document["artboards"] = [
        row for row in document["artboards"] if row["id"] != artboard_id
    ]
    document["objects"] = [
        row for row in document["objects"] if row["artboard_id"] != artboard_id
    ]
    if document["active_artboard_id"] == artboard_id:
        document["active_artboard_id"] = document["artboards"][0]["id"]
    if document["selection"]["object_id"] in removed_objects:
        document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = [
        object_id
        for object_id in document["selection"]["object_ids"]
        if object_id not in removed_objects
    ]
    return _revised(document), {
        "artboard_id": artboard_id,
        "removed_object_ids": removed_objects,
    }


def set_active_ui_artboard(
    value: Mapping[str, Any],
    artboard_id: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    target = str(artboard_id or "")
    if target not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target}")
    if document["active_artboard_id"] == target:
        return document
    document["active_artboard_id"] = target
    selected = document["selection"]["object_id"]
    selected_row = next(
        (row for row in document["objects"] if row["id"] == selected),
        None,
    )
    if selected_row is not None and selected_row["artboard_id"] != target:
        document["selection"]["object_id"] = ""
        document["selection"]["object_ids"] = []
    return _revised(document)


def add_ui_object(
    value: Mapping[str, Any],
    *,
    kind: str = "rectangle",
    name: str = "",
    artboard_id: str = "",
    parent_id: str = "",
    x: float = 0.0,
    y: float = 0.0,
    width: float = 160.0,
    height: float = 64.0,
    style: Mapping[str, Any] | None = None,
    content: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    target_artboard = str(artboard_id or document["active_artboard_id"])
    if target_artboard not in {row["id"] for row in document["artboards"]}:
        raise PainterUIDocumentError(f"UI artboard not found: {target_artboard}")
    if parent_id and parent_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI parent object not found: {parent_id}")
    object_id = _next_id("ui-object", document["objects"])
    row = _normalize_object(
        {
            "id": object_id,
            "kind": kind,
            "name": name or str(kind or "rectangle").title(),
            "artboard_id": target_artboard,
            "parent_id": parent_id,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "z_index": len(document["objects"]),
            "style": dict(style or {}),
            "content": dict(content or {}),
        },
        len(document["objects"]),
        target_artboard,
    )
    document["objects"].append(row)
    document["selection"]["object_id"] = object_id
    document["selection"]["object_ids"] = [object_id]
    return _revised(document), copy.deepcopy(row)


def update_ui_object(
    value: Mapping[str, Any],
    object_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    for index, row in enumerate(document["objects"]):
        if row["id"] != object_id:
            continue
        merged = {**row, **dict(changes), "id": row["id"]}
        updated_row = _normalize_object(
            merged,
            index,
            document["active_artboard_id"],
        )
        document["objects"][index] = updated_row
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise PainterUIDocumentError("Invalid UI object update: " + ", ".join(validation["errors"]))
        document["selection"]["object_id"] = object_id
        if object_id not in document["selection"]["object_ids"]:
            document["selection"]["object_ids"].append(object_id)
        return _revised(document), copy.deepcopy(updated_row)
    raise PainterUIDocumentError(f"UI object not found: {object_id}")


def remove_ui_object(
    value: Mapping[str, Any],
    object_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    if object_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    removed = {object_id}
    changed = True
    while changed:
        before = len(removed)
        removed.update(
            row["id"]
            for row in document["objects"]
            if row["parent_id"] in removed
        )
        changed = len(removed) != before
    document["objects"] = [
        row for row in document["objects"] if row["id"] not in removed
    ]
    if document["selection"]["object_id"] in removed:
        document["selection"]["object_id"] = ""
    document["selection"]["object_ids"] = [
        selected
        for selected in document["selection"]["object_ids"]
        if selected not in removed
    ]
    if (
        not document["selection"]["object_id"]
        and document["selection"]["object_ids"]
    ):
        document["selection"]["object_id"] = document["selection"]["object_ids"][-1]
    return _revised(document), {"removed_object_ids": sorted(removed)}


def select_ui_object(
    value: Mapping[str, Any],
    object_id: str = "",
    *,
    mode: str = "replace",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    if object_id and object_id not in {row["id"] for row in document["objects"]}:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    selected = list(document["selection"]["object_ids"])
    target = str(object_id or "")
    operation = str(mode or "replace").strip().casefold()
    if not target:
        selected = []
    elif operation == "add":
        if target not in selected:
            selected.append(target)
    elif operation == "toggle":
        if target in selected:
            selected.remove(target)
        else:
            selected.append(target)
    else:
        selected = [target]
    document["selection"]["object_ids"] = selected
    document["selection"]["object_id"] = (
        target if target in selected else selected[-1] if selected else ""
    )
    return document


def select_ui_objects(
    value: Mapping[str, Any],
    object_ids: list[str] | tuple[str, ...],
    *,
    primary_object_id: str = "",
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    active = document["active_artboard_id"]
    valid_by_id = {
        row["id"]: row
        for row in document["objects"]
        if row["artboard_id"] == active
    }
    selected: list[str] = []
    for value_id in object_ids:
        object_id = str(value_id or "")
        if object_id in valid_by_id and object_id not in selected:
            selected.append(object_id)
    primary = str(primary_object_id or "")
    if primary not in selected:
        primary = selected[-1] if selected else ""
    document["selection"] = {
        "object_id": primary,
        "object_ids": selected,
    }
    return document


__all__ = [
    "PainterUIDocumentError",
    "UI_DELIVERY_TARGETS",
    "UI_DOCUMENT_SCHEMA",
    "UI_DOCUMENT_VERSION",
    "UI_OBJECT_KINDS",
    "add_ui_artboard",
    "add_ui_object",
    "create_ui_document",
    "inspect_ui_document",
    "normalize_ui_document",
    "remove_ui_artboard",
    "remove_ui_object",
    "select_ui_object",
    "select_ui_objects",
    "set_active_ui_artboard",
    "update_ui_artboard",
    "update_ui_object",
    "validate_ui_document",
]
