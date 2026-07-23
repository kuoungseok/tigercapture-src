from __future__ import annotations

import copy
import json
import math
import tempfile
from datetime import datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QMimeData,
    QPoint,
    QPointF,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QIcon,
    QLinearGradient,
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
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMenuBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.i18n import tr


PAINT_CLIPBOARD_MIME = "application/x-tigercapture-paint-payload+json"
PAINT_CLIPBOARD_SCHEMA = "tigerstudio.paint.clipboard.v1"


_PAINT_DIALOG_QSS = """
QDialog {
    background-color: #111216;
    color: #f5f7fb;
}

QFrame#PaintTopBar,
QFrame#PaintToolRail,
QFrame#PaintInspector,
QFrame#PaintCanvasFrame {
    background-color: #15181d;
    border: 1px solid rgba(178, 186, 202, 26);
    border-radius: 8px;
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

QMenuBar#PaintMenuBar {
    background-color: #12151b;
    border: 1px solid rgba(178, 186, 202, 22);
    border-radius: 6px;
    color: #dce6f7;
    font-size: 11px;
    padding: 2px 6px;
}

QMenuBar#PaintMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 4px;
}

QMenuBar#PaintMenuBar::item:selected {
    background-color: #202635;
}

QMenu {
    background-color: #15181d;
    color: #eef3fb;
    border: 1px solid #303847;
    padding: 5px;
}

QMenu::item {
    padding: 5px 24px 5px 14px;
}

QMenu::item:selected {
    background-color: #24314a;
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
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,255,255,10), stop:0.48 rgba(255,255,255,5),
        stop:1 rgba(0,0,0,22));
    color: #eef3fb;
    border-top: 1px solid rgba(238,242,250,44);
    border-left: 1px solid rgba(178,186,202,28);
    border-right: 1px solid rgba(0,0,0,82);
    border-bottom: 1px solid rgba(0,0,0,104);
    border-radius: 7px;
    padding: 7px 10px;
    font-weight: 760;
    font-size: 11px;
    text-align: left;
    min-height: 32px;
}

QPushButton#PaintTool:hover,
QPushButton#BubbleBtn:hover,
QPushButton#StickerBtn:hover {
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,255,255,15), stop:1 rgba(255,255,255,5));
    border-top-color: rgba(255,255,255,70);
    border-left-color: rgba(220,225,238,58);
}

QPushButton#PaintTool:checked,
QPushButton#BubbleBtn:checked,
QPushButton#StickerBtn:checked {
    background: #243149;
    border-top-color: rgba(125,170,240,122);
    border-left-color: rgba(125,170,240,72);
    border-right-color: rgba(0,0,0,88);
    border-bottom-color: rgba(0,0,0,108);
    color: #ffffff;
}

QFrame#PaintToolRail QPushButton {
    min-width: 36px;
    max-width: 36px;
    min-height: 36px;
    max-height: 36px;
    padding: 0;
    text-align: center;
}

QFrame#PaintToolRail QPushButton#PaintTool,
QFrame#PaintToolRail QPushButton#BubbleBtn,
QFrame#PaintToolRail QPushButton#StickerBtn,
QFrame#PaintToolRail QPushButton#PaintDanger {
    border-radius: 5px;
    padding: 0;
}

QPushButton#PaintDanger {
    background-color: #241b1d;
    color: #ffdede;
    border: 1px solid rgba(204, 91, 91, 62);
    border-radius: 7px;
    padding: 7px 10px;
    font-weight: 760;
    min-height: 32px;
    text-align: left;
}

QPushButton#PaintDanger:hover {
    background-color: #3a2727;
    border-color: #de6969;
}

QPushButton#PaintCustomColor {
    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
        stop:0 rgba(255,255,255,8), stop:1 rgba(0,0,0,18));
    color: #f0f4fb;
    border-top: 1px solid rgba(238,242,250,38);
    border-left: 1px solid rgba(178,186,202,26);
    border-right: 1px solid rgba(0,0,0,74);
    border-bottom: 1px solid rgba(0,0,0,96);
    border-radius: 7px;
    padding: 6px 9px;
    font-weight: 760;
    min-height: 28px;
}

QPushButton#PaintCustomColor:hover {
    background-color: #242a34;
    border-top-color: rgba(255,255,255,68);
}

QFrame#PaintColorPanel {
    background-color: #11151b;
    border: 1px solid rgba(178, 186, 202, 22);
    border-radius: 8px;
}

QScrollArea#PaintInspectorScroll {
    background-color: transparent;
    border: none;
}

QScrollArea#PaintInspectorScroll > QWidget > QWidget {
    background-color: transparent;
}

QScrollArea#PaintInspectorScroll QScrollBar:vertical {
    background-color: #0c1017;
    border: 1px solid rgba(178, 186, 202, 18);
    border-radius: 4px;
    width: 8px;
    margin: 0;
}

QScrollArea#PaintInspectorScroll QScrollBar::handle:vertical {
    background-color: #3b4658;
    border-radius: 4px;
    min-height: 32px;
}

QScrollArea#PaintInspectorScroll QScrollBar::add-line:vertical,
QScrollArea#PaintInspectorScroll QScrollBar::sub-line:vertical {
    height: 0;
    background: transparent;
    border: none;
}

QScrollArea#PaintInspectorScroll QScrollBar::add-page:vertical,
QScrollArea#PaintInspectorScroll QScrollBar::sub-page:vertical {
    background: transparent;
}

QTabWidget#PaintLayerChannelPathTabs {
    background-color: #12151b;
}

QTabWidget#PaintLayerChannelPathTabs::pane {
    background-color: #11151b;
    border: 1px solid rgba(178, 186, 202, 28);
    border-top-color: rgba(178, 186, 202, 38);
    border-radius: 0;
    top: -1px;
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab {
    background-color: #24262a;
    color: #aeb7c7;
    border: 1px solid rgba(178, 186, 202, 30);
    border-bottom: 0;
    padding: 7px 13px;
    min-width: 54px;
    font-size: 11px;
    font-weight: 760;
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab:selected {
    background-color: #3a3b3e;
    color: #ffffff;
    border-color: rgba(220, 226, 238, 48);
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab:!selected:hover {
    background-color: #2d3036;
    color: #dce6f7;
}

QFrame#PaintLayerControlPanel {
    background-color: #16191f;
    border: 1px solid rgba(178, 186, 202, 20);
    border-radius: 0;
}

QLabel#PaintLayerControlLabel {
    color: #aeb7c7;
    font-size: 11px;
    font-weight: 700;
}

QPushButton#PaintLayerTinyButton {
    background-color: transparent;
    color: #dce6f7;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0;
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
}

QPushButton#PaintLayerTinyButton:hover {
    background-color: #242a34;
    border-color: rgba(178, 186, 202, 38);
}

QPushButton#PaintLayerTinyButton:checked {
    background-color: #343a45;
    border-color: rgba(220, 226, 238, 58);
}

QComboBox#PaintLayerFilterCombo,
QComboBox#PaintLayerBlendCombo {
    background-color: #20242b;
    color: #dce6f7;
    border: 1px solid rgba(178, 186, 202, 28);
    border-radius: 3px;
    padding: 4px 8px;
    min-width: 0;
}

QLabel#PaintColorWell {
    border: 1px solid #4c5870;
    border-radius: 9px;
}

QLabel#PaintPbrPreview {
    background-color: #08090c;
    border: 1px solid #2c3342;
    border-radius: 8px;
    color: #8f98a7;
    min-height: 130px;
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
    height: 3px;
    border-radius: 2px;
    background: #282d38;
}

QSlider::handle:horizontal {
    width: 12px;
    height: 12px;
    margin: -5px 0;
    border-radius: 6px;
    background: #afc2de;
    border: 1px solid #0b0e13;
}

QSlider#PaintHueSlider::groove:horizontal {
    height: 5px;
    border-radius: 3px;
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
    width: 12px;
    height: 12px;
    margin: -4px 0;
    border-radius: 6px;
    background: #e8eef8;
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

QListWidget#PaintBrushList {
    background-color: #11151d;
    color: #dce6f7;
    border: 1px solid #2c3342;
    border-radius: 8px;
    outline: none;
    padding: 5px;
}

QListWidget#PaintBrushList::item {
    border-radius: 6px;
    padding: 7px 8px;
    margin: 1px;
}

QListWidget#PaintBrushList::item:selected {
    background-color: #242b3a;
    color: #ffffff;
    border: 1px solid #7f8da3;
}

QDialogButtonBox QPushButton {
    min-width: 92px;
    padding: 8px 16px;
    border-radius: 7px;
    font-weight: 800;
    font-size: 12px;
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


def _clean_paint_button_text(text: str) -> str:
    """Strip decorative leading symbols from translated paint button labels."""
    value = str(text or "").strip()
    for index, char in enumerate(value):
        if char.isalnum():
            return value[index:].strip()
    return value


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
    layer_id: str = "paint-layer-1"
    source_tool: str = "pen"
    start_ms: int = 0
    end_ms: int | None = None

    def is_active(self, t_ms: int) -> bool:
        if t_ms < self.start_ms:
            return False
        if self.end_ms is not None and t_ms >= self.end_ms:
            return False
        return True


@dataclass
class PaintLayer:
    layer_id: str
    name: str
    visible: bool = True
    opacity: int = 100
    locked: bool = False
    blend_mode: str = "normal"
    mask: list[tuple[float, float]] = field(default_factory=list)
    mask_enabled: bool = False


CANVAS_SIZE_PRESETS: tuple[tuple[str, int, int], ...] = (
    ("Full HD 16:9", 1920, 1080),
    ("HD 16:9", 1280, 720),
    ("4K UHD 16:9", 3840, 2160),
    ("Square 1:1", 1080, 1080),
    ("Vertical 9:16", 1080, 1920),
    ("A4 Portrait 300 DPI", 2480, 3508),
    ("A4 Landscape 300 DPI", 3508, 2480),
)
CANVAS_BACKGROUND_PRESETS: tuple[tuple[str, str], ...] = (
    ("White", "#FFFFFF"),
    ("Transparent", "transparent"),
    ("Dark", "#101112"),
)


def create_blank_paint_pixmap(width: int, height: int, background: str = "#FFFFFF") -> QPixmap:
    """Create a blank Painter canvas pixmap.

    ``background="transparent"`` keeps alpha at zero; every other value is
    treated as a QColor string and filled as an opaque page.
    """
    safe_w = max(1, min(16384, int(width or 1)))
    safe_h = max(1, min(16384, int(height or 1)))
    pixmap = QPixmap(safe_w, safe_h)
    if str(background or "").strip().lower() in {"transparent", "alpha", "none"}:
        pixmap.fill(QColor(0, 0, 0, 0))
    else:
        color = QColor(str(background or "#FFFFFF"))
        if not color.isValid():
            color = QColor("#FFFFFF")
        pixmap.fill(color)
    return pixmap


def create_checkerboard_paint_pixmap(width: int, height: int, cell: int = 24) -> QPixmap:
    safe_w = max(1, min(16384, int(width or 1)))
    safe_h = max(1, min(16384, int(height or 1)))
    tile = max(4, int(cell or 24))
    pixmap = QPixmap(safe_w, safe_h)
    pixmap.fill(QColor("#d9dee8"))
    painter = QPainter(pixmap)
    try:
        dark = QColor("#aeb6c4")
        for y in range(0, safe_h, tile):
            for x in range(0, safe_w, tile):
                if ((x // tile) + (y // tile)) % 2:
                    painter.fillRect(x, y, tile, tile, dark)
    finally:
        painter.end()
    return pixmap


class NewCanvasDialog(QDialog):
    """Small first-run dialog for standalone Painter canvas creation."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        default_size: tuple[int, int] = (1920, 1080),
        default_background: str = "#FFFFFF",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Canvas")
        self.setModal(True)
        self.setStyleSheet(self.styleSheet() + _PAINT_DIALOG_QSS)
        self._syncing = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("New Canvas")
        title.setObjectName("PaintTitle")
        subtitle = QLabel("Choose a canvas template or enter a custom size.")
        subtitle.setObjectName("PaintSubtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        form = QFrame(self)
        form.setObjectName("PaintCanvasFrame")
        grid = QGridLayout(form)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)

        preset_label = QLabel("Template")
        preset_label.setObjectName("PaintMeta")
        self.preset_combo = QComboBox(form)
        for name, width, height in CANVAS_SIZE_PRESETS:
            self.preset_combo.addItem(name, (width, height))
        self.preset_combo.addItem("Custom", "custom")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        grid.addWidget(preset_label, 0, 0)
        grid.addWidget(self.preset_combo, 0, 1, 1, 3)

        width_label = QLabel("Width")
        width_label.setObjectName("PaintMeta")
        height_label = QLabel("Height")
        height_label.setObjectName("PaintMeta")
        self.width_spin = QSpinBox(form)
        self.width_spin.setRange(64, 16384)
        self.width_spin.setSuffix(" px")
        self.height_spin = QSpinBox(form)
        self.height_spin.setRange(64, 16384)
        self.height_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_custom_size_changed)
        self.height_spin.valueChanged.connect(self._on_custom_size_changed)
        grid.addWidget(width_label, 1, 0)
        grid.addWidget(self.width_spin, 1, 1)
        grid.addWidget(height_label, 1, 2)
        grid.addWidget(self.height_spin, 1, 3)

        background_label = QLabel("Background")
        background_label.setObjectName("PaintMeta")
        self.background_combo = QComboBox(form)
        for label, value in CANVAS_BACKGROUND_PRESETS:
            self.background_combo.addItem(label, value)
        grid.addWidget(background_label, 2, 0)
        grid.addWidget(self.background_combo, 2, 1, 1, 3)
        root.addWidget(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Create")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.resize(420, 240)
        self._set_initial_values(default_size, default_background)

    def _set_initial_values(self, size: tuple[int, int], background: str) -> None:
        width = max(64, min(16384, int(size[0] or 1920)))
        height = max(64, min(16384, int(size[1] or 1080)))
        match_index = -1
        for idx in range(self.preset_combo.count() - 1):
            preset = self.preset_combo.itemData(idx)
            if preset == (width, height):
                match_index = idx
                break
        self._syncing = True
        try:
            self.width_spin.setValue(width)
            self.height_spin.setValue(height)
            self.preset_combo.setCurrentIndex(match_index if match_index >= 0 else self.preset_combo.count() - 1)
            bg = str(background or "#FFFFFF").lower()
            for idx in range(self.background_combo.count()):
                if str(self.background_combo.itemData(idx)).lower() == bg:
                    self.background_combo.setCurrentIndex(idx)
                    break
        finally:
            self._syncing = False

    def _on_preset_changed(self) -> None:
        if self._syncing:
            return
        preset = self.preset_combo.currentData()
        if not isinstance(preset, tuple):
            return
        width, height = preset
        self._syncing = True
        try:
            self.width_spin.setValue(int(width))
            self.height_spin.setValue(int(height))
        finally:
            self._syncing = False

    def _on_custom_size_changed(self) -> None:
        if self._syncing:
            return
        current = (self.width_spin.value(), self.height_spin.value())
        for idx in range(self.preset_combo.count() - 1):
            if self.preset_combo.itemData(idx) == current:
                self._syncing = True
                try:
                    self.preset_combo.setCurrentIndex(idx)
                finally:
                    self._syncing = False
                return
        custom_index = self.preset_combo.count() - 1
        if self.preset_combo.currentIndex() != custom_index:
            self._syncing = True
            try:
                self.preset_combo.setCurrentIndex(custom_index)
            finally:
                self._syncing = False

    def canvas_request(self) -> dict:
        return {
            "width": int(self.width_spin.value()),
            "height": int(self.height_spin.value()),
            "background": str(self.background_combo.currentData() or "#FFFFFF"),
            "template": str(self.preset_combo.currentText() or "Custom"),
        }


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
    selection_probe_requested = Signal(str, float, float)

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
        self._active_layer_id: str = "paint-layer-1"
        self._layer_visibility: dict[str, bool] = {}
        self._layer_opacity: dict[str, int] = {}
        self._layer_masks: dict[str, list[tuple[float, float]]] = {}
        self._current_points: list[QPointF] = []  # while drawing (widget px)
        self._path_points: list[QPointF] = []
        self._selection_points: list[tuple[float, float]] = []
        self._selection_inverted: bool = False
        self._selection_aspect_mode: str = "free"
        self._selection_drag_tool: str = ""
        self._selection_drag_start: QPointF | None = None
        self._selection_drag_current: QPointF | None = None
        self._selection_phase: float = 0.0
        self._quick_mask_enabled: bool = False
        self._grid_visible: bool = False
        self._snap_enabled: bool = False
        self._grid_size_px: int = 64
        self._selection_timer = QTimer(self)
        self._selection_timer.setInterval(90)
        self._selection_timer.timeout.connect(self._advance_selection_march)
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
        if tool not in (
            "off",
            "pen",
            "eraser",
            "path",
            "rect_select",
            "ellipse_select",
            "crop",
            "magic_select",
        ):
            tool = "off"
        self._tool = tool
        self._refresh_mouse_transparency()
        cursor = (
            Qt.CursorShape.CrossCursor
            if tool in ("pen", "eraser", "path", "rect_select", "ellipse_select", "crop", "magic_select")
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

    def set_active_layer_id(self, layer_id: str | None) -> None:
        self._active_layer_id = str(layer_id or "paint-layer-1")

    def set_layer_view(
        self,
        visibility: dict[str, bool] | None = None,
        opacity: dict[str, int] | None = None,
        masks: dict[str, list[tuple[float, float]]] | None = None,
    ) -> None:
        self._layer_visibility = dict(visibility or {})
        self._layer_opacity = {
            str(key): max(0, min(100, int(value)))
            for key, value in dict(opacity or {}).items()
        }
        clean_masks: dict[str, list[tuple[float, float]]] = {}
        for key, value in dict(masks or {}).items():
            rows = list(value or [])
            if len(rows) < 3:
                continue
            clean_masks[str(key)] = [
                (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
                for x, y in rows
            ]
        self._layer_masks = clean_masks
        self.update()

    def path_point_count(self) -> int:
        return len(self._path_points)

    def path_snapshot(self) -> list[tuple[float, float]]:
        if not self._path_points:
            return []
        w = max(1, self.width())
        h = max(1, self.height())
        return [
            (max(0.0, min(1.0, point.x() / w)), max(0.0, min(1.0, point.y() / h)))
            for point in self._path_points
        ]

    def has_active_selection(self) -> bool:
        return len(self._selection_points) >= 3

    def selection_point_count(self) -> int:
        return len(self._selection_points)

    def selection_snapshot(self) -> list[tuple[float, float]]:
        return list(self._selection_points)

    def set_selection_aspect_mode(self, mode: str) -> None:
        value = str(mode or "free").strip().casefold().replace("-", "_")
        aliases = {
            "1_1": "square",
            "1:1": "square",
            "square": "square",
            "16_9": "16:9",
            "16:9": "16:9",
            "4_3": "4:3",
            "4:3": "4:3",
            "free": "free",
            "custom": "free",
        }
        self._selection_aspect_mode = aliases.get(value, "free")

    def selection_aspect_mode(self) -> str:
        return str(self._selection_aspect_mode or "free")

    def quick_mask_enabled(self) -> bool:
        return bool(getattr(self, "_quick_mask_enabled", False))

    def set_quick_mask_enabled(self, enabled: bool) -> None:
        self._quick_mask_enabled = bool(enabled)
        self.update()

    def set_grid_options(
        self,
        *,
        visible: bool | None = None,
        snap: bool | None = None,
        size_px: int | None = None,
    ) -> None:
        if visible is not None:
            self._grid_visible = bool(visible)
        if snap is not None:
            self._snap_enabled = bool(snap)
        if size_px is not None:
            self._grid_size_px = max(4, min(512, int(size_px or 64)))
        self.update()

    def grid_options(self) -> dict[str, int | bool]:
        return {
            "visible": bool(getattr(self, "_grid_visible", False)),
            "snap": bool(getattr(self, "_snap_enabled", False)),
            "size_px": int(getattr(self, "_grid_size_px", 64) or 64),
        }

    def select_rectangle(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        shape: str = "rect",
        aspect: str | None = None,
    ) -> None:
        rect = self._normalized_drag_rect(
            QPointF(float(x1) * max(1, self.width()), float(y1) * max(1, self.height())),
            QPointF(float(x2) * max(1, self.width()), float(y2) * max(1, self.height())),
            aspect or self._selection_aspect_mode,
        )
        points = self._points_from_drag_rect(rect, shape=shape)
        self.set_selection_snapshot(points)

    def selection_inverted(self) -> bool:
        return bool(getattr(self, "_selection_inverted", False))

    def set_selection_snapshot(
        self,
        points: list[tuple[float, float]] | None,
        *,
        inverted: bool = False,
    ) -> None:
        self._selection_points = [
            (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
            for x, y in list(points or [])
        ]
        self._selection_inverted = bool(inverted and len(self._selection_points) >= 3)
        self._sync_selection_timer()
        self.repaint_requested.emit()
        self.update()

    def clear_selection(self) -> None:
        if not self._selection_points and not self._selection_inverted:
            return
        self._selection_points = []
        self._selection_inverted = False
        self._sync_selection_timer()
        self.repaint_requested.emit()
        self.update()

    def select_all(self) -> None:
        self.set_selection_snapshot(
            [
                (0.0, 0.0),
                (1.0, 0.0),
                (1.0, 1.0),
                (0.0, 1.0),
            ]
        )

    def invert_selection(self) -> None:
        if len(self._selection_points) < 3:
            self.select_all()
            return
        self._selection_inverted = not bool(self._selection_inverted)
        self._sync_selection_timer()
        self.repaint_requested.emit()
        self.update()

    def _advance_selection_march(self) -> None:
        if not self.has_active_selection():
            self._selection_timer.stop()
            return
        self._selection_phase = (self._selection_phase + 1.0) % 12.0
        self.update()

    def _sync_selection_timer(self) -> None:
        if self.has_active_selection():
            if not self._selection_timer.isActive():
                self._selection_timer.start()
        else:
            self._selection_timer.stop()

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

        self._paint_grid(painter, w, h)

        t_ms = int(self._get_time_ms())
        for stroke in self._get_strokes():
            if not stroke.is_active(t_ms):
                continue
            layer_id = self._stroke_layer_id(stroke)
            if not self._layer_visibility.get(layer_id, True):
                continue
            mask = self._layer_masks.get(layer_id, [])
            if len(mask) >= 3:
                painter.save()
                self._clip_to_layer_mask(painter, mask, w, h)
            try:
                self._paint_stroke(
                    painter,
                    stroke,
                    w,
                    h,
                    opacity_scale=self._layer_opacity.get(layer_id, 100) / 100.0,
                )
            finally:
                if len(mask) >= 3:
                    painter.restore()

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
                layer_id=self._active_layer_id,
                source_tool="pen",
            )
            mask = self._layer_masks.get(self._active_layer_id, [])
            if len(mask) >= 3:
                painter.save()
                self._clip_to_layer_mask(painter, mask, w, h)
            try:
                self._paint_stroke(
                    painter,
                    stroke,
                    w,
                    h,
                    opacity_scale=self._layer_opacity.get(self._active_layer_id, 100) / 100.0,
                )
            finally:
                if len(mask) >= 3:
                    painter.restore()

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

        self._paint_selection_drag_preview(painter, w, h)
        self._paint_quick_mask_overlay(painter, w, h)
        self._paint_marching_ants(painter, w, h)

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
    def _stroke_layer_id(stroke: Stroke) -> str:
        return str(getattr(stroke, "layer_id", "") or "paint-layer-1")

    @staticmethod
    def _clip_to_layer_mask(
        painter: QPainter,
        points: list[tuple[float, float]],
        w: int,
        h: int,
    ) -> None:
        if len(points) < 3:
            return
        path = QPainterPath()
        path.moveTo(points[0][0] * w, points[0][1] * h)
        for x, y in points[1:]:
            path.lineTo(x * w, y * h)
        path.closeSubpath()
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)

    @staticmethod
    def _paint_stroke(
        painter: QPainter,
        stroke: Stroke,
        w: int,
        h: int,
        *,
        opacity_scale: float = 1.0,
    ) -> None:
        color = QColor(*stroke.color)
        color.setAlpha(max(0, min(255, int(stroke.opacity * opacity_scale))))
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

    def _paint_marching_ants(self, painter: QPainter, w: int, h: int) -> None:
        if len(self._selection_points) < 3:
            return
        path = self._selection_path(w, h)

        painter.save()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._selection_inverted:
            outside_pen = QPen(QColor(78, 142, 255, 150), 1.0)
            outside_pen.setCosmetic(True)
            outside_pen.setStyle(Qt.PenStyle.DashLine)
            outside_pen.setDashOffset(-self._selection_phase)
            painter.setPen(outside_pen)
            painter.drawRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0))
        for color, offset in (
            (QColor(0, 0, 0, 235), 0.0),
            (QColor(255, 255, 255, 245), 6.0),
        ):
            pen = QPen(color, 1.35)
            pen.setCosmetic(True)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
            pen.setDashPattern([6.0, 6.0])
            pen.setDashOffset(self._selection_phase + offset)
            painter.setPen(pen)
            painter.drawPath(path)
        painter.restore()

    def _selection_path(self, w: int, h: int) -> QPainterPath:
        path = QPainterPath()
        if len(self._selection_points) < 3:
            return path
        pts = [QPointF(x * w, y * h) for x, y in self._selection_points]
        path.moveTo(pts[0])
        for point in pts[1:]:
            path.lineTo(point)
        path.closeSubpath()
        return path

    def _paint_quick_mask_overlay(self, painter: QPainter, w: int, h: int) -> None:
        if not bool(getattr(self, "_quick_mask_enabled", False)):
            return
        painter.save()
        overlay = QColor(220, 43, 78, 70)
        if len(self._selection_points) < 3:
            painter.fillRect(QRectF(0, 0, w, h), overlay)
            painter.restore()
            return
        selection_path = self._selection_path(w, h)
        if self._selection_inverted:
            mask_path = selection_path
        else:
            full_path = QPainterPath()
            full_path.addRect(QRectF(0, 0, w, h))
            mask_path = full_path.subtracted(selection_path)
        painter.fillPath(mask_path, overlay)
        painter.restore()

    def _paint_grid(self, painter: QPainter, w: int, h: int) -> None:
        if not bool(getattr(self, "_grid_visible", False)):
            return
        step = max(4, min(512, int(getattr(self, "_grid_size_px", 64) or 64)))
        painter.save()
        minor = QPen(QColor(170, 190, 220, 40), 1.0)
        minor.setCosmetic(True)
        major = QPen(QColor(210, 225, 245, 58), 1.0)
        major.setCosmetic(True)
        for idx, x in enumerate(range(0, w + 1, step)):
            painter.setPen(major if idx % 4 == 0 else minor)
            painter.drawLine(QPointF(x + 0.5, 0), QPointF(x + 0.5, h))
        for idx, y in enumerate(range(0, h + 1, step)):
            painter.setPen(major if idx % 4 == 0 else minor)
            painter.drawLine(QPointF(0, y + 0.5), QPointF(w, y + 0.5))
        painter.restore()

    def _paint_selection_drag_preview(self, painter: QPainter, _w: int, _h: int) -> None:
        if self._selection_drag_start is None or self._selection_drag_current is None:
            return
        rect = self._selection_drag_rect()
        if rect.width() <= 1.0 or rect.height() <= 1.0:
            return
        painter.save()
        fill = QColor(87, 139, 255, 34)
        if self._selection_drag_tool == "crop":
            fill = QColor(248, 181, 70, 34)
        painter.setBrush(fill)
        pen = QPen(QColor("#E8EEF8"), 1.35)
        pen.setCosmetic(True)
        pen.setDashPattern([5.0, 5.0])
        pen.setDashOffset(self._selection_phase)
        painter.setPen(pen)
        if self._selection_drag_tool == "ellipse_select":
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        painter.restore()

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

    def _selection_drag_rect(self) -> QRectF:
        if self._selection_drag_start is None or self._selection_drag_current is None:
            return QRectF()
        return self._normalized_drag_rect(
            self._selection_drag_start,
            self._selection_drag_current,
            self._selection_aspect_mode,
        )

    def _normalized_drag_rect(
        self,
        start: QPointF,
        current: QPointF,
        aspect: str | None = None,
    ) -> QRectF:
        x1 = max(0.0, min(float(self.width()), float(start.x())))
        y1 = max(0.0, min(float(self.height()), float(start.y())))
        x2 = max(0.0, min(float(self.width()), float(current.x())))
        y2 = max(0.0, min(float(self.height()), float(current.y())))
        dx = x2 - x1
        dy = y2 - y1
        mode = str(aspect or "free").strip().casefold()
        ratios = {
            "square": 1.0,
            "1:1": 1.0,
            "16:9": 16.0 / 9.0,
            "4:3": 4.0 / 3.0,
        }
        ratio = ratios.get(mode)
        if ratio is not None and abs(dx) > 0.001 and abs(dy) > 0.001:
            sx = 1.0 if dx >= 0 else -1.0
            sy = 1.0 if dy >= 0 else -1.0
            adx = abs(dx)
            ady = abs(dy)
            if adx / max(1.0, ady) > ratio:
                adx = ady * ratio
            else:
                ady = adx / ratio
            x2 = x1 + sx * adx
            y2 = y1 + sy * ady
        left = max(0.0, min(x1, x2))
        top = max(0.0, min(y1, y2))
        right = min(float(self.width()), max(x1, x2))
        bottom = min(float(self.height()), max(y1, y2))
        return QRectF(left, top, max(0.0, right - left), max(0.0, bottom - top))

    def _points_from_drag_rect(self, rect: QRectF, *, shape: str = "rect") -> list[tuple[float, float]]:
        w = max(1, self.width())
        h = max(1, self.height())
        left = max(0.0, min(1.0, rect.left() / w))
        top = max(0.0, min(1.0, rect.top() / h))
        right = max(0.0, min(1.0, rect.right() / w))
        bottom = max(0.0, min(1.0, rect.bottom() / h))
        if str(shape or "rect") == "ellipse":
            cx = (left + right) * 0.5
            cy = (top + bottom) * 0.5
            rx = abs(right - left) * 0.5
            ry = abs(bottom - top) * 0.5
            return [
                (
                    max(0.0, min(1.0, cx + math.cos(math.tau * i / 32.0) * rx)),
                    max(0.0, min(1.0, cy + math.sin(math.tau * i / 32.0) * ry)),
                )
                for i in range(32)
            ]
        return [
            (left, top),
            (right, top),
            (right, bottom),
            (left, bottom),
        ]

    def _snap_canvas_point(self, point: QPointF) -> QPointF:
        if not (
            bool(getattr(self, "_grid_visible", False))
            and bool(getattr(self, "_snap_enabled", False))
        ):
            return QPointF(point)
        step = max(4, min(512, int(getattr(self, "_grid_size_px", 64) or 64)))
        x = round(float(point.x()) / step) * step
        y = round(float(point.y()) / step) * step
        return QPointF(
            max(0.0, min(float(self.width()), float(x))),
            max(0.0, min(float(self.height()), float(y))),
        )

    # ------------- mouse interaction -------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._tool == "magic_select":
            w = max(1, self.width())
            h = max(1, self.height())
            self.selection_probe_requested.emit("color", pos.x() / w, pos.y() / h)
            return
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
        if self._tool in {"rect_select", "ellipse_select", "crop"}:
            self._selection_drag_tool = self._tool
            snapped = self._snap_canvas_point(pos)
            self._selection_drag_start = QPointF(snapped)
            self._selection_drag_current = QPointF(snapped)
            self.update()
            return
        if self._tool == "pen":
            self._current_points = [QPointF(pos)]
            self.update()
        elif self._tool == "eraser":
            self._try_erase_at(pos.x(), pos.y())
        elif self._tool == "path":
            self._path_points.append(self._snap_canvas_point(pos))
            self.repaint_requested.emit()
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._tool == "path":
            self.commit_path(closed=True, make_selection=True)
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
        if self._selection_drag_start is not None and self._tool in {"rect_select", "ellipse_select", "crop"}:
            self._selection_drag_current = self._snap_canvas_point(event.position())
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
        if self._selection_drag_start is not None and self._tool in {"rect_select", "ellipse_select", "crop"}:
            self._selection_drag_current = self._snap_canvas_point(event.position())
            rect = self._selection_drag_rect()
            tool = self._selection_drag_tool or self._tool
            self._selection_drag_start = None
            self._selection_drag_current = None
            self._selection_drag_tool = ""
            if rect.width() > 1.0 and rect.height() > 1.0:
                shape = "ellipse" if tool == "ellipse_select" else "rect"
                self.set_selection_snapshot(self._points_from_drag_rect(rect, shape=shape))
            self.repaint_requested.emit()
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
            layer_id=self._active_layer_id,
            source_tool="pen",
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        self._current_points = []
        self.stroke_added.emit(stroke)
        self.update()

    def commit_path(
        self,
        *,
        closed: bool = False,
        make_selection: bool | None = None,
    ) -> None:
        if len(self._path_points) < 2:
            return
        w = max(1, self.width())
        h = max(1, self.height())
        norm_points = [(p.x() / w, p.y() / h) for p in self._path_points]
        if make_selection is None:
            make_selection = bool(closed)
        stroke = Stroke(
            points=norm_points,
            color=(
                self._pen_color.red(),
                self._pen_color.green(),
                self._pen_color.blue(),
            ),
            opacity=self._pen_opacity,
            width_px=self._pen_width,
            brush_style=self._pen_style,
            closed_path=bool(closed),
            layer_id=self._active_layer_id,
            source_tool="path",
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        if make_selection and len(norm_points) >= 3:
            self._selection_points = list(norm_points)
            self._selection_inverted = False
            self._sync_selection_timer()
        self._path_points = []
        self.stroke_added.emit(stroke)
        self.repaint_requested.emit()
        self.update()

    def clear_path_preview(self) -> None:
        self._path_points = []
        self.repaint_requested.emit()
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

    def clear_strokes_direct(self, layer_id: str | None = None) -> None:
        if hasattr(self, "_embedded_strokes"):
            if layer_id:
                target = str(layer_id)
                self._embedded_strokes = [
                    stroke for stroke in self._embedded_strokes
                    if self._stroke_layer_id(stroke) != target
                ]
                self._get_strokes = lambda: self._embedded_strokes
            else:
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
            layer_id = self._stroke_layer_id(stroke)
            if layer_id != self._active_layer_id:
                continue
            if not self._layer_visibility.get(layer_id, True):
                continue
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

BRUSH_LIBRARY_PRESETS: list[dict[str, object]] = [
    {
        "category": "Flow Map",
        "name": "Chalk",
        "style": "round",
        "width": 5,
        "opacity": 86,
    },
    {
        "category": "Flow Map",
        "name": "Real Wet Oil",
        "style": "marker",
        "width": 18,
        "opacity": 82,
    },
    {
        "category": "Flow Map",
        "name": "Screen Paper",
        "style": "highlighter",
        "width": 28,
        "opacity": 38,
    },
    {
        "category": "Pencil & Ink",
        "name": "Dry Graphite",
        "style": "round",
        "width": 3,
        "opacity": 72,
    },
    {
        "category": "Pencil & Ink",
        "name": "Digital Ink",
        "style": "round",
        "width": 7,
        "opacity": 100,
    },
    {
        "category": "Pencil & Ink",
        "name": "Dashed Layout",
        "style": "dashed",
        "width": 4,
        "opacity": 90,
    },
    {
        "category": "Markers",
        "name": "Soft Marker",
        "style": "marker",
        "width": 12,
        "opacity": 76,
    },
    {
        "category": "Markers",
        "name": "Wide Highlighter",
        "style": "highlighter",
        "width": 30,
        "opacity": 36,
    },
]


class PainterColorWheel(QWidget):
    colorChanged = Signal(QColor)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(112, 112)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._hue = 0
        self._sat = 255
        self._val = 255

    def set_color(self, color: QColor) -> None:
        hue = color.hue()
        self._hue = 0 if hue < 0 else int(hue)
        self._sat = max(0, min(255, int(color.saturation())))
        self._val = max(0, min(255, int(color.value())))
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        center = QPointF(self.width() / 2, self.height() / 2)
        outer = min(self.width(), self.height()) / 2 - 6
        ring_width = 12
        ring_radius = outer - ring_width / 2
        ring_rect = QRectF(
            center.x() - ring_radius,
            center.y() - ring_radius,
            ring_radius * 2,
            ring_radius * 2,
        )
        for degree in range(360):
            painter.setPen(QPen(QColor.fromHsv(degree, 255, 235), ring_width))
            painter.drawArc(ring_rect, int((90 - degree) * 16), -16)

        hue_point, white_point, black_point = self._triangle_points()
        image = QImage(self.width(), self.height(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        hue_color = QColor.fromHsv(self._hue, 255, 255)
        min_x = max(0, int(min(hue_point.x(), white_point.x(), black_point.x())) - 1)
        max_x = min(
            self.width(),
            int(max(hue_point.x(), white_point.x(), black_point.x())) + 2,
        )
        min_y = max(0, int(min(hue_point.y(), white_point.y(), black_point.y())) - 1)
        max_y = min(self.height(), int(max(hue_point.y(), white_point.y(), black_point.y())) + 2)
        for y in range(min_y, max_y):
            for x in range(min_x, max_x):
                weights = self._triangle_weights(QPointF(x + 0.5, y + 0.5))
                if weights is None:
                    continue
                hue_w, white_w, black_w = weights
                if hue_w < -0.001 or white_w < -0.001 or black_w < -0.001:
                    continue
                r = int(hue_color.red() * hue_w + 255 * white_w)
                g = int(hue_color.green() * hue_w + 255 * white_w)
                b = int(hue_color.blue() * hue_w + 255 * white_w)
                shade = 1.0 - black_w
                image.setPixelColor(
                    x,
                    y,
                    QColor(int(r * shade), int(g * shade), int(b * shade)),
                )
        painter.drawImage(0, 0, image)

        triangle = QPolygonF([hue_point, white_point, black_point])
        painter.setPen(QPen(QColor("#d9e5ff"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(triangle)

        angle = math.radians(self._hue)
        selector_radius = ring_radius
        hue_selector = QPointF(
            center.x() + math.cos(angle) * selector_radius,
            center.y() - math.sin(angle) * selector_radius,
        )
        painter.setPen(QPen(QColor("#111827"), 2))
        painter.setBrush(QColor("#eef2f7"))
        painter.drawEllipse(hue_selector, 5, 5)

        color_selector = self._selector_point()
        painter.setPen(QPen(QColor("#111827"), 2))
        painter.setBrush(QColor("#f8fafc"))
        painter.drawEllipse(color_selector, 4, 4)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def _pick(self, pos: QPointF) -> None:
        center = QPointF(self.width() / 2, self.height() / 2)
        outer = min(self.width(), self.height()) / 2 - 6
        ring_width = 12
        distance = math.hypot(pos.x() - center.x(), pos.y() - center.y())
        if outer - ring_width <= distance <= outer + 2:
            angle = math.degrees(math.atan2(center.y() - pos.y(), pos.x() - center.x()))
            self._hue = int((angle + 360) % 360)
            self.update()
            self.colorChanged.emit(QColor.fromHsv(self._hue, self._sat, self._val))
            return
        weights = self._triangle_weights(pos)
        if weights is None:
            return
        hue_w, white_w, black_w = weights
        if hue_w < -0.02 or white_w < -0.02 or black_w < -0.02:
            return
        value = max(0.0, min(1.0, hue_w + white_w))
        saturation = 0.0 if value <= 0.001 else max(0.0, min(1.0, hue_w / value))
        self._sat = int(saturation * 255)
        self._val = int(value * 255)
        self.update()
        self.colorChanged.emit(QColor.fromHsv(self._hue, self._sat, self._val))

    def _triangle_points(self) -> tuple[QPointF, QPointF, QPointF]:
        center = QPointF(self.width() / 2, self.height() / 2)
        radius = min(self.width(), self.height()) / 2 - 28
        return (
            QPointF(center.x() + radius * 0.78, center.y()),
            QPointF(center.x() - radius * 0.52, center.y() - radius * 0.64),
            QPointF(center.x() - radius * 0.52, center.y() + radius * 0.64),
        )

    def _triangle_weights(self, pos: QPointF) -> tuple[float, float, float] | None:
        hue_point, white_point, black_point = self._triangle_points()
        denom = (
            (white_point.y() - black_point.y()) * (hue_point.x() - black_point.x())
            + (black_point.x() - white_point.x()) * (hue_point.y() - black_point.y())
        )
        if abs(denom) < 0.0001:
            return None
        hue_w = (
            (white_point.y() - black_point.y()) * (pos.x() - black_point.x())
            + (black_point.x() - white_point.x()) * (pos.y() - black_point.y())
        ) / denom
        white_w = (
            (black_point.y() - hue_point.y()) * (pos.x() - black_point.x())
            + (hue_point.x() - black_point.x()) * (pos.y() - black_point.y())
        ) / denom
        black_w = 1.0 - hue_w - white_w
        return hue_w, white_w, black_w

    def _selector_point(self) -> QPointF:
        hue_point, white_point, black_point = self._triangle_points()
        saturation = self._sat / 255.0
        value = self._val / 255.0
        hue_w = value * saturation
        white_w = value * (1.0 - saturation)
        black_w = 1.0 - value
        return QPointF(
            hue_point.x() * hue_w + white_point.x() * white_w + black_point.x() * black_w,
            hue_point.y() * hue_w
            + white_point.y() * white_w
            + black_point.y() * black_w,
        )


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
        standalone: bool = False,
    ) -> None:
        super().__init__(parent)
        self._standalone = bool(standalone)
        self.setWindowTitle("Painter - TigerCapture" if self._standalone else tr("paint.title"))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self.setMinimumSize(760, 560)
        self.setSizeGripEnabled(True)
        self.setModal(not self._standalone)
        self._time_ms = int(time_ms)
        self._editor_object_provider = editor_object_provider
        self._bubbles: list[SpeechBubble] = list(initial_bubbles or [])
        self._bubble_items: list[SpeechBubbleItem] = []
        self._stickers: list["Sticker"] = list(initial_stickers or [])
        self._sticker_items: list["StickerItem"] = []
        self._undo_stack: list[tuple] = []
        self._redo_stack: list[tuple] = []
        self._undo_labels: list[str] = []
        self._redo_labels: list[str] = []
        self._restoring_state = False
        self._canvas_zoom = 1.0
        self._canvas_pan = QPoint(0, 0)
        self._canvas_pan_drag_start: QPoint | None = None
        self._canvas_pan_drag_origin = QPoint(0, 0)
        self._selected_path_item_id = "work-path"
        self._channel_visibility: dict[str, bool] = {
            "RGB": True,
            "Red": True,
            "Green": True,
            "Blue": True,
            "Alpha": True,
        }
        self._selected_channel = "RGB"
        self._selection_aspect_mode = "free"
        self._quick_mask_enabled = False
        self._grid_visible = False
        self._snap_to_grid = False
        self._grid_size_px = 64
        self._magic_select_tolerance = 32
        self._mirror_x_enabled = False
        self._mirror_y_enabled = False
        self._pbr_texture_settings: dict[str, float | str | bool] = {}
        self._pbr_preview_payload: dict | None = None
        self._pbr_source_path: str = ""
        self._selected_layer_id: str | None = None
        self._paint_clipboard: dict | None = None
        self._paint_layer_serial = 1
        self._paint_layers: list[PaintLayer] = [
            PaintLayer("paint-layer-1", "Layer 1")
        ]
        self._active_paint_layer_id = "paint-layer-1"
        self._background_layer_present = True
        self._canvas_document_size = (
            max(1, int(background_pixmap.width())) if background_pixmap and not background_pixmap.isNull() else 1920,
            max(1, int(background_pixmap.height())) if background_pixmap and not background_pixmap.isNull() else 1080,
        )

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

        self._prepare_paint_layers(initial_strokes)
        self._build_ui(background_pixmap, initial_strokes)

    # ---------- ui ----------

    def _configure_paint_icon_button(
        self,
        button: QPushButton,
        icon_name: str,
        *,
        icon_px: int = 14,
    ) -> None:
        button.setText(_clean_paint_button_text(button.text()))
        button.setIcon(app_icon(icon_name, size=icon_px, color="#EEF3FB"))
        button.setIconSize(icon_size(icon_px))

    def _configure_paint_tool_icon_button(
        self,
        button: QPushButton,
        icon_name: str,
        label: str,
        *,
        icon_px: int = 18,
    ) -> None:
        button.setText("")
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setIcon(app_icon(icon_name, size=icon_px, color="#E8EEF8"))
        button.setIconSize(icon_size(icon_px))
        button.setFixedSize(36, 36)

    def _make_layer_tiny_button(
        self,
        icon_name: str,
        label: str,
        *,
        checkable: bool = False,
    ) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("PaintLayerTinyButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setCheckable(checkable)
        button.setIcon(app_icon(icon_name, size=13, color="#DCE6F7"))
        button.setIconSize(icon_size(13))
        button.setFixedSize(22, 22)
        return button

    def _build_painter_menu_bar(self) -> QMenuBar:
        menu_bar = QMenuBar(self)
        menu_bar.setObjectName("PaintMenuBar")

        file_menu = menu_bar.addMenu("File")
        self._add_painter_menu_action(file_menu, "New Canvas...", self._open_new_canvas_dialog, "Ctrl+N")
        self._add_painter_menu_action(file_menu, "Export PNG...", lambda: self._export_png_to_file(include_background=True), "Ctrl+Shift+E")
        self._add_painter_menu_action(file_menu, "Export Transparent PNG...", lambda: self._export_png_to_file(include_background=False))
        file_menu.addSeparator()
        self._add_painter_menu_action(file_menu, "Close", self.reject, "Esc")

        edit_menu = menu_bar.addMenu("Edit")
        self._add_painter_menu_action(edit_menu, "Undo", self._undo, "Ctrl+Z")
        self._add_painter_menu_action(edit_menu, "Redo", self._redo, "Ctrl+Y")
        edit_menu.addSeparator()
        self._add_painter_menu_action(edit_menu, "Copy", self._copy_selected_layer, "Ctrl+C")
        self._add_painter_menu_action(edit_menu, "Cut", self._cut_selected_layer, "Ctrl+X")
        self._add_painter_menu_action(edit_menu, "Paste", self._paste_layer_clipboard, "Ctrl+V")
        self._add_painter_menu_action(edit_menu, "Delete", self._delete_selected_layer, "Del")
        edit_menu.addSeparator()
        self._add_painter_menu_action(edit_menu, "Fill", lambda: self._fill_document("solid"))
        self._add_painter_menu_action(edit_menu, "Gradient Fill", lambda: self._fill_document("gradient"))
        self._add_painter_menu_action(edit_menu, "Pattern Fill", lambda: self._fill_document("pattern"))
        edit_menu.addSeparator()
        self._add_painter_menu_action(edit_menu, "Clear All", self._clear_all)

        view_menu = menu_bar.addMenu("View")
        self._add_painter_menu_action(view_menu, "Zoom In", self._zoom_in, "Ctrl++")
        self._add_painter_menu_action(view_menu, "Zoom Out", self._zoom_out, "Ctrl+-")
        self._add_painter_menu_action(view_menu, "Fit", self._zoom_fit, "Ctrl+0")
        self._add_painter_menu_action(view_menu, "100%", lambda: self._set_zoom_percent(100), "Ctrl+1")
        view_menu.addSeparator()
        self._add_painter_menu_action(view_menu, "Pan Tool", lambda: self._set_tool("pan"), "H")
        self._add_painter_menu_action(view_menu, "Reset Pan", self._reset_canvas_pan)
        view_menu.addSeparator()
        self._add_painter_menu_action(view_menu, "Show Grid", lambda: self._set_grid_options(visible=not self._grid_visible))
        self._add_painter_menu_action(view_menu, "Snap To Grid", lambda: self._set_grid_options(snap=not self._snap_to_grid))
        view_menu.addSeparator()
        self._add_painter_menu_action(view_menu, "Mirror Drawing Horizontal", lambda: self._set_mirror_enabled(x=not self._mirror_x_enabled))
        self._add_painter_menu_action(view_menu, "Mirror Drawing Vertical", lambda: self._set_mirror_enabled(y=not self._mirror_y_enabled))

        image_menu = menu_bar.addMenu("Image")
        self._add_painter_menu_action(image_menu, "Image Size...", self._prompt_image_size)
        self._add_painter_menu_action(image_menu, "Canvas Size...", self._prompt_canvas_size)
        self._add_painter_menu_action(image_menu, "Crop To Selection", self._crop_to_selection)
        image_menu.addSeparator()
        self._add_painter_menu_action(image_menu, "Flip Canvas Horizontal", lambda: self._flip_canvas(horizontal=True))
        self._add_painter_menu_action(image_menu, "Flip Canvas Vertical", lambda: self._flip_canvas(horizontal=False))
        image_menu.addSeparator()
        self._add_painter_menu_action(image_menu, "Channels Panel", lambda: self._show_painter_tab("channels"))
        self._add_painter_menu_action(image_menu, "Show RGB", lambda: self._set_channel_visibility("RGB", True))
        self._add_painter_menu_action(image_menu, "Hide Alpha", lambda: self._set_channel_visibility("Alpha", False))

        layer_menu = menu_bar.addMenu("Layer")
        self._add_painter_menu_action(layer_menu, "New Layer", self._new_paint_layer, "Ctrl+Shift+N")
        self._add_painter_menu_action(layer_menu, "Duplicate Layer", self._duplicate_selected_layer, "Ctrl+J")
        self._add_painter_menu_action(layer_menu, "Rename Layer...", self._rename_selected_layer)
        self._add_painter_menu_action(layer_menu, "Delete Layer", self._delete_selected_layer)
        layer_menu.addSeparator()
        self._add_painter_menu_action(layer_menu, "Toggle Visibility", self._toggle_selected_layer_visibility)
        self._add_painter_menu_action(layer_menu, "Toggle Lock", self._toggle_selected_layer_lock)
        layer_menu.addSeparator()
        self._add_painter_menu_action(layer_menu, "Add White Mask", lambda: self._create_layer_mask("white"))
        self._add_painter_menu_action(layer_menu, "Add Mask From Selection", self._mask_selected_layer_from_selection)
        self._add_painter_menu_action(layer_menu, "Add Mask From Path", self._mask_selected_layer_from_path)
        self._add_painter_menu_action(layer_menu, "Add Mask From Channel", lambda: self._create_layer_mask("channel"))
        self._add_painter_menu_action(layer_menu, "Add Mask From Alpha", lambda: self._create_layer_mask("layer_alpha"))

        select_menu = menu_bar.addMenu("Select")
        self._add_painter_menu_action(select_menu, "All", self._select_all, "Ctrl+A")
        self._add_painter_menu_action(select_menu, "Deselect", self._deselect, "Ctrl+D")
        self._add_painter_menu_action(select_menu, "Inverse", self._invert_selection, "Ctrl+Shift+I")
        select_menu.addSeparator()
        self._add_painter_menu_action(select_menu, "Quick Mask", lambda: self._set_quick_mask_enabled(not self._quick_mask_enabled), "Q")
        self._add_painter_menu_action(select_menu, "Magic Select", lambda: self._set_tool("magic_select"))
        self._add_painter_menu_action(select_menu, "Select Similar From Center", lambda: self._select_by_color_at(0.5, 0.5))
        select_menu.addSeparator()
        self._add_painter_menu_action(select_menu, "Rectangular Marquee", lambda: self._set_tool("rect_select"), "M")
        self._add_painter_menu_action(select_menu, "Elliptical Marquee", lambda: self._set_tool("ellipse_select"))
        self._add_painter_menu_action(select_menu, "Free Ratio", lambda: self._set_selection_aspect_mode("free"))
        self._add_painter_menu_action(select_menu, "Square Ratio", lambda: self._set_selection_aspect_mode("square"))
        self._add_painter_menu_action(select_menu, "16:9 Ratio", lambda: self._set_selection_aspect_mode("16:9"))
        self._add_painter_menu_action(select_menu, "4:3 Ratio", lambda: self._set_selection_aspect_mode("4:3"))
        select_menu.addSeparator()
        self._add_painter_menu_action(select_menu, "Selection To Path", self._selection_to_path)
        self._add_painter_menu_action(select_menu, "Path To Selection", self._make_selection_from_selected_path)

        path_menu = menu_bar.addMenu("Path")
        self._add_painter_menu_action(path_menu, "Commit Work Path", lambda: self._commit_path(False))
        self._add_painter_menu_action(path_menu, "Close Work Path", lambda: self._commit_path(True))
        self._add_painter_menu_action(path_menu, "Clear Work Path", self._clear_path_preview)
        path_menu.addSeparator()
        self._add_painter_menu_action(path_menu, "Make Selection", self._make_selection_from_selected_path)
        self._add_painter_menu_action(path_menu, "Save Selection As Path", self._selection_to_path)

        window_menu = menu_bar.addMenu("Window")
        self._add_painter_menu_action(window_menu, "Layers", lambda: self._show_painter_tab("layers"))
        self._add_painter_menu_action(window_menu, "Channels", lambda: self._show_painter_tab("channels"))
        self._add_painter_menu_action(window_menu, "Paths", lambda: self._show_painter_tab("paths"))
        self._add_painter_menu_action(window_menu, "History", lambda: self._show_painter_tab("history"))
        return menu_bar

    def _add_painter_menu_action(
        self,
        menu: QMenu,
        label: str,
        handler: Callable[[], None],
        shortcut: str | None = None,
    ):
        action = menu.addAction(label)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(handler)
        return action

    def _prepare_paint_layers(self, strokes: list[Stroke]) -> None:
        seen = {layer.layer_id for layer in self._paint_layers}
        for stroke in strokes:
            layer_id = str(getattr(stroke, "layer_id", "") or "paint-layer-1")
            setattr(stroke, "layer_id", layer_id)
            if layer_id in seen:
                continue
            self._paint_layer_serial += 1
            self._paint_layers.append(
                PaintLayer(layer_id, f"Layer {self._paint_layer_serial}")
            )
            seen.add(layer_id)
        self._selected_layer_id = self._active_paint_layer_id if self._standalone else None

    def _paint_layer_by_id(self, layer_id: str | None) -> PaintLayer | None:
        target = str(layer_id or "")
        for layer in self._paint_layers:
            if layer.layer_id == target:
                return layer
        return None

    def _is_paint_layer_id(self, layer_id: str | None) -> bool:
        return self._paint_layer_by_id(layer_id) is not None

    def _active_paint_layer(self) -> PaintLayer:
        layer = self._paint_layer_by_id(self._active_paint_layer_id)
        if layer is None:
            layer = self._paint_layers[0]
            self._active_paint_layer_id = layer.layer_id
        return layer

    def _display_background_pixmap(self) -> QPixmap:
        width, height = self._canvas_document_size
        checker = create_checkerboard_paint_pixmap(width, height)
        if not (
            self._background_layer_present
            and self._bg_pixmap_source
            and not self._bg_pixmap_source.isNull()
        ):
            return checker
        try:
            has_alpha = self._bg_pixmap_source.hasAlphaChannel()
        except Exception:
            has_alpha = self._bg_pixmap_source.toImage().hasAlphaChannel()
        if not has_alpha:
            return self._apply_channel_visibility_to_pixmap(self._bg_pixmap_source)
        painter = QPainter(checker)
        try:
            painter.drawPixmap(0, 0, self._bg_pixmap_source)
        finally:
            painter.end()
        return self._apply_channel_visibility_to_pixmap(checker)

    def _apply_channel_visibility_to_pixmap(self, pixmap: QPixmap) -> QPixmap:
        if pixmap.isNull():
            return pixmap
        visibility = getattr(self, "_channel_visibility", None) or {}
        red_visible = bool(visibility.get("Red", True))
        green_visible = bool(visibility.get("Green", True))
        blue_visible = bool(visibility.get("Blue", True))
        alpha_visible = bool(visibility.get("Alpha", True))
        if red_visible and green_visible and blue_visible and alpha_visible:
            return pixmap
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for y in range(image.height()):
            for x in range(image.width()):
                color = image.pixelColor(x, y)
                if not red_visible:
                    color.setRed(0)
                if not green_visible:
                    color.setGreen(0)
                if not blue_visible:
                    color.setBlue(0)
                if not alpha_visible:
                    color.setAlpha(255)
                image.setPixelColor(x, y, color)
        return QPixmap.fromImage(image)

    def _export_background_pixmap(self) -> QPixmap | None:
        if self._background_layer_present and self._bg_pixmap_source and not self._bg_pixmap_source.isNull():
            return self._bg_pixmap_source
        return None

    def _sync_canvas_layer_view(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self.canvas.set_active_layer_id(self._active_paint_layer_id)
        self.canvas.set_layer_view(
            {layer.layer_id: layer.visible for layer in self._paint_layers},
            {layer.layer_id: layer.opacity for layer in self._paint_layers},
            {
                layer.layer_id: list(getattr(layer, "mask", []) or [])
                for layer in self._paint_layers
                if bool(getattr(layer, "mask_enabled", False)) and len(getattr(layer, "mask", []) or []) >= 3
            },
        )

    def _open_new_canvas_dialog(self) -> None:
        setup = NewCanvasDialog(
            self,
            default_size=self._canvas_document_size,
            default_background="transparent" if not self._background_layer_present else "#FFFFFF",
        )
        if setup.exec() != QDialog.DialogCode.Accepted:
            return
        request = setup.canvas_request()
        self._replace_canvas_document(
            int(request.get("width") or 1920),
            int(request.get("height") or 1080),
            str(request.get("background") or "#FFFFFF"),
        )

    def _replace_canvas_document(self, width: int, height: int, background: str = "#FFFFFF") -> None:
        self._push_undo_state("New canvas")
        width = max(64, min(16384, int(width or 1920)))
        height = max(64, min(16384, int(height or 1080)))
        background_text = str(background or "#FFFFFF")
        self._canvas_document_size = (width, height)
        self._bg_pixmap_source = create_blank_paint_pixmap(width, height, background_text)
        self._background_layer_present = background_text.strip().lower() not in {
            "transparent",
            "alpha",
            "none",
        }
        for item in list(getattr(self, "_bubble_items", [])):
            item.deleteLater()
        for item in list(getattr(self, "_sticker_items", [])):
            item.deleteLater()
        self._bubble_items = []
        self._sticker_items = []
        self._bubbles = []
        self._stickers = []
        self._paint_layer_serial = 1
        self._paint_layers = [PaintLayer("paint-layer-1", "Layer 1")]
        self._active_paint_layer_id = "paint-layer-1"
        self._selected_layer_id = "paint-layer-1" if self._standalone else None
        if hasattr(self, "canvas"):
            self.canvas.set_strokes_snapshot([])
            self.canvas.clear_selection()
            self.canvas.clear_path_preview()
        self._canvas_pan = QPoint(0, 0)
        self._sync_canvas_layer_view()
        self._update_canvas_geometry()
        self._update_inspector_counts()

    def _show_painter_tab(self, tab: str) -> None:
        tabs = getattr(self, "_layer_channel_path_tabs", None)
        if tabs is None:
            return
        target = str(tab or "").strip().casefold()
        names = {
            "layers": 0,
            "layer": 0,
            "channels": 1,
            "channel": 1,
            "paths": 2,
            "path": 2,
            "history": 3,
            "pbr": 4,
            "pbr_maps": 4,
            "texture": 4,
            "materials": 4,
        }
        index = names.get(target, 0)
        if 0 <= index < tabs.count():
            tabs.setCurrentIndex(index)

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
        self.clear_btn.setObjectName("PaintDanger")
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

        self._configure_paint_icon_button(self.pen_btn, "paint-brush")
        self._configure_paint_icon_button(self.eraser_btn, "eraser")
        self._configure_paint_icon_button(self.clear_btn, "trash")
        self._configure_paint_icon_button(self.bubble_btn, "caption")
        self._configure_paint_icon_button(self.sticker_btn, "image")

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
        self.custom_color_btn.setObjectName("PaintCustomColor")
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._configure_paint_icon_button(self.custom_color_btn, "color", icon_px=13)
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
        display_bg = self._display_background_pixmap()
        self._bg_label.setPixmap(
            display_bg.scaled(
                1, 1, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ) if display_bg and not display_bg.isNull() else QPixmap()
        )

        self.canvas = DrawingCanvas(
            get_time_ms=lambda: self._time_ms,
            get_strokes=lambda: [],
            parent=canvas_host,
        )
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self._sync_canvas_layer_view()
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

        self._painter_menu_bar = self._build_painter_menu_bar()
        root.addWidget(self._painter_menu_bar)

        top_bar = QFrame()
        top_bar.setObjectName("PaintTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(14, 10, 14, 10)
        top_layout.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(2)
        title = QLabel("TigerCapture Painter" if self._standalone else "TigerCapture Paint")
        title.setObjectName("PaintTitle")
        subtitle = QLabel(
            "Blank canvas drawing, selections, layers, and color adjustments."
            if self._standalone
            else "Draw, cut out, place PNG stickers, and import editor objects."
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
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setObjectName("PaintCustomColor")
        self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        top_layout.addWidget(self.zoom_out_btn)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(25, 400)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(140)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        top_layout.addWidget(self.zoom_slider)
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setObjectName("PaintCustomColor")
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        top_layout.addWidget(self.zoom_in_btn)
        self.zoom_fit_btn = QPushButton("Fit")
        self.zoom_fit_btn.setObjectName("PaintCustomColor")
        self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_fit_btn.setToolTip("Fit canvas (Ctrl+0)")
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)
        top_layout.addWidget(self.zoom_fit_btn)
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
        tool_rail.setFixedWidth(52)
        tool_rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._tool_rail = tool_rail
        tool_layout = QVBoxLayout(tool_rail)
        tool_layout.setContentsMargins(7, 8, 7, 8)
        tool_layout.setSpacing(4)

        self.select_btn = QPushButton("Select / Move")
        self.select_btn.setCheckable(True)
        self.select_btn.setObjectName("PaintTool")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(lambda: self._set_tool("select"))

        self.pan_btn = QPushButton("Pan")
        self.pan_btn.setCheckable(True)
        self.pan_btn.setObjectName("PaintTool")
        self.pan_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pan_btn.clicked.connect(lambda: self._set_tool("pan"))

        self.rect_select_btn = QPushButton("Rect Select")
        self.rect_select_btn.setCheckable(True)
        self.rect_select_btn.setObjectName("PaintTool")
        self.rect_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rect_select_btn.clicked.connect(lambda: self._set_tool("rect_select"))

        self.ellipse_select_btn = QPushButton("Ellipse Select")
        self.ellipse_select_btn.setCheckable(True)
        self.ellipse_select_btn.setObjectName("PaintTool")
        self.ellipse_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ellipse_select_btn.clicked.connect(lambda: self._set_tool("ellipse_select"))

        self.magic_select_btn = QPushButton("Magic Select")
        self.magic_select_btn.setCheckable(True)
        self.magic_select_btn.setObjectName("PaintTool")
        self.magic_select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.magic_select_btn.clicked.connect(lambda: self._set_tool("magic_select"))

        self.crop_btn = QPushButton("Crop")
        self.crop_btn.setCheckable(True)
        self.crop_btn.setObjectName("PaintTool")
        self.crop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.crop_btn.clicked.connect(lambda: self._set_tool("crop"))

        self.mirror_x_btn = QPushButton("Mirror X")
        self.mirror_x_btn.setCheckable(True)
        self.mirror_x_btn.setObjectName("PaintTool")
        self.mirror_x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mirror_x_btn.clicked.connect(lambda checked: self._set_mirror_enabled(x=bool(checked)))

        self.mirror_y_btn = QPushButton("Mirror Y")
        self.mirror_y_btn.setCheckable(True)
        self.mirror_y_btn.setObjectName("PaintTool")
        self.mirror_y_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mirror_y_btn.clicked.connect(lambda checked: self._set_mirror_enabled(y=bool(checked)))

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

        self.path_btn = QPushButton("Path")
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

        self.cutout_btn = QPushButton("Cutout")
        self.cutout_btn.setObjectName("PaintTool")
        self.cutout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cutout_btn.clicked.connect(self._create_cutout_sticker)

        self._configure_paint_tool_icon_button(self.select_btn, "cursor", "Select / Move")
        self._configure_paint_tool_icon_button(self.pan_btn, "hand", "Pan canvas")
        self._configure_paint_tool_icon_button(self.rect_select_btn, "marquee-rect", "Rectangular marquee")
        self._configure_paint_tool_icon_button(self.ellipse_select_btn, "marquee-ellipse", "Elliptical marquee")
        self._configure_paint_tool_icon_button(self.magic_select_btn, "target", "Magic Select / Select by Color")
        self._configure_paint_tool_icon_button(self.crop_btn, "crop", "Crop")
        self._configure_paint_tool_icon_button(self.mirror_x_btn, "mirror-x", "Mirror drawing horizontally")
        self._configure_paint_tool_icon_button(self.mirror_y_btn, "mirror-y", "Mirror drawing vertically")
        self._configure_paint_tool_icon_button(self.pen_btn, "paint-brush", tr("paint.btn.pen"))
        self._configure_paint_tool_icon_button(self.eraser_btn, "eraser", tr("paint.btn.eraser"))
        self._configure_paint_tool_icon_button(self.path_btn, "path-tool", "Path")
        self._configure_paint_tool_icon_button(self.bubble_btn, "caption", tr("bubble.add_button"))
        self._configure_paint_tool_icon_button(self.sticker_btn, "image", tr("sticker.add_button"))
        self._configure_paint_tool_icon_button(self.editor_object_btn, "layers", "Editor Object")
        self._configure_paint_tool_icon_button(self.cutout_btn, "scissors", "Cutout")
        self._configure_paint_tool_icon_button(self.clear_btn, "trash", tr("paint.btn.clear_all"))

        tool_layout.addWidget(self.select_btn)
        tool_layout.addWidget(self.pan_btn)
        tool_layout.addWidget(self.rect_select_btn)
        tool_layout.addWidget(self.ellipse_select_btn)
        tool_layout.addWidget(self.magic_select_btn)
        tool_layout.addWidget(self.crop_btn)
        tool_layout.addWidget(self.mirror_x_btn)
        tool_layout.addWidget(self.mirror_y_btn)
        tool_layout.addWidget(self.pen_btn)
        tool_layout.addWidget(self.eraser_btn)
        tool_layout.addWidget(self.path_btn)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: rgba(178, 186, 202, 38);")
        tool_layout.addWidget(line)
        tool_layout.addWidget(self.bubble_btn)
        tool_layout.addWidget(self.sticker_btn)
        tool_layout.addWidget(self.editor_object_btn)
        tool_layout.addWidget(self.cutout_btn)
        if self._standalone:
            self.bubble_btn.hide()
            self.sticker_btn.hide()
            self.editor_object_btn.hide()
            self.cutout_btn.hide()

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
        canvas_host.setMouseTracking(True)
        canvas_host.installEventFilter(self)
        self._canvas_host = canvas_host

        self._bg_label = QLabel(canvas_host)
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.setStyleSheet("background-color: #050607;")
        self._bg_label.installEventFilter(self)
        self._bg_pixmap_source = bg
        display_bg = self._display_background_pixmap()
        self._bg_label.setPixmap(
            display_bg.scaled(
                1, 1, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ) if display_bg and not display_bg.isNull() else QPixmap()
        )

        self.canvas = DrawingCanvas(
            get_time_ms=lambda: self._time_ms,
            get_strokes=lambda: [],
            parent=canvas_host,
        )
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self._sync_canvas_layer_view()
        self.canvas.set_tool("pen")
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_width(self._pen_width)
        self.canvas.set_pen_opacity(self._pen_opacity)
        self.canvas.stroke_added.connect(self._on_stroke_added)
        self.canvas.stroke_erased_at.connect(self._erase_stroke_direct)
        self.canvas.repaint_requested.connect(self._update_path_list)
        self.canvas.selection_probe_requested.connect(self._on_canvas_selection_probe)
        self.canvas.installEventFilter(self)

        canvas_layout.addWidget(canvas_host, stretch=1)
        workspace.addWidget(canvas_frame, stretch=1)

        inspector = QFrame()
        inspector.setObjectName("PaintInspector")
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(12, 12, 12, 12)
        inspector_layout.setSpacing(10)

        inspector_controls = QWidget()
        inspector_controls_layout = QVBoxLayout(inspector_controls)
        inspector_controls_layout.setContentsMargins(0, 0, 12, 0)
        inspector_controls_layout.setSpacing(10)
        self._paint_inspector_controls = inspector_controls

        inspector_controls_scroll = QScrollArea()
        inspector_controls_scroll.setObjectName("PaintInspectorScroll")
        inspector_controls_scroll.setWidgetResizable(True)
        inspector_controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if self._standalone:
            inspector_controls_scroll.setMinimumHeight(130)
            inspector_controls_scroll.setMaximumHeight(230)
        else:
            inspector_controls_scroll.setMinimumHeight(190)
            inspector_controls_scroll.setMaximumHeight(360)
        inspector_controls_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        inspector_controls_scroll.setWidget(inspector_controls)
        self._paint_inspector_controls_scroll = inspector_controls_scroll

        brush_title = QLabel("BRUSH")
        brush_title.setObjectName("PaintSectionTitle")

        tool_options_title = QLabel("TOOL OPTIONS")
        tool_options_title.setObjectName("PaintSectionTitle")
        inspector_controls_layout.addWidget(tool_options_title)

        selection_row = QHBoxLayout()
        selection_row.setContentsMargins(0, 0, 0, 0)
        selection_label = QLabel("Marquee")
        selection_label.setObjectName("PaintMeta")
        self.selection_aspect_combo = QComboBox()
        self.selection_aspect_combo.addItem("Free", "free")
        self.selection_aspect_combo.addItem("Square", "square")
        self.selection_aspect_combo.addItem("16:9", "16:9")
        self.selection_aspect_combo.addItem("4:3", "4:3")
        self.selection_aspect_combo.currentIndexChanged.connect(self._on_selection_aspect_changed)
        selection_row.addWidget(selection_label)
        selection_row.addStretch(1)
        selection_row.addWidget(self.selection_aspect_combo)
        inspector_controls_layout.addLayout(selection_row)

        tool_action_row = QHBoxLayout()
        tool_action_row.setContentsMargins(0, 0, 0, 0)
        self.crop_apply_btn = QPushButton("Apply Crop")
        self.crop_apply_btn.setObjectName("PaintCustomColor")
        self.crop_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.crop_apply_btn.setToolTip("Apply the active crop/selection bounds")
        self.crop_apply_btn.clicked.connect(self._crop_to_selection)
        self.mask_selection_btn = QPushButton("Mask")
        self.mask_selection_btn.setObjectName("PaintCustomColor")
        self.mask_selection_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mask_selection_btn.setToolTip("Create a layer mask from the active selection")
        self.mask_selection_btn.clicked.connect(self._mask_selected_layer_from_selection)
        self.deselect_option_btn = QPushButton("Deselect")
        self.deselect_option_btn.setObjectName("PaintCustomColor")
        self.deselect_option_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.deselect_option_btn.clicked.connect(self._deselect)
        tool_action_row.addWidget(self.crop_apply_btn)
        tool_action_row.addWidget(self.mask_selection_btn)
        tool_action_row.addWidget(self.deselect_option_btn)
        inspector_controls_layout.addLayout(tool_action_row)

        view_action_row = QHBoxLayout()
        view_action_row.setContentsMargins(0, 0, 0, 0)
        self.quick_mask_btn = QPushButton("Quick Mask")
        self.quick_mask_btn.setCheckable(True)
        self.quick_mask_btn.setObjectName("PaintCustomColor")
        self.quick_mask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_mask_btn.setToolTip("Toggle Photoshop-style Quick Mask overlay (Q)")
        self.quick_mask_btn.clicked.connect(lambda checked: self._set_quick_mask_enabled(bool(checked)))
        self.grid_view_btn = QPushButton("Grid")
        self.grid_view_btn.setCheckable(True)
        self.grid_view_btn.setObjectName("PaintCustomColor")
        self.grid_view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.grid_view_btn.setToolTip("Show canvas grid")
        self.grid_view_btn.clicked.connect(lambda checked: self._set_grid_options(visible=bool(checked)))
        self.snap_grid_btn = QPushButton("Snap")
        self.snap_grid_btn.setCheckable(True)
        self.snap_grid_btn.setObjectName("PaintCustomColor")
        self.snap_grid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snap_grid_btn.setToolTip("Snap marquee and path points to the grid")
        self.snap_grid_btn.clicked.connect(lambda checked: self._set_grid_options(snap=bool(checked)))
        view_action_row.addWidget(self.quick_mask_btn)
        view_action_row.addWidget(self.grid_view_btn)
        view_action_row.addWidget(self.snap_grid_btn)
        inspector_controls_layout.addLayout(view_action_row)

        magic_row = QHBoxLayout()
        magic_row.setContentsMargins(0, 0, 0, 0)
        magic_label = QLabel("Magic Tol")
        magic_label.setObjectName("PaintMeta")
        self._magic_tolerance_value_label = QLabel(f"{self._magic_select_tolerance}")
        self._magic_tolerance_value_label.setObjectName("PaintValue")
        magic_row.addWidget(magic_label)
        magic_row.addStretch(1)
        magic_row.addWidget(self._magic_tolerance_value_label)
        inspector_controls_layout.addLayout(magic_row)
        self.magic_tolerance_slider = QSlider(Qt.Orientation.Horizontal)
        self.magic_tolerance_slider.setRange(0, 100)
        self.magic_tolerance_slider.setValue(self._magic_select_tolerance)
        self.magic_tolerance_slider.valueChanged.connect(self._on_magic_tolerance_changed)
        inspector_controls_layout.addWidget(self.magic_tolerance_slider)

        fill_action_row = QHBoxLayout()
        fill_action_row.setContentsMargins(0, 0, 0, 0)
        self.fill_solid_btn = QPushButton("Fill")
        self.fill_solid_btn.setObjectName("PaintCustomColor")
        self.fill_solid_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fill_solid_btn.setToolTip("Fill selection or canvas with current color")
        self.fill_solid_btn.clicked.connect(lambda: self._fill_document("solid"))
        self.fill_gradient_btn = QPushButton("Gradient")
        self.fill_gradient_btn.setObjectName("PaintCustomColor")
        self.fill_gradient_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fill_gradient_btn.setToolTip("Fill selection or canvas with a soft current-color gradient")
        self.fill_gradient_btn.clicked.connect(lambda: self._fill_document("gradient"))
        self.fill_pattern_btn = QPushButton("Pattern")
        self.fill_pattern_btn.setObjectName("PaintCustomColor")
        self.fill_pattern_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fill_pattern_btn.setToolTip("Fill selection or canvas with a compact diagonal pattern")
        self.fill_pattern_btn.clicked.connect(lambda: self._fill_document("pattern"))
        fill_action_row.addWidget(self.fill_solid_btn)
        fill_action_row.addWidget(self.fill_gradient_btn)
        fill_action_row.addWidget(self.fill_pattern_btn)
        inspector_controls_layout.addLayout(fill_action_row)

        inspector_controls_layout.addWidget(brush_title)

        self.brush_category_combo = QComboBox()
        self.brush_category_combo.addItem("All Brushes", "")
        for category in dict.fromkeys(
            str(row["category"]) for row in BRUSH_LIBRARY_PRESETS
        ):
            self.brush_category_combo.addItem(category, category)
        self.brush_category_combo.currentIndexChanged.connect(
            self._populate_brush_library
        )
        inspector_controls_layout.addWidget(self.brush_category_combo)
        self.brush_library_list = QListWidget()
        self.brush_library_list.setObjectName("PaintBrushList")
        self.brush_library_list.setFixedHeight(118)
        self.brush_library_list.setViewMode(QListView.ViewMode.IconMode)
        self.brush_library_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.brush_library_list.setMovement(QListView.Movement.Static)
        self.brush_library_list.setWrapping(True)
        self.brush_library_list.setSpacing(6)
        self.brush_library_list.setIconSize(QSize(76, 36))
        self.brush_library_list.setGridSize(QSize(86, 54))
        self.brush_library_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.brush_library_list.itemClicked.connect(self._on_brush_library_item)
        inspector_controls_layout.addWidget(self.brush_library_list)
        self._populate_brush_library()

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
        inspector_controls_layout.addLayout(style_row)

        width_row = QHBoxLayout()
        width_row.setContentsMargins(0, 0, 0, 0)
        width_label = QLabel(tr("paint.label.width"))
        width_label.setObjectName("PaintMeta")
        self._width_value_label = QLabel(f"{int(self._pen_width)} px")
        self._width_value_label.setObjectName("PaintValue")
        width_row.addWidget(width_label)
        width_row.addStretch(1)
        width_row.addWidget(self._width_value_label)
        inspector_controls_layout.addLayout(width_row)
        self.width_slider = QSlider(Qt.Orientation.Horizontal)
        self.width_slider.setRange(1, 60)
        self.width_slider.setValue(int(self._pen_width))
        self.width_slider.valueChanged.connect(self._on_width_changed)
        inspector_controls_layout.addWidget(self.width_slider)

        opacity_row = QHBoxLayout()
        opacity_row.setContentsMargins(0, 0, 0, 0)
        opacity_label = QLabel(tr("paint.label.opacity"))
        opacity_label.setObjectName("PaintMeta")
        self._opacity_value_label = QLabel("100%")
        self._opacity_value_label.setObjectName("PaintValue")
        opacity_row.addWidget(opacity_label)
        opacity_row.addStretch(1)
        opacity_row.addWidget(self._opacity_value_label)
        inspector_controls_layout.addLayout(opacity_row)
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(10, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        inspector_controls_layout.addWidget(self.opacity_slider)

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
        inspector_controls_layout.addLayout(preset_row)

        color_title = QLabel("COLOR")
        color_title.setObjectName("PaintSectionTitle")
        inspector_controls_layout.addWidget(color_title)
        color_panel = QFrame()
        color_panel.setObjectName("PaintColorPanel")
        color_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._paint_color_panel = color_panel
        color_panel_layout = QVBoxLayout(color_panel)
        color_panel_layout.setContentsMargins(8, 8, 8, 8)
        color_panel_layout.setSpacing(6)

        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        color_label = QLabel("Current")
        color_label.setObjectName("PaintMeta")
        self._color_preview = QLabel()
        self._color_preview.setObjectName("PaintColorWell")
        self._color_preview.setFixedSize(48, 20)
        self._color_hex_label = QLabel("#E54646")
        self._color_hex_label.setObjectName("PaintColorHex")
        color_row.addWidget(color_label)
        color_row.addStretch(1)
        color_row.addWidget(self._color_hex_label)
        color_row.addWidget(self._color_preview)
        color_panel_layout.addLayout(color_row)

        wheel_row = QHBoxLayout()
        wheel_row.setContentsMargins(0, 0, 0, 0)
        wheel_row.addStretch(1)
        self.color_wheel = PainterColorWheel()
        self.color_wheel.colorChanged.connect(self._on_color_wheel_changed)
        wheel_row.addWidget(self.color_wheel)
        wheel_row.addStretch(1)
        color_panel_layout.addLayout(wheel_row)

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
        recent_row.setSpacing(5)
        self._recent_color_btns: list[QPushButton] = []
        for rgb in self._recent_colors:
            btn = self._make_palette_button(rgb, width=32, height=16)
            recent_row.addWidget(btn)
            self._recent_color_btns.append(btn)
        recent_row.addStretch(1)
        color_panel_layout.addLayout(recent_row)

        suggested_label = QLabel("PALETTE")
        suggested_label.setObjectName("PaintMeta")
        color_panel_layout.addWidget(suggested_label)
        palette_grid = QGridLayout()
        palette_grid.setAlignment(Qt.AlignmentFlag.AlignLeft)
        palette_grid.setHorizontalSpacing(5)
        palette_grid.setVerticalSpacing(5)
        self._palette_btns: list[QPushButton] = []
        for idx, rgb in enumerate(PALETTE_COLORS):
            btn = self._make_palette_button(rgb, width=38, height=16)
            palette_grid.addWidget(btn, idx // 4, idx % 4)
            self._palette_btns.append(btn)
        color_panel_layout.addLayout(palette_grid)

        self.custom_color_btn = QPushButton("Advanced picker")
        self.custom_color_btn.setObjectName("PaintCustomColor")
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        color_panel_layout.addWidget(self.custom_color_btn)
        inspector_controls_layout.addWidget(color_panel)
        inspector_controls_layout.addStretch(1)

        self._layer_channel_path_tabs = QTabWidget()
        self._layer_channel_path_tabs.setObjectName("PaintLayerChannelPathTabs")
        self._layer_channel_path_tabs.setDocumentMode(True)
        self._layer_channel_path_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._layer_channel_path_tabs.setMinimumHeight(320 if self._standalone else 280)

        layers_tab = QWidget()
        layers_layout = QVBoxLayout(layers_tab)
        layers_layout.setContentsMargins(8, 8, 8, 8)
        layers_layout.setSpacing(6)

        layer_controls = QFrame()
        layer_controls.setObjectName("PaintLayerControlPanel")
        layer_controls_layout = QVBoxLayout(layer_controls)
        layer_controls_layout.setContentsMargins(6, 6, 6, 6)
        layer_controls_layout.setSpacing(5)

        layer_filter_row = QHBoxLayout()
        layer_filter_row.setContentsMargins(0, 0, 0, 0)
        layer_filter_row.setSpacing(5)
        self.layer_filter_combo = QComboBox()
        self.layer_filter_combo.setObjectName("PaintLayerFilterCombo")
        self.layer_filter_combo.addItem(tr("paint.layer.filter_kind"), "kind")
        layer_filter_row.addWidget(self.layer_filter_combo, stretch=1)
        for icon_name, label in (
            ("image", "Pixel layers"),
            ("color", "Adjustment layers"),
            ("caption", "Text layers"),
            ("path-tool", "Shape paths"),
            ("layers", "Smart objects"),
            ("more", "Layer menu"),
        ):
            layer_filter_row.addWidget(self._make_layer_tiny_button(icon_name, label))
        layer_controls_layout.addLayout(layer_filter_row)

        layer_mode_row = QHBoxLayout()
        layer_mode_row.setContentsMargins(0, 0, 0, 0)
        layer_mode_row.setSpacing(6)
        self.layer_blend_combo = QComboBox()
        self.layer_blend_combo.setObjectName("PaintLayerBlendCombo")
        self.layer_blend_combo.addItem(tr("paint.layer.blend_normal"), "normal")
        self.layer_blend_combo.addItem("Multiply", "multiply")
        self.layer_blend_combo.addItem("Screen", "screen")
        self.layer_blend_combo.addItem("Overlay", "overlay")
        self.layer_blend_combo.currentIndexChanged.connect(self._on_layer_blend_changed)
        layer_opacity_text = QLabel(tr("paint.layer.opacity"))
        layer_opacity_text.setObjectName("PaintLayerControlLabel")
        self._layer_opacity_value = QLabel("100%")
        self._layer_opacity_value.setObjectName("PaintValue")
        layer_mode_row.addWidget(self.layer_blend_combo, stretch=1)
        layer_mode_row.addWidget(layer_opacity_text)
        layer_mode_row.addWidget(self._layer_opacity_value)
        layer_controls_layout.addLayout(layer_mode_row)

        self.layer_opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.layer_opacity_slider.setRange(0, 100)
        self.layer_opacity_slider.setValue(100)
        self.layer_opacity_slider.valueChanged.connect(self._on_layer_opacity_changed)
        layer_controls_layout.addWidget(self.layer_opacity_slider)

        layer_lock_row = QHBoxLayout()
        layer_lock_row.setContentsMargins(0, 0, 0, 0)
        layer_lock_row.setSpacing(5)
        layer_lock_label = QLabel(tr("paint.layer.lock"))
        layer_lock_label.setObjectName("PaintLayerControlLabel")
        layer_lock_row.addWidget(layer_lock_label)
        self._layer_lock_transparency_btn = self._make_layer_tiny_button(
            "grid",
            tr("paint.layer.lock_transparency"),
            checkable=True,
        )
        self._layer_lock_pixels_btn = self._make_layer_tiny_button(
            "paint-brush",
            tr("paint.layer.lock_pixels"),
            checkable=True,
        )
        self._layer_lock_position_btn = self._make_layer_tiny_button(
            "cursor",
            tr("paint.layer.lock_position"),
            checkable=True,
        )
        self._layer_lock_all_btn = self._make_layer_tiny_button(
            "lock",
            tr("paint.layer.lock_all"),
            checkable=True,
        )
        self._layer_lock_all_btn.toggled.connect(self._toggle_active_layer_lock)
        for btn in (
            self._layer_lock_transparency_btn,
            self._layer_lock_pixels_btn,
            self._layer_lock_position_btn,
            self._layer_lock_all_btn,
        ):
            layer_lock_row.addWidget(btn)
        layer_lock_row.addStretch(1)
        layer_fill_label = QLabel(tr("paint.layer.fill"))
        layer_fill_label.setObjectName("PaintLayerControlLabel")
        self._layer_fill_value = QLabel("100%")
        self._layer_fill_value.setObjectName("PaintValue")
        layer_lock_row.addWidget(layer_fill_label)
        layer_lock_row.addWidget(self._layer_fill_value)
        layer_controls_layout.addLayout(layer_lock_row)
        layers_layout.addWidget(layer_controls)

        self._layer_list = QListWidget()
        self._layer_list.setObjectName("PaintLayerList")
        self._layer_list.setMinimumHeight(150)
        self._layer_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._layer_list.itemClicked.connect(self._select_layer_item)
        self._layer_list.itemDoubleClicked.connect(self._rename_layer_item)
        self._layer_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._layer_list.customContextMenuRequested.connect(self._open_layer_context_menu)
        layers_layout.addWidget(self._layer_list, stretch=1)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        for label_text, handler in (
            ("New", self._new_paint_layer),
            ("Dup", self._duplicate_selected_layer),
            ("Copy", self._copy_selected_layer),
            ("Paste", self._paste_layer_clipboard),
            ("Del", self._delete_selected_layer),
        ):
            btn = QPushButton(label_text)
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            edit_row.addWidget(btn)
        layers_layout.addLayout(edit_row)
        self._layer_count_labels: dict[str, QLabel] = {}
        for key, label_text in (
            ("strokes", "Strokes"),
            ("bubbles", "Speech bubbles"),
            ("stickers", "PNG stickers"),
        ):
            if self._standalone and key != "strokes":
                continue
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_label = QLabel(label_text)
            name_label.setObjectName("PaintMeta")
            count_label = QLabel("0")
            count_label.setObjectName("PaintCount")
            row.addWidget(name_label)
            row.addStretch(1)
            row.addWidget(count_label)
            layers_layout.addLayout(row)
            self._layer_count_labels[key] = count_label
        self._layer_channel_path_tabs.addTab(layers_tab, tr("paint.tab.layers"))

        channels_tab = QWidget()
        channels_layout = QVBoxLayout(channels_tab)
        channels_layout.setContentsMargins(8, 8, 8, 8)
        channels_layout.setSpacing(8)
        channel_row = QHBoxLayout()
        channel_row.setContentsMargins(0, 0, 0, 0)
        self.toggle_channel_visibility_btn = QPushButton("Eye")
        self.toggle_channel_visibility_btn.setObjectName("PaintCustomColor")
        self.toggle_channel_visibility_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_channel_visibility_btn.setToolTip("Toggle visibility for the selected channel")
        self.toggle_channel_visibility_btn.clicked.connect(self._toggle_selected_channel_visibility)
        self.copy_channel_btn = QPushButton("Copy")
        self.copy_channel_btn.setObjectName("PaintCustomColor")
        self.copy_channel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_channel_btn.setToolTip("Copy the selected channel image to the system clipboard")
        self.copy_channel_btn.clicked.connect(self._copy_selected_channel_image)
        self.paste_channel_btn = QPushButton("Paste")
        self.paste_channel_btn.setObjectName("PaintCustomColor")
        self.paste_channel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.paste_channel_btn.setToolTip("Paste a grayscale clipboard image into the selected channel")
        self.paste_channel_btn.clicked.connect(self._paste_selected_channel_image)
        channel_row.addWidget(self.toggle_channel_visibility_btn)
        channel_row.addWidget(self.copy_channel_btn)
        channel_row.addWidget(self.paste_channel_btn)
        channels_layout.addLayout(channel_row)
        self._channel_list = QListWidget()
        self._channel_list.setObjectName("PaintLayerList")
        self._channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._channel_list.itemClicked.connect(self._select_channel_item)
        self._update_channel_list()
        channels_layout.addWidget(self._channel_list, stretch=1)
        self._layer_channel_path_tabs.addTab(channels_tab, tr("paint.tab.channels"))

        paths_tab = QWidget()
        paths_layout = QVBoxLayout(paths_tab)
        paths_layout.setContentsMargins(8, 8, 8, 8)
        paths_layout.setSpacing(8)
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
        self.path_to_selection_btn = QPushButton("Select")
        self.path_to_selection_btn.setObjectName("PaintCustomColor")
        self.path_to_selection_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_to_selection_btn.setToolTip("Convert the selected path to a marching-ants selection")
        self.path_to_selection_btn.clicked.connect(self._make_selection_from_selected_path)
        self.path_to_mask_btn = QPushButton("Mask")
        self.path_to_mask_btn.setObjectName("PaintCustomColor")
        self.path_to_mask_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.path_to_mask_btn.setToolTip("Convert the selected path to a layer mask")
        self.path_to_mask_btn.clicked.connect(self._mask_selected_layer_from_path)
        self.clear_path_btn = QPushButton("Clear")
        self.clear_path_btn.setObjectName("PaintCustomColor")
        self.clear_path_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_path_btn.clicked.connect(self._clear_path_preview)
        path_row.addWidget(self.commit_path_btn)
        path_row.addWidget(self.close_path_btn)
        path_row.addWidget(self.path_to_selection_btn)
        path_row.addWidget(self.path_to_mask_btn)
        path_row.addWidget(self.clear_path_btn)
        paths_layout.addLayout(path_row)
        self._path_list = QListWidget()
        self._path_list.setObjectName("PaintLayerList")
        self._path_list.setMinimumHeight(150)
        self._path_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._path_list.itemClicked.connect(self._select_path_item)
        paths_layout.addWidget(self._path_list, stretch=1)
        self._layer_channel_path_tabs.addTab(paths_tab, tr("paint.tab.paths"))

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.setContentsMargins(8, 8, 8, 8)
        history_layout.setSpacing(8)
        self._history_list = QListWidget()
        self._history_list.setObjectName("PaintLayerList")
        self._history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        history_layout.addWidget(self._history_list, stretch=1)
        self._layer_channel_path_tabs.addTab(history_tab, "History")

        pbr_tab = QWidget()
        pbr_layout = QVBoxLayout(pbr_tab)
        pbr_layout.setContentsMargins(8, 8, 8, 8)
        pbr_layout.setSpacing(8)
        pbr_source = QLabel("Source: current Painter document")
        pbr_source.setObjectName("PaintMeta")
        pbr_layout.addWidget(pbr_source)

        pbr_mode_row = QHBoxLayout()
        pbr_mode_row.setContentsMargins(0, 0, 0, 0)
        pbr_mode_label = QLabel("Preview")
        pbr_mode_label.setObjectName("PaintMeta")
        self.pbr_preview_mode_combo = QComboBox()
        for label_text, mode in (
            ("Material Plane", "material"),
            ("Base Color", "base_color"),
            ("Normal", "normal"),
            ("AO", "ao"),
            ("Roughness", "roughness"),
            ("Metallic", "metallic"),
            ("Height", "height"),
            ("Cavity", "cavity"),
            ("Unreal ORM", "unreal_orm"),
            ("glTF MR", "gltf_mr"),
        ):
            self.pbr_preview_mode_combo.addItem(label_text, mode)
        self.pbr_preview_mode_combo.currentIndexChanged.connect(self._queue_pbr_texture_preview)
        pbr_mode_row.addWidget(pbr_mode_label)
        pbr_mode_row.addWidget(self.pbr_preview_mode_combo, stretch=1)
        pbr_layout.addLayout(pbr_mode_row)

        pbr_normal_row = QHBoxLayout()
        pbr_normal_row.setContentsMargins(0, 0, 0, 0)
        normal_label = QLabel("Normal")
        normal_label.setObjectName("PaintMeta")
        self.pbr_normal_format_combo = QComboBox()
        self.pbr_normal_format_combo.addItem("Unreal / DirectX", "unreal_directx")
        self.pbr_normal_format_combo.addItem("OpenGL", "opengl")
        self.pbr_normal_format_combo.currentIndexChanged.connect(self._queue_pbr_texture_preview)
        pbr_normal_row.addWidget(normal_label)
        pbr_normal_row.addWidget(self.pbr_normal_format_combo, stretch=1)
        pbr_layout.addLayout(pbr_normal_row)

        self._pbr_slider_labels: dict[str, QLabel] = {}
        self._pbr_sliders: dict[str, QSlider] = {}
        for label_text, key, minimum, maximum, value, suffix in (
            ("Normal Strength", "normal_strength", 0, 120, 24, "x0.1"),
            ("Normal Radius", "normal_radius_px", 0, 240, 18, "x0.1"),
            ("AO Strength", "ao_strength", 0, 300, 82, "x0.01"),
            ("AO Radius", "ao_radius_px", 0, 640, 80, "x0.1"),
            ("Roughness", "roughness_bias", 0, 100, 55, "x0.01"),
            ("Detail", "roughness_detail", 0, 100, 34, "x0.01"),
            ("Metallic", "metallic_value", 0, 100, 0, "x0.01"),
            ("Light Elevation", "preview_light_elevation", 3, 89, 48, "deg"),
        ):
            self._add_pbr_slider(pbr_layout, label_text, key, minimum, maximum, value, suffix)

        self.pbr_preview_label = QLabel()
        self.pbr_preview_label.setObjectName("PaintPbrPreview")
        self.pbr_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pbr_preview_label.setMinimumHeight(130)
        pbr_layout.addWidget(self.pbr_preview_label)

        pbr_buttons = QHBoxLayout()
        pbr_buttons.setContentsMargins(0, 0, 0, 0)
        self.pbr_refresh_btn = QPushButton("Preview")
        self.pbr_refresh_btn.setObjectName("PaintCustomColor")
        self.pbr_refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pbr_refresh_btn.clicked.connect(self._refresh_pbr_texture_preview)
        self.pbr_export_maps_btn = QPushButton("Maps")
        self.pbr_export_maps_btn.setObjectName("PaintCustomColor")
        self.pbr_export_maps_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pbr_export_maps_btn.setToolTip("Export separate BaseColor, Normal, AO, Roughness, Metallic, Height, and Cavity maps")
        self.pbr_export_maps_btn.clicked.connect(lambda: self._export_pbr_texture_maps(packed=False))
        self.pbr_export_packed_btn = QPushButton("Packed")
        self.pbr_export_packed_btn.setObjectName("PaintCustomColor")
        self.pbr_export_packed_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pbr_export_packed_btn.setToolTip("Export Unreal ARM/ORM and glTF channel-packed maps")
        self.pbr_export_packed_btn.clicked.connect(lambda: self._export_pbr_texture_maps(packed=True))
        pbr_buttons.addWidget(self.pbr_refresh_btn)
        pbr_buttons.addWidget(self.pbr_export_maps_btn)
        pbr_buttons.addWidget(self.pbr_export_packed_btn)
        pbr_layout.addLayout(pbr_buttons)

        self.pbr_status_label = QLabel("Preview uses the current visible Painter document.")
        self.pbr_status_label.setObjectName("PaintMeta")
        self.pbr_status_label.setWordWrap(True)
        pbr_layout.addWidget(self.pbr_status_label)
        pbr_layout.addStretch(1)
        self._pbr_preview_timer = QTimer(self)
        self._pbr_preview_timer.setSingleShot(True)
        self._pbr_preview_timer.timeout.connect(self._refresh_pbr_texture_preview)
        self._layer_channel_path_tabs.addTab(pbr_tab, "PBR Maps")

        if self._standalone:
            inspector_layout.addWidget(self._layer_channel_path_tabs, stretch=1)
            inspector_layout.addWidget(inspector_controls_scroll, stretch=0)
        else:
            inspector_layout.addWidget(inspector_controls_scroll)
            inspector_layout.addWidget(self._layer_channel_path_tabs, stretch=1)

        note = QLabel(tr("paint.note"))
        note.setObjectName("PaintMeta")
        note.setWordWrap(True)
        inspector_layout.addWidget(note)
        workspace.addWidget(inspector)

        self._sync_palette_controls_from_color()
        self._highlight_selected_palette()
        self._update_inspector_counts()
        self._install_edit_shortcuts()

    def _add_pbr_slider(
        self,
        layout: QVBoxLayout,
        label_text: str,
        key: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
    ) -> None:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(label_text)
        label.setObjectName("PaintMeta")
        value_label = QLabel("")
        value_label.setObjectName("PaintValue")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value_label)
        layout.addLayout(row)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(minimum), int(maximum))
        slider.setValue(int(value))
        slider.setProperty("pbr_key", key)
        slider.setProperty("pbr_suffix", suffix)
        slider.valueChanged.connect(lambda _value, k=key: self._on_pbr_slider_changed(k))
        layout.addWidget(slider)
        self._pbr_sliders[key] = slider
        self._pbr_slider_labels[key] = value_label
        self._sync_pbr_slider_label(key)

    def _pbr_slider_value(self, key: str) -> float:
        slider = getattr(self, "_pbr_sliders", {}).get(key)
        if slider is None:
            return 0.0
        suffix = str(slider.property("pbr_suffix") or "")
        value = float(slider.value())
        if suffix == "x0.1":
            return value / 10.0
        if suffix == "x0.01":
            return value / 100.0
        return value

    def _sync_pbr_slider_label(self, key: str) -> None:
        label = getattr(self, "_pbr_slider_labels", {}).get(key)
        if label is None:
            return
        slider = getattr(self, "_pbr_sliders", {}).get(key)
        suffix = str(slider.property("pbr_suffix") or "") if slider is not None else ""
        value = self._pbr_slider_value(key)
        if suffix == "deg":
            label.setText(f"{value:.0f} deg")
        elif suffix == "x0.1":
            label.setText(f"{value:.1f}")
        elif suffix == "x0.01":
            label.setText(f"{value:.2f}")
        else:
            label.setText(str(int(value)))

    def _on_pbr_slider_changed(self, key: str) -> None:
        self._sync_pbr_slider_label(key)
        self._queue_pbr_texture_preview()

    def _queue_pbr_texture_preview(self) -> None:
        timer = getattr(self, "_pbr_preview_timer", None)
        if timer is not None:
            timer.start(180)

    def _pbr_texture_settings_payload(self, overrides: dict | None = None) -> dict:
        combo = getattr(self, "pbr_normal_format_combo", None)
        settings = {
            "normal_strength": self._pbr_slider_value("normal_strength"),
            "normal_radius_px": self._pbr_slider_value("normal_radius_px"),
            "normal_format": str(combo.currentData() if combo is not None else "unreal_directx"),
            "ao_strength": self._pbr_slider_value("ao_strength"),
            "ao_radius_px": self._pbr_slider_value("ao_radius_px"),
            "roughness_bias": self._pbr_slider_value("roughness_bias"),
            "roughness_detail": self._pbr_slider_value("roughness_detail"),
            "metallic_value": self._pbr_slider_value("metallic_value"),
            "preview_light_elevation": self._pbr_slider_value("preview_light_elevation"),
        }
        if overrides:
            settings.update(dict(overrides))
        return settings

    def _pbr_source_output_path(self) -> Path:
        root = Path(tempfile.gettempdir()) / "tiger_painter_pbr"
        root.mkdir(parents=True, exist_ok=True)
        return root / "painter_visible_document_source.png"

    def _write_pbr_source_image(self, output_path: str | Path | None = None) -> dict:
        from PIL import Image

        path = Path(output_path) if output_path else self._pbr_source_output_path()
        bg = self._export_background_pixmap()
        target_size = _paint_export_size(bg, fallback=self._canvas_document_size)
        width_scale = target_size[0] / max(1, self.canvas.width())
        report = export_paint_png(
            path,
            background_pixmap=bg,
            strokes=self._visible_strokes_for_export(),
            bubbles=self._bubbles,
            stickers=self._stickers,
            time_ms=self._time_ms,
            frame_size=target_size,
            include_background=True,
            stroke_width_scale=width_scale,
        )
        image = Image.open(path).convert("RGBA")
        neutral = Image.new("RGBA", image.size, (128, 128, 128, 255))
        Image.alpha_composite(neutral, image).convert("RGB").save(path, "PNG")
        self._pbr_source_path = str(path)
        report["pbr_source_path"] = str(path)
        report["transparent_pixels_flattened_to"] = "#808080"
        return report

    def _refresh_pbr_texture_preview(self) -> None:
        try:
            mode = str(self.pbr_preview_mode_combo.currentData() or "material")
            source = self._write_pbr_source_image()
            out = Path(tempfile.gettempdir()) / "tiger_painter_pbr" / f"painter_pbr_preview_{mode}.png"
            from app.ar_pbr.texture_map_lab import render_plane_preview

            payload = render_plane_preview(
                source["pbr_source_path"],
                self._pbr_texture_settings_payload(),
                preview_mode=mode,
                output_path=out,
                width=512,
            )
            pixmap = QPixmap(str(payload["preview_path"]))
            if not pixmap.isNull():
                self.pbr_preview_label.setPixmap(
                    pixmap.scaled(
                        self.pbr_preview_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._pbr_preview_payload = payload
            self.pbr_status_label.setText(f"{mode} | {payload['size'][0]} x {payload['size'][1]}")
        except Exception as exc:
            if hasattr(self, "pbr_status_label"):
                self.pbr_status_label.setText(f"PBR preview failed: {type(exc).__name__}: {exc}")

    def _export_pbr_texture_maps(self, *, packed: bool) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        try:
            from app.paths import default_save_dir

            base_dir = default_save_dir()
        except Exception:
            base_dir = Path.home()
        selected = QFileDialog.getExistingDirectory(self, "Export Painter PBR Maps", str(base_dir))
        if not selected:
            return
        try:
            payload = self.export_pbr_maps_to_path(selected, packed=bool(packed))
        except Exception as exc:
            QMessageBox.warning(self, "Painter PBR Maps", f"Export failed:\n\n{type(exc).__name__}: {exc}")
            return
        QMessageBox.information(self, "Painter PBR Maps", f"Wrote PBR maps:\n{payload.get('output_dir')}")

    def preview_pbr_map_to_path(
        self,
        path: str | Path,
        *,
        preview_mode: str = "material",
        width: int = 512,
        settings: dict | None = None,
    ) -> dict:
        source = self._write_pbr_source_image()
        from app.ar_pbr.texture_map_lab import render_plane_preview

        payload = render_plane_preview(
            source["pbr_source_path"],
            self._pbr_texture_settings_payload(settings),
            preview_mode=preview_mode,
            output_path=path,
            width=int(width or 512),
        )
        self._pbr_preview_payload = payload
        return payload

    def export_pbr_maps_to_path(
        self,
        output_dir: str | Path,
        *,
        settings: dict | None = None,
        maps: list[str] | tuple[str, ...] | None = None,
        packed_layouts: list[str] | tuple[str, ...] | None = None,
        packed: bool = True,
    ) -> dict:
        source = self._write_pbr_source_image()
        layouts = packed_layouts
        if layouts is None:
            layouts = ("unreal_orm", "arm", "gltf_mr") if packed else ()
        from app.ar_pbr.texture_map_lab import export_texture_maps

        payload = export_texture_maps(
            source["pbr_source_path"],
            output_dir,
            self._pbr_texture_settings_payload(settings),
            maps=maps,
            packed_layouts=layouts,
        )
        payload["painter_source"] = source
        return payload

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._bubble_items and self._bubbles:
            self._spawn_initial_bubbles()
        if not self._sticker_items and self._stickers:
            self._spawn_initial_stickers()

    def _brush_preset_icon(self, preset: dict[str, object]) -> QIcon:
        pixmap = QPixmap(76, 36)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#171b24"))
            painter.drawRoundedRect(QRectF(0.5, 0.5, 75, 35), 6, 6)
            painter.setBrush(QColor(255, 255, 255, 10))
            painter.drawRoundedRect(QRectF(4, 4, 68, 28), 5, 5)
            style = str(preset.get("style") or "round")
            width = max(1.5, min(16.0, float(preset.get("width") or 4) * 0.55))
            opacity = max(35, min(255, int(float(preset.get("opacity") or 100) * 2.55)))
            hue_colors = {
                "Pencil & Ink": "#DCE6F7",
                "Flow Map": "#6FA8C8",
                "Texture": "#A8B4C6",
                "Utility": "#C7A46A",
            }
            color = QColor(hue_colors.get(str(preset.get("category") or ""), "#90A9D6"))
            color.setAlpha(opacity)
            pen = QPen(color, width)
            DrawingCanvas._configure_pen_for_style(pen, style)
            if style == "dashed":
                pen.setDashPattern([4.0, 3.0])
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(9, 24)
            path.cubicTo(19, 9, 33, 28, 47, 15)
            path.cubicTo(55, 7, 62, 17, 69, 11)
            painter.drawPath(path)
            painter.setPen(QPen(QColor(255, 255, 255, 44), 1.0))
            if style == "highlighter":
                painter.drawLine(QPointF(11, 28), QPointF(66, 28))
            elif style == "marker":
                painter.drawLine(QPointF(12, 8), QPointF(67, 8))
        finally:
            painter.end()
        return QIcon(pixmap)

    def _populate_brush_library(self) -> None:
        if not hasattr(self, "brush_library_list"):
            return
        selected_category = ""
        if hasattr(self, "brush_category_combo"):
            selected_category = str(self.brush_category_combo.currentData() or "")
        self.brush_library_list.clear()
        for idx, preset in enumerate(BRUSH_LIBRARY_PRESETS):
            category = str(preset["category"])
            if selected_category and category != selected_category:
                continue
            name = str(preset["name"])
            width = int(preset["width"])
            opacity = int(preset["opacity"])
            item = QListWidgetItem(self._brush_preset_icon(preset), "")
            item.setToolTip(f"{category} | {name} | {width}px / {opacity}%")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setSizeHint(QSize(86, 54))
            self.brush_library_list.addItem(item)
        if self.brush_library_list.count() > 0:
            self.brush_library_list.setCurrentRow(0)

    def _on_brush_library_item(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        try:
            preset = BRUSH_LIBRARY_PRESETS[int(idx)]
        except Exception:
            return
        self._apply_brush_library_preset(preset)

    def _apply_brush_library_preset(self, preset: dict[str, object]) -> None:
        style = str(preset.get("style") or "round")
        width = int(preset.get("width") or self._pen_width)
        opacity = int(preset.get("opacity") or 100)
        if hasattr(self, "brush_style_combo"):
            index = self.brush_style_combo.findData(style)
            if index >= 0:
                self.brush_style_combo.setCurrentIndex(index)
        if hasattr(self, "width_slider"):
            self.width_slider.setValue(max(1, min(60, width)))
        if hasattr(self, "opacity_slider"):
            self.opacity_slider.setValue(max(10, min(100, opacity)))
        self._set_tool("pen")
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"Brush: {preset.get('name', 'Preset')}")

    def _make_palette_button(
        self,
        rgb: tuple[int, int, int],
        *,
        width: int = 38,
        height: int = 16,
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
            if hasattr(self, "color_wheel"):
                self.color_wheel.set_color(self._pen_color)
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
            "height: 5px; border-radius: 3px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #111827, stop:1 rgb({bright.red()},{bright.green()},{bright.blue()})); "
            "}"
            "QSlider#PaintValueSlider::handle:horizontal { "
            "width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; "
            "background: #e8eef8; border: 1px solid #111827; "
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
        radius = max(4, min(5, height // 3))
        border = "#c8d5e9" if selected else "#303847"
        border_width = 2 if selected else 1
        btn.setStyleSheet(
            "QPushButton { "
            f"background-color: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
            f"border: {border_width}px solid {border}; "
            f"border-radius: {radius}px; "
            "padding: 0; "
            "}"
            "QPushButton:hover { border-color: #8fb1dd; }"
        )

    def _refresh_recent_color_buttons(self, selected: tuple[int, int, int]) -> None:
        for idx, btn in enumerate(self._recent_color_btns):
            if idx >= len(self._recent_colors):
                btn.hide()
                continue
            rgb = self._recent_colors[idx]
            btn.show()
            self._style_palette_button(btn, rgb, selected=(rgb == selected), width=32, height=16)

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
        canvas_tool = tool if tool in (
            "pen",
            "eraser",
            "path",
            "rect_select",
            "ellipse_select",
            "crop",
            "magic_select",
        ) else "off"
        self.canvas.set_tool(canvas_tool)
        self.select_btn.setChecked(tool == "select")
        if hasattr(self, "pan_btn"):
            self.pan_btn.setChecked(tool == "pan")
        if hasattr(self, "rect_select_btn"):
            self.rect_select_btn.setChecked(tool == "rect_select")
        if hasattr(self, "ellipse_select_btn"):
            self.ellipse_select_btn.setChecked(tool == "ellipse_select")
        if hasattr(self, "magic_select_btn"):
            self.magic_select_btn.setChecked(tool == "magic_select")
        if hasattr(self, "crop_btn"):
            self.crop_btn.setChecked(tool == "crop")
        self.pen_btn.setChecked(tool == "pen")
        self.eraser_btn.setChecked(tool == "eraser")
        self.path_btn.setChecked(tool == "path")
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            host.setCursor(
                Qt.CursorShape.OpenHandCursor
                if tool == "pan"
                else Qt.CursorShape.ArrowCursor
            )
        if hasattr(self, "_tool_status_label"):
            labels = {
                "select": "Select / move objects",
                "pan": "Pan canvas",
                "pen": "Pen",
                "eraser": "Eraser",
                "path": "Path: click points, double-click to commit",
                "rect_select": "Rectangular marquee",
                "ellipse_select": "Elliptical marquee",
                "magic_select": "Magic Select: click a color region",
                "crop": "Crop: drag a crop area, then Image > Crop To Selection",
            }
            self._tool_status_label.setText(labels.get(tool, "Select / move objects"))
        self._update_tool_option_controls()

    def _on_selection_aspect_changed(self) -> None:
        mode = "free"
        if hasattr(self, "selection_aspect_combo"):
            mode = str(self.selection_aspect_combo.currentData() or "free")
        self._set_selection_aspect_mode(mode)

    def _set_selection_aspect_mode(self, mode: str) -> str:
        value = str(mode or "free").strip().casefold().replace("-", "_")
        aliases = {
            "free": "free",
            "custom": "free",
            "square": "square",
            "1_1": "square",
            "1:1": "square",
            "16_9": "16:9",
            "16:9": "16:9",
            "4_3": "4:3",
            "4:3": "4:3",
        }
        selected = aliases.get(value, "free")
        self._selection_aspect_mode = selected
        if hasattr(self, "selection_aspect_combo"):
            index = self.selection_aspect_combo.findData(selected)
            if index >= 0 and self.selection_aspect_combo.currentIndex() != index:
                self.selection_aspect_combo.blockSignals(True)
                try:
                    self.selection_aspect_combo.setCurrentIndex(index)
                finally:
                    self.selection_aspect_combo.blockSignals(False)
        if hasattr(self, "canvas"):
            self.canvas.set_selection_aspect_mode(selected)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"Selection ratio: {selected}")
        return selected

    def _set_quick_mask_enabled(self, enabled: bool | None = None) -> bool:
        if enabled is None:
            enabled = not bool(getattr(self, "_quick_mask_enabled", False))
        self._quick_mask_enabled = bool(enabled)
        if hasattr(self, "quick_mask_btn"):
            self.quick_mask_btn.blockSignals(True)
            try:
                self.quick_mask_btn.setChecked(self._quick_mask_enabled)
            finally:
                self.quick_mask_btn.blockSignals(False)
        if hasattr(self, "canvas"):
            self.canvas.set_quick_mask_enabled(self._quick_mask_enabled)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                "Quick Mask on" if self._quick_mask_enabled else "Quick Mask off"
            )
        return self._quick_mask_enabled

    def _set_grid_options(
        self,
        *,
        visible: bool | None = None,
        snap: bool | None = None,
        size_px: int | None = None,
    ) -> dict[str, bool | int]:
        if visible is not None:
            self._grid_visible = bool(visible)
        if snap is not None:
            self._snap_to_grid = bool(snap)
        if size_px is not None:
            self._grid_size_px = max(4, min(512, int(size_px or 64)))
        if hasattr(self, "grid_view_btn"):
            self.grid_view_btn.blockSignals(True)
            try:
                self.grid_view_btn.setChecked(bool(self._grid_visible))
            finally:
                self.grid_view_btn.blockSignals(False)
        if hasattr(self, "snap_grid_btn"):
            self.snap_grid_btn.blockSignals(True)
            try:
                self.snap_grid_btn.setChecked(bool(self._snap_to_grid))
            finally:
                self.snap_grid_btn.blockSignals(False)
        if hasattr(self, "canvas"):
            self.canvas.set_grid_options(
                visible=bool(self._grid_visible),
                snap=bool(self._snap_to_grid),
                size_px=int(self._grid_size_px),
            )
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                f"Grid {'on' if self._grid_visible else 'off'} / "
                f"Snap {'on' if self._snap_to_grid else 'off'}"
            )
        return {
            "visible": bool(self._grid_visible),
            "snap": bool(self._snap_to_grid),
            "size_px": int(self._grid_size_px),
        }

    def _on_magic_tolerance_changed(self, value: int) -> None:
        self._magic_select_tolerance = max(0, min(100, int(value or 0)))
        if hasattr(self, "_magic_tolerance_value_label"):
            self._magic_tolerance_value_label.setText(str(self._magic_select_tolerance))

    def _set_mirror_enabled(
        self,
        *,
        x: bool | None = None,
        y: bool | None = None,
    ) -> dict[str, bool]:
        if x is not None:
            self._mirror_x_enabled = bool(x)
        if y is not None:
            self._mirror_y_enabled = bool(y)
        if hasattr(self, "mirror_x_btn"):
            self.mirror_x_btn.blockSignals(True)
            try:
                self.mirror_x_btn.setChecked(bool(self._mirror_x_enabled))
            finally:
                self.mirror_x_btn.blockSignals(False)
        if hasattr(self, "mirror_y_btn"):
            self.mirror_y_btn.blockSignals(True)
            try:
                self.mirror_y_btn.setChecked(bool(self._mirror_y_enabled))
            finally:
                self.mirror_y_btn.blockSignals(False)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                f"Mirror X {'on' if self._mirror_x_enabled else 'off'} / "
                f"Y {'on' if self._mirror_y_enabled else 'off'}"
            )
        return {"x": bool(self._mirror_x_enabled), "y": bool(self._mirror_y_enabled)}

    def _update_tool_option_controls(self) -> None:
        has_selection = bool(hasattr(self, "canvas") and self.canvas.has_active_selection())
        current_tool = str(getattr(self.canvas, "_tool", "off") if hasattr(self, "canvas") else "off")
        if hasattr(self, "selection_aspect_combo"):
            self.selection_aspect_combo.setEnabled(current_tool in {"rect_select", "ellipse_select", "crop"})
        if hasattr(self, "magic_tolerance_slider"):
            self.magic_tolerance_slider.setEnabled(current_tool == "magic_select")
        if hasattr(self, "crop_apply_btn"):
            self.crop_apply_btn.setEnabled(has_selection)
        if hasattr(self, "mask_selection_btn"):
            self.mask_selection_btn.setEnabled(has_selection and self._selected_layer_id != "background")
        if hasattr(self, "deselect_option_btn"):
            self.deselect_option_btn.setEnabled(has_selection)
        if hasattr(self, "quick_mask_btn"):
            self.quick_mask_btn.setChecked(bool(getattr(self, "_quick_mask_enabled", False)))
        if hasattr(self, "grid_view_btn"):
            self.grid_view_btn.setChecked(bool(getattr(self, "_grid_visible", False)))
        if hasattr(self, "snap_grid_btn"):
            self.snap_grid_btn.setChecked(bool(getattr(self, "_snap_to_grid", False)))

    def _apply_crop_if_crop_tool(self) -> None:
        current_tool = str(getattr(self.canvas, "_tool", "off") if hasattr(self, "canvas") else "off")
        if current_tool == "crop" and self._selection_bounds() is not None:
            self._crop_to_selection()

    def _clear_all(self) -> None:
        self._push_undo_state("Clear all")
        self.canvas.clear_strokes_direct()
        self.canvas.clear_selection()
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

    def _on_color_wheel_changed(self, color: QColor) -> None:
        if self._palette_syncing:
            return
        self._apply_pen_color(color, remember=False)
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
        if self._standalone and self._active_paint_layer().locked:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(tr("paint.layer.locked_status"))
            return
        self._push_undo_state("Paint stroke" if stroke.source_tool != "path" else "Commit path")
        stroke.start_ms = self._time_ms
        if self._standalone:
            stroke.layer_id = self._active_paint_layer_id
        self.canvas.add_stroke_direct(stroke)
        for mirrored in self._mirrored_strokes_for(stroke):
            self.canvas.add_stroke_direct(mirrored)
        self._update_inspector_counts()

    def _mirrored_strokes_for(self, stroke: Stroke) -> list[Stroke]:
        if str(getattr(stroke, "source_tool", "") or "") != "pen":
            return []
        variants: list[tuple[bool, bool]] = []
        if self._mirror_x_enabled:
            variants.append((True, False))
        if self._mirror_y_enabled:
            variants.append((False, True))
        if self._mirror_x_enabled and self._mirror_y_enabled:
            variants.append((True, True))
        out: list[Stroke] = []
        for flip_x, flip_y in variants:
            copied = copy.deepcopy(stroke)
            copied.points = [
                (
                    max(0.0, min(1.0, 1.0 - float(x) if flip_x else float(x))),
                    max(0.0, min(1.0, 1.0 - float(y) if flip_y else float(y))),
                )
                for x, y in copied.points
            ]
            copied.source_tool = "pen_mirror"
            out.append(copied)
        return out

    def _erase_stroke_direct(self, idx: int) -> None:
        strokes = self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
        if 0 <= idx < len(strokes):
            layer_id = str(getattr(strokes[idx], "layer_id", "") or "paint-layer-1")
            layer = self._paint_layer_by_id(layer_id)
            if layer is not None and layer.locked:
                if hasattr(self, "_tool_status_label"):
                    self._tool_status_label.setText(tr("paint.layer.locked_status"))
                return
        self._push_undo_state("Erase stroke")
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
        self.canvas.commit_path(closed=closed, make_selection=closed)
        self._update_inspector_counts()
        self._update_path_list()

    def _clear_path_preview(self) -> None:
        self.canvas.clear_path_preview()
        self._update_path_list()

    def _on_zoom_changed(self, value: int) -> None:
        self._canvas_zoom = max(0.25, min(4.0, value / 100.0))
        if hasattr(self, "_zoom_value_label"):
            self._zoom_value_label.setText(f"{value}%")
        self._update_canvas_geometry()

    def _set_zoom_percent(self, value: int) -> None:
        value = max(25, min(400, int(value)))
        if hasattr(self, "zoom_slider"):
            self.zoom_slider.setValue(value)
        else:
            self._on_zoom_changed(value)

    def _zoom_in(self) -> None:
        current = int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100))
        self._set_zoom_percent(current + 25)

    def _zoom_out(self) -> None:
        current = int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100))
        self._set_zoom_percent(current - 25)

    def _zoom_fit(self) -> None:
        self._canvas_pan = QPoint(0, 0)
        self._set_zoom_percent(100)

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
        bg = self._export_background_pixmap() if include_background else None
        target_size = _paint_export_size(
            bg,
            fallback=self._canvas_document_size,
        )
        width_scale = target_size[0] / max(1, self.canvas.width())
        try:
            report = export_paint_png(
                out,
                background_pixmap=bg,
                strokes=self._visible_strokes_for_export(),
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

    def _visible_strokes_for_export(self) -> list[Stroke]:
        if not hasattr(self, "canvas"):
            return []
        visibility = {layer.layer_id: layer.visible for layer in self._paint_layers}
        opacity = {layer.layer_id: layer.opacity for layer in self._paint_layers}
        out: list[Stroke] = []
        for stroke in self.canvas.embedded_strokes():
            layer_id = str(getattr(stroke, "layer_id", "") or "paint-layer-1")
            if not visibility.get(layer_id, True):
                continue
            copied = copy.deepcopy(stroke)
            copied.opacity = max(
                0,
                min(255, int(copied.opacity * opacity.get(layer_id, 100) / 100.0)),
            )
            out.append(copied)
        return out

    def _snapshot_state(self) -> tuple:
        strokes = self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
        return (
            copy.deepcopy(strokes),
            copy.deepcopy(getattr(self, "_bubbles", [])),
            copy.deepcopy(getattr(self, "_stickers", [])),
            copy.deepcopy(getattr(self, "_paint_layers", [])),
            str(getattr(self, "_active_paint_layer_id", "paint-layer-1")),
            self._selected_layer_id,
            self.canvas.selection_snapshot() if hasattr(self, "canvas") else [],
            bool(getattr(self, "_background_layer_present", True)),
            bool(self.canvas.selection_inverted()) if hasattr(self, "canvas") else False,
            copy.deepcopy(getattr(self, "_channel_visibility", {})),
            str(getattr(self, "_selected_path_item_id", "work-path")),
            tuple(getattr(self, "_canvas_document_size", (1920, 1080))),
            QPixmap(getattr(self, "_bg_pixmap_source", QPixmap())),
            str(getattr(self, "_selected_channel", "RGB")),
            str(getattr(self, "_selection_aspect_mode", "free")),
            bool(getattr(self, "_mirror_x_enabled", False)),
            bool(getattr(self, "_mirror_y_enabled", False)),
        )

    def _push_undo_state(self, label: str = "Edit") -> None:
        if self._restoring_state or not hasattr(self, "canvas"):
            return
        self._undo_stack.append(self._snapshot_state())
        self._undo_labels.append(str(label or "Edit"))
        if len(self._undo_stack) > 50:
            self._undo_stack.pop(0)
            if self._undo_labels:
                self._undo_labels.pop(0)
        self._redo_stack.clear()
        self._redo_labels.clear()
        self._update_history_buttons()

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot_state())
        label = self._undo_labels.pop() if self._undo_labels else "Edit"
        self._redo_labels.append(label)
        snapshot = self._undo_stack.pop()
        self._restore_state(snapshot)

    def _redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot_state())
        label = self._redo_labels.pop() if self._redo_labels else "Edit"
        self._undo_labels.append(label)
        snapshot = self._redo_stack.pop()
        self._restore_state(snapshot)

    def _restore_state(
        self,
        snapshot,
    ) -> None:
        self._restoring_state = True
        try:
            strokes, bubbles, stickers = snapshot[:3]
            if len(snapshot) >= 6:
                layers, active_layer_id, selected_layer_id = snapshot[3:6]
                self._paint_layers = copy.deepcopy(layers)
                self._active_paint_layer_id = str(active_layer_id or "paint-layer-1")
                self._selected_layer_id = selected_layer_id
            selection_points = snapshot[6] if len(snapshot) >= 7 else []
            if len(snapshot) >= 8:
                self._background_layer_present = bool(snapshot[7])
            selection_inverted = bool(snapshot[8]) if len(snapshot) >= 9 else False
            if len(snapshot) >= 10 and isinstance(snapshot[9], dict):
                self._channel_visibility = copy.deepcopy(snapshot[9])
            if len(snapshot) >= 11:
                self._selected_path_item_id = str(snapshot[10] or "work-path")
            if len(snapshot) >= 12 and isinstance(snapshot[11], tuple):
                self._canvas_document_size = (
                    max(1, int(snapshot[11][0])),
                    max(1, int(snapshot[11][1])),
                )
            if len(snapshot) >= 13 and isinstance(snapshot[12], QPixmap):
                self._bg_pixmap_source = QPixmap(snapshot[12])
            if len(snapshot) >= 14:
                self._selected_channel = str(snapshot[13] or "RGB")
            if len(snapshot) >= 15:
                self._selection_aspect_mode = self._set_selection_aspect_mode(str(snapshot[14] or "free"))
            if len(snapshot) >= 17:
                self._set_mirror_enabled(x=bool(snapshot[15]), y=bool(snapshot[16]))
            for item in list(getattr(self, "_bubble_items", [])):
                item.deleteLater()
            for item in list(getattr(self, "_sticker_items", [])):
                item.deleteLater()
            self._bubble_items = []
            self._sticker_items = []
            self._bubbles = copy.deepcopy(bubbles)
            self._stickers = copy.deepcopy(stickers)
            self.canvas.set_strokes_snapshot(copy.deepcopy(strokes))
            self.canvas.set_selection_snapshot(
                copy.deepcopy(selection_points),
                inverted=selection_inverted,
            )
            self._sync_canvas_layer_view()
            self._spawn_initial_bubbles()
            self._spawn_initial_stickers()
            self._update_canvas_geometry()
        finally:
            self._restoring_state = False
        self._update_inspector_counts()
        self._update_channel_list()
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        if hasattr(self, "undo_btn"):
            self.undo_btn.setEnabled(bool(self._undo_stack))
        if hasattr(self, "redo_btn"):
            self.redo_btn.setEnabled(bool(self._redo_stack))
        self._update_history_list()

    def _update_history_list(self) -> None:
        history = getattr(self, "_history_list", None)
        if history is None:
            return
        labels = list(getattr(self, "_undo_labels", []) or [])
        redo_labels = list(getattr(self, "_redo_labels", []) or [])
        history.blockSignals(True)
        try:
            history.clear()
            base = QListWidgetItem("Document Opened")
            base.setIcon(app_icon("image", size=14, color="#9EA8BA"))
            history.addItem(base)
            for label in labels:
                item = QListWidgetItem(str(label or "Edit"))
                item.setIcon(app_icon("more", size=14, color="#DCE6F7"))
                history.addItem(item)
            for label in reversed(redo_labels):
                item = QListWidgetItem(f"Redo: {label or 'Edit'}")
                item.setIcon(app_icon("more", size=14, color="#687487"))
                history.addItem(item)
            current_row = max(0, len(labels))
            if history.count():
                history.setCurrentRow(min(current_row, history.count() - 1))
        finally:
            history.blockSignals(False)

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
        self._sync_canvas_layer_view()
        self._update_tool_option_controls()
        self._update_layer_list(strokes_count)
        self._update_path_list()
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
            if self._standalone:
                selected_background = (
                    selected_id == "background" and self._background_layer_present
                )
                if not self._is_paint_layer_id(selected_id) and not selected_background:
                    selected_id = self._active_paint_layer_id
                    self._selected_layer_id = selected_id
                for layer in reversed(self._paint_layers):
                    count = self._stroke_count_for_layer(layer.layer_id)
                    states: list[str] = []
                    if not layer.visible:
                        states.append("Hidden")
                    if layer.locked:
                        states.append("Locked")
                    if bool(getattr(layer, "mask_enabled", False)) and len(getattr(layer, "mask", []) or []) >= 3:
                        states.append("Mask")
                    if getattr(layer, "blend_mode", "normal") != "normal":
                        states.append(str(layer.blend_mode).title())
                    state = " ".join(states)
                    prefix = f"{state}  " if state else ""
                    label = f"{prefix}{layer.name}  {layer.opacity}%  ({count})"
                    item = QListWidgetItem(label)
                    item.setIcon(app_icon("layers", size=14, color="#DCE6F7"))
                    item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
                    layer_list.addItem(item)
                    if selected_id == layer.layer_id:
                        layer_list.setCurrentItem(item)
                if self._background_layer_present:
                    bg_item = QListWidgetItem(tr("paint.layer.background"))
                    bg_item.setIcon(app_icon("lock", size=14, color="#9EA8BA"))
                    bg_item.setData(Qt.ItemDataRole.UserRole, "background")
                    layer_list.addItem(bg_item)
                    if selected_id == "background":
                        layer_list.setCurrentItem(bg_item)
                self._update_layer_controls()
                return
            if strokes_count:
                label = f"Brush strokes ({strokes_count})"
                item = QListWidgetItem(label)
                item.setIcon(app_icon("paint-brush", size=14, color="#DCE6F7"))
                item.setData(Qt.ItemDataRole.UserRole, "strokes")
                layer_list.addItem(item)
                if selected_id == "strokes":
                    layer_list.setCurrentItem(item)
            for idx, bubble in enumerate(getattr(self, "_bubbles", [])):
                text = bubble.text.strip() or "Speech bubble"
                item = QListWidgetItem(f"Bubble {idx + 1}: {text[:24]}")
                item.setIcon(app_icon("caption", size=14, color="#DCE6F7"))
                layer_id = f"bubble:{idx}"
                item.setData(Qt.ItemDataRole.UserRole, layer_id)
                layer_list.addItem(item)
                if selected_id == layer_id:
                    layer_list.setCurrentItem(item)
            for idx, sticker in enumerate(getattr(self, "_stickers", [])):
                from pathlib import Path

                name = Path(sticker.png_path).name or "PNG sticker"
                item = QListWidgetItem(f"Sticker {idx + 1}: {name[:24]}")
                item.setIcon(app_icon("image", size=14, color="#DCE6F7"))
                layer_id = f"sticker:{idx}"
                item.setData(Qt.ItemDataRole.UserRole, layer_id)
                layer_list.addItem(item)
                if selected_id == layer_id:
                    layer_list.setCurrentItem(item)
        finally:
            layer_list.blockSignals(False)

    def _stroke_count_for_layer(self, layer_id: str) -> int:
        if not hasattr(self, "canvas"):
            return 0
        target = str(layer_id)
        return sum(
            1
            for stroke in self.canvas.embedded_strokes()
            if str(getattr(stroke, "layer_id", "") or "paint-layer-1") == target
        )

    def _update_layer_controls(self) -> None:
        if self._selected_layer_id == "background":
            if hasattr(self, "_layer_opacity_value"):
                self._layer_opacity_value.setText("100%")
            if hasattr(self, "_layer_fill_value"):
                self._layer_fill_value.setText("100%")
            self._sync_layer_lock_buttons(True, enabled=False)
            if hasattr(self, "layer_opacity_slider"):
                self.layer_opacity_slider.blockSignals(True)
                try:
                    self.layer_opacity_slider.setValue(100)
                    self.layer_opacity_slider.setEnabled(False)
                finally:
                    self.layer_opacity_slider.blockSignals(False)
            if hasattr(self, "layer_blend_combo"):
                self.layer_blend_combo.blockSignals(True)
                try:
                    normal_index = self.layer_blend_combo.findData("normal")
                    self.layer_blend_combo.setCurrentIndex(max(0, normal_index))
                    self.layer_blend_combo.setEnabled(False)
                finally:
                    self.layer_blend_combo.blockSignals(False)
            return
        layer = self._paint_layer_by_id(self._selected_layer_id) or self._active_paint_layer()
        if hasattr(self, "_layer_opacity_value"):
            self._layer_opacity_value.setText(f"{layer.opacity}%")
        if hasattr(self, "_layer_fill_value"):
            self._layer_fill_value.setText("100%")
        self._sync_layer_lock_buttons(layer.locked, enabled=True)
        if hasattr(self, "layer_opacity_slider"):
            self.layer_opacity_slider.blockSignals(True)
            try:
                self.layer_opacity_slider.setValue(layer.opacity)
                self.layer_opacity_slider.setEnabled(not layer.locked)
            finally:
                self.layer_opacity_slider.blockSignals(False)
        if hasattr(self, "layer_blend_combo"):
            self.layer_blend_combo.blockSignals(True)
            try:
                index = self.layer_blend_combo.findData(getattr(layer, "blend_mode", "normal"))
                self.layer_blend_combo.setCurrentIndex(max(0, index))
                self.layer_blend_combo.setEnabled(not layer.locked)
            finally:
                self.layer_blend_combo.blockSignals(False)

    def _sync_layer_lock_buttons(self, locked: bool, *, enabled: bool) -> None:
        for attr in (
            "_layer_lock_transparency_btn",
            "_layer_lock_pixels_btn",
            "_layer_lock_position_btn",
            "_layer_lock_all_btn",
        ):
            btn = getattr(self, attr, None)
            if btn is None:
                continue
            btn.blockSignals(True)
            try:
                btn.setChecked(bool(locked) if attr == "_layer_lock_all_btn" else False)
                btn.setEnabled(enabled or attr == "_layer_lock_all_btn")
            finally:
                btn.blockSignals(False)

    def _toggle_active_layer_lock(self, checked: bool) -> None:
        if self._selected_layer_id == "background":
            self._sync_layer_lock_buttons(True, enabled=False)
            return
        layer = self._paint_layer_by_id(self._selected_layer_id) or self._active_paint_layer()
        if layer.locked == bool(checked):
            return
        self._push_undo_state("Lock layer" if checked else "Unlock layer")
        layer.locked = bool(checked)
        self._sync_canvas_layer_view()
        self._update_inspector_counts()

    def _rename_layer_item(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        layer = self._paint_layer_by_id(str(layer_id) if layer_id is not None else None)
        if layer is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Rename Layer",
            "Layer name",
            text=layer.name,
        )
        new_name = str(name or "").strip()
        if not accepted or not new_name or new_name == layer.name:
            return
        self._push_undo_state("Rename layer")
        layer.name = new_name[:80]
        self._selected_layer_id = layer.layer_id
        self._update_inspector_counts()

    def _update_channel_list(self) -> None:
        channel_list = getattr(self, "_channel_list", None)
        if channel_list is None:
            return
        current = None
        current_item = channel_list.currentItem()
        if current_item is not None:
            current = current_item.data(Qt.ItemDataRole.UserRole)
        if current is None:
            current = getattr(self, "_selected_channel", "RGB")
        self._channel_visibility["RGB"] = all(
            self._channel_visibility.get(channel, True)
            for channel in ("Red", "Green", "Blue")
        )
        channel_list.blockSignals(True)
        try:
            channel_list.clear()
            for channel in ("RGB", "Red", "Green", "Blue", "Alpha"):
                visible = bool(self._channel_visibility.get(channel, True))
                item = QListWidgetItem(channel)
                item.setIcon(
                    app_icon(
                        "eye" if visible else "eye-off",
                        size=14,
                        color="#DCE6F7" if visible else "#687487",
                    )
                )
                item.setData(Qt.ItemDataRole.UserRole, channel)
                channel_list.addItem(item)
                if current == channel:
                    channel_list.setCurrentItem(item)
            if channel_list.currentItem() is None and channel_list.count():
                channel_list.setCurrentRow(0)
        finally:
            channel_list.blockSignals(False)

    def _select_channel_item(self, item: QListWidgetItem) -> None:
        channel = str(item.data(Qt.ItemDataRole.UserRole) or item.text() or "")
        self._set_selected_channel(channel)

    def _toggle_selected_channel_visibility(self) -> bool:
        channel = self._selected_channel
        item = None
        if hasattr(self, "_channel_list"):
            item = self._channel_list.currentItem()
            if item is not None:
                channel = str(item.data(Qt.ItemDataRole.UserRole) or channel)
        return self._toggle_channel_name_visibility(channel)

    def _toggle_channel_item_visibility(self, item: QListWidgetItem) -> None:
        channel = str(item.data(Qt.ItemDataRole.UserRole) or item.text() or "")
        self._set_selected_channel(channel)
        self._toggle_channel_name_visibility(channel)

    def _toggle_channel_name_visibility(self, channel: str) -> bool:
        if channel == "RGB":
            new_visible = not all(
                self._channel_visibility.get(key, True)
                for key in ("Red", "Green", "Blue")
            )
            return self._set_channel_visibility("RGB", new_visible)
        elif channel in {"Red", "Green", "Blue", "Alpha"}:
            return self._set_channel_visibility(channel, not self._channel_visibility.get(channel, True))
        return False

    def _update_path_list(self) -> None:
        path_list = getattr(self, "_path_list", None)
        if path_list is None:
            self._update_tool_option_controls()
            return
        active_points = self.canvas.path_point_count() if hasattr(self, "canvas") else 0
        path_strokes = [
            stroke for stroke in (self.canvas.embedded_strokes() if hasattr(self, "canvas") else [])
            if str(getattr(stroke, "source_tool", "") or "") == "path"
        ]
        path_list.blockSignals(True)
        try:
            path_list.clear()
            work_item = QListWidgetItem(f"Work Path  ({active_points} pts)")
            work_item.setIcon(app_icon("path-tool", size=14, color="#DCE6F7"))
            work_item.setData(Qt.ItemDataRole.UserRole, "work-path")
            path_list.addItem(work_item)
            if self._selected_path_item_id == "work-path" or active_points:
                path_list.setCurrentItem(work_item)
            if self.canvas.has_active_selection():
                selection_item = QListWidgetItem(
                    f"Selection Path  marching ants  ({self.canvas.selection_point_count()} pts)"
                )
                selection_item.setIcon(app_icon("path-tool", size=14, color="#FFFFFF"))
                selection_item.setData(Qt.ItemDataRole.UserRole, "selection")
                path_list.addItem(selection_item)
                if self._selected_path_item_id == "selection" and not active_points:
                    path_list.setCurrentItem(selection_item)
            for idx, stroke in enumerate(path_strokes, start=1):
                state = "closed" if bool(getattr(stroke, "closed_path", False)) else "open"
                item = QListWidgetItem(f"Path {idx}  {state}  ({len(stroke.points)} pts)")
                item.setIcon(app_icon("path-tool", size=14, color="#9FB9E7"))
                item.setData(Qt.ItemDataRole.UserRole, f"path:{idx - 1}")
                path_list.addItem(item)
                if self._selected_path_item_id == f"path:{idx - 1}" and not active_points:
                    path_list.setCurrentItem(item)
        finally:
            path_list.blockSignals(False)
        self._update_tool_option_controls()

    def _select_path_item(self, item: QListWidgetItem) -> None:
        value = item.data(Qt.ItemDataRole.UserRole)
        self._selected_path_item_id = str(value or "work-path")
        if value == "work-path":
            self._set_tool("path")
        elif value == "selection":
            self._set_tool("select")
        else:
            self._set_tool("select")

    def _path_points_for_item_id(self, item_id: str | None) -> list[tuple[float, float]]:
        value = str(item_id or "work-path")
        if value == "work-path":
            return self.canvas.path_snapshot() if hasattr(self, "canvas") else []
        if value == "selection":
            return self.canvas.selection_snapshot() if hasattr(self, "canvas") else []
        if value.startswith("path:"):
            try:
                target_index = int(value.split(":", 1)[1])
            except ValueError:
                return []
            path_strokes = [
                stroke
                for stroke in (self.canvas.embedded_strokes() if hasattr(self, "canvas") else [])
                if str(getattr(stroke, "source_tool", "") or "") == "path"
            ]
            if 0 <= target_index < len(path_strokes):
                return [
                    (max(0.0, min(1.0, float(x))), max(0.0, min(1.0, float(y))))
                    for x, y in path_strokes[target_index].points
                ]
        return []

    def _make_selection_from_selected_path(self) -> None:
        item = self._path_list.currentItem() if hasattr(self, "_path_list") else None
        if item is not None:
            self._selected_path_item_id = str(
                item.data(Qt.ItemDataRole.UserRole) or self._selected_path_item_id
            )
        points = self._path_points_for_item_id(self._selected_path_item_id)
        if len(points) < 3:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Path needs at least 3 points")
            return
        self._push_undo_state("Path to selection")
        self.canvas.set_selection_snapshot(points)
        self._selected_path_item_id = "selection"
        self._update_path_list()
        self._set_tool("select")

    def _select_all(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self._push_undo_state("Select all")
        self.canvas.select_all()
        self._selected_path_item_id = "selection"
        self._update_path_list()
        self._set_tool("select")

    def _deselect(self) -> None:
        if not hasattr(self, "canvas") or not self.canvas.has_active_selection():
            return
        self._push_undo_state("Deselect")
        self.canvas.clear_selection()
        self._selected_path_item_id = "work-path"
        self._update_path_list()
        self._set_tool("select")

    def _invert_selection(self) -> None:
        if not hasattr(self, "canvas"):
            return
        self._push_undo_state("Invert selection")
        self.canvas.invert_selection()
        self._selected_path_item_id = "selection"
        self._update_path_list()
        self._set_tool("select")

    def _selection_to_path(self) -> None:
        if not hasattr(self, "canvas"):
            return
        points = self.canvas.selection_snapshot()
        if len(points) < 3:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Selection needs at least 3 points")
            return
        self._push_undo_state("Selection to path")
        path_index = len([
            stroke
            for stroke in self.canvas.embedded_strokes()
            if str(getattr(stroke, "source_tool", "") or "") == "path"
        ])
        stroke = Stroke(
            points=copy.deepcopy(points),
            color=(
                self._pen_color.red(),
                self._pen_color.green(),
                self._pen_color.blue(),
            ),
            opacity=self._pen_opacity,
            width_px=self._pen_width,
            brush_style=self.canvas._pen_style if hasattr(self.canvas, "_pen_style") else "round",
            closed_path=True,
            layer_id=self._active_paint_layer_id,
            source_tool="path",
            start_ms=self._time_ms,
            end_ms=None,
        )
        self.canvas.add_stroke_direct(stroke)
        self._selected_path_item_id = f"path:{path_index}"
        self._update_inspector_counts()
        self._update_path_list()
        self._set_tool("select")

    @staticmethod
    def _normalise_path_points(points) -> list[tuple[float, float]]:
        out: list[tuple[float, float]] = []
        for point in list(points or []):
            if isinstance(point, dict):
                raw_x = point.get("x", point.get("x_norm", 0.0))
                raw_y = point.get("y", point.get("y_norm", 0.0))
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                raw_x, raw_y = point[0], point[1]
            else:
                continue
            try:
                x = float(raw_x)
                y = float(raw_y)
            except Exception:
                continue
            out.append((max(0.0, min(1.0, x)), max(0.0, min(1.0, y))))
        return out

    def _create_path_from_points(
        self,
        points,
        *,
        closed: bool = True,
        make_selection: bool = False,
    ) -> bool:
        norm_points = self._normalise_path_points(points)
        if len(norm_points) < 2:
            return False
        self._push_undo_state("Create path")
        path_index = len([
            stroke
            for stroke in self.canvas.embedded_strokes()
            if str(getattr(stroke, "source_tool", "") or "") == "path"
        ])
        stroke = Stroke(
            points=norm_points,
            color=(
                self._pen_color.red(),
                self._pen_color.green(),
                self._pen_color.blue(),
            ),
            opacity=self._pen_opacity,
            width_px=self._pen_width,
            brush_style=self.canvas._pen_style if hasattr(self.canvas, "_pen_style") else "round",
            closed_path=bool(closed),
            layer_id=self._active_paint_layer_id,
            source_tool="path",
            start_ms=self._time_ms,
            end_ms=None,
        )
        self.canvas.add_stroke_direct(stroke)
        if make_selection and len(norm_points) >= 3:
            self.canvas.set_selection_snapshot(norm_points)
            self._selected_path_item_id = "selection"
        else:
            self._selected_path_item_id = f"path:{path_index}"
        self._update_inspector_counts()
        self._update_path_list()
        self._set_tool("select")
        return True

    def _delete_path_by_id(self, path_id: str | None = None) -> bool:
        target = str(path_id or self._selected_path_item_id or "work-path")
        if target == "work-path":
            if not hasattr(self, "canvas") or self.canvas.path_point_count() <= 0:
                return False
            self._push_undo_state("Delete work path")
            self.canvas.clear_path_preview()
            self._update_path_list()
            return True
        if target == "selection":
            if not hasattr(self, "canvas") or not self.canvas.has_active_selection():
                return False
            self._push_undo_state("Delete selection path")
            self.canvas.clear_selection()
            self._selected_path_item_id = "work-path"
            self._update_path_list()
            return True
        if not target.startswith("path:"):
            return False
        try:
            target_index = int(target.split(":", 1)[1])
        except ValueError:
            return False
        strokes = self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
        path_seen = -1
        absolute_index = -1
        for idx, stroke in enumerate(strokes):
            if str(getattr(stroke, "source_tool", "") or "") != "path":
                continue
            path_seen += 1
            if path_seen == target_index:
                absolute_index = idx
                break
        if absolute_index < 0:
            return False
        self._push_undo_state("Delete path")
        kept = list(strokes)
        kept.pop(absolute_index)
        self.canvas.set_strokes_snapshot(kept)
        self._selected_path_item_id = "work-path"
        self._update_inspector_counts()
        self._update_path_list()
        return True

    def _select_layer_item(self, item: QListWidgetItem) -> None:
        layer_id = item.data(Qt.ItemDataRole.UserRole)
        self._selected_layer_id = str(layer_id) if layer_id is not None else None
        if self._standalone and self._is_paint_layer_id(self._selected_layer_id):
            self._active_paint_layer_id = str(self._selected_layer_id)
            self._sync_canvas_layer_view()
            self._update_layer_controls()
            return
        if self._selected_layer_id == "background":
            self._set_tool("select")
            self._update_layer_controls()
            return
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

    def _on_layer_opacity_changed(self, value: int) -> None:
        layer = self._paint_layer_by_id(self._selected_layer_id) or self._active_paint_layer()
        layer.opacity = max(0, min(100, int(value)))
        if hasattr(self, "_layer_opacity_value"):
            self._layer_opacity_value.setText(f"{layer.opacity}%")
        self._sync_canvas_layer_view()
        self._update_layer_list()

    def _on_layer_blend_changed(self) -> None:
        layer = self._paint_layer_by_id(self._selected_layer_id) or self._active_paint_layer()
        mode = "normal"
        if hasattr(self, "layer_blend_combo"):
            mode = str(self.layer_blend_combo.currentData() or "normal")
        if mode not in {"normal", "multiply", "screen", "overlay"}:
            mode = "normal"
        if getattr(layer, "blend_mode", "normal") == mode:
            return
        self._push_undo_state("Set layer blend mode")
        layer.blend_mode = mode
        self._update_layer_list()

    def _new_paint_layer(self, name: str | None = None) -> None:
        self._push_undo_state("New layer")
        self._paint_layer_serial += 1
        if isinstance(name, bool):
            name = None
        raw_name = str(name or "").strip()
        layer = PaintLayer(
            layer_id=f"paint-layer-{self._paint_layer_serial}",
            name=raw_name[:80] if raw_name else f"Layer {self._paint_layer_serial}",
        )
        self._paint_layers.append(layer)
        self._active_paint_layer_id = layer.layer_id
        self._selected_layer_id = layer.layer_id
        self._sync_canvas_layer_view()
        self._update_inspector_counts()

    def _toggle_selected_layer_visibility(self) -> None:
        layer = self._paint_layer_by_id(self._current_layer_id())
        if layer is None:
            return
        self._push_undo_state("Show layer" if not layer.visible else "Hide layer")
        layer.visible = not layer.visible
        self._sync_canvas_layer_view()
        self._update_layer_list()

    def _toggle_selected_layer_lock(self) -> None:
        if self._selected_layer_id == "background":
            return
        layer = self._paint_layer_by_id(self._current_layer_id()) or self._active_paint_layer()
        self._set_layer_locked(layer.layer_id, not bool(layer.locked))

    def _select_paint_layer_by_id(self, layer_id: str | None) -> PaintLayer | None:
        if not layer_id:
            layer_id = self._active_paint_layer_id
        layer_id = str(layer_id)
        layer = self._paint_layer_by_id(layer_id)
        if layer is None:
            return None
        self._selected_layer_id = layer.layer_id
        self._active_paint_layer_id = layer.layer_id
        if hasattr(self, "_layer_list"):
            for row in range(self._layer_list.count()):
                item = self._layer_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == layer.layer_id:
                    self._layer_list.setCurrentItem(item)
                    break
        self._sync_canvas_layer_view()
        self._update_layer_controls()
        return layer

    def _rename_selected_layer(self) -> None:
        layer = self._paint_layer_by_id(self._current_layer_id())
        if layer is None:
            return
        item = self._layer_list.currentItem() if hasattr(self, "_layer_list") else None
        if item is None or item.data(Qt.ItemDataRole.UserRole) != layer.layer_id:
            self._selected_layer_id = layer.layer_id
            self._update_layer_list()
            item = self._layer_list.currentItem() if hasattr(self, "_layer_list") else None
        if item is not None:
            self._rename_layer_item(item)

    def _rename_layer_to(self, layer_id: str | None, name: str) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        new_name = str(name or "").strip()
        if layer is None or not new_name or layer.name == new_name:
            return False
        self._push_undo_state("Rename layer")
        layer.name = new_name[:80]
        self._selected_layer_id = layer.layer_id
        self._update_inspector_counts()
        return True

    def _set_layer_visible(self, layer_id: str | None, visible: bool) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None or layer.visible == bool(visible):
            return False
        self._push_undo_state("Show layer" if visible else "Hide layer")
        layer.visible = bool(visible)
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        return True

    def _set_layer_locked(self, layer_id: str | None, locked: bool) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None or layer.locked == bool(locked):
            return False
        self._push_undo_state("Lock layer" if locked else "Unlock layer")
        layer.locked = bool(locked)
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        return True

    def _set_layer_opacity_value(self, layer_id: str | None, opacity: int) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None:
            return False
        value = max(0, min(100, int(opacity)))
        if layer.opacity == value:
            return False
        self._push_undo_state("Set layer opacity")
        layer.opacity = value
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        return True

    def _set_layer_blend_mode(self, layer_id: str | None, blend_mode: str) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None:
            return False
        mode = str(blend_mode or "normal").strip().casefold().replace("-", "_")
        if mode not in {"normal", "multiply", "screen", "overlay"}:
            mode = "normal"
        if getattr(layer, "blend_mode", "normal") == mode:
            return False
        self._push_undo_state("Set layer blend mode")
        layer.blend_mode = mode
        self._update_inspector_counts()
        return True

    def _set_channel_visibility(self, channel: str, visible: bool) -> bool:
        channel = str(channel or "RGB").strip()
        if channel not in {"RGB", "Red", "Green", "Blue", "Alpha"}:
            return False
        self._selected_channel = channel
        if channel == "RGB":
            changed = any(
                self._channel_visibility.get(key, True) != bool(visible)
                for key in ("Red", "Green", "Blue")
            )
        else:
            changed = self._channel_visibility.get(channel, True) != bool(visible)
        if not changed:
            return False
        self._push_undo_state("Set channel visibility")
        if channel == "RGB":
            for key in ("Red", "Green", "Blue"):
                self._channel_visibility[key] = bool(visible)
        else:
            self._channel_visibility[channel] = bool(visible)
        self._channel_visibility["RGB"] = all(
            self._channel_visibility.get(key, True)
            for key in ("Red", "Green", "Blue")
        )
        self._update_channel_list()
        self._update_canvas_geometry()
        return True

    def _set_selected_channel(self, channel: str) -> str:
        value = str(channel or "RGB").strip()
        if value not in {"RGB", "Red", "Green", "Blue", "Alpha"}:
            value = "RGB"
        self._selected_channel = value
        if hasattr(self, "_channel_list"):
            for row in range(self._channel_list.count()):
                item = self._channel_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == value:
                    self._channel_list.setCurrentItem(item)
                    break
        return value

    def _copy_selected_channel_image(self) -> bool:
        return self._copy_channel_image(self._selected_channel)

    def _paste_selected_channel_image(self) -> bool:
        return self._paste_channel_image(self._selected_channel)

    def _copy_channel_image(self, channel: str = "RGB") -> bool:
        channel = self._set_selected_channel(channel)
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            return False
        src = self._bg_pixmap_source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        if channel == "RGB":
            QApplication.clipboard().setImage(src)
            return True
        out = QImage(src.width(), src.height(), QImage.Format.Format_ARGB32)
        out.fill(QColor(0, 0, 0, 255))
        for y in range(src.height()):
            for x in range(src.width()):
                color = src.pixelColor(x, y)
                if channel == "Red":
                    value = color.red()
                elif channel == "Green":
                    value = color.green()
                elif channel == "Blue":
                    value = color.blue()
                else:
                    value = color.alpha()
                out.setPixelColor(x, y, QColor(value, value, value, 255))
        QApplication.clipboard().setImage(out)
        return True

    def _paste_channel_image(self, channel: str = "RGB") -> bool:
        channel = self._set_selected_channel(channel)
        clipboard = QApplication.clipboard()
        image = clipboard.image() if clipboard is not None else QImage()
        if image.isNull():
            return False
        self._push_undo_state("Paste channel")
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            width, height = self._canvas_document_size
            self._bg_pixmap_source = create_blank_paint_pixmap(width, height, "transparent")
        dst = self._bg_pixmap_source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        src = image.convertToFormat(QImage.Format.Format_ARGB32).scaled(
            dst.width(),
            dst.height(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        if channel == "RGB":
            for y in range(dst.height()):
                for x in range(dst.width()):
                    src_color = src.pixelColor(x, y)
                    dst_color = dst.pixelColor(x, y)
                    dst_color.setRed(src_color.red())
                    dst_color.setGreen(src_color.green())
                    dst_color.setBlue(src_color.blue())
                    dst.setPixelColor(x, y, dst_color)
        else:
            for y in range(dst.height()):
                for x in range(dst.width()):
                    src_color = src.pixelColor(x, y)
                    value = int((src_color.red() + src_color.green() + src_color.blue()) / 3)
                    dst_color = dst.pixelColor(x, y)
                    if channel == "Red":
                        dst_color.setRed(value)
                    elif channel == "Green":
                        dst_color.setGreen(value)
                    elif channel == "Blue":
                        dst_color.setBlue(value)
                    elif channel == "Alpha":
                        dst_color.setAlpha(value)
                    dst.setPixelColor(x, y, dst_color)
        self._bg_pixmap_source = QPixmap.fromImage(dst)
        self._background_layer_present = True
        self._update_canvas_geometry()
        self._update_channel_list()
        return True

    def _on_canvas_selection_probe(self, kind: str, x_norm: float, y_norm: float) -> None:
        if str(kind or "") == "color":
            self._select_by_color_at(x_norm, y_norm)

    def _select_by_color_at(
        self,
        x_norm: float,
        y_norm: float,
        *,
        tolerance: int | None = None,
    ) -> bool:
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Magic Select needs a raster background")
            return False
        image = self._bg_pixmap_source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        width = max(1, image.width())
        height = max(1, image.height())
        px = max(0, min(width - 1, int(round(float(x_norm) * (width - 1)))))
        py = max(0, min(height - 1, int(round(float(y_norm) * (height - 1)))))
        target = image.pixelColor(px, py)
        tol = max(0, min(100, int(tolerance if tolerance is not None else self._magic_select_tolerance)))
        threshold = max(0, min(255, int(round(tol * 2.55))))
        threshold_sq = threshold * threshold * 3
        step = max(1, int(math.ceil(max(width, height) / 768.0)))
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        for y in range(0, height, step):
            for x in range(0, width, step):
                color = image.pixelColor(x, y)
                if color.alpha() < 4 and target.alpha() >= 4:
                    continue
                dr = color.red() - target.red()
                dg = color.green() - target.green()
                db = color.blue() - target.blue()
                if dr * dr + dg * dg + db * db <= threshold_sq:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, min(width - 1, x + step))
                    max_y = max(max_y, min(height - 1, y + step))
        if max_x < min_x or max_y < min_y:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Magic Select found no similar color")
            return False
        self._push_undo_state("Magic select")
        self.canvas.select_rectangle(
            min_x / width,
            min_y / height,
            max_x / width,
            max_y / height,
            shape="rect",
            aspect="free",
        )
        self._selected_path_item_id = "selection"
        self._update_path_list()
        self._set_tool("magic_select")
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                f"Magic Select tolerance {tol}: selected similar color bounds"
            )
        return True

    def _selection_path_for_document(self, width: int, height: int) -> QPainterPath | None:
        if not hasattr(self, "canvas") or not self.canvas.has_active_selection():
            return None
        points = self.canvas.selection_snapshot()
        if len(points) < 3:
            return None
        path = QPainterPath()
        path.moveTo(points[0][0] * width, points[0][1] * height)
        for x, y in points[1:]:
            path.lineTo(float(x) * width, float(y) * height)
        path.closeSubpath()
        if self.canvas.selection_inverted():
            full = QPainterPath()
            full.addRect(QRectF(0, 0, width, height))
            return full.subtracted(path)
        return path

    def _fill_document(
        self,
        style: str = "solid",
        *,
        color1: str | QColor | None = None,
        color2: str | QColor | None = None,
    ) -> bool:
        width, height = self._canvas_document_size
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            self._bg_pixmap_source = create_blank_paint_pixmap(width, height, "transparent")
        self._push_undo_state(f"{str(style or 'solid').title()} fill")
        pixmap = QPixmap(self._bg_pixmap_source)
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            selection_path = self._selection_path_for_document(pixmap.width(), pixmap.height())
            if selection_path is not None:
                painter.setClipPath(selection_path)
            base = QColor(color1) if color1 is not None else QColor(self._pen_color)
            if not base.isValid():
                base = QColor(self._pen_color)
            accent = QColor(color2) if color2 is not None else QColor(base).lighter(136)
            if not accent.isValid():
                accent = QColor(base).lighter(136)
            mode = str(style or "solid").strip().casefold()
            rect = QRectF(0, 0, pixmap.width(), pixmap.height())
            if mode == "gradient":
                gradient = QLinearGradient(0, 0, pixmap.width(), pixmap.height())
                gradient.setColorAt(0.0, accent)
                gradient.setColorAt(0.52, base)
                gradient.setColorAt(1.0, QColor(base).darker(132))
                painter.fillRect(rect, QBrush(gradient))
            elif mode == "pattern":
                painter.fillRect(rect, QColor(base).darker(118))
                line_pen = QPen(QColor(accent), max(2, int(max(width, height) / 360)))
                line_pen.setCosmetic(True)
                painter.setPen(line_pen)
                spacing = max(14, int(max(width, height) / 80))
                for offset in range(-pixmap.height(), pixmap.width() + pixmap.height(), spacing):
                    painter.drawLine(
                        QPointF(offset, pixmap.height()),
                        QPointF(offset + pixmap.height(), 0),
                    )
            else:
                painter.fillRect(rect, base)
        finally:
            painter.end()
        self._bg_pixmap_source = pixmap
        self._background_layer_present = True
        self._update_canvas_geometry()
        self._update_channel_list()
        if hasattr(self, "_tool_status_label"):
            target = "selection" if self.canvas.has_active_selection() else "canvas"
            self._tool_status_label.setText(f"{str(style or 'solid').title()} filled {target}")
        return True

    def _mask_points_from_channel(
        self,
        channel: str,
        *,
        threshold: int = 8,
    ) -> list[tuple[float, float]]:
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            return []
        image = self._bg_pixmap_source.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        width = max(1, image.width())
        height = max(1, image.height())
        step = max(1, int(math.ceil(max(width, height) / 768.0)))
        min_x = width
        min_y = height
        max_x = -1
        max_y = -1
        channel_name = str(channel or "Alpha")
        for y in range(0, height, step):
            for x in range(0, width, step):
                color = image.pixelColor(x, y)
                if channel_name == "Red":
                    value = color.red()
                elif channel_name == "Green":
                    value = color.green()
                elif channel_name == "Blue":
                    value = color.blue()
                elif channel_name == "RGB":
                    value = max(color.red(), color.green(), color.blue())
                else:
                    value = color.alpha()
                if value > threshold:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, min(width - 1, x + step))
                    max_y = max(max_y, min(height - 1, y + step))
        if max_x < min_x or max_y < min_y:
            return []
        return [
            (min_x / width, min_y / height),
            (max_x / width, min_y / height),
            (max_x / width, max_y / height),
            (min_x / width, max_y / height),
        ]

    def _create_layer_mask(
        self,
        mask_type: str = "selection",
        layer_id: str | None = None,
    ) -> bool:
        if layer_id and not self._select_paint_layer_by_id(layer_id):
            return False
        layer = self._paint_layer_by_id(self._current_layer_id()) or self._active_paint_layer()
        if layer.locked:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(tr("paint.layer.locked_status"))
            return False
        mode = str(mask_type or "selection").strip().casefold().replace("-", "_")
        points: list[tuple[float, float]]
        if mode in {"white", "reveal_all", "all"}:
            points = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
        elif mode in {"path", "from_path"}:
            points = self._path_points_for_item_id(self._selected_path_item_id)
        elif mode in {"channel", "from_channel"}:
            points = self._mask_points_from_channel(self._selected_channel)
        elif mode in {"alpha", "layer_alpha", "from_alpha"}:
            points = self._mask_points_from_channel("Alpha")
        else:
            points = self.canvas.selection_snapshot() if hasattr(self, "canvas") else []
        if len(points) < 3:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(f"Layer mask needs {mode} pixels or points")
            return False
        self._push_undo_state("Layer mask")
        layer.mask = copy.deepcopy(points)
        layer.mask_enabled = True
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"Layer mask from {mode}")
        return True

    def _selection_bounds(self) -> tuple[float, float, float, float] | None:
        if not hasattr(self, "canvas") or not self.canvas.has_active_selection():
            return None
        points = self.canvas.selection_snapshot()
        if len(points) < 3:
            return None
        xs = [max(0.0, min(1.0, float(x))) for x, _y in points]
        ys = [max(0.0, min(1.0, float(y))) for _x, y in points]
        left, right = min(xs), max(xs)
        top, bottom = min(ys), max(ys)
        if right - left <= 0.001 or bottom - top <= 0.001:
            return None
        return left, top, right, bottom

    @staticmethod
    def _remap_points_to_rect(
        points: list[tuple[float, float]],
        bounds: tuple[float, float, float, float],
    ) -> list[tuple[float, float]]:
        left, top, right, bottom = bounds
        width = max(0.0001, right - left)
        height = max(0.0001, bottom - top)
        return [
            (
                max(0.0, min(1.0, (float(x) - left) / width)),
                max(0.0, min(1.0, (float(y) - top) / height)),
            )
            for x, y in points
        ]

    def _remap_objects_to_rect(self, bounds: tuple[float, float, float, float]) -> None:
        left, top, right, bottom = bounds
        width = max(0.0001, right - left)
        height = max(0.0001, bottom - top)
        for bubble in getattr(self, "_bubbles", []):
            bubble.x_norm = max(0.0, min(1.0, (float(bubble.x_norm) - left) / width))
            bubble.y_norm = max(0.0, min(1.0, (float(bubble.y_norm) - top) / height))
            bubble.width_norm = max(0.01, min(1.0, float(bubble.width_norm) / width))
            bubble.height_norm = max(0.01, min(1.0, float(bubble.height_norm) / height))
        for sticker in getattr(self, "_stickers", []):
            sticker.x_norm = max(0.0, min(1.0, (float(sticker.x_norm) - left) / width))
            sticker.y_norm = max(0.0, min(1.0, (float(sticker.y_norm) - top) / height))
            sticker.width_norm = max(0.01, min(1.0, float(sticker.width_norm) / width))
            sticker.height_norm = max(0.01, min(1.0, float(sticker.height_norm) / height))

    def _crop_to_selection(self) -> bool:
        bounds = self._selection_bounds()
        if bounds is None:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Crop needs an active selection")
            return False
        self._push_undo_state("Crop")
        left, top, right, bottom = bounds
        old_w, old_h = self._canvas_document_size
        crop_rect = QRect(
            max(0, min(old_w - 1, int(round(left * old_w)))),
            max(0, min(old_h - 1, int(round(top * old_h)))),
            max(1, min(old_w, int(round((right - left) * old_w)))),
            max(1, min(old_h, int(round((bottom - top) * old_h)))),
        )
        self._bg_pixmap_source = self._bg_pixmap_source.copy(crop_rect)
        self._canvas_document_size = (crop_rect.width(), crop_rect.height())
        strokes = self.canvas.embedded_strokes()
        for stroke in strokes:
            stroke.points = self._remap_points_to_rect(stroke.points, bounds)
        for layer in self._paint_layers:
            if len(getattr(layer, "mask", []) or []) >= 3:
                layer.mask = self._remap_points_to_rect(layer.mask, bounds)
        self._remap_objects_to_rect(bounds)
        self.canvas.set_strokes_snapshot(strokes)
        self.canvas.clear_selection()
        self._selected_path_item_id = "work-path"
        self._canvas_pan = QPoint(0, 0)
        self._update_canvas_geometry()
        self._update_inspector_counts()
        return True

    def _resize_image_document(self, width: int, height: int) -> bool:
        width = max(64, min(16384, int(width or 0)))
        height = max(64, min(16384, int(height or 0)))
        if (width, height) == tuple(self._canvas_document_size):
            return False
        self._push_undo_state("Image size")
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            old_w, old_h = self._canvas_document_size
            self._bg_pixmap_source = create_blank_paint_pixmap(old_w, old_h, "transparent")
        self._bg_pixmap_source = self._bg_pixmap_source.scaled(
            width,
            height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._canvas_document_size = (width, height)
        self._canvas_pan = QPoint(0, 0)
        self._update_canvas_geometry()
        self._update_inspector_counts()
        return True

    def _resize_canvas_document(
        self,
        width: int,
        height: int,
        *,
        background: str = "transparent",
    ) -> bool:
        width = max(64, min(16384, int(width or 0)))
        height = max(64, min(16384, int(height or 0)))
        old_w, old_h = self._canvas_document_size
        if (width, height) == (old_w, old_h):
            return False
        self._push_undo_state("Canvas size")
        if not self._bg_pixmap_source or self._bg_pixmap_source.isNull():
            self._bg_pixmap_source = create_blank_paint_pixmap(old_w, old_h, "transparent")
        new_pixmap = create_blank_paint_pixmap(width, height, background)
        offset_x = (width - old_w) / 2.0
        offset_y = (height - old_h) / 2.0
        painter = QPainter(new_pixmap)
        try:
            painter.drawPixmap(int(round(offset_x)), int(round(offset_y)), self._bg_pixmap_source)
        finally:
            painter.end()
        self._bg_pixmap_source = new_pixmap
        self._canvas_document_size = (width, height)
        strokes = self.canvas.embedded_strokes()
        for stroke in strokes:
            stroke.points = [
                (
                    max(0.0, min(1.0, (float(x) * old_w + offset_x) / width)),
                    max(0.0, min(1.0, (float(y) * old_h + offset_y) / height)),
                )
                for x, y in stroke.points
            ]
        for layer in self._paint_layers:
            if len(getattr(layer, "mask", []) or []) >= 3:
                layer.mask = [
                    (
                        max(0.0, min(1.0, (float(x) * old_w + offset_x) / width)),
                        max(0.0, min(1.0, (float(y) * old_h + offset_y) / height)),
                    )
                    for x, y in layer.mask
                ]
        self.canvas.set_strokes_snapshot(strokes)
        selection = self.canvas.selection_snapshot()
        if len(selection) >= 3:
            self.canvas.set_selection_snapshot([
                (
                    max(0.0, min(1.0, (float(x) * old_w + offset_x) / width)),
                    max(0.0, min(1.0, (float(y) * old_h + offset_y) / height)),
                )
                for x, y in selection
            ])
        self._canvas_pan = QPoint(0, 0)
        self._update_canvas_geometry()
        self._update_inspector_counts()
        return True

    def _flip_canvas(self, *, horizontal: bool = True) -> bool:
        self._push_undo_state("Flip canvas")
        image = self._bg_pixmap_source.toImage()
        if hasattr(image, "flipped"):
            orientation = (
                Qt.Orientation.Horizontal
                if horizontal
                else Qt.Orientation.Vertical
            )
            flipped = image.flipped(orientation)
        else:
            flipped = image.mirrored(bool(horizontal), not bool(horizontal))
        self._bg_pixmap_source = QPixmap.fromImage(flipped)
        strokes = self.canvas.embedded_strokes()
        for stroke in strokes:
            stroke.points = [
                (
                    max(0.0, min(1.0, 1.0 - float(x) if horizontal else float(x))),
                    max(0.0, min(1.0, float(y) if horizontal else 1.0 - float(y))),
                )
                for x, y in stroke.points
            ]
        for layer in self._paint_layers:
            if len(getattr(layer, "mask", []) or []) >= 3:
                layer.mask = [
                    (
                        max(0.0, min(1.0, 1.0 - float(x) if horizontal else float(x))),
                        max(0.0, min(1.0, float(y) if horizontal else 1.0 - float(y))),
                    )
                    for x, y in layer.mask
                ]
        self.canvas.set_strokes_snapshot(strokes)
        selection = self.canvas.selection_snapshot()
        if len(selection) >= 3:
            self.canvas.set_selection_snapshot([
                (
                    max(0.0, min(1.0, 1.0 - float(x) if horizontal else float(x))),
                    max(0.0, min(1.0, float(y) if horizontal else 1.0 - float(y))),
                )
                for x, y in selection
            ])
        for bubble in getattr(self, "_bubbles", []):
            if horizontal:
                bubble.x_norm = max(0.0, min(1.0, 1.0 - float(bubble.x_norm) - float(bubble.width_norm)))
            else:
                bubble.y_norm = max(0.0, min(1.0, 1.0 - float(bubble.y_norm) - float(bubble.height_norm)))
        for sticker in getattr(self, "_stickers", []):
            if horizontal:
                sticker.x_norm = max(0.0, min(1.0, 1.0 - float(sticker.x_norm) - float(sticker.width_norm)))
            else:
                sticker.y_norm = max(0.0, min(1.0, 1.0 - float(sticker.y_norm) - float(sticker.height_norm)))
        self._clear_path_preview()
        self._update_canvas_geometry()
        self._update_inspector_counts()
        return True

    def _prompt_image_size(self) -> None:
        width, ok = QInputDialog.getInt(
            self,
            "Image Size",
            "Width",
            int(self._canvas_document_size[0]),
            64,
            16384,
        )
        if not ok:
            return
        height, ok = QInputDialog.getInt(
            self,
            "Image Size",
            "Height",
            int(self._canvas_document_size[1]),
            64,
            16384,
        )
        if ok:
            self._resize_image_document(width, height)

    def _prompt_canvas_size(self) -> None:
        width, ok = QInputDialog.getInt(
            self,
            "Canvas Size",
            "Width",
            int(self._canvas_document_size[0]),
            64,
            16384,
        )
        if not ok:
            return
        height, ok = QInputDialog.getInt(
            self,
            "Canvas Size",
            "Height",
            int(self._canvas_document_size[1]),
            64,
            16384,
        )
        if ok:
            self._resize_canvas_document(width, height)

    def _mask_selected_layer_from_selection(self) -> bool:
        return self._create_layer_mask("selection")

    def _mask_selected_layer_from_path(self) -> bool:
        item = self._path_list.currentItem() if hasattr(self, "_path_list") else None
        if item is not None:
            self._selected_path_item_id = str(
                item.data(Qt.ItemDataRole.UserRole) or self._selected_path_item_id
            )
        return self._create_layer_mask("path")

    def _install_edit_shortcuts(self) -> None:
        shortcuts = (
            ("Ctrl+C", self._copy_selected_layer),
            ("Ctrl+X", self._cut_selected_layer),
            ("Ctrl+V", self._paste_layer_clipboard),
            ("Delete", self._delete_selected_layer),
            ("Backspace", self._delete_selected_layer),
            ("Ctrl+D", self._deselect),
            ("Ctrl+J", self._duplicate_selected_layer),
            ("Ctrl+A", self._select_all),
            ("Ctrl+Shift+I", self._invert_selection),
            ("Q", lambda: self._set_quick_mask_enabled(not self._quick_mask_enabled)),
            ("Ctrl++", self._zoom_in),
            ("Ctrl+=", self._zoom_in),
            ("Ctrl+-", self._zoom_out),
            ("Ctrl+0", self._zoom_fit),
            ("Ctrl+1", self._zoom_fit),
            ("Return", self._apply_crop_if_crop_tool),
            ("Enter", self._apply_crop_if_crop_tool),
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
        new_action = menu.addAction("New Layer")
        visibility_action = menu.addAction("Toggle Visibility")
        menu.addSeparator()
        copy_action = menu.addAction("Copy")
        cut_action = menu.addAction("Cut")
        paste_action = menu.addAction("Paste")
        duplicate_action = menu.addAction("Duplicate")
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        selected = self._current_layer_id()
        selected_background = selected == "background" and self._background_layer_present
        has_selection = selected is not None and not selected_background
        is_paint_layer = self._is_paint_layer_id(selected)
        visibility_action.setEnabled(is_paint_layer)
        copy_action.setEnabled(has_selection)
        cut_action.setEnabled(has_selection)
        duplicate_action.setEnabled(has_selection)
        delete_action.setEnabled(
            selected_background
            or (has_selection and (not is_paint_layer or len(self._paint_layers) > 1))
        )
        paste_action.setEnabled(
            self._paint_clipboard is not None or self._system_clipboard_has_paint_payload()
        )
        chosen = menu.exec(self._layer_list.mapToGlobal(pos))
        if chosen is new_action:
            self._new_paint_layer()
        elif chosen is visibility_action:
            self._toggle_selected_layer_visibility()
        elif chosen is copy_action:
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
        if self._standalone and not self._selected_layer_id:
            self._selected_layer_id = self._active_paint_layer_id
        return self._selected_layer_id

    def _copy_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        payload = self._payload_for_layer(self._current_layer_id())
        if payload is not None:
            self._paint_clipboard = payload
            self._write_payload_to_system_clipboard(payload)

    def _cut_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        layer_id = self._current_layer_id()
        payload = self._payload_for_layer(layer_id)
        if payload is None:
            return
        self._paint_clipboard = payload
        self._write_payload_to_system_clipboard(payload)
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
        payload = self._payload_from_system_clipboard()
        if payload is None:
            payload = self._paint_clipboard
        else:
            self._paint_clipboard = payload
        if payload is None:
            return
        self._paste_payload(payload)

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

    def _system_clipboard_has_paint_payload(self) -> bool:
        try:
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData() if clipboard is not None else None
            return bool(mime is not None and mime.hasFormat(PAINT_CLIPBOARD_MIME))
        except Exception:
            return False

    def _write_payload_to_system_clipboard(self, payload: dict) -> None:
        document = self._payload_to_clipboard_document(payload)
        if document is None:
            return
        try:
            encoded = json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            mime = QMimeData()
            mime.setData(PAINT_CLIPBOARD_MIME, QByteArray(encoded))
            mime.setText(f"TigerCapture Paint {document.get('kind', 'payload')}")
            QApplication.clipboard().setMimeData(mime)
        except Exception:
            return

    def _payload_from_system_clipboard(self) -> dict | None:
        try:
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData() if clipboard is not None else None
            if mime is None or not mime.hasFormat(PAINT_CLIPBOARD_MIME):
                return None
            raw = bytes(mime.data(PAINT_CLIPBOARD_MIME))
            document = json.loads(raw.decode("utf-8"))
        except Exception:
            return None
        return self._payload_from_clipboard_document(document)

    def _payload_to_clipboard_document(self, payload: dict) -> dict | None:
        kind = str(payload.get("kind") or "")
        body: dict
        if kind == "paint_layer":
            layer = payload.get("layer")
            body = {
                "layer": asdict(layer) if isinstance(layer, PaintLayer) else None,
                "strokes": [
                    asdict(stroke)
                    for stroke in payload.get("strokes") or []
                    if isinstance(stroke, Stroke)
                ],
            }
        elif kind == "strokes":
            body = {
                "strokes": [
                    asdict(stroke)
                    for stroke in payload.get("strokes") or []
                    if isinstance(stroke, Stroke)
                ],
            }
        elif kind == "bubble":
            bubble = payload.get("bubble")
            body = {"bubble": asdict(bubble) if isinstance(bubble, SpeechBubble) else None}
        elif kind == "sticker":
            sticker = payload.get("sticker")
            body = {"sticker": asdict(sticker) if isinstance(sticker, Sticker) else None}
        else:
            return None
        return {
            "schema": PAINT_CLIPBOARD_SCHEMA,
            "kind": kind,
            "payload": body,
        }

    def _payload_from_clipboard_document(self, document: dict) -> dict | None:
        if not isinstance(document, dict):
            return None
        if document.get("schema") != PAINT_CLIPBOARD_SCHEMA:
            return None
        kind = str(document.get("kind") or "")
        body = document.get("payload")
        if not isinstance(body, dict):
            return None
        if kind == "paint_layer":
            layer = self._paint_layer_from_clipboard_dict(body.get("layer") or {})
            return {
                "kind": "paint_layer",
                "layer": layer,
                "strokes": self._strokes_from_clipboard_list(body.get("strokes")),
            }
        if kind == "strokes":
            strokes = self._strokes_from_clipboard_list(body.get("strokes"))
            return {"kind": "strokes", "strokes": strokes} if strokes else None
        if kind == "bubble" and isinstance(body.get("bubble"), dict):
            return {"kind": "bubble", "bubble": self._bubble_from_clipboard_dict(body["bubble"])}
        if kind == "sticker" and isinstance(body.get("sticker"), dict):
            return {"kind": "sticker", "sticker": self._sticker_from_clipboard_dict(body["sticker"])}
        return None

    @staticmethod
    def _clipboard_int(value, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clipboard_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _strokes_from_clipboard_list(self, rows) -> list[Stroke]:
        if not isinstance(rows, list):
            return []
        strokes: list[Stroke] = []
        for row in rows:
            if isinstance(row, dict):
                strokes.append(self._stroke_from_clipboard_dict(row))
        return strokes

    def _stroke_from_clipboard_dict(self, row: dict) -> Stroke:
        points: list[tuple[float, float]] = []
        for point in row.get("points") or []:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((
                    max(0.0, min(1.0, self._clipboard_float(point[0]))),
                    max(0.0, min(1.0, self._clipboard_float(point[1]))),
                ))
        color_raw = row.get("color") or (255, 50, 50)
        if not isinstance(color_raw, (list, tuple)) or len(color_raw) < 3:
            color_raw = (255, 50, 50)
        color = tuple(
            max(0, min(255, self._clipboard_int(color_raw[idx], 0)))
            for idx in range(3)
        )
        end_ms = row.get("end_ms")
        return Stroke(
            points=points,
            color=color,
            opacity=max(0, min(255, self._clipboard_int(row.get("opacity"), 255))),
            width_px=max(0.1, self._clipboard_float(row.get("width_px"), 4.0)),
            brush_style=str(row.get("brush_style") or "round"),
            closed_path=bool(row.get("closed_path", False)),
            layer_id=str(row.get("layer_id") or "paint-layer-1"),
            source_tool=str(row.get("source_tool") or "pen"),
            start_ms=self._clipboard_int(row.get("start_ms"), 0),
            end_ms=None if end_ms is None else self._clipboard_int(end_ms, 0),
        )

    def _paint_layer_from_clipboard_dict(self, row: dict) -> PaintLayer:
        if not isinstance(row, dict):
            row = {}
        return PaintLayer(
            layer_id=str(row.get("layer_id") or "paint-layer-1"),
            name=str(row.get("name") or "Layer"),
            visible=bool(row.get("visible", True)),
            opacity=max(0, min(100, self._clipboard_int(row.get("opacity"), 100))),
            locked=bool(row.get("locked", False)),
            blend_mode=str(row.get("blend_mode") or "normal"),
            mask=self._normalise_path_points(row.get("mask") or []),
            mask_enabled=bool(row.get("mask_enabled", False)),
        )

    def _bubble_from_clipboard_dict(self, row: dict) -> "SpeechBubble":
        return SpeechBubble(
            x_norm=max(0.0, min(1.0, self._clipboard_float(row.get("x_norm"), 0.1))),
            y_norm=max(0.0, min(1.0, self._clipboard_float(row.get("y_norm"), 0.1))),
            width_norm=max(0.01, min(1.0, self._clipboard_float(row.get("width_norm"), 0.35))),
            height_norm=max(0.01, min(1.0, self._clipboard_float(row.get("height_norm"), 0.18))),
            text=str(row.get("text") or ""),
            start_ms=self._clipboard_int(row.get("start_ms"), 0),
            tail=str(row.get("tail") or "left"),
        )

    def _sticker_from_clipboard_dict(self, row: dict) -> "Sticker":
        return Sticker(
            png_path=str(row.get("png_path") or ""),
            x_norm=max(0.0, min(1.0, self._clipboard_float(row.get("x_norm"), 0.15))),
            y_norm=max(0.0, min(1.0, self._clipboard_float(row.get("y_norm"), 0.15))),
            width_norm=max(0.01, min(1.0, self._clipboard_float(row.get("width_norm"), 0.2))),
            height_norm=max(0.01, min(1.0, self._clipboard_float(row.get("height_norm"), 0.2))),
            opacity=max(0.0, min(100.0, self._clipboard_float(row.get("opacity"), 100.0))),
            rotation_deg=self._clipboard_float(row.get("rotation_deg"), 0.0),
            start_ms=self._clipboard_int(row.get("start_ms"), 0),
            end_ms=self._clipboard_int(row.get("end_ms"), -1),
            z_index=self._clipboard_int(row.get("z_index"), 0),
        )

    def _payload_for_layer(self, layer_id: str | None) -> dict | None:
        if not layer_id:
            return None
        if self._is_paint_layer_id(layer_id):
            strokes = [
                copy.deepcopy(stroke)
                for stroke in self.canvas.embedded_strokes()
                if str(getattr(stroke, "layer_id", "") or "paint-layer-1") == layer_id
            ]
            layer = self._paint_layer_by_id(layer_id)
            return {
                "kind": "paint_layer",
                "layer": copy.deepcopy(layer),
                "strokes": strokes,
            }
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
        if kind == "paint_layer":
            source_layer = payload.get("layer")
            self._paint_layer_serial += 1
            name = getattr(source_layer, "name", "Layer")
            layer = PaintLayer(
                layer_id=f"paint-layer-{self._paint_layer_serial}",
                name=f"{name} copy" if "copy" not in str(name).lower() else f"Layer {self._paint_layer_serial}",
                visible=bool(getattr(source_layer, "visible", True)),
                opacity=max(0, min(100, int(getattr(source_layer, "opacity", 100)))),
                locked=bool(getattr(source_layer, "locked", False)),
                blend_mode=str(getattr(source_layer, "blend_mode", "normal") or "normal"),
                mask=copy.deepcopy(getattr(source_layer, "mask", []) or []),
                mask_enabled=bool(getattr(source_layer, "mask_enabled", False)),
            )
            self._paint_layers.append(layer)
            pasted = copy.deepcopy(payload.get("strokes") or [])
            for stroke in pasted:
                stroke.points = [
                    (max(0.0, min(1.0, x + 0.025)), max(0.0, min(1.0, y + 0.025)))
                    for x, y in stroke.points
                ]
                stroke.layer_id = layer.layer_id
                stroke.start_ms = self._time_ms
                self.canvas.add_stroke_direct(stroke)
            self._active_paint_layer_id = layer.layer_id
            self._selected_layer_id = layer.layer_id
        elif kind == "strokes":
            pasted = copy.deepcopy(payload.get("strokes") or [])
            for stroke in pasted:
                stroke.points = [
                    (max(0.0, min(1.0, x + 0.025)), max(0.0, min(1.0, y + 0.025)))
                    for x, y in stroke.points
                ]
                if self._standalone:
                    stroke.layer_id = self._active_paint_layer_id
                stroke.start_ms = self._time_ms
                self.canvas.add_stroke_direct(stroke)
            self._selected_layer_id = self._active_paint_layer_id if self._standalone else "strokes"
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
        if not self._standalone:
            self._set_tool("select")

    def _delete_layer(self, layer_id: str | None) -> None:
        if not layer_id:
            return
        if layer_id == "background":
            if not self._standalone or not self._background_layer_present:
                return
            self._push_undo_state()
            self._background_layer_present = False
            self._selected_layer_id = self._active_paint_layer_id
            self._update_canvas_geometry()
            self._update_inspector_counts()
            return
        if self._is_paint_layer_id(layer_id):
            if len(self._paint_layers) <= 1:
                return
            target_layer = self._paint_layer_by_id(layer_id)
            if target_layer is not None and target_layer.locked:
                if hasattr(self, "_tool_status_label"):
                    self._tool_status_label.setText(tr("paint.layer.locked_status"))
                return
            self._push_undo_state()
            self.canvas.clear_strokes_direct(layer_id)
            self._paint_layers = [
                layer for layer in self._paint_layers if layer.layer_id != layer_id
            ]
            next_layer = self._paint_layers[-1]
            self._active_paint_layer_id = next_layer.layer_id
            self._selected_layer_id = next_layer.layer_id
            self._sync_canvas_layer_view()
            self._update_inspector_counts()
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

    def eventFilter(self, obj, event) -> bool:
        canvas_widgets = (
            getattr(self, "_canvas_host", None),
            getattr(self, "_bg_label", None),
            getattr(self, "canvas", None),
        )
        if obj not in canvas_widgets:
            return super().eventFilter(obj, event)
        event_type = event.type()
        if event_type == QEvent.Type.ContextMenu:
            try:
                self._show_canvas_context_menu(event.globalPos())
                event.accept()
                return True
            except Exception:
                return False
        if event_type == QEvent.Type.MouseButtonPress:
            button = event.button()
            should_pan = (
                button == Qt.MouseButton.MiddleButton
                or (
                    button == Qt.MouseButton.LeftButton
                    and hasattr(self, "pan_btn")
                    and self.pan_btn.isChecked()
                )
            )
            if should_pan:
                self._begin_canvas_pan(obj, event.position().toPoint())
                event.accept()
                return True
        if event_type == QEvent.Type.MouseMove and self._canvas_pan_drag_start is not None:
            self._update_canvas_pan_drag(obj, event.position().toPoint())
            event.accept()
            return True
        if event_type == QEvent.Type.MouseButtonRelease and self._canvas_pan_drag_start is not None:
            self._finish_canvas_pan()
            event.accept()
            return True
        return super().eventFilter(obj, event)

    def _point_in_canvas_host(self, obj, point: QPoint) -> QPoint:
        host = getattr(self, "_canvas_host", None)
        if host is None:
            return QPoint(point)
        if obj is host:
            return QPoint(point)
        try:
            return obj.mapTo(host, point)
        except Exception:
            return QPoint(point)

    def _begin_canvas_pan(self, obj, point: QPoint) -> None:
        self._canvas_pan_drag_start = self._point_in_canvas_host(obj, point)
        self._canvas_pan_drag_origin = QPoint(getattr(self, "_canvas_pan", QPoint(0, 0)))
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            host.setCursor(Qt.CursorShape.ClosedHandCursor)

    def _update_canvas_pan_drag(self, obj, point: QPoint) -> None:
        if self._canvas_pan_drag_start is None:
            return
        current = self._point_in_canvas_host(obj, point)
        delta = current - self._canvas_pan_drag_start
        self._set_canvas_pan(self._canvas_pan_drag_origin + delta)

    def _finish_canvas_pan(self) -> None:
        self._canvas_pan_drag_start = None
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            host.setCursor(
                Qt.CursorShape.OpenHandCursor
                if hasattr(self, "pan_btn") and self.pan_btn.isChecked()
                else Qt.CursorShape.ArrowCursor
            )

    def _set_canvas_pan(self, pan: QPoint) -> None:
        self._canvas_pan = QPoint(pan)
        self._update_canvas_geometry()

    def _pan_canvas_by(self, delta: QPoint) -> None:
        self._set_canvas_pan(QPoint(getattr(self, "_canvas_pan", QPoint(0, 0))) + delta)

    def _reset_canvas_pan(self) -> None:
        self._set_canvas_pan(QPoint(0, 0))

    @staticmethod
    def _clamped_canvas_pan(pan: QPoint, *, canvas_size: QSize, host_size: QSize) -> QPoint:
        max_x = max(0, (canvas_size.width() - host_size.width()) // 2)
        max_y = max(0, (canvas_size.height() - host_size.height()) // 2)
        return QPoint(
            max(-max_x, min(max_x, pan.x())),
            max(-max_y, min(max_y, pan.y())),
        )

    def _build_canvas_context_menu(self) -> QMenu:
        menu = QMenu(self)
        copy_action = menu.addAction("Copy")
        cut_action = menu.addAction("Cut")
        paste_action = menu.addAction("Paste")
        menu.addSeparator()
        select_all_action = menu.addAction("Select All")
        deselect_action = menu.addAction("Deselect")
        crop_action = menu.addAction("Crop To Selection")
        fill_action = menu.addAction("Fill")
        gradient_action = menu.addAction("Gradient Fill")
        pattern_action = menu.addAction("Pattern Fill")
        menu.addSeparator()
        zoom_in_action = menu.addAction("Zoom In")
        zoom_out_action = menu.addAction("Zoom Out")
        zoom_fit_action = menu.addAction("Fit")
        reset_pan_action = menu.addAction("Reset Pan")

        selected = self._current_layer_id()
        selected_background = selected == "background" and self._background_layer_present
        has_selection = selected is not None and not selected_background
        copy_action.setEnabled(has_selection)
        cut_action.setEnabled(has_selection)
        paste_action.setEnabled(
            self._paint_clipboard is not None or self._system_clipboard_has_paint_payload()
        )
        copy_action.triggered.connect(self._copy_selected_layer)
        cut_action.triggered.connect(self._cut_selected_layer)
        paste_action.triggered.connect(self._paste_layer_clipboard)
        select_all_action.triggered.connect(self._select_all)
        deselect_action.setEnabled(bool(hasattr(self, "canvas") and self.canvas.has_active_selection()))
        deselect_action.triggered.connect(self._deselect)
        crop_action.setEnabled(bool(self._selection_bounds()))
        crop_action.triggered.connect(self._crop_to_selection)
        fill_action.triggered.connect(lambda: self._fill_document("solid"))
        gradient_action.triggered.connect(lambda: self._fill_document("gradient"))
        pattern_action.triggered.connect(lambda: self._fill_document("pattern"))
        zoom_in_action.triggered.connect(self._zoom_in)
        zoom_out_action.triggered.connect(self._zoom_out)
        zoom_fit_action.triggered.connect(self._zoom_fit)
        reset_pan_action.triggered.connect(self._reset_canvas_pan)
        return menu

    def _show_canvas_context_menu(self, global_pos: QPoint) -> None:
        menu = self._build_canvas_context_menu()
        menu.exec(global_pos)

    # ---------- layout sync ----------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_canvas_geometry()

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom_in()
            elif delta < 0:
                self._zoom_out()
            event.accept()
            return
        super().wheelEvent(event)

    def _update_canvas_geometry(self) -> None:
        host = self._canvas_host
        if host is None:
            return
        hw, hh = host.width(), host.height()
        if hw <= 0 or hh <= 0:
            return

        # Scale the display background to fit host; transparent/no background
        # uses a Photoshop-style checkerboard but still exports as alpha.
        display_bg = self._display_background_pixmap()
        if display_bg and not display_bg.isNull():
            bg_scaled = display_bg.scaled(
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
        pan = self._clamped_canvas_pan(
            QPoint(getattr(self, "_canvas_pan", QPoint(0, 0))),
            canvas_size=QSize(bw, bh),
            host_size=QSize(hw, hh),
        )
        self._canvas_pan = pan
        bx = (hw - bw) // 2 + pan.x()
        by = (hh - bh) // 2 + pan.y()
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

    def export_png_to_path(
        self,
        path: str | Path,
        *,
        include_background: bool = True,
        width: int = 0,
        height: int = 0,
    ) -> dict:
        bg = self._export_background_pixmap() if include_background else None
        target_size = (
            (max(1, int(width)), max(1, int(height)))
            if int(width or 0) > 0 and int(height or 0) > 0
            else _paint_export_size(bg, fallback=self._canvas_document_size)
        )
        width_scale = target_size[0] / max(1, self.canvas.width())
        return export_paint_png(
            path,
            background_pixmap=bg,
            strokes=self._visible_strokes_for_export(),
            bubbles=self._bubbles,
            stickers=self._stickers,
            time_ms=self._time_ms,
            frame_size=target_size,
            include_background=include_background,
            stroke_width_scale=width_scale,
        )

    def painter_action_state(self) -> dict:
        path_strokes = [
            stroke
            for stroke in (self.canvas.embedded_strokes() if hasattr(self, "canvas") else [])
            if str(getattr(stroke, "source_tool", "") or "") == "path"
        ]
        return {
            "schema": "tigerstudio.paint.state.v1",
            "standalone": bool(self._standalone),
            "document": {
                "width": int(self._canvas_document_size[0]),
                "height": int(self._canvas_document_size[1]),
                "background_layer_present": bool(self._background_layer_present),
            },
            "view": {
                "zoom_percent": int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100)),
                "pan_x": int(getattr(self, "_canvas_pan", QPoint(0, 0)).x()),
                "pan_y": int(getattr(self, "_canvas_pan", QPoint(0, 0)).y()),
                "grid_visible": bool(getattr(self, "_grid_visible", False)),
                "snap_to_grid": bool(getattr(self, "_snap_to_grid", False)),
                "grid_size_px": int(getattr(self, "_grid_size_px", 64)),
            },
            "layers": [
                {
                    "layer_id": layer.layer_id,
                    "name": layer.name,
                    "visible": bool(layer.visible),
                    "opacity": int(layer.opacity),
                    "locked": bool(layer.locked),
                    "blend_mode": str(getattr(layer, "blend_mode", "normal") or "normal"),
                    "mask_enabled": bool(getattr(layer, "mask_enabled", False)),
                    "mask_point_count": len(getattr(layer, "mask", []) or []),
                    "stroke_count": self._stroke_count_for_layer(layer.layer_id),
                    "active": layer.layer_id == self._active_paint_layer_id,
                    "selected": layer.layer_id == self._selected_layer_id,
                }
                for layer in self._paint_layers
            ],
            "active_layer_id": str(self._active_paint_layer_id),
            "selected_layer_id": str(self._selected_layer_id or ""),
            "tool": str(getattr(self.canvas, "_tool", "off") if hasattr(self, "canvas") else "off"),
            "selection_aspect": str(getattr(self, "_selection_aspect_mode", "free")),
            "mirror": {
                "x": bool(getattr(self, "_mirror_x_enabled", False)),
                "y": bool(getattr(self, "_mirror_y_enabled", False)),
            },
            "channels": dict(self._channel_visibility),
            "selected_channel": str(getattr(self, "_selected_channel", "RGB")),
            "selection": {
                "active": bool(self.canvas.has_active_selection()) if hasattr(self, "canvas") else False,
                "point_count": int(self.canvas.selection_point_count()) if hasattr(self, "canvas") else 0,
                "inverted": bool(self.canvas.selection_inverted()) if hasattr(self, "canvas") else False,
                "quick_mask_enabled": bool(getattr(self, "_quick_mask_enabled", False)),
                "magic_tolerance": int(getattr(self, "_magic_select_tolerance", 32)),
            },
            "paths": {
                "selected_path_id": str(self._selected_path_item_id),
                "work_path_points": int(self.canvas.path_point_count()) if hasattr(self, "canvas") else 0,
                "saved_path_count": len(path_strokes),
            },
            "history": {
                "undo_count": len(self._undo_stack),
                "redo_count": len(self._redo_stack),
                "undo_labels": list(self._undo_labels),
                "redo_labels": list(self._redo_labels),
            },
        }

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
