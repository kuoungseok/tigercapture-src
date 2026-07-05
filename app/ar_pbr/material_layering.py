"""Single-layer material blending controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_MATERIAL_LAYER_MODE = "off"
DEFAULT_MATERIAL_LAYER_BLEND = 0.0
DEFAULT_MATERIAL_LAYER_COLOR = [1.0, 1.0, 1.0]
DEFAULT_MATERIAL_LAYER_ROUGHNESS = 0.5
DEFAULT_MATERIAL_LAYER_METALLIC = 0.0
DEFAULT_MATERIAL_LAYER_ALPHA = 1.0
DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH = 0.0
DEFAULT_MATERIAL_LAYER_MASK_STRENGTH = 1.0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "layer", "layered", "material_layer"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "none"}:
        return False
    return bool(default)


def _float_value(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "material_layering",
        "material_layer",
        "layered_material",
        "layer",
        "overlay_material",
    ):
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def _vec3_value(value: Any, default: list[float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        fallback = float(default[idx] if idx < len(default) else 1.0)
        raw = source[idx] if idx < len(source) else fallback
        out.append(_float_value(raw, fallback, 0.0, 1.0))
    return out


def normalize_material_layering_settings(value: Any) -> dict[str, Any]:
    """Normalize optional material layering controls.

    This is a realtime approximation of a material stack: one overlay layer is
    mixed into the sampled base material in shading space. It does not create
    additional geometry, per-slot draw calls, or a full node graph.
    """
    data = _as_mapping(value)
    layer_raw = data.get("material_layer")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("material_layer_mode"),
        data.get("layer_mode"),
        DEFAULT_MATERIAL_LAYER_MODE,
    )
    mode = str(raw_mode or DEFAULT_MATERIAL_LAYER_MODE).strip().casefold().replace("-", "_")
    if mode in {"layer", "layered", "overlay", "blend", "material_stack"}:
        mode = "layered"
    if mode not in {"off", "layered"}:
        mode = DEFAULT_MATERIAL_LAYER_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("material_layer_enabled"),
        data.get("layer_enabled"),
        layer_raw if isinstance(layer_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "layered")
    blend = _float_value(
        _first_value(
            _nested(data, "blend", "opacity", "strength", "factor", "material_layer_blend"),
            data.get("material_layer_blend"),
            data.get("layer_blend"),
            layer_raw if not isinstance(layer_raw, Mapping) else None,
        ),
        0.5 if enabled else DEFAULT_MATERIAL_LAYER_BLEND,
        0.0,
        1.0,
    )
    if blend > 0.0:
        enabled = True
        mode = "layered"

    color = _vec3_value(
        _first_value(
            _nested(data, "color", "base_color", "tint", "material_layer_color"),
            data.get("material_layer_color"),
            data.get("layer_color"),
        ),
        DEFAULT_MATERIAL_LAYER_COLOR,
    )
    roughness = _float_value(
        _first_value(
            _nested(data, "roughness", "material_layer_roughness", "layer_roughness"),
            data.get("material_layer_roughness"),
            data.get("layer_roughness"),
        ),
        DEFAULT_MATERIAL_LAYER_ROUGHNESS,
        0.04,
        1.0,
    )
    metallic = _float_value(
        _first_value(
            _nested(data, "metallic", "metalness", "material_layer_metallic", "layer_metallic"),
            data.get("material_layer_metallic"),
            data.get("layer_metallic"),
        ),
        DEFAULT_MATERIAL_LAYER_METALLIC,
        0.0,
        1.0,
    )
    alpha = _float_value(
        _first_value(
            _nested(data, "alpha", "coverage", "material_layer_alpha", "layer_alpha"),
            data.get("material_layer_alpha"),
            data.get("layer_alpha"),
        ),
        DEFAULT_MATERIAL_LAYER_ALPHA,
        0.0,
        1.0,
    )
    emissive_strength = _float_value(
        _first_value(
            _nested(data, "emissive_strength", "emission", "material_layer_emissive_strength"),
            data.get("material_layer_emissive_strength"),
            data.get("layer_emissive_strength"),
        ),
        DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH,
        0.0,
        4.0,
    )
    mask_strength = _float_value(
        _first_value(
            _nested(data, "mask_strength", "mask", "material_layer_mask_strength"),
            data.get("material_layer_mask_strength"),
            data.get("layer_mask_strength"),
        ),
        DEFAULT_MATERIAL_LAYER_MASK_STRENGTH,
        0.0,
        1.0,
    )
    if not enabled:
        mode = "off"
        blend = 0.0
        emissive_strength = 0.0
        mask_strength = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.material_layering.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "blend": float(blend),
        "color": [float(v) for v in color],
        "roughness": float(roughness),
        "metallic": float(metallic),
        "alpha": float(alpha),
        "emissive_strength": float(emissive_strength),
        "mask_strength": float(mask_strength),
        "layer_model": "single_overlay_material_layer",
        "blend_model": "base_material_to_overlay_lerp",
        "texture_policy": "shares_base_uv_without_independent_layer_textures",
        "stack_policy": "one_layer_preview_approximation",
        "render_pass_safe": True,
    }


def flatten_material_layering_settings(value: Any) -> dict[str, Any]:
    settings = normalize_material_layering_settings(value)
    return {
        "material_layer_mode": settings["mode"],
        "material_layer_enabled": settings["enabled"],
        "material_layer_blend": settings["blend"],
        "material_layer_color": list(settings["color"]),
        "material_layer_roughness": settings["roughness"],
        "material_layer_metallic": settings["metallic"],
        "material_layer_alpha": settings["alpha"],
        "material_layer_emissive_strength": settings["emissive_strength"],
        "material_layer_mask_strength": settings["mask_strength"],
    }


def apply_material_layer(
    albedo: Any,
    roughness: Any,
    metallic: Any,
    alpha: Any,
    emissive: Any,
    *,
    mask: Any = None,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, Any, Any, Any, Any]:
    cfg = normalize_material_layering_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["blend"]) <= 0.0:
        return albedo, roughness, metallic, alpha, emissive
    import numpy as np

    base = np.asarray(albedo, dtype=np.float32)
    rough = np.asarray(roughness, dtype=np.float32)
    metal = np.asarray(metallic, dtype=np.float32)
    coverage = np.asarray(alpha, dtype=np.float32)
    emit = np.asarray(emissive, dtype=np.float32)
    if base.ndim != 3 or base.shape[2] < 3:
        return albedo, roughness, metallic, alpha, emissive
    shape = base.shape[:2]
    if rough.shape != shape or metal.shape != shape or coverage.shape != shape or emit.shape[:2] != shape:
        return albedo, roughness, metallic, alpha, emissive
    if mask is None:
        mask_arr = np.ones(shape, dtype=np.float32)
    else:
        mask_arr = np.asarray(mask, dtype=np.float32)
        if mask_arr.shape != shape:
            return albedo, roughness, metallic, alpha, emissive
    layer = np.clip(mask_arr * float(cfg["mask_strength"]) * float(cfg["blend"]), 0.0, 1.0)
    layer3 = layer[:, :, None]
    # Color controls are authored as display values; the renderer works in
    # scene-linear space.
    color = np.power(np.asarray(cfg["color"], dtype=np.float32), 2.2)
    layer_color = color[None, None, :]
    out_albedo = base * (1.0 - layer3) + layer_color * layer3
    out_roughness = rough * (1.0 - layer) + float(cfg["roughness"]) * layer
    out_metallic = metal * (1.0 - layer) + float(cfg["metallic"]) * layer
    out_alpha = coverage * (1.0 - layer + layer * float(cfg["alpha"]))
    out_emissive = emit + layer_color * (float(cfg["emissive_strength"]) * layer3)
    return (
        np.clip(out_albedo, 0.0, 16.0),
        np.clip(out_roughness, 0.04, 1.0),
        np.clip(out_metallic, 0.0, 1.0),
        np.clip(out_alpha, 0.0, 1.0),
        np.clip(out_emissive, 0.0, 16.0),
    )
