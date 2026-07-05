"""Offscreen OpenGL renderer for MMD export overlays."""
from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QGuiApplication, QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLVertexArrayObject,
)

from app.opengl_preview import (
    _GL_COLOR_BUFFER_BIT,
    _GL_DEPTH_BUFFER_BIT,
    _GL_DEPTH_TEST,
    _GL_SCISSOR_TEST,
    _MMDDirectGLPainter,
)


def _qimage_to_rgba_array(img: QImage) -> np.ndarray:
    if img.format() != QImage.Format.Format_RGBA8888:
        img = img.convertToFormat(QImage.Format.Format_RGBA8888)
    ptr = img.bits()
    data = np.frombuffer(ptr[: img.sizeInBytes()], dtype=np.uint8)
    stride = int(img.bytesPerLine())
    h = int(img.height())
    w = int(img.width())
    rows = data.reshape((h, stride))
    return rows[:, : w * 4].reshape((h, w, 4)).copy()


def _unpremultiply_rgba_array(arr: np.ndarray) -> np.ndarray:
    if arr.ndim != 3 or arr.shape[2] < 4:
        return arr
    out = np.ascontiguousarray(arr).copy()
    alpha = out[:, :, 3].astype(np.uint16)
    mask = alpha > 0
    if not np.any(mask):
        return out
    rgb = out[:, :, :3].astype(np.uint16)
    denom = alpha[mask][:, None]
    rgb_out = ((rgb[mask] * 255 + denom // 2) // denom).clip(0, 255)
    out_rgb = out[:, :, :3]
    out_rgb[mask] = rgb_out.astype(np.uint8)
    return out


class MMDOffscreenGLRenderer:
    """Render MMD preview packets into a transparent RGBA frame."""

    def __init__(self) -> None:
        self._surface: QOffscreenSurface | None = None
        self._ctx: QOpenGLContext | None = None
        self._fbo: QOpenGLFramebufferObject | None = None
        self._fbo_size: tuple[int, int] = (0, 0)
        self._painter: _MMDDirectGLPainter | None = None
        self._vao: QOpenGLVertexArrayObject | None = None

    def _ensure_context(self, width: int, height: int) -> bool:
        if QGuiApplication.instance() is None:
            return False
        if self._surface is None:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setAlphaBufferSize(8)
            fmt.setDepthBufferSize(24)
            fmt.setStencilBufferSize(8)
            try:
                fmt.setVersion(2, 1)
                fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.NoProfile)
            except Exception:
                pass

            self._surface = QOffscreenSurface()
            self._surface.setFormat(fmt)
            self._surface.create()

            self._ctx = QOpenGLContext()
            self._ctx.setFormat(self._surface.requestedFormat())
            if not self._ctx.create():
                return False

        if self._ctx is None or self._surface is None or not self._ctx.makeCurrent(self._surface):
            return False

        size = (max(16, int(width)), max(16, int(height)))
        if self._fbo is None or self._fbo_size != size:
            self._fbo = None
            fmt = QOpenGLFramebufferObjectFormat()
            fmt.setAttachment(QOpenGLFramebufferObject.Attachment.CombinedDepthStencil)
            self._fbo = QOpenGLFramebufferObject(size[0], size[1], fmt)
            self._fbo_size = size
            if not self._fbo.isValid():
                return False
        if self._painter is None:
            self._painter = _MMDDirectGLPainter(None)
        if self._vao is None:
            self._vao = QOpenGLVertexArrayObject()
            if not self._vao.create():
                self._vao = None
                return False
        return True

    def render_array(self, items: list[dict[str, Any]], width: int, height: int) -> np.ndarray | None:
        w, h = max(16, int(width)), max(16, int(height))
        if not items:
            return np.zeros((h, w, 4), dtype=np.uint8)
        if not self._ensure_context(w, h) or self._ctx is None or self._fbo is None or self._painter is None:
            return None
        if not self._fbo.bind():
            return None
        gl = self._ctx.functions()
        vao_bound = False
        try:
            if self._vao is not None:
                self._vao.bind()
                vao_bound = True
            gl.glViewport(0, 0, w, h)
            gl.glDisable(_GL_SCISSOR_TEST)
            gl.glDisable(_GL_DEPTH_TEST)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClear(_GL_COLOR_BUFFER_BIT | _GL_DEPTH_BUFFER_BIT)
            self._painter.draw(gl, items, w, h, (0, 0, w, h), restore_fbo=self._fbo)
            img = self._fbo.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        finally:
            if vao_bound and self._vao is not None:
                self._vao.release()
            self._fbo.release()
            self._ctx.doneCurrent()
        return np.ascontiguousarray(_unpremultiply_rgba_array(_qimage_to_rgba_array(img)))
