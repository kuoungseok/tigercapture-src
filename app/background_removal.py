"""AI-based background removal using rembg or MediaPipe fallback."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class BackgroundRemovalParams:
    enabled: bool = False
    # "rembg" uses u2net model (best quality, requires rembg package)
    # "mediapipe" uses selfie segmentation (fast, built-in)
    # "chroma_auto" auto-detects background colour
    method: str = "mediapipe"
    # Background replacement
    bg_mode: str = "color"      # "color", "blur", "transparent"
    bg_r: int = 0
    bg_g: int = 0
    bg_b: int = 0
    bg_blur_radius: int = 20    # for bg_mode="blur"
    # Mask feather (pixels)
    feather: int = 3
    # Confidence threshold 0-1 (mediapipe)
    threshold: float = 0.5

    def is_identity(self) -> bool:
        return not self.enabled

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """Return composited frame with background removed/replaced."""
        if not self.enabled:
            return rgb
        mask = self._get_mask(rgb)
        if mask is None:
            return rgb
        return self._composite(rgb, mask)

    def _get_mask(self, rgb: np.ndarray) -> Optional[np.ndarray]:
        """Return float32 mask (H,W) — 1=foreground, 0=background."""
        if self.method == "mediapipe":
            return self._mediapipe_mask(rgb)
        elif self.method == "rembg":
            return self._rembg_mask(rgb)
        return None

    def _mediapipe_mask(self, rgb: np.ndarray) -> Optional[np.ndarray]:
        try:
            import mediapipe as mp
            seg = mp.solutions.selfie_segmentation
            with seg.SelfieSegmentation(model_selection=1) as selfie:
                result = selfie.process(rgb)
                if result.segmentation_mask is None:
                    return None
                mask = result.segmentation_mask  # float32 0-1
                return (mask > self.threshold).astype(np.float32)
        except ImportError:
            return self._fallback_mask(rgb)
        except Exception:
            return None

    def _rembg_mask(self, rgb: np.ndarray) -> Optional[np.ndarray]:
        try:
            from rembg import remove
            from PIL import Image
            import io
            pil = Image.fromarray(rgb)
            out = remove(pil)
            alpha = np.array(out)[:, :, 3].astype(np.float32) / 255.0
            return alpha
        except ImportError:
            return self._mediapipe_mask(rgb)
        except Exception:
            return None

    def _fallback_mask(self, rgb: np.ndarray) -> Optional[np.ndarray]:
        """Simple background colour detection fallback (no AI)."""
        try:
            import cv2
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            # Assume background is the most common colour at frame edges
            edges = np.concatenate([
                rgb[0, :], rgb[-1, :], rgb[:, 0], rgb[:, -1]
            ])
            mean_color = edges.mean(axis=0).astype(np.uint8)
            mean_hsv = cv2.cvtColor(mean_color.reshape(1, 1, 3), cv2.COLOR_RGB2HSV)[0, 0]
            hue_diff = np.abs(hsv[:,:,0].astype(int) - int(mean_hsv[0]))
            hue_diff = np.minimum(hue_diff, 180 - hue_diff)
            mask = (hue_diff > 20).astype(np.float32)
            return mask
        except Exception:
            return None

    def _composite(self, rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        try:
            import cv2
            h, w = rgb.shape[:2]
            # Feather mask
            if self.feather > 0:
                mask = cv2.GaussianBlur(mask, (self.feather*2+1, self.feather*2+1), self.feather/3)

            if self.bg_mode == "blur":
                # Blur the original for background
                bg = cv2.GaussianBlur(rgb, (0, 0), float(self.bg_blur_radius))
            else:
                # Solid colour background
                bg = np.full_like(rgb, [self.bg_r, self.bg_g, self.bg_b], dtype=np.uint8)

            m = mask[:,:,None]
            result = rgb.astype(np.float32) * m + bg.astype(np.float32) * (1 - m)
            return np.clip(result, 0, 255).astype(np.uint8)
        except Exception:
            return rgb

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in
                ['enabled','method','bg_mode','bg_r','bg_g','bg_b',
                 'bg_blur_radius','feather','threshold']}

    @classmethod
    def from_dict(cls, d: dict) -> "BackgroundRemovalParams":
        obj = cls()
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj
