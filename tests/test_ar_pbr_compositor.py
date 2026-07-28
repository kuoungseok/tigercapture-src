import numpy as np

from app.ar_pbr.compositor import composite_export_frame, composite_preview_frame
from app.ar_pbr import export_packet_renderer as export_renderer
from app.ar_pbr.export_packet_renderer import render_gpu_packet_export_frame, render_offscreen_gpu_export_frame
from app.ar_pbr.schema import normalize_ar_track, track_active_at


def _track(**overrides):
    data = {
        "id": "ar_pbr_001",
        "type": "ar_pbr_object",
        "asset_path": "model.glb",
        "start_ms": 0,
        "end_ms": 1000,
        "transform": {
            "position": [0, 0, 0],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1],
        },
        "occlusion": True,
        "shadow_catcher": False,
        "reflection_catcher": False,
        "material": {
            "base_color": [1.0, 0.0, 0.0, 1.0],
            "roughness": 0.3,
            "metallic": 0.1,
        },
    }
    data.update(overrides)
    return data


def test_ar_track_schema_normalizes_defaults():
    from app.ar_pbr.shadow import DEFAULT_SHADOW_STRENGTH

    track = normalize_ar_track({"asset_path": "car.fbx", "duration_ms": 2000})

    assert track["id"] == "ar_pbr_001"
    assert track["type"] == "ar_pbr_object"
    assert track["end_ms"] == 2000
    assert track["occlusion"] is True
    assert track["shadow_catcher"] is True
    assert track["material_override"] is False
    assert track["placement"]["mode"] == "manual"
    assert track["render"]["lighting"]["shadow_strength"] == DEFAULT_SHADOW_STRENGTH
    assert track["render"]["lighting"]["render_passes_enabled"] is False
    assert "beauty" in track["render"]["lighting"]["render_pass_names"]
    assert track["render"]["lighting"]["motion_blur_enabled"] is False
    assert track["render"]["lighting"]["motion_blur_samples"] == 1
    assert track["render"]["lighting"]["lens_effects_enabled"] is False
    assert track["render"]["lighting"]["chromatic_aberration_enabled"] is False
    assert track["render"]["lighting"]["lens_flare_enabled"] is False
    assert track["render"]["lighting"]["aperture_flare_enabled"] is False
    assert track["render"]["lighting"]["caustics_enabled"] is False
    assert track["render"]["lighting"]["depth_edge_glow_enabled"] is False
    assert track["render"]["lighting"]["depth_edge_glow_strength"] == 0.0
    assert track["render"]["lighting"]["ray_gi_detail_enabled"] is False
    assert track["render"]["lighting"]["ray_gi_denoise_channels"] == ["beauty"]
    assert track_active_at(track, 1999)
    assert not track_active_at(track, 2000)


def test_lighting_schema_normalizes_depth_edge_glow_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "depth_edge_glow_enabled": True,
        "depth_edge_glow_strength": 0.72,
        "depth_edge_glow_radius_px": 5.5,
        "depth_edge_glow_color": [0.2, 0.9, 1.4],
    })

    assert lighting["depth_edge_glow_enabled"] is True
    assert lighting["depth_edge_glow_strength"] == 0.72
    assert lighting["depth_edge_glow_radius_px"] == 5.5
    assert lighting["depth_edge_glow_color"] == [0.2, 0.9, 1.0]


def test_lighting_schema_normalizes_pcss_spot_shadow_map_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "shadow_filter": "PCSS",
        "shadow_light_type": "spotlight",
        "shadow_map_size": 4099,
        "shadow_pcf_radius": 13.0,
        "shadow_pcss_blocker_radius": 4.25,
        "shadow_bias": 0.004,
        "shadow_normal_bias": 0.006,
        "shadow_spot_inner_angle": 33.0,
        "shadow_spot_outer_angle": 48.0,
    })

    assert lighting["shadow_filter"] == "pcss"
    assert lighting["shadow_light_type"] == "spot"
    assert lighting["shadow_map_size"] == 4096
    assert lighting["shadow_pcf_radius"] == 12.0
    assert lighting["shadow_pcss_blocker_radius"] == 4.25
    assert lighting["shadow_bias"] == 0.004
    assert lighting["shadow_normal_bias"] == 0.006
    assert lighting["shadow_spot_inner_angle"] == 33.0
    assert lighting["shadow_spot_outer_angle"] == 48.0


def test_lighting_schema_normalizes_catcher_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "shadow_catcher_opacity": 1.4,
        "contact_shadow_softness": 0.7,
        "shadow_matte_alpha": 0.18,
        "reflection_opacity": 0.62,
        "reflection_catcher_roughness": 0.74,
        "reflection_blur": 0.66,
        "contact_reflection": 0.44,
        "contact_reflection_falloff": 0.03,
    })

    assert lighting["shadow_catcher_opacity"] == 1.0
    assert lighting["shadow_catcher_softness"] == 0.7
    assert lighting["shadow_catcher_matte_alpha"] == 0.18
    assert lighting["reflection_catcher_opacity"] == 0.62
    assert lighting["reflection_catcher_roughness"] == 0.74
    assert lighting["reflection_catcher_softness"] == 0.66
    assert lighting["contact_reflection_strength"] == 0.44
    assert lighting["contact_reflection_falloff"] == 0.05


def test_lighting_schema_normalizes_color_management_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "tone_map": "AgX",
        "tone_exposure": 9.0,
        "white_balance": 4200,
        "tone_gamma": 0.02,
    })

    assert lighting["tone_mapping"] == "agx"
    assert lighting["tone_exposure"] == 8.0
    assert lighting["tone_white_balance"] == 4200.0
    assert lighting["tone_gamma"] == 0.1


def test_lighting_schema_normalizes_hybrid_rendering_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "hybrid_accumulation": True,
        "render_samples": 20,
        "diffuse_gi_strength": 0.35,
        "specular_gi_strength": 0.22,
        "denoise_strength": 0.45,
        "denoise_radius": 2,
    })

    assert lighting["hybrid_render_mode"] == "hybrid"
    assert lighting["hybrid_accumulation_enabled"] is True
    assert lighting["hybrid_accumulation_samples"] == 20
    assert lighting["diffuse_gi_strength"] == 0.35
    assert lighting["specular_gi_strength"] == 0.22
    assert lighting["denoise_strength"] == 0.45
    assert lighting["denoise_radius"] == 2


def test_lighting_schema_normalizes_ray_gi_detail_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "ray_gi_detail": {
            "mode": "path-traced",
            "diffuse_bounces": 4,
            "specular_bounces": 5,
            "refraction_bounces": 6,
            "max_bounces": 7,
            "direct_radiance_clamp": 8.5,
            "indirect_radiance_clamp": 3.25,
            "advanced_light_sampling": True,
            "light_sampling_mode": "multiple_importance",
            "light_sample_count": 24,
            "environment_sample_count": 48,
            "denoise_channels": ["beauty", "diffuse", "specular", "transmission"],
            "denoise_albedo_guided": True,
            "denoise_normal_guided": True,
        }
    })

    assert lighting["ray_gi_detail_mode"] == "path_traced"
    assert lighting["ray_gi_detail_enabled"] is True
    assert lighting["ray_gi_max_bounces"] == 7
    assert lighting["ray_gi_diffuse_bounces"] == 4
    assert lighting["ray_gi_specular_bounces"] == 5
    assert lighting["ray_gi_refraction_bounces"] == 6
    assert lighting["ray_gi_direct_radiance_clamp"] == 8.5
    assert lighting["ray_gi_indirect_radiance_clamp"] == 3.25
    assert lighting["ray_gi_advanced_light_sampling"] is True
    assert lighting["ray_gi_light_sampling_mode"] == "mis"
    assert lighting["ray_gi_light_sample_count"] == 24
    assert lighting["ray_gi_environment_sample_count"] == 48
    assert lighting["ray_gi_mis_enabled"] is True
    assert lighting["ray_gi_importance_sampling"] is True
    assert lighting["ray_gi_denoise_channels"] == ["beauty", "diffuse", "specular", "transmission"]
    assert lighting["ray_gi_denoise_albedo_guided"] is True
    assert lighting["ray_gi_denoise_normal_guided"] is True


def test_lighting_schema_normalizes_caustics_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "caustics": {
            "mode": "glass",
            "strength": 0.48,
            "quality": "high",
            "sample_count": 30,
            "scale": 36.0,
            "focus": 0.72,
            "radius": 0.74,
            "threshold": 0.18,
            "tint": [1.0, 0.9, 0.58],
            "seed": 23,
        }
    })

    assert lighting["caustics_mode"] == "caustics"
    assert lighting["caustics_enabled"] is True
    assert lighting["caustics_strength"] == 0.48
    assert lighting["caustics_quality"] == "high"
    assert lighting["caustics_sample_count"] == 30
    assert lighting["caustics_scale"] == 36.0
    assert lighting["caustics_focus"] == 0.72
    assert lighting["caustics_radius"] == 0.74
    assert lighting["caustics_threshold"] == 0.18
    assert lighting["caustics_tint"] == [1.0, 0.9, 0.58]
    assert lighting["caustics_seed"] == 23


def test_lighting_schema_normalizes_anisotropic_material_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "anisotropic_material": {
            "mode": "thin_film",
            "strength": 0.46,
            "anisotropy": 0.62,
            "rotation": 28.0,
            "tangent_weight": 0.74,
            "clearcoat_anisotropy": 0.31,
            "thin_film_enabled": True,
            "thin_film_strength": 0.52,
            "thin_film_thickness_nm": 540.0,
            "thin_film_ior": 1.38,
            "thin_film_tint": [1.0, 0.82, 0.55],
            "newton_rings_strength": 0.24,
            "newton_rings_scale": 22.0,
            "seed": 17,
        }
    })

    assert lighting["anisotropic_mode"] == "anisotropic"
    assert lighting["anisotropic_enabled"] is True
    assert lighting["anisotropic_strength"] == 0.46
    assert lighting["anisotropy"] == 0.62
    assert lighting["anisotropic_rotation"] == 28.0
    assert lighting["anisotropic_tangent_weight"] == 0.74
    assert lighting["clearcoat_anisotropy"] == 0.31
    assert lighting["thin_film_enabled"] is True
    assert lighting["thin_film_strength"] == 0.52
    assert lighting["thin_film_thickness_nm"] == 540.0
    assert lighting["thin_film_ior"] == 1.38
    assert lighting["thin_film_tint"] == [1.0, 0.82, 0.55]
    assert lighting["newton_rings_strength"] == 0.24
    assert lighting["newton_rings_scale"] == 22.0
    assert lighting["anisotropic_seed"] == 17


def test_lighting_schema_normalizes_microsurface_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "advanced_microsurface": {
            "mode": "detail_normal",
            "detail_normal_strength": 0.52,
            "detail_normal_scale": 42.0,
            "detail_normal_blend": "overlay",
            "detail_normal_seed": 21,
            "micro_roughness_strength": 0.34,
            "micro_roughness_scale": 58.0,
            "micro_roughness_contrast": 0.44,
            "gloss_variation_strength": 0.29,
            "gloss_bias": 0.08,
            "specular_micro_occlusion": 0.22,
        }
    })

    assert lighting["microsurface_mode"] == "microsurface"
    assert lighting["microsurface_enabled"] is True
    assert lighting["detail_normal_enabled"] is True
    assert lighting["detail_normal_strength"] == 0.52
    assert lighting["detail_normal_scale"] == 42.0
    assert lighting["detail_normal_blend"] == "overlay"
    assert lighting["detail_normal_seed"] == 21
    assert lighting["micro_roughness_enabled"] is True
    assert lighting["micro_roughness_strength"] == 0.34
    assert lighting["micro_roughness_scale"] == 58.0
    assert lighting["micro_roughness_contrast"] == 0.44
    assert lighting["gloss_variation_strength"] == 0.29
    assert lighting["gloss_bias"] == 0.08
    assert lighting["specular_micro_occlusion"] == 0.22


def test_lighting_schema_normalizes_screen_ambient_occlusion_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "ambient_occlusion": {
            "mode": "SSAO",
            "strength": 0.64,
            "radius": 5.5,
            "distance": 0.72,
            "color": [0.04, 0.03, 0.02],
            "ambient": True,
            "diffuse": True,
            "specular": True,
        }
    })

    assert lighting["ambient_occlusion_mode"] == "screen"
    assert lighting["ambient_occlusion_enabled"] is True
    assert lighting["ao_strength"] == 0.64
    assert lighting["ao_radius"] == 5.5
    assert lighting["ao_distance"] == 0.72
    assert lighting["ao_color"] == [0.04, 0.03, 0.02]
    assert lighting["ao_ambient"] is True
    assert lighting["ao_diffuse"] is True
    assert lighting["ao_specular"] is True


def test_lighting_schema_normalizes_final_motion_blur_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "motion_blur": {
            "enabled": True,
            "samples": 7,
            "shutter_angle": 270,
            "strength": 0.8,
            "camera_motion_px": [8, -3],
        },
        "frame_duration_ms": 40,
    })

    assert lighting["motion_blur_mode"] == "final"
    assert lighting["motion_blur_enabled"] is True
    assert lighting["motion_blur_samples"] == 7
    assert lighting["motion_blur_shutter_angle"] == 270.0
    assert lighting["motion_blur_shutter_ms"] == 30.0
    assert lighting["motion_blur_strength"] == 0.8
    assert lighting["camera_motion_px"] == [8.0, -3.0]


def test_lighting_schema_normalizes_transmission_refraction_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "transmission": {
            "enabled": True,
            "amount": 0.58,
            "refraction_strength": 0.44,
            "refraction_depth_px": 9.0,
            "ior": 1.52,
            "thickness": 0.24,
            "absorption_color": [0.76, 0.92, 1.0],
            "absorption_distance": 1.7,
            "roughness_blur_strength": 0.31,
        }
    })

    assert lighting["transmission_mode"] == "transmission"
    assert lighting["transmission_enabled"] is True
    assert lighting["transmission"] == 0.58
    assert lighting["refraction_strength"] == 0.44
    assert lighting["refraction_depth_px"] == 9.0
    assert lighting["ior"] == 1.52
    assert lighting["thickness"] == 0.24
    assert lighting["absorption_color"] == [0.76, 0.92, 1.0]
    assert lighting["absorption_distance"] == 1.7
    assert lighting["roughness_blur_strength"] == 0.31


def test_lighting_schema_normalizes_clearcoat_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "clearcoat": {
            "enabled": True,
            "strength": 0.57,
            "roughness": 0.08,
            "ior": 1.58,
            "tint": [1.0, 0.94, 0.88],
        }
    })

    assert lighting["clearcoat_mode"] == "clearcoat"
    assert lighting["clearcoat_enabled"] is True
    assert lighting["clearcoat_strength"] == 0.57
    assert lighting["clearcoat_roughness"] == 0.08
    assert lighting["clearcoat_ior"] == 1.58
    assert lighting["clearcoat_tint"] == [1.0, 0.94, 0.88]


def test_lighting_schema_normalizes_surface_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "surface": {
            "mix": 0.62,
            "roughness": 0.27,
            "metallic": 0.74,
            "reflectance": 0.36,
        }
    })

    assert lighting["surface_override_strength"] == 0.62
    assert lighting["surface_roughness"] == 0.27
    assert lighting["surface_metallic"] == 0.74
    assert lighting["surface_reflectance"] == 0.36


def test_lighting_schema_normalizes_parallax_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "displacement": {
            "enabled": True,
            "strength": 0.52,
            "height_scale": 0.044,
            "height_center": 0.48,
            "steps": 5,
        }
    })

    assert lighting["parallax_mode"] == "parallax"
    assert lighting["parallax_enabled"] is True
    assert lighting["parallax_strength"] == 0.52
    assert lighting["parallax_depth"] == 0.044
    assert lighting["parallax_center"] == 0.48
    assert lighting["parallax_steps"] == 5


def test_lighting_schema_normalizes_displacement_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "geometry_displacement": {
            "mode": "vector",
            "height_strength": 0.55,
            "height_scale": 0.06,
            "height_center": 0.46,
            "vector_strength": 0.32,
            "vector_space": "tangent",
            "subdivision": "adaptive",
            "max_offset": 0.11,
            "parallax_fallback": True,
        }
    })

    assert lighting["displacement_mode"] == "displacement"
    assert lighting["displacement_enabled"] is True
    assert lighting["displacement_height_strength"] == 0.55
    assert lighting["displacement_height_scale"] == 0.06
    assert lighting["displacement_height_center"] == 0.46
    assert lighting["vector_displacement_strength"] == 0.32
    assert lighting["vector_displacement_space"] == "tangent"
    assert lighting["displacement_subdivision_mode"] == "adaptive"
    assert lighting["displacement_max_offset"] == 0.11
    assert lighting["displacement_parallax_fallback"] is True


def test_lighting_schema_normalizes_bevel_shader_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "rounded_edges": {
            "enabled": True,
            "strength": 0.53,
            "radius": 0.056,
            "edge_width": 0.095,
            "samples": 4,
        }
    })

    assert lighting["bevel_mode"] == "bevel"
    assert lighting["bevel_enabled"] is True
    assert lighting["bevel_strength"] == 0.53
    assert lighting["bevel_radius"] == 0.056
    assert lighting["bevel_edge_width"] == 0.095
    assert lighting["bevel_samples"] == 4


def test_lighting_schema_normalizes_material_layering_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "material_layer": {
            "enabled": True,
            "blend": 0.61,
            "color": [0.9, 0.4, 0.12],
            "roughness": 0.31,
            "metallic": 0.18,
            "alpha": 0.88,
            "emissive_strength": 0.12,
            "mask_strength": 0.77,
        }
    })

    assert lighting["material_layer_mode"] == "layered"
    assert lighting["material_layer_enabled"] is True
    assert lighting["material_layer_blend"] == 0.61
    assert lighting["material_layer_color"] == [0.9, 0.4, 0.12]
    assert lighting["material_layer_roughness"] == 0.31
    assert lighting["material_layer_metallic"] == 0.18
    assert lighting["material_layer_alpha"] == 0.88
    assert lighting["material_layer_emissive_strength"] == 0.12
    assert lighting["material_layer_mask_strength"] == 0.77


def test_lighting_schema_normalizes_subsurface_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "subsurface": {
            "enabled": True,
            "strength": 0.52,
            "color": [1.0, 0.55, 0.32],
            "radius": 0.48,
            "power": 2.7,
            "wrap": 0.56,
            "thickness": 0.18,
        }
    })

    assert lighting["subsurface_mode"] == "subsurface"
    assert lighting["subsurface_enabled"] is True
    assert lighting["subsurface_strength"] == 0.52
    assert lighting["subsurface_color"] == [1.0, 0.55, 0.32]
    assert lighting["subsurface_radius"] == 0.48
    assert lighting["subsurface_power"] == 2.7
    assert lighting["subsurface_wrap"] == 0.56
    assert lighting["subsurface_thickness"] == 0.18


def test_lighting_schema_normalizes_hair_groom_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "hair_groom": {
            "enabled": True,
            "strength": 0.54,
            "tint": [1.0, 0.82, 0.45],
            "primary_shift": 0.07,
            "secondary_shift": -0.22,
            "primary_roughness": 0.21,
            "secondary_roughness": 0.47,
            "secondary_strength": 0.58,
            "anisotropy": 0.84,
            "rim_strength": 0.19,
        }
    })

    assert lighting["hair_groom_mode"] == "hair"
    assert lighting["hair_groom_enabled"] is True
    assert lighting["hair_groom_strength"] == 0.54
    assert lighting["hair_groom_tint"] == [1.0, 0.82, 0.45]
    assert lighting["hair_primary_shift"] == 0.07
    assert lighting["hair_secondary_shift"] == -0.22
    assert lighting["hair_primary_roughness"] == 0.21
    assert lighting["hair_secondary_roughness"] == 0.47
    assert lighting["hair_secondary_strength"] == 0.58
    assert lighting["hair_anisotropy"] == 0.84
    assert lighting["hair_rim_strength"] == 0.19


def test_lighting_schema_normalizes_cloth_sheen_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "cloth_sheen": {
            "enabled": True,
            "strength": 0.49,
            "color": [0.82, 0.90, 1.0],
            "roughness": 0.63,
            "edge_tint": [0.66, 0.78, 1.0],
            "fiber_strength": 0.31,
            "wrap": 0.37,
            "retroreflection": 0.27,
        }
    })

    assert lighting["cloth_sheen_mode"] == "sheen"
    assert lighting["cloth_sheen_enabled"] is True
    assert lighting["cloth_sheen_strength"] == 0.49
    assert lighting["cloth_sheen_color"] == [0.82, 0.9, 1.0]
    assert lighting["cloth_sheen_roughness"] == 0.63
    assert lighting["cloth_sheen_edge_tint"] == [0.66, 0.78, 1.0]
    assert lighting["cloth_sheen_fiber_strength"] == 0.31
    assert lighting["cloth_sheen_wrap"] == 0.37
    assert lighting["cloth_sheen_retroreflection"] == 0.27


def test_lighting_schema_normalizes_glint_sparkle_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "glint_sparkle": {
            "enabled": True,
            "strength": 0.51,
            "color": [1.0, 0.91, 0.68],
            "density": 0.43,
            "scale": 38.0,
            "threshold": 0.41,
            "sharpness": 17.0,
            "roughness_jitter": 0.59,
        }
    })

    assert lighting["glint_mode"] == "sparkle"
    assert lighting["glint_enabled"] is True
    assert lighting["glint_strength"] == 0.51
    assert lighting["glint_color"] == [1.0, 0.91, 0.68]
    assert lighting["glint_density"] == 0.43
    assert lighting["glint_scale"] == 38.0
    assert lighting["glint_threshold"] == 0.41
    assert lighting["glint_sharpness"] == 17.0
    assert lighting["glint_roughness_jitter"] == 0.59


def test_lighting_schema_normalizes_depth_of_field_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "depth_of_field": {
            "enabled": True,
            "strength": 0.57,
            "focus_depth": 0.24,
            "focus_range": 0.06,
            "max_blur_px": 8.0,
            "near_blur": 0.72,
            "far_blur": 1.18,
            "bokeh_shape": "round",
        }
    })

    assert lighting["depth_of_field_mode"] == "depth_of_field"
    assert lighting["depth_of_field_enabled"] is True
    assert lighting["depth_of_field_strength"] == 0.57
    assert lighting["dof_focus_depth"] == 0.24
    assert lighting["dof_focus_range"] == 0.06
    assert lighting["dof_max_blur_px"] == 8.0
    assert lighting["dof_near_blur"] == 0.72
    assert lighting["dof_far_blur"] == 1.18
    assert lighting["dof_bokeh_shape"] == "round"


def test_lighting_schema_normalizes_post_effects_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "post_effects": {
            "enabled": True,
            "bloom_strength": 0.44,
            "bloom_radius": 3.5,
            "bloom_threshold": 0.39,
            "bloom_anamorphic_strength": 1.2,
            "bloom_anamorphic_threshold": 0.71,
            "bloom_anamorphic_ratio": 6.0,
            "vignette_strength": 0.21,
            "vignette_radius": 0.67,
            "vignette_feather": 0.31,
            "grain_strength": 0.04,
            "grain_scale": 88,
            "grain_seed": 12,
            "sharpen_strength": 0.27,
            "sharpen_radius": 0.85,
        }
    })

    assert lighting["post_effects_mode"] == "post_effects"
    assert lighting["post_effects_enabled"] is True
    assert lighting["bloom_enabled"] is True
    assert lighting["bloom_strength"] == 0.44
    assert lighting["bloom_radius"] == 3.5
    assert lighting["bloom_threshold"] == 0.39
    assert lighting["bloom_anamorphic_strength"] == 1.2
    assert lighting["bloom_anamorphic_threshold"] == 0.71
    assert lighting["bloom_anamorphic_ratio"] == 6.0
    assert lighting["vignette_enabled"] is True
    assert lighting["vignette_strength"] == 0.21
    assert lighting["vignette_radius"] == 0.67
    assert lighting["vignette_feather"] == 0.31
    assert lighting["grain_enabled"] is True
    assert lighting["grain_strength"] == 0.04
    assert lighting["grain_scale"] == 88.0
    assert lighting["grain_seed"] == 12
    assert lighting["sharpen_enabled"] is True
    assert lighting["sharpen_strength"] == 0.27
    assert lighting["sharpen_radius"] == 0.85


def test_lighting_schema_normalizes_lens_effects_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "lens_effects": {
            "distortion_strength": 0.22,
            "distortion_k2": 0.05,
            "chromatic_aberration_strength": 0.48,
            "chromatic_aberration_px": 2.6,
            "center": [0.52, 0.47],
            "edge_falloff": 1.25,
        }
    })

    assert lighting["lens_effects_mode"] == "lens_effects"
    assert lighting["lens_effects_enabled"] is True
    assert lighting["lens_distortion_enabled"] is True
    assert lighting["lens_distortion_strength"] == 0.22
    assert lighting["lens_distortion_k2"] == 0.05
    assert lighting["chromatic_aberration_enabled"] is True
    assert lighting["chromatic_aberration_strength"] == 0.48
    assert lighting["chromatic_aberration_px"] == 2.6
    assert lighting["lens_center"] == [0.52, 0.47]
    assert lighting["lens_edge_falloff"] == 1.25


def test_lighting_schema_normalizes_lens_flare_settings():
    from app.ar_pbr.schema import normalize_lighting_settings

    lighting = normalize_lighting_settings({
        "lens_flare": {
            "flare_strength": 0.41,
            "flare_threshold": 0.33,
            "flare_radius": 4.4,
            "ghost_count": 5,
            "ghost_spacing": 0.37,
            "flare_tint": [1.0, 0.82, 0.48],
            "aperture_flare_strength": 0.29,
            "aperture_blades": 7,
            "aperture_rotation": 16.0,
            "aperture_radius": 21.0,
            "dirt_strength": 0.18,
            "dirt_density": 0.43,
            "dirt_scale": 82.0,
            "scratch_strength": 0.14,
            "scratch_density": 0.31,
            "scratch_length": 0.64,
            "seed": 19,
        }
    })

    assert lighting["lens_flare_mode"] == "lens_flare"
    assert lighting["lens_flare_enabled"] is True
    assert lighting["lens_flare_strength"] == 0.41
    assert lighting["lens_flare_threshold"] == 0.33
    assert lighting["lens_flare_radius"] == 4.4
    assert lighting["lens_flare_ghost_count"] == 5
    assert lighting["lens_flare_ghost_spacing"] == 0.37
    assert lighting["lens_flare_tint"] == [1.0, 0.82, 0.48]
    assert lighting["aperture_flare_enabled"] is True
    assert lighting["aperture_flare_strength"] == 0.29
    assert lighting["aperture_flare_blades"] == 7
    assert lighting["aperture_flare_rotation_deg"] == 16.0
    assert lighting["aperture_flare_radius"] == 21.0
    assert lighting["lens_dirt_enabled"] is True
    assert lighting["lens_dirt_strength"] == 0.18
    assert lighting["lens_dirt_density"] == 0.43
    assert lighting["lens_dirt_scale"] == 82.0
    assert lighting["lens_scratch_enabled"] is True
    assert lighting["lens_scratch_strength"] == 0.14
    assert lighting["lens_scratch_density"] == 0.31
    assert lighting["lens_scratch_length"] == 0.64
    assert lighting["lens_flare_seed"] == 19


def test_ar_track_schema_preserves_lighting_settings():
    track = normalize_ar_track({
        "asset_path": "car.fbx",
        "render": {
            "render_profile": "marmoset_pbr",
            "shadow_quality": "preview",
            "lighting": {
                "ibl_exposure": 2.0,
                "ibl_rotation": 0.25,
                "light_azimuth": -30.0,
                "light_elevation": 20.0,
                "direct_strength": 1.2,
                "shadow_strength": 0.75,
                "ground_height": -0.2,
            },
        },
    })

    assert track["render"]["shadow_quality"] == "preview"
    assert track["render"]["render_profile"] == "marmoset_pbr"
    assert track["render"]["lighting"]["ibl_exposure"] == 2.0
    assert track["render"]["lighting"]["light_azimuth"] == -30.0
    assert track["render"]["lighting"]["shadow_strength"] == 0.75


def test_video_exporter_ar_pbr_settings_include_public_asset_support(tmp_path):
    from app.video_exporter import VideoExportThread

    asset = tmp_path / "model.glb"
    track = _track(id="ar_pbr_002", asset_path=str(asset))
    descriptor = {
        "source_path": str(asset),
        "source_ext": ".glb",
        "source_format": "glb",
        "import_state": "ready",
        "backend": "internal_gltf",
        "geometries": [{"triangle_count": 1, "triangles": [[0, 1, 2]]}],
        "materials": [{"name": "mat", "base_texture": "mat.png"}],
        "texture_count": 1,
    }
    exporter = VideoExportThread(
        source_path=tmp_path / "in.mp4",
        out_path=tmp_path / "out.mp4",
        segments=[(0, 1000, 1.0)],
        ar_pbr_tracks=[track],
        ar_pbr_asset_descriptors={str(asset): descriptor},
    )

    settings = exporter._ar_pbr_export_settings(exporter._ar_pbr_tracks)

    assert settings["asset_support"][0]["label"] == "Ready: realtime PBR"
    assert settings["asset_support"][0]["ok_for_export"] is True
    assert "issue_codes" not in settings["asset_support"][0]


def test_preview_noop_returns_original_frame_when_renderer_unavailable():
    base = np.zeros((32, 32, 3), dtype=np.uint8)

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution=None,
    )

    assert out is base
    assert diag["fallback"] is True
    assert diag["mode"] == "noop"
    assert "native ar_pbr renderer unavailable" in diag["warnings"]


def test_preview_full_gpu_renderer_routes_through_model_view_service(monkeypatch):
    base = np.zeros((32, 32, 3), dtype=np.uint8)
    called = {}

    def fake_render(frame, *, time_ms, ar_tracks, camera_solution, depth_frame=None, settings=None):
        called["time_ms"] = time_ms
        called["tracks"] = ar_tracks
        called["settings"] = settings
        out = frame.copy()
        out[:, :, 1] = 80
        return out, {
            "ok": True,
            "mode": "full_model_view_gpu_export_service",
            "fallback": False,
            "rendered_track_count": 1,
            "renderer_quality": "full_model_view_gpu_pbr",
        }

    monkeypatch.setattr(export_renderer, "render_offscreen_gpu_export_frame", fake_render)

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution=None,
        settings={"renderer": "full_gpu"},
    )

    assert called["time_ms"] == 100
    assert called["settings"]["quality"] == "preview"
    assert out[:, :, 1].max() == 80
    assert diag["mode"] == "full_model_view_gpu_export_service"
    assert diag["requested_renderer"] == "full_gpu"
    assert diag["renderer_quality"] == "full_model_view_gpu_pbr"
    assert diag["fallback"] is False


def test_preview_full_gpu_renderer_keeps_packet_fallback_warning(monkeypatch):
    base = np.zeros((32, 32, 3), dtype=np.uint8)

    def fake_render(frame, *, time_ms, ar_tracks, camera_solution, depth_frame=None, settings=None):
        out = frame.copy()
        out[:, :, 0] = 64
        return out, {
            "ok": True,
            "mode": "offscreen_gpu_requested_packet_fallback",
            "fallback": True,
            "rendered_track_count": 1,
            "renderer_quality": "preview_packet_pbr_material_maps",
            "warnings": [],
        }

    monkeypatch.setattr(export_renderer, "render_offscreen_gpu_export_frame", fake_render)

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution=None,
        settings={"renderer": "model_view_gpu"},
    )

    assert out[:, :, 0].max() == 64
    assert diag["requested_renderer"] == "full_gpu"
    assert diag["fallback"] is True
    assert "full GPU renderer fell back to packet renderer" in diag["warnings"]


def test_synthetic_preview_and_export_match():
    base = np.zeros((64, 64, 3), dtype=np.uint8)
    depth = np.ones((64, 64), dtype=np.float32)
    settings = {"renderer": "synthetic", "shadow_blur": 0}

    preview, pdiag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(shadow_catcher=True)],
        camera_solution={"id": "cam_001"},
        depth_frame=depth,
        settings=settings,
    )
    export, ediag = composite_export_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(shadow_catcher=True)],
        camera_solution={"id": "cam_001"},
        depth_frame=depth,
        settings=settings,
    )

    np.testing.assert_array_equal(preview, export)
    assert pdiag["rendered_track_count"] == 1
    assert ediag["rendered_track_count"] == 1
    assert pdiag["camera_solution_id"] == "cam_001"


def test_depth_occlusion_masks_nearer_video_pixels():
    base = np.zeros((64, 64, 3), dtype=np.uint8)
    depth = np.ones((64, 64), dtype=np.float32)
    depth[:, :32] = 0.0

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution={"id": "cam_001"},
        depth_frame=depth,
        settings={
            "renderer": "synthetic",
            "synthetic_color": [255, 0, 0, 255],
            "shadow_blur": 0,
        },
    )

    assert diag["synthetic_renderer"]["depth_occlusion"] is True
    assert out[32, 24, 0] == 0
    assert out[32, 38, 0] == 255


def test_software_pbr_renders_asset_descriptor_mesh():
    base = np.zeros((96, 96, 3), dtype=np.uint8)
    depth = np.ones((96, 96), dtype=np.float32)
    descriptor = {
        "id": "asset_triangle",
        "geometries": [
            {
                "name": "triangle",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {
                    "center": [0, 0, 0],
                    "size": [2, 2, 1],
                },
            }
        ],
        "materials": [
            {
                "base_color": [0.0, 1.0, 0.2, 1.0],
                "roughness": 0.2,
                "metallic": 0.0,
                "reflectance": 0.4,
            }
        ],
    }

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path="triangle.fbx")],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=depth,
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {"triangle.fbx": descriptor},
            "shadow_blur": 0,
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "software_pbr"
    assert diag["rendered_track_count"] == 1
    assert diag["software_renderer"]["triangle_count"] == 1
    assert out.sum() > 0


def test_software_pbr_tints_material_from_base_texture(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "textured_scene.gltf"
    texture = tmp_path / "paint.png"
    asset.write_text("{}", encoding="utf-8")
    Image.new("RGB", (8, 8), (24, 82, 210)).save(texture)
    descriptor = {
        "id": "textured_triangle",
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Paint",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "roughness": 0.35,
                "metallic": 0.0,
            }
        ],
        "texture_count": 1,
    }

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path=str(asset), material_override=False)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {str(asset): descriptor},
            "shadow_blur": 0,
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "software_pbr"
    assert diag["software_renderer"]["texture_tinted_triangle_count"] == 1
    assert diag["software_renderer"]["texture_sampled_triangle_count"] == 1
    assert diag["software_renderer"]["texture_plans"][0]["base_map_count"] == 1
    assert int(out[:, :, 2].max()) > int(out[:, :, 0].max())


def test_software_pbr_uses_shared_material_uv_transform_precedence(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "uv_priority_scene.gltf"
    texture = tmp_path / "atlas.png"
    asset.write_text("{}", encoding="utf-8")
    atlas = Image.new("RGB", (4, 4), (8, 8, 8))
    atlas.putpixel((0, 0), (240, 24, 18))
    atlas.putpixel((3, 3), (20, 42, 240))
    atlas.save(texture)
    descriptor = {
        "id": "uv_priority_triangle",
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.9, 0.1], [0.9, 0.1], [0.9, 0.1]],
                "uv_sets": {
                    "1": [[0.2, 0.2], [0.2, 0.2], [0.2, 0.2]],
                },
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Atlas",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "base_uv_set": 1,
                "uv_transform": {"offset": [0.1, 0.9], "scale": [0.0, 0.0], "rotation": 0.0},
                "base_uv_transform": {"offset": [0.9, 0.1], "scale": [0.0, 0.0], "rotation": 0.0},
                "roughness": 0.35,
                "metallic": 0.0,
            }
        ],
        "texture_count": 1,
    }

    out, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path=str(asset), occlusion=False, material_override=False)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {str(asset): descriptor},
            "shadow_blur": 0,
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "software_pbr"
    assert diag["software_renderer"]["texture_sampled_triangle_count"] == 1
    assert int(out[:, :, 0].max()) > int(out[:, :, 2].max())


def test_software_pbr_preview_and_export_match():
    base = np.zeros((96, 96, 3), dtype=np.uint8)
    settings = {
        "renderer": "software_pbr",
        "shadow_blur": 0,
        "camera_z": 3.0,
        "asset_descriptors": {
            "model.glb": {
                "geometries": [
                    {
                        "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                        "triangles": [[0, 1, 2]],
                        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
                    }
                ]
            }
        },
    }

    preview, pdiag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution=None,
        settings=settings,
    )
    export, ediag = composite_export_frame(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution=None,
        settings=settings,
    )

    np.testing.assert_array_equal(preview, export)
    assert pdiag["mode"] == "software_pbr"
    assert ediag["mode"] == "software_pbr"


def test_gpu_packet_export_renderer_rasterizes_preview_packets():
    base = np.zeros((96, 96, 3), dtype=np.uint8)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [1.0, 0.35, 0.12, 1.0]}],
    }

    out, diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path="model.glb", shadow_catcher=True)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "renderer": "software_pbr",
            "asset_descriptors": {"model.glb": descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "gpu_packet_export"
    assert diag["rendered_track_count"] == 1
    assert diag["mesh_triangle_count"] >= 1
    assert diag["ssaa_scale"] >= 1
    assert out.sum() > 0


def test_gpu_packet_export_renderer_surfaces_texture_plan(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "textured_body.glb"
    asset.write_bytes(b"placeholder")
    hdri = tmp_path / "directional_env.hdr"
    export_renderer._HDRI_ARRAY_CACHE[str(hdri)] = np.asarray(
        [
            [[0.95, 0.12, 0.10], [0.15, 0.85, 0.24], [0.12, 0.18, 0.90], [0.85, 0.80, 0.18]],
            [[0.28, 0.40, 0.92], [0.90, 0.54, 0.18], [0.20, 0.88, 0.78], [0.72, 0.22, 0.86]],
        ],
        dtype=np.float32,
    )
    export_renderer._HDRI_AVERAGE_CACHE.pop(str(hdri), None)
    export_renderer._HDRI_PREFILTER_CACHE.pop(str(hdri), None)
    texture = tmp_path / "body_bodyd.png"
    roughness = tmp_path / "body_roughness.png"
    metallic = tmp_path / "body_metallic.png"
    occlusion = tmp_path / "body_bodyao.png"
    emissive = tmp_path / "body_emissive.png"
    opacity = tmp_path / "body_opacity.png"
    height = tmp_path / "body_height.png"
    Image.new("RGB", (4, 4), (30, 220, 110)).save(texture)
    Image.new("L", (4, 4), 148).save(roughness)
    Image.new("L", (4, 4), 96).save(metallic)
    Image.new("L", (4, 4), 90).save(occlusion)
    Image.new("RGB", (4, 4), (255, 48, 16)).save(emissive)
    Image.new("L", (4, 4), 210).save(opacity)
    Image.new("L", (4, 4), 188).save(height)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [1.0, 0.0, 0.0, 1.0],
                "base_texture": str(texture),
                "roughness_texture": str(roughness),
                "metallic_texture": str(metallic),
                "occlusion_texture": str(occlusion),
                "emissive_texture": str(emissive),
                "opacity_texture": str(opacity),
                "height_texture": str(height),
                "alpha_cutoff": 0.05,
                "emissive_factor": [0.8, 0.15, 0.05],
            }
        ],
    }

    out, diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[
            _track(
                asset_path=str(asset),
                shadow_catcher=False,
                render={"lighting": {
                    "hdri_path": str(hdri),
                    "ibl_exposure": 1.0,
                    "hybrid_accumulation": True,
                    "accumulation_samples": 10,
                    "diffuse_gi_strength": 0.31,
                    "specular_gi_strength": 0.17,
                    "denoise_strength": 0.40,
                    "ray_gi_detail": {
                        "mode": "hybrid",
                        "max_bounces": 6,
                        "diffuse_bounces": 3,
                        "specular_bounces": 4,
                        "refraction_bounces": 5,
                        "direct_radiance_clamp": 1.25,
                        "indirect_radiance_clamp": 0.88,
                        "advanced_light_sampling": True,
                        "light_sampling_mode": "mis",
                        "light_sample_count": 18,
                        "environment_sample_count": 32,
                        "denoise_channels": ["beauty", "diffuse", "specular"],
                        "denoise_albedo_guided": True,
                        "denoise_normal_guided": True,
                    },
                    "ao_strength": 0.36,
                    "ao_radius": 4.5,
                    "ao_distance": 0.55,
                    "ao_specular": True,
                    "transmission": 0.46,
                    "refraction_strength": 0.52,
                    "refraction_depth_px": 7.0,
                    "ior": 1.5,
                    "thickness": 0.2,
                    "absorption_color": [0.82, 0.95, 1.0],
                    "roughness_blur_strength": 0.2,
                    "clearcoat_strength": 0.43,
                    "clearcoat_roughness": 0.09,
                    "clearcoat_ior": 1.53,
                    "clearcoat_tint": [1.0, 0.95, 0.9],
                    "parallax_mode": "pom",
                    "parallax_strength": 0.48,
                    "parallax_depth": 0.04,
                    "parallax_center": 0.5,
                    "parallax_steps": 4,
                    "displacement_height_strength": 0.54,
                    "displacement_height_scale": 0.05,
                    "displacement_height_center": 0.49,
                    "vector_displacement_strength": 0.22,
                    "vector_displacement_space": "tangent",
                    "displacement_subdivision_mode": "adaptive",
                    "displacement_max_offset": 0.10,
                    "displacement_parallax_fallback": True,
                    "bevel_strength": 0.46,
                    "bevel_radius": 0.052,
                    "bevel_edge_width": 0.10,
                    "bevel_samples": 4,
                    "material_layer_blend": 0.44,
                    "material_layer_color": [0.93, 0.38, 0.12],
                    "material_layer_roughness": 0.33,
                    "material_layer_metallic": 0.14,
                    "material_layer_alpha": 0.91,
                    "material_layer_emissive_strength": 0.08,
                    "material_layer_mask_strength": 0.8,
                    "subsurface_strength": 0.39,
                    "subsurface_color": [1.0, 0.57, 0.34],
                    "subsurface_radius": 0.44,
                    "subsurface_power": 2.3,
                    "subsurface_wrap": 0.51,
                    "subsurface_thickness": 0.15,
                    "hair_groom_strength": 0.41,
                    "hair_groom_tint": [1.0, 0.84, 0.48],
                    "hair_primary_shift": 0.08,
                    "hair_secondary_shift": -0.21,
                    "hair_primary_roughness": 0.22,
                    "hair_secondary_roughness": 0.45,
                    "hair_secondary_strength": 0.54,
                    "hair_anisotropy": 0.81,
                    "hair_rim_strength": 0.2,
                    "cloth_sheen_strength": 0.42,
                    "cloth_sheen_color": [0.84, 0.90, 1.0],
                    "cloth_sheen_roughness": 0.61,
                    "cloth_sheen_edge_tint": [0.68, 0.80, 1.0],
                    "cloth_sheen_fiber_strength": 0.29,
                    "cloth_sheen_wrap": 0.36,
                    "cloth_sheen_retroreflection": 0.30,
                    "glint_strength": 0.38,
                    "glint_color": [1.0, 0.93, 0.70],
                    "glint_density": 0.48,
                    "glint_scale": 36.0,
                    "glint_threshold": 0.38,
                    "glint_sharpness": 15.0,
                    "glint_roughness_jitter": 0.57,
                    "caustics_strength": 0.44,
                    "caustics_quality": "high",
                    "caustics_sample_count": 22,
                    "caustics_scale": 34.0,
                    "caustics_focus": 0.68,
                    "caustics_radius": 0.82,
                    "caustics_threshold": 0.08,
                    "caustics_tint": [1.0, 0.91, 0.62],
                    "caustics_seed": 13,
                    "anisotropic_strength": 0.47,
                    "anisotropy": 0.66,
                    "anisotropic_rotation": 24.0,
                    "anisotropic_tangent_weight": 0.78,
                    "clearcoat_anisotropy": 0.34,
                    "thin_film_enabled": True,
                    "thin_film_strength": 0.58,
                    "thin_film_thickness_nm": 520.0,
                    "thin_film_ior": 1.42,
                    "thin_film_tint": [1.0, 0.84, 0.58],
                    "newton_rings_strength": 0.22,
                    "newton_rings_scale": 24.0,
                    "anisotropic_seed": 19,
                    "detail_normal_strength": 0.44,
                    "detail_normal_scale": 46.0,
                    "detail_normal_blend": "reoriented",
                    "detail_normal_seed": 29,
                    "micro_roughness_strength": 0.36,
                    "micro_roughness_scale": 52.0,
                    "micro_roughness_contrast": 0.42,
                    "gloss_variation_strength": 0.28,
                    "gloss_bias": 0.08,
                    "specular_micro_occlusion": 0.18,
                    "render_passes_enabled": True,
                    "triplanar_strength": 1.0,
                    "triplanar_scale": 1.25,
                    "triplanar_blend_sharpness": 4.0,
                }},
            )
        ],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
            "render_pass_output_dir": str(tmp_path / "render_passes"),
        },
    )

    assert diag["mode"] == "gpu_packet_export"
    assert diag["texture_map_count"] >= 1
    assert diag["texture_material_count"] == 1
    assert diag["texture_tinted_triangle_count"] == 1
    assert diag["texture_triangle_count"] == 1
    assert diag["texture_sampled_triangle_count"] == 1
    assert diag["packet_pbr_triangle_count"] == 1
    assert diag["pbr_triangle_count"] == 1
    assert diag["pbr_sampled_triangle_count"] == 1
    assert diag["pbr_hdri_directional_sampling"] is True
    assert diag["pbr_hdri_sampled_pixels"] > 0
    assert diag["pbr_prefiltered_ibl"] is True
    assert diag["pbr_prefiltered_ibl_pixels"] > 0
    assert diag["pbr_prefiltered_ibl_level_count"] >= 2
    assert diag["pbr_occlusion_map_applied"] is True
    assert diag["pbr_occlusion_map_pixels"] > 0
    assert diag["pbr_opacity_map_applied"] is True
    assert diag["pbr_opacity_map_pixels"] > 0
    assert diag["pbr_emissive_map_applied"] is True
    assert diag["pbr_emissive_map_pixels"] > 0
    assert diag["pbr_hybrid_rendering"]["schema"] == "tigerstudio.ar_pbr.hybrid_rendering.v1"
    assert diag["pbr_hybrid_rendering"]["enabled"] is True
    assert diag["pbr_hybrid_rendering"]["sample_count"] == 10
    assert diag["pbr_diffuse_gi"] is True
    assert diag["pbr_specular_gi"] is True
    assert diag["pbr_ray_gi_detail"]["schema"] == "tigerstudio.ar_pbr.ray_gi_detail.v1"
    assert diag["pbr_ray_gi_detail"]["enabled"] is True
    assert diag["pbr_ray_gi_detail"]["max_bounces"] == 6
    assert diag["pbr_ray_gi_detail"]["diffuse_bounces"] == 3
    assert diag["pbr_ray_gi_detail"]["specular_bounces"] == 4
    assert diag["pbr_ray_gi_detail"]["refraction_bounces"] == 5
    assert diag["pbr_ray_gi_detail"]["light_sampling_mode"] == "mis"
    assert diag["pbr_ray_gi_detail"]["light_sample_count"] == 18
    assert diag["pbr_ray_gi_detail"]["environment_sample_count"] == 32
    assert diag["pbr_ray_gi_detail"]["denoise_channels"] == ["beauty", "diffuse", "specular"]
    assert diag["pbr_ray_gi_direct_clamp_applied"] is True
    assert diag["pbr_ray_gi_indirect_clamp_applied"] is True
    assert diag["pbr_ray_gi_denoise_channels"] == ["beauty", "diffuse", "specular"]
    assert diag["pbr_denoise_applied"] is True
    assert diag["pbr_hybrid_accumulated_pixels"] > 0
    assert diag["pbr_ambient_occlusion_rendering"]["schema"] == "tigerstudio.ar_pbr.ambient_occlusion.v1"
    assert diag["pbr_ambient_occlusion_rendering"]["enabled"] is True
    assert diag["pbr_ambient_occlusion_rendering"]["mode"] == "screen"
    assert diag["pbr_ambient_occlusion_applied"] is True
    assert diag["pbr_ambient_occlusion_pixels"] > 0
    assert diag["pbr_ambient_occlusion_changed_pixels"] > 0
    assert diag["pbr_ambient_occlusion_pass"]["mean"] < 1.0
    assert diag["pbr_transmission_rendering"]["schema"] == "tigerstudio.ar_pbr.transmission.v1"
    assert diag["pbr_transmission_rendering"]["enabled"] is True
    assert diag["pbr_transmission_rendering"]["transmission"] == 0.46
    assert diag["pbr_refraction_applied"] is True
    assert diag["pbr_refraction_pixels"] > 0
    assert diag["pbr_clearcoat_rendering"]["schema"] == "tigerstudio.ar_pbr.clearcoat.v1"
    assert diag["pbr_clearcoat_rendering"]["enabled"] is True
    assert diag["pbr_clearcoat_rendering"]["strength"] == 0.43
    assert diag["pbr_clearcoat_applied"] is True
    assert diag["pbr_clearcoat_pixels"] > 0
    assert diag["pbr_parallax_rendering"]["schema"] == "tigerstudio.ar_pbr.parallax.v1"
    assert diag["pbr_parallax_rendering"]["enabled"] is True
    assert diag["pbr_parallax_rendering"]["mode"] == "pom"
    assert diag["pbr_parallax_rendering"]["strength"] == 0.48
    assert diag["pbr_parallax_applied"] is True
    assert diag["pbr_parallax_pixels"] > 0
    assert diag["pbr_parallax_sampling"] == "single_offset_fallback"
    assert diag["pbr_displacement_rendering"]["schema"] == "tigerstudio.ar_pbr.displacement.v1"
    assert diag["pbr_displacement_rendering"]["enabled"] is True
    assert diag["pbr_displacement_rendering"]["height_strength"] == 0.54
    assert diag["pbr_displacement_rendering"]["vector_strength"] == 0.22
    assert diag["pbr_displacement_applied"] is True
    assert diag["pbr_displacement_pixels"] > 0
    assert diag["pbr_displacement_height_pixels"] > 0
    assert diag["pbr_displacement_max_offset"] > 0.0
    assert diag["pbr_displacement_parallax_fallback"] is True
    assert diag["pbr_bevel_rendering"]["schema"] == "tigerstudio.ar_pbr.bevel.v1"
    assert diag["pbr_bevel_rendering"]["enabled"] is True
    assert diag["pbr_bevel_rendering"]["strength"] == 0.46
    assert diag["pbr_bevel_applied"] is True
    assert diag["pbr_bevel_pixels"] > 0
    assert diag["pbr_material_layering"]["schema"] == "tigerstudio.ar_pbr.material_layering.v1"
    assert diag["pbr_material_layering"]["enabled"] is True
    assert diag["pbr_material_layering"]["blend"] == 0.44
    assert diag["pbr_material_layer_applied"] is True
    assert diag["pbr_material_layer_pixels"] > 0
    assert diag["pbr_subsurface_rendering"]["schema"] == "tigerstudio.ar_pbr.subsurface.v1"
    assert diag["pbr_subsurface_rendering"]["enabled"] is True
    assert diag["pbr_subsurface_rendering"]["strength"] == 0.39
    assert diag["pbr_subsurface_applied"] is True
    assert diag["pbr_subsurface_pixels"] > 0
    assert diag["pbr_hair_groom_rendering"]["schema"] == "tigerstudio.ar_pbr.hair_groom.v1"
    assert diag["pbr_hair_groom_rendering"]["enabled"] is True
    assert diag["pbr_hair_groom_rendering"]["strength"] == 0.41
    assert diag["pbr_hair_groom_applied"] is True
    assert diag["pbr_hair_groom_pixels"] > 0
    assert diag["pbr_cloth_sheen_rendering"]["schema"] == "tigerstudio.ar_pbr.cloth_sheen.v1"
    assert diag["pbr_cloth_sheen_rendering"]["enabled"] is True
    assert diag["pbr_cloth_sheen_rendering"]["strength"] == 0.42
    assert diag["pbr_cloth_sheen_applied"] is True
    assert diag["pbr_cloth_sheen_pixels"] > 0
    assert diag["pbr_glint_sparkle_rendering"]["schema"] == "tigerstudio.ar_pbr.glint_sparkle.v1"
    assert diag["pbr_glint_sparkle_rendering"]["enabled"] is True
    assert diag["pbr_glint_sparkle_rendering"]["strength"] == 0.38
    assert diag["pbr_glint_sparkle_applied"] is True
    assert diag["pbr_glint_sparkle_pixels"] > 0
    assert diag["pbr_caustics_rendering"]["schema"] == "tigerstudio.ar_pbr.caustics.v1"
    assert diag["pbr_caustics_rendering"]["enabled"] is True
    assert diag["pbr_caustics_rendering"]["strength"] == 0.44
    assert diag["pbr_caustics_rendering"]["quality"] == "high"
    assert diag["pbr_caustics_applied"] is True
    assert diag["pbr_caustics_pixels"] > 0
    assert diag["pbr_caustics_max_intensity"] > 0.0
    assert diag["pbr_anisotropic_rendering"]["schema"] == "tigerstudio.ar_pbr.anisotropic_material.v1"
    assert diag["pbr_anisotropic_rendering"]["enabled"] is True
    assert diag["pbr_anisotropic_rendering"]["strength"] == 0.47
    assert diag["pbr_anisotropic_rendering"]["anisotropy"] == 0.66
    assert diag["pbr_anisotropic_rendering"]["clearcoat_anisotropy"] == 0.34
    assert diag["pbr_anisotropic_rendering"]["thin_film_enabled"] is True
    assert diag["pbr_anisotropic_rendering"]["thin_film_strength"] == 0.58
    assert diag["pbr_anisotropic_applied"] is True
    assert diag["pbr_anisotropic_pixels"] > 0
    assert diag["pbr_anisotropic_max_intensity"] > 0.0
    assert diag["pbr_microsurface_rendering"]["schema"] == "tigerstudio.ar_pbr.microsurface.v1"
    assert diag["pbr_microsurface_rendering"]["enabled"] is True
    assert diag["pbr_microsurface_rendering"]["detail_normal_strength"] == 0.44
    assert diag["pbr_microsurface_rendering"]["micro_roughness_strength"] == 0.36
    assert diag["pbr_detail_normal_applied"] is True
    assert diag["pbr_detail_normal_pixels"] > 0
    assert diag["pbr_detail_normal_max_delta"] > 0.0
    assert diag["pbr_micro_roughness_applied"] is True
    assert diag["pbr_micro_roughness_pixels"] > 0
    assert diag["pbr_micro_roughness_mean"] > 0.0
    assert diag["pbr_triplanar_rendering"]["schema"] == "tigerstudio.ar_pbr.triplanar.v1"
    assert diag["pbr_triplanar_rendering"]["enabled"] is True
    assert diag["pbr_triplanar_rendering"]["scale"] == 1.25
    assert diag["pbr_triplanar_applied"] is True
    assert diag["pbr_triplanar_pixels"] > 0
    assert diag["renderer_quality"] == "preview_packet_pbr_material_maps"
    assert diag["packet_builder"]["gpu_renderer"]["texture_sampling"] == "gl_preview_pbr_triplanar_projection"
    assert diag["packet_builder"]["gpu_renderer"]["hair_groom_rendering"] == "hair"
    assert diag["packet_builder"]["gpu_renderer"]["cloth_sheen_rendering"] == "sheen"
    assert diag["packet_builder"]["gpu_renderer"]["glint_sparkle_rendering"] == "sparkle"
    assert diag["packet_builder"]["gpu_renderer"]["caustics_rendering"] == "caustics"
    assert diag["packet_builder"]["gpu_renderer"]["caustics_samples"] == 22
    assert diag["packet_builder"]["gpu_renderer"]["anisotropic_rendering"] == "anisotropic"
    assert diag["packet_builder"]["gpu_renderer"]["thin_film_strength"] == 0.58
    assert diag["packet_builder"]["gpu_renderer"]["displacement_rendering"] == "displacement"
    assert diag["packet_builder"]["gpu_renderer"]["displacement_fallback"] == "parallax_mapping"
    assert diag["packet_builder"]["gpu_renderer"]["microsurface_rendering"] == "microsurface"
    assert diag["packet_builder"]["gpu_renderer"]["detail_normal_strength"] == 0.44
    assert diag["packet_builder"]["gpu_renderer"]["micro_roughness_strength"] == 0.36
    assert diag["packet_builder"]["gpu_renderer"]["ray_gi_detail"] == "hybrid"
    assert diag["packet_builder"]["gpu_renderer"]["ray_gi_bounces"] == 6
    assert diag["packet_builder"]["gpu_renderer"]["ray_gi_light_sampling"] == "mis"
    assert diag["packet_builder"]["gpu_renderer"]["triplanar_rendering"] == "triplanar"
    assert diag["packet_builder"]["gpu_renderer"]["render_passes"] == "packet_render_pass_export_contract"
    assert diag["packet_builder"]["gpu_renderer"]["render_pass_count"] >= 19
    assert diag["packet_builder"]["gpu_renderer"]["pbr_preview"] == "gl_model_view_material_map_pbr_packet_ready"
    render_passes = diag["pbr_render_passes"]
    assert render_passes["schema"] == "tigerstudio.ar_pbr.render_passes.output.v1"
    assert render_passes["enabled"] is True
    assert render_passes["pass_count"] >= 19
    assert render_passes["written_count"] >= 19
    for pass_name in (
        "beauty",
        "alpha_mask",
        "depth",
        "normal",
        "position",
        "material_id",
        "object_id",
        "ambient_occlusion",
        "albedo",
        "roughness",
        "metallic",
        "emissive",
    ):
        row = render_passes["passes"][pass_name]
        assert row["path"]
        assert (tmp_path / "render_passes" / f"{pass_name}.png").is_file()
        assert row["changed_pixels"] > 0
    assert render_passes["passes"]["direct_lighting"]["policy"] == "beauty_packet_split_approximation"
    assert render_passes["passes"]["ambient_occlusion"]["policy"] == "screen_space_packet_approximation"
    assert out.sum() > 0


def test_gpu_packet_export_renderer_accumulates_motion_blur_samples(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "animated_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "animated_base.png"
    Image.new("RGBA", (8, 8), (210, 74, 32, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "id": "animated_mesh",
                "model_id": "animated_model",
                "vertices": [[-0.9, -0.8, 0.0], [0.9, -0.8, 0.0], [0.0, 0.9, 0.0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [1.8, 1.7, 1]},
            }
        ],
        "models": [{"id": "animated_model", "translation": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1]}],
        "materials": [
            {
                "name": "AnimatedPaint",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "animation_count": 1,
        "animation_clips": [
            {
                "id": "move_right",
                "name": "move_right",
                "duration_ms": 1000,
                "model_curves": {
                    "animated_model": {
                        "translation": {
                            "x": [[0, 0.0], [1000, 1.6]],
                            "y": [[0, 0.0], [1000, 0.0]],
                            "z": [[0, 0.0], [1000, 0.0]],
                        }
                    }
                },
            }
        ],
    }
    track = _track(
        id="animated_motion_blur",
        asset_path=str(asset),
        shadow_catcher=False,
        reflection_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.5,
            },
        },
        animation={"clip": "move_right", "auto_play": True, "loop": True, "speed": 4.0},
    )
    camera_solution = {
        "id": "cam_001",
        "frame_size": [96, 96],
        "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
    }
    settings = {"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0, "frame_duration_ms": 1000.0 / 60.0}
    no_blur, no_blur_diag = render_gpu_packet_export_frame(
        base,
        time_ms=80,
        ar_tracks=[track],
        camera_solution=camera_solution,
        settings=settings,
    )
    blur_track = dict(track)
    blur_track["render"] = {
        "render_profile": "marmoset_pbr",
        "lighting": {
            "direct_strength": 1.0,
            "ibl_exposure": 0.5,
            "motion_blur_enabled": True,
            "motion_blur_samples": 5,
            "motion_blur_shutter_angle": 270.0,
        },
    }
    blurred, blur_diag = render_gpu_packet_export_frame(
        base,
        time_ms=80,
        ar_tracks=[blur_track],
        camera_solution=camera_solution,
        settings=settings,
    )

    assert no_blur_diag["pbr_motion_blur_applied"] is False
    assert blur_diag["pbr_motion_blur_rendering"]["schema"] == "tigerstudio.ar_pbr.motion_blur.v1"
    assert blur_diag["pbr_motion_blur_rendering"]["enabled"] is True
    assert blur_diag["pbr_motion_blur_sample_count"] == 5
    assert len(blur_diag["pbr_motion_blur_sample_times_ms"]) == 5
    assert blur_diag["pbr_motion_blur_applied"] is True
    assert blur_diag["pbr_motion_blur_changed_pixels"] > 0
    assert blur_diag["renderer_quality"].endswith("_motion_blur")
    assert int(np.abs(blurred.astype(np.int16) - no_blur.astype(np.int16)).sum()) > 0


def test_gpu_packet_export_renderer_samples_triplanar_projection(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "triplanar_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "axis_base.png"
    img = Image.new("RGBA", (8, 8), (24, 40, 220, 255))
    for x in range(4, 8):
        for y in range(8):
            img.putpixel((x, y), (235, 36, 24, 255))
    img.save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[0.58, -0.72, 0.0], [0.92, -0.72, 0.0], [0.58, 0.72, 0.0]],
                "uvs": [[0.10, 0.10], [0.10, 0.10], [0.10, 0.10]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0.75, 0.0, 0], "size": [0.4, 1.5, 1]},
            }
        ],
        "materials": [
            {
                "name": "ProjectedPaint",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.42,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }

    uv_out, uv_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[
            _track(
                asset_path=str(asset),
                shadow_catcher=False,
                render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.5}},
            )
        ],
        camera_solution={"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0},
    )
    tri_out, tri_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[
            _track(
                asset_path=str(asset),
                shadow_catcher=False,
                render={
                    "render_profile": "marmoset_pbr",
                    "lighting": {
                        "direct_strength": 1.0,
                        "ibl_exposure": 0.5,
                        "triplanar_strength": 1.0,
                        "triplanar_scale": 1.0,
                        "triplanar_blend_sharpness": 8.0,
                    },
                },
            )
        ],
        camera_solution={"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}},
        settings={"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0},
    )

    assert uv_diag["pbr_triplanar_applied"] is False
    assert tri_diag["pbr_triplanar_rendering"]["schema"] == "tigerstudio.ar_pbr.triplanar.v1"
    assert tri_diag["pbr_triplanar_rendering"]["enabled"] is True
    assert tri_diag["pbr_triplanar_applied"] is True
    assert tri_diag["pbr_triplanar_pixels"] > 0
    assert tri_diag["packet_builder"]["gpu_renderer"]["triplanar_rendering"] == "triplanar"
    assert tri_diag["packet_builder"]["gpu_renderer"]["texture_sampling"] == "gl_preview_pbr_triplanar_projection"
    tri_mask = tri_out.sum(axis=2) > 0
    uv_mask = uv_out.sum(axis=2) > 0
    assert bool(tri_mask.any())
    assert bool(uv_mask.any())
    assert float(tri_out[:, :, 0][tri_mask].mean()) > float(uv_out[:, :, 0][uv_mask].mean()) + 5.0
    assert float(tri_out[:, :, 0][tri_mask].mean()) > float(tri_out[:, :, 2][tri_mask].mean())


def test_gpu_packet_export_renderer_applies_subsurface_scattering(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "subsurface_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "skin_base.png"
    Image.new("RGBA", (8, 8), (210, 126, 82, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "SkinLike",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.5,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 0.9, "ibl_exposure": 0.8}},
    )
    track_sss = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 0.9,
                "ibl_exposure": 0.8,
                "subsurface_strength": 0.85,
                "subsurface_color": [1.0, 0.58, 0.36],
                "subsurface_radius": 0.55,
                "subsurface_wrap": 0.65,
                "subsurface_thickness": 0.22,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_sss, sss_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_sss],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_subsurface_applied"] is False
    assert sss_diag["pbr_subsurface_rendering"]["schema"] == "tigerstudio.ar_pbr.subsurface.v1"
    assert sss_diag["pbr_subsurface_rendering"]["enabled"] is True
    assert sss_diag["pbr_subsurface_applied"] is True
    assert sss_diag["pbr_subsurface_pixels"] > 0
    mask = out_sss.sum(axis=2) > 0
    assert bool(mask.any())
    assert float(out_sss[:, :, 0][mask].mean()) > float(out_base[:, :, 0][mask].mean())


def test_gpu_packet_export_renderer_applies_hair_groom_shading(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "hair_groom_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "hair_base.png"
    Image.new("RGBA", (8, 8), (92, 54, 28, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "HairLike",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.38,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 0.95, "ibl_exposure": 0.7}},
    )
    track_hair = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 0.95,
                "ibl_exposure": 0.7,
                "hair_groom_strength": 0.95,
                "hair_groom_tint": [1.0, 0.86, 0.48],
                "hair_primary_shift": 0.08,
                "hair_secondary_shift": -0.22,
                "hair_primary_roughness": 0.18,
                "hair_secondary_roughness": 0.42,
                "hair_secondary_strength": 0.62,
                "hair_anisotropy": 0.88,
                "hair_rim_strength": 0.22,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_hair, hair_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_hair],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_hair_groom_applied"] is False
    assert hair_diag["pbr_hair_groom_rendering"]["schema"] == "tigerstudio.ar_pbr.hair_groom.v1"
    assert hair_diag["pbr_hair_groom_rendering"]["enabled"] is True
    assert hair_diag["pbr_hair_groom_applied"] is True
    assert hair_diag["pbr_hair_groom_pixels"] > 0
    assert hair_diag["packet_builder"]["gpu_renderer"]["hair_groom_rendering"] == "hair"
    mask = out_hair.sum(axis=2) > 0
    assert bool(mask.any())
    assert int(out_hair[:, :, :3][mask].sum()) > int(out_base[:, :, :3][mask].sum())


def test_gpu_packet_export_renderer_applies_cloth_sheen(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "cloth_sheen_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "cloth_base.png"
    Image.new("RGBA", (8, 8), (74, 86, 138, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "ClothLike",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.72,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 0.9, "ibl_exposure": 0.7}},
    )
    track_cloth = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 0.9,
                "ibl_exposure": 0.7,
                "cloth_sheen_strength": 0.92,
                "cloth_sheen_color": [0.84, 0.92, 1.0],
                "cloth_sheen_roughness": 0.68,
                "cloth_sheen_edge_tint": [0.64, 0.78, 1.0],
                "cloth_sheen_fiber_strength": 0.38,
                "cloth_sheen_wrap": 0.42,
                "cloth_sheen_retroreflection": 0.34,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_cloth, cloth_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_cloth],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_cloth_sheen_applied"] is False
    assert cloth_diag["pbr_cloth_sheen_rendering"]["schema"] == "tigerstudio.ar_pbr.cloth_sheen.v1"
    assert cloth_diag["pbr_cloth_sheen_rendering"]["enabled"] is True
    assert cloth_diag["pbr_cloth_sheen_applied"] is True
    assert cloth_diag["pbr_cloth_sheen_pixels"] > 0
    assert cloth_diag["packet_builder"]["gpu_renderer"]["cloth_sheen_rendering"] == "sheen"
    mask = out_cloth.sum(axis=2) > 0
    assert bool(mask.any())
    assert int(out_cloth[:, :, :3][mask].sum()) > int(out_base[:, :, :3][mask].sum())


def test_gpu_packet_export_renderer_applies_glint_sparkle(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "glint_sparkle_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "sparkle_base.png"
    Image.new("RGBA", (8, 8), (52, 58, 70, 255)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "SparklePaint",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.28,
                "metallic": 0.18,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.7}},
    )
    track_glint = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.7,
                "glint_strength": 0.95,
                "glint_color": [1.0, 0.92, 0.64],
                "glint_density": 0.96,
                "glint_scale": 18.0,
                "glint_threshold": 0.04,
                "glint_sharpness": 2.0,
                "glint_roughness_jitter": 0.8,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_glint, glint_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_glint],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_glint_sparkle_applied"] is False
    assert glint_diag["pbr_glint_sparkle_rendering"]["schema"] == "tigerstudio.ar_pbr.glint_sparkle.v1"
    assert glint_diag["pbr_glint_sparkle_rendering"]["enabled"] is True
    assert glint_diag["pbr_glint_sparkle_applied"] is True
    assert glint_diag["pbr_glint_sparkle_pixels"] > 0
    assert glint_diag["packet_builder"]["gpu_renderer"]["glint_sparkle_rendering"] == "sparkle"
    mask = out_glint.sum(axis=2) > 0
    assert bool(mask.any())
    assert int(out_glint[:, :, :3][mask].sum()) > int(out_base[:, :, :3][mask].sum())


def test_gpu_packet_export_renderer_applies_depth_of_field(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "dof_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "checker_base.png"
    img = Image.new("RGBA", (16, 16), (32, 44, 180, 255))
    for y in range(16):
        for x in range(16):
            if (x // 2 + y // 2) % 2:
                img.putpixel((x, y), (230, 220, 60, 255))
    img.save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "DOFChecker",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.42,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.8}},
    )
    track_dof = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.8,
                "depth_of_field_strength": 1.0,
                "dof_focus_depth": 0.0,
                "dof_focus_range": 0.0,
                "dof_max_blur_px": 7.0,
                "dof_far_blur": 1.0,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_dof, dof_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_dof],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_depth_of_field_applied"] is False
    assert dof_diag["pbr_depth_of_field_rendering"]["schema"] == "tigerstudio.ar_pbr.depth_of_field.v1"
    assert dof_diag["pbr_depth_of_field_rendering"]["enabled"] is True
    assert dof_diag["pbr_depth_of_field_applied"] is True
    assert dof_diag["pbr_depth_of_field_pixels"] > 0
    assert dof_diag["packet_builder"]["gpu_renderer"]["depth_of_field_rendering"] == "depth_of_field"
    assert int(np.abs(out_dof.astype(np.int16) - out_base.astype(np.int16)).sum()) > 0


def test_gpu_packet_export_renderer_applies_post_effects(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "post_effects_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "bright_checker_base.png"
    img = Image.new("RGBA", (16, 16), (40, 48, 72, 255))
    for y in range(16):
        for x in range(16):
            if (x // 2 + y // 2) % 2:
                img.putpixel((x, y), (255, 244, 92, 255))
    img.save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "PostChecker",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.32,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.8}},
    )
    track_post = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.8,
                "bloom_strength": 0.45,
                "bloom_radius": 2.6,
                "bloom_threshold": 0.34,
                "vignette_strength": 0.28,
                "vignette_radius": 0.62,
                "vignette_feather": 0.32,
                "grain_strength": 0.06,
                "grain_scale": 64.0,
                "grain_seed": 23,
                "sharpen_strength": 0.32,
                "sharpen_radius": 0.8,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_post, post_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_post],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_post_effects_applied"] is False
    assert post_diag["pbr_post_effects_rendering"]["schema"] == "tigerstudio.ar_pbr.post_effects.v1"
    assert post_diag["pbr_post_effects_rendering"]["enabled"] is True
    assert post_diag["pbr_post_effects_rendering"]["bloom_method"] == "convolution"
    assert post_diag["pbr_post_effects_rendering"]["bloom_model"] == (
        "thresholded_convolution_bloom_with_peak_anamorphic_streaks"
    )
    assert post_diag["pbr_post_effects_applied"] is True
    assert post_diag["pbr_bloom_applied"] is True
    assert post_diag["pbr_vignette_applied"] is True
    assert post_diag["pbr_grain_applied"] is True
    assert post_diag["pbr_sharpen_applied"] is True
    assert post_diag["pbr_post_effects_pixels"] > 0
    assert post_diag["packet_builder"]["gpu_renderer"]["post_effects_rendering"] == "post_effects"
    assert int(np.abs(out_post.astype(np.int16) - out_base.astype(np.int16)).sum()) > 0


def test_gpu_packet_export_renderer_applies_lens_effects(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "lens_effects_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "lens_checker_base.png"
    img = Image.new("RGBA", (24, 24), (32, 40, 64, 255))
    for y in range(24):
        for x in range(24):
            if (x // 3 + y // 3) % 2:
                img.putpixel((x, y), (245, 80, 44, 255))
            elif x > y:
                img.putpixel((x, y), (40, 180, 255, 255))
    img.save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "LensChecker",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.36,
                "metallic": 0.0,
                "base_texture": str(texture),
                "pbr_available": True,
            }
        ],
        "texture_count": 1,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.8}},
    )
    track_lens = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.8,
                "lens_distortion_strength": 0.34,
                "lens_distortion_k2": 0.08,
                "chromatic_aberration_strength": 0.75,
                "chromatic_aberration_px": 4.0,
                "lens_edge_falloff": 1.3,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_lens, lens_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_lens],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_lens_effects_applied"] is False
    assert lens_diag["pbr_lens_effects_rendering"]["schema"] == "tigerstudio.ar_pbr.lens_effects.v1"
    assert lens_diag["pbr_lens_effects_rendering"]["enabled"] is True
    assert lens_diag["pbr_lens_effects_applied"] is True
    assert lens_diag["pbr_lens_distortion_applied"] is True
    assert lens_diag["pbr_chromatic_aberration_applied"] is True
    assert lens_diag["pbr_lens_effects_pixels"] > 0
    assert lens_diag["pbr_chromatic_aberration_max_offset_px"] > 0.0
    assert lens_diag["packet_builder"]["gpu_renderer"]["lens_effects_rendering"] == "lens_effects"
    assert int(np.abs(out_lens.astype(np.int16) - out_base.astype(np.int16)).sum()) > 0


def test_gpu_packet_export_renderer_applies_lens_flare(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "lens_flare_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "lens_flare_emissive_base.png"
    img = Image.new("RGBA", (24, 24), (32, 36, 54, 255))
    for y in range(24):
        for x in range(24):
            if abs(x - 17) <= 3 and abs(y - 7) <= 3:
                img.putpixel((x, y), (255, 246, 160, 255))
            elif (x // 4 + y // 4) % 2:
                img.putpixel((x, y), (92, 106, 160, 255))
    img.save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "LensFlareBright",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.22,
                "metallic": 0.0,
                "base_texture": str(texture),
                "emissive_texture": str(texture),
                "emissive_factor": [1.8, 1.6, 0.8],
                "pbr_available": True,
            }
        ],
        "texture_count": 2,
    }
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
    }
    track_base = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.0, "ibl_exposure": 0.9}},
    )
    track_flare = _track(
        asset_path=str(asset),
        shadow_catcher=False,
        render={
            "render_profile": "marmoset_pbr",
            "lighting": {
                "direct_strength": 1.0,
                "ibl_exposure": 0.9,
                "lens_flare_strength": 0.75,
                "lens_flare_threshold": 0.18,
                "lens_flare_radius": 4.0,
                "lens_flare_ghost_count": 4,
                "lens_flare_ghost_spacing": 0.34,
                "aperture_flare_strength": 0.52,
                "aperture_flare_blades": 6,
                "aperture_flare_rotation_deg": 18.0,
                "aperture_flare_radius": 18.0,
                "lens_dirt_strength": 0.24,
                "lens_dirt_density": 0.48,
                "lens_dirt_scale": 72.0,
                "lens_scratch_strength": 0.22,
                "lens_scratch_density": 0.36,
                "lens_scratch_length": 0.68,
                "lens_flare_seed": 7,
            },
        },
    )
    camera = {"id": "cam_001", "frame_size": [96, 96], "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48}}
    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        settings=common,
    )
    out_flare, flare_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_flare],
        camera_solution=camera,
        settings=common,
    )

    assert base_diag["pbr_lens_flare_applied"] is False
    assert flare_diag["pbr_lens_flare_rendering"]["schema"] == "tigerstudio.ar_pbr.lens_flare.v1"
    assert flare_diag["pbr_lens_flare_rendering"]["enabled"] is True
    assert flare_diag["pbr_lens_flare_applied"] is True
    assert flare_diag["pbr_flare_applied"] is True
    assert flare_diag["pbr_aperture_flare_applied"] is True
    assert flare_diag["pbr_lens_dirt_applied"] is True
    assert flare_diag["pbr_lens_scratch_applied"] is True
    assert flare_diag["pbr_lens_flare_ghost_count"] == 4
    assert flare_diag["pbr_lens_flare_pixels"] > 0
    assert flare_diag["packet_builder"]["gpu_renderer"]["lens_flare_rendering"] == "lens_flare"
    assert int(np.abs(out_flare.astype(np.int16) - out_base.astype(np.int16)).sum()) > 0


def test_gpu_packet_export_renderer_samples_udim_tiles(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "udim_body.glb"
    asset.write_bytes(b"placeholder")
    tile_1001 = tmp_path / "body_base.1001.png"
    tile_1002 = tmp_path / "body_base.1002.png"
    Image.new("RGBA", (8, 8), (20, 40, 220, 255)).save(tile_1001)
    Image.new("RGBA", (8, 8), (230, 48, 24, 255)).save(tile_1002)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[1.08, 0.08], [1.92, 0.12], [1.45, 0.88]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "UDIMPaint",
                "base_color": [1.0, 1.0, 1.0, 1.0],
                "roughness": 0.36,
                "metallic": 0.0,
                "base_texture": "body_base.<UDIM>.png",
                "pbr_available": True,
            }
        ],
        "texture_count": 2,
    }

    out, diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[
            _track(
                asset_path=str(asset),
                shadow_catcher=False,
                render={"render_profile": "marmoset_pbr", "lighting": {"direct_strength": 1.1, "ibl_exposure": 1.0}},
            )
        ],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "gpu_packet_export"
    assert diag["packet_builder"]["gpu_renderer"]["udim"] == "texture_plan_udim_tiles_ready"
    assert diag["packet_builder"]["gpu_renderer"]["udim_tile_count"] == 2
    assert diag["pbr_udim_rendering"]["schema"] == "tigerstudio.ar_pbr.udim.v1"
    assert diag["pbr_udim_rendering"]["enabled"] is True
    assert diag["pbr_udim_sampled_pixels"] > 0
    assert diag["pbr_udim_sampled_tile_count"] == 1
    assert diag["pbr_udim_sampled_tiles"] == [1002]
    assert diag["pbr_udim_missing_tile_pixels"] == 0
    assert float(out[:, :, 0].mean()) > float(out[:, :, 2].mean())


def test_gpu_packet_export_pbr_uses_depth_occlusion_mask(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "occluded_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    Image.new("RGB", (8, 8), (240, 70, 30)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [1.0, 0.25, 0.1, 1.0],
                "base_texture": str(texture),
            }
        ],
    }
    depth = np.ones((96, 96), dtype=np.float32)
    depth[:, :48] = 0.0

    out, diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path=str(asset), occlusion=True, shadow_catcher=False)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=depth,
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
            "occlusion_tolerance": 0.02,
        },
    )

    assert diag["mode"] == "gpu_packet_export"
    assert diag["pbr_sampled_triangle_count"] == 1
    assert diag["pbr_depth_occlusion_applied"] is True
    assert diag["pbr_depth_occluded_pixels"] > 0
    assert out.sum() > 0


def test_gpu_packet_export_pbr_adds_depth_edge_glow(tmp_path):
    from PIL import Image

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "depth_glow_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    Image.new("RGB", (8, 8), (80, 130, 210)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [0.3, 0.5, 0.8, 1.0],
                "base_texture": str(texture),
            }
        ],
    }
    depth = np.ones((96, 96), dtype=np.float32)
    depth[:, :48] = 0.0
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
        "occlusion_tolerance": 0.02,
        "occlusion_softness": 0.01,
    }
    camera = {
        "id": "cam_001",
        "frame_size": [96, 96],
        "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
    }
    track_base = _track(asset_path=str(asset), occlusion=True, shadow_catcher=False)
    track_glow = _track(
        asset_path=str(asset),
        occlusion=True,
        shadow_catcher=False,
        render={
            "lighting": {
                "depth_edge_glow_enabled": True,
                "depth_edge_glow_strength": 0.9,
                "depth_edge_glow_radius_px": 5.0,
                "depth_edge_glow_color": [0.35, 0.85, 1.0],
            }
        },
    )

    out_base, base_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_base],
        camera_solution=camera,
        depth_frame=depth,
        settings=common,
    )
    out_glow, glow_diag = render_gpu_packet_export_frame(
        base,
        time_ms=100,
        ar_tracks=[track_glow],
        camera_solution=camera,
        depth_frame=depth,
        settings=common,
    )

    assert base_diag["pbr_depth_edge_glow_applied"] is False
    assert glow_diag["pbr_depth_edge_glow"]["schema"] == "tigerstudio.ar_pbr.depth_edge_glow.v1"
    assert glow_diag["pbr_depth_edge_glow_applied"] is True
    assert glow_diag["pbr_depth_edge_glow_pixels"] > 0
    assert int(out_glow[:, :, :3].sum()) > int(out_base[:, :, :3].sum())


def test_depth_effect_masks_are_reusable_for_non_glow_effects():
    from app.ar_pbr.depth_occlusion import build_depth_effect_masks

    alpha = np.ones((16, 16), dtype=np.float32)
    depth = np.ones((16, 16), dtype=np.float32)
    depth[:, :8] = 0.0

    masks, diag = build_depth_effect_masks(
        alpha,
        depth,
        object_depth=0.5,
        settings={
            "occlusion_tolerance": 0.02,
            "occlusion_softness": 0.01,
            "depth_edge_glow_radius_px": 4.0,
        },
    )

    assert diag["schema"] == "tigerstudio.ar_pbr.depth_effect_masks.v1"
    assert diag["visible_pixels"] > 0
    assert diag["hidden_pixels"] > 0
    assert diag["edge_pixels"] > 0
    assert masks["visible_mask"].shape == (16, 16)
    assert masks["hidden_mask"].shape == (16, 16)
    assert masks["edge_mask"].shape == (16, 16)
    assert float(masks["edge_mask"].max()) <= 1.0


def test_gpu_packet_export_uses_item_live_depth_texture_when_global_depth_missing(tmp_path):
    from PIL import Image
    from app.ar_pbr.gpu_preview import build_gpu_preview_items

    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "live_depth_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    Image.new("RGB", (8, 8), (240, 70, 30)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [1.0, 0.25, 0.1, 1.0],
                "base_texture": str(texture),
            }
        ],
    }
    depth = np.ones((96, 96), dtype=np.float32)
    depth[:, :48] = 0.0
    common = {
        "asset_descriptors": {str(asset): descriptor},
        "camera_z": 3.0,
        "occlusion_tolerance": 0.02,
    }
    items, packet_diag = build_gpu_preview_items(
        frame_size=(96, 96),
        time_ms=100,
        ar_tracks=[_track(asset_path=str(asset), occlusion=True, shadow_catcher=False)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        depth_frame=depth,
        settings=common,
    )

    out, diag = export_renderer.rasterize_gpu_preview_items(
        base,
        items,
        settings=common,
        depth_frame=None,
    )

    assert packet_diag["gpu_renderer"]["depth_occlusion"] == "live_depth_texture_fragment"
    assert diag["pbr_live_depth_texture_item_count"] == 1
    assert diag["pbr_depth_occlusion_applied"] is True
    assert diag["pbr_depth_occluded_pixels"] > 0
    assert out.sum() > 0


def test_gpu_preview_items_preserve_material_uv_set_transform_for_opengl_path(tmp_path):
    from PIL import Image
    from app.ar_pbr.gpu_preview import build_gpu_preview_items

    asset = tmp_path / "multi_uv_scene.gltf"
    texture = tmp_path / "atlas.png"
    asset.write_text("{}", encoding="utf-8")
    Image.new("RGBA", (4, 4), (180, 90, 40, 255)).save(texture)
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[-0.5, -0.5, 1.0], [0.5, -0.5, 1.0], [-0.5, 0.5, 1.0]],
                "triangles": [[0, 1, 2]],
                "uvs": [[0.9, 0.9], [0.8, 0.8], [0.7, 0.7]],
                "uv_sets": {
                    "1": [[0.0, 0.0], [1.0, 0.0], [0.0, 1.0]],
                },
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "Atlas",
                "base_texture": str(texture),
                "base_uv_set": 1,
                "base_uv_transform": {
                    "offset": [0.1, 0.2],
                    "scale": [0.5, 0.25],
                    "rotation": 0.0,
                },
                "uv_v_flip": "1",
            }
        ],
    }

    items, diag = build_gpu_preview_items(
        frame_size=(64, 64),
        time_ms=0,
        ar_tracks=[_track(asset_path=str(asset), occlusion=False)],
        camera_solution={
            "frame_size": [64, 64],
            "intrinsics": {"fx": 50, "fy": 50, "cx": 32, "cy": 32},
        },
        settings={"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0},
    )

    pbr_vertices = items[0]["pbr_triangles"][0]["vertices"]
    pbr_maps = items[0]["pbr_triangles"][0]["maps"]
    assert diag["pbr_triangle_count"] == 1
    assert pbr_maps["uv_v_flip"] == "1"
    assert np.allclose(
        [
            pbr_vertices[2:4],
            pbr_vertices[25:27],
            pbr_vertices[48:50],
        ],
        [[0.1, 0.2], [0.6, 0.2], [0.1, 0.45]],
    )


def test_gpu_preview_pbr_packets_apply_base_color_factor_to_base_texture(tmp_path):
    from PIL import Image
    from app.ar_pbr.gpu_preview import build_gpu_preview_items

    base = np.zeros((64, 64, 3), dtype=np.uint8)
    asset = tmp_path / "factor_tinted_scene.gltf"
    texture = tmp_path / "factor_base.png"
    asset.write_text("{}", encoding="utf-8")
    Image.new("RGBA", (4, 4), (200, 120, 40, 255)).save(texture)
    descriptor = {
        "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
        "geometries": [
            {
                "id": "geom_0",
                "material_id": "mat_0",
                "vertices": [[-0.7, -0.7, 0.0], [0.7, -0.7, 0.0], [0.0, 0.7, 0.0]],
                "uvs": [[0.0, 0.0], [1.0, 0.0], [0.5, 1.0]],
                "triangles": [[0, 1, 2]],
            }
        ],
        "materials": [
            {
                "id": "mat_0",
                "name": "TintedPaint",
                "base_color": [0.5, 0.25, 1.0, 1.0],
                "base_texture": str(texture),
                "base_texture_source": "gltf_pbr_base_color_texture",
                "roughness": 0.42,
                "metallic": 0.0,
                "pbr_available": True,
            }
        ],
    }
    settings = {"asset_descriptors": {str(asset): descriptor}, "camera_z": 3.0}

    items, packet_diag = build_gpu_preview_items(
        frame_size=(64, 64),
        time_ms=0,
        ar_tracks=[_track(asset_path=str(asset), occlusion=False, material_override=False)],
        camera_solution={
            "frame_size": [64, 64],
            "intrinsics": {"fx": 55, "fy": 55, "cx": 32, "cy": 32},
        },
        settings=settings,
    )
    pbr_triangle = items[0]["pbr_triangles"][0]
    pbr_vertices = pbr_triangle["vertices"]

    assert packet_diag["pbr_triangle_count"] == 1
    assert pbr_triangle["base_color_factor"] == [0.5, 0.25, 1.0, 1.0]
    assert np.allclose(pbr_vertices[13:16], [0.5, 0.25, 1.0])

    out, diag = export_renderer.rasterize_gpu_preview_items(base, items, settings=settings)

    assert diag["pbr_base_color_factor_applied"] is True
    assert diag["pbr_base_color_factor_pixels"] > 0
    assert out.sum() > 0


def test_full_gpu_export_service_serializes_depth_frame_to_request(tmp_path, monkeypatch):
    import json
    import sys

    from app.ar_pbr.full_gpu_export_service import (
        FULL_GPU_EXPORT_SERVICE_COMMAND_ENV,
        render_frame_via_full_gpu_export_service,
    )

    fake_service = tmp_path / "fake_full_gpu_service.py"
    fake_service.write_text(
        """
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

request_path = Path(sys.argv[sys.argv.index("--request") + 1])
request = json.loads(request_path.read_text(encoding="utf-8"))
payload = request.get("depth_frame") or {}
depth = np.load(payload["path"])
Image.open(request["base_frame_path"]).convert("RGBA").save(request["output_frame_path"])
print(json.dumps({
    "ok": True,
    "mode": "full_model_view_gpu_export_service",
    "rendered_track_count": 1,
    "depth_payload_kind": payload.get("kind"),
    "depth_shape": list(depth.shape),
    "depth_min": float(depth.min()),
    "depth_max": float(depth.max()),
}))
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV, f'"{sys.executable}" "{fake_service}"')
    base = np.zeros((32, 48, 3), dtype=np.uint8)
    depth = np.ones((32, 48), dtype=np.float32)
    depth[:, :24] = 0.125

    _out, diag = render_frame_via_full_gpu_export_service(
        base,
        time_ms=100,
        ar_tracks=[_track()],
        camera_solution={},
        depth_frame=depth,
        settings={},
    )

    assert diag["ok"] is True
    assert diag["depth_payload_kind"] == "npy"
    assert diag["depth_shape"] == [32, 48]
    assert diag["depth_min"] == 0.125
    assert diag["depth_max"] == 1.0


def test_full_gpu_export_service_overlay_applies_depth_matte():
    from PIL import Image
    from tools.ar_pbr_full_gpu_export_service import _apply_depth_occlusion_to_overlay

    overlay = Image.new("RGBA", (20, 20), (255, 64, 32, 255))
    depth = np.ones((40, 40), dtype=np.float32)
    depth[:, :20] = 0.0

    out, diag = _apply_depth_occlusion_to_overlay(
        overlay,
        depth_frame=depth,
        rect=(10, 10, 30, 30),
        object_depth=0.5,
        settings={"occlusion_tolerance": 0.02},
    )

    alpha = np.asarray(out)[:, :, 3]
    assert diag["applied"] is True
    assert diag["occluded_pixels"] > 0
    assert int(alpha[:, :10].sum()) == 0
    assert int(alpha[:, 10:].sum()) > 0


def test_offscreen_gpu_export_request_uses_safe_packet_fallback(tmp_path, monkeypatch):
    from PIL import Image
    from app.ar_pbr.full_gpu_export_service import FULL_GPU_EXPORT_SERVICE_COMMAND_ENV

    monkeypatch.setenv(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV, str(tmp_path / "missing_service.exe"))
    base = np.zeros((96, 96, 3), dtype=np.uint8)
    asset = tmp_path / "gpu_requested_body.glb"
    asset.write_bytes(b"placeholder")
    texture = tmp_path / "body_bodyd.png"
    Image.new("RGB", (8, 8), (80, 180, 240)).save(texture)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "uvs": [[0, 0], [1, 0], [0.5, 1]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [
            {
                "name": "BodyPaint",
                "base_color": [0.1, 0.55, 1.0, 1.0],
                "base_texture": str(texture),
            }
        ],
    }

    out, diag = render_offscreen_gpu_export_frame(
        base,
        time_ms=100,
        ar_tracks=[_track(asset_path=str(asset), shadow_catcher=False)],
        camera_solution={
            "id": "cam_001",
            "frame_size": [96, 96],
            "intrinsics": {"fx": 90, "fy": 90, "cx": 48, "cy": 48},
        },
        settings={
            "asset_descriptors": {str(asset): descriptor},
            "camera_z": 3.0,
        },
    )

    assert diag["mode"] == "offscreen_gpu_requested_packet_fallback"
    assert diag["requested_renderer"] == "offscreen_gpu"
    assert diag["full_gpu_export_available"] is False
    assert diag["fallback_reason"] == "full_gpu_export_service_failed_or_unavailable"
    assert diag["renderer_quality_gap"] == "full_model_view_gpu_export_service_missing"
    assert "full_gpu_export_service_attempt" in diag
    assert diag["full_gpu_export_service"]["contract_ready"] is True
    assert "service_command_env" in diag["full_gpu_export_service"]
    assert "model-view GPU helper probe+smoke QA" in " ".join(diag["next_renderer_steps"])
    assert diag["pbr_sampled_triangle_count"] == 1
    assert out.sum() > 0


def test_full_gpu_export_service_contract_is_honest_without_probe(monkeypatch):
    from app.ar_pbr.full_gpu_export_service import (
        FULL_GPU_EXPORT_SERVICE_COMMAND_ENV,
        build_full_gpu_export_service_report,
        full_gpu_export_service_contract,
    )

    monkeypatch.delenv(FULL_GPU_EXPORT_SERVICE_COMMAND_ENV, raising=False)

    report = build_full_gpu_export_service_report(probe=False)

    assert report["ok"] is True
    assert report["contract_ready"] is True
    assert report["full_gpu_export_available"] is False
    assert report["service_command_env"] == FULL_GPU_EXPORT_SERVICE_COMMAND_ENV
    assert report["configured"] is True
    assert "service_probe_not_run" in report["blockers"]
    contract = full_gpu_export_service_contract()
    assert "hybrid_rendering" in contract["output"]["diagnostics_json"]
    assert "ray_gi_detail" in contract["output"]["diagnostics_json"]
    assert "ambient_occlusion_rendering" in contract["output"]["diagnostics_json"]
    assert "depth_occlusion" in contract["output"]["diagnostics_json"]
    assert "transmission_rendering" in contract["output"]["diagnostics_json"]
    assert "clearcoat_rendering" in contract["output"]["diagnostics_json"]
    assert "parallax_rendering" in contract["output"]["diagnostics_json"]
    assert "displacement_rendering" in contract["output"]["diagnostics_json"]
    assert "bevel_rendering" in contract["output"]["diagnostics_json"]
    assert "material_layering" in contract["output"]["diagnostics_json"]
    assert "udim_rendering" in contract["output"]["diagnostics_json"]
    assert "subsurface_rendering" in contract["output"]["diagnostics_json"]
    assert "hair_groom_rendering" in contract["output"]["diagnostics_json"]
    assert "cloth_sheen_rendering" in contract["output"]["diagnostics_json"]
    assert "glint_sparkle_rendering" in contract["output"]["diagnostics_json"]
    assert "caustics_rendering" in contract["output"]["diagnostics_json"]
    assert "anisotropic_rendering" in contract["output"]["diagnostics_json"]
    assert "microsurface_rendering" in contract["output"]["diagnostics_json"]
    assert "depth_of_field_rendering" in contract["output"]["diagnostics_json"]
    assert "post_effects_rendering" in contract["output"]["diagnostics_json"]
    assert "lens_effects_rendering" in contract["output"]["diagnostics_json"]
    assert "lens_flare_rendering" in contract["output"]["diagnostics_json"]


def test_full_gpu_export_service_process_env_unsets_offscreen_qpa_on_windows(monkeypatch):
    from app.ar_pbr.full_gpu_export_service import (
        FULL_GPU_EXPORT_SERVICE_QPA_ENV,
        FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV,
        _service_process_env,
    )

    monkeypatch.setattr("app.ar_pbr.full_gpu_export_service.os.name", "nt")

    env = _service_process_env({"QT_QPA_PLATFORM": "offscreen", "QT_OPENGL": "software"})
    assert env.get("QT_QPA_PLATFORM") != "offscreen"
    assert env["QT_OPENGL"] == "desktop"

    env = _service_process_env({
        "QT_QPA_PLATFORM": "offscreen",
        FULL_GPU_EXPORT_SERVICE_QPA_ENV: "windows",
        FULL_GPU_EXPORT_SERVICE_QT_OPENGL_ENV: "desktop",
    })
    assert env["QT_QPA_PLATFORM"] == "windows"
    assert env["QT_OPENGL"] == "desktop"


def test_software_pbr_uses_track_lighting_shadow_strength():
    base = np.full((96, 96, 3), 220, dtype=np.uint8)
    descriptor = {
        "geometries": [
            {
                "vertices": [[-1, -1, 0], [1, -1, 0], [0, 1, 0]],
                "triangles": [[0, 1, 2]],
                "bounds": {"center": [0, 0, 0], "size": [2, 2, 1]},
            }
        ],
        "materials": [{"base_color": [0.0, 0.6, 1.0, 1.0]}],
    }
    common_settings = {
        "renderer": "software_pbr",
        "asset_descriptors": {"model.glb": descriptor},
        "shadow_blur": 0,
        "camera_z": 3.0,
    }
    no_shadow_track = _track(
        shadow_catcher=True,
        render={"lighting": {"shadow_strength": 0.0}},
    )
    strong_shadow_track = _track(
        shadow_catcher=True,
        render={"lighting": {"shadow_strength": 1.0}},
    )

    no_shadow, _ = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[no_shadow_track],
        camera_solution=None,
        settings=common_settings,
    )
    strong_shadow, diag = composite_preview_frame(
        base,
        time_ms=100,
        ar_tracks=[strong_shadow_track],
        camera_solution=None,
        settings=common_settings,
    )

    assert diag["software_renderer"]["lighting"][0]["shadow_strength"] == 1.0
    assert strong_shadow.sum() < no_shadow.sum()
