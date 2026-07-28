from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QColor, QImage

from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.painterly_look import (
    PAINTERLY_LOOK_CONTRACT,
    make_painterly_look_effect,
    normalize_painterly_look,
)
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


def _source() -> QImage:
    image = QImage(96, 64, QImage.Format_RGBA8888)
    image.fill(QColor("#00000000"))
    for y in range(8, 56):
        for x in range(10, 86):
            image.setPixelColor(
                x,
                y,
                QColor(
                    int(25 + x * 2.2),
                    int(35 + y * 3.0),
                    int(210 - x * 1.3),
                    220,
                ),
            )
    return image


def test_painterly_contract_clamps_and_round_trips() -> None:
    values = normalize_painterly_look({
        "amount": 7,
        "color_levels": 1,
        "edge_strength": 9,
        "seed": -4,
    }, preset="ink")
    assert values["amount"] == 1.0
    assert values["color_levels"] == 2.0
    assert values["edge_strength"] == 2.0
    assert values["seed"] == 0
    effect = make_painterly_look_effect(values, preset="ink")
    restored = MotionEffectRef.from_dict(effect.to_dict())
    assert restored.kind == "painterly_look"
    assert restored.metadata["contract"] == PAINTERLY_LOOK_CONTRACT
    assert restored.metadata["temporal_lock"] is True


def test_painterly_presets_are_stable_distinct_and_alpha_preserving() -> None:
    source = _source()
    source_pixels = _pixels(source)
    outputs = {}
    for preset in ("realistic", "toon", "painted", "ink", "paper"):
        effect = make_painterly_look_effect({"seed": 88}, preset=preset)
        first = _pixels(apply_effects(source, [effect], 0))
        later = _pixels(apply_effects(source, [effect], 875))
        assert np.array_equal(first, later)
        assert np.array_equal(first[..., 3], source_pixels[..., 3])
        outputs[preset] = first
    assert all(
        np.count_nonzero(outputs["realistic"] != outputs[preset]) > 100
        for preset in ("toon", "painted", "ink", "paper")
    )


def test_painterly_texture_projection_is_rendered(tmp_path) -> None:
    source = _source()
    texture = QImage(8, 8, QImage.Format_RGBA8888)
    texture.fill(QColor("#505050"))
    texture_path = tmp_path / "paper.png"
    assert texture.save(str(texture_path))
    effect = make_painterly_look_effect(preset="paper")
    effect.metadata["projected_texture"] = {
        "uri": str(texture_path),
        "blend_mode": "multiply",
        "opacity": 0.8,
        "revision": str(texture_path.stat().st_mtime_ns),
    }
    rendered = _pixels(apply_effects(source, [effect], 0))
    baseline = _pixels(apply_effects(
        source,
        [make_painterly_look_effect(preset="paper")],
        0,
    ))
    assert rendered[..., :3].mean() < baseline[..., :3].mean()


def test_painterly_bounded_working_surface_restores_exact_alpha() -> None:
    source = QImage(800, 450, QImage.Format_RGBA8888)
    source.fill(QColor("#00000000"))
    for y in range(60, 390):
        alpha = min(255, max(0, (y - 60) * 2))
        for x in range(100, 700):
            source.setPixelColor(x, y, QColor(80, 130, 210, alpha))
    effect = make_painterly_look_effect(
        {"working_limit": 320, "seed": 17},
        preset="painted",
    )
    rendered = apply_effects(source, [effect], 0)
    assert rendered.size() == source.size()
    assert np.array_equal(_pixels(rendered)[..., 3], _pixels(source)[..., 3])
