"""Discovery and persistent enable-state for declarative Motion plugins."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .plugin_manifest import MOTION_PLUGIN_MANIFEST_NAME, validate_motion_plugin_manifest


MOTION_PLUGIN_STATE_SCHEMA = "tigercapture.motion.plugin_state.v1"
ROOT = Path(__file__).resolve().parents[2]


def motion_plugin_user_root() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "TigerCapture" / "MotionDesigner" / "plugins"


def default_motion_plugin_roots() -> tuple[Path, ...]:
    return (ROOT / "resources" / "motion_plugins", motion_plugin_user_root())


def default_motion_plugin_state_path() -> Path:
    return motion_plugin_user_root().parent / "plugin_state.json"


def _read_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema": MOTION_PLUGIN_STATE_SCHEMA, "enabled": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Could not read Motion plugin state: {type(exc).__name__}: {exc}") from exc
    if not isinstance(value, Mapping) or value.get("schema") != MOTION_PLUGIN_STATE_SCHEMA:
        raise ValueError("Unsupported Motion plugin state file")
    enabled = value.get("enabled", {})
    if not isinstance(enabled, Mapping):
        raise ValueError("Motion plugin enabled state must be an object")
    return {**dict(value), "enabled": {str(key): bool(item) for key, item in enabled.items()}}


def _write_state(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(dict(value), stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _manifest_candidates(roots: Iterable[Path]) -> list[Path]:
    candidates: set[Path] = set()
    for root in roots:
        base = root.expanduser().resolve(strict=False)
        if base.is_file():
            candidates.add(base)
            continue
        direct = base / MOTION_PLUGIN_MANIFEST_NAME
        if direct.is_file():
            candidates.add(direct)
        if not base.is_dir():
            continue
        candidates.update(path.resolve() for path in base.glob(f"*/{MOTION_PLUGIN_MANIFEST_NAME}"))
        candidates.update(path.resolve() for path in base.glob("*.motion-plugin.json"))
    return sorted(candidates, key=lambda path: str(path).casefold())


def _version_major(value: str) -> int | None:
    digits = ""
    for character in str(value or "").lstrip("^~>= "):
        if not character.isdigit():
            break
        digits += character
    return int(digits) if digits else None


class MotionPluginRegistry:
    """Scans manifests and stores enable state without importing plugin code."""

    def __init__(self, roots: Iterable[str | Path] | None = None, *,
                 state_path: str | Path | None = None) -> None:
        self.roots = tuple(
            Path(path).expanduser().resolve(strict=False)
            for path in (roots if roots is not None else default_motion_plugin_roots())
        )
        self.state_path = Path(
            state_path or default_motion_plugin_state_path()
        ).expanduser().resolve(strict=False)

    def list(self) -> dict[str, Any]:
        state = _read_state(self.state_path)
        enabled_state = dict(state.get("enabled") or {})
        rows = []
        by_id: dict[str, list[dict[str, Any]]] = {}
        for path in _manifest_candidates(self.roots):
            validation = validate_motion_plugin_manifest(path)
            plugin = dict(validation.get("plugin") or {})
            plugin_id = str(plugin.get("id") or "")
            row = {
                "id": plugin_id,
                "name": str(plugin.get("name") or ""),
                "version": str(plugin.get("version") or ""),
                "vendor": str(plugin.get("vendor") or ""),
                "api_version": str(plugin.get("api_version") or ""),
                "manifest_path": validation["manifest_path"],
                "plugin_root": validation["plugin_root"],
                "valid": bool(validation["ok"]),
                "enabled": bool(enabled_state.get(plugin_id, plugin.get("default_enabled", False))),
                "runtime_loaded": False,
                "restart_required": False,
                "capabilities": list(plugin.get("capabilities") or []),
                "contribution_counts": {
                    kind: len(items)
                    for kind, items in dict(plugin.get("contributions") or {}).items()
                },
                "dependencies": dict(plugin.get("dependencies") or {}),
                "errors": list(validation.get("errors") or []),
                "warnings": list(validation.get("warnings") or []),
            }
            rows.append(row)
            if plugin_id:
                by_id.setdefault(plugin_id, []).append(row)
        duplicate_ids = sorted(plugin_id for plugin_id, items in by_id.items() if len(items) > 1)
        for plugin_id in duplicate_ids:
            for row in by_id[plugin_id]:
                row["valid"] = False
                row["errors"].append(f"Duplicate Motion plugin id: {plugin_id}")
                row["enabled"] = False
        invalid_enabled = sorted(
            plugin_id for plugin_id, enabled in enabled_state.items()
            if enabled and (plugin_id not in by_id or not any(row["valid"] for row in by_id[plugin_id]))
        )
        return {
            "ok": not duplicate_ids and not invalid_enabled,
            "schema": "tigercapture.motion.plugin_registry.v1",
            "roots": [str(path) for path in self.roots],
            "state_path": str(self.state_path),
            "count": len(rows),
            "enabled_count": sum(1 for row in rows if row["enabled"] and row["valid"]),
            "duplicate_ids": duplicate_ids,
            "invalid_enabled_ids": invalid_enabled,
            "plugins": rows,
            "runtime_policy": "declarative_registration_only",
        }

    def inspect(self, plugin_id: str) -> dict[str, Any]:
        target = str(plugin_id or "").strip()
        matches = [row for row in self.list()["plugins"] if row["id"] == target]
        if not matches:
            raise ValueError(f"Motion plugin not found: {target}")
        if len(matches) > 1:
            raise ValueError(f"Motion plugin id is ambiguous: {target}")
        validation = validate_motion_plugin_manifest(matches[0]["manifest_path"])
        return {**matches[0], "validation": validation}

    def set_enabled(self, plugin_id: str, enabled: bool) -> dict[str, Any]:
        row = self.inspect(plugin_id)
        if enabled and not row["valid"]:
            raise ValueError("Invalid Motion plugin cannot be enabled")
        listing = self.list()
        by_id = {item["id"]: item for item in listing["plugins"] if item["valid"]}
        state = _read_state(self.state_path)
        enabled_state = dict(state.get("enabled") or {})
        if enabled:
            for dependency in row["dependencies"].get("plugins", []):
                dependency_id = str(dependency.get("id") or "")
                candidate = by_id.get(dependency_id)
                if candidate is None:
                    raise ValueError(f"Required Motion plugin is missing: {dependency_id}")
                required_version = str(dependency.get("version") or "")
                if required_version and _version_major(required_version) != _version_major(candidate["version"]):
                    raise ValueError(
                        f"Motion plugin dependency version mismatch: {dependency_id} {required_version}"
                    )
                if not bool(enabled_state.get(dependency_id, candidate.get("enabled", False))):
                    raise ValueError(f"Required Motion plugin is disabled: {dependency_id}")
        else:
            dependents = []
            for candidate in by_id.values():
                if not bool(enabled_state.get(candidate["id"], candidate.get("enabled", False))):
                    continue
                required_ids = {
                    str(item.get("id") or "")
                    for item in candidate["dependencies"].get("plugins", [])
                    if isinstance(item, Mapping)
                }
                if row["id"] in required_ids:
                    dependents.append(candidate["id"])
            if dependents:
                raise ValueError(
                    "Disable dependent Motion plugins first: " + ", ".join(sorted(dependents))
                )
        previous = bool(enabled_state.get(row["id"], row.get("enabled", False)))
        enabled_state[row["id"]] = bool(enabled)
        updated = {
            "schema": MOTION_PLUGIN_STATE_SCHEMA,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "enabled": enabled_state,
        }
        _write_state(self.state_path, updated)
        return {
            "ok": True,
            "plugin_id": row["id"],
            "enabled": bool(enabled),
            "changed": previous != bool(enabled),
            "state_path": str(self.state_path),
            "runtime_loaded": False,
            "restart_required": True,
            "runtime_policy": "declarative_registration_only",
        }


__all__ = [
    "MOTION_PLUGIN_STATE_SCHEMA", "MotionPluginRegistry", "default_motion_plugin_roots",
    "default_motion_plugin_state_path", "motion_plugin_user_root",
]
