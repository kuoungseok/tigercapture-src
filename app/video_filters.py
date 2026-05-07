"""Clip-level video filter effects applied in the render pipeline."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


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
            out = np.clip(out, 0, 255).astype(np.uint8)

        # Chromatic aberration: shift R channel left, B channel right
        if self.chroma_aberration > 0:
            shift = max(1, int(self.chroma_aberration * 3))
            r = np.roll(out[:, :, 0], -shift, axis=1)
            b = np.roll(out[:, :, 2],  shift, axis=1)
            out = np.stack([r, out[:, :, 1], b], axis=2).astype(np.uint8)

        # Vignette: radial darkening from center
        if self.vignette > 0:
            ys = np.linspace(0, 1, h) - 0.5
            xs = np.linspace(0, 1, w) - 0.5
            xg, yg = np.meshgrid(xs, ys)
            dist = np.sqrt(xg**2 + yg**2) * 2.0  # 0..~1.41
            feather = max(0.01, float(self.vignette_feather))
            mask = np.clip(1.0 - (dist - (1.0 - feather)) / feather, 0.0, 1.0)
            darkness = float(self.vignette)
            mask = (1.0 - darkness) + darkness * mask
            out = np.clip(out.astype(np.float32) * mask[:, :, None], 0, 255).astype(np.uint8)

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
        )
