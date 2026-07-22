"""Versioned, declarative Motion Designer plugin manifest validation."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping


MOTION_PLUGIN_SCHEMA = "tigercapture.motion.plugin.v1"
MOTION_PLUGIN_API_VERSION = "1.0"
MOTION_PLUGIN_MANIFEST_NAME = "plugin.json"
PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
VERSION_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+){1,2}(?:[-+][0-9A-Za-z.-]+)?$")
CONTRIBUTION_KINDS = frozenset({"sources", "effects", "behaviors", "exporters", "templates"})
CORE_PLUGIN_CAPABILITIES = frozenset({
    "motion.source.v1", "motion.effect_descriptor.v1", "motion.behavior.v1",
    "motion.exporter.v1", "motion.template_pack.v1", "motion.inspector_schema.v1",
    "motion.action.v1",
})


def _manifest_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    return candidate / MOTION_PLUGIN_MANIFEST_NAME if candidate.is_dir() else candidate


def _major(version: str) -> int | None:
    match = re.match(r"^\s*(?:\^|~|>=?)?\s*([0-9]+)", str(version or ""))
    return int(match.group(1)) if match else None


def _safe_resource(root: Path, value: str) -> Path | None:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return None
    relative = Path(text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return candidate


def _load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"Could not read plugin manifest: {type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return {}, "Plugin manifest root must be an object"
    return value, ""


def validate_motion_plugin_manifest(path: str | Path, *,
                                    host_api_version: str = MOTION_PLUGIN_API_VERSION) -> dict[str, Any]:
    manifest_path = _manifest_path(path)
    plugin_root = manifest_path.parent.resolve(strict=False)
    errors: list[str] = []
    warnings: list[str] = []
    if not manifest_path.is_file():
        errors.append(f"Plugin manifest not found: {manifest_path}")
        data: dict[str, Any] = {}
    else:
        data, read_error = _load_manifest(manifest_path)
        if read_error:
            errors.append(read_error)

    schema = str(data.get("schema") or "")
    plugin_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    vendor = str(data.get("vendor") or "").strip()
    api_version = str(data.get("api_version") or "").strip()
    if schema != MOTION_PLUGIN_SCHEMA:
        errors.append(f"Unsupported Motion plugin schema: {schema or '<missing>'}")
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        errors.append("Plugin id must be a stable lowercase dotted, dashed, or underscored id")
    if not name:
        errors.append("Plugin display name is required")
    if not VERSION_PATTERN.fullmatch(version):
        errors.append("Plugin version must be a semantic numeric version")
    if not vendor:
        errors.append("Plugin vendor is required")
    if _major(api_version) != _major(host_api_version):
        errors.append(
            f"Plugin API {api_version or '<missing>'} is incompatible with host API {host_api_version}"
        )

    capabilities = data.get("capabilities", [])
    if not isinstance(capabilities, list) or any(not isinstance(item, str) for item in capabilities):
        errors.append("Plugin capabilities must be an array of strings")
        capabilities = []
    unknown_capabilities = sorted(set(capabilities) - CORE_PLUGIN_CAPABILITIES)
    if unknown_capabilities:
        errors.append(f"Unsupported plugin capability: {unknown_capabilities[0]}")

    dependencies = data.get("dependencies", {})
    if dependencies is None:
        dependencies = {}
    if not isinstance(dependencies, Mapping):
        errors.append("Plugin dependencies must be an object")
        dependencies = {}
    plugin_dependencies = dependencies.get("plugins", [])
    capability_dependencies = dependencies.get("capabilities", [])
    if not isinstance(plugin_dependencies, list):
        errors.append("Plugin dependencies.plugins must be an array")
        plugin_dependencies = []
    if not isinstance(capability_dependencies, list) or any(
        not isinstance(item, str) for item in capability_dependencies
    ):
        errors.append("Plugin dependencies.capabilities must be an array of strings")
        capability_dependencies = []
    for dependency in plugin_dependencies:
        if not isinstance(dependency, Mapping) or not PLUGIN_ID_PATTERN.fullmatch(
            str(dependency.get("id") or "")
        ):
            errors.append("Each plugin dependency requires a valid id")
            continue
        required_version = str(dependency.get("version") or "").strip()
        if required_version and _major(required_version) is None:
            errors.append(f"Invalid dependency version for {dependency.get('id')}")
    unsupported_dependencies = sorted(set(capability_dependencies) - CORE_PLUGIN_CAPABILITIES)
    if unsupported_dependencies:
        errors.append(f"Unavailable host capability: {unsupported_dependencies[0]}")

    contributions = data.get("contributions", {})
    if not isinstance(contributions, Mapping):
        errors.append("Plugin contributions must be an object")
        contributions = {}
    unknown_kinds = sorted(set(str(key) for key in contributions) - CONTRIBUTION_KINDS)
    if unknown_kinds:
        errors.append(f"Unsupported plugin contribution kind: {unknown_kinds[0]}")
    normalized_contributions: dict[str, list[dict[str, Any]]] = {}
    contribution_ids: set[str] = set()
    resource_paths: list[str] = []
    for kind in CONTRIBUTION_KINDS:
        rows = contributions.get(kind, [])
        if not isinstance(rows, list):
            errors.append(f"Plugin contributions.{kind} must be an array")
            continue
        normalized: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                errors.append(f"Plugin contribution {kind}[{index}] must be an object")
                continue
            contribution_id = str(row.get("id") or "").strip()
            if not PLUGIN_ID_PATTERN.fullmatch(contribution_id):
                errors.append(f"Plugin contribution {kind}[{index}] requires a valid id")
            elif contribution_id in contribution_ids:
                errors.append(f"Duplicate plugin contribution id: {contribution_id}")
            contribution_ids.add(contribution_id)
            label = str(row.get("label") or "").strip()
            if not label:
                errors.append(f"Plugin contribution {contribution_id or kind} requires a label")
            descriptor = str(row.get("descriptor") or row.get("entry") or "").strip()
            resolved = _safe_resource(plugin_root, descriptor)
            if not descriptor or resolved is None:
                errors.append(f"Plugin contribution {contribution_id or kind} has an unsafe descriptor path")
            elif not resolved.is_file():
                errors.append(f"Plugin contribution descriptor is missing: {descriptor}")
            elif resolved.suffix.casefold() != ".json":
                errors.append(
                    f"Plugin contribution {contribution_id or kind} must use a declarative JSON descriptor"
                )
            else:
                try:
                    descriptor_data = json.loads(resolved.read_text(encoding="utf-8"))
                    if not isinstance(descriptor_data, Mapping):
                        raise ValueError("descriptor root must be an object")
                except Exception as exc:
                    errors.append(
                        f"Plugin contribution descriptor is invalid: {descriptor}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                else:
                    resource_paths.append(str(resolved))
            normalized.append({
                "id": contribution_id,
                "label": label,
                "descriptor": descriptor,
                "kind": kind,
            })
        if normalized:
            normalized_contributions[kind] = normalized
    if not normalized_contributions:
        warnings.append("Plugin declares no contributions")

    return {
        "ok": not errors,
        "schema": MOTION_PLUGIN_SCHEMA,
        "host_api_version": host_api_version,
        "manifest_path": str(manifest_path),
        "plugin_root": str(plugin_root),
        "plugin": {
            "schema": schema,
            "id": plugin_id,
            "name": name,
            "version": version,
            "vendor": vendor,
            "api_version": api_version,
            "capabilities": list(capabilities),
            "dependencies": {
                "plugins": [dict(item) for item in plugin_dependencies if isinstance(item, Mapping)],
                "capabilities": list(capability_dependencies),
            },
            "contributions": normalized_contributions,
            "default_enabled": bool(data.get("default_enabled", False)),
        },
        "resource_paths": resource_paths,
        "runtime_loaded": False,
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
    }


__all__ = [
    "CONTRIBUTION_KINDS", "CORE_PLUGIN_CAPABILITIES", "MOTION_PLUGIN_API_VERSION",
    "MOTION_PLUGIN_MANIFEST_NAME", "MOTION_PLUGIN_SCHEMA", "validate_motion_plugin_manifest",
]
