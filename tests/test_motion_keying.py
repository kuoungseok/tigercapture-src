from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from app.actions.registry import ActionRegistry
from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.keying import (
    KEYER_CONTRACT,
    apply_keyer_rgba,
)
from app.motion_designer.schema import (
    AnimatedProperty,
    MotionComposition,
    MotionEffectRef,
    MotionLayer,
    SourceRef,
)
from app.motion_designer.validation import validate_composition


def _fixture() -> np.ndarray:
    rgba = np.zeros((80, 120, 4), dtype=np.uint8)
    rgba[..., 1] = 255
    rgba[..., 3] = 255
    rgba[20:60, 35:85, :3] = [220, 30, 30]
    return rgba


def _qimage(rgba: np.ndarray) -> QImage:
    return QImage(
        rgba.data,
        rgba.shape[1],
        rgba.shape[0],
        rgba.strides[0],
        QImage.Format_RGBA8888,
    ).copy()


def test_chroma_key_preserves_subject_and_removes_green_with_soft_edges() -> None:
    result = apply_keyer_rgba(
        _fixture(),
        "chroma_key",
        {
            "key_color": "#00ff00",
            "similarity": 0.25,
            "softness": 0.12,
            "feather": 1.5,
            "despill": 0.8,
        },
    )
    assert result.diagnostics["contract"] == KEYER_CONTRACT
    assert result.rgba[5, 5, 3] < 5
    assert result.rgba[40, 60, 3] > 250
    assert result.diagnostics["transparent_ratio"] > 0.5
    assert result.diagnostics["soft_ratio"] > 0.0


def test_luma_and_difference_key_create_expected_alpha() -> None:
    rgba = np.full((20, 30, 4), 255, dtype=np.uint8)
    rgba[:, :15, :3] = 0
    luma = apply_keyer_rgba(
        rgba,
        "luma_key",
        {"threshold": 0.5, "softness": 0.05},
    ).rgba
    assert luma[10, 4, 3] == 0
    assert luma[10, 24, 3] == 255

    reference = np.zeros((20, 30, 3), dtype=np.uint8)
    current = np.zeros((20, 30, 4), dtype=np.uint8)
    current[..., 3] = 255
    current[5:15, 10:20, :3] = 255
    difference = apply_keyer_rgba(
        current,
        "difference_key",
        {"threshold": 0.1, "softness": 0.05},
        reference_rgb=reference,
    ).rgba
    assert difference[1, 1, 3] == 0
    assert difference[10, 15, 3] == 255


def test_effect_adapter_and_key_actions_share_the_same_alpha_path() -> None:
    QApplication.instance() or QApplication([])
    effect = MotionEffectRef(
        kind="chroma_key",
        params={
            "key_color": AnimatedProperty(default="#00ff00"),
            "similarity": AnimatedProperty(default=0.25),
            "softness": AnimatedProperty(default=0.1),
        },
    )
    image = apply_effects(_qimage(_fixture()), [effect], 0)
    assert image.pixelColor(5, 5).alpha() < 5
    assert image.pixelColor(60, 40).alpha() > 250

    class Owner:
        def __init__(self) -> None:
            self._motion_compositions = {}

    registry = ActionRegistry(Owner())
    created = registry.execute(
        "motion.composition.create",
        {"duration_ms": 1000, "width": 120, "height": 80},
    )
    composition_id = created.result["payload"]["composition"]["id"]
    layer = MotionLayer(
        id="plate",
        layer_type="shape",
        source=SourceRef(kind="shape", params={
            "shape": "rectangle",
            "width": 120,
            "height": 80,
            "fill": "#00ff00",
            "stroke_width": 0,
        }),
        out_ms=1000,
    )
    layer.transform.position.default = [60, 40]
    assert registry.execute(
        "motion.layer.add",
        {"composition_id": composition_id, "layer": layer.to_dict()},
    ).ok
    created_key = registry.execute(
        "motion.key.create",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "kind": "chroma_key",
            "params": {"similarity": 0.25},
        },
    )
    assert created_key.ok
    effect_id = created_key.result["effect"]["id"]
    diagnostics = registry.execute(
        "motion.key.diagnostics",
        {
            "composition_id": composition_id,
            "layer_id": layer.id,
            "effect_id": effect_id,
            "time_ms": 0,
        },
    )
    assert diagnostics.ok
    assert diagnostics.result["transparent_ratio"] > 0.9


def test_difference_key_without_reference_is_explicit_validation_error() -> None:
    layer = MotionLayer(
        layer_type="shape",
        effects=[MotionEffectRef(kind="difference_key")],
    )
    report = validate_composition(MotionComposition(layers=[layer]))
    assert any(
        issue.code == "difference_key_reference_missing"
        for issue in report.issues
    )
