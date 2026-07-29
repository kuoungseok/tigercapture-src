"""Offscreen OpenGL export for render graphs supported by the GPU compositor."""
from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
)

try:
    from OpenGL import GL
except Exception:  # pragma: no cover - packaged fallback environments
    GL = None

from .glass_gpu_renderer import MotionGlassGpuRenderer
from .render_graph import RenderGraph


class MotionGpuExportRenderer:
    """Keep one offscreen context and render eligible full-resolution frames."""

    def __init__(self) -> None:
        self._surface: QOffscreenSurface | None = None
        self._context: QOpenGLContext | None = None
        self._renderer = MotionGlassGpuRenderer()
        self.last_diagnostics: dict[str, object] = {
            "backend": "qt_painter_fallback",
            "reason": "not_drawn",
        }

    def _ensure_context(self) -> bool:
        if GL is None:
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "pyopengl_unavailable",
            }
            return False
        if (
            self._context is not None
            and self._context.isValid()
            and self._surface is not None
            and self._surface.isValid()
        ):
            return True
        surface_format = QSurfaceFormat()
        surface_format.setRenderableType(QSurfaceFormat.OpenGL)
        surface_format.setProfile(QSurfaceFormat.CompatibilityProfile)
        surface_format.setVersion(3, 3)
        surface = QOffscreenSurface()
        surface.setFormat(surface_format)
        surface.create()
        context = QOpenGLContext()
        context.setFormat(surface.format())
        if not surface.isValid() or not context.create() or not context.isValid():
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "offscreen_gl_context_unavailable",
            }
            return False
        self._surface = surface
        self._context = context
        return True

    def render(
        self,
        graph: RenderGraph,
        *,
        width: int,
        height: int,
    ) -> QImage | None:
        eligible, reason = self._renderer.can_draw(graph)
        if not eligible:
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": reason,
            }
            return None
        if not self._ensure_context():
            return None
        assert self._context is not None and self._surface is not None
        if not self._context.makeCurrent(self._surface):
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "offscreen_gl_make_current_failed",
            }
            return None
        framebuffer_format = QOpenGLFramebufferObjectFormat()
        framebuffer_format.setAttachment(
            QOpenGLFramebufferObject.Attachment.NoAttachment
        )
        framebuffer_format.setTextureTarget(GL.GL_TEXTURE_2D)
        framebuffer_format.setInternalTextureFormat(GL.GL_RGBA8)
        framebuffer = QOpenGLFramebufferObject(
            max(1, int(width)),
            max(1, int(height)),
            framebuffer_format,
        )
        if not framebuffer.isValid() or not framebuffer.bind():
            self._context.doneCurrent()
            self.last_diagnostics = {
                "backend": "qt_painter_fallback",
                "reason": "offscreen_export_fbo_unavailable",
            }
            return None
        ok = self._renderer.draw(
            self._context.functions(),
            graph,
            widget_width=max(1, int(width)),
            widget_height=max(1, int(height)),
            target=QRectF(0.0, 0.0, float(width), float(height)),
            max_working_edge=max(int(width), int(height)),
            transparent_output=True,
        )
        image = framebuffer.toImage(True) if ok else QImage()
        framebuffer.release()
        self._context.doneCurrent()
        self.last_diagnostics = {
            **self._renderer.last_diagnostics,
            "offscreen_export": True,
            "readback_required": True,
            "output_width": int(width),
            "output_height": int(height),
        }
        if not ok or image.isNull():
            if image.isNull() and ok:
                self.last_diagnostics.update({
                    "backend": "qt_painter_fallback",
                    "reason": "offscreen_export_readback_failed",
                })
            return None
        return image.convertToFormat(QImage.Format_RGBA8888_Premultiplied)

    def clear(self) -> None:
        if (
            self._context is not None
            and self._surface is not None
            and self._context.makeCurrent(self._surface)
        ):
            self._renderer.clear()
            self._context.doneCurrent()
        self._context = None
        self._surface = None
