from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _tip_image(*, hardness: int, style: str = "round"):
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke

    image = QImage(101, 101, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    stroke = Stroke(
        points=[(0.5, 0.5)],
        width_px=40.0,
        brush_style=style,
        brush_hardness=hardness,
        brush_spacing=25,
        brush_roundness=100,
    )
    painter = QPainter(image)
    DrawingCanvas._paint_tip_detail_stroke(
        painter,
        stroke,
        image.width(),
        image.height(),
        QColor(40, 120, 220, 255),
        style,
    )
    painter.end()
    return image


def test_tip_hardness_is_direct_solid_radius_fraction() -> None:
    hard = _tip_image(hardness=100)
    soft = _tip_image(hardness=10)

    assert hard.pixelColor(50, 50).alpha() == 255
    assert soft.pixelColor(50, 50).alpha() == 255
    assert hard.pixelColor(68, 50).alpha() > soft.pixelColor(68, 50).alpha()
    assert soft.pixelColor(68, 50).alpha() < 64
    assert hard.pixelColor(72, 50).alpha() == 0
    assert soft.pixelColor(72, 50).alpha() == 0


def test_highlighter_style_does_not_override_authored_opacity() -> None:
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    from app.drawing import DrawingCanvas, Stroke

    configured = QPen(QColor(20, 220, 80, 255), 8.0)
    DrawingCanvas._configure_pen_for_style(configured, "highlighter")
    assert configured.color().alpha() == 255

    tip = _tip_image(hardness=100, style="highlighter")
    assert tip.pixelColor(50, 50).alpha() == 255

    dynamic = QImage(101, 101, QImage.Format.Format_ARGB32_Premultiplied)
    dynamic.fill(0)
    stroke = Stroke(
        points=[(0.25, 0.5), (0.75, 0.5)],
        color=(20, 220, 80),
        opacity=255,
        width_px=20.0,
        brush_style="highlighter",
        point_pressure=[0.5, 0.5],
    )
    painter = QPainter(dynamic)
    DrawingCanvas._paint_stroke(
        painter, stroke, dynamic.width(), dynamic.height()
    )
    painter.end()
    assert max(
        dynamic.pixelColor(x, 50).alpha() for x in range(dynamic.width())
    ) == 255


def test_legacy_polyline_sampling_is_cumulative_and_tessellation_invariant() -> None:
    from app.painter_legacy_brush import sample_polyline_uniform

    sparse, sparse_workload = sample_polyline_uniform([(0.0, 0.0), (10.0, 0.0)], 3.0)
    dense, dense_workload = sample_polyline_uniform(
        [(0.0, 0.0), (2.0, 0.0), (7.0, 0.0), (10.0, 0.0)], 3.0
    )

    assert sparse == dense
    assert [sample[0] for sample in sparse] == [0.0, 3.0, 6.0, 9.0, 10.0]
    assert sparse_workload == dense_workload


def test_legacy_polyline_sampling_uses_full_path_bounded_resampling() -> None:
    from app.painter_legacy_brush import sample_polyline_uniform

    samples, workload = sample_polyline_uniform(
        [(0.0, 0.0), (10.0, 0.0)], 0.01, sample_budget=4
    )

    assert [sample[0] for sample in samples] == pytest.approx(
        [0.0, 10.0 / 3.0, 20.0 / 3.0, 10.0]
    )
    assert workload == {
        "policy": "uniform_full_path_resampling_v1",
        "requested_spacing_px": 0.01,
        "effective_spacing_px": 10.0 / 3.0,
        "estimated_samples": 1001,
        "rendered_samples": 4,
        "sample_budget": 4,
        "degraded": True,
    }


@pytest.mark.parametrize("step", [0.0, -1.0, float("inf"), float("nan")])
def test_legacy_polyline_sampling_rejects_invalid_spacing(step: float) -> None:
    from app.painter_legacy_brush import sample_polyline_uniform

    with pytest.raises(ValueError, match="finite and positive"):
        sample_polyline_uniform([(0.0, 0.0), (1.0, 0.0)], step)


@pytest.mark.parametrize("budget", [True, 4.5, "4", None])
def test_legacy_polyline_sampling_requires_strict_integer_budget(budget) -> None:
    from app.painter_legacy_brush import sample_polyline_uniform

    with pytest.raises(TypeError, match="integer"):
        sample_polyline_uniform(
            [(0.0, 0.0), (1.0, 0.0)], 0.5, sample_budget=budget
        )


@pytest.mark.parametrize(
    "points",
    [
        [(0.0, 0.0), (float("inf"), 1.0)],
        [(0.0, float("nan")), (1.0, 1.0)],
    ],
)
def test_legacy_polyline_sampling_rejects_nonfinite_points(points) -> None:
    from app.painter_legacy_brush import sample_polyline_uniform

    with pytest.raises(ValueError, match="points must be finite"):
        sample_polyline_uniform(points, 0.5)


def test_legacy_noise_is_repeatable_and_style_specific() -> None:
    from app.painter_legacy_brush import deterministic_unit, stable_style_seed

    first = deterministic_unit(stable_style_seed("graphite_pencil"), 17)
    assert first == deterministic_unit(stable_style_seed("graphite_pencil"), 17)
    assert first != deterministic_unit(stable_style_seed("charcoal_vine"), 17)
    assert 0.0 <= first <= 1.0


def test_designer_profiles_cannot_shadow_public_brush_controls() -> None:
    from app.painter_brush_catalog import (
        DESIGNER_BRUSH_RENDER_PROFILES,
        DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS,
    )

    assert DESIGNER_BRUSH_RENDER_PROFILES
    for profile in DESIGNER_BRUSH_RENDER_PROFILES.values():
        assert DESIGNER_PROFILE_PUBLIC_CONTROL_KEYS.isdisjoint(profile)


def test_m51_measurement_passes_published_invariants() -> None:
    import json
    from pathlib import Path

    from tools.measure_painter_legacy_brush import ROOT, main

    assert main() == 0
    report = json.loads(
        (
            Path(ROOT)
            / "debugCapture"
            / "painter"
            / "evidence_audit"
            / "m51_legacy_brush.json"
        ).read_text(encoding="utf-8")
    )
    assert report["scope"] == "painting_only_ui_design_excluded"
    assert report["claim_boundary"]["external_brush_engine_pixel_parity_claim"] is False
    assert report["parity_hashes"]["preview_export_max_delta_lsb"] == 1
    assert report["passed"] is True
    assert all(report["checks"].values())


def test_retained_stroke_indices_clamp_to_existing_prefix_or_insert_boundary() -> None:
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from app.drawing import DrawingCanvas, Stroke

    app = QApplication.instance() or QApplication([])
    canvas = DrawingCanvas()
    first = Stroke(points=[(0.1, 0.1)])
    before = Stroke(points=[(0.2, 0.2)])
    after = Stroke(points=[(0.3, 0.3)])
    canvas.set_strokes_snapshot([first])
    canvas.insert_stroke_direct(-100, before)
    canvas.insert_stroke_direct(100, after)
    assert canvas._embedded_strokes == [before, first, after]

    canvas._current_points = [QPointF(10.0, 20.0), QPointF(30.0, 40.0)]
    canvas._current_pressure = [0.25, 0.75]
    canvas._current_tilt = [0.0, 0.0]
    canvas._current_tilt_x = [0.0, 0.0]
    canvas._current_tilt_y = [0.0, 0.0]
    canvas._current_rotation = [0.5, 0.5]
    canvas._current_tangential_pressure = [0.0, 0.0]
    canvas._current_load = [1.0, 1.0]
    low = canvas._current_stroke_snapshot(100, 100, start=-100)
    high = canvas._current_stroke_snapshot(100, 100, start=100)
    assert low.brush_sample_offset == 0
    assert low.points == [(0.1, 0.2), (0.3, 0.4)]
    assert high.brush_sample_offset == 1
    assert high.points == [(0.3, 0.4)]
    canvas.close()


def test_retained_polyline_offset_uses_endpoint_safe_neighbors() -> None:
    from app.drawing import _offset_polyline_xy

    assert _offset_polyline_xy([(0.0, 0.0), (10.0, 0.0)], 2.0) == [
        (0.0, 2.0),
        (10.0, 2.0),
    ]
