"""Optional OpenGL helpers for Painter preview surfaces.

Painter keeps CPU/QPainter fallbacks for reliability, but 3D blockout previews
should use OpenGL whenever the current Qt session can create a valid context.
The module is intentionally separate from ``app.drawing`` so the main Painter
window does not import PyOpenGL until a GPU preview is actually requested.
"""
from __future__ import annotations

import os
from typing import Any

import numpy as np
from PySide6.QtGui import QGuiApplication, QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat


PAINTER_OPENGL_RENDERER_ID = "painter_blockout_opengl_offscreen_v1"


class PainterOpenGLUnavailable(RuntimeError):
    """Raised when the optional Painter OpenGL path cannot be used."""


def painter_opengl_enabled() -> bool:
    value = str(os.environ.get("TIGERCAPTURE_PAINTER_OPENGL", "auto")).strip().casefold()
    return value not in {"0", "false", "no", "off", "disabled", "cpu", "qpainter"}


def painter_opengl_status() -> dict[str, Any]:
    """Return a cheap readiness report without creating a GL context."""

    app_ready = QGuiApplication.instance() is not None
    try:
        from OpenGL import GL  # noqa: F401

        pyopengl_ready = True
        pyopengl_error = ""
    except Exception as exc:
        pyopengl_ready = False
        pyopengl_error = str(exc)
    enabled = painter_opengl_enabled()
    return {
        "schema": "tigerstudio.painter.opengl.status.v1",
        "renderer": PAINTER_OPENGL_RENDERER_ID,
        "enabled": bool(enabled),
        "available": bool(enabled and app_ready and pyopengl_ready),
        "context_probe": "not_created_by_status_call",
        "fallback_on_context_failure": True,
        "remote_safe": True,
        "qt_app": bool(app_ready),
        "pyopengl": bool(pyopengl_ready),
        "pyopengl_error": pyopengl_error,
        "fallback_renderer": "painter_blockout_qpainter_v1",
        "default_policy": "auto_opengl_with_qpainter_fallback",
        "environment": {
            "TIGERCAPTURE_PAINTER_OPENGL": str(os.environ.get("TIGERCAPTURE_PAINTER_OPENGL", "auto")),
            "QT_OPENGL": str(os.environ.get("QT_OPENGL", "")),
            "QT_QPA_PLATFORM": str(os.environ.get("QT_QPA_PLATFORM", "")),
        },
        "surfaces": {
            "blockout_preview": "opengl_offscreen_if_available",
            "blockout_canvas_overlay": "opengl_offscreen_if_available",
            "paint_canvas": "planned_texture_fbo_stroke_atlas",
        },
    }


def render_blockout_scene_opengl_qimage(scene: Any, width: int = 640, height: int = 360) -> QImage:
    """Render Painter 3D blockout projection through an offscreen OpenGL FBO."""

    if not painter_opengl_enabled():
        raise PainterOpenGLUnavailable("Painter OpenGL is disabled by TIGERCAPTURE_PAINTER_OPENGL.")
    if QGuiApplication.instance() is None:
        raise PainterOpenGLUnavailable("Painter OpenGL requires a running Qt application.")
    try:
        from OpenGL import GL
    except Exception as exc:
        raise PainterOpenGLUnavailable(f"Painter OpenGL requires PyOpenGL: {exc}") from exc

    from app.painter_3d_blockout import project_blockout_scene

    target_w = max(1, int(width or 1))
    target_h = max(1, int(height or 1))
    projection = project_blockout_scene(scene, target_w, target_h)

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setVersion(2, 1)
    fmt.setDepthBufferSize(0)
    fmt.setStencilBufferSize(0)
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        raise PainterOpenGLUnavailable("Painter OpenGL could not create an offscreen surface.")
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        surface.destroy()
        raise PainterOpenGLUnavailable("Painter OpenGL could not create a context.")
    if not context.makeCurrent(surface):
        surface.destroy()
        raise PainterOpenGLUnavailable("Painter OpenGL could not activate the context.")

    fbo = 0
    color_texture = 0
    try:
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
            raise PainterOpenGLUnavailable("Painter OpenGL framebuffer is incomplete.")

        GL.glViewport(0, 0, target_w, target_h)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        scene_payload = projection.get("scene") if isinstance(projection.get("scene"), dict) else {}
        if bool(scene_payload.get("show_grid", True)):
            _draw_grid(GL, target_w, target_h)
        for face in projection.get("faces", []) or []:
            _draw_face(GL, face, target_w, target_h)
        for edge in projection.get("edges", []) or []:
            _draw_edge(GL, edge, target_w, target_h)
        GL.glFlush()

        raw = GL.glReadPixels(0, 0, target_w, target_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((target_h, target_w, 4))
        flipped = np.ascontiguousarray(np.flipud(pixels))
        image = QImage(flipped.data, target_w, target_h, 4 * target_w, QImage.Format.Format_RGBA8888).copy()
    finally:
        try:
            if color_texture:
                GL.glDeleteTextures(1, [int(color_texture)])
            if fbo:
                GL.glDeleteFramebuffers(1, [int(fbo)])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        except Exception:
            pass
        context.doneCurrent()
        surface.destroy()
    return image


def _draw_grid(GL: Any, width: int, height: int) -> None:
    step = max(24, int(min(width, height) / 10))
    GL.glLineWidth(1.0)
    GL.glColor4f(0.82, 0.86, 1.0, 0.14)
    GL.glBegin(GL.GL_LINES)
    try:
        for x in range(width // 2 % step, width, step):
            _gl_vertex(GL, x, 0, width, height)
            _gl_vertex(GL, x, height, width, height)
        for y in range(height // 2 % step, height, step):
            _gl_vertex(GL, 0, y, width, height)
            _gl_vertex(GL, width, y, width, height)
    finally:
        GL.glEnd()


def _draw_face(GL: Any, face: dict[str, Any], width: int, height: int) -> None:
    rgba = _hex_to_rgba(str(face.get("color") or "#7C8CFF"), float(face.get("opacity", 0.72) or 0.72))
    GL.glColor4f(*rgba)
    GL.glBegin(GL.GL_POLYGON)
    try:
        for x, y in face.get("points", []) or []:
            _gl_vertex(GL, float(x), float(y), width, height)
    finally:
        GL.glEnd()


def _draw_edge(GL: Any, edge: dict[str, Any], width: int, height: int) -> None:
    a = edge.get("a")
    b = edge.get("b")
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) < 2 or len(b) < 2:
        return
    GL.glLineWidth(1.35)
    GL.glColor4f(0.96, 0.975, 1.0, 0.72)
    GL.glBegin(GL.GL_LINES)
    try:
        _gl_vertex(GL, float(a[0]), float(a[1]), width, height)
        _gl_vertex(GL, float(b[0]), float(b[1]), width, height)
    finally:
        GL.glEnd()


def _gl_vertex(GL: Any, x: float, y: float, width: int, height: int) -> None:
    GL.glVertex2f((float(x) / max(1.0, float(width))) * 2.0 - 1.0, 1.0 - (float(y) / max(1.0, float(height))) * 2.0)


def _hex_to_rgba(value: str, opacity: float) -> tuple[float, float, float, float]:
    text = str(value or "#7C8CFF").strip()
    if not (text.startswith("#") and len(text) == 7):
        text = "#7C8CFF"
    try:
        r = int(text[1:3], 16) / 255.0
        g = int(text[3:5], 16) / 255.0
        b = int(text[5:7], 16) / 255.0
    except Exception:
        r, g, b = (124 / 255.0, 140 / 255.0, 1.0)
    a = max(0.05, min(1.0, float(opacity)))
    return (r, g, b, a)


__all__ = [
    "PAINTER_OPENGL_RENDERER_ID",
    "PainterOpenGLUnavailable",
    "painter_opengl_enabled",
    "painter_opengl_status",
    "render_blockout_scene_opengl_qimage",
]
