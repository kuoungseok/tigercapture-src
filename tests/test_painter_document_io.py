from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_native_painter_document_round_trips_2d_wet_and_3d_state(
    tmp_path: Path,
) -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap
    from app.painter_3d_blockout import (
        add_blockout_primitive,
        update_blockout_camera,
    )

    reference_path = tmp_path / "reference.png"
    assert create_blank_paint_pixmap(80, 60, "#3A7FB4").save(
        str(reference_path),
        "PNG",
    )
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#E8E1D2"),
        initial_strokes=[],
        time_ms=1250,
        standalone=True,
    )
    layer = dialog._new_material_paint_layer("Wet Impasto")
    layer.mask = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    layer.mask_enabled = True
    assert dialog._set_wet_canvas_settings(
        {
            "enabled": True,
            "mixing": 0.73,
            "diffusion": 0.31,
            "pickup": 0.52,
            "drying_seconds": 480,
            "elapsed_seconds": 90,
        },
        layer_id=layer.layer_id,
    )
    dialog._on_stroke_added(
        Stroke(
            points=[(0.15, 0.4), (0.82, 0.58)],
            color=(210, 72, 38),
            width_px=24,
            brush_style="impasto_oil",
            point_pressure=[0.42, 0.91],
            point_tilt_x=[-0.35, 0.4],
            point_tilt_y=[0.18, -0.22],
        )
    )
    dialog.canvas.set_selection_snapshot(
        [(0.2, 0.2), (0.7, 0.2), (0.7, 0.75), (0.2, 0.75)]
    )
    dialog.canvas.set_path_snapshot([(0.1, 0.8), (0.5, 0.3), (0.9, 0.78)])
    dialog._channel_visibility["Blue"] = False
    assert dialog._add_reference_image_path(
        str(reference_path),
        name="Lighting Reference",
    )
    scene = add_blockout_primitive(
        dialog._current_3d_blockout_scene(),
        kind="box",
        name="Room Mass",
        x=1.25,
        y=-0.5,
        z=0.0,
        sx=2.5,
        sy=1.5,
        sz=1.25,
    )
    scene = update_blockout_camera(
        scene,
        yaw_degrees=28,
        pitch_degrees=-17,
        distance=7.5,
        fov_degrees=41,
    )
    dialog._ensure_3d_blockout_layer()
    dialog._store_3d_blockout_scene(scene)
    dialog._painter_3d_blockout_selected_id = scene.primitives[0].id

    output = tmp_path / "production_study.tspaint"
    saved = dialog.save_document_to_path(output)
    assert output.exists()
    assert saved["blockout_primitive_count"] == 1
    assert saved["asset_count"] >= 2
    with zipfile.ZipFile(output, "r") as archive:
        assert "document.json" in archive.namelist()
        stored = json.loads(archive.read("document.json"))
        assert stored["schema"] == "tigerstudio.painter.document.v1"
        assert stored["blockout_3d"]["primitives"][0]["name"] == "Room Mass"
        assert stored["reference_board"]["references"][0]["path"].startswith(
            "asset://"
        )

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    loaded = restored.open_document_from_path(output)
    assert loaded["layer_count"] == len(dialog._paint_layers)
    assert loaded["stroke_count"] == 1
    assert loaded["blockout_primitive_count"] == 1
    assert restored._canvas_document_size == (640, 360)
    assert restored._background_layer_present is True
    restored_layer = restored._paint_layer_by_id(layer.layer_id)
    assert restored_layer is not None
    assert restored_layer.mask_enabled is True
    assert restored_layer.wet_canvas_settings["enabled"] is True
    assert restored_layer.wet_canvas_settings["mixing"] == 0.73
    restored_stroke = restored.canvas.embedded_strokes()[0]
    assert restored_stroke.point_pressure == [0.42, 0.91]
    assert restored_stroke.point_tilt_x == [-0.35, 0.4]
    assert restored.canvas.path_snapshot() == [
        (0.1, 0.8),
        (0.5, 0.3),
        (0.9, 0.78),
    ]
    assert restored._channel_visibility["Blue"] is False
    restored_scene = restored._current_3d_blockout_scene()
    assert len(restored_scene.primitives) == 1
    assert restored_scene.primitives[0].name == "Room Mass"
    assert restored_scene.camera.fov_degrees == 41.0
    restored_reference = restored._current_reference_board().references[0]
    assert restored_reference.name == "Lighting Reference"
    assert Path(restored_reference.path).exists()
    assert Path(restored_reference.path) != reference_path
    assert restored._painter_document_dirty is False

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()


def test_painter_document_actions_save_and_open_native_format(tmp_path: Path) -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {"paint.document.save", "paint.document.open"} <= action_ids
    path = tmp_path / "action_document.tspaint"
    saved = registry.execute(
        "paint.document.save",
        {"path": str(path)},
    ).to_dict()
    assert saved["ok"]
    assert path.exists()
    opened = registry.execute(
        "paint.document.open",
        {"path": str(path)},
    ).to_dict()
    assert opened["ok"]
    state = registry.execute("paint.state").to_dict()["result"]
    assert state["document"]["native_extension"] == ".tspaint"
    assert state["document"]["persists_3d_blockout"] is True

    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_native_document_embeds_painter_ui_image_sources(
    tmp_path: Path,
) -> None:
    app = _app()
    from PySide6.QtGui import QColor, QImage

    from app.drawing import PaintDialog, create_blank_paint_pixmap
    from app.painter_ui_image_assets import place_ui_image

    image_path = tmp_path / "ui-card.png"
    image = QImage(64, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor("#E05A47"))
    assert image.save(str(image_path), "PNG")

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    document, row, _report = place_ui_image(
        dialog._painter_ui_document,
        image_path,
    )
    dialog._painter_ui_document = document
    output = tmp_path / "ui-image.tspaint"
    saved = dialog.save_document_to_path(output)
    assert saved["asset_count"] >= 2

    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(output)
    restored_row = next(
        item
        for item in restored._painter_ui_document["objects"]
        if item["id"] == row["id"]
    )
    restored_path = Path(restored_row["content"]["source_path"])
    assert restored_path.is_file()
    assert restored_path != image_path
    assert QImage(str(restored_path)).size() == image.size()

    dialog.close()
    restored.close()
    dialog.deleteLater()
    restored.deleteLater()
    app.processEvents()
