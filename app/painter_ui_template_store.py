"""Durable template packages, user library state, and update review."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document
from app.painter_ui_templates import (
    UI_TEMPLATE_PACKAGE_SCHEMA,
    get_ui_template,
    instantiate_ui_template,
    list_ui_templates,
)


TEMPLATE_ARCHIVE_SCHEMA = "tigerstudio.painter.ui.template_archive.v1"
TEMPLATE_STORE_SCHEMA = "tigerstudio.painter.ui.template_store.v1"
TEMPLATE_SEARCH_SCHEMA = "tigerstudio.painter.ui.template_search.v1"
TEMPLATE_PREVIEW_SCHEMA = "tigerstudio.painter.ui.template_preview.v1"


def default_template_store_root() -> Path:
    return Path.home() / "TigerStudio" / "PainterUITemplates"


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _safe_id(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in str(value or "").strip().lower()
    ).strip("-")
    if not cleaned:
        raise ValueError("Template ID must contain letters or numbers")
    return cleaned


def _state_path(root: Path) -> Path:
    return root / "library_state.json"


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return {
            "schema": TEMPLATE_STORE_SCHEMA,
            "favorites": [],
            "recent": [],
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema": TEMPLATE_STORE_SCHEMA,
        "favorites": sorted(
            {str(item) for item in raw.get("favorites", []) if str(item)}
        ),
        "recent": [
            str(item) for item in raw.get("recent", []) if str(item)
        ][:20],
    }


def _save_state(root: Path, state: Mapping[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _state_path(root).write_bytes(_json_bytes(dict(state)))


def export_ui_template_package(
    document: Mapping[str, Any],
    output_path: str | Path,
    *,
    template_id: str,
    name: str,
    category: str = "User",
    description: str = "",
    tags: list[str] | None = None,
    version: int = 1,
    author: str = "",
    license_id: str = "User-Owned",
    source: str = "Tiger Studio user template",
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    validation = validate_ui_document(normalized)
    if not validation["ok"]:
        raise ValueError(
            "Cannot package invalid Painter UI document: "
            + ", ".join(validation["errors"])
        )
    package_id = _safe_id(template_id)
    manifest = {
        "schema": UI_TEMPLATE_PACKAGE_SCHEMA,
        "archive_schema": TEMPLATE_ARCHIVE_SCHEMA,
        "id": package_id,
        "version": max(1, int(version)),
        "name": str(name or package_id),
        "category": str(category or "User"),
        "description": str(description or ""),
        "tags": sorted({str(item) for item in (tags or []) if str(item)}),
        "difficulty": "Custom",
        "artboard_presets": [
            {
                "name": row["name"],
                "width": int(row["width"]),
                "height": int(row["height"]),
            }
            for row in normalized["artboards"]
        ],
        "features": [
            "Complete editable document",
            "Preserved components and tokens",
            "Stable object IDs",
        ],
        "author": str(author or ""),
        "source": str(source or ""),
        "source_url": "",
        "license": {
            "id": str(license_id or "User-Owned"),
            "name": str(license_id or "User-Owned"),
            "commercial_use": True,
            "attribution_required": False,
            "redistribution": "Controlled by the template owner",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "document_sha256": _digest(normalized),
        "dependencies": {
            "component_ids": sorted(
                row["id"] for row in normalized["components"]
            ),
            "token_ids": sorted(row["id"] for row in normalized["tokens"]),
        },
    }
    destination = Path(output_path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix.lower() != ".tstemplate":
        destination = destination.with_suffix(".tstemplate")
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        archive.writestr("design_document.json", _json_bytes(normalized))
    return {
        "ok": True,
        "path": str(destination),
        "manifest": manifest,
        "document_sha256": manifest["document_sha256"],
    }


def read_ui_template_package(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Painter UI template package not found: {source}")
    with zipfile.ZipFile(source, "r") as archive:
        names = set(archive.namelist())
        required = {"manifest.json", "design_document.json"}
        if not required.issubset(names):
            raise ValueError("Template package is missing manifest or document")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        document = normalize_ui_document(
            json.loads(archive.read("design_document.json").decode("utf-8"))
        )
    if manifest.get("schema") != UI_TEMPLATE_PACKAGE_SCHEMA:
        raise ValueError(f"Unsupported template schema: {manifest.get('schema')}")
    validation = validate_ui_document(document)
    if not validation["ok"]:
        raise ValueError(
            "Template package document is invalid: "
            + ", ".join(validation["errors"])
        )
    expected = str(manifest.get("document_sha256") or "")
    actual = _digest(document)
    if expected and expected != actual:
        raise ValueError("Template package document hash does not match manifest")
    license_row = manifest.get("license")
    if not isinstance(license_row, Mapping) or not str(license_row.get("id") or ""):
        raise ValueError("Template package requires explicit license metadata")
    return {
        "path": str(source),
        "manifest": dict(manifest),
        "document": document,
        "document_sha256": actual,
    }


def install_ui_template_package(
    path: str | Path,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    package = read_ui_template_package(path)
    root = Path(store_root or default_template_store_root()).expanduser().resolve()
    packages = root / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    manifest = package["manifest"]
    destination = packages / (
        f"{_safe_id(manifest['id'])}-v{max(1, int(manifest['version']))}.tstemplate"
    )
    shutil.copy2(package["path"], destination)
    return {
        "ok": True,
        "installed_path": str(destination),
        "manifest": manifest,
    }


def save_user_ui_template(
    document: Mapping[str, Any],
    *,
    template_id: str,
    name: str,
    store_root: str | Path | None = None,
    category: str = "User",
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_template_store_root()).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tiger_ui_template_") as temporary:
        package = export_ui_template_package(
            document,
            Path(temporary) / f"{_safe_id(template_id)}.tstemplate",
            template_id=template_id,
            name=name,
            category=category,
            description=description,
            tags=tags,
        )
        return install_ui_template_package(
            package["path"],
            store_root=root,
        )


def _installed_packages(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "packages").glob("*.tstemplate")):
        try:
            package = read_ui_template_package(path)
        except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile):
            continue
        manifest = dict(package["manifest"])
        manifest.update(
            {
                "installed_path": str(path),
                "installed": True,
                "document_sha256": package["document_sha256"],
            }
        )
        rows.append(manifest)
    return rows


def inspect_ui_template_store(
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_template_store_root()).expanduser().resolve()
    state = _load_state(root)
    built_in = [
        {**row, "installed": False, "built_in": True}
        for row in list_ui_templates()
    ]
    installed = _installed_packages(root)
    return {
        "schema": TEMPLATE_STORE_SCHEMA,
        "root": str(root),
        "built_in": built_in,
        "installed": installed,
        "favorites": state["favorites"],
        "recent": state["recent"],
        "template_count": len(built_in) + len(installed),
    }


def _template_platforms(row: Mapping[str, Any]) -> list[str]:
    platforms: set[str] = set()
    for preset in row.get("artboard_presets") or []:
        width = float(preset.get("width") or 0.0)
        height = float(preset.get("height") or 0.0)
        if height > width and width <= 600:
            platforms.add("mobile")
        elif width >= 1000:
            platforms.add("desktop")
        else:
            platforms.add("tablet")
    category = str(row.get("category") or "").casefold()
    if "broadcast" in category or "presentation" in category:
        platforms.add("screen")
    if "game" in category:
        platforms.add("game")
    return sorted(platforms)


def search_ui_templates(
    *,
    query: str = "",
    category: str = "",
    difficulty: str = "",
    platform: str = "",
    view: str = "all",
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    store = inspect_ui_template_store(store_root=store_root)
    installed_latest: dict[str, dict[str, Any]] = {}
    for row in store["installed"]:
        key = str(row["id"])
        if key not in installed_latest or int(row["version"]) > int(
            installed_latest[key]["version"]
        ):
            installed_latest[key] = dict(row)
    rows = [dict(row) for row in store["built_in"]]
    rows.extend(installed_latest.values())
    favorites = set(store["favorites"])
    recent = {key: index for index, key in enumerate(store["recent"])}
    query_key = str(query or "").strip().casefold()
    category_key = str(category or "").strip().casefold()
    difficulty_key = str(difficulty or "").strip().casefold()
    platform_key = str(platform or "").strip().casefold()
    view_key = str(view or "all").strip().casefold()
    if view_key not in {"all", "favorites", "recent", "installed"}:
        raise ValueError(f"Unsupported template view: {view}")
    matches = []
    for row in rows:
        template_id = str(row["id"])
        row["favorite"] = template_id in favorites
        row["recent"] = template_id in recent
        row["platforms"] = _template_platforms(row)
        row.setdefault("difficulty", "Custom")
        row.setdefault("tags", [])
        row.setdefault("description", "")
        row.setdefault("features", ["Complete editable document"])
        row.setdefault("artboard_presets", [])
        if view_key == "favorites" and not row["favorite"]:
            continue
        if view_key == "recent" and not row["recent"]:
            continue
        if view_key == "installed" and not row.get("installed"):
            continue
        if category_key and str(row.get("category") or "").casefold() != category_key:
            continue
        if difficulty_key and str(row["difficulty"]).casefold() != difficulty_key:
            continue
        if platform_key and platform_key not in row["platforms"]:
            continue
        haystack = " ".join(
            [
                str(row.get("name") or ""),
                str(row.get("category") or ""),
                str(row.get("description") or ""),
                *[str(tag) for tag in row["tags"]],
            ]
        ).casefold()
        if query_key and query_key not in haystack:
            continue
        matches.append(row)
    if view_key == "recent":
        matches.sort(key=lambda row: recent.get(str(row["id"]), 10_000))
    else:
        matches.sort(
            key=lambda row: (
                str(row.get("category") or "").casefold(),
                str(row.get("name") or "").casefold(),
            )
        )
    return {
        "schema": TEMPLATE_SEARCH_SCHEMA,
        "query": query_key,
        "filters": {
            "category": category,
            "difficulty": difficulty,
            "platform": platform,
            "view": view_key,
        },
        "count": len(matches),
        "templates": matches,
        "facets": {
            "categories": sorted(
                {str(row.get("category") or "") for row in rows}
            ),
            "difficulties": sorted(
                {str(row.get("difficulty") or "Custom") for row in rows}
            ),
            "platforms": sorted(
                {
                    item
                    for row in rows
                    for item in _template_platforms(row)
                }
            ),
        },
    }


def preview_ui_template(
    template_id: str,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    key = str(template_id or "").strip()
    search = search_ui_templates(store_root=store_root)
    manifest = next(
        (dict(row) for row in search["templates"] if str(row["id"]) == key),
        None,
    )
    if manifest is None:
        raise ValueError(f"Painter UI template not found: {key}")
    try:
        document, _report = instantiate_ui_template(key)
    except ValueError:
        selected = next(
            row
            for row in inspect_ui_template_store(
                store_root=store_root
            )["installed"]
            if str(row["id"]) == key
            and int(row["version"]) == int(manifest["version"])
        )
        document = read_ui_template_package(selected["installed_path"])[
            "document"
        ]
    return {
        "schema": TEMPLATE_PREVIEW_SCHEMA,
        "template": manifest,
        "document": {
            "page_count": len(document["pages"]),
            "artboard_count": len(document["artboards"]),
            "object_count": len(document["objects"]),
            "component_count": len(document["components"]),
            "token_count": len(document["tokens"]),
            "interaction_count": len(document["interactions"]),
            "themes": sorted(
                {
                    str(mode.get("name") or "")
                    for collection in document["variable_collections"]
                    for mode in collection.get("modes") or []
                    if str(mode.get("name") or "")
                }
            ),
        },
        "compatibility": {
            "web": "inspect_on_insert",
            "app": "inspect_on_insert",
            "umg": "inspect_on_insert",
        },
    }


def set_ui_template_favorite(
    template_id: str,
    favorite: bool,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_template_store_root()).expanduser().resolve()
    state = _load_state(root)
    values = set(state["favorites"])
    if favorite:
        values.add(str(template_id))
    else:
        values.discard(str(template_id))
    state["favorites"] = sorted(values)
    _save_state(root, state)
    return state


def record_ui_template_recent(
    template_id: str,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_template_store_root()).expanduser().resolve()
    state = _load_state(root)
    key = str(template_id)
    state["recent"] = [key] + [
        item for item in state["recent"] if item != key
    ]
    state["recent"] = state["recent"][:20]
    _save_state(root, state)
    return state


def instantiate_stored_ui_template(
    template_id: str,
    *,
    store_root: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    key = str(template_id)
    try:
        document, report = instantiate_ui_template(key)
    except ValueError:
        store = inspect_ui_template_store(store_root=store_root)
        candidates = [
            row for row in store["installed"] if str(row["id"]) == key
        ]
        if not candidates:
            raise
        selected = max(candidates, key=lambda row: int(row["version"]))
        package = read_ui_template_package(selected["installed_path"])
        document = package["document"]
        report = {
            "template_id": key,
            "template_name": selected["name"],
            "template_version": int(selected["version"]),
            "source": selected["source"],
            "license": selected["license"],
            "document_sha256": package["document_sha256"],
        }
    record_ui_template_recent(key, store_root=store_root)
    return document, report


def compare_ui_template_update(
    current_manifest: Mapping[str, Any],
    candidate_path: str | Path,
) -> dict[str, Any]:
    candidate = read_ui_template_package(candidate_path)
    current_version = max(0, int(current_manifest.get("version") or 0))
    candidate_version = max(0, int(candidate["manifest"].get("version") or 0))
    current_dependencies = current_manifest.get("dependencies")
    current_dependencies = (
        dict(current_dependencies)
        if isinstance(current_dependencies, Mapping)
        else {}
    )
    candidate_dependencies = dict(
        candidate["manifest"].get("dependencies") or {}
    )
    return {
        "schema": "tigerstudio.painter.ui.template_update_review.v1",
        "template_id": str(candidate["manifest"]["id"]),
        "current_version": current_version,
        "candidate_version": candidate_version,
        "update_available": candidate_version > current_version,
        "document_changed": (
            str(current_manifest.get("document_sha256") or "")
            != candidate["document_sha256"]
        ),
        "dependencies": {
            "current": current_dependencies,
            "candidate": candidate_dependencies,
        },
        "candidate": candidate["manifest"],
    }


__all__ = [
    "TEMPLATE_ARCHIVE_SCHEMA",
    "TEMPLATE_STORE_SCHEMA",
    "compare_ui_template_update",
    "default_template_store_root",
    "export_ui_template_package",
    "inspect_ui_template_store",
    "install_ui_template_package",
    "instantiate_stored_ui_template",
    "read_ui_template_package",
    "record_ui_template_recent",
    "save_user_ui_template",
    "set_ui_template_favorite",
]
