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
