"""Packet-based render pass export for AR/PBR frames."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.pbr_math import linear_to_srgb, srgb_to_linear
from app.ar_pbr.udim import decode_udim_tiles, local_uv_from_udim, udim_tile_id_from_uv


DEFAULT_RENDER_PASS_NAMES: tuple[str, ...] = (
    "beauty",
    "alpha_mask",
    "depth",
    "normal",
    "position",
    "material_id",
    "object_id",
    "ambient_occlusion",
    "direct_lighting",
    "indirect_lighting",
    "diffuse",
    "specular",
    "albedo",
    "emissive",
    "roughness",
    "metallic",
    "transparency",
    "shadow",
    "reflection",
)

RENDER_PASS_SCHEMA = "tigerstudio.ar_pbr.render_passes.v1"
RENDER_PASS_OUTPUT_SCHEMA = "tigerstudio.ar_pbr.render_passes.output.v1"
_TEXTURE_ARRAY_CACHE: dict[str, Any] = {}
_LEGACY_PBR_VERTEX_STRIDE_FLOATS = 20
_PBR_VERTEX_STRIDE_FLOATS = 23


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
    if text in {"1", "true", "yes", "on", "enabled", "export", "passes", "render_passes"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", "none"}:
        return False
    return bool(default)


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    for container_key in (
        "render_pass_export",
        "render_passes",
        "render_passes_rendering",
        "multi_pass",
        "passes",
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


def _normalize_pass_name(value: Any) -> str:
    text = str(value or "").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "alpha": "alpha_mask",
        "mask": "alpha_mask",
        "opacity": "alpha_mask",
        "ao": "ambient_occlusion",
        "ssao": "ambient_occlusion",
        "ambientocclusion": "ambient_occlusion",
        "direct": "direct_lighting",
        "indirect": "indirect_lighting",
        "base_color": "albedo",
        "basecolor": "albedo",
        "diffuse_color": "albedo",
        "metalness": "metallic",
        "metal": "metallic",
        "transmission": "transparency",
        "mat_id": "material_id",
        "materialid": "material_id",
        "objectid": "object_id",
        "obj_id": "object_id",
    }
    return aliases.get(text, text)


def _pass_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part for part in re.split(r"[,;|\s]+", value) if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        raw = []
    out: list[str] = []
    for part in raw:
        name = _normalize_pass_name(part)
        if name in DEFAULT_RENDER_PASS_NAMES and name not in out:
            out.append(name)
    return out


def normalize_render_pass_settings(value: Any) -> dict[str, Any]:
    """Normalize Marmoset-style multi-pass render export controls."""
    direct_names = value if isinstance(value, (list, tuple, set)) else None
    data = _as_mapping(value)
    raw_names = _first_value(
        direct_names,
        _nested(data, "passes", "names", "render_pass_names", "pass_names"),
        data.get("render_pass_names"),
    )
    names = _pass_list(raw_names)
    output_dir = str(_first_value(
        _nested(data, "output_dir", "directory", "path", "render_pass_output_dir"),
        data.get("render_pass_output_dir"),
        "",
    ) or "").strip()
    fmt = str(_first_value(
        _nested(data, "format", "image_format", "render_pass_format"),
        data.get("render_pass_format"),
        "png",
    ) or "png").strip().casefold().lstrip(".")
    if fmt not in {"png"}:
        fmt = "png"
    enabled = _bool_value(
        _first_value(
            _nested(data, "enabled", "render_passes_enabled", "export"),
            data.get("render_passes_enabled"),
            data.get("render_pass_enabled"),
        ),
        bool(names or output_dir),
    )
    if enabled and not names:
        names = list(DEFAULT_RENDER_PASS_NAMES)
    if not enabled:
        names = []
        output_dir = ""
    return {
        "schema": RENDER_PASS_SCHEMA,
        "enabled": bool(enabled),
        "passes": names,
        "output_dir": output_dir,
        "format": fmt,
        "renderer": "packet_export",
        "beauty_policy": "final_composited_beauty_pass",
        "data_policy": "packet_reconstruction_from_preview_geometry",
        "id_policy": "stable_hash_rgb_from_material_and_track_ids",
        "file_policy": "8bit_png_preview_passes",
        "render_pass_safe": True,
    }


def flatten_render_pass_settings(value: Any) -> dict[str, Any]:
    settings = normalize_render_pass_settings(value)
    return {
        "render_passes_enabled": settings["enabled"],
        "render_pass_names": list(settings["passes"] or DEFAULT_RENDER_PASS_NAMES),
        "render_pass_output_dir": settings["output_dir"],
        "render_pass_format": settings["format"],
    }


def _ndc_to_pixel(x: float, y: float, width: int, height: int) -> tuple[float, float]:
    return (
        (float(x) + 1.0) * 0.5 * max(1, width - 1),
        (1.0 - float(y)) * 0.5 * max(1, height - 1),
    )


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


def _texture_array(path: str):
    key = str(path or "")
    if not key:
        return None
    cached = _TEXTURE_ARRAY_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np
        from PIL import Image

        arr = np.asarray(Image.open(key).convert("RGBA"), dtype=np.float32) / 255.0
    except Exception:
        return None
    _TEXTURE_ARRAY_CACHE[key] = arr
    return arr


def _texture_udim_arrays(maps: Mapping[str, Any], key: str) -> dict[int, Any]:
    tiles = decode_udim_tiles(maps.get(f"{key}_udim_tiles") if isinstance(maps, Mapping) else None)
    out: dict[int, Any] = {}
    for tile, path in tiles.items():
        arr = _texture_array(str(path or ""))
        if arr is not None:
            out[int(tile)] = arr
    return out


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


def _sample_texture_udim(tile_arrays: Mapping[int, Any], fallback_arr: Any, u, v):
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
            out = np.zeros_like(sample, dtype=np.float32)
        tile_mask = tile_ids == int(tile)
        if bool(tile_mask.any()):
            out[tile_mask] = sample[tile_mask]
            matched |= tile_mask
    if out is None:
        return _sample_texture_nearest(fallback_arr, u, v)
    if fallback_arr is not None and bool((~matched).any()):
        fallback = _sample_texture_nearest(fallback_arr, local_u, local_v)
        if fallback is not None:
            out[~matched] = fallback[~matched]
    return out


def _map_channel(maps: Mapping[str, Any], key: str, default: int = 0) -> int:
    raw = str(maps.get(f"{key}_channel") or "").strip().casefold()
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
    lo: float = 0.0,
    hi: float = 1.0,
) -> float:
    raw = maps.get(key)
    try:
        value = float(raw) if raw not in {None, ""} else float(default)
    except Exception:
        value = float(default)
    return max(float(lo), min(float(hi), value))


def _map_vec3(maps: Mapping[str, Any], key: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = maps.get(key)
    if isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        parts = str(raw or "").replace(";", ",").split(",") if str(raw or "").strip() else []
    values: list[float] = []
    for idx in range(3):
        try:
            values.append(max(0.0, float(parts[idx])))
        except Exception:
            values.append(float(default[idx]))
    return (values[0], values[1], values[2])


def _id_color(text: str):
    import numpy as np

    digest = hashlib.sha1(str(text or "id").encode("utf-8", errors="replace")).digest()
    return np.asarray([0.18 + (digest[idx] / 255.0) * 0.78 for idx in range(3)], dtype=np.float32)


def _to_pil_rgba(image: Any, *, size: tuple[int, int] | None = None):
    import numpy as np
    from PIL import Image

    if isinstance(image, Image.Image):
        out = image.convert("RGBA")
    else:
        arr = np.asarray(image)
        if arr.dtype != np.uint8:
            arr = np.clip(arr, 0, 255).astype(np.uint8)
        if arr.ndim != 3 or arr.shape[2] not in {3, 4}:
            out = Image.new("RGBA", size or (1, 1), (0, 0, 0, 0))
        elif arr.shape[2] == 3:
            out = Image.fromarray(arr, "RGB").convert("RGBA")
        else:
            out = Image.fromarray(arr, "RGBA")
    if size is not None and out.size != size:
        out = out.resize(size, Image.Resampling.BILINEAR)
    return out


def _depth_array(depth_frame: Any, width: int, height: int):
    if depth_frame is None:
        return None
    try:
        import numpy as np
        from PIL import Image

        arr = np.asarray(depth_frame, dtype=np.float32)
        if arr.ndim == 3:
            arr = arr[:, :, 0]
        if arr.ndim != 2 or arr.size <= 0:
            return None
        if arr.shape != (height, width):
            arr = np.asarray(
                Image.fromarray(arr.astype(np.float32), mode="F").resize((width, height), Image.Resampling.BILINEAR),
                dtype=np.float32,
            )
        return np.nan_to_num(np.clip(arr, 0.0, 1.0), nan=1.0, posinf=1.0, neginf=0.0)
    except Exception:
        return None


def _normalize3(x, y, z):
    import numpy as np

    length = np.maximum(np.sqrt(x * x + y * y + z * z), 1.0e-6)
    return x / length, y / length, z / length


def _empty_packet_data(width: int, height: int) -> dict[str, Any]:
    import numpy as np

    return {
        "alpha": np.zeros((height, width), dtype=np.float32),
        "depth": np.ones((height, width), dtype=np.float32),
        "normal": np.zeros((height, width, 3), dtype=np.float32),
        "position": np.zeros((height, width, 3), dtype=np.float32),
        "position_valid": np.zeros((height, width), dtype=bool),
        "albedo": np.zeros((height, width, 3), dtype=np.float32),
        "roughness": np.zeros((height, width), dtype=np.float32),
        "metallic": np.zeros((height, width), dtype=np.float32),
        "reflectance": np.zeros((height, width), dtype=np.float32),
        "emissive": np.zeros((height, width, 3), dtype=np.float32),
        "material_id": np.zeros((height, width, 3), dtype=np.float32),
        "object_id": np.zeros((height, width, 3), dtype=np.float32),
        "triangle_pixels": 0,
    }


def _collect_pbr_packet_data(width: int, height: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    import numpy as np

    data = _empty_packet_data(width, height)
    for item in items:
        if not isinstance(item, Mapping):
            continue
        object_color = _id_color(str(item.get("track_id") or item.get("asset_path") or "object"))
        triangles = item.get("pbr_triangles")
        if not isinstance(triangles, (list, tuple)):
            continue
        for tri in triangles:
            if not isinstance(tri, Mapping):
                continue
            maps = tri.get("maps") if isinstance(tri.get("maps"), Mapping) else {}
            material_key = str(
                tri.get("material_id")
                or maps.get("material_id")
                or maps.get("material_name")
                or tri.get("texture")
                or item.get("asset_path")
                or "material"
            )
            material_color = _id_color(material_key)
            base_arr = _texture_array(str(maps.get("base") or tri.get("texture") or ""))
            rough_arr = _texture_array(str(maps.get("roughness") or ""))
            metal_arr = _texture_array(str(maps.get("metallic") or ""))
            opacity_arr = _texture_array(str(maps.get("opacity") or ""))
            emissive_arr = _texture_array(str(maps.get("emissive") or ""))
            base_udim = _texture_udim_arrays(maps, "base")
            rough_udim = _texture_udim_arrays(maps, "roughness")
            metal_udim = _texture_udim_arrays(maps, "metallic")
            opacity_udim = _texture_udim_arrays(maps, "opacity")
            emissive_udim = _texture_udim_arrays(maps, "emissive")
            try:
                tri_depth_default = float(tri.get("object_depth", 0.5) or 0.5)
            except Exception:
                tri_depth_default = 0.5
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

                alpha = np.clip(interp(16), 0.0, 1.0) if stride > 16 else np.ones_like(w0, dtype=np.float32)
                u = interp(2)
                v = interp(3)
                base_factor = np.dstack([
                    np.clip(interp(13), 0.0, 16.0),
                    np.clip(interp(14), 0.0, 16.0),
                    np.clip(interp(15), 0.0, 16.0),
                ]).astype(np.float32) if stride > 15 else np.ones((box_y1 - box_y0, box_x1 - box_x0, 3), dtype=np.float32)
                base_sample = _sample_texture_udim(base_udim, base_arr, u, v)
                if base_sample is not None:
                    albedo = linear_to_srgb(srgb_to_linear(base_sample[:, :, :3]) * base_factor)
                    if base_sample.shape[2] >= 4:
                        alpha = alpha * np.clip(base_sample[:, :, 3], 0.0, 1.0)
                else:
                    albedo = np.clip(base_factor, 0.0, 1.0)
                opacity_sample = _sample_texture_udim(opacity_udim, opacity_arr, u, v)
                if opacity_sample is not None:
                    alpha = alpha * np.clip(opacity_sample[:, :, _map_channel(maps, "opacity", 0)], 0.0, 1.0)
                cutoff = _map_float(maps, "alpha_cutoff", 0.0, lo=0.0, hi=1.0)
                if cutoff > 0.0:
                    alpha = np.where(alpha >= cutoff, alpha, 0.0)
                rough_sample = _sample_texture_udim(rough_udim, rough_arr, u, v)
                if rough_sample is not None:
                    roughness = np.clip(rough_sample[:, :, _map_channel(maps, "roughness", 0)], 0.0, 1.0)
                else:
                    roughness = np.clip(interp(17), 0.0, 1.0) if stride > 17 else np.full_like(w0, 0.45)
                metal_sample = _sample_texture_udim(metal_udim, metal_arr, u, v)
                if metal_sample is not None:
                    metallic = np.clip(metal_sample[:, :, _map_channel(maps, "metallic", 0)], 0.0, 1.0)
                else:
                    metallic = np.clip(interp(18), 0.0, 1.0) if stride > 18 else np.zeros_like(w0)
                emissive_sample = _sample_texture_udim(emissive_udim, emissive_arr, u, v)
                if emissive_sample is not None:
                    emissive = np.clip(np.asarray(emissive_sample[:, :, :3], dtype=np.float32), 0.0, 1.0)
                    factor = np.asarray(_map_vec3(maps, "emissive_factor", (1.0, 1.0, 1.0)), dtype=np.float32)
                    emissive = np.clip(emissive * factor.reshape(1, 1, 3), 0.0, 1.0)
                else:
                    emissive = np.zeros((box_y1 - box_y0, box_x1 - box_x0, 3), dtype=np.float32)
                nx, ny, nz = _normalize3(interp(4), interp(5), interp(6))
                normal = np.dstack([nx, ny, nz]).astype(np.float32)
                if stride >= _PBR_VERTEX_STRIDE_FLOATS:
                    position = np.dstack([interp(20), interp(21), interp(22)]).astype(np.float32)
                else:
                    position = np.zeros((box_y1 - box_y0, box_x1 - box_x0, 3), dtype=np.float32)
                reflectance = np.clip(interp(19), 0.0, 1.0) if stride > 19 else np.full_like(w0, 0.5)
                sub_depth = data["depth"][box_y0:box_y1, box_x0:box_x1]
                sub_alpha = data["alpha"][box_y0:box_y1, box_x0:box_x1]
                tri_depth = np.full_like(w0, max(0.0, min(1.0, tri_depth_default)), dtype=np.float32)
                write = mask & (alpha > 0.001) & (tri_depth <= sub_depth + 1.0e-5)
                if not bool(write.any()):
                    continue
                data["triangle_pixels"] += int(write.sum())
                sub_depth[write] = tri_depth[write]
                sub_alpha[write] = alpha[write]
                data["normal"][box_y0:box_y1, box_x0:box_x1][write] = normal[write]
                data["position"][box_y0:box_y1, box_x0:box_x1][write] = position[write]
                data["position_valid"][box_y0:box_y1, box_x0:box_x1][write] = stride >= _PBR_VERTEX_STRIDE_FLOATS
                data["albedo"][box_y0:box_y1, box_x0:box_x1][write] = albedo[write]
                data["roughness"][box_y0:box_y1, box_x0:box_x1][write] = roughness[write]
                data["metallic"][box_y0:box_y1, box_x0:box_x1][write] = metallic[write]
                data["reflectance"][box_y0:box_y1, box_x0:box_x1][write] = reflectance[write]
                data["emissive"][box_y0:box_y1, box_x0:box_x1][write] = emissive[write]
                data["material_id"][box_y0:box_y1, box_x0:box_x1][write] = material_color
                data["object_id"][box_y0:box_y1, box_x0:box_x1][write] = object_color
    return data


def _packet_triangle_image(width: int, height: int, items: list[dict[str, Any]], key: str):
    from PIL import Image, ImageDraw

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer, "RGBA")
    for item in items:
        if not isinstance(item, Mapping):
            continue
        vertices = item.get(key)
        if not isinstance(vertices, (list, tuple)) or len(vertices) < 18:
            continue
        usable = (len(vertices) // 18) * 18
        for idx in range(0, usable, 18):
            try:
                row = [float(value) for value in vertices[idx:idx + 18]]
                points = [
                    _ndc_to_pixel(row[0], row[1], width, height),
                    _ndc_to_pixel(row[6], row[7], width, height),
                    _ndc_to_pixel(row[12], row[13], width, height),
                ]
                rgba = []
                for offset in (0, 6, 12):
                    rgba.append((row[offset + 2], row[offset + 3], row[offset + 4], row[offset + 5]))
                color = tuple(
                    max(0, min(255, int(round(sum(values[channel] for values in rgba) / 3.0 * 255.0))))
                    for channel in range(4)
                )
                if color[3] > 0:
                    draw.polygon(points, fill=color)
            except Exception:
                continue
    return layer


def _ao_from_alpha(alpha, settings: Mapping[str, Any] | None = None):
    import numpy as np
    from PIL import Image, ImageFilter

    cfg = _as_mapping(settings)
    try:
        radius = max(1.0, min(32.0, float(cfg.get("ao_radius", cfg.get("radius", 4.0)) or 4.0)))
    except Exception:
        radius = 4.0
    try:
        strength = max(0.0, min(2.0, float(cfg.get("ao_strength", cfg.get("strength", 0.55)) or 0.55)))
    except Exception:
        strength = 0.55
    alpha_img = Image.fromarray(np.clip(alpha * 255.0, 0, 255).astype(np.uint8), "L")
    local_fill = np.asarray(alpha_img.filter(ImageFilter.GaussianBlur(radius=radius)), dtype=np.float32) / 255.0
    wider_fill = np.asarray(alpha_img.filter(ImageFilter.GaussianBlur(radius=radius * 2.0)), dtype=np.float32) / 255.0
    cavity = np.clip(local_fill - wider_fill * 0.42, 0.0, 1.0)
    edge = np.clip(local_fill * (1.0 - alpha), 0.0, 1.0)
    occlusion = np.clip(cavity + edge * 0.72, 0.0, 1.0)
    return np.clip(1.0 - occlusion * strength, 0.0, 1.0)


def _rgb_image(arr):
    import numpy as np
    from PIL import Image

    return Image.fromarray(np.clip(np.asarray(arr) * 255.0, 0, 255).astype(np.uint8), "RGB")


def _l_image(arr):
    import numpy as np
    from PIL import Image

    return Image.fromarray(np.clip(np.asarray(arr) * 255.0, 0, 255).astype(np.uint8), "L")


def _position_pass(position, valid):
    import numpy as np

    out = np.zeros_like(position, dtype=np.float32)
    if bool(valid.any()):
        vals = position[valid]
        lo = vals.min(axis=0)
        hi = vals.max(axis=0)
        denom = np.maximum(hi - lo, 1.0e-6)
        out[valid] = np.clip((position[valid] - lo) / denom, 0.0, 1.0)
        flat_axes = (hi - lo) <= 1.0e-6
        if bool(flat_axes.any()):
            out[:, :, flat_axes] = np.where(valid[:, :, None], 0.5, out[:, :, flat_axes])
    return out


def _pass_stats(image: Any, path: str, *, source: str, policy: str) -> dict[str, Any]:
    import numpy as np

    arr = np.asarray(image)
    if arr.ndim == 2:
        active = arr > 0
        mean = float(arr.mean() / 255.0) if arr.size else 0.0
    else:
        active = np.max(arr[:, :, :3], axis=2) > 0
        mean = float(arr[:, :, :3].mean() / 255.0) if arr.size else 0.0
    return {
        "path": str(path or ""),
        "mode": str(getattr(image, "mode", "")),
        "width": int(getattr(image, "size", [0, 0])[0]),
        "height": int(getattr(image, "size", [0, 0])[1]),
        "changed_pixels": int(active.sum()),
        "mean": mean,
        "source": source,
        "policy": policy,
    }


def render_packet_render_passes(
    *,
    beauty: Any,
    items: list[dict[str, Any]],
    settings: Mapping[str, Any] | None = None,
    base_frame: Any = None,
    depth_frame: Any = None,
    diagnostics: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate and optionally write render-pass PNGs from preview packets."""
    cfg = normalize_render_pass_settings(settings or {})
    pass_diag: dict[str, Any] = {
        "schema": RENDER_PASS_OUTPUT_SCHEMA,
        "enabled": bool(cfg["enabled"]),
        "requested_passes": list(cfg["passes"]),
        "pass_count": 0,
        "output_dir": str(cfg.get("output_dir") or ""),
        "format": str(cfg.get("format") or "png"),
        "renderer": "packet_export",
        "data_policy": "packet_reconstruction_from_preview_geometry",
        "passes": {},
        "warnings": [],
    }
    if not bool(cfg["enabled"]):
        return {}, pass_diag
    try:
        import numpy as np
    except Exception as exc:
        pass_diag["warnings"].append(f"render pass export skipped: {type(exc).__name__}: {exc}")
        return {}, pass_diag

    beauty_img = _to_pil_rgba(beauty)
    width, height = beauty_img.size
    beauty_rgb = np.asarray(beauty_img.convert("RGB"), dtype=np.float32) / 255.0
    packet = _collect_pbr_packet_data(width, height, list(items or []))
    alpha = np.clip(packet["alpha"], 0.0, 1.0)
    mask = alpha > 0.001
    depth = np.where(mask, np.clip(1.0 - packet["depth"], 0.0, 1.0), 0.0)
    if not bool(mask.any()):
        depth_fallback = _depth_array(depth_frame, width, height)
        if depth_fallback is not None:
            depth = np.clip(1.0 - depth_fallback, 0.0, 1.0)
    ao = _ao_from_alpha(alpha, diagnostics.get("pbr_ambient_occlusion_rendering") if isinstance(diagnostics, Mapping) else {})
    ao_masked = np.where(mask, ao, 0.0)
    albedo = np.clip(packet["albedo"], 0.0, 1.0) * alpha[:, :, None]
    roughness = np.where(mask, np.clip(packet["roughness"], 0.0, 1.0), 0.0)
    metallic = np.where(mask, np.clip(packet["metallic"], 0.0, 1.0), 0.0)
    reflectance = np.where(mask, np.clip(packet["reflectance"], 0.0, 1.0), 0.0)
    emissive = np.clip(packet["emissive"], 0.0, 1.0) * alpha[:, :, None]
    diffuse = np.clip(albedo * (1.0 - metallic[:, :, None] * 0.7) * ao[:, :, None], 0.0, 1.0)
    specular = np.clip((beauty_rgb - diffuse * 0.62) * alpha[:, :, None] + reflectance[:, :, None] * 0.12, 0.0, 1.0)
    direct = np.clip(beauty_rgb * alpha[:, :, None] * 0.72 + diffuse * 0.18, 0.0, 1.0)
    indirect = np.clip(albedo * ao[:, :, None] * 0.28 + emissive, 0.0, 1.0)
    shadow_layer = np.asarray(_packet_triangle_image(width, height, list(items or []), "shadow_vertices"), dtype=np.float32) / 255.0
    reflection_layer = np.asarray(_packet_triangle_image(width, height, list(items or []), "reflection_vertices"), dtype=np.float32) / 255.0
    shadow = np.maximum(shadow_layer[:, :, 3], np.where(mask, (1.0 - ao) * 0.65, 0.0))
    reflection = np.clip(reflection_layer[:, :, :3] * reflection_layer[:, :, 3:4], 0.0, 1.0)
    normal = np.where(mask[:, :, None], np.clip(packet["normal"] * 0.5 + 0.5, 0.0, 1.0), 0.0)
    passes = {
        "beauty": beauty_img.convert("RGB"),
        "alpha_mask": _l_image(alpha),
        "depth": _l_image(depth),
        "normal": _rgb_image(normal),
        "position": _rgb_image(_position_pass(packet["position"], packet["position_valid"] & mask)),
        "material_id": _rgb_image(packet["material_id"] * alpha[:, :, None]),
        "object_id": _rgb_image(packet["object_id"] * alpha[:, :, None]),
        "ambient_occlusion": _l_image(ao_masked),
        "direct_lighting": _rgb_image(direct),
        "indirect_lighting": _rgb_image(indirect),
        "diffuse": _rgb_image(diffuse),
        "specular": _rgb_image(specular),
        "albedo": _rgb_image(albedo),
        "emissive": _rgb_image(emissive),
        "roughness": _l_image(roughness),
        "metallic": _l_image(metallic),
        "transparency": _l_image(np.where(mask, 1.0 - alpha, 0.0)),
        "shadow": _l_image(shadow),
        "reflection": _rgb_image(reflection),
    }
    sources = {
        "beauty": "final_composited_frame",
        "alpha_mask": "packet_pbr_alpha",
        "depth": "packet_object_depth",
        "normal": "packet_geometry_normal",
        "position": "packet_world_position",
        "material_id": "stable_material_hash",
        "object_id": "stable_track_hash",
        "ambient_occlusion": "packet_alpha_screen_ao",
        "shadow": "shadow_catcher_packets_or_ao_fallback",
        "reflection": "reflection_catcher_packets",
    }
    policies = {
        "beauty": "post_effects_included",
        "ambient_occlusion": "screen_space_packet_approximation",
        "direct_lighting": "beauty_packet_split_approximation",
        "indirect_lighting": "albedo_ao_emissive_approximation",
        "diffuse": "albedo_metallic_ao_approximation",
        "specular": "beauty_minus_diffuse_reflectance_approximation",
    }
    output_dir = Path(str(cfg.get("output_dir") or "")) if str(cfg.get("output_dir") or "").strip() else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    selected: dict[str, Any] = {}
    for name in list(cfg["passes"]):
        image = passes.get(name)
        if image is None:
            continue
        path_text = ""
        if output_dir is not None:
            path = output_dir / f"{name}.png"
            image.save(path)
            path_text = str(path)
        selected[name] = image
        pass_diag["passes"][name] = _pass_stats(
            image,
            path_text,
            source=sources.get(name, "packet_material_data"),
            policy=policies.get(name, "packet_data_pass"),
        )
    pass_diag["pass_count"] = len(selected)
    pass_diag["triangle_pixels"] = int(packet.get("triangle_pixels", 0) or 0)
    pass_diag["written_count"] = len([
        row for row in pass_diag["passes"].values()
        if isinstance(row, Mapping) and str(row.get("path") or "")
    ])
    return selected, pass_diag
