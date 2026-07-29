"""Variable collection and mode contracts for Painter UI documents."""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping


UI_VARIABLE_TYPES = ("color", "number", "string", "boolean")
UI_VARIABLE_COLLECTION_KINDS = (
    "theme",
    "density",
    "locale",
    "platform",
    "brand",
    "custom",
)
UI_VARIABLE_SCOPES = (
    "style.fill",
    "style.stroke",
    "style.text_color",
    "style.stroke_width",
    "style.radius",
    "style.shadow",
    "style.font_size",
    "layout.gap",
    "layout.cross_gap",
    "layout.padding.left",
    "layout.padding.top",
    "layout.padding.right",
    "layout.padding.bottom",
    "opacity",
    "content.source",
)
LEGACY_THEME_COLLECTION_ID = "ui-variable-collection-theme"
LEGACY_THEME_MODE_IDS = {
    "light": "ui-variable-mode-light",
    "dark": "ui-variable-mode-dark",
    "high_contrast": "ui-variable-mode-high-contrast",
}


def _slug(value: object, fallback: str) -> str:
    text = re.sub(
        r"[^a-z0-9]+",
        "-",
        str(value or "").strip().casefold(),
    ).strip("-")
    return text or fallback


def infer_ui_variable_type(kind: object) -> str:
    normalized = str(kind or "").strip().casefold()
    if normalized == "color":
        return "color"
    if normalized in {"spacing", "radius", "opacity"}:
        return "number"
    return "string"


def normalize_ui_variable_type(value: object, *, kind: object = "") -> str:
    normalized = str(value or "").strip().casefold()
    return (
        normalized
        if normalized in UI_VARIABLE_TYPES
        else infer_ui_variable_type(kind)
    )


def ui_variable_value_matches_type(value: Any, variable_type: object) -> bool:
    if value is None:
        return True
    normalized = normalize_ui_variable_type(variable_type)
    if normalized == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if normalized == "boolean":
        return isinstance(value, bool)
    if normalized == "color":
        return isinstance(value, str)
    # Rich legacy typography/image values remain valid string-like variables.
    return True


def default_ui_variable_collections() -> list[dict[str, Any]]:
    modes = [
        {
            "id": LEGACY_THEME_MODE_IDS["light"],
            "name": "Light",
            "key": "light",
        },
        {
            "id": LEGACY_THEME_MODE_IDS["dark"],
            "name": "Dark",
            "key": "dark",
        },
        {
            "id": LEGACY_THEME_MODE_IDS["high_contrast"],
            "name": "High Contrast",
            "key": "high_contrast",
        },
    ]
    return [
        {
            "id": LEGACY_THEME_COLLECTION_ID,
            "name": "Theme",
            "kind": "theme",
            "default_mode_id": modes[0]["id"],
            "modes": modes,
            "description": "",
        }
    ]


def _normalize_mode(
    row: Mapping[str, Any],
    index: int,
    *,
    collection_id: str,
) -> dict[str, str]:
    name = str(row.get("name") or f"Mode {index + 1}").strip()
    key = _slug(row.get("key") or name, f"mode-{index + 1}").replace("-", "_")
    return {
        "id": str(
            row.get("id")
            or f"{collection_id}-mode-{_slug(name, str(index + 1))}"
        ),
        "name": name,
        "key": key,
    }


def normalize_ui_variable_collection(
    row: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    collection_id = str(
        row.get("id") or f"ui-variable-collection-{index + 1}"
    )
    raw_modes = [
        value
        for value in (row.get("modes") or [])
        if isinstance(value, Mapping)
    ]
    if not raw_modes:
        raw_modes = [{"name": "Default", "key": "default"}]
    modes = [
        _normalize_mode(value, mode_index, collection_id=collection_id)
        for mode_index, value in enumerate(raw_modes)
    ]
    default_mode_id = str(row.get("default_mode_id") or modes[0]["id"])
    if default_mode_id not in {mode["id"] for mode in modes}:
        default_mode_id = modes[0]["id"]
    kind = str(row.get("kind") or "custom").strip().casefold()
    if kind not in UI_VARIABLE_COLLECTION_KINDS:
        kind = "custom"
    return {
        "id": collection_id,
        "name": str(row.get("name") or f"Collection {index + 1}"),
        "kind": kind,
        "default_mode_id": default_mode_id,
        "modes": modes,
        "description": str(row.get("description") or ""),
    }


def normalize_ui_variable_collections(value: object) -> list[dict[str, Any]]:
    rows = [
        row for row in (value or []) if isinstance(row, Mapping)
    ]
    if not rows:
        return default_ui_variable_collections()
    return [
        normalize_ui_variable_collection(row, index)
        for index, row in enumerate(rows)
    ]


def normalize_ui_variable_mode_values(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(mode_id): copy.deepcopy(mode_value)
        for mode_id, mode_value in value.items()
        if str(mode_id or "")
    }


def legacy_theme_mode_values(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        LEGACY_THEME_MODE_IDS[str(theme).strip().casefold()]: copy.deepcopy(
            mode_value
        )
        for theme, mode_value in value.items()
        if str(theme).strip().casefold() in LEGACY_THEME_MODE_IDS
    }


def normalize_ui_artboard_variable_modes(
    value: object,
    *,
    theme: object = "light",
) -> dict[str, str]:
    modes = (
        {
            str(collection_id): str(mode_id)
            for collection_id, mode_id in value.items()
            if str(collection_id or "") and str(mode_id or "")
        }
        if isinstance(value, Mapping)
        else {}
    )
    theme_key = str(theme or "light").strip().casefold()
    theme_key = theme_key.replace("-", "_").replace(" ", "_")
    modes.setdefault(
        LEGACY_THEME_COLLECTION_ID,
        LEGACY_THEME_MODE_IDS.get(
            theme_key,
            LEGACY_THEME_MODE_IDS["light"],
        ),
    )
    return modes


def inspect_ui_variable_collections(value: Mapping[str, Any]) -> dict[str, Any]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    token_counts = {
        row["id"]: 0 for row in document["variable_collections"]
    }
    for token in document["tokens"]:
        if token["collection_id"] in token_counts:
            token_counts[token["collection_id"]] += 1
    active_artboard = next(
        row
        for row in document["artboards"]
        if row["id"] == document["active_artboard_id"]
    )
    collections = []
    for collection in document["variable_collections"]:
        active_mode_id = active_artboard["variable_modes"].get(
            collection["id"],
            collection["default_mode_id"],
        )
        collections.append(
            {
                **copy.deepcopy(collection),
                "token_count": token_counts[collection["id"]],
                "active_mode_id": active_mode_id,
            }
        )
    return {
        "schema": "tigerstudio.painter.ui.variable_collections.inspect.v1",
        "active_artboard_id": active_artboard["id"],
        "collection_count": len(collections),
        "mode_count": sum(len(row["modes"]) for row in collections),
        "collections": collections,
    }


def _next_collection_id(rows: list[Mapping[str, Any]]) -> str:
    used = {str(row.get("id") or "") for row in rows}
    serial = 1
    while f"ui-variable-collection-{serial}" in used:
        serial += 1
    return f"ui-variable-collection-{serial}"


def _next_mode_id(collection: Mapping[str, Any]) -> str:
    used = {
        str(row.get("id") or "") for row in collection.get("modes", [])
    }
    serial = 1
    prefix = f"{collection['id']}-mode"
    while f"{prefix}-{serial}" in used:
        serial += 1
    return f"{prefix}-{serial}"


def add_ui_variable_collection(
    value: Mapping[str, Any],
    *,
    name: str,
    kind: str = "custom",
    description: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    collection_id = _next_collection_id(document["variable_collections"])
    row = normalize_ui_variable_collection(
        {
            "id": collection_id,
            "name": name or "Collection",
            "kind": kind,
            "description": description,
            "modes": [
                {
                    "id": f"{collection_id}-mode-default",
                    "name": "Default",
                    "key": "default",
                }
            ],
        },
        len(document["variable_collections"]),
    )
    document["variable_collections"].append(row)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError("Invalid variable collection: " + ", ".join(validation["errors"]))
    document["revision"] += 1
    return document, copy.deepcopy(row)


def update_ui_variable_collection(
    value: Mapping[str, Any],
    collection_id: str,
    changes: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document, validate_ui_document

    document = normalize_ui_document(value)
    for index, row in enumerate(document["variable_collections"]):
        if row["id"] != str(collection_id):
            continue
        allowed_changes = {
            key: copy.deepcopy(value)
            for key, value in dict(changes).items()
            if key in {"name", "kind", "description"}
        }
        updated = normalize_ui_variable_collection(
            {**row, **allowed_changes, "id": row["id"]},
            index,
        )
        document["variable_collections"][index] = updated
        validation = validate_ui_document(document)
        if not validation["ok"]:
            raise ValueError(
                "Invalid variable collection update: "
                + ", ".join(validation["errors"])
            )
        document["revision"] += 1
        return document, copy.deepcopy(updated)
    raise ValueError(f"Variable collection not found: {collection_id}")


def remove_ui_variable_collection(
    value: Mapping[str, Any],
    collection_id: str,
    *,
    detach_tokens: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    target = next(
        (
            row
            for row in document["variable_collections"]
            if row["id"] == str(collection_id)
        ),
        None,
    )
    if target is None:
        raise ValueError(f"Variable collection not found: {collection_id}")
    if len(document["variable_collections"]) <= 1:
        raise ValueError("A UI document must retain at least one variable collection")
    token_ids = [
        row["id"]
        for row in document["tokens"]
        if row["collection_id"] == target["id"]
    ]
    if token_ids and not detach_tokens:
        raise ValueError(f"Variable collection is referenced: {collection_id}")
    fallback = next(
        row
        for row in document["variable_collections"]
        if row["id"] != target["id"]
    )
    if detach_tokens:
        for token in document["tokens"]:
            if token["collection_id"] == target["id"]:
                token["collection_id"] = fallback["id"]
                token["mode_values"] = {}
    document["variable_collections"] = [
        row
        for row in document["variable_collections"]
        if row["id"] != target["id"]
    ]
    for artboard in document["artboards"]:
        artboard["variable_modes"].pop(target["id"], None)
    document["revision"] += 1
    return document, {
        "collection_id": target["id"],
        "detached_token_ids": token_ids,
        "fallback_collection_id": fallback["id"] if token_ids else "",
    }


def add_ui_variable_mode(
    value: Mapping[str, Any],
    *,
    collection_id: str,
    name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    collection = next(
        (
            row
            for row in document["variable_collections"]
            if row["id"] == str(collection_id)
        ),
        None,
    )
    if collection is None:
        raise ValueError(f"Variable collection not found: {collection_id}")
    mode = _normalize_mode(
        {
            "id": _next_mode_id(collection),
            "name": name or "Mode",
        },
        len(collection["modes"]),
        collection_id=collection["id"],
    )
    collection["modes"].append(mode)
    document["revision"] += 1
    return document, copy.deepcopy(mode)


def update_ui_variable_mode(
    value: Mapping[str, Any],
    *,
    collection_id: str,
    mode_id: str,
    name: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    collection = next(
        (
            row
            for row in document["variable_collections"]
            if row["id"] == str(collection_id)
        ),
        None,
    )
    if collection is None:
        raise ValueError(f"Variable collection not found: {collection_id}")
    for index, mode in enumerate(collection["modes"]):
        if mode["id"] != str(mode_id):
            continue
        updated = _normalize_mode(
            {**mode, "name": name or mode["name"], "id": mode["id"]},
            index,
            collection_id=collection["id"],
        )
        collection["modes"][index] = updated
        if collection["kind"] == "theme":
            for token in document["tokens"]:
                if token["collection_id"] != collection["id"]:
                    continue
                if mode["key"] in token["theme_values"]:
                    token["theme_values"][updated["key"]] = token[
                        "theme_values"
                    ].pop(mode["key"])
        document["revision"] += 1
        return document, copy.deepcopy(updated)
    raise ValueError(f"Variable mode not found: {mode_id}")


def remove_ui_variable_mode(
    value: Mapping[str, Any],
    *,
    collection_id: str,
    mode_id: str,
    detach_values: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    collection = next(
        (
            row
            for row in document["variable_collections"]
            if row["id"] == str(collection_id)
        ),
        None,
    )
    if collection is None:
        raise ValueError(f"Variable collection not found: {collection_id}")
    if len(collection["modes"]) <= 1:
        raise ValueError("A variable collection must retain at least one mode")
    target = next(
        (row for row in collection["modes"] if row["id"] == str(mode_id)),
        None,
    )
    if target is None:
        raise ValueError(f"Variable mode not found: {mode_id}")
    token_ids = [
        row["id"]
        for row in document["tokens"]
        if target["id"] in row["mode_values"]
    ]
    active_artboard_ids = [
        row["id"]
        for row in document["artboards"]
        if row["variable_modes"].get(collection["id"]) == target["id"]
    ]
    if (token_ids or active_artboard_ids) and not detach_values:
        raise ValueError(f"Variable mode is referenced: {mode_id}")
    fallback_id = next(
        row["id"] for row in collection["modes"] if row["id"] != target["id"]
    )
    collection["modes"] = [
        row for row in collection["modes"] if row["id"] != target["id"]
    ]
    if collection["default_mode_id"] == target["id"]:
        collection["default_mode_id"] = fallback_id
    for token in document["tokens"]:
        token["mode_values"].pop(target["id"], None)
        if collection["kind"] == "theme":
            token["theme_values"].pop(target["key"], None)
    for artboard in document["artboards"]:
        if artboard["variable_modes"].get(collection["id"]) == target["id"]:
            artboard["variable_modes"][collection["id"]] = fallback_id
            if collection["kind"] == "theme":
                fallback = next(
                    row for row in collection["modes"] if row["id"] == fallback_id
                )
                artboard["theme"] = fallback["key"]
    document["revision"] += 1
    return document, {
        "collection_id": collection["id"],
        "mode_id": target["id"],
        "detached_token_ids": token_ids,
        "updated_artboard_ids": active_artboard_ids,
        "fallback_mode_id": fallback_id,
    }


def set_ui_variable_mode(
    value: Mapping[str, Any],
    *,
    artboard_id: str,
    collection_id: str,
    mode_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.painter_ui_document import normalize_ui_document

    document = normalize_ui_document(value)
    collection = next(
        (
            row
            for row in document["variable_collections"]
            if row["id"] == str(collection_id)
        ),
        None,
    )
    if collection is None:
        raise ValueError(f"Variable collection not found: {collection_id}")
    mode = next(
        (row for row in collection["modes"] if row["id"] == str(mode_id)),
        None,
    )
    if mode is None:
        raise ValueError(f"Variable mode not found: {mode_id}")
    artboard = next(
        (
            row
            for row in document["artboards"]
            if row["id"] == str(artboard_id)
        ),
        None,
    )
    if artboard is None:
        raise ValueError(f"UI artboard not found: {artboard_id}")
    artboard["variable_modes"][collection["id"]] = mode["id"]
    if collection["kind"] == "theme":
        artboard["theme"] = mode["key"]
    document["revision"] += 1
    return document, {
        "artboard_id": artboard["id"],
        "collection_id": collection["id"],
        "mode_id": mode["id"],
    }


__all__ = [
    "LEGACY_THEME_COLLECTION_ID",
    "LEGACY_THEME_MODE_IDS",
    "UI_VARIABLE_COLLECTION_KINDS",
    "UI_VARIABLE_SCOPES",
    "UI_VARIABLE_TYPES",
    "add_ui_variable_collection",
    "add_ui_variable_mode",
    "default_ui_variable_collections",
    "infer_ui_variable_type",
    "inspect_ui_variable_collections",
    "legacy_theme_mode_values",
    "normalize_ui_artboard_variable_modes",
    "normalize_ui_variable_collection",
    "normalize_ui_variable_collections",
    "normalize_ui_variable_mode_values",
    "normalize_ui_variable_type",
    "remove_ui_variable_collection",
    "remove_ui_variable_mode",
    "set_ui_variable_mode",
    "update_ui_variable_collection",
    "update_ui_variable_mode",
    "ui_variable_value_matches_type",
]
