"""Offscreen OpenGL renderer for Spine timeline previews.

This reuses the same draw math as ``SpineGLViewport`` but renders into a
QOpenGLFramebufferObject, returning a transparent RGBA PIL image for timeline
composition.  It must be used from the Qt GUI thread.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLFramebufferObject,
    QOpenGLFramebufferObjectFormat,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
    QOpenGLVertexArrayObject,
)

from app.spine_editor.spine_gl_renderer import (
    _FRAG,
    _GL_BLEND,
    _GL_COLOR_BUFFER_BIT,
    _GL_DEPTH_TEST,
    _GL_ONE_MINUS_SRC_ALPHA,
    _GL_SCISSOR_TEST,
    _GL_SRC_ALPHA,
    _VERT,
    SpineGLViewport,
)


_GL_ONE = 0x0001


def _qimage_to_rgba_array(img: QImage) -> np.ndarray:
    """Copy a RGBA8888 QImage into a tight HxWx4 uint8 array."""
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
    """Convert premultiplied RGBA data back to straight-alpha RGBA."""
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


class SpineOffscreenGLRenderer:
    """QOffscreenSurface + FBO Spine renderer."""

    pil_to_qimage = staticmethod(SpineGLViewport.pil_to_qimage)
    _mesh_weights_for = SpineGLViewport._mesh_weights_for
    _json_uv_to_atlas = SpineGLViewport._json_uv_to_atlas
    _compute_region_corners_screen_spine = (
        SpineGLViewport._compute_region_corners_screen_spine
    )
    _region_uv_corners = SpineGLViewport._region_uv_corners
    _draw_mesh = SpineGLViewport._draw_mesh
    _draw_spine_gl = SpineGLViewport._draw_spine_gl

    def __init__(self, skeleton, atlas: dict, pil_pages: list, pma: bool = False):
        self._skeleton = skeleton
        self._atlas = atlas or {}
        self._pil_pages = pil_pages or []
        self._pma = bool(pma)
        self._active_skin = "default"
        self._hidden_slots: set[str] = set()

        self._offset = QPointF(0.0, 0.0)
        self._zoom = 1.0
        self._w = 1
        self._h = 1

        self._surface: Optional[QOffscreenSurface] = None
        self._ctx: Optional[QOpenGLContext] = None
        self._fbo: Optional[QOpenGLFramebufferObject] = None
        self._fbo_w = 0
        self._fbo_h = 0
        self._prog: Optional[QOpenGLShaderProgram] = None
        self._vbo: Optional[QOpenGLBuffer] = None
        self._vao: Optional[QOpenGLVertexArrayObject] = None
        self._gl_textures: dict[int, QOpenGLTexture] = {}
        self._pending_destroy: list[QOpenGLTexture] = []

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h

    def _ensure_context(self, w: int, h: int) -> bool:
        if self._surface is None:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setVersion(3, 3)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
            fmt.setAlphaBufferSize(8)
            fmt.setDepthBufferSize(0)

            self._surface = QOffscreenSurface()
            self._surface.setFormat(fmt)
            self._surface.create()

            self._ctx = QOpenGLContext()
            self._ctx.setFormat(self._surface.requestedFormat())
            if not self._ctx.create():
                return False

        if not self._ctx.makeCurrent(self._surface):
            return False

        if self._prog is None:
            self._prog = QOpenGLShaderProgram()
            if not self._prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex, _VERT
            ):
                return False
            if not self._prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment, _FRAG
            ):
                return False
            if not self._prog.link():
                return False

            self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo.create()
            self._vao = QOpenGLVertexArrayObject()
            self._vao.create()

        if self._fbo is None or self._fbo_w != w or self._fbo_h != h:
            self._fbo = None
            fbo_fmt = QOpenGLFramebufferObjectFormat()
            fbo_fmt.setAttachment(QOpenGLFramebufferObject.Attachment.NoAttachment)
            self._fbo = QOpenGLFramebufferObject(w, h, fbo_fmt)
            self._fbo_w = w
            self._fbo_h = h

        return True

    def _upload_textures(self, gl) -> None:
        for tex in self._pending_destroy:
            try:
                tex.destroy()
            except Exception:
                pass
        self._pending_destroy.clear()

        for i, pil_img in enumerate(self._pil_pages):
            if pil_img is None:
                continue
            qimg = self.pil_to_qimage(pil_img)
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind()
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release()
            self._gl_textures[i] = tex

    def _render_qimage(
        self,
        width: int,
        height: int,
        scale: float,
        anim_name: str,
        time: float,
        skin_name: str,
        offset_x: float,
        offset_y: float,
    ) -> QImage | None:
        w, h = max(1, int(width)), max(1, int(height))
        if not self._ensure_context(w, h):
            return None

        self._w = w
        self._h = h
        self._active_skin = skin_name or "default"
        self._zoom = float(scale)
        self._offset = QPointF(w / 2 + float(offset_x), h / 2 - float(offset_y))

        if anim_name:
            anim = self._skeleton.animations.get(anim_name)
            if anim:
                self._skeleton.apply_animation(anim, float(time))

        if not self._fbo.bind():
            return None

        gl = self._ctx.functions()
        gl.glViewport(0, 0, w, h)
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glDisable(_GL_DEPTH_TEST)
        gl.glEnable(_GL_BLEND)
        if self._pma:
            gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
        else:
            gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(_GL_COLOR_BUFFER_BIT)

        if self._pil_pages and not self._gl_textures:
            self._upload_textures(gl)
        if self._skeleton and self._atlas and self._gl_textures:
            if self._vao is not None:
                self._vao.bind()
            try:
                self._draw_spine_gl(gl)
            finally:
                if self._vao is not None:
                    self._vao.release()

        img = self._fbo.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        self._fbo.release()
        self._ctx.doneCurrent()

        return img

    def render_array(
        self,
        width: int,
        height: int,
        scale: float,
        anim_name: str,
        time: float,
        skin_name: str,
        offset_x: float,
        offset_y: float,
    ) -> np.ndarray | None:
        """Render and return a tight RGBA ndarray for preview compositing."""
        img = self._render_qimage(
            width=width,
            height=height,
            scale=scale,
            anim_name=anim_name,
            time=time,
            skin_name=skin_name,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        if img is None:
            return None
        arr = _qimage_to_rgba_array(img)
        if self._pma:
            arr = _unpremultiply_rgba_array(arr)
        return np.ascontiguousarray(arr)

    def render(
        self,
        width: int,
        height: int,
        scale: float,
        anim_name: str,
        time: float,
        skin_name: str,
        offset_x: float,
        offset_y: float,
    ) -> Image.Image | None:
        img = self._render_qimage(
            width=width,
            height=height,
            scale=scale,
            anim_name=anim_name,
            time=time,
            skin_name=skin_name,
            offset_x=offset_x,
            offset_y=offset_y,
        )
        if img is None:
            return None
        ptr = img.bits()
        data = bytes(ptr[: img.sizeInBytes()])
        pil = Image.frombytes(
            "RGBA",
            (int(img.width()), int(img.height())),
            data,
            "raw",
            "RGBA",
            int(img.bytesPerLine()),
            1,
        )
        if self._pma:
            from app.spine_editor.spine_renderer import unpremultiply

            pil = unpremultiply(pil)
        return pil


class SpineOverlayGLCompositor:
    """Composite multiple Spine clips into one offscreen FBO/readback."""

    pil_to_qimage = staticmethod(SpineGLViewport.pil_to_qimage)
    _mesh_weights_for = SpineGLViewport._mesh_weights_for
    _json_uv_to_atlas = SpineGLViewport._json_uv_to_atlas
    _compute_region_corners_screen_spine = (
        SpineGLViewport._compute_region_corners_screen_spine
    )
    _region_uv_corners = SpineGLViewport._region_uv_corners
    _draw_mesh = SpineGLViewport._draw_mesh
    _draw_spine_gl = SpineGLViewport._draw_spine_gl

    def __init__(self):
        self._surface: Optional[QOffscreenSurface] = None
        self._ctx: Optional[QOpenGLContext] = None
        self._fbo: Optional[QOpenGLFramebufferObject] = None
        self._fbo_w = 0
        self._fbo_h = 0
        self._prog: Optional[QOpenGLShaderProgram] = None
        self._vbo: Optional[QOpenGLBuffer] = None
        self._vao: Optional[QOpenGLVertexArrayObject] = None
        self._texture_cache: dict[tuple, dict[int, QOpenGLTexture]] = {}
        self._texture_cache_order: list[tuple] = []
        self._texture_cache_limit = 16

        self._skeleton = None
        self._atlas: dict = {}
        self._pil_pages: list = []
        self._gl_textures: dict[int, QOpenGLTexture] = {}
        self._pma = False
        self._active_skin = "default"
        self._hidden_slots: set[str] = set()
        self._offset = QPointF(0.0, 0.0)
        self._zoom = 1.0
        self._w = 1
        self._h = 1

    def width(self) -> int:
        return self._w

    def height(self) -> int:
        return self._h

    def _ensure_context(self, w: int, h: int) -> bool:
        if self._surface is None:
            fmt = QSurfaceFormat()
            fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
            fmt.setVersion(3, 3)
            fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
            fmt.setAlphaBufferSize(8)
            fmt.setDepthBufferSize(0)

            self._surface = QOffscreenSurface()
            self._surface.setFormat(fmt)
            self._surface.create()

            self._ctx = QOpenGLContext()
            self._ctx.setFormat(self._surface.requestedFormat())
            if not self._ctx.create():
                return False

        if not self._ctx.makeCurrent(self._surface):
            return False

        if self._prog is None:
            self._prog = QOpenGLShaderProgram()
            if not self._prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Vertex, _VERT
            ):
                return False
            if not self._prog.addShaderFromSourceCode(
                QOpenGLShader.ShaderTypeBit.Fragment, _FRAG
            ):
                return False
            if not self._prog.link():
                return False

            self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
            self._vbo.create()
            self._vao = QOpenGLVertexArrayObject()
            self._vao.create()

        if self._fbo is None or self._fbo_w != w or self._fbo_h != h:
            self._fbo = None
            fbo_fmt = QOpenGLFramebufferObjectFormat()
            fbo_fmt.setAttachment(QOpenGLFramebufferObject.Attachment.NoAttachment)
            self._fbo = QOpenGLFramebufferObject(w, h, fbo_fmt)
            self._fbo_w = w
            self._fbo_h = h

        return True

    @staticmethod
    def _pages_key(pages: list) -> tuple:
        return tuple(
            (
                id(page),
                getattr(page, "size", None),
                getattr(page, "mode", None),
            )
            if page is not None
            else None
            for page in (pages or [])
        )

    def _textures_for_pages(self, pages: list) -> dict[int, QOpenGLTexture]:
        key = self._pages_key(pages)
        cached = self._texture_cache.get(key)
        if cached is not None:
            if key in self._texture_cache_order:
                self._texture_cache_order.remove(key)
            self._texture_cache_order.append(key)
            return cached

        textures: dict[int, QOpenGLTexture] = {}
        for i, pil_img in enumerate(pages or []):
            if pil_img is None:
                continue
            qimg = self.pil_to_qimage(pil_img)
            tex = QOpenGLTexture(QOpenGLTexture.Target.Target2D)
            tex.create()
            tex.bind()
            tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
            tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
            tex.setData(qimg)
            tex.release()
            textures[i] = tex

        self._texture_cache[key] = textures
        self._texture_cache_order.append(key)
        while len(self._texture_cache_order) > self._texture_cache_limit:
            old_key = self._texture_cache_order.pop(0)
            old = self._texture_cache.pop(old_key, {})
            for tex in old.values():
                try:
                    tex.destroy()
                except Exception:
                    pass
        return textures

    def _render_qimage(self, items: list[dict], width: int, height: int) -> QImage | None:
        w, h = max(1, int(width)), max(1, int(height))
        if not items:
            return None
        if not self._ensure_context(w, h):
            return None
        if self._fbo is None or not self._fbo.bind():
            return None

        self._w = w
        self._h = h
        gl = self._ctx.functions()
        gl.glViewport(0, 0, w, h)
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glDisable(_GL_DEPTH_TEST)
        gl.glEnable(_GL_BLEND)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(_GL_COLOR_BUFFER_BIT)

        if self._vao is not None:
            self._vao.bind()
        try:
            for item in items:
                skeleton = item.get("skeleton")
                atlas = item.get("atlas") or {}
                pages = item.get("pil_pages") or []
                if skeleton is None or not atlas or not pages:
                    continue

                self._skeleton = skeleton
                self._atlas = atlas
                self._pil_pages = pages
                self._pma = bool(item.get("pma", False))
                self._active_skin = str(item.get("skin_name") or "default")
                self._hidden_slots = set(item.get("hidden_slots") or ())
                self._zoom = float(item.get("scale", 1.0) or 1.0)
                self._offset = QPointF(
                    w / 2 + float(item.get("offset_x", 0.0) or 0.0),
                    h / 2 - float(item.get("offset_y", 0.0) or 0.0),
                )
                self._gl_textures = self._textures_for_pages(pages)

                anim_name = str(item.get("anim_name") or "")
                if anim_name:
                    anim = skeleton.animations.get(anim_name)
                    if anim:
                        skeleton.apply_animation(anim, float(item.get("time", 0.0) or 0.0))

                if self._pma:
                    gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
                else:
                    gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
                if self._gl_textures:
                    self._draw_spine_gl(gl)
        finally:
            if self._vao is not None:
                self._vao.release()

        img = self._fbo.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        self._fbo.release()
        self._ctx.doneCurrent()
        return img

    def render_array(self, items: list[dict], width: int, height: int) -> np.ndarray | None:
        img = self._render_qimage(items, width, height)
        if img is None:
            return None
        arr = _qimage_to_rgba_array(img)
        if any(bool(item.get("pma", False)) for item in items):
            arr = _unpremultiply_rgba_array(arr)
        return np.ascontiguousarray(arr)

    def render(self, items: list[dict], width: int, height: int) -> Image.Image | None:
        img = self._render_qimage(items, width, height)
        if img is None:
            return None
        ptr = img.bits()
        data = bytes(ptr[: img.sizeInBytes()])
        pil = Image.frombytes(
            "RGBA",
            (int(img.width()), int(img.height())),
            data,
            "raw",
            "RGBA",
            int(img.bytesPerLine()),
            1,
        )
        if any(bool(item.get("pma", False)) for item in items):
            from app.spine_editor.spine_renderer import unpremultiply

            pil = unpremultiply(pil)
        return pil
