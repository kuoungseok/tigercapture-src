"""Spine editor main viewport — renders bones and handles mouse interaction."""
from __future__ import annotations
import math
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPainterPath,
    QMouseEvent, QWheelEvent, QImage,
)
from PySide6.QtWidgets import QWidget
from PIL import Image

from app.spine_editor.spine_data import SpineSkeleton, Bone
from app.spine_editor.layout import SPINE_PREVIEW_FIT_MARGIN

if TYPE_CHECKING:
    from app.spine_editor.spine_renderer import SpineRenderer


class SpineViewport(QWidget):
    """Canvas for displaying and editing Spine skeletons.

    Coordinate system: world space with Y-up, viewport centre = (0,0).
    """
    bone_selected = Signal(str)     # bone name or "" for deselect
    bone_moved = Signal(str, float, float)   # name, dx, dy

    BONE_COLOR         = QColor("#5ec8e5")
    BONE_SELECTED      = QColor("#ff8c00")
    BONE_HOVER         = QColor("#a0e8ff")
    ROOT_COLOR         = QColor("#e55555")
    BG_COLOR           = QColor("#1a1a28")
    GRID_COLOR         = QColor("#30384F")
    GRID_MAJOR_COLOR   = QColor("#353550")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._selected: Optional[str] = None
        self._hovered: Optional[str] = None

        # Layer sprites: list of (QImage, spine_x, spine_y, width, height)
        self._sprites: list[tuple[QImage, float, float, float, float]] = []
        # Show/hide sprites
        self._show_sprites: bool = True

        self._renderer: Optional["SpineRenderer"] = None
        self._active_skin: str = "default"
        self._show_bones: bool = True   # toggled by toolbar

        # Viewport transform
        self._offset = QPointF(0.0, 0.0)   # pan offset in screen px
        self._zoom   = 1.0

        self._pan_start: Optional[QPoint] = None
        self._drag_bone: Optional[str] = None
        self._drag_start_world: Optional[tuple[float, float]] = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 400)

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton = skel
        self._fit_skeleton()
        self.update()

    def set_sprites(self, sprites: list[tuple["QImage", float, float, float, float]]) -> None:
        """Set layer sprite images. Each tuple: (qimage, spine_cx, spine_cy, w, h)."""
        self._sprites = sprites
        self.update()

    def clear_sprites(self) -> None:
        self._sprites.clear()
        self.update()

    def set_renderer(self, renderer: "SpineRenderer") -> None:
        self._renderer = renderer
        # Delay fit so viewport is fully laid out first
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, self._fit_and_update)
        self.update()

    def _fit_and_update(self) -> None:
        self._fit_skeleton()
        self.update()

    @staticmethod
    def pil_to_qimage(img: "Image.Image") -> QImage:
        """Convert a PIL RGBA image to QImage."""
        img = img.convert("RGBA")
        data = img.tobytes("raw", "RGBA")
        return QImage(data, img.width, img.height, img.width * 4,
                      QImage.Format.Format_RGBA8888).copy()

    def selected_bone(self) -> Optional[str]:
        return self._selected

    # ── coordinate conversion ─────────────────────────────────────────────

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        cx = self._offset.x() + wx * self._zoom
        cy = self._offset.y() - wy * self._zoom   # flip Y
        return cx, cy

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        wx = (sx - self._offset.x()) / self._zoom
        wy = -(sy - self._offset.y()) / self._zoom
        return wx, wy

    # ── painting ──────────────────────────────────────────────────────────

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        p.fillRect(self.rect(), self.BG_COLOR)

        # Grid
        self._draw_grid(p)

        if self._show_sprites and self._sprites:
            self._draw_sprites(p)

        if self._renderer and self._show_sprites:
            self._draw_slot_sprites(p)

        if self._skeleton and self._show_bones:
            has_sprites = self._renderer is not None and self._show_sprites
            if has_sprites:
                p.setOpacity(0.25)
            self._draw_bones(p)
            if has_sprites:
                p.setOpacity(1.0)
            self._draw_bone_labels(p)

        # Origin cross
        ox, oy = self.world_to_screen(0, 0)
        p.setPen(QPen(QColor("#ffffff40"), 1))
        p.drawLine(int(ox) - 10, int(oy), int(ox) + 10, int(oy))
        p.drawLine(int(ox), int(oy) - 10, int(ox), int(oy) + 10)

        p.end()

    def _draw_grid(self, p: QPainter):
        step = 50 * self._zoom
        if step < 8:
            return
        w, h = self.width(), self.height()
        ox = self._offset.x() % step
        oy = self._offset.y() % step

        # Major every 5
        major_step = step * 5
        major_ox = self._offset.x() % major_step
        major_oy = self._offset.y() % major_step

        p.setPen(QPen(self.GRID_COLOR, 1))
        x = ox
        while x < w:
            p.drawLine(int(x), 0, int(x), h)
            x += step
        y = oy
        while y < h:
            p.drawLine(0, int(y), w, int(y))
            y += step

        p.setPen(QPen(self.GRID_MAJOR_COLOR, 1))
        x = major_ox
        while x < w:
            p.drawLine(int(x), 0, int(x), h)
            x += major_step
        y = major_oy
        while y < h:
            p.drawLine(0, int(y), w, int(y))
            y += major_step

    def _draw_bones(self, p: QPainter):
        skel = self._skeleton
        for bone in skel.bones:
            sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
            tx, ty = bone.tip_pos()
            tsx, tsy = self.world_to_screen(tx, ty)

            is_selected = bone.name == self._selected
            is_hovered = bone.name == self._hovered
            is_root = bone.parent is None

            # Bone stick (diamond shape)
            if bone.length > 0:
                color = (self.BONE_SELECTED if is_selected
                         else self.BONE_HOVER if is_hovered
                         else self.ROOT_COLOR if is_root
                         else self.BONE_COLOR)
                self._draw_bone_stick(p, sx, sy, tsx, tsy, color, is_selected)

            # Joint circle
            r = 6 if is_selected else 5
            p.setBrush(QBrush(self.BONE_SELECTED if is_selected else QColor("#ffffff80")))
            p.setPen(QPen(QColor("#000000a0"), 1))
            p.drawEllipse(int(sx) - r, int(sy) - r, r * 2, r * 2)

    def _draw_bone_stick(self, p, sx, sy, tx, ty, color, bold):
        """Draw a bone as a tapered quadrilateral (classic Spine style)."""
        dx = tx - sx
        dy = ty - sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = -dy / length, dx / length   # perpendicular
        w = max(3, min(12, length * 0.12))

        pts = [
            QPointF(sx + nx * w * 0.3, sy + ny * w * 0.3),
            QPointF(sx + dx * 0.15 + nx * w, sy + dy * 0.15 + ny * w),
            QPointF(tx, ty),
            QPointF(sx + dx * 0.15 - nx * w, sy + dy * 0.15 - ny * w),
            QPointF(sx - nx * w * 0.3, sy - ny * w * 0.3),
        ]
        path = QPainterPath()
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        path.closeSubpath()

        fill = QColor(color)
        fill.setAlpha(180 if bold else 140)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, 1.5 if bold else 1))
        p.drawPath(path)

    def _draw_sprites(self, p: QPainter):
        p.setOpacity(0.85)
        for qimg, cx, cy, w, h in self._sprites:
            scx, scy = self.world_to_screen(cx, cy)
            sw = w * self._zoom
            sh = h * self._zoom
            rect = QRectF(scx - sw / 2, scy - sh / 2, sw, sh)
            p.drawImage(rect, qimg)
        p.setOpacity(1.0)

    def _draw_slot_sprites(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        offset_x = self._offset.x() - w / 2
        offset_y = -(self._offset.y() - h / 2)
        try:
            pil_img = self._renderer.render(
                width=w, height=h,
                scale=self._zoom,
                skin_name=self._active_skin,
                offset_x=offset_x,
                offset_y=offset_y,
            )
            qimg = self.pil_to_qimage(pil_img)
            p.drawImage(0, 0, qimg)
        except Exception as e:
            import traceback, sys
            print(f"[spine.viewport] render error: {e}\n{traceback.format_exc()}", file=sys.stderr)

    def _draw_bone_labels(self, p: QPainter):
        f = QFont("Segoe UI", 8)
        p.setFont(f)
        for bone in (self._skeleton.bones if self._skeleton else []):
            if bone.name == self._selected:
                sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
                p.setPen(QColor("#ffffffc0"))
                p.drawText(int(sx) + 8, int(sy) - 4, bone.name)

    # ── hit testing ───────────────────────────────────────────────────────

    def _bone_at(self, sx: float, sy: float) -> Optional[str]:
        if not self._skeleton:
            return None
        best, best_d = None, 12.0
        for bone in self._skeleton.bones:
            bx, by = self.world_to_screen(bone.world_x, bone.world_y)
            d = math.hypot(sx - bx, sy - by)
            if d < best_d:
                best_d, best = d, bone.name
        return best

    # ── mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent):
        pos = e.position()
        if e.button() == Qt.MouseButton.MiddleButton:
            self._pan_start = e.position().toPoint()
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
            dp = e.position().toPoint() - self._pan_start
            self._offset += QPointF(dp.x(), dp.y())
            self._pan_start = e.position().toPoint()
            self.update()
        elif self._drag_bone and self._drag_start_world:
            wx, wy = self.screen_to_world(pos.x(), pos.y())
            dx = wx - self._drag_start_world[0]
            dy = wy - self._drag_start_world[1]
            self._drag_start_world = (wx, wy)
            bone = self._skeleton.bone(self._drag_bone) if self._skeleton else None
            if bone:
                bone.x += dx
                bone.y += dy
                self._skeleton.update_world_transforms()
                self.bone_moved.emit(self._drag_bone, bone.x, bone.y)
                self.update()
        else:
            hover = self._bone_at(pos.x(), pos.y())
            if hover != self._hovered:
                self._hovered = hover
                self.update()

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._pan_start = None
        self._drag_bone = None
        self._drag_start_world = None

    def wheelEvent(self, e: QWheelEvent):
        factor = 1.12 if e.angleDelta().y() > 0 else 1 / 1.12
        pos = e.position()
        # Zoom towards cursor
        self._offset = QPointF(
            pos.x() - (pos.x() - self._offset.x()) * factor,
            pos.y() - (pos.y() - self._offset.y()) * factor,
        )
        self._zoom = max(0.05, min(20.0, self._zoom * factor))
        self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._skeleton:
            self._fit_skeleton()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_F:
            self._fit_skeleton()
            self.update()

    def _fit_skeleton(self) -> None:
        """Auto-zoom and center to show the full skeleton."""
        if not self._skeleton:
            return
        vw, vh = max(1, self.width()), max(1, self.height())

        # Collect world positions of all bones + attachment extents
        xs, ys = [], []
        import math as _math
        for bone in self._skeleton.bones:
            xs.append(bone.world_x)
            ys.append(bone.world_y)

        # Try to incorporate attachment bounds if renderer available
        if self._renderer:
            skin_name = self._active_skin
            default_sk = self._skeleton.skins.get("default", {})
            sel_sk = self._skeleton.skins.get(skin_name, {})
            merged: dict = {}
            for sn, atts in default_sk.items():
                merged[sn] = dict(atts)
            for sn, atts in sel_sk.items():
                merged.setdefault(sn, {}).update(atts)

            for slot in self._skeleton.slots:
                if not slot.attachment:
                    continue
                bone = self._skeleton.bone(slot.bone)
                if not bone:
                    continue
                attach = merged.get(slot.name, {}).get(slot.attachment)
                if not attach:
                    continue
                try:
                    rad = _math.radians(bone.world_rotation)
                    ax = attach.x * _math.cos(rad) - attach.y * _math.sin(rad)
                    ay = attach.x * _math.sin(rad) + attach.y * _math.cos(rad)
                    wx = bone.world_x + ax
                    wy = bone.world_y + ay
                    hw = attach.width / 2
                    hh = attach.height / 2
                    xs += [wx - hw, wx + hw]
                    ys += [wy - hh, wy + hh]
                except Exception:
                    pass

        # Fallback to skeleton declared size
        if not xs and self._skeleton.width > 0:
            xs = [-self._skeleton.width / 2, self._skeleton.width / 2]
            ys = [0, self._skeleton.height]

        if not xs:
            self._offset = QPointF(vw / 2, vh / 2)
            self._zoom = 1.0
            return

        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        skel_w = max(1, max_x - min_x)
        skel_h = max(1, max_y - min_y)
        cx_world = (min_x + max_x) / 2
        cy_world = (min_y + max_y) / 2

        margin = SPINE_PREVIEW_FIT_MARGIN
        self._zoom = max(0.02, min(20.0, min(vw * margin / skel_w,
                                              vh * margin / skel_h)))
        # offset maps world (cx_world, cy_world) to screen center
        # screen_x = offset_x + world_x * zoom
        # screen_y = offset_y - world_y * zoom   (Y flip)
        self._offset = QPointF(
            vw / 2 - cx_world * self._zoom,
            vh / 2 + cy_world * self._zoom,
        )
