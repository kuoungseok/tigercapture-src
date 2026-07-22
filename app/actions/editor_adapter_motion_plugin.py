"""Action adapter for Motion plugin and template-pack management."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from app.motion_designer.plugin_manifest import validate_motion_plugin_manifest
from app.motion_designer.plugin_registry import MotionPluginRegistry
from app.motion_designer.template_pack import (
    install_motion_template_pack,
    validate_motion_template_pack,
)


class MotionPluginAdapterMixin:
    @staticmethod
    def _motion_plugin_registry(
        plugin_roots: Iterable[str] | None = None,
    ) -> MotionPluginRegistry:
        roots = [Path(item) for item in plugin_roots] if plugin_roots is not None else None
        return MotionPluginRegistry(roots=roots)

    def motion_plugin_list(
        self,
        plugin_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._motion_plugin_registry(plugin_roots).list()

    def motion_plugin_inspect(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._motion_plugin_registry(plugin_roots).inspect(plugin_id)

    def motion_plugin_validate(self, path: str) -> dict[str, Any]:
        return validate_motion_plugin_manifest(path)

    def motion_plugin_enable(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._motion_plugin_registry(plugin_roots).set_enabled(plugin_id, True)

    def motion_plugin_disable(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._motion_plugin_registry(plugin_roots).set_enabled(plugin_id, False)

    def motion_template_pack_validate(self, path: str) -> dict[str, Any]:
        return validate_motion_template_pack(path)

    def motion_template_pack_install(
        self,
        path: str,
        replace: bool = False,
    ) -> dict[str, Any]:
        return install_motion_template_pack(
            path,
            replace=bool(replace),
        )


__all__ = ["MotionPluginAdapterMixin"]
