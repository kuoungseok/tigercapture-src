"""Surface material override controls for AR/PBR rendering."""
from __future__ import annotations

from typing import Any, Mapping


DEFAULT_SURFACE_OVERRIDE_STRENGTH = 0.0
DEFAULT_SURFACE_ROUGHNESS = 0.45
DEFAULT_SURFACE_METALLIC = 0.0
DEFAULT_SURFACE_REFLECTANCE = 0.5


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: Any, default: float, lo: float, hi: float) -> float:
    return max(float(lo), min(float(hi), _float_value(value, default)))


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for key in ("surface", "surface_override", "material_surface", "surface_rendering"):
        row = data.get(key)
        if not isinstance(row, Mapping):
            continue
        for nested_key in keys:
            if nested_key in row:
                return row.get(nested_key)
    return None


def normalize_surface_settings(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    strength = _clamp(
        data.get(
            "surface_override_strength",
            data.get(
                "surface_mix",
                _nested(data, "override_strength", "mix", "strength", "enabled"),
            ),
        ),
        DEFAULT_SURFACE_OVERRIDE_STRENGTH,
        0.0,
        1.0,
    )
    return {
        "schema": "tigerstudio.ar_pbr.surface.v1",
        "override_strength": strength,
        "roughness": _clamp(
            data.get("surface_roughness", _nested(data, "roughness")),
            DEFAULT_SURFACE_ROUGHNESS,
            0.04,
            1.0,
        ),
        "metallic": _clamp(
            data.get("surface_metallic", _nested(data, "metallic")),
            DEFAULT_SURFACE_METALLIC,
            0.0,
            1.0,
        ),
        "reflectance": _clamp(
            data.get("surface_reflectance", _nested(data, "reflectance", "specular")),
            DEFAULT_SURFACE_REFLECTANCE,
            0.0,
            1.0,
        ),
    }


def flatten_surface_settings(value: Any) -> dict[str, Any]:
    settings = normalize_surface_settings(value)
    return {
        "surface_override_strength": settings["override_strength"],
        "surface_roughness": settings["roughness"],
        "surface_metallic": settings["metallic"],
        "surface_reflectance": settings["reflectance"],
    }
