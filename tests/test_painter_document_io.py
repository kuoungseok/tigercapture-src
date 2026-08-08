from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest


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
    assert dialog._fill_document("solid", color1="#4287F5")
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
    assert dialog._set_material_settings(
        {
            "plow": 0.63,
            "resaturation": 0.57,
            "negative_depth": True,
        },
        layer_id=layer.layer_id,
    )
    dialog._set_material_preview(
        enabled=True,
        azimuth_deg=0.0,
        elevation_deg=85.0,
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
            brush_dynamics={
                "enabled": True,
                "mode": "smudge",
                "smudge_type": "dulling",
                "overlay": True,
                "sampled_rgba": [[36, 104, 216, 255], [40, 108, 212, 255]],
            },
        )
    )
    dialog.canvas.set_selection_snapshot(
        [(0.2, 0.2), (0.7, 0.2), (0.7, 0.75), (0.2, 0.75)]
    )
    dialog._sync_pixel_selection_from_canvas()
    dialog.canvas.set_path_snapshot([(0.1, 0.8), (0.5, 0.3), (0.9, 0.78)])
    dialog._channel_visibility["Blue"] = False
    dialog._set_perspective_guide_options(
        enabled=True,
        snap=True,
        mode=3,
        left_x=-2.0,
        right_x=3.0,
        vertical_y=-1.5,
    )
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
    assert saved["asset_count"] >= 3
    assert saved["security_policy"]["format_limit_claim"] is False
    assert saved["security_policy"]["universal_safe_capacity_claim"] is False
    with zipfile.ZipFile(output, "r") as archive:
        assert "document.json" in archive.namelist()
        stored = json.loads(archive.read("document.json"))
        assert stored["schema"] == "tigerstudio.painter.document.v5"
        assert stored["format_version"] == 5
        assert stored["blockout_3d"]["primitives"][0]["name"] == "Room Mass"
        assert stored["reference_board"]["references"][0]["path"].startswith(
            "asset://"
        )
        stored_layer = next(
            row for row in stored["layers"] if row["layer_id"] == layer.layer_id
        )
        assert stored_layer["raster_asset"].startswith("asset://assets/layers/")
        assert stored_layer["mask_asset"].startswith("asset://assets/layer-masks/")
        assert stored_layer["mask"] == []
        assert stored["selection"]["mask_asset"] == "asset://assets/selection/mask.png"
        assert stored["material_preview"] == {
            "enabled": True,
            "azimuth_deg": 0.0,
            "elevation_deg": 85.0,
        }
        assert "assets/selection/mask.png" in archive.namelist()

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
    assert restored._material_preview_enabled is True
    assert restored._material_preview_light_azimuth_deg == 0.0
    assert restored._material_preview_light_elevation_deg == 85.0
    restored_layer = restored._paint_layer_by_id(layer.layer_id)
    assert restored_layer is not None
    assert restored_layer.mask_enabled is True
    restored_mask = restored._paint_layer_mask(layer.layer_id)
    assert restored_mask is not None
    assert restored_mask.pixelColor(320, 180).alpha() == 255
    assert restored_mask.pixelColor(10, 10).alpha() == 0
    assert restored_layer.wet_canvas_settings["enabled"] is True
    assert restored_layer.wet_canvas_settings["mixing"] == 0.73
    restored_raster = restored._paint_layer_raster(layer.layer_id)
    assert restored_raster is not None
    assert restored_raster.pixelColor(320, 180).name() == "#4287f5"
    restored_stroke = restored.canvas.embedded_strokes()[0]
    assert restored_stroke.point_pressure == [0.42, 0.91]
    assert restored_stroke.point_tilt_x == [-0.35, 0.4]
    assert restored_stroke.material_plow == 0.63
    assert restored_stroke.material_resaturation == 0.57
    assert restored_stroke.material_negative_depth is True
    assert restored_stroke.brush_dynamics["overlay"] is True
    assert restored_stroke.brush_dynamics["sampled_rgba"][0] == [36, 104, 216, 255]
    assert restored.canvas.path_snapshot() == [
        (0.1, 0.8),
        (0.5, 0.3),
        (0.9, 0.78),
    ]
    assert restored._selection_pixel_mask is not None
    assert restored._selection_pixel_mask.pixelColor(320, 180).alpha() > 0
    assert restored._channel_visibility["Blue"] is False
    restored_perspective = restored.canvas.perspective_guide_state()
    assert restored_perspective["enabled"] is True
    assert restored_perspective["snap"] is True
    assert restored_perspective["mode"] == 3
    assert restored_perspective["left_vp"][0] == -2.0
    assert restored_perspective["vertical_vp"][1] == -1.5
    restored_scene = restored._current_3d_blockout_scene()
    assert len(restored_scene.primitives) == 1
    assert restored_scene.primitives[0].name == "Room Mass"
    assert restored_scene.camera.fov_degrees == 41.0
    restored_reference = restored._current_reference_board().references[0]
    assert restored_reference.name == "Lighting Reference"
    assert Path(restored_reference.path).exists()
    assert Path(restored_reference.path) != reference_path
    assert restored._painter_document_dirty is False
    resaved = restored.save_document_to_path(tmp_path / "production_study_resaved.tspaint")
    assert resaved["asset_count"] == saved["asset_count"]

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


def test_stroke_only_v1_document_migrates_losslessly_to_v4(tmp_path: Path) -> None:
    from app.painter_document_io import load_painter_document

    legacy = {
        "schema": "tigerstudio.painter.document.v1",
        "format_version": 1,
        "layers": [{"layer_id": "paint-layer-1", "name": "Legacy Ink"}],
        "strokes": [
            {
                "points": [[0.1, 0.2], [0.8, 0.7]],
                "layer_id": "paint-layer-1",
                "color": [12, 34, 56],
            }
        ],
        "asset_manifest": [],
    }
    path = tmp_path / "legacy_v1.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(legacy).encode("utf-8"))

    document, report = load_painter_document(path, asset_root=tmp_path / "assets")
    assert document["schema"] == "tigerstudio.painter.document.v5"
    assert document["format_version"] == 5
    assert document["layers"][0]["raster_asset"] == ""
    assert document["layers"][0]["mask_asset"] == ""
    assert document["strokes"] == legacy["strokes"]
    assert report["migrated"] is True
    assert report["source_format_version"] == 1

    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    with pytest.raises(ValueError, match="canvas dimensions"):
        dialog.open_document_from_path(path)
    assert dialog._canvas_document_size == (64, 64)
    dialog.close()


def test_v3_document_migrates_to_v5_with_empty_saved_selection_channels(
    tmp_path: Path,
) -> None:
    from app.painter_document_io import load_painter_document

    payload = {
        "schema": "tigerstudio.painter.document.v3",
        "format_version": 3,
        "document": {"width": 23, "height": 17},
        "channels": {"visibility": {"Blue": False}, "selected": "Blue"},
        "layers": [],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "legacy-v3.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))

    document, report = load_painter_document(path, asset_root=tmp_path / "v3-assets")
    assert document["schema"] == "tigerstudio.painter.document.v5"
    assert document["format_version"] == 5
    assert document["channels"]["saved_selection_channels"] == []
    assert document["channels"]["saved_selection_channel_serial"] == 0
    assert document["channels"]["visibility"]["Blue"] is False
    assert report["migrated"] is True
    assert report["source_format_version"] == 3


def test_v4_document_missing_canvas_dimensions_is_rejected_not_changed_to_full_hd(
    tmp_path: Path,
) -> None:
    from app.painter_document_io import PainterDocumentError, load_painter_document

    payload = {
        "schema": "tigerstudio.painter.document.v4",
        "format_version": 4,
        "document": {},
        "layers": [],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "missing-size.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
    with pytest.raises(PainterDocumentError, match="canvas dimensions"):
        load_painter_document(path, asset_root=tmp_path / "assets")


@pytest.mark.parametrize("width,height", [(19.9, 13), (True, 13), (19, 13.5)])
def test_v4_document_rejects_non_integer_canvas_dimensions(
    tmp_path: Path,
    width,
    height,
) -> None:
    from app.painter_document_io import PainterDocumentError, load_painter_document

    payload = {
        "schema": "tigerstudio.painter.document.v4",
        "format_version": 4,
        "document": {"width": width, "height": height},
        "layers": [],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / f"invalid-size-{width}-{height}.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
    with pytest.raises(PainterDocumentError, match="canvas dimensions"):
        load_painter_document(path, asset_root=tmp_path / "assets")


def test_legacy_missing_dimensions_are_recovered_from_embedded_background_asset(
    tmp_path: Path,
) -> None:
    import hashlib

    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    background_path = tmp_path / "background.png"
    assert create_blank_paint_pixmap(37, 23, "#304860").save(str(background_path), "PNG")
    background_bytes = background_path.read_bytes()
    entry = "assets/background.png"
    payload = {
        "schema": "tigerstudio.painter.document.v2",
        "format_version": 2,
        "document": {},
        "background": {"present": True, "asset": f"asset://{entry}"},
        "layers": [{"layer_id": "paint-layer-1", "name": "Layer 1"}],
        "strokes": [],
        "asset_manifest": [
            {
                "entry": entry,
                "size": len(background_bytes),
                "sha256": hashlib.sha256(background_bytes).hexdigest(),
            }
        ],
    }
    path = tmp_path / "legacy-background-size.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(payload).encode("utf-8"))
        archive.writestr(entry, background_bytes)

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    report = dialog.open_document_from_path(path)
    assert report["migrated"] is True
    assert dialog._canvas_document_size == (37, 23)
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_v2_polygon_mask_opens_as_v3_alpha8_raster(tmp_path: Path) -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    legacy = {
        "schema": "tigerstudio.painter.document.v2",
        "format_version": 2,
        "document": {"width": 40, "height": 20, "active_layer_id": "paint-layer-1"},
        "background": {"present": False, "color": "#FFFFFF"},
        "layers": [
            {
                "layer_id": "paint-layer-1",
                "name": "Legacy Mask",
                "mask": [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]],
                "mask_enabled": True,
            }
        ],
        "strokes": [],
        "asset_manifest": [],
    }
    path = tmp_path / "legacy-v2-mask.tspaint"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(legacy).encode("utf-8"))

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog._painter_recovery_timer.stop()
    report = dialog.open_document_from_path(path)
    assert report["source_format_version"] == 2
    assert report["migrated"] is True
    layer = dialog._paint_layer_by_id("paint-layer-1")
    assert layer is not None and layer.mask == [] and layer.mask_enabled is True
    mask = dialog._paint_layer_mask(layer.layer_id)
    assert mask is not None
    assert mask.pixelColor(5, 10).alpha() == 255
    assert mask.pixelColor(35, 10).alpha() == 0
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


def test_archive_entries_reject_posix_windows_drive_and_ads_escape_paths() -> None:
    from app.painter_document_io import PainterDocumentError, _safe_archive_entry

    unsafe = (
        "../escape.bin",
        "..\\escape.bin",
        "assets\\..\\..\\escape.bin",
        "C:\\absolute.bin",
        "\\\\server\\share\\escape.bin",
        "/absolute.bin",
        "assets/payload.bin:stream",
        "",
    )
    for entry in unsafe:
        with pytest.raises(PainterDocumentError):
            _safe_archive_entry(entry)

    assert _safe_archive_entry("assets\\layers\\paint.png") == "assets/layers/paint.png"


@pytest.mark.parametrize(
    "mutation,error_fragment",
    (
        ("manifest_not_list", "asset_manifest must be a list"),
        ("row_not_object", "manifest rows must be objects"),
        ("missing_size", "asset size is invalid"),
        ("size_mismatch", "asset size mismatch"),
        ("missing_sha", "SHA-256 is invalid"),
        ("entry_not_string", "manifest entry must be a string"),
        ("serial_is_bool", "channel serial is invalid"),
        ("duplicate_manifest", "manifest entry is duplicated"),
        ("duplicate_archive", "archive asset entry is duplicated"),
    ),
)
def test_v5_asset_manifest_is_strict_and_fails_before_extraction(
    tmp_path: Path,
    mutation: str,
    error_fragment: str,
) -> None:
    import hashlib

    from app.painter_document_io import PainterDocumentError, load_painter_document

    data = b"asset-pixels"
    entry = "assets/layers/000_asset.png"
    row = {
        "entry": entry,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    document = {
        "schema": "tigerstudio.painter.document.v5",
        "format_version": 5,
        "document": {"width": 8, "height": 6},
        "channels": {
            "saved_selection_channels": [],
            "saved_selection_channel_serial": 0,
        },
        "asset_manifest": [row],
    }
    if mutation == "manifest_not_list":
        document["asset_manifest"] = {}
    elif mutation == "row_not_object":
        document["asset_manifest"] = [entry]
    elif mutation == "missing_size":
        row.pop("size")
    elif mutation == "size_mismatch":
        row["size"] += 1
    elif mutation == "missing_sha":
        row.pop("sha256")
    elif mutation == "entry_not_string":
        row["entry"] = 7
    elif mutation == "serial_is_bool":
        document["channels"]["saved_selection_channel_serial"] = True
    elif mutation == "duplicate_manifest":
        document["asset_manifest"] = [row, dict(row)]

    archive_path = tmp_path / f"{mutation}.tspaint"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(document))
        archive.writestr(entry, data)
        if mutation == "duplicate_archive":
            archive.writestr(entry, data)

    extraction_root = tmp_path / f"extract-{mutation}"
    with pytest.raises(PainterDocumentError, match=error_fragment):
        load_painter_document(archive_path, asset_root=extraction_root)
    assert not extraction_root.exists()


def test_duplicate_document_json_is_rejected_as_ambiguous(tmp_path: Path) -> None:
    from app.painter_document_io import PainterDocumentError, load_painter_document

    document = {
        "schema": "tigerstudio.painter.document.v5",
        "format_version": 5,
        "document": {"width": 8, "height": 6},
        "channels": {
            "saved_selection_channels": [],
            "saved_selection_channel_serial": 0,
        },
        "asset_manifest": [],
    }
    archive_path = tmp_path / "duplicate-document.tspaint"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(document))
        archive.writestr("document.json", json.dumps(document))

    with pytest.raises(PainterDocumentError, match="exactly one document.json"):
        load_painter_document(archive_path, asset_root=tmp_path / "extract")


@pytest.mark.parametrize("format_version", (True, 5.0, "5", None))
def test_document_version_must_be_a_non_boolean_integer(
    tmp_path: Path,
    format_version: object,
) -> None:
    from app.painter_document_io import PainterDocumentError, load_painter_document

    document = {
        "schema": "tigerstudio.painter.document.v5",
        "format_version": format_version,
        "document": {"width": 8, "height": 6},
        "channels": {
            "saved_selection_channels": [],
            "saved_selection_channel_serial": 0,
        },
        "asset_manifest": [],
    }
    archive_path = tmp_path / "invalid-version.tspaint"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("document.json", json.dumps(document))

    with pytest.raises(PainterDocumentError, match="format_version is invalid"):
        load_painter_document(archive_path)


def test_invalid_zip_uses_painter_document_error_boundary(tmp_path: Path) -> None:
    from app.painter_document_io import PainterDocumentError, load_painter_document

    archive_path = tmp_path / "not-a-zip.tspaint"
    archive_path.write_bytes(b"not a zip archive")

    with pytest.raises(PainterDocumentError, match="archive could not be read"):
        load_painter_document(archive_path)


def test_auto_asset_root_is_removed_when_extraction_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.painter_document_io as document_io

    archive_path = tmp_path / "write-failure.tspaint"
    document_io.save_painter_document(
        archive_path,
        {
            "document": {"width": 8, "height": 6},
            "channels": {
                "saved_selection_channels": [],
                "saved_selection_channel_serial": 0,
            },
            "layers": [{"layer_id": "paint-1"}],
        },
        layer_raster_pngs={"paint-1": b"asset-pixels"},
    )
    extraction_root = tmp_path / "controlled-auto-root"
    monkeypatch.setattr(document_io.tempfile, "mkdtemp", lambda **_kwargs: str(extraction_root))
    original_write_bytes = Path.write_bytes

    def fail_asset_write(path: Path, data: bytes) -> int:
        if extraction_root in path.parents:
            raise OSError("measured extraction failure")
        return original_write_bytes(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_asset_write)

    with pytest.raises(document_io.PainterDocumentError, match="archive could not be read"):
        document_io.load_painter_document(archive_path)
    assert not extraction_root.exists()


def test_archive_entry_inventory_is_built_once_for_multiple_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.painter_document_io as document_io

    archive_path = tmp_path / "multiple-assets.tspaint"
    document_io.save_painter_document(
        archive_path,
        {
            "document": {"width": 8, "height": 6},
            "channels": {
                "saved_selection_channels": [],
                "saved_selection_channel_serial": 0,
            },
            "layers": [
                {"layer_id": "paint-1"},
                {"layer_id": "paint-2"},
                {"layer_id": "paint-3"},
            ],
        },
        layer_raster_pngs={
            "paint-1": b"asset-one",
            "paint-2": b"asset-two",
            "paint-3": b"asset-three",
        },
    )
    calls = 0
    original_infolist = zipfile.ZipFile.infolist

    def counted_infolist(archive: zipfile.ZipFile):
        nonlocal calls
        calls += 1
        return original_infolist(archive)

    monkeypatch.setattr(zipfile.ZipFile, "infolist", counted_infolist)

    loaded, report = document_io.load_painter_document(
        archive_path,
        asset_root=tmp_path / "extracted",
    )
    assert len(loaded["layers"]) == 3
    assert report["asset_count"] == 3
    assert calls == 1
