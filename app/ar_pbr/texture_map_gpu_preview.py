"""Offscreen OpenGL preview compositor for Texture Lab maps."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
from PIL import Image
from PySide6.QtGui import QGuiApplication, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

from app.ar_pbr.texture_map_lab import (
    PACKED_LAYOUTS,
    SCHEMA_ID,
    TextureMapGpuRequiredError,
    _normalize_preview_shape,
    normalize_texture_map_settings,
    substrate_export_plan,
)


_MODE_CODES: dict[str, int] = {
    "material": 0,
    "base_color_source": 1,
    "base_color": 2,
    "albedo": 2,
    "normal": 3,
    "ao": 4,
    "roughness": 5,
    "metallic": 6,
    "height": 7,
    "cavity": 8,
    "curvature": 9,
    "f0": 10,
    "f90_mask": 11,
    "unreal_orm": 12,
    "orm": 12,
    "arm": 13,
    "rma": 14,
    "gltf_mr": 15,
    "irradiance": 16,
    "delight_shading": 17,
    "intrinsic_channels": 18,
    "delight_compare": 19,
}

_TEXTURE_NAMES: tuple[str, ...] = (
    "base_color_source",
    "base_color",
    "normal",
    "ao",
    "roughness",
    "metallic",
    "height",
    "cavity",
    "curvature",
    "f0",
    "f90_mask",
    "irradiance",
    "delight_shading",
)

_VERTEX_SHADER = """
#version 120
varying vec2 v_uv;
void main() {
    v_uv = gl_MultiTexCoord0.xy;
    gl_Position = gl_Vertex;
}
"""

_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
uniform sampler2D u_base_source;
uniform sampler2D u_base;
uniform sampler2D u_normal;
uniform sampler2D u_ao;
uniform sampler2D u_roughness;
uniform sampler2D u_metallic;
uniform sampler2D u_height;
uniform sampler2D u_cavity;
uniform sampler2D u_curvature;
uniform sampler2D u_f0;
uniform sampler2D u_f90;
uniform sampler2D u_irradiance;
uniform sampler2D u_delight_shading;
uniform int u_mode;
uniform int u_shape;
uniform vec3 u_light;
uniform float u_environment;

vec3 srgb_to_linear(vec3 c) {
    return pow(max(c, vec3(0.0)), vec3(2.2));
}

vec3 linear_to_srgb(vec3 c) {
    return pow(max(c, vec3(0.0)), vec3(1.0 / 2.2));
}

float scalar_sample(sampler2D tex, vec2 uv) {
    return texture2D(tex, clamp(uv, vec2(0.0), vec2(1.0))).r;
}

vec3 normal_sample(vec2 uv) {
    vec3 n = texture2D(u_normal, clamp(uv, vec2(0.0), vec2(1.0))).rgb * 2.0 - 1.0;
    n.y = -n.y;
    return normalize(vec3(n.xy * 0.65, max(0.18, n.z)));
}

vec2 sphere_uv(vec3 n) {
    const float PI = 3.14159265358979323846;
    float u = atan(n.x, n.z) / (2.0 * PI) + 0.5;
    float v = asin(clamp(n.y, -1.0, 1.0)) / PI + 0.5;
    return vec2(fract(u), clamp(v, 0.0, 1.0));
}

vec3 sphere_tangent_normal(vec3 sphere_n, vec3 tangent_normal) {
    vec3 tangent = vec3(sphere_n.z, 0.0, -sphere_n.x);
    if (dot(tangent, tangent) < 0.0001) {
        tangent = vec3(1.0, 0.0, 0.0);
    } else {
        tangent = normalize(tangent);
    }
    vec3 bitangent = normalize(cross(sphere_n, tangent));
    return normalize(
        tangent * tangent_normal.x
        + bitangent * tangent_normal.y
        + sphere_n * tangent_normal.z
    );
}

vec3 packed_sample(vec2 uv, int code) {
    float ao = scalar_sample(u_ao, uv);
    float roughness = scalar_sample(u_roughness, uv);
    float metallic = scalar_sample(u_metallic, uv);
    if (code == 12) {
        return vec3(ao, roughness, metallic);
    }
    if (code == 13) {
        return vec3(ao, roughness, metallic);
    }
    if (code == 14) {
        return vec3(roughness, metallic, ao);
    }
    return vec3(0.0, roughness, metallic);
}

vec3 material_sample(vec2 uv, vec3 surface_normal) {
    vec3 base = srgb_to_linear(texture2D(u_base, clamp(uv, vec2(0.0), vec2(1.0))).rgb);
    float ao = scalar_sample(u_ao, uv);
    float roughness = clamp(scalar_sample(u_roughness, uv), 0.03, 1.0);
    float metallic = clamp(scalar_sample(u_metallic, uv), 0.0, 1.0);
    vec3 key_l = normalize(u_light);
    vec3 fill_l = normalize(vec3(0.68, 0.36, 0.64));
    vec3 v = normalize(vec3(0.0, 0.0, 1.0));
    vec3 key_h = normalize(key_l + v);
    vec3 fill_h = normalize(fill_l + v);
    float key_ndotl = max(dot(surface_normal, key_l), 0.0);
    float fill_ndotl = max(dot(surface_normal, fill_l), 0.0);
    float key_ndoth = max(dot(surface_normal, key_h), 0.0);
    float fill_ndoth = max(dot(surface_normal, fill_h), 0.0);
    float ndotv = max(dot(surface_normal, v), 0.0);
    float spec_power = mix(96.0, 10.0, roughness);
    vec3 f0 = mix(vec3(0.04), base, metallic);
    float key_spec = pow(key_ndoth, spec_power) * (1.0 - roughness * 0.55);
    float fill_spec = pow(fill_ndoth, spec_power) * (1.0 - roughness * 0.70) * 0.18;
    float ambient = max(0.015, u_environment * 0.55);
    float diffuse_light = ambient + key_ndotl * 0.92 + fill_ndotl * 0.20;
    vec3 diffuse = base * diffuse_light * (1.0 - metallic * 0.72) * mix(0.45, 1.0, ao);
    vec3 specular = f0 * (key_spec + fill_spec) * mix(0.55, 1.0, ao);
    float rim = pow(1.0 - ndotv, 3.0) * 0.10;
    vec3 color = diffuse + specular + base * rim;
    return linear_to_srgb(color);
}

vec3 panel_sample(int panel, vec2 uv) {
    if (u_mode == 18) {
        if (panel == 0) return texture2D(u_base_source, uv).rgb;
        if (panel == 1) return texture2D(u_base, uv).rgb;
        if (panel == 2) return texture2D(u_normal, uv).rgb;
        if (panel == 3) return vec3(scalar_sample(u_roughness, uv));
        return texture2D(u_irradiance, uv).rgb;
    }
    if (u_mode == 19) {
        vec3 source = texture2D(u_base_source, uv).rgb;
        vec3 base = texture2D(u_base, uv).rgb;
        if (panel == 0) return source;
        if (panel == 1) return base;
        return clamp(abs(source - base) * 4.0, 0.0, 1.0);
    }
    return vec3(0.0);
}

void main() {
    vec2 uv = clamp(v_uv, vec2(0.0), vec2(1.0));
    if (u_mode == 18 || u_mode == 19) {
        float count = u_mode == 18 ? 5.0 : 3.0;
        int panel = int(floor(clamp(uv.x * count, 0.0, count - 0.001)));
        vec2 panel_uv = vec2(fract(uv.x * count), uv.y);
        vec3 row = panel_sample(panel, panel_uv);
        float separator = step(fract(uv.x * count), 0.012);
        gl_FragColor = vec4(mix(row, vec3(0.02), separator), 1.0);
        return;
    }

    vec2 material_uv = uv;
    vec3 sphere_n = vec3(0.0, 0.0, 1.0);
    if (u_shape == 1) {
        vec2 p = uv * 2.0 - 1.0;
        float r2 = dot(p, p);
        if (r2 > 1.0) {
            float vignette = smoothstep(1.6, 0.15, length(p));
            gl_FragColor = vec4(vec3(0.035, 0.038, 0.046) * (0.65 + vignette * 0.35), 1.0);
            return;
        }
        sphere_n = normalize(vec3(p.x, p.y, sqrt(max(0.0, 1.0 - r2))));
        material_uv = sphere_uv(sphere_n);
    }

    if (u_mode == 1) { gl_FragColor = vec4(texture2D(u_base_source, material_uv).rgb, 1.0); return; }
    if (u_mode == 2) { gl_FragColor = vec4(texture2D(u_base, material_uv).rgb, 1.0); return; }
    if (u_mode == 3) { gl_FragColor = vec4(texture2D(u_normal, material_uv).rgb, 1.0); return; }
    if (u_mode == 4) { gl_FragColor = vec4(vec3(scalar_sample(u_ao, material_uv)), 1.0); return; }
    if (u_mode == 5) { gl_FragColor = vec4(vec3(scalar_sample(u_roughness, material_uv)), 1.0); return; }
    if (u_mode == 6) { gl_FragColor = vec4(vec3(scalar_sample(u_metallic, material_uv)), 1.0); return; }
    if (u_mode == 7) { gl_FragColor = vec4(vec3(scalar_sample(u_height, material_uv)), 1.0); return; }
    if (u_mode == 8) { gl_FragColor = vec4(vec3(scalar_sample(u_cavity, material_uv)), 1.0); return; }
    if (u_mode == 9) { gl_FragColor = vec4(vec3(scalar_sample(u_curvature, material_uv)), 1.0); return; }
    if (u_mode == 10) { gl_FragColor = vec4(texture2D(u_f0, material_uv).rgb, 1.0); return; }
    if (u_mode == 11) { gl_FragColor = vec4(vec3(scalar_sample(u_f90, material_uv)), 1.0); return; }
    if (u_mode == 12 || u_mode == 13 || u_mode == 14 || u_mode == 15) {
        gl_FragColor = vec4(packed_sample(material_uv, u_mode), 1.0);
        return;
    }
    if (u_mode == 16) { gl_FragColor = vec4(texture2D(u_irradiance, material_uv).rgb, 1.0); return; }
    if (u_mode == 17) { gl_FragColor = vec4(texture2D(u_delight_shading, material_uv).rgb, 1.0); return; }

    vec3 n = normal_sample(material_uv);
    if (u_shape == 1) {
        n = sphere_tangent_normal(sphere_n, normal_sample(material_uv));
    }
    gl_FragColor = vec4(material_sample(material_uv, n), 1.0);
}
"""


def _texture_array(value: Any, *, fallback: np.ndarray) -> np.ndarray:
    if value is None:
        return fallback
    arr = np.asarray(value, dtype=np.float32)
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    if arr.ndim != 3:
        return fallback
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    elif arr.shape[2] > 3:
        arr = arr[..., :3]
    return np.ascontiguousarray(np.clip(arr, 0.0, 1.0), dtype=np.float32)


def _compile_shader(gl: Any, shader_type: int, source: str) -> int:
    shader = int(gl.glCreateShader(shader_type))
    gl.glShaderSource(shader, source)
    gl.glCompileShader(shader)
    ok = int(gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS))
    if not ok:
        log = gl.glGetShaderInfoLog(shader)
        try:
            text = log.decode("utf-8", errors="replace")
        except Exception:
            text = str(log)
        raise TextureMapGpuRequiredError(f"Texture Lab GPU shader compile failed: {text}")
    return shader


def _link_program(gl: Any) -> int:
    vertex = _compile_shader(gl, gl.GL_VERTEX_SHADER, _VERTEX_SHADER)
    fragment = _compile_shader(gl, gl.GL_FRAGMENT_SHADER, _FRAGMENT_SHADER)
    program = int(gl.glCreateProgram())
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
    gl.glLinkProgram(program)
    ok = int(gl.glGetProgramiv(program, gl.GL_LINK_STATUS))
    gl.glDeleteShader(vertex)
    gl.glDeleteShader(fragment)
    if not ok:
        log = gl.glGetProgramInfoLog(program)
        try:
            text = log.decode("utf-8", errors="replace")
        except Exception:
            text = str(log)
        raise TextureMapGpuRequiredError(f"Texture Lab GPU shader link failed: {text}")
    return program


def _upload_texture(gl: Any, arr: np.ndarray, unit: int) -> int:
    rgba = np.empty((arr.shape[0], arr.shape[1], 4), dtype=np.uint8)
    rgba[..., :3] = np.clip(arr * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
    rgba[..., 3] = 255
    texture_id = int(gl.glGenTextures(1))
    gl.glActiveTexture(gl.GL_TEXTURE0 + int(unit))
    gl.glBindTexture(gl.GL_TEXTURE_2D, texture_id)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
    gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
    gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
    gl.glTexImage2D(
        gl.GL_TEXTURE_2D,
        0,
        gl.GL_RGBA8,
        int(arr.shape[1]),
        int(arr.shape[0]),
        0,
        gl.GL_RGBA,
        gl.GL_UNSIGNED_BYTE,
        np.ascontiguousarray(rgba),
    )
    return texture_id


def _uniform(gl: Any, program: int, name: str) -> int:
    return int(gl.glGetUniformLocation(program, name))


def _target_size(generated: Mapping[str, Any], width: int, height: int | None) -> tuple[int, int]:
    maps = generated.get("maps", {})
    first = next((np.asarray(v) for v in maps.values() if hasattr(v, "shape")), None)
    source_h = int(first.shape[0]) if first is not None and first.ndim >= 2 else 1
    source_w = int(first.shape[1]) if first is not None and first.ndim >= 2 else 1
    target_w = max(64, int(width or 768))
    target_h = max(64, int(height)) if height is not None else max(64, int(round(source_h * (target_w / max(1, source_w)))))
    return target_w, target_h


def render_texture_lab_gpu_preview_from_generated(
    generated: Mapping[str, Any],
    settings: Mapping[str, Any] | None = None,
    *,
    preview_mode: str = "material",
    preview_shape: str = "plane",
    output_path: str | Path | None = None,
    width: int = 768,
    height: int | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Render a Texture Lab preview through an offscreen OpenGL fragment shader."""
    if QGuiApplication.instance() is None:
        raise TextureMapGpuRequiredError("Texture Lab GPU preview requires a running Qt application.")
    try:
        from OpenGL import GL
    except Exception as exc:
        raise TextureMapGpuRequiredError(f"Texture Lab GPU preview requires PyOpenGL: {exc}") from exc

    mode = str(preview_mode or "material").strip().lower()
    if mode not in _MODE_CODES:
        raise ValueError(f"unknown preview mode: {preview_mode}")
    requested_shape = _normalize_preview_shape(preview_shape)
    effective_shape = requested_shape if mode not in {"intrinsic_channels", "delight_compare"} else "plane"
    target_w, target_h = _target_size(generated, int(width or 768), height)
    normalized = normalize_texture_map_settings(settings)
    preview_settings = dict(generated.get("settings") or {})
    preview_settings.update(normalized)

    maps = dict(generated.get("maps") or {})
    fallback = _texture_array(maps.get("base_color"), fallback=np.ones((4, 4, 3), dtype=np.float32) * 0.5)
    arrays = {
        name: _texture_array(maps.get(name), fallback=fallback)
        for name in _TEXTURE_NAMES
    }
    if "f0" not in maps:
        arrays["f0"] = np.ones_like(fallback) * float(preview_settings.get("substrate_reflectance", 0.5))
    if "f90_mask" not in maps:
        arrays["f90_mask"] = np.ones_like(fallback) * float(preview_settings.get("f90_mask_strength", 0.0))

    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(0)
    fmt.setStencilBufferSize(0)
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        raise TextureMapGpuRequiredError("Texture Lab GPU preview could not create an offscreen surface.")
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        raise TextureMapGpuRequiredError("Texture Lab GPU preview could not create an OpenGL context.")
    if not context.makeCurrent(surface):
        raise TextureMapGpuRequiredError("Texture Lab GPU preview could not activate the OpenGL context.")

    textures: list[int] = []
    fbo = 0
    color_texture = 0
    program = 0
    try:
        program = _link_program(GL)
        fbo = int(GL.glGenFramebuffers(1))
        color_texture = int(GL.glGenTextures(1))
        GL.glBindTexture(GL.GL_TEXTURE_2D, color_texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, target_w, target_h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, color_texture, 0)
        if int(GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)) != int(GL.GL_FRAMEBUFFER_COMPLETE):
            raise TextureMapGpuRequiredError("Texture Lab GPU preview framebuffer is incomplete.")

        GL.glViewport(0, 0, target_w, target_h)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_BLEND)
        GL.glUseProgram(program)

        sampler_uniforms = {
            "base_color_source": "u_base_source",
            "base_color": "u_base",
            "normal": "u_normal",
            "ao": "u_ao",
            "roughness": "u_roughness",
            "metallic": "u_metallic",
            "height": "u_height",
            "cavity": "u_cavity",
            "curvature": "u_curvature",
            "f0": "u_f0",
            "f90_mask": "u_f90",
            "irradiance": "u_irradiance",
            "delight_shading": "u_delight_shading",
        }
        for unit, name in enumerate(_TEXTURE_NAMES):
            tex_id = _upload_texture(GL, arrays[name], unit)
            textures.append(tex_id)
            loc = _uniform(GL, program, sampler_uniforms[name])
            if loc >= 0:
                GL.glUniform1i(loc, unit)

        azimuth = float(preview_settings.get("preview_light_azimuth", 38.0))
        elevation = float(preview_settings.get("preview_light_elevation", 28.0))
        az = np.deg2rad(azimuth)
        el = np.deg2rad(elevation)
        light = np.array([np.cos(el) * np.sin(az), np.sin(el), np.cos(el) * np.cos(az)], dtype=np.float32)
        light /= max(1e-6, float(np.linalg.norm(light)))
        GL.glUniform1i(_uniform(GL, program, "u_mode"), int(_MODE_CODES[mode]))
        GL.glUniform1i(_uniform(GL, program, "u_shape"), 1 if effective_shape == "sphere" else 0)
        GL.glUniform3f(_uniform(GL, program, "u_light"), float(light[0]), float(light[1]), float(light[2]))
        GL.glUniform1f(_uniform(GL, program, "u_environment"), float(preview_settings.get("preview_environment", 0.35)))

        GL.glClearColor(0.02, 0.022, 0.028, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glBegin(GL.GL_QUADS)
        GL.glTexCoord2f(0.0, 0.0)
        GL.glVertex2f(-1.0, -1.0)
        GL.glTexCoord2f(1.0, 0.0)
        GL.glVertex2f(1.0, -1.0)
        GL.glTexCoord2f(1.0, 1.0)
        GL.glVertex2f(1.0, 1.0)
        GL.glTexCoord2f(0.0, 1.0)
        GL.glVertex2f(-1.0, 1.0)
        GL.glEnd()
        GL.glFlush()

        raw = GL.glReadPixels(0, 0, target_w, target_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((target_h, target_w, 4))
        image = Image.fromarray(np.flipud(pixels[..., :3]), "RGB")
        if output_path is None:
            source = Path(str(source_path or generated.get("source_path") or "texture_source.png")).expanduser()
            out = source.with_name(f"{source.stem}_pbr_{effective_shape}_gpu_preview_{mode}.png")
        else:
            out = Path(output_path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out)
    finally:
        try:
            GL.glUseProgram(0)
            if program:
                GL.glDeleteProgram(program)
            if textures:
                GL.glDeleteTextures(len(textures), textures)
            if color_texture:
                GL.glDeleteTextures(1, [int(color_texture)])
            if fbo:
                GL.glDeleteFramebuffers(1, [int(fbo)])
        except Exception:
            pass
        context.doneCurrent()
        surface.destroy()

    backend = dict(generated.get("backend") or {})
    backend["preview_renderer"] = "opengl_offscreen_texture_lab"
    backend["cpu_preview"] = False
    diagnostics = dict(generated.get("diagnostics") or {})
    diagnostics["gpu_preview"] = {
        "renderer": "opengl_offscreen_texture_lab",
        "mode": mode,
        "shape": effective_shape,
        "readback": "rgba8_png",
        "cpu_preview": False,
    }
    return {
        "schema_id": SCHEMA_ID,
        "source_path": str(source_path or generated.get("source_path") or ""),
        "preview_path": str(out),
        "preview_mode": mode,
        "preview_shape": effective_shape,
        "requested_preview_shape": requested_shape,
        "size": [int(target_w), int(target_h)],
        "settings": preview_settings,
        "algorithms": generated["algorithms"],
        "diagnostics": diagnostics,
        "backend": backend,
        "source_fingerprint": generated.get("source_fingerprint", ""),
        "settings_fingerprint": generated.get("settings_fingerprint", ""),
        "substrate": substrate_export_plan(preview_settings),
    }


def texture_lab_gpu_preview_status() -> dict[str, Any]:
    """Return a lightweight readiness report without creating a GL context."""
    app_ready = QGuiApplication.instance() is not None
    try:
        from OpenGL import GL  # noqa: F401

        pyopengl_ready = True
        pyopengl_error = ""
    except Exception as exc:
        pyopengl_ready = False
        pyopengl_error = str(exc)
    return {
        "renderer": "opengl_offscreen_texture_lab",
        "available": bool(app_ready and pyopengl_ready),
        "qt_app": bool(app_ready),
        "pyopengl": bool(pyopengl_ready),
        "pyopengl_error": pyopengl_error,
        "supported_modes": sorted(_MODE_CODES),
        "supported_packed_layouts": sorted(PACKED_LAYOUTS),
        "cpu_preview": False,
    }
