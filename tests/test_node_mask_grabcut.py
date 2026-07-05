from __future__ import annotations

import importlib.util

import numpy as np
import pytest


cv2_available = importlib.util.find_spec("cv2") is not None


@pytest.mark.skipif(not cv2_available, reason="OpenCV is required")
def test_refine_grabcut_mask_reduces_loose_rect_spill():
    from app.node_mask import refine_grabcut_mask

    h, w = 240, 360
    rng = np.random.default_rng(1)
    rgb = np.full((h, w, 3), 235, dtype=np.uint8)
    rgb = np.clip(rgb + rng.normal(0, 6, rgb.shape), 0, 255).astype(np.uint8)

    # Dark game-character-like subject on a bright snow-like background.
    rgb[95:125, 198:213] = 45
    rgb[120:190, 190:220] = 35
    rgb[170:215, 180:198] = 38
    rgb[170:215, 215:232] = 38
    rgb[185:205, 140:205] = 70  # shadow/ground spill candidate

    rect = (0.25, 0.20, 0.55, 0.70)
    x = int(rect[0] * w)
    y = int(rect[1] * h)
    rw = int(rect[2] * w)
    rh = int(rect[3] * h)
    raw = np.zeros((h, w), dtype=np.uint8)
    raw[y:y + rh, x:x + rw] = 255

    refined, info = refine_grabcut_mask(rgb, raw, rect)

    assert info["quality"] == "seed_refined"
    assert info["coverage"] < 0.30
    assert refined[145, 205] == 255
    assert refined[y + 10, x + 10] == 0


@pytest.mark.skipif(not cv2_available, reason="OpenCV is required")
def test_grabcut_from_rect_returns_info():
    from app.node_mask import grabcut_from_rect

    rgb = np.full((120, 160, 3), 230, dtype=np.uint8)
    rgb[48:92, 70:94] = 30
    mask, info = grabcut_from_rect(
        rgb,
        (0.20, 0.20, 0.65, 0.65),
        iterations=2,
        return_info=True,
    )

    assert mask is not None
    assert isinstance(info, dict)
    assert "suggestion" in info
