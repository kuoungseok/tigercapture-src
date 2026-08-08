from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtGui import QColor, QImage

from app.actions.registry import ActionRegistry
from app.motion_designer.mask_adapter import apply_masks
from app.motion_designer.mask_matting import refine_alpha_matte
from app.motion_designer.schema import AnimatedProperty, MotionLayer, MotionMaskRef


def _opaque_image(width: int = 32, height: int = 24) -> QImage:
    image = QImage(width, height, QImage.Format_RGBA8888_Premultiplied)
    image.fill(QColor(240, 180, 120, 255))
    return image


def _rect_mask(mode: str) -> MotionMaskRef:
    return MotionMaskRef(
        kind="rectangle",
        mode=mode,
        params={
            "x": AnimatedProperty(default=0.0),
            "y": AnimatedProperty(default=0.0),
            "width": AnimatedProperty(default=16.0),
            "height": AnimatedProperty(default=24.0),
        },
    )


def test_m17_garbage_and_holdout_modes_remove_the_marked_region() -> None:
    for mode in ("garbage", "holdout"):
        layer = MotionLayer(masks=[_rect_mask(mode)])
        output = apply_masks(_opaque_image(), layer, 0.0)
        assert output.pixelColor(4, 12).alpha() == 0
        assert output.pixelColor(27, 12).alpha() == 255


def test_m17_edge_aware_matting_preserves_semantic_soft_alpha() -> None:
    rgb = np.full((24, 32, 3), 128, dtype=np.uint8)
    alpha = np.zeros((24, 32), dtype=np.uint8)
    alpha[:, 8:12] = 48
    alpha[:, 12:16] = 128
    alpha[:, 16:20] = 220
    alpha[:, 20:24] = 255

    refined = refine_alpha_matte(rgb, alpha, mode="edge_aware")

    assert refined.soft_pixel_ratio > 0.2
    assert 0 < int(refined.alpha[12, 9]) < 128
    assert 128 <= int(refined.alpha[12, 18]) < 255
    assert int(refined.alpha[12, 22]) == 255


def test_m17_action_contract_is_complete() -> None:
    action_ids = {row["id"] for row in ActionRegistry().list_actions()}
    assert {
        "motion.matte.object.select",
        "motion.matte.object.refine",
        "motion.matte.propagate",
        "motion.matte.correction.set",
        "motion.matte.freeze",
        "motion.matte.assign",
        "motion.matte.diagnostics",
        "motion.key.create",
        "motion.key.update",
        "motion.key.diagnostics",
    } <= action_ids
