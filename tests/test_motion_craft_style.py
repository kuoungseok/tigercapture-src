import numpy as np
from PySide6.QtGui import QColor, QImage

from app.motion_designer.craft_style import (
    CRAFT_STYLE_CONTRACT,
    make_craft_style_effect,
    normalize_craft_style,
)
from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.schema import MotionEffectRef


def _pixels(image: QImage) -> np.ndarray:
    straight = image.convertToFormat(QImage.Format_RGBA8888)
    rows = np.frombuffer(straight.constBits(), dtype=np.uint8).reshape(
        straight.height(),
        straight.bytesPerLine(),
    )
    return rows[:, : straight.width() * 4].reshape(
        straight.height(),
        straight.width(),
        4,
    ).copy()


def _quiet_settings(**overrides) -> dict:
    return {
        "grain_amount": 0.0,
        "weave_x": 0.0,
        "weave_y": 0.0,
        "weave_rotation": 0.0,
        "flicker_amount": 0.0,
        "dust_amount": 0.0,
        "scratch_amount": 0.0,
        "misregistration": 0.0,
        "halation_amount": 0.0,
        "warmth": 0.0,
        "vhs_amount": 0.0,
        "edge_roughness": 0.0,
        "edge_fiber_amount": 0.0,
        **overrides,
    }


def test_craft_style_contract_round_trips_and_clamps_values() -> None:
    values = normalize_craft_style({
        "amount": 9,
        "grain_size": -5,
        "grain_chroma": 4,
        "dust_lifetime": 0,
        "scratch_direction": 900,
        "edge_fiber_length": 1000,
        "flicker_warmth": -4,
        "seed": -12,
    }, preset="handmade")
    assert values["amount"] == 1.0
    assert values["grain_size"] == 1.0
    assert values["grain_chroma"] == 1.0
    assert values["dust_lifetime"] == 0.04
    assert values["scratch_direction"] == 180.0
    assert values["edge_fiber_length"] == 64.0
    assert values["flicker_warmth"] == -1.0
    assert values["seed"] == 0

    effect = make_craft_style_effect(values, preset="handmade")
    restored = MotionEffectRef.from_dict(effect.to_dict())
    assert restored.kind == "craft_style"
    assert restored.metadata["contract"] == CRAFT_STYLE_CONTRACT
    assert restored.metadata["preset"] == "handmade"
    assert restored.params["grain_size"].default == 1.0


def test_craft_color_grain_separates_channels_without_changing_alpha() -> None:
    source = QImage(80, 48, QImage.Format_RGBA8888)
    source.fill(QColor(128, 128, 128, 210))
    mono = apply_effects(
        source,
        [make_craft_style_effect(_quiet_settings(
            grain_amount=0.8,
            grain_chroma=0.0,
            seed=17,
        ))],
        0,
    )
    color = apply_effects(
        source,
        [make_craft_style_effect(_quiet_settings(
            grain_amount=0.8,
            grain_chroma=1.0,
            seed=17,
        ))],
        0,
    )
    mono_pixels = _pixels(mono)
    color_pixels = _pixels(color)
    assert np.array_equal(mono_pixels[..., 0], mono_pixels[..., 1])
    assert np.array_equal(mono_pixels[..., 1], mono_pixels[..., 2])
    assert np.count_nonzero(color_pixels[..., 0] != color_pixels[..., 1]) > 100
    assert np.array_equal(color_pixels[..., 3], _pixels(source)[..., 3])


def test_craft_dust_lifetime_holds_artifacts_then_changes() -> None:
    source = QImage(96, 64, QImage.Format_RGBA8888)
    source.fill(QColor("#707070"))
    effect = make_craft_style_effect(_quiet_settings(
        dust_amount=0.5,
        dust_lifetime=0.5,
        seed=123,
        loop_period=2.0,
    ))
    early = _pixels(apply_effects(source, [effect], 100))
    held = _pixels(apply_effects(source, [effect], 450))
    changed = _pixels(apply_effects(source, [effect], 650))
    assert np.array_equal(early, held)
    assert np.count_nonzero(early != changed) > 100


def test_craft_fibrous_edge_is_deterministic_and_keeps_interior() -> None:
    source = QImage(96, 64, QImage.Format_RGBA8888)
    source.fill(QColor("#00000000"))
    for y in range(12, 52):
        for x in range(16, 80):
            source.setPixelColor(x, y, QColor("#cf7d49"))
    effect = make_craft_style_effect(_quiet_settings(
        edge_fiber_amount=1.0,
        edge_fiber_length=11.0,
        seed=91,
    ))
    first = _pixels(apply_effects(source, [effect], 0))
    later = _pixels(apply_effects(source, [effect], 900))
    original = _pixels(source)
    assert np.array_equal(first, later)
    assert first[32, 48, 3] == 255
    assert np.count_nonzero(first[..., 3] != original[..., 3]) > 0
