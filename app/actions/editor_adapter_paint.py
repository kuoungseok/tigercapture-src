"""Paint / drawing action adapter methods."""
from __future__ import annotations

import copy
import math
import operator
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt

from app.painter_channel_contract import PAINTER_CHANNEL_IDS

from app.actions.editor_adapter_object_helpers import _int


def _validate_component_or_saved_channel(
    value: object,
    *,
    allow_empty: bool,
) -> str:
    if not isinstance(value, str):
        raise TypeError("Painter channel must be a string")
    if value != value.strip():
        raise ValueError("Painter channel must not contain surrounding whitespace")
    if not value:
        if allow_empty:
            return ""
        raise ValueError("Painter channel must not be blank")
    if value in PAINTER_CHANNEL_IDS:
        return value
    from app.painter_saved_selection_channels import (
        normalize_saved_selection_channel_id,
    )

    return normalize_saved_selection_channel_id(value)


def _validate_saved_selection_channel_id(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("Saved selection channel id must be a string")
    if value != value.strip():
        raise ValueError(
            "Saved selection channel id must not contain surrounding whitespace"
        )
    from app.painter_saved_selection_channels import normalize_saved_selection_channel_id

    return normalize_saved_selection_channel_id(value)
from app.painter_action_contract import (
    PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
    PAINT_ACTION_DEFAULT_REFERENCE_COLORS,
    PAINT_ACTION_DEFAULT_STUDY_REGIONS,
    PAINT_ACTION_DEFAULT_STUDY_STROKES,
    PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
    PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
    PAINT_ACTION_REQUEST_RESOURCE_CONTRACT,
    PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION,
    PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS,
    PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS,
    PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
    PAINT_ACTION_STROKE_ENGINE_VERSION_MIN,
    PAINT_ACTION_STROKE_OPACITY_MAX_PERCENT,
    PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT,
    PAINT_ACTION_STROKE_SEED_INDEX_FACTOR,
    PAINT_ACTION_STROKE_SEED_POINT_FACTOR,
    PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT,
    PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
    normalize_painter_numeric_color_components,
    normalize_painter_pbr_preview_width,
)
from app.painter_large_canvas import (
    DEFAULT_TILE_BUDGET_MB,
    DEFAULT_TILE_SIZE,
    DEFAULT_UNDO_BUDGET_MB,
    validate_large_canvas_configuration,
)
from app.painter_action_inputs import (
    PAINTER_ACTION_INPUT_UNSET,
    REFERENCE_DEFAULT_HEIGHT_NORM,
    REFERENCE_DEFAULT_OPACITY,
    REFERENCE_DEFAULT_ROTATION_DEGREES,
    REFERENCE_DEFAULT_WIDTH_NORM,
    REFERENCE_DEFAULT_X_NORM,
    REFERENCE_DEFAULT_Y_NORM,
    REFERENCE_DUPLICATE_OFFSET_NORM,
    normalize_paint_time_ms,
    optional_paint_export_size,
    validate_action_integer_domain,
    validate_blockout_preview_action,
    validate_blockout_camera_action,
    validate_blockout_camera_preset_action,
    validate_blockout_duplicate_offset_action,
    validate_blockout_material_preview_action,
    validate_blockout_primitive_id_action,
    validate_blockout_snap_action,
    validate_blockout_primitive_action,
    validate_brush_set_action,
    validate_layer_opacity_action,
    validate_layer_blend_mode_action,
    validate_layer_boolean_action,
    validate_layer_color_label_action,
    validate_layer_ids_action,
    validate_layer_locks_action,
    validate_layer_name_action,
    validate_layer_type_action,
    validate_painter_channel_action,
    validate_layer_mask_gradient_action,
    validate_layer_mask_paint_action,
    validate_layer_mask_state_action,
    validate_material_preview_action,
    validate_optional_action_boolean,
    validate_optional_layer_id_action,
    validate_required_layer_id_action,
    validate_path_create_action,
    validate_path_anchor_action,
    validate_path_id_action,
    validate_path_name_action,
    validate_path_reorder_action,
    validate_optional_path_color_action,
    validate_path_stroke_action,
    validate_pressure_calibration_action,
    validate_reference_palette_action,
    validate_reference_add_action,
    validate_reference_duplicate_action,
    validate_reference_id_action,
    validate_reference_sample_action,
    validate_reference_update_action,
    validate_perspective_guide_action,
    validate_paint_stroke_request,
    validate_editor_object_import_geometry_action,
    validate_editor_object_locator_action,
    validate_editor_objects_list_action,
    validate_canvas_flip_action,
    validate_color_selection_action,
    validate_crop_preview_action,
    validate_document_export_action,
    validate_selection_bounds_action,
    validate_selection_aspect_action,
    validate_selection_lasso_action,
    validate_selection_mode_action,
    validate_selection_modify_action,
    validate_selection_transform_action,
    validate_fill_color_action,
    validate_fill_color_pair_action,
    validate_mirror_action,
    validate_layer_mask_source_action,
    validate_symmetry_guide_action,
    validate_view_pan_action,
    validate_view_pan_result_coordinate,
    validate_zoom_area_action,
)
from app.painter_grid import PAINTER_GRID_SIZE_MAX_PX, PAINTER_GRID_SIZE_MIN_PX
from app.painter_zoom import PAINTER_ZOOM_MAX_PERCENT, PAINTER_ZOOM_MIN_PERCENT
from app.painter_wet_canvas import (
    validate_wet_canvas_advance_seconds,
    validate_wet_canvas_settings_update,
)
from app.actions.editor_adapter_paint_ui_advanced import (
    PaintUIAdvancedAdapterMixin,
)
from app.actions.editor_adapter_paint_ui_figma import PaintUIFigmaAdapterMixin


_PAINTER_ACTION_UNSET = object()


def _paint_positive_extent(value: object) -> int | None:
    """Return a positive integral Qt/raster extent without coercing state."""
    if isinstance(value, bool):
        return None
    try:
        integer = operator.index(value)
    except TypeError:
        return None
    return integer if integer > 0 else None


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

    def paint_performance_status(self) -> dict[str, Any]:
        return self._paint_dialog_owner().painter_large_canvas_status()

    def paint_performance_configure(
        self,
        *,
        tile_size: int = DEFAULT_TILE_SIZE,
        tile_budget_mb: int = DEFAULT_TILE_BUDGET_MB,
        undo_budget_mb: int = DEFAULT_UNDO_BUDGET_MB,
    ) -> dict[str, Any]:
        resolved_tile_size, resolved_tile_budget_mb, resolved_undo_budget_mb = (
            validate_large_canvas_configuration(
                tile_size=tile_size,
                tile_budget_mb=tile_budget_mb,
                undo_budget_mb=undo_budget_mb,
            )
        )
        return self._paint_dialog_owner().configure_painter_large_canvas(
            tile_size=resolved_tile_size,
            tile_budget_mb=resolved_tile_budget_mb,
            undo_budget_mb=resolved_undo_budget_mb,
        )

    def paint_document_new(
        self,
        *,
        width: int = 1920,
        height: int = 1080,
        background: str = "#FFFFFF",
    ) -> dict[str, Any]:
        from app.drawing import (
            _validated_paint_background,
            _validated_paint_dimensions,
        )
        from app.painter_output import PAINTER_NEW_CANVAS_MIN_DIMENSION_PX

        resolved_width, resolved_height = _validated_paint_dimensions(
            width,
            height,
            minimum=PAINTER_NEW_CANVAS_MIN_DIMENSION_PX,
            context="New canvas",
        )
        resolved_background = _validated_paint_background(background)
        dialog = self._paint_dialog_owner()
        dialog._replace_canvas_document(
            resolved_width,
            resolved_height,
            resolved_background,
        )
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

    def paint_ui_responsive_preview_matrix_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_responsive_preview import (
            build_ui_responsive_preview_matrix,
        )

        _documents, report = build_ui_responsive_preview_matrix(
            getattr(dialog, "_painter_ui_document", None)
        )
        return report

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

    def paint_ui_template_search(
        self,
        *,
        query: str = "",
        category: str = "",
        difficulty: str = "",
        platform: str = "",
        view: str = "all",
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_template_store import search_ui_templates

        return search_ui_templates(
            query=query,
            category=category,
            difficulty=difficulty,
            platform=platform,
            view=view,
            store_root=store_root or None,
        )

    def paint_ui_template_preview(
        self,
        *,
        template_id: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_template_store import preview_ui_template

        return preview_ui_template(
            template_id,
            store_root=store_root or None,
        )

    def paint_ui_template_insert(
        self,
        *,
        template_id: str,
        mode: str = "new_document",
        store_root: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_template_insert import insert_ui_template
        from app.painter_ui_template_store import instantiate_stored_ui_template

        source, _source_report = instantiate_stored_ui_template(
            template_id,
            store_root=store_root or None,
        )
        document, report = insert_ui_template(
            dialog._painter_ui_document,
            source,
            template_id=template_id,
            mode=mode,
        )
        dialog._push_undo_state("Insert UI template")
        self._paint_ui_commit(dialog, "Insert UI template", document)
        return {**dialog.painter_action_state(), "template_insert": report}

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

    def paint_ui_library_package_export(
        self,
        *,
        path: str,
        library_id: str,
        name: str,
        version: int = 1,
        description: str = "",
        author: str = "",
        license_id: str = "User-Owned",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_library_store import export_ui_library_package

        return export_ui_library_package(
            dialog._painter_ui_document,
            path,
            library_id=library_id,
            name=name,
            version=version,
            description=description,
            author=author,
            license_id=license_id,
        )

    def paint_ui_library_package_install(
        self,
        *,
        path: str,
        store_root: str = "",
        activate: bool = True,
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import install_ui_library_package

        return install_ui_library_package(
            path,
            store_root=store_root or None,
            activate=activate,
        )

    def paint_ui_library_store_inspect(
        self,
        *,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import inspect_ui_library_store

        return inspect_ui_library_store(store_root=store_root or None)

    def paint_ui_library_asset_search(
        self,
        *,
        query: str = "",
        kind: str = "",
        library_id: str = "",
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_assets import search_ui_library_assets

        return search_ui_library_assets(
            query=query,
            kind=kind,
            library_id=library_id,
            store_root=store_root or None,
        )

    def paint_ui_library_asset_insert(
        self,
        *,
        library_id: str,
        asset_id: str,
        kind: str,
        version: int = 0,
        property_path: str = "",
        x: float = 64.0,
        y: float = 64.0,
        store_root: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_library_assets import insert_ui_library_asset

        document, report = insert_ui_library_asset(
            dialog._painter_ui_document,
            library_id=library_id,
            asset_id=asset_id,
            kind=kind,
            version=version,
            property_path=property_path,
            x=x,
            y=y,
            store_root=store_root or None,
        )
        dialog._push_undo_state("Insert UI library asset")
        state = self._paint_ui_commit(
            dialog,
            "Insert UI library asset",
            document,
        )
        return {**state, "library_asset": report}

    def paint_ui_library_component_insert(
        self,
        *,
        library_id: str,
        component_id: str,
        version: int = 0,
        artboard_id: str = "",
        x: float = 64.0,
        y: float = 64.0,
        store_root: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_library_import import insert_ui_library_component

        document, report = insert_ui_library_component(
            dialog._painter_ui_document,
            library_id=library_id,
            component_id=component_id,
            version=version,
            artboard_id=artboard_id,
            x=x,
            y=y,
            store_root=store_root or None,
        )
        dialog._push_undo_state("Insert library component")
        state = self._paint_ui_commit(
            dialog,
            "Insert library component",
            document,
        )
        return {**state, "library_component": report}

    def paint_ui_library_update_inspect(
        self,
        *,
        candidate_path: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import compare_ui_library_update

        return compare_ui_library_update(
            candidate_path,
            store_root=store_root or None,
        )

    def paint_ui_library_update_apply(
        self,
        *,
        candidate_path: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import install_ui_library_package

        return install_ui_library_package(
            candidate_path,
            store_root=store_root or None,
            activate=True,
        )

    def paint_ui_library_update_defer(
        self,
        *,
        library_id: str,
        version: int,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import defer_ui_library_update

        return defer_ui_library_update(
            library_id,
            version,
            store_root=store_root or None,
        )

    def paint_ui_library_rollback(
        self,
        *,
        library_id: str,
        store_root: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_library_store import rollback_ui_library

        return rollback_ui_library(
            library_id,
            store_root=store_root or None,
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

    def paint_ui_prototype_authoring_inspect(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import (
            inspect_ui_prototype_authoring,
        )

        return inspect_ui_prototype_authoring(
            dialog._painter_ui_document,
            object_id=object_id,
        )

    def paint_ui_prototype_flow_add(
        self,
        *,
        name: str,
        artboard_id: str,
        start_object_id: str = "",
        device_preset: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import add_ui_prototype_flow

        document, row = add_ui_prototype_flow(
            dialog._painter_ui_document,
            name=name,
            artboard_id=artboard_id,
            start_object_id=start_object_id,
            device_preset=device_preset,
            description=description,
        )
        dialog._push_undo_state("Add prototype flow")
        result = self._paint_ui_commit(dialog, "Add prototype flow", document)
        result["flow"] = row
        return result

    def paint_ui_prototype_flow_update(
        self,
        *,
        flow_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import update_ui_prototype_flow

        document, row = update_ui_prototype_flow(
            dialog._painter_ui_document,
            flow_id,
            changes,
        )
        dialog._push_undo_state("Update prototype flow")
        result = self._paint_ui_commit(dialog, "Update prototype flow", document)
        result["flow"] = row
        return result

    def paint_ui_prototype_flow_remove(
        self,
        *,
        flow_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import remove_ui_prototype_flow

        document, row = remove_ui_prototype_flow(
            dialog._painter_ui_document,
            flow_id,
        )
        dialog._push_undo_state("Remove prototype flow")
        result = self._paint_ui_commit(dialog, "Remove prototype flow", document)
        result["removed_flow"] = row
        return result

    def paint_ui_prototype_flow_activate(
        self,
        *,
        flow_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import (
            set_active_ui_prototype_flow,
        )

        document, row = set_active_ui_prototype_flow(
            dialog._painter_ui_document,
            flow_id,
        )
        dialog._push_undo_state("Set active prototype flow")
        result = self._paint_ui_commit(
            dialog,
            "Set active prototype flow",
            document,
        )
        result["flow"] = row
        return result

    def paint_ui_prototype_transition_set(
        self,
        *,
        interaction_id: str,
        transition: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import (
            set_ui_prototype_transition,
        )

        document, row = set_ui_prototype_transition(
            dialog._painter_ui_document,
            interaction_id,
            transition,
        )
        dialog._push_undo_state("Set prototype transition")
        result = self._paint_ui_commit(
            dialog,
            "Set prototype transition",
            document,
        )
        result["interaction"] = row
        return result

    def paint_ui_prototype_connection_reorder(
        self,
        *,
        interaction_id: str,
        direction: int,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_prototype_authoring import (
            reorder_ui_prototype_interaction,
        )

        document, reorder = reorder_ui_prototype_interaction(
            dialog._painter_ui_document,
            interaction_id,
            direction,
        )
        dialog._push_undo_state("Reorder prototype connection")
        result = self._paint_ui_commit(
            dialog,
            "Reorder prototype connection",
            document,
        )
        result["reorder"] = reorder
        return result

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

    def paint_ui_umg_widget_view_set(
        self,
        *,
        visible: bool,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._set_painter_umg_widget_view_enabled(bool(visible))
        view = getattr(dialog, "_painter_umg_widget_view", None)
        is_visible = bool(view is not None and view.isVisible())
        return {
            "visible": is_visible,
            "workspace_mode": str(
                getattr(dialog, "_canvas_workspace_mode", "paint")
            ),
            "report": (
                view.report()
                if is_visible and hasattr(view, "report")
                else {}
            ),
        }

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

    def paint_ui_ai_prototype_plan(self, *, prompt: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ai_prototype import plan_ui_prototype_build

        return plan_ui_prototype_build(
            dialog._painter_ui_document,
            prompt=prompt,
        )

    def paint_ui_ai_prototype_apply(
        self,
        *,
        plan: dict[str, Any],
        selected_operation_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ai_prototype import apply_ui_prototype_build

        document, report = apply_ui_prototype_build(
            dialog._painter_ui_document,
            plan,
            selected_operation_ids=selected_operation_ids,
        )
        dialog._push_undo_state("Apply AI prototype build")
        self._paint_ui_commit(dialog, "Apply AI prototype build", document)
        return {**dialog.painter_action_state(), "ai_prototype_apply": report}

    def paint_ui_advanced_delivery_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_advanced_delivery import (
            inspect_advanced_ui_delivery,
        )

        return inspect_advanced_ui_delivery(dialog._painter_ui_document)

    def paint_ui_web_preflight(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_web_delivery import preflight_ui_web

        return preflight_ui_web(dialog._painter_ui_document)

    def paint_ui_web_package(self, *, output_dir: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_web_delivery import package_ui_web

        return package_ui_web(
            dialog._painter_ui_document,
            output_dir,
        )

    def paint_ui_ppt_inspect(
        self,
        *,
        scope: str = "active_artboard",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_ppt_bridge import inspect_painter_ui_ppt

        return inspect_painter_ui_ppt(
            dialog._painter_ui_document,
            scope=scope,
        )

    def paint_ui_ppt_send(
        self,
        *,
        scope: str = "active_artboard",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        method = getattr(dialog, "_send_painter_ui_to_ppt", None)
        if not callable(method):
            raise RuntimeError("Painter PPT bridge is unavailable")
        return dict(method(scope=scope) or {})

    def paint_ui_conversion_inspect(
        self,
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_mode_conversion import (
            inspect_painter_ui_conversion,
        )

        return inspect_painter_ui_conversion(
            dialog._painter_ui_document,
            object_ids=object_ids,
        )

    def paint_ui_convert_to_paint(
        self,
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dict(
            dialog._convert_painter_ui_selection_to_paint(
                object_ids=object_ids,
            )
            or {}
        )

    def paint_ui_convert_to_vector(
        self,
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dict(
            dialog._convert_painter_ui_selection_to_vector(
                object_ids=object_ids,
            )
            or {}
        )

    def paint_ui_component_library_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_component_library import inspect_ui_component_library

        return inspect_ui_component_library(
            getattr(dialog, "_painter_ui_document", None)
        )

    def paint_ui_component_set_inspect(
        self,
        *,
        component_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import inspect_ui_component_set

        return inspect_ui_component_set(
            dialog._painter_ui_document,
            component_id=str(component_id),
        )

    def paint_ui_component_playground_inspect(
        self,
        *,
        component_id: str,
        property_values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_component_playground import (
            build_ui_component_playground,
        )

        _preview, report = build_ui_component_playground(
            getattr(dialog, "_painter_ui_document", None),
            component_id=str(component_id),
            property_values=dict(property_values or {}),
        )
        return report

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
        presentation = dialog._set_painter_ui_inspector_presentation(mode)
        state = dialog.painter_action_state()
        state["inspector_presentation"] = presentation
        return state

    def paint_ui_navigator_presentation(
        self,
        *,
        mode: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        presentation = dialog._set_painter_ui_navigator_presentation(mode)
        state = dialog.painter_action_state()
        state["navigator_presentation"] = presentation
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

    def paint_ui_quick_action_search(
        self,
        *,
        query: str = "",
        limit: int = 30,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_quick_actions import (
            search_painter_ui_quick_actions,
        )

        return search_painter_ui_quick_actions(
            dialog._painter_ui_document,
            query,
            limit=limit,
        )

    def paint_ui_image_place(
        self,
        *,
        source_path: str,
        artboard_id: str = "",
        parent_id: str = "",
        x: float | None = None,
        y: float | None = None,
        width: float | None = None,
        height: float | None = None,
        image_fit: str = "fit",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_image_assets import place_ui_image

        document, _row, report = place_ui_image(
            dialog._painter_ui_document,
            source_path,
            artboard_id=artboard_id,
            parent_id=parent_id,
            x=x,
            y=y,
            width=width,
            height=height,
            image_fit=image_fit,
        )
        dialog._push_undo_state("Place UI image")
        result = self._paint_ui_commit(
            dialog,
            "Place UI image",
            document,
        )
        result["image_place"] = report
        return result

    def paint_ui_image_fill_set(
        self,
        *,
        source_path: str,
        object_id: str = "",
        image_fit: str = "fill",
        focal_x: float = 0.5,
        focal_y: float = 0.5,
        tile_scale: float = 1.0,
        restore_original_size: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_image_assets import set_ui_image_fill

        target_id = str(
            object_id
            or dialog._painter_ui_document["selection"]["object_id"]
            or ""
        )
        if not target_id:
            raise ValueError(
                "paint.ui.image.fill.set requires object_id or a selection"
            )
        document, _row, report = set_ui_image_fill(
            dialog._painter_ui_document,
            target_id,
            source_path,
            image_fit=image_fit,
            focal_x=focal_x,
            focal_y=focal_y,
            tile_scale=tile_scale,
            restore_original_size=restore_original_size,
        )
        dialog._push_undo_state("Set UI image fill")
        result = self._paint_ui_commit(
            dialog,
            "Set UI image fill",
            document,
        )
        result["image_fill"] = report
        return result

    def paint_ui_layout_diagnostics(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_diagnostics import diagnose_ui_layout

        return diagnose_ui_layout(dialog._painter_ui_document)

    def paint_ui_layout_stress_preview(
        self,
        *,
        preset: str,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        report = dialog._set_painter_ui_stress_preview(
            str(object_id or ""),
            str(preset or "none"),
        )
        return {
            "schema": "tigerstudio.painter.ui.stress_preview.action.v1",
            "stress_preview": report,
            "document_revision": int(
                dialog._painter_ui_document["revision"]
            ),
            "undo_depth": len(dialog._undo_stack),
        }

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

    def paint_ui_page_add(
        self,
        *,
        name: str = "",
        width: int = 1440,
        height: int = 900,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import add_ui_page

        document, _row = add_ui_page(
            dialog._painter_ui_document,
            name=name,
            width=width,
            height=height,
        )
        dialog._push_undo_state("Add UI page")
        return self._paint_ui_commit(dialog, "Add UI page", document)

    def paint_ui_page_update(
        self,
        *,
        page_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import update_ui_page

        document, _row = update_ui_page(
            dialog._painter_ui_document,
            page_id,
            changes,
        )
        dialog._push_undo_state("Update UI page")
        return self._paint_ui_commit(dialog, "Update UI page", document)

    def paint_ui_page_activate(self, *, page_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import set_active_ui_page

        document = set_active_ui_page(
            dialog._painter_ui_document,
            page_id,
        )
        if document == dialog._painter_ui_document:
            return dialog.painter_action_state()
        dialog._push_undo_state("Activate UI page")
        return self._paint_ui_commit(dialog, "Activate UI page", document)

    def paint_ui_page_remove(self, *, page_id: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_document import remove_ui_page

        document, _result = remove_ui_page(
            dialog._painter_ui_document,
            page_id,
        )
        dialog._push_undo_state("Remove UI page")
        return self._paint_ui_commit(dialog, "Remove UI page", document)

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
        layout_grids: list[dict[str, Any]] | None = None,
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
        if layout_grids is not None:
            changes["layout_grids"] = [
                dict(item) for item in layout_grids if isinstance(item, dict)
            ]
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

    def paint_ui_layout_grid_style_add(
        self,
        *,
        name: str,
        layout_grids: list[dict[str, Any]],
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_grid_styles import add_ui_layout_grid_style

        document, style = add_ui_layout_grid_style(
            dialog._painter_ui_document,
            name=name,
            layout_grids=layout_grids,
            description=description,
        )
        dialog._push_undo_state("Add UI layout-grid style")
        result = self._paint_ui_commit(dialog, "Add UI layout-grid style", document)
        result["layout_grid_style"] = style
        return result

    def paint_ui_layout_grid_style_update(
        self,
        *,
        style_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_grid_styles import update_ui_layout_grid_style

        document, style = update_ui_layout_grid_style(
            dialog._painter_ui_document,
            style_id,
            changes,
        )
        dialog._push_undo_state("Update UI layout-grid style")
        result = self._paint_ui_commit(
            dialog,
            "Update UI layout-grid style",
            document,
        )
        result["layout_grid_style"] = style
        return result

    def paint_ui_layout_grid_style_apply(
        self,
        *,
        artboard_id: str,
        style_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_grid_styles import apply_ui_layout_grid_style

        document, artboard = apply_ui_layout_grid_style(
            dialog._painter_ui_document,
            artboard_id=artboard_id,
            style_id=style_id,
        )
        dialog._push_undo_state("Apply UI layout-grid style")
        result = self._paint_ui_commit(
            dialog,
            "Apply UI layout-grid style",
            document,
        )
        result["artboard"] = artboard
        return result

    def paint_ui_layout_grid_style_remove(
        self,
        *,
        style_id: str,
        detach_references: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_layout_grid_styles import remove_ui_layout_grid_style

        document, removed = remove_ui_layout_grid_style(
            dialog._painter_ui_document,
            style_id,
            detach_references=detach_references,
        )
        dialog._push_undo_state("Remove UI layout-grid style")
        result = self._paint_ui_commit(
            dialog,
            "Remove UI layout-grid style",
            document,
        )
        result["removed_layout_grid_style"] = removed
        return result

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

    def _paint_ui_vector_target(self, dialog, object_id: str = ""):
        selected = str(
            object_id
            or dialog._painter_ui_document["selection"]["object_id"]
            or ""
        )
        row = next(
            (
                item
                for item in dialog._painter_ui_document["objects"]
                if item["id"] == selected
            ),
            None,
        )
        if row is None or row["kind"] != "path":
            raise ValueError(
                "Painter UI vector editing requires a selected path object"
            )
        from app.painter_ui_vector_network import (
            create_vector_network,
            normalize_vector_network,
        )

        content = copy.deepcopy(row["content"])
        network = content.get("vector_network")
        if not isinstance(network, dict):
            network = create_vector_network()
        return selected, content, normalize_vector_network(network)

    def _paint_ui_vector_commit(
        self,
        dialog,
        *,
        object_id: str,
        content: dict[str, Any],
        network: dict[str, Any],
        label: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.painter_ui_document import update_ui_object

        content["vector_network"] = network
        document, _row = update_ui_object(
            dialog._painter_ui_document,
            object_id,
            {"content": content},
        )
        dialog._push_undo_state(label)
        state = self._paint_ui_commit(dialog, label, document)
        return {
            **state,
            "vector_edit": {
                "object_id": object_id,
                "network": copy.deepcopy(
                    next(
                        row["content"]["vector_network"]
                        for row in document["objects"]
                        if row["id"] == object_id
                    )
                ),
                **dict(result or {}),
            },
        }

    def paint_ui_vector_node_add(
        self,
        *,
        object_id: str = "",
        x: float,
        y: float,
        after_node_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import add_vector_node

        network, node_id = add_vector_node(
            network,
            x=x,
            y=y,
            after_node_id=after_node_id,
        )
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Add UI vector node",
            result={"node_id": node_id},
        )

    def paint_ui_vector_node_update(
        self,
        *,
        node_id: str,
        changes: dict[str, Any],
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import update_vector_node

        network = update_vector_node(network, node_id, changes)
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Update UI vector node",
            result={"node_id": str(node_id)},
        )

    def paint_ui_vector_node_remove(
        self,
        *,
        node_id: str,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import remove_vector_node

        network = remove_vector_node(network, node_id)
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Remove UI vector node",
            result={"node_id": str(node_id)},
        )

    def paint_ui_vector_segment_set(
        self,
        *,
        segment_id: str,
        kind: str,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import set_vector_segment_kind

        network = set_vector_segment_kind(network, segment_id, kind)
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Set UI vector segment",
            result={"segment_id": str(segment_id), "kind": str(kind)},
        )

    def paint_ui_vector_segment_split(
        self,
        *,
        segment_id: str,
        position: float = 0.5,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import split_vector_segment

        network, node_id = split_vector_segment(
            network,
            segment_id,
            position=position,
        )
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Split UI vector segment",
            result={"segment_id": str(segment_id), "node_id": node_id},
        )

    def paint_ui_vector_path_closed_set(
        self,
        *,
        closed: bool,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import set_vector_path_closed

        network = set_vector_path_closed(network, closed)
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Close UI vector path" if closed else "Open UI vector path",
            result={"closed": bool(closed)},
        )

    def paint_ui_vector_path_join(
        self,
        *,
        start_node_id: str,
        end_node_id: str,
        kind: str = "line",
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import join_vector_nodes

        network = join_vector_nodes(
            network,
            start_node_id,
            end_node_id,
            kind=kind,
        )
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Join UI vector nodes",
            result={
                "start_node_id": str(start_node_id),
                "end_node_id": str(end_node_id),
            },
        )

    def paint_ui_vector_path_reverse(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import reverse_vector_path

        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=reverse_vector_path(network),
            label="Reverse UI vector path",
        )

    def paint_ui_vector_path_simplify(
        self,
        *,
        tolerance: float = 0.0025,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        from app.painter_ui_vector_network import simplify_vector_path

        network, report = simplify_vector_path(
            network,
            tolerance=tolerance,
        )
        return self._paint_ui_vector_commit(
            dialog,
            object_id=target,
            content=content,
            network=network,
            label="Simplify UI vector path",
            result={"simplify": report},
        )

    def paint_ui_vector_path_outline(
        self,
        *,
        stroke_width: float = 0.0,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        target, content, network = self._paint_ui_vector_target(
            dialog, object_id
        )
        row = next(
            item
            for item in dialog._painter_ui_document["objects"]
            if item["id"] == target
        )
        style = copy.deepcopy(dict(row.get("style") or {}))
        effective_width = float(
            stroke_width or style.get("stroke_width") or 0.0
        )
        if effective_width <= 0.0:
            raise ValueError("Outline stroke requires a visible stroke width")
        from app.painter_ui_document import update_ui_object
        from app.painter_ui_vector_network import (
            normalize_vector_content,
            outline_vector_path,
        )

        network, report = outline_vector_path(
            network,
            width=float(row["width"]),
            height=float(row["height"]),
            stroke_width=effective_width,
            cap=str(style.get("stroke_cap") or "round"),
            join=str(style.get("stroke_join") or "round"),
        )
        content["vector_network"] = network
        stroke_color = str(style.get("stroke") or "#000000")
        style.update(
            {
                "fill": stroke_color,
                "stroke": "#00000000",
                "stroke_width": 0.0,
            }
        )
        changes = {
            "x": float(row["x"]) + float(report["x"]),
            "y": float(row["y"]) + float(report["y"]),
            "width": float(report["width"]),
            "height": float(report["height"]),
            "style": style,
            "content": normalize_vector_content(content),
        }
        document, _updated = update_ui_object(
            dialog._painter_ui_document,
            target,
            changes,
        )
        label = "Outline UI vector stroke"
        dialog._push_undo_state(label)
        state = self._paint_ui_commit(dialog, label, document)
        return {
            **state,
            "vector_edit": {
                "object_id": target,
                "network": copy.deepcopy(network),
                "outline": report,
            },
        }

    def paint_ui_object_properties_copy(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_property_clipboard import copy_ui_object_payload

        selected = str(
            object_id
            or dialog._painter_ui_document["selection"]["object_id"]
            or ""
        )
        if not selected:
            raise ValueError("Select a Painter UI object to copy properties")
        payload = copy_ui_object_payload(
            dialog._painter_ui_document,
            selected,
        )
        dialog._painter_ui_property_clipboard = payload
        return {
            "schema": "tigerstudio.painter.ui.property_copy.v1",
            "object_id": selected,
            "clipboard": payload,
        }

    def paint_ui_object_properties_paste(
        self,
        *,
        target_object_ids: list[str] | None = None,
        clipboard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_property_clipboard import paste_ui_object_properties

        targets = list(
            target_object_ids
            or dialog._painter_ui_document["selection"]["object_ids"]
        )
        if not targets:
            raise ValueError("Select Painter UI objects to paste properties")
        payload = clipboard or getattr(
            dialog,
            "_painter_ui_property_clipboard",
            None,
        )
        if not isinstance(payload, dict):
            raise ValueError("Painter UI property clipboard is empty")
        document, report = paste_ui_object_properties(
            dialog._painter_ui_document,
            targets,
            payload,
        )
        if not report["target_object_ids"]:
            return {
                "changed": False,
                "clipboard_result": report,
                "ui_design": dialog.painter_action_state()["ui_design"],
            }
        dialog._push_undo_state("Paste UI object properties")
        result = self._paint_ui_commit(
            dialog,
            "Paste UI object properties",
            document,
        )
        result["clipboard_result"] = report
        return result

    def paint_ui_object_paste_replace(
        self,
        *,
        target_object_ids: list[str] | None = None,
        clipboard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_property_clipboard import paste_replace_ui_objects

        targets = list(
            target_object_ids
            or dialog._painter_ui_document["selection"]["object_ids"]
        )
        if not targets:
            raise ValueError("Select Painter UI objects to replace")
        payload = clipboard or getattr(
            dialog,
            "_painter_ui_property_clipboard",
            None,
        )
        if not isinstance(payload, dict):
            raise ValueError("Painter UI object clipboard is empty")
        document, report = paste_replace_ui_objects(
            dialog._painter_ui_document,
            targets,
            payload,
        )
        if not report["target_object_ids"]:
            return {
                "changed": False,
                "clipboard_result": report,
                "ui_design": dialog.painter_action_state()["ui_design"],
            }
        dialog._push_undo_state("Paste replace UI objects")
        result = self._paint_ui_commit(
            dialog,
            "Paste replace UI objects",
            document,
        )
        result["clipboard_result"] = report
        return result

    def paint_ui_object_scale(
        self,
        *,
        object_ids: list[str] | None = None,
        scale_x: float = 1.0,
        scale_y: float | None = None,
        origin: str = "center",
        scale_visuals: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_object_scale import scale_ui_objects

        targets = list(
            object_ids
            or dialog._painter_ui_document["selection"]["object_ids"]
        )
        document, report = scale_ui_objects(
            dialog._painter_ui_document,
            targets,
            scale_x=scale_x,
            scale_y=scale_y,
            origin=origin,
            scale_visuals=scale_visuals,
        )
        if not report["object_ids"]:
            return {
                "changed": False,
                "scale_result": report,
                "ui_design": dialog.painter_action_state()["ui_design"],
            }
        dialog._push_undo_state("Scale UI objects")
        result = self._paint_ui_commit(dialog, "Scale UI objects", document)
        result["scale_result"] = report
        return result

    def paint_ui_text_content_set(
        self,
        *,
        object_id: str,
        text: str,
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
        if row["kind"] != "text":
            raise ValueError("Inline text content requires a text object")
        document, updated = update_ui_object(
            dialog._painter_ui_document,
            str(object_id),
            {
                "content": {
                    **dict(row.get("content") or {}),
                    "text": str(text),
                }
            },
        )
        dialog._push_undo_state("Edit UI text")
        result = self._paint_ui_commit(dialog, "Edit UI text", document)
        result["text_object"] = {
            "object_id": str(updated["id"]),
            "text": str(updated["content"].get("text") or ""),
        }
        return result

    def paint_ui_typography_variable_axis_set(
        self,
        *,
        object_id: str,
        axis: str,
        value: float,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_typography import set_ui_variable_font_axis

        document, updated = set_ui_variable_font_axis(
            dialog._painter_ui_document,
            object_id,
            axis,
            value,
        )
        dialog._push_undo_state("Set variable-font axis")
        result = self._paint_ui_commit(
            dialog,
            "Set variable-font axis",
            document,
        )
        result["font_axes"] = dict(updated["style"].get("font_axes") or {})
        return result

    def paint_ui_typography_variable_axis_reset(
        self,
        *,
        object_id: str,
        axis: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_typography import reset_ui_variable_font_axis

        document, updated = reset_ui_variable_font_axis(
            dialog._painter_ui_document,
            object_id,
            axis,
        )
        dialog._push_undo_state("Reset variable-font axis")
        result = self._paint_ui_commit(
            dialog,
            "Reset variable-font axis",
            document,
        )
        result["font_axes"] = dict(updated["style"].get("font_axes") or {})
        return result

    def paint_ui_property_batch_set(
        self,
        *,
        changes_by_id: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_batch_mutation import apply_ui_object_batch

        document, changed_ids = apply_ui_object_batch(
            dialog._painter_ui_document,
            changes_by_id,
        )
        if not changed_ids:
            return {
                "changed": False,
                "updated_object_ids": [],
                "ui_design": dialog.painter_action_state()["ui_design"],
            }
        dialog._push_undo_state("Edit UI objects")
        result = self._paint_ui_commit(
            dialog,
            "Edit UI objects",
            document,
        )
        result["updated_object_ids"] = changed_ids
        return result

    def paint_ui_property_inspect(
        self,
        *,
        object_id: str,
        property_path: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_property_contract import inspect_ui_property

        return inspect_ui_property(
            dialog._painter_ui_document,
            str(object_id),
            str(property_path),
        )

    def paint_ui_property_reset(
        self,
        *,
        object_id: str,
        property_path: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_property_contract import reset_ui_property

        document, report = reset_ui_property(
            dialog._painter_ui_document,
            str(object_id),
            str(property_path),
        )
        if report["is_default"] and document == dialog._painter_ui_document:
            return {
                "changed": False,
                "property": report,
                "ui_design": dialog.painter_action_state()["ui_design"],
            }
        dialog._push_undo_state("Reset UI property")
        result = self._paint_ui_commit(
            dialog,
            "Reset UI property",
            document,
        )
        result["property"] = report
        return result

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

    def paint_ui_selection_similar_inspect(
        self,
        *,
        criterion: str = "kind",
        scope: str = "active_artboard",
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_select_similar import inspect_ui_select_similar

        return inspect_ui_select_similar(
            dialog._painter_ui_document,
            criterion=criterion,
            scope=scope,
            object_id=object_id,
        )

    def paint_ui_selection_similar_select(
        self,
        *,
        criterion: str = "kind",
        scope: str = "active_artboard",
        object_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        report = dialog._select_similar_painter_ui_objects(
            criterion=criterion,
            scope=scope,
            object_id=object_id,
        )
        state = dialog.painter_action_state()
        state["select_similar"] = report
        return state

    def paint_ui_find_replace_inspect(
        self,
        *,
        find: str,
        replacement: str = "",
        categories: list[str] | None = None,
        case_sensitive: bool = False,
        whole_value: bool = False,
        selected_match_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        del selected_match_ids
        dialog = self._paint_dialog_owner()
        from app.painter_ui_find_replace import inspect_ui_find_replace

        return inspect_ui_find_replace(
            dialog._painter_ui_document,
            find=find,
            replacement=replacement,
            categories=categories,
            case_sensitive=case_sensitive,
            whole_value=whole_value,
        )

    def paint_ui_find_replace_apply(
        self,
        *,
        find: str,
        replacement: str = "",
        categories: list[str] | None = None,
        case_sensitive: bool = False,
        whole_value: bool = False,
        selected_match_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_find_replace import apply_ui_find_replace

        document, report = apply_ui_find_replace(
            dialog._painter_ui_document,
            find=find,
            replacement=replacement,
            categories=categories,
            case_sensitive=case_sensitive,
            whole_value=whole_value,
            selected_match_ids=selected_match_ids,
        )
        if int(report.get("applied_count") or 0):
            dialog._push_undo_state("Find / Replace")
            state = self._paint_ui_commit(
                dialog,
                "Find / Replace",
                document,
            )
        else:
            state = dialog.painter_action_state()
        state["find_replace"] = report
        return state

    def paint_ui_batch_rename_inspect(
        self,
        *,
        object_ids: list[str] | None = None,
        find: str = "",
        replacement: str = "",
        prefix: str = "",
        suffix: str = "",
        numbering: bool = False,
        number_start: int = 1,
        number_padding: int = 0,
        number_separator: str = " ",
        case_sensitive: bool = False,
        selected_match_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        del selected_match_ids
        dialog = self._paint_dialog_owner()
        from app.painter_ui_batch_rename import inspect_ui_batch_rename

        return inspect_ui_batch_rename(
            dialog._painter_ui_document,
            object_ids=object_ids,
            find=find,
            replacement=replacement,
            prefix=prefix,
            suffix=suffix,
            numbering=numbering,
            number_start=number_start,
            number_padding=number_padding,
            number_separator=number_separator,
            case_sensitive=case_sensitive,
        )

    def paint_ui_batch_rename_apply(
        self,
        *,
        object_ids: list[str] | None = None,
        find: str = "",
        replacement: str = "",
        prefix: str = "",
        suffix: str = "",
        numbering: bool = False,
        number_start: int = 1,
        number_padding: int = 0,
        number_separator: str = " ",
        case_sensitive: bool = False,
        selected_match_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_batch_rename import apply_ui_batch_rename

        document, report = apply_ui_batch_rename(
            dialog._painter_ui_document,
            object_ids=object_ids,
            find=find,
            replacement=replacement,
            prefix=prefix,
            suffix=suffix,
            numbering=numbering,
            number_start=number_start,
            number_padding=number_padding,
            number_separator=number_separator,
            case_sensitive=case_sensitive,
            selected_match_ids=selected_match_ids,
        )
        if int(report.get("applied_count") or 0):
            dialog._push_undo_state("Batch Rename")
            state = self._paint_ui_commit(
                dialog,
                "Batch Rename",
                document,
            )
        else:
            state = dialog.painter_action_state()
        state["batch_rename"] = report
        return state

    def paint_ui_shortcut_inspect(
        self,
        *,
        query: str = "",
        conflicts_only: bool = False,
        active_scope: str = "ui_design",
    ) -> dict[str, Any]:
        from app.painter_ui_shortcut_map import inspect_painter_shortcuts

        return inspect_painter_shortcuts(
            query=query,
            conflicts_only=conflicts_only,
            active_scope=active_scope,
        )

    def paint_ui_action_parity_inspect(self) -> dict[str, Any]:
        from app.actions.registry import ActionRegistry
        from app.painter_ui_action_parity import (
            inspect_painter_ui_action_parity,
        )

        actions = ActionRegistry(owner=None).list_actions()
        return inspect_painter_ui_action_parity(actions)

    def paint_ui_locale_audit_inspect(self) -> dict[str, Any]:
        from app.painter_ui_locale_audit import inspect_painter_ui_locales

        return inspect_painter_ui_locales()

    def paint_ui_focus_audit_inspect(self) -> dict[str, Any]:
        from app.painter_ui_focus_audit import inspect_painter_ui_focus

        return inspect_painter_ui_focus(self._paint_dialog_owner())

    def paint_ui_release_corpus_run(
        self,
        *,
        output_dir: str = "",
    ) -> dict[str, Any]:
        from pathlib import Path

        from app.painter_ui_release_corpus import (
            run_painter_ui_release_corpus,
        )

        target = (
            Path(output_dir).expanduser()
            if str(output_dir).strip()
            else (
                Path(__file__).resolve().parents[2]
                / "debugCapture"
                / "painter_ui_designer"
                / "release_corpus"
            )
        )
        return run_painter_ui_release_corpus(target)

    def paint_ui_performance_budget_inspect(self) -> dict[str, Any]:
        from app.painter_ui_performance_budget import (
            inspect_painter_ui_performance_budget,
        )

        dialog = self._paint_dialog_owner()
        return inspect_painter_ui_performance_budget(
            getattr(dialog, "_painter_ui_document", None)
        )

    def paint_ui_runtime_performance_run(
        self,
        *,
        object_count: int = 1000,
        iterations: int = 3,
    ) -> dict[str, Any]:
        from app.painter_ui_runtime_performance import (
            run_painter_ui_runtime_performance,
        )

        return run_painter_ui_runtime_performance(
            object_count=object_count,
            iterations=iterations,
        )

    def paint_ui_recovery_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        rows = dialog._painter_recovery_rows()
        return {
            "schema": "tigerstudio.painter.recovery.inspect.v1",
            "count": len(rows),
            "snapshots": rows,
        }

    def paint_ui_recovery_create(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dialog._schedule_painter_recovery_snapshot(force=True)

    def paint_ui_recovery_restore(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        row = next(
            (
                item
                for item in dialog._painter_recovery_rows()
                if str(item.get("session_id") or "") == str(session_id)
            ),
            None,
        )
        if row is None:
            raise ValueError(f"Painter recovery snapshot not found: {session_id}")
        return dialog._restore_painter_recovery_snapshot(row)

    def paint_ui_recovery_discard(
        self,
        *,
        session_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        row = next(
            (
                item
                for item in dialog._painter_recovery_rows()
                if str(item.get("session_id") or "") == str(session_id)
            ),
            {"session_id": str(session_id)},
        )
        return dialog._discard_painter_recovery_snapshot(row)

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

    def paint_ui_selection_tidy(
        self,
        *,
        axis: str = "auto",
        gap: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_batch_mutation import apply_ui_object_batch
        from app.painter_ui_smart_selection import plan_ui_selection_tidy

        report = plan_ui_selection_tidy(
            dialog._painter_ui_document,
            axis=str(axis or "auto"),
            gap=gap,
        )
        if not report["eligible"]:
            raise ValueError(str(report["reason"]))
        document, changed_ids = apply_ui_object_batch(
            dialog._painter_ui_document,
            report["changes_by_id"],
        )
        if changed_ids:
            dialog._push_undo_state("Tidy UI selection")
            result = self._paint_ui_commit(
                dialog,
                "Tidy UI selection",
                document,
            )
        else:
            result = dialog.painter_action_state()
        result["tidy"] = {
            key: value
            for key, value in report.items()
            if key != "changes_by_id"
        }
        result["updated_object_ids"] = changed_ids
        return result

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

    def paint_ui_component_instance_swap_preferred_set(
        self,
        *,
        component_id: str,
        property_name: str,
        preferred_component_ids: list[str],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            set_ui_component_instance_swap_preferred_values,
        )

        document, _definition = (
            set_ui_component_instance_swap_preferred_values(
                dialog._painter_ui_document,
                component_id=str(component_id),
                property_name=str(property_name),
                preferred_component_ids=list(preferred_component_ids or []),
            )
        )
        dialog._push_undo_state("Set preferred Instance Swap values")
        return self._paint_ui_commit(
            dialog,
            "Set preferred Instance Swap values",
            document,
        )

    def paint_ui_component_slot_define(
        self,
        *,
        component_id: str,
        source_object_id: str,
        property_name: str,
        description: str = "",
        preferred_component_ids: list[str] | None = None,
        slot_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import define_ui_component_slot

        document, _definition = define_ui_component_slot(
            dialog._painter_ui_document,
            component_id=str(component_id),
            source_object_id=str(source_object_id),
            property_name=str(property_name),
            description=str(description),
            preferred_component_ids=list(preferred_component_ids or []),
            slot_settings=dict(slot_settings or {}),
        )
        dialog._push_undo_state("Define UI component Slot")
        return self._paint_ui_commit(dialog, "Define UI component Slot", document)

    def paint_ui_component_slot_inspect(
        self,
        *,
        instance_root_id: str,
        property_name: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import inspect_ui_component_instance_slot

        return inspect_ui_component_instance_slot(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            property_name=str(property_name),
        )

    def paint_ui_component_slot_insert(
        self,
        *,
        instance_root_id: str,
        property_name: str,
        object_id: str,
        index: int | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import insert_ui_object_into_component_slot

        document, _report = insert_ui_object_into_component_slot(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            property_name=str(property_name),
            object_id=str(object_id),
            index=index,
        )
        dialog._push_undo_state("Insert UI component Slot content")
        return self._paint_ui_commit(
            dialog, "Insert UI component Slot content", document
        )

    def paint_ui_component_slot_reset(
        self,
        *,
        instance_root_id: str,
        property_name: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import reset_ui_component_instance_slot

        document, _report = reset_ui_component_instance_slot(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            property_name=str(property_name),
        )
        dialog._push_undo_state("Reset UI component Slot")
        return self._paint_ui_commit(dialog, "Reset UI component Slot", document)

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
        variant_properties: dict[str, Any] | None = None,
        offset_x: float | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import create_ui_component_variant

        document, _variant = create_ui_component_variant(
            dialog._painter_ui_document,
            component_id=str(component_id),
            name=str(name or ""),
            variant_key=str(variant_key or ""),
            variant_properties=dict(variant_properties or {}),
            offset_x=offset_x,
        )
        dialog._push_undo_state("Create UI component variant")
        return self._paint_ui_commit(
            dialog,
            "Create UI component variant",
            document,
        )

    def paint_ui_component_variants_combine(
        self,
        *,
        component_ids: list[str],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import combine_ui_components_as_variants

        document, _report = combine_ui_components_as_variants(
            dialog._painter_ui_document,
            component_ids=list(component_ids or []),
        )
        dialog._push_undo_state("Combine UI components as variants")
        return self._paint_ui_commit(
            dialog, "Combine UI components as variants", document
        )

    def paint_ui_component_variant_property_define(
        self,
        *,
        component_id: str,
        property_name: str,
        values: list[str],
        default_value: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            define_ui_component_variant_property,
        )

        document, inspection = define_ui_component_variant_property(
            dialog._painter_ui_document,
            component_id=str(component_id),
            property_name=str(property_name),
            values=list(values or []),
            default_value=str(default_value or ""),
            description=str(description or ""),
        )
        dialog._push_undo_state("Define UI component Variant property")
        result = self._paint_ui_commit(
            dialog,
            "Define UI component Variant property",
            document,
        )
        result["component_set"] = inspection
        return result

    def paint_ui_component_variant_values_set(
        self,
        *,
        component_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            set_ui_component_variant_properties,
        )

        document, report = set_ui_component_variant_properties(
            dialog._painter_ui_document,
            component_id=str(component_id),
            properties=dict(properties or {}),
        )
        dialog._push_undo_state("Set UI component Variant values")
        result = self._paint_ui_commit(
            dialog,
            "Set UI component Variant values",
            document,
        )
        result["component_set"] = report["inspection"]
        return result

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

    def paint_ui_component_instance_variant_values_set(
        self,
        *,
        instance_root_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            switch_ui_component_instance_variant_values,
        )

        document, _result = switch_ui_component_instance_variant_values(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            properties=dict(properties or {}),
        )
        dialog._push_undo_state("Switch UI component Variant properties")
        return self._paint_ui_commit(
            dialog,
            "Switch UI component Variant properties",
            document,
        )

    def paint_ui_component_change_to_add(
        self,
        *,
        source_component_id: str,
        target_component_id: str,
        trigger: str = "click",
        transition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            add_ui_component_change_to_interaction,
        )

        document, _result = add_ui_component_change_to_interaction(
            dialog._painter_ui_document,
            source_component_id=str(source_component_id),
            target_component_id=str(target_component_id),
            trigger=str(trigger),
            transition=dict(transition or {}),
        )
        dialog._push_undo_state("Add UI component Change to")
        return self._paint_ui_commit(
            dialog,
            "Add UI component Change to",
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

    def paint_ui_component_override_reset(
        self,
        *,
        instance_root_id: str,
        object_id: str,
        property_path: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            reset_ui_component_instance_override,
        )

        document, report = reset_ui_component_instance_override(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
            object_id=str(object_id),
            property_path=str(property_path),
        )
        dialog._push_undo_state("Reset UI component override")
        result = self._paint_ui_commit(
            dialog,
            "Reset UI component override",
            document,
        )
        result["override_report"] = report
        return result

    def paint_ui_component_override_reset_all(
        self,
        *,
        instance_root_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_components import (
            reset_all_ui_component_instance_overrides,
        )

        document, report = reset_all_ui_component_instance_overrides(
            dialog._painter_ui_document,
            instance_root_id=str(instance_root_id),
        )
        dialog._push_undo_state("Reset all UI component overrides")
        result = self._paint_ui_commit(
            dialog,
            "Reset all UI component overrides",
            document,
        )
        result["override_report"] = report
        return result

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
        collection_id: str = "",
        variable_type: str = "",
        mode_values: dict[str, Any] | None = None,
        scope: list[str] | None = None,
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
            collection_id=collection_id,
            variable_type=variable_type,
            mode_values=mode_values,
            scope=scope,
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

    def paint_ui_style_library_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import inspect_ui_style_library

        return inspect_ui_style_library(dialog._painter_ui_document)

    def paint_ui_style_add(
        self,
        *,
        name: str,
        kind: str,
        properties: dict[str, Any] | None = None,
        token_bindings: dict[str, str] | None = None,
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import add_ui_style

        document, row = add_ui_style(
            dialog._painter_ui_document,
            name=name,
            kind=kind,
            properties=properties,
            token_bindings=token_bindings,
            description=description,
        )
        dialog._push_undo_state("Add UI style")
        result = self._paint_ui_commit(dialog, "Add UI style", document)
        result["style"] = row
        return result

    def paint_ui_style_update(
        self,
        *,
        style_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import update_ui_style

        document, row = update_ui_style(
            dialog._painter_ui_document,
            style_id,
            changes,
        )
        dialog._push_undo_state("Update UI style")
        result = self._paint_ui_commit(dialog, "Update UI style", document)
        result["style"] = row
        return result

    def paint_ui_style_remove(
        self,
        *,
        style_id: str,
        detach_references: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import remove_ui_style

        document, removed = remove_ui_style(
            dialog._painter_ui_document,
            style_id,
            detach_references=detach_references,
        )
        dialog._push_undo_state("Remove UI style")
        result = self._paint_ui_commit(dialog, "Remove UI style", document)
        result["removed"] = removed
        return result

    def paint_ui_style_apply(
        self,
        *,
        style_id: str,
        target_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import apply_ui_style

        document, target = apply_ui_style(
            dialog._painter_ui_document,
            target_id=target_id,
            style_id=style_id,
        )
        dialog._push_undo_state("Apply UI style")
        result = self._paint_ui_commit(dialog, "Apply UI style", document)
        result["target"] = target
        return result

    def paint_ui_style_unlink(
        self,
        *,
        kind: str,
        target_id: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_styles import unlink_ui_style

        document, detached = unlink_ui_style(
            dialog._painter_ui_document,
            target_id=target_id,
            kind=kind,
        )
        dialog._push_undo_state("Detach UI style")
        result = self._paint_ui_commit(dialog, "Detach UI style", document)
        result["detached"] = detached
        return result

    def paint_ui_variable_collection_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import inspect_ui_variable_collections

        return inspect_ui_variable_collections(dialog._painter_ui_document)

    def paint_ui_variable_collection_add(
        self,
        *,
        name: str,
        kind: str = "custom",
        description: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import add_ui_variable_collection

        document, row = add_ui_variable_collection(
            dialog._painter_ui_document,
            name=name,
            kind=kind,
            description=description,
        )
        dialog._push_undo_state("Add variable collection")
        result = self._paint_ui_commit(
            dialog,
            "Add variable collection",
            document,
        )
        result["variable_collection"] = row
        return result

    def paint_ui_variable_collection_update(
        self,
        *,
        collection_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import update_ui_variable_collection

        document, row = update_ui_variable_collection(
            dialog._painter_ui_document,
            collection_id,
            changes,
        )
        dialog._push_undo_state("Update variable collection")
        result = self._paint_ui_commit(
            dialog,
            "Update variable collection",
            document,
        )
        result["variable_collection"] = row
        return result

    def paint_ui_variable_collection_remove(
        self,
        *,
        collection_id: str,
        detach_tokens: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import remove_ui_variable_collection

        document, report = remove_ui_variable_collection(
            dialog._painter_ui_document,
            collection_id,
            detach_tokens=detach_tokens,
        )
        dialog._push_undo_state("Remove variable collection")
        result = self._paint_ui_commit(
            dialog,
            "Remove variable collection",
            document,
        )
        result["variable_collection_remove"] = report
        return result

    def paint_ui_variable_mode_add(
        self,
        *,
        collection_id: str,
        name: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import add_ui_variable_mode

        document, mode = add_ui_variable_mode(
            dialog._painter_ui_document,
            collection_id=collection_id,
            name=name,
        )
        dialog._push_undo_state("Add variable mode")
        result = self._paint_ui_commit(dialog, "Add variable mode", document)
        result["variable_mode"] = mode
        return result

    def paint_ui_variable_mode_update(
        self,
        *,
        collection_id: str,
        mode_id: str,
        name: str,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import update_ui_variable_mode

        document, mode = update_ui_variable_mode(
            dialog._painter_ui_document,
            collection_id=collection_id,
            mode_id=mode_id,
            name=name,
        )
        dialog._push_undo_state("Update variable mode")
        result = self._paint_ui_commit(
            dialog,
            "Update variable mode",
            document,
        )
        result["variable_mode"] = mode
        return result

    def paint_ui_variable_mode_remove(
        self,
        *,
        collection_id: str,
        mode_id: str,
        detach_values: bool = False,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import remove_ui_variable_mode

        document, report = remove_ui_variable_mode(
            dialog._painter_ui_document,
            collection_id=collection_id,
            mode_id=mode_id,
            detach_values=detach_values,
        )
        dialog._push_undo_state("Remove variable mode")
        result = self._paint_ui_commit(
            dialog,
            "Remove variable mode",
            document,
        )
        result["variable_mode_remove"] = report
        return result

    def paint_ui_variable_mode_set(
        self,
        *,
        collection_id: str,
        mode_id: str,
        artboard_id: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_variables import set_ui_variable_mode

        document, report = set_ui_variable_mode(
            dialog._painter_ui_document,
            artboard_id=(
                artboard_id or dialog._painter_ui_document["active_artboard_id"]
            ),
            collection_id=collection_id,
            mode_id=mode_id,
        )
        dialog._push_undo_state("Set variable mode")
        result = self._paint_ui_commit(dialog, "Set variable mode", document)
        result["variable_mode_set"] = report
        return result

    def paint_ui_token_suggest(
        self,
        *,
        object_id: str = "",
        property_path: str = "",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_ui_token_suggestion import suggest_ui_tokens

        return suggest_ui_tokens(
            dialog._painter_ui_document,
            object_id=str(object_id or ""),
            property_path=str(property_path or ""),
        )

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
        export_size = optional_paint_export_size(width, height)
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
            width=export_size[0] if export_size is not None else 0,
            height=export_size[1] if export_size is not None else 0,
        )

    def paint_document_exchange_preflight(
        self,
        *,
        format: str,
        bit_depth: int = 8,
        bake_unsupported: bool = False,
        color_mode: str = "RGB",
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dialog.painter_exchange_preflight(
            format_name=format, bit_depth=bit_depth,
            bake_unsupported=bake_unsupported, color_mode=color_mode,
        )

    def paint_document_export(
        self,
        *,
        path: str,
        format: str,
        include_background: bool = True,
        bit_depth: int = 8,
        bake_unsupported: bool = False,
        quality: int = 95,
        source_icc: str = "",
        output_icc: str = "",
        rendering_intent: int = 1,
    ) -> dict[str, Any]:
        resolved = validate_document_export_action(
            path=path,
            format_name=format,
            include_background=include_background,
            bit_depth=bit_depth,
            bake_unsupported=bake_unsupported,
            quality=quality,
            source_icc=source_icc,
            output_icc=output_icc,
            rendering_intent=rendering_intent,
        )
        dialog = self._paint_dialog_owner()
        return dialog.export_document_to_path(**resolved)

    def paint_document_import_psd(self, *, path: str) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        return dialog.import_psd_document_from_path(path)

    def paint_view_zoom(self, *, percent: int = 100) -> dict[str, Any]:
        resolved_percent = validate_action_integer_domain(
            percent,
            field="percent",
            minimum=PAINTER_ZOOM_MIN_PERCENT,
            maximum=PAINTER_ZOOM_MAX_PERCENT,
        )
        dialog = self._paint_dialog_owner()
        dialog._set_zoom_percent(resolved_percent)
        return dialog.painter_action_state()

    def paint_view_zoom_area(
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        x, y, width, height = validate_zoom_area_action(
            x=x,
            y=y,
            width=width,
            height=height,
        )
        dialog = self._paint_dialog_owner()
        dialog._handle_canvas_zoom_request(
            "zoom_area",
            x,
            y,
            width,
            height,
        )
        return dialog.painter_action_state()

    def paint_view_pan(
        self,
        *,
        x: object = PAINTER_ACTION_INPUT_UNSET,
        y: object = PAINTER_ACTION_INPUT_UNSET,
        dx: object = PAINTER_ACTION_INPUT_UNSET,
        dy: object = PAINTER_ACTION_INPUT_UNSET,
        reset: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        mode, horizontal, vertical = validate_view_pan_action(
            x=x, y=y, dx=dx, dy=dy, reset=reset
        )
        dialog = self._paint_dialog_owner()
        if mode == "reset":
            dialog._reset_canvas_pan()
        elif mode == "absolute":
            current = getattr(dialog, "_canvas_pan", None)
            current_x = int(current.x()) if current is not None else 0
            current_y = int(current.y()) if current is not None else 0
            from PySide6.QtCore import QPoint

            dialog._set_canvas_pan(QPoint(
                current_x if horizontal is None else horizontal,
                current_y if vertical is None else vertical,
            ))
        else:
            from PySide6.QtCore import QPoint

            current = getattr(dialog, "_canvas_pan", None)
            current_x = int(current.x()) if current is not None else 0
            current_y = int(current.y()) if current is not None else 0
            target_x = validate_view_pan_result_coordinate(
                current_x + (horizontal or 0), field="result x"
            )
            target_y = validate_view_pan_result_coordinate(
                current_y + (vertical or 0), field="result y"
            )
            dialog._set_canvas_pan(QPoint(target_x, target_y))
        return dialog.painter_action_state()

    def paint_view_grid(
        self,
        *,
        visible: bool | None = None,
        snap: bool | None = None,
        size_px: int | None = None,
    ) -> dict[str, Any]:
        resolved_visible = validate_optional_action_boolean(visible, field="visible")
        resolved_snap = validate_optional_action_boolean(snap, field="snap")
        resolved_size_px = (
            None
            if size_px is None
            else validate_action_integer_domain(
                size_px,
                field="size_px",
                minimum=PAINTER_GRID_SIZE_MIN_PX,
                maximum=PAINTER_GRID_SIZE_MAX_PX,
            )
        )
        dialog = self._paint_dialog_owner()
        dialog._set_grid_options(
            visible=resolved_visible,
            snap=resolved_snap,
            size_px=resolved_size_px,
        )
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
        center_x: float | None = None,
        center_y: float | None = None,
        vertical_x: float | None = None,
        vertical_y: float | None = None,
        mode: int | None = None,
        snap: bool | None = None,
    ) -> dict[str, Any]:
        resolved = validate_perspective_guide_action(
            enabled=enabled,
            horizon=horizon,
            left_x=left_x,
            left_y=left_y,
            right_x=right_x,
            right_y=right_y,
            center_x=center_x,
            center_y=center_y,
            vertical_x=vertical_x,
            vertical_y=vertical_y,
            mode=mode,
            snap=snap,
        )
        dialog = self._paint_dialog_owner()
        dialog._set_perspective_guide_options(**resolved)
        return dialog.painter_action_state()

    def paint_guide_symmetry(
        self,
        *,
        enabled: bool | None = None,
        axis: str | None = None,
        position: float | None = None,
    ) -> dict[str, Any]:
        resolved_enabled, resolved_axis, resolved_position = validate_symmetry_guide_action(
            enabled=enabled,
            axis=axis,
            position=position,
        )
        dialog = self._paint_dialog_owner()
        dialog._set_symmetry_guide_options(
            enabled=resolved_enabled,
            axis=resolved_axis,
            position=resolved_position,
        )
        return dialog.painter_action_state()

    def paint_quick_mask_set(self, *, enabled: bool = True) -> dict[str, Any]:
        enabled = validate_layer_boolean_action(enabled, field="enabled")
        dialog = self._paint_dialog_owner()
        if bool(getattr(dialog, "_quick_mask_enabled", False)) == enabled:
            raise ValueError("Painter Quick Mask state did not change")
        dialog._set_quick_mask_enabled(enabled)
        return dialog.painter_action_state()

    def paint_layer_add(
        self,
        *,
        name: str = "",
        layer_type: str = "standard",
    ) -> dict[str, Any]:
        name = validate_layer_name_action(name, allow_empty=True)
        layer_type = validate_layer_type_action(layer_type)
        dialog = self._paint_dialog_owner()
        dialog._new_paint_layer(
            name or None,
            layer_type=layer_type,
        )
        return dialog.painter_action_state()

    def paint_layer_import_image(
        self,
        *,
        path: str,
        name: str = "",
    ) -> dict[str, Any]:
        if not isinstance(path, str):
            raise TypeError("Painter layer import path must be a string")
        path = path.strip()
        if not path:
            raise ValueError("Painter layer import path must not be empty")
        name = validate_layer_name_action(name, allow_empty=True)
        dialog = self._paint_dialog_owner()
        report = dialog.import_image_as_paint_layer(
            path,
            name=name or None,
        )
        return {**dialog.painter_action_state(), "import": report}

    def paint_layer_group_create(
        self,
        *,
        name: str = "",
        layer_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        name = validate_layer_name_action(name, allow_empty=True)
        layer_ids = validate_layer_ids_action(layer_ids)
        dialog = self._paint_dialog_owner()
        missing_ids = [
            layer_id
            for layer_id in layer_ids
            if dialog._paint_layer_by_id(layer_id) is None
        ]
        if missing_ids:
            raise ValueError("Painter layer group contains an unknown layer_id")
        if any(
            bool(dialog._paint_layer_by_id(layer_id).lock_position)
            for layer_id in layer_ids
        ):
            raise ValueError("Painter layer group cannot reparent a position-locked layer")
        dialog._new_paint_layer_group(name or None, layer_ids=layer_ids)
        return dialog.painter_action_state()

    def paint_layer_set_clipping(
        self, *, layer_id: str = "", clipping: bool = False
    ) -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        clipping = validate_layer_boolean_action(clipping, field="clipping")
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_clipping(layer_id or None, clipping):
            raise ValueError("Painter clipping state did not change")
        return dialog.painter_action_state()

    def paint_layer_group_set_expanded(
        self, *, layer_id: str, expanded: bool
    ) -> dict[str, Any]:
        layer_id = validate_required_layer_id_action(layer_id)
        expanded = validate_layer_boolean_action(expanded, field="expanded")
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_group_expanded(layer_id, expanded):
            raise ValueError("Painter group disclosure did not change")
        return dialog.painter_action_state()

    def paint_layer_set_locks(
        self,
        *,
        layer_id: str = "",
        pixels: object = PAINTER_ACTION_INPUT_UNSET,
        transparency: object = PAINTER_ACTION_INPUT_UNSET,
        position: object = PAINTER_ACTION_INPUT_UNSET,
        all_locked: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        changes = validate_layer_locks_action(
            pixels=pixels,
            transparency=transparency,
            position=position,
            all_locked=all_locked,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_lock_channels(
            layer_id or None,
            **changes,
        ):
            raise ValueError("Painter layer lock state did not change")
        return dialog.painter_action_state()

    def paint_layer_merge_down(self, *, layer_id: str = "") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        if dialog._merge_down(layer_id or None) is None:
            raise ValueError("Painter layer has no mergeable sibling below")
        return dialog.painter_action_state()

    def paint_layer_merge_visible(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if dialog._merge_visible() is None:
            raise ValueError("Painter document has no visible layers")
        return dialog.painter_action_state()

    def paint_layer_flatten(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if dialog._flatten_paint_layers() is None:
            raise ValueError("Painter document has no layers to flatten")
        return dialog.painter_action_state()

    def paint_layer_set_type(
        self,
        *,
        layer_id: str = "",
        layer_type: str = "standard",
    ) -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        layer_type = validate_layer_type_action(layer_type)
        dialog = self._paint_dialog_owner()
        if not dialog._set_paint_layer_type(layer_id or None, layer_type):
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
        plow: float | None = None,
        resaturation: float | None = None,
        negative_depth: bool | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        values = {
            "load": load,
            "thickness": thickness,
            "wetness": wetness,
            "gloss": gloss,
            "roughness": roughness,
            "plow": plow,
            "resaturation": resaturation,
            "negative_depth": negative_depth,
        }
        if not dialog._set_material_settings(values, layer_id=layer_id or None):
            raise ValueError("Material Paint settings require a material layer and a changed value")
        return dialog.painter_action_state()

    def paint_material_preview_set(
        self,
        *,
        enabled: object = _PAINTER_ACTION_UNSET,
        azimuth_deg: object = _PAINTER_ACTION_UNSET,
        elevation_deg: object = _PAINTER_ACTION_UNSET,
    ) -> dict[str, Any]:
        supplied = {
            key: value
            for key, value in {
                "enabled": enabled,
                "azimuth_deg": azimuth_deg,
                "elevation_deg": elevation_deg,
            }.items()
            if value is not _PAINTER_ACTION_UNSET
        }
        if any(value is None for value in supplied.values()):
            raise TypeError("Material preview Action fields must not be null")
        values = validate_material_preview_action(
            enabled=supplied.get("enabled"),
            azimuth_deg=supplied.get("azimuth_deg"),
            elevation_deg=supplied.get("elevation_deg"),
            require_authored_field=True,
        )
        dialog = self._paint_dialog_owner()
        dialog._set_material_preview(
            **{key: value for key, value in values.items() if value is not None}
        )
        return dialog.painter_action_state()

    def paint_wet_canvas_settings_set(
        self,
        *,
        layer_id: str = "",
        enabled: object = _PAINTER_ACTION_UNSET,
        mixing: object = _PAINTER_ACTION_UNSET,
        diffusion: object = _PAINTER_ACTION_UNSET,
        pickup: object = _PAINTER_ACTION_UNSET,
        drying_seconds: object = _PAINTER_ACTION_UNSET,
    ) -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        supplied = {
            key: value
            for key, value in {
                "enabled": enabled,
                "mixing": mixing,
                "diffusion": diffusion,
                "pickup": pickup,
                "drying_seconds": drying_seconds,
            }.items()
            if value is not _PAINTER_ACTION_UNSET
        }
        values = validate_wet_canvas_settings_update(
            supplied,
            require_authored_field=True,
            allow_none=False,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._set_wet_canvas_settings(
            values,
            layer_id=resolved_layer_id or None,
        ):
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
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        resolved_seconds = validate_wet_canvas_advance_seconds(
            seconds,
            allow_zero=False,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._advance_wet_canvas(
            resolved_seconds,
            layer_id=resolved_layer_id or None,
        ):
            raise ValueError("Wet Canvas did not advance")
        return dialog.painter_action_state()

    def paint_wet_canvas_dry(self, *, layer_id: str = "") -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        if not dialog._dry_active_wet_canvas(
            layer_id=resolved_layer_id or None,
        ):
            raise ValueError("Wet Canvas requires an active material layer")
        return dialog.painter_action_state()

    def paint_layer_select(self, *, layer_id: str = "") -> dict[str, Any]:
        layer_id = validate_required_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        if not dialog._select_paint_layer_by_id(layer_id):
            raise ValueError("paint layer not found")
        return dialog.painter_action_state()

    def paint_layer_rename(self, *, layer_id: str = "", name: str = "") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        name = validate_layer_name_action(name, allow_empty=False)
        dialog = self._paint_dialog_owner()
        if not dialog._rename_layer_to(layer_id or None, name):
            raise ValueError("layer rename did not change a paint layer")
        return dialog.painter_action_state()

    def paint_layer_duplicate(self, *, layer_id: str = "") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        target = layer_id or str(dialog._current_layer_id() or "")
        target_layer = dialog._paint_layer_by_id(target)
        if target_layer is None:
            raise ValueError("paint layer not found")
        if dialog._text_editor_has_focus():
            raise ValueError("Painter layer cannot be duplicated while text editing is active")
        if dialog._payload_for_layer(target) is None:
            raise ValueError("Painter layer has no duplicate payload")
        if not dialog._select_paint_layer_by_id(target):
            raise ValueError("paint layer not found")
        before_count = len(dialog._paint_layers)
        dialog._duplicate_selected_layer()
        if len(dialog._paint_layers) == before_count:
            raise ValueError("Painter layer could not be duplicated")
        return dialog.painter_action_state()

    def paint_layer_delete(self, *, layer_id: str = "") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        target = layer_id or str(dialog._current_layer_id() or "")
        target_layer = dialog._paint_layer_by_id(target)
        if target_layer is None:
            raise ValueError("paint layer not found")
        if len(dialog._paint_layers) <= 1:
            raise ValueError("Painter document must retain at least one paint layer")
        if target_layer.locked:
            raise ValueError("Painter locked layer cannot be deleted")
        before_count = len(dialog._paint_layers)
        dialog._delete_layer(target)
        if len(dialog._paint_layers) == before_count:
            raise ValueError("Painter layer could not be deleted")
        return dialog.painter_action_state()

    def paint_layer_set_visible(self, *, layer_id: str = "", visible: bool = True) -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        visible = validate_layer_boolean_action(visible, field="visible")
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_visible(layer_id or None, visible):
            raise ValueError("Painter layer visibility did not change")
        return dialog.painter_action_state()

    def paint_layer_set_locked(self, *, layer_id: str = "", locked: bool = True) -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        locked = validate_layer_boolean_action(locked, field="locked")
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_locked(layer_id or None, locked):
            raise ValueError("Painter layer lock state did not change")
        return dialog.painter_action_state()

    def paint_layer_set_opacity(self, *, layer_id: str = "", opacity: int = 100) -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        resolved_opacity = validate_layer_opacity_action(opacity)
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_opacity_value(resolved_layer_id or None, resolved_opacity):
            raise ValueError("Painter layer opacity did not change")
        return dialog.painter_action_state()

    def paint_layer_set_blend_mode(self, *, layer_id: str = "", blend_mode: str = "normal") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        blend_mode = validate_layer_blend_mode_action(blend_mode)
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_blend_mode(layer_id or None, blend_mode):
            raise ValueError("Painter layer blend mode did not change")
        return dialog.painter_action_state()

    def paint_layer_set_color(self, *, layer_id: str = "", color_label: str = "none") -> dict[str, Any]:
        layer_id = validate_optional_layer_id_action(layer_id)
        color_label = validate_layer_color_label_action(color_label)
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_color_label(layer_id or None, color_label):
            raise ValueError("Painter layer color label did not change")
        return dialog.painter_action_state()

    def paint_channel_set_visible(self, *, channel: str, visible: bool) -> dict[str, Any]:
        channel = _validate_component_or_saved_channel(channel, allow_empty=False)
        visible = validate_layer_boolean_action(visible, field="visible")
        dialog = self._paint_dialog_owner()
        if not dialog._set_channel_visibility(channel, visible):
            raise ValueError("Painter channel visibility did not change")
        return dialog.painter_action_state()

    def paint_channel_select(self, *, channel: str) -> dict[str, Any]:
        channel = _validate_component_or_saved_channel(channel, allow_empty=False)
        dialog = self._paint_dialog_owner()
        selected = dialog._set_selected_channel(channel)
        if selected != channel:
            raise ValueError("Painter channel does not exist")
        return dialog.painter_action_state()

    def paint_channel_copy_image(self, *, channel: str = "") -> dict[str, Any]:
        channel = _validate_component_or_saved_channel(channel, allow_empty=True)
        dialog = self._paint_dialog_owner()
        target = channel.strip() or str(getattr(dialog, "_selected_channel", "RGB"))
        if not dialog._copy_channel_image(target):
            raise ValueError("no Painter channel image available to copy")
        state = dialog.painter_action_state()
        state["channel_clipboard"] = "copied"
        return state

    def paint_channel_paste_image(self, *, channel: str = "") -> dict[str, Any]:
        channel = _validate_component_or_saved_channel(channel, allow_empty=True)
        dialog = self._paint_dialog_owner()
        target = channel.strip() or str(getattr(dialog, "_selected_channel", "RGB"))
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        image = clipboard.image() if clipboard is not None else None
        if image is None or image.isNull():
            raise ValueError("system clipboard does not contain an image")
        if not dialog._paste_channel_image(target):
            raise ValueError("system clipboard does not contain an image")
        return dialog.painter_action_state()

    def paint_selection_save_channel(
        self,
        *,
        name: str = "",
        channel_id: str = "",
        operation: str = "new",
    ) -> dict[str, Any]:
        if not isinstance(name, str) or not isinstance(channel_id, str):
            raise TypeError("Saved selection channel name and id must be strings")
        from app.painter_saved_selection_channels import (
            normalize_saved_selection_channel_id,
            normalize_saved_selection_name,
            normalize_saved_selection_operation,
        )

        operation = normalize_saved_selection_operation(operation, loading=False)
        if operation == "new":
            if channel_id != "":
                raise ValueError("New saved selection must not specify channel_id")
            name = normalize_saved_selection_name(name)
        else:
            if name != "":
                raise ValueError("Existing saved selection update must not specify name")
            if channel_id != channel_id.strip():
                raise ValueError(
                    "Saved selection channel id must not contain surrounding whitespace"
                )
            channel_id = normalize_saved_selection_channel_id(channel_id)
        dialog = self._paint_dialog_owner()
        saved_id = dialog._save_selection_channel(
            name=name,
            channel_id=channel_id,
            operation=operation,
        )
        state = dialog.painter_action_state()
        state["saved_selection_channel_id"] = saved_id
        return state

    def paint_selection_load_channel(
        self,
        *,
        channel_id: str,
        operation: str = "new",
        invert: bool = False,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        invert = validate_layer_boolean_action(invert, field="invert")
        from app.painter_saved_selection_channels import (
            normalize_saved_selection_operation,
        )

        operation = normalize_saved_selection_operation(operation, loading=True)
        dialog = self._paint_dialog_owner()
        if not dialog._load_selection_channel(
            channel_id,
            operation=operation,
            invert=invert,
        ):
            raise ValueError("Loaded selection would not change")
        return dialog.painter_action_state()

    def paint_documents_inspect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_open_documents import (
            inspect_open_painter_documents,
            require_open_painter_document_instance,
        )

        require_open_painter_document_instance(dialog)
        report = inspect_open_painter_documents()
        report["active_document_id"] = str(
            getattr(dialog, "_painter_runtime_document_id", "") or ""
        )
        return report

    def paint_selection_save_channel_to_document(
        self,
        *,
        destination_document_id: str,
        name: str = "",
        channel_id: str = "",
        operation: str = "new",
    ) -> dict[str, Any]:
        from app.painter_open_documents import (
            normalize_painter_runtime_document_id,
        )

        destination_document_id = normalize_painter_runtime_document_id(
            destination_document_id
        )
        if not isinstance(name, str) or not isinstance(channel_id, str):
            raise TypeError("Saved selection channel name and id must be strings")
        from app.painter_saved_selection_channels import (
            normalize_saved_selection_channel_id,
            normalize_saved_selection_name,
            normalize_saved_selection_operation,
        )

        operation = normalize_saved_selection_operation(operation, loading=False)
        if operation == "new":
            if channel_id != "":
                raise ValueError("New saved selection must not specify channel_id")
            name = normalize_saved_selection_name(name)
        else:
            if name != "":
                raise ValueError(
                    "Existing saved selection update must not specify name"
                )
            if channel_id != channel_id.strip():
                raise ValueError(
                    "Saved selection channel id must not contain surrounding whitespace"
                )
            channel_id = normalize_saved_selection_channel_id(channel_id)
        source = self._paint_dialog_owner()
        from app.painter_open_documents import (
            painter_open_document_descriptor,
            resolve_open_painter_document,
            save_selection_to_open_painter_document,
        )

        destination = resolve_open_painter_document(
            destination_document_id,
            exclude=source,
        )
        saved_id = save_selection_to_open_painter_document(
            source,
            destination,
            name=name,
            channel_id=channel_id,
            operation=operation,
        )
        return {
            "schema": "tigerstudio.paint.cross-document-save.v1",
            "source": painter_open_document_descriptor(source),
            "destination": painter_open_document_descriptor(destination),
            "saved_selection_channel_id": saved_id,
            "destination_state": destination.painter_action_state(),
        }

    def paint_selection_load_channel_from_document(
        self,
        *,
        source_document_id: str,
        channel_id: str,
        operation: str = "new",
        invert: bool = False,
    ) -> dict[str, Any]:
        from app.painter_open_documents import (
            normalize_painter_runtime_document_id,
        )

        source_document_id = normalize_painter_runtime_document_id(
            source_document_id
        )
        channel_id = _validate_saved_selection_channel_id(channel_id)
        invert = validate_layer_boolean_action(invert, field="invert")
        from app.painter_saved_selection_channels import (
            normalize_saved_selection_operation,
        )

        operation = normalize_saved_selection_operation(operation, loading=True)
        destination = self._paint_dialog_owner()
        from app.painter_open_documents import (
            load_selection_from_open_painter_document,
            painter_open_document_descriptor,
            resolve_open_painter_document,
        )

        source = resolve_open_painter_document(
            source_document_id,
            exclude=destination,
        )
        if not load_selection_from_open_painter_document(
            destination,
            source,
            channel_id=channel_id,
            operation=operation,
            invert=invert,
        ):
            raise ValueError("Loaded selection would not change")
        state = destination.painter_action_state()
        state["cross_document_source"] = painter_open_document_descriptor(source)
        return state

    def paint_selection_channels_import_file(
        self,
        *,
        path: str,
    ) -> dict[str, Any]:
        if not isinstance(path, str):
            raise TypeError("Alpha channel import path must be a string")
        if path != path.strip() or not path:
            raise ValueError(
                "Alpha channel import path must be nonblank without surrounding whitespace"
            )
        source = Path(path)
        if source.suffix.casefold() not in {".psd", ".tif", ".tiff"}:
            raise ValueError("Alpha channel import path must use PSD or TIFF")
        if not source.is_file():
            raise ValueError("Alpha channel import source file does not exist")
        dialog = self._paint_dialog_owner()
        report = dialog.import_saved_selection_channels_from_path(source)
        report["state"] = dialog.painter_action_state()
        return report

    def paint_selection_channel_rename(
        self,
        *,
        channel_id: str,
        name: str,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        if not isinstance(name, str):
            raise TypeError("Saved selection channel name must be a string")
        from app.painter_saved_selection_channels import normalize_saved_selection_name

        name = normalize_saved_selection_name(name)
        dialog = self._paint_dialog_owner()
        dialog._rename_saved_selection_channel(channel_id, name)
        return dialog.painter_action_state()

    def paint_selection_channel_options_set(
        self,
        *,
        channel_id: str,
        display_mode: str,
        overlay_color: str,
        overlay_opacity_percent: int,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        from app.painter_saved_selection_channels import (
            normalize_saved_selection_channel_display_mode,
            normalize_saved_selection_channel_overlay_color,
            normalize_saved_selection_channel_overlay_opacity,
        )

        display_mode = normalize_saved_selection_channel_display_mode(display_mode)
        overlay_color = normalize_saved_selection_channel_overlay_color(
            overlay_color
        )
        overlay_opacity_percent = normalize_saved_selection_channel_overlay_opacity(
            overlay_opacity_percent
        )
        dialog = self._paint_dialog_owner()
        dialog._set_saved_selection_channel_options(
            channel_id,
            display_mode=display_mode,
            overlay_color=overlay_color,
            overlay_opacity_percent=overlay_opacity_percent,
        )
        return dialog.painter_action_state()

    def paint_selection_channel_duplicate(
        self,
        *,
        channel_id: str,
        name: str,
        invert: bool = False,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        if not isinstance(name, str):
            raise TypeError("Saved selection channel name must be a string")
        from app.painter_saved_selection_channels import normalize_saved_selection_name

        name = normalize_saved_selection_name(name)
        invert = validate_layer_boolean_action(invert, field="invert")
        dialog = self._paint_dialog_owner()
        duplicate_id = dialog._duplicate_saved_selection_channel(
            channel_id,
            name=name,
            invert=invert,
        )
        state = dialog.painter_action_state()
        state["saved_selection_channel_id"] = duplicate_id
        return state

    def paint_selection_channel_reorder(
        self,
        *,
        channel_id: str,
        target_channel_id: str,
        placement: str,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        target_channel_id = _validate_saved_selection_channel_id(target_channel_id)
        if not isinstance(placement, str):
            raise TypeError("Saved selection channel placement must be a string")
        placement = placement.strip().casefold()
        if placement not in {"before", "after"}:
            raise ValueError("Saved selection channel placement is unsupported")
        if channel_id == target_channel_id:
            raise ValueError("Saved selection channel reorder requires two channels")
        dialog = self._paint_dialog_owner()
        dialog._reorder_saved_selection_channel(
            channel_id,
            target_channel_id,
            placement=placement,
        )
        return dialog.painter_action_state()

    def paint_selection_channel_delete(
        self,
        *,
        channel_id: str,
    ) -> dict[str, Any]:
        channel_id = _validate_saved_selection_channel_id(channel_id)
        dialog = self._paint_dialog_owner()
        dialog._delete_saved_selection_channel(channel_id)
        return dialog.painter_action_state()

    def paint_selection_select_all(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._select_all():
            raise ValueError("Painter selection already covers the full canvas")
        return dialog.painter_action_state()

    def paint_selection_deselect(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._deselect():
            raise ValueError("Painter deselect requires an active selection")
        return dialog.painter_action_state()

    def paint_selection_invert(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._invert_selection()
        return dialog.painter_action_state()

    def paint_selection_to_path(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._selection_to_path():
            raise ValueError("selection-to-path requires an active selection")
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
        x1, y1, x2, y2, aspect, mode = validate_selection_bounds_action(
            x1=x1, y1=y1, x2=x2, y2=y2, aspect=aspect, mode=mode,
        )
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Rectangular selection")
        dialog._set_selection_aspect_mode(aspect)
        dialog._set_selection_combine_mode(mode)
        dialog.canvas.select_rectangle(x1, y1, x2, y2, shape="rect", aspect=aspect)
        dialog._sync_pixel_selection_from_canvas(ellipse=False)
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
        x1, y1, x2, y2, aspect, mode = validate_selection_bounds_action(
            x1=x1, y1=y1, x2=x2, y2=y2, aspect=aspect, mode=mode,
        )
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state("Elliptical selection")
        dialog._set_selection_aspect_mode(aspect)
        dialog._set_selection_combine_mode(mode)
        dialog.canvas.select_rectangle(x1, y1, x2, y2, shape="ellipse", aspect=aspect)
        dialog._sync_pixel_selection_from_canvas(ellipse=True)
        dialog._selected_path_item_id = "selection"
        dialog._update_path_list()
        dialog._set_tool("ellipse_select")
        return dialog.painter_action_state()

    def paint_selection_lasso(
        self,
        *,
        points: list | None = None,
        mode: str = "new",
        polygonal: bool = False,
    ) -> dict[str, Any]:
        resolved_points, resolved_mode, resolved_polygonal = (
            validate_selection_lasso_action(
                points=points,
                mode=mode,
                polygonal=polygonal,
            )
        )
        dialog = self._paint_dialog_owner()
        if not dialog._select_lasso_points(
            resolved_points,
            mode=resolved_mode,
            polygonal=resolved_polygonal,
        ):
            raise ValueError("lasso selection requires at least three points")
        return dialog.painter_action_state()

    def paint_selection_modify(
        self,
        *,
        operation: str = "expand",
        radius_px: float = 1,
    ) -> dict[str, Any]:
        resolved_operation, resolved_radius = validate_selection_modify_action(
            operation=operation,
            radius_px=radius_px,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._modify_selection(resolved_operation, resolved_radius):
            raise ValueError("selection modification requires an active selection")
        return dialog.painter_action_state()

    def paint_selection_set_aspect(self, *, aspect: str) -> dict[str, Any]:
        aspect = validate_selection_aspect_action(aspect)
        dialog = self._paint_dialog_owner()
        if getattr(dialog, "_selection_aspect_mode", "free") == aspect:
            raise ValueError("Painter selection aspect did not change")
        dialog._set_selection_aspect_mode(aspect)
        return dialog.painter_action_state()

    def paint_selection_set_mode(self, *, mode: str) -> dict[str, Any]:
        mode = validate_selection_mode_action(mode)
        dialog = self._paint_dialog_owner()
        if getattr(dialog, "_selection_combine_mode", "new") == mode:
            raise ValueError("Painter selection combination mode did not change")
        dialog._set_selection_combine_mode(mode)
        return dialog.painter_action_state()

    def paint_selection_select_by_color(
        self,
        *,
        x: float = 0.5,
        y: float = 0.5,
        tolerance: int | None = None,
        contiguous: bool = True,
        phase: str = "commit",
    ) -> dict[str, Any]:
        x, y, tolerance, contiguous, value = validate_color_selection_action(
            x=x,
            y=y,
            tolerance=tolerance,
            contiguous=contiguous,
            phase=phase,
        )
        dialog = self._paint_dialog_owner()
        if value == "cancel":
            ok = dialog._cancel_color_range_preview()
        elif value == "preview":
            ok = dialog._preview_color_range(
                x, y, tolerance=tolerance, contiguous=contiguous
            )
        else:
            ok = dialog._commit_color_range_preview()
            if not ok:
                ok = dialog._select_by_color_at(
                    x, y, tolerance=tolerance, contiguous=contiguous
                )
        if not ok:
            raise ValueError("Magic Select could not create a color selection")
        return dialog.painter_action_state()

    def paint_crop_to_selection(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._crop_to_selection():
            raise ValueError("crop requires an active Painter selection")
        return dialog.painter_action_state()

    def paint_crop_preview(
        self, *, x1: object = PAINTER_ACTION_INPUT_UNSET,
        y1: object = PAINTER_ACTION_INPUT_UNSET,
        x2: object = PAINTER_ACTION_INPUT_UNSET,
        y2: object = PAINTER_ACTION_INPUT_UNSET,
        straighten_degrees: object = 0.0,
    ) -> dict[str, Any]:
        bounds, angle = validate_crop_preview_action(
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            straighten_degrees=straighten_degrees,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._preview_crop(bounds, straighten_degrees=angle):
            raise ValueError("crop preview requires an active Painter selection")
        return dialog.painter_action_state()

    def paint_crop_commit(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._commit_crop():
            raise ValueError("no Painter crop preview is active")
        return dialog.painter_action_state()

    def paint_crop_cancel(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._cancel_crop():
            raise ValueError("no Painter crop preview is active")
        return dialog.painter_action_state()

    def paint_selection_transform(
        self,
        *,
        translate_x: float = 0.0,
        translate_y: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        rotation_degrees: float = 0.0,
        skew_x_degrees: float = 0.0,
        skew_y_degrees: float = 0.0,
        pivot_x: float = 0.5,
        pivot_y: float = 0.5,
        flip_x: bool = False,
        flip_y: bool = False,
        phase: str = "commit",
        target: str = "selected_pixels",
    ) -> dict[str, Any]:
        settings, value, resolved_target = validate_selection_transform_action(
            translate_x=translate_x,
            translate_y=translate_y,
            scale_x=scale_x,
            scale_y=scale_y,
            rotation_degrees=rotation_degrees,
            skew_x_degrees=skew_x_degrees,
            skew_y_degrees=skew_y_degrees,
            pivot_x=pivot_x,
            pivot_y=pivot_y,
            flip_x=flip_x,
            flip_y=flip_y,
            phase=phase,
            target=target,
        )
        dialog = self._paint_dialog_owner()
        if value == "cancel":
            ok = dialog._cancel_selection_transform()
        else:
            ok = dialog._preview_selection_transform(target=resolved_target, **settings)
            if ok and value == "commit":
                ok = dialog._commit_selection_transform()
        if not ok:
            raise ValueError("Painter selection transform could not be applied")
        return dialog.painter_action_state()

    def paint_image_resize(self, *, width: int, height: int) -> dict[str, Any]:
        from app.drawing import _validated_paint_dimensions
        from app.painter_output import PAINTER_NEW_CANVAS_MIN_DIMENSION_PX

        resolved_width, resolved_height = _validated_paint_dimensions(
            width,
            height,
            minimum=PAINTER_NEW_CANVAS_MIN_DIMENSION_PX,
            context="Image resize",
        )
        dialog = self._paint_dialog_owner()
        dialog._resize_image_document(resolved_width, resolved_height)
        return dialog.painter_action_state()

    def paint_canvas_resize(
        self,
        *,
        width: int,
        height: int,
        background: str = "transparent",
    ) -> dict[str, Any]:
        from app.drawing import _validated_paint_background, _validated_paint_dimensions
        from app.painter_output import PAINTER_NEW_CANVAS_MIN_DIMENSION_PX

        resolved_width, resolved_height = _validated_paint_dimensions(
            width,
            height,
            minimum=PAINTER_NEW_CANVAS_MIN_DIMENSION_PX,
            context="Canvas resize",
        )
        resolved_background = _validated_paint_background(background)
        dialog = self._paint_dialog_owner()
        dialog._resize_canvas_document(
            resolved_width,
            resolved_height,
            background=resolved_background,
        )
        return dialog.painter_action_state()

    def paint_canvas_flip(self, *, axis: object) -> dict[str, Any]:
        value = validate_canvas_flip_action(axis)
        dialog = self._paint_dialog_owner()
        if not dialog._flip_canvas(horizontal=value == "horizontal"):
            raise ValueError("Painter canvas flip did not change the document")
        return dialog.painter_action_state()

    def paint_fill_solid(self, *, color: object) -> dict[str, Any]:
        resolved_color = validate_fill_color_action(color, field="color")
        dialog = self._paint_dialog_owner()
        if not dialog._fill_document("solid", color1=resolved_color):
            raise ValueError("Painter solid fill could not modify the active raster layer")
        return dialog.painter_action_state()

    def paint_fill_gradient(self, *, color1: object, color2: object) -> dict[str, Any]:
        resolved_color1, resolved_color2 = validate_fill_color_pair_action(
            color1=color1,
            color2=color2,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._fill_document(
            "gradient",
            color1=resolved_color1,
            color2=resolved_color2,
        ):
            raise ValueError("Painter gradient fill could not modify the active raster layer")
        return dialog.painter_action_state()

    def paint_fill_pattern(self, *, color1: object, color2: object) -> dict[str, Any]:
        resolved_color1, resolved_color2 = validate_fill_color_pair_action(
            color1=color1,
            color2=color2,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._fill_document(
            "pattern",
            color1=resolved_color1,
            color2=resolved_color2,
        ):
            raise ValueError("Painter pattern fill could not modify the active raster layer")
        return dialog.painter_action_state()

    def paint_mirror_set(
        self,
        *,
        x: object = PAINTER_ACTION_INPUT_UNSET,
        y: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        resolved_x, resolved_y = validate_mirror_action(x=x, y=y)
        dialog = self._paint_dialog_owner()
        before = (
            bool(getattr(dialog, "_mirror_x_enabled", False)),
            bool(getattr(dialog, "_mirror_y_enabled", False)),
        )
        dialog._set_mirror_enabled(x=resolved_x, y=resolved_y)
        after = (
            bool(getattr(dialog, "_mirror_x_enabled", False)),
            bool(getattr(dialog, "_mirror_y_enabled", False)),
        )
        if after == before:
            raise ValueError("Painter mirror action did not change either axis")
        return dialog.painter_action_state()

    def paint_layer_mask_from_selection(self, *, layer_id: object = "") -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        if not dialog._create_layer_mask("selection", resolved_layer_id or None):
            raise ValueError("layer mask from selection requires an active selection")
        return dialog.painter_action_state()

    def paint_layer_mask_from_path(
        self,
        *,
        layer_id: object = "",
        path_id: object,
    ) -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        resolved_path_id = validate_path_id_action(path_id)
        if not resolved_path_id:
            raise ValueError("Painter layer mask from path requires path_id")
        dialog = self._paint_dialog_owner()
        if not dialog._create_layer_mask(
            "path",
            resolved_layer_id or None,
            path_id=resolved_path_id,
        ):
            raise ValueError("layer mask from path requires a path with at least 3 points")
        return dialog.painter_action_state()

    def paint_layer_mask_create(
        self,
        *,
        layer_id: object = "",
        mask_type: object,
    ) -> dict[str, Any]:
        resolved_layer_id, resolved_mask_type = validate_layer_mask_source_action(
            layer_id=layer_id,
            mask_type=mask_type,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._create_layer_mask(
            resolved_mask_type,
            resolved_layer_id or None,
        ):
            raise ValueError("layer mask creation requires valid mask source pixels or points")
        return dialog.painter_action_state()

    def paint_layer_mask_state_set(
        self,
        *,
        layer_id: str = "",
        enabled: object = PAINTER_ACTION_INPUT_UNSET,
        linked: object = PAINTER_ACTION_INPUT_UNSET,
        delete: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        layer_id, enabled, linked, delete = validate_layer_mask_state_action(
            layer_id=layer_id,
            enabled=enabled,
            linked=linked,
            delete=delete,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_mask_state(
            layer_id or None,
            enabled=enabled,
            linked=linked,
            delete=delete,
        ):
            raise ValueError("Painter layer mask state did not change")
        return dialog.painter_action_state()

    def paint_layer_mask_paint(
        self,
        *,
        layer_id: str = "",
        x: float,
        y: float,
        radius_px: float,
        value: int,
    ) -> dict[str, Any]:
        layer_id, x, y, radius_px, value = validate_layer_mask_paint_action(
            layer_id=layer_id,
            x=x,
            y=y,
            radius_px=radius_px,
            value=value,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._paint_layer_mask_circle(
            layer_id or None,
            x_norm=x,
            y_norm=y,
            radius_px=radius_px,
            value=value,
        ):
            raise ValueError("Painter layer mask paint requires an unlocked paint layer")
        return dialog.painter_action_state()

    def paint_layer_mask_gradient(
        self,
        *,
        layer_id: str = "",
        start: list[Any] | None = None,
        end: list[Any] | None = None,
        start_value: int = 0,
        end_value: int = 255,
    ) -> dict[str, Any]:
        layer_id, start, end, start_value, end_value = validate_layer_mask_gradient_action(
            layer_id=layer_id,
            start=start,
            end=end,
            start_value=start_value,
            end_value=end_value,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._set_layer_mask_gradient(
            layer_id or None,
            start=start,
            end=end,
            start_value=start_value,
            end_value=end_value,
        ):
            raise ValueError("Painter layer mask gradient requires an unlocked layer")
        return dialog.painter_action_state()

    def paint_layer_mask_apply(self, *, layer_id: object = "") -> dict[str, Any]:
        resolved_layer_id = validate_optional_layer_id_action(layer_id)
        dialog = self._paint_dialog_owner()
        if not dialog._apply_selected_layer_mask(resolved_layer_id or None):
            raise ValueError("Painter layer mask apply requires an enabled raster mask")
        return dialog.painter_action_state()

    def paint_path_to_selection(self, *, path_id: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        dialog = self._paint_dialog_owner()
        if not dialog._make_selection_from_selected_path(path_id or None):
            raise ValueError("Painter path to selection requires at least three path points")
        return dialog.painter_action_state()

    def paint_path_create(
        self,
        *,
        points: list[Any] | None = None,
        closed: bool = True,
        make_selection: bool = False,
    ) -> dict[str, Any]:
        points, closed, make_selection = validate_path_create_action(
            points=points,
            closed=closed,
            make_selection=make_selection,
        )
        dialog = self._paint_dialog_owner()
        if not dialog._create_path_from_points(points, closed=closed, make_selection=make_selection):
            raise ValueError("path requires at least two valid normalized points")
        return dialog.painter_action_state()

    def paint_path_delete(self, *, path_id: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        dialog = self._paint_dialog_owner()
        if not dialog._delete_path_by_id(path_id or None):
            raise ValueError("paint path not found")
        return dialog.painter_action_state()

    def paint_path_anchor_edit(
        self, *, path_id: str = "", index: int = 0, operation: str = "move",
        point: list | None = None, in_handle: list | None = None,
        out_handle: list | None = None,
    ) -> dict[str, Any]:
        path_id, index, operation, point, in_handle, out_handle = (
            validate_path_anchor_action(
                path_id=path_id,
                index=index,
                operation=operation,
                point=point,
                in_handle=in_handle,
                out_handle=out_handle,
            )
        )
        dialog = self._paint_dialog_owner()
        if not dialog._edit_path_anchor(
            path_id or None, index, operation, point=point,
            in_handle=in_handle, out_handle=out_handle,
        ):
            raise ValueError("Painter path anchor could not be edited")
        return dialog.painter_action_state()

    def paint_path_duplicate(self, *, path_id: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        dialog = self._paint_dialog_owner()
        if not dialog._duplicate_path(path_id or None):
            raise ValueError("Painter path not found")
        return dialog.painter_action_state()

    def paint_path_rename(self, *, name: str = "", path_id: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        name = validate_path_name_action(name)
        dialog = self._paint_dialog_owner()
        if not dialog._rename_path(name, path_id or None):
            raise ValueError("Painter path could not be renamed")
        return dialog.painter_action_state()

    def paint_path_reorder(self, *, index: int = 0, path_id: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        index = validate_path_reorder_action(index)
        dialog = self._paint_dialog_owner()
        if not dialog._reorder_path(path_id or None, index):
            raise ValueError("Painter path order did not change")
        return dialog.painter_action_state()

    def paint_path_fill(self, *, path_id: str = "", color: str = "") -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        color = validate_optional_path_color_action(color)
        dialog = self._paint_dialog_owner()
        if not dialog._fill_saved_path(path_id or None, color or None):
            raise ValueError("closed Painter path could not be filled")
        return dialog.painter_action_state()

    def paint_path_stroke(
        self, *, path_id: str = "", color: str = "", width_px: float | None = None
    ) -> dict[str, Any]:
        path_id = validate_path_id_action(path_id)
        color, width_px = validate_path_stroke_action(color=color, width_px=width_px)
        dialog = self._paint_dialog_owner()
        if not dialog._stroke_saved_path(path_id or None, color or None, width_px):
            raise ValueError("Painter path could not be stroked")
        return dialog.painter_action_state()

    def paint_path_clear(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._clear_path_preview()
        return dialog.painter_action_state()

    def paint_path_commit(self, *, closed: bool = False) -> dict[str, Any]:
        if not isinstance(closed, bool):
            raise TypeError("Painter path closed must be a boolean")
        dialog = self._paint_dialog_owner()
        dialog._commit_path(closed)
        return dialog.painter_action_state()

    def paint_clipboard_copy(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._copy_selected_layer():
            raise ValueError("Painter clipboard copy requires selected paint content")
        return dialog.painter_action_state()

    def paint_clipboard_cut(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._cut_selected_layer():
            raise ValueError("Painter clipboard cut requires editable selected paint content")
        return dialog.painter_action_state()

    def paint_clipboard_paste(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._paste_layer_clipboard():
            raise ValueError("Painter clipboard paste found no supported clipboard content")
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
            "lasso": "lasso_select",
            "lasso_select": "lasso_select",
            "polygon_lasso": "polygon_lasso",
            "polygonal_lasso": "polygon_lasso",
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
        dynamics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validated = validate_brush_set_action(
            preset=preset,
            style=style,
            width=width,
            opacity=opacity,
            hardness=hardness,
            spacing=spacing,
            angle=angle,
            roundness=roundness,
            flip_x=flip_x,
            flip_y=flip_y,
            dynamics=dynamics,
        )
        from app.drawing import BRUSH_LIBRARY_PRESETS

        preset_key = str(validated["preset"]).casefold().replace("-", "_").replace(" ", "_")
        preset_row = None
        if preset_key:
            for row in BRUSH_LIBRARY_PRESETS:
                name_key = str(row.get("name") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                style_key = str(row.get("style") or "").strip().casefold().replace("-", "_").replace(" ", "_")
                if preset_key in {name_key, style_key}:
                    preset_row = row
                    break
            if preset_row is None:
                raise ValueError("Painter brush preset not found")

        dialog = self._paint_dialog_owner()
        style_combo = getattr(dialog, "brush_style_combo", None)
        style_combo_index = None
        if str(validated["style"]) and style_combo is not None:
            style_combo_index = style_combo.findData(str(validated["style"]))
            if style_combo_index < 0:
                raise ValueError("Painter brush style is missing from the active style control")
        if preset_row is not None:
            dialog._apply_brush_library_preset(preset_row)

        style_id = str(validated["style"])
        if style_id:
            dialog._pen_style = style_id
            if hasattr(dialog, "canvas"):
                dialog.canvas.set_pen_style(style_id)
            if style_combo_index is not None:
                style_combo.setCurrentIndex(style_combo_index)
        if validated["width"] is not None:
            value = validated["width"]
            dialog._pen_width = float(value)
            if hasattr(dialog, "canvas"):
                dialog.canvas.set_pen_width(dialog._pen_width)
            if hasattr(dialog, "width_slider") and value <= dialog.width_slider.maximum():
                dialog.width_slider.setValue(value)
            if hasattr(dialog, "_width_value_label"):
                dialog._width_value_label.setText(f"{value} px")
        if validated["opacity"] is not None:
            value = validated["opacity"]
            if hasattr(dialog, "opacity_slider"):
                dialog.opacity_slider.setValue(value)
            else:
                dialog._pen_opacity = int(value * 255 / 100)
                if hasattr(dialog, "canvas"):
                    dialog.canvas.set_pen_opacity(dialog._pen_opacity)
        for key, value in (
            ("hardness", validated["hardness"]),
            ("spacing", validated["spacing"]),
            ("angle", validated["angle"]),
            ("roundness", validated["roundness"]),
        ):
            if value is not None:
                dialog._set_brush_detail_value(key, validated[key])
        if validated["flip_x"] is not None:
            dialog._set_brush_detail_toggle("flip_x", bool(validated["flip_x"]))
        if validated["flip_y"] is not None:
            dialog._set_brush_detail_toggle("flip_y", bool(validated["flip_y"]))
        if validated["dynamics"] is not None:
            dialog._set_brush_dynamics(dict(validated["dynamics"]))
        dialog._set_tool("pen")
        return dialog.painter_action_state()

    def paint_brush_calibration_set(
        self,
        *,
        device_id: str = "default",
        minimum: float = 0.0,
        maximum: float = 1.0,
        curve: list[list[float]] | None = None,
    ) -> dict[str, Any]:
        resolved_device_id, resolved_minimum, resolved_maximum, resolved_curve = (
            validate_pressure_calibration_action(
                device_id=device_id,
                minimum=minimum,
                maximum=maximum,
                curve=curve,
            )
        )
        dialog = self._paint_dialog_owner()
        profile = dialog._set_brush_pressure_calibration(
            resolved_device_id,
            minimum=resolved_minimum,
            maximum=resolved_maximum,
            curve=resolved_curve,
        )
        return {"profile": profile, "state": dialog.painter_action_state()}

    def paint_brush_resources_diagnose(self, *, preset: str = "") -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        from app.painter_brush_dynamics import brush_resource_diagnostics

        catalog = dialog._brush_presets_catalog()
        selected = None
        key = str(preset or "").strip().casefold()
        if key:
            selected = next((
                row for row in catalog
                if key in {
                    str(row.get("name") or "").strip().casefold(),
                    str(row.get("style") or "").strip().casefold(),
                }
            ), None)
            if selected is None:
                raise ValueError("Painter brush preset not found")
        elif 0 <= dialog._active_brush_preset_index < len(catalog):
            selected = catalog[dialog._active_brush_preset_index]
        if selected is None:
            raise ValueError("Painter brush preset not found")
        return {
            "preset": str(selected.get("name") or ""),
            **brush_resource_diagnostics(selected),
        }

    def paint_color_numeric_set(
        self,
        *,
        space: str,
        values: list[float],
        target: str = "foreground",
    ) -> dict[str, Any]:
        components = list(normalize_painter_numeric_color_components(values))
        dialog = self._paint_dialog_owner()
        return {
            "color": dialog._set_painter_numeric_color(space, components, target=target),
            "state": dialog.painter_action_state(),
        }

    def paint_adjustment_preview(
        self,
        *,
        type: str,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._preview_paint_adjustment(type, settings):
            raise ValueError("Painter adjustment preview could not start")
        return dialog.painter_action_state()

    def paint_adjustment_commit(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._commit_paint_adjustment():
            raise ValueError("Painter adjustment preview is not active")
        return dialog.painter_action_state()

    def paint_adjustment_cancel(self) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._cancel_paint_adjustment():
            raise ValueError("Painter adjustment preview is not active")
        return dialog.painter_action_state()

    def paint_adjustment_apply(
        self,
        *,
        type: str,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._apply_paint_adjustment(type, settings):
            raise ValueError("Painter adjustment could not be applied")
        return dialog.painter_action_state()

    def paint_adjustment_layer_create(
        self,
        *,
        type: str,
        settings: dict[str, Any] | None = None,
        name: str = "",
        use_selection: bool = True,
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        layer = dialog._new_adjustment_layer(
            type, settings, name=name or None, use_selection=use_selection
        )
        return {"layer_id": layer.layer_id, "state": dialog.painter_action_state()}

    def paint_adjustment_layer_update(
        self,
        *,
        layer_id: str,
        settings: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        if not dialog._update_adjustment_layer(layer_id, settings):
            raise ValueError("Painter adjustment layer could not be updated")
        return dialog.painter_action_state()

    def paint_palette_file_import(self, *, path: str) -> dict[str, Any]:
        return self._paint_dialog_owner()._import_named_palette(path)

    def paint_palette_file_export(self, *, path: str) -> dict[str, Any]:
        return self._paint_dialog_owner()._export_named_palette(path)

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
        rows = validate_paint_stroke_request(strokes)
        if not isinstance(undo_label, str):
            raise TypeError("Painter stroke undo_label must be a string")
        dialog = self._paint_dialog_owner()

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
            raw_points = list(row["points"])
            point_count += len(raw_points)
            path_mode = str(row["path_mode"])
            if path_mode == "smooth":
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
                if not math.isfinite(x) or not math.isfinite(y):
                    raise ValueError(
                        f"stroke {index} point {point_index} coordinates must be finite"
                    )
                if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
                    raise ValueError(
                        f"stroke {index} point {point_index} is outside normalized canvas bounds"
                    )
                points.append((x, y))
                channels = {
                    field: float(point[field])
                    for field in PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS
                }
                if not all(math.isfinite(value) for value in channels.values()):
                    raise ValueError(
                        f"stroke {index} point {point_index} channels must be finite"
                    )
                pressure.append(channels["pressure"])
                tilt.append(channels["tilt"])
                tilt_x.append(channels["tilt_x"])
                tilt_y.append(channels["tilt_y"])
                rotation.append(channels["rotation"])
                tangential_pressure.append(channels["tangential_pressure"])
                paint_load.append(channels["load"])

            layer_id = str(row.get("layer_id") or active_layer_id)
            layer = paint_layers.get(layer_id)
            if layer is None:
                raise ValueError(f"stroke {index} references unknown layer_id: {layer_id}")
            if bool(getattr(layer, "locked", False)):
                raise ValueError(f"stroke {index} targets locked layer_id: {layer_id}")

            color_value = str(row["color"])
            color = QColor(color_value)
            if not color.isValid():
                raise ValueError(f"stroke {index} has invalid color: {color_value}")
            opacity_percent = int(row["opacity"])
            is_material = str(getattr(layer, "layer_type", "standard") or "standard") == "material"
            engine_version = int(
                row.get(
                    "engine_version",
                    PAINT_ACTION_STROKE_ENGINE_VERSION_MAX
                    if is_material
                    else PAINT_ACTION_STROKE_ENGINE_VERSION_MIN,
                )
            )
            material = dict(PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS)
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
                    width_px=float(row["width"]),
                    brush_style=str(row["style"]),
                    brush_hardness=int(row["hardness"]),
                    brush_spacing=int(row["spacing"]),
                    brush_angle=int(row["angle"]),
                    brush_roundness=int(row["roundness"]),
                    closed_path=bool(row["closed"]),
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
                    bristle_count=int(row["bristle_count"]),
                    brush_seed=int(
                        row.get(
                            "seed",
                            index * PAINT_ACTION_STROKE_SEED_INDEX_FACTOR
                            + len(points) * PAINT_ACTION_STROKE_SEED_POINT_FACTOR,
                        )
                    ),
                    load_depletion=float(
                        row.get(
                            "load_depletion",
                            PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION,
                        )
                    ),
                    material_enabled=is_material,
                    material_load=float(material["load"]),
                    material_thickness=float(material["thickness"]),
                    material_wetness=float(material["wetness"]),
                    material_gloss=float(material["gloss"]),
                    material_roughness=float(material["roughness"]),
                    material_plow=float(material["plow"]),
                    material_resaturation=float(material["resaturation"]),
                    material_negative_depth=bool(material["negative_depth"]),
                    start_ms=self._paint_action_time_ms(None),
                )
            )
            rendered_point_count += len(points)

        selected_channel = str(getattr(dialog, "_selected_channel", "") or "")
        saved_channel = dialog._saved_selection_channel_by_id(selected_channel)
        if saved_channel is not None:
            if not dialog._apply_saved_selection_channel_strokes(
                prepared,
                undo_label=str(undo_label or "AI paint saved alpha channel"),
            ):
                raise ValueError("Painter saved alpha channel would not change")
            stroke_target = {
                "kind": "saved_selection_channel",
                "channel_id": selected_channel,
            }
        else:
            dialog._push_undo_state(str(undo_label or "AI paint strokes"))
            existing = dialog.canvas.embedded_strokes()
            dialog.canvas.set_strokes_snapshot([*existing, *prepared])
            dialog._update_inspector_counts()
            stroke_target = {"kind": "paint_layer", "layer_id": active_layer_id}
        state = dialog.painter_action_state()
        state["stroke_draw"] = {
            "stroke_count": len(prepared),
            "point_count": point_count,
            "rendered_point_count": rendered_point_count,
            "undo_label": str(undo_label or "AI paint strokes"),
            "coordinate_space": "normalized_canvas",
            "target": stroke_target,
            "request_resource_contract": dict(PAINT_ACTION_REQUEST_RESOURCE_CONTRACT),
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
        width: int = PAINT_ACTION_PBR_PREVIEW_DEFAULT_PX,
        settings: dict[str, Any] | None = None,
        allow_cpu: bool | None = None,
    ) -> dict[str, Any]:
        preview_width = normalize_painter_pbr_preview_width(width)
        if not path:
            import tempfile

            path = str(Path(tempfile.gettempdir()) / "tiger_painter_pbr" / f"painter_pbr_{preview_mode or 'material'}.png")
        dialog = self._paint_dialog_owner()
        return dialog.preview_pbr_map_to_path(
            path,
            preview_mode=str(preview_mode or "material"),
            preview_shape=str(preview_shape or "plane"),
            width=preview_width,
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
        limit: int = PAINT_ACTION_EDITOR_OBJECT_DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        time_ms, include_inactive, limit = validate_editor_objects_list_action(
            time_ms=time_ms, include_inactive=include_inactive, limit=limit
        )
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=include_inactive,
        )
        objects = [self._paint_object_payload(row) for row in rows[:limit]]
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
        validated = validate_editor_object_locator_action(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
            output_dir=output_dir,
            force=force,
        )
        obj = self._paint_find_import_object(
            object_id=str(validated["object_id"]),
            kind=str(validated["kind"]),
            time_ms=validated["time_ms"],
            include_inactive=bool(validated["include_inactive"]),
        )
        object_payload = self._paint_object_payload(obj)
        from app.drawing_editor_object_import import render_paint_import_object

        report = _paint_editor_object_render_report(
            render_paint_import_object(
                obj,
                canvas_size=self._paint_canvas_size(),
                output_dir=str(validated["output_dir"]) or None,
                force=bool(validated["force"]),
            ),
            obj,
        )
        return {
            "schema": "tigerstudio.actions.paint.editor_object.render.v1",
            "object": object_payload,
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
        validated = validate_editor_object_locator_action(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
            output_dir=output_dir,
            force=force,
        )
        geometry = validate_editor_object_import_geometry_action(
            x_norm=x_norm,
            y_norm=y_norm,
            width_norm=width_norm,
            height_norm=height_norm,
        )
        owner = self._require_owner()
        obj = self._paint_find_import_object(
            object_id=str(validated["object_id"]),
            kind=str(validated["kind"]),
            time_ms=validated["time_ms"],
            include_inactive=bool(validated["include_inactive"]),
        )
        object_payload = self._paint_object_payload(obj)
        from app.drawing import Sticker
        from app.drawing_editor_object_import import render_paint_import_object

        report = _paint_editor_object_render_report(
            render_paint_import_object(
                obj,
                canvas_size=self._paint_canvas_size(),
                output_dir=str(validated["output_dir"]) or None,
                force=bool(validated["force"]),
            ),
            obj,
        )
        raw_rect = report.get("rect_norm")
        rect = dict(raw_rect) if isinstance(raw_rect, dict) else {}
        w = (
            float(geometry["width_norm"])
            if geometry["width_norm"] is not None
            else _clamp_norm(
                rect.get("w", obj.width_norm),
                PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
                1.0,
            )
        )
        h = (
            float(geometry["height_norm"])
            if geometry["height_norm"] is not None
            else _clamp_norm(
                rect.get("h", obj.height_norm),
                PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
                1.0,
            )
        )
        x = (
            float(geometry["x_norm"])
            if geometry["x_norm"] is not None
            else _clamp_norm(rect.get("x", obj.x_norm), 0.0, 1.0 - w)
        )
        y = (
            float(geometry["y_norm"])
            if geometry["y_norm"] is not None
            else _clamp_norm(rect.get("y", obj.y_norm), 0.0, 1.0 - h)
        )
        if x + w > 1.0 or y + h > 1.0:
            raise ValueError("Painter editor object authored geometry must fit the canvas")
        stickers = getattr(owner, "_stickers", None)
        if stickers is None:
            stickers = []
            setattr(owner, "_stickers", stickers)
        start_ms = self._paint_action_time_ms(validated["time_ms"])
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
        refresh_errors: list[dict[str, str]] = []
        spawn = getattr(owner, "_spawn_sticker_item", None)
        if callable(spawn):
            try:
                spawn(sticker)
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("spawn_sticker_item", exc))
        update_visibility = getattr(owner, "_update_sticker_visibility", None)
        if callable(update_visibility):
            try:
                update_visibility(start_ms)
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("update_sticker_visibility", exc))
        canvas = getattr(owner, "_drawing_canvas", None)
        if canvas is not None and hasattr(canvas, "update"):
            try:
                canvas.update()
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("drawing_canvas_update", exc))
        self._register_change("Import editor object into paint")
        return {
            "schema": "tigerstudio.actions.paint.editor_object.import.v1",
            "object": object_payload,
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
            "ui_refresh": _paint_ui_refresh_status(refresh_errors),
        }

    def paint_3d_blockout_state(
        self,
        *,
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        dialog = self._paint_dialog_owner()
        scene = self._paint_3d_blockout_scene(dialog)
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_add(
        self,
        *,
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
        **params: Any,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        params = validate_blockout_primitive_action(
            params, require_authored_field=False
        )
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
        **params: Any,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        params = validate_blockout_primitive_action(
            params, require_authored_field=True
        )
        primitive_id = validate_blockout_primitive_id_action(primitive_id)
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        primitive_id = validate_blockout_primitive_id_action(primitive_id)
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        offset = validate_blockout_duplicate_offset_action(
            offset_x, offset_y, offset_z
        )
        primitive_id = validate_blockout_primitive_id_action(primitive_id)
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import duplicate_blockout_primitive

        scene = duplicate_blockout_primitive(
            self._paint_3d_blockout_scene(dialog),
            str(primitive_id or ""),
            offset=offset,
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        primitive_id = validate_blockout_primitive_id_action(primitive_id)
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        enabled, primitive_id = validate_blockout_snap_action(
            enabled=enabled, primitive_id=primitive_id
        )
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import set_blockout_snap, snap_blockout_primitive_to_grid

        scene = self._paint_3d_blockout_scene(dialog)
        if enabled is not None:
            scene = set_blockout_snap(scene, enabled)
        if primitive_id:
            scene = snap_blockout_primitive_to_grid(scene, primitive_id)
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Set Painter 3D blockout snap")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_camera(
        self,
        *,
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
        **params: Any,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        resolved_params = validate_blockout_camera_action(params)
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import update_blockout_camera

        scene = update_blockout_camera(
            self._paint_3d_blockout_scene(dialog), **resolved_params
        )
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        changes = validate_blockout_material_preview_action(
            {
                key: value
                for key, value in {
                    "material_lit": material_lit,
                    "show_floor": show_floor,
                    "show_shadows": show_shadows,
                    "show_fog": show_fog,
                    "show_depth": show_depth,
                    "light_yaw_degrees": light_yaw_degrees,
                    "light_pitch_degrees": light_pitch_degrees,
                }.items()
                if value is not None
            }
        )
        from dataclasses import replace

        dialog = self._paint_dialog_owner()
        scene = self._paint_3d_blockout_scene(dialog)
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
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        preset = validate_blockout_camera_preset_action(preset)
        dialog = self._paint_dialog_owner()
        from app.painter_3d_blockout import apply_blockout_camera_preset

        scene = apply_blockout_camera_preset(self._paint_3d_blockout_scene(dialog), preset)
        self._store_paint_3d_blockout_scene(dialog, scene)
        self._register_change("Apply Painter 3D blockout camera preset")
        return self._paint_3d_blockout_payload(scene, preview_width=preview_width, preview_height=preview_height)

    def paint_3d_blockout_bake(
        self,
        *,
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
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
        frame_size = optional_paint_export_size(width, height)
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
        if frame_size is None:
            frame_size = self._paint_export_size_for_owner(background)
        canvas_w, _canvas_h = self._paint_canvas_size()
        stroke_width_scale = float(frame_size[0]) / float(canvas_w)
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
            layer_rasters=dict(getattr(owner, "_paint_layer_rasters", {}) or {}),
        )
        return report

    def _paint_3d_blockout_scene(self, dialog: Any):
        from app.painter_3d_blockout import blockout_scene_from_dict

        return blockout_scene_from_dict(getattr(dialog, "_painter_3d_blockout_scene", None))

    def _store_paint_3d_blockout_scene(self, dialog: Any, scene: Any) -> dict[str, Any]:
        setattr(dialog, "_painter_3d_blockout_scene", scene.to_dict())
        setattr(dialog, "_painter_3d_blockout_flat_cache", None)
        refresh_errors: list[dict[str, str]] = []
        if scene.to_dict().get("primitive_count", 0):
            ensure_layer = getattr(dialog, "_ensure_3d_blockout_layer", None)
            if callable(ensure_layer):
                try:
                    ensure_layer()
                except Exception as exc:
                    refresh_errors.append(_paint_ui_refresh_error("ensure_3d_blockout_layer", exc))
        refresh = getattr(dialog, "_refresh_3d_blockout_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("refresh_3d_blockout_panel", exc))
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("paint_dialog_update", exc))
        status = _paint_ui_refresh_status(refresh_errors)
        setattr(dialog, "_painter_3d_blockout_ui_refresh", status)
        return status

    def _paint_3d_blockout_payload(
        self,
        scene: Any,
        *,
        preview_width: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_WIDTH_PX,
        preview_height: int = PAINT_ACTION_BLOCKOUT_PREVIEW_DEFAULT_HEIGHT_PX,
    ) -> dict[str, Any]:
        from app.painter_3d_blockout import project_blockout_scene
        from app.painter_opengl import PAINTER_OPENGL_RENDERER_ID

        preview_width, preview_height = validate_blockout_preview_action(
            preview_width, preview_height
        )
        projection = project_blockout_scene(scene, preview_width, preview_height)
        dialog = self._paint_dialog_owner()
        try:
            renderer_status = dict(getattr(dialog, "_painter_3d_blockout_renderer_status", {}) or {})
            renderer_status_error = None
        except (TypeError, ValueError) as exc:
            renderer_status = {}
            renderer_status_error = {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        return {
            "schema": "tigerstudio.actions.paint.3d_blockout.v1",
            "scene": scene.to_dict(),
            "projection": projection,
            "renderer": {
                "preferred": PAINTER_OPENGL_RENDERER_ID,
                "fallback": "painter_blockout_qpainter_v1",
                "last_render": renderer_status,
                "status_error": renderer_status_error,
                "remote_safe": True,
            },
            "ui_refresh": dict(
                getattr(
                    dialog,
                    "_painter_3d_blockout_ui_refresh",
                    _paint_ui_refresh_status([], committed=False, attempted=False),
                )
                or {}
            ),
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
            from PySide6.QtCore import QObject

            if isinstance(candidate, QObject):
                from shiboken6 import Shiboken

                if not Shiboken.isValid(candidate):
                    continue
            if hasattr(candidate, "isVisible") and not candidate.isVisible():
                continue
            return candidate
        raise ValueError("no active Painter dialog")

    def _paint_action_time_ms(self, time_ms: int | None) -> int:
        if time_ms is not None:
            return normalize_paint_time_ms(time_ms)
        owner = self._require_owner()
        if hasattr(owner, "_time_ms"):
            return normalize_paint_time_ms(owner._time_ms)
        player = getattr(owner, "_player", None)
        position = getattr(player, "position", None)
        if callable(position):
            return normalize_paint_time_ms(position())
        return 0

    def _paint_canvas_size(self) -> tuple[int, int]:
        owner = self._require_owner()
        document_size = getattr(owner, "_canvas_document_size", None)
        if isinstance(document_size, (list, tuple)) and len(document_size) == 2:
            width = _paint_positive_extent(document_size[0])
            height = _paint_positive_extent(document_size[1])
            if width is not None and height is not None:
                return width, height
        for name in ("_drawing_canvas", "_preview_label", "_preview_widget"):
            widget = getattr(owner, name, None)
            if widget is not None:
                width = _paint_positive_extent(widget.width())
                height = _paint_positive_extent(widget.height())
                if width is not None and height is not None:
                    return (width, height)
        pixmap = getattr(owner, "_preview_pixmap", None)
        if pixmap is not None:
            width = _paint_positive_extent(pixmap.width())
            height = _paint_positive_extent(pixmap.height())
            if width is not None and height is not None:
                return (width, height)
        raise ValueError("Painter canvas dimensions are unavailable")

    def _paint_export_size_for_owner(self, background: Any) -> tuple[int, int]:
        if background is not None:
            width = _paint_positive_extent(background.width())
            height = _paint_positive_extent(background.height())
            if width is not None and height is not None:
                return (width, height)
        return self._paint_canvas_size()

    def _paint_find_import_object(
        self,
        *,
        object_id: str = "",
        kind: str = "",
        time_ms: int | None = None,
        include_inactive: bool = True,
    ):
        validated = validate_editor_object_locator_action(
            object_id=object_id,
            kind=kind,
            time_ms=time_ms,
            include_inactive=include_inactive,
        )
        object_id = str(validated["object_id"])
        kind = str(validated["kind"])
        time_ms = validated["time_ms"]
        include_inactive = bool(validated["include_inactive"])
        owner = self._require_owner()
        target_ms = self._paint_action_time_ms(time_ms)
        from app.drawing_editor_object_import import collect_editor_paint_objects

        rows = collect_editor_paint_objects(
            owner,
            time_ms=target_ms,
            include_inactive=include_inactive,
        )
        wanted_id = object_id
        wanted_kind = kind
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
        width = _clamp_norm(
            getattr(obj, "width_norm", PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM),
            PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
            1.0,
        )
        height = _clamp_norm(
            getattr(obj, "height_norm", PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM),
            PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
            1.0,
        )
        return {
            "id": str(getattr(obj, "id", "")),
            "kind": str(getattr(obj, "kind", "")),
            "label": str(getattr(obj, "label", "")),
            "source_path": str(getattr(obj, "source_path", "")),
            "active": bool(getattr(obj, "active", False)),
            "start_ms": _paint_fallback_integer(getattr(obj, "start_ms", 0), 0),
            "end_ms": _paint_fallback_integer(getattr(obj, "end_ms", -1), -1),
            "x_norm": _clamp_norm(getattr(obj, "x_norm", 0.0), 0.0, 1.0 - width),
            "y_norm": _clamp_norm(getattr(obj, "y_norm", 0.0), 0.0, 1.0 - height),
            "width_norm": width,
            "height_norm": height,
            "payload": _paint_json_safe_copy(
                dict(getattr(obj, "payload", {}) or {}),
                field="Painter editor object payload",
            ),
        }

    def _paint_reference_board(self, dialog: Any):
        from app.painter_reference_board import reference_board_from_dict

        return reference_board_from_dict(getattr(dialog, "_painter_reference_board", None))

    def _apply_paint_reference_color_atomic(
        self,
        dialog: Any,
        color: Any,
        *,
        remember: bool,
    ) -> None:
        from PySide6.QtGui import QColor

        previous = {
            "pen": QColor(getattr(dialog, "_pen_color", QColor())),
            "previous_pen": QColor(getattr(dialog, "_previous_pen_color", QColor())),
            "recent": list(getattr(dialog, "_recent_colors", []) or []),
            "document": list(getattr(dialog, "_document_palette_colors", []) or []),
            "dirty": bool(getattr(dialog, "_painter_document_dirty", False)),
        }
        try:
            dialog._apply_pen_color(QColor(color), remember=remember)
        except Exception:
            dialog._pen_color = previous["pen"]
            dialog._previous_pen_color = previous["previous_pen"]
            dialog._recent_colors = previous["recent"]
            dialog._document_palette_colors = previous["document"]
            dialog._painter_document_dirty = previous["dirty"]
            canvas = getattr(dialog, "canvas", None)
            if canvas is not None:
                try:
                    canvas.set_pen_color(previous["pen"])
                except Exception as rollback_exc:
                    raise RuntimeError(
                        "Painter reference color rollback failed: "
                        f"{type(rollback_exc).__name__}: {rollback_exc}"
                    ) from rollback_exc
            raise

    def _store_paint_reference_board(self, dialog: Any, board: Any) -> dict[str, Any]:
        setattr(dialog, "_painter_reference_board", board.to_dict())
        refresh_errors: list[dict[str, str]] = []
        refresh = getattr(dialog, "_refresh_reference_board_panel", None)
        if callable(refresh):
            try:
                refresh()
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("refresh_reference_board_panel", exc))
        update = getattr(dialog, "update", None)
        if callable(update):
            try:
                update()
            except Exception as exc:
                refresh_errors.append(_paint_ui_refresh_error("paint_dialog_update", exc))
        status = _paint_ui_refresh_status(refresh_errors)
        setattr(dialog, "_painter_reference_ui_refresh", status)
        return status

    def _paint_reference_payload(self, dialog: Any) -> dict[str, Any]:
        board = self._paint_reference_board(dialog)
        selected = str(getattr(dialog, "_painter_reference_selected_id", "") or "")
        return {
            "schema": "tigerstudio.actions.paint.reference_board.v1",
            "board": board.to_dict(),
            "selected_reference_id": selected,
            "ui_refresh": dict(
                getattr(
                    dialog,
                    "_painter_reference_ui_refresh",
                    _paint_ui_refresh_status([], committed=False, attempted=False),
                )
                or {}
            ),
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
        x_norm: float = REFERENCE_DEFAULT_X_NORM,
        y_norm: float = REFERENCE_DEFAULT_Y_NORM,
        width_norm: float = REFERENCE_DEFAULT_WIDTH_NORM,
        height_norm: float = REFERENCE_DEFAULT_HEIGHT_NORM,
        opacity: float = REFERENCE_DEFAULT_OPACITY,
        rotation_deg: float = REFERENCE_DEFAULT_ROTATION_DEGREES,
        visible: bool = True,
        locked: bool = False,
    ) -> dict[str, Any]:
        validated = validate_reference_add_action(
            path=path,
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
        dialog = self._paint_dialog_owner()
        from app.painter_reference_board import add_reference_image

        board = add_reference_image(
            self._paint_reference_board(dialog),
            **validated,
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_update(
        self,
        *,
        reference_id: object = PAINTER_ACTION_INPUT_UNSET,
        name: object = PAINTER_ACTION_INPUT_UNSET,
        x_norm: object = PAINTER_ACTION_INPUT_UNSET,
        y_norm: object = PAINTER_ACTION_INPUT_UNSET,
        width_norm: object = PAINTER_ACTION_INPUT_UNSET,
        height_norm: object = PAINTER_ACTION_INPUT_UNSET,
        opacity: object = PAINTER_ACTION_INPUT_UNSET,
        rotation_deg: object = PAINTER_ACTION_INPUT_UNSET,
        visible: object = PAINTER_ACTION_INPUT_UNSET,
        locked: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        reference_id, changes = validate_reference_update_action(
            reference_id=reference_id,
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
        dialog = self._paint_dialog_owner()
        target = reference_id
        from app.painter_reference_board import update_reference_image

        board = update_reference_image(
            self._paint_reference_board(dialog),
            target,
            **changes,
        )
        setattr(dialog, "_painter_reference_selected_id", target)
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_delete(
        self,
        *,
        reference_id: object = PAINTER_ACTION_INPUT_UNSET,
    ) -> dict[str, Any]:
        reference_id = validate_reference_id_action(reference_id, allow_empty=False)
        dialog = self._paint_dialog_owner()
        target = reference_id
        from app.painter_reference_board import delete_reference_image

        board = delete_reference_image(self._paint_reference_board(dialog), target)
        rows = board.to_dict().get("references", [])
        setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or "") if rows else "")
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_duplicate(
        self,
        *,
        reference_id: object = PAINTER_ACTION_INPUT_UNSET,
        offset_x: float = REFERENCE_DUPLICATE_OFFSET_NORM,
        offset_y: float = REFERENCE_DUPLICATE_OFFSET_NORM,
    ) -> dict[str, Any]:
        reference_id, offset_x, offset_y = validate_reference_duplicate_action(
            reference_id=reference_id,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        dialog = self._paint_dialog_owner()
        target = reference_id
        from app.painter_reference_board import duplicate_reference_image

        board = duplicate_reference_image(
            self._paint_reference_board(dialog),
            target,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        rows = board.to_dict().get("references", [])
        if rows:
            setattr(dialog, "_painter_reference_selected_id", str(rows[-1].get("id") or ""))
        self._store_paint_reference_board(dialog, board)
        return self._paint_reference_payload(dialog)

    def paint_reference_bake(self, *, reference_id: str = "") -> dict[str, Any]:
        reference_id = validate_reference_id_action(reference_id)
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
        (
            resolved_reference_id,
            resolved_x_norm,
            resolved_y_norm,
            resolved_apply,
        ) = validate_reference_sample_action(
            reference_id=reference_id,
            x_norm=x_norm,
            y_norm=y_norm,
            apply=apply,
        )
        dialog = self._paint_dialog_owner()
        target = resolved_reference_id or str(
            getattr(dialog, "_painter_reference_selected_id", "") or ""
        )
        rows = self._paint_reference_board(dialog).to_dict().get("references", [])
        reference = next(
            (row for row in rows if str(row.get("id") or "") == target),
            None,
        )
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import sample_reference_color
        from PySide6.QtGui import QColor

        sample = sample_reference_color(
            str(reference.get("path") or ""),
            x_norm=resolved_x_norm,
            y_norm=resolved_y_norm,
        )
        if resolved_apply:
            rgb = sample.get("rgb", [255, 255, 255])
            self._apply_paint_reference_color_atomic(
                dialog,
                QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])),
                remember=True,
            )
        if resolved_reference_id:
            setattr(dialog, "_painter_reference_selected_id", resolved_reference_id)
        return {
            **self._paint_reference_payload(dialog),
            "sample": sample,
            "applied_to_foreground": resolved_apply,
        }

    def paint_reference_extract_palette(
        self,
        *,
        reference_id: str = "",
        max_colors: int = PAINT_ACTION_DEFAULT_REFERENCE_COLORS,
        apply: bool = True,
    ) -> dict[str, Any]:
        resolved_reference_id, resolved_max_colors, resolved_apply = (
            validate_reference_palette_action(
                reference_id=reference_id,
                max_colors=max_colors,
                apply=apply,
            )
        )
        dialog = self._paint_dialog_owner()
        target = resolved_reference_id or str(
            getattr(dialog, "_painter_reference_selected_id", "") or ""
        )
        rows = self._paint_reference_board(dialog).to_dict().get("references", [])
        reference = next(
            (row for row in rows if str(row.get("id") or "") == target),
            None,
        )
        if not reference:
            raise ValueError("Painter reference not found")
        from app.painter_reference_board import extract_reference_palette
        from PySide6.QtGui import QColor

        palette = extract_reference_palette(
            str(reference.get("path") or ""),
            max_colors=resolved_max_colors,
        )
        applied_colors: list[tuple[int, int, int]] = []
        if resolved_apply:
            for row in palette.get("colors", []) or []:
                rgb = row.get("rgb")
                if isinstance(rgb, list) and len(rgb) >= 3:
                    applied_colors.append((int(rgb[0]), int(rgb[1]), int(rgb[2])))
            if applied_colors:
                limit = len(getattr(dialog, "_recent_colors", []) or []) or 5
                self._apply_paint_reference_color_atomic(
                    dialog,
                    QColor(*applied_colors[0]),
                    remember=False,
                )
                dialog._recent_colors = applied_colors[:limit]
        if resolved_reference_id:
            setattr(dialog, "_painter_reference_selected_id", resolved_reference_id)
        return {
            **self._paint_reference_payload(dialog),
            "palette": palette,
            "applied_to_recent_colors": bool(resolved_apply and applied_colors),
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
        region_count: int = PAINT_ACTION_DEFAULT_STUDY_REGIONS,
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
            max_regions=int(region_count or PAINT_ACTION_DEFAULT_STUDY_REGIONS),
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
                max_strokes=int(max_strokes or PAINT_ACTION_DEFAULT_STUDY_STROKES),
                seed_offset=int(seed_offset or 0),
            )
        else:
            generated = generate_phase_strokes(
                runtime,
                phase=str(phase),
                layer_id=layer_id,
                max_strokes=int(max_strokes or PAINT_ACTION_DEFAULT_STUDY_STROKES),
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
        max_strokes: int = PAINT_ACTION_DEFAULT_STUDY_STROKES,
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
        max_strokes: int = PAINT_ACTION_DEFAULT_STUDY_STROKES,
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
        max_strokes: int = PAINT_ACTION_DEFAULT_STUDY_STROKES,
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
            strokes=dialog.canvas.embedded_strokes(),
            bubbles=[],
            stickers=[],
            time_ms=int(dialog._time_ms),
            frame_size=(width, height),
            stroke_width_scale=1.0,
            paint_layers=list(getattr(dialog, "_paint_layers", []) or []),
            layer_rasters=dict(getattr(dialog, "_paint_layer_rasters", {}) or {}),
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
        max_strokes: int = PAINT_ACTION_DEFAULT_STUDY_STROKES,
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
    except (TypeError, ValueError, OverflowError):
        number = lo
    if not math.isfinite(number):
        number = lo
    return max(lo, min(hi, number))


def _paint_fallback_integer(value: Any, fallback: int) -> int:
    if isinstance(value, bool):
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return fallback


def _paint_json_safe_copy(value: Any, *, field: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{field} must not contain NaN or infinity")
        return value
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{field} keys must be strings")
            result[key] = _paint_json_safe_copy(item, field=f"{field}.{key}")
        return result
    if isinstance(value, (list, tuple)):
        return [
            _paint_json_safe_copy(item, field=f"{field}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{field} contains a non-JSON value")


def _paint_editor_object_render_report(report: Any, obj: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        raise TypeError("Painter editor object render report must be an object")
    normalized = copy.deepcopy(report)
    raw_rect = normalized.get("rect_norm")
    rect = raw_rect if isinstance(raw_rect, dict) else {}
    width = _clamp_norm(
        rect.get("w", getattr(obj, "width_norm", PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM)),
        PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
        1.0,
    )
    height = _clamp_norm(
        rect.get("h", getattr(obj, "height_norm", PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM)),
        PAINT_ACTION_EDITOR_OBJECT_MIN_SIZE_NORM,
        1.0,
    )
    normalized["rect_norm"] = {
        "x": _clamp_norm(rect.get("x", getattr(obj, "x_norm", 0.0)), 0.0, 1.0 - width),
        "y": _clamp_norm(rect.get("y", getattr(obj, "y_norm", 0.0)), 0.0, 1.0 - height),
        "w": width,
        "h": height,
    }
    return _paint_json_safe_copy(normalized, field="Painter editor object render report")


def _paint_ui_refresh_error(operation: str, exc: BaseException) -> dict[str, str]:
    return {
        "operation": str(operation),
        "type": type(exc).__name__,
        "message": str(exc),
    }


def _paint_ui_refresh_status(
    errors: list[dict[str, str]],
    *,
    committed: bool = True,
    attempted: bool = True,
) -> dict[str, Any]:
    return {
        "attempted": bool(attempted),
        "committed": bool(committed),
        "ok": not errors,
        "errors": list(errors),
    }


def _looks_like_paint_dialog(candidate: Any) -> bool:
    if candidate is None:
        return False
    return bool(
        hasattr(candidate, "canvas")
        and callable(getattr(candidate, "painter_action_state", None))
        and callable(getattr(candidate, "export_png_to_path", None))
    )


__all__ = ["PaintAdapterMixin"]
