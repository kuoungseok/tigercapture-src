"""Action adapter methods for Painter UI Figma exchange."""
from __future__ import annotations

from pathlib import Path
from typing import Any


class PaintUIFigmaAdapterMixin:
    @staticmethod
    def _paint_ui_figma_plugin_registry(
        plugin_roots: list[str] | None = None,
        install_root: str = "",
    ):
        from app.painter_ui_figma_plugin_registry import PainterFigmaPluginRegistry

        roots = [Path(item) for item in plugin_roots] if plugin_roots is not None else None
        return PainterFigmaPluginRegistry(
            roots,
            install_root=Path(install_root) if install_root else None,
        )

    def paint_ui_figma_plugin_validate(self, path: str) -> dict[str, Any]:
        from app.painter_ui_figma_plugin_manifest import validate_figma_plugin_manifest

        return validate_figma_plugin_manifest(path)

    def paint_ui_figma_plugin_list(
        self,
        plugin_roots: list[str] | None = None,
        install_root: str = "",
    ) -> dict[str, Any]:
        return self._paint_ui_figma_plugin_registry(plugin_roots, install_root).list()

    def paint_ui_figma_plugin_inspect(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
        install_root: str = "",
    ) -> dict[str, Any]:
        return self._paint_ui_figma_plugin_registry(
            plugin_roots, install_root
        ).inspect(plugin_id)

    def paint_ui_figma_plugin_install(
        self,
        path: str,
        plugin_roots: list[str] | None = None,
        install_root: str = "",
    ) -> dict[str, Any]:
        return self._paint_ui_figma_plugin_registry(
            plugin_roots, install_root
        ).install(path)

    def paint_ui_figma_plugin_remove(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
        install_root: str = "",
    ) -> dict[str, Any]:
        return self._paint_ui_figma_plugin_registry(
            plugin_roots, install_root
        ).remove(plugin_id)

    def paint_ui_figma_plugin_run(
        self,
        plugin_id: str,
        plugin_roots: list[str] | None = None,
        install_root: str = "",
        timeout_ms: int = 750,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        registry = self._paint_ui_figma_plugin_registry(plugin_roots, install_root)
        from app.painter_ui_figma_plugin_runtime import run_installed_figma_plugin

        document, report = run_installed_figma_plugin(
            registry, plugin_id, dialog._painter_ui_document, timeout_ms=int(timeout_ms)
        )
        dialog._push_undo_state("Run Figma plugin")
        state = self._paint_ui_commit(dialog, "Run Figma plugin", document)
        return {**state, "figma_plugin": report}

    def paint_ui_figma_compatibility_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_figma import inspect_figma_compatibility

        return inspect_figma_compatibility(dialog._painter_ui_document)

    def paint_ui_figma_import(
        self,
        *,
        source: str,
        token: str = "",
        mode: str = "replace",
        json_snapshot: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_figma import (
            import_figma_file,
            import_figma_json,
            merge_figma_document,
        )

        if json_snapshot:
            imported, report = import_figma_json(source)
        else:
            imported, report = import_figma_file(source, token=token)
        document = merge_figma_document(
            dialog._painter_ui_document,
            imported,
            mode=mode,
        )
        dialog._push_undo_state("Import Figma UI")
        self._paint_ui_commit(dialog, "Import Figma UI", document)
        return {
            **dialog.painter_action_state(),
            "figma_import": report,
            "import_mode": str(mode),
        }

    def paint_ui_figma_export(self, *, output_dir: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_figma import export_figma_plugin_package

        return export_figma_plugin_package(
            dialog._painter_ui_document,
            output_dir,
        )


__all__ = ["PaintUIFigmaAdapterMixin"]
