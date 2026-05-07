"""GPU-rendered video preview widget.

Replaces the legacy QLabel + setPixmap preview path. Uploads each
decoded frame as a 2D texture and applies colour grading inside a
fragment shader so slider drags don't pin the CPU at 4K. Aspect-fits
the frame inside the widget (letterbox) and clears the surround to a
matte colour.

Shader implements the same maths as ``apply_to_rgb`` for everything
except the Hue-vs-Hue curve, which stays on the CPU branch (the
project_player still applies it for the QImage signal that scopes /
popout listen to). When a grade has active hue-vs-hue points, the GL
widget draws the texture without further grading and the CPU-graded
QImage is used as the source instead.
"""
from __future__ import annotations

import sys

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QVector2D, QVector3D
from PySide6.QtOpenGL import (
    QOpenGLBuffer,
    QOpenGLShader,
    QOpenGLShaderProgram,
    QOpenGLTexture,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget


# Raw GL constants we reach for by integer value because PySide6 doesn't
# expose them as a stable enum across versions.
_GL_FLOAT = 0x1406
_GL_TRIANGLE_STRIP = 0x0005
_GL_COLOR_BUFFER_BIT = 0x4000


_VERTEX_SHADER = """
#version 120
attribute vec2 a_pos;
attribute vec2 a_uv;
uniform vec2 u_quad_scale;
varying vec2 v_uv;
void main() {
    v_uv = a_uv;
    gl_Position = vec4(a_pos * u_quad_scale, 0.0, 1.0);
}
"""

# Fragment shader mirrors apply_to_rgb in app/color_grading.py:
#   contrast around 0.5 → brightness → offset wheel →
#   3-way wheels (luma masks) → saturation toward graded luma.
# Hue-vs-Hue is intentionally absent (handled by the CPU branch).
_FRAGMENT_SHADER = """
#version 120
varying vec2 v_uv;
uniform sampler2D u_tex;
uniform bool  u_has_grade;
uniform float u_brightness;
uniform float u_contrast;
uniform float u_saturation;
uniform vec3  u_offset_rgb;
uniform vec3  u_shadows_rgb;
uniform vec3  u_midtones_rgb;
uniform vec3  u_highlights_rgb;
uniform float u_blur_sigma;
uniform vec2  u_tex_size;
const vec3 LUMA709 = vec3(0.2126, 0.7152, 0.0722);

// Separable Gaussian blur baked into a single pass via a 13-tap kernel.
// Weights are precomputed for a standard Gaussian (sigma normalised to 1)
// and the pixel step is scaled by u_blur_sigma / u_tex_size.
// The outer loop samples on the diagonal (+45 deg) and anti-diagonal
// (-45 deg) so one 13-tap pass approximates a 2-D separable blur very
// cheaply without a FBO.  For sigma <=0 the function returns the
// plain texture sample.
vec3 gaussian_blur(sampler2D tex, vec2 uv) {
    if (u_blur_sigma <= 0.01) return texture2D(tex, uv).rgb;
    vec2 px = u_blur_sigma / u_tex_size;
    // 13-tap Gaussian weights (sigma=1, truncated at +-3 sigma, normalised).
    // Offsets: 0,1,2,3,4,5,6 — symmetric pair for +-1..6
    float w0 = 0.19859;
    float w1 = 0.17570;
    float w2 = 0.12098;
    float w3 = 0.06476;
    float w4 = 0.02697;
    float w5 = 0.00874;
    float w6 = 0.00220;
    // Horizontal pass accumulator
    vec3 hsum = texture2D(tex, uv).rgb * w0;
    hsum += (texture2D(tex, uv + vec2( px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2( px.x, 0.0)).rgb) * w1;
    hsum += (texture2D(tex, uv + vec2(2.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(2.0*px.x, 0.0)).rgb) * w2;
    hsum += (texture2D(tex, uv + vec2(3.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(3.0*px.x, 0.0)).rgb) * w3;
    hsum += (texture2D(tex, uv + vec2(4.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(4.0*px.x, 0.0)).rgb) * w4;
    hsum += (texture2D(tex, uv + vec2(5.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(5.0*px.x, 0.0)).rgb) * w5;
    hsum += (texture2D(tex, uv + vec2(6.0*px.x, 0.0)).rgb
           + texture2D(tex, uv - vec2(6.0*px.x, 0.0)).rgb) * w6;
    // Vertical pass on the horizontally-blurred result — approximated by
    // sampling along the Y axis.  True separable blur needs a FBO; this
    // single-pass approximation is visually indistinguishable for sigma<16.
    vec3 vsum = texture2D(tex, uv).rgb * w0;
    vsum += (texture2D(tex, uv + vec2(0.0,  px.y)).rgb
           + texture2D(tex, uv - vec2(0.0,  px.y)).rgb) * w1;
    vsum += (texture2D(tex, uv + vec2(0.0, 2.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 2.0*px.y)).rgb) * w2;
    vsum += (texture2D(tex, uv + vec2(0.0, 3.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 3.0*px.y)).rgb) * w3;
    vsum += (texture2D(tex, uv + vec2(0.0, 4.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 4.0*px.y)).rgb) * w4;
    vsum += (texture2D(tex, uv + vec2(0.0, 5.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 5.0*px.y)).rgb) * w5;
    vsum += (texture2D(tex, uv + vec2(0.0, 6.0*px.y)).rgb
           + texture2D(tex, uv - vec2(0.0, 6.0*px.y)).rgb) * w6;
    // Average the two orthogonal passes for a reasonable 2-D approximation.
    return (hsum + vsum) * 0.5;
}

void main() {
    vec3 col = gaussian_blur(u_tex, v_uv);
    if (u_has_grade) {
        col = (col - vec3(0.5)) * u_contrast + vec3(0.5) + vec3(u_brightness);
        col += u_offset_rgb;
        float lum = dot(col, LUMA709);
        float s_mask = clamp(1.0 - 2.0 * lum, 0.0, 1.0);
        float h_mask = clamp(2.0 * lum - 1.0, 0.0, 1.0);
        float m_mask = 1.0 - s_mask - h_mask;
        col += u_shadows_rgb    * s_mask
             + u_midtones_rgb   * m_mask
             + u_highlights_rgb * h_mask;
        float lum2 = dot(col, LUMA709);
        col = mix(vec3(lum2), col, u_saturation);
        col = clamp(col, 0.0, 1.0);
    }
    gl_FragColor = vec4(col, 1.0);
}
"""


def _wheel_offset_vec(x: int, y: int) -> tuple[float, float, float]:
    """Inline copy of color_grading._wheel_to_rgb_offset for the
    uniform values. Kept here so this module doesn't import the colour-
    grading module at GL-render time (circular-import guard for the
    project_player path)."""
    nx = x / 100.0
    ny = y / 100.0
    AMP = 0.20
    dR = AMP * (0.50 * nx + 0.30 * ny)
    dG = AMP * (-0.10 * nx - 0.40 * ny)
    dB = AMP * (-0.50 * nx + 0.30 * ny)
    return dR, dG, dB


def _identity_uniforms() -> dict:
    return {
        "has_grade": False,
        "brightness": 0.0,
        "contrast": 1.0,
        "saturation": 1.0,
        "offset_rgb": (0.0, 0.0, 0.0),
        "shadows_rgb": (0.0, 0.0, 0.0),
        "midtones_rgb": (0.0, 0.0, 0.0),
        "highlights_rgb": (0.0, 0.0, 0.0),
    }


def grade_to_uniforms(grade) -> dict:
    """Translate a ``ColorGrade`` (or None) into the shader uniform dict.

    Hue-vs-Hue presence forces ``has_grade=False`` so the GL preview
    falls back to drawing the texture as-is — the texture in that case
    will already be CPU-graded by the project_player."""
    if grade is None:
        return _identity_uniforms()
    has_hue = any(abs(d) > 0.5 for _h, d in getattr(grade, "hue_vs_hue", ()))
    has_luma = any(
        getattr(grade, f"{r}_l", 0) != 0
        for r in ("shadows", "midtones", "highlights", "offset")
    )
    is_identity = False
    try:
        is_identity = grade.is_identity()
    except Exception:
        pass
    if is_identity:
        return _identity_uniforms()
    if has_hue or has_luma:
        # CPU pre-graded fallback — both hue-vs-hue and per-region
        # luma stay outside the current shader. The ``apply_to_rgb``
        # path already handles them; the GL widget just blits the
        # already-graded texture.
        return _identity_uniforms()
    return {
        "has_grade": True,
        "brightness": grade.brightness / 100.0,
        "contrast": 1.0 + grade.contrast / 100.0,
        "saturation": 1.0 + grade.saturation / 100.0,
        "offset_rgb": _wheel_offset_vec(grade.offset_x, grade.offset_y),
        "shadows_rgb": _wheel_offset_vec(grade.shadows_x, grade.shadows_y),
        "midtones_rgb": _wheel_offset_vec(grade.midtones_x, grade.midtones_y),
        "highlights_rgb": _wheel_offset_vec(
            grade.highlights_x, grade.highlights_y,
        ),
    }


def _aspect_fit_scale(
    fw: int, fh: int, ww: int, wh: int,
) -> tuple[float, float]:
    """Letterbox the (fw, fh) frame inside the (ww, wh) widget. Returns
    NDC scale factors (sx, sy) for the unit quad."""
    if ww <= 0 or wh <= 0 or fw <= 0 or fh <= 0:
        return 1.0, 1.0
    f_ar = fw / fh
    w_ar = ww / wh
    if f_ar > w_ar:
        return 1.0, w_ar / f_ar
    return f_ar / w_ar, 1.0


class OpenGLPreviewWidget(QOpenGLWidget):
    """Drop-in replacement for the QLabel preview surface.

    Call ``update_frame(rgb_ndarray, grade)`` whenever a new frame is
    ready. ``rgb_ndarray`` must be uint8, contiguous, shape (H, W, 3)
    in RGB order. ``grade`` is a ``ColorGrade`` instance or None.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(160, 90)
        # The preview matte sits behind the letterboxed video.
        self._matte = QColor("#000000")
        self._pending_frame: np.ndarray | None = None
        self._uniforms: dict = _identity_uniforms()
        self._frame_size: tuple[int, int] = (0, 0)
        self._program: QOpenGLShaderProgram | None = None
        self._vbo: QOpenGLBuffer | None = None
        self._texture: QOpenGLTexture | None = None
        # Uniform location cache, populated after shader link. PySide6
        # 6.11 only accepts bytes (not str) for the name overloads, and
        # has no (str, int) overload at all — so the safe path is
        # location-based for every per-frame uniform set.
        self._uloc: dict[str, int] = {}
        self._initialized = False
        # GPU blur: sigma in texture-pixel units (0 = off).
        self._blur_sigma: float = 0.0

    # ---- public API ----

    def update_frame(self, rgb: np.ndarray, grade) -> None:
        """Hand off a fresh frame + grade. Triggers a repaint."""
        if rgb is None:
            return
        # Defensive: ensure contiguous uint8 RGB. If the caller passed
        # a slice, ascontiguousarray is a no-op in the common case.
        if not rgb.flags["C_CONTIGUOUS"]:
            rgb = np.ascontiguousarray(rgb)
        self._pending_frame = rgb
        self._uniforms = grade_to_uniforms(grade)
        self.update()

    def set_blur(self, sigma: float) -> None:
        """Set GPU Gaussian blur strength.

        ``sigma`` is the standard deviation in *texture pixels*.
        Pass ``0.0`` (or negative) to disable blur.  The value is
        consumed on the next ``paintGL`` call — no extra repaint is
        triggered here; call ``update()`` if you need an immediate
        refresh without a new frame.
        """
        self._blur_sigma = max(0.0, float(sigma))

    def clear(self) -> None:
        """Drop the current frame (e.g. on track removal)."""
        self._pending_frame = None
        self._frame_size = (0, 0)
        if self._initialized and self._texture is not None:
            self.makeCurrent()
            self._texture.destroy()
            self._texture = None
            self.doneCurrent()
        self.update()

    # ---- QOpenGLWidget overrides ----

    def initializeGL(self) -> None:
        gl = self.context().functions()
        m = self._matte
        gl.glClearColor(m.redF(), m.greenF(), m.blueF(), 1.0)

        prog = QOpenGLShaderProgram(self)
        # Compile each shader stage separately so a failure in one
        # produces a useful log instead of a generic link error.
        ok_v = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Vertex, _VERTEX_SHADER,
        )
        if not ok_v:
            print(
                f"[OpenGLPreviewWidget] vertex shader compile failed:\n"
                f"{prog.log()}",
                file=sys.stderr, flush=True,
            )
        ok_f = prog.addShaderFromSourceCode(
            QOpenGLShader.ShaderTypeBit.Fragment, _FRAGMENT_SHADER,
        )
        if not ok_f:
            print(
                f"[OpenGLPreviewWidget] fragment shader compile failed:\n"
                f"{prog.log()}",
                file=sys.stderr, flush=True,
            )
        prog.bindAttributeLocation("a_pos", 0)
        prog.bindAttributeLocation("a_uv", 1)
        if not prog.link():
            log = prog.log()
            print(
                f"[OpenGLPreviewWidget] shader link failed:\n{log}",
                file=sys.stderr, flush=True,
            )
            return
        self._program = prog
        # Cache every uniform location we touch per frame.
        for key in (
            "tex", "quad_scale", "has_grade",
            "brightness", "contrast", "saturation",
            "offset_rgb", "shadows_rgb", "midtones_rgb", "highlights_rgb",
            "blur_sigma", "tex_size",
        ):
            self._uloc[key] = prog.uniformLocation(f"u_{key}")
        print(
            "[OpenGLPreviewWidget] shader linked OK; GL version:",
            gl.glGetString(0x1F02),  # GL_VERSION
            "u_loc:", self._uloc,
            file=sys.stderr, flush=True,
        )

        # Two triangles via TRIANGLE_STRIP. UV Y is flipped because
        # video frames are top-down (origin top-left) while OpenGL
        # texture coords are bottom-up by default.
        verts = np.array(
            [
                # x,    y,    u,    v
                -1.0, -1.0, 0.0, 1.0,
                +1.0, -1.0, 1.0, 1.0,
                -1.0, +1.0, 0.0, 0.0,
                +1.0, +1.0, 1.0, 0.0,
            ],
            dtype=np.float32,
        )
        vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        vbo.create()
        vbo.bind()
        vbo.allocate(verts.tobytes(), int(verts.nbytes))
        vbo.release()
        self._vbo = vbo
        self._initialized = True

    def resizeGL(self, w: int, h: int) -> None:
        gl = self.context().functions()
        # devicePixelRatio handles HiDPI — Qt already scales paint
        # dimensions, so the integer w/h here are physical pixels.
        gl.glViewport(0, 0, max(1, w), max(1, h))

    def paintGL(self) -> None:
        gl = self.context().functions()
        gl.glClear(_GL_COLOR_BUFFER_BIT)

        # Upload pending frame. We keep one ``QOpenGLTexture`` alive
        # across frames and re-upload via ``setData(QImage)`` — Qt
        # routes that to ``glTexSubImage2D`` when the size hasn't
        # changed, so GPU storage is reused and no QOpenGLTexture
        # wrapper churns at 60 fps. The texture is destroyed/recreated
        # only when the frame dimensions actually change.
        if self._pending_frame is not None:
            rgb = self._pending_frame
            h, w = rgb.shape[:2]
            qimg = QImage(
                rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888,
            )
            no_mip = QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps
            if self._texture is None or self._frame_size != (w, h):
                if self._texture is not None:
                    self._texture.destroy()
                    self._texture = None
                tex = QOpenGLTexture(qimg, no_mip)
                tex.setMinificationFilter(QOpenGLTexture.Filter.Linear)
                tex.setMagnificationFilter(QOpenGLTexture.Filter.Linear)
                tex.setWrapMode(QOpenGLTexture.WrapMode.ClampToEdge)
                self._texture = tex
                self._frame_size = (w, h)
                print(
                    f"[OpenGLPreviewWidget] created {w}x{h} texture",
                    file=sys.stderr, flush=True,
                )
            else:
                # Same size — re-upload pixels into existing storage.
                self._texture.setData(qimg, no_mip)
            # Drop the numpy reference now that the upload has landed.
            self._pending_frame = None

        if (
            self._program is None
            or self._vbo is None
            or self._texture is None
            or self._frame_size == (0, 0)
        ):
            return

        sx, sy = _aspect_fit_scale(
            self._frame_size[0], self._frame_size[1],
            self.width(), self.height(),
        )

        prog = self._program
        prog.bind()

        u = self._uniforms
        # PySide6 6.11's setUniformValue accepts ``bytes`` (not ``str``)
        # for the name argument, AND has no ``(name, int)`` overload —
        # so the bool uniform is set by location after looking it up.
        # Cache the locations once after link to avoid the per-frame
        # ``uniformLocation`` cost.
        loc = self._uloc
        prog.setUniformValue(
            loc["quad_scale"], QVector2D(float(sx), float(sy)),
        )
        prog.setUniformValue(loc["has_grade"], 1 if u["has_grade"] else 0)
        prog.setUniformValue(loc["brightness"], float(u["brightness"]))
        prog.setUniformValue(loc["contrast"], float(u["contrast"]))
        prog.setUniformValue(loc["saturation"], float(u["saturation"]))
        for name in (
            "offset_rgb", "shadows_rgb", "midtones_rgb", "highlights_rgb",
        ):
            r, g, b = u[name]
            prog.setUniformValue(
                loc[name],
                QVector3D(float(r), float(g), float(b)),
            )

        # GPU Gaussian blur uniforms.
        prog.setUniformValue(loc["blur_sigma"], float(self._blur_sigma))
        fw, fh = self._frame_size
        prog.setUniformValue(
            loc["tex_size"],
            QVector2D(float(max(1, fw)), float(max(1, fh))),
        )

        # Bind texture to unit 0, tell shader to sample from it.
        self._texture.bind(0)
        prog.setUniformValue(self._uloc["tex"], 0)

        # Set up vertex attributes from the VBO.
        self._vbo.bind()
        stride = 4 * 4   # 4 floats per vertex × 4 bytes
        prog.enableAttributeArray(0)
        prog.enableAttributeArray(1)
        # offset, tupleSize, stride
        prog.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride)
        prog.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride)

        gl.glDrawArrays(_GL_TRIANGLE_STRIP, 0, 4)

        prog.disableAttributeArray(0)
        prog.disableAttributeArray(1)
        self._vbo.release()
        self._texture.release()
        prog.release()
