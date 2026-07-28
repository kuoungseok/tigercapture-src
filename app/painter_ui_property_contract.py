"""Inspectable and resettable Painter UI property contract."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_auto_layout import normalize_ui_auto_layout
from app.painter_ui_constraints import normalize_ui_constraints
from app.painter_ui_document import (
    PainterUIDocumentError,
    normalize_ui_document,
    update_ui_object,
)
from app.painter_ui_layout_diagnostics import diagnose_ui_layout


_TOP_LEVEL_DEFAULTS: dict[str, Any] = {
    "rotation": 0.0,
    "opacity": 1.0,
    "visible": True,
    "locked": False,
    "clip_content": False,
}
_LAYOUT_PATHS = {
    "layout.mode",
    "layout.gap",
    "layout.cross_gap",
    "layout.main_alignment",
    "layout.cross_alignment",
    "layout.positioning",
    "layout.wrap",
    "layout.width_sizing",
    "layout.height_sizing",
    "layout.padding.left",
    "layout.padding.top",
    "layout.padding.right",
    "layout.padding.bottom",
}
_CONSTRAINT_PATHS = {
    "constraints.horizontal",
    "constraints.vertical",
    "constraints.pivot_x",
    "constraints.pivot_y",
    "constraints.min_width",
    "constraints.min_height",
    "constraints.preferred_width",
    "constraints.preferred_height",
    "constraints.max_width",
    "constraints.max_height",
    "constraints.lock_aspect",
}


def _object(
    document: Mapping[str, Any],
    object_id: str,
) -> dict[str, Any]:
    row = next(
        (
            item
            for item in document.get("objects", [])
            if str(item.get("id") or "") == str(object_id)
        ),
        None,
    )
    if row is None:
        raise PainterUIDocumentError(f"UI object not found: {object_id}")
    return row


def _path_value(value: Mapping[str, Any], property_path: str) -> Any:
    current: Any = value
    for token in str(property_path).split("."):
        if not isinstance(current, Mapping) or token not in current:
            raise PainterUIDocumentError(
                f"Unsupported Painter UI property path: {property_path}"
            )
        current = current[token]
    return copy.deepcopy(current)


def _default_value(row: Mapping[str, Any], property_path: str) -> Any:
    if property_path in _TOP_LEVEL_DEFAULTS:
        return copy.deepcopy(_TOP_LEVEL_DEFAULTS[property_path])
    if property_path in _LAYOUT_PATHS:
        return _path_value(
            {"layout": normalize_ui_auto_layout(None)},
            property_path,
        )
    if property_path in _CONSTRAINT_PATHS:
        defaults = normalize_ui_constraints(
            None,
            width=float(row["width"]),
            height=float(row["height"]),
        )
        return _path_value({"constraints": defaults}, property_path)
    raise PainterUIDocumentError(
        f"Painter UI property cannot be reset: {property_path}"
    )


def _current_value(row: Mapping[str, Any], property_path: str) -> Any:
    if property_path in _LAYOUT_PATHS:
        return _path_value(
            {"layout": normalize_ui_auto_layout(row.get("layout"))},
            property_path,
        )
    if property_path in _CONSTRAINT_PATHS:
        return _path_value(
            {
                "constraints": normalize_ui_constraints(
                    row.get("constraints"),
                    width=float(row["width"]),
                    height=float(row["height"]),
                )
            },
            property_path,
        )
    return _path_value(row, property_path)


def inspect_ui_property(
    value: Mapping[str, Any] | None,
    object_id: str,
    property_path: str,
) -> dict[str, Any]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    path = str(property_path or "").strip()
    current = _current_value(row, path)
    try:
        default = _default_value(row, path)
        resettable = True
    except PainterUIDocumentError:
        default = None
        resettable = False
    diagnostics = [
        item
        for item in diagnose_ui_layout(document)["diagnostics"]
        if item["owner_id"] == str(object_id)
        or item["related_id"] == str(object_id)
    ]
    return {
        "schema": "tigerstudio.painter.ui.property.v1",
        "object_id": str(object_id),
        "property_path": path,
        "value": current,
        "default": default,
        "is_default": resettable and current == default,
        "resettable": resettable,
        "token_id": str(row.get("token_bindings", {}).get(path) or ""),
        "diagnostics": diagnostics,
        "revision": int(document["revision"]),
    }


def reset_ui_property(
    value: Mapping[str, Any] | None,
    object_id: str,
    property_path: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    row = _object(document, object_id)
    path = str(property_path or "").strip()
    default = _default_value(row, path)
    if _current_value(row, path) == default:
        return document, inspect_ui_property(document, str(object_id), path)
    if path in _TOP_LEVEL_DEFAULTS:
        changes = {path: default}
    elif path in _LAYOUT_PATHS:
        layout = normalize_ui_auto_layout(row.get("layout"))
        tokens = path.split(".")[1:]
        if len(tokens) == 1:
            layout[tokens[0]] = default
        else:
            layout[tokens[0]][tokens[1]] = default
        changes = {"layout": normalize_ui_auto_layout(layout)}
    elif path in _CONSTRAINT_PATHS:
        constraints = normalize_ui_constraints(
            row.get("constraints"),
            width=float(row["width"]),
            height=float(row["height"]),
        )
        constraints[path.split(".", 1)[1]] = default
        changes = {"constraints": constraints}
    else:
        raise PainterUIDocumentError(
            f"Painter UI property cannot be reset: {path}"
        )
    document, updated = update_ui_object(document, str(object_id), changes)
    return document, inspect_ui_property(document, updated["id"], path)


__all__ = ["inspect_ui_property", "reset_ui_property"]
