"""Lens flare, aperture flare, and lens dirt/scratch controls."""
from __future__ import annotations

import math
from typing import Any, Mapping


DEFAULT_LENS_FLARE_MODE = "off"
DEFAULT_LENS_FLARE_STRENGTH = 0.0
DEFAULT_LENS_FLARE_THRESHOLD = 0.72
DEFAULT_LENS_FLARE_RADIUS = 5.0
DEFAULT_LENS_FLARE_GHOST_COUNT = 3
DEFAULT_LENS_FLARE_GHOST_SPACING = 0.42
DEFAULT_LENS_FLARE_TINT = [1.0, 0.86, 0.58]
DEFAULT_APERTURE_FLARE_STRENGTH = 0.0
DEFAULT_APERTURE_FLARE_BLADES = 6
DEFAULT_APERTURE_FLARE_ROTATION_DEG = 0.0
DEFAULT_APERTURE_FLARE_RADIUS = 18.0
DEFAULT_LENS_DIRT_STRENGTH = 0.0
DEFAULT_LENS_DIRT_DENSITY = 0.35
DEFAULT_LENS_DIRT_SCALE = 78.0
DEFAULT_LENS_SCRATCH_STRENGTH = 0.0
DEFAULT_LENS_SCRATCH_DENSITY = 0.22
DEFAULT_LENS_SCRATCH_LENGTH = 0.72
DEFAULT_LENS_FLARE_SEED = 0


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
    if text in {"1", "true", "yes", "on", "enabled", "flare", "lens_flare", "aperture", "dirt", "scratch"}:
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


def _color3(value: Any, default: list[float] | None = None) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else (default or DEFAULT_LENS_FLARE_TINT)
    out: list[float] = []
    for idx in range(3):
        try:
            out.append(max(0.0, min(4.0, float(source[idx]))))
        except Exception:
            out.append(float((default or DEFAULT_LENS_FLARE_TINT)[idx]))
    return out


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "lens_flare_rendering",
        "lens_flare",
        "flare",
        "aperture_flare",
        "lens_dirt",
        "dirt_scratch",
        "optical_flare",
        "camera_flare",
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


def normalize_lens_flare_settings(value: Any) -> dict[str, Any]:
    """Normalize lens flare, aperture streaks, dirt, and scratches."""
    data = _as_mapping(value)
    raw_mode = _first_value(
        _nested(data, "mode", "lens_flare_mode"),
        data.get("lens_flare_mode"),
        DEFAULT_LENS_FLARE_MODE,
    )
    mode = str(raw_mode or DEFAULT_LENS_FLARE_MODE).strip().casefold().replace("-", "_").replace(" ", "_")
    if mode in {"flare", "lens", "optical", "camera", "aperture", "dirt"}:
        mode = "lens_flare"
    if mode not in {"off", "lens_flare"}:
        mode = DEFAULT_LENS_FLARE_MODE

    flare_strength = _float_value(
        _first_value(
            _nested(data, "flare_strength", "lens_flare_strength", "strength"),
            data.get("lens_flare_strength"),
        ),
        DEFAULT_LENS_FLARE_STRENGTH,
        0.0,
        2.0,
    )
    flare_enabled = _bool_value(
        _first_value(_nested(data, "flare_enabled", "lens_flare_enabled"), data.get("lens_flare_enabled")),
        flare_strength > 0.0,
    )
    if flare_enabled and flare_strength <= 0.0:
        flare_strength = 0.35
    if not flare_enabled:
        flare_strength = 0.0

    threshold = _float_value(
        _first_value(_nested(data, "threshold", "flare_threshold"), data.get("lens_flare_threshold")),
        DEFAULT_LENS_FLARE_THRESHOLD,
        0.0,
        1.0,
    )
    radius = _float_value(
        _first_value(_nested(data, "radius", "flare_radius"), data.get("lens_flare_radius")),
        DEFAULT_LENS_FLARE_RADIUS,
        0.5,
        48.0,
    )
    ghost_count = _int_value(
        _first_value(_nested(data, "ghost_count", "ghosts"), data.get("lens_flare_ghost_count")),
        DEFAULT_LENS_FLARE_GHOST_COUNT,
        0,
        8,
    )
    ghost_spacing = _float_value(
        _first_value(_nested(data, "ghost_spacing", "spacing"), data.get("lens_flare_ghost_spacing")),
        DEFAULT_LENS_FLARE_GHOST_SPACING,
        0.05,
        1.5,
    )
    tint = _color3(_first_value(_nested(data, "tint", "flare_tint"), data.get("lens_flare_tint")), DEFAULT_LENS_FLARE_TINT)

    aperture_strength = _float_value(
        _first_value(
            _nested(data, "aperture_strength", "aperture_flare_strength", "star_strength"),
            data.get("aperture_flare_strength"),
        ),
        DEFAULT_APERTURE_FLARE_STRENGTH,
        0.0,
        2.0,
    )
    aperture_enabled = _bool_value(
        _first_value(
            _nested(data, "aperture_enabled", "aperture_flare_enabled"),
            data.get("aperture_flare_enabled"),
        ),
        aperture_strength > 0.0,
    )
    if aperture_enabled and aperture_strength <= 0.0:
        aperture_strength = 0.28
    if not aperture_enabled:
        aperture_strength = 0.0
    aperture_blades = _int_value(
        _first_value(_nested(data, "aperture_blades", "blade_count"), data.get("aperture_flare_blades")),
        DEFAULT_APERTURE_FLARE_BLADES,
        3,
        12,
    )
    aperture_rotation = _float_value(
        _first_value(_nested(data, "aperture_rotation", "rotation_degrees"), data.get("aperture_flare_rotation_deg")),
        DEFAULT_APERTURE_FLARE_ROTATION_DEG,
        -360.0,
        360.0,
    )
    aperture_radius = _float_value(
        _first_value(_nested(data, "aperture_radius", "star_radius"), data.get("aperture_flare_radius")),
        DEFAULT_APERTURE_FLARE_RADIUS,
        1.0,
        256.0,
    )

    dirt_strength = _float_value(
        _first_value(_nested(data, "dirt_strength", "lens_dirt_strength"), data.get("lens_dirt_strength")),
        DEFAULT_LENS_DIRT_STRENGTH,
        0.0,
        1.0,
    )
    dirt_enabled = _bool_value(
        _first_value(_nested(data, "dirt_enabled", "lens_dirt_enabled"), data.get("lens_dirt_enabled")),
        dirt_strength > 0.0,
    )
    if dirt_enabled and dirt_strength <= 0.0:
        dirt_strength = 0.18
    if not dirt_enabled:
        dirt_strength = 0.0
    dirt_density = _float_value(
        _first_value(_nested(data, "dirt_density", "density"), data.get("lens_dirt_density")),
        DEFAULT_LENS_DIRT_DENSITY,
        0.0,
        1.0,
    )
    dirt_scale = _float_value(
        _first_value(_nested(data, "dirt_scale", "scale"), data.get("lens_dirt_scale")),
        DEFAULT_LENS_DIRT_SCALE,
        4.0,
        512.0,
    )

    scratch_strength = _float_value(
        _first_value(_nested(data, "scratch_strength", "lens_scratch_strength"), data.get("lens_scratch_strength")),
        DEFAULT_LENS_SCRATCH_STRENGTH,
        0.0,
        1.0,
    )
    scratch_enabled = _bool_value(
        _first_value(_nested(data, "scratch_enabled", "lens_scratch_enabled"), data.get("lens_scratch_enabled")),
        scratch_strength > 0.0,
    )
    if scratch_enabled and scratch_strength <= 0.0:
        scratch_strength = 0.16
    if not scratch_enabled:
        scratch_strength = 0.0
    scratch_density = _float_value(
        _first_value(_nested(data, "scratch_density"), data.get("lens_scratch_density")),
        DEFAULT_LENS_SCRATCH_DENSITY,
        0.0,
        1.0,
    )
    scratch_length = _float_value(
        _first_value(_nested(data, "scratch_length"), data.get("lens_scratch_length")),
        DEFAULT_LENS_SCRATCH_LENGTH,
        0.05,
        1.0,
    )
    seed = _int_value(_first_value(_nested(data, "seed"), data.get("lens_flare_seed")), DEFAULT_LENS_FLARE_SEED, 0, 2_147_483_647)

    enabled = bool(
        flare_strength > 0.0
        or aperture_strength > 0.0
        or dirt_strength > 0.0
        or scratch_strength > 0.0
    )
    mode = "lens_flare" if enabled else "off"

    return {
        "schema": "tigerstudio.ar_pbr.lens_flare.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "flare_enabled": bool(flare_strength > 0.0),
        "flare_strength": float(flare_strength),
        "flare_threshold": float(threshold),
        "flare_radius": float(radius),
        "ghost_count": int(ghost_count),
        "ghost_spacing": float(ghost_spacing),
        "flare_tint": tint,
        "aperture_flare_enabled": bool(aperture_strength > 0.0),
        "aperture_flare_strength": float(aperture_strength),
        "aperture_blades": int(aperture_blades),
        "aperture_rotation_deg": float(aperture_rotation),
        "aperture_flare_radius": float(aperture_radius),
        "lens_dirt_enabled": bool(dirt_strength > 0.0),
        "lens_dirt_strength": float(dirt_strength),
        "lens_dirt_density": float(dirt_density),
        "lens_dirt_scale": float(dirt_scale),
        "lens_scratch_enabled": bool(scratch_strength > 0.0),
        "lens_scratch_strength": float(scratch_strength),
        "lens_scratch_density": float(scratch_density),
        "lens_scratch_length": float(scratch_length),
        "seed": int(seed),
        "post_model": "deterministic_beauty_pass_lens_ghosts_aperture_dirt_scratches",
        "flare_model": "bright_source_radial_ghosts_and_halo",
        "aperture_model": "deterministic_multi_blade_star_streak",
        "dirt_model": "hash_based_lens_dirt_and_scratch_overlay",
        "render_pass_policy": "beauty_only_skip_data_passes",
        "alpha_policy": "preserve_existing_alpha",
        "render_pass_safe": True,
    }


def flatten_lens_flare_settings(value: Any) -> dict[str, Any]:
    settings = normalize_lens_flare_settings(value)
    return {
        "lens_flare_mode": settings["mode"],
        "lens_flare_enabled": settings["enabled"],
        "lens_flare_strength": settings["flare_strength"],
        "lens_flare_threshold": settings["flare_threshold"],
        "lens_flare_radius": settings["flare_radius"],
        "lens_flare_ghost_count": settings["ghost_count"],
        "lens_flare_ghost_spacing": settings["ghost_spacing"],
        "lens_flare_tint": list(settings["flare_tint"]),
        "aperture_flare_enabled": settings["aperture_flare_enabled"],
        "aperture_flare_strength": settings["aperture_flare_strength"],
        "aperture_flare_blades": settings["aperture_blades"],
        "aperture_flare_rotation_deg": settings["aperture_rotation_deg"],
        "aperture_flare_radius": settings["aperture_flare_radius"],
        "lens_dirt_enabled": settings["lens_dirt_enabled"],
        "lens_dirt_strength": settings["lens_dirt_strength"],
        "lens_dirt_density": settings["lens_dirt_density"],
        "lens_dirt_scale": settings["lens_dirt_scale"],
        "lens_scratch_enabled": settings["lens_scratch_enabled"],
        "lens_scratch_strength": settings["lens_scratch_strength"],
        "lens_scratch_density": settings["lens_scratch_density"],
        "lens_scratch_length": settings["lens_scratch_length"],
        "lens_flare_seed": settings["seed"],
    }


def _smoothstep(edge0: Any, edge1: Any, value: Any):
    import numpy as np

    denom = np.maximum(float(edge1) - float(edge0), 1.0e-6)
    x = np.clip((value - float(edge0)) / denom, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _hash2(x: Any, y: Any, seed: float):
    import numpy as np

    raw = np.sin((x + seed * 0.37) * 12.9898 + (y + seed * 0.73) * 78.233) * 43758.5453
    return raw - np.floor(raw)


def apply_lens_flare_to_image(image: Any, settings: Mapping[str, Any] | None) -> tuple[Any, dict[str, Any]]:
    """Apply deterministic lens flare, aperture flare, dirt, and scratches."""
    cfg = normalize_lens_flare_settings(settings or {})
    diagnostics: dict[str, Any] = {
        "rendering": cfg,
        "applied": False,
        "changed_pixels": 0,
        "flare_applied": False,
        "aperture_flare_applied": False,
        "dirt_applied": False,
        "scratch_applied": False,
        "ghost_count": 0,
        "bright_source_pixels": 0,
    }
    if not bool(cfg["enabled"]):
        return image, diagnostics
    try:
        import numpy as np
        from PIL import Image, ImageFilter
    except Exception as exc:
        diagnostics["warnings"] = [f"lens flare skipped: {type(exc).__name__}: {exc}"]
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
        original_rgb = arr[:, :, :3].copy()
        rgb = original_rgb.copy()
        alpha = np.clip(arr[:, :, 3:4], 0.0, 1.0)
        height, width = rgb.shape[:2]
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        cx = (width - 1) * 0.5
        cy = (height - 1) * 0.5
        seed = float(int(cfg["seed"]) % 8192)
        tint = np.asarray(cfg["flare_tint"], dtype=np.float32).reshape(1, 1, 3)
        lum = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
        bright_mask = _smoothstep(float(cfg["flare_threshold"]), min(1.0, float(cfg["flare_threshold"]) + 0.18), lum) * alpha[:, :, 0]
        diagnostics["bright_source_pixels"] = int((bright_mask > 0.001).sum())
        bright_weight = float(bright_mask.sum())

        if bright_weight > 1.0e-5 and (bool(cfg["flare_enabled"]) or bool(cfg["aperture_flare_enabled"])):
            sx = float((xx * bright_mask).sum() / bright_weight)
            sy = float((yy * bright_mask).sum() / bright_weight)
            source_power = max(0.15, min(1.0, bright_weight / max(1.0, float(width * height) * 0.025)))
        else:
            sx, sy, source_power = cx, cy, 0.0

        if bool(cfg["flare_enabled"]) and source_power > 0.0:
            flare_strength = float(cfg["flare_strength"]) * source_power
            bright = np.dstack((rgb * bright_mask[:, :, None], bright_mask))
            bright_img = Image.fromarray(np.clip(bright * 255.0, 0, 255).astype(np.uint8), "RGBA")
            halo = np.asarray(
                bright_img.filter(ImageFilter.GaussianBlur(radius=float(cfg["flare_radius"]))),
                dtype=np.float32,
            )[:, :, :3] / 255.0
            rgb = np.clip(rgb + halo * flare_strength * tint, 0.0, 1.0)
            ghost_count = int(cfg["ghost_count"])
            spacing = float(cfg["ghost_spacing"])
            vx = cx - sx
            vy = cy - sy
            base_radius = max(1.0, min(width, height) * 0.035 + float(cfg["flare_radius"]) * 0.28)
            for idx in range(1, ghost_count + 1):
                gx = cx + vx * spacing * idx
                gy = cy + vy * spacing * idx
                radius = base_radius * (0.72 + idx * 0.32)
                dist = np.sqrt((xx - gx) ** 2 + (yy - gy) ** 2)
                ring = np.exp(-(dist / max(1.0, radius)) ** 2)
                core = np.exp(-(dist / max(1.0, radius * 0.28)) ** 2)
                ghost = (ring * 0.38 + core * 0.72)[:, :, None]
                ghost_tint = tint * (0.72 + 0.12 * ((idx + int(seed)) % 3))
                rgb = np.clip(rgb + ghost * ghost_tint * flare_strength * (0.34 / (idx ** 0.55)), 0.0, 1.0)
            diagnostics["flare_applied"] = True
            diagnostics["ghost_count"] = int(ghost_count)

        if bool(cfg["aperture_flare_enabled"]) and source_power > 0.0:
            dx = xx - sx
            dy = yy - sy
            dist = np.sqrt(dx * dx + dy * dy)
            aperture = np.zeros((height, width), dtype=np.float32)
            blades = int(cfg["aperture_blades"])
            rotation = math.radians(float(cfg["aperture_rotation_deg"]))
            width_px = max(0.7, min(width, height) * 0.006 + float(cfg["aperture_flare_radius"]) * 0.018)
            radius_px = max(1.0, float(cfg["aperture_flare_radius"]))
            for idx in range(blades):
                angle = rotation + math.pi * float(idx) / float(blades)
                ca = math.cos(angle)
                sa = math.sin(angle)
                along = dx * ca + dy * sa
                perp = -dx * sa + dy * ca
                streak = np.exp(-(perp / width_px) ** 2) * np.exp(-np.abs(along) / radius_px)
                aperture = np.maximum(aperture, streak)
            aperture *= _smoothstep(0.0, 0.18, dist / max(1.0, min(width, height)))
            rgb = np.clip(
                rgb + aperture[:, :, None] * tint * float(cfg["aperture_flare_strength"]) * source_power,
                0.0,
                1.0,
            )
            diagnostics["aperture_flare_applied"] = True

        if bool(cfg["lens_dirt_enabled"]) and float(cfg["lens_dirt_strength"]) > 0.0:
            scale = max(1.0, float(cfg["lens_dirt_scale"]))
            cell_x = np.floor(xx * scale / max(1.0, float(width)))
            cell_y = np.floor(yy * scale / max(1.0, float(height)))
            coarse = _hash2(cell_x, cell_y, seed + 17.0)
            fine = _hash2(xx, yy, seed + 41.0)
            threshold = 1.0 - float(cfg["lens_dirt_density"]) * 0.62
            dirt = _smoothstep(threshold, 1.0, coarse * 0.72 + fine * 0.28)
            flare_gate = np.clip(0.25 + lum * 0.75 + bright_mask * 1.4, 0.0, 1.0)
            dirt_rgb = np.asarray([1.0, 0.88, 0.62], dtype=np.float32).reshape(1, 1, 3)
            rgb = np.clip(rgb + dirt[:, :, None] * flare_gate[:, :, None] * dirt_rgb * float(cfg["lens_dirt_strength"]), 0.0, 1.0)
            diagnostics["dirt_applied"] = bool((dirt > 0.01).any())

        if bool(cfg["lens_scratch_enabled"]) and float(cfg["lens_scratch_strength"]) > 0.0:
            line_hash = _hash2(np.floor(xx / 3.0), np.zeros_like(xx), seed + 83.0)
            line_gate = _smoothstep(1.0 - float(cfg["lens_scratch_density"]) * 0.42, 1.0, line_hash)
            y_hash = _hash2(np.floor(xx / 7.0), np.floor(yy / max(1.0, height * float(cfg["lens_scratch_length"]))), seed + 127.0)
            scratch = line_gate * _smoothstep(0.28, 0.88, y_hash)
            scratch *= 0.45 + 0.55 * _smoothstep(float(cfg["flare_threshold"]) * 0.75, 1.0, lum)
            scratch_rgb = np.asarray([0.82, 0.90, 1.0], dtype=np.float32).reshape(1, 1, 3)
            rgb = np.clip(rgb + scratch[:, :, None] * scratch_rgb * float(cfg["lens_scratch_strength"]), 0.0, 1.0)
            diagnostics["scratch_applied"] = bool((scratch > 0.01).any())

        changed = np.max(np.abs(rgb - original_rgb), axis=2) > (1.0 / 255.0)
        diagnostics["changed_pixels"] = int(changed.sum())
        diagnostics["applied"] = bool(diagnostics["changed_pixels"] > 0)
        out = np.dstack((rgb, alpha[:, :, 0]))
        return Image.fromarray(np.clip(out * 255.0, 0, 255).astype(np.uint8), "RGBA"), diagnostics
    except Exception as exc:
        diagnostics["warnings"] = [f"lens flare skipped: {type(exc).__name__}: {exc}"]
        return image, diagnostics
