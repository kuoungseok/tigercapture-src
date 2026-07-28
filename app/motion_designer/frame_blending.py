"""Frame blending configuration, backend preflight, and image mixing."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtGui import QImage, QPainter

from .schema import MotionLayer
from .source_frame import transparent_image

FRAME_BLENDING_KEY = "frame_blending"
FRAME_BLENDING_CONTRACT = "tigerstudio.motion.frame_blending.v1"
FRAME_BLEND_MODES = {"off", "frame_mix", "optical_flow"}


def set_layer_frame_blending(
    layer: MotionLayer,
    mode: str,
    *,
    source_fps: float = 0.0,
) -> dict[str, Any]:
    normalized = str(mode or "off").lower()
    if normalized not in FRAME_BLEND_MODES:
        raise ValueError(f"Unsupported frame blending mode: {mode}")
    data = {
        "contract": FRAME_BLENDING_CONTRACT,
        "mode": normalized,
        "source_fps": max(0.0, float(source_fps)),
    }
    layer.metadata[FRAME_BLENDING_KEY] = data
    return data


def layer_frame_blending(layer: MotionLayer) -> dict[str, Any]:
    value = layer.metadata.get(FRAME_BLENDING_KEY)
    return dict(value) if isinstance(value, Mapping) else {
        "contract": FRAME_BLENDING_CONTRACT,
        "mode": "off",
        "source_fps": 0.0,
    }


def optical_flow_preflight() -> dict[str, Any]:
    try:
        import cv2

        available = bool(
            hasattr(cv2, "calcOpticalFlowFarneback")
            or hasattr(cv2, "DISOpticalFlow_create")
        )
        version = str(getattr(cv2, "__version__", "unknown"))
    except Exception as exc:
        return {
            "available": False,
            "backend": "",
            "version": "",
            "reason": f"OpenCV unavailable: {exc}",
        }
    return {
        "available": available,
        "backend": "opencv" if available else "",
        "version": version,
        "reason": "" if available else "OpenCV optical-flow API unavailable",
    }


def frame_blending_preflight(layer: MotionLayer) -> dict[str, Any]:
    config = layer_frame_blending(layer)
    mode = str(config.get("mode") or "off")
    optical = optical_flow_preflight()
    effective = mode
    fallback = ""
    if mode == "optical_flow":
        # The current renderer advertises backend availability separately from
        # activation. Until vector warping is enabled, preserve deterministic
        # Preview/Export parity with explicit Frame Mix fallback.
        effective = "frame_mix"
        fallback = "optical_flow_vector_warp_not_enabled"
    return {
        "contract": FRAME_BLENDING_CONTRACT,
        "requested_mode": mode,
        "effective_mode": effective,
        "fallback_reason": fallback,
        "optical_flow": optical,
    }


def frame_mix_samples(
    time_ms: float,
    fps: float,
) -> tuple[float, float, float]:
    interval = 1000.0 / max(1.0, float(fps))
    frame_index = max(0, int(float(time_ms) // interval))
    left = frame_index * interval
    right = left + interval
    weight = max(0.0, min(1.0, (float(time_ms) - left) / interval))
    return left, right, weight


def mix_images(left: QImage, right: QImage, weight: float) -> QImage:
    if left.isNull() or right.isNull() or weight <= 1e-6:
        return left
    width = max(left.width(), right.width())
    height = max(left.height(), right.height())
    output = transparent_image(width, height)
    painter = QPainter(output)
    painter.setCompositionMode(QPainter.CompositionMode_Plus)
    painter.setOpacity(1.0 - max(0.0, min(1.0, float(weight))))
    painter.drawImage(0, 0, left)
    painter.setOpacity(max(0.0, min(1.0, float(weight))))
    painter.drawImage(0, 0, right)
    painter.end()
    return output


__all__ = [
    "FRAME_BLENDING_CONTRACT",
    "FRAME_BLENDING_KEY",
    "FRAME_BLEND_MODES",
    "frame_blending_preflight",
    "frame_mix_samples",
    "layer_frame_blending",
    "mix_images",
    "optical_flow_preflight",
    "set_layer_frame_blending",
]
