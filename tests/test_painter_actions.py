from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_painter_actions_register_and_control_standalone_dialog(tmp_path: Path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()

    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    required = {
        "paint.state",
        "paint.gpu.status",
        "paint.document.new",
        "paint.document.export_png",
        "paint.view.zoom",
        "paint.view.pan",
        "paint.view.grid",
        "paint.quick_mask.set",
        "paint.tool.set",
        "paint.brush.set",
        "paint.window.show_panel",
        "paint.layer.add",
        "paint.layer.select",
        "paint.layer.rename",
        "paint.layer.duplicate",
        "paint.layer.delete",
        "paint.layer.set_visible",
        "paint.layer.set_locked",
        "paint.layer.set_opacity",
        "paint.layer.set_blend_mode",
        "paint.channel.set_visible",
        "paint.channel.select",
        "paint.channel.copy_image",
        "paint.channel.paste_image",
        "paint.selection.select_all",
        "paint.selection.deselect",
        "paint.selection.invert",
        "paint.selection.to_path",
        "paint.selection.rectangle",
        "paint.selection.ellipse",
        "paint.selection.set_aspect",
        "paint.selection.select_by_color",
        "paint.crop.to_selection",
        "paint.image.resize",
        "paint.canvas.resize",
        "paint.canvas.flip",
        "paint.fill.solid",
        "paint.fill.gradient",
        "paint.fill.pattern",
        "paint.mirror.set",
        "paint.layer.mask_from_selection",
        "paint.layer.mask_from_path",
        "paint.layer.mask_create",
        "paint.path.to_selection",
        "paint.path.create",
        "paint.path.delete",
        "paint.path.clear",
        "paint.path.commit",
        "paint.clipboard.copy",
        "paint.clipboard.cut",
        "paint.clipboard.paste",
        "paint.reference.state",
        "paint.reference.add",
        "paint.reference.update",
        "paint.reference.delete",
        "paint.reference.duplicate",
        "paint.reference.bake",
        "paint.reference.sample_color",
        "paint.reference.extract_palette",
        "paint.3d_blockout.state",
        "paint.3d_blockout.add",
        "paint.3d_blockout.update",
        "paint.3d_blockout.delete",
        "paint.3d_blockout.duplicate",
        "paint.3d_blockout.align_ground",
        "paint.3d_blockout.snap",
        "paint.3d_blockout.camera",
        "paint.3d_blockout.camera_preset",
        "paint.3d_blockout.bake",
        "paint.pbr.preview",
        "paint.pbr.export",
        "paint.pbr.backend_status",
        "paint.pbr.substrate_plan",
    }
    assert required <= action_ids

    state = registry.execute("paint.state").to_dict()
    assert state["ok"]
    assert state["result"]["document"]["width"] == 640
    assert state["result"]["gpu"]["remote_safe"] is True

    gpu_status = registry.execute("paint.gpu.status").to_dict()
    assert gpu_status["ok"]
    assert gpu_status["result"]["renderer"] == "painter_blockout_opengl_offscreen_v1"
    assert gpu_status["result"]["remote_safe"] is True
    assert gpu_status["result"]["fallback_on_context_failure"] is True
    assert gpu_status["result"]["remote_work_contract"]["safe_for_rdp"] is True
    assert gpu_status["result"]["remote_work_contract"]["fallback_is_product_path"] is True

    added = registry.execute("paint.layer.add", {"name": "AI Ink"}).to_dict()
    assert added["ok"]
    layer_id = added["result"]["active_layer_id"]
    assert any(row["name"] == "AI Ink" for row in added["result"]["layers"])

    selected_layer = registry.execute(
        "paint.layer.select",
        {"layer_id": layer_id},
    ).to_dict()
    assert selected_layer["ok"]
    assert selected_layer["result"]["active_layer_id"] == layer_id

    tool = registry.execute("paint.tool.set", {"tool": "path"}).to_dict()
    assert tool["ok"]
    assert dialog.path_btn.isChecked()

    brush = registry.execute(
        "paint.brush.set",
        {
            "preset": "real_wet_oil",
            "hardness": 72,
            "spacing": 36,
            "angle": -12,
            "roundness": 64,
            "flip_x": True,
        },
    ).to_dict()
    assert brush["ok"]
    assert dialog.pen_btn.isChecked()
    assert brush["result"]["brush"]["style"] == "real_wet_oil"
    assert brush["result"]["brush"]["width_px"] == 28.0
    assert brush["result"]["brush"]["detail"]["hardness"] == 72
    assert brush["result"]["brush"]["detail"]["spacing"] == 36
    assert brush["result"]["brush"]["detail"]["angle"] == -12
    assert brush["result"]["brush"]["detail"]["roundness"] == 64
    assert brush["result"]["brush"]["detail"]["flip_x"] is True
    assert dialog.canvas._brush_hardness == 72
    assert dialog.canvas._brush_spacing == 36
    assert dialog.canvas._brush_angle == -12
    assert dialog.canvas._brush_roundness == 64
    assert dialog.canvas._brush_flip_x is True

    brush_panel = registry.execute("paint.window.show_panel", {"panel": "brush"}).to_dict()
    assert brush_panel["ok"]
    assert dialog._tool_status_label.text() == "Brush settings"

    panel = registry.execute("paint.window.show_panel", {"panel": "paths"}).to_dict()
    assert panel["ok"]
    assert dialog._layer_channel_path_tabs.currentIndex() == 2

    grid = registry.execute(
        "paint.view.grid",
        {"visible": True, "snap": True, "size_px": 48},
    ).to_dict()
    assert grid["ok"]
    assert grid["result"]["view"]["grid_visible"] is True
    assert grid["result"]["view"]["snap_to_grid"] is True
    assert grid["result"]["view"]["grid_size_px"] == 48

    quick = registry.execute("paint.quick_mask.set", {"enabled": True}).to_dict()
    assert quick["ok"]
    assert quick["result"]["selection"]["quick_mask_enabled"] is True

    renamed = registry.execute(
        "paint.layer.rename",
        {"layer_id": layer_id, "name": "Line Art"},
    ).to_dict()
    assert renamed["ok"]
    assert any(row["name"] == "Line Art" for row in renamed["result"]["layers"])

    opacity = registry.execute(
        "paint.layer.set_opacity",
        {"layer_id": layer_id, "opacity": 42},
    ).to_dict()
    assert opacity["ok"]
    assert next(row for row in opacity["result"]["layers"] if row["layer_id"] == layer_id)["opacity"] == 42

    blend = registry.execute(
        "paint.layer.set_blend_mode",
        {"layer_id": layer_id, "blend_mode": "multiply"},
    ).to_dict()
    assert blend["ok"]
    assert next(row for row in blend["result"]["layers"] if row["layer_id"] == layer_id)["blend_mode"] == "multiply"

    hidden = registry.execute(
        "paint.layer.set_visible",
        {"layer_id": layer_id, "visible": False},
    ).to_dict()
    assert hidden["ok"]
    assert next(row for row in hidden["result"]["layers"] if row["layer_id"] == layer_id)["visible"] is False

    locked = registry.execute(
        "paint.layer.set_locked",
        {"layer_id": layer_id, "locked": True},
    ).to_dict()
    assert locked["ok"]
    assert next(row for row in locked["result"]["layers"] if row["layer_id"] == layer_id)["locked"] is True
    registry.execute(
        "paint.layer.set_locked",
        {"layer_id": layer_id, "locked": False},
    )

    channel = registry.execute(
        "paint.channel.set_visible",
        {"channel": "Red", "visible": False},
    ).to_dict()
    assert channel["ok"]
    assert channel["result"]["channels"]["Red"] is False

    selected_channel = registry.execute("paint.channel.select", {"channel": "Green"}).to_dict()
    assert selected_channel["ok"]
    assert selected_channel["result"]["selected_channel"] == "Green"
    copied_channel = registry.execute("paint.channel.copy_image", {"channel": "Blue"}).to_dict()
    assert copied_channel["ok"]
    pasted_channel = registry.execute("paint.channel.paste_image", {"channel": "Alpha"}).to_dict()
    assert pasted_channel["ok"]
    assert pasted_channel["result"]["selected_channel"] == "Alpha"

    selected = registry.execute("paint.selection.select_all").to_dict()
    assert selected["ok"]
    assert selected["result"]["selection"]["active"] is True
    assert selected["result"]["selection"]["point_count"] == 4

    masked = registry.execute(
        "paint.layer.mask_from_selection",
        {"layer_id": layer_id},
    ).to_dict()
    assert masked["ok"]
    assert next(row for row in masked["result"]["layers"] if row["layer_id"] == layer_id)["mask_enabled"] is True

    inverted = registry.execute("paint.selection.invert").to_dict()
    assert inverted["ok"]
    assert inverted["result"]["selection"]["inverted"] is True

    path = registry.execute("paint.selection.to_path").to_dict()
    assert path["ok"]
    assert path["result"]["paths"]["saved_path_count"] >= 1

    path_to_selection = registry.execute(
        "paint.path.to_selection",
        {"path_id": "path:0"},
    ).to_dict()
    assert path_to_selection["ok"]
    assert path_to_selection["result"]["selection"]["active"] is True

    mask_from_path = registry.execute(
        "paint.layer.mask_from_path",
        {"layer_id": layer_id, "path_id": "path:0"},
    ).to_dict()
    assert mask_from_path["ok"]

    created_path = registry.execute(
        "paint.path.create",
        {
            "points": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.9, "y": 0.1},
                {"x": 0.5, "y": 0.8},
            ],
            "closed": True,
        },
    ).to_dict()
    assert created_path["ok"]
    assert created_path["result"]["paths"]["saved_path_count"] >= 2

    deleted_path = registry.execute("paint.path.delete", {"path_id": "path:1"}).to_dict()
    assert deleted_path["ok"]

    aspect = registry.execute("paint.selection.set_aspect", {"aspect": "square"}).to_dict()
    assert aspect["ok"]
    assert aspect["result"]["selection_aspect"] == "square"
    color_selection = registry.execute(
        "paint.selection.select_by_color",
        {"x": 0.5, "y": 0.5, "tolerance": 12},
    ).to_dict()
    assert color_selection["ok"]
    assert color_selection["result"]["selection"]["active"] is True
    assert color_selection["result"]["tool"] == "magic_select"
    rectangle = registry.execute(
        "paint.selection.rectangle",
        {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.35, "aspect": "free"},
    ).to_dict()
    assert rectangle["ok"]
    assert rectangle["result"]["selection"]["point_count"] == 4
    ellipse = registry.execute(
        "paint.selection.ellipse",
        {"x1": 0.1, "y1": 0.1, "x2": 0.4, "y2": 0.35, "aspect": "free"},
    ).to_dict()
    assert ellipse["ok"]
    assert ellipse["result"]["selection"]["point_count"] == 32

    mirror = registry.execute("paint.mirror.set", {"x": True, "y": False}).to_dict()
    assert mirror["ok"]
    assert mirror["result"]["mirror"]["x"] is True

    resized_image = registry.execute(
        "paint.image.resize",
        {"width": 800, "height": 450},
    ).to_dict()
    assert resized_image["ok"]
    assert resized_image["result"]["document"]["width"] == 800
    resized_canvas = registry.execute(
        "paint.canvas.resize",
        {"width": 960, "height": 540, "background": "transparent"},
    ).to_dict()
    assert resized_canvas["ok"]
    assert resized_canvas["result"]["document"]["width"] == 960
    flipped = registry.execute("paint.canvas.flip", {"axis": "horizontal"}).to_dict()
    assert flipped["ok"]
    solid = registry.execute("paint.fill.solid", {"color": "#3366CC"}).to_dict()
    assert solid["ok"]
    gradient = registry.execute(
        "paint.fill.gradient",
        {"color1": "#202833", "color2": "#E4EEF8"},
    ).to_dict()
    assert gradient["ok"]
    pattern = registry.execute(
        "paint.fill.pattern",
        {"color1": "#203040", "color2": "#7EA5D8"},
    ).to_dict()
    assert pattern["ok"]
    reveal_mask = registry.execute(
        "paint.layer.mask_create",
        {"layer_id": layer_id, "mask_type": "white"},
    ).to_dict()
    assert reveal_mask["ok"]
    assert next(row for row in reveal_mask["result"]["layers"] if row["layer_id"] == layer_id)["mask_point_count"] == 4
    registry.execute(
        "paint.selection.rectangle",
        {"x1": 0.0, "y1": 0.0, "x2": 0.5, "y2": 0.5, "aspect": "free"},
    )
    cropped = registry.execute("paint.crop.to_selection").to_dict()
    assert cropped["ok"]
    assert cropped["result"]["document"]["width"] == 480

    zoom = registry.execute("paint.view.zoom", {"percent": 150}).to_dict()
    assert zoom["ok"]
    assert zoom["result"]["view"]["zoom_percent"] == 150
    max_zoom = registry.execute("paint.view.zoom", {"percent": 800}).to_dict()
    assert max_zoom["ok"]
    assert max_zoom["result"]["view"]["zoom_percent"] == 800
    assert max_zoom["result"]["view"]["pixel_grid_visible"] is True

    pan = registry.execute("paint.view.pan", {"dx": 20, "dy": 10}).to_dict()
    assert pan["ok"]

    copied = registry.execute("paint.clipboard.copy").to_dict()
    assert copied["ok"]
    pasted = registry.execute("paint.clipboard.paste").to_dict()
    assert pasted["ok"]
    assert len(pasted["result"]["layers"]) >= 3

    out_path = tmp_path / "painter_action_overlay.png"
    exported = registry.execute(
        "paint.document.export_png",
        {"path": str(out_path), "include_background": False},
    ).to_dict()
    assert exported["ok"]
    assert out_path.exists()

    pbr_preview_path = tmp_path / "painter_pbr_preview.png"
    pbr_preview = registry.execute(
        "paint.pbr.preview",
        {
            "path": str(pbr_preview_path),
            "preview_mode": "material",
            "preview_shape": "sphere",
            "width": 128,
            "allow_cpu": True,
        },
    ).to_dict()
    assert pbr_preview["ok"]
    assert pbr_preview["result"]["preview_shape"] == "sphere"
    assert pbr_preview_path.exists()
    pbr_export = registry.execute(
        "paint.pbr.export",
        {
            "output_dir": str(tmp_path / "painter_pbr_maps"),
            "packed_layouts": ["arm"],
            "settings": {"metallic_value": 0.1},
            "allow_cpu": True,
        },
    ).to_dict()
    assert pbr_export["ok"]
    assert (tmp_path / "painter_pbr_maps" / "painter_visible_document_source_arm.png").exists()
    pbr_plan = registry.execute("paint.pbr.substrate_plan").to_dict()
    assert pbr_plan["ok"]
    assert pbr_plan["result"]["target"] == "Unreal Engine Substrate Slab BSDF"
    pbr_backend = registry.execute("paint.pbr.backend_status", {"allow_cpu": True}).to_dict()
    assert pbr_backend["ok"]
    assert pbr_backend["result"]["active"] in {"cpu", "torch_cuda"}
    assert "install_guidance" in pbr_backend["result"]["status"]

    reference_path = tmp_path / "paint_reference.png"
    assert create_blank_paint_pixmap(160, 90, "#88AAFF").save(str(reference_path), "PNG")
    reference = registry.execute(
        "paint.reference.add",
        {
            "path": str(reference_path),
            "name": "Color Script",
            "x_norm": 0.1,
            "y_norm": 0.12,
            "width_norm": 0.4,
            "height_norm": 0.25,
            "opacity": 0.5,
            "rotation_deg": 12,
        },
    ).to_dict()
    assert reference["ok"]
    assert reference["result"]["board"]["reference_count"] == 1
    assert reference["result"]["ui_contract"]["exported_by_default"] is False
    reference_id = reference["result"]["board"]["references"][0]["id"]
    moved_reference = registry.execute(
        "paint.reference.update",
        {"reference_id": reference_id, "x_norm": 0.2, "opacity": 0.72, "rotation_deg": -20, "locked": True},
    ).to_dict()
    assert moved_reference["ok"]
    assert moved_reference["result"]["board"]["references"][0]["x_norm"] == 0.2
    assert moved_reference["result"]["board"]["references"][0]["opacity"] == 0.72
    assert moved_reference["result"]["board"]["references"][0]["rotation_deg"] == -20.0
    assert moved_reference["result"]["board"]["references"][0]["locked"] is True
    sampled_reference = registry.execute(
        "paint.reference.sample_color",
        {"reference_id": reference_id, "x_norm": 0.5, "y_norm": 0.5},
    ).to_dict()
    assert sampled_reference["ok"]
    assert sampled_reference["result"]["sample"]["hex"] == "#88AAFF"
    palette_reference = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": reference_id, "max_colors": 4},
    ).to_dict()
    assert palette_reference["ok"]
    assert palette_reference["result"]["palette"]["color_count"] >= 1
    duplicated_reference = registry.execute(
        "paint.reference.duplicate",
        {"reference_id": reference_id, "offset_x": 0.03},
    ).to_dict()
    assert duplicated_reference["ok"]
    assert duplicated_reference["result"]["board"]["reference_count"] == 2
    baked_reference = registry.execute("paint.reference.bake", {"reference_id": reference_id}).to_dict()
    assert baked_reference["ok"]
    assert baked_reference["result"]["bake"]["path"] == str(reference_path)
    deleted_reference = registry.execute("paint.reference.delete", {"reference_id": reference_id}).to_dict()
    assert deleted_reference["ok"]
    assert deleted_reference["result"]["board"]["reference_count"] == 1

    blockout = registry.execute(
        "paint.3d_blockout.add",
        {"kind": "box", "name": "Room Block", "sx": 2.0, "sy": 1.2, "preview_width": 320, "preview_height": 180},
    ).to_dict()
    assert blockout["ok"]
    assert blockout["result"]["scene"]["primitive_count"] == 1
    assert blockout["result"]["renderer"]["preferred"] == "painter_blockout_opengl_offscreen_v1"
    assert blockout["result"]["renderer"]["remote_safe"] is True
    assert blockout["result"]["gpu_contract"]["future_gpu_preview"] is True
    assert blockout["result"]["gpu_contract"]["opengl_first_preview"] is True
    assert blockout["result"]["gpu_contract"]["qpainter_fallback"] is True
    assert blockout["result"]["ui_guardrails"]["preserve_texture_lab_entry_points"] is True
    assert blockout["result"]["ui_guardrails"]["layers_channels_paths_remain_primary_dock"] is True
    primitive_id = blockout["result"]["scene"]["primitives"][0]["id"]
    updated_blockout = registry.execute(
        "paint.3d_blockout.update",
        {"primitive_id": primitive_id, "kind": "arch", "x": 1.0, "sx": 3.0, "sy": 2.2, "rz": 12.0},
    ).to_dict()
    assert updated_blockout["ok"]
    assert updated_blockout["result"]["scene"]["primitives"][0]["kind"] == "arch"
    assert updated_blockout["result"]["gizmo_contract"]["object_modes"] == ["move", "rotate", "scale"]
    duplicated_blockout = registry.execute(
        "paint.3d_blockout.duplicate",
        {"primitive_id": primitive_id, "offset_x": 0.5, "offset_z": 0.5},
    ).to_dict()
    assert duplicated_blockout["ok"]
    assert duplicated_blockout["result"]["scene"]["primitive_count"] == 2
    grounded_blockout = registry.execute(
        "paint.3d_blockout.align_ground",
        {"primitive_id": primitive_id},
    ).to_dict()
    assert grounded_blockout["ok"]
    assert grounded_blockout["result"]["scene"]["primitives"][0]["position"][1] == 0.0
    snap_blockout = registry.execute(
        "paint.3d_blockout.snap",
        {"enabled": True, "primitive_id": primitive_id},
    ).to_dict()
    assert snap_blockout["ok"]
    assert snap_blockout["result"]["scene"]["snap_to_grid"] is True
    camera = registry.execute(
        "paint.3d_blockout.camera",
        {"yaw_degrees": 20, "pitch_degrees": -10, "target_x": 0.5, "distance": 5.0, "fov_degrees": 35},
    ).to_dict()
    assert camera["ok"]
    assert camera["result"]["scene"]["camera"]["fov_degrees"] == 35.0
    assert camera["result"]["scene"]["camera"]["target"][0] == 0.5
    camera_preset = registry.execute(
        "paint.3d_blockout.camera_preset",
        {"preset": "top"},
    ).to_dict()
    assert camera_preset["ok"]
    assert camera_preset["result"]["scene"]["camera"]["pitch_degrees"] == -82.0
    blockout_state = registry.execute("paint.3d_blockout.state").to_dict()
    assert blockout_state["ok"]
    assert blockout_state["result"]["projection"]["face_count"] > 0
    baked_blockout = registry.execute("paint.3d_blockout.bake").to_dict()
    assert baked_blockout["ok"]
    assert baked_blockout["result"]["bake"]["stroke_count"] > 0
    assert baked_blockout["result"]["bake"]["layer_name"] == "3D Blockout Guide"
    deleted_blockout = registry.execute("paint.3d_blockout.delete", {"primitive_id": primitive_id}).to_dict()
    assert deleted_blockout["ok"]
    assert deleted_blockout["result"]["scene"]["primitive_count"] == 1

    new_doc = registry.execute(
        "paint.document.new",
        {"width": 800, "height": 600, "background": "transparent"},
    ).to_dict()
    assert new_doc["ok"]
    assert new_doc["result"]["document"]["width"] == 800
    assert new_doc["result"]["document"]["background_layer_present"] is False

    from PySide6.QtWidgets import QApplication

    QApplication.clipboard().clear()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()
