"""Deterministic alpha-matte refinement for extracted Motion image layers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


MATTING_MODES = ("binary", "edge_aware")


@dataclass(frozen=True, slots=True)
class MatteResult:
    alpha: Any
    provider: str
    soft_pixel_ratio: float

    def diagnostics(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "soft_pixel_ratio": float(self.soft_pixel_ratio),
        }


def refine_alpha_matte(rgb, mask, *, mode: str = "edge_aware") -> MatteResult:
    import cv2
    import numpy as np

    normalized = str(mode or "edge_aware").strip().casefold()
    if normalized not in MATTING_MODES:
        raise ValueError(f"unsupported matting mode: {mode}")
    source_alpha = np.clip(np.asarray(mask), 0, 255).astype(np.uint8)
    binary = np.where(source_alpha >= 128, 255, 0).astype(np.uint8)
    if normalized == "binary":
        return MatteResult(binary, "binary_mask", 0.0)

    height, width = binary.shape[:2]
    radius = max(1, min(7, int(round(min(height, width) * 0.004))))
    kernel_size = radius * 2 + 1
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    core = cv2.erode(binary, kernel, iterations=1)
    possible = cv2.dilate(binary, kernel, iterations=1)
    possible = np.maximum(
        possible,
        np.where(source_alpha > 0, 255, 0).astype(np.uint8),
    )
    sigma = max(0.8, radius * 0.8)
    # Preserve soft semantic alpha from BiRefNet/SAM-style providers. Turning it
    # into a binary mask here destroys hair strands and motion-blurred edges.
    smooth = cv2.GaussianBlur(
        source_alpha.astype(np.float32),
        (0, 0),
        sigma,
    )

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edge = cv2.Laplacian(gray, cv2.CV_32F, ksize=3)
    edge = np.clip(np.abs(edge) / 64.0, 0.0, 1.0)
    guided = smooth * (1.0 - edge * 0.28) + source_alpha.astype(np.float32) * edge * 0.28
    alpha = np.where(
        core > 0,
        np.maximum(source_alpha.astype(np.float32), guided),
        guided,
    )
    alpha = np.where(possible > 0, alpha, 0.0)
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)
    soft = np.count_nonzero((alpha > 0) & (alpha < 255))
    return MatteResult(
        alpha=alpha,
        provider="opencv_edge_aware_trimap",
        soft_pixel_ratio=float(soft) / float(max(1, alpha.size)),
    )


__all__ = ["MATTING_MODES", "MatteResult", "refine_alpha_matte"]
