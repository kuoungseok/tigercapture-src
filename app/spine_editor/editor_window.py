"""Spine Editor window — Live2D-style simple UI."""
from __future__ import annotations
import os
import glob
import time
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QSize, QMimeData, QByteArray, QUrl, Signal
from PySide6.QtGui import QColor, QPixmap, QImage, QPainter, QFont, QIcon, QDrag
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QSlider, QScrollArea,
    QListWidget, QListWidgetItem, QFrame,
    QSizePolicy, QFileDialog, QAbstractItemView,
    QComboBox, QTreeWidget, QTreeWidgetItem, QProgressBar,
)

from app.icons import app_icon, icon_size
from app.style import editor_scrollbar_qss, studio_chrome_qss
from app.spine_editor.spine_gl_renderer import SpineGLViewport as SpineViewport

_SAMPLES_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "resources", "spine_samples")
)
_BLUE_ARCHIVE_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..", "..", "external", "blue-archive-viewer", "public", "data",
    )
)
_NIKKE_INITIAL_FOLDERS = ("absolute",)

_DARK  = "#0B0D16"
_PANEL = "#111421"
_CARD  = "#171B2A"
_RULE  = "#30384F"
_MUTED = "#A7ADC2"
_TEXT  = "#E8EAF4"

_BTN = (
    "QPushButton{background:rgba(255,255,255,18);color:#E8EAF4;border:1px solid #37405A;"
    "border-radius:13px;padding:7px 13px;font-size:11px;font-weight:700;}"
    "QPushButton:hover{background:rgba(255,255,255,30);border-color:#7580A5;color:#FFFFFF;}"
    "QPushButton:pressed{background:rgba(255,255,255,24);border-color:#A79EFF;}"
)
_BTN_ICON = (
    "QPushButton{background:rgba(255,255,255,12);color:#E8EAF4;border:1px solid #30384F;"
    "border-radius:11px;font-size:13px;padding:0;}"
    "QPushButton:hover{background:rgba(255,255,255,28);color:#FFFFFF;border-color:#7580A5;}"
)
_SECTION = (
    f"QLabel{{color:{_MUTED};font-size:10px;font-weight:bold;"
    "letter-spacing:1px;padding:6px 0 2px 0;}}"
)


# ── thumbnail generator ───────────────────────────────────────────────────────

def _generate_thumb(spine_path: str, size: int = 72) -> Optional[QIcon]:
    """Build a cheap thumbnail for a Spine JSON or .skel file.

    Do not render the skeleton here.  Mesh-heavy Spine assets such as NIKKE
    can take seconds per CPU-rendered frame, and this function runs for every
    item in the browser.
    """
    try:
        from app.spine_editor.spine_json_parser import (
            load_atlas_pages,
        )
        from PIL import Image

        if spine_path.endswith(".skel"):
            json_peer = spine_path[:-5] + ".json"
            if os.path.exists(json_peer):
                spine_path = json_peer

        # Determine stem: strip .json or .skel suffix
        if spine_path.endswith(".skel"):
            stem = spine_path[:-5]
        else:
            stem = os.path.splitext(spine_path)[0]
        json_path = spine_path   # keep original variable name below
        atlas_path = stem + ".atlas"
        if not os.path.exists(atlas_path):
            raise FileNotFoundError("no atlas")

        pages   = load_atlas_pages(atlas_path)
        base    = os.path.dirname(json_path)
        img = None
        for pg in pages:
            p = os.path.join(base, pg)
            if os.path.exists(p):
                img = Image.open(p).convert("RGBA")
                break
        if img is None:
            raise FileNotFoundError("no texture page")

        # Auto-crop to content
        import numpy as np
        arr = np.array(img)
        rows = np.any(arr[:, :, 3] > 0, axis=1)
        cols = np.any(arr[:, :, 3] > 0, axis=0)
        if rows.any() and cols.any():
            r0, r1 = np.where(rows)[0][[0, -1]]
            c0, c1 = np.where(cols)[0][[0, -1]]
            pad = 4
            img = img.crop((max(0, c0 - pad), max(0, r0 - pad),
                            min(img.width, c1 + pad), min(img.height, r1 + pad)))

        img = img.resize((size, size), Image.Resampling.LANCZOS)
        data = img.tobytes("raw", "RGBA")
        qi = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888).copy()
        pm = QPixmap.fromImage(qi)
        return QIcon(pm)
    except Exception:
        pm = QPixmap(size, size)
        pm.fill(QColor("#2a2060"))
        p = QPainter(pm)
        p.setPen(QColor("#8A7CFF"))
        p.setFont(QFont("Segoe UI", 8))
        name = os.path.splitext(os.path.basename(spine_path))[0][:8]
        p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, name)
        p.end()
        return QIcon(pm)


# ── main editor window ────────────────────────────────────────────────────────

class SpineEditorWindow(QWidget):
    """Spine character editor — Live2D-style simple UI."""

    def __init__(self, parent=None, *, autoload_sample: bool = True):
        super().__init__(parent)
        self.setWindowTitle("Spine 에디터 — TigerCapture")
        self.setWindowFlags(Qt.WindowType.Window)
        self.resize(1200, 740)
        self.setStyleSheet(studio_chrome_qss(
            f"QWidget{{background:{_DARK};color:{_TEXT};font-size:12px;}}"
            f"QScrollBar:vertical{{background:{_PANEL};width:6px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:#30384F;border-radius:3px;}}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
            f"QScrollBar:horizontal{{background:{_PANEL};height:6px;border-radius:3px;}}"
            f"QScrollBar::handle:horizontal{{background:#30384F;border-radius:3px;}}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}"
            f"QListWidget{{background:{_PANEL};border:1px solid {_RULE};border-radius:7px;outline:none;}}"
            f"QListWidget::item{{padding:3px 6px;border-radius:3px;}}"
            f"QListWidget::item:hover{{background:rgba(255,255,255,24);}}"
            f"QListWidget::item:selected{{background:#6F5CFF;color:#fff;}}"
            "QSlider::groove:horizontal{background:#292B35;height:3px;border-radius:2px;}"
            "QSlider::handle:horizontal{background:#6452FF;border:1px solid #9C8EFF;width:12px;height:12px;"
            "margin:-5px 0;border-radius:6px;}"
            "QSlider::sub-page:horizontal{background:#5B45FF;border-radius:2px;}"
            + editor_scrollbar_qss()
        ))

        self._anims: list[str] = []
        self._current_anim_idx = -1
        self._current_json: Optional[str] = None
        self._target_clip     = None
        self._target_lane_row = None
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(33)
        self._play_timer.timeout.connect(self._on_tick)
        self._anim_time: float = 0.0
        self._playing: bool = False
        self._load_generation = 0
        self._loading_active = False
        self._current_loading_path = ""
        self._last_failed_path = ""
        self._pending_loaded_name = ""
        self._current_load_started_at = 0.0
        self._load_timeout_timer = QTimer(self)
        self._load_timeout_timer.setSingleShot(True)
        self._load_timeout_timer.timeout.connect(self._on_load_timeout)

        self._extra_dirs: list[str] = []   # user-added directories
        self._current_folder: Optional[str] = None
        self._suppress_single_folder_autoload = True

        self._build_ui()
        self._sync_output_aspect_ratio_from_parent()
        self._refresh_folder_tree()
        self._suppress_single_folder_autoload = False

        initial_spine = self._initial_spine_path()
        if autoload_sample and initial_spine:
            self.load_character_deferred(initial_spine, delay_ms=160)

    # ── close → hide ─────────────────────────────────────────────────────────

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self._sync_output_aspect_ratio_from_parent()

    def _sync_output_aspect_ratio_from_parent(self) -> None:
        if hasattr(self, "_viewport") and hasattr(self._viewport, "set_output_aspect_ratio"):
            self._viewport.set_output_aspect_ratio(_editor_output_aspect_ratio(self.parent()))

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        splitter.setStyleSheet(f"QSplitter::handle{{background:{_RULE};}}")

        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_right())
        splitter.setSizes([240, 680, 280])
        splitter.setStretchFactor(1, 1)

        root.addWidget(splitter)

    # ── left: folder tree + character grid ───────────────────────────────────

    def _build_left(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"QWidget{{background:{_PANEL};}}")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Toolbar ─────────────────────────────────────────────────────────
        toolbar = QWidget()
        tb = QHBoxLayout(toolbar)
        tb.setContentsMargins(8, 5, 6, 4)
        tb.setSpacing(4)

        hdr = QLabel("SPINE 탐색기")
        hdr.setStyleSheet(f"color:{_MUTED};font-size:10px;font-weight:bold;letter-spacing:1px;")
        tb.addWidget(hdr, 1)

        btn_add_dir = QPushButton("")
        btn_add_dir.setFixedSize(28, 22)
        btn_add_dir.setIcon(app_icon("plus", size=14))
        btn_add_dir.setIconSize(icon_size(14))
        btn_add_dir.setStyleSheet(_BTN_ICON)
        btn_add_dir.setToolTip("폴더 추가")
        btn_add_dir.clicked.connect(self._add_search_dir)
        tb.addWidget(btn_add_dir)

        btn_open = QPushButton("")
        btn_open.setFixedSize(22, 22)
        btn_open.setIcon(app_icon("project", size=14))
        btn_open.setIconSize(icon_size(14))
        btn_open.setStyleSheet(_BTN_ICON)
        btn_open.setToolTip("파일 직접 열기")
        btn_open.clicked.connect(self._open_file)
        tb.addWidget(btn_open)

        btn_refresh = QPushButton("")
        btn_refresh.setFixedSize(22, 22)
        btn_refresh.setIcon(app_icon("reset", size=14))
        btn_refresh.setIconSize(icon_size(14))
        btn_refresh.setStyleSheet(_BTN_ICON)
        btn_refresh.setToolTip("목록 새로고침")
        btn_refresh.clicked.connect(self._refresh_folder_tree)
        tb.addWidget(btn_refresh)

        lay.addWidget(toolbar)

        # ── Splitter: folder tree (top) / file grid (bottom) ────────────────
        vsplit = QSplitter(Qt.Orientation.Vertical)
        vsplit.setHandleWidth(6)
        vsplit.setStyleSheet(f"QSplitter::handle{{background:{_RULE};}}")

        # Folder tree
        self._folder_tree = QTreeWidget()
        self._folder_tree.setHeaderHidden(True)
        self._folder_tree.setRootIsDecorated(True)
        self._folder_tree.setIndentation(14)
        self._folder_tree.setStyleSheet(
            studio_chrome_qss(
                f"QTreeWidget{{outline:none;}}"
                f"QTreeWidget::item{{padding:4px 5px;border-radius:8px;color:{_TEXT};}}"
                "QTreeWidget::branch{background:transparent;}"
            )
        )
        self._folder_tree.currentItemChanged.connect(self._on_folder_selected)
        vsplit.addWidget(self._folder_tree)

        # File grid
        grid_container = QWidget()
        gc = QVBoxLayout(grid_container)
        gc.setContentsMargins(0, 0, 0, 0)
        gc.setSpacing(0)

        self._char_grid = QListWidget()
        self._char_grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._char_grid.setIconSize(QSize(72, 72))
        self._char_grid.setGridSize(QSize(90, 100))
        self._char_grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._char_grid.setMovement(QListWidget.Movement.Static)
        self._char_grid.setSpacing(4)
        self._char_grid.setDragEnabled(True)
        self._char_grid.setStyleSheet(
            studio_chrome_qss(
                "QListWidget{border:none;outline:none;padding:4px;}"
                "QListWidget::item{border-radius:10px;padding:3px;}"
            )
        )
        self._char_grid.currentItemChanged.connect(self._on_char_current_changed)
        self._char_grid.itemClicked.connect(self._on_char_click)
        self._char_grid.itemDoubleClicked.connect(self._on_char_dclick)
        self._char_grid.startDrag = self._grid_start_drag
        gc.addWidget(self._char_grid, 1)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color:{_MUTED};font-size:10px;padding:3px 8px;")
        gc.addWidget(self._status_lbl)

        vsplit.addWidget(grid_container)
        vsplit.setSizes([200, 340])

        lay.addWidget(vsplit, 1)
        return w

    # ── center: viewport + bottom bar ────────────────────────────────────────

    def _build_center(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._viewport = SpineViewport()
        if hasattr(self._viewport, "first_frame_ready"):
            self._viewport.first_frame_ready.connect(self._on_first_frame_ready)
        lay.addWidget(self._viewport, 1)
        lay.addWidget(self._build_bottom_bar())
        return w

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(44)
        bar.setStyleSheet(f"background:{_PANEL};border-top:1px solid {_RULE};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(12, 0, 12, 0)
        bl.setSpacing(8)

        self._play_btn = QPushButton("")
        self._play_btn.setFixedSize(28, 28)
        self._set_play_icon(False)
        self._play_btn.setStyleSheet(_BTN)
        self._play_btn.setToolTip("재생/정지")
        self._play_btn.clicked.connect(self._toggle_play)
        bl.addWidget(self._play_btn)

        prev_btn = QPushButton("")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setIcon(app_icon("previous", size=15, color="#FFFFFF"))
        prev_btn.setIconSize(icon_size(15))
        prev_btn.setStyleSheet(_BTN)
        prev_btn.setToolTip("이전 애니메이션")
        prev_btn.clicked.connect(self._prev_anim)
        bl.addWidget(prev_btn)

        next_btn = QPushButton("")
        next_btn.setFixedSize(28, 28)
        next_btn.setIcon(app_icon("next", size=15, color="#FFFFFF"))
        next_btn.setIconSize(icon_size(15))
        next_btn.setStyleSheet(_BTN)
        next_btn.setToolTip("다음 애니메이션")
        next_btn.clicked.connect(self._next_anim)
        bl.addWidget(next_btn)

        self._anim_label = QLabel("—")
        self._anim_label.setStyleSheet(f"color:{_MUTED};font-size:11px;")
        self._anim_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        bl.addWidget(self._anim_label, 1)

        # Background swatches
        bl.addWidget(QLabel("배경"))
        for _name, col in [("dark", (.05, .05, .08, 1)), ("light", (.95, .95, .95, 1)), ("green", (0, .75, .2, 1))]:
            b = QPushButton("")
            b.setFixedSize(26, 26)
            r, g, bb, _a = col
            b.setStyleSheet(
                _BTN
                + f"QPushButton{{background:rgb({int(r*255)},{int(g*255)},{int(bb*255)});}}"
            )
            b.clicked.connect(lambda _, c=col: self._set_bg(*c))
            bl.addWidget(b)

        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet("color:#8A7CFF;font-size:10px;")
        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 100)
        self._loading_bar.setValue(0)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setFixedSize(130, 8)
        self._loading_bar.setVisible(False)
        self._loading_bar.setStyleSheet(
            "QProgressBar{background:#202331;border:1px solid #343A52;"
            "border-radius:4px;}"
            "QProgressBar::chunk{background:qlineargradient("
            "x1:0,y1:0,x2:1,y2:0,stop:0 #FF6A3D,stop:0.55 #7B61FF,stop:1 #38C7FF);"
            "border-radius:3px;}"
        )
        self._cancel_load_btn = QPushButton("취소")
        self._cancel_load_btn.setFixedHeight(22)
        self._cancel_load_btn.setStyleSheet(_BTN)
        self._cancel_load_btn.setVisible(False)
        self._cancel_load_btn.clicked.connect(self._cancel_loading)
        bl.addWidget(self._loading_bar)
        bl.addWidget(self._cancel_load_btn)
        bl.addWidget(self._info_lbl)
        return bar

    # ── right: inspector ──────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet(f"QWidget{{background:{_PANEL};}}")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        inner = QWidget()
        inner.setStyleSheet(f"QWidget{{background:{_PANEL};}}")
        il = QVBoxLayout(inner)
        il.setContentsMargins(10, 10, 10, 10)
        il.setSpacing(4)

        # ── Animation list ──
        il.addWidget(_section("애니메이션"))
        self._anim_list = QListWidget()
        self._anim_list.setFixedHeight(180)
        self._anim_list.itemClicked.connect(self._on_anim_click)
        self._anim_list.itemDoubleClicked.connect(self._on_anim_dclick)
        il.addWidget(self._anim_list)

        il.addWidget(_h_rule())

        # ── Skin selector ──
        il.addWidget(_section("스킨"))
        self._skin_combo = QComboBox()
        self._skin_combo.setStyleSheet(
            studio_chrome_qss("QComboBox{font-size:11px;}")
        )
        self._skin_combo.currentTextChanged.connect(self._on_skin_changed)
        il.addWidget(self._skin_combo)

        il.addWidget(_h_rule())

        # ── Position / Scale controls ──
        il.addWidget(_section("배치"))
        for label, attr, mn, mx, default in [
            ("X 위치", "_ctrl_x", 0, 100, 50),
            ("Y 위치", "_ctrl_y", 0, 100, 50),
            ("크기",   "_ctrl_s",    5, 200, 40),
        ]:
            row = QWidget(); row.setStyleSheet("background:transparent;")
            rl = QVBoxLayout(row); rl.setContentsMargins(0, 2, 0, 0); rl.setSpacing(1)
            top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0)
            lbl_w = QLabel(label); lbl_w.setStyleSheet(f"font-size:10px;color:{_MUTED};")
            val_lbl = QLabel(f"{default}"); val_lbl.setStyleSheet("font-size:10px;color:#8A7CFF;")
            val_lbl.setFixedWidth(30); val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            top.addWidget(lbl_w, 1); top.addWidget(val_lbl); rl.addLayout(top)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(mn, mx); slider.setValue(default); slider.setFixedHeight(16)
            setattr(self, attr, slider)
            setattr(self, attr + "_lbl", val_lbl)
            slider.valueChanged.connect(lambda v, vl=val_lbl, a=attr: self._on_ctrl_changed(v, vl, a))
            rl.addWidget(slider)
            il.addWidget(row)

        il.addWidget(_h_rule())

        # ── Bone display toggle ──
        il.addWidget(_section("표시"))
        bone_row = QHBoxLayout()
        self._bone_btn = QPushButton("뼈대 표시")
        self._bone_btn.setCheckable(True); self._bone_btn.setChecked(False)
        self._bone_btn.setIcon(app_icon("bone", size=15))
        self._bone_btn.setIconSize(icon_size(15))
        self._bone_btn.setStyleSheet(_BTN)
        self._bone_btn.toggled.connect(lambda on: setattr(self._viewport, '_show_bones', on) or self._viewport.update())
        bone_row.addWidget(self._bone_btn)
        self._frame_view_btn = QPushButton("작업 보기")
        self._frame_view_btn.setCheckable(True)
        self._frame_view_btn.setChecked(False)
        self._frame_view_btn.setIcon(app_icon("fit", size=15))
        self._frame_view_btn.setIconSize(icon_size(15))
        self._frame_view_btn.setStyleSheet(_BTN)
        self._frame_view_btn.setToolTip("작업 보기 / 최종 영상 프레임 보기")
        self._frame_view_btn.toggled.connect(self._on_view_mode_toggled)
        bone_row.addWidget(self._frame_view_btn)
        il.addLayout(bone_row)

        il.addWidget(_h_rule())
        il.addWidget(_section("로드 진단"))
        self._load_log_list = QListWidget()
        self._load_log_list.setFixedHeight(92)
        self._load_log_list.setStyleSheet(
            studio_chrome_qss(
                "QListWidget{font-size:9px;color:#A7ADC2;}"
                "QListWidget::item{padding:2px 5px;border-radius:6px;}"
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

    # ── folder tree browser ───────────────────────────────────────────────────

    def _all_search_roots(self) -> list[str]:
        roots = [_SAMPLES_DIR]
        if os.path.isdir(_BLUE_ARCHIVE_DIR):
            roots.append(_BLUE_ARCHIVE_DIR)
        roots.extend(self._extra_dirs)
        return [r for r in roots if os.path.isdir(r)]

    def _initial_spine_path(self) -> Optional[str]:
        """Pick the first sample to show when the editor opens."""
        nikke_root = os.path.join(_SAMPLES_DIR, "nikke")
        for folder_name in _NIKKE_INITIAL_FOLDERS:
            folder = os.path.join(nikke_root, folder_name)
            files = self._spine_files_in(folder, recursive=False)
            if files:
                return files[0]

        if os.path.isdir(nikke_root):
            try:
                for entry in sorted(os.scandir(nikke_root), key=lambda e: e.name.lower()):
                    if not entry.is_dir():
                        continue
                    files = self._spine_files_in(entry.path, recursive=False)
                    if files:
                        return files[0]
            except PermissionError:
                pass

        for root in self._all_search_roots():
            files = self._spine_files_in(root, recursive=True)
            if files:
                return files[0]
        return None

    def _refresh_folder_tree(self):
        self._folder_tree.clear()
        for root in self._all_search_roots():
            root_item = self._make_tree_node(root, is_root=True)
            if root_item:
                self._folder_tree.addTopLevelItem(root_item)
                root_item.setExpanded(True)
        # Select first leaf with Spine files
        self._auto_select_first()

    def _make_tree_node(self, directory: str, is_root: bool = False) -> Optional[QTreeWidgetItem]:
        """Recursively build tree nodes for directories that contain Spine files."""
        if not os.path.isdir(directory):
            return None
        has_files = bool(self._spine_files_in(directory, recursive=False))
        children: list[QTreeWidgetItem] = []
        try:
            for entry in sorted(os.scandir(directory), key=lambda e: e.name.lower()):
                if entry.is_dir():
                    child = self._make_tree_node(entry.path)
                    if child:
                        children.append(child)
        except PermissionError:
            pass

        if not has_files and not children:
            return None

        label = os.path.basename(directory)
        node = QTreeWidgetItem([label])
        node.setData(0, Qt.ItemDataRole.UserRole, directory)
        node.setToolTip(0, directory)
        # Folder icon indicator (bold for roots)
        if is_root:
            f = node.font(0)
            f.setBold(True)
            node.setFont(0, f)
        for child in children:
            node.addChild(child)
        return node

    @staticmethod
    def _spine_files_in(directory: str, recursive: bool = False) -> list[str]:
        """Return Spine files (.json / .skel) with companion .atlas in the same directory."""
        results: list[str] = []
        for ext in ("*.json", "*.skel"):
            pattern = os.path.join(directory, "**", ext) if recursive else os.path.join(directory, ext)
            for p in glob.glob(pattern, recursive=recursive):
                if p.endswith(".skel.json"):
                    continue
                stem = p[:-5]  # strip .skel or .json
                base_dir = os.path.dirname(p)
                # 1. Exact stem match
                if os.path.exists(stem + ".atlas"):
                    results.append(p)
                    continue
                # 2. Any .atlas in the same directory (e.g. "celestial-circus-pro.json" + "celestial-circus.atlas")
                atlases = glob.glob(os.path.join(base_dir, "*.atlas"))
                if atlases:
                    results.append(p)

        # Prefer JSON when a binary .skel has a same-stem JSON export. NIKKE
        # samples include both, and the JSON path is currently more complete.
        by_stem: dict[str, str] = {}
        for p in results:
            stem = p[:-5] if p.endswith(".skel") else os.path.splitext(p)[0]
            current = by_stem.get(stem)
            if current is None or p.lower().endswith(".json"):
                by_stem[stem] = p
        return sorted(set(by_stem.values()))

    def _auto_select_first(self):
        """Expand to and select the first tree node that has files."""
        def _walk(item: QTreeWidgetItem) -> bool:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and self._spine_files_in(path, recursive=False):
                self._folder_tree.setCurrentItem(item)
                return True
            for i in range(item.childCount()):
                if _walk(item.child(i)):
                    return True
            return False

        for i in range(self._folder_tree.topLevelItemCount()):
            if _walk(self._folder_tree.topLevelItem(i)):
                break

    def _on_folder_selected(self, current: Optional[QTreeWidgetItem], _previous):
        if current is None:
            return
        folder = current.data(0, Qt.ItemDataRole.UserRole)
        if folder and os.path.isdir(folder):
            self._current_folder = folder
            self._populate_grid(folder)

    def _populate_grid(self, directory: str):
        from PySide6.QtWidgets import QApplication
        self._char_grid.clear()
        candidates = self._spine_files_in(directory, recursive=False)
        self._status_lbl.setText(f"로딩 중… (0/{len(candidates)})")
        QApplication.processEvents()

        for i, path in enumerate(candidates):
            name = os.path.basename(path).replace(".json", "")
            icon = _generate_thumb(path)
            item = QListWidgetItem(icon, name)
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            item.setSizeHint(QSize(90, 100))
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            self._char_grid.addItem(item)
            if (i + 1) % 3 == 0:
                self._status_lbl.setText(f"로딩 중… ({i+1}/{len(candidates)})")
                QApplication.processEvents()

        count = len(candidates)
        if count == 1:
            self._status_lbl.setText("1개 - 자동 선택")
            if not self._suppress_single_folder_autoload:
                QTimer.singleShot(
                    0,
                    lambda path=candidates[0], folder=directory: self._auto_load_single_grid_item(path, folder),
                )
        else:
            self._status_lbl.setText(f"{count}개" if count else "Spine 파일 없음")

    def _auto_load_single_grid_item(self, path: str, directory: str) -> None:
        if directory != self._current_folder:
            return
        if self._char_grid.count() != 1:
            return
        item = self._char_grid.item(0)
        if item is None or item.data(Qt.ItemDataRole.UserRole) != path:
            return
        self._char_grid.blockSignals(True)
        self._char_grid.setCurrentItem(item)
        self._char_grid.blockSignals(False)
        if path and os.path.exists(path):
            if path != self._current_json:
                self._load_character(path)
            if self._target_clip is not None:
                self._assign_to_target(skel_path=path)

    def _add_search_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Spine 파일 폴더 추가", _SAMPLES_DIR,
        )
        if directory and directory not in self._extra_dirs:
            self._extra_dirs.append(directory)
            self._refresh_folder_tree()

    def _on_char_click(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            if path == self._current_json:
                return
            self._load_character(path)
            if self._target_clip is not None:
                self._assign_to_target(skel_path=path)

    def _on_char_current_changed(self, current: Optional[QListWidgetItem], _previous):
        if current is None:
            return
        path = current.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path) and path != self._current_json:
            self._load_character(path)
            if self._target_clip is not None:
                self._assign_to_target(skel_path=path)

    def _on_char_dclick(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            self._load_character(path)

    def _grid_start_drag(self, supported_actions):
        item = self._char_grid.currentItem()
        if item is None:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        mime = QMimeData()
        mime.setData("application/x-spine-model", QByteArray(path.encode()))
        mime.setUrls([QUrl.fromLocalFile(path)])
        pm = item.icon().pixmap(72, 72)
        drag = QDrag(self._char_grid)
        drag.setMimeData(mime)
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        drag.exec(supported_actions)

    # ── character loading ─────────────────────────────────────────────────────

    def load_character_deferred(self, path: str, delay_ms: int = 120) -> None:
        if not path:
            return
        self._load_generation += 1
        token = self._load_generation
        self._current_loading_path = path
        self._current_load_started_at = time.perf_counter()
        self._set_loading(True, "Spine 로드 준비 중…", progress=5, stage="queued")
        self._cache_load_status("loading", "queued", "Spine load queued", path=path)

        def _load(attempt: int = 0) -> None:
            if token != self._load_generation:
                return
            if not self.isVisible():
                if attempt < 20:
                    QTimer.singleShot(50, lambda: _load(attempt + 1))
                return
            self._load_character(path, _from_deferred=True)

        QTimer.singleShot(max(0, int(delay_ms)), _load)

    def _set_loading(self, active: bool, text: str = "", *, progress: int | None = None, stage: str = "") -> None:
        self._loading_active = bool(active)
        bar = getattr(self, "_loading_bar", None)
        if bar is not None:
            bar.setVisible(bool(active))
            if active:
                bar.setRange(0, 100)
                if progress is None and stage:
                    try:
                        from app.actor_loading_cache import actor_progress_for_stage
                        progress = actor_progress_for_stage(stage)
                    except Exception:
                        progress = None
                if progress is not None:
                    bar.setValue(max(0, min(100, int(progress))))
            elif progress is not None:
                bar.setValue(max(0, min(100, int(progress))))
        cancel = getattr(self, "_cancel_load_btn", None)
        if cancel is not None:
            cancel.setVisible(bool(active))
            cancel.setEnabled(bool(active))
        if text:
            self._info_lbl.setText(text)
            self._append_load_log(text)
        if not active:
            self._load_timeout_timer.stop()

    def _record_load_action(self, stage: str, **data) -> None:
        try:
            from app.crash_reporter import record_action
            record_action("actor.load_spine.stage", stage=stage, **data)
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
        actor_path = path or self._current_loading_path or self._current_json or ""
        if not actor_path:
            return
        try:
            from app.actor_loading_cache import record_actor_load
            record_actor_load(
                "spine",
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
        if log is None or not text:
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
            if btn is not None:
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
                path=self._current_loading_path or self._current_json or "",
            )
        except Exception:
            pass
        row = getattr(self, "_target_lane_row", None)
        if row is not None:
            try:
                row.update()
            except Exception:
                pass

    def _cancel_loading(self) -> None:
        self._load_generation += 1
        self._load_timeout_timer.stop()
        if hasattr(self._viewport, "clear"):
            self._viewport.clear()
        self._set_loading(False, "로드 취소됨", progress=100, stage="cancelled")
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("cancelled", "Spine load cancelled")
        self._cache_load_status("cancelled", "cancelled", "Spine load cancelled", path=self._last_failed_path or self._current_json or "")

    def _on_load_timeout(self) -> None:
        if not self._loading_active:
            return
        self._last_failed_path = self._current_loading_path or self._current_json or ""
        self._load_generation += 1
        if hasattr(self._viewport, "clear"):
            self._viewport.clear()
        msg = "첫 프레임 타임아웃: atlas/texture/GL 렌더 초기화를 확인하세요"
        self._set_loading(False, msg, progress=100, stage="timeout")
        self._set_failure_actions_visible(True)
        self._mark_target_clip_status("timeout", msg)
        self._cache_load_status("timeout", "timeout", msg, path=self._last_failed_path)

    def _retry_last_failed_model(self) -> None:
        path = self._last_failed_path or self._current_json
        if path:
            self.load_character_deferred(path, delay_ms=80)

    def _open_current_model_location(self) -> None:
        path = self._last_failed_path or self._current_json
        if not path:
            return
        try:
            os.startfile(os.path.dirname(path))
        except Exception as exc:
            self._append_load_log(f"위치 열기 실패: {exc}")

    def _load_sample_model(self) -> None:
        sample = self._initial_spine_path()
        if sample:
            self.load_character_deferred(sample, delay_ms=80)

    def _load_character(self, json_path: str, *, _from_deferred: bool = False):
        if not _from_deferred:
            self._load_generation += 1
        self._current_load_started_at = time.perf_counter()
        self._set_loading(True, "Spine 파일 확인 중…", progress=10, stage="file_check")
        self._cache_load_status("loading", "file_check", "Spine file check", path=json_path)
        try:
            from app.actor_compat_repair import repair_actor_model_path
            repair = repair_actor_model_path("spine", json_path)
            for step in repair.get("steps", []) or []:
                self._append_load_log(str(step))
            for warning in repair.get("warnings", []) or []:
                self._append_load_log(str(warning))
            if repair.get("path"):
                json_path = str(repair["path"])
            self._set_loading(True, "Spine 호환성 확인 중…", progress=30, stage="compat")
            self._cache_load_status("loading", "compat", "Spine compatibility checked", path=json_path, metadata=repair.get("metadata") or {})
        except Exception as exc:
            self._append_load_log(f"호환성 자동 확인 실패: {exc}")
            self._set_loading(True, "Spine 호환성 확인 중…", progress=30, stage="compat")
        if json_path.endswith(".skel"):
            json_peer = json_path[:-5] + ".json"
            if os.path.exists(json_peer):
                json_path = json_peer
        self._current_json = json_path
        self._current_loading_path = json_path
        self._set_failure_actions_visible(False)
        self._set_loading(True, f"Spine 파일 읽는 중… {os.path.basename(json_path)}", progress=55, stage="parse")
        self._mark_target_clip_status("loading", f"Spine loading: {os.path.basename(json_path)}")
        self._cache_load_status("loading", "parse", f"Spine parsing: {os.path.basename(json_path)}", path=json_path)
        try:
            self._load_timeout_timer.start(
                max(5_000, int(os.environ.get("TIGERCAPTURE_ACTOR_LOAD_TIMEOUT_MS", "25000")))
            )
        except Exception:
            self._load_timeout_timer.start(25_000)
        # Strip .skel or .json to get the stem for atlas lookup
        if json_path.endswith(".skel"):
            stem = json_path[:-5]
        else:
            stem = os.path.splitext(json_path)[0]
        base_dir = os.path.dirname(json_path)
        atlas_path = stem + ".atlas"

        try:
            from app.spine_editor.spine_json_parser import (
                load_spine_file, load_atlas, load_atlas_pages, atlas_is_pma)
            from PIL import Image as _PIL

            self._set_loading(True, "Spine skeleton 파싱 중…", progress=55, stage="parse")
            skel  = load_spine_file(json_path)
            atlas = {}; textures = []; pma = False

            # Find atlas: try exact stem match first, then any .atlas in same dir
            self._set_loading(True, "Atlas/texture 읽는 중…", progress=70, stage="textures")
            if not os.path.exists(atlas_path):
                candidates = glob.glob(os.path.join(base_dir, "*.atlas"))
                atlas_path = candidates[0] if candidates else atlas_path

            if os.path.exists(atlas_path):
                atlas   = load_atlas(atlas_path)
                pma     = atlas_is_pma(atlas_path)
                for pg in load_atlas_pages(atlas_path):
                    pp = os.path.join(base_dir, pg)
                    textures.append(_PIL.open(pp).convert("RGBA") if os.path.exists(pp) else None)

            self._viewport.set_skeleton(skel)
            self._viewport.set_renderer_data(atlas, textures, pma=pma)
            self._viewport._show_bones = False

            name = os.path.basename(stem)
            self._pending_loaded_name = f"{name}  {len(skel.bones)}뼈 {len(skel.animations)}애님"
            self._set_loading(True, "첫 프레임 렌더링 중…", progress=90, stage="first_frame")
            self._mark_target_clip_status("loading", f"Spine first frame: {name}")
            self._cache_load_status(
                "loading",
                "first_frame",
                f"Spine first frame: {name}",
                path=json_path,
                metadata={
                    "bones": len(skel.bones),
                    "animations": len(skel.animations),
                    "atlas_path": atlas_path if os.path.exists(atlas_path) else "",
                    "textures": len(textures),
                },
            )

            # Populate animation list
            self._anims = sorted(skel.animations.keys())
            self._anim_list.clear()
            for a in self._anims:
                dur = skel.animations[a].duration
                item = QListWidgetItem(f"{a}  ({dur:.1f}s)")
                item.setData(Qt.ItemDataRole.UserRole, a)
                self._anim_list.addItem(item)

            # Populate skin combo — auto-select first non-default if default is empty
            self._skin_combo.blockSignals(True)
            self._skin_combo.clear()
            skin_names = sorted(skel.skins.keys())
            for sk in skin_names:
                self._skin_combo.addItem(sk)
            if not skin_names:
                self._skin_combo.addItem("default")

            # Pick best initial skin: prefer non-default if default has no visual attachments
            from app.spine_editor.spine_data import RegionAttachment as _RA
            def _has_visual(skin_name):
                for atts in skel.skins.get(skin_name, {}).values():
                    for att in atts.values():
                        if isinstance(att, _RA) and not getattr(att, "_non_visual", False):
                            return True
                return False

            best_skin = "default"
            if not _has_visual("default"):
                # Try "full-skins/*" first, then first non-default
                for sk in skin_names:
                    if "full-skin" in sk.lower() or sk.startswith("full"):
                        best_skin = sk; break
                else:
                    non_def = [s for s in skin_names if s != "default"]
                    if non_def:
                        best_skin = non_def[0]

            idx = self._skin_combo.findText(best_skin)
            if idx >= 0:
                self._skin_combo.setCurrentIndex(idx)
            self._skin_combo.blockSignals(False)
            self._viewport._active_skin = best_skin
            if self._target_clip is not None:
                self._assign_to_target(skel_path=json_path, skin_name=best_skin)

            # Auto-play an idle/action animation when available.
            preferred = ("Idle_01", "idle", "Idle", "action", "Action", "walk", "Walk")
            pref = next((a for a in preferred if a in skel.animations), None)
            if pref is None:
                pref = next((a for a in self._anims if "idle" in a.lower()), None)
            if pref is None:
                pref = self._anims[0] if self._anims else None
            if pref:
                self._play_anim(self._anims.index(pref))

        except Exception as e:
            self._last_failed_path = json_path
            if hasattr(self._viewport, "clear"):
                self._viewport.clear()
            self._anims = []
            self._anim_list.clear()
            self._skin_combo.blockSignals(True)
            self._skin_combo.clear()
            self._skin_combo.addItem("default")
            self._skin_combo.blockSignals(False)
            self._anim_label.setText("—")
            self._set_loading(False, f"❌ {str(e)[:140]}", progress=100, stage="error")
            self._set_failure_actions_visible(True)
            self._mark_target_clip_status("error", str(e))
            self._cache_load_status("error", "error", str(e), path=json_path)

    def _on_first_frame_ready(self) -> None:
        if not self._loading_active:
            return
        name = self._pending_loaded_name or (
            os.path.basename(self._current_json or "") or "Spine"
        )
        self._cache_load_status("ready", "ready", f"Spine ready: {name}")
        self._set_loading(False, f"✓ {name}", progress=100, stage="ready")
        self._set_failure_actions_visible(False)
        self._mark_target_clip_status("ready", f"Spine ready: {name}")

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Spine 파일 열기", _SAMPLES_DIR,
            "Spine Files (*.json *.skel.json *.skel);;All Files (*.*)"
        )
        if path:
            self._load_character(path)

    # ── animation playback ────────────────────────────────────────────────────

    def _set_play_icon(self, playing: bool) -> None:
        btn = getattr(self, "_play_btn", None)
        if btn is None:
            return
        btn.setText("")
        btn.setIcon(app_icon("pause" if playing else "play", size=15, color="#FFFFFF"))
        btn.setIconSize(icon_size(15))

    def _play_anim(self, idx: int):
        if not (0 <= idx < len(self._anims)):
            return
        self._current_anim_idx = idx
        name = self._anims[idx]
        self._anim_label.setText(name)
        self._anim_list.setCurrentRow(idx)
        self._anim_time = 0.0
        self._update_viewport()
        self._assign_to_target(anim_name=name)

    def _on_anim_click(self, item: QListWidgetItem):
        idx = self._anim_list.row(item)
        self._play_anim(idx)

    def _on_anim_dclick(self, item: QListWidgetItem):
        idx = self._anim_list.row(item)
        self._play_anim(idx)
        self._playing = True
        self._set_play_icon(True)
        self._play_timer.start()

    def _prev_anim(self):
        if self._anims:
            self._play_anim((self._current_anim_idx - 1) % len(self._anims))

    def _next_anim(self):
        if self._anims:
            self._play_anim((self._current_anim_idx + 1) % len(self._anims))

    def _toggle_play(self):
        self._playing = not self._playing
        self._set_play_icon(self._playing)
        if self._playing:
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _should_loop_anim(self, name: str, anim) -> bool:
        if not anim or anim.duration <= 0:
            return False
        if anim.duration < 0.5:
            return False
        return True

    def _on_tick(self):
        if not self._playing:
            return
        self._anim_time += 0.033
        skel = getattr(self._viewport, '_skeleton', None)
        if skel and self._current_anim_idx >= 0 and self._anims:
            anim_name = self._anims[self._current_anim_idx]
            anim = skel.animations.get(anim_name)
            if anim and anim.duration > 0:
                if self._should_loop_anim(anim_name, anim):
                    self._anim_time %= anim.duration
                elif self._anim_time >= anim.duration:
                    self._anim_time = anim.duration
                    self._playing = False
                    self._set_play_icon(False)
                    self._play_timer.stop()
        self._update_viewport()

    def _update_viewport(self):
        skel = getattr(self._viewport, '_skeleton', None)
        if not skel or self._current_anim_idx < 0 or not self._anims:
            return
        anim = skel.animations.get(self._anims[self._current_anim_idx])
        if anim:
            skel.apply_animation(anim, self._anim_time)
        self._viewport.update()

    # ── controls ──────────────────────────────────────────────────────────────

    def _on_ctrl_changed(self, value: int, val_lbl: QLabel, attr: str):
        val_lbl.setText(str(value))
        self._apply_placement_controls_to_viewport()
        self._assign_placement_to_target()

    def _placement_values_from_controls(self) -> tuple[float, float, float]:
        x = self._ctrl_x.value() / 100.0
        y = self._ctrl_y.value() / 100.0
        scale = self._ctrl_s.value() / 40.0
        return x, y, scale

    def _apply_placement_controls_to_viewport(self) -> None:
        x, y, scale = self._placement_values_from_controls()
        if hasattr(self._viewport, "set_placement"):
            self._viewport.set_placement(x=x, y=y, scale=scale)
        else:
            self._viewport.update()

    def _on_view_mode_toggled(self, final_mode: bool) -> None:
        if hasattr(self._viewport, "set_placement_view_mode"):
            self._viewport.set_placement_view_mode("final" if final_mode else "work")
        if hasattr(self, "_frame_view_btn"):
            self._frame_view_btn.setText("프레임 보기" if final_mode else "작업 보기")

    def _assign_placement_to_target(self) -> None:
        clip = self._target_clip
        row = self._target_lane_row
        if clip is None:
            return
        x, y, scale = self._placement_values_from_controls()
        changed = False
        if abs(getattr(clip, "pos_x", 0.5) - x) > 1e-6:
            clip.pos_x = x
            changed = True
        if abs(getattr(clip, "pos_y", 0.5) - y) > 1e-6:
            clip.pos_y = y
            changed = True
        if abs(getattr(clip, "scale", 1.0) - scale) > 1e-6:
            clip.scale = scale
            changed = True
        if changed and row is not None:
            row.update()
            row.clip_changed.emit()
        if changed:
            self._focus_target_clip_preview()

    def _sync_placement_controls_from_clip(self, clip) -> None:
        if clip is None:
            return
        values = [
            (self._ctrl_x, self._ctrl_x_lbl, round(getattr(clip, "pos_x", 0.5) * 100)),
            (self._ctrl_y, self._ctrl_y_lbl, round(getattr(clip, "pos_y", 0.5) * 100)),
            (self._ctrl_s, self._ctrl_s_lbl, round(getattr(clip, "scale", 1.0) * 40)),
        ]
        for slider, label, value in values:
            value = max(slider.minimum(), min(slider.maximum(), int(value)))
            slider.blockSignals(True)
            slider.setValue(value)
            slider.blockSignals(False)
            label.setText(str(value))
        self._apply_placement_controls_to_viewport()

    def _on_skin_changed(self, name: str):
        self._viewport._active_skin = name
        self._viewport.update()
        self._assign_to_target(skin_name=name)

    def _set_bg(self, r: float, g: float, b: float, a: float = 1.0):
        col = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
        self._viewport.setStyleSheet(f"background:{col};")
        self._viewport.update()

    # ── timeline clip linking (같은 방식 as Live2D) ───────────────────────────

    def set_target_clip(self, clip, lane_row) -> None:
        self._target_clip     = clip
        self._target_lane_row = lane_row
        self._sync_output_aspect_ratio_from_parent()
        self._sync_placement_controls_from_clip(clip)
        if clip and not clip.skel_path and self._current_json:
            self._assign_to_target(skel_path=self._current_json)
            if self._current_anim_idx >= 0 and self._anims:
                self._assign_to_target(anim_name=self._anims[self._current_anim_idx])

    def _assign_to_target(self, skel_path: str = None,
                           anim_name: str = None, skin_name: str = None):
        clip = self._target_clip
        row  = self._target_lane_row
        if clip is None:
            return
        changed = False
        if skel_path is not None and clip.skel_path != skel_path:
            clip.skel_path = skel_path
            # Auto-detect atlas + texture
            stem = os.path.splitext(skel_path)[0]
            base = os.path.dirname(skel_path)
            clip.atlas_path   = stem + ".atlas" if os.path.exists(stem + ".atlas") else ""
            clip.texture_path = next(
                (os.path.join(base, pg) for pg in _get_pages(clip.atlas_path)
                 if os.path.exists(os.path.join(base, pg))), "")
            clip._renderer = None
            if hasattr(clip, "invalidate_render_cache"):
                clip.invalidate_render_cache()
            changed = True
        if anim_name is not None:
            clip.anim_name = anim_name
            skel = getattr(self._viewport, "_skeleton", None)
            anim = skel.animations.get(anim_name) if skel is not None else None
            if anim is not None and getattr(anim, "duration", 0) > 0:
                clip.duration_ms = max(
                    int(getattr(clip, "duration_ms", 0) or 0),
                    int(anim.duration * 1000) + 100,
                    6000,
                )
            if hasattr(clip, "invalidate_render_cache"):
                clip.invalidate_render_cache()
            changed = True
        if skin_name is not None:
            clip.skin_name = skin_name
            if hasattr(clip, "invalidate_render_cache"):
                clip.invalidate_render_cache()
            changed = True
        if changed and row is not None:
            row.update()
            row.clip_changed.emit()


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_pages(atlas_path: str) -> list[str]:
    if not atlas_path or not os.path.exists(atlas_path):
        return []
    try:
        from app.spine_editor.spine_json_parser import load_atlas_pages
        return load_atlas_pages(atlas_path)
    except Exception:
        return []


def _editor_output_aspect_ratio(owner) -> float:
    """Resolve the active editor canvas ratio, with a standalone 16:9 fallback."""
    settings = getattr(owner, "_project_settings", None) if owner is not None else None
    if isinstance(settings, dict):
        try:
            width = float(settings.get("canvas_width") or 0)
            height = float(settings.get("canvas_height") or 0)
            if width > 0 and height > 0:
                return width / height
        except (TypeError, ValueError):
            pass
    for attr in ("_export_resolution", "_preview_gl_frame_size"):
        value = getattr(owner, attr, None) if owner is not None else None
        if isinstance(value, (tuple, list)) and len(value) >= 2:
            try:
                width, height = float(value[0]), float(value[1])
                if width > 0 and height > 0:
                    return width / height
            except (TypeError, ValueError):
                pass
    return 16.0 / 9.0


def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(_SECTION)
    return lbl


def _h_rule() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color:{_RULE};")
    return f


def _spine_editor_focus_target_clip_preview(self) -> None:
    clip = getattr(self, "_target_clip", None)
    parent = self.parent()
    focus = getattr(parent, "_focus_actor_clip_for_edit", None)
    if clip is not None and callable(focus):
        try:
            focus(clip, refresh=True)
        except Exception:
            pass


SpineEditorWindow._focus_target_clip_preview = _spine_editor_focus_target_clip_preview
