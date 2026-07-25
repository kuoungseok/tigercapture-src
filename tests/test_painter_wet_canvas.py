from __future__ import annotations

import os
from pathlib import Path

import numpy as np


def _app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _rgba(image) -> np.ndarray:
    from PySide6.QtGui import QImage

    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(bytes(rgba.constBits()), dtype=np.uint8).reshape(
        rgba.height(),
        rgba.width(),
        4,
    )


def _render(strokes, settings):
    from app.drawing import DrawingCanvas
    from app.painter_wet_canvas import render_wet_layer_qimage

    return render_wet_layer_qimage(
        strokes,
        settings=settings,
        width=160,
        height=120,
        time_ms=0,
        render_stroke=lambda painter, stroke, width, height, opacity: DrawingCanvas._paint_stroke(
            painter,
            stroke,
            width,
            height,
            opacity_scale=opacity,
        ),
    )


def test_wet_canvas_state_advances_deterministically() -> None:
    from app.painter_wet_canvas import (
        advance_wet_canvas,
        dry_wet_canvas,
        normalize_wet_canvas_settings,
        wet_canvas_remaining,
    )

    settings = normalize_wet_canvas_settings(
        {"enabled": True, "drying_seconds": 100, "elapsed_seconds": 10}
    )
    assert wet_canvas_remaining(settings) == 0.9
    advanced = advance_wet_canvas(settings, 35)
    assert advanced["elapsed_seconds"] == 45.0
    assert wet_canvas_remaining(advanced) == 0.55
    dried = dry_wet_canvas(advanced)
    assert dried["elapsed_seconds"] == 100.0
    assert wet_canvas_remaining(dried) == 0.0


def test_wet_canvas_exchanges_color_only_while_layer_is_wet() -> None:
    _app()
    from app.drawing import Stroke

    red = Stroke(
        points=[(0.12, 0.5), (0.88, 0.5)],
        color=(230, 24, 20),
        width_px=34,
        opacity=255,
        material_wetness=1.0,
    )
    blue = Stroke(
        points=[(0.5, 0.12), (0.5, 0.88)],
        color=(20, 40, 230),
        width_px=34,
        opacity=255,
        material_wetness=1.0,
    )
    wet_settings = {
        "enabled": True,
        "mixing": 1.0,
        "diffusion": 0.0,
        "pickup": 1.0,
        "drying_seconds": 100,
        "elapsed_seconds": 0,
    }
    wet_image, report = _render([red, blue], wet_settings)
    dry_image, dry_report = _render(
        [red, blue],
        {**wet_settings, "elapsed_seconds": 100},
    )
    wet_pixel = _rgba(wet_image)[60, 80, :3].astype(int)
    dry_pixel = _rgba(dry_image)[60, 80, :3].astype(int)

    assert report["remaining"] == 1.0
    assert report["physical_pigment_claim"] is False
    assert dry_report["remaining"] == 0.0
    assert wet_pixel[0] > dry_pixel[0] + 20
    assert wet_pixel[2] < dry_pixel[2] - 10


def test_wet_canvas_export_uses_saved_layer_state(tmp_path: Path) -> None:
    _app()
    from PIL import Image

    from app.drawing import PaintLayer, Stroke, export_paint_png

    layer = PaintLayer(
        "wet-oil",
        "Wet Oil",
        layer_type="material",
        wet_canvas_settings={
            "enabled": True,
            "mixing": 1.0,
            "diffusion": 0.0,
            "pickup": 1.0,
            "drying_seconds": 100,
            "elapsed_seconds": 0,
        },
    )
    strokes = [
        Stroke(
            points=[(0.12, 0.5), (0.88, 0.5)],
            color=(230, 24, 20),
            width_px=34,
            layer_id=layer.layer_id,
            material_wetness=1.0,
        ),
        Stroke(
            points=[(0.5, 0.12), (0.5, 0.88)],
            color=(20, 40, 230),
            width_px=34,
            layer_id=layer.layer_id,
            material_wetness=1.0,
        ),
    ]
    path = tmp_path / "wet_canvas.png"
    report = export_paint_png(
        path,
        strokes=strokes,
        frame_size=(160, 120),
        include_background=False,
        paint_layers=[layer],
    )

    assert path.exists()
    assert report["wet_canvas_layer_count"] == 1
    pixel = np.asarray(Image.open(path).convert("RGBA"))[60, 80, :3]
    assert int(pixel[0]) > 40
    assert int(pixel[2]) > 20


def test_wet_canvas_actions_are_registered_and_edit_layer_state() -> None:
    app = _app()
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    layer = dialog._new_material_paint_layer("Wet Oil")
    registry = ActionRegistry(owner=dialog)
    action_ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.wet_canvas.settings.set",
        "paint.wet_canvas.advance",
        "paint.wet_canvas.dry",
    } <= action_ids

    configured = registry.execute(
        "paint.wet_canvas.settings.set",
        {
            "layer_id": layer.layer_id,
            "enabled": True,
            "mixing": 0.75,
            "diffusion": 0.3,
            "pickup": 0.55,
            "drying_seconds": 120,
        },
    ).to_dict()
    assert configured["ok"]
    current_layer = dialog._paint_layer_by_id(layer.layer_id)
    assert current_layer is not None
    assert current_layer.wet_canvas_settings["mixing"] == 0.75

    advanced = registry.execute(
        "paint.wet_canvas.advance",
        {"layer_id": layer.layer_id, "seconds": 30},
    ).to_dict()
    assert advanced["ok"]
    current_layer = dialog._paint_layer_by_id(layer.layer_id)
    assert current_layer is not None
    assert current_layer.wet_canvas_settings["elapsed_seconds"] == 30.0

    dried = registry.execute(
        "paint.wet_canvas.dry",
        {"layer_id": layer.layer_id},
    ).to_dict()
    assert dried["ok"]
    current_layer = dialog._paint_layer_by_id(layer.layer_id)
    assert current_layer is not None
    assert (
        current_layer.wet_canvas_settings["elapsed_seconds"]
        == current_layer.wet_canvas_settings["drying_seconds"]
    )

    dialog.close()
    dialog.deleteLater()
    app.processEvents()
