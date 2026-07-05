"""Live2D actor track — data model for animated 2D characters on the timeline."""
from __future__ import annotations
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, NamedTuple


# ── interpolation curves ──────────────────────────────────────────────────────

def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

def _ease_in(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t

def _ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 2

_CURVES = {
    "linear":    lambda t: max(0.0, min(1.0, t)),
    "smoothstep": _smoothstep,
    "ease_in":   _ease_in,
    "ease_out":  _ease_out,
}


def _log_live2d_load(original_path: str, runtime_path: str) -> None:
    msg = f"[live2d load] source={original_path!r} runtime={runtime_path!r}"
    try:
        print(msg, flush=True)
    except Exception:
        pass
    try:
        from app.paths import runtime_log_dir

        with (runtime_log_dir() / "tigercapture.log").open("a", encoding="utf-8", errors="replace") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def apply_curve(t: float, curve: str) -> float:
    return _CURVES.get(curve, _smoothstep)(t)


# ── transform keyframes ───────────────────────────────────────────────────────

@dataclass
class Live2DKeyframe:
    """Single keyframe for one animated property on a clip."""
    time_ms: int     # ms relative to clip start (0 = clip start)
    value:   float
    curve:   str = "linear"   # linear | smoothstep | ease_in | ease_out


def _eval_keyframes(keyframes: list, time_ms: int, default: float) -> float:
    """Interpolate keyframe value at time_ms. Returns default if no keyframes."""
    if not keyframes:
        return default
    kfs = sorted(keyframes, key=lambda k: k.time_ms)
    if time_ms <= kfs[0].time_ms:
        return kfs[0].value
    if time_ms >= kfs[-1].time_ms:
        return kfs[-1].value
    for i in range(len(kfs) - 1):
        k0, k1 = kfs[i], kfs[i + 1]
        if k0.time_ms <= time_ms <= k1.time_ms:
            span = max(1, k1.time_ms - k0.time_ms)
            t = apply_curve((time_ms - k0.time_ms) / span, k0.curve)
            return k0.value + (k1.value - k0.value) * t
    return default


def _coerce_keyframe(value: Any) -> Optional[Live2DKeyframe]:
    """Accept dataclass or persisted-dict keyframes."""
    if isinstance(value, Live2DKeyframe):
        return value
    if isinstance(value, Mapping):
        try:
            return Live2DKeyframe(
                time_ms=max(0, int(value.get("time_ms", 0) or 0)),
                value=float(value.get("value", 0.0) or 0.0),
                curve=str(value.get("curve", "linear") or "linear"),
            )
        except Exception:
            return None
    try:
        return Live2DKeyframe(
            time_ms=max(0, int(getattr(value, "time_ms", 0) or 0)),
            value=float(getattr(value, "value", 0.0) or 0.0),
            curve=str(getattr(value, "curve", "linear") or "linear"),
        )
    except Exception:
        return None


def _eval_parameter_keyframes(parameter_tracks: Mapping[str, Any] | None, time_ms: int) -> dict[str, float]:
    """Evaluate arbitrary Live2D parameter tracks at a clip-local time."""
    values: dict[str, float] = {}
    if not isinstance(parameter_tracks, Mapping):
        return values
    for raw_param_id, raw_keys in parameter_tracks.items():
        param_id = str(raw_param_id or "").strip()
        if not param_id:
            continue
        if isinstance(raw_keys, Mapping):
            raw_iterable = raw_keys.get("keyframes") or raw_keys.get("keys") or []
        else:
            raw_iterable = raw_keys or []
        if not isinstance(raw_iterable, (list, tuple)):
            continue
        kfs = [kf for kf in (_coerce_keyframe(row) for row in raw_iterable) if kf is not None]
        if not kfs:
            continue
        values[param_id] = float(_eval_keyframes(kfs, int(time_ms), kfs[0].value))
    return values


# ── blend result ──────────────────────────────────────────────────────────────

class ClipWeight(NamedTuple):
    clip:   "Live2DActorClip"
    weight: float   # 0.0 – 1.0


# ── offscreen renderer (singleton per process) ────────────────────────────────

class _OffscreenRenderer:
    """
    QOffscreenSurface + QOpenGLContext for rendering Live2D to PIL images.
    Must be created on the main thread; render() can be called from any thread
    by bouncing through QMetaObject.invokeMethod with BlockingQueued connection.
    """
    _instance: Optional[_OffscreenRenderer] = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> _OffscreenRenderer:
        if cls._instance is None:
            cls._instance = _OffscreenRenderer()
        return cls._instance

    def __init__(self):
        self._backend    = ""
        self._surface    = None
        self._ctx        = None
        self._fbo        = None
        self._glfw       = None
        self._glfw_window = None
        self._gl_fbo     = 0
        self._gl_color_tex = 0
        self._gl_depth_rb = 0
        self._fbo_w      = 0
        self._fbo_h      = 0
        self._l2d_ready  = False
        self._model_sizes: dict[tuple[str, int], tuple[int, int]] = {}
        self._support_errors: dict[str, str] = {}
        self._normalized_paths: dict[str, str] = {}
        self._models: dict[str, object] = {}  # (model_path, clip_key) → LAppModel

    # ── GL setup ──────────────────────────────────────────────────────────

    def _ensure_gl(self, w: int, h: int) -> bool:
        backend = os.environ.get("TIGERCAPTURE_LIVE2D_RENDER_BACKEND", "glfw").strip().lower()
        if backend in {"qt", "qt_offscreen", "qoffscreen"}:
            return self._ensure_qt_gl(w, h)
        return self._ensure_glfw_gl(w, h)

    def _ensure_glfw_gl(self, w: int, h: int) -> bool:
        try:
            import glfw
            from OpenGL import GL

            w = max(1, int(w))
            h = max(1, int(h))
            if self._glfw_window is None:
                if not glfw.init():
                    return False
                glfw.window_hint(glfw.VISIBLE, False)
                glfw.window_hint(glfw.ALPHA_BITS, 8)
                glfw.window_hint(glfw.DEPTH_BITS, 24)
                glfw.window_hint(glfw.STENCIL_BITS, 8)
                glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_COMPAT_PROFILE)
                glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
                glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
                self._glfw_window = glfw.create_window(
                    max(16, w), max(16, h), "Tiger Studio Live2D Renderer", None, None
                )
                if self._glfw_window is None:
                    return False
                self._glfw = glfw
                self._backend = "glfw"

            glfw.make_context_current(self._glfw_window)
            if not self._l2d_ready:
                import live2d.v3 as l2d
                try:
                    l2d.init()
                except Exception:
                    pass
                l2d.glInit()
                self._l2d_ready = True

            if self._gl_fbo <= 0:
                self._gl_fbo = int(GL.glGenFramebuffers(1))
                self._gl_color_tex = int(GL.glGenTextures(1))
                self._gl_depth_rb = int(GL.glGenRenderbuffers(1))

            if self._fbo_w != w or self._fbo_h != h:
                self._fbo_w = w
                self._fbo_h = h
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._gl_fbo)
                GL.glBindTexture(GL.GL_TEXTURE_2D, self._gl_color_tex)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
                GL.glTexImage2D(
                    GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0,
                    GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None
                )
                GL.glFramebufferTexture2D(
                    GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0,
                    GL.GL_TEXTURE_2D, self._gl_color_tex, 0
                )
                GL.glBindRenderbuffer(GL.GL_RENDERBUFFER, self._gl_depth_rb)
                GL.glRenderbufferStorage(GL.GL_RENDERBUFFER, GL.GL_DEPTH24_STENCIL8, w, h)
                GL.glFramebufferRenderbuffer(
                    GL.GL_FRAMEBUFFER, GL.GL_DEPTH_STENCIL_ATTACHMENT,
                    GL.GL_RENDERBUFFER, self._gl_depth_rb
                )
                status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                if status != GL.GL_FRAMEBUFFER_COMPLETE:
                    print(f"[live2d offscreen] GLFW FBO incomplete: {status}")
                    return False

            return True
        except Exception as e:
            print(f"[live2d offscreen] GLFW GL init error: {e}")
            return False

    def _ensure_qt_gl(self, w: int, h: int) -> bool:
        try:
            from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat
            from PySide6.QtOpenGL import (QOpenGLFramebufferObject,
                                           QOpenGLFramebufferObjectFormat)

            if self._surface is None:
                fmt = QSurfaceFormat()
                fmt.setDepthBufferSize(24)
                fmt.setAlphaBufferSize(8)
                self._surface = QOffscreenSurface()
                self._surface.setFormat(fmt)
                self._surface.create()

                self._ctx = QOpenGLContext()
                self._ctx.setFormat(self._surface.requestedFormat())
                if not self._ctx.create():
                    return False

            if QOpenGLContext.currentContext() is not self._ctx:
                if not self._ctx.makeCurrent(self._surface):
                    return False
            self._backend = "qt"

            if not self._l2d_ready:
                import live2d.v3 as l2d
                try:
                    l2d.init()
                except Exception:
                    pass
                # Always call glInit() for this context — it sets both shader
                # programs AND per-context GL state (blending, etc.).
                # With setShareContext, shader programs are in the share group
                # so the latest IDs are valid in all contexts.
                l2d.glInit()
                self._l2d_ready = True

            if self._fbo is None or self._fbo_w != w or self._fbo_h != h:
                fbo_fmt = QOpenGLFramebufferObjectFormat()
                fbo_fmt.setAttachment(
                    QOpenGLFramebufferObject.Attachment.CombinedDepthStencil
                )
                self._fbo = QOpenGLFramebufferObject(w, h, fbo_fmt)
                self._fbo_w = w
                self._fbo_h = h

            return True
        except Exception as e:
            print(f"[live2d offscreen] GL init error: {e}")
            return False

    def _normalize_model_path(self, model_path: str) -> str:
        cached = self._normalized_paths.get(model_path)
        if cached is not None:
            return cached
        normalized = model_path
        try:
            from app.live2d.compat import normalize_live2d_model_path
            normalized = normalize_live2d_model_path(model_path) or model_path
        except Exception:
            pass
        self._normalized_paths[model_path] = normalized
        return normalized

    def _get_model(self, model_path: str, w: int, h: int, clip_key: int = 0):
        """Return a model instance. clip_key=0 means shared (used by blending)."""
        import live2d.v3 as l2d
        original_path = model_path
        model_path = self._normalize_model_path(model_path)
        key = (model_path, clip_key)
        m = self._models.get(key)
        if m is None:
            _log_live2d_load(original_path, model_path)
            m = l2d.LAppModel()
            m.LoadModelJson(model_path)
            m.Resize(w, h)
            self._models[key] = m
            self._model_sizes[key] = (w, h)
        elif self._model_sizes.get(key) != (w, h):
            try:
                m.Resize(w, h)
            except Exception:
                pass
            self._model_sizes[key] = (w, h)
        return m

    def _support_error(self, model_path: str) -> str:
        key = self._normalize_model_path(model_path)
        cached = self._support_errors.get(key)
        if cached is not None:
            return cached
        error = ""
        try:
            from app.live2d.compat import model_support_error
            error = model_support_error(key)
        except Exception:
            pass
        self._support_errors[key] = error
        return error

    def _make_current(self) -> bool:
        if self._backend == "glfw" and self._glfw is not None and self._glfw_window is not None:
            self._glfw.make_context_current(self._glfw_window)
            return True
        if self._ctx is not None and self._surface is not None:
            return bool(self._ctx.makeCurrent(self._surface))
        return False

    def _done_current(self) -> None:
        try:
            if self._backend == "glfw" and self._glfw is not None:
                self._glfw.make_context_current(None)
            elif self._ctx is not None:
                self._ctx.doneCurrent()
        except Exception:
            pass

    def _begin_frame(self, w: int, h: int):
        if self._backend == "glfw":
            from OpenGL import GL
            GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, self._gl_fbo)
            GL.glViewport(0, 0, int(w), int(h))
            GL.glColorMask(True, True, True, True)
            GL.glClearColor(0.0, 0.0, 0.0, 0.0)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT | GL.GL_STENCIL_BUFFER_BIT)
            GL.glEnable(GL.GL_BLEND)
            GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
            return None
        self._fbo.bind()
        gl = self._ctx.functions()
        gl.glViewport(0, 0, int(w), int(h))
        gl.glClearColor(0, 0, 0, 0)
        gl.glClear(0x4000 | 0x0100)
        return gl

    def _color_mask_rgba(self) -> None:
        if self._backend == "glfw":
            from OpenGL import GL
            GL.glColorMask(True, True, True, True)
            return
        if self._ctx is not None:
            self._ctx.functions().glColorMask(True, True, True, True)

    def _finish_frame_before_read(self) -> None:
        if self._backend == "glfw":
            from OpenGL import GL
            GL.glFlush()
            return
        if self._fbo is not None:
            self._fbo.release()

    def _unbind_frame_after_read(self) -> None:
        if self._backend == "glfw":
            try:
                from OpenGL import GL
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            except Exception:
                pass

    def evict_model(self, model_path: str, clip_key: int = 0) -> None:
        """Drop a cached Live2D model while the offscreen GL context is current."""
        model_path = self._normalize_model_path(model_path)
        key = (model_path, clip_key)
        with self._lock:
            try:
                self._make_current()
                self._models.pop(key, None)
                self._model_sizes.pop(key, None)
            finally:
                self._done_current()

    def _fbo_to_rgba(self, w: int, h: int, opacity: float):
        """Read current FBO contents as numpy RGBA array."""
        import numpy as np
        if self._backend == "glfw":
            from OpenGL import GL
            raw = GL.glReadPixels(0, 0, int(w), int(h), GL.GL_RGBA, GL.GL_UNSIGNED_BYTE)
            arr = np.frombuffer(raw, dtype=np.uint8).reshape(int(h), int(w), 4).copy()
            rgba = np.flipud(arr)
            rgba[:, :, 3] = (rgba[:, :, 3] * opacity).astype(np.uint8)
            return rgba
        img_qt = self._fbo.toImage()
        ptr = img_qt.constBits()
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape(h, w, 4).copy()
        rgba = np.empty_like(arr)
        rgba[:, :, 0] = arr[:, :, 2]
        rgba[:, :, 1] = arr[:, :, 1]
        rgba[:, :, 2] = arr[:, :, 0]
        rgba[:, :, 3] = (arr[:, :, 3] * opacity).astype(np.uint8)
        return rgba

    # ── single-clip render ────────────────────────────────────────────────

    def render_on_main(self, model_path: str, w: int, h: int,
                        motion_group: str, motion_idx: int,
                        n_updates: int, pos_x: float, pos_y: float,
                        scale: float, opacity: float,
                        clip_key: int = 0,
                        start_motion: bool = False,
                        expression_id: str = "",
                        parameter_values: Mapping[str, float] | None = None):
        """Render one frame. Returns RGBA PIL Image or None. Call from main thread."""
        from PIL import Image

        with self._lock:
            if not self._ensure_gl(w, h):
                return None
            try:
                if self._support_error(model_path):
                    self._done_current()
                    return None

                self._begin_frame(w, h)

                model = self._get_model(model_path, w, h, clip_key)

                # Start motion on first render or after reset
                if start_motion and motion_group:
                    try:
                        import live2d.v3 as _l2d
                        model.StartMotion(motion_group, motion_idx,
                                          _l2d.MotionPriority.FORCE)
                    except Exception:
                        pass
                if expression_id:
                    try:
                        model.SetExpression(str(expression_id))
                    except Exception:
                        pass

                if scale != 1.0:
                    model.SetScale(scale)
                dx = (pos_x - 0.5) * 2.0
                dy = -(pos_y - 0.5) * 2.0
                model.SetOffset(dx, dy)
                # Live2D SDK disables alpha writes (glColorMask alpha=False)
                # internally. Re-enable so the FBO alpha channel is captured.
                self._color_mask_rgba()
                for _ in range(max(0, n_updates)):
                    model.Update()
                if parameter_values:
                    for param_id, value in dict(parameter_values).items():
                        try:
                            model.SetParameterValue(str(param_id), float(value))
                        except Exception:
                            continue
                model.Draw()
                # Restore — re-enable alpha after draw in case it was changed
                self._color_mask_rgba()

                self._finish_frame_before_read()
                rgba = self._fbo_to_rgba(w, h, opacity)
                self._unbind_frame_after_read()
                return Image.fromarray(rgba, "RGBA")
            except Exception as e:
                print(f"[live2d offscreen] render error: {e}")
                self._done_current()
                return None

    # ── parameter-level blend render (same model) ─────────────────────────

    def render_blended_on_main(self,
                                model_path: str,
                                w: int, h: int,
                                updates_a: int, motion_group_a: str,
                                pos_x_a: float, pos_y_a: float, scale_a: float,
                                updates_b: int, motion_group_b: str,
                                pos_x_b: float, pos_y_b: float, scale_b: float,
                                t: float,
                                opacity: float) -> "PIL.Image | None":
        """
        Blend two expressions of the *same* model at parameter level.

        Strategy:
          1. Advance model to state A, capture parameter snapshot.
          2. Advance model to state B, capture parameter snapshot.
          3. Lerp all parameters with smoothstep(t).
          4. Apply blended params, render once.

        pos_x/y and scale are also lerped so the actor can drift smoothly.
        """
        import numpy as np
        from PIL import Image

        with self._lock:
            if not self._ensure_gl(w, h):
                return None
            try:
                model = self._get_model(model_path, w, h)

                # ── snapshot A ────────────────────────────────────────────
                for _ in range(max(1, updates_a)):
                    model.Update()
                try:
                    params_a = list(model.GetParameterValues())
                except AttributeError:
                    params_a = None  # library doesn't expose params → pixel crossfade

                # ── snapshot B ────────────────────────────────────────────
                for _ in range(max(1, updates_b)):
                    model.Update()
                try:
                    params_b = list(model.GetParameterValues())
                except AttributeError:
                    params_b = None

                # ── blend params (parameter-level) ────────────────────────
                if params_a is not None and params_b is not None:
                    n = min(len(params_a), len(params_b))
                    blended = [params_a[i] * (1.0 - t) + params_b[i] * t
                               for i in range(n)]
                    try:
                        model.SetParameterValues(blended)
                    except AttributeError:
                        # SetParameterValues not available — set individually
                        for i, v in enumerate(blended):
                            try:
                                model.SetParameterValue(i, v)
                            except Exception:
                                break

                # ── lerp position / scale ─────────────────────────────────
                pos_x = pos_x_a * (1.0 - t) + pos_x_b * t
                pos_y = pos_y_a * (1.0 - t) + pos_y_b * t
                scale = scale_a * (1.0 - t) + scale_b * t

                model.SetScale(scale)
                dx = (pos_x - 0.5) * 2.0
                dy = -(pos_y - 0.5) * 2.0
                model.SetOffset(dx, dy)

                # ── render ────────────────────────────────────────────────
                self._begin_frame(w, h)
                self._color_mask_rgba()
                model.Draw()
                self._color_mask_rgba()
                self._finish_frame_before_read()

                rgba = self._fbo_to_rgba(w, h, opacity)
                self._unbind_frame_after_read()
                return Image.fromarray(rgba, "RGBA")

            except Exception as e:
                print(f"[live2d offscreen] blend render error: {e}")
                self._done_current()
                return None

    # ── pixel-level crossfade (different models or library fallback) ──────

    def render_crossfade_on_main(self,
                                  clip_a: "Live2DActorClip",
                                  clip_b: "Live2DActorClip",
                                  w: int, h: int, t: float) -> "PIL.Image | None":
        """Alpha-composite clip_a and clip_b with weight t (0=A, 1=B)."""
        import numpy as np
        from PIL import Image

        img_a = clip_a.render_frame(w, h, clip_a._last_render_ms)
        img_b = clip_b.render_frame(w, h, clip_b._last_render_ms)
        if img_a is None and img_b is None:
            return None
        if img_a is None:
            return img_b
        if img_b is None:
            return img_a

        arr_a = np.asarray(img_a, dtype=np.float32)
        arr_b = np.asarray(img_b, dtype=np.float32)
        blended = (arr_a * (1.0 - t) + arr_b * t).clip(0, 255).astype(np.uint8)
        return Image.fromarray(blended, "RGBA")


# ── data model ────────────────────────────────────────────────────────────────

@dataclass
class Live2DActorClip:
    """One Live2D animation clip placed on the timeline."""
    model_path:   str   = ""          # .model3.json
    motion_group: str   = "Idle"
    motion_idx:   int   = 0
    expression_id: str  = ""
    start_ms:     int   = 0
    duration_ms:  int   = 3000
    loop:         bool  = True
    pos_x:        float = 0.5         # normalized (0=left, 1=right)
    pos_y:        float = 0.5         # normalized (0=top, 1=bottom)
    scale:        float = 1.0
    opacity:      float = 1.0

    # Per-property keyframe tracks (time_ms relative to clip start)
    kf_pos_x:   list = field(default_factory=list)   # list[Live2DKeyframe]
    kf_pos_y:   list = field(default_factory=list)
    kf_scale:   list = field(default_factory=list)
    kf_opacity: list = field(default_factory=list)

    # Blend handles — how long the fade-in / fade-out takes at this clip's edges
    blend_in_ms:  int   = 0           # 0 = no fade-in
    blend_out_ms: int   = 0           # 0 = no fade-out
    blend_curve:  str   = "smoothstep"  # "linear" | "smoothstep" | "ease_in" | "ease_out"

    # Arbitrary Live2D parameter tracks keyed by Cubism parameter id. These are
    # evaluated after the authored motion update and before draw, so they can
    # layer face/gesture/hand-authored corrections on top of a selected motion.
    parameter_keyframes: dict = field(default_factory=dict)

    # Offline video/webcam retarget payloads. Transform keyframes above are the
    # broad actor movement path; mocap parameter payloads are renderable too and
    # can drive model parameters such as ParamAngleX / ParamBodyAngleX.
    mocap_source_path: str = ""
    mocap_backend: str = ""
    mocap_payload: dict = field(default_factory=dict)
    mocap_parameter_keyframes: dict = field(default_factory=dict)
    mocap_parameter_aliases: dict = field(default_factory=dict)
    mocap_subject_type: str = ""
    mocap_movement_constraints: dict = field(default_factory=dict)
    mocap_events: list = field(default_factory=list)
    motion_storyboard_payload: dict = field(default_factory=dict)
    # Performance Source framing payloads are camera/placement guidance from
    # VTuber source tracking. They are stored separately from mocap so Program
    # Output never needs to render the source video directly.
    performance_source_path: str = ""
    performance_source_framing_payload: dict = field(default_factory=dict)
    performance_source_framing_keyframes: dict = field(default_factory=dict)
    performance_source_model_view: dict = field(default_factory=dict)
    performance_source_track_rotation: list = field(default_factory=list)
    performance_source_subject_type: str = ""
    performance_source_mapping_constraints: dict = field(default_factory=dict)

    # Runtime state (not serialized)
    _last_render_ms:       int  = field(default=-1,    repr=False, compare=False)
    _accum_updates:        int  = field(default=0,     repr=False, compare=False)
    _motion_started:       bool = field(default=False, repr=False, compare=False)
    _model_motion_started: bool = field(default=False, repr=False, compare=False)

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.duration_ms

    def _tick(self, pos_ms: int) -> int:
        """Update internal time state. Returns update steps for this frame."""
        FPS = 60.0
        MAX_UPDATES_PER_RENDER = 4
        anim_ms = pos_ms - self.start_ms
        if anim_ms < 0:
            return 0
        if self._last_render_ms < 0 or pos_ms < self._last_render_ms:
            updates = 1
            self._accum_updates = 0
            self._motion_started = False
        else:
            delta_ms = pos_ms - self._last_render_ms
            if delta_ms <= 0 and self._motion_started:
                updates = 0
            else:
                updates = max(1, int(round(delta_ms / 1000.0 * FPS)))
            updates = min(MAX_UPDATES_PER_RENDER, updates)
            self._accum_updates += updates
        self._last_render_ms = pos_ms
        self._motion_started = True
        return updates

    def parameter_values_at(self, pos_ms: int) -> dict[str, float]:
        """Return Live2D parameter overrides for a timeline position."""
        anim_ms = max(0, int(pos_ms) - int(self.start_ms))
        values: dict[str, float] = {}
        values.update(_eval_parameter_keyframes(self.parameter_keyframes, anim_ms))
        # Mocap wins when it drives the same parameter as a generic/manual track.
        values.update(_eval_parameter_keyframes(self.mocap_parameter_keyframes, anim_ms))
        return values

    def render_frame(self, width: int, height: int, pos_ms: int):
        """
        Return RGBA PIL Image at pos_ms. Main thread only.
        Uses full opacity — caller applies blend weight separately if needed.
        """
        if not self.model_path:
            return None
        need_start = not self._model_motion_started
        n = self._tick(pos_ms)
        if n == 0 and pos_ms < self.start_ms:
            return None
        # Evaluate keyframe-animated properties
        anim_ms = max(0, pos_ms - self.start_ms)
        cur_pos_x   = _eval_keyframes(self.kf_pos_x,   anim_ms, self.pos_x)
        cur_pos_y   = _eval_keyframes(self.kf_pos_y,   anim_ms, self.pos_y)
        cur_scale   = _eval_keyframes(self.kf_scale,   anim_ms, self.scale)
        cur_opacity = _eval_keyframes(self.kf_opacity, anim_ms, self.opacity)
        parameter_values = self.parameter_values_at(pos_ms)
        img = _OffscreenRenderer.instance().render_on_main(
            model_path   = self.model_path,
            w            = width,
            h            = height,
            motion_group = self.motion_group,
            motion_idx   = self.motion_idx,
            n_updates    = n,
            pos_x        = cur_pos_x,
            pos_y        = cur_pos_y,
            scale        = cur_scale,
            opacity      = cur_opacity,
            clip_key     = id(self),
            start_motion = need_start,
            expression_id = self.expression_id,
            parameter_values = parameter_values,
        )
        if img is not None:
            self._model_motion_started = True
        return img

    def reset(self):
        self._last_render_ms       = -1
        self._accum_updates        = 0
        self._motion_started       = False
        self._model_motion_started = False  # force StartMotion on next render


# ── blend marker (placed between two clips) ───────────────────────────────────

@dataclass
class Live2DBlend:
    """A crossfade transition placed between two adjacent clips.

    The transition is centered at ``center_ms`` and spans
    ``duration_ms`` total (half on each side).  During the active
    window the clip before it fades out and the clip after fades in
    using the chosen curve.
    """
    center_ms:   int  = 0
    duration_ms: int  = 500    # total span; 250ms each side
    curve:       str  = "smoothstep"

    @property
    def start_ms(self) -> int:
        return self.center_ms - self.duration_ms // 2

    @property
    def end_ms(self) -> int:
        return self.center_ms + self.duration_ms // 2


# ── track ─────────────────────────────────────────────────────────────────────

@dataclass
class Live2DActorTrack:
    """A timeline track containing Live2D actor clips."""
    id:     int  = 0
    label:  str  = "Live2D"
    clips:  list = field(default_factory=list)   # list[Live2DActorClip]
    blends: list = field(default_factory=list)   # list[Live2DBlend]

    def clips_at(self, pos_ms: int) -> list[Live2DActorClip]:
        return [c for c in self.clips
                if c.start_ms <= pos_ms < c.end_ms]

    def weighted_clips_at(self, pos_ms: int) -> list[ClipWeight]:
        """
        Return each active clip with its blend weight for pos_ms.

        Priority order for weight calculation:
        1. Live2DBlend markers placed between clips  (explicit crossfade)
        2. Per-clip blend_in / blend_out handles     (legacy fallback)
        """
        active = [c for c in self.clips if c.start_ms <= pos_ms < c.end_ms]
        if not active:
            return []

        # Collect blend modifiers from explicit blend markers.
        # blend_mod[clip] = weight multiplier from blend markers.
        blend_mod: dict[int, float] = {}  # id(clip) → multiplier

        sorted_clips = sorted(self.clips, key=lambda c: c.start_ms)
        for blend in self.blends:
            if not (blend.start_ms <= pos_ms < blend.end_ms):
                continue
            # t: 0 = start of blend window, 1 = end
            t = apply_curve(
                (pos_ms - blend.start_ms) / max(1, blend.duration_ms),
                blend.curve,
            )
            # Find the clip that ends closest before center_ms (clip A)
            # and the clip that starts closest after center_ms (clip B).
            clip_a = next(
                (c for c in reversed(sorted_clips)
                 if c.start_ms <= blend.center_ms), None
            )
            clip_b = next(
                (c for c in sorted_clips
                 if c.start_ms > blend.center_ms), None
            )
            if clip_a is not None:
                blend_mod[id(clip_a)] = blend_mod.get(id(clip_a), 1.0) * (1.0 - t)
            if clip_b is not None:
                blend_mod[id(clip_b)] = blend_mod.get(id(clip_b), 1.0) * t

        results: list[ClipWeight] = []
        for clip in active:
            w = blend_mod.get(id(clip), 1.0)

            # Per-clip fade handles (only when no blend marker covers this)
            if id(clip) not in blend_mod:
                if clip.blend_in_ms > 0:
                    elapsed_in = pos_ms - clip.start_ms
                    if elapsed_in < clip.blend_in_ms:
                        w *= apply_curve(elapsed_in / clip.blend_in_ms,
                                         clip.blend_curve)
                if clip.blend_out_ms > 0:
                    remaining = clip.end_ms - pos_ms
                    if remaining < clip.blend_out_ms:
                        w *= apply_curve(remaining / clip.blend_out_ms,
                                         clip.blend_curve)

            results.append(ClipWeight(clip, max(0.0, min(1.0, w))))

        return results

    def render_at(self, pos_ms: int, width: int, height: int):
        """
        Composite all active clips at pos_ms into one RGBA PIL Image.
        Each clip is rendered independently (safe, no shared GL state),
        then alpha-composited in numpy with blend weights.
        """
        weighted = self.weighted_clips_at(pos_ms)
        if not weighted:
            return None
        if len(weighted) == 1 and weighted[0].weight >= 0.999:
            return weighted[0].clip.render_frame(width, height, pos_ms)

        from PIL import Image
        import numpy as np
        canvas = np.zeros((height, width, 4), dtype=np.float32)

        for clip, w in weighted:
            img = clip.render_frame(width, height, pos_ms)
            if img is None:
                continue
            arr = np.asarray(img, dtype=np.float32)
            alpha = arr[:, :, 3:4] / 255.0 * w
            canvas[:, :, :3] += arr[:, :, :3] * alpha
            canvas[:, :, 3:]  = np.maximum(canvas[:, :, 3:], arr[:, :, 3:4] * w)

        out = canvas.clip(0, 255).astype(np.uint8)
        return Image.fromarray(out, "RGBA")
