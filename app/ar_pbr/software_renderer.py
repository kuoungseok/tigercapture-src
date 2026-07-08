"""Deterministic CPU preview renderer for AR/PBR mesh contracts.

This is a feature-contract renderer, not the final production backend. It
projects imported mesh triangles, applies simple PBR-like material controls, and
composites shadows, reflections, and depth occlusion without PyQt or OpenGL.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.catcher import normalize_catcher_settings
from app.ar_pbr.depth_occlusion import (
    apply_depth_occlusion_to_alpha,
    depth_occlusion_tolerance,
    normalize_depth_frame,
)
from app.ar_pbr.pbr_math import (
    cook_torrance_direct,
    energy_conserving_diffuse_weight,
    fresnel_schlick,
    material_f0,
    srgb_to_linear,
)
from app.ar_pbr.tone_mapping import apply_display_transform, normalize_color_management_settings
from app.ar_pbr.placement import resolve_track_placement
from app.ar_pbr.texture_plan import (
    material_base_texture_color,
    material_base_texture_path,
    resolve_material_texture_plan,
)
from app.ar_pbr import gpu_material_packets


_TEXTURE_SAMPLE_CACHE: dict[tuple[str, int, int], Any] = {}


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


def _normalize_depth(depth_frame: Any, width: int, height: int):
    return normalize_depth_frame(depth_frame, width, height)


def _as_vec3(value: Any, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if not isinstance(value, (list, tuple)):
        return default
    vals = list(value) + list(default)
    try:
        return (float(vals[0]), float(vals[1]), float(vals[2]))
    except Exception:
        return default


def _normalize(v: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length <= 1e-8:
        return (0.0, 0.0, 1.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _track_lighting(track: Mapping[str, Any]) -> Mapping[str, Any]:
    render = track.get("render") if isinstance(track.get("render"), Mapping) else {}
    lighting = render.get("lighting") if isinstance(render, Mapping) else {}
    return lighting if isinstance(lighting, Mapping) else {}


def _lighting_float(
    lighting: Mapping[str, Any],
    key: str,
    default: float,
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> float:
    try:
        value = float(lighting.get(key, default))
    except Exception:
        value = float(default)
    if lo is not None:
        value = max(float(lo), value)
    if hi is not None:
        value = min(float(hi), value)
    return value


def _light_direction_from_lighting(
    lighting: Mapping[str, Any],
    fallback: tuple[float, float, float],
) -> tuple[float, float, float]:
    if not lighting:
        return _normalize(fallback)
    azimuth = math.radians(
        _lighting_float(lighting, "light_azimuth", 45.0, lo=-180.0, hi=180.0)
        - _lighting_float(lighting, "ibl_rotation", 0.0, lo=-1.0, hi=1.0) * 360.0
    )
    elevation = math.radians(_lighting_float(lighting, "light_elevation", 45.0, lo=-20.0, hi=89.0))
    ce = math.cos(elevation)
    to_light = (
        math.cos(azimuth) * ce,
        math.sin(elevation),
        math.sin(azimuth) * ce,
    )
    return _normalize((-to_light[0], -to_light[1], -to_light[2]))


def _rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> tuple[tuple[float, float, float], ...]:
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    return (
        (cy * cz, -cy * sz, sy),
        (cx * sz + cz * sx * sy, cx * cz - sx * sy * sz, -cy * sx),
        (sx * sz - cx * cz * sy, cz * sx + cx * sy * sz, cx * cy),
    )


def _mat_mul_vec(m: tuple[tuple[float, float, float], ...], v: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _descriptor_for_track(track: Mapping[str, Any], settings: Mapping[str, Any]) -> Mapping[str, Any]:
    direct = track.get("asset_descriptor")
    if isinstance(direct, Mapping):
        return direct
    descriptors = settings.get("asset_descriptors")
    if isinstance(descriptors, Mapping):
        track_id = str(track.get("id") or "")
        asset_path = str(track.get("asset_path") or "")
        for key in (track_id, asset_path, "default"):
            item = descriptors.get(key)
            if isinstance(item, Mapping):
                return item
    return {}


def _texture_plan_for_track(
    track: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> tuple[Mapping[str, Mapping[str, str]], dict[str, Any]]:
    if not descriptor:
        return {}, {"status": "none", "reason": "missing_descriptor"}
    try:
        asset_path = str(track.get("asset_path") or descriptor.get("source_path") or "")
        plan, diag = resolve_material_texture_plan(asset_path, descriptor)
        return plan, diag
    except Exception as exc:
        return {}, {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _default_cube_geometry() -> dict[str, Any]:
    vertices = [
        [-0.5, -0.5, -0.5], [0.5, -0.5, -0.5], [0.5, 0.5, -0.5], [-0.5, 0.5, -0.5],
        [-0.5, -0.5, 0.5], [0.5, -0.5, 0.5], [0.5, 0.5, 0.5], [-0.5, 0.5, 0.5],
    ]
    triangles = [
        [0, 1, 2], [0, 2, 3],
        [4, 6, 5], [4, 7, 6],
        [0, 4, 5], [0, 5, 1],
        [1, 5, 6], [1, 6, 2],
        [2, 6, 7], [2, 7, 3],
        [3, 7, 4], [3, 4, 0],
    ]
    return {
        "name": "unit_cube",
        "vertices": vertices,
        "triangles": triangles,
        "bounds": {
            "center": [0.0, 0.0, 0.0],
            "size": [1.0, 1.0, 1.0],
        },
    }


def _first_geometry(descriptor: Mapping[str, Any]) -> Mapping[str, Any]:
    geometries = descriptor.get("geometries")
    if isinstance(geometries, list):
        for item in geometries:
            if isinstance(item, Mapping) and item.get("vertices") and item.get("triangles"):
                return item
    return _default_cube_geometry()


def _geometry_model_material_maps(descriptor: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    geometry_to_model: dict[str, str] = {}
    model_to_material: dict[str, str] = {}
    connections = descriptor.get("connections")
    if not isinstance(connections, list):
        return geometry_to_model, model_to_material
    geometry_ids = {
        str(item.get("id") or "")
        for item in descriptor.get("geometries", [])
        if isinstance(item, Mapping)
    }
    material_ids = {
        str(item.get("id") or "")
        for item in descriptor.get("materials", [])
        if isinstance(item, Mapping)
    }
    for connection in connections:
        if not isinstance(connection, Mapping):
            continue
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in geometry_ids:
            geometry_to_model[child] = parent
        if child in material_ids:
            model_to_material[parent] = child
    return geometry_to_model, model_to_material


def _all_geometries(descriptor: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    geometries = descriptor.get("geometries")
    out: list[Mapping[str, Any]] = []
    if isinstance(geometries, list):
        for item in geometries:
            if isinstance(item, Mapping) and item.get("vertices") and item.get("triangles"):
                out.append(item)
    return out or [_default_cube_geometry()]


def _material(
    track: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    geometry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "base_color": [1.0, 0.45, 0.18, 1.0],
        "roughness": 0.45,
        "metallic": 0.0,
        "reflectance": 0.5,
    }
    material = None
    materials = descriptor.get("materials")
    if isinstance(materials, list) and materials:
        material_by_id = {
            str(item.get("id") or ""): item
            for item in materials
            if isinstance(item, Mapping)
        }
        if isinstance(geometry, Mapping):
            material_id = str(geometry.get("material_id") or "")
            if not material_id:
                geometry_to_model, model_to_material = _geometry_model_material_maps(descriptor)
                geometry_id = str(geometry.get("id") or "")
                model_id = geometry_to_model.get(geometry_id, "")
                material_id = model_to_material.get(model_id, "")
            material = material_by_id.get(material_id)
        if material is None and isinstance(materials[0], Mapping):
            material = materials[0]
    if isinstance(material, Mapping):
        out.update(dict(material))
        for key, fallback in (
            ("base_color", [1.0, 0.45, 0.18, 1.0]),
            ("roughness", 0.45),
            ("metallic", 0.0),
            ("reflectance", 0.5),
        ):
            if key not in out:
                out[key] = fallback
    track_material = track.get("material")
    should_override = bool(track.get("material_override")) or material is None
    if should_override and isinstance(track_material, Mapping):
        for key in ("base_color", "roughness", "metallic", "reflectance"):
            if key in track_material:
                out[key] = track_material[key]  # type: ignore[assignment]
    return out


def _material_roughness(material: Mapping[str, Any]) -> float:
    return gpu_material_packets.material_pbr(material)[0]


def _camera_intrinsics(camera_solution: Mapping[str, Any] | None, width: int, height: int) -> tuple[float, float, float, float]:
    intrinsics = camera_solution.get("intrinsics") if isinstance(camera_solution, Mapping) else None
    frame_size = camera_solution.get("frame_size") if isinstance(camera_solution, Mapping) else None
    fx = fy = float(min(width, height)) * 1.15
    cx = float(width) * 0.5
    cy = float(height) * 0.5
    if isinstance(intrinsics, Mapping):
        try:
            src_w = float(frame_size[0]) if isinstance(frame_size, (list, tuple)) and frame_size else float(width)
            src_h = float(frame_size[1]) if isinstance(frame_size, (list, tuple)) and len(frame_size) > 1 else float(height)
            sx = float(width) / max(src_w, 1.0)
            sy = float(height) / max(src_h, 1.0)
            fx = float(intrinsics.get("fx", fx)) * sx
            fy = float(intrinsics.get("fy", fy)) * sy
            cx = float(intrinsics.get("cx", cx)) * sx
            cy = float(intrinsics.get("cy", cy)) * sy
        except Exception:
            pass
    return fx, fy, cx, cy


def _transform_vertex_list(
    vertices_raw: Sequence[Any],
    track: Mapping[str, Any],
    settings: Mapping[str, Any],
    bounds: Mapping[str, Any] | None,
) -> list[tuple[float, float, float]]:
    bounds = bounds if isinstance(bounds, Mapping) else {}
    center = _as_vec3(bounds.get("center") if isinstance(bounds, Mapping) else None, (0.0, 0.0, 0.0))
    size = _as_vec3(bounds.get("size") if isinstance(bounds, Mapping) else None, (1.0, 1.0, 1.0))
    max_size = max(size[0], size[1], size[2], 1e-6)

    transform = track.get("transform") if isinstance(track.get("transform"), Mapping) else {}
    position = _as_vec3(transform.get("position") if isinstance(transform, Mapping) else None, (0.0, 0.0, 0.0))
    rotation = _as_vec3(transform.get("rotation") if isinstance(transform, Mapping) else None, (0.0, 0.0, 0.0))
    scale = _as_vec3(transform.get("scale") if isinstance(transform, Mapping) else None, (1.0, 1.0, 1.0))
    base_z = float(settings.get("camera_z", 3.25) or 3.25)
    rot = _rotation_matrix(rotation[0], rotation[1], rotation[2])

    out: list[tuple[float, float, float]] = []
    for raw in vertices_raw:
        v = _as_vec3(raw, (0.0, 0.0, 0.0))
        local = (
            (v[0] - center[0]) / max_size * scale[0],
            (v[1] - center[1]) / max_size * scale[1],
            (v[2] - center[2]) / max_size * scale[2],
        )
        rotated = _mat_mul_vec(rot, local)
        out.append((
            rotated[0] + position[0],
            rotated[1] + position[1],
            max(0.05, base_z + position[2] - rotated[2]),
        ))
    return out


def _bounds_from_vertex_list(vertices_raw: Sequence[Any]) -> dict[str, list[float]]:
    try:
        import numpy as np

        rows = [
            _as_vec3(raw, (0.0, 0.0, 0.0))
            for raw in vertices_raw
            if isinstance(raw, (list, tuple)) and len(raw) >= 3
        ]
        if not rows:
            raise ValueError("empty vertex list")
        arr = np.asarray(rows, dtype=np.float64)
        lo = arr.min(axis=0)
        hi = arr.max(axis=0)
        center = (lo + hi) * 0.5
        size = np.maximum(hi - lo, 1.0e-6)
        return {
            "center": [float(v) for v in center],
            "size": [float(v) for v in size],
        }
    except Exception:
        return {"center": [0.0, 0.0, 0.0], "size": [1.0, 1.0, 1.0]}


def _transform_vertices(
    geometry: Mapping[str, Any],
    track: Mapping[str, Any],
    settings: Mapping[str, Any],
    scene_bounds: Mapping[str, Any] | None = None,
    descriptor: Mapping[str, Any] | None = None,
    time_ms: int = 0,
) -> list[tuple[float, float, float]]:
    vertices_raw = geometry.get("vertices") or []
    if descriptor is not None:
        try:
            from app.ar_pbr.animation import animated_vertices_for_geometry

            vertices_raw = animated_vertices_for_geometry(
                vertices_raw,
                geometry=geometry,
                descriptor=descriptor,
                track=track,
                time_ms=int(time_ms),
            )
        except Exception:
            pass
    preserve_scene_layout = bool(settings.get("preserve_scene_layout", True))
    if isinstance(geometry.get("skin_inverse_bind_matrices"), list):
        bounds = _bounds_from_vertex_list(vertices_raw)
    elif preserve_scene_layout and isinstance(scene_bounds, Mapping):
        bounds = scene_bounds
    else:
        bounds = geometry.get("bounds") if isinstance(geometry.get("bounds"), Mapping) else {}
    return _transform_vertex_list(vertices_raw, track, settings, bounds)


def _project(
    vertices: list[tuple[float, float, float]],
    *,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
) -> list[tuple[float, float, float]]:
    projected: list[tuple[float, float, float]] = []
    for x, y, z in vertices:
        zz = max(z, 0.05)
        projected.append((cx + fx * x / zz, cy - fy * y / zz, zz))
    return projected


def _base_color(material: Mapping[str, Any]) -> tuple[int, int, int, int]:
    color = material.get("base_color")
    vals = list(color) if isinstance(color, (list, tuple)) else [1.0, 0.45, 0.18, 1.0]
    vals += [1.0, 1.0, 1.0, 1.0]
    return tuple(max(0, min(255, int(round(float(v) * 255.0)))) for v in vals[:4])  # type: ignore[return-value]


def _triangle_uv_centroid(
    geometry: Mapping[str, Any],
    material: Mapping[str, Any],
    triangle_index: int,
    indices: list[int],
) -> tuple[float, float] | None:
    try:
        vertex_indices = (int(indices[0]), int(indices[1]), int(indices[2]))
    except Exception:
        return None
    uv_rows = gpu_material_packets.geometry_uvs_for_material(geometry, material)
    uvs = gpu_material_packets.triangle_uvs(
        geometry,
        triangle_index,
        vertex_indices,
        uv_rows,
        gpu_material_packets.material_uv_transform(material),
    )
    if uvs is None or len(uvs) != 3:
        return None
    return (
        (float(uvs[0][0]) + float(uvs[1][0]) + float(uvs[2][0])) / 3.0,
        (float(uvs[0][1]) + float(uvs[1][1]) + float(uvs[2][1])) / 3.0,
    )


def _texture_image_for_sampling(path: str):
    if not str(path or "").strip():
        return None
    try:
        from PIL import Image

        p = Path(path)
        st = p.stat()
        key = (str(p.resolve()), int(st.st_size), int(st.st_mtime_ns))
        cached = _TEXTURE_SAMPLE_CACHE.get(key)
        if cached is not None:
            return cached
        image = Image.open(p).convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.BILINEAR)
        _TEXTURE_SAMPLE_CACHE[key] = image.copy()
        return _TEXTURE_SAMPLE_CACHE[key]
    except Exception:
        return None


def _sample_material_texture_color(
    texture_plan: Mapping[str, Mapping[str, str]],
    material: Mapping[str, Any],
    geometry: Mapping[str, Any],
    triangle_index: int,
    indices: list[int],
    *,
    alpha: int,
) -> tuple[int, int, int, int] | None:
    path = material_base_texture_path(texture_plan, material)
    if not path:
        return None
    uv = _triangle_uv_centroid(geometry, material, triangle_index, indices)
    if uv is None:
        return None
    image = _texture_image_for_sampling(path)
    if image is None:
        return None
    try:
        u = uv[0] - math.floor(uv[0])
        v = uv[1] - math.floor(uv[1])
        x = max(0, min(image.width - 1, int(round(u * (image.width - 1)))))
        y = max(0, min(image.height - 1, int(round((1.0 - v) * (image.height - 1)))))
        r, g, b = image.getpixel((x, y))
        return (int(r), int(g), int(b), max(0, min(255, int(alpha))))
    except Exception:
        return None


def _shade_color(
    color: tuple[int, int, int, int],
    normal: tuple[float, float, float],
    material: Mapping[str, Any],
    light_dir: tuple[float, float, float],
    *,
    direct_strength: float = 1.0,
    ibl_exposure: float = 1.0,
    color_management: Mapping[str, Any] | None = None,
) -> tuple[int, int, int, int]:
    import numpy as np

    n = _normalize(normal)
    light = _normalize((-light_dir[0], -light_dir[1], -light_dir[2]))
    view = (0.0, 0.0, -1.0)
    if _dot(n, view) < 0.0:
        n = (-n[0], -n[1], -n[2])
    half_vec = _normalize((light[0] + view[0], light[1] + view[1], light[2] + view[2]))
    roughness, metallic, reflectance = gpu_material_packets.material_pbr(material)
    ndotl = max(0.0, _dot(n, light))
    ndotv = max(0.0, _dot(n, view))
    ndoth = max(0.0, _dot(n, half_vec))
    vdoth = max(0.0, _dot(view, half_vec))
    albedo = srgb_to_linear(np.asarray([[[float(color[0]) / 255.0, float(color[1]) / 255.0, float(color[2]) / 255.0]]], dtype=np.float32))
    rough = np.asarray([[roughness]], dtype=np.float32)
    metal = np.asarray([[metallic]], dtype=np.float32)
    refl = np.asarray([[reflectance]], dtype=np.float32)
    f0 = material_f0(albedo, metal, refl)
    fresnel = fresnel_schlick(np.asarray([[ndotv]], dtype=np.float32), f0)
    kd = energy_conserving_diffuse_weight(fresnel, metal)
    ambient = albedo * kd * (0.16 + rough[:, :, None] * 0.10) * max(0.0, float(ibl_exposure))
    direct = cook_torrance_direct(
        albedo=albedo,
        f0=f0,
        roughness=rough,
        metallic=metal,
        ndotl=np.asarray([[ndotl]], dtype=np.float32),
        ndotv=np.asarray([[ndotv]], dtype=np.float32),
        ndoth=np.asarray([[ndoth]], dtype=np.float32),
        vdoth=np.asarray([[vdoth]], dtype=np.float32),
        light_strength=max(0.0, float(direct_strength)),
        ao=np.asarray([[1.0]], dtype=np.float32),
    )
    rgb_linear = np.maximum(ambient + direct, 0.0)
    srgb = apply_display_transform(rgb_linear, color_management or {})[0, 0]
    rgb = [max(0, min(255, int(round(float(channel) * 255.0)))) for channel in srgb[:3]]
    return (rgb[0], rgb[1], rgb[2], color[3])


def _draw_depth_aware_polygon(
    *,
    object_layer: Any,
    polygon: list[tuple[float, float]],
    fill: tuple[int, int, int, int],
    depth: Any,
    object_depth: float,
    tolerance: float,
) -> None:
    from PIL import Image, ImageDraw
    import numpy as np

    width, height = object_layer.size
    mask = Image.new("L", object_layer.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(polygon, fill=fill[3])
    if depth is not None:
        mask_arr = np.asarray(mask, dtype=np.uint8).copy()
        mask_arr, _diag = apply_depth_occlusion_to_alpha(
            mask_arr,
            depth,
            object_depth=object_depth,
            settings={"occlusion_tolerance": tolerance},
        )
        mask = Image.fromarray(mask_arr, "L")
    color = Image.new("RGBA", (width, height), fill)
    object_layer.alpha_composite(Image.composite(color, Image.new("RGBA", (width, height), (0, 0, 0, 0)), mask))


def _draw_shadow(
    shadow_layer: Any,
    screen_points: list[tuple[float, float, float]],
    *,
    alpha: int,
    softness: float = 0.55,
    matte_alpha: float = 0.0,
) -> None:
    if not screen_points:
        return
    from PIL import ImageDraw

    soft = max(0.0, min(1.0, float(softness)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    width, height = shadow_layer.size
    xs = [p[0] for p in screen_points]
    ys = [p[1] for p in screen_points]
    x0 = max(0, int(min(xs)))
    x1 = min(width, int(max(xs)))
    y1 = min(height, int(max(ys) + max(2, (max(ys) - min(ys)) * 0.16)))
    h = max(2, int((max(ys) - min(ys)) * 0.18))
    y0 = max(0, y1 - h)
    if x1 <= x0 or y1 <= y0:
        return
    draw = ImageDraw.Draw(shadow_layer, "RGBA")
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5
    rx = max(1.0, (x1 - x0) * 0.5)
    ry = max(1.0, (y1 - y0) * 0.5)
    for radius_scale, alpha_scale in (
        (1.00 + soft * 0.10, 0.70),
        (1.32 + soft * 0.42, 0.34),
        (1.74 + soft * 0.72, 0.15),
    ):
        layer_alpha = max(int(round(255.0 * matte * 0.035)), int(round(alpha * alpha_scale)))
        if layer_alpha <= 0:
            continue
        draw.ellipse(
            (
                int(round(cx - rx * radius_scale)),
                int(round(cy - ry * radius_scale * (0.82 + soft * 0.24))),
                int(round(cx + rx * radius_scale)),
                int(round(cy + ry * radius_scale * (0.82 + soft * 0.24))),
            ),
            fill=(0, 0, 0, max(0, min(255, layer_alpha))),
        )


def _draw_reflection(
    reflection_layer: Any,
    screen_points: list[tuple[float, float, float]],
    *,
    color: tuple[int, int, int, int],
    opacity: float = 0.35,
    roughness: float = 0.5,
    softness: float = 0.45,
    matte_alpha: float = 0.0,
    contact_strength: float = 0.32,
    contact_falloff: float = 0.58,
) -> None:
    if not screen_points:
        return
    from PIL import ImageDraw

    opacity = max(0.0, min(1.0, float(opacity)))
    rough = max(0.02, min(1.0, float(roughness)))
    soft = max(0.0, min(1.0, float(softness)))
    matte = max(0.0, min(1.0, float(matte_alpha)))
    contact = max(0.0, min(1.0, float(contact_strength)))
    falloff = max(0.05, min(1.0, float(contact_falloff)))
    width, height = reflection_layer.size
    xs = [p[0] for p in screen_points]
    ys = [p[1] for p in screen_points]
    x0 = max(0, int(min(xs)))
    x1 = min(width, int(max(xs)))
    y0 = max(0, int(max(ys)))
    y1 = min(height, y0 + max(1, int((max(ys) - min(ys)) * 0.35)))
    if x1 <= x0 or y1 <= y0:
        return
    draw = ImageDraw.Draw(reflection_layer, "RGBA")
    span_y = max(1, y1 - y0)
    layers = (
        (0.00, 0.34 + contact * 0.20, 0.68 + contact * 0.24),
        (0.18 + soft * 0.05, 0.58 + rough * 0.18, 0.30),
        (0.38 + soft * 0.10, 0.90 + rough * 0.34, 0.13),
    )
    for y_start_scale, y_end_scale, alpha_scale in layers:
        ly0 = int(round(y0 + span_y * y_start_scale * falloff))
        ly1 = int(round(y0 + span_y * y_end_scale * (0.82 + rough * 0.35)))
        if ly1 <= ly0:
            continue
        layer_alpha = max(
            int(round(255.0 * matte * 0.025)),
            int(round(color[3] * opacity * alpha_scale)),
        )
        if layer_alpha <= 0:
            continue
        inset = int(round((x1 - x0) * (0.06 + y_start_scale * 0.18)))
        tint = 1.0 - rough * (0.12 + y_start_scale * 0.20)
        draw.rectangle(
            (
                max(0, x0 + inset),
                max(0, ly0),
                min(width, x1 - inset),
                min(height, ly1),
            ),
            fill=(
                max(0, min(255, int(round(color[0] * tint)))),
                max(0, min(255, int(round(color[1] * tint)))),
                max(0, min(255, int(round(color[2] * tint)))),
                max(0, min(255, layer_alpha)),
            ),
        )


def _decimation_ratio(geometry: Mapping[str, Any]) -> float:
    try:
        source = float(geometry.get("source_triangle_count") or 0.0)
        stored = float(geometry.get("triangle_count") or len(geometry.get("triangles") or []) or 0.0)
        if source <= 0.0 or stored <= 0.0 or source <= stored:
            return 1.0
        return source / stored
    except Exception:
        return 1.0


def _solidify_decimated_layer(layer: Any, *, ratio: float) -> Any:
    """Fill small screen-space gaps caused by aggressive preview decimation."""
    try:
        if ratio <= 1.15:
            return layer
        from PIL import Image, ImageChops, ImageFilter

        radius = 1
        size = radius * 2 + 1
        expanded = layer.filter(ImageFilter.MaxFilter(size=size))
        original_alpha = layer.getchannel("A")
        expanded_alpha = expanded.getchannel("A")
        soft_alpha = expanded_alpha.filter(ImageFilter.GaussianBlur(radius=max(0.6, radius * 0.45)))
        soft_alpha = ImageChops.lighter(soft_alpha, original_alpha)
        under_alpha = soft_alpha.point(lambda value: int(max(0, min(255, value * 0.72))))
        under = expanded.copy()
        under.putalpha(under_alpha)
        out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        out.alpha_composite(under)
        out.alpha_composite(layer)
        return out
    except Exception:
        return layer


def _draw_preview_point_splats(
    layer: Any,
    points: Sequence[tuple[float, float, float]],
    *,
    color: tuple[int, int, int, int],
    ratio: float,
) -> int:
    if not points:
        return 0
    try:
        from PIL import ImageDraw

        width, height = layer.size
        radius = max(1, min(4, int(round(math.sqrt(max(1.0, ratio)) * 0.32))))
        alpha = max(42, min(104, int(round(64 + math.log(max(1.0, ratio), 2) * 4.0))))
        fill = (color[0], color[1], color[2], min(color[3], alpha))
        draw = ImageDraw.Draw(layer, "RGBA")
        count = 0
        for x, y, _z in points:
            if x < -radius or y < -radius or x > width + radius or y > height + radius:
                continue
            ix = int(round(x))
            iy = int(round(y))
            draw.rectangle((ix - radius, iy - radius, ix + radius, iy + radius), fill=fill)
            count += 1
        return count
    except Exception:
        return 0


def _convex_hull_2d(points: Sequence[tuple[float, float, float]]) -> list[tuple[float, float]]:
    unique = sorted({(round(float(x), 2), round(float(y), 2)) for x, y, _z in points})
    if len(unique) <= 1:
        return unique

    def _cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _draw_preview_hull(
    layer: Any,
    points: Sequence[tuple[float, float, float]],
    *,
    color: tuple[int, int, int, int],
    ratio: float,
) -> bool:
    if len(points) < 3 or ratio <= 2.0:
        return False
    try:
        from PIL import ImageDraw

        hull = _convex_hull_2d(points)
        if len(hull) < 3:
            return False
        alpha = max(22, min(58, int(round(26 + math.log(max(1.0, ratio), 2) * 3.5))))
        ImageDraw.Draw(layer, "RGBA").polygon(hull, fill=(color[0], color[1], color[2], min(color[3], alpha)))
        return True
    except Exception:
        return False


def render_software_pbr_frame(
    base_frame: Any,
    *,
    time_ms: int,
    tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any,
    settings: Mapping[str, Any],
    diagnostics: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    image, kind, error = _frame_to_pil_rgba(base_frame)
    if image is None:
        diagnostics["fallback"] = True
        diagnostics["warnings"].append(error or "unsupported frame")
        return base_frame, diagnostics

    try:
        from PIL import Image
        import numpy as np
    except Exception as exc:
        diagnostics["fallback"] = True
        diagnostics["warnings"].append(f"missing software renderer dependency: {type(exc).__name__}")
        return base_frame, diagnostics

    width, height = image.size
    depth = _normalize_depth(depth_frame, width, height)
    default_light_dir = _as_vec3(settings.get("light_direction"), (-0.35, -0.85, -0.4))
    near = float(settings.get("depth_near", 0.05) or 0.05)
    far = float(settings.get("depth_far", 8.0) or 8.0)
    tolerance = depth_occlusion_tolerance(settings)

    shadow_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    reflection_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    solid_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    object_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    rendered_tracks = 0
    triangle_count = 0
    fallback_mesh_count = 0
    decimated_mesh_count = 0
    max_decimation_ratio = 1.0
    preview_splat_count = 0
    preview_hull_count = 0
    placement_diags: list[dict[str, Any]] = []
    depth_occlusion_used = False
    lighting_diags: list[dict[str, Any]] = []
    max_reflection_blur = 0.0
    texture_tinted_triangle_count = 0
    texture_sampled_triangle_count = 0
    texture_plan_diags: list[dict[str, Any]] = []
    pending_track_count = 0

    for track in tracks:
        candidate_solution = track.get("camera_solution") if isinstance(track.get("camera_solution"), Mapping) else None
        track_camera_solution = candidate_solution if candidate_solution and candidate_solution.get("plane") else camera_solution
        fx, fy, cx, cy = _camera_intrinsics(track_camera_solution, width, height)
        track, placement_diag = resolve_track_placement(
            track,
            track_camera_solution,
            frame_size=(width, height),
            settings=settings,
        )
        placement_diags.append(placement_diag)
        descriptor = _descriptor_for_track(track, settings)
        if str(descriptor.get("import_state") or "").casefold() in {"loading", "pending", "error"}:
            pending_track_count += 1
            continue
        texture_plan, texture_plan_diag = _texture_plan_for_track(track, descriptor)
        texture_plan_diags.append({
            "track_id": str(track.get("id") or ""),
            **dict(texture_plan_diag),
        })
        geometries = _all_geometries(descriptor)
        descriptor_bounds = descriptor.get("bounds") if isinstance(descriptor.get("bounds"), Mapping) else None
        if not descriptor or all(geometry.get("name") == "unit_cube" for geometry in geometries):
            fallback_mesh_count += 1
        lighting = _track_lighting(track)
        catcher_settings = normalize_catcher_settings(lighting)
        color_management = normalize_color_management_settings(lighting)
        shadow_catcher_settings = catcher_settings["shadow_catcher"]
        reflection_catcher_settings = catcher_settings["reflection_catcher"]
        light_dir = _light_direction_from_lighting(lighting, default_light_dir)
        direct_strength = _lighting_float(lighting, "direct_strength", 1.0, lo=0.0, hi=4.0)
        ibl_exposure = _lighting_float(lighting, "ibl_exposure", 1.0, lo=0.0, hi=8.0)
        shadow_strength = _lighting_float(lighting, "shadow_strength", 1.0, lo=0.0, hi=1.0)
        lighting_diags.append({
            "track_id": str(track.get("id") or ""),
            "light_direction": [round(float(v), 5) for v in light_dir],
            "direct_strength": direct_strength,
            "ibl_exposure": ibl_exposure,
            "shadow_strength": shadow_strength,
            "catcher": catcher_settings,
            "color_management": color_management,
        })
        draw_items: list[tuple[float, list[tuple[float, float]], tuple[int, int, int, int], float]] = []
        all_projected: list[tuple[float, float, float]] = []
        for geometry in geometries:
            ratio = _decimation_ratio(geometry)
            is_decimated = ratio > 1.15 or bool(geometry.get("decimated"))
            if is_decimated:
                decimated_mesh_count += 1
                max_decimation_ratio = max(max_decimation_ratio, ratio)
            vertices = _transform_vertices(
                geometry,
                track,
                settings,
                scene_bounds=descriptor_bounds,
                descriptor=descriptor,
                time_ms=int(time_ms),
            )
            projected = _project(vertices, fx=fx, fy=fy, cx=cx, cy=cy)
            all_projected.extend(projected)
            triangles = geometry.get("triangles") or []
            material = _material(track, descriptor, geometry)
            base_color = _base_color(material)
            average_texture_color = material_base_texture_color(texture_plan, material, alpha=base_color[3])
            color = average_texture_color or base_color
            if is_decimated and bool(settings.get("preview_point_splats", False)):
                preview_points = geometry.get("preview_points") or []
                if isinstance(preview_points, list) and preview_points:
                    point_vertices = _transform_vertex_list(
                        preview_points,
                        track,
                        settings,
                        descriptor_bounds if isinstance(descriptor_bounds, Mapping) else geometry.get("bounds"),
                    )
                    point_projected = _project(point_vertices, fx=fx, fy=fy, cx=cx, cy=cy)
                    preview_splat_count += _draw_preview_point_splats(
                        solid_layer,
                        point_projected,
                        color=_shade_color(
                            color,
                            (0.0, 0.0, 1.0),
                            material,
                        light_dir,
                        direct_strength=direct_strength * 0.35,
                        ibl_exposure=ibl_exposure,
                        color_management=color_management,
                    ),
                    ratio=ratio,
                )

            if track.get("reflection_catcher"):
                roughness = max(
                    float(reflection_catcher_settings["roughness"]),
                    _material_roughness(material),
                )
                max_reflection_blur = max(
                    max_reflection_blur,
                    roughness * float(reflection_catcher_settings["softness"]) * 4.0,
                )
                _draw_reflection(
                    reflection_layer,
                    projected,
                    color=color,
                    opacity=float(reflection_catcher_settings["opacity"]),
                    roughness=roughness,
                    softness=float(reflection_catcher_settings["softness"]),
                    matte_alpha=float(reflection_catcher_settings["matte_alpha"]),
                    contact_strength=float(reflection_catcher_settings["contact_reflection_strength"]),
                    contact_falloff=float(reflection_catcher_settings["contact_reflection_falloff"]),
                )

            for triangle_index, tri in enumerate(triangles):
                if not isinstance(tri, (list, tuple)) or len(tri) < 3:
                    continue
                try:
                    indices = [int(tri[0]), int(tri[1]), int(tri[2])]
                    pts3 = [vertices[idx] for idx in indices]
                    pts2 = [projected[idx] for idx in indices]
                except Exception:
                    continue
                normal = _cross(_sub(pts3[1], pts3[0]), _sub(pts3[2], pts3[0]))
                if abs(normal[0]) + abs(normal[1]) + abs(normal[2]) <= 1e-8:
                    continue
                texture_color = _sample_material_texture_color(
                    texture_plan,
                    material,
                    geometry,
                    triangle_index,
                    indices,
                    alpha=base_color[3],
                )
                color = texture_color or average_texture_color or base_color
                screen_poly = [(pts2[0][0], pts2[0][1]), (pts2[1][0], pts2[1][1]), (pts2[2][0], pts2[2][1])]
                avg_z = (pts2[0][2] + pts2[1][2] + pts2[2][2]) / 3.0
                object_depth = max(0.0, min(1.0, (avg_z - near) / max(far - near, 1e-6)))
                draw_items.append((
                    avg_z,
                    screen_poly,
                    _shade_color(
                        color,
                        normal,
                        material,
                        light_dir,
                        direct_strength=direct_strength,
                        ibl_exposure=ibl_exposure,
                        color_management=color_management,
                    ),
                    object_depth,
                ))
                if texture_color is not None:
                    texture_sampled_triangle_count += 1
                if texture_color is not None or average_texture_color is not None:
                    texture_tinted_triangle_count += 1

        if track.get("shadow_catcher"):
            base_alpha = int(settings.get("shadow_alpha", 72) or 72)
            shadow_alpha = int(max(
                0,
                min(
                    255,
                    round(
                        base_alpha
                        * shadow_strength
                        * float(shadow_catcher_settings["opacity"])
                    ),
                ),
            ))
            if shadow_alpha > 0 or float(shadow_catcher_settings["matte_alpha"]) > 0.0:
                _draw_shadow(
                    shadow_layer,
                    all_projected,
                    alpha=shadow_alpha,
                    softness=float(shadow_catcher_settings["softness"]),
                    matte_alpha=float(shadow_catcher_settings["matte_alpha"]),
                )

        draw_items.sort(key=lambda row: row[0], reverse=True)
        for _, screen_poly, fill, object_depth in draw_items:
            if track.get("occlusion") and depth is not None:
                depth_occlusion_used = True
                _draw_depth_aware_polygon(
                    object_layer=object_layer,
                    polygon=screen_poly,
                    fill=fill,
                    depth=depth,
                    object_depth=object_depth,
                    tolerance=tolerance,
                )
            else:
                from PIL import ImageDraw
                ImageDraw.Draw(object_layer, "RGBA").polygon(screen_poly, fill=fill)
            triangle_count += 1
        if draw_items:
            rendered_tracks += 1

    blur = max(0.0, float(settings.get("shadow_blur", 3.0) or 3.0))
    if blur:
        from PIL import ImageFilter
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur))
    if max_reflection_blur > 0.01:
        from PIL import ImageFilter
        reflection_layer = reflection_layer.filter(ImageFilter.GaussianBlur(radius=max_reflection_blur))
    if decimated_mesh_count and bool(settings.get("preview_solidify_decimated", False)):
        object_layer = _solidify_decimated_layer(object_layer, ratio=max_decimation_ratio)
    image.alpha_composite(shadow_layer)
    image.alpha_composite(reflection_layer)
    image.alpha_composite(solid_layer)
    image.alpha_composite(object_layer)
    diagnostics["mode"] = "software_pbr"
    diagnostics["rendered_track_count"] = rendered_tracks
    diagnostics["software_renderer"] = {
        "backend": "cpu_pil_numpy",
        "triangle_count": triangle_count,
        "geometry_count": sum(len(_all_geometries(_descriptor_for_track(track, settings))) for track in tracks),
        "fallback_mesh_count": fallback_mesh_count,
        "decimated_mesh_count": decimated_mesh_count,
        "max_decimation_ratio": round(max_decimation_ratio, 3),
        "preview_splat_count": preview_splat_count,
        "preview_hull_count": preview_hull_count,
        "texture_tinted_triangle_count": texture_tinted_triangle_count,
        "texture_sampled_triangle_count": texture_sampled_triangle_count,
        "texture_plans": texture_plan_diags,
        "pending_track_count": pending_track_count,
        "depth_occlusion": depth_occlusion_used,
        "reflection_blur_radius": round(float(max_reflection_blur), 3),
        "catcher_contract": "matte_soft_shadow_roughness_blur_contact_reflection",
        "color_management_contract": "scene_linear_display_transform_preserve_alpha",
        "camera_intrinsics": _camera_intrinsics(camera_solution, width, height),
        "placement_applied_count": sum(1 for item in placement_diags if item.get("applied")),
        "placements": placement_diags,
        "lighting": lighting_diags,
    }
    return _pil_to_original_kind(image, kind, base_frame), diagnostics
