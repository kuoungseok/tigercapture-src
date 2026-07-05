"""CPU-based Spine viewport — QPainter + SpineRenderer (PIL).

No OpenGL required. Renders at ~30 fps using the same SpineRenderer
used for thumbnails, so what-you-see-in-viewport == what-you-see-in-export.
"""
from __future__ import annotations
import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPointF, Signal
from PySide6.QtGui import (
    QColor, QImage, QPainter, QPen, QBrush, QPainterPath,
    QFont, QMouseEvent, QWheelEvent, QPixmap,
)
from PySide6.QtWidgets import QWidget

from app.spine_editor.spine_data import SpineSkeleton


class SpineCPUViewport(QWidget):
    """Spine character viewport — pure CPU rendering via SpineRenderer."""

    bone_selected = Signal(str)
    bone_moved    = Signal(str, float, float)

    BONE_COLOR       = QColor("#5ec8e5")
    BONE_SELECTED    = QColor("#ff8c00")
    BONE_HOVER       = QColor("#a0e8ff")
    ROOT_COLOR       = QColor("#e55555")
    BG_COLOR         = QColor("#1a1a28")
    GRID_COLOR       = QColor("#30384F")
    GRID_MAJOR_COLOR = QColor("#353550")

    _FPS_MS = 33

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton:  Optional[SpineSkeleton] = None
        self._renderer   = None          # SpineRenderer instance
        self._pixmap:    Optional[QPixmap] = None
        self._selected:  Optional[str] = None
        self._hovered:   Optional[str] = None
        self._show_sprites = True
        self._show_bones   = True
        self._active_skin  = "default"

        self._offset = QPointF(0.0, 0.0)
        self._zoom   = 1.0

        self._pan_start:       Optional[QPointF] = None
        self._drag_bone:       Optional[str] = None
        self._drag_start_world: Optional[tuple] = None

        self._anim_name: str   = ""
        self._anim_time: float = 0.0
        self._playing:   bool  = False

        # Render timer — only ticks when animation is playing
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(self._FPS_MS)
        self._render_timer.timeout.connect(self._on_tick)

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 400)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)

    # ── public API ────────────────────────────────────────────────────────

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton   = skel
        self._renderer   = None
        self._pixmap     = None
        self._anim_name  = ""
        self._anim_time  = 0.0
        QTimer.singleShot(0, self._fit_and_render)

    def set_renderer_data(self, atlas: dict, pil_pages: list,
                          pma: bool = False) -> None:
        if self._skeleton is None:
            return
        try:
            from app.spine_editor.spine_renderer import SpineRenderer
            self._renderer = SpineRenderer(
                self._skeleton, atlas, pil_pages, pma=pma
            )
        except Exception as e:
            import sys
            print(f"[spine viewport] renderer init failed: {e}", file=sys.stderr)
            self._renderer = None
        self._render_frame()
        self.update()

    def clear_sprites(self) -> None:
        self._renderer = None
        self._pixmap   = None
        self.update()

    def clear(self) -> None:
        self._skeleton = None
        self._selected = None
        self.clear_sprites()

    def selected_bone(self) -> Optional[str]:
        return self._selected

    def play_anim(self, anim_name: str, time: float = 0.0) -> None:
        self._anim_name  = anim_name
        self._anim_time  = time
        self._playing    = True
        self._render_frame()
        self._render_timer.start()

    def stop_anim(self) -> None:
        self._playing = False
        self._render_timer.stop()

    def seek(self, time: float) -> None:
        self._anim_time = time
        self._render_frame()
        self.update()

    # ── coordinate helpers ────────────────────────────────────────────────

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (self._offset.x() + wx * self._zoom,
                self._offset.y() - wy * self._zoom)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return ((sx - self._offset.x()) / self._zoom,
                -(sy - self._offset.y()) / self._zoom)

    # ── rendering ─────────────────────────────────────────────────────────

    def _on_tick(self) -> None:
        if not self._playing or not self._skeleton or not self._anim_name:
            return
        self._anim_time += self._FPS_MS / 1000.0
        anim = self._skeleton.animations.get(self._anim_name)
        if anim and anim.duration > 0:
            self._anim_time %= anim.duration
        self._render_frame()
        self.update()

    def _render_frame(self) -> None:
        if not self._renderer or not self._skeleton:
            return
        w, h = max(4, self.width()), max(4, self.height())
        try:
            import numpy as _np
            img = self._renderer.render(
                width=w, height=h,
                scale=self._zoom,
                anim_name=self._anim_name or None,
                time=self._anim_time,
                skin_name=self._active_skin,
                offset_x=self._offset.x() - w / 2,
                offset_y=-(self._offset.y() - h / 2),
            )
            if img is not None:
                arr = _np.asarray(img, dtype=_np.uint8)
                qi = QImage(arr.data, w, h, arr.strides[0],
                            QImage.Format.Format_RGBA8888).copy()
                self._pixmap = QPixmap.fromImage(qi)
        except Exception as e:
            import sys
            print(f"[spine viewport] render error: {e}", file=sys.stderr)

    def _fit_and_render(self) -> None:
        self._fit_skeleton()
        self._render_frame()
        self.update()

    def _fit_skeleton(self) -> None:
        if not self._skeleton:
            return
        vw, vh = max(1, self.width()), max(1, self.height())
        xs, ys = [], []
        for bone in self._skeleton.bones:
            xs.append(bone.world_x); ys.append(bone.world_y)
        if not xs:
            return
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        skel_w = max(1.0, max_x - min_x)
        skel_h = max(1.0, max_y - min_y)
        cx_w = (min_x + max_x) / 2
        cy_w = (min_y + max_y) / 2
        self._zoom = max(0.05, min(20.0, min(vw * 0.75 / skel_w,
                                              vh * 0.75 / skel_h)))
        self._offset = QPointF(vw / 2 - cx_w * self._zoom,
                               vh / 2 + cy_w * self._zoom)

    # ── paint ─────────────────────────────────────────────────────────────

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, self.BG_COLOR)

        # Sprite layer
        if self._show_sprites and self._pixmap:
            p.drawPixmap(0, 0, self._pixmap)

        # Grid
        self._draw_grid(p)

        # Bones overlay
        if self._skeleton and self._show_bones:
            self._draw_bones(p)
            self._draw_bone_labels(p)

        # Origin crosshair
        ox, oy = self.world_to_screen(0, 0)
        p.setPen(QPen(QColor("#ffffff40"), 1))
        p.drawLine(int(ox) - 10, int(oy), int(ox) + 10, int(oy))
        p.drawLine(int(ox), int(oy) - 10, int(ox), int(oy) + 10)

        p.end()

    def _draw_grid(self, p: QPainter) -> None:
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

    def _draw_bones(self, p: QPainter) -> None:
        if not self._skeleton:
            return
        opacity = 0.35 if (self._renderer and self._show_sprites) else 1.0
        p.setOpacity(opacity)
        for bone in self._skeleton.bones:
            sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
            tx, ty = bone.tip_pos()
            tsx, tsy = self.world_to_screen(tx, ty)
            is_sel  = bone.name == self._selected
            is_hov  = bone.name == self._hovered
            is_root = bone.parent is None
            if bone.length > 0:
                color = (self.BONE_SELECTED if is_sel else
                         self.BONE_HOVER if is_hov else
                         self.ROOT_COLOR if is_root else self.BONE_COLOR)
                self._draw_bone_stick(p, sx, sy, tsx, tsy, color, is_sel)
            r = 6 if is_sel else 4
            p.setBrush(QBrush(self.BONE_SELECTED if is_sel else QColor("#ffffff80")))
            p.setPen(QPen(QColor("#000000a0"), 1))
            p.drawEllipse(int(sx) - r, int(sy) - r, r * 2, r * 2)
        p.setOpacity(1.0)

    def _draw_bone_stick(self, p, sx, sy, tx, ty, color, bold):
        dx, dy = tx - sx, ty - sy
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = -dy / length, dx / length
        w2 = max(3, min(10, length * 0.12))
        pts = [
            QPointF(sx + nx * w2 * 0.3, sy + ny * w2 * 0.3),
            QPointF(sx + dx * 0.15 + nx * w2, sy + dy * 0.15 + ny * w2),
            QPointF(tx, ty),
            QPointF(sx + dx * 0.15 - nx * w2, sy + dy * 0.15 - ny * w2),
            QPointF(sx - nx * w2 * 0.3, sy - ny * w2 * 0.3),
        ]
        path = QPainterPath()
        path.moveTo(pts[0])
        for pt in pts[1:]:
            path.lineTo(pt)
        path.closeSubpath()
        fill = QColor(color)
        fill.setAlpha(180 if bold else 130)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(color, 1.5 if bold else 1))
        p.drawPath(path)

    def _draw_bone_labels(self, p: QPainter) -> None:
        if not self._skeleton:
            return
        p.setFont(QFont("Segoe UI", 8))
        for bone in self._skeleton.bones:
            if bone.name == self._selected:
                sx, sy = self.world_to_screen(bone.world_x, bone.world_y)
                p.setPen(QColor("#ffffffc0"))
                p.drawText(int(sx) + 8, int(sy) - 4, bone.name)

    # ── mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, e: QMouseEvent) -> None:
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

    def mouseMoveEvent(self, e: QMouseEvent) -> None:
        pos = e.position()
        if self._pan_start is not None:
            dp = pos - self._pan_start
            self._offset += dp
            self._pan_start = pos
            self._render_frame()
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
                self._render_frame()
                self.update()
        else:
            hover = self._bone_at(pos.x(), pos.y())
            if hover != self._hovered:
                self._hovered = hover
                self.update()

    def mouseReleaseEvent(self, _) -> None:
        self._pan_start     = None
        self._drag_bone     = None
        self._drag_start_world = None

    def wheelEvent(self, e: QWheelEvent) -> None:
        factor = 1.12 if e.angleDelta().y() > 0 else 1 / 1.12
        pos = e.position()
        self._offset = QPointF(
            pos.x() - (pos.x() - self._offset.x()) * factor,
            pos.y() - (pos.y() - self._offset.y()) * factor,
        )
        self._zoom = max(0.05, min(20.0, self._zoom * factor))
        self._render_frame()
        self.update()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_F:
            self._fit_skeleton()
            self._render_frame()
            self.update()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._render_frame()

    def _bone_at(self, sx, sy) -> Optional[str]:
        if not self._skeleton:
            return None
        best, best_d = None, 12.0
        for bone in self._skeleton.bones:
            bx, by = self.world_to_screen(bone.world_x, bone.world_y)
            d = math.hypot(sx - bx, sy - by)
            if d < best_d:
                best_d, best = d, bone.name
        return best
