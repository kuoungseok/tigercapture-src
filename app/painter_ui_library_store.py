"""Versioned local Painter UI component, style, variable, and asset libraries."""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_document import normalize_ui_document, validate_ui_document


UI_LIBRARY_PACKAGE_SCHEMA = "tigerstudio.painter.ui.library_package.v1"
UI_LIBRARY_STORE_SCHEMA = "tigerstudio.painter.ui.library_store.v1"
UI_LIBRARY_ARCHIVE_SUFFIX = ".tsuilib"


def default_ui_library_store_root() -> Path:
    return Path.home() / "TigerStudio" / "PainterUILibraries"


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _safe_id(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in str(value or "").strip().lower()
    ).strip("-")
    if not cleaned:
        raise ValueError("Library ID must contain letters or numbers")
    return cleaned


def _state_path(root: Path) -> Path:
    return root / "library_state.json"


def _empty_state() -> dict[str, Any]:
    return {
        "schema": UI_LIBRARY_STORE_SCHEMA,
        "active_versions": {},
        "previous_versions": {},
        "deferred_versions": {},
    }


def _load_state(root: Path) -> dict[str, Any]:
    path = _state_path(root)
    if not path.is_file():
        return _empty_state()
    raw = json.loads(path.read_text(encoding="utf-8"))
    state = _empty_state()
    for key in ("active_versions", "previous_versions", "deferred_versions"):
        values = raw.get(key)
        if isinstance(values, Mapping):
            state[key] = {
                str(library_id): max(0, int(version))
                for library_id, version in values.items()
                if str(library_id)
            }
    return state


def _save_state(root: Path, state: Mapping[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _state_path(root).write_bytes(_json_bytes(dict(state)))


def _component_object_ids(document: Mapping[str, Any]) -> set[str]:
    roots = {
        str(row.get("root_object_id") or "")
        for row in document["components"]
        if str(row.get("root_object_id") or "")
    }
    selected = set(roots)
    changed = True
    while changed:
        changed = False
        for row in document["objects"]:
            if row["parent_id"] in selected and row["id"] not in selected:
                selected.add(row["id"])
                changed = True
    return selected


def _resource_candidates(document: Mapping[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for obj in document["objects"]:
        content = dict(obj.get("content") or {})
        candidates = []
        if obj["kind"] == "image":
            candidates.append(
                (
                    "image",
                    "source_path" if content.get("source_path") else "path",
                    str(content.get("source_path") or content.get("path") or ""),
                )
            )
        candidates.append(("font", "font_path", str(content.get("font_path") or "")))
        for kind, content_key, raw_path in candidates:
            if not raw_path:
                continue
            path = Path(raw_path).expanduser().resolve()
            rows.append(
                {
                    "kind": kind,
                    "source_path": str(path),
                    "object_id": str(obj["id"]),
                    "content_key": content_key,
                }
            )
    return rows


def export_ui_library_package(
    document: Mapping[str, Any],
    output_path: str | Path,
    *,
    library_id: str,
    name: str,
    version: int = 1,
    description: str = "",
    author: str = "",
    license_id: str = "User-Owned",
) -> dict[str, Any]:
    normalized = normalize_ui_document(document)
    validation = validate_ui_document(normalized)
    if not validation["ok"]:
        raise ValueError(
            "Cannot package invalid Painter UI library: "
            + ", ".join(validation["errors"])
        )
    component_object_ids = _component_object_ids(normalized)
    payload = {
        "components": normalized["components"],
        "component_objects": [
            row for row in normalized["objects"] if row["id"] in component_object_ids
        ],
        "styles": normalized["styles"],
        "layout_grid_styles": normalized["layout_grid_styles"],
        "variable_collections": normalized["variable_collections"],
        "tokens": normalized["tokens"],
        "resources": [],
    }
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != UI_LIBRARY_ARCHIVE_SUFFIX:
        destination = destination.with_suffix(UI_LIBRARY_ARCHIVE_SUFFIX)
    destination.parent.mkdir(parents=True, exist_ok=True)
    resource_files: list[tuple[Path, str, dict[str, Any]]] = []
    resources_by_key: dict[str, dict[str, Any]] = {}
    for candidate in _resource_candidates(normalized):
        source = Path(candidate["source_path"])
        if not source.is_file():
            continue
        sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
        archive_path = f"resources/{sha256}{source.suffix.lower()}"
        resource_key = f"{candidate['kind']}:{sha256}"
        record = resources_by_key.get(resource_key)
        if record is None:
            record = {
                "id": f"{candidate['kind']}-{sha256[:16]}",
                "kind": candidate["kind"],
                "name": source.name,
                "archive_path": archive_path,
                "sha256": sha256,
                "size_bytes": source.stat().st_size,
                "bindings": [],
            }
            resources_by_key[resource_key] = record
            payload["resources"].append(record)
            resource_files.append((source, archive_path, record))
        record["bindings"].append(
            {
                "object_id": candidate["object_id"],
                "content_key": candidate["content_key"],
            }
        )
    package_id = _safe_id(library_id)
    manifest = {
        "schema": UI_LIBRARY_PACKAGE_SCHEMA,
        "id": package_id,
        "version": max(1, int(version)),
        "name": str(name or package_id),
        "description": str(description or ""),
        "author": str(author or ""),
        "license": {
            "id": str(license_id or "User-Owned"),
            "commercial_use": True,
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payload_sha256": _digest(payload),
        "counts": {
            "components": len(payload["components"]),
            "styles": len(payload["styles"]) + len(payload["layout_grid_styles"]),
            "variable_collections": len(payload["variable_collections"]),
            "tokens": len(payload["tokens"]),
            "resources": len(payload["resources"]),
        },
    }
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        archive.writestr("library.json", _json_bytes(payload))
        for source, archive_path, _record in resource_files:
            archive.write(source, archive_path)
    return {"ok": True, "path": str(destination), "manifest": manifest}


def read_ui_library_package(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Painter UI library package not found: {source}")
    with zipfile.ZipFile(source, "r") as archive:
        names = set(archive.namelist())
        if not {"manifest.json", "library.json"}.issubset(names):
            raise ValueError("UI library package is missing manifest or payload")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        payload = json.loads(archive.read("library.json").decode("utf-8"))
        if manifest.get("schema") != UI_LIBRARY_PACKAGE_SCHEMA:
            raise ValueError(
                f"Unsupported UI library schema: {manifest.get('schema')}"
            )
        if str(manifest.get("payload_sha256") or "") != _digest(payload):
            raise ValueError("UI library payload hash does not match manifest")
        for resource in payload.get("resources", []):
            archive_path = str(resource.get("archive_path") or "")
            if archive_path not in names:
                raise ValueError(f"UI library resource is missing: {archive_path}")
            if hashlib.sha256(archive.read(archive_path)).hexdigest() != str(
                resource.get("sha256") or ""
            ):
                raise ValueError(f"UI library resource hash mismatch: {archive_path}")
    license_row = manifest.get("license")
    if not isinstance(license_row, Mapping) or not str(license_row.get("id") or ""):
        raise ValueError("UI library package requires explicit license metadata")
    return {
        "path": str(source),
        "manifest": dict(manifest),
        "payload": dict(payload),
    }


def _installed_packages(root: Path) -> list[dict[str, Any]]:
    rows = []
    for path in sorted((root / "packages").glob(f"*{UI_LIBRARY_ARCHIVE_SUFFIX}")):
        try:
            package = read_ui_library_package(path)
        except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile):
            continue
        rows.append(
            {
                **package["manifest"],
                "installed_path": str(path),
            }
        )
    return rows


def install_ui_library_package(
    path: str | Path,
    *,
    store_root: str | Path | None = None,
    activate: bool = True,
) -> dict[str, Any]:
    package = read_ui_library_package(path)
    root = Path(store_root or default_ui_library_store_root()).expanduser().resolve()
    packages = root / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    manifest = package["manifest"]
    library_id = _safe_id(manifest["id"])
    version = max(1, int(manifest["version"]))
    destination = packages / f"{library_id}-v{version}{UI_LIBRARY_ARCHIVE_SUFFIX}"
    if Path(package["path"]) != destination:
        shutil.copy2(package["path"], destination)
    state = _load_state(root)
    if activate:
        current = int(state["active_versions"].get(library_id, 0))
        if current and current != version:
            state["previous_versions"][library_id] = current
        state["active_versions"][library_id] = version
        state["deferred_versions"].pop(library_id, None)
        _save_state(root, state)
    return {
        "ok": True,
        "installed_path": str(destination),
        "active": bool(activate),
        "manifest": manifest,
    }


def inspect_ui_library_store(
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_ui_library_store_root()).expanduser().resolve()
    state = _load_state(root)
    packages = _installed_packages(root)
    for row in packages:
        library_id = str(row["id"])
        row["active"] = (
            int(state["active_versions"].get(library_id, 0))
            == int(row["version"])
        )
        row["deferred"] = (
            int(state["deferred_versions"].get(library_id, 0))
            == int(row["version"])
        )
    return {
        "schema": UI_LIBRARY_STORE_SCHEMA,
        "root": str(root),
        "packages": packages,
        "library_count": len({str(row["id"]) for row in packages}),
        "active_versions": state["active_versions"],
        "previous_versions": state["previous_versions"],
        "deferred_versions": state["deferred_versions"],
    }


def compare_ui_library_update(
    candidate_path: str | Path,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    candidate = read_ui_library_package(candidate_path)
    root = Path(store_root or default_ui_library_store_root()).expanduser().resolve()
    state = _load_state(root)
    manifest = candidate["manifest"]
    library_id = str(manifest["id"])
    current_version = int(state["active_versions"].get(library_id, 0))
    current = next(
        (
            row
            for row in _installed_packages(root)
            if row["id"] == library_id
            and int(row["version"]) == current_version
        ),
        None,
    )
    return {
        "schema": "tigerstudio.painter.ui.library_update_review.v1",
        "library_id": library_id,
        "current_version": current_version,
        "candidate_version": int(manifest["version"]),
        "update_available": int(manifest["version"]) > current_version,
        "payload_changed": (
            current is None
            or str(current.get("payload_sha256") or "")
            != str(manifest.get("payload_sha256") or "")
        ),
        "counts": {
            "current": dict((current or {}).get("counts") or {}),
            "candidate": dict(manifest.get("counts") or {}),
        },
        "candidate": manifest,
    }


def defer_ui_library_update(
    library_id: str,
    version: int,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_ui_library_store_root()).expanduser().resolve()
    state = _load_state(root)
    state["deferred_versions"][_safe_id(library_id)] = max(1, int(version))
    _save_state(root, state)
    return state


def rollback_ui_library(
    library_id: str,
    *,
    store_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(store_root or default_ui_library_store_root()).expanduser().resolve()
    state = _load_state(root)
    key = _safe_id(library_id)
    previous = int(state["previous_versions"].get(key, 0))
    if not previous:
        raise ValueError(f"UI library has no rollback version: {key}")
    available = {
        int(row["version"])
        for row in _installed_packages(root)
        if row["id"] == key
    }
    if previous not in available:
        raise ValueError(f"UI library rollback package is missing: {key} v{previous}")
    current = int(state["active_versions"].get(key, 0))
    state["active_versions"][key] = previous
    if current:
        state["previous_versions"][key] = current
    state["deferred_versions"].pop(key, None)
    _save_state(root, state)
    return {
        "ok": True,
        "library_id": key,
        "active_version": previous,
        "previous_version": current,
    }


__all__ = [
    "UI_LIBRARY_ARCHIVE_SUFFIX",
    "UI_LIBRARY_PACKAGE_SCHEMA",
    "UI_LIBRARY_STORE_SCHEMA",
    "compare_ui_library_update",
    "default_ui_library_store_root",
    "defer_ui_library_update",
    "export_ui_library_package",
    "inspect_ui_library_store",
    "install_ui_library_package",
    "read_ui_library_package",
    "rollback_ui_library",
]
