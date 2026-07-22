"""Direct OpenGL renderer for cached Motion Designer vector meshes."""
from __future__ import annotations

from collections import OrderedDict
import ctypes

import numpy as np
try:
    from OpenGL import GL
except Exception:  # pragma: no cover - exercised by packaged fallback environments
    GL = None
from PySide6.QtCore import QRectF
from PySide6.QtGui import QVector2D, QVector4D
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram

from .render_graph import RenderGraph


_VERTEX_SHADER = """
#version 120
attribute vec2 a_position;
attribute vec4 a_color;
uniform vec4 u_layer_linear;
uniform vec2 u_layer_translate;
uniform vec4 u_repeat_linear;
uniform vec2 u_repeat_translate;
uniform vec2 u_anchor;
uniform vec2 u_composition_size;
uniform vec2 u_widget_size;
uniform vec4 u_target;
uniform float u_opacity;
uniform vec4 u_instance_color;
varying vec4 v_color;
void main() {
    vec2 repeated = vec2(
        u_repeat_linear.x * a_position.x + u_repeat_linear.z * a_position.y + u_repeat_translate.x,
        u_repeat_linear.y * a_position.x + u_repeat_linear.w * a_position.y + u_repeat_translate.y
    );
    vec2 local = repeated - u_anchor;
    vec2 composition = vec2(
        u_layer_linear.x * local.x + u_layer_linear.z * local.y + u_layer_translate.x,
        u_layer_linear.y * local.x + u_layer_linear.w * local.y + u_layer_translate.y
    );
    vec2 screen = u_target.xy + composition / u_composition_size * u_target.zw;
    vec2 ndc = vec2(screen.x / u_widget_size.x * 2.0 - 1.0, 1.0 - screen.y / u_widget_size.y * 2.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_color = a_color * u_instance_color * u_opacity;
}
"""

_FRAGMENT_SHADER = """
#version 120
varying vec4 v_color;
void main() {
    gl_FragColor = v_color;
}
"""


class MotionVectorGpuRenderer:
    def __init__(self, parent=None, *, cache_capacity: int = 256) -> None:
        self._parent = parent
        self._program: QOpenGLShaderProgram | None = None
        self._buffers: OrderedDict[str, tuple[int, int, int]] = OrderedDict()
        self._capacity = max(1, int(cache_capacity))
        self.cache_hits = 0
        self.cache_misses = 0
        self.upload_count = 0
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
            if node.vector_gpu_packet is None:
                return False, node.vector_gpu_reason or "non_vector_node"
            if node.blend_mode not in {"normal", "add", "screen"}:
                return False, f"blend_mode:{node.blend_mode}"
        return True, ""

    def _ensure_resources(self) -> bool:
        if GL is None:
            self.last_diagnostics = {"backend": "qt_painter_fallback", "reason": "pyopengl_unavailable"}
            return False
        if self._program is not None:
            return True
        program = QOpenGLShaderProgram(self._parent)
        vertex_ok = program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER)
        fragment_ok = program.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER)
        program.bindAttributeLocation("a_position", 0)
        program.bindAttributeLocation("a_color", 1)
        if not vertex_ok or not fragment_ok or not program.link():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "vector_shader_compile_failed",
                "shader_log": program.log(),
            }
            return False
        self._program = program
        return True

    def _buffer_for(self, key: str, vertices: tuple[float, ...]) -> tuple[int, int, int] | None:
        cached = self._buffers.pop(key, None)
        if cached is not None:
            self.cache_hits += 1
            self._buffers[key] = cached
            return cached
        self.cache_misses += 1
        values = np.asarray(vertices, dtype=np.float32)
        vao = int(GL.glGenVertexArrays(1))
        vbo = int(GL.glGenBuffers(1))
        if not vao or not vbo:
            return None
        GL.glBindVertexArray(vao)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, vbo)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, int(values.nbytes), values, GL.GL_STATIC_DRAW)
        stride = 6 * 4
        GL.glEnableVertexAttribArray(0)
        GL.glEnableVertexAttribArray(1)
        GL.glVertexAttribPointer(0, 2, GL.GL_FLOAT, False, stride, ctypes.c_void_p(0))
        GL.glVertexAttribPointer(1, 4, GL.GL_FLOAT, False, stride, ctypes.c_void_p(2 * 4))
        GL.glBindVertexArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)
        result = vao, vbo, len(vertices) // 6
        self._buffers[key] = result
        self.upload_count += 1
        while len(self._buffers) > self._capacity:
            _old_key, (old_vao, old_vbo, _count) = self._buffers.popitem(last=False)
            GL.glDeleteBuffers(1, [old_vbo])
            GL.glDeleteVertexArrays(1, [old_vao])
        return result

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
        if GL is None or not self._ensure_resources() or self._program is None:
            return False
        for _ in range(8):
            if GL.glGetError() == GL.GL_NO_ERROR:
                break
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDisable(GL.GL_SCISSOR_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glClearColor(11.0 / 255.0, 13.0 / 255.0, 17.0 / 255.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        if not self._program.bind():
            self.last_diagnostics = {"backend": "qt_painter_fallback", "reason": "vector_shader_bind_failed"}
            return False
        self._set_uniform("u_composition_size", QVector2D(float(graph.width), float(graph.height)))
        self._set_uniform("u_widget_size", QVector2D(float(widget_width), float(widget_height)))
        self._set_uniform(
            "u_target", QVector4D(float(target.x()), float(target.y()), float(target.width()), float(target.height())),
        )
        vertex_count = 0
        draw_count = 0
        for node in graph.nodes:
            packet = node.vector_gpu_packet
            if packet is None:
                continue
            cached = self._buffer_for(packet.mesh.key, packet.mesh.vertices)
            if cached is None:
                self._program.release()
                self.last_diagnostics = {"backend": "qt_painter_fallback", "reason": "vbo_upload_failed"}
                return False
            vao, _vbo, count = cached
            a, b, c, d, tx, ty = node.matrix
            self._set_uniform("u_layer_linear", QVector4D(a, b, c, d))
            self._set_uniform("u_layer_translate", QVector2D(tx, ty))
            self._set_uniform(
                "u_anchor", QVector2D(packet.width * node.anchor[0], packet.height * node.anchor[1]),
            )
            if node.blend_mode == "add":
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE)
            elif node.blend_mode == "screen":
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_COLOR)
            else:
                GL.glBlendFunc(GL.GL_ONE, GL.GL_ONE_MINUS_SRC_ALPHA)
            GL.glBindVertexArray(vao)
            for instance in packet.instances:
                ra, rb, rc, rd, rtx, rty = instance.matrix
                self._set_uniform("u_repeat_linear", QVector4D(ra, rb, rc, rd))
                self._set_uniform("u_repeat_translate", QVector2D(rtx, rty))
                self._set_uniform("u_opacity", float(node.opacity * instance.opacity))
                self._set_uniform("u_instance_color", QVector4D(*instance.color))
                GL.glDrawArrays(GL.GL_TRIANGLES, 0, count)
                draw_count += 1
                vertex_count += count
            GL.glBindVertexArray(0)
        self._program.release()
        gl_error = int(GL.glGetError())
        self.last_diagnostics = {
            "backend": "motion_vector_gpu",
            "reason": "",
            "draw_count": draw_count,
            "vertex_count": vertex_count,
            "gpu_mesh_cache_hits": self.cache_hits,
            "gpu_mesh_cache_misses": self.cache_misses,
            "vbo_upload_count": self.upload_count,
            "gl_error": gl_error,
            "position_attribute": self._program.attributeLocation("a_position"),
            "color_attribute": self._program.attributeLocation("a_color"),
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
            for vao, vbo, _count in self._buffers.values():
                GL.glDeleteBuffers(1, [vbo])
                GL.glDeleteVertexArrays(1, [vao])
        self._buffers.clear()
        if self._program is not None:
            self._program.removeAllShaders()
            self._program = None
