"""Background video stabilization using cv2 feature tracking."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
import os
import numpy as np


@dataclass
class StabilizerParams:
    enabled: bool = False
    smoothing_radius: int = 15   # frames to smooth over
    crop_ratio: float = 0.05     # fraction to crop on each side for stability border

    def is_identity(self) -> bool:
        return not self.enabled

    def to_dict(self) -> dict:
        return {'enabled': self.enabled, 'smoothing_radius': self.smoothing_radius, 'crop_ratio': self.crop_ratio}

    @classmethod
    def from_dict(cls, d: dict) -> "StabilizerParams":
        return cls(enabled=bool(d.get('enabled', False)),
                   smoothing_radius=int(d.get('smoothing_radius', 15)),
                   crop_ratio=float(d.get('crop_ratio', 0.05)))


class FrameStabilizer:
    """Per-clip stabilizer that maintains a rolling transform buffer.
    Call reset() when seeking, then apply(frame) each decoded frame."""

    def __init__(self, params: StabilizerParams):
        self.params = params
        self._prev_gray = None
        self._transforms: List[np.ndarray] = []  # list of 2x3 affine matrices
        self._smoothed: List[np.ndarray] = []
        self._frame_idx = 0

    def reset(self):
        self._prev_gray = None
        self._transforms = []
        self._smoothed = []
        self._frame_idx = 0

    def _preview_scale(self) -> float:
        raw = os.environ.get("TIGERCAPTURE_STABILIZER_PREVIEW_SCALE", "0.5")
        try:
            scale = float(raw)
        except (TypeError, ValueError):
            scale = 0.5
        return max(0.25, min(1.0, scale))

    def _prepare_gray(self, cv2, rgb: np.ndarray, scale: float = 1.0) -> tuple[np.ndarray, float, float]:
        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if scale >= 0.999:
            return gray, 1.0, 1.0
        scaled_w = max(16, int(round(w * scale)))
        scaled_h = max(16, int(round(h * scale)))
        if scaled_w == w and scaled_h == h:
            return gray, 1.0, 1.0
        gray = cv2.resize(gray, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
        return gray, float(w) / float(scaled_w), float(h) / float(scaled_h)

    def _identity_transform(self) -> np.ndarray:
        return np.eye(2, 3, dtype=np.float64)

    def _estimate_transform(self, cv2, gray: np.ndarray, sx: float, sy: float) -> np.ndarray:
        if self._prev_gray is None or self._prev_gray.shape != gray.shape:
            self._prev_gray = gray
            return self._identity_transform()

        prev_pts = cv2.goodFeaturesToTrack(
            self._prev_gray, maxCorners=160, qualityLevel=0.01,
            minDistance=24, blockSize=3,
        )
        if prev_pts is None or len(prev_pts) < 4:
            return self._identity_transform()

        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            self._prev_gray, gray, prev_pts, None,
        )
        if curr_pts is None or status is None:
            return self._identity_transform()
        good_prev = prev_pts[status.ravel() == 1]
        good_curr = curr_pts[status.ravel() == 1]
        if len(good_prev) < 4:
            return self._identity_transform()
        M, _ = cv2.estimateAffinePartial2D(good_prev, good_curr)
        if M is None:
            return self._identity_transform()
        M = np.asarray(M, dtype=np.float64)
        M[0, 2] *= sx
        M[1, 2] *= sy
        return M

    def _smooth_current_transform(self) -> np.ndarray:
        r = self.params.smoothing_radius
        n = len(self._transforms)
        if n <= 0:
            return self._identity_transform()
        cum = np.cumsum([t[:, 2] for t in self._transforms], axis=0)
        lo = max(0, n - 1 - r)
        hi = min(n - 1, n - 1 + r)
        smooth_t = cum[hi] / (hi - lo + 1) if hi > lo else cum[n - 1] / n
        raw_t = self._transforms[-1][:, 2]
        correction = smooth_t - raw_t
        M_corrected = self._transforms[-1].copy()
        M_corrected[:, 2] += correction
        return M_corrected

    def _warp_and_crop(self, cv2, rgb: np.ndarray, M_corrected: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        crop = self.params.crop_ratio
        cx, cy = int(w * crop), int(h * crop)
        stabilized = cv2.warpAffine(
            rgb, M_corrected, (w, h),
            borderMode=cv2.BORDER_REPLICATE,
        )
        cropped = stabilized[cy:h-cy, cx:w-cx]
        if cropped.size == 0:
            return stabilized
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    def _apply_with_gray(self, cv2, rgb: np.ndarray, gray: np.ndarray, sx: float, sy: float) -> np.ndarray:
        M = self._estimate_transform(cv2, gray, sx, sy)
        self._transforms.append(M)
        self._prev_gray = gray
        self._frame_idx += 1
        M_corrected = self._smooth_current_transform()
        return self._warp_and_crop(cv2, rgb, M_corrected)

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """Stabilize one frame at full quality. Export uses this path."""
        if not self.params.enabled:
            return rgb
        try:
            import cv2
        except ImportError:
            return rgb
        gray, sx, sy = self._prepare_gray(cv2, rgb, 1.0)
        return self._apply_with_gray(cv2, rgb, gray, sx, sy)

    def apply_preview(self, rgb: np.ndarray) -> np.ndarray:
        """Stabilize one preview frame using low-res tracking and full-res warp."""
        if not self.params.enabled:
            return rgb
        try:
            import cv2
        except ImportError:
            return rgb
        gray, sx, sy = self._prepare_gray(cv2, rgb, self._preview_scale())
        return self._apply_with_gray(cv2, rgb, gray, sx, sy)
