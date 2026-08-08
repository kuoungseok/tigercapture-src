"""Substrate-compatible material controls for AR/PBR rendering.

This is not a clone of Unreal Engine's renderer.  It is an output-compatibility
layer that lets TigerCapture consume Substrate Slab-style inputs and shade them
through the existing packet/software PBR paths.
"""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SUBSTRATE_MODE = "off"
DEFAULT_SUBSTRATE_F90_COLOR = [1.0, 1.0, 1.0]
DEFAULT_SUBSTRATE_F90_STRENGTH = 1.0
DEFAULT_SUBSTRATE_F90_MASK_STRENGTH = 1.0


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().casefold()
    if text in {"1", "true", "yes", "on", "enabled", "enable", "substrate", "slab"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "disable", "none"}:
        return False
    return bool(default)


def _float_value(value: Any, default: float, lo: float, hi: float) -> float:
    try:
        out = float(value)
    except Exception:
        out = float(default)
    return max(float(lo), min(float(hi), out))


def _vec3_value(value: Any, default: list[float]) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for idx in range(3):
        fallback = float(default[idx] if idx < len(default) else 1.0)
        raw = source[idx] if idx < len(source) else fallback
        out.append(_float_value(raw, fallback, 0.0, 1.0))
    return out


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
        "substrate",
        "substrate_rendering",
        "substrate_slab",
        "slab",
        "unreal_substrate",
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


def _map_requests_substrate(maps: Mapping[str, Any] | None) -> bool:
    row = _as_mapping(maps)
    if not row:
        return False
    for key in ("substrate_enabled", "use_substrate"):
        if key in row and _bool_value(row.get(key), False):
            return True
    mode = str(row.get("substrate_mode") or "").strip().casefold()
    if mode in {"substrate", "substrate_slab", "slab", "bsdf_slab"}:
        return True
    for key in (
        "diffuse_albedo",
        "diffuse_albedo_map",
        "f0",
        "f0_map",
        "f90",
        "f90_map",
        "f90_mask",
        "f90_mask_map",
    ):
        if row.get(key):
            return True
    shader = str(row.get("shader_model") or row.get("source_shader") or "").casefold()
    return "substrate" in shader


def normalize_substrate_settings(
    value: Any,
    *,
    maps: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = _as_mapping(value)
    requested_by_maps = _map_requests_substrate(maps)
    raw_mode = str(
        _first_value(
            _nested(data, "mode", "shading_model"),
            data.get("substrate_mode"),
            DEFAULT_SUBSTRATE_MODE,
        )
        or DEFAULT_SUBSTRATE_MODE
    ).strip().casefold().replace("-", "_")
    if raw_mode in {"substrate", "substrate_slab", "bsdf_slab"}:
        raw_mode = "slab"
    if raw_mode not in {"off", "slab"}:
        raw_mode = DEFAULT_SUBSTRATE_MODE
    enabled = _bool_value(
        _first_value(
            _nested(data, "enabled"),
            data.get("substrate_enabled"),
            data.get("use_substrate"),
            requested_by_maps,
        ),
        requested_by_maps or raw_mode == "slab",
    )
    if requested_by_maps:
        enabled = True
    mode = "slab" if enabled else "off"
    f90_color = _vec3_value(
        _first_value(
            _nested(data, "f90_color", "edge_color", "grazing_color"),
            data.get("substrate_f90_color"),
            data.get("f90_color"),
        ),
        DEFAULT_SUBSTRATE_F90_COLOR,
    )
    return {
        "schema": "tigerstudio.ar_pbr.substrate_slab.v1",
        "enabled": bool(enabled),
        "mode": mode,
        "target": "Unreal Engine Substrate Slab BSDF output match",
        "helper": "Substrate Metalness-To-DiffuseAlbedo-F0",
        "diffuse_albedo": "map_or_base_color_times_one_minus_metallic",
        "f0": "optional_f0_map_or_metalness_helper",
        "f90": "optional_f90_map_or_f90_color_with_mask",
        "f90_color": [float(v) for v in f90_color],
        "f90_strength": _float_value(
            _first_value(_nested(data, "f90_strength"), data.get("substrate_f90_strength"), data.get("f90_strength")),
            DEFAULT_SUBSTRATE_F90_STRENGTH,
            0.0,
            1.0,
        ),
        "f90_mask_strength": _float_value(
            _first_value(
                _nested(data, "f90_mask_strength", "edge_mask_strength"),
                data.get("substrate_f90_mask_strength"),
                data.get("f90_mask_strength"),
            ),
            DEFAULT_SUBSTRATE_F90_MASK_STRENGTH,
            0.0,
            1.0,
        ),
        "render_model": "cpu_packet_substrate_slab_approximation",
        "render_pass_safe": True,
    }


def flatten_substrate_settings(value: Any) -> dict[str, Any]:
    settings = normalize_substrate_settings(value)
    return {
        "substrate_enabled": settings["enabled"],
        "substrate_mode": settings["mode"],
        "substrate_f90_color": settings["f90_color"],
        "substrate_f90_strength": settings["f90_strength"],
        "substrate_f90_mask_strength": settings["f90_mask_strength"],
    }
