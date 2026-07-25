"""Optional OpenGL helpers for Painter preview surfaces.

Painter keeps CPU/QPainter fallbacks for reliability, but 3D blockout previews
should use OpenGL whenever the current Qt session can create a valid context.
The module is intentionally separate from ``app.drawing`` so the main Painter
window does not import PyOpenGL until a GPU preview is actually requested.
"""
from __future__ import annotations

import math
import os
from typing import Any

import numpy as np
from PySide6.QtGui import QGuiApplication, QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat


PAINTER_OPENGL_RENDERER_ID = "painter_blockout_opengl_offscreen_v1"
PAINTER_CANVAS_OPENGL_RENDERER_ID = "painter_canvas_opengl_stroke_fbo_v1"
PAINTER_CANVAS_ATLAS_RENDERER_ID = "painter_canvas_opengl_persistent_stroke_atlas_v1"
PAINTER_CANVAS_FALLBACK_RENDERER_ID = "painter_canvas_qpainter_strokes_v1"
_BASIC_CANVAS_STYLES = frozenset({"round", "marker", "highlighter"})
_TEXTURED_CANVAS_STYLES = frozenset(
    {
        "real_wet_oil",
        "loaded_oil",
        "impasto_oil",
        "oil_smear",
        "soft_oil_glaze",
        "bristle_oil",
        "dry_oil",
        "palette_knife",
        "textured_chalk",
    }
)


class PainterOpenGLUnavailable(RuntimeError):
    """Raised when the optional Painter OpenGL path cannot be used."""


def painter_opengl_enabled() -> bool:
    value = str(os.environ.get("TIGERCAPTURE_PAINTER_OPENGL", "auto")).strip().casefold()
    return value not in {"0", "false", "no", "off", "disabled", "cpu", "qpainter"}


def painter_canvas_opengl_enabled() -> bool:
    value = str(os.environ.get("TIGERCAPTURE_PAINTER_CANVAS_OPENGL", "auto")).strip().casefold()
    if value in {"0", "false", "no", "off", "disabled", "cpu", "qpainter"}:
        return False
    return painter_opengl_enabled()


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
            "paint_canvas": "opengl_persistent_stroke_atlas_if_supported",
        },
        "canvas": painter_canvas_opengl_status(),
    }


def painter_canvas_opengl_status() -> dict[str, Any]:
    enabled = painter_canvas_opengl_enabled()
    app_ready = QGuiApplication.instance() is not None
    try:
        from OpenGL import GL  # noqa: F401

        pyopengl_ready = True
        pyopengl_error = ""
    except Exception as exc:
        pyopengl_ready = False
        pyopengl_error = str(exc)
    return {
        "schema": "tigerstudio.painter.canvas.opengl.status.v1",
        "renderer": PAINTER_CANVAS_ATLAS_RENDERER_ID,
        "base_renderer": PAINTER_CANVAS_OPENGL_RENDERER_ID,
        "enabled": bool(enabled),
        "available": bool(enabled and app_ready and pyopengl_ready),
        "remote_safe": True,
        "fallback_renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
        "fallback_on_context_failure": True,
        "capabilities": painter_canvas_gpu_capabilities(),
        "supported_first_pass": painter_canvas_gpu_capabilities()["basic_strokes"],
        "next_gpu_target": "retained_gl_texture_display_and_textured_brush_shader_parity",
        "pyopengl": bool(pyopengl_ready),
        "pyopengl_error": pyopengl_error,
    }


def painter_canvas_gpu_capabilities() -> dict[str, Any]:
    """Return the Painter canvas GPU contract visible to UI and automation."""

    return {
        "schema": "tigerstudio.painter.canvas.gpu.capabilities.v1",
        "remote_safe": True,
        "persistent_stroke_atlas": {
            "enabled": True,
            "renderer": PAINTER_CANVAS_ATLAS_RENDERER_ID,
            "base_renderer": PAINTER_CANVAS_OPENGL_RENDERER_ID,
            "readback_policy": "only_when_stroke_signature_changes",
            "cache_scope": "active_canvas_session",
            "fallback_renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
            "next": "retained_gl_context_texture_display",
        },
        "basic_strokes": {
            "stroke_styles": sorted(_BASIC_CANVAS_STYLES),
            "unsupported_falls_back": True,
            "layer_masks": "fallback",
            "textured_brushes": "fallback",
            "tip_dynamics": "fallback",
        },
        "texture_brush_gpu_parity": {
            "target_styles": sorted(_TEXTURED_CANVAS_STYLES),
            "current": "qpainter_fallback",
            "shader_plan": "dab_atlas_noise_texture_brush_stamp_shader",
            "parity_contract": "gpu_path_must_match_qpainter_preview_before_enable",
        },
        "layer_compositing": {
            "visibility": "contracted",
            "opacity": "contracted",
            "blend_modes": ["normal"],
            "masks": "qpainter_fallback_until_mask_shader",
            "shader_plan": "per_layer_fbo_opacity_blend_mask_shader",
        },
        "high_zoom_canvas": {
            "max_zoom_percent": 800,
            "pixel_grid": "dirty_region_qpainter_overlay",
            "stroke_cache": "signature_atlas_cache",
            "next": "gpu_texture_display_dirty_region_upload",
        },
    }


class PainterCanvasStrokeAtlas:
    """Session-local cache for the canvas GL stroke image.

    The current Qt widget still paints the cached result through QPainter, but
    this keeps the GL readback to signature changes and gives the next retained
    texture/FBO pass a stable contract to replace internally.
    """

    def __init__(self) -> None:
        self.signature: str | None = None
        self.image: QImage | None = None
        self.report: dict[str, Any] = {}
        self.failed_signature: str | None = None

    def clear(self) -> None:
        self.signature = None
        self.image = None
        self.report = {}
        self.failed_signature = None

    def render(
        self,
        strokes: list[Any],
        *,
        width: int,
        height: int,
        time_ms: int,
        layer_visibility: dict[str, bool] | None = None,
        layer_opacity: dict[str, int] | None = None,
        layer_masks: dict[str, list[tuple[float, float]]] | None = None,
    ) -> tuple[QImage, dict[str, Any]]:
        signature = canvas_stroke_gpu_signature(
            list(strokes or []),
            width=width,
            height=height,
            time_ms=time_ms,
            layer_visibility=layer_visibility,
            layer_opacity=layer_opacity,
            layer_masks=layer_masks,
        )
        if signature and signature == self.failed_signature:
            raise PainterOpenGLUnavailable("Painter canvas atlas skipped a known failing stroke signature.")
        if (
            signature
            and signature == self.signature
            and isinstance(self.image, QImage)
            and not self.image.isNull()
        ):
            report = {
                **dict(self.report or {}),
                "renderer": PAINTER_CANVAS_ATLAS_RENDERER_ID,
                "source_renderer": self.report.get("source_renderer", PAINTER_CANVAS_OPENGL_RENDERER_ID),
                "active": "opengl",
                "fallback": False,
                "cache_hit": True,
                "persistent_atlas": True,
                "readback": False,
                "readback_policy": "only_when_stroke_signature_changes",
                "signature": signature,
            }
            return self.image, report

        try:
            image, report = render_canvas_strokes_opengl_qimage(
                list(strokes or []),
                width=width,
                height=height,
                time_ms=time_ms,
                layer_visibility=layer_visibility,
                layer_opacity=layer_opacity,
                layer_masks=layer_masks,
            )
        except Exception:
            self.failed_signature = signature
            raise
        if image.isNull():
            self.failed_signature = signature
            raise PainterOpenGLUnavailable("Painter canvas atlas received an empty GL render.")

        source_renderer = str(dict(report or {}).get("renderer") or PAINTER_CANVAS_OPENGL_RENDERER_ID)
        atlas_report = {
            **dict(report or {}),
            "renderer": PAINTER_CANVAS_ATLAS_RENDERER_ID,
            "source_renderer": source_renderer,
            "cache_hit": False,
            "persistent_atlas": True,
            "readback": True,
            "readback_policy": "only_when_stroke_signature_changes",
            "signature": signature,
        }
        self.signature = signature
        self.image = image
        self.report = dict(atlas_report)
        self.failed_signature = None
        return image, atlas_report


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
    fmt.setDepthBufferSize(24)
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
    depth_buffer = 0
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
        depth_buffer = int(GL.glGenRenderbuffers(1))
        GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, depth_buffer)
        GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT24, target_w, target_h)
        GL.glFramebufferRenderbuffer(
            GL.GL_FRAMEBUFFER,
            GL.GL_DEPTH_ATTACHMENT,
            GL.GL_RENDERBUFFER,
            depth_buffer,
        )
        if int(GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)) != int(GL.GL_FRAMEBUFFER_COMPLETE):
            raise PainterOpenGLUnavailable("Painter OpenGL framebuffer is incomplete.")

        GL.glViewport(0, 0, target_w, target_h)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glEnable(GL.GL_BLEND)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glEnable(GL.GL_POINT_SMOOTH)
        GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
        GL.glHint(GL.GL_POINT_SMOOTH_HINT, GL.GL_NICEST)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClearDepth(1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        scene_payload = projection.get("scene") if isinstance(projection.get("scene"), dict) else {}
        depth_range = projection.get("depth_range") or {}
        for tile in projection.get("floor_tiles", []) or []:
            _draw_floor_tile(GL, tile, target_w, target_h, depth_range)
        if bool(scene_payload.get("show_grid", True)) and not bool(scene_payload.get("show_floor", False)):
            _draw_grid(GL, target_w, target_h)
        GL.glDisable(GL.GL_DEPTH_TEST)
        for shadow in projection.get("shadows", []) or []:
            _draw_shadow(GL, shadow, target_w, target_h, depth_range)
        GL.glEnable(GL.GL_DEPTH_TEST)
        for face in projection.get("faces", []) or []:
            _draw_face(GL, face, target_w, target_h, depth_range)
        for edge in projection.get("edges", []) or []:
            _draw_edge(GL, edge, target_w, target_h, depth_range)
        GL.glFlush()

        raw = GL.glReadPixels(0, 0, target_w, target_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((target_h, target_w, 4))
        flipped = np.ascontiguousarray(np.flipud(pixels))
        image = QImage(flipped.data, target_w, target_h, 4 * target_w, QImage.Format.Format_RGBA8888).copy()
    finally:
        try:
            if color_texture:
                GL.glDeleteTextures(1, [int(color_texture)])
            if depth_buffer:
                GL.glDeleteRenderbuffers(1, [int(depth_buffer)])
            if fbo:
                GL.glDeleteFramebuffers(1, [int(fbo)])
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        except Exception:
            pass
        context.doneCurrent()
        surface.destroy()
    return image


def canvas_stroke_gpu_signature(
    strokes: list[Any],
    *,
    width: int,
    height: int,
    time_ms: int,
    layer_visibility: dict[str, bool] | None = None,
    layer_opacity: dict[str, int] | None = None,
    layer_masks: dict[str, list[tuple[float, float]]] | None = None,
) -> str:
    """Return a stable signature for the current GL-renderable stroke layer."""

    import hashlib

    h = hashlib.blake2b(digest_size=16)
    h.update(str(max(1, int(width or 1))).encode("ascii"))
    h.update(b"x")
    h.update(str(max(1, int(height or 1))).encode("ascii"))
    h.update(b"@")
    h.update(str(int(time_ms or 0)).encode("ascii"))
    visibility = dict(layer_visibility or {})
    opacity = dict(layer_opacity or {})
    masks = dict(layer_masks or {})
    for stroke in list(strokes or []):
        layer_id = _stroke_layer_id(stroke)
        if not visibility.get(layer_id, True):
            continue
        if len(masks.get(layer_id, []) or []) >= 3:
            h.update(f"|mask:{layer_id}".encode("utf-8", "ignore"))
        if not _stroke_is_active(stroke, int(time_ms or 0)):
            continue
        h.update(f"|layer:{layer_id}:{opacity.get(layer_id, 100)}".encode("utf-8", "ignore"))
        h.update(_stroke_style(stroke).encode("ascii", "ignore"))
        h.update(f":{float(getattr(stroke, 'width_px', 1.0) or 1.0):.3f}".encode("ascii"))
        h.update(f":{int(getattr(stroke, 'opacity', 255) or 255)}".encode("ascii"))
        color = tuple(getattr(stroke, "color", (255, 255, 255)) or (255, 255, 255))
        h.update((":%s" % ",".join(str(int(c)) for c in color[:3])).encode("ascii", "ignore"))
        h.update(f":closed={bool(getattr(stroke, 'closed_path', False))}".encode("ascii"))
        for x, y in list(getattr(stroke, "points", []) or []):
            h.update(f";{float(x):.5f},{float(y):.5f}".encode("ascii"))
        for channel in (
            "point_pressure",
            "point_tilt_x",
            "point_tilt_y",
            "point_rotation",
            "point_tangential_pressure",
        ):
            values = list(getattr(stroke, channel, []) or [])
            h.update(f":{channel}=".encode("ascii"))
            h.update(",".join(f"{float(value):.4f}" for value in values).encode("ascii"))
    return h.hexdigest()


def render_canvas_strokes_opengl_qimage(
    strokes: list[Any],
    *,
    width: int,
    height: int,
    time_ms: int,
    layer_visibility: dict[str, bool] | None = None,
    layer_opacity: dict[str, int] | None = None,
    layer_masks: dict[str, list[tuple[float, float]]] | None = None,
) -> tuple[QImage, dict[str, Any]]:
    """Render GL-supported Painter strokes into a transparent QImage.

    This first pass deliberately supports only basic strokes whose visual
    contract maps cleanly to simple GL lines/points. Complex brushes, masks,
    and custom tip dynamics raise ``PainterOpenGLUnavailable`` so the maintained
    QPainter stroke path preserves exact artwork.
    """

    if not painter_canvas_opengl_enabled():
        raise PainterOpenGLUnavailable("Painter canvas OpenGL is disabled.")
    if QGuiApplication.instance() is None:
        raise PainterOpenGLUnavailable("Painter canvas OpenGL requires a running Qt application.")
    try:
        from OpenGL import GL
    except Exception as exc:
        raise PainterOpenGLUnavailable(f"Painter canvas OpenGL requires PyOpenGL: {exc}") from exc

    target_w = max(1, int(width or 1))
    target_h = max(1, int(height or 1))
    visible = _collect_canvas_gpu_strokes(
        list(strokes or []),
        width=target_w,
        height=target_h,
        time_ms=int(time_ms or 0),
        layer_visibility=dict(layer_visibility or {}),
        layer_opacity=dict(layer_opacity or {}),
        layer_masks=dict(layer_masks or {}),
    )

    surface, context = _make_offscreen_context()
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
            raise PainterOpenGLUnavailable("Painter canvas OpenGL framebuffer is incomplete.")

        GL.glViewport(0, 0, target_w, target_h)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glEnable(GL.GL_BLEND)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glEnable(GL.GL_POINT_SMOOTH)
        GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
        GL.glHint(GL.GL_POINT_SMOOTH_HINT, GL.GL_NICEST)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)

        for row in visible:
            _draw_canvas_stroke(GL, row, target_w, target_h)
        GL.glFlush()

        raw = GL.glReadPixels(0, 0, target_w, target_h, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
        pixels = np.frombuffer(raw, dtype=np.uint8).reshape((target_h, target_w, 4))
        flipped = np.ascontiguousarray(np.flipud(pixels))
        image = QImage(flipped.data, target_w, target_h, 4 * target_w, QImage.Format.Format_RGBA8888).copy()
        report = {
            "renderer": PAINTER_CANVAS_OPENGL_RENDERER_ID,
            "active": "opengl",
            "fallback": False,
            "surface": "offscreen_fbo",
            "size": [target_w, target_h],
            "stroke_count": len(visible),
            "supported_first_pass": True,
        }
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
    return image, report


def _make_offscreen_context() -> tuple[QOffscreenSurface, QOpenGLContext]:
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
    return surface, context


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


def _draw_face(
    GL: Any,
    face: dict[str, Any],
    width: int,
    height: int,
    depth_range: dict[str, Any],
) -> None:
    if bool(face.get("depth_preview", False)):
        value = max(0.0, min(1.0, float(face.get("depth_value", 1.0) or 1.0)))
        rgba = (value, value, value, float(face.get("opacity", 1.0) or 1.0))
    else:
        rgba = _hex_to_rgba(str(face.get("color") or "#F2F2F2"), float(face.get("opacity", 1.0) or 1.0))
    shade = max(0.0, min(1.0, float(face.get("shade", 1.0) or 1.0)))
    fog = 0.0 if bool(face.get("depth_preview", False)) else max(0.0, min(0.75, float(face.get("fog", 0.0) or 0.0)))
    fog_rgb = (58 / 255.0, 60 / 255.0, 63 / 255.0)
    shade = 1.0 if bool(face.get("depth_preview", False)) else shade
    rgba = (
        rgba[0] * shade * (1.0 - fog) + fog_rgb[0] * fog,
        rgba[1] * shade * (1.0 - fog) + fog_rgb[1] * fog,
        rgba[2] * shade * (1.0 - fog) + fog_rgb[2] * fog,
        rgba[3],
    )
    GL.glColor4f(*rgba)
    GL.glBegin(GL.GL_POLYGON)
    try:
        points = face.get("points", []) or []
        depths = face.get("point_depths", []) or []
        fallback_depth = float(face.get("depth", 0.0) or 0.0)
        for index, (x, y) in enumerate(points):
            depth = float(depths[index]) if index < len(depths) else fallback_depth
            _gl_vertex_depth(GL, float(x), float(y), depth, width, height, depth_range)
    finally:
        GL.glEnd()


def _draw_floor_tile(
    GL: Any,
    tile: dict[str, Any],
    width: int,
    height: int,
    depth_range: dict[str, Any],
) -> None:
    rgba = _hex_to_rgba(str(tile.get("color") or "#707276"), 1.0)
    GL.glColor4f(*rgba)
    GL.glBegin(GL.GL_POLYGON)
    try:
        points = tile.get("points", []) or []
        depths = tile.get("point_depths", []) or []
        fallback_depth = float(tile.get("depth", 0.0) or 0.0)
        for index, (x, y) in enumerate(points):
            depth = float(depths[index]) if index < len(depths) else fallback_depth
            _gl_vertex_depth(GL, float(x), float(y), depth, width, height, depth_range)
    finally:
        GL.glEnd()


def _draw_shadow(
    GL: Any,
    shadow: dict[str, Any],
    width: int,
    height: int,
    depth_range: dict[str, Any],
) -> None:
    from math import cos, pi, sin

    polygon = shadow.get("polygon") or []
    depth = float(shadow.get("depth", 0.0) or 0.0)
    opacity = max(0.0, min(0.5, float(shadow.get("opacity", 0.25) or 0.25)))
    if len(polygon) >= 3:
        GL.glColor4f(0.0, 0.0, 0.0, opacity)
        GL.glBegin(GL.GL_POLYGON)
        try:
            for x, y in polygon:
                _gl_vertex(GL, float(x), float(y), width, height)
        finally:
            GL.glEnd()
        return
    rect = shadow.get("rect")
    if not isinstance(rect, (list, tuple)) or len(rect) < 4:
        return
    x, y, rect_w, rect_h = (float(value) for value in rect[:4])
    cx = x + rect_w * 0.5
    cy = y + rect_h * 0.5
    GL.glColor4f(0.0, 0.0, 0.0, opacity)
    GL.glBegin(GL.GL_TRIANGLE_FAN)
    try:
        _gl_vertex(GL, cx, cy, width, height)
        for index in range(25):
            angle = 2.0 * pi * index / 24.0
            _gl_vertex(
                GL,
                cx + cos(angle) * rect_w * 0.5,
                cy + sin(angle) * rect_h * 0.5,
                width,
                height,
            )
    finally:
        GL.glEnd()


def _draw_edge(
    GL: Any,
    edge: dict[str, Any],
    width: int,
    height: int,
    depth_range: dict[str, Any],
) -> None:
    a = edge.get("a")
    b = edge.get("b")
    if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) < 2 or len(b) < 2:
        return
    GL.glLineWidth(1.35)
    GL.glColor4f(0.96, 0.975, 1.0, 0.72)
    GL.glBegin(GL.GL_LINES)
    try:
        depth = max(0.0, float(edge.get("depth", 0.0) or 0.0) - 0.004)
        _gl_vertex_depth(GL, float(a[0]), float(a[1]), depth, width, height, depth_range)
        _gl_vertex_depth(GL, float(b[0]), float(b[1]), depth, width, height, depth_range)
    finally:
        GL.glEnd()


def _gl_vertex(GL: Any, x: float, y: float, width: int, height: int) -> None:
    GL.glVertex2f((float(x) / max(1.0, float(width))) * 2.0 - 1.0, 1.0 - (float(y) / max(1.0, float(height))) * 2.0)


def _gl_vertex_depth(
    GL: Any,
    x: float,
    y: float,
    depth: float,
    width: int,
    height: int,
    depth_range: dict[str, Any],
) -> None:
    near = float(depth_range.get("near", 0.05) or 0.05)
    far = max(near + 0.001, float(depth_range.get("far", near + 1.0) or near + 1.0))
    camera_depth = max(near, min(far, float(depth)))
    # The X/Y coordinates are already perspective projected. Use the matching
    # reciprocal camera-depth mapping so intersecting face triangles agree
    # with the depth buffer instead of producing linear-depth wedges.
    depth_ndc = (
        (far + near) / (far - near)
        - (2.0 * far * near) / (camera_depth * (far - near))
    )
    GL.glVertex3f(
        (float(x) / max(1.0, float(width))) * 2.0 - 1.0,
        1.0 - (float(y) / max(1.0, float(height))) * 2.0,
        max(-1.0, min(1.0, depth_ndc)),
    )


def _hex_to_rgba(value: str, opacity: float) -> tuple[float, float, float, float]:
    text = str(value or "#F2F2F2").strip()
    if not (text.startswith("#") and len(text) == 7):
        text = "#F2F2F2"
    try:
        r = int(text[1:3], 16) / 255.0
        g = int(text[3:5], 16) / 255.0
        b = int(text[5:7], 16) / 255.0
    except Exception:
        r, g, b = (242 / 255.0, 242 / 255.0, 242 / 255.0)
    a = max(0.05, min(1.0, float(opacity)))
    return (r, g, b, a)


def _collect_canvas_gpu_strokes(
    strokes: list[Any],
    *,
    width: int,
    height: int,
    time_ms: int,
    layer_visibility: dict[str, bool],
    layer_opacity: dict[str, int],
    layer_masks: dict[str, list[tuple[float, float]]],
) -> list[dict[str, Any]]:
    visible: list[dict[str, Any]] = []
    for stroke in strokes:
        if not _stroke_is_active(stroke, time_ms):
            continue
        layer_id = _stroke_layer_id(stroke)
        if not layer_visibility.get(layer_id, True):
            continue
        if len(layer_masks.get(layer_id, []) or []) >= 3:
            raise PainterOpenGLUnavailable("Painter canvas OpenGL does not yet handle layer masks.")
        style = _stroke_style(stroke)
        if style not in _BASIC_CANVAS_STYLES:
            raise PainterOpenGLUnavailable(f"Painter canvas OpenGL unsupported brush style: {style}")
        if not _stroke_tip_is_default(stroke):
            raise PainterOpenGLUnavailable("Painter canvas OpenGL does not yet handle tip dynamics.")
        points = [
            (
                max(0.0, min(1.0, float(x))) * float(width),
                max(0.0, min(1.0, float(y))) * float(height),
            )
            for x, y in list(getattr(stroke, "points", []) or [])
        ]
        if not points:
            continue
        from app.painter_brush_engine_v2 import normalize_curve, normalize_signed_curve

        point_count = len(points)
        pressure = normalize_curve(
            getattr(stroke, "point_pressure", []) or [],
            point_count,
            1.0,
        )
        tilt_x = normalize_signed_curve(
            getattr(stroke, "point_tilt_x", []) or [],
            point_count,
        )
        tilt_y = normalize_signed_curve(
            getattr(stroke, "point_tilt_y", []) or [],
            point_count,
        )
        base_width = max(1.0, float(getattr(stroke, "width_px", 1.0) or 1.0))
        points = [
            (
                point[0] + tilt_x[index] * base_width * 0.10,
                point[1] + tilt_y[index] * base_width * 0.10,
            )
            for index, point in enumerate(points)
        ]
        dynamic_widths = [
            base_width
            * (0.18 + pressure[index] * 0.82)
            * (1.0 + min(1.0, math.hypot(tilt_x[index], tilt_y[index])) * 0.24)
            for index in range(point_count)
        ]
        color = tuple(getattr(stroke, "color", (255, 255, 255)) or (255, 255, 255))
        alpha = max(0.0, min(1.0, float(getattr(stroke, "opacity", 255) or 255) / 255.0))
        alpha *= max(0.0, min(1.0, float(layer_opacity.get(layer_id, 100)) / 100.0))
        if style == "highlighter":
            alpha = min(alpha, 110.0 / 255.0)
        visible.append(
            {
                "points": points,
                "color": (
                    max(0, min(255, int(color[0] if len(color) > 0 else 255))) / 255.0,
                    max(0, min(255, int(color[1] if len(color) > 1 else 255))) / 255.0,
                    max(0, min(255, int(color[2] if len(color) > 2 else 255))) / 255.0,
                    alpha,
                ),
                "width": base_width,
                "dynamic_widths": dynamic_widths,
                "closed": bool(getattr(stroke, "closed_path", False)),
                "style": style,
            }
        )
    return visible


def _draw_canvas_stroke(GL: Any, stroke: dict[str, Any], width: int, height: int) -> None:
    points = list(stroke.get("points", []) or [])
    if not points:
        return
    rgba = tuple(stroke.get("color") or (1.0, 1.0, 1.0, 1.0))
    GL.glColor4f(float(rgba[0]), float(rgba[1]), float(rgba[2]), float(rgba[3]))
    line_width = max(1.0, float(stroke.get("width", 1.0) or 1.0))
    if str(stroke.get("style") or "") == "marker":
        line_width *= 1.08
    dynamic_widths = list(stroke.get("dynamic_widths", []) or [])
    GL.glLineWidth(line_width)
    GL.glPointSize(max(1.0, dynamic_widths[0] if dynamic_widths else line_width))
    if len(points) == 1:
        GL.glBegin(GL.GL_POINTS)
        try:
            _gl_vertex(GL, float(points[0][0]), float(points[0][1]), width, height)
        finally:
            GL.glEnd()
        return
    if dynamic_widths:
        pairs = list(zip(range(len(points) - 1), range(1, len(points))))
        if bool(stroke.get("closed", False)) and len(points) >= 3:
            pairs.append((len(points) - 1, 0))
        for first_index, second_index in pairs:
            GL.glLineWidth(
                max(
                    1.0,
                    (dynamic_widths[first_index] + dynamic_widths[second_index]) * 0.5,
                )
            )
            GL.glBegin(GL.GL_LINES)
            try:
                for point_index in (first_index, second_index):
                    _gl_vertex(
                        GL,
                        float(points[point_index][0]),
                        float(points[point_index][1]),
                        width,
                        height,
                    )
            finally:
                GL.glEnd()
    else:
        GL.glBegin(GL.GL_LINE_LOOP if bool(stroke.get("closed", False)) else GL.GL_LINE_STRIP)
        try:
            for x, y in points:
                _gl_vertex(GL, float(x), float(y), width, height)
        finally:
            GL.glEnd()
    GL.glBegin(GL.GL_POINTS)
    try:
        for x, y in points:
            _gl_vertex(GL, float(x), float(y), width, height)
    finally:
        GL.glEnd()


def _stroke_is_active(stroke: Any, time_ms: int) -> bool:
    active = getattr(stroke, "is_active", None)
    if callable(active):
        return bool(active(int(time_ms or 0)))
    start_ms = int(getattr(stroke, "start_ms", 0) or 0)
    end_ms = getattr(stroke, "end_ms", None)
    if int(time_ms or 0) < start_ms:
        return False
    if end_ms is not None and int(time_ms or 0) >= int(end_ms):
        return False
    return True


def _stroke_layer_id(stroke: Any) -> str:
    return str(getattr(stroke, "layer_id", "paint-layer-1") or "paint-layer-1")


def _stroke_style(stroke: Any) -> str:
    return str(getattr(stroke, "brush_style", "round") or "round").strip().casefold().replace("-", "_").replace(" ", "_")


def _stroke_tip_is_default(stroke: Any) -> bool:
    return not any(
        (
            int(getattr(stroke, "brush_hardness", 100) or 100) != 100,
            int(getattr(stroke, "brush_spacing", 25) or 25) != 25,
            int(getattr(stroke, "brush_angle", 0) or 0) != 0,
            int(getattr(stroke, "brush_roundness", 100) or 100) != 100,
            bool(getattr(stroke, "brush_flip_x", False)),
            bool(getattr(stroke, "brush_flip_y", False)),
        )
    )


__all__ = [
    "PAINTER_CANVAS_ATLAS_RENDERER_ID",
    "PAINTER_CANVAS_FALLBACK_RENDERER_ID",
    "PAINTER_CANVAS_OPENGL_RENDERER_ID",
    "PAINTER_OPENGL_RENDERER_ID",
    "PainterCanvasStrokeAtlas",
    "PainterOpenGLUnavailable",
    "canvas_stroke_gpu_signature",
    "painter_canvas_opengl_enabled",
    "painter_canvas_gpu_capabilities",
    "painter_canvas_opengl_status",
    "painter_opengl_enabled",
    "painter_opengl_status",
    "render_blockout_scene_opengl_qimage",
    "render_canvas_strokes_opengl_qimage",
]
