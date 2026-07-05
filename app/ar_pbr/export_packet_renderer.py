"""Headless AR/PBR export renderer using the GPU-preview packet contract.

The live preview draws AR/PBR objects from ``build_gpu_preview_items`` as flat
``x, y, r, g, b, a`` triangle packets in OpenGL. Export cannot safely create a
preview GL widget inside the worker thread, so this module rasterizes the same
packets into an RGBA frame. It is not the final native/PBR renderer, but it
keeps preview and export on the same mesh/shadow/reflection packet contract.
"""
from __future__ import annotations

import os
from typing import Any, Mapping

from app.ar_pbr.anisotropy import (
    apply_anisotropic_material_polish,
    normalize_anisotropic_material_settings,
)
from app.ar_pbr.pbr_math import (
    cook_torrance_direct,
    energy_conserving_diffuse_weight,
    fresnel_schlick,
    material_f0,
    srgb_to_linear,
)
from app.ar_pbr.ambient_occlusion import (
    apply_screen_ambient_occlusion_to_overlay,
    normalize_ambient_occlusion_settings,
    normalize_packet_ambient_occlusion_settings,
)
from app.ar_pbr.depth_occlusion import (
    apply_depth_occlusion_to_alpha,
    apply_depth_edge_glow_to_rgb,
    depth_occlusion_tolerance,
    normalize_depth_edge_glow_settings,
    normalize_depth_frame,
)
from app.ar_pbr.clearcoat import (
    apply_clearcoat_layer,
    normalize_clearcoat_settings,
)
from app.ar_pbr.cloth import (
    apply_cloth_sheen_shading,
    normalize_cloth_sheen_settings,
)
from app.ar_pbr.glint import (
    apply_glint_sparkle_shading,
    normalize_glint_sparkle_settings,
)
from app.ar_pbr.caustics import (
    apply_caustic_highlights,
    normalize_caustics_settings,
)
from app.ar_pbr.depth_of_field import (
    apply_depth_of_field_to_overlay,
    normalize_depth_of_field_settings,
)
from app.ar_pbr.post_effects import (
    apply_post_effects_to_image,
    normalize_post_effects_settings,
)
from app.ar_pbr.lens_effects import (
    apply_lens_effects_to_image,
    normalize_lens_effects_settings,
)
from app.ar_pbr.lens_flare import (
    apply_lens_flare_to_image,
    normalize_lens_flare_settings,
)
from app.ar_pbr.render_passes import (
    normalize_render_pass_settings,
    render_packet_render_passes,
)
from app.ar_pbr.motion_blur import (
    camera_solution_for_motion_sample,
    merge_motion_blur_settings,
    motion_blur_sample_offsets_ms,
    normalize_motion_blur_settings,
)
from app.ar_pbr.bevel import (
    apply_bevel_normal,
    bevel_edge_mask,
    normalize_bevel_settings,
)
from app.ar_pbr.displacement import (
    apply_displacement_proxy,
    normalize_displacement_settings,
)
from app.ar_pbr.hybrid_rendering import (
    apply_hybrid_gi,
    denoise_float_rgb,
    normalize_hybrid_render_settings,
)
from app.ar_pbr.ray_gi_detail import normalize_ray_gi_detail_settings
from app.ar_pbr.hair import (
    apply_hair_groom_shading,
    normalize_hair_groom_settings,
)
from app.ar_pbr.material_layering import (
    apply_material_layer,
    normalize_material_layering_settings,
)
from app.ar_pbr.microsurface import (
    apply_detail_normal_layer,
    apply_microsurface_roughness,
    normalize_microsurface_settings,
)
from app.ar_pbr.parallax import (
    apply_parallax_uv,
    normalize_parallax_settings,
)
from app.ar_pbr.subsurface import (
    apply_subsurface_scattering,
    normalize_subsurface_settings,
)
from app.ar_pbr.surface import normalize_surface_settings
from app.ar_pbr.tone_mapping import apply_display_transform, normalize_color_management_settings
from app.ar_pbr.transmission import (
    apply_screen_space_refraction,
    normalize_transmission_settings,
)
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
_LEGACY_PBR_VERTEX_STRIDE_FLOATS = 20
_PBR_VERTEX_STRIDE_FLOATS = 23


def _frame_to_pil_rgba(base_frame: Any):
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:
        return None, "", f"missing image dependency: {type(exc).__name__}"

    if isinstance(base_frame, Image.Image):
        return base_frame.convert("RGBA"), "pil", ""
    try:
        arr = np.asarray(base_frame)
    except Exception:
        return None, "", "unsupported base_frame type"
    if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
        return None, "", "base_frame must be HxWx3 or HxWx4"
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0, 255).astype(np.uint8)
    if arr.shape[2] == 3:
        return Image.fromarray(arr, "RGB").convert("RGBA"), "numpy_rgb", ""
    return Image.fromarray(arr, "RGBA"), "numpy_rgba", ""


def _pil_to_original_kind(image: Any, kind: str, original: Any):
    if kind == "pil":
        return image.convert("RGBA")
    try:
        import numpy as np

        arr = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        if kind == "numpy_rgb":
            return arr[:, :, :3].copy()
        return arr.copy()
    except Exception:
        return original


def _ndc_to_pixel(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return (
        (float(x) + 1.0) * 0.5 * max(1, width - 1),
        (1.0 - float(y)) * 0.5 * max(1, height - 1),
    )


def _rgba_from_triangle(row: list[float]) -> tuple[int, int, int, int]:
    rgba = [0.0, 0.0, 0.0, 0.0]
    count = 0
    for offset in (0, 6, 12):
        if offset + 5 >= len(row):
            continue
        rgba[0] += float(row[offset + 2])
        rgba[1] += float(row[offset + 3])
        rgba[2] += float(row[offset + 4])
        rgba[3] += float(row[offset + 5])
        count += 1
    if count <= 0:
        return (0, 0, 0, 0)
    return tuple(
        max(0, min(255, int(round((value / count) * 255.0))))
        for value in rgba
    )  # type: ignore[return-value]


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
    return out  # type: ignore[return-value]


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


def _draw_textured_triangles(image: Any, triangles: Any, diagnostics: dict[str, Any]) -> int:
    if not isinstance(triangles, (list, tuple)):
        return 0
    try:
        from PIL import Image, ImageDraw
        import numpy as np
    except Exception as exc:
        diagnostics.setdefault("warnings", []).append(
            f"texture triangle dependency unavailable: {type(exc).__name__}: {exc}"
        )
        return 0

    width, height = image.size
    drawn = 0
    for tri in triangles:
        if not isinstance(tri, Mapping):
            continue
        texture_path = str(tri.get("texture") or "")
        texture = _load_texture(texture_path)
        if texture is None:
            diagnostics.setdefault("warnings", []).append(f"texture triangle skipped missing texture: {texture_path}")
            continue
        for row in _texture_rows(tri.get("vertices")):
            try:
                points = [
                    _ndc_to_pixel(row[0], row[1], width, height),
                    _ndc_to_pixel(row[8], row[9], width, height),
                    _ndc_to_pixel(row[16], row[17], width, height),
                ]
            except Exception:
                continue
            try:
                xs = [p[0] for p in points]
                ys = [p[1] for p in points]
                bbox_x0 = max(0, int(np.floor(min(xs))))
                bbox_y0 = max(0, int(np.floor(min(ys))))
                bbox_x1 = min(width, int(np.ceil(max(xs))) + 1)
                bbox_y1 = min(height, int(np.ceil(max(ys))) + 1)
                if bbox_x1 <= bbox_x0 or bbox_y1 <= bbox_y0:
                    continue
                tex_w, tex_h = texture.size
                uvs = [
                    (row[2], row[3]),
                    (row[10], row[11]),
                    (row[18], row[19]),
                ]
                src = np.asarray(
                    [
                        [float(u % 1.0) * max(1, tex_w - 1), (1.0 - float(v % 1.0)) * max(1, tex_h - 1)]
                        for u, v in uvs
                    ],
                    dtype=np.float64,
                )
                dst = np.asarray([[points[0][0], points[0][1], 1.0], [points[1][0], points[1][1], 1.0], [points[2][0], points[2][1], 1.0]], dtype=np.float64)
                coeff_u = np.linalg.solve(dst, src[:, 0])
                coeff_v = np.linalg.solve(dst, src[:, 1])
                a, b, c = [float(v) for v in coeff_u]
                d, e, f = [float(v) for v in coeff_v]
                coeffs = (
                    a,
                    b,
                    a * bbox_x0 + b * bbox_y0 + c,
                    d,
                    e,
                    d * bbox_x0 + e * bbox_y0 + f,
                )
                patch_size = (bbox_x1 - bbox_x0, bbox_y1 - bbox_y0)
                patch = texture.transform(
                    patch_size,
                    Image.Transform.AFFINE,
                    coeffs,
                    resample=Image.Resampling.BILINEAR,
                ).convert("RGBA")
                mask = Image.new("L", patch_size, 0)
                local_points = [(x - bbox_x0, y - bbox_y0) for x, y in points]
                shade = _rgba_from_triangle([
                    row[0],
                    row[1],
                    row[4],
                    row[5],
                    row[6],
                    row[7],
                    row[8],
                    row[9],
                    row[12],
                    row[13],
                    row[14],
                    row[15],
                    row[16],
                    row[17],
                    row[20],
                    row[21],
                    row[22],
                    row[23],
                ])
                ImageDraw.Draw(mask).polygon(local_points, fill=shade[3])
                avg = _texture_average_rgb(texture_path, texture)
                factors = np.asarray(
                    [
                        max(0.0, min(4.0, float(shade[0]) / avg[0])),
                        max(0.0, min(4.0, float(shade[1]) / avg[1])),
                        max(0.0, min(4.0, float(shade[2]) / avg[2])),
                    ],
                    dtype=np.float32,
                )
                arr = np.asarray(patch, dtype=np.float32)
                arr[:, :, :3] = np.clip(arr[:, :, :3] * factors[None, None, :], 0, 255)
                mask_arr = np.asarray(mask, dtype=np.float32) / 255.0
                arr[:, :, 3] = np.clip(arr[:, :, 3] * mask_arr, 0, 255)
                shaded_patch = Image.fromarray(arr.astype(np.uint8), "RGBA")
                image.alpha_composite(shaded_patch, (bbox_x0, bbox_y0))
                drawn += 1
            except Exception as exc:
                diagnostics.setdefault("warnings", []).append(
                    f"texture triangle skipped: {type(exc).__name__}: {exc}"
                )
    return drawn


def _pbr_vertex_stride(raw: Any) -> int:
    try:
        count = len(raw)
    except Exception:
        return _LEGACY_PBR_VERTEX_STRIDE_FLOATS
    if count >= _PBR_VERTEX_STRIDE_FLOATS * 3 and count % _PBR_VERTEX_STRIDE_FLOATS == 0:
        return _PBR_VERTEX_STRIDE_FLOATS
    return _LEGACY_PBR_VERTEX_STRIDE_FLOATS


def _pbr_rows(raw: Any) -> list[tuple[list[float], int]]:
    rows: list[tuple[list[float], int]] = []
    if not isinstance(raw, (list, tuple)):
        return rows
    stride = _pbr_vertex_stride(raw)
    triangle_floats = stride * 3
    if len(raw) < triangle_floats:
        return rows
    usable = (len(raw) // triangle_floats) * triangle_floats
    for idx in range(0, usable, triangle_floats):
        try:
            rows.append(([float(value) for value in raw[idx:idx + triangle_floats]], stride))
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


def _draw_pbr_triangles(
    image: Any,
    triangles: Any,
    lighting: Mapping[str, Any],
    diagnostics: dict[str, Any],
    *,
    depth: Any = None,
    dof_depth: Any = None,
    settings: Mapping[str, Any] | None = None,
    occlusion_enabled: bool = False,
) -> int:
    if not isinstance(triangles, (list, tuple)):
        return 0
    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:
        diagnostics.setdefault("warnings", []).append(
            f"pbr triangle dependency unavailable: {type(exc).__name__}: {exc}"
        )
        return 0

    width, height = image.size
    light_raw = lighting.get("light_dir") if isinstance(lighting, Mapping) else None
    try:
        light = np.asarray([-float(light_raw[0]), -float(light_raw[1]), -float(light_raw[2])], dtype=np.float32)
    except Exception:
        light = np.asarray([0.35, 0.65, 0.72], dtype=np.float32)
    light_len = max(1.0e-6, float(np.linalg.norm(light)))
    light = light / light_len
    view = np.asarray([0.0, 0.0, -1.0], dtype=np.float32)
    half_vec = light + view
    half_len = max(1.0e-6, float(np.linalg.norm(half_vec)))
    half_vec = half_vec / half_len
    try:
        direct_strength = max(0.0, min(4.0, float(lighting.get("direct_strength", 0.85))))
    except Exception:
        direct_strength = 0.85
    try:
        ibl_exposure = max(0.0, min(8.0, float(lighting.get("ibl_exposure", 1.0))))
    except Exception:
        ibl_exposure = 1.0
    try:
        ibl_rotation = max(-1.0, min(1.0, float(lighting.get("ibl_rotation", 0.0))))
    except Exception:
        ibl_rotation = 0.0
    color_management = normalize_color_management_settings(lighting)
    hybrid_rendering = normalize_hybrid_render_settings(lighting)
    ray_gi_detail = normalize_ray_gi_detail_settings(lighting)
    ambient_occlusion_rendering = normalize_ambient_occlusion_settings(lighting)
    depth_edge_glow = normalize_depth_edge_glow_settings(lighting)
    transmission_rendering = normalize_transmission_settings(lighting)
    clearcoat_rendering = normalize_clearcoat_settings(lighting)
    parallax_rendering = normalize_parallax_settings(lighting)
    displacement_rendering = normalize_displacement_settings(lighting)
    bevel_rendering = normalize_bevel_settings(lighting)
    material_layering = normalize_material_layering_settings(lighting)
    surface_rendering = normalize_surface_settings(lighting)
    subsurface_rendering = normalize_subsurface_settings(lighting)
    hair_groom_rendering = normalize_hair_groom_settings(lighting)
    cloth_sheen_rendering = normalize_cloth_sheen_settings(lighting)
    glint_sparkle_rendering = normalize_glint_sparkle_settings(lighting)
    caustics_rendering = normalize_caustics_settings(lighting)
    anisotropic_rendering = normalize_anisotropic_material_settings(lighting)
    microsurface_rendering = normalize_microsurface_settings(lighting)
    depth_of_field_rendering = normalize_depth_of_field_settings(lighting)
    lens_effects_rendering = normalize_lens_effects_settings(lighting)
    lens_flare_rendering = normalize_lens_flare_settings(lighting)
    triplanar_rendering = normalize_triplanar_settings(lighting)
    diagnostics["pbr_color_management"] = color_management
    diagnostics["pbr_hybrid_rendering"] = hybrid_rendering
    diagnostics["pbr_ray_gi_detail"] = ray_gi_detail
    diagnostics["pbr_ambient_occlusion_rendering"] = ambient_occlusion_rendering
    diagnostics["pbr_depth_edge_glow"] = normalize_depth_edge_glow_settings(lighting)
    diagnostics["pbr_transmission_rendering"] = transmission_rendering
    diagnostics["pbr_clearcoat_rendering"] = clearcoat_rendering
    diagnostics["pbr_parallax_rendering"] = parallax_rendering
    diagnostics["pbr_displacement_rendering"] = displacement_rendering
    diagnostics["pbr_bevel_rendering"] = bevel_rendering
    diagnostics["pbr_material_layering"] = material_layering
    diagnostics["pbr_surface_rendering"] = surface_rendering
    diagnostics["pbr_subsurface_rendering"] = subsurface_rendering
    diagnostics["pbr_hair_groom_rendering"] = hair_groom_rendering
    diagnostics["pbr_cloth_sheen_rendering"] = cloth_sheen_rendering
    diagnostics["pbr_glint_sparkle_rendering"] = glint_sparkle_rendering
    diagnostics["pbr_caustics_rendering"] = caustics_rendering
    diagnostics["pbr_anisotropic_rendering"] = anisotropic_rendering
    diagnostics["pbr_microsurface_rendering"] = microsurface_rendering
    diagnostics["pbr_depth_of_field_rendering"] = depth_of_field_rendering
    diagnostics["pbr_lens_effects_rendering"] = lens_effects_rendering
    diagnostics["pbr_lens_flare_rendering"] = lens_flare_rendering
    diagnostics["pbr_triplanar_rendering"] = triplanar_rendering
    hdri_path = str(lighting.get("hdri_path") or "")
    ibl_probe = _load_ibl_probe(hdri_path)
    hdri_env = ibl_probe.environment if ibl_probe is not None and ibl_probe.available else None
    hdri_prefilter = []
    if ibl_probe is not None and ibl_probe.available:
        env_rgb = np.asarray(ibl_probe.average_rgb, dtype=np.float32) * ibl_exposure
        diagnostics["pbr_hdri_directional_sampling"] = True
        diagnostics["pbr_prefiltered_ibl_level_count"] = max(
            int(diagnostics.get("pbr_prefiltered_ibl_level_count", 0) or 0),
            int(ibl_probe.prefilter_level_count),
        )
        diagnostics["pbr_irradiance_ibl"] = True
        diagnostics["pbr_brdf_lut"] = True
        diagnostics["pbr_ibl_probe"] = ibl_probe.diagnostics()
    else:
        hdri_env = _hdri_array(hdri_path)
        hdri_prefilter = _hdri_prefilter_levels(hdri_path)
        env_rgb = np.asarray(_hdri_average_rgb(hdri_path), dtype=np.float32) * ibl_exposure
        if hdri_env is not None:
            diagnostics["pbr_hdri_directional_sampling"] = True
            diagnostics["pbr_prefiltered_ibl_level_count"] = max(
                int(diagnostics.get("pbr_prefiltered_ibl_level_count", 0) or 0),
                len(hdri_prefilter),
            )
    settings_map = settings or {}
    try:
        camera_z = max(0.1, float(settings_map.get("camera_z", 3.25)))
    except Exception:
        camera_z = 3.25
    occlusion_tolerance = depth_occlusion_tolerance(settings_map)

    drawn = 0
    for tri in triangles:
        if not isinstance(tri, Mapping):
            continue
        maps = tri.get("maps") if isinstance(tri.get("maps"), Mapping) else {}
        unlit = str((maps or {}).get("unlit") or "").strip().casefold() in {"1", "true", "yes", "on"}
        texture_path = str((maps or {}).get("base") or tri.get("texture") or "")
        base_arr = _texture_array(texture_path)
        rough_arr = _texture_array(str((maps or {}).get("roughness") or ""))
        metal_arr = _texture_array(str((maps or {}).get("metallic") or ""))
        spec_arr = _texture_array(str((maps or {}).get("specular") or ""))
        normal_arr = _texture_array(str((maps or {}).get("normal") or ""))
        occlusion_arr = _texture_array(str((maps or {}).get("occlusion") or ""))
        emissive_arr = _texture_array(str((maps or {}).get("emissive") or ""))
        opacity_arr = _texture_array(str((maps or {}).get("opacity") or ""))
        height_arr = _texture_array(str((maps or {}).get("height") or ""))
        base_udim = _texture_udim_arrays(maps or {}, "base")
        rough_udim = _texture_udim_arrays(maps or {}, "roughness")
        metal_udim = _texture_udim_arrays(maps or {}, "metallic")
        spec_udim = _texture_udim_arrays(maps or {}, "specular")
        normal_udim = _texture_udim_arrays(maps or {}, "normal")
        occlusion_udim = _texture_udim_arrays(maps or {}, "occlusion")
        emissive_udim = _texture_udim_arrays(maps or {}, "emissive")
        opacity_udim = _texture_udim_arrays(maps or {}, "opacity")
        height_udim = _texture_udim_arrays(maps or {}, "height")
        if (
            base_arr is None
            and rough_arr is None
            and metal_arr is None
            and spec_arr is None
            and normal_arr is None
            and occlusion_arr is None
            and emissive_arr is None
            and opacity_arr is None
            and height_arr is None
            and not any((base_udim, rough_udim, metal_udim, spec_udim, normal_udim, occlusion_udim, emissive_udim, opacity_udim, height_udim))
        ):
            diagnostics.setdefault("warnings", []).append(f"pbr triangle skipped missing texture maps: {texture_path}")
            continue
        for row, stride in _pbr_rows(tri.get("vertices")):
            try:
                p0 = _ndc_to_pixel(row[0], row[1], width, height)
                p1 = _ndc_to_pixel(row[stride], row[stride + 1], width, height)
                p2 = _ndc_to_pixel(row[stride * 2], row[stride * 2 + 1], width, height)
            except Exception:
                continue
            xs = [p0[0], p1[0], p2[0]]
            ys = [p0[1], p1[1], p2[1]]
            box_x0 = max(0, int(np.floor(min(xs))))
            box_y0 = max(0, int(np.floor(min(ys))))
            box_x1 = min(width, int(np.ceil(max(xs))) + 1)
            box_y1 = min(height, int(np.ceil(max(ys))) + 1)
            if box_x1 <= box_x0 or box_y1 <= box_y0:
                continue
            x0, y0 = p0
            x1, y1 = p1
            x2, y2 = p2
            denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(denom) <= 1.0e-8:
                continue
            yy, xx = np.mgrid[box_y0:box_y1, box_x0:box_x1].astype(np.float32)
            px = xx + 0.5
            py = yy + 0.5
            w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / denom
            w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / denom
            w2 = 1.0 - w0 - w1
            mask = (w0 >= -0.001) & (w1 >= -0.001) & (w2 >= -0.001)
            if not bool(mask.any()):
                continue

            def interp(offset: int):
                return (
                    w0 * float(row[offset])
                    + w1 * float(row[stride + offset])
                    + w2 * float(row[stride * 2 + offset])
                )

            geom_nx, geom_ny, geom_nz = _normalize_vec3_array(interp(4), interp(5), interp(6))
            geom_tx, geom_ty, geom_tz = _normalize_vec3_array(interp(7), interp(8), interp(9))
            geom_bx, geom_by, geom_bz = _normalize_vec3_array(interp(10), interp(11), interp(12))
            u = interp(2)
            v = interp(3)
            if stride >= _PBR_VERTEX_STRIDE_FLOATS:
                world_x, world_y, world_z = interp(20), interp(21), interp(22)
            else:
                world_x = np.zeros_like(u, dtype=np.float32)
                world_y = np.zeros_like(u, dtype=np.float32)
                world_z = np.zeros_like(u, dtype=np.float32)
            triplanar_pos = (world_x, world_y, world_z)
            triplanar_normal = (geom_nx, geom_ny, geom_nz)
            height_sample = (
                _sample_texture_projected(
                    height_udim,
                    height_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if height_arr is not None or height_udim else None
            )
            height_channel = _sample_texture_channel(height_sample, _map_channel(maps or {}, "height", 0))
            if height_channel is not None and bool(displacement_rendering.get("enabled")):
                world_x, world_y, world_z, displacement_diag = apply_displacement_proxy(
                    world_pos=(world_x, world_y, world_z),
                    normal=(geom_nx, geom_ny, geom_nz),
                    tangent=(geom_tx, geom_ty, geom_tz),
                    bitangent=(geom_bx, geom_by, geom_bz),
                    height=height_channel,
                    vector_sample=height_sample,
                    alpha=mask.astype(np.float32),
                    settings=displacement_rendering,
                )
                triplanar_pos = (world_x, world_y, world_z)
                if bool(displacement_diag.get("applied")):
                    diagnostics["pbr_displacement_rendering"] = dict(
                        displacement_diag.get("rendering") or displacement_rendering
                    )
                    diagnostics["pbr_displacement_applied"] = True
                    diagnostics["pbr_displacement_pixels"] = int(
                        diagnostics.get("pbr_displacement_pixels", 0) or 0
                    ) + int(displacement_diag.get("changed_pixels", 0) or 0)
                    diagnostics["pbr_displacement_height_pixels"] = int(
                        diagnostics.get("pbr_displacement_height_pixels", 0) or 0
                    ) + int(displacement_diag.get("height_pixels", 0) or 0)
                    diagnostics["pbr_displacement_vector_pixels"] = int(
                        diagnostics.get("pbr_displacement_vector_pixels", 0) or 0
                    ) + int(displacement_diag.get("vector_pixels", 0) or 0)
                    diagnostics["pbr_displacement_max_offset"] = max(
                        float(diagnostics.get("pbr_displacement_max_offset", 0.0) or 0.0),
                        float(displacement_diag.get("max_offset", 0.0) or 0.0),
                    )
                    diagnostics["pbr_displacement_mean_offset"] = max(
                        float(diagnostics.get("pbr_displacement_mean_offset", 0.0) or 0.0),
                        float(displacement_diag.get("mean_offset", 0.0) or 0.0),
                    )
                    diagnostics["pbr_displacement_parallax_fallback"] = bool(
                        displacement_rendering.get("parallax_fallback")
                    )
            if height_channel is not None and bool(parallax_rendering.get("enabled")):
                view_tx = geom_tx * view[0] + geom_ty * view[1] + geom_tz * view[2]
                view_ty = geom_bx * view[0] + geom_by * view[1] + geom_bz * view[2]
                u, v = apply_parallax_uv(
                    u,
                    v,
                    height=height_channel,
                    tangent_view_xy=(view_tx, view_ty),
                    settings=parallax_rendering,
                )
                diagnostics["pbr_parallax_applied"] = True
                diagnostics["pbr_parallax_pixels"] = int(
                    diagnostics.get("pbr_parallax_pixels", 0) or 0
                ) + int(mask.sum())
            sample_v = 1.0 - v if unlit else v
            _record_udim_sampling(diagnostics, maps or {}, u, sample_v, mask)
            _record_triplanar_sampling(diagnostics, maps or {}, triplanar_rendering, mask)
            base = (
                _sample_texture_projected(
                    base_udim,
                    base_arr,
                    u,
                    sample_v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if base_arr is not None or base_udim else None
            )
            opacity_sample = (
                _sample_texture_projected(
                    opacity_udim,
                    opacity_arr,
                    u,
                    sample_v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if opacity_arr is not None or opacity_udim else None
            )
            if base is not None:
                albedo = srgb_to_linear(base[:, :, :3])
                alpha = np.clip(base[:, :, 3] * interp(16), 0.0, 1.0) * mask.astype(np.float32)
            else:
                vertex_rgb = np.dstack((
                    np.clip(interp(13), 0.0, 1.0),
                    np.clip(interp(14), 0.0, 1.0),
                    np.clip(interp(15), 0.0, 1.0),
                ))
                albedo = srgb_to_linear(vertex_rgb)
                alpha = np.clip(interp(16), 0.0, 1.0) * mask.astype(np.float32)
            opacity_channel = _sample_texture_channel(opacity_sample, _map_channel(maps or {}, "opacity", 0))
            if opacity_channel is not None:
                alpha *= np.clip(opacity_channel, 0.0, 1.0)
                diagnostics["pbr_opacity_map_applied"] = True
                diagnostics["pbr_opacity_map_pixels"] = int(
                    diagnostics.get("pbr_opacity_map_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            alpha_cutoff = _map_float(maps or {}, "alpha_cutoff", 0.001, lo=0.0, hi=1.0)
            if alpha_cutoff > 0.001:
                before_cutoff = int((alpha > 0.001).sum())
                alpha = np.where(alpha > alpha_cutoff, alpha, 0.0)
                after_cutoff = int((alpha > 0.001).sum())
                if before_cutoff > after_cutoff:
                    diagnostics["pbr_alpha_cutoff_pixels"] = int(
                        diagnostics.get("pbr_alpha_cutoff_pixels", 0) or 0
                    ) + (before_cutoff - after_cutoff)
            object_depth = max(
                0.0,
                min(1.0, float(tri.get("object_depth", 0.0) or 0.0)),
            )
            if object_depth <= 0.0:
                object_depth = max(0.0, min(1.0, float(tri.get("z", 0.0) or 0.0) / (camera_z * 2.0)))
            depth_patch_for_effect = None
            if occlusion_enabled and depth is not None:
                try:
                    depth_patch = depth[box_y0:box_y1, box_x0:box_x1]
                    depth_patch_for_effect = depth_patch
                    before = int((alpha > 0.001).sum())
                    alpha, occlusion_diag = apply_depth_occlusion_to_alpha(
                        alpha,
                        depth_patch,
                        object_depth=object_depth,
                        settings={**dict(settings_map), "occlusion_tolerance": occlusion_tolerance},
                    )
                    after = int((alpha > 0.001).sum())
                    if before > after:
                        diagnostics["pbr_depth_occluded_pixels"] = int(
                            diagnostics.get("pbr_depth_occluded_pixels", 0) or 0
                        ) + int(occlusion_diag.get("occluded_pixels", before - after) or 0)
                        diagnostics["pbr_depth_occlusion_applied"] = True
                except Exception as exc:
                    diagnostics.setdefault("warnings", []).append(
                        f"pbr depth occlusion skipped: {type(exc).__name__}: {exc}"
                    )
            if not bool((alpha > 0.001).any()):
                continue
            if dof_depth is not None and bool(depth_of_field_rendering.get("enabled")):
                try:
                    dof_patch = dof_depth[box_y0:box_y1, box_x0:box_x1]
                    dof_patch[alpha > 0.001] = float(object_depth)
                except Exception:
                    pass
            if unlit:
                gain = max(0.65, min(1.35, 0.92 + float(ibl_exposure) * 0.08))
                rgb = apply_display_transform(albedo * gain, color_management)
                dst = np.asarray(image.crop((box_x0, box_y0, box_x1, box_y1)).convert("RGBA"), dtype=np.float32) / 255.0
                src_a = alpha[:, :, None]
                dst_a = dst[:, :, 3:4]
                out_a = src_a + dst_a * (1.0 - src_a)
                out_rgb = np.where(
                    out_a > 1.0e-6,
                    (rgb * src_a + dst[:, :, :3] * dst_a * (1.0 - src_a)) / np.maximum(out_a, 1.0e-6),
                    0.0,
                )
                out = np.concatenate([out_rgb, out_a], axis=2)
                out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
                image.paste(Image.fromarray(out, "RGBA"), (box_x0, box_y0))
                diagnostics["pbr_unlit_sampled_triangle_count"] = int(
                    diagnostics.get("pbr_unlit_sampled_triangle_count", 0) or 0
                ) + 1
                drawn += 1
                continue

            nx, ny, nz = geom_nx, geom_ny, geom_nz
            tx, ty, tz = geom_tx, geom_ty, geom_tz
            bx, by, bz = geom_bx, geom_by, geom_bz
            normal_sample = (
                _sample_texture_projected(
                    normal_udim,
                    normal_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if normal_arr is not None or normal_udim else None
            )
            if normal_sample is not None:
                tn = normal_sample[:, :, :3] * 2.0 - 1.0
                nx = tx * tn[:, :, 0] + bx * tn[:, :, 1] + nx * tn[:, :, 2]
                ny = ty * tn[:, :, 0] + by * tn[:, :, 1] + ny * tn[:, :, 2]
                nz = tz * tn[:, :, 0] + bz * tn[:, :, 1] + nz * tn[:, :, 2]
                nx, ny, nz = _normalize_vec3_array(nx, ny, nz)
            nx, ny, nz, detail_normal_diag = apply_detail_normal_layer(
                normal=(nx, ny, nz),
                tangent=(tx, ty, tz),
                bitangent=(bx, by, bz),
                uv=(u, v),
                world_pos=(world_x, world_y, world_z),
                alpha=alpha,
                settings=microsurface_rendering,
            )
            if bool(detail_normal_diag.get("applied")):
                diagnostics["pbr_microsurface_rendering"] = dict(
                    detail_normal_diag.get("rendering") or microsurface_rendering
                )
                diagnostics["pbr_detail_normal_applied"] = True
                diagnostics["pbr_detail_normal_pixels"] = int(
                    diagnostics.get("pbr_detail_normal_pixels", 0) or 0
                ) + int(detail_normal_diag.get("changed_pixels", 0) or 0)
                diagnostics["pbr_detail_normal_max_delta"] = max(
                    float(diagnostics.get("pbr_detail_normal_max_delta", 0.0) or 0.0),
                    float(detail_normal_diag.get("max_delta", 0.0) or 0.0),
                )
            bevel_mask = bevel_edge_mask(w0, w1, w2, bevel_rendering)
            if bool(bevel_rendering.get("enabled")) and bool((bevel_mask > 0.001).any()):
                nx, ny, nz = apply_bevel_normal(
                    nx,
                    ny,
                    nz,
                    barycentric=(w0, w1, w2),
                    tangent=(tx, ty, tz),
                    bitangent=(bx, by, bz),
                    settings=bevel_rendering,
                )
                diagnostics["pbr_bevel_applied"] = True
                diagnostics["pbr_bevel_pixels"] = int(
                    diagnostics.get("pbr_bevel_pixels", 0) or 0
                ) + int(((alpha > 0.001) & (bevel_mask > 0.001)).sum())

            ndotv = nx * view[0] + ny * view[1] + nz * view[2]
            flip = ndotv < 0.0
            nx = np.where(flip, -nx, nx)
            ny = np.where(flip, -ny, ny)
            nz = np.where(flip, -nz, nz)
            ndotv = np.maximum(nx * view[0] + ny * view[1] + nz * view[2], 0.0)
            lambert = np.maximum(nx * light[0] + ny * light[1] + nz * light[2], 0.0)
            hdotn = np.maximum(nx * half_vec[0] + ny * half_vec[1] + nz * half_vec[2], 0.0)

            roughness = np.clip(interp(17), 0.04, 1.0)
            metallic = np.clip(interp(18), 0.0, 1.0)
            reflectance = np.clip(interp(19), 0.0, 1.0)
            rough_sample = (
                _sample_texture_projected(
                    rough_udim,
                    rough_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if rough_arr is not None or rough_udim else None
            )
            metal_sample = (
                _sample_texture_projected(
                    metal_udim,
                    metal_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if metal_arr is not None or metal_udim else None
            )
            spec_sample = (
                _sample_texture_projected(
                    spec_udim,
                    spec_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if spec_arr is not None or spec_udim else None
            )
            occlusion_sample = (
                _sample_texture_projected(
                    occlusion_udim,
                    occlusion_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if occlusion_arr is not None or occlusion_udim else None
            )
            emissive_sample = (
                _sample_texture_projected(
                    emissive_udim,
                    emissive_arr,
                    u,
                    v,
                    world_pos=triplanar_pos,
                    normal=triplanar_normal,
                    settings=triplanar_rendering,
                )
                if emissive_arr is not None or emissive_udim else None
            )
            rough_channel = _sample_texture_channel(rough_sample, _map_channel(maps or {}, "roughness", 0))
            metal_channel = _sample_texture_channel(metal_sample, _map_channel(maps or {}, "metallic", 0))
            spec_channel = _sample_texture_channel(spec_sample, _map_channel(maps or {}, "specular", 0))
            occlusion_channel = _sample_texture_channel(occlusion_sample, _map_channel(maps or {}, "occlusion", 0))
            if rough_channel is not None:
                roughness = np.clip(rough_channel, 0.04, 1.0)
            if metal_channel is not None:
                metallic = np.clip(metal_channel, 0.0, 1.0)
            if spec_channel is not None:
                reflectance = np.clip(spec_channel, 0.0, 1.0)
            if occlusion_channel is not None:
                ao = np.clip(occlusion_channel, 0.0, 1.0)
                diagnostics["pbr_occlusion_map_pixels"] = int(
                    diagnostics.get("pbr_occlusion_map_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
                diagnostics["pbr_occlusion_map_applied"] = True
            else:
                ao = np.ones_like(roughness, dtype=np.float32)
            surface_mix = max(0.0, min(1.0, float(surface_rendering.get("override_strength", 0.0) or 0.0)))
            if surface_mix > 1.0e-6:
                roughness = np.clip(
                    roughness * (1.0 - surface_mix)
                    + float(surface_rendering.get("roughness", 0.45) or 0.45) * surface_mix,
                    0.04,
                    1.0,
                )
                metallic = np.clip(
                    metallic * (1.0 - surface_mix)
                    + float(surface_rendering.get("metallic", 0.0) or 0.0) * surface_mix,
                    0.0,
                    1.0,
                )
                reflectance = np.clip(
                    reflectance * (1.0 - surface_mix)
                    + float(surface_rendering.get("reflectance", 0.5) or 0.5) * surface_mix,
                    0.0,
                    1.0,
                )
                diagnostics["pbr_surface_applied"] = True
                diagnostics["pbr_surface_pixels"] = int(
                    diagnostics.get("pbr_surface_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            emissive_factor = np.asarray(_map_vec3(maps or {}, "emissive_factor"), dtype=np.float32)
            emissive = np.zeros_like(albedo, dtype=np.float32)
            if emissive_sample is not None:
                emissive = srgb_to_linear(emissive_sample[:, :, :3]) * emissive_factor[None, None, :]
                diagnostics["pbr_emissive_map_applied"] = True
                diagnostics["pbr_emissive_map_pixels"] = int(
                    diagnostics.get("pbr_emissive_map_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            elif bool(np.any(emissive_factor > 0.0)):
                emissive = albedo * emissive_factor[None, None, :]
            albedo, roughness, metallic, alpha, emissive = apply_material_layer(
                albedo,
                roughness,
                metallic,
                alpha,
                emissive,
                mask=mask.astype(np.float32),
                settings=material_layering,
            )
            if bool(material_layering.get("enabled")):
                diagnostics["pbr_material_layer_applied"] = True
                diagnostics["pbr_material_layer_pixels"] = int(
                    diagnostics.get("pbr_material_layer_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            roughness, micro_roughness_diag = apply_microsurface_roughness(
                roughness,
                uv=(u, v),
                world_pos=(world_x, world_y, world_z),
                alpha=alpha,
                settings=microsurface_rendering,
            )
            if bool(micro_roughness_diag.get("applied")):
                diagnostics["pbr_microsurface_rendering"] = dict(
                    micro_roughness_diag.get("rendering") or microsurface_rendering
                )
                diagnostics["pbr_micro_roughness_applied"] = True
                diagnostics["pbr_micro_roughness_pixels"] = int(
                    diagnostics.get("pbr_micro_roughness_pixels", 0) or 0
                ) + int(micro_roughness_diag.get("changed_pixels", 0) or 0)
                diagnostics["pbr_micro_roughness_mean"] = max(
                    float(diagnostics.get("pbr_micro_roughness_mean", 0.0) or 0.0),
                    float(micro_roughness_diag.get("mean_roughness", 0.0) or 0.0),
                )
                diagnostics["pbr_micro_roughness_max_delta"] = max(
                    float(diagnostics.get("pbr_micro_roughness_max_delta", 0.0) or 0.0),
                    float(micro_roughness_diag.get("max_delta", 0.0) or 0.0),
                )

            f0 = material_f0(albedo, metallic, reflectance)
            fresnel = fresnel_schlick(ndotv, f0)
            diffuse_env = None
            spec_env_rgb = None
            brdf_terms = None
            if hdri_env is not None:
                rnx, rny, rnz = _rotate_ibl_direction(nx, ny, nz, ibl_rotation)
                if ibl_probe is not None:
                    diffuse_env = ibl_probe.sample_irradiance(rnx, rny, rnz)
                else:
                    diffuse_env = _sample_hdri_direction(hdri_env, rnx, rny, rnz)
                rx = -view[0] + 2.0 * ndotv * nx
                ry = -view[1] + 2.0 * ndotv * ny
                rz = -view[2] + 2.0 * ndotv * nz
                rrx, rry, rrz = _rotate_ibl_direction(rx, ry, rz, ibl_rotation)
                if ibl_probe is not None:
                    spec_env_rgb = ibl_probe.sample_prefiltered(rrx, rry, rrz, roughness)
                    brdf_terms = ibl_probe.sample_brdf(ndotv, roughness)
                else:
                    spec_env_rgb = _sample_hdri_prefiltered(hdri_prefilter or [hdri_env], rrx, rry, rrz, roughness)
                if diffuse_env is not None and spec_env_rgb is not None:
                    diagnostics["pbr_hdri_sampled_pixels"] = int(
                        diagnostics.get("pbr_hdri_sampled_pixels", 0) or 0
                    ) + int((alpha > 0.001).sum())
                    if float(np.nanmean(roughness)) > 0.045:
                        diagnostics["pbr_prefiltered_ibl"] = True
                        diagnostics["pbr_prefiltered_ibl_pixels"] = int(
                            diagnostics.get("pbr_prefiltered_ibl_pixels", 0) or 0
                        ) + int((alpha > 0.001).sum())
            if diffuse_env is None:
                diffuse_env = env_rgb[None, None, :]
            else:
                diffuse_env = np.asarray(diffuse_env, dtype=np.float32) * ibl_exposure
            if spec_env_rgb is None:
                spec_env_rgb = env_rgb[None, None, :]
            else:
                spec_env_rgb = np.asarray(spec_env_rgb, dtype=np.float32) * ibl_exposure
                if ibl_probe is None:
                    spec_env_rgb = spec_env_rgb * (1.0 - roughness[:, :, None] * 0.52) + env_rgb[None, None, :] * (roughness[:, :, None] * 0.52)

            if brdf_terms is not None:
                brdf_terms = np.asarray(brdf_terms, dtype=np.float32)
                brdf_scale = brdf_terms[:, :, 0:1]
                brdf_bias = brdf_terms[:, :, 1:2]
                specular_term = fresnel * brdf_scale + brdf_bias
                diagnostics["pbr_brdf_lut_sampled_pixels"] = int(
                    diagnostics.get("pbr_brdf_lut_sampled_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            else:
                specular_term = fresnel * (1.25 - roughness[:, :, None] * 0.45)

            diffuse_weight = energy_conserving_diffuse_weight(fresnel, metallic)
            diffuse = albedo * diffuse_env * diffuse_weight * ao[:, :, None]
            specular_env = spec_env_rgb * specular_term * (0.64 + 0.36 * ao[:, :, None])
            vdoth = np.maximum(view[0] * half_vec[0] + view[1] * half_vec[1] + view[2] * half_vec[2], 0.0)
            direct = cook_torrance_direct(
                albedo=albedo,
                f0=f0,
                roughness=roughness,
                metallic=metallic,
                ndotl=lambert,
                ndotv=ndotv,
                ndoth=hdotn,
                vdoth=np.full_like(roughness, float(vdoth), dtype=np.float32),
                light_strength=direct_strength,
                ao=ao,
            )
            fill = albedo * (0.045 + roughness[:, :, None] * 0.03) * diffuse_weight * (0.48 + 0.52 * ao[:, :, None])
            direct_clamp = float(ray_gi_detail.get("direct_radiance_clamp", 0.0) or 0.0)
            indirect_clamp = float(ray_gi_detail.get("indirect_radiance_clamp", 0.0) or 0.0)
            if bool(ray_gi_detail.get("enabled")) and direct_clamp > 0.0:
                direct = np.minimum(direct, direct_clamp)
                diagnostics["pbr_ray_gi_direct_clamp_applied"] = True
            indirect = diffuse + specular_env + fill
            if bool(ray_gi_detail.get("enabled")) and indirect_clamp > 0.0:
                indirect = np.minimum(indirect, indirect_clamp)
                diagnostics["pbr_ray_gi_indirect_clamp_applied"] = True
            rgb = indirect + direct + emissive
            rgb = apply_hybrid_gi(
                rgb,
                albedo=albedo,
                diffuse_env=diffuse_env,
                spec_env=spec_env_rgb,
                diffuse_weight=diffuse_weight,
                fresnel=fresnel,
                roughness=roughness,
                metallic=metallic,
                ao=ao,
                settings=hybrid_rendering,
            )
            if bool(hybrid_rendering.get("enabled")):
                active_pixels = int((alpha > 0.001).sum())
                diagnostics["pbr_hybrid_accumulated_pixels"] = int(
                    diagnostics.get("pbr_hybrid_accumulated_pixels", 0) or 0
                ) + active_pixels
                diagnostics["pbr_diffuse_gi"] = float(hybrid_rendering["diffuse_gi_strength"]) > 0.0
                diagnostics["pbr_specular_gi"] = float(hybrid_rendering["specular_gi_strength"]) > 0.0
            rgb = apply_subsurface_scattering(
                rgb,
                albedo,
                normal=(nx, ny, nz),
                light_dir=(float(light[0]), float(light[1]), float(light[2])),
                view_dir=(float(view[0]), float(view[1]), float(view[2])),
                ndotl=lambert,
                ao=ao,
                direct_strength=direct_strength,
                env_rgb=diffuse_env,
                settings=subsurface_rendering,
            )
            if bool(subsurface_rendering.get("enabled")):
                diagnostics["pbr_subsurface_applied"] = True
                diagnostics["pbr_subsurface_pixels"] = int(
                    diagnostics.get("pbr_subsurface_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            rgb = apply_hair_groom_shading(
                rgb,
                normal=(nx, ny, nz),
                tangent=(tx, ty, tz),
                light_dir=(float(light[0]), float(light[1]), float(light[2])),
                view_dir=(float(view[0]), float(view[1]), float(view[2])),
                ndotl=lambert,
                ndotv=ndotv,
                ndoth=hdotn,
                roughness=roughness,
                ao=ao,
                direct_strength=direct_strength,
                env_rgb=spec_env_rgb,
                settings=hair_groom_rendering,
            )
            if bool(hair_groom_rendering.get("enabled")):
                diagnostics["pbr_hair_groom_applied"] = True
                diagnostics["pbr_hair_groom_pixels"] = int(
                    diagnostics.get("pbr_hair_groom_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            rgb = apply_cloth_sheen_shading(
                rgb,
                albedo,
                normal=(nx, ny, nz),
                light_dir=(float(light[0]), float(light[1]), float(light[2])),
                view_dir=(float(view[0]), float(view[1]), float(view[2])),
                ndotl=lambert,
                ndotv=ndotv,
                ndoth=hdotn,
                roughness=roughness,
                ao=ao,
                direct_strength=direct_strength,
                env_rgb=spec_env_rgb,
                settings=cloth_sheen_rendering,
            )
            if bool(cloth_sheen_rendering.get("enabled")):
                diagnostics["pbr_cloth_sheen_applied"] = True
                diagnostics["pbr_cloth_sheen_pixels"] = int(
                    diagnostics.get("pbr_cloth_sheen_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            rgb = apply_glint_sparkle_shading(
                rgb,
                uv=(u, v),
                world_pos=(world_x, world_y, world_z),
                ndotl=lambert,
                ndotv=ndotv,
                ndoth=hdotn,
                roughness=roughness,
                ao=ao,
                direct_strength=direct_strength,
                env_rgb=spec_env_rgb,
                settings=glint_sparkle_rendering,
            )
            if bool(glint_sparkle_rendering.get("enabled")):
                diagnostics["pbr_glint_sparkle_applied"] = True
                diagnostics["pbr_glint_sparkle_pixels"] = int(
                    diagnostics.get("pbr_glint_sparkle_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            rgb = apply_clearcoat_layer(
                rgb,
                spec_env=spec_env_rgb,
                ndotv=ndotv,
                ndotl=lambert,
                ndoth=hdotn,
                vdoth=np.full_like(roughness, float(vdoth), dtype=np.float32),
                roughness=roughness,
                metallic=metallic,
                ao=ao,
                direct_strength=direct_strength,
                settings=clearcoat_rendering,
            )
            if bool(clearcoat_rendering.get("enabled")):
                diagnostics["pbr_clearcoat_applied"] = True
                diagnostics["pbr_clearcoat_pixels"] = int(
                    diagnostics.get("pbr_clearcoat_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            rgb, anisotropic_diag = apply_anisotropic_material_polish(
                rgb,
                uv=(u, v),
                world_pos=(world_x, world_y, world_z),
                normal=(nx, ny, nz),
                tangent=(tx, ty, tz),
                bitangent=(bx, by, bz),
                light_dir=(float(light[0]), float(light[1]), float(light[2])),
                view_dir=(float(view[0]), float(view[1]), float(view[2])),
                ndotl=lambert,
                ndotv=ndotv,
                roughness=roughness,
                metallic=metallic,
                ao=ao,
                direct_strength=direct_strength,
                env_rgb=spec_env_rgb,
                clearcoat=clearcoat_rendering,
                settings=anisotropic_rendering,
            )
            if bool(anisotropic_diag.get("applied")):
                diagnostics["pbr_anisotropic_rendering"] = dict(
                    anisotropic_diag.get("rendering") or anisotropic_rendering
                )
                diagnostics["pbr_anisotropic_applied"] = True
                diagnostics["pbr_anisotropic_pixels"] = int(
                    diagnostics.get("pbr_anisotropic_pixels", 0) or 0
                ) + int(anisotropic_diag.get("changed_pixels", 0) or 0)
                diagnostics["pbr_anisotropic_max_intensity"] = max(
                    float(diagnostics.get("pbr_anisotropic_max_intensity", 0.0) or 0.0),
                    float(anisotropic_diag.get("max_intensity", 0.0) or 0.0),
                )
            rgb, caustics_diag = apply_caustic_highlights(
                rgb,
                uv=(u, v),
                world_pos=(world_x, world_y, world_z),
                ndotl=lambert,
                ndotv=ndotv,
                roughness=roughness,
                alpha=alpha,
                transmission=transmission_rendering,
                settings=caustics_rendering,
            )
            if bool(caustics_diag.get("applied")):
                diagnostics["pbr_caustics_rendering"] = dict(caustics_diag.get("rendering") or caustics_rendering)
                diagnostics["pbr_caustics_applied"] = True
                diagnostics["pbr_caustics_pixels"] = int(
                    diagnostics.get("pbr_caustics_pixels", 0) or 0
                ) + int(caustics_diag.get("changed_pixels", 0) or 0)
                diagnostics["pbr_caustics_max_intensity"] = max(
                    float(diagnostics.get("pbr_caustics_max_intensity", 0.0) or 0.0),
                    float(caustics_diag.get("max_intensity", 0.0) or 0.0),
                )
            rgb = apply_display_transform(rgb, color_management)
            denoise_settings = dict(hybrid_rendering)
            if bool(ray_gi_detail.get("enabled")):
                denoise_settings.update({
                    "denoise_channels": list(ray_gi_detail.get("denoise_channels") or ["beauty"]),
                    "denoise_beauty": bool(ray_gi_detail.get("denoise_beauty")),
                })
                diagnostics["pbr_ray_gi_denoise_channels"] = list(ray_gi_detail.get("denoise_channels") or [])
            rgb = denoise_float_rgb(rgb, alpha, denoise_settings)
            if bool(hybrid_rendering.get("enabled")) and float(hybrid_rendering.get("denoise_strength", 0.0) or 0.0) > 0.0:
                if bool(denoise_settings.get("denoise_beauty", True)):
                    diagnostics["pbr_denoise_applied"] = True
                    diagnostics["pbr_denoise_pixels"] = int(
                        diagnostics.get("pbr_denoise_pixels", 0) or 0
                    ) + int((alpha > 0.001).sum())
                else:
                    diagnostics["pbr_denoise_skipped_by_channel"] = True
            dst = np.asarray(image.crop((box_x0, box_y0, box_x1, box_y1)).convert("RGBA"), dtype=np.float32) / 255.0
            rgb = apply_screen_space_refraction(
                rgb,
                alpha=alpha,
                background_rgba=dst,
                normal_xy=(nx, ny),
                roughness=roughness,
                settings=transmission_rendering,
            )
            if bool(transmission_rendering.get("enabled")):
                diagnostics["pbr_refraction_applied"] = True
                diagnostics["pbr_transmission"] = True
                diagnostics["pbr_refraction_pixels"] = int(
                    diagnostics.get("pbr_refraction_pixels", 0) or 0
                ) + int((alpha > 0.001).sum())
            if depth_patch_for_effect is not None and bool(depth_edge_glow.get("enabled")):
                rgb, glow_diag = apply_depth_edge_glow_to_rgb(
                    rgb,
                    alpha,
                    depth_patch_for_effect,
                    object_depth=object_depth,
                    settings={**dict(lighting), **dict(settings_map)},
                )
                diagnostics["pbr_depth_edge_glow"] = dict(glow_diag.get("rendering") or depth_edge_glow)
                if bool(glow_diag.get("applied")):
                    diagnostics["pbr_depth_edge_glow_applied"] = True
                    diagnostics["pbr_depth_edge_glow_pixels"] = int(
                        diagnostics.get("pbr_depth_edge_glow_pixels", 0) or 0
                    ) + int(glow_diag.get("changed_pixels", 0) or 0)
            rgb = np.clip(rgb, 0.0, 1.0)
            diagnostics["pbr_brdf_model"] = "scene_linear_ggx_cook_torrance_schlick_smith"
            diagnostics["pbr_display_transform"] = str(color_management["tone_mapping"])

            src_a = alpha[:, :, None]
            dst_a = dst[:, :, 3:4]
            out_a = src_a + dst_a * (1.0 - src_a)
            out_rgb = np.where(
                out_a > 1.0e-6,
                (rgb * src_a + dst[:, :, :3] * dst_a * (1.0 - src_a)) / np.maximum(out_a, 1.0e-6),
                0.0,
            )
            out = np.concatenate([out_rgb, out_a], axis=2)
            out = np.clip(out * 255.0, 0, 255).astype(np.uint8)
            image.paste(Image.fromarray(out, "RGBA"), (box_x0, box_y0))
            drawn += 1
    return drawn


def _packet_ssaa_scale(settings: Mapping[str, Any] | None) -> int:
    raw = None
    if isinstance(settings, Mapping):
        raw = settings.get("packet_ssaa")
    if raw is None:
        raw = os.environ.get("TIGERCAPTURE_AR_PBR_PACKET_SSAA", "2")
    try:
        value = int(float(raw))
    except Exception:
        value = 2
    return max(1, min(3, value))


def _draw_packet_triangles(image: Any, vertices: Any, diagnostics: dict[str, Any]) -> int:
    if not isinstance(vertices, (list, tuple)) or len(vertices) < 18:
        return 0
    from PIL import Image, ImageDraw

    width, height = image.size
    drawn = 0
    usable = (len(vertices) // 18) * 18
    for idx in range(0, usable, 18):
        try:
            row = [float(value) for value in vertices[idx:idx + 18]]
            points = [
                _ndc_to_pixel(row[0], row[1], width, height),
                _ndc_to_pixel(row[6], row[7], width, height),
                _ndc_to_pixel(row[12], row[13], width, height),
            ]
            color = _rgba_from_triangle(row)
            if color[3] <= 0:
                continue
            layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
            ImageDraw.Draw(layer, "RGBA").polygon(points, fill=color)
            image.alpha_composite(layer)
            drawn += 1
        except Exception as exc:
            diagnostics.setdefault("warnings", []).append(
                f"packet triangle skipped: {type(exc).__name__}: {exc}"
            )
    return drawn


def rasterize_gpu_preview_items(
    base_frame: Any,
    items: list[dict[str, Any]],
    *,
    settings: Mapping[str, Any] | None = None,
    depth_frame: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """Composite AR/PBR GPU-preview packets over ``base_frame``."""
    diagnostics: dict[str, Any] = {
        "ok": True,
        "mode": "gpu_packet_export",
        "fallback": False,
        "item_count": len(items),
        "ssaa_scale": _packet_ssaa_scale(settings),
        "shadow_triangle_count": 0,
        "reflection_triangle_count": 0,
        "mesh_triangle_count": 0,
        "texture_triangle_count": 0,
        "texture_sampled_triangle_count": 0,
        "pbr_triangle_count": 0,
        "pbr_sampled_triangle_count": 0,
        "pbr_texture_map_count": 0,
        "pbr_depth_occlusion_applied": False,
        "pbr_depth_occluded_pixels": 0,
        "pbr_depth_edge_glow": {},
        "pbr_depth_edge_glow_applied": False,
        "pbr_depth_edge_glow_pixels": 0,
        "pbr_live_depth_texture_item_count": 0,
        "pbr_occlusion_map_applied": False,
        "pbr_occlusion_map_pixels": 0,
        "pbr_opacity_map_applied": False,
        "pbr_opacity_map_pixels": 0,
        "pbr_alpha_cutoff_pixels": 0,
        "pbr_emissive_map_applied": False,
        "pbr_emissive_map_pixels": 0,
        "pbr_hdri_directional_sampling": False,
        "pbr_hdri_sampled_pixels": 0,
        "pbr_irradiance_ibl": False,
        "pbr_prefiltered_ibl": False,
        "pbr_prefiltered_ibl_pixels": 0,
        "pbr_prefiltered_ibl_level_count": 0,
        "pbr_brdf_lut": False,
        "pbr_brdf_lut_sampled_pixels": 0,
        "pbr_brdf_model": "",
        "pbr_ibl_probe": {},
        "pbr_color_management": {},
        "pbr_display_transform": "",
        "pbr_hybrid_rendering": {},
        "pbr_hybrid_accumulated_pixels": 0,
        "pbr_diffuse_gi": False,
        "pbr_specular_gi": False,
        "pbr_ray_gi_detail": {},
        "pbr_ray_gi_direct_clamp_applied": False,
        "pbr_ray_gi_indirect_clamp_applied": False,
        "pbr_ray_gi_denoise_channels": [],
        "pbr_denoise_skipped_by_channel": False,
        "pbr_denoise_applied": False,
        "pbr_denoise_pixels": 0,
        "pbr_ambient_occlusion_rendering": {},
        "pbr_ambient_occlusion_applied": False,
        "pbr_ambient_occlusion_pixels": 0,
        "pbr_ambient_occlusion_changed_pixels": 0,
        "pbr_ambient_occlusion_pass": {},
        "pbr_transmission_rendering": {},
        "pbr_transmission": False,
        "pbr_refraction_applied": False,
        "pbr_refraction_pixels": 0,
        "pbr_clearcoat_rendering": {},
        "pbr_clearcoat_applied": False,
        "pbr_clearcoat_pixels": 0,
        "pbr_parallax_rendering": {},
        "pbr_parallax_applied": False,
        "pbr_parallax_pixels": 0,
        "pbr_displacement_rendering": {},
        "pbr_displacement_applied": False,
        "pbr_displacement_pixels": 0,
        "pbr_displacement_height_pixels": 0,
        "pbr_displacement_vector_pixels": 0,
        "pbr_displacement_max_offset": 0.0,
        "pbr_displacement_mean_offset": 0.0,
        "pbr_displacement_parallax_fallback": False,
        "pbr_bevel_rendering": {},
        "pbr_bevel_applied": False,
        "pbr_bevel_pixels": 0,
        "pbr_material_layering": {},
        "pbr_material_layer_applied": False,
        "pbr_material_layer_pixels": 0,
        "pbr_surface_rendering": {},
        "pbr_surface_applied": False,
        "pbr_surface_pixels": 0,
        "pbr_subsurface_rendering": {},
        "pbr_subsurface_applied": False,
        "pbr_subsurface_pixels": 0,
        "pbr_hair_groom_rendering": {},
        "pbr_hair_groom_applied": False,
        "pbr_hair_groom_pixels": 0,
        "pbr_cloth_sheen_rendering": {},
        "pbr_cloth_sheen_applied": False,
        "pbr_cloth_sheen_pixels": 0,
        "pbr_glint_sparkle_rendering": {},
        "pbr_glint_sparkle_applied": False,
        "pbr_glint_sparkle_pixels": 0,
        "pbr_caustics_rendering": {},
        "pbr_caustics_applied": False,
        "pbr_caustics_pixels": 0,
        "pbr_caustics_max_intensity": 0.0,
        "pbr_anisotropic_rendering": {},
        "pbr_anisotropic_applied": False,
        "pbr_anisotropic_pixels": 0,
        "pbr_anisotropic_max_intensity": 0.0,
        "pbr_microsurface_rendering": {},
        "pbr_detail_normal_applied": False,
        "pbr_detail_normal_pixels": 0,
        "pbr_detail_normal_max_delta": 0.0,
        "pbr_micro_roughness_applied": False,
        "pbr_micro_roughness_pixels": 0,
        "pbr_micro_roughness_mean": 0.0,
        "pbr_micro_roughness_max_delta": 0.0,
        "pbr_depth_of_field_rendering": {},
        "pbr_depth_of_field_applied": False,
        "pbr_depth_of_field_pixels": 0,
        "pbr_depth_of_field_max_coc_px": 0.0,
        "pbr_post_effects_rendering": {},
        "pbr_post_effects_applied": False,
        "pbr_post_effects_pixels": 0,
        "pbr_bloom_applied": False,
        "pbr_vignette_applied": False,
        "pbr_grain_applied": False,
        "pbr_sharpen_applied": False,
        "pbr_lens_effects_rendering": {},
        "pbr_lens_effects_applied": False,
        "pbr_lens_effects_pixels": 0,
        "pbr_lens_distortion_applied": False,
        "pbr_chromatic_aberration_applied": False,
        "pbr_chromatic_aberration_max_offset_px": 0.0,
        "pbr_lens_flare_rendering": {},
        "pbr_lens_flare_applied": False,
        "pbr_lens_flare_pixels": 0,
        "pbr_flare_applied": False,
        "pbr_aperture_flare_applied": False,
        "pbr_lens_dirt_applied": False,
        "pbr_lens_scratch_applied": False,
        "pbr_lens_flare_ghost_count": 0,
        "pbr_lens_flare_bright_pixels": 0,
        "pbr_render_passes": {},
        "pbr_render_pass_count": 0,
        "pbr_render_pass_output_dir": "",
        "pbr_motion_blur_rendering": {},
        "pbr_motion_blur_applied": False,
        "pbr_motion_blur_pixels": 0,
        "pbr_motion_blur_changed_pixels": 0,
        "pbr_motion_blur_sample_count": 1,
        "pbr_motion_blur_sample_times_ms": [],
        "pbr_udim_rendering": {},
        "pbr_udim_sampled_pixels": 0,
        "pbr_udim_sampled_tiles": [],
        "pbr_udim_sampled_tile_count": 0,
        "pbr_udim_missing_tile_pixels": 0,
        "pbr_triplanar_rendering": {},
        "pbr_triplanar_applied": False,
        "pbr_triplanar_pixels": 0,
        "catcher": {},
        "warnings": [],
        "errors": [],
    }
    image, kind, error = _frame_to_pil_rgba(base_frame)
    if image is None:
        diagnostics["ok"] = False
        diagnostics["fallback"] = True
        diagnostics["errors"].append(error or "unsupported frame")
        return base_frame, diagnostics
    if not items:
        diagnostics["fallback"] = True
        diagnostics["warnings"].append("no ar_pbr gpu-preview items")
        return base_frame, diagnostics

    from PIL import Image

    original_size = image.size
    ssaa_scale = int(diagnostics["ssaa_scale"])
    overlay = Image.new(
        "RGBA",
        (original_size[0] * ssaa_scale, original_size[1] * ssaa_scale),
        (0, 0, 0, 0),
    )
    depth = _depth_array(depth_frame, overlay.size[0], overlay.size[1])
    dof_settings: dict[str, Any] | None = None
    dof_depth = None
    ao_settings: dict[str, Any] | None = None
    post_settings: dict[str, Any] | None = None
    lens_settings: dict[str, Any] | None = None
    lens_flare_settings: dict[str, Any] | None = None
    settings_map = settings or {}
    render_pass_disabled = bool(settings_map.get("disable_render_pass_export"))
    settings_passes = normalize_render_pass_settings({} if render_pass_disabled else settings_map)
    render_pass_settings: dict[str, Any] | None = dict(settings_passes) if bool(settings_passes.get("enabled")) else None

    for key, counter in (
        ("shadow_vertices", "shadow_triangle_count"),
        ("reflection_vertices", "reflection_triangle_count"),
        ("vertices", "mesh_triangle_count"),
    ):
        for item in items:
            diagnostics[counter] += _draw_packet_triangles(
                overlay,
                item.get(key) if isinstance(item, dict) else None,
                diagnostics,
            )
    for item in items:
        if not isinstance(item, dict):
            continue
        if not diagnostics["catcher"] and isinstance(item.get("catcher"), Mapping):
            diagnostics["catcher"] = dict(item.get("catcher") or {})
        texture_triangles = item.get("texture_triangles")
        if isinstance(texture_triangles, (list, tuple)):
            diagnostics["texture_triangle_count"] += len(texture_triangles)
            diagnostics["texture_sampled_triangle_count"] += _draw_textured_triangles(
                overlay,
                texture_triangles,
                diagnostics,
            )
        pbr_triangles = item.get("pbr_triangles")
        if isinstance(pbr_triangles, (list, tuple)):
            diagnostics["pbr_triangle_count"] += len(pbr_triangles)
            pbr_map_count = 0
            for tri in pbr_triangles:
                if isinstance(tri, Mapping) and isinstance(tri.get("maps"), Mapping):
                    maps = tri.get("maps") or {}
                    pbr_map_count += len([
                        key
                        for key in ("base", "roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity", "height")
                        if maps.get(key)
                    ])
            diagnostics["pbr_texture_map_count"] += pbr_map_count
            item_depth = depth
            if item_depth is None:
                item_depth = _depth_array(item.get("depth_texture"), overlay.size[0], overlay.size[1])
                if item_depth is not None:
                    diagnostics["pbr_live_depth_texture_item_count"] = int(
                        diagnostics.get("pbr_live_depth_texture_item_count", 0) or 0
                    ) + 1
            lighting = item.get("pbr_lighting") if isinstance(item.get("pbr_lighting"), Mapping) else {}
            item_ao = normalize_packet_ambient_occlusion_settings(item, lighting)
            item_dof = normalize_depth_of_field_settings(lighting)
            item_post = normalize_post_effects_settings(lighting)
            item_lens = normalize_lens_effects_settings(lighting)
            item_lens_flare = normalize_lens_flare_settings(lighting)
            item_passes = normalize_render_pass_settings(lighting)
            if bool(item_ao.get("enabled")) and ao_settings is None:
                ao_settings = dict(item_ao)
                diagnostics["pbr_ambient_occlusion_rendering"] = dict(item_ao)
            if bool(item_post.get("enabled")) and post_settings is None:
                post_settings = dict(item_post)
                diagnostics["pbr_post_effects_rendering"] = dict(item_post)
            if bool(item_lens.get("enabled")) and lens_settings is None:
                lens_settings = dict(item_lens)
                diagnostics["pbr_lens_effects_rendering"] = dict(item_lens)
            if bool(item_lens_flare.get("enabled")) and lens_flare_settings is None:
                lens_flare_settings = dict(item_lens_flare)
                diagnostics["pbr_lens_flare_rendering"] = dict(item_lens_flare)
            if bool(item_passes.get("enabled")) and not render_pass_disabled:
                merged_passes = dict(item_passes)
                if str(settings_passes.get("output_dir") or ""):
                    merged_passes["output_dir"] = str(settings_passes.get("output_dir") or "")
                if not render_pass_settings or not bool(render_pass_settings.get("enabled")):
                    render_pass_settings = merged_passes
                elif not str(render_pass_settings.get("output_dir") or "") and str(merged_passes.get("output_dir") or ""):
                    render_pass_settings["output_dir"] = str(merged_passes.get("output_dir") or "")
            if bool(item_dof.get("enabled")) and dof_depth is None:
                try:
                    import numpy as np

                    dof_depth = np.full(
                        (overlay.size[1], overlay.size[0]),
                        float(item_dof.get("focus_depth", 0.5) or 0.5),
                        dtype=np.float32,
                    )
                    dof_settings = dict(item_dof)
                    diagnostics["pbr_depth_of_field_rendering"] = dict(item_dof)
                except Exception as exc:
                    diagnostics.setdefault("warnings", []).append(
                        f"depth of field depth buffer skipped: {type(exc).__name__}: {exc}"
                    )
            diagnostics["pbr_sampled_triangle_count"] += _draw_pbr_triangles(
                overlay,
                pbr_triangles,
                lighting,
                diagnostics,
                depth=item_depth,
                dof_depth=dof_depth,
                settings=settings,
                occlusion_enabled=bool(item.get("occlusion_enabled")),
            )
    if ssaa_scale > 1:
        overlay = overlay.resize(original_size, Image.Resampling.LANCZOS)
    if ao_settings is not None:
        overlay, ao_diag = apply_screen_ambient_occlusion_to_overlay(overlay, ao_settings, dof_depth)
        diagnostics["pbr_ambient_occlusion_rendering"] = dict(ao_diag.get("rendering") or ao_settings)
        diagnostics["pbr_ambient_occlusion_applied"] = bool(ao_diag.get("applied"))
        diagnostics["pbr_ambient_occlusion_pixels"] = int(ao_diag.get("pixels", 0) or 0)
        diagnostics["pbr_ambient_occlusion_changed_pixels"] = int(ao_diag.get("changed_pixels", 0) or 0)
        diagnostics["pbr_ambient_occlusion_pass"] = {
            "min": float(ao_diag.get("pass_min", 1.0) or 1.0),
            "mean": float(ao_diag.get("pass_mean", 1.0) or 1.0),
            "max": float(ao_diag.get("pass_max", 1.0) or 1.0),
        }
        if ao_diag.get("warnings"):
            diagnostics.setdefault("warnings", []).extend(list(ao_diag.get("warnings") or []))
    if dof_settings is not None and dof_depth is not None:
        overlay, dof_diag = apply_depth_of_field_to_overlay(overlay, dof_depth, dof_settings)
        diagnostics["pbr_depth_of_field_rendering"] = dict(dof_diag.get("rendering") or dof_settings)
        diagnostics["pbr_depth_of_field_applied"] = bool(dof_diag.get("applied"))
        diagnostics["pbr_depth_of_field_pixels"] = int(dof_diag.get("pixels", 0) or 0)
        diagnostics["pbr_depth_of_field_max_coc_px"] = float(dof_diag.get("max_circle_of_confusion_px", 0.0) or 0.0)
        if dof_diag.get("warnings"):
            diagnostics.setdefault("warnings", []).extend(list(dof_diag.get("warnings") or []))
    image.alpha_composite(overlay)
    if post_settings is not None:
        image, post_diag = apply_post_effects_to_image(image, post_settings)
        diagnostics["pbr_post_effects_rendering"] = dict(post_diag.get("rendering") or post_settings)
        diagnostics["pbr_post_effects_applied"] = bool(post_diag.get("applied"))
        diagnostics["pbr_post_effects_pixels"] = int(post_diag.get("changed_pixels", 0) or 0)
        diagnostics["pbr_bloom_applied"] = bool(post_diag.get("bloom_applied"))
        diagnostics["pbr_vignette_applied"] = bool(post_diag.get("vignette_applied"))
        diagnostics["pbr_grain_applied"] = bool(post_diag.get("grain_applied"))
        diagnostics["pbr_sharpen_applied"] = bool(post_diag.get("sharpen_applied"))
        if post_diag.get("warnings"):
            diagnostics.setdefault("warnings", []).extend(list(post_diag.get("warnings") or []))
    if lens_settings is not None:
        image, lens_diag = apply_lens_effects_to_image(image, lens_settings)
        diagnostics["pbr_lens_effects_rendering"] = dict(lens_diag.get("rendering") or lens_settings)
        diagnostics["pbr_lens_effects_applied"] = bool(lens_diag.get("applied"))
        diagnostics["pbr_lens_effects_pixels"] = int(lens_diag.get("changed_pixels", 0) or 0)
        diagnostics["pbr_lens_distortion_applied"] = bool(lens_diag.get("distortion_applied"))
        diagnostics["pbr_chromatic_aberration_applied"] = bool(lens_diag.get("chromatic_aberration_applied"))
        diagnostics["pbr_chromatic_aberration_max_offset_px"] = float(
            lens_diag.get("max_channel_offset_px", 0.0) or 0.0
        )
        if lens_diag.get("warnings"):
            diagnostics.setdefault("warnings", []).extend(list(lens_diag.get("warnings") or []))
    if lens_flare_settings is not None:
        image, flare_diag = apply_lens_flare_to_image(image, lens_flare_settings)
        diagnostics["pbr_lens_flare_rendering"] = dict(flare_diag.get("rendering") or lens_flare_settings)
        diagnostics["pbr_lens_flare_applied"] = bool(flare_diag.get("applied"))
        diagnostics["pbr_lens_flare_pixels"] = int(flare_diag.get("changed_pixels", 0) or 0)
        diagnostics["pbr_flare_applied"] = bool(flare_diag.get("flare_applied"))
        diagnostics["pbr_aperture_flare_applied"] = bool(flare_diag.get("aperture_flare_applied"))
        diagnostics["pbr_lens_dirt_applied"] = bool(flare_diag.get("dirt_applied"))
        diagnostics["pbr_lens_scratch_applied"] = bool(flare_diag.get("scratch_applied"))
        diagnostics["pbr_lens_flare_ghost_count"] = int(flare_diag.get("ghost_count", 0) or 0)
        diagnostics["pbr_lens_flare_bright_pixels"] = int(flare_diag.get("bright_source_pixels", 0) or 0)
        if flare_diag.get("warnings"):
            diagnostics.setdefault("warnings", []).extend(list(flare_diag.get("warnings") or []))
    if render_pass_settings is not None and bool(render_pass_settings.get("enabled")):
        try:
            _pass_images, pass_diag = render_packet_render_passes(
                beauty=image,
                items=items,
                settings=render_pass_settings,
                base_frame=base_frame,
                depth_frame=depth_frame,
                diagnostics=diagnostics,
            )
            diagnostics["pbr_render_passes"] = pass_diag
            diagnostics["pbr_render_pass_count"] = int(pass_diag.get("pass_count", 0) or 0)
            diagnostics["pbr_render_pass_output_dir"] = str(pass_diag.get("output_dir") or "")
            if pass_diag.get("warnings"):
                diagnostics.setdefault("warnings", []).extend(list(pass_diag.get("warnings") or []))
        except Exception as exc:
            diagnostics.setdefault("warnings", []).append(
                f"render pass export skipped: {type(exc).__name__}: {exc}"
            )
    return _pil_to_original_kind(image, kind, base_frame), diagnostics


def _track_lighting_settings(track: Mapping[str, Any]) -> Mapping[str, Any]:
    render = track.get("render") if isinstance(track.get("render"), Mapping) else {}
    lighting = render.get("lighting") if isinstance(render.get("lighting"), Mapping) else {}
    return lighting


def _motion_blur_settings_for_tracks(
    settings: Mapping[str, Any] | None,
    tracks: list[dict[str, Any]],
) -> dict[str, Any]:
    settings_map = settings or {}
    if bool(settings_map.get("_disable_motion_blur")):
        return normalize_motion_blur_settings({})
    global_motion = normalize_motion_blur_settings(settings_map)
    if bool(global_motion.get("enabled")):
        return global_motion
    for track in tracks or []:
        if not isinstance(track, Mapping):
            continue
        row = merge_motion_blur_settings(settings_map, _track_lighting_settings(track))
        if bool(row.get("enabled")):
            return row
    return global_motion


def _render_pass_settings_for_tracks(
    settings: Mapping[str, Any] | None,
    tracks: list[dict[str, Any]],
) -> dict[str, Any]:
    settings_map = settings or {}
    if bool(settings_map.get("disable_render_pass_export")):
        return normalize_render_pass_settings({})
    global_passes = normalize_render_pass_settings(settings_map)
    if bool(global_passes.get("enabled")):
        return global_passes
    for track in tracks or []:
        if not isinstance(track, Mapping):
            continue
        row = normalize_render_pass_settings(_track_lighting_settings(track))
        if bool(row.get("enabled")):
            merged = dict(row)
            if str(settings_map.get("render_pass_output_dir") or ""):
                merged["output_dir"] = str(settings_map.get("render_pass_output_dir") or "")
            return merged
    return global_passes


def _render_gpu_packet_export_frame_single(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any], list[dict[str, Any]]]:
    """Build preview-equivalent AR/PBR packets and rasterize them for export."""
    try:
        from app.ar_pbr.gpu_preview import build_gpu_preview_items

        image, _kind, error = _frame_to_pil_rgba(base_frame)
        if image is None:
            return base_frame, {
                "ok": False,
                "mode": "gpu_packet_export",
                "fallback": True,
                "warnings": [],
                "errors": [error or "unsupported frame"],
            }, []
        width, height = image.size
        items, packet_diag = build_gpu_preview_items(
            frame_size=(width, height),
            time_ms=int(time_ms),
            ar_tracks=list(ar_tracks or []),
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings=dict(settings or {}),
        )
        out, draw_diag = rasterize_gpu_preview_items(
            base_frame,
            items,
            settings=settings,
            depth_frame=depth_frame,
        )
        draw_diag["packet_builder"] = packet_diag
        draw_diag["rendered_track_count"] = int(packet_diag.get("rendered_track_count", 0) or 0)
        draw_diag["triangle_count"] = int(packet_diag.get("triangle_count", 0) or 0)
        draw_diag["visible_triangle_count"] = int(packet_diag.get("visible_triangle_count", 0) or 0)
        draw_diag["occluded_triangle_count"] = int(packet_diag.get("occluded_triangle_count", 0) or 0)
        draw_diag["texture_map_status_counts"] = dict(packet_diag.get("texture_map_status_counts") or {})
        draw_diag["texture_map_count"] = int(packet_diag.get("texture_map_count", 0) or 0)
        draw_diag["texture_material_count"] = int(packet_diag.get("texture_material_count", 0) or 0)
        draw_diag["texture_missing_count"] = int(packet_diag.get("texture_missing_count", 0) or 0)
        draw_diag["texture_tinted_triangle_count"] = int(packet_diag.get("texture_tinted_triangle_count", 0) or 0)
        draw_diag["packet_pbr_triangle_count"] = int(packet_diag.get("pbr_triangle_count", 0) or 0)
        if int(draw_diag.get("pbr_sampled_triangle_count", 0) or 0) > 0:
            draw_diag["renderer_quality"] = "preview_packet_pbr_material_maps"
        elif int(draw_diag.get("texture_sampled_triangle_count", 0) or 0) > 0:
            draw_diag["renderer_quality"] = "preview_packet_affine_texture"
        else:
            draw_diag["renderer_quality"] = "preview_packet_color"
        if not packet_diag.get("ok", True):
            draw_diag["ok"] = False
        if packet_diag.get("warnings"):
            draw_diag.setdefault("warnings", []).extend(packet_diag.get("warnings", []) or [])
        if packet_diag.get("errors"):
            draw_diag.setdefault("errors", []).extend(packet_diag.get("errors", []) or [])
        return out, draw_diag, items
    except Exception as exc:
        return base_frame, {
            "ok": False,
            "mode": "gpu_packet_export",
            "fallback": True,
            "warnings": [],
            "errors": [f"{type(exc).__name__}: {exc}"],
        }, []


def _render_gpu_packet_export_frame_motion_blur(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
    motion_blur: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    try:
        import numpy as np
        from PIL import Image
    except Exception:
        out, diag, _items = _render_gpu_packet_export_frame_single(
            base_frame,
            time_ms=time_ms,
            ar_tracks=ar_tracks,
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings=settings,
        )
        return out, diag

    base_image, kind, error = _frame_to_pil_rgba(base_frame)
    if base_image is None:
        return base_frame, {
            "ok": False,
            "mode": "gpu_packet_export",
            "fallback": True,
            "warnings": [],
            "errors": [error or "unsupported frame"],
        }

    cfg = normalize_motion_blur_settings(motion_blur)
    offsets = motion_blur_sample_offsets_ms(cfg)
    sample_settings = dict(settings or {})
    sample_settings["_disable_motion_blur"] = True
    sample_settings["disable_render_pass_export"] = True
    frames = []
    sample_times: list[int] = []
    sample_diags: list[dict[str, Any]] = []
    center_diag: dict[str, Any] = {}
    center_items: list[dict[str, Any]] = []
    center_distance = float("inf")
    for offset in offsets:
        sample_time = int(round(float(time_ms) + float(offset)))
        sample_camera = camera_solution_for_motion_sample(camera_solution, cfg, float(offset))
        sample_out, sample_diag, sample_items = _render_gpu_packet_export_frame_single(
            base_frame,
            time_ms=sample_time,
            ar_tracks=ar_tracks,
            camera_solution=sample_camera,
            depth_frame=depth_frame,
            settings=sample_settings,
        )
        sample_img, _sample_kind, _sample_error = _frame_to_pil_rgba(sample_out)
        if sample_img is None:
            continue
        if sample_img.size != base_image.size:
            sample_img = sample_img.resize(base_image.size, Image.Resampling.BILINEAR)
        frames.append(np.asarray(sample_img.convert("RGBA"), dtype=np.float32))
        sample_times.append(sample_time)
        sample_diags.append({
            "time_ms": sample_time,
            "offset_ms": float(offset),
            "rendered_track_count": int(sample_diag.get("rendered_track_count", 0) or 0),
            "pbr_sampled_triangle_count": int(sample_diag.get("pbr_sampled_triangle_count", 0) or 0),
            "ok": bool(sample_diag.get("ok", True)),
        })
        distance = abs(float(offset))
        if distance < center_distance:
            center_distance = distance
            center_diag = dict(sample_diag or {})
            center_items = list(sample_items or [])
    if not frames:
        out, diag, _items = _render_gpu_packet_export_frame_single(
            base_frame,
            time_ms=time_ms,
            ar_tracks=ar_tracks,
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings=settings,
        )
        return out, diag

    accum = np.mean(np.stack(frames, axis=0), axis=0)
    blurred = Image.fromarray(np.clip(accum, 0, 255).astype(np.uint8), "RGBA")
    center_frame = frames[min(range(len(frames)), key=lambda idx: abs(sample_times[idx] - int(time_ms)))]
    changed = np.max(np.abs(accum[:, :, :3] - center_frame[:, :, :3]), axis=2) > 1.0
    diag = dict(center_diag or {})
    diag["pbr_motion_blur_rendering"] = dict(cfg)
    diag["pbr_motion_blur_applied"] = bool(len(frames) > 1)
    diag["pbr_motion_blur_pixels"] = int(changed.sum())
    diag["pbr_motion_blur_changed_pixels"] = int(changed.sum())
    diag["pbr_motion_blur_sample_count"] = int(len(frames))
    diag["pbr_motion_blur_sample_times_ms"] = sample_times
    diag["pbr_motion_blur_samples"] = sample_diags
    diag["pbr_motion_blur_shutter_ms"] = float(cfg.get("shutter_ms", 0.0) or 0.0)
    diag["pbr_motion_blur_camera_motion_px"] = list(cfg.get("camera_motion_px") or [0.0, 0.0])
    diag["renderer_quality"] = f"{diag.get('renderer_quality') or 'preview_packet'}_motion_blur"
    diag["mode"] = "gpu_packet_export"
    diag["fallback"] = False

    pass_settings = _render_pass_settings_for_tracks(settings, ar_tracks)
    if bool(pass_settings.get("enabled")):
        try:
            _pass_images, pass_diag = render_packet_render_passes(
                beauty=blurred,
                items=center_items,
                settings=pass_settings,
                base_frame=base_frame,
                depth_frame=depth_frame,
                diagnostics=diag,
            )
            diag["pbr_render_passes"] = pass_diag
            diag["pbr_render_pass_count"] = int(pass_diag.get("pass_count", 0) or 0)
            diag["pbr_render_pass_output_dir"] = str(pass_diag.get("output_dir") or "")
            if pass_diag.get("warnings"):
                diag.setdefault("warnings", []).extend(list(pass_diag.get("warnings") or []))
        except Exception as exc:
            diag.setdefault("warnings", []).append(
                f"motion blur render pass export skipped: {type(exc).__name__}: {exc}"
            )
    return _pil_to_original_kind(blurred, kind, base_frame), diag


def render_gpu_packet_export_frame(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Build preview-equivalent AR/PBR packets and rasterize them for export."""
    motion_blur = _motion_blur_settings_for_tracks(settings, list(ar_tracks or []))
    if bool(motion_blur.get("enabled")):
        return _render_gpu_packet_export_frame_motion_blur(
            base_frame,
            time_ms=time_ms,
            ar_tracks=list(ar_tracks or []),
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings=settings,
            motion_blur=motion_blur,
        )
    out, diag, _items = _render_gpu_packet_export_frame_single(
        base_frame,
        time_ms=time_ms,
        ar_tracks=list(ar_tracks or []),
        camera_solution=camera_solution,
        depth_frame=depth_frame,
        settings=settings,
    )
    return out, diag


def render_offscreen_gpu_export_frame(
    base_frame: Any,
    *,
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Render AR/PBR export through the helper process, with packet fallback.

    The exporter runs in a worker thread, so Qt/OpenGL rendering is delegated to
    a separate process. If that helper is unavailable or fails, export returns to
    the deterministic packet renderer instead of failing normal MP4 output.
    """
    service_diag: dict[str, Any] = {}
    try:
        from app.ar_pbr.full_gpu_export_service import render_frame_via_full_gpu_export_service

        service_out, service_diag = render_frame_via_full_gpu_export_service(
            base_frame,
            time_ms=int(time_ms),
            ar_tracks=list(ar_tracks or []),
            camera_solution=camera_solution,
            depth_frame=depth_frame,
            settings=dict(settings or {}),
        )
        if bool(service_diag.get("ok")) and int(service_diag.get("rendered_track_count", 0) or 0) > 0:
            service_diag = dict(service_diag or {})
            service_diag["requested_renderer"] = "offscreen_gpu"
            service_diag["mode"] = "full_model_view_gpu_export_service"
            service_diag["fallback"] = False
            service_diag["renderer_quality_gap"] = ""
            return service_out, service_diag
    except Exception as exc:
        service_diag = {
            "ok": False,
            "mode": "full_model_view_gpu_export_service",
            "fallback": True,
            "errors": [f"{type(exc).__name__}: {exc}"],
        }

    out, diagnostics = render_gpu_packet_export_frame(
        base_frame,
        time_ms=time_ms,
        ar_tracks=ar_tracks,
        camera_solution=camera_solution,
        depth_frame=depth_frame,
        settings=settings,
    )
    diagnostics = dict(diagnostics or {})
    diagnostics["requested_renderer"] = "offscreen_gpu"
    diagnostics["mode"] = "offscreen_gpu_requested_packet_fallback"
    diagnostics["full_gpu_export_available"] = False
    diagnostics["fallback"] = True
    diagnostics["fallback_reason"] = "full_gpu_export_service_failed_or_unavailable"
    diagnostics["renderer_quality_gap"] = "full_model_view_gpu_export_service_missing"
    diagnostics["full_gpu_export_service_attempt"] = dict(service_diag or {})
    try:
        from app.ar_pbr.full_gpu_export_service import build_full_gpu_export_service_report

        service = build_full_gpu_export_service_report(probe=False)
        diagnostics["full_gpu_export_service"] = {
            "contract_ready": bool(service.get("contract_ready")),
            "service_command_env": str(service.get("service_command_env") or ""),
            "configured": bool(service.get("configured")),
            "available": bool(service.get("available")),
            "blockers": list(service.get("blockers") or []),
        }
    except Exception:
        diagnostics["full_gpu_export_service"] = {
            "contract_ready": False,
            "blockers": ["service_contract_report_failed"],
        }
    diagnostics["next_renderer_steps"] = [
        "run the model-view GPU helper probe+smoke QA on this machine",
        "tune model-view PBR material, IBL, shadow, reflection, and depth parity on real FBX/GLB assets",
        "share texture/HDRI/shadow-map resources with timeline preview and export",
        "keep preview-packet PBR as deterministic fallback diagnostics",
    ]
    diagnostics.setdefault("warnings", []).append(
        "offscreen GPU AR/PBR helper did not complete; used preview-packet PBR fallback"
    )
    return out, diagnostics
