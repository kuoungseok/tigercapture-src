"""Texture, UDIM, triplanar, HDRI, and depth sampling helpers for AR/PBR export packets."""
from __future__ import annotations

from typing import Any, Mapping

from app.ar_pbr.depth_occlusion import normalize_depth_frame
from app.ar_pbr.triplanar import (
    normalize_triplanar_settings,
    triplanar_uvs,
    triplanar_weights,
)
from app.ar_pbr.udim import decode_udim_tiles, local_uv_from_udim, udim_tile_id_from_uv


_TEXTURE_CACHE: dict[str, Any] = {}
_TEXTURE_AVERAGE_CACHE: dict[str, tuple[float, float, float]] = {}
_TEXTURE_ARRAY_CACHE: dict[str, Any] = {}
_HDRI_AVERAGE_CACHE: dict[str, tuple[float, float, float]] = {}
_HDRI_ARRAY_CACHE: dict[str, Any] = {}
_HDRI_PREFILTER_CACHE: dict[str, list[Any]] = {}


def _load_texture(path: str):
    key = str(path or "")
    if not key:
        return None
    cached = _TEXTURE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        from PIL import Image

        image = Image.open(key).convert("RGBA")
        _TEXTURE_CACHE[key] = image
        return image
    except Exception:
        return None

def _texture_array(path: str):
    key = str(path or "")
    if not key:
        return None
    cached = _TEXTURE_ARRAY_CACHE.get(key)
    if cached is not None:
        return cached
    image = _load_texture(key)
    if image is None:
        return None
    try:
        import numpy as np

        arr = np.asarray(image.convert("RGBA"), dtype=np.float32) / 255.0
        _TEXTURE_ARRAY_CACHE[key] = arr
        return arr
    except Exception:
        return None

def _texture_udim_arrays(maps: Mapping[str, Any], key: str) -> dict[int, Any]:
    tiles = decode_udim_tiles(maps.get(f"{key}_udim_tiles") if isinstance(maps, Mapping) else None)
    out: dict[int, Any] = {}
    for tile, path in tiles.items():
        arr = _texture_array(str(path or ""))
        if arr is not None:
            out[int(tile)] = arr
    return out

def _hdri_array(path: str):
    key = str(path or "")
    if not key:
        return None
    cached = _HDRI_ARRAY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np
        from app.ar_pbr.hdr import load_radiance_hdr

        hdr_image = load_radiance_hdr(key)
        hdr = np.asarray(hdr_image.pixels, dtype=np.float32)
        if hdr.ndim != 3 or hdr.shape[2] < 3:
            raise ValueError("invalid HDRI shape")
        rgb = np.nan_to_num(hdr[:, :, :3], nan=0.0, posinf=8.0, neginf=0.0)
        rgb = np.clip(rgb, 0.0, 8.0)
        mapped = (rgb * (2.51 * rgb + 0.03)) / (rgb * (2.43 * rgb + 0.59) + 0.14)
        out = np.ascontiguousarray(np.clip(mapped, 0.0, 1.0), dtype=np.float32)
    except Exception:
        return None
    _HDRI_ARRAY_CACHE[key] = out
    return out

def _hdri_average_rgb(path: str) -> tuple[float, float, float]:
    key = str(path or "")
    if not key:
        return (0.26, 0.30, 0.38)
    cached = _HDRI_AVERAGE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np

        hdr = _hdri_array(key)
        if hdr is None:
            raise ValueError("HDRI unavailable")
        avg = np.asarray(hdr, dtype=np.float32).reshape(-1, 3).mean(axis=0)
        out = tuple(float(v) for v in np.clip(avg, 0.04, 1.0))
    except Exception:
        out = (0.26, 0.30, 0.38)
    _HDRI_AVERAGE_CACHE[key] = out  # type: ignore[assignment]
    return out

def _downsample_hdri_level(arr):
    try:
        import numpy as np

        src = np.asarray(arr, dtype=np.float32)
        if src.ndim != 3 or src.shape[2] < 3:
            return None
        h, w = int(src.shape[0]), int(src.shape[1])
        if h <= 1 and w <= 1:
            return None
        h2 = max(1, h // 2)
        w2 = max(1, w // 2)
        cropped = src[: h2 * 2, : w2 * 2, :3]
        if cropped.shape[0] < h2 * 2 or cropped.shape[1] < w2 * 2:
            # Keep odd edge pixels by padding with the last row/column before
            # averaging. This avoids dropping bright strips in small QA HDRIs.
            pad_h = max(0, h2 * 2 - cropped.shape[0])
            pad_w = max(0, w2 * 2 - cropped.shape[1])
            cropped = np.pad(cropped, ((0, pad_h), (0, pad_w), (0, 0)), mode="edge")
        return np.ascontiguousarray(cropped.reshape(h2, 2, w2, 2, 3).mean(axis=(1, 3)), dtype=np.float32)
    except Exception:
        return None

def _hdri_prefilter_levels(path: str):
    key = str(path or "")
    if not key:
        return []
    cached = _HDRI_PREFILTER_CACHE.get(key)
    if cached is not None:
        return cached
    base = _hdri_array(key)
    if base is None:
        return []
    levels = [base]
    current = base
    for _idx in range(1, 7):
        next_level = _downsample_hdri_level(current)
        if next_level is None:
            break
        levels.append(next_level)
        current = next_level
        if int(current.shape[0]) <= 1 and int(current.shape[1]) <= 1:
            break
    _HDRI_PREFILTER_CACHE[key] = levels
    return levels

def _sample_hdri_direction(hdri, dx, dy, dz):
    if hdri is None:
        return None
    try:
        import numpy as np

        arr = np.asarray(hdri, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[2] < 3:
            return None
        length = np.maximum(np.sqrt(dx * dx + dy * dy + dz * dz), 1.0e-6)
        sx = dx / length
        sy = dy / length
        sz = dz / length
        u = (np.arctan2(sz, sx) / (2.0 * np.pi) + 0.5) % 1.0
        v = np.arccos(np.clip(sy, -1.0, 1.0)) / np.pi
        h, w = int(arr.shape[0]), int(arr.shape[1])
        ix = np.clip(np.rint(u * max(1, w - 1)).astype(np.int32), 0, max(0, w - 1))
        iy = np.clip(np.rint(v * max(1, h - 1)).astype(np.int32), 0, max(0, h - 1))
        return arr[iy, ix, :3]
    except Exception:
        return None

def _sample_hdri_prefiltered(hdri_levels, dx, dy, dz, roughness):
    try:
        levels = list(hdri_levels) if isinstance(hdri_levels, (list, tuple)) else [hdri_levels]
    except Exception:
        levels = [hdri_levels]
    levels = [level for level in levels if level is not None]
    if not levels:
        return None
    base = _sample_hdri_direction(levels[0], dx, dy, dz)
    if base is None:
        return None
    try:
        import numpy as np

        rough = np.clip(roughness, 0.0, 1.0)
        if len(levels) <= 1 or float(np.nanmean(rough)) <= 0.045:
            return base
        level_float = float(np.nanmean(np.clip(rough * rough, 0.0, 1.0))) * (len(levels) - 1)
        lo = max(0, min(len(levels) - 1, int(np.floor(level_float))))
        hi = max(0, min(len(levels) - 1, lo + 1))
        mix = max(0.0, min(1.0, level_float - float(lo)))
        low = _sample_hdri_direction(levels[lo], dx, dy, dz)
        high = _sample_hdri_direction(levels[hi], dx, dy, dz)
        if low is None:
            return high if high is not None else base
        if high is None or hi == lo:
            return low
        return np.asarray(low, dtype=np.float32) * (1.0 - mix) + np.asarray(high, dtype=np.float32) * mix
    except Exception:
        return base

def _texture_average_rgb(path: str, image: Any) -> tuple[float, float, float]:
    key = str(path or "")
    cached = _TEXTURE_AVERAGE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np

        small = image.copy()
        small.thumbnail((32, 32))
        arr = np.asarray(small.convert("RGB"), dtype=np.float32)
        avg = arr.reshape(-1, 3).mean(axis=0)
        out = (
            max(1.0, float(avg[0])),
            max(1.0, float(avg[1])),
            max(1.0, float(avg[2])),
        )
    except Exception:
        out = (255.0, 255.0, 255.0)
    _TEXTURE_AVERAGE_CACHE[key] = out
    return out

def _texture_rows(raw: Any) -> list[list[float]]:
    rows: list[list[float]] = []
    if not isinstance(raw, (list, tuple)) or len(raw) < 24:
        return rows
    usable = (len(raw) // 24) * 24
    for idx in range(0, usable, 24):
        try:
            rows.append([float(value) for value in raw[idx:idx + 24]])
        except Exception:
            continue
    return rows

def _normalize_vec3_array(x, y, z):
    import numpy as np

    length = np.maximum(np.sqrt(x * x + y * y + z * z), 1.0e-6)
    return x / length, y / length, z / length

def _sample_texture_nearest(arr, u, v):
    import numpy as np

    if arr is None:
        return None
    h, w = arr.shape[:2]
    if h <= 0 or w <= 0:
        return None
    uu = np.mod(u, 1.0)
    vv = np.mod(v, 1.0)
    x = np.clip(np.rint(uu * max(1, w - 1)).astype(np.int32), 0, max(0, w - 1))
    y = np.clip(np.rint((1.0 - vv) * max(1, h - 1)).astype(np.int32), 0, max(0, h - 1))
    return arr[y, x]

def _sample_texture_nearest_udim(tile_arrays: Mapping[int, Any], fallback_arr, u, v):
    if not tile_arrays:
        return _sample_texture_nearest(fallback_arr, u, v)
    import numpy as np

    tile_ids = udim_tile_id_from_uv(u, v)
    local_u, local_v = local_uv_from_udim(u, v)
    out = None
    matched = np.zeros_like(np.asarray(local_u, dtype=np.float32), dtype=bool)
    for tile, arr in tile_arrays.items():
        sample = _sample_texture_nearest(arr, local_u, local_v)
        if sample is None:
            continue
        if out is None:
            out = np.zeros_like(sample)
        tile_mask = tile_ids == int(tile)
        if bool(tile_mask.any()):
            out[tile_mask] = sample[tile_mask]
            matched |= tile_mask
    if out is None:
        return _sample_texture_nearest(fallback_arr, u, v)
    missing = ~matched
    if bool(missing.any()) and fallback_arr is not None:
        fallback = _sample_texture_nearest(fallback_arr, local_u, local_v)
        if fallback is not None:
            out[missing] = fallback[missing]
    return out

def _sample_texture_projected(
    tile_arrays: Mapping[int, Any],
    fallback_arr: Any,
    u: Any,
    v: Any,
    *,
    world_pos: tuple[Any, Any, Any],
    normal: tuple[Any, Any, Any],
    settings: Mapping[str, Any] | None,
):
    cfg = normalize_triplanar_settings(settings or {})
    if not bool(cfg.get("enabled")) or float(cfg.get("strength", 0.0) or 0.0) <= 0.0:
        return _sample_texture_nearest_udim(tile_arrays, fallback_arr, u, v)
    if fallback_arr is None and not tile_arrays:
        return None
    import numpy as np

    uv_sample = _sample_texture_nearest_udim(tile_arrays, fallback_arr, u, v)
    uv_x, uv_y, uv_z = triplanar_uvs(world_pos[0], world_pos[1], world_pos[2], cfg)
    weights = triplanar_weights(normal[0], normal[1], normal[2], cfg)
    axis_samples = [
        _sample_texture_nearest_udim(tile_arrays, fallback_arr, uv_x[0], uv_x[1]),
        _sample_texture_nearest_udim(tile_arrays, fallback_arr, uv_y[0], uv_y[1]),
        _sample_texture_nearest_udim(tile_arrays, fallback_arr, uv_z[0], uv_z[1]),
    ]
    valid = [sample for sample in axis_samples if sample is not None]
    if not valid:
        return uv_sample
    template = valid[0]
    tri = np.zeros_like(template, dtype=np.float32)
    for sample, weight in zip(axis_samples, weights):
        if sample is None:
            sample = template
        tri += np.asarray(sample, dtype=np.float32) * np.asarray(weight, dtype=np.float32)[:, :, None]
    strength = max(0.0, min(1.0, float(cfg.get("strength", 1.0) or 1.0)))
    if strength < 0.999 and uv_sample is not None:
        tri = np.asarray(uv_sample, dtype=np.float32) * (1.0 - strength) + tri * strength
    return np.clip(tri, 0.0, 1.0)

def _record_udim_sampling(diagnostics: dict[str, Any], maps: Mapping[str, Any], u, v, mask) -> None:
    import numpy as np

    map_rows: list[dict[str, Any]] = []
    all_tiles: set[int] = set()
    for map_name in ("base", "roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity", "height"):
        tiles = decode_udim_tiles(maps.get(f"{map_name}_udim_tiles") if isinstance(maps, Mapping) else None)
        if not tiles:
            continue
        tile_ids = sorted(int(tile) for tile in tiles)
        all_tiles.update(tile_ids)
        map_rows.append({
            "map": map_name,
            "tile_count": len(tile_ids),
            "tiles": tile_ids,
            "primary_tile": int(maps.get(f"{map_name}_udim_primary_tile") or 0),
        })
    if not all_tiles:
        return
    tile_id_arr = udim_tile_id_from_uv(u, v)
    active_mask = np.asarray(mask, dtype=bool)
    matched = active_mask & np.isin(tile_id_arr, list(all_tiles))
    missing = active_mask & ~np.isin(tile_id_arr, list(all_tiles))
    sampled_tiles = set(int(tile) for tile in diagnostics.get("pbr_udim_sampled_tiles", []) or [])
    sampled_tiles.update(int(tile) for tile in np.unique(tile_id_arr[matched]).tolist())
    diagnostics["pbr_udim_rendering"] = {
        "schema": "tigerstudio.ar_pbr.udim.v1",
        "enabled": True,
        "sampling_model": "uv_integer_tile_lookup",
        "preview_policy": "packet_export_full_tile_lookup_live_primary_tile_preview",
        "map_count": len(map_rows),
        "tile_count": sum(int(row["tile_count"]) for row in map_rows),
        "maps": map_rows,
        "render_pass_safe": True,
    }
    diagnostics["pbr_udim_sampled_pixels"] = int(
        diagnostics.get("pbr_udim_sampled_pixels", 0) or 0
    ) + int(matched.sum())
    diagnostics["pbr_udim_missing_tile_pixels"] = int(
        diagnostics.get("pbr_udim_missing_tile_pixels", 0) or 0
    ) + int(missing.sum())
    diagnostics["pbr_udim_sampled_tiles"] = sorted(sampled_tiles)
    diagnostics["pbr_udim_sampled_tile_count"] = len(sampled_tiles)

def _record_triplanar_sampling(
    diagnostics: dict[str, Any],
    maps: Mapping[str, Any],
    settings: Mapping[str, Any],
    mask: Any,
) -> None:
    cfg = normalize_triplanar_settings(settings or {})
    if not bool(cfg.get("enabled")) or float(cfg.get("strength", 0.0) or 0.0) <= 0.0:
        return
    import numpy as np

    map_count = len([
        key
        for key in ("base", "roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity", "height")
        if maps.get(key) or maps.get(f"{key}_udim_tiles")
    ])
    row = dict(cfg)
    row.update({
        "map_count": int(map_count),
        "sampling_model": "normal_weighted_axis_texture_projection",
        "preview_policy": "live_gl_and_packet_export_project_material_maps_from_position",
    })
    diagnostics["pbr_triplanar_rendering"] = row
    diagnostics["pbr_triplanar_applied"] = True
    diagnostics["pbr_triplanar_pixels"] = int(
        diagnostics.get("pbr_triplanar_pixels", 0) or 0
    ) + int(np.asarray(mask, dtype=bool).sum())

def _map_channel(maps: Mapping[str, Any], key: str, default: int = 0) -> int:
    raw = str(maps.get(f"{key}_channel") or "").strip().lower()
    aliases = {"r": 0, "red": 0, "g": 1, "green": 1, "b": 2, "blue": 2, "a": 3, "alpha": 3}
    if raw in aliases:
        return aliases[raw]
    try:
        return max(0, min(3, int(raw)))
    except Exception:
        return int(default)

def _map_float(
    maps: Mapping[str, Any],
    key: str,
    default: float,
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    raw = maps.get(key)
    if raw is None or raw == "":
        value = float(default)
    else:
        try:
            value = float(raw)
        except Exception:
            value = float(default)
    if lo is not None:
        value = max(float(lo), value)
    if hi is not None:
        value = min(float(hi), value)
    return float(value)

def _map_vec3(
    maps: Mapping[str, Any],
    key: str,
    default: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[float, float, float]:
    raw = maps.get(key)
    if isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        text = str(raw or "").strip()
        parts = text.replace(";", ",").split(",") if text else []
    values: list[float] = []
    for idx in range(3):
        try:
            values.append(max(0.0, float(parts[idx])))
        except Exception:
            values.append(float(default[idx]))
    return (values[0], values[1], values[2])

def _sample_texture_channel(sample: Any, channel: int):
    if sample is None:
        return None
    try:
        return sample[:, :, max(0, min(3, int(channel)))]
    except Exception:
        return None

def _depth_array(depth_frame: Any, width: int, height: int):
    return normalize_depth_frame(depth_frame, width, height)

def _rotate_ibl_direction(dx, dy, dz, rotation: float):
    import numpy as np

    try:
        angle = float(rotation) * 2.0 * np.pi
    except Exception:
        angle = 0.0
    if abs(float(angle)) <= 1.0e-8:
        return dx, dy, dz
    c = float(np.cos(angle))
    s = float(np.sin(angle))
    return dx * c - dz * s, dy, dx * s + dz * c

def _load_ibl_probe(path: str):
    if not str(path or "").strip():
        return None
    try:
        from app.ar_pbr.ibl import load_ibl_probe

        return load_ibl_probe(path)
    except Exception:
        return None
