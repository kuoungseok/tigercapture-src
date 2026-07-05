"""Realtime hair/groom shading controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_HAIR_GROOM_MODE = "off"
DEFAULT_HAIR_GROOM_STRENGTH = 0.0
DEFAULT_HAIR_GROOM_TINT = [1.0, 0.88, 0.62]
DEFAULT_HAIR_PRIMARY_SHIFT = 0.08
DEFAULT_HAIR_SECONDARY_SHIFT = -0.18
DEFAULT_HAIR_PRIMARY_ROUGHNESS = 0.24
DEFAULT_HAIR_SECONDARY_ROUGHNESS = 0.42
DEFAULT_HAIR_SECONDARY_STRENGTH = 0.48
DEFAULT_HAIR_ANISOTROPY = 0.78
DEFAULT_HAIR_RIM_STRENGTH = 0.18


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "hair", "groom", "fur"}:
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
        "hair_groom_rendering",
        "groom_rendering",
        "hair_rendering",
        "hair_groom",
        "hair",
        "groom",
        "fur",
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


def _nested_hair_value(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "hair_groom_rendering",
        "groom_rendering",
        "hair_rendering",
        "hair_groom",
        "hair",
        "groom",
        "fur",
    ):
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    return None


def _vec3_value(value: Any, default: list[float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        fallback = float(default[idx] if idx < len(default) else 1.0)
        raw = source[idx] if idx < len(source) else fallback
        out.append(_float_value(raw, fallback, 0.0, 1.0))
    return out


def normalize_hair_groom_settings(value: Any) -> dict[str, Any]:
    """Normalize optional realtime hair/groom shading controls.

    This is a render-pass-safe anisotropic highlight approximation using the
    existing mesh tangent basis. It does not create strand geometry, simulate
    groom dynamics, perform Marschner multi-scattering, or generate deep
    shadow maps.
    """
    data = _as_mapping(value)
    hair_raw = data.get("hair_groom", data.get("hair", data.get("groom")))
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("hair_groom_mode"),
        data.get("hair_mode"),
        data.get("groom_mode"),
        DEFAULT_HAIR_GROOM_MODE,
    )
    mode = str(raw_mode or DEFAULT_HAIR_GROOM_MODE).strip().casefold().replace("-", "_")
    if mode in {"groom", "fur", "anisotropic_hair", "anisotropic", "kajiya_kay", "marschner", "strand"}:
        mode = "hair"
    if mode not in {"off", "hair"}:
        mode = DEFAULT_HAIR_GROOM_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("hair_groom_enabled"),
        data.get("hair_enabled"),
        data.get("groom_enabled"),
        hair_raw if isinstance(hair_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "hair")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "hair", "groom"),
            data.get("hair_groom_strength"),
            data.get("hair_strength"),
            data.get("groom_strength"),
            hair_raw if not isinstance(hair_raw, Mapping) else None,
        ),
        0.55 if enabled else DEFAULT_HAIR_GROOM_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "hair"

    tint = _vec3_value(
        _first_value(
            _nested(data, "tint", "color", "highlight_color", "hair_tint", "groom_tint"),
            data.get("hair_groom_tint"),
            data.get("hair_tint"),
            data.get("groom_tint"),
        ),
        DEFAULT_HAIR_GROOM_TINT,
    )
    primary_shift = _float_value(
        _first_value(
            _nested(data, "primary_shift", "root_shift", "hair_primary_shift"),
            data.get("hair_primary_shift"),
        ),
        DEFAULT_HAIR_PRIMARY_SHIFT,
        -0.5,
        0.5,
    )
    secondary_shift = _float_value(
        _first_value(
            _nested(data, "secondary_shift", "tip_shift", "hair_secondary_shift"),
            data.get("hair_secondary_shift"),
        ),
        DEFAULT_HAIR_SECONDARY_SHIFT,
        -0.5,
        0.5,
    )
    primary_roughness = _float_value(
        _first_value(
            _nested(data, "primary_roughness", "roughness", "hair_primary_roughness"),
            data.get("hair_primary_roughness"),
        ),
        DEFAULT_HAIR_PRIMARY_ROUGHNESS,
        0.03,
        1.0,
    )
    secondary_roughness = _float_value(
        _first_value(
            _nested(data, "secondary_roughness", "secondary_width", "hair_secondary_roughness"),
            data.get("hair_secondary_roughness"),
        ),
        DEFAULT_HAIR_SECONDARY_ROUGHNESS,
        0.03,
        1.0,
    )
    secondary_strength = _float_value(
        _first_value(
            _nested(data, "secondary_strength", "secondary", "hair_secondary_strength"),
            data.get("hair_secondary_strength"),
        ),
        DEFAULT_HAIR_SECONDARY_STRENGTH,
        0.0,
        1.5,
    )
    anisotropy = _float_value(
        _first_value(
            data.get("hair_anisotropy"),
            _nested(data, "strand_anisotropy", "hair_anisotropy"),
            _nested_hair_value(data, "anisotropy"),
        ),
        DEFAULT_HAIR_ANISOTROPY,
        0.0,
        1.0,
    )
    rim_strength = _float_value(
        _first_value(
            _nested(data, "rim_strength", "backscatter", "hair_rim_strength"),
            data.get("hair_rim_strength"),
            data.get("hair_backscatter"),
        ),
        DEFAULT_HAIR_RIM_STRENGTH,
        0.0,
        1.0,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        secondary_strength = 0.0
        rim_strength = 0.0

    return {
        "schema": "tigerstudio.ar_pbr.hair_groom.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "tint": [float(v) for v in tint],
        "primary_shift": float(primary_shift),
        "secondary_shift": float(secondary_shift),
        "primary_roughness": float(primary_roughness),
        "secondary_roughness": float(secondary_roughness),
        "secondary_strength": float(secondary_strength),
        "anisotropy": float(anisotropy),
        "rim_strength": float(rim_strength),
        "shading_model": "dual_lobe_kajiya_kay_anisotropic_specular",
        "tangent_policy": "uses_existing_mesh_tangent_or_generated_uv_tangent",
        "geometry_policy": "no_generated_strand_geometry_or_groom_simulation",
        "shadow_policy": "shading_only_no_deep_opacity_shadow_maps",
        "render_pass_safe": True,
    }


def flatten_hair_groom_settings(value: Any) -> dict[str, Any]:
    settings = normalize_hair_groom_settings(value)
    return {
        "hair_groom_mode": settings["mode"],
        "hair_groom_enabled": settings["enabled"],
        "hair_groom_strength": settings["strength"],
        "hair_groom_tint": list(settings["tint"]),
        "hair_primary_shift": settings["primary_shift"],
        "hair_secondary_shift": settings["secondary_shift"],
        "hair_primary_roughness": settings["primary_roughness"],
        "hair_secondary_roughness": settings["secondary_roughness"],
        "hair_secondary_strength": settings["secondary_strength"],
        "hair_anisotropy": settings["anisotropy"],
        "hair_rim_strength": settings["rim_strength"],
    }


def apply_hair_groom_shading(
    rgb: Any,
    *,
    normal: tuple[Any, Any, Any],
    tangent: tuple[Any, Any, Any],
    light_dir: tuple[float, float, float],
    view_dir: tuple[float, float, float],
    ndotl: Any,
    ndotv: Any,
    ndoth: Any,
    roughness: Any,
    ao: Any,
    direct_strength: float,
    env_rgb: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_hair_groom_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return rgb
    import numpy as np

    out = np.asarray(rgb, dtype=np.float32)
    if out.ndim != 3 or out.shape[2] < 3:
        return rgb
    shape = out.shape[:2]

    def _arr(value: Any, default: float = 0.0):
        raw = np.asarray(value, dtype=np.float32)
        if raw.shape == shape:
            return raw
        try:
            return np.broadcast_to(raw, shape).astype(np.float32, copy=False)
        except Exception:
            return np.full(shape, float(default), dtype=np.float32)

    nx = _arr(normal[0], 0.0)
    ny = _arr(normal[1], 0.0)
    nz = _arr(normal[2], 1.0)
    n_len = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1.0e-6)
    nx, ny, nz = nx / n_len, ny / n_len, nz / n_len

    tx = _arr(tangent[0], 1.0)
    ty = _arr(tangent[1], 0.0)
    tz = _arr(tangent[2], 0.0)
    t_dot_n = tx * nx + ty * ny + tz * nz
    tx = tx - nx * t_dot_n
    ty = ty - ny * t_dot_n
    tz = tz - nz * t_dot_n
    t_len = np.sqrt(tx * tx + ty * ty + tz * tz)
    fallback_tx = np.where(np.abs(nx) < 0.9, 1.0, 0.0)
    fallback_ty = np.where(np.abs(nx) < 0.9, 0.0, 1.0)
    fallback_tz = np.zeros_like(fallback_tx)
    tx = np.where(t_len > 1.0e-6, tx / np.maximum(t_len, 1.0e-6), fallback_tx)
    ty = np.where(t_len > 1.0e-6, ty / np.maximum(t_len, 1.0e-6), fallback_ty)
    tz = np.where(t_len > 1.0e-6, tz / np.maximum(t_len, 1.0e-6), fallback_tz)

    lx, ly, lz = (float(light_dir[0]), float(light_dir[1]), float(light_dir[2]))
    vx, vy, vz = (float(view_dir[0]), float(view_dir[1]), float(view_dir[2]))
    h = np.asarray([lx + vx, ly + vy, lz + vz], dtype=np.float32)
    h_len = max(1.0e-6, float(np.linalg.norm(h)))
    hx, hy, hz = (float(h[0] / h_len), float(h[1] / h_len), float(h[2] / h_len))
    nl = np.clip(_arr(ndotl, 0.0), 0.0, 1.0)
    nv = np.clip(_arr(ndotv, 0.0), 0.0, 1.0)
    nh = np.clip(_arr(ndoth, 0.0), 0.0, 1.0)
    rough = np.clip(_arr(roughness, 0.35), 0.03, 1.0)
    ao_arr = np.clip(_arr(ao, 1.0), 0.0, 1.0)

    def _lobe(shift: float, lobe_roughness: float):
        sx = tx + nx * float(shift)
        sy = ty + ny * float(shift)
        sz = tz + nz * float(shift)
        s_len = np.maximum(np.sqrt(sx * sx + sy * sy + sz * sz), 1.0e-6)
        sx, sy, sz = sx / s_len, sy / s_len, sz / s_len
        tdoth = np.clip(sx * hx + sy * hy + sz * hz, -1.0, 1.0)
        strand = np.sqrt(np.maximum(1.0 - tdoth * tdoth, 0.0))
        width = np.clip(lobe_roughness * 0.72 + rough * 0.28, 0.03, 1.0)
        exponent = 8.0 + (1.0 - width) * 88.0
        kk = np.power(np.clip(strand, 0.0, 1.0), exponent)
        iso = np.power(nh, 2.0 + (1.0 - width) * 54.0)
        return iso * (1.0 - float(cfg["anisotropy"])) + kk * float(cfg["anisotropy"])

    primary = _lobe(float(cfg["primary_shift"]), float(cfg["primary_roughness"]))
    secondary = _lobe(float(cfg["secondary_shift"]), float(cfg["secondary_roughness"])) * float(cfg["secondary_strength"])
    tl = np.sqrt(np.maximum(1.0 - np.clip(tx * lx + ty * ly + tz * lz, -1.0, 1.0) ** 2.0, 0.0))
    tv = np.sqrt(np.maximum(1.0 - np.clip(tx * vx + ty * vy + tz * vz, -1.0, 1.0) ** 2.0, 0.0))
    strand_gate = np.clip(tl * tv, 0.0, 1.0)
    facing = np.clip(nl * 0.65 + 0.35, 0.0, 1.0) * np.clip(nv * 0.55 + 0.45, 0.0, 1.0)
    rim = np.power(np.clip(1.0 - nv, 0.0, 1.0), 2.0) * float(cfg["rim_strength"])

    env = np.asarray(env_rgb, dtype=np.float32)
    if env.ndim == 1 and env.shape[0] >= 3:
        env = env[None, None, :3]
    if env.ndim != 3 or env.shape[2] < 3:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.18
    try:
        env = np.broadcast_to(env[:, :, :3], (*shape, 3)).astype(np.float32, copy=False)
    except Exception:
        env = np.ones((*shape, 3), dtype=np.float32) * 0.18

    tint = np.asarray(cfg["tint"], dtype=np.float32)
    strength = float(cfg["strength"])
    direct = (
        (primary + secondary)[:, :, None]
        * tint[None, None, :]
        * strand_gate[:, :, None]
        * facing[:, :, None]
        * max(0.0, float(direct_strength))
        * strength
        * (0.28 + ao_arr[:, :, None] * 0.72)
    )
    environment = env * tint[None, None, :] * (primary[:, :, None] * 0.12 + rim[:, :, None]) * strength * (0.35 + ao_arr[:, :, None] * 0.65)
    # Low-poly proxy exports often have flat normals/tangents where the
    # anisotropic lobes quantize away. Keep a tiny groom body sheen so an
    # enabled hair pass produces visible, testable pixels without washing out
    # authored texture color.
    body_sheen = (
        tint[None, None, :]
        * strength
        * (0.014 + np.clip(1.0 - rough, 0.0, 1.0)[:, :, None] * 0.045)
        * facing[:, :, None]
        * (0.35 + ao_arr[:, :, None] * 0.65)
    )
    return np.clip(out + direct + environment + body_sheen, 0.0, 32.0)
