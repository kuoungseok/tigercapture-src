from __future__ import annotations

from app.motion_designer.effect_adapter import apply_effects
from app.motion_designer.mask_adapter import apply_masks
from app.motion_designer.schema import MotionLayer

from .image import render_image
from .shape import render_shape
from .typography import render_typography

def render_source(layer: MotionLayer, time_ms: float = 0.0):
    if layer.layer_type == "image":
        image = render_image(layer)
    elif layer.layer_type == "text":
        image = render_typography(layer, time_ms)
    else:
        image = render_shape(layer, time_ms)
    return apply_effects(apply_masks(image, layer, time_ms), layer.effects, time_ms)
