"""QA report for the AR/PBR full GPU export service contract."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def run_ar_pbr_full_gpu_export_service_qa(
    *,
    probe: bool = False,
    smoke_render: bool = False,
    timeout_seconds: int = 10,
) -> dict:
    from app.ar_pbr.full_gpu_export_service import build_full_gpu_export_service_report

    report = build_full_gpu_export_service_report(
        probe=bool(probe),
        timeout_seconds=max(1, int(timeout_seconds or 10)),
    )
    if smoke_render:
        try:
            import numpy as np
            from PIL import Image
            from app.ar_pbr.export_packet_renderer import render_offscreen_gpu_export_frame

            base = np.zeros((96, 96, 3), dtype=np.uint8)
            texture_dir = ROOT / "debugCapture" / "ar_pbr_full_gpu_service_smoke_assets"
            texture_dir.mkdir(parents=True, exist_ok=True)
            yy, xx = np.mgrid[0:32, 0:32]
            height_tex = np.clip(128 + np.sin(xx / 3.5) * 46 + np.cos(yy / 4.5) * 34, 0, 255).astype(np.uint8)
            height_tex_1002 = np.clip(142 + np.sin((xx + 7) / 4.0) * 38 + np.cos((yy + 3) / 5.0) * 42, 0, 255).astype(np.uint8)
            height_path = texture_dir / "smoke_height.<UDIM>.png"
            Image.fromarray(height_tex, "L").save(texture_dir / "smoke_height.1001.png")
            Image.fromarray(height_tex_1002, "L").save(texture_dir / "smoke_height.1002.png")
            descriptor = {
                "geometries": [
                    {
                        "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                        "uvs": [[1.02, 0.0], [1.95, 0.0], [1.5, 0.95]],
                        "triangles": [[0, 1, 2]],
                        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                    }
                ],
                "materials": [{"name": "smoke", "base_color": [1.0, 0.24, 0.08, 1.0], "height_texture": str(height_path)}],
            }
            track = {
                "id": "ar_pbr_full_gpu_smoke",
                "asset_path": "ar_pbr_full_gpu_smoke.glb",
                "start_ms": 0,
                "end_ms": 1000,
                "transform": {"position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]},
                "render": {
                    "lighting": {
                        "shadow_filter": "pcss",
                        "shadow_light_type": "spot",
                        "shadow_pcf_radius": 2.2,
                        "shadow_pcss_blocker_radius": 3.25,
                        "shadow_bias": 0.004,
                        "shadow_normal_bias": 0.005,
                        "shadow_spot_inner_angle": 26.0,
                        "shadow_spot_outer_angle": 48.0,
                        "shadow_catcher_opacity": 0.82,
                        "shadow_catcher_softness": 0.70,
                        "shadow_catcher_matte_alpha": 0.12,
                        "reflection_catcher_opacity": 0.58,
                        "reflection_catcher_roughness": 0.72,
                        "reflection_catcher_softness": 0.66,
                        "contact_reflection_strength": 0.44,
                        "contact_reflection_falloff": 0.64,
                        "tone_mapping": "agx",
                        "tone_exposure": 0.5,
                        "tone_white_balance": 5600,
                        "tone_gamma": 2.3,
                        "hybrid_accumulation": True,
                        "accumulation_samples": 12,
                        "diffuse_gi_strength": 0.28,
                        "specular_gi_strength": 0.16,
                        "denoise_strength": 0.34,
                        "ray_gi_detail": {
                            "mode": "hybrid",
                            "max_bounces": 5,
                            "diffuse_bounces": 2,
                            "specular_bounces": 3,
                            "refraction_bounces": 4,
                            "direct_radiance_clamp": 1.25,
                            "indirect_radiance_clamp": 0.88,
                            "advanced_light_sampling": True,
                            "light_sampling_mode": "mis",
                            "light_sample_count": 20,
                            "environment_sample_count": 40,
                            "denoise_channels": ["beauty", "diffuse", "specular"],
                            "denoise_albedo_guided": True,
                            "denoise_normal_guided": True,
                        },
                        "ao_strength": 0.35,
                        "ao_radius": 4.2,
                        "ao_distance": 0.50,
                        "ao_color": [0.025, 0.02, 0.018],
                        "ao_specular": True,
                        "transmission": 0.38,
                        "refraction_strength": 0.52,
                        "refraction_depth_px": 7.0,
                        "ior": 1.47,
                        "thickness": 0.18,
                        "absorption_color": [0.86, 0.96, 1.0],
                        "absorption_distance": 1.5,
                        "roughness_blur_strength": 0.22,
                        "clearcoat_strength": 0.41,
                        "clearcoat_roughness": 0.11,
                        "clearcoat_ior": 1.54,
                        "clearcoat_tint": [1.0, 0.96, 0.92],
                        "parallax_strength": 0.47,
                        "parallax_depth": 0.04,
                        "parallax_center": 0.5,
                        "parallax_steps": 4,
                        "displacement_height_strength": 0.49,
                        "displacement_height_scale": 0.045,
                        "displacement_height_center": 0.48,
                        "vector_displacement_strength": 0.18,
                        "vector_displacement_space": "tangent",
                        "displacement_subdivision_mode": "adaptive",
                        "displacement_max_offset": 0.09,
                        "displacement_parallax_fallback": True,
                        "bevel_strength": 0.42,
                        "bevel_radius": 0.052,
                        "bevel_edge_width": 0.08,
                        "bevel_samples": 4,
                        "material_layer_blend": 0.36,
                        "material_layer_color": [0.92, 0.48, 0.18],
                        "material_layer_roughness": 0.34,
                        "material_layer_metallic": 0.16,
                        "material_layer_alpha": 0.93,
                        "material_layer_emissive_strength": 0.07,
                        "material_layer_mask_strength": 0.82,
                        "subsurface_strength": 0.31,
                        "subsurface_color": [1.0, 0.60, 0.38],
                        "subsurface_radius": 0.42,
                        "subsurface_power": 2.2,
                        "subsurface_wrap": 0.50,
                        "subsurface_thickness": 0.14,
                        "hair_groom_strength": 0.33,
                        "hair_groom_tint": [1.0, 0.84, 0.50],
                        "hair_primary_shift": 0.08,
                        "hair_secondary_shift": -0.19,
                        "hair_primary_roughness": 0.23,
                        "hair_secondary_roughness": 0.44,
                        "hair_secondary_strength": 0.52,
                        "hair_anisotropy": 0.80,
                        "hair_rim_strength": 0.18,
                        "cloth_sheen_strength": 0.32,
                        "cloth_sheen_color": [0.86, 0.91, 1.0],
                        "cloth_sheen_roughness": 0.60,
                        "cloth_sheen_edge_tint": [0.70, 0.82, 1.0],
                        "cloth_sheen_fiber_strength": 0.26,
                        "cloth_sheen_wrap": 0.35,
                        "cloth_sheen_retroreflection": 0.29,
                        "glint_strength": 0.30,
                        "glint_color": [1.0, 0.93, 0.70],
                        "glint_density": 0.44,
                        "glint_scale": 40.0,
                        "glint_threshold": 0.40,
                        "glint_sharpness": 15.0,
                        "glint_roughness_jitter": 0.56,
                        "caustics_strength": 0.36,
                        "caustics_quality": "high",
                        "caustics_sample_count": 20,
                        "caustics_scale": 32.0,
                        "caustics_focus": 0.66,
                        "caustics_radius": 0.80,
                        "caustics_threshold": 0.10,
                        "caustics_tint": [1.0, 0.9, 0.62],
                        "caustics_seed": 41,
                        "anisotropic_strength": 0.39,
                        "anisotropy": 0.56,
                        "anisotropic_rotation": 26.0,
                        "anisotropic_tangent_weight": 0.72,
                        "clearcoat_anisotropy": 0.28,
                        "thin_film_enabled": True,
                        "thin_film_strength": 0.46,
                        "thin_film_thickness_nm": 500.0,
                        "thin_film_ior": 1.39,
                        "thin_film_tint": [1.0, 0.84, 0.58],
                        "newton_rings_strength": 0.16,
                        "newton_rings_scale": 20.0,
                        "anisotropic_seed": 47,
                        "detail_normal_strength": 0.42,
                        "detail_normal_scale": 44.0,
                        "detail_normal_blend": "reoriented",
                        "detail_normal_seed": 53,
                        "micro_roughness_strength": 0.34,
                        "micro_roughness_scale": 50.0,
                        "micro_roughness_contrast": 0.40,
                        "gloss_variation_strength": 0.24,
                        "gloss_bias": 0.06,
                        "specular_micro_occlusion": 0.18,
                        "depth_of_field_strength": 0.58,
                        "dof_focus_depth": 0.16,
                        "dof_focus_range": 0.04,
                        "dof_max_blur_px": 4.5,
                        "dof_near_blur": 0.62,
                        "dof_far_blur": 1.05,
                        "bloom_strength": 0.28,
                        "bloom_radius": 2.6,
                        "bloom_threshold": 0.40,
                        "vignette_strength": 0.20,
                        "vignette_radius": 0.68,
                        "vignette_feather": 0.35,
                        "grain_strength": 0.03,
                        "grain_scale": 80.0,
                        "grain_seed": 11,
                        "sharpen_strength": 0.22,
                        "sharpen_radius": 0.95,
                        "lens_distortion_strength": 0.18,
                        "lens_distortion_k2": 0.04,
                        "chromatic_aberration_strength": 0.42,
                        "chromatic_aberration_px": 2.4,
                        "lens_edge_falloff": 1.2,
                        "lens_flare_strength": 0.34,
                        "lens_flare_threshold": 0.38,
                        "lens_flare_radius": 4.2,
                        "lens_flare_ghost_count": 4,
                        "lens_flare_ghost_spacing": 0.36,
                        "aperture_flare_strength": 0.26,
                        "aperture_flare_blades": 7,
                        "aperture_flare_rotation_deg": 18.0,
                        "aperture_flare_radius": 20.0,
                        "lens_dirt_strength": 0.16,
                        "lens_dirt_density": 0.42,
                        "lens_dirt_scale": 84.0,
                        "lens_scratch_strength": 0.14,
                        "lens_scratch_density": 0.30,
                        "lens_scratch_length": 0.62,
                        "lens_flare_seed": 31,
                        "render_passes_enabled": True,
                        "render_pass_names": ["beauty", "alpha_mask", "depth", "normal"],
                        "motion_blur_enabled": True,
                        "motion_blur_samples": 4,
                        "motion_blur_shutter_angle": 180.0,
                        "triplanar_strength": 1.0,
                        "triplanar_scale": 1.35,
                        "triplanar_blend_sharpness": 4.5,
                        "triplanar_offset": [0.07, 0.13, 0.19],
                    }
                },
                "shadow_catcher": True,
                "reflection_catcher": True,
            }
            out, diag = render_offscreen_gpu_export_frame(
                base,
                time_ms=10,
                ar_tracks=[track],
                camera_solution={"frame_size": [96, 96]},
                settings={
                    "asset_descriptors": {
                        "ar_pbr_full_gpu_smoke": descriptor,
                        "ar_pbr_full_gpu_smoke.glb": descriptor,
                    },
                    "enable_shadow_map": True,
                    "render_pass_output_dir": str(ROOT / "debugCapture" / "ar_pbr_full_gpu_service_render_passes"),
                    "model_view": {
                        "draw_ground": True,
                        "transparent_background": True,
                    },
                },
            )
            changed = int(np.asarray(out).sum()) > 0
            rows = diag.get("rows") if isinstance(diag.get("rows"), list) else []
            first_row = rows[0] if rows and isinstance(rows[0], dict) else {}
            shadow_filter = first_row.get("shadow_filter") if isinstance(first_row.get("shadow_filter"), dict) else {}
            catcher = first_row.get("catcher") if isinstance(first_row.get("catcher"), dict) else {}
            color_management = first_row.get("color_management") if isinstance(first_row.get("color_management"), dict) else {}
            hybrid_rendering = first_row.get("hybrid_rendering") if isinstance(first_row.get("hybrid_rendering"), dict) else {}
            ray_gi_detail = first_row.get("ray_gi_detail") if isinstance(first_row.get("ray_gi_detail"), dict) else {}
            ambient_occlusion_rendering = first_row.get("ambient_occlusion_rendering") if isinstance(first_row.get("ambient_occlusion_rendering"), dict) else {}
            transmission_rendering = first_row.get("transmission_rendering") if isinstance(first_row.get("transmission_rendering"), dict) else {}
            clearcoat_rendering = first_row.get("clearcoat_rendering") if isinstance(first_row.get("clearcoat_rendering"), dict) else {}
            parallax_rendering = first_row.get("parallax_rendering") if isinstance(first_row.get("parallax_rendering"), dict) else {}
            displacement_rendering = first_row.get("displacement_rendering") if isinstance(first_row.get("displacement_rendering"), dict) else {}
            bevel_rendering = first_row.get("bevel_rendering") if isinstance(first_row.get("bevel_rendering"), dict) else {}
            material_layering = first_row.get("material_layering") if isinstance(first_row.get("material_layering"), dict) else {}
            subsurface_rendering = first_row.get("subsurface_rendering") if isinstance(first_row.get("subsurface_rendering"), dict) else {}
            hair_groom_rendering = first_row.get("hair_groom_rendering") if isinstance(first_row.get("hair_groom_rendering"), dict) else {}
            cloth_sheen_rendering = first_row.get("cloth_sheen_rendering") if isinstance(first_row.get("cloth_sheen_rendering"), dict) else {}
            glint_sparkle_rendering = first_row.get("glint_sparkle_rendering") if isinstance(first_row.get("glint_sparkle_rendering"), dict) else {}
            caustics_rendering = first_row.get("caustics_rendering") if isinstance(first_row.get("caustics_rendering"), dict) else {}
            anisotropic_rendering = first_row.get("anisotropic_rendering") if isinstance(first_row.get("anisotropic_rendering"), dict) else {}
            microsurface_rendering = first_row.get("microsurface_rendering") if isinstance(first_row.get("microsurface_rendering"), dict) else {}
            depth_of_field_rendering = first_row.get("depth_of_field_rendering") if isinstance(first_row.get("depth_of_field_rendering"), dict) else {}
            post_effects_rendering = first_row.get("post_effects_rendering") if isinstance(first_row.get("post_effects_rendering"), dict) else {}
            lens_effects_rendering = first_row.get("lens_effects_rendering") if isinstance(first_row.get("lens_effects_rendering"), dict) else {}
            lens_flare_rendering = first_row.get("lens_flare_rendering") if isinstance(first_row.get("lens_flare_rendering"), dict) else {}
            render_passes = first_row.get("render_passes") if isinstance(first_row.get("render_passes"), dict) else {}
            motion_blur = first_row.get("motion_blur") if isinstance(first_row.get("motion_blur"), dict) else {}
            udim_rendering = first_row.get("udim_rendering") if isinstance(first_row.get("udim_rendering"), dict) else {}
            triplanar_rendering = first_row.get("triplanar_rendering") if isinstance(first_row.get("triplanar_rendering"), dict) else {}
            shadow_catcher = catcher.get("shadow_catcher") if isinstance(catcher.get("shadow_catcher"), dict) else {}
            reflection_catcher = catcher.get("reflection_catcher") if isinstance(catcher.get("reflection_catcher"), dict) else {}
            shadow_ok = (
                bool(first_row.get("shadow_map_enabled"))
                and not bool(first_row.get("shadow_map_retry"))
                and str(shadow_filter.get("primary_shadow_model") or "") == "shadow_map"
                and str(shadow_filter.get("filter") or "") == "pcss"
                and str(shadow_filter.get("light_type") or "") == "spot"
            )
            catcher_ok = (
                str(catcher.get("schema") or "") == "tigerstudio.ar_pbr.catcher.v1"
                and abs(float(shadow_catcher.get("matte_alpha", 0.0) or 0.0) - 0.12) < 1e-6
                and abs(float(reflection_catcher.get("roughness", 0.0) or 0.0) - 0.72) < 1e-6
                and abs(float(reflection_catcher.get("contact_reflection_strength", 0.0) or 0.0) - 0.44) < 1e-6
            )
            color_ok = (
                str(color_management.get("schema") or "") == "tigerstudio.ar_pbr.color_management.v1"
                and str(color_management.get("tone_mapping") or "") == "agx"
                and int(color_management.get("tone_mapping_mode", -1) or -1) == 1
                and abs(float(color_management.get("tone_exposure", 0.0) or 0.0) - 0.5) < 1e-6
                and abs(float(color_management.get("tone_white_balance", 0.0) or 0.0) - 5600.0) < 1e-6
                and abs(float(color_management.get("tone_gamma", 0.0) or 0.0) - 2.3) < 1e-6
                and bool(color_management.get("render_pass_safe"))
            )
            hybrid_ok = (
                str(hybrid_rendering.get("schema") or "") == "tigerstudio.ar_pbr.hybrid_rendering.v1"
                and bool(hybrid_rendering.get("enabled"))
                and int(hybrid_rendering.get("sample_count", 0) or 0) == 12
                and abs(float(hybrid_rendering.get("diffuse_gi_strength", 0.0) or 0.0) - 0.28) < 1e-6
                and abs(float(hybrid_rendering.get("specular_gi_strength", 0.0) or 0.0) - 0.16) < 1e-6
                and abs(float(hybrid_rendering.get("denoise_strength", 0.0) or 0.0) - 0.34) < 1e-6
            )
            ray_gi_detail_ok = (
                str(ray_gi_detail.get("schema") or "") == "tigerstudio.ar_pbr.ray_gi_detail.v1"
                and bool(ray_gi_detail.get("enabled"))
                and int(ray_gi_detail.get("max_bounces", 0) or 0) == 5
                and int(ray_gi_detail.get("diffuse_bounces", 0) or 0) == 2
                and int(ray_gi_detail.get("specular_bounces", 0) or 0) == 3
                and int(ray_gi_detail.get("refraction_bounces", 0) or 0) == 4
                and str(ray_gi_detail.get("light_sampling_mode") or "") == "mis"
                and int(ray_gi_detail.get("light_sample_count", 0) or 0) == 20
                and int(ray_gi_detail.get("environment_sample_count", 0) or 0) == 40
                and "specular" in list(ray_gi_detail.get("denoise_channels") or [])
                and str(ray_gi_detail.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            ambient_occlusion_ok = (
                str(ambient_occlusion_rendering.get("schema") or "") == "tigerstudio.ar_pbr.ambient_occlusion.v1"
                and bool(ambient_occlusion_rendering.get("enabled"))
                and str(ambient_occlusion_rendering.get("mode") or "") == "screen"
                and abs(float(ambient_occlusion_rendering.get("strength", 0.0) or 0.0) - 0.35) < 1e-6
                and bool(ambient_occlusion_rendering.get("specular"))
            )
            transmission_ok = (
                str(transmission_rendering.get("schema") or "") == "tigerstudio.ar_pbr.transmission.v1"
                and bool(transmission_rendering.get("enabled"))
                and abs(float(transmission_rendering.get("transmission", 0.0) or 0.0) - 0.38) < 1e-6
                and abs(float(transmission_rendering.get("refraction_strength", 0.0) or 0.0) - 0.52) < 1e-6
                and abs(float(transmission_rendering.get("ior", 0.0) or 0.0) - 1.47) < 1e-6
            )
            clearcoat_ok = (
                str(clearcoat_rendering.get("schema") or "") == "tigerstudio.ar_pbr.clearcoat.v1"
                and bool(clearcoat_rendering.get("enabled"))
                and abs(float(clearcoat_rendering.get("strength", 0.0) or 0.0) - 0.41) < 1e-6
                and abs(float(clearcoat_rendering.get("roughness", 0.0) or 0.0) - 0.11) < 1e-6
                and abs(float(clearcoat_rendering.get("ior", 0.0) or 0.0) - 1.54) < 1e-6
            )
            parallax_ok = (
                str(parallax_rendering.get("schema") or "") == "tigerstudio.ar_pbr.parallax.v1"
                and bool(parallax_rendering.get("enabled"))
                and abs(float(parallax_rendering.get("strength", 0.0) or 0.0) - 0.47) < 1e-6
                and abs(float(parallax_rendering.get("depth", 0.0) or 0.0) - 0.04) < 1e-6
            )
            displacement_ok = (
                str(displacement_rendering.get("schema") or "") == "tigerstudio.ar_pbr.displacement.v1"
                and bool(displacement_rendering.get("enabled"))
                and abs(float(displacement_rendering.get("height_strength", 0.0) or 0.0) - 0.49) < 1e-6
                and abs(float(displacement_rendering.get("vector_strength", 0.0) or 0.0) - 0.18) < 1e-6
                and bool(displacement_rendering.get("parallax_fallback"))
                and str(displacement_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            bevel_ok = (
                str(bevel_rendering.get("schema") or "") == "tigerstudio.ar_pbr.bevel.v1"
                and bool(bevel_rendering.get("enabled"))
                and abs(float(bevel_rendering.get("strength", 0.0) or 0.0) - 0.42) < 1e-6
                and abs(float(bevel_rendering.get("radius", 0.0) or 0.0) - 0.052) < 1e-6
            )
            material_layering_ok = (
                str(material_layering.get("schema") or "") == "tigerstudio.ar_pbr.material_layering.v1"
                and bool(material_layering.get("enabled"))
                and abs(float(material_layering.get("blend", 0.0) or 0.0) - 0.36) < 1e-6
                and abs(float(material_layering.get("roughness", 0.0) or 0.0) - 0.34) < 1e-6
            )
            subsurface_ok = (
                str(subsurface_rendering.get("schema") or "") == "tigerstudio.ar_pbr.subsurface.v1"
                and bool(subsurface_rendering.get("enabled"))
                and abs(float(subsurface_rendering.get("strength", 0.0) or 0.0) - 0.31) < 1e-6
                and abs(float(subsurface_rendering.get("radius", 0.0) or 0.0) - 0.42) < 1e-6
            )
            hair_groom_ok = (
                str(hair_groom_rendering.get("schema") or "") == "tigerstudio.ar_pbr.hair_groom.v1"
                and bool(hair_groom_rendering.get("enabled"))
                and abs(float(hair_groom_rendering.get("strength", 0.0) or 0.0) - 0.33) < 1e-6
                and abs(float(hair_groom_rendering.get("primary_roughness", 0.0) or 0.0) - 0.23) < 1e-6
                and abs(float(hair_groom_rendering.get("anisotropy", 0.0) or 0.0) - 0.80) < 1e-6
            )
            cloth_sheen_ok = (
                str(cloth_sheen_rendering.get("schema") or "") == "tigerstudio.ar_pbr.cloth_sheen.v1"
                and bool(cloth_sheen_rendering.get("enabled"))
                and abs(float(cloth_sheen_rendering.get("strength", 0.0) or 0.0) - 0.32) < 1e-6
                and abs(float(cloth_sheen_rendering.get("roughness", 0.0) or 0.0) - 0.60) < 1e-6
                and abs(float(cloth_sheen_rendering.get("fiber_strength", 0.0) or 0.0) - 0.26) < 1e-6
            )
            glint_sparkle_ok = (
                str(glint_sparkle_rendering.get("schema") or "") == "tigerstudio.ar_pbr.glint_sparkle.v1"
                and bool(glint_sparkle_rendering.get("enabled"))
                and abs(float(glint_sparkle_rendering.get("strength", 0.0) or 0.0) - 0.30) < 1e-6
                and abs(float(glint_sparkle_rendering.get("density", 0.0) or 0.0) - 0.44) < 1e-6
                and abs(float(glint_sparkle_rendering.get("scale", 0.0) or 0.0) - 40.0) < 1e-6
            )
            caustics_ok = (
                str(caustics_rendering.get("schema") or "") == "tigerstudio.ar_pbr.caustics.v1"
                and bool(caustics_rendering.get("enabled"))
                and abs(float(caustics_rendering.get("strength", 0.0) or 0.0) - 0.36) < 1e-6
                and int(caustics_rendering.get("sample_count", 0) or 0) == 20
                and str(caustics_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            anisotropic_ok = (
                str(anisotropic_rendering.get("schema") or "") == "tigerstudio.ar_pbr.anisotropic_material.v1"
                and bool(anisotropic_rendering.get("enabled"))
                and abs(float(anisotropic_rendering.get("strength", 0.0) or 0.0) - 0.39) < 1e-6
                and abs(float(anisotropic_rendering.get("anisotropy", 0.0) or 0.0) - 0.56) < 1e-6
                and bool(anisotropic_rendering.get("thin_film_enabled"))
                and abs(float(anisotropic_rendering.get("thin_film_strength", 0.0) or 0.0) - 0.46) < 1e-6
                and str(anisotropic_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            microsurface_ok = (
                str(microsurface_rendering.get("schema") or "") == "tigerstudio.ar_pbr.microsurface.v1"
                and bool(microsurface_rendering.get("enabled"))
                and bool(microsurface_rendering.get("detail_normal_enabled"))
                and abs(float(microsurface_rendering.get("detail_normal_strength", 0.0) or 0.0) - 0.42) < 1e-6
                and abs(float(microsurface_rendering.get("detail_normal_scale", 0.0) or 0.0) - 44.0) < 1e-6
                and bool(microsurface_rendering.get("micro_roughness_enabled"))
                and abs(float(microsurface_rendering.get("micro_roughness_strength", 0.0) or 0.0) - 0.34) < 1e-6
                and abs(float(microsurface_rendering.get("gloss_variation_strength", 0.0) or 0.0) - 0.24) < 1e-6
                and str(microsurface_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            depth_of_field_ok = (
                str(depth_of_field_rendering.get("schema") or "") == "tigerstudio.ar_pbr.depth_of_field.v1"
                and bool(depth_of_field_rendering.get("enabled"))
                and abs(float(depth_of_field_rendering.get("strength", 0.0) or 0.0) - 0.58) < 1e-6
                and abs(float(depth_of_field_rendering.get("focus_depth", 0.0) or 0.0) - 0.16) < 1e-6
                and abs(float(depth_of_field_rendering.get("max_blur_px", 0.0) or 0.0) - 4.5) < 1e-6
            )
            post_effects_ok = (
                str(post_effects_rendering.get("schema") or "") == "tigerstudio.ar_pbr.post_effects.v1"
                and bool(post_effects_rendering.get("enabled"))
                and bool(post_effects_rendering.get("bloom_enabled"))
                and bool(post_effects_rendering.get("vignette_enabled"))
                and bool(post_effects_rendering.get("grain_enabled"))
                and bool(post_effects_rendering.get("sharpen_enabled"))
                and abs(float(post_effects_rendering.get("bloom_strength", 0.0) or 0.0) - 0.28) < 1e-6
                and abs(float(post_effects_rendering.get("vignette_strength", 0.0) or 0.0) - 0.20) < 1e-6
            )
            lens_effects_ok = (
                str(lens_effects_rendering.get("schema") or "") == "tigerstudio.ar_pbr.lens_effects.v1"
                and bool(lens_effects_rendering.get("enabled"))
                and bool(lens_effects_rendering.get("distortion_enabled"))
                and bool(lens_effects_rendering.get("chromatic_aberration_enabled"))
                and abs(float(lens_effects_rendering.get("distortion_strength", 0.0) or 0.0) - 0.18) < 1e-6
                and abs(float(lens_effects_rendering.get("chromatic_aberration_px", 0.0) or 0.0) - 2.4) < 1e-6
                and str(lens_effects_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            lens_flare_ok = (
                str(lens_flare_rendering.get("schema") or "") == "tigerstudio.ar_pbr.lens_flare.v1"
                and bool(lens_flare_rendering.get("enabled"))
                and bool(lens_flare_rendering.get("flare_enabled"))
                and bool(lens_flare_rendering.get("aperture_flare_enabled"))
                and bool(lens_flare_rendering.get("lens_dirt_enabled"))
                and bool(lens_flare_rendering.get("lens_scratch_enabled"))
                and int(lens_flare_rendering.get("ghost_count", 0) or 0) == 4
                and int(lens_flare_rendering.get("aperture_blades", 0) or 0) == 7
                and abs(float(lens_flare_rendering.get("flare_strength", 0.0) or 0.0) - 0.34) < 1e-6
                and abs(float(lens_flare_rendering.get("lens_dirt_strength", 0.0) or 0.0) - 0.16) < 1e-6
                and str(lens_flare_rendering.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            render_passes_ok = (
                str(render_passes.get("schema") or "") == "tigerstudio.ar_pbr.render_passes.v1"
                and bool(render_passes.get("enabled"))
                and list(render_passes.get("passes") or []) == ["beauty", "alpha_mask", "depth", "normal"]
                and str(render_passes.get("renderer") or "") == "full_gpu_helper_contract_only"
                and bool(render_passes.get("render_pass_safe"))
            )
            motion_blur_ok = (
                str(motion_blur.get("schema") or "") == "tigerstudio.ar_pbr.motion_blur.v1"
                and bool(motion_blur.get("enabled"))
                and str(motion_blur.get("mode") or "") == "final"
                and int(motion_blur.get("sample_count", 0) or 0) == 4
                and abs(float(motion_blur.get("shutter_angle", 0.0) or 0.0) - 180.0) < 1e-6
                and str(motion_blur.get("renderer") or "") == "full_gpu_helper_contract_only"
            )
            udim_ok = (
                str(udim_rendering.get("schema") or "") == "tigerstudio.ar_pbr.udim.v1"
                and bool(udim_rendering.get("enabled"))
                and int(udim_rendering.get("tile_count", 0) or 0) >= 2
            )
            triplanar_ok = (
                str(triplanar_rendering.get("schema") or "") == "tigerstudio.ar_pbr.triplanar.v1"
                and bool(triplanar_rendering.get("enabled"))
                and abs(float(triplanar_rendering.get("scale", 0.0) or 0.0) - 1.35) < 1e-6
                and abs(float(triplanar_rendering.get("blend_sharpness", 0.0) or 0.0) - 4.5) < 1e-6
            )
            report["smoke_render"] = {
                "ok": bool(diag.get("ok") and diag.get("mode") == "full_model_view_gpu_export_service" and changed and shadow_ok and catcher_ok and color_ok and hybrid_ok and ray_gi_detail_ok and ambient_occlusion_ok and transmission_ok and clearcoat_ok and parallax_ok and displacement_ok and bevel_ok and material_layering_ok and subsurface_ok and hair_groom_ok and cloth_sheen_ok and glint_sparkle_ok and caustics_ok and anisotropic_ok and microsurface_ok and depth_of_field_ok and post_effects_ok and lens_effects_ok and lens_flare_ok and render_passes_ok and motion_blur_ok and udim_ok and triplanar_ok),
                "mode": str(diag.get("mode") or ""),
                "fallback": bool(diag.get("fallback")),
                "rendered_track_count": int(diag.get("rendered_track_count", 0) or 0),
                "changed_pixels_proxy": changed,
                "ibl_probe": dict(first_row.get("ibl_probe") or {}),
                "shadow_filter": dict(shadow_filter),
                "catcher": dict(catcher),
                "color_management": dict(color_management),
                "hybrid_rendering": dict(hybrid_rendering),
                "ray_gi_detail": dict(ray_gi_detail),
                "ambient_occlusion_rendering": dict(ambient_occlusion_rendering),
                "transmission_rendering": dict(transmission_rendering),
                "clearcoat_rendering": dict(clearcoat_rendering),
                "parallax_rendering": dict(parallax_rendering),
                "displacement_rendering": dict(displacement_rendering),
                "bevel_rendering": dict(bevel_rendering),
                "material_layering": dict(material_layering),
                "subsurface_rendering": dict(subsurface_rendering),
                "hair_groom_rendering": dict(hair_groom_rendering),
                "cloth_sheen_rendering": dict(cloth_sheen_rendering),
                "glint_sparkle_rendering": dict(glint_sparkle_rendering),
                "caustics_rendering": dict(caustics_rendering),
                "anisotropic_rendering": dict(anisotropic_rendering),
                "microsurface_rendering": dict(microsurface_rendering),
                "depth_of_field_rendering": dict(depth_of_field_rendering),
                "post_effects_rendering": dict(post_effects_rendering),
                "lens_effects_rendering": dict(lens_effects_rendering),
                "lens_flare_rendering": dict(lens_flare_rendering),
                "render_passes": dict(render_passes),
                "motion_blur": dict(motion_blur),
                "udim_rendering": dict(udim_rendering),
                "triplanar_rendering": dict(triplanar_rendering),
                "errors": list(diag.get("errors") or []),
            }
        except Exception as exc:
            report["smoke_render"] = {
                "ok": False,
                "errors": [f"{type(exc).__name__}: {exc}"],
            }
        if not (report.get("smoke_render") or {}).get("ok"):
            report["full_gpu_export_available"] = False
            report["worker_safe"] = False
            blockers = list(report.get("blockers") or [])
            if "service_smoke_render_failed" not in blockers:
                blockers.append("service_smoke_render_failed")
            report["blockers"] = blockers
    return report


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Validate AR/PBR full GPU export service readiness.")
    parser.add_argument("--out", default="debugCapture/ar_pbr_full_gpu_export_service_qa.json")
    parser.add_argument("--probe", action="store_true", help="Run the configured service command with --probe.")
    parser.add_argument("--smoke-render", action="store_true", help="Render one synthetic AR/PBR frame through the helper.")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    args = parser.parse_args()

    report = run_ar_pbr_full_gpu_export_service_qa(
        probe=bool(args.probe),
        smoke_render=bool(args.smoke_render),
        timeout_seconds=max(1, int(args.timeout_seconds or 10)),
    )
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    _write_json(out_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    print(f"report: {out_path}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
