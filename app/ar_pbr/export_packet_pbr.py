"""PBR triangle rasterization path for AR/PBR export packets."""
from __future__ import annotations

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
from app.ar_pbr.ambient_occlusion import normalize_ambient_occlusion_settings
from app.ar_pbr.depth_occlusion import (
    apply_depth_occlusion_to_alpha,
    apply_depth_edge_glow_to_rgb,
    depth_occlusion_tolerance,
    normalize_depth_edge_glow_settings,
)
from app.ar_pbr.clearcoat import apply_clearcoat_layer, normalize_clearcoat_settings
from app.ar_pbr.cloth import apply_cloth_sheen_shading, normalize_cloth_sheen_settings
from app.ar_pbr.glint import apply_glint_sparkle_shading, normalize_glint_sparkle_settings
from app.ar_pbr.caustics import apply_caustic_highlights, normalize_caustics_settings
from app.ar_pbr.depth_of_field import normalize_depth_of_field_settings
from app.ar_pbr.lens_effects import normalize_lens_effects_settings
from app.ar_pbr.lens_flare import normalize_lens_flare_settings
from app.ar_pbr.bevel import apply_bevel_normal, bevel_edge_mask, normalize_bevel_settings
from app.ar_pbr.displacement import apply_displacement_proxy, normalize_displacement_settings
from app.ar_pbr.hybrid_rendering import apply_hybrid_gi, denoise_float_rgb, normalize_hybrid_render_settings
from app.ar_pbr.ray_gi_detail import normalize_ray_gi_detail_settings
from app.ar_pbr.hair import apply_hair_groom_shading, normalize_hair_groom_settings
from app.ar_pbr.material_layering import apply_material_layer, normalize_material_layering_settings
from app.ar_pbr.microsurface import (
    apply_detail_normal_layer,
    apply_microsurface_roughness,
    normalize_microsurface_settings,
)
from app.ar_pbr.parallax import apply_parallax_uv, normalize_parallax_settings
from app.ar_pbr.subsurface import apply_subsurface_scattering, normalize_subsurface_settings
from app.ar_pbr.surface import normalize_surface_settings
from app.ar_pbr.tone_mapping import apply_display_transform, normalize_color_management_settings
from app.ar_pbr.transmission import apply_screen_space_refraction, normalize_transmission_settings
from app.ar_pbr.triplanar import normalize_triplanar_settings
from app.ar_pbr.export_packet_sampling import (
    _hdri_array,
    _hdri_average_rgb,
    _hdri_prefilter_levels,
    _load_ibl_probe,
    _map_channel,
    _map_float,
    _map_vec3,
    _normalize_vec3_array,
    _record_triplanar_sampling,
    _record_udim_sampling,
    _rotate_ibl_direction,
    _sample_hdri_direction,
    _sample_hdri_prefiltered,
    _sample_texture_channel,
    _sample_texture_projected,
    _texture_array,
    _texture_udim_arrays,
)


_LEGACY_PBR_VERTEX_STRIDE_FLOATS = 20
_PBR_VERTEX_STRIDE_FLOATS = 23


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
            base_factor = np.dstack((
                np.clip(interp(13), 0.0, 16.0),
                np.clip(interp(14), 0.0, 16.0),
                np.clip(interp(15), 0.0, 16.0),
            )).astype(np.float32)
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
                albedo = srgb_to_linear(base[:, :, :3]) * base_factor
                alpha = np.clip(base[:, :, 3] * interp(16), 0.0, 1.0) * mask.astype(np.float32)
                if bool(np.any(np.abs(base_factor - 1.0) > 1.0e-4)):
                    diagnostics["pbr_base_color_factor_applied"] = True
                    diagnostics["pbr_base_color_factor_pixels"] = int(
                        diagnostics.get("pbr_base_color_factor_pixels", 0) or 0
                    ) + int((alpha > 0.001).sum())
            else:
                vertex_rgb = np.clip(base_factor, 0.0, 1.0)
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
