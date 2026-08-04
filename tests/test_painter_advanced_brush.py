from __future__ import annotations

import numpy as np


def test_dual_brush_deposits_only_primary_secondary_intersection() -> None:
    from app.painter_advanced_brush import dual_brush_intersection

    primary = np.asarray([[0.0, 0.5, 1.0], [1.0, 0.5, 0.0]], dtype=np.float32)
    secondary = np.asarray([[1.0, 1.0, 0.5], [0.25, 0.0, 1.0]], dtype=np.float32)
    combined = dual_brush_intersection(primary, secondary, enabled=True)
    np.testing.assert_array_equal(combined, primary * secondary)
    np.testing.assert_array_equal(
        dual_brush_intersection(primary, secondary, enabled=False),
        primary,
    )


def test_noise_field_is_replay_deterministic_from_persisted_seed() -> None:
    from app.painter_advanced_brush import deterministic_noise_field

    first = deterministic_noise_field(17, 11, seed=781, scale=0.75)
    replay = deterministic_noise_field(17, 11, seed=781, scale=0.75)
    different = deterministic_noise_field(17, 11, seed=782, scale=0.75)
    np.testing.assert_array_equal(first, replay)
    assert not np.array_equal(first, different)
    assert first.shape == (11, 17)
    assert bool(np.isfinite(first).all())
    assert float(first.min()) >= 0.0
    assert float(first.max()) <= 1.0


def test_wet_edges_are_stateful_pooling_and_disabled_is_byte_identical() -> None:
    from app.painter_advanced_brush import WetEdgeState

    mask = np.zeros((7, 7), dtype=np.float32)
    mask[2:5, 2:5] = 1.0
    state = WetEdgeState.blank(width=7, height=7)
    state.deposit(mask, pigment=0.5, water=1.0)
    pigment_before = state.pigment.copy()
    disabled = state.composite_alpha(pooling=1.0, enabled=False)
    np.testing.assert_array_equal(disabled, pigment_before)

    pooled = state.composite_alpha(pooling=1.0, enabled=True)
    assert pooled[2, 3] > pooled[3, 3]
    water_before = state.water.copy()
    state.dry(0.5)
    assert bool(np.all(state.water <= water_before))
    np.testing.assert_array_equal(state.pigment, pigment_before)
    state.dry(1.0)
    assert not bool(np.any(state.water))


def test_protect_texture_uses_document_pattern_and_scale_across_presets() -> None:
    from app.painter_advanced_brush import resolve_texture_settings

    document_texture = {
        "pattern_id": "paper/cold-press",
        "scale": 0.625,
        "offset": [0.125, -0.25],
    }
    first = {
        "protect_texture": True,
        "texture": {"pattern_id": "preset/a", "scale": 2.0, "offset": [0.0, 0.0]},
    }
    second = {
        "protect_texture": True,
        "texture": {"pattern_id": "preset/b", "scale": 0.25, "offset": [0.5, 0.5]},
    }
    assert resolve_texture_settings(first, document_texture) == document_texture
    assert resolve_texture_settings(second, document_texture) == document_texture

    unprotected = dict(second)
    unprotected["protect_texture"] = False
    assert resolve_texture_settings(unprotected, document_texture) == second["texture"]


def test_advanced_dab_alpha_pipeline_is_disabled_exact_and_replay_stable() -> None:
    from app.painter_advanced_brush import advanced_dab_alphas

    base = np.linspace(0.2, 0.9, 17, dtype=np.float32)
    np.testing.assert_array_equal(
        advanced_dab_alphas(base, {}, stroke_seed=8123),
        base,
    )

    settings = {
        "dual_brush_enabled": True,
        "dual_brush_seed": 41,
        "dual_brush_strength": 80,
        "noise_enabled": True,
        "noise_seed": 73,
        "noise_scale": 65,
        "wet_edges_enabled": True,
        "wet_edge_pooling": 70,
        "wet_edge_pigment": 90,
        "wet_edge_water": 85,
    }
    first = advanced_dab_alphas(base, settings, stroke_seed=8123)
    replay = advanced_dab_alphas(base, settings, stroke_seed=8123)
    np.testing.assert_array_equal(first, replay)
    assert not np.array_equal(first, base)
    assert bool(np.isfinite(first).all())
    assert float(first.min()) >= 0.0
    assert float(first.max()) <= 1.0


def test_zero_strength_dual_and_noise_are_neutral_not_transparent() -> None:
    from app.painter_advanced_brush import advanced_dab_alphas

    base = np.linspace(0.15, 0.95, 13, dtype=np.float32)
    np.testing.assert_array_equal(
        advanced_dab_alphas(
            base,
            {"dual_brush_enabled": True, "dual_brush_strength": 0},
            stroke_seed=12,
        ),
        base,
    )
    np.testing.assert_array_equal(
        advanced_dab_alphas(
            base,
            {"noise_enabled": True, "noise_scale": 0},
            stroke_seed=12,
        ),
        base,
    )


def test_protected_texture_changes_real_dab_alpha_from_document_settings() -> None:
    from app.painter_advanced_brush import advanced_dab_alphas

    base = np.ones(23, dtype=np.float32)
    document_texture = {
        "pattern_id": "paper/cold-press",
        "strength": 72,
        "scale": 0.625,
        "offset": [0.125, -0.25],
    }
    first = advanced_dab_alphas(
        base,
        {
            "protect_texture": True,
            "texture": {"pattern_id": "preset/a", "strength": 10},
            "document_texture": document_texture,
        },
        stroke_seed=91,
    )
    second = advanced_dab_alphas(
        base,
        {
            "protect_texture": True,
            "texture": {"pattern_id": "preset/b", "strength": 100},
            "document_texture": document_texture,
        },
        stroke_seed=91,
    )
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, base)
    changed_scale = advanced_dab_alphas(
        base,
        {
            "protect_texture": True,
            "document_texture": {**document_texture, "scale": 1.25},
        },
        stroke_seed=91,
    )
    assert not np.array_equal(first, changed_scale)


def test_advanced_brush_settings_change_actual_painter_render_and_replay() -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter

    from app.drawing import DrawingCanvas, Stroke

    def render(dynamics: dict[str, object]) -> QImage:
        image = QImage(96, 48, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        stroke = Stroke(
            points=[(0.1, 0.5), (0.9, 0.5)],
            color=(44, 116, 220),
            width_px=15,
            brush_spacing=18,
            brush_seed=811,
            brush_dynamics={"enabled": True, **dynamics},
        )
        painter = QPainter(image)
        try:
            DrawingCanvas._paint_stroke(painter, stroke, 96, 48)
        finally:
            painter.end()
        return image

    baseline = render({})
    advanced_settings = {
        "dual_brush_enabled": True,
        "dual_brush_seed": 17,
        "dual_brush_strength": 90,
        "noise_enabled": True,
        "noise_seed": 19,
        "noise_scale": 60,
        "wet_edges_enabled": True,
        "wet_edge_pooling": 65,
        "wet_edge_pigment": 100,
        "wet_edge_water": 80,
        "protect_texture": True,
        "document_texture": {
            "pattern_id": "paper/cold-press",
            "strength": 55,
        },
    }
    advanced = render(advanced_settings)
    replay = render(advanced_settings)
    assert advanced != baseline
    assert replay == advanced
    assert advanced.pixelColor(48, 24) != QColor(Qt.GlobalColor.transparent)
