"""Depth refinement helpers for video/AR compositing."""
from __future__ import annotations

from typing import Any, Mapping

from app.depth.providers import frame_to_rgb_array, resize_depth_to_frame


def refine_depth_for_compositing(
    depth_frame: Any,
    reference_frame: Any,
    *,
    foreground_mask: Any = None,
    settings: Mapping[str, Any] | None = None,
):
    """Return a normalized depth map with conservative edge cleanup.

    This is intentionally lightweight. It does not replace SAM or a learned
    refinement model, but it gives the compositor a less noisy map until those
    optional backends are installed.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    settings = settings or {}
    rgb = frame_to_rgb_array(reference_frame)
    h, w = rgb.shape[:2]
    depth = resize_depth_to_frame(depth_frame, w, h)
    radius = max(0.0, min(6.0, float(settings.get("radius_px", 1.25) or 1.25)))
    if radius > 0.0:
        image = Image.fromarray(depth.astype(np.float32), mode="F")
        depth = np.asarray(image.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32)
    if foreground_mask is not None:
        mask = np.asarray(foreground_mask, dtype=np.float32)
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        if mask.shape != (h, w):
            mask = np.asarray(
                Image.fromarray(mask.astype(np.float32), mode="F").resize((w, h), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
        if float(mask.max()) > 1.5:
            mask = mask / 255.0
        mask = np.clip(mask, 0.0, 1.0)
        # Pull foreground slightly forward so hands/face/object boundaries win
        # occlusion tests instead of flickering around equal depth values.
        foreground_bias = max(0.0, min(0.2, float(settings.get("foreground_bias", 0.035) or 0.035)))
        depth = np.where(mask > 0.5, np.maximum(0.0, depth - foreground_bias), depth)
    return np.clip(depth, 0.0, 1.0).astype(np.float32)
