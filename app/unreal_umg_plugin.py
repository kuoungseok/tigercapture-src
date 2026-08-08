"""Bundled Tiger Studio UMG plugin discovery and project-local installation."""
from __future__ import annotations

import json
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLUGIN_NAME = "TigerStudioUMG"
PLUGIN_SOURCE_RELATIVE_ROOT = (
    Path("resources") / "unreal_plugins" / "UMG" / PLUGIN_NAME
)
PLUGIN_BUNDLE_RELATIVE_ROOT = (
    Path("bundled") / "unreal_plugins" / "UMG" / PLUGIN_NAME
)
PLUGIN_RELATIVE_ROOT = PLUGIN_SOURCE_RELATIVE_ROOT


def _replace_path_with_retry(
    source: Path,
    target: Path,
    *,
    attempts: int = 8,
) -> None:
    """Rename a plugin directory despite short-lived Windows scanner locks."""
    for attempt in range(max(1, int(attempts))):
        try:
            source.replace(target)
            return
        except PermissionError:
            if attempt + 1 >= attempts:
                raise
            time.sleep(0.05 * (attempt + 1))


def bundled_plugin_root() -> Path:
    roots: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        roots.append(Path(bundle_root))
    roots.append(Path(__file__).resolve().parents[1])
    roots.append(Path.cwd())
    for root in roots:
        for relative_root in (
            PLUGIN_BUNDLE_RELATIVE_ROOT,
            PLUGIN_SOURCE_RELATIVE_ROOT,
        ):
            candidate = root / relative_root
            if (candidate / f"{PLUGIN_NAME}.uplugin").is_file():
                return candidate
    raise FileNotFoundError(
        "Tiger Studio UMG plugin is missing from both the binary bundle and "
        f"source tree: {PLUGIN_BUNDLE_RELATIVE_ROOT}, {PLUGIN_SOURCE_RELATIVE_ROOT}"
    )


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def bundled_plugin_manifest() -> dict[str, Any]:
    return _read_json(bundled_plugin_root() / f"{PLUGIN_NAME}.uplugin")


def project_plugin_root(project_path: str | Path) -> Path:
    project = Path(project_path).expanduser().resolve()
    if project.suffix.lower() != ".uproject" or not project.is_file():
        raise ValueError(f"Valid .uproject file is required: {project}")
    return project.parent / "Plugins" / PLUGIN_NAME


@dataclass(frozen=True)
class UnrealUMGPluginStatus:
    project_path: str
    source_path: str
    installed_path: str
    bundled_version: str
    installed_version: str
    installed: bool
    enabled: bool
    update_required: bool
    restart_required: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "plugin_name": PLUGIN_NAME,
            "source_path": self.source_path,
            "installed_path": self.installed_path,
            "bundled_version": self.bundled_version,
            "installed_version": self.installed_version,
            "installed": self.installed,
            "enabled": self.enabled,
            "update_required": self.update_required,
            "restart_required": self.restart_required,
        }


def plugin_status(project_path: str | Path) -> UnrealUMGPluginStatus:
    project = Path(project_path).expanduser().resolve()
    source = bundled_plugin_root()
    target = project_plugin_root(project)
    bundled = bundled_plugin_manifest()
    installed_descriptor = target / f"{PLUGIN_NAME}.uplugin"
    installed_manifest = _read_json(installed_descriptor) if installed_descriptor.is_file() else {}
    project_payload = _read_json(project)
    enabled = any(
        isinstance(row, dict)
        and str(row.get("Name") or "") == PLUGIN_NAME
        and bool(row.get("Enabled", False))
        for row in project_payload.get("Plugins", [])
    )
    bundled_version = str(bundled.get("VersionName") or bundled.get("Version") or "")
    installed_version = str(
        installed_manifest.get("VersionName") or installed_manifest.get("Version") or ""
    )
    installed = installed_descriptor.is_file()
    update_required = installed and installed_version != bundled_version
    return UnrealUMGPluginStatus(
        project_path=str(project),
        source_path=str(source),
        installed_path=str(target),
        bundled_version=bundled_version,
        installed_version=installed_version,
        installed=installed,
        enabled=enabled,
        update_required=update_required,
        restart_required=(not installed) or update_required or (not enabled),
    )


def install_project_plugin(
    project_path: str | Path,
    *,
    enable: bool = True,
) -> UnrealUMGPluginStatus:
    project = Path(project_path).expanduser().resolve()
    source = bundled_plugin_root()
    target = project_plugin_root(project)
    plugins_dir = target.parent
    plugins_dir.mkdir(parents=True, exist_ok=True)
    staging = plugins_dir / f".{PLUGIN_NAME}.installing"
    backup = plugins_dir / f".{PLUGIN_NAME}.backup.{time.time_ns()}"

    if staging.exists():
        shutil.rmtree(staging)
    shutil.copytree(source, staging)
    if target.exists():
        _replace_path_with_retry(target, backup)
    try:
        _replace_path_with_retry(staging, target)
    except Exception:
        if backup.exists() and not target.exists():
            _replace_path_with_retry(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)

    if enable:
        payload = _read_json(project)
        plugins = payload.get("Plugins")
        if not isinstance(plugins, list):
            plugins = []
        row = next(
            (
                item
                for item in plugins
                if isinstance(item, dict) and str(item.get("Name") or "") == PLUGIN_NAME
            ),
            None,
        )
        if row is None:
            row = {"Name": PLUGIN_NAME, "Enabled": True}
            plugins.append(row)
        else:
            row["Enabled"] = True
        payload["Plugins"] = plugins
        temporary = project.with_suffix(project.suffix + ".tiger.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(project)

    return plugin_status(project)


__all__ = [
    "PLUGIN_NAME",
    "PLUGIN_BUNDLE_RELATIVE_ROOT",
    "PLUGIN_RELATIVE_ROOT",
    "PLUGIN_SOURCE_RELATIVE_ROOT",
    "UnrealUMGPluginStatus",
    "bundled_plugin_manifest",
    "bundled_plugin_root",
    "install_project_plugin",
    "plugin_status",
    "project_plugin_root",
]
