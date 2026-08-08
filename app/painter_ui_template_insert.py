"""Stable-ID template insertion for Painter UI documents."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


INSERT_MODES = ("new_document", "page", "component_set", "theme")


def _all_ids(document: Mapping[str, Any]) -> set[str]:
    values = {
        str(row["id"])
        for key in (
            "pages",
            "artboards",
            "objects",
            "components",
            "styles",
            "variable_collections",
            "tokens",
            "interactions",
            "sections",
            "layout_grid_styles",
        )
        for row in document[key]
    }
    values.update(
        str(mode["id"])
        for collection in document["variable_collections"]
        for mode in collection.get("modes") or []
    )
    return values


def _next_id(source_id: str, namespace: str, used: set[str]) -> str:
    stem = f"{namespace}-{source_id}".strip("-")
    candidate = stem
    serial = 2
    while candidate in used:
        candidate = f"{stem}-{serial}"
        serial += 1
    used.add(candidate)
    return candidate


def _namespace(template_id: str) -> str:
    value = "".join(
        character if character.isalnum() else "-"
        for character in str(template_id or "template").casefold()
    ).strip("-")
    return f"tpl-{value or 'template'}"


def _build_maps(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
    namespace: str,
) -> dict[str, dict[str, str]]:
    used = _all_ids(target)
    maps: dict[str, dict[str, str]] = {}
    for key in (
        "pages",
        "artboards",
        "objects",
        "components",
        "styles",
        "variable_collections",
        "tokens",
        "interactions",
        "sections",
        "layout_grid_styles",
    ):
        maps[key] = {
            str(row["id"]): _next_id(str(row["id"]), namespace, used)
            for row in source[key]
        }
    maps["variable_modes"] = {
        str(mode["id"]): _next_id(str(mode["id"]), namespace, used)
        for collection in source["variable_collections"]
        for mode in collection.get("modes") or []
    }
    return maps


def _map(value: Any, mapping: Mapping[str, str]) -> str:
    key = str(value or "")
    return mapping.get(key, key) if key else ""


def _clone_collections(
    source: Mapping[str, Any],
    maps: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for source_row in source["variable_collections"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["variable_collections"][str(source_row["id"])]
        for mode in row.get("modes") or []:
            mode["id"] = maps["variable_modes"][str(mode["id"])]
        row["default_mode_id"] = _map(
            source_row.get("default_mode_id"),
            maps["variable_modes"],
        )
        rows.append(row)
    return rows


def _clone_tokens(
    source: Mapping[str, Any],
    maps: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for source_row in source["tokens"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["tokens"][str(source_row["id"])]
        row["collection_id"] = _map(
            source_row.get("collection_id"),
            maps["variable_collections"],
        )
        row["alias_token_id"] = _map(
            source_row.get("alias_token_id"),
            maps["tokens"],
        )
        row["mode_values"] = {
            _map(mode_id, maps["variable_modes"]): copy.deepcopy(value)
            for mode_id, value in dict(
                source_row.get("mode_values") or {}
            ).items()
        }
        rows.append(row)
    return rows


def _clone_styles(
    source: Mapping[str, Any],
    maps: Mapping[str, Mapping[str, str]],
    key: str,
) -> list[dict[str, Any]]:
    rows = []
    for source_row in source[key]:
        row = copy.deepcopy(source_row)
        row["id"] = maps[key][str(source_row["id"])]
        row["token_bindings"] = {
            str(path): _map(token_id, maps["tokens"])
            for path, token_id in dict(
                source_row.get("token_bindings") or {}
            ).items()
        }
        rows.append(row)
    return rows


def _clone_object(
    source_row: Mapping[str, Any],
    maps: Mapping[str, Mapping[str, str]],
    *,
    target_artboard_id: str = "",
) -> dict[str, Any]:
    row = copy.deepcopy(source_row)
    row["id"] = maps["objects"][str(source_row["id"])]
    row["artboard_id"] = (
        target_artboard_id
        or _map(source_row.get("artboard_id"), maps["artboards"])
    )
    for field in (
        "parent_id",
        "component_source_object_id",
        "component_scope_source_object_id",
    ):
        row[field] = _map(source_row.get(field), maps["objects"])
    for field in ("component_id", "component_scope_id"):
        row[field] = _map(source_row.get(field), maps["components"])
    row["style_ids"] = {
        str(kind): _map(style_id, maps["styles"])
        for kind, style_id in dict(source_row.get("style_ids") or {}).items()
    }
    row["token_bindings"] = {
        str(path): _map(token_id, maps["tokens"])
        for path, token_id in dict(
            source_row.get("token_bindings") or {}
        ).items()
    }
    mask = copy.deepcopy(dict(row.get("mask") or {}))
    mask["target_ids"] = [
        _map(item, maps["objects"]) for item in mask.get("target_ids") or []
    ]
    row["mask"] = mask
    content = copy.deepcopy(dict(row.get("content") or {}))
    boolean = copy.deepcopy(dict(content.get("boolean") or {}))
    if boolean:
        boolean["operand_ids"] = [
            _map(item, maps["objects"])
            for item in boolean.get("operand_ids") or []
        ]
        content["boolean"] = boolean
    row["content"] = content
    return row


def _append_foundation(
    result: dict[str, Any],
    source: Mapping[str, Any],
    maps: Mapping[str, Mapping[str, str]],
) -> None:
    result["variable_collections"].extend(_clone_collections(source, maps))
    result["tokens"].extend(_clone_tokens(source, maps))
    result["styles"].extend(_clone_styles(source, maps, "styles"))
    result["layout_grid_styles"].extend(
        _clone_styles(source, maps, "layout_grid_styles")
    )


def _insert_pages(
    target: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    template_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = normalize_ui_document(target)
    maps = _build_maps(source, result, _namespace(template_id))
    _append_foundation(result, source, maps)
    current_right = max(
        (
            float(row["x"]) + float(row["width"])
            for row in result["artboards"]
        ),
        default=0.0,
    )
    source_left = min(
        (float(row["x"]) for row in source["artboards"]),
        default=0.0,
    )
    offset_x = current_right + 160.0 - source_left
    for source_row in source["pages"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["pages"][str(source_row["id"])]
        row["active_artboard_id"] = _map(
            source_row.get("active_artboard_id"),
            maps["artboards"],
        )
        result["pages"].append(row)
    for source_row in source["artboards"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["artboards"][str(source_row["id"])]
        row["page_id"] = _map(source_row.get("page_id"), maps["pages"])
        row["x"] = float(source_row.get("x") or 0.0) + offset_x
        row["layout_grid_style_id"] = _map(
            source_row.get("layout_grid_style_id"),
            maps["layout_grid_styles"],
        )
        row["variable_modes"] = {
            _map(collection_id, maps["variable_collections"]): _map(
                mode_id,
                maps["variable_modes"],
            )
            for collection_id, mode_id in dict(
                source_row.get("variable_modes") or {}
            ).items()
        }
        result["artboards"].append(row)
    result["objects"].extend(
        _clone_object(row, maps) for row in source["objects"]
    )
    for source_row in source["components"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["components"][str(source_row["id"])]
        row["root_object_id"] = _map(
            source_row.get("root_object_id"), maps["objects"]
        )
        row["base_component_id"] = _map(
            source_row.get("base_component_id"), maps["components"]
        )
        row["variant_ids"] = [
            _map(item, maps["components"])
            for item in source_row.get("variant_ids") or []
        ]
        result["components"].append(row)
    for source_row in source["interactions"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["interactions"][str(source_row["id"])]
        row["source_object_id"] = _map(
            source_row.get("source_object_id"), maps["objects"]
        )
        row["target_object_id"] = _map(
            source_row.get("target_object_id"), maps["objects"]
        )
        row["target_artboard_id"] = _map(
            source_row.get("target_artboard_id"), maps["artboards"]
        )
        row["component_id"] = _map(
            source_row.get("component_id"), maps["components"]
        )
        result["interactions"].append(row)
    for source_row in source["sections"]:
        row = copy.deepcopy(source_row)
        row["id"] = maps["sections"][str(source_row["id"])]
        row["object_ids"] = [
            _map(item, maps["objects"])
            for item in source_row.get("object_ids") or []
        ]
        if "page_id" in row:
            row["page_id"] = _map(source_row.get("page_id"), maps["pages"])
        result["sections"].append(row)
    result["active_page_id"] = _map(
        source["active_page_id"], maps["pages"]
    )
    result["active_artboard_id"] = _map(
        source["active_artboard_id"], maps["artboards"]
    )
    return result, {
        "inserted_pages": len(source["pages"]),
        "inserted_artboards": len(source["artboards"]),
        "inserted_objects": len(source["objects"]),
        "inserted_components": len(source["components"]),
    }


def _insert_component_set(
    target: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    template_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = normalize_ui_document(target)
    maps = _build_maps(source, result, _namespace(template_id))
    _append_foundation(result, source, maps)
    component_ids = {str(row["id"]) for row in source["components"]}
    root_ids = {
        str(row.get("root_object_id") or "") for row in source["components"]
    }
    children: dict[str, list[str]] = {}
    objects_by_id = {str(row["id"]): row for row in source["objects"]}
    for row in source["objects"]:
        children.setdefault(str(row.get("parent_id") or ""), []).append(
            str(row["id"])
        )
    object_ids: set[str] = set()

    def collect(object_id: str) -> None:
        if not object_id or object_id in object_ids:
            return
        object_ids.add(object_id)
        for child_id in children.get(object_id, []):
            collect(child_id)

    for root_id in root_ids:
        collect(root_id)
    target_artboard = result["active_artboard_id"]
    right = max(
        (
            float(row["x"]) + float(row["width"])
            for row in result["objects"]
            if row["artboard_id"] == target_artboard
        ),
        default=0.0,
    )
    source_left = min(
        (float(objects_by_id[item]["x"]) for item in object_ids),
        default=0.0,
    )
    for source_row in source["objects"]:
        if str(source_row["id"]) not in object_ids:
            continue
        row = _clone_object(
            source_row,
            maps,
            target_artboard_id=target_artboard,
        )
        row["x"] = float(source_row.get("x") or 0.0) - source_left + right + 80.0
        result["objects"].append(row)
    for source_row in source["components"]:
        if str(source_row["id"]) not in component_ids:
            continue
        row = copy.deepcopy(source_row)
        row["id"] = maps["components"][str(source_row["id"])]
        row["root_object_id"] = _map(
            source_row.get("root_object_id"), maps["objects"]
        )
        row["base_component_id"] = _map(
            source_row.get("base_component_id"), maps["components"]
        )
        row["variant_ids"] = [
            _map(item, maps["components"])
            for item in source_row.get("variant_ids") or []
        ]
        result["components"].append(row)
    return result, {
        "inserted_components": len(component_ids),
        "inserted_objects": len(object_ids),
    }


def _apply_theme(
    target: Mapping[str, Any],
    source: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    result = normalize_ui_document(target)
    used = _all_ids(result)
    collection_map: dict[str, str] = {}
    mode_map: dict[str, str] = {}
    for source_collection in source["variable_collections"]:
        target_collection = next(
            (
                row
                for row in result["variable_collections"]
                if str(row["name"]).casefold()
                == str(source_collection["name"]).casefold()
            ),
            None,
        )
        if target_collection is None:
            target_collection = copy.deepcopy(source_collection)
            target_collection["id"] = _next_id(
                str(source_collection["id"]), "theme", used
            )
            target_collection["modes"] = []
            result["variable_collections"].append(target_collection)
        collection_map[str(source_collection["id"])] = str(
            target_collection["id"]
        )
        for source_mode in source_collection.get("modes") or []:
            target_mode = next(
                (
                    row
                    for row in target_collection.get("modes") or []
                    if str(row.get("key") or row.get("name") or "").casefold()
                    == str(
                        source_mode.get("key")
                        or source_mode.get("name")
                        or ""
                    ).casefold()
                ),
                None,
            )
            if target_mode is None:
                target_mode = copy.deepcopy(source_mode)
                target_mode["id"] = _next_id(
                    str(source_mode["id"]), "theme", used
                )
                target_collection.setdefault("modes", []).append(target_mode)
            mode_map[str(source_mode["id"])] = str(target_mode["id"])
        target_collection["default_mode_id"] = mode_map.get(
            str(source_collection.get("default_mode_id") or ""),
            str(target_collection.get("default_mode_id") or ""),
        )
    token_map: dict[str, str] = {}
    changed_tokens = 0
    for source_token in source["tokens"]:
        target_token = next(
            (
                row
                for row in result["tokens"]
                if str(row["name"]).casefold()
                == str(source_token["name"]).casefold()
                and str(row["kind"]) == str(source_token["kind"])
            ),
            None,
        )
        if target_token is None:
            target_token = copy.deepcopy(source_token)
            target_token["id"] = _next_id(
                str(source_token["id"]), "theme", used
            )
            result["tokens"].append(target_token)
        stable_id = str(target_token["id"])
        target_token.update(copy.deepcopy(source_token))
        target_token["id"] = stable_id
        target_token["collection_id"] = _map(
            source_token.get("collection_id"), collection_map
        )
        target_token["mode_values"] = {
            _map(mode_id, mode_map): copy.deepcopy(value)
            for mode_id, value in dict(
                source_token.get("mode_values") or {}
            ).items()
        }
        token_map[str(source_token["id"])] = stable_id
        changed_tokens += 1
    for source_token in source["tokens"]:
        target_id = token_map[str(source_token["id"])]
        target_token = next(row for row in result["tokens"] if row["id"] == target_id)
        target_token["alias_token_id"] = _map(
            source_token.get("alias_token_id"), token_map
        )
    for key in ("styles", "layout_grid_styles"):
        for source_style in source[key]:
            target_style = next(
                (
                    row
                    for row in result[key]
                    if str(row.get("name") or "").casefold()
                    == str(source_style.get("name") or "").casefold()
                    and str(row.get("kind") or "")
                    == str(source_style.get("kind") or "")
                ),
                None,
            )
            if target_style is None:
                target_style = copy.deepcopy(source_style)
                target_style["id"] = _next_id(
                    str(source_style["id"]), "theme", used
                )
                result[key].append(target_style)
            stable_id = str(target_style["id"])
            target_style.update(copy.deepcopy(source_style))
            target_style["id"] = stable_id
            target_style["token_bindings"] = {
                str(path): _map(token_id, token_map)
                for path, token_id in dict(
                    source_style.get("token_bindings") or {}
                ).items()
            }
    active_artboard = next(
        row
        for row in result["artboards"]
        if row["id"] == result["active_artboard_id"]
    )
    for source_collection in source["variable_collections"]:
        collection_id = collection_map[str(source_collection["id"])]
        active_artboard["variable_modes"][collection_id] = mode_map.get(
            str(source_collection.get("default_mode_id") or ""),
            "",
        )
    return result, {
        "updated_tokens": changed_tokens,
        "theme_collections": len(source["variable_collections"]),
    }


def insert_ui_template(
    target: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    template_id: str,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    insert_mode = str(mode or "").strip().casefold()
    if insert_mode not in INSERT_MODES:
        raise ValueError(f"Unsupported template insert mode: {mode}")
    normalized_source = normalize_ui_document(source)
    if insert_mode == "new_document":
        result = normalized_source
        details = {
            "inserted_pages": len(result["pages"]),
            "inserted_artboards": len(result["artboards"]),
            "inserted_objects": len(result["objects"]),
        }
    elif insert_mode == "page":
        result, details = _insert_pages(
            target,
            normalized_source,
            template_id=template_id,
        )
    elif insert_mode == "component_set":
        result, details = _insert_component_set(
            target,
            normalized_source,
            template_id=template_id,
        )
    else:
        result, details = _apply_theme(target, normalized_source)
    result["selection"] = {"object_id": "", "object_ids": []}
    result["revision"] = int(result.get("revision") or 0) + 1
    result = normalize_ui_document(result)
    validation = validate_ui_document(result)
    if not validation["ok"]:
        raise ValueError(
            "Template insertion produced an invalid document: "
            + ", ".join(validation["errors"])
        )
    return result, {
        "schema": "tigerstudio.painter.ui.template_insert.v1",
        "template_id": str(template_id),
        "mode": insert_mode,
        **details,
    }


__all__ = ["INSERT_MODES", "insert_ui_template"]
