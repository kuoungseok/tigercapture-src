"""Material, UV, and PBR triangle packet helpers for AR/PBR GPU preview."""
from __future__ import annotations

import math
from typing import Any, Mapping


PBR_VERTEX_STRIDE_FLOATS = 23
PBR_TRIANGLE_FLOATS = PBR_VERTEX_STRIDE_FLOATS * 3


def _clamp01(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(default)


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


def _ndc_from_projected(point: tuple[float, float, float], width: int, height: int) -> tuple[float, float]:
    return (
        max(-4.0, min(4.0, (float(point[0]) / max(1.0, float(width))) * 2.0 - 1.0)),
        max(-4.0, min(4.0, 1.0 - (float(point[1]) / max(1.0, float(height))) * 2.0)),
    )


def material_unlit(material: Mapping[str, Any]) -> bool:
    shader = str(material.get("shader_model") or material.get("source_shader") or "").casefold()
    return bool(material.get("unlit")) or "mtoon" in shader or shader == "unlit"


def material_has_pbr_data(material: Mapping[str, Any]) -> bool:
    if bool(material.get("pbr_available")):
        return True
    for key in (
        "base_texture_source",
        "roughness_texture_source",
        "metallic_texture_source",
        "normal_texture_source",
        "occlusion_texture_source",
        "emissive_texture_source",
        "opacity_texture_source",
    ):
        if str(material.get(key) or "").startswith("gltf_pbr"):
            return True
    return not material_unlit(material) and ("roughness" in material or "metallic" in material)


def material_pbr(material: Mapping[str, Any], *, force_pbr: bool = False) -> tuple[float, float, float]:
    if material_unlit(material) and not force_pbr:
        return (1.0, 0.0, 0.0)
    return (
        max(0.04, min(1.0, _clamp01(material.get("roughness"), 0.45))),
        _clamp01(material.get("metallic"), 0.0),
        _clamp01(material.get("reflectance"), 0.5),
    )


def material_texture_maps(
    texture_plan: Mapping[str, Mapping[str, str]],
    material: Mapping[str, Any],
) -> dict[str, str]:
    if not texture_plan:
        return {}
    material_name = str(material.get("name") or material.get("id") or "")
    maps = texture_plan.get(material_name) if material_name else None
    if maps is None and len(texture_plan) == 1:
        maps = next(iter(texture_plan.values()))
    if not isinstance(maps, Mapping):
        return {}
    out: dict[str, str] = {}
    for key in ("base", "roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity", "height"):
        path = str(maps.get(key) or "")
        if path:
            out[key] = path
        channel = str(maps.get(f"{key}_channel") or "")
        if channel:
            out[f"{key}_channel"] = channel
        for suffix in (
            "wrap_s",
            "wrap_t",
            "udim_tiles",
            "udim_tile_count",
            "udim_primary_tile",
            "udim_sampling_model",
        ):
            value = str(maps.get(f"{key}_{suffix}") or "")
            if value:
                out[f"{key}_{suffix}"] = value
    for key in (
        "alpha_mode",
        "alpha_cutoff",
        "emissive_factor",
        "uv_v_flip",
        "shader_model",
        "source_shader",
        "render_queue",
        "mtoon_render_queue",
        "mtoon_cull_mode",
        "mtoon_zwrite",
        "mtoon_src_blend",
        "mtoon_dst_blend",
        "depth_write",
    ):
        value = str(maps.get(key) or "")
        if value:
            out[key] = value
    return out


def geometry_uvs(geometry: Mapping[str, Any]) -> list[Any]:
    uvs = geometry.get("uvs")
    return list(uvs) if isinstance(uvs, list) else []


def geometry_uvs_for_material(geometry: Mapping[str, Any], material: Mapping[str, Any]) -> list[Any]:
    try:
        uv_set = int(material.get("uv_set", material.get("base_uv_set", 0)) or 0)
    except Exception:
        uv_set = 0
    uv_sets = geometry.get("uv_sets")
    if isinstance(uv_sets, Mapping):
        for key in (str(uv_set), uv_set):
            rows = uv_sets.get(key)  # type: ignore[arg-type]
            if isinstance(rows, list):
                return list(rows)
    return geometry_uvs(geometry)


def _coerce_uv_pair(value: Any) -> list[float] | None:
    try:
        return [float(value[0]), float(value[1])]
    except Exception:
        return None


def material_uv_transform(material: Mapping[str, Any]) -> Mapping[str, Any] | None:
    transform = material.get("uv_transform") or material.get("base_uv_transform")
    return transform if isinstance(transform, Mapping) else None


def apply_uv_transform_pair(uv: list[float], transform: Mapping[str, Any] | None) -> list[float]:
    if not transform:
        return uv
    try:
        offset_raw = transform.get("offset") if isinstance(transform.get("offset"), (list, tuple)) else []
        scale_raw = transform.get("scale") if isinstance(transform.get("scale"), (list, tuple)) else []
        rotation = float(transform.get("rotation", 0.0) or 0.0)
        scale = list(scale_raw)
        offset = list(offset_raw)
        sx = float((scale + [1.0, 1.0])[0])
        sy = float((scale + [1.0, 1.0])[1])
        ox = float((offset + [0.0, 0.0])[0])
        oy = float((offset + [0.0, 0.0])[1])
        u = float(uv[0]) * sx
        v = float(uv[1]) * sy
        c = math.cos(rotation)
        s = math.sin(rotation)
        return [u * c - v * s + ox, u * s + v * c + oy]
    except Exception:
        return uv


def triangle_uvs(
    geometry: Mapping[str, Any],
    triangle_index: int,
    vertex_indices: tuple[int, int, int],
    geometry_uv_rows: list[Any],
    uv_transform: Mapping[str, Any] | None = None,
) -> list[Any] | None:
    triangle_uv_rows = geometry.get("triangle_uvs")
    if isinstance(triangle_uv_rows, list) and 0 <= triangle_index < len(triangle_uv_rows):
        raw = triangle_uv_rows[triangle_index]
        if isinstance(raw, (list, tuple)) and len(raw) >= 3:
            out: list[list[float]] = []
            for value in raw[:3]:
                uv = _coerce_uv_pair(value)
                if uv is None:
                    break
                out.append(apply_uv_transform_pair(uv, uv_transform))
            if len(out) == 3:
                return out
    max_index = max(vertex_indices)
    if len(geometry_uv_rows) > max_index:
        out = []
        for idx in vertex_indices:
            uv = _coerce_uv_pair(geometry_uv_rows[idx])
            if uv is None:
                return None
            out.append(apply_uv_transform_pair(uv, uv_transform))
        return out
    return None


def triangle_tangent_basis(
    v0: tuple[float, float, float],
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
    uv0: Any,
    uv1: Any,
    uv2: Any,
    normal: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    try:
        u0, vv0 = float(uv0[0]), float(uv0[1])
        u1, vv1 = float(uv1[0]), float(uv1[1])
        u2, vv2 = float(uv2[0]), float(uv2[1])
        e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
        e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])
        du1, dv1 = u1 - u0, vv1 - vv0
        du2, dv2 = u2 - u0, vv2 - vv0
        denom = du1 * dv2 - du2 * dv1
        if abs(denom) > 1e-8:
            inv = 1.0 / denom
            tangent = (
                (e1[0] * dv2 - e2[0] * dv1) * inv,
                (e1[1] * dv2 - e2[1] * dv1) * inv,
                (e1[2] * dv2 - e2[2] * dv1) * inv,
            )
            bitangent = (
                (e2[0] * du1 - e1[0] * du2) * inv,
                (e2[1] * du1 - e1[1] * du2) * inv,
                (e2[2] * du1 - e1[2] * du2) * inv,
            )
            return _normalize3(tangent, (1.0, 0.0, 0.0)), _normalize3(bitangent, (0.0, 1.0, 0.0))
    except Exception:
        pass
    nx, ny, nz = normal
    fallback_tangent = (1.0, 0.0, 0.0) if abs(nx) < 0.9 else (0.0, 1.0, 0.0)
    tangent = _normalize3((
        fallback_tangent[0] - nx * (fallback_tangent[0] * nx + fallback_tangent[1] * ny + fallback_tangent[2] * nz),
        fallback_tangent[1] - ny * (fallback_tangent[0] * nx + fallback_tangent[1] * ny + fallback_tangent[2] * nz),
        fallback_tangent[2] - nz * (fallback_tangent[0] * nx + fallback_tangent[1] * ny + fallback_tangent[2] * nz),
    ), fallback_tangent)
    bitangent = _normalize3((
        ny * tangent[2] - nz * tangent[1],
        nz * tangent[0] - nx * tangent[2],
        nx * tangent[1] - ny * tangent[0],
    ), (0.0, 1.0, 0.0))
    return tangent, bitangent


def extend_texture_vertex(
    out: list[float],
    point: tuple[float, float, float],
    uv: Any,
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
) -> None:
    x, y = _ndc_from_projected(point, width, height)
    try:
        u = float(uv[0])
        v = float(uv[1])
    except Exception:
        u, v = 0.0, 0.0
    out.extend((
        x,
        y,
        max(-16.0, min(16.0, u)),
        max(-16.0, min(16.0, v)),
        rgba[0],
        rgba[1],
        rgba[2],
        rgba[3],
    ))


def extend_pbr_texture_vertex(
    out: list[float],
    point: tuple[float, float, float],
    world_pos: tuple[float, float, float],
    uv: Any,
    normal: tuple[float, float, float],
    tangent: tuple[float, float, float],
    bitangent: tuple[float, float, float],
    width: int,
    height: int,
    rgba: tuple[float, float, float, float],
    pbr: tuple[float, float, float],
) -> None:
    x, y = _ndc_from_projected(point, width, height)
    try:
        u = float(uv[0])
        v = float(uv[1])
    except Exception:
        u, v = 0.0, 0.0
    out.extend((
        x,
        y,
        max(-16.0, min(16.0, u)),
        max(-16.0, min(16.0, v)),
        normal[0],
        normal[1],
        normal[2],
        tangent[0],
        tangent[1],
        tangent[2],
        bitangent[0],
        bitangent[1],
        bitangent[2],
        rgba[0],
        rgba[1],
        rgba[2],
        rgba[3],
        pbr[0],
        pbr[1],
        pbr[2],
        float(world_pos[0]),
        float(world_pos[1]),
        float(world_pos[2]),
    ))


def build_material_triangle_packets(
    *,
    projected_points: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    world_points: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]],
    tri_uvs: list[Any] | None,
    normal: tuple[float, float, float],
    material: Mapping[str, Any],
    geometry: Mapping[str, Any],
    texture_path: str,
    texture_maps: Mapping[str, str],
    rgba: tuple[float, float, float, float],
    width: int,
    height: int,
    avg_z: float,
    pbr_rgba: tuple[float, float, float, float] | None = None,
    force_marmoset_pbr: bool = False,
) -> dict[str, Any]:
    texture_triangle: dict[str, Any] | None = None
    pbr_triangle: dict[str, Any] | None = None
    pbr_roughness: float | None = None
    if tri_uvs is None:
        return {
            "texture_triangle": None,
            "pbr_triangle": None,
            "pbr_roughness": None,
            "marmoset_pbr_triangle": False,
        }
    p0, p1, p2 = projected_points
    v0, v1, v2 = world_points
    uv0, uv1, uv2 = tri_uvs[0], tri_uvs[1], tri_uvs[2]
    if texture_path:
        texture_row: list[float] = []
        for point, uv in ((p0, uv0), (p1, uv1), (p2, uv2)):
            extend_texture_vertex(texture_row, point, uv, width, height, rgba)
        if len(texture_row) == 24:
            texture_triangle = {
                "z": float(avg_z),
                "texture": texture_path,
                "vertices": texture_row,
            }
    if texture_path or texture_maps:
        pbr_row: list[float] = []
        tangent, bitangent = triangle_tangent_basis(v0, v1, v2, uv0, uv1, uv2, normal)
        pbr = material_pbr(material, force_pbr=force_marmoset_pbr)
        pbr_roughness = float(pbr[0])
        pbr_color = pbr_rgba if pbr_rgba is not None else rgba
        for point, world_pos, uv in ((p0, v0, uv0), (p1, v1, uv1), (p2, v2, uv2)):
            extend_pbr_texture_vertex(
                pbr_row,
                point,
                world_pos,
                uv,
                normal,
                tangent,
                bitangent,
                width,
                height,
                pbr_color,
                pbr,
            )
        if len(pbr_row) == PBR_TRIANGLE_FLOATS:
            pbr_triangle = {
                "z": float(avg_z),
                "material_id": str(
                    material.get("id")
                    or material.get("name")
                    or geometry.get("material_id")
                    or geometry.get("id")
                    or texture_path
                    or "material"
                ),
                "texture": texture_path,
                "maps": dict(texture_maps or {}),
                "base_color_factor": list(pbr_color),
                "vertices": pbr_row,
            }
    return {
        "texture_triangle": texture_triangle,
        "pbr_triangle": pbr_triangle,
        "pbr_roughness": pbr_roughness,
        "marmoset_pbr_triangle": bool(force_marmoset_pbr and pbr_triangle is not None),
    }
