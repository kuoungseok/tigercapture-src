"""Safe metadata preflight for local Figma plugin packages.

FP1 deliberately reads package metadata only.  It never imports or executes the
plugin's JavaScript entry point.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping

from app.painter_ui_figma_plugin_network import (
    figma_plugin_network_reasoning_required,
    validate_figma_plugin_domains,
)


FIGMA_PLUGIN_MANIFEST_NAME = "manifest.json"
FIGMA_PLUGIN_API_VERSION = "1.0.0"
FIGMA_PLUGIN_PREFLIGHT_SCHEMA = "tigercapture.painter.figma_plugin_preflight.v1"
PLUGIN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
KNOWN_PERMISSIONS = frozenset({
    "currentuser", "activeusers", "fileusers", "payments", "teamlibrary",
})


def _manifest_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser().resolve(strict=False)
    return candidate / FIGMA_PLUGIN_MANIFEST_NAME if candidate.is_dir() else candidate


def _safe_resource(root: Path, value: object) -> Path | None:
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


def _read_manifest(path: Path) -> tuple[dict[str, Any], str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, f"Could not read Figma plugin manifest: {type(exc).__name__}: {exc}"
    if not isinstance(value, dict):
        return {}, "Figma plugin manifest root must be an object"
    return value, ""


def validate_figma_plugin_manifest(path: str | Path) -> dict[str, Any]:
    """Validate an installable package without loading any plugin code."""
    manifest_path = _manifest_path(path)
    root = manifest_path.parent.resolve(strict=False)
    errors: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    resources: list[str] = []
    if not manifest_path.is_file():
        data: dict[str, Any] = {}
        errors.append(f"Figma plugin manifest not found: {manifest_path}")
    else:
        data, read_error = _read_manifest(manifest_path)
        if read_error:
            errors.append(read_error)

    plugin_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    api = str(data.get("api") or "").strip()
    if not PLUGIN_ID_PATTERN.fullmatch(plugin_id):
        errors.append("Figma plugin id must be a stable path-free identifier")
    if not name:
        errors.append("Figma plugin display name is required")
    if api != FIGMA_PLUGIN_API_VERSION:
        errors.append(
            f"Unsupported Figma Plugin API: {api or '<missing>'}; "
            f"expected {FIGMA_PLUGIN_API_VERSION}"
        )

    editor_types = data.get("editorType", [])
    if not isinstance(editor_types, list) or any(not isinstance(item, str) for item in editor_types):
        errors.append("Figma plugin editorType must be an array of strings")
        editor_types = []
    if "figma" not in editor_types:
        blockers.append("Plugin does not declare the Figma Design editor")

    main_value = str(data.get("main") or "").strip()
    main_path = _safe_resource(root, main_value)
    if main_path is None:
        errors.append("Figma plugin main path is missing or unsafe")
    elif main_path.suffix.casefold() not in {".js", ".mjs"}:
        errors.append("Figma plugin main entry must be JavaScript")
    elif not main_path.is_file():
        errors.append(f"Figma plugin main entry is missing: {main_value}")
    else:
        resources.append(str(main_path))

    ui_value = data.get("ui")
    ui_entries: dict[str, str] = {}
    if isinstance(ui_value, str):
        ui_entries["default"] = ui_value
    elif isinstance(ui_value, Mapping):
        for key, value in ui_value.items():
            if not isinstance(key, str) or not isinstance(value, str):
                errors.append("Figma plugin ui map must contain string paths")
                continue
            ui_entries[key] = value
    elif ui_value is not None:
        errors.append("Figma plugin ui must be a path or a map of paths")
    for key, value in ui_entries.items():
        ui_path = _safe_resource(root, value)
        if ui_path is None:
            errors.append(f"Figma plugin ui path is unsafe: {key}")
        elif ui_path.suffix.casefold() not in {".html", ".htm"}:
            errors.append(f"Figma plugin ui entry must be HTML: {value}")
        elif not ui_path.is_file():
            errors.append(f"Figma plugin ui entry is missing: {value}")
        else:
            resources.append(str(ui_path))

    document_access = str(data.get("documentAccess") or "").strip()
    if document_access != "dynamic-page":
        blockers.append("Only documentAccess=dynamic-page is planned for the Painter host")
    if bool(data.get("enablePrivatePluginApi")):
        blockers.append("Private Figma Plugin API is not supported")
    if bool(data.get("enableProposedApi")):
        blockers.append("Proposed Figma Plugin API is not supported")

    permissions = data.get("permissions", [])
    if permissions is None:
        permissions = []
    if not isinstance(permissions, list) or any(not isinstance(item, str) for item in permissions):
        errors.append("Figma plugin permissions must be an array of strings")
        permissions = []
    unknown_permissions = sorted(set(permissions) - KNOWN_PERMISSIONS)
    if unknown_permissions:
        warnings.append(f"Unknown Figma plugin permission: {unknown_permissions[0]}")
    if permissions:
        blockers.append("User/team/payment permissions are not supported by the initial runtime")

    network_declared = "networkAccess" in data
    network_access = data.get("networkAccess", {})
    if network_access is None:
        network_access = {}
    if not isinstance(network_access, Mapping):
        errors.append("Figma plugin networkAccess must be an object")
        network_access = {}
    allowed_domains, domain_errors = validate_figma_plugin_domains(
        network_access.get("allowedDomains", []),
        field="networkAccess.allowedDomains",
    )
    errors.extend(domain_errors)
    if network_declared and not allowed_domains:
        errors.append("Figma plugin networkAccess.allowedDomains must contain at least one pattern")
    dev_allowed_domains, dev_domain_errors = validate_figma_plugin_domains(
        network_access.get("devAllowedDomains", []),
        field="networkAccess.devAllowedDomains",
    )
    errors.extend(dev_domain_errors)
    reasoning = str(network_access.get("reasoning") or "").strip()
    try:
        reasoning_required = figma_plugin_network_reasoning_required(allowed_domains)
    except ValueError:
        reasoning_required = False
    if reasoning_required and not reasoning:
        errors.append("Figma plugin networkAccess.reasoning is required for '*' or local domains")
    network_requested = bool(allowed_domains and allowed_domains != ["none"])
    if network_requested:
        warnings.append("Network domains require explicit approval for each Plugin UI run")
    if dev_allowed_domains:
        warnings.append("devAllowedDomains are ignored outside an explicit development run")

    menu = data.get("menu", [])
    if menu is None:
        menu = []
    if not isinstance(menu, list):
        errors.append("Figma plugin menu must be an array")
        menu = []

    capabilities = ["manifest", "main"]
    if ui_entries:
        capabilities.append("ui")
    if menu:
        capabilities.append("commands")
    if network_requested:
        capabilities.append("network")
    if permissions:
        capabilities.append("permissions")

    warnings.append("FP2 runtime readiness requires a separate main-source preflight")
    return {
        "ok": not errors,
        "schema": FIGMA_PLUGIN_PREFLIGHT_SCHEMA,
        "manifest_path": str(manifest_path),
        "plugin_root": str(root),
        "plugin": {
            "id": plugin_id,
            "name": name,
            "api": api,
            "editor_types": list(editor_types),
            "main": main_value,
            "ui": dict(ui_entries),
            "document_access": document_access,
            "permissions": list(permissions),
            "allowed_domains": list(allowed_domains),
            "dev_allowed_domains": list(dev_allowed_domains),
            "network_reasoning": reasoning,
            "network_approval_required": network_requested,
            "capabilities": capabilities,
            "command_count": len(menu),
        },
        "resource_paths": resources,
        "installable": not errors,
        "runtime_ready": False,
        "runtime_policy": "metadata_only_no_code_execution",
        "compatibility": "blocked" if blockers else "source_preflight_required",
        "blockers": list(dict.fromkeys(blockers)),
        "errors": list(dict.fromkeys(errors)),
        "warnings": list(dict.fromkeys(warnings)),
    }


__all__ = [
    "FIGMA_PLUGIN_API_VERSION",
    "FIGMA_PLUGIN_MANIFEST_NAME",
    "FIGMA_PLUGIN_PREFLIGHT_SCHEMA",
    "validate_figma_plugin_manifest",
]
