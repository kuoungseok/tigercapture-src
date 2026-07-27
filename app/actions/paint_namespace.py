"""Paint / drawing action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object
from app.painter_brush_catalog import DESIGNER_BRUSH_STYLE_IDS
from app.painter_ui_document import (
    UI_DELIVERY_TARGETS,
    UI_INTERACTION_ACTIONS,
    UI_INTERACTION_TRIGGERS,
    UI_OBJECT_KINDS,
    UI_TOKEN_KINDS,
)


PAINT_ACTION_BRUSH_STYLES = tuple(
    sorted(
        {
            "round",
            "marker",
            "highlighter",
            "dashed",
            "loaded_oil",
            "impasto_oil",
            "oil_smear",
            "soft_oil_glaze",
            "real_wet_oil",
            "bristle_oil",
            "dry_oil",
            "palette_knife",
            "filbert_oil",
            "flat_hog_oil",
            "fan_bristle_oil",
            "rigger_oil",
            "scumble_oil",
            "stipple_oil",
            "knife_scrape_oil",
            "textured_chalk",
        }
        | set(DESIGNER_BRUSH_STYLE_IDS)
    )
)


def register_paint_actions(registry: Any) -> None:
    any_object = {"type": "object", "additionalProperties": True}
    registry.register_adapter_action(
        "paint.state",
        "Read the active Painter document, layer, channel, selection, path, and history state.",
        "paint",
        "paint_state",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="active Painter state would be read",
    )
    registry.register_adapter_action(
        "paint.gpu.status",
        "Report Painter OpenGL readiness, active/fallback renderer state, and remote-safe fallback policy.",
        "paint",
        "paint_gpu_status",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter GPU/OpenGL status would be read",
    )
    registry.register_adapter_action(
        "paint.document.new",
        "Replace the active Painter document with a new blank canvas.",
        "paint",
        "paint_document_new",
        params_schema=schema_object(
            {
                "width": {"type": "integer", "minimum": 64, "maximum": 16384},
                "height": {"type": "integer", "minimum": 64, "maximum": 16384},
                "background": {"type": "string"},
            }
        ),
        undo_label="New Painter canvas",
        dry_summary="active Painter canvas would be replaced",
    )
    registry.register_adapter_action(
        "paint.document.save",
        (
            "Save the complete editable Painter document, including layers, "
            "Wet Canvas, references, and 3D blockout scene, as .tspaint."
        ),
        "paint",
        "paint_document_save",
        params_schema=schema_object({"path": {"type": "string"}}),
        mutating=False,
        changed=False,
        dry_summary="active Painter document would be saved as .tspaint",
    )
    registry.register_adapter_action(
        "paint.document.open",
        (
            "Open a .tspaint document and restore editable 2D and 3D Painter "
            "state."
        ),
        "paint",
        "paint_document_open",
        params_schema=schema_object(
            {"path": {"type": "string"}},
            required=("path",),
        ),
        undo_label="Open Painter document",
        dry_summary="active Painter document would be replaced from .tspaint",
    )
    registry.register_adapter_action(
        "paint.ui.document.inspect",
        "Inspect the provider-neutral Painter UI document, validation, artboards, objects, and delivery targets.",
        "paint",
        "paint_ui_document_inspect",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="the Painter UI document would be inspected",
    )
    registry.register_adapter_action(
        "paint.ui.template.catalog.inspect",
        "Inspect built-in complete-document templates, categories, tags, sources, and licenses.",
        "paint",
        "paint_ui_template_catalog_inspect",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="the Painter UI template catalog would be inspected",
    )
    registry.register_adapter_action(
        "paint.ui.template.apply",
        "Replace the active UI document with an editable template copy while preserving source provenance.",
        "paint",
        "paint_ui_template_apply",
        params_schema=schema_object(
            {"template_id": {"type": "string", "minLength": 1}},
            required=("template_id",),
        ),
        required=("template_id",),
        undo_label="Apply UI template",
        dry_summary="a complete Painter UI template would replace the active document",
    )
    registry.register_adapter_action(
        "paint.ui.component.library.inspect",
        "Inspect component families, Variants, stable roots, and Instance usage.",
        "paint",
        "paint_ui_component_library_inspect",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="the Painter component library would be inspected",
    )
    registry.register_adapter_action(
        "paint.ui.token.library.inspect",
        "Inspect design tokens, theme values, aliases, stable bindings, and unused-token status.",
        "paint",
        "paint_ui_token_library_inspect",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="the Painter design-token library would be inspected",
    )
    registry.register_adapter_action(
        "paint.ui.token.library.export",
        "Export the typed design-token library as deterministic JSON.",
        "paint",
        "paint_ui_token_library_export",
        params_schema=schema_object(
            {"path": {"type": "string", "minLength": 1}},
            required=("path",),
        ),
        required=("path",),
        mutating=False,
        changed=False,
        dry_summary="the Painter token library would be exported to JSON",
    )
    registry.register_adapter_action(
        "paint.ui.token.library.import",
        "Import a token JSON library with explicit stable-ID conflict handling.",
        "paint",
        "paint_ui_token_library_import",
        params_schema=schema_object(
            {
                "path": {"type": "string", "minLength": 1},
                "conflict_policy": {
                    "type": "string",
                    "enum": ["update", "skip", "regenerate"],
                },
            },
            required=("path",),
        ),
        required=("path",),
        undo_label="Import UI tokens",
        dry_summary="a token JSON library would be imported",
    )
    registry.register_adapter_action(
        "paint.ui.workspace.set",
        "Switch Painter between Paint, UI Design, and 3D Place canvas workspaces.",
        "paint",
        "paint_ui_workspace_set",
        params_schema=schema_object(
            {
                "mode": {
                    "type": "string",
                    "enum": ["paint", "ui_design", "3d_place"],
                }
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="the visible Painter canvas workspace would change",
    )
    registry.register_adapter_action(
        "paint.ui.view.fit",
        "Fit all UI artboards, the active artboard, or the current selection in the Painter canvas.",
        "paint",
        "paint_ui_view_fit",
        params_schema=schema_object(
            {
                "mode": {
                    "type": "string",
                    "enum": ["all", "artboard", "selection"],
                }
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="the Painter UI canvas camera would be fitted",
    )
    registry.register_adapter_action(
        "paint.ui.layout.diagnostics",
        "Inspect deterministic Auto Layout, constraint, grid, and safe-area conflicts.",
        "paint",
        "paint_ui_layout_diagnostics",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter UI layout diagnostics would be returned",
    )
    registry.register_adapter_action(
        "paint.ui.responsive.override.set",
        "Set an object override for a breakpoint and orientation context.",
        "paint",
        "paint_ui_responsive_override_set",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "breakpoint": {"type": "string"},
                "orientation": {
                    "type": "string",
                    "enum": ["any", "portrait", "landscape"],
                },
                "changes": any_object,
            },
            required=("object_id", "changes"),
        ),
        required=("object_id", "changes"),
        undo_label="Set UI responsive override",
        dry_summary="a responsive object override would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.responsive.override.remove",
        "Remove an object override for a breakpoint and orientation context.",
        "paint",
        "paint_ui_responsive_override_remove",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "breakpoint": {"type": "string"},
                "orientation": {
                    "type": "string",
                    "enum": ["any", "portrait", "landscape"],
                },
            },
            required=("object_id",),
        ),
        required=("object_id",),
        undo_label="Remove UI responsive override",
        dry_summary="a responsive object override would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.theme.set",
        "Set the Light, Dark, or High Contrast preview theme for an artboard.",
        "paint",
        "paint_ui_theme_set",
        params_schema=schema_object(
            {
                "artboard_id": {"type": "string"},
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "high_contrast"],
                },
            },
            required=("theme",),
        ),
        required=("theme",),
        undo_label="Set UI theme",
        dry_summary="the artboard preview theme would be changed",
    )
    registry.register_adapter_action(
        "paint.ui.theme.inspect",
        "Inspect resolved design-token bindings for an artboard theme.",
        "paint",
        "paint_ui_theme_inspect",
        params_schema=schema_object(
            {"artboard_id": {"type": "string"}},
        ),
        mutating=False,
        changed=False,
        dry_summary="resolved UI theme bindings would be returned",
    )
    registry.register_adapter_action(
        "paint.ui.token.theme.set",
        "Set one theme-specific value on a design token.",
        "paint",
        "paint_ui_token_theme_set",
        params_schema=schema_object(
            {
                "token_id": {"type": "string"},
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "high_contrast"],
                },
                "value": {},
            },
            required=("token_id", "theme", "value"),
        ),
        required=("token_id", "theme", "value"),
        undo_label="Set UI token theme value",
        dry_summary="a theme-specific token value would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.token.theme.remove",
        "Remove one theme-specific value from a design token.",
        "paint",
        "paint_ui_token_theme_remove",
        params_schema=schema_object(
            {
                "token_id": {"type": "string"},
                "theme": {
                    "type": "string",
                    "enum": ["light", "dark", "high_contrast"],
                },
            },
            required=("token_id", "theme"),
        ),
        required=("token_id", "theme"),
        undo_label="Remove UI token theme value",
        dry_summary="a theme-specific token value would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.artboard.add",
        "Add a general UI artboard to the active Painter document.",
        "paint",
        "paint_ui_artboard_add",
        params_schema=schema_object(
            {
                "name": {"type": "string"},
                "width": {"type": "integer", "minimum": 1, "maximum": 16384},
                "height": {"type": "integer", "minimum": 1, "maximum": 16384},
                "breakpoint": {"type": "string"},
            }
        ),
        undo_label="Add UI artboard",
        dry_summary="a UI artboard would be added",
    )
    registry.register_adapter_action(
        "paint.ui.artboard.update",
        "Update a general UI artboard without introducing target-runtime types.",
        "paint",
        "paint_ui_artboard_update",
        params_schema=schema_object(
            {
                "artboard_id": {"type": "string"},
                "changes": any_object,
            },
            required=("artboard_id", "changes"),
        ),
        required=("artboard_id", "changes"),
        undo_label="Update UI artboard",
        dry_summary="a UI artboard would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.artboard.activate",
        "Set the active Painter UI artboard for editing and preview.",
        "paint",
        "paint_ui_artboard_activate",
        params_schema=schema_object(
            {"artboard_id": {"type": "string"}},
            required=("artboard_id",),
        ),
        required=("artboard_id",),
        undo_label="Activate UI artboard",
        dry_summary="the active UI artboard would change",
    )
    registry.register_adapter_action(
        "paint.ui.artboard.layout.set",
        "Set provider-neutral grid, columns, guides, and safe area on a Painter UI artboard.",
        "paint",
        "paint_ui_artboard_layout_set",
        params_schema=schema_object(
            {
                "artboard_id": {"type": "string"},
                "layout_grid": any_object,
                "safe_area": any_object,
                "safe_area_visible": {"type": "boolean"},
                "guides": any_object,
            },
            required=("artboard_id",),
        ),
        required=("artboard_id",),
        undo_label="Set UI artboard layout",
        dry_summary="the artboard grid, guides, and safe area would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.artboard.remove",
        "Remove a UI artboard and its owned objects while keeping at least one artboard.",
        "paint",
        "paint_ui_artboard_remove",
        params_schema=schema_object(
            {"artboard_id": {"type": "string"}},
            required=("artboard_id",),
        ),
        required=("artboard_id",),
        undo_label="Remove UI artboard",
        dry_summary="a UI artboard and its owned objects would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.object.add",
        "Add a provider-neutral UI object to a Painter artboard.",
        "paint",
        "paint_ui_object_add",
        params_schema=schema_object(
            {
                "kind": {
                    "type": "string",
                    "enum": sorted(UI_OBJECT_KINDS),
                },
                "name": {"type": "string"},
                "artboard_id": {"type": "string"},
                "parent_id": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "width": {"type": "number", "minimum": 1},
                "height": {"type": "number", "minimum": 1},
                "style": any_object,
                "content": any_object,
            }
        ),
        undo_label="Add UI object",
        dry_summary="a provider-neutral UI object would be added",
    )
    registry.register_adapter_action(
        "paint.ui.object.update",
        "Update a Painter UI object and validate parent/artboard references.",
        "paint",
        "paint_ui_object_update",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "changes": any_object,
            },
            required=("object_id", "changes"),
        ),
        required=("object_id", "changes"),
        undo_label="Update UI object",
        dry_summary="a UI object would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.layout.set",
        "Set deterministic Horizontal or Vertical Auto Layout on a Painter UI container.",
        "paint",
        "paint_ui_layout_set",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["none", "horizontal", "vertical"],
                },
                "padding": any_object,
                "gap": {"type": "number", "minimum": 0},
                "cross_gap": {"type": "number", "minimum": 0},
                "main_alignment": {
                    "type": "string",
                    "enum": ["start", "center", "end", "space_between"],
                },
                "cross_alignment": {
                    "type": "string",
                    "enum": ["start", "center", "end", "stretch"],
                },
                "wrap": {"type": "boolean"},
                "width_sizing": {
                    "type": "string",
                    "enum": ["fixed", "hug", "fill"],
                },
                "height_sizing": {
                    "type": "string",
                    "enum": ["fixed", "hug", "fill"],
                },
            },
            required=("object_id", "mode"),
        ),
        required=("object_id", "mode"),
        undo_label="Set UI Auto Layout",
        dry_summary="Painter UI Auto Layout would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.object.remove",
        "Remove a Painter UI object and its child hierarchy.",
        "paint",
        "paint_ui_object_remove",
        params_schema=schema_object(
            {"object_id": {"type": "string"}},
            required=("object_id",),
        ),
        required=("object_id",),
        undo_label="Remove UI object",
        dry_summary="a UI object hierarchy would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.selection.set",
        "Select one or more UI objects on the active Painter artboard.",
        "paint",
        "paint_ui_selection_set",
        params_schema=schema_object(
            {
                "object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "uniqueItems": True,
                },
                "primary_object_id": {"type": "string"},
            }
        ),
        undo_label="Set UI selection",
        dry_summary="the active Painter UI selection would change",
    )
    registry.register_adapter_action(
        "paint.ui.object.arrange",
        "Align or distribute the selected Painter UI objects.",
        "paint",
        "paint_ui_object_arrange",
        params_schema=schema_object(
            {
                "command": {
                    "type": "string",
                    "enum": [
                        "left",
                        "hcenter",
                        "right",
                        "top",
                        "vcenter",
                        "bottom",
                        "distribute_h",
                        "distribute_v",
                    ],
                }
            },
            required=("command",),
        ),
        required=("command",),
        undo_label="Arrange UI objects",
        dry_summary="selected Painter UI objects would be aligned or distributed",
    )
    registry.register_adapter_action(
        "paint.ui.object.group",
        "Create an editable group from two or more Painter UI objects.",
        "paint",
        "paint_ui_object_group",
        params_schema=schema_object(
            {
                "object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "uniqueItems": True,
                },
                "name": {"type": "string"},
            },
            required=("object_ids",),
        ),
        required=("object_ids",),
        undo_label="Group UI objects",
        dry_summary="the selected Painter UI objects would be grouped",
    )
    registry.register_adapter_action(
        "paint.ui.object.ungroup",
        "Remove a Painter UI group while preserving its child objects.",
        "paint",
        "paint_ui_object_ungroup",
        params_schema=schema_object(
            {"object_id": {"type": "string"}},
            required=("object_id",),
        ),
        required=("object_id",),
        undo_label="Ungroup UI objects",
        dry_summary="the selected Painter UI group would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.object.reorder",
        "Move selected Painter UI objects through the active artboard stack.",
        "paint",
        "paint_ui_object_reorder",
        params_schema=schema_object(
            {
                "object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "command": {
                    "type": "string",
                    "enum": ["front", "forward", "backward", "back"],
                },
            },
            required=("object_ids", "command"),
        ),
        required=("object_ids", "command"),
        undo_label="Reorder UI objects",
        dry_summary="selected Painter UI objects would move in the layer stack",
    )
    registry.register_adapter_action(
        "paint.ui.object.reparent",
        "Move Painter UI objects into a group, beside a sibling, or to root.",
        "paint",
        "paint_ui_object_reparent",
        params_schema=schema_object(
            {
                "object_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "uniqueItems": True,
                },
                "target_parent_id": {"type": "string"},
                "anchor_id": {"type": "string"},
                "placement": {
                    "type": "string",
                    "enum": ["inside", "before", "after", "root"],
                },
            },
            required=("object_ids", "placement"),
        ),
        required=("object_ids", "placement"),
        undo_label="Move UI hierarchy",
        dry_summary="selected Painter UI objects would move in the hierarchy",
    )
    for suffix, method, summary in (
        ("component.update", "paint_ui_component_update", "a UI component would be updated"),
        ("token.update", "paint_ui_token_update", "a UI token would be updated"),
        ("interaction.update", "paint_ui_interaction_update", "a UI interaction would be updated"),
    ):
        id_key = suffix.split(".", 1)[0] + "_id"
        registry.register_adapter_action(
            f"paint.ui.{suffix}",
            f"Update a typed Painter UI {suffix.split('.', 1)[0]} while preserving its stable ID.",
            "paint",
            method,
            params_schema=schema_object(
                {id_key: {"type": "string"}, "changes": any_object},
                required=(id_key, "changes"),
            ),
            required=(id_key, "changes"),
            undo_label=f"Update UI {suffix.split('.', 1)[0]}",
            dry_summary=summary,
        )
    registry.register_adapter_action(
        "paint.ui.component.create",
        "Convert a selected UI object subtree into a reusable component definition.",
        "paint",
        "paint_ui_component_create",
        params_schema=schema_object(
            {
                "root_object_id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
            }
        ),
        undo_label="Create UI component",
        dry_summary="the selected UI subtree would become a component definition",
    )
    registry.register_adapter_action(
        "paint.ui.component.instantiate",
        "Create an editable instance of a component definition.",
        "paint",
        "paint_ui_component_instantiate",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "artboard_id": {"type": "string"},
                "x": {"type": "number"},
                "y": {"type": "number"},
            },
            required=("component_id",),
        ),
        required=("component_id",),
        undo_label="Instantiate UI component",
        dry_summary="a component instance would be created",
    )
    registry.register_adapter_action(
        "paint.ui.component.sync",
        "Synchronize component instances from their current definition.",
        "paint",
        "paint_ui_component_sync",
        params_schema=schema_object(
            {"component_id": {"type": "string"}},
            required=("component_id",),
        ),
        required=("component_id",),
        undo_label="Sync UI component instances",
        dry_summary="component instances would be synchronized",
    )
    registry.register_adapter_action(
        "paint.ui.component.property.define",
        "Define a typed property exposed by a Painter UI component.",
        "paint",
        "paint_ui_component_property_define",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "property_name": {"type": "string"},
                "definition": any_object,
            },
            required=("component_id", "property_name", "definition"),
        ),
        required=("component_id", "property_name", "definition"),
        undo_label="Define UI component property",
        dry_summary="a typed component property would be defined",
    )
    registry.register_adapter_action(
        "paint.ui.component.property.bind",
        "Bind a component property to a definition sublayer field.",
        "paint",
        "paint_ui_component_property_bind",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "source_object_id": {"type": "string"},
                "property_name": {"type": "string"},
                "target_path": {
                    "type": "string",
                    "enum": ["content.text", "visible", "component_id"],
                },
            },
            required=(
                "component_id",
                "source_object_id",
                "property_name",
                "target_path",
            ),
        ),
        required=(
            "component_id",
            "source_object_id",
            "property_name",
            "target_path",
        ),
        undo_label="Bind UI component property",
        dry_summary="a component property would control a definition sublayer",
    )
    registry.register_adapter_action(
        "paint.ui.component.state.override.set",
        "Set visual overrides for one interactive component state.",
        "paint",
        "paint_ui_component_state_override_set",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "state": {
                    "type": "string",
                    "enum": [
                        "normal",
                        "hover",
                        "pressed",
                        "focused",
                        "disabled",
                        "selected",
                    ],
                },
                "source_object_id": {"type": "string"},
                "changes": any_object,
            },
            required=(
                "component_id",
                "state",
                "source_object_id",
                "changes",
            ),
        ),
        required=("component_id", "state", "source_object_id", "changes"),
        undo_label="Set UI component state",
        dry_summary="a component state appearance would be updated",
    )
    registry.register_adapter_action(
        "paint.ui.component.instance.property.set",
        "Set a typed property, including preview state, on a component instance.",
        "paint",
        "paint_ui_component_instance_property_set",
        params_schema=schema_object(
            {
                "instance_root_id": {"type": "string"},
                "property_name": {"type": "string"},
                "value": {},
            },
            required=("instance_root_id", "property_name", "value"),
        ),
        required=("instance_root_id", "property_name", "value"),
        undo_label="Set UI component instance property",
        dry_summary="a component instance property would be changed",
    )
    registry.register_adapter_action(
        "paint.ui.component.variant.create",
        "Duplicate a component definition as a linked family Variant.",
        "paint",
        "paint_ui_component_variant_create",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "name": {"type": "string"},
                "variant_key": {"type": "string"},
                "offset_x": {"type": "number"},
            },
            required=("component_id",),
        ),
        required=("component_id",),
        undo_label="Create UI component variant",
        dry_summary="a linked component Variant would be created",
    )
    registry.register_adapter_action(
        "paint.ui.component.instance.variant.set",
        "Switch an Instance to another Variant in the same component family.",
        "paint",
        "paint_ui_component_instance_variant_set",
        params_schema=schema_object(
            {
                "instance_root_id": {"type": "string"},
                "component_id": {"type": "string"},
            },
            required=("instance_root_id", "component_id"),
        ),
        required=("instance_root_id", "component_id"),
        undo_label="Switch UI component variant",
        dry_summary="a component Instance would switch Variant",
    )
    registry.register_adapter_action(
        "paint.ui.component.instance.detach",
        "Detach an Instance as local objects or convert it into a local component.",
        "paint",
        "paint_ui_component_instance_detach",
        params_schema=schema_object(
            {
                "instance_root_id": {"type": "string"},
                "create_local_component": {"type": "boolean"},
                "name": {"type": "string"},
            },
            required=("instance_root_id",),
        ),
        required=("instance_root_id",),
        undo_label="Detach UI component instance",
        dry_summary="a component Instance would become local content",
    )
    registry.register_adapter_action(
        "paint.ui.component.add",
        "Create a typed reusable component definition rooted at a Painter UI object.",
        "paint",
        "paint_ui_component_add",
        params_schema=schema_object(
            {
                "name": {"type": "string"},
                "root_object_id": {"type": "string"},
                "base_component_id": {"type": "string"},
                "description": {"type": "string"},
                "property_definitions": any_object,
            }
        ),
        undo_label="Add UI component",
        dry_summary="a typed UI component would be added",
    )
    registry.register_adapter_action(
        "paint.ui.component.remove",
        "Remove a component, blocking referenced deletion unless detachment is explicit.",
        "paint",
        "paint_ui_component_remove",
        params_schema=schema_object(
            {
                "component_id": {"type": "string"},
                "detach_references": {"type": "boolean"},
            },
            required=("component_id",),
        ),
        required=("component_id",),
        undo_label="Remove UI component",
        dry_summary="a UI component would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.token.add",
        "Create a typed design token with optional theme values or alias reference.",
        "paint",
        "paint_ui_token_add",
        params_schema=schema_object(
            {
                "name": {"type": "string"},
                "kind": {"type": "string", "enum": sorted(UI_TOKEN_KINDS)},
                "value": {},
                "theme_values": any_object,
                "alias_token_id": {"type": "string"},
                "description": {"type": "string"},
            }
        ),
        undo_label="Add UI token",
        dry_summary="a typed UI token would be added",
    )
    registry.register_adapter_action(
        "paint.ui.token.remove",
        "Remove a token, blocking referenced deletion unless detachment is explicit.",
        "paint",
        "paint_ui_token_remove",
        params_schema=schema_object(
            {
                "token_id": {"type": "string"},
                "detach_references": {"type": "boolean"},
            },
            required=("token_id",),
        ),
        required=("token_id",),
        undo_label="Remove UI token",
        dry_summary="a UI token would be removed",
    )
    token_binding_schema = schema_object(
        {
            "object_id": {"type": "string"},
            "path": {
                "type": "string",
                "enum": [
                    "style.fill",
                    "style.stroke",
                    "style.text_color",
                    "style.stroke_width",
                    "style.radius",
                    "style.shadow",
                    "style.font_size",
                    "layout.gap",
                    "opacity",
                    "content.source",
                ],
            },
            "token_id": {"type": "string"},
        },
        required=("object_id", "path", "token_id"),
    )
    registry.register_adapter_action(
        "paint.ui.token.bind",
        "Bind a selected object property to a design token by stable token ID.",
        "paint",
        "paint_ui_token_bind",
        params_schema=token_binding_schema,
        required=("object_id", "path", "token_id"),
        undo_label="Bind UI token",
        dry_summary="an object property would be bound to a stable UI token",
    )
    registry.register_adapter_action(
        "paint.ui.token.unbind",
        "Remove a design-token binding without changing the token or other properties.",
        "paint",
        "paint_ui_token_unbind",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "path": token_binding_schema["properties"]["path"],
            },
            required=("object_id", "path"),
        ),
        required=("object_id", "path"),
        undo_label="Unbind UI token",
        dry_summary="an object property token binding would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.interaction.add",
        "Create a typed prototype interaction with validated source and target references.",
        "paint",
        "paint_ui_interaction_add",
        params_schema=schema_object(
            {
                "name": {"type": "string"},
                "source_object_id": {"type": "string"},
                "trigger": {
                    "type": "string",
                    "enum": sorted(UI_INTERACTION_TRIGGERS),
                },
                "action": {
                    "type": "string",
                    "enum": sorted(UI_INTERACTION_ACTIONS),
                },
                "target_artboard_id": {"type": "string"},
                "target_object_id": {"type": "string"},
                "component_id": {"type": "string"},
                "motion_clip_id": {"type": "string"},
                "parameters": any_object,
                "enabled": {"type": "boolean"},
            }
        ),
        undo_label="Add UI interaction",
        dry_summary="a typed UI interaction would be added",
    )
    registry.register_adapter_action(
        "paint.ui.interaction.remove",
        "Remove a Painter UI interaction by stable ID.",
        "paint",
        "paint_ui_interaction_remove",
        params_schema=schema_object(
            {"interaction_id": {"type": "string"}},
            required=("interaction_id",),
        ),
        required=("interaction_id",),
        undo_label="Remove UI interaction",
        dry_summary="a UI interaction would be removed",
    )
    registry.register_adapter_action(
        "paint.ui.delivery.profiles",
        "List general Painter UI delivery adapters and artifact capabilities.",
        "paint",
        "paint_ui_delivery_profiles",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter UI delivery profiles would be listed",
    )
    registry.register_adapter_action(
        "paint.ui.delivery.preflight",
        "Classify each UI object as native, material, baked, or blocked for a delivery target.",
        "paint",
        "paint_ui_delivery_preflight",
        params_schema=schema_object(
            {
                "target": {
                    "type": "string",
                    "enum": list(UI_DELIVERY_TARGETS),
                }
            },
            required=("target",),
        ),
        required=("target",),
        mutating=False,
        changed=False,
        dry_summary="the selected UI delivery target would be preflighted",
    )
    registry.register_adapter_action(
        "paint.ui.handoff.export",
        "Export a target-neutral design handoff package with document, tokens, components, interactions, and manifest.",
        "paint",
        "paint_ui_handoff_export",
        params_schema=schema_object(
            {"output_dir": {"type": "string"}},
            required=("output_dir",),
        ),
        required=("output_dir",),
        mutating=False,
        changed=False,
        dry_summary="a general Painter UI design handoff package would be written",
    )
    registry.register_adapter_action(
        "paint.document.export_png",
        "Export the active Painter document to PNG.",
        "paint",
        "paint_document_export_png",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "include_background": {"type": "boolean"},
                "width": {"type": "integer", "minimum": 0},
                "height": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="active Painter document would be exported as PNG",
    )
    registry.register_adapter_action(
        "paint.view.zoom",
        "Set the active Painter canvas zoom percentage.",
        "paint",
        "paint_view_zoom",
        params_schema=schema_object({"percent": {"type": "integer", "minimum": 25, "maximum": 800}}),
        undo_label="Set Painter zoom",
        dry_summary="active Painter zoom would change",
    )
    registry.register_adapter_action(
        "paint.view.zoom_area",
        "Magnify and center a normalized rectangular area of the active Painter canvas.",
        "paint",
        "paint_view_zoom_area",
        params_schema=schema_object(
            {
                "x": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "width": {"type": "number", "minimum": 0.001, "maximum": 1.0},
                "height": {"type": "number", "minimum": 0.001, "maximum": 1.0},
            },
            required=("x", "y", "width", "height"),
        ),
        undo_label="Zoom Painter area",
        dry_summary="a Painter canvas area would be magnified and centered",
    )
    registry.register_adapter_action(
        "paint.view.pan",
        "Move or reset the active Painter canvas pan offset.",
        "paint",
        "paint_view_pan",
        params_schema=schema_object(
            {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "dx": {"type": "integer"},
                "dy": {"type": "integer"},
                "reset": {"type": "boolean"},
            }
        ),
        undo_label="Pan Painter canvas",
        dry_summary="active Painter pan would change",
    )
    registry.register_adapter_action(
        "paint.view.grid",
        "Set Photoshop-style Painter grid visibility, snapping, and grid size.",
        "paint",
        "paint_view_grid",
        params_schema=schema_object(
            {
                "visible": {"type": "boolean"},
                "snap": {"type": "boolean"},
                "size_px": {"type": "integer", "minimum": 4, "maximum": 512},
            }
        ),
        undo_label="Set Painter grid",
        dry_summary="active Painter grid or snap state would change",
    )
    registry.register_adapter_action(
        "paint.guide.perspective",
        "Set Painter perspective ruler overlay with horizon and two vanishing points.",
        "paint",
        "paint_guide_perspective",
        params_schema=schema_object(
            {
                "enabled": {"type": "boolean"},
                "horizon": {"type": "number", "minimum": 0.02, "maximum": 0.98},
                "left_x": {"type": "number", "minimum": -1.5, "maximum": 2.5},
                "left_y": {"type": "number", "minimum": 0.02, "maximum": 0.98},
                "right_x": {"type": "number", "minimum": -1.5, "maximum": 2.5},
                "right_y": {"type": "number", "minimum": 0.02, "maximum": 0.98},
            }
        ),
        undo_label="Set Painter perspective guide",
        dry_summary="active Painter perspective guide would change",
    )
    registry.register_adapter_action(
        "paint.guide.symmetry",
        "Set Painter symmetry guide overlay for drawing alignment.",
        "paint",
        "paint_guide_symmetry",
        params_schema=schema_object(
            {
                "enabled": {"type": "boolean"},
                "axis": {"type": "string", "enum": ["vertical", "horizontal"]},
                "position": {"type": "number", "minimum": 0.02, "maximum": 0.98},
            }
        ),
        undo_label="Set Painter symmetry guide",
        dry_summary="active Painter symmetry guide would change",
    )
    registry.register_adapter_action(
        "paint.quick_mask.set",
        "Toggle Photoshop-style Quick Mask overlay for the active Painter selection.",
        "paint",
        "paint_quick_mask_set",
        params_schema=schema_object({"enabled": {"type": "boolean"}}),
        undo_label="Set Painter Quick Mask",
        dry_summary="active Painter Quick Mask overlay would change",
    )
    registry.register_adapter_action(
        "paint.tool.set",
        "Set the active Painter tool.",
        "paint",
        "paint_tool_set",
        params_schema=schema_object(
            {
                "tool": {
                    "type": "string",
                    "enum": [
                        "select",
                        "move",
                        "pan",
                        "hand",
                        "pen",
                        "brush",
                        "eraser",
                        "path",
                        "rect_select",
                        "rectangle",
                        "ellipse_select",
                        "ellipse",
                        "magic_select",
                        "magic_wand",
                        "select_color",
                        "crop",
                        "zoom_in",
                        "zoom_out",
                        "zoom_area",
                    ],
                }
            },
            required=("tool",),
        ),
        undo_label="Set Painter tool",
        dry_summary="active Painter tool would change",
    )
    registry.register_adapter_action(
        "paint.brush.set",
        "Set the active Painter brush preset, style, size, opacity, and brush detail controls.",
        "paint",
        "paint_brush_set",
        params_schema=schema_object(
            {
                "preset": {"type": "string"},
                "style": {
                    "type": "string",
                    "enum": list(PAINT_ACTION_BRUSH_STYLES),
                },
                "width": {"type": "integer", "minimum": 1, "maximum": 60},
                "opacity": {"type": "integer", "minimum": 10, "maximum": 100},
                "hardness": {"type": "integer", "minimum": 1, "maximum": 100},
                "spacing": {"type": "integer", "minimum": 1, "maximum": 200},
                "angle": {"type": "integer", "minimum": -180, "maximum": 180},
                "roundness": {"type": "integer", "minimum": 10, "maximum": 100},
                "flip_x": {"type": "boolean"},
                "flip_y": {"type": "boolean"},
            }
        ),
        undo_label="Set Painter brush",
        dry_summary="active Painter brush preset or brush parameters would change",
    )
    registry.register_adapter_action(
        "paint.brush.library.view",
        "Show and filter the Corel-style Painter brush library or advanced controls.",
        "paint",
        "paint_brush_library_view",
        params_schema=schema_object(
            {
                "tab": {"type": "string", "enum": ["library", "controls"]},
                "category": {"type": "string"},
                "filter": {
                    "type": "string",
                    "enum": [
                        "",
                        "favorites",
                        "masters",
                        "stamps",
                        "watercolor",
                        "thick_paint",
                    ],
                },
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "favorites",
                            "masters",
                            "stamps",
                            "watercolor",
                            "thick_paint",
                        ],
                    },
                    "uniqueItems": True,
                },
                "search": {"type": "string"},
                "compact": {"type": "boolean"},
            }
        ),
        undo_label="Set Painter brush library view",
        dry_summary="Painter brush library view would change",
    )
    registry.register_adapter_action(
        "paint.brush.favorite.set",
        "Mark or unmark a Painter brush preset as a favorite.",
        "paint",
        "paint_brush_favorite_set",
        params_schema=schema_object(
            {
                "preset": {"type": "string"},
                "favorite": {"type": "boolean"},
            },
            required=("preset", "favorite"),
        ),
        undo_label="Set Painter brush favorite",
        dry_summary="Painter brush favorite state would change",
    )
    point_schema = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "y": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "pressure": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "tilt": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "tilt_x": {"type": "number", "minimum": -1.0, "maximum": 1.0},
            "tilt_y": {"type": "number", "minimum": -1.0, "maximum": 1.0},
            "rotation": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "tangential_pressure": {
                "type": "number",
                "minimum": -1.0,
                "maximum": 1.0,
            },
            "load": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        "required": ["x", "y"],
        "additionalProperties": False,
    }
    stroke_schema = {
        "type": "object",
        "properties": {
            "points": {
                "type": "array",
                "items": point_schema,
                "minItems": 2,
                "maxItems": 2048,
            },
            "color": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
            "opacity": {"type": "integer", "minimum": 1, "maximum": 100},
            "width": {"type": "number", "minimum": 0.25, "maximum": 512.0},
            "style": {
                "type": "string",
                "enum": list(PAINT_ACTION_BRUSH_STYLES),
            },
            "hardness": {"type": "integer", "minimum": 1, "maximum": 100},
            "spacing": {"type": "integer", "minimum": 1, "maximum": 200},
            "angle": {"type": "integer", "minimum": -180, "maximum": 180},
            "roundness": {"type": "integer", "minimum": 10, "maximum": 100},
            "closed": {"type": "boolean"},
            "layer_id": {"type": "string"},
            "engine_version": {"type": "integer", "minimum": 1, "maximum": 2},
            "bristle_count": {"type": "integer", "minimum": 0, "maximum": 64},
            "seed": {"type": "integer"},
            "load_depletion": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "path_mode": {
                "type": "string",
                "enum": ["smooth", "polyline"],
            },
        },
        "required": ["points"],
        "additionalProperties": False,
    }
    registry.register_adapter_action(
        "paint.stroke.draw",
        (
            "Draw one or more normalized-coordinate brush strokes into Painter. "
            "Use batches for AI/Claude painting; the entire batch is one undo step."
        ),
        "paint",
        "paint_stroke_draw",
        params_schema=schema_object(
            {
                "strokes": {
                    "type": "array",
                    "items": stroke_schema,
                    "minItems": 1,
                    "maxItems": 512,
                },
                "undo_label": {"type": "string"},
            },
            required=("strokes",),
        ),
        undo_label="Draw AI Painter strokes",
        dry_summary="AI-planned brush strokes would be drawn on the Painter canvas",
    )
    registry.register_adapter_action(
        "paint.history.undo",
        "Undo the latest Painter document operation.",
        "paint",
        "paint_history_undo",
        undo_label="Undo Painter operation",
        dry_summary="latest Painter document operation would be undone",
    )
    registry.register_adapter_action(
        "paint.history.redo",
        "Redo the latest undone Painter document operation.",
        "paint",
        "paint_history_redo",
        undo_label="Redo Painter operation",
        dry_summary="latest undone Painter document operation would be redone",
    )
    registry.register_adapter_action(
        "paint.window.show_panel",
        "Show the Brush, Layers, Channels, or Paths panel in the active Painter window.",
        "paint",
        "paint_window_show_panel",
        params_schema=schema_object(
            {"panel": {"type": "string", "enum": ["brush", "layers", "channels", "paths", "reference", "3d_blockout"]}},
            required=("panel",),
        ),
        undo_label="Show Painter panel",
        dry_summary="active Painter panel would change",
    )
    registry.register_adapter_action(
        "paint.layer.add",
        "Add a standard or stroke-native Material Paint layer to the active Painter document.",
        "paint",
        "paint_layer_add",
        params_schema=schema_object(
            {
                "name": {"type": "string"},
                "layer_type": {"type": "string", "enum": ["standard", "material"]},
            }
        ),
        undo_label="Add Painter layer",
        dry_summary="a Painter layer would be added",
    )
    registry.register_adapter_action(
        "paint.layer.set_type",
        "Convert a Painter layer between standard color paint and stroke-native Material Paint.",
        "paint",
        "paint_layer_set_type",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "layer_type": {"type": "string", "enum": ["standard", "material"]},
            },
            required=("layer_type",),
        ),
        undo_label="Set Painter layer type",
        dry_summary="Painter layer type would change",
    )
    material_properties = {
        key: {"type": "number", "minimum": 0.0, "maximum": 1.0}
        for key in ("load", "thickness", "wetness", "gloss", "roughness")
    }
    registry.register_adapter_action(
        "paint.material.settings.set",
        "Set native Material Paint deposition and surface response for the active material layer.",
        "paint",
        "paint_material_settings_set",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, **material_properties}
        ),
        undo_label="Set Painter material paint",
        dry_summary="Material Paint deposition or surface controls would change",
    )
    registry.register_adapter_action(
        "paint.material.preview.set",
        "Set the canvas Material Paint relief preview and inspection light direction.",
        "paint",
        "paint_material_preview_set",
        params_schema=schema_object(
            {
                "enabled": {"type": "boolean"},
                "azimuth_deg": {"type": "number", "minimum": -180.0, "maximum": 180.0},
                "elevation_deg": {"type": "number", "minimum": 5.0, "maximum": 85.0},
            }
        ),
        undo_label="Set Painter material preview",
        dry_summary="Material Paint relief preview would change",
    )
    registry.register_adapter_action(
        "paint.wet_canvas.settings.set",
        (
            "Enable and configure deterministic editable wet-layer color "
            "exchange for a Painter material layer."
        ),
        "paint",
        "paint_wet_canvas_settings_set",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "enabled": {"type": "boolean"},
                "mixing": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "diffusion": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "pickup": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "drying_seconds": {
                    "type": "number",
                    "minimum": 1.0,
                    "maximum": 86400.0,
                },
            }
        ),
        undo_label="Set Painter Wet Canvas",
        dry_summary="Wet Canvas settings would change",
    )
    registry.register_adapter_action(
        "paint.wet_canvas.advance",
        "Advance the saved Wet Canvas drying state by a deterministic duration.",
        "paint",
        "paint_wet_canvas_advance",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "seconds": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 86400.0,
                },
            },
            required=("seconds",),
        ),
        undo_label="Advance Painter Wet Canvas",
        dry_summary="Wet Canvas drying time would advance",
    )
    registry.register_adapter_action(
        "paint.wet_canvas.dry",
        "Dry the selected Painter material layer without flattening its strokes.",
        "paint",
        "paint_wet_canvas_dry",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        undo_label="Dry Painter Wet Canvas",
        dry_summary="Wet Canvas would become dry",
    )
    registry.register_adapter_action(
        "paint.layer.select",
        "Select a Painter layer by id.",
        "paint",
        "paint_layer_select",
        params_schema=schema_object({"layer_id": {"type": "string"}}, required=("layer_id",)),
        undo_label="Select Painter layer",
        dry_summary="a Painter layer would be selected",
    )
    registry.register_adapter_action(
        "paint.layer.rename",
        "Rename a Painter layer.",
        "paint",
        "paint_layer_rename",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, "name": {"type": "string"}},
            required=("name",),
        ),
        undo_label="Rename Painter layer",
        dry_summary="a Painter layer would be renamed",
    )
    registry.register_adapter_action(
        "paint.layer.duplicate",
        "Duplicate the selected Painter layer or a layer by id.",
        "paint",
        "paint_layer_duplicate",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        undo_label="Duplicate Painter layer",
        dry_summary="a Painter layer would be duplicated",
    )
    registry.register_adapter_action(
        "paint.layer.delete",
        "Delete the selected Painter layer or a layer by id.",
        "paint",
        "paint_layer_delete",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        undo_label="Delete Painter layer",
        dry_summary="a Painter layer would be deleted",
    )
    registry.register_adapter_action(
        "paint.layer.set_visible",
        "Set Painter layer visibility.",
        "paint",
        "paint_layer_set_visible",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, "visible": {"type": "boolean"}},
            required=("visible",),
        ),
        undo_label="Set Painter layer visibility",
        dry_summary="Painter layer visibility would change",
    )
    registry.register_adapter_action(
        "paint.layer.set_locked",
        "Set Painter layer lock state.",
        "paint",
        "paint_layer_set_locked",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, "locked": {"type": "boolean"}},
            required=("locked",),
        ),
        undo_label="Set Painter layer lock",
        dry_summary="Painter layer lock would change",
    )
    registry.register_adapter_action(
        "paint.layer.set_opacity",
        "Set Painter layer opacity.",
        "paint",
        "paint_layer_set_opacity",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, "opacity": {"type": "integer", "minimum": 0, "maximum": 100}},
            required=("opacity",),
        ),
        undo_label="Set Painter layer opacity",
        dry_summary="Painter layer opacity would change",
    )
    registry.register_adapter_action(
        "paint.layer.set_blend_mode",
        "Set Painter layer blend mode state.",
        "paint",
        "paint_layer_set_blend_mode",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "blend_mode": {"type": "string", "enum": ["normal", "multiply", "screen", "overlay"]},
            },
            required=("blend_mode",),
        ),
        undo_label="Set Painter layer blend mode",
        dry_summary="Painter layer blend mode would change",
    )
    registry.register_adapter_action(
        "paint.layer.set_color",
        "Set the Photoshop-style Painter layer color label.",
        "paint",
        "paint_layer_set_color",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "color_label": {
                    "type": "string",
                    "enum": ["none", "red", "orange", "yellow", "green", "blue", "violet", "gray"],
                },
            },
            required=("color_label",),
        ),
        undo_label="Set Painter layer color label",
        dry_summary="Painter layer color label would change",
    )
    registry.register_adapter_action(
        "paint.channel.set_visible",
        "Set RGB, Red, Green, Blue, or Alpha visibility in the active Painter document.",
        "paint",
        "paint_channel_set_visible",
        params_schema=schema_object(
            {
                "channel": {"type": "string", "enum": ["RGB", "Red", "Green", "Blue", "Alpha"]},
                "visible": {"type": "boolean"},
            },
            required=("channel", "visible"),
        ),
        undo_label="Set Painter channel visibility",
        dry_summary="Painter channel visibility would change",
    )
    registry.register_adapter_action(
        "paint.channel.select",
        "Select RGB, Red, Green, Blue, or Alpha as the active Painter channel target.",
        "paint",
        "paint_channel_select",
        params_schema=schema_object(
            {"channel": {"type": "string", "enum": ["RGB", "Red", "Green", "Blue", "Alpha"]}},
            required=("channel",),
        ),
        undo_label="Select Painter channel",
        dry_summary="Painter channel target would change",
    )
    registry.register_adapter_action(
        "paint.channel.copy_image",
        "Copy the selected or specified Painter channel image to the system clipboard.",
        "paint",
        "paint_channel_copy_image",
        params_schema=schema_object(
            {"channel": {"type": "string", "enum": ["RGB", "Red", "Green", "Blue", "Alpha"]}}
        ),
        mutating=False,
        changed=False,
        dry_summary="Painter channel image would be copied",
    )
    registry.register_adapter_action(
        "paint.channel.paste_image",
        "Paste a clipboard image into the selected or specified Painter channel.",
        "paint",
        "paint_channel_paste_image",
        params_schema=schema_object(
            {"channel": {"type": "string", "enum": ["RGB", "Red", "Green", "Blue", "Alpha"]}}
        ),
        undo_label="Paste Painter channel image",
        dry_summary="clipboard image would be pasted into a Painter channel",
    )
    registry.register_adapter_action(
        "paint.selection.select_all",
        "Select the full Painter canvas.",
        "paint",
        "paint_selection_select_all",
        params_schema=schema_object({}),
        undo_label="Select all",
        dry_summary="Painter canvas would be selected",
    )
    registry.register_adapter_action(
        "paint.selection.deselect",
        "Clear the active Painter selection.",
        "paint",
        "paint_selection_deselect",
        params_schema=schema_object({}),
        undo_label="Deselect",
        dry_summary="Painter selection would be cleared",
    )
    registry.register_adapter_action(
        "paint.selection.invert",
        "Invert the active Painter selection.",
        "paint",
        "paint_selection_invert",
        params_schema=schema_object({}),
        undo_label="Invert Painter selection",
        dry_summary="Painter selection would be inverted",
    )
    registry.register_adapter_action(
        "paint.selection.to_path",
        "Save the active Painter selection as a closed path.",
        "paint",
        "paint_selection_to_path",
        params_schema=schema_object({}),
        undo_label="Selection to path",
        dry_summary="Painter selection would become a path",
    )
    registry.register_adapter_action(
        "paint.selection.rectangle",
        "Create a rectangular Painter selection from normalized 0..1 bounds.",
        "paint",
        "paint_selection_rectangle",
        params_schema=schema_object(
            {
                "x1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "x2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "aspect": {"type": "string", "enum": ["free", "square", "16:9", "4:3"]},
                "mode": {"type": "string", "enum": ["new", "add", "subtract", "intersect"]},
            },
            required=("x1", "y1", "x2", "y2"),
        ),
        undo_label="Rectangular Painter selection",
        dry_summary="Painter rectangular selection would be created",
    )
    registry.register_adapter_action(
        "paint.selection.ellipse",
        "Create an elliptical Painter selection from normalized 0..1 bounds.",
        "paint",
        "paint_selection_ellipse",
        params_schema=schema_object(
            {
                "x1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y1": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "x2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y2": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "aspect": {"type": "string", "enum": ["free", "square", "16:9", "4:3"]},
                "mode": {"type": "string", "enum": ["new", "add", "subtract", "intersect"]},
            },
            required=("x1", "y1", "x2", "y2"),
        ),
        undo_label="Elliptical Painter selection",
        dry_summary="Painter elliptical selection would be created",
    )
    registry.register_adapter_action(
        "paint.selection.set_aspect",
        "Set Painter marquee aspect mode to free, square, 16:9, or 4:3.",
        "paint",
        "paint_selection_set_aspect",
        params_schema=schema_object(
            {"aspect": {"type": "string", "enum": ["free", "square", "16:9", "4:3"]}},
            required=("aspect",),
        ),
        undo_label="Set Painter selection aspect",
        dry_summary="Painter marquee aspect mode would change",
    )
    registry.register_adapter_action(
        "paint.selection.set_mode",
        "Set how the next Painter selection combines with the current selection.",
        "paint",
        "paint_selection_set_mode",
        params_schema=schema_object(
            {"mode": {"type": "string", "enum": ["new", "add", "subtract", "intersect"]}},
            required=("mode",),
        ),
        undo_label="Set Painter selection mode",
        dry_summary="Painter selection combination mode would change",
    )
    registry.register_adapter_action(
        "paint.selection.select_by_color",
        "Create a Painter selection from pixels similar to the sampled color point.",
        "paint",
        "paint_selection_select_by_color",
        params_schema=schema_object(
            {
                "x": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "tolerance": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            required=("x", "y"),
        ),
        undo_label="Magic Select by color",
        dry_summary="Painter would select similar color pixels",
    )
    registry.register_adapter_action(
        "paint.crop.to_selection",
        "Crop the Painter document to the active selection bounds.",
        "paint",
        "paint_crop_to_selection",
        params_schema=schema_object({}),
        undo_label="Crop Painter document",
        dry_summary="Painter document would be cropped to selection",
    )
    registry.register_adapter_action(
        "paint.image.resize",
        "Resize the Painter image pixels and document dimensions.",
        "paint",
        "paint_image_resize",
        params_schema=schema_object(
            {
                "width": {"type": "integer", "minimum": 64, "maximum": 16384},
                "height": {"type": "integer", "minimum": 64, "maximum": 16384},
            },
            required=("width", "height"),
        ),
        undo_label="Resize Painter image",
        dry_summary="Painter image pixels would be resized",
    )
    registry.register_adapter_action(
        "paint.canvas.resize",
        "Resize the Painter canvas without scaling layer geometry.",
        "paint",
        "paint_canvas_resize",
        params_schema=schema_object(
            {
                "width": {"type": "integer", "minimum": 64, "maximum": 16384},
                "height": {"type": "integer", "minimum": 64, "maximum": 16384},
                "background": {"type": "string"},
            },
            required=("width", "height"),
        ),
        undo_label="Resize Painter canvas",
        dry_summary="Painter canvas bounds would be resized",
    )
    registry.register_adapter_action(
        "paint.canvas.flip",
        "Flip the Painter canvas horizontally or vertically.",
        "paint",
        "paint_canvas_flip",
        params_schema=schema_object(
            {"axis": {"type": "string", "enum": ["horizontal", "vertical", "x", "y"]}}
        ),
        undo_label="Flip Painter canvas",
        dry_summary="Painter canvas would be flipped",
    )
    registry.register_adapter_action(
        "paint.fill.solid",
        "Fill the active Painter selection, or full canvas if none is selected, with one color.",
        "paint",
        "paint_fill_solid",
        params_schema=schema_object({"color": {"type": "string"}}),
        undo_label="Painter solid fill",
        dry_summary="Painter selection or canvas would be solid-filled",
    )
    registry.register_adapter_action(
        "paint.fill.gradient",
        "Fill the active Painter selection, or full canvas if none is selected, with a soft gradient.",
        "paint",
        "paint_fill_gradient",
        params_schema=schema_object(
            {"color1": {"type": "string"}, "color2": {"type": "string"}}
        ),
        undo_label="Painter gradient fill",
        dry_summary="Painter selection or canvas would be gradient-filled",
    )
    registry.register_adapter_action(
        "paint.fill.pattern",
        "Fill the active Painter selection, or full canvas if none is selected, with a compact pattern.",
        "paint",
        "paint_fill_pattern",
        params_schema=schema_object(
            {"color1": {"type": "string"}, "color2": {"type": "string"}}
        ),
        undo_label="Painter pattern fill",
        dry_summary="Painter selection or canvas would be pattern-filled",
    )
    registry.register_adapter_action(
        "paint.mirror.set",
        "Set Painter mirrored drawing along the canvas horizontal and/or vertical axes.",
        "paint",
        "paint_mirror_set",
        params_schema=schema_object(
            {
                "x": {"type": "boolean"},
                "y": {"type": "boolean"},
            }
        ),
        undo_label="Set Painter mirror drawing",
        dry_summary="Painter mirror drawing mode would change",
    )
    registry.register_adapter_action(
        "paint.layer.mask_from_selection",
        "Create or replace the selected Painter layer mask from the active selection.",
        "paint",
        "paint_layer_mask_from_selection",
        params_schema=schema_object({"layer_id": {"type": "string"}}),
        undo_label="Layer mask from selection",
        dry_summary="Painter layer mask would be created from selection",
    )
    registry.register_adapter_action(
        "paint.layer.mask_from_path",
        "Create or replace the selected Painter layer mask from the active path.",
        "paint",
        "paint_layer_mask_from_path",
        params_schema=schema_object(
            {"layer_id": {"type": "string"}, "path_id": {"type": "string"}}
        ),
        undo_label="Layer mask from path",
        dry_summary="Painter layer mask would be created from path",
    )
    registry.register_adapter_action(
        "paint.layer.mask_create",
        "Create or replace the selected Painter layer mask from selection, path, channel, alpha, or reveal-all.",
        "paint",
        "paint_layer_mask_create",
        params_schema=schema_object(
            {
                "layer_id": {"type": "string"},
                "mask_type": {
                    "type": "string",
                    "enum": ["selection", "path", "channel", "alpha", "layer_alpha", "white", "reveal_all"],
                },
            }
        ),
        undo_label="Create Painter layer mask",
        dry_summary="Painter layer mask would be created",
    )
    registry.register_adapter_action(
        "paint.path.to_selection",
        "Convert the active or specified Painter path to a marching-ants selection.",
        "paint",
        "paint_path_to_selection",
        params_schema=schema_object({"path_id": {"type": "string"}}),
        undo_label="Path to selection",
        dry_summary="Painter path would become a selection",
    )
    registry.register_adapter_action(
        "paint.path.create",
        "Create a saved Painter path from normalized 0..1 points.",
        "paint",
        "paint_path_create",
        params_schema=schema_object(
            {
                "points": {"type": "array"},
                "closed": {"type": "boolean"},
                "make_selection": {"type": "boolean"},
            },
            required=("points",),
            additional_properties=True,
        ),
        undo_label="Create Painter path",
        dry_summary="Painter path would be created",
    )
    registry.register_adapter_action(
        "paint.path.delete",
        "Delete the active or specified Painter work, selection, or saved path.",
        "paint",
        "paint_path_delete",
        params_schema=schema_object({"path_id": {"type": "string"}}),
        undo_label="Delete Painter path",
        dry_summary="Painter path would be deleted",
    )
    registry.register_adapter_action(
        "paint.path.clear",
        "Clear the active Painter work path preview.",
        "paint",
        "paint_path_clear",
        params_schema=schema_object({}),
        undo_label="Clear Painter work path",
        dry_summary="Painter work path preview would be cleared",
    )
    registry.register_adapter_action(
        "paint.path.commit",
        "Commit the active Painter work path as an editable path stroke.",
        "paint",
        "paint_path_commit",
        params_schema=schema_object({"closed": {"type": "boolean"}}),
        undo_label="Commit Painter path",
        dry_summary="Painter work path would be committed",
    )
    registry.register_adapter_action(
        "paint.clipboard.copy",
        "Copy the selected Painter layer/object to the TigerCapture paint clipboard.",
        "paint",
        "paint_clipboard_copy",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="selected Painter content would be copied",
    )
    registry.register_adapter_action(
        "paint.clipboard.cut",
        "Cut the selected Painter layer/object to the TigerCapture paint clipboard.",
        "paint",
        "paint_clipboard_cut",
        params_schema=schema_object({}),
        undo_label="Cut Painter content",
        dry_summary="selected Painter content would be cut",
    )
    registry.register_adapter_action(
        "paint.clipboard.paste",
        "Paste TigerCapture paint clipboard content into the active Painter document.",
        "paint",
        "paint_clipboard_paste",
        params_schema=schema_object({}),
        undo_label="Paste Painter content",
        dry_summary="Painter clipboard content would be pasted",
    )
    registry.register_adapter_action(
        "paint.editor_objects.list",
        "List editor typography, AR/PBR, and actor objects importable into Paint.",
        "paint",
        "paint_editor_objects_list",
        params_schema=schema_object(
            {
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "limit": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="paint importable editor objects would be listed",
    )
    registry.register_adapter_action(
        "paint.editor_object.render",
        "Render one editor object to a Paint-import PNG without placing it.",
        "paint",
        "paint_editor_object_render",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "kind": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "output_dir": {"type": "string"},
                "force": {"type": "boolean"},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="editor object poster would be rendered for Paint",
    )
    registry.register_adapter_action(
        "paint.editor_object.import",
        "Import one editor object into Paint as a movable sticker layer.",
        "paint",
        "paint_editor_object_import",
        params_schema=schema_object(
            {
                "object_id": {"type": "string"},
                "kind": {"type": "string"},
                "time_ms": {"type": "integer", "minimum": 0},
                "include_inactive": {"type": "boolean"},
                "x_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "width_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "height_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "output_dir": {"type": "string"},
                "force": {"type": "boolean"},
                "metadata": any_object,
            }
        ),
        undo_label="Import editor object into Paint",
        dry_summary="editor object would be imported into Paint as a sticker layer",
    )
    reference_params = {
        "reference_id": {"type": "string"},
        "path": {"type": "string"},
        "name": {"type": "string"},
        "x_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "y_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "width_norm": {"type": "number", "minimum": 0.02, "maximum": 1.0},
        "height_norm": {"type": "number", "minimum": 0.02, "maximum": 1.0},
        "opacity": {"type": "number", "minimum": 0.05, "maximum": 1.0},
        "rotation_deg": {"type": "number", "minimum": -180.0, "maximum": 180.0},
        "visible": {"type": "boolean"},
        "locked": {"type": "boolean"},
    }
    registry.register_adapter_action(
        "paint.reference.state",
        "Read the active Painter reference board without changing paint layers.",
        "paint",
        "paint_reference_state",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter reference board would be read",
    )
    registry.register_adapter_action(
        "paint.reference.add",
        "Add a non-destructive reference image to the Painter board.",
        "paint",
        "paint_reference_add",
        params_schema=schema_object(reference_params, required=("path",)),
        undo_label="Add Painter reference image",
        dry_summary="Painter reference image would be added",
    )
    registry.register_adapter_action(
        "paint.reference.update",
        "Update position, size, opacity, visibility, or label for a Painter reference image.",
        "paint",
        "paint_reference_update",
        params_schema=schema_object(reference_params, required=("reference_id",)),
        undo_label="Update Painter reference image",
        dry_summary="Painter reference image would be updated",
    )
    registry.register_adapter_action(
        "paint.reference.delete",
        "Delete a Painter reference image from the reference board.",
        "paint",
        "paint_reference_delete",
        params_schema=schema_object({"reference_id": {"type": "string"}}, required=("reference_id",)),
        undo_label="Delete Painter reference image",
        dry_summary="Painter reference image would be deleted",
    )
    registry.register_adapter_action(
        "paint.reference.duplicate",
        "Duplicate a Painter reference image while keeping it non-destructive.",
        "paint",
        "paint_reference_duplicate",
        params_schema=schema_object(
            {
                "reference_id": {"type": "string"},
                "offset_x": {"type": "number"},
                "offset_y": {"type": "number"},
            },
            required=("reference_id",),
        ),
        undo_label="Duplicate Painter reference image",
        dry_summary="Painter reference image would be duplicated",
    )
    registry.register_adapter_action(
        "paint.reference.bake",
        "Bake a selected Painter reference into an exportable sticker layer.",
        "paint",
        "paint_reference_bake",
        params_schema=schema_object({"reference_id": {"type": "string"}}),
        undo_label="Bake Painter reference image",
        dry_summary="Painter reference image would be baked into an exportable sticker layer",
    )
    registry.register_adapter_action(
        "paint.reference.sample_color",
        "Sample a color from a Painter reference image and optionally apply it as foreground color.",
        "paint",
        "paint_reference_sample_color",
        params_schema=schema_object(
            {
                "reference_id": {"type": "string"},
                "x_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "y_norm": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "apply": {"type": "boolean"},
            }
        ),
        undo_label="Sample Painter reference color",
        dry_summary="Painter reference color would be sampled",
    )
    registry.register_adapter_action(
        "paint.reference.extract_palette",
        "Extract a compact color palette from a Painter reference image and optionally apply it to recent colors.",
        "paint",
        "paint_reference_extract_palette",
        params_schema=schema_object(
            {
                "reference_id": {"type": "string"},
                "max_colors": {"type": "integer", "minimum": 1, "maximum": 12},
                "apply": {"type": "boolean"},
            }
        ),
        undo_label="Extract Painter reference palette",
        dry_summary="Painter reference palette would be extracted",
    )
    study_session_params = {
        "reference_path": {"type": "string"},
        "target_width": {"type": "integer", "minimum": 256, "maximum": 1600},
        "region_count": {"type": "integer", "minimum": 3, "maximum": 24},
        "seed": {"type": "integer"},
        "focus_regions": {
            "type": "array",
            "maxItems": 16,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "bbox_norm": {
                        "type": "array",
                        "minItems": 4,
                        "maxItems": 4,
                        "items": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    },
                    "priority": {"type": "number", "minimum": 0.1, "maximum": 3.0},
                },
                "required": ["bbox_norm"],
                "additionalProperties": False,
            },
        },
    }
    registry.register_adapter_action(
        "paint.study.analyze_reference",
        "Analyze an approved reference for deterministic AI-guided Painter reconstruction.",
        "paint",
        "paint_study_analyze_reference",
        params_schema=schema_object(study_session_params, required=("reference_path",)),
        mutating=False,
        changed=False,
        dry_summary="Painter study reference would be analyzed",
    )
    registry.register_adapter_action(
        "paint.study.segment_regions",
        "Read deterministic color and edge regions for the active Painter study.",
        "paint",
        "paint_study_segment_regions",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter study regions would be reported",
    )
    study_generate_params = {
        "max_strokes": {"type": "integer", "minimum": 1, "maximum": 50000},
        "layer_name": {"type": "string"},
        "seed_offset": {"type": "integer"},
    }
    registry.register_adapter_action(
        "paint.study.build_underpaint",
        "Build broad editable underpainting strokes from the active Painter study.",
        "paint",
        "paint_study_build_underpaint",
        params_schema=schema_object(study_generate_params),
        undo_label="Build AI study underpaint",
        dry_summary="editable underpainting strokes would be generated",
    )
    registry.register_adapter_action(
        "paint.study.trace_contours",
        "Trace high-value reference contours as editable Painter strokes.",
        "paint",
        "paint_study_trace_contours",
        params_schema=schema_object(study_generate_params),
        undo_label="Trace AI study contours",
        dry_summary="editable contour strokes would be generated",
    )
    registry.register_adapter_action(
        "paint.study.generate_strokes",
        "Generate one editable Painter study stroke phase.",
        "paint",
        "paint_study_generate_strokes",
        params_schema=schema_object(
            {
                **study_generate_params,
                "phase": {
                    "type": "string",
                    "enum": ["underpaint", "forms", "detail", "contour", "accent"],
                },
            },
            required=("phase",),
        ),
        undo_label="Generate AI study strokes",
        dry_summary="editable study strokes would be generated",
    )
    registry.register_adapter_action(
        "paint.study.compare_render",
        "Compare the current real Painter render with the active approved reference.",
        "paint",
        "paint_study_compare_render",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter study render would be compared with its reference",
    )
    registry.register_adapter_action(
        "paint.study.refine_region",
        "Add deterministic editable strokes to the highest-error study regions.",
        "paint",
        "paint_study_refine_region",
        params_schema=schema_object(study_generate_params),
        undo_label="Refine AI study regions",
        dry_summary="highest-error study regions would receive editable correction strokes",
    )
    registry.register_adapter_action(
        "paint.study.quality_report",
        "Report whether the active Painter study passes editability and fidelity gates.",
        "paint",
        "paint_study_quality_report",
        params_schema=schema_object({}),
        mutating=False,
        changed=False,
        dry_summary="Painter study quality gates would be reported",
    )
    blockout_primitive = {
        "primitive_id": {"type": "string"},
        "kind": {
            "type": "string",
            "enum": ["box", "sphere", "cylinder", "cone", "plane", "arch"],
        },
        "name": {"type": "string"},
        "x": {"type": "number"},
        "y": {"type": "number"},
        "z": {"type": "number"},
        "rx": {"type": "number"},
        "ry": {"type": "number"},
        "rz": {"type": "number"},
        "sx": {"type": "number", "minimum": 0.001},
        "sy": {"type": "number", "minimum": 0.001},
        "sz": {"type": "number", "minimum": 0.001},
        "color": {"type": "string"},
        "opacity": {"type": "number", "minimum": 0.05, "maximum": 1.0},
        "wireframe": {"type": "boolean"},
        "locked": {"type": "boolean"},
        "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
        "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
    }
    registry.register_adapter_action(
        "paint.3d_blockout.state",
        "Read the active Painter 3D blockout scene and projected guide geometry.",
        "paint",
        "paint_3d_blockout_state",
        params_schema=schema_object(
            {
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="Painter 3D blockout scene would be read",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.add",
        "Add a simple concept-art 3D blockout primitive to the active Painter scene.",
        "paint",
        "paint_3d_blockout_add",
        params_schema=schema_object(blockout_primitive),
        undo_label="Add Painter 3D blockout primitive",
        dry_summary="Painter 3D blockout primitive would be added",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.update",
        "Update a Painter 3D blockout primitive transform, color, or guide state.",
        "paint",
        "paint_3d_blockout_update",
        params_schema=schema_object(blockout_primitive, required=("primitive_id",)),
        undo_label="Update Painter 3D blockout primitive",
        dry_summary="Painter 3D blockout primitive would be updated",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.delete",
        "Delete a Painter 3D blockout primitive from the active scene.",
        "paint",
        "paint_3d_blockout_delete",
        params_schema=schema_object(
            {
                "primitive_id": {"type": "string"},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            },
            required=("primitive_id",),
        ),
        undo_label="Delete Painter 3D blockout primitive",
        dry_summary="Painter 3D blockout primitive would be deleted",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.duplicate",
        "Duplicate a Painter 3D blockout primitive for fast box-based scene construction.",
        "paint",
        "paint_3d_blockout_duplicate",
        params_schema=schema_object(
            {
                "primitive_id": {"type": "string"},
                "offset_x": {"type": "number"},
                "offset_y": {"type": "number"},
                "offset_z": {"type": "number"},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            },
            required=("primitive_id",),
        ),
        undo_label="Duplicate Painter 3D blockout primitive",
        dry_summary="Painter 3D blockout primitive would be duplicated",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.align_ground",
        "Align a Painter 3D blockout primitive to the ground plane.",
        "paint",
        "paint_3d_blockout_align_ground",
        params_schema=schema_object(
            {
                "primitive_id": {"type": "string"},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            },
            required=("primitive_id",),
        ),
        undo_label="Align Painter 3D blockout primitive to ground",
        dry_summary="Painter 3D blockout primitive would be aligned to ground",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.snap",
        "Enable/disable blockout grid snapping or snap a selected primitive to the current grid.",
        "paint",
        "paint_3d_blockout_snap",
        params_schema=schema_object(
            {
                "enabled": {"type": "boolean"},
                "primitive_id": {"type": "string"},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            }
        ),
        undo_label="Set Painter 3D blockout snap",
        dry_summary="Painter 3D blockout snap would be changed",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.camera",
        "Adjust the Painter 3D blockout camera orbit, pan, zoom distance, or FOV.",
        "paint",
        "paint_3d_blockout_camera",
        params_schema=schema_object(
            {
                "yaw_degrees": {"type": "number"},
                "pitch_degrees": {"type": "number"},
                "distance": {"type": "number", "minimum": 0.25},
                "target_x": {"type": "number"},
                "target_y": {"type": "number"},
                "target_z": {"type": "number"},
                "fov_degrees": {"type": "number", "minimum": 15.0, "maximum": 90.0},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            }
        ),
        undo_label="Adjust Painter 3D blockout camera",
        dry_summary="Painter 3D blockout camera would be adjusted",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.material_preview",
        "Adjust the Painter blockout lit-white material, shadows, and directional light.",
        "paint",
        "paint_3d_blockout_material_preview",
        params_schema=schema_object(
            {
                "material_lit": {"type": "boolean"},
                "show_floor": {"type": "boolean"},
                "show_shadows": {"type": "boolean"},
                "show_fog": {"type": "boolean"},
                "show_depth": {"type": "boolean"},
                "light_yaw_degrees": {"type": "number", "minimum": -180.0, "maximum": 180.0},
                "light_pitch_degrees": {"type": "number", "minimum": 5.0, "maximum": 85.0},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            }
        ),
        undo_label="Adjust Painter 3D blockout material preview",
        dry_summary="Painter 3D blockout material preview would be adjusted",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.camera_preset",
        "Apply a Painter 3D blockout camera preset such as front, side, top, or perspective.",
        "paint",
        "paint_3d_blockout_camera_preset",
        params_schema=schema_object(
            {
                "preset": {"type": "string", "enum": ["front", "side", "top", "perspective"]},
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            },
            required=("preset",),
        ),
        undo_label="Apply Painter 3D blockout camera preset",
        dry_summary="Painter 3D blockout camera preset would be applied",
    )
    registry.register_adapter_action(
        "paint.3d_blockout.bake",
        "Bake the current Painter 3D blockout wire guide into a new paint layer.",
        "paint",
        "paint_3d_blockout_bake",
        params_schema=schema_object(
            {
                "preview_width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "preview_height": {"type": "integer", "minimum": 64, "maximum": 8192},
            }
        ),
        undo_label="Bake Painter 3D blockout",
        dry_summary="Painter 3D blockout guide would be baked into a paint layer",
    )
    registry.register_adapter_action(
        "paint.export_png",
        "Export the current Paint overlays as a PNG from the editor window.",
        "paint",
        "paint_export_png",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "mode": {"type": "string", "enum": ["composited", "overlay", "transparent_overlay"]},
                "time_ms": {"type": "integer", "minimum": 0},
                "width": {"type": "integer", "minimum": 0},
                "height": {"type": "integer", "minimum": 0},
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="current Paint overlays would be exported as PNG",
    )
    pbr_settings = {
        "type": "object",
        "properties": {
            "normal_strength": {"type": "number", "minimum": 0.0, "maximum": 12.0},
            "normal_radius_px": {"type": "number", "minimum": 0.0, "maximum": 24.0},
            "normal_format": {"type": "string", "enum": ["unreal_directx", "directx", "opengl"]},
            "normal_filter": {"type": "string", "enum": ["sobel", "central_difference"]},
            "height_invert": {"type": "boolean"},
            "height_contrast": {"type": "number", "minimum": 0.1, "maximum": 4.0},
            "height_blur_px": {"type": "number", "minimum": 0.0, "maximum": 8.0},
            "edge_aware_smoothing": {"type": "boolean"},
            "edge_aware_sensitivity": {"type": "number", "minimum": 0.0, "maximum": 32.0},
            "ao_strength": {"type": "number", "minimum": 0.0, "maximum": 3.0},
            "ao_radius_px": {"type": "number", "minimum": 0.0, "maximum": 64.0},
            "ao_algorithm": {"type": "string", "enum": ["heightfield_horizon", "legacy_blur"]},
            "ao_samples": {"type": "integer", "minimum": 4, "maximum": 32},
            "ao_steps": {"type": "integer", "minimum": 2, "maximum": 24},
            "ao_height_scale": {"type": "number", "minimum": 0.1, "maximum": 64.0},
            "ao_multiscale": {"type": "boolean"},
            "cavity_strength": {"type": "number", "minimum": 0.0, "maximum": 2.0},
            "cavity_radius_px": {"type": "number", "minimum": 0.2, "maximum": 32.0},
            "curvature_strength": {"type": "number", "minimum": 0.0, "maximum": 8.0},
            "roughness_bias": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "roughness_detail": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "metallic_value": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "preview_light_elevation": {"type": "number", "minimum": 3.0, "maximum": 89.0},
        },
    }
    registry.register_adapter_action(
        "paint.pbr.preview",
        "Render a Painter document AR/PBR plane or texture-map preview from the current visible Painter document.",
        "paint",
        "paint_pbr_preview",
        params_schema=schema_object(
            {
                "path": {"type": "string"},
                "preview_mode": {
                    "type": "string",
                    "enum": [
                        "material",
                        "base_color",
                        "normal",
                        "ao",
                        "roughness",
                        "metallic",
                        "height",
                        "cavity",
                        "curvature",
                        "unreal_orm",
                        "arm",
                        "gltf_mr",
                    ],
                },
                "preview_shape": {"type": "string", "enum": ["plane", "sphere"]},
                "width": {"type": "integer", "minimum": 64, "maximum": 8192},
                "settings": pbr_settings,
                "allow_cpu": {
                    "type": "boolean",
                    "description": "Diagnostic only. Product Painter PBR preview defaults to GPU-required mode.",
                },
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="Painter PBR map preview would be rendered",
    )
    registry.register_adapter_action(
        "paint.pbr.export",
        "Export separate and packed AR/PBR texture maps from the current visible Painter document.",
        "paint",
        "paint_pbr_export",
        params_schema=schema_object(
            {
                "output_dir": {"type": "string"},
                "settings": pbr_settings,
                "maps": {"type": "array", "items": {"type": "string"}},
                "packed_layouts": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["unreal_orm", "orm", "arm", "rma", "gltf_mr"]},
                },
                "packed": {"type": "boolean"},
                "allow_cpu": {
                    "type": "boolean",
                    "description": "Diagnostic only. Product Painter PBR export defaults to GPU-required mode.",
                },
            }
        ),
        mutating=True,
        changed=True,
        undo_label="Export Painter PBR maps",
        dry_summary="Painter PBR maps would be exported",
    )
    registry.register_adapter_action(
        "paint.pbr.backend_status",
        "Report Painter PBR Texture Lab CPU/GPU backend availability and selected backend.",
        "paint",
        "paint_pbr_backend_status",
        params_schema=schema_object(
            {
                "backend": {"type": "string", "enum": ["auto", "cpu", "torch_cuda", "cupy", "opencv_cuda"]},
                "allow_cpu": {
                    "type": "boolean",
                    "description": "Diagnostic only. Product Painter PBR backend selection defaults to GPU-required mode.",
                },
            }
        ),
        mutating=False,
        changed=False,
        dry_summary="Painter PBR Texture Lab backend status would be reported",
    )
    registry.register_adapter_action(
        "paint.pbr.substrate_plan",
        "Return Unreal Default Lit and Substrate wiring guidance for Painter PBR map exports.",
        "paint",
        "paint_pbr_substrate_plan",
        params_schema=schema_object({"settings": pbr_settings}),
        mutating=False,
        changed=False,
        dry_summary="Painter PBR Substrate plan would be returned",
    )
    from app.actions.paint_ui_production_namespace import (
        register_paint_ui_production_actions,
    )

    register_paint_ui_production_actions(registry)


__all__ = ["register_paint_actions"]
