"""Animation timeline widget for Spine editor.

Layout:
  ┌─ transport bar ─────────────────────────────────────────────────┐
  │ [play/pause] [stop]  00:00.000  [anim]  dur: 2.00s  30fps      │
  ├─ ruler ──────────────────────────────────────────────────────────┤
  │ bone name │ 0    0.25    0.5    0.75    1.0   ...               │
  │ hip       │      ◆       ◆       ◆                              │
  │ spine     │  ◆                                ◆                 │
  └──────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations
import math
from typing import Optional

from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QTimer, Signal
from PySide6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QPainterPath, QMouseEvent, QAction,
)
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
    QComboBox, QScrollArea, QSizePolicy, QMenu,
)
from app.icons import app_icon, icon_size
from app.style import studio_chrome_qss
from app.spine_editor.spine_data import SpineSkeleton, Animation


_DARK = QColor("#0B0D16")
_RULER_BG = QColor("#111421")
_BONE_BG = QColor("#121727")
_BONE_ALT = QColor("#161B2E")
_GRID = QColor("#30384F")
_KEYFRAME = QColor("#FFBD59")
_KEYFRAME_SEL = QColor("#FF8057")
_PLAYHEAD = QColor("#8A7CFF")
_TEXT = QColor("#E8EAF4")
_SUBTEXT = QColor("#A7ADC2")

RULER_H = 22
ROW_H = 20
LEFT_W = 100


class _TimelineCanvas(QWidget):
    """Scrollable canvas: ruler + keyframe rows."""

    time_scrubbed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._anim: Optional[Animation] = None
        self._time: float = 0.0
        self._zoom: float = 200.0       # px / second
        self._scroll_x: float = 0.0    # horizontal scroll offset in px
        self._bone_rows: list[str] = []  # bone names with keyframes

        self._selected_kf: tuple | None = None
        self._dragging_kf: bool = False
        self._drag_kf_start_x: float = 0.0
        self._drag_kf_orig_time: float = 0.0
        self._drag_bone: str = ""
        self._drag_prop: str = ""
        self._drag_kf_idx: int = -1

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(RULER_H + ROW_H * 4)

    def set_animation(self, skel: SpineSkeleton, anim: Optional[Animation]) -> None:
        self._skeleton = skel
        self._anim = anim
        self._bone_rows = []
        if anim:
            seen: set[str] = set()
            for tl in anim.timelines:
                if tl.bone not in seen:
                    seen.add(tl.bone)
                    self._bone_rows.append(tl.bone)
        total_rows = max(4, len(self._bone_rows))
        self.setFixedHeight(RULER_H + ROW_H * total_rows + 4)
        self.update()

    def set_time(self, t: float) -> None:
        self._time = t
        self.update()

    def _duration(self) -> float:
        return self._anim.duration if self._anim else 1.0

    def _time_to_x(self, t: float) -> float:
        return LEFT_W + (t * self._zoom) - self._scroll_x

    def _x_to_time(self, x: float) -> float:
        return ((x - LEFT_W + self._scroll_x) / self._zoom)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        p.fillRect(0, 0, w, h, _DARK)

        self._draw_ruler(p, w)
        self._draw_rows(p, w)
        self._draw_playhead(p)

        p.end()

    def _draw_ruler(self, p: QPainter, w: int):
        p.fillRect(0, 0, w, RULER_H, _RULER_BG)

        dur = self._duration()
        # Choose tick spacing
        raw_step = 50.0 / self._zoom
        steps = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
        step = next((s for s in steps if s >= raw_step), steps[-1])

        f = QFont("Segoe UI", 8)
        p.setFont(f)
        t = 0.0
        while t <= dur + step * 0.5:
            x = self._time_to_x(t)
            if LEFT_W <= x <= w:
                is_major = round(t / step) % 4 == 0 or step >= 0.5
                p.setPen(QPen(_GRID if not is_major else QColor("#4a4a60"), 1))
                p.drawLine(int(x), RULER_H - (12 if is_major else 6), int(x), RULER_H)
                if is_major:
                    secs = int(t)
                    frac = round((t - secs) * 100)
                    lbl = f"{secs}:{frac:02d}"
                    p.setPen(_SUBTEXT)
                    p.drawText(int(x) + 2, RULER_H - 8, lbl)
            t = round(t + step, 6)

        # Bone name column header
        p.fillRect(0, 0, LEFT_W, RULER_H, _RULER_BG)
        p.setPen(_SUBTEXT)
        p.drawText(4, RULER_H - 7, "BONE")
        p.setPen(QPen(QColor("#30384F"), 1))
        p.drawLine(LEFT_W, 0, LEFT_W, RULER_H)

    def _draw_rows(self, p: QPainter, w: int):
        if not self._anim:
            return
        f = QFont("Segoe UI", 9)
        p.setFont(f)

        for i, bone_name in enumerate(self._bone_rows):
            y = RULER_H + i * ROW_H
            bg = _BONE_BG if i % 2 == 0 else _BONE_ALT
            p.fillRect(0, y, w, ROW_H, bg)

            # Bone name
            p.setPen(_TEXT)
            p.drawText(4, y + ROW_H - 5, bone_name)
            p.setPen(QPen(QColor("#30384F"), 1))
            p.drawLine(LEFT_W, y, LEFT_W, y + ROW_H)

            # Keyframes
            for tl in self._anim.timelines:
                if tl.bone != bone_name:
                    continue
                for j, kf in enumerate(tl.keyframes):
                    x = self._time_to_x(kf.time)
                    if LEFT_W <= x <= w:
                        cy = y + ROW_H // 2
                        is_sel = (
                            self._selected_kf is not None
                            and self._selected_kf[0] == bone_name
                            and self._selected_kf[1] == tl.property
                            and self._selected_kf[2] == j
                        )
                        if is_sel:
                            self._draw_diamond(p, x, cy, 7, _KEYFRAME_SEL)
                        else:
                            self._draw_diamond(p, x, cy, 5, _KEYFRAME)

        # Row separator lines
        p.setPen(QPen(QColor("#30384F"), 1))
        for i in range(len(self._bone_rows) + 1):
            y = RULER_H + i * ROW_H
            p.drawLine(LEFT_W, y, w, y)

    def _draw_diamond(self, p: QPainter, cx: float, cy: float, r: float, color: QColor):
        path = QPainterPath()
        path.moveTo(cx, cy - r)
        path.lineTo(cx + r, cy)
        path.lineTo(cx, cy + r)
        path.lineTo(cx - r, cy)
        path.closeSubpath()
        p.setBrush(QBrush(color))
        p.setPen(QPen(color.lighter(130), 1))
        p.drawPath(path)

    def _draw_playhead(self, p: QPainter):
        x = int(self._time_to_x(self._time))
        p.setPen(QPen(_PLAYHEAD, 2))
        p.drawLine(x, 0, x, self.height())
        # Triangle at top
        path = QPainterPath()
        path.moveTo(x, RULER_H)
        path.lineTo(x - 5, 0)
        path.lineTo(x + 5, 0)
        path.closeSubpath()
        p.setBrush(QBrush(_PLAYHEAD))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)

    def _kf_at(self, sx: float, sy: float) -> tuple | None:
        """Return (bone, prop, kf_idx) if (sx, sy) is within 6px of a keyframe diamond."""
        if not self._anim:
            return None
        for i, bone_name in enumerate(self._bone_rows):
            row_cy = RULER_H + i * ROW_H + ROW_H // 2
            if abs(sy - row_cy) > ROW_H:
                continue
            for tl in self._anim.timelines:
                if tl.bone != bone_name:
                    continue
                for j, kf in enumerate(tl.keyframes):
                    kx = self._time_to_x(kf.time)
                    if abs(sx - kx) < 7:
                        return (bone_name, tl.property, j)
        return None

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            sx, sy = e.position().x(), e.position().y()
            hit = self._kf_at(sx, sy)
            if hit:
                self._selected_kf = hit
                self._dragging_kf = True
                self._drag_bone, self._drag_prop, self._drag_kf_idx = hit
                self._drag_kf_start_x = sx
                # Store original time
                for tl in self._anim.timelines:  # type: ignore[union-attr]
                    if tl.bone == self._drag_bone and tl.property == self._drag_prop:
                        self._drag_kf_orig_time = tl.keyframes[self._drag_kf_idx].time
                        break
                self.update()
            elif sx >= LEFT_W:
                self._selected_kf = None
                t = max(0.0, min(self._duration(), self._x_to_time(sx)))
                self.time_scrubbed.emit(t)
                self.update()

    def mouseMoveEvent(self, e: QMouseEvent):
        if e.buttons() & Qt.MouseButton.LeftButton:
            sx = e.position().x()
            if self._dragging_kf and self._anim:
                dx = sx - self._drag_kf_start_x
                new_time = max(0.0, min(
                    self._duration(),
                    self._drag_kf_orig_time + dx / self._zoom,
                ))
                for tl in self._anim.timelines:
                    if tl.bone == self._drag_bone and tl.property == self._drag_prop:
                        tl.keyframes[self._drag_kf_idx].time = new_time
                        break
                self.update()
            elif sx >= LEFT_W:
                t = max(0.0, min(self._duration(), self._x_to_time(sx)))
                self.time_scrubbed.emit(t)

    def mouseReleaseEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton and self._dragging_kf and self._anim:
            # Re-sort keyframes by time after drag
            for tl in self._anim.timelines:
                if tl.bone == self._drag_bone and tl.property == self._drag_prop:
                    dropped_time = tl.keyframes[self._drag_kf_idx].time
                    tl.keyframes.sort(key=lambda k: k.time)
                    # Update selected index after sort
                    new_idx = next(
                        (idx for idx, k in enumerate(tl.keyframes)
                         if abs(k.time - dropped_time) < 1e-9),
                        self._drag_kf_idx,
                    )
                    self._selected_kf = (self._drag_bone, self._drag_prop, new_idx)
                    self._drag_kf_idx = new_idx
                    break
            self._dragging_kf = False
            self.update()

    def contextMenuEvent(self, e):
        sx, sy = e.pos().x(), e.pos().y()
        hit = self._kf_at(float(sx), float(sy))

        menu = QMenu(self)
        menu.setStyleSheet(studio_chrome_qss(""))

        if hit:
            bone_name, prop, kf_idx = hit
            act_del = QAction("키프레임 삭제", self)

            def _delete_kf():
                if not self._anim:
                    return
                for tl in self._anim.timelines:
                    if tl.bone == bone_name and tl.property == prop:
                        if 0 <= kf_idx < len(tl.keyframes):
                            tl.keyframes.pop(kf_idx)
                        break
                if self._selected_kf == hit:
                    self._selected_kf = None
                self.update()

            act_del.triggered.connect(_delete_kf)
            menu.addAction(act_del)
        else:
            # Identify which bone row was right-clicked
            clicked_bone: str | None = None
            clicked_prop: str | None = None
            for i, bone_name in enumerate(self._bone_rows):
                row_y = RULER_H + i * ROW_H
                if row_y <= sy < row_y + ROW_H and sx >= LEFT_W:
                    clicked_bone = bone_name
                    # Use first timeline property for this bone, or default
                    if self._anim:
                        for tl in self._anim.timelines:
                            if tl.bone == bone_name:
                                clicked_prop = tl.property
                                break
                    break

            if clicked_bone and self._anim:
                act_add = QAction("키프레임 추가", self)
                _bone = clicked_bone
                _prop = clicked_prop

                def _add_kf():
                    if not self._anim or not _bone or not _prop:
                        return
                    from app.spine_editor.spine_data import BoneKeyframe
                    for tl in self._anim.timelines:
                        if tl.bone == _bone and tl.property == _prop:
                            new_kf = BoneKeyframe(time=self._time, value=0.0)
                            tl.keyframes.append(new_kf)
                            tl.keyframes.sort(key=lambda k: k.time)
                            break
                    self.update()

                act_add.triggered.connect(_add_kf)
                menu.addAction(act_add)

        if menu.actions():
            menu.exec(e.globalPos())

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            pivot_t = self._x_to_time(e.position().x())
            self._zoom = max(20, min(2000, self._zoom * factor))
            self._scroll_x = LEFT_W + pivot_t * self._zoom - e.position().x()
            self._scroll_x = max(0, self._scroll_x)
        else:
            self._scroll_x = max(0, self._scroll_x - e.angleDelta().y() * 0.5)
        self.update()


class AnimTimeline(QWidget):
    """Full animation timeline panel: transport + canvas."""

    time_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._skeleton: Optional[SpineSkeleton] = None
        self._anim: Optional[Animation] = None
        self._time: float = 0.0
        self._playing: bool = False
        self._fps: int = 30

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self.setMaximumHeight(260)
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Transport bar
        transport = QWidget()
        transport.setFixedHeight(32)
        transport.setStyleSheet("background:#111421;")
        tlay = QHBoxLayout(transport)
        tlay.setContentsMargins(6, 2, 6, 2)
        tlay.setSpacing(4)

        _btn_ss = (
            "QPushButton{background:rgba(255,255,255,18);color:#E8EAF4;border:1px solid #37405A;"
            "border-radius:11px;padding:4px 9px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;color:#fff;}"
            "QPushButton:checked{background:#6F5CFF;color:#fff;border-color:#C2BAFF;}"
        )

        self._play_btn = QPushButton("")
        self._play_btn.setCheckable(True)
        self._set_play_icon(False)
        self._play_btn.setStyleSheet(_btn_ss)
        self._play_btn.clicked.connect(self._on_play_clicked)
        tlay.addWidget(self._play_btn)

        stop_btn = QPushButton("")
        stop_btn.setIcon(app_icon("stop", size=14, color="#FFFFFF"))
        stop_btn.setIconSize(icon_size(14))
        stop_btn.setStyleSheet(_btn_ss)
        stop_btn.clicked.connect(self._stop)
        tlay.addWidget(stop_btn)

        self._time_lbl = QLabel("00:00.000")
        self._time_lbl.setStyleSheet("color:#E8EAF4;font-size:11px;min-width:70px;font-weight:700;")
        tlay.addWidget(self._time_lbl)

        lbl = QLabel("애니메이션:")
        lbl.setStyleSheet("color:#A7ADC2;font-size:10px;")
        tlay.addWidget(lbl)

        self._anim_combo = QComboBox()
        self._anim_combo.setStyleSheet(studio_chrome_qss(
            "QComboBox{font-size:11px;min-width:120px;}"
        ))
        self._anim_combo.currentTextChanged.connect(self._on_anim_selected)
        tlay.addWidget(self._anim_combo)

        self._dur_lbl = QLabel("dur: —")
        self._dur_lbl.setStyleSheet("color:#A7ADC2;font-size:10px;")
        tlay.addWidget(self._dur_lbl)

        tlay.addStretch()
        lay.addWidget(transport)

        # Canvas (scrollable)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea{border:none;background:#0B0D16;}")

        self._canvas = _TimelineCanvas()
        self._canvas.time_scrubbed.connect(self._on_scrub)
        scroll.setWidget(self._canvas)
        lay.addWidget(scroll)

    def set_skeleton(self, skel: SpineSkeleton) -> None:
        self._skeleton = skel
        self._stop()
        self._anim_combo.blockSignals(True)
        self._anim_combo.clear()
        if skel and skel.animations:
            for name in sorted(skel.animations.keys()):
                self._anim_combo.addItem(name)
            self._anim_combo.blockSignals(False)
            self._on_anim_selected(self._anim_combo.currentText())
        else:
            self._anim_combo.blockSignals(False)
            self._canvas.set_animation(skel, None)
            self._dur_lbl.setText("dur: —")

    def _on_anim_selected(self, name: str) -> None:
        if not self._skeleton:
            return
        self._anim = self._skeleton.animations.get(name)
        self._canvas.set_animation(self._skeleton, self._anim)
        if self._anim:
            self._dur_lbl.setText(f"dur: {self._anim.duration:.2f}s")
        self._set_time(0.0)

    def _set_play_icon(self, playing: bool) -> None:
        self._play_btn.setText("")
        self._play_btn.setIcon(app_icon("pause" if playing else "play", size=14, color="#FFFFFF"))
        self._play_btn.setIconSize(icon_size(14))

    def _on_play_clicked(self, checked: bool) -> None:
        if checked:
            self._playing = True
            self._set_play_icon(True)
            interval = max(1, 1000 // self._fps)
            self._timer.start(interval)
        else:
            self._playing = False
            self._set_play_icon(False)
            self._timer.stop()

    def _stop(self) -> None:
        self._playing = False
        self._play_btn.setChecked(False)
        self._set_play_icon(False)
        self._timer.stop()
        self._set_time(0.0)

    def _tick(self) -> None:
        if not self._anim:
            return
        dt = 1.0 / self._fps
        new_t = self._time + dt
        if new_t > self._anim.duration:
            if self._anim.duration < 0.5:
                new_t = self._anim.duration
                self._playing = False
                self._play_btn.setChecked(False)
                self._set_play_icon(False)
                self._timer.stop()
            else:
                new_t = 0.0  # loop
        self._set_time(new_t)

    def _on_scrub(self, t: float) -> None:
        self._set_time(t)

    def _set_time(self, t: float) -> None:
        self._time = t
        self._canvas.set_time(t)
        secs = int(t)
        ms = int((t - secs) * 1000)
        self._time_lbl.setText(f"{secs:02d}:{ms:03d}")
        self.time_changed.emit(t)
