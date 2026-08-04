from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _image(width: int = 48, height: int = 32):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(42, 88, 132, 255))
    painter = QPainter(image)
    painter.fillRect(QRect(width // 2, 0, width // 2, height), QColor(214, 154, 76, 255))
    painter.fillRect(QRect(8, 8, 12, 12), QColor(92, 206, 116, 255))
    painter.end()
    return image


def _bytes(image) -> bytes:
    return bytes(image.constBits())


def test_all_adjustments_change_pixels_and_selection_mask_preserves_outside() -> None:
    from app.painter_adjustments import apply_adjustment_qimage
    from app.painter_selection_mask import polygon_selection_mask

    source = _image()
    variants = {
        "levels": {"black": 35, "white": 220, "gamma": 0.75},
        "curves": {"points": [[0, 0], [90, 40], [180, 225], [255, 255]]},
        "brightness_contrast": {"brightness": 24, "contrast": 38},
        "hue_saturation": {"hue": 35, "saturation": 42, "lightness": -8},
        "color_balance": {"shadows": [24, -12, -20], "midtones": [-8, 18, 10], "highlights": [12, 0, -16]},
        "blur": {"radius": 2.5},
        "sharpen": {"radius": 1.2, "amount": 190, "threshold": 1},
    }
    rendered = {
        kind: apply_adjustment_qimage(source, kind, settings)
        for kind, settings in variants.items()
    }
    assert all(_bytes(image) != _bytes(source) for image in rendered.values())
    assert len({_bytes(image) for image in rendered.values()}) == len(rendered)
    mask = polygon_selection_mask(48, 32, [(0, 0), (0.5, 0), (0.5, 1), (0, 1)])
    selected = apply_adjustment_qimage(source, "brightness_contrast", {"brightness": 60}, mask=mask)
    assert selected.pixelColor(8, 4) != source.pixelColor(8, 4)
    assert selected.pixelColor(40, 4) == source.pixelColor(40, 4)


def test_hue_adjustment_uses_documented_degree_domain_and_reports_units() -> None:
    from app.painter_adjustments import adjustment_parameter_contracts, apply_adjustment_qimage, normalize_adjustment
    from PySide6.QtGui import QColor, QImage

    _kind, settings = normalize_adjustment("hue_saturation", {"hue": 999, "saturation": 999, "lightness": -999})
    assert settings == {"hue": 180, "saturation": 100, "lightness": -100}
    source = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
    source.fill(QColor(255, 0, 0, 255))
    opposite = apply_adjustment_qimage(source, "hue_saturation", {"hue": 180})
    color = opposite.pixelColor(0, 0)
    assert color.red() <= 2 and color.green() >= 252 and color.blue() >= 252
    contract = adjustment_parameter_contracts()["hue_saturation"]
    assert contract["hue"] == [-180, 180, "degrees"]
    assert contract["photoshop_algorithm_parity_claim"] is False


def test_adjustment_preview_cancel_commit_and_one_step_undo() -> None:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(48, 32, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    layer_id = dialog._active_paint_layer_id
    dialog._set_paint_layer_raster(layer_id, _image())
    original = dialog._paint_layer_raster(layer_id).copy()
    dialog.canvas.select_rectangle(0, 0, 0.5, 1)
    dialog._sync_pixel_selection_from_canvas()
    assert dialog._preview_paint_adjustment("levels", {"gamma": 0.55})
    preview = dialog._paint_layer_raster(layer_id).copy()
    assert _bytes(preview) != _bytes(original)
    assert dialog._cancel_paint_adjustment()
    assert _bytes(dialog._paint_layer_raster(layer_id)) == _bytes(original)
    assert dialog._preview_paint_adjustment("levels", {"gamma": 0.55})
    assert dialog._commit_paint_adjustment()
    assert _bytes(dialog._paint_layer_raster(layer_id)) == _bytes(preview)
    dialog._undo()
    assert _bytes(dialog._paint_layer_raster(layer_id)) == _bytes(original)
    dialog.close(); app.processEvents()


def test_adjustment_layer_is_non_destructive_and_save_open_export_parity(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication
    from app.drawing import PaintDialog, compose_pil_paint_overlays, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(48, 32, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    base_id = dialog._active_paint_layer_id
    source = _image(); dialog._set_paint_layer_raster(base_id, source)
    before_source = _bytes(dialog._paint_layer_raster(base_id))
    layer = dialog._new_adjustment_layer("hue_saturation", {"hue": 40, "saturation": 30})
    rendered = compose_pil_paint_overlays(
        paint_layers=dialog._paint_layers,
        layer_rasters=dialog._paint_layer_rasters,
        frame_size=(48, 32),
    )
    assert rendered.tobytes() != bytes(source.constBits())
    assert _bytes(dialog._paint_layer_raster(base_id)) == before_source
    document = tmp_path / "adjustment.tspaint"
    dialog.save_document_to_path(document)
    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    reopened.open_document_from_path(document)
    restored_layer = reopened._paint_layer_by_id(layer.layer_id)
    assert restored_layer.node_type == "adjustment"
    assert restored_layer.adjustment_type == "hue_saturation"
    reopened_render = compose_pil_paint_overlays(
        paint_layers=reopened._paint_layers,
        layer_rasters=reopened._paint_layer_rasters,
        frame_size=(48, 32),
    )
    assert reopened_render.tobytes() == rendered.tobytes()
    reopened.close(); dialog.close(); app.processEvents()


def test_named_gpl_and_ase_palette_groups_roundtrip(tmp_path: Path) -> None:
    from app.painter_adjustments import export_ase, export_gpl, import_ase, import_gpl

    groups = {
        "Skin": [{"name": "Warm", "rgb": [224, 152, 120]}, {"name": "Shadow", "rgb": [98, 58, 64]}],
        "Sky": [{"name": "Blue", "rgb": [54, 126, 220]}],
    }
    gpl = tmp_path / "named.gpl"; ase = tmp_path / "named.ase"
    export_gpl(gpl, groups); export_ase(ase, groups)
    assert import_gpl(gpl) == groups
    assert import_ase(ase) == groups


def test_malformed_or_empty_palette_files_are_rejected(tmp_path: Path) -> None:
    from app.painter_adjustments import import_ase, import_gpl

    malformed_gpl = tmp_path / "malformed.gpl"
    malformed_gpl.write_text("GIMP Palette\nnot a color\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid GPL color row"):
        import_gpl(malformed_gpl)

    empty_gpl = tmp_path / "empty.gpl"
    empty_gpl.write_text("GIMP Palette\nName: Empty\n", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no colors"):
        import_gpl(empty_gpl)

    empty_ase = tmp_path / "empty.ase"
    empty_ase.write_bytes(b"ASEF\x00\x01\x00\x00\x00\x00\x00\x00")
    with pytest.raises(ValueError, match="contains no RGB colors"):
        import_ase(empty_ase)


def test_numeric_rgb_hsb_gamut_shortcuts_and_action_surface() -> None:
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(48, 32, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    report = dialog._set_painter_numeric_color("rgb", [300, -20, 128])
    assert not report["in_gamut"] and report["rgb"] == [255, 0, 128]
    invalid_hsb = dialog._set_painter_numeric_color("hsb", [720, 150, -20])
    assert invalid_hsb["in_gamut"] is False
    assert invalid_hsb["source_range_valid"] is False
    assert invalid_hsb["source_values"] == [720.0, 150.0, -20.0]
    hsb = dialog._set_painter_numeric_color("hsb", [180, 100, 50], target="background")
    assert hsb["rgb"] == [0, 128, 128]
    dialog._reset_painter_foreground_background()
    assert dialog._pen_color.name() == "#000000" and dialog._background_color.name() == "#ffffff"
    dialog._swap_painter_foreground_background()
    assert dialog._pen_color.name() == "#ffffff" and dialog._background_color.name() == "#000000"
    registry = ActionRegistry(owner=dialog)
    ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.color.numeric.set", "paint.adjustment.preview", "paint.adjustment.apply",
        "paint.adjustment.commit", "paint.adjustment.cancel",
        "paint.adjustment.layer.create", "paint.adjustment.layer.update",
        "paint.palette.file.import", "paint.palette.file.export",
    } <= ids
    state = dialog.painter_action_state()
    assert state["palette"]["display_profile"] == "sRGB"
    assert state["palette"]["output_profile"] == "sRGB"
    assert state["palette"]["output_profile_boundary"] == "document-srgb-to-export-profile"
    assert state["palette"]["harmony_model"] == "tiger_authored_oklch_suggestions_v1"
    assert state["palette"]["harmony_chroma_floor"] == 0.0
    assert state["palette"]["css_gamut_mapping_claim"] is False
    assert state["palette"]["harmony_quality_claim"] is False
    assert state["adjustment_preview"]["parameter_contracts"]["hue_saturation"]["hue"] == [-180, 180, "degrees"]
    dialog.close(); app.processEvents()
