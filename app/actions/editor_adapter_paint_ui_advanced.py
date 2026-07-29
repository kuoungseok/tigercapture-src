"""Advanced Painter UI action implementations kept outside the legacy adapter."""
from __future__ import annotations

from typing import Any


class PaintUIAdvancedAdapterMixin:
    def _paint_ui_advanced_apply(
        self,
        label: str,
        document: dict[str, Any],
    ) -> dict[str, Any]:
        dialog = self._paint_dialog_owner()
        dialog._push_undo_state(label)
        return self._paint_ui_commit(dialog, label, document)

    def paint_ui_object_duplicate_to_artboard(
        self,
        *,
        object_ids: list[str] | None = None,
        target_artboard_id: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_cross_artboard import (
            duplicate_ui_selection_to_artboard,
        )

        dialog = self._paint_dialog_owner()
        document, report = duplicate_ui_selection_to_artboard(
            dialog._painter_ui_document,
            object_ids=object_ids,
            target_artboard_id=target_artboard_id,
        )
        result = self._paint_ui_advanced_apply(
            "Duplicate UI selection to artboard",
            document,
        )
        return {**result, "duplicate": report}

    def paint_ui_object_duplicate(
        self,
        *,
        object_ids: list[str] | None = None,
        offset_x: float = 12.0,
        offset_y: float = 12.0,
    ) -> dict[str, Any]:
        from app.painter_ui_duplicate import duplicate_ui_selection

        dialog = self._paint_dialog_owner()
        document, report = duplicate_ui_selection(
            dialog._painter_ui_document,
            object_ids=object_ids,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        result = self._paint_ui_advanced_apply(
            "Duplicate UI selection",
            document,
        )
        return {**result, "duplicate": report}

    def paint_ui_object_paste_in_place(
        self,
        *,
        object_ids: list[str] | None = None,
        clipboard: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from app.painter_ui_duplicate import duplicate_ui_selection

        dialog = self._paint_dialog_owner()
        payload = clipboard or getattr(
            dialog,
            "_painter_ui_property_clipboard",
            None,
        )
        source_ids = list(object_ids or [])
        if not source_ids and isinstance(payload, dict):
            source_id = str(payload.get("source_object_id") or "")
            if source_id:
                source_ids = [source_id]
        if not source_ids:
            raise ValueError("Copy a Painter UI object before pasting in place")
        document, report = duplicate_ui_selection(
            dialog._painter_ui_document,
            object_ids=source_ids,
            offset_x=0.0,
            offset_y=0.0,
        )
        result = self._paint_ui_advanced_apply(
            "Paste UI objects in place",
            document,
        )
        return {**result, "paste_in_place": report}

    def paint_ui_dev_measurement_inspect(
        self,
        *,
        object_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        from app.painter_ui_measurements import (
            inspect_ui_selection_measurements,
        )

        dialog = self._paint_dialog_owner()
        return inspect_ui_selection_measurements(
            dialog._painter_ui_document,
            object_ids=object_ids,
        )

    def paint_ui_smart_guide_inspect(
        self,
        *,
        object_id: str,
        x: float,
        y: float,
        excluded_object_ids: list[str] | None = None,
        tolerance: float = 6.0,
    ) -> dict[str, Any]:
        from app.painter_ui_smart_guides import plan_ui_move_guides

        dialog = self._paint_dialog_owner()
        return plan_ui_move_guides(
            dialog._painter_ui_document,
            object_id=object_id,
            x=x,
            y=y,
            excluded_object_ids=excluded_object_ids or [],
            tolerance=tolerance,
        )

    def paint_ui_mask_inspect(self, *, object_id: str) -> dict[str, Any]:
        from app.painter_ui_masks import inspect_ui_mask

        dialog = self._paint_dialog_owner()
        return inspect_ui_mask(dialog._painter_ui_document, object_id)

    def paint_ui_mask_create(
        self,
        *,
        object_id: str,
        target_ids: list[str] | None = None,
        inverted: bool = False,
        outline: bool = False,
    ) -> dict[str, Any]:
        from app.painter_ui_masks import create_ui_mask

        dialog = self._paint_dialog_owner()
        document, row = create_ui_mask(
            dialog._painter_ui_document,
            object_id,
            target_ids=target_ids,
            inverted=inverted,
            outline=outline,
        )
        result = self._paint_ui_advanced_apply("Create UI mask", document)
        return {**result, "mask": row["mask"]}

    def paint_ui_mask_update(
        self,
        *,
        object_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        from app.painter_ui_masks import update_ui_mask

        dialog = self._paint_dialog_owner()
        document, row = update_ui_mask(
            dialog._painter_ui_document,
            object_id,
            changes,
        )
        result = self._paint_ui_advanced_apply("Update UI mask", document)
        return {**result, "mask": row["mask"]}

    def paint_ui_mask_remove(self, *, object_id: str) -> dict[str, Any]:
        from app.painter_ui_masks import remove_ui_mask

        dialog = self._paint_dialog_owner()
        document = remove_ui_mask(dialog._painter_ui_document, object_id)
        return self._paint_ui_advanced_apply("Release UI mask", document)

    def paint_ui_mask_reorder(
        self,
        *,
        object_id: str,
        target_ids: list[str],
    ) -> dict[str, Any]:
        from app.painter_ui_masks import reorder_ui_mask_targets

        dialog = self._paint_dialog_owner()
        document, row = reorder_ui_mask_targets(
            dialog._painter_ui_document,
            object_id,
            target_ids,
        )
        result = self._paint_ui_advanced_apply("Reorder UI mask", document)
        return {**result, "mask": row["mask"]}

    def paint_ui_appearance_advanced_inspect(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        from app.painter_ui_advanced_appearance import (
            inspect_ui_advanced_appearance,
        )

        dialog = self._paint_dialog_owner()
        return inspect_ui_advanced_appearance(
            dialog._painter_ui_document,
            object_id,
        )

    def paint_ui_appearance_blend_set(
        self,
        *,
        object_id: str,
        blend_mode: str,
    ) -> dict[str, Any]:
        from app.painter_ui_advanced_appearance import (
            set_ui_object_blend_mode,
        )

        dialog = self._paint_dialog_owner()
        document, row = set_ui_object_blend_mode(
            dialog._painter_ui_document,
            object_id,
            blend_mode,
        )
        result = self._paint_ui_advanced_apply("Set UI blend mode", document)
        return {**result, "object": row}

    def _paint_ui_paint_mutate(
        self,
        *,
        object_id: str,
        stack: str,
        operation: str,
        paint: dict[str, Any] | None = None,
        index: int = -1,
        target_index: int = -1,
    ) -> dict[str, Any]:
        from app.painter_ui_advanced_appearance import mutate_ui_paint

        dialog = self._paint_dialog_owner()
        document, row = mutate_ui_paint(
            dialog._painter_ui_document,
            object_id,
            stack=stack,
            operation=operation,
            paint=paint,
            index=index,
            target_index=target_index,
        )
        result = self._paint_ui_advanced_apply(
            f"{operation.title()} UI {stack} paint",
            document,
        )
        return {**result, "paint": row}

    def paint_ui_appearance_paint_add(self, **params) -> dict[str, Any]:
        return self._paint_ui_paint_mutate(operation="add", **params)

    def paint_ui_appearance_paint_update(self, **params) -> dict[str, Any]:
        return self._paint_ui_paint_mutate(operation="update", **params)

    def paint_ui_appearance_paint_remove(self, **params) -> dict[str, Any]:
        return self._paint_ui_paint_mutate(operation="remove", **params)

    def paint_ui_appearance_paint_reorder(self, **params) -> dict[str, Any]:
        return self._paint_ui_paint_mutate(operation="reorder", **params)

    def paint_ui_appearance_corner_set(
        self,
        *,
        object_id: str,
        corner_radii: dict[str, Any],
    ) -> dict[str, Any]:
        from app.painter_ui_advanced_appearance import set_ui_corner_geometry

        dialog = self._paint_dialog_owner()
        document, row = set_ui_corner_geometry(
            dialog._painter_ui_document,
            object_id,
            corner_radii=corner_radii,
        )
        result = self._paint_ui_advanced_apply("Set UI corner radii", document)
        return {**result, "object": row}

    def paint_ui_appearance_stroke_set(
        self,
        *,
        object_id: str,
        stroke_align: str,
    ) -> dict[str, Any]:
        from app.painter_ui_advanced_appearance import set_ui_corner_geometry

        dialog = self._paint_dialog_owner()
        document, row = set_ui_corner_geometry(
            dialog._painter_ui_document,
            object_id,
            stroke_align=stroke_align,
        )
        result = self._paint_ui_advanced_apply(
            "Set UI stroke alignment",
            document,
        )
        return {**result, "object": row}

    def paint_ui_text_range_style_inspect(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        from app.painter_ui_text_ranges import inspect_ui_text_ranges

        dialog = self._paint_dialog_owner()
        return inspect_ui_text_ranges(dialog._painter_ui_document, object_id)

    def paint_ui_text_range_style_set(
        self,
        *,
        object_id: str,
        start: int,
        end: int,
        style: dict[str, Any],
    ) -> dict[str, Any]:
        from app.painter_ui_text_ranges import set_ui_text_range_style

        dialog = self._paint_dialog_owner()
        document, row = set_ui_text_range_style(
            dialog._painter_ui_document,
            object_id,
            start,
            end,
            style,
        )
        result = self._paint_ui_advanced_apply("Set mixed text style", document)
        return {**result, "range": row}

    def paint_ui_text_range_style_remove(
        self,
        *,
        object_id: str,
        start: int,
        end: int,
    ) -> dict[str, Any]:
        from app.painter_ui_text_ranges import remove_ui_text_range_style

        dialog = self._paint_dialog_owner()
        document = remove_ui_text_range_style(
            dialog._painter_ui_document,
            object_id,
            start,
            end,
        )
        return self._paint_ui_advanced_apply("Remove mixed text style", document)

    def paint_ui_component_remote_inspect(
        self,
        *,
        object_id: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_remote_components import inspect_remote_components

        dialog = self._paint_dialog_owner()
        return inspect_remote_components(
            dialog._painter_ui_document,
            object_id=object_id,
        )

    def paint_ui_component_remote_relink(self, **params) -> dict[str, Any]:
        from app.painter_ui_remote_components import relink_remote_component

        dialog = self._paint_dialog_owner()
        document, row = relink_remote_component(
            dialog._painter_ui_document,
            **params,
        )
        result = self._paint_ui_advanced_apply(
            "Relink remote UI component",
            document,
        )
        return {**result, "object": row}

    def paint_ui_component_remote_localize(self, **params) -> dict[str, Any]:
        from app.painter_ui_remote_components import localize_remote_component

        dialog = self._paint_dialog_owner()
        document, row = localize_remote_component(
            dialog._painter_ui_document,
            **params,
        )
        result = self._paint_ui_advanced_apply(
            "Localize remote UI component",
            document,
        )
        return {**result, "object": row}

    def paint_ui_component_remote_replace(self, **params) -> dict[str, Any]:
        from app.painter_ui_remote_components import replace_remote_component

        dialog = self._paint_dialog_owner()
        document, row = replace_remote_component(
            dialog._painter_ui_document,
            **params,
        )
        result = self._paint_ui_advanced_apply(
            "Replace remote UI component",
            document,
        )
        return {**result, "object": row}

    def paint_ui_vector_boolean_inspect(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        from app.painter_ui_boolean import inspect_ui_boolean

        dialog = self._paint_dialog_owner()
        return inspect_ui_boolean(dialog._painter_ui_document, object_id)

    def paint_ui_vector_boolean_set(
        self,
        *,
        object_id: str,
        operation: str,
        operand_ids: list[str],
    ) -> dict[str, Any]:
        from app.painter_ui_boolean import set_ui_boolean

        dialog = self._paint_dialog_owner()
        document, row = set_ui_boolean(
            dialog._painter_ui_document,
            object_id,
            operation,
            operand_ids,
        )
        result = self._paint_ui_advanced_apply("Set UI Boolean", document)
        return {**result, "object": row}

    def paint_ui_vector_boolean_compose(
        self,
        *,
        operation: str,
        operand_ids: list[str] | None = None,
        name: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_boolean import compose_ui_boolean

        dialog = self._paint_dialog_owner()
        selected = list(
            operand_ids
            or dialog._painter_ui_document["selection"]["object_ids"]
        )
        document, row = compose_ui_boolean(
            dialog._painter_ui_document,
            operation,
            selected,
            name=name,
        )
        result = self._paint_ui_advanced_apply(
            "Create UI Boolean group",
            document,
        )
        return {**result, "object": row}

    def paint_ui_vector_boolean_release(
        self,
        *,
        object_id: str,
    ) -> dict[str, Any]:
        from app.painter_ui_boolean import release_ui_boolean

        dialog = self._paint_dialog_owner()
        document = release_ui_boolean(dialog._painter_ui_document, object_id)
        return self._paint_ui_advanced_apply("Release UI Boolean", document)

    def paint_ui_section_inspect(
        self,
        *,
        section_id: str = "",
    ) -> dict[str, Any]:
        from app.painter_ui_sections import inspect_ui_sections

        dialog = self._paint_dialog_owner()
        return inspect_ui_sections(
            dialog._painter_ui_document,
            section_id=section_id,
        )

    def paint_ui_section_create(
        self,
        *,
        section: dict[str, Any],
    ) -> dict[str, Any]:
        from app.painter_ui_sections import create_ui_section

        dialog = self._paint_dialog_owner()
        document, row = create_ui_section(
            dialog._painter_ui_document,
            section,
        )
        result = self._paint_ui_advanced_apply("Create UI section", document)
        return {**result, "section": row}

    def paint_ui_section_update(
        self,
        *,
        section_id: str,
        changes: dict[str, Any],
    ) -> dict[str, Any]:
        from app.painter_ui_sections import update_ui_section

        dialog = self._paint_dialog_owner()
        document, row = update_ui_section(
            dialog._painter_ui_document,
            section_id,
            changes,
        )
        result = self._paint_ui_advanced_apply("Update UI section", document)
        return {**result, "section": row}

    def paint_ui_section_remove(self, *, section_id: str) -> dict[str, Any]:
        from app.painter_ui_sections import remove_ui_section

        dialog = self._paint_dialog_owner()
        document = remove_ui_section(
            dialog._painter_ui_document,
            section_id,
        )
        return self._paint_ui_advanced_apply("Remove UI section", document)


__all__ = ["PaintUIAdvancedAdapterMixin"]
