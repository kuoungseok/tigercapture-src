"""Optional OpenGL helpers for Painter preview surfaces.

Painter keeps CPU/QPainter fallbacks for reliability, but 3D blockout previews
should use OpenGL whenever the current Qt session can create a valid context.
The module is intentionally separate from ``app.drawing`` so the main Painter
window does not import PyOpenGL until a GPU preview is actually requested.
"""
from __future__ import annotations

import math
import numbers
import os
import ctypes
import operator
import sys
from typing import Any

import numpy as np
from PySide6.QtGui import QGuiApplication, QImage, QOffscreenSurface, QOpenGLContext, QSurfaceFormat

from app.painter_zoom import PAINTER_ZOOM_MAX_PERCENT


PAINTER_OPENGL_RENDERER_ID = "painter_blockout_opengl_offscreen_v1"
PAINTER_CANVAS_OPENGL_RENDERER_ID = "painter_canvas_opengl_stroke_fbo_v1"
PAINTER_CANVAS_ATLAS_RENDERER_ID = "painter_canvas_opengl_persistent_stroke_atlas_v1"
PAINTER_CANVAS_FALLBACK_RENDERER_ID = "painter_canvas_qpainter_strokes_v1"
# Only the default round QPen contract is pixel-semantically represented by
# both retained OpenGL paths. Other styles and authored dynamics fall back to
# the canonical QPainter renderer until their complete contracts are mapped.
_BASIC_CANVAS_STYLES = frozenset({"round"})
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
_GL_CLEANUP_STATUS: dict[str, Any] = {
    "failure_count": 0,
    "last_operation": "",
    "last_error": "",
    "primary_error_preserved": False,
}


def _strict_gl_real(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise PainterOpenGLUnavailable(f"Painter OpenGL {field} must be a real number.")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise PainterOpenGLUnavailable(f"Painter OpenGL {field} must be finite.")
    return resolved


def _strict_gl_range(
    value: object,
    *,
    field: str,
    minimum: float,
    maximum: float,
) -> float:
    resolved = _strict_gl_real(value, field=field)
    if not minimum <= resolved <= maximum:
        raise PainterOpenGLUnavailable(
            f"Painter OpenGL {field} must be between {minimum} and {maximum}."
        )
    return resolved


def _best_effort_gl_cleanup(operation: str, callback: Any) -> bool:
    """Run one teardown operation without replacing an active render error."""

    primary_error = sys.exc_info()[1]
    try:
        callback()
        return True
    except Exception as exc:
        _GL_CLEANUP_STATUS["failure_count"] = int(
            _GL_CLEANUP_STATUS.get("failure_count", 0)
        ) + 1
        _GL_CLEANUP_STATUS["last_operation"] = str(operation)
        _GL_CLEANUP_STATUS["last_error"] = f"{type(exc).__name__}: {exc}"
        _GL_CLEANUP_STATUS["primary_error_preserved"] = primary_error is not None
        if primary_error is not None and hasattr(primary_error, "add_note"):
            primary_error.add_note(
                f"Painter OpenGL cleanup failed during {operation}: "
                f"{type(exc).__name__}: {exc}"
            )
        return False


def painter_opengl_cleanup_status() -> dict[str, Any]:
    return dict(_GL_CLEANUP_STATUS)


class PainterOpenGLUnavailable(RuntimeError):
    """Raised when the optional Painter OpenGL path cannot be used."""


class PainterRetainedGLTileUploader:
    """Keep document tiles as real GL textures in one persistent offscreen context."""

    def __init__(self) -> None:
        if not painter_canvas_opengl_enabled() or QGuiApplication.instance() is None:
            raise PainterOpenGLUnavailable("Retained Painter GL tiles require an enabled Qt GUI application.")
        try:
            from OpenGL import GL
            from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLTexture
        except Exception as exc:
            raise PainterOpenGLUnavailable(f"PyOpenGL unavailable: {exc}") from exc
        fmt = QSurfaceFormat(); fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
        # The retained path uses core framebuffer entry points plus legacy
        # immediate-mode quads. Request a compatibility context new enough to
        # expose glGenFramebuffers; 2.1 succeeded as a Qt context on the native
        # QA host but PyOpenGL correctly reported that FBO entry point missing.
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile); fmt.setVersion(3, 3)
        self.surface = QOffscreenSurface(); self.surface.setFormat(fmt); self.surface.create()
        self.context = QOpenGLContext(); self.context.setFormat(fmt)
        if not self.surface.isValid() or not self.context.create() or not self.context.makeCurrent(self.surface):
            _best_effort_gl_cleanup("retained_surface_destroy", self.surface.destroy)
            raise PainterOpenGLUnavailable("Could not create a persistent Painter tile OpenGL context.")
        self.GL = GL; self.FBO = QOpenGLFramebufferObject; self.Texture = QOpenGLTexture
        self.qt_gl = self.context.functions()
        self.raw_gl = {}
        signatures = {
            "glViewport": (None, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int),
            "glDisable": (None, ctypes.c_uint), "glEnable": (None, ctypes.c_uint),
            "glBlendFunc": (None, ctypes.c_uint, ctypes.c_uint),
            "glClearColor": (None, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float),
            "glClear": (None, ctypes.c_uint), "glMatrixMode": (None, ctypes.c_uint),
            "glLoadIdentity": (None,),
            "glOrtho": (None, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double, ctypes.c_double),
            "glBindTexture": (None, ctypes.c_uint, ctypes.c_uint),
            "glTexParameteri": (None, ctypes.c_uint, ctypes.c_uint, ctypes.c_int),
            "glPixelStorei": (None, ctypes.c_uint, ctypes.c_int),
            "glTexImage2D": (None, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p),
            "glReadPixels": (None, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p),
            "glColor4f": (None, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float),
            "glBegin": (None, ctypes.c_uint), "glTexCoord2f": (None, ctypes.c_float, ctypes.c_float),
            "glVertex2f": (None, ctypes.c_float, ctypes.c_float), "glEnd": (None,), "glFlush": (None,),
        }
        for name, signature in signatures.items():
            address = int(self.context.getProcAddress(name.encode("ascii")) or 0)
            if not address:
                raise PainterOpenGLUnavailable(f"OpenGL entry point unavailable: {name}")
            restype, *argtypes = signature
            self.raw_gl[name] = ctypes.CFUNCTYPE(restype, *argtypes)(address)
        self.validation_fbo = QOpenGLFramebufferObject(1, 1)
        if not self.validation_fbo.isValid():
            raise PainterOpenGLUnavailable("Qt retained Painter tile FBO is invalid.")
        # Qt's Windows FBO wrapper can leave a driver diagnostic in the shared
        # error slot even though the object is valid. Clear that boundary once
        # so PyOpenGL does not attribute the stale code to the next texture call.
        while int(self.qt_gl.glGetError()) != int(GL.GL_NO_ERROR):
            pass
        self.fbo = 1; self.handles: set[int] = set(); self.texture_objects: dict[int, Any] = {}
        self.created = 0; self.updated = 0; self.uploaded_bytes = 0
        self.display_composites = 0; self.display_texture_reads = 0; self.display_readback_bytes = 0

    def _current(self) -> None:
        if not self.context.makeCurrent(self.surface):
            raise PainterOpenGLUnavailable("Could not activate retained Painter tile context.")

    def _clear_qt_boundary_errors(self) -> None:
        while int(self.qt_gl.glGetError()) != int(self.GL.GL_NO_ERROR):
            pass

    def _gl(self, name: str, *args) -> None:
        self.raw_gl[name](*args)

    def _read_rgba(self, width: int, height: int) -> QImage:
        payload = (ctypes.c_ubyte * (width * height * 4))()
        self._gl(
            "glReadPixels", 0, 0, width, height,
            self.GL.GL_RGBA, self.GL.GL_UNSIGNED_BYTE,
            ctypes.cast(payload, ctypes.c_void_p),
        )
        pixels = np.ctypeslib.as_array(payload).reshape((height, width, 4))
        flipped = np.ascontiguousarray(np.flipud(pixels))
        return QImage(flipped.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()

    def __call__(self, _key, image: QImage, existing_handle: int = 0) -> int:
        self._current(); GL = self.GL
        converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
        handle = int(existing_handle or 0)
        if not handle:
            texture = self.Texture(self.Texture.Target.Target2D)
            texture.create()
            if not texture.isCreated():
                raise PainterOpenGLUnavailable("Qt could not create retained Painter tile texture.")
            handle = int(texture.textureId()); self.texture_objects[handle] = texture
            self.handles.add(handle); self.created += 1
        else:
            texture = self.texture_objects.get(handle)
            if texture is None:
                raise PainterOpenGLUnavailable("Retained Painter tile texture owner is missing.")
            self.updated += 1
        raw = bytes(converted.constBits())
        payload = ctypes.create_string_buffer(raw)
        self._gl("glBindTexture", GL.GL_TEXTURE_2D, handle)
        self._gl("glTexParameteri", GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        self._gl("glTexParameteri", GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        self._gl("glTexParameteri", GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        self._gl("glTexParameteri", GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        self._gl("glPixelStorei", GL.GL_UNPACK_ALIGNMENT, 4)
        self._gl(
            "glTexImage2D", GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8,
            converted.width(), converted.height(), 0,
            GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, ctypes.cast(payload, ctypes.c_void_p),
        )
        self.uploaded_bytes += converted.width() * converted.height() * 4
        return handle

    def delete(self, handle: int) -> None:
        if not int(handle or 0): return
        self._current(); texture = self.texture_objects.pop(int(handle), None)
        self.handles.discard(int(handle))
        if texture is not None:
            texture.destroy()

    def composite_normal_layers(self, layers: list[tuple[QImage, float]], width: int, height: int) -> tuple[QImage, dict[str, Any]]:
        """Composite pre-masked normal-blend layers in the retained GL FBO."""
        self._current(); GL = self.GL; width, height = _validated_render_dimensions(width, height)
        output_fbo = self.FBO(width, height)
        temporary: list[int] = []
        try:
            if not output_fbo.isValid() or not output_fbo.bind():
                raise PainterOpenGLUnavailable("Painter compositor FBO is incomplete.")
            self._clear_qt_boundary_errors()
            self._gl("glViewport", 0, 0, width, height); self._gl("glDisable", GL.GL_DEPTH_TEST); self._gl("glEnable", GL.GL_BLEND)
            self._gl("glBlendFunc", GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
            self._gl("glClearColor", 0.0, 0.0, 0.0, 0.0); self._gl("glClear", GL.GL_COLOR_BUFFER_BIT)
            self._gl("glMatrixMode", GL.GL_PROJECTION); self._gl("glLoadIdentity"); self._gl("glOrtho", 0, width, height, 0, -1, 1)
            self._gl("glMatrixMode", GL.GL_MODELVIEW); self._gl("glLoadIdentity"); self._gl("glEnable", GL.GL_TEXTURE_2D)
            for index, (image, opacity) in enumerate(layers):
                handle = self((f"compose:{index}", 0, 0), image, 0); temporary.append(handle)
                output_fbo.bind()
                self._clear_qt_boundary_errors()
                layer_opacity = _strict_gl_range(
                    opacity,
                    field=f"normal layer {index} opacity",
                    minimum=0.0,
                    maximum=1.0,
                )
                self._gl("glBindTexture", GL.GL_TEXTURE_2D, handle); self._gl("glColor4f", 1.0, 1.0, 1.0, layer_opacity)
                self._gl("glBegin", GL.GL_QUADS)
                self._gl("glTexCoord2f", 0, 0); self._gl("glVertex2f", 0, 0)
                self._gl("glTexCoord2f", 1, 0); self._gl("glVertex2f", width, 0)
                self._gl("glTexCoord2f", 1, 1); self._gl("glVertex2f", width, height)
                self._gl("glTexCoord2f", 0, 1); self._gl("glVertex2f", 0, height)
                self._gl("glEnd")
            self._gl("glFlush"); result = self._read_rgba(width, height)
        finally:
            for handle in temporary:
                _best_effort_gl_cleanup(
                    "retained_compositor_texture_delete",
                    lambda handle=handle: self.delete(handle),
                )
            _best_effort_gl_cleanup(
                "retained_compositor_framebuffer_release", output_fbo.release
            )
        return result, {"renderer": "painter_retained_gl_normal_compositor_v1", "layers": len(layers), "mask_policy": "preapplied_alpha", "readback": True}

    def composite_tile_records(self, records, width: int, height: int, tile_size: int) -> tuple[QImage, dict[str, Any]]:
        """Consume retained texture handles into the actual Canvas display image."""
        self._current(); GL = self.GL
        width, height = _validated_render_dimensions(width, height)
        from app.painter_large_canvas import (
            MAX_TILE_SIZE,
            MIN_TILE_SIZE,
            _strict_bounded_resource_integer,
        )
        tile_size = _strict_bounded_resource_integer(
            tile_size,
            field="retained compositor tile_size",
            minimum=MIN_TILE_SIZE,
            maximum=MAX_TILE_SIZE,
        )
        output_fbo = self.FBO(width, height)
        reads = 0
        try:
            if not output_fbo.isValid() or not output_fbo.bind():
                raise PainterOpenGLUnavailable("Painter tile display FBO is incomplete.")
            self._clear_qt_boundary_errors()
            self._gl("glViewport", 0, 0, width, height); self._gl("glDisable", GL.GL_DEPTH_TEST); self._gl("glDisable", GL.GL_BLEND)
            self._gl("glClearColor", 0.0, 0.0, 0.0, 0.0); self._gl("glClear", GL.GL_COLOR_BUFFER_BIT)
            self._gl("glMatrixMode", GL.GL_PROJECTION); self._gl("glLoadIdentity"); self._gl("glOrtho", 0, width, height, 0, -1, 1)
            self._gl("glMatrixMode", GL.GL_MODELVIEW); self._gl("glLoadIdentity"); self._gl("glEnable", GL.GL_TEXTURE_2D)
            for tx, ty, record in records:
                if not int(record.gpu_handle or 0):
                    raise PainterOpenGLUnavailable("Retained tile has no GPU texture handle.")
                x0 = int(tx) * tile_size; y0 = int(ty) * tile_size
                x1 = min(width, x0 + record.image.width()); y1 = min(height, y0 + record.image.height())
                self._gl("glBindTexture", GL.GL_TEXTURE_2D, int(record.gpu_handle)); self._gl("glColor4f", 1.0, 1.0, 1.0, 1.0)
                self._gl("glBegin", GL.GL_QUADS)
                self._gl("glTexCoord2f", 0, 0); self._gl("glVertex2f", x0, y0)
                self._gl("glTexCoord2f", 1, 0); self._gl("glVertex2f", x1, y0)
                self._gl("glTexCoord2f", 1, 1); self._gl("glVertex2f", x1, y1)
                self._gl("glTexCoord2f", 0, 1); self._gl("glVertex2f", x0, y1)
                self._gl("glEnd"); reads += 1
            self._gl("glFlush"); result = self._read_rgba(width, height)
        finally:
            _best_effort_gl_cleanup(
                "retained_tile_framebuffer_release", output_fbo.release
            )
        self.display_composites += 1; self.display_texture_reads += reads; self.display_readback_bytes += width * height * 4
        return result, {"renderer": "painter_retained_gl_tile_display_v1", "tile_texture_reads": reads, "readback": True}

    def close(self) -> None:
        textures = list(self.texture_objects.values())
        self.handles.clear(); self.texture_objects.clear(); self.validation_fbo = None; self.fbo = 0
        if not _best_effort_gl_cleanup("retained_context_make_current", self._current):
            textures = []
        for texture in textures:
            _best_effort_gl_cleanup("retained_texture_destroy", texture.destroy)
        _best_effort_gl_cleanup("retained_context_done_current", self.context.doneCurrent)
        _best_effort_gl_cleanup("retained_surface_destroy", self.surface.destroy)

    def telemetry(self) -> dict[str, Any]:
        return {"schema": "tigerstudio.painter.gl-tile-uploader.v1", "active": True, "textures": len(self.handles), "fbo": bool(self.fbo), "created": self.created, "updated": self.updated, "uploaded_bytes": self.uploaded_bytes, "display_composites": self.display_composites, "display_texture_reads": self.display_texture_reads, "display_readback_bytes": self.display_readback_bytes}


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
        pyopengl_error = f"{type(exc).__name__}: {exc}"
    enabled = painter_opengl_enabled()
    dependency_ready = bool(enabled and app_ready and pyopengl_ready)
    return {
        "schema": "tigerstudio.painter.opengl.status.v1",
        "renderer": PAINTER_OPENGL_RENDERER_ID,
        "enabled": bool(enabled),
        "available": False,
        "dependency_ready": dependency_ready,
        "candidate_backend": PAINTER_OPENGL_RENDERER_ID if dependency_ready else "",
        "context_probe": "not_created_by_status_call",
        "fallback_on_context_failure": True,
        "remote_safe": True,
        "qt_app": bool(app_ready),
        "pyopengl": bool(pyopengl_ready),
        "pyopengl_error": pyopengl_error,
        "fallback_renderer": "painter_blockout_qpainter_v1",
        "active_backend": "painter_blockout_qpainter_v1",
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
        "cleanup": painter_opengl_cleanup_status(),
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
        pyopengl_error = f"{type(exc).__name__}: {exc}"
    dependency_ready = bool(enabled and app_ready and pyopengl_ready)
    try:
        capabilities = painter_canvas_gpu_capabilities()
        capabilities_error = ""
    except Exception as exc:
        capabilities = {
            "remote_safe": True,
            "persistent_stroke_atlas": {
                "enabled": False,
                "fallback_renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
            },
        }
        capabilities_error = f"{type(exc).__name__}: {exc}"
    return {
        "schema": "tigerstudio.painter.canvas.opengl.status.v1",
        "renderer": PAINTER_CANVAS_ATLAS_RENDERER_ID,
        "base_renderer": PAINTER_CANVAS_OPENGL_RENDERER_ID,
        "enabled": bool(enabled),
        "available": False,
        "dependency_ready": dependency_ready,
        "candidate_backend": PAINTER_CANVAS_ATLAS_RENDERER_ID if dependency_ready else "",
        "remote_safe": True,
        "fallback_renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
        "active_backend": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
        "fallback_on_context_failure": True,
        "capabilities": capabilities,
        "capabilities_error": capabilities_error,
        "supported_first_pass": dict(capabilities.get("basic_strokes") or {}),
        "next_gpu_target": "retained_gl_texture_display_and_textured_brush_shader_parity",
        "pyopengl": bool(pyopengl_ready),
        "pyopengl_error": pyopengl_error,
        "cleanup": painter_opengl_cleanup_status(),
    }


def painter_canvas_gpu_capabilities() -> dict[str, Any]:
    """Return the Painter canvas GPU contract visible to UI and automation."""

    from app.painter_large_canvas import DEFAULT_TILE_SIZE, MAX_TILE_SIZE, MIN_TILE_SIZE

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
            "next": "widget-native_zero-readback_texture_display",
        },
        "retained_document_tiles": {
            "enabled": True,
            "implementation": "PainterRetainedGLTileUploader",
            "tile_size": DEFAULT_TILE_SIZE,
            "default_tile_size": DEFAULT_TILE_SIZE,
            "supported_tile_size": [MIN_TILE_SIZE, MAX_TILE_SIZE],
            "runtime_tile_size_forwarded_to_compositor": True,
            "upload_policy": "dirty_tiles_only",
            "fbo_validation": True,
            "bounded_lru_cpu_mirror": True,
            "fallback_renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
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
            "max_zoom_percent": PAINTER_ZOOM_MAX_PERCENT,
            "pixel_grid": "dirty_region_qpainter_overlay",
            "stroke_cache": "signature_atlas_cache",
            "next": "widget-native_zero-readback_texture_display",
        },
    }


def _validated_render_dimensions(width: int, height: int) -> tuple[int, int]:
    try:
        if isinstance(width, bool) or isinstance(height, bool):
            raise TypeError
        target_w = operator.index(width)
        target_h = operator.index(height)
    except TypeError as exc:
        raise TypeError("Painter render dimensions must be finite integers") from exc
    if target_w <= 0 or target_h <= 0:
        raise ValueError("Painter render dimensions must be positive")
    return target_w, target_h


class _PainterCanvasOffscreenSession:
    """Own one Qt offscreen surface/context for a canvas atlas lifetime."""

    def __init__(self) -> None:
        self.surface: QOffscreenSurface | None = None
        self.context: QOpenGLContext | None = None
        self.context_creations = 0
        self.context_activation_failures = 0
        self.context_recoveries = 0
        self.context_recovery_failures = 0
        self.last_context_error = ""
        self.closed = False

    def _release_context(self, *, operation: str) -> None:
        context, surface = self.context, self.surface
        self.context = None
        self.surface = None
        if context is not None:
            _best_effort_gl_cleanup(f"{operation}_context_done_current", context.doneCurrent)
        if surface is not None:
            _best_effort_gl_cleanup(f"{operation}_surface_destroy", surface.destroy)

    def make_current(self) -> tuple[QOffscreenSurface, QOpenGLContext]:
        if self.closed:
            raise PainterOpenGLUnavailable("Painter canvas OpenGL session is closed.")
        activation_failed = False
        invalid_context = False
        if self.surface is None or self.context is None:
            self.surface, self.context = _make_offscreen_context()
            self.context_creations += 1
        else:
            is_valid = getattr(self.context, "isValid", None)
            invalid_context = callable(is_valid) and not bool(is_valid())
            activation_failed = invalid_context or not self.context.makeCurrent(
                self.surface
            )
        if activation_failed:
            self.context_activation_failures += 1
            self.last_context_error = (
                "QOpenGLContext.isValid returned false"
                if invalid_context
                else "QOpenGLContext.makeCurrent returned false"
            )
            self._release_context(operation="canvas_lost_context")
            try:
                self.surface, self.context = _make_offscreen_context()
                self.context_creations += 1
                self.context_recoveries += 1
            except Exception as exc:
                self.context_recovery_failures += 1
                self.last_context_error = f"{type(exc).__name__}: {exc}"
                raise PainterOpenGLUnavailable(
                    "Painter canvas OpenGL session could not recover its context."
                ) from exc
        return self.surface, self.context

    def done_current(self) -> None:
        if self.context is not None:
            self.context.doneCurrent()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._release_context(operation="canvas_session")

    def telemetry(self) -> dict[str, Any]:
        return {
            "closed": bool(self.closed),
            "context_creations": int(self.context_creations),
            "context_activation_failures": int(self.context_activation_failures),
            "context_recoveries": int(self.context_recoveries),
            "context_recovery_failures": int(self.context_recovery_failures),
            "last_context_error": str(self.last_context_error),
            "context_retained": self.context is not None,
            "surface_retained": self.surface is not None,
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
        self._session = _PainterCanvasOffscreenSession()

    def clear(self) -> None:
        self.signature = None
        self.image = None
        self.report = {}
        self.failed_signature = None

    def close(self) -> None:
        self.clear()
        self._session.close()

    def telemetry(self) -> dict[str, Any]:
        return {
            **self._session.telemetry(),
            "has_cached_image": isinstance(self.image, QImage) and not self.image.isNull(),
            "failed_signature": str(self.failed_signature or ""),
        }

    def render(
        self,
        strokes: list[Any],
        *,
        signature: str | None = None,
        width: int,
        height: int,
        time_ms: int,
        layer_visibility: dict[str, bool] | None = None,
        layer_opacity: dict[str, int] | None = None,
        layer_masks: dict[str, list[tuple[float, float]]] | None = None,
    ) -> tuple[QImage, dict[str, Any]]:
        if signature is None:
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
                _session=self._session,
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

    target_w, target_h = _validated_render_dimensions(width, height)
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
        _best_effort_gl_cleanup(
            "blockout_surface_destroy_after_context_create_failure",
            surface.destroy,
        )
        raise PainterOpenGLUnavailable("Painter OpenGL could not create a context.")
    if not context.makeCurrent(surface):
        _best_effort_gl_cleanup(
            "blockout_surface_destroy_after_context_activation_failure",
            surface.destroy,
        )
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
        if color_texture:
            _best_effort_gl_cleanup(
                "blockout_color_texture_delete",
                lambda: GL.glDeleteTextures(1, [int(color_texture)]),
            )
        if depth_buffer:
            _best_effort_gl_cleanup(
                "blockout_depth_buffer_delete",
                lambda: GL.glDeleteRenderbuffers(1, [int(depth_buffer)]),
            )
        if fbo:
            _best_effort_gl_cleanup(
                "blockout_framebuffer_delete",
                lambda: GL.glDeleteFramebuffers(1, [int(fbo)]),
            )
        _best_effort_gl_cleanup(
            "blockout_default_framebuffer_bind",
            lambda: GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0),
        )
        _best_effort_gl_cleanup("blockout_context_done_current", context.doneCurrent)
        _best_effort_gl_cleanup("blockout_surface_destroy", surface.destroy)
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

    target_w, target_h = _validated_render_dimensions(width, height)
    h = hashlib.blake2b(digest_size=16)
    h.update(str(target_w).encode("ascii"))
    h.update(b"x")
    h.update(str(target_h).encode("ascii"))
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
        h.update(f":{float(getattr(stroke, 'width_px', 1.0)):.3f}".encode("ascii"))
        h.update(f":{int(getattr(stroke, 'opacity', 255))}".encode("ascii"))
        color = tuple(getattr(stroke, "color", (255, 255, 255)) or (255, 255, 255))
        h.update((":%s" % ",".join(str(int(c)) for c in color[:3])).encode("ascii", "ignore"))
        h.update(f":closed={bool(getattr(stroke, 'closed_path', False))}".encode("ascii"))
        for x, y in list(getattr(stroke, "points", []) or []):
            h.update(f";{float(x):.5f},{float(y):.5f}".encode("ascii"))
        dynamics = dict(getattr(stroke, "brush_dynamics", {}) or {})
        dynamic_enabled = bool(dynamics.get("enabled", False))
        h.update(f":dynamics={dynamic_enabled}".encode("ascii"))
        if dynamic_enabled:
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
    _session: _PainterCanvasOffscreenSession | None = None,
) -> tuple[QImage, dict[str, Any]]:
    """Render GL-supported Painter strokes into a transparent QImage.

    This first pass deliberately supports only basic strokes whose visual
    contract maps cleanly to simple GL lines/points. Complex brushes, masks,
    and custom tip dynamics raise ``PainterOpenGLUnavailable`` so the maintained
    QPainter stroke path preserves exact artwork.
    """

    target_w, target_h = _validated_render_dimensions(width, height)
    if not painter_canvas_opengl_enabled():
        raise PainterOpenGLUnavailable("Painter canvas OpenGL is disabled.")
    if QGuiApplication.instance() is None:
        raise PainterOpenGLUnavailable("Painter canvas OpenGL requires a running Qt application.")
    visible = _collect_canvas_gpu_strokes(
        list(strokes or []),
        width=target_w,
        height=target_h,
        time_ms=int(time_ms or 0),
        layer_visibility=dict(layer_visibility or {}),
        layer_opacity=dict(layer_opacity or {}),
        layer_masks=dict(layer_masks or {}),
    )

    owns_session = _session is None
    session = _session or _PainterCanvasOffscreenSession()
    _surface, context = session.make_current()
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtOpenGL import QOpenGLFramebufferObject, QOpenGLPaintDevice

    fbo = None
    try:
        # Qt resolves framebuffer entry points against the QOpenGLContext. This
        # avoids PyOpenGL's platform loader returning a null glGenFramebuffers
        # even while the Qt context itself supports FBOs.
        fbo = QOpenGLFramebufferObject(target_w, target_h)
        if not fbo.isValid() or not fbo.bind():
            raise PainterOpenGLUnavailable("Painter canvas OpenGL framebuffer is incomplete.")

        device = QOpenGLPaintDevice(target_w, target_h)
        painter = QPainter(device)
        if not painter.isActive():
            raise PainterOpenGLUnavailable("Painter canvas could not activate the Qt OpenGL paint engine.")
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        painter.fillRect(QRectF(0, 0, target_w, target_h), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for row in visible:
            points = [QPointF(float(x), float(y)) for x, y in row.get("points", [])]
            if not points:
                continue
            rgba = tuple(row.get("color") or (1.0, 1.0, 1.0, 1.0))
            color = QColor.fromRgbF(*rgba)
            widths = list(row.get("dynamic_widths", []) or [])
            base_width = float(row["width"])
            if len(points) == 1:
                painter.setPen(QPen(color, widths[0] if widths else base_width))
                painter.drawPoint(points[0])
                continue
            pairs = list(zip(range(len(points) - 1), range(1, len(points))))
            if bool(row.get("closed", False)) and len(points) >= 3:
                pairs.append((len(points) - 1, 0))
            for first, second in pairs:
                width = base_width
                if widths:
                    width = (widths[first] + widths[second]) * 0.5
                pen = QPen(color, width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawLine(points[first], points[second])
        painter.end()
        image = fbo.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        report = {
            "renderer": PAINTER_CANVAS_OPENGL_RENDERER_ID,
            "active": "opengl",
            "fallback": False,
            "surface": "offscreen_fbo",
            "size": [target_w, target_h],
            "stroke_count": len(visible),
            "supported_first_pass": True,
            "backend": "qt_opengl_paint_device",
        }
    finally:
        if fbo is not None:
            _best_effort_gl_cleanup("canvas_framebuffer_release", fbo.release)
            fbo = None
        if owns_session:
            _best_effort_gl_cleanup("canvas_session_close", session.close)
        else:
            _best_effort_gl_cleanup("canvas_context_done_current", session.done_current)
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
        _best_effort_gl_cleanup(
            "canvas_surface_destroy_after_context_create_failure",
            surface.destroy,
        )
        raise PainterOpenGLUnavailable("Painter OpenGL could not create a context.")
    if not context.makeCurrent(surface):
        _best_effort_gl_cleanup(
            "canvas_surface_destroy_after_context_activation_failure",
            surface.destroy,
        )
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
        value = _strict_gl_range(
            face.get("depth_value", 1.0),
            field="blockout depth value",
            minimum=0.0,
            maximum=1.0,
        )
        opacity = _strict_gl_range(
            face.get("opacity", 1.0),
            field="blockout face opacity",
            minimum=0.0,
            maximum=1.0,
        )
        rgba = (value, value, value, opacity)
    else:
        rgba = _hex_to_rgba(
            str(face.get("color") or "#F2F2F2"),
            _strict_gl_range(
                face.get("opacity", 1.0),
                field="blockout face opacity",
                minimum=0.0,
                maximum=1.0,
            ),
        )
    shade = _strict_gl_range(
        face.get("shade", 1.0),
        field="blockout face shade",
        minimum=0.0,
        maximum=1.0,
    )
    fog = 0.0 if bool(face.get("depth_preview", False)) else _strict_gl_range(
        face.get("fog", 0.0),
        field="blockout face fog",
        minimum=0.0,
        maximum=0.75,
    )
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
    opacity = _strict_gl_range(
        shadow.get("opacity", 0.25),
        field="blockout shadow opacity",
        minimum=0.0,
        maximum=0.5,
    )
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
    except ValueError:
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
        if bool(dict(getattr(stroke, "brush_dynamics", {}) or {}).get("enabled", False)):
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL does not yet handle authored brush dynamics."
            )
        points = []
        for point_index, (x, y) in enumerate(
            list(getattr(stroke, "points", []) or [])
        ):
            x_norm = _strict_gl_range(
                x,
                field=f"stroke point {point_index} x",
                minimum=0.0,
                maximum=1.0,
            )
            y_norm = _strict_gl_range(
                y,
                field=f"stroke point {point_index} y",
                minimum=0.0,
                maximum=1.0,
            )
            points.append((x_norm * float(width), y_norm * float(height)))
        if not points:
            continue
        from app.painter_brush_domains import BRUSH_WIDTH_RANGE_PX

        try:
            raw_width = getattr(stroke, "width_px", None)
            if isinstance(raw_width, bool) or not isinstance(raw_width, numbers.Real):
                raise TypeError("width must be a real number")
            base_width = float(raw_width)
            if not math.isfinite(base_width):
                raise ValueError("width must be finite")
        except (TypeError, ValueError, OverflowError) as exc:
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL received an invalid brush width."
            ) from exc
        if not BRUSH_WIDTH_RANGE_PX[0] <= base_width <= BRUSH_WIDTH_RANGE_PX[1]:
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL cannot preserve a stroke width outside the "
                "published GPU brush domain; use the canonical CPU renderer."
            )
        dynamic_widths: list[float] = []
        color = tuple(getattr(stroke, "color", (255, 255, 255)) or (255, 255, 255))
        try:
            stroke_opacity = operator.index(getattr(stroke, "opacity", 255))
            resolved_layer_opacity = operator.index(layer_opacity.get(layer_id, 100))
        except TypeError as exc:
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL received a non-integer opacity."
            ) from exc
        if isinstance(getattr(stroke, "opacity", 255), bool) or isinstance(
            layer_opacity.get(layer_id, 100), bool
        ):
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL received a non-integer opacity."
            )
        if not 0 <= stroke_opacity <= 255 or not 0 <= resolved_layer_opacity <= 100:
            raise PainterOpenGLUnavailable(
                "Painter canvas OpenGL received opacity outside its document domain."
            )
        alpha = (stroke_opacity / 255.0) * (resolved_layer_opacity / 100.0)
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
    line_width = float(stroke["width"])
    dynamic_widths = list(stroke.get("dynamic_widths", []) or [])
    GL.glLineWidth(line_width)
    GL.glPointSize(dynamic_widths[0] if dynamic_widths else line_width)
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
    "PainterRetainedGLTileUploader",
    "canvas_stroke_gpu_signature",
    "painter_canvas_opengl_enabled",
    "painter_canvas_gpu_capabilities",
    "painter_canvas_opengl_status",
    "painter_opengl_enabled",
    "painter_opengl_status",
    "render_blockout_scene_opengl_qimage",
    "render_canvas_strokes_opengl_qimage",
]
