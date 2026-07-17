"""Beauty-pass post effects for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_POST_EFFECTS_MODE = "off"
DEFAULT_BLOOM_STRENGTH = 0.0
DEFAULT_BLOOM_RADIUS = 2.0
DEFAULT_BLOOM_THRESHOLD = 0.72
DEFAULT_BLOOM_KERNEL = "cinematic"
DEFAULT_BLOOM_CONVOLUTION_SCALE = 1.0
DEFAULT_BLOOM_SCATTER = 1.0
DEFAULT_BLOOM_BOOST = 0.0
DEFAULT_VIGNETTE_STRENGTH = 0.0
DEFAULT_VIGNETTE_RADIUS = 0.72
DEFAULT_VIGNETTE_FEATHER = 0.36
DEFAULT_GRAIN_STRENGTH = 0.0
DEFAULT_GRAIN_SCALE = 96.0
DEFAULT_GRAIN_SEED = 0
DEFAULT_SHARPEN_STRENGTH = 0.0
DEFAULT_SHARPEN_RADIUS = 1.0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "post", "post_effects", "beauty"}:
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
        out = int(value)
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


def _normalize_bloom_kernel(value: Any) -> str:
    text = str(value or DEFAULT_BLOOM_KERNEL).strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "default": DEFAULT_BLOOM_KERNEL,
        "marmoset": "cinematic",
        "marmoset_style": "cinematic",
        "lens": "soft_lens",
        "soft": "soft_lens",
        "softlens": "soft_lens",
        "soft_lens": "soft_lens",
        "anamorphic": "anamorphic",
        "streak": "anamorphic",
        "horizontal": "anamorphic",
        "star": "starburst",
        "star_burst": "starburst",
        "starburst": "starburst",
        "glare": "cinematic",
        "cinematic": "cinematic",
    }
    return aliases.get(text, DEFAULT_BLOOM_KERNEL)


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "post_effects_rendering",
        "post_effects",
        "post_processing",
        "camera_post",
        "lens_post",
        "beauty_post",
        "render_post",
        "bloom_vignette_grain_sharpen",
        "post",
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


def normalize_post_effects_settings(value: Any) -> dict[str, Any]:
    """Normalize optional beauty-pass bloom/vignette/grain/sharpen controls."""
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("post_effects_mode"),
        DEFAULT_POST_EFFECTS_MODE,
    )
    mode = str(raw_mode or DEFAULT_POST_EFFECTS_MODE).strip().casefold().replace("-", "_")
    if mode in {"beauty", "post", "post_processing", "camera_post", "lens"}:
        mode = "post_effects"
    if mode not in {"off", "post_effects"}:
        mode = DEFAULT_POST_EFFECTS_MODE

    bloom_strength = _float_value(
        _first_value(
            _nested(data, "bloom_strength", "bloom", "glow_strength"),
            data.get("bloom_strength"),
        ),
        DEFAULT_BLOOM_STRENGTH,
        0.0,
        2.0,
    )
    bloom_enabled = _bool_value(
        _first_value(_nested(data, "bloom_enabled"), data.get("bloom_enabled")),
        bloom_strength > 0.0,
    )
    bloom_radius = _float_value(
        _first_value(_nested(data, "bloom_radius", "glow_radius"), data.get("bloom_radius")),
        DEFAULT_BLOOM_RADIUS,
        0.5,
        16.0,
    )
    bloom_threshold = _float_value(
        _first_value(_nested(data, "bloom_threshold", "glow_threshold"), data.get("bloom_threshold")),
        DEFAULT_BLOOM_THRESHOLD,
        0.0,
        1.0,
    )
    bloom_kernel = _normalize_bloom_kernel(
        _first_value(
            _nested(data, "bloom_kernel", "convolution_kernel", "bloom_convolution_kernel"),
            data.get("bloom_kernel"),
            data.get("convolution_kernel"),
        )
    )
    bloom_convolution_scale = _float_value(
        _first_value(
            _nested(data, "bloom_convolution_scale", "convolution_scale", "bloom_scale"),
            data.get("bloom_convolution_scale"),
            data.get("convolution_scale"),
        ),
        DEFAULT_BLOOM_CONVOLUTION_SCALE,
        0.15,
        4.0,
    )
    bloom_scatter = _float_value(
        _first_value(
            _nested(data, "bloom_scatter", "scatter_dispersion", "convolution_scatter"),
            data.get("bloom_scatter"),
            data.get("scatter_dispersion"),
        ),
        DEFAULT_BLOOM_SCATTER,
        0.05,
        4.0,
    )
    bloom_boost = _float_value(
        _first_value(
            _nested(data, "bloom_boost", "convolution_boost", "bloom_convolution_boost"),
            data.get("bloom_boost"),
            data.get("convolution_boost"),
        ),
        DEFAULT_BLOOM_BOOST,
        0.0,
        8.0,
    )
    if not bloom_enabled:
        bloom_strength = 0.0

    vignette_strength = _float_value(
        _first_value(_nested(data, "vignette_strength", "vignette"), data.get("vignette_strength")),
        DEFAULT_VIGNETTE_STRENGTH,
        0.0,
        1.0,
    )
    vignette_enabled = _bool_value(
        _first_value(_nested(data, "vignette_enabled"), data.get("vignette_enabled")),
        vignette_strength > 0.0,
    )
    vignette_radius = _float_value(
        _first_value(_nested(data, "vignette_radius"), data.get("vignette_radius")),
        DEFAULT_VIGNETTE_RADIUS,
        0.05,
        1.5,
    )
    vignette_feather = _float_value(
        _first_value(_nested(data, "vignette_feather", "vignette_softness"), data.get("vignette_feather")),
        DEFAULT_VIGNETTE_FEATHER,
        0.01,
        1.0,
    )
    if not vignette_enabled:
        vignette_strength = 0.0

    grain_strength = _float_value(
        _first_value(_nested(data, "grain_strength", "grain", "film_grain"), data.get("grain_strength")),
        DEFAULT_GRAIN_STRENGTH,
        0.0,
        0.5,
    )
    grain_enabled = _bool_value(
        _first_value(_nested(data, "grain_enabled"), data.get("grain_enabled")),
        grain_strength > 0.0,
    )
    grain_scale = _float_value(
        _first_value(_nested(data, "grain_scale", "grain_frequency"), data.get("grain_scale")),
        DEFAULT_GRAIN_SCALE,
        8.0,
        512.0,
    )
    grain_seed = _int_value(
        _first_value(_nested(data, "grain_seed", "seed"), data.get("grain_seed")),
        DEFAULT_GRAIN_SEED,
        0,
        2_147_483_647,
    )
    if not grain_enabled:
        grain_strength = 0.0

    sharpen_strength = _float_value(
        _first_value(_nested(data, "sharpen_strength", "sharpen"), data.get("sharpen_strength")),
        DEFAULT_SHARPEN_STRENGTH,
        0.0,
        1.5,
    )
    sharpen_enabled = _bool_value(
        _first_value(_nested(data, "sharpen_enabled"), data.get("sharpen_enabled")),
        sharpen_strength > 0.0,
    )
    sharpen_radius = _float_value(
        _first_value(_nested(data, "sharpen_radius"), data.get("sharpen_radius")),
        DEFAULT_SHARPEN_RADIUS,
        0.4,
        4.0,
    )
    if not sharpen_enabled:
        sharpen_strength = 0.0

    enabled = bool(
        bloom_strength > 0.0
        or vignette_strength > 0.0
        or grain_strength > 0.0
        or sharpen_strength > 0.0
    )
    if enabled:
        mode = "post_effects"
    else:
        mode = "off"

    return {
        "schema": "tigerstudio.ar_pbr.post_effects.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "bloom_enabled": bool(bloom_strength > 0.0),
        "bloom_strength": float(bloom_strength),
        "bloom_radius": float(bloom_radius),
        "bloom_threshold": float(bloom_threshold),
        "bloom_method": "convolution",
        "bloom_kernel": bloom_kernel,
        "bloom_convolution_scale": float(bloom_convolution_scale),
        "bloom_scatter": float(bloom_scatter),
        "bloom_boost": float(bloom_boost),
        "vignette_enabled": bool(vignette_strength > 0.0),
        "vignette_strength": float(vignette_strength),
        "vignette_radius": float(vignette_radius),
        "vignette_feather": float(vignette_feather),
        "grain_enabled": bool(grain_strength > 0.0),
        "grain_strength": float(grain_strength),
        "grain_scale": float(grain_scale),
        "grain_seed": int(grain_seed),
        "sharpen_enabled": bool(sharpen_strength > 0.0),
        "sharpen_strength": float(sharpen_strength),
        "sharpen_radius": float(sharpen_radius),
        "post_model": "deterministic_beauty_pass_bloom_vignette_grain_sharpen",
        "grain_model": "deterministic_hash_luma_weighted_film_grain",
        "render_pass_policy": "beauty_only_skip_data_passes",
        "alpha_policy": "preserve_existing_alpha",
        "bloom_model": "thresholded_fft_convolution_lens_bloom",
        "render_pass_safe": True,
    }


def flatten_post_effects_settings(value: Any) -> dict[str, Any]:
    settings = normalize_post_effects_settings(value)
    return {
        "post_effects_mode": settings["mode"],
        "post_effects_enabled": settings["enabled"],
        "bloom_enabled": settings["bloom_enabled"],
        "bloom_strength": settings["bloom_strength"],
        "bloom_radius": settings["bloom_radius"],
        "bloom_threshold": settings["bloom_threshold"],
        "bloom_method": settings["bloom_method"],
        "bloom_kernel": settings["bloom_kernel"],
        "bloom_convolution_scale": settings["bloom_convolution_scale"],
        "bloom_scatter": settings["bloom_scatter"],
        "bloom_boost": settings["bloom_boost"],
        "vignette_enabled": settings["vignette_enabled"],
        "vignette_strength": settings["vignette_strength"],
        "vignette_radius": settings["vignette_radius"],
        "vignette_feather": settings["vignette_feather"],
        "grain_enabled": settings["grain_enabled"],
        "grain_strength": settings["grain_strength"],
        "grain_scale": settings["grain_scale"],
        "grain_seed": settings["grain_seed"],
        "sharpen_enabled": settings["sharpen_enabled"],
        "sharpen_strength": settings["sharpen_strength"],
        "sharpen_radius": settings["sharpen_radius"],
    }


def _smoothstep(edge0: Any, edge1: Any, value: Any):
    import numpy as np

    denom = np.maximum(float(edge1) - float(edge0), 1.0e-6)
    x = np.clip((value - float(edge0)) / denom, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _pil_resampling_filter(Image: Any) -> Any:
    return getattr(getattr(Image, "Resampling", Image), "BICUBIC", getattr(Image, "BICUBIC", 3))


def _resize_rgb_array(arr: Any, size: tuple[int, int], Image: Any, np: Any) -> Any:
    img = Image.fromarray(np.clip(arr * 255.0, 0, 255).astype(np.uint8), "RGB")
    return np.asarray(img.resize(size, _pil_resampling_filter(Image)), dtype=np.float32) / 255.0


def _ray_kernel_component(x: Any, y: Any, angle: float, width: float, decay: float, amount: float, np: Any) -> Any:
    import math

    dx = math.cos(angle)
    dy = math.sin(angle)
    distance = np.abs(x * dy - y * dx)
    along = np.abs(x * dx + y * dy)
    return float(amount) * np.exp(-0.5 * (distance / max(float(width), 1.0e-4)) ** 2) * np.exp(
        -along / max(float(decay), 1.0e-4)
    )


def _build_convolution_bloom_kernel(
    kernel_name: str,
    radius_px: float,
    scale: float,
    scatter: float,
    np: Any,
) -> Any:
    import math

    radius = int(math.ceil(max(1.0, float(radius_px)) * max(0.15, float(scale)) * 2.35))
    radius = max(5, min(96, radius))
    size = radius * 2 + 1
    coords = np.linspace(-1.0, 1.0, size, dtype=np.float32)
    x, y = np.meshgrid(coords, coords)
    r = np.sqrt(x * x + y * y)
    spread = max(0.25, min(1.6, float(scatter)))
    radial = (
        np.exp(-0.5 * (r / (0.22 * spread)) ** 2) * 0.48
        + np.exp(-0.5 * (r / (0.58 * spread)) ** 2) * 0.22
        + np.exp(-0.5 * (r / (1.08 * spread)) ** 2) * 0.08
    )
    center = np.exp(-0.5 * (r / 0.035) ** 2) * 1.35
    name = _normalize_bloom_kernel(kernel_name)
    if name == "soft_lens":
        kernel = radial + center
    elif name == "anamorphic":
        kernel = radial * 0.38 + center * 0.72
        kernel += _ray_kernel_component(x, y, 0.0, 0.025 * spread, 1.15 * spread, 1.0, np)
        kernel += _ray_kernel_component(x, y, math.pi, 0.025 * spread, 1.15 * spread, 1.0, np)
    elif name == "starburst":
        kernel = radial * 0.32 + center * 0.92
        for angle, amount in (
            (0.0, 0.46),
            (math.pi * 0.5, 0.36),
            (math.pi * 0.25, 0.24),
            (-math.pi * 0.25, 0.24),
        ):
            kernel += _ray_kernel_component(x, y, angle, 0.021 * spread, 0.92 * spread, amount, np)
    else:
        kernel = radial * 0.62 + center
        kernel += _ray_kernel_component(x, y, 0.0, 0.026 * spread, 1.04 * spread, 0.42, np)
        kernel += _ray_kernel_component(x, y, math.pi * 0.25, 0.018 * spread, 0.82 * spread, 0.14, np)
        kernel += _ray_kernel_component(x, y, -math.pi * 0.25, 0.018 * spread, 0.82 * spread, 0.14, np)
    kernel = np.maximum(kernel.astype(np.float32), 0.0)
    total = float(kernel.sum())
    if total <= 1.0e-8:
        kernel[radius, radius] = 1.0
        total = 1.0
    return kernel / total


def _fft_convolve_rgb(source: Any, kernel: Any, np: Any) -> Any:
    height, width = source.shape[:2]
    kernel_h, kernel_w = kernel.shape[:2]
    out_h = int(height + kernel_h - 1)
    out_w = int(width + kernel_w - 1)
    kernel_pad = np.zeros((out_h, out_w), dtype=np.float32)
    kernel_pad[:kernel_h, :kernel_w] = kernel.astype(np.float32)
    kernel_fft = np.fft.rfft2(kernel_pad)
    out = np.zeros_like(source, dtype=np.float32)
    start_y = kernel_h // 2
    start_x = kernel_w // 2
    for channel in range(3):
        src_pad = np.zeros((out_h, out_w), dtype=np.float32)
        src_pad[:height, :width] = source[:, :, channel].astype(np.float32)
        convolved = np.fft.irfft2(np.fft.rfft2(src_pad) * kernel_fft, s=(out_h, out_w))
        out[:, :, channel] = convolved[start_y : start_y + height, start_x : start_x + width]
    return np.clip(out, 0.0, None)


def _apply_convolution_bloom(rgb: Any, alpha: Any, cfg: Mapping[str, Any], Image: Any, np: Any) -> tuple[Any, dict[str, Any]]:
    height, width = rgb.shape[:2]
    radius = max(0.5, float(cfg["bloom_radius"]))
    threshold = max(0.0, min(1.0, float(cfg["bloom_threshold"])))
    lum = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    knee = max(0.035, min(0.32, 0.08 + radius / 72.0))
    excess = np.maximum(lum - threshold, 0.0)
    contribution = np.clip(excess / max(1.0 - threshold, 1.0e-4), 0.0, 1.0)
    gate = _smoothstep(0.0, knee, excess) * contribution
    boost = float(cfg.get("bloom_boost", DEFAULT_BLOOM_BOOST) or 0.0)
    if boost > 0.0:
        gate *= 1.0 + np.clip(contribution, 0.0, 1.0) * boost
    source_pixels = int((gate > 0.001).sum())
    if source_pixels <= 0:
        return np.zeros_like(rgb, dtype=np.float32), {
            "bloom_method": "convolution",
            "bloom_kernel": _normalize_bloom_kernel(cfg.get("bloom_kernel")),
            "bloom_kernel_size": 0,
            "bloom_work_scale": 1.0,
            "bloom_source_pixels": 0,
        }
    bright = rgb * gate[:, :, None] * alpha
    max_dim = max(int(width), int(height))
    work_scale = 1.0
    if max_dim > 960:
        work_scale = 960.0 / float(max_dim)
    elif radius >= 7.0 and max_dim > 384:
        work_scale = 0.5
    work_w = max(8, int(round(float(width) * work_scale)))
    work_h = max(8, int(round(float(height) * work_scale)))
    if work_scale < 0.999:
        work = _resize_rgb_array(bright, (work_w, work_h), Image, np)
    else:
        work = bright.astype(np.float32)
    kernel = _build_convolution_bloom_kernel(
        str(cfg.get("bloom_kernel") or DEFAULT_BLOOM_KERNEL),
        radius * work_scale,
        float(cfg.get("bloom_convolution_scale", DEFAULT_BLOOM_CONVOLUTION_SCALE) or DEFAULT_BLOOM_CONVOLUTION_SCALE),
        float(cfg.get("bloom_scatter", DEFAULT_BLOOM_SCATTER) or DEFAULT_BLOOM_SCATTER),
        np,
    )
    bloom_work = _fft_convolve_rgb(work, kernel, np)
    if work_scale < 0.999:
        bloom = _resize_rgb_array(bloom_work, (int(width), int(height)), Image, np)
    else:
        bloom = bloom_work
    scatter = max(0.05, min(4.0, float(cfg.get("bloom_scatter", DEFAULT_BLOOM_SCATTER) or DEFAULT_BLOOM_SCATTER)))
    diagnostics = {
        "bloom_method": "convolution",
        "bloom_kernel": _normalize_bloom_kernel(cfg.get("bloom_kernel")),
        "bloom_kernel_size": int(kernel.shape[0]),
        "bloom_work_scale": float(work_scale),
        "bloom_source_pixels": source_pixels,
    }
    return np.clip(bloom * scatter, 0.0, None), diagnostics


def apply_post_effects_to_image(image: Any, settings: Mapping[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    """Apply deterministic beauty-pass post effects to an RGBA image."""
    cfg = normalize_post_effects_settings(settings or {})
    diagnostics: dict[str, Any] = {
        "rendering": cfg,
        "applied": False,
        "changed_pixels": 0,
        "bloom_applied": False,
        "vignette_applied": False,
        "grain_applied": False,
        "sharpen_applied": False,
    }
    if not bool(cfg["enabled"]):
        return image, diagnostics
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception as exc:
        diagnostics["warnings"] = [f"post effects skipped: {type(exc).__name__}: {exc}"]
        return image, diagnostics

    try:
        if hasattr(image, "convert"):
            pil = image.convert("RGBA")
        else:
            raw = np.asarray(image)
            if raw.dtype != np.uint8:
                raw = np.clip(raw, 0, 255).astype(np.uint8)
            if raw.ndim == 3 and raw.shape[2] == 3:
                pil = Image.fromarray(raw, "RGB").convert("RGBA")
            elif raw.ndim == 3 and raw.shape[2] == 4:
                pil = Image.fromarray(raw, "RGBA")
            else:
                pil = Image.fromarray(raw).convert("RGBA")
        arr = np.asarray(pil, dtype=np.float32) / 255.0
        original_rgb = arr[:, :, :3].copy()
        rgb = original_rgb.copy()
        alpha = np.clip(arr[:, :, 3:4], 0.0, 1.0)
        height, width = rgb.shape[:2]

        if bool(cfg["bloom_enabled"]) and float(cfg["bloom_strength"]) > 0.0:
            bloom, bloom_diag = _apply_convolution_bloom(rgb, alpha, cfg, Image, np)
            rgb = np.clip(rgb + bloom * float(cfg["bloom_strength"]), 0.0, 1.0)
            diagnostics["bloom_applied"] = True
            diagnostics.update(bloom_diag)

        if bool(cfg["sharpen_enabled"]) and float(cfg["sharpen_strength"]) > 0.0:
            rgb_img = Image.fromarray(np.clip(rgb * 255.0, 0, 255).astype(np.uint8), "RGB")
            blur = np.asarray(
                rgb_img.filter(ImageFilter.GaussianBlur(radius=float(cfg["sharpen_radius"]))),
                dtype=np.float32,
            ) / 255.0
            rgb = np.clip(rgb * (1.0 + float(cfg["sharpen_strength"])) - blur * float(cfg["sharpen_strength"]), 0.0, 1.0)
            diagnostics["sharpen_applied"] = True

        if bool(cfg["vignette_enabled"]) and float(cfg["vignette_strength"]) > 0.0:
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            nx = (xx / max(1.0, float(width - 1)) - 0.5) * 2.0
            ny = (yy / max(1.0, float(height - 1)) - 0.5) * 2.0
            aspect = float(width) / max(1.0, float(height))
            dist = np.sqrt((nx / max(1.0, aspect)) ** 2 + ny ** 2)
            edge = _smoothstep(float(cfg["vignette_radius"]), float(cfg["vignette_radius"]) + float(cfg["vignette_feather"]), dist)
            mult = 1.0 - edge[:, :, None] * float(cfg["vignette_strength"])
            rgb = np.clip(rgb * mult, 0.0, 1.0)
            diagnostics["vignette_applied"] = True

        if bool(cfg["grain_enabled"]) and float(cfg["grain_strength"]) > 0.0:
            yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
            scale = max(1.0, float(cfg["grain_scale"]))
            cell_x = np.floor(xx * scale / max(1.0, float(width)))
            cell_y = np.floor(yy * scale / max(1.0, float(height)))
            seed = float(int(cfg["grain_seed"]) % 8192)
            raw = np.sin((cell_x + seed * 0.37) * 12.9898 + (cell_y + seed * 0.73) * 78.233) * 43758.5453
            noise = (raw - np.floor(raw) - 0.5)[:, :, None]
            luma = rgb[:, :, 0:1] * 0.2126 + rgb[:, :, 1:2] * 0.7152 + rgb[:, :, 2:3] * 0.0722
            grain_weight = 0.35 + (1.0 - np.abs(luma - 0.5) * 1.3).clip(0.0, 1.0) * 0.65
            rgb = np.clip(rgb + noise * float(cfg["grain_strength"]) * grain_weight, 0.0, 1.0)
            diagnostics["grain_applied"] = True

        changed = np.max(np.abs(rgb - original_rgb), axis=2) > (1.0 / 255.0)
        diagnostics["changed_pixels"] = int(changed.sum())
        diagnostics["applied"] = bool(diagnostics["changed_pixels"] > 0)
        out = np.dstack((rgb, alpha[:, :, 0]))
        return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), "RGBA"), diagnostics
    except Exception as exc:
        diagnostics["warnings"] = [f"post effects skipped: {type(exc).__name__}: {exc}"]
        return image, diagnostics
