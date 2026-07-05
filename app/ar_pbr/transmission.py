"""Transmission and refraction controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_TRANSMISSION_MODE = "off"
DEFAULT_TRANSMISSION = 0.0
DEFAULT_REFRACTION_STRENGTH = 0.0
DEFAULT_REFRACTION_DEPTH_PX = 6.0
DEFAULT_IOR = 1.45
DEFAULT_THICKNESS = 0.05
DEFAULT_ABSORPTION_COLOR = [1.0, 1.0, 1.0]
DEFAULT_ABSORPTION_DISTANCE = 1.0
DEFAULT_ROUGHNESS_BLUR_STRENGTH = 0.0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "glass", "transmission", "refraction"}:
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
    for container_key in ("transmission_rendering", "transmission", "refraction", "glass"):
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


def normalize_transmission_settings(value: Any) -> dict[str, Any]:
    """Normalize optional glass/transmission controls.

    This is a realtime-friendly approximation: packet export uses
    screen-space background sampling, while live/full GPU shaders sample the
    environment along a refracted direction.
    """
    data = _as_mapping(value)
    transmission_raw = data.get("transmission")
    refraction_raw = data.get("refraction")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("transmission_mode"),
        data.get("refraction_mode"),
        DEFAULT_TRANSMISSION_MODE,
    )
    mode = str(raw_mode or DEFAULT_TRANSMISSION_MODE).strip().casefold().replace("-", "_")
    if mode in {"transparent", "transmissive", "screen_space", "screen_space_refraction"}:
        mode = "transmission"
    if mode not in {"off", "transmission", "refraction", "glass"}:
        mode = DEFAULT_TRANSMISSION_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("transmission_enabled"),
        data.get("refraction_enabled"),
        transmission_raw if isinstance(transmission_raw, bool) else None,
        refraction_raw if isinstance(refraction_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode in {"transmission", "refraction", "glass"})
    transmission = _float_value(
        _first_value(
            _nested(data, "transmission", "amount", "strength"),
            data.get("transmission_factor"),
            data.get("transmission_strength"),
            transmission_raw if not isinstance(transmission_raw, Mapping) else None,
        ),
        0.55 if enabled else DEFAULT_TRANSMISSION,
        0.0,
        1.0,
    )
    refraction_strength = _float_value(
        _first_value(
            _nested(data, "refraction_strength", "refraction", "distortion"),
            data.get("screen_space_refraction_strength"),
            refraction_raw if not isinstance(refraction_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_REFRACTION_STRENGTH,
        0.0,
        1.0,
    )
    if transmission > 0.0 or refraction_strength > 0.0:
        enabled = True
        if mode == "off":
            mode = "transmission" if transmission >= refraction_strength else "refraction"
    ior = _float_value(
        _first_value(_nested(data, "ior", "index_of_refraction"), data.get("ior"), data.get("index_of_refraction")),
        DEFAULT_IOR,
        1.0,
        2.5,
    )
    thickness = _float_value(
        _first_value(
            _nested(data, "thickness", "volume_thickness", "transmission_thickness"),
            data.get("volume_thickness"),
        ),
        DEFAULT_THICKNESS,
        0.0,
        4.0,
    )
    absorption_color = _vec3_value(
        _first_value(
            _nested(data, "absorption_color", "attenuation_color", "transmission_color"),
            data.get("attenuation_color"),
        ),
        DEFAULT_ABSORPTION_COLOR,
    )
    absorption_distance = _float_value(
        _first_value(_nested(data, "absorption_distance", "attenuation_distance"), data.get("attenuation_distance")),
        DEFAULT_ABSORPTION_DISTANCE,
        0.001,
        64.0,
    )
    refraction_depth_px = _float_value(
        _first_value(
            _nested(data, "refraction_depth_px", "max_refraction_pixels", "screen_space_refraction_pixels"),
            data.get("refraction_depth_px"),
        ),
        DEFAULT_REFRACTION_DEPTH_PX,
        0.0,
        64.0,
    )
    roughness_blur = _float_value(
        _first_value(
            _nested(data, "roughness_blur_strength", "background_blur_strength", "transmission_roughness_blur"),
            data.get("roughness_blur_strength"),
        ),
        DEFAULT_ROUGHNESS_BLUR_STRENGTH,
        0.0,
        1.0,
    )
    if not enabled:
        mode = "off"
        transmission = 0.0
        refraction_strength = 0.0
        refraction_depth_px = 0.0
        roughness_blur = 0.0
    return {
        "schema": "tigerstudio.ar_pbr.transmission.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "transmission": float(transmission),
        "refraction_strength": float(refraction_strength),
        "refraction_depth_px": float(refraction_depth_px),
        "ior": float(ior),
        "thickness": float(thickness),
        "absorption_color": [float(v) for v in absorption_color],
        "absorption_distance": float(absorption_distance),
        "roughness_blur_strength": float(roughness_blur),
        "screen_space_model": "normal_offset_background_sampling",
        "environment_model": "refracted_environment_sampling",
        "alpha_policy": "baked_refraction_preserve_coverage",
        "render_pass_safe": True,
    }


def flatten_transmission_settings(value: Any) -> dict[str, Any]:
    settings = normalize_transmission_settings(value)
    return {
        "transmission_mode": settings["mode"],
        "transmission_enabled": settings["enabled"],
        "transmission": settings["transmission"],
        "refraction_strength": settings["refraction_strength"],
        "refraction_depth_px": settings["refraction_depth_px"],
        "ior": settings["ior"],
        "thickness": settings["thickness"],
        "absorption_color": list(settings["absorption_color"]),
        "absorption_distance": settings["absorption_distance"],
        "roughness_blur_strength": settings["roughness_blur_strength"],
    }


def _blur_rgb(arr: Any) -> Any:
    import numpy as np

    padded = np.pad(arr, ((1, 1), (1, 1), (0, 0)), mode="edge")
    return (
        padded[0:-2, 0:-2] + padded[0:-2, 1:-1] * 2.0 + padded[0:-2, 2:]
        + padded[1:-1, 0:-2] * 2.0 + padded[1:-1, 1:-1] * 4.0 + padded[1:-1, 2:] * 2.0
        + padded[2:, 0:-2] + padded[2:, 1:-1] * 2.0 + padded[2:, 2:]
    ) / 16.0


def apply_screen_space_refraction(
    rgb: Any,
    *,
    alpha: Any,
    background_rgba: Any,
    normal_xy: tuple[Any, Any],
    roughness: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_transmission_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["transmission"]) <= 0.0:
        return rgb
    import numpy as np

    arr = np.asarray(rgb, dtype=np.float32)
    bg = np.asarray(background_rgba, dtype=np.float32)
    if bg.ndim != 3 or bg.shape[2] < 3 or arr.ndim != 3 or arr.shape[:2] != bg.shape[:2]:
        return arr
    bg_rgb = np.clip(bg[:, :, :3], 0.0, 1.0)
    h, w = arr.shape[:2]
    if h <= 0 or w <= 0:
        return arr
    nx = np.asarray(normal_xy[0], dtype=np.float32)
    ny = np.asarray(normal_xy[1], dtype=np.float32)
    rough = np.clip(np.asarray(roughness, dtype=np.float32), 0.0, 1.0)
    mask = (np.asarray(alpha, dtype=np.float32) > 0.001).astype(np.float32)
    if nx.shape != (h, w) or ny.shape != (h, w) or rough.shape != (h, w) or mask.shape != (h, w):
        return arr
    ior_bend = np.clip((float(cfg["ior"]) - 1.0) / 0.8, 0.0, 1.5)
    max_offset = float(cfg["refraction_depth_px"]) * float(cfg["refraction_strength"]) * ior_bend
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    offset = max_offset * (1.0 - rough * 0.55)
    sx = np.clip(np.rint(xx + nx * offset), 0, w - 1).astype(np.int32)
    sy = np.clip(np.rint(yy - ny * offset), 0, h - 1).astype(np.int32)
    refracted = bg_rgb[sy, sx]
    rough_blur = float(cfg["roughness_blur_strength"])
    if rough_blur > 0.0:
        blurred = _blur_rgb(bg_rgb)
        blur_mix = np.clip(rough * rough_blur, 0.0, 1.0)[:, :, None]
        refracted = refracted * (1.0 - blur_mix) + blurred * blur_mix
    absorption = np.asarray(cfg["absorption_color"], dtype=np.float32)
    density = float(cfg["thickness"]) / max(0.001, float(cfg["absorption_distance"]))
    tint = np.exp(-np.maximum(0.0, 1.0 - absorption) * density * 2.0)
    refracted = refracted * tint[None, None, :]
    through = np.clip(float(cfg["transmission"]) * mask, 0.0, 1.0)[:, :, None]
    return arr * (1.0 - through) + refracted * through
