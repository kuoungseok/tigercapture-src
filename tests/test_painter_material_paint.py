from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_material_channels_are_authored_from_strokes() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import (
        material_paint_signature,
        rasterize_material_channels,
    )

    layer = PaintLayer(
        layer_id="material-1",
        name="Impasto",
        layer_type="material",
        material_settings={"thickness": 0.8, "roughness": 0.42},
    )
    stroke = Stroke(
        points=[(0.1, 0.7), (0.45, 0.25), (0.9, 0.55)],
        width_px=18.0,
        brush_style="bristle_oil",
        layer_id=layer.layer_id,
        material_enabled=True,
        material_load=0.9,
        material_thickness=0.84,
        material_wetness=0.32,
        material_gloss=0.38,
        material_roughness=0.46,
    )

    channels = rasterize_material_channels([stroke], [layer], width=192, height=108)
    assert channels["active"] is True
    assert channels["stroke_count"] == 1
    assert channels["height"].shape == (108, 192)
    assert channels["normal"].shape == (108, 192, 3)
    assert channels["direction"].shape == (108, 192, 2)
    assert float(np.max(channels["height"])) > 0.05
    assert float(np.std(channels["normal"][..., 0])) > 0.001
    assert float(np.min(channels["roughness"])) < 0.72

    first = material_paint_signature([stroke], [layer], width=192, height=108)
    stroke.material_thickness = 0.22
    second = material_paint_signature([stroke], [layer], width=192, height=108)
    assert first != second


def test_material_channels_merge_with_texture_lab_maps() -> None:
    from app.drawing import PaintLayer, Stroke
    from app.painter_material_paint import (
        merge_material_channels_into_generated,
        rasterize_material_channels,
    )

    layer = PaintLayer("m", "Material", layer_type="material")
    stroke = Stroke(
        points=[(0.2, 0.5), (0.8, 0.5)],
        width_px=12,
        layer_id="m",
        material_enabled=True,
        material_load=1.0,
        material_thickness=1.0,
    )
    channels = rasterize_material_channels([stroke], [layer], width=96, height=64)
    base = {
        "maps": {
            "height": np.zeros((64, 96), dtype=np.float32),
            "normal": np.full((64, 96, 3), 0.5, dtype=np.float32),
            "roughness": np.full((64, 96), 0.9, dtype=np.float32),
            "ao": np.ones((64, 96), dtype=np.float32),
        }
    }
    merged = merge_material_channels_into_generated(base, channels)
    assert merged["material_paint"]["native_channels"] is True
    assert merged["material_paint"]["stroke_count"] == 1
    assert float(np.max(merged["maps"]["height"])) > 0.0
    assert not np.array_equal(merged["maps"]["normal"], base["maps"]["normal"])


def test_material_layer_ui_and_stroke_contract(tmp_path: Path) -> None:
    app = _app()
    from app.drawing import PaintDialog, Stroke, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(640, 360, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    dialog.show()
    app.processEvents()
    layer = dialog._new_material_paint_layer("Oil Relief")
    dialog._set_material_settings(
        {"thickness": 0.91, "roughness": 0.37, "gloss": 0.46},
        layer_id=layer.layer_id,
    )
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=22,
        brush_style="impasto_oil",
        source_tool="pen",
    )
    dialog._on_stroke_added(stroke)
    app.processEvents()

    state = dialog.painter_action_state()
    active = next(row for row in state["layers"] if row["active"])
    assert active["layer_type"] == "material"
    assert active["material_settings"]["thickness"] == 0.91
    assert state["material_preview"]["enabled"] is True
    assert state["material_preview"]["stroke_count"] == 1
    saved_stroke = dialog.canvas.embedded_strokes()[-1]
    assert saved_stroke.material_enabled is True
    assert saved_stroke.material_thickness == 0.91
    assert saved_stroke.material_roughness == 0.37
    assert dialog._material_options_button.isVisible()

    output = tmp_path / "material_preview.png"
    payload = dialog.preview_pbr_map_to_path(output, allow_cpu=True)
    assert output.exists()
    assert payload["painter_source"]["material_paint"]["native_channels"] is True
    export_dir = tmp_path / "maps"
    exported = dialog.export_pbr_maps_to_path(
        export_dir,
        maps=("height", "normal", "roughness", "ao"),
        packed=False,
        allow_cpu=True,
    )
    assert exported["material_paint"]["native_channels"] is True
    assert set(exported["files"]) == {"height", "normal", "roughness", "ao"}
    assert Path(exported["manifest_path"]).exists()
    dialog.close()
