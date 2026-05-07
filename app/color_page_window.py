"""DaVinci Resolve-style Color Page — faithful recreation of the
'Primaries - Color Wheels' panel from ref.png.

Layout (top→bottom):
  ① Toolbar  — page icons  |  "Primaries - Color Wheels"  |  Temp/Tint/Cont/Pivot/MD
  ② Wheels   — 4 large wheels  (Lift | Gamma | Gain | Offset)
               each: label ↺  /  wheel  /  R G B Y readouts
  ③ Bottom   — Col Boost · Shadow · HiLight  ‖  Sat · Hue · L.Mix
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QConicalGradient, QFont, QLinearGradient,
    QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QSlider, QSplitter,
    QVBoxLayout, QWidget,
)

# ── Design tokens (DaVinci dark) ─────────────────────────────────────────────
_BG         = "#17171c"   # global background
_BG_PANEL   = "#1d1d24"   # wheel panel
_BG_SECTION = "#1d1d24"   # per-wheel box (unified with panel tone)
_BG_BAR     = "#141418"   # top / bottom bars
_BORDER     = "#2c2c38"   # separator / panel border
_LABEL      = "#9090aa"   # wheel labels (slightly brighter for readability)
_TITLE      = "#c8c8d8"   # panel title text
_TEXT       = "#d4d4e0"   # general text
_VAL_BG     = "#0d0d14"   # readout spinbox bg
_ACCENT     = "#D85A30"   # Tiger Orange — matches global COLOR_ACCENT

_TINY_FONT = "font-size: 10px; font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
_SBOX_QSS = (
    f"QDoubleSpinBox {{ background: {_VAL_BG}; color: {_TEXT}; "
    f"border: 1px solid {_BORDER}; border-radius: 2px; {_TINY_FONT} "
    "padding: 0 2px; min-width: 44px; max-width: 52px; }}"
    "QDoubleSpinBox:focus { border-color: " + _ACCENT + "; }"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0; }"
)
_PARAM_QSS = (
    f"QDoubleSpinBox {{ background: {_VAL_BG}; color: {_TEXT}; "
    f"border: 1px solid {_BORDER}; border-radius: 2px; {_TINY_FONT} "
    "padding: 0 3px; min-width: 48px; max-width: 60px; }}"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0; }"
)


# ── Colour Wheel ──────────────────────────────────────────────────────────────

class _Wheel(QWidget):
    """180×180 colour-chromaticity wheel — draggable indicator.
    The outer luma arc is also interactive: drag it to adjust luminosity (-100..100).
    """
    value_changed = Signal(int, int)   # x, y  in -100..100
    luma_changed  = Signal(int)        # luma  in -100..100

    SIZE = 180
    IND  = 8   # indicator radius

    def __init__(self, parent=None):
        super().__init__(parent)
        self._x = self._y = 0
        self._luma = 0          # -100..100, maps to region_l
        self._drag = False
        self._luma_drag = False # dragging the outer luma arc
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.CrossCursor)
        # Prevent any parent QSS clip from bleeding into this widget's painting
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    # public ─────────────────────────────────────────────────────────────────
    def value(self): return self._x, self._y
    def luma(self): return self._luma

    def set_value(self, x, y, *, emit=True):
        x, y = max(-100, min(100, int(x))), max(-100, min(100, int(y)))
        if x == self._x and y == self._y: return
        self._x, self._y = x, y
        self.update()
        if emit: self.value_changed.emit(x, y)

    def set_luma(self, v, *, emit=True):
        v = max(-100, min(100, int(v)))
        if v == self._luma: return
        self._luma = v
        self.update()
        if emit: self.luma_changed.emit(v)

    # geometry — use ACTUAL widget dimensions, not SIZE constant,
    # so the wheel renders correctly even when setFixedSize() overrides SIZE.
    def _cx(self): return self.width() // 2
    def _cy(self): return self.height() // 2
    def _rad(self): return min(self.width(), self.height()) // 2 - 6

    def _v2p(self):
        r = self._rad()
        return QPoint(int(self._cx() + self._x / 100 * r),
                      int(self._cy() + self._y / 100 * r))

    def _p2v(self, p):
        r = self._rad()
        if r <= 0: return 0, 0
        dx = (p.x() - self._cx()) / r
        dy = (p.y() - self._cy()) / r
        d  = math.hypot(dx, dy)
        if d > 1.0: dx, dy = dx / d, dy / d
        return int(dx * 100), int(dy * 100)

    # events ──────────────────────────────────────────────────────────────────
    def _in_luma_arc(self, p) -> bool:
        """Return True if point p is in the outer luma arc ring."""
        cx, cy = self._cx(), self._cy()
        outer_r = min(self.width(), self.height()) // 2 - 3
        luma_in = outer_r - max(8, outer_r // 9) - 2  # inside edge of luma ring
        dx, dy = p.x() - cx, p.y() - cy
        d = math.hypot(dx, dy)
        return luma_in <= d <= outer_r

    def _p2luma(self, p) -> int:
        """Convert point on luma arc to -100..100 value.
        Top of arc = +100 (bright), bottom = -100 (dark)."""
        cx, cy = self._cx(), self._cy()
        dy = cy - p.y()   # positive = above center = brighter
        dx = p.x() - cx
        # Use vertical component primarily
        d = math.hypot(dx, dy)
        if d < 1:
            return 0
        angle = math.degrees(math.atan2(dy, dx))  # -180..180
        # Map angle to luma: 90° (top) = +100, -90° (bottom) = -100
        luma = int(angle / 90.0 * 100.0)
        return max(-100, min(100, luma))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._in_luma_arc(e.position().toPoint()):
                self._luma_drag = True
                self.set_luma(self._p2luma(e.position().toPoint()))
            else:
                self._drag = True
                x, y = self._p2v(e.position().toPoint())
                self.set_value(x, y)

    def mouseMoveEvent(self, e):
        if self._luma_drag:
            self.set_luma(self._p2luma(e.position().toPoint()))
        elif self._drag:
            x, y = self._p2v(e.position().toPoint())
            self.set_value(x, y)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = False
            self._luma_drag = False

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._in_luma_arc(e.position().toPoint()):
                self.set_luma(0)
            else:
                self.set_value(0, 0)

    # paint ───────────────────────────────────────────────────────────────────
    # ── colour stops (shared across paint passes) ─────────────────────────
    _HUE_STOPS = [
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

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(17, 17, 28))

        cx, cy = self._cx(), self._cy()
        outer_r = min(self.width(), self.height()) // 2 - 3

        # Radii for the three concentric rings:
        LUMA_W  = max(8,  outer_r // 9)   # luma arc ring width
        HUE_W   = max(6,  outer_r // 11)  # hue ring width
        BEVEL_W = 2
        luma_out = outer_r
        luma_in  = luma_out - LUMA_W
        hue_out  = luma_in  - BEVEL_W
        hue_in   = hue_out  - HUE_W
        inner_r  = hue_in   - BEVEL_W     # radius of the dark centre disc

        # ── 1. Outer dark bezel ───────────────────────────────────────────
        p.setBrush(QColor(12, 12, 18))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(cx, cy), luma_out, luma_out)

        # ── 2. Luma gradient arc (dark bottom → bright top, full circle) ──
        luma_grad = QConicalGradient(cx, cy, -90)   # top = bright
        luma_grad.setColorAt(0.0,  QColor(200, 200, 200))
        luma_grad.setColorAt(0.5,  QColor( 30,  30,  40))
        luma_grad.setColorAt(1.0,  QColor(200, 200, 200))
        p.setBrush(luma_grad)
        p.drawEllipse(QPoint(cx, cy), luma_out, luma_out)
        # Erase inner part → creates a ring
        p.setBrush(QColor(12, 12, 18))
        p.drawEllipse(QPoint(cx, cy), luma_in, luma_in)

        # ── 3. Thin dark separator between luma and hue ring ─────────────
        p.setBrush(QColor(8, 8, 14))
        p.drawEllipse(QPoint(cx, cy), hue_out, hue_out)

        # ── 4. Hue ring (rainbow) ─────────────────────────────────────────
        conic = QConicalGradient(cx, cy, 0)
        for pos, rgb in self._HUE_STOPS:
            conic.setColorAt(pos, QColor(*rgb))
        p.setBrush(conic)
        p.drawEllipse(QPoint(cx, cy), hue_out, hue_out)
        # Erase inner part → ring only
        p.setBrush(QColor(8, 8, 14))
        p.drawEllipse(QPoint(cx, cy), hue_in, hue_in)

        # ── 5. Dark centre disc ───────────────────────────────────────────
        center_grad = QRadialGradient(cx, cy, inner_r)
        center_grad.setColorAt(0.0, QColor(35, 35, 48))
        center_grad.setColorAt(1.0, QColor(20, 20, 30))
        p.setBrush(center_grad)
        p.drawEllipse(QPoint(cx, cy), inner_r, inner_r)

        # ── 5b. Luma arc indicator dot ────────────────────────────────────────
        luma_mid_r = (luma_out + luma_in) // 2
        luma_angle_rad = math.radians(self._luma / 100.0 * 90.0)
        lind_x = int(cx + luma_mid_r * math.cos(math.pi/2 + luma_angle_rad))
        lind_y = int(cy - luma_mid_r * math.sin(math.pi/2 + luma_angle_rad))
        brightness = max(20, min(235, 128 + self._luma * 107 // 100))
        p.setBrush(QColor(brightness, brightness, brightness))
        p.setPen(QPen(QColor(0, 0, 0, 120), 1))
        p.drawEllipse(QPoint(lind_x, lind_y), 5, 5)

        # ── 6. Crosshair ──────────────────────────────────────────────────
        hline = int(inner_r * 0.55)
        p.setPen(QPen(QColor(255, 255, 255, 45), 1))
        p.drawLine(cx - hline, cy, cx + hline, cy)
        p.drawLine(cx, cy - hline, cx, cy + hline)

        # ── 7. Indicator puck ─────────────────────────────────────────────
        vx = int(self._x / 100.0 * inner_r * 0.88) + cx
        vy = int(self._y / 100.0 * inner_r * 0.88) + cy
        ind = QPoint(vx, vy)

        # Outer white ring
        p.setPen(QPen(QColor(0, 0, 0, 80), 1))
        p.setBrush(QColor(240, 240, 240))
        p.drawEllipse(ind, self.IND, self.IND)

        # Inner sampled colour dot
        ang = math.atan2(self._y, self._x)
        t   = (-ang) / (2 * math.pi) % 1.0
        sat = math.hypot(self._x, self._y) / 100.0
        stops = self._HUE_STOPS
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]; t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                f  = (t - t0) / max(t1 - t0, 1e-9)
                rv = int(c0[0] + f * (c1[0] - c0[0]))
                gv = int(c0[1] + f * (c1[1] - c0[1]))
                bv = int(c0[2] + f * (c1[2] - c0[2]))
                rv = int(220 + (rv - 220) * sat)
                gv = int(220 + (gv - 220) * sat)
                bv = int(220 + (bv - 220) * sat)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(rv, gv, bv))
                p.drawEllipse(ind, self.IND - 2, self.IND - 2)
                break
        p.end()


# ── _WheelSection : label + wheel + 4 readouts ───────────────────────────────

def _spinbox(val=0.0, lo=-5.0, hi=5.0, step=0.01, decimals=2) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi); sb.setValue(val)
    sb.setSingleStep(step); sb.setDecimals(decimals)
    sb.setStyleSheet(_SBOX_QSS)
    sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
    sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return sb


class _WheelSection(QWidget):
    wheel_changed  = Signal(int, int)    # x, y
    luma_changed   = Signal(float)       # luma  (L readout)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._label = label
        self._busy  = False
        self.setObjectName("WheelSection")
        self.setStyleSheet(
            f"QWidget#WheelSection {{ background: {_BG_SECTION}; }}"
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)
        root.setSpacing(6)

        # header row: LABEL  ↺
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0,0,0,0); hdr.setSpacing(4)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet(
            f"color: {_LABEL}; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none; letter-spacing: 0.5px;"
        )
        hdr.addWidget(lbl); hdr.addStretch()
        rst = QPushButton("↺")
        rst.setFixedSize(20, 20)
        rst.setCursor(Qt.CursorShape.PointingHandCursor)
        rst.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {_LABEL}; "
            "border: none; font-size: 14px; padding: 0; }}"
            f"QPushButton:hover {{ color: {_TEXT}; }}"
        )
        rst.clicked.connect(self._reset)
        hdr.addWidget(rst)
        root.addLayout(hdr)

        # colour wheel
        self.wheel = _Wheel()
        self.wheel.value_changed.connect(self._on_wheel)
        root.addWidget(self.wheel, 0, Qt.AlignmentFlag.AlignHCenter)

        # 4 readouts: R  G  B  L
        readouts = QHBoxLayout()
        readouts.setSpacing(4); readouts.setContentsMargins(0,0,0,0)
        self._r = _spinbox(); self._g = _spinbox(); self._b = _spinbox()
        self._l = _spinbox(val=0.0, lo=-1.0, hi=1.0)
        for sb in (self._r, self._g, self._b, self._l):
            readouts.addWidget(sb)
        # small R G B L hints
        for sb, hint in zip((self._r, self._g, self._b, self._l),
                            ("R", "G", "B", "L")):
            sb.setToolTip(hint)
            sb.valueChanged.connect(self._on_readout)
        root.addLayout(readouts)

    def _on_wheel(self, x, y):
        self._busy = True
        # map x/y -100..100 to -1..1 for R/G/B display (approx)
        scale = 0.01
        self._r.setValue(round(x * scale, 2))
        self._b.setValue(round(y * scale, 2))
        self._busy = False
        self.wheel_changed.emit(x, y)

    def _on_readout(self):
        if self._busy: return
        self.luma_changed.emit(self._l.value())

    def _reset(self):
        self.wheel.set_value(0, 0)
        for sb in (self._r, self._g, self._b, self._l):
            sb.blockSignals(True); sb.setValue(0.0); sb.blockSignals(False)
        self.wheel_changed.emit(0, 0)

    def set_grade_values(self, x, y, luma=0.0):
        self._busy = True
        self.wheel.set_value(x, y, emit=False)
        self._r.setValue(round(x * 0.01, 2))
        self._b.setValue(round(y * 0.01, 2))
        self._l.setValue(round(luma * 0.01, 2))
        self._busy = False
        self.update()


# ── Slim horizontal slider with label+value ───────────────────────────────────

class _SlimSlider(QWidget):
    """Compact  LABEL ────── value  like DaVinci's bottom bar."""
    value_changed = Signal(float)

    def __init__(self, label: str, lo=-100, hi=100, default=0, parent=None):
        super().__init__(parent)
        row = QHBoxLayout(self); row.setContentsMargins(0,0,0,0); row.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFixedWidth(60)
        lbl.setStyleSheet(f"color: {_LABEL}; {_TINY_FONT} background:transparent; border:none;")
        row.addWidget(lbl)

        self._sl = QSlider(Qt.Orientation.Horizontal)
        self._sl.setRange(lo, hi); self._sl.setValue(default)
        self._sl.setStyleSheet(
            "QSlider::groove:horizontal { background:#2a2a38; height:3px; border-radius:1px; }"
            f"QSlider::handle:horizontal {{ background:{_ACCENT}; width:10px; height:10px; "
            "border-radius:5px; margin:-4px 0; }}"
            "QSlider::sub-page:horizontal { background:#4a5878; border-radius:1px; }"
        )
        row.addWidget(self._sl, 1)

        self._val = QLabel(f"{default:.2f}")
        self._val.setFixedWidth(38)
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val.setStyleSheet(f"color:{_TEXT}; {_TINY_FONT} background:transparent; border:none;")
        row.addWidget(self._val)

        self._sl.valueChanged.connect(self._changed)

    def _changed(self, v):
        self._val.setText(f"{v:.2f}")
        self.value_changed.emit(float(v))

    def set_value(self, v):
        self._sl.blockSignals(True)
        self._sl.setValue(int(v))
        self._val.setText(f"{v:.2f}")
        self._sl.blockSignals(False)


# ── Compact number field for top bar ─────────────────────────────────────────

def _param_field(label: str, val=0.0, lo=-10.0, hi=10.0, decimals=3):
    w = QWidget()
    row = QHBoxLayout(w); row.setContentsMargins(0,0,0,0); row.setSpacing(3)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color:{_LABEL}; {_TINY_FONT} background:transparent; border:none;")
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi); sb.setValue(val); sb.setDecimals(decimals)
    sb.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
    sb.setStyleSheet(_PARAM_QSS)
    sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    row.addWidget(lbl); row.addWidget(sb)
    return w, sb


# ── Scope display widget ──────────────────────────────────────────────────────

class _ScopeDisplayWidget(QWidget):
    """Renders a single video scope (waveform, vectorscope, parade, or
    histogram) from a live RGB frame using :func:`app.color_scopes.render_scope`.

    The widget paints the numpy array returned by ``render_scope`` directly
    onto its surface via QImage → QPixmap conversion so no extra copies are
    made inside Qt's paint path.
    """

    _KINDS = [
        ("Waveform",    "waveform"),
        ("Vectorscope", "vectorscope"),
        ("Parade",      "parade"),
        ("Histogram",   "histogram"),
    ]

    def __init__(self, kind: str = "waveform", parent=None):
        super().__init__(parent)
        self._kind = kind
        self._pixmap: "QPixmap | None" = None
        self.setMinimumSize(200, 130)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.setStyleSheet(f"background: #0a0a0e; border: 1px solid {_BORDER};")

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self._pixmap = None
        self.update()

    def update_frame(self, rgb) -> None:
        """Compute the scope for *rgb* and schedule a repaint."""
        if rgb is None:
            return
        try:
            from app.color_scopes import render_scope
            w = max(self.width(),  80)
            h = max(self.height(), 50)
            arr = render_scope(self._kind, rgb, w, h)
            from PySide6.QtGui import QImage
            h_px, w_px, _ = arr.shape
            img = QImage(arr.data, w_px, h_px, w_px * 3, QImage.Format.Format_RGB888)
            self._pixmap = QPixmap.fromImage(img.copy())
        except Exception:
            self._pixmap = None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(10, 10, 14))
        if self._pixmap is not None:
            p.drawPixmap(self.rect(), self._pixmap, self._pixmap.rect())
        p.end()


# ── Main ColorPageWindow ──────────────────────────────────────────────────────

class ColorPageWindow(QWidget):
    """Full-screen color grading page — DaVinci Resolve 'Primaries - Color Wheels' style."""

    grade_changed = Signal(object)   # emits ColorGrade

    def __init__(self, editor=None, parent=None):
        super().__init__(parent)
        self._editor = editor
        self.setWindowTitle("TigerCapture — Color")
        self.resize(1440, 820)
        self.setStyleSheet(f"background: {_BG};")
        self._build_ui()

    # ── build ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar(), 0)

        # Middle row: scopes panel (left) + color wheels (centre/right)
        mid = QWidget()
        mid_row = QHBoxLayout(mid)
        mid_row.setContentsMargins(0, 0, 0, 0)
        mid_row.setSpacing(0)
        mid_row.addWidget(self._build_scopes_panel(), 0)

        # Thin vertical divider
        div = QFrame()
        div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet(f"background: {_BORDER}; border: none;")
        mid_row.addWidget(div)

        mid_row.addWidget(self._build_wheels_area(), 1)
        root.addWidget(mid, 1)

        root.addWidget(self._build_bottom_bar(), 0)
        root.addWidget(self._build_node_strip(), 0)

    # ── toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(36)
        bar.setStyleSheet(
            f"background: {_BG_BAR}; border-bottom: 1px solid {_BORDER};"
            "font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 0, 10, 0); row.setSpacing(8)

        # Back button — uses design-token surface colors
        back = QPushButton("← 편집")
        back.setStyleSheet(
            f"QPushButton {{ background: #282832; color: {_TEXT}; border: 1px solid #2c2c38; "
            "border-radius: 4px; padding: 4px 10px; font-size: 11px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: #32323e; border-color: #3a3a48; }}"
            "QPushButton:pressed { background: #20202a; }"
        )
        back.clicked.connect(self.close)
        row.addWidget(back)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {_BORDER}; max-width: 1px;"); row.addWidget(sep)

        # Title
        title = QLabel("Primaries — Color Wheels")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 11px; font-weight: 600; "
            "letter-spacing: 0.3px; background: transparent; border: none;"
        )
        row.addWidget(title)
        row.addStretch(1)

        # Param fields: Temp / Tint / Cont / Pivot
        for lbl, val, lo, hi, dec in [
            ("Temp", 0.0, -100, 100, 1),
            ("Tint", 0.0, -100, 100, 2),
            ("Cont", 1.0, 0.0, 3.0, 3),
            ("Pivot", 0.435, 0.0, 1.0, 3),
        ]:
            w, _ = _param_field(lbl, val, lo, hi, dec)
            row.addWidget(w)

        return bar

    # ── scopes panel ─────────────────────────────────────────────────────────

    def _build_scopes_panel(self) -> QWidget:
        """Left panel: dropdown to choose scope kind + the scope display."""
        panel = QWidget()
        panel.setFixedWidth(260)
        panel.setStyleSheet(
            f"background: #131318; border-right: 1px solid {_BORDER};"
        )
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # Header row: label + dropdown
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)
        title = QLabel("Scopes")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 11px; font-weight: 600; "
            "background: transparent; border: none;"
        )
        hdr.addWidget(title)
        hdr.addStretch(1)

        self._scope_combo = QComboBox()
        self._scope_combo.setFixedHeight(20)
        self._scope_combo.setStyleSheet(
            f"QComboBox {{ background: #1d1d28; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; border-radius: 3px; "
            "font-size: 10px; padding: 0 4px; }}"
            f"QComboBox::drop-down {{ border: none; width: 16px; }}"
            f"QComboBox QAbstractItemView {{ background: #1d1d28; color: {_TEXT}; "
            f"border: 1px solid {_BORDER}; selection-background-color: #2a3a5a; }}"
        )
        for label, kind in _ScopeDisplayWidget._KINDS:
            self._scope_combo.addItem(label, kind)
        self._scope_combo.currentIndexChanged.connect(self._on_scope_kind_changed)
        hdr.addWidget(self._scope_combo)
        lay.addLayout(hdr)

        # Primary scope widget (top, larger)
        self._scope_primary = _ScopeDisplayWidget("waveform")
        lay.addWidget(self._scope_primary, 3)

        # Secondary scope widget (bottom, smaller) — fixed to vectorscope
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_BORDER};")
        lay.addWidget(sep)

        sec_label = QLabel("Vectorscope")
        sec_label.setStyleSheet(
            f"color: {_LABEL}; font-size: 10px; background: transparent; border: none;"
        )
        lay.addWidget(sec_label)

        self._scope_secondary = _ScopeDisplayWidget("vectorscope")
        lay.addWidget(self._scope_secondary, 2)

        return panel

    def _on_scope_kind_changed(self, index: int) -> None:
        kind = self._scope_combo.itemData(index)
        if kind:
            self._scope_primary.set_kind(kind)

    # ── four wheels ──────────────────────────────────────────────────────────

    def _build_wheels_area(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {_BG_PANEL};")
        row = QHBoxLayout(panel)
        row.setContentsMargins(16, 16, 16, 16)
        row.setSpacing(0)

        self._sections: dict[str, _WheelSection] = {}
        specs = [
            ("shadows",    "Lift"),
            ("midtones",   "Gamma"),
            ("highlights", "Gain"),
            ("offset",     "Offset"),
        ]
        for i, (region, label) in enumerate(specs):
            sec = _WheelSection(label)
            sec.wheel_changed.connect(
                lambda x, y, r=region: self._on_wheel(r, x, y)
            )
            sec.luma_changed.connect(
                lambda v, r=region: self._on_luma(r, v)
            )
            row.addWidget(sec, 1)
            self._sections[region] = sec

            if i < len(specs) - 1:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.VLine)
                div.setFixedWidth(1)
                div.setStyleSheet(f"background: {_BORDER}; border: none;")
                row.addWidget(div)

        return panel

    # ── bottom bar ───────────────────────────────────────────────────────────

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(
            f"background: {_BG_BAR}; "
            f"border-top: 1px solid {_BORDER}; border-bottom: 1px solid {_BORDER};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 0, 14, 0); row.setSpacing(12)

        # Left group: sliders
        self._sl_boost   = _SlimSlider("Col Boost")
        self._sl_shadow  = _SlimSlider("Shadow")
        self._sl_hilight = _SlimSlider("HiLight")
        for sl in (self._sl_boost, self._sl_shadow, self._sl_hilight):
            row.addWidget(sl, 1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"color: {_BORDER};"); row.addWidget(sep)

        # Right group: spinboxes
        for lbl, val in [("Sat", 55.0), ("Hue", 0.0), ("L.Mix", 100.0)]:
            w, _ = _param_field(lbl, val, -200, 200, 2)
            row.addWidget(w)

        return bar

    # ── node graph strip ─────────────────────────────────────────────────────

    def _build_node_strip(self) -> QWidget:
        self._node_strip_host = QWidget()
        self._node_strip_host.setFixedHeight(160)
        self._node_strip_host.setStyleSheet(
            f"background: #141418; border-top: 1px solid {_BORDER};"
        )
        lay = QVBoxLayout(self._node_strip_host)
        placeholder = QLabel("노드 그래프")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(f"color: #404050; font-size: 12px; border:none; background:transparent;")
        lay.addWidget(placeholder)
        return self._node_strip_host

    # ── public API ───────────────────────────────────────────────────────────

    def set_node_graph_widget(self, widget: QWidget) -> None:
        lay = self._node_strip_host.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget(): item.widget().setParent(None)
        lay.addWidget(widget)

    def update_grade(self, grade) -> None:
        if grade is None: return
        mapping = {
            "shadows":    ("shadows_x", "shadows_y", "shadows_l"),
            "midtones":   ("midtones_x","midtones_y","midtones_l"),
            "highlights": ("highlights_x","highlights_y","highlights_l"),
            "offset":     ("offset_x", "offset_y", "offset_l"),
        }
        for region, (ax, ay, al) in mapping.items():
            sec = self._sections.get(region)
            if sec is None: continue
            x  = int(getattr(grade, ax, 0))
            y  = int(getattr(grade, ay, 0))
            lm = float(getattr(grade, al, 0.0))
            sec.set_grade_values(x, y, lm)
        sat = float(getattr(grade, "saturation", 0.0))
        self._sl_shadow.set_value(sat)

    def update_frame(self, rgb, grade) -> None:
        """Push a new frame to the scopes and update the grade display."""
        if grade is not None:
            self.update_grade(grade)
        if rgb is not None:
            try:
                self._scope_primary.update_frame(rgb)
                self._scope_secondary.update_frame(rgb)
            except Exception:
                pass

    # ── grade changes ────────────────────────────────────────────────────────

    def _on_wheel(self, region: str, x: int, y: int) -> None:
        grade = self._get_or_create_grade()
        if grade is None: return
        ax = region + "_x"; ay = region + "_y"
        setattr(grade, ax, x); setattr(grade, ay, y)
        self.grade_changed.emit(grade)

    def _on_luma(self, region: str, val: float) -> None:
        grade = self._get_or_create_grade()
        if grade is None: return
        setattr(grade, region + "_l", int(val * 100))
        self.grade_changed.emit(grade)

    def _get_or_create_grade(self):
        if self._editor is None: return None
        try:
            from app.color_grading import ColorGrade
            node = getattr(self._editor, "_node_grade_target", None)
            if node is not None:
                g = getattr(node, "color_grade", None)
                if g is None:
                    node.color_grade = ColorGrade()
                return node.color_grade
            track = getattr(self._editor, "_active_track", None)
            if track:
                if not hasattr(track, "color_grade"):
                    track.color_grade = ColorGrade()
                return track.color_grade
        except Exception:
            pass
        return None
