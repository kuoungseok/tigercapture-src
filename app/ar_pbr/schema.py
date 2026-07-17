"""Schema helpers for AR/PBR object tracks."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from app.ar_pbr.animation import normalize_animation_settings
from app.ar_pbr.ambient_occlusion import (
    DEFAULT_AMBIENT_OCCLUSION_MODE,
    DEFAULT_AO_AMBIENT,
    DEFAULT_AO_COLOR,
    DEFAULT_AO_DIFFUSE,
    DEFAULT_AO_DISTANCE,
    DEFAULT_AO_RADIUS,
    DEFAULT_AO_SPECULAR,
    DEFAULT_AO_STRENGTH,
    flatten_ambient_occlusion_settings,
)
from app.ar_pbr.catcher import (
    DEFAULT_CONTACT_REFLECTION_FALLOFF,
    DEFAULT_CONTACT_REFLECTION_STRENGTH,
    DEFAULT_REFLECTION_CATCHER_OPACITY,
    DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
    DEFAULT_REFLECTION_CATCHER_SOFTNESS,
    DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
    DEFAULT_SHADOW_CATCHER_OPACITY,
    DEFAULT_SHADOW_CATCHER_SOFTNESS,
    flatten_catcher_settings,
)
from app.ar_pbr.anisotropy import (
    DEFAULT_ANISOTROPIC_MODE,
    DEFAULT_ANISOTROPIC_ROTATION,
    DEFAULT_ANISOTROPIC_SEED,
    DEFAULT_ANISOTROPIC_STRENGTH,
    DEFAULT_ANISOTROPIC_TANGENT_WEIGHT,
    DEFAULT_ANISOTROPY,
    DEFAULT_CLEARCOAT_ANISOTROPY,
    DEFAULT_NEWTON_RINGS_SCALE,
    DEFAULT_NEWTON_RINGS_STRENGTH,
    DEFAULT_THIN_FILM_IOR,
    DEFAULT_THIN_FILM_STRENGTH,
    DEFAULT_THIN_FILM_THICKNESS_NM,
    DEFAULT_THIN_FILM_TINT,
    flatten_anisotropic_material_settings,
)
from app.ar_pbr.microsurface import (
    DEFAULT_DETAIL_NORMAL_BLEND,
    DEFAULT_DETAIL_NORMAL_SCALE,
    DEFAULT_DETAIL_NORMAL_SEED,
    DEFAULT_DETAIL_NORMAL_STRENGTH,
    DEFAULT_GLOSS_BIAS,
    DEFAULT_GLOSS_VARIATION_STRENGTH,
    DEFAULT_MICRO_ROUGHNESS_CONTRAST,
    DEFAULT_MICRO_ROUGHNESS_SCALE,
    DEFAULT_MICRO_ROUGHNESS_STRENGTH,
    DEFAULT_MICROSURFACE_MODE,
    DEFAULT_SPECULAR_MICRO_OCCLUSION,
    flatten_microsurface_settings,
)
from app.ar_pbr.bevel import (
    DEFAULT_BEVEL_EDGE_WIDTH,
    DEFAULT_BEVEL_MODE,
    DEFAULT_BEVEL_RADIUS,
    DEFAULT_BEVEL_SAMPLES,
    DEFAULT_BEVEL_STRENGTH,
    flatten_bevel_settings,
)
from app.ar_pbr.clearcoat import (
    DEFAULT_CLEARCOAT_IOR,
    DEFAULT_CLEARCOAT_MODE,
    DEFAULT_CLEARCOAT_ROUGHNESS,
    DEFAULT_CLEARCOAT_STRENGTH,
    DEFAULT_CLEARCOAT_TINT,
    flatten_clearcoat_settings,
)
from app.ar_pbr.cloth import (
    DEFAULT_CLOTH_SHEEN_COLOR,
    DEFAULT_CLOTH_SHEEN_EDGE_TINT,
    DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH,
    DEFAULT_CLOTH_SHEEN_MODE,
    DEFAULT_CLOTH_SHEEN_RETROREFLECTION,
    DEFAULT_CLOTH_SHEEN_ROUGHNESS,
    DEFAULT_CLOTH_SHEEN_STRENGTH,
    DEFAULT_CLOTH_SHEEN_WRAP,
    flatten_cloth_sheen_settings,
)
from app.ar_pbr.glint import (
    DEFAULT_GLINT_COLOR,
    DEFAULT_GLINT_DENSITY,
    DEFAULT_GLINT_MODE,
    DEFAULT_GLINT_ROUGHNESS_JITTER,
    DEFAULT_GLINT_SCALE,
    DEFAULT_GLINT_SHARPNESS,
    DEFAULT_GLINT_STRENGTH,
    DEFAULT_GLINT_THRESHOLD,
    flatten_glint_sparkle_settings,
)
from app.ar_pbr.caustics import (
    DEFAULT_CAUSTICS_FOCUS,
    DEFAULT_CAUSTICS_MODE,
    DEFAULT_CAUSTICS_QUALITY,
    DEFAULT_CAUSTICS_RADIUS,
    DEFAULT_CAUSTICS_SAMPLE_COUNT,
    DEFAULT_CAUSTICS_SCALE,
    DEFAULT_CAUSTICS_SEED,
    DEFAULT_CAUSTICS_STRENGTH,
    DEFAULT_CAUSTICS_THRESHOLD,
    DEFAULT_CAUSTICS_TINT,
    flatten_caustics_settings,
)
from app.ar_pbr.depth_of_field import (
    DEFAULT_DEPTH_OF_FIELD_MODE,
    DEFAULT_DEPTH_OF_FIELD_STRENGTH,
    DEFAULT_DOF_BOKEH_SHAPE,
    DEFAULT_DOF_FAR_BLUR,
    DEFAULT_DOF_FOCUS_DEPTH,
    DEFAULT_DOF_FOCUS_RANGE,
    DEFAULT_DOF_MAX_BLUR_PX,
    DEFAULT_DOF_NEAR_BLUR,
    flatten_depth_of_field_settings,
)
from app.ar_pbr.depth_occlusion import (
    DEFAULT_DEPTH_EDGE_GLOW_COLOR,
    DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
    DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
    flatten_depth_edge_glow_settings,
)
from app.ar_pbr.post_effects import (
    DEFAULT_BLOOM_BOOST,
    DEFAULT_BLOOM_CONVOLUTION_SCALE,
    DEFAULT_BLOOM_KERNEL,
    DEFAULT_BLOOM_RADIUS,
    DEFAULT_BLOOM_SCATTER,
    DEFAULT_BLOOM_STRENGTH,
    DEFAULT_BLOOM_THRESHOLD,
    DEFAULT_GRAIN_SCALE,
    DEFAULT_GRAIN_SEED,
    DEFAULT_GRAIN_STRENGTH,
    DEFAULT_POST_EFFECTS_MODE,
    DEFAULT_SHARPEN_RADIUS,
    DEFAULT_SHARPEN_STRENGTH,
    DEFAULT_VIGNETTE_FEATHER,
    DEFAULT_VIGNETTE_RADIUS,
    DEFAULT_VIGNETTE_STRENGTH,
    flatten_post_effects_settings,
)
from app.ar_pbr.lens_effects import (
    DEFAULT_CHROMATIC_ABERRATION_PX,
    DEFAULT_CHROMATIC_ABERRATION_STRENGTH,
    DEFAULT_LENS_CENTER,
    DEFAULT_LENS_DISTORTION_K2,
    DEFAULT_LENS_DISTORTION_STRENGTH,
    DEFAULT_LENS_EDGE_FALLOFF,
    DEFAULT_LENS_EFFECTS_MODE,
    flatten_lens_effects_settings,
)
from app.ar_pbr.lens_flare import (
    DEFAULT_APERTURE_FLARE_BLADES,
    DEFAULT_APERTURE_FLARE_RADIUS,
    DEFAULT_APERTURE_FLARE_ROTATION_DEG,
    DEFAULT_APERTURE_FLARE_STRENGTH,
    DEFAULT_LENS_DIRT_DENSITY,
    DEFAULT_LENS_DIRT_SCALE,
    DEFAULT_LENS_DIRT_STRENGTH,
    DEFAULT_LENS_FLARE_GHOST_COUNT,
    DEFAULT_LENS_FLARE_GHOST_SPACING,
    DEFAULT_LENS_FLARE_MODE,
    DEFAULT_LENS_FLARE_RADIUS,
    DEFAULT_LENS_FLARE_SEED,
    DEFAULT_LENS_FLARE_STRENGTH,
    DEFAULT_LENS_FLARE_THRESHOLD,
    DEFAULT_LENS_FLARE_TINT,
    DEFAULT_LENS_SCRATCH_DENSITY,
    DEFAULT_LENS_SCRATCH_LENGTH,
    DEFAULT_LENS_SCRATCH_STRENGTH,
    flatten_lens_flare_settings,
)
from app.ar_pbr.render_passes import (
    DEFAULT_RENDER_PASS_NAMES,
    flatten_render_pass_settings,
)
from app.ar_pbr.motion_blur import (
    DEFAULT_FRAME_DURATION_MS,
    DEFAULT_MOTION_BLUR_MODE,
    DEFAULT_MOTION_BLUR_SAMPLE_COUNT,
    DEFAULT_SHUTTER_ANGLE,
    flatten_motion_blur_settings,
)
from app.ar_pbr.hybrid_rendering import (
    DEFAULT_DENOISE_RADIUS,
    DEFAULT_DENOISE_STRENGTH,
    DEFAULT_DIFFUSE_GI_STRENGTH,
    DEFAULT_HYBRID_RENDER_MODE,
    DEFAULT_HYBRID_SAMPLE_COUNT,
    DEFAULT_SPECULAR_GI_STRENGTH,
    flatten_hybrid_render_settings,
)
from app.ar_pbr.ray_gi_detail import (
    DEFAULT_DIRECT_RADIANCE_CLAMP,
    DEFAULT_ENVIRONMENT_SAMPLE_COUNT,
    DEFAULT_INDIRECT_RADIANCE_CLAMP,
    DEFAULT_LIGHT_SAMPLE_COUNT,
    DEFAULT_LIGHT_SAMPLING_MODE,
    DEFAULT_RAY_GI_DETAIL_MODE,
    DEFAULT_RAY_GI_DIFFUSE_BOUNCES,
    DEFAULT_RAY_GI_MAX_BOUNCES,
    DEFAULT_RAY_GI_REFRACTION_BOUNCES,
    DEFAULT_RAY_GI_SPECULAR_BOUNCES,
    flatten_ray_gi_detail_settings,
)
from app.ar_pbr.hair import (
    DEFAULT_HAIR_ANISOTROPY,
    DEFAULT_HAIR_GROOM_MODE,
    DEFAULT_HAIR_GROOM_STRENGTH,
    DEFAULT_HAIR_GROOM_TINT,
    DEFAULT_HAIR_PRIMARY_ROUGHNESS,
    DEFAULT_HAIR_PRIMARY_SHIFT,
    DEFAULT_HAIR_RIM_STRENGTH,
    DEFAULT_HAIR_SECONDARY_ROUGHNESS,
    DEFAULT_HAIR_SECONDARY_SHIFT,
    DEFAULT_HAIR_SECONDARY_STRENGTH,
    flatten_hair_groom_settings,
)
from app.ar_pbr.material_layering import (
    DEFAULT_MATERIAL_LAYER_ALPHA,
    DEFAULT_MATERIAL_LAYER_BLEND,
    DEFAULT_MATERIAL_LAYER_COLOR,
    DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH,
    DEFAULT_MATERIAL_LAYER_MASK_STRENGTH,
    DEFAULT_MATERIAL_LAYER_METALLIC,
    DEFAULT_MATERIAL_LAYER_MODE,
    DEFAULT_MATERIAL_LAYER_ROUGHNESS,
    flatten_material_layering_settings,
)
from app.ar_pbr.subsurface import (
    DEFAULT_SUBSURFACE_COLOR,
    DEFAULT_SUBSURFACE_MODE,
    DEFAULT_SUBSURFACE_POWER,
    DEFAULT_SUBSURFACE_RADIUS,
    DEFAULT_SUBSURFACE_STRENGTH,
    DEFAULT_SUBSURFACE_THICKNESS,
    DEFAULT_SUBSURFACE_WRAP,
    flatten_subsurface_settings,
)
from app.ar_pbr.surface import (
    DEFAULT_SURFACE_METALLIC,
    DEFAULT_SURFACE_OVERRIDE_STRENGTH,
    DEFAULT_SURFACE_REFLECTANCE,
    DEFAULT_SURFACE_ROUGHNESS,
    flatten_surface_settings,
)
from app.ar_pbr.parallax import (
    DEFAULT_PARALLAX_CENTER,
    DEFAULT_PARALLAX_DEPTH,
    DEFAULT_PARALLAX_MODE,
    DEFAULT_PARALLAX_STEPS,
    DEFAULT_PARALLAX_STRENGTH,
    flatten_parallax_settings,
)
from app.ar_pbr.displacement import (
    DEFAULT_DISPLACEMENT_HEIGHT_CENTER,
    DEFAULT_DISPLACEMENT_HEIGHT_SCALE,
    DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH,
    DEFAULT_DISPLACEMENT_MAX_OFFSET,
    DEFAULT_DISPLACEMENT_MODE,
    DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK,
    DEFAULT_DISPLACEMENT_SUBDIVISION_MODE,
    DEFAULT_VECTOR_DISPLACEMENT_SPACE,
    DEFAULT_VECTOR_DISPLACEMENT_STRENGTH,
    flatten_displacement_settings,
)
from app.ar_pbr.triplanar import (
    DEFAULT_TRIPLANAR_BLEND_SHARPNESS,
    DEFAULT_TRIPLANAR_MODE,
    DEFAULT_TRIPLANAR_OFFSET,
    DEFAULT_TRIPLANAR_SCALE,
    DEFAULT_TRIPLANAR_STRENGTH,
    flatten_triplanar_settings,
)
from app.ar_pbr.transmission import (
    DEFAULT_ABSORPTION_COLOR,
    DEFAULT_ABSORPTION_DISTANCE,
    DEFAULT_IOR,
    DEFAULT_REFRACTION_DEPTH_PX,
    DEFAULT_REFRACTION_STRENGTH,
    DEFAULT_ROUGHNESS_BLUR_STRENGTH,
    DEFAULT_THICKNESS,
    DEFAULT_TRANSMISSION,
    DEFAULT_TRANSMISSION_MODE,
    flatten_transmission_settings,
)
from app.ar_pbr.shadow import (
    DEFAULT_SHADOW_BIAS,
    DEFAULT_SHADOW_FILTER,
    DEFAULT_SHADOW_LIGHT_TYPE,
    DEFAULT_SHADOW_MAP_SIZE,
    DEFAULT_SHADOW_NORMAL_BIAS,
    DEFAULT_SHADOW_PCF_RADIUS,
    DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS,
    DEFAULT_SHADOW_STRENGTH,
    DEFAULT_SPOT_INNER_ANGLE,
    DEFAULT_SPOT_OUTER_ANGLE,
    normalize_shadow_filter,
    normalize_shadow_light_type,
)
from app.ar_pbr.tone_mapping import (
    DEFAULT_TONE_EXPOSURE,
    DEFAULT_TONE_GAMMA,
    DEFAULT_TONE_MAPPING,
    DEFAULT_TONE_WHITE_BALANCE,
    flatten_color_management_settings,
)


SUPPORTED_ASSET_EXTS = frozenset({
    ".fbx",
    ".glb",
    ".gltf",
    ".vrm",
    ".obj",
    ".usd",
    ".usdz",
    ".arpbr",
})

DEFAULT_TRANSFORM = {
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0],
    "scale": [1.0, 1.0, 1.0],
}

DEFAULT_COLOR_MATCH = {
    "exposure": 0.0,
    "white_balance": 6500.0,
    "contrast": 1.0,
}

DEFAULT_MATERIAL = {
    "base_color": [1.0, 1.0, 1.0, 1.0],
    "roughness": 0.45,
    "metallic": 0.0,
    "reflectance": 0.5,
}

DEFAULT_RENDER = {
    "render_profile": "authored",
    "shadow_quality": "medium",
    "reflection_quality": "preview",
    "lighting": {
        "hdri_id": "wide_street_01",
        "hdri_path": "",
        "ibl_exposure": 1.1,
        "ibl_rotation": 0.0,
        "light_azimuth": 45.0,
        "light_elevation": 45.0,
        "direct_strength": 0.42,
        "shadow_strength": DEFAULT_SHADOW_STRENGTH,
        "shadow_light_type": DEFAULT_SHADOW_LIGHT_TYPE,
        "shadow_filter": DEFAULT_SHADOW_FILTER,
        "shadow_map_size": DEFAULT_SHADOW_MAP_SIZE,
        "shadow_pcf_radius": DEFAULT_SHADOW_PCF_RADIUS,
        "shadow_pcss_blocker_radius": DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS,
        "shadow_bias": DEFAULT_SHADOW_BIAS,
        "shadow_normal_bias": DEFAULT_SHADOW_NORMAL_BIAS,
        "shadow_spot_inner_angle": DEFAULT_SPOT_INNER_ANGLE,
        "shadow_spot_outer_angle": DEFAULT_SPOT_OUTER_ANGLE,
        "shadow_catcher_opacity": DEFAULT_SHADOW_CATCHER_OPACITY,
        "shadow_catcher_softness": DEFAULT_SHADOW_CATCHER_SOFTNESS,
        "shadow_catcher_matte_alpha": DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
        "reflection_catcher_opacity": DEFAULT_REFLECTION_CATCHER_OPACITY,
        "reflection_catcher_roughness": DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
        "reflection_catcher_softness": DEFAULT_REFLECTION_CATCHER_SOFTNESS,
        "contact_reflection_strength": DEFAULT_CONTACT_REFLECTION_STRENGTH,
        "contact_reflection_falloff": DEFAULT_CONTACT_REFLECTION_FALLOFF,
        "tone_mapping": DEFAULT_TONE_MAPPING,
        "tone_exposure": DEFAULT_TONE_EXPOSURE,
        "tone_white_balance": DEFAULT_TONE_WHITE_BALANCE,
        "tone_gamma": DEFAULT_TONE_GAMMA,
        "hybrid_render_mode": DEFAULT_HYBRID_RENDER_MODE,
        "hybrid_accumulation_enabled": False,
        "hybrid_accumulation_samples": DEFAULT_HYBRID_SAMPLE_COUNT,
        "hybrid_sample_seed": 0,
        "diffuse_gi_strength": DEFAULT_DIFFUSE_GI_STRENGTH,
        "specular_gi_strength": DEFAULT_SPECULAR_GI_STRENGTH,
        "denoise_strength": DEFAULT_DENOISE_STRENGTH,
        "denoise_radius": DEFAULT_DENOISE_RADIUS,
        "ray_gi_detail_mode": DEFAULT_RAY_GI_DETAIL_MODE,
        "ray_gi_detail_enabled": False,
        "ray_gi_max_bounces": DEFAULT_RAY_GI_MAX_BOUNCES,
        "ray_gi_diffuse_bounces": DEFAULT_RAY_GI_DIFFUSE_BOUNCES,
        "ray_gi_specular_bounces": DEFAULT_RAY_GI_SPECULAR_BOUNCES,
        "ray_gi_refraction_bounces": DEFAULT_RAY_GI_REFRACTION_BOUNCES,
        "ray_gi_direct_radiance_clamp": DEFAULT_DIRECT_RADIANCE_CLAMP,
        "ray_gi_indirect_radiance_clamp": DEFAULT_INDIRECT_RADIANCE_CLAMP,
        "ray_gi_advanced_light_sampling": False,
        "ray_gi_light_sampling_mode": DEFAULT_LIGHT_SAMPLING_MODE,
        "ray_gi_light_sample_count": DEFAULT_LIGHT_SAMPLE_COUNT,
        "ray_gi_environment_sample_count": DEFAULT_ENVIRONMENT_SAMPLE_COUNT,
        "ray_gi_mis_enabled": False,
        "ray_gi_importance_sampling": False,
        "ray_gi_denoise_channels": ["beauty"],
        "ray_gi_denoise_beauty": True,
        "ray_gi_denoise_diffuse": False,
        "ray_gi_denoise_specular": False,
        "ray_gi_denoise_transmission": False,
        "ray_gi_denoise_albedo_guided": False,
        "ray_gi_denoise_normal_guided": False,
        "ambient_occlusion_mode": DEFAULT_AMBIENT_OCCLUSION_MODE,
        "ambient_occlusion_enabled": False,
        "ao_strength": DEFAULT_AO_STRENGTH,
        "ao_radius": DEFAULT_AO_RADIUS,
        "ao_distance": DEFAULT_AO_DISTANCE,
        "ao_color": list(DEFAULT_AO_COLOR),
        "ao_ambient": DEFAULT_AO_AMBIENT,
        "ao_diffuse": DEFAULT_AO_DIFFUSE,
        "ao_specular": DEFAULT_AO_SPECULAR,
        "depth_edge_glow_enabled": False,
        "depth_edge_glow_strength": DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
        "depth_edge_glow_radius_px": DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
        "depth_edge_glow_color": list(DEFAULT_DEPTH_EDGE_GLOW_COLOR),
        "transmission_mode": DEFAULT_TRANSMISSION_MODE,
        "transmission_enabled": False,
        "transmission": DEFAULT_TRANSMISSION,
        "refraction_strength": DEFAULT_REFRACTION_STRENGTH,
        "refraction_depth_px": DEFAULT_REFRACTION_DEPTH_PX,
        "ior": DEFAULT_IOR,
        "thickness": DEFAULT_THICKNESS,
        "absorption_color": list(DEFAULT_ABSORPTION_COLOR),
        "absorption_distance": DEFAULT_ABSORPTION_DISTANCE,
        "roughness_blur_strength": DEFAULT_ROUGHNESS_BLUR_STRENGTH,
        "clearcoat_mode": DEFAULT_CLEARCOAT_MODE,
        "clearcoat_enabled": False,
        "clearcoat_strength": DEFAULT_CLEARCOAT_STRENGTH,
        "clearcoat_roughness": DEFAULT_CLEARCOAT_ROUGHNESS,
        "clearcoat_ior": DEFAULT_CLEARCOAT_IOR,
        "clearcoat_tint": list(DEFAULT_CLEARCOAT_TINT),
        "surface_override_strength": DEFAULT_SURFACE_OVERRIDE_STRENGTH,
        "surface_roughness": DEFAULT_SURFACE_ROUGHNESS,
        "surface_metallic": DEFAULT_SURFACE_METALLIC,
        "surface_reflectance": DEFAULT_SURFACE_REFLECTANCE,
        "parallax_mode": DEFAULT_PARALLAX_MODE,
        "parallax_enabled": False,
        "parallax_strength": DEFAULT_PARALLAX_STRENGTH,
        "parallax_depth": DEFAULT_PARALLAX_DEPTH,
        "parallax_center": DEFAULT_PARALLAX_CENTER,
        "parallax_steps": DEFAULT_PARALLAX_STEPS,
        "displacement_mode": DEFAULT_DISPLACEMENT_MODE,
        "displacement_enabled": False,
        "displacement_height_strength": DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH,
        "displacement_height_scale": DEFAULT_DISPLACEMENT_HEIGHT_SCALE,
        "displacement_height_center": DEFAULT_DISPLACEMENT_HEIGHT_CENTER,
        "vector_displacement_strength": DEFAULT_VECTOR_DISPLACEMENT_STRENGTH,
        "vector_displacement_space": DEFAULT_VECTOR_DISPLACEMENT_SPACE,
        "displacement_subdivision_mode": DEFAULT_DISPLACEMENT_SUBDIVISION_MODE,
        "displacement_max_offset": DEFAULT_DISPLACEMENT_MAX_OFFSET,
        "displacement_parallax_fallback": DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK,
        "bevel_mode": DEFAULT_BEVEL_MODE,
        "bevel_enabled": False,
        "bevel_strength": DEFAULT_BEVEL_STRENGTH,
        "bevel_radius": DEFAULT_BEVEL_RADIUS,
        "bevel_edge_width": DEFAULT_BEVEL_EDGE_WIDTH,
        "bevel_samples": DEFAULT_BEVEL_SAMPLES,
        "material_layer_mode": DEFAULT_MATERIAL_LAYER_MODE,
        "material_layer_enabled": False,
        "material_layer_blend": DEFAULT_MATERIAL_LAYER_BLEND,
        "material_layer_color": list(DEFAULT_MATERIAL_LAYER_COLOR),
        "material_layer_roughness": DEFAULT_MATERIAL_LAYER_ROUGHNESS,
        "material_layer_metallic": DEFAULT_MATERIAL_LAYER_METALLIC,
        "material_layer_alpha": DEFAULT_MATERIAL_LAYER_ALPHA,
        "material_layer_emissive_strength": DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH,
        "material_layer_mask_strength": DEFAULT_MATERIAL_LAYER_MASK_STRENGTH,
        "subsurface_mode": DEFAULT_SUBSURFACE_MODE,
        "subsurface_enabled": False,
        "subsurface_strength": DEFAULT_SUBSURFACE_STRENGTH,
        "subsurface_color": list(DEFAULT_SUBSURFACE_COLOR),
        "subsurface_radius": DEFAULT_SUBSURFACE_RADIUS,
        "subsurface_power": DEFAULT_SUBSURFACE_POWER,
        "subsurface_wrap": DEFAULT_SUBSURFACE_WRAP,
        "subsurface_thickness": DEFAULT_SUBSURFACE_THICKNESS,
        "hair_groom_mode": DEFAULT_HAIR_GROOM_MODE,
        "hair_groom_enabled": False,
        "hair_groom_strength": DEFAULT_HAIR_GROOM_STRENGTH,
        "hair_groom_tint": list(DEFAULT_HAIR_GROOM_TINT),
        "hair_primary_shift": DEFAULT_HAIR_PRIMARY_SHIFT,
        "hair_secondary_shift": DEFAULT_HAIR_SECONDARY_SHIFT,
        "hair_primary_roughness": DEFAULT_HAIR_PRIMARY_ROUGHNESS,
        "hair_secondary_roughness": DEFAULT_HAIR_SECONDARY_ROUGHNESS,
        "hair_secondary_strength": DEFAULT_HAIR_SECONDARY_STRENGTH,
        "hair_anisotropy": DEFAULT_HAIR_ANISOTROPY,
        "hair_rim_strength": DEFAULT_HAIR_RIM_STRENGTH,
        "cloth_sheen_mode": DEFAULT_CLOTH_SHEEN_MODE,
        "cloth_sheen_enabled": False,
        "cloth_sheen_strength": DEFAULT_CLOTH_SHEEN_STRENGTH,
        "cloth_sheen_color": list(DEFAULT_CLOTH_SHEEN_COLOR),
        "cloth_sheen_roughness": DEFAULT_CLOTH_SHEEN_ROUGHNESS,
        "cloth_sheen_edge_tint": list(DEFAULT_CLOTH_SHEEN_EDGE_TINT),
        "cloth_sheen_fiber_strength": DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH,
        "cloth_sheen_wrap": DEFAULT_CLOTH_SHEEN_WRAP,
        "cloth_sheen_retroreflection": DEFAULT_CLOTH_SHEEN_RETROREFLECTION,
        "glint_mode": DEFAULT_GLINT_MODE,
        "glint_enabled": False,
        "glint_strength": DEFAULT_GLINT_STRENGTH,
        "glint_color": list(DEFAULT_GLINT_COLOR),
        "glint_density": DEFAULT_GLINT_DENSITY,
        "glint_scale": DEFAULT_GLINT_SCALE,
        "glint_threshold": DEFAULT_GLINT_THRESHOLD,
        "glint_sharpness": DEFAULT_GLINT_SHARPNESS,
        "glint_roughness_jitter": DEFAULT_GLINT_ROUGHNESS_JITTER,
        "caustics_mode": DEFAULT_CAUSTICS_MODE,
        "caustics_enabled": False,
        "caustics_strength": DEFAULT_CAUSTICS_STRENGTH,
        "caustics_quality": DEFAULT_CAUSTICS_QUALITY,
        "caustics_sample_count": DEFAULT_CAUSTICS_SAMPLE_COUNT,
        "caustics_scale": DEFAULT_CAUSTICS_SCALE,
        "caustics_focus": DEFAULT_CAUSTICS_FOCUS,
        "caustics_radius": DEFAULT_CAUSTICS_RADIUS,
        "caustics_threshold": DEFAULT_CAUSTICS_THRESHOLD,
        "caustics_tint": list(DEFAULT_CAUSTICS_TINT),
        "caustics_seed": DEFAULT_CAUSTICS_SEED,
        "anisotropic_mode": DEFAULT_ANISOTROPIC_MODE,
        "anisotropic_enabled": False,
        "anisotropic_strength": DEFAULT_ANISOTROPIC_STRENGTH,
        "anisotropy": DEFAULT_ANISOTROPY,
        "anisotropic_rotation": DEFAULT_ANISOTROPIC_ROTATION,
        "anisotropic_tangent_weight": DEFAULT_ANISOTROPIC_TANGENT_WEIGHT,
        "clearcoat_anisotropy": DEFAULT_CLEARCOAT_ANISOTROPY,
        "thin_film_enabled": False,
        "thin_film_strength": DEFAULT_THIN_FILM_STRENGTH,
        "thin_film_thickness_nm": DEFAULT_THIN_FILM_THICKNESS_NM,
        "thin_film_ior": DEFAULT_THIN_FILM_IOR,
        "thin_film_tint": list(DEFAULT_THIN_FILM_TINT),
        "newton_rings_strength": DEFAULT_NEWTON_RINGS_STRENGTH,
        "newton_rings_scale": DEFAULT_NEWTON_RINGS_SCALE,
        "anisotropic_seed": DEFAULT_ANISOTROPIC_SEED,
        "microsurface_mode": DEFAULT_MICROSURFACE_MODE,
        "microsurface_enabled": False,
        "detail_normal_enabled": False,
        "detail_normal_strength": DEFAULT_DETAIL_NORMAL_STRENGTH,
        "detail_normal_scale": DEFAULT_DETAIL_NORMAL_SCALE,
        "detail_normal_blend": DEFAULT_DETAIL_NORMAL_BLEND,
        "detail_normal_seed": DEFAULT_DETAIL_NORMAL_SEED,
        "micro_roughness_enabled": False,
        "micro_roughness_strength": DEFAULT_MICRO_ROUGHNESS_STRENGTH,
        "micro_roughness_scale": DEFAULT_MICRO_ROUGHNESS_SCALE,
        "micro_roughness_contrast": DEFAULT_MICRO_ROUGHNESS_CONTRAST,
        "gloss_variation_strength": DEFAULT_GLOSS_VARIATION_STRENGTH,
        "gloss_bias": DEFAULT_GLOSS_BIAS,
        "specular_micro_occlusion": DEFAULT_SPECULAR_MICRO_OCCLUSION,
        "depth_of_field_mode": DEFAULT_DEPTH_OF_FIELD_MODE,
        "depth_of_field_enabled": False,
        "depth_of_field_strength": DEFAULT_DEPTH_OF_FIELD_STRENGTH,
        "dof_focus_depth": DEFAULT_DOF_FOCUS_DEPTH,
        "dof_focus_range": DEFAULT_DOF_FOCUS_RANGE,
        "dof_max_blur_px": DEFAULT_DOF_MAX_BLUR_PX,
        "dof_near_blur": DEFAULT_DOF_NEAR_BLUR,
        "dof_far_blur": DEFAULT_DOF_FAR_BLUR,
        "dof_bokeh_shape": DEFAULT_DOF_BOKEH_SHAPE,
        "post_effects_mode": DEFAULT_POST_EFFECTS_MODE,
        "post_effects_enabled": False,
        "bloom_enabled": False,
        "bloom_strength": DEFAULT_BLOOM_STRENGTH,
        "bloom_radius": DEFAULT_BLOOM_RADIUS,
        "bloom_threshold": DEFAULT_BLOOM_THRESHOLD,
        "bloom_method": "convolution",
        "bloom_kernel": DEFAULT_BLOOM_KERNEL,
        "bloom_convolution_scale": DEFAULT_BLOOM_CONVOLUTION_SCALE,
        "bloom_scatter": DEFAULT_BLOOM_SCATTER,
        "bloom_boost": DEFAULT_BLOOM_BOOST,
        "vignette_enabled": False,
        "vignette_strength": DEFAULT_VIGNETTE_STRENGTH,
        "vignette_radius": DEFAULT_VIGNETTE_RADIUS,
        "vignette_feather": DEFAULT_VIGNETTE_FEATHER,
        "grain_enabled": False,
        "grain_strength": DEFAULT_GRAIN_STRENGTH,
        "grain_scale": DEFAULT_GRAIN_SCALE,
        "grain_seed": DEFAULT_GRAIN_SEED,
        "sharpen_enabled": False,
        "sharpen_strength": DEFAULT_SHARPEN_STRENGTH,
        "sharpen_radius": DEFAULT_SHARPEN_RADIUS,
        "lens_effects_mode": DEFAULT_LENS_EFFECTS_MODE,
        "lens_effects_enabled": False,
        "lens_distortion_enabled": False,
        "lens_distortion_strength": DEFAULT_LENS_DISTORTION_STRENGTH,
        "lens_distortion_k1": DEFAULT_LENS_DISTORTION_STRENGTH,
        "lens_distortion_k2": DEFAULT_LENS_DISTORTION_K2,
        "chromatic_aberration_enabled": False,
        "chromatic_aberration_strength": DEFAULT_CHROMATIC_ABERRATION_STRENGTH,
        "chromatic_aberration_px": DEFAULT_CHROMATIC_ABERRATION_PX,
        "lens_center": list(DEFAULT_LENS_CENTER),
        "lens_edge_falloff": DEFAULT_LENS_EDGE_FALLOFF,
        "lens_flare_mode": DEFAULT_LENS_FLARE_MODE,
        "lens_flare_enabled": False,
        "lens_flare_strength": DEFAULT_LENS_FLARE_STRENGTH,
        "lens_flare_threshold": DEFAULT_LENS_FLARE_THRESHOLD,
        "lens_flare_radius": DEFAULT_LENS_FLARE_RADIUS,
        "lens_flare_ghost_count": DEFAULT_LENS_FLARE_GHOST_COUNT,
        "lens_flare_ghost_spacing": DEFAULT_LENS_FLARE_GHOST_SPACING,
        "lens_flare_tint": list(DEFAULT_LENS_FLARE_TINT),
        "aperture_flare_enabled": False,
        "aperture_flare_strength": DEFAULT_APERTURE_FLARE_STRENGTH,
        "aperture_flare_blades": DEFAULT_APERTURE_FLARE_BLADES,
        "aperture_flare_rotation_deg": DEFAULT_APERTURE_FLARE_ROTATION_DEG,
        "aperture_flare_radius": DEFAULT_APERTURE_FLARE_RADIUS,
        "lens_dirt_enabled": False,
        "lens_dirt_strength": DEFAULT_LENS_DIRT_STRENGTH,
        "lens_dirt_density": DEFAULT_LENS_DIRT_DENSITY,
        "lens_dirt_scale": DEFAULT_LENS_DIRT_SCALE,
        "lens_scratch_enabled": False,
        "lens_scratch_strength": DEFAULT_LENS_SCRATCH_STRENGTH,
        "lens_scratch_density": DEFAULT_LENS_SCRATCH_DENSITY,
        "lens_scratch_length": DEFAULT_LENS_SCRATCH_LENGTH,
        "lens_flare_seed": DEFAULT_LENS_FLARE_SEED,
        "triplanar_mode": DEFAULT_TRIPLANAR_MODE,
        "triplanar_enabled": False,
        "triplanar_strength": DEFAULT_TRIPLANAR_STRENGTH,
        "triplanar_scale": DEFAULT_TRIPLANAR_SCALE,
        "triplanar_blend_sharpness": DEFAULT_TRIPLANAR_BLEND_SHARPNESS,
        "triplanar_offset": list(DEFAULT_TRIPLANAR_OFFSET),
        "triplanar_space": "object",
        "render_passes_enabled": False,
        "render_pass_names": list(DEFAULT_RENDER_PASS_NAMES),
        "render_pass_output_dir": "",
        "render_pass_format": "png",
        "motion_blur_mode": DEFAULT_MOTION_BLUR_MODE,
        "motion_blur_enabled": False,
        "motion_blur_samples": DEFAULT_MOTION_BLUR_SAMPLE_COUNT,
        "motion_blur_shutter_angle": DEFAULT_SHUTTER_ANGLE,
        "motion_blur_shutter_fraction": DEFAULT_SHUTTER_ANGLE / 360.0,
        "motion_blur_shutter_ms": 0.0,
        "motion_blur_frame_duration_ms": DEFAULT_FRAME_DURATION_MS,
        "motion_blur_strength": 1.0,
        "camera_motion_px": [0.0, 0.0],
        "self_shadow_strength": 0.45,
        "ground_height": -0.52,
    },
}

DEFAULT_PLACEMENT = {
    "mode": "manual",
    "image_point": [],
    "coordinate_space": "frame",
    "surface_offset": 0.0,
    "plane_solution_id": "",
    "anchor_world": [],
    "surface_normal": [],
    "manual_offset": [],
    "tracking": {},
}


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _coerce_vector(value: Any, length: int, default: list[float]) -> list[float]:
    if not isinstance(value, (list, tuple)):
        value = []
    out: list[float] = []
    for idx in range(length):
        fallback = default[idx] if idx < len(default) else 0.0
        raw = value[idx] if idx < len(value) else fallback
        out.append(_coerce_float(raw, fallback))
    return out


def _coerce_float_list(value: Any, default: list[float], *, limit: int = 9) -> list[float]:
    source = value if isinstance(value, (list, tuple)) else default
    out: list[float] = []
    for raw in list(source)[:limit]:
        try:
            out.append(float(raw))
        except Exception:
            pass
    return out or list(default)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def normalize_transform(value: Any) -> dict[str, list[float]]:
    data = _as_mapping(value)
    return {
        "position": _coerce_vector(data.get("position"), 3, DEFAULT_TRANSFORM["position"]),
        "rotation": _coerce_vector(data.get("rotation"), 3, DEFAULT_TRANSFORM["rotation"]),
        "scale": [
            max(0.0001, v)
            for v in _coerce_vector(data.get("scale"), 3, DEFAULT_TRANSFORM["scale"])
        ],
    }


def normalize_color_match(value: Any) -> dict[str, float]:
    data = _as_mapping(value)
    return {
        "exposure": _coerce_float(data.get("exposure"), DEFAULT_COLOR_MATCH["exposure"]),
        "white_balance": max(1000.0, min(40000.0, _coerce_float(
            data.get("white_balance"),
            DEFAULT_COLOR_MATCH["white_balance"],
        ))),
        "contrast": max(0.0, _coerce_float(data.get("contrast"), DEFAULT_COLOR_MATCH["contrast"])),
    }


def normalize_material(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    color = _coerce_vector(data.get("base_color"), 4, DEFAULT_MATERIAL["base_color"])
    return {
        "base_color": [_clamp(v, 0.0, 1.0) for v in color],
        "roughness": _clamp(_coerce_float(data.get("roughness"), DEFAULT_MATERIAL["roughness"]), 0.0, 1.0),
        "metallic": _clamp(_coerce_float(data.get("metallic"), DEFAULT_MATERIAL["metallic"]), 0.0, 1.0),
        "reflectance": _clamp(_coerce_float(data.get("reflectance"), DEFAULT_MATERIAL["reflectance"]), 0.0, 1.0),
    }


def normalize_lighting_settings(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    defaults = DEFAULT_RENDER["lighting"]
    hdri_id = str(data.get("hdri_id") or defaults.get("hdri_id") or "wide_street_01").strip()
    hdri_path = str(data.get("hdri_path") or defaults.get("hdri_path") or "").strip()
    out = {
        "hdri_id": hdri_id,
        "hdri_path": hdri_path,
        "ibl_exposure": _clamp(_coerce_float(data.get("ibl_exposure"), defaults["ibl_exposure"]), 0.0, 8.0),
        "ibl_rotation": _clamp(_coerce_float(data.get("ibl_rotation"), defaults["ibl_rotation"]), -1.0, 1.0),
        "light_azimuth": _clamp(_coerce_float(data.get("light_azimuth"), defaults["light_azimuth"]), -180.0, 180.0),
        "light_elevation": _clamp(_coerce_float(data.get("light_elevation"), defaults["light_elevation"]), -20.0, 89.0),
        "direct_strength": _clamp(_coerce_float(data.get("direct_strength"), defaults["direct_strength"]), 0.0, 4.0),
        "shadow_strength": _clamp(_coerce_float(data.get("shadow_strength"), defaults["shadow_strength"]), 0.0, 1.0),
        "shadow_light_type": normalize_shadow_light_type(
            data.get("shadow_light_type", data.get("light_type", defaults["shadow_light_type"]))
        ),
        "shadow_filter": normalize_shadow_filter(
            data.get("shadow_filter", data.get("shadow_filter_mode", defaults["shadow_filter"]))
        ),
        "shadow_map_size": int(_clamp(
            _coerce_float(data.get("shadow_map_size"), defaults["shadow_map_size"]),
            256.0,
            4096.0,
        )),
        "shadow_pcf_radius": _clamp(
            _coerce_float(data.get("shadow_pcf_radius", data.get("shadow_softness")), defaults["shadow_pcf_radius"]),
            0.0,
            12.0,
        ),
        "shadow_pcss_blocker_radius": _clamp(
            _coerce_float(
                data.get("shadow_pcss_blocker_radius", data.get("pcss_blocker_radius")),
                defaults["shadow_pcss_blocker_radius"],
            ),
            0.0,
            16.0,
        ),
        "shadow_bias": _clamp(
            _coerce_float(data.get("shadow_bias"), defaults["shadow_bias"]),
            0.00005,
            0.08,
        ),
        "shadow_normal_bias": _clamp(
            _coerce_float(data.get("shadow_normal_bias"), defaults["shadow_normal_bias"]),
            0.0,
            0.08,
        ),
        "shadow_spot_outer_angle": _clamp(
            _coerce_float(data.get("shadow_spot_outer_angle", data.get("spot_outer_angle")), defaults["shadow_spot_outer_angle"]),
            1.0,
            89.0,
        ),
        "shadow_spot_inner_angle": _clamp(
            _coerce_float(data.get("shadow_spot_inner_angle", data.get("spot_inner_angle")), defaults["shadow_spot_inner_angle"]),
            0.0,
            _clamp(
                _coerce_float(data.get("shadow_spot_outer_angle", data.get("spot_outer_angle")), defaults["shadow_spot_outer_angle"]),
                1.0,
                89.0,
            ),
        ),
        "self_shadow_strength": _clamp(
            _coerce_float(data.get("self_shadow_strength"), defaults["self_shadow_strength"]),
            0.0,
            1.0,
        ),
        "ground_height": _clamp(_coerce_float(data.get("ground_height"), defaults["ground_height"]), -3.0, 3.0),
    }
    out.update(flatten_catcher_settings(data))
    out.update(flatten_color_management_settings(data))
    out.update(flatten_hybrid_render_settings(data))
    out.update(flatten_ray_gi_detail_settings(data))
    out.update(flatten_ambient_occlusion_settings(data))
    out.update(flatten_depth_edge_glow_settings(data))
    out.update(flatten_transmission_settings(data))
    out.update(flatten_clearcoat_settings(data))
    out.update(flatten_parallax_settings(data))
    out.update(flatten_displacement_settings(data))
    out.update(flatten_bevel_settings(data))
    out.update(flatten_material_layering_settings(data))
    out.update(flatten_surface_settings(data))
    out.update(flatten_subsurface_settings(data))
    out.update(flatten_hair_groom_settings(data))
    out.update(flatten_cloth_sheen_settings(data))
    out.update(flatten_glint_sparkle_settings(data))
    out.update(flatten_caustics_settings(data))
    out.update(flatten_anisotropic_material_settings(data))
    out.update(flatten_microsurface_settings(data))
    out.update(flatten_depth_of_field_settings(data))
    out.update(flatten_post_effects_settings(data))
    out.update(flatten_lens_effects_settings(data))
    out.update(flatten_lens_flare_settings(data))
    out.update(flatten_render_pass_settings(data))
    out.update(flatten_motion_blur_settings(data))
    out.update(flatten_triplanar_settings(data))
    return out


def normalize_render_settings(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    out = deepcopy(DEFAULT_RENDER)
    profile = str(data.get("render_profile") or data.get("ar_pbr_render_profile") or DEFAULT_RENDER["render_profile"]).strip().casefold()
    out["render_profile"] = profile if profile in {"authored", "vrm_mtoon", "marmoset_pbr"} else DEFAULT_RENDER["render_profile"]
    if data.get("shadow_quality"):
        out["shadow_quality"] = str(data.get("shadow_quality"))
    if data.get("reflection_quality"):
        out["reflection_quality"] = str(data.get("reflection_quality"))
    out["lighting"] = normalize_lighting_settings(data.get("lighting"))
    return out


def normalize_camera_solution(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    if not data:
        return {}
    out: dict[str, Any] = {}
    for key in ("id", "model", "depth_source_id"):
        if data.get(key):
            out[key] = str(data.get(key))
    if isinstance(data.get("frame_size"), (list, tuple)) and len(data.get("frame_size")) >= 2:
        out["frame_size"] = [
            max(1, _coerce_int(data.get("frame_size")[0], 1)),
            max(1, _coerce_int(data.get("frame_size")[1], 1)),
        ]
    intr = _as_mapping(data.get("intrinsics"))
    if intr:
        out["intrinsics"] = {
            "fx": _coerce_float(intr.get("fx"), 1.0),
            "fy": _coerce_float(intr.get("fy"), 1.0),
            "cx": _coerce_float(intr.get("cx"), 0.0),
            "cy": _coerce_float(intr.get("cy"), 0.0),
        }
    plane = _as_mapping(data.get("plane"))
    if plane:
        out["plane"] = {
            "point": _coerce_vector(plane.get("point"), 3, [0.0, 0.0, 1.0]),
            "normal": _coerce_vector(plane.get("normal"), 3, [0.0, 1.0, 0.0]),
            "d": _coerce_float(plane.get("d"), 0.0),
        }
    if isinstance(data.get("image_points"), (list, tuple)):
        points = []
        for row in data.get("image_points"):
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                points.append(_coerce_vector(row, 2, [0.0, 0.0]))
        if points:
            out["image_points"] = points
    return out


def normalize_placement(value: Any) -> dict[str, Any]:
    data = _as_mapping(value)
    out = deepcopy(DEFAULT_PLACEMENT)
    if data.get("mode"):
        out["mode"] = str(data.get("mode"))
    if isinstance(data.get("image_point"), (list, tuple)) and len(data.get("image_point")) >= 2:
        out["image_point"] = _coerce_vector(data.get("image_point"), 2, [0.0, 0.0])
    if data.get("coordinate_space"):
        out["coordinate_space"] = str(data.get("coordinate_space"))
    out["surface_offset"] = _coerce_float(data.get("surface_offset"), DEFAULT_PLACEMENT["surface_offset"])
    if data.get("plane_solution_id"):
        out["plane_solution_id"] = str(data.get("plane_solution_id"))
    if isinstance(data.get("anchor_world"), (list, tuple)) and len(data.get("anchor_world")) >= 3:
        out["anchor_world"] = _coerce_vector(data.get("anchor_world"), 3, [0.0, 0.0, 1.0])
    if isinstance(data.get("surface_normal"), (list, tuple)) and len(data.get("surface_normal")) >= 3:
        out["surface_normal"] = _coerce_vector(data.get("surface_normal"), 3, [0.0, 1.0, 0.0])
    if isinstance(data.get("manual_offset"), (list, tuple)) and len(data.get("manual_offset")) >= 3:
        out["manual_offset"] = _coerce_vector(data.get("manual_offset"), 3, [0.0, 0.0, 0.0])
    tracking = _as_mapping(data.get("tracking"))
    if tracking:
        out["tracking"] = {
            "enabled": _coerce_bool(tracking.get("enabled"), True),
            "image_point": _coerce_vector(tracking.get("image_point"), 2, out.get("image_point") or [0.5, 0.62]),
            "template_size": [
                max(1, _coerce_int((tracking.get("template_size") or [24, 24])[0], 24))
                if isinstance(tracking.get("template_size"), (list, tuple)) else 24,
                max(1, _coerce_int((tracking.get("template_size") or [24, 24])[1], 24))
                if isinstance(tracking.get("template_size"), (list, tuple)) and len(tracking.get("template_size")) > 1 else 24,
            ],
            "patch_radius_norm": _clamp(_coerce_float(tracking.get("patch_radius_norm"), 0.09), 0.005, 0.5),
            "search_radius_norm": _clamp(_coerce_float(tracking.get("search_radius_norm"), 0.22), 0.01, 0.75),
            "min_confidence": _clamp(_coerce_float(tracking.get("min_confidence"), 0.18), -1.0, 1.0),
            "scale_tracking": _coerce_bool(tracking.get("scale_tracking"), True),
            "rotation_tracking": _coerce_bool(tracking.get("rotation_tracking"), True),
            "scale_candidates": [
                _clamp(value, 0.35, 3.0)
                for value in _coerce_float_list(tracking.get("scale_candidates"), [0.82, 0.92, 1.0, 1.1, 1.22])
            ],
            "rotation_range_deg": _clamp(_coerce_float(tracking.get("rotation_range_deg"), 18.0), 0.0, 45.0),
            "rotation_step_deg": _clamp(_coerce_float(tracking.get("rotation_step_deg"), 9.0), 3.0, 45.0),
            "base_scale": _coerce_vector(tracking.get("base_scale"), 3, [1.0, 1.0, 1.0]),
            "base_rotation": _coerce_vector(tracking.get("base_rotation"), 3, [0.0, 0.0, 0.0]),
        }
        raw_template = tracking.get("template_luma")
        if isinstance(raw_template, (list, tuple)):
            out["tracking"]["template_luma"] = [
                max(0, min(255, _coerce_int(value, 0)))
                for value in raw_template[:4096]
            ]
        raw_probes = tracking.get("probe_templates")
        if isinstance(raw_probes, (list, tuple)):
            probes: list[dict[str, Any]] = []
            for raw_probe in raw_probes[:8]:
                probe = _as_mapping(raw_probe)
                if not probe:
                    continue
                template_luma = probe.get("template_luma")
                template_size = probe.get("template_size")
                if not isinstance(template_luma, (list, tuple)) or not isinstance(template_size, (list, tuple)):
                    continue
                row = {
                    "image_point": _coerce_vector(probe.get("image_point"), 2, out["tracking"]["image_point"]),
                    "offset_norm": _coerce_vector(probe.get("offset_norm"), 2, [0.0, 0.0]),
                    "template_size": [
                        max(1, _coerce_int(template_size[0], 16)),
                        max(1, _coerce_int(template_size[1] if len(template_size) > 1 else template_size[0], 16)),
                    ],
                    "template_luma": [
                        max(0, min(255, _coerce_int(value, 0)))
                        for value in template_luma[:2048]
                    ],
                    "std": _coerce_float(probe.get("std"), 0.0),
                }
                probes.append(row)
            if probes:
                out["tracking"]["probe_templates"] = probes
    return out


def is_supported_asset_path(path: str | Path) -> bool:
    try:
        return Path(path).suffix.casefold() in SUPPORTED_ASSET_EXTS
    except Exception:
        return False


def normalize_ar_track(value: Any, *, index: int = 0) -> dict[str, Any]:
    """Return a stable AR/PBR track dict.

    Unknown fields are intentionally dropped so project I/O can use the returned
    dict as a clean persistence payload.
    """
    data = _as_mapping(value)
    start_ms = max(0, _coerce_int(data.get("start_ms"), 0))
    end_ms = _coerce_int(data.get("end_ms"), start_ms)
    duration_ms = _coerce_int(data.get("duration_ms"), 0)
    if end_ms <= start_ms and duration_ms > 0:
        end_ms = start_ms + duration_ms
    if end_ms <= start_ms:
        end_ms = start_ms + 1000
    asset_path = str(data.get("asset_path") or "")
    track_id = str(data.get("id") or f"ar_pbr_{index + 1:03d}")
    if "material_override" in data:
        material_override = _coerce_bool(data.get("material_override"), False)
    else:
        material_override = "material" in data
    return {
        "id": track_id,
        "type": "ar_pbr_object",
        "asset_path": asset_path,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "transform": normalize_transform(data.get("transform")),
        "camera_solution_id": str(data.get("camera_solution_id") or ""),
        "camera_solution": normalize_camera_solution(data.get("camera_solution")),
        "depth_source_id": str(data.get("depth_source_id") or ""),
        "occlusion": _coerce_bool(data.get("occlusion"), True),
        "shadow_catcher": _coerce_bool(data.get("shadow_catcher"), True),
        "reflection_catcher": _coerce_bool(data.get("reflection_catcher"), False),
        "color_match": normalize_color_match(data.get("color_match")),
        "material": normalize_material(data.get("material")),
        "material_override": material_override,
        "render": normalize_render_settings(data.get("render")),
        "placement": normalize_placement(data.get("placement")),
        "animation": normalize_animation_settings(data.get("animation")),
    }


def normalize_ar_tracks(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)):
        return []
    return [normalize_ar_track(row, index=idx) for idx, row in enumerate(values)]


def track_active_at(track: Mapping[str, Any], time_ms: int) -> bool:
    start_ms = _coerce_int(track.get("start_ms"), 0)
    end_ms = _coerce_int(track.get("end_ms"), start_ms)
    return start_ms <= int(time_ms) < end_ms


def track_schema_diagnostics(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    unsupported: list[str] = []
    missing: list[str] = []
    for track in tracks:
        path = str(track.get("asset_path") or "")
        if not path:
            missing.append(str(track.get("id") or ""))
        elif not is_supported_asset_path(path):
            unsupported.append(path)
    return {
        "track_count": len(tracks),
        "missing_asset_path_count": len(missing),
        "unsupported_asset_count": len(unsupported),
        "missing_asset_track_ids": missing,
        "unsupported_asset_paths": unsupported,
    }
