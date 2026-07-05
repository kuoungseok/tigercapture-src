"""Fast preview-only combined clip effects."""
from __future__ import annotations

import os

import numpy as np


def _preview_scale(name: str, default: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except Exception:
        value = default
    return max(0.25, min(1.0, value))


def _active(obj) -> bool:
    return obj is not None and not obj.is_identity()


def _filter_can_batch(video_filters) -> bool:
    if not _active(video_filters):
        return False
    return (
        float(getattr(video_filters, "denoise", 0.0) or 0.0) <= 0.0
        and float(getattr(video_filters, "glitch", 0.0) or 0.0) <= 0.0
    )


def shader_clip_effects_enabled() -> bool:
    return os.environ.get("TIGERCAPTURE_SHADER_CLIP_FX", "1").strip().lower() not in {
        "0", "false", "no", "off", "disabled",
    }


def _filter_can_shader(video_filters) -> bool:
    if not _active(video_filters):
        return True
    return (
        float(getattr(video_filters, "denoise", 0.0) or 0.0) <= 0.0
        and float(getattr(video_filters, "glitch", 0.0) or 0.0) <= 0.0
    )


def build_shader_clip_effects(video_filters, chroma_key) -> dict | None:
    """Return GL-shader metadata for preview-safe clip filters/chroma.

    The shader path is intentionally narrower than the CPU path. Temporal or
    random effects stay on CPU so GL preview and QImage fallback do not diverge.
    """
    if not shader_clip_effects_enabled():
        return None
    has_filters = _active(video_filters)
    has_chroma = _active(chroma_key)
    if not has_filters and not has_chroma:
        return None
    if not _filter_can_shader(video_filters):
        return None
    filters = None
    if has_filters:
        filters = {
            "sharpen": float(getattr(video_filters, "sharpen", 0.0) or 0.0),
            "vignette": float(getattr(video_filters, "vignette", 0.0) or 0.0),
            "vignette_feather": float(getattr(video_filters, "vignette_feather", 0.5) or 0.5),
            "chroma_aberration": float(getattr(video_filters, "chroma_aberration", 0.0) or 0.0),
        }
    chroma = None
    if has_chroma:
        chroma = {
            "key_hue": float(getattr(chroma_key, "key_hue", 60) or 60),
            "hue_range": float(getattr(chroma_key, "hue_range", 30) or 30),
            "sat_min": float(getattr(chroma_key, "sat_min", 60) or 60),
            "val_min": float(getattr(chroma_key, "val_min", 60) or 60),
            "spill_suppress": float(getattr(chroma_key, "spill_suppress", 0.0) or 0.0),
            "bg": (
                float(getattr(chroma_key, "bg_r", 0) or 0) / 255.0,
                float(getattr(chroma_key, "bg_g", 0) or 0) / 255.0,
                float(getattr(chroma_key, "bg_b", 0) or 0) / 255.0,
            ),
        }
    return {
        "enabled": True,
        "filters": filters,
        "chroma": chroma,
    }


def apply_filter_chroma_preview_batch(
    rgb: np.ndarray,
    video_filters,
    chroma_key,
) -> tuple[np.ndarray, np.ndarray | None, bool]:
    """Apply filter+chroma preview through one downsample/upsample pass.

    Export keeps using the independent full-resolution effect paths. This is
    only for interactive preview where both clip-level video filters and chroma
    key are enabled and both can safely run on a monitoring-resolution frame.
    """
    if os.environ.get("TIGERCAPTURE_DISABLE_FILTER_CHROMA_BATCH", "").strip().lower() in {
        "1", "true", "yes", "on",
    }:
        return rgb, None, False
    if not (_filter_can_batch(video_filters) and _active(chroma_key)):
        return rgb, None, False
    h, w = rgb.shape[:2]
    if h < 360 or w < 640:
        return rgb, None, False

    scale = min(
        _preview_scale("TIGERCAPTURE_FILTER_PREVIEW_SCALE", 0.375),
        _preview_scale("TIGERCAPTURE_CHROMA_PREVIEW_SCALE", 0.375),
    )
    if scale >= 0.999:
        return rgb, None, False

    try:
        import cv2

        sw = max(1, int(round(w * scale)))
        sh = max(1, int(round(h * scale)))
        small = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA)
        filtered = video_filters.apply(small, prev_frame=None)
        keyed_small, alpha_small = chroma_key.apply(filtered)
        keyed = cv2.resize(keyed_small, (w, h), interpolation=cv2.INTER_LINEAR)
        alpha = cv2.resize(alpha_small, (w, h), interpolation=cv2.INTER_LINEAR)
        return (
            np.ascontiguousarray(keyed.astype(np.uint8, copy=False)),
            np.ascontiguousarray(alpha.astype(np.uint8, copy=False)),
            True,
        )
    except Exception:
        return rgb, None, False
