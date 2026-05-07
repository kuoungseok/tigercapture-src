"""Background video stabilization using cv2 feature tracking."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
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

    def apply(self, rgb: np.ndarray) -> np.ndarray:
        """Stabilize one frame. Returns stabilized RGB."""
        if not self.params.enabled:
            return rgb
        try:
            import cv2
        except ImportError:
            return rgb

        h, w = rgb.shape[:2]
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

        if self._prev_gray is None:
            self._prev_gray = gray
            self._transforms.append(np.eye(2, 3, dtype=np.float64))
            self._frame_idx += 1
            return rgb

        # Feature tracking
        prev_pts = cv2.goodFeaturesToTrack(
            self._prev_gray, maxCorners=200, qualityLevel=0.01,
            minDistance=30, blockSize=3,
        )
        if prev_pts is None or len(prev_pts) < 4:
            self._transforms.append(np.eye(2, 3, dtype=np.float64))
        else:
            curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
                self._prev_gray, gray, prev_pts, None,
            )
            good_prev = prev_pts[status.ravel() == 1]
            good_curr = curr_pts[status.ravel() == 1]
            if len(good_prev) >= 4:
                M, _ = cv2.estimateAffinePartial2D(good_prev, good_curr)
                if M is None:
                    M = np.eye(2, 3, dtype=np.float64)
            else:
                M = np.eye(2, 3, dtype=np.float64)
            self._transforms.append(M)

        self._prev_gray = gray
        self._frame_idx += 1

        # Smooth transforms over rolling window
        r = self.params.smoothing_radius
        n = len(self._transforms)
        # Cumulative sum for smoothing
        cum = np.cumsum([t[:, 2] for t in self._transforms], axis=0)
        lo = max(0, n - 1 - r)
        hi = min(n - 1, n - 1 + r)
        smooth_t = cum[hi] / (hi - lo + 1) if hi > lo else cum[n-1] / n

        # Correction: difference between smooth and raw
        raw_t = self._transforms[-1][:, 2]
        correction = smooth_t - raw_t

        M_corrected = self._transforms[-1].copy()
        M_corrected[:, 2] += correction

        # Apply transform with border crop
        crop = self.params.crop_ratio
        cx, cy = int(w * crop), int(h * crop)
        stabilized = cv2.warpAffine(
            rgb, M_corrected, (w, h),
            borderMode=cv2.BORDER_REPLICATE,
        )
        # Crop and resize back
        cropped = stabilized[cy:h-cy, cx:w-cx]
        if cropped.size == 0:
            return stabilized
        return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
