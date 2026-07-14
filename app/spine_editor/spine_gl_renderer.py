"""OpenGL-based Spine renderer — replaces the PIL software renderer.

Uses QOpenGLWidget context. Atlas pages are uploaded as GL textures.
Each slot's mesh is drawn as indexed triangles with proper UV mapping
and alpha blending.
"""
from __future__ import annotations
import math
import numpy as np
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPainterPath, QFont, QMouseEvent, QWheelEvent
from PySide6.QtOpenGL import (
    QOpenGLBuffer, QOpenGLShader, QOpenGLShaderProgram,
    QOpenGLTexture,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QWidget

from app.spine_editor.spine_data import SpineSkeleton, Bone, RegionAttachment
from app.spine_editor.layout import (
    SPINE_PREVIEW_FIT_MARGIN,
    compute_spine_editor_view_transform,
)

if TYPE_CHECKING:
    from PIL import Image

# ── GLSL shaders ──────────────────────────────────────────────────────────

_VERT = """
#version 330 core
layout(location = 0) in vec2 a_pos;
layout(location = 1) in vec2 a_uv;
out vec2 v_uv;
void main() {
    gl_Position = vec4(a_pos, 0.0, 1.0);
    v_uv = a_uv;
}
"""

_FRAG = """
#version 330 core
in vec2 v_uv;
uniform sampler2D u_tex;
out vec4 frag_color;
void main() {
    frag_color = texture(u_tex, v_uv);
}
"""

_GL_TRIANGLES = 0x0004
_GL_FLOAT = 0x1406
_GL_BLEND = 0x0BE2
_GL_SRC_ALPHA = 0x0302
_GL_ONE_MINUS_SRC_ALPHA = 0x0303
_GL_DEPTH_TEST = 0x0B71
_GL_SCISSOR_TEST = 0x0C11
_GL_COLOR_BUFFER_BIT = 0x4000
_GL_TEXTURE_2D = 0x0DE1


def _atlas_rotation_degrees(value) -> int:
    if isinstance(value, bool):
        return 90 if value else 0
    try:
        return int(value) % 360
    except Exception:
        return 0


class SpineGLViewport(QOpenGLWidget):
    """QOpenGLWidget-based Spine viewport.

    Renders the skeleton's slot sprites with proper GPU alpha blending
    and bilinear filtering. Bones/labels drawn on top via QPainter.
    """
    from PySide6.QtCore import Signal
    bone_selected = Signal(str)
    bone_moved    = Signal(str, float, float)
    first_frame_ready = Signal()

    BONE_COLOR       = QColor("#5ec8e5")
    BONE_SELECTED    = QColor("#ff8c00")
    BONE_HOVER       = QColor("#a0e8ff")
    ROOT_COLOR       = QColor("#e55555")
    BG_COLOR         = QColor("#1a1a28")
    GRID_COLOR       = QColor("#30384F")
    GRID_MAJOR_COLOR = QColor("#353550")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._selected: Optional[str] = None
        self._hovered:  Optional[str] = None
        self._show_sprites = True
        self._show_bones   = True
        self._active_skin  = "default"

        self._offset = QPointF(0.0, 0.0)
        self._zoom   = 1.0
        self._fit_center = (0.0, 0.0)
        self._fit_zoom = 1.0
        self._placement_x = 0.5
        self._placement_y = 0.5
        self._placement_scale = 1.0
        self._placement_view_mode = "work"
        self._output_aspect_ratio = 16.0 / 9.0
        self._frame_rect = QRectF()

        self._pan_start: Optional[QPointF] = None
        self._drag_bone: Optional[str] = None
        self._drag_start_world: Optional[tuple] = None

        # GL resources (created in initializeGL)
        self._prog: Optional[QOpenGLShaderProgram] = None
        self._vbo:  Optional[QOpenGLBuffer] = None
        self._gl_textures: dict = {}    # page_idx → QOpenGLTexture
        self._gl_ready = False
        self._has_first_frame = False

        # Runtime data
        self._atlas:    dict = {}       # {region_name: (page_idx, x, y, w, h, rotate)}
        self._pil_pages: list = []      # PIL images for upload
        self._pma:       bool = False   # premultiplied alpha flag
        self._hidden_slots: set = set()
        self._pending_destroy: list = []  # old textures to destroy on next paintGL

        self.setMouseTracking(True)
        from PySide6.QtCore import Qt as _Qt
        self.setFocusPolicy(_Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 400)

    # ── public API ────────────────────────────────────────────────────────

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton = skel
        self._has_first_frame = False
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._fit_and_update)
        self.update()

    def set_renderer_data(self, atlas: dict, pil_pages: list,
                          pma: bool = False) -> None:
        """Set atlas metadata and PIL page images for GL upload."""
        self._atlas     = atlas
        self._pil_pages = pil_pages
        self._pma       = pma
        self._destroy_gl_textures()  # destroy with context active
        self._gl_ready  = False
        self._has_first_frame = False
        from PySide6.QtCore import QTimer
        QTimer.singleShot(80, self._fit_and_update)
        self.update()

    def clear_sprites(self) -> None:
        self._atlas.clear()
        self._pil_pages.clear()
        self._destroy_gl_textures()
        self.update()

    def clear(self) -> None:
        self._skeleton = None
        self._selected = None
        self._hovered = None
        self.clear_sprites()

    def set_placement(self, x: float | None = None,
                      y: float | None = None,
                      scale: float | None = None) -> None:
        """Apply clip-style placement: x/y are normalized screen coordinates."""
        if x is not None:
            self._placement_x = max(0.0, min(1.0, float(x)))
        if y is not None:
            self._placement_y = max(0.0, min(1.0, float(y)))
        if scale is not None:
            self._placement_scale = max(0.02, min(20.0, float(scale)))
        self._apply_placement()
        self.update()

    def set_placement_view_mode(self, mode: str) -> None:
        normalized = str(mode or "work").lower()
        self._placement_view_mode = "final" if normalized == "final" else "work"
        self._apply_placement()
        self.update()

    def placement_view_mode(self) -> str:
        return self._placement_view_mode

    def set_output_aspect_ratio(self, aspect_ratio: float) -> None:
        try:
            aspect = float(aspect_ratio)
        except (TypeError, ValueError):
            aspect = 16.0 / 9.0
        self._output_aspect_ratio = max(0.05, min(20.0, aspect))
        self._apply_placement()
        self.update()

    def output_aspect_ratio(self) -> float:
        return self._output_aspect_ratio

    def _apply_placement(self) -> None:
        vw, vh = max(1, self.width()), max(1, self.height())
        try:
            bounds = self._visual_bounds()
        except Exception:
            bounds = None
        zoom, offset_x, offset_y, frame_rect = compute_spine_editor_view_transform(
            bounds,
            vw,
            vh,
            self._placement_x,
            self._placement_y,
            self._placement_scale,
            mode=self._placement_view_mode,
            frame_aspect_ratio=self._output_aspect_ratio,
        )
        self._zoom = max(0.02, min(20.0, float(zoom)))
        self._offset = QPointF(float(offset_x), float(offset_y))
        self._frame_rect = QRectF(
            float(frame_rect[0]),
            float(frame_rect[1]),
            float(frame_rect[2]),
            float(frame_rect[3]),
        )

    def _destroy_gl_textures(self) -> None:
        """Schedule GL texture destruction on next paintGL call."""
        # Mark old textures for deferred cleanup — will be replaced in _upload_textures
        self._pending_destroy = list(self._gl_textures.values())
        self._gl_textures.clear()

    @staticmethod
    def pil_to_qimage(img):
        from PySide6.QtGui import QImage as _QI
        img = img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        return _QI(data, img.width, img.height, img.width * 4,
                   _QI.Format.Format_RGBA8888).copy()

    def selected_bone(self) -> Optional[str]:
        return self._selected

    def _mesh_weights_for(self, slot_name: str, attachment_name: str,
                          attach: RegionAttachment) -> list:
        weights = getattr(attach, "mesh_weights", []) or []
        deforms = getattr(self._skeleton, "active_deforms", {}) if self._skeleton else {}
        deform = (
            deforms.get((slot_name, attachment_name))
            or deforms.get((slot_name, attach.name))
        )
        if not deform:
            return weights
        is_weighted = any(
            bone_idx >= 0
            for vtx_bones in weights
            for bone_idx, _lx, _ly, _weight in vtx_bones
        )
        if is_weighted:
            influence_index = 0
            deformed_weights = []
            for vtx_bones in weights:
                deformed_vertex = []
                for bone_idx, lx, ly, weight in vtx_bones:
                    j = influence_index * 2
                    dx = float(deform[j]) if j < len(deform) else 0.0
                    dy = float(deform[j + 1]) if j + 1 < len(deform) else 0.0
                    deformed_vertex.append((bone_idx, lx + dx, ly + dy, weight))
                    influence_index += 1
                deformed_weights.append(deformed_vertex)
            return deformed_weights
        if len(deform) < len(weights) * 2:
            return weights
        for vtx_bones in weights:
            if len(vtx_bones) != 1:
                return weights
            bone_idx, _lx, _ly, weight = vtx_bones[0]
            if bone_idx >= 0 or abs(weight - 1.0) > 1e-5:
                return weights
        return [
            [(-1, float(deform[i * 2]), float(deform[i * 2 + 1]), 1.0)]
            for i in range(len(weights))
        ]

    # ── coordinate helpers ────────────────────────────────────────────────

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        cx = self._offset.x() + wx * self._zoom
        cy = self._offset.y() - wy * self._zoom
        return cx, cy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = (sx - self._offset.x()) / self._zoom
        wy = -(sy - self._offset.y()) / self._zoom
        return wx, wy

    def _screen_to_ndc(self, sx: float, sy: float) -> tuple[float, float]:
        w, h = max(1, self.width()), max(1, self.height())
        return sx / w * 2 - 1, -(sy / h * 2 - 1)

    # ── OpenGL lifecycle ──────────────────────────────────────────────────

    def closeEvent(self, event):
        self._pending_destroy.extend(self._gl_textures.values())
        self._gl_textures.clear()
        super().closeEvent(event)

    def initializeGL(self):
        import sys
        gl = self.context().functions()
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glEnable(_GL_BLEND)
        gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)
        gl.glDisable(_GL_DEPTH_TEST)

        self._prog = QOpenGLShaderProgram()
        ok_v = self._prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Vertex,   _VERT)
        ok_f = self._prog.addShaderFromSourceCode(QOpenGLShader.ShaderTypeBit.Fragment, _FRAG)
        if not ok_v or not ok_f:
            print(f"[spine GL] shader compile error: {self._prog.log()}", file=sys.stderr)
        self._prog.link()
        if not self._prog.isLinked():
            print(f"[spine GL] shader link error: {self._prog.log()}", file=sys.stderr)

        self._vbo = QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        self._vbo.create()

    def resizeGL(self, w: int, h: int):
        gl = self.context().functions()
        gl.glViewport(0, 0, w, h)
        if self._skeleton:
            self._fit_skeleton()

    def paintGL(self):
        p = QPainter(self)
        emit_first_frame = False

        # GL sprite rendering inside beginNativePainting block
        p.beginNativePainting()
        gl = self.context().functions()
        r, g, b = 0x1a/255, 0x1a/255, 0x28/255
        gl.glDisable(_GL_SCISSOR_TEST)
        gl.glClearColor(r, g, b, 1.0)
        gl.glClear(_GL_COLOR_BUFFER_BIT)

        if self._pil_pages and not self._gl_textures:
            self._upload_textures(gl)

        _GL_ONE = 0x0001
        gl.glEnable(_GL_BLEND)
        if self._pma:
            gl.glBlendFunc(_GL_ONE, _GL_ONE_MINUS_SRC_ALPHA)
        else:
            gl.glBlendFunc(_GL_SRC_ALPHA, _GL_ONE_MINUS_SRC_ALPHA)

        if self._show_sprites and self._skeleton and self._atlas and self._gl_textures:
            self._draw_spine_gl(gl)
        if self._skeleton and not self._has_first_frame:
            self._has_first_frame = True
            emit_first_frame = True
        p.endNativePainting()

        # QPainter overlay: bones only
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._skeleton and self._show_bones:
            self._draw_bones(p)
            self._draw_bone_labels(p)
        if self._skeleton:
            self._draw_final_frame_overlay(p)
        ox, oy = self.world_to_screen(0, 0)
        try:
            ox_i, oy_i = int(max(-32000, min(32000, ox))), int(max(-32000, min(32000, oy)))
            p.setPen(QPen(QColor("#ffffff40"), 1))
            p.drawLine(ox_i - 10, oy_i, ox_i + 10, oy_i)
            p.drawLine(ox_i, oy_i - 10, ox_i, oy_i + 10)
        except (OverflowError, ValueError):
            pass
        p.end()
        if emit_first_frame:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self.first_frame_ready.emit)

    # ── texture upload ────────────────────────────────────────────────────

    def _upload_textures(self, gl):
        # Destroy old textures now that context is active
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

    # ── Spine GL draw ─────────────────────────────────────────────────────

    def _draw_spine_gl(self, gl):
        if not self._skeleton:
            return

        resolved_skin = self._active_skin
        merged: dict = {}
        for sn, atts in self._skeleton.skins.get("default", {}).items():
            merged[sn] = dict(atts)
        for sn, atts in self._skeleton.skins.get(resolved_skin, {}).items():
            merged.setdefault(sn, {}).update(atts)

        bones = self._skeleton.bones
        w, h = max(1, self.width()), max(1, self.height())
        cx = self._offset.x()
        cy = self._offset.y()
        scale = self._zoom

        self._prog.bind()
        self._prog.setUniformValue("u_tex", 0)

        batch_tex = None
        batch_vertices: list[float] = []

        def _flush_batch() -> None:
            nonlocal batch_tex, batch_vertices
            if batch_tex is not None and batch_vertices:
                self._draw_expanded_mesh(gl, batch_tex, batch_vertices)
            batch_tex = None
            batch_vertices = []

        def _queue_mesh(tex, verts_flat, triangles) -> None:
            nonlocal batch_tex, batch_vertices
            if batch_tex is not tex:
                _flush_batch()
                batch_tex = tex
            self._append_expanded_vertices(batch_vertices, verts_flat, triangles)

        for slot in self._skeleton.slots:
            if not slot.attachment:
                continue
            if slot.name in self._hidden_slots:
                continue
            bone = self._skeleton.bone(slot.bone)
            if bone is None:
                continue
            attach = merged.get(slot.name, {}).get(slot.attachment)
            if not isinstance(attach, RegionAttachment):
                continue
            if getattr(attach, "_non_visual", False):
                continue

            region_name = attach.path or attach.name
            skin_base = resolved_skin.rsplit("/", 1)[-1] if resolved_skin else ""
            entry = (self._atlas.get(region_name)
                     or (self._atlas.get(f"{resolved_skin}/{region_name}") if resolved_skin else None)
                     or (self._atlas.get(f"{skin_base}/{region_name}") if skin_base else None)
                     or self._atlas.get(f"common/{region_name}"))
            if entry is None:
                continue

            page_idx = entry[0]
            rx, ry, rw, rh = entry[1], entry[2], entry[3], entry[4]
            atlas_rotate = _atlas_rotation_degrees(entry[5] if len(entry) > 5 else 0)
            orig_w = entry[6] if len(entry) > 6 else rw
            orig_h = entry[7] if len(entry) > 7 else rh
            off_x = entry[8] if len(entry) > 8 else 0
            off_y = entry[9] if len(entry) > 9 else 0
            stored_w = entry[10] if len(entry) > 10 else None
            stored_h = entry[11] if len(entry) > 11 else None
            if stored_w is None or stored_h is None:
                if atlas_rotate in (90, 270):
                    stored_w, stored_h = rh, rw
                else:
                    stored_w, stored_h = rw, rh

            if page_idx not in self._gl_textures:
                continue
            tex = self._gl_textures[page_idx]

            pil_page = self._pil_pages[page_idx]
            if pil_page is None:
                continue
            tex_w, tex_h = pil_page.size

            weights = self._mesh_weights_for(slot.name, slot.attachment, attach)
            mesh_uvs = getattr(attach, 'mesh_uvs', [])
            mesh_tris = getattr(attach, 'mesh_triangles', [])

            if weights and mesh_uvs and mesh_tris:
                # Weighted mesh: compute world positions + UVs
                verts = []
                for i, vtx_bones in enumerate(weights):
                    wx_sum = wy_sum = 0.0
                    for bi, lx, ly, weight in vtx_bones:
                        if bi < 0:
                            b = bone   # unweighted: use slot's own bone
                        elif bi < len(bones):
                            b = bones[bi]
                        else:
                            b = bone
                        wx_sum += (lx * b.m00 + ly * b.m01 + b.world_x) * weight
                        wy_sum += (lx * b.m10 + ly * b.m11 + b.world_y) * weight
                    # Screen coords → NDC
                    sx = cx + wx_sum * scale
                    sy = cy - wy_sum * scale
                    nx, ny = sx / w * 2 - 1, -(sy / h * 2 - 1)

                    # UV in atlas texture
                    if i * 2 + 1 < len(mesh_uvs):
                        json_u, json_v = mesh_uvs[i*2], mesh_uvs[i*2+1]
                    else:
                        json_u, json_v = 0.0, 0.0

                    # Convert JSON UV to atlas texture UV (handles rotate)
                    au, av = self._json_uv_to_atlas(json_u, json_v, rx, ry, rw, rh,
                                                     tex_w, tex_h, atlas_rotate,
                                                     orig_w, orig_h, off_x, off_y,
                                                     stored_w, stored_h)
                    verts.extend([nx, ny, au, av])

                _queue_mesh(tex, verts, mesh_tris)

            else:
                # Simple region attachment: Spine handles atlas trimming in geometry,
                # then maps the packed atlas rectangle to BR, BL, UL, UR vertices.
                corners_screen = self._compute_region_corners_screen_spine(
                    bone, attach, cx, cy, scale,
                    stored_h if atlas_rotate in (90, 270) else stored_w,
                    stored_w if atlas_rotate in (90, 270) else stored_h,
                    orig_w, orig_h, off_x, off_y)
                uv_corners = self._region_uv_corners(
                    rx, ry, stored_w, stored_h, tex_w, tex_h, atlas_rotate)
                verts = []
                for (sx2, sy2), (au, av) in zip(corners_screen, uv_corners):
                    nx, ny = sx2 / w * 2 - 1, -(sy2 / h * 2 - 1)
                    verts.extend([nx, ny, au, av])
                tris = [0,1,2, 0,2,3]
                _queue_mesh(tex, verts, tris)

        _flush_batch()
        self._prog.release()

    def _json_uv_to_atlas(self, json_u: float, json_v: float,
                           rx: int, ry: int, rw: int, rh: int,
                           tex_w: int, tex_h: int,
                           atlas_rotate: bool,
                           orig_w: int | float | None = None,
                           orig_h: int | float | None = None,
                           off_x: int | float = 0,
                           off_y: int | float = 0,
                           stored_w: int | float | None = None,
                           stored_h: int | float | None = None) -> tuple[float, float]:
        """Map JSON mesh UV (natural image space) → atlas GL texture UV.

        Spine atlas rotate:90 = image stored CW 90° in atlas.
        Natural → atlas: atlas_u = natural_v, atlas_v = 1 - natural_u
        """
        ow = float(orig_w or rw)
        oh = float(orig_h or rh)
        ox = float(off_x or 0)
        oy = float(off_y or 0)
        rotation = _atlas_rotation_degrees(atlas_rotate)
        packed_w = float(stored_w if stored_w is not None else (rh if rotation in (90, 270) else rw))
        packed_h = float(stored_h if stored_h is not None else (rw if rotation in (90, 270) else rh))

        if rotation == 90:
            atlas_px = rx - (oh - oy - packed_w) + json_v * oh
            atlas_py = ry - (ow - ox - packed_h) + (1.0 - json_u) * ow
        elif rotation == 180:
            atlas_px = rx - (ow - ox - packed_w) + (1.0 - json_u) * ow
            atlas_py = ry - oy + (1.0 - json_v) * oh
        elif rotation == 270:
            atlas_px = rx - oy + (1.0 - json_v) * oh
            atlas_py = ry - ox + json_u * ow
        else:
            atlas_px = rx - ox + json_u * ow
            atlas_py = ry - (oh - oy - packed_h) + json_v * oh

        atlas_px = max(float(rx), min(float(rx) + packed_w - 1.0, atlas_px))
        atlas_py = max(float(ry), min(float(ry) + packed_h - 1.0, atlas_py))

        return atlas_px / tex_w, atlas_py / tex_h

    def _compute_region_corners_screen(self, bone, attach: RegionAttachment,
                                        cx, cy, scale) -> list:
        """4 screen corners: TL, TR, BR, BL."""
        aw = attach.width  * attach.scale_x / 2
        ah = attach.height * attach.scale_y / 2
        local = [(-aw, -ah), (aw, -ah), (aw, ah), (-aw, ah)]
        r = math.radians(attach.rotation)
        cr, sr = math.cos(r), math.sin(r)
        result = []
        for lx, ly in local:
            rx2 = lx * cr - ly * sr + attach.x
            ry2 = lx * sr + ly * cr + attach.y
            wx = rx2 * bone.m00 + ry2 * bone.m01 + bone.world_x
            wy = rx2 * bone.m10 + ry2 * bone.m11 + bone.world_y
            result.append((cx + wx * scale, cy - wy * scale))
        return result

    def _compute_region_corners_screen_spine(
        self, bone, attach: RegionAttachment,
        cx, cy, scale,
        packed_w: int | float, packed_h: int | float,
        orig_w: int | float, orig_h: int | float,
        off_x: int | float, off_y: int | float,
    ) -> list:
        """Spine RegionAttachment world vertices in BR, BL, UL, UR order."""
        width = float(attach.width) * float(attach.scale_x)
        height = float(attach.height) * float(attach.scale_y)
        ow = max(1.0, float(orig_w or packed_w or width))
        oh = max(1.0, float(orig_h or packed_h or height))
        pw = float(packed_w or ow)
        ph = float(packed_h or oh)
        ox = float(off_x or 0)
        oy = float(off_y or 0)

        local_x = -width / 2.0 + ox / ow * width
        local_y = -height / 2.0 + oy / oh * height
        local_x2 = width / 2.0 - (ow - ox - pw) / ow * width
        local_y2 = height / 2.0 - (oh - oy - ph) / oh * height

        r = math.radians(float(attach.rotation))
        cr, sr = math.cos(r), math.sin(r)
        ax, ay = float(attach.x), float(attach.y)

        def world_point(lx: float, ly: float) -> tuple[float, float]:
            rx2 = lx * cr - ly * sr + ax
            ry2 = lx * sr + ly * cr + ay
            wx = rx2 * bone.m00 + ry2 * bone.m01 + bone.world_x
            wy = rx2 * bone.m10 + ry2 * bone.m11 + bone.world_y
            return cx + wx * scale, cy - wy * scale

        return [
            world_point(local_x2, local_y),   # BR
            world_point(local_x, local_y),    # BL
            world_point(local_x, local_y2),   # UL
            world_point(local_x2, local_y2),  # UR
        ]

    def _region_uv_corners(
        self,
        rx: int, ry: int, rw: int, rh: int,
        tex_w: int, tex_h: int,
        atlas_rotate: bool,
    ) -> list[tuple[float, float]]:
        """Packed atlas UVs in BR, BL, UL, UR order."""
        sw = float(rw)
        sh = float(rh)
        rotation = _atlas_rotation_degrees(atlas_rotate)
        if rotation == 90:
            br = (rx + sw, ry)
            bl = (rx + sw, ry + sh)
            ul = (rx, ry + sh)
            ur = (rx, ry)
        elif rotation == 180:
            br = (rx, ry)
            bl = (rx + sw, ry)
            ul = (rx + sw, ry + sh)
            ur = (rx, ry + sh)
        elif rotation == 270:
            br = (rx, ry + sh)
            bl = (rx, ry)
            ul = (rx + sw, ry)
            ur = (rx + sw, ry + sh)
        else:
            br = (rx + sw, ry + sh)
            bl = (rx, ry + sh)
            ul = (rx, ry)
            ur = (rx + sw, ry)
        return [
            (br[0] / tex_w, br[1] / tex_h),
            (bl[0] / tex_w, bl[1] / tex_h),
            (ul[0] / tex_w, ul[1] / tex_h),
            (ur[0] / tex_w, ur[1] / tex_h),
        ]

    def _draw_mesh(self, gl, tex, verts_flat, triangles):
        """Upload and draw a textured mesh using glDrawArrays (no IBO needed)."""
        if not verts_flat or not triangles:
            return

        expanded = []
        self._append_expanded_vertices(expanded, verts_flat, triangles)
        self._draw_expanded_mesh(gl, tex, expanded)

    @staticmethod
    def _append_expanded_vertices(out: list[float], verts_flat, triangles) -> None:
        if not verts_flat or not triangles:
            return
        stride4 = 4
        max_len = len(verts_flat)
        for i in range(0, len(triangles), 3):
            for idx in triangles[i:i + 3]:
                base = int(idx) * stride4
                if base < 0 or base + stride4 > max_len:
                    continue
                out.extend(verts_flat[base:base + stride4])

    def _draw_expanded_mesh(self, gl, tex, expanded) -> None:
        if not expanded:
            return
        stride4 = 4
        v_arr = np.array(expanded, dtype=np.float32)
        n_verts = len(expanded) // stride4
        if n_verts <= 0:
            return

        tex.bind(0)
        self._vbo.bind()
        self._vbo.allocate(v_arr.tobytes(), v_arr.nbytes)

        stride_bytes = stride4 * 4  # 4 floats × 4 bytes = 16
        self._prog.enableAttributeArray(0)
        self._prog.enableAttributeArray(1)
        self._prog.setAttributeBuffer(0, _GL_FLOAT, 0, 2, stride_bytes)
        self._prog.setAttributeBuffer(1, _GL_FLOAT, 8, 2, stride_bytes)

        gl.glDrawArrays(_GL_TRIANGLES, 0, n_verts)

        self._prog.disableAttributeArray(0)
        self._prog.disableAttributeArray(1)
        self._vbo.release()
        tex.release(0)

    # ── grid / bones (QPainter) ───────────────────────────────────────────

    def _draw_grid(self, p: QPainter):
        step = 50 * self._zoom
        if step < 8:
            return
        w, h = self.width(), self.height()
        ox = self._offset.x() % step
        oy = self._offset.y() % step
        major = step * 5
        major_ox = self._offset.x() % major
        major_oy = self._offset.y() % major

        p.setPen(QPen(self.GRID_COLOR, 1))
        x = ox
        while x < w:
            p.drawLine(int(x), 0, int(x), h); x += step
        y = oy
        while y < h:
            p.drawLine(0, int(y), w, int(y)); y += step
        p.setPen(QPen(self.GRID_MAJOR_COLOR, 1))
        x = major_ox
        while x < w:
            p.drawLine(int(x), 0, int(x), h); x += major
        y = major_oy
        while y < h:
            p.drawLine(0, int(y), w, int(y)); y += major

    def _draw_final_frame_overlay(self, p: QPainter) -> None:
        if self._placement_view_mode != "work":
            return
        rect = QRectF(self._frame_rect)
        if rect.width() <= 0 or rect.height() <= 0:
            return
        viewport = QRectF(0, 0, self.width(), self.height())
        if abs(rect.x()) < 1.0 and abs(rect.y()) < 1.0:
            if abs(rect.width() - viewport.width()) < 1.0 and abs(rect.height() - viewport.height()) < 1.0:
                return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outside = QPainterPath()
        outside.addRect(viewport)
        inside = QPainterPath()
        inside.addRoundedRect(rect, 10, 10)
        outside = outside.subtracted(inside)
        p.fillPath(outside, QColor(0, 0, 0, 72))

        pen = QPen(QColor(255, 112, 77, 204), 1.6)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 10, 10)

        p.setPen(QPen(QColor("#ffffff70"), 1))
        corner = 10.0
        for x0, y0, sx, sy in (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        ):
            p.drawLine(QPointF(x0, y0), QPointF(x0 + corner * sx, y0))
            p.drawLine(QPointF(x0, y0), QPointF(x0, y0 + corner * sy))
        p.restore()

    def _draw_bones(self, p: QPainter):
        if not self._skeleton:
            return
        p.setOpacity(0.3 if (self._atlas and self._show_sprites) else 1.0)
        for bone in self._skeleton.bones:
            sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
            tx, ty = bone.tip_pos()
            tsx, tsy = self.world_to_screen(tx, ty)
            is_sel = bone.name == self._selected
            is_hov = bone.name == self._hovered
            is_root = bone.parent is None
            if bone.length > 0:
                color = (self.BONE_SELECTED if is_sel else
                         self.BONE_HOVER if is_hov else
                         self.ROOT_COLOR if is_root else self.BONE_COLOR)
                self._draw_bone_stick(p, sx, sy, tsx, tsy, color, is_sel)
            r = 6 if is_sel else 4
            p.setBrush(QBrush(self.BONE_SELECTED if is_sel else QColor("#ffffff80")))
            p.setPen(QPen(QColor("#000000a0"), 1))
            p.drawEllipse(int(sx)-r, int(sy)-r, r*2, r*2)
        p.setOpacity(1.0)

    def _draw_bone_stick(self, p, sx, sy, tx, ty, color, bold):
        dx, dy = tx-sx, ty-sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = -dy/length, dx/length
        w2 = max(3, min(10, length*0.12))
        pts = [QPointF(sx+nx*w2*0.3, sy+ny*w2*0.3),
               QPointF(sx+dx*0.15+nx*w2, sy+dy*0.15+ny*w2),
               QPointF(tx, ty),
               QPointF(sx+dx*0.15-nx*w2, sy+dy*0.15-ny*w2),
               QPointF(sx-nx*w2*0.3, sy-ny*w2*0.3)]
        path = QPainterPath()
        path.moveTo(pts[0])
        for pt in pts[1:]: path.lineTo(pt)
        path.closeSubpath()
        fill = QColor(color); fill.setAlpha(180 if bold else 130)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, 1.5 if bold else 1))
        p.drawPath(path)

    def _draw_bone_labels(self, p: QPainter):
        if not self._skeleton:
            return
        p.setFont(QFont("Segoe UI", 8))
        for bone in self._skeleton.bones:
            if bone.name == self._selected:
                sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
                p.setPen(QColor("#ffffffc0"))
                p.drawText(int(sx)+8, int(sy)-4, bone.name)

    # ── fit ───────────────────────────────────────────────────────────────

    def _fit_and_update(self):
        self._fit_skeleton()
        self.update()

    def _visual_bounds(self) -> tuple[float, float, float, float] | None:
        if not self._skeleton:
            return None
        self._skeleton.update_world_transforms()
        resolved_skin = self._active_skin or "default"
        merged: dict = {}
        for sn, atts in self._skeleton.skins.get("default", {}).items():
            merged[sn] = dict(atts)
        for sn, atts in self._skeleton.skins.get(resolved_skin, {}).items():
            merged.setdefault(sn, {}).update(atts)

        xs: list[float] = []
        ys: list[float] = []
        bones = self._skeleton.bones
        for slot in self._skeleton.slots:
            if not slot.attachment:
                continue
            bone = self._skeleton.bone(slot.bone)
            if bone is None:
                continue
            attach = merged.get(slot.name, {}).get(slot.attachment)
            if not isinstance(attach, RegionAttachment):
                continue
            if getattr(attach, "_non_visual", False):
                continue

            weights = self._mesh_weights_for(slot.name, slot.attachment, attach)
            if weights:
                for vtx_bones in weights:
                    wx_sum = wy_sum = 0.0
                    for bi, lx, ly, weight in vtx_bones:
                        if bi < 0:
                            b = bone
                        elif bi < len(bones):
                            b = bones[bi]
                        else:
                            b = bone
                        wx_sum += (lx * b.m00 + ly * b.m01 + b.world_x) * weight
                        wy_sum += (lx * b.m10 + ly * b.m11 + b.world_y) * weight
                    xs.append(wx_sum)
                    ys.append(wy_sum)
                continue

            region_name = attach.path or attach.name
            entry = self._atlas.get(region_name)
            if entry and len(entry) >= 5:
                aw, ah = float(entry[3]), float(entry[4])
            else:
                aw, ah = float(attach.width), float(attach.height)
            hw = max(1.0, aw * float(getattr(attach, "scale_x", 1.0))) / 2.0
            hh = max(1.0, ah * float(getattr(attach, "scale_y", 1.0))) / 2.0
            rot = math.radians(float(getattr(attach, "rotation", 0.0)))
            cr, sr = math.cos(rot), math.sin(rot)
            ax = float(getattr(attach, "x", 0.0))
            ay = float(getattr(attach, "y", 0.0))
            for lx, ly in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                rx = lx * cr - ly * sr + ax
                ry = lx * sr + ly * cr + ay
                xs.append(rx * bone.m00 + ry * bone.m01 + bone.world_x)
                ys.append(rx * bone.m10 + ry * bone.m11 + bone.world_y)

        if not xs or not ys:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    def _fit_skeleton(self):
        if not self._skeleton:
            return
        vw, vh = max(1, self.width()), max(1, self.height())
        import math as _math
        bounds = self._visual_bounds()
        if bounds is not None:
            min_x, min_y, max_x, max_y = bounds
            skel_w = max(1.0, max_x - min_x)
            skel_h = max(1.0, max_y - min_y)
            cx_w = (min_x + max_x) / 2
            cy_w = (min_y + max_y) / 2
            self._fit_center = (cx_w, cy_w)
            self._fit_zoom = max(0.02, min(20.0, min(
                vw * SPINE_PREVIEW_FIT_MARGIN / skel_w,
                vh * SPINE_PREVIEW_FIT_MARGIN / skel_h,
            )))
            self._apply_placement()
            return

        # Filter out NaN/infinity bone positions
        xs = [b.world_x for b in self._skeleton.bones
              if _math.isfinite(b.world_x) and abs(b.world_x) < 1e6]
        ys = [b.world_y for b in self._skeleton.bones
              if _math.isfinite(b.world_y) and abs(b.world_y) < 1e6]
        if not xs or not ys:
            self._fit_center = (0.0, 0.0)
            self._fit_zoom = 0.5
            self._apply_placement()
            return
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        skel_w = max(1.0, max_x - min_x)
        skel_h = max(1.0, max_y - min_y)
        cx_w = (min_x + max_x) / 2
        cy_w = (min_y + max_y) / 2
        self._fit_center = (cx_w, cy_w)
        self._fit_zoom = max(0.02, min(20.0, min(
            vw * SPINE_PREVIEW_FIT_MARGIN / skel_w,
            vh * SPINE_PREVIEW_FIT_MARGIN / skel_h,
        )))
        self._apply_placement()

    # ── mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent):
        pos = e.position()
        if e.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = pos
        elif e.button() == Qt.MouseButton.LeftButton:
            hit = self._bone_at(pos.x(), pos.y())
            self._selected = hit
            self.bone_selected.emit(hit or "")
            if hit:
                self._drag_bone = hit
                self._drag_start_world = self.screen_to_world(pos.x(), pos.y())
            self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        pos = e.position()
        if self._pan_start is not None:
            dp = pos - self._pan_start
            self._offset += dp
            self._pan_start = pos
            self.update()
        elif self._drag_bone and self._drag_start_world:
            wx, wy = self.screen_to_world(pos.x(), pos.y())
            dx = wx - self._drag_start_world[0]
            dy = wy - self._drag_start_world[1]
            self._drag_start_world = (wx, wy)
            bone = self._skeleton.bone(self._drag_bone) if self._skeleton else None
            if bone:
                bone.x += dx; bone.y += dy
                self._skeleton.update_world_transforms()
                self.bone_moved.emit(self._drag_bone, bone.x, bone.y)
                self.update()
        else:
            hover = self._bone_at(pos.x(), pos.y())
            if hover != self._hovered:
                self._hovered = hover; self.update()

    def mouseReleaseEvent(self, _):
        self._pan_start = None
        self._drag_bone = None
        self._drag_start_world = None

    def wheelEvent(self, e: QWheelEvent):
        factor = 1.12 if e.angleDelta().y() > 0 else 1/1.12
        pos = e.position()
        self._offset = QPointF(
            pos.x() - (pos.x()-self._offset.x())*factor,
            pos.y() - (pos.y()-self._offset.y())*factor)
        self._zoom = max(0.05, min(20.0, self._zoom*factor))
        self.update()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F:
            self._fit_skeleton(); self.update()

    def _bone_at(self, sx, sy):
        if not self._skeleton:
            return None
        best, best_d = None, 12.0
        for bone in self._skeleton.bones:
            bx, by = self.world_to_screen(bone.world_x, bone.world_y)
            d = math.hypot(sx-bx, sy-by)
            if d < best_d:
                best_d, best = d, bone.name
        return best
