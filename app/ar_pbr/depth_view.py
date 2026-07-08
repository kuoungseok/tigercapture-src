"""Viewer-friendly depth map conversion for AR/PBR preview frames."""
from __future__ import annotations

from typing import Any

from app.ar_pbr.depth_occlusion import normalize_depth_frame


DEPTH_VIEW_SCHEMA = "tigerstudio.ar_pbr.depth_view.v1"


def normalize_depth_view_mode(mode: Any) -> str:
    text = str(mode or "").strip().casefold().replace("-", "_").replace(" ", "_")
    if text in {"", "0", "false", "none", "normal", "off", "disabled"}:
        return "off"
    if text in {"1", "true", "on", "depth", "depth_map", "depth_only", "mono", "grayscale", "greyscale"}:
        return "grayscale"
    if text in {"invert", "inverted", "raw", "far_white", "grayscale_inverted", "greyscale_inverted"}:
        return "inverted_grayscale"
    if text in {"heat", "false_color", "falsecolour", "false_colour", "turbo"}:
        return "heat"
    return "grayscale"


def _contrast_depth(arr):
    import numpy as np

    data = np.asarray(arr, dtype=np.float32)
    finite = data[np.isfinite(data)]
    if finite.size <= 0:
        return np.clip(data, 0.0, 1.0), 0.0, 1.0
    lo = float(np.percentile(finite, 2.0))
    hi = float(np.percentile(finite, 98.0))
    if hi - lo < 1e-5:
        lo = float(np.min(finite))
        hi = float(np.max(finite))
    if hi - lo < 1e-5:
        return np.zeros_like(data, dtype=np.float32), lo, hi
    return np.clip((data - lo) / (hi - lo), 0.0, 1.0), lo, hi


def depth_frame_to_rgb(
    depth_frame: Any,
    width: int,
    height: int,
    *,
    mode: str = "grayscale",
) -> tuple[Any | None, dict[str, Any]]:
    """Convert a normalized depth frame to an RGB preview image.

    AR/PBR depth convention is near=0, far=1. The default viewer convention is
    near=white because it matches common depth-debug imagery and makes foreground
    object masks easier to inspect.
    """
    import numpy as np

    canonical_mode = normalize_depth_view_mode(mode)
    if canonical_mode == "off":
        return None, {
            "schema": DEPTH_VIEW_SCHEMA,
            "ok": True,
            "enabled": False,
            "mode": "off",
        }
    w = max(1, int(width or 1))
    h = max(1, int(height or 1))
    arr = normalize_depth_frame(depth_frame, w, h)
    if arr is None:
        return None, {
            "schema": DEPTH_VIEW_SCHEMA,
            "ok": False,
            "enabled": True,
            "mode": canonical_mode,
            "reason": "depth frame unavailable",
        }
    contrasted, lo, hi = _contrast_depth(arr)
    near = 1.0 - contrasted
    if canonical_mode == "inverted_grayscale":
        gray = contrasted
        rgb = np.repeat((gray * 255.0).astype(np.uint8)[:, :, None], 3, axis=2)
        near_is_white = False
    elif canonical_mode == "heat":
        # Compact false-color ramp: far blue, middle violet/cyan, near warm.
        t = np.clip(near, 0.0, 1.0)
        r = np.clip(0.10 + 1.25 * t, 0.0, 1.0)
        g = np.clip(0.18 + 1.45 * (1.0 - abs(t - 0.55) * 1.85), 0.0, 1.0)
        b = np.clip(1.05 - 0.95 * t + 0.22 * (1.0 - abs(t - 0.35) * 2.2), 0.0, 1.0)
        rgb = (np.stack([r, g, b], axis=2) * 255.0).astype(np.uint8)
        near_is_white = False
    else:
        gray = near
        rgb = np.repeat((gray * 255.0).astype(np.uint8)[:, :, None], 3, axis=2)
        near_is_white = True
    diagnostics = {
        "schema": DEPTH_VIEW_SCHEMA,
        "ok": True,
        "enabled": True,
        "mode": canonical_mode,
        "width": int(w),
        "height": int(h),
        "near_is_white": bool(near_is_white),
        "input_depth_min": float(np.nanmin(arr)),
        "input_depth_max": float(np.nanmax(arr)),
        "display_depth_low": float(lo),
        "display_depth_high": float(hi),
    }
    return np.ascontiguousarray(rgb), diagnostics
