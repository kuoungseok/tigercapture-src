"""Paint / drawing action adapter methods."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt

from app.actions.editor_adapter_object_helpers import _int
from app.actions.editor_adapter_paint_ui_advanced import (
    PaintUIAdvancedAdapterMixin,
)
from app.actions.editor_adapter_paint_ui_figma import PaintUIFigmaAdapterMixin


class PaintAdapterMixin(
    PaintUIAdvancedAdapterMixin,
    PaintUIFigmaAdapterMixin,
):
    """Registered action surface for paint dialog object import workflows."""

    def paint_state(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dialog.painter_action_state()

    def paint_gpu_status(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_opengl import painter_opengl_status

        status = painter_opengl_status()
        state = dialog.painter_action_state()
        return {
            **status,
            "last_blockout_renderer": dict(state.get("gpu", {}).get("blockout_renderer", {}) or {}),
            "last_canvas_renderer": dict(state.get("gpu", {}).get("canvas_renderer", {}) or {}),
            "remote_work_contract": {
                "safe_for_rdp": True,
                "opengl_is_preferred_not_required": True,
                "fallback_is_product_path": True,
            },
        }

    def paint_document_new(
        self,
        *,
        width: int = 1920,
        height: int = 1080,
        background: str = "#FFFFFF",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._replace_canvas_document(int(width or 1920), int(height or 1080), str(background or "#FFFFFF"))
        return dialog.painter_action_state()

    def paint_document_save(self, *, path: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(path or getattr(dialog, "_painter_document_path", "") or "")
        if not target:
            raise ValueError("paint.document.save requires path for an unsaved document")
        return dialog.save_document_to_path(target)

    def paint_document_open(self, *, path: str = "") -> dict[str, Any]:
        if not str(path or "").strip():
            raise ValueError("paint.document.open requires path")
        dialog = self._paint_dialog_owner()
        return dialog.open_document_from_path(path)

    def _paint_ui_commit(self, dialog, label: str, document: dict[str, Any]) -> dict[str, Any]:
        dialog._painter_ui_document = document
        dialog._painter_document_dirty = True
        refresh = getattr(dialog, "_refresh_painter_ui_overlay", None)
        if callable(refresh):
            refresh()
        return dialog.painter_action_state()

    def paint_ui_document_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import inspect_ui_document

        return inspect_ui_document(getattr(dialog, "_painter_ui_document", None))

    def paint_ui_template_catalog_inspect(self) -> dict[str, Any]:
        from app.painter_ui_templates import inspect_ui_template_catalog

        return inspect_ui_template_catalog()

    def paint_ui_template_apply(self, *, template_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_templates import instantiate_ui_template

        document, report = instantiate_ui_template(str(template_id))
        dialog._push_undo_state("Apply UI template")
        self._paint_ui_commit(dialog, "Apply UI template", document)
        return {
            **dialog.painter_action_state(),
            "template": report,
        }

    def paint_ui_template_store_inspect(self, *, store_root: str = "") -> dict[str, Any]:
        from app.painter_ui_template_store import inspect_ui_template_store

        return inspect_ui_template_store(store_root=store_root or None)

    def paint_ui_template_package_export(
        self,
        *,
        path: str,
        template_id: str,
        name: str,
        category: str = "User",
        description: str = "",
        tags: list[str] | None = None,
        version: int = 1,
        author: str = "",
        license_id: str = "User-Owned",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_template_store import export_ui_template_package

        return export_ui_template_package(
            dialog._painter_ui_document,
            path,
            template_id=template_id,
            name=name,
            category=category,
            description=description,
            tags=tags,
            version=version,
            author=author,
            license_id=license_id,
        )

    def paint_ui_template_package_install(
        self,
        *,
        path: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_template_store import install_ui_template_package

        return install_ui_template_package(path, store_root=store_root or None)

    def paint_ui_template_user_save(
        self,
        *,
        template_id: str,
        name: str,
        store_root: str = "",
        category: str = "User",
        description: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_template_store import save_user_ui_template

        return save_user_ui_template(
            dialog._painter_ui_document,
            template_id=template_id,
            name=name,
            store_root=store_root or None,
            category=category,
            description=description,
            tags=tags,
        )

    def paint_ui_template_favorite_set(
        self,
        *,
        template_id: str,
        favorite: bool,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_template_store import set_ui_template_favorite

        return set_ui_template_favorite(
            template_id,
            favorite,
            store_root=store_root or None,
        )

    def paint_ui_template_stored_apply(
        self,
        *,
        template_id: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_template_store import instantiate_stored_ui_template

        document, report = instantiate_stored_ui_template(
            template_id,
            store_root=store_root or None,
        )
        dialog._push_undo_state("Apply stored UI template")
        self._paint_ui_commit(dialog, "Apply stored UI template", document)
        return {**dialog.painter_action_state(), "template": report}

    def paint_ui_template_update_inspect(
        self,
        *,
        candidate_path: str,
        current_manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.painter_ui_template_store import compare_ui_template_update

        return compare_ui_template_update(
            current_manifest or {},
            candidate_path,
        )

    def paint_ui_review_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import inspect_ui_review

        return inspect_ui_review(dialog._painter_ui_document)

    def paint_ui_review_comment_add(
        self,
        *,
        text: str,
        object_id: str = "",
        artboard_id: str = "",
        author: str = "",
        x: float = 0.5,
        y: float = 0.5,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import add_ui_review_comment

        document, comment = add_ui_review_comment(
            dialog._painter_ui_document,
            text=text,
            object_id=object_id,
            artboard_id=artboard_id,
            author=author,
            x=x,
            y=y,
        )
        dialog._push_undo_state("Add UI review comment")
        self._paint_ui_commit(dialog, "Add UI review comment", document)
        return {**dialog.painter_action_state(), "comment": comment}

    def paint_ui_review_comment_update(
        self,
        *,
        comment_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import update_ui_review_comment

        document, comment = update_ui_review_comment(
            dialog._painter_ui_document,
            comment_id,
            changes,
        )
        dialog._push_undo_state("Update UI review comment")
        self._paint_ui_commit(dialog, "Update UI review comment", document)
        return {**dialog.painter_action_state(), "comment": comment}

    def paint_ui_review_comment_remove(self, *, comment_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import remove_ui_review_comment

        document = remove_ui_review_comment(
            dialog._painter_ui_document,
            comment_id,
        )
        dialog._push_undo_state("Remove UI review comment")
        return self._paint_ui_commit(dialog, "Remove UI review comment", document)

    def paint_ui_review_checkpoint_create(
        self,
        *,
        name: str,
        author: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import create_ui_review_checkpoint

        document, checkpoint = create_ui_review_checkpoint(
            dialog._painter_ui_document,
            name=name,
            author=author,
        )
        dialog._push_undo_state("Create UI review checkpoint")
        self._paint_ui_commit(dialog, "Create UI review checkpoint", document)
        return {**dialog.painter_action_state(), "checkpoint": checkpoint}

    def paint_ui_review_checkpoint_diff(self, *, checkpoint_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import diff_ui_checkpoint

        return diff_ui_checkpoint(dialog._painter_ui_document, checkpoint_id)

    def paint_ui_review_export(self, *, output_dir: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import export_ui_review_package

        return export_ui_review_package(
            dialog._painter_ui_document,
            output_dir,
        )

    def paint_ui_developer_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_review import developer_inspect_ui_document

        return developer_inspect_ui_document(dialog._painter_ui_document)

    def paint_ui_prototype_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype import inspect_ui_prototype

        return inspect_ui_prototype(dialog._painter_ui_document)

    def paint_ui_prototype_trigger(
        self,
        *,
        source_object_id: str,
        trigger: str,
        state: dict[str, Any] | None = None,
        key: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype import execute_ui_prototype_trigger

        return execute_ui_prototype_trigger(
            dialog._painter_ui_document,
            state,
            source_object_id=source_object_id,
            trigger=trigger,
            key=key,
        )

    def paint_ui_prototype_export(self, *, output_dir: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype import export_ui_prototype

        return export_ui_prototype(dialog._painter_ui_document, output_dir)

    def paint_ui_assets_export(
        self,
        *,
        output_dir: str,
        formats: list[str] | None = None,
        densities: list[float] | None = None,
        create_atlas: bool = False,
        object_ids: list[str] | None = None,
        trim_transparent: bool = False,
        padding: int = 0,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_asset_export import export_ui_assets

        return export_ui_assets(
            dialog._painter_ui_document,
            output_dir,
            formats=formats,
            densities=densities,
            create_atlas=create_atlas,
            object_ids=object_ids,
            trim_transparent=trim_transparent,
            padding=padding,
        )

    def paint_ui_umg_preflight(self, *, artboard_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_umg_adapter import preflight_painter_umg

        return preflight_painter_umg(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
        )

    def paint_ui_umg_package(
        self,
        *,
        output_dir: str,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_umg_adapter import package_painter_umg

        return package_painter_umg(
            dialog._painter_ui_document,
            output_dir,
            artboard_id=artboard_id,
        )

    def paint_ui_umg_generate(
        self,
        *,
        project_path: str,
        output_dir: str,
        artboard_id: str = "",
        destination_root: str = "/Game/TigerStudio/Generated",
        timeout_seconds: int = 300,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_umg_adapter import generate_painter_umg

        return generate_painter_umg(
            dialog._painter_ui_document,
            project_path=project_path,
            output_dir=output_dir,
            artboard_id=artboard_id,
            destination_root=destination_root,
            timeout_seconds=timeout_seconds,
        )

    def paint_ui_ai_plan(self, *, prompt: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ai_design import plan_ui_co_design

        return plan_ui_co_design(dialog._painter_ui_document, prompt=prompt)

    def paint_ui_ai_apply(
        self,
        *,
        plan: dict[str, Any],
        selected_operation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ai_design import apply_ui_co_design

        document, report = apply_ui_co_design(
            dialog._painter_ui_document,
            plan,
            selected_operation_ids=selected_operation_ids,
        )
        dialog._push_undo_state("Apply AI UI design plan")
        self._paint_ui_commit(dialog, "Apply AI UI design plan", document)
        return {**dialog.painter_action_state(), "ai_apply": report}

    def paint_ui_ai_audit(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ai_design import audit_ui_design

        return audit_ui_design(dialog._painter_ui_document)

    def paint_ui_component_library_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_component_library import inspect_ui_component_library

        return inspect_ui_component_library(
            getattr(dialog, "_painter_ui_document", None)
        )

    def paint_ui_token_library_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_token_library import inspect_ui_token_library

        return inspect_ui_token_library(
            getattr(dialog, "_painter_ui_document", None)
        )

    def paint_ui_token_library_export(self, *, path: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_token_io import export_ui_token_library

        if not str(path or "").strip():
            raise ValueError("paint.ui.token.library.export requires path")
        return export_ui_token_library(dialog._painter_ui_document, path)

    def paint_ui_token_library_import(
        self,
        *,
        path: str,
        conflict_policy: str = "update",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_token_io import import_ui_token_library

        if not str(path or "").strip():
            raise ValueError("paint.ui.token.library.import requires path")
        document, report = import_ui_token_library(
            dialog._painter_ui_document,
            path,
            conflict_policy=conflict_policy,
        )
        dialog._push_undo_state("Import UI tokens")
        self._paint_ui_commit(dialog, "Import UI tokens", document)
        return {
            **dialog.painter_action_state(),
            "token_import": report,
        }

    def paint_ui_workspace_set(self, *, mode: str = "ui_design") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        selected = dialog._set_canvas_workspace_mode(str(mode or "ui_design"))
        state = dialog.painter_action_state()
        state["workspace"]["mode"] = selected
        return state

    def paint_ui_inspector_presentation(
        self,
        *,
        mode: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        value = str(mode or "").strip().casefold()
        if value not in {"auto_hide", "pinned", "floating"}:
            raise ValueError(
                "paint.ui.inspector.presentation mode must be "
                "auto_hide, pinned, or floating"
            )
        dialog._set_canvas_workspace_mode("ui_design")
        if value == "floating":
            dialog._paint_ui_inspector.set_auto_hide(False)
            dialog._detach_painter_ui_inspector()
        else:
            if bool(
                getattr(dialog, "_painter_ui_inspector_detached", False)
            ):
                dialog._dock_painter_ui_inspector()
            dialog._paint_ui_inspector.set_auto_hide(
                value == "auto_hide"
            )
        state = dialog.painter_action_state()
        state["inspector_presentation"] = {
            "mode": value,
            "auto_hide": dialog._paint_ui_inspector.is_auto_hide(),
            "detached": bool(
                getattr(dialog, "_painter_ui_inspector_detached", False)
            ),
        }
        return state

    def paint_ui_view_fit(self, *, mode: str = "all") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        view = dialog._fit_painter_ui_view(str(mode or "all"))
        state = dialog.painter_action_state()
        state["ui_view"] = view
        return state

    def paint_ui_view_focus(
        self,
        *,
        target: str = "selection",
        object_id: str = "",
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        view = dialog._focus_painter_ui_view(
            target=str(target or "selection"),
            object_id=str(object_id or ""),
            artboard_id=str(artboard_id or ""),
        )
        state = dialog.painter_action_state()
        state["ui_view"] = view
        return state

    def paint_ui_view_zoom(
        self,
        *,
        percent: float,
        anchor_x: float | None = None,
        anchor_y: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        view = dialog._set_painter_ui_zoom(
            float(percent),
            anchor_x=anchor_x,
            anchor_y=anchor_y,
        )
        state = dialog.painter_action_state()
        state["ui_view"] = view
        return state

    def paint_ui_view_pan(
        self,
        *,
        dx: float = 0.0,
        dy: float = 0.0,
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        view = dialog._pan_painter_ui_view(
            dx=float(dx or 0.0),
            dy=float(dy or 0.0),
            x=x,
            y=y,
        )
        state = dialog.painter_action_state()
        state["ui_view"] = view
        return state

    def paint_ui_layout_diagnostics(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_diagnostics import diagnose_ui_layout

        return diagnose_ui_layout(dialog._painter_ui_document)

    def paint_ui_responsive_override_set(
        self,
        *,
        object_id: str,
        breakpoint: str = "",
        orientation: str = "",
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_responsive import (
            responsive_context,
            set_ui_responsive_override,
        )

        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == str(object_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Painter UI object not found: {object_id}")
        artboard = next(
            item
            for item in dialog._painter_ui_document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        current_breakpoint, current_orientation = responsive_context(artboard)
        overrides = set_ui_responsive_override(
            row,
            breakpoint=breakpoint or current_breakpoint,
            orientation=orientation or current_orientation,
            changes=changes,
        )
        return self.paint_ui_object_update(
            object_id=str(object_id),
            changes={"responsive_overrides": overrides},
        )

    def paint_ui_responsive_override_remove(
        self,
        *,
        object_id: str,
        breakpoint: str = "",
        orientation: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_responsive import (
            remove_ui_responsive_override,
            responsive_context,
        )

        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == str(object_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Painter UI object not found: {object_id}")
        artboard = next(
            item
            for item in dialog._painter_ui_document["artboards"]
            if item["id"] == row["artboard_id"]
        )
        current_breakpoint, current_orientation = responsive_context(artboard)
        overrides = remove_ui_responsive_override(
            row,
            breakpoint=breakpoint or current_breakpoint,
            orientation=orientation or current_orientation,
        )
        return self.paint_ui_object_update(
            object_id=str(object_id),
            changes={"responsive_overrides": overrides},
        )

    def paint_ui_theme_set(
        self,
        *,
        theme: str,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_themes import normalize_ui_theme

        selected_artboard_id = str(
            artboard_id or dialog._painter_ui_document["active_artboard_id"]
        )
        return self.paint_ui_artboard_update(
            artboard_id=selected_artboard_id,
            changes={"theme": normalize_ui_theme(theme)},
        )

    def paint_ui_theme_inspect(self, *, artboard_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_themes import inspect_ui_theme

        return inspect_ui_theme(
            dialog._painter_ui_document,
            artboard_id=str(artboard_id or ""),
        )

    def paint_ui_token_theme_set(
        self,
        *,
        token_id: str,
        theme: str,
        value: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_themes import set_ui_token_theme_value

        token = next(
            (
                row
                for row in dialog._painter_ui_document["tokens"]
                if row["id"] == str(token_id)
            ),
            None,
        )
        if token is None:
            raise ValueError(f"Painter UI token not found: {token_id}")
        return self.paint_ui_token_update(
            token_id=str(token_id),
            changes={
                "theme_values": set_ui_token_theme_value(
                    token,
                    theme=theme,
                    value=value,
                )
            },
        )

    def paint_ui_token_theme_remove(
        self,
        *,
        token_id: str,
        theme: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_themes import remove_ui_token_theme_value

        token = next(
            (
                row
                for row in dialog._painter_ui_document["tokens"]
                if row["id"] == str(token_id)
            ),
            None,
        )
        if token is None:
            raise ValueError(f"Painter UI token not found: {token_id}")
        return self.paint_ui_token_update(
            token_id=str(token_id),
            changes={
                "theme_values": remove_ui_token_theme_value(
                    token,
                    theme=theme,
                )
            },
        )

    def paint_ui_artboard_add(
        self,
        *,
        name: str = "",
        width: int = 1920,
        height: int = 1080,
        breakpoint: str = "custom",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_artboard

        document, _row = add_ui_artboard(
            dialog._painter_ui_document,
            name=name,
            width=width,
            height=height,
            breakpoint=breakpoint,
        )
        dialog._push_undo_state("Add UI artboard")
        return self._paint_ui_commit(dialog, "Add UI artboard", document)

    def paint_ui_artboard_update(
        self,
        *,
        artboard_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_artboard

        document, _row = update_ui_artboard(
            dialog._painter_ui_document,
            artboard_id,
            changes,
        )
        dialog._push_undo_state("Update UI artboard")
        return self._paint_ui_commit(dialog, "Update UI artboard", document)

    def paint_ui_artboard_layout_set(
        self,
        *,
        artboard_id: str,
        layout_grid: dict[str, Any] | None = None,
        safe_area: dict[str, Any] | None = None,
        safe_area_visible: bool | None = None,
        guides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        row = next(
            (
                item
                for item in dialog._painter_ui_document["artboards"]
                if item["id"] == str(artboard_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Painter UI artboard not found: {artboard_id}")
        changes: dict[str, Any] = {}
        if layout_grid is not None:
            changes["layout_grid"] = dict(layout_grid)
        if safe_area is not None:
            changes["safe_area"] = dict(safe_area)
        if safe_area_visible is not None:
            changes["safe_area_visible"] = bool(safe_area_visible)
        if guides is not None:
            changes["guides"] = dict(guides)
        return self.paint_ui_artboard_update(
            artboard_id=str(artboard_id),
            changes=changes,
        )

    def paint_ui_guide_create(
        self,
        *,
        orientation: str,
        position: float,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import add_ui_guide

        document = add_ui_guide(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            orientation=orientation,
            position=position,
        )
        dialog._push_undo_state("Create UI guide")
        return self._paint_ui_commit(dialog, "Create UI guide", document)

    def paint_ui_guide_remove(
        self,
        *,
        orientation: str,
        position: float,
        artboard_id: str = "",
        tolerance: float = 0.5,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import remove_ui_guide

        document = remove_ui_guide(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            orientation=orientation,
            position=position,
            tolerance=tolerance,
        )
        dialog._push_undo_state("Remove UI guide")
        return self._paint_ui_commit(dialog, "Remove UI guide", document)

    def paint_ui_guide_update(
        self,
        *,
        orientation: str,
        position: float,
        next_position: float,
        artboard_id: str = "",
        tolerance: float = 0.5,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import update_ui_guide

        document = update_ui_guide(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            orientation=orientation,
            position=position,
            next_position=next_position,
            tolerance=tolerance,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Move UI guide")
        return self._paint_ui_commit(dialog, "Move UI guide", document)

    def paint_ui_guide_clear(
        self,
        *,
        artboard_id: str = "",
        orientation: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import clear_ui_guides

        document = clear_ui_guides(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            orientation=orientation,
        )
        dialog._push_undo_state("Clear UI guides")
        return self._paint_ui_commit(dialog, "Clear UI guides", document)

    def paint_ui_ruler_visibility_set(
        self,
        *,
        visible: bool,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        overlay = getattr(dialog, "_painter_ui_overlay", None)
        if overlay is None:
            raise ValueError("Painter UI canvas is unavailable")
        overlay.set_rulers_visible(bool(visible))
        return dialog.painter_action_state()

    def paint_ui_guide_visibility_set(
        self,
        *,
        visible: bool,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import set_ui_guides_visibility

        document = set_ui_guides_visibility(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            visible=visible,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Set UI guide visibility")
        return self._paint_ui_commit(
            dialog,
            "Set UI guide visibility",
            document,
        )

    def paint_ui_guide_lock_set(
        self,
        *,
        locked: bool,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import set_ui_guides_locked

        document = set_ui_guides_locked(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            locked=locked,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Set UI guide lock")
        return self._paint_ui_commit(dialog, "Set UI guide lock", document)

    def paint_ui_ruler_origin_set(
        self,
        *,
        x: float,
        y: float,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import set_ui_ruler_origin

        document = set_ui_ruler_origin(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            x=x,
            y=y,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Set UI ruler origin")
        return self._paint_ui_commit(dialog, "Set UI ruler origin", document)

    def paint_ui_ruler_origin_reset(
        self,
        *,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_guides import reset_ui_ruler_origin

        document = reset_ui_ruler_origin(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Reset UI ruler origin")
        return self._paint_ui_commit(
            dialog,
            "Reset UI ruler origin",
            document,
        )

    def paint_ui_artboard_activate(self, *, artboard_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import set_active_ui_artboard

        document = set_active_ui_artboard(
            dialog._painter_ui_document,
            artboard_id,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Activate UI artboard")
        return self._paint_ui_commit(dialog, "Activate UI artboard", document)

    def paint_ui_artboard_remove(self, *, artboard_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_artboard

        document, _result = remove_ui_artboard(
            dialog._painter_ui_document,
            artboard_id,
        )
        dialog._push_undo_state("Remove UI artboard")
        return self._paint_ui_commit(dialog, "Remove UI artboard", document)

    def paint_ui_object_add(
        self,
        *,
        kind: str = "rectangle",
        name: str = "",
        artboard_id: str = "",
        parent_id: str = "",
        x: float = 0.0,
        y: float = 0.0,
        width: float = 160.0,
        height: float = 64.0,
        style: dict[str, Any] | None = None,
        content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_object

        document, _row = add_ui_object(
            dialog._painter_ui_document,
            kind=kind,
            name=name,
            artboard_id=artboard_id,
            parent_id=parent_id,
            x=x,
            y=y,
            width=width,
            height=height,
            style=style,
            content=content,
        )
        dialog._push_undo_state("Add UI object")
        return self._paint_ui_commit(dialog, "Add UI object", document)

    def paint_ui_object_update(
        self,
        *,
        object_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_object

        document, _row = update_ui_object(
            dialog._painter_ui_document,
            object_id,
            changes,
        )
        dialog._push_undo_state("Update UI object")
        return self._paint_ui_commit(dialog, "Update UI object", document)

    def paint_ui_appearance_inspect(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import inspect_ui_appearance

        return inspect_ui_appearance(
            dialog._painter_ui_document,
            str(object_id),
        )

    def paint_ui_appearance_gradient_set(
        self,
        *,
        object_id: str,
        gradient: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import set_ui_fill_gradient

        document, _row = set_ui_fill_gradient(
            dialog._painter_ui_document,
            str(object_id),
            dict(gradient or {}),
        )
        dialog._push_undo_state("Set UI fill gradient")
        return self._paint_ui_commit(dialog, "Set UI fill gradient", document)

    def paint_ui_appearance_gradient_remove(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import remove_ui_fill_gradient

        document, _row = remove_ui_fill_gradient(
            dialog._painter_ui_document,
            str(object_id),
        )
        dialog._push_undo_state("Remove UI fill gradient")
        return self._paint_ui_commit(
            dialog,
            "Remove UI fill gradient",
            document,
        )

    def paint_ui_appearance_effect_add(
        self,
        *,
        object_id: str,
        effect: dict[str, Any],
        index: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import add_ui_effect

        document, _row = add_ui_effect(
            dialog._painter_ui_document,
            str(object_id),
            dict(effect or {}),
            index=index,
        )
        dialog._push_undo_state("Add UI appearance effect")
        return self._paint_ui_commit(
            dialog,
            "Add UI appearance effect",
            document,
        )

    def paint_ui_appearance_effect_update(
        self,
        *,
        object_id: str,
        index: int,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import update_ui_effect

        document, _row = update_ui_effect(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
            dict(changes or {}),
        )
        dialog._push_undo_state("Update UI appearance effect")
        return self._paint_ui_commit(
            dialog,
            "Update UI appearance effect",
            document,
        )

    def paint_ui_appearance_effect_remove(
        self,
        *,
        object_id: str,
        index: int,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import remove_ui_effect

        document, _row = remove_ui_effect(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
        )
        dialog._push_undo_state("Remove UI appearance effect")
        return self._paint_ui_commit(
            dialog,
            "Remove UI appearance effect",
            document,
        )

    def paint_ui_appearance_effect_reorder(
        self,
        *,
        object_id: str,
        index: int,
        target_index: int,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import reorder_ui_effect

        document, _effects = reorder_ui_effect(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
            int(target_index),
        )
        dialog._push_undo_state("Reorder UI appearance effects")
        return self._paint_ui_commit(
            dialog,
            "Reorder UI appearance effects",
            document,
        )

    def paint_ui_appearance_blur_add(
        self,
        *,
        object_id: str,
        blur_type: str,
        radius: float = 8.0,
        index: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import add_ui_blur

        document, _row = add_ui_blur(
            dialog._painter_ui_document,
            str(object_id),
            str(blur_type),
            float(radius),
            index=index,
        )
        dialog._push_undo_state("Add UI blur")
        return self._paint_ui_commit(dialog, "Add UI blur", document)

    def paint_ui_appearance_blur_update(
        self,
        *,
        object_id: str,
        index: int,
        radius: float,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import update_ui_blur

        document, _row = update_ui_blur(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
            float(radius),
        )
        dialog._push_undo_state("Update UI blur")
        return self._paint_ui_commit(dialog, "Update UI blur", document)

    def paint_ui_appearance_blur_remove(
        self,
        *,
        object_id: str,
        index: int,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import remove_ui_blur

        document, _row = remove_ui_blur(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
        )
        dialog._push_undo_state("Remove UI blur")
        return self._paint_ui_commit(dialog, "Remove UI blur", document)

    def paint_ui_appearance_blur_reorder(
        self,
        *,
        object_id: str,
        index: int,
        target_index: int,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_appearance import reorder_ui_blur

        document, _effects = reorder_ui_blur(
            dialog._painter_ui_document,
            str(object_id),
            int(index),
            int(target_index),
        )
        dialog._push_undo_state("Reorder UI blur")
        return self._paint_ui_commit(dialog, "Reorder UI blur", document)

    def paint_ui_clip_inspect(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_clipping import inspect_ui_clip

        return inspect_ui_clip(
            dialog._painter_ui_document,
            str(object_id),
        )

    def paint_ui_clip_set(
        self,
        *,
        object_id: str,
        clip_content: bool,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_clipping import set_ui_clip

        document, _row = set_ui_clip(
            dialog._painter_ui_document,
            str(object_id),
            bool(clip_content),
        )
        dialog._push_undo_state("Set frame clipping")
        return self._paint_ui_commit(
            dialog,
            "Set frame clipping",
            document,
        )

    def paint_ui_layout_set(
        self,
        *,
        object_id: str,
        mode: str,
        padding: dict[str, Any] | None = None,
        gap: float | None = None,
        cross_gap: float | None = None,
        main_alignment: str = "",
        cross_alignment: str = "",
        wrap: bool | None = None,
        width_sizing: str = "",
        height_sizing: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_auto_layout import normalize_ui_auto_layout

        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == str(object_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Painter UI object not found: {object_id}")
        existing = normalize_ui_auto_layout(row.get("layout"))
        layout = normalize_ui_auto_layout(
            {
                **existing,
                "mode": mode,
                "padding": (
                    dict(padding) if padding is not None else existing["padding"]
                ),
                "gap": existing["gap"] if gap is None else gap,
                "cross_gap": (
                    existing["cross_gap"] if cross_gap is None else cross_gap
                ),
                "main_alignment": (
                    main_alignment or existing["main_alignment"]
                ),
                "cross_alignment": (
                    cross_alignment or existing["cross_alignment"]
                ),
                "wrap": existing["wrap"] if wrap is None else bool(wrap),
                "width_sizing": width_sizing or existing["width_sizing"],
                "height_sizing": height_sizing or existing["height_sizing"],
            }
        )
        return self.paint_ui_object_update(
            object_id=str(object_id),
            changes={"layout": layout},
        )

    def paint_ui_object_remove(self, *, object_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_object

        document, _result = remove_ui_object(
            dialog._painter_ui_document,
            object_id,
        )
        dialog._push_undo_state("Remove UI object")
        return self._paint_ui_commit(dialog, "Remove UI object", document)

    def paint_ui_selection_set(
        self,
        *,
        object_ids: list[str] | None = None,
        primary_object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_painter_ui_selection(
            list(object_ids or []),
            str(primary_object_id or ""),
        )
        return dialog.painter_action_state()

    def paint_ui_selection_parent(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        report = dialog._select_parent_painter_ui_object(
            str(object_id or "")
        )
        state = dialog.painter_action_state()
        state["selection_navigation"] = report
        return state

    def paint_ui_selection_deep_select(
        self,
        *,
        object_id: str = "",
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        if (x is None) != (y is None):
            raise ValueError(
                "paint.ui.selection.deep_select requires both x and y"
            )
        dialog = self._paint_dialog_owner()
        report = dialog._deep_select_painter_ui_object(
            str(object_id or ""),
            x=x,
            y=y,
        )
        state = dialog.painter_action_state()
        state["selection_navigation"] = report
        return state

    def paint_ui_selection_scope_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        state = dialog.painter_action_state()
        state["selection_scope"] = (
            dialog._painter_ui_edit_scope_state()
        )
        return state

    def paint_ui_selection_scope_enter(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        report = dialog._enter_painter_ui_edit_scope(
            str(object_id or "")
        )
        state = dialog.painter_action_state()
        state["selection_scope"] = report
        return state

    def paint_ui_selection_scope_exit(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        report = dialog._exit_painter_ui_edit_scope()
        state = dialog.painter_action_state()
        state["selection_scope"] = report
        return state

    def paint_ui_object_arrange(self, *, command: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        selected = str(
            (
                getattr(dialog, "_painter_ui_document", {}).get("selection")
                or {}
            ).get("object_id")
            or ""
        )
        if not selected:
            raise ValueError("paint.ui.object.arrange requires a UI selection")
        dialog._align_painter_ui_object(selected, str(command or ""))
        return dialog.painter_action_state()

    def paint_ui_object_group(
        self,
        *,
        object_ids: list[str],
        name: str = "Group",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import group_ui_objects

        document, _group = group_ui_objects(
            dialog._painter_ui_document,
            list(object_ids or []),
            name=str(name or "Group"),
        )
        dialog._push_undo_state("Group UI objects")
        return self._paint_ui_commit(dialog, "Group UI objects", document)

    def paint_ui_object_ungroup(self, *, object_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import ungroup_ui_object

        document, _result = ungroup_ui_object(
            dialog._painter_ui_document,
            str(object_id or ""),
        )
        dialog._push_undo_state("Ungroup UI objects")
        return self._paint_ui_commit(dialog, "Ungroup UI objects", document)

    def paint_ui_object_reorder(
        self,
        *,
        object_ids: list[str],
        command: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import reorder_ui_objects

        document = reorder_ui_objects(
            dialog._painter_ui_document,
            list(object_ids or []),
            str(command or ""),
        )
        dialog._push_undo_state("Reorder UI objects")
        return self._paint_ui_commit(dialog, "Reorder UI objects", document)

    def paint_ui_object_reparent(
        self,
        *,
        object_ids: list[str],
        target_parent_id: str = "",
        anchor_id: str = "",
        placement: str = "inside",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import move_ui_objects_in_hierarchy

        document = move_ui_objects_in_hierarchy(
            dialog._painter_ui_document,
            list(object_ids or []),
            target_parent_id=str(target_parent_id or ""),
            anchor_id=str(anchor_id or ""),
            placement=str(placement or "inside"),
        )
        dialog._push_undo_state("Move UI hierarchy")
        return self._paint_ui_commit(dialog, "Move UI hierarchy", document)

    def paint_ui_component_add(
        self,
        *,
        name: str = "",
        root_object_id: str = "",
        base_component_id: str = "",
        description: str = "",
        property_definitions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_component

        document, _row = add_ui_component(
            dialog._painter_ui_document,
            name=name,
            root_object_id=root_object_id,
            base_component_id=base_component_id,
            description=description,
            property_definitions=property_definitions,
        )
        dialog._push_undo_state("Add UI component")
        return self._paint_ui_commit(dialog, "Add UI component", document)

    def paint_ui_component_create(
        self,
        *,
        root_object_id: str = "",
        name: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import convert_ui_object_to_component

        selected_id = str(
            root_object_id
            or dialog._painter_ui_document["selection"]["object_id"]
        )
        document, _component = convert_ui_object_to_component(
            dialog._painter_ui_document,
            root_object_id=selected_id,
            name=name,
            description=description,
        )
        dialog._push_undo_state("Create UI component")
        return self._paint_ui_commit(dialog, "Create UI component", document)

    def paint_ui_component_instantiate(
        self,
        *,
        component_id: str,
        artboard_id: str = "",
        x: float | None = None,
        y: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import instantiate_ui_component

        document, _result = instantiate_ui_component(
            dialog._painter_ui_document,
            component_id=str(component_id),
            artboard_id=str(artboard_id or ""),
            x=x,
            y=y,
        )
        dialog._push_undo_state("Instantiate UI component")
        return self._paint_ui_commit(dialog, "Instantiate UI component", document)

    def paint_ui_component_sync(self, *, component_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import sync_ui_component_instances

        document = sync_ui_component_instances(
            dialog._painter_ui_document,
            str(component_id),
        )
        document["revision"] += 1
        dialog._push_undo_state("Sync UI component instances")
        return self._paint_ui_commit(
            dialog,
            "Sync UI component instances",
            document,
        )

    def paint_ui_component_property_define(
        self,
        *,
        component_id: str,
        property_name: str,
        definition: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import define_ui_component_property

        document, _property = define_ui_component_property(
            dialog._painter_ui_document,
            component_id=str(component_id),
            property_name=str(property_name),
            definition=dict(definition or {}),
        )
        dialog._push_undo_state("Define UI component property")
        return self._paint_ui_commit(
            dialog,
            "Define UI component property",
            document,
        )

    def paint_ui_component_property_bind(
        self,
        *,
        component_id: str,
        source_object_id: str,
        property_name: str,
        target_path: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import bind_ui_component_property

        document, _bindings = bind_ui_component_property(
            dialog._painter_ui_document,
            component_id=str(component_id),
            source_object_id=str(source_object_id),
            property_name=str(property_name),
            target_path=str(target_path),
        )
        dialog._push_undo_state("Bind UI component property")
        return self._paint_ui_commit(
            dialog,
            "Bind UI component property",
            document,
        )

    def paint_ui_component_state_override_set(
        self,
        *,
        component_id: str,
        state: str,
        source_object_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import set_ui_component_state_override

        document, _override = set_ui_component_state_override(
            dialog._painter_ui_document,
            component_id=str(component_id),
            state=str(state),
            source_object_id=str(source_object_id),
            changes=dict(changes or {}),
        )
        dialog._push_undo_state("Set UI component state")
        return self._paint_ui_commit(
            dialog,
            "Set UI component state",
            document,
        )

    def paint_ui_component_instance_property_set(
        self,
        *,
        instance_root_id: str,
        property_name: str,
        value: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import set_ui_instance_component_property

        document, _properties = set_ui_instance_component_property(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            property_name=str(property_name),
            property_value=value,
        )
        dialog._push_undo_state("Set UI component instance property")
        return self._paint_ui_commit(
            dialog,
            "Set UI component instance property",
            document,
        )

    def paint_ui_component_variant_create(
        self,
        *,
        component_id: str,
        name: str = "",
        variant_key: str = "",
        offset_x: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import create_ui_component_variant

        document, _variant = create_ui_component_variant(
            dialog._painter_ui_document,
            component_id=str(component_id),
            name=str(name or ""),
            variant_key=str(variant_key or ""),
            offset_x=offset_x,
        )
        dialog._push_undo_state("Create UI component variant")
        return self._paint_ui_commit(
            dialog,
            "Create UI component variant",
            document,
        )

    def paint_ui_component_instance_variant_set(
        self,
        *,
        instance_root_id: str,
        component_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import switch_ui_component_instance_variant

        document, _result = switch_ui_component_instance_variant(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            target_component_id=str(component_id),
        )
        dialog._push_undo_state("Switch UI component variant")
        return self._paint_ui_commit(
            dialog,
            "Switch UI component variant",
            document,
        )

    def paint_ui_component_instance_detach(
        self,
        *,
        instance_root_id: str,
        create_local_component: bool = False,
        name: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import detach_ui_component_instance

        document, _result = detach_ui_component_instance(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            create_local_component=bool(create_local_component),
            name=str(name or ""),
        )
        label = (
            "Localize UI component instance"
            if create_local_component
            else "Detach UI component instance"
        )
        dialog._push_undo_state(label)
        return self._paint_ui_commit(dialog, label, document)

    def paint_ui_component_update(
        self,
        *,
        component_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_component

        document, _row = update_ui_component(
            dialog._painter_ui_document, component_id, changes
        )
        dialog._push_undo_state("Update UI component")
        return self._paint_ui_commit(dialog, "Update UI component", document)

    def paint_ui_component_remove(
        self,
        *,
        component_id: str,
        detach_references: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_component

        document, _result = remove_ui_component(
            dialog._painter_ui_document,
            component_id,
            detach_references=detach_references,
        )
        dialog._push_undo_state("Remove UI component")
        return self._paint_ui_commit(dialog, "Remove UI component", document)

    def paint_ui_token_add(
        self,
        *,
        name: str = "",
        kind: str = "color",
        value: Any = None,
        theme_values: dict[str, Any] | None = None,
        alias_token_id: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_token

        document, _row = add_ui_token(
            dialog._painter_ui_document,
            name=name,
            kind=kind,
            token_value=value,
            theme_values=theme_values,
            alias_token_id=alias_token_id,
            description=description,
        )
        dialog._push_undo_state("Add UI token")
        return self._paint_ui_commit(dialog, "Add UI token", document)

    def paint_ui_token_update(
        self,
        *,
        token_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_token

        document, _row = update_ui_token(
            dialog._painter_ui_document, token_id, changes
        )
        dialog._push_undo_state("Update UI token")
        return self._paint_ui_commit(dialog, "Update UI token", document)

    def paint_ui_token_remove(
        self,
        *,
        token_id: str,
        detach_references: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_token

        document, _result = remove_ui_token(
            dialog._painter_ui_document,
            token_id,
            detach_references=detach_references,
        )
        dialog._push_undo_state("Remove UI token")
        return self._paint_ui_commit(dialog, "Remove UI token", document)

    def paint_ui_token_bind(
        self,
        *,
        object_id: str,
        path: str,
        token_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_object
        from app.painter_ui_token_library import TOKEN_BINDING_PATHS

        binding_path = str(path or "")
        if binding_path not in TOKEN_BINDING_PATHS:
            raise ValueError(f"Unsupported UI token binding path: {binding_path}")
        if token_id not in {
            row["id"] for row in dialog._painter_ui_document["tokens"]
        }:
            raise ValueError(f"UI token not found: {token_id}")
        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == str(object_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"UI object not found: {object_id}")
        bindings = dict(row["token_bindings"])
        bindings[binding_path] = str(token_id)
        document, _row = update_ui_object(
            dialog._painter_ui_document,
            str(object_id),
            {"token_bindings": bindings},
        )
        dialog._push_undo_state("Bind UI token")
        return self._paint_ui_commit(dialog, "Bind UI token", document)

    def paint_ui_token_unbind(
        self,
        *,
        object_id: str,
        path: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_object

        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == str(object_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"UI object not found: {object_id}")
        bindings = dict(row["token_bindings"])
        bindings.pop(str(path or ""), None)
        document, _row = update_ui_object(
            dialog._painter_ui_document,
            str(object_id),
            {"token_bindings": bindings},
        )
        dialog._push_undo_state("Unbind UI token")
        return self._paint_ui_commit(dialog, "Unbind UI token", document)

    def paint_ui_interaction_add(
        self,
        *,
        name: str = "",
        source_object_id: str = "",
        trigger: str = "click",
        action: str = "navigate",
        target_artboard_id: str = "",
        target_object_id: str = "",
        component_id: str = "",
        motion_clip_id: str = "",
        parameters: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_interaction

        document, _row = add_ui_interaction(
            dialog._painter_ui_document,
            name=name,
            source_object_id=source_object_id,
            trigger=trigger,
            action=action,
            target_artboard_id=target_artboard_id,
            target_object_id=target_object_id,
            component_id=component_id,
            motion_clip_id=motion_clip_id,
            parameters=parameters,
            enabled=enabled,
        )
        dialog._push_undo_state("Add UI interaction")
        return self._paint_ui_commit(dialog, "Add UI interaction", document)

    def paint_ui_interaction_update(
        self,
        *,
        interaction_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_interaction

        document, _row = update_ui_interaction(
            dialog._painter_ui_document, interaction_id, changes
        )
        dialog._push_undo_state("Update UI interaction")
        return self._paint_ui_commit(dialog, "Update UI interaction", document)

    def paint_ui_interaction_remove(
        self,
        *,
        interaction_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_interaction

        document, _result = remove_ui_interaction(
            dialog._painter_ui_document, interaction_id
        )
        dialog._push_undo_state("Remove UI interaction")
        return self._paint_ui_commit(dialog, "Remove UI interaction", document)

    def paint_ui_motion_attach(
        self,
        *,
        object_id: str = "",
        duration_ms: int = 600,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.motion_designer.schema import MotionComposition
        from app.painter_ui_motion_bridge import (
            attach_motion_composition,
            create_or_sync_ui_motion_composition,
            linked_motion_composition_id,
        )

        document = dialog._painter_ui_document
        selected = str(
            object_id
            or ((document.get("selection") or {}).get("object_id"))
            or ""
        )
        if not selected:
            raise ValueError("paint.ui.motion.attach requires a UI object")
        linked_id = linked_motion_composition_id(document, selected)
        if not linked_id:
            linked_id = str(dialog._painter_ui_linked_motion_id(selected) or "")
        existing = getattr(dialog, "_painter_ui_motion_compositions", {}).get(
            linked_id
        )
        if isinstance(existing, dict):
            existing = MotionComposition.from_dict(existing)
        source = (
            (existing.metadata.get("painter_ui_source") or {})
            if isinstance(existing, MotionComposition)
            else {}
        )
        root_object_id = str(source.get("object_id") or selected)
        composition = create_or_sync_ui_motion_composition(
            document,
            root_object_id,
            existing,
            duration_ms=max(1, int(duration_ms or 600)),
        )
        dialog._push_undo_state("Attach UI motion")
        dialog._painter_ui_motion_compositions[composition.id] = composition
        from app.motion_designer.ui_motion_binding import ui_motion_bindings

        binding = next(
            (
                row
                for row in ui_motion_bindings(composition)
                if row.source_object_id == root_object_id
            ),
            None,
        )
        updated = attach_motion_composition(
            document,
            root_object_id,
            composition.id,
            binding_id=binding.id if binding else "",
            composition_revision=composition.revision,
        )
        self._paint_ui_commit(dialog, "Attach UI motion", updated)
        return {
            "attached": True,
            "object_id": selected,
            "root_object_id": root_object_id,
            "composition_id": composition.id,
            "composition": composition.to_dict(),
        }

    def paint_ui_motion_open(self, *, object_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(object_id or "")
        if target:
            from app.painter_ui_document import select_ui_object

            dialog._painter_ui_document = select_ui_object(
                dialog._painter_ui_document,
                target,
            )
            dialog._refresh_painter_ui_overlay()
        return dialog._animate_selected_painter_ui_object()

    def paint_ui_motion_preview(self, *, playing: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        active = dialog._set_painter_ui_motion_preview(bool(playing))
        return {
            "playing": active,
            "composition_id": str(
                getattr(dialog, "_painter_ui_motion_active_id", "") or ""
            ),
            "time_ms": int(
                getattr(dialog, "_painter_ui_motion_time_ms", 0) or 0
            ),
        }

    def paint_ui_motion_inspect(self, *, object_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.motion_designer.schema import MotionComposition
        from app.painter_ui_motion_bridge import linked_motion_composition_id

        document = dialog._painter_ui_document
        selected = str(
            object_id
            or ((document.get("selection") or {}).get("object_id"))
            or ""
        )
        composition_id = linked_motion_composition_id(document, selected)
        if not composition_id and selected:
            composition_id = str(
                dialog._painter_ui_linked_motion_id(selected) or ""
            )
        composition = getattr(
            dialog, "_painter_ui_motion_compositions", {}
        ).get(composition_id)
        if isinstance(composition, dict):
            composition = MotionComposition.from_dict(composition)
        return {
            "object_id": selected,
            "attached": isinstance(composition, MotionComposition),
            "composition_id": composition_id,
            "composition": (
                composition.to_dict()
                if isinstance(composition, MotionComposition)
                else None
            ),
        }

    def paint_ui_motion_delivery_inspect(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_delivery import motion_delivery_report

        document = dialog._painter_ui_document
        selected = str(
            object_id
            or ((document.get("selection") or {}).get("object_id"))
            or ""
        )
        if not selected:
            raise ValueError(
                "paint.ui.motion.delivery.inspect requires a UI object"
            )
        return motion_delivery_report(
            document,
            selected,
            getattr(dialog, "_painter_ui_motion_compositions", {}),
        )

    def paint_ui_motion_binding_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_bridge import (
            inspect_motion_binding_links,
        )

        return inspect_motion_binding_links(
            dialog._painter_ui_document,
            getattr(dialog, "_painter_ui_motion_compositions", {}),
        )

    def paint_ui_motion_binding_migrate(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_bridge import (
            migrate_motion_binding_links,
        )

        document, report = migrate_motion_binding_links(
            dialog._painter_ui_document,
            getattr(dialog, "_painter_ui_motion_compositions", {}),
        )
        if document != dialog._painter_ui_document:
            dialog._push_undo_state("Migrate UI motion bindings")
            self._paint_ui_commit(
                dialog, "Migrate UI motion bindings", document
            )
        return report

    def paint_ui_motion_binding_relink(
        self,
        *,
        object_id: str,
        composition_id: str,
        binding_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_bridge import relink_motion_binding

        document = relink_motion_binding(
            dialog._painter_ui_document,
            object_id,
            composition_id,
            binding_id,
            getattr(dialog, "_painter_ui_motion_compositions", {}),
        )
        dialog._push_undo_state("Relink UI motion")
        self._paint_ui_commit(dialog, "Relink UI motion", document)
        return {
            "relinked": True,
            "object_id": str(object_id),
            "composition_id": str(composition_id),
            "binding_id": str(binding_id),
        }

    def paint_ui_motion_binding_detach(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_bridge import detach_motion_binding

        document, result = detach_motion_binding(
            dialog._painter_ui_document,
            object_id,
        )
        if result["detached"]:
            dialog._push_undo_state("Detach UI motion")
            self._paint_ui_commit(dialog, "Detach UI motion", document)
        return result

    def paint_ui_motion_actor_import(
        self,
        *,
        path: str,
        name: str = "",
        x: float | None = None,
        y: float | None = None,
        width: float = 0.0,
        height: float = 0.0,
        autoplay: bool = True,
        loop: bool = True,
    ) -> dict[str, Any]:
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Motion project not found: {source}")
        from app.motion_designer.project_io import load_motion_project

        dialog = self._paint_dialog_owner()
        dialog._set_canvas_workspace_mode("ui_design")
        composition = load_motion_project(source)
        return dialog._place_painter_ui_motion_actor(
            composition,
            source_path=str(source),
            name=name,
            x=x,
            y=y,
            width=width,
            height=height,
            autoplay=autoplay,
            loop=loop,
        )

    def paint_ui_motion_actor_list(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_motion_actor import (
            motion_actor_composition_id,
            motion_actor_rows,
        )

        rows = motion_actor_rows(dialog._painter_ui_document)
        compositions = getattr(dialog, "_painter_ui_motion_compositions", {})
        return {
            "count": len(rows),
            "actors": [
                {
                    "object_id": row["id"],
                    "name": row["name"],
                    "composition_id": motion_actor_composition_id(row),
                    "composition_available": (
                        motion_actor_composition_id(row) in compositions
                    ),
                    "rect": {
                        key: float(row[key])
                        for key in ("x", "y", "width", "height")
                    },
                    "source_path": str(
                        (row.get("content") or {}).get("source_path") or ""
                    ),
                }
                for row in rows
            ],
        }

    def paint_ui_delivery_profiles(self) -> dict[str, Any]:
        from app.painter_ui_delivery import list_ui_delivery_profiles

        return list_ui_delivery_profiles()

    def paint_ui_delivery_preflight(self, *, target: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_delivery import preflight_ui_delivery

        return preflight_ui_delivery(dialog._painter_ui_document, target)

    def paint_ui_handoff_export(self, *, output_dir: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_delivery import package_design_handoff

        return package_design_handoff(dialog._painter_ui_document, output_dir)

    def paint_document_export_png(
        self,
        *,
        path: str = "",
        include_background: bool = True,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        if not path:
            from datetime import datetime

            from app.paths import default_save_dir

            suffix = "composited" if include_background else "overlay"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(default_save_dir() / f"paint_{suffix}_{stamp}.png")
        dialog = self._paint_dialog_owner()
        return dialog.export_png_to_path(
            path,
            include_background=bool(include_background),
            width=int(width or 0),
            height=int(height or 0),
        )

    def paint_view_zoom(self, *, percent: int = 100) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_zoom_percent(int(percent or 100))
        return dialog.painter_action_state()

    def paint_view_zoom_area(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._handle_canvas_zoom_request(
            "zoom_area",
            float(x),
            float(y),
            float(width),
            float(height),
        )
        return dialog.painter_action_state()

    def paint_view_pan(
        self,
        *,
        x: int | None = None,
        y: int | None = None,
        dx: int = 0,
        dy: int = 0,
        reset: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if reset:
            dialog._reset_canvas_pan()
        elif x is not None or y is not None:
            current = getattr(dialog, "_canvas_pan", None)
            current_x = int(current.x()) if current is not None else 0
            current_y = int(current.y()) if current is not None else 0
            from PySide6.QtCore import QPoint

            dialog._set_canvas_pan(QPoint(current_x if x is None else int(x), current_y if y is None else int(y)))
        else:
            from PySide6.QtCore import QPoint

            dialog._pan_canvas_by(QPoint(int(dx or 0), int(dy or 0)))
        return dialog.painter_action_state()

    def paint_view_grid(
        self,
        *,
        visible: bool | None = None,
        snap: bool | None = None,
        size_px: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_grid_options(visible=visible, snap=snap, size_px=size_px)
        return dialog.painter_action_state()

    def paint_guide_perspective(
        self,
        *,
        enabled: bool | None = None,
        horizon: float | None = None,
        left_x: float | None = None,
        left_y: float | None = None,
        right_x: float | None = None,
        right_y: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_perspective_guide_options(
            enabled=enabled,
            horizon=horizon,
            left_x=left_x,
            left_y=left_y,
            right_x=right_x,
            right_y=right_y,
        )
        return dialog.painter_action_state()

    def paint_guide_symmetry(
        self,
        *,
        enabled: bool | None = None,
        axis: str | None = None,
        position: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_symmetry_guide_options(enabled=enabled, axis=axis, position=position)
        return dialog.painter_action_state()

    def paint_quick_mask_set(self, *, enabled: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_quick_mask_enabled(bool(enabled))
        return dialog.painter_action_state()

    def paint_layer_add(
        self,
        *,
        name: str = "",
        layer_type: str = "standard",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._new_paint_layer(
            str(name or "") or None,
            layer_type=str(layer_type or "standard"),
        )
        return dialog.painter_action_state()

    def paint_layer_set_type(
        self,
        *,
        layer_id: str = "",
        layer_type: str = "standard",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._set_paint_layer_type(layer_id or None, str(layer_type or "standard")):
            raise ValueError("Painter layer type did not change")
        return dialog.painter_action_state()

    def paint_material_settings_set(
        self,
        *,
        layer_id: str = "",
        load: float | None = None,
        thickness: float | None = None,
        wetness: float | None = None,
        gloss: float | None = None,
        roughness: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        values = {
            "load": load,
            "thickness": thickness,
            "wetness": wetness,
            "gloss": gloss,
            "roughness": roughness,
        }
        if not dialog._set_material_settings(values, layer_id=layer_id or None):
            raise ValueError("Material Paint settings require a material layer and a changed value")
        return dialog.painter_action_state()

    def paint_material_preview_set(
        self,
        *,
        enabled: bool | None = None,
        azimuth_deg: float | None = None,
        elevation_deg: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_material_preview(
            enabled=enabled,
            azimuth_deg=azimuth_deg,
            elevation_deg=elevation_deg,
        )
        return dialog.painter_action_state()

    def paint_wet_canvas_settings_set(
        self,
        *,
        layer_id: str = "",
        enabled: bool | None = None,
        mixing: float | None = None,
        diffusion: float | None = None,
        pickup: float | None = None,
        drying_seconds: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        values = {
            "enabled": enabled,
            "mixing": mixing,
            "diffusion": diffusion,
            "pickup": pickup,
            "drying_seconds": drying_seconds,
        }
        if not dialog._set_wet_canvas_settings(values, layer_id=layer_id or None):
            raise ValueError(
                "Wet Canvas settings require a material layer and a changed value"
            )
        return dialog.painter_action_state()

    def paint_wet_canvas_advance(
        self,
        *,
        seconds: float = 0.0,
        layer_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._advance_wet_canvas(
            max(0.0, float(seconds)),
            layer_id=layer_id or None,
        ):
            raise ValueError("Wet Canvas did not advance")
        return dialog.painter_action_state()

    def paint_wet_canvas_dry(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id:
            dialog._select_paint_layer_by_id(layer_id)
        if not dialog._dry_active_wet_canvas():
            raise ValueError("Wet Canvas requires an active material layer")
        return dialog.painter_action_state()

    def paint_layer_select(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._select_paint_layer_by_id(layer_id or None):
            raise ValueError("paint layer not found")
        return dialog.painter_action_state()

    def paint_layer_rename(self, *, layer_id: str = "", name: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._rename_layer_to(layer_id or None, str(name or "")):
            raise ValueError("layer rename did not change a paint layer")
        return dialog.painter_action_state()

    def paint_layer_duplicate(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id:
            dialog._select_paint_layer_by_id(layer_id)
        dialog._duplicate_selected_layer()
        return dialog.painter_action_state()

    def paint_layer_delete(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._delete_layer(layer_id or dialog._current_layer_id())
        return dialog.painter_action_state()

    def paint_layer_set_visible(self, *, layer_id: str = "", visible: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_visible(layer_id or None, bool(visible))
        return dialog.painter_action_state()

    def paint_layer_set_locked(self, *, layer_id: str = "", locked: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_locked(layer_id or None, bool(locked))
        return dialog.painter_action_state()

    def paint_layer_set_opacity(self, *, layer_id: str = "", opacity: int = 100) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_opacity_value(layer_id or None, int(opacity or 0))
        return dialog.painter_action_state()

    def paint_layer_set_blend_mode(self, *, layer_id: str = "", blend_mode: str = "normal") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_blend_mode(layer_id or None, str(blend_mode or "normal"))
        return dialog.painter_action_state()

    def paint_layer_set_color(self, *, layer_id: str = "", color_label: str = "none") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_layer_color_label(layer_id or None, str(color_label or "none"))
        return dialog.painter_action_state()

    def paint_channel_set_visible(self, *, channel: str = "RGB", visible: bool = True) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_channel_visibility(str(channel or "RGB"), bool(visible))
        return dialog.painter_action_state()

    def paint_channel_select(self, *, channel: str = "RGB") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_selected_channel(str(channel or "RGB"))
        return dialog.painter_action_state()

    def paint_channel_copy_image(self, *, channel: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._copy_channel_image(str(channel or getattr(dialog, "_selected_channel", "RGB"))):
            raise ValueError("no Painter channel image available to copy")
        state = dialog.painter_action_state()
        state["channel_clipboard"] = "copied"
        return state

    def paint_channel_paste_image(self, *, channel: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._paste_channel_image(str(channel or getattr(dialog, "_selected_channel", "RGB"))):
            raise ValueError("system clipboard does not contain an image")
        return dialog.painter_action_state()

    def paint_selection_select_all(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._select_all()
        return dialog.painter_action_state()

    def paint_selection_deselect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._deselect()
        return dialog.painter_action_state()

    def paint_selection_invert(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._invert_selection()
        return dialog.painter_action_state()

    def paint_selection_to_path(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._selection_to_path()
        return dialog.painter_action_state()

    def paint_selection_rectangle(
        self,
        *,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 1.0,
        y2: float = 1.0,
        aspect: str = "free",
        mode: str = "new",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Rectangular selection")
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        dialog._set_selection_combine_mode(str(mode or "new"))
        dialog.canvas.select_rectangle(float(x1), float(y1), float(x2), float(y2), shape="rect", aspect=str(aspect or "free"))
        dialog._selected_path_item_id = "selection"
        dialog._update_path_list()
        dialog._set_tool("rect_select")
        return dialog.painter_action_state()

    def paint_selection_ellipse(
        self,
        *,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 1.0,
        y2: float = 1.0,
        aspect: str = "free",
        mode: str = "new",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Elliptical selection")
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        dialog._set_selection_combine_mode(str(mode or "new"))
        dialog.canvas.select_rectangle(float(x1), float(y1), float(x2), float(y2), shape="ellipse", aspect=str(aspect or "free"))
        dialog._selected_path_item_id = "selection"
        dialog._update_path_list()
        dialog._set_tool("ellipse_select")
        return dialog.painter_action_state()

    def paint_selection_set_aspect(self, *, aspect: str = "free") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_selection_aspect_mode(str(aspect or "free"))
        return dialog.painter_action_state()

    def paint_selection_set_mode(self, *, mode: str = "new") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_selection_combine_mode(str(mode or "new"))
        return dialog.painter_action_state()

    def paint_selection_select_by_color(
        self,
        *,
        x: float = 0.5,
        y: float = 0.5,
        tolerance: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._select_by_color_at(float(x), float(y), tolerance=tolerance):
            raise ValueError("Magic Select could not create a color selection")
        return dialog.painter_action_state()

    def paint_crop_to_selection(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._crop_to_selection():
            raise ValueError("crop requires an active Painter selection")
        return dialog.painter_action_state()

    def paint_image_resize(self, *, width: int = 1920, height: int = 1080) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._resize_image_document(int(width or 1920), int(height or 1080))
        return dialog.painter_action_state()

    def paint_canvas_resize(
        self,
        *,
        width: int = 1920,
        height: int = 1080,
        background: str = "transparent",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._resize_canvas_document(int(width or 1920), int(height or 1080), background=str(background or "transparent"))
        return dialog.painter_action_state()

    def paint_canvas_flip(self, *, axis: str = "horizontal") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        value = str(axis or "horizontal").strip().casefold()
        dialog._flip_canvas(horizontal=value in {"horizontal", "x"})
        return dialog.painter_action_state()

    def paint_fill_solid(self, *, color: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document("solid", color1=str(color or "") or None)
        return dialog.painter_action_state()

    def paint_fill_gradient(self, *, color1: str = "", color2: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document(
            "gradient",
            color1=str(color1 or "") or None,
            color2=str(color2 or "") or None,
        )
        return dialog.painter_action_state()

    def paint_fill_pattern(self, *, color1: str = "", color2: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._fill_document(
            "pattern",
            color1=str(color1 or "") or None,
            color2=str(color2 or "") or None,
        )
        return dialog.painter_action_state()

    def paint_mirror_set(self, *, x: bool | None = None, y: bool | None = None) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_mirror_enabled(x=x, y=y)
        return dialog.painter_action_state()

    def paint_layer_mask_from_selection(self, *, layer_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id and not dialog._select_paint_layer_by_id(layer_id):
            raise ValueError("paint layer not found")
        if not dialog._mask_selected_layer_from_selection():
            raise ValueError("layer mask from selection requires an active selection")
        return dialog.painter_action_state()

    def paint_layer_mask_from_path(self, *, layer_id: str = "", path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if layer_id and not dialog._select_paint_layer_by_id(layer_id):
            raise ValueError("paint layer not found")
        if path_id:
            dialog._selected_path_item_id = str(path_id)
        if not dialog._mask_selected_layer_from_path():
            raise ValueError("layer mask from path requires a path with at least 3 points")
        return dialog.painter_action_state()

    def paint_layer_mask_create(
        self,
        *,
        layer_id: str = "",
        mask_type: str = "selection",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._create_layer_mask(str(mask_type or "selection"), layer_id or None):
            raise ValueError("layer mask creation requires valid mask source pixels or points")
        return dialog.painter_action_state()

    def paint_path_to_selection(self, *, path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if path_id:
            dialog._selected_path_item_id = str(path_id)
        dialog._make_selection_from_selected_path()
        return dialog.painter_action_state()

    def paint_path_create(
        self,
        *,
        points: list[Any] | None = None,
        closed: bool = True,
        make_selection: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._create_path_from_points(points or [], closed=bool(closed), make_selection=bool(make_selection)):
            raise ValueError("path requires at least two valid normalized points")
        return dialog.painter_action_state()

    def paint_path_delete(self, *, path_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._delete_path_by_id(path_id or None):
            raise ValueError("paint path not found")
        return dialog.painter_action_state()

    def paint_path_clear(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._clear_path_preview()
        return dialog.painter_action_state()

    def paint_path_commit(self, *, closed: bool = False) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._commit_path(bool(closed))
        return dialog.painter_action_state()

    def paint_clipboard_copy(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._copy_selected_layer()
        return dialog.painter_action_state()

    def paint_clipboard_cut(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._cut_selected_layer()
        return dialog.painter_action_state()

    def paint_clipboard_paste(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._paste_layer_clipboard()
        return dialog.painter_action_state()

    def paint_tool_set(self, *, tool: str = "select") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        tool_name = str(tool or "select").strip().casefold().replace("-", "_")
        aliases = {
            "move": "select",
            "hand": "pan",
            "brush": "pen",
            "pen": "pen",
            "eraser": "eraser",
            "path": "path",
            "rect_select": "rect_select",
            "rectangle": "rect_select",
            "marquee_rect": "rect_select",
            "ellipse_select": "ellipse_select",
            "ellipse": "ellipse_select",
            "marquee_ellipse": "ellipse_select",
            "magic_select": "magic_select",
            "magic_wand": "magic_select",
            "select_color": "magic_select",
            "crop": "crop",
            "pan": "pan",
            "select": "select",
        }
        dialog._set_tool(aliases.get(tool_name, "select"))
        return dialog.painter_action_state()

    def paint_brush_set(
        self,
        *,
        preset: str = "",
        style: str = "",
        width: int | None = None,
        opacity: int | None = None,
        hardness: int | None = None,
        spacing: int | None = None,
        angle: int | None = None,
        roundness: int | None = None,
        flip_x: bool | None = None,
        flip_y: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.drawing import BRUSH_LIBRARY_PRESETS, _normalize_paint_brush_style

        preset_key = str(preset or "").strip().casefold().replace("-", "_").replace(" ", "_")
        if preset_key:
            for row in BRUSH_LIBRARY_PRESETS:
                name_key = str(row.get("name") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                style_key = str(row.get("style") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                if preset_key in {name_key, style_key}:
                    dialog._apply_brush_library_preset(row)
                    break
            else:
                raise ValueError("Painter brush preset not found")

        if style:
            style_id = _normalize_paint_brush_style(str(style))
            dialog._pen_style = style_id
            if hasattr(dialog, "canvas"):
                dialog.canvas.set_pen_style(style_id)
            if hasattr(dialog, "brush_style_combo"):
                index = dialog.brush_style_combo.findData(style_id)
                if index >= 0:
                    dialog.brush_style_combo.setCurrentIndex(index)
        if width is not None:
            value = max(1, min(60, int(width or 1)))
            if hasattr(dialog, "width_slider"):
                dialog.width_slider.setValue(value)
            else:
                dialog._pen_width = float(value)
                if hasattr(dialog, "canvas"):
                    dialog.canvas.set_pen_width(dialog._pen_width)
        if opacity is not None:
            value = max(10, min(100, int(opacity or 100)))
            if hasattr(dialog, "opacity_slider"):
                dialog.opacity_slider.setValue(value)
            else:
                dialog._pen_opacity = int(value * 255 / 100)
                if hasattr(dialog, "canvas"):
                    dialog.canvas.set_pen_opacity(dialog._pen_opacity)
        for key, value in (
            ("hardness", hardness),
            ("spacing", spacing),
            ("angle", angle),
            ("roundness", roundness),
        ):
            if value is not None:
                dialog._set_brush_detail_value(key, int(value))
        if flip_x is not None:
            dialog._set_brush_detail_toggle("flip_x", bool(flip_x))
        if flip_y is not None:
            dialog._set_brush_detail_toggle("flip_y", bool(flip_y))
        dialog._set_tool("pen")
        return dialog.painter_action_state()

    def paint_brush_library_view(
        self,
        *,
        tab: str = "library",
        category: str = "",
        filter: str = "",
        filters: list[str] | None = None,
        search: str = "",
        compact: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_brush_tab("settings" if str(tab).strip().casefold() == "controls" else "presets")
        category_key = str(category or "").strip().casefold()
        category_list = getattr(dialog, "_brush_category_list", None)
        if category_list is not None:
            target_row = 0
            if category_key:
                for row in range(category_list.count()):
                    item = category_list.item(row)
                    item_key = str(
                        item.data(Qt.ItemDataRole.UserRole) or item.text()
                    ).strip().casefold()
                    if item_key == category_key:
                        target_row = row
                        break
                else:
                    raise ValueError("Painter brush category not found")
            category_list.setCurrentRow(target_row)
        requested_filters = list(filters or [])
        legacy_filter = str(filter or "").strip().casefold()
        if legacy_filter and legacy_filter not in requested_filters:
            requested_filters.append(legacy_filter)
        dialog._set_brush_filters(requested_filters)
        search_edit = getattr(dialog, "_brush_search_edit", None)
        if search_edit is not None:
            search_edit.setText(str(search or ""))
        if compact is not None:
            compact_button = getattr(dialog, "_brush_compact_btn", None)
            if compact_button is not None:
                compact_button.setChecked(bool(compact))
            else:
                dialog._set_brush_selector_compact(bool(compact))
        dialog._populate_brush_library()
        return dialog.painter_action_state()

    def paint_brush_favorite_set(
        self,
        *,
        preset: str,
        favorite: bool,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.drawing import BRUSH_LIBRARY_PRESETS

        preset_key = str(preset or "").strip().casefold().replace("-", "_").replace(" ", "_")
        selected_index = -1
        for index, row in enumerate(BRUSH_LIBRARY_PRESETS):
            name_key = str(row.get("name") or "").strip().casefold().replace("-", "_").replace(" ", "_")
            style_key = str(row.get("style") or "").strip().casefold().replace("-", "_").replace(" ", "_")
            if preset_key in {name_key, style_key}:
                selected_index = index
                break
        if selected_index < 0:
            raise ValueError("Painter brush preset not found")
        selected = BRUSH_LIBRARY_PRESETS[selected_index]
        key = dialog._brush_preset_key(selected)
        if bool(favorite):
            dialog._brush_favorites.add(key)
        else:
            dialog._brush_favorites.discard(key)
        dialog._active_brush_preset_index = selected_index
        dialog._update_brush_favorite_button()
        dialog._populate_brush_library()
        dialog._populate_brush_recent_list()
        return dialog.painter_action_state()

    def paint_stroke_draw(
        self,
        *,
        strokes: list[dict[str, Any]] | None = None,
        undo_label: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        rows = list(strokes or [])
        if not rows:
            raise ValueError("strokes must contain at least one stroke")
        if len(rows) > 512:
            raise ValueError("strokes cannot contain more than 512 entries")

        from PySide6.QtGui import QColor

        from app.drawing import Stroke

        paint_layers = {
            str(layer.layer_id): layer
            for layer in list(getattr(dialog, "_paint_layers", []) or [])
        }
        active_layer_id = str(getattr(dialog, "_active_paint_layer_id", "") or "paint-layer-1")
        prepared: list[Stroke] = []
        point_count = 0
        rendered_point_count = 0
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(f"stroke {index} must be an object")
            raw_points = list(row.get("points") or [])
            if len(raw_points) < 2:
                raise ValueError(f"stroke {index} requires at least two points")
            if len(raw_points) > 2048:
                raise ValueError(f"stroke {index} exceeds the 2048 point limit")
            point_count += len(raw_points)
            path_mode = str(row.get("path_mode") or "smooth").strip().casefold()
            if path_mode not in {"smooth", "polyline"}:
                raise ValueError(f"stroke {index} has invalid path_mode: {path_mode}")
            if path_mode == "smooth" and len(raw_points) >= 3:
                from app.painter_stroke_geometry import smooth_action_points

                raw_points = smooth_action_points(raw_points)
            points: list[tuple[float, float]] = []
            pressure: list[float] = []
            tilt: list[float] = []
            tilt_x: list[float] = []
            tilt_y: list[float] = []
            rotation: list[float] = []
            tangential_pressure: list[float] = []
            paint_load: list[float] = []
            for point_index, point in enumerate(raw_points):
                if not isinstance(point, dict) or "x" not in point or "y" not in point:
                    raise ValueError(f"stroke {index} point {point_index} requires x and y")
                x = float(point["x"])
                y = float(point["y"])
                if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
                    raise ValueError(
                        f"stroke {index} point {point_index} is outside normalized canvas bounds"
                    )
                points.append((x, y))
                pressure.append(max(0.0, min(1.0, float(point.get("pressure", 0.82)))))
                tilt.append(max(0.0, min(1.0, float(point.get("tilt", 0.5)))))
                tilt_x.append(max(-1.0, min(1.0, float(point.get("tilt_x", 0.0)))))
                tilt_y.append(max(-1.0, min(1.0, float(point.get("tilt_y", 0.0)))))
                rotation.append(max(0.0, min(1.0, float(point.get("rotation", 0.5)))))
                tangential_pressure.append(
                    max(-1.0, min(1.0, float(point.get("tangential_pressure", 0.0))))
                )
                paint_load.append(max(0.0, min(1.0, float(point.get("load", 1.0)))))

            layer_id = str(row.get("layer_id") or active_layer_id)
            layer = paint_layers.get(layer_id)
            if layer is None:
                raise ValueError(f"stroke {index} references unknown layer_id: {layer_id}")
            if bool(getattr(layer, "locked", False)):
                raise ValueError(f"stroke {index} targets locked layer_id: {layer_id}")

            color_value = str(row.get("color") or "#EEF2F7")
            color = QColor(color_value)
            if not color.isValid():
                raise ValueError(f"stroke {index} has invalid color: {color_value}")
            opacity_percent = max(1, min(100, int(row.get("opacity", 100) or 100)))
            is_material = str(getattr(layer, "layer_type", "standard") or "standard") == "material"
            engine_version = max(
                1,
                min(2, int(row.get("engine_version", 2 if is_material else 1) or 1)),
            )
            material = {}
            if is_material:
                from app.painter_material_paint import normalize_material_settings

                material = normalize_material_settings(
                    getattr(layer, "material_settings", {}) or {}
                )
            prepared.append(
                Stroke(
                    points=points,
                    color=(color.red(), color.green(), color.blue()),
                    opacity=int(round(opacity_percent * 255 / 100)),
                    width_px=max(0.25, min(512.0, float(row.get("width", 4.0) or 4.0))),
                    brush_style=str(row.get("style") or "round"),
                    brush_hardness=max(1, min(100, int(row.get("hardness", 100) or 100))),
                    brush_spacing=max(1, min(200, int(row.get("spacing", 25) or 25))),
                    brush_angle=max(-180, min(180, int(row.get("angle", 0) or 0))),
                    brush_roundness=max(10, min(100, int(row.get("roundness", 100) or 100))),
                    closed_path=bool(row.get("closed", False)),
                    layer_id=layer_id,
                    source_tool="ai_paint",
                    brush_engine_version=engine_version,
                    point_pressure=pressure,
                    point_tilt=tilt,
                    point_tilt_x=tilt_x,
                    point_tilt_y=tilt_y,
                    point_rotation=rotation,
                    point_tangential_pressure=tangential_pressure,
                    point_load=paint_load,
                    bristle_count=max(
                        0, min(64, int(row.get("bristle_count", 0) or 0))
                    ),
                    brush_seed=int(row.get("seed", index * 7919 + len(points) * 131) or 0),
                    load_depletion=max(
                        0.0,
                        min(1.0, float(row.get("load_depletion", 0.28) or 0.0)),
                    ),
                    material_enabled=is_material,
                    material_load=float(material.get("load", 0.0)),
                    material_thickness=float(material.get("thickness", 0.0)),
                    material_wetness=float(material.get("wetness", 0.0)),
                    material_gloss=float(material.get("gloss", 0.0)),
                    material_roughness=float(material.get("roughness", 0.56)),
                    start_ms=int(getattr(dialog, "_time_ms", 0) or 0),
                )
            )
            rendered_point_count += len(points)

        dialog._push_undo_state(str(undo_label or "AI paint strokes"))
        existing = dialog.canvas.embedded_strokes()
        dialog.canvas.set_strokes_snapshot([*existing, *prepared])
        dialog._update_inspector_counts()
        state = dialog.painter_action_state()
        state["stroke_draw"] = {
            "stroke_count": len(prepared),
            "point_count": point_count,
            "rendered_point_count": rendered_point_count,
            "undo_label": str(undo_label or "AI paint strokes"),
            "coordinate_space": "normalized_canvas",
            "engine_versions": sorted(
                {int(stroke.brush_engine_version) for stroke in prepared}
            ),
            "dynamic_channels": [
                "pressure",
                "tilt",
                "tilt_x",
                "tilt_y",
                "rotation",
                "tangential_pressure",
                "load",
            ],
        }
        return state

    def paint_history_undo(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        before = len(getattr(dialog, "_undo_stack", []) or [])
        dialog._undo()
        state = dialog.painter_action_state()
        state["history_action"] = {"operation": "undo", "changed": before > 0}
        return state

    def paint_history_redo(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        before = len(getattr(dialog, "_redo_stack", []) or [])
        dialog._redo()
        state = dialog.painter_action_state()
        state["history_action"] = {"operation": "redo", "changed": before > 0}
        return state

    def paint_window_show_panel(self, *, panel: str = "layers") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(panel or "layers")
        if target.strip().casefold() in {"brush", "brushes", "brush_settings"}:
            dialog._focus_brush_panel()
        elif target.strip().casefold() in {"reference", "references", "reference_board", "ref"}:
            dialog._focus_reference_board_panel()
        elif target.strip().casefold() in {"3d", "blockout", "3d_blockout"}:
            dialog._focus_3d_blockout_panel()
        else:
            dialog._show_painter_tab(target)
        return dialog.painter_action_state()

    def paint_pbr_preview(
        self,
        *,
        path: str = "",
        preview_mode: str = "material",
        preview_shape: str = "plane",
        width: int = 512,
        settings: dict[str, Any] | None = None,
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not path:
            import tempfile

            path = str(Path(tempfile.gettempdir()) / "tiger_painter_pbr" / f"painter_pbr_{preview_mode or 'material'}.png")
        return dialog.preview_pbr_map_to_path(
            path,
            preview_mode=str(preview_mode or "material"),
            preview_shape=str(preview_shape or "plane"),
            width=int(width or 512),
            settings=dict(settings or {}),
            allow_cpu=allow_cpu,
        )

    def paint_pbr_export(
        self,
        *,
        output_dir: str = "",
        settings: dict[str, Any] | None = None,
        maps: list[str] | None = None,
        packed_layouts: list[str] | None = None,
        packed: bool = True,
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not output_dir:
            from datetime import datetime

            from app.paths import default_save_dir

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = str(default_save_dir() / f"painter_pbr_maps_{stamp}")
        return dialog.export_pbr_maps_to_path(
            output_dir,
            settings=dict(settings or {}),
            maps=maps,
            packed_layouts=packed_layouts,
            packed=bool(packed),
            allow_cpu=allow_cpu,
        )

    def paint_pbr_substrate_plan(
        self,
        *,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.ar_pbr.texture_map_lab import substrate_export_plan

        merged = dialog._pbr_texture_settings_payload(dict(settings or {}))
        return substrate_export_plan(merged)

    def paint_pbr_backend_status(
        self,
        *,
        backend: str = "auto",
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        self._paint_dialog_owner()
        from app.ar_pbr.texture_map_lab import select_texture_map_backend, texture_lab_cpu_fallback_allowed

        cpu_allowed = texture_lab_cpu_fallback_allowed(False) if allow_cpu is None else bool(allow_cpu)
        return select_texture_map_backend(backend, allow_cpu=cpu_allowed)

    def paint_editor_objects_list(
        self,
        *,
        time_ms: int | None = None,
        include_inactive: bool = True,
        limit: int = 100,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=bool(include_inactive),
        )
        max_rows = max(0, _int(limit, 100))
        objects = [self._paint_object_payload(row) for row in rows[:max_rows]]
        return {
            "schema": "tigerstudio.actions.paint.editor_objects.list.v1",
            "time_ms": target_ms,
            "count": len(rows),
            "returned": len(objects),
            "objects": objects,
        }

    def paint_editor_object_render(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
        output_dir: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        obj = self._paint_find_import_object(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
        )
        from app.drawing_editor_object_import import render_paint_import_object

        report = render_paint_import_object(
            obj,
            canvas_size=self._paint_canvas_size(),
            output_dir=output_dir or None,
            force=bool(force),
        )
        return {
            "schema": "tigerstudio.actions.paint.editor_object.render.v1",
            "object": self._paint_object_payload(obj),
            "render": report,
        }

    def paint_editor_object_import(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
        x_norm: float | None = None,
        y_norm: float | None = None,
        width_norm: float | None = None,
        height_norm: float | None = None,
        output_dir: str = "",
        force: bool = False,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        obj = self._paint_find_import_object(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
        )
        from app.drawing import Sticker
        from app.drawing_editor_object_import import render_paint_import_object

        report = render_paint_import_object(
            obj,
            canvas_size=self._paint_canvas_size(),
            output_dir=output_dir or None,
            force=bool(force),
        )
        rect = dict(report.get("rect_norm") or {})
        w = _clamp_norm(width_norm if width_norm is not None else rect.get("w", obj.width_norm), 0.04, 1.0)
        h = _clamp_norm(height_norm if height_norm is not None else rect.get("h", obj.height_norm), 0.04, 1.0)
        x = _clamp_norm(x_norm if x_norm is not None else rect.get("x", obj.x_norm), 0.0, 1.0 - w)
        y = _clamp_norm(y_norm if y_norm is not None else rect.get("y", obj.y_norm), 0.0, 1.0 - h)
        stickers = getattr(owner, "_stickers", None)
        if stickers is None:
            stickers = []
            setattr(owner, "_stickers", stickers)
        start_ms = self._paint_action_time_ms(time_ms)
        sticker = Sticker(
            png_path=str(report.get("png_path") or ""),
            x_norm=x,
            y_norm=y,
            width_norm=w,
            height_norm=h,
            start_ms=start_ms,
            end_ms=-1,
            z_index=max((int(getattr(row, "z_index", 0) or 0) for row in stickers), default=0) + 1,
        )
        stickers.append(sticker)
        spawn = getattr(owner, "_spawn_sticker_item", None)
        if callable(spawn):
            try:
                spawn(sticker)
            except Exception:
                pass
        update_visibility = getattr(owner, "_update_sticker_visibility", None)
        if callable(update_visibility):
            try:
                update_visibility(start_ms)
            except Exception:
                pass
        canvas = getattr(owner, "_drawing_canvas", None)
        if canvas is not None and hasattr(canvas, "update"):
            try:
                canvas.update()
            except Exception:
                pass
        self._register_change("Import editor object into paint")
        return {
            "schema": "tigerstudio.actions.paint.editor_object.import.v1",
            "object": self._paint_object_payload(obj),
            "sticker": {
                "png_path": str(Path(sticker.png_path)),
                "x_norm": sticker.x_norm,
                "y_norm": sticker.y_norm,
                "width_norm": sticker.width_norm,
                "height_norm": sticker.height_norm,
                "start_ms": sticker.start_ms,
                "end_ms": sticker.end_ms,
                "z_index": sticker.z_index,
            },
            "render": report,
            "sticker_count": len(stickers),
        }

    def paint_3d_blockout_state(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        scene = self._paint_3d_blockout_scene(dialog)
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_add(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import add_blockout_primitive

        scene = add_blockout_primitive(self._paint_3d_blockout_scene(dialog), **dict(params))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Add Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_update(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import update_blockout_primitive

        scene = update_blockout_primitive(
            self._paint_3d_blockout_scene(dialog),
            str(primitive_id or ""),
            **dict(params),
        )
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Update Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_delete(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import delete_blockout_primitive

        scene = delete_blockout_primitive(self._paint_3d_blockout_scene(dialog), str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Delete Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_duplicate(
        self,
        *,
        primitive_id: str = "",
        offset_x: float = 0.65,
        offset_y: float = 0.0,
        offset_z: float = 0.25,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import duplicate_blockout_primitive

        scene = duplicate_blockout_primitive(
            self._paint_3d_blockout_scene(dialog),
            str(primitive_id or ""),
            offset=(float(offset_x), float(offset_y), float(offset_z)),
        )
        rows = scene.to_dict().get("primitives", [])
        if rows:
            setattr(dialog, "_painter_3d_blockout_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Duplicate Painter 3D blockout primitive")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_align_ground(
        self,
        *,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import align_blockout_primitive_to_ground

        scene = align_blockout_primitive_to_ground(self._paint_3d_blockout_scene(dialog), str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Align Painter 3D blockout primitive to ground")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_snap(
        self,
        *,
        enabled: bool | None = None,
        primitive_id: str = "",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import set_blockout_snap, snap_blockout_primitive_to_grid

        scene = self._paint_3d_blockout_scene(dialog)
        if enabled is not None:
            scene = set_blockout_snap(scene, bool(enabled))
        if str(primitive_id or "").strip():
            scene = snap_blockout_primitive_to_grid(scene, str(primitive_id or ""))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Set Painter 3D blockout snap")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_camera(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
        **params: Any,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import update_blockout_camera

        scene = update_blockout_camera(self._paint_3d_blockout_scene(dialog), **dict(params))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Adjust Painter 3D blockout camera")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_material_preview(
        self,
        *,
        material_lit: bool | None = None,
        show_floor: bool | None = None,
        show_shadows: bool | None = None,
        show_fog: bool | None = None,
        show_depth: bool | None = None,
        light_yaw_degrees: float | None = None,
        light_pitch_degrees: float | None = None,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        from dataclasses import replace

        dialog = self._paint_dialog_owner()
        scene = self._paint_3d_blockout_scene(dialog)
        changes: dict[str, Any] = {}
        if material_lit is not None:
            changes["material_lit"] = bool(material_lit)
        if show_floor is not None:
            changes["show_floor"] = bool(show_floor)
        if show_shadows is not None:
            changes["show_shadows"] = bool(show_shadows)
        if show_fog is not None:
            changes["show_fog"] = bool(show_fog)
        if show_depth is not None:
            changes["show_depth"] = bool(show_depth)
        if light_yaw_degrees is not None:
            changes["light_yaw_degrees"] = float(light_yaw_degrees)
        if light_pitch_degrees is not None:
            changes["light_pitch_degrees"] = float(light_pitch_degrees)
        scene = replace(scene, **changes).normalized()
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Adjust Painter 3D blockout material preview")
        return self._paint_3d_blockout_payload(
            scene,
            preview_width=preview_width,
            preview_height=preview_height,
        )

    def paint_3d_blockout_camera_preset(
        self,
        *,
        preset: str = "perspective",
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import apply_blockout_camera_preset

        scene = apply_blockout_camera_preset(self._paint_3d_blockout_scene(dialog), str(preset or "perspective"))
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Apply Painter 3D blockout camera preset")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_bake(
        self,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        bake = getattr(dialog, "_bake_3d_blockout_to_layer", None)
        if not callable(bake):
            raise RuntimeError("Active Painter dialog does not support 3D blockout baking")
        report = bake()
        if not report:
            raise ValueError("No Painter 3D blockout guide edges are available to bake")
        self._register_change("Bake Painter 3D blockout")
        scene = self._paint_3d_blockout_scene(dialog)
        payload = self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)
        payload["bake"] = report
        return payload

    def paint_export_png(
        self,
        *,
        path: str = "",
        mode: str = "composited",
        time_ms: int | None = None,
        width: int = 0,
        height: int = 0,
    ) -> dict[str, Any]:
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        mode_text = str(mode or "composited").strip().casefold().replace("-", "_")
        include_background = mode_text not in {"overlay", "transparent", "transparent_overlay"}
        if not path:
            from datetime import datetime

            from app.paths import default_save_dir

            suffix = "composited" if include_background else "overlay"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = str(default_save_dir() / f"paint_{suffix}_{stamp}.png")
        background = getattr(owner, "_preview_pixmap", None) if include_background else None
        frame_size = None
        if int(width or 0) > 0 and int(height or 0) > 0:
            frame_size = (int(width), int(height))
        else:
            frame_size = self._paint_export_size_for_owner(background)
        canvas_w, _canvas_h = self._paint_canvas_size()
        stroke_width_scale = max(0.001, float(frame_size[0]) / max(1, float(canvas_w)))
        from app.drawing import export_paint_png

        report = export_paint_png(
            path,
            background_pixmap=background,
            strokes=list(getattr(owner, "_strokes", []) or []),
            bubbles=list(getattr(owner, "_bubbles", []) or []),
            stickers=list(getattr(owner, "_stickers", []) or []),
            time_ms=target_ms,
            frame_size=frame_size,
            include_background=include_background,
            stroke_width_scale=stroke_width_scale,
            paint_layers=list(getattr(owner, "_paint_layers", []) or []),
        )
        return report

    def _paint_3d_blockout_scene(self, dialog: Any):
        from app.painter_3d_blockout import blockout_scene_from_dict

        return blockout_scene_from_dict(getattr(dialog, "_painter_3d_blockout_scene", None))

    def _store_paint_3d_blockout_scene(self, dialog: Any, scene: Any) -> None:
        setattr(dialog, "_painter_3d_blockout_scene", scene.to_dict())
        setattr(dialog, "_painter_3d_blockout_flat_cache", None)
        if scene.to_dict().get("primitive_count", 0):
            ensure_layer = getattr(dialog, "_ensure_3d_blockout_layer", None)
            if callable(ensure_layer):
                try:
                    ensure_layer()
                except Exception:
                    pass
        refresh = getattr(dialog, "_refresh_3d_blockout_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def _paint_3d_blockout_payload(
        self,
        scene: Any,
        *,
        preview_width: int = 640,
        preview_height: int = 360,
    ) -> dict[str, Any]:
        from app.painter_3d_blockout import project_blockout_scene
        from app.painter_opengl import PAINTER_OPENGL_RENDERER_ID

        projection = project_blockout_scene(scene, int(preview_width or 640), int(preview_height or 360))
        try:
            dialog = self._paint_dialog_owner()
            renderer_status = dict(getattr(dialog, "_painter_3d_blockout_renderer_status", {}) or {})
        except Exception:
            renderer_status = {}
        return {
            "schema": "tigerstudio.actions.paint.3d_blockout.v1",
            "scene": scene.to_dict(),
            "projection": projection,
            "renderer": {
                "preferred": PAINTER_OPENGL_RENDERER_ID,
                "fallback": "painter_blockout_qpainter_v1",
                "last_render": renderer_status,
                "remote_safe": True,
            },
            "gpu_contract": {
                "future_gpu_preview": True,
                "opengl_first_preview": True,
                "qpainter_fallback": True,
                "payload_is_serializable": True,
                "qt_preview_is_reference_only": True,
            },
            "ui_guardrails": {
                "preserve_texture_lab_entry_points": True,
                "layers_channels_paths_remain_primary_dock": True,
                "blockout_is_optional_painter_doorway": True,
            },
            "gizmo_contract": {
                "standard_3d_gizmo": True,
                "axis_convention": "z_up_x_red_y_green_z_blue",
                "object_modes": ["move", "rotate", "scale"],
                "camera_modes": ["orbit", "pan", "wasd", "wheel_zoom", "zoom_distance", "fov"],
                "primitive_scope": ["box", "sphere", "cylinder", "cone", "plane", "arch"],
                "drop_placement": "screen_to_world_ground_plane",
            },
            "paint_over_contract": {
                "reference_layer": "paint-layer-3d-blockout",
                "paint_strokes_above_reference": True,
                "paint_mode_flat_cache": True,
                "scene_remains_editable": True,
            },
        }

    def _paint_dialog_owner(self) -> Any:
        owner = self._require_owner()
        if _looks_like_paint_dialog(owner):
            return owner
        for attr in (
            "_active_painter_window",
            "_active_paint_dialog",
            "_paint_dialog",
            "_painter_dialog",
        ):
            candidate = getattr(owner, attr, None)
            if _looks_like_paint_dialog(candidate):
                return candidate
        workbench = getattr(owner, "_workbench_panel", None) or getattr(owner, "workbench_panel", None)
        candidates: list[Any] = []
        if workbench is not None:
            candidates.extend(list(getattr(workbench, "_painter_windows", []) or []))
        candidates.extend(list(getattr(owner, "_painter_windows", []) or []))
        for candidate in reversed(candidates):
            if not _looks_like_paint_dialog(candidate):
                continue
            try:
                if hasattr(candidate, "isVisible") and not candidate.isVisible():
                    continue
            except Exception:
                pass
            return candidate
        raise ValueError("no active Painter dialog")

    def _paint_action_time_ms(self, time_ms: int | None) -> int:
        if time_ms is not None:
            return max(0, _int(time_ms, 0))
        owner = self._require_owner()
        player = getattr(owner, "_player", None)
        position = getattr(player, "position", None)
        if callable(position):
            try:
                return max(0, _int(position(), 0))
            except Exception:
                pass
        return 0

    def _paint_canvas_size(self) -> tuple[int, int]:
        owner = self._require_owner()
        for name in ("_drawing_canvas", "_preview_label", "_preview_widget"):
            widget = getattr(owner, name, None)
            if widget is not None:
                try:
                    width = int(widget.width())
                    height = int(widget.height())
                    if width > 0 and height > 0:
                        return (width, height)
                except Exception:
                    pass
        pixmap = getattr(owner, "_preview_pixmap", None)
        if pixmap is not None:
            try:
                width = int(pixmap.width())
                height = int(pixmap.height())
                if width > 0 and height > 0:
                    return (width, height)
            except Exception:
                pass
        return (1920, 1080)

    def _paint_export_size_for_owner(self, background: Any) -> tuple[int, int]:
        if background is not None:
            try:
                width = int(background.width())
                height = int(background.height())
                if width > 0 and height > 0:
                    return (width, height)
            except Exception:
                pass
        return self._paint_canvas_size()

    def _paint_find_import_object(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
    ):
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=bool(include_inactive),
        )
        wanted_id = str(object_id or "").strip()
        wanted_kind = str(kind or "").strip()
        if wanted_id:
            for row in rows:
                if row.id == wanted_id:
                    return row
            raise ValueError(f"paint import object not found: {wanted_id}")
        if wanted_kind:
            for row in rows:
                if row.kind == wanted_kind:
                    return row
            raise ValueError(f"paint import object kind not found: {wanted_kind}")
        if rows:
            return rows[0]
        raise ValueError("no paint import objects available")

    @staticmethod
    def _paint_object_payload(obj: Any) -> dict[str, Any]:
        return {
            "id": str(getattr(obj, "id", "")),
            "kind": str(getattr(obj, "kind", "")),
            "label": str(getattr(obj, "label", "")),
            "source_path": str(getattr(obj, "source_path", "")),
            "active": bool(getattr(obj, "active", False)),
            "start_ms": int(getattr(obj, "start_ms", 0) or 0),
            "end_ms": int(getattr(obj, "end_ms", -1) or -1),
            "x_norm": float(getattr(obj, "x_norm", 0.0) or 0.0),
            "y_norm": float(getattr(obj, "y_norm", 0.0) or 0.0),
            "width_norm": float(getattr(obj, "width_norm", 0.0) or 0.0),
            "height_norm": float(getattr(obj, "height_norm", 0.0) or 0.0),
            "payload": dict(getattr(obj, "payload", {}) or {}),
        }

    def _paint_reference_board(self, dialog: Any):
        from app.painter_reference_board import reference_board_from_dict

        return reference_board_from_dict(getattr(dialog, "_painter_reference_board", None))

    def _store_paint_reference_board(self, dialog: Any, board: Any) -> None:
        setattr(dialog, "_painter_reference_board", board.to_dict())
        refresh = getattr(dialog, "_refresh_reference_board_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception:
                pass
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception:
                pass

    def _paint_reference_payload(self, dialog: Any) -> dict[str, Any]:
        board = self._paint_reference_board(dialog)
        selected = str(getattr(dialog, "_painter_reference_selected_id", "") or "")
        return {
            "schema": "tigerstudio.actions.paint.reference_board.v1",
            "board": board.to_dict(),
            "selected_reference_id": selected,
            "ui_contract": {
                "non_destructive_reference_overlay": True,
                "exported_by_default": False,
                "requires_explicit_bake": True,
                "layers_channels_paths_remain_primary_dock": True,
            },
        }

    def paint_reference_state(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return self._paint_reference_payload(dialog)

    def paint_reference_add(
        self,
        *,
        path: str = "",
        name: str = "",
        x_norm: float = 0.04,
        y_norm: float = 0.04,
        width_norm: float = 0.34,
        height_norm: float = 0.34,
        opacity: float = 0.58,
        rotation_deg: float = 0.0,
        visible: bool = True,
        locked: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_reference_board import add_reference_image

        board = add_reference_image(
            self._paint_reference_board(dialog),
            path=str(path or ""),
            name=str(name or ""),
            x_norm=float(x_norm),
            y_norm=float(y_norm),
            width_norm=float(width_norm),
            height_norm=float(height_norm),
            opacity=float(opacity),
            rotation_deg=float(rotation_deg),
            visible=bool(visible),
            locked=bool(locked),
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_update(
        self,
        *,
        reference_id: str = "",
        name: str | None = None,
        x_norm: float | None = None,
        y_norm: float | None = None,
        width_norm: float | None = None,
        height_norm: float | None = None,
        opacity: float | None = None,
        rotation_deg: float | None = None,
        visible: bool | None = None,
        locked: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import update_reference_image

        board = update_reference_image(
            self._paint_reference_board(dialog),
            target,
            name=name,
            x_norm=x_norm,
            y_norm=y_norm,
            width_norm=width_norm,
            height_norm=height_norm,
            opacity=opacity,
            rotation_deg=rotation_deg,
            visible=visible,
            locked=locked,
        )
        setattr(dialog, "_painter_reference_selected_id", target)
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_delete(self, *, reference_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import delete_reference_image

        board = delete_reference_image(self._paint_reference_board(dialog), target)
        rows = board.to_dict().get("references", [])
        setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or "") if rows else "")
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_duplicate(
        self,
        *,
        reference_id: str = "",
        offset_x: float = 0.04,
        offset_y: float = 0.04,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        from app.painter_reference_board import duplicate_reference_image

        board = duplicate_reference_image(
            self._paint_reference_board(dialog),
            target,
            offset_x=float(offset_x),
            offset_y=float(offset_y),
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_bake(self, *, reference_id: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if reference_id:
            setattr(dialog, "_painter_reference_selected_id", str(reference_id))
        bake = dialog._bake_selected_reference_to_sticker()
        return {
            **self._paint_reference_payload(dialog),
            "bake": dict(bake or {}),
        }

    def paint_reference_sample_color(
        self,
        *,
        reference_id: str = "",
        x_norm: float = 0.5,
        y_norm: float = 0.5,
        apply: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        if target:
            setattr(dialog, "_painter_reference_selected_id", target)
        reference = dialog._selected_reference_payload()
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import sample_reference_color
        from PySide6.QtGui import QColor

        sample = sample_reference_color(str(reference.get("path") or ""), x_norm=float(x_norm), y_norm=float(y_norm))
        if bool(apply):
            rgb = sample.get("rgb", [255, 255, 255])
            dialog._apply_pen_color(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])), remember=True)
        return {
            **self._paint_reference_payload(dialog),
            "sample": sample,
            "applied_to_foreground": bool(apply),
        }

    def paint_reference_extract_palette(
        self,
        *,
        reference_id: str = "",
        max_colors: int = 8,
        apply: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target = str(reference_id or getattr(dialog, "_painter_reference_selected_id", "") or "")
        if target:
            setattr(dialog, "_painter_reference_selected_id", target)
        reference = dialog._selected_reference_payload()
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import extract_reference_palette
        from PySide6.QtGui import QColor

        palette = extract_reference_palette(str(reference.get("path") or ""), max_colors=int(max_colors or 8))
        applied_colors: list[tuple[int, int, int]] = []
        if bool(apply):
            for row in palette.get("colors", []) or []:
                rgb = row.get("rgb")
                if isinstance(rgb, list) and len(rgb) >= 3:
                    applied_colors.append((int(rgb[0]), int(rgb[1]), int(rgb[2])))
            if applied_colors:
                limit = len(getattr(dialog, "_recent_colors", []) or []) or 5
                dialog._recent_colors = applied_colors[:limit]
                dialog._apply_pen_color(QColor(*applied_colors[0]), remember=False)
        return {
            **self._paint_reference_payload(dialog),
            "palette": palette,
            "applied_to_recent_colors": bool(apply),
        }

    def _paint_study_runtime(self, dialog: Any) -> dict[str, Any]:
        runtime = getattr(dialog, "_paint_study_runtime", None)
        if not isinstance(runtime, dict):
            raise ValueError("paint.study.analyze_reference must run first")
        current_strokes = [
            stroke
            for stroke in dialog.canvas.embedded_strokes()
            if str(getattr(stroke, "source_tool", "") or "").startswith("ai_study_")
        ]
        runtime["stroke_count"] = len(current_strokes)
        layer_ids = {
            str(getattr(layer, "layer_id", "") or "")
            for layer in list(getattr(dialog, "_paint_layers", []) or [])
        }
        runtime["generated_layers"] = [
            row
            for row in list(
                runtime.get("generated_layer_history")
                or runtime.get("generated_layers")
                or []
            )
            if str(row.get("layer_id") or "") in layer_ids
        ]
        return runtime

    def paint_study_analyze_reference(
        self,
        *,
        reference_path: str = "",
        target_width: int = 800,
        region_count: int = 12,
        seed: int = 240725,
        focus_regions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        import time
        from app.painter_ai_study import analyze_reference

        started = time.perf_counter()
        runtime, report = analyze_reference(
            reference_path,
            target_width=int(target_width or 800),
            max_regions=int(region_count or 12),
            seed=int(seed or 0),
            focus_regions=focus_regions,
        )
        runtime.setdefault("timings", []).append(
            {
                "operation": "analyze_reference",
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
            }
        )
        setattr(dialog, "_paint_study_runtime", runtime)
        return {"study": report}

    def paint_study_segment_regions(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ai_study import segment_report

        return {"study": segment_report(self._paint_study_runtime(dialog))}

    def _paint_study_add_phase(
        self,
        dialog: Any,
        *,
        phase: str,
        max_strokes: int,
        layer_name: str,
        seed_offset: int,
        refinement: bool = False,
    ) -> dict[str, Any]:
        from app.drawing import PaintLayer
        from app.painter_ai_study import (
            generate_phase_strokes,
            generate_refinement_strokes,
            quality_report,
        )

        runtime = self._paint_study_runtime(dialog)
        import time
        started = time.perf_counter()
        label = str(layer_name or "").strip() or f"AI Study {str(phase).title()}"
        next_serial = int(dialog._paint_layer_serial) + 1
        layer_id = f"paint-layer-{next_serial}"
        layer_type = "material" if str(phase) == "accent" else "standard"
        if refinement:
            generated = generate_refinement_strokes(
                runtime,
                layer_id=layer_id,
                max_strokes=int(max_strokes or 5000),
                seed_offset=int(seed_offset or 0),
            )
        else:
            generated = generate_phase_strokes(
                runtime,
                phase=str(phase),
                layer_id=layer_id,
                max_strokes=int(max_strokes or 5000),
                seed_offset=int(seed_offset or 0),
            )
        dialog._push_undo_state(label)
        dialog._paint_layer_serial = next_serial
        layer = PaintLayer(
            layer_id=layer_id,
            name=label[:80],
            layer_type=layer_type,
        )
        dialog._paint_layers.append(layer)
        dialog._active_paint_layer_id = layer_id
        dialog._selected_layer_id = layer_id
        existing = dialog.canvas.embedded_strokes()
        dialog.canvas.set_strokes_snapshot([*existing, *generated])
        runtime["stroke_count"] = int(runtime.get("stroke_count", 0)) + len(generated)
        layer_report = {
            "layer_id": layer_id,
            "name": label[:80],
            "phase": "refinement" if refinement else str(phase),
            "stroke_count": len(generated),
        }
        runtime.setdefault("generated_layer_history", []).append(layer_report)
        runtime.setdefault("generated_layers", []).append(layer_report)
        runtime["last_comparison"] = {}
        runtime.pop("error_map", None)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        runtime.setdefault("timings", []).append(
            {
                "operation": "refine_region" if refinement else f"generate_{phase}",
                "elapsed_ms": elapsed_ms,
                "stroke_count": len(generated),
            }
        )
        dialog._sync_canvas_layer_view()
        dialog._update_inspector_counts()
        return {
            "study": quality_report(runtime),
            "generated": {
                "layer_id": layer_id,
                "phase": "refinement" if refinement else str(phase),
                "stroke_count": len(generated),
                "elapsed_ms": elapsed_ms,
            },
        }

    def paint_study_build_underpaint(
        self,
        *,
        max_strokes: int = 5000,
        layer_name: str = "AI Study Underpaint",
        seed_offset: int = 0,
    ) -> dict[str, Any]:
        return self._paint_study_add_phase(
            self._paint_dialog_owner(),
            phase="underpaint",
            max_strokes=max_strokes,
            layer_name=layer_name,
            seed_offset=seed_offset,
        )

    def paint_study_trace_contours(
        self,
        *,
        max_strokes: int = 5000,
        layer_name: str = "AI Study Contours",
        seed_offset: int = 0,
    ) -> dict[str, Any]:
        return self._paint_study_add_phase(
            self._paint_dialog_owner(),
            phase="contour",
            max_strokes=max_strokes,
            layer_name=layer_name,
            seed_offset=seed_offset,
        )

    def paint_study_generate_strokes(
        self,
        *,
        phase: str = "forms",
        max_strokes: int = 5000,
        layer_name: str = "",
        seed_offset: int = 0,
    ) -> dict[str, Any]:
        return self._paint_study_add_phase(
            self._paint_dialog_owner(),
            phase=phase,
            max_strokes=max_strokes,
            layer_name=layer_name,
            seed_offset=seed_offset,
        )

    def paint_study_compare_render(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        runtime = self._paint_study_runtime(dialog)
        import time
        started = time.perf_counter()
        from PIL import Image
        from app.drawing import (
            _pixmap_to_pil_rgba,
            compose_pil_paint_overlays,
        )
        from app.painter_ai_study import compare_reference_to_render

        width, height = int(runtime["width"]), int(runtime["height"])
        background = dialog._export_background_pixmap()
        if background is not None and not background.isNull():
            base = _pixmap_to_pil_rgba(background).resize(
                (width, height),
                Image.Resampling.LANCZOS,
            )
        else:
            base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        overlay = compose_pil_paint_overlays(
            strokes=dialog._visible_strokes_for_export(),
            bubbles=[],
            stickers=[],
            time_ms=int(dialog._time_ms),
            frame_size=(width, height),
            stroke_width_scale=1.0,
            paint_layers=list(getattr(dialog, "_paint_layers", []) or []),
        )
        rendered = Image.alpha_composite(base.convert("RGBA"), overlay)
        comparison = compare_reference_to_render(runtime, rendered)
        runtime.setdefault("timings", []).append(
            {
                "operation": "compare_render",
                "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
                "stroke_count": int(runtime.get("stroke_count", 0)),
            }
        )
        return {"study": comparison}

    def paint_study_refine_region(
        self,
        *,
        max_strokes: int = 5000,
        layer_name: str = "AI Study Refinement",
        seed_offset: int = 0,
    ) -> dict[str, Any]:
        return self._paint_study_add_phase(
            self._paint_dialog_owner(),
            phase="detail",
            max_strokes=max_strokes,
            layer_name=layer_name,
            seed_offset=seed_offset,
            refinement=True,
        )

    def paint_study_quality_report(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ai_study import quality_report

        return {"study": quality_report(self._paint_study_runtime(dialog))}


def _clamp_norm(value: Any, lo: float, hi: float) -> float:
    try:
        number = float(value)
    except Exception:
        number = lo
    return max(lo, min(hi, number))


def _looks_like_paint_dialog(candidate: Any) -> bool:
    if candidate is None:
        return False
    return bool(
        hasattr(candidate, "canvas")
        and callable(getattr(candidate, "painter_action_state", None))
        and callable(getattr(candidate, "export_png_to_path", None))
    )


__all__ = ["PaintAdapterMixin"]
