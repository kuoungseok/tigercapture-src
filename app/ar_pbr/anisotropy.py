"""General anisotropic and thin-film material polish for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_ANISOTROPIC_MODE = "off"
DEFAULT_ANISOTROPIC_STRENGTH = 0.0
DEFAULT_ANISOTROPY = 0.0
DEFAULT_ANISOTROPIC_ROTATION = 0.0
DEFAULT_ANISOTROPIC_TANGENT_WEIGHT = 1.0
DEFAULT_CLEARCOAT_ANISOTROPY = 0.0
DEFAULT_THIN_FILM_STRENGTH = 0.0
DEFAULT_THIN_FILM_THICKNESS_NM = 450.0
DEFAULT_THIN_FILM_IOR = 1.45
DEFAULT_THIN_FILM_TINT = [1.0, 0.86, 0.62]
DEFAULT_NEWTON_RINGS_STRENGTH = 0.0
DEFAULT_NEWTON_RINGS_SCALE = 18.0
DEFAULT_ANISOTROPIC_SEED = 0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
        "anisotropic",
        "anisotropy",
        "thin_film",
        "iridescence",
        "newton_rings",
        "brushed",
    }:
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
        "anisotropic_material",
        "anisotropic_rendering",
        "anisotropic_reflection",
        "anisotropy_rendering",
        "material_polish",
        "thin_film_rendering",
        "thin_film",
        "iridescence",
        "newton_rings",
        "anisotropy",
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


def normalize_anisotropic_material_settings(value: Any) -> dict[str, Any]:
    """Normalize general anisotropy, clearcoat anisotropy, and thin-film polish.

    Hair, cloth, and glint keep their specialized lobes. This contract covers
    the common material-level polish used by brushed metals, coated plastics,
    pearlescent surfaces, soap/oil-film tinting, and subtle Newton rings.
    """
    data = _as_mapping(value)
    raw_polish = data.get("anisotropic_material", data.get("anisotropy", data.get("thin_film")))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("anisotropic_mode"),
        data.get("anisotropy_mode"),
        data.get("thin_film_mode"),
        DEFAULT_ANISOTROPIC_MODE,
    )
    mode = str(raw_mode or DEFAULT_ANISOTROPIC_MODE).strip().casefold().replace("-", "_")
    if mode in {
        "anisotropy",
        "anisotropic_reflection",
        "brushed",
        "brushed_metal",
        "thinfilm",
        "thin_film",
        "iridescent",
        "iridescence",
        "newton",
        "newton_rings",
        "polish",
    }:
        mode = "anisotropic"
    if mode not in {"off", "anisotropic"}:
        mode = DEFAULT_ANISOTROPIC_MODE

    enabled = _bool_value(
        _first_value(
            _nested(data, "enabled"),
            data.get("anisotropic_enabled"),
            data.get("anisotropy_enabled"),
            data.get("thin_film_enabled"),
            raw_polish if isinstance(raw_polish, bool) else None,
        ),
        mode == "anisotropic",
    )
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount"),
            data.get("anisotropic_strength"),
            data.get("anisotropy_strength"),
            raw_polish if not isinstance(raw_polish, Mapping) else None,
        ),
        0.35 if enabled else DEFAULT_ANISOTROPIC_STRENGTH,
        0.0,
        1.5,
    )
    anisotropy = _float_value(
        _first_value(
            _nested(data, "anisotropy", "amount"),
            data.get("anisotropy"),
            data.get("anisotropic_amount"),
        ),
        DEFAULT_ANISOTROPY,
        -0.95,
        0.95,
    )
    rotation = _float_value(
        _first_value(
            _nested(data, "rotation", "angle", "rotation_deg"),
            data.get("anisotropic_rotation"),
            data.get("anisotropy_rotation"),
        ),
        DEFAULT_ANISOTROPIC_ROTATION,
        -180.0,
        180.0,
    )
    tangent_weight = _float_value(
        _first_value(
            _nested(data, "tangent_weight", "direction_weight"),
            data.get("anisotropic_tangent_weight"),
        ),
        DEFAULT_ANISOTROPIC_TANGENT_WEIGHT,
        0.0,
        1.0,
    )
    clearcoat_anisotropy = _float_value(
        _first_value(
            _nested(data, "clearcoat_anisotropy", "coat_anisotropy"),
            data.get("clearcoat_anisotropy"),
            data.get("clear_coat_anisotropy"),
        ),
        DEFAULT_CLEARCOAT_ANISOTROPY,
        -0.95,
        0.95,
    )
    thin_film_enabled_raw = _first_value(
        _nested(data, "thin_film_enabled", "film_enabled", "iridescence_enabled"),
        data.get("thin_film_enabled"),
        data.get("iridescence_enabled"),
    )
    thin_film_strength = _float_value(
        _first_value(
            _nested(data, "thin_film_strength", "film_strength", "iridescence_strength"),
            data.get("thin_film_strength"),
            data.get("iridescence_strength"),
        ),
        DEFAULT_THIN_FILM_STRENGTH,
        0.0,
        1.5,
    )
    thin_film_enabled = _bool_value(thin_film_enabled_raw, thin_film_strength > 0.0)
    thickness_nm = _float_value(
        _first_value(
            _nested(data, "thin_film_thickness_nm", "film_thickness_nm", "thickness_nm"),
            data.get("thin_film_thickness_nm"),
            data.get("thin_film_thickness"),
        ),
        DEFAULT_THIN_FILM_THICKNESS_NM,
        50.0,
        1600.0,
    )
    thin_film_ior = _float_value(
        _first_value(
            _nested(data, "thin_film_ior", "film_ior"),
            data.get("thin_film_ior"),
        ),
        DEFAULT_THIN_FILM_IOR,
        1.0,
        2.5,
    )
    thin_film_tint = _vec3_value(
        _first_value(
            _nested(data, "thin_film_tint", "film_tint", "iridescence_tint", "tint"),
            data.get("thin_film_tint"),
            data.get("iridescence_tint"),
        ),
        DEFAULT_THIN_FILM_TINT,
    )
    newton_rings_strength = _float_value(
        _first_value(
            _nested(data, "newton_rings_strength", "rings_strength", "ring_strength"),
            data.get("newton_rings_strength"),
        ),
        DEFAULT_NEWTON_RINGS_STRENGTH,
        0.0,
        1.0,
    )
    newton_rings_scale = _float_value(
        _first_value(
            _nested(data, "newton_rings_scale", "rings_scale", "ring_scale"),
            data.get("newton_rings_scale"),
        ),
        DEFAULT_NEWTON_RINGS_SCALE,
        1.0,
        256.0,
    )
    seed = _int_value(
        _first_value(_nested(data, "seed"), data.get("anisotropic_seed")),
        DEFAULT_ANISOTROPIC_SEED,
        0,
        2_147_483_647,
    )
    if any(abs(v) > 0.0 for v in (strength, anisotropy, clearcoat_anisotropy, thin_film_strength, newton_rings_strength)):
        enabled = True
        mode = "anisotropic"
    if thin_film_strength > 0.0:
        thin_film_enabled = True
    if not enabled:
        mode = "off"
        strength = 0.0
        anisotropy = 0.0
        clearcoat_anisotropy = 0.0
        thin_film_enabled = False
        thin_film_strength = 0.0
        newton_rings_strength = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.anisotropic_material.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "anisotropy": float(anisotropy),
        "rotation": float(rotation),
        "tangent_weight": float(tangent_weight),
        "clearcoat_anisotropy": float(clearcoat_anisotropy),
        "thin_film_enabled": bool(thin_film_enabled),
        "thin_film_strength": float(thin_film_strength),
        "thin_film_thickness_nm": float(thickness_nm),
        "thin_film_ior": float(thin_film_ior),
        "thin_film_tint": [float(v) for v in thin_film_tint],
        "newton_rings_strength": float(newton_rings_strength),
        "newton_rings_scale": float(newton_rings_scale),
        "seed": int(seed),
        "shading_model": "anisotropic_ggx_packet_specular_with_thin_film_interference_tint",
        "clearcoat_policy": "clearcoat_anisotropy_adds_top_lobe_directionality",
        "thin_film_policy": "deterministic_rgb_interference_tint_no_spectral_renderer",
        "geometry_policy": "uses_existing_mesh_tangent_or_generated_uv_tangent_no_brush_geometry",
        "render_pass_safe": True,
    }


def flatten_anisotropic_material_settings(value: Any) -> dict[str, Any]:
    settings = normalize_anisotropic_material_settings(value)
    return {
        "anisotropic_mode": settings["mode"],
        "anisotropic_enabled": settings["enabled"],
        "anisotropic_strength": settings["strength"],
        "anisotropy": settings["anisotropy"],
        "anisotropic_rotation": settings["rotation"],
        "anisotropic_tangent_weight": settings["tangent_weight"],
        "clearcoat_anisotropy": settings["clearcoat_anisotropy"],
        "thin_film_enabled": settings["thin_film_enabled"],
        "thin_film_strength": settings["thin_film_strength"],
        "thin_film_thickness_nm": settings["thin_film_thickness_nm"],
        "thin_film_ior": settings["thin_film_ior"],
        "thin_film_tint": list(settings["thin_film_tint"]),
        "newton_rings_strength": settings["newton_rings_strength"],
        "newton_rings_scale": settings["newton_rings_scale"],
        "anisotropic_seed": settings["seed"],
    }


def apply_anisotropic_material_polish(
    rgb: Any,
    *,
    uv: tuple[Any, Any],
    world_pos: tuple[Any, Any, Any],
    normal: tuple[Any, Any, Any],
    tangent: tuple[Any, Any, Any],
    bitangent: tuple[Any, Any, Any],
    light_dir: tuple[float, float, float],
    view_dir: tuple[float, float, float],
    ndotl: Any,
    ndotv: Any,
    roughness: Any,
    metallic: Any,
    ao: Any,
    direct_strength: float,
    env_rgb: Any,
    clearcoat: Mapping[str, Any] | None,
    settings: Mapping[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    cfg = normalize_anisotropic_material_settings(settings or {})
    diagnostics = {
        "rendering": cfg,
        "applied": False,
        "pixels": 0,
        "changed_pixels": 0,
        "max_intensity": 0.0,
        "mean_intensity": 0.0,
    }
    if not bool(cfg["enabled"]):
        return rgb, diagnostics
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
    if out.ndim != 3 or out.shape[2] < 3:
        return rgb, diagnostics
    shape = out.shape[:2]

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        try:
            return np.broadcast_to(raw, shape).astype(np.float32, copy=False)
        except Exception:
            return np.full(shape, float(default), dtype=np.float32)

    u = _arr(uv[0], 0.0)
    v = _arr(uv[1], 0.0)
    wx = _arr(world_pos[0], 0.0)
    wy = _arr(world_pos[1], 0.0)
    wz = _arr(world_pos[2], 0.0)
    nx = _arr(normal[0], 0.0)
    ny = _arr(normal[1], 0.0)
    nz = _arr(normal[2], 1.0)
    n_len = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1.0e-6)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len

    tx = _arr(tangent[0], 1.0)
    ty = _arr(tangent[1], 0.0)
    tz = _arr(tangent[2], 0.0)
    bx = _arr(bitangent[0], 0.0)
    by = _arr(bitangent[1], 1.0)
    bz = _arr(bitangent[2], 0.0)
    rot = np.deg2rad(float(cfg["rotation"]))
    cos_r = float(np.cos(rot))
    sin_r = float(np.sin(rot))
    rtx = tx * cos_r + bx * sin_r
    rty = ty * cos_r + by * sin_r
    rtz = tz * cos_r + bz * sin_r
    rbx = bx * cos_r - tx * sin_r
    rby = by * cos_r - ty * sin_r
    rbz = bz * cos_r - tz * sin_r
    t_dot_n = rtx * nx + rty * ny + rtz * nz
    rtx, rty, rtz = rtx - nx * t_dot_n, rty - ny * t_dot_n, rtz - nz * t_dot_n
    t_len = np.maximum(np.sqrt(rtx * rtx + rty * rty + rtz * rtz), 1.0e-6)
    rtx, rty, rtz = rtx / t_len, rty / t_len, rtz / t_len
    b_dot_n = rbx * nx + rby * ny + rbz * nz
    rbx, rby, rbz = rbx - nx * b_dot_n, rby - ny * b_dot_n, rbz - nz * b_dot_n
    b_len = np.maximum(np.sqrt(rbx * rbx + rby * rby + rbz * rbz), 1.0e-6)
    rbx, rby, rbz = rbx / b_len, rby / b_len, rbz / b_len

    lx, ly, lz = (float(light_dir[0]), float(light_dir[1]), float(light_dir[2]))
    vx, vy, vz = (float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
    h = np.asarray([lx + vx, ly + vy, lz + vz], dtype=np.float32)
    h_len = max(1.0e-6, float(np.linalg.norm(h)))
    hx, hy, hz = (float(h[0] / h_len), float(h[1] / h_len), float(h[2] / h_len))

    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nv = np.clip(_arr(ndotv, 0.0), 0.0, 1.0)
    rough = np.clip(_arr(roughness, 0.35), 0.025, 1.0)
    metal = np.clip(_arr(metallic, 0.0), 0.0, 1.0)
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)
    nh = np.clip(nx * hx + ny * hy + nz * hz, 0.0, 1.0)
    th = rtx * hx + rty * hy + rtz * hz
    bh = rbx * hx + rby * hy + rbz * hz

    anis = float(cfg["anisotropy"])
    strength = max(0.0, float(cfg["strength"]))
    coat_cfg = clearcoat if isinstance(clearcoat, Mapping) else {}
    coat_strength = max(0.0, min(1.0, float(coat_cfg.get("strength", 0.0) or 0.0)))
    coat_anis = abs(float(cfg["clearcoat_anisotropy"])) * coat_strength
    total_strength = max(strength, coat_anis * 0.85, float(cfg["thin_film_strength"]) * 0.55)
    if total_strength <= 0.0:
        return rgb, diagnostics

    tangent_weight = max(0.0, min(1.0, float(cfg["tangent_weight"])))
    direction_mix = np.abs(th) * tangent_weight + np.abs(bh) * (1.0 - tangent_weight)
    primary_width = np.clip(rough * (1.0 + anis * 0.72), 0.025, 1.0)
    secondary_width = np.clip(rough * (1.0 - anis * 0.58), 0.025, 1.0)
    ellipse = np.exp(-(
        (th * th) / np.maximum(primary_width * primary_width, 1.0e-5)
        + (bh * bh) / np.maximum(secondary_width * secondary_width, 1.0e-5)
    ) * np.maximum(nh, 0.12))
    exponent = np.maximum(2.0, 18.0 * (1.0 - rough) + 2.0)
    lobe = np.power(nh, exponent) * (0.38 + 0.62 * ellipse)
    brushed_floor = np.power(np.clip(1.0 - direction_mix, 0.0, 1.0), 2.0) * np.power(1.0 - rough, 1.2)
    fresnel = 0.04 + (0.86 + metal * 0.10) * np.power(1.0 - nv, 5.0)
    direct = (lobe + brushed_floor * abs(anis) * 0.18) * nl * max(0.0, float(direct_strength))
    env = np.asarray(env_rgb, dtype=np.float32)
    if env.ndim == 1 and env.shape[0] >= 3:
        env = env[None, None, :3]
    if env.ndim != 3 or env.shape[2] < 3:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.16
    try:
        env = np.broadcast_to(env[:, :, :3], (*shape, 3)).astype(np.float32, copy=False)
    except Exception:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.16

    film_strength = float(cfg["thin_film_strength"]) if bool(cfg["thin_film_enabled"]) else 0.0
    if film_strength > 0.0:
        wavelengths = np.asarray([620.0, 530.0, 460.0], dtype=np.float32)
        thickness = float(cfg["thin_film_thickness_nm"])
        film_ior = float(cfg["thin_film_ior"])
        optical_depth = thickness * film_ior * (0.42 + 0.58 * nv)
        phase = (optical_depth[:, :, None] / wavelengths[None, None, :]) * (2.0 * np.pi)
        interference = 0.54 + 0.46 * np.cos(phase + np.asarray([0.0, 2.1, 4.2], dtype=np.float32))
        tint = np.asarray(cfg["thin_film_tint"], dtype=np.float32)
        film_color = np.clip(interference * (0.62 + tint[None, None, :] * 0.38), 0.0, 1.35)
    else:
        film_color = np.ones((*shape, 3), dtype=np.float32)

    rings_strength = float(cfg["newton_rings_strength"])
    if rings_strength > 0.0:
        seed = float(int(cfg["seed"]) % 100_000) * 0.017
        radius = np.sqrt((u - 0.5 + wx * 0.013) ** 2 + (v - 0.5 + wy * 0.013) ** 2)
        ring = 0.5 + 0.5 * np.cos((radius * radius * float(cfg["newton_rings_scale"]) + wz * 0.07 + seed) * 2.0 * np.pi)
        ring_color = np.stack([
            0.72 + 0.28 * ring,
            0.80 + 0.20 * (1.0 - ring),
            0.78 + 0.22 * np.sin(ring * np.pi),
        ], axis=2)
        film_color = film_color * (1.0 - rings_strength) + ring_color * rings_strength

    coat_boost = 1.0 + coat_anis * 0.75
    intensity = (direct[:, :, None] + env * fresnel[:, :, None] * (0.22 + 0.55 * (1.0 - rough[:, :, None]))) * total_strength
    intensity = intensity * (0.35 + 0.65 * ao_arr[:, :, None]) * coat_boost
    polish = intensity * film_color
    changed = np.max(polish, axis=2) > 0.001
    if not bool(changed.any()):
        return out, diagnostics
    out = out + polish
    diagnostics.update({
        "applied": True,
        "pixels": int(np.prod(shape)),
        "changed_pixels": int(changed.sum()),
        "max_intensity": float(np.max(polish)),
        "mean_intensity": float(np.mean(np.max(polish, axis=2)[changed])),
    })
    return out, diagnostics
