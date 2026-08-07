"""Render an authored material graph through the GLSL 120 backend.

``compile_graph_glsl`` turns the graph - HLSL Custom nodes and all - into a
fragment shader; this module puts it on a real GL context and reads the result
back as a ``QImage``.

Every failure is reported rather than swallowed: no GL context, a driver that
refuses the shader, or a graph the compiler rejected all come back as a report
with the reason, so the editor can show it instead of a blank preview.
"""
from __future__ import annotations

from typing import Any, Mapping

from app.material_graph.compile_glsl import GraphCompileError, compile_graph_glsl


SCHEMA_ID = "tigerstudio.material_graph.preview.v1"

VERTEX_SHADER = """#version 120
varying vec2 v_uv;
void main() {
    v_uv = gl_MultiTexCoord0.xy;
    gl_Position = gl_Vertex;
}
"""


def render_graph_preview(
    graph: Mapping[str, Any],
    *,
    width: int = 256,
    height: int = 256,
    source_image: Any = None,
) -> dict[str, Any]:
    """Compile and draw the graph, or explain why it could not be drawn."""
    result: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "compiled": False,
        "rendered": False,
        "reason": "",
        "glsl": "",
        "notes": [],
        "image": None,
        "backend": "opengl_120",
    }
    try:
        shader = compile_graph_glsl(graph)
    except GraphCompileError as error:
        result["reason"] = str(error)
        result["failed_node_id"] = error.node_id
        return result
    result["glsl"] = shader["glsl"]
    result["notes"] = list(shader["notes"])

    try:
        from PySide6.QtGui import (
            QImage,
            QOffscreenSurface,
            QOpenGLContext,
            QSurfaceFormat,
        )
        from PySide6.QtOpenGL import (
            QOpenGLFramebufferObject,
            QOpenGLShader,
            QOpenGLShaderProgram,
        )
    except Exception as error:  # pragma: no cover - PySide6 build without GL
        result["reason"] = f"Qt OpenGL is unavailable: {error}"
        return result

    surface_format = QSurfaceFormat()
    surface_format.setVersion(2, 1)
    surface_format.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    context = QOpenGLContext()
    context.setFormat(surface_format)
    if not context.create():
        result["reason"] = "This machine could not create an OpenGL context."
        return result
    surface = QOffscreenSurface()
    surface.setFormat(surface_format)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        result["reason"] = "This machine could not make an OpenGL context current."
        return result
    try:
        program = QOpenGLShaderProgram()
        if not program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex,
            VERTEX_SHADER,
        ):
            result["reason"] = f"Vertex shader rejected: {program.log()}"
            return result
        if not program.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment,
            shader["glsl"],
        ):
            result["reason"] = f"Fragment shader rejected: {program.log()}"
            return result
        if not program.link():
            result["reason"] = f"Shader link failed: {program.log()}"
            return result
        result["compiled"] = True

        target_width = max(1, min(4096, int(width)))
        target_height = max(1, min(4096, int(height)))
        buffer = QOpenGLFramebufferObject(target_width, target_height)
        if not buffer.bind():
            result["reason"] = "Could not bind the offscreen framebuffer."
            return result
        functions = context.functions()
        functions.glViewport(0, 0, target_width, target_height)
        functions.glClearColor(0.0, 0.0, 0.0, 0.0)
        functions.glClear(0x00004000)  # GL_COLOR_BUFFER_BIT
        program.bind()
        program.setUniformValue1i("u_source", 0)
        program.setUniformValue("u_resolution", float(target_width), float(target_height))
        _draw_full_screen_quad(context)
        program.release()
        buffer.release()
        image = buffer.toImage()
        result["rendered"] = not image.isNull()
        result["image"] = image if result["rendered"] else None
        if not result["rendered"]:
            result["reason"] = "The framebuffer read back empty."
        return result
    finally:
        context.doneCurrent()


def _draw_full_screen_quad(context: Any) -> None:
    """Fixed-function quad, matching the GLSL 120 path already in the app."""
    from OpenGL import GL  # type: ignore

    GL.glBegin(GL.GL_TRIANGLE_STRIP)
    for x, y in ((-1.0, -1.0), (1.0, -1.0), (-1.0, 1.0), (1.0, 1.0)):
        GL.glMultiTexCoord2f(GL.GL_TEXTURE0, (x + 1.0) * 0.5, (y + 1.0) * 0.5)
        GL.glVertex2f(x, y)
    GL.glEnd()


def preview_backend_status() -> dict[str, Any]:
    """Whether this machine can render the preview at all."""
    reason = ""
    available = False
    try:
        from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

        surface_format = QSurfaceFormat()
        surface_format.setVersion(2, 1)
        context = QOpenGLContext()
        context.setFormat(surface_format)
        if context.create():
            surface = QOffscreenSurface()
            surface.setFormat(surface_format)
            surface.create()
            available = bool(surface.isValid() and context.makeCurrent(surface))
            if available:
                context.doneCurrent()
            else:
                reason = "an OpenGL context could not be made current"
        else:
            reason = "an OpenGL context could not be created"
    except Exception as error:  # pragma: no cover - environment dependent
        reason = str(error)
    return {
        "schema": f"{SCHEMA_ID}.status",
        "available": available,
        "reason": reason,
        "target": "#version 120",
    }
