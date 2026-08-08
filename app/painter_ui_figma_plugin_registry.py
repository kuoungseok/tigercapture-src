"""Install and discover Figma plugin packages without executing their code."""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Iterable

from app.painter_ui_figma_plugin_manifest import (
    FIGMA_PLUGIN_MANIFEST_NAME,
    validate_figma_plugin_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
MAX_PACKAGE_FILES = 2_000
MAX_PACKAGE_BYTES = 64 * 1024 * 1024


def figma_plugin_user_root() -> Path:
    local = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    return local / "TigerCapture" / "PainterUI" / "figma_plugins"


def default_figma_plugin_roots() -> tuple[Path, ...]:
    return (ROOT / "resources" / "painter_ui_figma_plugins", figma_plugin_user_root())


def _manifest_candidates(roots: Iterable[Path]) -> list[Path]:
    candidates: set[Path] = set()
    for root in roots:
        base = root.expanduser().resolve(strict=False)
        if base.is_file():
            candidates.add(base)
            continue
        direct = base / FIGMA_PLUGIN_MANIFEST_NAME
        if direct.is_file():
            candidates.add(direct)
        if base.is_dir():
            candidates.update(
                path.resolve() for path in base.glob(f"*/{FIGMA_PLUGIN_MANIFEST_NAME}")
            )
    return sorted(candidates, key=lambda path: str(path).casefold())


def _package_budget(root: Path) -> tuple[int, int]:
    count = 0
    total = 0
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Figma plugin package cannot contain symlinks: {path.name}")
        if not path.is_file():
            continue
        count += 1
        total += path.stat().st_size
        if count > MAX_PACKAGE_FILES:
            raise ValueError("Figma plugin package contains too many files")
        if total > MAX_PACKAGE_BYTES:
            raise ValueError("Figma plugin package exceeds the 64 MiB FP1 limit")
    return count, total


class PainterFigmaPluginRegistry:
    """Metadata-only FP1 registry; JavaScript is never loaded here."""

    def __init__(
        self,
        roots: Iterable[str | Path] | None = None,
        *,
        install_root: str | Path | None = None,
    ) -> None:
        self.install_root = Path(
            install_root or figma_plugin_user_root()
        ).expanduser().resolve(strict=False)
        self.roots = tuple(
            Path(path).expanduser().resolve(strict=False)
            for path in (roots if roots is not None else default_figma_plugin_roots())
        )

    def list(self) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        by_id: dict[str, list[dict[str, Any]]] = {}
        for path in _manifest_candidates(self.roots):
            validation = validate_figma_plugin_manifest(path)
            plugin = dict(validation.get("plugin") or {})
            runtime_errors: list[str] = []
            ui_runtime_errors: list[str] = []
            ui_runtime_ready = False
            source_preflight: dict[str, Any] = {}
            if validation["ok"] and not validation.get("blockers"):
                from app.painter_ui_figma_plugin_runtime import preflight_figma_plugin_source

                main_path = Path(validation["plugin_root"]) / str(plugin.get("main") or "")
                source = main_path.read_text(encoding="utf-8")
                source_preflight = preflight_figma_plugin_source(source)
                if source_preflight.get("requires_plugin_ui"):
                    from app.painter_ui_figma_plugin_ui_session import (
                        preflight_figma_plugin_ui_source,
                    )

                    ui_entries = dict(plugin.get("ui") or {})
                    ui_name = ui_entries.get("default") or next(iter(ui_entries.values()), "")
                    if not ui_name:
                        ui_runtime_errors.append("Plugin UI source has no manifest ui entry")
                    else:
                        html_path = Path(validation["plugin_root"]) / ui_name
                        ui_preflight = preflight_figma_plugin_ui_source(
                            source, html_path.read_text(encoding="utf-8")
                        )
                        ui_runtime_errors = list(ui_preflight["errors"])
                        ui_runtime_ready = bool(ui_preflight["ok"])
                else:
                    runtime_errors = list(source_preflight["errors"])
            runtime_ready = bool(
                validation["ok"] and not validation.get("blockers") and not runtime_errors
                and not source_preflight.get("requires_plugin_ui", False)
            )
            row = {
                "id": str(plugin.get("id") or ""),
                "name": str(plugin.get("name") or ""),
                "api": str(plugin.get("api") or ""),
                "manifest_path": validation["manifest_path"],
                "plugin_root": validation["plugin_root"],
                "valid": bool(validation["ok"]),
                "installable": bool(validation["installable"]),
                "runtime_ready": runtime_ready,
                "ui_runtime_ready": ui_runtime_ready,
                "runtime_policy": (
                    "isolated_allowlist_fp2" if runtime_ready else
                    "isolated_limited_ui_fp3" if ui_runtime_ready else
                    "metadata_only_no_code_execution"
                ),
                "compatibility": (
                    "fp2_basic" if runtime_ready else
                    "fp3_limited_ui" if ui_runtime_ready else
                    validation["compatibility"]
                ),
                "capabilities": list(plugin.get("capabilities") or []),
                "allowed_domains": list(plugin.get("allowed_domains") or []),
                "network_reasoning": str(plugin.get("network_reasoning") or ""),
                "network_approval_required": bool(plugin.get("network_approval_required")),
                "blockers": list(validation.get("blockers") or []) + runtime_errors + ui_runtime_errors,
                "errors": list(validation.get("errors") or []),
                "warnings": list(validation.get("warnings") or []),
            }
            rows.append(row)
            if row["id"]:
                by_id.setdefault(row["id"], []).append(row)
        duplicates = sorted(key for key, values in by_id.items() if len(values) > 1)
        for plugin_id in duplicates:
            for row in by_id[plugin_id]:
                row["valid"] = False
                row["installable"] = False
                row["errors"].append(f"Duplicate Figma plugin id: {plugin_id}")
        return {
            "ok": not duplicates and all(row["valid"] for row in rows),
            "schema": "tigercapture.painter.figma_plugin_registry.v1",
            "roots": [str(path) for path in self.roots],
            "install_root": str(self.install_root),
            "count": len(rows),
            "duplicate_ids": duplicates,
            "plugins": rows,
            "runtime_ready_count": sum(1 for row in rows if row["runtime_ready"]),
            "ui_runtime_ready_count": sum(1 for row in rows if row["ui_runtime_ready"]),
            "runtime_policy": "isolated_allowlist_fp2_and_limited_ui_fp3",
        }

    def inspect(self, plugin_id: str) -> dict[str, Any]:
        target = str(plugin_id or "").strip()
        matches = [row for row in self.list()["plugins"] if row["id"] == target]
        if not matches:
            raise ValueError(f"Figma plugin not found: {target}")
        if len(matches) > 1:
            raise ValueError(f"Figma plugin id is ambiguous: {target}")
        return {**matches[0], "validation": validate_figma_plugin_manifest(matches[0]["manifest_path"])}

    def install(self, source: str | Path) -> dict[str, Any]:
        validation = validate_figma_plugin_manifest(source)
        if not validation["installable"]:
            raise ValueError("Invalid Figma plugin package: " + "; ".join(validation["errors"]))
        source_root = Path(validation["plugin_root"]).resolve(strict=True)
        file_count, byte_count = _package_budget(source_root)
        plugin_id = str(validation["plugin"]["id"])
        self.install_root.mkdir(parents=True, exist_ok=True)
        target = (self.install_root / plugin_id).resolve(strict=False)
        if target.parent != self.install_root or target.exists():
            raise ValueError(f"Figma plugin is already installed or target is unsafe: {plugin_id}")
        staging = self.install_root / f".{plugin_id}.{uuid.uuid4().hex}.installing"
        try:
            shutil.copytree(source_root, staging)
            copied = validate_figma_plugin_manifest(staging)
            if not copied["installable"] or copied["plugin"]["id"] != plugin_id:
                raise ValueError("Copied Figma plugin package failed validation")
            os.replace(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "install_path": str(target),
            "file_count": file_count,
            "byte_count": byte_count,
            "runtime_ready": False,
            "runtime_policy": "metadata_only_no_code_execution",
            "blockers": list(validation["blockers"]),
        }

    def remove(self, plugin_id: str) -> dict[str, Any]:
        row = self.inspect(plugin_id)
        root = Path(row["plugin_root"]).resolve(strict=True)
        if root.parent != self.install_root or root.is_symlink():
            raise ValueError("Only plugins installed in the writable user root can be removed")
        shutil.rmtree(root)
        return {
            "ok": True,
            "plugin_id": row["id"],
            "removed_path": str(root),
            "runtime_policy": "metadata_only_no_code_execution",
        }


__all__ = [
    "PainterFigmaPluginRegistry",
    "default_figma_plugin_roots",
    "figma_plugin_user_root",
]
