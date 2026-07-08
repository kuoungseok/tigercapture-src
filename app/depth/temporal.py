"""Temporal depth stabilization helpers."""
from __future__ import annotations

from typing import Any, Mapping

from app.depth.providers import resize_depth_to_frame


def stabilize_depth_frame(
    current_depth: Any,
    previous_depth: Any,
    *,
    reference_frame: Any | None = None,
    previous_reference_frame: Any | None = None,
    settings: Mapping[str, Any] | None = None,
):
    """Blend consecutive depth maps unless a scene cut is detected."""
    settings = settings or {}
    import numpy as np

    current_arr = np.asarray(current_depth)
    if current_arr.ndim < 2:
        raise ValueError("current_depth must be a 2D depth-like frame")
    current = resize_depth_to_frame(current_depth, int(current_arr.shape[1]), int(current_arr.shape[0]))
    if previous_depth is None:
        return current, {"ok": True, "stabilized": False, "reason": "no_previous_depth"}
    previous = resize_depth_to_frame(previous_depth, current.shape[1], current.shape[0])
    cut_threshold = max(0.0, min(1.0, float(settings.get("scene_cut_threshold", 0.28) or 0.28)))
    scene_cut_score = 0.0
    if reference_frame is not None and previous_reference_frame is not None:
        try:
            from app.depth.providers import frame_to_rgb_array

            a = frame_to_rgb_array(reference_frame).astype(np.float32) / 255.0
            b = frame_to_rgb_array(previous_reference_frame).astype(np.float32) / 255.0
            if a.shape == b.shape:
                scene_cut_score = float(np.mean(np.abs(a - b)))
        except Exception:
            scene_cut_score = 0.0
    if scene_cut_score >= cut_threshold:
        return current, {
            "ok": True,
            "stabilized": False,
            "scene_cut": True,
            "scene_cut_score": scene_cut_score,
        }
    alpha = max(0.0, min(0.95, float(settings.get("alpha", 0.72) or 0.72)))
    out = previous * alpha + current * (1.0 - alpha)
    return np.clip(out, 0.0, 1.0).astype(np.float32), {
        "ok": True,
        "stabilized": True,
        "scene_cut": False,
        "scene_cut_score": scene_cut_score,
        "alpha": alpha,
    }
