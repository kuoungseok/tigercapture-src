"""Paint / drawing action registrations."""
from __future__ import annotations

from typing import Any

from app.actions.schema import schema_object


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
        params_schema=schema_object({"percent": {"type": "integer", "minimum": 25, "maximum": 400}}),
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
        "paint.window.show_panel",
        "Show the Layers, Channels, Paths, or History panel in the active Painter window.",
        "paint",
        "paint_window_show_panel",
        params_schema=schema_object(
            {"panel": {"type": "string", "enum": ["layers", "channels", "paths", "history"]}},
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


__all__ = ["register_paint_actions"]
