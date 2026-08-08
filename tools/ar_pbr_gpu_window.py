"""Standalone GPU AR/PBR mesh viewer.

This is a direct OpenGL preview for imported AR/PBR asset descriptors. It is
meant for fast model inspection; the video-compositor contract remains in
app/ar_pbr/compositor.py.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QMouseEvent, QSurfaceFormat, QWheelEvent
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import (
    QApplication,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.ar_pbr.importer import import_asset
from app.ar_pbr.ambient_occlusion import (
    DEFAULT_AMBIENT_OCCLUSION_MODE,
    DEFAULT_AO_AMBIENT,
    DEFAULT_AO_COLOR,
    DEFAULT_AO_DIFFUSE,
    DEFAULT_AO_DISTANCE,
    DEFAULT_AO_RADIUS,
    DEFAULT_AO_SPECULAR,
    DEFAULT_AO_STRENGTH,
    normalize_ambient_occlusion_settings,
)
from app.ar_pbr.hdr import HdrImage, image_stats, load_radiance_hdr
from app.ar_pbr.render_profile import (
    PROFILE_AUTHORED,
    PROFILE_MARMOSET_PBR,
    PROFILE_VRM_MTOON,
    inspect_asset_render_profiles_from_descriptor,
    marmoset_pbr_available,
    vrm_mtoon_available,
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
    normalize_catcher_settings,
)
from app.ar_pbr.depth_occlusion import (
    DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX,
    DEFAULT_DEPTH_EDGE_GLOW_STRENGTH,
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
    normalize_anisotropic_material_settings,
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
    normalize_microsurface_settings,
)
from app.ar_pbr.bevel import (
    DEFAULT_BEVEL_EDGE_WIDTH,
    DEFAULT_BEVEL_MODE,
    DEFAULT_BEVEL_RADIUS,
    DEFAULT_BEVEL_SAMPLES,
    DEFAULT_BEVEL_STRENGTH,
    normalize_bevel_settings,
)
from app.ar_pbr.clearcoat import (
    DEFAULT_CLEARCOAT_IOR,
    DEFAULT_CLEARCOAT_MODE,
    DEFAULT_CLEARCOAT_ROUGHNESS,
    DEFAULT_CLEARCOAT_STRENGTH,
    DEFAULT_CLEARCOAT_TINT,
    normalize_clearcoat_settings,
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
    normalize_cloth_sheen_settings,
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
    normalize_glint_sparkle_settings,
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
    normalize_caustics_settings,
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
    normalize_depth_of_field_settings,
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
    normalize_hair_groom_settings,
)
from app.ar_pbr.hybrid_rendering import (
    DEFAULT_DENOISE_STRENGTH,
    DEFAULT_DIFFUSE_GI_STRENGTH,
    DEFAULT_HYBRID_SAMPLE_COUNT,
    DEFAULT_SPECULAR_GI_STRENGTH,
    normalize_hybrid_render_settings,
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
    normalize_ray_gi_detail_settings,
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
    normalize_material_layering_settings,
)
from app.ar_pbr.subsurface import (
    DEFAULT_SUBSURFACE_COLOR,
    DEFAULT_SUBSURFACE_MODE,
    DEFAULT_SUBSURFACE_POWER,
    DEFAULT_SUBSURFACE_RADIUS,
    DEFAULT_SUBSURFACE_STRENGTH,
    DEFAULT_SUBSURFACE_THICKNESS,
    DEFAULT_SUBSURFACE_WRAP,
    normalize_subsurface_settings,
)
from app.ar_pbr.surface import (
    DEFAULT_SURFACE_METALLIC,
    DEFAULT_SURFACE_OVERRIDE_STRENGTH,
    DEFAULT_SURFACE_REFLECTANCE,
    DEFAULT_SURFACE_ROUGHNESS,
    normalize_surface_settings,
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
    normalize_transmission_settings,
)
from app.ar_pbr.parallax import (
    DEFAULT_PARALLAX_CENTER,
    DEFAULT_PARALLAX_DEPTH,
    DEFAULT_PARALLAX_MODE,
    DEFAULT_PARALLAX_STEPS,
    DEFAULT_PARALLAX_STRENGTH,
    normalize_parallax_settings,
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
    normalize_displacement_settings,
)
from app.ar_pbr.post_effects import (
    DEFAULT_BLOOM_ANAMORPHIC_RATIO,
    DEFAULT_BLOOM_ANAMORPHIC_STRENGTH,
    DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD,
    DEFAULT_BLOOM_BOOST,
    DEFAULT_BLOOM_RADIUS,
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
    normalize_post_effects_settings,
)
from app.ar_pbr.lens_effects import (
    DEFAULT_CHROMATIC_ABERRATION_PX,
    DEFAULT_CHROMATIC_ABERRATION_STRENGTH,
    DEFAULT_LENS_CENTER,
    DEFAULT_LENS_DISTORTION_K2,
    DEFAULT_LENS_DISTORTION_STRENGTH,
    DEFAULT_LENS_EDGE_FALLOFF,
    DEFAULT_LENS_EFFECTS_MODE,
    normalize_lens_effects_settings,
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
    normalize_lens_flare_settings,
)
from app.ar_pbr.triplanar import (
    DEFAULT_TRIPLANAR_BLEND_SHARPNESS,
    DEFAULT_TRIPLANAR_MODE,
    DEFAULT_TRIPLANAR_OFFSET,
    DEFAULT_TRIPLANAR_SCALE,
    DEFAULT_TRIPLANAR_STRENGTH,
    normalize_triplanar_settings,
)
from app.ar_pbr.tone_mapping import (
    DEFAULT_TONE_EXPOSURE,
    DEFAULT_TONE_GAMMA,
    DEFAULT_TONE_MAPPING,
    DEFAULT_TONE_WHITE_BALANCE,
    normalize_color_management_settings,
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
    SHADOW_PCF_KERNEL,
    normalize_shadow_settings,
    shadow_filter_diagnostics as build_shadow_filter_diagnostics,
)
from app.ar_pbr.sample_assets import default_ar_pbr_preview_asset


DEFAULT_EXTERNAL_ASSET = default_ar_pbr_preview_asset()
try:
    from app.ar_pbr.hdri_presets import default_hdri_path

    DEFAULT_HDRI = default_hdri_path()
except Exception:
    DEFAULT_HDRI = ROOT / "resources" / "ar_pbr" / "hdri" / "wide_street_01_1k.hdr"
DEFAULT_FRAME_FIT_PADDING = 0.06
FRAME_FIT_FOV_DEG = 45.0
VRM_MTOON_UNLIT_EXPOSURE_SCALE = 1.0
VRM_MTOON_UNLIT_CONTRAST = 1.0
VRM_MTOON_UNLIT_GAMMA = 1.35
GPU_SKINNING_MAX_BONES = 128
GPU_VERTEX_STRIDE_FLOAT_COUNT = 29
GPU_VERTEX_BASE_STRIDE_FLOAT_COUNT = 21


VERT_SHADER = """
#version 330 core
const int MAX_SKIN_BONES = 128;
layout(location = 0) in vec3 a_pos;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec4 a_color;
layout(location = 3) in vec3 a_material;
layout(location = 4) in vec2 a_uv;
layout(location = 5) in vec3 a_tangent;
layout(location = 6) in vec3 a_bitangent;
layout(location = 7) in vec4 a_bone_indices;
layout(location = 8) in vec4 a_bone_weights;
uniform mat4 u_mvp;
uniform mat4 u_model;
uniform mat4 u_light_mvp;
uniform mat3 u_normal_mat;
uniform int u_skinning_enabled;
uniform int u_skin_bone_count;
uniform mat4 u_skin_bones[MAX_SKIN_BONES];
uniform vec3 u_bounds_center;
uniform float u_bounds_max_size;
uniform int u_stage_transform_enabled;
uniform int u_stage_rotate_y_180;
uniform vec3 u_stage_center;
uniform vec3 u_stage_offset;
out vec3 v_world_pos;
out vec4 v_light_pos;
out vec3 v_normal;
out vec4 v_color;
out vec3 v_material;
out vec2 v_uv;
out vec3 v_tangent;
out vec3 v_bitangent;
mat4 skin_bone(float raw_index) {
    int idx = int(raw_index + 0.5);
    if (idx < 0 || idx >= u_skin_bone_count || idx >= MAX_SKIN_BONES) {
        return mat4(1.0);
    }
    return u_skin_bones[idx];
}
void main() {
    vec3 raw_object_pos = a_pos * u_bounds_max_size + u_bounds_center;
    vec3 object_normal = a_normal;
    vec3 object_tangent = a_tangent;
    vec3 object_bitangent = a_bitangent;
    float weight_sum = a_bone_weights.x + a_bone_weights.y + a_bone_weights.z + a_bone_weights.w;
    if (u_skinning_enabled != 0 && weight_sum > 0.0001 && u_bounds_max_size > 0.000001) {
        mat4 skin =
            skin_bone(a_bone_indices.x) * a_bone_weights.x +
            skin_bone(a_bone_indices.y) * a_bone_weights.y +
            skin_bone(a_bone_indices.z) * a_bone_weights.z +
            skin_bone(a_bone_indices.w) * a_bone_weights.w;
        vec4 skinned_pos = skin * vec4(raw_object_pos, 1.0);
        raw_object_pos = skinned_pos.xyz;
        object_normal = normalize(mat3(skin) * a_normal);
        object_tangent = normalize(mat3(skin) * a_tangent);
        object_bitangent = normalize(mat3(skin) * a_bitangent);
    }
    if (u_stage_transform_enabled != 0) {
        if (u_stage_rotate_y_180 != 0) {
            raw_object_pos.x = u_stage_center.x - (raw_object_pos.x - u_stage_center.x);
            raw_object_pos.z = u_stage_center.z - (raw_object_pos.z - u_stage_center.z);
            object_normal.xz *= -1.0;
            object_tangent.xz *= -1.0;
            object_bitangent.xz *= -1.0;
        }
        raw_object_pos += u_stage_offset;
    }
    vec3 object_pos = (raw_object_pos - u_bounds_center) / u_bounds_max_size;
    vec4 world_pos = u_model * vec4(object_pos, 1.0);
    gl_Position = u_mvp * vec4(object_pos, 1.0);
    v_world_pos = world_pos.xyz;
    v_light_pos = u_light_mvp * vec4(object_pos, 1.0);
    v_normal = normalize(u_normal_mat * object_normal);
    v_color = a_color;
    v_material = a_material;
    v_uv = a_uv;
    v_tangent = normalize(u_normal_mat * object_tangent);
    v_bitangent = normalize(u_normal_mat * object_bitangent);
}
"""


FRAG_SHADER = """
#version 330 core
const float PI = 3.14159265358979323846;
in vec3 v_world_pos;
in vec4 v_light_pos;
in vec3 v_normal;
in vec4 v_color;
in vec3 v_material;
in vec2 v_uv;
in vec3 v_tangent;
in vec3 v_bitangent;
uniform vec3 u_light_dir;
uniform vec3 u_light_color;
uniform vec3 u_camera_pos;
uniform sampler2D u_hdri;
uniform sampler2D u_irradiance;
uniform sampler2D u_prefilter;
uniform sampler2D u_brdf_lut;
uniform sampler2D u_base_map;
uniform sampler2D u_roughness_map;
uniform sampler2D u_metallic_map;
uniform sampler2D u_specular_map;
uniform sampler2D u_normal_map;
uniform sampler2D u_occlusion_map;
uniform sampler2D u_emissive_map;
uniform sampler2D u_opacity_map;
uniform sampler2D u_height_map;
uniform sampler2D u_shadow_map;
uniform int u_has_hdri;
uniform int u_has_ibl_probe;
uniform int u_has_base_map;
uniform int u_has_roughness_map;
uniform int u_has_metallic_map;
uniform int u_has_specular_map;
uniform int u_has_normal_map;
uniform int u_has_occlusion_map;
uniform int u_has_emissive_map;
uniform int u_has_opacity_map;
uniform int u_has_height_map;
uniform int u_base_alpha_to_opacity;
uniform int u_has_shadow_map;
uniform float u_ibl_exposure;
uniform float u_unlit_exposure_scale;
uniform float u_unlit_contrast;
uniform float u_unlit_output_gamma;
uniform float u_ibl_rotation;
uniform float u_max_lod;
uniform float u_prefilter_level_count;
uniform float u_direct_intensity;
uniform float u_shadow_strength;
uniform float u_shadow_pcf_radius;
uniform float u_shadow_pcss_blocker_radius;
uniform float u_shadow_bias;
uniform float u_shadow_normal_bias;
uniform float u_self_shadow_strength;
uniform int u_shadow_filter_mode;
uniform float u_alpha_cutoff;
uniform vec3 u_emissive_factor;
uniform int u_tone_mapping_mode;
uniform float u_tone_exposure;
uniform vec3 u_tone_white_balance;
uniform float u_tone_gamma;
uniform int u_hybrid_sample_count;
uniform float u_diffuse_gi_strength;
uniform float u_specular_gi_strength;
uniform float u_denoise_strength;
uniform float u_transmission;
uniform float u_refraction_strength;
uniform float u_ior;
uniform float u_thickness;
uniform vec3 u_absorption_color;
uniform float u_clearcoat_strength;
uniform float u_clearcoat_roughness;
uniform float u_clearcoat_ior;
uniform vec3 u_clearcoat_tint;
uniform float u_parallax_strength;
uniform float u_parallax_depth;
uniform float u_parallax_center;
uniform int u_parallax_steps;
uniform float u_bevel_strength;
uniform float u_bevel_radius;
uniform float u_bevel_edge_width;
uniform float u_material_layer_blend;
uniform vec3 u_material_layer_color;
uniform float u_material_layer_roughness;
uniform float u_material_layer_metallic;
uniform float u_material_layer_alpha;
uniform float u_material_layer_emissive_strength;
uniform float u_material_layer_mask_strength;
uniform float u_surface_override_strength;
uniform float u_surface_roughness;
uniform float u_surface_metallic;
uniform float u_surface_reflectance;
uniform float u_subsurface_strength;
uniform vec3 u_subsurface_color;
uniform float u_subsurface_radius;
uniform float u_subsurface_power;
uniform float u_subsurface_wrap;
uniform float u_subsurface_thickness;
uniform float u_hair_groom_strength;
uniform vec3 u_hair_groom_tint;
uniform float u_hair_primary_shift;
uniform float u_hair_secondary_shift;
uniform float u_hair_primary_roughness;
uniform float u_hair_secondary_roughness;
uniform float u_hair_secondary_strength;
uniform float u_hair_anisotropy;
uniform float u_hair_rim_strength;
uniform float u_cloth_sheen_strength;
uniform vec3 u_cloth_sheen_color;
uniform float u_cloth_sheen_roughness;
uniform vec3 u_cloth_sheen_edge_tint;
uniform float u_cloth_sheen_fiber_strength;
uniform float u_cloth_sheen_wrap;
uniform float u_cloth_sheen_retroreflection;
uniform float u_glint_strength;
uniform vec3 u_glint_color;
uniform float u_glint_density;
uniform float u_glint_scale;
uniform float u_glint_threshold;
uniform float u_glint_sharpness;
uniform float u_glint_roughness_jitter;
uniform float u_triplanar_strength;
uniform float u_triplanar_scale;
uniform float u_triplanar_blend_sharpness;
uniform vec3 u_triplanar_offset;
uniform float u_screen_ao_strength;
uniform float u_screen_ao_radius;
uniform float u_screen_ao_distance;
uniform vec3 u_screen_ao_color;
uniform int u_screen_ao_ambient;
uniform int u_screen_ao_diffuse;
uniform int u_screen_ao_specular;
layout(location = 0) out vec4 frag_color;
layout(location = 1) out vec4 bloom_source;

vec2 dir_to_equirect(vec3 dir) {
    vec3 d = normalize(dir);
    float u = atan(d.z, d.x) / (2.0 * PI) + 0.5 + u_ibl_rotation;
    float v = 0.5 - asin(clamp(d.y, -1.0, 1.0)) / PI;
    return vec2(fract(u), clamp(v, 0.0, 1.0));
}

vec3 sample_env(vec3 dir, float lod) {
    if (u_has_hdri == 0) {
        vec3 up = vec3(0.18, 0.22, 0.28);
        vec3 side = vec3(0.72, 0.70, 0.66);
        return mix(side, up, clamp(normalize(dir).y * 0.5 + 0.5, 0.0, 1.0)) * u_ibl_exposure;
    }
    return textureLod(u_hdri, dir_to_equirect(dir), lod).rgb * u_ibl_exposure;
}

vec3 sample_irradiance(vec3 dir) {
    if (u_has_ibl_probe == 1) {
        return texture(u_irradiance, dir_to_equirect(dir)).rgb * u_ibl_exposure;
    }
    return sample_env(dir, max(u_max_lod - 2.0, 0.0));
}

vec3 sample_prefiltered_env(vec3 dir, float roughness) {
    if (u_has_ibl_probe == 1 && u_prefilter_level_count > 0.5) {
        float level = clamp(roughness * roughness, 0.0, 1.0) * max(0.0, u_prefilter_level_count - 1.0);
        return textureLod(u_prefilter, dir_to_equirect(dir), level).rgb * u_ibl_exposure;
    }
    return sample_env(dir, roughness * u_max_lod);
}

vec2 sample_brdf_lut(float ndotv, float roughness) {
    if (u_has_ibl_probe == 1) {
        return texture(u_brdf_lut, vec2(clamp(ndotv, 0.0, 1.0), clamp(roughness, 0.0, 1.0))).rg;
    }
    return vec2(1.25 - roughness * 0.45, 0.0);
}

float screen_space_ao_factor(vec3 normal, vec3 view_dir, vec3 world_pos) {
    float strength = clamp(u_screen_ao_strength, 0.0, 2.0);
    if (strength <= 0.0001) {
        return 1.0;
    }
    vec3 n = normalize(normal);
    vec3 v = normalize(view_dir);
    float ndotv = clamp(dot(n, v), 0.0, 1.0);
    float radius = max(u_screen_ao_radius, 0.5);
    float distance = max(u_screen_ao_distance, 0.01);
    vec3 dn_dx = dFdx(n);
    vec3 dn_dy = dFdy(n);
    vec3 dp_dx = dFdx(world_pos);
    vec3 dp_dy = dFdy(world_pos);
    float curvature = length(dn_dx) + length(dn_dy);
    float depth_gradient = length(vec2(dFdx(world_pos.z), dFdy(world_pos.z)));
    float footprint = max(max(length(dp_dx), length(dp_dy)), 0.0001);
    float crease = smoothstep(0.015, 0.22, curvature * radius * 0.42);
    float contact = smoothstep(0.005, max(0.006, distance * 0.34), depth_gradient * radius / max(footprint, 0.0001) * 0.025);
    float horizon = smoothstep(0.18, 0.92, pow(1.0 - ndotv, 1.35));
    float underside = smoothstep(0.10, 0.82, -n.y) * 0.22;
    float micro = pow(clamp(curvature * radius * 0.22, 0.0, 1.0), 1.8) * 0.35;
    float occlusion = clamp(crease * 0.46 + contact * 0.34 + horizon * 0.18 + underside + micro, 0.0, 1.0);
    occlusion = smoothstep(0.02, 0.96, occlusion);
    return clamp(1.0 - occlusion * strength, 0.0, 1.0);
}

vec3 tonemap_aces(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 tonemap_reinhard(vec3 x) {
    x = max(x, vec3(0.0));
    return clamp(x / (vec3(1.0) + x), 0.0, 1.0);
}

vec3 tonemap_agx(vec3 x) {
    x = log2(max(x, vec3(0.000001)));
    x = clamp((x + vec3(12.47393)) / 16.5, 0.0, 1.0);
    return clamp(x * x * (vec3(3.0) - 2.0 * x), 0.0, 1.0);
}

vec3 apply_output_transform_gamma(vec3 rgb, float gamma) {
    vec3 x = max(rgb, vec3(0.0)) * exp2(u_tone_exposure) * max(u_tone_white_balance, vec3(0.0001));
    vec3 mapped = u_tone_mapping_mode == 1
        ? tonemap_agx(x)
        : (u_tone_mapping_mode == 2 ? tonemap_reinhard(x) : tonemap_aces(x));
    return pow(clamp(mapped, 0.0, 1.0), vec3(1.0 / max(gamma, 0.1)));
}

vec3 apply_output_transform(vec3 rgb) {
    return apply_output_transform_gamma(rgb, u_tone_gamma);
}

float hybrid_sample_gain() {
    return 1.0 - exp(-max(float(u_hybrid_sample_count), 1.0) / 8.0);
}

vec3 triplanar_axis_weights(vec3 normal) {
    vec3 w = pow(abs(normalize(normal)), vec3(max(u_triplanar_blend_sharpness, 1.0)));
    return w / max(w.x + w.y + w.z, 0.000001);
}

vec2 triplanar_axis_uv(vec3 pos, int axis) {
    vec3 p = pos * max(u_triplanar_scale, 0.0001) + u_triplanar_offset;
    if (axis == 0) {
        return p.zy;
    }
    if (axis == 1) {
        return p.xz;
    }
    return p.xy;
}

vec4 sample_material_rgba(sampler2D tex, vec2 uv, vec3 world_pos, vec3 normal) {
    vec4 uv_sample = texture(tex, uv);
    float strength = clamp(u_triplanar_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return uv_sample;
    }
    vec3 w = triplanar_axis_weights(normal);
    vec4 tri_sample =
        texture(tex, triplanar_axis_uv(world_pos, 0)) * w.x +
        texture(tex, triplanar_axis_uv(world_pos, 1)) * w.y +
        texture(tex, triplanar_axis_uv(world_pos, 2)) * w.z;
    return mix(uv_sample, tri_sample, strength);
}

vec2 apply_parallax_uv(vec2 uv, vec3 view_dir, vec3 tangent, vec3 bitangent, vec3 normal, vec3 world_pos) {
    if (u_has_height_map != 1 || u_parallax_strength <= 0.0001 || u_parallax_depth <= 0.0001) {
        return uv;
    }
    vec3 n = normalize(normal);
    vec3 t = normalize(tangent);
    vec3 b = normalize(bitangent);
    if (length(t) <= 0.001 || length(b) <= 0.001) {
        t = vec3(1.0, 0.0, 0.0);
        b = normalize(cross(n, t));
    }
    vec3 v = normalize(view_dir);
    float view_z = max(abs(dot(v, n)), 0.18);
    vec2 view_xy = vec2(dot(v, t), dot(v, b)) / view_z;
    int steps = clamp(u_parallax_steps, 1, 64);
    if (steps > 1) {
        float layer_step = 1.0 / float(steps);
        vec2 ray = vec2(view_xy.x, -view_xy.y) * u_parallax_depth * u_parallax_strength;
        vec2 delta = ray / float(steps);
        vec2 current_uv = uv;
        vec2 previous_uv = uv;
        float current_layer = 0.0;
        float previous_layer = 0.0;
        float center_bias = clamp(u_parallax_center, 0.0, 1.0) - 0.5;
        float surface_depth = clamp(
            1.0 - sample_material_rgba(u_height_map, current_uv, world_pos, n).r + center_bias,
            0.0,
            1.0
        );
        for (int i = 0; i < 64; ++i) {
            if (i >= steps || current_layer >= surface_depth) {
                break;
            }
            previous_uv = current_uv;
            previous_layer = current_layer;
            current_uv -= delta;
            current_layer += layer_step;
            surface_depth = clamp(
                1.0 - sample_material_rgba(u_height_map, current_uv, world_pos, n).r + center_bias,
                0.0,
                1.0
            );
        }
        float current_error = current_layer - surface_depth;
        float previous_depth = clamp(
            1.0 - sample_material_rgba(u_height_map, previous_uv, world_pos, n).r + center_bias,
            0.0,
            1.0
        );
        float previous_error = previous_depth - previous_layer;
        float blend = clamp(
            previous_error / max(previous_error + current_error, 0.000001),
            0.0,
            1.0
        );
        return clamp(mix(previous_uv, current_uv, blend), vec2(-0.25), vec2(1.25));
    }
    float height = sample_material_rgba(u_height_map, uv, world_pos, n).r;
    float amount = (height - clamp(u_parallax_center, 0.0, 1.0)) * u_parallax_depth * u_parallax_strength;
    return clamp(uv + view_xy * amount, vec2(-0.25), vec2(1.25));
}

vec3 apply_bevel_normal(vec3 normal, vec3 tangent, vec3 bitangent, vec2 uv) {
    if (u_bevel_strength <= 0.0001 || u_bevel_radius <= 0.0001 || u_bevel_edge_width <= 0.0001) {
        return normalize(normal);
    }
    vec2 local = fract(uv);
    vec2 edge_dist = min(local, vec2(1.0) - local);
    float edge = min(edge_dist.x, edge_dist.y);
    float mask = 1.0 - smoothstep(0.0, max(u_bevel_edge_width, 0.0001), edge);
    if (mask <= 0.0001) {
        return normalize(normal);
    }
    vec2 dir = normalize(local - vec2(0.5) + vec2(0.0001, -0.0001));
    float bend = clamp(u_bevel_strength, 0.0, 1.0) * clamp(u_bevel_radius, 0.0, 0.25) * mask;
    return normalize(normal + normalize(tangent) * dir.x * bend + normalize(bitangent) * dir.y * bend);
}

vec3 apply_transmission_refraction(vec3 rgb, vec3 albedo, vec3 normal, vec3 view_dir, float roughness, vec3 fresnel) {
    float transmission = clamp(u_transmission, 0.0, 1.0);
    if (transmission <= 0.0001) {
        return rgb;
    }
    vec3 n = normalize(normal);
    vec3 refracted_dir = refract(-normalize(view_dir), n, 1.0 / max(u_ior, 1.0001));
    if (length(refracted_dir) <= 0.001) {
        refracted_dir = reflect(-normalize(view_dir), n);
    }
    vec3 refracted_env = sample_prefiltered_env(refracted_dir, clamp(roughness + u_refraction_strength * 0.22, 0.0, 1.0));
    vec3 absorption = exp(-max(vec3(0.0), vec3(1.0) - clamp(u_absorption_color, vec3(0.0), vec3(1.0))) * max(u_thickness, 0.0) * 2.0);
    float edge_reflect = clamp((fresnel.r + fresnel.g + fresnel.b) / 3.0, 0.0, 1.0);
    float through = transmission * (1.0 - edge_reflect * 0.45);
    return mix(rgb, refracted_env * absorption, through);
}

vec3 srgb_to_linear(vec3 c) {
    vec3 x = clamp(c, 0.0, 1.0);
    vec3 low = x / 12.92;
    vec3 high = pow((x + vec3(0.055)) / 1.055, vec3(2.4));
    return mix(low, high, step(vec3(0.04045), x));
}

vec3 linear_to_srgb(vec3 c) {
    vec3 x = clamp(c, 0.0, 1.0);
    vec3 low = x * 12.92;
    vec3 high = 1.055 * pow(x, vec3(1.0 / 2.4)) - vec3(0.055);
    return mix(low, high, step(vec3(0.0031308), x));
}

void apply_material_layer(inout vec3 albedo, inout float roughness, inout float metallic, inout float out_alpha, inout vec3 emissive) {
    float layer = clamp(u_material_layer_blend * u_material_layer_mask_strength, 0.0, 1.0);
    if (layer <= 0.0001) {
        return;
    }
    vec3 layer_color = srgb_to_linear(clamp(u_material_layer_color, vec3(0.0), vec3(1.0)));
    albedo = mix(albedo, layer_color, layer);
    roughness = mix(roughness, clamp(u_material_layer_roughness, 0.04, 1.0), layer);
    metallic = mix(metallic, clamp(u_material_layer_metallic, 0.0, 1.0), layer);
    out_alpha *= mix(1.0, clamp(u_material_layer_alpha, 0.0, 1.0), layer);
    emissive += layer_color * max(u_material_layer_emissive_strength, 0.0) * layer;
}

void apply_surface_override(inout float roughness, inout float metallic, inout float reflectance) {
    float mix_amount = clamp(u_surface_override_strength, 0.0, 1.0);
    if (mix_amount <= 0.0001) {
        return;
    }
    roughness = mix(roughness, clamp(u_surface_roughness, 0.04, 1.0), mix_amount);
    metallic = mix(metallic, clamp(u_surface_metallic, 0.0, 1.0), mix_amount);
    reflectance = mix(reflectance, clamp(u_surface_reflectance, 0.0, 1.0), mix_amount);
}

vec3 apply_subsurface_lighting(vec3 rgb, vec3 albedo, vec3 normal, vec3 view_dir, vec3 light_dir, float ndotl, float ao, vec3 irradiance, float direct_power) {
    float strength = clamp(u_subsurface_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return rgb;
    }
    vec3 n = normalize(normal);
    vec3 l = normalize(light_dir);
    vec3 v = normalize(view_dir);
    float wrap = clamp(u_subsurface_wrap, 0.0, 1.0);
    float wrap_light = clamp((dot(n, l) + wrap) / max(1.0 + wrap, 0.000001), 0.0, 1.0);
    float back = pow(clamp(dot(-n, l), 0.0, 1.0), max(u_subsurface_power, 0.5));
    float edge = pow(clamp(1.0 - dot(n, v), 0.0, 1.0), 1.5);
    float radius = clamp(u_subsurface_radius, 0.0, 4.0);
    float thickness = clamp(u_subsurface_thickness, 0.0, 2.0);
    float scatter_shape = pow(wrap_light, 1.0 / max(u_subsurface_power, 0.5)) * 0.58 + back * 0.42;
    vec3 scatter = albedo
        * clamp(u_subsurface_color, vec3(0.0), vec3(1.0))
        * (scatter_shape * (0.65 + radius * 0.35) + edge * (0.20 + thickness * 0.15))
        * (vec3(0.35) + irradiance * 0.65)
        * max(direct_power, 0.0)
        * strength
        * (0.45 + thickness)
        * (0.35 + ao * 0.65)
        * (1.0 - clamp(ndotl, 0.0, 1.0) * 0.22);
    return rgb + scatter;
}

float hair_groom_lobe(vec3 tangent, vec3 normal, vec3 half_vec, float shift, float lobe_roughness, float ndoth) {
    vec3 shifted = normalize(tangent + normal * shift);
    float tdoth = clamp(dot(shifted, normalize(half_vec)), -1.0, 1.0);
    float strand = sqrt(max(1.0 - tdoth * tdoth, 0.0));
    float width = clamp(lobe_roughness, 0.03, 1.0);
    float exponent = 8.0 + (1.0 - width) * 88.0;
    float anisotropic = pow(clamp(strand, 0.0, 1.0), exponent);
    float isotropic = pow(clamp(ndoth, 0.0, 1.0), 2.0 + (1.0 - width) * 54.0);
    return mix(isotropic, anisotropic, clamp(u_hair_anisotropy, 0.0, 1.0));
}

vec3 apply_hair_groom_lighting(vec3 rgb, vec3 normal, vec3 tangent, vec3 view_dir, vec3 light_dir, float ndotl, float ndotv, float ndoth, float roughness, float ao, float direct_power, vec3 spec_env) {
    float strength = clamp(u_hair_groom_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return rgb;
    }
    vec3 n = normalize(normal);
    vec3 t = normalize(tangent - n * dot(tangent, n));
    if (length(t) <= 0.001) {
        t = normalize(abs(n.x) < 0.9 ? cross(n, vec3(1.0, 0.0, 0.0)) : cross(n, vec3(0.0, 1.0, 0.0)));
    }
    vec3 l = normalize(light_dir);
    vec3 v = normalize(view_dir);
    vec3 h = normalize(l + v);
    float primary_width = clamp(u_hair_primary_roughness * 0.72 + roughness * 0.28, 0.03, 1.0);
    float secondary_width = clamp(u_hair_secondary_roughness * 0.72 + roughness * 0.28, 0.03, 1.0);
    float primary = hair_groom_lobe(t, n, h, u_hair_primary_shift, primary_width, ndoth);
    float secondary = hair_groom_lobe(t, n, h, u_hair_secondary_shift, secondary_width, ndoth) * clamp(u_hair_secondary_strength, 0.0, 1.5);
    float tl_dot = clamp(dot(t, l), -1.0, 1.0);
    float tv_dot = clamp(dot(t, v), -1.0, 1.0);
    float tl = sqrt(max(1.0 - tl_dot * tl_dot, 0.0));
    float tv = sqrt(max(1.0 - tv_dot * tv_dot, 0.0));
    float strand_gate = clamp(tl * tv, 0.0, 1.0);
    float facing = clamp(ndotl * 0.65 + 0.35, 0.0, 1.0) * clamp(ndotv * 0.55 + 0.45, 0.0, 1.0);
    float rim = pow(clamp(1.0 - ndotv, 0.0, 1.0), 2.0) * clamp(u_hair_rim_strength, 0.0, 1.0);
    vec3 tint = srgb_to_linear(clamp(u_hair_groom_tint, vec3(0.0), vec3(1.0)));
    vec3 direct = (primary + secondary) * tint * strand_gate * facing * max(direct_power, 0.0) * strength * mix(0.28, 1.0, ao);
    vec3 env = spec_env * tint * (primary * 0.12 + rim) * strength * mix(0.35, 1.0, ao);
    return rgb + direct + env;
}

vec3 apply_cloth_sheen_lighting(vec3 rgb, vec3 albedo, vec3 normal, vec3 view_dir, vec3 light_dir, float ndotl, float ndotv, float ndoth, float roughness, float ao, float direct_power, vec3 spec_env) {
    float strength = clamp(u_cloth_sheen_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return rgb;
    }
    vec3 n = normalize(normal);
    vec3 l = normalize(light_dir);
    vec3 v = normalize(view_dir);
    float sheen_roughness = clamp(u_cloth_sheen_roughness * 0.72 + roughness * 0.28, 0.03, 1.0);
    float ndoth_clamped = clamp(ndoth, 0.0, 1.0);
    float sin_h = sqrt(max(1.0 - ndoth_clamped * ndoth_clamped, 0.0));
    float charlie = pow(sin_h, 1.0 + sheen_roughness * 9.0) * (0.45 + sheen_roughness * 0.75);
    float wrap = clamp(u_cloth_sheen_wrap, 0.0, 1.0);
    float wrap_light = clamp((dot(n, l) + wrap) / max(1.0 + wrap, 0.000001), 0.0, 1.0);
    float edge = pow(clamp(1.0 - ndotv, 0.0, 1.0), 2.0);
    float retro = pow(clamp(dot(l, v) * 0.5 + 0.5, 0.0, 1.0), 3.0) * clamp(u_cloth_sheen_retroreflection, 0.0, 1.0);
    float fuzz = edge * wrap_light * clamp(u_cloth_sheen_fiber_strength, 0.0, 1.0);
    vec3 cloth_color = srgb_to_linear(clamp(u_cloth_sheen_color, vec3(0.0), vec3(1.0)));
    vec3 edge_tint = srgb_to_linear(clamp(u_cloth_sheen_edge_tint, vec3(0.0), vec3(1.0)));
    vec3 cloth_tint = albedo * 0.38 + cloth_color * 0.62;
    vec3 sheen = (charlie * (0.35 + ndotl * 0.65) + retro * wrap_light) * cloth_tint * max(direct_power, 0.0) * strength * mix(0.30, 1.0, ao);
    vec3 fiber = (fuzz * edge_tint + edge * spec_env * 0.18) * strength * mix(0.35, 1.0, ao);
    return rgb + sheen + fiber;
}

float glint_hash21(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec3 apply_glint_sparkle_lighting(vec3 rgb, vec2 uv, vec3 world_pos, vec3 view_dir, vec3 light_dir, float ndotl, float ndotv, float ndoth, float roughness, float ao, float direct_power, vec3 spec_env) {
    float strength = clamp(u_glint_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return rgb;
    }
    float scale = max(u_glint_scale, 1.0);
    vec2 cell = floor(uv * scale + world_pos.xy * 0.27 + vec2(world_pos.z * 0.11, -world_pos.z * 0.07));
    float seed = glint_hash21(cell);
    float seed_b = glint_hash21(cell + vec2(19.19, -7.31));
    float density = clamp(u_glint_density, 0.0, 1.0);
    float threshold = clamp(u_glint_threshold, 0.0, 0.98);
    float density_gate = clamp((seed - (1.0 - density)) / max(density, 0.00001), 0.0, 1.0);
    float sparkle_gate = smoothstep(threshold, 1.0, density_gate * seed_b);
    float jitter = clamp(u_glint_roughness_jitter, 0.0, 1.0);
    float micro_rough = clamp(roughness * (1.0 - jitter * (0.35 + seed_b * 0.55)), 0.015, 1.0);
    float sharpness = clamp(u_glint_sharpness, 1.0, 64.0);
    float exponent = max((10.0 + sharpness * 3.2) * (1.0 - micro_rough * 0.58), 2.0);
    float needle = pow(clamp(ndoth, 0.0, 1.0), exponent);
    float grazing = pow(clamp(1.0 - ndotv, 0.0, 1.0), 3.0);
    float flake_floor = (1.0 - roughness) * 0.035;
    float glitter = sparkle_gate * (needle * (0.55 + ndotl * 0.45) + grazing * 0.12 + flake_floor);
    vec3 tint = srgb_to_linear(clamp(u_glint_color, vec3(0.0), vec3(1.0)));
    vec3 direct = glitter * tint * max(direct_power, 0.0) * strength * mix(0.35, 1.0, ao);
    vec3 env = sparkle_gate * spec_env * tint * (0.08 + grazing * 0.34) * (1.0 - roughness * 0.55) * strength * mix(0.35, 1.0, ao);
    return rgb + direct + env;
}

vec3 fresnel_schlick(float cos_theta, vec3 f0) {
    return f0 + (1.0 - f0) * pow(1.0 - clamp(cos_theta, 0.0, 1.0), 5.0);
}

float distribution_ggx(float ndoth, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float denom = ndoth * ndoth * (a2 - 1.0) + 1.0;
    return a2 / max(PI * denom * denom, 0.000001);
}

float geometry_schlick_ggx(float ndot, float roughness) {
    float r = roughness + 1.0;
    float k = (r * r) / 8.0;
    return ndot / max(ndot * (1.0 - k) + k, 0.000001);
}

float geometry_smith(float ndotv, float ndotl, float roughness) {
    return geometry_schlick_ggx(ndotv, roughness) * geometry_schlick_ggx(ndotl, roughness);
}

vec3 cook_torrance_direct(vec3 albedo, vec3 f0, float roughness, float metallic, float ndotl, float ndotv, float ndoth, float vdoth, float direct_power) {
    vec3 f = fresnel_schlick(vdoth, f0);
    vec3 kd = (vec3(1.0) - f) * (1.0 - metallic);
    vec3 diffuse = kd * albedo / PI;
    float d = distribution_ggx(ndoth, roughness);
    float g = geometry_smith(ndotv, ndotl, roughness);
    vec3 specular = (d * g * f) / max(4.0 * ndotv * ndotl, 0.00001);
    return (diffuse + specular) * ndotl * max(direct_power, 0.0);
}

vec3 apply_clearcoat_layer(vec3 rgb, vec3 normal, vec3 view_dir, vec3 light_dir, float roughness, float ndotv, float ndotl, float ndoth, float vdoth, float ao, float direct_power) {
    float strength = clamp(u_clearcoat_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return rgb;
    }
    float coat_roughness = clamp(u_clearcoat_roughness, 0.02, 1.0);
    float eta = max(u_clearcoat_ior, 1.0001);
    float f0 = pow((eta - 1.0) / (eta + 1.0), 2.0);
    float coat_fresnel = f0 + (1.0 - f0) * pow(1.0 - clamp(ndotv, 0.0, 1.0), 5.0);
    float half_fresnel = f0 + (1.0 - f0) * pow(1.0 - clamp(vdoth, 0.0, 1.0), 5.0);
    vec3 reflect_dir = reflect(-normalize(view_dir), normalize(normal));
    vec3 coat_env = sample_prefiltered_env(reflect_dir, coat_roughness) * coat_fresnel * (1.18 - coat_roughness * 0.42);
    float d = distribution_ggx(ndoth, coat_roughness);
    float g = geometry_smith(ndotv, ndotl, coat_roughness);
    float direct = (d * g * half_fresnel) / max(4.0 * ndotv * ndotl, 0.00001) * ndotl * max(direct_power, 0.0);
    vec3 tint = clamp(u_clearcoat_tint, vec3(0.0), vec3(1.0));
    vec3 coat = (coat_env + vec3(direct)) * tint * strength * mix(0.40, 1.0, ao);
    float base_attenuation = 1.0 - strength * (0.025 + 0.025 * (1.0 - clamp(roughness, 0.0, 1.0)));
    return rgb * base_attenuation + coat;
}

float shadow_pcf(vec2 uv, float current, float bias, float radius_texels) {
    vec2 texel = max(radius_texels, 0.0) / vec2(textureSize(u_shadow_map, 0));
    float lit = 0.0;
    for (int x = -2; x <= 2; x++) {
        for (int y = -2; y <= 2; y++) {
            float closest = texture(u_shadow_map, uv + vec2(x, y) * texel).r;
            lit += current - bias <= closest ? 1.0 : 0.0;
        }
    }
    return lit / 25.0;
}

float shadow_pcss(vec2 uv, float current, float bias) {
    vec2 search_texel = max(max(u_shadow_pcf_radius, u_shadow_pcss_blocker_radius), 0.0) / vec2(textureSize(u_shadow_map, 0));
    float blocker_sum = 0.0;
    float blocker_count = 0.0;
    for (int x = -2; x <= 2; x++) {
        for (int y = -2; y <= 2; y++) {
            float closest = texture(u_shadow_map, uv + vec2(x, y) * search_texel).r;
            if (closest < current - bias) {
                blocker_sum += closest;
                blocker_count += 1.0;
            }
        }
    }
    if (blocker_count <= 0.5) {
        return 1.0;
    }
    float avg_blocker = blocker_sum / blocker_count;
    float penumbra = clamp(
        (current - avg_blocker) * max(u_shadow_pcss_blocker_radius, 0.0) * 32.0,
        u_shadow_pcf_radius,
        u_shadow_pcf_radius + max(u_shadow_pcss_blocker_radius, 0.0)
    );
    return shadow_pcf(uv, current, bias, penumbra);
}

float shadow_factor(vec4 light_pos, vec3 n, vec3 l) {
    if (u_has_shadow_map == 0) {
        return 1.0;
    }
    vec3 projected = light_pos.xyz / max(light_pos.w, 1e-6);
    projected = projected * 0.5 + 0.5;
    if (projected.x < 0.0 || projected.x > 1.0 || projected.y < 0.0 || projected.y > 1.0 || projected.z > 1.0) {
        return 1.0;
    }
    float normal_light = clamp(dot(n, l), 0.0, 1.0);
    float bias = max(u_shadow_bias, u_shadow_bias + u_shadow_normal_bias * (1.0 - normal_light));
    float lit = u_shadow_filter_mode == 1
        ? shadow_pcss(projected.xy, projected.z, bias)
        : shadow_pcf(projected.xy, projected.z, bias, u_shadow_pcf_radius);
    return mix(1.0 - u_shadow_strength, 1.0, lit);
}

void main() {
    vec3 n = normalize(v_normal);
    vec3 v = normalize(u_camera_pos - v_world_pos);
    if (dot(n, v) < 0.0) {
        n = -n;
    }
    bool unlit = v_material.z < -0.5;
    vec2 material_uv = v_uv;
    material_uv = apply_parallax_uv(material_uv, v, v_tangent, v_bitangent, n, v_world_pos);
    if (u_has_normal_map == 1) {
        vec3 tn = sample_material_rgba(u_normal_map, material_uv, v_world_pos, n).rgb * 2.0 - 1.0;
        mat3 tbn = mat3(normalize(v_tangent), normalize(v_bitangent), n);
        n = normalize(tbn * tn);
        if (dot(n, v) < 0.0) {
            n = -n;
        }
    }
    n = apply_bevel_normal(n, v_tangent, v_bitangent, material_uv);
    vec3 l = normalize(-u_light_dir);
    float shadow = shadow_factor(v_light_pos, n, l);
    float roughness = clamp(v_material.x, 0.04, 1.0);
    float metallic = clamp(v_material.y, 0.0, 1.0);
    float reflectance = unlit ? 0.0 : clamp(v_material.z, 0.0, 1.0);
    vec3 albedo = max(v_color.rgb, vec3(0.0));
    float out_alpha = clamp(v_color.a, 0.0, 1.0);
    if (u_has_base_map == 1) {
        vec4 base_sample = sample_material_rgba(u_base_map, material_uv, v_world_pos, n);
        albedo = srgb_to_linear(base_sample.rgb) * clamp(albedo, vec3(0.0), vec3(16.0));
        if (u_base_alpha_to_opacity == 1) {
            out_alpha *= clamp(base_sample.a, 0.0, 1.0);
        }
    }
    if (u_has_opacity_map == 1) {
        out_alpha *= clamp(sample_material_rgba(u_opacity_map, material_uv, v_world_pos, n).r, 0.0, 1.0);
    }
    if (out_alpha <= max(u_alpha_cutoff, 0.001)) {
        discard;
    }
    if (unlit) {
        vec3 bloom_rgb = albedo * max(u_unlit_exposure_scale, 0.0);
        vec3 rgb = apply_output_transform_gamma(bloom_rgb, u_unlit_output_gamma);
        rgb = clamp((rgb - vec3(0.5)) * max(u_unlit_contrast, 0.0) + vec3(0.5), 0.0, 1.0);
        frag_color = vec4(rgb, out_alpha);
        bloom_source = vec4(bloom_rgb, out_alpha);
        return;
    }
    if (u_has_roughness_map == 1) {
        roughness = clamp(sample_material_rgba(u_roughness_map, material_uv, v_world_pos, n).r, 0.04, 1.0);
    }
    if (u_has_metallic_map == 1) {
        metallic = clamp(sample_material_rgba(u_metallic_map, material_uv, v_world_pos, n).r, 0.0, 1.0);
    }
    if (u_has_specular_map == 1) {
        reflectance = clamp(sample_material_rgba(u_specular_map, material_uv, v_world_pos, n).r, 0.0, 1.0);
    }
    apply_surface_override(roughness, metallic, reflectance);
    float ao = 1.0;
    if (u_has_occlusion_map == 1) {
        ao = clamp(sample_material_rgba(u_occlusion_map, material_uv, v_world_pos, n).r, 0.0, 1.0);
    }
    float screen_ao = screen_space_ao_factor(n, v, v_world_pos);
    float ambient_ao = ao * (u_screen_ao_ambient == 1 ? screen_ao : 1.0);
    float diffuse_ao = ao * (u_screen_ao_diffuse == 1 ? screen_ao : 1.0);
    float specular_ao = ao * (u_screen_ao_specular == 1 ? screen_ao : 1.0);
    vec3 emissive = albedo * max(u_emissive_factor, vec3(0.0));
    if (u_has_emissive_map == 1) {
        emissive = srgb_to_linear(sample_material_rgba(u_emissive_map, material_uv, v_world_pos, n).rgb) * max(u_emissive_factor, vec3(0.0));
    }
    apply_material_layer(albedo, roughness, metallic, out_alpha, emissive);

    float ndotl = max(dot(n, l), 0.0);
    float ndotv = max(dot(n, v), 0.0);
    vec3 f0 = mix(vec3(0.02 + reflectance * 0.06), albedo, metallic);
    vec3 fresnel = fresnel_schlick(ndotv, f0);

    vec3 irradiance = sample_irradiance(n);
    vec3 reflect_dir = reflect(-v, n);
    vec3 spec_env = sample_prefiltered_env(reflect_dir, roughness);
    vec2 brdf = sample_brdf_lut(ndotv, roughness);
    vec3 kd = (vec3(1.0) - fresnel) * (1.0 - metallic);
    vec3 diffuse = albedo * irradiance * kd * ambient_ao;
    vec3 specular = spec_env * (fresnel * brdf.x + vec3(brdf.y)) * mix(0.64, 1.0, specular_ao);
    float self_shadow = mix(1.0, shadow, clamp(u_self_shadow_strength, 0.0, 1.0));
    diffuse *= self_shadow;
    specular *= mix(1.0, self_shadow, 0.35);

    float direct_power = u_direct_intensity;
    vec3 h = normalize(l + v);
    float ndoth = max(dot(n, h), 0.0);
    float vdoth = max(dot(v, h), 0.0);
    vec3 direct = cook_torrance_direct(albedo, f0, roughness, metallic, ndotl, ndotv, ndoth, vdoth, direct_power) * diffuse_ao * max(u_light_color, vec3(0.0));
    direct *= shadow;

    vec3 fill = albedo * (0.045 + roughness * 0.03) * kd * mix(0.48, 1.0, ambient_ao);
    fill *= mix(1.0, self_shadow, 0.65);
    vec3 rgb = diffuse + specular + direct + fill + emissive;
    float accumulation = hybrid_sample_gain();
    vec3 diffuse_gi = albedo * irradiance * kd * ambient_ao * u_diffuse_gi_strength * accumulation * (1.0 - metallic) * mix(0.55, 1.0, roughness);
    vec3 specular_gi = spec_env * fresnel * u_specular_gi_strength * accumulation * (1.0 - roughness * 0.40) * mix(0.50, 1.0, specular_ao);
    rgb += diffuse_gi + specular_gi;
    rgb = apply_subsurface_lighting(rgb, albedo, n, v, l, ndotl, diffuse_ao, irradiance, direct_power);
    rgb = apply_hair_groom_lighting(rgb, n, v_tangent, v, l, ndotl, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_cloth_sheen_lighting(rgb, albedo, n, v, l, ndotl, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_glint_sparkle_lighting(rgb, material_uv, v_world_pos, v, l, ndotl, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_clearcoat_layer(rgb, n, v, l, roughness, ndotv, ndotl, ndoth, vdoth, specular_ao, direct_power);
    float screen_ao_shadow = clamp(1.0 - min(min(ambient_ao, diffuse_ao), specular_ao), 0.0, 1.0);
    rgb = mix(rgb, rgb * (0.82 + clamp(u_screen_ao_color, vec3(0.0), vec3(1.0)) * 0.18), screen_ao_shadow);
    rgb = apply_transmission_refraction(rgb, albedo, n, v, roughness, fresnel);
    vec3 bloom_rgb = max(
        emissive * 1.75
        + specular * 1.25
        + direct * 0.42
        + specular_gi * 0.70
        + rgb * 0.10,
        vec3(0.0)
    );
    rgb = apply_output_transform(rgb);
    frag_color = vec4(rgb, out_alpha);
    bloom_source = vec4(bloom_rgb, out_alpha);
}
"""


DEPTH_VERT_SHADER = """
#version 330 core
const int MAX_SKIN_BONES = 128;
layout(location = 0) in vec3 a_pos;
layout(location = 7) in vec4 a_bone_indices;
layout(location = 8) in vec4 a_bone_weights;
uniform mat4 u_light_mvp;
uniform int u_skinning_enabled;
uniform int u_skin_bone_count;
uniform mat4 u_skin_bones[MAX_SKIN_BONES];
uniform vec3 u_bounds_center;
uniform float u_bounds_max_size;
uniform int u_stage_transform_enabled;
uniform int u_stage_rotate_y_180;
uniform vec3 u_stage_center;
uniform vec3 u_stage_offset;
mat4 skin_bone(float raw_index) {
    int idx = int(raw_index + 0.5);
    if (idx < 0 || idx >= u_skin_bone_count || idx >= MAX_SKIN_BONES) {
        return mat4(1.0);
    }
    return u_skin_bones[idx];
}
void main() {
    vec3 raw_object_pos = a_pos * u_bounds_max_size + u_bounds_center;
    float weight_sum = a_bone_weights.x + a_bone_weights.y + a_bone_weights.z + a_bone_weights.w;
    if (u_skinning_enabled != 0 && weight_sum > 0.0001 && u_bounds_max_size > 0.000001) {
        mat4 skin =
            skin_bone(a_bone_indices.x) * a_bone_weights.x +
            skin_bone(a_bone_indices.y) * a_bone_weights.y +
            skin_bone(a_bone_indices.z) * a_bone_weights.z +
            skin_bone(a_bone_indices.w) * a_bone_weights.w;
        vec4 skinned_pos = skin * vec4(raw_object_pos, 1.0);
        raw_object_pos = skinned_pos.xyz;
    }
    if (u_stage_transform_enabled != 0) {
        if (u_stage_rotate_y_180 != 0) {
            raw_object_pos.x = u_stage_center.x - (raw_object_pos.x - u_stage_center.x);
            raw_object_pos.z = u_stage_center.z - (raw_object_pos.z - u_stage_center.z);
        }
        raw_object_pos += u_stage_offset;
    }
    vec3 object_pos = (raw_object_pos - u_bounds_center) / u_bounds_max_size;
    gl_Position = u_light_mvp * vec4(object_pos, 1.0);
}
"""


DEPTH_FRAG_SHADER = """
#version 330 core
out vec4 frag_color;
void main() {
    float depth = gl_FragCoord.z;
    frag_color = vec4(depth, depth, depth, 1.0);
}
"""


GROUND_VERT_SHADER = """
#version 330 core
layout(location = 0) in vec3 a_pos;
uniform mat4 u_mvp;
uniform mat4 u_light_mvp;
out vec3 v_world_pos;
out vec4 v_light_pos;
void main() {
    gl_Position = u_mvp * vec4(a_pos, 1.0);
    v_world_pos = a_pos;
    v_light_pos = u_light_mvp * vec4(a_pos, 1.0);
}
"""


GROUND_FRAG_SHADER = """
#version 330 core
in vec3 v_world_pos;
in vec4 v_light_pos;
uniform sampler2D u_shadow_map;
uniform sampler2D u_hdri;
uniform int u_has_shadow_map;
uniform int u_has_hdri;
uniform float u_shadow_strength;
uniform float u_shadow_pcf_radius;
uniform float u_shadow_pcss_blocker_radius;
uniform float u_shadow_bias;
uniform int u_shadow_filter_mode;
uniform float u_ibl_rotation;
uniform float u_ibl_exposure;
uniform float u_ground_reflection;
uniform float u_shadow_catcher_opacity;
uniform float u_shadow_catcher_softness;
uniform float u_shadow_catcher_matte_alpha;
uniform float u_reflection_catcher_opacity;
uniform float u_reflection_catcher_roughness;
uniform float u_reflection_catcher_softness;
uniform float u_reflection_catcher_matte_alpha;
uniform float u_contact_reflection_strength;
uniform float u_contact_reflection_falloff;
uniform int u_tone_mapping_mode;
uniform float u_tone_exposure;
uniform vec3 u_tone_white_balance;
uniform float u_tone_gamma;
layout(location = 0) out vec4 frag_color;
layout(location = 1) out vec4 bloom_source;

const float PI = 3.14159265358979323846;

vec2 dir_to_equirect(vec3 dir) {
    vec3 d = normalize(dir);
    float u = atan(d.z, d.x) / (2.0 * PI) + 0.5 + u_ibl_rotation;
    float v = 0.5 - asin(clamp(d.y, -1.0, 1.0)) / PI;
    return vec2(fract(u), clamp(v, 0.0, 1.0));
}

vec3 tonemap_aces(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 tonemap_reinhard(vec3 x) {
    x = max(x, vec3(0.0));
    return clamp(x / (vec3(1.0) + x), 0.0, 1.0);
}

vec3 tonemap_agx(vec3 x) {
    x = log2(max(x, vec3(0.000001)));
    x = clamp((x + vec3(12.47393)) / 16.5, 0.0, 1.0);
    return clamp(x * x * (vec3(3.0) - 2.0 * x), 0.0, 1.0);
}

vec3 apply_output_transform(vec3 rgb) {
    vec3 x = max(rgb, vec3(0.0)) * exp2(u_tone_exposure) * max(u_tone_white_balance, vec3(0.0001));
    vec3 mapped = u_tone_mapping_mode == 1
        ? tonemap_agx(x)
        : (u_tone_mapping_mode == 2 ? tonemap_reinhard(x) : tonemap_aces(x));
    return pow(clamp(mapped, 0.0, 1.0), vec3(1.0 / max(u_tone_gamma, 0.1)));
}

float ground_shadow_pcf(vec2 uv, float current, float bias, float radius_texels) {
    vec2 texel = max(radius_texels, 0.0) / vec2(textureSize(u_shadow_map, 0));
    float lit = 0.0;
    for (int x = -2; x <= 2; x++) {
        for (int y = -2; y <= 2; y++) {
            float closest = texture(u_shadow_map, uv + vec2(x, y) * texel).r;
            lit += current - bias <= closest ? 1.0 : 0.0;
        }
    }
    return lit / 25.0;
}

float ground_shadow_pcss(vec2 uv, float current, float bias) {
    vec2 search_texel = max(max(u_shadow_pcf_radius, u_shadow_pcss_blocker_radius), 0.0) / vec2(textureSize(u_shadow_map, 0));
    float blocker_sum = 0.0;
    float blocker_count = 0.0;
    for (int x = -2; x <= 2; x++) {
        for (int y = -2; y <= 2; y++) {
            float closest = texture(u_shadow_map, uv + vec2(x, y) * search_texel).r;
            if (closest < current - bias) {
                blocker_sum += closest;
                blocker_count += 1.0;
            }
        }
    }
    if (blocker_count <= 0.5) {
        return 1.0;
    }
    float avg_blocker = blocker_sum / blocker_count;
    float penumbra = clamp(
        (current - avg_blocker) * max(u_shadow_pcss_blocker_radius, 0.0) * 32.0,
        u_shadow_pcf_radius,
        u_shadow_pcf_radius + max(u_shadow_pcss_blocker_radius, 0.0)
    );
    return ground_shadow_pcf(uv, current, bias, penumbra);
}

float shadow_factor(vec4 light_pos) {
    if (u_has_shadow_map == 0) {
        float contact_width = mix(24.0, 7.0, clamp(u_shadow_catcher_softness, 0.0, 1.0));
        float contact = exp(-dot(v_world_pos.xz, v_world_pos.xz) * contact_width);
        return 1.0 - contact * u_shadow_strength * u_shadow_catcher_opacity * 0.92;
    }
    vec3 projected = light_pos.xyz / max(light_pos.w, 1e-6);
    projected = projected * 0.5 + 0.5;
    if (projected.x < 0.0 || projected.x > 1.0 || projected.y < 0.0 || projected.y > 1.0 || projected.z > 1.0) {
        return 1.0;
    }
    float bias = max(u_shadow_bias, 0.00005);
    float lit = u_shadow_filter_mode == 1
        ? ground_shadow_pcss(projected.xy, projected.z, bias)
        : ground_shadow_pcf(projected.xy, projected.z, bias, u_shadow_pcf_radius);
    return mix(1.0 - u_shadow_strength * u_shadow_catcher_opacity, 1.0, lit);
}

void main() {
    float rough = clamp(u_reflection_catcher_roughness, 0.02, 1.0);
    float soft = clamp(u_reflection_catcher_softness, 0.0, 1.0);
    float reflection_lod = mix(2.0, 7.0, rough);
    vec3 env = u_has_hdri == 1 ? textureLod(u_hdri, dir_to_equirect(vec3(0.0, 1.0, 0.0)), reflection_lod).rgb * u_ibl_exposure : vec3(0.28);
    float contact_width = mix(18.0, 5.0, clamp(u_contact_reflection_falloff, 0.05, 1.0));
    float contact = exp(-dot(v_world_pos.xz, v_world_pos.xz) * contact_width);
    float reflection_amount = clamp(
        u_reflection_catcher_opacity * (u_ground_reflection + contact * u_contact_reflection_strength) * (1.0 - rough * 0.34),
        0.0,
        1.0
    );
    float visibility = shadow_factor(v_light_pos);
    float shadow_alpha = (1.0 - visibility) * (0.78 + soft * 0.22);
    vec3 reflection_rgb = env * reflection_amount * 0.38;
    vec3 rgb = reflection_rgb;
    rgb = apply_output_transform(rgb);
    float matte_alpha = max(u_shadow_catcher_matte_alpha, u_reflection_catcher_matte_alpha);
    float alpha = clamp(matte_alpha + shadow_alpha + reflection_amount * (0.08 + soft * 0.10), 0.0, 1.0);
    frag_color = vec4(rgb, alpha);
    bloom_source = vec4(0.0, 0.0, 0.0, 0.0);
}
"""


ENV_VERT_SHADER = """
#version 330 core
const vec2 POSITIONS[3] = vec2[3](
    vec2(-1.0, -1.0),
    vec2(3.0, -1.0),
    vec2(-1.0, 3.0)
);
out vec2 v_uv;
void main() {
    vec2 pos = POSITIONS[gl_VertexID];
    gl_Position = vec4(pos, 0.0, 1.0);
    v_uv = pos * 0.5 + 0.5;
}
"""


ENV_FRAG_SHADER = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_hdri;
uniform int u_has_hdri;
uniform float u_ibl_rotation;
uniform float u_ibl_exposure;
uniform int u_tone_mapping_mode;
uniform float u_tone_exposure;
uniform vec3 u_tone_white_balance;
uniform float u_tone_gamma;
layout(location = 0) out vec4 frag_color;
layout(location = 1) out vec4 bloom_source;

vec3 tonemap_aces(vec3 x) {
    const float a = 2.51;
    const float b = 0.03;
    const float c = 2.43;
    const float d = 0.59;
    const float e = 0.14;
    return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

vec3 tonemap_reinhard(vec3 x) {
    x = max(x, vec3(0.0));
    return clamp(x / (vec3(1.0) + x), 0.0, 1.0);
}

vec3 tonemap_agx(vec3 x) {
    x = log2(max(x, vec3(0.000001)));
    x = clamp((x + vec3(12.47393)) / 16.5, 0.0, 1.0);
    return clamp(x * x * (vec3(3.0) - 2.0 * x), 0.0, 1.0);
}

vec3 apply_output_transform(vec3 rgb) {
    vec3 x = max(rgb, vec3(0.0)) * exp2(u_tone_exposure) * max(u_tone_white_balance, vec3(0.0001));
    vec3 mapped = u_tone_mapping_mode == 1
        ? tonemap_agx(x)
        : (u_tone_mapping_mode == 2 ? tonemap_reinhard(x) : tonemap_aces(x));
    return pow(clamp(mapped, 0.0, 1.0), vec3(1.0 / max(u_tone_gamma, 0.1)));
}

void main() {
    vec2 uv = vec2(fract(v_uv.x + u_ibl_rotation), 1.0 - v_uv.y);
    vec3 rgb;
    if (u_has_hdri == 1) {
        rgb = textureLod(u_hdri, uv, 0.0).rgb * u_ibl_exposure * 0.72;
        rgb = apply_output_transform(rgb);
    } else {
        rgb = mix(vec3(0.035, 0.043, 0.062), vec3(0.18, 0.20, 0.24), smoothstep(0.0, 1.0, v_uv.y));
        rgb = apply_output_transform(rgb);
    }
    frag_color = vec4(rgb, 1.0);
    bloom_source = vec4(0.0, 0.0, 0.0, 0.0);
}
"""


POST_BLOOM_VERT_SHADER = """
#version 330 core
const vec2 POSITIONS[3] = vec2[3](
    vec2(-1.0, -1.0),
    vec2(3.0, -1.0),
    vec2(-1.0, 3.0)
);
out vec2 v_uv;
void main() {
    vec2 pos = POSITIONS[gl_VertexID];
    gl_Position = vec4(pos, 0.0, 1.0);
    v_uv = pos * 0.5 + 0.5;
}
"""


BLOOM_BLUR_FRAG_SHADER = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_source;
uniform vec2 u_texel_size;
uniform vec2 u_direction;
uniform float u_bloom_radius;
uniform float u_bloom_threshold;
uniform float u_bloom_boost;
uniform float u_anamorphic_strength;
uniform float u_anamorphic_threshold;
uniform float u_anamorphic_ratio;
uniform int u_extract_bright;
out vec4 frag_color;

vec3 bright_pass(vec4 sample_rgba) {
    vec3 rgb = max(sample_rgba.rgb, vec3(0.0));
    if (u_extract_bright == 0) {
        return rgb;
    }
    float source_mask = clamp(sample_rgba.a, 0.0, 1.0);
    float lum = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
    float threshold = clamp(u_bloom_threshold, 0.0, 1.0);
    float knee = mix(0.10, 0.32, clamp(u_bloom_radius / 24.0, 0.0, 1.0));
    float excess = max(lum - threshold, 0.0);
    float contribution = clamp(excess / max(1.0 - threshold, 0.001), 0.0, 8.0);
    float soft_mask = smoothstep(0.0, knee, excess);
    float boost = 1.0 + clamp(u_bloom_boost, 0.0, 8.0) * (0.85 + contribution * 0.35);
    return rgb * contribution * soft_mask * source_mask * boost;
}

vec3 sample_blur(vec2 offset_px, float weight) {
    return bright_pass(texture(u_source, clamp(v_uv + u_texel_size * offset_px, vec2(0.0), vec2(1.0)))) * weight;
}

vec3 peak_pass(vec4 sample_rgba) {
    vec3 rgb = max(sample_rgba.rgb, vec3(0.0));
    float source_mask = clamp(sample_rgba.a, 0.0, 1.0);
    float lum = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
    float threshold = max(clamp(u_anamorphic_threshold, 0.0, 2.0), clamp(u_bloom_threshold, 0.0, 1.0) + 0.14);
    float excess = max(lum - threshold, 0.0);
    float gate = smoothstep(0.0, 0.42, excess);
    float power = clamp(excess / max(threshold, 0.001), 0.0, 12.0);
    return rgb * gate * power * source_mask;
}

vec3 sample_peak_streak(float offset_px, float weight) {
    vec2 offset = vec2(u_texel_size.x * offset_px, 0.0);
    vec3 a = peak_pass(texture(u_source, clamp(v_uv + offset, vec2(0.0), vec2(1.0))));
    vec3 b = peak_pass(texture(u_source, clamp(v_uv - offset, vec2(0.0), vec2(1.0))));
    return (a + b) * weight;
}

void main() {
    vec2 dir = normalize(u_direction);
    float radius = max(u_bloom_radius, 1.0);
    float step_px = max(0.65, radius * 0.185);
    vec3 bloom = bright_pass(texture(u_source, v_uv)) * 0.19648255;
    bloom += sample_blur( dir * step_px * 1.0, 0.17603266);
    bloom += sample_blur(-dir * step_px * 1.0, 0.17603266);
    bloom += sample_blur( dir * step_px * 2.0, 0.12098138);
    bloom += sample_blur(-dir * step_px * 2.0, 0.12098138);
    bloom += sample_blur( dir * step_px * 3.0, 0.06475994);
    bloom += sample_blur(-dir * step_px * 3.0, 0.06475994);
    bloom += sample_blur( dir * step_px * 4.0, 0.02699548);
    bloom += sample_blur(-dir * step_px * 4.0, 0.02699548);
    bloom += sample_blur( dir * step_px * 5.0, 0.00876430);
    bloom += sample_blur(-dir * step_px * 5.0, 0.00876430);
    if (u_extract_bright == 1 && abs(u_direction.x) > abs(u_direction.y) && u_anamorphic_strength > 0.0) {
        float streak_radius = radius * clamp(u_anamorphic_ratio, 1.0, 12.0);
        vec3 streak = peak_pass(texture(u_source, v_uv)) * 0.070;
        streak += sample_peak_streak(streak_radius * 0.16, 0.070);
        streak += sample_peak_streak(streak_radius * 0.36, 0.060);
        streak += sample_peak_streak(streak_radius * 0.68, 0.046);
        streak += sample_peak_streak(streak_radius * 1.12, 0.032);
        streak += sample_peak_streak(streak_radius * 1.76, 0.020);
        streak += sample_peak_streak(streak_radius * 2.72, 0.012);
        streak += sample_peak_streak(streak_radius * 4.10, 0.006);
        bloom += streak * clamp(u_anamorphic_strength, 0.0, 6.0);
    }
    frag_color = vec4(max(bloom, vec3(0.0)), 1.0);
}
"""


POST_BLOOM_FRAG_SHADER = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_scene_color;
uniform sampler2D u_bloom_source;
uniform sampler2D u_peak_source;
uniform vec2 u_texel_size;
uniform vec2 u_peak_texel_size;
uniform float u_bloom_strength;
uniform float u_bloom_radius;
uniform float u_bloom_threshold;
uniform float u_anamorphic_strength;
uniform float u_anamorphic_threshold;
uniform float u_anamorphic_ratio;
uniform int u_force_opaque;
out vec4 frag_color;

vec3 peak_sprite_source(vec2 uv) {
    vec4 sample_rgba = texture(u_peak_source, clamp(uv, vec2(0.0), vec2(1.0)));
    vec3 rgb = max(sample_rgba.rgb, vec3(0.0));
    float source_mask = clamp(sample_rgba.a, 0.0, 1.0);
    float lum = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
    vec2 peak_px = u_peak_texel_size * max(2.0, u_bloom_radius * 0.11);
    float n0 = dot(max(texture(u_peak_source, clamp(uv + vec2( peak_px.x, 0.0), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n1 = dot(max(texture(u_peak_source, clamp(uv + vec2(-peak_px.x, 0.0), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n2 = dot(max(texture(u_peak_source, clamp(uv + vec2(0.0,  peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n3 = dot(max(texture(u_peak_source, clamp(uv + vec2(0.0, -peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n4 = dot(max(texture(u_peak_source, clamp(uv + vec2( peak_px.x,  peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n5 = dot(max(texture(u_peak_source, clamp(uv + vec2(-peak_px.x,  peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n6 = dot(max(texture(u_peak_source, clamp(uv + vec2( peak_px.x, -peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float n7 = dot(max(texture(u_peak_source, clamp(uv + vec2(-peak_px.x, -peak_px.y), vec2(0.0), vec2(1.0))).rgb, vec3(0.0)), vec3(0.2126, 0.7152, 0.0722));
    float neighbor_max = max(max(max(n0, n1), max(n2, n3)), max(max(n4, n5), max(n6, n7)));
    float local_peak = smoothstep(0.015, 0.11, lum - neighbor_max);
    float threshold = max(clamp(u_anamorphic_threshold, 0.0, 2.0), clamp(u_bloom_threshold, 0.0, 1.0) + 0.28);
    float excess = max(lum - threshold, 0.0);
    float gate = smoothstep(0.0, 0.26, excess);
    float power = pow(clamp(excess / max(threshold, 0.001), 0.0, 14.0), 1.35);
    return rgb * gate * power * source_mask * local_peak;
}

vec3 peak_sprite_sample(float x_px, float y_px, float weight) {
    vec2 offset = vec2(x_px * u_peak_texel_size.x, y_px * u_peak_texel_size.y);
    return peak_sprite_source(v_uv + offset) * weight;
}

vec3 sample_anamorphic_lens_sprite() {
    float strength = clamp(u_anamorphic_strength, 0.0, 6.0);
    if (strength <= 0.0) {
        return vec3(0.0);
    }
    float radius = max(u_bloom_radius, 1.0);
    float span = radius * clamp(u_anamorphic_ratio, 1.0, 12.0);
    float y = max(1.0, radius * 0.085);
    vec3 tint_a = vec3(1.00, 0.92, 0.78);
    vec3 tint_b = vec3(0.64, 0.78, 1.00);
    vec3 glare = peak_sprite_sample(0.0, 0.0, 0.12);
    for (int i = 1; i <= 26; ++i) {
        float t = float(i) / 26.0;
        float curve = t * t;
        float dx = span * mix(0.035, 2.35, curve);
        float w = exp(-t * 4.15) * 0.040;
        vec3 near_line =
            peak_sprite_sample( dx, 0.0, w) +
            peak_sprite_sample(-dx, 0.0, w);
        vec3 soft_edge =
            peak_sprite_sample( dx * 1.018, y, w * 0.34) +
            peak_sprite_sample(-dx * 1.018, y, w * 0.34) +
            peak_sprite_sample( dx * 1.018, -y, w * 0.34) +
            peak_sprite_sample(-dx * 1.018, -y, w * 0.34) +
            peak_sprite_sample( dx * 0.992, y * 2.0, w * 0.09) +
            peak_sprite_sample(-dx * 0.992, -y * 2.0, w * 0.09);
        float tint_mix = t;
        glare += (near_line + soft_edge) * mix(tint_a, tint_b, tint_mix) * (1.0 + tint_mix * 0.22);
    }
    return glare * pow(strength, 1.18) * 0.92;
}

void main() {
    vec4 base = texture(u_scene_color, v_uv);
    float strength = pow(clamp(u_bloom_strength, 0.0, 4.0), 1.35) * 1.75;
    vec3 bloom = max(texture(u_bloom_source, v_uv).rgb, vec3(0.0));
    vec3 lens_sprite = sample_anamorphic_lens_sprite();
    vec3 rgb = clamp(base.rgb + bloom * strength + lens_sprite, 0.0, 1.0);
    float lens_alpha = max(max(lens_sprite.r, lens_sprite.g), lens_sprite.b);
    float bloom_alpha = clamp(max(max(bloom.r, bloom.g), bloom.b) * strength + lens_alpha, 0.0, 1.0);
    float alpha = u_force_opaque == 1 ? 1.0 : max(base.a, bloom_alpha * 0.45);
    frag_color = vec4(rgb, alpha);
}
"""


@dataclass
class GpuState:
    pitch: float = -10.0
    yaw: float = 72.0
    roll: float = 0.0
    zoom: float = 1.75
    camera_z: float = 3.25
    fov_deg: float = FRAME_FIT_FOV_DEG
    pan_x: float = 0.0
    pan_y: float = 0.0
    pan_z: float = 0.0
    ibl_exposure: float = 1.1
    ibl_rotation: float = 0.0
    tone_mapping: str = DEFAULT_TONE_MAPPING
    tone_exposure: float = DEFAULT_TONE_EXPOSURE
    tone_white_balance: float = DEFAULT_TONE_WHITE_BALANCE
    tone_gamma: float = DEFAULT_TONE_GAMMA
    depth_edge_glow_enabled: bool = False
    depth_edge_glow_strength: float = DEFAULT_DEPTH_EDGE_GLOW_STRENGTH
    depth_edge_glow_radius_px: float = DEFAULT_DEPTH_EDGE_GLOW_RADIUS_PX
    hybrid_sample_count: int = DEFAULT_HYBRID_SAMPLE_COUNT
    diffuse_gi_strength: float = DEFAULT_DIFFUSE_GI_STRENGTH
    specular_gi_strength: float = DEFAULT_SPECULAR_GI_STRENGTH
    denoise_strength: float = DEFAULT_DENOISE_STRENGTH
    ray_gi_detail_mode: str = DEFAULT_RAY_GI_DETAIL_MODE
    ray_gi_max_bounces: int = DEFAULT_RAY_GI_MAX_BOUNCES
    ray_gi_diffuse_bounces: int = DEFAULT_RAY_GI_DIFFUSE_BOUNCES
    ray_gi_specular_bounces: int = DEFAULT_RAY_GI_SPECULAR_BOUNCES
    ray_gi_refraction_bounces: int = DEFAULT_RAY_GI_REFRACTION_BOUNCES
    ray_gi_direct_radiance_clamp: float = DEFAULT_DIRECT_RADIANCE_CLAMP
    ray_gi_indirect_radiance_clamp: float = DEFAULT_INDIRECT_RADIANCE_CLAMP
    ray_gi_light_sampling_mode: str = DEFAULT_LIGHT_SAMPLING_MODE
    ray_gi_light_sample_count: int = DEFAULT_LIGHT_SAMPLE_COUNT
    ray_gi_environment_sample_count: int = DEFAULT_ENVIRONMENT_SAMPLE_COUNT
    ray_gi_mis_enabled: bool = False
    ray_gi_importance_sampling: bool = False
    ray_gi_denoise_channels: tuple[str, ...] = ("beauty",)
    ray_gi_denoise_beauty: bool = True
    ray_gi_denoise_diffuse: bool = False
    ray_gi_denoise_specular: bool = False
    ray_gi_denoise_transmission: bool = False
    ray_gi_denoise_albedo_guided: bool = False
    ray_gi_denoise_normal_guided: bool = False
    ambient_occlusion_mode: str = DEFAULT_AMBIENT_OCCLUSION_MODE
    ao_strength: float = DEFAULT_AO_STRENGTH
    ao_radius: float = DEFAULT_AO_RADIUS
    ao_distance: float = DEFAULT_AO_DISTANCE
    ao_color: tuple[float, float, float] = (
        DEFAULT_AO_COLOR[0],
        DEFAULT_AO_COLOR[1],
        DEFAULT_AO_COLOR[2],
    )
    ao_ambient: bool = DEFAULT_AO_AMBIENT
    ao_diffuse: bool = DEFAULT_AO_DIFFUSE
    ao_specular: bool = DEFAULT_AO_SPECULAR
    transmission_mode: str = DEFAULT_TRANSMISSION_MODE
    transmission: float = DEFAULT_TRANSMISSION
    refraction_strength: float = DEFAULT_REFRACTION_STRENGTH
    refraction_depth_px: float = DEFAULT_REFRACTION_DEPTH_PX
    ior: float = DEFAULT_IOR
    thickness: float = DEFAULT_THICKNESS
    absorption_color: tuple[float, float, float] = (
        DEFAULT_ABSORPTION_COLOR[0],
        DEFAULT_ABSORPTION_COLOR[1],
        DEFAULT_ABSORPTION_COLOR[2],
    )
    absorption_distance: float = DEFAULT_ABSORPTION_DISTANCE
    roughness_blur_strength: float = DEFAULT_ROUGHNESS_BLUR_STRENGTH
    clearcoat_mode: str = DEFAULT_CLEARCOAT_MODE
    clearcoat_strength: float = DEFAULT_CLEARCOAT_STRENGTH
    clearcoat_roughness: float = DEFAULT_CLEARCOAT_ROUGHNESS
    clearcoat_ior: float = DEFAULT_CLEARCOAT_IOR
    clearcoat_tint: tuple[float, float, float] = (
        DEFAULT_CLEARCOAT_TINT[0],
        DEFAULT_CLEARCOAT_TINT[1],
        DEFAULT_CLEARCOAT_TINT[2],
    )
    parallax_mode: str = DEFAULT_PARALLAX_MODE
    parallax_strength: float = DEFAULT_PARALLAX_STRENGTH
    parallax_depth: float = DEFAULT_PARALLAX_DEPTH
    parallax_center: float = DEFAULT_PARALLAX_CENTER
    parallax_steps: int = DEFAULT_PARALLAX_STEPS
    displacement_mode: str = DEFAULT_DISPLACEMENT_MODE
    displacement_height_strength: float = DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH
    displacement_height_scale: float = DEFAULT_DISPLACEMENT_HEIGHT_SCALE
    displacement_height_center: float = DEFAULT_DISPLACEMENT_HEIGHT_CENTER
    vector_displacement_strength: float = DEFAULT_VECTOR_DISPLACEMENT_STRENGTH
    vector_displacement_space: str = DEFAULT_VECTOR_DISPLACEMENT_SPACE
    displacement_subdivision_mode: str = DEFAULT_DISPLACEMENT_SUBDIVISION_MODE
    displacement_max_offset: float = DEFAULT_DISPLACEMENT_MAX_OFFSET
    displacement_parallax_fallback: bool = DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK
    bevel_mode: str = DEFAULT_BEVEL_MODE
    bevel_strength: float = DEFAULT_BEVEL_STRENGTH
    bevel_radius: float = DEFAULT_BEVEL_RADIUS
    bevel_edge_width: float = DEFAULT_BEVEL_EDGE_WIDTH
    bevel_samples: int = DEFAULT_BEVEL_SAMPLES
    material_layer_mode: str = DEFAULT_MATERIAL_LAYER_MODE
    material_layer_blend: float = DEFAULT_MATERIAL_LAYER_BLEND
    material_layer_color: tuple[float, float, float] = (
        DEFAULT_MATERIAL_LAYER_COLOR[0],
        DEFAULT_MATERIAL_LAYER_COLOR[1],
        DEFAULT_MATERIAL_LAYER_COLOR[2],
    )
    material_layer_roughness: float = DEFAULT_MATERIAL_LAYER_ROUGHNESS
    material_layer_metallic: float = DEFAULT_MATERIAL_LAYER_METALLIC
    material_layer_alpha: float = DEFAULT_MATERIAL_LAYER_ALPHA
    material_layer_emissive_strength: float = DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH
    material_layer_mask_strength: float = DEFAULT_MATERIAL_LAYER_MASK_STRENGTH
    surface_override_strength: float = DEFAULT_SURFACE_OVERRIDE_STRENGTH
    surface_roughness: float = DEFAULT_SURFACE_ROUGHNESS
    surface_metallic: float = DEFAULT_SURFACE_METALLIC
    surface_reflectance: float = DEFAULT_SURFACE_REFLECTANCE
    subsurface_mode: str = DEFAULT_SUBSURFACE_MODE
    subsurface_strength: float = DEFAULT_SUBSURFACE_STRENGTH
    subsurface_color: tuple[float, float, float] = (
        DEFAULT_SUBSURFACE_COLOR[0],
        DEFAULT_SUBSURFACE_COLOR[1],
        DEFAULT_SUBSURFACE_COLOR[2],
    )
    subsurface_radius: float = DEFAULT_SUBSURFACE_RADIUS
    subsurface_power: float = DEFAULT_SUBSURFACE_POWER
    subsurface_wrap: float = DEFAULT_SUBSURFACE_WRAP
    subsurface_thickness: float = DEFAULT_SUBSURFACE_THICKNESS
    hair_groom_mode: str = DEFAULT_HAIR_GROOM_MODE
    hair_groom_strength: float = DEFAULT_HAIR_GROOM_STRENGTH
    hair_groom_tint: tuple[float, float, float] = (
        DEFAULT_HAIR_GROOM_TINT[0],
        DEFAULT_HAIR_GROOM_TINT[1],
        DEFAULT_HAIR_GROOM_TINT[2],
    )
    hair_primary_shift: float = DEFAULT_HAIR_PRIMARY_SHIFT
    hair_secondary_shift: float = DEFAULT_HAIR_SECONDARY_SHIFT
    hair_primary_roughness: float = DEFAULT_HAIR_PRIMARY_ROUGHNESS
    hair_secondary_roughness: float = DEFAULT_HAIR_SECONDARY_ROUGHNESS
    hair_secondary_strength: float = DEFAULT_HAIR_SECONDARY_STRENGTH
    hair_anisotropy: float = DEFAULT_HAIR_ANISOTROPY
    hair_rim_strength: float = DEFAULT_HAIR_RIM_STRENGTH
    cloth_sheen_mode: str = DEFAULT_CLOTH_SHEEN_MODE
    cloth_sheen_strength: float = DEFAULT_CLOTH_SHEEN_STRENGTH
    cloth_sheen_color: tuple[float, float, float] = (
        DEFAULT_CLOTH_SHEEN_COLOR[0],
        DEFAULT_CLOTH_SHEEN_COLOR[1],
        DEFAULT_CLOTH_SHEEN_COLOR[2],
    )
    cloth_sheen_roughness: float = DEFAULT_CLOTH_SHEEN_ROUGHNESS
    cloth_sheen_edge_tint: tuple[float, float, float] = (
        DEFAULT_CLOTH_SHEEN_EDGE_TINT[0],
        DEFAULT_CLOTH_SHEEN_EDGE_TINT[1],
        DEFAULT_CLOTH_SHEEN_EDGE_TINT[2],
    )
    cloth_sheen_fiber_strength: float = DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH
    cloth_sheen_wrap: float = DEFAULT_CLOTH_SHEEN_WRAP
    cloth_sheen_retroreflection: float = DEFAULT_CLOTH_SHEEN_RETROREFLECTION
    glint_mode: str = DEFAULT_GLINT_MODE
    glint_strength: float = DEFAULT_GLINT_STRENGTH
    glint_color: tuple[float, float, float] = (
        DEFAULT_GLINT_COLOR[0],
        DEFAULT_GLINT_COLOR[1],
        DEFAULT_GLINT_COLOR[2],
    )
    glint_density: float = DEFAULT_GLINT_DENSITY
    glint_scale: float = DEFAULT_GLINT_SCALE
    glint_threshold: float = DEFAULT_GLINT_THRESHOLD
    glint_sharpness: float = DEFAULT_GLINT_SHARPNESS
    glint_roughness_jitter: float = DEFAULT_GLINT_ROUGHNESS_JITTER
    caustics_mode: str = DEFAULT_CAUSTICS_MODE
    caustics_strength: float = DEFAULT_CAUSTICS_STRENGTH
    caustics_quality: str = DEFAULT_CAUSTICS_QUALITY
    caustics_sample_count: int = DEFAULT_CAUSTICS_SAMPLE_COUNT
    caustics_scale: float = DEFAULT_CAUSTICS_SCALE
    caustics_focus: float = DEFAULT_CAUSTICS_FOCUS
    caustics_radius: float = DEFAULT_CAUSTICS_RADIUS
    caustics_threshold: float = DEFAULT_CAUSTICS_THRESHOLD
    caustics_tint: tuple[float, float, float] = (
        DEFAULT_CAUSTICS_TINT[0],
        DEFAULT_CAUSTICS_TINT[1],
        DEFAULT_CAUSTICS_TINT[2],
    )
    caustics_seed: int = DEFAULT_CAUSTICS_SEED
    anisotropic_mode: str = DEFAULT_ANISOTROPIC_MODE
    anisotropic_strength: float = DEFAULT_ANISOTROPIC_STRENGTH
    anisotropy: float = DEFAULT_ANISOTROPY
    anisotropic_rotation: float = DEFAULT_ANISOTROPIC_ROTATION
    anisotropic_tangent_weight: float = DEFAULT_ANISOTROPIC_TANGENT_WEIGHT
    clearcoat_anisotropy: float = DEFAULT_CLEARCOAT_ANISOTROPY
    thin_film_strength: float = DEFAULT_THIN_FILM_STRENGTH
    thin_film_thickness_nm: float = DEFAULT_THIN_FILM_THICKNESS_NM
    thin_film_ior: float = DEFAULT_THIN_FILM_IOR
    thin_film_tint: tuple[float, float, float] = (
        DEFAULT_THIN_FILM_TINT[0],
        DEFAULT_THIN_FILM_TINT[1],
        DEFAULT_THIN_FILM_TINT[2],
    )
    newton_rings_strength: float = DEFAULT_NEWTON_RINGS_STRENGTH
    newton_rings_scale: float = DEFAULT_NEWTON_RINGS_SCALE
    anisotropic_seed: int = DEFAULT_ANISOTROPIC_SEED
    microsurface_mode: str = DEFAULT_MICROSURFACE_MODE
    detail_normal_strength: float = DEFAULT_DETAIL_NORMAL_STRENGTH
    detail_normal_scale: float = DEFAULT_DETAIL_NORMAL_SCALE
    detail_normal_blend: str = DEFAULT_DETAIL_NORMAL_BLEND
    detail_normal_seed: int = DEFAULT_DETAIL_NORMAL_SEED
    micro_roughness_strength: float = DEFAULT_MICRO_ROUGHNESS_STRENGTH
    micro_roughness_scale: float = DEFAULT_MICRO_ROUGHNESS_SCALE
    micro_roughness_contrast: float = DEFAULT_MICRO_ROUGHNESS_CONTRAST
    gloss_variation_strength: float = DEFAULT_GLOSS_VARIATION_STRENGTH
    gloss_bias: float = DEFAULT_GLOSS_BIAS
    specular_micro_occlusion: float = DEFAULT_SPECULAR_MICRO_OCCLUSION
    depth_of_field_mode: str = DEFAULT_DEPTH_OF_FIELD_MODE
    depth_of_field_strength: float = DEFAULT_DEPTH_OF_FIELD_STRENGTH
    dof_focus_depth: float = DEFAULT_DOF_FOCUS_DEPTH
    dof_focus_range: float = DEFAULT_DOF_FOCUS_RANGE
    dof_max_blur_px: float = DEFAULT_DOF_MAX_BLUR_PX
    dof_near_blur: float = DEFAULT_DOF_NEAR_BLUR
    dof_far_blur: float = DEFAULT_DOF_FAR_BLUR
    dof_bokeh_shape: str = DEFAULT_DOF_BOKEH_SHAPE
    post_effects_mode: str = DEFAULT_POST_EFFECTS_MODE
    bloom_strength: float = DEFAULT_BLOOM_STRENGTH
    bloom_radius: float = DEFAULT_BLOOM_RADIUS
    bloom_threshold: float = DEFAULT_BLOOM_THRESHOLD
    bloom_boost: float = DEFAULT_BLOOM_BOOST
    bloom_anamorphic_strength: float = DEFAULT_BLOOM_ANAMORPHIC_STRENGTH
    bloom_anamorphic_threshold: float = DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD
    bloom_anamorphic_ratio: float = DEFAULT_BLOOM_ANAMORPHIC_RATIO
    vignette_strength: float = DEFAULT_VIGNETTE_STRENGTH
    vignette_radius: float = DEFAULT_VIGNETTE_RADIUS
    vignette_feather: float = DEFAULT_VIGNETTE_FEATHER
    grain_strength: float = DEFAULT_GRAIN_STRENGTH
    grain_scale: float = DEFAULT_GRAIN_SCALE
    grain_seed: int = DEFAULT_GRAIN_SEED
    sharpen_strength: float = DEFAULT_SHARPEN_STRENGTH
    sharpen_radius: float = DEFAULT_SHARPEN_RADIUS
    lens_effects_mode: str = DEFAULT_LENS_EFFECTS_MODE
    lens_distortion_strength: float = DEFAULT_LENS_DISTORTION_STRENGTH
    lens_distortion_k2: float = DEFAULT_LENS_DISTORTION_K2
    chromatic_aberration_strength: float = DEFAULT_CHROMATIC_ABERRATION_STRENGTH
    chromatic_aberration_px: float = DEFAULT_CHROMATIC_ABERRATION_PX
    lens_center: tuple[float, float] = (DEFAULT_LENS_CENTER[0], DEFAULT_LENS_CENTER[1])
    lens_edge_falloff: float = DEFAULT_LENS_EDGE_FALLOFF
    lens_flare_mode: str = DEFAULT_LENS_FLARE_MODE
    lens_flare_strength: float = DEFAULT_LENS_FLARE_STRENGTH
    lens_flare_threshold: float = DEFAULT_LENS_FLARE_THRESHOLD
    lens_flare_radius: float = DEFAULT_LENS_FLARE_RADIUS
    lens_flare_ghost_count: int = DEFAULT_LENS_FLARE_GHOST_COUNT
    lens_flare_ghost_spacing: float = DEFAULT_LENS_FLARE_GHOST_SPACING
    lens_flare_tint: tuple[float, float, float] = (
        DEFAULT_LENS_FLARE_TINT[0],
        DEFAULT_LENS_FLARE_TINT[1],
        DEFAULT_LENS_FLARE_TINT[2],
    )
    aperture_flare_strength: float = DEFAULT_APERTURE_FLARE_STRENGTH
    aperture_flare_blades: int = DEFAULT_APERTURE_FLARE_BLADES
    aperture_flare_rotation_deg: float = DEFAULT_APERTURE_FLARE_ROTATION_DEG
    aperture_flare_radius: float = DEFAULT_APERTURE_FLARE_RADIUS
    lens_dirt_strength: float = DEFAULT_LENS_DIRT_STRENGTH
    lens_dirt_density: float = DEFAULT_LENS_DIRT_DENSITY
    lens_dirt_scale: float = DEFAULT_LENS_DIRT_SCALE
    lens_scratch_strength: float = DEFAULT_LENS_SCRATCH_STRENGTH
    lens_scratch_density: float = DEFAULT_LENS_SCRATCH_DENSITY
    lens_scratch_length: float = DEFAULT_LENS_SCRATCH_LENGTH
    lens_flare_seed: int = DEFAULT_LENS_FLARE_SEED
    triplanar_mode: str = DEFAULT_TRIPLANAR_MODE
    triplanar_strength: float = DEFAULT_TRIPLANAR_STRENGTH
    triplanar_scale: float = DEFAULT_TRIPLANAR_SCALE
    triplanar_blend_sharpness: float = DEFAULT_TRIPLANAR_BLEND_SHARPNESS
    triplanar_offset: tuple[float, float, float] = (
        DEFAULT_TRIPLANAR_OFFSET[0],
        DEFAULT_TRIPLANAR_OFFSET[1],
        DEFAULT_TRIPLANAR_OFFSET[2],
    )
    triplanar_space: str = "object"
    light_azimuth: float = 45.0
    light_elevation: float = 45.0
    light_color: tuple[float, float, float] = (1.0, 1.0, 1.0)
    direct_intensity: float = 0.42
    shadow_strength: float = DEFAULT_SHADOW_STRENGTH
    shadow_pcf_radius: float = DEFAULT_SHADOW_PCF_RADIUS
    shadow_filter: str = DEFAULT_SHADOW_FILTER
    shadow_light_type: str = DEFAULT_SHADOW_LIGHT_TYPE
    shadow_pcss_blocker_radius: float = DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS
    shadow_bias: float = DEFAULT_SHADOW_BIAS
    shadow_normal_bias: float = DEFAULT_SHADOW_NORMAL_BIAS
    shadow_spot_inner_angle: float = DEFAULT_SPOT_INNER_ANGLE
    shadow_spot_outer_angle: float = DEFAULT_SPOT_OUTER_ANGLE
    self_shadow_strength: float = 0.45
    ground_y: float = -0.52
    ground_reflection: float = 0.05
    shadow_catcher_opacity: float = DEFAULT_SHADOW_CATCHER_OPACITY
    shadow_catcher_softness: float = DEFAULT_SHADOW_CATCHER_SOFTNESS
    shadow_catcher_matte_alpha: float = DEFAULT_SHADOW_CATCHER_MATTE_ALPHA
    reflection_catcher_opacity: float = DEFAULT_REFLECTION_CATCHER_OPACITY
    reflection_catcher_roughness: float = DEFAULT_REFLECTION_CATCHER_ROUGHNESS
    reflection_catcher_softness: float = DEFAULT_REFLECTION_CATCHER_SOFTNESS
    contact_reflection_strength: float = DEFAULT_CONTACT_REFLECTION_STRENGTH
    contact_reflection_falloff: float = DEFAULT_CONTACT_REFLECTION_FALLOFF


def shadow_filter_diagnostics(
    state: GpuState,
    *,
    enable_shadow_map: bool,
    shadow_supported: bool,
    shadow_size: int,
    shadow_error: str = "",
    shadow_backend: str = "",
) -> dict[str, Any]:
    settings = {
        "shadow_filter": getattr(state, "shadow_filter", DEFAULT_SHADOW_FILTER),
        "shadow_light_type": getattr(state, "shadow_light_type", DEFAULT_SHADOW_LIGHT_TYPE),
        "shadow_map_size": int(shadow_size),
        "shadow_pcf_radius": getattr(state, "shadow_pcf_radius", DEFAULT_SHADOW_PCF_RADIUS),
        "shadow_pcss_blocker_radius": getattr(state, "shadow_pcss_blocker_radius", DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS),
        "shadow_bias": getattr(state, "shadow_bias", DEFAULT_SHADOW_BIAS),
        "shadow_normal_bias": getattr(state, "shadow_normal_bias", DEFAULT_SHADOW_NORMAL_BIAS),
        "shadow_spot_inner_angle": getattr(state, "shadow_spot_inner_angle", DEFAULT_SPOT_INNER_ANGLE),
        "shadow_spot_outer_angle": getattr(state, "shadow_spot_outer_angle", DEFAULT_SPOT_OUTER_ANGLE),
    }
    out = build_shadow_filter_diagnostics(
        settings=settings,
        shadow_map_requested=enable_shadow_map,
        shadow_map_enabled=shadow_supported,
        backend=str(shadow_backend or ("shadow_map" if shadow_supported else "fallback")),
        shadow_error=shadow_error,
    )
    out["self_shadow_strength"] = max(0.0, min(1.0, float(getattr(state, "self_shadow_strength", 0.45))))
    return out


def catcher_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_catcher_settings({
        "shadow_catcher_opacity": getattr(state, "shadow_catcher_opacity", DEFAULT_SHADOW_CATCHER_OPACITY),
        "shadow_catcher_softness": getattr(state, "shadow_catcher_softness", DEFAULT_SHADOW_CATCHER_SOFTNESS),
        "shadow_catcher_matte_alpha": getattr(state, "shadow_catcher_matte_alpha", DEFAULT_SHADOW_CATCHER_MATTE_ALPHA),
        "reflection_catcher_opacity": getattr(state, "reflection_catcher_opacity", DEFAULT_REFLECTION_CATCHER_OPACITY),
        "reflection_catcher_roughness": getattr(state, "reflection_catcher_roughness", DEFAULT_REFLECTION_CATCHER_ROUGHNESS),
        "reflection_catcher_softness": getattr(state, "reflection_catcher_softness", DEFAULT_REFLECTION_CATCHER_SOFTNESS),
        "contact_reflection_strength": getattr(state, "contact_reflection_strength", DEFAULT_CONTACT_REFLECTION_STRENGTH),
        "contact_reflection_falloff": getattr(state, "contact_reflection_falloff", DEFAULT_CONTACT_REFLECTION_FALLOFF),
    })


def color_management_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_color_management_settings({
        "tone_mapping": getattr(state, "tone_mapping", DEFAULT_TONE_MAPPING),
        "tone_exposure": getattr(state, "tone_exposure", DEFAULT_TONE_EXPOSURE),
        "tone_white_balance": getattr(state, "tone_white_balance", DEFAULT_TONE_WHITE_BALANCE),
        "tone_gamma": getattr(state, "tone_gamma", DEFAULT_TONE_GAMMA),
    })


def hybrid_rendering_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_hybrid_render_settings({
        "enabled": int(getattr(state, "hybrid_sample_count", DEFAULT_HYBRID_SAMPLE_COUNT)) > 1
        or float(getattr(state, "diffuse_gi_strength", DEFAULT_DIFFUSE_GI_STRENGTH)) > 0.0
        or float(getattr(state, "specular_gi_strength", DEFAULT_SPECULAR_GI_STRENGTH)) > 0.0
        or float(getattr(state, "denoise_strength", DEFAULT_DENOISE_STRENGTH)) > 0.0,
        "sample_count": getattr(state, "hybrid_sample_count", DEFAULT_HYBRID_SAMPLE_COUNT),
        "diffuse_gi_strength": getattr(state, "diffuse_gi_strength", DEFAULT_DIFFUSE_GI_STRENGTH),
        "specular_gi_strength": getattr(state, "specular_gi_strength", DEFAULT_SPECULAR_GI_STRENGTH),
        "denoise_strength": getattr(state, "denoise_strength", DEFAULT_DENOISE_STRENGTH),
    })


def ray_gi_detail_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_ray_gi_detail_settings({
        "mode": getattr(state, "ray_gi_detail_mode", DEFAULT_RAY_GI_DETAIL_MODE),
        "enabled": str(getattr(state, "ray_gi_detail_mode", DEFAULT_RAY_GI_DETAIL_MODE)) != "off"
        or int(getattr(state, "ray_gi_max_bounces", DEFAULT_RAY_GI_MAX_BOUNCES)) > DEFAULT_RAY_GI_MAX_BOUNCES
        or float(getattr(state, "ray_gi_direct_radiance_clamp", DEFAULT_DIRECT_RADIANCE_CLAMP)) > 0.0
        or float(getattr(state, "ray_gi_indirect_radiance_clamp", DEFAULT_INDIRECT_RADIANCE_CLAMP)) > 0.0
        or str(getattr(state, "ray_gi_light_sampling_mode", DEFAULT_LIGHT_SAMPLING_MODE)) != DEFAULT_LIGHT_SAMPLING_MODE
        or int(getattr(state, "ray_gi_light_sample_count", DEFAULT_LIGHT_SAMPLE_COUNT)) > DEFAULT_LIGHT_SAMPLE_COUNT
        or int(getattr(state, "ray_gi_environment_sample_count", DEFAULT_ENVIRONMENT_SAMPLE_COUNT)) > DEFAULT_ENVIRONMENT_SAMPLE_COUNT
        or bool(getattr(state, "ray_gi_mis_enabled", False))
        or bool(getattr(state, "ray_gi_importance_sampling", False))
        or tuple(getattr(state, "ray_gi_denoise_channels", ("beauty",))) != ("beauty",)
        or not bool(getattr(state, "ray_gi_denoise_beauty", True))
        or bool(getattr(state, "ray_gi_denoise_diffuse", False))
        or bool(getattr(state, "ray_gi_denoise_specular", False))
        or bool(getattr(state, "ray_gi_denoise_transmission", False)),
        "max_bounces": getattr(state, "ray_gi_max_bounces", DEFAULT_RAY_GI_MAX_BOUNCES),
        "diffuse_bounces": getattr(state, "ray_gi_diffuse_bounces", DEFAULT_RAY_GI_DIFFUSE_BOUNCES),
        "specular_bounces": getattr(state, "ray_gi_specular_bounces", DEFAULT_RAY_GI_SPECULAR_BOUNCES),
        "refraction_bounces": getattr(state, "ray_gi_refraction_bounces", DEFAULT_RAY_GI_REFRACTION_BOUNCES),
        "direct_radiance_clamp": getattr(state, "ray_gi_direct_radiance_clamp", DEFAULT_DIRECT_RADIANCE_CLAMP),
        "indirect_radiance_clamp": getattr(state, "ray_gi_indirect_radiance_clamp", DEFAULT_INDIRECT_RADIANCE_CLAMP),
        "light_sampling_mode": getattr(state, "ray_gi_light_sampling_mode", DEFAULT_LIGHT_SAMPLING_MODE),
        "light_sample_count": getattr(state, "ray_gi_light_sample_count", DEFAULT_LIGHT_SAMPLE_COUNT),
        "environment_sample_count": getattr(state, "ray_gi_environment_sample_count", DEFAULT_ENVIRONMENT_SAMPLE_COUNT),
        "mis_enabled": getattr(state, "ray_gi_mis_enabled", False),
        "importance_sampling": getattr(state, "ray_gi_importance_sampling", False),
        "denoise_channels": list(getattr(state, "ray_gi_denoise_channels", ("beauty",))),
        "denoise_beauty": getattr(state, "ray_gi_denoise_beauty", True),
        "denoise_diffuse": getattr(state, "ray_gi_denoise_diffuse", False),
        "denoise_specular": getattr(state, "ray_gi_denoise_specular", False),
        "denoise_transmission": getattr(state, "ray_gi_denoise_transmission", False),
        "denoise_albedo_guided": getattr(state, "ray_gi_denoise_albedo_guided", False),
        "denoise_normal_guided": getattr(state, "ray_gi_denoise_normal_guided", False),
    })


def ambient_occlusion_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_ambient_occlusion_settings({
        "mode": getattr(state, "ambient_occlusion_mode", DEFAULT_AMBIENT_OCCLUSION_MODE),
        "enabled": float(getattr(state, "ao_strength", DEFAULT_AO_STRENGTH)) > 0.0,
        "ao_strength": getattr(state, "ao_strength", DEFAULT_AO_STRENGTH),
        "ao_radius": getattr(state, "ao_radius", DEFAULT_AO_RADIUS),
        "ao_distance": getattr(state, "ao_distance", DEFAULT_AO_DISTANCE),
        "ao_color": list(getattr(state, "ao_color", tuple(DEFAULT_AO_COLOR))),
        "ao_ambient": getattr(state, "ao_ambient", DEFAULT_AO_AMBIENT),
        "ao_diffuse": getattr(state, "ao_diffuse", DEFAULT_AO_DIFFUSE),
        "ao_specular": getattr(state, "ao_specular", DEFAULT_AO_SPECULAR),
    })


def transmission_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_transmission_settings({
        "mode": getattr(state, "transmission_mode", DEFAULT_TRANSMISSION_MODE),
        "enabled": float(getattr(state, "transmission", DEFAULT_TRANSMISSION)) > 0.0
        or float(getattr(state, "refraction_strength", DEFAULT_REFRACTION_STRENGTH)) > 0.0,
        "transmission": getattr(state, "transmission", DEFAULT_TRANSMISSION),
        "refraction_strength": getattr(state, "refraction_strength", DEFAULT_REFRACTION_STRENGTH),
        "refraction_depth_px": getattr(state, "refraction_depth_px", DEFAULT_REFRACTION_DEPTH_PX),
        "ior": getattr(state, "ior", DEFAULT_IOR),
        "thickness": getattr(state, "thickness", DEFAULT_THICKNESS),
        "absorption_color": list(getattr(state, "absorption_color", tuple(DEFAULT_ABSORPTION_COLOR))),
        "absorption_distance": getattr(state, "absorption_distance", DEFAULT_ABSORPTION_DISTANCE),
        "roughness_blur_strength": getattr(state, "roughness_blur_strength", DEFAULT_ROUGHNESS_BLUR_STRENGTH),
    })


def clearcoat_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_clearcoat_settings({
        "mode": getattr(state, "clearcoat_mode", DEFAULT_CLEARCOAT_MODE),
        "enabled": float(getattr(state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH)) > 0.0,
        "clearcoat_strength": getattr(state, "clearcoat_strength", DEFAULT_CLEARCOAT_STRENGTH),
        "clearcoat_roughness": getattr(state, "clearcoat_roughness", DEFAULT_CLEARCOAT_ROUGHNESS),
        "clearcoat_ior": getattr(state, "clearcoat_ior", DEFAULT_CLEARCOAT_IOR),
        "clearcoat_tint": list(getattr(state, "clearcoat_tint", tuple(DEFAULT_CLEARCOAT_TINT))),
    })


def parallax_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_parallax_settings({
        "mode": getattr(state, "parallax_mode", DEFAULT_PARALLAX_MODE),
        "enabled": float(getattr(state, "parallax_strength", DEFAULT_PARALLAX_STRENGTH)) > 0.0,
        "parallax_strength": getattr(state, "parallax_strength", DEFAULT_PARALLAX_STRENGTH),
        "parallax_depth": getattr(state, "parallax_depth", DEFAULT_PARALLAX_DEPTH),
        "parallax_center": getattr(state, "parallax_center", DEFAULT_PARALLAX_CENTER),
        "parallax_steps": getattr(state, "parallax_steps", DEFAULT_PARALLAX_STEPS),
    })


def displacement_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_displacement_settings({
        "mode": getattr(state, "displacement_mode", DEFAULT_DISPLACEMENT_MODE),
        "enabled": float(
            getattr(state, "displacement_height_strength", DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH)
        ) > 0.0
        or float(
            getattr(state, "vector_displacement_strength", DEFAULT_VECTOR_DISPLACEMENT_STRENGTH)
        ) > 0.0,
        "height_strength": getattr(
            state,
            "displacement_height_strength",
            DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH,
        ),
        "height_scale": getattr(state, "displacement_height_scale", DEFAULT_DISPLACEMENT_HEIGHT_SCALE),
        "height_center": getattr(state, "displacement_height_center", DEFAULT_DISPLACEMENT_HEIGHT_CENTER),
        "vector_strength": getattr(
            state,
            "vector_displacement_strength",
            DEFAULT_VECTOR_DISPLACEMENT_STRENGTH,
        ),
        "vector_space": getattr(state, "vector_displacement_space", DEFAULT_VECTOR_DISPLACEMENT_SPACE),
        "subdivision_mode": getattr(
            state,
            "displacement_subdivision_mode",
            DEFAULT_DISPLACEMENT_SUBDIVISION_MODE,
        ),
        "max_offset": getattr(state, "displacement_max_offset", DEFAULT_DISPLACEMENT_MAX_OFFSET),
        "parallax_fallback": getattr(
            state,
            "displacement_parallax_fallback",
            DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK,
        ),
    })


def bevel_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_bevel_settings({
        "mode": getattr(state, "bevel_mode", DEFAULT_BEVEL_MODE),
        "enabled": float(getattr(state, "bevel_strength", DEFAULT_BEVEL_STRENGTH)) > 0.0,
        "bevel_strength": getattr(state, "bevel_strength", DEFAULT_BEVEL_STRENGTH),
        "bevel_radius": getattr(state, "bevel_radius", DEFAULT_BEVEL_RADIUS),
        "bevel_edge_width": getattr(state, "bevel_edge_width", DEFAULT_BEVEL_EDGE_WIDTH),
        "bevel_samples": getattr(state, "bevel_samples", DEFAULT_BEVEL_SAMPLES),
    })


def material_layering_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_material_layering_settings({
        "mode": getattr(state, "material_layer_mode", DEFAULT_MATERIAL_LAYER_MODE),
        "enabled": float(getattr(state, "material_layer_blend", DEFAULT_MATERIAL_LAYER_BLEND)) > 0.0,
        "material_layer_blend": getattr(state, "material_layer_blend", DEFAULT_MATERIAL_LAYER_BLEND),
        "material_layer_color": list(getattr(state, "material_layer_color", tuple(DEFAULT_MATERIAL_LAYER_COLOR))),
        "material_layer_roughness": getattr(state, "material_layer_roughness", DEFAULT_MATERIAL_LAYER_ROUGHNESS),
        "material_layer_metallic": getattr(state, "material_layer_metallic", DEFAULT_MATERIAL_LAYER_METALLIC),
        "material_layer_alpha": getattr(state, "material_layer_alpha", DEFAULT_MATERIAL_LAYER_ALPHA),
        "material_layer_emissive_strength": getattr(
            state,
            "material_layer_emissive_strength",
            DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH,
        ),
        "material_layer_mask_strength": getattr(
            state,
            "material_layer_mask_strength",
            DEFAULT_MATERIAL_LAYER_MASK_STRENGTH,
        ),
    })


def surface_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_surface_settings({
        "surface_override_strength": getattr(state, "surface_override_strength", DEFAULT_SURFACE_OVERRIDE_STRENGTH),
        "surface_roughness": getattr(state, "surface_roughness", DEFAULT_SURFACE_ROUGHNESS),
        "surface_metallic": getattr(state, "surface_metallic", DEFAULT_SURFACE_METALLIC),
        "surface_reflectance": getattr(state, "surface_reflectance", DEFAULT_SURFACE_REFLECTANCE),
    })


def subsurface_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_subsurface_settings({
        "mode": getattr(state, "subsurface_mode", DEFAULT_SUBSURFACE_MODE),
        "enabled": float(getattr(state, "subsurface_strength", DEFAULT_SUBSURFACE_STRENGTH)) > 0.0,
        "subsurface_strength": getattr(state, "subsurface_strength", DEFAULT_SUBSURFACE_STRENGTH),
        "subsurface_color": list(getattr(state, "subsurface_color", tuple(DEFAULT_SUBSURFACE_COLOR))),
        "subsurface_radius": getattr(state, "subsurface_radius", DEFAULT_SUBSURFACE_RADIUS),
        "subsurface_power": getattr(state, "subsurface_power", DEFAULT_SUBSURFACE_POWER),
        "subsurface_wrap": getattr(state, "subsurface_wrap", DEFAULT_SUBSURFACE_WRAP),
        "subsurface_thickness": getattr(state, "subsurface_thickness", DEFAULT_SUBSURFACE_THICKNESS),
    })


def hair_groom_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_hair_groom_settings({
        "mode": getattr(state, "hair_groom_mode", DEFAULT_HAIR_GROOM_MODE),
        "enabled": float(getattr(state, "hair_groom_strength", DEFAULT_HAIR_GROOM_STRENGTH)) > 0.0,
        "hair_groom_strength": getattr(state, "hair_groom_strength", DEFAULT_HAIR_GROOM_STRENGTH),
        "hair_groom_tint": list(getattr(state, "hair_groom_tint", tuple(DEFAULT_HAIR_GROOM_TINT))),
        "hair_primary_shift": getattr(state, "hair_primary_shift", DEFAULT_HAIR_PRIMARY_SHIFT),
        "hair_secondary_shift": getattr(state, "hair_secondary_shift", DEFAULT_HAIR_SECONDARY_SHIFT),
        "hair_primary_roughness": getattr(state, "hair_primary_roughness", DEFAULT_HAIR_PRIMARY_ROUGHNESS),
        "hair_secondary_roughness": getattr(state, "hair_secondary_roughness", DEFAULT_HAIR_SECONDARY_ROUGHNESS),
        "hair_secondary_strength": getattr(state, "hair_secondary_strength", DEFAULT_HAIR_SECONDARY_STRENGTH),
        "hair_anisotropy": getattr(state, "hair_anisotropy", DEFAULT_HAIR_ANISOTROPY),
        "hair_rim_strength": getattr(state, "hair_rim_strength", DEFAULT_HAIR_RIM_STRENGTH),
    })


def cloth_sheen_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_cloth_sheen_settings({
        "mode": getattr(state, "cloth_sheen_mode", DEFAULT_CLOTH_SHEEN_MODE),
        "enabled": float(getattr(state, "cloth_sheen_strength", DEFAULT_CLOTH_SHEEN_STRENGTH)) > 0.0,
        "cloth_sheen_strength": getattr(state, "cloth_sheen_strength", DEFAULT_CLOTH_SHEEN_STRENGTH),
        "cloth_sheen_color": list(getattr(state, "cloth_sheen_color", tuple(DEFAULT_CLOTH_SHEEN_COLOR))),
        "cloth_sheen_roughness": getattr(state, "cloth_sheen_roughness", DEFAULT_CLOTH_SHEEN_ROUGHNESS),
        "cloth_sheen_edge_tint": list(getattr(state, "cloth_sheen_edge_tint", tuple(DEFAULT_CLOTH_SHEEN_EDGE_TINT))),
        "cloth_sheen_fiber_strength": getattr(
            state,
            "cloth_sheen_fiber_strength",
            DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH,
        ),
        "cloth_sheen_wrap": getattr(state, "cloth_sheen_wrap", DEFAULT_CLOTH_SHEEN_WRAP),
        "cloth_sheen_retroreflection": getattr(
            state,
            "cloth_sheen_retroreflection",
            DEFAULT_CLOTH_SHEEN_RETROREFLECTION,
        ),
    })


def glint_sparkle_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_glint_sparkle_settings({
        "mode": getattr(state, "glint_mode", DEFAULT_GLINT_MODE),
        "enabled": float(getattr(state, "glint_strength", DEFAULT_GLINT_STRENGTH)) > 0.0,
        "glint_strength": getattr(state, "glint_strength", DEFAULT_GLINT_STRENGTH),
        "glint_color": list(getattr(state, "glint_color", tuple(DEFAULT_GLINT_COLOR))),
        "glint_density": getattr(state, "glint_density", DEFAULT_GLINT_DENSITY),
        "glint_scale": getattr(state, "glint_scale", DEFAULT_GLINT_SCALE),
        "glint_threshold": getattr(state, "glint_threshold", DEFAULT_GLINT_THRESHOLD),
        "glint_sharpness": getattr(state, "glint_sharpness", DEFAULT_GLINT_SHARPNESS),
        "glint_roughness_jitter": getattr(
            state,
            "glint_roughness_jitter",
            DEFAULT_GLINT_ROUGHNESS_JITTER,
        ),
    })


def caustics_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_caustics_settings({
        "mode": getattr(state, "caustics_mode", DEFAULT_CAUSTICS_MODE),
        "enabled": float(getattr(state, "caustics_strength", DEFAULT_CAUSTICS_STRENGTH)) > 0.0
        or str(getattr(state, "caustics_mode", DEFAULT_CAUSTICS_MODE)) != "off",
        "caustics_strength": getattr(state, "caustics_strength", DEFAULT_CAUSTICS_STRENGTH),
        "caustics_quality": getattr(state, "caustics_quality", DEFAULT_CAUSTICS_QUALITY),
        "caustics_sample_count": getattr(state, "caustics_sample_count", DEFAULT_CAUSTICS_SAMPLE_COUNT),
        "caustics_scale": getattr(state, "caustics_scale", DEFAULT_CAUSTICS_SCALE),
        "caustics_focus": getattr(state, "caustics_focus", DEFAULT_CAUSTICS_FOCUS),
        "caustics_radius": getattr(state, "caustics_radius", DEFAULT_CAUSTICS_RADIUS),
        "caustics_threshold": getattr(state, "caustics_threshold", DEFAULT_CAUSTICS_THRESHOLD),
        "caustics_tint": list(getattr(state, "caustics_tint", tuple(DEFAULT_CAUSTICS_TINT))),
        "caustics_seed": getattr(state, "caustics_seed", DEFAULT_CAUSTICS_SEED),
    })


def anisotropic_material_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_anisotropic_material_settings({
        "mode": getattr(state, "anisotropic_mode", DEFAULT_ANISOTROPIC_MODE),
        "enabled": float(getattr(state, "anisotropic_strength", DEFAULT_ANISOTROPIC_STRENGTH)) > 0.0
        or abs(float(getattr(state, "anisotropy", DEFAULT_ANISOTROPY))) > 0.0
        or float(getattr(state, "thin_film_strength", DEFAULT_THIN_FILM_STRENGTH)) > 0.0
        or float(getattr(state, "newton_rings_strength", DEFAULT_NEWTON_RINGS_STRENGTH)) > 0.0,
        "anisotropic_strength": getattr(state, "anisotropic_strength", DEFAULT_ANISOTROPIC_STRENGTH),
        "anisotropy": getattr(state, "anisotropy", DEFAULT_ANISOTROPY),
        "anisotropic_rotation": getattr(state, "anisotropic_rotation", DEFAULT_ANISOTROPIC_ROTATION),
        "anisotropic_tangent_weight": getattr(
            state,
            "anisotropic_tangent_weight",
            DEFAULT_ANISOTROPIC_TANGENT_WEIGHT,
        ),
        "clearcoat_anisotropy": getattr(state, "clearcoat_anisotropy", DEFAULT_CLEARCOAT_ANISOTROPY),
        "thin_film_enabled": float(getattr(state, "thin_film_strength", DEFAULT_THIN_FILM_STRENGTH)) > 0.0,
        "thin_film_strength": getattr(state, "thin_film_strength", DEFAULT_THIN_FILM_STRENGTH),
        "thin_film_thickness_nm": getattr(state, "thin_film_thickness_nm", DEFAULT_THIN_FILM_THICKNESS_NM),
        "thin_film_ior": getattr(state, "thin_film_ior", DEFAULT_THIN_FILM_IOR),
        "thin_film_tint": list(getattr(state, "thin_film_tint", tuple(DEFAULT_THIN_FILM_TINT))),
        "newton_rings_strength": getattr(state, "newton_rings_strength", DEFAULT_NEWTON_RINGS_STRENGTH),
        "newton_rings_scale": getattr(state, "newton_rings_scale", DEFAULT_NEWTON_RINGS_SCALE),
        "anisotropic_seed": getattr(state, "anisotropic_seed", DEFAULT_ANISOTROPIC_SEED),
    })


def microsurface_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_microsurface_settings({
        "mode": getattr(state, "microsurface_mode", DEFAULT_MICROSURFACE_MODE),
        "enabled": float(getattr(state, "detail_normal_strength", DEFAULT_DETAIL_NORMAL_STRENGTH)) > 0.0
        or float(getattr(state, "micro_roughness_strength", DEFAULT_MICRO_ROUGHNESS_STRENGTH)) > 0.0
        or float(getattr(state, "gloss_variation_strength", DEFAULT_GLOSS_VARIATION_STRENGTH)) > 0.0
        or float(getattr(state, "specular_micro_occlusion", DEFAULT_SPECULAR_MICRO_OCCLUSION)) > 0.0,
        "detail_normal_strength": getattr(state, "detail_normal_strength", DEFAULT_DETAIL_NORMAL_STRENGTH),
        "detail_normal_scale": getattr(state, "detail_normal_scale", DEFAULT_DETAIL_NORMAL_SCALE),
        "detail_normal_blend": getattr(state, "detail_normal_blend", DEFAULT_DETAIL_NORMAL_BLEND),
        "detail_normal_seed": getattr(state, "detail_normal_seed", DEFAULT_DETAIL_NORMAL_SEED),
        "micro_roughness_strength": getattr(state, "micro_roughness_strength", DEFAULT_MICRO_ROUGHNESS_STRENGTH),
        "micro_roughness_scale": getattr(state, "micro_roughness_scale", DEFAULT_MICRO_ROUGHNESS_SCALE),
        "micro_roughness_contrast": getattr(state, "micro_roughness_contrast", DEFAULT_MICRO_ROUGHNESS_CONTRAST),
        "gloss_variation_strength": getattr(state, "gloss_variation_strength", DEFAULT_GLOSS_VARIATION_STRENGTH),
        "gloss_bias": getattr(state, "gloss_bias", DEFAULT_GLOSS_BIAS),
        "specular_micro_occlusion": getattr(state, "specular_micro_occlusion", DEFAULT_SPECULAR_MICRO_OCCLUSION),
    })


def depth_of_field_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_depth_of_field_settings({
        "mode": getattr(state, "depth_of_field_mode", DEFAULT_DEPTH_OF_FIELD_MODE),
        "enabled": float(getattr(state, "depth_of_field_strength", DEFAULT_DEPTH_OF_FIELD_STRENGTH)) > 0.0,
        "depth_of_field_strength": getattr(
            state,
            "depth_of_field_strength",
            DEFAULT_DEPTH_OF_FIELD_STRENGTH,
        ),
        "dof_focus_depth": getattr(state, "dof_focus_depth", DEFAULT_DOF_FOCUS_DEPTH),
        "dof_focus_range": getattr(state, "dof_focus_range", DEFAULT_DOF_FOCUS_RANGE),
        "dof_max_blur_px": getattr(state, "dof_max_blur_px", DEFAULT_DOF_MAX_BLUR_PX),
        "dof_near_blur": getattr(state, "dof_near_blur", DEFAULT_DOF_NEAR_BLUR),
        "dof_far_blur": getattr(state, "dof_far_blur", DEFAULT_DOF_FAR_BLUR),
        "dof_bokeh_shape": getattr(state, "dof_bokeh_shape", DEFAULT_DOF_BOKEH_SHAPE),
    })


def post_effects_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_post_effects_settings({
        "mode": getattr(state, "post_effects_mode", DEFAULT_POST_EFFECTS_MODE),
        "bloom_strength": getattr(state, "bloom_strength", DEFAULT_BLOOM_STRENGTH),
        "bloom_radius": getattr(state, "bloom_radius", DEFAULT_BLOOM_RADIUS),
        "bloom_threshold": getattr(state, "bloom_threshold", DEFAULT_BLOOM_THRESHOLD),
        "bloom_boost": getattr(state, "bloom_boost", DEFAULT_BLOOM_BOOST),
        "bloom_anamorphic_strength": getattr(
            state,
            "bloom_anamorphic_strength",
            DEFAULT_BLOOM_ANAMORPHIC_STRENGTH,
        ),
        "bloom_anamorphic_threshold": getattr(
            state,
            "bloom_anamorphic_threshold",
            DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD,
        ),
        "bloom_anamorphic_ratio": getattr(
            state,
            "bloom_anamorphic_ratio",
            DEFAULT_BLOOM_ANAMORPHIC_RATIO,
        ),
        "vignette_strength": getattr(state, "vignette_strength", DEFAULT_VIGNETTE_STRENGTH),
        "vignette_radius": getattr(state, "vignette_radius", DEFAULT_VIGNETTE_RADIUS),
        "vignette_feather": getattr(state, "vignette_feather", DEFAULT_VIGNETTE_FEATHER),
        "grain_strength": getattr(state, "grain_strength", DEFAULT_GRAIN_STRENGTH),
        "grain_scale": getattr(state, "grain_scale", DEFAULT_GRAIN_SCALE),
        "grain_seed": getattr(state, "grain_seed", DEFAULT_GRAIN_SEED),
        "sharpen_strength": getattr(state, "sharpen_strength", DEFAULT_SHARPEN_STRENGTH),
        "sharpen_radius": getattr(state, "sharpen_radius", DEFAULT_SHARPEN_RADIUS),
    })


def lens_effects_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_lens_effects_settings({
        "mode": getattr(state, "lens_effects_mode", DEFAULT_LENS_EFFECTS_MODE),
        "lens_distortion_strength": getattr(
            state,
            "lens_distortion_strength",
            DEFAULT_LENS_DISTORTION_STRENGTH,
        ),
        "lens_distortion_k2": getattr(state, "lens_distortion_k2", DEFAULT_LENS_DISTORTION_K2),
        "chromatic_aberration_strength": getattr(
            state,
            "chromatic_aberration_strength",
            DEFAULT_CHROMATIC_ABERRATION_STRENGTH,
        ),
        "chromatic_aberration_px": getattr(
            state,
            "chromatic_aberration_px",
            DEFAULT_CHROMATIC_ABERRATION_PX,
        ),
        "lens_center": list(getattr(state, "lens_center", tuple(DEFAULT_LENS_CENTER))),
        "lens_edge_falloff": getattr(state, "lens_edge_falloff", DEFAULT_LENS_EDGE_FALLOFF),
    })


def lens_flare_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_lens_flare_settings({
        "mode": getattr(state, "lens_flare_mode", DEFAULT_LENS_FLARE_MODE),
        "lens_flare_strength": getattr(state, "lens_flare_strength", DEFAULT_LENS_FLARE_STRENGTH),
        "lens_flare_threshold": getattr(state, "lens_flare_threshold", DEFAULT_LENS_FLARE_THRESHOLD),
        "lens_flare_radius": getattr(state, "lens_flare_radius", DEFAULT_LENS_FLARE_RADIUS),
        "lens_flare_ghost_count": getattr(state, "lens_flare_ghost_count", DEFAULT_LENS_FLARE_GHOST_COUNT),
        "lens_flare_ghost_spacing": getattr(state, "lens_flare_ghost_spacing", DEFAULT_LENS_FLARE_GHOST_SPACING),
        "lens_flare_tint": list(getattr(state, "lens_flare_tint", tuple(DEFAULT_LENS_FLARE_TINT))),
        "aperture_flare_strength": getattr(state, "aperture_flare_strength", DEFAULT_APERTURE_FLARE_STRENGTH),
        "aperture_flare_blades": getattr(state, "aperture_flare_blades", DEFAULT_APERTURE_FLARE_BLADES),
        "aperture_flare_rotation_deg": getattr(
            state,
            "aperture_flare_rotation_deg",
            DEFAULT_APERTURE_FLARE_ROTATION_DEG,
        ),
        "aperture_flare_radius": getattr(state, "aperture_flare_radius", DEFAULT_APERTURE_FLARE_RADIUS),
        "lens_dirt_strength": getattr(state, "lens_dirt_strength", DEFAULT_LENS_DIRT_STRENGTH),
        "lens_dirt_density": getattr(state, "lens_dirt_density", DEFAULT_LENS_DIRT_DENSITY),
        "lens_dirt_scale": getattr(state, "lens_dirt_scale", DEFAULT_LENS_DIRT_SCALE),
        "lens_scratch_strength": getattr(state, "lens_scratch_strength", DEFAULT_LENS_SCRATCH_STRENGTH),
        "lens_scratch_density": getattr(state, "lens_scratch_density", DEFAULT_LENS_SCRATCH_DENSITY),
        "lens_scratch_length": getattr(state, "lens_scratch_length", DEFAULT_LENS_SCRATCH_LENGTH),
        "lens_flare_seed": getattr(state, "lens_flare_seed", DEFAULT_LENS_FLARE_SEED),
    })


def triplanar_diagnostics(state: GpuState) -> dict[str, Any]:
    return normalize_triplanar_settings({
        "mode": getattr(state, "triplanar_mode", DEFAULT_TRIPLANAR_MODE),
        "enabled": float(getattr(state, "triplanar_strength", DEFAULT_TRIPLANAR_STRENGTH)) > 0.0,
        "triplanar_strength": getattr(state, "triplanar_strength", DEFAULT_TRIPLANAR_STRENGTH),
        "triplanar_scale": getattr(state, "triplanar_scale", DEFAULT_TRIPLANAR_SCALE),
        "triplanar_blend_sharpness": getattr(
            state,
            "triplanar_blend_sharpness",
            DEFAULT_TRIPLANAR_BLEND_SHARPNESS,
        ),
        "triplanar_offset": list(getattr(state, "triplanar_offset", tuple(DEFAULT_TRIPLANAR_OFFSET))),
        "triplanar_space": getattr(state, "triplanar_space", "object"),
    })


def _normalized_bounds_corners(mesh_diag: Mapping[str, Any]) -> np.ndarray:
    bounds = mesh_diag.get("normalized_bounds") if isinstance(mesh_diag.get("normalized_bounds"), Mapping) else {}
    mins = np.asarray(bounds.get("min", [-0.5, -0.5, -0.5]), dtype=np.float32)
    maxs = np.asarray(bounds.get("max", [0.5, 0.5, 0.5]), dtype=np.float32)
    if mins.shape != (3,) or maxs.shape != (3,) or not np.all(np.isfinite(mins)) or not np.all(np.isfinite(maxs)):
        mins = np.asarray([-0.5, -0.5, -0.5], dtype=np.float32)
        maxs = np.asarray([0.5, 0.5, 0.5], dtype=np.float32)
    return np.asarray(
        [[x, y, z] for x in (mins[0], maxs[0]) for y in (mins[1], maxs[1]) for z in (mins[2], maxs[2])],
        dtype=np.float32,
    )


def _rotation_matrix(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)
    sx, cx = math.sin(rx), math.cos(rx)
    sy, cy = math.sin(ry), math.cos(ry)
    sz, cz = math.sin(rz), math.cos(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype=np.float32)
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype=np.float32)
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype=np.float32)
    return mz @ my @ mx


def _perspective(fov_deg: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    out = np.zeros((4, 4), dtype=np.float32)
    out[0, 0] = f / max(aspect, 1e-6)
    out[1, 1] = f
    out[2, 2] = (far + near) / (near - far)
    out[2, 3] = (2.0 * far * near) / (near - far)
    out[3, 2] = -1.0
    return out


def _projected_bounds_half_extent(
    points_in: np.ndarray,
    *,
    pitch: float,
    yaw: float,
    roll: float,
    zoom: float,
    camera_z: float,
    aspect: float,
    fov_deg: float = FRAME_FIT_FOV_DEG,
    near: float = 0.05,
) -> tuple[float, float, float]:
    rot = _rotation_matrix(pitch, yaw, roll)
    points = (points_in @ rot.T) * float(zoom)
    depth = float(camera_z) - points[:, 2]
    if np.any(depth <= near):
        return float("inf"), float("inf"), float("inf")
    f = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
    ndc_x = (f / max(float(aspect), 1e-6)) * points[:, 0] / depth
    ndc_y = f * points[:, 1] / depth
    half_x = float(np.max(np.abs(ndc_x)))
    half_y = float(np.max(np.abs(ndc_y)))
    return max(half_x, half_y), half_x, half_y


def _fit_zoom_to_projected_points(
    points: np.ndarray,
    state: GpuState,
    *,
    viewport_width: int,
    viewport_height: int,
    padding: float = DEFAULT_FRAME_FIT_PADDING,
    minimum_zoom: float = 0.1,
    maximum_zoom: float = 8.0,
) -> tuple[float, dict[str, Any]]:
    points = np.asarray(points, dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0:
        points = np.asarray([[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]], dtype=np.float32)
    aspect = max(float(viewport_width), 1.0) / max(float(viewport_height), 1.0)
    target_half_extent = max(0.1, min(0.99, 1.0 - float(padding)))
    rot = _rotation_matrix(state.pitch, state.yaw, state.roll)
    rotated = points @ rot.T
    f = 1.0 / math.tan(math.radians(FRAME_FIT_FOV_DEG) * 0.5)

    x_limit_denom = (f / max(aspect, 1e-6)) * np.abs(rotated[:, 0]) + target_half_extent * rotated[:, 2]
    y_limit_denom = f * np.abs(rotated[:, 1]) + target_half_extent * rotated[:, 2]
    candidates: list[float] = [float(maximum_zoom)]
    for denom in (x_limit_denom, y_limit_denom):
        valid = denom > 1e-8
        if np.any(valid):
            candidates.append(float(np.min(target_half_extent * float(state.camera_z) / denom[valid])))

    forward = rotated[:, 2] > 1e-8
    if np.any(forward):
        candidates.append(float(np.min((float(state.camera_z) - 0.075) / rotated[forward, 2])))

    fit_zoom = max(float(minimum_zoom), min(float(maximum_zoom), *candidates))
    extent, half_x, half_y = _projected_bounds_half_extent(
        points,
        pitch=state.pitch,
        yaw=state.yaw,
        roll=state.roll,
        zoom=fit_zoom,
        camera_z=state.camera_z,
        aspect=aspect,
    )
    return fit_zoom, {
        "method": "projected_mesh_vertices_analytic",
        "point_count": int(len(points)),
        "viewport": [int(viewport_width), int(viewport_height)],
        "fov_deg": FRAME_FIT_FOV_DEG,
        "padding": float(padding),
        "target_half_extent_ndc": target_half_extent,
        "actual_half_extent_ndc": extent,
        "actual_half_x_ndc": half_x,
        "actual_half_y_ndc": half_y,
        "zoom": fit_zoom,
        "camera_z": float(state.camera_z),
    }


def _fit_zoom_to_projected_bounds(
    mesh_diag: Mapping[str, Any],
    state: GpuState,
    *,
    viewport_width: int,
    viewport_height: int,
    padding: float = DEFAULT_FRAME_FIT_PADDING,
    minimum_zoom: float = 0.1,
    maximum_zoom: float = 8.0,
) -> tuple[float, dict[str, Any]]:
    corners = _normalized_bounds_corners(mesh_diag)
    zoom, diag = _fit_zoom_to_projected_points(
        corners,
        state,
        viewport_width=viewport_width,
        viewport_height=viewport_height,
        padding=padding,
        minimum_zoom=minimum_zoom,
        maximum_zoom=maximum_zoom,
    )
    diag["method"] = "projected_bounds_corners_analytic"
    return zoom, diag


def _screen_pan_delta(
    pixel_delta_x: float,
    pixel_delta_y: float,
    *,
    viewport_width: int,
    viewport_height: int,
    camera_z: float,
    fov_deg: float = FRAME_FIT_FOV_DEG,
) -> tuple[float, float]:
    safe_width = max(float(viewport_width), 1.0)
    safe_height = max(float(viewport_height), 1.0)
    safe_camera_z = max(float(camera_z), 0.05)
    view_height = 2.0 * safe_camera_z * math.tan(math.radians(float(fov_deg)) * 0.5)
    view_width = view_height * (safe_width / safe_height)
    return (
        float(pixel_delta_x) * view_width / safe_width,
        -float(pixel_delta_y) * view_height / safe_height,
    )


def _orthographic(left: float, right: float, bottom: float, top: float, near: float, far: float) -> np.ndarray:
    out = np.eye(4, dtype=np.float32)
    out[0, 0] = 2.0 / max(right - left, 1e-6)
    out[1, 1] = 2.0 / max(top - bottom, 1e-6)
    out[2, 2] = -2.0 / max(far - near, 1e-6)
    out[0, 3] = -(right + left) / max(right - left, 1e-6)
    out[1, 3] = -(top + bottom) / max(top - bottom, 1e-6)
    out[2, 3] = -(far + near) / max(far - near, 1e-6)
    return out


def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    forward = target - eye
    forward = forward / max(float(np.linalg.norm(forward)), 1e-8)
    side = np.cross(forward, up)
    if float(np.linalg.norm(side)) <= 1e-8:
        side = np.cross(forward, np.asarray([0.0, 0.0, 1.0], dtype=np.float32))
    side = side / max(float(np.linalg.norm(side)), 1e-8)
    true_up = np.cross(side, forward)
    out = np.eye(4, dtype=np.float32)
    out[0, :3] = side
    out[1, :3] = true_up
    out[2, :3] = -forward
    out[0, 3] = -float(np.dot(side, eye))
    out[1, 3] = -float(np.dot(true_up, eye))
    out[2, 3] = float(np.dot(forward, eye))
    return out


def _direction_from_azimuth_elevation(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    ce = math.cos(elevation)
    return np.asarray([
        math.cos(azimuth) * ce,
        math.sin(elevation),
        math.sin(azimuth) * ce,
    ], dtype=np.float32)


def _azimuth_elevation_from_direction(direction: np.ndarray) -> tuple[float, float]:
    length = float(np.linalg.norm(direction))
    if length <= 1e-8:
        return 45.0, 45.0
    d = direction / length
    azimuth = math.degrees(math.atan2(float(d[2]), float(d[0])))
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, float(d[1])))))
    return azimuth, elevation


def _material_maps(descriptor: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
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
    geometry_to_model: dict[str, str] = {}
    model_to_material: dict[str, str] = {}
    for connection in descriptor.get("connections", []) or []:
        if not isinstance(connection, Mapping):
            continue
        child = str(connection.get("child") or "")
        parent = str(connection.get("parent") or "")
        if child in geometry_ids:
            geometry_to_model[child] = parent
        if child in material_ids:
            model_to_material[parent] = child
    return geometry_to_model, model_to_material


def _material_for_geometry(descriptor: Mapping[str, Any], geometry: Mapping[str, Any]) -> Mapping[str, Any]:
    material_by_id = {
        str(item.get("id") or ""): item
        for item in descriptor.get("materials", []) or []
        if isinstance(item, Mapping)
    }
    material_id = str(geometry.get("material_id") or "")
    material = material_by_id.get(material_id) if material_id else None
    if isinstance(material, Mapping):
        return material
    geometry_to_model, model_to_material = _material_maps(descriptor)
    model_id = geometry_to_model.get(str(geometry.get("id") or ""), "")
    material_id = model_to_material.get(model_id, "")
    material = material_by_id.get(material_id)
    if not isinstance(material, Mapping):
        materials = descriptor.get("materials", [])
        material = materials[0] if isinstance(materials, list) and materials and isinstance(materials[0], Mapping) else {}
    return material if isinstance(material, Mapping) else {}


def _material_render_queue(material: Mapping[str, Any]) -> int:
    for key in ("mtoon_render_queue", "render_queue"):
        try:
            return int(float(material.get(key)))
        except Exception:
            continue
    alpha_mode = str(material.get("alpha_mode") or "").strip().upper()
    return 3000 if alpha_mode == "BLEND" else 2450 if alpha_mode == "MASK" else 2000


def _material_depth_write(material: Mapping[str, Any]) -> bool:
    if material.get("depth_write") is not None:
        return _metadata_bool(material.get("depth_write"), default=True)
    try:
        return int(float(material.get("mtoon_zwrite"))) != 0
    except Exception:
        pass
    return True


def _material_alpha_bucket(material: Mapping[str, Any]) -> int:
    return 1 if not _material_depth_write(material) else 0


def _metadata_bool(raw: Any, *, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    text = str(raw).strip().casefold()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    try:
        return bool(int(float(text)))
    except Exception:
        return default


def _base_alpha_to_opacity(material_name: str, maps: Mapping[str, Any] | None) -> bool:
    """Return whether a base-color alpha channel should drive transparency.

    Some third-party glTF exports mark regular PBR body materials as BLEND and
    leave packed or noisy alpha in the base-color PNG. Treating that alpha as
    opacity makes the whole mesh see-through. Keep alpha for explicit opacity
    surfaces, alpha-mask materials, MToon ZWrite-off materials, and decal-like
    layers; otherwise render depth-writing PBR base maps as opaque color maps.
    """

    data = maps or {}
    if data.get("base_alpha_to_opacity") is not None:
        return _metadata_bool(data.get("base_alpha_to_opacity"), default=False)
    if data.get("opacity"):
        return True
    alpha_mode = str(data.get("alpha_mode") or "").strip().upper()
    if alpha_mode == "MASK":
        return True
    if data.get("depth_write") is not None and not _metadata_bool(data.get("depth_write"), default=True):
        return True
    try:
        if int(float(data.get("mtoon_zwrite"))) == 0:
            return True
    except Exception:
        pass
    lowered = str(material_name or "").casefold()
    if any(token in lowered for token in ("decal", "sticker", "label")):
        return True
    return False


def _geometry_render_sort_key(descriptor: Mapping[str, Any], geometry: Mapping[str, Any]) -> tuple[int, int]:
    material = _material_for_geometry(descriptor, geometry)
    return (
        _material_alpha_bucket(material),
        _material_render_queue(material),
    )


def _color_for_geometry(descriptor: Mapping[str, Any], geometry: Mapping[str, Any]) -> tuple[float, float, float, float]:
    material = _material_for_geometry(descriptor, geometry)
    raw = material.get("base_color") if isinstance(material, Mapping) else None
    vals = list(raw) if isinstance(raw, (list, tuple)) else [0.95, 0.24, 0.05, 1.0]
    vals += [1.0, 1.0, 1.0, 1.0]
    return tuple(max(0.0, min(1.0, float(v))) for v in vals[:4])  # type: ignore[return-value]


def _material_has_pbr_data(material: Mapping[str, Any]) -> bool:
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
    shader = str(material.get("shader_model") or material.get("source_shader") or "").casefold()
    unlit = bool(material.get("unlit")) or "mtoon" in shader or shader == "unlit"
    return not unlit and ("roughness" in material or "metallic" in material)


def _requested_render_profile(track: Mapping[str, Any] | None) -> str:
    render = track.get("render") if isinstance(track, Mapping) and isinstance(track.get("render"), Mapping) else {}
    value = str(render.get("render_profile") or render.get("ar_pbr_render_profile") or "").strip().casefold()
    return value if value in {PROFILE_AUTHORED, PROFILE_MARMOSET_PBR, PROFILE_VRM_MTOON} else PROFILE_AUTHORED


def _active_render_profile(descriptor: Mapping[str, Any], track: Mapping[str, Any] | None) -> tuple[str, dict[str, Any], str]:
    profiles = inspect_asset_render_profiles_from_descriptor(descriptor)
    requested = _requested_render_profile(track)
    if requested == PROFILE_VRM_MTOON:
        if vrm_mtoon_available(profiles):
            return PROFILE_VRM_MTOON, profiles, ""
        return PROFILE_AUTHORED, profiles, "vrm_mtoon_requested_without_mtoon_materials"
    if requested == PROFILE_MARMOSET_PBR:
        if marmoset_pbr_available(profiles):
            return PROFILE_MARMOSET_PBR, profiles, ""
        return PROFILE_AUTHORED, profiles, "marmoset_pbr_requested_without_pbr_data"
    if requested == PROFILE_AUTHORED and vrm_mtoon_available(profiles):
        return PROFILE_VRM_MTOON, profiles, ""
    return PROFILE_AUTHORED, profiles, ""


def _mtoon_color_policy_for_profile(render_profile: str, ibl_exposure: float) -> tuple[float, float, float]:
    if str(render_profile or "").strip().casefold() == PROFILE_VRM_MTOON:
        return VRM_MTOON_UNLIT_EXPOSURE_SCALE, VRM_MTOON_UNLIT_CONTRAST, VRM_MTOON_UNLIT_GAMMA
    return max(float(ibl_exposure), 0.65), 1.0, DEFAULT_TONE_GAMMA


def _pbr_for_geometry(
    descriptor: Mapping[str, Any],
    geometry: Mapping[str, Any],
    *,
    render_profile: str = PROFILE_AUTHORED,
) -> tuple[float, float, float]:
    material = _material_for_geometry(descriptor, geometry)
    shader = str(material.get("shader_model") or material.get("source_shader") or "").casefold()
    force_pbr = render_profile == PROFILE_MARMOSET_PBR and _material_has_pbr_data(material)
    if (bool(material.get("unlit")) or "mtoon" in shader or shader == "unlit") and not force_pbr:
        return (1.0, 0.0, -1.0)

    def value(name: str, default: float) -> float:
        try:
            return float(material.get(name, default))
        except Exception:
            return default

    return (
        max(0.04, min(1.0, value("roughness", 0.45))),
        max(0.0, min(1.0, value("metallic", 0.0))),
        max(0.0, min(1.0, value("reflectance", 0.5))),
    )


def _descriptor_bounds(descriptor: Mapping[str, Any]) -> tuple[np.ndarray, float]:
    bounds = descriptor.get("bounds") if isinstance(descriptor.get("bounds"), Mapping) else {}
    center = np.asarray(bounds.get("center", [0.0, 0.0, 0.0]), dtype=np.float32)
    size = np.asarray(bounds.get("size", [1.0, 1.0, 1.0]), dtype=np.float32)
    return center, float(max(size.max(initial=1.0), 1e-6))


def _geometry_skin_attribute_arrays(
    geometry: Mapping[str, Any],
    vertex_count: int,
    *,
    max_influences: int = 4,
) -> tuple[np.ndarray, np.ndarray, int]:
    indices = np.zeros((max(0, int(vertex_count)), max_influences), dtype=np.float32)
    weights = np.zeros((max(0, int(vertex_count)), max_influences), dtype=np.float32)
    rows_raw = geometry.get("skin_weights")
    if not isinstance(rows_raw, list) or vertex_count <= 0:
        return indices, weights, 0
    skinned_vertex_count = 0
    for vertex_index in range(min(vertex_count, len(rows_raw))):
        rows = _normalized_skin_rows(rows_raw[vertex_index])
        slot = 0
        for row in rows:
            if slot >= max_influences:
                break
            bone_index = _bone_index_from_skin_row(row)
            weight = _skin_row_weight(row)
            if bone_index < 0 or weight <= 1.0e-8:
                continue
            indices[vertex_index, slot] = float(bone_index)
            weights[vertex_index, slot] = float(max(0.0, min(1.0, weight)))
            slot += 1
        total = float(weights[vertex_index].sum())
        if total > 1.0e-8:
            weights[vertex_index] /= total
            skinned_vertex_count += 1
    return indices, weights, skinned_vertex_count


def _normalized_skin_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        joints = value.get("joints")
        weights = value.get("weights")
        if isinstance(joints, (list, tuple)) and isinstance(weights, (list, tuple)):
            return [
                {"bone_index": joints[idx], "weight": weights[idx] if idx < len(weights) else 0.0}
                for idx in range(len(joints))
            ]
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def _bone_index_from_skin_row(row: Mapping[str, Any]) -> int:
    for key in ("bone_index", "joint", "joint_index"):
        try:
            return int(row[key])
        except Exception:
            pass
    text = str(row.get("bone_id") or row.get("model_id") or "")
    if text.startswith("bone_"):
        try:
            return int(text.split("_", 1)[1])
        except Exception:
            return -1
    try:
        return int(text)
    except Exception:
        return -1


def _skin_row_weight(row: Mapping[str, Any]) -> float:
    try:
        return float(row.get("weight", 0.0) or 0.0)
    except Exception:
        return 0.0


def _geometry_stage_transform(geometry: Mapping[str, Any]) -> dict[str, Any]:
    raw = geometry.get("stage_transform")
    if not isinstance(raw, Mapping) or raw.get("enabled") is False:
        return {
            "enabled": False,
            "center": [0.0, 0.0, 0.0],
            "offset": [0.0, 0.0, 0.0],
            "rotate_y_180": False,
        }
    center = list(raw.get("center") or [0.0, 0.0, 0.0])[:3]
    offset = list(raw.get("offset") or [0.0, 0.0, 0.0])[:3]
    center += [0.0] * (3 - len(center))
    offset += [0.0] * (3 - len(offset))
    try:
        center_out = [float(center[0]), float(center[1]), float(center[2])]
    except Exception:
        center_out = [0.0, 0.0, 0.0]
    try:
        offset_out = [float(offset[0]), float(offset[1]), float(offset[2])]
    except Exception:
        offset_out = [0.0, 0.0, 0.0]
    return {
        "enabled": True,
        "center": center_out,
        "offset": offset_out,
        "rotate_y_180": bool(raw.get("rotate_y_180")),
    }


def _apply_stage_transform_points(vertices: np.ndarray, transform: Mapping[str, Any]) -> np.ndarray:
    if not bool(transform.get("enabled")) or vertices.size <= 0:
        return vertices
    out = np.asarray(vertices, dtype=np.float32).copy()
    center = np.asarray(transform.get("center") or [0.0, 0.0, 0.0], dtype=np.float32)
    offset = np.asarray(transform.get("offset") or [0.0, 0.0, 0.0], dtype=np.float32)
    if center.shape[0] < 3:
        center = np.pad(center, (0, 3 - center.shape[0]))
    if offset.shape[0] < 3:
        offset = np.pad(offset, (0, 3 - offset.shape[0]))
    if bool(transform.get("rotate_y_180")):
        out[:, 0] = center[0] - (out[:, 0] - center[0])
        out[:, 2] = center[2] - (out[:, 2] - center[2])
    out[:, :3] += offset[:3]
    return out


PREVIEW_UV_V_FLIP_MODE = "auto"


def _descriptor_needs_preview_uv_v_flip(descriptor: Mapping[str, Any]) -> bool:
    """Compensate for this preview path's OpenGL texture upload Y flip."""
    fmt = str(descriptor.get("source_format") or "").strip().casefold()
    ext = str(descriptor.get("source_ext") or "").strip().casefold()
    backend = str(descriptor.get("backend") or "").strip().casefold()
    return fmt in {"gltf", "glb"} or ext in {".gltf", ".glb"} or "gltf" in backend


def _preview_uv_v_flip_enabled(descriptor: Mapping[str, Any]) -> bool:
    mode = str(PREVIEW_UV_V_FLIP_MODE or "auto").strip().casefold()
    if mode == "on":
        return True
    if mode == "off":
        return False
    return _descriptor_needs_preview_uv_v_flip(descriptor)


def _material_uv_set(material: Mapping[str, Any]) -> int:
    for key in ("base_uv_set", "uv_set"):
        if key not in material:
            continue
        try:
            return max(0, int(material.get(key) or 0))
        except Exception:
            continue
    return 0


def _geometry_uv_array_for_material(
    geometry: Mapping[str, Any],
    material: Mapping[str, Any],
) -> np.ndarray:
    uv_set = _material_uv_set(material)
    uv_sets = geometry.get("uv_sets")
    raw = None
    if isinstance(uv_sets, Mapping):
        raw = uv_sets.get(str(uv_set))
        if raw is None:
            raw = uv_sets.get(uv_set)  # type: ignore[index]
    if raw is None:
        raw = geometry.get("uvs")
    return np.asarray(raw, dtype=np.float32) if isinstance(raw, list) else np.empty((0, 2), dtype=np.float32)


def _material_uv_transform(material: Mapping[str, Any]) -> Mapping[str, Any] | None:
    transform = material.get("base_uv_transform") or material.get("uv_transform")
    return transform if isinstance(transform, Mapping) else None


def _apply_material_uv_transform(uvs: np.ndarray, transform: Mapping[str, Any] | None) -> np.ndarray:
    if transform is None or uvs.size <= 0:
        return uvs
    out = np.asarray(uvs, dtype=np.float32).copy()
    try:
        scale_raw = transform.get("scale", [1.0, 1.0])
        offset_raw = transform.get("offset", [0.0, 0.0])
        rotation = float(transform.get("rotation", 0.0) or 0.0)
        scale = np.asarray(list(scale_raw)[:2], dtype=np.float32)
        offset = np.asarray(list(offset_raw)[:2], dtype=np.float32)
        if scale.shape != (2,):
            scale = np.asarray([1.0, 1.0], dtype=np.float32)
        if offset.shape != (2,):
            offset = np.asarray([0.0, 0.0], dtype=np.float32)
        if abs(rotation) > 1.0e-8:
            c = math.cos(rotation)
            s = math.sin(rotation)
            rot = np.asarray([[c, -s], [s, c]], dtype=np.float32)
            out = out @ rot.T
        out = out * scale + offset
        return out.astype(np.float32, copy=False)
    except Exception:
        return np.asarray(uvs, dtype=np.float32)


def _face_normals(vertices: np.ndarray, triangles: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    triangle_points = vertices[triangles]
    normals = np.cross(
        triangle_points[:, 1] - triangle_points[:, 0],
        triangle_points[:, 2] - triangle_points[:, 0],
    ).astype(np.float32)
    lengths = np.linalg.norm(normals, axis=1)
    nondegenerate = lengths > 1e-8
    if not np.any(nondegenerate):
        return normals[:0], nondegenerate, 0
    normals = normals[nondegenerate]
    triangles_valid = triangles[nondegenerate]
    centroid = vertices.mean(axis=0) if len(vertices) else np.zeros(3, dtype=np.float32)
    face_centers = vertices[triangles_valid].mean(axis=1)
    flip_mask = np.einsum("ij,ij->i", normals, face_centers - centroid) < 0.0
    normals[flip_mask] *= -1.0
    return normals, nondegenerate, int(np.count_nonzero(flip_mask))


def _smooth_normals(vertices: np.ndarray, triangles: np.ndarray, face_normals: np.ndarray) -> np.ndarray:
    normals = np.zeros_like(vertices, dtype=np.float32)
    repeated = np.repeat(face_normals, 3, axis=0)
    np.add.at(normals, triangles.reshape(-1), repeated)
    lengths = np.linalg.norm(normals, axis=1)
    valid = lengths > 1e-8
    normals[valid] = normals[valid] / lengths[valid, None]
    normals[~valid] = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    return normals


def _compute_tangent_basis(vertices: np.ndarray, triangles: np.ndarray, normals: np.ndarray, uvs: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    tangents = np.zeros_like(vertices, dtype=np.float32)
    bitangents = np.zeros_like(vertices, dtype=np.float32)
    if len(triangles) <= 0 or len(uvs) != len(vertices):
        tangents[:, 0] = 1.0
        bitangents[:, 2] = 1.0
        return tangents, bitangents
    pts = vertices[triangles]
    tri_uvs = uvs[triangles]
    edge1 = pts[:, 1] - pts[:, 0]
    edge2 = pts[:, 2] - pts[:, 0]
    duv1 = tri_uvs[:, 1] - tri_uvs[:, 0]
    duv2 = tri_uvs[:, 2] - tri_uvs[:, 0]
    denom = duv1[:, 0] * duv2[:, 1] - duv1[:, 1] * duv2[:, 0]
    valid = np.abs(denom) > 1e-8
    if np.any(valid):
        inv = np.zeros_like(denom, dtype=np.float32)
        inv[valid] = 1.0 / denom[valid]
        tri_tangents = (edge1 * duv2[:, 1:2] - edge2 * duv1[:, 1:2]) * inv[:, None]
        tri_bitangents = (edge2 * duv1[:, 0:1] - edge1 * duv2[:, 0:1]) * inv[:, None]
        tri_tangents[~valid] = 0.0
        tri_bitangents[~valid] = 0.0
        np.add.at(tangents, triangles.reshape(-1), np.repeat(tri_tangents, 3, axis=0))
        np.add.at(bitangents, triangles.reshape(-1), np.repeat(tri_bitangents, 3, axis=0))
    n = normals.astype(np.float32, copy=False)
    tangents = tangents - n * np.sum(n * tangents, axis=1, keepdims=True)
    tangent_lengths = np.linalg.norm(tangents, axis=1)
    invalid_tangents = tangent_lengths <= 1e-8
    tangents[~invalid_tangents] = tangents[~invalid_tangents] / tangent_lengths[~invalid_tangents, None]
    tangents[invalid_tangents] = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    bitangents = np.cross(n, tangents)
    bitangent_lengths = np.linalg.norm(bitangents, axis=1)
    invalid_bitangents = bitangent_lengths <= 1e-8
    bitangents[~invalid_bitangents] = bitangents[~invalid_bitangents] / bitangent_lengths[~invalid_bitangents, None]
    bitangents[invalid_bitangents] = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    return tangents.astype(np.float32), bitangents.astype(np.float32)


def build_vertex_buffer(
    descriptor: Mapping[str, Any],
    *,
    track: Mapping[str, Any] | None = None,
    time_ms: int = 0,
) -> tuple[np.ndarray, dict[str, Any]]:
    render_profile, render_profiles, render_profile_warning = _active_render_profile(descriptor, track)
    center, max_size = _descriptor_bounds(descriptor)
    chunks: list[np.ndarray] = []
    bounds_chunks: list[np.ndarray] = []
    draw_ranges: list[dict[str, Any]] = []
    geometry_count = 0
    triangle_count = 0
    flipped_normal_count = 0
    skipped_triangle_count = 0
    animated_geometry_count = 0
    skeletal_geometry_count = 0
    gpu_skinning_vertex_count = 0
    animation_clip_count = len(descriptor.get("animation_clips") or []) if isinstance(descriptor, Mapping) else 0
    flip_uv_v_for_texture_upload = _preview_uv_v_flip_enabled(descriptor)
    vertex_start = 0
    geometries = [item for item in descriptor.get("geometries", []) or [] if isinstance(item, Mapping)]
    for geometry in sorted(geometries, key=lambda item: _geometry_render_sort_key(descriptor, item)):
        verts = geometry.get("vertices")
        tris = geometry.get("triangles")
        if not isinstance(verts, list) or not isinstance(tris, list):
            continue
        if geometry.get("skin_weights"):
            skeletal_geometry_count += 1
        if track is not None and animation_clip_count > 0:
            try:
                from app.ar_pbr.animation import animated_vertices_for_geometry

                animated = animated_vertices_for_geometry(
                    verts,
                    geometry=geometry,
                    descriptor=descriptor,
                    track=track,
                    time_ms=int(time_ms),
                )
                if animated is not verts:
                    verts = list(animated)
                    animated_geometry_count += 1
            except Exception:
                pass
        vertices_np = np.asarray(verts, dtype=np.float32)
        triangles_np = np.asarray(tris, dtype=np.int64)
        if vertices_np.ndim != 2 or vertices_np.shape[1] != 3 or triangles_np.ndim != 2 or triangles_np.shape[1] < 3:
            continue
        stage_transform = _geometry_stage_transform(geometry)
        bounds_vertices_np = _apply_stage_transform_points(vertices_np, stage_transform)
        in_range = np.all((triangles_np[:, :3] >= 0) & (triangles_np[:, :3] < len(vertices_np)), axis=1)
        skipped_triangle_count += int(len(triangles_np) - int(np.count_nonzero(in_range)))
        triangles_np = triangles_np[in_range, :3]
        if len(triangles_np) <= 0:
            continue
        face_normals, nondegenerate, flipped = _face_normals(vertices_np, triangles_np)
        skipped_triangle_count += int(len(triangles_np) - int(np.count_nonzero(nondegenerate)))
        triangles_np = triangles_np[nondegenerate]
        if len(triangles_np) <= 0:
            continue
        normals_raw = geometry.get("normals")
        normals_np = np.asarray(normals_raw, dtype=np.float32) if isinstance(normals_raw, list) else np.empty((0, 3), dtype=np.float32)
        if normals_np.ndim == 2 and normals_np.shape == vertices_np.shape and np.linalg.norm(normals_np, axis=1).max(initial=0.0) > 1e-8:
            normal_lengths = np.linalg.norm(normals_np, axis=1)
            valid_normals = normal_lengths > 1e-8
            normals_np[valid_normals] = normals_np[valid_normals] / normal_lengths[valid_normals, None]
            smooth_normals = normals_np
            normal_mode = "fbx_layer_normals"
        else:
            smooth_normals = _smooth_normals(vertices_np, triangles_np, face_normals)
            normal_mode = "smooth_center_oriented"
        flipped_normal_count += flipped
        color = _color_for_geometry(descriptor, geometry)
        pbr = _pbr_for_geometry(descriptor, geometry, render_profile=render_profile)
        material = _material_for_geometry(descriptor, geometry)
        material_name = str(material.get("name") or "")
        material_alpha_mode = str(material.get("alpha_mode") or "").strip().upper()
        material_depth_write = _material_depth_write(material)
        material_uv_set = _material_uv_set(material)
        geometry_count += 1
        points = ((vertices_np[triangles_np] - center) / max_size).astype(np.float32)
        bounds_points = ((bounds_vertices_np[triangles_np] - center) / max_size).astype(np.float32)
        bounds_chunks.append(bounds_points.reshape(-1, 3))
        normals = smooth_normals[triangles_np].astype(np.float32)
        uvs_np = _geometry_uv_array_for_material(geometry, material)
        if uvs_np.ndim == 2 and len(uvs_np) == len(vertices_np) and uvs_np.shape[1] >= 2:
            compact_uvs = uvs_np[:, :2].astype(np.float32)
            compact_uvs = _apply_material_uv_transform(compact_uvs, _material_uv_transform(material))
            if flip_uv_v_for_texture_upload:
                compact_uvs = compact_uvs.copy()
                compact_uvs[:, 1] = 1.0 - compact_uvs[:, 1]
            uvs = compact_uvs[triangles_np, :2].astype(np.float32)
        else:
            uvs = np.zeros((len(triangles_np), 3, 2), dtype=np.float32)
            compact_uvs = np.zeros((len(vertices_np), 2), dtype=np.float32)
        tangents_np, bitangents_np = _compute_tangent_basis(vertices_np, triangles_np, smooth_normals, compact_uvs)
        tangents = tangents_np[triangles_np].astype(np.float32)
        bitangents = bitangents_np[triangles_np].astype(np.float32)
        skin_indices_np, skin_weights_np, skinned_vertices = _geometry_skin_attribute_arrays(geometry, len(vertices_np))
        gpu_skinning_vertex_count += int(skinned_vertices)
        skin_indices = skin_indices_np[triangles_np].astype(np.float32)
        skin_weights = skin_weights_np[triangles_np].astype(np.float32)
        colors = np.empty((len(triangles_np), 3, 4), dtype=np.float32)
        colors[:] = np.asarray(color, dtype=np.float32)
        materials = np.empty((len(triangles_np), 3, 3), dtype=np.float32)
        materials[:] = np.asarray(pbr, dtype=np.float32)
        chunk = np.concatenate(
            [points, normals, colors, materials, uvs, tangents, bitangents, skin_indices, skin_weights],
            axis=2,
        ).reshape(-1, GPU_VERTEX_STRIDE_FLOAT_COUNT)
        chunks.append(chunk)
        chunk_vertex_count = int(len(chunk))
        draw_ranges.append({
            "start": vertex_start,
            "count": chunk_vertex_count,
            "geometry_name": str(geometry.get("name") or ""),
            "material_name": material_name,
            "normal_mode": normal_mode,
            "has_uvs": bool(np.any(uvs != 0.0)),
            "uv_set": int(material_uv_set),
            "uv_v_flipped_for_texture_upload": bool(flip_uv_v_for_texture_upload),
            "alpha_mode": material_alpha_mode,
            "depth_write": bool(material_depth_write),
            "render_queue": int(_material_render_queue(material)),
            "shader_model": str(material.get("shader_model") or material.get("source_shader") or ""),
            "stage_transform_enabled": bool(stage_transform.get("enabled")),
            "stage_rotate_y_180": bool(stage_transform.get("rotate_y_180")),
            "stage_center": list(stage_transform.get("center") or [0.0, 0.0, 0.0]),
            "stage_offset": list(stage_transform.get("offset") or [0.0, 0.0, 0.0]),
        })
        vertex_start += chunk_vertex_count
        triangle_count += int(len(triangles_np))
    if not chunks:
        chunks = [np.asarray([
            [-0.5, -0.5, 0.0, 0.0, 0.0, 1.0, 0.95, 0.24, 0.05, 1.0, 0.45, 0.0, 0.5, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.5, -0.5, 0.0, 0.0, 0.0, 1.0, 0.95, 0.24, 0.05, 1.0, 0.45, 0.0, 0.5, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.5, 0.0, 0.0, 0.0, 1.0, 0.95, 0.24, 0.05, 1.0, 0.45, 0.0, 0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ], dtype=np.float32)]
        draw_ranges = [{"start": 0, "count": 3, "geometry_name": "fallback", "material_name": "", "normal_mode": "fallback", "has_uvs": True}]
    arr = np.ascontiguousarray(np.concatenate(chunks, axis=0), dtype=np.float32)
    xyz = np.concatenate(bounds_chunks, axis=0) if bounds_chunks else (arr[:, :3] if len(arr) else np.zeros((0, 3), dtype=np.float32))
    min_xyz = xyz.min(axis=0).tolist() if len(xyz) else [-0.5, -0.5, -0.5]
    max_xyz = xyz.max(axis=0).tolist() if len(xyz) else [0.5, 0.5, 0.5]
    return arr, {
        "vertex_count": int(len(arr)),
        "triangle_count": int(len(arr) // 3),
        "geometry_count": geometry_count,
        "normal_mode": "fbx_layer_normals_or_smooth",
        "vertex_stride_float_count": GPU_VERTEX_STRIDE_FLOAT_COUNT,
        "shading_model": "hdr_ibl_pbr_textured_normal_mapped_shadow_mapped",
        "flipped_normal_count": int(flipped_normal_count),
        "skipped_triangle_count": int(skipped_triangle_count),
        "animation_clip_count": int(animation_clip_count),
        "animated_geometry_count": int(animated_geometry_count),
        "skeletal_geometry_count": int(skeletal_geometry_count),
        "gpu_skinning_vertex_count": int(gpu_skinning_vertex_count),
        "gpu_skinning_bone_count": len(descriptor.get("bones") or []) if isinstance(descriptor, Mapping) else 0,
        "gpu_skinning_available": bool(gpu_skinning_vertex_count > 0 and len(descriptor.get("bones") or []) > 0 if isinstance(descriptor, Mapping) else False),
        "skeletal_animation_applied": bool(animated_geometry_count > 0 and skeletal_geometry_count > 0),
        "descriptor_center": center.astype(float).tolist(),
        "descriptor_max_size": float(max_size),
        "render_profile": render_profile,
        "render_profiles": render_profiles,
        "mtoon_color_policy": (
            {
                "unlit_exposure_scale": VRM_MTOON_UNLIT_EXPOSURE_SCALE,
                "unlit_contrast": VRM_MTOON_UNLIT_CONTRAST,
                "unlit_gamma": VRM_MTOON_UNLIT_GAMMA,
            }
            if render_profile == PROFILE_VRM_MTOON
            else {}
        ),
        "warnings": [render_profile_warning] if render_profile_warning else [],
        "normalized_bounds": {"min": min_xyz, "max": max_xyz},
        "uv_v_flipped_for_texture_upload": bool(flip_uv_v_for_texture_upload),
        "draw_ranges": draw_ranges,
    }


def _load_hdri_or_none(path: Path | None) -> tuple[HdrImage | None, dict[str, Any]]:
    if path is None:
        return None, {"enabled": False, "reason": "disabled"}
    if not path.exists():
        return None, {"enabled": False, "path": str(path), "reason": "missing"}
    try:
        raw_image = load_radiance_hdr(path)
        raw_stats = image_stats(raw_image)
        key_light = _estimate_hdri_key_light(raw_image)
        image, preview_diag = _stabilize_hdri_for_preview(raw_image)
        stats = image_stats(image)
        return image, {
            "enabled": True,
            **stats,
            "raw_max_luminance": raw_stats["max_luminance"],
            "raw_mean_luminance": raw_stats["mean_luminance"],
            **key_light,
            **preview_diag,
        }
    except Exception as exc:
        return None, {
            "enabled": False,
            "path": str(path),
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _estimate_hdri_key_light(image: HdrImage) -> dict[str, Any]:
    pixels = image.pixels
    luminance = pixels[:, :, 0] * 0.2126 + pixels[:, :, 1] * 0.7152 + pixels[:, :, 2] * 0.0722
    if luminance.size <= 0 or float(luminance.max(initial=0.0)) <= 0.0:
        return {
            "key_light_source": "fallback",
            "key_light_azimuth": 45.0,
            "key_light_elevation": 45.0,
            "key_light_direction": [0.5, 0.707, 0.5],
        }
    threshold = max(float(np.quantile(luminance, 0.9995)), float(luminance.max()) * 0.08)
    mask = luminance >= threshold
    if int(np.count_nonzero(mask)) < 4:
        threshold = float(np.quantile(luminance, 0.999))
        mask = luminance >= threshold
    yy, xx = np.nonzero(mask)
    if len(xx) <= 0:
        direction = _direction_from_azimuth_elevation(45.0, 45.0)
        azimuth, elevation = _azimuth_elevation_from_direction(direction)
        return {
            "key_light_source": "fallback",
            "key_light_azimuth": azimuth,
            "key_light_elevation": elevation,
            "key_light_direction": direction.tolist(),
        }
    u = (xx.astype(np.float32) + 0.5) / max(float(image.width), 1.0)
    v = (yy.astype(np.float32) + 0.5) / max(float(image.height), 1.0)
    theta = (u - 0.5) * (2.0 * math.pi)
    elevation_rad = (0.5 - v) * math.pi
    ce = np.cos(elevation_rad)
    dirs = np.stack([
        np.cos(theta) * ce,
        np.sin(elevation_rad),
        np.sin(theta) * ce,
    ], axis=1).astype(np.float32)
    weights = luminance[mask].astype(np.float32)
    weights *= np.maximum(0.05, ce.astype(np.float32))
    direction = np.sum(dirs * weights[:, None], axis=0)
    length = float(np.linalg.norm(direction))
    if length <= 1e-8:
        direction = _direction_from_azimuth_elevation(45.0, 45.0)
    else:
        direction = direction / length
    azimuth, elevation = _azimuth_elevation_from_direction(direction)
    return {
        "key_light_source": "hdri_luminance_peak",
        "key_light_threshold": threshold,
        "key_light_pixel_count": int(len(xx)),
        "key_light_azimuth": float(azimuth),
        "key_light_elevation": float(elevation),
        "key_light_direction": [float(v) for v in direction.tolist()],
    }


def _stabilize_hdri_for_preview(image: HdrImage) -> tuple[HdrImage, dict[str, Any]]:
    pixels = image.pixels.astype(np.float32, copy=True)
    luminance = pixels[:, :, 0] * 0.2126 + pixels[:, :, 1] * 0.7152 + pixels[:, :, 2] * 0.0722
    if luminance.size <= 0:
        return image, {"preview_processing": "none_empty"}
    q999 = float(np.quantile(luminance, 0.999))
    q9999 = float(np.quantile(luminance, 0.9999))
    highlight_cap = max(8.0, q999 * 8.0)
    scale = min(1.0, 1.4 / max(float(np.quantile(luminance, 0.99)), 1e-6))
    luminance_safe = np.maximum(luminance, 1e-6)
    compression = np.minimum(1.0, highlight_cap / luminance_safe)
    pixels *= (compression * scale)[:, :, None]
    return (
        HdrImage(
            pixels=np.ascontiguousarray(pixels, dtype=np.float32),
            width=image.width,
            height=image.height,
            path=image.path,
            format=image.format,
        ),
        {
            "preview_processing": "percentile_highlight_compression",
            "preview_luminance_q999": q999,
            "preview_luminance_q9999": q9999,
            "preview_highlight_cap": highlight_cap,
            "preview_exposure_scale": scale,
        },
    )


def _find_texture(files: Mapping[str, Path], required: tuple[str, ...]) -> str | None:
    for name, path in files.items():
        if all(part in name for part in required):
            return str(path)
    return None


def _resolve_material_texture_plan(asset: Path, descriptor: Mapping[str, Any]) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    from app.ar_pbr.texture_plan import resolve_material_texture_plan

    return resolve_material_texture_plan(asset, descriptor)


def _channel_index(raw: Any) -> int:
    text = str(raw or "").strip().casefold()
    aliases = {
        "r": 0,
        "red": 0,
        "0": 0,
        "g": 1,
        "green": 1,
        "1": 1,
        "b": 2,
        "blue": 2,
        "2": 2,
        "a": 3,
        "alpha": 3,
        "3": 3,
    }
    return aliases.get(text, 0)


def _material_float(
    maps: Mapping[str, Any] | None,
    key: str,
    default: float,
    *,
    lo: float = 0.0,
    hi: float = 1.0,
) -> float:
    try:
        value = float((maps or {}).get(key, default))
    except Exception:
        value = float(default)
    return max(float(lo), min(float(hi), float(value)))


def _material_vec3(
    maps: Mapping[str, Any] | None,
    key: str,
    default: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[float, float, float]:
    raw = (maps or {}).get(key)
    if isinstance(raw, (list, tuple)):
        parts = list(raw)
    else:
        text = str(raw or "").strip()
        parts = text.replace(";", ",").split(",") if text else []
    values: list[float] = []
    for idx in range(3):
        try:
            values.append(max(0.0, min(16.0, float(parts[idx]))))
        except Exception:
            values.append(float(default[idx]))
    return (values[0], values[1], values[2])


def _bleed_transparent_rgb(rgba: np.ndarray, *, passes: int = 32) -> np.ndarray:
    alpha = rgba[:, :, 3]
    missing = alpha == 0
    if not bool(missing.any()):
        return rgba
    out = rgba.copy()
    valid = alpha > 0
    h, w = alpha.shape
    for _ in range(max(1, int(passes))):
        missing = ~valid
        if not bool(missing.any()):
            break
        padded_rgb = np.pad(out[:, :, :3], ((1, 1), (1, 1), (0, 0)), mode="edge")
        padded_valid = np.pad(valid, ((1, 1), (1, 1)), mode="constant", constant_values=False)
        rgb_sum = np.zeros((h, w, 3), dtype=np.uint32)
        count = np.zeros((h, w), dtype=np.uint32)
        for y in range(3):
            for x in range(3):
                if x == 1 and y == 1:
                    continue
                neighbor_valid = padded_valid[y : y + h, x : x + w]
                rgb_sum += padded_rgb[y : y + h, x : x + w].astype(np.uint32) * neighbor_valid[:, :, None]
                count += neighbor_valid.astype(np.uint32)
        fill = missing & (count > 0)
        if not bool(fill.any()):
            break
        out_rgb = out[:, :, :3]
        out_rgb[fill] = (rgb_sum[fill] // count[fill][:, None]).astype(np.uint8)
        valid[fill] = True
    return out


def _upload_texture_2d(path: str, *, scalar: bool, max_size: int, channel: Any = None) -> int:
    from OpenGL import GL
    from PIL import Image

    image = Image.open(path)
    if max(image.size) > max_size > 0:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    if scalar:
        rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        data = np.ascontiguousarray(rgba[:, :, _channel_index(channel)])
        internal_format = getattr(GL, "GL_R8", 0x8229)
        pixel_format = getattr(GL, "GL_RED", 0x1903)
        has_cutout_alpha = False
    else:
        image = image.convert("RGBA")
        rgba = np.asarray(image, dtype=np.uint8)
        has_cutout_alpha = bool((rgba[:, :, 3] < 250).any())
        if has_cutout_alpha:
            rgba = _bleed_transparent_rgb(rgba)
        data = np.ascontiguousarray(rgba)
        internal_format = GL.GL_RGBA8
        pixel_format = GL.GL_RGBA
    texture_id = int(GL.glGenTextures(1))
    GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
    GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
    GL.glTexParameteri(
        GL.GL_TEXTURE_2D,
        GL.GL_TEXTURE_MIN_FILTER,
        GL.GL_LINEAR if has_cutout_alpha else GL.GL_LINEAR_MIPMAP_LINEAR,
    )
    GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glTexImage2D(
        GL.GL_TEXTURE_2D,
        0,
        internal_format,
        int(image.width),
        int(image.height),
        0,
        pixel_format,
        GL.GL_UNSIGNED_BYTE,
        data,
    )
    if not has_cutout_alpha:
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
    GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
    return texture_id


class GpuMeshWidget(QOpenGLWidget):
    def __init__(
        self,
        vertices: np.ndarray,
        state: GpuState,
        hdri: HdrImage | None,
        mesh_diag: Mapping[str, Any],
        texture_plan: Mapping[str, Mapping[str, str]],
        texture_max_size: int,
        enable_shadow_map: bool,
        fit_padding: float,
        show_environment_background: bool = False,
        transparent_background: bool = False,
        draw_ground: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.vertices = vertices
        self.state = state
        self.hdri = hdri
        self.mesh_diag = mesh_diag
        self.draw_ranges = list(mesh_diag.get("draw_ranges") or [{"start": 0, "count": int(len(vertices)), "material_name": ""}])
        self.texture_plan = texture_plan
        self.texture_max_size = int(texture_max_size)
        self.enable_shadow_map = bool(enable_shadow_map)
        self.fit_padding = float(fit_padding)
        self.show_environment_background = bool(show_environment_background)
        self.transparent_background = bool(transparent_background)
        self.draw_ground = bool(draw_ground)
        self.auto_fit_enabled = True
        self.auto_fit_pending = True
        self.last_fit_diag: dict[str, Any] = {}
        self.program = 0
        self.vbo = 0
        self.vao = 0
        self.environment_program = 0
        self.environment_vao = 0
        self.post_bloom_program = 0
        self.bloom_blur_program = 0
        self.post_bloom_vao = 0
        self.scene_fbo = 0
        self.scene_color_texture = 0
        self.scene_bloom_texture = 0
        self.bloom_blur_fbo_a = 0
        self.bloom_blur_fbo_b = 0
        self.bloom_blur_texture_a = 0
        self.bloom_blur_texture_b = 0
        self.bloom_blur_fbo_size: tuple[int, int] = (0, 0)
        self.scene_depth_renderbuffer = 0
        self.scene_fbo_size: tuple[int, int] = (0, 0)
        self.hdri_texture = 0
        self.hdri_max_lod = 0.0
        self.ibl_irradiance_texture = 0
        self.ibl_prefilter_texture = 0
        self.ibl_brdf_lut_texture = 0
        self.ibl_prefilter_level_count = 0
        self.ibl_probe_diag: dict[str, Any] = {"available": False}
        self.material_textures: dict[str, dict[str, int]] = {}
        self._vbo_size_bytes = 0
        self.depth_program = 0
        self.ground_program = 0
        self.shadow_fbo = 0
        self.shadow_texture = 0
        self.shadow_qt_fbo = None
        self.shadow_size = int(DEFAULT_SHADOW_MAP_SIZE)
        self.shadow_supported = False
        self.shadow_error = ""
        self._shadow_dirty = True
        self._last_shadow_signature: tuple[object, ...] | None = None
        self._uniform_locations: dict[tuple[int, str], int] = {}
        self.skinning_matrices: np.ndarray | None = None
        self.skinning_diag: dict[str, Any] = {}
        self.ground_vao = 0
        self.ground_vbo = 0
        self.last_pos = None
        self.drag_mode = ""
        self.setMinimumSize(760, 520)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Left-drag to orbit. Right/middle-drag or Shift-drag to pan. Mouse wheel zooms.")

    @staticmethod
    def _delete_gl_texture(texture_id: int) -> None:
        if not int(texture_id or 0):
            return
        try:
            from OpenGL import GL

            try:
                GL.glDeleteTextures(1, [int(texture_id)])
            except TypeError:
                GL.glDeleteTextures([int(texture_id)])
        except Exception:
            pass

    @staticmethod
    def _delete_gl_framebuffer(framebuffer_id: int) -> None:
        if not int(framebuffer_id or 0):
            return
        try:
            from OpenGL import GL

            try:
                GL.glDeleteFramebuffers(1, [int(framebuffer_id)])
            except TypeError:
                GL.glDeleteFramebuffers([int(framebuffer_id)])
        except Exception:
            pass

    @staticmethod
    def _delete_gl_renderbuffer(renderbuffer_id: int) -> None:
        if not int(renderbuffer_id or 0):
            return
        try:
            from OpenGL import GL

            try:
                GL.glDeleteRenderbuffers(1, [int(renderbuffer_id)])
            except TypeError:
                GL.glDeleteRenderbuffers([int(renderbuffer_id)])
        except Exception:
            pass

    def _uniform_location(self, program: int, name: str) -> int:
        """Cache uniform lookups; PyOpenGL calls are measurable during drags."""
        key = (int(program or 0), str(name))
        cached = self._uniform_locations.get(key)
        if cached is not None:
            return int(cached)
        from OpenGL import GL

        loc = int(GL.glGetUniformLocation(int(program or 0), str(name)))
        self._uniform_locations[key] = loc
        return loc

    def _invalidate_shadow_cache(self) -> None:
        self._shadow_dirty = True

    @staticmethod
    def _rounded(value: float, digits: int = 5) -> float:
        try:
            return round(float(value), int(digits))
        except Exception:
            return 0.0

    def _shadow_signature(self) -> tuple[object, ...]:
        ranges = tuple(
            (
                int(row.get("start", 0) or 0),
                int(row.get("count", 0) or 0),
                bool(row.get("depth_write", True)),
            )
            for row in self.draw_ranges
        )
        return (
            int(self._vbo_size_bytes or 0),
            int(self.shadow_size or 0),
            ranges,
            self._rounded(self.state.pitch),
            self._rounded(self.state.yaw),
            self._rounded(self.state.roll),
            self._rounded(self.state.zoom),
            self._rounded(self.state.pan_x),
            self._rounded(self.state.pan_y),
            self._rounded(self.state.pan_z),
            self._rounded(self.state.light_azimuth),
            self._rounded(self.state.light_elevation),
            self._rounded(self.state.ibl_rotation),
            str(self.state.shadow_light_type),
            self._rounded(self.state.shadow_spot_inner_angle),
            self._rounded(self.state.shadow_spot_outer_angle),
        )

    def _mark_shadow_clean(self, signature: tuple[object, ...]) -> None:
        self._last_shadow_signature = signature
        self._shadow_dirty = False

    def shadow_diagnostics(self) -> dict[str, Any]:
        return shadow_filter_diagnostics(
            self.state,
            enable_shadow_map=self.enable_shadow_map,
            shadow_supported=self.shadow_supported,
            shadow_size=self.shadow_size,
            shadow_error=self.shadow_error,
            shadow_backend="qt_color_depth" if self.shadow_qt_fbo is not None else "raw_depth_texture",
        )

    def ibl_diagnostics(self) -> dict[str, Any]:
        return {
            **dict(self.ibl_probe_diag or {}),
            "gl_irradiance_texture": bool(self.ibl_irradiance_texture),
            "gl_prefilter_texture": bool(self.ibl_prefilter_texture),
            "gl_brdf_lut_texture": bool(self.ibl_brdf_lut_texture),
            "gl_prefilter_level_count": int(self.ibl_prefilter_level_count or 0),
        }

    def unlit_color_controls(self) -> dict[str, float]:
        scale, contrast, gamma = _mtoon_color_policy_for_profile(
            str(self.mesh_diag.get("render_profile") or PROFILE_AUTHORED),
            float(self.state.ibl_exposure),
        )
        return {
            "unlit_exposure_scale": float(scale),
            "unlit_contrast": float(contrast),
            "unlit_output_gamma": float(gamma),
        }

    def fit_current_view(self) -> dict[str, Any]:
        zoom, diag = _fit_zoom_to_projected_bounds(
            self.mesh_diag,
            self.state,
            viewport_width=max(1, self.width()),
            viewport_height=max(1, self.height()),
            padding=self.fit_padding,
            minimum_zoom=0.1,
            maximum_zoom=8.0,
        )
        self.state.zoom = float(zoom)
        self.last_fit_diag = diag
        return diag

    def _framebuffer_size(self) -> tuple[int, int]:
        dpr = max(float(self.devicePixelRatioF()), 1.0)
        return (
            max(1, int(round(self.width() * dpr))),
            max(1, int(round(self.height() * dpr))),
        )

    def _bind_default_framebuffer(self) -> None:
        from OpenGL import GL

        default_fbo = 0
        try:
            default_fbo = int(self.defaultFramebufferObject())
        except Exception:
            default_fbo = 0
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, default_fbo)
        try:
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0 if default_fbo else GL.GL_BACK)
        except Exception:
            pass

    @staticmethod
    def _set_scene_draw_buffers() -> None:
        from OpenGL import GL

        buffers = [GL.GL_COLOR_ATTACHMENT0, GL.GL_COLOR_ATTACHMENT1]
        try:
            GL.glDrawBuffers(len(buffers), buffers)
        except TypeError:
            GL.glDrawBuffers(buffers)

    def _delete_scene_fbo(self) -> None:
        self._delete_gl_framebuffer(self.scene_fbo)
        self._delete_gl_texture(self.scene_color_texture)
        self._delete_gl_texture(self.scene_bloom_texture)
        self._delete_gl_framebuffer(self.bloom_blur_fbo_a)
        self._delete_gl_framebuffer(self.bloom_blur_fbo_b)
        self._delete_gl_texture(self.bloom_blur_texture_a)
        self._delete_gl_texture(self.bloom_blur_texture_b)
        self._delete_gl_renderbuffer(self.scene_depth_renderbuffer)
        self.scene_fbo = 0
        self.scene_color_texture = 0
        self.scene_bloom_texture = 0
        self.bloom_blur_fbo_a = 0
        self.bloom_blur_fbo_b = 0
        self.bloom_blur_texture_a = 0
        self.bloom_blur_texture_b = 0
        self.bloom_blur_fbo_size = (0, 0)
        self.scene_depth_renderbuffer = 0
        self.scene_fbo_size = (0, 0)

    def _ensure_bloom_blur_fbo(self, width: int, height: int) -> bool:
        from OpenGL import GL

        width = max(1, int(width) // 2)
        height = max(1, int(height) // 2)
        if (
            int(self.bloom_blur_fbo_a or 0)
            and int(self.bloom_blur_fbo_b or 0)
            and int(self.bloom_blur_texture_a or 0)
            and int(self.bloom_blur_texture_b or 0)
            and self.bloom_blur_fbo_size == (width, height)
        ):
            return True
        for fbo_id in (self.bloom_blur_fbo_a, self.bloom_blur_fbo_b):
            self._delete_gl_framebuffer(fbo_id)
        for texture_id in (self.bloom_blur_texture_a, self.bloom_blur_texture_b):
            self._delete_gl_texture(texture_id)
        self.bloom_blur_fbo_a = self.bloom_blur_fbo_b = 0
        self.bloom_blur_texture_a = self.bloom_blur_texture_b = 0
        self.bloom_blur_fbo_size = (0, 0)
        try:
            self.bloom_blur_fbo_a = int(GL.glGenFramebuffers(1))
            self.bloom_blur_fbo_b = int(GL.glGenFramebuffers(1))
            self.bloom_blur_texture_a = int(GL.glGenTextures(1))
            self.bloom_blur_texture_b = int(GL.glGenTextures(1))
            for fbo_id, texture_id in (
                (self.bloom_blur_fbo_a, self.bloom_blur_texture_a),
                (self.bloom_blur_fbo_b, self.bloom_blur_texture_b),
            ):
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D,
                    0,
                    getattr(GL, "GL_RGBA16F", 0x881A),
                    width,
                    height,
                    0,
                    GL.GL_RGBA,
                    GL.GL_FLOAT,
                    None,
                )
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo_id)
                GL.glFramebufferTexture2D(
                    GL.GL_FRAMEBUFFER,
                    GL.GL_COLOR_ATTACHMENT0,
                    GL.GL_TEXTURE_2D,
                    texture_id,
                    0,
                )
                try:
                    GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
                except Exception:
                    pass
                status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
                if status != GL.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError(f"bloom blur framebuffer incomplete: {status}")
            self.bloom_blur_fbo_size = (width, height)
            return True
        except Exception:
            for fbo_id in (self.bloom_blur_fbo_a, self.bloom_blur_fbo_b):
                self._delete_gl_framebuffer(fbo_id)
            for texture_id in (self.bloom_blur_texture_a, self.bloom_blur_texture_b):
                self._delete_gl_texture(texture_id)
            self.bloom_blur_fbo_a = self.bloom_blur_fbo_b = 0
            self.bloom_blur_texture_a = self.bloom_blur_texture_b = 0
            self.bloom_blur_fbo_size = (0, 0)
            return False
        finally:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def _ensure_scene_fbo(self, width: int, height: int) -> bool:
        from OpenGL import GL

        width = max(1, int(width))
        height = max(1, int(height))
        if (
            int(self.scene_fbo or 0)
            and int(self.scene_color_texture or 0)
            and int(self.scene_bloom_texture or 0)
            and int(self.scene_depth_renderbuffer or 0)
            and self.scene_fbo_size == (width, height)
        ):
            return True

        self._delete_scene_fbo()
        try:
            self.scene_fbo = int(GL.glGenFramebuffers(1))
            self.scene_color_texture = int(GL.glGenTextures(1))
            self.scene_bloom_texture = int(GL.glGenTextures(1))
            self.scene_depth_renderbuffer = int(GL.glGenRenderbuffers(1))

            for texture_id, internal_format, pixel_type in (
                (self.scene_color_texture, GL.GL_RGBA8, GL.GL_UNSIGNED_BYTE),
                (self.scene_bloom_texture, getattr(GL, "GL_RGBA16F", 0x881A), GL.GL_FLOAT),
            ):
                GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D,
                    0,
                    internal_format,
                    width,
                    height,
                    0,
                    GL.GL_RGBA,
                    pixel_type,
                    None,
                )

            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, self.scene_depth_renderbuffer)
            GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT24, width, height)

            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.scene_fbo)
            GL.glFramebufferTexture2D(
                GL.GL_FRAMEBUFFER,
                GL.GL_COLOR_ATTACHMENT0,
                GL.GL_TEXTURE_2D,
                self.scene_color_texture,
                0,
            )
            GL.glFramebufferTexture2D(
                GL.GL_FRAMEBUFFER,
                GL.GL_COLOR_ATTACHMENT1,
                GL.GL_TEXTURE_2D,
                self.scene_bloom_texture,
                0,
            )
            GL.glFramebufferRenderbuffer(
                GL.GL_FRAMEBUFFER,
                GL.GL_DEPTH_ATTACHMENT,
                GL.GL_RENDERBUFFER,
                self.scene_depth_renderbuffer,
            )
            self._set_scene_draw_buffers()
            status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
            if status != GL.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"scene framebuffer incomplete: {status}")
            self.scene_fbo_size = (width, height)
            return True
        except Exception:
            self._delete_scene_fbo()
            return False
        finally:
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, 0)

    def initializeGL(self) -> None:
        from OpenGL import GL

        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        self.program = self._create_program()
        self.environment_program = self._create_program(ENV_VERT_SHADER, ENV_FRAG_SHADER)
        self.environment_vao = GL.glGenVertexArrays(1)
        self.bloom_blur_program = self._create_program(POST_BLOOM_VERT_SHADER, BLOOM_BLUR_FRAG_SHADER)
        self.post_bloom_program = self._create_program(POST_BLOOM_VERT_SHADER, POST_BLOOM_FRAG_SHADER)
        self.post_bloom_vao = GL.glGenVertexArrays(1)
        self.depth_program = self._create_program(DEPTH_VERT_SHADER, DEPTH_FRAG_SHADER)
        self.ground_program = self._create_program(GROUND_VERT_SHADER, GROUND_FRAG_SHADER)
        self._upload_hdri()
        self._upload_ibl_probe()
        self._upload_material_textures()
        if self.enable_shadow_map:
            self._create_shadow_resources()
        self._create_ground_geometry()
        self.vao = GL.glGenVertexArrays(1)
        self.vbo = GL.glGenBuffers(1)
        GL.glBindVertexArray(self.vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL.GL_STATIC_DRAW)
        self._vbo_size_bytes = int(self.vertices.nbytes)
        self._configure_mesh_vertex_attributes()
        GL.glBindVertexArray(0)

    def _configure_mesh_vertex_attributes(self) -> None:
        from OpenGL import GL

        stride_float_count = int(self.mesh_diag.get("vertex_stride_float_count") or GPU_VERTEX_STRIDE_FLOAT_COUNT)
        stride = max(GPU_VERTEX_BASE_STRIDE_FLOAT_COUNT, stride_float_count) * 4
        specs = (
            (0, 3, 0),
            (1, 3, 12),
            (2, 4, 24),
            (3, 3, 40),
            (4, 2, 52),
            (5, 3, 60),
            (6, 3, 72),
        )
        for location, size, offset in specs:
            GL.glEnableVertexAttribArray(location)
            GL.glVertexAttribPointer(location, size, GL.GL_FLOAT, False, stride, ctypes.c_void_p(offset))
        if stride_float_count >= GPU_VERTEX_STRIDE_FLOAT_COUNT:
            GL.glEnableVertexAttribArray(7)
            GL.glVertexAttribPointer(7, 4, GL.GL_FLOAT, False, stride, ctypes.c_void_p(84))
            GL.glEnableVertexAttribArray(8)
            GL.glVertexAttribPointer(8, 4, GL.GL_FLOAT, False, stride, ctypes.c_void_p(100))
        else:
            for location in (7, 8):
                GL.glDisableVertexAttribArray(location)

    def replace_vertices(self, vertices: np.ndarray, mesh_diag: Mapping[str, Any]) -> None:
        """Replace animated vertex data without rebuilding programs/textures."""
        self.vertices = np.ascontiguousarray(vertices, dtype=np.float32)
        self.mesh_diag = mesh_diag
        self.draw_ranges = list(mesh_diag.get("draw_ranges") or [{"start": 0, "count": int(len(self.vertices)), "material_name": ""}])
        if not int(self.vbo or 0):
            return
        from OpenGL import GL

        self.makeCurrent()
        try:
            GL.glBindVertexArray(self.vao)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
            if int(self.vertices.nbytes) <= int(self._vbo_size_bytes or 0):
                GL.glBufferSubData(GL.GL_ARRAY_BUFFER, 0, int(self.vertices.nbytes), self.vertices)
            else:
                GL.glBufferData(GL.GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL.GL_DYNAMIC_DRAW)
                self._vbo_size_bytes = int(self.vertices.nbytes)
            self._configure_mesh_vertex_attributes()
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
            GL.glBindVertexArray(0)
        finally:
            self.doneCurrent()
        self._invalidate_shadow_cache()
        self.update()

    def _create_shadow_resources(self) -> None:
        from OpenGL import GL

        self._invalidate_shadow_cache()
        self.shadow_supported = False
        self.shadow_error = ""
        self.shadow_fbo = 0
        self.shadow_texture = 0
        self.shadow_qt_fbo = None

        try:
            from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat

            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
            fbo = QOpenGLFramebufferObject(self.shadow_size, self.shadow_size, fmt)
            if not fbo.isValid():
                raise RuntimeError("QOpenGLFramebufferObject invalid")
            self.shadow_qt_fbo = fbo
            self.shadow_texture = int(fbo.texture())
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.shadow_texture)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            self.shadow_supported = True
            self.shadow_error = ""
            self._invalidate_shadow_cache()
            return
        except Exception as qt_exc:
            qt_error = f"{type(qt_exc).__name__}: {qt_exc}"

        try:
            self.shadow_texture = int(GL.glGenTextures(1))
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.shadow_texture)
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_DEPTH_COMPONENT24,
                self.shadow_size,
                self.shadow_size,
                0,
                GL.GL_DEPTH_COMPONENT,
                GL.GL_FLOAT,
                None,
            )
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            self.shadow_fbo = int(GL.glGenFramebuffers(1))
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.shadow_fbo)
            GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_DEPTH_ATTACHMENT, GL.GL_TEXTURE_2D, self.shadow_texture, 0)
            GL.glDrawBuffer(GL.GL_NONE)
            GL.glReadBuffer(GL.GL_NONE)
            status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
            if status != GL.GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"shadow framebuffer incomplete: {status}")
            self.shadow_supported = True
            self.shadow_error = f"qt_color_depth_fbo_unavailable; using_raw_depth_shadow_map: {qt_error}"
            self._invalidate_shadow_cache()
        except Exception as exc:
            raw_error = f"{type(exc).__name__}: {exc}"
            self.shadow_supported = False
            self.shadow_error = f"qt_color_depth_fbo_failed: {qt_error}; raw_depth_fbo_failed: {raw_error}"
            self.shadow_fbo = 0
            self.shadow_texture = 0
        finally:
            try:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            except Exception:
                pass
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    def _create_ground_geometry(self) -> None:
        from OpenGL import GL

        size = 1.35
        vertices = np.asarray([
            [-size, 0.0, -size],
            [size, 0.0, -size],
            [size, 0.0, size],
            [-size, 0.0, -size],
            [size, 0.0, size],
            [-size, 0.0, size],
        ], dtype=np.float32)
        self.ground_vao = int(GL.glGenVertexArrays(1))
        self.ground_vbo = int(GL.glGenBuffers(1))
        GL.glBindVertexArray(self.ground_vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.ground_vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, False, 3 * 4, ctypes.c_void_p(0))
        GL.glBindVertexArray(0)

    def _upload_hdri(self) -> None:
        if self.hdri is None:
            self.hdri_texture = 0
            self.hdri_max_lod = 0.0
            return
        from OpenGL import GL

        texture_id = GL.glGenTextures(1)
        self.hdri_texture = int(texture_id)
        self.hdri_max_lod = float(max(0, int(math.floor(math.log2(max(self.hdri.width, self.hdri.height))))))
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.hdri_texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            getattr(GL, "GL_RGB16F", 0x881B),
            int(self.hdri.width),
            int(self.hdri.height),
            0,
            GL.GL_RGB,
            GL.GL_FLOAT,
            self.hdri.pixels,
        )
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)

    @staticmethod
    def _upload_float_rgb_texture(arr: np.ndarray, *, texture_unit: int, mipmapped: bool = False) -> int:
        from OpenGL import GL

        data = np.ascontiguousarray(np.asarray(arr, dtype=np.float32)[:, :, :3])
        if data.ndim != 3 or data.shape[2] < 3 or data.size <= 0:
            return 0
        tex = int(GL.glGenTextures(1))
        GL.glActiveTexture(GL.GL_TEXTURE0 + int(texture_unit))
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(
            GL.GL_TEXTURE_2D,
            GL.GL_TEXTURE_MIN_FILTER,
            GL.GL_LINEAR_MIPMAP_LINEAR if mipmapped else GL.GL_LINEAR,
        )
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            getattr(GL, "GL_RGB16F", 0x881B),
            int(data.shape[1]),
            int(data.shape[0]),
            0,
            GL.GL_RGB,
            GL.GL_FLOAT,
            data,
        )
        if mipmapped:
            GL.glGenerateMipmap(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        return tex

    @staticmethod
    def _upload_prefilter_levels(levels: Any, *, texture_unit: int) -> tuple[int, int]:
        from OpenGL import GL

        rows = [np.ascontiguousarray(np.asarray(level, dtype=np.float32)[:, :, :3]) for level in levels if level is not None]
        if not rows:
            return 0, 0
        tex = int(GL.glGenTextures(1))
        GL.glActiveTexture(GL.GL_TEXTURE0 + int(texture_unit))
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR if len(rows) > 1 else GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        try:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, getattr(GL, "GL_TEXTURE_BASE_LEVEL", 0x813C), 0)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, getattr(GL, "GL_TEXTURE_MAX_LEVEL", 0x813D), len(rows) - 1)
        except Exception:
            pass
        for level, data in enumerate(rows):
            if data.ndim != 3 or data.shape[2] < 3 or data.size <= 0:
                continue
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                int(level),
                getattr(GL, "GL_RGB16F", 0x881B),
                int(data.shape[1]),
                int(data.shape[0]),
                0,
                GL.GL_RGB,
                GL.GL_FLOAT,
                data,
            )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        return tex, len(rows)

    @staticmethod
    def _upload_brdf_lut(lut: np.ndarray, *, texture_unit: int) -> int:
        from OpenGL import GL

        data = np.ascontiguousarray(np.asarray(lut, dtype=np.float32)[:, :, :2])
        if data.ndim != 3 or data.shape[2] < 2 or data.size <= 0:
            return 0
        tex = int(GL.glGenTextures(1))
        GL.glActiveTexture(GL.GL_TEXTURE0 + int(texture_unit))
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D,
            0,
            getattr(GL, "GL_RG16F", 0x822F),
            int(data.shape[1]),
            int(data.shape[0]),
            0,
            getattr(GL, "GL_RG", 0x8227),
            GL.GL_FLOAT,
            data,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        return tex

    def _clear_ibl_textures(self) -> None:
        self._delete_gl_texture(self.ibl_irradiance_texture)
        self._delete_gl_texture(self.ibl_prefilter_texture)
        self._delete_gl_texture(self.ibl_brdf_lut_texture)
        self.ibl_irradiance_texture = 0
        self.ibl_prefilter_texture = 0
        self.ibl_brdf_lut_texture = 0
        self.ibl_prefilter_level_count = 0
        self.ibl_probe_diag = {"available": False}

    def _upload_ibl_probe(self) -> None:
        self._clear_ibl_textures()
        if self.hdri is None or not str(getattr(self.hdri, "path", "") or "").strip():
            self.ibl_probe_diag = {"available": False, "reason": "hdri_missing"}
            return
        try:
            from app.ar_pbr.ibl import load_ibl_probe

            probe = load_ibl_probe(str(self.hdri.path))
            if probe is None or not probe.available:
                self.ibl_probe_diag = {"available": False, "reason": "probe_unavailable", "path": str(self.hdri.path)}
                return
            irradiance = self._upload_float_rgb_texture(probe.irradiance_map, texture_unit=7)
            prefilter, levels = self._upload_prefilter_levels(probe.prefiltered_levels, texture_unit=8)
            brdf = self._upload_brdf_lut(probe.brdf_lut, texture_unit=9)
            if not irradiance or not prefilter or not brdf or levels <= 0:
                self._delete_gl_texture(irradiance)
                self._delete_gl_texture(prefilter)
                self._delete_gl_texture(brdf)
                self.ibl_probe_diag = {"available": False, "reason": "probe_texture_upload_failed", **probe.diagnostics()}
                return
            self.ibl_irradiance_texture = int(irradiance)
            self.ibl_prefilter_texture = int(prefilter)
            self.ibl_brdf_lut_texture = int(brdf)
            self.ibl_prefilter_level_count = int(levels)
            self.ibl_probe_diag = {**probe.diagnostics(), "gl_uploaded": True}
        except Exception as exc:
            self.ibl_probe_diag = {
                "available": False,
                "reason": f"{type(exc).__name__}: {exc}",
                "path": str(getattr(self.hdri, "path", "") or ""),
            }

    def set_hdri(self, hdri: HdrImage | None) -> None:
        """Replace the viewport HDR environment without reimporting the mesh."""
        self.hdri = hdri
        try:
            self.makeCurrent()
            if self.hdri_texture:
                from OpenGL import GL

                self._delete_gl_texture(self.hdri_texture)
                self.hdri_texture = 0
                self.hdri_max_lod = 0.0
            self._clear_ibl_textures()
            self._upload_hdri()
            self._upload_ibl_probe()
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass
        self._invalidate_shadow_cache()
        self.update()

    def set_environment_background_visible(self, visible: bool) -> None:
        """Show or hide the HDR environment background without changing IBL."""
        self.show_environment_background = bool(visible)
        self.update()

    def set_mesh_data(self, vertices: np.ndarray, mesh_diag: Mapping[str, Any]) -> None:
        """Replace the mesh buffer without rebuilding the OpenGL widget."""
        self.vertices = np.ascontiguousarray(vertices, dtype=np.float32)
        self.mesh_diag = dict(mesh_diag or {})
        self.draw_ranges = list(self.mesh_diag.get("draw_ranges") or [{"start": 0, "count": int(len(self.vertices)), "material_name": ""}])
        try:
            self.makeCurrent()
            if self.vbo:
                from OpenGL import GL

                GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vbo)
                GL.glBufferData(GL.GL_ARRAY_BUFFER, self.vertices.nbytes, self.vertices, GL.GL_STATIC_DRAW)
                self._vbo_size_bytes = int(self.vertices.nbytes)
                self._configure_mesh_vertex_attributes()
                GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass
        self.update()

    def set_skinning_matrices(self, matrices: Any, diagnostics: Mapping[str, Any] | None = None) -> None:
        """Update the GPU bone palette without rebuilding mesh vertices."""
        arr = np.asarray(matrices, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[1:] != (4, 4) or len(arr) <= 0:
            self.skinning_matrices = None
            self.skinning_diag = {"available": False, "reason": "invalid_skinning_matrix_shape"}
        else:
            self.skinning_matrices = np.ascontiguousarray(arr[:GPU_SKINNING_MAX_BONES], dtype=np.float32)
            self.skinning_diag = {
                "available": True,
                "bone_count": int(len(self.skinning_matrices)),
                **dict(diagnostics or {}),
            }
        self._invalidate_shadow_cache()
        self.update()

    def clear_skinning_matrices(self) -> None:
        self.skinning_matrices = None
        self.skinning_diag = {"available": False}
        self._invalidate_shadow_cache()
        self.update()

    def _upload_skinning_uniforms(self, program: int) -> None:
        from OpenGL import GL

        available = (
            self.skinning_matrices is not None
            and int(self.mesh_diag.get("gpu_skinning_vertex_count", 0) or 0) > 0
        )
        GL.glUniform1i(self._uniform_location(program, "u_skinning_enabled"), 1 if available else 0)
        count = int(len(self.skinning_matrices)) if available and self.skinning_matrices is not None else 0
        count = max(0, min(GPU_SKINNING_MAX_BONES, count))
        GL.glUniform1i(self._uniform_location(program, "u_skin_bone_count"), count)
        center = self.mesh_diag.get("descriptor_center") or [0.0, 0.0, 0.0]
        max_size = float(self.mesh_diag.get("descriptor_max_size") or 1.0)
        GL.glUniform3f(
            self._uniform_location(program, "u_bounds_center"),
            float(center[0] if len(center) > 0 else 0.0),
            float(center[1] if len(center) > 1 else 0.0),
            float(center[2] if len(center) > 2 else 0.0),
        )
        GL.glUniform1f(self._uniform_location(program, "u_bounds_max_size"), max(1.0e-6, max_size))
        if count > 0 and self.skinning_matrices is not None:
            GL.glUniformMatrix4fv(
                self._uniform_location(program, "u_skin_bones"),
                count,
                True,
                self.skinning_matrices[:count],
            )

    def _upload_stage_transform_uniforms(self, program: int, draw_range: Mapping[str, Any]) -> None:
        from OpenGL import GL

        enabled = bool(draw_range.get("stage_transform_enabled"))
        center = list(draw_range.get("stage_center") or [0.0, 0.0, 0.0])[:3]
        offset = list(draw_range.get("stage_offset") or [0.0, 0.0, 0.0])[:3]
        center += [0.0] * (3 - len(center))
        offset += [0.0] * (3 - len(offset))
        try:
            center_values = [float(center[0]), float(center[1]), float(center[2])]
        except Exception:
            center_values = [0.0, 0.0, 0.0]
        try:
            offset_values = [float(offset[0]), float(offset[1]), float(offset[2])]
        except Exception:
            offset_values = [0.0, 0.0, 0.0]
        GL.glUniform1i(self._uniform_location(program, "u_stage_transform_enabled"), 1 if enabled else 0)
        GL.glUniform1i(self._uniform_location(program, "u_stage_rotate_y_180"), 1 if bool(draw_range.get("stage_rotate_y_180")) else 0)
        GL.glUniform3f(
            self._uniform_location(program, "u_stage_center"),
            float(center_values[0]),
            float(center_values[1]),
            float(center_values[2]),
        )
        GL.glUniform3f(
            self._uniform_location(program, "u_stage_offset"),
            float(offset_values[0]),
            float(offset_values[1]),
            float(offset_values[2]),
        )

    def _upload_material_textures(self) -> None:
        for material_name, maps in self.texture_plan.items():
            uploaded: dict[str, int] = {}
            for map_name in ("base", "roughness", "metallic", "specular", "normal", "occlusion", "emissive", "opacity", "height"):
                path = maps.get(map_name)
                if not path:
                    continue
                uploaded[map_name] = _upload_texture_2d(
                    path,
                    scalar=map_name in {"roughness", "metallic", "specular", "occlusion", "opacity", "height"},
                    max_size=self.texture_max_size,
                    channel=maps.get(f"{map_name}_channel"),
                )
            if uploaded:
                self.material_textures[str(material_name)] = uploaded

    def _compile_shader(self, shader_type: int, source: str) -> int:
        from OpenGL import GL

        shader = GL.glCreateShader(shader_type)
        GL.glShaderSource(shader, source)
        GL.glCompileShader(shader)
        if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
            raise RuntimeError(GL.glGetShaderInfoLog(shader).decode("utf-8", errors="replace"))
        return shader

    def _create_program(self, vertex_source: str = VERT_SHADER, fragment_source: str = FRAG_SHADER) -> int:
        from OpenGL import GL

        vertex = self._compile_shader(GL.GL_VERTEX_SHADER, vertex_source)
        fragment = self._compile_shader(GL.GL_FRAGMENT_SHADER, fragment_source)
        program = GL.glCreateProgram()
        GL.glAttachShader(program, vertex)
        GL.glAttachShader(program, fragment)
        GL.glLinkProgram(program)
        GL.glDeleteShader(vertex)
        GL.glDeleteShader(fragment)
        if not GL.glGetProgramiv(program, GL.GL_LINK_STATUS):
            raise RuntimeError(GL.glGetProgramInfoLog(program).decode("utf-8", errors="replace"))
        return program

    def resizeGL(self, width: int, height: int) -> None:
        from OpenGL import GL

        framebuffer_width, framebuffer_height = self._framebuffer_size()
        GL.glViewport(0, 0, framebuffer_width, framebuffer_height)
        if self.auto_fit_enabled:
            self.auto_fit_pending = True

    def _draw_bloom_blur_pass(
        self,
        *,
        source_texture: int,
        source_width: int,
        source_height: int,
        target_fbo: int,
        target_width: int,
        target_height: int,
        direction: tuple[float, float],
        radius: float,
        threshold: float,
        boost: float,
        anamorphic_strength: float,
        anamorphic_threshold: float,
        anamorphic_ratio: float,
        extract_bright: bool,
    ) -> bool:
        from OpenGL import GL

        if not int(self.bloom_blur_program or 0) or not int(source_texture or 0) or not int(target_fbo or 0):
            return False
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, int(target_fbo))
        try:
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
        except Exception:
            pass
        GL.glViewport(0, 0, max(1, int(target_width)), max(1, int(target_height)))
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthMask(False)
        GL.glUseProgram(self.bloom_blur_program)
        GL.glActiveTexture(GL.GL_TEXTURE15)
        GL.glBindTexture(GL.GL_TEXTURE_2D, int(source_texture))
        GL.glUniform1i(self._uniform_location(self.bloom_blur_program, "u_source"), 15)
        GL.glUniform2f(
            self._uniform_location(self.bloom_blur_program, "u_texel_size"),
            1.0 / max(1, int(source_width)),
            1.0 / max(1, int(source_height)),
        )
        GL.glUniform2f(
            self._uniform_location(self.bloom_blur_program, "u_direction"),
            float(direction[0]),
            float(direction[1]),
        )
        GL.glUniform1f(self._uniform_location(self.bloom_blur_program, "u_bloom_radius"), float(radius))
        GL.glUniform1f(self._uniform_location(self.bloom_blur_program, "u_bloom_threshold"), float(threshold))
        GL.glUniform1f(self._uniform_location(self.bloom_blur_program, "u_bloom_boost"), float(boost))
        GL.glUniform1f(
            self._uniform_location(self.bloom_blur_program, "u_anamorphic_strength"),
            float(anamorphic_strength),
        )
        GL.glUniform1f(
            self._uniform_location(self.bloom_blur_program, "u_anamorphic_threshold"),
            float(anamorphic_threshold),
        )
        GL.glUniform1f(
            self._uniform_location(self.bloom_blur_program, "u_anamorphic_ratio"),
            float(anamorphic_ratio),
        )
        GL.glUniform1i(self._uniform_location(self.bloom_blur_program, "u_extract_bright"), 1 if extract_bright else 0)
        GL.glBindVertexArray(self.post_bloom_vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        GL.glBindVertexArray(0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glUseProgram(0)
        return True

    def _blurred_bloom_texture(self, width: int, height: int, post_effects: Mapping[str, Any]) -> tuple[int, int, int]:
        from OpenGL import GL

        if not self._ensure_bloom_blur_fbo(width, height):
            return int(self.scene_bloom_texture or 0), max(1, int(width)), max(1, int(height))
        blur_w, blur_h = self.bloom_blur_fbo_size
        radius = float(post_effects.get("bloom_radius", DEFAULT_BLOOM_RADIUS) or DEFAULT_BLOOM_RADIUS)
        strength = float(post_effects.get("bloom_strength", DEFAULT_BLOOM_STRENGTH) or DEFAULT_BLOOM_STRENGTH)
        boost = max(float(post_effects.get("bloom_boost", DEFAULT_BLOOM_BOOST) or DEFAULT_BLOOM_BOOST), strength * 0.42)
        raw_threshold = float(post_effects.get("bloom_threshold", DEFAULT_BLOOM_THRESHOLD) or DEFAULT_BLOOM_THRESHOLD)
        threshold = max(0.02, raw_threshold - min(0.34, strength * 0.075 + boost * 0.035))
        anamorphic_strength = float(
            post_effects.get("bloom_anamorphic_strength", DEFAULT_BLOOM_ANAMORPHIC_STRENGTH)
            or DEFAULT_BLOOM_ANAMORPHIC_STRENGTH
        )
        if anamorphic_strength <= 0.0:
            anamorphic_strength = max(0.0, strength - 0.72) * 0.72 + boost * 0.28
        anamorphic_strength = max(0.0, min(6.0, anamorphic_strength))
        anamorphic_threshold = max(
            threshold + 0.14,
            float(
                post_effects.get("bloom_anamorphic_threshold", DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD)
                or DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD
            ),
        )
        anamorphic_ratio = max(
            1.0,
            min(
                12.0,
                float(
                    post_effects.get("bloom_anamorphic_ratio", DEFAULT_BLOOM_ANAMORPHIC_RATIO)
                    or DEFAULT_BLOOM_ANAMORPHIC_RATIO
                ),
            ),
        )
        vertical_radius = radius * (0.34 if anamorphic_strength > 0.001 else 1.0)
        second_horizontal_radius = radius * (0.82 if anamorphic_strength > 0.001 else 0.62)
        second_vertical_radius = radius * (0.22 if anamorphic_strength > 0.001 else 0.62)
        pass_plan = (
            (
                int(self.scene_bloom_texture or 0),
                max(1, int(width)),
                max(1, int(height)),
                self.bloom_blur_fbo_a,
                (1.0, 0.0),
                radius,
                True,
                0.0,
            ),
            (self.bloom_blur_texture_a, blur_w, blur_h, self.bloom_blur_fbo_b, (0.0, 1.0), vertical_radius, False, 0.0),
            (self.bloom_blur_texture_b, blur_w, blur_h, self.bloom_blur_fbo_a, (1.0, 0.0), second_horizontal_radius, False, 0.0),
            (self.bloom_blur_texture_a, blur_w, blur_h, self.bloom_blur_fbo_b, (0.0, 1.0), second_vertical_radius, False, 0.0),
        )
        for source, source_w, source_h, target_fbo, direction, pass_radius, extract, pass_anamorphic_strength in pass_plan:
            ok = self._draw_bloom_blur_pass(
                source_texture=source,
                source_width=source_w,
                source_height=source_h,
                target_fbo=int(target_fbo or 0),
                target_width=blur_w,
                target_height=blur_h,
                direction=direction,
                radius=pass_radius,
                threshold=threshold,
                boost=boost if extract else 0.0,
                anamorphic_strength=pass_anamorphic_strength,
                anamorphic_threshold=anamorphic_threshold,
                anamorphic_ratio=anamorphic_ratio,
                extract_bright=extract,
            )
            if not ok:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                return int(self.scene_bloom_texture or 0), max(1, int(width)), max(1, int(height))
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        return int(self.bloom_blur_texture_b or 0), blur_w, blur_h

    def _draw_bloom_post(self, width: int, height: int, post_effects: Mapping[str, Any], bloom_strength: float) -> None:
        from OpenGL import GL

        if not int(self.post_bloom_program or 0) or not int(self.scene_color_texture or 0) or not int(self.scene_bloom_texture or 0):
            self._bind_default_framebuffer()
            return
        bloom_texture, bloom_width, bloom_height = self._blurred_bloom_texture(width, height, post_effects)
        self._bind_default_framebuffer()
        GL.glViewport(0, 0, max(1, int(width)), max(1, int(height)))
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glDepthMask(False)
        GL.glUseProgram(self.post_bloom_program)
        GL.glActiveTexture(GL.GL_TEXTURE14)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.scene_color_texture)
        GL.glUniform1i(self._uniform_location(self.post_bloom_program, "u_scene_color"), 14)
        GL.glActiveTexture(GL.GL_TEXTURE15)
        GL.glBindTexture(GL.GL_TEXTURE_2D, int(bloom_texture or self.scene_bloom_texture))
        GL.glUniform1i(self._uniform_location(self.post_bloom_program, "u_bloom_source"), 15)
        GL.glActiveTexture(GL.GL_TEXTURE13)
        GL.glBindTexture(GL.GL_TEXTURE_2D, int(self.scene_bloom_texture or 0))
        GL.glUniform1i(self._uniform_location(self.post_bloom_program, "u_peak_source"), 13)
        GL.glUniform2f(
            self._uniform_location(self.post_bloom_program, "u_texel_size"),
            1.0 / max(1, int(bloom_width)),
            1.0 / max(1, int(bloom_height)),
        )
        GL.glUniform2f(
            self._uniform_location(self.post_bloom_program, "u_peak_texel_size"),
            1.0 / max(1, int(width)),
            1.0 / max(1, int(height)),
        )
        GL.glUniform1f(self._uniform_location(self.post_bloom_program, "u_bloom_strength"), float(bloom_strength))
        GL.glUniform1f(
            self._uniform_location(self.post_bloom_program, "u_bloom_radius"),
            float(post_effects.get("bloom_radius", DEFAULT_BLOOM_RADIUS) or DEFAULT_BLOOM_RADIUS),
        )
        GL.glUniform1f(
            self._uniform_location(self.post_bloom_program, "u_bloom_threshold"),
            float(post_effects.get("bloom_threshold", DEFAULT_BLOOM_THRESHOLD) or DEFAULT_BLOOM_THRESHOLD),
        )
        anamorphic_strength = float(
            post_effects.get("bloom_anamorphic_strength", DEFAULT_BLOOM_ANAMORPHIC_STRENGTH)
            or DEFAULT_BLOOM_ANAMORPHIC_STRENGTH
        )
        if anamorphic_strength <= 0.0:
            anamorphic_strength = max(0.0, float(bloom_strength) - 0.72) * 0.72
        GL.glUniform1f(
            self._uniform_location(self.post_bloom_program, "u_anamorphic_strength"),
            max(0.0, min(6.0, anamorphic_strength)),
        )
        GL.glUniform1f(
            self._uniform_location(self.post_bloom_program, "u_anamorphic_threshold"),
            float(
                post_effects.get("bloom_anamorphic_threshold", DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD)
                or DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD
            ),
        )
        GL.glUniform1f(
            self._uniform_location(self.post_bloom_program, "u_anamorphic_ratio"),
            max(
                1.0,
                min(
                    12.0,
                    float(
                        post_effects.get("bloom_anamorphic_ratio", DEFAULT_BLOOM_ANAMORPHIC_RATIO)
                        or DEFAULT_BLOOM_ANAMORPHIC_RATIO
                    ),
                ),
            ),
        )
        GL.glUniform1i(self._uniform_location(self.post_bloom_program, "u_force_opaque"), 0 if self.transparent_background else 1)
        GL.glBindVertexArray(self.post_bloom_vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
        GL.glBindVertexArray(0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE13)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE14)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glUseProgram(0)
        GL.glDepthMask(True)
        GL.glEnable(GL.GL_BLEND)
        GL.glEnable(GL.GL_DEPTH_TEST)

    def paintGL(self) -> None:
        from OpenGL import GL

        width = max(1, self.width())
        height = max(1, self.height())
        framebuffer_width, framebuffer_height = self._framebuffer_size()
        if self.auto_fit_enabled and self.auto_fit_pending:
            self.fit_current_view()
            self.auto_fit_pending = False
        proj = _perspective(max(10.0, min(120.0, float(self.state.fov_deg))), width / height, 0.05, 50.0)
        view = np.eye(4, dtype=np.float32)
        view[2, 3] = -float(self.state.camera_z)
        rot3 = _rotation_matrix(self.state.pitch, self.state.yaw, self.state.roll)
        model = np.eye(4, dtype=np.float32)
        model[:3, :3] = rot3 * float(self.state.zoom)
        model[:3, 3] = np.asarray([self.state.pan_x, self.state.pan_y, self.state.pan_z], dtype=np.float32)
        mvp = proj @ view @ model
        normal_mat = rot3.astype(np.float32)
        to_light = _direction_from_azimuth_elevation(
            self.state.light_azimuth - self.state.ibl_rotation * 360.0,
            self.state.light_elevation,
        )
        light_dir = -to_light
        shadow_settings = normalize_shadow_settings({
            "shadow_filter": self.state.shadow_filter,
            "shadow_light_type": self.state.shadow_light_type,
            "shadow_map_size": self.shadow_size,
            "shadow_pcf_radius": self.state.shadow_pcf_radius,
            "shadow_pcss_blocker_radius": self.state.shadow_pcss_blocker_radius,
            "shadow_bias": self.state.shadow_bias,
            "shadow_normal_bias": self.state.shadow_normal_bias,
            "shadow_spot_inner_angle": self.state.shadow_spot_inner_angle,
            "shadow_spot_outer_angle": self.state.shadow_spot_outer_angle,
        })
        light_view = _look_at(
            to_light * 4.0,
            np.asarray([0.0, 0.0, 0.0], dtype=np.float32),
            np.asarray([0.0, 1.0, 0.0], dtype=np.float32),
        )
        if shadow_settings["light_type"] == "spot":
            light_proj = _perspective(float(shadow_settings["spot_outer_angle"]) * 2.0, 1.0, 0.1, 8.0)
        else:
            light_proj = _orthographic(-2.0, 2.0, -2.0, 2.0, 0.1, 8.0)
        light_mvp = light_proj @ light_view @ model
        ground_offset = np.eye(4, dtype=np.float32)
        ground_offset[1, 3] = float(self.state.ground_y)
        ground_model = model @ ground_offset
        ground_mvp = proj @ view @ ground_model
        ground_light_mvp = light_proj @ light_view @ ground_model

        shadow_signature = self._shadow_signature()
        should_update_shadow = bool(
            self.shadow_supported
            and (self._shadow_dirty or shadow_signature != self._last_shadow_signature)
        )
        if should_update_shadow:
            shadow_bound = True
            if self.shadow_qt_fbo is not None:
                shadow_bound = bool(self.shadow_qt_fbo.bind())
                if not shadow_bound:
                    self.shadow_supported = False
                    self.shadow_error = "qt_color_depth_shadow_fbo_bind_failed"
            else:
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.shadow_fbo)
            if shadow_bound:
                GL.glViewport(0, 0, self.shadow_size, self.shadow_size)
                GL.glClearColor(1.0, 1.0, 1.0, 1.0)
                clear_bits = GL.GL_DEPTH_BUFFER_BIT
                if self.shadow_qt_fbo is not None:
                    clear_bits |= GL.GL_COLOR_BUFFER_BIT
                GL.glClear(clear_bits)
                GL.glUseProgram(self.depth_program)
                GL.glUniformMatrix4fv(self._uniform_location(self.depth_program, "u_light_mvp"), 1, True, light_mvp)
                self._upload_skinning_uniforms(self.depth_program)
                GL.glBindVertexArray(self.vao)
                for draw_range in self.draw_ranges:
                    if draw_range.get("depth_write") is False:
                        continue
                    draw_count = int(draw_range.get("count", len(self.vertices)) or 0)
                    if draw_count <= 0:
                        continue
                    self._upload_stage_transform_uniforms(self.depth_program, draw_range)
                    GL.glDrawArrays(
                        GL.GL_TRIANGLES,
                        int(draw_range.get("start", 0) or 0),
                        draw_count,
                    )
                GL.glBindVertexArray(0)
                if self.shadow_qt_fbo is not None:
                    self.shadow_qt_fbo.release()
                else:
                    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                self._mark_shadow_clean(shadow_signature)

        post_effects = post_effects_diagnostics(self.state)
        bloom_strength = (
            float(post_effects.get("bloom_strength", 0.0) or 0.0)
            if bool(post_effects.get("enabled")) and bool(post_effects.get("bloom_enabled"))
            else 0.0
        )
        bloom_post_active = bool(
            bloom_strength > 0.0001
            and self._ensure_scene_fbo(framebuffer_width, framebuffer_height)
        )
        if bloom_post_active:
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self.scene_fbo)
            self._set_scene_draw_buffers()
        else:
            self._bind_default_framebuffer()
        GL.glViewport(0, 0, framebuffer_width, framebuffer_height)
        if self.transparent_background:
            clear_color = (0.0, 0.0, 0.0, 0.0)
        else:
            clear_color = (0.36, 0.40, 0.43, 1.0)
        if bloom_post_active:
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT0)
            GL.glClearColor(*clear_color)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
            GL.glDrawBuffer(GL.GL_COLOR_ATTACHMENT1)
            GL.glClearColor(0.0, 0.0, 0.0, 0.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT)
            self._set_scene_draw_buffers()
        else:
            GL.glClearColor(*clear_color)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        color_management = color_management_diagnostics(self.state)
        hybrid_rendering = hybrid_rendering_diagnostics(self.state)
        transmission = transmission_diagnostics(self.state)
        clearcoat = clearcoat_diagnostics(self.state)
        parallax = parallax_diagnostics(self.state)
        bevel = bevel_diagnostics(self.state)
        material_layering = material_layering_diagnostics(self.state)
        surface = surface_diagnostics(self.state)
        subsurface = subsurface_diagnostics(self.state)
        hair_groom = hair_groom_diagnostics(self.state)
        cloth_sheen = cloth_sheen_diagnostics(self.state)
        glint_sparkle = glint_sparkle_diagnostics(self.state)
        triplanar = triplanar_diagnostics(self.state)
        ambient_occlusion = ambient_occlusion_diagnostics(self.state)
        tone_mode = int(color_management["tone_mapping_mode"])
        tone_exposure = float(color_management["tone_exposure"])
        tone_gamma = float(color_management["tone_gamma"])
        tone_wb = list(color_management["tone_white_balance_rgb"])
        hybrid_samples = int(hybrid_rendering["sample_count"])
        diffuse_gi = float(hybrid_rendering["diffuse_gi_strength"])
        specular_gi = float(hybrid_rendering["specular_gi_strength"])
        denoise_strength = float(hybrid_rendering["denoise_strength"])
        absorption_color = list(transmission.get("absorption_color") or [1.0, 1.0, 1.0])
        clearcoat_tint = list(clearcoat.get("tint") or [1.0, 1.0, 1.0])
        material_layer_color = list(material_layering.get("color") or [1.0, 1.0, 1.0])
        subsurface_color = list(subsurface.get("color") or [1.0, 0.62, 0.42])
        hair_tint = list(hair_groom.get("tint") or [1.0, 0.88, 0.62])
        cloth_color = list(cloth_sheen.get("color") or [0.92, 0.96, 1.0])
        cloth_edge_tint = list(cloth_sheen.get("edge_tint") or [0.72, 0.82, 1.0])
        glint_color = list(glint_sparkle.get("color") or [1.0, 0.96, 0.82])
        triplanar_offset = list(triplanar.get("offset") or [0.0, 0.0, 0.0])
        ao_color = list(ambient_occlusion.get("color") or [0.0, 0.0, 0.0])
        ao_color = (ao_color + [0.0, 0.0, 0.0])[:3]
        ao_strength = (
            float(ambient_occlusion.get("strength", 0.0) or 0.0)
            if bool(ambient_occlusion.get("enabled"))
            else 0.0
        )
        if self.show_environment_background:
            GL.glDepthMask(False)
            GL.glDisable(GL.GL_DEPTH_TEST)
            GL.glUseProgram(self.environment_program)
            GL.glUniform1i(self._uniform_location(self.environment_program, "u_has_hdri"), 1 if self.hdri_texture else 0)
            GL.glUniform1f(self._uniform_location(self.environment_program, "u_ibl_rotation"), float(self.state.ibl_rotation))
            GL.glUniform1f(self._uniform_location(self.environment_program, "u_ibl_exposure"), float(self.state.ibl_exposure))
            GL.glUniform1i(self._uniform_location(self.environment_program, "u_tone_mapping_mode"), tone_mode)
            GL.glUniform1f(self._uniform_location(self.environment_program, "u_tone_exposure"), tone_exposure)
            GL.glUniform3f(self._uniform_location(self.environment_program, "u_tone_white_balance"), float(tone_wb[0]), float(tone_wb[1]), float(tone_wb[2]))
            GL.glUniform1f(self._uniform_location(self.environment_program, "u_tone_gamma"), tone_gamma)
            if self.hdri_texture:
                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, self.hdri_texture)
                GL.glUniform1i(self._uniform_location(self.environment_program, "u_hdri"), 0)
            GL.glBindVertexArray(self.environment_vao)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 3)
            GL.glBindVertexArray(0)
            GL.glUseProgram(0)
            GL.glEnable(GL.GL_DEPTH_TEST)
            GL.glDepthMask(True)

        if self.draw_ground:
            GL.glUseProgram(self.ground_program)
            GL.glUniformMatrix4fv(self._uniform_location(self.ground_program, "u_mvp"), 1, True, ground_mvp)
            GL.glUniformMatrix4fv(self._uniform_location(self.ground_program, "u_light_mvp"), 1, True, ground_light_mvp)
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_strength"), float(self.state.shadow_strength))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_pcf_radius"), float(self.state.shadow_pcf_radius))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_pcss_blocker_radius"), float(self.state.shadow_pcss_blocker_radius))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_bias"), float(self.state.shadow_bias))
            GL.glUniform1i(self._uniform_location(self.ground_program, "u_shadow_filter_mode"), 1 if self.state.shadow_filter == "pcss" else 0)
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_ibl_rotation"), float(self.state.ibl_rotation))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_ibl_exposure"), float(self.state.ibl_exposure))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_ground_reflection"), float(self.state.ground_reflection))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_catcher_opacity"), float(self.state.shadow_catcher_opacity))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_catcher_softness"), float(self.state.shadow_catcher_softness))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_shadow_catcher_matte_alpha"), float(self.state.shadow_catcher_matte_alpha))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_reflection_catcher_opacity"), float(self.state.reflection_catcher_opacity))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_reflection_catcher_roughness"), float(self.state.reflection_catcher_roughness))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_reflection_catcher_softness"), float(self.state.reflection_catcher_softness))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_reflection_catcher_matte_alpha"), float(self.state.shadow_catcher_matte_alpha))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_contact_reflection_strength"), float(self.state.contact_reflection_strength))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_contact_reflection_falloff"), float(self.state.contact_reflection_falloff))
            GL.glUniform1i(self._uniform_location(self.ground_program, "u_tone_mapping_mode"), tone_mode)
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_tone_exposure"), tone_exposure)
            GL.glUniform3f(self._uniform_location(self.ground_program, "u_tone_white_balance"), float(tone_wb[0]), float(tone_wb[1]), float(tone_wb[2]))
            GL.glUniform1f(self._uniform_location(self.ground_program, "u_tone_gamma"), tone_gamma)
            GL.glUniform1i(self._uniform_location(self.ground_program, "u_has_shadow_map"), 1 if self.shadow_supported else 0)
            if self.shadow_supported:
                GL.glActiveTexture(GL.GL_TEXTURE6)
                GL.glBindTexture(GL.GL_TEXTURE_2D, self.shadow_texture)
                GL.glUniform1i(self._uniform_location(self.ground_program, "u_shadow_map"), 6)
            GL.glUniform1i(self._uniform_location(self.ground_program, "u_has_hdri"), 1 if self.hdri_texture else 0)
            if self.hdri_texture:
                GL.glActiveTexture(GL.GL_TEXTURE0)
                GL.glBindTexture(GL.GL_TEXTURE_2D, self.hdri_texture)
                GL.glUniform1i(self._uniform_location(self.ground_program, "u_hdri"), 0)
            GL.glBindVertexArray(self.ground_vao)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
            GL.glBindVertexArray(0)

        GL.glUseProgram(self.program)
        GL.glUniformMatrix4fv(self._uniform_location(self.program, "u_mvp"), 1, True, mvp)
        GL.glUniformMatrix4fv(self._uniform_location(self.program, "u_model"), 1, True, model)
        GL.glUniformMatrix4fv(self._uniform_location(self.program, "u_light_mvp"), 1, True, light_mvp)
        GL.glUniformMatrix3fv(self._uniform_location(self.program, "u_normal_mat"), 1, True, normal_mat)
        self._upload_skinning_uniforms(self.program)
        GL.glUniform3f(
            self._uniform_location(self.program, "u_light_dir"),
            float(light_dir[0]),
            float(light_dir[1]),
            float(light_dir[2]),
        )
        light_color = list(self.state.light_color) + [1.0, 1.0, 1.0]
        GL.glUniform3f(
            self._uniform_location(self.program, "u_light_color"),
            max(0.0, float(light_color[0])),
            max(0.0, float(light_color[1])),
            max(0.0, float(light_color[2])),
        )
        GL.glUniform3f(self._uniform_location(self.program, "u_camera_pos"), 0.0, 0.0, float(self.state.camera_z))
        GL.glUniform1f(self._uniform_location(self.program, "u_ibl_exposure"), float(self.state.ibl_exposure))
        unlit_controls = self.unlit_color_controls()
        GL.glUniform1f(
            self._uniform_location(self.program, "u_unlit_exposure_scale"),
            float(unlit_controls["unlit_exposure_scale"]),
        )
        GL.glUniform1f(
            self._uniform_location(self.program, "u_unlit_contrast"),
            float(unlit_controls["unlit_contrast"]),
        )
        GL.glUniform1f(
            self._uniform_location(self.program, "u_unlit_output_gamma"),
            float(unlit_controls["unlit_output_gamma"]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_ibl_rotation"), float(self.state.ibl_rotation))
        GL.glUniform1f(self._uniform_location(self.program, "u_max_lod"), float(self.hdri_max_lod))
        GL.glUniform1f(self._uniform_location(self.program, "u_direct_intensity"), float(self.state.direct_intensity))
        GL.glUniform1i(self._uniform_location(self.program, "u_tone_mapping_mode"), tone_mode)
        GL.glUniform1f(self._uniform_location(self.program, "u_tone_exposure"), tone_exposure)
        GL.glUniform3f(self._uniform_location(self.program, "u_tone_white_balance"), float(tone_wb[0]), float(tone_wb[1]), float(tone_wb[2]))
        GL.glUniform1f(self._uniform_location(self.program, "u_tone_gamma"), tone_gamma)
        GL.glUniform1i(self._uniform_location(self.program, "u_hybrid_sample_count"), hybrid_samples)
        GL.glUniform1f(self._uniform_location(self.program, "u_diffuse_gi_strength"), diffuse_gi)
        GL.glUniform1f(self._uniform_location(self.program, "u_specular_gi_strength"), specular_gi)
        GL.glUniform1f(self._uniform_location(self.program, "u_denoise_strength"), denoise_strength)
        GL.glUniform1f(self._uniform_location(self.program, "u_transmission"), float(transmission.get("transmission", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_refraction_strength"), float(transmission.get("refraction_strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_ior"), float(transmission.get("ior", DEFAULT_IOR) or DEFAULT_IOR))
        GL.glUniform1f(self._uniform_location(self.program, "u_thickness"), float(transmission.get("thickness", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_absorption_color"),
            float(absorption_color[0]),
            float(absorption_color[1]),
            float(absorption_color[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_clearcoat_strength"), float(clearcoat.get("strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_clearcoat_roughness"), float(clearcoat.get("roughness", DEFAULT_CLEARCOAT_ROUGHNESS) or DEFAULT_CLEARCOAT_ROUGHNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_clearcoat_ior"), float(clearcoat.get("ior", DEFAULT_CLEARCOAT_IOR) or DEFAULT_CLEARCOAT_IOR))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_clearcoat_tint"),
            float(clearcoat_tint[0]),
            float(clearcoat_tint[1]),
            float(clearcoat_tint[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_parallax_strength"), float(parallax.get("strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_parallax_depth"), float(parallax.get("depth", DEFAULT_PARALLAX_DEPTH) or DEFAULT_PARALLAX_DEPTH))
        GL.glUniform1f(self._uniform_location(self.program, "u_parallax_center"), float(parallax.get("center", DEFAULT_PARALLAX_CENTER) or DEFAULT_PARALLAX_CENTER))
        GL.glUniform1i(
            self._uniform_location(self.program, "u_parallax_steps"),
            int(parallax.get("steps", 24) or 24)
            if str(parallax.get("mode") or "") == "pom"
            else 1,
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_bevel_strength"), float(bevel.get("strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_bevel_radius"), float(bevel.get("radius", DEFAULT_BEVEL_RADIUS) or DEFAULT_BEVEL_RADIUS))
        GL.glUniform1f(self._uniform_location(self.program, "u_bevel_edge_width"), float(bevel.get("edge_width", DEFAULT_BEVEL_EDGE_WIDTH) or DEFAULT_BEVEL_EDGE_WIDTH))
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_blend"), float(material_layering.get("blend", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_material_layer_color"),
            float(material_layer_color[0]),
            float(material_layer_color[1]),
            float(material_layer_color[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_roughness"), float(material_layering.get("roughness", DEFAULT_MATERIAL_LAYER_ROUGHNESS) or DEFAULT_MATERIAL_LAYER_ROUGHNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_metallic"), float(material_layering.get("metallic", DEFAULT_MATERIAL_LAYER_METALLIC) or DEFAULT_MATERIAL_LAYER_METALLIC))
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_alpha"), float(material_layering.get("alpha", DEFAULT_MATERIAL_LAYER_ALPHA) or DEFAULT_MATERIAL_LAYER_ALPHA))
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_emissive_strength"), float(material_layering.get("emissive_strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_material_layer_mask_strength"), float(material_layering.get("mask_strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_surface_override_strength"), float(surface.get("override_strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_surface_roughness"), float(surface.get("roughness", DEFAULT_SURFACE_ROUGHNESS) or DEFAULT_SURFACE_ROUGHNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_surface_metallic"), float(surface.get("metallic", DEFAULT_SURFACE_METALLIC) or DEFAULT_SURFACE_METALLIC))
        GL.glUniform1f(self._uniform_location(self.program, "u_surface_reflectance"), float(surface.get("reflectance", DEFAULT_SURFACE_REFLECTANCE) or DEFAULT_SURFACE_REFLECTANCE))
        GL.glUniform1f(self._uniform_location(self.program, "u_subsurface_strength"), float(subsurface.get("strength", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_subsurface_color"),
            float(subsurface_color[0]),
            float(subsurface_color[1]),
            float(subsurface_color[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_subsurface_radius"), float(subsurface.get("radius", DEFAULT_SUBSURFACE_RADIUS) or DEFAULT_SUBSURFACE_RADIUS))
        GL.glUniform1f(self._uniform_location(self.program, "u_subsurface_power"), float(subsurface.get("power", DEFAULT_SUBSURFACE_POWER) or DEFAULT_SUBSURFACE_POWER))
        GL.glUniform1f(self._uniform_location(self.program, "u_subsurface_wrap"), float(subsurface.get("wrap", DEFAULT_SUBSURFACE_WRAP) or DEFAULT_SUBSURFACE_WRAP))
        GL.glUniform1f(self._uniform_location(self.program, "u_subsurface_thickness"), float(subsurface.get("thickness", DEFAULT_SUBSURFACE_THICKNESS) or DEFAULT_SUBSURFACE_THICKNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_groom_strength"), float(hair_groom.get("strength", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_hair_groom_tint"),
            float(hair_tint[0]),
            float(hair_tint[1]),
            float(hair_tint[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_primary_shift"), float(hair_groom.get("primary_shift", DEFAULT_HAIR_PRIMARY_SHIFT) if hair_groom.get("primary_shift") is not None else DEFAULT_HAIR_PRIMARY_SHIFT))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_secondary_shift"), float(hair_groom.get("secondary_shift", DEFAULT_HAIR_SECONDARY_SHIFT) if hair_groom.get("secondary_shift") is not None else DEFAULT_HAIR_SECONDARY_SHIFT))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_primary_roughness"), float(hair_groom.get("primary_roughness", DEFAULT_HAIR_PRIMARY_ROUGHNESS) or DEFAULT_HAIR_PRIMARY_ROUGHNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_secondary_roughness"), float(hair_groom.get("secondary_roughness", DEFAULT_HAIR_SECONDARY_ROUGHNESS) or DEFAULT_HAIR_SECONDARY_ROUGHNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_secondary_strength"), float(hair_groom.get("secondary_strength", DEFAULT_HAIR_SECONDARY_STRENGTH) if hair_groom.get("secondary_strength") is not None else DEFAULT_HAIR_SECONDARY_STRENGTH))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_anisotropy"), float(hair_groom.get("anisotropy", DEFAULT_HAIR_ANISOTROPY) if hair_groom.get("anisotropy") is not None else DEFAULT_HAIR_ANISOTROPY))
        GL.glUniform1f(self._uniform_location(self.program, "u_hair_rim_strength"), float(hair_groom.get("rim_strength", DEFAULT_HAIR_RIM_STRENGTH) if hair_groom.get("rim_strength") is not None else DEFAULT_HAIR_RIM_STRENGTH))
        GL.glUniform1f(self._uniform_location(self.program, "u_cloth_sheen_strength"), float(cloth_sheen.get("strength", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_cloth_sheen_color"),
            float(cloth_color[0]),
            float(cloth_color[1]),
            float(cloth_color[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_cloth_sheen_roughness"), float(cloth_sheen.get("roughness", DEFAULT_CLOTH_SHEEN_ROUGHNESS) or DEFAULT_CLOTH_SHEEN_ROUGHNESS))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_cloth_sheen_edge_tint"),
            float(cloth_edge_tint[0]),
            float(cloth_edge_tint[1]),
            float(cloth_edge_tint[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_cloth_sheen_fiber_strength"), float(cloth_sheen.get("fiber_strength", DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH) if cloth_sheen.get("fiber_strength") is not None else DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH))
        GL.glUniform1f(self._uniform_location(self.program, "u_cloth_sheen_wrap"), float(cloth_sheen.get("wrap", DEFAULT_CLOTH_SHEEN_WRAP) if cloth_sheen.get("wrap") is not None else DEFAULT_CLOTH_SHEEN_WRAP))
        GL.glUniform1f(self._uniform_location(self.program, "u_cloth_sheen_retroreflection"), float(cloth_sheen.get("retroreflection", DEFAULT_CLOTH_SHEEN_RETROREFLECTION) if cloth_sheen.get("retroreflection") is not None else DEFAULT_CLOTH_SHEEN_RETROREFLECTION))
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_strength"), float(glint_sparkle.get("strength", 0.0) or 0.0))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_glint_color"),
            float(glint_color[0]),
            float(glint_color[1]),
            float(glint_color[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_density"), float(glint_sparkle.get("density", DEFAULT_GLINT_DENSITY) if glint_sparkle.get("density") is not None else DEFAULT_GLINT_DENSITY))
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_scale"), float(glint_sparkle.get("scale", DEFAULT_GLINT_SCALE) if glint_sparkle.get("scale") is not None else DEFAULT_GLINT_SCALE))
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_threshold"), float(glint_sparkle.get("threshold", DEFAULT_GLINT_THRESHOLD) if glint_sparkle.get("threshold") is not None else DEFAULT_GLINT_THRESHOLD))
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_sharpness"), float(glint_sparkle.get("sharpness", DEFAULT_GLINT_SHARPNESS) if glint_sparkle.get("sharpness") is not None else DEFAULT_GLINT_SHARPNESS))
        GL.glUniform1f(self._uniform_location(self.program, "u_glint_roughness_jitter"), float(glint_sparkle.get("roughness_jitter", DEFAULT_GLINT_ROUGHNESS_JITTER) if glint_sparkle.get("roughness_jitter") is not None else DEFAULT_GLINT_ROUGHNESS_JITTER))
        GL.glUniform1f(self._uniform_location(self.program, "u_triplanar_strength"), float(triplanar.get("strength", 0.0) or 0.0))
        GL.glUniform1f(self._uniform_location(self.program, "u_triplanar_scale"), float(triplanar.get("scale", DEFAULT_TRIPLANAR_SCALE) or DEFAULT_TRIPLANAR_SCALE))
        GL.glUniform1f(self._uniform_location(self.program, "u_triplanar_blend_sharpness"), float(triplanar.get("blend_sharpness", DEFAULT_TRIPLANAR_BLEND_SHARPNESS) or DEFAULT_TRIPLANAR_BLEND_SHARPNESS))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_triplanar_offset"),
            float(triplanar_offset[0]),
            float(triplanar_offset[1]),
            float(triplanar_offset[2]),
        )
        GL.glUniform1f(self._uniform_location(self.program, "u_screen_ao_strength"), ao_strength)
        GL.glUniform1f(self._uniform_location(self.program, "u_screen_ao_radius"), float(ambient_occlusion.get("radius", DEFAULT_AO_RADIUS) or DEFAULT_AO_RADIUS))
        GL.glUniform1f(self._uniform_location(self.program, "u_screen_ao_distance"), float(ambient_occlusion.get("distance", DEFAULT_AO_DISTANCE) or DEFAULT_AO_DISTANCE))
        GL.glUniform3f(
            self._uniform_location(self.program, "u_screen_ao_color"),
            float(ao_color[0]),
            float(ao_color[1]),
            float(ao_color[2]),
        )
        GL.glUniform1i(self._uniform_location(self.program, "u_screen_ao_ambient"), 1 if bool(ambient_occlusion.get("ambient", True)) else 0)
        GL.glUniform1i(self._uniform_location(self.program, "u_screen_ao_diffuse"), 1 if bool(ambient_occlusion.get("diffuse", True)) else 0)
        GL.glUniform1i(self._uniform_location(self.program, "u_screen_ao_specular"), 1 if bool(ambient_occlusion.get("specular", False)) else 0)
        GL.glUniform1f(self._uniform_location(self.program, "u_shadow_strength"), float(self.state.shadow_strength))
        GL.glUniform1f(self._uniform_location(self.program, "u_shadow_pcf_radius"), float(self.state.shadow_pcf_radius))
        GL.glUniform1f(self._uniform_location(self.program, "u_shadow_pcss_blocker_radius"), float(self.state.shadow_pcss_blocker_radius))
        GL.glUniform1f(self._uniform_location(self.program, "u_shadow_bias"), float(self.state.shadow_bias))
        GL.glUniform1f(self._uniform_location(self.program, "u_shadow_normal_bias"), float(self.state.shadow_normal_bias))
        GL.glUniform1i(self._uniform_location(self.program, "u_shadow_filter_mode"), 1 if self.state.shadow_filter == "pcss" else 0)
        GL.glUniform1f(self._uniform_location(self.program, "u_self_shadow_strength"), float(self.state.self_shadow_strength))
        GL.glUniform1i(self._uniform_location(self.program, "u_has_hdri"), 1 if self.hdri_texture else 0)
        has_ibl_probe = bool(self.ibl_irradiance_texture and self.ibl_prefilter_texture and self.ibl_brdf_lut_texture)
        GL.glUniform1i(self._uniform_location(self.program, "u_has_ibl_probe"), 1 if has_ibl_probe else 0)
        GL.glUniform1f(self._uniform_location(self.program, "u_prefilter_level_count"), float(self.ibl_prefilter_level_count))
        GL.glUniform1i(self._uniform_location(self.program, "u_has_shadow_map"), 1 if self.shadow_supported else 0)
        if self.shadow_supported:
            GL.glActiveTexture(GL.GL_TEXTURE6)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.shadow_texture)
            GL.glUniform1i(self._uniform_location(self.program, "u_shadow_map"), 6)
        if self.hdri_texture:
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.hdri_texture)
            GL.glUniform1i(self._uniform_location(self.program, "u_hdri"), 0)
        if has_ibl_probe:
            GL.glActiveTexture(GL.GL_TEXTURE7)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.ibl_irradiance_texture)
            GL.glUniform1i(self._uniform_location(self.program, "u_irradiance"), 7)
            GL.glActiveTexture(GL.GL_TEXTURE8)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.ibl_prefilter_texture)
            GL.glUniform1i(self._uniform_location(self.program, "u_prefilter"), 8)
            GL.glActiveTexture(GL.GL_TEXTURE9)
            GL.glBindTexture(GL.GL_TEXTURE_2D, self.ibl_brdf_lut_texture)
            GL.glUniform1i(self._uniform_location(self.program, "u_brdf_lut"), 9)
        GL.glBindVertexArray(self.vao)
        for draw_range in self.draw_ranges:
            material_name = str(draw_range.get("material_name") or "")
            depth_write = bool(draw_range.get("depth_write", True))
            if not depth_write:
                GL.glDepthMask(False)
            else:
                GL.glDepthMask(True)
            self._bind_material_textures(material_name)
            self._upload_stage_transform_uniforms(self.program, draw_range)
            GL.glDrawArrays(
                GL.GL_TRIANGLES,
                int(draw_range.get("start", 0) or 0),
                int(draw_range.get("count", len(self.vertices)) or 0),
            )
        GL.glDepthMask(True)
        GL.glBindVertexArray(0)
        if self.hdri_texture:
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        if has_ibl_probe:
            for unit in (7, 8, 9):
                GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
                GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glUseProgram(0)
        if bloom_post_active:
            self._draw_bloom_post(framebuffer_width, framebuffer_height, post_effects, bloom_strength)
        else:
            self._bind_default_framebuffer()

    def _bind_material_textures(self, material_name: str) -> None:
        from OpenGL import GL

        texture_units = {
            "base": 1,
            "roughness": 2,
            "metallic": 3,
            "specular": 4,
            "normal": 5,
            "occlusion": 10,
            "emissive": 11,
            "opacity": 12,
            "height": 13,
        }
        uniform_names = {
            "base": ("u_base_map", "u_has_base_map"),
            "roughness": ("u_roughness_map", "u_has_roughness_map"),
            "metallic": ("u_metallic_map", "u_has_metallic_map"),
            "specular": ("u_specular_map", "u_has_specular_map"),
            "normal": ("u_normal_map", "u_has_normal_map"),
            "occlusion": ("u_occlusion_map", "u_has_occlusion_map"),
            "emissive": ("u_emissive_map", "u_has_emissive_map"),
            "opacity": ("u_opacity_map", "u_has_opacity_map"),
            "height": ("u_height_map", "u_has_height_map"),
        }
        maps = self.texture_plan.get(material_name)
        if maps is None and len(self.texture_plan) == 1:
            maps = next(iter(self.texture_plan.values()))
        if not isinstance(maps, Mapping):
            maps = {}
        textures = self.material_textures.get(material_name, {})
        if not textures and len(self.material_textures) == 1:
            textures = next(iter(self.material_textures.values()))
        GL.glUniform1f(
            self._uniform_location(self.program, "u_alpha_cutoff"),
            _material_float(maps, "alpha_cutoff", 0.02, lo=0.0, hi=1.0),
        )
        emissive = _material_vec3(maps, "emissive_factor")
        GL.glUniform3f(
            self._uniform_location(self.program, "u_emissive_factor"),
            float(emissive[0]),
            float(emissive[1]),
            float(emissive[2]),
        )
        GL.glUniform1i(
            self._uniform_location(self.program, "u_base_alpha_to_opacity"),
            1 if _base_alpha_to_opacity(material_name, maps) else 0,
        )
        for map_name, unit in texture_units.items():
            sampler_name, flag_name = uniform_names[map_name]
            texture_id = int(textures.get(map_name, 0) or 0)
            GL.glActiveTexture(GL.GL_TEXTURE0 + unit)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture_id)
            GL.glUniform1i(self._uniform_location(self.program, sampler_name), unit)
            GL.glUniform1i(self._uniform_location(self.program, flag_name), 1 if texture_id else 0)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            self.last_pos = event.position()
            if event.button() == Qt.MouseButton.LeftButton and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.drag_mode = "orbit"
            else:
                self.drag_mode = "pan"
            event.accept()
            return
        self.drag_mode = ""
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.last_pos is None:
            super().mouseMoveEvent(event)
            return
        if self.drag_mode == "orbit" and event.buttons() & Qt.MouseButton.LeftButton:
            pos = event.position()
            delta = pos - self.last_pos
            self.auto_fit_enabled = False
            self.auto_fit_pending = False
            self.state.pitch = max(-180.0, min(180.0, self.state.pitch + float(delta.y()) * 0.35))
            self.state.yaw = max(-180.0, min(180.0, self.state.yaw + float(delta.x()) * 0.35))
            self.last_pos = pos
            window = self.window()
            if hasattr(window, "sync_controls"):
                window.sync_controls()
            self.update()
            event.accept()
            return
        pan_buttons = Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton | Qt.MouseButton.RightButton
        if self.drag_mode == "pan" and event.buttons() & pan_buttons:
            pos = event.position()
            delta = pos - self.last_pos
            self.auto_fit_enabled = False
            self.auto_fit_pending = False
            pan_dx, pan_dy = _screen_pan_delta(
                float(delta.x()),
                float(delta.y()),
                viewport_width=max(1, self.width()),
                viewport_height=max(1, self.height()),
                camera_z=float(self.state.camera_z),
                fov_deg=max(10.0, min(120.0, float(self.state.fov_deg))),
            )
            self.state.pan_x = max(-20.0, min(20.0, float(self.state.pan_x) + pan_dx))
            self.state.pan_y = max(-20.0, min(20.0, float(self.state.pan_y) + pan_dy))
            self.last_pos = pos
            window = self.window()
            if hasattr(window, "sync_controls"):
                window.sync_controls()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self.last_pos = None
        self.drag_mode = ""
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        steps = float(delta) / 120.0
        if abs(steps) <= 1e-6:
            event.accept()
            return
        self.auto_fit_enabled = False
        self.auto_fit_pending = False
        self.state.zoom = max(0.03, min(40.0, self.state.zoom * (1.14 ** steps)))
        window = self.window()
        if hasattr(window, "sync_controls"):
            window.sync_controls()
        self.update()
        event.accept()


class GpuWindow(QMainWindow):
    def __init__(
        self,
        asset: Path,
        descriptor: dict,
        import_diag: dict,
        vertices: np.ndarray,
        mesh_diag: dict,
        hdri: HdrImage | None,
        hdri_diag: dict[str, Any],
        texture_plan: dict[str, dict[str, str]],
        texture_diag: dict[str, Any],
        texture_max_size: int,
        enable_shadow_map: bool,
        fit_padding: float,
        shadow_pcf_radius: float = DEFAULT_SHADOW_PCF_RADIUS,
        shadow_filter: str = DEFAULT_SHADOW_FILTER,
        shadow_light_type: str = DEFAULT_SHADOW_LIGHT_TYPE,
        shadow_pcss_blocker_radius: float = DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS,
        shadow_bias: float = DEFAULT_SHADOW_BIAS,
        shadow_normal_bias: float = DEFAULT_SHADOW_NORMAL_BIAS,
        shadow_spot_inner_angle: float = DEFAULT_SPOT_INNER_ANGLE,
        shadow_spot_outer_angle: float = DEFAULT_SPOT_OUTER_ANGLE,
        shadow_catcher_opacity: float = DEFAULT_SHADOW_CATCHER_OPACITY,
        shadow_catcher_softness: float = DEFAULT_SHADOW_CATCHER_SOFTNESS,
        shadow_catcher_matte_alpha: float = DEFAULT_SHADOW_CATCHER_MATTE_ALPHA,
        reflection_catcher_opacity: float = DEFAULT_REFLECTION_CATCHER_OPACITY,
        reflection_catcher_roughness: float = DEFAULT_REFLECTION_CATCHER_ROUGHNESS,
        reflection_catcher_softness: float = DEFAULT_REFLECTION_CATCHER_SOFTNESS,
        contact_reflection_strength: float = DEFAULT_CONTACT_REFLECTION_STRENGTH,
        contact_reflection_falloff: float = DEFAULT_CONTACT_REFLECTION_FALLOFF,
        tone_mapping: str = DEFAULT_TONE_MAPPING,
        tone_exposure: float = DEFAULT_TONE_EXPOSURE,
        tone_white_balance: float = DEFAULT_TONE_WHITE_BALANCE,
        tone_gamma: float = DEFAULT_TONE_GAMMA,
    ) -> None:
        super().__init__()
        self.asset = asset
        self.descriptor = descriptor
        self.import_diag = import_diag
        self.mesh_diag = mesh_diag
        self.hdri_diag = hdri_diag
        self.texture_diag = texture_diag
        self.fit_padding = float(fit_padding)
        self.state = GpuState()
        self.state.light_azimuth = float(hdri_diag.get("key_light_azimuth", self.state.light_azimuth) or self.state.light_azimuth)
        self.state.light_elevation = float(hdri_diag.get("key_light_elevation", self.state.light_elevation) or self.state.light_elevation)
        shadow_settings = normalize_shadow_settings({
            "shadow_filter": shadow_filter,
            "shadow_light_type": shadow_light_type,
            "shadow_pcf_radius": shadow_pcf_radius,
            "shadow_pcss_blocker_radius": shadow_pcss_blocker_radius,
            "shadow_bias": shadow_bias,
            "shadow_normal_bias": shadow_normal_bias,
            "shadow_spot_inner_angle": shadow_spot_inner_angle,
            "shadow_spot_outer_angle": shadow_spot_outer_angle,
        })
        self.state.shadow_filter = str(shadow_settings["filter"])
        self.state.shadow_light_type = str(shadow_settings["light_type"])
        self.state.shadow_pcf_radius = float(shadow_settings["pcf_radius_texels"])
        self.state.shadow_pcss_blocker_radius = float(shadow_settings["pcss_blocker_radius_texels"])
        self.state.shadow_bias = float(shadow_settings["bias"])
        self.state.shadow_normal_bias = float(shadow_settings["normal_bias"])
        self.state.shadow_spot_inner_angle = float(shadow_settings["spot_inner_angle"])
        self.state.shadow_spot_outer_angle = float(shadow_settings["spot_outer_angle"])
        catcher_settings = normalize_catcher_settings({
            "shadow_catcher_opacity": shadow_catcher_opacity,
            "shadow_catcher_softness": shadow_catcher_softness,
            "shadow_catcher_matte_alpha": shadow_catcher_matte_alpha,
            "reflection_catcher_opacity": reflection_catcher_opacity,
            "reflection_catcher_roughness": reflection_catcher_roughness,
            "reflection_catcher_softness": reflection_catcher_softness,
            "contact_reflection_strength": contact_reflection_strength,
            "contact_reflection_falloff": contact_reflection_falloff,
        })
        self.state.shadow_catcher_opacity = float(catcher_settings["shadow_catcher"]["opacity"])
        self.state.shadow_catcher_softness = float(catcher_settings["shadow_catcher"]["softness"])
        self.state.shadow_catcher_matte_alpha = float(catcher_settings["shadow_catcher"]["matte_alpha"])
        self.state.reflection_catcher_opacity = float(catcher_settings["reflection_catcher"]["opacity"])
        self.state.reflection_catcher_roughness = float(catcher_settings["reflection_catcher"]["roughness"])
        self.state.reflection_catcher_softness = float(catcher_settings["reflection_catcher"]["softness"])
        self.state.contact_reflection_strength = float(catcher_settings["reflection_catcher"]["contact_reflection_strength"])
        self.state.contact_reflection_falloff = float(catcher_settings["reflection_catcher"]["contact_reflection_falloff"])
        color_management = normalize_color_management_settings({
            "tone_mapping": tone_mapping,
            "tone_exposure": tone_exposure,
            "tone_white_balance": tone_white_balance,
            "tone_gamma": tone_gamma,
        })
        self.state.tone_mapping = str(color_management["tone_mapping"])
        self.state.tone_exposure = float(color_management["tone_exposure"])
        self.state.tone_white_balance = float(color_management["tone_white_balance"])
        self.state.tone_gamma = float(color_management["tone_gamma"])
        bounds = mesh_diag.get("normalized_bounds") if isinstance(mesh_diag.get("normalized_bounds"), Mapping) else {}
        mins = bounds.get("min", []) if isinstance(bounds, Mapping) else []
        if isinstance(mins, list) and len(mins) >= 2:
            self.state.ground_y = float(mins[1]) + 0.01
        self.setWindowTitle("AR/PBR GPU Render")
        self.resize(1280, 900)

        center = QWidget()
        layout = QVBoxLayout(center)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(QLabel(f"Asset: {asset}"))
        if hdri_diag.get("enabled"):
            layout.addWidget(QLabel(f"HDRI: {hdri_diag.get('path')}"))
        else:
            layout.addWidget(QLabel(f"HDRI: unavailable ({hdri_diag.get('reason', 'unknown')})"))
        self.gl_widget = GpuMeshWidget(
            vertices,
            self.state,
            hdri,
            mesh_diag,
            texture_plan,
            texture_max_size,
            enable_shadow_map,
            self.fit_padding,
            False,
            parent=center,
        )
        layout.addWidget(self.gl_widget, stretch=1)

        controls = QGroupBox("GPU Controls")
        form = QFormLayout(controls)
        self.pitch = self._angle_slider()
        self.yaw = self._angle_slider()
        self.roll = self._angle_slider()
        self.zoom = QDoubleSpinBox()
        self.zoom.setRange(0.1, 8.0)
        self.zoom.setSingleStep(0.1)
        self.zoom.setDecimals(2)
        self.camera_z = QDoubleSpinBox()
        self.camera_z.setRange(0.2, 20.0)
        self.camera_z.setSingleStep(0.1)
        self.camera_z.setDecimals(2)
        self.pan_x = self._pan_spinbox()
        self.pan_y = self._pan_spinbox()
        self.pan_z = self._pan_spinbox()
        self.ibl_exposure = self._float_slider(0.0, 8.0, 800)
        self.ibl_rotation = self._float_slider(-1.0, 1.0, 2000)
        self.light_azimuth = self._float_slider(-180.0, 180.0, 3600)
        self.light_elevation = self._float_slider(-20.0, 89.0, 1090)
        self.direct_intensity = self._float_slider(0.0, 2.0, 400)
        self.shadow_strength = self._float_slider(0.0, 1.0, 200)
        self.shadow_pcf_radius = self._float_slider(0.0, 4.0, 400)
        self.self_shadow_strength = self._float_slider(0.0, 1.0, 200)
        self.ground_y = self._float_slider(-1.2, 0.4, 320)
        self.ground_reflection = self._float_slider(0.0, 0.7, 140)
        self.shadow_catcher_opacity = self._float_slider(0.0, 1.0, 200)
        self.shadow_catcher_softness = self._float_slider(0.0, 1.0, 200)
        self.shadow_catcher_matte_alpha = self._float_slider(0.0, 1.0, 200)
        self.reflection_catcher_opacity = self._float_slider(0.0, 1.0, 200)
        self.reflection_catcher_roughness = self._float_slider(0.02, 1.0, 196)
        self.reflection_catcher_softness = self._float_slider(0.0, 1.0, 200)
        self.contact_reflection_strength = self._float_slider(0.0, 1.0, 200)
        self.contact_reflection_falloff = self._float_slider(0.05, 1.0, 190)
        self.pitch.valueChanged.connect(lambda value: self._set("pitch", float(value)))
        self.yaw.valueChanged.connect(lambda value: self._set("yaw", float(value)))
        self.roll.valueChanged.connect(lambda value: self._set("roll", float(value)))
        self.zoom.valueChanged.connect(lambda value: self._set("zoom", float(value)))
        self.camera_z.valueChanged.connect(lambda value: self._set("camera_z", float(value)))
        self.pan_x.valueChanged.connect(lambda value: self._set("pan_x", float(value)))
        self.pan_y.valueChanged.connect(lambda value: self._set("pan_y", float(value)))
        self.pan_z.valueChanged.connect(lambda value: self._set("pan_z", float(value)))
        self.ibl_exposure.valueChanged.connect(lambda value: self._set("ibl_exposure", self._float_slider_value(self.ibl_exposure, value)))
        self.ibl_rotation.valueChanged.connect(lambda value: self._set("ibl_rotation", self._float_slider_value(self.ibl_rotation, value)))
        self.light_azimuth.valueChanged.connect(lambda value: self._set("light_azimuth", self._float_slider_value(self.light_azimuth, value)))
        self.light_elevation.valueChanged.connect(lambda value: self._set("light_elevation", self._float_slider_value(self.light_elevation, value)))
        self.direct_intensity.valueChanged.connect(lambda value: self._set("direct_intensity", self._float_slider_value(self.direct_intensity, value)))
        self.shadow_strength.valueChanged.connect(lambda value: self._set("shadow_strength", self._float_slider_value(self.shadow_strength, value)))
        self.shadow_pcf_radius.valueChanged.connect(lambda value: self._set("shadow_pcf_radius", self._float_slider_value(self.shadow_pcf_radius, value)))
        self.self_shadow_strength.valueChanged.connect(lambda value: self._set("self_shadow_strength", self._float_slider_value(self.self_shadow_strength, value)))
        self.ground_y.valueChanged.connect(lambda value: self._set("ground_y", self._float_slider_value(self.ground_y, value)))
        self.ground_reflection.valueChanged.connect(lambda value: self._set("ground_reflection", self._float_slider_value(self.ground_reflection, value)))
        self.shadow_catcher_opacity.valueChanged.connect(lambda value: self._set("shadow_catcher_opacity", self._float_slider_value(self.shadow_catcher_opacity, value)))
        self.shadow_catcher_softness.valueChanged.connect(lambda value: self._set("shadow_catcher_softness", self._float_slider_value(self.shadow_catcher_softness, value)))
        self.shadow_catcher_matte_alpha.valueChanged.connect(lambda value: self._set("shadow_catcher_matte_alpha", self._float_slider_value(self.shadow_catcher_matte_alpha, value)))
        self.reflection_catcher_opacity.valueChanged.connect(lambda value: self._set("reflection_catcher_opacity", self._float_slider_value(self.reflection_catcher_opacity, value)))
        self.reflection_catcher_roughness.valueChanged.connect(lambda value: self._set("reflection_catcher_roughness", self._float_slider_value(self.reflection_catcher_roughness, value)))
        self.reflection_catcher_softness.valueChanged.connect(lambda value: self._set("reflection_catcher_softness", self._float_slider_value(self.reflection_catcher_softness, value)))
        self.contact_reflection_strength.valueChanged.connect(lambda value: self._set("contact_reflection_strength", self._float_slider_value(self.contact_reflection_strength, value)))
        self.contact_reflection_falloff.valueChanged.connect(lambda value: self._set("contact_reflection_falloff", self._float_slider_value(self.contact_reflection_falloff, value)))
        form.addRow("Pitch", self.pitch)
        form.addRow("Yaw", self.yaw)
        form.addRow("Roll", self.roll)
        form.addRow("Zoom", self.zoom)
        form.addRow("Camera Z", self.camera_z)
        form.addRow("Pan X", self.pan_x)
        form.addRow("Pan Y", self.pan_y)
        form.addRow("Pan Z", self.pan_z)
        form.addRow("IBL Exposure", self.ibl_exposure)
        form.addRow("IBL Rotation", self.ibl_rotation)
        form.addRow("Light Azimuth", self.light_azimuth)
        form.addRow("Light Elevation", self.light_elevation)
        form.addRow("Direct Strength", self.direct_intensity)
        form.addRow("Shadow Strength", self.shadow_strength)
        form.addRow("PCF Softness", self.shadow_pcf_radius)
        form.addRow("Self Shadow", self.self_shadow_strength)
        form.addRow("Ground Height", self.ground_y)
        form.addRow("Ground Reflection", self.ground_reflection)
        form.addRow("Shadow Catcher Opacity", self.shadow_catcher_opacity)
        form.addRow("Shadow Catcher Softness", self.shadow_catcher_softness)
        form.addRow("Shadow Matte Alpha", self.shadow_catcher_matte_alpha)
        form.addRow("Reflection Opacity", self.reflection_catcher_opacity)
        form.addRow("Reflection Roughness", self.reflection_catcher_roughness)
        form.addRow("Reflection Softness", self.reflection_catcher_softness)
        form.addRow("Contact Reflection", self.contact_reflection_strength)
        form.addRow("Reflection Falloff", self.contact_reflection_falloff)
        fit_view = QPushButton("Fit View")
        fit_view.clicked.connect(self.fit_view)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        row = QHBoxLayout()
        row.addWidget(fit_view)
        row.addWidget(reset)
        form.addRow(row)
        layout.addWidget(controls)

        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setPlainText(json.dumps(self._diagnostics(), ensure_ascii=False, indent=2, default=str))
        self.info.setMinimumWidth(390)

        splitter = QSplitter()
        splitter.addWidget(center)
        splitter.addWidget(self.info)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)
        self.sync_controls()

    def _angle_slider(self) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(-180, 180)
        return slider

    def _float_slider(self, minimum: float, maximum: float, steps: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, max(1, int(steps)))
        slider.setProperty("ar_minimum", float(minimum))
        slider.setProperty("ar_maximum", float(maximum))
        return slider

    def _pan_spinbox(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(-20.0, 20.0)
        spin.setSingleStep(0.05)
        spin.setDecimals(3)
        return spin

    def _float_slider_value(self, slider: QSlider, raw_value: int | None = None) -> float:
        minimum = float(slider.property("ar_minimum"))
        maximum = float(slider.property("ar_maximum"))
        value = slider.value() if raw_value is None else int(raw_value)
        ratio = value / max(float(slider.maximum()), 1.0)
        return minimum + (maximum - minimum) * ratio

    def _set_float_slider_value(self, slider: QSlider, value: float) -> None:
        minimum = float(slider.property("ar_minimum"))
        maximum = float(slider.property("ar_maximum"))
        clamped = max(minimum, min(maximum, float(value)))
        ratio = (clamped - minimum) / max(maximum - minimum, 1e-8)
        slider.setValue(int(round(ratio * slider.maximum())))

    def _diagnostics(self) -> dict[str, Any]:
        return {
            "asset": str(self.asset),
            "backend": "gpu_opengl",
            "controls": self.state.__dict__,
            "shadow": self.gl_widget.shadow_diagnostics() if hasattr(self, "gl_widget") else {},
            "catcher": catcher_diagnostics(self.state),
            "color_management": color_management_diagnostics(self.state),
            "hybrid_rendering": hybrid_rendering_diagnostics(self.state),
            "ray_gi_detail": ray_gi_detail_diagnostics(self.state),
            "ambient_occlusion_rendering": ambient_occlusion_diagnostics(self.state),
            "transmission_rendering": transmission_diagnostics(self.state),
            "clearcoat_rendering": clearcoat_diagnostics(self.state),
            "parallax_rendering": parallax_diagnostics(self.state),
            "displacement_rendering": displacement_diagnostics(self.state),
            "bevel_rendering": bevel_diagnostics(self.state),
            "material_layering": material_layering_diagnostics(self.state),
            "surface_rendering": surface_diagnostics(self.state),
            "subsurface_rendering": subsurface_diagnostics(self.state),
            "hair_groom_rendering": hair_groom_diagnostics(self.state),
            "cloth_sheen_rendering": cloth_sheen_diagnostics(self.state),
            "glint_sparkle_rendering": glint_sparkle_diagnostics(self.state),
            "caustics_rendering": caustics_diagnostics(self.state),
            "anisotropic_rendering": anisotropic_material_diagnostics(self.state),
            "microsurface_rendering": microsurface_diagnostics(self.state),
            "depth_of_field_rendering": depth_of_field_diagnostics(self.state),
            "post_effects_rendering": post_effects_diagnostics(self.state),
            "lens_effects_rendering": lens_effects_diagnostics(self.state),
            "lens_flare_rendering": lens_flare_diagnostics(self.state),
            "triplanar_rendering": triplanar_diagnostics(self.state),
            "frame_fit": getattr(self.gl_widget, "last_fit_diag", {}),
            "unlit_color": self.gl_widget.unlit_color_controls() if hasattr(self, "gl_widget") else {},
            "import": self.import_diag,
            "mesh": self.mesh_diag,
            "hdri": self.hdri_diag,
            "textures": self.texture_diag,
        }

    def fit_view(self) -> None:
        self.gl_widget.auto_fit_enabled = True
        self.state.pan_x = 0.0
        self.state.pan_y = 0.0
        self.state.pan_z = 0.0
        self.gl_widget.fit_current_view()
        self.gl_widget.auto_fit_pending = False
        self.sync_controls()
        self.gl_widget.update()

    def sync_controls(self) -> None:
        for widget, value in (
            (self.pitch, self.state.pitch),
            (self.yaw, self.state.yaw),
            (self.roll, self.state.roll),
        ):
            widget.blockSignals(True)
            widget.setValue(int(round(value)))
            widget.blockSignals(False)
        for widget, value in (
            (self.zoom, self.state.zoom),
            (self.camera_z, self.state.camera_z),
            (self.pan_x, self.state.pan_x),
            (self.pan_y, self.state.pan_y),
            (self.pan_z, self.state.pan_z),
        ):
            widget.blockSignals(True)
            widget.setValue(float(value))
            widget.blockSignals(False)
        for widget, value in (
            (self.ibl_exposure, self.state.ibl_exposure),
            (self.ibl_rotation, self.state.ibl_rotation),
            (self.light_azimuth, self.state.light_azimuth),
            (self.light_elevation, self.state.light_elevation),
            (self.direct_intensity, self.state.direct_intensity),
            (self.shadow_strength, self.state.shadow_strength),
            (self.shadow_pcf_radius, self.state.shadow_pcf_radius),
            (self.self_shadow_strength, self.state.self_shadow_strength),
            (self.ground_y, self.state.ground_y),
            (self.ground_reflection, self.state.ground_reflection),
            (self.shadow_catcher_opacity, self.state.shadow_catcher_opacity),
            (self.shadow_catcher_softness, self.state.shadow_catcher_softness),
            (self.shadow_catcher_matte_alpha, self.state.shadow_catcher_matte_alpha),
            (self.reflection_catcher_opacity, self.state.reflection_catcher_opacity),
            (self.reflection_catcher_roughness, self.state.reflection_catcher_roughness),
            (self.reflection_catcher_softness, self.state.reflection_catcher_softness),
            (self.contact_reflection_strength, self.state.contact_reflection_strength),
            (self.contact_reflection_falloff, self.state.contact_reflection_falloff),
        ):
            widget.blockSignals(True)
            self._set_float_slider_value(widget, float(value))
            widget.blockSignals(False)
        self.info.setPlainText(json.dumps(self._diagnostics(), ensure_ascii=False, indent=2, default=str))

    def _set(self, key: str, value: float) -> None:
        if key in {"pitch", "yaw", "roll", "zoom", "camera_z", "pan_x", "pan_y", "pan_z"}:
            self.gl_widget.auto_fit_enabled = False
            self.gl_widget.auto_fit_pending = False
        setattr(self.state, key, value)
        self.info.setPlainText(json.dumps(self._diagnostics(), ensure_ascii=False, indent=2, default=str))
        self.gl_widget.update()

    def reset(self) -> None:
        self.state.pitch = -10.0
        self.state.yaw = 72.0
        self.state.roll = 0.0
        self.state.camera_z = 3.25
        self.state.pan_x = 0.0
        self.state.pan_y = 0.0
        self.state.pan_z = 0.0
        self.state.ibl_exposure = 1.1
        self.state.ibl_rotation = 0.0
        self.state.tone_mapping = DEFAULT_TONE_MAPPING
        self.state.tone_exposure = DEFAULT_TONE_EXPOSURE
        self.state.tone_white_balance = DEFAULT_TONE_WHITE_BALANCE
        self.state.tone_gamma = DEFAULT_TONE_GAMMA
        self.state.hybrid_sample_count = DEFAULT_HYBRID_SAMPLE_COUNT
        self.state.diffuse_gi_strength = DEFAULT_DIFFUSE_GI_STRENGTH
        self.state.specular_gi_strength = DEFAULT_SPECULAR_GI_STRENGTH
        self.state.denoise_strength = DEFAULT_DENOISE_STRENGTH
        self.state.ray_gi_detail_mode = DEFAULT_RAY_GI_DETAIL_MODE
        self.state.ray_gi_max_bounces = DEFAULT_RAY_GI_MAX_BOUNCES
        self.state.ray_gi_diffuse_bounces = DEFAULT_RAY_GI_DIFFUSE_BOUNCES
        self.state.ray_gi_specular_bounces = DEFAULT_RAY_GI_SPECULAR_BOUNCES
        self.state.ray_gi_refraction_bounces = DEFAULT_RAY_GI_REFRACTION_BOUNCES
        self.state.ray_gi_direct_radiance_clamp = DEFAULT_DIRECT_RADIANCE_CLAMP
        self.state.ray_gi_indirect_radiance_clamp = DEFAULT_INDIRECT_RADIANCE_CLAMP
        self.state.ray_gi_light_sampling_mode = DEFAULT_LIGHT_SAMPLING_MODE
        self.state.ray_gi_light_sample_count = DEFAULT_LIGHT_SAMPLE_COUNT
        self.state.ray_gi_environment_sample_count = DEFAULT_ENVIRONMENT_SAMPLE_COUNT
        self.state.ray_gi_mis_enabled = False
        self.state.ray_gi_importance_sampling = False
        self.state.ray_gi_denoise_channels = ("beauty",)
        self.state.ray_gi_denoise_beauty = True
        self.state.ray_gi_denoise_diffuse = False
        self.state.ray_gi_denoise_specular = False
        self.state.ray_gi_denoise_transmission = False
        self.state.ray_gi_denoise_albedo_guided = False
        self.state.ray_gi_denoise_normal_guided = False
        self.state.ambient_occlusion_mode = DEFAULT_AMBIENT_OCCLUSION_MODE
        self.state.ao_strength = DEFAULT_AO_STRENGTH
        self.state.ao_radius = DEFAULT_AO_RADIUS
        self.state.ao_distance = DEFAULT_AO_DISTANCE
        self.state.ao_color = tuple(DEFAULT_AO_COLOR)
        self.state.ao_ambient = DEFAULT_AO_AMBIENT
        self.state.ao_diffuse = DEFAULT_AO_DIFFUSE
        self.state.ao_specular = DEFAULT_AO_SPECULAR
        self.state.transmission_mode = DEFAULT_TRANSMISSION_MODE
        self.state.transmission = DEFAULT_TRANSMISSION
        self.state.refraction_strength = DEFAULT_REFRACTION_STRENGTH
        self.state.refraction_depth_px = DEFAULT_REFRACTION_DEPTH_PX
        self.state.ior = DEFAULT_IOR
        self.state.thickness = DEFAULT_THICKNESS
        self.state.absorption_color = tuple(DEFAULT_ABSORPTION_COLOR)
        self.state.absorption_distance = DEFAULT_ABSORPTION_DISTANCE
        self.state.roughness_blur_strength = DEFAULT_ROUGHNESS_BLUR_STRENGTH
        self.state.clearcoat_mode = DEFAULT_CLEARCOAT_MODE
        self.state.clearcoat_strength = DEFAULT_CLEARCOAT_STRENGTH
        self.state.clearcoat_roughness = DEFAULT_CLEARCOAT_ROUGHNESS
        self.state.clearcoat_ior = DEFAULT_CLEARCOAT_IOR
        self.state.clearcoat_tint = tuple(DEFAULT_CLEARCOAT_TINT)
        self.state.parallax_mode = DEFAULT_PARALLAX_MODE
        self.state.parallax_strength = DEFAULT_PARALLAX_STRENGTH
        self.state.parallax_depth = DEFAULT_PARALLAX_DEPTH
        self.state.parallax_center = DEFAULT_PARALLAX_CENTER
        self.state.parallax_steps = DEFAULT_PARALLAX_STEPS
        self.state.displacement_mode = DEFAULT_DISPLACEMENT_MODE
        self.state.displacement_height_strength = DEFAULT_DISPLACEMENT_HEIGHT_STRENGTH
        self.state.displacement_height_scale = DEFAULT_DISPLACEMENT_HEIGHT_SCALE
        self.state.displacement_height_center = DEFAULT_DISPLACEMENT_HEIGHT_CENTER
        self.state.vector_displacement_strength = DEFAULT_VECTOR_DISPLACEMENT_STRENGTH
        self.state.vector_displacement_space = DEFAULT_VECTOR_DISPLACEMENT_SPACE
        self.state.displacement_subdivision_mode = DEFAULT_DISPLACEMENT_SUBDIVISION_MODE
        self.state.displacement_max_offset = DEFAULT_DISPLACEMENT_MAX_OFFSET
        self.state.displacement_parallax_fallback = DEFAULT_DISPLACEMENT_PARALLAX_FALLBACK
        self.state.bevel_mode = DEFAULT_BEVEL_MODE
        self.state.bevel_strength = DEFAULT_BEVEL_STRENGTH
        self.state.bevel_radius = DEFAULT_BEVEL_RADIUS
        self.state.bevel_edge_width = DEFAULT_BEVEL_EDGE_WIDTH
        self.state.bevel_samples = DEFAULT_BEVEL_SAMPLES
        self.state.material_layer_mode = DEFAULT_MATERIAL_LAYER_MODE
        self.state.material_layer_blend = DEFAULT_MATERIAL_LAYER_BLEND
        self.state.material_layer_color = tuple(DEFAULT_MATERIAL_LAYER_COLOR)
        self.state.material_layer_roughness = DEFAULT_MATERIAL_LAYER_ROUGHNESS
        self.state.material_layer_metallic = DEFAULT_MATERIAL_LAYER_METALLIC
        self.state.material_layer_alpha = DEFAULT_MATERIAL_LAYER_ALPHA
        self.state.material_layer_emissive_strength = DEFAULT_MATERIAL_LAYER_EMISSIVE_STRENGTH
        self.state.material_layer_mask_strength = DEFAULT_MATERIAL_LAYER_MASK_STRENGTH
        self.state.surface_override_strength = DEFAULT_SURFACE_OVERRIDE_STRENGTH
        self.state.surface_roughness = DEFAULT_SURFACE_ROUGHNESS
        self.state.surface_metallic = DEFAULT_SURFACE_METALLIC
        self.state.surface_reflectance = DEFAULT_SURFACE_REFLECTANCE
        self.state.subsurface_mode = DEFAULT_SUBSURFACE_MODE
        self.state.subsurface_strength = DEFAULT_SUBSURFACE_STRENGTH
        self.state.subsurface_color = tuple(DEFAULT_SUBSURFACE_COLOR)
        self.state.subsurface_radius = DEFAULT_SUBSURFACE_RADIUS
        self.state.subsurface_power = DEFAULT_SUBSURFACE_POWER
        self.state.subsurface_wrap = DEFAULT_SUBSURFACE_WRAP
        self.state.subsurface_thickness = DEFAULT_SUBSURFACE_THICKNESS
        self.state.hair_groom_mode = DEFAULT_HAIR_GROOM_MODE
        self.state.hair_groom_strength = DEFAULT_HAIR_GROOM_STRENGTH
        self.state.hair_groom_tint = tuple(DEFAULT_HAIR_GROOM_TINT)
        self.state.hair_primary_shift = DEFAULT_HAIR_PRIMARY_SHIFT
        self.state.hair_secondary_shift = DEFAULT_HAIR_SECONDARY_SHIFT
        self.state.hair_primary_roughness = DEFAULT_HAIR_PRIMARY_ROUGHNESS
        self.state.hair_secondary_roughness = DEFAULT_HAIR_SECONDARY_ROUGHNESS
        self.state.hair_secondary_strength = DEFAULT_HAIR_SECONDARY_STRENGTH
        self.state.hair_anisotropy = DEFAULT_HAIR_ANISOTROPY
        self.state.hair_rim_strength = DEFAULT_HAIR_RIM_STRENGTH
        self.state.cloth_sheen_mode = DEFAULT_CLOTH_SHEEN_MODE
        self.state.cloth_sheen_strength = DEFAULT_CLOTH_SHEEN_STRENGTH
        self.state.cloth_sheen_color = tuple(DEFAULT_CLOTH_SHEEN_COLOR)
        self.state.cloth_sheen_roughness = DEFAULT_CLOTH_SHEEN_ROUGHNESS
        self.state.cloth_sheen_edge_tint = tuple(DEFAULT_CLOTH_SHEEN_EDGE_TINT)
        self.state.cloth_sheen_fiber_strength = DEFAULT_CLOTH_SHEEN_FIBER_STRENGTH
        self.state.cloth_sheen_wrap = DEFAULT_CLOTH_SHEEN_WRAP
        self.state.cloth_sheen_retroreflection = DEFAULT_CLOTH_SHEEN_RETROREFLECTION
        self.state.glint_mode = DEFAULT_GLINT_MODE
        self.state.glint_strength = DEFAULT_GLINT_STRENGTH
        self.state.glint_color = tuple(DEFAULT_GLINT_COLOR)
        self.state.glint_density = DEFAULT_GLINT_DENSITY
        self.state.glint_scale = DEFAULT_GLINT_SCALE
        self.state.glint_threshold = DEFAULT_GLINT_THRESHOLD
        self.state.glint_sharpness = DEFAULT_GLINT_SHARPNESS
        self.state.glint_roughness_jitter = DEFAULT_GLINT_ROUGHNESS_JITTER
        self.state.caustics_mode = DEFAULT_CAUSTICS_MODE
        self.state.caustics_strength = DEFAULT_CAUSTICS_STRENGTH
        self.state.caustics_quality = DEFAULT_CAUSTICS_QUALITY
        self.state.caustics_sample_count = DEFAULT_CAUSTICS_SAMPLE_COUNT
        self.state.caustics_scale = DEFAULT_CAUSTICS_SCALE
        self.state.caustics_focus = DEFAULT_CAUSTICS_FOCUS
        self.state.caustics_radius = DEFAULT_CAUSTICS_RADIUS
        self.state.caustics_threshold = DEFAULT_CAUSTICS_THRESHOLD
        self.state.caustics_tint = tuple(DEFAULT_CAUSTICS_TINT)
        self.state.caustics_seed = DEFAULT_CAUSTICS_SEED
        self.state.anisotropic_mode = DEFAULT_ANISOTROPIC_MODE
        self.state.anisotropic_strength = DEFAULT_ANISOTROPIC_STRENGTH
        self.state.anisotropy = DEFAULT_ANISOTROPY
        self.state.anisotropic_rotation = DEFAULT_ANISOTROPIC_ROTATION
        self.state.anisotropic_tangent_weight = DEFAULT_ANISOTROPIC_TANGENT_WEIGHT
        self.state.clearcoat_anisotropy = DEFAULT_CLEARCOAT_ANISOTROPY
        self.state.thin_film_strength = DEFAULT_THIN_FILM_STRENGTH
        self.state.thin_film_thickness_nm = DEFAULT_THIN_FILM_THICKNESS_NM
        self.state.thin_film_ior = DEFAULT_THIN_FILM_IOR
        self.state.thin_film_tint = tuple(DEFAULT_THIN_FILM_TINT)
        self.state.newton_rings_strength = DEFAULT_NEWTON_RINGS_STRENGTH
        self.state.newton_rings_scale = DEFAULT_NEWTON_RINGS_SCALE
        self.state.anisotropic_seed = DEFAULT_ANISOTROPIC_SEED
        self.state.microsurface_mode = DEFAULT_MICROSURFACE_MODE
        self.state.detail_normal_strength = DEFAULT_DETAIL_NORMAL_STRENGTH
        self.state.detail_normal_scale = DEFAULT_DETAIL_NORMAL_SCALE
        self.state.detail_normal_blend = DEFAULT_DETAIL_NORMAL_BLEND
        self.state.detail_normal_seed = DEFAULT_DETAIL_NORMAL_SEED
        self.state.micro_roughness_strength = DEFAULT_MICRO_ROUGHNESS_STRENGTH
        self.state.micro_roughness_scale = DEFAULT_MICRO_ROUGHNESS_SCALE
        self.state.micro_roughness_contrast = DEFAULT_MICRO_ROUGHNESS_CONTRAST
        self.state.gloss_variation_strength = DEFAULT_GLOSS_VARIATION_STRENGTH
        self.state.gloss_bias = DEFAULT_GLOSS_BIAS
        self.state.specular_micro_occlusion = DEFAULT_SPECULAR_MICRO_OCCLUSION
        self.state.depth_of_field_mode = DEFAULT_DEPTH_OF_FIELD_MODE
        self.state.depth_of_field_strength = DEFAULT_DEPTH_OF_FIELD_STRENGTH
        self.state.dof_focus_depth = DEFAULT_DOF_FOCUS_DEPTH
        self.state.dof_focus_range = DEFAULT_DOF_FOCUS_RANGE
        self.state.dof_max_blur_px = DEFAULT_DOF_MAX_BLUR_PX
        self.state.dof_near_blur = DEFAULT_DOF_NEAR_BLUR
        self.state.dof_far_blur = DEFAULT_DOF_FAR_BLUR
        self.state.dof_bokeh_shape = DEFAULT_DOF_BOKEH_SHAPE
        self.state.post_effects_mode = DEFAULT_POST_EFFECTS_MODE
        self.state.bloom_strength = DEFAULT_BLOOM_STRENGTH
        self.state.bloom_radius = DEFAULT_BLOOM_RADIUS
        self.state.bloom_threshold = DEFAULT_BLOOM_THRESHOLD
        self.state.bloom_boost = DEFAULT_BLOOM_BOOST
        self.state.bloom_anamorphic_strength = DEFAULT_BLOOM_ANAMORPHIC_STRENGTH
        self.state.bloom_anamorphic_threshold = DEFAULT_BLOOM_ANAMORPHIC_THRESHOLD
        self.state.bloom_anamorphic_ratio = DEFAULT_BLOOM_ANAMORPHIC_RATIO
        self.state.vignette_strength = DEFAULT_VIGNETTE_STRENGTH
        self.state.vignette_radius = DEFAULT_VIGNETTE_RADIUS
        self.state.vignette_feather = DEFAULT_VIGNETTE_FEATHER
        self.state.grain_strength = DEFAULT_GRAIN_STRENGTH
        self.state.grain_scale = DEFAULT_GRAIN_SCALE
        self.state.grain_seed = DEFAULT_GRAIN_SEED
        self.state.sharpen_strength = DEFAULT_SHARPEN_STRENGTH
        self.state.sharpen_radius = DEFAULT_SHARPEN_RADIUS
        self.state.lens_effects_mode = DEFAULT_LENS_EFFECTS_MODE
        self.state.lens_distortion_strength = DEFAULT_LENS_DISTORTION_STRENGTH
        self.state.lens_distortion_k2 = DEFAULT_LENS_DISTORTION_K2
        self.state.chromatic_aberration_strength = DEFAULT_CHROMATIC_ABERRATION_STRENGTH
        self.state.chromatic_aberration_px = DEFAULT_CHROMATIC_ABERRATION_PX
        self.state.lens_center = tuple(DEFAULT_LENS_CENTER)
        self.state.lens_edge_falloff = DEFAULT_LENS_EDGE_FALLOFF
        self.state.lens_flare_mode = DEFAULT_LENS_FLARE_MODE
        self.state.lens_flare_strength = DEFAULT_LENS_FLARE_STRENGTH
        self.state.lens_flare_threshold = DEFAULT_LENS_FLARE_THRESHOLD
        self.state.lens_flare_radius = DEFAULT_LENS_FLARE_RADIUS
        self.state.lens_flare_ghost_count = DEFAULT_LENS_FLARE_GHOST_COUNT
        self.state.lens_flare_ghost_spacing = DEFAULT_LENS_FLARE_GHOST_SPACING
        self.state.lens_flare_tint = tuple(DEFAULT_LENS_FLARE_TINT)
        self.state.aperture_flare_strength = DEFAULT_APERTURE_FLARE_STRENGTH
        self.state.aperture_flare_blades = DEFAULT_APERTURE_FLARE_BLADES
        self.state.aperture_flare_rotation_deg = DEFAULT_APERTURE_FLARE_ROTATION_DEG
        self.state.aperture_flare_radius = DEFAULT_APERTURE_FLARE_RADIUS
        self.state.lens_dirt_strength = DEFAULT_LENS_DIRT_STRENGTH
        self.state.lens_dirt_density = DEFAULT_LENS_DIRT_DENSITY
        self.state.lens_dirt_scale = DEFAULT_LENS_DIRT_SCALE
        self.state.lens_scratch_strength = DEFAULT_LENS_SCRATCH_STRENGTH
        self.state.lens_scratch_density = DEFAULT_LENS_SCRATCH_DENSITY
        self.state.lens_scratch_length = DEFAULT_LENS_SCRATCH_LENGTH
        self.state.lens_flare_seed = DEFAULT_LENS_FLARE_SEED
        self.state.triplanar_mode = DEFAULT_TRIPLANAR_MODE
        self.state.triplanar_strength = DEFAULT_TRIPLANAR_STRENGTH
        self.state.triplanar_scale = DEFAULT_TRIPLANAR_SCALE
        self.state.triplanar_blend_sharpness = DEFAULT_TRIPLANAR_BLEND_SHARPNESS
        self.state.triplanar_offset = tuple(DEFAULT_TRIPLANAR_OFFSET)
        self.state.triplanar_space = "object"
        self.state.light_azimuth = float(self.hdri_diag.get("key_light_azimuth", 45.0) or 45.0)
        self.state.light_elevation = float(self.hdri_diag.get("key_light_elevation", 45.0) or 45.0)
        self.state.direct_intensity = 0.42
        self.state.shadow_filter = DEFAULT_SHADOW_FILTER
        self.state.shadow_light_type = DEFAULT_SHADOW_LIGHT_TYPE
        self.state.shadow_pcf_radius = DEFAULT_SHADOW_PCF_RADIUS
        self.state.shadow_pcss_blocker_radius = DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS
        self.state.shadow_bias = DEFAULT_SHADOW_BIAS
        self.state.shadow_normal_bias = DEFAULT_SHADOW_NORMAL_BIAS
        self.state.shadow_spot_inner_angle = DEFAULT_SPOT_INNER_ANGLE
        self.state.shadow_spot_outer_angle = DEFAULT_SPOT_OUTER_ANGLE
        self.state.self_shadow_strength = 0.45
        bounds = self.mesh_diag.get("normalized_bounds") if isinstance(self.mesh_diag.get("normalized_bounds"), Mapping) else {}
        mins = bounds.get("min", []) if isinstance(bounds, Mapping) else []
        self.state.ground_y = float(mins[1]) + 0.01 if isinstance(mins, list) and len(mins) >= 2 else -0.52
        self.state.shadow_strength = DEFAULT_SHADOW_STRENGTH
        self.state.ground_reflection = 0.05
        self.state.shadow_catcher_opacity = DEFAULT_SHADOW_CATCHER_OPACITY
        self.state.shadow_catcher_softness = DEFAULT_SHADOW_CATCHER_SOFTNESS
        self.state.shadow_catcher_matte_alpha = DEFAULT_SHADOW_CATCHER_MATTE_ALPHA
        self.state.reflection_catcher_opacity = DEFAULT_REFLECTION_CATCHER_OPACITY
        self.state.reflection_catcher_roughness = DEFAULT_REFLECTION_CATCHER_ROUGHNESS
        self.state.reflection_catcher_softness = DEFAULT_REFLECTION_CATCHER_SOFTNESS
        self.state.contact_reflection_strength = DEFAULT_CONTACT_REFLECTION_STRENGTH
        self.state.contact_reflection_falloff = DEFAULT_CONTACT_REFLECTION_FALLOFF
        self.gl_widget.auto_fit_enabled = True
        self.gl_widget.auto_fit_pending = True
        self.gl_widget.fit_current_view()
        self.gl_widget.auto_fit_pending = False
        self.sync_controls()
        self.gl_widget.update()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset", default=str(DEFAULT_EXTERNAL_ASSET))
    parser.add_argument("--hdri", default=str(DEFAULT_HDRI))
    parser.add_argument("--no-hdri", action="store_true")
    parser.add_argument("--max-triangles", type=int, default=2_000_000)
    parser.add_argument("--texture-max-size", type=int, default=1024)
    parser.add_argument("--fit-padding", type=float, default=DEFAULT_FRAME_FIT_PADDING)
    parser.add_argument("--enable-shadow-map", action="store_true")
    parser.add_argument("--shadow-pcf-radius", type=float, default=DEFAULT_SHADOW_PCF_RADIUS)
    parser.add_argument("--shadow-filter", choices=("pcf", "pcss"), default=DEFAULT_SHADOW_FILTER)
    parser.add_argument("--shadow-light-type", choices=("directional", "spot"), default=DEFAULT_SHADOW_LIGHT_TYPE)
    parser.add_argument("--shadow-pcss-blocker-radius", type=float, default=DEFAULT_SHADOW_PCSS_BLOCKER_RADIUS)
    parser.add_argument("--shadow-bias", type=float, default=DEFAULT_SHADOW_BIAS)
    parser.add_argument("--shadow-normal-bias", type=float, default=DEFAULT_SHADOW_NORMAL_BIAS)
    parser.add_argument("--shadow-spot-inner-angle", type=float, default=DEFAULT_SPOT_INNER_ANGLE)
    parser.add_argument("--shadow-spot-outer-angle", type=float, default=DEFAULT_SPOT_OUTER_ANGLE)
    parser.add_argument("--self-shadow-strength", type=float, default=0.45)
    parser.add_argument("--shadow-catcher-opacity", type=float, default=DEFAULT_SHADOW_CATCHER_OPACITY)
    parser.add_argument("--shadow-catcher-softness", type=float, default=DEFAULT_SHADOW_CATCHER_SOFTNESS)
    parser.add_argument("--shadow-catcher-matte-alpha", type=float, default=DEFAULT_SHADOW_CATCHER_MATTE_ALPHA)
    parser.add_argument("--reflection-catcher-opacity", type=float, default=DEFAULT_REFLECTION_CATCHER_OPACITY)
    parser.add_argument("--reflection-catcher-roughness", type=float, default=DEFAULT_REFLECTION_CATCHER_ROUGHNESS)
    parser.add_argument("--reflection-catcher-softness", type=float, default=DEFAULT_REFLECTION_CATCHER_SOFTNESS)
    parser.add_argument("--contact-reflection-strength", type=float, default=DEFAULT_CONTACT_REFLECTION_STRENGTH)
    parser.add_argument("--contact-reflection-falloff", type=float, default=DEFAULT_CONTACT_REFLECTION_FALLOFF)
    parser.add_argument("--tone-mapping", choices=("aces", "agx", "reinhard"), default=DEFAULT_TONE_MAPPING)
    parser.add_argument("--tone-exposure", type=float, default=DEFAULT_TONE_EXPOSURE)
    parser.add_argument("--tone-white-balance", type=float, default=DEFAULT_TONE_WHITE_BALANCE)
    parser.add_argument("--tone-gamma", type=float, default=DEFAULT_TONE_GAMMA)
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument("--preview-uv-v-flip", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--pitch", type=float, default=None)
    parser.add_argument("--yaw", type=float, default=None)
    parser.add_argument("--roll", type=float, default=None)
    parser.add_argument("--zoom", type=float, default=None)
    parser.add_argument("--pan-x", type=float, default=None)
    parser.add_argument("--pan-y", type=float, default=None)
    parser.add_argument("--pan-z", type=float, default=None)
    parser.add_argument("--screenshot", default="")
    parser.add_argument("--screenshot-delay-ms", type=int, default=900)
    parser.add_argument("--view-state-out", default="", help="Write current view and GPU control state JSON on exit.")
    args = parser.parse_args()

    global PREVIEW_UV_V_FLIP_MODE
    PREVIEW_UV_V_FLIP_MODE = str(args.preview_uv_v_flip)

    asset = Path(args.asset)
    hdri_path = None if args.no_hdri else Path(args.hdri)
    hdri, hdri_diag = _load_hdri_or_none(hdri_path)
    descriptor, import_diag = import_asset(
        asset,
        settings={"max_triangles_per_geometry": max(100, int(args.max_triangles))},
    )
    vertices, mesh_diag = build_vertex_buffer(descriptor)
    texture_plan, texture_diag = _resolve_material_texture_plan(asset, descriptor)
    texture_diag["upload_max_size"] = int(args.texture_max_size)
    shadow_settings = normalize_shadow_settings({
        "shadow_filter": args.shadow_filter,
        "shadow_light_type": args.shadow_light_type,
        "shadow_pcf_radius": args.shadow_pcf_radius,
        "shadow_pcss_blocker_radius": args.shadow_pcss_blocker_radius,
        "shadow_bias": args.shadow_bias,
        "shadow_normal_bias": args.shadow_normal_bias,
        "shadow_spot_inner_angle": args.shadow_spot_inner_angle,
        "shadow_spot_outer_angle": args.shadow_spot_outer_angle,
    })
    shadow_radius = float(shadow_settings["pcf_radius_texels"])
    self_shadow_strength = max(0.0, min(1.0, float(args.self_shadow_strength)))
    catcher_settings = normalize_catcher_settings({
        "shadow_catcher_opacity": args.shadow_catcher_opacity,
        "shadow_catcher_softness": args.shadow_catcher_softness,
        "shadow_catcher_matte_alpha": args.shadow_catcher_matte_alpha,
        "reflection_catcher_opacity": args.reflection_catcher_opacity,
        "reflection_catcher_roughness": args.reflection_catcher_roughness,
        "reflection_catcher_softness": args.reflection_catcher_softness,
        "contact_reflection_strength": args.contact_reflection_strength,
        "contact_reflection_falloff": args.contact_reflection_falloff,
    })
    color_management = normalize_color_management_settings({
        "tone_mapping": args.tone_mapping,
        "tone_exposure": args.tone_exposure,
        "tone_white_balance": args.tone_white_balance,
        "tone_gamma": args.tone_gamma,
    })
    shadow_config = shadow_filter_diagnostics(
        GpuState(
            shadow_pcf_radius=shadow_radius,
            shadow_filter=str(shadow_settings["filter"]),
            shadow_light_type=str(shadow_settings["light_type"]),
            shadow_pcss_blocker_radius=float(shadow_settings["pcss_blocker_radius_texels"]),
            shadow_bias=float(shadow_settings["bias"]),
            shadow_normal_bias=float(shadow_settings["normal_bias"]),
            shadow_spot_inner_angle=float(shadow_settings["spot_inner_angle"]),
            shadow_spot_outer_angle=float(shadow_settings["spot_outer_angle"]),
            self_shadow_strength=self_shadow_strength,
            shadow_catcher_opacity=float(catcher_settings["shadow_catcher"]["opacity"]),
            shadow_catcher_softness=float(catcher_settings["shadow_catcher"]["softness"]),
            shadow_catcher_matte_alpha=float(catcher_settings["shadow_catcher"]["matte_alpha"]),
            reflection_catcher_opacity=float(catcher_settings["reflection_catcher"]["opacity"]),
            reflection_catcher_roughness=float(catcher_settings["reflection_catcher"]["roughness"]),
            reflection_catcher_softness=float(catcher_settings["reflection_catcher"]["softness"]),
            contact_reflection_strength=float(catcher_settings["reflection_catcher"]["contact_reflection_strength"]),
            contact_reflection_falloff=float(catcher_settings["reflection_catcher"]["contact_reflection_falloff"]),
            tone_mapping=str(color_management["tone_mapping"]),
            tone_exposure=float(color_management["tone_exposure"]),
            tone_white_balance=float(color_management["tone_white_balance"]),
            tone_gamma=float(color_management["tone_gamma"]),
        ),
        enable_shadow_map=bool(args.enable_shadow_map),
        shadow_supported=bool(args.enable_shadow_map),
        shadow_size=int(DEFAULT_SHADOW_MAP_SIZE),
    )
    texture_diag["shadow_filter"] = shadow_config
    texture_diag["catcher"] = catcher_settings
    texture_diag["color_management"] = color_management
    texture_diag["shadow_map_default"] = (
        (
            f"enabled; {shadow_settings['light_type']} {shadow_settings['filter']} "
            f"{SHADOW_PCF_KERNEL} radius {shadow_radius:.2f} texels"
        )
        if args.enable_shadow_map
        else "disabled; using contact shadow fallback"
    )
    if args.probe_only:
        print(json.dumps({
            "asset": str(asset),
            "hdri": hdri_diag,
            "import": import_diag,
            "mesh": mesh_diag,
            "textures": texture_diag,
            "shadow": shadow_config,
        }, ensure_ascii=False, indent=2, default=str))
        return 0

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    from app.window_placement import install_global_window_placement

    install_global_window_placement(app)
    window = GpuWindow(
        asset,
        descriptor,
        import_diag,
        vertices,
        mesh_diag,
        hdri,
        hdri_diag,
        texture_plan,
        texture_diag,
        max(256, int(args.texture_max_size)),
        bool(args.enable_shadow_map),
        max(0.0, min(0.5, float(args.fit_padding))),
        shadow_radius,
        str(shadow_settings["filter"]),
        str(shadow_settings["light_type"]),
        float(shadow_settings["pcss_blocker_radius_texels"]),
        float(shadow_settings["bias"]),
        float(shadow_settings["normal_bias"]),
        float(shadow_settings["spot_inner_angle"]),
        float(shadow_settings["spot_outer_angle"]),
        float(catcher_settings["shadow_catcher"]["opacity"]),
        float(catcher_settings["shadow_catcher"]["softness"]),
        float(catcher_settings["shadow_catcher"]["matte_alpha"]),
        float(catcher_settings["reflection_catcher"]["opacity"]),
        float(catcher_settings["reflection_catcher"]["roughness"]),
        float(catcher_settings["reflection_catcher"]["softness"]),
        float(catcher_settings["reflection_catcher"]["contact_reflection_strength"]),
        float(catcher_settings["reflection_catcher"]["contact_reflection_falloff"]),
        str(color_management["tone_mapping"]),
        float(color_management["tone_exposure"]),
        float(color_management["tone_white_balance"]),
        float(color_management["tone_gamma"]),
    )
    window.show()
    app.processEvents()
    window.fit_view()
    view_state_path = Path(args.view_state_out).expanduser().resolve() if str(args.view_state_out or "").strip() else None

    def _write_view_state() -> None:
        if view_state_path is None:
            return
        view_state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "asset": str(asset),
            "view": {
                "pitch": float(window.state.pitch),
                "yaw": float(window.state.yaw),
                "roll": float(window.state.roll),
                "zoom": float(window.state.zoom),
                "camera_z": float(window.state.camera_z),
                "fov_deg": float(window.state.fov_deg),
                "pan_x": float(window.state.pan_x),
                "pan_y": float(window.state.pan_y),
                "pan_z": float(window.state.pan_z),
            },
            "controls": dict(window.state.__dict__),
        }
        view_state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(str(view_state_path))

    app.aboutToQuit.connect(_write_view_state)
    orientation_changed = False
    for key, value in (
        ("pitch", args.pitch),
        ("yaw", args.yaw),
        ("roll", args.roll),
    ):
        if value is None:
            continue
        setattr(window.state, key, float(value))
        orientation_changed = True
    if orientation_changed:
        window.gl_widget.auto_fit_enabled = True
        window.gl_widget.fit_current_view()
        window.gl_widget.auto_fit_pending = False
    if args.zoom is not None:
        window.state.zoom = max(0.03, min(40.0, float(args.zoom)))
        window.gl_widget.auto_fit_enabled = False
        window.gl_widget.auto_fit_pending = False
    pan_changed = False
    for key, value in (
        ("pan_x", args.pan_x),
        ("pan_y", args.pan_y),
        ("pan_z", args.pan_z),
    ):
        if value is None:
            continue
        setattr(window.state, key, max(-20.0, min(20.0, float(value))))
        pan_changed = True
    if pan_changed:
        window.gl_widget.auto_fit_enabled = False
        window.gl_widget.auto_fit_pending = False
    if orientation_changed or args.zoom is not None or pan_changed:
        window.sync_controls()
        window.gl_widget.update()
        app.processEvents()
    screenshot_path = str(args.screenshot or "").strip()
    if screenshot_path:
        out_path = Path(screenshot_path).expanduser().resolve()

        def _capture_and_quit() -> None:
            try:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                window.gl_widget.update()
                app.processEvents()
                image = window.gl_widget.grabFramebuffer()
                if image.isNull():
                    image = window.grab().toImage()
                image.save(str(out_path), "PNG")
                print(str(out_path))
            finally:
                app.quit()

        QTimer.singleShot(max(100, int(args.screenshot_delay_ms)), _capture_and_quit)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
