"""Background reconstruction providers for editable layered image motion."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


INPAINT_MODES = ("auto", "fast", "enhanced_local")


@dataclass(slots=True)
class BackgroundInpaintResult:
    image: Any
    provider: str
    confidence: float
    coverage: float
    max_camera_travel_ratio: float
    warnings: list[str] = field(default_factory=list)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "confidence": float(self.confidence),
            "coverage": float(self.coverage),
            "max_camera_travel_ratio": float(self.max_camera_travel_ratio),
            "warnings": list(self.warnings),
        }


def inpaint_background(
    rgb,
    mask,
    *,
    transparent_source: bool,
    mode: str = "auto",
) -> BackgroundInpaintResult:
    """Reconstruct pixels hidden by extracted layers.

    The enhanced-local mode is a capability request. Until an optional learned
    provider is installed it falls back explicitly to the deterministic
    multiscale OpenCV implementation.
    """
    import cv2
    import numpy as np

    normalized_mode = str(mode or "auto").strip().casefold()
    if normalized_mode not in INPAINT_MODES:
        raise ValueError(f"unsupported background inpaint mode: {mode}")
    height, width = rgb.shape[:2]
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    coverage = float(np.count_nonzero(binary)) / float(max(1, height * width))
    if transparent_source:
        return BackgroundInpaintResult(
            image=np.dstack((rgb, np.zeros(binary.shape, dtype=np.uint8))),
            provider="transparent_canvas",
            confidence=1.0,
            coverage=coverage,
            max_camera_travel_ratio=0.12,
        )

    expanded = cv2.dilate(
        binary,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
        iterations=1,
    )
    expanded_coverage = float(np.count_nonzero(expanded)) / float(max(1, height * width))
    source_bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    warnings: list[str] = []
    if normalized_mode == "enhanced_local":
        warnings.append(
            "Enhanced Local inpainting is not installed; deterministic multiscale OpenCV fallback was used."
        )

    if expanded_coverage <= 0.045 and normalized_mode != "enhanced_local":
        radius = max(3.0, min(10.0, min(height, width) * 0.01))
        background = cv2.inpaint(source_bgr, expanded, radius, cv2.INPAINT_TELEA)
        return BackgroundInpaintResult(
            image=cv2.cvtColor(background, cv2.COLOR_BGR2RGB),
            provider="opencv_telea_small_hole",
            confidence=max(0.55, 0.95 - expanded_coverage * 4.0),
            coverage=expanded_coverage,
            max_camera_travel_ratio=0.075,
            warnings=warnings,
        )

    target_long_edge = 128
    scale = min(1.0, float(target_long_edge) / max(height, width))
    small_width = max(24, int(round(width * scale)))
    small_height = max(24, int(round(height * scale)))
    small_image = cv2.resize(
        source_bgr,
        (small_width, small_height),
        interpolation=cv2.INTER_AREA,
    )
    small_mask = cv2.resize(
        expanded,
        (small_width, small_height),
        interpolation=cv2.INTER_NEAREST,
    )
    small_mask = cv2.dilate(
        small_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
        iterations=1,
    )
    filled_small = cv2.inpaint(small_image, small_mask, 5.0, cv2.INPAINT_NS)
    filled = cv2.resize(filled_small, (width, height), interpolation=cv2.INTER_CUBIC)
    filled = cv2.GaussianBlur(
        filled,
        (0, 0),
        max(1.5, min(height, width) * 0.009),
    )
    blend = cv2.GaussianBlur(
        expanded.astype(np.float32) / 255.0,
        (0, 0),
        max(1.2, min(height, width) * 0.007),
    )[:, :, None]
    background = (
        source_bgr.astype(np.float32) * (1.0 - blend)
        + filled.astype(np.float32) * blend
    )
    confidence = max(0.2, min(0.78, 0.82 - expanded_coverage * 0.9))
    max_travel = max(0.008, min(0.04, 0.045 - expanded_coverage * 0.04))
    if expanded_coverage >= 0.18:
        warnings.append(
            "A large hidden region used deterministic inpainting; camera travel was restricted."
        )
    return BackgroundInpaintResult(
        image=cv2.cvtColor(
            np.clip(background, 0, 255).astype(np.uint8),
            cv2.COLOR_BGR2RGB,
        ),
        provider="opencv_multiscale_ns",
        confidence=confidence,
        coverage=expanded_coverage,
        max_camera_travel_ratio=max_travel,
        warnings=warnings,
    )


__all__ = [
    "INPAINT_MODES",
    "BackgroundInpaintResult",
    "inpaint_background",
]
