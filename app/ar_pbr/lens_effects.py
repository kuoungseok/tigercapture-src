"""Camera/lens post effects for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_LENS_EFFECTS_MODE = "off"
DEFAULT_LENS_DISTORTION_STRENGTH = 0.0
DEFAULT_LENS_DISTORTION_K2 = 0.0
DEFAULT_CHROMATIC_ABERRATION_STRENGTH = 0.0
DEFAULT_CHROMATIC_ABERRATION_PX = 0.0
DEFAULT_LENS_EDGE_FALLOFF = 1.0
DEFAULT_LENS_CENTER = [0.5, 0.5]


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "lens", "camera", "distortion", "chromatic"}:
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


def _vec2(value: Any, default: list[float] | None = None) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else (default or DEFAULT_LENS_CENTER)
    out: list[float] = []
    for idx in range(2):
        try:
            out.append(max(0.0, min(1.0, float(source[idx]))))
        except Exception:
            out.append(float((default or DEFAULT_LENS_CENTER)[idx]))
    return out


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "lens_effects_rendering",
        "lens_effects",
        "lens_post",
        "camera_lens",
        "lens",
        "distortion",
        "chromatic_aberration",
        "camera_post",
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


def _nested_from(data: Mapping[str, Any], container_keys: tuple[str, ...], *keys: str) -> Any:
    for container_key in container_keys:
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def normalize_lens_effects_settings(value: Any) -> dict[str, Any]:
    """Normalize barrel/pincushion distortion and chromatic aberration controls."""
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode", "lens_effects_mode"),
        data.get("lens_effects_mode"),
        data.get("lens_distortion_mode"),
        DEFAULT_LENS_EFFECTS_MODE,
    )
    mode = str(raw_mode or DEFAULT_LENS_EFFECTS_MODE).strip().casefold().replace("-", "_").replace(" ", "_")
    if mode in {"lens", "camera", "camera_post", "distortion", "chromatic", "chromatic_aberration"}:
        mode = "lens_effects"
    if mode not in {"off", "lens_effects"}:
        mode = DEFAULT_LENS_EFFECTS_MODE

    distortion_strength = _float_value(
        _first_value(
            _nested_from(
                data,
                (
                    "lens_effects_rendering",
                    "lens_effects",
                    "lens_post",
                    "camera_lens",
                    "lens",
                    "distortion",
                    "camera_post",
                ),
                "distortion_strength",
                "lens_distortion_strength",
                "barrel",
                "pincushion",
                "k1",
                "strength",
            ),
            data.get("lens_distortion_strength"),
            data.get("distortion_strength"),
            data.get("lens_distortion_k1"),
        ),
        DEFAULT_LENS_DISTORTION_STRENGTH,
        -1.0,
        1.0,
    )
    distortion_k2 = _float_value(
        _first_value(
            _nested(data, "distortion_k2", "k2"),
            data.get("lens_distortion_k2"),
        ),
        DEFAULT_LENS_DISTORTION_K2,
        -1.0,
        1.0,
    )
    distortion_enabled = _bool_value(
        _first_value(
            _nested(data, "distortion_enabled", "lens_distortion_enabled"),
            data.get("lens_distortion_enabled"),
        ),
        abs(distortion_strength) > 1.0e-6 or abs(distortion_k2) > 1.0e-6,
    )
    if distortion_enabled and abs(distortion_strength) <= 1.0e-6 and abs(distortion_k2) <= 1.0e-6:
        distortion_strength = 0.12
    if not distortion_enabled:
        distortion_strength = 0.0
        distortion_k2 = 0.0

    chromatic_strength = _float_value(
        _first_value(
            _nested_from(
                data,
                (
                    "lens_effects_rendering",
                    "lens_effects",
                    "lens_post",
                    "camera_lens",
                    "lens",
                    "chromatic_aberration",
                    "camera_post",
                ),
                "chromatic_aberration_strength",
                "chromatic_strength",
                "fringe_strength",
                "strength",
            ),
            data.get("chromatic_aberration_strength"),
            data.get("ca_strength"),
        ),
        DEFAULT_CHROMATIC_ABERRATION_STRENGTH,
        0.0,
        1.0,
    )
    chromatic_px = _float_value(
        _first_value(
            _nested(data, "chromatic_aberration_px", "fringe_px", "rgb_offset_px"),
            data.get("chromatic_aberration_px"),
            data.get("ca_px"),
        ),
        DEFAULT_CHROMATIC_ABERRATION_PX,
        0.0,
        16.0,
    )
    chromatic_enabled = _bool_value(
        _first_value(
            _nested(data, "chromatic_aberration_enabled", "chromatic_enabled", "ca_enabled"),
            data.get("chromatic_aberration_enabled"),
            data.get("ca_enabled"),
        ),
        chromatic_strength > 0.0 or chromatic_px > 0.0,
    )
    if chromatic_enabled and chromatic_strength <= 0.0 and chromatic_px <= 0.0:
        chromatic_strength = 0.35
        chromatic_px = 2.0
    elif chromatic_enabled and chromatic_strength <= 0.0:
        chromatic_strength = 1.0
    elif chromatic_enabled and chromatic_px <= 0.0:
        chromatic_px = max(0.5, chromatic_strength * 6.0)
    if not chromatic_enabled:
        chromatic_strength = 0.0
        chromatic_px = 0.0

    edge_falloff = _float_value(
        _first_value(_nested(data, "edge_falloff", "falloff"), data.get("lens_edge_falloff")),
        DEFAULT_LENS_EDGE_FALLOFF,
        0.1,
        4.0,
    )
    center = _vec2(
        _first_value(
            _nested(data, "center", "lens_center"),
            data.get("lens_center"),
            data.get("distortion_center"),
        ),
        DEFAULT_LENS_CENTER,
    )

    enabled = bool(distortion_enabled or chromatic_enabled or mode == "lens_effects")
    if not enabled:
        mode = "off"
    else:
        mode = "lens_effects"
    if not distortion_enabled and not chromatic_enabled:
        enabled = False
        mode = "off"

    distortion_type = "neutral"
    if distortion_strength > 0.0:
        distortion_type = "barrel"
    elif distortion_strength < 0.0:
        distortion_type = "pincushion"

    return {
        "schema": "tigerstudio.ar_pbr.lens_effects.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "distortion_enabled": bool(distortion_enabled),
        "distortion_strength": float(distortion_strength),
        "distortion_k1": float(distortion_strength),
        "distortion_k2": float(distortion_k2),
        "distortion_type": distortion_type,
        "chromatic_aberration_enabled": bool(chromatic_enabled),
        "chromatic_aberration_strength": float(chromatic_strength),
        "chromatic_aberration_px": float(chromatic_px),
        "center": center,
        "edge_falloff": float(edge_falloff),
        "post_model": "camera_post_radial_lens_distortion_chromatic_aberration",
        "distortion_model": "inverse_radial_uv_warp_barrel_pincushion",
        "chromatic_model": "radial_rgb_channel_offset",
        "render_pass_policy": "beauty_only_skip_data_passes",
        "alpha_policy": "preserve_existing_alpha",
        "render_pass_safe": True,
    }


def flatten_lens_effects_settings(value: Any) -> dict[str, Any]:
    settings = normalize_lens_effects_settings(value)
    return {
        "lens_effects_mode": settings["mode"],
        "lens_effects_enabled": settings["enabled"],
        "lens_distortion_enabled": settings["distortion_enabled"],
        "lens_distortion_strength": settings["distortion_strength"],
        "lens_distortion_k1": settings["distortion_k1"],
        "lens_distortion_k2": settings["distortion_k2"],
        "chromatic_aberration_enabled": settings["chromatic_aberration_enabled"],
        "chromatic_aberration_strength": settings["chromatic_aberration_strength"],
        "chromatic_aberration_px": settings["chromatic_aberration_px"],
        "lens_center": list(settings["center"]),
        "lens_edge_falloff": settings["edge_falloff"],
    }


def _bilinear_sample(arr: Any, x: Any, y: Any, channel: int):
    import numpy as np

    height, width = arr.shape[:2]
    x = np.clip(x, 0.0, float(width - 1))
    y = np.clip(y, 0.0, float(height - 1))
    x0 = np.floor(x).astype(np.int32)
    y0 = np.floor(y).astype(np.int32)
    x1 = np.clip(x0 + 1, 0, width - 1)
    y1 = np.clip(y0 + 1, 0, height - 1)
    wx = x - x0
    wy = y - y0
    c00 = arr[y0, x0, channel]
    c10 = arr[y0, x1, channel]
    c01 = arr[y1, x0, channel]
    c11 = arr[y1, x1, channel]
    return (
        c00 * (1.0 - wx) * (1.0 - wy)
        + c10 * wx * (1.0 - wy)
        + c01 * (1.0 - wx) * wy
        + c11 * wx * wy
    )


def apply_lens_effects_to_image(image: Any, settings: Mapping[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    """Apply deterministic lens distortion and chromatic aberration to RGBA beauty."""
    cfg = normalize_lens_effects_settings(settings or {})
    diagnostics: dict[str, Any] = {
        "rendering": cfg,
        "applied": False,
        "changed_pixels": 0,
        "distortion_applied": False,
        "chromatic_aberration_applied": False,
        "max_channel_offset_px": 0.0,
    }
    if not bool(cfg["enabled"]):
        return image, diagnostics
    try:
        import numpy as np
        from PIL import Image
    except Exception as exc:
        diagnostics["warnings"] = [f"lens effects skipped: {type(exc).__name__}: {exc}"]
        return image, diagnostics

    try:
        if hasattr(image, "convert"):
            pil = image.convert("RGBA")
        else:
            raw = np.asarray(image)
            if raw.dtype != np.uint8:
                raw = np.clip(raw, 0, 255).astype(np.uint8)
            pil = Image.fromarray(raw).convert("RGBA")

        arr = np.asarray(pil, dtype=np.float32) / 255.0
        original = arr.copy()
        height, width = arr.shape[:2]
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        center = cfg.get("center") if isinstance(cfg.get("center"), list) else DEFAULT_LENS_CENTER
        cx = float(center[0]) * float(width - 1)
        cy = float(center[1]) * float(height - 1)
        half = max(1.0, min(float(width), float(height)) * 0.5)
        dx = (xx - cx) / half
        dy = (yy - cy) / half
        r2 = dx * dx + dy * dy
        edge = np.power(np.clip(r2, 0.0, 4.0), float(cfg["edge_falloff"]) * 0.5)
        k1 = float(cfg["distortion_k1"]) * 0.34
        k2 = float(cfg["distortion_k2"]) * 0.16
        if abs(k2) <= 1.0e-6:
            k2 = float(cfg["distortion_k1"]) * abs(float(cfg["distortion_k1"])) * 0.08
        base_factor = 1.0 + k1 * r2 + k2 * r2 * r2
        if not bool(cfg["distortion_enabled"]):
            base_factor = np.ones_like(r2, dtype=np.float32)

        ca_norm = (
            float(cfg["chromatic_aberration_px"])
            * float(cfg["chromatic_aberration_strength"])
            / half
        )
        ca_factor = ca_norm * (0.35 + edge)
        factor_r = base_factor + ca_factor
        factor_g = base_factor
        factor_b = base_factor - ca_factor

        src_x_r = cx + dx * half * factor_r
        src_y_r = cy + dy * half * factor_r
        src_x_g = cx + dx * half * factor_g
        src_y_g = cy + dy * half * factor_g
        src_x_b = cx + dx * half * factor_b
        src_y_b = cy + dy * half * factor_b

        out = np.empty_like(arr)
        out[:, :, 0] = _bilinear_sample(arr, src_x_r, src_y_r, 0)
        out[:, :, 1] = _bilinear_sample(arr, src_x_g, src_y_g, 1)
        out[:, :, 2] = _bilinear_sample(arr, src_x_b, src_y_b, 2)
        out[:, :, 3] = _bilinear_sample(arr, src_x_g, src_y_g, 3)
        out = np.clip(out, 0.0, 1.0)

        diff = np.max(np.abs(out[:, :, :3] - original[:, :, :3]), axis=2)
        changed = diff > (1.0 / 255.0)
        diagnostics["changed_pixels"] = int(changed.sum())
        diagnostics["applied"] = bool(diagnostics["changed_pixels"] > 0)
        diagnostics["distortion_applied"] = bool(cfg["distortion_enabled"] and abs(float(cfg["distortion_k1"])) > 1.0e-6)
        diagnostics["chromatic_aberration_applied"] = bool(
            cfg["chromatic_aberration_enabled"] and float(cfg["chromatic_aberration_px"]) > 0.0
        )
        diagnostics["max_channel_offset_px"] = float(np.max(np.abs(ca_factor)) * half) if ca_factor.size else 0.0
        return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), "RGBA"), diagnostics
    except Exception as exc:
        diagnostics["warnings"] = [f"lens effects skipped: {type(exc).__name__}: {exc}"]
        return image, diagnostics
