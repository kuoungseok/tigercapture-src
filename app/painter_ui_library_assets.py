"""Search and insert installed Painter UI library assets."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import (
    add_ui_object,
    normalize_ui_document,
    update_ui_artboard,
    update_ui_object,
    validate_ui_document,
)
from app.painter_ui_library_import import (
    _active_package,
    _extract_resources,
    insert_ui_library_component,
)
from app.painter_ui_library_store import (
    default_ui_library_store_root,
    inspect_ui_library_store,
    read_ui_library_package,
)


ASSET_KINDS = ("component", "style", "token", "image", "font")


def _active_packages(store_root: Path) -> list[dict[str, Any]]:
    report = inspect_ui_library_store(store_root=store_root)
    return [dict(row) for row in report["packages"] if row["active"]]


def search_ui_library_assets(
    *,
    query: str = "",
    kind: str = "",
    library_id: str = "",
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(
        store_root or default_ui_library_store_root()
    ).expanduser().resolve()
    query_key = str(query or "").strip().casefold()
    kind_key = str(kind or "").strip().casefold()
    if kind_key and kind_key not in ASSET_KINDS:
        raise ValueError(f"Unsupported library asset kind: {kind}")
    rows: list[dict[str, Any]] = []
    for package_row in _active_packages(root):
        package_id = str(package_row["id"])
        if library_id and package_id != str(library_id):
            continue
        package = read_ui_library_package(package_row["installed_path"])
        payload = package["payload"]
        sources = (
            ("component", payload.get("components") or []),
            ("style", payload.get("styles") or []),
            ("style", payload.get("layout_grid_styles") or []),
            ("token", payload.get("tokens") or []),
            ("resource", payload.get("resources") or []),
        )
        for source_kind, items in sources:
            for item in items:
                asset_kind = (
                    str(item.get("kind") or "")
                    if source_kind == "resource"
                    else source_kind
                )
                if asset_kind not in ASSET_KINDS:
                    continue
                if kind_key and asset_kind != kind_key:
                    continue
                name = str(item.get("name") or item.get("id") or "")
                haystack = " ".join(
                    (
                        name,
                        package_id,
                        str(package_row.get("name") or ""),
                        asset_kind,
                    )
                ).casefold()
                if query_key and query_key not in haystack:
                    continue
                rows.append(
                    {
                        "library_id": package_id,
                        "library_name": str(package_row.get("name") or ""),
                        "version": int(package_row["version"]),
                        "kind": asset_kind,
                        "asset_id": str(item["id"]),
                        "name": name,
                        "license": copy.deepcopy(package_row.get("license") or {}),
                        "details": {
                            "style_kind": (
                                str(item.get("kind") or "")
                                if source_kind == "style"
                                else ""
                            ),
                            "style_collection": (
                                "layout_grid_styles"
                                if item in (payload.get("layout_grid_styles") or [])
                                else "styles"
                                if source_kind == "style"
                                else ""
                            ),
                            "token_kind": (
                                str(item.get("kind") or "")
                                if source_kind == "token"
                                else ""
                            ),
                            "size_bytes": int(item.get("size_bytes") or 0),
                        },
                    }
                )
    rows.sort(
        key=lambda row: (
            row["library_name"].casefold(),
            ASSET_KINDS.index(row["kind"]),
            row["name"].casefold(),
        )
    )
    return {
        "schema": "tigerstudio.painter.ui.library_asset_search.v1",
        "query": query_key,
        "filters": {"kind": kind_key, "library_id": str(library_id or "")},
        "count": len(rows),
        "assets": rows,
        "facets": {
            "kinds": [
                value for value in ASSET_KINDS if any(
                    row["kind"] == value for row in rows
                )
            ],
            "libraries": sorted({row["library_id"] for row in rows}),
        },
    }


def _source_marker(
    library_id: str,
    version: int,
    kind: str,
    asset_id: str,
) -> dict[str, Any]:
    return {
        "library_id": str(library_id),
        "version": int(version),
        "kind": str(kind),
        "asset_id": str(asset_id),
    }


def _asset_links(document: dict[str, Any]) -> list[dict[str, Any]]:
    links = document["linked_targets"].setdefault("library_assets", [])
    if not isinstance(links, list):
        links = []
        document["linked_targets"]["library_assets"] = links
    return links


def _existing_link(
    document: dict[str, Any],
    marker: Mapping[str, Any],
) -> dict[str, Any] | None:
    return next(
        (
            row
            for row in _asset_links(document)
            if all(row.get(key) == value for key, value in marker.items())
        ),
        None,
    )


def _next_id(prefix: str, document: Mapping[str, Any]) -> str:
    used = {
        str(row["id"])
        for key in (
            "styles",
            "layout_grid_styles",
            "variable_collections",
            "tokens",
        )
        for row in document[key]
    }
    used.update(
        str(mode["id"])
        for collection in document["variable_collections"]
        for mode in collection.get("modes") or []
    )
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    return f"{prefix}-{serial}"


def _all_mode_ids(document: Mapping[str, Any]) -> set[str]:
    return {
        str(mode["id"])
        for collection in document["variable_collections"]
        for mode in collection.get("modes") or []
    }


def _import_collection_and_token(
    document: dict[str, Any],
    payload: Mapping[str, Any],
    token_id: str,
    *,
    marker_base: Mapping[str, Any],
) -> str:
    source_token = next(
        row for row in payload.get("tokens") or []
        if str(row["id"]) == str(token_id)
    )
    token_marker = {
        **marker_base,
        "kind": "token",
        "asset_id": str(source_token["id"]),
    }
    existing = _existing_link(document, token_marker)
    if existing:
        return str(existing["target_id"])
    source_collection_id = str(source_token.get("collection_id") or "")
    target_collection_id = ""
    mode_map: dict[str, str] = {}
    if source_collection_id:
        source_collection = next(
            row for row in payload.get("variable_collections") or []
            if str(row["id"]) == source_collection_id
        )
        collection_marker = {
            **marker_base,
            "kind": "variable_collection",
            "asset_id": source_collection_id,
        }
        collection_link = _existing_link(document, collection_marker)
        if collection_link:
            target_collection_id = str(collection_link["target_id"])
            target_collection = next(
                row for row in document["variable_collections"]
                if row["id"] == target_collection_id
            )
            for source_mode, target_mode in zip(
                source_collection.get("modes") or [],
                target_collection.get("modes") or [],
            ):
                mode_map[str(source_mode["id"])] = str(target_mode["id"])
        else:
            target_collection = copy.deepcopy(source_collection)
            target_collection_id = _next_id(
                "ui-library-variable-collection", document
            )
            target_collection["id"] = target_collection_id
            reserved_modes: set[str] = set()
            for mode in target_collection.get("modes") or []:
                source_mode_id = str(mode["id"])
                serial = 1
                while (
                    candidate := f"ui-library-variable-mode-{serial}"
                ) in _all_mode_ids(document) | reserved_modes:
                    serial += 1
                mode["id"] = candidate
                reserved_modes.add(candidate)
                mode_map[source_mode_id] = str(mode["id"])
            target_collection["default_mode_id"] = mode_map.get(
                str(source_collection.get("default_mode_id") or ""),
                "",
            )
            document["variable_collections"].append(target_collection)
            _asset_links(document).append(
                {**collection_marker, "target_id": target_collection_id}
            )
    target_id = _next_id("ui-library-token", document)
    clone = copy.deepcopy(source_token)
    clone["id"] = target_id
    clone["collection_id"] = target_collection_id
    clone["mode_values"] = {
        mode_map.get(str(mode_id), str(mode_id)): copy.deepcopy(value)
        for mode_id, value in dict(source_token.get("mode_values") or {}).items()
    }
    clone["alias_token_id"] = ""
    document["tokens"].append(clone)
    _asset_links(document).append({**token_marker, "target_id": target_id})
    source_alias_id = str(source_token.get("alias_token_id") or "")
    if source_alias_id:
        clone["alias_token_id"] = _import_collection_and_token(
            document,
            payload,
            source_alias_id,
            marker_base=marker_base,
        )
    return target_id


def _selected_object(document: Mapping[str, Any]) -> dict[str, Any]:
    object_id = str(document["selection"].get("object_id") or "")
    row = next(
        (item for item in document["objects"] if item["id"] == object_id),
        None,
    )
    if row is None:
        raise ValueError("Select a compatible UI object before applying this asset")
    return row


def insert_ui_library_asset(
    value: Mapping[str, Any],
    *,
    library_id: str,
    asset_id: str,
    kind: str,
    version: int = 0,
    property_path: str = "",
    x: float = 64.0,
    y: float = 64.0,
    store_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    asset_kind = str(kind or "").casefold()
    if asset_kind not in ASSET_KINDS:
        raise ValueError(f"Unsupported library asset kind: {kind}")
    if asset_kind == "component":
        return insert_ui_library_component(
            value,
            library_id=library_id,
            component_id=asset_id,
            version=version,
            x=x,
            y=y,
            store_root=store_root,
        )
    document = normalize_ui_document(value)
    root = Path(
        store_root or default_ui_library_store_root()
    ).expanduser().resolve()
    package_row = _active_package(
        library_id,
        version=int(version),
        store_root=root,
    )
    package = read_ui_library_package(package_row["installed_path"])
    payload = package["payload"]
    resolved_version = int(package["manifest"]["version"])
    marker = _source_marker(
        library_id,
        resolved_version,
        asset_kind,
        asset_id,
    )
    target_id = ""
    if asset_kind == "token":
        source = next(
            row for row in payload.get("tokens") or []
            if str(row["id"]) == str(asset_id)
        )
        target_id = _import_collection_and_token(
            document,
            payload,
            str(asset_id),
            marker_base={
                "library_id": str(library_id),
                "version": resolved_version,
            },
        )
        path = str(property_path or "").strip()
        if not path:
            path = str(next(iter(source.get("scope") or []), "style.fill"))
        selected = _selected_object(document)
        bindings = dict(selected.get("token_bindings") or {})
        bindings[path] = target_id
        document, _row = update_ui_object(
            document,
            selected["id"],
            {"token_bindings": bindings},
        )
    elif asset_kind == "style":
        style_collection = "styles"
        source = next(
            (
                row
                for row in payload.get("styles") or []
                if str(row["id"]) == str(asset_id)
            ),
            None,
        )
        if source is None:
            style_collection = "layout_grid_styles"
            source = next(
                row
                for row in payload.get("layout_grid_styles") or []
                if str(row["id"]) == str(asset_id)
            )
        existing = _existing_link(document, marker)
        if existing:
            target_id = str(existing["target_id"])
        else:
            clone = copy.deepcopy(source)
            target_id = _next_id("ui-library-style", document)
            clone["id"] = target_id
            clone["token_bindings"] = {
                str(path): _import_collection_and_token(
                    document,
                    payload,
                    str(token_id),
                    marker_base={
                        "library_id": str(library_id),
                        "version": resolved_version,
                    },
                )
                for path, token_id in dict(
                    source.get("token_bindings") or {}
                ).items()
            }
            document[style_collection].append(clone)
            _asset_links(document).append({**marker, "target_id": target_id})
        if style_collection == "layout_grid_styles":
            document, _row = update_ui_artboard(
                document,
                document["active_artboard_id"],
                {"layout_grid_style_id": target_id},
            )
        else:
            selected = _selected_object(document)
            style_ids = dict(selected.get("style_ids") or {})
            style_ids[str(source.get("kind") or "color")] = target_id
            document, _row = update_ui_object(
                document,
                selected["id"],
                {"style_ids": style_ids},
            )
    else:
        source = next(
            row for row in payload.get("resources") or []
            if str(row["id"]) == str(asset_id)
            and str(row.get("kind") or "") == asset_kind
        )
        resource_paths = _extract_resources(package, store_root=root)
        path = resource_paths.get(
            (asset_kind, str(source["name"]).casefold())
        )
        if not path:
            raise ValueError(f"Library resource could not be extracted: {asset_id}")
        target_id = str(path)
        if asset_kind == "image":
            document, row = add_ui_object(
                document,
                kind="image",
                name=Path(path).stem,
                x=float(x),
                y=float(y),
                width=256.0,
                height=256.0,
                content={"source_path": path, "fit": "contain"},
            )
            target_id = str(row["id"])
        else:
            selected = _selected_object(document)
            if selected["kind"] != "text":
                raise ValueError("Font assets can only be applied to text objects")
            content = copy.deepcopy(dict(selected.get("content") or {}))
            content["font_path"] = path
            document, _row = update_ui_object(
                document,
                selected["id"],
                {"content": content},
            )
        _asset_links(document).append(
            {**marker, "target_id": target_id, "resource_path": path}
        )
    document["revision"] = int(document.get("revision") or 0) + 1
    document = normalize_ui_document(document)
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Library asset insertion produced an invalid document: "
            + ", ".join(validation["errors"])
        )
    return document, {
        "schema": "tigerstudio.painter.ui.library_asset_insert.v1",
        **marker,
        "target_id": target_id,
    }


__all__ = [
    "ASSET_KINDS",
    "insert_ui_library_asset",
    "search_ui_library_assets",
]
