"""Import installed Painter UI library components into an editable document."""
from __future__ import annotations

import copy
import zipfile
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_components import instantiate_ui_component
from app.painter_ui_document import normalize_ui_document, validate_ui_document
from app.painter_ui_library_store import (
    default_ui_library_store_root,
    inspect_ui_library_store,
    read_ui_library_package,
)


def _next_id(prefix: str, used: set[str]) -> str:
    serial = 1
    while f"{prefix}-{serial}" in used:
        serial += 1
    value = f"{prefix}-{serial}"
    used.add(value)
    return value


def _active_package(
    library_id: str,
    *,
    version: int,
    store_root: Path,
) -> dict[str, Any]:
    report = inspect_ui_library_store(store_root=store_root)
    target_version = max(0, int(version))
    if not target_version:
        target_version = int(
            report["active_versions"].get(str(library_id), 0)
        )
    row = next(
        (
            item
            for item in report["packages"]
            if str(item["id"]) == str(library_id)
            and int(item["version"]) == target_version
        ),
        None,
    )
    if row is None:
        raise ValueError(
            f"Installed UI library not found: {library_id} v{target_version}"
        )
    if not version and not row["active"]:
        raise ValueError(f"UI library has no active version: {library_id}")
    return row


def _extract_resources(
    package: Mapping[str, Any],
    *,
    store_root: Path,
) -> dict[tuple[str, ...], str]:
    manifest = package["manifest"]
    root = (
        store_root
        / "resources"
        / str(manifest["id"])
        / f"v{int(manifest['version'])}"
    )
    root.mkdir(parents=True, exist_ok=True)
    paths: dict[tuple[str, ...], str] = {}
    with zipfile.ZipFile(str(package["path"]), "r") as archive:
        for resource in package["payload"].get("resources", []):
            archive_path = str(resource.get("archive_path") or "")
            if not archive_path:
                continue
            suffix = Path(archive_path).suffix.lower()
            destination = root / f"{resource['sha256']}{suffix}"
            if not destination.is_file():
                destination.write_bytes(archive.read(archive_path))
            paths[
                (
                    str(resource.get("kind") or ""),
                    str(resource.get("name") or "").casefold(),
                )
            ] = str(destination)
            for binding in resource.get("bindings") or []:
                paths[
                    (
                        "binding",
                        str(binding.get("object_id") or ""),
                        str(binding.get("content_key") or ""),
                    )
                ] = str(destination)
    return paths


def _remap_object_resources(
    row: dict[str, Any],
    resource_paths: Mapping[tuple[str, ...], str],
    *,
    source_object_id: str,
) -> None:
    content = copy.deepcopy(dict(row.get("content") or {}))
    candidates = (
        ("image", "source_path"),
        ("image", "path"),
        ("font", "font_path"),
    )
    for kind, key in candidates:
        raw = str(content.get(key) or "")
        if not raw:
            continue
        replacement = resource_paths.get(
            ("binding", str(source_object_id), key)
        ) or resource_paths.get((kind, Path(raw).name.casefold()))
        if replacement:
            content[key] = replacement
    row["content"] = content


def _source_component(
    components: list[Mapping[str, Any]],
    component_id: str,
) -> Mapping[str, Any]:
    row = next(
        (item for item in components if str(item["id"]) == str(component_id)),
        None,
    )
    if row is None:
        raise ValueError(f"UI library component not found: {component_id}")
    return row


def insert_ui_library_component(
    value: Mapping[str, Any],
    *,
    library_id: str,
    component_id: str,
    version: int = 0,
    artboard_id: str = "",
    x: float = 64.0,
    y: float = 64.0,
    store_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    document = normalize_ui_document(value)
    root = Path(
        store_root or default_ui_library_store_root()
    ).expanduser().resolve()
    package_row = _active_package(
        str(library_id),
        version=int(version),
        store_root=root,
    )
    package = read_ui_library_package(package_row["installed_path"])
    payload = package["payload"]
    source_components = list(payload.get("components") or [])
    source_component = _source_component(source_components, component_id)
    source_key = {
        "library_id": str(package["manifest"]["id"]),
        "version": int(package["manifest"]["version"]),
        "component_id": str(source_component["id"]),
    }
    imported_component = next(
        (
            row
            for row in document["components"]
            if dict((row.get("metadata") or {}).get("library_source") or {})
            == source_key
        ),
        None,
    )
    imported_counts = {
        "components": 0,
        "objects": 0,
        "styles": 0,
        "layout_grid_styles": 0,
        "variable_collections": 0,
        "tokens": 0,
        "resources": 0,
    }
    if imported_component is None:
        used_ids = {
            str(row["id"])
            for key in (
                "objects",
                "components",
                "styles",
                "layout_grid_styles",
                "variable_collections",
                "tokens",
            )
            for row in document[key]
        }
        collection_map: dict[str, str] = {}
        mode_map: dict[str, str] = {}
        for source in payload.get("variable_collections", []):
            clone = copy.deepcopy(source)
            clone["id"] = _next_id("ui-variable-collection", used_ids)
            collection_map[str(source["id"])] = clone["id"]
            for source_mode, clone_mode in zip(
                source.get("modes") or [],
                clone.get("modes") or [],
            ):
                clone_mode["id"] = _next_id("ui-variable-mode", used_ids)
                mode_map[str(source_mode["id"])] = clone_mode["id"]
            clone["default_mode_id"] = mode_map.get(
                str(source.get("default_mode_id") or ""),
                "",
            )
            document["variable_collections"].append(clone)
            imported_counts["variable_collections"] += 1

        token_map: dict[str, str] = {}
        token_clones = []
        for source in payload.get("tokens", []):
            clone = copy.deepcopy(source)
            clone["id"] = _next_id("ui-token", used_ids)
            token_map[str(source["id"])] = clone["id"]
            clone["collection_id"] = collection_map.get(
                str(source.get("collection_id") or ""),
                "",
            )
            clone["mode_values"] = {
                mode_map.get(str(mode_id), str(mode_id)): copy.deepcopy(item)
                for mode_id, item in dict(
                    source.get("mode_values") or {}
                ).items()
            }
            token_clones.append((source, clone))
        for source, clone in token_clones:
            clone["alias_token_id"] = token_map.get(
                str(source.get("alias_token_id") or ""),
                "",
            )
            document["tokens"].append(clone)
            imported_counts["tokens"] += 1

        style_map: dict[str, str] = {}
        for key, prefix in (
            ("styles", "ui-style"),
            ("layout_grid_styles", "ui-layout-grid-style"),
        ):
            for source in payload.get(key, []):
                clone = copy.deepcopy(source)
                clone["id"] = _next_id(prefix, used_ids)
                style_map[str(source["id"])] = clone["id"]
                clone["token_bindings"] = {
                    str(path): token_map.get(str(token_id), str(token_id))
                    for path, token_id in dict(
                        source.get("token_bindings") or {}
                    ).items()
                }
                document[key].append(clone)
                imported_counts[key] += 1

        component_map = {
            str(source["id"]): _next_id("ui-component", used_ids)
            for source in source_components
        }
        source_objects = list(payload.get("component_objects") or [])
        source_children: dict[str, list[str]] = {}
        for source in source_objects:
            source_children.setdefault(
                str(source.get("parent_id") or ""),
                [],
            ).append(str(source["id"]))
        source_owner: dict[str, str] = {}

        def mark_owner(object_id: str, owner_component_id: str) -> None:
            source_owner.setdefault(object_id, owner_component_id)
            for child_id in source_children.get(object_id, []):
                mark_owner(child_id, owner_component_id)

        for source in source_components:
            mark_owner(
                str(source.get("root_object_id") or ""),
                str(source["id"]),
            )
        object_map = {
            str(source["id"]): _next_id("ui-object", used_ids)
            for source in source_objects
        }
        resource_paths = _extract_resources(package, store_root=root)
        imported_counts["resources"] = len(payload.get("resources") or [])
        target_artboard = str(artboard_id or document["active_artboard_id"])
        next_z = max(
            [int(row["z_index"]) for row in document["objects"]] or [-1]
        ) + 1
        for source in source_objects:
            clone = copy.deepcopy(source)
            clone["id"] = object_map[str(source["id"])]
            clone["artboard_id"] = target_artboard
            clone["parent_id"] = object_map.get(
                str(source.get("parent_id") or ""),
                "",
            )
            clone["component_id"] = component_map.get(
                str(source.get("component_id") or ""),
                "",
            )
            clone["component_scope_id"] = component_map.get(
                str(source.get("component_scope_id") or ""),
                "",
            )
            clone["component_source_object_id"] = object_map.get(
                str(source.get("component_source_object_id") or ""),
                "",
            )
            clone["component_scope_source_object_id"] = object_map.get(
                str(source.get("component_scope_source_object_id") or ""),
                "",
            )
            if not clone["component_id"] and str(source["id"]) in source_owner:
                clone["component_id"] = component_map[
                    source_owner[str(source["id"])]
                ]
                clone["component_role"] = "definition"
                clone["component_source_object_id"] = clone["id"]
            clone["x"] = float(source.get("x") or 0.0) - 100000.0
            clone["z_index"] = next_z
            next_z += 1
            clone["style_ids"] = {
                str(kind): style_map.get(str(style_id), str(style_id))
                for kind, style_id in dict(
                    source.get("style_ids") or {}
                ).items()
            }
            clone["token_bindings"] = {
                str(path): token_map.get(str(token_id), str(token_id))
                for path, token_id in dict(
                    source.get("token_bindings") or {}
                ).items()
            }
            mask = copy.deepcopy(dict(clone.get("mask") or {}))
            mask["target_ids"] = [
                object_map.get(str(item), str(item))
                for item in mask.get("target_ids") or []
            ]
            clone["mask"] = mask
            boolean = copy.deepcopy(
                dict((clone.get("content") or {}).get("boolean") or {})
            )
            if boolean:
                boolean["operand_ids"] = [
                    object_map.get(str(item), str(item))
                    for item in boolean.get("operand_ids") or []
                ]
                clone.setdefault("content", {})["boolean"] = boolean
            _remap_object_resources(
                clone,
                resource_paths,
                source_object_id=str(source["id"]),
            )
            document["objects"].append(clone)
            imported_counts["objects"] += 1

        for source in source_components:
            clone = copy.deepcopy(source)
            clone["id"] = component_map[str(source["id"])]
            clone["root_object_id"] = object_map.get(
                str(source.get("root_object_id") or ""),
                "",
            )
            clone["base_component_id"] = component_map.get(
                str(source.get("base_component_id") or ""),
                "",
            )
            clone["variant_ids"] = [
                component_map.get(str(item), str(item))
                for item in source.get("variant_ids") or []
            ]
            metadata = copy.deepcopy(dict(clone.get("metadata") or {}))
            source_map = dict(metadata.get("variant_source_map") or {})
            if source_map:
                metadata["variant_source_map"] = {
                    str(path): object_map.get(str(object_id), str(object_id))
                    for path, object_id in source_map.items()
                }
            metadata["library_source"] = {
                "library_id": str(package["manifest"]["id"]),
                "version": int(package["manifest"]["version"]),
                "component_id": str(source["id"]),
            }
            clone["metadata"] = metadata
            document["components"].append(clone)
            imported_counts["components"] += 1
        document["revision"] += 1
        imported_component = next(
            row
            for row in document["components"]
            if row["id"] == component_map[str(source_component["id"])]
        )

    target_artboard = str(artboard_id or document["active_artboard_id"])
    document, instance = instantiate_ui_component(
        document,
        component_id=str(imported_component["id"]),
        artboard_id=target_artboard,
        x=float(x),
        y=float(y),
    )
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Imported UI library component is invalid: "
            + ", ".join(validation["errors"])
        )
    return document, {
        "schema": "tigerstudio.painter.ui.library_component_insert.v1",
        "library_id": str(package["manifest"]["id"]),
        "version": int(package["manifest"]["version"]),
        "source_component_id": str(source_component["id"]),
        "component_id": str(imported_component["id"]),
        "instance": instance,
        "imported": imported_counts,
        "validation": validation,
    }


__all__ = ["insert_ui_library_component"]
