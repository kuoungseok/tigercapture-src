"""Action adapter methods for Painter UI Figma exchange."""
from __future__ import annotations

from typing import Any


class PaintUIFigmaAdapterMixin:
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
