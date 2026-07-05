from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.i18n import tr
from app.style import COLOR_BORDER_DEFAULT, COLOR_TEXT_TERTIARY

__all__ = [
    "ScopesPanel",
    "_LumaDial",
    "_HueCurveWidget",
    "_ColorWheelWidget",
    "parse_cube_lut",
    "apply_lut",
]

# ---------------------------------------------------------------------------
#  3D LUT support (.cube format)
# ---------------------------------------------------------------------------

def parse_cube_lut(path: str):
    """Parse an Adobe .cube 3D LUT file.

    Returns a numpy array of shape ``(size, size, size, 3)`` float32 on
    success, or ``None`` if the file is not a valid 3D LUT."""
    import numpy as np
    size = None
    data = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if line.startswith("LUT_3D_SIZE"):
                try:
                    size = int(line.split()[-1])
                except (ValueError, IndexError):
                    pass
            elif (
                line
                and not line.startswith("#")
                and not line.startswith("TITLE")
                and not line.startswith("DOMAIN")
                and not line.startswith("LUT")
            ):
                parts = line.split()
                if len(parts) == 3:
                    try:
                        data.append([float(p) for p in parts])
                    except ValueError:
                        pass
    if size is None or len(data) < size ** 3:
        return None
    arr = np.array(data[: size ** 3], dtype=np.float32).reshape(size, size, size, 3)
    return arr


def apply_lut(rgb_u8, lut, strength: float = 1.0):
    """Apply a 3D LUT to an RGB uint8 image using trilinear interpolation.

    Parameters
    ----------
    rgb_u8 : np.ndarray, shape (H, W, 3), dtype uint8
    lut    : np.ndarray, shape (S, S, S, 3), dtype float32  ??values 0..1
    strength : float 0..1 ??blend factor between original and graded

    Returns uint8 (H, W, 3) array.
    """
    import numpy as np
    size = lut.shape[0]
    scale = (size - 1) / 255.0
    r = rgb_u8[:, :, 0].astype(np.float32) * scale
    g = rgb_u8[:, :, 1].astype(np.float32) * scale
    b = rgb_u8[:, :, 2].astype(np.float32) * scale
    r0 = np.clip(r.astype(np.int32), 0, size - 2)
    g0 = np.clip(g.astype(np.int32), 0, size - 2)
    b0 = np.clip(b.astype(np.int32), 0, size - 2)
    rf = r - r0
    gf = g - g0
    bf = b - b0
    c000 = lut[b0, g0, r0]
    c001 = lut[b0, g0, r0 + 1]
    c010 = lut[b0, g0 + 1, r0]
    c011 = lut[b0, g0 + 1, r0 + 1]
    c100 = lut[b0 + 1, g0, r0]
    c101 = lut[b0 + 1, g0, r0 + 1]
    c110 = lut[b0 + 1, g0 + 1, r0]
    c111 = lut[b0 + 1, g0 + 1, r0 + 1]
    rf = rf[:, :, np.newaxis]
    gf = gf[:, :, np.newaxis]
    bf = bf[:, :, np.newaxis]
    result = (
        c000 * (1 - rf) * (1 - gf) * (1 - bf)
        + c001 * rf * (1 - gf) * (1 - bf)
        + c010 * (1 - rf) * gf * (1 - bf)
        + c011 * rf * gf * (1 - bf)
        + c100 * (1 - rf) * (1 - gf) * bf
        + c101 * rf * (1 - gf) * bf
        + c110 * (1 - rf) * gf * bf
        + c111 * rf * gf * bf
    )
    result = np.clip(result * 255, 0, 255).astype(np.uint8)
    if strength < 1.0:
        result = (rgb_u8 * (1.0 - strength) + result * strength).astype(np.uint8)
    return result


class ScopesPanel(QWidget):
    """DaVinci-style scopes panel ??dropdown of Histogram / Parade /
    Waveform / Vectorscope. Subscribes to the player's frame_ready
    signal and re-renders the active scope from the latest frame."""

    SCOPE_W = 360
    SCOPE_H = 220

    def __init__(self, player, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player = player
        self._latest_rgb = None
        self._kind = "histogram"
        self.setFixedHeight(self.SCOPE_H + 38)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 6, 8, 6)
        outer.setSpacing(4)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        title = QLabel(tr("veditor.scopes.title"))
        title.setStyleSheet(
            f"color: {COLOR_TEXT_TERTIARY}; font-size: 11px; font-weight: 600;"
        )
        head.addWidget(title)
        head.addStretch(1)
        from PySide6.QtWidgets import QComboBox
        self._kind_combo = QComboBox()
        for kid, key in (
            ("histogram",   "veditor.scopes.histogram"),
            ("parade",      "veditor.scopes.parade"),
            ("waveform",    "veditor.scopes.waveform"),
            ("vectorscope", "veditor.scopes.vectorscope"),
        ):
            self._kind_combo.addItem(tr(key), userData=kid)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        head.addWidget(self._kind_combo)
        outer.addLayout(head)

        self._image_label = QLabel()
        self._image_label.setFixedSize(self.SCOPE_W, self.SCOPE_H)
        self._image_label.setStyleSheet(
            f"background-color: #0a0a0e; border: 1px solid {COLOR_BORDER_DEFAULT};"
        )
        outer.addWidget(self._image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Player frame stream ??recompute current scope.
        self._player.frame_ready.connect(self._on_frame_ready)

    def _on_kind_changed(self) -> None:
        self._kind = self._kind_combo.currentData() or "histogram"
        # Re-render with the cached frame, if any.
        if self._latest_rgb is not None:
            self._render_now()

    def _on_frame_ready(self, qimg) -> None:
        """Cache the RGB array from the player and refresh the scope.
        We pull pixel bytes via QImage's bits() ??fast enough at 1080p
        for the modest scope canvas."""
        try:
            import numpy as np
            # Force RGB888 layout so bits() is plain RGB bytes.
            img = qimg.convertToFormat(qimg.Format.Format_RGB888)
            w, h = img.width(), img.height()
            ptr = img.constBits()
            arr = np.frombuffer(ptr, dtype=np.uint8, count=w * h * 3)
            arr = arr.reshape((h, w, 3))
            self._latest_rgb = arr.copy()      # decouple from Qt buffer
            self._render_now()
        except Exception:
            pass

    def _render_now(self) -> None:
        if self._latest_rgb is None:
            return
        from app.color_scopes import render_scope
        out = render_scope(self._kind, self._latest_rgb,
                           self.SCOPE_W, self.SCOPE_H)
        h, w = out.shape[:2]
        from PySide6.QtGui import QImage as _QI, QPixmap as _QP
        qimg = _QI(out.data, w, h, w * 3, _QI.Format.Format_RGB888).copy()
        self._image_label.setPixmap(_QP.fromImage(qimg))


class _LumaDial(QWidget):
    """Thin horizontal drag control for per-region luma adjustment.
    Maps drag position to -100..100 range."""
    value_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0   # -100..100
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_val = 0
        self.setFixedHeight(16)
        self.setMinimumWidth(80)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip("Drag to adjust luma (double-click to reset)")

    def set_value(self, v, *, emit=True):
        v = max(-100, min(100, int(v)))
        if v == self._value:
            return
        self._value = v
        self.update()
        if emit:
            self.value_changed.emit(v)

    def value(self):
        return self._value

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = e.position().x()
            self._drag_start_val = self._value

    def mouseMoveEvent(self, e):
        if self._dragging:
            dx = e.position().x() - self._drag_start_x
            new_val = int(self._drag_start_val + dx * 1.5)
            self.set_value(new_val)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def mouseDoubleClickEvent(self, e):
        self.set_value(0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Background track
        p.fillRect(0, 0, w, h, QColor(20, 20, 28))

        # Filled portion (from center)
        cx = w // 2
        fill_x = int(cx + self._value / 100.0 * (w // 2 - 4))
        if fill_x > cx:
            p.fillRect(cx, 2, fill_x - cx, h - 4, QColor(80, 140, 200, 160))
        elif fill_x < cx:
            p.fillRect(fill_x, 2, cx - fill_x, h - 4, QColor(80, 140, 200, 160))

        # Center line
        p.setPen(QPen(QColor(60, 60, 80), 1))
        p.drawLine(cx, 1, cx, h - 2)

        # Indicator dot
        ind_x = int(cx + self._value / 100.0 * (cx - 4))
        p.setPen(QPen(QColor(0, 0, 0, 80), 1))
        p.setBrush(QColor(200, 200, 220))
        p.drawEllipse(ind_x - 4, h // 2 - 4, 8, 8)
        p.end()


class _HueCurveWidget(QWidget):
    """DaVinci-style Hue-vs-Hue curve editor.

    X axis: input hue 0..360吏?(background painted as a rainbow strip).
    Y axis: hue rotation -180..+180吏?(centre line = no change).

    Default control points cover the six primary hues (R/Y/G/C/B/M)
    with delta = 0; users drag a point up/down to rotate that hue.
    Double-click adds a point, right-click on a point removes it.
    Emits ``points_changed(list)`` whenever the curve mutates.
    """

    points_changed = Signal(list)

    DEFAULT_HUES = [0.0, 60.0, 120.0, 180.0, 240.0, 300.0]
    HANDLE_R = 4
    GRAB_PX = 9
    HEIGHT = 108
    MAX_WIDTH = 480

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(self.HEIGHT)
        self.setMaximumHeight(self.HEIGHT)
        self.setMinimumWidth(280)
        self.setMaximumWidth(self.MAX_WIDTH)
        self.setMouseTracking(True)
        # Each point is (input_hue 0..360, delta_hue -180..180).
        self._points: list[list[float]] = [
            [h, 0.0] for h in self.DEFAULT_HUES
        ]
        self._dragging_idx: int | None = None
        self._selected_idx: int | None = None

    # ---- public ----

    def points(self) -> list[tuple[float, float]]:
        return [(p[0], p[1]) for p in self._points]

    def set_points(self, pts: list[tuple[float, float]]) -> None:
        if pts:
            self._points = [[float(h), float(d)] for h, d in pts]
        else:
            self._points = [[h, 0.0] for h in self.DEFAULT_HUES]
        self._points.sort(key=lambda p: p[0])
        self.update()

    def reset(self) -> None:
        self._points = [[h, 0.0] for h in self.DEFAULT_HUES]
        self._dragging_idx = None
        self._selected_idx = None
        self.update()
        self.points_changed.emit(self.points())

    # ---- coords ----

    def _hue_to_x(self, h: float) -> float:
        w = self.width() - 12
        return 6 + (h / 360.0) * w

    def _x_to_hue(self, x: float) -> float:
        w = self.width() - 12
        return max(0.0, min(360.0, (x - 6) / w * 360.0))

    def _delta_to_y(self, d: float) -> float:
        h = self.height() - 12
        # delta=0 ??centre; +180 ??top; -180 ??bottom
        return 6 + h * (1.0 - (d + 180.0) / 360.0)

    def _y_to_delta(self, y: float) -> float:
        h = self.height() - 12
        return max(-180.0, min(180.0,
                               (1.0 - (y - 6) / h) * 360.0 - 180.0))

    def _point_at(self, pos) -> int | None:
        from math import hypot
        for i, (hue, dlt) in enumerate(self._points):
            x = self._hue_to_x(hue)
            y = self._delta_to_y(dlt)
            if hypot(pos.x() - x, pos.y() - y) <= self.GRAB_PX:
                return i
        return None

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._point_at(event.position().toPoint())
            if idx is not None:
                self._dragging_idx = idx
                self._selected_idx = idx
                self.update()
            else:
                # Click on empty space inside the curve area = add point.
                p = event.position().toPoint()
                hue = self._x_to_hue(p.x())
                dlt = self._y_to_delta(p.y())
                self._points.append([hue, dlt])
                self._points.sort(key=lambda q: q[0])
                self._dragging_idx = next(
                    (i for i, q in enumerate(self._points)
                     if abs(q[0] - hue) < 1e-3 and abs(q[1] - dlt) < 1e-3),
                    None,
                )
                self._selected_idx = self._dragging_idx
                self.update()
                self.points_changed.emit(self.points())
        elif event.button() == Qt.MouseButton.RightButton:
            idx = self._point_at(event.position().toPoint())
            # Don't allow deleting all six default points; require ??.
            if idx is not None and len(self._points) > 2:
                del self._points[idx]
                self._dragging_idx = None
                self._selected_idx = None
                self.update()
                self.points_changed.emit(self.points())

    def mouseMoveEvent(self, event) -> None:
        if self._dragging_idx is None:
            return
        p = event.position().toPoint()
        hue = self._x_to_hue(p.x())
        dlt = self._y_to_delta(p.y())
        self._points[self._dragging_idx][0] = hue
        self._points[self._dragging_idx][1] = dlt
        # Re-sort + track index.
        sel = self._points[self._dragging_idx]
        self._points.sort(key=lambda q: q[0])
        self._dragging_idx = self._points.index(sel)
        self._selected_idx = self._dragging_idx
        self.update()
        self.points_changed.emit(self.points())

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_idx = None

    # ---- paint ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QLinearGradient, QBrush
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Background: hue rainbow gradient covering the X axis.
        grad = QLinearGradient(6, 0, self.width() - 6, 0)
        for stop, rgb in (
            (0.000, (255, 70,  70)),
            (0.166, (235, 210, 60)),
            (0.333, (110, 220, 70)),
            (0.500, (60,  180, 220)),
            (0.666, (130, 100, 235)),
            (0.833, (235, 90,  200)),
            (1.000, (255, 70,  70)),
        ):
            grad.setColorAt(stop, QColor(*rgb, 110))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect().adjusted(2, 2, -2, -2), 4, 4)

        # Centre baseline (delta = 0)
        cy = self._delta_to_y(0.0)
        painter.setPen(QPen(QColor(255, 255, 255, 80), 1, Qt.PenStyle.DashLine))
        painter.drawLine(6, int(cy), self.width() - 6, int(cy))

        # Curve ??connect points in order, with wrap from last to first.
        if len(self._points) >= 2:
            pen = QPen(QColor(255, 255, 255), 2)
            painter.setPen(pen)
            n = len(self._points)
            for i in range(n):
                a = self._points[i]
                b = self._points[(i + 1) % n]
                ax = self._hue_to_x(a[0])
                ay = self._delta_to_y(a[1])
                bx = self._hue_to_x(b[0])
                by = self._delta_to_y(b[1])
                # Wrap: don't draw a segment that crosses the seam if
                # the next point's hue is smaller (wraps around 360).
                if b[0] < a[0]:
                    continue
                painter.drawLine(int(ax), int(ay), int(bx), int(by))

        # Control points
        for i, (hue, dlt) in enumerate(self._points):
            x = self._hue_to_x(hue)
            y = self._delta_to_y(dlt)
            r = self.HANDLE_R + (1 if i == self._selected_idx else 0)
            painter.setPen(QPen(QColor(0, 0, 0, 200), 1))
            fill = QColor(255, 255, 255) if i == self._selected_idx else QColor(220, 220, 220)
            painter.setBrush(fill)
            painter.drawEllipse(int(x) - r, int(y) - r, r * 2, r * 2)

        # Outer border
        painter.setPen(QPen(QColor(0, 0, 0, 140), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 4, 4)


class _ColorWheelWidget(QWidget):
    """DaVinci-style chromaticity wheel with a draggable indicator.

    Emits ``value_changed(x, y)`` in ``-100..100`` while dragging.
    Axis convention matches :func:`app.color_grading._wheel_to_rgb_offset`:

        +x ??red / orange (warm)        -x ??cyan / blue  (cool)
        +y ??magenta                    -y ??green

    Visual treatment: smooth 12-stop conical hue ring with a subtle
    outer glow, a feathered radial centre fade for the neutral zone,
    two faint guide rings at 50 % and 100 % saturation, a crosshair,
    and a high-contrast white indicator with an inner colour dot.
    Bottom label sits directly under the wheel, with the live ``x, y``
    readout in a small chip just above the label.
    """

    value_changed = Signal(int, int)

    SIZE = 132              # widget side length (px) ??DaVinci-leaning size
    LABEL_H = 16
    READOUT_H = 13
    INDICATOR_R = 7

    def __init__(self, label: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = label
        self._x = 0           # -100..100
        self._y = 0
        self._dragging = False
        # Total height = wheel + readout + label + small gaps.
        self.setFixedSize(self.SIZE, self.SIZE + self.READOUT_H + self.LABEL_H + 4)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def value(self) -> tuple[int, int]:
        return self._x, self._y

    def set_value(self, x: int, y: int, *, emit: bool = True) -> None:
        x = max(-100, min(100, int(x)))
        y = max(-100, min(100, int(y)))
        if x == self._x and y == self._y:
            return
        self._x = x
        self._y = y
        self.update()
        if emit:
            self.value_changed.emit(self._x, self._y)

    # ---- geometry helpers ----

    def _wheel_rect(self) -> QRect:
        # Leave room at the bottom for readout + label.
        return QRect(3, 3, self.SIZE - 6, self.SIZE - 6)

    def _wheel_center(self) -> QPoint:
        r = self._wheel_rect()
        return QPoint(r.left() + r.width() // 2,
                      r.top() + r.height() // 2)

    def _wheel_radius(self) -> float:
        r = self._wheel_rect()
        return min(r.width(), r.height()) / 2.0 - 2.0

    def _value_to_pos(self) -> QPoint:
        c = self._wheel_center()
        rad = self._wheel_radius()
        x = c.x() + self._x / 100.0 * rad
        y = c.y() + self._y / 100.0 * rad
        return QPoint(int(x), int(y))

    def _pos_to_value(self, p: QPoint) -> tuple[int, int]:
        c = self._wheel_center()
        rad = self._wheel_radius()
        if rad <= 0:
            return 0, 0
        dx = (p.x() - c.x()) / rad
        dy = (p.y() - c.y()) / rad
        import math
        d = math.hypot(dx, dy)
        if d > 1.0:
            dx /= d
            dy /= d
        x = int(round(max(-1.0, min(1.0, dx)) * 100))
        y = int(round(max(-1.0, min(1.0, dy)) * 100))
        return x, y

    # ---- mouse ----

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)
        elif event.button() == Qt.MouseButton.RightButton:
            self.set_value(0, 0)

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            x, y = self._pos_to_value(event.pos())
            self.set_value(x, y)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def mouseDoubleClickEvent(self, _event) -> None:
        self.set_value(0, 0)

    # ---- painting ----

    def paintEvent(self, _event) -> None:
        from PySide6.QtGui import QConicalGradient, QRadialGradient
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        wheel = self._wheel_rect()
        cx = wheel.center().x()
        cy = wheel.center().y()
        rad = self._wheel_radius()

        # ---- subtle outer glow (drawn first, behind everything) ----
        glow = QRadialGradient(QPoint(cx, cy), rad + 6)
        glow.setColorAt(0.85, QColor(0, 0, 0, 0))
        glow.setColorAt(1.00, QColor(0, 0, 0, 90))
        painter.setBrush(glow)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(cx, cy), int(rad + 5), int(rad + 5))

        # ---- conical hue ring ----
        # QConicalGradient progresses counter-clockwise from the 3 o'clock
        # position. To match the value convention (+x=warm red,
        # -y=green at the screen top, -x=cyan, +y=magenta at the screen
        # bottom), place red at t=0, green at t=0.25, cyan at 0.5,
        # magenta at 0.75.
        grad = QConicalGradient(QPoint(cx, cy), 0.0)
        stops = [
            (0.000, (245,  70,  70)),    # red       ??3 o'clock, +x
            (0.083, (245, 150,  60)),    # orange
            (0.166, (235, 210,  60)),    # yellow
            (0.250, (110, 220,  70)),    # GREEN     ??12 o'clock, -y
            (0.333, ( 60, 220, 140)),    # green-cyan
            (0.416, ( 50, 210, 200)),    # cyan-green
            (0.500, ( 60, 180, 220)),    # CYAN      ??9 o'clock, -x
            (0.583, ( 80, 140, 235)),    # blue
            (0.666, (130, 100, 235)),    # blue-violet
            (0.750, (235,  90, 200)),    # MAGENTA   ??6 o'clock, +y
            (0.833, (240, 100, 150)),    # pink
            (0.916, (245,  90, 110)),    # warm pink
            (1.000, (245,  70,  70)),
        ]
        for stop, (r, g, b) in stops:
            grad.setColorAt(stop, QColor(r, g, b))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(wheel)

        # ---- feathered radial fade toward neutral grey at centre ----
        # Two-stop fade gives the wheel that "punched" centre look
        # without obliterating chromatic information at the edge.
        radial = QRadialGradient(QPoint(cx, cy), rad)
        radial.setColorAt(0.00, QColor(232, 232, 234, 245))
        radial.setColorAt(0.35, QColor(232, 232, 234, 130))
        radial.setColorAt(0.65, QColor(232, 232, 234, 0))
        painter.setBrush(radial)
        painter.drawEllipse(wheel)

        # ---- guide rings at 50% and 100% saturation ----
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawEllipse(QPoint(cx, cy), int(rad * 0.5), int(rad * 0.5))
        # 100% ring (rim) ??slightly darker to read as the boundary.
        painter.setPen(QPen(QColor(0, 0, 0, 130), 1))
        painter.drawEllipse(wheel)

        # ---- crosshair ----
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
        painter.drawLine(cx - 4, cy, cx + 4, cy)
        painter.drawLine(cx, cy - 4, cx, cy + 4)

        # ---- indicator ----
        # White ring + coloured inner dot. The dot's hue matches the
        # current (x, y) direction so the user can see "what colour
        # am I pulling toward". Saturation = distance from centre.
        ind = self._value_to_pos()
        # Outer ring (with subtle drop shadow).
        painter.setPen(QPen(QColor(0, 0, 0, 110), 1))
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(ind, self.INDICATOR_R, self.INDICATOR_R)
        # Inner coloured dot ??sample the wheel colour at this position.
        inner_color = self._sample_wheel_color()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(inner_color)
        painter.drawEllipse(ind, self.INDICATOR_R - 3, self.INDICATOR_R - 3)

        # ---- numeric readout ----
        readout_text = f"{self._x:+d}, {self._y:+d}"
        painter.setPen(QPen(QColor("#9CA0AC")))
        f = QFont(painter.font())
        f.setPointSize(8)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE - 3, self.width(), self.READOUT_H),
            Qt.AlignmentFlag.AlignCenter,
            readout_text,
        )

        # ---- bottom label ----
        painter.setPen(QPen(QColor("#D6D6DC")))
        f.setPointSize(9)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(
            QRect(0, self.SIZE + self.READOUT_H, self.width(), self.LABEL_H),
            Qt.AlignmentFlag.AlignCenter,
            self._label,
        )

    def _sample_wheel_color(self) -> QColor:
        """Approximate the wheel hue at the current (x, y). Used as the
        indicator's inner-dot colour so the user gets visual feedback
        on which way they're pulling. Uses the same 13-stop hue ring
        the gradient paints, with the screen-Y flip baked into the
        atan2 ??t conversion (Qt's CCW gradient on a Y-down canvas)."""
        import math
        if self._x == 0 and self._y == 0:
            return QColor(220, 220, 220)
        # Negate the angle: Qt paints the gradient CCW visually, so a
        # point with screen-Y = +y_data lands further around the wheel
        # in the "going CW visually" direction. The negation aligns the
        # sampled colour with the painted gradient.
        ang = math.atan2(self._y, self._x)
        t = (-ang / (2 * math.pi)) % 1.0
        stops = [
            (0.000, (245,  70,  70)),
            (0.083, (245, 150,  60)),
            (0.166, (235, 210,  60)),
            (0.250, (110, 220,  70)),
            (0.333, ( 60, 220, 140)),
            (0.416, ( 50, 210, 200)),
            (0.500, ( 60, 180, 220)),
            (0.583, ( 80, 140, 235)),
            (0.666, (130, 100, 235)),
            (0.750, (235,  90, 200)),
            (0.833, (240, 100, 150)),
            (0.916, (245,  90, 110)),
            (1.000, (245,  70,  70)),
        ]
        for i in range(len(stops) - 1):
            a, ca = stops[i]
            b, cb = stops[i + 1]
            if a <= t <= b:
                u = (t - a) / max(1e-6, b - a)
                r = int(ca[0] + (cb[0] - ca[0]) * u)
                g = int(ca[1] + (cb[1] - ca[1]) * u)
                bl = int(ca[2] + (cb[2] - ca[2]) * u)
                # Saturation = distance from centre.
                d = min(1.0, math.hypot(self._x, self._y) / 100.0)
                rr = int(220 + (r - 220) * d)
                gg = int(220 + (g - 220) * d)
                bb = int(220 + (bl - 220) * d)
                return QColor(rr, gg, bb)
        return QColor(220, 220, 220)


# Module-level: which clip type currently owns the marching-ants selection.
# "video" | "audio" | ""  ??updated by click handlers so only ONE type shows ants.
_ANTS_OWNER: str = ""


