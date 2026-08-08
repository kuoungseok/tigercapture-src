from __future__ import annotations

import os
from pathlib import Path


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _dialog():
    _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    return PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "#FFFFFF"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )


def test_oklch_palette_is_gamut_mapped_and_perceptual() -> None:
    from app.painter_palette import oklch_harmony_colors, rgb_to_oklch

    rows = oklch_harmony_colors((225, 64, 86))
    assert len(rows) == 8
    assert [label for _rgb, label in rows][2] == "Current color"
    assert [label for _rgb, label in rows][-1] == "Complement"
    assert all(0 <= channel <= 255 for rgb, _label in rows for channel in rgb)
    lightness = [rgb_to_oklch(rgb)[0] for rgb, _label in rows[:5]]
    assert lightness[0] < lightness[1] < lightness[3] < lightness[4]
    for mode in (
        "monochrome",
        "analogous",
        "complementary",
        "split_complementary",
        "triadic",
    ):
        mode_rows = oklch_harmony_colors((225, 64, 86), mode)
        assert len(mode_rows) == 8
        assert all(
            0 <= channel <= 255
            for mode_rgb, _label in mode_rows
            for channel in mode_rgb
        )


def test_oklch_powerless_gray_hue_does_not_create_arbitrary_harmony() -> None:
    import math
    from app.painter_palette import oklch_harmony_colors, rgb_to_oklch

    lightness, chroma, hue = rgb_to_oklch((128, 128, 128))
    assert 0.0 < lightness < 1.0
    assert chroma <= 0.000004
    assert math.isnan(hue)
    for mode in ("full", "analogous", "complementary", "split_complementary", "triadic"):
        rows = oklch_harmony_colors((128, 128, 128), mode)
        assert len(rows) == 8
        assert all(red == green == blue for (red, green, blue), _label in rows)


def test_palette_library_and_brush_bundle_round_trip(tmp_path: Path) -> None:
    from app.painter_palette import (
        export_brush_bundle,
        import_brush_bundle,
        load_palette_library,
        save_palette_library,
    )

    library_path = tmp_path / "palette.json"
    save_palette_library(
        {
            "favorites": ["Drawing::Ink::round"],
            "recent_brushes": ["Drawing::Ink::round"],
            "recent_colors": [[1, 2, 3], [1, 2, 3], "#AABBCC"],
            "pinned_colors": ["#102030"],
            "custom_brushes": [
                {
                    "name": "Large Ink",
                    "category": "Comics",
                    "style": "round",
                    "width": 1400,
                    "pressure_response": 165,
                    "tags": ["ink", "large"],
                }
            ],
        },
        library_path,
    )
    restored = load_palette_library(library_path)
    assert restored["recent_colors"] == [[1, 2, 3], [170, 187, 204]]
    assert restored["custom_brushes"][0]["width"] == 1400
    assert restored["custom_brushes"][0]["pressure_response"] == 165

    bundle_path = tmp_path / "brushes.tsbrushes"
    export_brush_bundle(restored["custom_brushes"], bundle_path)
    imported = import_brush_bundle(bundle_path)
    assert imported == restored["custom_brushes"]


def test_corrupt_palette_is_reported_and_preserved_before_replacement(tmp_path: Path) -> None:
    from app.painter_palette import (
        load_palette_library_with_report,
        save_palette_library_with_report,
    )

    library_path = tmp_path / "palette.json"
    corrupt_bytes = b'{"schema": "broken",'
    library_path.write_bytes(corrupt_bytes)
    library, load_report = load_palette_library_with_report(library_path)
    assert library["favorites"] == []
    assert load_report["status"] == "corrupt"
    assert load_report["fallback_used"] is True
    assert load_report["error"]["type"]

    save_report = save_palette_library_with_report(
        {"favorites": ["Drawing::Ink::round"]},
        library_path,
    )
    backup = Path(save_report["corrupt_backup_path"])
    assert backup.read_bytes() == corrupt_bytes
    assert backup != library_path
    restored, restored_report = load_palette_library_with_report(library_path)
    assert restored["favorites"] == ["Drawing::Ink::round"]
    assert restored_report["status"] == "loaded"


def test_palette_save_failure_is_exposed_and_later_success_clears_it(monkeypatch) -> None:
    dialog = _dialog()
    import app.drawing as drawing

    def fail_save(_payload):
        raise OSError("palette volume is read-only")

    monkeypatch.setattr(drawing, "save_palette_library", fail_save)
    dialog._save_palette_library_state()
    assert "read-only" in dialog.painter_action_state()["operational_errors"]["palette_library"]

    monkeypatch.setattr(drawing, "save_palette_library", lambda _payload: None)
    dialog._save_palette_library_state()
    assert dialog.painter_action_state()["operational_errors"]["palette_library"] == ""
    dialog.close()


def test_quick_palette_large_brush_custom_preset_and_document_colors() -> None:
    app = _app()
    dialog = _dialog()
    dialog.show()
    app.processEvents()

    dialog._on_width_changed(1400)
    assert dialog._pen_width == 1400
    assert dialog.canvas._pen_width == 1400
    assert dialog._top_brush_size_spin.maximum() == 5000

    before_hardness = int(dialog._brush_detail_settings["hardness"])
    dialog._adjust_brush_from_hud(1000.0, 20.0, False)
    assert dialog._pen_width == 5000
    assert int(dialog._brush_detail_settings["hardness"]) < before_hardness

    custom = dialog._create_custom_brush_preset(
        "Storyboard Giant",
        ["storyboard", "ink"],
        category="Comics",
    )
    assert custom["width"] == 5000
    assert custom["pressure_response"] == dialog._brush_detail_settings["pressure_response"]
    assert dialog._brush_presets_catalog()[-1]["name"] == "Storyboard Giant"
    assert dialog._palette_library_state["custom_brushes"][-1]["category"] == "Comics"

    for index in range(40):
        dialog._remember_recent_color((index, index + 1, index + 2))
    assert len(dialog._recent_colors) == 32
    assert len(dialog._document_palette_colors) == 32
    dialog._toggle_pin_current_color()
    assert dialog._pinned_colors

    payload = dialog._painter_document_payload()
    assert payload["palette"]["schema"] == "tigerstudio.painter.document-palette.v1"
    assert len(payload["palette"]["colors"]) == 32
    state = dialog.painter_action_state()
    assert state["palette"]["engine"] == "oklch_srgb_gamut_mapped_v1"
    assert state["brush"]["library"]["max_brush_size_px"] == 5000
    assert state["brush"]["library"]["size_limit_contract"]["performance_at_maximum_claim"] is False
    triadic_index = dialog._palette_harmony_combo.findData("triadic")
    dialog._palette_harmony_combo.setCurrentIndex(triadic_index)
    assert dialog._palette_harmony_mode == "triadic"
    assert len(dialog._derived_palette_colors()) == 8

    dialog._show_quick_palette()
    app.processEvents()
    assert dialog._quick_palette_menu.isVisible()
    dialog._quick_palette_menu.close()
    dialog.close()


def test_document_palette_round_trips_in_tspaint(tmp_path: Path) -> None:
    app = _app()
    dialog = _dialog()
    dialog._remember_recent_color((18, 52, 86))
    dialog._remember_recent_color((170, 187, 204))
    path = tmp_path / "palette-roundtrip.tspaint"
    dialog.save_document_to_path(path)

    restored = _dialog()
    restored.open_document_from_path(path)
    app.processEvents()
    assert restored._document_palette_colors[:2] == [
        (170, 187, 204),
        (18, 52, 86),
    ]
    assert restored._recent_color_btns[0].width() >= 36
    dialog.close()
    restored.close()


def test_saved_pressure_response_changes_tablet_curve() -> None:
    _app()
    from PySide6.QtCore import QPointF

    from app.painter_stylus import StylusSample

    dialog = _dialog()
    dialog._set_brush_detail_value("pressure_response", 200)
    dialog.canvas._begin_current_stroke(
        QPointF(20.0, 20.0),
        StylusSample(pressure=0.25),
    )
    assert dialog.canvas._current_pressure == [0.5]
    preset = dialog._create_custom_brush_preset("Soft Pressure")
    assert preset["pressure_response"] == 200
    dialog.canvas._clear_current_stroke()
    dialog.close()


def test_pen_barrel_click_opens_palette_and_drag_adjusts_without_stroke() -> None:
    _app()
    from PySide6.QtCore import QPointF
    from PySide6.QtTest import QSignalSpy

    dialog = _dialog()
    canvas = dialog.canvas
    palette_spy = QSignalSpy(canvas.quick_palette_requested)
    adjust_spy = QSignalSpy(canvas.brush_hud_adjust_requested)

    canvas._begin_brush_hud_gesture(QPointF(100.0, 100.0))
    assert canvas._finish_brush_hud_gesture(QPointF(102.0, 101.0))
    assert palette_spy.count() == 1
    assert canvas.embedded_strokes() == []

    canvas._begin_brush_hud_gesture(QPointF(100.0, 100.0))
    canvas._update_brush_hud_gesture(QPointF(125.0, 114.0))
    canvas._finish_brush_hud_gesture(QPointF(125.0, 114.0))
    assert adjust_spy.count() == 2
    assert palette_spy.count() == 1
    assert canvas.embedded_strokes() == []
    dialog.close()
