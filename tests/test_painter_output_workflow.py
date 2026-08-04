from __future__ import annotations

import os
from pathlib import Path

import pytest


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_print_pixel_math_and_preflight_are_explicit() -> None:
    from app.painter_output import output_preflight, pixels_for_print

    assert pixels_for_print(210, 297, ppi=300, bleed_mm=0) == (2480, 3508)
    assert pixels_for_print(210, 297, ppi=300, bleed_mm=3) == (2551, 3579)

    report = output_preflight(
        {
            "mode": "print",
            "width_mm": 210,
            "height_mm": 297,
            "ppi": 300,
            "bleed_mm": 3,
            "output_kind": "color",
        },
        pixel_width=2551,
        pixel_height=3579,
    )
    assert report["ok"]
    assert report["effective_ppi"] == pytest.approx(300, abs=0.2)
    assert report["target_ppi"] == 300
    assert any("profile" in warning.casefold() for warning in report["warnings"])

    trim_only = output_preflight(
        {
            "mode": "print",
            "width_mm": 210,
            "height_mm": 297,
            "ppi": 300,
            "bleed_mm": 3,
            "include_bleed": False,
            "output_kind": "color",
        },
        pixel_width=2480,
        pixel_height=3508,
    )
    assert trim_only["effective_ppi"] == pytest.approx(300, abs=0.2)
    assert trim_only["summary"].endswith("0 mm bleed")
    assert any("No bleed" in warning for warning in trim_only["warnings"])

    low_resolution = output_preflight(
        {
            "mode": "print",
            "width_mm": 210,
            "height_mm": 297,
            "ppi": 300,
            "bleed_mm": 0,
            "output_kind": "line_art",
        },
        pixel_width=800,
        pixel_height=1200,
    )
    assert low_resolution["ok"]
    assert low_resolution["errors"] == []
    assert low_resolution["print_quality_threshold_claim"] is False
    assert low_resolution["target_contract"]["printer_confirmation_required"] is True
    assert any("guidance" in warning.casefold() for warning in low_resolution["warnings"])
    assert any("bleed" in warning.casefold() for warning in low_resolution["warnings"])

    runtime_limited = output_preflight(
        {"mode": "print", "output_kind": "color"},
        pixel_width=16385,
        pixel_height=100,
    )
    assert runtime_limited["ok"] is False
    assert runtime_limited["canvas_limit_contract"]["universal_capacity_claim"] is False
    assert "not a Qt" in runtime_limited["errors"][0]


def test_new_canvas_print_preset_calculates_pixels_and_output_contract() -> None:
    app = _app()
    from app.drawing import NewCanvasDialog

    dialog = NewCanvasDialog()
    dialog.mode_combo.setCurrentIndex(dialog.mode_combo.findData("print"))
    app.processEvents()
    request = dialog.canvas_request()
    assert request["purpose"] == "print"
    assert request["template"].startswith("A4")
    assert (request["width"], request["height"]) == (2551, 3579)
    assert request["output"]["width_mm"] == 210
    assert request["output"]["height_mm"] == 297
    assert request["output"]["ppi"] == 300
    assert request["output"]["bleed_mm"] == 3
    assert request["background"] == "#FFFFFF"
    assert "Trim size excludes bleed" in dialog.output_summary_label.text()

    dialog.unit_combo.setCurrentIndex(dialog.unit_combo.findData("in"))
    app.processEvents()
    assert dialog.physical_width_spin.value() == pytest.approx(210 / 25.4, abs=0.01)
    assert dialog.canvas_request()["width"] == 2551
    dialog.close()


def test_output_size_dialog_distinguishes_metadata_from_resampling() -> None:
    app = _app()
    from app.drawing import PainterOutputSettingsDialog

    dialog = PainterOutputSettingsDialog(
        None,
        pixel_size=(2480, 3508),
        output_settings={
            "mode": "print",
            "width_mm": 210,
            "height_mm": 297,
            "ppi": 300,
            "bleed_mm": 0,
            "resample": False,
        },
    )
    dialog.resample_check.setChecked(False)
    dialog.ppi_spin.setValue(150)
    app.processEvents()
    request = dialog.output_request()
    assert (request["width"], request["height"]) == (2480, 3508)
    assert request["settings"]["width_mm"] == pytest.approx(420, abs=0.2)

    dialog.resample_check.setChecked(True)
    dialog.physical_width_spin.setValue(210)
    dialog.physical_height_spin.setValue(297)
    dialog.ppi_spin.setValue(300)
    app.processEvents()
    request = dialog.output_request()
    assert (request["width"], request["height"]) == (2480, 3508)
    dialog.close()


def test_tspaint_and_png_preserve_print_output_metadata(tmp_path: Path) -> None:
    app = _app()
    from PIL import Image

    from app.drawing import PaintDialog, create_blank_paint_pixmap

    output = {
        "mode": "print",
        "width_mm": 210,
        "height_mm": 297,
        "ppi": 300,
        "bleed_mm": 0,
        "output_kind": "color",
        "resample": True,
    }
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(2480, 3508, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
        output_settings=output,
    )
    payload = dialog._painter_document_payload()
    assert payload["output"]["mode"] == "print"
    assert payload["output"]["ppi"] == 300
    assert dialog.canvas._output_guide_settings["mode"] == "print"

    document_path = tmp_path / "print-document.tspaint"
    dialog.save_document_to_path(document_path)
    restored = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(64, 64),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    restored.open_document_from_path(document_path)
    assert restored._output_settings["width_mm"] == 210
    assert restored._output_settings["ppi"] == 300

    png_path = tmp_path / "print.png"
    report = restored.export_png_to_path(png_path)
    assert report["resolution_ppi"] == 300
    assert report["preflight"]["mode"] == "print"
    with Image.open(png_path) as image:
        assert image.info["dpi"][0] == pytest.approx(300, abs=0.2)
        assert image.info["dpi"][1] == pytest.approx(300, abs=0.2)
    dialog.close()
    restored.close()
