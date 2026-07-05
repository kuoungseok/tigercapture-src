"""Shader-only bevel/rounded-edge controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_BEVEL_MODE = "off"
DEFAULT_BEVEL_STRENGTH = 0.0
DEFAULT_BEVEL_RADIUS = 0.045
DEFAULT_BEVEL_EDGE_WIDTH = 0.075
DEFAULT_BEVEL_SAMPLES = 1


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "bevel", "rounded", "rounded_edges"}:
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
    for container_key in ("bevel_rendering", "bevel", "rounded_edges", "rounded_edge"):
        nested = data.get(container_key)
        if isinstance(nested, Mapping):
            for key in keys:
                if key in nested:
                    return nested.get(key)
    for key in keys:
        if key in data:
            return data.get(key)
    return None


def normalize_bevel_settings(value: Any) -> dict[str, Any]:
    """Normalize optional shader bevel controls.

    This approximates small rounded edges by bending the shading normal near
    triangle or UV-island boundaries. It does not change mesh topology,
    silhouettes, depth, or shadow-caster geometry.
    """
    data = _as_mapping(value)
    bevel_raw = data.get("bevel")
    raw_mode = _first_value(
        _nested(data, "mode"),
        data.get("bevel_mode"),
        DEFAULT_BEVEL_MODE,
    )
    mode = str(raw_mode or DEFAULT_BEVEL_MODE).strip().casefold().replace("-", "_")
    if mode in {"rounded", "rounded_edge", "rounded_edges", "edge_rounding"}:
        mode = "bevel"
    if mode not in {"off", "bevel"}:
        mode = DEFAULT_BEVEL_MODE

    enabled_raw = _first_value(
        _nested(data, "enabled"),
        data.get("bevel_enabled"),
        data.get("rounded_edges_enabled"),
        bevel_raw if isinstance(bevel_raw, bool) else None,
    )
    enabled = _bool_value(enabled_raw, mode == "bevel")
    strength = _float_value(
        _first_value(
            _nested(data, "strength", "amount", "bevel_strength", "rounded_edge_strength"),
            data.get("bevel_strength"),
            data.get("rounded_edge_strength"),
            bevel_raw if not isinstance(bevel_raw, Mapping) else None,
        ),
        0.45 if enabled else DEFAULT_BEVEL_STRENGTH,
        0.0,
        1.0,
    )
    if strength > 0.0:
        enabled = True
        mode = "bevel"
    radius = _float_value(
        _first_value(
            _nested(data, "radius", "bevel_radius", "rounded_edge_radius"),
            data.get("bevel_radius"),
            data.get("rounded_edge_radius"),
        ),
        DEFAULT_BEVEL_RADIUS,
        0.0,
        0.25,
    )
    edge_width = _float_value(
        _first_value(
            _nested(data, "edge_width", "width", "bevel_edge_width"),
            data.get("bevel_edge_width"),
        ),
        DEFAULT_BEVEL_EDGE_WIDTH,
        0.001,
        0.5,
    )
    samples = _int_value(
        _first_value(
            _nested(data, "samples", "sample_count", "bevel_samples"),
            data.get("bevel_samples"),
        ),
        DEFAULT_BEVEL_SAMPLES,
        1,
        8,
    )
    if not enabled:
        mode = "off"
        strength = 0.0
        radius = 0.0
        samples = 1
    return {
        "schema": "tigerstudio.ar_pbr.bevel.v1",
        "mode": mode,
        "enabled": bool(enabled),
        "strength": float(strength),
        "radius": float(radius),
        "edge_width": float(edge_width),
        "samples": int(samples),
        "normal_model": "shader_only_edge_normal_rounding",
        "packet_model": "barycentric_edge_normal_blend",
        "gpu_model": "uv_island_edge_normal_blend",
        "geometry_policy": "no_topology_bevel",
        "silhouette_policy": "no_geometry_silhouette_bevel",
        "shadow_policy": "shading_only_no_beveled_shadow_caster",
        "render_pass_safe": True,
    }


def flatten_bevel_settings(value: Any) -> dict[str, Any]:
    settings = normalize_bevel_settings(value)
    return {
        "bevel_mode": settings["mode"],
        "bevel_enabled": settings["enabled"],
        "bevel_strength": settings["strength"],
        "bevel_radius": settings["radius"],
        "bevel_edge_width": settings["edge_width"],
        "bevel_samples": settings["samples"],
    }


def bevel_edge_mask(
    w0: Any,
    w1: Any,
    w2: Any,
    settings: Mapping[str, Any] | None,
) -> Any:
    cfg = normalize_bevel_settings(settings or {})
    import numpy as np

    a = np.asarray(w0, dtype=np.float32)
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0:
        return np.zeros_like(a, dtype=np.float32)
    b = np.asarray(w1, dtype=np.float32)
    c = np.asarray(w2, dtype=np.float32)
    edge = np.minimum(np.minimum(a, b), c)
    width = max(0.001, float(cfg["edge_width"]))
    mask = np.clip((width - edge) / width, 0.0, 1.0)
    return mask * mask * (3.0 - 2.0 * mask)


def apply_bevel_normal(
    nx: Any,
    ny: Any,
    nz: Any,
    *,
    barycentric: tuple[Any, Any, Any],
    tangent: tuple[Any, Any, Any],
    bitangent: tuple[Any, Any, Any],
    settings: Mapping[str, Any] | None,
) -> tuple[Any, Any, Any]:
    cfg = normalize_bevel_settings(settings or {})
    if not bool(cfg["enabled"]) or float(cfg["strength"]) <= 0.0 or float(cfg["radius"]) <= 0.0:
        return nx, ny, nz
    import numpy as np

    nxs = np.asarray(nx, dtype=np.float32)
    nys = np.asarray(ny, dtype=np.float32)
    nzs = np.asarray(nz, dtype=np.float32)
    w0, w1, w2 = (np.asarray(v, dtype=np.float32) for v in barycentric)
    tx, ty, tz = (np.asarray(v, dtype=np.float32) for v in tangent)
    bx, by, bz = (np.asarray(v, dtype=np.float32) for v in bitangent)
    edge0 = np.clip((float(cfg["edge_width"]) - w0) / max(0.001, float(cfg["edge_width"])), 0.0, 1.0)
    edge1 = np.clip((float(cfg["edge_width"]) - w1) / max(0.001, float(cfg["edge_width"])), 0.0, 1.0)
    edge2 = np.clip((float(cfg["edge_width"]) - w2) / max(0.001, float(cfg["edge_width"])), 0.0, 1.0)
    edge0 = edge0 * edge0 * (3.0 - 2.0 * edge0)
    edge1 = edge1 * edge1 * (3.0 - 2.0 * edge1)
    edge2 = edge2 * edge2 * (3.0 - 2.0 * edge2)
    dx = edge1 - edge0
    dy = edge2 - (edge0 + edge1) * 0.5
    length = np.maximum(np.sqrt(dx * dx + dy * dy), 1.0e-6)
    mask = bevel_edge_mask(w0, w1, w2, cfg)
    bend = float(cfg["strength"]) * float(cfg["radius"]) * mask
    dx = dx / length * bend
    dy = dy / length * bend
    out_x = nxs + tx * dx + bx * dy
    out_y = nys + ty * dx + by * dy
    out_z = nzs + tz * dx + bz * dy
    out_len = np.maximum(np.sqrt(out_x * out_x + out_y * out_y + out_z * out_z), 1.0e-6)
    return out_x / out_len, out_y / out_len, out_z / out_len
