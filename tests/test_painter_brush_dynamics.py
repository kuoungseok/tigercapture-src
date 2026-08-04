from __future__ import annotations

import json
import math
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _render(settings: dict[str, object], *, background: str | None = None) -> bytes:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from app.drawing import DrawingCanvas, Stroke

    image = QImage(160, 96, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(background) if background else Qt.GlobalColor.transparent)
    stroke = Stroke(
        points=[(0.08, 0.62), (0.28, 0.28), (0.52, 0.55), (0.76, 0.34), (0.92, 0.58)],
        color=(220, 62, 45), opacity=220, width_px=18, brush_style="round",
        brush_spacing=28, brush_roundness=62, brush_seed=7919,
        brush_dynamics={"enabled": True, **settings},
        point_pressure=[0.15, 0.42, 0.7, 0.9, 0.55],
        point_tilt_x=[0.0, 0.3, 0.5, -0.2, -0.4],
        point_tilt_y=[0.0, -0.4, 0.2, 0.45, 0.1],
        point_rotation=[0.1, 0.3, 0.5, 0.7, 0.9],
        point_tangential_pressure=[0.0, 0.2, 0.5, 0.8, 1.0],
    )
    painter = QPainter(image)
    DrawingCanvas._paint_stroke(painter, stroke, image.width(), image.height())
    painter.end()
    return bytes(image.constBits())


def test_brush_dynamics_contract_separates_replay_from_physical_claims() -> None:
    from app.painter_brush_dynamics import BRUSH_DYNAMICS_MODEL_CONTRACT

    assert BRUSH_DYNAMICS_MODEL_CONTRACT["model"] == "tiger_authored_deterministic_dab_dynamics_v1"
    assert BRUSH_DYNAMICS_MODEL_CONTRACT["deterministic_replay_claim"] is True
    assert BRUSH_DYNAMICS_MODEL_CONTRACT["physical_media_claim"] is False
    assert BRUSH_DYNAMICS_MODEL_CONTRACT["driver_latency_claim"] is False
    assert BRUSH_DYNAMICS_MODEL_CONTRACT["external_brush_engine_parity_claim"] is False


def test_advanced_texture_mapping_normalization_rejects_nonfinite_serialized_values() -> None:
    from app.painter_brush_dynamics import normalize_brush_dynamics

    normalized = normalize_brush_dynamics(
        {
            "protect_texture": True,
            "texture": {
                "pattern_id": "  paper/fine  ",
                "strength": 125,
                "scale": float("nan"),
                "offset": [float("inf"), 0],
            },
            "document_texture": {
                "pattern_id": "paper/cold-press",
                "strength": "54",
                "scale": "0.625",
                "offset": ["0.125", "-0.25"],
            },
        }
    )
    assert normalized["texture"] == {
        "pattern_id": "paper/fine",
        "strength": 100.0,
    }
    assert normalized["document_texture"] == {
        "pattern_id": "paper/cold-press",
        "strength": 54.0,
        "scale": 0.625,
        "offset": [0.125, -0.25],
    }
    assert normalized["normalization_errors"] == [
        "texture.scale must be finite and positive",
        "texture.offset must contain two finite numbers",
    ]


def test_corrupt_dynamic_scalars_and_negative_seed_fallback_with_diagnostics() -> None:
    from app.painter_brush_dynamics import normalize_brush_dynamics

    normalized = normalize_brush_dynamics(
        {
            "flow": float("inf"),
            "scatter_count": "bad",
            "sampled_rgba": [["bad", 0, 0, 255]],
            "noise_seed": -1,
        }
    )
    assert normalized["flow"] == 100
    assert normalized["scatter_count"] == 1
    assert normalized["sampled_rgba"] == []
    assert normalized["noise_seed"] == (1 << 64) - 1
    assert normalized["normalization_errors"] == [
        "flow must be finite numeric percent",
        "scatter_count must be an integer from 1 to 8",
        "sampled_rgba rejected 1 invalid rows",
    ]
    assert _render(normalized)


def test_engine_v2_dynamic_render_is_invariant_to_collinear_input_tessellation() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage, QPainter
    from app.drawing import DrawingCanvas, Stroke

    def render(points: list[tuple[float, float]]) -> bytes:
        image = QImage(160, 64, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        stroke = Stroke(
            points=points,
            color=(36, 102, 210),
            width_px=14,
            brush_style="impasto_oil",
            brush_spacing=20,
            brush_engine_version=2,
            bristle_count=12,
            brush_seed=721,
            brush_dynamics={
                "enabled": True,
                "dual_brush_enabled": True,
                "dual_brush_seed": 31,
                "dual_brush_strength": 70,
            },
        )
        painter = QPainter(image)
        try:
            DrawingCanvas._paint_stroke(painter, stroke, 160, 64)
        finally:
            painter.end()
        return bytes(image.constBits())

    assert render([(0.1, 0.5), (0.9, 0.5)]) == render(
        [(0.1, 0.5), (0.5, 0.5), (0.9, 0.5)]
    ) == render(
        [(0.1, 0.5), (0.3, 0.5), (0.5, 0.5), (0.7, 0.5), (0.9, 0.5)]
    )


def test_extreme_dynamic_stroke_is_bounded_and_reports_uniform_degrade() -> None:
    from app.drawing import Stroke
    from app.painter_brush_dynamics import (
        PAINTER_DYNAMIC_DAB_BUDGET,
        dynamic_dab_workload,
        dynamic_dabs,
    )

    points = [
        (0.0 if index % 2 == 0 else 1.0, index / 39.0)
        for index in range(40)
    ]
    stroke = Stroke(
        points=points,
        width_px=0.5,
        brush_spacing=1,
        brush_seed=37,
        brush_dynamics={
            "enabled": True,
            "scatter_count": 8,
            "buildup": 100,
            "scatter": 100,
            "dual_brush_enabled": True,
            "dual_brush_strength": 80,
        },
    )
    authored_before = json.loads(json.dumps(stroke.brush_dynamics))
    dabs = dynamic_dabs(stroke, 256, 256)
    workload = dynamic_dab_workload(stroke, 256, 256)
    assert stroke.brush_dynamics == authored_before
    assert len(dabs) == PAINTER_DYNAMIC_DAB_BUDGET
    assert workload["estimated_dabs"] > PAINTER_DYNAMIC_DAB_BUDGET
    assert workload["rendered_dabs"] == PAINTER_DYNAMIC_DAB_BUDGET
    assert workload["degraded"] is True
    assert workload["effective_spacing_px"] > workload["requested_spacing_px"]
    assert math.isfinite(float(dabs[0]["x"]))
    assert math.isfinite(float(dabs[-1]["y"]))


@pytest.mark.parametrize("brush_seed", [-1, 10**1000])
def test_corrupt_or_oversized_stroke_seed_is_uint64_normalized(
    brush_seed: int,
) -> None:
    from app.drawing import Stroke
    from app.painter_brush_dynamics import dynamic_dabs

    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        width_px=8,
        brush_seed=brush_seed,
        brush_dynamics={"enabled": True, "noise_enabled": True},
    )
    first = dynamic_dabs(stroke, 96, 64)
    second = dynamic_dabs(stroke, 96, 64)
    assert first == second
    assert first


def test_pressure_calibration_curve_and_stabilization_are_prefix_stable() -> None:
    from app.painter_brush_dynamics import map_pressure, stabilize_points

    settings = {
        "pressure_min": 20,
        "pressure_max": 80,
        "pressure_curve": [[0, 0], [0.5, 0.25], [1, 1]],
    }
    assert map_pressure(0.2, settings) == 0.0
    assert abs(map_pressure(0.5, settings) - 0.25) < 1e-6
    assert map_pressure(0.8, settings) == 1.0
    points = [(0.0, 0.0), (0.4, 0.8), (0.9, 0.3)]
    full = stabilize_points(points, 0.75)
    assert full[:2] == stabilize_points(points[:2], 0.75)
    assert full != points


def test_every_active_dynamics_category_changes_actual_pixels() -> None:
    baseline = _render({})
    variants = {
        "flow": {"flow": 32},
        "buildup": {"buildup": 100},
        "stabilization": {"stabilization": 82},
        "scatter": {"scatter": 90, "scatter_count": 3},
        "texture": {"texture_strength": 86, "texture_scale": 37},
        "transfer": {"transfer_flow": 44, "transfer_opacity": 63},
        "color": {"hue_jitter": 55, "saturation_jitter": 40, "value_jitter": 32},
        "pose": {"tilt_size": 60, "tilt_angle": 80, "rotation_angle": 100, "barrel_flow": 70},
    }
    rendered = {name: _render(values) for name, values in variants.items()}
    assert all(value != baseline for value in rendered.values())
    assert len(set(rendered.values())) == len(rendered)
    assert _render({"flow": 30}) != _render({"flow": 100, "buildup": 100})


def test_smudge_mixer_pickup_use_underlying_canvas_color() -> None:
    paint = _render({"mode": "paint"}, background="#2877C8")
    smudge = _render({"mode": "smudge", "pickup": 90}, background="#2877C8")
    mixer = _render({"mode": "mixer", "mix": 50}, background="#2877C8")
    pickup = _render({"mode": "pickup", "pickup": 45}, background="#2877C8")
    assert len({paint, smudge, mixer, pickup}) == 4


def _render_smudge_response(
    *, length: int, radius: int, color_rate: int, smudge_type: str = "dulling"
):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor, QImage, QPainter
    from app.drawing import DrawingCanvas, Stroke

    image = QImage(200, 64, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#E4C52E"))
    painter = QPainter(image)
    painter.fillRect(QRect(0, 0, 100, 64), QColor("#2468D8"))
    painter.end()
    stroke = Stroke(
        points=[(0.1, 0.5), (0.9, 0.5)],
        color=(220, 45, 35),
        opacity=255,
        width_px=22,
        brush_style="round",
        brush_spacing=18,
        brush_seed=17,
        brush_dynamics={
            "enabled": True,
            "mode": "smudge",
            "flow": 100,
            "pickup": 100,
            "smudge_length": length,
            "smudge_radius": radius,
            "color_rate": color_rate,
            "smudge_type": smudge_type,
        },
        point_pressure=[1.0, 1.0],
    )
    painter = QPainter(image)
    DrawingCanvas._paint_stroke(painter, stroke, image.width(), image.height())
    painter.end()
    return image


def test_smudge_length_radius_and_color_rate_have_measured_pixel_responses() -> None:
    short = _render_smudge_response(length=0, radius=0, color_rate=0)
    carried = _render_smudge_response(length=100, radius=0, color_rate=0)
    wide = _render_smudge_response(length=0, radius=100, color_rate=0)
    colored = _render_smudge_response(length=100, radius=0, color_rate=100)
    end_x, center_y = 165, 32
    assert carried.pixelColor(end_x, center_y).blue() > short.pixelColor(end_x, center_y).blue()
    assert colored.pixelColor(end_x, center_y).red() > carried.pixelColor(end_x, center_y).red()
    assert bytes(wide.constBits()) != bytes(short.constBits())
    smear_narrow = _render_smudge_response(
        length=100, radius=0, color_rate=0, smudge_type="smear"
    )
    smear_wide = _render_smudge_response(
        length=100, radius=100, color_rate=0, smudge_type="smear"
    )
    assert smear_narrow == smear_wide


def test_live_smudge_uses_committed_layer_source_and_matches_pen_up_pixels() -> None:
    from PySide6.QtCore import QPointF, QRect, QSize
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, PaintDialog, create_blank_paint_pixmap
    from app.painter_stylus import StylusSample

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(200, 64, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    layer_id = dialog._active_paint_layer().layer_id
    base = QImage(200, 64, QImage.Format.Format_ARGB32_Premultiplied)
    base.fill(QColor("#E4C52E"))
    base_painter = QPainter(base)
    base_painter.fillRect(QRect(0, 0, 100, 64), QColor("#2468D8"))
    base_painter.end()
    dialog._paint_layer_rasters[layer_id] = base.copy()
    dialog._sync_canvas_layer_view()
    dialog.canvas.set_view_pose(rotation_degrees=0.0, content_size=QSize(200, 64))
    dialog._pen_color = QColor(220, 45, 35)
    dialog._pen_width = 22
    dialog.canvas.set_pen_color(dialog._pen_color)
    dialog.canvas.set_pen_width(22)
    dialog._set_brush_dynamics(
        {
            "enabled": True,
            "mode": "smudge",
            "flow": 100,
            "pickup": 100,
            "smudge_length": 100,
            "smudge_radius": 0,
            "color_rate": 0,
        }
    )
    sample = StylusSample(pressure=1.0)
    committed = []
    dialog.canvas.stroke_added.connect(committed.append)
    dialog.canvas._begin_current_stroke(QPointF(20, 32), sample)
    dialog.canvas._append_current_stroke_sample(QPointF(180, 32), sample, force=True)
    live_overlay = dialog.canvas._live_stroke_cache_image.copy()
    live_composite = base.copy()
    painter = QPainter(live_composite)
    painter.drawImage(0, 0, live_overlay)
    painter.end()
    dialog.canvas._finish_current_stroke()
    assert committed
    assert committed[-1].brush_dynamics["sampled_rgba"]
    final = base.copy()
    painter = QPainter(final)
    DrawingCanvas._paint_stroke(painter, committed[-1], 200, 64)
    painter.end()
    import numpy as np

    live_bytes = np.frombuffer(bytes(live_composite.constBits()), dtype=np.uint8)
    final_bytes = np.frombuffer(bytes(final.constBits()), dtype=np.uint8)
    # Live uses a transparent-overlay stage before the layer alpha-over stage;
    # commit draws directly. The contract budgets one 8-bit code value for each
    # distinct quantized alpha-over stage rather than using an observed cutoff.
    from app.painter_brush_dynamics import BRUSH_DYNAMICS_MODEL_CONTRACT

    tolerance = BRUSH_DYNAMICS_MODEL_CONTRACT["live_commit_rgba_tolerance_contract"]
    assert int(np.max(np.abs(live_bytes.astype(int) - final_bytes.astype(int)))) <= int(
        tolerance["max_delta_lsb"]
    )
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_overlay_smudge_samples_all_layers_and_freezes_replay_colors(tmp_path: Path) -> None:
    from PySide6.QtCore import QPointF, QSize
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, PaintDialog, create_blank_paint_pixmap
    from app.painter_stylus import StylusSample

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(160, 80, "transparent"),
        initial_strokes=[],
        time_ms=0,
        standalone=True,
    )
    bottom_id = dialog._active_paint_layer().layer_id
    bottom = QImage(160, 80, QImage.Format.Format_ARGB32_Premultiplied)
    bottom.fill(QColor("#2468D8"))
    dialog._paint_layer_rasters[bottom_id] = bottom
    top = dialog._new_paint_layer("Overlay Smudge")
    dialog._select_paint_layer_by_id(top.layer_id)
    dialog._sync_canvas_layer_view()
    dialog.canvas.set_view_pose(rotation_degrees=0.0, content_size=QSize(160, 80))
    dialog._pen_color = QColor(220, 45, 35)
    dialog.canvas.set_pen_color(dialog._pen_color)
    dialog.canvas.set_pen_width(20)
    dialog._set_brush_dynamics(
        {
            "enabled": True,
            "mode": "smudge",
            "smudge_type": "dulling",
            "overlay": True,
            "flow": 100,
            "pickup": 100,
            "smudge_length": 100,
            "smudge_radius": 0,
            "color_rate": 0,
        }
    )
    committed = []
    dialog.canvas.stroke_added.connect(committed.append)
    sample = StylusSample(pressure=1.0)
    dialog.canvas._begin_current_stroke(QPointF(20, 40), sample)
    dialog.canvas._append_current_stroke_sample(QPointF(140, 40), sample, force=True)
    dialog.canvas._finish_current_stroke()
    assert committed and committed[-1].brush_dynamics["overlay"] is True
    samples = committed[-1].brush_dynamics["sampled_rgba"]
    assert samples and samples[len(samples) // 2][:3] == [36, 104, 216]

    # Replay onto a different target: the picked blue remains authored in the
    # stroke instead of being re-sampled as green after a lower-layer edit.
    replay = QImage(160, 80, QImage.Format.Format_ARGB32_Premultiplied)
    replay.fill(QColor("#28B86A"))
    painter = QPainter(replay)
    DrawingCanvas._paint_stroke(painter, committed[-1], 160, 80)
    painter.end()
    center = replay.pixelColor(80, 40)
    assert center.blue() > center.green()
    from PIL import Image
    from app.drawing import PaintLayer, export_paint_png

    export_path = tmp_path / "overlay-smudge.png"
    report = export_paint_png(
        export_path,
        strokes=[committed[-1]],
        paint_layers=[PaintLayer(top.layer_id, "Overlay Smudge")],
        frame_size=(160, 80),
        include_background=False,
    )
    assert report["path"] == str(export_path.resolve())
    exported_center = Image.open(export_path).convert("RGBA").getpixel((80, 40))
    assert exported_center[2] > exported_center[1]
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def test_export_requires_document_or_background_dimensions_instead_of_full_hd(
    tmp_path: Path,
) -> None:
    from app.drawing import export_paint_png

    with pytest.raises(ValueError, match="dimensions|frame.*size|canvas.*size"):
        export_paint_png(
            tmp_path / "missing-size.png",
            background_pixmap=None,
            frame_size=None,
        )


def test_captured_dab_bundle_roundtrip_and_missing_resource_diagnostics(tmp_path: Path) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImage
    from app.painter_brush_dynamics import _captured_dab_image, brush_resource_diagnostics
    from app.painter_palette import export_brush_bundle, import_brush_bundle

    dab = QImage(8, 8, QImage.Format.Format_ARGB32)
    dab.fill(Qt.GlobalColor.white)
    dab_path = tmp_path / "dab.png"
    assert dab.save(str(dab_path), "PNG")
    preset = {
        "name": "Captured", "category": "My Brushes", "style": "round",
        "width": 22, "opacity": 100,
        "dynamics": {"enabled": True, "dab_image_path": str(dab_path)},
    }
    assert brush_resource_diagnostics(preset)["ok"]
    bundle = tmp_path / "captured.tsbrushes"
    export_brush_bundle([preset], bundle)
    payload = json.loads(bundle.read_text(encoding="utf-8"))
    assert payload["schema"].endswith(".v2")
    assert payload["brushes"][0]["dynamics"]["dab_png_base64"]
    restored = import_brush_bundle(bundle)
    assert restored[0]["dynamics"]["dab_png_base64"]
    missing = dict(preset)
    missing["dynamics"] = {"enabled": True, "dab_image_path": str(tmp_path / "missing.png")}
    assert not brush_resource_diagnostics(missing)["ok"]
    invalid_embedded = {
        "dynamics": {"enabled": True, "dab_png_base64": "not-base64%%"}
    }
    invalid_report = brush_resource_diagnostics(invalid_embedded)
    assert invalid_report["ok"] is False
    assert invalid_report["embedded_valid"] is False
    assert "embedded:dab_png_base64:invalid" in invalid_report["missing_resources"]
    durable_fallback = {
        "dab_png_base64": "not-base64%%",
        "dab_image_path": str(dab_path),
    }
    assert _captured_dab_image(durable_fallback) is not None
    fallback_report = brush_resource_diagnostics({"dynamics": durable_fallback})
    assert fallback_report["ok"] is True
    assert fallback_report["embedded_valid"] is False
    abr = tmp_path / "legacy.abr"
    abr.write_bytes(b"\x00\x06\x00\x00")
    try:
        import_brush_bundle(abr)
    except ValueError as exc:
        assert "proprietary dab decoding" in str(exc).casefold()
    else:
        raise AssertionError("ABR scope must be explicit")


def test_dialog_dynamics_actions_and_document_roundtrip(tmp_path: Path) -> None:
    from PySide6.QtWidgets import QApplication
    from app.actions.registry import ActionRegistry
    from app.drawing import PaintDialog, create_blank_paint_pixmap

    app = QApplication.instance() or QApplication([])
    dialog = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(96, 64, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    registry = ActionRegistry(owner=dialog)
    ids = {row["id"] for row in registry.list_actions()}
    assert {
        "paint.brush.set", "paint.brush.calibration.set",
        "paint.brush.resources.diagnose",
    } <= ids
    result = registry.execute("paint.brush.set", {
        "dynamics": {
            "enabled": True, "flow": 48, "buildup": 66,
            "scatter": 35, "mode": "mixer", "mix": 72,
        }
    }).to_dict()
    assert result["ok"]
    calibrated = registry.execute("paint.brush.calibration.set", {
        "device_id": "tablet-a", "minimum": 0.1, "maximum": 0.92,
        "curve": [[0, 0], [0.5, 0.35], [1, 1]],
    }).to_dict()
    assert calibrated["ok"]
    diagnosed = registry.execute("paint.brush.resources.diagnose", {}).to_dict()
    assert diagnosed["ok"] and diagnosed["result"]["ok"]
    state = dialog.painter_action_state()["brush"]["engine"]
    assert state["dynamics"]["mode"] == "mixer"
    assert "tablet-a" in state["device_calibrations"]
    path = tmp_path / "dynamics.tspaint"
    dialog.save_document_to_path(path)
    reopened = PaintDialog(
        background_pixmap=create_blank_paint_pixmap(8, 8, "transparent"),
        initial_strokes=[], time_ms=0, standalone=True,
    )
    assert reopened.open_document_from_path(path)
    assert reopened._brush_dynamics["flow"] == 48
    assert reopened._brush_dynamics["mode"] == "mixer"
    assert "tablet-a" in reopened._brush_device_calibrations
    reopened.close(); dialog.close(); app.processEvents()


def test_dynamic_live_prefix_matches_committed_render_and_preserves_long_input() -> None:
    from types import SimpleNamespace
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from app.drawing import DrawingCanvas, Stroke
    from app.painter_brush_dynamics import dynamic_dabs

    app = QApplication.instance() or QApplication([])
    canvas = DrawingCanvas(lambda: 0, lambda: [])
    canvas.resize(160, 96)
    canvas.set_pen_width(14)
    canvas.set_brush_detail(dynamics={
        "enabled": True, "flow": 73, "buildup": 35,
        "stabilization": 62, "scatter": 18, "texture_strength": 25,
    })
    sample = SimpleNamespace(
        pressure=0.7, tilt=0.5, tilt_x=0.25, tilt_y=-0.15,
        rotation=0.65, tangential_pressure=0.4, load=1.0,
    )
    for index, point in enumerate(
        (QPointF(12, 62), QPointF(42, 30), QPointF(78, 58), QPointF(118, 34), QPointF(148, 60))
    ):
        if index == 0:
            canvas._begin_current_stroke(point, sample)
        else:
            canvas._append_current_stroke_sample(point, sample, force=True)
    committed = canvas._current_stroke_snapshot(160, 96, committed=True)
    final = QImage(160, 96, QImage.Format.Format_ARGB32_Premultiplied)
    final.fill(Qt.GlobalColor.transparent)
    painter = QPainter(final)
    DrawingCanvas._paint_stroke(painter, committed, 160, 96)
    painter.end()
    assert bytes(canvas._live_stroke_cache_image.constBits()) == bytes(final.constBits())

    long_stroke = Stroke(
        points=[(index / 4999.0, 0.5) for index in range(5000)],
        width_px=12, brush_spacing=10, brush_seed=23,
        brush_dynamics={"enabled": True, "scatter": 50, "scatter_count": 3},
    )
    dabs = dynamic_dabs(long_stroke, 1920, 1080)
    spacing_px = long_stroke.width_px * long_stroke.brush_spacing / 100.0
    expected = (int(math.ceil(1920 / spacing_px)) + 1) * 3
    assert abs(len(dabs) - expected) <= 3
    canvas.deleteLater(); app.processEvents()


def test_dynamic_dab_density_is_independent_of_collinear_input_tessellation() -> None:
    from app.drawing import Stroke
    from app.painter_brush_dynamics import dynamic_dabs

    dynamics = {"enabled": True, "scatter_count": 1, "buildup": 0}
    sparse = Stroke(
        points=[(0.0, 0.5), (1.0, 0.5)], width_px=1.0,
        brush_spacing=100, brush_dynamics=dynamics,
    )
    divided = Stroke(
        points=[(index / 32.0, 0.5) for index in range(33)], width_px=1.0,
        brush_spacing=100, brush_dynamics=dynamics,
    )

    assert len(dynamic_dabs(sparse, 7680, 64)) == len(
        dynamic_dabs(divided, 7680, 64)
    )
