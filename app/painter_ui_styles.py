"""Named Color, Text, Effect, and Layout Grid styles for Painter UI."""
from __future__ import annotations

import copy
from typing import Any, Mapping


UI_NAMED_STYLE_KINDS = ("color", "text", "effect")
UI_STYLE_KINDS = (*UI_NAMED_STYLE_KINDS, "layout_grid")
UI_STYLE_PROPERTY_KEYS = {
    "color": {
        "fill",
        "fills",
        "stroke",
        "strokes",
        "text_color",
    },
    "text": {
        "font_family",
        "font_size",
        "font_weight",
        "font_style",
        "font_axes",
        "alignment",
        "text_align",
        "line_height",
        "letter_spacing",
        "text_decoration",
    },
    "effect": {
        "shadow",
        "text_shadow",
        "blur",
        "background_blur",
        "blend_mode",
    },
}
UI_STYLE_TOKEN_PATHS = {
    "color": {
        "style.fill",
        "style.stroke",
        "style.text_color",
    },
    "text": {"style.font_size"},
    "effect": {"style.shadow"},
}


def normalize_ui_named_style(
    row: Mapping[str, Any] | None,
    index: int = 0,
) -> dict[str, Any]:
    source = row if isinstance(row, Mapping) else {}
    kind = str(source.get("kind") or "color").strip().casefold()
    if kind not in UI_NAMED_STYLE_KINDS:
        kind = "color"
    allowed_keys = UI_STYLE_PROPERTY_KEYS[kind]
    properties = source.get("properties")
    properties = properties if isinstance(properties, Mapping) else {}
    token_bindings = source.get("token_bindings")
    token_bindings = (
        token_bindings if isinstance(token_bindings, Mapping) else {}
    )
    return {
        "id": str(source.get("id") or f"ui-style-{index + 1}"),
        "name": str(source.get("name") or f"Style {index + 1}"),
        "kind": kind,
        "properties": {
            str(key): copy.deepcopy(value)
            for key, value in properties.items()
            if str(key) in allowed_keys
        },
        "token_bindings": {
            str(path): str(token_id)
            for path, token_id in token_bindings.items()
            if str(path) in UI_STYLE_TOKEN_PATHS[kind] and str(token_id or "")
        },
        "description": str(source.get("description") or ""),
    }


def normalize_ui_style_ids(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(kind): str(style_id)
        for kind, style_id in value.items()
        if str(kind) in UI_NAMED_STYLE_KINDS and str(style_id or "")
    }


def extract_ui_named_style(
    row: Mapping[str, Any],
    *,
    kind: str,
) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().casefold()
    if normalized_kind not in UI_NAMED_STYLE_KINDS:
        raise ValueError(f"Unsupported UI style kind: {kind}")
    style = row.get("style")
    style = style if isinstance(style, Mapping) else {}
    properties = {
        key: copy.deepcopy(style[key])
        for key in UI_STYLE_PROPERTY_KEYS[normalized_kind]
        if key in style
    }
    bindings = row.get("token_bindings")
    bindings = bindings if isinstance(bindings, Mapping) else {}
    token_bindings = {
        str(path): str(token_id)
        for path, token_id in bindings.items()
        if str(path) in UI_STYLE_TOKEN_PATHS[normalized_kind]
        and str(token_id or "")
    }
    return {
        "kind": normalized_kind,
        "properties": properties,
        "token_bindings": token_bindings,
    }


def _next_style_id(rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"ui-style-{serial}" in used:
        serial += 1
    return f"ui-style-{serial}"


def _style_row(
    document: Mapping[str, Any],
    style_id: str,
) -> dict[str, Any]:
    row = next(
        (
            item
            for item in document["styles"]
            if item["id"] == str(style_id)
        ),
        None,
    )
    if row is None:
        raise ValueError(f"UI named style not found: {style_id}")
    return row


def inspect_ui_style_library(value: Mapping[str, Any]) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    usage = {row["id"]: [] for row in document["styles"]}
    for obj in document["objects"]:
        for kind, style_id in obj["style_ids"].items():
            if style_id in usage:
                usage[style_id].append(
                    {
                        "target_type": "object",
                        "target_id": obj["id"],
                        "target_name": obj["name"],
                        "kind": kind,
                    }
                )
    rows = [
        {
            **copy.deepcopy(style),
            "usage": usage[style["id"]],
            "usage_count": len(usage[style["id"]]),
        }
        for style in document["styles"]
    ]
    grid_usage = {
        row["id"]: [
            {
                "target_type": "artboard",
                "target_id": artboard["id"],
                "target_name": artboard["name"],
                "kind": "layout_grid",
            }
            for artboard in document["artboards"]
            if artboard.get("layout_grid_style_id") == row["id"]
        ]
        for row in document["layout_grid_styles"]
    }
    rows.extend(
        {
            "id": style["id"],
            "name": style["name"],
            "kind": "layout_grid",
            "properties": {
                "layout_grids": copy.deepcopy(style["layout_grids"])
            },
            "token_bindings": {},
            "description": style["description"],
            "usage": grid_usage[style["id"]],
            "usage_count": len(grid_usage[style["id"]]),
        }
        for style in document["layout_grid_styles"]
    )
    rows.sort(key=lambda row: (row["kind"], row["name"].casefold(), row["id"]))
    return {
        "schema": "tigerstudio.painter.ui.style_library.inspect.v1",
        "style_count": len(rows),
        "used_count": sum(bool(row["usage_count"]) for row in rows),
        "unused_count": sum(not row["usage_count"] for row in rows),
        "styles": rows,
        "kinds": {
            kind: [row for row in rows if row["kind"] == kind]
            for kind in UI_STYLE_KINDS
        },
    }


def add_ui_named_style(
    value: Mapping[str, Any],
    *,
    name: str,
    kind: str,
    properties: Mapping[str, Any] | None = None,
    token_bindings: Mapping[str, str] | None = None,
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    style_id = _next_style_id(document["styles"])
    row = normalize_ui_named_style(
        {
            "id": style_id,
            "name": name or "Style",
            "kind": kind,
            "properties": dict(properties or {}),
            "token_bindings": dict(token_bindings or {}),
            "description": description,
        },
        len(document["styles"]),
    )
    document["styles"].append(row)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError("Invalid UI named style: " + ", ".join(validation["errors"]))
    document["revision"] += 1
    return document, copy.deepcopy(row)


def _apply_style_to_object(
    row: dict[str, Any],
    style: Mapping[str, Any],
    *,
    previous: Mapping[str, Any] | None = None,
) -> None:
    kind = str(style["kind"])
    object_style = copy.deepcopy(dict(row.get("style") or {}))
    if previous is not None:
        for key in previous.get("properties", {}):
            object_style.pop(str(key), None)
    object_style.update(copy.deepcopy(dict(style["properties"])))
    row["style"] = object_style
    bindings = dict(row.get("token_bindings") or {})
    if previous is not None:
        for path in previous.get("token_bindings", {}):
            bindings.pop(str(path), None)
    bindings.update(copy.deepcopy(dict(style["token_bindings"])))
    row["token_bindings"] = bindings
    style_ids = normalize_ui_style_ids(row.get("style_ids"))
    style_ids[kind] = str(style["id"])
    row["style_ids"] = style_ids


def update_ui_named_style(
    value: Mapping[str, Any],
    style_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    for index, row in enumerate(document["styles"]):
        if row["id"] != str(style_id):
            continue
        allowed_changes = {
            key: copy.deepcopy(value)
            for key, value in changes.items()
            if key in {
                "name",
                "properties",
                "token_bindings",
                "description",
            }
        }
        updated = normalize_ui_named_style(
            {**row, **allowed_changes, "id": row["id"], "kind": row["kind"]},
            index,
        )
        document["styles"][index] = updated
        for obj in document["objects"]:
            if obj["style_ids"].get(row["kind"]) == row["id"]:
                _apply_style_to_object(obj, updated, previous=row)
        document["revision"] += 1
        document = normalize_ui_document(document)
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise ValueError(
                "Invalid UI named style update: "
                + ", ".join(validation["errors"])
            )
        return document, copy.deepcopy(updated)
    raise ValueError(f"UI named style not found: {style_id}")


def apply_ui_named_style(
    value: Mapping[str, Any],
    *,
    object_id: str,
    style_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    style = _style_row(document, style_id)
    obj = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(object_id)
        ),
        None,
    )
    if obj is None:
        raise ValueError(f"UI object not found: {object_id}")
    previous_id = obj["style_ids"].get(style["kind"], "")
    previous = (
        next(
            (row for row in document["styles"] if row["id"] == previous_id),
            None,
        )
        if previous_id
        else None
    )
    _apply_style_to_object(obj, style, previous=previous)
    document["revision"] += 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Invalid UI named style application: "
            + ", ".join(validation["errors"])
        )
    applied = next(row for row in document["objects"] if row["id"] == obj["id"])
    return document, copy.deepcopy(applied)


def unlink_ui_named_style(
    value: Mapping[str, Any],
    *,
    object_id: str,
    kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    obj = next(
        (
            row
            for row in document["objects"]
            if row["id"] == str(object_id)
        ),
        None,
    )
    if obj is None:
        raise ValueError(f"UI object not found: {object_id}")
    normalized_kind = str(kind).strip().casefold()
    if normalized_kind not in UI_NAMED_STYLE_KINDS:
        raise ValueError(f"Unsupported UI style kind: {kind}")
    style_ids = dict(obj["style_ids"])
    detached_style_id = str(style_ids.pop(normalized_kind, ""))
    obj["style_ids"] = style_ids
    document["revision"] += 1
    return document, {
        "object_id": obj["id"],
        "kind": normalized_kind,
        "detached_style_id": detached_style_id,
    }


def remove_ui_named_style(
    value: Mapping[str, Any],
    style_id: str,
    *,
    detach_references: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    style = _style_row(document, style_id)
    object_ids = [
        row["id"]
        for row in document["objects"]
        if row["style_ids"].get(style["kind"]) == style["id"]
    ]
    if object_ids and not detach_references:
        raise ValueError(f"UI named style is referenced: {style_id}")
    if detach_references:
        for row in document["objects"]:
            if row["style_ids"].get(style["kind"]) == style["id"]:
                row["style_ids"].pop(style["kind"], None)
    document["styles"] = [
        row for row in document["styles"] if row["id"] != style["id"]
    ]
    document["revision"] += 1
    return document, {
        "style_id": style["id"],
        "detached_object_ids": object_ids,
    }


def add_ui_style(
    value: Mapping[str, Any],
    *,
    name: str,
    kind: str,
    properties: Mapping[str, Any] | None = None,
    token_bindings: Mapping[str, str] | None = None,
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_kind = str(kind or "").strip().casefold()
    if normalized_kind == "layout_grid":
        from app.painter_ui_layout_grid_styles import add_ui_layout_grid_style

        return add_ui_layout_grid_style(
            value,
            name=name,
            layout_grids=list((properties or {}).get("layout_grids") or []),
            description=description,
        )
    return add_ui_named_style(
        value,
        name=name,
        kind=normalized_kind,
        properties=properties,
        token_bindings=token_bindings,
        description=description,
    )


def update_ui_style(
    value: Mapping[str, Any],
    style_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    grid_style = next(
        (
            row
            for row in document["layout_grid_styles"]
            if row["id"] == style_id
        ),
        None,
    )
    if grid_style is not None:
        from app.painter_ui_layout_grid_styles import update_ui_layout_grid_style

        properties = changes.get("properties")
        properties = properties if isinstance(properties, Mapping) else {}
        return update_ui_layout_grid_style(
            document,
            style_id,
            {
                "name": str(changes.get("name") or grid_style["name"]),
                "layout_grids": list(
                    properties.get("layout_grids")
                    or grid_style["layout_grids"]
                ),
                "description": str(
                    changes.get("description")
                    if "description" in changes
                    else grid_style["description"]
                ),
            },
        )
    return update_ui_named_style(document, style_id, changes)


def apply_ui_style(
    value: Mapping[str, Any],
    *,
    target_id: str,
    style_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    if style_id in {row["id"] for row in document["layout_grid_styles"]}:
        from app.painter_ui_layout_grid_styles import apply_ui_layout_grid_style

        return apply_ui_layout_grid_style(
            document,
            artboard_id=target_id,
            style_id=style_id,
        )
    return apply_ui_named_style(
        document,
        object_id=target_id,
        style_id=style_id,
    )


def unlink_ui_style(
    value: Mapping[str, Any],
    *,
    target_id: str,
    kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_kind = str(kind or "").strip().casefold()
    if normalized_kind == "layout_grid":
        from app.painter_ui_document import normalize_ui_document, update_ui_artboard

        document = normalize_ui_document(value)
        artboard = next(
            (
                row
                for row in document["artboards"]
                if row["id"] == str(target_id)
            ),
            None,
        )
        if artboard is None:
            raise ValueError(f"UI artboard not found: {target_id}")
        detached_style_id = str(artboard.get("layout_grid_style_id") or "")
        document, _row = update_ui_artboard(
            document,
            artboard["id"],
            {"layout_grid_style_id": ""},
        )
        return document, {
            "target_id": artboard["id"],
            "kind": normalized_kind,
            "detached_style_id": detached_style_id,
        }
    return unlink_ui_named_style(
        value,
        object_id=target_id,
        kind=normalized_kind,
    )


def remove_ui_style(
    value: Mapping[str, Any],
    style_id: str,
    *,
    detach_references: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    if style_id in {row["id"] for row in document["layout_grid_styles"]}:
        from app.painter_ui_layout_grid_styles import remove_ui_layout_grid_style

        return remove_ui_layout_grid_style(
            document,
            style_id,
            detach_references=detach_references,
        )
    return remove_ui_named_style(
        document,
        style_id,
        detach_references=detach_references,
    )


__all__ = [
    "UI_NAMED_STYLE_KINDS",
    "UI_STYLE_KINDS",
    "UI_STYLE_PROPERTY_KEYS",
    "add_ui_named_style",
    "add_ui_style",
    "apply_ui_named_style",
    "apply_ui_style",
    "extract_ui_named_style",
    "inspect_ui_style_library",
    "normalize_ui_named_style",
    "normalize_ui_style_ids",
    "remove_ui_named_style",
    "remove_ui_style",
    "unlink_ui_named_style",
    "unlink_ui_style",
    "update_ui_named_style",
    "update_ui_style",
]
