"""Shared Motion Clip state normalization and premultiplied-alpha compositing."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .export_renderer import MotionExportRenderer
from .color_management import (
    composite_premultiplied_srgb_over_srgb,
    settings_from_composition_metadata,
)
from .schema import MotionComposition
from .timeline_bridge import active_motion_clips, composition_time_ms, normalize_motion_clips


def normalize_motion_state(compositions: Any, clips: Any) -> tuple[dict[str, MotionComposition], list]:
    values = compositions.values() if isinstance(compositions, Mapping) else (compositions or [])
    normalized_compositions = {
        item.id: item if isinstance(item, MotionComposition) else MotionComposition.from_dict(item)
        for item in values
    }
    return normalized_compositions, normalize_motion_clips(clips or [])


def transform_motion_actor_rgba(rgba, clip):
    """Apply one timeline Motion Actor instance transform to premultiplied RGBA."""
    import numpy as np

    source = np.asarray(rgba, dtype=np.uint8)
    if source.ndim != 3 or source.shape[2] != 4:
        raise ValueError("Motion Actor source must be an RGBA array")
    position_x = float(getattr(clip, "position_x", 0.0) or 0.0)
    position_y = float(getattr(clip, "position_y", 0.0) or 0.0)
    scale_x = max(0.001, float(getattr(clip, "scale_x", 1.0) or 1.0))
    scale_y = max(0.001, float(getattr(clip, "scale_y", 1.0) or 1.0))
    rotation = float(getattr(clip, "rotation_degrees", 0.0) or 0.0)
    if (
        abs(position_x) < 1e-6
        and abs(position_y) < 1e-6
        and abs(scale_x - 1.0) < 1e-6
        and abs(scale_y - 1.0) < 1e-6
        and abs(rotation) < 1e-6
    ):
        return source

    import cv2

    height, width = source.shape[:2]
    anchor_x = max(0.0, min(1.0, float(getattr(clip, "anchor_x", 0.5))))
    anchor_y = max(0.0, min(1.0, float(getattr(clip, "anchor_y", 0.5))))
    pivot_x = anchor_x * width
    pivot_y = anchor_y * height
    radians = np.deg2rad(rotation)
    cosine = float(np.cos(radians))
    sine = float(np.sin(radians))
    a = cosine * scale_x
    b = sine * scale_y
    c = -sine * scale_x
    d = cosine * scale_y
    matrix = np.asarray(
        [
            [a, b, pivot_x + position_x - a * pivot_x - b * pivot_y],
            [c, d, pivot_y + position_y - c * pivot_x - d * pivot_y],
        ],
        dtype=np.float32,
    )
    return cv2.warpAffine(
        source,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )


def composite_motion_clips(owner: Any, rgb, project_ms: int, *, cache_capacity: int = 90):
    """Composite active clips over an RGB uint8 frame using the owner's renderer cache."""
    import numpy as np

    clips = active_motion_clips(getattr(owner, "_motion_clips", []) or [], int(project_ms))
    if not clips:
        return rgb
    compositions = getattr(owner, "_motion_compositions", {}) or {}
    renderer = getattr(owner, "_motion_renderer", None)
    if renderer is None:
        renderer = MotionExportRenderer(cache_capacity=cache_capacity)
        owner._motion_renderer = renderer
    output = np.asarray(rgb, dtype=np.uint8).copy()
    height, width = output.shape[:2]
    for clip in clips:
        composition = compositions.get(clip.composition_id)
        if composition is None:
            continue
        rgba = renderer.render_rgba_array(
            composition,
            composition_time_ms(clip, composition, int(project_ms)),
            width=width,
            height=height,
        )
        rgba = transform_motion_actor_rgba(rgba, clip)
        opacity = max(0.0, min(1.0, float(clip.opacity)))
        color_settings = settings_from_composition_metadata(composition.metadata)
        if color_settings.blend_space == "linear-srgb":
            output = composite_premultiplied_srgb_over_srgb(output, rgba, opacity=opacity)
        else:
            alpha = rgba[..., 3:4].astype(np.float32) / 255.0 * opacity
            premultiplied_rgb = rgba[..., :3].astype(np.float32) * opacity
            output = np.clip(
                premultiplied_rgb + output.astype(np.float32) * (1.0 - alpha), 0, 255
            ).astype(np.uint8)
    return output
