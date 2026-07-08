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

from app.ar_pbr.ambient_occlusion import (
    apply_screen_ambient_occlusion_to_overlay,
    normalize_packet_ambient_occlusion_settings,
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
from app.ar_pbr.export_packet_sampling import (
    _HDRI_ARRAY_CACHE,
    _HDRI_AVERAGE_CACHE,
    _HDRI_PREFILTER_CACHE,
    _TEXTURE_ARRAY_CACHE,
    _TEXTURE_AVERAGE_CACHE,
    _TEXTURE_CACHE,
    _depth_array,
    _hdri_array,
    _hdri_average_rgb,
    _hdri_prefilter_levels,
    _load_ibl_probe,
    _load_texture,
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
    _texture_average_rgb,
    _texture_rows,
    _texture_udim_arrays,
)

from app.ar_pbr.export_packet_pbr import (
    _LEGACY_PBR_VERTEX_STRIDE_FLOATS,
    _PBR_VERTEX_STRIDE_FLOATS,
    _draw_pbr_triangles,
    _pbr_rows,
    _pbr_vertex_stride,
)


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
