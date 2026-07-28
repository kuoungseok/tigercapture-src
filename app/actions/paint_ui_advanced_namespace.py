"""Registrations for advanced Painter UI/Figma authoring workflows."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


_ID = {"type": "string"}
_ID_LIST = {"type": "array", "items": {"type": "string"}}
_OBJECT = {"type": "object", "additionalProperties": True}


def _register(
    registry: Any,
    name: str,
    description: str,
    method: str,
    properties: dict[str, Any],
    *,
    required: tuple[str, ...] = (),
    mutating: bool = True,
    undo_label: str = "",
) -> None:
    kwargs: dict[str, Any] = {
        "params_schema": schema_object(properties, required=required),
        "required": required,
        "mutating": mutating,
        "changed": mutating,
        "dry_summary": f"{description.rstrip('.').casefold()} would run",
    }
    if undo_label:
        kwargs["undo_label"] = undo_label
    registry.register_adapter_action(
        name,
        description,
        "paint",
        method,
        **kwargs,
    )


def register_paint_ui_advanced_actions(registry: Any) -> None:
    _register(
        registry,
        "paint.ui.mask.inspect",
        "Inspect a Painter UI object mask and ordered targets.",
        "paint_ui_mask_inspect",
        {"object_id": _ID},
        required=("object_id",),
        mutating=False,
    )
    _register(
        registry,
        "paint.ui.mask.create",
        "Use a Painter UI object as an editable mask.",
        "paint_ui_mask_create",
        {
            "object_id": _ID,
            "target_ids": _ID_LIST,
            "inverted": {"type": "boolean"},
            "outline": {"type": "boolean"},
        },
        required=("object_id",),
        undo_label="Create UI mask",
    )
    _register(
        registry,
        "paint.ui.mask.update",
        "Update mask visibility, inversion, outline, or targets.",
        "paint_ui_mask_update",
        {"object_id": _ID, "changes": _OBJECT},
        required=("object_id", "changes"),
        undo_label="Update UI mask",
    )
    _register(
        registry,
        "paint.ui.mask.remove",
        "Release a Painter UI mask without deleting its source object.",
        "paint_ui_mask_remove",
        {"object_id": _ID},
        required=("object_id",),
        undo_label="Release UI mask",
    )
    _register(
        registry,
        "paint.ui.mask.reorder",
        "Set the ordered target list for a Painter UI mask.",
        "paint_ui_mask_reorder",
        {"object_id": _ID, "target_ids": _ID_LIST},
        required=("object_id", "target_ids"),
        undo_label="Reorder UI mask",
    )
    _register(
        registry,
        "paint.ui.appearance.advanced.inspect",
        "Inspect blend, Fill/Stroke stacks, corners, and stroke alignment.",
        "paint_ui_appearance_advanced_inspect",
        {"object_id": _ID},
        required=("object_id",),
        mutating=False,
    )
    _register(
        registry,
        "paint.ui.appearance.blend.set",
        "Set a Painter UI object blend mode.",
        "paint_ui_appearance_blend_set",
        {"object_id": _ID, "blend_mode": {"type": "string"}},
        required=("object_id", "blend_mode"),
        undo_label="Set UI blend mode",
    )
    paint_common = {
        "object_id": _ID,
        "stack": {"type": "string", "enum": ["fill", "stroke"]},
        "paint": _OBJECT,
        "index": {"type": "integer"},
        "target_index": {"type": "integer"},
    }
    for suffix in ("add", "update", "remove", "reorder"):
        required = ["object_id", "stack"]
        if suffix in {"update", "remove", "reorder"}:
            required.append("index")
        if suffix in {"add", "update"}:
            required.append("paint")
        if suffix == "reorder":
            required.append("target_index")
        _register(
            registry,
            f"paint.ui.appearance.paint.{suffix}",
            f"{suffix.title()} an ordered Painter UI Fill or Stroke paint.",
            f"paint_ui_appearance_paint_{suffix}",
            paint_common,
            required=tuple(required),
            undo_label=f"{suffix.title()} UI paint",
        )
    _register(
        registry,
        "paint.ui.appearance.corner.set",
        "Set four independent Painter UI corner radii.",
        "paint_ui_appearance_corner_set",
        {"object_id": _ID, "corner_radii": _OBJECT},
        required=("object_id", "corner_radii"),
        undo_label="Set UI corner radii",
    )
    _register(
        registry,
        "paint.ui.appearance.stroke.set",
        "Set Inside, Center, or Outside stroke alignment.",
        "paint_ui_appearance_stroke_set",
        {"object_id": _ID, "stroke_align": {"type": "string"}},
        required=("object_id", "stroke_align"),
        undo_label="Set UI stroke alignment",
    )
    _register(
        registry,
        "paint.ui.text.range.style.inspect",
        "Inspect mixed text-style ranges.",
        "paint_ui_text_range_style_inspect",
        {"object_id": _ID},
        required=("object_id",),
        mutating=False,
    )
    _register(
        registry,
        "paint.ui.text.range.style.set",
        "Set style for a selected text range.",
        "paint_ui_text_range_style_set",
        {
            "object_id": _ID,
            "start": {"type": "integer", "minimum": 0},
            "end": {"type": "integer", "minimum": 0},
            "style": _OBJECT,
        },
        required=("object_id", "start", "end", "style"),
        undo_label="Set mixed text style",
    )
    _register(
        registry,
        "paint.ui.text.range.style.remove",
        "Remove mixed styling from a selected text range.",
        "paint_ui_text_range_style_remove",
        {
            "object_id": _ID,
            "start": {"type": "integer", "minimum": 0},
            "end": {"type": "integer", "minimum": 0},
        },
        required=("object_id", "start", "end"),
        undo_label="Remove mixed text style",
    )
    for suffix, method, properties, required in (
        (
            "inspect",
            "paint_ui_component_remote_inspect",
            {"object_id": _ID},
            (),
        ),
        (
            "relink",
            "paint_ui_component_remote_relink",
            {
                "object_id": _ID,
                "component_key": _ID,
                "source_file_key": _ID,
                "source_node_id": _ID,
            },
            ("object_id", "component_key"),
        ),
        (
            "localize",
            "paint_ui_component_remote_localize",
            {"object_id": _ID, "name": _ID},
            ("object_id",),
        ),
        (
            "replace",
            "paint_ui_component_remote_replace",
            {"object_id": _ID, "component_id": _ID},
            ("object_id", "component_id"),
        ),
    ):
        _register(
            registry,
            f"paint.ui.component.remote.{suffix}",
            f"{suffix.title()} missing remote component references.",
            method,
            properties,
            required=required,
            mutating=suffix != "inspect",
            undo_label=(
                f"{suffix.title()} remote UI component"
                if suffix != "inspect"
                else ""
            ),
        )
    _register(
        registry,
        "paint.ui.vector.boolean.inspect",
        "Inspect an editable Painter UI Boolean group.",
        "paint_ui_vector_boolean_inspect",
        {"object_id": _ID},
        required=("object_id",),
        mutating=False,
    )
    _register(
        registry,
        "paint.ui.vector.boolean.set",
        "Set Union, Subtract, Intersect, or Exclude operands.",
        "paint_ui_vector_boolean_set",
        {
            "object_id": _ID,
            "operation": {"type": "string"},
            "operand_ids": _ID_LIST,
        },
        required=("object_id", "operation", "operand_ids"),
        undo_label="Set UI Boolean",
    )
    _register(
        registry,
        "paint.ui.vector.boolean.release",
        "Release a Painter UI Boolean group to editable operands.",
        "paint_ui_vector_boolean_release",
        {"object_id": _ID},
        required=("object_id",),
        undo_label="Release UI Boolean",
    )
    _register(
        registry,
        "paint.ui.section.inspect",
        "Inspect imported or authored Figma-style sections.",
        "paint_ui_section_inspect",
        {"section_id": _ID},
        mutating=False,
    )
    _register(
        registry,
        "paint.ui.section.create",
        "Create a Figma-style Painter UI section.",
        "paint_ui_section_create",
        {"section": _OBJECT},
        required=("section",),
        undo_label="Create UI section",
    )
    _register(
        registry,
        "paint.ui.section.update",
        "Update a Painter UI section.",
        "paint_ui_section_update",
        {"section_id": _ID, "changes": _OBJECT},
        required=("section_id", "changes"),
        undo_label="Update UI section",
    )
    _register(
        registry,
        "paint.ui.section.remove",
        "Remove a Painter UI section without deleting its objects.",
        "paint_ui_section_remove",
        {"section_id": _ID},
        required=("section_id",),
        undo_label="Remove UI section",
    )


__all__ = ["register_paint_ui_advanced_actions"]
