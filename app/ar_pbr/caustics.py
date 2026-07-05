"""Conservative caustic highlight controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_CAUSTICS_MODE = "off"
DEFAULT_CAUSTICS_STRENGTH = 0.0
DEFAULT_CAUSTICS_QUALITY = "preview"
DEFAULT_CAUSTICS_SAMPLE_COUNT = 8
DEFAULT_CAUSTICS_SCALE = 28.0
DEFAULT_CAUSTICS_FOCUS = 0.55
DEFAULT_CAUSTICS_RADIUS = 0.82
DEFAULT_CAUSTICS_THRESHOLD = 0.32
DEFAULT_CAUSTICS_TINT = [1.0, 0.92, 0.68]
DEFAULT_CAUSTICS_SEED = 0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "caustic", "caustics", "glass"}:
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


def _int_value(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        out = int(round(float(value)))
    except Exception:
        out = int(default)
    return max(int(lo), min(int(hi), out))


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
        "caustics_rendering",
        "caustic_rendering",
        "caustics",
        "caustic",
        "glass_caustics",
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


def normalize_caustics_settings(value: Any) -> dict[str, Any]:
    """Normalize Marmoset-style caustic controls.

    The current packet renderer uses a deterministic highlight approximation
    for bright glass/specular/transmission pixels. True photon/path caustic
    transport remains a full ray-tracing contract.
    """
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("caustics_mode"),
        data.get("caustic_mode"),
        DEFAULT_CAUSTICS_MODE,
    )
    mode = str(raw_mode or DEFAULT_CAUSTICS_MODE).strip().casefold().replace("-", "_")
    if mode in {"glass", "refractive", "transmission", "surface", "highlights"}:
        mode = "caustics"
    if mode not in {"off", "caustics", "ray_traced", "path_traced"}:
        mode = DEFAULT_CAUSTICS_MODE

    raw_caustics = data.get("caustics", data.get("caustic"))
    enabled = _bool_value(
        _first_value(
            _nested(data, "enabled"),
            data.get("caustics_enabled"),
            data.get("caustic_enabled"),
            raw_caustics if isinstance(raw_caustics, bool) else None,
        ),
        mode in {"caustics", "ray_traced", "path_traced"},
    )
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount"),
            data.get("caustics_strength"),
            data.get("caustic_strength"),
            raw_caustics if not isinstance(raw_caustics, Mapping) else None,
        ),
        0.35 if enabled else DEFAULT_CAUSTICS_STRENGTH,
        0.0,
        2.0,
    )
    if strength > 0.0:
        enabled = True
        if mode == "off":
            mode = "caustics"

    quality = str(_first_value(
        _nested(data, "quality"),
        data.get("caustics_quality"),
        data.get("caustic_quality"),
        DEFAULT_CAUSTICS_QUALITY,
    ) or DEFAULT_CAUSTICS_QUALITY).strip().casefold().replace("-", "_")
    if quality not in {"low", "preview", "high", "ultra"}:
        quality = DEFAULT_CAUSTICS_QUALITY

    sample_default = {"low": 4, "preview": DEFAULT_CAUSTICS_SAMPLE_COUNT, "high": 24, "ultra": 48}.get(
        quality,
        DEFAULT_CAUSTICS_SAMPLE_COUNT,
    )
    sample_count = _int_value(
        _first_value(
            _nested(data, "sample_count", "samples", "photon_count"),
            data.get("caustics_sample_count"),
            data.get("caustic_sample_count"),
            data.get("caustics_samples"),
        ),
        sample_default,
        1,
        128,
    )
    scale = _float_value(
        _first_value(_nested(data, "scale", "frequency"), data.get("caustics_scale")),
        DEFAULT_CAUSTICS_SCALE,
        1.0,
        512.0,
    )
    focus = _float_value(
        _first_value(_nested(data, "focus", "sharpness"), data.get("caustics_focus")),
        DEFAULT_CAUSTICS_FOCUS,
        0.05,
        2.0,
    )
    radius = _float_value(
        _first_value(_nested(data, "radius", "spread"), data.get("caustics_radius")),
        DEFAULT_CAUSTICS_RADIUS,
        0.05,
        2.0,
    )
    threshold = _float_value(
        _first_value(_nested(data, "threshold", "cutoff"), data.get("caustics_threshold")),
        DEFAULT_CAUSTICS_THRESHOLD,
        0.0,
        1.0,
    )
    tint = _vec3_value(
        _first_value(_nested(data, "tint", "color"), data.get("caustics_tint"), data.get("caustics_color")),
        DEFAULT_CAUSTICS_TINT,
    )
    seed = _int_value(
        _first_value(_nested(data, "seed"), data.get("caustics_seed")),
        DEFAULT_CAUSTICS_SEED,
        0,
        2_147_483_647,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        sample_count = 1
    return {
        "schema": "tigerstudio.ar_pbr.caustics.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "quality": quality,
        "sample_count": int(sample_count),
        "scale": float(scale),
        "focus": float(focus),
        "radius": float(radius),
        "threshold": float(threshold),
        "tint": [float(v) for v in tint],
        "seed": int(seed),
        "packet_model": "deterministic_transmission_specular_caustic_highlight_ripples",
        "receiver_policy": "packet_highlights_on_visible_transmissive_or_specular_pixels",
        "ray_traced_policy": "contract_only_no_photon_or_path_caustic_transport",
        "full_gpu_policy": "contract_only_until_native_caustic_integrator",
        "render_pass_safe": True,
    }


def flatten_caustics_settings(value: Any) -> dict[str, Any]:
    settings = normalize_caustics_settings(value)
    return {
        "caustics_mode": settings["mode"],
        "caustics_enabled": settings["enabled"],
        "caustics_strength": settings["strength"],
        "caustics_quality": settings["quality"],
        "caustics_sample_count": settings["sample_count"],
        "caustics_scale": settings["scale"],
        "caustics_focus": settings["focus"],
        "caustics_radius": settings["radius"],
        "caustics_threshold": settings["threshold"],
        "caustics_tint": list(settings["tint"]),
        "caustics_seed": settings["seed"],
    }


def apply_caustic_highlights(
    rgb: Any,
    *,
    uv: tuple[Any, Any],
    world_pos: tuple[Any, Any, Any],
    ndotl: Any,
    ndotv: Any,
    roughness: Any,
    alpha: Any,
    transmission: Mapping[str, Any] | None,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    cfg = normalize_caustics_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "max_intensity": 0.0,
        "mean_intensity": 0.0,
    }
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return rgb, diagnostics
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
    if out.ndim != 3:
        return rgb, diagnostics
    shape = out.shape[:2]

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        return np.full(shape, float(default), dtype=np.float32)

    u = _arr(uv[0], 0.0)
    v = _arr(uv[1], 0.0)
    wx = _arr(world_pos[0], 0.0)
    wy = _arr(world_pos[1], 0.0)
    wz = _arr(world_pos[2], 0.0)
    rough = np.clip(_arr(roughness, 0.45), 0.0, 1.0)
    light = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    view = np.clip(_arr(ndotv, 0.0), 0.0, 1.0)
    mask = (np.asarray(alpha, dtype=np.float32) > 0.001).astype(np.float32)
    if mask.shape != shape:
        return rgb, diagnostics

    trans_cfg = transmission if isinstance(transmission, Mapping) else {}
    try:
        transmission_energy = max(
            float(trans_cfg.get("transmission", 0.0) or 0.0),
            float(trans_cfg.get("refraction_strength", 0.0) or 0.0) * 0.85,
        )
    except Exception:
        transmission_energy = 0.0
    try:
        ior_energy = max(0.0, min(1.0, (float(trans_cfg.get("ior", 1.45) or 1.45) - 1.0) / 0.65))
    except Exception:
        ior_energy = 0.65
    specular_energy = np.power(np.clip(light * view, 0.0, 1.0), 0.55) * np.power(1.0 - rough, 1.6)
    refractive_energy = np.clip(transmission_energy * (0.35 + 0.65 * ior_energy) * (1.0 - rough * 0.72), 0.0, 2.0)
    incident = np.clip(light * 0.75 + 0.25, 0.0, 1.0)
    specular_source = specular_energy * 0.58 * light
    refractive_source = refractive_energy * incident
    source_energy = np.maximum(specular_source, refractive_source) * mask

    threshold = float(cfg["threshold"])
    active = source_energy > threshold * 0.35
    if not bool(active.any()):
        return out, diagnostics

    seed = float(int(cfg["seed"]) % 100_000) * 0.0137
    scale = float(cfg["scale"])
    px = (u * 1.31 + wx * 0.47 + wz * 0.19 + seed) * scale
    py = (v * 1.17 + wy * 0.43 - wz * 0.23 - seed * 0.37) * scale
    ripple_a = 1.0 - np.abs(np.sin(px + np.sin(py * 0.73 + seed)))
    ripple_b = 1.0 - np.abs(np.sin((px * 0.61 - py * 0.82) + np.cos(px * 0.19)))
    ripple_c = 1.0 - np.abs(np.sin((px + py) * 0.37 + seed * 1.7))
    ridges = np.clip((ripple_a * 0.50 + ripple_b * 0.32 + ripple_c * 0.18 - threshold) / max(1.0 - threshold, 1e-6), 0.0, 1.0)
    ridges = np.power(ridges, max(0.08, float(cfg["focus"])))
    radial = np.sqrt(np.square(u - 0.5) + np.square(v - 0.55))
    radius_mask = np.clip((float(cfg["radius"]) - radial) / max(float(cfg["radius"]), 1e-6), 0.0, 1.0)
    sample_gain = min(1.35, 0.82 + int(cfg["sample_count"]) / 64.0)
    intensity = ridges * radius_mask * source_energy * float(cfg["strength"]) * sample_gain
    intensity = np.where(active, intensity, 0.0)
    changed = intensity > 0.002
    if not bool(changed.any()):
        return out, diagnostics

    tint = np.asarray(cfg["tint"], dtype=np.float32)
    out = out + intensity[:, :, None] * tint[None, None, :]
    diagnostics.update({
        "applied": True,
        "pixels": int(active.sum()),
        "changed_pixels": int(changed.sum()),
        "max_intensity": float(np.max(intensity)),
        "mean_intensity": float(np.mean(intensity[changed])),
    })
    return out, diagnostics
