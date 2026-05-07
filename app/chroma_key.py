"""Chroma key (green/blue screen) masking via HSV colour range."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class ChromaKeyParams:
    """HSV-based colour difference key."""
    enabled: bool = False
    # Key colour in HSV (hue 0-179, sat 0-255, val 0-255 — OpenCV scale)
    key_hue: int = 60        # green = 60
    key_sat: int = 120
    key_val: int = 120
    # Tolerance / softness
    hue_range: int = 30      # ±hue_range around key_hue
    sat_min: int = 60
    val_min: int = 60
    # Spill suppression (0=off, 1=full)
    spill_suppress: float = 0.3
    # Background replacement colour (None = transparent / black)
    bg_r: int = 0
    bg_g: int = 0
    bg_b: int = 0

    def is_identity(self) -> bool:
        return not self.enabled

    def apply(self, rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return (result_rgb, alpha_mask 0-255).
        alpha_mask=255 means opaque (not keyed), 0 means transparent (keyed out)."""
        import cv2
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        h, s, v = hsv[:,:,0], hsv[:,:,1], hsv[:,:,2]

        # Hue distance (circular)
        hue_diff = np.abs(h.astype(np.int16) - self.key_hue)
        hue_diff = np.minimum(hue_diff, 180 - hue_diff).astype(np.uint8)

        # Key mask: pixels within range are keyed out (alpha=0)
        in_range = (
            (hue_diff <= self.hue_range) &
            (s >= self.sat_min) &
            (v >= self.val_min)
        )

        # Soft edge: linearly fade over half the hue range
        soft = np.clip(
            1.0 - (self.hue_range - hue_diff.astype(np.float32)) / max(1, self.hue_range * 0.5),
            0.0, 1.0,
        )
        soft[~in_range] = 1.0
        alpha = (soft * 255).astype(np.uint8)

        # Spill suppression: reduce green channel in semi-transparent areas
        if self.spill_suppress > 0:
            result = rgb.copy().astype(np.float32)
            spill_mask = (1.0 - soft) * self.spill_suppress
            # Reduce green toward average of R and B
            avg_rb = (result[:,:,0] + result[:,:,2]) / 2.0
            result[:,:,1] = result[:,:,1] * (1 - spill_mask) + avg_rb * spill_mask
            result = np.clip(result, 0, 255).astype(np.uint8)
        else:
            result = rgb.copy()

        # Composite over background colour
        bg = np.array([self.bg_r, self.bg_g, self.bg_b], dtype=np.float32)
        a = alpha[:,:,None].astype(np.float32) / 255.0
        composited = (result.astype(np.float32) * a + bg * (1 - a))
        return np.clip(composited, 0, 255).astype(np.uint8), alpha

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ['enabled','key_hue','key_sat','key_val','hue_range',
                 'sat_min','val_min','spill_suppress','bg_r','bg_g','bg_b']}

    @classmethod
    def from_dict(cls, d: dict) -> "ChromaKeyParams":
        return cls(**{k: d[k] for k in d if hasattr(cls, k)})
