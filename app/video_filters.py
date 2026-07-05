"""Clip-level video filter effects applied in the render pipeline."""
from __future__ import annotations
from collections import OrderedDict
from dataclasses import dataclass, field
import os
from typing import Any, Optional
import numpy as np


_VIGNETTE_MASK_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_VIGNETTE_MASK_CACHE_LIMIT = 16
_VIGNETTE_MASK16_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_VIGNETTE_MASK16_CACHE_LIMIT = 16


def _vignette_mask(height: int, width: int, amount: float, feather: float) -> np.ndarray:
    """Return a cached float32 vignette multiplier for a frame shape."""
    key = (
        int(height),
        int(width),
        round(float(amount), 4),
        round(float(feather), 4),
    )
    cached = _VIGNETTE_MASK_CACHE.get(key)
    if cached is not None:
        _VIGNETTE_MASK_CACHE.move_to_end(key)
        return cached

    ys = np.linspace(0, 1, height, dtype=np.float32) - 0.5
    xs = np.linspace(0, 1, width, dtype=np.float32) - 0.5
    xg, yg = np.meshgrid(xs, ys)
    dist = np.sqrt(xg * xg + yg * yg).astype(np.float32, copy=False) * 2.0
    feather_v = max(0.01, float(feather))
    mask = np.clip(
        1.0 - (dist - (1.0 - feather_v)) / feather_v,
        0.0,
        1.0,
    ).astype(np.float32, copy=False)
    darkness = float(amount)
    mask = ((1.0 - darkness) + darkness * mask).astype(np.float32, copy=False)
    _VIGNETTE_MASK_CACHE[key] = mask
    _VIGNETTE_MASK_CACHE.move_to_end(key)
    while len(_VIGNETTE_MASK_CACHE) > _VIGNETTE_MASK_CACHE_LIMIT:
        _VIGNETTE_MASK_CACHE.popitem(last=False)
    return mask


def _vignette_mask16(height: int, width: int, amount: float, feather: float) -> np.ndarray:
    """Return a cached 0..256 uint16 vignette multiplier."""
    key = (
        int(height),
        int(width),
        round(float(amount), 4),
        round(float(feather), 4),
    )
    cached = _VIGNETTE_MASK16_CACHE.get(key)
    if cached is not None:
        _VIGNETTE_MASK16_CACHE.move_to_end(key)
        return cached
    mask = _vignette_mask(height, width, amount, feather)
    mask16 = np.clip(mask * 256.0 + 0.5, 0, 256).astype(np.uint16)
    _VIGNETTE_MASK16_CACHE[key] = mask16
    _VIGNETTE_MASK16_CACHE.move_to_end(key)
    while len(_VIGNETTE_MASK16_CACHE) > _VIGNETTE_MASK16_CACHE_LIMIT:
        _VIGNETTE_MASK16_CACHE.popitem(last=False)
    return mask16


@dataclass
class VideoFilterParams:
    """All optional clip-level filter effects."""
    # Sharpen: unsharp mask strength (0=off, 1=normal, 2=heavy)
    sharpen: float = 0.0
    # Vignette: darkness at edges (0=off, 1=full black edges)
    vignette: float = 0.0
    vignette_feather: float = 0.5  # 0=hard, 1=soft
    # Noise reduction: temporal blend strength (0=off, 1=max)
    denoise: float = 0.0
    # Chromatic aberration: pixel offset (0=off, 5=heavy)
    chroma_aberration: float = 0.0
    # Glitch: horizontal scanline shift intensity (0=off, 1=heavy)
    glitch: float = 0.0
    enabled: bool = True
    # UI/application metadata for timeline labels and project round-trips.
    preset_meta: dict[str, Any] = field(default_factory=dict)

    def is_identity(self) -> bool:
        return (not self.enabled or
                (self.sharpen == 0 and self.vignette == 0 and
                 self.denoise == 0 and self.chroma_aberration == 0 and
                 self.glitch == 0))

    def apply(self, rgb: np.ndarray, prev_frame: Optional[np.ndarray] = None) -> np.ndarray:
        if self.is_identity():
            return rgb
        import cv2
        out = rgb.copy()
        h, w = out.shape[:2]

        # Sharpen via unsharp mask
        if self.sharpen > 0:
            strength = float(self.sharpen)
            blurred = cv2.GaussianBlur(out, (0, 0), 3.0)
            out = cv2.addWeighted(out, 1.0 + strength, blurred, -strength, 0)

        # Chromatic aberration: shift R channel left, B channel right
        if self.chroma_aberration > 0:
            shift = max(1, int(self.chroma_aberration * 3))
            src = out.copy()
            out[:, :, 0] = np.roll(src[:, :, 0], -shift, axis=1)
            out[:, :, 2] = np.roll(src[:, :, 2], shift, axis=1)

        # Vignette: radial darkening from center
        if self.vignette > 0:
            mask = _vignette_mask16(h, w, self.vignette, self.vignette_feather)
            out = ((out.astype(np.uint16) * mask[:, :, None] + 128) // 256).astype(np.uint8)

        # Noise reduction: blend with previous frame
        if self.denoise > 0 and prev_frame is not None:
            if prev_frame.shape == out.shape:
                alpha = float(self.denoise) * 0.5
                out = (out.astype(np.float32) * (1 - alpha) +
                       prev_frame.astype(np.float32) * alpha)
                out = np.clip(out, 0, 255).astype(np.uint8)

        # Glitch: random horizontal scanline shifts
        if self.glitch > 0:
            import random
            strength = float(self.glitch)
            n_lines = max(1, int(strength * 10))
            for _ in range(n_lines):
                y = random.randint(0, h - 1)
                shift = random.randint(-int(strength * 20), int(strength * 20))
                if shift != 0:
                    out[y] = np.roll(out[y], shift, axis=0)

        return out

    def apply_preview(self, rgb: np.ndarray, prev_frame: Optional[np.ndarray] = None) -> np.ndarray:
        """Apply filters using a fast preview path.

        Export keeps using ``apply`` at full source resolution. Preview can
        safely run most spatial filters on a downsampled frame because the UI
        is already a monitoring surface, and this keeps timeline playback from
        being dominated by full-frame filter passes.
        """
        if self.is_identity():
            return rgb
        if self.denoise > 0 or self.glitch > 0:
            return self.apply(rgb, prev_frame=prev_frame)
        try:
            scale = float(os.environ.get("TIGERCAPTURE_FILTER_PREVIEW_SCALE", "0.375"))
        except Exception:
            scale = 0.375
        scale = max(0.25, min(1.0, scale))
        h, w = rgb.shape[:2]
        if scale >= 0.999 or h < 360 or w < 640:
            return self.apply(rgb, prev_frame=prev_frame)
        import cv2
        sw = max(1, int(round(w * scale)))
        sh = max(1, int(round(h * scale)))
        small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA)
        filtered = self.apply(small, prev_frame=None)
        return cv2.resize(filtered, (w, h), interpolation=cv2.INTER_LINEAR)

    def to_dict(self) -> dict:
        return {
            "kind": "video_filters",
            "sharpen": self.sharpen,
            "vignette": self.vignette,
            "vignette_feather": self.vignette_feather,
            "denoise": self.denoise,
            "chroma_aberration": self.chroma_aberration,
            "glitch": self.glitch,
            "enabled": self.enabled,
            "preset_meta": dict(self.preset_meta or {}),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VideoFilterParams":
        return cls(
            sharpen=float(d.get("sharpen", 0.0)),
            vignette=float(d.get("vignette", 0.0)),
            vignette_feather=float(d.get("vignette_feather", 0.5)),
            denoise=float(d.get("denoise", 0.0)),
            chroma_aberration=float(d.get("chroma_aberration", 0.0)),
            glitch=float(d.get("glitch", 0.0)),
            enabled=bool(d.get("enabled", True)),
            preset_meta=dict(d.get("preset_meta", {}) or {}),
        )
