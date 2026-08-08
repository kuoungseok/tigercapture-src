from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

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


def test_wet_canvas_advance_rejects_fabricated_durations() -> None:
    import pytest

    from app.painter_wet_canvas import advance_wet_canvas

    assert advance_wet_canvas({"enabled": True}, 0)["elapsed_seconds"] == 0.0
    for invalid in (-1, True, "1", None, float("nan"), float("inf"), 86400.1):
        with pytest.raises((TypeError, ValueError)):
            advance_wet_canvas({"enabled": True}, invalid)


def test_wet_canvas_render_identity_rejects_invalid_dimensions_and_opacity() -> None:
    import pytest

    from app.painter_wet_canvas import wet_canvas_signature

    with pytest.raises(ValueError, match="wet canvas width must be positive"):
        wet_canvas_signature([], {}, width=0, height=8, time_ms=0)
    with pytest.raises(ValueError, match="opacity_scale must be between 0 and 1"):
        wet_canvas_signature([], {}, width=8, height=8, time_ms=0, opacity_scale=1.1)


def test_wet_canvas_actions_validate_complete_input_before_owner_resolution() -> None:
    import pytest

    from app.actions.editor_adapter_paint import PaintAdapterMixin
    from app.actions.registry import ActionRegistry

    class Adapter(PaintAdapterMixin):
        def _paint_dialog_owner(self):
            raise AssertionError("invalid Wet Canvas input reached owner resolution")

    adapter = Adapter()
    invalid_settings = (
        {},
        {"layer_id": 1, "mixing": 0.5},
        {"enabled": 1},
        {"enabled": True, "mixing": None},
        {"mixing": True},
        {"mixing": -0.001},
        {"diffusion": 1.001},
        {"pickup": float("nan")},
        {"pickup": float("inf")},
        {"drying_seconds": 0},
        {"drying_seconds": 86400.1},
    )
    for payload in invalid_settings:
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_wet_canvas_settings_set(**payload)

    for seconds in (0, -1, True, "1", None, float("nan"), float("inf"), 86400.1):
        with pytest.raises((TypeError, ValueError)):
            adapter.paint_wet_canvas_advance(seconds=seconds)
    with pytest.raises(TypeError):
        adapter.paint_wet_canvas_advance(seconds=1, layer_id=1)
    with pytest.raises(TypeError):
        adapter.paint_wet_canvas_dry(layer_id=1)

    schemas = {
        row["id"]: row["params_schema"]
        for row in ActionRegistry(owner=None).list_actions()
    }
    settings_schema = schemas["paint.wet_canvas.settings.set"]
    assert settings_schema["properties"]["drying_seconds"] == {
        "type": "number",
        "minimum": 1.0,
        "maximum": 86400.0,
    }
    assert settings_schema["anyOf"] == [
        {"required": [field]}
        for field in ("enabled", "mixing", "diffusion", "pickup", "drying_seconds")
    ]
    assert schemas["paint.wet_canvas.advance"]["properties"]["seconds"] == {
        "type": "number",
        "exclusiveMinimum": 0.0,
        "maximum": 86400.0,
    }


def test_wet_canvas_dialog_rejects_invalid_values_before_layer_or_undo() -> None:
    import pytest

    from app.drawing import PaintDialog

    def unexpected_lookup(*_args, **_kwargs):
        raise AssertionError("invalid Wet Canvas input reached layer lookup")

    direct = SimpleNamespace(
        _paint_layer_by_id=unexpected_lookup,
        _active_paint_layer=unexpected_lookup,
    )
    for values in (
        {},
        {"enabled": 1},
        {"mixing": -0.1},
        {"diffusion": float("nan")},
        {"drying_seconds": 86401},
        {"invented": 0.5},
    ):
        with pytest.raises((TypeError, ValueError)):
            PaintDialog._set_wet_canvas_settings(direct, values)
    with pytest.raises(TypeError):
        PaintDialog._set_wet_canvas_settings(
            direct,
            {"mixing": 0.5},
            layer_id=1,
        )
    for seconds in (0, -1, True, float("nan"), float("inf"), 86401):
        with pytest.raises((TypeError, ValueError)):
            PaintDialog._advance_wet_canvas(direct, seconds)
    with pytest.raises(TypeError):
        PaintDialog._advance_wet_canvas(direct, 1, layer_id=1)
    with pytest.raises(TypeError):
        PaintDialog._dry_active_wet_canvas(direct, layer_id=1)


def test_wet_canvas_drying_minutes_cover_serialized_domain_with_bounded_round_trip() -> None:
    import pytest

    from app.painter_wet_canvas import (
        WET_CANVAS_DRYING_MAX_SECONDS,
        WET_CANVAS_DRYING_MIN_SECONDS,
        WET_CANVAS_DRYING_UI_MINUTES_MAX,
        WET_CANVAS_DRYING_UI_MINUTES_MIN,
        drying_seconds_to_ui_minutes,
        drying_ui_minutes_to_seconds,
    )

    errors = []
    for seconds in range(
        int(WET_CANVAS_DRYING_MIN_SECONDS),
        int(WET_CANVAS_DRYING_MAX_SECONDS) + 1,
    ):
        minutes = drying_seconds_to_ui_minutes(seconds)
        assert WET_CANVAS_DRYING_UI_MINUTES_MIN <= minutes <= WET_CANVAS_DRYING_UI_MINUTES_MAX
        restored = drying_ui_minutes_to_seconds(minutes)
        errors.append(abs(restored - seconds))

    assert max(errors) == 59.0
    assert drying_seconds_to_ui_minutes(30) == 1
    assert drying_seconds_to_ui_minutes(90) == 2
    assert drying_seconds_to_ui_minutes(3600) == 60
    assert drying_seconds_to_ui_minutes(86400) == 1440
    assert drying_ui_minutes_to_seconds(1440) == 86400.0
    for invalid in (0, 1441, 1.5, True):
        with pytest.raises(ValueError):
            drying_ui_minutes_to_seconds(invalid)


def test_wet_canvas_drying_slider_edits_the_complete_serialized_domain() -> None:
    app = _app()
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(320, 180, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    layer = dialog._new_material_paint_layer("Wet Oil")
    layer.wet_canvas_settings["drying_seconds"] = 86400.0
    menu = dialog._build_material_options_menu()
    slider = dialog._wet_canvas_control_sliders["drying_seconds"]
    label = dialog._wet_canvas_control_labels["drying_seconds"]

    assert slider.minimum() == 1
    assert slider.maximum() == 1440
    assert slider.value() == 1440
    assert label.text() == "1440 min"

    slider.setValue(721)
    app.processEvents()
    assert layer.wet_canvas_settings["drying_seconds"] == 43260.0
    assert label.text() == "721 min"

    menu.close()
    menu.deleteLater()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


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


def test_wet_canvas_diffusion_failure_is_typed_and_never_claimed(monkeypatch) -> None:
    _app()
    import cv2
    from app.drawing import Stroke

    def fail_blur(*_args, **_kwargs):
        raise RuntimeError("injected wet diffusion failure")

    monkeypatch.setattr(cv2, "GaussianBlur", fail_blur)
    _image, report = _render(
        [
            Stroke(
                points=[(0.2, 0.5), (0.8, 0.5)],
                color=(90, 130, 220),
                width_px=18,
            )
        ],
        {
            "enabled": True,
            "diffusion": 1.0,
            "drying_seconds": 100,
            "elapsed_seconds": 0,
        },
    )
    assert report["diffusion_applied"] is False
    assert report["diffusion_error"] == (
        "RuntimeError: injected wet diffusion failure"
    )


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

    selected_before_invalid_dry = dialog._current_layer_id()
    before_invalid_dry = dict(current_layer.wet_canvas_settings)
    invalid_dry = registry.execute(
        "paint.wet_canvas.dry",
        {"layer_id": "missing-wet-layer"},
    ).to_dict()
    assert not invalid_dry["ok"]
    assert dialog._current_layer_id() == selected_before_invalid_dry
    assert current_layer.wet_canvas_settings == before_invalid_dry

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
