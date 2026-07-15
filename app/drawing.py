from __future__ import annotations

import copy
import math
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPixmap,
    QPolygonF,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


_PAINT_DIALOG_QSS = """
QDialog {
    background-color: #111216;
    color: #f5f7fb;
}

QFrame#PaintTopBar,
QFrame#PaintToolRail,
QFrame#PaintInspector,
QFrame#PaintCanvasFrame {
    background-color: #181a20;
    border: 1px solid #2a2e39;
    border-radius: 10px;
}

QLabel#PaintTitle {
    color: #ffffff;
    font-size: 18px;
    font-weight: 800;
}

QLabel#PaintSubtitle,
QLabel#PaintMeta,
QLabel#PaintCount {
    color: #9ea8ba;
    font-size: 11px;
}

QLabel#PaintSectionTitle {
    color: #dce6f7;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
}

QLabel#PaintValue {
    color: #ffffff;
    background-color: #0f1117;
    border: 1px solid #2c3342;
    border-radius: 6px;
    padding: 3px 7px;
    min-width: 42px;
}

QPushButton#PaintTool,
QPushButton#BubbleBtn,
QPushButton#StickerBtn {
    background-color: #20242d;
    color: #ffffff;
    border: 1px solid #333a49;
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 700;
    text-align: left;
}

QPushButton#PaintTool:hover,
QPushButton#BubbleBtn:hover,
QPushButton#StickerBtn:hover {
    background-color: #2a303c;
    border-color: #4a89ff;
}

QPushButton#PaintTool:checked,
QPushButton#BubbleBtn:checked,
QPushButton#StickerBtn:checked {
    background-color: #263552;
    border-color: #6aa2ff;
    color: #ffffff;
}

QFrame#PaintToolRail QPushButton {
    min-width: 128px;
}

QPushButton#PaintDanger {
    background-color: #2a2020;
    color: #ffdede;
    border: 1px solid #563436;
    border-radius: 8px;
    padding: 9px 12px;
    font-weight: 700;
    text-align: left;
}

QPushButton#PaintDanger:hover {
    background-color: #3a2727;
    border-color: #de6969;
}

QPushButton#PaintCustomColor {
    background-color: #222632;
    color: #ffffff;
    border: 1px solid #394152;
    border-radius: 8px;
    padding: 7px 10px;
    font-weight: 700;
}

QPushButton#PaintCustomColor:hover {
    background-color: #2b3140;
    border-color: #6aa2ff;
}

QFrame#PaintColorPanel {
    background-color: #121722;
    border: 1px solid #273044;
    border-radius: 10px;
}

QLabel#PaintColorWell {
    border: 1px solid #4c5870;
    border-radius: 9px;
}

QLabel#PaintColorHex {
    color: #f5f7fb;
    background-color: #0b0f17;
    border: 1px solid #273044;
    border-radius: 7px;
    padding: 5px 8px;
    font-weight: 800;
}

QSlider::groove:horizontal {
    height: 4px;
    border-radius: 2px;
    background: #303746;
}

QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #9bbcff;
}

QSlider#PaintHueSlider::groove:horizontal {
    height: 8px;
    border-radius: 4px;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #d14f4f,
        stop:0.17 #d9b64d,
        stop:0.33 #69b170,
        stop:0.5 #3f9cd6,
        stop:0.67 #6a58a9,
        stop:0.83 #b75279,
        stop:1 #d14f4f
    );
}

QSlider#PaintHueSlider::handle:horizontal,
QSlider#PaintValueSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -4px 0;
    border-radius: 7px;
    background: #eef2f7;
    border: 1px solid #111827;
}

QComboBox {
    background-color: #0f1117;
    color: #ffffff;
    border: 1px solid #2c3342;
    border-radius: 6px;
    padding: 4px 8px;
    min-width: 118px;
}

QComboBox:hover {
    border-color: #6aa2ff;
}

QListWidget#PaintLayerList {
    background-color: #0f1117;
    color: #dce6f7;
    border: 1px solid #2c3342;
    border-radius: 8px;
    outline: none;
    padding: 4px;
}

QListWidget#PaintLayerList::item {
    border-radius: 5px;
    padding: 5px 7px;
}

QListWidget#PaintLayerList::item:selected {
    background-color: #263552;
    color: #ffffff;
}

QDialogButtonBox QPushButton {
    min-width: 104px;
    padding: 9px 20px;
    border-radius: 8px;
    font-weight: 800;
    font-size: 13px;
}
QDialogButtonBox QPushButton[text="OK"],
QDialogButtonBox QPushButton:default {
    background-color: #f0f3fa;
    color: #171a21;
    border: 1px solid #ffffff;
}
QDialogButtonBox QPushButton:default:hover,
QDialogButtonBox QPushButton[text="OK"]:hover {
    background-color: #ffffff;
}
QDialogButtonBox QPushButton:!default {
    background-color: #242832;
    color: #ffffff;
    border: 1px solid #3a4150;
}
QDialogButtonBox QPushButton:!default:hover {
    background-color: #303645;
}
"""


@dataclass
class Stroke:
    """A drawn stroke overlay on the video.

    - ``points`` are normalized to [0, 1] in the preview widget coord space
      so strokes scale with preview resizing.
    - ``start_ms`` is the project time when the stroke was drawn.
    - ``end_ms`` is None while the stroke is live; set to the erase time when
      the eraser tool marks it invisible from that point onward.
    - A stroke is visible at time ``t`` iff ``start_ms <= t`` and
      (``end_ms`` is None or ``t < end_ms``).
    """

    points: list[tuple[float, float]] = field(default_factory=list)
    color: tuple[int, int, int] = (255, 50, 50)
    opacity: int = 255
    width_px: float = 4.0
    brush_style: str = "round"
    closed_path: bool = False
    start_ms: int = 0
    end_ms: int | None = None

    def is_active(self, t_ms: int) -> bool:
        if t_ms < self.start_ms:
            return False
        if self.end_ms is not None and t_ms >= self.end_ms:
            return False
        return True


class DrawingCanvas(QWidget):
    """Transparent overlay widget that draws strokes on top of the preview.

    - When tool is "off" the widget is click-through (preview gets the clicks,
      or rather nothing does — preview doesn't handle them either).
    - When tool is "pen", left-drag creates a new ``Stroke`` stamped with
      the current project time.
    - When tool is "eraser", left-click removes any stroke whose polyline
      passes within ``ERASE_RADIUS_PX`` of the click.

    The widget queries ``get_time_ms`` / ``get_strokes`` lazily in paint so
    the caller (VideoEditorWindow) owns the data.
    """

    stroke_added = Signal(object)  # Stroke
    stroke_erased_at = Signal(int)  # index in the strokes list
    repaint_requested = Signal()

    ERASE_RADIUS_PX = 18

    def __init__(
        self,
        get_time_ms: Callable[[], int],
        get_strokes: Callable[[], list],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._get_time_ms = get_time_ms
        self._get_strokes = get_strokes

        self._tool: str = "off"
        self._pen_color: QColor = QColor(255, 50, 50)
        self._pen_opacity: int = 255
        self._pen_width: float = 4.0
        self._pen_style: str = "round"
        self._current_points: list[QPointF] = []  # while drawing (widget px)
        self._path_points: list[QPointF] = []
        # Phase E — node-mask polygon editor hook. The editor sets
        # this to a callable when it wants to capture clicks for a
        # Power Window polygon. Returns True if the click was
        # consumed; False lets the regular pen/eraser path run.
        self._click_hook: Callable[[float, float, str], bool] | None = None
        # Stage 1 rotoscope — rectangle drag for GrabCut. When set,
        # mousePress starts a rect, mouseMove updates it, mouseRelease
        # emits final ``(nx, ny, nw, nh)`` to the hook.
        self._rect_hook: Callable[[float, float, float, float], None] | None = None
        self._rect_drag_start: QPointF | None = None
        self._rect_drag_current: QPointF | None = None
        # Color Page direct Power Window editor. The editor owns the grade; this
        # canvas only mirrors the current normalized window and reports drags.
        self._color_window_payload: dict | None = None
        self._color_window_change_hook: Callable[[dict, bool], None] | None = None
        self._color_window_drag_handle: str | None = None
        self._color_window_drag_start: QPointF | None = None
        self._color_window_drag_origin: dict | None = None
        self._extra_paint_hook: Callable[[QPainter, int, int], None] | None = None
        self._interaction_hook: Callable[[str, float, float, QMouseEvent], bool] | None = None
        self._interaction_active = False

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    # ------------- tool / pen config -------------

    def tool(self) -> str:
        return self._tool

    def set_tool(self, tool: str) -> None:
        if tool not in ("off", "pen", "eraser", "path"):
            tool = "off"
        self._tool = tool
        self._refresh_mouse_transparency()
        cursor = (
            Qt.CursorShape.CrossCursor
            if tool in ("pen", "eraser", "path")
            else Qt.CursorShape.ArrowCursor
        )
        self.setCursor(cursor)
        self.update()

    def set_pen_color(self, color: QColor) -> None:
        self._pen_color = QColor(color)

    def set_pen_opacity(self, opacity: int) -> None:
        self._pen_opacity = max(1, min(255, int(opacity)))

    def set_pen_width(self, width: float) -> None:
        self._pen_width = max(1.0, min(80.0, float(width)))

    def set_pen_style(self, style: str) -> None:
        allowed = {"round", "marker", "highlighter", "dashed"}
        self._pen_style = style if style in allowed else "round"
        self.update()

    def set_extra_paint_hook(self, hook: Callable[[QPainter, int, int], None] | None) -> None:
        self._extra_paint_hook = hook
        self.update()

    def set_interaction_hook(self, hook: Callable[[str, float, float, QMouseEvent], bool] | None) -> None:
        self._interaction_hook = hook
        self._interaction_active = False
        self._refresh_mouse_transparency()
        self.update()

    # ------------- paint -------------

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1, self.width())
        h = max(1, self.height())

        t_ms = int(self._get_time_ms())
        for stroke in self._get_strokes():
            if not stroke.is_active(t_ms):
                continue
            self._paint_stroke(painter, stroke, w, h)

        if self._current_points:
            stroke = Stroke(
                points=[(p.x() / w, p.y() / h) for p in self._current_points],
                color=(
                    self._pen_color.red(),
                    self._pen_color.green(),
                    self._pen_color.blue(),
                ),
                opacity=self._pen_opacity,
                width_px=self._pen_width,
                brush_style=self._pen_style,
            )
            self._paint_stroke(painter, stroke, w, h)

        if self._path_points:
            color = QColor(self._pen_color)
            color.setAlpha(max(90, min(220, self._pen_opacity)))
            pen = QPen(color, max(1.0, self._pen_width))
            self._configure_pen_for_style(pen, self._pen_style)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            if len(self._path_points) == 1:
                painter.drawPoint(self._path_points[0])
            else:
                painter.drawPolyline(self._path_points)
            painter.setBrush(QColor("#ffffff"))
            painter.setPen(QPen(QColor("#4a89ff"), 2))
            for point in self._path_points:
                painter.drawEllipse(point, 4, 4)

        # Stage 1 rotoscope — dashed Tiger Orange rectangle while
        # the user is dragging out a GrabCut bounding box.
        if (self._rect_hook is not None
                and self._rect_drag_start is not None
                and self._rect_drag_current is not None):
            painter.save()
            from PySide6.QtCore import QRectF
            x1 = self._rect_drag_start.x()
            y1 = self._rect_drag_start.y()
            x2 = self._rect_drag_current.x()
            y2 = self._rect_drag_current.y()
            rect = QRectF(min(x1, x2), min(y1, y2),
                          abs(x2 - x1), abs(y2 - y1))
            pen = QPen(QColor("#D85A30"), 2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(216, 90, 48, 40))
            painter.drawRect(rect)
            painter.restore()

        # Phase E — Power Window polygon overlay. The editor stashes
        # the active mask on this widget while in polygon-edit mode.
        pw = getattr(self, "_power_window_preview", None)
        if pw is not None and pw.points:
            painter.save()
            pts = [QPointF(x * w, y * h) for x, y in pw.points]
            # Tiger Orange polygon line + small handles per point.
            from PySide6.QtGui import QPolygonF
            outline_pen = QPen(QColor("#D85A30"), 2)
            outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            outline_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(outline_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if len(pts) >= 3:
                painter.drawPolygon(QPolygonF(pts))
            elif len(pts) == 2:
                painter.drawLine(pts[0], pts[1])
            for p in pts:
                painter.setBrush(QColor("#ffffff"))
                painter.setPen(QPen(QColor("#D85A30"), 2))
                painter.drawEllipse(p, 4, 4)
            painter.restore()

        self._paint_color_power_window(painter, w, h)
        if self._extra_paint_hook is not None:
            try:
                self._extra_paint_hook(painter, w, h)
            except Exception:
                pass

    @staticmethod
    def _paint_stroke(painter: QPainter, stroke: Stroke, w: int, h: int) -> None:
        color = QColor(*stroke.color)
        color.setAlpha(stroke.opacity)
        pen = QPen(color, stroke.width_px)
        DrawingCanvas._configure_pen_for_style(pen, getattr(stroke, "brush_style", "round"))
        painter.setPen(pen)
        pts = [QPointF(p[0] * w, p[1] * h) for p in stroke.points]
        if len(pts) == 1:
            painter.drawPoint(pts[0])
        elif getattr(stroke, "closed_path", False) and len(pts) >= 3:
            painter.drawPolyline(pts + [pts[0]])
        else:
            painter.drawPolyline(pts)

    @staticmethod
    def _configure_pen_for_style(pen: QPen, style: str) -> None:
        if style == "marker":
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        else:
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        if style == "highlighter":
            color = QColor(pen.color())
            color.setAlpha(min(color.alpha(), 110))
            pen.setColor(color)
            pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        elif style == "dashed":
            pen.setStyle(Qt.PenStyle.DashLine)

    # ------------- mouse interaction -------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        # Stage 1 rotoscope — rectangle drag for GrabCut takes
        # precedence over polygon / pen / eraser.
        if self._rect_hook is not None:
            self._rect_drag_start = QPointF(pos)
            self._rect_drag_current = QPointF(pos)
            self.update()
            return
        # Phase E — Power Window polygon editor takes precedence over
        # pen/eraser when the editor has installed a click hook.
        if self._click_hook is not None:
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                consumed = self._click_hook(pos.x() / w, pos.y() / h, "click")
            except Exception:
                consumed = False
            if consumed:
                self.update()
                return
        if self._interaction_hook is not None:
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                consumed = bool(self._interaction_hook("press", pos.x() / w, pos.y() / h, event))
            except Exception:
                consumed = False
            self._interaction_active = consumed
            if consumed:
                self.update()
                return
        if self._color_window_payload is not None:
            handle = self._color_window_hit_test(pos)
            if handle is not None:
                self._color_window_drag_handle = handle
                self._color_window_drag_start = QPointF(pos)
                self._color_window_drag_origin = dict(self._color_window_payload)
                self._set_color_window_cursor(handle)
                self.update()
            return
        if self._tool == "pen":
            self._current_points = [QPointF(pos)]
            self.update()
        elif self._tool == "eraser":
            self._try_erase_at(pos.x(), pos.y())
        elif self._tool == "path":
            self._path_points.append(QPointF(pos))
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._tool == "path":
            self.commit_path(closed=False)
            return
        if (event.button() == Qt.MouseButton.LeftButton
                and self._interaction_hook is not None):
            pos = event.position()
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                consumed = bool(self._interaction_hook("double", pos.x() / w, pos.y() / h, event))
            except Exception:
                consumed = False
            if consumed:
                self.update()
                return
        if (event.button() == Qt.MouseButton.LeftButton
                and self._click_hook is not None):
            pos = event.position()
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                self._click_hook(pos.x() / w, pos.y() / h, "double")
            except Exception:
                pass
            self.update()
            return
        super().mouseDoubleClickEvent(event)

    def set_click_hook(self, hook):
        """Install / remove the Power Window polygon click hook.
        ``hook`` is ``Callable[[float, float, str], bool]`` — first
        two args are normalised [0,1] coordinates, third is "click"
        or "double". Returns True if the click is consumed."""
        self._click_hook = hook
        self._refresh_mouse_transparency()
        self.update()

    def set_rect_hook(self, hook):
        """Install / remove the rotoscope rectangle hook.
        ``hook`` is ``Callable[[float, float, float, float], None]``
        — receives ``(nx, ny, nw, nh)`` in normalised [0,1] coords
        on mouse release. While the hook is active, drag-on-preview
        starts a rectangle instead of a pen stroke."""
        self._rect_hook = hook
        self._rect_drag_start = None
        self._rect_drag_current = None
        self._refresh_mouse_transparency()
        self.update()

    def set_color_power_window_editor(self, window, hook=None, active: bool = False) -> None:
        """Enable direct Color Page power-window editing on the preview."""
        if self._color_window_drag_handle is not None:
            return
        if not active or window is None:
            self._color_window_payload = None
            self._color_window_change_hook = None
        else:
            try:
                from app.color_workflow import normalize_tracking_window

                self._color_window_payload = normalize_tracking_window(window).to_dict()
                self._color_window_change_hook = hook
            except Exception:
                self._color_window_payload = dict(window) if isinstance(window, dict) else None
                self._color_window_change_hook = hook
        self._refresh_mouse_transparency()
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._color_window_drag_handle is not None:
            self._update_color_window_drag(event.position(), commit=False)
            return
        # Rectangle drag — keep updating the current corner while
        # the mouse is held.
        if self._rect_hook is not None and self._rect_drag_start is not None:
            self._rect_drag_current = QPointF(event.position())
            self.update()
            return
        if self._color_window_payload is not None:
            self._set_color_window_cursor(self._color_window_hit_test(event.position()))
            return
        if self._interaction_hook is not None:
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                consumed = bool(self._interaction_hook("move", event.position().x() / w, event.position().y() / h, event))
            except Exception:
                consumed = False
            if consumed or self._interaction_active:
                self.update()
                return
        if self._tool != "pen" or not self._current_points:
            return
        pos = event.position()
        # Only add a point if moved at least 2px from the previous one
        last = self._current_points[-1]
        if abs(pos.x() - last.x()) + abs(pos.y() - last.y()) >= 2:
            self._current_points.append(QPointF(pos))
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._color_window_drag_handle is not None:
            self._update_color_window_drag(event.position(), commit=True)
            self._color_window_drag_handle = None
            self._color_window_drag_start = None
            self._color_window_drag_origin = None
            self._set_color_window_cursor(self._color_window_hit_test(event.position()))
            self.update()
            return
        # Rectangle drag finished — emit normalised rect to the hook.
        if (self._rect_hook is not None
                and self._rect_drag_start is not None
                and self._rect_drag_current is not None):
            w = max(1, self.width())
            h = max(1, self.height())
            x1, y1 = self._rect_drag_start.x(), self._rect_drag_start.y()
            x2, y2 = self._rect_drag_current.x(), self._rect_drag_current.y()
            nx1, ny1 = min(x1, x2) / w, min(y1, y2) / h
            nx2, ny2 = max(x1, x2) / w, max(y1, y2) / h
            nw, nh = nx2 - nx1, ny2 - ny1
            try:
                if nw > 0.005 and nh > 0.005:
                    self._rect_hook(nx1, ny1, nw, nh)
            except Exception:
                pass
            self._rect_drag_start = None
            self._rect_drag_current = None
            self.update()
            return
        if self._interaction_hook is not None and self._interaction_active:
            w = max(1, self.width())
            h = max(1, self.height())
            try:
                self._interaction_hook("release", event.position().x() / w, event.position().y() / h, event)
            except Exception:
                pass
            self._interaction_active = False
            self.update()
            return
        if self._tool != "pen" or not self._current_points:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        norm_pts = [(p.x() / w, p.y() / h) for p in self._current_points]
        stroke = Stroke(
            points=norm_pts,
            color=(
                self._pen_color.red(),
                self._pen_color.green(),
                self._pen_color.blue(),
            ),
            opacity=self._pen_opacity,
            width_px=self._pen_width,
            brush_style=self._pen_style,
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        self._current_points = []
        self.stroke_added.emit(stroke)
        self.update()

    def commit_path(self, *, closed: bool = False) -> None:
        if len(self._path_points) < 2:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        stroke = Stroke(
            points=[(p.x() / w, p.y() / h) for p in self._path_points],
            color=(
                self._pen_color.red(),
                self._pen_color.green(),
                self._pen_color.blue(),
            ),
            opacity=self._pen_opacity,
            width_px=self._pen_width,
            brush_style=self._pen_style,
            closed_path=bool(closed),
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        self._path_points = []
        self.stroke_added.emit(stroke)
        self.update()

    def clear_path_preview(self) -> None:
        self._path_points = []
        self.update()

    def set_strokes_snapshot(self, strokes: list[Stroke]) -> None:
        """Replace the backing strokes list (for standalone paint dialog use)."""
        self._embedded_strokes = list(strokes)
        self._get_strokes = lambda: self._embedded_strokes
        self.update()

    def add_stroke_direct(self, stroke: Stroke) -> None:
        """Append a stroke to the embedded list (dialog context)."""
        if hasattr(self, "_embedded_strokes"):
            self._embedded_strokes.append(stroke)
            self.update()

    def remove_stroke_direct(self, index: int) -> None:
        if hasattr(self, "_embedded_strokes") and 0 <= index < len(self._embedded_strokes):
            self._embedded_strokes.pop(index)
            self.update()

    def clear_strokes_direct(self) -> None:
        if hasattr(self, "_embedded_strokes"):
            self._embedded_strokes.clear()
            self.update()

    def embedded_strokes(self) -> list[Stroke]:
        if hasattr(self, "_embedded_strokes"):
            return list(self._embedded_strokes)
        return []

    def _try_erase_at(self, px: float, py: float) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        t_ms = int(self._get_time_ms())
        radius_sq = self.ERASE_RADIUS_PX * self.ERASE_RADIUS_PX
        strokes = self._get_strokes()
        # Iterate in reverse so top-most-drawn stroke is erased first
        for idx in range(len(strokes) - 1, -1, -1):
            stroke = strokes[idx]
            if not stroke.is_active(t_ms):
                continue
            for nx, ny in stroke.points:
                dx = nx * w - px
                dy = ny * h - py
                if dx * dx + dy * dy <= radius_sq:
                    self.stroke_erased_at.emit(idx)
                    self.update()
                    return

    def _refresh_mouse_transparency(self) -> None:
        wants_mouse = (
            self._tool != "off"
            or self._click_hook is not None
            or self._rect_hook is not None
            or self._color_window_payload is not None
            or self._interaction_hook is not None
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not wants_mouse,
        )

    def _paint_color_power_window(self, painter: QPainter, w: int, h: int) -> None:
        payload = self._color_window_payload
        if not payload:
            return
        try:
            from app.color_workflow import normalize_tracking_window

            win = normalize_tracking_window(payload)
        except Exception:
            return
        rect = QRectF(
            (win.x - win.w * 0.5) * w,
            (win.y - win.h * 0.5) * h,
            win.w * w,
            win.h * h,
        )
        if rect.width() <= 1 or rect.height() <= 1:
            return
        painter.save()
        painter.setBrush(QColor(216, 90, 48, 34))
        pen = QPen(QColor("#E96B3C"), 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        if win.shape.startswith("rect"):
            painter.drawRect(rect)
        else:
            painter.drawEllipse(rect)
        if win.feather > 0.001:
            feather_px = max(3.0, min(w, h) * win.feather * 0.16)
            feather_rect = rect.adjusted(-feather_px, -feather_px, feather_px, feather_px)
            fpen = QPen(QColor(233, 107, 60, 135), 1)
            fpen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(fpen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            if win.shape.startswith("rect"):
                painter.drawRect(feather_rect)
            else:
                painter.drawEllipse(feather_rect)
        painter.setPen(QPen(QColor("#0C0D10"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        for _name, point in self._color_window_handle_points(rect).items():
            painter.drawRect(QRectF(point.x() - 4, point.y() - 4, 8, 8))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        cx, cy = rect.center().x(), rect.center().y()
        painter.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
        painter.drawLine(QPointF(cx, cy - 6), QPointF(cx, cy + 6))
        painter.restore()

    @staticmethod
    def _color_window_handle_points(rect: QRectF) -> dict[str, QPointF]:
        cx = rect.center().x()
        cy = rect.center().y()
        return {
            "top_left": rect.topLeft(),
            "top": QPointF(cx, rect.top()),
            "top_right": rect.topRight(),
            "right": QPointF(rect.right(), cy),
            "bottom_right": rect.bottomRight(),
            "bottom": QPointF(cx, rect.bottom()),
            "bottom_left": rect.bottomLeft(),
            "left": QPointF(rect.left(), cy),
        }

    def _color_window_rect(self) -> QRectF | None:
        payload = self._color_window_payload
        if not payload:
            return None
        try:
            from app.color_workflow import normalize_tracking_window

            win = normalize_tracking_window(payload)
        except Exception:
            return None
        w = max(1, self.width())
        h = max(1, self.height())
        return QRectF(
            (win.x - win.w * 0.5) * w,
            (win.y - win.h * 0.5) * h,
            win.w * w,
            win.h * h,
        )

    def _color_window_hit_test(self, pos: QPointF) -> str | None:
        rect = self._color_window_rect()
        if rect is None:
            return None
        threshold = 12.0
        best_name = None
        best_dist = threshold * threshold
        for name, point in self._color_window_handle_points(rect).items():
            dx = point.x() - pos.x()
            dy = point.y() - pos.y()
            dist = dx * dx + dy * dy
            if dist <= best_dist:
                best_name = name
                best_dist = dist
        if best_name is not None:
            return best_name
        payload = self._color_window_payload or {}
        shape = str(payload.get("shape", "ellipse")).lower()
        if shape.startswith("rect"):
            return "move" if rect.contains(pos) else None
        rx = max(1.0, rect.width() * 0.5)
        ry = max(1.0, rect.height() * 0.5)
        cx = rect.center().x()
        cy = rect.center().y()
        inside = ((pos.x() - cx) / rx) ** 2 + ((pos.y() - cy) / ry) ** 2 <= 1.0
        return "move" if inside else None

    def _set_color_window_cursor(self, handle: str | None) -> None:
        if handle is None:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif handle == "move":
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif handle in {"left", "right"}:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif handle in {"top", "bottom"}:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        elif handle in {"top_left", "bottom_right"}:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)

    def _update_color_window_drag(self, pos: QPointF, *, commit: bool) -> None:
        if (
            self._color_window_drag_handle is None
            or self._color_window_drag_start is None
            or self._color_window_drag_origin is None
        ):
            return
        w = max(1, self.width())
        h = max(1, self.height())
        dx = (pos.x() - self._color_window_drag_start.x()) / w
        dy = (pos.y() - self._color_window_drag_start.y()) / h
        try:
            from app.color_workflow import edit_tracking_window

            win = edit_tracking_window(
                self._color_window_drag_origin,
                self._color_window_drag_handle,
                dx,
                dy,
            )
            self._color_window_payload = win.to_dict()
        except Exception:
            return
        hook = self._color_window_change_hook
        if hook is not None:
            try:
                hook(dict(self._color_window_payload), bool(commit))
            except Exception:
                pass
        self.update()


def compose_pil_frame_with_overlays(
    frame,
    strokes: list["Stroke"],
    subtitles: list,
    time_ms: int,
    width_scale: float = 1.0,
):
    """Return a new PIL image with any active strokes + subtitle burned in."""
    from PIL import Image, ImageDraw, ImageFont

    w, h = frame.size
    out = frame.convert("RGBA") if frame.mode != "RGBA" else frame.copy()

    active_strokes = [s for s in (strokes or []) if s.is_active(int(time_ms))]
    if active_strokes:
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for s in active_strokes:
            r, g, b = s.color
            color = (r, g, b, int(s.opacity))
            stroke_w = max(1, int(round(s.width_px * width_scale)))
            pts = [(int(p[0] * w), int(p[1] * h)) for p in s.points]
            _draw_pil_stroke(
                draw,
                pts,
                color,
                stroke_w,
                getattr(s, "brush_style", "round"),
                bool(getattr(s, "closed_path", False)),
            )
        out = Image.alpha_composite(out, overlay)

    active_sub = None
    for sub in (subtitles or []):
        if sub.contains(int(time_ms)) and sub.text.strip():
            active_sub = sub
            break
    if active_sub is not None:
        draw = ImageDraw.Draw(out)
        font_size = max(14, int(h * 0.05))
        font = None
        for name in ("malgun.ttf", "arial.ttf", "segoeui.ttf"):
            try:
                font = ImageFont.truetype(name, font_size)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        text = active_sub.text
        bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (w - tw) // 2
        y = h - th - max(12, int(h * 0.04))
        pad_x, pad_y = max(8, int(h * 0.015)), max(4, int(h * 0.008))
        if active_sub.show_box:
            draw.rectangle(
                [x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y],
                fill=(0, 0, 0, 180),
            )
            draw.multiline_text(
                (x, y), text, font=font, fill=(255, 255, 255, 255),
                align="center",
            )
        else:
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    if dx == 0 and dy == 0:
                        continue
                    draw.multiline_text(
                        (x + dx, y + dy), text, font=font,
                        fill=(0, 0, 0, 230), align="center",
                    )
            draw.multiline_text(
                (x, y), text, font=font, fill=(255, 255, 255, 255),
                align="center",
            )

    if frame.mode != "RGBA":
        return out.convert(frame.mode)
    return out


def _draw_pil_stroke(
    draw,
    pts: list[tuple[int, int]],
    color: tuple[int, int, int, int],
    stroke_w: int,
    style: str,
    closed: bool,
) -> None:
    if not pts:
        return
    if len(pts) == 1:
        x, y = pts[0]
        half = max(1, stroke_w // 2)
        draw.ellipse([x - half, y - half, x + half, y + half], fill=color)
        return
    draw_pts = list(pts)
    if closed and len(draw_pts) >= 3:
        draw_pts.append(draw_pts[0])
    if style == "dashed":
        _draw_pil_dashed_polyline(draw, draw_pts, color, stroke_w)
    elif style == "highlighter":
        hl = (color[0], color[1], color[2], min(color[3], 110))
        draw.line(draw_pts, fill=hl, width=max(2, stroke_w), joint="curve")
    else:
        draw.line(draw_pts, fill=color, width=stroke_w, joint="curve")


def _draw_pil_dashed_polyline(
    draw,
    pts: list[tuple[int, int]],
    color: tuple[int, int, int, int],
    width: int,
) -> None:
    dash_len = max(8.0, width * 2.4)
    gap_len = max(5.0, width * 1.4)
    cycle = dash_len + gap_len
    distance_cursor = 0.0
    for a, b in zip(pts, pts[1:]):
        ax, ay = a
        bx, by = b
        seg_len = math.hypot(bx - ax, by - ay)
        if seg_len <= 0.01:
            continue
        travelled = 0.0
        while travelled < seg_len:
            cycle_pos = distance_cursor % cycle
            if cycle_pos < dash_len:
                step = min(seg_len - travelled, dash_len - cycle_pos)
                t0 = travelled / seg_len
                t1 = (travelled + step) / seg_len
                p0 = (ax + (bx - ax) * t0, ay + (by - ay) * t0)
                p1 = (ax + (bx - ax) * t1, ay + (by - ay) * t1)
                draw.line([p0, p1], fill=color, width=width)
            else:
                step = min(seg_len - travelled, cycle - cycle_pos)
            travelled += max(0.01, step)
            distance_cursor += max(0.01, step)


def render_strokes_to_png(
    strokes: list["Stroke"],
    width: int,
    height: int,
    out_path: str,
    width_scale: float = 1.0,
) -> bool:
    """Render a list of strokes to a transparent PNG at the given size.

    Strokes use normalized [0,1] coords in the PaintDialog's video-aligned
    canvas, so multiplying by (width, height) gives exact video-pixel
    positions. ``width_scale`` boosts stroke line width so thin lines drawn
    on the ~700 px dialog canvas stay visible when rendered at 1080 / 4K.
    Returns True if the PNG was written successfully.
    """
    if width <= 0 or height <= 0:
        return False
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(0)  # fully transparent
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        for stroke in strokes:
            color = QColor(*stroke.color)
            color.setAlpha(stroke.opacity)
            pen = QPen(color, max(1.0, stroke.width_px * width_scale))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            pts = [QPointF(p[0] * width, p[1] * height) for p in stroke.points]
            if len(pts) == 1:
                painter.drawPoint(pts[0])
            elif len(pts) > 1:
                painter.drawPolyline(pts)
    finally:
        painter.end()
    return bool(img.save(out_path, "PNG"))


def compose_pil_paint_overlays(
    *,
    strokes: list["Stroke"] | None = None,
    bubbles: list["SpeechBubble"] | None = None,
    stickers: list["Sticker"] | None = None,
    time_ms: int = 0,
    frame_size: tuple[int, int] = (1920, 1080),
    stroke_width_scale: float = 1.0,
):
    """Render paint overlays onto a transparent PIL RGBA image."""
    from PIL import Image

    width = max(1, int(frame_size[0]))
    height = max(1, int(frame_size[1]))
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out = compose_pil_frame_with_overlays(
        out,
        list(strokes or []),
        [],
        int(time_ms),
        width_scale=max(0.001, float(stroke_width_scale or 1.0)),
    )
    out = compose_pil_stickers(out, list(stickers or []), int(time_ms))
    out = compose_pil_bubbles(out, list(bubbles or []), int(time_ms))
    return out


def export_paint_png(
    out_path: str | Path,
    *,
    background_pixmap: QPixmap | None = None,
    strokes: list["Stroke"] | None = None,
    bubbles: list["SpeechBubble"] | None = None,
    stickers: list["Sticker"] | None = None,
    time_ms: int = 0,
    frame_size: tuple[int, int] | None = None,
    include_background: bool = True,
    stroke_width_scale: float = 1.0,
) -> dict:
    """Write a Paint-window PNG export and return a small report.

    ``include_background=False`` writes a transparent overlay PNG. When
    ``include_background=True`` and a background pixmap exists, the output is
    the frozen frame plus all active Paint overlays.
    """
    from PIL import Image

    path = Path(out_path)
    if path.suffix.lower() != ".png":
        path = path.with_suffix(".png")
    path.parent.mkdir(parents=True, exist_ok=True)
    size = frame_size or _paint_export_size(background_pixmap)
    width = max(1, int(size[0]))
    height = max(1, int(size[1]))
    if include_background and background_pixmap is not None and not background_pixmap.isNull():
        base = _pixmap_to_pil_rgba(background_pixmap)
        if base.size != (width, height):
            base = base.resize((width, height), Image.LANCZOS)
    else:
        base = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay = compose_pil_paint_overlays(
        strokes=strokes,
        bubbles=bubbles,
        stickers=stickers,
        time_ms=int(time_ms),
        frame_size=(width, height),
        stroke_width_scale=stroke_width_scale,
    )
    out = Image.alpha_composite(base.convert("RGBA"), overlay)
    out.save(path, "PNG")
    return {
        "schema": "tigerstudio.paint.png_export.v1",
        "path": str(path.resolve()),
        "mode": "composited" if include_background else "overlay",
        "width": width,
        "height": height,
        "stroke_count": len(list(strokes or [])),
        "bubble_count": len(list(bubbles or [])),
        "sticker_count": len(list(stickers or [])),
    }


def _paint_export_size(
    background_pixmap: QPixmap | None,
    *,
    fallback: tuple[int, int] = (1920, 1080),
) -> tuple[int, int]:
    if background_pixmap is not None and not background_pixmap.isNull():
        width = int(background_pixmap.width())
        height = int(background_pixmap.height())
        if width > 0 and height > 0:
            return (width, height)
    return (max(1, int(fallback[0])), max(1, int(fallback[1])))


def _pixmap_to_pil_rgba(pixmap: QPixmap):
    from io import BytesIO

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray

    qimg = pixmap.toImage()
    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    qimg.save(buffer, "PNG")
    buffer.close()
    with BytesIO(bytes(byte_array)) as bio:
        image = Image.open(bio)
        image.load()
    return image.convert("RGBA")


# ---------------------------------------------------------------------------
#  Paint-style dialog
# ---------------------------------------------------------------------------


# Modern creator palette: muted editorial swatches for screen annotation.
PALETTE_COLORS: list[tuple[int, int, int]] = [
    (238, 242, 247),
    (173, 181, 194),
    (87, 98, 114),
    (16, 20, 27),
    (83, 116, 255),
    (63, 156, 214),
    (42, 169, 145),
    (105, 177, 112),
    (227, 183, 74),
    (218, 130, 79),
    (210, 79, 79),
    (183, 82, 121),
    (136, 103, 224),
    (106, 88, 169),
    (229, 220, 198),
    (181, 139, 94),
]

RECENT_COLOR_LIMIT = 5


class PaintDialog(QDialog):
    """Full-window paint-mode dialog: frozen video frame as background,
    toolbar with pen/eraser/palette/sliders at the top, large canvas center.

    The caller passes:
        background_pixmap - the current video frame to draw over
        initial_strokes - existing strokes to show (at time_ms)
        time_ms - stamped into newly drawn strokes
    On accept, ``result_strokes()`` returns the full (possibly modified)
    list of strokes that should replace the caller's stroke state.
    """

    def __init__(
        self,
        background_pixmap: QPixmap,
        initial_strokes: list[Stroke],
        time_ms: int,
        parent: QWidget | None = None,
        initial_bubbles: list["SpeechBubble"] | None = None,
        initial_stickers: list["Sticker"] | None = None,
        editor_object_provider: Callable[[], list] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("paint.title"))
        self.setModal(True)
        self._time_ms = int(time_ms)
        self._editor_object_provider = editor_object_provider
        self._bubbles: list[SpeechBubble] = list(initial_bubbles or [])
        self._bubble_items: list[SpeechBubbleItem] = []
        self._stickers: list["Sticker"] = list(initial_stickers or [])
        self._sticker_items: list["StickerItem"] = []
        self._undo_stack: list[tuple[list[Stroke], list[SpeechBubble], list["Sticker"]]] = []
        self._redo_stack: list[tuple[list[Stroke], list[SpeechBubble], list["Sticker"]]] = []
        self._restoring_state = False
        self._canvas_zoom = 1.0
        self._selected_layer_id: str | None = None
        self._paint_clipboard: dict | None = None

        # Make the dialog large (paint-app feel). Cap at screen size.
        if parent is not None:
            parent_win = parent.window()
            if parent_win is not None:
                self.resize(
                    int(parent_win.width() * 0.92),
                    int(parent_win.height() * 0.9),
                )
        if self.width() < 900:
            self.resize(1100, 780)

        self._pen_color = QColor(*PALETTE_COLORS[0])
        self._pen_width = 6.0
        self._pen_opacity = 255
        self._palette_syncing = False
        self._recent_colors: list[tuple[int, int, int]] = [
            PALETTE_COLORS[0],
            PALETTE_COLORS[4],
            PALETTE_COLORS[6],
            PALETTE_COLORS[14],
            PALETTE_COLORS[15],
        ]

        self._build_ui(background_pixmap, initial_strokes)

    # ---------- ui ----------

    def _build_ui_legacy(self, bg: QPixmap, initial_strokes: list[Stroke]) -> None:
        self.setStyleSheet(self.styleSheet() + _PAINT_DIALOG_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

        # --- Top toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        self.pen_btn = QPushButton(tr("paint.btn.pen"))
        self.pen_btn.setCheckable(True)
        self.pen_btn.setChecked(True)
        self.pen_btn.setObjectName("PaintTool")
        self.pen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pen_btn.clicked.connect(lambda: self._set_tool("pen"))

        self.eraser_btn = QPushButton(tr("paint.btn.eraser"))
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.setObjectName("PaintTool")
        self.eraser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eraser_btn.clicked.connect(lambda: self._set_tool("eraser"))

        self.clear_btn = QPushButton(tr("paint.btn.clear_all"))
        self.clear_btn.setObjectName("PaintTool")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_all)

        # Add-bubble button (lives with the paint tools, distinct accent)
        self.bubble_btn = QPushButton(tr("bubble.add_button"))
        self.bubble_btn.setObjectName("BubbleBtn")
        self.bubble_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bubble_btn.clicked.connect(self._add_bubble)

        # Add-sticker button — PNG stickers / watermarks.
        self.sticker_btn = QPushButton(tr("sticker.add_button"))
        self.sticker_btn.setObjectName("StickerBtn")
        self.sticker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sticker_btn.setToolTip(tr("sticker.add_tooltip"))
        self.sticker_btn.clicked.connect(self._add_sticker)

        toolbar.addWidget(self.pen_btn)
        toolbar.addWidget(self.eraser_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.bubble_btn)
        toolbar.addWidget(self.sticker_btn)
        toolbar.addSpacing(18)

        # Width + opacity sliders
        toolbar.addWidget(QLabel(tr("paint.label.width")))
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 60)
        self.width_slider.setValue(int(self._pen_width))
        self.width_slider.setFixedWidth(120)
        self.width_slider.valueChanged.connect(self._on_width_changed)
        toolbar.addWidget(self.width_slider)

        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel(tr("paint.label.opacity")))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(120)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        toolbar.addWidget(self.opacity_slider)

        toolbar.addStretch(1)
        root.addLayout(toolbar)

        # --- Palette row ---
        palette_row = QHBoxLayout()
        palette_row.setSpacing(4)
        palette_row.addWidget(QLabel(tr("paint.label.color")))
        self._palette_btns: list[QPushButton] = []
        for rgb in PALETTE_COLORS:
            btn = self._make_palette_button(rgb)
            palette_row.addWidget(btn)
            self._palette_btns.append(btn)
        self._highlight_selected_palette()

        self.custom_color_btn = QPushButton(tr("paint.btn.custom_color"))
        self.custom_color_btn.setObjectName("PaintTool")
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        palette_row.addWidget(self.custom_color_btn)
        palette_row.addStretch(1)
        root.addLayout(palette_row)

        # --- Canvas host (background frame + transparent drawing canvas) ---
        canvas_host = QWidget()
        canvas_host.setStyleSheet("background-color: #1a1a1a;")
        canvas_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas_host = canvas_host

        self._bg_label = QLabel(canvas_host)
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.setStyleSheet("background-color: #1a1a1a;")
        self._bg_pixmap_source = bg
        self._bg_label.setPixmap(
            bg.scaled(
                1, 1, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ) if bg and not bg.isNull() else QPixmap()
        )

        self.canvas = DrawingCanvas(
            get_time_ms=lambda: self._time_ms,
            get_strokes=lambda: [],
            parent=canvas_host,
        )
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self.canvas.set_tool("pen")
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_width(self._pen_width)
        self.canvas.set_pen_opacity(self._pen_opacity)
        self.canvas.stroke_added.connect(self._on_stroke_added)
        self.canvas.stroke_erased_at.connect(
            lambda idx: self.canvas.remove_stroke_direct(idx)
        )

        root.addWidget(canvas_host, stretch=1)

        # --- Note + buttons ---
        note = QLabel(tr("paint.note"))
        note.setStyleSheet("color: #8a8a8a; font-size: 11px;")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("paint.btn.done")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("paint.btn.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Spawn any bubbles the caller passed in (deferred until canvas has
        # a real size — triggered via the first showEvent).

    def _build_ui(self, bg: QPixmap, initial_strokes: list[Stroke]) -> None:
        self.setStyleSheet(self.styleSheet() + _PAINT_DIALOG_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("PaintTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title = QLabel("TigerCapture Paint")
        title.setObjectName("PaintTitle")
        subtitle = QLabel(
            "Draw, cut out, place PNG stickers, and import editor objects."
        )
        subtitle.setObjectName("PaintSubtitle")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        top_layout.addLayout(title_col, stretch=1)

        self.undo_btn = QPushButton("Undo")
        self.undo_btn.setObjectName("PaintTool")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.clicked.connect(self._undo)
        top_layout.addWidget(self.undo_btn)

        self.redo_btn = QPushButton("Redo")
        self.redo_btn.setObjectName("PaintTool")
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.clicked.connect(self._redo)
        top_layout.addWidget(self.redo_btn)

        self.export_png_btn = QPushButton("Export PNG")
        self.export_png_btn.setObjectName("PaintTool")
        self.export_png_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_png_btn.clicked.connect(self._show_export_png_menu)
        top_layout.addWidget(self.export_png_btn)

        zoom_label = QLabel("Zoom")
        zoom_label.setObjectName("PaintMeta")
        top_layout.addWidget(zoom_label)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(120)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        top_layout.addWidget(self.zoom_slider)
        self._zoom_value_label = QLabel("100%")
        self._zoom_value_label.setObjectName("PaintValue")
        top_layout.addWidget(self._zoom_value_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            tr("paint.btn.done")
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("paint.btn.cancel")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        top_layout.addWidget(buttons)
        root.addWidget(top_bar)

        workspace = QHBoxLayout()
        workspace.setSpacing(10)
        root.addLayout(workspace, stretch=1)

        tool_rail = QFrame()
        tool_rail.setObjectName("PaintToolRail")
        tool_layout = QVBoxLayout(tool_rail)
        tool_layout.setContentsMargins(10, 12, 10, 12)
        tool_layout.setSpacing(8)
        tool_title = QLabel("TOOLS")
        tool_title.setObjectName("PaintSectionTitle")
        tool_layout.addWidget(tool_title)

        self.select_btn = QPushButton("↖ Select / Move")
        self.select_btn.setCheckable(True)
        self.select_btn.setObjectName("PaintTool")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(lambda: self._set_tool("select"))

        self.pen_btn = QPushButton(tr("paint.btn.pen"))
        self.pen_btn.setCheckable(True)
        self.pen_btn.setChecked(True)
        self.pen_btn.setObjectName("PaintTool")
        self.pen_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pen_btn.clicked.connect(lambda: self._set_tool("pen"))

        self.eraser_btn = QPushButton(tr("paint.btn.eraser"))
        self.eraser_btn.setCheckable(True)
        self.eraser_btn.setObjectName("PaintTool")
        self.eraser_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eraser_btn.clicked.connect(lambda: self._set_tool("eraser"))

        self.path_btn = QPushButton("✦ Path")
        self.path_btn.setCheckable(True)
        self.path_btn.setObjectName("PaintTool")
        self.path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_btn.clicked.connect(lambda: self._set_tool("path"))

        self.bubble_btn = QPushButton(tr("bubble.add_button"))
        self.bubble_btn.setObjectName("BubbleBtn")
        self.bubble_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bubble_btn.clicked.connect(self._add_bubble)

        self.sticker_btn = QPushButton(tr("sticker.add_button"))
        self.sticker_btn.setObjectName("StickerBtn")
        self.sticker_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sticker_btn.setToolTip(tr("sticker.add_tooltip"))
        self.sticker_btn.clicked.connect(self._add_sticker)

        self.editor_object_btn = QPushButton("Editor Object")
        self.editor_object_btn.setObjectName("StickerBtn")
        self.editor_object_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.editor_object_btn.setToolTip("Import typography, AR/PBR, and actor objects from the editor.")
        self.editor_object_btn.setEnabled(callable(self._editor_object_provider))
        self.editor_object_btn.clicked.connect(self._import_editor_object)

        self.clear_btn = QPushButton(tr("paint.btn.clear_all"))
        self.clear_btn.setObjectName("PaintDanger")
        self.clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_btn.clicked.connect(self._clear_all)

        self.cutout_btn = QPushButton("✂ Cutout")
        self.cutout_btn.setObjectName("PaintTool")
        self.cutout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cutout_btn.clicked.connect(self._create_cutout_sticker)

        tool_layout.addWidget(self.select_btn)
        tool_layout.addWidget(self.pen_btn)
        tool_layout.addWidget(self.eraser_btn)
        tool_layout.addWidget(self.path_btn)
        tool_layout.addSpacing(8)
        tool_layout.addWidget(self.bubble_btn)
        tool_layout.addWidget(self.sticker_btn)
        tool_layout.addWidget(self.editor_object_btn)
        tool_layout.addWidget(self.cutout_btn)
        tool_layout.addSpacing(8)
        tool_layout.addWidget(self.clear_btn)
        tool_layout.addStretch(1)
        workspace.addWidget(tool_rail)

        canvas_frame = QFrame()
        canvas_frame.setObjectName("PaintCanvasFrame")
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(10, 10, 10, 10)
        canvas_layout.setSpacing(8)

        canvas_bar = QHBoxLayout()
        canvas_bar.setContentsMargins(0, 0, 0, 0)
        canvas_title = QLabel("CANVAS")
        canvas_title.setObjectName("PaintSectionTitle")
        self._tool_status_label = QLabel("Pen")
        self._tool_status_label.setObjectName("PaintMeta")
        canvas_bar.addWidget(canvas_title)
        canvas_bar.addStretch(1)
        canvas_bar.addWidget(self._tool_status_label)
        canvas_layout.addLayout(canvas_bar)

        canvas_host = QWidget()
        canvas_host.setStyleSheet("background-color: #050607; border-radius: 8px;")
        canvas_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas_host = canvas_host

        self._bg_label = QLabel(canvas_host)
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.setStyleSheet("background-color: #050607;")
        self._bg_pixmap_source = bg
        self._bg_label.setPixmap(
            bg.scaled(
                1, 1, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ) if bg and not bg.isNull() else QPixmap()
        )

        self.canvas = DrawingCanvas(
            get_time_ms=lambda: self._time_ms,
            get_strokes=lambda: [],
            parent=canvas_host,
        )
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self.canvas.set_tool("pen")
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_width(self._pen_width)
        self.canvas.set_pen_opacity(self._pen_opacity)
        self.canvas.stroke_added.connect(self._on_stroke_added)
        self.canvas.stroke_erased_at.connect(self._erase_stroke_direct)

        canvas_layout.addWidget(canvas_host, stretch=1)
        workspace.addWidget(canvas_frame, stretch=1)

        inspector = QFrame()
        inspector.setObjectName("PaintInspector")
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(10)

        brush_title = QLabel("BRUSH")
        brush_title.setObjectName("PaintSectionTitle")
        inspector_layout.addWidget(brush_title)

        style_row = QHBoxLayout()
        style_row.setContentsMargins(0, 0, 0, 0)
        style_label = QLabel("Style")
        style_label.setObjectName("PaintMeta")
        self.brush_style_combo = QComboBox()
        self.brush_style_combo.addItem("Round pen", "round")
        self.brush_style_combo.addItem("Marker", "marker")
        self.brush_style_combo.addItem("Highlighter", "highlighter")
        self.brush_style_combo.addItem("Dashed", "dashed")
        self.brush_style_combo.currentIndexChanged.connect(self._on_brush_style_changed)
        style_row.addWidget(style_label)
        style_row.addStretch(1)
        style_row.addWidget(self.brush_style_combo)
        inspector_layout.addLayout(style_row)

        width_row = QHBoxLayout()
        width_row.setContentsMargins(0, 0, 0, 0)
        width_label = QLabel(tr("paint.label.width"))
        width_label.setObjectName("PaintMeta")
        self._width_value_label = QLabel(f"{int(self._pen_width)} px")
        self._width_value_label.setObjectName("PaintValue")
        width_row.addWidget(width_label)
        width_row.addStretch(1)
        width_row.addWidget(self._width_value_label)
        inspector_layout.addLayout(width_row)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 60)
        self.width_slider.setValue(int(self._pen_width))
        self.width_slider.valueChanged.connect(self._on_width_changed)
        inspector_layout.addWidget(self.width_slider)

        opacity_row = QHBoxLayout()
        opacity_row.setContentsMargins(0, 0, 0, 0)
        opacity_label = QLabel(tr("paint.label.opacity"))
        opacity_label.setObjectName("PaintMeta")
        self._opacity_value_label = QLabel("100%")
        self._opacity_value_label.setObjectName("PaintValue")
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch(1)
        opacity_row.addWidget(self._opacity_value_label)
        inspector_layout.addLayout(opacity_row)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        inspector_layout.addWidget(self.opacity_slider)

        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        for label_text, width, opacity in (
            ("Fine", 3, 100),
            ("Marker", 8, 100),
            ("Highlighter", 24, 42),
        ):
            preset_btn = QPushButton(label_text)
            preset_btn.setObjectName("PaintCustomColor")
            preset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            preset_btn.clicked.connect(
                lambda _checked=False, w=width, o=opacity: self._apply_brush_preset(w, o)
            )
            preset_row.addWidget(preset_btn)
        inspector_layout.addLayout(preset_row)

        path_title = QLabel("PATH")
        path_title.setObjectName("PaintSectionTitle")
        inspector_layout.addWidget(path_title)
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        self.commit_path_btn = QPushButton("Commit")
        self.commit_path_btn.setObjectName("PaintCustomColor")
        self.commit_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.commit_path_btn.clicked.connect(lambda: self._commit_path(False))
        self.close_path_btn = QPushButton("Close")
        self.close_path_btn.setObjectName("PaintCustomColor")
        self.close_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_path_btn.clicked.connect(lambda: self._commit_path(True))
        self.clear_path_btn = QPushButton("Clear")
        self.clear_path_btn.setObjectName("PaintCustomColor")
        self.clear_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_path_btn.clicked.connect(self._clear_path_preview)
        path_row.addWidget(self.commit_path_btn)
        path_row.addWidget(self.close_path_btn)
        path_row.addWidget(self.clear_path_btn)
        inspector_layout.addLayout(path_row)

        color_title = QLabel("COLOR")
        color_title.setObjectName("PaintSectionTitle")
        inspector_layout.addWidget(color_title)
        color_panel = QFrame()
        color_panel.setObjectName("PaintColorPanel")
        color_panel_layout = QVBoxLayout(color_panel)
        color_panel_layout.setContentsMargins(9, 9, 9, 9)
        color_panel_layout.setSpacing(8)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_label = QLabel("Current")
        color_label.setObjectName("PaintMeta")
        self._color_preview = QLabel()
        self._color_preview.setObjectName("PaintColorWell")
        self._color_preview.setFixedSize(64, 24)
        self._color_hex_label = QLabel("#E54646")
        self._color_hex_label.setObjectName("PaintColorHex")
        color_row.addWidget(color_label)
        color_row.addStretch(1)
        color_row.addWidget(self._color_hex_label)
        color_row.addWidget(self._color_preview)
        color_panel_layout.addLayout(color_row)

        mixer_label = QLabel("MIXER")
        mixer_label.setObjectName("PaintMeta")
        color_panel_layout.addWidget(mixer_label)
        hue_row = QHBoxLayout()
        hue_row.setContentsMargins(0, 0, 0, 0)
        hue_label = QLabel("Hue")
        hue_label.setObjectName("PaintMeta")
        self.hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.hue_slider.setObjectName("PaintHueSlider")
        self.hue_slider.setRange(0, 359)
        self.hue_slider.valueChanged.connect(self._on_hue_changed)
        hue_row.addWidget(hue_label)
        hue_row.addWidget(self.hue_slider, stretch=1)
        color_panel_layout.addLayout(hue_row)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_label = QLabel("Value")
        value_label.setObjectName("PaintMeta")
        self.value_slider = QSlider(Qt.Orientation.Horizontal)
        self.value_slider.setObjectName("PaintValueSlider")
        self.value_slider.setRange(12, 100)
        self.value_slider.valueChanged.connect(self._on_value_changed)
        value_row.addWidget(value_label)
        value_row.addWidget(self.value_slider, stretch=1)
        color_panel_layout.addLayout(value_row)

        recent_label = QLabel("RECENT")
        recent_label.setObjectName("PaintMeta")
        color_panel_layout.addWidget(recent_label)
        recent_row = QHBoxLayout()
        recent_row.setContentsMargins(0, 0, 0, 0)
        recent_row.setSpacing(6)
        self._recent_color_btns: list[QPushButton] = []
        for rgb in self._recent_colors:
            btn = self._make_palette_button(rgb, width=40, height=18)
            recent_row.addWidget(btn)
            self._recent_color_btns.append(btn)
        recent_row.addStretch(1)
        color_panel_layout.addLayout(recent_row)

        suggested_label = QLabel("PALETTE")
        suggested_label.setObjectName("PaintMeta")
        color_panel_layout.addWidget(suggested_label)
        palette_grid = QGridLayout()
        palette_grid.setHorizontalSpacing(6)
        palette_grid.setVerticalSpacing(6)
        self._palette_btns: list[QPushButton] = []
        for idx, rgb in enumerate(PALETTE_COLORS):
            btn = self._make_palette_button(rgb, width=54, height=20)
            palette_grid.addWidget(btn, idx // 4, idx % 4)
            self._palette_btns.append(btn)
        color_panel_layout.addLayout(palette_grid)

        self.custom_color_btn = QPushButton("Advanced picker")
        self.custom_color_btn.setObjectName("PaintCustomColor")
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        color_panel_layout.addWidget(self.custom_color_btn)
        inspector_layout.addWidget(color_panel)

        layer_title = QLabel("LAYERS")
        layer_title.setObjectName("PaintSectionTitle")
        inspector_layout.addWidget(layer_title)
        self._layer_list = QListWidget()
        self._layer_list.setObjectName("PaintLayerList")
        self._layer_list.setFixedHeight(142)
        self._layer_list.itemClicked.connect(self._select_layer_item)
        self._layer_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._layer_list.customContextMenuRequested.connect(self._open_layer_context_menu)
        inspector_layout.addWidget(self._layer_list)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        for label_text, handler in (
            ("Copy", self._copy_selected_layer),
            ("Cut", self._cut_selected_layer),
            ("Paste", self._paste_layer_clipboard),
            ("Delete", self._delete_selected_layer),
        ):
            btn = QPushButton(label_text)
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            edit_row.addWidget(btn)
        inspector_layout.addLayout(edit_row)
        self._layer_count_labels: dict[str, QLabel] = {}
        for key, label_text in (
            ("strokes", "Strokes"),
            ("bubbles", "Speech bubbles"),
            ("stickers", "PNG stickers"),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_label = QLabel(label_text)
            name_label.setObjectName("PaintMeta")
            count_label = QLabel("0")
            count_label.setObjectName("PaintCount")
            row.addWidget(name_label)
            row.addStretch(1)
            row.addWidget(count_label)
            inspector_layout.addLayout(row)
            self._layer_count_labels[key] = count_label

        inspector_layout.addStretch(1)
        note = QLabel(tr("paint.note"))
        note.setObjectName("PaintMeta")
        note.setWordWrap(True)
        inspector_layout.addWidget(note)
        workspace.addWidget(inspector)

        self._sync_palette_controls_from_color()
        self._highlight_selected_palette()
        self._update_inspector_counts()
        self._install_edit_shortcuts()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._bubble_items and self._bubbles:
            self._spawn_initial_bubbles()
        if not self._sticker_items and self._stickers:
            self._spawn_initial_stickers()

    def _make_palette_button(
        self,
        rgb: tuple[int, int, int],
        *,
        width: int = 44,
        height: int = 22,
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(width, height)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_palette_button(btn, rgb, selected=False, width=width, height=height)
        btn.clicked.connect(
            lambda _checked=False, b=btn: self._pick_palette_color(
                getattr(b, "_paint_rgb", rgb)
            )
        )
        return btn

    def _highlight_selected_palette(self) -> None:
        sel = (
            self._pen_color.red(),
            self._pen_color.green(),
            self._pen_color.blue(),
        )
        if hasattr(self, "_color_preview"):
            self._color_preview.setStyleSheet(
                "QLabel { "
                f"background-color: rgb({sel[0]},{sel[1]},{sel[2]}); "
                "border: 1px solid #7f8da3; border-radius: 6px; "
                "}"
            )
        if hasattr(self, "_color_hex_label"):
            self._color_hex_label.setText(self._rgb_to_hex(sel))
        for btn, rgb in zip(self._palette_btns, PALETTE_COLORS):
            self._style_palette_button(btn, rgb, selected=(rgb == sel))
        if hasattr(self, "_recent_color_btns"):
            self._refresh_recent_color_buttons(sel)
        self._update_value_slider_style()

    def _sync_palette_controls_from_color(self) -> None:
        if not hasattr(self, "hue_slider") or not hasattr(self, "value_slider"):
            return
        hue = self._pen_color.hue()
        if hue < 0:
            hue = 0
        value = max(12, min(100, round(self._pen_color.value() * 100 / 255)))
        self._palette_syncing = True
        try:
            self.hue_slider.setValue(hue)
            self.value_slider.setValue(value)
        finally:
            self._palette_syncing = False
        self._update_value_slider_style()

    def _update_value_slider_style(self) -> None:
        if not hasattr(self, "value_slider"):
            return
        hue = self._pen_color.hue()
        if hue < 0:
            hue = self.hue_slider.value() if hasattr(self, "hue_slider") else 0
        saturation = max(80, self._pen_color.saturation())
        bright = QColor.fromHsv(hue, saturation, 255)
        self.value_slider.setStyleSheet(
            "QSlider#PaintValueSlider::groove:horizontal { "
            "height: 8px; border-radius: 4px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #111827, stop:1 rgb({bright.red()},{bright.green()},{bright.blue()})); "
            "}"
            "QSlider#PaintValueSlider::handle:horizontal { "
            "width: 14px; height: 14px; margin: -4px 0; border-radius: 7px; "
            "background: #eef2f7; border: 1px solid #111827; "
            "}"
        )

    @staticmethod
    def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
        return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

    @staticmethod
    def _normalise_rgb(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        return (
            max(0, min(255, int(rgb[0]))),
            max(0, min(255, int(rgb[1]))),
            max(0, min(255, int(rgb[2]))),
        )

    def _style_palette_button(
        self,
        btn: QPushButton,
        rgb: tuple[int, int, int],
        *,
        selected: bool,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        rgb = self._normalise_rgb(rgb)
        if width is None:
            width = max(1, btn.width() or 44)
        if height is None:
            height = max(1, btn.height() or 22)
        setattr(btn, "_paint_rgb", rgb)
        btn.setToolTip(self._rgb_to_hex(rgb))
        radius = max(4, min(6, height // 3))
        border = "#b9c7dd" if selected else "#30394a"
        border_width = 2 if selected else 1
        btn.setStyleSheet(
            "QPushButton { "
            f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
            f"border: {border_width}px solid {border}; "
            f"border-radius: {radius}px; "
            "padding: 0; "
            "}"
            "QPushButton:hover { border-color: #7fa7df; }"
        )

    def _refresh_recent_color_buttons(self, selected: tuple[int, int, int]) -> None:
        for idx, btn in enumerate(self._recent_color_btns):
            if idx >= len(self._recent_colors):
                btn.hide()
                continue
            rgb = self._recent_colors[idx]
            btn.show()
            self._style_palette_button(btn, rgb, selected=(rgb == selected), width=40, height=18)

    def _remember_recent_color(self, rgb: tuple[int, int, int]) -> None:
        rgb = self._normalise_rgb(rgb)
        self._recent_colors = [item for item in self._recent_colors if item != rgb]
        self._recent_colors.insert(0, rgb)
        del self._recent_colors[RECENT_COLOR_LIMIT:]

    def _apply_pen_color(self, color: QColor, *, remember: bool) -> None:
        self._pen_color = QColor(color)
        self.canvas.set_pen_color(self._pen_color)
        if remember:
            self._remember_recent_color(
                (self._pen_color.red(), self._pen_color.green(), self._pen_color.blue())
            )
        self._sync_palette_controls_from_color()
        self._highlight_selected_palette()

    def _color_from_mixer(self) -> QColor:
        hue = self.hue_slider.value() if hasattr(self, "hue_slider") else 0
        value_percent = (
            self.value_slider.value() if hasattr(self, "value_slider") else 100
        )
        value = int(value_percent * 255 / 100)
        saturation = self._pen_color.saturation()
        if saturation < 48:
            saturation = 150
        return QColor.fromHsv(hue, saturation, max(24, min(255, value)))

    # ---------- tool actions ----------

    def _set_tool(self, tool: str) -> None:
        canvas_tool = tool if tool in ("pen", "eraser", "path") else "off"
        self.canvas.set_tool(canvas_tool)
        self.select_btn.setChecked(tool == "select")
        self.pen_btn.setChecked(tool == "pen")
        self.eraser_btn.setChecked(tool == "eraser")
        self.path_btn.setChecked(tool == "path")
        if hasattr(self, "_tool_status_label"):
            labels = {
                "select": "Select / move objects",
                "pen": "Pen",
                "eraser": "Eraser",
                "path": "Path: click points, double-click to commit",
            }
            self._tool_status_label.setText(labels.get(tool, "Select / move objects"))

    def _clear_all(self) -> None:
        self._push_undo_state()
        self.canvas.clear_strokes_direct()
        self._update_inspector_counts()

    def _pick_palette_color(self, rgb: tuple[int, int, int]) -> None:
        rgb = self._normalise_rgb(rgb)
        self._apply_pen_color(QColor(*rgb), remember=True)
        self._set_tool("pen")

    def _pick_custom_color(self) -> None:
        color = QColorDialog.getColor(self._pen_color, self, tr("paint.btn.custom_color"))
        if color.isValid():
            self._apply_pen_color(color, remember=True)
            self._set_tool("pen")

    def _on_hue_changed(self, _value: int) -> None:
        if self._palette_syncing:
            return
        self._apply_pen_color(self._color_from_mixer(), remember=False)
        self._set_tool("pen")

    def _on_value_changed(self, _value: int) -> None:
        if self._palette_syncing:
            return
        self._apply_pen_color(self._color_from_mixer(), remember=False)
        self._set_tool("pen")

    def _on_width_changed(self, value: int) -> None:
        self._pen_width = float(value)
        self.canvas.set_pen_width(self._pen_width)
        if hasattr(self, "_width_value_label"):
            self._width_value_label.setText(f"{value} px")

    def _on_opacity_changed(self, value: int) -> None:
        self._pen_opacity = int(value * 255 / 100)
        self.canvas.set_pen_opacity(self._pen_opacity)
        if hasattr(self, "_opacity_value_label"):
            self._opacity_value_label.setText(f"{value}%")

    def _on_stroke_added(self, stroke: Stroke) -> None:
        # Override the default start_ms so all dialog strokes stamp to the
        # moment the dialog was opened.
        self._push_undo_state()
        stroke.start_ms = self._time_ms
        self.canvas.add_stroke_direct(stroke)
        self._update_inspector_counts()

    def _erase_stroke_direct(self, idx: int) -> None:
        self._push_undo_state()
        self.canvas.remove_stroke_direct(idx)
        self._update_inspector_counts()

    def _apply_brush_preset(self, width: int, opacity: int) -> None:
        self.width_slider.setValue(width)
        self.opacity_slider.setValue(opacity)
        if opacity < 70:
            self.brush_style_combo.setCurrentIndex(
                max(0, self.brush_style_combo.findData("highlighter"))
            )
        elif width >= 8:
            self.brush_style_combo.setCurrentIndex(
                max(0, self.brush_style_combo.findData("marker"))
            )
        self._set_tool("pen")

    def _on_brush_style_changed(self) -> None:
        style = self.brush_style_combo.currentData() or "round"
        self.canvas.set_pen_style(str(style))

    def _commit_path(self, closed: bool) -> None:
        self.canvas.commit_path(closed=closed)
        self._update_inspector_counts()

    def _clear_path_preview(self) -> None:
        self.canvas.clear_path_preview()

    def _on_zoom_changed(self, value: int) -> None:
        self._canvas_zoom = max(0.5, min(2.0, value / 100.0))
        if hasattr(self, "_zoom_value_label"):
            self._zoom_value_label.setText(f"{value}%")
        self._update_canvas_geometry()

    def _show_export_png_menu(self) -> None:
        menu = QMenu(self)
        composited_action = menu.addAction("Composited PNG")
        overlay_action = menu.addAction("Transparent overlay PNG")
        pos = self.export_png_btn.mapToGlobal(self.export_png_btn.rect().bottomLeft())
        chosen = menu.exec(pos)
        if chosen is composited_action:
            self._export_png_to_file(include_background=True)
        elif chosen is overlay_action:
            self._export_png_to_file(include_background=False)

    def _export_png_to_file(self, *, include_background: bool) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        try:
            from app.paths import default_save_dir

            base_dir = default_save_dir()
        except Exception:
            base_dir = Path.home()
        suffix = "composited" if include_background else "overlay"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = base_dir / f"paint_{suffix}_{stamp}.png"
        path, _selected = QFileDialog.getSaveFileName(
            self,
            "Export Paint PNG",
            str(default_path),
            "PNG Image (*.png)",
        )
        if not path:
            return
        out = Path(path)
        if out.suffix.lower() != ".png":
            out = out.with_suffix(".png")
        bg = self._bg_pixmap_source if include_background else None
        target_size = _paint_export_size(
            bg,
            fallback=(max(1, self.canvas.width()), max(1, self.canvas.height())),
        )
        width_scale = target_size[0] / max(1, self.canvas.width())
        try:
            report = export_paint_png(
                out,
                background_pixmap=bg,
                strokes=self.canvas.embedded_strokes(),
                bubbles=self._bubbles,
                stickers=self._stickers,
                time_ms=self._time_ms,
                frame_size=target_size,
                include_background=include_background,
                stroke_width_scale=width_scale,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Export Paint PNG",
                f"PNG export failed: {type(exc).__name__}: {exc}",
            )
            return
        QMessageBox.information(
            self,
            "Export Paint PNG",
            f"Wrote {report.get('mode')} PNG:\n{report.get('path')}",
        )

    def _snapshot_state(self) -> tuple[list[Stroke], list[SpeechBubble], list["Sticker"]]:
        strokes = self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
        return (
            copy.deepcopy(strokes),
            copy.deepcopy(getattr(self, "_bubbles", [])),
            copy.deepcopy(getattr(self, "_stickers", [])),
        )

    def _push_undo_state(self) -> None:
        if self._restoring_state or not hasattr(self, "canvas"):
            return
        self._undo_stack.append(self._snapshot_state())
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_history_buttons()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot_state())
        snapshot = self._undo_stack.pop()
        self._restore_state(snapshot)

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot_state())
        snapshot = self._redo_stack.pop()
        self._restore_state(snapshot)

    def _restore_state(
        self,
        snapshot: tuple[list[Stroke], list[SpeechBubble], list["Sticker"]],
    ) -> None:
        self._restoring_state = True
        try:
            strokes, bubbles, stickers = snapshot
            for item in list(getattr(self, "_bubble_items", [])):
                item.deleteLater()
            for item in list(getattr(self, "_sticker_items", [])):
                item.deleteLater()
            self._bubble_items = []
            self._sticker_items = []
            self._bubbles = copy.deepcopy(bubbles)
            self._stickers = copy.deepcopy(stickers)
            self.canvas.set_strokes_snapshot(copy.deepcopy(strokes))
            self._spawn_initial_bubbles()
            self._spawn_initial_stickers()
            self._update_canvas_geometry()
        finally:
            self._restoring_state = False
        self._update_inspector_counts()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self._undo_stack))
        if hasattr(self, "redo_btn"):
            self.redo_btn.setEnabled(bool(self._redo_stack))

    def _update_inspector_counts(self) -> None:
        labels = getattr(self, "_layer_count_labels", {})
        strokes_count = 0
        if hasattr(self, "canvas"):
            strokes_count = len(self.canvas.embedded_strokes())
        counts = {
            "strokes": strokes_count,
            "bubbles": len(getattr(self, "_bubbles", [])),
            "stickers": len(getattr(self, "_stickers", [])),
        }
        for key, value in counts.items():
            label = labels.get(key)
            if label is not None:
                label.setText(str(value))
        self._update_layer_list(strokes_count)
        self._update_history_buttons()

    def _update_layer_list(self, strokes_count: int | None = None) -> None:
        layer_list = getattr(self, "_layer_list", None)
        if layer_list is None:
            return
        selected_id = self._selected_layer_id
        if strokes_count is None:
            strokes_count = len(self.canvas.embedded_strokes()) if hasattr(self, "canvas") else 0
        layer_list.blockSignals(True)
        try:
            layer_list.clear()
            if strokes_count:
                item = QListWidgetItem(f"Brush strokes ({strokes_count})")
                item.setData(Qt.ItemDataRole.UserRole, "strokes")
                layer_list.addItem(item)
                if selected_id == "strokes":
                    layer_list.setCurrentItem(item)
            for idx, bubble in enumerate(getattr(self, "_bubbles", [])):
                text = bubble.text.strip() or "Speech bubble"
                item = QListWidgetItem(f"Bubble {idx + 1}: {text[:24]}")
                layer_id = f"bubble:{idx}"
                item.setData(Qt.ItemDataRole.UserRole, layer_id)
                layer_list.addItem(item)
                if selected_id == layer_id:
                    layer_list.setCurrentItem(item)
            for idx, sticker in enumerate(getattr(self, "_stickers", [])):
                from pathlib import Path

                name = Path(sticker.png_path).name or "PNG sticker"
                item = QListWidgetItem(f"Sticker {idx + 1}: {name[:24]}")
                layer_id = f"sticker:{idx}"
                item.setData(Qt.ItemDataRole.UserRole, layer_id)
                layer_list.addItem(item)
                if selected_id == layer_id:
                    layer_list.setCurrentItem(item)
        finally:
            layer_list.blockSignals(False)

    def _select_layer_item(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_layer_id = str(layer_id) if layer_id is not None else None
        self._set_tool("select")
        if layer_id == "strokes":
            return
        if isinstance(layer_id, str) and layer_id.startswith("bubble:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._bubble_items):
                bubble_item = self._bubble_items[idx]
                bubble_item.raise_()
                bubble_item.setFocus()
            return
        if isinstance(layer_id, str) and layer_id.startswith("sticker:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._sticker_items):
                sticker_item = self._sticker_items[idx]
                sticker_item.raise_()
                sticker_item.setFocus()

    def _install_edit_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+C", self._copy_selected_layer),
            ("Ctrl+X", self._cut_selected_layer),
            ("Ctrl+V", self._paste_layer_clipboard),
            ("Delete", self._delete_selected_layer),
            ("Backspace", self._delete_selected_layer),
            ("Ctrl+D", self._duplicate_selected_layer),
        )
        self._paint_shortcuts = []
        for key, handler in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
            self._paint_shortcuts.append(shortcut)

    def _open_layer_context_menu(self, pos) -> None:
        item = self._layer_list.itemAt(pos)
        if item is not None:
            self._layer_list.setCurrentItem(item)
            self._select_layer_item(item)
        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        cut_action = menu.addAction("Cut")
        paste_action = menu.addAction("Paste")
        duplicate_action = menu.addAction("Duplicate")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        has_selection = self._selected_layer_id is not None
        copy_action.setEnabled(has_selection)
        cut_action.setEnabled(has_selection)
        duplicate_action.setEnabled(has_selection)
        delete_action.setEnabled(has_selection)
        paste_action.setEnabled(self._paint_clipboard is not None)
        chosen = menu.exec(self._layer_list.mapToGlobal(pos))
        if chosen is copy_action:
            self._copy_selected_layer()
        elif chosen is cut_action:
            self._cut_selected_layer()
        elif chosen is paste_action:
            self._paste_layer_clipboard()
        elif chosen is duplicate_action:
            self._duplicate_selected_layer()
        elif chosen is delete_action:
            self._delete_selected_layer()

    def _current_layer_id(self) -> str | None:
        if self._selected_layer_id:
            return self._selected_layer_id
        item = self._layer_list.currentItem() if hasattr(self, "_layer_list") else None
        if item is not None:
            layer_id = item.data(Qt.ItemDataRole.UserRole)
            if layer_id is not None:
                self._selected_layer_id = str(layer_id)
        return self._selected_layer_id

    def _copy_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        payload = self._payload_for_layer(self._current_layer_id())
        if payload is not None:
            self._paint_clipboard = payload

    def _cut_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        layer_id = self._current_layer_id()
        payload = self._payload_for_layer(layer_id)
        if payload is None:
            return
        self._paint_clipboard = payload
        self._delete_layer(layer_id)

    def _duplicate_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        payload = self._payload_for_layer(self._current_layer_id())
        if payload is None:
            return
        self._paste_payload(payload)

    def _paste_layer_clipboard(self) -> None:
        if self._text_editor_has_focus():
            return
        if self._paint_clipboard is None:
            return
        self._paste_payload(self._paint_clipboard)

    def _delete_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        self._delete_layer(self._current_layer_id())

    def _text_editor_has_focus(self) -> bool:
        widget = self.focusWidget()
        while widget is not None:
            if isinstance(widget, QTextEdit):
                return True
            widget = widget.parentWidget()
        return False

    def _payload_for_layer(self, layer_id: str | None) -> dict | None:
        if not layer_id:
            return None
        if layer_id == "strokes":
            strokes = self.canvas.embedded_strokes()
            if not strokes:
                return None
            return {"kind": "strokes", "strokes": copy.deepcopy(strokes)}
        if layer_id.startswith("bubble:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._bubbles):
                return {"kind": "bubble", "bubble": copy.deepcopy(self._bubbles[idx])}
        if layer_id.startswith("sticker:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._stickers):
                return {"kind": "sticker", "sticker": copy.deepcopy(self._stickers[idx])}
        return None

    def _paste_payload(self, payload: dict) -> None:
        kind = payload.get("kind")
        self._push_undo_state()
        if kind == "strokes":
            pasted = copy.deepcopy(payload.get("strokes") or [])
            for stroke in pasted:
                stroke.points = [
                    (max(0.0, min(1.0, x + 0.025)), max(0.0, min(1.0, y + 0.025)))
                    for x, y in stroke.points
                ]
                stroke.start_ms = self._time_ms
                self.canvas.add_stroke_direct(stroke)
            self._selected_layer_id = "strokes"
        elif kind == "bubble":
            bubble = copy.deepcopy(payload.get("bubble"))
            if bubble is None:
                return
            bubble.x_norm = min(0.95, float(bubble.x_norm) + 0.035)
            bubble.y_norm = min(0.95, float(bubble.y_norm) + 0.035)
            bubble.start_ms = self._time_ms
            self._bubbles.append(bubble)
            self._spawn_bubble_item(bubble)
            self._selected_layer_id = f"bubble:{len(self._bubbles) - 1}"
        elif kind == "sticker":
            sticker = copy.deepcopy(payload.get("sticker"))
            if sticker is None:
                return
            sticker.x_norm = min(0.95, float(sticker.x_norm) + 0.035)
            sticker.y_norm = min(0.95, float(sticker.y_norm) + 0.035)
            sticker.start_ms = self._time_ms
            sticker.z_index = max((s.z_index for s in self._stickers), default=0) + 1
            self._stickers.append(sticker)
            self._spawn_sticker_item(sticker)
            self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._update_inspector_counts()
        self._set_tool("select")

    def _delete_layer(self, layer_id: str | None) -> None:
        if not layer_id:
            return
        self._push_undo_state()
        if layer_id == "strokes":
            self.canvas.clear_strokes_direct()
            self._selected_layer_id = None
        elif layer_id.startswith("bubble:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._bubbles):
                bubble = self._bubbles[idx]
                item = self._bubble_items[idx] if idx < len(self._bubble_items) else None
                if item is not None:
                    self._remove_bubble(bubble, item)
                else:
                    self._bubbles.pop(idx)
                self._selected_layer_id = None
        elif layer_id.startswith("sticker:"):
            idx = int(layer_id.split(":", 1)[1])
            if 0 <= idx < len(self._stickers):
                sticker = self._stickers[idx]
                item = self._sticker_items[idx] if idx < len(self._sticker_items) else None
                if item is not None:
                    self._remove_sticker(sticker, item)
                else:
                    self._stickers.pop(idx)
                self._selected_layer_id = None
        self._update_inspector_counts()

    # ---------- layout sync ----------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_canvas_geometry()

    def _update_canvas_geometry(self) -> None:
        host = self._canvas_host
        if host is None:
            return
        hw, hh = host.width(), host.height()
        if hw <= 0 or hh <= 0:
            return

        # Scale background to fit host, keep aspect
        if self._bg_pixmap_source and not self._bg_pixmap_source.isNull():
            bg_scaled = self._bg_pixmap_source.scaled(
                hw, hh,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            zoom = float(getattr(self, "_canvas_zoom", 1.0) or 1.0)
            if abs(zoom - 1.0) > 0.001:
                bg_scaled = bg_scaled.scaled(
                    max(1, int(bg_scaled.width() * zoom)),
                    max(1, int(bg_scaled.height() * zoom)),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        else:
            bg_scaled = QPixmap()

        self._bg_label.setPixmap(bg_scaled)
        # Position the bg_label centered in the host
        bw = bg_scaled.width() if not bg_scaled.isNull() else hw
        bh = bg_scaled.height() if not bg_scaled.isNull() else hh
        bx = (hw - bw) // 2
        by = (hh - bh) // 2
        self._bg_label.setGeometry(bx, by, bw, bh)
        # Canvas covers the bg area exactly so stroke coords map 1:1 with video
        self.canvas.setGeometry(bx, by, bw, bh)
        self.canvas.raise_()
        # Re-lay out any speech bubble items so their normalized coords map
        # onto the current canvas rect.
        for item in getattr(self, "_bubble_items", []):
            item.sync_to_parent()
            item.raise_()
        # Same for stickers — stickers live under bubbles so the user can
        # still edit bubble text over a watermark.
        for item in getattr(self, "_sticker_items", []):
            item.sync_to_parent()
            item.raise_()
        # Re-raise bubbles on top of stickers.
        for item in getattr(self, "_bubble_items", []):
            item.raise_()

    def _add_bubble(self) -> None:
        self._push_undo_state()
        bubble = SpeechBubble(
            x_norm=0.15, y_norm=0.15,
            width_norm=0.35, height_norm=0.22,
            text="",
            start_ms=self._time_ms,
            tail="left",
        )
        self._bubbles.append(bubble)
        self._spawn_bubble_item(bubble)
        self._selected_layer_id = f"bubble:{len(self._bubbles) - 1}"
        self._update_inspector_counts()

    def _spawn_bubble_item(self, bubble: "SpeechBubble") -> "SpeechBubbleItem":
        item = SpeechBubbleItem(bubble, self.canvas)
        item.sync_to_parent()
        item.show()
        item.raise_()
        item.moved.connect(lambda it=item: it.sync_to_bubble())
        item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
        self._bubble_items.append(item)
        return item

    def _remove_bubble(self, bubble: "SpeechBubble", item: "SpeechBubbleItem") -> None:
        if bubble in self._bubbles:
            self._bubbles.remove(bubble)
        if item in self._bubble_items:
            self._bubble_items.remove(item)
        item.deleteLater()
        self._update_inspector_counts()

    def _spawn_initial_bubbles(self) -> None:
        for bubble in self._bubbles:
            self._spawn_bubble_item(bubble)
        self._update_inspector_counts()

    def result_strokes(self) -> list[Stroke]:
        return self.canvas.embedded_strokes()

    def result_bubbles(self) -> list["SpeechBubble"]:
        return list(self._bubbles)

    def result_stickers(self) -> list["Sticker"]:
        return list(self._stickers)

    # ---- sticker management ----

    def _add_sticker(self) -> None:
        """Prompt for a PNG, add a Sticker at the default position, and
        spawn an interactive StickerItem on the canvas."""
        from pathlib import Path

        from PySide6.QtWidgets import QFileDialog, QMessageBox

        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("sticker.pick_title"),
            str(Path.home()),
            tr("sticker.pick_filter"),
        )
        if not path:
            return
        p = Path(path)
        if not p.exists():
            return

        # Guess a sensible default size: fit the PNG at up to 25% of the
        # canvas width, preserving its aspect ratio.
        pm = QPixmap(str(p))
        if pm.isNull():
            QMessageBox.warning(
                self,
                tr("sticker.error.title"),
                tr("sticker.error.decode", name=p.name),
            )
            return

        canvas_w = max(1, self.canvas.width())
        canvas_h = max(1, self.canvas.height())
        target_w = min(pm.width(), int(canvas_w * 0.25))
        aspect = pm.height() / max(1, pm.width())
        target_h = int(target_w * aspect)
        # Clamp to canvas
        target_w = min(target_w, canvas_w - 2)
        target_h = min(target_h, canvas_h - 2)
        w_norm = max(0.05, target_w / canvas_w)
        h_norm = max(0.05, target_h / canvas_h)

        sticker = Sticker(
            png_path=str(p),
            x_norm=0.15,
            y_norm=0.15,
            width_norm=w_norm,
            height_norm=h_norm,
            start_ms=self._time_ms,
            end_ms=-1,
        )
        self._push_undo_state()
        self._stickers.append(sticker)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(sticker)
        self._update_inspector_counts()

    def _import_editor_object(self) -> None:
        """Import an editor creative object as a movable sticker layer."""
        from PySide6.QtWidgets import QMessageBox

        provider = getattr(self, "_editor_object_provider", None)
        if not callable(provider):
            QMessageBox.information(
                self,
                "Editor Object",
                "No editor object source is connected to this paint window.",
            )
            return
        try:
            raw_objects = list(provider() or [])
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Editor Object",
                f"Could not read editor objects: {type(exc).__name__}",
            )
            return
        if not raw_objects:
            QMessageBox.information(
                self,
                "Editor Object",
                "No typography, AR/PBR, or actor objects are available at this point in the project.",
            )
            return

        from app.drawing_editor_object_import import coerce_paint_import_object

        objects = [coerce_paint_import_object(item) for item in raw_objects]
        menu = QMenu(self)
        for index, obj in enumerate(objects):
            action = menu.addAction(obj.menu_label())
            action.setData(index)
        anchor = getattr(self, "editor_object_btn", self)
        pos = anchor.mapToGlobal(anchor.rect().bottomLeft()) if hasattr(anchor, "rect") else self.cursor().pos()
        chosen = menu.exec(pos)
        if chosen is None:
            return
        try:
            obj = objects[int(chosen.data())]
        except Exception:
            return
        self._place_editor_object_sticker(obj)

    def _place_editor_object_sticker(self, obj) -> None:
        from PySide6.QtWidgets import QMessageBox

        from app.drawing_editor_object_import import render_paint_import_object

        canvas_w = max(1, self.canvas.width())
        canvas_h = max(1, self.canvas.height())
        try:
            report = render_paint_import_object(
                obj,
                canvas_size=(canvas_w, canvas_h),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Editor Object",
                f"Import render failed: {type(exc).__name__}",
            )
            return
        png_path = str(report.get("png_path") or "")
        pm = QPixmap(png_path)
        if pm.isNull():
            QMessageBox.warning(
                self,
                "Editor Object",
                "The imported object poster could not be decoded as a PNG.",
            )
            return
        rect = dict(report.get("rect_norm") or {})
        w_norm = max(0.04, min(1.0, float(rect.get("w", 0.28) or 0.28)))
        h_norm = max(0.04, min(1.0, float(rect.get("h", 0.20) or 0.20)))
        x_norm = max(0.0, min(1.0 - w_norm, float(rect.get("x", 0.15) or 0.15)))
        y_norm = max(0.0, min(1.0 - h_norm, float(rect.get("y", 0.15) or 0.15)))
        sticker = Sticker(
            png_path=png_path,
            x_norm=x_norm,
            y_norm=y_norm,
            width_norm=w_norm,
            height_norm=h_norm,
            start_ms=self._time_ms,
            end_ms=-1,
            z_index=max((s.z_index for s in self._stickers), default=0) + 1,
        )
        self._push_undo_state()
        self._stickers.append(sticker)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(sticker)
        self._update_inspector_counts()
        self._set_tool("select")

    def _create_cutout_sticker(self) -> None:
        """Create a foreground cutout from the current frame as a PNG sticker."""
        from datetime import datetime
        from pathlib import Path

        import numpy as np
        from PIL import Image, ImageFilter
        from PySide6.QtWidgets import QMessageBox

        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            QMessageBox.warning(self, "Cutout", "No frame is available for cutout.")
            return
        self._push_undo_state()
        out_dir = Path("external/assets/paint_cutouts")
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        source_path = out_dir / f"cutout_source_{stamp}.png"
        out_path = out_dir / f"cutout_{stamp}.png"
        try:
            self._bg_pixmap_source.save(str(source_path), "PNG")
            img = Image.open(source_path).convert("RGBA")
            rgb = np.asarray(img.convert("RGB"))
            from app.background_removal import BackgroundRemovalParams

            params = BackgroundRemovalParams(
                enabled=True,
                method="rembg",
                bg_mode="transparent",
                feather=5,
                threshold=0.45,
            )
            mask = params._get_mask(rgb)
            if mask is None:
                raise RuntimeError("background removal unavailable")
            alpha = Image.fromarray(
                np.clip(mask * 255.0, 0, 255).astype("uint8"),
                mode="L",
            ).filter(ImageFilter.GaussianBlur(radius=1.6))
            bbox = alpha.getbbox()
            if bbox is None:
                raise RuntimeError("no foreground detected")
            cut = img.copy()
            cut.putalpha(alpha)
            cut = cut.crop(bbox)
            cut.save(out_path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Cutout",
                f"Cutout failed: {type(exc).__name__}",
            )
            return
        finally:
            try:
                source_path.unlink(missing_ok=True)
            except Exception:
                pass

        frame_w = max(1, self._bg_pixmap_source.width())
        frame_h = max(1, self._bg_pixmap_source.height())
        x0, y0, x1, y1 = bbox
        sticker = Sticker(
            png_path=str(out_path.resolve()),
            x_norm=max(0.0, min(0.95, x0 / frame_w)),
            y_norm=max(0.0, min(0.95, y0 / frame_h)),
            width_norm=max(0.04, min(1.0, (x1 - x0) / frame_w)),
            height_norm=max(0.04, min(1.0, (y1 - y0) / frame_h)),
            start_ms=self._time_ms,
            end_ms=-1,
            z_index=max((s.z_index for s in self._stickers), default=0) + 1,
        )
        self._stickers.append(sticker)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(sticker)
        self._update_inspector_counts()
        self._set_tool("select")

    def _spawn_sticker_item(self, sticker: "Sticker") -> "StickerItem":
        item = StickerItem(sticker, self.canvas)
        item.sync_to_parent()
        item.show()
        item.raise_()
        # Re-raise bubbles so they sit on top of stickers (stickers =
        # backdrop, bubbles = foreground captions).
        for b_item in self._bubble_items:
            b_item.raise_()
        item.moved.connect(lambda it=item: it.sync_to_sticker())
        item.deleted.connect(lambda it=item, s=sticker: self._remove_sticker(s, it))
        item.duplicated.connect(lambda s=sticker: self._duplicate_sticker(s))
        item.raise_requested.connect(lambda s=sticker: self._reorder_sticker(s, +1))
        item.lower_requested.connect(lambda s=sticker: self._reorder_sticker(s, -1))
        self._sticker_items.append(item)
        self._update_inspector_counts()
        return item

    def _remove_sticker(self, sticker: "Sticker", item: "StickerItem") -> None:
        if sticker in self._stickers:
            self._stickers.remove(sticker)
        if item in self._sticker_items:
            self._sticker_items.remove(item)
        item.deleteLater()
        self._update_inspector_counts()

    def _spawn_initial_stickers(self) -> None:
        for sticker in self._stickers:
            self._spawn_sticker_item(sticker)
        self._update_inspector_counts()

    def _duplicate_sticker(self, sticker: "Sticker") -> None:
        import copy
        self._push_undo_state()
        dup = copy.deepcopy(sticker)
        # Nudge the copy a little so it doesn't sit exactly on top.
        dup.x_norm = min(0.95, dup.x_norm + 0.03)
        dup.y_norm = min(0.95, dup.y_norm + 0.03)
        # Put new stickers on top by default.
        current_max_z = max((s.z_index for s in self._stickers), default=0)
        dup.z_index = current_max_z + 1
        self._stickers.append(dup)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(dup)
        self._update_inspector_counts()

    def _reorder_sticker(self, sticker: "Sticker", direction: int) -> None:
        """direction > 0 → send to front; < 0 → send to back."""
        if direction > 0:
            sticker.z_index = max(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) + 1
        else:
            sticker.z_index = min(
                (s.z_index for s in self._stickers if s is not sticker),
                default=0,
            ) - 1
        # Re-stack widgets: highest z_index on top.
        self._sticker_items.sort(key=lambda it: int(it.sticker.z_index))
        for it in self._sticker_items:
            it.raise_()
        # Bubbles always float above stickers.
        for b_item in self._bubble_items:
            b_item.raise_()


# ---------------------------------------------------------------------------
#  Speech bubble
# ---------------------------------------------------------------------------


@dataclass
class SpeechBubble:
    """A persistent callout placed on the preview. Coords are normalized to
    the video rect so the bubble scales with preview resize / export."""

    x_norm: float = 0.1
    y_norm: float = 0.1
    width_norm: float = 0.35
    height_norm: float = 0.18
    text: str = ""
    start_ms: int = 0
    tail: str = "left"  # "left" or "right"


def _build_bubble_path(rect: QRectF, tail: str, radius: float = 12.0) -> QPainterPath:
    """Return a QPainterPath for the rounded bubble body + a downward tail
    attached to the bottom-left or bottom-right corner."""
    body = QPainterPath()
    body.addRoundedRect(rect, radius, radius)

    # Tail triangle: ~14 px horizontal base below the bubble, ~16 px tall.
    tail_w = max(10.0, min(18.0, rect.width() * 0.12))
    tail_h = max(10.0, min(22.0, rect.height() * 0.45))
    bottom_y = rect.bottom()
    if tail == "right":
        x_attach = rect.right() - rect.width() * 0.28
    else:
        x_attach = rect.left() + rect.width() * 0.28
    poly = QPolygonF([
        QPointF(x_attach - tail_w / 2, bottom_y - 1),
        QPointF(x_attach + tail_w / 2, bottom_y - 1),
        QPointF(x_attach + tail_w / 4, bottom_y + tail_h),
    ])
    tail_path = QPainterPath()
    tail_path.addPolygon(poly)
    tail_path.closeSubpath()
    return body.united(tail_path)


class SpeechBubbleItem(QWidget):
    """Interactive, draggable speech bubble placed on the preview. Text is
    edited in-place via an embedded QTextEdit. Corner buttons toggle tail
    side and delete the bubble."""

    moved = Signal()          # geometry changed (drag, etc.)
    deleted = Signal()
    text_changed = Signal()
    tail_changed = Signal()

    HANDLE_SIZE = 18
    RESIZE_GRIP_PX = 16
    MIN_WIDTH = 80
    MIN_HEIGHT = 60
    TAIL_EXTRA_PX = 22       # extra space below body for the tail
    TEXT_PADDING = 10

    def __init__(self, bubble: SpeechBubble, parent: QWidget) -> None:
        super().__init__(parent)
        self.bubble = bubble
        self._dragging = False
        self._resizing = False
        self._drag_offset = QPoint()
        self._resize_start_size = QPoint()
        self._resize_start_mouse = QPoint()

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)

        # In-place text editor — transparent, sits over the bubble body.
        self._text = QTextEdit(self)
        self._text.setFrameShape(QTextEdit.Shape.NoFrame)
        self._text.setStyleSheet(
            "QTextEdit { background: transparent; color: #1a1a1a; "
            "font-size: 14px; font-weight: 600; border: none; }"
        )
        self._text.setPlainText(bubble.text)
        self._text.textChanged.connect(self._on_text_changed)

        # Tail toggle button (L/R) — top-right of the bubble header
        self._tail_btn = QPushButton("↔", self)
        self._tail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tail_btn.setToolTip(tr("bubble.toggle_tail"))
        self._tail_btn.setFixedSize(self.HANDLE_SIZE, self.HANDLE_SIZE)
        self._tail_btn.setStyleSheet(
            "QPushButton { background: #4a4a4a; color: white; "
            "border: 1px solid #5a5a5a; "
            "border-radius: 9px; font-size: 10px; font-weight: 700; }"
            "QPushButton:hover { background: #5a5a5a; border-color: #6a6a6a; }"
        )
        self._tail_btn.clicked.connect(self._on_toggle_tail)

        # Delete button — top-left
        self._del_btn = QPushButton("✕", self)
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setToolTip(tr("bubble.delete"))
        self._del_btn.setFixedSize(self.HANDLE_SIZE, self.HANDLE_SIZE)
        self._del_btn.setStyleSheet(
            "QPushButton { background: #c53030; color: white; border: none; "
            "border-radius: 9px; font-size: 10px; font-weight: 700; }"
            "QPushButton:hover { background: #e54646; }"
        )
        self._del_btn.clicked.connect(self.deleted.emit)

        # Set focus on creation so user can type immediately.
        self._text.setFocus()

    # ------- layout helpers -------

    def _body_rect(self) -> QRectF:
        """Bubble body rectangle in local coords (excluding the tail)."""
        return QRectF(
            0, 0,
            self.width(),
            max(1.0, self.height() - self.TAIL_EXTRA_PX),
        )

    def resizeEvent(self, _e) -> None:
        body = self._body_rect()
        pad = self.TEXT_PADDING
        self._text.setGeometry(
            int(body.left() + pad + 4),
            int(body.top() + pad + self.HANDLE_SIZE + 2),
            int(max(20, body.width() - 2 * pad - 8)),
            int(max(20, body.height() - 2 * pad - self.HANDLE_SIZE - 4)),
        )
        self._tail_btn.move(int(body.right() - self.HANDLE_SIZE - 4), 4)
        self._del_btn.move(4, 4)

    def paintEvent(self, _e) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = _build_bubble_path(self._body_rect(), self.bubble.tail)
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.setPen(QPen(QColor(30, 30, 34), 2))
        painter.drawPath(path)

        # Resize grip — three diagonal ticks in the bottom-right corner of
        # the body rect. Always visible so users discover resizing.
        body = self._body_rect()
        gx = int(body.right()) - self.RESIZE_GRIP_PX
        gy = int(body.bottom()) - self.RESIZE_GRIP_PX
        pen = QPen(QColor(90, 90, 100))
        pen.setWidth(2)
        painter.setPen(pen)
        for step in (4, 8, 12):
            painter.drawLine(
                gx + self.RESIZE_GRIP_PX - step, int(body.bottom()) - 2,
                int(body.right()) - 2, gy + self.RESIZE_GRIP_PX - step,
            )

    def _grip_rect(self) -> QRectF:
        body = self._body_rect()
        return QRectF(
            body.right() - self.RESIZE_GRIP_PX,
            body.bottom() - self.RESIZE_GRIP_PX,
            self.RESIZE_GRIP_PX,
            self.RESIZE_GRIP_PX,
        )

    # ------- tail / text -------

    def _on_toggle_tail(self) -> None:
        self.bubble.tail = "right" if self.bubble.tail == "left" else "left"
        self.update()
        self.tail_changed.emit()

    def _on_text_changed(self) -> None:
        self.bubble.text = self._text.toPlainText()
        self.text_changed.emit()

    # ------- drag to move -------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        # Resize grip at bottom-right takes priority
        if self._grip_rect().contains(pos):
            self._resizing = True
            self._resize_start_size = QPoint(self.width(), self.height())
            self._resize_start_mouse = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            return
        # Clicks over the text editor or corner buttons are handled by those
        # widgets; only bubble body starts a drag.
        child = self.childAt(pos)
        if child in (self._text, self._tail_btn, self._del_btn):
            return
        self._dragging = True
        self._drag_offset = pos
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._resizing:
            parent = self.parentWidget()
            dx = event.globalPosition().toPoint().x() - self._resize_start_mouse.x()
            dy = event.globalPosition().toPoint().y() - self._resize_start_mouse.y()
            new_w = max(self.MIN_WIDTH, self._resize_start_size.x() + dx)
            new_h = max(self.MIN_HEIGHT, self._resize_start_size.y() + dy)
            if parent is not None:
                new_w = min(new_w, parent.width() - self.x())
                new_h = min(new_h, parent.height() - self.y())
            self.resize(new_w, new_h)
            return
        if self._dragging:
            parent = self.parentWidget()
            if parent is None:
                return
            new_global = event.globalPosition().toPoint() - self._drag_offset
            new_local = parent.mapFromGlobal(new_global)
            nx = max(0, min(parent.width() - self.width(), new_local.x()))
            ny = max(0, min(parent.height() - self.height(), new_local.y()))
            self.move(nx, ny)
            return
        # Idle hover — swap cursor when pointer sits on the grip so the user
        # sees it's resizable.
        if self._grip_rect().contains(pos):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._resizing:
            self._resizing = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.moved.emit()
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.moved.emit()

    def sync_to_parent(self) -> None:
        """Pull geometry from the stored ``SpeechBubble`` relative to the
        parent preview area (so the bubble re-lays-out on preview resize)."""
        parent = self.parentWidget()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        if pw <= 0 or ph <= 0:
            return
        w = max(80, int(self.bubble.width_norm * pw))
        h = max(60, int(self.bubble.height_norm * ph))
        x = max(0, min(pw - w, int(self.bubble.x_norm * pw)))
        y = max(0, min(ph - h, int(self.bubble.y_norm * ph)))
        self.setGeometry(x, y, w, h)

    def sync_to_bubble(self) -> None:
        """Write current widget geometry back into the stored bubble (after
        drag)."""
        parent = self.parentWidget()
        if parent is None:
            return
        pw, ph = max(1, parent.width()), max(1, parent.height())
        self.bubble.x_norm = self.x() / pw
        self.bubble.y_norm = self.y() / ph
        self.bubble.width_norm = self.width() / pw
        self.bubble.height_norm = self.height() / ph


def render_bubble_to_png(
    bubble: SpeechBubble, width: int, height: int, out_path: str
) -> bool:
    """Render a single speech bubble to a transparent PNG at the given size.
    Used as an FFmpeg overlay input during MP4 export."""
    from PIL import Image
    if width <= 0 or height <= 0:
        return False
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas = compose_pil_bubbles(canvas, [bubble], int(bubble.start_ms))
    try:
        canvas.save(out_path, "PNG")
        return True
    except Exception:
        return False


def compose_pil_bubbles(frame, bubbles: list[SpeechBubble], time_ms: int):
    """Burn any active speech bubbles onto the PIL frame. Returns the same
    frame (mutated) for chain-friendliness."""
    from PIL import ImageDraw, ImageFont

    active = [b for b in (bubbles or []) if b.start_ms <= int(time_ms)]
    if not active:
        return frame
    if frame.mode != "RGBA":
        out = frame.convert("RGBA")
    else:
        out = frame.copy()
    draw = ImageDraw.Draw(out)
    w, h = out.size

    # Pick a reasonable sans-serif font
    font = None
    for name in ("malgun.ttf", "arial.ttf", "segoeui.ttf"):
        try:
            font = ImageFont.truetype(name, max(14, int(h * 0.03)))
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    for b in active:
        bw = max(40, int(b.width_norm * w))
        bh = max(30, int(b.height_norm * h))
        bx = max(0, int(b.x_norm * w))
        by = max(0, int(b.y_norm * h))
        tail_extra = max(14, int(bh * 0.3))
        body_h = max(20, bh - tail_extra)

        body_box = [bx, by, bx + bw, by + body_h]
        radius = max(6, int(min(bw, body_h) * 0.15))
        draw.rounded_rectangle(
            body_box, radius, fill=(255, 255, 255, 235), outline=(30, 30, 34), width=2
        )

        # Tail
        tail_w = max(10, int(bw * 0.12))
        if b.tail == "right":
            x_attach = bx + int(bw * 0.72)
        else:
            x_attach = bx + int(bw * 0.28)
        tail_pts = [
            (x_attach - tail_w // 2, by + body_h - 1),
            (x_attach + tail_w // 2, by + body_h - 1),
            (x_attach + tail_w // 4, by + body_h + tail_extra),
        ]
        draw.polygon(tail_pts, fill=(255, 255, 255, 235), outline=(30, 30, 34))
        # Smooth the seam between body and tail
        draw.line(
            [(x_attach - tail_w // 2 + 1, by + body_h - 1),
             (x_attach + tail_w // 2 - 1, by + body_h - 1)],
            fill=(255, 255, 255, 235), width=2,
        )

        # Text — simple left-aligned wrap
        if b.text.strip():
            pad = max(6, int(min(bw, body_h) * 0.08))
            text_box = (bx + pad, by + pad, bx + bw - pad, by + body_h - pad)
            _draw_wrapped_text(draw, b.text, font, text_box, (20, 20, 24))

    if frame.mode != "RGBA":
        return out.convert(frame.mode)
    return out


def _draw_wrapped_text(draw, text: str, font, box, fill) -> None:
    """Word-wrap ``text`` into the bounding box and draw it line by line."""
    x0, y0, x1, y1 = box
    max_w = x1 - x0
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        candidate = (line + " " + word).strip()
        if font.getlength(candidate) <= max_w or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    # Fall back to splitting on character boundaries for very long strings
    if not lines and text.strip():
        lines = [text]
    line_h = font.size + 4
    y = y0
    for ln in lines:
        if y + line_h > y1:
            break
        draw.text((x0, y), ln, font=font, fill=fill)
        y += line_h


# ---------------------------------------------------------------------------
#  PNG sticker / watermark
# ---------------------------------------------------------------------------


@dataclass
class Sticker:
    """A PNG image stamped onto the preview. Coords are normalized to the
    video rect. The PNG's own alpha channel is preserved (partial
    transparency passes through); ``opacity`` multiplies on top of that
    for global dimming (watermark use case)."""

    png_path: str = ""                 # absolute path to the source PNG
    x_norm: float = 0.15
    y_norm: float = 0.15
    width_norm: float = 0.2            # un-rotated footprint
    height_norm: float = 0.2
    opacity: float = 100.0             # 0..100 (%)
    rotation_deg: float = 0.0          # 0..359
    start_ms: int = 0                  # when the sticker appears
    end_ms: int = -1                   # -1 = stays until the end
    z_index: int = 0                   # lower draws first (bottom)


def _sticker_active(sticker: Sticker, time_ms: int) -> bool:
    """Return True if the sticker is visible at ``time_ms``."""
    if time_ms < int(sticker.start_ms):
        return False
    if sticker.end_ms is not None and int(sticker.end_ms) >= 0:
        if time_ms >= int(sticker.end_ms):
            return False
    return True


def _load_sticker_pixmap_cache() -> dict:
    """Shared QPixmap cache so repeated paints don't reload the PNG from
    disk. Keyed by ``(path, mtime)`` so edits on disk invalidate."""
    if not hasattr(_load_sticker_pixmap_cache, "_cache"):
        _load_sticker_pixmap_cache._cache = {}
    return _load_sticker_pixmap_cache._cache


def get_sticker_pixmap(path: str) -> QPixmap | None:
    """Load (and cache) the sticker's source PNG as a QPixmap."""
    from pathlib import Path
    if not path:
        return None
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return None
    cache = _load_sticker_pixmap_cache()
    key = (path, mtime)
    hit = cache.get(key)
    if hit is not None:
        return hit
    pm = QPixmap(path)
    if pm.isNull():
        return None
    cache[key] = pm
    return pm


def compose_pil_stickers(frame, stickers: list[Sticker], time_ms: int):
    """Burn active PNG stickers onto the PIL frame. Returns the mutated
    frame (chain-friendly). Supports alpha, rotation, global opacity, and
    time windows."""
    from PIL import Image

    active = [s for s in (stickers or []) if _sticker_active(s, int(time_ms))]
    if not active:
        return frame
    # Respect z_index: lower renders first, higher lands on top.
    active = sorted(active, key=lambda s: int(getattr(s, "z_index", 0)))

    if frame.mode != "RGBA":
        out = frame.convert("RGBA")
    else:
        out = frame.copy()
    W, H = out.size

    for s in active:
        src = _open_sticker_pil(s.png_path)
        if src is None:
            continue
        tw = max(1, int(s.width_norm * W))
        th = max(1, int(s.height_norm * H))
        tx = int(s.x_norm * W)
        ty = int(s.y_norm * H)

        # Resize (preserving internal alpha), then apply global opacity,
        # then rotate. Order matters: rotating *after* resize keeps edges
        # sharp; opacity *before* rotate lets the rotate's bilinear sampler
        # mix dimmed pixels (visually identical, computationally cheaper).
        img = src.resize((tw, th), Image.LANCZOS)

        opacity = max(0.0, min(1.0, float(s.opacity) / 100.0))
        if opacity < 0.999:
            alpha = img.getchannel("A").point(lambda v: int(v * opacity))
            img.putalpha(alpha)

        rot = float(s.rotation_deg) % 360.0
        if abs(rot) > 0.05:
            img = img.rotate(-rot, resample=Image.BICUBIC, expand=True)

        # Paste centered on (tx + tw/2, ty + th/2) so rotation pivots on
        # the sticker's visual center — matches Qt's QPainter.rotate.
        cx = tx + tw // 2
        cy = ty + th // 2
        px = cx - img.size[0] // 2
        py = cy - img.size[1] // 2
        out.alpha_composite(img, (px, py))

    if frame.mode != "RGBA":
        return out.convert(frame.mode)
    return out


def _open_sticker_pil(path: str):
    """PIL-side loader with a tiny cache. Returns None on decode error."""
    from pathlib import Path
    from PIL import Image
    if not path:
        return None
    if not hasattr(_open_sticker_pil, "_cache"):
        _open_sticker_pil._cache = {}
    try:
        mtime = Path(path).stat().st_mtime
    except OSError:
        return None
    key = (path, mtime)
    hit = _open_sticker_pil._cache.get(key)
    if hit is not None:
        return hit
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        return None
    _open_sticker_pil._cache[key] = img
    return img


def render_sticker_to_png(
    sticker: Sticker, width: int, height: int, out_path: str
) -> bool:
    """Render a single sticker to a transparent PNG at the given frame
    size. Used by the MP4 exporter as an FFmpeg overlay input."""
    from PIL import Image
    if width <= 0 or height <= 0:
        return False
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas = compose_pil_stickers(canvas, [sticker], int(sticker.start_ms))
    try:
        canvas.save(out_path, "PNG")
        return True
    except Exception:
        return False


class StickerItem(QWidget):
    """Interactive, draggable, rotatable PNG sticker placed on the preview.

    Mirrors the SpeechBubbleItem pattern (norm-coord widget living on
    the DrawingCanvas): drag-to-move, corner-grip resize (aspect-locked
    by default, Shift unlocks), ✕ delete button, right-click menu for
    opacity / rotation / time window / z-order / duplicate."""

    moved = Signal()
    deleted = Signal()
    duplicated = Signal()         # parent inserts a copy into its list
    raise_requested = Signal()    # z-order: send to front
    lower_requested = Signal()    # z-order: send to back

    HANDLE_SIZE = 18
    GIZMO_VISUAL_PX = 9         # painted square at each handle
    GIZMO_HIT_PX = 14           # generous hit area
    MIN_WIDTH = 24
    MIN_HEIGHT = 24
    # 8 resize handles. Names encode direction: t=top, b=bottom,
    # l=left, r=right; corners combine two letters.
    HANDLES = ("tl", "t", "tr", "l", "r", "bl", "b", "br")

    def __init__(self, sticker: Sticker, parent: QWidget) -> None:
        super().__init__(parent)
        self.sticker = sticker
        self._dragging = False
        self._resizing = False
        self._resize_handle: str = ""        # which gizmo is being dragged
        self._drag_offset = QPoint()
        self._resize_start_geom = QRect()
        self._resize_start_mouse = QPoint()
        self._resize_free_aspect = False

        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        # Delete button — top-right so it doesn't crowd the usual top-left
        # content area of watermarks.
        self._del_btn = QPushButton("✕", self)
        self._del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._del_btn.setToolTip(tr("sticker.delete"))
        self._del_btn.setFixedSize(self.HANDLE_SIZE, self.HANDLE_SIZE)
        self._del_btn.setStyleSheet(
            "QPushButton { background: #c53030; color: white; border: none; "
            "border-radius: 9px; font-size: 10px; font-weight: 700; }"
            "QPushButton:hover { background: #e54646; }"
        )
        self._del_btn.clicked.connect(self.deleted.emit)

    # ---- layout ----

    def resizeEvent(self, _e) -> None:
        self._del_btn.move(self.width() - self.HANDLE_SIZE - 4, 4)

    def paintEvent(self, _e) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        pm = get_sticker_pixmap(self.sticker.png_path)
        if pm is None or pm.isNull():
            # Decode failed — paint a placeholder box so the user can
            # still interact with / delete the sticker.
            painter.fillRect(self.rect(), QColor(200, 50, 50, 120))
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "PNG error"
            )
            self._paint_grip(painter)
            return

        # Global opacity on top of the PNG's own alpha.
        opacity = max(0.0, min(1.0, float(self.sticker.opacity) / 100.0))
        painter.setOpacity(opacity)

        rot = float(self.sticker.rotation_deg) % 360.0
        if abs(rot) < 0.05:
            painter.drawPixmap(self.rect(), pm, pm.rect())
        else:
            # Rotate around the widget center so scaling keeps the
            # pivot stable. The widget's own rect doesn't expand with
            # rotation here (simpler bookkeeping); very steep angles
            # will clip slightly at the corners in preview. Export is
            # PIL-based and doesn't clip.
            cx = self.width() / 2.0
            cy = self.height() / 2.0
            painter.translate(cx, cy)
            painter.rotate(rot)
            painter.translate(-cx, -cy)
            painter.drawPixmap(self.rect(), pm, pm.rect())

        painter.resetTransform()
        painter.setOpacity(1.0)
        self._paint_gizmos(painter)

    # ---- gizmo geometry ----

    def _gizmo_centers(self) -> dict:
        """Map handle name → (cx, cy) in widget-local coords."""
        w, h = self.width(), self.height()
        return {
            "tl": (0,        0),
            "t":  (w // 2,   0),
            "tr": (w,        0),
            "l":  (0,        h // 2),
            "r":  (w,        h // 2),
            "bl": (0,        h),
            "b":  (w // 2,   h),
            "br": (w,        h),
        }

    def _handle_hit_rect(self, name: str) -> QRect:
        cx, cy = self._gizmo_centers()[name]
        s = self.GIZMO_HIT_PX
        return QRect(cx - s // 2, cy - s // 2, s, s)

    def _handle_visual_rect(self, name: str) -> QRect:
        cx, cy = self._gizmo_centers()[name]
        s = self.GIZMO_VISUAL_PX
        return QRect(cx - s // 2, cy - s // 2, s, s)

    def _handle_at(self, pos: QPoint) -> str:
        """Return the handle name under ``pos``, or empty string."""
        for name in self.HANDLES:
            if self._handle_hit_rect(name).contains(pos):
                return name
        return ""

    @staticmethod
    def _cursor_for_handle(name: str):
        diag1 = Qt.CursorShape.SizeFDiagCursor   # ↘ ↖ — "tl" + "br"
        diag2 = Qt.CursorShape.SizeBDiagCursor   # ↗ ↙ — "tr" + "bl"
        return {
            "tl": diag1, "br": diag1,
            "tr": diag2, "bl": diag2,
            "t": Qt.CursorShape.SizeVerCursor,
            "b": Qt.CursorShape.SizeVerCursor,
            "l": Qt.CursorShape.SizeHorCursor,
            "r": Qt.CursorShape.SizeHorCursor,
        }.get(name, Qt.CursorShape.ArrowCursor)

    def _paint_gizmos(self, painter: QPainter) -> None:
        """Draw the 8 resize handles as small red squares with a
        white border. Visible on top of the sticker so they read as
        the active selection chrome."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for name in self.HANDLES:
            r = self._handle_visual_rect(name)
            # Drop shadow for legibility on light backgrounds.
            painter.fillRect(r.adjusted(1, 1, 1, 1), QColor(0, 0, 0, 130))
            painter.fillRect(r, QColor("#E54646"))
            painter.setPen(QPen(QColor(255, 255, 255), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(r)

    # ---- interaction ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position().toPoint()
        # 1. Resize handles take priority over body drag / delete btn.
        handle = self._handle_at(pos)
        if handle:
            self._resizing = True
            self._resize_handle = handle
            self._resize_start_geom = QRect(
                self.x(), self.y(), self.width(), self.height()
            )
            self._resize_start_mouse = event.globalPosition().toPoint()
            # Shift unlocks aspect for corner handles. Edge handles
            # are always single-axis regardless of modifiers.
            self._resize_free_aspect = bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            )
            self.setCursor(self._cursor_for_handle(handle))
            return
        if self.childAt(pos) is self._del_btn:
            return
        self._dragging = True
        self._drag_offset = pos
        self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint()
        if self._resizing and self._resize_handle:
            self._apply_resize(event.globalPosition().toPoint())
            return
        if self._dragging:
            parent = self.parentWidget()
            if parent is None:
                return
            new_global = event.globalPosition().toPoint() - self._drag_offset
            new_local = parent.mapFromGlobal(new_global)
            nx = max(0, min(parent.width() - self.width(), new_local.x()))
            ny = max(0, min(parent.height() - self.height(), new_local.y()))
            self.move(nx, ny)
            return
        # Idle hover — pick the cursor for whichever handle is under
        # the pointer (or default arrow elsewhere).
        handle = self._handle_at(pos)
        if handle:
            self.setCursor(self._cursor_for_handle(handle))
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def _apply_resize(self, mouse_global: QPoint) -> None:
        """Re-position / resize the widget based on the current handle
        and mouse delta. Handles aspect lock for corners and parent-
        bounds clamping."""
        handle = self._resize_handle
        start = self._resize_start_geom
        dx = mouse_global.x() - self._resize_start_mouse.x()
        dy = mouse_global.y() - self._resize_start_mouse.y()

        x, y, w, h = start.x(), start.y(), start.width(), start.height()
        new_x, new_y, new_w, new_h = x, y, w, h

        if "l" in handle:
            new_x = x + dx
            new_w = w - dx
        elif "r" in handle:
            new_w = w + dx
        if "t" in handle:
            new_y = y + dy
            new_h = h - dy
        elif "b" in handle:
            new_h = h + dy

        # Min-size enforcement (anchor stays on the *opposite* edge).
        if new_w < self.MIN_WIDTH:
            if "l" in handle:
                new_x = (x + w) - self.MIN_WIDTH
            new_w = self.MIN_WIDTH
        if new_h < self.MIN_HEIGHT:
            if "t" in handle:
                new_y = (y + h) - self.MIN_HEIGHT
            new_h = self.MIN_HEIGHT

        # Aspect lock for corners (Shift held during press → unlocked).
        is_corner = handle in ("tl", "tr", "bl", "br")
        if is_corner and not self._resize_free_aspect and w > 0 and h > 0:
            aspect = w / h
            # Pick the dimension with the larger absolute change as
            # the driver, then derive the other. Matches Photoshop.
            if abs(new_w - w) >= abs(new_h - h):
                target_w = new_w
                target_h = max(self.MIN_HEIGHT, int(round(target_w / aspect)))
            else:
                target_h = new_h
                target_w = max(self.MIN_WIDTH, int(round(target_h * aspect)))
            if "l" in handle:
                new_x = (x + w) - target_w
            if "t" in handle:
                new_y = (y + h) - target_h
            new_w = target_w
            new_h = target_h

        # Parent-bounds clamp.
        parent = self.parentWidget()
        if parent is not None:
            if new_x < 0:
                new_w += new_x  # shrink width by however much we'd go off-screen
                new_x = 0
            if new_y < 0:
                new_h += new_y
                new_y = 0
            if new_x + new_w > parent.width():
                new_w = parent.width() - new_x
            if new_y + new_h > parent.height():
                new_h = parent.height() - new_y

        self.setGeometry(new_x, new_y, max(self.MIN_WIDTH, new_w),
                         max(self.MIN_HEIGHT, new_h))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._resizing:
            self._resizing = False
            self._resize_handle = ""
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.moved.emit()
        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.moved.emit()

    # ---- geometry ↔ sticker sync ----

    def sync_to_parent(self) -> None:
        """Pull widget geometry from the stored Sticker."""
        parent = self.parentWidget()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        if pw <= 0 or ph <= 0:
            return
        w = max(self.MIN_WIDTH, int(self.sticker.width_norm * pw))
        h = max(self.MIN_HEIGHT, int(self.sticker.height_norm * ph))
        x = max(0, min(pw - w, int(self.sticker.x_norm * pw)))
        y = max(0, min(ph - h, int(self.sticker.y_norm * ph)))
        self.setGeometry(x, y, w, h)

    def sync_to_sticker(self) -> None:
        """Write current widget geometry back to the stored Sticker."""
        parent = self.parentWidget()
        if parent is None:
            return
        pw, ph = max(1, parent.width()), max(1, parent.height())
        self.sticker.x_norm = self.x() / pw
        self.sticker.y_norm = self.y() / ph
        self.sticker.width_norm = self.width() / pw
        self.sticker.height_norm = self.height() / ph

    # ---- right-click menu ----

    def _on_context_menu(self, pos) -> None:
        from PySide6.QtWidgets import QInputDialog, QMenu

        menu = QMenu(self)
        a_opacity = menu.addAction(tr("sticker.menu.opacity"))
        a_rotate = menu.addAction(tr("sticker.menu.rotate"))
        a_time = menu.addAction(tr("sticker.menu.time_window"))
        menu.addSeparator()
        a_dup = menu.addAction(tr("sticker.menu.duplicate"))
        a_front = menu.addAction(tr("sticker.menu.to_front"))
        a_back = menu.addAction(tr("sticker.menu.to_back"))
        menu.addSeparator()
        a_del = menu.addAction(tr("sticker.menu.delete"))

        chosen = menu.exec(self.mapToGlobal(pos))
        if chosen is a_opacity:
            v, ok = QInputDialog.getInt(
                self, tr("sticker.dialog.opacity_title"),
                tr("sticker.dialog.opacity_label"),
                int(self.sticker.opacity), 0, 100, 5,
            )
            if ok:
                self.sticker.opacity = float(v)
                self.update()
                self.moved.emit()
        elif chosen is a_rotate:
            v, ok = QInputDialog.getInt(
                self, tr("sticker.dialog.rotate_title"),
                tr("sticker.dialog.rotate_label"),
                int(self.sticker.rotation_deg), 0, 359, 5,
            )
            if ok:
                self.sticker.rotation_deg = float(v)
                self.update()
                self.moved.emit()
        elif chosen is a_time:
            self._prompt_time_window()
        elif chosen is a_dup:
            self.duplicated.emit()
        elif chosen is a_front:
            self.raise_requested.emit()
        elif chosen is a_back:
            self.lower_requested.emit()
        elif chosen is a_del:
            self.deleted.emit()

    def _prompt_time_window(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        # Start (ms)
        start_v, ok = QInputDialog.getInt(
            self, tr("sticker.dialog.time_start_title"),
            tr("sticker.dialog.time_start_label"),
            int(self.sticker.start_ms), 0, 24 * 60 * 60 * 1000, 100,
        )
        if not ok:
            return
        # End (ms) — -1 means "until end"; display as 0 for the dialog
        # then convert.
        current_end = self.sticker.end_ms
        dialog_end = 0 if current_end is None or current_end < 0 else int(current_end)
        end_v, ok = QInputDialog.getInt(
            self, tr("sticker.dialog.time_end_title"),
            tr("sticker.dialog.time_end_label"),
            dialog_end, 0, 24 * 60 * 60 * 1000, 100,
        )
        if not ok:
            return
        self.sticker.start_ms = int(start_v)
        self.sticker.end_ms = -1 if end_v <= start_v else int(end_v)
        self.moved.emit()
