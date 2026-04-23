from __future__ import annotations

from dataclasses import dataclass, field
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
)
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


_PAINT_DIALOG_QSS = """
QDialog { background-color: #1a1a1c; }

QPushButton#PaintTool {
    background-color: #2a2a30;
    color: #ffffff;
    border: 1px solid #4a4a52;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}
QPushButton#PaintTool:hover {
    background-color: #36363c;
    border-color: #5a5a62;
}
QPushButton#PaintTool:checked {
    background-color: #378ADD;
    border-color: #378ADD;
    color: #ffffff;
}

QPushButton#BubbleBtn {
    background-color: #5DCAA5;
    color: #0a0a0b;
    border: none;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 700;
}
QPushButton#BubbleBtn:hover {
    background-color: #73d6b3;
}

QDialogButtonBox QPushButton {
    min-width: 90px;
    padding: 8px 18px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 13px;
}
QDialogButtonBox QPushButton[text="OK"],
QDialogButtonBox QPushButton:default {
    background-color: #378ADD;
    color: #ffffff;
    border: none;
}
QDialogButtonBox QPushButton:default:hover,
QDialogButtonBox QPushButton[text="OK"]:hover {
    background-color: #4a9bee;
}
QDialogButtonBox QPushButton:!default {
    background-color: #2a2a30;
    color: #ffffff;
    border: 1px solid #4a4a52;
}
QDialogButtonBox QPushButton:!default:hover {
    background-color: #36363c;
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
        self._current_points: list[QPointF] = []  # while drawing (widget px)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    # ------------- tool / pen config -------------

    def tool(self) -> str:
        return self._tool

    def set_tool(self, tool: str) -> None:
        if tool not in ("off", "pen", "eraser"):
            tool = "off"
        self._tool = tool
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, tool == "off"
        )
        cursor = (
            Qt.CursorShape.CrossCursor
            if tool in ("pen", "eraser")
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
            color = QColor(self._pen_color)
            color.setAlpha(self._pen_opacity)
            pen = QPen(color, self._pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            if len(self._current_points) == 1:
                painter.drawPoint(self._current_points[0])
            else:
                painter.drawPolyline(self._current_points)

    @staticmethod
    def _paint_stroke(painter: QPainter, stroke: Stroke, w: int, h: int) -> None:
        color = QColor(*stroke.color)
        color.setAlpha(stroke.opacity)
        pen = QPen(color, stroke.width_px)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        pts = [QPointF(p[0] * w, p[1] * h) for p in stroke.points]
        if len(pts) == 1:
            painter.drawPoint(pts[0])
        else:
            painter.drawPolyline(pts)

    # ------------- mouse interaction -------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._tool == "pen":
            self._current_points = [QPointF(pos)]
            self.update()
        elif self._tool == "eraser":
            self._try_erase_at(pos.x(), pos.y())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
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
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        self._current_points = []
        self.stroke_added.emit(stroke)
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
            if len(pts) == 1:
                x, y = pts[0]
                half = stroke_w // 2
                draw.ellipse(
                    [x - half, y - half, x + half, y + half], fill=color
                )
            elif len(pts) > 1:
                draw.line(pts, fill=color, width=stroke_w, joint="curve")
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


# ---------------------------------------------------------------------------
#  Paint-style dialog
# ---------------------------------------------------------------------------


# Preset palette — 8 common colors + custom picker
PALETTE_COLORS: list[tuple[int, int, int]] = [
    (229, 70, 70),     # red
    (255, 140, 40),    # orange
    (255, 210, 40),    # yellow
    (70, 200, 90),     # green
    (40, 120, 220),    # blue
    (150, 70, 220),    # purple
    (0, 0, 0),         # black
    (255, 255, 255),   # white
]


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
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("paint.title"))
        self.setModal(True)
        self._time_ms = int(time_ms)
        self._bubbles: list[SpeechBubble] = list(initial_bubbles or [])
        self._bubble_items: list[SpeechBubbleItem] = []

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

        self._build_ui(background_pixmap, initial_strokes)

    # ---------- ui ----------

    def _build_ui(self, bg: QPixmap, initial_strokes: list[Stroke]) -> None:
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

        toolbar.addWidget(self.pen_btn)
        toolbar.addWidget(self.eraser_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.bubble_btn)
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

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._bubble_items and self._bubbles:
            self._spawn_initial_bubbles()

    def _make_palette_button(self, rgb: tuple[int, int, int]) -> QPushButton:
        btn = QPushButton()
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
            f"border: 2px solid #cccccc; border-radius: 4px; }}"
            f"QPushButton:hover {{ border-color: #333333; }}"
        )
        btn.clicked.connect(lambda: self._pick_palette_color(rgb))
        return btn

    def _highlight_selected_palette(self) -> None:
        sel = (
            self._pen_color.red(),
            self._pen_color.green(),
            self._pen_color.blue(),
        )
        for btn, rgb in zip(self._palette_btns, PALETTE_COLORS):
            if rgb == sel:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
                    f"border: 3px solid #0067c0; border-radius: 4px; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
                    f"border: 2px solid #cccccc; border-radius: 4px; }}"
                    f"QPushButton:hover {{ border-color: #333333; }}"
                )

    # ---------- tool actions ----------

    def _set_tool(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        self.pen_btn.setChecked(tool == "pen")
        self.eraser_btn.setChecked(tool == "eraser")

    def _clear_all(self) -> None:
        self.canvas.clear_strokes_direct()

    def _pick_palette_color(self, rgb: tuple[int, int, int]) -> None:
        self._pen_color = QColor(*rgb)
        self.canvas.set_pen_color(self._pen_color)
        self._highlight_selected_palette()
        self._set_tool("pen")

    def _pick_custom_color(self) -> None:
        color = QColorDialog.getColor(self._pen_color, self, tr("paint.btn.custom_color"))
        if color.isValid():
            self._pen_color = color
            self.canvas.set_pen_color(color)
            self._highlight_selected_palette()

    def _on_width_changed(self, value: int) -> None:
        self._pen_width = float(value)
        self.canvas.set_pen_width(self._pen_width)

    def _on_opacity_changed(self, value: int) -> None:
        self._pen_opacity = int(value * 255 / 100)
        self.canvas.set_pen_opacity(self._pen_opacity)

    def _on_stroke_added(self, stroke: Stroke) -> None:
        # Override the default start_ms so all dialog strokes stamp to the
        # moment the dialog was opened.
        stroke.start_ms = self._time_ms
        self.canvas.add_stroke_direct(stroke)

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

    def _add_bubble(self) -> None:
        bubble = SpeechBubble(
            x_norm=0.15, y_norm=0.15,
            width_norm=0.35, height_norm=0.22,
            text="",
            start_ms=self._time_ms,
            tail="left",
        )
        self._bubbles.append(bubble)
        item = SpeechBubbleItem(bubble, self.canvas)
        item.sync_to_parent()
        item.show()
        item.raise_()
        item.moved.connect(lambda it=item: it.sync_to_bubble())
        item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
        self._bubble_items.append(item)

    def _remove_bubble(self, bubble: "SpeechBubble", item: "SpeechBubbleItem") -> None:
        if bubble in self._bubbles:
            self._bubbles.remove(bubble)
        if item in self._bubble_items:
            self._bubble_items.remove(item)
        item.deleteLater()

    def _spawn_initial_bubbles(self) -> None:
        for bubble in self._bubbles:
            item = SpeechBubbleItem(bubble, self.canvas)
            item.sync_to_parent()
            item.show()
            item.raise_()
            item.moved.connect(lambda it=item: it.sync_to_bubble())
            item.deleted.connect(lambda it=item, b=bubble: self._remove_bubble(b, it))
            self._bubble_items.append(item)

    def result_strokes(self) -> list[Stroke]:
        return self.canvas.embedded_strokes()

    def result_bubbles(self) -> list["SpeechBubble"]:
        return list(self._bubbles)


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
            "QPushButton { background: #378ADD; color: white; border: none; "
            "border-radius: 9px; font-size: 10px; font-weight: 700; }"
            "QPushButton:hover { background: #4a9bee; }"
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
