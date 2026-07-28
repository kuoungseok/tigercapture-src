"""Direct OpenGL backdrop renderer for eligible Tiger Glass preview graphs."""
from __future__ import annotations

import ctypes
from dataclasses import replace
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
from .keyframes import evaluate_property
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
uniform int u_mode;
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

void main() {
    if (u_mode == 0) {
        gl_FragColor = backdrop(v_uv);
        return;
    }
    vec4 original = backdrop(v_uv);
    float mask = texture2D(u_mask, v_uv).a * u_opacity;
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
        min(texture2D(u_mask, v_uv + vec2(u_texel.x, 0.0)).a,
            texture2D(u_mask, v_uv - vec2(u_texel.x, 0.0)).a),
        min(texture2D(u_mask, v_uv + vec2(0.0, u_texel.y)).a,
            texture2D(u_mask, v_uv - vec2(0.0, u_texel.y)).a)
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
        if graph.effect_groups:
            return False, "effect_group_requires_raster"
        glass_count = 0
        for node in graph.nodes:
            effect = glass_effect(node.effects)
            if effect is not None:
                glass_count += 1
                if any(
                    item.enabled and item.kind.strip().lower() != "tiger_glass"
                    for item in node.effects or ()
                ):
                    return False, "glass_layer_has_additional_effects"
            if node.layer_type in {"adjustment", "precomp"}:
                return False, f"{node.layer_type}_requires_raster"
            if node.matte_layer_id:
                return False, "track_matte_requires_raster"
            if node.motion_blur_samples > 1:
                return False, "motion_blur_requires_raster"
            if node.cast_shadows or node.receive_shadows:
                return False, "card_shadow_requires_raster"
            if node.blend_mode != "normal":
                return False, f"blend_mode:{node.blend_mode}"
        if glass_count == 0:
            return False, "glass_material_missing"
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
    def _working_size(target: QRectF) -> tuple[int, int]:
        width = max(1, int(round(target.width())))
        height = max(1, int(round(target.height())))
        longest = max(width, height)
        if longest <= MAX_GLASS_PREVIEW_LONG_EDGE:
            return width, height
        scale = MAX_GLASS_PREVIEW_LONG_EDGE / float(longest)
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
        raster_size = self._working_size(target)
        stages: list[tuple[str, RenderNode | None, QImage]] = []
        raster_nodes = []
        for node in graph.nodes:
            effect = glass_effect(node.effects)
            if effect is None:
                raster_nodes.append(node)
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
                ))
                raster_nodes.clear()
            stages.append((
                "glass",
                node,
                render_graph_image(
                    replace(
                        graph,
                        nodes=[replace(node, effects=[])],
                        effect_groups=[],
                    ),
                    output_size=raster_size,
                ),
            ))
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
            ))
        raster_ms = (time.perf_counter() - raster_started) * 1000.0
        stage_textures = [
            (kind, node, self._image_texture(image))
            for kind, node, image in stages
        ]
        if any(texture is None for _kind, _node, texture in stage_textures):
            for _kind, _node, texture in stage_textures:
                if texture is not None:
                    texture.destroy()
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
            for _kind, _node, texture in stage_textures:
                texture.destroy()
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
        GL.glClearColor(11.0 / 255.0, 13.0 / 255.0, 17.0 / 255.0, 1.0)
        if not self._program.bind():
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, default_fbo)
            for _kind, _node, texture in stage_textures:
                texture.destroy()
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

        glass_pass_count = 0
        raster_pass_count = 0
        for kind, stage_node, stage_texture in stage_textures:
            if kind == "raster":
                GL.glEnable(GL.GL_BLEND)
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
                self._set_uniform("u_mode", 0)
                self._set_uniform("u_backdrop_flip_y", 0)
                stage_texture.bind(0)
                self._draw_quad()
                stage_texture.release(0)
                raster_pass_count += 1
                continue
            node = stage_node
            mask_texture = stage_texture
            effect = glass_effect(node.effects)
            if effect is None:
                continue
            next_index = 1 - current_index
            framebuffers[next_index].bind()
            GL.glViewport(0, 0, raster_size[0], raster_size[1])
            GL.glDisable(GL.GL_BLEND)
            tint = QColor(str(effect.metadata.get("tint") or "#ffffff"))
            driver = node.glass_driver_override or (
                _effect_value(effect, "driver_x", node.local_time_ms, 0.0),
                _effect_value(effect, "driver_y", node.local_time_ms, 0.0),
            )
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
            self._set_uniform("u_mode", 1)
            self._set_uniform("u_backdrop_flip_y", 1)
            self._set_uniform(
                "u_texel",
                QVector2D(1.0 / raster_size[0], 1.0 / raster_size[1]),
            )
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
            self._set_uniform("u_time", node.local_time_ms * 0.001)
            self._set_uniform("u_driver", QVector2D(*driver))
            self._draw_quad()
            mask_texture.release(1)
            current_index = next_index
            glass_pass_count += 1

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
        for _kind, _node, texture in stage_textures:
            texture.destroy()
        gl_error = int(GL.glGetError())
        gpu_ms = (time.perf_counter() - gpu_started) * 1000.0
        self.last_diagnostics = {
            "backend": "motion_glass_gpu",
            "reason": "",
            "glass_pass_count": glass_pass_count,
            "raster_segment_count": raster_pass_count,
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
