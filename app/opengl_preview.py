"""GPU-rendered video preview widget.

Replaces the legacy QLabel + setPixmap preview path. Uploads each
decoded frame as a 2D texture and applies colour grading inside a
fragment shader so slider drags don't pin the CPU at 4K. Aspect-fits
the frame inside the widget (letterbox) and clears the surround to a
matte colour.

Shader implements the same maths as ``apply_to_rgb`` for everything
except the Hue-vs-Hue curve, which stays on the CPU branch (the
project_player still applies it for the QImage signal that scopes /
popout listen to). When a grade has active hue-vs-hue points, the GL
widget draws the texture without further grading and the CPU-graded
QImage is used as the source instead.
"""
from __future__ import annotations

import os
import sys
import math
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QSurfaceFormat, QVector2D, QVector3D, QVector4D
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from app.ar_pbr.bevel import normalize_bevel_settings
from app.ar_pbr.ambient_occlusion import (
    normalize_ambient_occlusion_settings,
    normalize_packet_ambient_occlusion_settings,
)
from app.ar_pbr.clearcoat import normalize_clearcoat_settings
from app.ar_pbr.cloth import normalize_cloth_sheen_settings
from app.ar_pbr.depth_of_field import normalize_depth_of_field_settings
from app.ar_pbr.glint import normalize_glint_sparkle_settings
from app.ar_pbr.hair import normalize_hair_groom_settings
from app.ar_pbr.parallax import normalize_parallax_settings
from app.ar_pbr.post_effects import normalize_post_effects_settings
from app.ar_pbr.preview_diagnostics import overlay_diagnostics_payload
from app.ar_pbr.shadow import normalize_shadow_settings
from app.ar_pbr.hybrid_rendering import normalize_hybrid_render_settings
from app.ar_pbr.material_layering import normalize_material_layering_settings
from app.ar_pbr.subsurface import normalize_subsurface_settings
from app.ar_pbr.surface import normalize_surface_settings
from app.ar_pbr.tone_mapping import normalize_color_management_settings
from app.ar_pbr.triplanar import normalize_triplanar_settings
from app.ar_pbr.transmission import normalize_transmission_settings


# Raw GL constants we reach for by integer value because PySide6 doesn't
# expose them as a stable enum across versions.
_GL_FLOAT = 0x1406
_GL_TRIANGLES = 0x0004
_GL_TRIANGLE_STRIP = 0x0005
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_ONE = 0x0001
_GL_SCISSOR_TEST = 0x0C11
_GL_COLOR_BUFFER_BIT = 0x4000
_GL_DEPTH_BUFFER_BIT = 0x0100
_GL_DEPTH_TEST = 0x0B71
_GL_LEQUAL = 0x0203
_GL_CULL_FACE = 0x0B44
_GL_FRONT = 0x0404
_GL_BACK = 0x0405
_GL_TEXTURE_2D = 0x0DE1
_GL_TEXTURE0 = 0x84C0
_GL_TEXTURE_MIN_FILTER = 0x2801
_GL_TEXTURE_MAG_FILTER = 0x2800
_GL_TEXTURE_WRAP_S = 0x2802
_GL_TEXTURE_WRAP_T = 0x2803
_GL_LINEAR = 0x2601
_GL_CLAMP_TO_EDGE = 0x812F
_AR_PBR_LEGACY_TEXTURE_VERTEX_STRIDE_FLOATS = 20
_AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS = 23


def _env_flag(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().casefold() in {"1", "true", "yes", "on"}


def _format_debug_bytes(value: object) -> str:
    try:
        amount = max(0.0, float(value or 0.0))
    except Exception:
        amount = 0.0
    if amount >= 1024.0 * 1024.0:
        return f"{amount / (1024.0 * 1024.0):.1f} MB"
    if amount >= 1024.0:
        return f"{amount / 1024.0:.1f} KB"
    return f"{int(amount)} B"


_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec2 a_uv;
uniform vec2 u_quad_scale;
varying vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos * u_quad_scale, 0.0, 1.0);
}
"""

# Fragment shader mirrors apply_to_rgb in app/color_grading.py:
#   contrast around 0.5 → brightness → offset wheel →
#   3-way wheels (luma masks) → saturation toward graded luma.
# Hue-vs-Hue is intentionally absent (handled by the CPU branch).
_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
uniform sampler2D u_tex;
uniform bool  u_has_grade;
uniform float u_brightness;
uniform float u_contrast;
uniform float u_saturation;
uniform vec3  u_offset_rgb;
uniform vec3  u_shadows_rgb;
uniform vec3  u_midtones_rgb;
uniform vec3  u_highlights_rgb;
uniform float u_blur_sigma;
uniform vec2  u_tex_size;
uniform bool  u_fx_enabled;
uniform float u_fx_sharpen;
uniform float u_fx_vignette;
uniform float u_fx_vignette_feather;
uniform float u_fx_chroma_aberration;
uniform bool  u_chroma_enabled;
uniform float u_chroma_key_hue;
uniform float u_chroma_hue_range;
uniform float u_chroma_sat_min;
uniform float u_chroma_val_min;
uniform float u_chroma_spill;
uniform vec3  u_chroma_bg;
const vec3 LUMA709 = vec3(0.2126, 0.7152, 0.0722);

// Separable Gaussian blur baked into a single pass via a 13-tap kernel.
// Weights are precomputed for a standard Gaussian (sigma normalised to 1)
// and the pixel step is scaled by u_blur_sigma / u_tex_size.
// The outer loop samples on the diagonal (+45 deg) and anti-diagonal
// (-45 deg) so one 13-tap pass approximates a 2-D separable blur very
// cheaply without a FBO.  For sigma <=0 the function returns the
// plain texture sample.
vec3 gaussian_blur(sampler2D tex, vec2 uv) {
    if (u_blur_sigma <= 0.01) return texture2D(tex, uv).rgb;
    vec2 px = u_blur_sigma / u_tex_size;
    // 13-tap Gaussian weights (sigma=1, truncated at +-3 sigma, normalised).
    // Offsets: 0,1,2,3,4,5,6 — symmetric pair for +-1..6
    float w0 = 0.19859;
    float w1 = 0.17570;
    float w2 = 0.12098;
    float w3 = 0.06476;
    float w4 = 0.02697;
    float w5 = 0.00874;
    float w6 = 0.00220;
    // Horizontal pass accumulator
    vec3 hsum = texture2D(tex, uv).rgb * w0;
    hsum += (texture2D(tex, uv + vec2( px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2( px.x, 0.0)).rgb) * w1;
    hsum += (texture2D(tex, uv + vec2(2.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(2.0*px.x, 0.0)).rgb) * w2;
    hsum += (texture2D(tex, uv + vec2(3.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(3.0*px.x, 0.0)).rgb) * w3;
    hsum += (texture2D(tex, uv + vec2(4.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(4.0*px.x, 0.0)).rgb) * w4;
    hsum += (texture2D(tex, uv + vec2(5.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(5.0*px.x, 0.0)).rgb) * w5;
    hsum += (texture2D(tex, uv + vec2(6.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(6.0*px.x, 0.0)).rgb) * w6;
    // Vertical pass on the horizontally-blurred result — approximated by
    // sampling along the Y axis.  True separable blur needs a FBO; this
    // single-pass approximation is visually indistinguishable for sigma<16.
    vec3 vsum = texture2D(tex, uv).rgb * w0;
    vsum += (texture2D(tex, uv + vec2(0.0,  px.y)).rgb
           + texture2D(tex, uv - vec2(0.0,  px.y)).rgb) * w1;
    vsum += (texture2D(tex, uv + vec2(0.0, 2.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 2.0*px.y)).rgb) * w2;
    vsum += (texture2D(tex, uv + vec2(0.0, 3.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 3.0*px.y)).rgb) * w3;
    vsum += (texture2D(tex, uv + vec2(0.0, 4.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 4.0*px.y)).rgb) * w4;
    vsum += (texture2D(tex, uv + vec2(0.0, 5.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 5.0*px.y)).rgb) * w5;
    vsum += (texture2D(tex, uv + vec2(0.0, 6.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 6.0*px.y)).rgb) * w6;
    // Average the two orthogonal passes for a reasonable 2-D approximation.
    return (hsum + vsum) * 0.5;
}

vec3 gaussian_blur_sigma(sampler2D tex, vec2 uv, float sigma) {
    if (sigma <= 0.01) return texture2D(tex, uv).rgb;
    vec2 px = sigma / u_tex_size;
    float w0 = 0.19859;
    float w1 = 0.17570;
    float w2 = 0.12098;
    float w3 = 0.06476;
    vec3 sum = texture2D(tex, uv).rgb * w0;
    sum += (texture2D(tex, uv + vec2( px.x, 0.0)).rgb
          + texture2D(tex, uv - vec2( px.x, 0.0)).rgb) * w1;
    sum += (texture2D(tex, uv + vec2(2.0*px.x, 0.0)).rgb
          + texture2D(tex, uv - vec2(2.0*px.x, 0.0)).rgb) * w2;
    sum += (texture2D(tex, uv + vec2(3.0*px.x, 0.0)).rgb
          + texture2D(tex, uv - vec2(3.0*px.x, 0.0)).rgb) * w3;
    return sum;
}

vec3 rgb_to_hsv(vec3 c) {
    float maxc = max(c.r, max(c.g, c.b));
    float minc = min(c.r, min(c.g, c.b));
    float d = maxc - minc;
    float h = 0.0;
    if (d > 0.00001) {
        if (maxc == c.r) {
            h = mod((c.g - c.b) / d, 6.0);
        } else if (maxc == c.g) {
            h = ((c.b - c.r) / d) + 2.0;
        } else {
            h = ((c.r - c.g) / d) + 4.0;
        }
        h = h / 6.0;
        if (h < 0.0) h += 1.0;
    }
    float s = maxc <= 0.00001 ? 0.0 : d / maxc;
    return vec3(h, s, maxc);
}

vec3 apply_clip_fx(vec2 uv) {
    vec3 col = texture2D(u_tex, uv).rgb;
    if (!u_fx_enabled) return col;
    if (u_fx_chroma_aberration > 0.001) {
        float shift = max(1.0, u_fx_chroma_aberration * 3.0);
        vec2 off = vec2(shift / max(u_tex_size.x, 1.0), 0.0);
        col.r = texture2D(u_tex, clamp(uv + off, vec2(0.0), vec2(1.0))).r;
        col.b = texture2D(u_tex, clamp(uv - off, vec2(0.0), vec2(1.0))).b;
    }
    if (u_fx_sharpen > 0.001) {
        vec3 blurred = gaussian_blur_sigma(u_tex, uv, 3.0);
        col = clamp(col * (1.0 + u_fx_sharpen) - blurred * u_fx_sharpen, 0.0, 1.0);
    }
    if (u_fx_vignette > 0.001) {
        float feather = max(0.01, u_fx_vignette_feather);
        float dist = length((uv - vec2(0.5)) * 2.0);
        float mask = clamp(1.0 - (dist - (1.0 - feather)) / feather, 0.0, 1.0);
        float mult = (1.0 - u_fx_vignette) + u_fx_vignette * mask;
        col *= mult;
    }
    if (u_chroma_enabled) {
        vec3 hsv = rgb_to_hsv(col);
        float hue = hsv.x * 180.0;
        float hue_diff = abs(hue - u_chroma_key_hue);
        hue_diff = min(hue_diff, 180.0 - hue_diff);
        bool key = (
            hue_diff <= u_chroma_hue_range
            && hsv.y * 255.0 >= u_chroma_sat_min
            && hsv.z * 255.0 >= u_chroma_val_min
        );
        float denom = max(1.0, u_chroma_hue_range * 0.5);
        float alpha = key ? clamp(1.0 - (u_chroma_hue_range - hue_diff) / denom, 0.0, 1.0) : 1.0;
        if (u_chroma_spill > 0.001 && alpha < 1.0) {
            float strength = (1.0 - alpha) * clamp(u_chroma_spill, 0.0, 1.0);
            float avg_rb = (col.r + col.b) * 0.5;
            col.g = mix(col.g, avg_rb, strength);
        }
        col = mix(u_chroma_bg, col, alpha);
    }
    return clamp(col, 0.0, 1.0);
}

void main() {
    vec3 col = u_fx_enabled ? apply_clip_fx(v_uv) : gaussian_blur(u_tex, v_uv);
    if (u_has_grade) {
        col = (col - vec3(0.5)) * u_contrast + vec3(0.5) + vec3(u_brightness);
        col += u_offset_rgb;
        float lum = dot(col, LUMA709);
        float s_mask = clamp(1.0 - 2.0 * lum, 0.0, 1.0);
        float h_mask = clamp(2.0 * lum - 1.0, 0.0, 1.0);
        float m_mask = 1.0 - s_mask - h_mask;
        col += u_shadows_rgb    * s_mask
             + u_midtones_rgb   * m_mask
             + u_highlights_rgb * h_mask;
        float lum2 = dot(col, LUMA709);
        col = mix(vec3(lum2), col, u_saturation);
        col = clamp(col, 0.0, 1.0);
    }
    gl_FragColor = vec4(col, 1.0);
}
"""


def _wheel_offset_vec(x: int, y: int) -> tuple[float, float, float]:
    """Inline copy of color_grading._wheel_to_rgb_offset for the
    uniform values. Kept here so this module doesn't import the colour-
    grading module at GL-render time (circular-import guard for the
    project_player path)."""
    nx = x / 100.0
    ny = y / 100.0
    AMP = 0.20
    dR = AMP * (0.50 * nx + 0.30 * ny)
    dG = AMP * (-0.10 * nx - 0.40 * ny)
    dB = AMP * (-0.50 * nx + 0.30 * ny)
    return dR, dG, dB


def _identity_uniforms() -> dict:
    return {
        "has_grade": False,
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "offset_rgb": (0.0, 0.0, 0.0),
        "shadows_rgb": (0.0, 0.0, 0.0),
        "midtones_rgb": (0.0, 0.0, 0.0),
        "highlights_rgb": (0.0, 0.0, 0.0),
    }


def _identity_clip_effects() -> dict:
    return {
        "enabled": False,
        "sharpen": 0.0,
        "vignette": 0.0,
        "vignette_feather": 0.5,
        "chroma_aberration": 0.0,
        "chroma_enabled": False,
        "chroma_key_hue": 60.0,
        "chroma_hue_range": 30.0,
        "chroma_sat_min": 60.0,
        "chroma_val_min": 60.0,
        "chroma_spill": 0.0,
        "chroma_bg": (0.0, 0.0, 0.0),
    }


def clip_effects_to_uniforms(effects) -> dict:
    if not isinstance(effects, dict) or not effects.get("enabled"):
        return _identity_clip_effects()
    out = _identity_clip_effects()
    filters = effects.get("filters") if isinstance(effects.get("filters"), dict) else None
    chroma = effects.get("chroma") if isinstance(effects.get("chroma"), dict) else None
    if filters is not None:
        out["sharpen"] = max(0.0, float(filters.get("sharpen", 0.0) or 0.0))
        out["vignette"] = max(0.0, min(1.0, float(filters.get("vignette", 0.0) or 0.0)))
        out["vignette_feather"] = max(0.01, min(1.0, float(filters.get("vignette_feather", 0.5) or 0.5)))
        out["chroma_aberration"] = max(0.0, float(filters.get("chroma_aberration", 0.0) or 0.0))
    if chroma is not None:
        out["chroma_enabled"] = True
        out["chroma_key_hue"] = max(0.0, min(179.0, float(chroma.get("key_hue", 60.0) or 60.0)))
        out["chroma_hue_range"] = max(1.0, min(179.0, float(chroma.get("hue_range", 30.0) or 30.0)))
        out["chroma_sat_min"] = max(0.0, min(255.0, float(chroma.get("sat_min", 60.0) or 60.0)))
        out["chroma_val_min"] = max(0.0, min(255.0, float(chroma.get("val_min", 60.0) or 60.0)))
        out["chroma_spill"] = max(0.0, min(1.0, float(chroma.get("spill_suppress", 0.0) or 0.0)))
        bg = chroma.get("bg", (0.0, 0.0, 0.0))
        try:
            out["chroma_bg"] = (
                max(0.0, min(1.0, float(bg[0]))),
                max(0.0, min(1.0, float(bg[1]))),
                max(0.0, min(1.0, float(bg[2]))),
            )
        except Exception:
            out["chroma_bg"] = (0.0, 0.0, 0.0)
    out["enabled"] = (
        out["sharpen"] > 0.001
        or out["vignette"] > 0.001
        or out["chroma_aberration"] > 0.001
        or bool(out["chroma_enabled"])
    )
    return out


def grade_to_uniforms(grade) -> dict:
    """Translate a ``ColorGrade`` (or None) into the shader uniform dict.

    Hue-vs-Hue presence forces ``has_grade=False`` so the GL preview
    falls back to drawing the texture as-is — the texture in that case
    will already be CPU-graded by the project_player."""
    if grade is None:
        return _identity_uniforms()
    has_hue = any(abs(d) > 0.5 for _h, d in getattr(grade, "hue_vs_hue", ()))
    has_luma = any(
        getattr(grade, f"{r}_l", 0) != 0
        for r in ("shadows", "midtones", "highlights", "offset")
    )
    is_identity = False
    try:
        is_identity = grade.is_identity()
    except Exception:
        pass
    if is_identity:
        return _identity_uniforms()
    if has_hue or has_luma:
        # CPU pre-graded fallback — both hue-vs-hue and per-region
        # luma stay outside the current shader. The ``apply_to_rgb``
        # path already handles them; the GL widget just blits the
        # already-graded texture.
        return _identity_uniforms()
    return {
        "has_grade": True,
        "brightness": grade.brightness / 100.0,
        "contrast": 1.0 + grade.contrast / 100.0,
        "saturation": 1.0 + grade.saturation / 100.0,
        "offset_rgb": _wheel_offset_vec(grade.offset_x, grade.offset_y),
        "shadows_rgb": _wheel_offset_vec(grade.shadows_x, grade.shadows_y),
        "midtones_rgb": _wheel_offset_vec(grade.midtones_x, grade.midtones_y),
        "highlights_rgb": _wheel_offset_vec(
            grade.highlights_x, grade.highlights_y,
        ),
    }


def _aspect_fit_scale(
    fw: int, fh: int, ww: int, wh: int,
) -> tuple[float, float]:
    """Letterbox the (fw, fh) frame inside the (ww, wh) widget. Returns
    NDC scale factors (sx, sy) for the unit quad."""
    if ww <= 0 or wh <= 0 or fw <= 0 or fh <= 0:
        return 1.0, 1.0
    f_ar = fw / fh
    w_ar = ww / wh
    if f_ar > w_ar:
        return 1.0, w_ar / f_ar
    return f_ar / w_ar, 1.0


_SPINE_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec2 a_uv;
varying vec2 v_uv;
void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_uv = a_uv;
}
"""


_SPINE_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
uniform sampler2D u_tex;
void main() {
    gl_FragColor = texture2D(u_tex, v_uv);
}
"""


_MMD_VERTEX_SHADER = """
#version 120
attribute vec3 a_pos;
attribute vec3 a_normal;
attribute vec2 a_uv;
attribute vec4 a_bone_indices;
attribute vec4 a_bone_weights;
attribute vec3 a_morph_delta0;
attribute vec3 a_morph_delta1;
uniform vec3 u_center;
uniform float u_model_scale;
uniform vec3 u_rotation;
uniform vec2 u_offset;
uniform vec2 u_viewport_size;
uniform float u_outline_width;
uniform int u_gpu_skinning;
uniform sampler2D u_bone_tex;
uniform float u_bone_tex_width;
uniform float u_morph_weight0;
uniform float u_morph_weight1;
varying vec2 v_uv;
varying vec3 v_normal;
varying vec3 v_model_normal;
varying vec3 v_view;
varying vec3 v_model_pos;

mat3 rot_x(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat3(1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c);
}

mat3 rot_y(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat3(c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c);
}

mat3 rot_z(float a) {
    float c = cos(a);
    float s = sin(a);
    return mat3(c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0);
}

mat4 fetch_bone_matrix(float bone_index) {
    float base = max(0.0, floor(bone_index + 0.5)) * 4.0;
    float width = max(1.0, u_bone_tex_width);
    vec4 c0 = texture2D(u_bone_tex, vec2((base + 0.5) / width, 0.5));
    vec4 c1 = texture2D(u_bone_tex, vec2((base + 1.5) / width, 0.5));
    vec4 c2 = texture2D(u_bone_tex, vec2((base + 2.5) / width, 0.5));
    vec4 c3 = texture2D(u_bone_tex, vec2((base + 3.5) / width, 0.5));
    return mat4(c0, c1, c2, c3);
}

void main() {
    mat3 r = rot_y(u_rotation.y) * rot_x(u_rotation.x) * rot_z(u_rotation.z);
    vec3 safe_normal = length(a_normal) > 0.0001 ? normalize(a_normal) : vec3(0.0, 1.0, 0.0);
    vec3 morphed_pos = a_pos + a_morph_delta0 * u_morph_weight0 + a_morph_delta1 * u_morph_weight1;
    vec3 source_pos = morphed_pos;
    vec3 source_normal = safe_normal;
    if (u_gpu_skinning == 1) {
        vec4 p4 = vec4(morphed_pos, 1.0);
        vec4 n4 = vec4(safe_normal, 0.0);
        vec4 skinned_pos = vec4(0.0);
        vec3 skinned_normal = vec3(0.0);
        float total_weight = 0.0;
        for (int i = 0; i < 4; ++i) {
            float weight = a_bone_weights[i];
            if (weight > 0.00001) {
                mat4 bone = fetch_bone_matrix(a_bone_indices[i]);
                skinned_pos += (bone * p4) * weight;
                skinned_normal += (bone * n4).xyz * weight;
                total_weight += weight;
            }
        }
        if (total_weight > 0.00001) {
            source_pos = skinned_pos.xyz / total_weight;
            source_normal = length(skinned_normal) > 0.0001 ? normalize(skinned_normal) : safe_normal;
        }
    }
    vec3 local = source_pos - u_center + source_normal * u_outline_width;
    vec3 p = r * (local * u_model_scale);
    vec3 n = normalize(r * source_normal);
    float camera = 3.2;
    float z = p.z + camera;
    float persp = camera / max(0.35, z);
    float aspect = u_viewport_size.x / max(1.0, u_viewport_size.y);
    vec2 ndc = vec2((p.x * persp) / max(0.1, aspect), p.y * persp) + u_offset;
    float depth = clamp((z - 0.15) / 6.0, 0.0, 1.0);
    gl_Position = vec4(ndc, depth * 2.0 - 1.0, 1.0);
    v_uv = a_uv;
    v_normal = n;
    v_model_normal = source_normal;
    v_view = normalize(vec3(0.0, 0.0, camera) - p);
    v_model_pos = source_pos;
}
"""


_MMD_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
varying vec3 v_normal;
varying vec3 v_model_normal;
varying vec3 v_view;
varying vec3 v_model_pos;
uniform sampler2D u_tex;
uniform sampler2D u_sphere_tex;
uniform sampler2D u_toon_tex;
uniform sampler2D u_shadow_tex;
uniform int u_has_tex;
uniform int u_has_sphere_tex;
uniform int u_has_toon_tex;
uniform int u_has_shadow_map;
uniform int u_sphere_mode;
uniform int u_outline;
uniform int u_bloom_mask;
uniform int u_output_premultiplied;
uniform int u_shadow_debug;
uniform int u_receive_shadow;
uniform vec4 u_diffuse;
uniform vec3 u_ambient;
uniform vec3 u_specular;
uniform float u_specular_strength;
uniform vec4 u_edge_color;
uniform vec3 u_light_dir;
uniform vec3 u_fill_dir;
uniform vec3 u_key_color;
uniform vec3 u_fill_color;
uniform vec3 u_rim_color;
uniform vec3 u_sky_color;
uniform vec3 u_ground_color;
uniform vec3 u_toon_shadow_color;
uniform vec2 u_uv_min;
uniform vec2 u_uv_max;
uniform vec3 u_bounds_min;
uniform vec3 u_bounds_max;
uniform vec3 u_group_bounds_min;
uniform vec3 u_group_bounds_max;
uniform vec3 u_shadow_center;
uniform float u_shadow_radius;
uniform float u_key_intensity;
uniform float u_fill_intensity;
uniform float u_rim_intensity;
uniform float u_ambient_intensity;
uniform float u_shadow_strength;
uniform float u_soft_shadow_strength;
uniform float u_shadow_map_size;
uniform float u_shadow_softness;
uniform float u_shadow_bias;
uniform float u_contact_shadow_strength;
uniform float u_alpha_cutoff;
uniform int u_material_class;
uniform float u_toon_ao_strength;
uniform float u_skin_warmth;
uniform float u_highlight_clamp;
uniform float u_rim_boost;
uniform float u_sphere_strength;
uniform float u_matcap_specular_strength;
uniform float u_toon_highlight_strength;
uniform float u_toon_highlight_size;
uniform float u_hair_angel_ring_strength;
uniform float u_hair_angel_ring_center;
uniform float u_hair_angel_ring_width;
uniform float u_eye_highlight_strength;
uniform float u_lip_specular_strength;
uniform float u_wrap_diffuse;
uniform float u_emissive_strength;
uniform float u_skin_shadow_soften;
uniform float u_skin_shadow_lift;

float sample_shadow(vec3 model_pos, vec3 normal, vec3 light_dir) {
    if (u_has_shadow_map != 1 || u_shadow_radius <= 0.001 || u_soft_shadow_strength <= 0.001) {
        return 0.0;
    }
    vec3 light = normalize(-light_dir);
    float normal_light = clamp(abs(dot(normalize(normal), light)), 0.08, 1.0);
    vec3 up = abs(light.y) > 0.92 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 sx = normalize(cross(up, light));
    vec3 sy = cross(light, sx);
    vec3 local = model_pos - u_shadow_center;
    vec2 uv = vec2(dot(local, sx), dot(local, sy)) / (u_shadow_radius * 2.0) + vec2(0.5);
    if (uv.x <= 0.002 || uv.x >= 0.998 || uv.y <= 0.002 || uv.y >= 0.998) {
        return 0.0;
    }
    float current = clamp(0.5 - dot(local, light) / (u_shadow_radius * 2.0), 0.0, 1.0);
    float bias = max(u_shadow_bias, u_shadow_bias * (1.0 + (1.0 - normal_light) * 3.0));
    float texel = max(0.5, u_shadow_softness) / max(1.0, u_shadow_map_size);
    float shadow = 0.0;
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            float closest = texture2D(u_shadow_tex, uv + vec2(float(x), float(y)) * texel).r;
            shadow += current - bias > closest ? 1.0 : 0.0;
        }
    }
    return shadow / 9.0;
}

void main() {
    vec4 tex = u_has_tex == 1 ? texture2D(u_tex, v_uv) : vec4(1.0);
    vec4 base = tex * u_diffuse;
    vec2 uv_span = max(u_uv_max - u_uv_min, vec2(0.0001));
    vec2 local_uv = clamp((v_uv - u_uv_min) / uv_span, vec2(0.0), vec2(1.0));
    vec3 group_span = max(u_group_bounds_max - u_group_bounds_min, vec3(0.0001));
    vec3 group_local = clamp((v_model_pos - u_group_bounds_min) / group_span, vec3(0.0), vec3(1.0));
    if (base.a <= u_alpha_cutoff) {
        discard;
    }
    if (u_bloom_mask == 1) {
        float emissive = clamp(u_emissive_strength, 0.0, 3.0);
        float lum = dot(base.rgb, vec3(0.2126, 0.7152, 0.0722));
        float bright = smoothstep(0.68, 1.0, lum) * 0.24;
        float glow_power = max(emissive, bright);
        if (glow_power <= 0.001) {
            gl_FragColor = vec4(0.0);
            return;
        }
        vec3 glow = clamp(base.rgb * glow_power, 0.0, 1.0);
        gl_FragColor = vec4(glow * base.a, base.a);
        return;
    }
    if (u_outline == 1) {
        float edge_alpha = u_edge_color.a * base.a;
        vec3 edge_rgb = u_edge_color.rgb;
        if (u_output_premultiplied == 1) {
            edge_rgb *= edge_alpha;
        }
        gl_FragColor = vec4(edge_rgb, edge_alpha);
        return;
    }
    vec3 n = normalize(v_normal);
    vec3 view_dir = normalize(v_view);
    vec3 light = normalize(-u_light_dir);
    vec3 fill_light = normalize(-u_fill_dir);
    if (dot(n, view_dir) < 0.0) {
        n = -n;
    }
    float raw_ndotl = max(dot(n, light), 0.0);
    float wrap = clamp(u_wrap_diffuse, 0.0, 0.45);
    float ndotl = clamp((dot(n, light) + wrap) / (1.0 + wrap), 0.0, 1.0);
    ndotl = mix(raw_ndotl, ndotl, smoothstep(0.001, 0.45, wrap));
    float fill = max(dot(n, fill_light), 0.0);
    float band = 0.34;
    vec3 ramp_shadow_color = vec3(0.34);
    if (ndotl > 0.82) {
        band = 0.92;
    } else if (ndotl > 0.48) {
        band = 0.68;
    }
    if (u_has_toon_tex == 1) {
        vec3 toon = texture2D(u_toon_tex, vec2(clamp(ndotl, 0.02, 0.98), 0.5)).rgb;
        band = mix(0.34, 0.92, clamp(dot(toon, vec3(0.3333)), 0.0, 1.0));
        ramp_shadow_color = clamp(u_toon_shadow_color, vec3(0.0), vec3(1.0));
    }
    band = mix(1.0, band, clamp(u_shadow_strength, 0.0, 1.0));
    float soft_shadow = u_receive_shadow == 1 ? sample_shadow(v_model_pos, v_model_normal, u_light_dir) : 0.0;
    if (u_shadow_debug == 1) {
        gl_FragColor = vec4(vec3(soft_shadow), base.a);
        return;
    }
    float shadow_soften = clamp(u_skin_shadow_soften, 0.0, 0.75);
    float shadow_mix = clamp(soft_shadow * u_soft_shadow_strength * (1.0 - shadow_soften), 0.0, 0.85);
    float hemi = clamp(n.y * 0.5 + 0.5, 0.0, 1.0);
    vec3 hemi_color = mix(u_ground_color, u_sky_color, hemi) * clamp(u_ambient_intensity, 0.0, 1.0);
    vec3 ambient = clamp(u_ambient, vec3(0.10), vec3(0.48)) * 0.18 + hemi_color;
    vec3 key_lit = u_key_color * band * clamp(u_key_intensity, 0.0, 2.0);
    vec3 fill_lit = u_fill_color * fill * clamp(u_fill_intensity, 0.0, 1.0);
    vec3 rgb = base.rgb * (ambient + key_lit * 0.72 + fill_lit * 0.34);
    vec3 ramp_shadow_rgb = base.rgb * ramp_shadow_color * (ambient + u_key_color * 0.24 + fill_lit * 0.12);
    rgb = mix(rgb, ramp_shadow_rgb, shadow_mix);
    vec3 half_dir = normalize(light + view_dir);
    float ndoth = max(dot(n, half_dir), 0.0);
    vec3 sphere_sample = vec3(0.0);
    if (u_has_sphere_tex == 1) {
        vec2 sphere_uv = clamp(n.xy * 0.5 + vec2(0.5), vec2(0.0), vec2(1.0));
        sphere_sample = texture2D(u_sphere_tex, sphere_uv).rgb;
        float sphere_strength = clamp(u_sphere_strength, 0.0, 1.4);
        if (u_sphere_mode == 1) {
            rgb *= mix(vec3(1.0), sphere_sample, 0.55 * sphere_strength);
        } else if (u_sphere_mode == 2) {
            rgb += sphere_sample * (0.22 * sphere_strength);
        }
    }
    float matcap_specular_strength = clamp(u_matcap_specular_strength, 0.0, 1.5);
    if (matcap_specular_strength > 0.001) {
        float spec_power = clamp(u_specular_strength, 4.0, 96.0);
        float blinn = pow(ndoth, spec_power) * raw_ndotl;
        float fresnel = pow(1.0 - max(dot(n, view_dir), 0.0), 2.0);
        vec3 spec_tint = max(u_specular, vec3(0.08));
        if (u_has_sphere_tex == 1) {
            spec_tint = max(sphere_sample, vec3(0.08));
        }
        rgb += spec_tint * (0.16 + fresnel * 0.42) * matcap_specular_strength;
        rgb += max(u_specular, vec3(0.02)) * blinn * (0.10 + 0.20 * matcap_specular_strength);
    }
    float toon_highlight_strength = clamp(u_toon_highlight_strength, 0.0, 1.5);
    if (toon_highlight_strength > 0.001) {
        float center = clamp(u_toon_highlight_size, 0.10, 0.92);
        float toon_band = 1.0 - smoothstep(0.035, 0.18, abs(ndoth - center));
        float light_gate = smoothstep(0.05, 0.58, raw_ndotl + fill * 0.38);
        float face_gate = smoothstep(0.02, 0.62, max(dot(n, view_dir), 0.0));
        vec3 toon_tint = base.rgb * 0.42 + u_key_color * 0.22 + vec3(0.08);
        rgb += toon_tint * toon_band * light_gate * face_gate * toon_highlight_strength;
    }
    float hair_angel_ring_strength = clamp(u_hair_angel_ring_strength, 0.0, 1.5);
    if (hair_angel_ring_strength > 0.001) {
        float ring_x = group_local.x * 2.0 - 1.0;
        float ring_y = group_local.y;
        float ring_center = clamp(u_hair_angel_ring_center, 0.20, 0.90) + ring_x * ring_x * 0.055;
        float ring_width = clamp(u_hair_angel_ring_width, 0.015, 0.18);
        float ring_band = 1.0 - smoothstep(ring_width, ring_width * 2.75, abs(ring_y - ring_center));
        float center_gate = 1.0 - smoothstep(0.48, 0.92, abs(ring_x));
        float front_gate = smoothstep(0.00, 0.52, max(dot(n, view_dir), 0.0));
        float upper_gate = smoothstep(0.18, 0.42, group_local.y) * (1.0 - smoothstep(0.96, 1.0, group_local.y));
        float light_gate = 0.58 + 0.42 * smoothstep(0.02, 0.52, raw_ndotl + fill * 0.42);
        float strand_gate = 0.78 + 0.22 * smoothstep(0.10, 0.90, local_uv.x);
        vec3 ring_tint = base.rgb * 0.54 + u_key_color * 0.16 + u_rim_color * 0.10 + vec3(0.075);
        rgb += ring_tint * ring_band * center_gate * front_gate * upper_gate * light_gate * strand_gate * hair_angel_ring_strength;
    }
    float eye_highlight_strength = clamp(u_eye_highlight_strength, 0.0, 1.5);
    if (eye_highlight_strength > 0.001) {
        float glint_a = 1.0 - smoothstep(0.0, 0.145, length((local_uv - vec2(0.34, 0.72)) * vec2(1.0, 1.55)));
        float glint_b = 1.0 - smoothstep(0.0, 0.070, length((local_uv - vec2(0.64, 0.62)) * vec2(1.35, 1.0)));
        float glint_c = 1.0 - smoothstep(0.0, 0.055, length((local_uv - vec2(0.46, 0.82)) * vec2(1.20, 1.60)));
        float iris_gleam = smoothstep(0.52, 0.92, ndoth) * smoothstep(0.04, 0.42, raw_ndotl + fill * 0.40);
        float eye_glint = clamp(glint_a * 0.82 + glint_b * 0.55 + glint_c * 0.42 + iris_gleam * 0.22, 0.0, 1.0);
        rgb += vec3(1.0, 0.96, 0.84) * eye_glint * eye_highlight_strength;
    }
    float lip_specular_strength = clamp(u_lip_specular_strength, 0.0, 1.5);
    if (lip_specular_strength > 0.001) {
        float lip_line = 1.0 - smoothstep(0.0, 0.095, abs(local_uv.y - 0.61));
        lip_line *= smoothstep(0.10, 0.28, local_uv.x) * (1.0 - smoothstep(0.72, 0.93, local_uv.x));
        float lip_blinn = pow(ndoth, clamp(u_specular_strength * 1.35, 18.0, 96.0));
        lip_blinn *= smoothstep(0.02, 0.52, raw_ndotl + fill * 0.34);
        vec3 lip_tint = max(base.rgb, vec3(0.08)) * 0.32 + vec3(0.33, 0.16, 0.13);
        rgb += lip_tint * (lip_line * 0.34 + lip_blinn * 0.48) * lip_specular_strength;
    }
    float rim = pow(1.0 - max(dot(n, view_dir), 0.0), 3.0);
    rgb += base.rgb * u_rim_color * rim * clamp(u_rim_intensity * u_rim_boost, 0.0, 1.4);
    float height = clamp(
        (v_model_pos.y - u_bounds_min.y) / max(0.001, u_bounds_max.y - u_bounds_min.y),
        0.0,
        1.0
    );
    float lower_zone = 1.0 - smoothstep(0.06, 0.36, height);
    float underside = smoothstep(0.02, 0.60, -n.y);
    float grazing = smoothstep(0.20, 0.88, 1.0 - abs(dot(n, normalize(v_view))));
    float toon_ao = clamp(
        (lower_zone * 0.46 + underside * 0.22 + grazing * 0.08) * u_toon_ao_strength,
        0.0,
        0.18
    );
    rgb = mix(rgb, ramp_shadow_rgb, toon_ao);
    float contact = (1.0 - smoothstep(0.02, 0.24, height)) * (1.0 - ndotl * 0.35);
    rgb = mix(rgb, ramp_shadow_rgb, clamp(contact * u_contact_shadow_strength, 0.0, 0.55));
    if (u_skin_warmth > 0.001) {
        float skin_shadow_zone = clamp((1.0 - ndotl) * 0.55 + shadow_mix * 0.70 + toon_ao * 1.40, 0.0, 1.0);
        vec3 peach_lift = base.rgb * vec3(0.18, 0.095, 0.045) + vec3(0.014, 0.006, 0.002);
        rgb += peach_lift * skin_shadow_zone * clamp(u_skin_shadow_lift, 0.0, 0.6);
        vec3 skin_floor = base.rgb * vec3(0.48, 0.36, 0.30) + vec3(0.030, 0.015, 0.006);
        rgb = mix(rgb, max(rgb, skin_floor), skin_shadow_zone * clamp(u_skin_shadow_lift, 0.0, 0.6));
        vec3 warm_skin = rgb * vec3(1.035, 0.985, 0.940) + base.rgb * vec3(0.018, 0.010, 0.004);
        rgb = mix(rgb, warm_skin, clamp(u_skin_warmth, 0.0, 1.0));
    }
    if (u_emissive_strength > 0.001) {
        rgb += base.rgb * clamp(u_emissive_strength, 0.0, 3.0) * 0.32;
    }
    if (u_highlight_clamp < 0.999) {
        vec3 over = max(rgb - vec3(u_highlight_clamp), vec3(0.0));
        rgb -= over * 0.72;
    }
    vec4 out_color = vec4(clamp(rgb, 0.0, 1.0), base.a);
    if (u_output_premultiplied == 1) {
        out_color.rgb *= out_color.a;
    }
    gl_FragColor = out_color;
}
"""


_MMD_SHADOW_VERTEX_SHADER = """
#version 120
attribute vec3 a_pos;
attribute vec2 a_uv;
attribute vec4 a_bone_indices;
attribute vec4 a_bone_weights;
attribute vec3 a_morph_delta0;
attribute vec3 a_morph_delta1;
uniform vec3 u_shadow_center;
uniform vec3 u_shadow_light_dir;
uniform float u_shadow_radius;
uniform int u_gpu_skinning;
uniform sampler2D u_bone_tex;
uniform float u_bone_tex_width;
uniform float u_morph_weight0;
uniform float u_morph_weight1;
varying vec2 v_uv;
varying float v_depth;

mat4 fetch_bone_matrix(float bone_index) {
    float base = max(0.0, floor(bone_index + 0.5)) * 4.0;
    float width = max(1.0, u_bone_tex_width);
    vec4 c0 = texture2D(u_bone_tex, vec2((base + 0.5) / width, 0.5));
    vec4 c1 = texture2D(u_bone_tex, vec2((base + 1.5) / width, 0.5));
    vec4 c2 = texture2D(u_bone_tex, vec2((base + 2.5) / width, 0.5));
    vec4 c3 = texture2D(u_bone_tex, vec2((base + 3.5) / width, 0.5));
    return mat4(c0, c1, c2, c3);
}

void main() {
    vec3 morphed_pos = a_pos + a_morph_delta0 * u_morph_weight0 + a_morph_delta1 * u_morph_weight1;
    vec3 source_pos = morphed_pos;
    if (u_gpu_skinning == 1) {
        vec4 p4 = vec4(morphed_pos, 1.0);
        vec4 skinned_pos = vec4(0.0);
        float total_weight = 0.0;
        for (int i = 0; i < 4; ++i) {
            float weight = a_bone_weights[i];
            if (weight > 0.00001) {
                skinned_pos += (fetch_bone_matrix(a_bone_indices[i]) * p4) * weight;
                total_weight += weight;
            }
        }
        if (total_weight > 0.00001) {
            source_pos = skinned_pos.xyz / total_weight;
        }
    }
    vec3 light = normalize(-u_shadow_light_dir);
    vec3 up = abs(light.y) > 0.92 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 sx = normalize(cross(up, light));
    vec3 sy = cross(light, sx);
    vec3 local = source_pos - u_shadow_center;
    vec2 xy = vec2(dot(local, sx), dot(local, sy)) / max(0.001, u_shadow_radius);
    v_depth = clamp(0.5 - dot(local, light) / max(0.001, u_shadow_radius * 2.0), 0.0, 1.0);
    gl_Position = vec4(xy, v_depth * 2.0 - 1.0, 1.0);
    v_uv = a_uv;
}
"""


_MMD_SHADOW_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
varying float v_depth;
uniform sampler2D u_tex;
uniform int u_has_tex;
uniform float u_alpha_cutoff;

void main() {
    vec4 tex = u_has_tex == 1 ? texture2D(u_tex, v_uv) : vec4(1.0);
    if (tex.a <= u_alpha_cutoff) {
        discard;
    }
    gl_FragColor = vec4(v_depth, v_depth, v_depth, 1.0);
}
"""


_MMD_COMPOSITE_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec2 a_uv;
varying vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos, 0.0, 1.0);
}
"""


_MMD_COMPOSITE_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
uniform sampler2D u_layer_tex;
uniform sampler2D u_bloom_tex;
uniform vec2 u_texel_size;
uniform float u_bloom_strength;
uniform float u_bloom_radius;
uniform float u_bloom_threshold;
uniform vec2 u_ground_shadow_center;
uniform vec2 u_ground_shadow_radius;
uniform vec3 u_ground_shadow_color;
uniform float u_ground_shadow_strength;

vec3 bloom_sample(vec2 uv) {
    vec4 src = texture2D(u_bloom_tex, clamp(uv, vec2(0.0), vec2(1.0)));
    float lum = dot(src.rgb, vec3(0.2126, 0.7152, 0.0722));
    float threshold = clamp(u_bloom_threshold, 0.0, 1.0);
    float excess = max(lum - threshold, 0.0);
    float contribution = clamp(excess / max(1.0 - threshold, 0.001), 0.0, 1.0);
    float gate = smoothstep(0.0, 0.18, excess) * contribution;
    return src.rgb * gate * clamp(src.a, 0.0, 1.0);
}

vec3 convolution_tap(vec2 uv, vec2 offset_px, float weight) {
    return bloom_sample(uv + u_texel_size * offset_px) * weight;
}

vec3 convolution_axis(vec2 uv, vec2 dir, float radius, float weight, inout float weight_sum) {
    vec2 axis = normalize(dir);
    vec3 bloom = vec3(0.0);
    float w0 = 0.070 * weight;
    float w1 = 0.040 * weight;
    float w2 = 0.018 * weight;
    bloom += convolution_tap(uv,  axis * radius * 0.72, w0);
    bloom += convolution_tap(uv, -axis * radius * 0.72, w0);
    bloom += convolution_tap(uv,  axis * radius * 1.45, w1);
    bloom += convolution_tap(uv, -axis * radius * 1.45, w1);
    bloom += convolution_tap(uv,  axis * radius * 2.35, w2);
    bloom += convolution_tap(uv, -axis * radius * 2.35, w2);
    weight_sum += (w0 + w1 + w2) * 2.0;
    return bloom;
}

vec3 convolution_bloom(vec2 uv, float radius) {
    vec3 bloom = bloom_sample(uv) * 0.090;
    float weight_sum = 0.090;
    for (int i = 0; i < 24; ++i) {
        float fi = float(i) + 0.5;
        float t = fi / 24.0;
        float r = sqrt(t);
        float angle = fi * 2.39996323;
        vec2 dir = vec2(cos(angle), sin(angle));
        float halo_weight = exp(-2.65 * t) * (0.036 + 0.024 * (1.0 - r));
        bloom += convolution_tap(uv, dir * radius * r * 1.92, halo_weight);
        weight_sum += halo_weight;
    }
    bloom += convolution_axis(uv, vec2(1.0, 0.0), radius * 1.65, 0.52, weight_sum);
    bloom += convolution_axis(uv, vec2(0.0, 1.0), radius * 0.95, 0.18, weight_sum);
    bloom += convolution_axis(uv, vec2(0.707, 0.707), radius * 1.22, 0.16, weight_sum);
    bloom += convolution_axis(uv, vec2(-0.707, 0.707), radius * 1.22, 0.16, weight_sum);
    return bloom / max(weight_sum, 0.0001) * 1.42;
}

void main() {
    vec4 layer = texture2D(u_layer_tex, v_uv);
    float radius = max(0.5, u_bloom_radius);
    vec3 bloom = convolution_bloom(v_uv, radius);
    vec2 shadow_delta = (v_uv - u_ground_shadow_center) / max(u_ground_shadow_radius, vec2(0.0001));
    float oval = 1.0 - smoothstep(0.46, 1.0, dot(shadow_delta, shadow_delta));
    float ground_alpha = oval * clamp(u_ground_shadow_strength, 0.0, 0.75) * (1.0 - layer.a);
    vec3 shadow_rgb = u_ground_shadow_color * ground_alpha;
    float out_alpha = layer.a + ground_alpha * (1.0 - layer.a);
    vec3 rgb = shadow_rgb + layer.rgb + bloom * clamp(u_bloom_strength, 0.0, 2.0);
    gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), clamp(out_alpha, 0.0, 1.0));
}
"""


_AR_PBR_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec4 a_color;
varying vec4 v_color;
void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_color = a_color;
}
"""


_AR_PBR_FRAGMENT_SHADER = """
#version 120
varying vec4 v_color;
void main() {
    gl_FragColor = v_color;
}
"""


_AR_PBR_TEXTURE_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec2 a_uv;
attribute vec3 a_normal;
attribute vec3 a_tangent;
attribute vec3 a_bitangent;
attribute vec4 a_color;
attribute vec3 a_material;
attribute vec3 a_world_pos;
varying vec2 v_uv;
varying vec3 v_normal;
varying vec3 v_tangent;
varying vec3 v_bitangent;
varying vec4 v_color;
varying vec3 v_material;
varying vec3 v_world_pos;
void main() {
    float depth = clamp((a_world_pos.z - 0.05) / 8.0, 0.0, 1.0);
    gl_Position = vec4(a_pos, depth * 2.0 - 1.0, 1.0);
    v_uv = a_uv;
    v_normal = a_normal;
    v_tangent = a_tangent;
    v_bitangent = a_bitangent;
    v_color = a_color;
    v_material = a_material;
    v_world_pos = a_world_pos;
}
"""


_AR_PBR_TEXTURE_FRAGMENT_SHADER = """
#version 120
const float PI = 3.14159265358979323846;
varying vec2 v_uv;
varying vec3 v_normal;
varying vec3 v_tangent;
varying vec3 v_bitangent;
varying vec4 v_color;
varying vec3 v_material;
varying vec3 v_world_pos;
uniform sampler2D u_base_tex;
uniform sampler2D u_roughness_tex;
uniform sampler2D u_metallic_tex;
uniform sampler2D u_specular_tex;
uniform sampler2D u_normal_tex;
uniform sampler2D u_hdri_tex;
uniform sampler2D u_depth_tex;
uniform sampler2D u_occlusion_tex;
uniform sampler2D u_emissive_tex;
uniform sampler2D u_opacity_tex;
uniform sampler2D u_height_tex;
uniform sampler2D u_shadow_tex;
uniform sampler2D u_irradiance_tex;
uniform sampler2D u_prefilter_tex;
uniform sampler2D u_brdf_lut_tex;
uniform int u_has_base_tex;
uniform int u_has_roughness_tex;
uniform int u_has_metallic_tex;
uniform int u_has_specular_tex;
uniform int u_has_normal_tex;
uniform int u_has_hdri_tex;
uniform int u_has_ibl_probe;
uniform int u_has_depth_tex;
uniform int u_has_occlusion_tex;
uniform int u_has_emissive_tex;
uniform int u_has_opacity_tex;
uniform int u_has_height_tex;
uniform int u_has_shadow_map;
uniform int u_flip_uv_v;
uniform float u_depth_enabled;
uniform vec3 u_light_dir;
uniform vec3 u_shadow_center;
uniform float u_direct_strength;
uniform float u_ibl_exposure;
uniform float u_ibl_rotation;
uniform float u_object_depth;
uniform float u_occlusion_tolerance;
uniform float u_depth_edge_glow_strength;
uniform float u_depth_edge_glow_radius_px;
uniform vec3 u_depth_edge_glow_color;
uniform float u_shadow_radius;
uniform float u_shadow_map_size;
uniform float u_shadow_pcf_radius;
uniform float u_shadow_pcss_blocker_radius;
uniform float u_shadow_bias;
uniform float u_shadow_normal_bias;
uniform float u_shadow_strength;
uniform float u_self_shadow_strength;
uniform int u_shadow_filter_mode;
uniform int u_shadow_light_type;
uniform float u_shadow_spot_tan_outer;
uniform float u_shadow_spot_cos_inner;
uniform float u_shadow_spot_cos_outer;
uniform float u_prefilter_level_count;
uniform float u_alpha_cutoff;
uniform vec3 u_emissive_factor;
uniform vec2 u_viewport_size;
uniform vec4 u_roughness_channel;
uniform vec4 u_metallic_channel;
uniform vec4 u_specular_channel;
uniform vec4 u_occlusion_channel;
uniform vec4 u_opacity_channel;
uniform vec4 u_height_channel;
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

vec2 maybe_flip_uv(vec2 uv) {
    return u_flip_uv_v == 1 ? vec2(uv.x, 1.0 - uv.y) : uv;
}

vec2 dir_to_equirect(vec3 dir) {
    vec3 d = normalize(dir);
    float u = atan(d.z, d.x) / (2.0 * PI) + 0.5 + u_ibl_rotation;
    float v = 0.5 - asin(clamp(d.y, -1.0, 1.0)) / PI;
    return vec2(fract(u), clamp(v, 0.0, 1.0));
}

vec3 sample_env(vec3 dir) {
    if (u_has_hdri_tex == 1) {
        return pow(max(texture2D(u_hdri_tex, dir_to_equirect(dir)).rgb, vec3(0.0)), vec3(2.2)) * u_ibl_exposure;
    }
    vec3 up = vec3(0.18, 0.22, 0.28);
    vec3 side = vec3(0.72, 0.70, 0.66);
    return mix(side, up, clamp(normalize(dir).y * 0.5 + 0.5, 0.0, 1.0)) * u_ibl_exposure;
}

vec3 sample_irradiance(vec3 dir) {
    if (u_has_ibl_probe == 1) {
        return pow(max(texture2D(u_irradiance_tex, dir_to_equirect(dir)).rgb, vec3(0.0)), vec3(2.2)) * u_ibl_exposure;
    }
    return sample_env(dir);
}

vec3 sample_prefiltered_env(vec3 dir, float roughness) {
    if (u_has_ibl_probe == 1 && u_prefilter_level_count > 0.5) {
        float levels = max(1.0, u_prefilter_level_count);
        float level = clamp(roughness * roughness, 0.0, 1.0) * (levels - 1.0);
        float lo = floor(level);
        float hi = min(lo + 1.0, levels - 1.0);
        float mix_value = clamp(level - lo, 0.0, 1.0);
        vec2 uv = dir_to_equirect(dir);
        vec3 low = pow(max(texture2D(u_prefilter_tex, vec2(uv.x, (uv.y + lo) / levels)).rgb, vec3(0.0)), vec3(2.2));
        vec3 high = pow(max(texture2D(u_prefilter_tex, vec2(uv.x, (uv.y + hi) / levels)).rgb, vec3(0.0)), vec3(2.2));
        return mix(low, high, mix_value) * u_ibl_exposure;
    }
    vec3 env = sample_env(dir);
    vec3 blur = sample_env(vec3(0.0, 1.0, 0.0));
    return mix(env, blur, clamp(roughness * 0.58, 0.0, 0.72));
}

vec2 sample_brdf_lut(float ndotv, float roughness) {
    if (u_has_ibl_probe == 1) {
        return texture2D(u_brdf_lut_tex, vec2(clamp(ndotv, 0.0, 1.0), clamp(roughness, 0.0, 1.0))).rg;
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

vec3 apply_output_transform(vec3 rgb) {
    vec3 x = max(rgb, vec3(0.0)) * exp2(u_tone_exposure) * max(u_tone_white_balance, vec3(0.0001));
    vec3 mapped = u_tone_mapping_mode == 1
        ? tonemap_agx(x)
        : (u_tone_mapping_mode == 2 ? tonemap_reinhard(x) : tonemap_aces(x));
    return pow(clamp(mapped, 0.0, 1.0), vec3(1.0 / max(u_tone_gamma, 0.1)));
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
    vec4 uv_sample = texture2D(tex, uv);
    float strength = clamp(u_triplanar_strength, 0.0, 1.0);
    if (strength <= 0.0001) {
        return uv_sample;
    }
    vec3 w = triplanar_axis_weights(normal);
    vec4 tri_sample =
        texture2D(tex, triplanar_axis_uv(world_pos, 0)) * w.x +
        texture2D(tex, triplanar_axis_uv(world_pos, 1)) * w.y +
        texture2D(tex, triplanar_axis_uv(world_pos, 2)) * w.z;
    return mix(uv_sample, tri_sample, strength);
}

vec2 apply_parallax_uv(vec2 uv, vec3 view_dir, vec3 tangent, vec3 bitangent, vec3 normal, vec3 world_pos) {
    if (u_has_height_tex != 1 || u_parallax_strength <= 0.0001 || u_parallax_depth <= 0.0001) {
        return uv;
    }
    vec3 v = normalize(view_dir);
    vec3 t = normalize(tangent);
    vec3 b = normalize(bitangent);
    vec3 n = normalize(normal);
    vec3 view_ts = vec3(dot(v, t), dot(v, b), max(abs(dot(v, n)), 0.08));
    float height = dot(sample_material_rgba(u_height_tex, uv, world_pos, n), u_height_channel);
    float amount = (height - clamp(u_parallax_center, 0.0, 1.0)) * u_parallax_depth * u_parallax_strength;
    return uv + view_ts.xy * amount;
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

float sample_channel(sampler2D tex, vec2 uv, vec4 channel) {
    return dot(texture2D(tex, uv), channel);
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
    float tl = sqrt(max(1.0 - clamp(dot(t, l), -1.0, 1.0) * clamp(dot(t, l), -1.0, 1.0), 0.0));
    float tv = sqrt(max(1.0 - clamp(dot(t, v), -1.0, 1.0) * clamp(dot(t, v), -1.0, 1.0), 0.0));
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
    float sin_h = sqrt(max(1.0 - clamp(ndoth, 0.0, 1.0) * clamp(ndoth, 0.0, 1.0), 0.0));
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

vec3 cook_torrance_direct(vec3 albedo, vec3 f0, float roughness, float metallic, float ndotl, float ndotv, float ndoth, float vdoth, float direct_power, float ao) {
    vec3 f = fresnel_schlick(vdoth, f0);
    vec3 kd = (vec3(1.0) - f) * (1.0 - metallic);
    vec3 diffuse = kd * albedo / PI;
    float d = distribution_ggx(ndoth, roughness);
    float g = geometry_smith(ndotv, ndotl, roughness);
    vec3 specular = (d * g * f) / max(4.0 * ndotv * ndotl, 0.00001);
    return (diffuse + specular) * ndotl * max(direct_power, 0.0) * ao;
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

vec3 pbr_shadow_project(vec3 world_pos, vec3 light_dir) {
    vec3 light = normalize(-light_dir);
    vec3 up = abs(light.y) > 0.92 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 sx = normalize(cross(up, light));
    vec3 sy = cross(light, sx);
    if (u_shadow_light_type == 1) {
        vec3 origin = u_shadow_center - light * (u_shadow_radius * 2.0);
        vec3 ray = world_pos - origin;
        float depth = dot(ray, light);
        float far_depth = max(0.001, u_shadow_radius * 4.0);
        float cone_radius = max(0.001, depth * max(u_shadow_spot_tan_outer, 0.001));
        vec2 uv = vec2(dot(ray, sx), dot(ray, sy)) / (cone_radius * 2.0) + vec2(0.5);
        return vec3(uv, clamp(depth / far_depth, 0.0, 1.0));
    }
    vec3 local = world_pos - u_shadow_center;
    vec2 uv = vec2(dot(local, sx), dot(local, sy)) / (u_shadow_radius * 2.0) + vec2(0.5);
    float current = clamp(0.5 - dot(local, light) / (u_shadow_radius * 2.0), 0.0, 1.0);
    return vec3(uv, current);
}

float pbr_shadow_pcf(vec2 uv, float current, float bias, float radius_texels) {
    float texel = max(0.0, radius_texels) / max(1.0, u_shadow_map_size);
    float lit = 0.0;
    for (int x = -2; x <= 2; ++x) {
        for (int y = -2; y <= 2; ++y) {
            float closest = texture2D(u_shadow_tex, uv + vec2(float(x), float(y)) * texel).r;
            lit += current - bias <= closest ? 1.0 : 0.0;
        }
    }
    return lit / 25.0;
}

float pbr_shadow_pcss(vec2 uv, float current, float bias) {
    float search_texel = max(u_shadow_pcf_radius, u_shadow_pcss_blocker_radius) / max(1.0, u_shadow_map_size);
    float blocker_sum = 0.0;
    float blocker_count = 0.0;
    for (int x = -2; x <= 2; ++x) {
        for (int y = -2; y <= 2; ++y) {
            float closest = texture2D(u_shadow_tex, uv + vec2(float(x), float(y)) * search_texel).r;
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
    return pbr_shadow_pcf(uv, current, bias, penumbra);
}

float pbr_shadow_visibility(vec3 world_pos, vec3 normal, vec3 light_dir) {
    if (u_has_shadow_map != 1 || u_shadow_radius <= 0.001 || u_shadow_map_size <= 1.0) {
        return 1.0;
    }
    vec3 light = normalize(-light_dir);
    float normal_light = clamp(abs(dot(normalize(normal), light)), 0.08, 1.0);
    vec3 projected = pbr_shadow_project(world_pos, light_dir);
    vec2 uv = projected.xy;
    if (uv.x <= 0.002 || uv.x >= 0.998 || uv.y <= 0.002 || uv.y >= 0.998) {
        return 1.0;
    }
    float spot_mask = 1.0;
    if (u_shadow_light_type == 1) {
        vec3 origin = u_shadow_center - light * (u_shadow_radius * 2.0);
        float spot_cos = dot(normalize(world_pos - origin), light);
        spot_mask = smoothstep(u_shadow_spot_cos_outer, u_shadow_spot_cos_inner, spot_cos);
    }
    float current = projected.z;
    float bias = max(u_shadow_bias, u_shadow_bias + u_shadow_normal_bias * (1.0 - normal_light));
    float lit = u_shadow_filter_mode == 1 ? pbr_shadow_pcss(uv, current, bias) : pbr_shadow_pcf(uv, current, bias, u_shadow_pcf_radius);
    lit = mix(1.0, lit, spot_mask);
    return mix(1.0 - clamp(u_shadow_strength, 0.0, 1.0), 1.0, lit);
}

void main() {
    vec2 uv = maybe_flip_uv(v_uv);
    vec3 parallax_n = normalize(v_normal);
    if (length(parallax_n) <= 0.001) {
        parallax_n = vec3(0.0, 0.0, 1.0);
    }
    vec3 parallax_tangent = normalize(v_tangent);
    vec3 parallax_bitangent = normalize(v_bitangent);
    if (length(parallax_tangent) <= 0.001 || length(parallax_bitangent) <= 0.001) {
        parallax_tangent = vec3(1.0, 0.0, 0.0);
        parallax_bitangent = normalize(cross(parallax_n, parallax_tangent));
    }
    uv = apply_parallax_uv(uv, vec3(0.0, 0.0, -1.0), parallax_tangent, parallax_bitangent, parallax_n, v_world_pos);
    vec4 tex = sample_material_rgba(u_base_tex, uv, v_world_pos, parallax_n);
    float out_alpha = tex.a * v_color.a;
    if (u_has_base_tex == 0) {
        tex = vec4(clamp(v_color.rgb, 0.0, 1.0), v_color.a);
        out_alpha = v_color.a;
    }
    if (u_has_opacity_tex == 1) {
        out_alpha *= clamp(dot(sample_material_rgba(u_opacity_tex, uv, v_world_pos, parallax_n), u_opacity_channel), 0.0, 1.0);
    }
    if (out_alpha <= max(u_alpha_cutoff, 0.001)) {
        discard;
    }
    float depth_edge_glow = 0.0;
    if (u_depth_enabled > 0.5 && u_viewport_size.x > 1.0 && u_viewport_size.y > 1.0) {
        vec2 depth_uv = vec2(
            clamp(gl_FragCoord.x / u_viewport_size.x, 0.0, 1.0),
            clamp(1.0 - gl_FragCoord.y / u_viewport_size.y, 0.0, 1.0)
        );
        float scene_depth = texture2D(u_depth_tex, depth_uv).r;
        float threshold = u_object_depth - u_occlusion_tolerance;
        if (scene_depth < threshold) {
            discard;
        }
        if (u_depth_edge_glow_strength > 0.0001) {
            vec2 texel = vec2(
                max(1.0, u_depth_edge_glow_radius_px) / u_viewport_size.x,
                max(1.0, u_depth_edge_glow_radius_px) / u_viewport_size.y
            );
            float left_depth = texture2D(u_depth_tex, clamp(depth_uv + vec2(-texel.x, 0.0), vec2(0.0), vec2(1.0))).r;
            float right_depth = texture2D(u_depth_tex, clamp(depth_uv + vec2(texel.x, 0.0), vec2(0.0), vec2(1.0))).r;
            float up_depth = texture2D(u_depth_tex, clamp(depth_uv + vec2(0.0, texel.y), vec2(0.0), vec2(1.0))).r;
            float down_depth = texture2D(u_depth_tex, clamp(depth_uv + vec2(0.0, -texel.y), vec2(0.0), vec2(1.0))).r;
            float left_hidden = 1.0 - step(threshold, left_depth);
            float right_hidden = 1.0 - step(threshold, right_depth);
            float up_hidden = 1.0 - step(threshold, up_depth);
            float down_hidden = 1.0 - step(threshold, down_depth);
            float scene_edge = max(max(abs(scene_depth - left_depth), abs(scene_depth - right_depth)), max(abs(scene_depth - up_depth), abs(scene_depth - down_depth)));
            float near_boundary = 1.0 - smoothstep(0.0, max(0.002, u_occlusion_tolerance + 0.018), abs(scene_depth - threshold));
            depth_edge_glow = clamp(max(max(left_hidden, right_hidden), max(up_hidden, down_hidden)) + scene_edge + near_boundary * 0.45, 0.0, 1.0);
        }
    }

    vec3 n = normalize(v_normal);
    if (length(n) <= 0.001) {
        n = vec3(0.0, 0.0, 1.0);
    }
    vec3 tangent = normalize(v_tangent);
    vec3 bitangent = normalize(v_bitangent);
    if (length(tangent) <= 0.001 || length(bitangent) <= 0.001) {
        tangent = vec3(1.0, 0.0, 0.0);
        bitangent = normalize(cross(n, tangent));
    }
    if (u_has_normal_tex == 1) {
        vec3 tn = sample_material_rgba(u_normal_tex, uv, v_world_pos, n).rgb * 2.0 - 1.0;
        mat3 tbn = mat3(tangent, bitangent, n);
        n = normalize(tbn * tn);
    }
    n = apply_bevel_normal(n, tangent, bitangent, uv);

    float roughness = clamp(v_material.x, 0.04, 1.0);
    float metallic = clamp(v_material.y, 0.0, 1.0);
    float reflectance = clamp(v_material.z, 0.0, 1.0);
    if (u_has_roughness_tex == 1) {
        roughness = clamp(dot(sample_material_rgba(u_roughness_tex, uv, v_world_pos, n), u_roughness_channel), 0.04, 1.0);
    }
    if (u_has_metallic_tex == 1) {
        metallic = clamp(dot(sample_material_rgba(u_metallic_tex, uv, v_world_pos, n), u_metallic_channel), 0.0, 1.0);
    }
    if (u_has_specular_tex == 1) {
        reflectance = clamp(dot(sample_material_rgba(u_specular_tex, uv, v_world_pos, n), u_specular_channel), 0.0, 1.0);
    }
    apply_surface_override(roughness, metallic, reflectance);

    vec3 light = normalize(-u_light_dir);
    vec3 view = vec3(0.0, 0.0, -1.0);
    if (dot(n, view) < 0.0) {
        n = -n;
    }
    float raw_lambert = dot(n, light);
    float lambert = max(raw_lambert, 0.0);
    float wrapped_lambert = clamp((raw_lambert + 0.42) / 1.42, 0.0, 1.0);
    float ndotv = max(dot(n, view), 0.0);
    vec3 albedo = srgb_to_linear(tex.rgb);
    if (u_has_base_tex == 1) {
        albedo *= clamp(v_color.rgb, vec3(0.0), vec3(16.0));
    }
    float ao = 1.0;
    if (u_has_occlusion_tex == 1) {
        ao = clamp(dot(sample_material_rgba(u_occlusion_tex, uv, v_world_pos, n), u_occlusion_channel), 0.0, 1.0);
    }
    float screen_ao = screen_space_ao_factor(n, view, v_world_pos);
    float ambient_ao = ao * (u_screen_ao_ambient == 1 ? screen_ao : 1.0);
    float diffuse_ao = ao * (u_screen_ao_diffuse == 1 ? screen_ao : 1.0);
    float specular_ao = ao * (u_screen_ao_specular == 1 ? screen_ao : 1.0);
    vec3 emissive = albedo * max(u_emissive_factor, vec3(0.0));
    if (u_has_emissive_tex == 1) {
        emissive = srgb_to_linear(sample_material_rgba(u_emissive_tex, uv, v_world_pos, n).rgb) * max(u_emissive_factor, vec3(0.0));
    }
    apply_material_layer(albedo, roughness, metallic, out_alpha, emissive);
    vec3 f0 = mix(vec3(0.02 + reflectance * 0.06), albedo, metallic);
    vec3 fresnel = fresnel_schlick(ndotv, f0);

    vec3 irradiance = sample_irradiance(n);
    vec3 reflect_dir = reflect(-view, n);
    vec3 spec_env = sample_prefiltered_env(reflect_dir, roughness);
    vec2 brdf = sample_brdf_lut(ndotv, roughness);
    vec3 kd = (vec3(1.0) - fresnel) * (1.0 - metallic);
    vec3 diffuse = albedo * irradiance * kd * ambient_ao;
    vec3 specular_env = spec_env * (fresnel * brdf.x + vec3(brdf.y)) * mix(0.64, 1.0, specular_ao);
    float shadow_visibility = pbr_shadow_visibility(v_world_pos, n, u_light_dir);
    float self_shadow = mix(1.0, shadow_visibility, clamp(u_self_shadow_strength, 0.0, 1.0));
    diffuse *= self_shadow;
    specular_env *= mix(1.0, self_shadow, 0.35);

    float direct_power = max(u_direct_strength, 0.0);
    vec3 half_vec = normalize(light + view);
    float ndoth = max(dot(n, half_vec), 0.0);
    float vdoth = max(dot(view, half_vec), 0.0);
    float preview_direct_lambert = max(lambert, wrapped_lambert * 0.62);
    vec3 direct = cook_torrance_direct(albedo, f0, roughness, metallic, preview_direct_lambert, ndotv, ndoth, vdoth, direct_power, diffuse_ao);
    direct *= shadow_visibility;

    vec3 fill = albedo * (0.045 + roughness * 0.03) * kd * mix(0.48, 1.0, ambient_ao);
    fill *= mix(1.0, self_shadow, 0.65);
    vec3 preview_hemi = albedo
        * (0.20 + roughness * 0.14 + metallic * 0.08)
        * clamp(u_ibl_exposure, 0.35, 3.0)
        * (0.55 + wrapped_lambert * 0.45)
        * mix(0.58, 1.0, ambient_ao);
    vec3 preview_lift = albedo * (0.11 + roughness * 0.075) * clamp(u_ibl_exposure, 0.35, 4.0) * mix(0.60, 1.0, ambient_ao);
    preview_lift *= mix(1.0, self_shadow, 0.25);
    vec3 rgb = diffuse + specular_env + direct + fill + preview_hemi + preview_lift + emissive;
    float accumulation = hybrid_sample_gain();
    vec3 diffuse_gi = albedo * irradiance * kd * ambient_ao * u_diffuse_gi_strength * accumulation * (1.0 - metallic) * mix(0.55, 1.0, roughness);
    vec3 specular_gi = spec_env * fresnel * u_specular_gi_strength * accumulation * (1.0 - roughness * 0.40) * mix(0.50, 1.0, specular_ao);
    rgb += diffuse_gi + specular_gi;
    rgb = apply_subsurface_lighting(rgb, albedo, n, view, light, lambert, diffuse_ao, irradiance, direct_power);
    rgb = apply_hair_groom_lighting(rgb, n, tangent, view, light, lambert, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_cloth_sheen_lighting(rgb, albedo, n, view, light, lambert, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_glint_sparkle_lighting(rgb, uv, v_world_pos, view, light, lambert, ndotv, ndoth, roughness, diffuse_ao, direct_power, spec_env);
    rgb = apply_clearcoat_layer(rgb, n, view, light, roughness, ndotv, lambert, ndoth, vdoth, specular_ao, direct_power);
    float screen_ao_shadow = clamp(1.0 - min(min(ambient_ao, diffuse_ao), specular_ao), 0.0, 1.0);
    rgb = mix(rgb, rgb * (0.82 + clamp(u_screen_ao_color, vec3(0.0), vec3(1.0)) * 0.18), screen_ao_shadow);
    rgb = apply_transmission_refraction(rgb, albedo, n, view, roughness, fresnel);
    rgb = apply_output_transform(rgb);
    if (u_has_base_tex == 1) {
        vec3 preview_base = clamp(tex.rgb * clamp(v_color.rgb, vec3(0.0), vec3(1.0)), 0.0, 1.0);
        vec3 preview_albedo = pow(preview_base, vec3(0.58));
        vec3 base_visibility = preview_albedo
            * (0.48 + roughness * 0.24 + (1.0 - metallic) * 0.10)
            * clamp(0.92 + u_ibl_exposure * 0.18, 0.92, 1.55)
            * mix(0.68, 1.0, ambient_ao)
            * mix(0.90, 1.0, self_shadow);
        rgb = max(rgb, base_visibility);
    }
    rgb += clamp(u_depth_edge_glow_color, vec3(0.0), vec3(1.0)) * depth_edge_glow * clamp(u_depth_edge_glow_strength, 0.0, 1.0);
    gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), out_alpha);
}
"""


_AR_PBR_TEXTURE_SHADOW_VERTEX_SHADER = """
#version 120
attribute vec3 a_world_pos;
attribute vec2 a_uv;
uniform vec3 u_shadow_center;
uniform vec3 u_shadow_light_dir;
uniform float u_shadow_radius;
uniform int u_shadow_light_type;
uniform float u_shadow_spot_tan_outer;
varying vec2 v_uv;
varying float v_depth;
void main() {
    vec3 light = normalize(-u_shadow_light_dir);
    vec3 up = abs(light.y) > 0.92 ? vec3(1.0, 0.0, 0.0) : vec3(0.0, 1.0, 0.0);
    vec3 sx = normalize(cross(up, light));
    vec3 sy = cross(light, sx);
    vec2 xy;
    if (u_shadow_light_type == 1) {
        vec3 origin = u_shadow_center - light * (u_shadow_radius * 2.0);
        vec3 ray = a_world_pos - origin;
        float depth = dot(ray, light);
        float cone_radius = max(0.001, depth * max(u_shadow_spot_tan_outer, 0.001));
        xy = vec2(dot(ray, sx), dot(ray, sy)) / cone_radius;
        v_depth = clamp(depth / max(0.001, u_shadow_radius * 4.0), 0.0, 1.0);
    } else {
        vec3 local = a_world_pos - u_shadow_center;
        xy = vec2(dot(local, sx), dot(local, sy)) / max(0.001, u_shadow_radius);
        v_depth = clamp(0.5 - dot(local, light) / max(0.001, u_shadow_radius * 2.0), 0.0, 1.0);
    }
    gl_Position = vec4(xy, v_depth * 2.0 - 1.0, 1.0);
    v_uv = a_uv;
}
"""


_AR_PBR_TEXTURE_SHADOW_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
varying float v_depth;
uniform sampler2D u_base_tex;
uniform int u_has_base_tex;
uniform int u_flip_uv_v;
uniform float u_alpha_cutoff;
void main() {
    vec2 uv = u_flip_uv_v == 1 ? vec2(v_uv.x, 1.0 - v_uv.y) : v_uv;
    vec4 tex = u_has_base_tex == 1 ? texture2D(u_base_tex, uv) : vec4(1.0);
    if (tex.a <= u_alpha_cutoff) {
        discard;
    }
    gl_FragColor = vec4(v_depth, v_depth, v_depth, 1.0);
}
"""


def _letterbox_viewport(fw: int, fh: int, ww: int, wh: int) -> tuple[int, int, int, int]:
    if fw <= 0 or fh <= 0 or ww <= 0 or wh <= 0:
        return 0, 0, max(1, ww), max(1, wh)
    scale = min(float(ww) / float(fw), float(wh) / float(fh))
    vw = max(1, int(round(float(fw) * scale)))
    vh = max(1, int(round(float(fh) * scale)))
    return max(0, (ww - vw) // 2), max(0, (wh - vh) // 2), vw, vh


class _SpineDirectGLPainter:
    """Draw Spine actor render states into the current preview GL context."""

    def __init__(self, parent=None) -> None:
        from app.spine_editor.spine_gl_renderer import SpineGLViewport

        self.pil_to_qimage = SpineGLViewport.pil_to_qimage
        self._mesh_weights_for = SpineGLViewport._mesh_weights_for.__get__(self, self.__class__)
        self._json_uv_to_atlas = SpineGLViewport._json_uv_to_atlas.__get__(self, self.__class__)
        self._compute_region_corners_screen_spine = (
            SpineGLViewport._compute_region_corners_screen_spine.__get__(self, self.__class__)
        )
        self._region_uv_corners = SpineGLViewport._region_uv_corners.__get__(self, self.__class__)
        self._append_expanded_vertices = SpineGLViewport._append_expanded_vertices
        self._draw_spine_gl = SpineGLViewport._draw_spine_gl.__get__(self, self.__class__)

        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._prog: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._texture_cache: dict[tuple, dict[int, QOpenGLTexture]] = {}
        self._texture_cache_order: list[tuple] = []
        self._texture_cache_limit = 16

        self._skeleton = None
        self._atlas: dict = {}
        self._pil_pages: list = []
        self._gl_textures: dict[int, QOpenGLTexture] = {}
        self._pma = False
        self._active_skin = "default"
        self._hidden_slots: set[str] = set()
        self._offset = QPointF(0.0, 0.0)
        self._zoom = 1.0
        self._w = 1
        self._h = 1

    def width(self) -> int:
        return int(self._w)

    def height(self) -> int:
        return int(self._h)

    def _ensure_resources(self) -> bool:
        if self._program is not None and self._vbo is not None:
            return True
        prog = QOpenGLShaderProgram(self._parent)
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _SPINE_VERTEX_SHADER,
        )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _SPINE_FRAGMENT_SHADER,
        )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_uv", 1)
        if not ok_v or not ok_f or not prog.link():
            print(
                f"[OpenGLPreviewWidget] Spine direct shader failed:\n{prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return False
        self._program = prog
        self._prog = prog
        self._vbo = vbo
        return True

    @staticmethod
    def _pages_key(pages: list) -> tuple:
        return tuple(
            (
                id(page),
                getattr(page, "size", None),
                getattr(page, "mode", None),
            )
            if page is not None
            else None
            for page in (pages or [])
        )

    def _textures_for_pages(self, pages: list) -> dict[int, QOpenGLTexture]:
        key = self._pages_key(pages)
        cached = self._texture_cache.get(key)
        if cached is not None:
            if key in self._texture_cache_order:
                self._texture_cache_order.remove(key)
            self._texture_cache_order.append(key)
            return cached

        textures: dict[int, QOpenGLTexture] = {}
        for i, pil_img in enumerate(pages or []):
            if pil_img is None:
                continue
            qimg = self.pil_to_qimage(pil_img)
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind()
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release()
            textures[i] = tex

        self._texture_cache[key] = textures
        self._texture_cache_order.append(key)
        while len(self._texture_cache_order) > self._texture_cache_limit:
            old_key = self._texture_cache_order.pop(0)
            old = self._texture_cache.pop(old_key, {})
            for tex in old.values():
                try:
                    tex.destroy()
                except Exception:
                    pass
        return textures

    def _draw_expanded_mesh(self, gl, tex, expanded) -> None:
        if self._program is None or self._vbo is None or not expanded:
            return
        stride4 = 4
        v_arr = np.array(expanded, dtype=np.float32)
        n_verts = len(expanded) // stride4
        if n_verts <= 0:
            return

        tex.bind(0)
        self._vbo.bind()
        self._vbo.allocate(v_arr.tobytes(), int(v_arr.nbytes))
        stride_bytes = stride4 * 4
        self._program.enableAttributeArray(0)
        self._program.enableAttributeArray(1)
        self._program.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride_bytes)
        self._program.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride_bytes)
        gl.glDrawArrays(_GL_TRIANGLES, 0, int(n_verts))
        self._program.disableAttributeArray(0)
        self._program.disableAttributeArray(1)
        self._vbo.release()
        tex.release(0)

    def draw(self, gl, items: list[dict], frame_w: int, frame_h: int) -> bool:
        if not items:
            return True
        if not self._ensure_resources() or self._program is None:
            return False
        self._w = max(1, int(frame_w))
        self._h = max(1, int(frame_h))

        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glEnable(_GL_BLEND)
        for item in items:
            skeleton = item.get("skeleton")
            atlas = item.get("atlas") or {}
            pages = item.get("pil_pages") or []
            if skeleton is None or not atlas or not pages:
                continue

            self._skeleton = skeleton
            self._atlas = atlas
            self._pil_pages = pages
            self._gl_textures = self._textures_for_pages(pages)
            if not self._gl_textures:
                continue
            self._pma = bool(item.get("pma", False))
            self._active_skin = str(item.get("skin_name") or "default")
            self._hidden_slots = set(item.get("hidden_slots") or ())
            self._zoom = float(item.get("scale", 1.0) or 1.0)
            self._offset = QPointF(
                self._w / 2 + float(item.get("offset_x", 0.0) or 0.0),
                self._h / 2 - float(item.get("offset_y", 0.0) or 0.0),
            )

            anim_name = str(item.get("anim_name") or "")
            if anim_name:
                anim = skeleton.animations.get(anim_name)
                if anim:
                    skeleton.apply_animation(anim, float(item.get("time", 0.0) or 0.0))

            if self._pma:
                gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
            else:
                gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
            self._draw_spine_gl(gl)
        return True


class _MMDDirectGLPainter:
    """Draw PMX preview packets in the current preview GL context."""

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._shadow_program: QOpenGLShaderProgram | None = None
        self._composite_program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._quad_vbo: QOpenGLBuffer | None = None
        self._group_vbo_cache: dict[tuple[object, ...], tuple[QOpenGLBuffer, int]] = {}
        self._group_vbo_cache_order: list[tuple[object, ...]] = []
        self._group_vbo_cache_limit = 256
        self._shadow_fbo: QOpenGLFramebufferObject | None = None
        self._shadow_fbo_size = 0
        self._layer_fbo: QOpenGLFramebufferObject | None = None
        self._bloom_fbo: QOpenGLFramebufferObject | None = None
        self._layer_fbo_size: tuple[int, int] = (0, 0)
        self._texture_cache: dict[tuple[str, int, int], QOpenGLTexture] = {}
        self._texture_cache_order: list[tuple[str, int, int]] = []
        self._white_texture: QOpenGLTexture | None = None
        self._texture_cache_limit = 48
        self._bone_texture_id = 0
        self._bone_texture_error_logged = False
        self._vbo_frame_stats: dict[str, int] = {}

    def _reset_vbo_frame_stats(self) -> None:
        self._vbo_frame_stats = {
            "binds": 0,
            "hits": 0,
            "misses": 0,
            "transient_uploads": 0,
            "uploaded_bytes": 0,
            "cached_bytes": 0,
            "evictions": 0,
        }

    def _record_vbo_stat(self, key: str, value: int = 1) -> None:
        if not self._vbo_frame_stats:
            self._reset_vbo_frame_stats()
        self._vbo_frame_stats[key] = int(self._vbo_frame_stats.get(key, 0)) + int(value)

    def _vbo_frame_stats_snapshot(self) -> dict[str, int | float | bool]:
        stats = dict(self._vbo_frame_stats or {})
        binds = int(stats.get("binds", 0) or 0)
        hits = int(stats.get("hits", 0) or 0)
        misses = int(stats.get("misses", 0) or 0)
        cache_attempts = hits + misses
        cached_bytes = 0
        for _key, (_vbo, nbytes) in self._group_vbo_cache.items():
            cached_bytes += int(nbytes)
        return {
            "mmd_vbo_cache_enabled": True,
            "mmd_vbo_cache_size": int(len(self._group_vbo_cache)),
            "mmd_vbo_cache_limit": int(self._group_vbo_cache_limit),
            "mmd_vbo_cache_binds": binds,
            "mmd_vbo_cache_hits": hits,
            "mmd_vbo_cache_misses": misses,
            "mmd_vbo_cache_hit_rate": float(hits / cache_attempts) if cache_attempts > 0 else 0.0,
            "mmd_vbo_transient_uploads": int(stats.get("transient_uploads", 0) or 0),
            "mmd_vbo_uploaded_bytes": int(stats.get("uploaded_bytes", 0) or 0),
            "mmd_vbo_cached_bytes": int(cached_bytes),
            "mmd_vbo_cache_evictions": int(stats.get("evictions", 0) or 0),
        }

    def _attach_vbo_diagnostics(self, items: list[dict]) -> None:
        snapshot = self._vbo_frame_stats_snapshot()
        for item in items:
            if not isinstance(item, dict):
                continue
            diagnostics = dict(item.get("diagnostics") or {})
            diagnostics.update(snapshot)
            item["diagnostics"] = diagnostics

    def _group_vbo_key(self, item: dict, group: dict, stride_floats: int, nbytes: int) -> tuple[object, ...] | None:
        if not bool(item.get("gpu_skinning")) or not bool(group.get("gpu_skinning")):
            return None
        mesh_id = str(item.get("mesh_id") or item.get("path") or "")
        if not mesh_id:
            return None
        return (
            mesh_id,
            tuple(str(name) for name in (item.get("gpu_morph_names") or ())),
            int(group.get("material_index", 0) or 0),
            int(group.get("vertex_count", 0) or 0),
            int(stride_floats),
            int(nbytes),
            int(group.get("gpu_morph_slot_count", 0) or 0),
        )

    def _bind_group_vbo(
        self,
        item: dict,
        group: dict,
        vertices: np.ndarray,
        stride_floats: int,
    ) -> QOpenGLBuffer | None:
        if self._vbo is None:
            return None
        arr = np.ascontiguousarray(vertices, dtype=np.float32)
        key = self._group_vbo_key(item, group, stride_floats, int(arr.nbytes))
        self._record_vbo_stat("binds")
        if key is None:
            self._vbo.bind()
            self._vbo.allocate(arr.tobytes(), int(arr.nbytes))
            self._record_vbo_stat("transient_uploads")
            self._record_vbo_stat("uploaded_bytes", int(arr.nbytes))
            return self._vbo
        cached = self._group_vbo_cache.get(key)
        if cached is not None:
            vbo, _nbytes = cached
            if key in self._group_vbo_cache_order:
                self._group_vbo_cache_order.remove(key)
            self._group_vbo_cache_order.append(key)
            vbo.bind()
            self._record_vbo_stat("hits")
            return vbo
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return None
        vbo.bind()
        vbo.allocate(arr.tobytes(), int(arr.nbytes))
        self._record_vbo_stat("misses")
        self._record_vbo_stat("uploaded_bytes", int(arr.nbytes))
        self._group_vbo_cache[key] = (vbo, int(arr.nbytes))
        self._group_vbo_cache_order.append(key)
        while len(self._group_vbo_cache_order) > self._group_vbo_cache_limit:
            old_key = self._group_vbo_cache_order.pop(0)
            old = self._group_vbo_cache.pop(old_key, None)
            if old is not None:
                self._record_vbo_stat("evictions")
                try:
                    old[0].destroy()
                except Exception:
                    pass
        return vbo

    def _ensure_resources(self) -> bool:
        if (
            self._program is not None
            and self._shadow_program is not None
            and self._composite_program is not None
            and self._vbo is not None
            and self._quad_vbo is not None
        ):
            return True
        prog = QOpenGLShaderProgram(self._parent)
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _MMD_VERTEX_SHADER,
        )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _MMD_FRAGMENT_SHADER,
        )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_normal", 1)
        prog.bindAttributeLocation("a_uv", 2)
        prog.bindAttributeLocation("a_bone_indices", 3)
        prog.bindAttributeLocation("a_bone_weights", 4)
        prog.bindAttributeLocation("a_morph_delta0", 5)
        prog.bindAttributeLocation("a_morph_delta1", 6)
        if not ok_v or not ok_f or not prog.link():
            print(
                f"[OpenGLPreviewWidget] MMD shader failed:\n{prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        shadow_prog = QOpenGLShaderProgram(self._parent)
        ok_sv = shadow_prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _MMD_SHADOW_VERTEX_SHADER,
        )
        ok_sf = shadow_prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _MMD_SHADOW_FRAGMENT_SHADER,
        )
        shadow_prog.bindAttributeLocation("a_pos", 0)
        shadow_prog.bindAttributeLocation("a_uv", 2)
        shadow_prog.bindAttributeLocation("a_bone_indices", 3)
        shadow_prog.bindAttributeLocation("a_bone_weights", 4)
        shadow_prog.bindAttributeLocation("a_morph_delta0", 5)
        shadow_prog.bindAttributeLocation("a_morph_delta1", 6)
        if not ok_sv or not ok_sf or not shadow_prog.link():
            print(
                f"[OpenGLPreviewWidget] MMD shadow shader failed:\n{shadow_prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        composite_prog = QOpenGLShaderProgram(self._parent)
        ok_cv = composite_prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _MMD_COMPOSITE_VERTEX_SHADER,
        )
        ok_cf = composite_prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _MMD_COMPOSITE_FRAGMENT_SHADER,
        )
        composite_prog.bindAttributeLocation("a_pos", 0)
        composite_prog.bindAttributeLocation("a_uv", 1)
        if not ok_cv or not ok_cf or not composite_prog.link():
            print(
                f"[OpenGLPreviewWidget] MMD composite shader failed:\n{composite_prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return False
        quad_vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not quad_vbo.create():
            return False
        self._program = prog
        self._shadow_program = shadow_prog
        self._composite_program = composite_prog
        self._vbo = vbo
        self._quad_vbo = quad_vbo
        return True

    def _ensure_layer_fbos(self, width: int, height: int) -> bool:
        width = max(16, min(4096, int(width or 1)))
        height = max(16, min(4096, int(height or 1)))
        if self._layer_fbo is not None and self._bloom_fbo is not None and self._layer_fbo_size == (width, height):
            return True
        self._layer_fbo = None
        self._bloom_fbo = None
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
        layer = QOpenGLFramebufferObject(width, height, fmt)
        bloom = QOpenGLFramebufferObject(width, height, fmt)
        if not layer.isValid() or not bloom.isValid():
            return False
        self._layer_fbo = layer
        self._bloom_fbo = bloom
        self._layer_fbo_size = (width, height)
        return True

    def _ensure_shadow_fbo(self, size: int) -> bool:
        size = max(256, min(2048, int(size or 1024)))
        if self._shadow_fbo is not None and self._shadow_fbo_size == size:
            return True
        self._shadow_fbo = None
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
        fbo = QOpenGLFramebufferObject(size, size, fmt)
        if not fbo.isValid():
            return False
        self._shadow_fbo = fbo
        self._shadow_fbo_size = size
        return True

    @staticmethod
    def _texture_key(path: str) -> tuple[str, int, int] | None:
        if not str(path or "").strip():
            return None
        try:
            p = Path(str(path))
            if not p.is_file():
                return None
            st = p.stat()
            return (str(p.resolve()), int(st.st_size), int(st.st_mtime_ns))
        except Exception:
            return None

    def _texture_for_path(self, path: str) -> QOpenGLTexture | None:
        key = self._texture_key(path)
        if key is None:
            return None
        cached = self._texture_cache.get(key)
        if cached is not None:
            if key in self._texture_cache_order:
                self._texture_cache_order.remove(key)
            self._texture_cache_order.append(key)
            return cached
        try:
            from PIL import Image

            image = Image.open(key[0]).convert("RGBA")
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            arr = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
            h, w = int(arr.shape[0]), int(arr.shape[1])
            qimg = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(0)
            tex.setMinificationFilter(QOpenGLTexture.Filter.LinearMipMapLinear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            try:
                tex.generateMipMaps()
            except Exception:
                pass
            tex.release(0)
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] MMD texture upload failed for {path}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        self._texture_cache[key] = tex
        self._texture_cache_order.append(key)
        while len(self._texture_cache_order) > self._texture_cache_limit:
            old_key = self._texture_cache_order.pop(0)
            old = self._texture_cache.pop(old_key, None)
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
        return tex

    def _solid_texture(self) -> QOpenGLTexture | None:
        if self._white_texture is not None:
            return self._white_texture
        try:
            arr = np.ascontiguousarray(np.asarray([[[255, 255, 255, 255]]], dtype=np.uint8))
            qimg = QImage(arr.data, 1, 1, 4, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(0)
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release(0)
            self._white_texture = tex
            return tex
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] MMD white texture fallback failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None

    def _set_uniform1i_gl(self, gl, name: str, value: int) -> None:
        if self._program is None:
            return
        self._set_program_uniform1i_gl(gl, self._program, name, value)

    def _set_program_uniform1i_gl(self, gl, program: QOpenGLShaderProgram, name: str, value: int) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1i"):
                gl.glUniform1i(loc, int(value))
            elif loc >= 0:
                program.setUniformValue(loc, int(value))
        except Exception:
            pass

    def _set_uniform(self, name: str, value) -> None:
        if self._program is None:
            return
        self._set_program_uniform(self._program, name, value)

    def _set_program_uniform(self, program: QOpenGLShaderProgram, name: str, value) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0:
                program.setUniformValue(loc, value)
        except Exception:
            pass

    def _set_uniform1f_gl(self, gl, name: str, value: float) -> None:
        if self._program is None:
            return
        self._set_program_uniform1f_gl(gl, self._program, name, value)

    def _set_program_uniform1f_gl(self, gl, program: QOpenGLShaderProgram, name: str, value: float) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1f"):
                gl.glUniform1f(loc, float(value))
            elif loc >= 0:
                program.setUniformValue(loc, float(value))
        except Exception:
            pass

    @staticmethod
    def _vec3(values, fallback: tuple[float, float, float]) -> QVector3D:
        try:
            return QVector3D(float(values[0]), float(values[1]), float(values[2]))
        except Exception:
            return QVector3D(*fallback)

    @staticmethod
    def _vec4(values, fallback: tuple[float, float, float, float]) -> QVector4D:
        try:
            return QVector4D(float(values[0]), float(values[1]), float(values[2]), float(values[3]))
        except Exception:
            return QVector4D(*fallback)

    def _shadow_params(self, item: dict, bounds: dict) -> dict[str, object]:
        lighting = item.get("lighting") if isinstance(item.get("lighting"), dict) else {}
        size = int(lighting.get("shadow_map_size", 1024) or 1024)
        center = self._vec3(bounds.get("center"), (0.0, 0.0, 0.0))
        light_dir = self._vec3(item.get("light_dir"), (0.42, -0.76, -0.48))
        if light_dir.length() <= 0.001:
            light_dir = QVector3D(0.42, -0.76, -0.48)
        try:
            mins = np.asarray(bounds.get("min") or (-1.0, 0.0, -1.0), dtype=np.float32)
            maxs = np.asarray(bounds.get("max") or (1.0, 1.0, 1.0), dtype=np.float32)
            c = np.asarray(bounds.get("center") or (0.0, 0.0, 0.0), dtype=np.float32)
            light = np.asarray([-light_dir.x(), -light_dir.y(), -light_dir.z()], dtype=np.float32)
            light_len = float(np.linalg.norm(light))
            if light_len <= 0.0001:
                light = np.asarray((-0.42, 0.76, 0.48), dtype=np.float32)
            else:
                light = light / light_len
            up = np.asarray((1.0, 0.0, 0.0), dtype=np.float32) if abs(float(light[1])) > 0.92 else np.asarray((0.0, 1.0, 0.0), dtype=np.float32)
            sx = np.cross(up, light)
            sx = sx / max(0.0001, float(np.linalg.norm(sx)))
            sy = np.cross(light, sx)
            corners = np.asarray(
                [
                    (mins[0], mins[1], mins[2]),
                    (mins[0], mins[1], maxs[2]),
                    (mins[0], maxs[1], mins[2]),
                    (mins[0], maxs[1], maxs[2]),
                    (maxs[0], mins[1], mins[2]),
                    (maxs[0], mins[1], maxs[2]),
                    (maxs[0], maxs[1], mins[2]),
                    (maxs[0], maxs[1], maxs[2]),
                ],
                dtype=np.float32,
            )
            local = corners - c
            radius = max(
                float(np.max(np.abs(local @ sx))),
                float(np.max(np.abs(local @ sy))),
                float(np.max(np.abs(local @ light))),
                0.001,
            ) * 1.10
        except Exception:
            radius = 1.0
        return {
            "enabled": float(lighting.get("soft_shadow_strength", 0.0) or 0.0) > 0.001,
            "size": max(256, min(2048, size)),
            "center": center,
            "radius": max(0.05, radius),
            "light_dir": light_dir,
            "softness": max(0.5, min(4.0, float(lighting.get("shadow_softness", 1.35) or 1.35))),
            "bias": max(0.0002, min(0.04, float(lighting.get("shadow_bias", 0.002) or 0.002))),
            "strength": max(0.0, min(1.0, float(lighting.get("soft_shadow_strength", 0.34) or 0.34))),
            "texture_id": 0,
        }

    def _bind_raw_texture(self, gl, unit: int, texture_id: int) -> bool:
        try:
            if not hasattr(gl, "glActiveTexture") or not hasattr(gl, "glBindTexture"):
                return False
            gl.glActiveTexture(_GL_TEXTURE0 + int(unit))
            gl.glBindTexture(_GL_TEXTURE_2D, int(texture_id))
            if hasattr(gl, "glTexParameteri"):
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MIN_FILTER, _GL_LINEAR)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MAG_FILTER, _GL_LINEAR)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_S, _GL_CLAMP_TO_EDGE)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_T, _GL_CLAMP_TO_EDGE)
            return True
        except Exception:
            return False

    def _bind_bone_texture(self, unit: int, matrices) -> tuple[bool, float]:
        try:
            import OpenGL.GL as GL

            def clear_gl_errors() -> None:
                try:
                    for _ in range(16):
                        if GL.glGetError() == GL.GL_NO_ERROR:
                            break
                except Exception:
                    pass

            arr = np.asarray(matrices, dtype=np.float32)
            if arr.ndim != 3 or arr.shape[1:] != (4, 4) or int(arr.shape[0]) <= 0:
                return False, 0.0
            width = int(arr.shape[0]) * 4
            if width <= 0:
                return False, 0.0
            if self._bone_texture_id <= 0:
                clear_gl_errors()
                generated = GL.glGenTextures(1)
                try:
                    self._bone_texture_id = int(generated)
                except Exception:
                    self._bone_texture_id = int(generated[0])
            if self._bone_texture_id <= 0:
                return False, 0.0

            # GLSL mat4() takes column vectors. CPU skinning stores row-major
            # matrices, so upload the transpose and fetch it as 4 columns.
            packed = np.ascontiguousarray(arr.transpose(0, 2, 1).reshape((1, width, 4)), dtype=np.float32)
            clear_gl_errors()
            GL.glActiveTexture(GL.GL_TEXTURE0 + int(unit))
            clear_gl_errors()
            GL.glBindTexture(GL.GL_TEXTURE_2D, int(self._bone_texture_id))
            clear_gl_errors()
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            clear_gl_errors()
            GL.glTexImage2D(
                GL.GL_TEXTURE_2D,
                0,
                GL.GL_RGBA32F,
                width,
                1,
                0,
                GL.GL_RGBA,
                GL.GL_FLOAT,
                packed,
            )
            clear_gl_errors()
            GL.glActiveTexture(GL.GL_TEXTURE0)
            return True, float(width)
        except Exception as exc:
            if not self._bone_texture_error_logged:
                print(
                    f"[OpenGLPreviewWidget] MMD bone texture upload failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                self._bone_texture_error_logged = True
            return False, 0.0

    def _unbind_raw_texture(self, gl, unit: int) -> None:
        try:
            if hasattr(gl, "glActiveTexture") and hasattr(gl, "glBindTexture"):
                gl.glActiveTexture(_GL_TEXTURE0 + int(unit))
                gl.glBindTexture(_GL_TEXTURE_2D, 0)
                gl.glActiveTexture(_GL_TEXTURE0)
        except Exception:
            pass

    def _set_premultiplied_blend(self, gl) -> None:
        try:
            if hasattr(gl, "glBlendFuncSeparate"):
                gl.glBlendFuncSeparate(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA, _GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
            else:
                gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
        except Exception:
            try:
                gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
            except Exception:
                pass

    def _render_shadow_map(self, gl, item: dict, groups: list[dict], bounds: dict, frame_w: int, frame_h: int) -> dict[str, object]:
        params = self._shadow_params(item, bounds)
        if not bool(params["enabled"]) or self._shadow_program is None or self._vbo is None:
            return params
        size = int(params["size"])
        if not self._ensure_shadow_fbo(size) or self._shadow_fbo is None:
            return params
        if not self._shadow_fbo.bind():
            return params
        shadow_prog = self._shadow_program
        try:
            gl.glViewport(0, 0, size, size)
            gl.glDisable(_GL_BLEND)
            gl.glDisable(_GL_CULL_FACE)
            gl.glEnable(_GL_DEPTH_TEST)
            if hasattr(gl, "glDepthFunc"):
                gl.glDepthFunc(_GL_LEQUAL)
            if hasattr(gl, "glDepthMask"):
                gl.glDepthMask(True)
            gl.glClearColor(1.0, 1.0, 1.0, 1.0)
            gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
            shadow_prog.bind()
            self._set_program_uniform(shadow_prog, "u_shadow_center", params["center"])
            self._set_program_uniform(shadow_prog, "u_shadow_light_dir", params["light_dir"])
            self._set_program_uniform1f_gl(gl, shadow_prog, "u_shadow_radius", float(params["radius"]))
            self._set_program_uniform1i_gl(gl, shadow_prog, "u_tex", 0)
            self._set_program_uniform1i_gl(gl, shadow_prog, "u_bone_tex", 4)
            bone_bound = False
            bone_width = 0.0
            if bool(item.get("gpu_skinning")):
                bone_bound, bone_width = self._bind_bone_texture(4, item.get("bone_matrices"))
            self._set_program_uniform1f_gl(gl, shadow_prog, "u_bone_tex_width", bone_width)
            morph_weights = tuple(float(v) for v in (item.get("gpu_morph_weights") or ())[:2])
            self._set_program_uniform1f_gl(gl, shadow_prog, "u_morph_weight0", morph_weights[0] if len(morph_weights) > 0 else 0.0)
            self._set_program_uniform1f_gl(gl, shadow_prog, "u_morph_weight1", morph_weights[1] if len(morph_weights) > 1 else 0.0)
            for group in groups:
                if not isinstance(group, dict):
                    continue
                if not bool(group.get("casts_self_shadow", group.get("casts_shadow", int(group.get("render_bucket", 0) or 0) < 2))):
                    continue
                vertices = group.get("vertices")
                try:
                    arr = np.asarray(vertices, dtype=np.float32)
                except Exception:
                    continue
                stride_floats = max(8, int(group.get("vertex_stride_floats", 8) or 8))
                stride_bytes = stride_floats * 4
                usable = (arr.size // stride_floats) * stride_floats
                if usable < stride_floats * 3:
                    continue
                arr = np.ascontiguousarray(arr[:usable], dtype=np.float32)
                n_verts = int(arr.size // stride_floats)
                group_gpu_skinning = bool(bone_bound and bool(group.get("gpu_skinning")) and stride_floats >= 16)
                group_gpu_morphs = bool(group_gpu_skinning and stride_floats >= 22 and int(group.get("gpu_morph_slot_count", 0) or 0) > 0)
                tex = self._texture_for_path(str(group.get("texture") or ""))
                has_tex = tex is not None
                if tex is None:
                    tex = self._solid_texture()
                if tex is None:
                    continue
                self._set_program_uniform1i_gl(gl, shadow_prog, "u_has_tex", 1 if has_tex else 0)
                self._set_program_uniform1f_gl(
                    gl,
                    shadow_prog,
                    "u_alpha_cutoff",
                    float(group.get("alpha_cutoff", 0.002) or 0.002),
                )
                self._set_program_uniform1i_gl(gl, shadow_prog, "u_gpu_skinning", 1 if group_gpu_skinning else 0)
                tex.bind(0)
                vbo = self._bind_group_vbo(item, group, arr, stride_floats)
                if vbo is None:
                    tex.release(0)
                    continue
                shadow_prog.enableAttributeArray(0)
                shadow_prog.enableAttributeArray(2)
                shadow_prog.setAttributeBuffer(0, _GL_FLOAT, 0, 3, stride_bytes)
                shadow_prog.setAttributeBuffer(2, _GL_FLOAT, 24, 2, stride_bytes)
                if group_gpu_skinning:
                    shadow_prog.enableAttributeArray(3)
                    shadow_prog.enableAttributeArray(4)
                    shadow_prog.setAttributeBuffer(3, _GL_FLOAT, 32, 4, stride_bytes)
                    shadow_prog.setAttributeBuffer(4, _GL_FLOAT, 48, 4, stride_bytes)
                if group_gpu_morphs:
                    shadow_prog.enableAttributeArray(5)
                    shadow_prog.enableAttributeArray(6)
                    shadow_prog.setAttributeBuffer(5, _GL_FLOAT, 64, 3, stride_bytes)
                    shadow_prog.setAttributeBuffer(6, _GL_FLOAT, 76, 3, stride_bytes)
                gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
                shadow_prog.disableAttributeArray(0)
                shadow_prog.disableAttributeArray(2)
                if group_gpu_skinning:
                    shadow_prog.disableAttributeArray(3)
                    shadow_prog.disableAttributeArray(4)
                if group_gpu_morphs:
                    shadow_prog.disableAttributeArray(5)
                    shadow_prog.disableAttributeArray(6)
                vbo.release()
                tex.release(0)
            shadow_prog.release()
            debug_path = os.environ.get("GIFCAM_MMD_SHADOW_MAP_PNG", "").strip()
            if debug_path:
                try:
                    image = self._shadow_fbo.toImage()
                    image.save(debug_path, "PNG")
                except Exception as exc:
                    print(
                        f"[OpenGLPreviewWidget] MMD shadow map debug save failed: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
            params["texture_id"] = int(self._shadow_fbo.texture())
        finally:
            self._shadow_fbo.release()
            gl.glViewport(0, 0, max(1, int(frame_w)), max(1, int(frame_h)))
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        return params

    def _draw_model_items_to_current_target(
        self,
        gl,
        items: list[dict],
        frame_w: int,
        frame_h: int,
        *,
        bloom_mask: bool = False,
        restore_fbo: QOpenGLFramebufferObject | None = None,
    ) -> bool:
        if not items:
            return True
        if not self._ensure_resources() or self._program is None or self._vbo is None:
            return False
        ww = max(1, int(frame_w))
        wh = max(1, int(frame_h))
        drew_any = False
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glDisable(_GL_CULL_FACE)
        gl.glEnable(_GL_DEPTH_TEST)
        if hasattr(gl, "glDepthFunc"):
            gl.glDepthFunc(_GL_LEQUAL)
        if hasattr(gl, "glDepthMask"):
            gl.glDepthMask(True)
        gl.glClear(_GL_DEPTH_BUFFER_BIT)
        gl.glEnable(_GL_BLEND)
        self._set_premultiplied_blend(gl)

        self._program.bind()
        self._set_uniform("u_tex", 0)
        self._set_uniform("u_sphere_tex", 1)
        self._set_uniform("u_toon_tex", 2)
        self._set_uniform("u_viewport_size", QVector2D(float(ww), float(wh)))
        self._set_uniform1i_gl(gl, "u_tex", 0)
        self._set_uniform1i_gl(gl, "u_sphere_tex", 1)
        self._set_uniform1i_gl(gl, "u_toon_tex", 2)
        self._set_uniform1i_gl(gl, "u_bloom_mask", 1 if bloom_mask else 0)
        self._set_uniform1i_gl(gl, "u_output_premultiplied", 1)
        self._set_uniform1i_gl(gl, "u_shadow_debug", 1 if os.environ.get("GIFCAM_MMD_SHADOW_DEBUG") else 0)
        for item in items:
            if not isinstance(item, dict):
                continue
            groups = item.get("groups")
            if not isinstance(groups, list) or not groups:
                continue
            bounds = item.get("bounds") if isinstance(item.get("bounds"), dict) else {}
            shadow = {"texture_id": 0, "center": self._vec3(bounds.get("center"), (0.0, 0.0, 0.0))}
            if not bloom_mask:
                shadow = self._render_shadow_map(gl, item, groups, bounds, ww, wh)
                if restore_fbo is not None:
                    restore_fbo.bind()
                    gl.glViewport(0, 0, ww, wh)
            self._program.bind()
            self._set_uniform("u_tex", 0)
            self._set_uniform("u_sphere_tex", 1)
            self._set_uniform("u_toon_tex", 2)
            self._set_uniform("u_shadow_tex", 3)
            self._set_uniform("u_viewport_size", QVector2D(float(ww), float(wh)))
            self._set_uniform1i_gl(gl, "u_tex", 0)
            self._set_uniform1i_gl(gl, "u_sphere_tex", 1)
            self._set_uniform1i_gl(gl, "u_toon_tex", 2)
            self._set_uniform1i_gl(gl, "u_shadow_tex", 3)
            self._set_uniform1i_gl(gl, "u_bone_tex", 4)
            self._set_uniform1i_gl(gl, "u_bloom_mask", 1 if bloom_mask else 0)
            self._set_uniform1i_gl(gl, "u_output_premultiplied", 1)
            self._set_uniform1i_gl(gl, "u_shadow_debug", 1 if os.environ.get("GIFCAM_MMD_SHADOW_DEBUG") else 0)
            bone_bound = False
            bone_width = 0.0
            if bool(item.get("gpu_skinning")):
                bone_bound, bone_width = self._bind_bone_texture(4, item.get("bone_matrices"))
            self._set_uniform1f_gl(gl, "u_bone_tex_width", bone_width)
            morph_weights = tuple(float(v) for v in (item.get("gpu_morph_weights") or ())[:2])
            self._set_uniform1f_gl(gl, "u_morph_weight0", morph_weights[0] if len(morph_weights) > 0 else 0.0)
            self._set_uniform1f_gl(gl, "u_morph_weight1", morph_weights[1] if len(morph_weights) > 1 else 0.0)
            center = bounds.get("center") or (0.0, 0.0, 0.0)
            fit_extent = max(0.0001, float(bounds.get("fit_extent") or 1.0))
            zoom = max(0.05, float(item.get("zoom", 1.0) or 1.0))
            scale = zoom * 1.84 / fit_extent
            rotation = QVector3D(
                math.radians(float(item.get("pitch", 0.0) or 0.0)),
                math.radians(float(item.get("yaw", 0.0) or 0.0)),
                math.radians(float(item.get("roll", 0.0) or 0.0)),
            )
            light_dir = self._vec3(item.get("light_dir"), (0.42, -0.76, -0.48))
            if light_dir.length() <= 0.001:
                light_dir = QVector3D(0.42, -0.76, -0.48)
            light_dir.normalize()

            self._set_uniform("u_center", self._vec3(center, (0.0, 0.0, 0.0)))
            self._set_uniform1f_gl(gl, "u_model_scale", float(scale))
            self._set_uniform("u_rotation", rotation)
            self._set_uniform(
                "u_offset",
                QVector2D(
                    float(item.get("offset_x", 0.0) or 0.0),
                    float(item.get("offset_y", 0.0) or 0.0),
                ),
            )
            self._set_uniform("u_light_dir", light_dir)
            lighting = item.get("lighting") if isinstance(item.get("lighting"), dict) else {}
            self._set_uniform("u_fill_dir", self._vec3(lighting.get("fill_dir"), (0.62, -0.28, 0.42)))
            self._set_uniform("u_key_color", self._vec3(lighting.get("key_color"), (1.0, 0.96, 0.90)))
            self._set_uniform("u_fill_color", self._vec3(lighting.get("fill_color"), (0.58, 0.70, 1.0)))
            self._set_uniform("u_rim_color", self._vec3(lighting.get("rim_color"), (0.70, 0.88, 1.0)))
            self._set_uniform("u_sky_color", self._vec3(lighting.get("sky_color"), (0.30, 0.34, 0.42)))
            self._set_uniform("u_ground_color", self._vec3(lighting.get("ground_color"), (0.18, 0.16, 0.14)))
            self._set_uniform("u_bounds_min", self._vec3(bounds.get("min"), (-1.0, 0.0, -1.0)))
            self._set_uniform("u_bounds_max", self._vec3(bounds.get("max"), (1.0, 1.0, 1.0)))
            self._set_uniform1f_gl(gl, "u_key_intensity", float(lighting.get("key_intensity", 0.92) or 0.92))
            self._set_uniform1f_gl(gl, "u_fill_intensity", float(lighting.get("fill_intensity", 0.22) or 0.22))
            self._set_uniform1f_gl(gl, "u_rim_intensity", float(lighting.get("rim_intensity", 0.12) or 0.12))
            self._set_uniform1f_gl(gl, "u_ambient_intensity", float(lighting.get("ambient_intensity", 0.34) or 0.34))
            self._set_uniform1f_gl(gl, "u_shadow_strength", float(lighting.get("shadow_strength", 0.72) or 0.72))
            self._set_uniform1f_gl(
                gl,
                "u_contact_shadow_strength",
                float(lighting.get("contact_shadow_strength", 0.22) or 0.22),
            )
            shadow_texture_id = int(shadow.get("texture_id", 0) or 0) if isinstance(shadow, dict) else 0
            shadow_bound = bool(shadow_texture_id and self._bind_raw_texture(gl, 3, shadow_texture_id))
            self._set_uniform1i_gl(gl, "u_has_shadow_map", 1 if shadow_bound else 0)
            self._set_uniform("u_shadow_center", shadow.get("center") if isinstance(shadow, dict) else self._vec3(center, (0.0, 0.0, 0.0)))
            self._set_uniform1f_gl(gl, "u_shadow_radius", float(shadow.get("radius", 1.0) if isinstance(shadow, dict) else 1.0))
            self._set_uniform1f_gl(gl, "u_shadow_map_size", float(shadow.get("size", 1024) if isinstance(shadow, dict) else 1024))
            self._set_uniform1f_gl(gl, "u_shadow_softness", float(shadow.get("softness", 1.35) if isinstance(shadow, dict) else 1.35))
            self._set_uniform1f_gl(gl, "u_shadow_bias", float(shadow.get("bias", 0.006) if isinstance(shadow, dict) else 0.006))
            self._set_uniform1f_gl(gl, "u_soft_shadow_strength", float(shadow.get("strength", 0.0) if shadow_bound and isinstance(shadow, dict) else 0.0))

            for group in groups:
                if not isinstance(group, dict):
                    continue
                vertices = group.get("vertices")
                try:
                    arr = np.asarray(vertices, dtype=np.float32)
                except Exception:
                    continue
                stride_floats = max(8, int(group.get("vertex_stride_floats", 8) or 8))
                stride_bytes = stride_floats * 4
                usable = (arr.size // stride_floats) * stride_floats
                if usable < stride_floats * 3:
                    continue
                arr = np.ascontiguousarray(arr[:usable], dtype=np.float32)
                n_verts = int(arr.size // stride_floats)
                group_gpu_skinning = bool(bone_bound and bool(group.get("gpu_skinning")) and stride_floats >= 16)
                group_gpu_morphs = bool(group_gpu_skinning and stride_floats >= 22 and int(group.get("gpu_morph_slot_count", 0) or 0) > 0)
                tex = self._texture_for_path(str(group.get("texture") or ""))
                has_tex = tex is not None
                if tex is None:
                    tex = self._solid_texture()
                if tex is None:
                    continue
                sphere_tex = self._texture_for_path(str(group.get("sphere_texture") or ""))
                toon_tex = self._texture_for_path(str(group.get("toon_texture") or ""))

                diffuse = self._vec4(group.get("diffuse"), (0.86, 0.82, 0.78, 1.0))
                edge_color = self._vec4(group.get("edge_color"), (0.02, 0.02, 0.02, 1.0))
                self._set_uniform("u_diffuse", diffuse)
                self._set_uniform("u_ambient", self._vec3(group.get("ambient"), (0.24, 0.24, 0.24)))
                self._set_uniform("u_specular", self._vec3(group.get("specular"), (0.18, 0.18, 0.18)))
                self._set_uniform("u_edge_color", edge_color)
                self._set_uniform("u_toon_shadow_color", self._vec3(group.get("toon_shadow_color"), (0.34, 0.34, 0.34)))
                uv_min = group.get("uv_min") or (0.0, 0.0)
                uv_max = group.get("uv_max") or (1.0, 1.0)
                group_bounds_min = group.get("hair_ring_bounds_min") or group.get("bounds_min") or bounds.get("min") or (-1.0, 0.0, -1.0)
                group_bounds_max = group.get("hair_ring_bounds_max") or group.get("bounds_max") or bounds.get("max") or (1.0, 1.0, 1.0)
                self._set_uniform("u_uv_min", QVector2D(float(uv_min[0]), float(uv_min[1])))
                self._set_uniform("u_uv_max", QVector2D(float(uv_max[0]), float(uv_max[1])))
                self._set_uniform("u_group_bounds_min", self._vec3(group_bounds_min, (-1.0, 0.0, -1.0)))
                self._set_uniform("u_group_bounds_max", self._vec3(group_bounds_max, (1.0, 1.0, 1.0)))
                self._set_uniform1f_gl(gl, "u_specular_strength", float(group.get("specular_strength", 16.0) or 16.0))
                self._set_uniform1f_gl(gl, "u_alpha_cutoff", float(group.get("alpha_cutoff", 0.002) or 0.002))
                self._set_uniform1i_gl(gl, "u_material_class", int(group.get("material_class", 0) or 0))
                self._set_uniform1f_gl(gl, "u_toon_ao_strength", float(group.get("toon_ao_strength", 0.08) or 0.0))
                self._set_uniform1f_gl(gl, "u_skin_warmth", float(group.get("skin_warmth", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_highlight_clamp", float(group.get("highlight_clamp", 1.0) or 1.0))
                self._set_uniform1f_gl(gl, "u_rim_boost", float(group.get("rim_boost", 1.0) or 1.0))
                self._set_uniform1f_gl(gl, "u_sphere_strength", float(group.get("sphere_strength", 1.0) or 1.0))
                self._set_uniform1f_gl(gl, "u_matcap_specular_strength", float(group.get("matcap_specular_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_toon_highlight_strength", float(group.get("toon_highlight_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_toon_highlight_size", float(group.get("toon_highlight_size", 0.62) or 0.62))
                self._set_uniform1f_gl(gl, "u_hair_angel_ring_strength", float(group.get("hair_angel_ring_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_hair_angel_ring_center", float(group.get("hair_angel_ring_center", 0.66) or 0.66))
                self._set_uniform1f_gl(gl, "u_hair_angel_ring_width", float(group.get("hair_angel_ring_width", 0.055) or 0.055))
                self._set_uniform1f_gl(gl, "u_eye_highlight_strength", float(group.get("eye_highlight_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_lip_specular_strength", float(group.get("lip_specular_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_wrap_diffuse", float(group.get("wrap_diffuse", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_emissive_strength", float(group.get("emissive_strength", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_skin_shadow_soften", float(group.get("skin_shadow_soften", 0.0) or 0.0))
                self._set_uniform1f_gl(gl, "u_skin_shadow_lift", float(group.get("skin_shadow_lift", 0.0) or 0.0))
                self._set_uniform1i_gl(gl, "u_has_tex", 1 if has_tex else 0)
                self._set_uniform1i_gl(gl, "u_has_sphere_tex", 1 if sphere_tex is not None else 0)
                self._set_uniform1i_gl(gl, "u_has_toon_tex", 1 if toon_tex is not None else 0)
                self._set_uniform1i_gl(gl, "u_sphere_mode", int(group.get("sphere_mode", 0) or 0))
                self._set_uniform1i_gl(gl, "u_gpu_skinning", 1 if group_gpu_skinning else 0)
                self._set_uniform1i_gl(
                    gl,
                    "u_receive_shadow",
                    1 if bool(group.get("receives_self_shadow", group.get("receives_shadow", True))) else 0,
                )

                tex.bind(0)
                if sphere_tex is not None:
                    sphere_tex.bind(1)
                if toon_tex is not None:
                    toon_tex.bind(2)
                vbo = self._bind_group_vbo(item, group, arr, stride_floats)
                if vbo is None:
                    tex.release(0)
                    if sphere_tex is not None:
                        sphere_tex.release(1)
                    if toon_tex is not None:
                        toon_tex.release(2)
                    continue
                self._program.enableAttributeArray(0)
                self._program.enableAttributeArray(1)
                self._program.enableAttributeArray(2)
                self._program.setAttributeBuffer(0, _GL_FLOAT, 0, 3, stride_bytes)
                self._program.setAttributeBuffer(1, _GL_FLOAT, 12, 3, stride_bytes)
                self._program.setAttributeBuffer(2, _GL_FLOAT, 24, 2, stride_bytes)
                if group_gpu_skinning:
                    self._program.enableAttributeArray(3)
                    self._program.enableAttributeArray(4)
                    self._program.setAttributeBuffer(3, _GL_FLOAT, 32, 4, stride_bytes)
                    self._program.setAttributeBuffer(4, _GL_FLOAT, 48, 4, stride_bytes)
                if group_gpu_morphs:
                    self._program.enableAttributeArray(5)
                    self._program.enableAttributeArray(6)
                    self._program.setAttributeBuffer(5, _GL_FLOAT, 64, 3, stride_bytes)
                    self._program.setAttributeBuffer(6, _GL_FLOAT, 76, 3, stride_bytes)

                outline_size = float(group.get("edge_size", 0.0) or 0.0)
                edge_enabled = bool(group.get("edge_enabled", outline_size > 0.001))
                render_bucket = int(group.get("render_bucket", 0) or 0)
                depth_write = bool(group.get("depth_write", render_bucket < 2))
                if render_bucket >= 2:
                    gl.glEnable(_GL_BLEND)
                    self._set_premultiplied_blend(gl)
                else:
                    gl.glDisable(_GL_BLEND)
                if edge_enabled and outline_size > 0.001:
                    gl.glEnable(_GL_CULL_FACE)
                    if hasattr(gl, "glCullFace"):
                        gl.glCullFace(_GL_FRONT)
                    if hasattr(gl, "glDepthMask"):
                        gl.glDepthMask(False)
                    self._set_uniform1i_gl(gl, "u_outline", 1)
                    self._set_uniform1f_gl(
                        gl,
                        "u_outline_width",
                        max(0.004, min(outline_size, 2.0) * 0.075),
                    )
                    gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
                    if hasattr(gl, "glDepthMask"):
                        gl.glDepthMask(True)
                    if hasattr(gl, "glCullFace"):
                        gl.glCullFace(_GL_BACK)
                    gl.glDisable(_GL_CULL_FACE)
                self._set_uniform1i_gl(gl, "u_outline", 0)
                self._set_uniform1f_gl(gl, "u_outline_width", 0.0)
                if hasattr(gl, "glDepthMask"):
                    gl.glDepthMask(True if depth_write else False)
                gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
                if hasattr(gl, "glDepthMask"):
                    gl.glDepthMask(True)
                if render_bucket >= 2:
                    gl.glDisable(_GL_BLEND)
                self._program.disableAttributeArray(0)
                self._program.disableAttributeArray(1)
                self._program.disableAttributeArray(2)
                if group_gpu_skinning:
                    self._program.disableAttributeArray(3)
                    self._program.disableAttributeArray(4)
                if group_gpu_morphs:
                    self._program.disableAttributeArray(5)
                    self._program.disableAttributeArray(6)
                vbo.release()
                tex.release(0)
                if sphere_tex is not None:
                    sphere_tex.release(1)
                if toon_tex is not None:
                    toon_tex.release(2)
                drew_any = True
            if shadow_bound:
                self._unbind_raw_texture(gl, 3)
        self._program.release()
        gl.glDisable(_GL_CULL_FACE)
        gl.glDisable(_GL_DEPTH_TEST)
        return drew_any

    @staticmethod
    def _bloom_params(items: list[dict]) -> dict[str, float | bool]:
        enabled = False
        strength = 0.0
        radius = 2.0
        threshold = 1.0
        for item in items:
            if not isinstance(item, dict):
                continue
            lighting = item.get("lighting") if isinstance(item.get("lighting"), dict) else {}
            if not bool(lighting.get("bloom_enabled", True)):
                continue
            enabled = True
            try:
                strength = max(strength, float(lighting.get("bloom_strength", 0.30) or 0.0))
            except Exception:
                strength = max(strength, 0.30)
            try:
                radius = max(radius, float(lighting.get("bloom_radius", 2.0) or 2.0))
            except Exception:
                radius = max(radius, 2.0)
            try:
                threshold = min(threshold, float(lighting.get("bloom_threshold", 0.08) or 0.08))
            except Exception:
                threshold = min(threshold, 0.08)
        return {
            "enabled": enabled,
            "strength": max(0.0, min(2.0, strength if enabled else 0.0)),
            "radius": max(0.5, min(8.0, radius)),
            "threshold": max(0.0, min(1.0, threshold if enabled else 0.08)),
        }

    @staticmethod
    def _project_mmd_point(item: dict, bounds: dict, point: tuple[float, float, float], width: int, height: int) -> tuple[float, float]:
        center = bounds.get("center") or (0.0, 0.0, 0.0)
        fit_extent = max(0.0001, float(bounds.get("fit_extent") or 1.0))
        zoom = max(0.05, float(item.get("zoom", 1.0) or 1.0))
        scale = zoom * 1.84 / fit_extent
        pitch = math.radians(float(item.get("pitch", 0.0) or 0.0))
        yaw = math.radians(float(item.get("yaw", 0.0) or 0.0))
        roll = math.radians(float(item.get("roll", 0.0) or 0.0))
        cx, sx = math.cos(pitch), math.sin(pitch)
        cy, sy = math.cos(yaw), math.sin(yaw)
        cz, sz = math.cos(roll), math.sin(roll)
        rx = np.asarray([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float32)
        ry = np.asarray([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float32)
        rz = np.asarray([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        local = (np.asarray(point, dtype=np.float32) - np.asarray(center, dtype=np.float32)) * float(scale)
        p = (ry @ rx @ rz) @ local
        camera = 3.2
        z = float(p[2]) + camera
        persp = camera / max(0.35, z)
        aspect = max(1.0, float(width)) / max(1.0, float(height))
        offset_x = float(item.get("offset_x", 0.0) or 0.0)
        offset_y = float(item.get("offset_y", 0.0) or 0.0)
        ndc_x = (float(p[0]) * persp) / max(0.1, aspect) + offset_x
        ndc_y = float(p[1]) * persp + offset_y
        return ndc_x * 0.5 + 0.5, ndc_y * 0.5 + 0.5

    def _ground_shadow_params(self, items: list[dict], width: int, height: int) -> dict[str, object]:
        best: dict[str, object] = {
            "center": QVector2D(0.5, 0.18),
            "radius": QVector2D(0.16, 0.035),
            "color": QVector3D(0.0, 0.0, 0.0),
            "strength": 0.0,
        }
        for item in items:
            if not isinstance(item, dict):
                continue
            bounds = item.get("bounds") if isinstance(item.get("bounds"), dict) else {}
            lighting = item.get("lighting") if isinstance(item.get("lighting"), dict) else {}
            strength = max(0.0, min(0.75, float(lighting.get("ground_shadow_strength", 0.0) or 0.0)))
            if strength <= float(best["strength"]):
                continue
            mins = bounds.get("min") or (-1.0, 0.0, -1.0)
            maxs = bounds.get("max") or (1.0, 1.0, 1.0)
            center = bounds.get("center") or (0.0, 0.0, 0.0)
            foot = (float(center[0]), float(mins[1]), float(center[2]))
            center_uv = self._project_mmd_point(item, bounds, foot, width, height)
            left_uv = self._project_mmd_point(item, bounds, (float(mins[0]), float(mins[1]), float(center[2])), width, height)
            right_uv = self._project_mmd_point(item, bounds, (float(maxs[0]), float(mins[1]), float(center[2])), width, height)
            radius_x = abs(float(right_uv[0]) - float(left_uv[0])) * 0.46
            radius_x = max(0.055, min(0.24, radius_x))
            radius_y = max(0.016, min(0.055, radius_x * 0.22))
            color_values = lighting.get("ground_shadow_color") or (0.0, 0.0, 0.0)
            best = {
                "center": QVector2D(float(center_uv[0]), max(0.02, min(0.98, float(center_uv[1]) - radius_y * 0.22))),
                "radius": QVector2D(radius_x, radius_y),
                "color": self._vec3(color_values, (0.0, 0.0, 0.0)),
                "strength": strength,
            }
        return best

    def _composite_mmd_layer(self, gl, width: int, height: int, params: dict[str, float | bool]) -> bool:
        if (
            self._composite_program is None
            or self._quad_vbo is None
            or self._layer_fbo is None
            or self._bloom_fbo is None
        ):
            return False
        program = self._composite_program
        program.bind()
        self._set_program_uniform1i_gl(gl, program, "u_layer_tex", 0)
        self._set_program_uniform1i_gl(gl, program, "u_bloom_tex", 1)
        self._set_program_uniform(program, "u_texel_size", QVector2D(1.0 / max(1.0, float(width)), 1.0 / max(1.0, float(height))))
        self._set_program_uniform1f_gl(gl, program, "u_bloom_strength", float(params.get("strength", 0.0) or 0.0))
        self._set_program_uniform1f_gl(gl, program, "u_bloom_radius", float(params.get("radius", 2.0) or 2.0))
        self._set_program_uniform1f_gl(gl, program, "u_bloom_threshold", float(params.get("threshold", 0.08) or 0.08))
        self._set_program_uniform(program, "u_ground_shadow_center", params.get("ground_center") or QVector2D(0.5, 0.18))
        self._set_program_uniform(program, "u_ground_shadow_radius", params.get("ground_radius") or QVector2D(0.16, 0.035))
        self._set_program_uniform(program, "u_ground_shadow_color", params.get("ground_color") or QVector3D(0.0, 0.0, 0.0))
        self._set_program_uniform1f_gl(gl, program, "u_ground_shadow_strength", float(params.get("ground_strength", 0.0) or 0.0))
        layer_bound = self._bind_raw_texture(gl, 0, int(self._layer_fbo.texture()))
        bloom_bound = self._bind_raw_texture(gl, 1, int(self._bloom_fbo.texture()))
        if not layer_bound or not bloom_bound:
            program.release()
            self._unbind_raw_texture(gl, 0)
            self._unbind_raw_texture(gl, 1)
            return False
        quad = np.asarray(
            [
                -1.0, -1.0, 0.0, 0.0,
                1.0, -1.0, 1.0, 0.0,
                -1.0, 1.0, 0.0, 1.0,
                1.0, 1.0, 1.0, 1.0,
            ],
            dtype=np.float32,
        )
        gl.glDisable(_GL_DEPTH_TEST)
        gl.glDisable(_GL_CULL_FACE)
        gl.glEnable(_GL_BLEND)
        self._set_premultiplied_blend(gl)
        self._quad_vbo.bind()
        self._quad_vbo.allocate(quad.tobytes(), int(quad.nbytes))
        stride_bytes = 4 * 4
        program.enableAttributeArray(0)
        program.enableAttributeArray(1)
        program.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride_bytes)
        program.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride_bytes)
        gl.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)
        program.disableAttributeArray(0)
        program.disableAttributeArray(1)
        self._quad_vbo.release()
        self._unbind_raw_texture(gl, 0)
        self._unbind_raw_texture(gl, 1)
        program.release()
        return True

    def draw(
        self,
        gl,
        items: list[dict],
        frame_w: int,
        frame_h: int,
        viewport: tuple[int, int, int, int] | None = None,
        *,
        restore_fbo: QOpenGLFramebufferObject | None = None,
    ) -> bool:
        if not items:
            return True
        self._reset_vbo_frame_stats()
        if not self._ensure_resources():
            return False
        if viewport is not None:
            vx, vy, vw, vh = (int(viewport[0]), int(viewport[1]), int(viewport[2]), int(viewport[3]))
        else:
            vx, vy, vw, vh = (0, 0, int(frame_w), int(frame_h))
        target_w = max(16, int(vw or frame_w or 1))
        target_h = max(16, int(vh or frame_h or 1))
        if not self._ensure_layer_fbos(target_w, target_h) or self._layer_fbo is None or self._bloom_fbo is None:
            ok = self._draw_model_items_to_current_target(
                gl,
                items,
                target_w,
                target_h,
                bloom_mask=False,
                restore_fbo=restore_fbo,
            )
            self._attach_vbo_diagnostics(items)
            return ok

        drew_layer = False
        try:
            if self._layer_fbo.bind():
                gl.glViewport(0, 0, target_w, target_h)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
                drew_layer = self._draw_model_items_to_current_target(
                    gl,
                    items,
                    target_w,
                    target_h,
                    bloom_mask=False,
                    restore_fbo=self._layer_fbo,
                )
        finally:
            self._layer_fbo.release()

        try:
            if self._bloom_fbo.bind():
                gl.glViewport(0, 0, target_w, target_h)
                gl.glClearColor(0.0, 0.0, 0.0, 0.0)
                gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
                self._draw_model_items_to_current_target(gl, items, target_w, target_h, bloom_mask=True)
        finally:
            self._bloom_fbo.release()

        if restore_fbo is not None:
            restore_fbo.bind()
        gl.glViewport(vx, vy, target_w, target_h)
        params = self._bloom_params(items)
        ground = self._ground_shadow_params(items, target_w, target_h)
        params.update(
            {
                "ground_center": ground["center"],
                "ground_radius": ground["radius"],
                "ground_color": ground["color"],
                "ground_strength": ground["strength"],
            }
        )
        ok = self._composite_mmd_layer(gl, target_w, target_h, params)
        gl.glViewport(vx, vy, target_w, target_h)
        self._attach_vbo_diagnostics(items)
        return bool(drew_layer and ok)


class _ARPBRDirectGLPainter:
    """Draw AR/PBR preview mesh packets in the current preview GL context."""

    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._pbr_program: QOpenGLShaderProgram | None = None
        self._pbr_vbo: QOpenGLBuffer | None = None
        self._pbr_shadow_program: QOpenGLShaderProgram | None = None
        self._pbr_shadow_vbo: QOpenGLBuffer | None = None
        self._pbr_shadow_fbo: QOpenGLFramebufferObject | None = None
        self._pbr_shadow_fbo_size = 0
        self._texture_cache: dict[tuple[str, int, int], QOpenGLTexture] = {}
        self._texture_cache_order: list[tuple[str, int, int]] = []
        self._hdri_texture_cache: dict[tuple[str, int, int], QOpenGLTexture] = {}
        self._hdri_texture_cache_order: list[tuple[str, int, int]] = []
        self._ibl_texture_cache: dict[tuple[str, int, int], dict[str, object]] = {}
        self._ibl_texture_cache_order: list[tuple[str, int, int]] = []
        self._depth_texture_cache: dict[tuple[int, tuple[int, ...], int], QOpenGLTexture] = {}
        self._depth_texture_cache_order: list[tuple[int, tuple[int, ...], int]] = []
        self._solid_white_texture: QOpenGLTexture | None = None
        self._texture_cache_limit = 32
        self._packet_vbo_cache: dict[tuple[object, ...], tuple[QOpenGLBuffer, int]] = {}
        self._packet_vbo_cache_order: list[tuple[object, ...]] = []
        self._packet_vbo_cache_limit = 96
        self._pbr_batch_cache: dict[tuple[object, ...], list[dict]] = {}
        self._pbr_batch_cache_order: list[tuple[object, ...]] = []
        self._pbr_batch_cache_limit = 48
        self._packet_vbo_stats: dict[str, int] = {
            "binds": 0,
            "hits": 0,
            "misses": 0,
            "transient_uploads": 0,
            "uploaded_bytes": 0,
            "evictions": 0,
        }

    def _record_packet_vbo_stat(self, key: str, amount: int = 1) -> None:
        try:
            self._packet_vbo_stats[key] = int(self._packet_vbo_stats.get(key, 0) or 0) + int(amount)
        except Exception:
            pass

    def vbo_diagnostics(self) -> dict[str, object]:
        stats = dict(self._packet_vbo_stats)
        binds = int(stats.get("binds", 0) or 0)
        hits = int(stats.get("hits", 0) or 0)
        misses = int(stats.get("misses", 0) or 0)
        cached_bytes = 0
        for _key, (_vbo, nbytes) in self._packet_vbo_cache.items():
            cached_bytes += int(nbytes)
        attempts = hits + misses
        return {
            "ar_pbr_vbo_cache_enabled": True,
            "ar_pbr_vbo_cache_size": int(len(self._packet_vbo_cache)),
            "ar_pbr_vbo_cache_limit": int(self._packet_vbo_cache_limit),
            "ar_pbr_vbo_cache_binds": binds,
            "ar_pbr_vbo_cache_hits": hits,
            "ar_pbr_vbo_cache_misses": misses,
            "ar_pbr_vbo_cache_hit_rate": float(hits / attempts) if attempts > 0 else 0.0,
            "ar_pbr_vbo_transient_uploads": int(stats.get("transient_uploads", 0) or 0),
            "ar_pbr_vbo_uploaded_bytes": int(stats.get("uploaded_bytes", 0) or 0),
            "ar_pbr_vbo_cached_bytes": int(cached_bytes),
            "ar_pbr_vbo_cache_evictions": int(stats.get("evictions", 0) or 0),
            "ar_pbr_pbr_batch_cache_size": int(len(self._pbr_batch_cache)),
            "ar_pbr_pbr_batch_cache_limit": int(self._pbr_batch_cache_limit),
        }

    def _attach_vbo_diagnostics(self, items: list[dict]) -> None:
        snapshot = self.vbo_diagnostics()
        for item in items:
            if not isinstance(item, dict):
                continue
            diagnostics = dict(item.get("diagnostics") or {})
            diagnostics.update(snapshot)
            item["diagnostics"] = diagnostics

    @staticmethod
    def _packet_cache_token(item: dict) -> str:
        if not isinstance(item, dict):
            return ""
        return str(item.get("packet_cache_id") or item.get("cache_id") or "")

    def _vbo_cache_key(
        self,
        kind: str,
        item: dict | None,
        suffix: object,
        raw_len: int,
        stride_floats: int,
    ) -> tuple[object, ...] | None:
        token = self._packet_cache_token(item or {})
        if not token:
            return None
        return (
            "ar_pbr_packet_vbo",
            str(token),
            str(kind),
            suffix,
            int(raw_len),
            int(stride_floats),
        )

    def _bind_packet_vbo(
        self,
        raw: list[float] | tuple[float, ...],
        fallback_vbo: QOpenGLBuffer,
        cache_key: tuple[object, ...] | None,
    ) -> QOpenGLBuffer | None:
        self._record_packet_vbo_stat("binds")
        if cache_key is not None:
            cached = self._packet_vbo_cache.get(cache_key)
            if cached is not None:
                vbo, _nbytes = cached
                if cache_key in self._packet_vbo_cache_order:
                    self._packet_vbo_cache_order.remove(cache_key)
                self._packet_vbo_cache_order.append(cache_key)
                vbo.bind()
                self._record_packet_vbo_stat("hits")
                return vbo
        arr = np.asarray(raw, dtype=np.float32)
        if int(arr.size) <= 0:
            return None
        arr = np.ascontiguousarray(arr)
        if cache_key is None:
            fallback_vbo.bind()
            fallback_vbo.allocate(arr.tobytes(), int(arr.nbytes))
            self._record_packet_vbo_stat("transient_uploads")
            self._record_packet_vbo_stat("uploaded_bytes", int(arr.nbytes))
            return fallback_vbo
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            fallback_vbo.bind()
            fallback_vbo.allocate(arr.tobytes(), int(arr.nbytes))
            self._record_packet_vbo_stat("transient_uploads")
            self._record_packet_vbo_stat("uploaded_bytes", int(arr.nbytes))
            return fallback_vbo
        vbo.bind()
        vbo.allocate(arr.tobytes(), int(arr.nbytes))
        self._record_packet_vbo_stat("misses")
        self._record_packet_vbo_stat("uploaded_bytes", int(arr.nbytes))
        self._packet_vbo_cache[cache_key] = (vbo, int(arr.nbytes))
        self._packet_vbo_cache_order.append(cache_key)
        while len(self._packet_vbo_cache_order) > self._packet_vbo_cache_limit:
            old_key = self._packet_vbo_cache_order.pop(0)
            old = self._packet_vbo_cache.pop(old_key, None)
            if old is not None:
                self._record_packet_vbo_stat("evictions")
                try:
                    old[0].destroy()
                except Exception:
                    pass
        return vbo

    def _pbr_batch_cache_key(self, item: dict, include_object_depth: bool) -> tuple[object, ...] | None:
        token = self._packet_cache_token(item)
        if not token:
            return None
        rows = item.get("pbr_triangles") if isinstance(item, dict) else None
        if not isinstance(rows, list):
            return None
        return (
            "ar_pbr_pbr_batches",
            str(token),
            bool(include_object_depth),
            int(len(rows)),
            int(item.get("pbr_triangle_count", len(rows)) or len(rows)),
        )

    def _pbr_batches_for_item(self, item: dict, *, include_object_depth: bool = False) -> list[dict]:
        rows = item.get("pbr_triangles") if isinstance(item, dict) else None
        if not isinstance(rows, list):
            return []
        cache_key = self._pbr_batch_cache_key(item, include_object_depth)
        if cache_key is not None:
            cached = self._pbr_batch_cache.get(cache_key)
            if cached is not None:
                if cache_key in self._pbr_batch_cache_order:
                    self._pbr_batch_cache_order.remove(cache_key)
                self._pbr_batch_cache_order.append(cache_key)
                return cached
        batches = self._pbr_row_batches(rows, include_object_depth=include_object_depth)
        if cache_key is not None:
            self._pbr_batch_cache[cache_key] = batches
            self._pbr_batch_cache_order.append(cache_key)
            while len(self._pbr_batch_cache_order) > self._pbr_batch_cache_limit:
                old_key = self._pbr_batch_cache_order.pop(0)
                self._pbr_batch_cache.pop(old_key, None)
        return batches

    def _ensure_resources(self) -> bool:
        if self._program is not None and self._vbo is not None:
            return True
        prog = QOpenGLShaderProgram(self._parent)
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _AR_PBR_VERTEX_SHADER,
        )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _AR_PBR_FRAGMENT_SHADER,
        )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_color", 1)
        if not ok_v or not ok_f or not prog.link():
            print(
                f"[OpenGLPreviewWidget] AR/PBR direct shader failed:\n{prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return False
        self._program = prog
        self._vbo = vbo
        return True

    def _ensure_pbr_resources(self) -> bool:
        if self._pbr_program is not None and self._pbr_vbo is not None:
            return True
        prog = QOpenGLShaderProgram(self._parent)
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _AR_PBR_TEXTURE_VERTEX_SHADER,
        )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _AR_PBR_TEXTURE_FRAGMENT_SHADER,
        )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_uv", 1)
        prog.bindAttributeLocation("a_normal", 2)
        prog.bindAttributeLocation("a_tangent", 3)
        prog.bindAttributeLocation("a_bitangent", 4)
        prog.bindAttributeLocation("a_color", 5)
        prog.bindAttributeLocation("a_material", 6)
        prog.bindAttributeLocation("a_world_pos", 7)
        if not ok_v or not ok_f or not prog.link():
            print(
                f"[OpenGLPreviewWidget] AR/PBR textured shader failed:\n{prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return False
        self._pbr_program = prog
        self._pbr_vbo = vbo
        return True

    def _ensure_pbr_shadow_resources(self) -> bool:
        if self._pbr_shadow_program is not None and self._pbr_shadow_vbo is not None:
            return True
        prog = QOpenGLShaderProgram(self._parent)
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _AR_PBR_TEXTURE_SHADOW_VERTEX_SHADER,
        )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _AR_PBR_TEXTURE_SHADOW_FRAGMENT_SHADER,
        )
        prog.bindAttributeLocation("a_world_pos", 0)
        prog.bindAttributeLocation("a_uv", 1)
        if not ok_v or not ok_f or not prog.link():
            print(
                f"[OpenGLPreviewWidget] AR/PBR textured shadow shader failed:\n{prog.log()}",
                file=sys.stderr,
                flush=True,
            )
            return False
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not vbo.create():
            return False
        self._pbr_shadow_program = prog
        self._pbr_shadow_vbo = vbo
        return True

    def _ensure_pbr_shadow_fbo(self, size: int) -> bool:
        size = max(256, min(2048, int(size or 1024)))
        if self._pbr_shadow_fbo is not None and self._pbr_shadow_fbo_size == size:
            return True
        self._pbr_shadow_fbo = None
        fmt = QOpenGLFramebufferObjectFormat()
        fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
        fbo = QOpenGLFramebufferObject(size, size, fmt)
        if not fbo.isValid():
            return False
        self._pbr_shadow_fbo = fbo
        self._pbr_shadow_fbo_size = size
        return True

    @staticmethod
    def _normalize_texture_wrap_name(value: object) -> str:
        text = str(value or "").strip().casefold().replace("-", "_")
        if text in {"33071", "clamp", "clamp_to_edge", "clampedge"}:
            return "clamp_to_edge"
        if text in {"33648", "mirror", "mirrored", "mirrored_repeat", "mirror_repeat"}:
            return "mirrored_repeat"
        return "repeat"

    @classmethod
    def _qt_texture_wrap_mode(cls, value: object):
        name = cls._normalize_texture_wrap_name(value)
        if name == "clamp_to_edge":
            return QOpenGLTexture.WrapMode.ClampToEdge
        if name == "mirrored_repeat":
            return QOpenGLTexture.WrapMode.MirroredRepeat
        return QOpenGLTexture.WrapMode.Repeat

    @classmethod
    def _set_texture_wrap_modes(cls, tex: QOpenGLTexture, wrap_s: object, wrap_t: object) -> None:
        mode_s = cls._qt_texture_wrap_mode(wrap_s)
        mode_t = cls._qt_texture_wrap_mode(wrap_t)
        try:
            tex.setWrapMode(QOpenGLTexture.CoordinateDirection.DirectionS, mode_s)
            tex.setWrapMode(QOpenGLTexture.CoordinateDirection.DirectionT, mode_t)
        except Exception:
            tex.setWrapMode(mode_s if mode_s == mode_t else QOpenGLTexture.WrapMode.Repeat)

    @classmethod
    def _texture_wrap_for_map(cls, maps: dict, map_name: str) -> tuple[str, str]:
        wrap_s = maps.get(f"{map_name}_wrap_s") if isinstance(maps, dict) else None
        wrap_t = maps.get(f"{map_name}_wrap_t") if isinstance(maps, dict) else None
        if wrap_s is None and isinstance(maps, dict):
            wrap_s = maps.get("wrap_s")
        if wrap_t is None and isinstance(maps, dict):
            wrap_t = maps.get("wrap_t")
        return (
            cls._normalize_texture_wrap_name(wrap_s or "repeat"),
            cls._normalize_texture_wrap_name(wrap_t or "repeat"),
        )

    @classmethod
    def _texture_key(cls, path: str, wrap_s: object = "repeat", wrap_t: object = "repeat") -> tuple[str, int, int, str, str] | None:
        if not str(path or "").strip():
            return None
        try:
            p = Path(str(path))
            if not p.is_file():
                return None
            st = p.stat()
            return (
                str(p.resolve()),
                int(st.st_size),
                int(st.st_mtime_ns),
                cls._normalize_texture_wrap_name(wrap_s),
                cls._normalize_texture_wrap_name(wrap_t),
            )
        except Exception:
            return None

    @staticmethod
    def _vec3(values, fallback: tuple[float, float, float]) -> QVector3D:
        try:
            return QVector3D(float(values[0]), float(values[1]), float(values[2]))
        except Exception:
            return QVector3D(*fallback)

    def _texture_for_path(self, path: str, wrap_s: object = "repeat", wrap_t: object = "repeat") -> QOpenGLTexture | None:
        key = self._texture_key(path, wrap_s, wrap_t)
        if key is None:
            return None
        cached = self._texture_cache.get(key)
        if cached is not None:
            if key in self._texture_cache_order:
                self._texture_cache_order.remove(key)
            self._texture_cache_order.append(key)
            return cached
        try:
            from PIL import Image

            image = Image.open(key[0]).convert("RGBA")
            image.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            arr = np.ascontiguousarray(np.asarray(image, dtype=np.uint8))
            h, w = int(arr.shape[0]), int(arr.shape[1])
            qimg = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(0)
            tex.setMinificationFilter(QOpenGLTexture.Filter.LinearMipMapLinear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            self._set_texture_wrap_modes(tex, key[3], key[4])
            tex.setData(qimg)
            try:
                tex.generateMipMaps()
            except Exception:
                pass
            tex.release(0)
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR texture upload failed for {path}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        self._texture_cache[key] = tex
        self._texture_cache_order.append(key)
        while len(self._texture_cache_order) > self._texture_cache_limit:
            old_key = self._texture_cache_order.pop(0)
            old = self._texture_cache.pop(old_key, None)
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
        return tex

    def _white_texture(self) -> QOpenGLTexture | None:
        if self._solid_white_texture is not None:
            return self._solid_white_texture
        try:
            arr = np.ascontiguousarray(np.asarray([[[255, 255, 255, 255]]], dtype=np.uint8))
            qimg = QImage(arr.data, 1, 1, 4, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(0)
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release(0)
            self._solid_white_texture = tex
            return tex
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR white texture fallback failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None

    def _hdri_texture_for_path(self, path: str) -> QOpenGLTexture | None:
        key = self._texture_key(path)
        if key is None:
            return None
        cached = self._hdri_texture_cache.get(key)
        if cached is not None:
            if key in self._hdri_texture_cache_order:
                self._hdri_texture_cache_order.remove(key)
            self._hdri_texture_cache_order.append(key)
            return cached
        try:
            from app.ar_pbr.hdr import load_radiance_hdr

            hdr = load_radiance_hdr(key[0])
            rgb = np.asarray(hdr.pixels, dtype=np.float32)
            rgb = np.nan_to_num(rgb, nan=0.0, posinf=0.0, neginf=0.0)
            rgb = np.maximum(rgb, 0.0)
            # ACES preview tonemap to an 8-bit environment texture. Exposure
            # remains a shader uniform so the track lighting still controls it.
            a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
            mapped = np.clip((rgb * (a * rgb + b)) / (rgb * (c * rgb + d) + e), 0.0, 1.0)
            mapped = np.power(mapped, 1.0 / 2.2)
            arr = np.ascontiguousarray(np.round(mapped * 255.0).astype(np.uint8))
            h, w = int(arr.shape[0]), int(arr.shape[1])
            alpha = np.full((h, w, 1), 255, dtype=np.uint8)
            rgba = np.ascontiguousarray(np.concatenate([arr, alpha], axis=2))
            qimg = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(5)
            tex.setMinificationFilter(QOpenGLTexture.Filter.LinearMipMapLinear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.Repeat)
            tex.setData(qimg)
            try:
                tex.generateMipMaps()
            except Exception:
                pass
            tex.release(5)
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR HDRI upload failed for {path}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        self._hdri_texture_cache[key] = tex
        self._hdri_texture_cache_order.append(key)
        while len(self._hdri_texture_cache_order) > 8:
            old_key = self._hdri_texture_cache_order.pop(0)
            old = self._hdri_texture_cache.pop(old_key, None)
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
        return tex

    @staticmethod
    def _encoded_ibl_rgba(rgb) -> np.ndarray:
        arr = np.asarray(rgb, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[2] < 3:
            arr = np.zeros((1, 1, 3), dtype=np.float32)
        arr = np.nan_to_num(arr[:, :, :3], nan=0.0, posinf=16.0, neginf=0.0)
        arr = np.maximum(arr, 0.0)
        mapped = np.clip((arr * (2.51 * arr + 0.03)) / (arr * (2.43 * arr + 0.59) + 0.14), 0.0, 1.0)
        mapped = np.power(mapped, 1.0 / 2.2)
        rgb8 = np.ascontiguousarray(np.round(mapped * 255.0).astype(np.uint8))
        alpha = np.full((rgb8.shape[0], rgb8.shape[1], 1), 255, dtype=np.uint8)
        return np.ascontiguousarray(np.concatenate([rgb8, alpha], axis=2))

    @staticmethod
    def _encoded_lut_rgba(lut) -> np.ndarray:
        arr = np.asarray(lut, dtype=np.float32)
        if arr.ndim != 3 or arr.shape[2] < 2:
            arr = np.zeros((1, 1, 2), dtype=np.float32)
        rg = np.clip(arr[:, :, :2], 0.0, 1.0)
        h, w = int(rg.shape[0]), int(rg.shape[1])
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0:2] = np.round(rg * 255.0).astype(np.uint8)
        rgba[:, :, 3] = 255
        return np.ascontiguousarray(rgba)

    @staticmethod
    def _texture_from_rgba_array(rgba: np.ndarray, unit: int) -> QOpenGLTexture | None:
        try:
            arr = np.ascontiguousarray(np.asarray(rgba, dtype=np.uint8))
            if arr.ndim != 3 or arr.shape[2] != 4:
                return None
            h, w = int(arr.shape[0]), int(arr.shape[1])
            qimg = QImage(arr.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(int(unit))
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release(int(unit))
            return tex
        except Exception:
            return None

    @classmethod
    def _prefilter_atlas_rgba(cls, levels) -> tuple[np.ndarray, int]:
        rows = [np.asarray(level, dtype=np.float32) for level in levels if level is not None]
        if not rows:
            return cls._encoded_ibl_rgba(np.zeros((1, 1, 3), dtype=np.float32)), 0
        try:
            from PIL import Image

            base_h, base_w = int(rows[0].shape[0]), int(rows[0].shape[1])
            base_w = max(1, min(512, base_w))
            base_h = max(1, min(256, base_h))
            encoded_rows: list[np.ndarray] = []
            for row in rows:
                rgba = cls._encoded_ibl_rgba(row)
                image = Image.fromarray(rgba, "RGBA")
                if image.size != (base_w, base_h):
                    image = image.resize((base_w, base_h), Image.Resampling.BILINEAR)
                encoded_rows.append(np.asarray(image, dtype=np.uint8))
            atlas = np.concatenate(encoded_rows, axis=0)
            return np.ascontiguousarray(atlas), len(encoded_rows)
        except Exception:
            return cls._encoded_ibl_rgba(rows[0]), 1

    @staticmethod
    def _destroy_texture(value) -> None:
        if value is None:
            return
        try:
            value.destroy()
        except Exception:
            pass

    def _ibl_texture_bundle_for_path(self, path: str) -> dict[str, object] | None:
        key = self._texture_key(path)
        if key is None:
            return None
        cached = self._ibl_texture_cache.get(key)
        if cached is not None:
            if key in self._ibl_texture_cache_order:
                self._ibl_texture_cache_order.remove(key)
            self._ibl_texture_cache_order.append(key)
            return cached
        try:
            from app.ar_pbr.ibl import load_ibl_probe

            probe = load_ibl_probe(key[0])
            if probe is None or not probe.available:
                return None
            irradiance = self._texture_from_rgba_array(self._encoded_ibl_rgba(probe.irradiance_map), 9)
            prefilter_rgba, level_count = self._prefilter_atlas_rgba(probe.prefiltered_levels)
            prefilter = self._texture_from_rgba_array(prefilter_rgba, 10)
            brdf = self._texture_from_rgba_array(self._encoded_lut_rgba(probe.brdf_lut), 11)
            if irradiance is None or prefilter is None or brdf is None or level_count <= 0:
                self._destroy_texture(irradiance)
                self._destroy_texture(prefilter)
                self._destroy_texture(brdf)
                return None
            bundle: dict[str, object] = {
                "irradiance": irradiance,
                "prefilter": prefilter,
                "brdf": brdf,
                "level_count": float(level_count),
                "diagnostics": probe.diagnostics(),
            }
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR IBL probe upload failed for {path}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        self._ibl_texture_cache[key] = bundle
        self._ibl_texture_cache_order.append(key)
        while len(self._ibl_texture_cache_order) > 8:
            old_key = self._ibl_texture_cache_order.pop(0)
            old = self._ibl_texture_cache.pop(old_key, None)
            if old is not None:
                self._destroy_texture(old.get("irradiance"))
                self._destroy_texture(old.get("prefilter"))
                self._destroy_texture(old.get("brdf"))
        return bundle

    @staticmethod
    def _bind_ibl_bundle(bundle: dict[str, object] | None) -> bool:
        if not bundle:
            return False
        try:
            bundle["irradiance"].bind(9)  # type: ignore[union-attr]
            bundle["prefilter"].bind(10)  # type: ignore[union-attr]
            bundle["brdf"].bind(11)  # type: ignore[union-attr]
            return True
        except Exception:
            return False

    @staticmethod
    def _release_ibl_bundle(bundle: dict[str, object] | None) -> None:
        if not bundle:
            return
        try:
            bundle["irradiance"].release(9)  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            bundle["prefilter"].release(10)  # type: ignore[union-attr]
        except Exception:
            pass
        try:
            bundle["brdf"].release(11)  # type: ignore[union-attr]
        except Exception:
            pass

    @staticmethod
    def _depth_array_key(raw) -> tuple[int, tuple[int, ...], int] | None:
        try:
            arr = np.asarray(raw)
            if arr.ndim != 2 or arr.size <= 0:
                return None
            sample = arr
            if arr.size > 4096:
                sample = arr.ravel()[:: max(1, arr.size // 4096)]
            checksum = int(np.asarray(sample, dtype=np.uint8).sum()) & 0xFFFFFFFF
            return (id(raw), tuple(int(v) for v in arr.shape), checksum)
        except Exception:
            return None

    def _depth_texture_for_item(self, item: dict) -> QOpenGLTexture | None:
        raw = item.get("depth_texture") if isinstance(item, dict) else None
        key = self._depth_array_key(raw)
        if key is None:
            return None
        cached = self._depth_texture_cache.get(key)
        if cached is not None:
            if key in self._depth_texture_cache_order:
                self._depth_texture_cache_order.remove(key)
            self._depth_texture_cache_order.append(key)
            return cached
        try:
            arr = np.asarray(raw, dtype=np.uint8)
            if arr.ndim != 2 or arr.size <= 0:
                return None
            h, w = int(arr.shape[0]), int(arr.shape[1])
            rgba = np.ascontiguousarray(np.repeat(arr[:, :, None], 4, axis=2))
            qimg = QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind(6)
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release(6)
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR depth texture upload failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None
        self._depth_texture_cache[key] = tex
        self._depth_texture_cache_order.append(key)
        while len(self._depth_texture_cache_order) > 4:
            old_key = self._depth_texture_cache_order.pop(0)
            old = self._depth_texture_cache.pop(old_key, None)
            if old is not None:
                try:
                    old.destroy()
                except Exception:
                    pass
        return tex

    def _draw_color_packets(self, gl, items: list[dict]) -> bool:
        if not self._ensure_resources() or self._program is None or self._vbo is None:
            return False
        if not items:
            return True
        vertices: list[float] = []
        cache_parts: list[tuple[str, str, int]] = []
        cacheable = True
        for key in ("shadow_vertices", "reflection_vertices", "vertices"):
            for item in items:
                if key == "vertices" and isinstance(item, dict) and int(item.get("pbr_triangle_count", 0) or 0) > 0:
                    continue
                raw = item.get(key) if isinstance(item, dict) else None
                if isinstance(raw, (list, tuple)):
                    token = self._packet_cache_token(item)
                    if token:
                        cache_parts.append((token, key, len(raw)))
                    else:
                        cacheable = False
                    vertices.extend(float(v) for v in raw)
        if len(vertices) < 18:
            return True
        usable = (len(vertices) // 6) * 6
        if usable < 18:
            return True
        n_verts = int(usable // 6)
        if n_verts <= 0:
            return True

        gl.glDisable(_GL_DEPTH_TEST)
        gl.glDisable(_GL_CULL_FACE)
        if hasattr(gl, "glDepthMask"):
            gl.glDepthMask(False)
        if hasattr(gl, "glColorMask"):
            gl.glColorMask(True, True, True, True)
        gl.glEnable(_GL_BLEND)
        gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        self._program.bind()
        cache_key = (
            (
                "ar_pbr_color_packets",
                tuple(cache_parts),
                int(usable),
            )
            if cacheable and cache_parts
            else None
        )
        bound_vbo = self._bind_packet_vbo(vertices[:usable], self._vbo, cache_key)
        if bound_vbo is None:
            self._program.release()
            return False
        stride_bytes = 6 * 4
        self._program.enableAttributeArray(0)
        self._program.enableAttributeArray(1)
        self._program.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride_bytes)
        self._program.setAttributeBuffer(1, _GL_FLOAT, 8, 4, stride_bytes)
        gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
        self._program.disableAttributeArray(0)
        self._program.disableAttributeArray(1)
        bound_vbo.release()
        self._program.release()
        return True

    def _set_pbr_uniform(self, name: str, value) -> None:
        if self._pbr_program is None:
            return
        loc = self._pbr_program.uniformLocation(str(name))
        if int(loc) >= 0:
            self._pbr_program.setUniformValue(int(loc), value)

    def _set_pbr_uniform1i_gl(self, gl, name: str, value: int) -> None:
        if self._pbr_program is None:
            return
        try:
            loc = int(self._pbr_program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1i"):
                gl.glUniform1i(loc, int(value))
        except Exception:
            pass

    def _set_pbr_uniform1f_gl(self, gl, name: str, value: float) -> None:
        if self._pbr_program is None:
            return
        try:
            loc = int(self._pbr_program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1f"):
                gl.glUniform1f(loc, float(value))
        except Exception:
            pass

    def _set_pbr_uniform2f_gl(self, gl, name: str, x: float, y: float) -> None:
        if self._pbr_program is None:
            return
        try:
            loc = int(self._pbr_program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform2f"):
                gl.glUniform2f(loc, float(x), float(y))
        except Exception:
            pass

    def _set_pbr_uniform3f_gl(self, gl, name: str, x: float, y: float, z: float) -> None:
        if self._pbr_program is None:
            return
        try:
            loc = int(self._pbr_program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform3f"):
                gl.glUniform3f(loc, float(x), float(y), float(z))
        except Exception:
            pass

    def _set_program_uniform(self, program: QOpenGLShaderProgram, name: str, value) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0:
                program.setUniformValue(loc, value)
        except Exception:
            pass

    def _set_program_uniform1i_gl(self, gl, program: QOpenGLShaderProgram, name: str, value: int) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1i"):
                gl.glUniform1i(loc, int(value))
            elif loc >= 0:
                program.setUniformValue(loc, int(value))
        except Exception:
            pass

    def _set_program_uniform1f_gl(self, gl, program: QOpenGLShaderProgram, name: str, value: float) -> None:
        try:
            loc = int(program.uniformLocation(str(name)))
            if loc >= 0 and hasattr(gl, "glUniform1f"):
                gl.glUniform1f(loc, float(value))
            elif loc >= 0:
                program.setUniformValue(loc, float(value))
        except Exception:
            pass

    @staticmethod
    def _pbr_stride_for_raw(raw) -> int:
        try:
            count = len(raw)
        except Exception:
            return _AR_PBR_LEGACY_TEXTURE_VERTEX_STRIDE_FLOATS
        if (
            count >= _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS * 3
            and count % _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS == 0
        ):
            return _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS
        return _AR_PBR_LEGACY_TEXTURE_VERTEX_STRIDE_FLOATS

    @staticmethod
    def _pbr_maps_key(maps: dict) -> tuple[tuple[str, str], ...]:
        if not isinstance(maps, dict):
            return ()
        return tuple(sorted((str(key), str(value)) for key, value in maps.items()))

    @classmethod
    def _pbr_row_batches(cls, rows: list, *, include_object_depth: bool = False) -> list[dict]:
        batches: dict[tuple, dict] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            maps = row.get("maps") if isinstance(row.get("maps"), dict) else {}
            path = str(maps.get("base") or row.get("texture") or "")
            raw = row.get("vertices")
            if not isinstance(raw, (list, tuple)):
                continue
            stride_floats = cls._pbr_stride_for_raw(raw)
            usable = (len(raw) // stride_floats) * stride_floats
            if usable < stride_floats * 3:
                continue
            try:
                object_depth = max(0.0, min(1.0, float(row.get("object_depth", 1.0))))
            except Exception:
                object_depth = 1.0
            depth_key = round(object_depth, 3) if include_object_depth else 1.0
            key = (path, stride_floats, cls._pbr_maps_key(maps), depth_key)
            batch = batches.get(key)
            if batch is None:
                batch = {
                    "path": path,
                    "maps": dict(maps),
                    "stride_floats": stride_floats,
                    "vertices": [],
                    "object_depth": object_depth,
                    "batch_key": key,
                }
                batches[key] = batch
            batch["vertices"].extend(float(value) for value in raw[:usable])
        return list(batches.values())

    @classmethod
    def _pbr_world_positions_for_item(cls, item: dict) -> list[tuple[float, float, float]]:
        rows = item.get("pbr_triangles") if isinstance(item, dict) else None
        if not isinstance(rows, list):
            return []
        points: list[tuple[float, float, float]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw = row.get("vertices")
            if not isinstance(raw, (list, tuple)):
                continue
            stride = cls._pbr_stride_for_raw(raw)
            if stride < _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS:
                continue
            usable = (len(raw) // stride) * stride
            for offset in range(0, usable, stride):
                try:
                    points.append((
                        float(raw[offset + 20]),
                        float(raw[offset + 21]),
                        float(raw[offset + 22]),
                    ))
                except Exception:
                    continue
        return points

    @staticmethod
    def _lighting_value(lighting: dict, key: str, default: float, lo: float, hi: float) -> float:
        try:
            value = float(lighting.get(key, default))
        except Exception:
            value = float(default)
        return max(float(lo), min(float(hi), value))

    def _pbr_shadow_params(self, item: dict) -> dict[str, object]:
        lighting = item.get("pbr_lighting") if isinstance(item.get("pbr_lighting"), dict) else {}
        shadow_settings = normalize_shadow_settings(lighting)
        strength = self._lighting_value(lighting, "shadow_strength", 0.45, 0.0, 1.0)
        self_strength = self._lighting_value(lighting, "self_shadow_strength", 0.45, 0.0, 1.0)
        points = self._pbr_world_positions_for_item(item)
        spot_outer = float(shadow_settings["spot_outer_angle"])
        params: dict[str, object] = {
            "enabled": bool(points) and (strength > 0.001 or self_strength > 0.001),
            "texture_id": 0,
            "size": int(shadow_settings["map_size"]),
            "center": QVector3D(0.0, 0.0, 0.0),
            "radius": 1.0,
            "light_dir": self._lighting_for_item(item)["light"],
            "strength": strength,
            "self_strength": self_strength,
            "filter": str(shadow_settings["filter"]),
            "filter_mode": 1 if str(shadow_settings["filter"]) == "pcss" else 0,
            "light_type": str(shadow_settings["light_type"]),
            "light_type_mode": 1 if str(shadow_settings["light_type"]) == "spot" else 0,
            "pcf_radius": float(shadow_settings["pcf_radius_texels"]),
            "pcss_blocker_radius": float(shadow_settings["pcss_blocker_radius_texels"]),
            "bias": float(shadow_settings["bias"]),
            "normal_bias": float(shadow_settings["normal_bias"]),
            "spot_inner_angle": float(shadow_settings["spot_inner_angle"]),
            "spot_outer_angle": spot_outer,
            "spot_tan_outer": math.tan(math.radians(max(1.0, min(89.0, spot_outer)))),
            "spot_cos_inner": math.cos(math.radians(max(0.0, min(89.0, float(shadow_settings["spot_inner_angle"]))))),
            "spot_cos_outer": math.cos(math.radians(max(1.0, min(89.0, spot_outer)))),
        }
        if not params["enabled"]:
            return params
        try:
            arr = np.asarray(points, dtype=np.float32)
            arr = arr[np.isfinite(arr).all(axis=1)]
            if arr.shape[0] < 3:
                params["enabled"] = False
                return params
            mins = arr.min(axis=0)
            maxs = arr.max(axis=0)
            center_np = (mins + maxs) * 0.5
            light_dir = params["light_dir"]
            light = np.asarray([-light_dir.x(), -light_dir.y(), -light_dir.z()], dtype=np.float32)
            light_len = float(np.linalg.norm(light))
            if light_len <= 0.0001:
                light = np.asarray((0.35, 0.65, 0.72), dtype=np.float32)
            else:
                light = light / light_len
            up = np.asarray((1.0, 0.0, 0.0), dtype=np.float32) if abs(float(light[1])) > 0.92 else np.asarray((0.0, 1.0, 0.0), dtype=np.float32)
            sx = np.cross(up, light)
            sx = sx / max(0.0001, float(np.linalg.norm(sx)))
            sy = np.cross(light, sx)
            local = arr - center_np
            radius = max(
                float(np.max(np.abs(local @ sx))),
                float(np.max(np.abs(local @ sy))),
                float(np.max(np.abs(local @ light))),
                0.001,
            ) * 1.10
            if params["light_type"] == "spot":
                radius *= max(1.15, 1.0 + float(params["spot_tan_outer"]) * 0.25)
            params["center"] = QVector3D(float(center_np[0]), float(center_np[1]), float(center_np[2]))
            params["radius"] = max(0.05, radius)
        except Exception:
            params["enabled"] = False
        return params

    def _bind_raw_texture(self, gl, unit: int, texture_id: int) -> bool:
        try:
            if not hasattr(gl, "glActiveTexture") or not hasattr(gl, "glBindTexture"):
                return False
            gl.glActiveTexture(_GL_TEXTURE0 + int(unit))
            gl.glBindTexture(_GL_TEXTURE_2D, int(texture_id))
            if hasattr(gl, "glTexParameteri"):
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MIN_FILTER, _GL_LINEAR)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_MAG_FILTER, _GL_LINEAR)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_S, _GL_CLAMP_TO_EDGE)
                gl.glTexParameteri(_GL_TEXTURE_2D, _GL_TEXTURE_WRAP_T, _GL_CLAMP_TO_EDGE)
            return True
        except Exception:
            return False

    def _unbind_raw_texture(self, gl, unit: int) -> None:
        try:
            if hasattr(gl, "glActiveTexture") and hasattr(gl, "glBindTexture"):
                gl.glActiveTexture(_GL_TEXTURE0 + int(unit))
                gl.glBindTexture(_GL_TEXTURE_2D, 0)
                gl.glActiveTexture(_GL_TEXTURE0)
        except Exception:
            pass

    @staticmethod
    def _lighting_for_item(item: dict) -> dict:
        lighting = item.get("pbr_lighting") if isinstance(item.get("pbr_lighting"), dict) else {}
        raw_dir = lighting.get("light_dir") if isinstance(lighting, dict) else None
        try:
            light = QVector3D(float(raw_dir[0]), float(raw_dir[1]), float(raw_dir[2]))
        except Exception:
            light = QVector3D(-0.35, -0.65, -0.72)
        if light.length() <= 0.001:
            light = QVector3D(-0.35, -0.65, -0.72)
        light.normalize()
        try:
            direct = max(0.0, min(4.0, float(lighting.get("direct_strength", 0.85))))
        except Exception:
            direct = 0.85
        try:
            ibl = max(0.0, min(8.0, float(lighting.get("ibl_exposure", 1.0))))
        except Exception:
            ibl = 1.0
        try:
            rotation = max(-1.0, min(1.0, float(lighting.get("ibl_rotation", 0.0))))
        except Exception:
            rotation = 0.0
        color_management = normalize_color_management_settings(lighting)
        hybrid_rendering = normalize_hybrid_render_settings(lighting)
        ambient_occlusion_rendering = normalize_ambient_occlusion_settings(lighting)
        transmission_rendering = normalize_transmission_settings(lighting)
        clearcoat_rendering = normalize_clearcoat_settings(lighting)
        parallax_rendering = normalize_parallax_settings(lighting)
        bevel_rendering = normalize_bevel_settings(lighting)
        material_layering = normalize_material_layering_settings(lighting)
        surface_rendering = normalize_surface_settings(lighting)
        subsurface_rendering = normalize_subsurface_settings(lighting)
        hair_groom_rendering = normalize_hair_groom_settings(lighting)
        cloth_sheen_rendering = normalize_cloth_sheen_settings(lighting)
        glint_sparkle_rendering = normalize_glint_sparkle_settings(lighting)
        depth_of_field_rendering = normalize_depth_of_field_settings(lighting)
        post_effects_rendering = normalize_post_effects_settings(lighting)
        triplanar_rendering = normalize_triplanar_settings(lighting)
        return {
            "light": light,
            "direct": direct,
            "ibl": ibl,
            "rotation": rotation,
            "hdri_path": str(lighting.get("hdri_path") or ""),
            "color_management": color_management,
            "hybrid_rendering": hybrid_rendering,
            "ambient_occlusion_rendering": ambient_occlusion_rendering,
            "transmission_rendering": transmission_rendering,
            "clearcoat_rendering": clearcoat_rendering,
            "parallax_rendering": parallax_rendering,
            "bevel_rendering": bevel_rendering,
            "material_layering": material_layering,
            "surface_rendering": surface_rendering,
            "subsurface_rendering": subsurface_rendering,
            "hair_groom_rendering": hair_groom_rendering,
            "cloth_sheen_rendering": cloth_sheen_rendering,
            "glint_sparkle_rendering": glint_sparkle_rendering,
            "depth_of_field_rendering": depth_of_field_rendering,
            "post_effects_rendering": post_effects_rendering,
            "triplanar_rendering": triplanar_rendering,
        }

    @staticmethod
    def _channel_selector(maps: dict, key: str, default: int = 0) -> QVector4D:
        raw = str(maps.get(f"{key}_channel") or "").strip().lower()
        aliases = {"r": 0, "red": 0, "g": 1, "green": 1, "b": 2, "blue": 2, "a": 3, "alpha": 3}
        try:
            idx = aliases[raw] if raw in aliases else int(raw)
        except Exception:
            idx = int(default)
        idx = max(0, min(3, int(idx)))
        return QVector4D(
            1.0 if idx == 0 else 0.0,
            1.0 if idx == 1 else 0.0,
            1.0 if idx == 2 else 0.0,
            1.0 if idx == 3 else 0.0,
        )

    @staticmethod
    def _map_float(maps: dict, key: str, default: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
        try:
            value = float(maps.get(key, default))
        except Exception:
            value = float(default)
        return max(float(lo), min(float(hi), float(value)))

    @staticmethod
    def _map_bool(maps: dict, key: str, default: bool = False) -> bool:
        if not isinstance(maps, dict) or key not in maps:
            return bool(default)
        value = maps.get(key)
        if isinstance(value, bool):
            return value
        text = str(value).strip().casefold()
        if text in {"1", "true", "yes", "on", "enabled"}:
            return True
        if text in {"0", "false", "no", "off", "disabled", "none"}:
            return False
        return bool(default)

    @staticmethod
    def _map_vec3(maps: dict, key: str, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> QVector3D:
        raw = maps.get(key)
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
        return QVector3D(float(values[0]), float(values[1]), float(values[2]))

    def _render_pbr_shadow_map(self, gl, item: dict, frame_w: int, frame_h: int) -> dict[str, object]:
        params = self._pbr_shadow_params(item)
        if (
            not bool(params.get("enabled"))
            or not self._ensure_pbr_shadow_resources()
            or self._pbr_shadow_program is None
            or self._pbr_shadow_vbo is None
        ):
            return params
        size = int(params.get("size", 1024) or 1024)
        if not self._ensure_pbr_shadow_fbo(size) or self._pbr_shadow_fbo is None:
            return params
        if not self._pbr_shadow_fbo.bind():
            return params
        program = self._pbr_shadow_program
        vbo = self._pbr_shadow_vbo
        try:
            gl.glViewport(0, 0, size, size)
            gl.glDisable(_GL_BLEND)
            gl.glDisable(_GL_CULL_FACE)
            gl.glEnable(_GL_DEPTH_TEST)
            if hasattr(gl, "glDepthFunc"):
                gl.glDepthFunc(_GL_LEQUAL)
            if hasattr(gl, "glDepthMask"):
                gl.glDepthMask(True)
            gl.glClearColor(1.0, 1.0, 1.0, 1.0)
            gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
            program.bind()
            self._set_program_uniform(program, "u_shadow_center", params["center"])
            self._set_program_uniform(program, "u_shadow_light_dir", params["light_dir"])
            self._set_program_uniform1f_gl(gl, program, "u_shadow_radius", float(params.get("radius", 1.0)))
            self._set_program_uniform1i_gl(gl, program, "u_shadow_light_type", int(params.get("light_type_mode", 0) or 0))
            self._set_program_uniform1f_gl(gl, program, "u_shadow_spot_tan_outer", float(params.get("spot_tan_outer", 1.0) or 1.0))
            self._set_program_uniform1i_gl(gl, program, "u_base_tex", 0)
            self._set_program_uniform1f_gl(gl, program, "u_alpha_cutoff", 0.002)
            for batch in self._pbr_batches_for_item(item):
                maps = batch.get("maps") if isinstance(batch.get("maps"), dict) else {}
                path = str(batch.get("path") or "")
                tex = self._texture_for_path(path, *self._texture_wrap_for_map(maps, "base"))
                has_base_tex = tex is not None
                if tex is None:
                    tex = self._white_texture()
                if tex is None:
                    continue
                raw = batch.get("vertices")
                if not isinstance(raw, list):
                    continue
                stride_floats = int(batch.get("stride_floats", _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS) or _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS)
                if stride_floats < _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS:
                    continue
                n_verts = int(len(raw) // stride_floats)
                if n_verts <= 0:
                    continue
                stride_bytes = stride_floats * 4
                cache_key = self._vbo_cache_key(
                    "pbr_shadow",
                    item,
                    batch.get("batch_key"),
                    len(raw),
                    stride_floats,
                )
                self._set_program_uniform1i_gl(gl, program, "u_has_base_tex", 1 if has_base_tex else 0)
                self._set_program_uniform1i_gl(
                    gl,
                    program,
                    "u_flip_uv_v",
                    1 if self._map_bool(maps, "uv_v_flip", False) else 0,
                )
                self._set_program_uniform1f_gl(
                    gl,
                    program,
                    "u_alpha_cutoff",
                    self._map_float(maps, "alpha_cutoff", 0.002, lo=0.0, hi=1.0),
                )
                tex.bind(0)
                bound_vbo = self._bind_packet_vbo(raw, vbo, cache_key)
                if bound_vbo is None:
                    tex.release(0)
                    continue
                program.enableAttributeArray(0)
                program.enableAttributeArray(1)
                program.setAttributeBuffer(0, _GL_FLOAT, 20 * 4, 3, stride_bytes)
                program.setAttributeBuffer(1, _GL_FLOAT, 2 * 4, 2, stride_bytes)
                gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
                program.disableAttributeArray(0)
                program.disableAttributeArray(1)
                bound_vbo.release()
                tex.release(0)
            program.release()
            debug_path = os.environ.get("GIFCAM_AR_PBR_SHADOW_MAP_PNG", "").strip()
            if debug_path:
                try:
                    image = self._pbr_shadow_fbo.toImage()
                    image.save(debug_path, "PNG")
                except Exception as exc:
                    print(
                        f"[OpenGLPreviewWidget] AR/PBR shadow map debug save failed: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
            params["texture_id"] = int(self._pbr_shadow_fbo.texture())
        finally:
            self._pbr_shadow_fbo.release()
            gl.glViewport(0, 0, max(1, int(frame_w)), max(1, int(frame_h)))
            gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        return params

    def _draw_pbr_packets(self, gl, items: list[dict]) -> bool:
        if not self._ensure_pbr_resources() or self._pbr_program is None or self._pbr_vbo is None:
            return False
        drew_any = False
        self._pbr_program.bind()
        self._set_pbr_uniform("u_base_tex", 0)
        self._set_pbr_uniform("u_roughness_tex", 1)
        self._set_pbr_uniform("u_metallic_tex", 2)
        self._set_pbr_uniform("u_specular_tex", 3)
        self._set_pbr_uniform("u_normal_tex", 4)
        self._set_pbr_uniform("u_hdri_tex", 5)
        self._set_pbr_uniform("u_depth_tex", 6)
        self._set_pbr_uniform("u_occlusion_tex", 7)
        self._set_pbr_uniform("u_shadow_tex", 8)
        self._set_pbr_uniform("u_irradiance_tex", 9)
        self._set_pbr_uniform("u_prefilter_tex", 10)
        self._set_pbr_uniform("u_brdf_lut_tex", 11)
        self._set_pbr_uniform("u_emissive_tex", 12)
        self._set_pbr_uniform("u_opacity_tex", 13)
        self._set_pbr_uniform("u_height_tex", 14)
        self._set_pbr_uniform1i_gl(gl, "u_base_tex", 0)
        self._set_pbr_uniform1i_gl(gl, "u_roughness_tex", 1)
        self._set_pbr_uniform1i_gl(gl, "u_metallic_tex", 2)
        self._set_pbr_uniform1i_gl(gl, "u_specular_tex", 3)
        self._set_pbr_uniform1i_gl(gl, "u_normal_tex", 4)
        self._set_pbr_uniform1i_gl(gl, "u_hdri_tex", 5)
        self._set_pbr_uniform1i_gl(gl, "u_depth_tex", 6)
        self._set_pbr_uniform1i_gl(gl, "u_occlusion_tex", 7)
        self._set_pbr_uniform1i_gl(gl, "u_shadow_tex", 8)
        self._set_pbr_uniform1i_gl(gl, "u_irradiance_tex", 9)
        self._set_pbr_uniform1i_gl(gl, "u_prefilter_tex", 10)
        self._set_pbr_uniform1i_gl(gl, "u_brdf_lut_tex", 11)
        self._set_pbr_uniform1i_gl(gl, "u_emissive_tex", 12)
        self._set_pbr_uniform1i_gl(gl, "u_opacity_tex", 13)
        self._set_pbr_uniform1i_gl(gl, "u_height_tex", 14)
        self._set_pbr_uniform1i_gl(gl, "u_flip_uv_v", 0)
        try:
            if hasattr(self._parent, "_surface_size_px"):
                surface_w, surface_h = self._parent._surface_size_px()
                viewport_w = max(1.0, float(surface_w))
                viewport_h = max(1.0, float(surface_h))
            else:
                dpr = float(self._parent.devicePixelRatioF()) if hasattr(self._parent, "devicePixelRatioF") else 1.0
                viewport_w = max(1.0, float(self._parent.width()) * max(0.01, dpr))
                viewport_h = max(1.0, float(self._parent.height()) * max(0.01, dpr))
        except Exception:
            viewport_w = 1.0
            viewport_h = 1.0
        self._set_pbr_uniform("u_viewport_size", QVector2D(viewport_w, viewport_h))
        self._set_pbr_uniform2f_gl(gl, "u_viewport_size", viewport_w, viewport_h)
        for item in items:
            if not isinstance(item, dict):
                continue
            self._pbr_program.release()
            shadow = self._render_pbr_shadow_map(gl, item, int(viewport_w), int(viewport_h))
            gl.glClear(_GL_DEPTH_BUFFER_BIT)
            gl.glEnable(_GL_DEPTH_TEST)
            if hasattr(gl, "glDepthFunc"):
                gl.glDepthFunc(_GL_LEQUAL)
            if hasattr(gl, "glDepthMask"):
                gl.glDepthMask(True)
            gl.glEnable(_GL_BLEND)
            gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
            self._pbr_program.bind()
            lighting = self._lighting_for_item(item)
            self._set_pbr_uniform("u_light_dir", lighting["light"])
            self._set_pbr_uniform("u_direct_strength", float(lighting["direct"]))
            self._set_pbr_uniform("u_ibl_exposure", float(lighting["ibl"]))
            self._set_pbr_uniform("u_ibl_rotation", float(lighting["rotation"]))
            color_management = lighting.get("color_management") if isinstance(lighting.get("color_management"), dict) else {}
            tone_wb = list(color_management.get("tone_white_balance_rgb") or [1.0, 1.0, 1.0])
            self._set_pbr_uniform("u_tone_mapping_mode", int(color_management.get("tone_mapping_mode", 0) or 0))
            self._set_pbr_uniform("u_tone_exposure", float(color_management.get("tone_exposure", 0.0) or 0.0))
            self._set_pbr_uniform("u_tone_white_balance", QVector3D(float(tone_wb[0]), float(tone_wb[1]), float(tone_wb[2])))
            self._set_pbr_uniform("u_tone_gamma", float(color_management.get("tone_gamma", 2.2) or 2.2))
            hybrid_rendering = lighting.get("hybrid_rendering") if isinstance(lighting.get("hybrid_rendering"), dict) else {}
            self._set_pbr_uniform("u_hybrid_sample_count", int(hybrid_rendering.get("sample_count", 1) or 1))
            self._set_pbr_uniform("u_diffuse_gi_strength", float(hybrid_rendering.get("diffuse_gi_strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_specular_gi_strength", float(hybrid_rendering.get("specular_gi_strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_denoise_strength", float(hybrid_rendering.get("denoise_strength", 0.0) or 0.0))
            transmission_rendering = lighting.get("transmission_rendering") if isinstance(lighting.get("transmission_rendering"), dict) else {}
            absorption_color = list(transmission_rendering.get("absorption_color") or [1.0, 1.0, 1.0])
            self._set_pbr_uniform("u_transmission", float(transmission_rendering.get("transmission", 0.0) or 0.0))
            self._set_pbr_uniform("u_refraction_strength", float(transmission_rendering.get("refraction_strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_ior", float(transmission_rendering.get("ior", 1.45) or 1.45))
            self._set_pbr_uniform("u_thickness", float(transmission_rendering.get("thickness", 0.0) or 0.0))
            self._set_pbr_uniform("u_absorption_color", QVector3D(float(absorption_color[0]), float(absorption_color[1]), float(absorption_color[2])))
            clearcoat_rendering = lighting.get("clearcoat_rendering") if isinstance(lighting.get("clearcoat_rendering"), dict) else {}
            clearcoat_tint = list(clearcoat_rendering.get("tint") or [1.0, 1.0, 1.0])
            self._set_pbr_uniform("u_clearcoat_strength", float(clearcoat_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_clearcoat_roughness", float(clearcoat_rendering.get("roughness", 0.12) or 0.12))
            self._set_pbr_uniform("u_clearcoat_ior", float(clearcoat_rendering.get("ior", 1.5) or 1.5))
            self._set_pbr_uniform("u_clearcoat_tint", QVector3D(float(clearcoat_tint[0]), float(clearcoat_tint[1]), float(clearcoat_tint[2])))
            parallax_rendering = lighting.get("parallax_rendering") if isinstance(lighting.get("parallax_rendering"), dict) else {}
            self._set_pbr_uniform("u_parallax_strength", float(parallax_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_parallax_depth", float(parallax_rendering.get("depth", 0.0) or 0.0))
            self._set_pbr_uniform("u_parallax_center", float(parallax_rendering.get("center", 0.5) or 0.5))
            bevel_rendering = lighting.get("bevel_rendering") if isinstance(lighting.get("bevel_rendering"), dict) else {}
            self._set_pbr_uniform("u_bevel_strength", float(bevel_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_bevel_radius", float(bevel_rendering.get("radius", 0.0) or 0.0))
            self._set_pbr_uniform("u_bevel_edge_width", float(bevel_rendering.get("edge_width", 0.075) or 0.075))
            material_layering = lighting.get("material_layering") if isinstance(lighting.get("material_layering"), dict) else {}
            material_layer_color = list(material_layering.get("color") or [1.0, 1.0, 1.0])
            self._set_pbr_uniform("u_material_layer_blend", float(material_layering.get("blend", 0.0) or 0.0))
            self._set_pbr_uniform("u_material_layer_color", QVector3D(float(material_layer_color[0]), float(material_layer_color[1]), float(material_layer_color[2])))
            self._set_pbr_uniform("u_material_layer_roughness", float(material_layering.get("roughness", 0.5) or 0.5))
            self._set_pbr_uniform("u_material_layer_metallic", float(material_layering.get("metallic", 0.0) or 0.0))
            self._set_pbr_uniform("u_material_layer_alpha", float(material_layering.get("alpha", 1.0) or 1.0))
            self._set_pbr_uniform("u_material_layer_emissive_strength", float(material_layering.get("emissive_strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_material_layer_mask_strength", float(material_layering.get("mask_strength", 0.0) or 0.0))
            surface_rendering = lighting.get("surface_rendering") if isinstance(lighting.get("surface_rendering"), dict) else {}
            self._set_pbr_uniform("u_surface_override_strength", float(surface_rendering.get("override_strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_surface_roughness", float(surface_rendering.get("roughness", 0.45) or 0.45))
            self._set_pbr_uniform("u_surface_metallic", float(surface_rendering.get("metallic", 0.0) or 0.0))
            self._set_pbr_uniform("u_surface_reflectance", float(surface_rendering.get("reflectance", 0.5) or 0.5))
            subsurface_rendering = lighting.get("subsurface_rendering") if isinstance(lighting.get("subsurface_rendering"), dict) else {}
            subsurface_color = list(subsurface_rendering.get("color") or [1.0, 0.62, 0.42])
            self._set_pbr_uniform("u_subsurface_strength", float(subsurface_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_subsurface_color", QVector3D(float(subsurface_color[0]), float(subsurface_color[1]), float(subsurface_color[2])))
            self._set_pbr_uniform("u_subsurface_radius", float(subsurface_rendering.get("radius", 0.38) or 0.38))
            self._set_pbr_uniform("u_subsurface_power", float(subsurface_rendering.get("power", 2.0) or 2.0))
            self._set_pbr_uniform("u_subsurface_wrap", float(subsurface_rendering.get("wrap", 0.45) or 0.45))
            self._set_pbr_uniform("u_subsurface_thickness", float(subsurface_rendering.get("thickness", 0.12) or 0.12))
            hair_groom_rendering = lighting.get("hair_groom_rendering") if isinstance(lighting.get("hair_groom_rendering"), dict) else {}
            hair_tint = list(hair_groom_rendering.get("tint") or [1.0, 0.88, 0.62])
            def _hair_uniform_float(key: str, default: float) -> float:
                raw = hair_groom_rendering.get(key)
                try:
                    return float(default if raw is None else raw)
                except Exception:
                    return float(default)

            self._set_pbr_uniform("u_hair_groom_strength", _hair_uniform_float("strength", 0.0))
            self._set_pbr_uniform("u_hair_groom_tint", QVector3D(float(hair_tint[0]), float(hair_tint[1]), float(hair_tint[2])))
            self._set_pbr_uniform("u_hair_primary_shift", _hair_uniform_float("primary_shift", 0.08))
            self._set_pbr_uniform("u_hair_secondary_shift", _hair_uniform_float("secondary_shift", -0.18))
            self._set_pbr_uniform("u_hair_primary_roughness", _hair_uniform_float("primary_roughness", 0.24))
            self._set_pbr_uniform("u_hair_secondary_roughness", _hair_uniform_float("secondary_roughness", 0.42))
            self._set_pbr_uniform("u_hair_secondary_strength", _hair_uniform_float("secondary_strength", 0.48))
            self._set_pbr_uniform("u_hair_anisotropy", _hair_uniform_float("anisotropy", 0.78))
            self._set_pbr_uniform("u_hair_rim_strength", _hair_uniform_float("rim_strength", 0.18))
            cloth_sheen_rendering = lighting.get("cloth_sheen_rendering") if isinstance(lighting.get("cloth_sheen_rendering"), dict) else {}
            cloth_color = list(cloth_sheen_rendering.get("color") or [0.92, 0.96, 1.0])
            cloth_edge_tint = list(cloth_sheen_rendering.get("edge_tint") or [0.72, 0.82, 1.0])

            def _cloth_uniform_float(key: str, default: float) -> float:
                raw = cloth_sheen_rendering.get(key)
                try:
                    return float(default if raw is None else raw)
                except Exception:
                    return float(default)

            self._set_pbr_uniform("u_cloth_sheen_strength", _cloth_uniform_float("strength", 0.0))
            self._set_pbr_uniform("u_cloth_sheen_color", QVector3D(float(cloth_color[0]), float(cloth_color[1]), float(cloth_color[2])))
            self._set_pbr_uniform("u_cloth_sheen_roughness", _cloth_uniform_float("roughness", 0.58))
            self._set_pbr_uniform("u_cloth_sheen_edge_tint", QVector3D(float(cloth_edge_tint[0]), float(cloth_edge_tint[1]), float(cloth_edge_tint[2])))
            self._set_pbr_uniform("u_cloth_sheen_fiber_strength", _cloth_uniform_float("fiber_strength", 0.24))
            self._set_pbr_uniform("u_cloth_sheen_wrap", _cloth_uniform_float("wrap", 0.34))
            self._set_pbr_uniform("u_cloth_sheen_retroreflection", _cloth_uniform_float("retroreflection", 0.28))
            glint_sparkle_rendering = lighting.get("glint_sparkle_rendering") if isinstance(lighting.get("glint_sparkle_rendering"), dict) else {}
            glint_color = list(glint_sparkle_rendering.get("color") or [1.0, 0.96, 0.82])

            def _glint_uniform_float(key: str, default: float) -> float:
                raw = glint_sparkle_rendering.get(key)
                try:
                    return float(default if raw is None else raw)
                except Exception:
                    return float(default)

            self._set_pbr_uniform("u_glint_strength", _glint_uniform_float("strength", 0.0))
            self._set_pbr_uniform("u_glint_color", QVector3D(float(glint_color[0]), float(glint_color[1]), float(glint_color[2])))
            self._set_pbr_uniform("u_glint_density", _glint_uniform_float("density", 0.24))
            self._set_pbr_uniform("u_glint_scale", _glint_uniform_float("scale", 64.0))
            self._set_pbr_uniform("u_glint_threshold", _glint_uniform_float("threshold", 0.62))
            self._set_pbr_uniform("u_glint_sharpness", _glint_uniform_float("sharpness", 18.0))
            self._set_pbr_uniform("u_glint_roughness_jitter", _glint_uniform_float("roughness_jitter", 0.55))
            triplanar_rendering = lighting.get("triplanar_rendering") if isinstance(lighting.get("triplanar_rendering"), dict) else {}
            triplanar_offset = list(triplanar_rendering.get("offset") or [0.0, 0.0, 0.0])
            self._set_pbr_uniform("u_triplanar_strength", float(triplanar_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform("u_triplanar_scale", float(triplanar_rendering.get("scale", 1.0) or 1.0))
            self._set_pbr_uniform("u_triplanar_blend_sharpness", float(triplanar_rendering.get("blend_sharpness", 4.0) or 4.0))
            self._set_pbr_uniform("u_triplanar_offset", QVector3D(float(triplanar_offset[0]), float(triplanar_offset[1]), float(triplanar_offset[2])))
            ambient_occlusion = normalize_packet_ambient_occlusion_settings(item, lighting)
            ao_enabled = bool(ambient_occlusion.get("enabled"))
            ao_strength = float(ambient_occlusion.get("strength", 0.0) or 0.0) if ao_enabled else 0.0
            ao_radius = float(ambient_occlusion.get("radius", 3.0) or 3.0)
            ao_distance = float(ambient_occlusion.get("distance", 0.45) or 0.45)
            ao_color = list(ambient_occlusion.get("color") or [0.0, 0.0, 0.0])
            ao_color = (ao_color + [0.0, 0.0, 0.0])[:3]
            ao_ambient = 1 if bool(ambient_occlusion.get("ambient", True)) else 0
            ao_diffuse = 1 if bool(ambient_occlusion.get("diffuse", True)) else 0
            ao_specular = 1 if bool(ambient_occlusion.get("specular", False)) else 0
            self._set_pbr_uniform("u_screen_ao_strength", ao_strength)
            self._set_pbr_uniform("u_screen_ao_radius", ao_radius)
            self._set_pbr_uniform("u_screen_ao_distance", ao_distance)
            self._set_pbr_uniform(
                "u_screen_ao_color",
                QVector3D(float(ao_color[0]), float(ao_color[1]), float(ao_color[2])),
            )
            self._set_pbr_uniform("u_screen_ao_ambient", ao_ambient)
            self._set_pbr_uniform("u_screen_ao_diffuse", ao_diffuse)
            self._set_pbr_uniform("u_screen_ao_specular", ao_specular)
            shadow_bound = False
            try:
                shadow_tex_id = int(shadow.get("texture_id", 0) if isinstance(shadow, dict) else 0)
            except Exception:
                shadow_tex_id = 0
            if shadow_tex_id > 0:
                shadow_bound = self._bind_raw_texture(gl, 8, shadow_tex_id)
            self._set_pbr_uniform("u_has_shadow_map", 1 if shadow_bound else 0)
            self._set_pbr_uniform1i_gl(gl, "u_has_shadow_map", 1 if shadow_bound else 0)
            self._set_pbr_uniform("u_shadow_center", shadow.get("center", QVector3D(0.0, 0.0, 0.0)) if isinstance(shadow, dict) else QVector3D(0.0, 0.0, 0.0))
            self._set_pbr_uniform("u_shadow_radius", float(shadow.get("radius", 1.0) if isinstance(shadow, dict) else 1.0))
            self._set_pbr_uniform("u_shadow_map_size", float(shadow.get("size", 1024) if isinstance(shadow, dict) else 1024))
            self._set_pbr_uniform("u_shadow_pcf_radius", float(shadow.get("pcf_radius", 1.35) if isinstance(shadow, dict) else 1.35))
            self._set_pbr_uniform("u_shadow_pcss_blocker_radius", float(shadow.get("pcss_blocker_radius", 2.5) if isinstance(shadow, dict) else 2.5))
            self._set_pbr_uniform("u_shadow_bias", float(shadow.get("bias", 0.002) if isinstance(shadow, dict) else 0.002))
            self._set_pbr_uniform("u_shadow_normal_bias", float(shadow.get("normal_bias", 0.002) if isinstance(shadow, dict) else 0.002))
            self._set_pbr_uniform("u_shadow_strength", float(shadow.get("strength", 0.0) if isinstance(shadow, dict) else 0.0))
            self._set_pbr_uniform("u_self_shadow_strength", float(shadow.get("self_strength", 0.0) if isinstance(shadow, dict) else 0.0))
            self._set_pbr_uniform("u_shadow_filter_mode", int(shadow.get("filter_mode", 0) if isinstance(shadow, dict) else 0))
            self._set_pbr_uniform("u_shadow_light_type", int(shadow.get("light_type_mode", 0) if isinstance(shadow, dict) else 0))
            self._set_pbr_uniform("u_shadow_spot_tan_outer", float(shadow.get("spot_tan_outer", 1.0) if isinstance(shadow, dict) else 1.0))
            self._set_pbr_uniform("u_shadow_spot_cos_inner", float(shadow.get("spot_cos_inner", 0.88) if isinstance(shadow, dict) else 0.88))
            self._set_pbr_uniform("u_shadow_spot_cos_outer", float(shadow.get("spot_cos_outer", 0.70) if isinstance(shadow, dict) else 0.70))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_radius", float(shadow.get("radius", 1.0) if isinstance(shadow, dict) else 1.0))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_map_size", float(shadow.get("size", 1024) if isinstance(shadow, dict) else 1024))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_pcf_radius", float(shadow.get("pcf_radius", 1.35) if isinstance(shadow, dict) else 1.35))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_pcss_blocker_radius", float(shadow.get("pcss_blocker_radius", 2.5) if isinstance(shadow, dict) else 2.5))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_bias", float(shadow.get("bias", 0.002) if isinstance(shadow, dict) else 0.002))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_normal_bias", float(shadow.get("normal_bias", 0.002) if isinstance(shadow, dict) else 0.002))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_strength", float(shadow.get("strength", 0.0) if isinstance(shadow, dict) else 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_self_shadow_strength", float(shadow.get("self_strength", 0.0) if isinstance(shadow, dict) else 0.0))
            self._set_pbr_uniform1i_gl(gl, "u_shadow_filter_mode", int(shadow.get("filter_mode", 0) if isinstance(shadow, dict) else 0))
            self._set_pbr_uniform1i_gl(gl, "u_shadow_light_type", int(shadow.get("light_type_mode", 0) if isinstance(shadow, dict) else 0))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_spot_tan_outer", float(shadow.get("spot_tan_outer", 1.0) if isinstance(shadow, dict) else 1.0))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_spot_cos_inner", float(shadow.get("spot_cos_inner", 0.88) if isinstance(shadow, dict) else 0.88))
            self._set_pbr_uniform1f_gl(gl, "u_shadow_spot_cos_outer", float(shadow.get("spot_cos_outer", 0.70) if isinstance(shadow, dict) else 0.70))
            self._set_pbr_uniform1i_gl(gl, "u_tone_mapping_mode", int(color_management.get("tone_mapping_mode", 0) or 0))
            self._set_pbr_uniform1f_gl(gl, "u_tone_exposure", float(color_management.get("tone_exposure", 0.0) or 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_tone_white_balance", float(tone_wb[0]), float(tone_wb[1]), float(tone_wb[2]))
            self._set_pbr_uniform1f_gl(gl, "u_tone_gamma", float(color_management.get("tone_gamma", 2.2) or 2.2))
            self._set_pbr_uniform1i_gl(gl, "u_hybrid_sample_count", int(hybrid_rendering.get("sample_count", 1) or 1))
            self._set_pbr_uniform1f_gl(gl, "u_diffuse_gi_strength", float(hybrid_rendering.get("diffuse_gi_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_specular_gi_strength", float(hybrid_rendering.get("specular_gi_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_denoise_strength", float(hybrid_rendering.get("denoise_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_transmission", float(transmission_rendering.get("transmission", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_refraction_strength", float(transmission_rendering.get("refraction_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_ior", float(transmission_rendering.get("ior", 1.45) or 1.45))
            self._set_pbr_uniform1f_gl(gl, "u_thickness", float(transmission_rendering.get("thickness", 0.0) or 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_absorption_color", float(absorption_color[0]), float(absorption_color[1]), float(absorption_color[2]))
            self._set_pbr_uniform1f_gl(gl, "u_clearcoat_strength", float(clearcoat_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_clearcoat_roughness", float(clearcoat_rendering.get("roughness", 0.12) or 0.12))
            self._set_pbr_uniform1f_gl(gl, "u_clearcoat_ior", float(clearcoat_rendering.get("ior", 1.5) or 1.5))
            self._set_pbr_uniform3f_gl(gl, "u_clearcoat_tint", float(clearcoat_tint[0]), float(clearcoat_tint[1]), float(clearcoat_tint[2]))
            self._set_pbr_uniform1f_gl(gl, "u_parallax_strength", float(parallax_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_parallax_depth", float(parallax_rendering.get("depth", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_parallax_center", float(parallax_rendering.get("center", 0.5) or 0.5))
            self._set_pbr_uniform1f_gl(gl, "u_bevel_strength", float(bevel_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_bevel_radius", float(bevel_rendering.get("radius", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_bevel_edge_width", float(bevel_rendering.get("edge_width", 0.075) or 0.075))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_blend", float(material_layering.get("blend", 0.0) or 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_material_layer_color", float(material_layer_color[0]), float(material_layer_color[1]), float(material_layer_color[2]))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_roughness", float(material_layering.get("roughness", 0.5) or 0.5))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_metallic", float(material_layering.get("metallic", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_alpha", float(material_layering.get("alpha", 1.0) or 1.0))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_emissive_strength", float(material_layering.get("emissive_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_material_layer_mask_strength", float(material_layering.get("mask_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_surface_override_strength", float(surface_rendering.get("override_strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_surface_roughness", float(surface_rendering.get("roughness", 0.45) or 0.45))
            self._set_pbr_uniform1f_gl(gl, "u_surface_metallic", float(surface_rendering.get("metallic", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_surface_reflectance", float(surface_rendering.get("reflectance", 0.5) or 0.5))
            self._set_pbr_uniform1f_gl(gl, "u_subsurface_strength", float(subsurface_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_subsurface_color", float(subsurface_color[0]), float(subsurface_color[1]), float(subsurface_color[2]))
            self._set_pbr_uniform1f_gl(gl, "u_subsurface_radius", float(subsurface_rendering.get("radius", 0.38) or 0.38))
            self._set_pbr_uniform1f_gl(gl, "u_subsurface_power", float(subsurface_rendering.get("power", 2.0) or 2.0))
            self._set_pbr_uniform1f_gl(gl, "u_subsurface_wrap", float(subsurface_rendering.get("wrap", 0.45) or 0.45))
            self._set_pbr_uniform1f_gl(gl, "u_subsurface_thickness", float(subsurface_rendering.get("thickness", 0.12) or 0.12))
            self._set_pbr_uniform1f_gl(gl, "u_hair_groom_strength", _hair_uniform_float("strength", 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_hair_groom_tint", float(hair_tint[0]), float(hair_tint[1]), float(hair_tint[2]))
            self._set_pbr_uniform1f_gl(gl, "u_hair_primary_shift", _hair_uniform_float("primary_shift", 0.08))
            self._set_pbr_uniform1f_gl(gl, "u_hair_secondary_shift", _hair_uniform_float("secondary_shift", -0.18))
            self._set_pbr_uniform1f_gl(gl, "u_hair_primary_roughness", _hair_uniform_float("primary_roughness", 0.24))
            self._set_pbr_uniform1f_gl(gl, "u_hair_secondary_roughness", _hair_uniform_float("secondary_roughness", 0.42))
            self._set_pbr_uniform1f_gl(gl, "u_hair_secondary_strength", _hair_uniform_float("secondary_strength", 0.48))
            self._set_pbr_uniform1f_gl(gl, "u_hair_anisotropy", _hair_uniform_float("anisotropy", 0.78))
            self._set_pbr_uniform1f_gl(gl, "u_hair_rim_strength", _hair_uniform_float("rim_strength", 0.18))
            self._set_pbr_uniform1f_gl(gl, "u_cloth_sheen_strength", _cloth_uniform_float("strength", 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_cloth_sheen_color", float(cloth_color[0]), float(cloth_color[1]), float(cloth_color[2]))
            self._set_pbr_uniform1f_gl(gl, "u_cloth_sheen_roughness", _cloth_uniform_float("roughness", 0.58))
            self._set_pbr_uniform3f_gl(gl, "u_cloth_sheen_edge_tint", float(cloth_edge_tint[0]), float(cloth_edge_tint[1]), float(cloth_edge_tint[2]))
            self._set_pbr_uniform1f_gl(gl, "u_cloth_sheen_fiber_strength", _cloth_uniform_float("fiber_strength", 0.24))
            self._set_pbr_uniform1f_gl(gl, "u_cloth_sheen_wrap", _cloth_uniform_float("wrap", 0.34))
            self._set_pbr_uniform1f_gl(gl, "u_cloth_sheen_retroreflection", _cloth_uniform_float("retroreflection", 0.28))
            self._set_pbr_uniform1f_gl(gl, "u_glint_strength", _glint_uniform_float("strength", 0.0))
            self._set_pbr_uniform3f_gl(gl, "u_glint_color", float(glint_color[0]), float(glint_color[1]), float(glint_color[2]))
            self._set_pbr_uniform1f_gl(gl, "u_glint_density", _glint_uniform_float("density", 0.24))
            self._set_pbr_uniform1f_gl(gl, "u_glint_scale", _glint_uniform_float("scale", 64.0))
            self._set_pbr_uniform1f_gl(gl, "u_glint_threshold", _glint_uniform_float("threshold", 0.62))
            self._set_pbr_uniform1f_gl(gl, "u_glint_sharpness", _glint_uniform_float("sharpness", 18.0))
            self._set_pbr_uniform1f_gl(gl, "u_glint_roughness_jitter", _glint_uniform_float("roughness_jitter", 0.55))
            self._set_pbr_uniform1f_gl(gl, "u_triplanar_strength", float(triplanar_rendering.get("strength", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_triplanar_scale", float(triplanar_rendering.get("scale", 1.0) or 1.0))
            self._set_pbr_uniform1f_gl(gl, "u_triplanar_blend_sharpness", float(triplanar_rendering.get("blend_sharpness", 4.0) or 4.0))
            self._set_pbr_uniform3f_gl(gl, "u_triplanar_offset", float(triplanar_offset[0]), float(triplanar_offset[1]), float(triplanar_offset[2]))
            self._set_pbr_uniform1f_gl(gl, "u_screen_ao_strength", ao_strength)
            self._set_pbr_uniform1f_gl(gl, "u_screen_ao_radius", ao_radius)
            self._set_pbr_uniform1f_gl(gl, "u_screen_ao_distance", ao_distance)
            self._set_pbr_uniform3f_gl(
                gl,
                "u_screen_ao_color",
                float(ao_color[0]),
                float(ao_color[1]),
                float(ao_color[2]),
            )
            self._set_pbr_uniform1i_gl(gl, "u_screen_ao_ambient", ao_ambient)
            self._set_pbr_uniform1i_gl(gl, "u_screen_ao_diffuse", ao_diffuse)
            self._set_pbr_uniform1i_gl(gl, "u_screen_ao_specular", ao_specular)
            ibl_bundle = self._ibl_texture_bundle_for_path(str(lighting["hdri_path"] or ""))
            ibl_bound = self._bind_ibl_bundle(ibl_bundle)
            self._set_pbr_uniform("u_has_ibl_probe", 1 if ibl_bound else 0)
            self._set_pbr_uniform1i_gl(gl, "u_has_ibl_probe", 1 if ibl_bound else 0)
            self._set_pbr_uniform("u_prefilter_level_count", float((ibl_bundle or {}).get("level_count", 0.0) or 0.0))
            self._set_pbr_uniform1f_gl(gl, "u_prefilter_level_count", float((ibl_bundle or {}).get("level_count", 0.0) or 0.0))
            hdri_tex = None if ibl_bound else self._hdri_texture_for_path(str(lighting["hdri_path"] or ""))
            self._set_pbr_uniform("u_has_hdri_tex", 1 if hdri_tex is not None else 0)
            self._set_pbr_uniform1i_gl(gl, "u_has_hdri_tex", 1 if hdri_tex is not None else 0)
            if hdri_tex is not None:
                hdri_tex.bind(5)
            depth_tex = self._depth_texture_for_item(item)
            self._set_pbr_uniform("u_has_depth_tex", 1 if depth_tex is not None else 0)
            self._set_pbr_uniform("u_depth_enabled", 1.0 if depth_tex is not None else 0.0)
            self._set_pbr_uniform1i_gl(gl, "u_has_depth_tex", 1 if depth_tex is not None else 0)
            self._set_pbr_uniform1f_gl(gl, "u_depth_enabled", 1.0 if depth_tex is not None else 0.0)
            if depth_tex is not None:
                depth_tex.bind(6)
            occlusion = item.get("pbr_depth_occlusion") if isinstance(item.get("pbr_depth_occlusion"), dict) else {}
            try:
                default_tolerance = max(0.0, min(0.25, float(occlusion.get("tolerance", 0.02))))
            except Exception:
                default_tolerance = 0.02
            edge_glow = occlusion.get("edge_glow") if isinstance(occlusion.get("edge_glow"), dict) else {}
            try:
                edge_glow_strength = max(0.0, min(1.0, float(edge_glow.get("strength", 0.0) or 0.0)))
            except Exception:
                edge_glow_strength = 0.0
            if not bool(edge_glow.get("enabled")):
                edge_glow_strength = 0.0
            try:
                edge_glow_radius = max(0.5, min(18.0, float(edge_glow.get("radius_px", 3.0) or 3.0)))
            except Exception:
                edge_glow_radius = 3.0
            edge_glow_color = self._vec3(edge_glow.get("color"), (0.38, 0.82, 1.0))
            rows = item.get("pbr_triangles")
            if not isinstance(rows, list):
                if shadow_bound:
                    self._unbind_raw_texture(gl, 8)
                if hdri_tex is not None:
                    hdri_tex.release(5)
                if ibl_bound:
                    self._release_ibl_bundle(ibl_bundle)
                if depth_tex is not None:
                    depth_tex.release(6)
                continue
            for batch in self._pbr_batches_for_item(item, include_object_depth=depth_tex is not None):
                maps = batch.get("maps") if isinstance(batch.get("maps"), dict) else {}
                path = str(batch.get("path") or "")
                tex = self._texture_for_path(path, *self._texture_wrap_for_map(maps, "base"))
                has_base_tex = tex is not None
                if tex is None:
                    tex = self._white_texture()
                if tex is None:
                    continue
                rough_tex = self._texture_for_path(str(maps.get("roughness") or ""), *self._texture_wrap_for_map(maps, "roughness"))
                metal_tex = self._texture_for_path(str(maps.get("metallic") or ""), *self._texture_wrap_for_map(maps, "metallic"))
                spec_tex = self._texture_for_path(str(maps.get("specular") or ""), *self._texture_wrap_for_map(maps, "specular"))
                normal_tex = self._texture_for_path(str(maps.get("normal") or ""), *self._texture_wrap_for_map(maps, "normal"))
                occlusion_tex = self._texture_for_path(str(maps.get("occlusion") or ""), *self._texture_wrap_for_map(maps, "occlusion"))
                emissive_tex = self._texture_for_path(str(maps.get("emissive") or ""), *self._texture_wrap_for_map(maps, "emissive"))
                opacity_tex = self._texture_for_path(str(maps.get("opacity") or ""), *self._texture_wrap_for_map(maps, "opacity"))
                height_tex = self._texture_for_path(str(maps.get("height") or ""), *self._texture_wrap_for_map(maps, "height"))
                raw = batch.get("vertices")
                if not isinstance(raw, list):
                    continue
                stride_floats = int(batch.get("stride_floats", _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS) or _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS)
                stride_bytes = stride_floats * 4
                if len(raw) < stride_floats * 3:
                    continue
                n_verts = int(len(raw) // stride_floats)
                if n_verts <= 0:
                    continue
                cache_key = self._vbo_cache_key(
                    "pbr",
                    item,
                    batch.get("batch_key"),
                    len(raw),
                    stride_floats,
                )
                try:
                    object_depth = max(0.0, min(1.0, float(batch.get("object_depth", 1.0))))
                except Exception:
                    object_depth = 1.0
                self._set_pbr_uniform("u_object_depth", object_depth)
                self._set_pbr_uniform("u_occlusion_tolerance", default_tolerance)
                self._set_pbr_uniform("u_depth_edge_glow_strength", edge_glow_strength)
                self._set_pbr_uniform("u_depth_edge_glow_radius_px", edge_glow_radius)
                self._set_pbr_uniform("u_depth_edge_glow_color", edge_glow_color)
                self._set_pbr_uniform1f_gl(gl, "u_object_depth", object_depth)
                self._set_pbr_uniform1f_gl(gl, "u_occlusion_tolerance", default_tolerance)
                self._set_pbr_uniform1f_gl(gl, "u_depth_edge_glow_strength", edge_glow_strength)
                self._set_pbr_uniform1f_gl(gl, "u_depth_edge_glow_radius_px", edge_glow_radius)
                self._set_pbr_uniform3f_gl(
                    gl,
                    "u_depth_edge_glow_color",
                    float(edge_glow_color.x()),
                    float(edge_glow_color.y()),
                    float(edge_glow_color.z()),
                )
                tex.bind(0)
                if rough_tex is not None:
                    rough_tex.bind(1)
                if metal_tex is not None:
                    metal_tex.bind(2)
                if spec_tex is not None:
                    spec_tex.bind(3)
                if normal_tex is not None:
                    normal_tex.bind(4)
                if occlusion_tex is not None:
                    occlusion_tex.bind(7)
                if emissive_tex is not None:
                    emissive_tex.bind(12)
                if opacity_tex is not None:
                    opacity_tex.bind(13)
                if height_tex is not None:
                    height_tex.bind(14)
                self._set_pbr_uniform("u_has_base_tex", 1 if has_base_tex else 0)
                self._set_pbr_uniform("u_has_roughness_tex", 1 if rough_tex is not None else 0)
                self._set_pbr_uniform("u_has_metallic_tex", 1 if metal_tex is not None else 0)
                self._set_pbr_uniform("u_has_specular_tex", 1 if spec_tex is not None else 0)
                self._set_pbr_uniform("u_has_normal_tex", 1 if normal_tex is not None else 0)
                self._set_pbr_uniform("u_has_occlusion_tex", 1 if occlusion_tex is not None else 0)
                self._set_pbr_uniform("u_has_emissive_tex", 1 if emissive_tex is not None else 0)
                self._set_pbr_uniform("u_has_opacity_tex", 1 if opacity_tex is not None else 0)
                self._set_pbr_uniform("u_has_height_tex", 1 if height_tex is not None else 0)
                uv_flip_v = self._map_bool(maps, "uv_v_flip", False)
                self._set_pbr_uniform("u_flip_uv_v", 1 if uv_flip_v else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_base_tex", 1 if has_base_tex else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_roughness_tex", 1 if rough_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_metallic_tex", 1 if metal_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_specular_tex", 1 if spec_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_normal_tex", 1 if normal_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_occlusion_tex", 1 if occlusion_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_emissive_tex", 1 if emissive_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_opacity_tex", 1 if opacity_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_has_height_tex", 1 if height_tex is not None else 0)
                self._set_pbr_uniform1i_gl(gl, "u_flip_uv_v", 1 if uv_flip_v else 0)
                self._set_pbr_uniform("u_roughness_channel", self._channel_selector(maps, "roughness", 0))
                self._set_pbr_uniform("u_metallic_channel", self._channel_selector(maps, "metallic", 0))
                self._set_pbr_uniform("u_specular_channel", self._channel_selector(maps, "specular", 0))
                self._set_pbr_uniform("u_occlusion_channel", self._channel_selector(maps, "occlusion", 0))
                self._set_pbr_uniform("u_opacity_channel", self._channel_selector(maps, "opacity", 0))
                self._set_pbr_uniform("u_height_channel", self._channel_selector(maps, "height", 0))
                self._set_pbr_uniform("u_alpha_cutoff", self._map_float(maps, "alpha_cutoff", 0.001, lo=0.0, hi=1.0))
                self._set_pbr_uniform("u_emissive_factor", self._map_vec3(maps, "emissive_factor"))
                self._set_pbr_uniform1f_gl(gl, "u_alpha_cutoff", self._map_float(maps, "alpha_cutoff", 0.001, lo=0.0, hi=1.0))
                bound_vbo = self._bind_packet_vbo(raw, self._pbr_vbo, cache_key)
                if bound_vbo is None:
                    tex.release(0)
                    if rough_tex is not None:
                        rough_tex.release(1)
                    if metal_tex is not None:
                        metal_tex.release(2)
                    if spec_tex is not None:
                        spec_tex.release(3)
                    if normal_tex is not None:
                        normal_tex.release(4)
                    if occlusion_tex is not None:
                        occlusion_tex.release(7)
                    if emissive_tex is not None:
                        emissive_tex.release(12)
                    if opacity_tex is not None:
                        opacity_tex.release(13)
                    if height_tex is not None:
                        height_tex.release(14)
                    continue
                self._pbr_program.enableAttributeArray(0)
                self._pbr_program.enableAttributeArray(1)
                self._pbr_program.enableAttributeArray(2)
                self._pbr_program.enableAttributeArray(3)
                self._pbr_program.enableAttributeArray(4)
                self._pbr_program.enableAttributeArray(5)
                self._pbr_program.enableAttributeArray(6)
                has_world_pos = stride_floats >= _AR_PBR_TEXTURE_VERTEX_STRIDE_FLOATS
                if has_world_pos:
                    self._pbr_program.enableAttributeArray(7)
                self._pbr_program.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride_bytes)
                self._pbr_program.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride_bytes)
                self._pbr_program.setAttributeBuffer(2, _GL_FLOAT, 16, 3, stride_bytes)
                self._pbr_program.setAttributeBuffer(3, _GL_FLOAT, 28, 3, stride_bytes)
                self._pbr_program.setAttributeBuffer(4, _GL_FLOAT, 40, 3, stride_bytes)
                self._pbr_program.setAttributeBuffer(5, _GL_FLOAT, 52, 4, stride_bytes)
                self._pbr_program.setAttributeBuffer(6, _GL_FLOAT, 68, 3, stride_bytes)
                if has_world_pos:
                    self._pbr_program.setAttributeBuffer(7, _GL_FLOAT, 80, 3, stride_bytes)
                gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)
                self._pbr_program.disableAttributeArray(0)
                self._pbr_program.disableAttributeArray(1)
                self._pbr_program.disableAttributeArray(2)
                self._pbr_program.disableAttributeArray(3)
                self._pbr_program.disableAttributeArray(4)
                self._pbr_program.disableAttributeArray(5)
                self._pbr_program.disableAttributeArray(6)
                if has_world_pos:
                    self._pbr_program.disableAttributeArray(7)
                bound_vbo.release()
                tex.release(0)
                if rough_tex is not None:
                    rough_tex.release(1)
                if metal_tex is not None:
                    metal_tex.release(2)
                if spec_tex is not None:
                    spec_tex.release(3)
                if normal_tex is not None:
                    normal_tex.release(4)
                if occlusion_tex is not None:
                    occlusion_tex.release(7)
                if emissive_tex is not None:
                    emissive_tex.release(12)
                if opacity_tex is not None:
                    opacity_tex.release(13)
                if height_tex is not None:
                    height_tex.release(14)
                drew_any = True
            if hdri_tex is not None:
                hdri_tex.release(5)
            if ibl_bound:
                self._release_ibl_bundle(ibl_bundle)
            if depth_tex is not None:
                depth_tex.release(6)
            if shadow_bound:
                self._unbind_raw_texture(gl, 8)
        if hasattr(gl, "glDepthMask"):
            gl.glDepthMask(False)
        gl.glDisable(_GL_DEPTH_TEST)
        self._pbr_program.release()
        return drew_any

    def draw(self, gl, items: list[dict]) -> bool:
        if not items:
            return True
        color_ok = False
        pbr_ok = False
        try:
            color_ok = self._draw_color_packets(gl, items)
        except Exception as exc:
            print(
                f"[OpenGLPreviewWidget] AR/PBR color packet draw failed: {exc}",
                file=sys.stderr,
                flush=True,
            )
        has_pbr = any(
            isinstance(item, dict) and int(item.get("pbr_triangle_count", 0) or 0) > 0
            for item in items
        )
        if has_pbr:
            try:
                gl.glEnable(_GL_BLEND)
                gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
                pbr_ok = self._draw_pbr_packets(gl, items)
            except Exception as exc:
                print(
                    f"[OpenGLPreviewWidget] AR/PBR textured PBR draw failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        self._attach_vbo_diagnostics(items)
        return color_ok or pbr_ok or not has_pbr


class OpenGLPreviewWidget(QOpenGLWidget):
    """Drop-in replacement for the QLabel preview surface.

    Call ``update_frame(rgb_ndarray, grade)`` whenever a new frame is
    ready. ``rgb_ndarray`` must be uint8, contiguous, shape (H, W, 3)
    in RGB order. ``grade`` is a ``ColorGrade`` instance or None.
    """
    spine_overlay_failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        fmt = QSurfaceFormat(self.format())
        if fmt.depthBufferSize() < 24:
            fmt.setDepthBufferSize(24)
            self.setFormat(fmt)
        self.setMinimumSize(160, 90)
        # The preview matte sits behind the letterboxed video.
        self._matte = QColor("#000000")
        self._pending_frame: np.ndarray | None = None
        self._uniforms: dict = _identity_uniforms()
        self._clip_effect_uniforms: dict = _identity_clip_effects()
        self._frame_size: tuple[int, int] = (0, 0)
        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._texture: QOpenGLTexture | None = None
        # Uniform location cache, populated after shader link. PySide6
        # 6.11 only accepts bytes (not str) for the name overloads, and
        # has no (str, int) overload at all — so the safe path is
        # location-based for every per-frame uniform set.
        self._uloc: dict[str, int] = {}
        self._initialized = False
        # GPU blur: sigma in texture-pixel units (0 = off).
        self._blur_sigma: float = 0.0
        self._spine_items: list[dict] = []
        self._spine_painter: _SpineDirectGLPainter | None = None
        self._spine_failed = False
        self._ar_pbr_items: list[dict] = []
        self._ar_pbr_painter: _ARPBRDirectGLPainter | None = None
        self._ar_pbr_failed = False
        self._mmd_items: list[dict] = []
        self._mmd_painter: _MMDDirectGLPainter | None = None
        self._mmd_failed = False
        self._mmd_debug_overlay_enabled = _env_flag("TIGERCAPTURE_MMD_DEBUG_OVERLAY")
        self._upload_count = 0
        self._last_upload_ms = 0.0
        self._last_paint_ms = 0.0
        self._last_upload_diag_s = 0.0

    def _surface_size_px(self) -> tuple[int, int]:
        """Return the backing OpenGL surface size in physical pixels."""
        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        dpr = max(0.01, dpr)
        return (
            max(1, int(round(float(self.width()) * dpr))),
            max(1, int(round(float(self.height()) * dpr))),
        )

    # ---- public API ----

    def update_frame(self, rgb: np.ndarray, grade) -> None:
        """Hand off a fresh frame + grade. Triggers a repaint."""
        if rgb is None:
            return
        # Defensive: ensure contiguous uint8 RGB. If the caller passed
        # a slice, ascontiguousarray is a no-op in the common case.
        if not rgb.flags["C_CONTIGUOUS"]:
            rgb = np.ascontiguousarray(rgb)
        self._pending_frame = rgb
        self._uniforms = grade_to_uniforms(grade)
        self.update()

    def preview_gl_diagnostics(self) -> dict[str, object]:
        return {
            "frame_size": [int(self._frame_size[0]), int(self._frame_size[1])],
            "upload_count": int(self._upload_count),
            "last_upload_ms": round(float(self._last_upload_ms), 3),
            "last_paint_ms": round(float(self._last_paint_ms), 3),
        }

    def _record_preview_gl_upload_event(
        self,
        *,
        elapsed_ms: float,
        width: int,
        height: int,
        mode: str,
    ) -> None:
        try:
            threshold = float(os.environ.get("TIGERCAPTURE_PREVIEW_GL_UPLOAD_SLOW_MS", "6.0"))
        except Exception:
            threshold = 6.0
        now = time.monotonic()
        if float(elapsed_ms) < threshold and now - float(self._last_upload_diag_s or 0.0) < 5.0:
            return
        if now - float(self._last_upload_diag_s or 0.0) < 1.0:
            return
        self._last_upload_diag_s = now
        try:
            from app.loading_performance import record_loading_event

            record_loading_event(
                "preview.gl",
                "texture_upload",
                status="ok",
                elapsed_ms=float(elapsed_ms),
                detail=f"{mode} {int(width)}x{int(height)}",
                metadata={
                    "width": int(width),
                    "height": int(height),
                    "mode": str(mode),
                    "upload_count": int(self._upload_count),
                    "bytes": int(width) * int(height) * 3,
                },
            )
        except Exception:
            pass

    def set_spine_overlay_items(self, items) -> None:
        """Set Spine actor states to draw directly in the preview GL pass."""
        if self._spine_failed:
            self._spine_items = []
            return
        if not items:
            self._spine_items = []
            return
        self._spine_items = list(items)

    def set_ar_pbr_overlay_items(self, items) -> None:
        """Set AR/PBR mesh packets to draw directly in the preview GL pass."""
        if self._ar_pbr_failed:
            self._ar_pbr_items = []
            return
        if not items:
            self._ar_pbr_items = []
            return
        self._ar_pbr_items = list(items)

    def ar_pbr_overlay_diagnostics(self) -> dict[str, object]:
        """Return diagnostics for the currently deferred AR/PBR GL overlay."""
        items = [item for item in self._ar_pbr_items if isinstance(item, dict)]
        painter_diag: dict[str, object] = {}
        if self._ar_pbr_painter is not None:
            try:
                painter_diag = dict(self._ar_pbr_painter.vbo_diagnostics())
            except Exception:
                painter_diag = {}
        return overlay_diagnostics_payload(
            items=items,
            painter_diagnostics=painter_diag,
            failed=bool(self._ar_pbr_failed),
            painter_ready=self._ar_pbr_painter is not None,
        )

    def set_mmd_overlay_items(self, items) -> None:
        """Set MMD PMX render packets to draw directly in the preview GL pass."""
        if self._mmd_failed:
            self._mmd_items = []
            return
        if not items:
            self._mmd_items = []
            return
        self._mmd_items = list(items)

    def set_mmd_debug_overlay_enabled(self, enabled: bool) -> None:
        """Toggle the compact MMD performance overlay. Off by default."""
        next_value = bool(enabled)
        if self._mmd_debug_overlay_enabled == next_value:
            return
        self._mmd_debug_overlay_enabled = next_value
        self.update()

    def set_clip_effects(self, effects) -> None:
        self._clip_effect_uniforms = clip_effects_to_uniforms(effects)

    def set_blur(self, sigma: float) -> None:
        """Set GPU Gaussian blur strength.

        ``sigma`` is the standard deviation in *texture pixels*.
        Pass ``0.0`` (or negative) to disable blur.  The value is
        consumed on the next ``paintGL`` call — no extra repaint is
        triggered here; call ``update()`` if you need an immediate
        refresh without a new frame.
        """
        self._blur_sigma = max(0.0, float(sigma))

    def clear(self) -> None:
        """Drop the current frame (e.g. on track removal)."""
        self._pending_frame = None
        self._spine_items = []
        self._ar_pbr_items = []
        self._mmd_items = []
        self._clip_effect_uniforms = _identity_clip_effects()
        self._frame_size = (0, 0)
        if self._initialized and self._texture is not None:
            self.makeCurrent()
            self._texture.destroy()
            self._texture = None
            self.doneCurrent()
        self.update()

    def _mmd_debug_overlay_lines(self) -> list[str]:
        if not self._mmd_debug_overlay_enabled or not self._mmd_items:
            return []
        first = next((item for item in self._mmd_items if isinstance(item, dict)), None)
        if first is None:
            return []
        diagnostics = dict(first.get("diagnostics") or {})
        try:
            from app.mmd.diagnostics import format_mmd_performance_line

            perf_line = format_mmd_performance_line(diagnostics)
        except Exception:
            perf_line = ""
        track_id = str(first.get("track_id") or "")
        if not track_id:
            path = str(first.get("path") or "")
            track_id = Path(path).stem if path else "item"
        lines = [f"MMD debug: {len(self._mmd_items)} item"]
        if perf_line:
            lines.append(perf_line)
        binds = int(diagnostics.get("mmd_vbo_cache_binds", 0) or 0)
        hits = int(diagnostics.get("mmd_vbo_cache_hits", 0) or 0)
        misses = int(diagnostics.get("mmd_vbo_cache_misses", 0) or 0)
        uploads = int(diagnostics.get("mmd_vbo_transient_uploads", 0) or 0)
        if binds > 0:
            lines.append(f"VBO bind {binds} hit {hits} miss {misses} upload {uploads}")
            lines.append(
                "VBO cached "
                f"{_format_debug_bytes(diagnostics.get('mmd_vbo_cached_bytes', 0))} "
                f"uploaded {_format_debug_bytes(diagnostics.get('mmd_vbo_uploaded_bytes', 0))}"
            )
        fallback = str(
            diagnostics.get("gpu_skinning_fallback_reason")
            or diagnostics.get("track_gpu_skinning_fallback_reason")
            or ""
        )
        frame = diagnostics.get("track_playback_frame")
        suffix = f" frame {float(frame):.1f}" if frame is not None else ""
        if fallback:
            lines.append(f"{track_id}{suffix} fallback {fallback}")
        else:
            lines.append(f"{track_id}{suffix}")
        return lines[:5]

    def _draw_mmd_debug_overlay(self) -> None:
        lines = self._mmd_debug_overlay_lines()
        if not lines:
            return
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
            font = QFont("Consolas")
            font.setPointSize(9)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            line_height = max(13, metrics.height())
            text_width = max(metrics.horizontalAdvance(line) for line in lines)
            x = 10
            y = 10
            pad_x = 9
            pad_y = 7
            rect_w = text_width + pad_x * 2
            rect_h = line_height * len(lines) + pad_y * 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(9, 11, 16, 205))
            painter.drawRoundedRect(x, y, rect_w, rect_h, 6, 6)
            painter.setPen(QColor(232, 238, 248, 235))
            baseline = y + pad_y + metrics.ascent()
            for line in lines:
                painter.drawText(x + pad_x, baseline, line)
                baseline += line_height
        finally:
            painter.end()

    # ---- QOpenGLWidget overrides ----

    def initializeGL(self) -> None:
        gl = self.context().functions()
        m = self._matte
        gl.glClearColor(m.redF(), m.greenF(), m.blueF(), 1.0)

        prog = QOpenGLShaderProgram(self)
        # Compile each shader stage separately so a failure in one
        # produces a useful log instead of a generic link error.
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER,
        )
        if not ok_v:
            print(
                f"[OpenGLPreviewWidget] vertex shader compile failed:\n"
                f"{prog.log()}",
                file=sys.stderr, flush=True,
            )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER,
        )
        if not ok_f:
            print(
                f"[OpenGLPreviewWidget] fragment shader compile failed:\n"
                f"{prog.log()}",
                file=sys.stderr, flush=True,
            )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_uv", 1)
        if not prog.link():
            log = prog.log()
            print(
                f"[OpenGLPreviewWidget] shader link failed:\n{log}",
                file=sys.stderr, flush=True,
            )
            return
        self._program = prog
        # Cache every uniform location we touch per frame.
        for key in (
            "tex", "quad_scale", "has_grade",
            "brightness", "contrast", "saturation",
            "offset_rgb", "shadows_rgb", "midtones_rgb", "highlights_rgb",
            "blur_sigma", "tex_size",
            "fx_enabled", "fx_sharpen", "fx_vignette",
            "fx_vignette_feather", "fx_chroma_aberration",
            "chroma_enabled", "chroma_key_hue", "chroma_hue_range",
            "chroma_sat_min", "chroma_val_min", "chroma_spill",
            "chroma_bg",
        ):
            self._uloc[key] = prog.uniformLocation(f"u_{key}")
        print(
            "[OpenGLPreviewWidget] shader linked OK; GL version:",
            gl.glGetString(0x1F02),  # GL_VERSION
            "u_loc:", self._uloc,
            file=sys.stderr, flush=True,
        )

        # Two triangles via TRIANGLE_STRIP. UV Y is flipped because
        # video frames are top-down (origin top-left) while OpenGL
        # texture coords are bottom-up by default.
        verts = np.array(
            [
                # x,    y,    u,    v
                -1.0, -1.0, 0.0, 1.0,
                +1.0, -1.0, 1.0, 1.0,
                -1.0, +1.0, 0.0, 0.0,
                +1.0, +1.0, 1.0, 0.0,
            ],
            dtype=np.float32,
        )
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        vbo.create()
        vbo.bind()
        vbo.allocate(verts.tobytes(), int(verts.nbytes))
        vbo.release()
        self._vbo = vbo
        self._initialized = True

    def resizeGL(self, w: int, h: int) -> None:
        gl = self.context().functions()
        # devicePixelRatio handles HiDPI — Qt already scales paint
        # dimensions, so the integer w/h here are physical pixels.
        gl.glViewport(0, 0, max(1, w), max(1, h))

    def paintGL(self) -> None:
        paint_started = time.perf_counter()
        gl = self.context().functions()
        surface_w, surface_h = self._surface_size_px()
        gl.glViewport(0, 0, surface_w, surface_h)
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glClear(_GL_COLOR_BUFFER_BIT)

        # Upload pending frame. We keep one ``QOpenGLTexture`` alive
        # across frames and re-upload via ``setData(QImage)`` — Qt
        # routes that to ``glTexSubImage2D`` when the size hasn't
        # changed, so GPU storage is reused and no QOpenGLTexture
        # wrapper churns at 60 fps. The texture is destroyed/recreated
        # only when the frame dimensions actually change.
        if self._pending_frame is not None:
            upload_started = time.perf_counter()
            upload_mode = "subimage"
            rgb = self._pending_frame
            h, w = rgb.shape[:2]
            qimg = QImage(
                rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888,
            )
            no_mip = QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps
            if self._texture is None or self._frame_size != (w, h):
                upload_mode = "create"
                if self._texture is not None:
                    self._texture.destroy()
                    self._texture = None
                tex = QOpenGLTexture(qimg, no_mip)
                tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
                self._texture = tex
                self._frame_size = (w, h)
                print(
                    f"[OpenGLPreviewWidget] created {w}x{h} texture",
                    file=sys.stderr, flush=True,
                )
            else:
                # Same size — re-upload pixels into existing storage.
                self._texture.setData(qimg, no_mip)
            upload_ms = (time.perf_counter() - upload_started) * 1000.0
            self._upload_count += 1
            self._last_upload_ms = upload_ms
            self._record_preview_gl_upload_event(
                elapsed_ms=upload_ms,
                width=int(w),
                height=int(h),
                mode=upload_mode,
            )
            # Drop the numpy reference now that the upload has landed.
            self._pending_frame = None

        if (
            self._program is None
            or self._vbo is None
            or self._texture is None
            or self._frame_size == (0, 0)
        ):
            return

        sx, sy = _aspect_fit_scale(
            self._frame_size[0], self._frame_size[1],
            surface_w, surface_h,
        )

        prog = self._program
        prog.bind()

        u = self._uniforms
        # PySide6 6.11's setUniformValue accepts ``bytes`` (not ``str``)
        # for the name argument, AND has no ``(name, int)`` overload —
        # so the bool uniform is set by location after looking it up.
        # Cache the locations once after link to avoid the per-frame
        # ``uniformLocation`` cost.
        loc = self._uloc
        prog.setUniformValue(
            loc["quad_scale"], QVector2D(float(sx), float(sy)),
        )
        prog.setUniformValue(loc["has_grade"], 1 if u["has_grade"] else 0)
        prog.setUniformValue(loc["brightness"], float(u["brightness"]))
        prog.setUniformValue(loc["contrast"], float(u["contrast"]))
        prog.setUniformValue(loc["saturation"], float(u["saturation"]))
        for name in (
            "offset_rgb", "shadows_rgb", "midtones_rgb", "highlights_rgb",
        ):
            r, g, b = u[name]
            prog.setUniformValue(
                loc[name],
                QVector3D(float(r), float(g), float(b)),
            )

        # GPU Gaussian blur uniforms.
        prog.setUniformValue(loc["blur_sigma"], float(self._blur_sigma))
        fw, fh = self._frame_size
        prog.setUniformValue(
            loc["tex_size"],
            QVector2D(float(max(1, fw)), float(max(1, fh))),
        )
        fx = self._clip_effect_uniforms
        prog.setUniformValue(loc["fx_enabled"], 1 if fx["enabled"] else 0)
        prog.setUniformValue(loc["fx_sharpen"], float(fx["sharpen"]))
        prog.setUniformValue(loc["fx_vignette"], float(fx["vignette"]))
        prog.setUniformValue(loc["fx_vignette_feather"], float(fx["vignette_feather"]))
        prog.setUniformValue(loc["fx_chroma_aberration"], float(fx["chroma_aberration"]))
        prog.setUniformValue(loc["chroma_enabled"], 1 if fx["chroma_enabled"] else 0)
        prog.setUniformValue(loc["chroma_key_hue"], float(fx["chroma_key_hue"]))
        prog.setUniformValue(loc["chroma_hue_range"], float(fx["chroma_hue_range"]))
        prog.setUniformValue(loc["chroma_sat_min"], float(fx["chroma_sat_min"]))
        prog.setUniformValue(loc["chroma_val_min"], float(fx["chroma_val_min"]))
        prog.setUniformValue(loc["chroma_spill"], float(fx["chroma_spill"]))
        bg_r, bg_g, bg_b = fx["chroma_bg"]
        prog.setUniformValue(
            loc["chroma_bg"],
            QVector3D(float(bg_r), float(bg_g), float(bg_b)),
        )

        # Bind texture to unit 0, tell shader to sample from it.
        self._texture.bind(0)
        prog.setUniformValue(self._uloc["tex"], 0)

        # Set up vertex attributes from the VBO.
        self._vbo.bind()
        stride = 4 * 4   # 4 floats per vertex × 4 bytes
        prog.enableAttributeArray(0)
        prog.enableAttributeArray(1)
        # offset, tupleSize, stride
        prog.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride)
        prog.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride)

        gl.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)

        prog.disableAttributeArray(0)
        prog.disableAttributeArray(1)
        self._vbo.release()
        self._texture.release()
        prog.release()

        if self._ar_pbr_items:
            if self._ar_pbr_painter is None:
                self._ar_pbr_painter = _ARPBRDirectGLPainter(self)
            fw, fh = self._frame_size
            ww, wh = surface_w, surface_h
            vx, vy, vw, vh = _letterbox_viewport(fw, fh, ww, wh)
            gl.glViewport(int(vx), int(vy), int(vw), int(vh))
            ok = False
            try:
                ok = self._ar_pbr_painter.draw(gl, self._ar_pbr_items)
            except Exception as exc:
                print(
                    f"[OpenGLPreviewWidget] AR/PBR direct draw failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            finally:
                gl.glViewport(0, 0, ww, wh)
            if not ok:
                self._ar_pbr_failed = True
                self._ar_pbr_items = []

        if self._mmd_items:
            if self._mmd_painter is None:
                self._mmd_painter = _MMDDirectGLPainter(self)
            fw, fh = self._frame_size
            ww, wh = surface_w, surface_h
            vx, vy, vw, vh = _letterbox_viewport(fw, fh, ww, wh)
            gl.glViewport(int(vx), int(vy), int(vw), int(vh))
            ok = False
            try:
                ok = self._mmd_painter.draw(gl, self._mmd_items, fw, fh, (vx, vy, vw, vh))
            except Exception as exc:
                print(
                    f"[OpenGLPreviewWidget] MMD direct draw failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            finally:
                gl.glViewport(0, 0, ww, wh)
            if not ok:
                self._mmd_failed = True
                self._mmd_items = []

        if self._spine_items:
            if self._spine_painter is None:
                self._spine_painter = _SpineDirectGLPainter(self)
            fw, fh = self._frame_size
            ww, wh = surface_w, surface_h
            vx, vy, vw, vh = _letterbox_viewport(fw, fh, ww, wh)
            gl.glViewport(int(vx), int(vy), int(vw), int(vh))
            ok = False
            try:
                ok = self._spine_painter.draw(gl, self._spine_items, fw, fh)
            except Exception as exc:
                print(
                    f"[OpenGLPreviewWidget] Spine direct draw failed: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
            finally:
                gl.glViewport(0, 0, ww, wh)
            if not ok and not self._spine_failed:
                self._spine_failed = True
                self._spine_items = []
                self.spine_overlay_failed.emit("Spine direct GL overlay failed")

        self._draw_mmd_debug_overlay()
        self._last_paint_ms = (time.perf_counter() - paint_started) * 1000.0
