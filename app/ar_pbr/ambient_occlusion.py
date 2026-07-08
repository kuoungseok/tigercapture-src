"""Screen-space ambient occlusion controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_AMBIENT_OCCLUSION_MODE = "off"
DEFAULT_AO_STRENGTH = 0.0
DEFAULT_AO_ACTIVE_STRENGTH = 0.65
DEFAULT_AO_RADIUS = 3.0
DEFAULT_AO_DISTANCE = 0.45
DEFAULT_AO_COLOR = [0.0, 0.0, 0.0]
DEFAULT_AO_AMBIENT = True
DEFAULT_AO_DIFFUSE = True
DEFAULT_AO_SPECULAR = False


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "screen", "ssao", "ray_traced", "raytraced"}:
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
        "ambient_occlusion_rendering",
        "ambient_occlusion",
        "screen_ao",
        "ssao",
        "ao",
        "occlusion",
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


def _color3(value: Any, default: list[float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        raw = source[idx] if idx < len(source) else default[idx]
        out.append(_float_value(raw, default[idx], 0.0, 1.0))
    return out


def normalize_ambient_occlusion_settings(value: Any) -> dict[str, Any]:
    """Normalize Marmoset-style screen/ray-traced AO controls."""
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode", "ambient_occlusion_mode", "ao_mode"),
        data.get("ambient_occlusion_mode"),
        data.get("ao_mode"),
        DEFAULT_AMBIENT_OCCLUSION_MODE,
    )
    mode = str(raw_mode or DEFAULT_AMBIENT_OCCLUSION_MODE).strip().casefold().replace("-", "_").replace(" ", "_")
    if mode in {"ssao", "screen_space", "screen_space_ao"}:
        mode = "screen"
    if mode in {"raytrace", "ray_tracing", "raytracing", "raytraced"}:
        mode = "ray_traced"
    if mode not in {"off", "screen", "ray_traced"}:
        mode = DEFAULT_AMBIENT_OCCLUSION_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled", "ao_enabled", "ambient_occlusion_enabled"),
        data.get("ao_enabled"),
        data.get("ambient_occlusion_enabled"),
    )
    strength_raw = _first_value(
        _nested(data, "strength", "ao_strength", "ambient_occlusion_strength", "occlusion_strength"),
        data.get("ao_strength"),
        data.get("ambient_occlusion_strength"),
    )
    strength_default = (
        DEFAULT_AO_ACTIVE_STRENGTH
        if strength_raw is None and (mode != "off" or _bool_value(enabled_raw, False))
        else DEFAULT_AO_STRENGTH
    )
    strength = _float_value(
        strength_raw,
        strength_default,
        0.0,
        2.0,
    )
    enabled = _bool_value(
        enabled_raw,
        mode != "off" or strength > 0.0,
    )
    if enabled and mode == "off":
        mode = "screen"
    if not enabled:
        mode = "off"
        strength = 0.0

    radius = _float_value(
        _first_value(_nested(data, "radius", "ao_radius", "occlusion_size"), data.get("ao_radius")),
        DEFAULT_AO_RADIUS,
        0.5,
        32.0,
    )
    distance = _float_value(
        _first_value(_nested(data, "distance", "ao_distance", "ray_distance"), data.get("ao_distance")),
        DEFAULT_AO_DISTANCE,
        0.01,
        4.0,
    )
    color = _color3(
        _first_value(_nested(data, "color", "ao_color", "ambient_occlusion_color"), data.get("ao_color")),
        list(DEFAULT_AO_COLOR),
    )
    ambient = _bool_value(
        _first_value(_nested(data, "ambient", "ambient_occlusion_ambient"), data.get("ao_ambient")),
        DEFAULT_AO_AMBIENT,
    )
    diffuse = _bool_value(
        _first_value(_nested(data, "diffuse", "ambient_occlusion_diffuse"), data.get("ao_diffuse")),
        DEFAULT_AO_DIFFUSE,
    )
    specular = _bool_value(
        _first_value(_nested(data, "specular", "ambient_occlusion_specular"), data.get("ao_specular")),
        DEFAULT_AO_SPECULAR,
    )

    return {
        "schema": "tigerstudio.ar_pbr.ambient_occlusion.v1",
        "mode": mode,
        "enabled": bool(mode != "off" and strength > 0.0),
        "strength": float(strength),
        "radius": float(radius),
        "distance": float(distance),
        "color": color,
        "ambient": bool(ambient),
        "diffuse": bool(diffuse),
        "specular": bool(specular),
        "screen_model": "alpha_depth_edge_aware_screen_space_occlusion",
        "ray_traced_policy": "contract_only_packet_export_uses_screen_approximation",
        "render_pass": "ambient_occlusion",
        "render_pass_safe": True,
    }


def normalize_packet_ambient_occlusion_settings(
    item: Any,
    lighting: Any | None = None,
) -> dict[str, Any]:
    """Normalize AO settings from an AR/PBR preview/export packet.

    GPU preview packets carry the canonical AO contract at item level while
    older paths only carry flattened ``ao_*`` keys inside ``pbr_lighting``.
    This helper keeps live preview and export/bake paths on the same lookup
    order.
    """
    data = _as_mapping(item)
    packet_settings = data.get("ambient_occlusion_rendering")
    if isinstance(packet_settings, Mapping):
        return normalize_ambient_occlusion_settings(packet_settings)
    if lighting is None:
        lighting = data.get("pbr_lighting")
    return normalize_ambient_occlusion_settings(lighting)


def flatten_ambient_occlusion_settings(value: Any) -> dict[str, Any]:
    settings = normalize_ambient_occlusion_settings(value)
    return {
        "ambient_occlusion_mode": settings["mode"],
        "ambient_occlusion_enabled": settings["enabled"],
        "ao_strength": settings["strength"],
        "ao_radius": settings["radius"],
        "ao_distance": settings["distance"],
        "ao_color": list(settings["color"]),
        "ao_ambient": settings["ambient"],
        "ao_diffuse": settings["diffuse"],
        "ao_specular": settings["specular"],
    }


def apply_screen_ambient_occlusion_to_overlay(
    overlay: Any,
    settings: Mapping[str, Any] | None,
    depth_map: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """Apply a deterministic screen-space AO approximation to overlay pixels."""
    cfg = normalize_ambient_occlusion_settings(settings or {})
    diagnostics: dict[str, Any] = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "pass_min": 1.0,
        "pass_mean": 1.0,
        "pass_max": 1.0,
    }
    if not bool(cfg["enabled"]):
        return overlay, diagnostics
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception as exc:
        diagnostics["warnings"] = [f"ambient occlusion skipped: {type(exc).__name__}: {exc}"]
        return overlay, diagnostics

    try:
        image = overlay.convert("RGBA") if hasattr(overlay, "convert") else Image.fromarray(overlay, "RGBA")
        arr = np.asarray(image, dtype=np.float32) / 255.0
        alpha = np.clip(arr[:, :, 3], 0.0, 1.0)
        active = alpha > 0.001
        if not bool(active.any()):
            return overlay, diagnostics

        radius = float(cfg["radius"])
        alpha_img = Image.fromarray(np.clip(alpha * 255.0, 0, 255).astype(np.uint8), "L")
        local_fill = np.asarray(alpha_img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0
        wider_fill = np.asarray(alpha_img.filter(ImageFilter.GaussianBlur(radius=radius * 2.0)), dtype=np.float32) / 255.0
        cavity = np.clip(local_fill - wider_fill * 0.42, 0.0, 1.0)
        edge = np.clip(local_fill * (1.0 - alpha), 0.0, 1.0)
        ao = np.clip(cavity + edge * 0.72, 0.0, 1.0)

        if depth_map is not None:
            depth = np.asarray(depth_map, dtype=np.float32)
            if depth.ndim == 2:
                if depth.shape != alpha.shape:
                    depth_img = Image.fromarray(np.clip(depth * 255.0, 0, 255).astype(np.uint8), "L")
                    depth = np.asarray(depth_img.resize(image.size, Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
                gy, gx = np.gradient(np.nan_to_num(depth, nan=1.0, posinf=1.0, neginf=0.0))
                depth_edges = np.clip((np.abs(gx) + np.abs(gy)) / max(0.01, float(cfg["distance"])), 0.0, 1.0)
                ao = np.clip(ao + depth_edges * alpha * 0.38, 0.0, 1.0)

        strength = float(cfg["strength"])
        occlusion = np.clip(1.0 - ao * strength, 0.0, 1.0)
        color = np.asarray(cfg["color"], dtype=np.float32).reshape(1, 1, 3)
        rgb = arr[:, :, :3]
        shaded = rgb * occlusion[:, :, None] + color * (1.0 - occlusion[:, :, None]) * 0.18
        changed = (np.max(np.abs(shaded - rgb), axis=2) > (1.0 / 255.0)) & active
        out = np.dstack((np.where(active[:, :, None], shaded, rgb), alpha))

        active_ao = occlusion[active]
        diagnostics["applied"] = bool(changed.any())
        diagnostics["pixels"] = int(active.sum())
        diagnostics["changed_pixels"] = int(changed.sum())
        diagnostics["pass_min"] = float(active_ao.min()) if active_ao.size else 1.0
        diagnostics["pass_mean"] = float(active_ao.mean()) if active_ao.size else 1.0
        diagnostics["pass_max"] = float(active_ao.max()) if active_ao.size else 1.0
        return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), "RGBA"), diagnostics
    except Exception as exc:
        diagnostics["warnings"] = [f"ambient occlusion skipped: {type(exc).__name__}: {exc}"]
        return overlay, diagnostics
