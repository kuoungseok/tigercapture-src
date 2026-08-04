"""Raster preparation for grounded layered-image composites."""
from __future__ import annotations

from pathlib import Path
from typing import Any


CONTACT_COMPOSITE_SCHEMA = "tigerstudio.motion.contact_composite.v1"


def prepare_contact_composite(
    *,
    foreground_path: str | Path,
    background_path: str | Path,
    output_dir: str | Path,
    edge_strength: float = 0.8,
    light_match_strength: float = 0.25,
    shadow_opacity: float = 0.34,
) -> dict[str, Any]:
    """Write a decontaminated foreground and a separate soft contact shadow."""
    import cv2
    import numpy as np

    foreground_source = Path(foreground_path).expanduser().resolve(strict=True)
    background_source = Path(background_path).expanduser().resolve(strict=True)
    target = Path(output_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    foreground = cv2.imread(str(foreground_source), cv2.IMREAD_UNCHANGED)
    background = cv2.imread(str(background_source), cv2.IMREAD_COLOR)
    if foreground is None or foreground.ndim != 3 or foreground.shape[2] < 4:
        raise ValueError("foreground must be a readable RGBA image")
    if background is None:
        raise ValueError("background must be a readable image")
    height, width = foreground.shape[:2]
    if background.shape[:2] != (height, width):
        background = cv2.resize(background, (width, height), interpolation=cv2.INTER_AREA)

    bgr = foreground[:, :, :3].astype(np.float32)
    alpha = foreground[:, :, 3].astype(np.float32) / 255.0
    bg = background.astype(np.float32)
    edge = (alpha > 0.02) & (alpha < 0.98)
    safe_alpha = np.maximum(alpha[:, :, None], 0.08)
    recovered = (bgr - bg * (1.0 - alpha[:, :, None])) / safe_alpha
    blend = np.clip(float(edge_strength), 0.0, 1.0) * edge[:, :, None]
    corrected = bgr * (1.0 - blend) + np.clip(recovered, 0.0, 255.0) * blend

    subject = alpha >= 0.75
    ring = cv2.dilate(subject.astype(np.uint8), np.ones((15, 15), np.uint8), 1) > 0
    ring &= ~subject
    if np.any(subject) and np.any(ring):
        subject_mean = corrected[subject].mean(axis=0)
        background_mean = bg[ring].mean(axis=0)
        gain = np.clip(background_mean / np.maximum(subject_mean, 12.0), 0.78, 1.22)
        strength = np.clip(float(light_match_strength), 0.0, 1.0)
        corrected[subject] *= 1.0 + (gain - 1.0) * strength
    else:
        gain = np.ones(3, dtype=np.float32)
    corrected = np.clip(corrected, 0.0, 255.0).astype(np.uint8)
    corrected_rgba = np.dstack((corrected, foreground[:, :, 3]))

    ys, xs = np.nonzero(alpha > 0.08)
    shadow = np.zeros((height, width, 4), dtype=np.uint8)
    if len(xs):
        left, right = int(xs.min()), int(xs.max())
        bottom = int(min(
            height - 1,
            int(ys.max()) + max(1, int(round(height * 0.006))),
        ))
        center = ((left + right) // 2, bottom)
        axes = (max(3, int((right - left + 1) * 0.28)), max(2, int(height * 0.014)))
        matte = np.zeros((height, width), dtype=np.uint8)
        cv2.ellipse(matte, center, axes, 0, 0, 360, 255, -1, cv2.LINE_AA)
        sigma = max(2.0, width * 0.009)
        matte = cv2.GaussianBlur(matte, (0, 0), sigma)
        shadow[:, :, 3] = np.clip(
            matte.astype(np.float32) * np.clip(float(shadow_opacity), 0.0, 1.0),
            0,
            255,
        ).astype(np.uint8)

    foreground_output = target / "foreground_contact_ready.png"
    shadow_output = target / "contact_shadow.png"
    if not cv2.imwrite(str(foreground_output), corrected_rgba):
        raise OSError(f"unable to write {foreground_output}")
    if not cv2.imwrite(str(shadow_output), shadow):
        raise OSError(f"unable to write {shadow_output}")
    return {
        "schema": CONTACT_COMPOSITE_SCHEMA,
        "foreground_path": str(foreground_output),
        "shadow_path": str(shadow_output),
        "diagnostics": {
            "edge_pixel_count": int(np.count_nonzero(edge)),
            "light_gain_bgr": [round(float(value), 4) for value in gain],
            "shadow_opacity": float(np.clip(shadow_opacity, 0.0, 1.0)),
            "preview_export_assets_shared": True,
        },
    }


__all__ = ["CONTACT_COMPOSITE_SCHEMA", "prepare_contact_composite"]
