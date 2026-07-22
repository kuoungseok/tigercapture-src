"""Validation and safe installation for declarative Motion template packs."""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping

from .plugin_manifest import PLUGIN_ID_PATTERN, VERSION_PATTERN
from .schema import MotionComposition
from .templates import TEMPLATE_VARIANTS
from .validation import validate_composition


MOTION_TEMPLATE_PACK_SCHEMA = "tigercapture.motion.template_pack.v1"
MOTION_TEMPLATE_PACK_MANIFEST_NAME = "template-pack.json"
MAX_PACK_FILES = 2048
MAX_PACK_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
PUBLISHED_CONTROL_TYPES = frozenset({
    "string", "number", "integer", "boolean", "color", "enum", "media", "font",
})
PREVIEW_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
BLOCKED_SUFFIXES = frozenset({
    ".bat", ".cmd", ".com", ".dll", ".exe", ".js", ".msi", ".ps1", ".py",
    ".pyc", ".pyd", ".scr", ".vbs",
})


def motion_template_pack_user_root() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "TigerCapture" / "MotionDesigner" / "template_packs"


def _safe_relative(value: str) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    pure = PurePosixPath(text)
    if (
        not text or text.startswith("/") or pure.is_absolute() or ".." in pure.parts
        or any(":" in part for part in pure.parts)
    ):
        return None
    return Path(*pure.parts)


def _safe_member_name(value: str) -> Path:
    relative = _safe_relative(value)
    if relative is None:
        raise ValueError(f"Unsafe template-pack archive path: {value}")
    return relative


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)


def _locate_manifest(root: Path) -> Path:
    direct = root / MOTION_TEMPLATE_PACK_MANIFEST_NAME
    if direct.is_file():
        return direct
    candidates = sorted(root.glob(f"*/{MOTION_TEMPLATE_PACK_MANIFEST_NAME}"))
    if len(candidates) != 1:
        raise ValueError(
            f"Template pack must contain exactly one {MOTION_TEMPLATE_PACK_MANIFEST_NAME}"
        )
    return candidates[0]


def _check_directory_files(root: Path) -> tuple[int, int, list[str]]:
    count = 0
    total = 0
    blocked: list[str] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Template pack may not contain symbolic links: {path}")
        if not path.is_file():
            continue
        count += 1
        total += path.stat().st_size
        relative = path.relative_to(root).as_posix()
        if path.suffix.casefold() in BLOCKED_SUFFIXES:
            blocked.append(relative)
        if count > MAX_PACK_FILES:
            raise ValueError(f"Template pack exceeds {MAX_PACK_FILES} files")
        if total > MAX_PACK_UNCOMPRESSED_BYTES:
            raise ValueError("Template pack exceeds the uncompressed size limit")
    return count, total, blocked


def _extract_zip_safely(source: Path, output: Path) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_PACK_FILES:
            raise ValueError(f"Template pack exceeds {MAX_PACK_FILES} archive entries")
        total = sum(max(0, int(item.file_size)) for item in members)
        if total > MAX_PACK_UNCOMPRESSED_BYTES:
            raise ValueError("Template pack exceeds the uncompressed size limit")
        seen_members: set[str] = set()
        for info in members:
            relative = _safe_member_name(info.filename)
            member_key = relative.as_posix().casefold().rstrip("/")
            if member_key in seen_members:
                raise ValueError(f"Duplicate template-pack archive path: {info.filename}")
            seen_members.add(member_key)
            if _is_zip_symlink(info):
                raise ValueError(f"Template pack may not contain symbolic links: {info.filename}")
            target = output / relative
            target.resolve(strict=False).relative_to(output.resolve(strict=False))
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info, "r") as source_stream, target.open("wb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream, length=1024 * 1024)


@contextmanager
def _materialized_pack(source: str | Path) -> Iterator[tuple[Path, Path, str]]:
    path = Path(source).expanduser().resolve(strict=False)
    if path.is_dir():
        manifest = _locate_manifest(path)
        yield manifest.parent, manifest, "directory"
        return
    if path.is_file() and path.name.casefold() == MOTION_TEMPLATE_PACK_MANIFEST_NAME:
        yield path.parent, path, "manifest"
        return
    if not path.is_file() or path.suffix.casefold() != ".zip":
        raise ValueError(f"Template pack source must be a directory, manifest, or ZIP: {path}")
    with tempfile.TemporaryDirectory(prefix="tiger-motion-pack-") as temporary:
        extraction_root = Path(temporary)
        _extract_zip_safely(path, extraction_root)
        manifest = _locate_manifest(extraction_root)
        yield manifest.parent, manifest, "zip"


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(
            f"Could not read template-pack manifest: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise ValueError("Template-pack manifest root must be an object")
    return value


def _resource(root: Path, value: str) -> Path | None:
    relative = _safe_relative(value)
    if relative is None:
        return None
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return candidate


def _validate_control(control: Any, path: str, seen: set[str], errors: list[str]) -> dict[str, Any]:
    if not isinstance(control, Mapping):
        errors.append(f"{path} must be an object")
        return {}
    control_id = str(control.get("id") or "").strip()
    label = str(control.get("label") or "").strip()
    value_type = str(control.get("value_type") or "").strip()
    if not PLUGIN_ID_PATTERN.fullmatch(control_id):
        errors.append(f"{path}.id must be a stable lowercase id")
    elif control_id in seen:
        errors.append(f"Duplicate published control id: {control_id}")
    seen.add(control_id)
    if not label:
        errors.append(f"{path}.label is required")
    if value_type not in PUBLISHED_CONTROL_TYPES:
        errors.append(f"{path}.value_type is unsupported: {value_type or '<missing>'}")
    if "default" not in control:
        errors.append(f"{path}.default is required")
    return {
        "id": control_id,
        "label": label,
        "value_type": value_type,
        "default": control.get("default"),
        "options": list(control.get("options") or []) if isinstance(control.get("options"), list) else [],
    }


def _validate_materialized(root: Path, manifest_path: Path, source_type: str,
                           source_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        data = _load_manifest(manifest_path)
    except ValueError as exc:
        data = {}
        errors.append(str(exc))

    schema = str(data.get("schema") or "")
    pack_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    vendor = str(data.get("vendor") or "").strip()
    license_name = str(data.get("license") or "").strip()
    if schema != MOTION_TEMPLATE_PACK_SCHEMA:
        errors.append(f"Unsupported Motion template-pack schema: {schema or '<missing>'}")
    if not PLUGIN_ID_PATTERN.fullmatch(pack_id):
        errors.append("Template-pack id must be a stable lowercase id")
    if not name:
        errors.append("Template-pack display name is required")
    if not VERSION_PATTERN.fullmatch(version):
        errors.append("Template-pack version must be a semantic numeric version")
    if not vendor:
        errors.append("Template-pack vendor is required")
    if not license_name:
        errors.append("Template-pack license is required")

    try:
        file_count, total_bytes, blocked_files = _check_directory_files(root)
    except ValueError as exc:
        file_count, total_bytes, blocked_files = 0, 0, []
        errors.append(str(exc))
    if blocked_files:
        errors.append(f"Template pack contains executable content: {blocked_files[0]}")

    templates = data.get("templates", [])
    if not isinstance(templates, list) or not templates:
        errors.append("Template pack must declare at least one template")
        templates = []
    normalized_templates: list[dict[str, Any]] = []
    template_ids: set[str] = set()
    for index, template in enumerate(templates):
        path = f"templates[{index}]"
        if not isinstance(template, Mapping):
            errors.append(f"{path} must be an object")
            continue
        template_id = str(template.get("id") or "").strip()
        template_name = str(template.get("name") or "").strip()
        category = str(template.get("category") or "").strip()
        if not PLUGIN_ID_PATTERN.fullmatch(template_id):
            errors.append(f"{path}.id must be a stable lowercase id")
        elif template_id in template_ids:
            errors.append(f"Duplicate template id: {template_id}")
        template_ids.add(template_id)
        if not template_name:
            errors.append(f"{path}.name is required")
        if not category:
            errors.append(f"{path}.category is required")
        variants = template.get("variants", [])
        if (
            not isinstance(variants, list) or not variants
            or any(str(item) not in TEMPLATE_VARIANTS for item in variants)
        ):
            errors.append(f"{path}.variants must use supported aspect variants")
            variants = []

        composition_value = str(template.get("composition") or "").strip()
        composition_path = _resource(root, composition_value)
        composition_report: dict[str, Any] = {"ok": False, "issues": []}
        if composition_path is None:
            errors.append(f"{path}.composition has an unsafe path")
        elif not composition_path.is_file():
            errors.append(f"{path}.composition is missing: {composition_value}")
        elif composition_path.suffix.casefold() != ".json":
            errors.append(f"{path}.composition must be a JSON Motion composition")
        else:
            try:
                raw_composition = json.loads(composition_path.read_text(encoding="utf-8"))
                if not isinstance(raw_composition, Mapping):
                    raise ValueError("composition root must be an object")
                composition = MotionComposition.from_dict(raw_composition)
                composition_report = validate_composition(composition).to_dict()
                for issue in composition_report["issues"]:
                    if issue.get("severity") == "error":
                        errors.append(
                            f"{path}.composition {issue.get('path') or '<root>'}: {issue.get('message')}"
                        )
            except Exception as exc:
                errors.append(
                    f"{path}.composition could not be parsed: {type(exc).__name__}: {exc}"
                )

        preview_value = str(template.get("preview") or "").strip()
        preview_path = _resource(root, preview_value) if preview_value else None
        if not preview_value:
            warnings.append(f"{path} has no preview image")
        elif preview_path is None:
            errors.append(f"{path}.preview has an unsafe path")
        elif not preview_path.is_file() or preview_path.suffix.casefold() not in PREVIEW_SUFFIXES:
            errors.append(f"{path}.preview must reference a PNG, JPEG, or WebP image")

        controls = template.get("published_controls", [])
        if not isinstance(controls, list):
            errors.append(f"{path}.published_controls must be an array")
            controls = []
        seen_controls: set[str] = set()
        normalized_controls = [
            _validate_control(item, f"{path}.published_controls[{control_index}]", seen_controls, errors)
            for control_index, item in enumerate(controls)
        ]
        normalized_templates.append({
            "id": template_id,
            "name": template_name,
            "category": category,
            "variants": [str(item) for item in variants],
            "composition": composition_value,
            "preview": preview_value,
            "published_controls": normalized_controls,
            "composition_validation": composition_report,
        })

    return {
        "ok": not errors,
        "schema": MOTION_TEMPLATE_PACK_SCHEMA,
        "source_path": str(source_path),
        "source_type": source_type,
        "manifest_path": (
            str(manifest_path) if source_type != "zip"
            else f"{source_path}!/{manifest_path.relative_to(root).as_posix()}"
        ),
        "pack": {
            "schema": schema,
            "id": pack_id,
            "name": name,
            "version": version,
            "vendor": vendor,
            "license": license_name,
            "templates": normalized_templates,
        },
        "file_count": file_count,
        "uncompressed_bytes": total_bytes,
        "runtime_loaded": False,
        "runtime_policy": "declarative_templates_only",
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def validate_motion_template_pack(source: str | Path) -> dict[str, Any]:
    source_path = Path(source).expanduser().resolve(strict=False)
    try:
        with _materialized_pack(source_path) as (root, manifest_path, source_type):
            return _validate_materialized(root, manifest_path, source_type, source_path)
    except Exception as exc:
        return {
            "ok": False,
            "schema": MOTION_TEMPLATE_PACK_SCHEMA,
            "source_path": str(source_path),
            "source_type": "unknown",
            "manifest_path": "",
            "pack": {},
            "file_count": 0,
            "uncompressed_bytes": 0,
            "runtime_loaded": False,
            "runtime_policy": "declarative_templates_only",
            "errors": [str(exc)],
            "warnings": [],
        }


def install_motion_template_pack(source: str | Path, *, destination_root: str | Path | None = None,
                                 replace: bool = False) -> dict[str, Any]:
    validation = validate_motion_template_pack(source)
    if not validation["ok"]:
        raise ValueError("Invalid Motion template pack: " + "; ".join(validation["errors"]))
    destination = Path(
        destination_root or motion_template_pack_user_root()
    ).expanduser().resolve(strict=False)
    if any(part.casefold() == "debugcapture" for part in destination.parts):
        raise ValueError("Template packs must be installed in durable storage, not debugCapture")
    destination.mkdir(parents=True, exist_ok=True)
    pack_id = str(validation["pack"]["id"])
    target = destination / pack_id
    if target.exists() and not replace:
        raise FileExistsError(f"Motion template pack is already installed: {pack_id}")

    staging = destination / f".{pack_id}.{os.getpid()}.{uuid.uuid4().hex}.staging"
    backup = destination / f".{pack_id}.{os.getpid()}.{uuid.uuid4().hex}.backup"
    source_path = Path(source).expanduser().resolve(strict=False)
    try:
        with _materialized_pack(source_path) as (root, _manifest_path, _source_type):
            shutil.copytree(root, staging, symlinks=False)
        installed_validation = validate_motion_template_pack(staging)
        if not installed_validation["ok"]:
            raise ValueError(
                "Staged Motion template pack failed validation: "
                + "; ".join(installed_validation["errors"])
            )
        if target.exists():
            target.rename(backup)
        staging.rename(target)
    except Exception:
        if target.exists() and backup.exists():
            shutil.rmtree(target)
        if backup.exists() and not target.exists():
            backup.rename(target)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if backup.exists():
            shutil.rmtree(backup)

    return {
        "ok": True,
        "pack_id": pack_id,
        "installed_path": str(target),
        "replaced": bool(replace),
        "template_count": len(validation["pack"]["templates"]),
        "validation": validation,
        "runtime_loaded": False,
        "restart_required": True,
        "runtime_policy": "declarative_templates_only",
    }


__all__ = [
    "MOTION_TEMPLATE_PACK_MANIFEST_NAME", "MOTION_TEMPLATE_PACK_SCHEMA",
    "install_motion_template_pack", "motion_template_pack_user_root",
    "validate_motion_template_pack",
]
