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
    QColor, QConicalGradient, QFont, QImage, QLinearGradient,
    QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QMenu, QPushButton, QScrollArea, QSizePolicy, QSlider, QSplitter,
    QVBoxLayout, QWidget,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import editor_scrollbar_qss
from app.ux_feedback import apply_state_to_label, color_management_state, scope_status_state

# ── Design tokens: Screen-Studio-like color workspace chrome ────────────────
_BG         = "#0F1011"
_BG_PANEL   = "#141414"
_BG_SECTION = "#171717"
_BG_BAR     = "#111111"
_BORDER     = "#2E3033"
_BORDER_HI  = "#62676F"
_LABEL      = "#A7ADB5"
_TITLE      = "#F8F4EA"
_TEXT       = "#E5E8ED"
_VAL_BG     = "rgba(255,255,255,10)"
_ACCENT     = "#B98A72"
_ACCENT_2   = "#9CA6B5"
_CYAN       = "#8DA7B4"

_TINY_FONT = (
    "font-size: 10px; "
    "font-family: 'Pretendard', 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
)
_SBOX_QSS = (
    f"QDoubleSpinBox {{ background: {_VAL_BG}; color: {_TEXT}; "
    f"border: 1px solid {_BORDER}; border-radius: 9px; {_TINY_FONT} "
    "padding: 3px 5px; min-width: 46px; max-width: 58px; }}"
    f"QDoubleSpinBox:hover {{ background: rgba(255,255,255,22); border-color: {_BORDER_HI}; }}"
    f"QDoubleSpinBox:focus {{ border-color: {_ACCENT_2}; background: rgba(255,255,255,14); }}"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0; }"
)
_PARAM_QSS = (
    f"QDoubleSpinBox {{ background: {_VAL_BG}; color: {_TEXT}; "
    f"border: 1px solid {_BORDER}; border-radius: 10px; {_TINY_FONT} "
    "padding: 4px 7px; min-width: 52px; max-width: 68px; }}"
    f"QDoubleSpinBox:hover {{ background: rgba(255,255,255,22); border-color: {_BORDER_HI}; }}"
    f"QDoubleSpinBox:focus {{ border-color: {_ACCENT_2}; }}"
    "QDoubleSpinBox::up-button, QDoubleSpinBox::down-button { width:0; }"
)


def _glass_panel_qss(selector: str) -> str:
    return (
        f"{selector} {{ "
        "background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
        " stop:0 rgba(255,255,255,12), stop:1 rgba(255,255,255,5));"
        f" border:1px solid {_BORDER}; border-radius:14px; }}"
        f"{selector}:hover {{ border-color: {_BORDER_HI}; }}"
    )


def _combo_qss() -> str:
    return (
        f"QComboBox {{ background: rgba(255,255,255,10); color: {_TEXT}; "
        f"border: 1px solid {_BORDER}; border-radius: 10px; "
        "font-size: 10px; padding: 5px 24px 5px 9px; }}"
        f"QComboBox:hover {{ background: rgba(255,255,255,16); border-color: {_BORDER_HI}; }}"
        "QComboBox:focus, QComboBox:on { border-color: #7B8DA8; }"
        "QComboBox::drop-down { border: none; width: 20px; background: transparent; }"
        "QComboBox::down-arrow { image: none; border-left:4px solid transparent; "
        "border-right:4px solid transparent; border-top:5px solid #A7ADC2; width:0; height:0; }"
        f"QComboBox QAbstractItemView {{ background: #151515; color: {_TEXT}; "
        f"border: 1px solid {_BORDER_HI}; border-radius: 10px; padding: 5px; "
        "selection-background-color: #282A2D; }}"
    )


def _soft_button_qss() -> str:
    return (
        "QPushButton { background: #171717; color:#D9DDE4; "
        "border:1px solid #303030; border-radius:10px; padding:6px 12px; "
        "font-size:10px; font-weight:700; }"
        "QPushButton:hover { background: #202020; border-color:#565A60; color:#F4F6FA; }"
        "QPushButton:pressed { background: #242424; border-color:#87909A; }"
    )


# ── Colour Wheel ──────────────────────────────────────────────────────────────

class _ColorPaletteRibbon(QWidget):
    """Compact wallpaper-palette strip used as a visual color-page signature."""

    _PALETTES = (
        ("#FF8057", "#F65368", "#755DF2"),
        ("#FFB454", "#FF6A88", "#8A7CFF"),
        ("#36D1DC", "#5B86E5", "#A06BD0"),
        ("#8EE6A8", "#22BDE4", "#6F5CFF"),
        ("#FFD36B", "#FF8057", "#E84E78"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 28)
        self.setToolTip("Color look palette")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        x = 0
        for idx, stops in enumerate(self._PALETTES):
            rect = QRect(x, 2, 24, 24)
            grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
            for stop_idx, color in enumerate(stops):
                grad.setColorAt(stop_idx / max(1, len(stops) - 1), QColor(color))
            p.setPen(QPen(QColor(255, 255, 255, 58 if idx else 105), 1))
            p.setBrush(grad)
            p.drawRoundedRect(rect, 8, 8)
            shine = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.center().y())
            shine.setColorAt(0.0, QColor(255, 255, 255, 86))
            shine.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(shine)
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -12), 6, 6)
            x += 30
        p.end()


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
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

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

        cx, cy = self._cx(), self._cy()
        outer_r = min(self.width(), self.height()) // 2 - 4
        hue_w = max(4, int(outer_r * 0.078))
        hue_out = outer_r - max(2, int(outer_r * 0.025))
        hue_in = hue_out - hue_w
        inner_r = max(8, hue_in - max(4, int(outer_r * 0.045)))

        p.setPen(Qt.PenStyle.NoPen)

        # Reference-style circular instrument: no rounded-square tile behind it.
        p.setBrush(QColor(0, 0, 0, 92))
        p.drawEllipse(QPoint(cx, cy + 2), outer_r + 4, outer_r + 4)
        shell = QRadialGradient(cx - outer_r * 0.22, cy - outer_r * 0.32, outer_r * 1.18)
        shell.setColorAt(0.0, QColor("#202831"))
        shell.setColorAt(0.62, QColor("#111820"))
        shell.setColorAt(1.0, QColor("#07090B"))
        p.setBrush(shell)
        p.drawEllipse(QPoint(cx, cy), outer_r + 2, outer_r + 2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.drawEllipse(QPoint(cx, cy), outer_r + 1, outer_r + 1)
        p.setPen(QPen(QColor(0, 0, 0, 130), 1))
        p.drawEllipse(QPoint(cx, cy), outer_r + 3, outer_r + 3)

        p.setPen(Qt.PenStyle.NoPen)
        luma_grad = QConicalGradient(cx, cy, -90)
        luma_grad.setColorAt(0.0, QColor(222, 226, 232, 88))
        luma_grad.setColorAt(0.33, QColor(74, 82, 92, 58))
        luma_grad.setColorAt(0.66, QColor(10, 12, 15, 34))
        luma_grad.setColorAt(1.0, QColor(222, 226, 232, 88))
        p.setBrush(luma_grad)
        p.drawEllipse(QPoint(cx, cy), hue_out + 4, hue_out + 4)
        p.setBrush(QColor("#0C1116"))
        p.drawEllipse(QPoint(cx, cy), hue_out + 1, hue_out + 1)

        conic = QConicalGradient(cx, cy, 90)
        for pos, rgb in self._HUE_STOPS:
            conic.setColorAt(pos, QColor(*rgb))
        p.setBrush(conic)
        p.drawEllipse(QPoint(cx, cy), hue_out, hue_out)
        p.setBrush(QColor("#0C1116"))
        p.drawEllipse(QPoint(cx, cy), hue_in, hue_in)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawEllipse(QPoint(cx, cy), hue_out, hue_out)
        p.setPen(QPen(QColor(0, 0, 0, 120), 1))
        p.drawEllipse(QPoint(cx, cy), hue_in, hue_in)

        center_grad = QRadialGradient(cx, cy, inner_r)
        center_grad.setColorAt(0.0, QColor("#171F27"))
        center_grad.setColorAt(0.74, QColor("#10171E"))
        center_grad.setColorAt(1.0, QColor("#0B0F14"))
        p.setBrush(center_grad)
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        p.drawEllipse(QPoint(cx, cy), inner_r, inner_r)

        p.setPen(QPen(QColor(190, 200, 212, 42), 1))
        p.drawLine(cx - inner_r, cy, cx + inner_r, cy)
        p.drawLine(cx, cy - inner_r, cx, cy + inner_r)
        p.setPen(QPen(QColor(0, 0, 0, 84), 1))
        p.drawEllipse(QPoint(cx, cy), inner_r // 4, inner_r // 4)

        luma_angle = math.radians(90.0 - self._luma * 0.68)
        luma_mid_r = hue_out - hue_w * 0.52
        lind_x = int(cx + luma_mid_r * math.cos(luma_angle))
        lind_y = int(cy - luma_mid_r * math.sin(luma_angle))
        brightness = max(70, min(225, 150 + self._luma * 65 // 100))
        p.setBrush(QColor(0, 0, 0, 118))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(lind_x, lind_y + 1), 4, 4)
        p.setBrush(QColor(brightness, brightness, brightness))
        p.setPen(QPen(QColor(255, 255, 255, 72), 1))
        p.drawEllipse(QPoint(lind_x, lind_y), 3, 3)

        vx = int(self._x / 100.0 * inner_r * 0.82) + cx
        vy = int(self._y / 100.0 * inner_r * 0.82) + cy
        ind = QPoint(vx, vy)
        puck_r = max(5, min(8, int(outer_r * 0.13)))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 126))
        p.drawEllipse(QPoint(vx, vy + 1), puck_r + 2, puck_r + 2)
        p.setBrush(QColor("#1C232B"))
        p.setPen(QPen(QColor(207, 216, 229, 174), 1.2))
        p.drawEllipse(ind, puck_r, puck_r)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#7E8995"))
        p.drawEllipse(ind, max(2, puck_r // 2), max(2, puck_r // 2))
        p.end()
        return

        bg = QLinearGradient(0, 0, self.width(), self.height())
        bg.setColorAt(0.0, QColor("#171B2A"))
        bg.setColorAt(1.0, QColor("#0B0D16"))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(bg)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 18, 18)

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
        self.setStyleSheet(_glass_panel_qss("QWidget#WheelSection"))
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 12)
        root.setSpacing(8)

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
            "QPushButton { background: rgba(255,255,255,12); color:#A7ADC2; "
            "border:1px solid #30384F; border-radius:10px; font-size:13px; padding:0; }"
            "QPushButton:hover { background: rgba(255,255,255,28); color:#FFFFFF; border-color:#7580A5; }"
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
        readouts.setSpacing(5); readouts.setContentsMargins(0,0,0,0)
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
        self.setObjectName("ColorSlimSlider")
        self.setStyleSheet(
            "QWidget#ColorSlimSlider { background: rgba(255,255,255,8); "
            "border:1px solid rgba(126,141,198,36); border-radius:13px; }"
        )
        row = QHBoxLayout(self); row.setContentsMargins(9,4,8,4); row.setSpacing(8)

        lbl = QLabel(label)
        lbl.setFixedWidth(68)
        lbl.setStyleSheet(f"color: {_LABEL}; {_TINY_FONT} background:transparent; border:none;")
        row.addWidget(lbl)

        self._sl = StudioSlider("accent")
        self._sl.setRange(lo, hi); self._sl.setValue(default)
        row.addWidget(self._sl, 1)

        self._val = QLabel(f"{default:.2f}")
        self._val.setFixedWidth(42)
        self._val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._val.setStyleSheet(
            f"color:{_TEXT}; {_TINY_FONT} background:rgba(255,255,255,10); "
            "border:1px solid rgba(255,255,255,18); border-radius:9px; padding:2px 5px;"
        )
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
    w.setObjectName("ColorParamChip")
    w.setStyleSheet(
        "QWidget#ColorParamChip { background: rgba(255,255,255,8); "
        "border:1px solid rgba(126,141,198,34); border-radius:13px; }"
    )
    row = QHBoxLayout(w); row.setContentsMargins(8,4,5,4); row.setSpacing(5)
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
        self.setStyleSheet(
            f"background: rgba(10,12,21,220); border: 1px solid {_BORDER}; "
            "border-radius: 14px;"
        )

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
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        p.setBrush(QColor("#090B12"))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
        if self._pixmap is not None:
            p.drawPixmap(self.rect().adjusted(6, 6, -6, -6), self._pixmap, self._pixmap.rect())
        p.end()


class _SplitPreviewWidget(QWidget):
    """Small before/after preview for the current grade."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._before_pixmap: QPixmap | None = None
        self._after_pixmap: QPixmap | None = None
        self.setFixedHeight(72)
        self.setMinimumWidth(220)
        self.setToolTip("Before / after grade preview")

    def update_frame(self, rgb, grade) -> None:
        if rgb is None:
            return
        try:
            import numpy as np
            from app.color_grading import apply_to_rgb

            before = np.ascontiguousarray(rgb)
            after = np.ascontiguousarray(apply_to_rgb(before, grade)) if grade is not None else before
            h, w, _ = before.shape
            before_img = QImage(before.data, w, h, w * 3, QImage.Format.Format_RGB888)
            after_img = QImage(after.data, w, h, w * 3, QImage.Format.Format_RGB888)
            self._before_pixmap = QPixmap.fromImage(before_img.copy())
            self._after_pixmap = QPixmap.fromImage(after_img.copy())
        except Exception:
            self._before_pixmap = None
            self._after_pixmap = None
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 38), 1))
        p.setBrush(QColor(12, 15, 26, 210))
        p.drawRoundedRect(r, 14, 14)
        inner = r.adjusted(5, 5, -5, -5)
        mid = inner.center().x()
        left = QRect(inner.left(), inner.top(), max(1, mid - inner.left()), inner.height())
        right = QRect(mid, inner.top(), max(1, inner.right() - mid + 1), inner.height())
        if self._before_pixmap is not None:
            p.drawPixmap(left, self._before_pixmap, self._before_pixmap.rect())
        if self._after_pixmap is not None:
            p.drawPixmap(right, self._after_pixmap, self._after_pixmap.rect())
        p.setPen(QPen(QColor("#FFFFFF"), 1))
        p.drawLine(mid, inner.top(), mid, inner.bottom())
        p.setPen(QColor(255, 255, 255, 210))
        p.drawText(left.adjusted(6, 4, -4, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Before")
        p.drawText(right.adjusted(6, 4, -4, -4), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "After")
        p.end()


class _HueCurveMiniGraph(QWidget):
    """Tiny Hue-vs-Sat graph for advanced color controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skin_sat = 0
        self._shadow = 0
        self._highlight = 0
        self.setFixedHeight(64)
        self.setToolTip("Hue/Sat and HDR zone response")

    def set_values(self, *, skin_sat: int = 0, shadow: int = 0, highlight: int = 0) -> None:
        self._skin_sat = int(skin_sat)
        self._shadow = int(shadow)
        self._highlight = int(highlight)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(r, 12, 12)
        g = r.adjusted(10, 10, -10, -12)
        base_y = g.center().y()
        p.setPen(QPen(QColor(255, 255, 255, 36), 1))
        p.drawLine(g.left(), base_y, g.right(), base_y)
        p.drawLine(g.left(), g.top(), g.left(), g.bottom())
        p.setPen(QPen(QColor("#FF8057"), 2))
        x0 = g.left()
        y0 = base_y - int(self._shadow / 100.0 * g.height() * 0.5)
        x1 = g.left() + int(g.width() * 0.28)
        y1 = base_y - int(self._skin_sat / 100.0 * g.height() * 0.5)
        x2 = g.right()
        y2 = base_y - int(self._highlight / 100.0 * g.height() * 0.5)
        p.drawLine(x0, y0, x1, y1)
        p.drawLine(x1, y1, x2, y2)
        p.setBrush(QColor("#8A7CFF"))
        p.setPen(QPen(QColor("#FFFFFF"), 1))
        for x, y in ((x0, y0), (x1, y1), (x2, y2)):
            p.drawEllipse(QPoint(x, y), 3, 3)
        p.setPen(QColor("#A7ADC2"))
        p.drawText(r.adjusted(8, 2, -8, -2), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Hue/Sat")
        p.end()


class _WarperMiniGrid(QWidget):
    """Tiny Color Warper grid showing the current skin-hue point."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hue_shift = 0
        self._sat = 0
        self.setFixedHeight(64)
        self.setToolTip("Color Warper point")

    def set_values(self, *, hue_shift: int = 0, saturation: int = 0) -> None:
        self._hue_shift = int(hue_shift)
        self._sat = int(saturation)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 34), 1))
        p.setBrush(QColor(255, 255, 255, 10))
        p.drawRoundedRect(r, 12, 12)
        g = r.adjusted(10, 12, -10, -10)
        for idx in range(5):
            t = idx / 4.0
            x = g.left() + int(g.width() * t)
            y = g.top() + int(g.height() * t)
            p.setPen(QPen(QColor(255, 255, 255, 26), 1))
            p.drawLine(x, g.top(), x, g.bottom())
            p.drawLine(g.left(), y, g.right(), y)
        px = g.center().x() + int(self._hue_shift / 45.0 * g.width() * 0.42)
        py = g.center().y() - int(self._sat / 100.0 * g.height() * 0.36)
        p.setBrush(QColor("#36D1DC"))
        p.setPen(QPen(QColor("#FFFFFF"), 2))
        p.drawEllipse(QPoint(px, py), 6, 6)
        p.setPen(QColor("#A7ADC2"))
        p.drawText(r.adjusted(8, 2, -8, -2), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, "Warper")
        p.end()


# ── Main ColorPageWindow ──────────────────────────────────────────────────────

class ColorPageWindow(QWidget):
    """Full-screen color grading page — DaVinci Resolve 'Primaries - Color Wheels' style."""

    grade_changed = Signal(object)   # emits ColorGrade

    def __init__(self, editor=None, parent=None):
        super().__init__(parent)
        self._editor = editor
        self._cm_syncing = False
        self._workflow_syncing = False
        self._workflow_slider_labels: dict[str, QLabel] = {}
        self._advanced_syncing = False
        self._advanced_slider_labels: dict[str, QLabel] = {}
        self.setWindowTitle("TigerCapture — Color")
        self.resize(1440, 820)
        self.setStyleSheet(
            f"QWidget {{ background: {_BG}; color: {_TEXT}; }}"
            "QLabel { background: transparent; border: none; }"
            "QSplitter::handle { background: rgba(255,255,255,24); }"
        )
        self._build_ui()
        self._sync_color_management_ui()

    # ── build ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_toolbar(), 0)
        root.addWidget(self._build_role_strip(), 0)
        root.addWidget(self._build_color_management_bar(), 0)

        # Middle row: scopes panel (left) + color wheels (centre/right)
        mid = QWidget()
        mid.setObjectName("ColorMainRow")
        mid.setStyleSheet(
            "QWidget#ColorMainRow { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            " stop:0 #0F1011, stop:.55 #141414, stop:1 #0F1011); }"
        )
        mid_row = QHBoxLayout(mid)
        mid_row.setContentsMargins(10, 10, 10, 10)
        mid_row.setSpacing(10)
        mid_row.addWidget(self._build_scopes_panel(), 0)

        mid_row.addWidget(self._build_wheels_area(), 1)

        mid_row.addWidget(self._build_qualifier_window_panel(), 0)
        root.addWidget(mid, 1)

        root.addWidget(self._build_bottom_bar(), 0)
        root.addWidget(self._build_node_strip(), 0)

    # ── toolbar ──────────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ColorTopBar")
        bar.setFixedHeight(56)
        bar.setStyleSheet(
            "QWidget#ColorTopBar {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 #0F1011, stop:.44 #151515, stop:1 #0F1011);"
            f" border-bottom: 1px solid {_BORDER};"
            "}"
            "font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8); row.setSpacing(10)

        back = QPushButton("Edit")
        back.setIcon(app_icon("previous", size=15, color="#E8EAF4"))
        back.setIconSize(icon_size(15))
        back.setToolTip("Back to edit workspace")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(_soft_button_qss())
        back.clicked.connect(self.close)
        row.addWidget(back)

        row.addWidget(_ColorPaletteRibbon())

        title = QLabel("Color Grade")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 16px; font-weight: 900; "
            "letter-spacing: 0px; background: transparent; border: none;"
        )
        row.addWidget(title)
        subtitle = QLabel("Primaries · Curves · Scopes · Windows")
        subtitle.setStyleSheet(
            f"color:{_LABEL}; font-size:10px; font-weight:700; "
            "background:transparent; border:none;"
        )
        row.addWidget(subtitle)
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

    def _build_role_strip(self) -> QWidget:
        strip = QWidget()
        strip.setObjectName("ColorRoleStrip")
        strip.setFixedHeight(42)
        strip.setStyleSheet(
            "QWidget#ColorRoleStrip {"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 rgba(18,18,18,238), stop:.48 rgba(14,14,14,236), stop:1 rgba(20,20,20,238));"
            f"border-bottom:1px solid {_BORDER};"
            "}"
            "QLabel#ColorRoleChip {"
            "background:rgba(255,255,255,16); color:#E8EAF4;"
            "border:1px solid rgba(190,198,210,34); border-radius:12px;"
            "padding:5px 11px; font-size:10px; font-weight:850;"
            "}"
            "QLabel#ColorRoleChip[active=\"true\"] {"
            "background:#242424;"
            "border-color:#A8B5C9; color:#FFFFFF;"
            "}"
            "QLabel#ColorRoleHint { color:#A7ADC2; font-size:10px; font-weight:700; }"
        )
        row = QHBoxLayout(strip)
        row.setContentsMargins(14, 7, 14, 7)
        row.setSpacing(8)

        def _chip(text: str, *, active: bool = False) -> QLabel:
            lbl = QLabel(text)
            lbl.setObjectName("ColorRoleChip")
            lbl.setProperty("active", "true" if active else "false")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            return lbl

        row.addWidget(_chip("Quick Dock", active=False), 0)
        row.addWidget(_chip("Professional Grade", active=True), 0)
        row.addWidget(_chip("Scopes + Windows", active=False), 0)
        row.addWidget(_chip("Export Parity", active=False), 0)
        row.addWidget(_ColorPaletteRibbon(), 0)
        row.addStretch(1)
        hint = QLabel("Dock = fast correction · Page = scopes, qualifier, power window, color management")
        hint.setObjectName("ColorRoleHint")
        row.addWidget(hint, 0)
        return strip

    def _build_color_management_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ColorPipelineBar")
        bar.setFixedHeight(78)
        bar.setStyleSheet(
            "QWidget#ColorPipelineBar { background: rgba(15,15,15,238); "
            f"border-bottom: 1px solid {_BORDER}; }}"
            "font-family: 'Segoe UI Variable', 'Segoe UI', Arial, sans-serif;"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(10)

        title_box = QWidget()
        title_box.setObjectName("ColorPipelineTitle")
        title_box.setStyleSheet(_glass_panel_qss("QWidget#ColorPipelineTitle"))
        title_lay = QVBoxLayout(title_box)
        title_lay.setContentsMargins(12, 7, 12, 7)
        title_lay.setSpacing(1)
        title = QLabel("PIPELINE")
        title.setStyleSheet(
            f"color:{_TITLE}; font-size:10px; font-weight:900; letter-spacing:0px;"
        )
        title_lay.addWidget(title)
        hint = QLabel("Input → Look → Output")
        hint.setStyleSheet(f"color:{_LABEL}; font-size:9px; font-weight:700;")
        title_lay.addWidget(hint)
        row.addWidget(title_box)

        self._cm_input_space = self._cm_combo("Input", [
            ("Rec.709", "rec709"), ("sRGB", "srgb"), ("Rec.2020", "rec2020"),
            ("P3-D65", "p3-d65"), ("ACEScg", "acescg"), ("ACEScct", "acescct"),
        ])
        self._cm_working_space = self._cm_combo("Working", [
            ("Rec.709", "rec709"), ("sRGB", "srgb"), ("ACEScg", "acescg"),
            ("ACEScct", "acescct"), ("Rec.2020", "rec2020"),
        ])
        self._cm_output_space = self._cm_combo("Output", [
            ("Rec.709", "rec709"), ("sRGB", "srgb"), ("Rec.2020", "rec2020"),
            ("P3-D65", "p3-d65"),
        ])
        self._cm_output_transfer = self._cm_combo("Transfer", [
            ("BT.709", "bt709"), ("sRGB", "srgb"), ("PQ", "pq"),
            ("HLG", "hlg"), ("Linear", "linear"),
        ])
        self._cm_view_transform = self._cm_combo("View", [
            ("Rec.709", "rec709"), ("sRGB", "srgb"), ("ACES 1.3", "aces-1.3"),
            ("HDR PQ", "hdr-pq"), ("HDR HLG", "hdr-hlg"), ("None", "none"),
        ])
        for combo in (
            self._cm_input_space,
            self._cm_working_space,
            self._cm_output_space,
            self._cm_output_transfer,
            self._cm_view_transform,
        ):
            combo.currentIndexChanged.connect(self._on_color_management_controls_changed)
            row.addWidget(combo)

        self._cm_hdr = QCheckBox("HDR")
        self._cm_hdr.setStyleSheet(
            f"QCheckBox {{ color: {_TEXT}; font-size: 10px; font-weight:800; background: transparent; }}"
            "QCheckBox::indicator { width: 17px; height: 17px; border-radius:5px; "
            "border:1px solid #3A435D; background:rgba(255,255,255,12); }"
            "QCheckBox::indicator:checked { background:#6E86A7; border-color:#D6DEE9; }"
        )
        self._cm_hdr.toggled.connect(self._on_color_management_controls_changed)
        row.addWidget(self._cm_hdr)

        self._cm_look_strength = _SlimSlider("Look %", 0, 100, 100)
        self._cm_look_strength.setFixedWidth(200)
        self._cm_look_strength.value_changed.connect(self._on_color_management_controls_changed)
        row.addWidget(self._cm_look_strength)

        for label, slot in (("Input LUT", "input"), ("Look LUT", "creative"), ("Output LUT", "output")):
            btn = QPushButton(label)
            btn.setFixedHeight(30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._cm_button_qss())
            btn.clicked.connect(lambda _checked=False, s=slot: self._pick_project_lut(s))
            row.addWidget(btn)

        self._cm_ocio_button = QPushButton("OCIO")
        self._cm_ocio_button.setFixedHeight(30)
        self._cm_ocio_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cm_ocio_button.setStyleSheet(self._cm_button_qss())
        self._cm_ocio_button.clicked.connect(self._show_ocio_menu)
        row.addWidget(self._cm_ocio_button)

        clear = QPushButton("Clear LUTs")
        clear.setFixedHeight(30)
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setStyleSheet(self._cm_button_qss())
        clear.clicked.connect(self._clear_project_luts)
        row.addWidget(clear)

        self._cm_status = QLabel("")
        self._cm_status.setMinimumWidth(180)
        self._cm_status.setStyleSheet(
            f"QLabel {{ color: {_LABEL}; font-size: 10px; font-weight:700; "
            "background:rgba(255,255,255,8); border:1px solid rgba(126,141,198,34); "
            "border-radius:13px; padding:7px 10px; }}"
            "QLabel[tone=\"success\"] { color:#5DCAA5; }"
            "QLabel[tone=\"warning\"] { color:#E0B45C; }"
            "QLabel[tone=\"error\"] { color:#E54646; }"
        )
        row.addWidget(self._cm_status, 1)
        return bar

    def _cm_combo(self, tooltip: str, items: list[tuple[str, str]]) -> QComboBox:
        combo = QComboBox()
        combo.setToolTip(tooltip)
        combo.setFixedHeight(30)
        combo.setMinimumWidth(108)
        combo.setStyleSheet(_combo_qss())
        for label, value in items:
            combo.addItem(label, value)
        return combo

    def _cm_button_qss(self) -> str:
        return _soft_button_qss()

    def _sync_color_management_ui(self) -> None:
        if not hasattr(self, "_cm_input_space"):
            return
        try:
            cm = self._project_color_management()
            self._cm_syncing = True
            self._set_combo_data(self._cm_input_space, cm.input_space)
            self._set_combo_data(self._cm_working_space, cm.working_space)
            self._set_combo_data(self._cm_output_space, cm.output_space)
            self._set_combo_data(self._cm_output_transfer, cm.output_transfer)
            self._set_combo_data(self._cm_view_transform, cm.view_transform)
            self._cm_hdr.setChecked(bool(cm.hdr_mode))
            self._cm_look_strength.set_value(int(round(cm.creative_lut.strength * 100.0)))
            self._cm_ocio_button.setToolTip(
                cm.ocio_config_path or "Choose an OpenColorIO config"
            )
            from app.color_management import validate_color_management

            apply_state_to_label(
                self._cm_status,
                color_management_state(validate_color_management(cm)),
            )
        except Exception:
            pass
        finally:
            self._cm_syncing = False

    def _set_combo_data(self, combo: QComboBox, value: str) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _project_color_management(self):
        from app.color_management import ColorManagementSettings, default_color_management

        settings = getattr(self._editor, "_project_settings", None) if self._editor is not None else None
        if not isinstance(settings, dict):
            return default_color_management()
        cm = ColorManagementSettings.from_dict(settings.get("color_management"))
        settings["color_management"] = cm.to_dict()
        return cm

    def _commit_color_management(self, cm) -> None:
        if self._editor is None:
            return
        settings = getattr(self._editor, "_project_settings", None)
        if not isinstance(settings, dict):
            settings = {}
            self._editor._project_settings = settings
        settings["color_management"] = cm.to_dict()
        try:
            player = getattr(self._editor, "_player", None)
            if player is not None and hasattr(player, "set_project_settings"):
                player.set_project_settings(settings)
            if player is not None and hasattr(player, "refresh_current_frame"):
                player.refresh_current_frame()
        except Exception:
            pass
        try:
            register = getattr(self._editor, "_register_change", None)
            if callable(register):
                register("project color management")
        except Exception:
            pass
        try:
            flash = getattr(self._editor, "_flash_status", None)
            if callable(flash):
                flash("Color management updated")
        except Exception:
            pass

    def _on_color_management_controls_changed(self, *_args) -> None:
        if self._cm_syncing:
            return
        try:
            from app.color_management import ColorManagementSettings

            cm = self._project_color_management()
            data = cm.to_dict()
            data.update({
                "input_space": self._cm_input_space.currentData(),
                "working_space": self._cm_working_space.currentData(),
                "output_space": self._cm_output_space.currentData(),
                "output_transfer": self._cm_output_transfer.currentData(),
                "view_transform": self._cm_view_transform.currentData(),
                "hdr_mode": self._cm_hdr.isChecked(),
            })
            if (
                not str(data.get("ocio_config_path", "") or "")
                and (
                    data["working_space"] in {"acescg", "acescct"}
                    or data["view_transform"] == "aces-1.3"
                )
            ):
                from app.color_ocio import preferred_aces_ocio_uri

                data["ocio_config_path"] = preferred_aces_ocio_uri()
            creative = dict(data.get("creative_lut") or {})
            creative["strength"] = max(0.0, min(1.0, self._cm_look_strength._sl.value() / 100.0))
            data["creative_lut"] = creative
            new_cm = ColorManagementSettings.from_dict(data)
            self._commit_color_management(new_cm)
            self._sync_editor_creative_lut(new_cm)
            self._sync_color_management_ui()
        except Exception:
            pass

    def _pick_project_lut(self, slot_name: str) -> None:
        try:
            cm = self._project_color_management()
            start = ""
            slot = getattr(cm, f"{slot_name}_lut", None)
            if slot is not None and slot.path:
                import os
                start = os.path.dirname(slot.path)
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select LUT",
                start,
                "LUT Files (*.cube *.3dl);;All Files (*)",
            )
            if not path:
                return
            data = cm.to_dict()
            key = f"{slot_name}_lut"
            old = dict(data.get(key) or {})
            old.update({"path": path, "enabled": True})
            if "strength" not in old:
                old["strength"] = 1.0
            data[key] = old
            from app.color_management import ColorManagementSettings

            new_cm = ColorManagementSettings.from_dict(data)
            self._commit_color_management(new_cm)
            self._sync_editor_creative_lut(new_cm)
            self._sync_color_management_ui()
        except Exception:
            pass

    def _pick_ocio_config(self) -> None:
        try:
            cm = self._project_color_management()
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select OpenColorIO Config",
                cm.ocio_config_path,
                "OpenColorIO Config (*.ocio *.yaml *.yml);;All Files (*)",
            )
            if not path:
                return
            data = cm.to_dict()
            data["ocio_config_path"] = path
            from app.color_management import ColorManagementSettings

            self._commit_color_management(ColorManagementSettings.from_dict(data))
            self._sync_color_management_ui()
        except Exception:
            pass

    def _set_ocio_config(self, config_spec: str) -> None:
        try:
            cm = self._project_color_management()
            data = cm.to_dict()
            data["ocio_config_path"] = str(config_spec or "")
            from app.color_management import ColorManagementSettings

            self._commit_color_management(ColorManagementSettings.from_dict(data))
            self._sync_color_management_ui()
        except Exception:
            pass

    def _show_ocio_menu(self) -> None:
        menu = QMenu(self)
        try:
            from app.color_ocio import list_builtin_ocio_configs

            for row in list_builtin_ocio_configs():
                name = str(row["name"])
                if "v2.2.0_aces-v1.3" not in name:
                    continue
                family = "Studio" if row["studio"] else "CG"
                action = menu.addAction(f"{family} ACES 1.3")
                action.setToolTip(str(row["description"]))
                action.triggered.connect(
                    lambda _checked=False, uri=str(row["uri"]): self._set_ocio_config(uri)
                )
        except Exception:
            unavailable = menu.addAction("OpenColorIO runtime unavailable")
            unavailable.setEnabled(False)
        if not menu.isEmpty():
            menu.addSeparator()
        menu.addAction("Choose config file...", self._pick_ocio_config)
        clear = menu.addAction("Clear OCIO config")
        clear.triggered.connect(lambda _checked=False: self._set_ocio_config(""))
        menu.exec(
            self._cm_ocio_button.mapToGlobal(
                QPoint(0, self._cm_ocio_button.height())
            )
        )

    def _clear_project_luts(self) -> None:
        try:
            cm = self._project_color_management()
            data = cm.to_dict()
            for key in ("input_lut", "creative_lut", "output_lut"):
                data[key] = {"path": "", "strength": 1.0, "enabled": True}
            from app.color_management import ColorManagementSettings

            new_cm = ColorManagementSettings.from_dict(data)
            self._commit_color_management(new_cm)
            if self._editor is not None and hasattr(self._editor, "_clear_lut"):
                self._editor._clear_lut()
            self._sync_color_management_ui()
        except Exception:
            pass

    def _sync_editor_creative_lut(self, cm) -> None:
        if self._editor is None:
            return
        slot = cm.creative_lut
        try:
            if slot.is_active() and hasattr(self._editor, "_load_lut_from_path"):
                if getattr(self._editor, "_lut_path", "") != slot.path:
                    self._editor._load_lut_from_path(slot.path, warn_on_failure=False)
                self._editor._lut_strength = float(slot.strength)
                player = getattr(self._editor, "_player", None)
                if player is not None and hasattr(player, "refresh_current_frame"):
                    player.refresh_current_frame()
            elif hasattr(self._editor, "_clear_lut"):
                self._editor._clear_lut()
        except Exception:
            pass

    # ── scopes panel ─────────────────────────────────────────────────────────

    def _build_scopes_panel(self) -> QWidget:
        """Left panel: dropdown to choose scope kind + the scope display."""
        panel = QWidget()
        panel.setObjectName("ColorScopesPanel")
        panel.setFixedWidth(282)
        panel.setStyleSheet(_glass_panel_qss("QWidget#ColorScopesPanel"))
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Header row: label + dropdown
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)
        title = QLabel("Scopes")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 12px; font-weight: 900; "
            "background: transparent; border: none;"
        )
        hdr.addWidget(title)
        hdr.addStretch(1)

        self._scope_combo = QComboBox()
        self._scope_combo.setFixedHeight(28)
        self._scope_combo.setStyleSheet(_combo_qss())
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
        sep.setStyleSheet(f"background:{_BORDER}; border:none; max-height:1px;")
        lay.addWidget(sep)

        sec_label = QLabel("Vectorscope")
        sec_label.setStyleSheet(
            f"color: {_LABEL}; font-size: 10px; font-weight:800; background: transparent; border: none;"
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
        panel.setObjectName("ColorWheelsArea")
        panel.setStyleSheet("QWidget#ColorWheelsArea { background: transparent; border:none; }")
        row = QHBoxLayout(panel)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

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

        return panel

    def _build_qualifier_window_panel(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setObjectName("ColorQualifierScroll")
        scroll.setFixedWidth(336)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea#ColorQualifierScroll { background: transparent; border: none; }"
            "QScrollArea#ColorQualifierScroll > QWidget > QWidget { background: transparent; }"
            "QScrollBar:vertical { background: rgba(255,255,255,8); width:8px; border-radius:4px; }"
            "QScrollBar::handle:vertical { background:#6F5CFF; border-radius:4px; min-height:24px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }"
            + editor_scrollbar_qss("QScrollArea#ColorQualifierScroll")
        )
        panel = QWidget()
        panel.setObjectName("ColorQualifierPanel")
        panel.setStyleSheet(_glass_panel_qss("QWidget#ColorQualifierPanel"))
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(9)

        title = QLabel("Qualifier / Window")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 12px; font-weight: 900; "
            "background: transparent; border: none;"
        )
        lay.addWidget(title)

        self._qual_enabled = self._workflow_checkbox("Qualifier", lay)
        self._qual_invert = self._workflow_checkbox("Invert Key", lay)
        self._qual_hue = self._workflow_slider("Hue", "qual_hue", 0, 360, 60, lay, "deg")
        self._qual_width = self._workflow_slider("Width", "qual_width", 1, 180, 30, lay, "deg")
        self._qual_sat_min = self._workflow_slider("Sat Min", "qual_sat_min", 0, 100, 15, lay, "%")
        self._qual_sat_max = self._workflow_slider("Sat Max", "qual_sat_max", 0, 100, 100, lay, "%")
        self._qual_val_min = self._workflow_slider("Val Min", "qual_val_min", 0, 100, 0, lay, "%")
        self._qual_val_max = self._workflow_slider("Val Max", "qual_val_max", 0, 100, 100, lay, "%")
        self._qual_softness = self._workflow_slider("Soft", "qual_softness", 0, 100, 8, lay, "%")
        self._qual_clean_black = self._workflow_slider("Clean B", "qual_clean_black", 0, 100, 0, lay, "%")
        self._qual_clean_white = self._workflow_slider("Clean W", "qual_clean_white", 0, 100, 0, lay, "%")
        self._qual_denoise = self._workflow_slider("Denoise", "qual_denoise", 0, 9, 0, lay, "px")

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{_BORDER}; border:none; max-height:1px;")
        lay.addWidget(sep)

        self._window_enabled = self._workflow_checkbox("Power Window", lay)
        self._window_shape = self._cm_combo("Window shape", [("Ellipse", "ellipse"), ("Rectangle", "rectangle")])
        self._window_shape.currentIndexChanged.connect(self._on_workflow_controls_changed)
        lay.addWidget(self._window_shape)
        self._window_track = self._workflow_checkbox("Track Object", lay)
        self._window_x = self._workflow_slider("Center X", "window_x", 0, 100, 50, lay, "%")
        self._window_y = self._workflow_slider("Center Y", "window_y", 0, 100, 50, lay, "%")
        self._window_w = self._workflow_slider("Width", "window_w", 1, 100, 50, lay, "%")
        self._window_h = self._workflow_slider("Height", "window_h", 1, 100, 50, lay, "%")
        self._window_feather = self._workflow_slider("Feather", "window_feather", 0, 100, 8, lay, "%")
        self._window_opacity = self._workflow_slider("Opacity", "window_opacity", 0, 100, 100, lay, "%")

        self._workflow_status = QLabel("Mask: off")
        self._workflow_status.setWordWrap(True)
        self._workflow_status.setStyleSheet(
            f"color: {_LABEL}; font-size: 10px; font-weight:700; "
            "background:rgba(255,255,255,8); border:1px solid rgba(126,141,198,34); "
            "border-radius:13px; padding:7px 9px;"
        )
        lay.addWidget(self._workflow_status)
        self._scope_warning_status = QLabel("Scopes: nominal")
        self._scope_warning_status.setWordWrap(True)
        self._scope_warning_status.setStyleSheet(
            f"QLabel {{ color: {_LABEL}; font-size: 10px; font-weight:700; "
            "background:rgba(255,255,255,8); border:1px solid rgba(126,141,198,34); "
            "border-radius:13px; padding:7px 9px; }}"
            "QLabel[tone=\"success\"] { color:#5DCAA5; }"
            "QLabel[tone=\"warning\"] { color:#E0B45C; }"
            "QLabel[tone=\"error\"] { color:#E54646; }"
        )
        lay.addWidget(self._scope_warning_status)

        adv_sep = QFrame()
        adv_sep.setFrameShape(QFrame.Shape.HLine)
        adv_sep.setStyleSheet(f"background:{_BORDER}; border:none; max-height:1px;")
        lay.addWidget(adv_sep)
        self._build_advanced_color_panel(lay)
        lay.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def _build_advanced_color_panel(self, parent_layout: QVBoxLayout) -> None:
        title = QLabel("Advanced Color")
        title.setStyleSheet(
            f"color: {_TITLE}; font-size: 12px; font-weight: 900; "
            "background: transparent; border: none;"
        )
        parent_layout.addWidget(title)
        self._adv_enabled = self._workflow_checkbox("HDR / Log / Warper", parent_layout)
        try:
            self._adv_enabled.toggled.disconnect()
        except Exception:
            pass
        self._adv_enabled.toggled.connect(self._on_advanced_color_controls_changed)
        state_row = QHBoxLayout()
        state_row.setContentsMargins(0, 0, 0, 0)
        state_row.setSpacing(6)
        self._adv_bypass = QCheckBox("Bypass")
        self._adv_bypass.setStyleSheet(self._mini_checkbox_qss())
        self._adv_bypass.toggled.connect(self._on_advanced_color_controls_changed)
        self._adv_solo = QCheckBox("Solo")
        self._adv_solo.setStyleSheet(self._mini_checkbox_qss())
        self._adv_solo.toggled.connect(self._on_advanced_color_controls_changed)
        reset = QPushButton("Reset")
        reset.setFixedHeight(26)
        reset.setCursor(Qt.CursorShape.PointingHandCursor)
        reset.setStyleSheet(_soft_button_qss())
        reset.clicked.connect(self._reset_advanced_color_controls)
        state_row.addWidget(self._adv_bypass)
        state_row.addWidget(self._adv_solo)
        state_row.addWidget(reset)
        state_wrap = QWidget()
        state_wrap.setLayout(state_row)
        parent_layout.addWidget(state_wrap)
        self._adv_hdr_shadow = self._advanced_slider("HDR Shadow", "hdr_shadow", -100, 100, 0, parent_layout, "%")
        self._adv_hdr_highlight = self._advanced_slider("HDR High", "hdr_highlight", -100, 100, 0, parent_layout, "%")
        self._adv_log_shadow_r = self._advanced_slider("Log Shadow R", "log_shadow_r", -50, 50, 0, parent_layout, "")
        self._adv_log_highlight_b = self._advanced_slider("Log High B", "log_highlight_b", -50, 50, 0, parent_layout, "")
        self._adv_hue_sat_skin = self._advanced_slider("Skin Sat", "hue_sat_skin", -100, 100, 0, parent_layout, "%")
        self._adv_warper_skin = self._advanced_slider("Skin Warp", "warper_skin", -45, 45, 0, parent_layout, "deg")

        self._adv_split_preview = _SplitPreviewWidget()
        parent_layout.addWidget(self._adv_split_preview)
        graphs = QHBoxLayout()
        graphs.setContentsMargins(0, 0, 0, 0)
        graphs.setSpacing(7)
        self._adv_curve_graph = _HueCurveMiniGraph()
        self._adv_warper_grid = _WarperMiniGrid()
        graphs.addWidget(self._adv_curve_graph, 1)
        graphs.addWidget(self._adv_warper_grid, 1)
        graph_wrap = QWidget()
        graph_wrap.setLayout(graphs)
        parent_layout.addWidget(graph_wrap)

        self._advanced_status = QLabel("Advanced: off")
        self._advanced_status.setWordWrap(True)
        self._advanced_status.setStyleSheet(
            f"color: {_LABEL}; font-size: 10px; font-weight:700; "
            "background:rgba(255,255,255,8); border:1px solid rgba(126,141,198,34); "
            "border-radius:13px; padding:7px 9px;"
        )
        parent_layout.addWidget(self._advanced_status)

    def _mini_checkbox_qss(self) -> str:
        return (
            f"QCheckBox {{ color: {_TEXT}; font-size: 10px; font-weight:800; background: transparent; spacing:6px; }}"
            "QCheckBox::indicator { width: 15px; height: 15px; border-radius:5px; "
            "border:1px solid #3A435D; background:rgba(255,255,255,12); }"
            "QCheckBox::indicator:checked { background:#6E86A7; border-color:#D6DEE9; }"
        )

    def _advanced_slider(
        self,
        label: str,
        key: str,
        lo: int,
        hi: int,
        default: int,
        parent_layout: QVBoxLayout,
        suffix: str = "",
    ) -> QSlider:
        slider = self._workflow_slider(label, key, lo, hi, default, parent_layout, suffix)
        try:
            slider.valueChanged.disconnect()
        except Exception:
            pass
        slider.valueChanged.connect(
            lambda v, k=key, s=suffix: self._on_advanced_slider_changed(k, v, s)
        )
        return slider

    def _on_advanced_slider_changed(self, key: str, value: int, suffix: str) -> None:
        label = self._workflow_slider_labels.get(key)
        if label is not None:
            label.setText(self._workflow_slider_text(value, suffix))
        self._on_advanced_color_controls_changed()

    def _workflow_checkbox(self, label: str, parent_layout: QVBoxLayout) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setStyleSheet(
            f"QCheckBox {{ color: {_TEXT}; font-size: 10px; font-weight:800; background: transparent; spacing:8px; }}"
            "QCheckBox::indicator { width: 17px; height: 17px; border-radius:5px; "
            "border:1px solid #3A435D; background:rgba(255,255,255,12); }"
            "QCheckBox::indicator:hover { border-color:#8A7CFF; }"
            "QCheckBox::indicator:checked { background:#6E86A7; border-color:#D6DEE9; }"
        )
        cb.toggled.connect(self._on_workflow_controls_changed)
        parent_layout.addWidget(cb)
        return cb

    def _workflow_slider(
        self,
        label: str,
        key: str,
        lo: int,
        hi: int,
        default: int,
        parent_layout: QVBoxLayout,
        suffix: str = "",
    ) -> QSlider:
        row = QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(7)
        lbl = QLabel(label)
        lbl.setFixedWidth(64)
        lbl.setStyleSheet(f"color: {_LABEL}; font-size: 10px; font-weight:700; background: transparent; border: none;")
        row.addWidget(lbl)
        slider = StudioSlider("accent")
        slider.setRange(int(lo), int(hi))
        slider.setValue(int(default))
        row.addWidget(slider, 1)
        value = QLabel(self._workflow_slider_text(default, suffix))
        value.setFixedWidth(40)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        value.setStyleSheet(
            f"color:{_TEXT}; font-size: 10px; font-weight:700; background:rgba(255,255,255,10); "
            "border:1px solid rgba(255,255,255,18); border-radius:9px; padding:2px 5px;"
        )
        row.addWidget(value)
        self._workflow_slider_labels[key] = value
        slider.valueChanged.connect(
            lambda v, k=key, s=suffix: self._on_workflow_slider_changed(k, v, s)
        )
        wrap = QWidget()
        wrap.setObjectName("WorkflowSliderRow")
        wrap.setStyleSheet(
            "QWidget#WorkflowSliderRow { background: rgba(255,255,255,7); "
            "border:1px solid rgba(126,141,198,26); border-radius:13px; }"
        )
        wrap.setLayout(row)
        parent_layout.addWidget(wrap)
        return slider

    def _workflow_slider_text(self, value: int, suffix: str = "") -> str:
        return f"{int(value)}{suffix}" if suffix else str(int(value))

    def _on_workflow_slider_changed(self, key: str, value: int, suffix: str) -> None:
        label = self._workflow_slider_labels.get(key)
        if label is not None:
            label.setText(self._workflow_slider_text(value, suffix))
        self._on_workflow_controls_changed()

    # ── bottom bar ───────────────────────────────────────────────────────────

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("ColorBottomBar")
        bar.setFixedHeight(58)
        bar.setStyleSheet(
            "QWidget#ColorBottomBar { background: rgba(12,15,26,238); "
            f"border-top: 1px solid {_BORDER}; border-bottom: 1px solid {_BORDER}; }}"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(14, 8, 14, 8); row.setSpacing(10)

        # Left group: sliders
        self._sl_boost   = _SlimSlider("Col Boost")
        self._sl_shadow  = _SlimSlider("Shadow")
        self._sl_hilight = _SlimSlider("HiLight")
        self._sl_boost.value_changed.connect(
            lambda v: self._on_primary_slider("saturation", v)
        )
        self._sl_shadow.value_changed.connect(
            lambda v: self._on_primary_slider("brightness", v)
        )
        self._sl_hilight.value_changed.connect(
            lambda v: self._on_primary_slider("contrast", v)
        )
        for sl in (self._sl_boost, self._sl_shadow, self._sl_hilight):
            row.addWidget(sl, 1)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background:{_BORDER}; border:none; max-width:1px;"); row.addWidget(sep)

        # Right group: spinboxes
        for lbl, val in [("Sat", 55.0), ("Hue", 0.0), ("L.Mix", 100.0)]:
            w, _ = _param_field(lbl, val, -200, 200, 2)
            row.addWidget(w)

        return bar

    # ── node graph strip ─────────────────────────────────────────────────────

    def _build_node_strip(self) -> QWidget:
        self._node_strip_host = QWidget()
        self._node_strip_host.setObjectName("ColorNodeStrip")
        self._node_strip_host.setFixedHeight(168)
        self._node_strip_host.setStyleSheet(
            "QWidget#ColorNodeStrip { background: #0B0D16; border-top: 1px solid #30384F; }"
        )
        lay = QVBoxLayout(self._node_strip_host)
        placeholder = QLabel("노드 그래프")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet(
            "color:#6F7484; font-size:12px; font-weight:800; "
            "border:1px dashed #30384F; border-radius:16px; background:rgba(255,255,255,6);"
        )
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
        self._sl_boost.set_value(float(getattr(grade, "saturation", 0.0)))
        self._sl_shadow.set_value(float(getattr(grade, "brightness", 0.0)))
        self._sl_hilight.set_value(float(getattr(grade, "contrast", 0.0)))
        self._sync_workflow_ui(grade)
        self._sync_advanced_color_ui(grade)

    def _sync_workflow_ui(self, grade) -> None:
        if grade is None or not hasattr(self, "_qual_enabled"):
            return
        try:
            from app.color_workflow import ColorNodeWorkflow

            workflow = ColorNodeWorkflow.from_dict(getattr(grade, "color_workflow", None) or {})
            q = workflow.qualifier
            w = workflow.window
            self._workflow_syncing = True
            self._qual_enabled.setChecked(bool(q.enabled))
            self._qual_invert.setChecked(bool(q.invert))
            self._set_workflow_slider("qual_hue", self._qual_hue, int(round(q.hue_center)))
            self._set_workflow_slider("qual_width", self._qual_width, int(round(q.hue_width)))
            self._set_workflow_slider("qual_sat_min", self._qual_sat_min, int(round(q.sat_min * 100.0)))
            self._set_workflow_slider("qual_sat_max", self._qual_sat_max, int(round(q.sat_max * 100.0)))
            self._set_workflow_slider("qual_val_min", self._qual_val_min, int(round(q.val_min * 100.0)))
            self._set_workflow_slider("qual_val_max", self._qual_val_max, int(round(q.val_max * 100.0)))
            self._set_workflow_slider("qual_softness", self._qual_softness, int(round(q.softness * 100.0)))
            self._set_workflow_slider("qual_clean_black", self._qual_clean_black, int(round(q.clean_black * 100.0)))
            self._set_workflow_slider("qual_clean_white", self._qual_clean_white, int(round(q.clean_white * 100.0)))
            self._set_workflow_slider("qual_denoise", self._qual_denoise, int(q.denoise_radius))

            self._window_enabled.setChecked(bool(w.enabled))
            self._set_combo_data(self._window_shape, str(w.shape))
            self._window_track.setChecked(bool(w.track_object))
            self._set_workflow_slider("window_x", self._window_x, int(round(w.x * 100.0)))
            self._set_workflow_slider("window_y", self._window_y, int(round(w.y * 100.0)))
            self._set_workflow_slider("window_w", self._window_w, int(round(w.w * 100.0)))
            self._set_workflow_slider("window_h", self._window_h, int(round(w.h * 100.0)))
            self._set_workflow_slider("window_feather", self._window_feather, int(round(w.feather * 100.0)))
            self._set_workflow_slider("window_opacity", self._window_opacity, int(round(w.opacity * 100.0)))
            self._refresh_workflow_status()
        except Exception:
            pass
        finally:
            self._workflow_syncing = False

    def _sync_advanced_color_ui(self, grade) -> None:
        if grade is None or not hasattr(self, "_adv_enabled"):
            return
        try:
            advanced = dict(getattr(grade, "advanced_color_toolset", None) or {})
            hdr = advanced.get("hdr_zones", {}) if isinstance(advanced.get("hdr_zones"), dict) else {}
            log = advanced.get("log_wheels", {}) if isinstance(advanced.get("log_wheels"), dict) else {}
            hue = advanced.get("hue_curves", {}) if isinstance(advanced.get("hue_curves"), dict) else {}
            points = advanced.get("warper_points", []) if isinstance(advanced.get("warper_points"), list) else []

            def _arr_value(payload: dict, key: str, index: int) -> float:
                raw = payload.get(key, [])
                if isinstance(raw, (list, tuple)) and len(raw) > index:
                    try:
                        return float(raw[index])
                    except Exception:
                        return 0.0
                return 0.0

            def _curve_value(rows, target_hue: float) -> float:
                for raw in rows or []:
                    try:
                        h, v = raw
                        if abs(float(h) - target_hue) <= 6.0:
                            return float(v)
                    except Exception:
                        continue
                return 0.0

            warper_skin = 0.0
            for raw in points:
                if not isinstance(raw, dict):
                    continue
                try:
                    if abs(float(raw.get("hue", 0.0)) - 28.0) <= 12.0:
                        warper_skin = float(raw.get("hue_shift", 0.0))
                        break
                except Exception:
                    continue

            self._advanced_syncing = True
            self._adv_enabled.setChecked(bool(advanced))
            self._adv_bypass.setChecked(bool(advanced and advanced.get("enabled") is False))
            self._adv_solo.setChecked(bool(advanced and advanced.get("solo_preview", False)))
            self._set_advanced_slider("hdr_shadow", self._adv_hdr_shadow, int(round(float(hdr.get("shadow", 0.0) or 0.0))), "%")
            self._set_advanced_slider("hdr_highlight", self._adv_hdr_highlight, int(round(float(hdr.get("highlight", 0.0) or 0.0))), "%")
            self._set_advanced_slider("log_shadow_r", self._adv_log_shadow_r, int(round(_arr_value(log, "shadows", 0) * 1000.0)), "")
            self._set_advanced_slider("log_highlight_b", self._adv_log_highlight_b, int(round(_arr_value(log, "highlights", 2) * 1000.0)), "")
            self._set_advanced_slider("hue_sat_skin", self._adv_hue_sat_skin, int(round(_curve_value(hue.get("hue_vs_sat", []), 28.0) * 100.0)), "%")
            self._set_advanced_slider("warper_skin", self._adv_warper_skin, int(round(warper_skin)), "deg")
            self._refresh_advanced_status()
        except Exception:
            pass
        finally:
            self._advanced_syncing = False

    def _set_workflow_slider(self, key: str, slider: QSlider, value: int) -> None:
        value = max(slider.minimum(), min(slider.maximum(), int(value)))
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)
        label = self._workflow_slider_labels.get(key)
        if label is not None:
            suffix = "deg" if key in {"qual_hue", "qual_width"} else "%"
            if key == "qual_denoise":
                suffix = "px"
            label.setText(self._workflow_slider_text(value, suffix))

    def _set_advanced_slider(self, key: str, slider: QSlider, value: int, suffix: str = "") -> None:
        value = max(slider.minimum(), min(slider.maximum(), int(value)))
        slider.blockSignals(True)
        slider.setValue(value)
        slider.blockSignals(False)
        label = self._workflow_slider_labels.get(key)
        if label is not None:
            label.setText(self._workflow_slider_text(value, suffix))

    def _on_advanced_color_controls_changed(self, *_args) -> None:
        if self._advanced_syncing:
            return
        grade = self._get_or_create_grade()
        if grade is None:
            return
        try:
            enabled = bool(self._adv_enabled.isChecked())
            bypass = bool(self._adv_bypass.isChecked())
            solo = bool(self._adv_solo.isChecked())
            shadow = int(self._adv_hdr_shadow.value())
            highlight = int(self._adv_hdr_highlight.value())
            log_shadow_r = float(self._adv_log_shadow_r.value()) / 1000.0
            log_highlight_b = float(self._adv_log_highlight_b.value()) / 1000.0
            skin_sat = float(self._adv_hue_sat_skin.value()) / 100.0
            skin_warp = float(self._adv_warper_skin.value())
            active = enabled and any(
                abs(v) > 1e-6
                for v in (shadow, highlight, log_shadow_r, log_highlight_b, skin_sat, skin_warp)
            )
            if active:
                grade.advanced_color_toolset = {
                    "enabled": not bypass,
                    "solo_preview": solo,
                    "processing_bits": 32,
                    "yrgb": True,
                    "hdr_zones": {
                        "enabled": bool(shadow or highlight),
                        "shadow": shadow,
                        "highlight": highlight,
                        "pivot": 0.52,
                    },
                    "log_wheels": {
                        "shadows": [log_shadow_r, 0.0, 0.0],
                        "midtones": [0.0, 0.0, 0.0],
                        "highlights": [0.0, 0.0, log_highlight_b],
                        "pivot": 0.50,
                    },
                    "hue_curves": {
                        "hue_vs_sat": [[28, skin_sat]] if abs(skin_sat) > 1e-6 else [],
                    },
                    "warper_points": [
                        {"hue": 28, "saturation": 0.58, "hue_shift": skin_warp, "sat_scale": 1.0}
                    ] if abs(skin_warp) > 1e-6 else [],
                }
            else:
                grade.advanced_color_toolset = {}
            if getattr(grade, "preset_id", "none") != "none":
                grade.preset_id = "custom"
            self._refresh_advanced_status()
            self.grade_changed.emit(grade)
        except Exception:
            pass

    def _reset_advanced_color_controls(self) -> None:
        self._advanced_syncing = True
        try:
            self._adv_enabled.setChecked(False)
            self._adv_bypass.setChecked(False)
            self._adv_solo.setChecked(False)
            for key, slider, suffix in (
                ("hdr_shadow", self._adv_hdr_shadow, "%"),
                ("hdr_highlight", self._adv_hdr_highlight, "%"),
                ("log_shadow_r", self._adv_log_shadow_r, ""),
                ("log_highlight_b", self._adv_log_highlight_b, ""),
                ("hue_sat_skin", self._adv_hue_sat_skin, "%"),
                ("warper_skin", self._adv_warper_skin, "deg"),
            ):
                self._set_advanced_slider(key, slider, 0, suffix)
        finally:
            self._advanced_syncing = False
        grade = self._get_or_create_grade()
        if grade is not None:
            try:
                grade.advanced_color_toolset = {}
                if getattr(grade, "preset_id", "none") != "none":
                    grade.preset_id = "custom"
                self.grade_changed.emit(grade)
            except Exception:
                pass
        self._refresh_advanced_status()

    def _refresh_advanced_status(self) -> None:
        if not hasattr(self, "_advanced_status"):
            return
        if hasattr(self, "_adv_curve_graph"):
            self._adv_curve_graph.set_values(
                skin_sat=int(self._adv_hue_sat_skin.value()),
                shadow=int(self._adv_hdr_shadow.value()),
                highlight=int(self._adv_hdr_highlight.value()),
            )
        if hasattr(self, "_adv_warper_grid"):
            self._adv_warper_grid.set_values(
                hue_shift=int(self._adv_warper_skin.value()),
                saturation=int(self._adv_hue_sat_skin.value()),
            )
        if not self._adv_enabled.isChecked():
            self._advanced_status.setText("Advanced: off")
            return
        parts = []
        if self._adv_bypass.isChecked():
            parts.append("Bypassed")
        if self._adv_solo.isChecked():
            parts.append("Solo preview")
        if self._adv_hdr_shadow.value() or self._adv_hdr_highlight.value():
            parts.append(f"HDR S{self._adv_hdr_shadow.value()} H{self._adv_hdr_highlight.value()}")
        if self._adv_log_shadow_r.value() or self._adv_log_highlight_b.value():
            parts.append(f"Log R{self._adv_log_shadow_r.value()} B{self._adv_log_highlight_b.value()}")
        if self._adv_hue_sat_skin.value():
            parts.append(f"Skin sat {self._adv_hue_sat_skin.value()}%")
        if self._adv_warper_skin.value():
            parts.append(f"Skin warp {self._adv_warper_skin.value()}deg")
        self._advanced_status.setText(" | ".join(parts) if parts else "Advanced: armed")

    def _on_workflow_controls_changed(self, *_args) -> None:
        if self._workflow_syncing:
            return
        grade = self._get_or_create_grade()
        if grade is None:
            return
        try:
            from app.color_workflow import ColorNodeWorkflow, ColorQualifier, TrackingWindow

            existing = dict(getattr(grade, "color_workflow", None) or {})
            qualifier = ColorQualifier(
                enabled=bool(self._qual_enabled.isChecked()),
                hue_center=float(self._qual_hue.value()),
                hue_width=float(self._qual_width.value()),
                sat_min=self._percent(self._qual_sat_min),
                sat_max=self._percent(self._qual_sat_max),
                val_min=self._percent(self._qual_val_min),
                val_max=self._percent(self._qual_val_max),
                softness=self._percent(self._qual_softness),
                clean_black=self._percent(self._qual_clean_black),
                clean_white=self._percent(self._qual_clean_white),
                denoise_radius=int(self._qual_denoise.value()),
                invert=bool(self._qual_invert.isChecked()),
            )
            window = TrackingWindow(
                enabled=bool(self._window_enabled.isChecked()),
                shape=str(self._window_shape.currentData() or "ellipse"),
                x=self._percent(self._window_x),
                y=self._percent(self._window_y),
                w=max(0.01, self._percent(self._window_w)),
                h=max(0.01, self._percent(self._window_h)),
                feather=self._percent(self._window_feather),
                opacity=self._percent(self._window_opacity),
                track_object=bool(self._window_track.isChecked()),
                tracking_status="tracking" if self._window_track.isChecked() else "manual",
                tracker_id=str(existing.get("window", {}).get("tracker_id", "")) if isinstance(existing.get("window"), dict) else "",
            )
            workflow = ColorNodeWorkflow.from_dict(existing)
            data = workflow.to_dict()
            data["enabled"] = bool(qualifier.enabled or window.enabled or not workflow.curves.is_identity())
            data["qualifier"] = qualifier.to_dict()
            data["window"] = window.to_dict()
            if not data["enabled"]:
                grade.color_workflow = {}
            else:
                grade.color_workflow = data
            self._refresh_workflow_status()
            self.grade_changed.emit(grade)
        except Exception:
            pass

    def _percent(self, slider: QSlider) -> float:
        return max(0.0, min(1.0, float(slider.value()) / 100.0))

    def _refresh_workflow_status(self) -> None:
        if not hasattr(self, "_workflow_status"):
            return
        parts = []
        if self._qual_enabled.isChecked():
            parts.append(
                f"Key H{self._qual_hue.value()} W{self._qual_width.value()} "
                f"CB{self._qual_clean_black.value()} CW{self._qual_clean_white.value()}"
            )
        if self._window_enabled.isChecked():
            shape = self._window_shape.currentText()
            track = " tracking" if self._window_track.isChecked() else ""
            parts.append(f"{shape} window{track}")
        self._workflow_status.setText(" | ".join(parts) if parts else "Mask: off")

    def update_frame(self, rgb, grade) -> None:
        """Push a new frame to the scopes and update the grade display."""
        if grade is not None:
            self.update_grade(grade)
        if rgb is not None:
            try:
                self._scope_primary.update_frame(rgb)
                self._scope_secondary.update_frame(rgb)
                if hasattr(self, "_adv_split_preview"):
                    self._adv_split_preview.update_frame(rgb, grade)
                self._update_scope_warning_status(rgb)
            except Exception:
                pass

    def _update_scope_warning_status(self, rgb) -> None:
        if not hasattr(self, "_scope_warning_status"):
            return
        try:
            from app.color_scopes import scope_quality_diagnostics
            from app.color_workflow import scope_accuracy_report

            settings = {}
            if self._editor is not None:
                settings = (getattr(self._editor, "_project_settings", {}) or {}).get("color_management", {})
            diag = scope_quality_diagnostics(rgb, settings)
            qa = getattr(self, "_scope_accuracy_report_cache", None)
            if not isinstance(qa, dict):
                qa = scope_accuracy_report()
                self._scope_accuracy_report_cache = qa
            if not qa.get("ok", False):
                diag = dict(diag)
                diag["warnings"] = list(diag.get("warnings", []) or []) + list(qa.get("warnings", []) or [])
            apply_state_to_label(self._scope_warning_status, scope_status_state(diag))
            try:
                self._scope_warning_status.setToolTip(
                    f"{self._scope_warning_status.toolTip()}\n"
                    f"Scope QA: {'OK' if qa.get('ok') else 'Review'} | "
                    f"{', '.join(str(v) for v in list(qa.get('qa_gates', []) or [])[:3])}"
                )
            except Exception:
                pass
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

    def _on_primary_slider(self, key: str, val: float) -> None:
        grade = self._get_or_create_grade()
        if grade is None:
            return
        setattr(grade, key, int(round(float(val))))
        if getattr(grade, "preset_id", "none") != "none":
            grade.preset_id = "custom"
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
            if callable(track):
                track = track()
            if track is not None:
                if getattr(track, "color_grade", None) is None:
                    track.color_grade = ColorGrade()
                return track.color_grade
        except Exception:
            pass
        return None
