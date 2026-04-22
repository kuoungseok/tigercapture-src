from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
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
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr


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
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("paint.title"))
        self.setModal(True)
        self._time_ms = int(time_ms)

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

        toolbar.addWidget(self.pen_btn)
        toolbar.addWidget(self.eraser_btn)
        toolbar.addWidget(self.clear_btn)
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

    def result_strokes(self) -> list[Stroke]:
        return self.canvas.embedded_strokes()
