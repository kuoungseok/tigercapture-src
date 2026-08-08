from __future__ import annotations

import numpy as np

from app.motion_designer.background_inpainting import inpaint_background
from app.motion_designer.typography_reconstruction import (
    TypographyRegion,
    native_typography_mask,
    typography_source_params,
)


def test_large_local_inpaint_limits_camera_travel() -> None:
    rgb = np.zeros((120, 200, 3), dtype=np.uint8)
    rgb[:, :100] = (28, 64, 110)
    rgb[:, 100:] = (170, 88, 32)
    mask = np.zeros((120, 200), dtype=np.uint8)
    mask[20:110, 45:155] = 255
    result = inpaint_background(
        rgb,
        mask,
        transparent_source=False,
        mode="fast",
    )
    assert result.image.shape == rgb.shape
    assert result.provider == "opencv_multiscale_ns"
    assert result.coverage > 0.18
    assert result.max_camera_travel_ratio <= 0.04
    assert result.warnings


def test_transparent_source_produces_transparent_background() -> None:
    rgb = np.full((80, 100, 3), 128, dtype=np.uint8)
    mask = np.full((80, 100), 255, dtype=np.uint8)
    result = inpaint_background(
        rgb,
        mask,
        transparent_source=True,
        mode="auto",
    )
    assert result.image.shape == (80, 100, 4)
    assert np.count_nonzero(result.image[:, :, 3]) == 0
    assert result.provider == "transparent_canvas"


def test_only_native_eligible_typography_is_removed_from_raster() -> None:
    regions = [
        TypographyRegion(
            text="MOTION",
            bbox=(10, 10, 80, 20),
            confidence=0.95,
            role="headline",
            native_eligible=True,
        ),
        TypographyRegion(
            text="uncertain",
            bbox=(20, 55, 60, 12),
            confidence=0.55,
            role="body",
            native_eligible=False,
        ),
    ]
    mask = native_typography_mask(120, 90, regions)
    assert np.count_nonzero(mask[8:34, 8:94]) > 0
    assert np.count_nonzero(mask[50:72, 15:85]) == 0
    params = typography_source_params(regions[0])
    assert params["text"] == "MOTION"
    assert params["font_weight"] == 800
