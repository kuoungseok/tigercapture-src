"""GPU-preview mesh packet builder for AR/PBR tracks.

This module does not issue OpenGL calls. It converts AR/PBR track + asset
descriptor state into compact triangle packets that ``OpenGLPreviewWidget`` can
draw directly over the video texture. Headless export consumes the same packet
contract through ``app.ar_pbr.export_packet_renderer`` and falls back to the
software renderer only when packet rendering cannot draw a track.
"""
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
from app.ar_pbr.ambient_occlusion import normalize_ambient_occlusion_settings
from app.ar_pbr.anisotropy import normalize_anisotropic_material_settings
from app.ar_pbr.catcher import normalize_catcher_settings
from app.ar_pbr.bevel import normalize_bevel_settings
from app.ar_pbr.clearcoat import normalize_clearcoat_settings
from app.ar_pbr.cloth import normalize_cloth_sheen_settings
from app.ar_pbr.depth_of_field import normalize_depth_of_field_settings
from app.ar_pbr.depth_occlusion import normalize_depth_edge_glow_settings
from app.ar_pbr.displacement import normalize_displacement_settings
from app.ar_pbr.glint import normalize_glint_sparkle_settings
from app.ar_pbr.caustics import normalize_caustics_settings
from app.ar_pbr.schema import normalize_ar_tracks, track_active_at
from app.ar_pbr.shadow import normalize_shadow_settings
from app.ar_pbr.tone_mapping import normalize_color_management_settings
from app.ar_pbr.hair import normalize_hair_groom_settings
from app.ar_pbr.hybrid_rendering import normalize_hybrid_render_settings
from app.ar_pbr.ray_gi_detail import normalize_ray_gi_detail_settings
from app.ar_pbr.material_layering import normalize_material_layering_settings
from app.ar_pbr.microsurface import normalize_microsurface_settings
from app.ar_pbr.parallax import normalize_parallax_settings
from app.ar_pbr.post_effects import normalize_post_effects_settings
from app.ar_pbr.lens_effects import normalize_lens_effects_settings
from app.ar_pbr.lens_flare import normalize_lens_flare_settings
from app.ar_pbr.render_passes import normalize_render_pass_settings
from app.ar_pbr.motion_blur import merge_motion_blur_settings
from app.ar_pbr.subsurface import normalize_subsurface_settings
from app.ar_pbr.substrate import normalize_substrate_settings
from app.ar_pbr.surface import normalize_surface_settings
from app.ar_pbr.triplanar import normalize_triplanar_settings
from app.ar_pbr.transmission import normalize_transmission_settings
from app.ar_pbr import gpu_material_packets
from app.ar_pbr.gpu_preview_math import (
    _active_render_profile,
    _depth_texture_payload,
    _extend_ndc_vertex,
    _float,
    _lighting_hdri_path,
    _max_triangles,
    _ndc_from_projected,
    _normalize3,
    _projected_bounds,
    _sample_triangle_rows,
    _shade_tuple_to_floats,
    _track_is_pending,
    _triangle_offscreen,
)
from app.ar_pbr.gpu_preview_geometry import (
    _contact_shadow_vertices,
    _convex_hull_2d,
    _ellipse_vertices,
    _mesh_contact_shadow_vertices,
    _mesh_reflection_catcher_vertices,
    _polygon_fan_vertices,
    _rect_vertices,
    _reflection_catcher_vertices,
)


PBR_VERTEX_STRIDE_FLOATS = gpu_material_packets.PBR_VERTEX_STRIDE_FLOATS
PBR_TRIANGLE_FLOATS = gpu_material_packets.PBR_TRIANGLE_FLOATS


def _bool_setting(settings: Mapping[str, Any], *keys: str) -> bool:
    for key in keys:
        if key not in settings:
            continue
        value = settings.get(key)
        if isinstance(value, bool):
            return value
        if value is None:
            continue
        text = str(value).strip().casefold()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled"}:
            return False
    return False


def _preview_safe_post_effects(
    post_effects: Mapping[str, Any],
    *,
    disable_bloom: bool,
) -> dict[str, Any]:
    out = dict(post_effects or {})
    if not disable_bloom or not bool(out.get("bloom_enabled")):
        return out
    out["preview_bloom_suppressed"] = True
    out["bloom_enabled"] = False
    out["bloom_strength"] = 0.0
    still_enabled = any(
        bool(out.get(key))
        for key in (
            "vignette_enabled",
            "grain_enabled",
            "sharpen_enabled",
        )
    )
    out["enabled"] = bool(still_enabled)
    out["mode"] = "post_effects" if still_enabled else "off"
    return out














































def build_gpu_preview_items(
    *,
    frame_size: tuple[int, int],
    time_ms: int,
    ar_tracks: list[dict[str, Any]],
    camera_solution: Mapping[str, Any] | None,
    depth_frame: Any = None,
    settings: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build OpenGL overlay packets for active AR/PBR tracks.

    Returned packet format is intentionally simple: each item contains a flat
    float list of ``x, y, r, g, b, a`` values in NDC space. The actual raster
    work happens in ``OpenGLPreviewWidget``.
    """
    settings_map: Mapping[str, Any] = settings or {}
    preview_disable_bloom = _bool_setting(
        settings_map,
        "preview_disable_bloom",
        "disable_preview_bloom",
        "forbid_preview_bloom",
    )
    width = max(1, int(frame_size[0]))
    height = max(1, int(frame_size[1]))
    tracks = normalize_ar_tracks(ar_tracks)
    active = [track for track in tracks if track_active_at(track, int(time_ms))]
    diagnostics: dict[str, Any] = {
        "ok": True,
        "mode": "gpu_preview",
        "fallback": False,
        "time_ms": int(time_ms),
        "track_count": len(tracks),
        "active_track_count": len(active),
        "rendered_track_count": 0,
        "triangle_count": 0,
        "triangle_limit": 0,
        "source_triangle_count": 0,
        "sampled_triangle_count": 0,
        "sampled_triangle_source_count": 0,
        "gpu_renderer": {
            "packet": "ndc_color_triangles_with_gpu_catchers",
            "texture_maps": "none",
            "texture_sampling": "not_sampled",
            "pbr_preview": "not_available",
            "depth_occlusion": "coarse" if depth_frame is not None else "none",
            "shadow_catcher": "matte_soft_contact_shadow_packet",
            "reflection_catcher": "roughness_blur_contact_reflection_packet",
        },
        "texture_map_status_counts": {},
        "texture_map_count": 0,
        "texture_material_count": 0,
        "texture_missing_count": 0,
        "texture_tinted_triangle_count": 0,
        "pbr_substrate_material_count": 0,
        "pbr_triangle_count": 0,
        "live_depth_texture_triangle_count": 0,
        "shadow_triangle_count": 0,
        "reflection_triangle_count": 0,
        "visible_triangle_count": 0,
        "occluded_triangle_count": 0,
        "placement_applied_count": 0,
        "placements": [],
        "warnings": [],
        "errors": [],
    }
    if not active:
        diagnostics["fallback"] = True
        diagnostics["warnings"].append("no active ar_pbr tracks")
        return [], diagnostics

    try:
        from app.ar_pbr.software_renderer import (
            _all_geometries,
            _base_color,
            _camera_intrinsics,
            _cross,
            _descriptor_for_track,
            _light_direction_from_lighting,
            _lighting_float,
            _material,
            _normalize_depth,
            _shade_color,
            _sub,
            _track_lighting,
            _transform_vertices,
            _project,
        )
        from app.ar_pbr.placement import resolve_track_placement
        from app.ar_pbr.texture_plan import (
            material_base_color_factor,
            material_base_texture_color,
            material_base_texture_path,
            resolve_material_texture_plan,
        )
    except Exception as exc:
        diagnostics["ok"] = False
        diagnostics["fallback"] = True
        diagnostics["errors"].append(f"gpu packet builder import failed: {type(exc).__name__}: {exc}")
        return [], diagnostics

    depth = _normalize_depth(depth_frame, width, height) if depth_frame is not None else None
    max_tris = _max_triangles(settings_map)
    diagnostics["triangle_limit"] = max_tris
    remaining = max_tris
    items: list[dict[str, Any]] = []
    rendered_tracks = 0
    total_triangles = 0

    for track in active:
        if remaining <= 0:
            diagnostics["warnings"].append("gpu triangle limit reached")
            break
        candidate_solution = track.get("camera_solution") if isinstance(track.get("camera_solution"), Mapping) else None
        track_camera_solution = candidate_solution if isinstance(candidate_solution, Mapping) and candidate_solution.get("plane") else camera_solution
        try:
            track, placement_diag = resolve_track_placement(
                track,
                track_camera_solution,
                frame_size=(width, height),
                settings=settings_map,
            )
        except Exception as exc:
            placement_diag = {
                "ok": False,
                "applied": False,
                "track_id": str(track.get("id") or ""),
                "warnings": [f"placement resolve failed: {type(exc).__name__}: {exc}"],
            }
        diagnostics["placements"].append(placement_diag)
        if placement_diag.get("applied"):
            diagnostics["placement_applied_count"] += 1
        fx, fy, cx, cy = _camera_intrinsics(track_camera_solution, width, height)
        descriptor = _descriptor_for_track(track, settings_map)
        render_profile, render_profiles, render_profile_warning = _active_render_profile(track, settings_map, descriptor)
        if render_profile_warning:
            diagnostics["warnings"].append(render_profile_warning)
        if _track_is_pending(descriptor):
            diagnostics["warnings"].append(
                f"{track.get('id') or track.get('asset_path') or 'track'} descriptor is {descriptor.get('import_state')}"
            )
            diagnostics["pending_track_count"] = int(diagnostics.get("pending_track_count", 0) or 0) + 1
            continue
        try:
            texture_plan, texture_diag = resolve_material_texture_plan(track.get("asset_path"), descriptor)
        except Exception as exc:
            texture_plan = {}
            texture_diag = {
                "status": "error",
                "map_count": 0,
                "planned_material_count": 0,
                "missing_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
            }
            diagnostics["warnings"].append(f"texture plan unavailable: {texture_diag['error']}")
        texture_status = str(texture_diag.get("status") or "none")
        status_counts = diagnostics["texture_map_status_counts"]
        status_counts[texture_status] = int(status_counts.get(texture_status, 0) or 0) + 1
        diagnostics["texture_map_count"] += int(texture_diag.get("map_count", 0) or 0)
        diagnostics["texture_material_count"] += int(texture_diag.get("planned_material_count", 0) or 0)
        diagnostics["texture_missing_count"] += int(texture_diag.get("missing_count", 0) or 0)
        if texture_status == "missing":
            diagnostics["warnings"].append(
                f"{track.get('id') or track.get('asset_path') or 'track'} has missing material texture maps"
            )
        geometries = _all_geometries(descriptor)
        scene_bounds = descriptor.get("bounds") if isinstance(descriptor.get("bounds"), Mapping) else None
        lighting = _track_lighting(track)
        catcher_settings = normalize_catcher_settings(lighting)
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
        post_effects_rendering = _preview_safe_post_effects(
            normalize_post_effects_settings(lighting),
            disable_bloom=preview_disable_bloom,
        )
        lens_effects_rendering = normalize_lens_effects_settings(lighting)
        lens_flare_rendering = normalize_lens_flare_settings(lighting)
        render_passes = normalize_render_pass_settings(lighting)
        motion_blur = merge_motion_blur_settings(settings_map, lighting)
        triplanar_rendering = normalize_triplanar_settings(lighting)
        substrate_rendering = normalize_substrate_settings(lighting)
        shadow_catcher_settings = catcher_settings["shadow_catcher"]
        reflection_catcher_settings = catcher_settings["reflection_catcher"]
        light_dir = _light_direction_from_lighting(lighting, (-0.35, -0.65, -0.72))
        direct_strength = _lighting_float(lighting, "direct_strength", 0.85, lo=0.0, hi=4.0)
        ibl_exposure = _lighting_float(lighting, "ibl_exposure", 1.0, lo=0.0, hi=8.0)
        ibl_rotation = _lighting_float(lighting, "ibl_rotation", 0.0, lo=-1.0, hi=1.0)
        shadow_strength = _lighting_float(lighting, "shadow_strength", 1.0, lo=0.0, hi=1.0)
        shadow_settings = normalize_shadow_settings(lighting)
        shadow_pcf_radius = float(shadow_settings["pcf_radius_texels"])
        self_shadow_strength = _lighting_float(lighting, "self_shadow_strength", 0.45, lo=0.0, hi=1.0)
        shadow_map_size = int(shadow_settings["map_size"])
        shadow_bias = float(shadow_settings["bias"])
        hdri_path = _lighting_hdri_path(lighting)
        mesh_rows: list[tuple[float, list[float]]] = []
        all_projected: list[tuple[float, float, float]] = []
        reflection_rgba = (0.08, 0.10, 0.14, 0.14)
        track_triangles = 0
        track_occluded_triangles = 0
        texture_triangles: list[dict[str, Any]] = []
        pbr_triangles: list[dict[str, Any]] = []
        pbr_roughness_values: list[float] = []
        marmoset_pbr_triangle_count = 0
        vrm_mtoon_triangle_count = 0

        for geometry in geometries:
            if remaining <= 0:
                break
            vertices = _transform_vertices(
                geometry,
                track,
                settings_map,
                scene_bounds,
                descriptor=descriptor,
                time_ms=int(time_ms),
            )
            projected = _project(vertices, fx=fx, fy=fy, cx=cx, cy=cy)
            material = _material(track, descriptor, geometry)
            base_color = _base_color(material)
            texture_color = material_base_texture_color(texture_plan, material, alpha=base_color[3])
            texture_path = material_base_texture_path(texture_plan, material)
            texture_maps = gpu_material_packets.material_texture_maps(texture_plan, material)
            material_substrate = normalize_substrate_settings(lighting, maps=texture_maps)
            if bool(material_substrate.get("enabled")):
                texture_maps = {
                    **texture_maps,
                    "substrate_enabled": "1",
                    "substrate_mode": "slab",
                    "substrate_f90_color": ",".join(str(v) for v in material_substrate.get("f90_color", [])),
                    "substrate_f90_strength": str(material_substrate.get("f90_strength", 1.0)),
                    "substrate_f90_mask_strength": str(material_substrate.get("f90_mask_strength", 1.0)),
                }
                diagnostics["pbr_substrate_material_count"] = int(
                    diagnostics.get("pbr_substrate_material_count", 0) or 0
                ) + 1
            force_marmoset_pbr = render_profile == PROFILE_MARMOSET_PBR and gpu_material_packets.material_has_pbr_data(material)
            is_unlit_material = gpu_material_packets.material_unlit(material) and not force_marmoset_pbr
            is_mtoon_material = render_profile == PROFILE_VRM_MTOON and is_unlit_material
            if is_unlit_material:
                texture_maps = {**texture_maps, "unlit": "1"}
            if is_mtoon_material:
                texture_maps = {**texture_maps, "vrm_mtoon": "1"}
            geometry_uvs = gpu_material_packets.geometry_uvs_for_material(geometry, material)
            uv_transform = gpu_material_packets.material_uv_transform(material)
            triangles = geometry.get("triangles") or []
            if not isinstance(triangles, list):
                continue
            diagnostics["source_triangle_count"] += len(triangles)
            all_projected.extend(projected)
            sampled_triangles = _sample_triangle_rows(triangles, remaining)
            if len(sampled_triangles) < len(triangles):
                diagnostics["sampled_triangle_source_count"] += len(triangles)
                diagnostics["sampled_triangle_count"] += len(sampled_triangles)
            for triangle_index, raw_tri in sampled_triangles:
                if remaining <= 0:
                    break
                if not isinstance(raw_tri, (list, tuple)) or len(raw_tri) < 3:
                    continue
                try:
                    i0, i1, i2 = int(raw_tri[0]), int(raw_tri[1]), int(raw_tri[2])
                    p0, p1, p2 = projected[i0], projected[i1], projected[i2]
                    v0, v1, v2 = vertices[i0], vertices[i1], vertices[i2]
                except Exception:
                    continue
                if _triangle_offscreen([p0, p1, p2], width, height):
                    continue
                avg_x = int(max(0, min(width - 1, round((p0[0] + p1[0] + p2[0]) / 3.0))))
                avg_y = int(max(0, min(height - 1, round((p0[1] + p1[1] + p2[1]) / 3.0))))
                avg_z = max(0.05, (p0[2] + p1[2] + p2[2]) / 3.0)
                tri_uvs = gpu_material_packets.triangle_uvs(
                    geometry,
                    triangle_index,
                    (i0, i1, i2),
                    geometry_uvs,
                    uv_transform,
                )
                has_triangle_uvs = tri_uvs is not None
                will_emit_pbr = has_triangle_uvs and bool(texture_path or texture_maps)
                if depth is not None and bool(track.get("occlusion")):
                    if will_emit_pbr:
                        diagnostics["live_depth_texture_triangle_count"] += 1
                    else:
                        # Coarse center-sample occlusion is retained only for
                        # color-packet fallback meshes. PBR/UV meshes keep the
                        # triangle and let the GL/export depth texture apply
                        # per-fragment occlusion.
                        scene_depth = float(depth[avg_y, avg_x])
                        object_depth = max(0.0, min(1.0, avg_z / max(0.1, _float(settings_map.get("camera_z"), 3.25) * 2.0)))
                        tolerance = max(0.0, _float(settings_map.get("occlusion_tolerance"), 0.02))
                        if scene_depth < object_depth - tolerance:
                            track_occluded_triangles += 1
                            diagnostics["occluded_triangle_count"] += 1
                            continue
                normal = _normalize3(_cross(_sub(v1, v0), _sub(v2, v0)), (0.0, 0.0, 1.0))
                color_for_triangle = texture_color or base_color
                if texture_color is not None:
                    diagnostics["texture_tinted_triangle_count"] += 1
                if is_unlit_material:
                    shaded = color_for_triangle
                else:
                    shaded = _shade_color(
                        color_for_triangle,
                        normal,
                        material,
                        light_dir,
                        direct_strength=direct_strength,
                        ibl_exposure=ibl_exposure,
                    )
                rgba = _shade_tuple_to_floats(shaded)
                reflection_rgba = (
                    max(reflection_rgba[0], rgba[0] * 0.36),
                    max(reflection_rgba[1], rgba[1] * 0.36),
                    max(reflection_rgba[2], rgba[2] * 0.36),
                    0.18,
                )
                row: list[float] = []
                for point in (p0, p1, p2):
                    _extend_ndc_vertex(row, point, width, height, rgba)
                mesh_rows.append((avg_z, row))
                material_packet = gpu_material_packets.build_material_triangle_packets(
                    projected_points=(p0, p1, p2),
                    world_points=(v0, v1, v2),
                    tri_uvs=tri_uvs,
                    normal=normal,
                    material=material,
                    geometry=geometry,
                    texture_path=texture_path,
                    texture_maps=texture_maps,
                    rgba=rgba,
                    width=width,
                    height=height,
                    avg_z=avg_z,
                    pbr_rgba=material_base_color_factor(material),
                    force_marmoset_pbr=force_marmoset_pbr,
                )
                texture_triangle = material_packet.get("texture_triangle")
                if isinstance(texture_triangle, dict):
                    texture_triangles.append(texture_triangle)
                pbr_triangle = material_packet.get("pbr_triangle")
                if isinstance(pbr_triangle, dict):
                    pbr_triangles.append(pbr_triangle)
                if material_packet.get("pbr_roughness") is not None:
                    pbr_roughness_values.append(float(material_packet["pbr_roughness"]))
                if bool(material_packet.get("marmoset_pbr_triangle")):
                    marmoset_pbr_triangle_count += 1
                if is_mtoon_material and pbr_triangle is not None:
                    vrm_mtoon_triangle_count += 1
                track_triangles += 1
                total_triangles += 1
                diagnostics["visible_triangle_count"] += 1
                remaining -= 1

        track_vertices: list[float] = []
        for _z, row in sorted(mesh_rows, key=lambda item: item[0], reverse=True):
            track_vertices.extend(row)

        shadow_vertices: list[float] = []
        reflection_vertices: list[float] = []
        depth_texture = _depth_texture_payload(depth, width, height) if depth is not None and bool(track.get("occlusion")) and pbr_triangles else None
        bounds = _projected_bounds(all_projected)
        if bounds is not None:
            x0, y0, x1, y1 = bounds
            span_x = max(1.0, x1 - x0)
            span_y = max(1.0, y1 - y0)
            if bool(track.get("shadow_catcher")):
                base_alpha = max(0.0, min(1.0, _float(settings_map.get("shadow_alpha"), 72.0) / 255.0))
                shadow_alpha = min(
                    0.42,
                    base_alpha
                    * max(0.0, shadow_strength)
                    * float(shadow_catcher_settings["opacity"]),
                )
                shadow_vertices = _mesh_contact_shadow_vertices(
                    all_projected,
                    x0=x0,
                    y0=y0,
                    y1=y1,
                    span_x=span_x,
                    span_y=span_y,
                    width=width,
                    height=height,
                    light_dir=light_dir,
                    alpha=shadow_alpha,
                    softness=float(shadow_catcher_settings["softness"]),
                    matte_alpha=float(shadow_catcher_settings["matte_alpha"]),
                )
                shadow_vertices.extend(_contact_shadow_vertices(
                    x0=x0,
                    y1=y1,
                    span_x=span_x,
                    span_y=span_y,
                    width=width,
                    height=height,
                    light_dir=light_dir,
                    alpha=shadow_alpha,
                    softness=float(shadow_catcher_settings["softness"]),
                    matte_alpha=float(shadow_catcher_settings["matte_alpha"]),
                ))
            if bool(track.get("reflection_catcher")):
                material_reflection_roughness = (
                    sum(pbr_roughness_values) / max(1, len(pbr_roughness_values))
                    if pbr_roughness_values else 0.45
                )
                reflection_roughness = max(
                    float(reflection_catcher_settings["roughness"]),
                    float(material_reflection_roughness),
                )
                reflection_vertices = _mesh_reflection_catcher_vertices(
                    all_projected,
                    y1=y1,
                    span_y=span_y,
                    width=width,
                    height=height,
                    rgba=reflection_rgba,
                    roughness=reflection_roughness,
                    opacity=float(reflection_catcher_settings["opacity"]),
                    softness=float(reflection_catcher_settings["softness"]),
                    matte_alpha=float(reflection_catcher_settings["matte_alpha"]),
                    contact_strength=float(reflection_catcher_settings["contact_reflection_strength"]),
                )
                reflection_vertices.extend(_reflection_catcher_vertices(
                    x0=x0,
                    y1=y1,
                    span_x=span_x,
                    span_y=span_y,
                    width=width,
                    height=height,
                    rgba=reflection_rgba,
                    roughness=reflection_roughness,
                    opacity=float(reflection_catcher_settings["opacity"]),
                    softness=float(reflection_catcher_settings["softness"]),
                    matte_alpha=float(reflection_catcher_settings["matte_alpha"]),
                    contact_strength=float(reflection_catcher_settings["contact_reflection_strength"]),
                    contact_falloff=float(reflection_catcher_settings["contact_reflection_falloff"]),
                ))

        shadow_triangles = len(shadow_vertices) // 18
        reflection_triangles = len(reflection_vertices) // 18
        diagnostics["shadow_triangle_count"] += shadow_triangles
        diagnostics["reflection_triangle_count"] += reflection_triangles

        if track_vertices or shadow_vertices or reflection_vertices:
            rendered_tracks += 1
            items.append({
                "track_id": str(track.get("id") or ""),
                "asset_path": str(track.get("asset_path") or ""),
                "vertices": track_vertices,
                "shadow_vertices": shadow_vertices,
                "reflection_vertices": reflection_vertices,
                "triangle_count": track_triangles,
                "shadow_triangle_count": shadow_triangles,
                "reflection_triangle_count": reflection_triangles,
                "visible_triangle_count": track_triangles,
                "occluded_triangle_count": track_occluded_triangles,
                "texture_status": texture_status,
                "texture_map_count": int(texture_diag.get("map_count", 0) or 0),
                "texture_material_count": int(texture_diag.get("planned_material_count", 0) or 0),
                "texture_missing_count": int(texture_diag.get("missing_count", 0) or 0),
                "render_profile": render_profile,
                "render_profiles": render_profiles,
                "marmoset_pbr_triangle_count": marmoset_pbr_triangle_count,
                "vrm_mtoon_triangle_count": vrm_mtoon_triangle_count,
                "texture_triangles": [
                    {
                        "z": float(row.get("z", 0.0)),
                        "texture": str(row.get("texture") or ""),
                        "vertices": list(row.get("vertices") or []),
                    }
                    for row in sorted(texture_triangles, key=lambda item: float(item.get("z", 0.0)), reverse=True)
                ],
                "texture_triangle_count": len(texture_triangles),
                "pbr_triangles": [
                    {
                        "z": float(row.get("z", 0.0)),
                        "object_depth": max(
                            0.0,
                            min(
                                1.0,
                                float(row.get("z", 0.0)) / max(
                                    0.1,
                                    _float(settings_map.get("camera_z"), 3.25) * 2.0,
                                ),
                            ),
                        ),
                        "texture": str(row.get("texture") or ""),
                        "material_id": str(row.get("material_id") or row.get("texture") or "material"),
                        "maps": dict(row.get("maps") or {}),
                        "base_color_factor": list(row.get("base_color_factor") or []),
                        "vertices": list(row.get("vertices") or []),
                    }
                    for row in sorted(pbr_triangles, key=lambda item: float(item.get("z", 0.0)), reverse=True)
                ],
                "pbr_triangle_count": len(pbr_triangles),
                "pbr_vertex_stride_floats": PBR_VERTEX_STRIDE_FLOATS,
                "occlusion_enabled": bool(track.get("occlusion")),
                "depth_texture": depth_texture,
                "pbr_depth_occlusion": {
                    "enabled": bool(depth_texture is not None),
                    "mode": "live_depth_texture_fragment" if depth_texture is not None else "none",
                    "tolerance": max(0.0, _float(settings_map.get("occlusion_tolerance"), 0.02)),
                    "edge_glow": dict(depth_edge_glow),
                },
                "pbr_lighting": {
                    "light_dir": [float(light_dir[0]), float(light_dir[1]), float(light_dir[2])],
                    "direct_strength": float(direct_strength),
                    "ibl_exposure": float(ibl_exposure),
                    "ibl_rotation": float(ibl_rotation),
                    "hdri_path": str(hdri_path),
                    "hdri_enabled": bool(hdri_path),
                    "shadow_strength": float(shadow_strength),
                    "shadow_pcf_radius": float(shadow_pcf_radius),
                    "shadow_filter": str(shadow_settings["filter"]),
                    "shadow_light_type": str(shadow_settings["light_type"]),
                    "shadow_pcss_blocker_radius": float(shadow_settings["pcss_blocker_radius_texels"]),
                    "shadow_normal_bias": float(shadow_settings["normal_bias"]),
                    "shadow_spot_inner_angle": float(shadow_settings["spot_inner_angle"]),
                    "shadow_spot_outer_angle": float(shadow_settings["spot_outer_angle"]),
                    "shadow_map_primary": True,
                    "contact_shadow_role": "helper_only",
                    "self_shadow_strength": float(self_shadow_strength),
                    "shadow_map_size": int(shadow_map_size),
                    "shadow_bias": float(shadow_bias),
                    "shadow_catcher_opacity": float(shadow_catcher_settings["opacity"]),
                    "shadow_catcher_softness": float(shadow_catcher_settings["softness"]),
                    "shadow_catcher_matte_alpha": float(shadow_catcher_settings["matte_alpha"]),
                    "reflection_catcher_opacity": float(reflection_catcher_settings["opacity"]),
                    "reflection_catcher_roughness": float(reflection_catcher_settings["roughness"]),
                    "depth_edge_glow_enabled": bool(depth_edge_glow["enabled"]),
                    "depth_edge_glow_strength": float(depth_edge_glow["strength"]),
                    "depth_edge_glow_radius_px": float(depth_edge_glow["radius_px"]),
                    "depth_edge_glow_color": list(depth_edge_glow["color"]),
                    "reflection_catcher_softness": float(reflection_catcher_settings["softness"]),
                    "contact_reflection_strength": float(reflection_catcher_settings["contact_reflection_strength"]),
                    "contact_reflection_falloff": float(reflection_catcher_settings["contact_reflection_falloff"]),
                    "tone_mapping": str(color_management["tone_mapping"]),
                    "tone_mapping_mode": int(color_management["tone_mapping_mode"]),
                    "tone_exposure": float(color_management["tone_exposure"]),
                    "tone_white_balance": float(color_management["tone_white_balance"]),
                    "tone_white_balance_rgb": list(color_management["tone_white_balance_rgb"]),
                    "tone_gamma": float(color_management["tone_gamma"]),
                    "hybrid_render_mode": str(hybrid_rendering["mode"]),
                    "hybrid_accumulation_enabled": bool(hybrid_rendering["enabled"]),
                    "hybrid_accumulation_samples": int(hybrid_rendering["sample_count"]),
                    "hybrid_sample_gain": float(hybrid_rendering["sample_gain"]),
                    "diffuse_gi_strength": float(hybrid_rendering["diffuse_gi_strength"]),
                    "specular_gi_strength": float(hybrid_rendering["specular_gi_strength"]),
                    "denoise_strength": float(hybrid_rendering["denoise_strength"]),
                    "denoise_radius": int(hybrid_rendering["denoise_radius"]),
                    "ray_gi_detail_mode": str(ray_gi_detail["mode"]),
                    "ray_gi_detail_enabled": bool(ray_gi_detail["enabled"]),
                    "ray_gi_max_bounces": int(ray_gi_detail["max_bounces"]),
                    "ray_gi_diffuse_bounces": int(ray_gi_detail["diffuse_bounces"]),
                    "ray_gi_specular_bounces": int(ray_gi_detail["specular_bounces"]),
                    "ray_gi_refraction_bounces": int(ray_gi_detail["refraction_bounces"]),
                    "ray_gi_direct_radiance_clamp": float(ray_gi_detail["direct_radiance_clamp"]),
                    "ray_gi_indirect_radiance_clamp": float(ray_gi_detail["indirect_radiance_clamp"]),
                    "ray_gi_advanced_light_sampling": bool(ray_gi_detail["advanced_light_sampling"]),
                    "ray_gi_light_sampling_mode": str(ray_gi_detail["light_sampling_mode"]),
                    "ray_gi_light_sample_count": int(ray_gi_detail["light_sample_count"]),
                    "ray_gi_environment_sample_count": int(ray_gi_detail["environment_sample_count"]),
                    "ray_gi_mis_enabled": bool(ray_gi_detail["mis_enabled"]),
                    "ray_gi_importance_sampling": bool(ray_gi_detail["importance_sampling"]),
                    "ray_gi_denoise_channels": list(ray_gi_detail["denoise_channels"]),
                    "ray_gi_denoise_beauty": bool(ray_gi_detail["denoise_beauty"]),
                    "ray_gi_denoise_diffuse": bool(ray_gi_detail["denoise_diffuse"]),
                    "ray_gi_denoise_specular": bool(ray_gi_detail["denoise_specular"]),
                    "ray_gi_denoise_transmission": bool(ray_gi_detail["denoise_transmission"]),
                    "ray_gi_denoise_albedo_guided": bool(ray_gi_detail["denoise_albedo_guided"]),
                    "ray_gi_denoise_normal_guided": bool(ray_gi_detail["denoise_normal_guided"]),
                    "ambient_occlusion_mode": str(ambient_occlusion_rendering["mode"]),
                    "ambient_occlusion_enabled": bool(ambient_occlusion_rendering["enabled"]),
                    "ao_strength": float(ambient_occlusion_rendering["strength"]),
                    "ao_radius": float(ambient_occlusion_rendering["radius"]),
                    "ao_distance": float(ambient_occlusion_rendering["distance"]),
                    "ao_color": list(ambient_occlusion_rendering["color"]),
                    "ao_ambient": bool(ambient_occlusion_rendering["ambient"]),
                    "ao_diffuse": bool(ambient_occlusion_rendering["diffuse"]),
                    "ao_specular": bool(ambient_occlusion_rendering["specular"]),
                    "transmission_mode": str(transmission_rendering["mode"]),
                    "transmission_enabled": bool(transmission_rendering["enabled"]),
                    "transmission": float(transmission_rendering["transmission"]),
                    "refraction_strength": float(transmission_rendering["refraction_strength"]),
                    "refraction_depth_px": float(transmission_rendering["refraction_depth_px"]),
                    "ior": float(transmission_rendering["ior"]),
                    "thickness": float(transmission_rendering["thickness"]),
                    "absorption_color": list(transmission_rendering["absorption_color"]),
                    "absorption_distance": float(transmission_rendering["absorption_distance"]),
                    "roughness_blur_strength": float(transmission_rendering["roughness_blur_strength"]),
                    "clearcoat_mode": str(clearcoat_rendering["mode"]),
                    "clearcoat_enabled": bool(clearcoat_rendering["enabled"]),
                    "clearcoat_strength": float(clearcoat_rendering["strength"]),
                    "clearcoat_roughness": float(clearcoat_rendering["roughness"]),
                    "clearcoat_ior": float(clearcoat_rendering["ior"]),
                    "clearcoat_tint": list(clearcoat_rendering["tint"]),
                    "parallax_mode": str(parallax_rendering["mode"]),
                    "parallax_enabled": bool(parallax_rendering["enabled"]),
                    "parallax_strength": float(parallax_rendering["strength"]),
                    "parallax_depth": float(parallax_rendering["depth"]),
                    "parallax_center": float(parallax_rendering["center"]),
                    "parallax_steps": int(parallax_rendering["steps"]),
                    "displacement_mode": str(displacement_rendering["mode"]),
                    "displacement_enabled": bool(displacement_rendering["enabled"]),
                    "displacement_height_strength": float(displacement_rendering["height_strength"]),
                    "displacement_height_scale": float(displacement_rendering["height_scale"]),
                    "displacement_height_center": float(displacement_rendering["height_center"]),
                    "vector_displacement_strength": float(displacement_rendering["vector_strength"]),
                    "vector_displacement_space": str(displacement_rendering["vector_space"]),
                    "displacement_subdivision_mode": str(displacement_rendering["subdivision_mode"]),
                    "displacement_max_offset": float(displacement_rendering["max_offset"]),
                    "displacement_parallax_fallback": bool(displacement_rendering["parallax_fallback"]),
                    "bevel_mode": str(bevel_rendering["mode"]),
                    "bevel_enabled": bool(bevel_rendering["enabled"]),
                    "bevel_strength": float(bevel_rendering["strength"]),
                    "bevel_radius": float(bevel_rendering["radius"]),
                    "bevel_edge_width": float(bevel_rendering["edge_width"]),
                    "bevel_samples": int(bevel_rendering["samples"]),
                    "material_layer_mode": str(material_layering["mode"]),
                    "material_layer_enabled": bool(material_layering["enabled"]),
                    "material_layer_blend": float(material_layering["blend"]),
                    "material_layer_color": list(material_layering["color"]),
                    "material_layer_roughness": float(material_layering["roughness"]),
                    "material_layer_metallic": float(material_layering["metallic"]),
                    "material_layer_alpha": float(material_layering["alpha"]),
                    "material_layer_emissive_strength": float(material_layering["emissive_strength"]),
                    "material_layer_mask_strength": float(material_layering["mask_strength"]),
                    "surface_override_strength": float(surface_rendering["override_strength"]),
                    "surface_roughness": float(surface_rendering["roughness"]),
                    "surface_metallic": float(surface_rendering["metallic"]),
                    "surface_reflectance": float(surface_rendering["reflectance"]),
                    "substrate_enabled": bool(substrate_rendering["enabled"]),
                    "substrate_mode": str(substrate_rendering["mode"]),
                    "substrate_f90_color": list(substrate_rendering["f90_color"]),
                    "substrate_f90_strength": float(substrate_rendering["f90_strength"]),
                    "substrate_f90_mask_strength": float(substrate_rendering["f90_mask_strength"]),
                    "subsurface_mode": str(subsurface_rendering["mode"]),
                    "subsurface_enabled": bool(subsurface_rendering["enabled"]),
                    "subsurface_strength": float(subsurface_rendering["strength"]),
                    "subsurface_color": list(subsurface_rendering["color"]),
                    "subsurface_radius": float(subsurface_rendering["radius"]),
                    "subsurface_power": float(subsurface_rendering["power"]),
                    "subsurface_wrap": float(subsurface_rendering["wrap"]),
                    "subsurface_thickness": float(subsurface_rendering["thickness"]),
                    "hair_groom_mode": str(hair_groom_rendering["mode"]),
                    "hair_groom_enabled": bool(hair_groom_rendering["enabled"]),
                    "hair_groom_strength": float(hair_groom_rendering["strength"]),
                    "hair_groom_tint": list(hair_groom_rendering["tint"]),
                    "hair_primary_shift": float(hair_groom_rendering["primary_shift"]),
                    "hair_secondary_shift": float(hair_groom_rendering["secondary_shift"]),
                    "hair_primary_roughness": float(hair_groom_rendering["primary_roughness"]),
                    "hair_secondary_roughness": float(hair_groom_rendering["secondary_roughness"]),
                    "hair_secondary_strength": float(hair_groom_rendering["secondary_strength"]),
                    "hair_anisotropy": float(hair_groom_rendering["anisotropy"]),
                    "hair_rim_strength": float(hair_groom_rendering["rim_strength"]),
                    "cloth_sheen_mode": str(cloth_sheen_rendering["mode"]),
                    "cloth_sheen_enabled": bool(cloth_sheen_rendering["enabled"]),
                    "cloth_sheen_strength": float(cloth_sheen_rendering["strength"]),
                    "cloth_sheen_color": list(cloth_sheen_rendering["color"]),
                    "cloth_sheen_roughness": float(cloth_sheen_rendering["roughness"]),
                    "cloth_sheen_edge_tint": list(cloth_sheen_rendering["edge_tint"]),
                    "cloth_sheen_fiber_strength": float(cloth_sheen_rendering["fiber_strength"]),
                    "cloth_sheen_wrap": float(cloth_sheen_rendering["wrap"]),
                    "cloth_sheen_retroreflection": float(cloth_sheen_rendering["retroreflection"]),
                    "glint_mode": str(glint_sparkle_rendering["mode"]),
                    "glint_enabled": bool(glint_sparkle_rendering["enabled"]),
                    "glint_strength": float(glint_sparkle_rendering["strength"]),
                    "glint_color": list(glint_sparkle_rendering["color"]),
                    "glint_density": float(glint_sparkle_rendering["density"]),
                    "glint_scale": float(glint_sparkle_rendering["scale"]),
                    "glint_threshold": float(glint_sparkle_rendering["threshold"]),
                    "glint_sharpness": float(glint_sparkle_rendering["sharpness"]),
                    "glint_roughness_jitter": float(glint_sparkle_rendering["roughness_jitter"]),
                    "caustics_mode": str(caustics_rendering["mode"]),
                    "caustics_enabled": bool(caustics_rendering["enabled"]),
                    "caustics_strength": float(caustics_rendering["strength"]),
                    "caustics_quality": str(caustics_rendering["quality"]),
                    "caustics_sample_count": int(caustics_rendering["sample_count"]),
                    "caustics_scale": float(caustics_rendering["scale"]),
                    "caustics_focus": float(caustics_rendering["focus"]),
                    "caustics_radius": float(caustics_rendering["radius"]),
                    "caustics_threshold": float(caustics_rendering["threshold"]),
                    "caustics_tint": list(caustics_rendering["tint"]),
                    "caustics_seed": int(caustics_rendering["seed"]),
                    "anisotropic_mode": str(anisotropic_rendering["mode"]),
                    "anisotropic_enabled": bool(anisotropic_rendering["enabled"]),
                    "anisotropic_strength": float(anisotropic_rendering["strength"]),
                    "anisotropy": float(anisotropic_rendering["anisotropy"]),
                    "anisotropic_rotation": float(anisotropic_rendering["rotation"]),
                    "anisotropic_tangent_weight": float(anisotropic_rendering["tangent_weight"]),
                    "clearcoat_anisotropy": float(anisotropic_rendering["clearcoat_anisotropy"]),
                    "thin_film_enabled": bool(anisotropic_rendering["thin_film_enabled"]),
                    "thin_film_strength": float(anisotropic_rendering["thin_film_strength"]),
                    "thin_film_thickness_nm": float(anisotropic_rendering["thin_film_thickness_nm"]),
                    "thin_film_ior": float(anisotropic_rendering["thin_film_ior"]),
                    "thin_film_tint": list(anisotropic_rendering["thin_film_tint"]),
                    "newton_rings_strength": float(anisotropic_rendering["newton_rings_strength"]),
                    "newton_rings_scale": float(anisotropic_rendering["newton_rings_scale"]),
                    "anisotropic_seed": int(anisotropic_rendering["seed"]),
                    "microsurface_mode": str(microsurface_rendering["mode"]),
                    "microsurface_enabled": bool(microsurface_rendering["enabled"]),
                    "detail_normal_enabled": bool(microsurface_rendering["detail_normal_enabled"]),
                    "detail_normal_strength": float(microsurface_rendering["detail_normal_strength"]),
                    "detail_normal_scale": float(microsurface_rendering["detail_normal_scale"]),
                    "detail_normal_blend": str(microsurface_rendering["detail_normal_blend"]),
                    "detail_normal_seed": int(microsurface_rendering["detail_normal_seed"]),
                    "micro_roughness_enabled": bool(microsurface_rendering["micro_roughness_enabled"]),
                    "micro_roughness_strength": float(microsurface_rendering["micro_roughness_strength"]),
                    "micro_roughness_scale": float(microsurface_rendering["micro_roughness_scale"]),
                    "micro_roughness_contrast": float(microsurface_rendering["micro_roughness_contrast"]),
                    "gloss_variation_strength": float(microsurface_rendering["gloss_variation_strength"]),
                    "gloss_bias": float(microsurface_rendering["gloss_bias"]),
                    "specular_micro_occlusion": float(microsurface_rendering["specular_micro_occlusion"]),
                    "depth_of_field_mode": str(depth_of_field_rendering["mode"]),
                    "depth_of_field_enabled": bool(depth_of_field_rendering["enabled"]),
                    "depth_of_field_strength": float(depth_of_field_rendering["strength"]),
                    "dof_focus_depth": float(depth_of_field_rendering["focus_depth"]),
                    "dof_focus_range": float(depth_of_field_rendering["focus_range"]),
                    "dof_max_blur_px": float(depth_of_field_rendering["max_blur_px"]),
                    "dof_near_blur": float(depth_of_field_rendering["near_blur"]),
                    "dof_far_blur": float(depth_of_field_rendering["far_blur"]),
                    "dof_bokeh_shape": str(depth_of_field_rendering["bokeh_shape"]),
                    "post_effects_mode": str(post_effects_rendering["mode"]),
                    "post_effects_enabled": bool(post_effects_rendering["enabled"]),
                    "bloom_enabled": bool(post_effects_rendering["bloom_enabled"]),
                    "bloom_strength": float(post_effects_rendering["bloom_strength"]),
                    "bloom_radius": float(post_effects_rendering["bloom_radius"]),
                    "bloom_threshold": float(post_effects_rendering["bloom_threshold"]),
                    "bloom_method": str(post_effects_rendering["bloom_method"]),
                    "bloom_kernel": str(post_effects_rendering["bloom_kernel"]),
                    "bloom_convolution_scale": float(post_effects_rendering["bloom_convolution_scale"]),
                    "bloom_scatter": float(post_effects_rendering["bloom_scatter"]),
                    "bloom_boost": float(post_effects_rendering["bloom_boost"]),
                    "vignette_enabled": bool(post_effects_rendering["vignette_enabled"]),
                    "vignette_strength": float(post_effects_rendering["vignette_strength"]),
                    "vignette_radius": float(post_effects_rendering["vignette_radius"]),
                    "vignette_feather": float(post_effects_rendering["vignette_feather"]),
                    "grain_enabled": bool(post_effects_rendering["grain_enabled"]),
                    "grain_strength": float(post_effects_rendering["grain_strength"]),
                    "grain_scale": float(post_effects_rendering["grain_scale"]),
                    "grain_seed": int(post_effects_rendering["grain_seed"]),
                    "sharpen_enabled": bool(post_effects_rendering["sharpen_enabled"]),
                    "sharpen_strength": float(post_effects_rendering["sharpen_strength"]),
                    "sharpen_radius": float(post_effects_rendering["sharpen_radius"]),
                    "lens_effects_mode": str(lens_effects_rendering["mode"]),
                    "lens_effects_enabled": bool(lens_effects_rendering["enabled"]),
                    "lens_distortion_enabled": bool(lens_effects_rendering["distortion_enabled"]),
                    "lens_distortion_strength": float(lens_effects_rendering["distortion_strength"]),
                    "lens_distortion_k1": float(lens_effects_rendering["distortion_k1"]),
                    "lens_distortion_k2": float(lens_effects_rendering["distortion_k2"]),
                    "chromatic_aberration_enabled": bool(lens_effects_rendering["chromatic_aberration_enabled"]),
                    "chromatic_aberration_strength": float(lens_effects_rendering["chromatic_aberration_strength"]),
                    "chromatic_aberration_px": float(lens_effects_rendering["chromatic_aberration_px"]),
                    "lens_center": list(lens_effects_rendering["center"]),
                    "lens_edge_falloff": float(lens_effects_rendering["edge_falloff"]),
                    "lens_flare_mode": str(lens_flare_rendering["mode"]),
                    "lens_flare_enabled": bool(lens_flare_rendering["enabled"]),
                    "lens_flare_strength": float(lens_flare_rendering["flare_strength"]),
                    "lens_flare_threshold": float(lens_flare_rendering["flare_threshold"]),
                    "lens_flare_radius": float(lens_flare_rendering["flare_radius"]),
                    "lens_flare_ghost_count": int(lens_flare_rendering["ghost_count"]),
                    "lens_flare_ghost_spacing": float(lens_flare_rendering["ghost_spacing"]),
                    "lens_flare_tint": list(lens_flare_rendering["flare_tint"]),
                    "aperture_flare_enabled": bool(lens_flare_rendering["aperture_flare_enabled"]),
                    "aperture_flare_strength": float(lens_flare_rendering["aperture_flare_strength"]),
                    "aperture_flare_blades": int(lens_flare_rendering["aperture_blades"]),
                    "aperture_flare_rotation_deg": float(lens_flare_rendering["aperture_rotation_deg"]),
                    "aperture_flare_radius": float(lens_flare_rendering["aperture_flare_radius"]),
                    "lens_dirt_enabled": bool(lens_flare_rendering["lens_dirt_enabled"]),
                    "lens_dirt_strength": float(lens_flare_rendering["lens_dirt_strength"]),
                    "lens_dirt_density": float(lens_flare_rendering["lens_dirt_density"]),
                    "lens_dirt_scale": float(lens_flare_rendering["lens_dirt_scale"]),
                    "lens_scratch_enabled": bool(lens_flare_rendering["lens_scratch_enabled"]),
                    "lens_scratch_strength": float(lens_flare_rendering["lens_scratch_strength"]),
                    "lens_scratch_density": float(lens_flare_rendering["lens_scratch_density"]),
                    "lens_scratch_length": float(lens_flare_rendering["lens_scratch_length"]),
                    "lens_flare_seed": int(lens_flare_rendering["seed"]),
                    "render_passes_enabled": bool(render_passes["enabled"]),
                    "render_pass_names": list(render_passes["passes"]),
                    "render_pass_output_dir": str(render_passes["output_dir"]),
                    "render_pass_format": str(render_passes["format"]),
                    "motion_blur_mode": str(motion_blur["mode"]),
                    "motion_blur_enabled": bool(motion_blur["enabled"]),
                    "motion_blur_samples": int(motion_blur["sample_count"]),
                    "motion_blur_shutter_angle": float(motion_blur["shutter_angle"]),
                    "motion_blur_shutter_fraction": float(motion_blur["shutter_fraction"]),
                    "motion_blur_shutter_ms": float(motion_blur["shutter_ms"]),
                    "motion_blur_frame_duration_ms": float(motion_blur["frame_duration_ms"]),
                    "motion_blur_strength": float(motion_blur["strength"]),
                    "camera_motion_px": list(motion_blur["camera_motion_px"]),
                    "triplanar_mode": str(triplanar_rendering["mode"]),
                    "triplanar_enabled": bool(triplanar_rendering["enabled"]),
                    "triplanar_strength": float(triplanar_rendering["strength"]),
                    "triplanar_scale": float(triplanar_rendering["scale"]),
                    "triplanar_blend_sharpness": float(triplanar_rendering["blend_sharpness"]),
                    "triplanar_offset": list(triplanar_rendering["offset"]),
                    "triplanar_space": str(triplanar_rendering["space"]),
                },
                "catcher": catcher_settings,
                "color_management": color_management,
                "hybrid_rendering": hybrid_rendering,
                "ray_gi_detail": ray_gi_detail,
                "ambient_occlusion_rendering": ambient_occlusion_rendering,
                "transmission_rendering": transmission_rendering,
                "clearcoat_rendering": clearcoat_rendering,
                "parallax_rendering": parallax_rendering,
                "displacement_rendering": displacement_rendering,
                "bevel_rendering": bevel_rendering,
                "material_layering": material_layering,
                "subsurface_rendering": subsurface_rendering,
                "substrate_rendering": substrate_rendering,
                "hair_groom_rendering": hair_groom_rendering,
                "cloth_sheen_rendering": cloth_sheen_rendering,
                "glint_sparkle_rendering": glint_sparkle_rendering,
                "caustics_rendering": caustics_rendering,
                "anisotropic_rendering": anisotropic_rendering,
                "microsurface_rendering": microsurface_rendering,
                "depth_of_field_rendering": depth_of_field_rendering,
                "post_effects_rendering": post_effects_rendering,
                "lens_effects_rendering": lens_effects_rendering,
                "lens_flare_rendering": lens_flare_rendering,
                "render_passes": render_passes,
                "motion_blur": motion_blur,
                "triplanar_rendering": triplanar_rendering,
            })

    diagnostics["rendered_track_count"] = rendered_tracks
    diagnostics["triangle_count"] = total_triangles
    diagnostics["gpu_renderer"]["item_count"] = len(items)
    diagnostics["gpu_renderer"]["triangle_limit"] = max_tris
    status_counts = diagnostics.get("texture_map_status_counts") if isinstance(diagnostics.get("texture_map_status_counts"), dict) else {}
    if int(diagnostics.get("texture_tinted_triangle_count", 0) or 0) > 0:
        diagnostics["gpu_renderer"]["texture_maps"] = "metadata_ready_packet_average_tint"
        diagnostics["gpu_renderer"]["texture_sampling"] = "base_map_average_tint"
    texture_triangle_count = sum(
        int(item.get("texture_triangle_count", 0) or 0)
        for item in items
        if isinstance(item, Mapping)
    )
    diagnostics["texture_triangle_count"] = int(texture_triangle_count)
    pbr_triangle_count = sum(
        int(item.get("pbr_triangle_count", 0) or 0)
        for item in items
        if isinstance(item, Mapping)
    )
    diagnostics["pbr_triangle_count"] = int(pbr_triangle_count)
    marmoset_pbr_triangle_count = sum(
        int(item.get("marmoset_pbr_triangle_count", 0) or 0)
        for item in items
        if isinstance(item, Mapping)
    )
    diagnostics["marmoset_pbr_triangle_count"] = int(marmoset_pbr_triangle_count)
    if marmoset_pbr_triangle_count > 0:
        diagnostics["gpu_renderer"]["render_profile"] = PROFILE_MARMOSET_PBR
        diagnostics["gpu_renderer"]["marmoset_pbr"] = "enabled_for_pbr_materials"
    vrm_mtoon_triangle_count = sum(
        int(item.get("vrm_mtoon_triangle_count", 0) or 0)
        for item in items
        if isinstance(item, Mapping)
    )
    diagnostics["vrm_mtoon_triangle_count"] = int(vrm_mtoon_triangle_count)
    if vrm_mtoon_triangle_count > 0:
        diagnostics["gpu_renderer"]["render_profile"] = PROFILE_VRM_MTOON
        diagnostics["gpu_renderer"]["vrm_mtoon"] = "enabled_for_vrm_mtoon_materials"
    if texture_triangle_count > 0:
        diagnostics["gpu_renderer"]["texture_maps"] = "packet_uv_texture_ready"
        diagnostics["gpu_renderer"]["texture_sampling"] = "export_affine_uv_sampling_preview_average_tint"
    if pbr_triangle_count > 0:
        diagnostics["gpu_renderer"]["pbr_preview"] = "gl_model_view_material_map_pbr_packet_ready"
        diagnostics["gpu_renderer"]["pbr_vertex_stride_floats"] = PBR_VERTEX_STRIDE_FLOATS
        if int(texture_diag.get("udim_tile_count", 0) or 0) > 0:
            diagnostics["gpu_renderer"]["udim"] = "texture_plan_udim_tiles_ready"
            diagnostics["gpu_renderer"]["udim_tile_count"] = int(texture_diag.get("udim_tile_count", 0) or 0)
            diagnostics["gpu_renderer"]["udim_sampling"] = "packet_export_full_tile_lookup_live_primary_tile_preview"
        shadow_filters = [
            str((item.get("pbr_lighting") or {}).get("shadow_filter") or "pcf")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("pbr_lighting"), Mapping)
        ]
        shadow_light_types = [
            str((item.get("pbr_lighting") or {}).get("shadow_light_type") or "directional")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("pbr_lighting"), Mapping)
        ]
        diagnostics["gpu_renderer"]["pbr_self_shadow"] = (
            f"{shadow_filters[0] if shadow_filters else 'pcf'}_shadow_map_packet_ready"
        )
        diagnostics["gpu_renderer"]["shadow_light_type"] = shadow_light_types[0] if shadow_light_types else "directional"
        diagnostics["gpu_renderer"]["contact_shadow_role"] = "helper_only"
        color_management_rows = [
            item.get("color_management")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("color_management"), Mapping)
        ]
        if color_management_rows:
            diagnostics["gpu_renderer"]["color_management"] = str(color_management_rows[0].get("tone_mapping") or "aces")
            diagnostics["gpu_renderer"]["render_pass_safe_color"] = "scene_linear_display_transform_preserve_alpha"
        hybrid_rows = [
            item.get("hybrid_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("hybrid_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in hybrid_rows):
            first_hybrid = next(row for row in hybrid_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["hybrid_rendering"] = str(first_hybrid.get("mode") or "hybrid")
            diagnostics["gpu_renderer"]["hybrid_accumulation_samples"] = int(first_hybrid.get("sample_count", 1) or 1)
            diagnostics["gpu_renderer"]["diffuse_specular_gi"] = "enabled"
            diagnostics["gpu_renderer"]["denoise"] = "alpha_weighted_spatial_blend"
        ray_gi_rows = [
            item.get("ray_gi_detail")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("ray_gi_detail"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in ray_gi_rows):
            first_ray_gi = next(row for row in ray_gi_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["ray_gi_detail"] = str(first_ray_gi.get("mode") or "hybrid")
            diagnostics["gpu_renderer"]["ray_gi_bounces"] = int(first_ray_gi.get("max_bounces", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_diffuse_bounces"] = int(first_ray_gi.get("diffuse_bounces", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_specular_bounces"] = int(first_ray_gi.get("specular_bounces", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_refraction_bounces"] = int(first_ray_gi.get("refraction_bounces", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_light_sampling"] = str(first_ray_gi.get("light_sampling_mode") or "standard")
            diagnostics["gpu_renderer"]["ray_gi_light_samples"] = int(first_ray_gi.get("light_sample_count", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_environment_samples"] = int(first_ray_gi.get("environment_sample_count", 1) or 1)
            diagnostics["gpu_renderer"]["ray_gi_denoise_channels"] = list(first_ray_gi.get("denoise_channels") or [])
            diagnostics["gpu_renderer"]["ray_gi_policy"] = "packet_clamp_and_contract_until_native_ray_hybrid_detail"
        ao_rows = [
            item.get("ambient_occlusion_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("ambient_occlusion_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in ao_rows):
            first_ao = next(row for row in ao_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["ambient_occlusion_rendering"] = str(first_ao.get("mode") or "screen")
            diagnostics["gpu_renderer"]["ambient_occlusion"] = "screen_space_ao_contract"
            diagnostics["gpu_renderer"]["ao_strength"] = float(first_ao.get("strength", 0.0) or 0.0)
        render_pass_rows = [
            item.get("render_passes")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("render_passes"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in render_pass_rows):
            first_passes = next(row for row in render_pass_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["render_passes"] = "packet_render_pass_export_contract"
            diagnostics["gpu_renderer"]["render_pass_count"] = len(list(first_passes.get("passes") or []))
            diagnostics["gpu_renderer"]["render_pass_format"] = str(first_passes.get("format") or "png")
        motion_blur_rows = [
            item.get("motion_blur")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("motion_blur"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in motion_blur_rows):
            first_motion = next(row for row in motion_blur_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["motion_blur"] = "final_export_shutter_sample_contract"
            diagnostics["gpu_renderer"]["motion_blur_samples"] = int(first_motion.get("sample_count", 1) or 1)
            diagnostics["gpu_renderer"]["motion_blur_shutter_ms"] = float(first_motion.get("shutter_ms", 0.0) or 0.0)
            diagnostics["gpu_renderer"]["motion_blur_viewport_policy"] = "single_sample_preview_contract_only"
        transmission_rows = [
            item.get("transmission_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("transmission_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in transmission_rows):
            first_transmission = next(row for row in transmission_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["transmission_rendering"] = str(first_transmission.get("mode") or "transmission")
            diagnostics["gpu_renderer"]["refraction"] = "screen_space_packet_or_refracted_environment"
            diagnostics["gpu_renderer"]["transmission"] = float(first_transmission.get("transmission", 0.0) or 0.0)
        clearcoat_rows = [
            item.get("clearcoat_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("clearcoat_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in clearcoat_rows):
            first_clearcoat = next(row for row in clearcoat_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["clearcoat_rendering"] = str(first_clearcoat.get("mode") or "clearcoat")
            diagnostics["gpu_renderer"]["clearcoat_strength"] = float(first_clearcoat.get("strength", 0.0) or 0.0)
            diagnostics["gpu_renderer"]["clearcoat"] = "secondary_ggx_top_specular_lobe"
        parallax_rows = [
            item.get("parallax_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("parallax_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in parallax_rows):
            first_parallax = next(row for row in parallax_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["parallax_rendering"] = str(first_parallax.get("mode") or "parallax")
            diagnostics["gpu_renderer"]["parallax"] = "height_map_tangent_space_uv_offset"
            diagnostics["gpu_renderer"]["parallax_strength"] = float(first_parallax.get("strength", 0.0) or 0.0)
        displacement_rows = [
            item.get("displacement_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("displacement_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in displacement_rows):
            first_displacement = next(row for row in displacement_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["displacement_rendering"] = str(
                first_displacement.get("mode") or "displacement"
            )
            diagnostics["gpu_renderer"]["displacement"] = "height_vector_geometry_contract_parallax_fallback"
            diagnostics["gpu_renderer"]["displacement_height_scale"] = float(
                first_displacement.get("height_scale", 0.0) or 0.0
            )
            diagnostics["gpu_renderer"]["vector_displacement_strength"] = float(
                first_displacement.get("vector_strength", 0.0) or 0.0
            )
            diagnostics["gpu_renderer"]["displacement_fallback"] = str(
                first_displacement.get("realtime_fallback") or "parallax_mapping"
            )
        bevel_rows = [
            item.get("bevel_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("bevel_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in bevel_rows):
            first_bevel = next(row for row in bevel_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["bevel_rendering"] = str(first_bevel.get("mode") or "bevel")
            diagnostics["gpu_renderer"]["bevel"] = "shader_only_edge_normal_rounding"
            diagnostics["gpu_renderer"]["bevel_strength"] = float(first_bevel.get("strength", 0.0) or 0.0)
        material_layer_rows = [
            item.get("material_layering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("material_layering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in material_layer_rows):
            first_layer = next(row for row in material_layer_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["material_layering"] = str(first_layer.get("mode") or "layered")
            diagnostics["gpu_renderer"]["material_layer"] = "single_overlay_material_layer"
            diagnostics["gpu_renderer"]["material_layer_blend"] = float(first_layer.get("blend", 0.0) or 0.0)
        substrate_rows = [
            item.get("substrate_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("substrate_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in substrate_rows):
            first_substrate = next(row for row in substrate_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["substrate_rendering"] = str(first_substrate.get("mode") or "slab")
            diagnostics["gpu_renderer"]["substrate"] = "substrate_slab_output_match_helper"
            diagnostics["gpu_renderer"]["substrate_helper"] = str(
                first_substrate.get("helper") or "Substrate Metalness-To-DiffuseAlbedo-F0"
            )
            diagnostics["gpu_renderer"]["substrate_f90_strength"] = float(
                first_substrate.get("f90_strength", 1.0) or 1.0
            )
        elif int(diagnostics.get("pbr_substrate_material_count", 0) or 0) > 0:
            diagnostics["gpu_renderer"]["substrate_rendering"] = "slab"
            diagnostics["gpu_renderer"]["substrate"] = "substrate_slab_output_match_helper"
        subsurface_rows = [
            item.get("subsurface_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("subsurface_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in subsurface_rows):
            first_subsurface = next(row for row in subsurface_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["subsurface_rendering"] = str(first_subsurface.get("mode") or "subsurface")
            diagnostics["gpu_renderer"]["subsurface"] = "single_scatter_wrap_diffuse_backscatter"
            diagnostics["gpu_renderer"]["subsurface_strength"] = float(first_subsurface.get("strength", 0.0) or 0.0)
        hair_rows = [
            item.get("hair_groom_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("hair_groom_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in hair_rows):
            first_hair = next(row for row in hair_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["hair_groom_rendering"] = str(first_hair.get("mode") or "hair")
            diagnostics["gpu_renderer"]["hair_groom"] = "dual_lobe_kajiya_kay_anisotropic_specular"
            diagnostics["gpu_renderer"]["hair_groom_strength"] = float(first_hair.get("strength", 0.0) or 0.0)
        cloth_rows = [
            item.get("cloth_sheen_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("cloth_sheen_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in cloth_rows):
            first_cloth = next(row for row in cloth_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["cloth_sheen_rendering"] = str(first_cloth.get("mode") or "sheen")
            diagnostics["gpu_renderer"]["cloth_sheen"] = "charlie_sheen_retroreflection_fabric_fuzz"
            diagnostics["gpu_renderer"]["cloth_sheen_strength"] = float(first_cloth.get("strength", 0.0) or 0.0)
        glint_rows = [
            item.get("glint_sparkle_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("glint_sparkle_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in glint_rows):
            first_glint = next(row for row in glint_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["glint_sparkle_rendering"] = str(first_glint.get("mode") or "sparkle")
            diagnostics["gpu_renderer"]["glint_sparkle"] = "deterministic_microflake_sparkle_specular"
            diagnostics["gpu_renderer"]["glint_strength"] = float(first_glint.get("strength", 0.0) or 0.0)
        caustic_rows = [
            item.get("caustics_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("caustics_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in caustic_rows):
            first_caustics = next(row for row in caustic_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["caustics_rendering"] = str(first_caustics.get("mode") or "caustics")
            diagnostics["gpu_renderer"]["caustics"] = "packet_transmission_specular_highlight_contract"
            diagnostics["gpu_renderer"]["caustics_strength"] = float(first_caustics.get("strength", 0.0) or 0.0)
            diagnostics["gpu_renderer"]["caustics_quality"] = str(first_caustics.get("quality") or "preview")
            diagnostics["gpu_renderer"]["caustics_samples"] = int(first_caustics.get("sample_count", 1) or 1)
        anisotropic_rows = [
            item.get("anisotropic_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("anisotropic_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in anisotropic_rows):
            first_anisotropic = next(row for row in anisotropic_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["anisotropic_rendering"] = str(
                first_anisotropic.get("mode") or "anisotropic"
            )
            diagnostics["gpu_renderer"]["anisotropic_material"] = "anisotropic_ggx_thin_film_packet_contract"
            diagnostics["gpu_renderer"]["anisotropic_strength"] = float(
                first_anisotropic.get("strength", 0.0) or 0.0
            )
            diagnostics["gpu_renderer"]["anisotropy"] = float(first_anisotropic.get("anisotropy", 0.0) or 0.0)
            diagnostics["gpu_renderer"]["thin_film_strength"] = float(
                first_anisotropic.get("thin_film_strength", 0.0) or 0.0
            )
        microsurface_rows = [
            item.get("microsurface_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("microsurface_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in microsurface_rows):
            first_micro = next(row for row in microsurface_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["microsurface_rendering"] = str(
                first_micro.get("mode") or "microsurface"
            )
            diagnostics["gpu_renderer"]["microsurface"] = "detail_normal_and_micro_roughness_packet_contract"
            diagnostics["gpu_renderer"]["detail_normal_strength"] = float(
                first_micro.get("detail_normal_strength", 0.0) or 0.0
            )
            diagnostics["gpu_renderer"]["micro_roughness_strength"] = float(
                first_micro.get("micro_roughness_strength", 0.0) or 0.0
            )
            diagnostics["gpu_renderer"]["gloss_variation_strength"] = float(
                first_micro.get("gloss_variation_strength", 0.0) or 0.0
            )
        dof_rows = [
            item.get("depth_of_field_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("depth_of_field_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in dof_rows):
            first_dof = next(row for row in dof_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["depth_of_field_rendering"] = str(first_dof.get("mode") or "depth_of_field")
            diagnostics["gpu_renderer"]["depth_of_field"] = "depth_banded_overlay_post_blur"
            diagnostics["gpu_renderer"]["dof_max_blur_px"] = float(first_dof.get("max_blur_px", 0.0) or 0.0)
        post_effect_rows = [
            item.get("post_effects_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("post_effects_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in post_effect_rows):
            first_post = next(row for row in post_effect_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["post_effects_rendering"] = str(first_post.get("mode") or "post_effects")
            diagnostics["gpu_renderer"]["bloom"] = "thresholded_convolution_lens_bloom" if first_post.get("bloom_enabled") else "off"
            diagnostics["gpu_renderer"]["vignette"] = "beauty_pass_radial_falloff" if first_post.get("vignette_enabled") else "off"
            diagnostics["gpu_renderer"]["grain"] = "deterministic_film_grain" if first_post.get("grain_enabled") else "off"
            diagnostics["gpu_renderer"]["sharpen"] = "unsharp_mask" if first_post.get("sharpen_enabled") else "off"
        lens_effect_rows = [
            item.get("lens_effects_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("lens_effects_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in lens_effect_rows):
            first_lens = next(row for row in lens_effect_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["lens_effects_rendering"] = str(first_lens.get("mode") or "lens_effects")
            diagnostics["gpu_renderer"]["lens_distortion"] = (
                str(first_lens.get("distortion_type") or "barrel")
                if first_lens.get("distortion_enabled") else "off"
            )
            diagnostics["gpu_renderer"]["chromatic_aberration"] = (
                "radial_rgb_channel_offset" if first_lens.get("chromatic_aberration_enabled") else "off"
            )
            diagnostics["gpu_renderer"]["chromatic_aberration_px"] = float(
                first_lens.get("chromatic_aberration_px", 0.0) or 0.0
            )
        lens_flare_rows = [
            item.get("lens_flare_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("lens_flare_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in lens_flare_rows):
            first_flare = next(row for row in lens_flare_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["lens_flare_rendering"] = str(first_flare.get("mode") or "lens_flare")
            diagnostics["gpu_renderer"]["lens_flare"] = (
                "bright_source_radial_ghosts_and_halo" if first_flare.get("flare_enabled") else "off"
            )
            diagnostics["gpu_renderer"]["aperture_flare"] = (
                "deterministic_multi_blade_star_streak" if first_flare.get("aperture_flare_enabled") else "off"
            )
            diagnostics["gpu_renderer"]["lens_dirt"] = (
                "hash_based_lens_dirt_overlay" if first_flare.get("lens_dirt_enabled") else "off"
            )
            diagnostics["gpu_renderer"]["lens_scratch"] = (
                "hash_based_lens_scratch_overlay" if first_flare.get("lens_scratch_enabled") else "off"
            )
        triplanar_rows = [
            item.get("triplanar_rendering")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("triplanar_rendering"), Mapping)
        ]
        if any(bool(row.get("enabled")) for row in triplanar_rows):
            first_triplanar = next(row for row in triplanar_rows if bool(row.get("enabled")))
            diagnostics["gpu_renderer"]["triplanar_rendering"] = str(first_triplanar.get("mode") or "triplanar")
            diagnostics["gpu_renderer"]["triplanar_projection"] = "normal_weighted_axis_box_projection"
            diagnostics["gpu_renderer"]["triplanar_strength"] = float(first_triplanar.get("strength", 0.0) or 0.0)
            diagnostics["gpu_renderer"]["triplanar_scale"] = float(first_triplanar.get("scale", 1.0) or 1.0)
        diagnostics["gpu_renderer"]["texture_sampling"] = (
            "gl_preview_pbr_triplanar_projection"
            if diagnostics["gpu_renderer"].get("triplanar_rendering")
            else "gl_preview_pbr_texture_export_affine_uv"
        )
        if any(isinstance(item, Mapping) and item.get("depth_texture") is not None for item in items):
            diagnostics["gpu_renderer"]["depth_occlusion"] = "live_depth_texture_fragment"
        edge_glow_rows = [
            (item.get("pbr_depth_occlusion") or {}).get("edge_glow")
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("pbr_depth_occlusion"), Mapping)
        ]
        if any(isinstance(row, Mapping) and bool(row.get("enabled")) for row in edge_glow_rows):
            diagnostics["gpu_renderer"]["depth_edge_glow"] = "depth_boundary_visible_rim"
        if int(diagnostics.get("reflection_triangle_count", 0) or 0) > 0:
            diagnostics["gpu_renderer"]["reflection_quality"] = "roughness_blur_contact_reflection_packet"
    elif int(status_counts.get("ready", 0) or 0) > 0:
        diagnostics["gpu_renderer"]["texture_maps"] = "metadata_ready_packet_sampling_pending"
    elif int(status_counts.get("missing", 0) or 0) > 0:
        diagnostics["gpu_renderer"]["texture_maps"] = "missing"
    elif int(status_counts.get("referenced", 0) or 0) > 0:
        diagnostics["gpu_renderer"]["texture_maps"] = "referenced_unresolved"
    if int(diagnostics.get("reflection_triangle_count", 0) or 0) > 0:
        diagnostics["gpu_renderer"]["reflection_quality"] = "roughness_blur_contact_reflection_packet"
    if not items:
        diagnostics["fallback"] = True
        diagnostics["warnings"].append("no gpu drawable triangles")
    return items, diagnostics
