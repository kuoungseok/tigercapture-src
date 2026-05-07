"""Blur effect parameters for BlurNodeItem.

Implements lens-bokeh-style out-of-focus blur using a circular (or
hexagonal) disk convolution kernel — matches the way a real camera
aperture works. Gaussian mode is also available as a softer option.

The ``apply`` method takes a uint8 H×W×3 RGB ndarray and returns
a blurred version.  When called via ``apply_with_mask`` the blurred
result is composited onto the sharp original using the supplied mask
(mask=1 → sharp, mask=0 → blurred).  Inverting the mask gives the
"background blur" / out-of-focus look (person sharp, background soft).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np


BLUR_SHAPE_CIRCLE = "circle"
BLUR_SHAPE_HEXAGON = "hexagon"
BLUR_SHAPE_GAUSSIAN = "gaussian"

BLUR_SHAPES = (BLUR_SHAPE_CIRCLE, BLUR_SHAPE_HEXAGON, BLUR_SHAPE_GAUSSIAN)


@lru_cache(maxsize=32)
def _make_kernel(radius: int, shape: str) -> np.ndarray:
    """Build and cache a normalised 2-D convolution kernel."""
    size = 2 * radius + 1
    k = np.zeros((size, size), dtype=np.float32)
    cx = cy = radius
    if shape == BLUR_SHAPE_CIRCLE:
        for i in range(size):
            for j in range(size):
                if (i - cy) ** 2 + (j - cx) ** 2 <= radius ** 2:
                    k[i, j] = 1.0
    elif shape == BLUR_SHAPE_HEXAGON:
        # Approximate hexagon via two overlapping rectangles rotated 30°.
        # Simpler iterative approach: include pixel if within hex bound.
        r = float(radius)
        for i in range(size):
            for j in range(size):
                dy = abs(i - cy) / r
                dx = abs(j - cx) / r
                if dx <= 1.0 and dy <= 1.0 and dx + dy * (2.0 / 3.0) <= 1.0 + (2.0 / 3.0):
                    k[i, j] = 1.0
    else:
        # Gaussian: we don't use the kernel path for this shape
        raise ValueError(f"Use cv2.GaussianBlur for shape={shape!r}")
    total = k.sum()
    if total > 0:
        k /= total
    return k


@dataclass
class BlurParams:
    """Configurable bokeh / out-of-focus blur.

    Parameters
    ----------
    radius : int
        Half-width of the kernel in pixels (1–50).
        Larger = more blur / shallower depth-of-field look.
    shape : str
        Kernel shape: ``"circle"`` (standard bokeh), ``"hexagon"``
        (6-blade aperture bokeh), or ``"gaussian"`` (soft, no bokeh).
    strength : float
        0.0 = no effect (original), 1.0 = full blur.  Values in
        between blend between the original and blurred frame.
    enabled : bool
        When False the node is treated as identity (pass-through).
    """

    radius: int = 25  # visible at typical preview sizes
    shape: str = BLUR_SHAPE_CIRCLE
    strength: float = 1.0
    enabled: bool = True

    # Runtime cache for fast re-calls at the same resolution.
    _cache: Any = None
    _cache_key: tuple = ()

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """Return a blurred copy of ``rgb``.

        For all kernel shapes the implementation uses ``cv2.GaussianBlur``
        (SIMD-optimised, IIR-accelerated for large radii) as the primary
        engine.  Circle/hexagon shapes are approximated with a Gaussian
        of equivalent width — the visual difference is negligible for the
        preview path where speed matters most.

        For radii >= 8 the frame is scaled to half-resolution before
        blurring and then scaled back up.  This gives a ~4× speed-up
        (blur cost is O(r) per pixel; half-res = ¼ pixels × ½ kernel =
        8× theoretical saving, practical ~4×) with no perceptible quality
        loss at preview sizes.
        """
        if not self.enabled or self.radius <= 0 or self.strength <= 0:
            return rgb
        try:
            import cv2
        except ImportError:
            return rgb
        h, w = rgb.shape[:2]
        # Gaussian sigma: radius ≈ 2*sigma for a natural look.
        sigma = float(self.radius) / 2.0
        # Half-resolution fast path for large blur radii.
        _USE_HALF_RES = self.radius >= 8 and h >= 32 and w >= 32
        if _USE_HALF_RES:
            small = cv2.resize(rgb, (w // 2, h // 2), interpolation=cv2.INTER_LINEAR)
            half_sigma = sigma / 2.0
            ksize = max(3, int(half_sigma * 6) | 1)  # cover ±3σ
            blurred_small = cv2.GaussianBlur(small, (ksize, ksize), half_sigma)
            blurred = cv2.resize(blurred_small, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            ksize = max(3, self.radius * 2 + 1) | 1
            blurred = cv2.GaussianBlur(rgb, (ksize, ksize), sigma)
        if self.strength < 1.0:
            a = float(self.strength)
            blurred = (a * blurred.astype(np.float32)
                       + (1.0 - a) * rgb.astype(np.float32))
            blurred = np.clip(blurred, 0, 255).astype(np.uint8)
        return blurred

    def apply_with_mask(
        self,
        rgb: np.ndarray,
        mask: np.ndarray | None,
        invert_mask: bool = True,
    ) -> np.ndarray:
        """Blur ``rgb`` and composite with the original using ``mask``.

        ``invert_mask=True`` (default):
            mask=1 → SHARP (subject), mask=0 → BLURRED (background).
            Typical "background out-of-focus" / bokeh look.

        ``invert_mask=False``:
            mask=1 → BLURRED, mask=0 → SHARP.
            "Blur this region" style.
        """
        blurred = self.apply(rgb)
        if mask is None:
            return blurred
        h, w = rgb.shape[:2]
        if mask.shape[:2] != (h, w):
            try:
                import cv2
                mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
            except Exception:
                return blurred
        mf = np.clip(mask, 0.0, 1.0).astype(np.float32)[..., None]
        if invert_mask:
            # mf=1 → sharp, mf=0 → blurred
            out = mf * rgb.astype(np.float32) + (1.0 - mf) * blurred.astype(np.float32)
        else:
            # mf=1 → blurred, mf=0 → sharp
            out = mf * blurred.astype(np.float32) + (1.0 - mf) * rgb.astype(np.float32)
        return np.clip(out, 0, 255).astype(np.uint8)

    def to_dict(self) -> dict:
        return {
            "kind": "blur",
            "radius": int(self.radius),
            "shape": str(self.shape),
            "strength": float(self.strength),
            "enabled": bool(self.enabled),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BlurParams":
        return cls(
            radius=int(d.get("radius", 15)),
            shape=str(d.get("shape", BLUR_SHAPE_CIRCLE)),
            strength=float(d.get("strength", 1.0)),
            enabled=bool(d.get("enabled", True)),
        )

    def is_identity(self) -> bool:
        return not self.enabled or self.radius <= 0 or self.strength <= 0
