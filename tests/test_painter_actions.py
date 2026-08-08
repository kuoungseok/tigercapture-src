from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


def _raise_refresh(error: BaseException):
    def fail(*_args, **_kwargs):
        raise error

    return fail


def test_committed_paint_action_data_exposes_optional_ui_refresh_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.drawing_editor_object_import import PaintImportObject
    from app.painter_3d_blockout import add_blockout_primitive
    from app.painter_reference_board import add_reference_image
    import app.drawing_editor_object_import as editor_import

    paint_object = PaintImportObject(id="object:1", kind="test", label="Test object")
    png_path = tmp_path / "rendered.png"

    class Adapter(PaintAdapterMixin):
        def __init__(self, owner):
            self.owner = owner

        def _require_owner(self):
            return self.owner

        def _paint_dialog_owner(self):
            return self.owner

        def _paint_find_import_object(self, **_params):
            return paint_object

        def _paint_canvas_size(self):
            return (640, 360)

        def _paint_action_time_ms(self, _time_ms):
            return 125

        def _register_change(self, _label):
            return None

    owner = SimpleNamespace(
        _stickers=[],
        _spawn_sticker_item=_raise_refresh(RuntimeError("spawn unavailable")),
        _update_sticker_visibility=_raise_refresh(ValueError("visibility stale")),
        _drawing_canvas=SimpleNamespace(update=_raise_refresh(OSError("canvas detached"))),
    )
    adapter = Adapter(owner)
    render_report = {
        "png_path": str(png_path),
        "rect_norm": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
    }
    monkeypatch.setattr(
        editor_import,
        "render_paint_import_object",
        lambda *_args, **_kwargs: dict(render_report),
    )

    imported = adapter.paint_editor_object_import()

    assert len(owner._stickers) == 1
    assert imported["sticker_count"] == 1
    assert imported["ui_refresh"] == {
        "attempted": True,
        "committed": True,
        "ok": False,
        "errors": [
            {"operation": "spawn_sticker_item", "type": "RuntimeError", "message": "spawn unavailable"},
            {"operation": "update_sticker_visibility", "type": "ValueError", "message": "visibility stale"},
            {"operation": "drawing_canvas_update", "type": "OSError", "message": "canvas detached"},
        ],
    }

    boundary_import = adapter.paint_editor_object_import(
        x_norm=0.96,
        y_norm=0.96,
        width_norm=0.04,
        height_norm=0.04,
    )
    assert boundary_import["sticker"] == {
        "png_path": str(png_path),
        "x_norm": 0.96,
        "y_norm": 0.96,
        "width_norm": 0.04,
        "height_norm": 0.04,
        "start_ms": 125,
        "end_ms": -1,
        "z_index": 2,
    }
    committed_count = len(owner._stickers)
    with pytest.raises(ValueError, match="fit the canvas"):
        adapter.paint_editor_object_import(x_norm=0.8)
    assert len(owner._stickers) == committed_count

    render_report["rect_norm"] = {
        "x": float("nan"),
        "y": float("inf"),
        "w": float("-inf"),
        "h": "bad",
    }
    recovered = adapter.paint_editor_object_import()
    assert recovered["render"]["rect_norm"] == {
        "x": 0.0,
        "y": 0.0,
        "w": 0.04,
        "h": 0.04,
    }
    json.dumps(recovered, allow_nan=False)

    committed_count = len(owner._stickers)
    render_report["diagnostic"] = {"bad": float("nan")}
    with pytest.raises(ValueError, match="NaN or infinity"):
        adapter.paint_editor_object_import()
    assert len(owner._stickers) == committed_count
    render_report.pop("diagnostic")

    paint_object.payload["bad"] = float("inf")
    with pytest.raises(ValueError, match="NaN or infinity"):
        adapter.paint_editor_object_import()
    assert len(owner._stickers) == committed_count
    paint_object.payload.clear()

    owner._ensure_3d_blockout_layer = _raise_refresh(RuntimeError("layer unavailable"))
    owner._refresh_3d_blockout_panel = _raise_refresh(ValueError("panel stale"))
    owner.update = _raise_refresh(OSError("dialog detached"))
    scene = add_blockout_primitive(None, kind="box")

    blockout_refresh = adapter._store_paint_3d_blockout_scene(owner, scene)
    blockout_payload = adapter._paint_3d_blockout_payload(scene, preview_width=64, preview_height=64)

    assert owner._painter_3d_blockout_scene["primitive_count"] == 1
    assert blockout_refresh["committed"] is True
    assert blockout_refresh["ok"] is False
    assert [row["operation"] for row in blockout_refresh["errors"]] == [
        "ensure_3d_blockout_layer",
        "refresh_3d_blockout_panel",
        "paint_dialog_update",
    ]
    assert blockout_payload["ui_refresh"] == blockout_refresh

    owner._refresh_reference_board_panel = _raise_refresh(RuntimeError("reference panel unavailable"))
    board = add_reference_image(None, path=str(tmp_path / "reference.png"))

    reference_refresh = adapter._store_paint_reference_board(owner, board)
    reference_payload = adapter._paint_reference_payload(owner)

    assert owner._painter_reference_board["reference_count"] == 1
    assert reference_refresh["committed"] is True
    assert reference_refresh["ok"] is False
    assert reference_refresh["errors"] == [
        {
            "operation": "refresh_reference_board_panel",
            "type": "RuntimeError",
            "message": "reference panel unavailable",
        },
        {"operation": "paint_dialog_update", "type": "OSError", "message": "dialog detached"},
    ]
    assert reference_payload["ui_refresh"] == reference_refresh


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_smoothed_stroke_outside_normalized_canvas_fails_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app import painter_stroke_geometry

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    undo_before = len(dialog._undo_stack)
    strokes_before = list(dialog.canvas.embedded_strokes())

    def outside_after_smoothing(points):
        result = [dict(point) for point in points]
        result[0]["x"] = -0.01
        return result

    monkeypatch.setattr(
        painter_stroke_geometry,
        "smooth_action_points",
        outside_after_smoothing,
    )
    result = registry.execute(
        "paint.stroke.draw",
        {
            "strokes": [{
                "path_mode": "smooth",
                "points": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 1.0}],
            }],
        },
    ).to_dict()
    assert not result["ok"]
    assert "outside normalized canvas bounds" in result["error"]
    assert list(dialog.canvas.embedded_strokes()) == strokes_before
    assert len(dialog._undo_stack) == undo_before
    dialog.close()
    app.processEvents()


def test_flip_fill_and_mirror_actions_have_measured_raster_contract() -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    layer = dialog._active_paint_layer()
    asymmetric = QImage(8, 8, QImage.Format.Format_ARGB32_Premultiplied)
    asymmetric.fill(QColor("#000000"))
    asymmetric.setPixelColor(0, 0, QColor("#FF0000"))
    asymmetric.setPixelColor(7, 0, QColor("#0000FF"))
    dialog._set_paint_layer_raster(layer.layer_id, asymmetric)

    flipped = registry.execute("paint.canvas.flip", {"axis": "horizontal"}).to_dict()
    assert flipped["ok"]
    raster = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert raster is not None
    assert raster.pixelColor(0, 0).name().upper() == "#0000FF"
    assert raster.pixelColor(7, 0).name().upper() == "#FF0000"

    gradient = registry.execute(
        "paint.fill.gradient",
        {"color1": "#000000", "color2": "#FFFFFF"},
    ).to_dict()
    assert gradient["ok"]
    raster = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert raster is not None
    top_left = raster.pixelColor(0, 0)
    bottom_right = raster.pixelColor(7, 7)
    assert top_left.red() == top_left.green() == top_left.blue()
    assert bottom_right.red() == bottom_right.green() == bottom_right.blue()
    assert top_left.red() < bottom_right.red()

    pattern = registry.execute(
        "paint.fill.pattern",
        {"color1": "#102030", "color2": "#D0E0F0"},
    ).to_dict()
    assert pattern["ok"]
    raster = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert raster is not None
    colors = {
        raster.pixelColor(x, y).name().upper()
        for y in range(raster.height())
        for x in range(raster.width())
    }
    assert colors == {"#102030", "#D0E0F0"}

    same_pattern = registry.execute(
        "paint.fill.pattern",
        {"color1": "#102030", "color2": "#D0E0F0"},
    ).to_dict()
    assert same_pattern["ok"] is False
    same_raster = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert same_raster is not None
    assert same_raster == raster

    unchanged = registry.execute("paint.mirror.set", {"x": False}).to_dict()
    assert unchanged["ok"] is False
    changed = registry.execute("paint.mirror.set", {"x": True}).to_dict()
    assert changed["ok"]
    assert changed["result"]["mirror"]["x"] is True

    layer.locked = True
    before = raster.copy()
    locked_fill = registry.execute(
        "paint.fill.solid",
        {"color": "#ABCDEF"},
    ).to_dict()
    assert locked_fill["ok"] is False
    after = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert after is not None
    assert after == before
    dialog.close()
    app.processEvents()


def test_path_to_selection_uses_authored_path_and_reports_missing_path_failure() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    authored_points = [(0.0, 0.0), (0.75, 0.0), (0.0, 0.75)]
    dialog.canvas.set_path_snapshot(authored_points)
    dialog._selected_path_item_id = "selection"

    converted = registry.execute(
        "paint.path.to_selection",
        {"path_id": "work-path"},
    ).to_dict()
    assert converted["ok"]
    assert dialog.canvas.selection_snapshot() == authored_points
    assert dialog._selected_path_item_id == "selection"

    repeat_undo_count = len(dialog._undo_stack)
    repeated = registry.execute(
        "paint.path.to_selection",
        {"path_id": "work-path"},
    ).to_dict()
    assert repeated["ok"] is False
    assert len(dialog._undo_stack) == repeat_undo_count

    selection_before = dialog.canvas.selection_snapshot()
    selected_path_before = dialog._selected_path_item_id
    undo_count_before = len(dialog._undo_stack)
    missing = registry.execute(
        "paint.path.to_selection",
        {"path_id": "path:999"},
    ).to_dict()
    assert missing["ok"] is False
    assert dialog.canvas.selection_snapshot() == selection_before
    assert dialog._selected_path_item_id == selected_path_before
    assert len(dialog._undo_stack) == undo_count_before

    dialog.canvas.set_path_snapshot([(0.0, 0.0), (1.0, 1.0)])
    short = registry.execute(
        "paint.path.to_selection",
        {"path_id": "work-path"},
    ).to_dict()
    assert short["ok"] is False
    assert dialog.canvas.selection_snapshot() == selection_before
    assert dialog._selected_path_item_id == selected_path_before
    assert len(dialog._undo_stack) == undo_count_before
    dialog.close()
    app.processEvents()


def test_clipboard_actions_report_truthful_selection_round_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    from PySide6.QtCore import QByteArray, QMimeData
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import (
        PAINT_CLIPBOARD_MIME,
        PAINT_CLIPBOARD_SCHEMA,
        PaintDialog,
        create_blank_paint_pixmap,
    )

    clipboard = QApplication.clipboard()
    clipboard.clear()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(4, 2, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    layer = dialog._active_paint_layer()

    paste_undo_before = len(dialog._undo_stack)
    empty_paste = registry.execute("paint.clipboard.paste").to_dict()
    assert empty_paste["ok"] is False
    assert len(dialog._undo_stack) == paste_undo_before
    blank_cut = registry.execute("paint.clipboard.cut").to_dict()
    assert blank_cut["ok"] is False
    blank_copy = registry.execute("paint.clipboard.copy").to_dict()
    assert blank_copy["ok"] is False
    mime = clipboard.mimeData()
    assert mime is None or not mime.hasFormat(PAINT_CLIPBOARD_MIME)

    malformed_mime = QMimeData()
    malformed_mime.setData(
        PAINT_CLIPBOARD_MIME,
        QByteArray(json.dumps({
            "schema": PAINT_CLIPBOARD_SCHEMA,
            "kind": "paint_layer",
            "payload": {},
        }).encode("utf-8")),
    )
    malformed_preview = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
    malformed_preview.fill(QColor("#FF0000"))
    malformed_mime.setImageData(malformed_preview)
    clipboard.setMimeData(malformed_mime)
    malformed_undo_before = len(dialog._undo_stack)
    malformed_layer_count_before = len(dialog._paint_layers)
    malformed_paste = registry.execute("paint.clipboard.paste").to_dict()
    assert malformed_paste["ok"] is False
    assert len(dialog._undo_stack) == malformed_undo_before
    assert len(dialog._paint_layers) == malformed_layer_count_before
    clipboard.clear()

    empty_layer_mime = QMimeData()
    empty_layer_mime.setData(
        PAINT_CLIPBOARD_MIME,
        QByteArray(json.dumps({
            "schema": PAINT_CLIPBOARD_SCHEMA,
            "kind": "paint_layer",
            "payload": {
                "layer": {"layer_id": "paint-layer-empty", "name": "Empty"},
                "strokes": [],
                "raster_png": "",
                "mask_png": "",
            },
        }).encode("utf-8")),
    )
    clipboard.setMimeData(empty_layer_mime)
    empty_layer_paste = registry.execute("paint.clipboard.paste").to_dict()
    assert empty_layer_paste["ok"] is False
    assert len(dialog._undo_stack) == malformed_undo_before
    assert len(dialog._paint_layers) == malformed_layer_count_before
    clipboard.clear()

    dialog._paint_clipboard = {
        "kind": "paint_layer",
        "layer": "not-a-layer",
        "strokes": "not-a-list",
        "raster": "not-an-image",
    }
    malformed_local_paste = registry.execute("paint.clipboard.paste").to_dict()
    assert malformed_local_paste["ok"] is False
    assert len(dialog._undo_stack) == malformed_undo_before
    assert len(dialog._paint_layers) == malformed_layer_count_before
    dialog._paint_clipboard = None

    raster = QImage(4, 2, QImage.Format.Format_ARGB32_Premultiplied)
    raster.fill(QColor("#FF0000"))
    dialog._set_paint_layer_raster(layer.layer_id, raster)
    dialog.canvas.select_rectangle(0.0, 0.0, 0.5, 1.0)
    copied = registry.execute("paint.clipboard.copy").to_dict()
    assert copied["ok"]
    mime = clipboard.mimeData()
    assert mime is not None and mime.hasFormat(PAINT_CLIPBOARD_MIME)
    assert mime.hasImage()

    dialog._paint_clipboard = None
    layer_count_before = len(dialog._paint_layers)
    pasted = registry.execute("paint.clipboard.paste").to_dict()
    assert pasted["ok"]
    assert len(dialog._paint_layers) == layer_count_before + 1
    pasted_layer = dialog._active_paint_layer()
    pasted_raster = dialog._paint_layer_raster(pasted_layer.layer_id, create=False)
    assert pasted_raster is not None
    assert pasted_raster.size() == raster.size()
    assert pasted_raster.pixelColor(0, 0).name().upper() == "#FF0000"
    assert pasted_raster.pixelColor(3, 0).alpha() == 0

    assert dialog._select_paint_layer_by_id(layer.layer_id)
    original_before_failed_write = dialog._paint_layer_raster(
        layer.layer_id, create=False
    )
    assert original_before_failed_write is not None
    original_before_failed_write = original_before_failed_write.copy()
    real_clipboard_write = dialog._write_payload_to_system_clipboard
    monkeypatch.setattr(
        dialog,
        "_write_payload_to_system_clipboard",
        lambda _payload: False,
    )
    failed_write_cut = registry.execute("paint.clipboard.cut").to_dict()
    assert failed_write_cut["ok"] is False
    original_after_failed_write = dialog._paint_layer_raster(
        layer.layer_id, create=False
    )
    assert original_after_failed_write is not None
    assert original_after_failed_write == original_before_failed_write
    monkeypatch.setattr(
        dialog,
        "_write_payload_to_system_clipboard",
        real_clipboard_write,
    )
    cut = registry.execute("paint.clipboard.cut").to_dict()
    assert cut["ok"]
    cut_raster = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert cut_raster is not None
    assert cut_raster.pixelColor(0, 0).alpha() == 0
    assert cut_raster.pixelColor(3, 0).name().upper() == "#FF0000"

    layer.lock_pixels = True
    cut_before = cut_raster.copy()
    locked_cut = registry.execute("paint.clipboard.cut").to_dict()
    assert locked_cut["ok"] is False
    cut_after = dialog._paint_layer_raster(layer.layer_id, create=False)
    assert cut_after is not None and cut_after == cut_before
    clipboard.clear()
    dialog.close()
    app.processEvents()


def test_clipboard_cut_retains_last_paint_node_beside_group() -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, PaintLayer, create_blank_paint_pixmap

    QApplication.clipboard().clear()
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(2, 2, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    paint_layer = dialog._active_paint_layer()
    raster = QImage(2, 2, QImage.Format.Format_ARGB32_Premultiplied)
    raster.fill(QColor("#FF0000"))
    dialog._set_paint_layer_raster(paint_layer.layer_id, raster)
    dialog._paint_layers.append(
        PaintLayer("paint-layer-group", "Group", node_type="group")
    )
    assert dialog._select_paint_layer_by_id(paint_layer.layer_id)

    cut = registry.execute("paint.clipboard.cut").to_dict()
    assert cut["ok"]
    assert len(dialog._paint_layers) == 2
    assert sum(layer.node_type == "paint" for layer in dialog._paint_layers) == 1
    remaining = dialog._paint_layer_raster(paint_layer.layer_id, create=False)
    assert remaining is None
    assert dialog._active_paint_layer().layer_id == paint_layer.layer_id
    QApplication.clipboard().clear()
    dialog.close()
    app.processEvents()


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
    action_specs = {row["id"]: row for row in registry.list_actions()}
    assert (
        action_specs["paint.document.export"]["params_schema"]["properties"]["path"]
        ["pattern"]
        == r".*\S.*"
    )
    export_schema = action_specs["paint.document.export"]["params_schema"]
    assert set(export_schema["required"]) == {"path", "format"}
    assert export_schema["allOf"][0]["then"]["properties"]["format"]["enum"] == [
        "png",
        "tiff",
    ]
    from app.painter_action_contract import (
        PAINT_ACTION_MAX_BRUSH_WIDTH_PX,
        PAINT_ACTION_MAX_POINTS_PER_STROKE,
        PAINT_ACTION_MAX_STROKES_PER_REQUEST,
    )

    stroke_params = action_specs["paint.stroke.draw"]["params_schema"]["properties"]
    assert stroke_params["strokes"]["maxItems"] == PAINT_ACTION_MAX_STROKES_PER_REQUEST
    stroke_schema = stroke_params["strokes"]["items"]["properties"]
    assert stroke_schema["points"]["maxItems"] == PAINT_ACTION_MAX_POINTS_PER_STROKE
    assert stroke_schema["width"]["maximum"] == PAINT_ACTION_MAX_BRUSH_WIDTH_PX
    action_ids = set(action_specs)
    required = {
        "paint.state",
        "paint.gpu.status",
        "paint.document.new",
        "paint.document.export_png",
        "paint.view.zoom",
        "paint.view.zoom_area",
        "paint.view.pan",
        "paint.view.grid",
        "paint.guide.perspective",
        "paint.guide.symmetry",
        "paint.quick_mask.set",
        "paint.tool.set",
        "paint.brush.set",
        "paint.brush.library.view",
        "paint.brush.favorite.set",
        "paint.stroke.draw",
        "paint.history.undo",
        "paint.history.redo",
        "paint.window.show_panel",
        "paint.layer.add",
        "paint.layer.import_image",
        "paint.layer.group.create",
        "paint.layer.set_clipping",
        "paint.layer.group.set_expanded",
        "paint.layer.set_locks",
        "paint.layer.merge_down",
        "paint.layer.merge_visible",
        "paint.layer.flatten",
        "paint.layer.set_type",
        "paint.material.settings.set",
        "paint.material.preview.set",
        "paint.layer.select",
        "paint.layer.rename",
        "paint.layer.duplicate",
        "paint.layer.delete",
        "paint.layer.set_visible",
        "paint.layer.set_locked",
        "paint.layer.set_opacity",
        "paint.layer.set_blend_mode",
        "paint.layer.set_color",
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
        "paint.selection.set_mode",
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
        "paint.layer.mask_state.set",
        "paint.layer.mask.paint",
        "paint.layer.mask.gradient",
        "paint.layer.mask.apply",
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
        "paint.study.analyze_reference",
        "paint.study.segment_regions",
        "paint.study.build_underpaint",
        "paint.study.trace_contours",
        "paint.study.generate_strokes",
        "paint.study.compare_render",
        "paint.study.refine_region",
        "paint.study.quality_report",
        "paint.3d_blockout.state",
        "paint.3d_blockout.add",
        "paint.3d_blockout.update",
        "paint.3d_blockout.delete",
        "paint.3d_blockout.duplicate",
        "paint.3d_blockout.align_ground",
        "paint.3d_blockout.snap",
        "paint.3d_blockout.camera",
        "paint.3d_blockout.material_preview",
        "paint.3d_blockout.camera_preset",
        "paint.3d_blockout.bake",
        "paint.pbr.preview",
        "paint.pbr.export",
        "paint.pbr.backend_status",
        "paint.pbr.substrate_plan",
    }
    assert required <= action_ids
    brush_style_enum = set(
        action_specs["paint.brush.set"]["params_schema"]["properties"]["style"]["enum"]
    )
    assert {
        "filbert_oil",
        "graphite_pencil",
        "watercolor_wash",
        "airbrush_soft",
        "foliage_scatter",
        "paint_splatter",
    } <= brush_style_enum

    state = registry.execute("paint.state").to_dict()
    assert state["ok"]
    assert state["result"]["document"]["width"] == 640
    assert state["result"]["gpu"]["remote_safe"] is True
    assert state["result"]["gpu"]["canvas_renderer"]["remote_safe"] is True
    assert state["result"]["gpu"]["paint_canvas_next_gpu_target"] == "retained_gl_texture_display_and_textured_brush_shader_parity"
    assert state["result"]["gpu"]["capabilities"]["persistent_stroke_atlas"]["enabled"] is True
    assert state["result"]["brush"]["engine"]["preset_thumbnail_mode"] == "actual_stroke_preview"
    bristle_contract = state["result"]["brush"]["engine"]["bristle_model_contract"]
    assert bristle_contract["physical_bristle_claim"] is False
    assert bristle_contract["paint_rheology_claim"] is False

    gpu_status = registry.execute("paint.gpu.status").to_dict()
    assert gpu_status["ok"]
    assert gpu_status["result"]["renderer"] == "painter_blockout_opengl_offscreen_v1"
    assert gpu_status["result"]["canvas"]["renderer"] == "painter_canvas_opengl_persistent_stroke_atlas_v1"
    assert gpu_status["result"]["canvas"]["base_renderer"] == "painter_canvas_opengl_stroke_fbo_v1"
    assert gpu_status["result"]["canvas"]["fallback_renderer"] == "painter_canvas_qpainter_strokes_v1"
    assert gpu_status["result"]["canvas"]["supported_first_pass"]["unsupported_falls_back"] is True
    assert gpu_status["result"]["last_canvas_renderer"]["remote_safe"] is True
    assert gpu_status["result"]["remote_safe"] is True
    assert gpu_status["result"]["fallback_on_context_failure"] is True
    assert gpu_status["result"]["remote_work_contract"]["safe_for_rdp"] is True
    assert gpu_status["result"]["remote_work_contract"]["fallback_is_product_path"] is True

    perspective = registry.execute(
        "paint.guide.perspective",
        {
            "enabled": True,
            "snap": True,
            "mode": 3,
            "horizon": 0.42,
            "left_x": -2.0,
            "right_x": 3.0,
            "vertical_y": -1.5,
        },
    ).to_dict()
    assert perspective["ok"]
    assert perspective["result"]["guides"]["perspective"]["enabled"] is True
    assert perspective["result"]["guides"]["perspective"]["horizon"] == 0.42
    assert perspective["result"]["guides"]["perspective"]["snap"] is True
    assert perspective["result"]["guides"]["perspective"]["mode"] == 3
    assert perspective["result"]["guides"]["perspective"]["left_vp"][0] == -2.0
    assert perspective["result"]["guides"]["perspective"]["vertical_vp"][1] == -1.5

    symmetry = registry.execute(
        "paint.guide.symmetry",
        {"enabled": True, "axis": "horizontal", "position": 0.58},
    ).to_dict()
    assert symmetry["ok"]
    assert symmetry["result"]["guides"]["symmetry"]["enabled"] is True
    assert symmetry["result"]["guides"]["symmetry"]["axis"] == "horizontal"

    high_zoom = registry.execute("paint.view.zoom", {"percent": 800}).to_dict()
    assert high_zoom["ok"]
    assert high_zoom["result"]["gpu"]["high_zoom"]["current_zoom_percent"] == 800
    registry.execute("paint.view.zoom", {"percent": 100})
    zoom_area = registry.execute(
        "paint.view.zoom_area",
        {"x": 0.25, "y": 0.25, "width": 0.5, "height": 0.5},
    ).to_dict()
    assert zoom_area["ok"]
    assert zoom_area["result"]["view"]["zoom_percent"] == 200

    added = registry.execute("paint.layer.add", {"name": "AI Ink"}).to_dict()
    assert added["ok"]
    layer_id = added["result"]["active_layer_id"]
    assert any(row["name"] == "AI Ink" for row in added["result"]["layers"])

    from PySide6.QtGui import QColor
    from app.painter_raster_layers import transparent_raster

    import_source = transparent_raster(24, 16)
    import_source.fill(QColor("#49B86E"))
    import_path = tmp_path / "action_import.png"
    assert import_source.save(str(import_path), "PNG")
    imported = registry.execute(
        "paint.layer.import_image",
        {"path": str(import_path), "name": "Imported Swatch"},
    ).to_dict()
    assert imported["ok"]
    imported_id = imported["result"]["import"]["layer_id"]
    assert dialog._paint_layer_rasters[imported_id].pixelColor(320, 180).name() == "#49b86e"
    assert not dialog.result_stickers()

    material = registry.execute(
        "paint.layer.add",
        {"name": "AI Impasto", "layer_type": "material"},
    ).to_dict()
    assert material["ok"]
    material_layer_id = material["result"]["active_layer_id"]
    assert next(
        row for row in material["result"]["layers"] if row["layer_id"] == material_layer_id
    )["layer_type"] == "material"

    material_settings = registry.execute(
        "paint.material.settings.set",
        {
            "layer_id": material_layer_id,
            "load": 0.92,
            "thickness": 0.86,
            "wetness": 0.41,
                "gloss": 0.36,
                "roughness": 0.48,
                "plow": 0.67,
                "resaturation": 0.58,
                "negative_depth": True,
        },
    ).to_dict()
    assert material_settings["ok"]
    assert material_settings["result"]["brush"]["material"]["settings"]["thickness"] == 0.86
    assert material_settings["result"]["brush"]["material"]["settings"]["plow"] == 0.67
    assert material_settings["result"]["brush"]["material"]["settings"]["resaturation"] == 0.58
    assert material_settings["result"]["brush"]["material"]["settings"]["negative_depth"] is True

    material_preview = registry.execute(
        "paint.material.preview.set",
        {"enabled": True, "azimuth_deg": 24.0, "elevation_deg": 56.0},
    ).to_dict()
    assert material_preview["ok"]
    assert material_preview["result"]["material_preview"]["enabled"] is True
    assert material_preview["result"]["material_preview"]["azimuth_deg"] == 24.0

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
            "dynamics": {
                "enabled": True,
                "mode": "smudge",
                "smudge_length": 73,
                "smudge_radius": 41,
                "color_rate": 19,
                "smudge_type": "smear",
                "overlay": True,
            },
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
    assert brush["result"]["brush"]["engine"]["dynamics"]["smudge_length"] == 73
    assert brush["result"]["brush"]["engine"]["dynamics"]["smudge_radius"] == 41
    assert brush["result"]["brush"]["engine"]["dynamics"]["color_rate"] == 19
    assert brush["result"]["brush"]["engine"]["dynamics"]["smudge_type"] == "smear"
    assert brush["result"]["brush"]["engine"]["dynamics"]["overlay"] is True
    assert brush["result"]["brush"]["library"]["name"] == "Tiger Studio Brushes"
    assert brush["result"]["brush"]["library"]["preset_count"] > 30

    maximum_brush = registry.execute(
        "paint.brush.set",
        {"width": PAINT_ACTION_MAX_BRUSH_WIDTH_PX},
    ).to_dict()
    assert maximum_brush["ok"]
    assert maximum_brush["result"]["brush"]["width_px"] == float(
        PAINT_ACTION_MAX_BRUSH_WIDTH_PX
    )

    invalid_fill = registry.execute(
        "paint.fill.solid",
        {"color": "not-a-color"},
    ).to_dict()
    assert invalid_fill["ok"] is False
    assert brush["result"]["brush"]["library"]["recent_indices"]
    assert dialog.canvas._brush_hardness == 72
    assert dialog.canvas._brush_spacing == 36
    assert dialog.canvas._brush_angle == -12
    assert dialog.canvas._brush_roundness == 64
    assert dialog.canvas._brush_flip_x is True

    favorite = registry.execute(
        "paint.brush.favorite.set",
        {"preset": "real_wet_oil", "favorite": True},
    ).to_dict()
    assert favorite["ok"]
    assert favorite["result"]["brush"]["library"]["favorite_count"] == 1

    library_view = registry.execute(
        "paint.brush.library.view",
        {
            "tab": "library",
            "category": "Water Media",
            "filters": ["masters", "watercolor"],
            "search": "watercolor",
            "compact": True,
        },
    ).to_dict()
    assert library_view["ok"]
    assert library_view["result"]["brush"]["library"]["filters"] == [
        "masters",
        "watercolor",
    ]
    assert library_view["result"]["brush"]["library"]["compact"] is True
    assert library_view["result"]["brush"]["library"]["search"] == "watercolor"
    assert dialog._brush_panel_stack.currentWidget() is dialog._brush_library_page
    assert dialog.brush_library_list.count() > 0

    ai_strokes = registry.execute(
        "paint.stroke.draw",
        {
            "undo_label": "Claude painterly sky",
            "strokes": [
                {
                    "points": [
                        {"x": 0.10, "y": 0.20},
                        {"x": 0.25, "y": 0.14},
                        {"x": 0.42, "y": 0.22},
                    ],
                    "color": "#2457A6",
                    "opacity": 86,
                    "width": 18,
                    "style": "loaded_oil",
                    "hardness": 72,
                    "spacing": 19,
                    "layer_id": layer_id,
                },
                {
                    "points": [
                        {
                            "x": 0.18,
                            "y": 0.30,
                            "pressure": 0.46,
                            "tilt_x": -0.4,
                            "tilt_y": 0.2,
                            "tangential_pressure": -0.25,
                            "load": 1.0,
                        },
                        {
                            "x": 0.31,
                            "y": 0.25,
                            "pressure": 0.91,
                            "tilt_x": 0.3,
                            "tilt_y": -0.1,
                            "tangential_pressure": 0.35,
                            "load": 0.72,
                        },
                    ],
                    "color": "#F0C541",
                    "width": 9,
                    "style": "impasto_oil",
                    "engine_version": 2,
                    "bristle_count": 11,
                    "seed": 83,
                    "load_depletion": 0.36,
                    "layer_id": material_layer_id,
                },
            ],
        },
    ).to_dict()
    assert ai_strokes["ok"]
    assert ai_strokes["result"]["stroke_draw"]["stroke_count"] == 2
    assert ai_strokes["result"]["stroke_draw"]["point_count"] == 5
    from app.painter_action_contract import PAINT_ACTION_REQUEST_RESOURCE_CONTRACT

    assert ai_strokes["result"]["stroke_draw"]["request_resource_contract"] == (
        PAINT_ACTION_REQUEST_RESOURCE_CONTRACT
    )
    assert PAINT_ACTION_REQUEST_RESOURCE_CONTRACT["document_stroke_capacity_claim"] is False
    assert ai_strokes["result"]["stroke_draw"]["engine_versions"] == [1, 2]
    assert ai_strokes["result"]["stroke_draw"]["dynamic_channels"] == [
        "pressure",
        "tilt",
        "tilt_x",
        "tilt_y",
        "rotation",
        "tangential_pressure",
        "load",
    ]
    assert ai_strokes["result"]["history"]["undo_labels"][-1] == "Claude painterly sky"
    assert len(dialog.canvas.embedded_strokes()) == 2
    material_stroke = dialog.canvas.embedded_strokes()[-1]
    assert material_stroke.material_enabled is True
    assert material_stroke.material_thickness == 0.86
    assert material_stroke.material_plow == 0.67
    assert material_stroke.material_resaturation == 0.58
    assert material_stroke.material_negative_depth is True
    assert material_stroke.point_pressure == [0.46, 0.91]
    assert material_stroke.point_tilt_x == [-0.4, 0.3]
    assert material_stroke.point_tilt_y == [0.2, -0.1]
    assert material_stroke.point_tangential_pressure == [-0.25, 0.35]

    undone = registry.execute("paint.history.undo").to_dict()
    assert undone["ok"]
    assert undone["result"]["history_action"]["changed"] is True
    assert len(dialog.canvas.embedded_strokes()) == 0

    redone = registry.execute("paint.history.redo").to_dict()
    assert redone["ok"]
    assert redone["result"]["history_action"]["changed"] is True
    assert len(dialog.canvas.embedded_strokes()) == 2

    ai_render_path = tmp_path / "claude_painter_strokes.png"
    rendered = registry.execute(
        "paint.document.export_png",
        {"path": str(ai_render_path), "include_background": False},
    ).to_dict()
    assert rendered["ok"]
    assert ai_render_path.exists()
    from PySide6.QtGui import QImage

    rendered_image = QImage(str(ai_render_path))
    assert not rendered_image.isNull()
    assert any(
        rendered_image.pixelColor(x, y).alpha() > 0
        for y in range(0, rendered_image.height(), max(1, rendered_image.height() // 24))
        for x in range(0, rendered_image.width(), max(1, rendered_image.width() // 24))
    )

    brush_panel = registry.execute("paint.window.show_panel", {"panel": "brush"}).to_dict()
    assert brush_panel["ok"]
    assert dialog._tool_status_label.text() == "Advanced brush controls"

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

    color_labeled = registry.execute(
        "paint.layer.set_color",
        {"layer_id": layer_id, "color_label": "blue"},
    ).to_dict()
    assert color_labeled["ok"]
    assert any(
        row["layer_id"] == layer_id and row["color_label"] == "blue"
        for row in color_labeled["result"]["layers"]
    )

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
    assert mask_from_path["ok"] is False

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
    combine_mode = registry.execute(
        "paint.selection.set_mode",
        {"mode": "add"},
    ).to_dict()
    assert combine_mode["ok"]
    assert combine_mode["result"]["selection"]["combine_mode"] == "add"
    color_selection = registry.execute(
        "paint.selection.select_by_color",
        {"x": 0.5, "y": 0.5, "tolerance": 12},
    ).to_dict()
    assert color_selection["ok"]
    assert color_selection["result"]["selection"]["active"] is True
    assert color_selection["result"]["tool"] == "magic_select"
    rectangle = registry.execute(
        "paint.selection.rectangle",
        {
            "x1": 0.1,
            "y1": 0.1,
            "x2": 0.4,
            "y2": 0.35,
            "aspect": "free",
            "mode": "new",
        },
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
    reveal_row = next(
        row for row in reveal_mask["result"]["layers"] if row["layer_id"] == layer_id
    )
    assert reveal_row["mask_point_count"] == 0
    assert reveal_row["mask_raster"] is True
    mask_gradient = registry.execute(
        "paint.layer.mask.gradient",
        {
            "layer_id": layer_id,
            "start": [0.0, 0.0],
            "end": [1.0, 0.0],
            "start_value": 0,
            "end_value": 255,
        },
    ).to_dict()
    assert mask_gradient["ok"]
    mask_paint = registry.execute(
        "paint.layer.mask.paint",
        {"layer_id": layer_id, "x": 0.25, "y": 0.5, "radius_px": 16, "value": 180},
    ).to_dict()
    assert mask_paint["ok"]
    applied_mask = registry.execute(
        "paint.layer.mask.apply",
        {"layer_id": layer_id},
    ).to_dict()
    assert applied_mask["ok"]
    assert next(
        row for row in applied_mask["result"]["layers"] if row["layer_id"] == layer_id
    )["mask_raster"] is False
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
    assert sampled_reference["result"]["sample"]["x_norm"] == 0.5
    assert sampled_reference["result"]["sample"]["y_norm"] == 0.5
    original_apply_pen_color = dialog._apply_pen_color
    dialog._painter_reference_selected_id = ""
    dialog._recent_colors = [(1, 2, 3)]
    pen_before_failure = dialog._pen_color.name()
    document_colors_before_failure = list(dialog._document_palette_colors)
    dirty_before_failure = dialog._painter_document_dirty

    def fail_reference_apply(color, *, remember):
        dialog._pen_color = color
        dialog._recent_colors = [(9, 9, 9)]
        dialog._document_palette_colors = [(8, 8, 8)]
        dialog._painter_document_dirty = not dirty_before_failure
        raise RuntimeError("injected reference apply failure")

    dialog._apply_pen_color = fail_reference_apply
    failed_sample_apply = registry.execute(
        "paint.reference.sample_color",
        {"reference_id": reference_id, "x_norm": 0.0, "y_norm": 1.0, "apply": True},
    ).to_dict()
    assert not failed_sample_apply["ok"]
    assert dialog._painter_reference_selected_id == ""
    assert dialog._recent_colors == [(1, 2, 3)]
    assert dialog._pen_color.name() == pen_before_failure
    assert dialog._document_palette_colors == document_colors_before_failure
    assert dialog._painter_document_dirty == dirty_before_failure
    failed_apply = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": reference_id, "max_colors": 4, "apply": True},
    ).to_dict()
    assert not failed_apply["ok"]
    assert dialog._painter_reference_selected_id == ""
    assert dialog._recent_colors == [(1, 2, 3)]
    assert dialog._pen_color.name() == pen_before_failure
    assert dialog._document_palette_colors == document_colors_before_failure
    assert dialog._painter_document_dirty == dirty_before_failure
    dialog._apply_pen_color = original_apply_pen_color
    dialog._painter_reference_selected_id = reference_id
    selected_before_missing = dialog._painter_reference_selected_id
    missing_reference = registry.execute(
        "paint.reference.sample_color",
        {"reference_id": "reference:missing", "x_norm": 0.5, "y_norm": 0.5},
    ).to_dict()
    assert not missing_reference["ok"]
    assert dialog._painter_reference_selected_id == selected_before_missing
    missing_palette_reference = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": "reference:missing", "max_colors": 4},
    ).to_dict()
    assert not missing_palette_reference["ok"]
    assert dialog._painter_reference_selected_id == selected_before_missing
    palette_reference = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": reference_id, "max_colors": 4},
    ).to_dict()
    assert palette_reference["ok"]
    assert palette_reference["result"]["palette"]["color_count"] >= 1

    transparent_path = tmp_path / "paint_reference_transparent.png"
    from PySide6.QtGui import QColor, QImage

    transparent_image = QImage(2, 2, QImage.Format.Format_ARGB32)
    transparent_image.fill(QColor(0, 0, 0, 0))
    assert transparent_image.save(str(transparent_path), "PNG")
    transparent_reference = registry.execute(
        "paint.reference.add",
        {"path": str(transparent_path), "name": "Transparent"},
    ).to_dict()
    assert transparent_reference["ok"]
    transparent_reference_id = transparent_reference["result"]["board"]["references"][-1]["id"]
    recent_before_empty_palette = list(dialog._recent_colors)
    empty_palette = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": transparent_reference_id, "max_colors": 4, "apply": True},
    ).to_dict()
    assert empty_palette["ok"]
    assert empty_palette["result"]["palette"]["color_count"] == 0
    assert empty_palette["result"]["applied_to_recent_colors"] is False
    assert dialog._recent_colors == recent_before_empty_palette

    missing_path_reference = registry.execute(
        "paint.reference.add",
        {"path": str(tmp_path / "does_not_exist.png"), "name": "Missing File"},
    ).to_dict()
    assert missing_path_reference["ok"]
    missing_path_reference_id = missing_path_reference["result"]["board"]["references"][-1]["id"]
    dialog._painter_reference_selected_id = reference_id
    foreground_before_load_failure = dialog._pen_color.name()
    recent_before_load_failure = list(dialog._recent_colors)
    failed_sample_load = registry.execute(
        "paint.reference.sample_color",
        {"reference_id": missing_path_reference_id, "x_norm": 0.0, "y_norm": 1.0},
    ).to_dict()
    failed_palette_load = registry.execute(
        "paint.reference.extract_palette",
        {"reference_id": missing_path_reference_id, "max_colors": 4},
    ).to_dict()
    assert not failed_sample_load["ok"]
    assert not failed_palette_load["ok"]
    assert dialog._painter_reference_selected_id == reference_id
    assert dialog._pen_color.name() == foreground_before_load_failure
    assert dialog._recent_colors == recent_before_load_failure
    assert registry.execute(
        "paint.reference.delete",
        {"reference_id": transparent_reference_id},
    ).to_dict()["ok"]
    assert registry.execute(
        "paint.reference.delete",
        {"reference_id": missing_path_reference_id},
    ).to_dict()["ok"]
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
    assert blockout["result"]["gizmo_contract"]["axis_convention"] == "z_up_x_red_y_green_z_blue"
    assert blockout["result"]["gizmo_contract"]["drop_placement"] == "screen_to_world_ground_plane"
    assert blockout["result"]["paint_over_contract"]["paint_strokes_above_reference"] is True
    primitive_id = blockout["result"]["scene"]["primitives"][0]["id"]
    blockout_before_rejection = dict(dialog._painter_3d_blockout_scene)
    for action_id, invalid_payload in (
        ("paint.3d_blockout.add", {"x": float("nan")}),
        ("paint.3d_blockout.update", {"primitive_id": primitive_id, "sx": 0.001}),
        ("paint.3d_blockout.update", {"primitive_id": primitive_id}),
        ("paint.3d_blockout.delete", {"primitive_id": ""}),
        ("paint.3d_blockout.duplicate", {"primitive_id": primitive_id, "offset_x": float("inf")}),
        ("paint.3d_blockout.snap", {}),
        ("paint.3d_blockout.material_preview", {"light_pitch_degrees": 90.0}),
        ("paint.3d_blockout.camera_preset", {"preset": "right"}),
    ):
        rejected = registry.execute(action_id, invalid_payload).to_dict()
        assert not rejected["ok"]
        assert dialog._painter_3d_blockout_scene == blockout_before_rejection
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
    assert grounded_blockout["result"]["scene"]["primitives"][0]["position"][2] == 0.0
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
    import json

    from app.painter_3d_blockout import BLOCKOUT_CAMERA_TARGET_MAX

    camera_before_rejection = dict(dialog._painter_3d_blockout_scene)
    rejected_extreme_camera = registry.execute(
        "paint.3d_blockout.camera",
        {"target_x": 1e308},
    ).to_dict()
    assert not rejected_extreme_camera["ok"]
    assert dialog._painter_3d_blockout_scene == camera_before_rejection
    endpoint_camera = registry.execute(
        "paint.3d_blockout.camera",
        {"target_x": BLOCKOUT_CAMERA_TARGET_MAX},
    ).to_dict()
    assert endpoint_camera["ok"]
    json.dumps(endpoint_camera["result"], allow_nan=False)
    material = registry.execute(
        "paint.3d_blockout.material_preview",
        {
            "material_lit": False,
            "show_floor": False,
            "show_shadows": False,
            "show_fog": True,
            "show_depth": True,
            "light_yaw_degrees": 70,
            "light_pitch_degrees": 30,
        },
    ).to_dict()
    assert material["ok"]
    assert material["result"]["scene"]["material_lit"] is False
    assert material["result"]["scene"]["show_floor"] is False
    assert material["result"]["scene"]["show_shadows"] is False
    assert material["result"]["scene"]["show_fog"] is True
    assert material["result"]["scene"]["show_depth"] is True
    assert material["result"]["scene"]["light_yaw_degrees"] == 70.0
    from app.painter_3d_blockout import (
        BLOCKOUT_LIGHT_PITCH_MAX_DEGREES,
        BLOCKOUT_LIGHT_YAW_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_POSITION_MAX,
        BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
        BLOCKOUT_PRIMITIVE_SCALE_MAX,
    )

    endpoint_primitive = registry.execute(
        "paint.3d_blockout.update",
        {
            "primitive_id": primitive_id,
            "x": BLOCKOUT_PRIMITIVE_POSITION_MAX,
            "rx": BLOCKOUT_PRIMITIVE_ROTATION_MIN_DEGREES,
            "sx": BLOCKOUT_PRIMITIVE_SCALE_MAX,
        },
    ).to_dict()
    assert endpoint_primitive["ok"]
    json.dumps(endpoint_primitive["result"], allow_nan=False)
    endpoint_light = registry.execute(
        "paint.3d_blockout.material_preview",
        {
            "light_yaw_degrees": BLOCKOUT_LIGHT_YAW_MIN_DEGREES,
            "light_pitch_degrees": BLOCKOUT_LIGHT_PITCH_MAX_DEGREES,
        },
    ).to_dict()
    assert endpoint_light["ok"]
    json.dumps(endpoint_light["result"], allow_nan=False)
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


def test_action_helpers_use_document_size_and_painter_time_without_full_hd_fabrication() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(321, 179, "transparent"),
        initial_strokes=[],
        time_ms=2468,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    assert registry.adapter._paint_canvas_size() == (321, 179)
    assert registry.adapter._paint_export_size_for_owner(None) == (321, 179)
    assert registry.adapter._paint_action_time_ms(None) == 2468
    dialog.close()
    dialog.deleteLater()
    app.processEvents()

    missing = ActionRegistry(owner=object())
    with pytest.raises(ValueError, match="canvas.*size|dimensions"):
        missing.adapter._paint_canvas_size()

    class BrokenPlayer:
        def position(self):
            raise RuntimeError("player position unavailable")

    class BrokenOwner:
        _player = BrokenPlayer()

    broken = ActionRegistry(owner=BrokenOwner())
    with pytest.raises(RuntimeError, match="position unavailable"):
        broken.adapter._paint_action_time_ms(None)

    class BrokenBackground:
        def width(self):
            raise RuntimeError("background dimensions unavailable")

        def height(self):
            return 10

    with pytest.raises(RuntimeError, match="dimensions unavailable"):
        registry.adapter._paint_export_size_for_owner(BrokenBackground())


def test_action_dialog_lookup_rejects_deleted_qobject_wrapper() -> None:
    app = _app()
    import shiboken6

    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 48, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )

    class Owner:
        _painter_windows = [dialog]

    registry = ActionRegistry(owner=Owner())
    shiboken6.delete(dialog)
    assert shiboken6.isValid(dialog) is False
    with pytest.raises(ValueError, match="no active Painter dialog"):
        registry.adapter._paint_dialog_owner()
    app.processEvents()


def test_action_and_clipboard_missing_pressure_use_explicit_unmodulated_constant() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(160, 90, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    result = registry.execute(
        "paint.stroke.draw",
        {
            "strokes": [
                {
                    "points": [
                        {"x": 0.1, "y": 0.2},
                        {"x": 0.5, "y": 0.7},
                        {"x": 0.9, "y": 0.8},
                    ],
                    "width": 8,
                    "style": "round",
                }
            ]
        },
    ).to_dict()
    assert result["ok"]
    first_stroke = dialog.canvas.embedded_strokes()[-1]
    assert set(first_stroke.point_pressure) == {1.0}
    import json

    from app.painter_action_contract import (
        PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX,
        PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION,
        PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS,
        PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS,
        PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
        PAINT_ACTION_STROKE_MIN_WIDTH_PX,
        PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT,
        PAINT_ACTION_STROKE_SEED_INDEX_FACTOR,
        PAINT_ACTION_STROKE_SEED_MAX,
        PAINT_ACTION_STROKE_SEED_POINT_FACTOR,
    )
    assert first_stroke.color == (238, 242, 247)
    assert first_stroke.opacity == 255
    assert first_stroke.brush_hardness == 100
    assert first_stroke.brush_spacing == 25
    assert first_stroke.brush_angle == 0
    assert first_stroke.brush_roundness == 100
    assert first_stroke.load_depletion == PAINT_ACTION_STROKE_DEFAULT_LOAD_DEPLETION
    assert first_stroke.brush_seed == (
        0 * PAINT_ACTION_STROKE_SEED_INDEX_FACTOR
        + len(first_stroke.points) * PAINT_ACTION_STROKE_SEED_POINT_FACTOR
    )
    for field, expected in PAINT_ACTION_STROKE_DEFAULT_POINT_CHANNELS.items():
        values = getattr(
            first_stroke,
            "point_load" if field == "load" else f"point_{field}",
        )
        assert set(values) == {expected}
    for field, expected in PAINT_ACTION_STROKE_DEFAULT_MATERIAL_CHANNELS.items():
        assert getattr(first_stroke, f"material_{field}") == expected

    endpoint = registry.execute(
        "paint.stroke.draw",
        {
            "strokes": [{
                "points": [
                    {"x": 0.0, "y": 1.0, "pressure": 0.0, "tilt_x": -1.0},
                    {"x": 1.0, "y": 0.0, "pressure": 1.0, "tilt_x": 1.0},
                ],
                "opacity": PAINT_ACTION_STROKE_OPACITY_MIN_PERCENT,
                "width": PAINT_ACTION_STROKE_MIN_WIDTH_PX,
                "hardness": 1,
                "spacing": 200,
                "angle": 180,
                "roundness": 10,
                "engine_version": PAINT_ACTION_STROKE_ENGINE_VERSION_MAX,
                "bristle_count": PAINT_ACTION_STROKE_BRISTLE_COUNT_MAX,
                "load_depletion": 0.0,
                "style": "bristle_oil",
                "closed": False,
                "seed": PAINT_ACTION_STROKE_SEED_MAX,
            }]
        },
    ).to_dict()
    assert endpoint["ok"]
    json.dumps(endpoint["result"], allow_nan=False)
    from PySide6.QtGui import QImage

    rendered = QImage(160, 90, QImage.Format.Format_ARGB32_Premultiplied)
    rendered.fill(0)
    dialog.canvas.render(rendered)
    stroke_count_before_rejection = len(dialog.canvas.embedded_strokes())
    undo_count_before_rejection = len(dialog._undo_stack)
    redo_count_before_rejection = len(dialog._redo_stack)

    nonfinite = registry.execute(
        "paint.stroke.draw",
        {
            "strokes": [{
                "points": [
                    {"x": 0.1, "y": 0.2, "pressure": float("nan")},
                    {"x": 0.9, "y": 0.8, "pressure": 1.0},
                ],
                "width": 8,
                "style": "round",
            }]
        },
    ).to_dict()
    assert nonfinite["ok"] is False
    out_of_domain = registry.execute(
        "paint.stroke.draw",
        {
            "strokes": [{
                "points": [
                    {"x": 0.1, "y": 0.2, "pressure": 1.01},
                    {"x": 0.9, "y": 0.8, "pressure": 1.0},
                ]
            }]
        },
    ).to_dict()
    assert out_of_domain["ok"] is False
    assert len(dialog.canvas.embedded_strokes()) == stroke_count_before_rejection
    unknown_layer = registry.execute(
        "paint.stroke.draw",
        {"strokes": [{"points": [{"x": 0.1, "y": 0.2}, {"x": 0.9, "y": 0.8}], "layer_id": "missing"}]},
    ).to_dict()
    assert unknown_layer["ok"] is False
    assert len(dialog.canvas.embedded_strokes()) == stroke_count_before_rejection
    assert len(dialog._undo_stack) == undo_count_before_rejection
    assert len(dialog._redo_stack) == redo_count_before_rejection

    restored = dialog._stroke_from_clipboard_dict(
        {
            "points": [[0.1, 0.2], [0.9, 0.8]],
            "point_pressure": [None, "invalid"],
        }
    )
    assert restored.point_pressure == [1.0, 1.0]
    with pytest.raises(ValueError, match="finite"):
        dialog._stroke_from_clipboard_dict(
            {
                "points": [[0.1, 0.2], [0.9, 0.8]],
                "point_pressure": [float("nan"), 1.0],
            }
        )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_brush_preset_keeps_selected_style_and_undo_uses_payload_budget() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(32, 32, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._pen_style = "graphite_pencil"
    dialog.canvas.set_pen_style("graphite_pencil")
    dialog._apply_brush_preset(12, 55)
    assert dialog._pen_style == "graphite_pencil"
    assert dialog.canvas._pen_style == "graphite_pencil"

    for index in range(60):
        dialog._push_history_command(
            {"kind": "test_small_command", "index": index},
            f"Test {index}",
        )
    assert len(dialog._undo_stack) == 60
    assert dialog.painter_action_state()["history"]["memory"]["within_budget"] is True
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_channel_actions_preserve_read_selection_and_measure_pixels() -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage, QPixmap
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog

    image = QImage(2, 1, QImage.Format.Format_ARGB32)
    image.setPixelColor(0, 0, QColor(10, 20, 30, 255))
    image.setPixelColor(1, 0, QColor(100, 150, 200, 255))
    dialog = PaintDialog(
        background_pixmap=QPixmap.fromImage(image),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    clipboard = QApplication.clipboard()
    previous_clipboard_image = clipboard.image()
    try:
        assert registry.execute("paint.channel.select", {"channel": "Green"}).ok

        copied = registry.execute(
            "paint.channel.copy_image", {"channel": "Blue"}
        ).to_dict()
        assert copied["ok"]
        assert dialog._selected_channel == "Green"
        copied_image = clipboard.image().convertToFormat(QImage.Format.Format_ARGB32)
        assert copied_image.pixelColor(0, 0).getRgb() == (30, 30, 30, 255)
        assert copied_image.pixelColor(1, 0).getRgb() == (200, 200, 200, 255)

        no_visibility_change = registry.execute(
            "paint.channel.set_visible", {"channel": "Blue", "visible": True}
        ).to_dict()
        assert not no_visibility_change["ok"]
        assert dialog._selected_channel == "Green"

        assert not registry.execute(
            "paint.quick_mask.set", {"enabled": False}
        ).ok
        assert registry.execute("paint.quick_mask.set", {"enabled": True}).ok
        assert not registry.execute("paint.quick_mask.set", {"enabled": True}).ok

        clipboard.clear()
        empty_paste = registry.execute(
            "paint.channel.paste_image", {"channel": "Red"}
        ).to_dict()
        assert not empty_paste["ok"]
        assert dialog._selected_channel == "Green"

        paste_source = QImage(2, 1, QImage.Format.Format_ARGB32)
        paste_source.setPixelColor(0, 0, QColor(60, 60, 60, 255))
        paste_source.setPixelColor(1, 0, QColor(180, 180, 180, 255))
        clipboard.setImage(paste_source)
        assert registry.execute(
            "paint.channel.paste_image", {"channel": "Red"}
        ).ok
        assert dialog._selected_channel == "Red"
        result = dialog._bg_pixmap_source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        assert result.pixelColor(0, 0).getRgb() == (60, 20, 30, 255)
        assert result.pixelColor(1, 0).getRgb() == (180, 150, 200, 255)
    finally:
        if previous_clipboard_image.isNull():
            clipboard.clear()
        else:
            clipboard.setImage(previous_clipboard_image)
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_selection_state_actions_report_noops_without_undo_or_fallback() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(16, 12, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    try:
        initial_undo = len(dialog._undo_stack)
        assert not registry.execute("paint.selection.deselect").ok
        assert not registry.execute("paint.selection.to_path").ok
        assert not registry.execute(
            "paint.selection.set_aspect", {"aspect": "free"}
        ).ok
        assert not registry.execute(
            "paint.selection.set_mode", {"mode": "new"}
        ).ok
        assert len(dialog._undo_stack) == initial_undo

        assert registry.execute("paint.selection.select_all").ok
        selected_undo = len(dialog._undo_stack)
        assert selected_undo == initial_undo + 1
        assert not registry.execute("paint.selection.select_all").ok
        assert len(dialog._undo_stack) == selected_undo

        assert registry.execute("paint.selection.to_path").ok
        assert registry.execute("paint.selection.deselect").ok
        deselected_undo = len(dialog._undo_stack)
        assert not registry.execute("paint.selection.deselect").ok
        assert len(dialog._undo_stack) == deselected_undo

        assert registry.execute(
            "paint.selection.set_aspect", {"aspect": "square"}
        ).ok
        assert registry.execute(
            "paint.selection.set_mode", {"mode": "add"}
        ).ok
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()


def test_crop_preview_is_atomic_and_does_not_clamp_authored_rotation() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(16, 12, "#204060"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    try:
        assert not registry.execute("paint.crop.preview").ok
        assert dialog._crop_preview_bounds is None

        assert registry.execute(
            "paint.crop.preview",
            {
                "x1": 0.25,
                "y1": 0.25,
                "x2": 0.75,
                "y2": 0.75,
                "straighten_degrees": 90.0,
            },
        ).ok
        assert dialog._crop_preview_bounds == (0.25, 0.25, 0.75, 0.75)
        assert dialog._crop_preview_straighten_degrees == 90.0
        assert not registry.execute(
            "paint.crop.preview",
            {
                "x1": 0.25,
                "y1": 0.25,
                "x2": 0.75,
                "y2": 0.75,
                "straighten_degrees": 90.0,
            },
        ).ok
        dialog._m3_drag_state = {
            "kind": "crop",
            "handle": "rotate",
            "start": (0.5, 0.25),
            "bounds": (0.25, 0.25, 0.75, 0.75),
            "straighten": 90.0,
        }
        assert dialog._handle_m3_canvas_interaction("move", 0.5, 0.9, None)
        assert dialog._crop_preview_straighten_degrees == 180.0
        assert registry.execute("paint.crop.cancel").ok
        assert not registry.execute("paint.crop.cancel").ok

        before_size = dialog._canvas_document_size
        partial = registry.execute("paint.crop.preview", {"x1": 0.25}).to_dict()
        assert not partial["ok"]
        assert dialog._crop_preview_bounds is None
        assert dialog._canvas_document_size == before_size

        assert registry.execute(
            "paint.crop.preview",
            {"x1": 0.25, "y1": 0.25, "x2": 0.75, "y2": 0.75},
        ).ok
        assert registry.execute("paint.crop.commit").ok
        assert dialog._canvas_document_size == (8, 6)
        assert not registry.execute("paint.crop.commit").ok
    finally:
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
