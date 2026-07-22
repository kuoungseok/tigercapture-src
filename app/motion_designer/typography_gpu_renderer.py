"""OpenGL glyph-atlas renderer for Motion Designer typography Preview."""
from __future__ import annotations

from collections import OrderedDict
import ctypes

import numpy as np
try:
    from OpenGL import GL
except Exception:  # pragma: no cover - packaged environments may omit PyOpenGL
    GL = None
from PySide6.QtCore import QRectF
from PySide6.QtGui import QVector2D, QVector4D
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLTexture

from .render_graph import RenderGraph
from .typography_gpu import TYPOGRAPHY_GLYPH_ATLAS, TypographyGpuPage


_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
uniform vec2 u_glyph_offset;
uniform vec2 u_glyph_size;
uniform vec4 u_glyph_linear;
uniform vec2 u_glyph_translate;
uniform vec4 u_layer_linear;
uniform vec2 u_layer_translate;
uniform vec2 u_anchor;
uniform vec2 u_layer_size;
uniform vec2 u_composition_size;
uniform vec2 u_widget_size;
uniform vec4 u_target;
uniform vec4 u_uv;
varying vec2 v_uv;
varying vec2 v_layer_local;
void main() {
    vec2 glyph_local = u_glyph_offset + a_position * u_glyph_size;
    vec2 layer_pixel = vec2(
        u_glyph_linear.x * glyph_local.x + u_glyph_linear.z * glyph_local.y + u_glyph_translate.x,
        u_glyph_linear.y * glyph_local.x + u_glyph_linear.w * glyph_local.y + u_glyph_translate.y
    );
    vec2 layer_local = layer_pixel - u_anchor;
    vec2 composition = vec2(
        u_layer_linear.x * layer_local.x + u_layer_linear.z * layer_local.y + u_layer_translate.x,
        u_layer_linear.y * layer_local.x + u_layer_linear.w * layer_local.y + u_layer_translate.y
    );
    vec2 screen = u_target.xy + composition / u_composition_size * u_target.zw;
    vec2 ndc = vec2(screen.x / u_widget_size.x * 2.0 - 1.0, 1.0 - screen.y / u_widget_size.y * 2.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = u_uv.xy + a_position * u_uv.zw;
    v_layer_local = layer_pixel;
}
"""

_FRAGMENT_SHADER = """
#version 120
uniform sampler2D u_atlas;
uniform vec4 u_color;
uniform float u_opacity;
uniform vec2 u_layer_size;
varying vec2 v_uv;
varying vec2 v_layer_local;
void main() {
    if (v_layer_local.x < 0.0 || v_layer_local.y < 0.0 ||
        v_layer_local.x > u_layer_size.x || v_layer_local.y > u_layer_size.y) {
        discard;
    }
    float coverage = texture2D(u_atlas, v_uv).a;
    float alpha = coverage * u_color.a * u_opacity;
    gl_FragColor = vec4(u_color.rgb * alpha, alpha);
}
"""


class MotionTypographyGpuRenderer:
    def __init__(self, parent=None, *, texture_capacity: int = 16) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._quad_vao = 0
        self._quad_vbo = 0
        self._textures: OrderedDict[str, tuple[QOpenGLTexture, int]] = OrderedDict()
        self._texture_capacity = max(1, int(texture_capacity))
        self.texture_upload_count = 0
        self.texture_cache_hits = 0
        self.texture_cache_misses = 0
        self.last_diagnostics: dict[str, object] = {
            "backend": "qt_painter_fallback",
            "reason": "not_drawn",
        }

    @staticmethod
    def can_draw(graph: RenderGraph) -> tuple[bool, str]:
        for node in graph.nodes:
            if node.layer_type == "adjustment":
                return False, "adjustment_layer"
            if node.matte_layer_id:
                return False, "track_matte"
            if node.typography_gpu_packet is None:
                return False, node.typography_gpu_reason or "non_typography_node"
            if node.blend_mode not in {"normal", "add"}:
                return False, f"blend_mode:{node.blend_mode}"
        return True, ""

    def _ensure_resources(self) -> bool:
        if GL is None:
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "pyopengl_unavailable",
            }
            return False
        if self._program is not None and self._quad_vao and self._quad_vbo:
            return True
        program = QOpenGLShaderProgram(self._parent)
        vertex_ok = program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER)
        fragment_ok = program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER)
        program.bindAttributeLocation("a_position", 0)
        if not vertex_ok or not fragment_ok or not program.link():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "typography_shader_compile_failed",
                "shader_log": program.log(),
            }
            return False
        vertices = np.asarray([
            0.0, 0.0, 1.0, 0.0, 1.0, 1.0,
            0.0, 0.0, 1.0, 1.0, 0.0, 1.0,
        ], dtype=np.float32)
        vao = int(GL.glGenVertexArrays(1))
        vbo = int(GL.glGenBuffers(1))
        if not vao or not vbo:
            return False
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, int(vertices.nbytes), vertices, GL.GL_STATIC_DRAW)
        GL.glEnableVertexAttribArray(0)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, False, 2 * 4, ctypes.c_void_p(0))
        GL.glBindVertexArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        self._program = program
        self._quad_vao = vao
        self._quad_vbo = vbo
        return True

    def _texture_for(self, page: TypographyGpuPage) -> QOpenGLTexture | None:
        cached = self._textures.pop(page.key, None)
        if cached is not None and cached[1] == page.revision:
            self.texture_cache_hits += 1
            self._textures[page.key] = cached
            return cached[0]
        if cached is not None:
            cached[0].destroy()
        self.texture_cache_misses += 1
        texture = QOpenGLTexture(
            page.image,
            QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps,
        )
        if not texture.isCreated():
            return None
        texture.setMinMagFilters(QOpenGLTexture.Filter.Linear, QOpenGLTexture.Filter.Linear)
        texture.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
        self._textures[page.key] = (texture, page.revision)
        self.texture_upload_count += 1
        while len(self._textures) > self._texture_capacity:
            _key, (old_texture, _revision) = self._textures.popitem(last=False)
            old_texture.destroy()
        return texture

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
            self.last_diagnostics = {"backend": "qt_painter_fallback", "reason": reason}
            return False
        if not self._ensure_resources() or self._program is None:
            return False
        for _index in range(8):
            if GL.glGetError() == GL.GL_NO_ERROR:
                break
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glClearColor(11.0 / 255.0, 13.0 / 255.0, 17.0 / 255.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if not self._program.bind():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "typography_shader_bind_failed",
            }
            return False
        self._set_uniform("u_composition_size", QVector2D(float(graph.width), float(graph.height)))
        self._set_uniform("u_widget_size", QVector2D(float(widget_width), float(widget_height)))
        self._set_uniform(
            "u_target",
            QVector4D(float(target.x()), float(target.y()), float(target.width()), float(target.height())),
        )
        self._set_uniform("u_atlas", 0)
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindVertexArray(self._quad_vao)
        draw_count = 0
        page_by_key = {
            page.key: page
            for node in graph.nodes
            for page in node.typography_gpu_packet.pages
        }
        current_texture = 0
        for node in graph.nodes:
            packet = node.typography_gpu_packet
            if packet is None:
                continue
            a, b, c, d, tx, ty = node.matrix
            self._set_uniform("u_layer_linear", QVector4D(a, b, c, d))
            self._set_uniform("u_layer_translate", QVector2D(tx, ty))
            self._set_uniform(
                "u_anchor",
                QVector2D(packet.width * node.anchor[0], packet.height * node.anchor[1]),
            )
            self._set_uniform("u_layer_size", QVector2D(float(packet.width), float(packet.height)))
            if node.blend_mode == "add":
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
            else:
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
            for instance in packet.instances:
                page = page_by_key.get(instance.page_key)
                if page is None:
                    continue
                texture = self._texture_for(page)
                if texture is None:
                    continue
                texture_id = int(texture.textureId())
                if texture_id != current_texture:
                    texture.bind(0)
                    current_texture = texture_id
                ga, gb, gc, gd, gtx, gty = instance.matrix
                self._set_uniform("u_glyph_offset", QVector2D(*instance.offset))
                self._set_uniform("u_glyph_size", QVector2D(*instance.size))
                self._set_uniform("u_glyph_linear", QVector4D(ga, gb, gc, gd))
                self._set_uniform("u_glyph_translate", QVector2D(gtx, gty))
                self._set_uniform("u_uv", QVector4D(*instance.uv))
                self._set_uniform("u_color", QVector4D(*instance.color))
                self._set_uniform("u_opacity", float(node.opacity * instance.opacity))
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, 6)
                draw_count += 1
        GL.glBindVertexArray(0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self._program.release()
        gl_error = int(GL.glGetError())
        self.last_diagnostics = {
            "backend": "motion_typography_gpu",
            "reason": "",
            "draw_count": draw_count,
            "glyph_atlas_texture_count": len(self._textures),
            "glyph_atlas_texture_upload_count": self.texture_upload_count,
            "glyph_atlas_texture_hits": self.texture_cache_hits,
            "glyph_atlas_texture_misses": self.texture_cache_misses,
            "gl_error": gl_error,
            **TYPOGRAPHY_GLYPH_ATLAS.diagnostics(),
        }
        if gl_error:
            self.last_diagnostics.update({
                "backend": "qt_painter_fallback",
                "reason": f"gl_error:{gl_error}",
            })
            return False
        return True

    def clear(self) -> None:
        if GL is not None:
            for texture, _revision in self._textures.values():
                texture.destroy()
            if self._quad_vbo:
                GL.glDeleteBuffers(1, [self._quad_vbo])
            if self._quad_vao:
                GL.glDeleteVertexArrays(1, [self._quad_vao])
        self._textures.clear()
        self._quad_vbo = 0
        self._quad_vao = 0
        if self._program is not None:
            self._program.removeAllShaders()
            self._program = None
