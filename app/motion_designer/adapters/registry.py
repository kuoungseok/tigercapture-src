from __future__ import annotations

from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.mask_adapter import apply_masks
from app.motion_designer.schema import MotionLayer

from .image import render_image
from .shape import render_shape
from .typography import render_typography

def render_source(
    layer: MotionLayer,
    time_ms: float = 0.0,
    *,
    composition=None,
    composition_time_ms: float | None = None,
    quality: str = "preview",
    viewport_size: tuple[int, int] | None = None,
):
    if layer.layer_type == "image":
        image = render_image(layer, time_ms)
    elif layer.layer_type == "text":
        image = render_typography(layer, time_ms)
    elif layer.layer_type == "ar_pbr" or layer.source.kind == "ar_pbr":
        from .ar_pbr import render_ar_pbr

        image = render_ar_pbr(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "live2d_actor" or layer.source.kind == "live2d_actor":
        from .live2d import render_live2d

        image = render_live2d(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "spine_actor" or layer.source.kind == "spine_actor":
        from .spine import render_spine

        image = render_spine(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "mmd_actor" or layer.source.kind == "mmd_actor":
        from .mmd import render_mmd

        image = render_mmd(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "vrm_actor" or layer.source.kind == "vrm_actor":
        from .vrm import render_vrm

        image = render_vrm(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "particle" or layer.source.kind == "particle":
        from .particle import render_particle

        image = render_particle(
            layer, time_ms, composition=composition, composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "generator" or layer.source.kind == "generator":
        from .generator import render_generator

        image = render_generator(
            layer, time_ms, composition=composition,
            composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    elif layer.layer_type == "remotion_tsx" or layer.source.kind == "remotion_tsx":
        from .remotion_tsx import render_remotion_tsx

        image = render_remotion_tsx(
            layer, time_ms, composition=composition,
            composition_time_ms=composition_time_ms,
            quality=quality, viewport_size=viewport_size,
        )
    else:
        image = render_shape(layer, time_ms)
    return apply_effects(apply_masks(image, layer, time_ms), layer.effects, time_ms)
