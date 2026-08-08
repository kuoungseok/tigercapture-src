"""Direct OpenGL renderer for animated textured puppet meshes."""
from __future__ import annotations

from collections import OrderedDict
import ctypes

import numpy as np
try:
    from OpenGL import GL
except Exception:  # pragma: no cover - packaged fallback environments
    GL = None
from PySide6.QtCore import QRectF
from PySide6.QtGui import QVector2D, QVector4D
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram

from .render_graph import RenderGraph


_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
attribute vec2 a_uv;
uniform vec4 u_layer_linear;
uniform vec2 u_layer_translate;
uniform vec2 u_anchor;
uniform vec2 u_composition_size;
uniform vec2 u_widget_size;
uniform vec4 u_target;
varying vec2 v_uv;
void main() {
    vec2 local = a_position - u_anchor;
    vec2 composition = vec2(
        u_layer_linear.x * local.x + u_layer_linear.z * local.y + u_layer_translate.x,
        u_layer_linear.y * local.x + u_layer_linear.w * local.y + u_layer_translate.y
    );
    vec2 screen = u_target.xy + composition / u_composition_size * u_target.zw;
    vec2 ndc = vec2(screen.x / u_widget_size.x * 2.0 - 1.0, 1.0 - screen.y / u_widget_size.y * 2.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = a_uv;
}
"""

_FRAGMENT_SHADER = """
#version 120
uniform sampler2D u_texture;
uniform float u_opacity;
varying vec2 v_uv;
void main() {
    gl_FragColor = texture2D(u_texture, v_uv) * u_opacity;
}
"""


class MotionPuppetGpuRenderer:
    def __init__(self, parent=None, *, cache_capacity: int = 64) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._buffers: dict[str, tuple[int, int]] = {}
        self._textures: OrderedDict[str, int] = OrderedDict()
        self._capacity = max(1, int(cache_capacity))
        self.texture_upload_count = 0
        self.vertex_upload_count = 0
        self.last_diagnostics: dict[str, object] = {
            "backend": "qt_painter_fallback",
            "reason": "not_drawn",
        }

    @staticmethod
    def can_draw(graph: RenderGraph) -> tuple[bool, str]:
        if not graph.nodes:
            return False, "empty_graph"
        if graph.effect_groups:
            return False, "effect_group_requires_raster"
        for node in graph.nodes:
            if node.layer_type == "adjustment":
                return False, "adjustment_layer"
            if node.matte_layer_id:
                return False, "track_matte"
            if node.effects:
                return False, "effects_require_raster"
            if node.puppet_gpu_packet is None:
                return False, node.puppet_gpu_reason or "non_puppet_node"
            if node.blend_mode not in {"normal", "add", "screen"}:
                return False, f"blend_mode:{node.blend_mode}"
            if node.replicator_instances and len(node.replicator_instances) > 1:
                return False, "replicator_requires_raster"
            if node.motion_blur_samples > 1:
                return False, "motion_blur_requires_raster"
        return True, ""

    def _ensure_resources(self) -> bool:
        if GL is None:
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "pyopengl_unavailable",
            }
            return False
        if self._program is not None:
            return True
        program = QOpenGLShaderProgram(self._parent)
        vertex_ok = program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER,
        )
        fragment_ok = program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER,
        )
        program.bindAttributeLocation("a_position", 0)
        program.bindAttributeLocation("a_uv", 1)
        if not vertex_ok or not fragment_ok or not program.link():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "puppet_shader_compile_failed",
                "shader_log": program.log(),
            }
            return False
        self._program = program
        return True

    def _dynamic_buffer(self, key: str, vertices: tuple[float, ...]) -> tuple[int, int, int] | None:
        resource = self._buffers.get(key)
        if resource is None:
            vao = int(GL.glGenVertexArrays(1))
            vbo = int(GL.glGenBuffers(1))
            if not vao or not vbo:
                return None
            resource = vao, vbo
            self._buffers[key] = resource
        vao, vbo = resource
        values = np.asarray(vertices, dtype=np.float32)
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, int(values.nbytes), values, GL.GL_DYNAMIC_DRAW)
        stride = 4 * 4
        GL.glEnableVertexAttribArray(0)
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, False, stride, ctypes.c_void_p(2 * 4))
        GL.glBindVertexArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        self.vertex_upload_count += 1
        return vao, vbo, len(vertices) // 4

    def _texture(self, key: str, image) -> int:
        cached = self._textures.pop(key, None)
        if cached is not None:
            self._textures[key] = cached
            return cached
        texture = int(GL.glGenTextures(1))
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        values = np.frombuffer(image.constBits(), dtype=np.uint8).reshape(
            image.height(), image.bytesPerLine(),
        )[:, : image.width() * 4]
        values = np.ascontiguousarray(values)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage2D(
            GL.GL_TEXTURE_2D, 0, GL.GL_RGBA,
            image.width(), image.height(), 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, values,
        )
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        self._textures[key] = texture
        self.texture_upload_count += 1
        while len(self._textures) > self._capacity:
            _old_key, old_texture = self._textures.popitem(last=False)
            GL.glDeleteTextures([old_texture])
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
        for _ in range(8):
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
                "reason": "puppet_shader_bind_failed",
            }
            return False
        self._set_uniform("u_composition_size", QVector2D(float(graph.width), float(graph.height)))
        self._set_uniform("u_widget_size", QVector2D(float(widget_width), float(widget_height)))
        self._set_uniform(
            "u_target",
            QVector4D(float(target.x()), float(target.y()), float(target.width()), float(target.height())),
        )
        GL.glUniform1i(self._program.uniformLocation("u_texture"), 0)
        draw_count = 0
        triangle_count = 0
        repaired_vertex_count = 0
        for node in graph.nodes:
            packet = node.puppet_gpu_packet
            if packet is None:
                continue
            buffer = self._dynamic_buffer(packet.key, packet.vertices)
            if buffer is None:
                self._program.release()
                self.last_diagnostics = {
                    "backend": "qt_painter_fallback",
                    "reason": "puppet_vbo_upload_failed",
                }
                return False
            vao, _vbo, count = buffer
            texture = self._texture(packet.texture_key, packet.image)
            a, b, c, d, tx, ty = node.matrix
            self._set_uniform("u_layer_linear", QVector4D(a, b, c, d))
            self._set_uniform("u_layer_translate", QVector2D(tx, ty))
            self._set_uniform(
                "u_anchor",
                QVector2D(packet.width * node.anchor[0], packet.height * node.anchor[1]),
            )
            self._set_uniform("u_opacity", float(node.opacity))
            if node.blend_mode == "add":
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
            elif node.blend_mode == "screen":
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_COLOR)
            else:
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
            GL.glActiveTexture(GL.GL_TEXTURE0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
            GL.glBindVertexArray(vao)
            GL.glDrawArrays(GL.GL_TRIANGLES, 0, count)
            GL.glBindVertexArray(0)
            GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
            draw_count += 1
            triangle_count += packet.triangle_count
            repaired_vertex_count += int(packet.repair.get("repaired_vertex_count", 0) or 0)
        self._program.release()
        gl_error = int(GL.glGetError())
        self.last_diagnostics = {
            "backend": "motion_puppet_gpu",
            "reason": "",
            "draw_count": draw_count,
            "triangle_count": triangle_count,
            "texture_upload_count": self.texture_upload_count,
            "dynamic_vertex_upload_count": self.vertex_upload_count,
            "repaired_vertex_count": repaired_vertex_count,
            "vertex_solver": "cpu_pins",
            "mesh_rasterizer": "opengl",
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
        if GL is not None:
            for vao, vbo in self._buffers.values():
                GL.glDeleteBuffers(1, [vbo])
                GL.glDeleteVertexArrays(1, [vao])
            if self._textures:
                GL.glDeleteTextures(list(self._textures.values()))
        self._buffers.clear()
        self._textures.clear()
        if self._program is not None:
            self._program.removeAllShaders()
            self._program = None


__all__ = ["MotionPuppetGpuRenderer"]
