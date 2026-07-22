"""Motion Clip preview compositing for ProjectPlayer."""
from __future__ import annotations

import numpy as np

from app.motion_designer.compositor import composite_motion_clips, normalize_motion_state


def set_motion_state(self, compositions, clips) -> None:
    self._motion_compositions, self._motion_clips = normalize_motion_state(compositions, clips)
    renderer = getattr(self, "_motion_renderer", None)
    if renderer is not None:
        renderer.cache.clear()
    self._last_preview_frame_cache = None


def motion_state(self) -> dict:
    return {"compositions": [item.to_dict() for item in self._motion_compositions.values()],
            "clips": [item.to_dict() for item in self._motion_clips]}


def _apply_motion_clips(self, rgb: np.ndarray, position_ms: int) -> np.ndarray:
    return composite_motion_clips(self, rgb, position_ms, cache_capacity=90)
