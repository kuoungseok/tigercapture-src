"""Live2D editor window — viewport + layer panel + inspector."""
from __future__ import annotations
import os
import json
import glob
import time
from typing import Optional


def _qt_valid(obj) -> bool:
    """Return False when a PySide wrapper points at a deleted C++ object."""
    if obj is None:
        return False
    try:
        from shiboken6 import isValid
        return bool(isValid(obj))
    except Exception:
        return True

from PySide6.QtCore import Qt, QTimer, Signal, QSize, QRect, QMimeData, QByteArray, QUrl
from PySide6.QtGui import (
    QColor, QPixmap, QImage, QPainter, QPen, QBrush, QFont, QLinearGradient,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QSlider, QScrollArea, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QSizePolicy, QFrame, QAbstractItemView,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import FONT_FAMILY, editor_scrollbar_qss, studio_chrome_qss

_SAMPLES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "resources", "live2d_samples")
)
_MODEL_PATH_CACHE: Optional[list[str]] = None
_MODEL_ICON_CACHE: dict[str, object] = {}
_MODEL_SUPPORT_CACHE: dict[str, str] = {}

_INSPECTOR_PARAMS = [
    ("ParamAngleX",     "머리 좌우",   -30,  30),
    ("ParamAngleY",     "머리 상하",   -30,  30),
    ("ParamAngleZ",     "머리 기울기", -30,  30),
    ("ParamEyeLOpen",   "왼눈 열림",     0,   2),
    ("ParamEyeROpen",   "오른눈 열림",   0,   2),
    ("ParamEyeBallX",   "눈동자 좌우",  -1,   1),
    ("ParamEyeBallY",   "눈동자 상하",  -1,   1),
    ("ParamMouthOpenY", "입 열림",       0,   1),
    ("ParamMouthForm",  "입 모양",      -1,   1),
    ("ParamBodyAngleX", "몸 좌우",    -10,  10),
    ("ParamBreath",     "호흡",          0,   1),
]

_DARK  = "#08090C"
_PANEL = "#101114"
_CARD  = "#15171C"
_RULE  = "#252A34"
_MUTED = "#9AA1AE"
_TEXT  = "#EEF1F6"

_BTN = (
    "QPushButton{background:rgba(255,255,255,7);color:#DDE2EA;border:1px solid rgba(178,186,202,26);"
    "border-radius:6px;padding:6px 10px;font-size:10px;font-weight:620;}"
    "QPushButton:hover{background:rgba(255,255,255,12);border-color:rgba(220,225,238,72);color:#FFFFFF;}"
    "QPushButton:pressed{background:rgba(255,255,255,10);border-color:rgba(238,242,250,104);}"
    "QPushButton:disabled{color:#626A76;background:rgba(255,255,255,4);border-color:rgba(178,186,202,12);}"
)
_BTN_ICON = (
    "QPushButton{background:rgba(255,255,255,6);color:#DDE2EA;border:1px solid rgba(178,186,202,24);"
    "border-radius:6px;font-size:13px;padding:0;}"
    "QPushButton:hover{background:rgba(255,255,255,12);color:#FFFFFF;border-color:rgba(220,225,238,68);}"
    "QPushButton:pressed{background:rgba(255,255,255,10);border-color:rgba(238,242,250,104);}"
)
_SECTION = (
    f"QLabel{{color:{_MUTED};font-size:9px;font-weight:620;"
    "letter-spacing:0px;padding:7px 0 3px 0;}}"
)


# ── viewport (QLabel-based, no GL context) ────────────────────────────────────
#
# Renders via _OffscreenRenderer → PIL → QPixmap → QLabel.
# Keeps Live2D GL isolated to a single context (the offscreen renderer),
# preventing any interaction with the main video preview's GL context.

class Live2DViewport(QWidget):
    """Pixmap-based Live2D preview — no QOpenGLWidget, no GL context conflicts."""

    model_loaded    = Signal(str, list, list, list, list)
    error_occurred  = Signal(str)
    bounds_computed = Signal(int, bool)
    first_frame_ready = Signal()

    _FPS_MS = 33   # ~30 fps; FBO readback is the bottleneck, not motion timing.
    _MAX_RENDER_DIM = 720

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model_path: Optional[str] = None
        self._preview_clip = None
        self._pixmap: Optional[QPixmap] = None
        self._bg = QColor(26, 26, 41)
        self._pos_ms: int = 0
        self._has_first_frame = False
        self._render_error_reported = False
        self._load_token = 0
        self._first_frame_model_path = ""
        self._timer = QTimer(self)
        self._timer.setInterval(self._FPS_MS)
        self._timer.timeout.connect(self._tick)
        self.setMinimumSize(320, 320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ── public API ────────────────────────────────────────────────────────────

    def load_model(self, path: str) -> None:
        from app.live2d.actor_track import Live2DActorClip
        source_path = path
        try:
            from app.live2d.compat import normalize_live2d_model_path
            runtime_path = normalize_live2d_model_path(path) or path
        except Exception:
            runtime_path = path
        if not runtime_path:
            self.unload_model()
            return
        self._load_token += 1
        token = self._load_token
        self._evict_preview_model()
        self._model_path = source_path
        self._first_frame_model_path = ""
        self._pixmap = None
        self._has_first_frame = False
        self._render_error_reported = False
        if not self._timer.isActive():
            self._timer.start()
        self._preview_clip = Live2DActorClip(model_path=runtime_path)
        self._pos_ms = 0
        try:
            name, motions, exprs, parts, textures = self._parse_meta(source_path)
            if motions:
                idle = next(
                    ((g, i) for g, i, lbl in motions if "idle" in lbl.lower()),
                    (motions[0][0], motions[0][1]),
                )
                self._preview_clip.motion_group = idle[0]
                self._preview_clip.motion_idx = idle[1]
            else:
                self._preview_clip.motion_group = ""
                self._preview_clip.motion_idx = 0
            load_path = self._model_path

            def _emit_loaded() -> None:
                if (
                    not _qt_valid(self)
                    or token != self._load_token
                    or self._model_path != load_path
                ):
                    return
                self.model_loaded.emit(name, motions, exprs, parts, textures)

            QTimer.singleShot(0, _emit_loaded)
        except Exception as e:
            self.error_occurred.emit(str(e))

    def unload_model(self) -> None:
        self._load_token += 1
        self._timer.stop()
        self._evict_preview_model()
        self._model_path = None
        self._preview_clip = None
        self._pixmap = None
        self._has_first_frame = False
        self._render_error_reported = False
        self._first_frame_model_path = ""
        self._pos_ms = 0
        self.update()

    def current_model_path(self) -> str:
        return self._model_path or ""

    def first_frame_model_path(self) -> str:
        return self._first_frame_model_path or ""

    def play_motion(self, group: str, index: int) -> None:
        if self._preview_clip:
            self._preview_clip.motion_group = group
            self._preview_clip.motion_idx   = index
            self._preview_clip.reset()
            self._pos_ms = 0

    def set_expression(self, expr_id: str) -> None:
        m = self._offscreen_model()
        if m:
            try:
                m.SetExpression(expr_id)
            except Exception:
                pass

    def set_parameter(self, param_id: str, value: float) -> None:
        m = self._offscreen_model()
        if m:
            try:
                m.SetParameterValue(param_id, value)
            except Exception:
                pass

    def set_bg_color(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        self._bg = QColor(int(r * 255), int(g * 255), int(b * 255))
        self.update()

    def set_part_visible(self, part_idx: int, visible: bool) -> None:
        m = self._offscreen_model()
        if m:
            try:
                m.SetPartOpacity(part_idx, 1.0 if visible else 0.0)
            except Exception:
                pass

    def highlight_part(self, part_idx: int) -> None:
        self.bounds_computed.emit(part_idx, False)

    def clear_highlight(self) -> None:
        pass

    # ── frame update ──────────────────────────────────────────────────────────

    def _tick(self) -> None:
        token = self._load_token
        clip = self._preview_clip
        model_path = self._model_path or ""
        if not clip or not clip.model_path:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        try:
            rw, rh = self._preview_render_size(w, h)
            img = clip.render_frame(rw, rh, self._pos_ms)
            if (
                token != self._load_token
                or clip is not self._preview_clip
                or model_path != (self._model_path or "")
            ):
                return
            if img is not None:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qi = QImage(
                    data,
                    img.width,
                    img.height,
                    img.width * 4,
                    QImage.Format.Format_RGBA8888,
                ).copy()
                self._pixmap = QPixmap.fromImage(qi)
                if not self._has_first_frame:
                    self._has_first_frame = True
                    self._first_frame_model_path = model_path
                    self.first_frame_ready.emit()
                self.update()
        except Exception as e:
            print(f"[live2d viewport] {e}")
            if not self._render_error_reported:
                self._render_error_reported = True
                self.error_occurred.emit(str(e))
        self._pos_ms += self._FPS_MS

    def _preview_render_size(self, w: int, h: int) -> tuple[int, int]:
        max_dim = max(w, h)
        if max_dim <= self._MAX_RENDER_DIM:
            return w, h
        scale = self._MAX_RENDER_DIM / max_dim
        return max(1, int(w * scale)), max(1, int(h * scale))

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bg = QLinearGradient(0, 0, 0, max(1, self.height()))
        bg.setColorAt(0.0, self._bg.lighter(112))
        bg.setColorAt(1.0, self._bg.darker(118))
        p.fillRect(self.rect(), bg)
        if self._pixmap:
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            p.drawPixmap(
                (self.width()  - scaled.width())  // 2,
                (self.height() - scaled.height()) // 2,
                scaled,
            )
        frame = self.rect().adjusted(8, 8, -9, -9)
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(frame, 8, 8)
        p.end()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _offscreen_model(self):
        if not self._preview_clip or not self._preview_clip.model_path:
            return None
        from app.live2d.actor_track import _OffscreenRenderer
        return _OffscreenRenderer.instance()._models.get(
            (self._preview_clip.model_path, id(self._preview_clip))
        )

    def _evict_preview_model(self) -> None:
        clip = self._preview_clip
        if not clip or not clip.model_path:
            return
        try:
            from app.live2d.actor_track import _OffscreenRenderer
            _OffscreenRenderer.instance().evict_model(clip.model_path, id(clip))
        except Exception:
            pass

    def _parse_meta(self, path: str):
        motions, exprs, parts, textures = [], [], [], []
        source_path = path
        try:
            from app.live2d.compat import normalize_live2d_model_path
            path = normalize_live2d_model_path(path) or path
        except Exception:
            pass
        base = os.path.dirname(path)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            refs = data.get("FileReferences", {})
            for grp, items in refs.get("Motions", {}).items():
                for i, item in enumerate(items):
                    file_ref = item.get("File", "") if isinstance(item, dict) else ""
                    if not isinstance(file_ref, str) or not file_ref:
                        continue
                    if not file_ref.lower().replace("\\", "/").endswith(".motion3.json"):
                        continue
                    motion_path = os.path.normpath(os.path.join(base, file_ref))
                    if not os.path.exists(motion_path):
                        continue
                    fname = os.path.basename(file_ref)
                    lbl   = fname.replace(".motion3.json", "")
                    motions.append((grp, i, f"{grp}/{lbl}" if grp else lbl))
            for ex in refs.get("Expressions", []):
                eid = ex.get("Name") or os.path.basename(
                    ex.get("File", "")).replace(".exp3.json", "")
                exprs.append(eid)
            for tex in refs.get("Textures", []):
                textures.append(os.path.normpath(os.path.join(base, tex)))
        except Exception:
            pass
        name = os.path.basename(source_path).replace(".model3.json","").replace(".model3","")
        return name, motions, exprs, parts, textures


# ── layer row ─────────────────────────────────────────────────────────────────

class _LayerRow(QWidget):
    """One row in the layer panel: eye · thumbnail · name · reload."""

    selected    = Signal(int)   # part_idx
    visibility  = Signal(int, bool)
    reload_req  = Signal()

    _THUMB = 40
    _H     = 52

    def __init__(self, part_idx: int, name: str, thumb_px: Optional[QPixmap],
                 parent=None):
        super().__init__(parent)
        self._idx     = part_idx
        self._visible = True
        self._selected = False
        self.setFixedHeight(self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build(name, thumb_px)

    def _build(self, name: str, thumb_px: Optional[QPixmap]):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(6)

        # Eye toggle
        self._eye = QPushButton("👁")
        self._eye.setFixedSize(22, 22)
        self._eye.setStyleSheet(_BTN_ICON)
        self._eye.setToolTip("레이어 보이기/숨기기")
        self._eye.clicked.connect(self._toggle_visibility)
        lay.addWidget(self._eye)

        # Thumbnail
        thumb_lbl = QLabel()
        thumb_lbl.setFixedSize(self._THUMB, self._THUMB)
        thumb_lbl.setStyleSheet(f"background:#1a1a2e;border-radius:3px;")
        if thumb_px:
            thumb_lbl.setPixmap(
                thumb_px.scaled(self._THUMB, self._THUMB,
                                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                Qt.TransformationMode.SmoothTransformation)
            )
        else:
            # Colored placeholder derived from part index
            ph = QPixmap(self._THUMB, self._THUMB)
            hue = (self._idx * 47) % 360
            ph.fill(QColor.fromHsv(hue, 120, 160))
            thumb_lbl.setPixmap(ph)
        thumb_lbl.setScaledContents(True)
        lay.addWidget(thumb_lbl)

        # Name
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(f"color:{_TEXT};font-size:11px;")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_lbl.setToolTip(name)
        lay.addWidget(name_lbl, 1)

        # Reload
        rel_btn = QPushButton("↺")
        rel_btn.setFixedSize(20, 20)
        rel_btn.setStyleSheet(_BTN_ICON)
        rel_btn.setToolTip("모델 다시 불러오기")
        rel_btn.clicked.connect(self.reload_req)
        lay.addWidget(rel_btn)

    def set_selected(self, on: bool):
        self._selected = on
        self.setStyleSheet(
            f"background:{'#1e2040' if on else 'transparent'};"
            "border-radius:4px;"
        )

    def set_detected(self, found: bool):
        """Mark whether this part was locatable via HitPart."""
        tip = "" if found else " (위치 감지 불가)"
        self.setToolTip(tip)
        # Dim the eye icon slightly for undetectable parts
        self._eye.setStyleSheet(
            _BTN_ICON if found
            else _BTN_ICON.replace("#E8EAF4", "#6F7484").replace("#30384F", "#252B3A")
        )

    def _toggle_visibility(self):
        self._visible = not self._visible
        self._eye.setText("👁" if self._visible else "🚫")
        self._eye.setStyleSheet(
            _BTN_ICON if self._visible
            else _BTN_ICON.replace("#E8EAF4", "#6F7484").replace("#30384F", "#252B3A")
        )
        self.visibility.emit(self._idx, self._visible)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._idx)
        super().mousePressEvent(event)


# ── layer panel ───────────────────────────────────────────────────────────────

class _LayerPanel(QWidget):
    """Scrollable list of _LayerRow widgets."""

    part_selected = Signal(int)   # part index
    part_visible  = Signal(int, bool)
    reload_model  = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._inner = QWidget()
        self._inner_lay = QVBoxLayout(self._inner)
        self._inner_lay.setContentsMargins(4, 4, 4, 4)
        self._inner_lay.setSpacing(2)
        self._inner_lay.addStretch(1)

        scroll.setWidget(self._inner)
        lay.addWidget(scroll)

        self._rows: list[_LayerRow] = []
        self._selected_idx = -1

    def populate(self, part_names: list[str], thumb_px: Optional[QPixmap]):
        # Clear old rows
        for r in self._rows:
            r.setParent(None)
            r.deleteLater()
        self._rows.clear()
        self._selected_idx = -1

        # Remove stretch
        while self._inner_lay.count():
            self._inner_lay.takeAt(0)

        for i, name in enumerate(part_names):
            row = _LayerRow(i, name, thumb_px)
            row.selected.connect(self._on_row_selected)
            row.visibility.connect(self.part_visible)
            row.reload_req.connect(self.reload_model)
            self._inner_lay.addWidget(row)
            self._rows.append(row)

        self._inner_lay.addStretch(1)

    def _on_row_selected(self, idx: int):
        if self._selected_idx >= 0 and self._selected_idx < len(self._rows):
            self._rows[self._selected_idx].set_selected(False)
        self._selected_idx = idx
        if 0 <= idx < len(self._rows):
            self._rows[idx].set_selected(True)
        self.part_selected.emit(idx)


# ── inspector helpers ─────────────────────────────────────────────────────────

def _section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(_SECTION)
    return lbl


def _h_rule() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{_RULE};")
    return f


# ── main editor window ────────────────────────────────────────────────────────

class Live2DEditorWindow(QWidget):
    """Live2D editor: layer panel + viewport + inspector."""

    def __init__(self, parent=None, *, autoload_sample: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Live2D 에디터 — TigerCapture")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1200, 740)
        self.setStyleSheet(studio_chrome_qss(
            f"QWidget{{background:{_DARK};color:{_TEXT};font-family:{FONT_FAMILY};font-size:12px;}}"
            f"QWidget#Live2DLeftPane,QWidget#Live2DRightPane{{background:{_PANEL};border:none;}}"
            f"QWidget#Live2DCenterPane{{background:{_DARK};border:none;}}"
            f"QTreeWidget{{background:{_PANEL};border:1px solid rgba(178,186,202,18);border-radius:6px;outline:none;}}"
            f"QTreeWidget::item{{padding:3px 4px;border-radius:3px;color:{_TEXT};}}"
            f"QTreeWidget::item:hover{{background:rgba(255,255,255,9);}}"
            f"QTreeWidget::item:selected{{background:#252A31;color:#fff;border:1px solid rgba(238,242,250,60);}}"
            f"QListWidget{{background:{_PANEL};border:1px solid rgba(178,186,202,18);border-radius:6px;outline:none;}}"
            f"QListWidget::item{{padding:3px 6px;border-radius:3px;color:{_TEXT};}}"
            f"QListWidget::item:hover{{background:rgba(255,255,255,9);}}"
            f"QListWidget::item:selected{{background:#252A31;color:#fff;border:1px solid rgba(238,242,250,60);}}"
            "QSlider::groove:horizontal{background:#292D31;height:2px;border-radius:1px;}"
            "QSlider::handle:horizontal{background:#A1A9B3;border:1px solid #D5D9DF;width:10px;height:10px;"
            "margin:-4px 0;border-radius:5px;}"
            "QSlider::handle:horizontal:hover{background:#A6B7CD;border-color:#FFFFFF;}"
            "QSlider::sub-page:horizontal{background:#7A8797;border-radius:1px;}"
            "QSlider::add-page:horizontal{background:#292D31;border-radius:1px;}"
            + editor_scrollbar_qss()
        ))

        self._motions: list[tuple] = []
        self._current_motion_idx = -1
        self._param_sliders: dict[str, tuple] = {}  # id → (slider, val_lbl)
        self._current_model_path: Optional[str] = None
        self._target_clip     = None   # Live2DActorClip linked from timeline
        self._target_lane_row = None
        self._load_generation = 0
        self._loading_active = False
        self._pending_loaded_name = ""
        self._current_loading_path = ""
        self._last_failed_model_path = ""
        self._current_load_started_at = 0.0
        self._load_timeout_timer = QTimer(self)
        self._load_timeout_timer.setSingleShot(True)
        self._load_timeout_timer.timeout.connect(self._on_load_timeout)

        self._build_ui()
        QTimer.singleShot(0, self._refresh_model_tree)

        # Auto-load Haru
        haru = os.path.join(_SAMPLES_DIR,
            "CubismWebSamples", "Samples", "Resources", "Haru", "Haru.model3.json")
        if autoload_sample and os.path.exists(haru):
            self.load_model_deferred(haru, delay_ms=180)

    # ── build UI ──────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self._load_generation += 1
        try:
            self._load_timeout_timer.stop()
        except Exception:
            pass
        self._apply_current_model_to_target()
        self._viewport.unload_model()
        event.ignore()
        self.hide()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(3)
        splitter.setStyleSheet(
            "QSplitter::handle{background:rgba(178,186,202,18);}"
            "QSplitter::handle:hover{background:rgba(178,186,202,46);}"
        )

        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_right())
        splitter.setSizes([240, 680, 280])
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ── left: layer panel + model browser ─────────────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Live2DLeftPane")
        w.setStyleSheet(f"QWidget#Live2DLeftPane{{background:{_PANEL};}}")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Layer panel (top, 60%) ──
        layer_hdr = self._panel_header("레이어")
        lay.addWidget(layer_hdr)

        self._layer_panel = _LayerPanel()
        self._layer_panel.part_selected.connect(self._on_part_selected)
        self._layer_panel.part_visible.connect(self._on_part_visible)
        self._layer_panel.reload_model.connect(self._reload_model)
        lay.addWidget(self._layer_panel, 3)

        lay.addWidget(_h_rule())

        # ── Model browser (bottom, 40%) ──
        model_hdr = self._panel_header("모델")
        btn_open = QPushButton("")
        btn_open.setFixedSize(22, 22)
        btn_open.setIcon(app_icon("project", size=14))
        btn_open.setIconSize(icon_size(14))
        btn_open.setStyleSheet(_BTN_ICON)
        btn_open.setToolTip("파일에서 열기")
        btn_open.clicked.connect(self._open_file)
        btn_refresh = QPushButton("")
        btn_refresh.setFixedSize(22, 22)
        btn_refresh.setIcon(app_icon("reset", size=14))
        btn_refresh.setIconSize(icon_size(14))
        btn_refresh.setStyleSheet(_BTN_ICON)
        btn_refresh.setToolTip("목록 새로고침")
        btn_refresh.clicked.connect(lambda _checked=False: self._refresh_model_tree(force=True))
        model_hdr_row = QWidget()
        mhr = QHBoxLayout(model_hdr_row)
        mhr.setContentsMargins(8, 4, 6, 4)
        mhr.setSpacing(4)
        mhr.addWidget(model_hdr)
        mhr.addStretch(1)
        mhr.addWidget(btn_open)
        mhr.addWidget(btn_refresh)
        lay.addWidget(model_hdr_row)

        # Icon grid — models as draggable thumbnails
        self._model_grid = QListWidget()
        self._model_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._model_grid.setIconSize(QSize(72, 72))
        self._model_grid.setGridSize(QSize(88, 96))
        self._model_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._model_grid.setMovement(QListWidget.Movement.Static)
        self._model_grid.setSpacing(4)
        self._model_grid.setDragEnabled(True)
        self._model_grid.setStyleSheet(
            studio_chrome_qss(
                "QListWidget{border:none;outline:none;padding:5px;background:transparent;}"
                "QListWidget::item{border-radius:6px;padding:4px;color:#DDE2EA;}"
                "QListWidget::item:hover{background:rgba(255,255,255,8);}"
                "QListWidget::item:selected{background:#252A31;border:1px solid rgba(238,242,250,58);}"
            )
        )
        self._model_grid.itemClicked.connect(self._on_grid_click)
        self._model_grid.itemDoubleClicked.connect(self._on_grid_dclick)
        self._model_grid.startDrag = self._grid_start_drag
        lay.addWidget(self._model_grid, 2)
        # Keep _model_tree as hidden fallback (referenced elsewhere)
        self._model_tree = self._model_grid

        return w

    def _panel_header(self, text: str) -> QLabel:
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color:{_MUTED};font-size:9px;font-weight:620;"
            "letter-spacing:0px;padding:7px 8px 4px 8px;"
        )
        return lbl

    @staticmethod
    def _moc3_version(model3_path: str) -> int:
        try:
            from app.live2d.compat import moc3_version
            return moc3_version(model3_path)
        except Exception:
            pass
        """Return the moc3 version byte (0–6+). Returns -1 if unreadable."""
        try:
            import json as _j
            with open(model3_path, encoding="utf-8") as f:
                data = _j.load(f)
            moc_rel = data.get("FileReferences", {}).get("Moc", "")
            if not moc_rel:
                return -1
            moc_path = os.path.normpath(
                os.path.join(os.path.dirname(model3_path), moc_rel)
            )
            with open(moc_path, "rb") as f:
                hdr = f.read(8)
            if hdr[:4] != b"MOC3":
                return -1
            return hdr[4]  # version byte
        except Exception:
            return -1

    def _cached_model_paths(self, force: bool = False) -> list[str]:
        global _MODEL_PATH_CACHE
        if _MODEL_PATH_CACHE is not None and not force:
            return list(_MODEL_PATH_CACHE)

        patterns = (
            "*.model3.json",
            "*.model3.json.bytes",
            "*.model.json",
        )
        found: list[str] = []
        for pattern in patterns:
            found.extend(
                glob.glob(os.path.join(_SAMPLES_DIR, "**", pattern), recursive=True)
            )

        # Deep compatibility scan is intentionally refresh-only. The sample
        # tree contains many motion/physics JSON files, and opening all of them
        # during editor construction makes the window feel stuck.
        if force:
            try:
                from app.live2d.compat import find_model_in_path
                known = {os.path.normcase(os.path.normpath(p)) for p in found}
                for path in glob.glob(
                    os.path.join(_SAMPLES_DIR, "**", "*.json"), recursive=True
                ):
                    key = os.path.normcase(os.path.normpath(path))
                    if key in known:
                        continue
                    found_model = find_model_in_path(path)
                    if found_model is not None:
                        found.append(str(found_model))
            except Exception:
                pass

        _MODEL_PATH_CACHE = sorted(
            dict.fromkeys(os.path.normpath(path) for path in found)
        )
        return list(_MODEL_PATH_CACHE)

    def _support_error_for_model(self, path: str, force: bool = False) -> str:
        global _MODEL_SUPPORT_CACHE
        key = os.path.normcase(os.path.normpath(path))
        if force:
            _MODEL_SUPPORT_CACHE.pop(key, None)
        cached = _MODEL_SUPPORT_CACHE.get(key)
        if cached is not None:
            return cached
        support_error = ""
        try:
            from app.live2d.compat import model_support_error
            support_error = model_support_error(path)
        except Exception:
            pass
        _MODEL_SUPPORT_CACHE[key] = support_error
        return support_error

    def _refresh_model_tree(self, force: bool = False):
        global _MODEL_ICON_CACHE, _MODEL_SUPPORT_CACHE
        if not _qt_valid(self):
            return
        model_grid = getattr(self, "_model_grid", None)
        if not _qt_valid(model_grid):
            return
        if force:
            _MODEL_ICON_CACHE.clear()
            _MODEL_SUPPORT_CACHE.clear()
        model_grid.clear()
        found = self._cached_model_paths(force=force)
        for path in found:
            if not _qt_valid(model_grid):
                return
            name = os.path.basename(path).replace(".model3.json", "")
            support_error = self._support_error_for_model(path, force=force)
            if support_error:
                name = f"{name} (unsupported)"
            icon_key = os.path.normcase(os.path.normpath(path))
            icon = _MODEL_ICON_CACHE.get(icon_key) or self._fallback_model_icon()

            item = QListWidgetItem(icon, name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(f"{path}\n{support_error}" if support_error else path)
            item.setSizeHint(QSize(88, 96))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            model_grid.addItem(item)
            if icon_key not in _MODEL_ICON_CACHE:
                self._queue_model_icon_load(item, path, force=force)

    def _fallback_model_icon(self) -> "QIcon":
        from PySide6.QtGui import QIcon
        pm = QPixmap(72, 72)
        pm.fill(QColor("#2a2060"))
        return QIcon(pm)

    def _queue_model_icon_load(self, item: QListWidgetItem, path: str,
                               force: bool = False) -> None:
        delay_ms = min(350, 10 + self._model_grid.count() * 8)

        def _load_icon() -> None:
            if not _qt_valid(self) or not _qt_valid(self._model_grid):
                return
            if self._model_grid.row(item) < 0:
                return
            icon = self._model_icon(path, force=force)
            if self._model_grid.row(item) >= 0:
                item.setIcon(icon)

        QTimer.singleShot(delay_ms, _load_icon)

    def _model_icon(self, model3_path: str, force: bool = False) -> "QIcon":
        """Load the model's first texture as a 72×72 icon."""
        from PySide6.QtGui import QIcon
        global _MODEL_ICON_CACHE
        cache_key = os.path.normcase(os.path.normpath(model3_path))
        if force:
            _MODEL_ICON_CACHE.pop(cache_key, None)
        cached = _MODEL_ICON_CACHE.get(cache_key)
        if cached is not None:
            return cached

        def _remember(icon: "QIcon") -> "QIcon":
            _MODEL_ICON_CACHE[cache_key] = icon
            return icon

        try:
            from app.live2d.compat import normalize_live2d_model_path
            model3_path = normalize_live2d_model_path(model3_path) or model3_path
        except Exception:
            pass
        try:
            import json as _j
            with open(model3_path, encoding="utf-8") as f:
                data = _j.load(f)
            textures = data.get("FileReferences", {}).get("Textures", [])
            if textures:
                tex = os.path.normpath(
                    os.path.join(os.path.dirname(model3_path), textures[0])
                )
                if os.path.exists(tex):
                    # Load via PIL first to cap memory (large 4K textures)
                    try:
                        from PIL import Image as _Img
                        img = _Img.open(tex)
                        img.thumbnail((256, 256))
                        img = img.convert("RGBA")
                        from PySide6.QtGui import QImage as _QI
                        qi = _QI(img.tobytes(), img.width, img.height,
                                 _QI.Format.Format_RGBA8888).copy()
                        pm = QPixmap.fromImage(qi)
                    except Exception:
                        pm = QPixmap(tex)
                    pm = pm.scaled(
                        72, 72,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    # Crop to square
                    sz = min(pm.width(), pm.height())
                    ox = (pm.width()  - sz) // 2
                    oy = (pm.height() - sz) // 2
                    return _remember(QIcon(pm.copy(ox, oy, sz, sz)))
        except Exception:
            pass
        # Fallback: colored square
        pm = QPixmap(72, 72)
        pm.fill(QColor("#2a2060"))
        return _remember(QIcon(pm))

    def _on_tree_click(self, item, _col=None):
        path = item.data(Qt.ItemDataRole.UserRole) if hasattr(item, 'data') else None
        if path and os.path.exists(path) and path != self._current_model_path:
            self.load_model_deferred(path, delay_ms=120)

    def _on_tree_double_click(self, item, _col=None):
        path = item.data(Qt.ItemDataRole.UserRole) if hasattr(item, 'data') else None
        if path and os.path.exists(path):
            self.load_model_deferred(path, delay_ms=0)

    # ── grid (icon mode) handlers ─────────────────────────────────────────

    def _on_grid_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path) and path != self._current_model_path:
            self.load_model_deferred(path, delay_ms=120)

    def _on_grid_dclick(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self.load_model_deferred(path, delay_ms=0)

    def _grid_start_drag(self, supported_actions):
        from PySide6.QtGui import QDrag
        item = self._model_grid.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        mime = QMimeData()
        mime.setData("application/x-live2d-model", QByteArray(path.encode("utf-8")))
        mime.setUrls([QUrl.fromLocalFile(path)])

        # Use the item's icon as drag pixmap
        pm = item.icon().pixmap(72, 72)
        drag = QDrag(self._model_grid)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        drag.exec(supported_actions)

    def _tree_start_drag(self, supported_actions):
        """Custom drag — embed model path as application/x-live2d-model mime."""
        from PySide6.QtGui import QDrag, QPixmap, QPainter as _P
        from PySide6.QtCore import QMimeData, QByteArray

        item = self._model_tree.currentItem()
        if item is None:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return

        mime = QMimeData()
        mime.setData("application/x-live2d-model",
                     QByteArray(path.encode("utf-8")))
        # Also set as URL so Windows file drop targets can accept it
        from PySide6.QtCore import QUrl
        mime.setUrls([QUrl.fromLocalFile(path)])

        # Small drag pixmap with model name
        name = item.text(0)
        pm = QPixmap(max(80, len(name) * 7 + 16), 20)
        pm.fill(QColor("#251F3E"))
        painter = _P(pm)
        painter.setPen(QColor("#c0c0e0"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawPixmap(8, 3, app_icon("live2d", size=14, color="#c0c0e0").pixmap(icon_size(14)))
        painter.drawText(26, 14, name)
        painter.end()

        drag = QDrag(self._model_tree)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        drag.exec(supported_actions)

    def _open_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Live2D 모델 열기", _SAMPLES_DIR,
            "Live2D Model (*.model3.json *.model3.json.bytes *.json *.unitypackage);;All Files (*)"
        )
        if path:
            self._load_model(path)

    # ── center: viewport + bottom bar ─────────────────────────────────────────

    def _open_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Live2D Model",
            _SAMPLES_DIR,
            "Live2D Model (*.model3.json *.model3.json.bytes *.json *.unitypackage);;All Files (*)",
        )
        if path:
            self._load_model(path)

    def _build_center(self) -> QWidget:
        w = QWidget()
        w.setObjectName("Live2DCenterPane")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._loading_panel = QFrame()
        self._loading_panel.setObjectName("Live2DLoadingPanel")
        self._loading_panel.setVisible(False)
        self._loading_panel.setStyleSheet(
            "QFrame#Live2DLoadingPanel{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            " stop:0 rgba(255,128,87,40), stop:.55 rgba(126,107,255,34), stop:1 rgba(34,189,228,36));"
            "border-bottom:1px solid rgba(255,255,255,42);"
            "}"
            "QLabel#Live2DLoadingTitle{color:#FFFFFF;font-size:12px;font-weight:900;}"
            "QLabel#Live2DLoadingSub{color:#C8D0EA;font-size:10px;font-weight:700;}"
        )
        lp = QHBoxLayout(self._loading_panel)
        lp.setContentsMargins(14, 8, 14, 8)
        lp.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(app_icon("live2d", size=22, color="#FFFFFF").pixmap(icon_size(22)))
        lp.addWidget(icon, 0)
        text_box = QVBoxLayout()
        text_box.setContentsMargins(0, 0, 0, 0)
        text_box.setSpacing(2)
        title = QLabel("Live2D loading")
        title.setObjectName("Live2DLoadingTitle")
        self._loading_panel_label = QLabel("")
        self._loading_panel_label.setObjectName("Live2DLoadingSub")
        text_box.addWidget(title)
        text_box.addWidget(self._loading_panel_label)
        lp.addLayout(text_box, 1)
        self._loading_panel_bar = QProgressBar()
        self._loading_panel_bar.setRange(0, 100)
        self._loading_panel_bar.setValue(0)
        self._loading_panel_bar.setTextVisible(False)
        self._loading_panel_bar.setFixedWidth(210)
        self._loading_panel_bar.setFixedHeight(9)
        self._loading_panel_bar.setStyleSheet(
            "QProgressBar{background:rgba(10,13,24,160);border:1px solid rgba(255,255,255,45);"
            "border-radius:5px;}"
            "QProgressBar::chunk{background:qlineargradient("
            "x1:0,y1:0,x2:1,y2:0,stop:0 #FF8057,stop:.55 #7E6BFF,stop:1 #22BDE4);"
            "border-radius:4px;}"
        )
        lp.addWidget(self._loading_panel_bar, 0)
        lay.addWidget(self._loading_panel, 0)

        self._viewport = Live2DViewport()
        self._viewport.model_loaded.connect(self._on_model_loaded)
        self._viewport.error_occurred.connect(self._on_error)
        self._viewport.bounds_computed.connect(self._on_bounds_computed)
        self._viewport.first_frame_ready.connect(self._on_first_frame_ready)
        lay.addWidget(self._viewport, 1)
        lay.addWidget(self._build_bottom_bar())
        return w

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Live2DBottomBar")
        bar.setFixedHeight(42)
        bar.setStyleSheet(
            f"QWidget#Live2DBottomBar{{background:{_PANEL};"
            "border-top:1px solid rgba(178,186,202,18);}}"
            f"QWidget#Live2DBottomBar QLabel{{color:{_MUTED};font-size:9px;}}"
        )
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(10, 0, 10, 0)
        bl.setSpacing(6)

        prev_btn = QPushButton("")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setIcon(app_icon("previous", size=15, color="#FFFFFF"))
        prev_btn.setIconSize(icon_size(15))
        prev_btn.setStyleSheet(_BTN)
        prev_btn.setToolTip("이전 모션")
        prev_btn.clicked.connect(self._prev_motion)

        next_btn = QPushButton("")
        next_btn.setFixedSize(28, 28)
        next_btn.setIcon(app_icon("next", size=15, color="#FFFFFF"))
        next_btn.setIconSize(icon_size(15))
        next_btn.setStyleSheet(_BTN)
        next_btn.setToolTip("다음 모션")
        next_btn.clicked.connect(self._next_motion)

        self._motion_label = QLabel("—")
        self._motion_label.setStyleSheet(
            "QLabel{color:#C7CDD8;font-size:10px;padding:4px 8px;"
            "background:rgba(255,255,255,5);border:1px solid rgba(178,186,202,18);"
            "border-radius:6px;}"
        )
        self._motion_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        done_btn = QPushButton("Done")
        done_btn.setFixedHeight(28)
        done_btn.setMinimumWidth(64)
        done_btn.setStyleSheet(_BTN)
        done_btn.setToolTip("Model and motion are applied automatically")
        done_btn.clicked.connect(self.close)

        self._performance_source_mapping_btn = QPushButton("Map Source")
        self._performance_source_mapping_btn.setFixedHeight(28)
        self._performance_source_mapping_btn.setMinimumWidth(92)
        self._performance_source_mapping_btn.setStyleSheet(_BTN)
        self._performance_source_mapping_btn.setToolTip(
            "Map the active Performance Source to this Live2D clip"
        )
        self._performance_source_mapping_btn.setEnabled(False)
        self._performance_source_mapping_btn.clicked.connect(
            self._request_performance_source_mapping
        )

        bl.addWidget(prev_btn)
        bl.addWidget(next_btn)
        bl.addWidget(self._motion_label, 1)
        bl.addWidget(self._performance_source_mapping_btn)
        bl.addWidget(done_btn)

        # BG swatches
        bg_lbl = QLabel("배경")
        bg_lbl.setStyleSheet(f"color:{_MUTED};font-size:9px;padding-left:4px;")
        bl.addWidget(bg_lbl)
        for _name, col in [("dark", (.05,.05,.08,1)), ("light", (.95,.95,.95,1)), ("green", (0,.75,.2,1))]:
            b = QPushButton("")
            b.setFixedSize(22, 22)
            r, g, blue, _a = col
            b.setStyleSheet(
                _BTN
                + f"QPushButton{{background:rgb({int(r*255)},{int(g*255)},{int(blue*255)});"
                "border-radius:5px;padding:0;}}"
            )
            b.clicked.connect(lambda _, c=col: self._viewport.set_bg_color(*c))
            bl.addWidget(b)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{_MUTED};font-size:9px;")
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 100)
        self._loading_bar.setValue(0)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setFixedSize(150, 8)
        self._loading_bar.setVisible(False)
        self._loading_bar.setStyleSheet(
            "QProgressBar{background:#17191E;border:1px solid rgba(178,186,202,30);"
            "border-radius:4px;}"
            "QProgressBar::chunk{background:#A1A9B3;border-radius:3px;}"
        )
        self._cancel_load_btn = QPushButton("취소")
        self._cancel_load_btn.setFixedHeight(22)
        self._cancel_load_btn.setMinimumWidth(58)
        self._cancel_load_btn.setStyleSheet(_BTN)
        self._cancel_load_btn.setVisible(False)
        self._cancel_load_btn.clicked.connect(self._cancel_loading)
        bl.addWidget(self._loading_bar)
        bl.addWidget(self._cancel_load_btn)
        bl.addWidget(self._status_lbl)
        return bar

    # ── right: inspector ───────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        outer = QWidget()
        outer.setObjectName("Live2DRightPane")
        outer.setStyleSheet(f"QWidget#Live2DRightPane{{background:{_PANEL};}}")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet("QWidget{background:transparent;}")
        il = QVBoxLayout(inner)
        il.setContentsMargins(12, 10, 12, 10)
        il.setSpacing(5)

        # ── Transform controls ─────────────────────────────────────────────
        il.addWidget(_section_label("배치 / 키프레임"))
        self._transform_controls: dict = {}
        self._kf_lists: dict = {}   # key → QListWidget
        for label, key, lo, hi, default, fmt in [
            ("X 위치",   "pos_x",   0,   100, 50,  lambda v: f"{v:.0f}%"),
            ("Y 위치",   "pos_y",   0,   100, 50,  lambda v: f"{v:.0f}%"),
            ("크기",     "scale",   10,  400, 100, lambda v: f"{v:.0f}%"),
            ("불투명도", "opacity",  0,   100, 100, lambda v: f"{v:.0f}%"),
        ]:
            row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
            rl = QVBoxLayout(row_w); rl.setContentsMargins(0,2,0,0); rl.setSpacing(1)

            # Label + value + key button row
            top = QHBoxLayout(); top.setContentsMargins(0,0,0,0); top.setSpacing(4)
            lbl_w = QLabel(label); lbl_w.setStyleSheet(f"font-size:10px;color:{_MUTED};")
            val_lbl = QLabel(fmt(default)); val_lbl.setStyleSheet("font-size:10px;color:#C9D0DA;")
            val_lbl.setFixedWidth(36); val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            key_btn = QPushButton("")
            key_btn.setFixedSize(22, 16)
            key_btn.setIcon(app_icon("keyframe", size=12))
            key_btn.setIconSize(icon_size(12))
            key_btn.setStyleSheet(_BTN_ICON)
            key_btn.setToolTip(f"현재 플레이헤드 위치에 {label} 키프레임 추가")
            top.addWidget(lbl_w, 1); top.addWidget(val_lbl); top.addWidget(key_btn)
            rl.addLayout(top)

            # Slider
            slider = StudioSlider("accent")
            slider.setRange(lo, hi); slider.setValue(default); slider.setFixedHeight(16)
            _fmt = fmt
            def _on_change(v, k=key, vl=val_lbl, f=_fmt):
                vl.setText(f(v))
                self._apply_transform(k, v)
            slider.valueChanged.connect(_on_change)
            rl.addWidget(slider)

            # Keyframe list (compact)
            kf_list = QListWidget()
            kf_list.setFixedHeight(52)
            kf_list.setStyleSheet(
                studio_chrome_qss(
                    "QListWidget{font-size:9px;color:#A7ADC2;background:rgba(255,255,255,4);"
                    "border:1px solid rgba(178,186,202,16);border-radius:6px;}"
                    "QListWidget::item{padding:2px 5px;border-radius:4px;}"
                )
            )
            kf_list.setToolTip("더블클릭: 삭제 / 단축키 Del: 삭제")
            kf_list.itemDoubleClicked.connect(
                lambda item, k=key: self._delete_keyframe(k, item)
            )
            rl.addWidget(kf_list)

            il.addWidget(row_w)
            self._transform_controls[key] = slider
            self._kf_lists[key] = kf_list

            key_btn.clicked.connect(lambda checked=False, k=key: self._add_keyframe(k))

        il.addWidget(_h_rule())

        # ── Motion ──────────────────────────────────────────────────────────
        il.addWidget(_section_label("모션"))
        self._motion_list = QListWidget()
        self._motion_list.setFixedHeight(150)
        self._motion_list.itemDoubleClicked.connect(self._on_motion_dclick)
        il.addWidget(self._motion_list)

        il.addWidget(_h_rule())

        il.addWidget(_section_label("표정"))
        self._expr_wrap = QWidget()
        self._expr_wrap.setStyleSheet("background:transparent;")
        self._expr_flow = _FlowBox(self._expr_wrap)
        il.addWidget(self._expr_wrap)

        il.addWidget(_h_rule())

        il.addWidget(_section_label("파라미터"))
        self._param_box = QWidget()
        self._param_box.setStyleSheet("background:transparent;")
        self._param_vlay = QVBoxLayout(self._param_box)
        self._param_vlay.setContentsMargins(0, 0, 0, 0)
        self._param_vlay.setSpacing(2)
        il.addWidget(self._param_box)

        il.addWidget(_h_rule())
        il.addWidget(_section_label("로드 진단"))
        self._load_log_list = QListWidget()
        self._load_log_list.setFixedHeight(92)
        self._load_log_list.setStyleSheet(
            studio_chrome_qss(
                    "QListWidget{font-size:9px;color:#A7ADC2;background:rgba(255,255,255,4);"
                    "border:1px solid rgba(178,186,202,16);border-radius:6px;}"
                    "QListWidget::item{padding:2px 5px;border-radius:4px;}"
                )
            )
        il.addWidget(self._load_log_list)
        fail_row = QWidget(); fail_row.setStyleSheet("background:transparent;")
        fr = QHBoxLayout(fail_row); fr.setContentsMargins(0, 0, 0, 0); fr.setSpacing(4)
        self._retry_load_btn = QPushButton("다시")
        self._open_location_btn = QPushButton("위치")
        self._sample_load_btn = QPushButton("샘플")
        for btn in (self._retry_load_btn, self._open_location_btn, self._sample_load_btn):
            btn.setFixedHeight(24)
            btn.setStyleSheet(_BTN)
            btn.setVisible(False)
            fr.addWidget(btn)
        self._retry_load_btn.clicked.connect(self._retry_last_failed_model)
        self._open_location_btn.clicked.connect(self._open_current_model_location)
        self._sample_load_btn.clicked.connect(self._load_sample_model)
        il.addWidget(fail_row)

        il.addStretch(1)
        scroll.setWidget(inner)
        ol.addWidget(scroll, 1)
        return outer

    # ── model loading ─────────────────────────────────────────────────────────

    def _apply_transform(self, key: str, slider_value: int) -> None:
        """Push a transform change to the linked clip immediately."""
        clip = getattr(self, "_target_clip", None)
        row  = getattr(self, "_target_lane_row", None)
        if clip is None:
            return
        if key in ("pos_x", "pos_y"):
            setattr(clip, key, slider_value / 100.0)
        elif key == "scale":
            clip.scale = slider_value / 100.0
        elif key == "opacity":
            clip.opacity = slider_value / 100.0
        clip.reset()
        if row is not None:
            row.update()
            row.clip_changed.emit()
        self._focus_target_clip_preview()

    def _add_keyframe(self, key: str) -> None:
        """Add a keyframe at the current playhead position for the given property."""
        from app.live2d.actor_track import Live2DKeyframe
        clip = getattr(self, "_target_clip", None)
        row  = getattr(self, "_target_lane_row", None)
        if clip is None:
            return
        # Get current playhead (ms absolute) from the lane row
        playhead_ms = getattr(row, "_playhead_ms", 0) if row else 0
        anim_ms = max(0, playhead_ms - clip.start_ms)
        anim_ms = min(anim_ms, clip.duration_ms)

        # Current slider value → float
        slider = self._transform_controls.get(key)
        if slider is None:
            return
        v = slider.value()
        if key in ("pos_x", "pos_y"):
            value = v / 100.0
        elif key == "scale":
            value = v / 100.0
        else:  # opacity
            value = v / 100.0

        kf_list_attr = f"kf_{key}"
        kfs: list = getattr(clip, kf_list_attr, [])
        # Overwrite keyframe at same time if exists
        existing = next((k for k in kfs if k.time_ms == anim_ms), None)
        if existing:
            existing.value = value
        else:
            kfs.append(Live2DKeyframe(time_ms=anim_ms, value=value))
        setattr(clip, kf_list_attr, kfs)
        clip.reset()
        self._refresh_kf_list(key)
        if row is not None:
            row.update()
            row.clip_changed.emit()
        self._focus_target_clip_preview()

    def _delete_keyframe(self, key: str, item) -> None:
        """Delete a keyframe by list item."""
        clip = getattr(self, "_target_clip", None)
        row  = getattr(self, "_target_lane_row", None)
        if clip is None:
            return
        kf_list_attr = f"kf_{key}"
        kfs: list = getattr(clip, kf_list_attr, [])
        time_ms = item.data(Qt.ItemDataRole.UserRole)
        new_kfs = [k for k in kfs if k.time_ms != time_ms]
        setattr(clip, kf_list_attr, new_kfs)
        clip.reset()
        self._refresh_kf_list(key)
        if row is not None:
            row.update()
            row.clip_changed.emit()
        self._focus_target_clip_preview()

    def _refresh_kf_list(self, key: str) -> None:
        """Rebuild the keyframe list widget for one property."""
        lw = self._kf_lists.get(key)
        clip = getattr(self, "_target_clip", None)
        if lw is None:
            return
        lw.clear()
        if clip is None:
            return
        kfs = sorted(getattr(clip, f"kf_{key}", []), key=lambda k: k.time_ms)
        for kf in kfs:
            sec = kf.time_ms / 1000.0
            if key in ("pos_x", "pos_y"):
                val_str = f"{kf.value*100:.0f}%"
            elif key == "scale":
                val_str = f"{kf.value*100:.0f}%"
            else:
                val_str = f"{kf.value*100:.0f}%"
            item = __import__("PySide6.QtWidgets", fromlist=["QListWidgetItem"]).QListWidgetItem(
                f"{sec:.2f}s → {val_str}")
            item.setData(Qt.ItemDataRole.UserRole, kf.time_ms)
            lw.addItem(item)

    def _refresh_all_kf_lists(self) -> None:
        for key in ("pos_x", "pos_y", "scale", "opacity"):
            self._refresh_kf_list(key)

    def set_target_clip(self, clip, lane_row) -> None:
        """Link this editor to a timeline actor clip for live assignment."""
        self._target_clip     = clip
        self._target_lane_row = lane_row
        if _qt_valid(lane_row):
            try:
                lane_row.destroyed.connect(lambda *_args, row=lane_row: self._clear_target_lane_row(row))
            except Exception:
                pass

        # Sync transform sliders to clip's current values
        ctrls = getattr(self, "_transform_controls", {})
        if clip is not None and ctrls:
            for key, slider in ctrls.items():
                slider.blockSignals(True)
                if key in ("pos_x", "pos_y"):
                    slider.setValue(int(getattr(clip, key, 0.5) * 100))
                elif key == "scale":
                    slider.setValue(int(clip.scale * 100))
                elif key == "opacity":
                    slider.setValue(int(clip.opacity * 100))
                slider.blockSignals(False)

        # Refresh keyframe lists
        if hasattr(self, "_kf_lists"):
            self._refresh_all_kf_lists()
        self._update_performance_source_mapping_button()

        # Assignment is automatic: selecting/loading a model updates the linked
        # timeline clip, and closing the editor applies the current model/motion
        # one final time.

    def _clear_target_lane_row(self, row=None) -> None:
        if row is None or row is getattr(self, "_target_lane_row", None):
            self._target_lane_row = None

    def load_model_deferred(self, path: str, delay_ms: int = 120) -> None:
        """Load a model after the editor has become visible and stable.

        The first Live2D native initialization is expensive. Loading after
        show/raise prevents the first double-click from looking like the
        editor opened and immediately disappeared, and the generation token
        cancels stale sample loads when a timeline clip is opened.
        """
        if not path:
            return
        self._load_generation += 1
        token = self._load_generation
        self._current_loading_path = path
        self._current_load_started_at = time.perf_counter()
        self._set_loading(True, "모델 로드 준비 중…", progress=5, stage="queued")
        self._cache_load_status("loading", "queued", "Live2D load queued", path=path)

        def _load(attempt: int = 0) -> None:
            if not _qt_valid(self) or token != self._load_generation:
                return
            if not self.isVisible():
                if attempt < 20:
                    QTimer.singleShot(50, lambda: _load(attempt + 1))
                return
            self._load_model(path, _from_deferred=True)

        QTimer.singleShot(max(0, int(delay_ms)), _load)

    def _set_loading(self, active: bool, text: str = "", *, progress: int | None = None, stage: str = "") -> None:
        self._loading_active = bool(active)
        if progress is None and stage:
            try:
                from app.actor_loading_cache import actor_progress_for_stage
                progress = actor_progress_for_stage(stage)
            except Exception:
                progress = None
        bar = getattr(self, "_loading_bar", None)
        if _qt_valid(bar):
            bar.setVisible(bool(active))
            if active:
                bar.setRange(0, 100)
                if progress is not None:
                    bar.setValue(max(0, min(100, int(progress))))
            elif progress is not None:
                bar.setValue(max(0, min(100, int(progress))))
        panel = getattr(self, "_loading_panel", None)
        if _qt_valid(panel):
            panel.setVisible(bool(active))
        panel_bar = getattr(self, "_loading_panel_bar", None)
        if _qt_valid(panel_bar):
            if progress is not None:
                panel_bar.setValue(max(0, min(100, int(progress))))
            elif active:
                panel_bar.setValue(0)
        panel_label = getattr(self, "_loading_panel_label", None)
        if _qt_valid(panel_label):
            panel_label.setText(text or ("Preparing Live2D runtime..." if active else ""))
        cancel_btn = getattr(self, "_cancel_load_btn", None)
        if _qt_valid(cancel_btn):
            cancel_btn.setVisible(bool(active))
            cancel_btn.setEnabled(bool(active))
        lbl = getattr(self, "_status_lbl", None)
        if text and _qt_valid(lbl):
            lbl.setText(text)
            self._append_load_log(text)
        if not active:
            try:
                self._load_timeout_timer.stop()
            except Exception:
                pass

    def _record_load_action(self, stage: str, **data) -> None:
        try:
            from app.crash_reporter import record_action
            record_action("actor.load_live2d.stage", stage=stage, **data)
        except Exception:
            pass

    def _elapsed_load_ms(self) -> int | None:
        started = float(getattr(self, "_current_load_started_at", 0.0) or 0.0)
        if started <= 0:
            return None
        return int((time.perf_counter() - started) * 1000)

    def _cache_load_status(
        self,
        status: str,
        stage: str,
        message: str = "",
        *,
        path: str = "",
        metadata: dict | None = None,
    ) -> None:
        actor_path = path or self._current_loading_path or self._current_model_path or ""
        if not actor_path:
            return
        try:
            from app.actor_loading_cache import record_actor_load
            record_actor_load(
                "live2d",
                actor_path,
                status=status,
                stage=stage,
                message=message,
                elapsed_ms=self._elapsed_load_ms(),
                metadata=metadata or None,
            )
        except Exception:
            pass
        self._record_load_action(stage, path=actor_path, status=status, message=message)

    def _append_load_log(self, text: str) -> None:
        log = getattr(self, "_load_log_list", None)
        if not text or not _qt_valid(log):
            return
        try:
            import time as _time
            log.addItem(f"{_time.strftime('%H:%M:%S')}  {text}")
            while log.count() > 9:
                log.takeItem(0)
            log.scrollToBottom()
        except Exception:
            pass

    def _set_failure_actions_visible(self, visible: bool) -> None:
        for name in ("_retry_load_btn", "_open_location_btn", "_sample_load_btn"):
            btn = getattr(self, name, None)
            if _qt_valid(btn):
                btn.setVisible(bool(visible))

    def _mark_target_clip_status(self, status: str, message: str = "") -> None:
        clip = getattr(self, "_target_clip", None)
        if clip is None:
            return
        try:
            from app.actor_loading_status import set_actor_clip_status
            set_actor_clip_status(
                clip,
                status,
                message,
                path=self._current_loading_path or self._current_model_path or "",
            )
        except Exception:
            pass
        row = getattr(self, "_target_lane_row", None)
        if _qt_valid(row):
            try:
                row.update()
            except Exception:
                pass

    def _same_model_path(self, left: str, right: str) -> bool:
        if not left or not right:
            return True
        try:
            return os.path.normcase(os.path.normpath(left)) == os.path.normcase(os.path.normpath(right))
        except Exception:
            return str(left) == str(right)

    def _viewport_matches_current_load(self) -> bool:
        viewport = getattr(self, "_viewport", None)
        if not _qt_valid(viewport):
            return False
        getter = getattr(viewport, "current_model_path", None)
        viewport_path = ""
        if callable(getter):
            try:
                viewport_path = str(getter() or "")
            except Exception:
                viewport_path = ""
        current_path = self._current_loading_path or self._current_model_path or ""
        return self._same_model_path(viewport_path, current_path)

    def _cancel_loading(self) -> None:
        self._load_generation += 1
        self._current_loading_path = ""
        try:
            self._load_timeout_timer.stop()
        except Exception:
            pass
        self._viewport.unload_model()
        self._set_loading(False, "로드 취소됨", progress=100, stage="cancelled")
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("cancelled", "Live2D load cancelled")
        self._cache_load_status("cancelled", "cancelled", "Live2D load cancelled", path=self._last_failed_model_path or self._current_model_path or "")

    def _on_load_timeout(self) -> None:
        if not self._loading_active:
            return
        path = self._current_loading_path or self._current_model_path or ""
        self._last_failed_model_path = path
        self._load_generation += 1
        self._viewport.unload_model()
        msg = "첫 프레임 타임아웃: 모델/텍스처/렌더 초기화를 확인하세요"
        self._set_loading(False, msg, progress=100, stage="timeout")
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("timeout", msg)
        self._cache_load_status("timeout", "timeout", msg, path=path)

    def _retry_last_failed_model(self) -> None:
        path = self._last_failed_model_path or self._current_model_path
        if path:
            self.load_model_deferred(path, delay_ms=80)

    def _open_current_model_location(self) -> None:
        path = self._last_failed_model_path or self._current_model_path
        if not path:
            return
        try:
            os.startfile(os.path.dirname(path))
        except Exception as exc:
            self._append_load_log(f"위치 열기 실패: {exc}")

    def _load_sample_model(self) -> None:
        haru = os.path.join(
            _SAMPLES_DIR,
            "CubismWebSamples", "Samples", "Resources", "Haru", "Haru.model3.json",
        )
        if os.path.exists(haru):
            self.load_model_deferred(haru, delay_ms=80)

    def _load_model(self, path: str, *, _from_deferred: bool = False):
        if not _from_deferred:
            self._load_generation += 1
        self._current_load_started_at = time.perf_counter()
        self._set_loading(True, "모델 파일 확인 중…", progress=10, stage="file_check")
        self._set_failure_actions_visible(False)
        self._cache_load_status("loading", "file_check", "Live2D file check", path=path)
        try:
            from app.actor_compat_repair import repair_actor_model_path
            repair = repair_actor_model_path("live2d", path)
            for step in repair.get("steps", []) or []:
                self._append_load_log(str(step))
            for warning in repair.get("warnings", []) or []:
                self._append_load_log(str(warning))
            if repair.get("path"):
                path = str(repair["path"])
            self._set_loading(True, "모델 호환성 확인 중…", progress=30, stage="compat")
            self._cache_load_status("loading", "compat", "Live2D compatibility checked", path=path, metadata=repair.get("metadata") or {})
        except Exception as exc:
            self._append_load_log(f"호환성 자동 확인 실패: {exc}")
            self._set_loading(True, "모델 호환성 확인 중…", progress=30, stage="compat")
        if not self._ensure_model_supported(path):
            self._cache_load_status("error", "error", "Live2D model unsupported", path=path)
            self._set_loading(False, progress=100, stage="error")
            return
        self._current_model_path = path
        self._current_loading_path = path
        self._mark_target_clip_status("loading", f"Live2D loading: {os.path.basename(path)}")
        self._set_loading(True, "메타데이터 읽는 중…", progress=55, stage="parse")
        self._cache_load_status("loading", "parse", "Live2D metadata parse", path=path)
        try:
            self._load_timeout_timer.start(
                max(5_000, int(os.environ.get("TIGERCAPTURE_ACTOR_LOAD_TIMEOUT_MS", "25000")))
            )
        except Exception:
            self._load_timeout_timer.start(25_000)
        self._viewport.load_model(path)
        self._assign_to_target(path=path)

    def _ensure_model_supported(self, path: str) -> bool:
        try:
            from app.live2d.compat import model_support_error
            error = model_support_error(path)
        except Exception:
            error = ""
        if not error:
            return True
        self._last_failed_model_path = path
        self._status_lbl.setText(error)
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("error", error)
        self._cache_load_status("error", "error", error, path=path)
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Live2D", error)
        except Exception:
            pass
        return False

    def _reload_model(self):
        if self._current_model_path:
            self._load_model(self._current_model_path)

    def _on_model_loaded(self, name: str, motions: list, exprs: list,
                          parts: list, textures: list):
        if not _qt_valid(self):
            return
        if not self._viewport_matches_current_load():
            return
        required_widgets = (
            getattr(self, "_status_lbl", None),
            getattr(self, "_motion_label", None),
            getattr(self, "_layer_panel", None),
            getattr(self, "_motion_list", None),
            getattr(self, "_expr_wrap", None),
            getattr(self, "_param_box", None),
        )
        if not all(_qt_valid(w) for w in required_widgets):
            return

        self._motions = motions
        self._current_motion_idx = -1
        self._pending_loaded_name = name
        self._set_loading(True, "첫 프레임 렌더링 중…", progress=90, stage="first_frame")
        self._mark_target_clip_status("loading", f"Live2D first frame: {name}")
        self._cache_load_status("loading", "first_frame", f"Live2D first frame: {name}")
        self._motion_label.setText("—")

        # Thumbnail from first texture
        thumb_px = self._load_thumbnail(textures[0] if textures else "")

        # Layer panel
        self._layer_panel.populate(parts, thumb_px)

        # Motion list
        motion_list = self._motion_list
        motion_list.clear()
        for g, i, lbl in motions:
            item = QListWidgetItem(lbl)
            item.setData(Qt.ItemDataRole.UserRole, (g, i))
            motion_list.addItem(item)

        # Auto-play idle
        for idx, (g, i, lbl) in enumerate(motions):
            if "idle" in lbl.lower():
                self._play_motion_idx(idx, apply_to_target=True)
                break

        # Expression buttons
        self._expr_flow.clear(delete_widgets=True)
        for eid in exprs:
            btn = QPushButton(eid)
            btn.setStyleSheet(_BTN)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda _, e=eid: self._viewport.set_expression(e))
            self._expr_flow.add(btn)

        # Parameter sliders
        while self._param_vlay.count():
            item = self._param_vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._param_sliders.clear()

        model_ids: set[str] = set()
        try:
            m = self._viewport._model
            if m:
                model_ids = set(m.GetParamIds())
        except Exception:
            pass

        for pid, label, pmin, pmax in _INSPECTOR_PARAMS:
            if model_ids and pid not in model_ids:
                continue
            row = QWidget()
            row.setStyleSheet("background:transparent;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 0)
            rl.setSpacing(1)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            lbl_w = QLabel(label)
            lbl_w.setStyleSheet(f"font-size:10px;color:{_MUTED};")
            val_lbl = QLabel("0.0")
            val_lbl.setStyleSheet("font-size:10px;color:#8A7CFF;")
            val_lbl.setFixedWidth(30)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            top.addWidget(lbl_w, 1)
            top.addWidget(val_lbl)
            rl.addLayout(top)

            slider = StudioSlider("accent")
            slider.setMinimum(int(pmin * 100))
            slider.setMaximum(int(pmax * 100))
            slider.setValue(0)
            slider.setFixedHeight(16)

            def _on_change(v, p=pid, vl=val_lbl):
                fv = v / 100.0
                vl.setText(f"{fv:.1f}")
                self._viewport.set_parameter(p, fv)
            slider.valueChanged.connect(_on_change)

            rl.addWidget(slider)
            self._param_vlay.addWidget(row)
            self._param_sliders[pid] = (slider, val_lbl)

    def _load_thumbnail(self, tex_path: str) -> Optional[QPixmap]:
        if not tex_path or not os.path.exists(tex_path):
            return None
        try:
            from PIL import Image
            img = Image.open(tex_path).convert("RGBA")
            img.thumbnail((120, 120))
            data = img.tobytes("raw", "RGBA")
            qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888).copy()
            return QPixmap.fromImage(qi)
        except Exception:
            return QPixmap(tex_path)

    def _apply_current_model_to_target(self) -> None:
        if not self._current_model_path:
            return
        if not self._ensure_model_supported(self._current_model_path):
            return
        model_path = self._current_model_path
        if self._motions:
            idx = self._current_motion_idx if self._current_motion_idx >= 0 else 0
            g, i, _ = self._motions[idx]
            motion_group, motion_idx = g, i
        else:
            motion_group, motion_idx = "", 0
        self._assign_to_target(
            path=model_path,
            motion_group=motion_group,
            motion_idx=motion_idx,
        )

    def _assign_to_target(self, path: str = None,
                           motion_group: str = None, motion_idx: int = None):
        """Push model/motion assignment back to the linked timeline actor clip."""
        clip = getattr(self, "_target_clip", None)
        row  = getattr(self, "_target_lane_row", None)
        if clip is None:
            return
        if path is not None:
            if not self._ensure_model_supported(path):
                return
        changed = False
        if path is not None and clip.model_path != path:
            clip.model_path = path
            clip.reset()
            changed = True
        motion_changed = False
        if motion_group is not None:
            clip.motion_group = motion_group
            motion_changed = True
        if motion_idx is not None:
            clip.motion_idx = motion_idx
            motion_changed = True
        if motion_changed:
            clip.reset()  # restart animation from beginning
            changed = True
        if changed and _qt_valid(row):
            try:
                row.update()
            except Exception:
                pass
            try:
                row.clip_changed.emit()
            except Exception:
                pass
        if changed:
            self._focus_target_clip_preview()

    def _focus_target_clip_preview(self) -> None:
        clip = getattr(self, "_target_clip", None)
        parent = self.parent()
        if parent is not None and not _qt_valid(parent):
            return
        focus = getattr(parent, "_focus_actor_clip_for_edit", None)
        if clip is not None and callable(focus):
            try:
                focus(clip, refresh=True)
            except Exception:
                pass

    def _update_performance_source_mapping_button(self) -> None:
        btn = getattr(self, "_performance_source_mapping_btn", None)
        if not _qt_valid(btn):
            return
        clip = getattr(self, "_target_clip", None)
        parent = self.parent()
        if parent is not None and not _qt_valid(parent):
            parent = None
        handler = getattr(
            parent,
            "_on_live2d_clip_performance_source_mapping_requested",
            None,
        )
        btn.setEnabled(clip is not None and callable(handler))

    def _request_performance_source_mapping(self) -> None:
        clip = getattr(self, "_target_clip", None)
        if clip is None:
            lbl = getattr(self, "_status_lbl", None)
            if _qt_valid(lbl):
                lbl.setText("Select a Live2D clip first")
            self._update_performance_source_mapping_button()
            return
        parent = self.parent()
        if parent is not None and not _qt_valid(parent):
            parent = None
        handler = getattr(
            parent,
            "_on_live2d_clip_performance_source_mapping_requested",
            None,
        )
        if not callable(handler):
            lbl = getattr(self, "_status_lbl", None)
            if _qt_valid(lbl):
                lbl.setText("Performance Source Mapping is unavailable here")
            self._update_performance_source_mapping_button()
            return
        self._focus_target_clip_preview()
        handler(clip)
        self._focus_target_clip_preview()

    def _on_error(self, msg: str):
        self._last_failed_model_path = self._current_loading_path or self._current_model_path
        self._set_loading(False, f"❌ {msg[:50]}", progress=100, stage="error")
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("error", msg)
        self._cache_load_status("error", "error", msg)

    def _on_first_frame_ready(self) -> None:
        if not self._loading_active:
            return
        if not self._viewport_matches_current_load():
            return
        viewport = getattr(self, "_viewport", None)
        first_frame_path = ""
        getter = getattr(viewport, "first_frame_model_path", None) if _qt_valid(viewport) else None
        if callable(getter):
            try:
                first_frame_path = str(getter() or "")
            except Exception:
                first_frame_path = ""
        current_path = self._current_loading_path or self._current_model_path or ""
        if first_frame_path and not self._same_model_path(first_frame_path, current_path):
            return
        name = self._pending_loaded_name or (
            os.path.basename(self._current_model_path or "") or "Live2D"
        )
        self._cache_load_status("ready", "ready", f"Live2D ready: {name}")
        self._set_loading(False, f"✓ {name}", progress=100, stage="ready")
        self._set_failure_actions_visible(False)
        self._mark_target_clip_status("ready", f"Live2D ready: {name}")

    # ── part interaction ──────────────────────────────────────────────────────

    def _on_part_selected(self, part_idx: int):
        self._viewport.highlight_part(part_idx)

    def _on_part_visible(self, part_idx: int, visible: bool):
        self._viewport.set_part_visible(part_idx, visible)

    def _on_bounds_computed(self, part_idx: int, found: bool):
        rows = self._layer_panel._rows
        if 0 <= part_idx < len(rows):
            rows[part_idx].set_detected(found)

    # ── motion controls ───────────────────────────────────────────────────────

    def _on_motion_dclick(self, item: QListWidgetItem):
        idx = self._motion_list.row(item)
        self._play_motion_idx(idx)

    def _play_motion_idx(self, idx: int, apply_to_target: bool = True):
        if 0 <= idx < len(self._motions):
            g, i, lbl = self._motions[idx]
            self._viewport.play_motion(g, i)
            self._current_motion_idx = idx
            self._motion_label.setText(lbl)
            self._motion_list.setCurrentRow(idx)
            clip = getattr(self, "_target_clip", None)
            if (
                apply_to_target
                and clip is not None
                and clip.model_path == self._current_model_path
            ):
                self._assign_to_target(motion_group=g, motion_idx=i)

    def _prev_motion(self):
        if self._motions:
            self._play_motion_idx((self._current_motion_idx - 1) % len(self._motions))

    def _next_motion(self):
        if self._motions:
            self._play_motion_idx((self._current_motion_idx + 1) % len(self._motions))


# ── simple flow layout ────────────────────────────────────────────────────────

class _FlowBox:
    def __init__(self, parent: QWidget):
        self._parent = parent
        self._widgets: list[QWidget] = []
        self._lay = QVBoxLayout(parent)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)

    def add(self, w: QWidget):
        self._widgets.append(w)
        self._rebuild()

    def count(self) -> int:
        return len(self._widgets)

    def widget_at(self, i: int) -> Optional[QWidget]:
        return self._widgets[i] if 0 <= i < len(self._widgets) else None

    def clear(self, delete_widgets: bool = False):
        if delete_widgets:
            for w in self._widgets:
                if _qt_valid(w):
                    w.setParent(None)
                    w.deleteLater()
        self._widgets.clear()
        self._clear_layout(self._lay)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            if child_layout:
                self._clear_layout(child_layout)

    def _rebuild(self):
        self._clear_layout(self._lay)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row_w = 0
        max_w = 230

        for w in self._widgets:
            w_hint = max(w.sizeHint().width(), 50)
            if row_w + w_hint > max_w and row_w > 0:
                row.addStretch(1)
                self._lay.addLayout(row)
                row = QHBoxLayout()
                row.setContentsMargins(0, 0, 0, 0)
                row.setSpacing(4)
                row_w = 0
            row.addWidget(w)
            row_w += w_hint + 4

        if row_w > 0:
            row.addStretch(1)
            self._lay.addLayout(row)


Live2DWindow = Live2DEditorWindow
