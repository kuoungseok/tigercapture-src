"""Depth estimation entry points.

The production backend is intentionally not hardwired here. This module exposes
a deterministic local estimator for synthetic QA and reports optional backend
availability without downloading models.
"""
from __future__ import annotations

import importlib.util
from typing import Any


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def depth_backend_status() -> dict[str, Any]:
    return {
        "ok": True,
        "cloud_enabled": False,
        "auto_download": False,
        "capabilities": {
            "synthetic_luma_depth": {
                "available": True,
                "metric": False,
                "note": "Deterministic QA fallback, not production depth.",
            },
            "onnxruntime": {
                "available": _module_available("onnxruntime"),
                "metric": False,
                "note": "Candidate runtime for a packaged depth model.",
            },
            "torch": {
                "available": _module_available("torch"),
                "metric": False,
                "note": "Candidate runtime for local Video Depth Anything style models.",
            },
        },
    }


def _frame_to_rgb_array(frame: Any):
    import numpy as np

    try:
        from PIL import Image
        if isinstance(frame, Image.Image):
            return np.asarray(frame.convert("RGB"), dtype=np.uint8)
    except Exception:
        pass
    arr = np.asarray(frame)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError("frame must be grayscale or RGB-like")
    arr = arr[:, :, :3]
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    return arr


def estimate_depth_from_luma(
    frame: Any,
    *,
    source_id: str = "",
    time_ms: int = 0,
    vertical_weight: float = 0.7,
) -> tuple[Any, dict[str, Any]]:
    """Return a normalized synthetic depth frame.

    Convention: 0 is near, 1 is far. The vertical gradient assumes the lower
    part of a road frame is usually closer to the camera, then blends in luma so
    tests can exercise non-uniform depth behavior without a model dependency.
    """
    import numpy as np

    rgb = _frame_to_rgb_array(frame)
    h, w = rgb.shape[:2]
    luma = (
        rgb[..., 0].astype(np.float32) * 0.2126
        + rgb[..., 1].astype(np.float32) * 0.7152
        + rgb[..., 2].astype(np.float32) * 0.0722
    ) / 255.0
    y = np.linspace(1.0, 0.0, h, dtype=np.float32)[:, None]
    v = max(0.0, min(1.0, float(vertical_weight)))
    depth = np.clip(y * v + luma * (1.0 - v), 0.0, 1.0).astype(np.float32)
    if depth.shape[1] == 1 and w > 1:
        depth = np.repeat(depth, w, axis=1)
    diagnostics = {
        "ok": True,
        "backend": "synthetic_luma_depth",
        "metric": False,
        "depth_source_id": str(source_id or ""),
        "time_ms": int(time_ms),
        "shape": [int(h), int(w)],
        "range": [float(depth.min()), float(depth.max())],
        "warnings": ["synthetic depth is for QA and placeholder previews only"],
    }
    return depth, diagnostics

