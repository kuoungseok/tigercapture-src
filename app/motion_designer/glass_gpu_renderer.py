"""Direct OpenGL backdrop renderer for eligible Tiger Glass preview graphs."""
from __future__ import annotations

import ctypes
from dataclasses import replace
import math
import time

try:
    from OpenGL import GL
except Exception:  # pragma: no cover - packaged fallback environments
    GL = None

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QVector2D, QVector4D
from PySide6.QtOpenGL import (
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
)

from .glass_material import glass_effect
from .craft_style import is_craft_style_effect
from .gpu_effect_contract import (
    gpu_effect_parameters,
    is_common_gpu_effect,
    unsupported_gpu_effect_reason,
)
from .keyframes import evaluate_property
from .painterly_look import is_painterly_look_effect
from .render_graph import RenderGraph, RenderNode, render_graph_image


_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
attribute vec2 a_uv;
uniform vec2 u_widget_size;
uniform vec4 u_target;
varying vec2 v_uv;
void main() {
    vec2 screen = u_target.xy + a_position * u_target.zw;
    vec2 ndc = vec2(
        screen.x / u_widget_size.x * 2.0 - 1.0,
        1.0 - screen.y / u_widget_size.y * 2.0
    );
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = a_uv;
}
"""

_FRAGMENT_SHADER = """
#version 120
uniform sampler2D u_backdrop;
uniform sampler2D u_mask;
uniform sampler2D u_track_matte;
uniform sampler2D u_shadow_receiver;
uniform int u_mode;
uniform int u_matte_mode;
uniform int u_backdrop_flip_y;
uniform vec2 u_texel;
uniform vec4 u_tint;
uniform float u_blur;
uniform float u_refraction;
uniform float u_normal_scale;
uniform float u_thickness;
uniform float u_absorption;
uniform float u_edge;
uniform float u_specular;
uniform float u_dispersion;
uniform float u_bloom;
uniform float u_tint_strength;
uniform float u_opacity;
uniform float u_time;
uniform vec2 u_driver;
uniform float u_seed;
uniform float u_amount;
uniform float u_grain;
uniform float u_grain_size;
uniform float u_flicker;
uniform float u_warmth;
uniform float u_weave_x;
uniform float u_weave_y;
uniform float u_misregistration;
uniform float u_dust;
uniform float u_scratch;
uniform float u_vhs;
uniform float u_color_levels;
uniform float u_toon;
uniform float u_smoothing;
uniform float u_edge_strength;
uniform float u_edge_threshold;
uniform float u_brush_amount;
uniform float u_brush_scale;
uniform float u_granulation;
uniform float u_paper_amount;
uniform float u_hatch_amount;
uniform float u_hatch_spacing;
uniform vec4 u_line_color;
uniform vec4 u_paper_color;
uniform int u_motion_samples;
uniform vec2 u_motion_vector;
uniform int u_blend_mode;
uniform int u_shadow_enabled;
uniform vec2 u_shadow_offset;
uniform float u_shadow_softness;
uniform float u_shadow_alpha;
uniform int u_effect_kind;
uniform vec4 u_effect_values_a;
uniform vec2 u_effect_values_b;
uniform vec4 u_effect_color;
varying vec2 v_uv;

vec2 backdrop_uv(vec2 uv) {
    return vec2(uv.x, u_backdrop_flip_y == 1 ? 1.0 - uv.y : uv.y);
}

vec4 backdrop(vec2 uv) {
    return texture2D(u_backdrop, backdrop_uv(clamp(uv, 0.0, 1.0)));
}

vec4 blurred(vec2 uv) {
    vec2 radius = u_texel * u_blur;
    vec4 value = backdrop(uv) * 0.20;
    value += backdrop(uv + vec2(radius.x, 0.0)) * 0.10;
    value += backdrop(uv - vec2(radius.x, 0.0)) * 0.10;
    value += backdrop(uv + vec2(0.0, radius.y)) * 0.10;
    value += backdrop(uv - vec2(0.0, radius.y)) * 0.10;
    value += backdrop(uv + radius * 0.70) * 0.10;
    value += backdrop(uv - radius * 0.70) * 0.10;
    value += backdrop(uv + vec2(radius.x, -radius.y) * 0.70) * 0.10;
    value += backdrop(uv + vec2(-radius.x, radius.y) * 0.70) * 0.10;
    return value;
}

float hash21(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32 + u_seed * 0.00013);
    return fract(p.x * p.y);
}

vec4 source_pixel(vec2 uv) {
    vec4 source;
    if (u_motion_samples <= 1) {
        source = texture2D(u_mask, clamp(uv, 0.0, 1.0));
    } else {
        vec4 accumulated = vec4(0.0);
        for (int index = 0; index < 32; ++index) {
            if (index < u_motion_samples) {
                float phase = float(index) / max(
                    1.0,
                    float(u_motion_samples - 1)
                ) - 0.5;
                accumulated += texture2D(
                    u_mask,
                    clamp(uv - u_motion_vector * phase, 0.0, 1.0)
                );
            }
        }
        source = accumulated / max(1.0, float(u_motion_samples));
    }
    if (u_matte_mode == 0) {
        return source;
    }
    vec4 matte = texture2D(u_track_matte, clamp(uv, 0.0, 1.0));
    float factor = matte.a;
    if (u_matte_mode == 2 || u_matte_mode == 4) {
        vec3 matte_rgb = matte.a > 0.0001
            ? matte.rgb / matte.a : vec3(0.0);
        factor = dot(matte_rgb, vec3(0.2126, 0.7152, 0.0722)) * matte.a;
    }
    if (u_matte_mode == 3 || u_matte_mode == 4) {
        factor = 1.0 - factor;
    }
    return source * clamp(factor, 0.0, 1.0);
}

vec3 straight_rgb(vec4 color) {
    return color.a > 0.0001 ? color.rgb / color.a : vec3(0.0);
}

vec3 blend_rgb(vec3 backdrop_rgb, vec3 source_rgb) {
    if (u_blend_mode == 1) {
        return backdrop_rgb * source_rgb;
    }
    if (u_blend_mode == 2) {
        return 1.0 - (1.0 - backdrop_rgb) * (1.0 - source_rgb);
    }
    if (u_blend_mode == 3) {
        return min(vec3(1.0), backdrop_rgb + source_rgb);
    }
    if (u_blend_mode == 4) {
        vec3 low = 2.0 * backdrop_rgb * source_rgb;
        vec3 high = 1.0 - 2.0 * (1.0 - backdrop_rgb) * (1.0 - source_rgb);
        return mix(low, high, step(vec3(0.5), backdrop_rgb));
    }
    return source_rgb;
}

vec4 shadowed_backdrop();

vec4 over_backdrop(vec3 rgb, float alpha) {
    vec4 behind = shadowed_backdrop();
    vec3 source_rgb = clamp(rgb, 0.0, 1.0);
    vec3 behind_rgb = straight_rgb(behind);
    float output_alpha = alpha + behind.a * (1.0 - alpha);
    vec3 blended = blend_rgb(behind_rgb, source_rgb);
    vec3 premul = (
        (1.0 - alpha) * behind.rgb
        + (1.0 - behind.a) * source_rgb * alpha
        + behind.a * alpha * blended
    );
    return vec4(premul, output_alpha);
}

float shadow_caster_alpha(vec2 uv) {
    vec2 radius = u_texel * u_shadow_softness;
    float value = source_pixel(uv).a * 0.24;
    value += source_pixel(uv + vec2(radius.x, 0.0)).a * 0.12;
    value += source_pixel(uv - vec2(radius.x, 0.0)).a * 0.12;
    value += source_pixel(uv + vec2(0.0, radius.y)).a * 0.12;
    value += source_pixel(uv - vec2(0.0, radius.y)).a * 0.12;
    value += source_pixel(uv + radius * 0.72).a * 0.07;
    value += source_pixel(uv - radius * 0.72).a * 0.07;
    value += source_pixel(uv + vec2(radius.x, -radius.y) * 0.72).a * 0.07;
    value += source_pixel(uv + vec2(-radius.x, radius.y) * 0.72).a * 0.07;
    return value;
}

vec4 shadowed_backdrop() {
    vec4 behind = backdrop(v_uv);
    if (u_shadow_enabled == 0) {
        return behind;
    }
    float receiver = texture2D(
        u_shadow_receiver,
        clamp(v_uv, 0.0, 1.0)
    ).a;
    float caster = shadow_caster_alpha(v_uv - u_shadow_offset);
    float alpha = clamp(
        caster * receiver * u_shadow_alpha,
        0.0,
        1.0
    );
    return vec4(
        behind.rgb * (1.0 - alpha),
        alpha + behind.a * (1.0 - alpha)
    );
}

vec4 source_over_color(vec4 behind, vec3 rgb, float alpha) {
    vec3 source_rgb = clamp(rgb, 0.0, 1.0);
    vec3 behind_rgb = straight_rgb(behind);
    float output_alpha = alpha + behind.a * (1.0 - alpha);
    vec3 blended = blend_rgb(behind_rgb, source_rgb);
    vec3 premul = (
        (1.0 - alpha) * behind.rgb
        + (1.0 - behind.a) * source_rgb * alpha
        + behind.a * alpha * blended
    );
    return vec4(premul, output_alpha);
}

vec4 effect_input(vec2 uv, int backdrop_input) {
    return backdrop_input == 1 ? backdrop(uv) : source_pixel(uv);
}

vec4 effect_blur(vec2 uv, int backdrop_input, float radius) {
    vec2 step_uv = u_texel * max(0.0, radius);
    vec4 value = effect_input(uv, backdrop_input) * 0.20;
    value += effect_input(uv + vec2(step_uv.x, 0.0), backdrop_input) * 0.12;
    value += effect_input(uv - vec2(step_uv.x, 0.0), backdrop_input) * 0.12;
    value += effect_input(uv + vec2(0.0, step_uv.y), backdrop_input) * 0.12;
    value += effect_input(uv - vec2(0.0, step_uv.y), backdrop_input) * 0.12;
    value += effect_input(uv + step_uv * 0.707, backdrop_input) * 0.08;
    value += effect_input(uv - step_uv * 0.707, backdrop_input) * 0.08;
    value += effect_input(
        uv + vec2(step_uv.x, -step_uv.y) * 0.707,
        backdrop_input
    ) * 0.08;
    value += effect_input(
        uv + vec2(-step_uv.x, step_uv.y) * 0.707,
        backdrop_input
    ) * 0.08;
    return value;
}

float fractal_value(vec2 uv) {
    float total = 0.0;
    float weight = 0.0;
    float frequency = 1.0;
    float amplitude = 1.0;
    float seed = u_effect_color.r * 997.0;
    for (int octave = 0; octave < 8; ++octave) {
        if (float(octave) < u_effect_values_a.z) {
            vec2 cell = floor(
                uv / max(u_texel * u_effect_values_a.y / frequency, u_texel)
            );
            float phase = u_effect_values_b.x + u_time * u_effect_values_b.y;
            total += hash21(cell + seed + floor(phase) * 7919.0) * amplitude;
            weight += amplitude;
            frequency *= 2.0;
            amplitude *= 0.5;
        }
    }
    return total / max(0.0001, weight);
}

vec4 common_effect_pixel(int backdrop_input) {
    vec2 uv = v_uv;
    if (u_effect_kind == 12) {
        float phase = u_time * u_effect_values_a.z;
        uv += vec2(
            sin(v_uv.y / max(u_texel.y * u_effect_values_a.y, u_texel.y)
                * 6.28318 + phase) * u_effect_values_a.x * u_texel.x,
            cos(v_uv.x / max(u_texel.x * u_effect_values_a.y, u_texel.x)
                * 6.28318 - phase * 0.73) * u_effect_values_a.x * u_texel.y
        );
    }
    vec4 source = effect_input(uv, backdrop_input);
    vec3 rgb = straight_rgb(source);
    if (u_effect_kind == 1) {
        rgb = (rgb - 0.5) * u_effect_values_a.y + 0.5
              + u_effect_values_a.x;
    } else if (u_effect_kind == 2) {
        float luma = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
        rgb = vec3(luma) + (rgb - vec3(luma)) * u_effect_values_a.x;
    } else if (u_effect_kind == 3) {
        return effect_blur(uv, backdrop_input, u_effect_values_a.x);
    } else if (u_effect_kind == 4) {
        vec4 soft = effect_blur(uv, backdrop_input, u_effect_values_a.x);
        rgb += (rgb - straight_rgb(soft)) * u_effect_values_a.y;
    } else if (u_effect_kind == 5) {
        vec4 soft = effect_blur(uv, backdrop_input, u_effect_values_a.y);
        vec3 halo = straight_rgb(soft);
        float selected = step(
            u_effect_values_a.x,
            max(halo.r, max(halo.g, halo.b))
        );
        rgb += halo * selected * u_effect_values_a.z;
    } else if (u_effect_kind == 6) {
        vec2 centered = v_uv * 2.0 - 1.0;
        float radius = length(centered);
        float softness = max(0.05, u_effect_values_a.y);
        float shade = 1.0 - u_effect_values_a.x * smoothstep(
            1.0 - softness,
            1.0,
            radius
        );
        rgb *= shade;
    } else if (u_effect_kind == 7) {
        vec2 offset = vec2(
            u_effect_values_a.x * u_texel.x,
            u_effect_values_a.y * u_texel.y
        );
        float shadow = effect_blur(
            v_uv - offset,
            backdrop_input,
            u_effect_values_a.z
        ).a * u_effect_values_a.w;
        vec4 behind = vec4(
            u_effect_color.rgb * shadow,
            shadow
        );
        return source_over_color(behind, rgb, source.a);
    } else if (u_effect_kind == 8) {
        float angle = radians(u_effect_values_a.z);
        vec2 delta = v_uv - u_effect_values_a.xy;
        float distance = abs(
            delta.x * cos(angle) + delta.y * sin(angle)
        );
        float width = max(0.005, u_effect_values_a.w);
        float inner = width * max(0.0, 1.0 - u_effect_values_b.x);
        float sweep = 1.0 - smoothstep(inner, width, distance);
        rgb += u_effect_color.rgb * sweep * u_effect_values_b.y;
    } else if (u_effect_kind == 9) {
        float noise = clamp(
            (fractal_value(v_uv) - 0.5) * u_effect_values_a.w + 0.5,
            0.0,
            1.0
        );
        rgb = mix(rgb, vec3(noise), u_effect_values_a.x);
    } else if (u_effect_kind == 10) {
        float levels = max(2.0, u_effect_values_a.x);
        vec3 quantized = floor(rgb * (levels - 1.0) + 0.5)
                         / (levels - 1.0);
        rgb = mix(rgb, quantized, u_effect_values_a.y);
    } else if (u_effect_kind == 11) {
        vec4 accumulated = vec4(0.0);
        float angle = radians(u_effect_values_a.y);
        vec2 vector = vec2(cos(angle), sin(angle))
                      * u_effect_values_a.x * u_texel;
        int samples = int(clamp(u_effect_values_a.z, 2.0, 32.0));
        for (int index = 0; index < 32; ++index) {
            if (index < samples) {
                float phase = float(index) / max(1.0, float(samples - 1))
                              - 0.5;
                accumulated += effect_input(
                    v_uv - vector * phase,
                    backdrop_input
                );
            }
        }
        return accumulated / float(samples);
    }
    return vec4(clamp(rgb, 0.0, 1.0) * source.a, source.a);
}

vec4 craft_pixel() {
    float t = u_time;
    vec2 weave = vec2(
        sin(t * 5.0265 + u_seed) * u_weave_x,
        sin(t * 3.669 + u_seed * 1.7) * u_weave_y
    ) * u_texel * u_amount;
    vec2 uv = v_uv - weave;
    vec4 source = source_pixel(uv);
    float alpha = source.a;
    vec3 rgb = straight_rgb(source);
    float flicker = (hash21(vec2(floor(t * 12.0), u_seed)) * 2.0 - 1.0)
                    * u_flicker * u_amount;
    rgb *= vec3(
        1.0 + flicker * (1.0 + u_warmth),
        1.0 + flicker,
        1.0 + flicker * (1.0 - u_warmth)
    );
    vec2 grain_cell = floor(v_uv / max(u_texel * u_grain_size, u_texel));
    float grain = (hash21(grain_cell + floor(t * 12.0)) * 2.0 - 1.0);
    float luma = dot(rgb, vec3(0.2126, 0.7152, 0.0722));
    float response = 0.4 + 0.6 * (1.0 - abs(luma * 2.0 - 1.0));
    rgb += grain * u_grain * response * 0.18 * u_amount;
    float shift = u_misregistration * u_amount;
    if (shift > 0.001) {
        rgb.r = straight_rgb(source_pixel(uv + vec2(shift * u_texel.x, 0.0))).r;
        rgb.b = straight_rgb(source_pixel(uv - vec2(shift * u_texel.x, 0.0))).b;
    }
    float dust_hash = hash21(floor(v_uv * vec2(311.0, 197.0))
                             + floor(t / 0.35) + u_seed);
    float dust = step(1.0 - u_dust * 0.12, dust_hash) * u_amount;
    float scratch_x = hash21(vec2(floor(v_uv.x * 600.0), floor(t * 3.0) + u_seed));
    float scratch = step(1.0 - u_scratch * 0.22, scratch_x)
                    * step(0.08, v_uv.y) * step(v_uv.y, 0.92) * u_amount;
    rgb = mix(rgb, vec3(step(0.45, dust_hash)), clamp(dust + scratch, 0.0, 0.55));
    float scan = sin((v_uv.y + t * 0.08) * 900.0) * u_vhs * 0.035 * u_amount;
    rgb += scan;
    rgb *= vec3(1.0 + u_warmth * 0.08, 1.0, 1.0 - u_warmth * 0.06);
    return over_backdrop(rgb, alpha);
}

vec4 painterly_pixel() {
    vec4 source = source_pixel(v_uv);
    float alpha = source.a;
    vec3 center = straight_rgb(source);
    vec2 px = u_texel * (1.0 + u_smoothing * 2.0);
    vec3 smooth = center * 0.36;
    smooth += straight_rgb(source_pixel(v_uv + vec2(px.x, 0.0))) * 0.12;
    smooth += straight_rgb(source_pixel(v_uv - vec2(px.x, 0.0))) * 0.12;
    smooth += straight_rgb(source_pixel(v_uv + vec2(0.0, px.y))) * 0.12;
    smooth += straight_rgb(source_pixel(v_uv - vec2(0.0, px.y))) * 0.12;
    smooth += straight_rgb(source_pixel(v_uv + px)) * 0.04;
    smooth += straight_rgb(source_pixel(v_uv - px)) * 0.04;
    smooth += straight_rgb(source_pixel(v_uv + vec2(px.x, -px.y))) * 0.04;
    smooth += straight_rgb(source_pixel(v_uv + vec2(-px.x, px.y))) * 0.04;
    vec3 rgb = mix(center, smooth, u_smoothing);
    float levels = max(2.0, u_color_levels);
    vec3 quantized = floor(rgb * (levels - 1.0) + 0.5) / (levels - 1.0);
    rgb = mix(rgb, quantized, u_toon);
    float left = dot(straight_rgb(source_pixel(v_uv - vec2(px.x, 0.0))),
                     vec3(0.2126, 0.7152, 0.0722));
    float right = dot(straight_rgb(source_pixel(v_uv + vec2(px.x, 0.0))),
                      vec3(0.2126, 0.7152, 0.0722));
    float up = dot(straight_rgb(source_pixel(v_uv - vec2(0.0, px.y))),
                   vec3(0.2126, 0.7152, 0.0722));
    float down = dot(straight_rgb(source_pixel(v_uv + vec2(0.0, px.y))),
                     vec3(0.2126, 0.7152, 0.0722));
    float edge = smoothstep(u_edge_threshold, u_edge_threshold + 0.08,
                            length(vec2(right - left, down - up)));
    rgb = mix(rgb, u_line_color.rgb, edge * u_edge_strength);
    float brush = sin(
        (v_uv.x * 0.83 + v_uv.y * 0.37)
        * max(2.0, u_brush_scale) * 6.28318 + u_seed
    );
    float paper = hash21(floor(v_uv * vec2(640.0, 360.0) / 3.0) + u_seed) - 0.5;
    rgb *= 1.0 + brush * u_brush_amount * 0.055
               + paper * u_granulation * 0.12;
    rgb = mix(rgb, u_paper_color.rgb,
              clamp((paper + 0.5) * u_paper_amount * 0.18, 0.0, 0.3));
    float hatch = step(
        0.82,
        sin((v_uv.x + v_uv.y) * max(2.0, u_hatch_spacing) * 18.0)
    ) * step(dot(rgb, vec3(0.2126, 0.7152, 0.0722)), 0.52);
    rgb = mix(rgb, u_line_color.rgb, hatch * u_hatch_amount * 0.45);
    return over_backdrop(mix(center, rgb, u_amount), alpha);
}

void main() {
    if (u_mode == 0) {
        gl_FragColor = backdrop(v_uv);
        return;
    }
    if (u_mode == 2) {
        gl_FragColor = craft_pixel();
        return;
    }
    if (u_mode == 3) {
        gl_FragColor = painterly_pixel();
        return;
    }
    if (u_mode == 4) {
        vec4 source = source_pixel(v_uv);
        gl_FragColor = source_over_color(
            shadowed_backdrop(),
            straight_rgb(source),
            source.a
        );
        return;
    }
    if (u_mode == 5) {
        vec4 effected = common_effect_pixel(0);
        gl_FragColor = source_over_color(
            shadowed_backdrop(),
            straight_rgb(effected),
            effected.a
        );
        return;
    }
    if (u_mode == 6) {
        gl_FragColor = common_effect_pixel(1);
        return;
    }
    vec4 original = backdrop(v_uv);
    float mask = source_pixel(v_uv).a * u_opacity;
    vec2 wave = vec2(
        sin(v_uv.y * 6.2831853 * u_normal_scale + u_time * 1.7 + u_driver.y),
        cos(v_uv.x * 6.2831853 * u_normal_scale - u_time * 1.3 + u_driver.x)
    );
    vec2 refracted_uv = v_uv + wave * u_refraction * u_texel;
    vec4 glass = blurred(refracted_uv);
    if (u_dispersion > 0.001) {
        vec2 chroma = normalize(wave + vec2(0.001)) * u_dispersion * u_texel;
        glass.r = backdrop(refracted_uv + chroma).r;
        glass.b = backdrop(refracted_uv - chroma).b;
    }
    glass.rgb = mix(
        glass.rgb,
        glass.rgb * u_tint.rgb,
        clamp(u_tint_strength + u_absorption * 0.35, 0.0, 1.0)
    );
    float neighbor = min(
        min(source_pixel(v_uv + vec2(u_texel.x, 0.0)).a,
            source_pixel(v_uv - vec2(u_texel.x, 0.0)).a),
        min(source_pixel(v_uv + vec2(0.0, u_texel.y)).a,
            source_pixel(v_uv - vec2(0.0, u_texel.y)).a)
    );
    float edge = clamp(mask - neighbor, 0.0, 1.0);
    float sheen = pow(
        clamp(0.5 + 0.5 * sin(
            v_uv.x * 3.1415926 + v_uv.y * 0.7 + u_time * 1.2
            + u_driver.x * 0.08 - u_driver.y * 0.06
        ), 0.0, 1.0),
        5.0
    );
    glass.rgb += u_tint.rgb * (
        edge * u_edge * (0.28 + u_thickness * 0.22)
        + sheen * u_specular * 0.16
        + sheen * u_bloom * 0.12
    );
    glass.a = original.a;
    gl_FragColor = mix(original, glass, clamp(mask, 0.0, 1.0));
}
"""

MAX_GLASS_PREVIEW_LONG_EDGE = 960
_GPU_BLEND_MODES = {
    "normal": 0,
    "multiply": 1,
    "screen": 2,
    "add": 3,
    "overlay": 4,
}
_GPU_MATTE_MODES = {
    "alpha": 1,
    "luma": 2,
    "alpha_inverted": 3,
    "luma_inverted": 4,
}


def _gpu_effects_by_target(graph: RenderGraph) -> dict[str, list]:
    effects: dict[str, list] = {}
    for group in graph.effect_groups:
        for layer_id in group.target_layer_ids:
            effects.setdefault(layer_id, []).extend(
                effect for effect in group.effects if effect.enabled
            )
    lower_ids: set[str] = set()
    for node in graph.nodes:
        if node.layer_type == "adjustment":
            if node.adjustment_scope_mode == "selected_layers_below":
                active = [
                    effect for effect in node.effects or () if effect.enabled
                ]
                for layer_id in node.adjustment_target_layer_ids:
                    if layer_id in lower_ids:
                        effects.setdefault(layer_id, []).extend(active)
            continue
        if node.layer_type not in {"group", "null", "camera", "light"}:
            lower_ids.add(node.layer_id)
    return effects


def _effective_gpu_effects(
    node: RenderNode,
    targeted: dict[str, list],
) -> list:
    return [
        effect for effect in node.effects or () if effect.enabled
    ] + list(targeted.get(node.layer_id, ()))


def _effect_value(effect, name: str, time_ms: float, default: float) -> float:
    prop = effect.params.get(name)
    try:
        return float(evaluate_property(prop, time_ms)) if prop is not None else default
    except (TypeError, ValueError):
        return default


class MotionGlassGpuRenderer:
    def __init__(self, parent=None) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._quad_vao = 0
        self._quad_vbo = 0
        self._framebuffers: list[QOpenGLFramebufferObject] = []
        self._framebuffer_size = (0, 0)
        self.last_diagnostics: dict[str, object] = {
            "backend": "qt_painter_fallback",
            "reason": "not_drawn",
        }

    @staticmethod
    def can_draw(graph: RenderGraph) -> tuple[bool, str]:
        if GL is None:
            return False, "pyopengl_unavailable"
        receiver_count = sum(1 for node in graph.nodes if node.receive_shadows)
        if receiver_count > 1 and any(node.cast_shadows for node in graph.nodes):
            return False, "multi_receiver_card_shadow_requires_raster"
        targeted_effects = _gpu_effects_by_target(graph)
        gpu_effect_count = 0
        for node in graph.nodes:
            if node.layer_type in {"group", "null", "camera", "light"}:
                continue
            active_effects = _effective_gpu_effects(node, targeted_effects)
            if node.layer_type == "adjustment":
                if node.adjustment_scope_mode == "selected_layers_below":
                    continue
                if not active_effects:
                    continue
                if len(active_effects) > 1:
                    return False, "stacked_adjustment_effects_require_raster"
                if not is_common_gpu_effect(active_effects[0]):
                    return False, unsupported_gpu_effect_reason(active_effects[0])
                gpu_effect_count += 1
                continue
            effect = glass_effect(active_effects)
            gpu_motion_blur = (
                node.motion_blur_samples > 1
                and (
                    abs(node.motion_blur_vector[0]) > 0.05
                    or abs(node.motion_blur_vector[1]) > 0.05
                )
            )
            if effect is not None:
                gpu_effect_count += 1
                if any(
                    item.enabled and item.kind.strip().lower() != "tiger_glass"
                    for item in active_effects
                ):
                    return False, "glass_layer_has_additional_effects"
            else:
                if active_effects:
                    if len(active_effects) > 1:
                        return False, "stacked_effects_require_raster"
                    style_effect = active_effects[0]
                    if is_common_gpu_effect(style_effect):
                        gpu_effect_count += 1
                    elif (
                        is_craft_style_effect(style_effect)
                        and isinstance(style_effect.metadata.get("texture"), dict)
                    ):
                        return False, "craft_texture_requires_raster"
                    elif is_painterly_look_effect(style_effect):
                        if isinstance(
                            style_effect.metadata.get("projected_texture"),
                            dict,
                        ):
                            return False, "painterly_texture_requires_raster"
                        overrides = style_effect.metadata.get(
                            "material_overrides"
                        )
                        if isinstance(overrides, dict) and overrides:
                            return False, "material_id_pass_unavailable"
                        gpu_effect_count += 1
                    elif is_craft_style_effect(style_effect):
                        gpu_effect_count += 1
                    else:
                        return False, unsupported_gpu_effect_reason(style_effect)
                elif gpu_motion_blur:
                    gpu_effect_count += 1
            if node.matte_layer_id:
                matte_mode = node.matte_mode.strip().lower()
                if node.matte_inverted and not matte_mode.endswith("_inverted"):
                    matte_mode = f"{matte_mode}_inverted"
                if matte_mode not in _GPU_MATTE_MODES:
                    return False, f"track_matte_mode:{matte_mode}"
                gpu_effect_count += 1
            if node.cast_shadows:
                if effect is not None:
                    return False, "glass_card_shadow_requires_raster"
                gpu_effect_count += 1
            if effect is not None and node.blend_mode != "normal":
                return False, "glass_blend_mode_requires_raster"
            if node.blend_mode not in _GPU_BLEND_MODES:
                return False, f"blend_mode:{node.blend_mode}"
        if gpu_effect_count == 0:
            return False, "gpu_effect_missing"
        return True, ""

    def _ensure_resources(self) -> bool:
        if GL is None:
            return False
        if self._program is not None:
            return True
        program = QOpenGLShaderProgram(self._parent)
        vertex_ok = program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex,
            _VERTEX_SHADER,
        )
        fragment_ok = program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment,
            _FRAGMENT_SHADER,
        )
        program.bindAttributeLocation("a_position", 0)
        program.bindAttributeLocation("a_uv", 1)
        if not vertex_ok or not fragment_ok or not program.link():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "glass_shader_compile_failed",
                "shader_log": program.log(),
            }
            return False
        vertices = np.asarray([
            0.0, 0.0, 0.0, 0.0,
            1.0, 0.0, 1.0, 0.0,
            1.0, 1.0, 1.0, 1.0,
            0.0, 0.0, 0.0, 0.0,
            1.0, 1.0, 1.0, 1.0,
            0.0, 1.0, 0.0, 1.0,
        ], dtype=np.float32)
        vao = int(GL.glGenVertexArrays(1))
        vbo = int(GL.glGenBuffers(1))
        if not vao or not vbo:
            return False
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, int(vertices.nbytes), vertices, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, False, 4 * 4, ctypes.c_void_p(0))
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, False, 4 * 4, ctypes.c_void_p(2 * 4))
        GL.glBindVertexArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        self._program = program
        self._quad_vao = vao
        self._quad_vbo = vbo
        return True

    def _set_uniform(self, name: str, value) -> None:
        if self._program is None:
            return
        location = self._program.uniformLocation(name)
        if location < 0:
            return
        if isinstance(value, QVector2D):
            GL.glUniform2f(location, value.x(), value.y())
        elif isinstance(value, QVector4D):
            GL.glUniform4f(location, value.x(), value.y(), value.z(), value.w())
        elif isinstance(value, int):
            GL.glUniform1i(location, value)
        else:
            GL.glUniform1f(location, float(value))

    @staticmethod
    def _image_texture(image: QImage) -> QOpenGLTexture | None:
        texture = QOpenGLTexture(
            image.convertToFormat(QImage.Format_RGBA8888_Premultiplied),
            QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps,
        )
        if not texture.isCreated():
            return None
        texture.setMinMagFilters(
            QOpenGLTexture.Filter.Linear,
            QOpenGLTexture.Filter.Linear,
        )
        texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
        return texture

    def _draw_quad(self) -> None:
        GL.glBindVertexArray(self._quad_vao)
        GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
        GL.glBindVertexArray(0)

    def _ensure_framebuffers(
        self,
        size: tuple[int, int],
    ) -> list[QOpenGLFramebufferObject]:
        if (
            self._framebuffer_size == size
            and len(self._framebuffers) == 2
            and all(framebuffer.isValid() for framebuffer in self._framebuffers)
        ):
            return self._framebuffers
        self._framebuffers.clear()
        framebuffer_format = QOpenGLFramebufferObjectFormat()
        framebuffer_format.setAttachment(
            QOpenGLFramebufferObject.Attachment.NoAttachment
        )
        framebuffer_format.setTextureTarget(GL.GL_TEXTURE_2D)
        framebuffer_format.setInternalTextureFormat(GL.GL_RGBA8)
        self._framebuffers = [
            QOpenGLFramebufferObject(size[0], size[1], framebuffer_format)
            for _index in range(2)
        ]
        self._framebuffer_size = size
        return self._framebuffers

    @staticmethod
    def _working_size(
        target: QRectF,
        *,
        max_long_edge: int = MAX_GLASS_PREVIEW_LONG_EDGE,
    ) -> tuple[int, int]:
        width = max(1, int(round(target.width())))
        height = max(1, int(round(target.height())))
        longest = max(width, height)
        if longest <= max_long_edge:
            return width, height
        scale = max_long_edge / float(longest)
        return (
            max(1, int(round(width * scale))),
            max(1, int(round(height * scale))),
        )

    def draw(
        self,
        gl,
        graph: RenderGraph,
        *,
        widget_width: int,
        widget_height: int,
        target: QRectF,
        max_working_edge: int = MAX_GLASS_PREVIEW_LONG_EDGE,
        transparent_output: bool = False,
    ) -> bool:
        eligible, reason = self.can_draw(graph)
        if not eligible:
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": reason,
            }
            return False
        if not self._ensure_resources() or self._program is None:
            return False
        for _index in range(8):
            if GL.glGetError() == GL.GL_NO_ERROR:
                break
        raster_started = time.perf_counter()
        raster_size = self._working_size(
            target,
            max_long_edge=max(1, int(max_working_edge)),
        )
        stages: list[
            tuple[
                str,
                RenderNode | None,
                QImage,
                QImage | None,
                QImage | None,
            ]
        ] = []
        node_by_id = {node.layer_id: node for node in graph.nodes}
        matte_ids = {
            node.matte_layer_id for node in graph.nodes if node.matte_layer_id
        }
        targeted_effects = _gpu_effects_by_target(graph)
        raster_nodes = []
        active_shadow_receiver: RenderNode | None = None
        shadow_receiver_by_caster: dict[str, RenderNode] = {}
        for node in graph.nodes:
            if node.layer_id in matte_ids:
                continue
            if node.layer_type == "adjustment":
                if node.adjustment_scope_mode == "selected_layers_below":
                    continue
                adjustment_effects = _effective_gpu_effects(
                    node,
                    targeted_effects,
                )
                if not adjustment_effects:
                    continue
                if raster_nodes:
                    stages.append((
                        "raster",
                        None,
                        render_graph_image(
                            replace(
                                graph,
                                nodes=list(raster_nodes),
                                effect_groups=[],
                            ),
                            output_size=raster_size,
                        ),
                        None,
                        None,
                    ))
                    raster_nodes.clear()
                empty = QImage(
                    raster_size[0],
                    raster_size[1],
                    QImage.Format_RGBA8888_Premultiplied,
                )
                empty.fill(0)
                stages.append((
                    "adjustment",
                    replace(node, effects=adjustment_effects),
                    empty,
                    None,
                    None,
                ))
                continue
            if node.layer_type in {"group", "null", "camera", "light"}:
                continue
            effective_effects = _effective_gpu_effects(
                node,
                targeted_effects,
            )
            effective_node = replace(node, effects=effective_effects)
            receiver_for_shadow = active_shadow_receiver
            effect = glass_effect(effective_effects)
            style_effect = next(
                (
                    item for item in effective_effects
                    if item.enabled and (
                        is_craft_style_effect(item)
                        or is_painterly_look_effect(item)
                    )
                ),
                None,
            )
            common_effect = next(
                (
                    item for item in effective_effects
                    if is_common_gpu_effect(item)
                ),
                None,
            )
            gpu_motion_blur = (
                node.motion_blur_samples > 1
                and (
                    abs(node.motion_blur_vector[0]) > 0.05
                    or abs(node.motion_blur_vector[1]) > 0.05
                )
            )
            if (
                effect is None
                and style_effect is None
                and common_effect is None
                and not gpu_motion_blur
            ):
                raster_nodes.append(effective_node)
                if node.receive_shadows:
                    active_shadow_receiver = node
                continue
            if raster_nodes:
                stages.append((
                    "raster",
                    None,
                    render_graph_image(
                        replace(
                            graph,
                            nodes=list(raster_nodes),
                            effect_groups=[],
                        ),
                        output_size=raster_size,
                    ),
                    None,
                    None,
                ))
                raster_nodes.clear()
            matte_node = node_by_id.get(node.matte_layer_id)
            matte_image = (
                render_graph_image(
                    replace(
                        graph,
                        nodes=[
                            replace(
                                matte_node,
                                matte_layer_id="",
                                matte_mode="alpha",
                                matte_inverted=False,
                                blend_mode="normal",
                            )
                        ],
                        effect_groups=[],
                    ),
                    output_size=raster_size,
                )
                if matte_node is not None
                else None
            )
            shadow_receiver_image = (
                render_graph_image(
                    replace(
                        graph,
                        nodes=[
                            replace(
                                receiver_for_shadow,
                                cast_shadows=False,
                                receive_shadows=False,
                                blend_mode="normal",
                            )
                        ],
                        effect_groups=[],
                    ),
                    output_size=raster_size,
                )
                if node.cast_shadows and receiver_for_shadow is not None
                else None
            )
            if node.cast_shadows and receiver_for_shadow is not None:
                shadow_receiver_by_caster[node.layer_id] = receiver_for_shadow
            stages.append((
                (
                    "glass"
                    if effect is not None
                    else "style"
                    if style_effect is not None
                    else "effect"
                    if common_effect is not None
                    else "motion"
                ),
                effective_node,
                render_graph_image(
                    replace(
                        graph,
                        nodes=[
                            replace(
                                effective_node,
                                effects=[],
                                motion_blur_samples=1,
                                motion_blur_vector=(0.0, 0.0),
                                blend_mode="normal",
                            )
                        ],
                        effect_groups=[],
                    ),
                    output_size=raster_size,
                ),
                matte_image,
                shadow_receiver_image,
            ))
            if node.receive_shadows:
                active_shadow_receiver = node
        if raster_nodes:
            stages.append((
                "raster",
                None,
                render_graph_image(
                    replace(
                        graph,
                        nodes=list(raster_nodes),
                        effect_groups=[],
                    ),
                    output_size=raster_size,
                ),
                None,
                None,
            ))
        raster_ms = (time.perf_counter() - raster_started) * 1000.0
        stage_textures = [
            (
                kind,
                node,
                self._image_texture(image),
                self._image_texture(matte) if matte is not None else None,
                self._image_texture(shadow_receiver)
                if shadow_receiver is not None
                else None,
            )
            for kind, node, image, matte, shadow_receiver in stages
        ]
        if any(
            texture is None
            for _kind, _node, texture, _matte, _shadow in stage_textures
        ):
            for (
                _kind,
                _node,
                texture,
                matte_texture,
                shadow_texture,
            ) in stage_textures:
                if texture is not None:
                    texture.destroy()
                if matte_texture is not None:
                    matte_texture.destroy()
                if shadow_texture is not None:
                    shadow_texture.destroy()
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "glass_texture_upload_failed",
            }
            return False

        gpu_started = time.perf_counter()
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        default_fbo = int(GL.glGetIntegerv(GL.GL_DRAW_FRAMEBUFFER_BINDING))
        framebuffers = self._ensure_framebuffers(raster_size)
        if any(not framebuffer.isValid() for framebuffer in framebuffers):
            for (
                _kind,
                _node,
                texture,
                matte_texture,
                shadow_texture,
            ) in stage_textures:
                texture.destroy()
                if matte_texture is not None:
                    matte_texture.destroy()
                if shadow_texture is not None:
                    shadow_texture.destroy()
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "glass_framebuffer_create_failed",
            }
            return False
        current_index = 0
        framebuffers[current_index].bind()
        GL.glViewport(0, 0, raster_size[0], raster_size[1])
        GL.glDisable(GL.GL_BLEND)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if transparent_output:
            GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        else:
            GL.glClearColor(
                11.0 / 255.0,
                13.0 / 255.0,
                17.0 / 255.0,
                1.0,
            )
        if not self._program.bind():
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, default_fbo)
            for (
                _kind,
                _node,
                texture,
                matte_texture,
                shadow_texture,
            ) in stage_textures:
                texture.destroy()
                if matte_texture is not None:
                    matte_texture.destroy()
                if shadow_texture is not None:
                    shadow_texture.destroy()
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "glass_shader_bind_failed",
            }
            return False
        self._set_uniform(
            "u_widget_size",
            QVector2D(raster_size[0], raster_size[1]),
        )
        self._set_uniform(
            "u_target",
            QVector4D(0.0, 0.0, raster_size[0], raster_size[1]),
        )
        self._set_uniform("u_backdrop", 0)
        self._set_uniform("u_mask", 1)
        self._set_uniform("u_track_matte", 2)
        self._set_uniform("u_shadow_receiver", 3)

        glass_pass_count = 0
        craft_pass_count = 0
        painterly_pass_count = 0
        motion_blur_pass_count = 0
        blend_pass_count = 0
        matte_pass_count = 0
        shadow_pass_count = 0
        common_effect_pass_count = 0
        adjustment_pass_count = 0
        raster_pass_count = 0
        for (
            kind,
            stage_node,
            stage_texture,
            matte_texture,
            shadow_texture,
        ) in stage_textures:
            if kind == "raster":
                GL.glEnable(GL.GL_BLEND)
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
                self._set_uniform("u_mode", 0)
                self._set_uniform("u_matte_mode", 0)
                self._set_uniform("u_shadow_enabled", 0)
                self._set_uniform("u_backdrop_flip_y", 0)
                stage_texture.bind(0)
                self._draw_quad()
                stage_texture.release(0)
                raster_pass_count += 1
                continue
            node = stage_node
            mask_texture = stage_texture
            effect = glass_effect(node.effects)
            style_effect = next(
                (
                    item for item in node.effects or ()
                    if item.enabled and (
                        is_craft_style_effect(item)
                        or is_painterly_look_effect(item)
                    )
                ),
                None,
            )
            common_effect = next(
                (
                    item for item in node.effects or ()
                    if is_common_gpu_effect(item)
                ),
                None,
            )
            next_index = 1 - current_index
            framebuffers[next_index].bind()
            GL.glViewport(0, 0, raster_size[0], raster_size[1])
            GL.glDisable(GL.GL_BLEND)
            scale = min(
                raster_size[0] / max(1.0, graph.width),
                raster_size[1] / max(1.0, graph.height),
            )
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(
                GL.GL_TEXTURE_2D,
                int(framebuffers[current_index].texture()),
            )
            mask_texture.bind(1)
            matte_mode_name = node.matte_mode.strip().lower()
            if (
                node.matte_inverted
                and not matte_mode_name.endswith("_inverted")
            ):
                matte_mode_name = f"{matte_mode_name}_inverted"
            matte_mode = (
                _GPU_MATTE_MODES.get(matte_mode_name, 0)
                if matte_texture is not None
                else 0
            )
            self._set_uniform("u_matte_mode", matte_mode)
            if matte_texture is not None:
                matte_texture.bind(2)
                matte_pass_count += 1
            receiver_node = shadow_receiver_by_caster.get(node.layer_id)
            shadow_enabled = bool(
                shadow_texture is not None
                and receiver_node is not None
                and node.depth_z > receiver_node.depth_z
                and node.shadow_light_intensity > 0.0
                and node.shadow_strength > 0.0
            )
            self._set_uniform("u_shadow_enabled", int(shadow_enabled))
            if shadow_enabled:
                shadow_texture.bind(3)
                elevation = math.radians(max(
                    5.0,
                    min(89.0, node.shadow_light_elevation),
                ))
                distance = min(
                    float(max(raster_size)),
                    max(0.0, node.depth_z - receiver_node.depth_z)
                    * 36.0 * scale
                    / max(0.087, math.tan(elevation)),
                )
                azimuth = math.radians(node.shadow_light_azimuth)
                self._set_uniform(
                    "u_shadow_offset",
                    QVector2D(
                        -math.cos(azimuth) * distance / raster_size[0],
                        math.sin(azimuth) * distance / raster_size[1],
                    ),
                )
                self._set_uniform(
                    "u_shadow_softness",
                    max(0.0, node.shadow_softness * scale),
                )
                self._set_uniform(
                    "u_shadow_alpha",
                    node.shadow_strength
                    * max(
                        0.0,
                        min(1.0, node.shadow_light_intensity / 0.42),
                    ),
                )
                shadow_pass_count += 1
            self._set_uniform("u_backdrop_flip_y", 1)
            self._set_uniform(
                "u_texel",
                QVector2D(1.0 / raster_size[0], 1.0 / raster_size[1]),
            )
            self._set_uniform("u_time", node.local_time_ms * 0.001)
            motion_samples = max(
                1,
                min(32, int(node.motion_blur_samples)),
            )
            motion_x = float(node.motion_blur_vector[0]) / max(
                1.0,
                float(graph.width),
            )
            motion_y = float(node.motion_blur_vector[1]) / max(
                1.0,
                float(graph.height),
            )
            self._set_uniform("u_motion_samples", motion_samples)
            self._set_uniform(
                "u_motion_vector",
                QVector2D(motion_x, motion_y),
            )
            blend_mode = _GPU_BLEND_MODES.get(node.blend_mode, 0)
            self._set_uniform("u_blend_mode", blend_mode)
            if blend_mode:
                blend_pass_count += 1
            if motion_samples > 1 and (
                abs(motion_x) > 1e-6 or abs(motion_y) > 1e-6
            ):
                motion_blur_pass_count += 1
            if effect is not None:
                tint = QColor(str(effect.metadata.get("tint") or "#ffffff"))
                driver = node.glass_driver_override or (
                    _effect_value(effect, "driver_x", node.local_time_ms, 0.0),
                    _effect_value(effect, "driver_y", node.local_time_ms, 0.0),
                )
                self._set_uniform("u_mode", 1)
                self._set_uniform(
                    "u_tint",
                    QVector4D(tint.redF(), tint.greenF(), tint.blueF(), tint.alphaF()),
                )
                for uniform, key, default in (
                    ("u_blur", "blur_radius", 4.0),
                    ("u_refraction", "refraction", 3.0),
                    ("u_normal_scale", "normal_scale", 1.4),
                    ("u_thickness", "thickness", 0.45),
                    ("u_absorption", "absorption", 0.08),
                    ("u_edge", "edge_highlight", 0.35),
                    ("u_specular", "specular", 0.4),
                    ("u_dispersion", "dispersion", 0.35),
                    ("u_bloom", "bloom", 0.08),
                    ("u_tint_strength", "tint_strength", 0.05),
                ):
                    value = _effect_value(effect, key, node.local_time_ms, default)
                    if key in {"blur_radius", "refraction", "dispersion"}:
                        value *= scale
                    self._set_uniform(uniform, value)
                self._set_uniform("u_opacity", node.opacity)
                self._set_uniform("u_driver", QVector2D(*driver))
                glass_pass_count += 1
            elif (
                style_effect is not None
                and is_craft_style_effect(style_effect)
            ):
                self._set_uniform("u_mode", 2)
                for uniform, key, default in (
                    ("u_seed", "seed", 1.0),
                    ("u_amount", "amount", 1.0),
                    ("u_grain", "grain_amount", 0.1),
                    ("u_grain_size", "grain_size", 1.4),
                    ("u_flicker", "flicker_amount", 0.018),
                    ("u_warmth", "warmth", 0.06),
                    ("u_weave_x", "weave_x", 0.8),
                    ("u_weave_y", "weave_y", 0.55),
                    ("u_misregistration", "misregistration", 0.25),
                    ("u_dust", "dust_amount", 0.015),
                    ("u_scratch", "scratch_amount", 0.008),
                    ("u_vhs", "vhs_amount", 0.0),
                ):
                    self._set_uniform(
                        uniform,
                        _effect_value(style_effect, key, node.local_time_ms, default),
                    )
                craft_pass_count += 1
            elif style_effect is not None:
                self._set_uniform("u_mode", 3)
                for uniform, key, default in (
                    ("u_seed", "seed", 20260729.0),
                    ("u_amount", "amount", 1.0),
                    ("u_color_levels", "color_levels", 8.0),
                    ("u_toon", "toon_amount", 0.0),
                    ("u_smoothing", "smoothing", 0.15),
                    ("u_edge_strength", "edge_strength", 0.0),
                    ("u_edge_threshold", "edge_threshold", 0.18),
                    ("u_brush_amount", "brush_amount", 0.0),
                    ("u_brush_scale", "brush_scale", 18.0),
                    ("u_granulation", "granulation", 0.0),
                    ("u_paper_amount", "paper_amount", 0.0),
                    ("u_hatch_amount", "hatch_amount", 0.0),
                    ("u_hatch_spacing", "hatch_spacing", 9.0),
                ):
                    self._set_uniform(
                        uniform,
                        _effect_value(style_effect, key, node.local_time_ms, default),
                    )
                line = QColor(str(style_effect.metadata.get("line_color") or "#17202a"))
                paper = QColor(str(style_effect.metadata.get("paper_color") or "#f1ead9"))
                self._set_uniform(
                    "u_line_color",
                    QVector4D(line.redF(), line.greenF(), line.blueF(), line.alphaF()),
                )
                self._set_uniform(
                    "u_paper_color",
                    QVector4D(paper.redF(), paper.greenF(), paper.blueF(), paper.alphaF()),
                )
                painterly_pass_count += 1
            elif common_effect is not None:
                parameters = gpu_effect_parameters(
                    common_effect,
                    node.local_time_ms,
                    pixel_scale=scale,
                )
                self._set_uniform(
                    "u_mode",
                    6 if kind == "adjustment" else 5,
                )
                self._set_uniform("u_effect_kind", parameters.mode)
                self._set_uniform(
                    "u_effect_values_a",
                    QVector4D(*parameters.values[:4]),
                )
                self._set_uniform(
                    "u_effect_values_b",
                    QVector2D(*parameters.values[4:]),
                )
                self._set_uniform(
                    "u_effect_color",
                    QVector4D(
                        parameters.color.redF(),
                        parameters.color.greenF(),
                        parameters.color.blueF(),
                        parameters.color.alphaF(),
                    ),
                )
                common_effect_pass_count += 1
                if kind == "adjustment":
                    adjustment_pass_count += 1
            else:
                self._set_uniform("u_mode", 4)
            self._draw_quad()
            if matte_texture is not None:
                matte_texture.release(2)
            if shadow_enabled:
                shadow_texture.release(3)
            mask_texture.release(1)
            current_index = next_index

        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, default_fbo)
        GL.glViewport(0, 0, widget_width, widget_height)
        GL.glDisable(GL.GL_BLEND)
        GL.glClearColor(11.0 / 255.0, 13.0 / 255.0, 17.0 / 255.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        self._set_uniform("u_widget_size", QVector2D(widget_width, widget_height))
        self._set_uniform(
            "u_target",
            QVector4D(target.x(), target.y(), target.width(), target.height()),
        )
        self._set_uniform("u_mode", 0)
        self._set_uniform("u_backdrop_flip_y", 1)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(
            GL.GL_TEXTURE_2D,
            int(framebuffers[current_index].texture()),
        )
        self._draw_quad()
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self._program.release()
        for (
            _kind,
            _node,
            texture,
            matte_texture,
            shadow_texture,
        ) in stage_textures:
            texture.destroy()
            if matte_texture is not None:
                matte_texture.destroy()
            if shadow_texture is not None:
                shadow_texture.destroy()
        gl_error = int(GL.glGetError())
        gpu_ms = (time.perf_counter() - gpu_started) * 1000.0
        backend = (
            "motion_glass_gpu"
            if glass_pass_count and not craft_pass_count and not painterly_pass_count
            and not common_effect_pass_count
            else "motion_style_gpu"
            if craft_pass_count or painterly_pass_count
            else "motion_compositor_gpu"
        )
        self.last_diagnostics = {
            "backend": backend,
            "reason": "",
            "glass_pass_count": glass_pass_count,
            "craft_pass_count": craft_pass_count,
            "painterly_pass_count": painterly_pass_count,
            "motion_blur_pass_count": motion_blur_pass_count,
            "blend_pass_count": blend_pass_count,
            "matte_pass_count": matte_pass_count,
            "shadow_pass_count": shadow_pass_count,
            "common_effect_pass_count": common_effect_pass_count,
            "adjustment_pass_count": adjustment_pass_count,
            "raster_segment_count": raster_pass_count,
            "precomp_source_raster_count": sum(
                1 for node in graph.nodes if node.layer_type == "precomp"
            ),
            "base_cpu_raster_ms": raster_ms,
            "gpu_submit_ms": gpu_ms,
            "viewport_width": raster_size[0],
            "viewport_height": raster_size[1],
            "backdrop_shader": True,
            "framebuffer_feedback": True,
            "gl_error": gl_error,
        }
        if gl_error:
            self.last_diagnostics.update({
                "backend": "qt_painter_fallback",
                "reason": f"gl_error:{gl_error}",
            })
            return False
        return True

    def clear(self) -> None:
        self._framebuffers.clear()
        self._framebuffer_size = (0, 0)
        if GL is not None:
            if self._quad_vbo:
                GL.glDeleteBuffers(1, [self._quad_vbo])
            if self._quad_vao:
                GL.glDeleteVertexArrays(1, [self._quad_vao])
        self._quad_vbo = 0
        self._quad_vao = 0
        if self._program is not None:
            self._program.removeAllShaders()
            self._program = None


__all__ = ["MAX_GLASS_PREVIEW_LONG_EDGE", "MotionGlassGpuRenderer"]
