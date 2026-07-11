"""Worker-safe AR/PBR model-view GPU export helper.

This helper is intentionally a separate process: VideoExportThread calls it
through ``app.ar_pbr.full_gpu_export_service`` instead of creating Qt/OpenGL
objects inside the export worker.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


_GPU_WIDGET_CACHE: dict[tuple[Any, ...], dict[str, Any]] = {}


def _ensure_service_gl_defaults() -> None:
    if os.name == "nt":
        # The export helper renders through the same PyOpenGL model-view path
        # as the interactive preview.  On Windows, Qt's non-desktop defaults
        # can create a QOpenGLWidget surface that fails at glViewport.
        os.environ.setdefault("QT_OPENGL", "desktop")


def _write_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(dict(payload), ensure_ascii=False, default=str), flush=True)


def _load_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _serve_stdio() -> int:
    """Serve repeated render requests on stdin/stdout.

    Each input line is either a full request object or
    ``{"request_path": "..."}``.  Keeping this process alive avoids paying the
    Python/Qt/OpenGL import and QApplication startup cost for every preview
    frame.  The render path still owns per-request widget/FBO work.
    """
    for line in sys.stdin:
        text = str(line or "").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
            if not isinstance(payload, dict):
                payload = {}
            request_path = payload.get("request_path") or payload.get("request")
            request = _load_json(request_path) if request_path else payload
            result = render_request(request)
        except Exception as exc:
            result = {
                "ok": False,
                "mode": "full_model_view_gpu_export_service",
                "persistent_service": True,
                "error": f"{type(exc).__name__}: {exc}",
            }
        result = dict(result or {})
        result["persistent_service"] = True
        _write_json(result)
    return 0


def _resolve_descriptor(track: Mapping[str, Any], settings: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    descriptors = settings.get("asset_descriptors") if isinstance(settings.get("asset_descriptors"), Mapping) else {}
    keys = [
        str(track.get("id") or ""),
        str(track.get("asset_path") or ""),
        str(track.get("asset_id") or ""),
    ]
    for key in keys:
        descriptor = descriptors.get(key) if isinstance(descriptors, Mapping) else None
        if isinstance(descriptor, Mapping) and descriptor:
            return dict(descriptor), {"source": "request_asset_descriptors", "key": key}
    asset_path = str(track.get("asset_path") or "").strip()
    if not asset_path:
        return {}, {"source": "none", "error": "track_asset_path_missing"}
    from app.ar_pbr.importer import import_asset

    descriptor, diag = import_asset(Path(asset_path), settings={"max_triangles_per_geometry": 2_000_000})
    return dict(descriptor or {}), {"source": "import_asset", "asset_path": asset_path, "import": diag}


def _track_rect(track: Mapping[str, Any], width: int, height: int) -> tuple[int, int, int, int, float]:
    from app.ar_pbr.compositor import _screen_rect

    return _screen_rect(track, width, height)


def _load_depth_frame_payload(payload: Any, width: int, height: int):
    if payload is None:
        return None
    try:
        import numpy as np
        from PIL import Image
        from app.ar_pbr.depth_occlusion import normalize_depth_frame

        source = payload
        if isinstance(payload, Mapping):
            inline = payload.get("data")
            if inline is not None:
                return normalize_depth_frame(inline, width, height)
            source = payload.get("path")
        if isinstance(source, (str, Path)):
            path = Path(str(source))
            if not path.is_file():
                return None
            if path.suffix.lower() == ".npy":
                return normalize_depth_frame(np.load(path), width, height)
            return normalize_depth_frame(Image.open(path), width, height)
        return normalize_depth_frame(source, width, height)
    except Exception:
        return None


def _apply_depth_occlusion_to_overlay(
    overlay: Any,
    *,
    depth_frame: Any,
    rect: tuple[int, int, int, int],
    object_depth: float,
    settings: Mapping[str, Any],
) -> tuple[Any, dict[str, Any]]:
    if depth_frame is None:
        return overlay, {"enabled": False, "applied": False, "occluded_pixels": 0}
    try:
        import numpy as np
        from PIL import Image
        from app.ar_pbr.depth_occlusion import apply_depth_occlusion_to_alpha

        x0, y0, x1, y1 = rect
        if x1 <= x0 or y1 <= y0:
            return overlay, {"enabled": True, "applied": False, "occluded_pixels": 0, "reason": "empty_rect"}
        depth_patch = depth_frame[y0:y1, x0:x1]
        if depth_patch.shape[:2] != (overlay.size[1], overlay.size[0]):
            depth_patch = np.asarray(
                Image.fromarray(depth_patch.astype(np.float32), mode="F").resize(
                    overlay.size,
                    Image.Resampling.BILINEAR,
                ),
                dtype=np.float32,
            )
        arr = np.asarray(overlay.convert("RGBA"), dtype=np.uint8).copy()
        alpha, diag = apply_depth_occlusion_to_alpha(
            arr[:, :, 3],
            depth_patch,
            object_depth=float(object_depth),
            settings=settings,
        )
        arr[:, :, 3] = alpha
        return Image.fromarray(arr, "RGBA"), dict(diag)
    except Exception as exc:
        return overlay, {
            "enabled": True,
            "applied": False,
            "occluded_pixels": 0,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _lighting(track: Mapping[str, Any], settings: Mapping[str, Any]) -> dict[str, Any]:
    render = track.get("render") if isinstance(track.get("render"), Mapping) else {}
    lighting = render.get("lighting") if isinstance(render.get("lighting"), Mapping) else {}
    if not lighting:
        lighting = settings.get("lighting") if isinstance(settings.get("lighting"), Mapping) else {}
    return dict(lighting or {})


def _model_view_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    raw = settings.get("model_view") if isinstance(settings.get("model_view"), Mapping) else {}
    return dict(raw or {})


def _float_setting(settings: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(settings.get(key, default))
    except Exception:
        return float(default)


def _bool_setting(settings: Mapping[str, Any], key: str, default: bool) -> bool:
    raw = settings.get(key)
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return bool(default)
    return str(raw).strip().casefold() not in {"0", "false", "no", "off", "disabled"}


def _render_track_overlay(
    *,
    app,
    track: Mapping[str, Any],
    descriptor: Mapping[str, Any],
    time_ms: int,
    rect_size: tuple[int, int],
    settings: Mapping[str, Any],
    temp_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QWidget
    from tools.ar_pbr_gpu_window import (
        DEFAULT_FRAME_FIT_PADDING,
        DEFAULT_HDRI,
        GpuMeshWidget,
        GpuState,
        DEFAULT_SHADOW_PCF_RADIUS,
        _load_hdri_or_none,
        _resolve_material_texture_plan,
        ambient_occlusion_diagnostics,
        anisotropic_material_diagnostics,
        bevel_diagnostics,
        catcher_diagnostics,
        clearcoat_diagnostics,
        cloth_sheen_diagnostics,
        color_management_diagnostics,
        caustics_diagnostics,
        depth_of_field_diagnostics,
        glint_sparkle_diagnostics,
        hybrid_rendering_diagnostics,
        ray_gi_detail_diagnostics,
        material_layering_diagnostics,
        parallax_diagnostics,
        displacement_diagnostics,
        post_effects_diagnostics,
        lens_effects_diagnostics,
        lens_flare_diagnostics,
        microsurface_diagnostics,
        subsurface_diagnostics,
        hair_groom_diagnostics,
        transmission_diagnostics,
        triplanar_diagnostics,
        shadow_filter_diagnostics,
        build_vertex_buffer,
    )
    from app.ar_pbr.bevel import normalize_bevel_settings
    from app.ar_pbr.ambient_occlusion import normalize_ambient_occlusion_settings
    from app.ar_pbr.catcher import normalize_catcher_settings
    from app.ar_pbr.clearcoat import normalize_clearcoat_settings
    from app.ar_pbr.cloth import normalize_cloth_sheen_settings
    from app.ar_pbr.caustics import normalize_caustics_settings
    from app.ar_pbr.anisotropy import normalize_anisotropic_material_settings
    from app.ar_pbr.microsurface import normalize_microsurface_settings
    from app.ar_pbr.depth_of_field import normalize_depth_of_field_settings
    from app.ar_pbr.glint import normalize_glint_sparkle_settings
    from app.ar_pbr.hybrid_rendering import normalize_hybrid_render_settings
    from app.ar_pbr.ray_gi_detail import normalize_ray_gi_detail_settings
    from app.ar_pbr.hair import normalize_hair_groom_settings
    from app.ar_pbr.material_layering import normalize_material_layering_settings
    from app.ar_pbr.parallax import normalize_parallax_settings
    from app.ar_pbr.displacement import normalize_displacement_settings
    from app.ar_pbr.post_effects import normalize_post_effects_settings
    from app.ar_pbr.lens_effects import normalize_lens_effects_settings
    from app.ar_pbr.lens_flare import normalize_lens_flare_settings
    from app.ar_pbr.render_passes import normalize_render_pass_settings
    from app.ar_pbr.motion_blur import merge_motion_blur_settings
    from app.ar_pbr.shadow import normalize_shadow_settings
    from app.ar_pbr.subsurface import normalize_subsurface_settings
    from app.ar_pbr.tone_mapping import normalize_color_management_settings
    from app.ar_pbr.transmission import normalize_transmission_settings
    from app.ar_pbr.triplanar import normalize_triplanar_settings

    width, height = max(2, int(rect_size[0])), max(2, int(rect_size[1]))
    asset = Path(str(track.get("asset_path") or descriptor.get("source_path") or "ar_pbr_asset"))
    timings: dict[str, float] = {}
    stage_start = time.perf_counter()
    vertices, mesh_diag = build_vertex_buffer(descriptor, track=track, time_ms=int(time_ms))
    timings["build_vertex_buffer_s"] = round(time.perf_counter() - stage_start, 4)
    stage_start = time.perf_counter()
    texture_plan, texture_diag = _resolve_material_texture_plan(asset, descriptor)
    timings["texture_plan_s"] = round(time.perf_counter() - stage_start, 4)
    lighting = _lighting(track, settings)
    hdri_path_raw = str(lighting.get("hdri_path") or settings.get("hdri_path") or DEFAULT_HDRI or "").strip()
    stage_start = time.perf_counter()
    hdri, hdri_diag = _load_hdri_or_none(Path(hdri_path_raw) if hdri_path_raw else None)
    timings["hdri_load_s"] = round(time.perf_counter() - stage_start, 4)
    state = GpuState()
    transform = track.get("transform") if isinstance(track.get("transform"), Mapping) else {}
    rotation = transform.get("rotation", []) if isinstance(transform, Mapping) else []
    if isinstance(rotation, (list, tuple)) and len(rotation) >= 3:
        state.pitch = float(rotation[0])
        state.yaw = float(rotation[1])
        state.roll = float(rotation[2])
    state.ibl_exposure = float(lighting.get("ibl_exposure", state.ibl_exposure) or state.ibl_exposure)
    state.ibl_rotation = float(lighting.get("ibl_rotation", state.ibl_rotation) or state.ibl_rotation)
    state.light_azimuth = float(lighting.get("light_azimuth", hdri_diag.get("key_light_azimuth", state.light_azimuth)) or state.light_azimuth)
    state.light_elevation = float(lighting.get("light_elevation", hdri_diag.get("key_light_elevation", state.light_elevation)) or state.light_elevation)
    state.direct_intensity = float(lighting.get("direct_strength", state.direct_intensity) or state.direct_intensity)
    state.shadow_strength = float(lighting.get("shadow_strength", state.shadow_strength) or state.shadow_strength)
    state.self_shadow_strength = max(0.0, min(1.0, float(lighting.get("self_shadow_strength", state.self_shadow_strength) or state.self_shadow_strength)))
    shadow_settings = normalize_shadow_settings(lighting)
    state.shadow_filter = str(shadow_settings["filter"])
    state.shadow_light_type = str(shadow_settings["light_type"])
    state.shadow_pcf_radius = float(shadow_settings["pcf_radius_texels"])
    state.shadow_pcss_blocker_radius = float(shadow_settings["pcss_blocker_radius_texels"])
    state.shadow_bias = float(shadow_settings["bias"])
    state.shadow_normal_bias = float(shadow_settings["normal_bias"])
    state.shadow_spot_inner_angle = float(shadow_settings["spot_inner_angle"])
    state.shadow_spot_outer_angle = float(shadow_settings["spot_outer_angle"])
    catcher_settings = normalize_catcher_settings(lighting)
    state.shadow_catcher_opacity = float(catcher_settings["shadow_catcher"]["opacity"])
    state.shadow_catcher_softness = float(catcher_settings["shadow_catcher"]["softness"])
    state.shadow_catcher_matte_alpha = float(catcher_settings["shadow_catcher"]["matte_alpha"])
    state.reflection_catcher_opacity = float(catcher_settings["reflection_catcher"]["opacity"])
    state.reflection_catcher_roughness = float(catcher_settings["reflection_catcher"]["roughness"])
    state.reflection_catcher_softness = float(catcher_settings["reflection_catcher"]["softness"])
    state.contact_reflection_strength = float(catcher_settings["reflection_catcher"]["contact_reflection_strength"])
    state.contact_reflection_falloff = float(catcher_settings["reflection_catcher"]["contact_reflection_falloff"])
    color_management = normalize_color_management_settings(lighting)
    state.tone_mapping = str(color_management["tone_mapping"])
    state.tone_exposure = float(color_management["tone_exposure"])
    state.tone_white_balance = float(color_management["tone_white_balance"])
    state.tone_gamma = float(color_management["tone_gamma"])
    hybrid_rendering = normalize_hybrid_render_settings(lighting)
    state.hybrid_sample_count = int(hybrid_rendering["sample_count"])
    state.diffuse_gi_strength = float(hybrid_rendering["diffuse_gi_strength"])
    state.specular_gi_strength = float(hybrid_rendering["specular_gi_strength"])
    state.denoise_strength = float(hybrid_rendering["denoise_strength"])
    ray_gi_detail = normalize_ray_gi_detail_settings(lighting)
    state.ray_gi_detail_mode = str(ray_gi_detail["mode"])
    state.ray_gi_max_bounces = int(ray_gi_detail["max_bounces"])
    state.ray_gi_diffuse_bounces = int(ray_gi_detail["diffuse_bounces"])
    state.ray_gi_specular_bounces = int(ray_gi_detail["specular_bounces"])
    state.ray_gi_refraction_bounces = int(ray_gi_detail["refraction_bounces"])
    state.ray_gi_direct_radiance_clamp = float(ray_gi_detail["direct_radiance_clamp"])
    state.ray_gi_indirect_radiance_clamp = float(ray_gi_detail["indirect_radiance_clamp"])
    state.ray_gi_light_sampling_mode = str(ray_gi_detail["light_sampling_mode"])
    state.ray_gi_light_sample_count = int(ray_gi_detail["light_sample_count"])
    state.ray_gi_environment_sample_count = int(ray_gi_detail["environment_sample_count"])
    state.ray_gi_mis_enabled = bool(ray_gi_detail["mis_enabled"])
    state.ray_gi_importance_sampling = bool(ray_gi_detail["importance_sampling"])
    state.ray_gi_denoise_channels = tuple(str(v) for v in ray_gi_detail["denoise_channels"])
    state.ray_gi_denoise_beauty = bool(ray_gi_detail["denoise_beauty"])
    state.ray_gi_denoise_diffuse = bool(ray_gi_detail["denoise_diffuse"])
    state.ray_gi_denoise_specular = bool(ray_gi_detail["denoise_specular"])
    state.ray_gi_denoise_transmission = bool(ray_gi_detail["denoise_transmission"])
    state.ray_gi_denoise_albedo_guided = bool(ray_gi_detail["denoise_albedo_guided"])
    state.ray_gi_denoise_normal_guided = bool(ray_gi_detail["denoise_normal_guided"])
    ambient_occlusion = normalize_ambient_occlusion_settings(lighting)
    state.ambient_occlusion_mode = str(ambient_occlusion["mode"])
    state.ao_strength = float(ambient_occlusion["strength"])
    state.ao_radius = float(ambient_occlusion["radius"])
    state.ao_distance = float(ambient_occlusion["distance"])
    state.ao_color = tuple(float(v) for v in ambient_occlusion["color"])
    state.ao_ambient = bool(ambient_occlusion["ambient"])
    state.ao_diffuse = bool(ambient_occlusion["diffuse"])
    state.ao_specular = bool(ambient_occlusion["specular"])
    transmission = normalize_transmission_settings(lighting)
    state.transmission_mode = str(transmission["mode"])
    state.transmission = float(transmission["transmission"])
    state.refraction_strength = float(transmission["refraction_strength"])
    state.refraction_depth_px = float(transmission["refraction_depth_px"])
    state.ior = float(transmission["ior"])
    state.thickness = float(transmission["thickness"])
    state.absorption_color = tuple(float(v) for v in transmission["absorption_color"])
    state.absorption_distance = float(transmission["absorption_distance"])
    state.roughness_blur_strength = float(transmission["roughness_blur_strength"])
    clearcoat = normalize_clearcoat_settings(lighting)
    state.clearcoat_mode = str(clearcoat["mode"])
    state.clearcoat_strength = float(clearcoat["strength"])
    state.clearcoat_roughness = float(clearcoat["roughness"])
    state.clearcoat_ior = float(clearcoat["ior"])
    state.clearcoat_tint = tuple(float(v) for v in clearcoat["tint"])
    parallax = normalize_parallax_settings(lighting)
    state.parallax_mode = str(parallax["mode"])
    state.parallax_strength = float(parallax["strength"])
    state.parallax_depth = float(parallax["depth"])
    state.parallax_center = float(parallax["center"])
    state.parallax_steps = int(parallax["steps"])
    displacement = normalize_displacement_settings(lighting)
    state.displacement_mode = str(displacement["mode"])
    state.displacement_height_strength = float(displacement["height_strength"])
    state.displacement_height_scale = float(displacement["height_scale"])
    state.displacement_height_center = float(displacement["height_center"])
    state.vector_displacement_strength = float(displacement["vector_strength"])
    state.vector_displacement_space = str(displacement["vector_space"])
    state.displacement_subdivision_mode = str(displacement["subdivision_mode"])
    state.displacement_max_offset = float(displacement["max_offset"])
    state.displacement_parallax_fallback = bool(displacement["parallax_fallback"])
    bevel = normalize_bevel_settings(lighting)
    state.bevel_mode = str(bevel["mode"])
    state.bevel_strength = float(bevel["strength"])
    state.bevel_radius = float(bevel["radius"])
    state.bevel_edge_width = float(bevel["edge_width"])
    state.bevel_samples = int(bevel["samples"])
    material_layering = normalize_material_layering_settings(lighting)
    state.material_layer_mode = str(material_layering["mode"])
    state.material_layer_blend = float(material_layering["blend"])
    state.material_layer_color = tuple(float(v) for v in material_layering["color"])
    state.material_layer_roughness = float(material_layering["roughness"])
    state.material_layer_metallic = float(material_layering["metallic"])
    state.material_layer_alpha = float(material_layering["alpha"])
    state.material_layer_emissive_strength = float(material_layering["emissive_strength"])
    state.material_layer_mask_strength = float(material_layering["mask_strength"])
    subsurface = normalize_subsurface_settings(lighting)
    state.subsurface_mode = str(subsurface["mode"])
    state.subsurface_strength = float(subsurface["strength"])
    state.subsurface_color = tuple(float(v) for v in subsurface["color"])
    state.subsurface_radius = float(subsurface["radius"])
    state.subsurface_power = float(subsurface["power"])
    state.subsurface_wrap = float(subsurface["wrap"])
    state.subsurface_thickness = float(subsurface["thickness"])
    hair_groom = normalize_hair_groom_settings(lighting)
    state.hair_groom_mode = str(hair_groom["mode"])
    state.hair_groom_strength = float(hair_groom["strength"])
    state.hair_groom_tint = tuple(float(v) for v in hair_groom["tint"])
    state.hair_primary_shift = float(hair_groom["primary_shift"])
    state.hair_secondary_shift = float(hair_groom["secondary_shift"])
    state.hair_primary_roughness = float(hair_groom["primary_roughness"])
    state.hair_secondary_roughness = float(hair_groom["secondary_roughness"])
    state.hair_secondary_strength = float(hair_groom["secondary_strength"])
    state.hair_anisotropy = float(hair_groom["anisotropy"])
    state.hair_rim_strength = float(hair_groom["rim_strength"])
    cloth_sheen = normalize_cloth_sheen_settings(lighting)
    state.cloth_sheen_mode = str(cloth_sheen["mode"])
    state.cloth_sheen_strength = float(cloth_sheen["strength"])
    state.cloth_sheen_color = tuple(float(v) for v in cloth_sheen["color"])
    state.cloth_sheen_roughness = float(cloth_sheen["roughness"])
    state.cloth_sheen_edge_tint = tuple(float(v) for v in cloth_sheen["edge_tint"])
    state.cloth_sheen_fiber_strength = float(cloth_sheen["fiber_strength"])
    state.cloth_sheen_wrap = float(cloth_sheen["wrap"])
    state.cloth_sheen_retroreflection = float(cloth_sheen["retroreflection"])
    glint_sparkle = normalize_glint_sparkle_settings(lighting)
    state.glint_mode = str(glint_sparkle["mode"])
    state.glint_strength = float(glint_sparkle["strength"])
    state.glint_color = tuple(float(v) for v in glint_sparkle["color"])
    state.glint_density = float(glint_sparkle["density"])
    state.glint_scale = float(glint_sparkle["scale"])
    state.glint_threshold = float(glint_sparkle["threshold"])
    state.glint_sharpness = float(glint_sparkle["sharpness"])
    state.glint_roughness_jitter = float(glint_sparkle["roughness_jitter"])
    caustics = normalize_caustics_settings(lighting)
    state.caustics_mode = str(caustics["mode"])
    state.caustics_strength = float(caustics["strength"])
    state.caustics_quality = str(caustics["quality"])
    state.caustics_sample_count = int(caustics["sample_count"])
    state.caustics_scale = float(caustics["scale"])
    state.caustics_focus = float(caustics["focus"])
    state.caustics_radius = float(caustics["radius"])
    state.caustics_threshold = float(caustics["threshold"])
    state.caustics_tint = tuple(float(v) for v in caustics["tint"])
    state.caustics_seed = int(caustics["seed"])
    anisotropic = normalize_anisotropic_material_settings(lighting)
    state.anisotropic_mode = str(anisotropic["mode"])
    state.anisotropic_strength = float(anisotropic["strength"])
    state.anisotropy = float(anisotropic["anisotropy"])
    state.anisotropic_rotation = float(anisotropic["rotation"])
    state.anisotropic_tangent_weight = float(anisotropic["tangent_weight"])
    state.clearcoat_anisotropy = float(anisotropic["clearcoat_anisotropy"])
    state.thin_film_strength = float(anisotropic["thin_film_strength"])
    state.thin_film_thickness_nm = float(anisotropic["thin_film_thickness_nm"])
    state.thin_film_ior = float(anisotropic["thin_film_ior"])
    state.thin_film_tint = tuple(float(v) for v in anisotropic["thin_film_tint"])
    state.newton_rings_strength = float(anisotropic["newton_rings_strength"])
    state.newton_rings_scale = float(anisotropic["newton_rings_scale"])
    state.anisotropic_seed = int(anisotropic["seed"])
    microsurface = normalize_microsurface_settings(lighting)
    state.microsurface_mode = str(microsurface["mode"])
    state.detail_normal_strength = float(microsurface["detail_normal_strength"])
    state.detail_normal_scale = float(microsurface["detail_normal_scale"])
    state.detail_normal_blend = str(microsurface["detail_normal_blend"])
    state.detail_normal_seed = int(microsurface["detail_normal_seed"])
    state.micro_roughness_strength = float(microsurface["micro_roughness_strength"])
    state.micro_roughness_scale = float(microsurface["micro_roughness_scale"])
    state.micro_roughness_contrast = float(microsurface["micro_roughness_contrast"])
    state.gloss_variation_strength = float(microsurface["gloss_variation_strength"])
    state.gloss_bias = float(microsurface["gloss_bias"])
    state.specular_micro_occlusion = float(microsurface["specular_micro_occlusion"])
    depth_of_field = normalize_depth_of_field_settings(lighting)
    state.depth_of_field_mode = str(depth_of_field["mode"])
    state.depth_of_field_strength = float(depth_of_field["strength"])
    state.dof_focus_depth = float(depth_of_field["focus_depth"])
    state.dof_focus_range = float(depth_of_field["focus_range"])
    state.dof_max_blur_px = float(depth_of_field["max_blur_px"])
    state.dof_near_blur = float(depth_of_field["near_blur"])
    state.dof_far_blur = float(depth_of_field["far_blur"])
    state.dof_bokeh_shape = str(depth_of_field["bokeh_shape"])
    post_effects = normalize_post_effects_settings(lighting)
    state.post_effects_mode = str(post_effects["mode"])
    state.bloom_strength = float(post_effects["bloom_strength"])
    state.bloom_radius = float(post_effects["bloom_radius"])
    state.bloom_threshold = float(post_effects["bloom_threshold"])
    state.vignette_strength = float(post_effects["vignette_strength"])
    state.vignette_radius = float(post_effects["vignette_radius"])
    state.vignette_feather = float(post_effects["vignette_feather"])
    state.grain_strength = float(post_effects["grain_strength"])
    state.grain_scale = float(post_effects["grain_scale"])
    state.grain_seed = int(post_effects["grain_seed"])
    state.sharpen_strength = float(post_effects["sharpen_strength"])
    state.sharpen_radius = float(post_effects["sharpen_radius"])
    lens_effects = normalize_lens_effects_settings(lighting)
    state.lens_effects_mode = str(lens_effects["mode"])
    state.lens_distortion_strength = float(lens_effects["distortion_strength"])
    state.lens_distortion_k2 = float(lens_effects["distortion_k2"])
    state.chromatic_aberration_strength = float(lens_effects["chromatic_aberration_strength"])
    state.chromatic_aberration_px = float(lens_effects["chromatic_aberration_px"])
    state.lens_center = tuple(float(v) for v in lens_effects["center"])
    state.lens_edge_falloff = float(lens_effects["edge_falloff"])
    lens_flare = normalize_lens_flare_settings(lighting)
    state.lens_flare_mode = str(lens_flare["mode"])
    state.lens_flare_strength = float(lens_flare["flare_strength"])
    state.lens_flare_threshold = float(lens_flare["flare_threshold"])
    state.lens_flare_radius = float(lens_flare["flare_radius"])
    state.lens_flare_ghost_count = int(lens_flare["ghost_count"])
    state.lens_flare_ghost_spacing = float(lens_flare["ghost_spacing"])
    state.lens_flare_tint = tuple(float(v) for v in lens_flare["flare_tint"])
    state.aperture_flare_strength = float(lens_flare["aperture_flare_strength"])
    state.aperture_flare_blades = int(lens_flare["aperture_blades"])
    state.aperture_flare_rotation_deg = float(lens_flare["aperture_rotation_deg"])
    state.aperture_flare_radius = float(lens_flare["aperture_flare_radius"])
    state.lens_dirt_strength = float(lens_flare["lens_dirt_strength"])
    state.lens_dirt_density = float(lens_flare["lens_dirt_density"])
    state.lens_dirt_scale = float(lens_flare["lens_dirt_scale"])
    state.lens_scratch_strength = float(lens_flare["lens_scratch_strength"])
    state.lens_scratch_density = float(lens_flare["lens_scratch_density"])
    state.lens_scratch_length = float(lens_flare["lens_scratch_length"])
    state.lens_flare_seed = int(lens_flare["seed"])
    render_pass_source = dict(lighting)
    if str(settings.get("render_pass_output_dir") or ""):
        render_pass_source["render_pass_output_dir"] = str(settings.get("render_pass_output_dir") or "")
    render_passes = normalize_render_pass_settings(render_pass_source)
    motion_blur = merge_motion_blur_settings(settings, lighting)
    triplanar = normalize_triplanar_settings(lighting)
    state.triplanar_mode = str(triplanar["mode"])
    state.triplanar_strength = float(triplanar["strength"])
    state.triplanar_scale = float(triplanar["scale"])
    state.triplanar_blend_sharpness = float(triplanar["blend_sharpness"])
    state.triplanar_offset = tuple(float(v) for v in triplanar["offset"])
    state.triplanar_space = str(triplanar["space"])
    state.ground_y = float(lighting.get("ground_height", state.ground_y) or state.ground_y)
    model_view = _model_view_settings(settings)
    state.zoom = _float_setting(model_view, "zoom", state.zoom)
    state.camera_z = _float_setting(model_view, "camera_z", state.camera_z)
    state.pan_x = _float_setting(model_view, "pan_x", state.pan_x)
    state.pan_y = _float_setting(model_view, "pan_y", state.pan_y)
    state.pan_z = _float_setting(model_view, "pan_z", state.pan_z)
    auto_fit = _bool_setting(model_view, "auto_fit", True)
    fit_padding = _float_setting(model_view, "fit_padding", _float_setting(settings, "fit_padding", DEFAULT_FRAME_FIT_PADDING))
    show_environment_background = _bool_setting(model_view, "show_environment_background", False)
    transparent_background = _bool_setting(model_view, "transparent_background", True)
    draw_ground = _bool_setting(model_view, "draw_ground", False)

    def _grab_overlay(*, enable_shadow_map: bool) -> tuple[Path, dict[str, Any]]:
        stage_start = time.perf_counter()
        reuse_widget = _bool_setting(settings, "reuse_gpu_widget", False)
        texture_key = json.dumps(texture_plan, sort_keys=True, default=str)
        cache_key = (
            str(asset.resolve()) if asset.exists() else str(asset),
            width,
            height,
            int(settings.get("texture_max_size", 1024) or 1024),
            bool(enable_shadow_map),
            bool(show_environment_background),
            bool(transparent_background),
            bool(draw_ground),
            hdri_path_raw,
            texture_key,
        )
        cached = _GPU_WIDGET_CACHE.get(cache_key) if reuse_widget else None
        host = cached.get("host") if isinstance(cached, dict) else None
        widget = cached.get("widget") if isinstance(cached, dict) else None
        cache_hit = widget is not None and host is not None
        if host is None:
            host = QWidget()
            # QOpenGLWidget needs a real native surface on Windows.  Using
            # WA_DontShowOnScreen can leave PyOpenGL with an invalid current
            # context during resize/paint.  Keep the helper window offscreen
            # instead so export remains worker-safe without showing UI chrome.
            host.setWindowFlag(Qt.WindowType.Tool, True)
            host.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
            host.move(-32000, -32000)
        widget = None
        cache_stored = False
        try:
            if cache_hit:
                widget = cached["widget"]
                widget.state = state
                widget.fit_padding = float(fit_padding)
                widget.show_environment_background = bool(show_environment_background)
                widget.transparent_background = bool(transparent_background)
                widget.draw_ground = bool(draw_ground)
                widget.replace_vertices(vertices, mesh_diag)
            else:
                widget = GpuMeshWidget(
                    vertices,
                    state,
                    hdri,
                    mesh_diag,
                    texture_plan,
                    int(settings.get("texture_max_size", 1024) or 1024),
                    bool(enable_shadow_map),
                    float(fit_padding),
                    bool(show_environment_background),
                    bool(transparent_background),
                    bool(draw_ground),
                    parent=host,
                )
            widget.auto_fit_enabled = bool(auto_fit)
            widget.auto_fit_pending = bool(auto_fit)
            widget.setMinimumSize(1, 1)
            widget.setFixedSize(width, height)
            host.setFixedSize(width, height)
            host.resize(width, height)
            widget.resize(width, height)
            host.show()
            widget.show()
            if reuse_widget and not cache_hit:
                _GPU_WIDGET_CACHE[cache_key] = {"host": host, "widget": widget}
                cache_stored = True
            warmup_default = 1 if cache_hit else 8
            warmup_frames = max(1, min(8, int(settings.get("gpu_warmup_frames", warmup_default) or warmup_default)))
            timings["gpu_warmup_frames"] = float(warmup_frames)
            timings["gpu_widget_cache_hit"] = 1.0 if cache_hit else 0.0
            for _ in range(warmup_frames):
                app.processEvents()
                widget.update()
            app.processEvents()
            widget.makeCurrent()
            qimg = widget.grabFramebuffer()
            widget.doneCurrent()
            suffix = "shadow" if enable_shadow_map else "safe"
            overlay_path = temp_dir / f"overlay_{str(track.get('id') or 'track')}_{suffix}.png"
            qimg.save(str(overlay_path))
            timings["gpu_widget_grab_s"] = round(time.perf_counter() - stage_start, 4)
            return overlay_path, {
                "mesh": mesh_diag,
                "textures": texture_diag,
                "timings": dict(timings),
                "udim_rendering": {
                    "schema": "tigerstudio.ar_pbr.udim.v1",
                    "enabled": int(texture_diag.get("udim_tile_count", 0) or 0) > 0,
                    "map_count": int(texture_diag.get("udim_map_count", 0) or 0),
                    "tile_count": int(texture_diag.get("udim_tile_count", 0) or 0),
                    "sampling_model": "texture_plan_tile_set_primary_tile_live_gpu_preview",
                    "preview_policy": "packet_export_full_tile_lookup_live_primary_tile_preview",
                    "render_pass_safe": True,
                },
                "hdri": hdri_diag,
                "ibl_probe": widget.ibl_diagnostics() if hasattr(widget, "ibl_diagnostics") else {},
                "overlay_path": str(overlay_path),
                "overlay_size": [width, height],
                "shadow_map_enabled": bool(enable_shadow_map),
                "shadow_filter": shadow_filter_diagnostics(
                    state,
                    enable_shadow_map=bool(enable_shadow_map),
                    shadow_supported=bool(getattr(widget, "shadow_supported", False)),
                    shadow_size=int(getattr(widget, "shadow_size", 2048)),
                    shadow_error=str(getattr(widget, "shadow_error", "") or ""),
                ),
                "catcher": catcher_diagnostics(state),
                "color_management": color_management_diagnostics(state),
                "hybrid_rendering": hybrid_rendering_diagnostics(state),
                "ray_gi_detail": {
                    **dict(ray_gi_detail_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_clamp_and_denoise_channel_gate_until_native_ray_hybrid_detail_lands",
                },
                "ambient_occlusion_rendering": ambient_occlusion_diagnostics(state),
                "transmission_rendering": transmission_diagnostics(state),
                "clearcoat_rendering": clearcoat_diagnostics(state),
                "parallax_rendering": parallax_diagnostics(state),
                "displacement_rendering": {
                    **dict(displacement_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "native_tessellation_or_vector_displacement_pending_parallax_shader_is_realtime_fallback",
                },
                "bevel_rendering": bevel_diagnostics(state),
                "material_layering": material_layering_diagnostics(state),
                "subsurface_rendering": subsurface_diagnostics(state),
                "hair_groom_rendering": hair_groom_diagnostics(state),
                "cloth_sheen_rendering": cloth_sheen_diagnostics(state),
                "glint_sparkle_rendering": glint_sparkle_diagnostics(state),
                "caustics_rendering": {
                    **dict(caustics_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_caustic_highlight_ripples_until_native_caustic_integrator_lands",
                },
                "anisotropic_rendering": {
                    **dict(anisotropic_material_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_anisotropic_thin_film_polish_until_native_shader_lands",
                },
                "microsurface_rendering": {
                    **dict(microsurface_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_detail_normal_and_micro_roughness_until_native_shader_lands",
                },
                "depth_of_field_rendering": depth_of_field_diagnostics(state),
                "post_effects_rendering": post_effects_diagnostics(state),
                "lens_effects_rendering": {
                    **dict(lens_effects_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_beauty_warp_until_native_full_gpu_post_pass_lands",
                },
                "lens_flare_rendering": {
                    **dict(lens_flare_diagnostics(state)),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_applies_beauty_flare_until_native_full_gpu_post_pass_lands",
                },
                "render_passes": {
                    **dict(render_passes),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_writes_png_passes_until_native_full_gpu_pass_fbos_land",
                },
                "motion_blur": {
                    **dict(motion_blur),
                    "renderer": "full_gpu_helper_contract_only",
                    "output_policy": "packet_export_uses_shutter_sample_accumulation_until_native_velocity_or_multisample_full_gpu_path",
                },
                "triplanar_rendering": triplanar_diagnostics(state),
                "model_view": {
                    "auto_fit": bool(auto_fit),
                    "zoom": float(state.zoom),
                    "camera_z": float(state.camera_z),
                    "pan": [float(state.pan_x), float(state.pan_y), float(state.pan_z)],
                    "show_environment_background": bool(show_environment_background),
                    "transparent_background": bool(transparent_background),
                    "draw_ground": bool(draw_ground),
                },
            }
        finally:
            if widget is not None and not (reuse_widget and (cache_hit or cache_stored)):
                widget.close()
            if not (reuse_widget and (cache_hit or cache_stored)):
                host.close()

    requested_shadow_map = bool(settings.get("enable_shadow_map", False))
    try:
        return _grab_overlay(enable_shadow_map=requested_shadow_map)
    except Exception as exc:
        if not requested_shadow_map:
            raise
        overlay_path, diag = _grab_overlay(enable_shadow_map=False)
        diag["shadow_map_retry"] = True
        diag["warnings"] = [f"shadow-map pass failed; retried without shadow map: {type(exc).__name__}: {exc}"]
        return overlay_path, diag


def render_request(request: Mapping[str, Any]) -> dict[str, Any]:
    from PIL import Image
    from PySide6.QtGui import QSurfaceFormat
    from PySide6.QtWidgets import QApplication
    from app.ar_pbr.schema import normalize_ar_tracks, track_active_at

    base_path = Path(str(request.get("base_frame_path") or ""))
    output_path = Path(str(request.get("output_frame_path") or ""))
    if not base_path.is_file():
        return {"ok": False, "error": "base_frame_missing", "base_frame_path": str(base_path)}
    if not output_path:
        return {"ok": False, "error": "output_frame_path_missing"}

    base = Image.open(base_path).convert("RGBA")
    width, height = base.size
    time_ms = int(request.get("time_ms", 0) or 0)
    settings = request.get("settings") if isinstance(request.get("settings"), Mapping) else {}
    depth_frame = _load_depth_frame_payload(request.get("depth_frame"), width, height)
    tracks = [track for track in normalize_ar_tracks(request.get("ar_tracks") or []) if track_active_at(track, time_ms)]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    fmt.setAlphaBufferSize(8)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication.instance() or QApplication(["ar_pbr_full_gpu_export_service"])
    rows: list[dict[str, Any]] = []
    rendered = 0
    depth_occluded_pixels = 0
    depth_occlusion_applied = False
    with tempfile.TemporaryDirectory(prefix="tiger_ar_pbr_gpu_overlay_") as raw_tmp:
        temp_dir = Path(raw_tmp)
        for track in tracks:
            x0, y0, x1, y1, _depth = _track_rect(track, width, height)
            if x1 <= x0 or y1 <= y0:
                rows.append({"track_id": str(track.get("id") or ""), "ok": False, "reason": "empty_screen_rect"})
                continue
            descriptor, descriptor_diag = _resolve_descriptor(track, settings)
            if not descriptor:
                rows.append({"track_id": str(track.get("id") or ""), "ok": False, "reason": "descriptor_missing", "descriptor": descriptor_diag})
                continue
            try:
                overlay_path, diag = _render_track_overlay(
                    app=app,
                    track=track,
                    descriptor=descriptor,
                    time_ms=int(time_ms),
                    rect_size=(x1 - x0, y1 - y0),
                    settings=settings,
                    temp_dir=temp_dir,
                )
                overlay = Image.open(overlay_path).convert("RGBA")
                if overlay.size != (x1 - x0, y1 - y0):
                    overlay = overlay.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
                depth_occlusion_diag = {"enabled": False, "applied": False, "occluded_pixels": 0}
                if bool(track.get("occlusion")):
                    overlay, depth_occlusion_diag = _apply_depth_occlusion_to_overlay(
                        overlay,
                        depth_frame=depth_frame,
                        rect=(x0, y0, x1, y1),
                        object_depth=_depth,
                        settings=settings,
                    )
                    depth_occluded_pixels += int(depth_occlusion_diag.get("occluded_pixels", 0) or 0)
                    depth_occlusion_applied = depth_occlusion_applied or bool(depth_occlusion_diag.get("applied"))
                base.alpha_composite(overlay, (x0, y0))
                rendered += 1
                rows.append({
                    "track_id": str(track.get("id") or ""),
                    "ok": True,
                    "rect": [x0, y0, x1, y1],
                    "depth_occlusion": depth_occlusion_diag,
                    **diag,
                })
            except Exception as exc:
                rows.append({"track_id": str(track.get("id") or ""), "ok": False, "reason": f"{type(exc).__name__}: {exc}", "descriptor": descriptor_diag})

    base.save(output_path)
    return {
        "ok": rendered > 0,
        "mode": "full_model_view_gpu_export_service",
        "renderer_quality": "full_model_view_gpu_pbr",
        "full_gpu_export_available": True,
        "worker_safe": True,
        "rendered_track_count": rendered,
        "track_count": len(tracks),
        "depth_frame_available": depth_frame is not None,
        "pbr_depth_occlusion_applied": depth_occlusion_applied,
        "pbr_depth_occluded_pixels": depth_occluded_pixels,
        "output_frame_path": str(output_path),
        "rows": rows,
    }


def main() -> int:
    _ensure_service_gl_defaults()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="AR/PBR full model-view GPU export helper")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--stdio", action="store_true", help="Keep the helper alive and read JSON render requests from stdin.")
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()

    if args.probe:
        try:
            import OpenGL  # noqa: F401
            import PySide6  # noqa: F401

            _write_json({
                "ok": True,
                "mode": "full_model_view_gpu_export_service",
                "renderer_quality": "full_model_view_gpu_pbr",
                "worker_safe": True,
            })
            return 0
        except Exception as exc:
            _write_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
            return 1
    if args.stdio:
        return _serve_stdio()
    if not args.request:
        _write_json({"ok": False, "error": "--request is required unless --probe is used"})
        return 2
    try:
        _write_json(render_request(_load_json(args.request)))
        return 0
    except Exception as exc:
        _write_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
