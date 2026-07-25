"""Paint / drawing action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object
from app.painter_brush_catalog import DESIGNER_BRUSH_STYLE_IDS


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
        "Add a new layer to the active Painter document.",
        "paint",
        "paint_layer_add",
        params_schema=schema_object({"name": {"type": "string"}}),
        undo_label="Add Painter layer",
        dry_summary="a Painter layer would be added",
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


__all__ = ["register_paint_actions"]
