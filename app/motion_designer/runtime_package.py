"""Portable, hash-verified Motion project package with embedded resources."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import zipfile
from typing import Any, Mapping

from .schema import MotionComposition
from .validation import validate_composition


MOTION_PACKAGE_SCHEMA = "tigerstudio.motion.runtime_package.v1"
MOTION_PACKAGE_EXTENSION = ".tgmotionpkg"
_RESOURCE_KEYS = {"uri", "resource_uri", "font_path", "source_path", "texture_path", "audio_path"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resource_slots(value: Any, path: tuple[Any, ...] = ()):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, key)
            if key in _RESOURCE_KEYS and isinstance(child, str) and child:
                yield value, key, child, child_path
            yield from _resource_slots(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _resource_slots(child, (*path, index))


def _local_resource(value: str) -> Path | None:
    text = str(value or "").strip()
    if not text or text.startswith(("package://", "data:", "http://", "https://")):
        return None
    path = Path(text).expanduser().resolve(strict=False)
    return path if path.is_file() else None


def export_motion_package(composition: MotionComposition, path: str | Path) -> dict[str, Any]:
    report = validate_composition(composition)
    if not report.ok:
        raise ValueError(f"Invalid Motion composition cannot be packaged: {report.issues[0].message}")
    target = Path(path).expanduser().resolve(strict=False)
    if target.suffix.lower() != MOTION_PACKAGE_EXTENSION:
        target = target.with_suffix(MOTION_PACKAGE_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = deepcopy(composition.to_dict())
    assets: dict[str, dict[str, Any]] = {}
    source_by_hash: dict[str, Path] = {}
    for owner, key, raw, json_path in _resource_slots(document):
        source = _local_resource(raw)
        if source is None:
            continue
        digest = _sha256(source)
        archive_path = f"assets/{digest[:16]}_{source.name}"
        owner[key] = f"package://{archive_path}"
        source_by_hash.setdefault(digest, source)
        assets.setdefault(digest, {
            "sha256": digest,
            "size": source.stat().st_size,
            "archive_path": archive_path,
            "original_name": source.name,
            "references": [],
        })["references"].append({"json_path": list(json_path), "original_uri": raw})
    manifest = {
        "schema": MOTION_PACKAGE_SCHEMA,
        "format_version": 1,
        "composition": document,
        "assets": list(assets.values()),
    }
    temporary = target.with_name(target.name + f".{os.getpid()}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for digest, source in source_by_hash.items():
                archive.write(source, assets[digest]["archive_path"])
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"path": str(target), "asset_count": len(assets), "assets": list(assets.values())}


def inspect_motion_package(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve(strict=False)
    with zipfile.ZipFile(source, "r") as archive:
        names = set(archive.namelist())
        if "manifest.json" not in names:
            raise ValueError("Motion package has no manifest.json")
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        if not isinstance(manifest, Mapping) or manifest.get("schema") != MOTION_PACKAGE_SCHEMA:
            raise ValueError("Unsupported Motion package schema")
        checks = []
        for asset in manifest.get("assets", []):
            archive_path = str(asset.get("archive_path") or "")
            safe = PurePosixPath(archive_path)
            present = archive_path in names and not safe.is_absolute() and ".." not in safe.parts
            digest = hashlib.sha256(archive.read(archive_path)).hexdigest() if present else ""
            checks.append({
                "archive_path": archive_path,
                "present": present,
                "hash_ok": present and digest == str(asset.get("sha256") or ""),
            })
    return {
        "schema": MOTION_PACKAGE_SCHEMA,
        "path": str(source),
        "composition_id": str((manifest.get("composition") or {}).get("id") or ""),
        "asset_count": len(checks),
        "assets": checks,
        "ok": all(row["present"] and row["hash_ok"] for row in checks),
    }


def load_motion_package(path: str | Path, extract_dir: str | Path) -> MotionComposition:
    source = Path(path).expanduser().resolve(strict=False)
    destination = Path(extract_dir).expanduser().resolve(strict=False)
    destination.mkdir(parents=True, exist_ok=True)
    inspection = inspect_motion_package(source)
    if not inspection["ok"]:
        raise ValueError("Motion package asset verification failed")
    with zipfile.ZipFile(source, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        document = deepcopy(manifest["composition"])
        for asset in manifest.get("assets", []):
            archive_path = str(asset["archive_path"])
            target = (destination / Path(*PurePosixPath(archive_path).parts)).resolve(strict=False)
            if destination != target and destination not in target.parents:
                raise ValueError("Motion package contains an unsafe asset path")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(archive_path))
        for owner, key, raw, _json_path in _resource_slots(document):
            if raw.startswith("package://"):
                relative = PurePosixPath(raw[len("package://"):])
                owner[key] = str((destination / Path(*relative.parts)).resolve(strict=False))
    composition = MotionComposition.from_dict(document)
    validation = validate_composition(composition)
    if not validation.ok:
        raise ValueError(f"Invalid packaged Motion composition: {validation.issues[0].message}")
    return composition


__all__ = [
    "MOTION_PACKAGE_EXTENSION", "MOTION_PACKAGE_SCHEMA", "export_motion_package",
    "inspect_motion_package", "load_motion_package",
]
