"""Chroma key (green/blue screen) masking via HSV colour range."""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional
import numpy as np


_CHROMA_LUT_CACHE: "OrderedDict[tuple, tuple[np.ndarray, np.ndarray]]" = OrderedDict()
_CHROMA_LUT_CACHE_LIMIT = 32


def _chroma_luts(key_hue: int, hue_range: int) -> tuple[np.ndarray, np.ndarray]:
    key = (int(key_hue), int(hue_range))
    cached = _CHROMA_LUT_CACHE.get(key)
    if cached is not None:
        _CHROMA_LUT_CACHE.move_to_end(key)
        return cached

    values_i = np.arange(256, dtype=np.int16)
    hue_diff = np.abs(values_i - int(key_hue))
    hue_diff = np.minimum(hue_diff, 180 - hue_diff).clip(0, 255).astype(np.uint8)

    denom = max(1.0, float(hue_range) * 0.5)
    values_f = np.arange(256, dtype=np.float32)
    soft = np.clip(1.0 - (float(hue_range) - values_f) / denom, 0.0, 1.0)
    alpha = np.clip(soft * 255.0, 0, 255).astype(np.uint8)

    _CHROMA_LUT_CACHE[key] = (hue_diff, alpha)
    _CHROMA_LUT_CACHE.move_to_end(key)
    while len(_CHROMA_LUT_CACHE) > _CHROMA_LUT_CACHE_LIMIT:
        _CHROMA_LUT_CACHE.popitem(last=False)
    return hue_diff, alpha


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
        h, s, v = cv2.split(hsv)

        hue_diff_lut, alpha_lut = _chroma_luts(self.key_hue, self.hue_range)
        hue_diff = cv2.LUT(h, hue_diff_lut)

        # Key mask: pixels within range are keyed out (alpha=0)
        hue_mask = cv2.inRange(hue_diff, 0, int(self.hue_range))
        sat_mask = cv2.inRange(s, int(self.sat_min), 255)
        val_mask = cv2.inRange(v, int(self.val_min), 255)
        key_mask = cv2.bitwise_and(
            cv2.bitwise_and(hue_mask, sat_mask),
            val_mask,
        )
        if cv2.countNonZero(key_mask) <= 0:
            alpha = np.full(h.shape, 255, dtype=np.uint8)
            return rgb, alpha

        # Soft edge: linearly fade over half the hue range
        alpha = cv2.LUT(hue_diff, alpha_lut)
        alpha = cv2.bitwise_or(alpha, cv2.bitwise_not(key_mask))

        # Most preview frames are almost entirely alpha==0 or alpha==255. Avoid
        # full-frame RGB blending and only run fixed-point spill/composite math
        # on soft-edge pixels.
        bg_u8 = np.array([self.bg_r, self.bg_g, self.bg_b], dtype=np.uint8)
        result = np.empty_like(rgb)
        result[:] = bg_u8
        opaque_mask = cv2.inRange(alpha, 255, 255)
        cv2.copyTo(rgb, opaque_mask, result)

        soft_mask = (alpha > 0) & (alpha < 255)
        if not np.any(soft_mask):
            return result, alpha

        pix = rgb[soft_mask]
        alpha_soft = alpha[soft_mask].astype(np.uint16)
        inv_alpha = (255 - alpha_soft).astype(np.uint16)
        spill = max(0.0, min(1.0, float(self.spill_suppress)))
        if spill > 0:
            pix = pix.copy()
            strength = (
                inv_alpha * int(round(spill * 256.0)) + 127
            ) // 255
            if np.any(strength):
                red = pix[:, 0].astype(np.uint16)
                green = pix[:, 1].astype(np.uint16)
                blue = pix[:, 2].astype(np.uint16)
                avg_rb = (red + blue + 1) // 2
                pix[:, 1] = (
                    (green * (256 - strength) + avg_rb * strength + 128) // 256
                ).astype(np.uint8)

        bg_u16 = bg_u8.astype(np.uint16)
        result[soft_mask] = (
            pix.astype(np.uint16) * alpha_soft[:, None]
            + bg_u16 * inv_alpha[:, None]
            + 127
        ) // 255
        return result, alpha

    def apply_preview(self, rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Preview-only chroma key path.

        Export keeps using full-resolution ``apply``. Timeline preview can key a
        smaller frame and scale the keyed RGB/alpha back up, which cuts the
        repeated HSV/LUT/mask cost while preserving the same output contract.
        """
        if self.is_identity():
            return self.apply(rgb)
        try:
            import os
            scale = float(os.environ.get("TIGERCAPTURE_CHROMA_PREVIEW_SCALE", "0.375"))
        except Exception:
            scale = 0.375
        scale = max(0.25, min(1.0, scale))
        h, w = rgb.shape[:2]
        if scale >= 0.999 or w < 640 or h < 360:
            return self.apply(rgb)
        try:
            import cv2
            small_w = max(1, int(round(w * scale)))
            small_h = max(1, int(round(h * scale)))
            small = cv2.resize(rgb, (small_w, small_h), interpolation=cv2.INTER_AREA)
            keyed_small, alpha_small = self.apply(small)
            keyed = cv2.resize(keyed_small, (w, h), interpolation=cv2.INTER_LINEAR)
            alpha = cv2.resize(alpha_small, (w, h), interpolation=cv2.INTER_LINEAR)
            return (
                np.ascontiguousarray(keyed.astype(np.uint8, copy=False)),
                np.ascontiguousarray(alpha.astype(np.uint8, copy=False)),
            )
        except Exception:
            return self.apply(rgb)

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ['enabled','key_hue','key_sat','key_val','hue_range',
                 'sat_min','val_min','spill_suppress','bg_r','bg_g','bg_b']}

    @classmethod
    def from_dict(cls, d: dict) -> "ChromaKeyParams":
        return cls(**{k: d[k] for k in d if hasattr(cls, k)})
