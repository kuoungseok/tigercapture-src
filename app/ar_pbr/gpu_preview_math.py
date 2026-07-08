"""Math/profile helpers for AR/PBR GPU preview packet building."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.render_profile import (
    PROFILE_AUTHORED,
    PROFILE_MARMOSET_PBR,
    PROFILE_VRM_MTOON,
    inspect_asset_render_profiles_from_descriptor,
    marmoset_pbr_available,
    vrm_mtoon_available,
)

def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)

def _max_triangles(settings: Mapping[str, Any]) -> int:
    for key in ("gpu_triangle_limit", "max_gpu_triangles", "max_triangles"):
        try:
            value = int(settings.get(key, 0) or 0)
            if value > 0:
                return max(64, min(240_000, value))
        except Exception:
            pass
    return 120_000

def _sample_triangle_rows(triangles: list[Any], budget: int) -> list[tuple[int, Any]]:
    if budget <= 0:
        return []
    if len(triangles) <= budget:
        return list(enumerate(triangles))
    step = len(triangles) / float(max(1, budget))
    rows: list[tuple[int, Any]] = []
    seen: set[int] = set()
    for sample_index in range(int(budget)):
        triangle_index = min(len(triangles) - 1, int(sample_index * step))
        if triangle_index in seen:
            continue
        seen.add(triangle_index)
        rows.append((triangle_index, triangles[triangle_index]))
    return rows

def _ndc_from_projected(point: tuple[float, float, float], width: int, height: int) -> tuple[float, float]:
    return (
        max(-4.0, min(4.0, (float(point[0]) / max(1.0, float(width))) * 2.0 - 1.0)),
        max(-4.0, min(4.0, 1.0 - (float(point[1]) / max(1.0, float(height))) * 2.0)),
    )

def _triangle_offscreen(points: list[tuple[float, float, float]], width: int, height: int) -> bool:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return max(xs) < -2 or min(xs) > width + 2 or max(ys) < -2 or min(ys) > height + 2

def _shade_tuple_to_floats(color: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return (
        max(0.0, min(1.0, float(color[0]) / 255.0)),
        max(0.0, min(1.0, float(color[1]) / 255.0)),
        max(0.0, min(1.0, float(color[2]) / 255.0)),
        max(0.0, min(1.0, float(color[3]) / 255.0)),
    )

def _extend_ndc_vertex(
    out: list[float],
    point: tuple[float, float, float],
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
) -> None:
    x, y = _ndc_from_projected(point, width, height)
    out.extend((x, y, rgba[0], rgba[1], rgba[2], rgba[3]))

def _normalize3(value: Any, fallback: tuple[float, float, float]) -> tuple[float, float, float]:
    try:
        x = float(value[0])
        y = float(value[1])
        z = float(value[2])
    except Exception:
        return fallback
    length = math.sqrt(x * x + y * y + z * z)
    if length <= 1e-8:
        return fallback
    return (x / length, y / length, z / length)

def _requested_render_profile(track: Mapping[str, Any], settings: Mapping[str, Any]) -> str:
    render = track.get("render") if isinstance(track.get("render"), Mapping) else {}
    for source in (render, settings):
        for key in ("render_profile", "ar_pbr_render_profile", "vrm_render_profile"):
            value = str(source.get(key) or "").strip().casefold()
            if value:
                return value
    return PROFILE_AUTHORED

def _active_render_profile(
    track: Mapping[str, Any],
    settings: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> tuple[str, dict[str, Any], str]:
    profiles = inspect_asset_render_profiles_from_descriptor(descriptor)
    requested = _requested_render_profile(track, settings)
    if requested == PROFILE_VRM_MTOON:
        if vrm_mtoon_available(profiles):
            return PROFILE_VRM_MTOON, profiles, ""
        return PROFILE_AUTHORED, profiles, "vrm_mtoon_requested_without_mtoon_materials"
    if requested == PROFILE_MARMOSET_PBR:
        if marmoset_pbr_available(profiles):
            return PROFILE_MARMOSET_PBR, profiles, ""
        return PROFILE_AUTHORED, profiles, "marmoset_pbr_requested_without_pbr_data"
    if requested == PROFILE_AUTHORED and vrm_mtoon_available(profiles):
        return PROFILE_VRM_MTOON, profiles, ""
    return PROFILE_AUTHORED, profiles, ""

def _lighting_hdri_path(lighting: Mapping[str, Any]) -> str:
    raw = str(lighting.get("hdri_path") or "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            try:
                path = Path(__file__).resolve().parents[2] / path
            except Exception:
                path = Path(raw)
        return str(path)
    try:
        from app.ar_pbr.hdri_presets import resolve_hdri_preset

        preset = resolve_hdri_preset(str(lighting.get("hdri_id") or ""))
        if preset is not None:
            return str(preset.path)
    except Exception:
        pass
    return ""

def _projected_bounds(points: list[tuple[float, float, float]]) -> tuple[float, float, float, float] | None:
    visible = [(float(x), float(y)) for x, y, _z in points if math.isfinite(float(x)) and math.isfinite(float(y))]
    if not visible:
        return None
    xs = [p[0] for p in visible]
    ys = [p[1] for p in visible]
    return min(xs), min(ys), max(xs), max(ys)

def _depth_texture_payload(depth: Any, width: int, height: int):
    if depth is None:
        return None
    try:
        import numpy as np
        from PIL import Image

        arr = np.asarray(depth, dtype=np.float32)
        if arr.ndim != 2 or arr.size <= 0:
            return None
        arr = np.nan_to_num(arr, nan=1.0, posinf=1.0, neginf=0.0)
        if float(np.max(arr)) > 1.5:
            arr = arr / 255.0
        arr = np.clip(arr, 0.0, 1.0)
        max_dim = 640
        h, w = int(arr.shape[0]), int(arr.shape[1])
        if max(w, h) > max_dim:
            scale = float(max_dim) / float(max(w, h))
            target = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
            image = Image.fromarray(np.round(arr * 255.0).astype(np.uint8), mode="L")
            image = image.resize(target, Image.Resampling.BILINEAR)
            return np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
        return np.ascontiguousarray(np.round(arr * 255.0).astype(np.uint8))
    except Exception:
        return None

def _track_is_pending(descriptor: Mapping[str, Any]) -> bool:
    return str(descriptor.get("import_state") or "").casefold() in {"loading", "pending", "error"}
