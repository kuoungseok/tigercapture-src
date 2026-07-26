from __future__ import annotations

import copy
import colorsys
import hashlib
import json
import math
import tempfile
from datetime import datetime
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

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
    QCursor,
    QDrag,
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
    QTabletEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
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
    QLineEdit,
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
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from app.icons import app_icon, icon_size
from app.i18n import tr
from app.studio_slider import StudioSlider
from app.painter_brush_catalog import (
    DESIGNER_BRUSH_PRESETS,
    DESIGNER_BRUSH_RENDER_PROFILES,
    DESIGNER_BRUSH_STYLE_IDS,
)
from app.window_placement import available_geometry_for_window


PAINT_CLIPBOARD_MIME = "application/x-tigercapture-paint-payload+json"
PAINT_CLIPBOARD_SCHEMA = "tigerstudio.paint.clipboard.v1"
PAINT_CLIPBOARD_IMAGE_DIR = Path("external/assets/paint_clipboard")
PAINT_REFERENCE_IMAGE_DIR = Path("external/assets/painter_references")
PAINT_MAX_ZOOM_PERCENT = 800
PAINT_PIXEL_GRID_FINE_ZOOM_PERCENT = 800
PAINT_BLOCKOUT_SHAPE_MIME = "application/x-tigerstudio-painter-blockout-shape"


def _distance_qpointf(a: QPointF, b: QPointF) -> float:
    return math.hypot(float(a.x() - b.x()), float(a.y() - b.y()))


def _distance_to_segment(point: QPointF, start: QPointF, end: QPointF) -> float:
    dx = float(end.x() - start.x())
    dy = float(end.y() - start.y())
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0001:
        return _distance_qpointf(point, start)
    amount = max(
        0.0,
        min(
            1.0,
            ((point.x() - start.x()) * dx + (point.y() - start.y()) * dy)
            / length_squared,
        ),
    )
    closest = QPointF(start.x() + dx * amount, start.y() + dy * amount)
    return _distance_qpointf(point, closest)


def _zoom_tool_cursor(mode: str) -> QCursor:
    """Return a high-contrast magnifier cursor with an in-lens mode mark."""
    value = str(mode or "zoom_in")
    if value not in {"zoom_in", "zoom_out"}:
        return QCursor(Qt.CursorShape.CrossCursor)

    pixmap = QPixmap(28, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        shadow_pen = QPen(QColor(0, 0, 0, 220), 4.0)
        shadow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(shadow_pen)
        painter.setBrush(QColor(20, 22, 26, 210))
        painter.drawEllipse(QPointF(9.5, 9.5), 7.0, 7.0)
        painter.drawLine(QPointF(14.4, 14.4), QPointF(23.0, 23.0))

        outline_pen = QPen(QColor(245, 248, 252), 2.0)
        outline_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(outline_pen)
        painter.setBrush(QColor(38, 42, 49, 235))
        painter.drawEllipse(QPointF(9.5, 9.5), 6.4, 6.4)
        painter.drawLine(QPointF(14.2, 14.2), QPointF(22.4, 22.4))

        mark_pen = QPen(QColor(255, 255, 255), 1.8)
        mark_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(mark_pen)
        painter.drawLine(QPointF(6.1, 9.5), QPointF(12.9, 9.5))
        if value == "zoom_in":
            painter.drawLine(QPointF(9.5, 6.1), QPointF(9.5, 12.9))
    finally:
        painter.end()
    return QCursor(pixmap, 10, 10)


_PAINT_DIALOG_QSS = """
QDialog {
    background-color: #111216;
    color: #f5f7fb;
}

QFrame#PaintTopBar,
QFrame#PaintInspector,
QFrame#PaintCanvasFrame {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QFrame#PaintTopBar {
    background-color: #474747;
    border-top: 1px solid #656565;
    border-bottom: 1px solid #303030;
    min-height: 34px;
    max-height: 34px;
}

QWidget#PaintToolOptionsHost {
    background-color: transparent;
}

QLabel#PaintActiveToolName {
    color: #f1f1f1;
    font-size: 11px;
    font-weight: 700;
    min-width: 66px;
}

QFrame#PaintOptionSeparator {
    background-color: #707070;
    border: none;
    min-width: 1px;
    max-width: 1px;
    min-height: 20px;
    max-height: 20px;
}

QFrame#PaintStatusBar {
    background-color: #3f3f3f;
    border-top: 1px solid #2f2f2f;
    border-bottom: none;
    min-height: 23px;
    max-height: 23px;
}

QFrame#PaintStatusBar QLabel {
    color: #d8d8d8;
    font-size: 10px;
}

QWidget#PaintCanvasModeBar {
    background-color: #2f3134;
    border-bottom: 1px solid #222427;
}

QPushButton#PaintCanvasModeButton,
QPushButton#PaintBlockoutModeButton {
    background-color: transparent;
    color: #cfd2d7;
    border: 1px solid transparent;
    border-radius: 2px;
    padding: 2px 7px;
    min-height: 20px;
    font-size: 10px;
    font-weight: 600;
}

QPushButton#PaintCanvasModeButton:hover,
QPushButton#PaintBlockoutModeButton:hover {
    background-color: #45484d;
}

QPushButton#PaintCanvasModeButton:checked,
QPushButton#PaintBlockoutModeButton:checked {
    background-color: #505761;
    color: #ffffff;
    border-color: #69727f;
}

QFrame#PaintStatusBar QSpinBox {
    background-color: transparent;
    color: #eeeeee;
    border: none;
    border-radius: 0;
    min-height: 19px;
    max-height: 19px;
    padding: 0 3px;
}

QWidget#PaintToolOptionsHost QPushButton {
    background-color: transparent;
    color: #eeeeee;
    border: 1px solid transparent;
    border-radius: 2px;
    min-height: 22px;
    max-height: 22px;
    padding: 0 7px;
}

QWidget#PaintToolOptionsHost QPushButton:hover {
    background-color: #606060;
    border-color: #727272;
}

QWidget#PaintToolOptionsHost QPushButton:checked {
    background-color: #2f2f2f;
    border-color: #8a8a8a;
}

QWidget#PaintToolOptionsHost QComboBox,
QWidget#PaintToolOptionsHost QSpinBox {
    background-color: #343434;
    color: #f1f1f1;
    border: 1px solid #272727;
    border-radius: 2px;
    min-height: 22px;
    max-height: 22px;
    padding: 0 5px;
}

QFrame#PaintToolRail {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QFrame#PaintInspector {
    background-color: #535353;
    border: 1px solid #393939;
    border-radius: 0;
}

QLabel#PaintTitle {
    color: #ffffff;
    font-size: 15px;
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
    background-color: #3f3f3f;
    border: none;
    border-radius: 0;
    color: #eeeeee;
    font-size: 11px;
    padding: 0 4px;
}

QMenuBar#PaintMenuBar::item {
    background: transparent;
    padding: 5px 9px;
    border-radius: 0;
}

QMenuBar#PaintMenuBar::item:selected {
    background-color: #5b5b5b;
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

QMenu#PaintBrushPopup {
    background-color: #292929;
    border: 1px solid #0f0f0f;
    border-radius: 2px;
    padding: 1px;
}

QFrame#PaintBrushPopupPanel {
    background-color: #303030;
    border: none;
}

QFrame#PaintBrushPopupNotice {
    background-color: #454545;
    border: 1px solid #202020;
    color: #ededed;
}

QComboBox#PaintBrushPopupLibrary,
QLineEdit#PaintBrushPopupSearch {
    background-color: #4a4a4a;
    border: 1px solid #202020;
    border-radius: 1px;
    color: #f0f0f0;
    min-height: 24px;
    padding: 1px 6px;
}

QListWidget#PaintBrushPopupCategory {
    background-color: #393939;
    border: 1px solid #202020;
    color: #ececec;
    outline: none;
}

QListWidget#PaintBrushPopupCategory::item {
    min-height: 24px;
    padding: 1px 5px;
}

QListWidget#PaintBrushPopupCategory::item:hover {
    background-color: #484848;
}

QListWidget#PaintBrushPopupCategory::item:selected {
    background-color: #575757;
    border-left: 2px solid #d99b31;
    color: #ffffff;
}

QListWidget#PaintBrushPopupList {
    background-color: #252525;
    border: 1px solid #1d1d1d;
    outline: none;
}

QListWidget#PaintBrushPopupList::item {
    background-color: #303030;
    border: 1px solid #222222;
    border-radius: 0;
    color: #f1f1f1;
    padding: 2px 5px;
    margin: 1px;
}

QListWidget#PaintBrushPopupList::item:hover {
    background-color: #3d3d3d;
    border-color: #595959;
}

QListWidget#PaintBrushPopupList::item:selected {
    background-color: #393939;
    border: 1px solid #d99b31;
}

QFrame#PaintBrushPopupFilters,
QFrame#PaintBrushPopupFooter {
    background-color: #353535;
    border: 1px solid #202020;
}

QCheckBox#PaintBrushPopupFilter {
    color: #ededed;
    spacing: 5px;
    min-height: 22px;
}

QCheckBox#PaintBrushPopupFilter::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #777777;
    background-color: #2a2a2a;
}

QCheckBox#PaintBrushPopupFilter::indicator:checked {
    background-color: #d99b31;
    border-color: #f1bd59;
}

QLabel#PaintBrushPopupPreview {
    background-color: #222222;
    border: 1px solid #171717;
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
    background-color: #1a1f29;
    color: #eef3fb;
    border: 1px solid rgba(178,186,202,32);
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 760;
    font-size: 11px;
    text-align: left;
    min-height: 26px;
}

QPushButton#PaintTool:hover,
QPushButton#BubbleBtn:hover,
QPushButton#StickerBtn:hover {
    background-color: #202635;
    border-color: rgba(210, 218, 235, 52);
}

QPushButton#PaintTool:checked,
QPushButton#BubbleBtn:checked,
QPushButton#StickerBtn:checked {
    background: #2d3450;
    border-color: rgba(139, 124, 255, 130);
    color: #ffffff;
}

QFrame#PaintToolRail QPushButton {
    min-width: 30px;
    max-width: 30px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    text-align: center;
}

QFrame#PaintToolRail QPushButton#PaintTool,
QFrame#PaintToolRail QPushButton#BubbleBtn,
QFrame#PaintToolRail QPushButton#StickerBtn,
QFrame#PaintToolRail QPushButton#PaintDanger {
    background-color: transparent;
    border: none;
    border-radius: 0;
    padding: 0;
}

QFrame#PaintToolRail QPushButton#PaintTool:hover,
QFrame#PaintToolRail QPushButton#BubbleBtn:hover,
QFrame#PaintToolRail QPushButton#StickerBtn:hover,
QFrame#PaintToolRail QPushButton#PaintDanger:hover {
    background-color: #626262;
    border: none;
}

QFrame#PaintToolRail QPushButton#PaintTool:checked,
QFrame#PaintToolRail QPushButton#BubbleBtn:checked,
QFrame#PaintToolRail QPushButton#StickerBtn:checked {
    background-color: #3f3f3f;
    border: none;
}

QLabel#PaintToolRailGrip {
    color: #bdbdbd;
    background-color: transparent;
    border: none;
    font-size: 8px;
    letter-spacing: 1px;
}

QPushButton#PaintToolRailChrome {
    background-color: transparent;
    color: #9ea8ba;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 0;
    min-width: 16px;
    max-width: 16px;
    min-height: 16px;
    max-height: 16px;
}

QPushButton#PaintToolRailChrome:hover {
    background-color: #202635;
    color: #eef3fb;
    border-color: rgba(178,186,202,36);
}

QFrame#PaintToolRailSeparator {
    background-color: transparent;
    border: none;
    min-height: 3px;
    max-height: 3px;
}

QFrame#PaintToolSwatches {
    background-color: transparent;
    border: none;
    border-radius: 0;
}

QPushButton#PaintForegroundSwatch,
QPushButton#PaintBackgroundSwatch {
    border: 1px solid #f0f0f0;
    border-radius: 0;
    padding: 0;
}

QPushButton#PaintForegroundSwatch {
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
}

QPushButton#PaintBackgroundSwatch {
    min-width: 21px;
    max-width: 21px;
    min-height: 21px;
    max-height: 21px;
}

QPushButton#PaintForegroundSwatch:hover,
QPushButton#PaintBackgroundSwatch:hover {
    border-color: #ffffff;
}

QPushButton#PaintSwapSwatch {
    background-color: transparent;
    color: #aeb8c9;
    border: none;
    padding: 0;
    min-width: 14px;
    max-width: 14px;
    min-height: 14px;
    max-height: 14px;
}

QPushButton#PaintDanger {
    background-color: #241b1d;
    color: #ffdede;
    border: 1px solid rgba(204, 91, 91, 62);
    border-radius: 6px;
    padding: 5px 9px;
    font-weight: 760;
    min-height: 26px;
    text-align: left;
}

QPushButton#PaintDanger:hover {
    background-color: #3a2727;
    border-color: #de6969;
}

QPushButton#PaintCustomColor {
    background-color: #191e27;
    color: #f0f4fb;
    border: 1px solid rgba(178,186,202,32);
    border-radius: 6px;
    padding: 4px 8px;
    font-weight: 760;
    min-height: 24px;
}

QPushButton#PaintCustomColor:hover {
    background-color: #202635;
    border-color: rgba(210, 218, 235, 52);
}

QFrame#PaintColorPanel {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QFrame#PaintColorPanel QLabel {
    background-color: transparent;
    border: none;
}

QTabWidget#PaintColorTabs {
    background-color: #535353;
}

QTabWidget#PaintColorTabs::pane {
    background-color: #535353;
    border: none;
    border-top: 1px solid #3d3d3d;
    top: 0;
}

QTabWidget#PaintColorTabs QTabBar::tab {
    background-color: #4a4a4a;
    color: #d0d0d0;
    border: none;
    border-right: 1px solid #393939;
    border-radius: 0;
    padding: 3px 7px;
    min-height: 17px;
    font-size: 9px;
    font-weight: 600;
}

QTabWidget#PaintColorTabs QTabBar::tab:selected {
    background-color: #626262;
    color: #ffffff;
}

QTabWidget#PaintColorTabs QTabBar::tab:!selected:hover {
    background-color: #5b5b5b;
    color: #ffffff;
}

QPushButton#PaintFlatPresetButton {
    background-color: #5a5a5a;
    color: #ededed;
    border: 1px solid #3d3d3d;
    border-radius: 0;
    padding: 3px 6px;
    text-align: left;
    min-height: 18px;
    font-size: 9px;
}

QPushButton#PaintFlatPresetButton:hover {
    background-color: #686868;
}

QLabel#PaintColorLabel {
    color: #aab4c4;
    font-size: 10px;
    font-weight: 700;
    padding: 0;
    min-width: 0;
}

QLabel#PaintColorSectionLabel {
    color: #dce6f7;
    font-size: 10px;
    font-weight: 780;
    letter-spacing: 0px;
    padding: 0;
}

QFrame#PaintColorWheelFrame {
    background-color: #0f131a;
    border: 1px solid rgba(178, 186, 202, 18);
    border-radius: 5px;
}

QFrame#PaintColorMatrixFrame {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QFrame#PaintLayerDockPanel {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QFrame#PaintBlockoutPanel {
    background-color: #11151b;
    border: 1px solid rgba(178, 186, 202, 24);
    border-radius: 6px;
}

QFrame#PaintReferencePanel {
    background-color: #11151b;
    border: 1px solid rgba(178, 186, 202, 24);
    border-radius: 6px;
}

QLabel#PaintReferencePreview {
    background-color: #080b11;
    border: 1px solid rgba(178, 186, 202, 24);
    border-radius: 6px;
    color: #7f8a9f;
    font-size: 11px;
    font-weight: 700;
}

QLabel#PaintBlockoutStatus {
    color: #9ea8ba;
    font-size: 10px;
    font-weight: 650;
}

QListWidget#PaintBlockoutList {
    background-color: #0f131a;
    color: #eef3fb;
    border: 1px solid rgba(178, 186, 202, 22);
    border-radius: 6px;
    outline: none;
}

QListWidget#PaintBlockoutList::item {
    border-radius: 5px;
    padding: 4px 6px;
}

QListWidget#PaintBlockoutList::item:selected {
    background-color: #243a63;
    color: #ffffff;
}

QListWidget#PaintReferenceList {
    background-color: #0f131a;
    color: #eef3fb;
    border: 1px solid rgba(178, 186, 202, 22);
    border-radius: 6px;
    outline: none;
}

QListWidget#PaintReferenceList::item {
    border-radius: 5px;
    padding: 4px 6px;
}

QListWidget#PaintReferenceList::item:selected {
    background-color: #26324f;
    color: #ffffff;
}

QLabel#PaintLayerDockNote {
    color: #8f9bb0;
    font-size: 11px;
    font-weight: 650;
    padding: 1px 4px 0 4px;
}

QScrollArea#PaintInspectorScroll {
    background-color: transparent;
    border: none;
}

QScrollArea#PaintInspectorScroll > QWidget > QWidget {
    background-color: #535353;
}

QScrollArea#PaintInspectorScroll QScrollBar:vertical {
    background-color: #474747;
    border: none;
    border-radius: 0;
    width: 6px;
    margin: 0;
}

QScrollArea#PaintInspectorScroll QScrollBar::handle:vertical {
    background-color: #707070;
    border-radius: 0;
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
    background-color: #535353;
}

QTabWidget#PaintLayerChannelPathTabs::pane {
    background-color: #535353;
    border: none;
    border-radius: 0;
    top: 0;
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab {
    background-color: #4a4a4a;
    color: #d0d0d0;
    border: none;
    border-right: 1px solid #393939;
    border-bottom: none;
    border-radius: 0;
    padding: 3px 8px;
    min-width: 36px;
    min-height: 18px;
    font-size: 10px;
    font-weight: 600;
}

QWidget#PaintPanelTabButtonGrid {
    background-color: transparent;
}

QPushButton#PaintPanelTabButton {
    background-color: #191e27;
    color: #aeb7c7;
    border: 1px solid rgba(178, 186, 202, 28);
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 760;
}

QPushButton#PaintPanelTabButton:hover {
    background-color: #2d3036;
    color: #dce6f7;
}

QPushButton#PaintPanelTabButton:checked {
    background-color: #2d3450;
    color: #ffffff;
    border-color: rgba(139, 124, 255, 118);
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab:selected {
    background-color: #626262;
    color: #ffffff;
}

QTabWidget#PaintLayerChannelPathTabs QTabBar::tab:!selected:hover {
    background-color: #5b5b5b;
    color: #ffffff;
}

QFrame#PaintLayerControlPanel {
    background-color: #535353;
    border: none;
    border-radius: 0;
}

QLabel#PaintLayerControlLabel {
    color: #c5cfdf;
    font-size: 11px;
    font-weight: 760;
    padding: 0;
}

QPushButton#PaintLayerTinyButton {
    background-color: transparent;
    color: #e4e4e4;
    border: none;
    border-radius: 0;
    padding: 0;
    min-width: 20px;
    max-width: 20px;
    min-height: 20px;
    max-height: 20px;
}

QPushButton#PaintLayerTinyButton:hover {
    background-color: #686868;
    border: none;
}

QPushButton#PaintLayerTinyButton:checked {
    background-color: #747474;
    border: none;
}

QComboBox#PaintLayerFilterCombo,
QComboBox#PaintLayerBlendCombo {
    background-color: #484848;
    color: #f0f0f0;
    border: 1px solid #393939;
    border-radius: 0;
    padding: 2px 5px;
    min-width: 0;
    min-height: 20px;
}

QLabel#PaintColorWell {
    border: 1px solid #f0f0f0;
    border-radius: 0;
}

QLabel#PaintPbrPreview {
    background-color: #08090c;
    border: 1px solid #2c3342;
    border-radius: 8px;
    color: #8f98a7;
    min-height: 130px;
}

QLabel#PaintColorHex {
    color: #f3f3f3;
    background-color: transparent;
    border: none;
    border-radius: 0;
    padding: 1px 4px;
    font-weight: 600;
    font-size: 9px;
}

QFrame#PaintColorPanel QPushButton#PaintCustomColor {
    background-color: transparent;
    color: #ededed;
    border: none;
    border-radius: 0;
    padding: 0;
    min-width: 24px;
    max-width: 24px;
    min-height: 20px;
    max-height: 20px;
}

QFrame#PaintColorPanel QPushButton#PaintCustomColor:hover {
    background-color: #686868;
}

QFrame#PaintInspector QLabel#PaintValue {
    color: #f3f3f3;
    background-color: #484848;
    border: 1px solid #393939;
    border-radius: 0;
    padding: 2px 4px;
}

QFrame#PaintColorPanel QSlider::groove:horizontal {
    height: 3px;
    border-radius: 2px;
    background: #292B35;
}

QFrame#PaintColorPanel QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    background: #6452FF;
    border: 1px solid #9C8EFF;
}

QSlider::groove:horizontal {
    height: 3px;
    border-radius: 2px;
    background: #292B35;
}

QSlider::sub-page:horizontal {
    background: #5B45FF;
    border-radius: 2px;
}

QSlider::add-page:horizontal {
    background: #292B35;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    background: #6452FF;
    border: 1px solid #9C8EFF;
}

QSlider::handle:horizontal:hover {
    background: #7566FF;
    border-color: #D6D0FF;
}

QSlider#PaintHueSlider::groove:horizontal {
    height: 4px;
    border-radius: 2px;
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
QSlider#PaintSaturationSlider::handle:horizontal,
QSlider#PaintValueSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
    background: #6452FF;
    border: 1px solid #9C8EFF;
}

QComboBox {
    background-color: #0f1117;
    color: #ffffff;
    border: 1px solid #2c3342;
    border-radius: 5px;
    padding: 3px 8px;
    min-width: 118px;
}

QComboBox:hover {
    border-color: #6aa2ff;
}

QListWidget#PaintLayerList {
    background-color: #535353;
    color: #ededed;
    border: none;
    border-radius: 0;
    outline: none;
    padding: 0;
}

QListWidget#PaintLayerList::item {
    border-radius: 0;
    padding: 3px 4px;
    border-bottom: 1px solid #494949;
}

QListWidget#PaintLayerList::item:selected {
    background-color: #747474;
    color: #ffffff;
}

QFrame#PaintLayerControlPanel QSlider::groove:horizontal {
    height: 2px;
    background-color: #343434;
    border-radius: 0;
}

QFrame#PaintLayerControlPanel QSlider::sub-page:horizontal {
    background-color: #a0a0a0;
    border-radius: 0;
}

QFrame#PaintLayerControlPanel QSlider::handle:horizontal {
    width: 10px;
    height: 10px;
    margin: -4px 0;
    background-color: #d8d8d8;
    border: 1px solid #353535;
    border-radius: 5px;
}

QListWidget#PaintBrushList {
    background-color: #303236;
    color: #e7e7e7;
    border: 1px solid #242629;
    border-radius: 0;
    outline: none;
    padding: 2px;
}

QListWidget#PaintBrushList::item {
    border-radius: 0;
    padding: 2px 5px;
    margin: 0;
    border-bottom: 1px solid #3b3d41;
}

QListWidget#PaintBrushList::item:selected {
    background-color: #505761;
    color: #ffffff;
    border: none;
    border-bottom: 1px solid #616a76;
}

QListWidget#PaintBrushCategoryList,
QListWidget#PaintBrushRecentList {
    background-color: #35373a;
    color: #d8d8d8;
    border: 1px solid #27292c;
    border-radius: 0;
    outline: none;
}

QListWidget#PaintBrushCategoryList::item {
    min-height: 20px;
    padding: 1px 6px;
}

QListWidget#PaintBrushCategoryList::item:selected,
QListWidget#PaintBrushRecentList::item:selected {
    background-color: #505761;
    color: #ffffff;
}

QLineEdit#PaintBrushSearch,
QComboBox#PaintBrushLibrarySelector {
    background-color: #34363a;
    color: #e6e6e6;
    border: 1px solid #25272a;
    border-radius: 0;
    min-height: 21px;
    max-height: 21px;
    padding: 0 5px;
}

QPushButton#PaintBrushLibraryTool,
QPushButton#PaintBrushViewTool {
    background-color: transparent;
    color: #dddddd;
    border: 1px solid transparent;
    border-radius: 0;
    padding: 2px;
}

QPushButton#PaintBrushLibraryTool:hover,
QPushButton#PaintBrushViewTool:hover {
    background-color: #45484d;
    border-color: #55595f;
}

QPushButton#PaintBrushLibraryTool:checked,
QPushButton#PaintBrushLibraryTool[activeFilters="true"],
QPushButton#PaintBrushViewTool:checked {
    background-color: #505761;
    border-color: #69727f;
}

QLabel#PaintBrushPanelTitle {
    color: #f0f0f0;
    font-size: 11px;
    font-weight: 700;
}

QLabel#PaintBrushMeta {
    color: #aeb2b8;
    font-size: 9px;
    padding: 1px 3px;
}

QFrame#PaintBrushDetailPanel {
    background-color: #383a3d;
    border: 1px solid #292b2e;
    border-radius: 0;
}

QPushButton#PaintBrushCategory,
QPushButton#PaintBrushTinyButton {
    background-color: #34363a;
    color: #dedede;
    border: 1px solid #27292c;
    border-radius: 1px;
    padding: 4px 6px;
    font-size: 11px;
    font-weight: 600;
    text-align: left;
}

QPushButton#PaintBrushCategory:checked,
QPushButton#PaintBrushTinyButton:checked {
    background-color: #505761;
    border-color: #69727f;
    color: #ffffff;
}

QPushButton#PaintBrushCategory:disabled {
    color: #697386;
    border-color: #222936;
}

QLabel#PaintBrushPreview {
    background-color: #303236;
    border: 1px solid #242629;
    border-radius: 0;
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
    brush_hardness: int = 100
    brush_spacing: int = 25
    brush_angle: int = 0
    brush_roundness: int = 100
    brush_flip_x: bool = False
    brush_flip_y: bool = False
    closed_path: bool = False
    layer_id: str = "paint-layer-1"
    source_tool: str = "pen"
    brush_engine_version: int = 1
    point_pressure: list[float] = field(default_factory=list)
    point_tilt: list[float] = field(default_factory=list)
    point_tilt_x: list[float] = field(default_factory=list)
    point_tilt_y: list[float] = field(default_factory=list)
    point_rotation: list[float] = field(default_factory=list)
    point_tangential_pressure: list[float] = field(default_factory=list)
    point_load: list[float] = field(default_factory=list)
    bristle_count: int = 0
    brush_seed: int = 0
    load_depletion: float = 0.28
    material_enabled: bool = False
    material_load: float = 0.0
    material_thickness: float = 0.0
    material_wetness: float = 0.0
    material_gloss: float = 0.0
    material_roughness: float = 0.56
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
    color_label: str = "none"
    layer_type: str = "standard"
    material_settings: dict[str, float] = field(default_factory=dict)
    wet_canvas_settings: dict[str, object] = field(default_factory=dict)


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
    ("Transparent", "transparent"),
    ("White", "#FFFFFF"),
    ("Dark", "#101112"),
)

PAINT_LAYER_COLOR_LABELS: tuple[tuple[str, str, str], ...] = (
    ("none", "None", ""),
    ("red", "Red", "#8A3A3A"),
    ("orange", "Orange", "#8A5731"),
    ("yellow", "Yellow", "#7A6C2E"),
    ("green", "Green", "#3D6B48"),
    ("blue", "Blue", "#365B86"),
    ("violet", "Violet", "#59477F"),
    ("gray", "Gray", "#555B64"),
)
PAINT_LAYER_COLOR_LABEL_MAP = {
    key: {"name": label, "color": color}
    for key, label, color in PAINT_LAYER_COLOR_LABELS
}


def _normalise_paint_layer_color_label(value: str | None) -> str:
    key = str(value or "none").strip().casefold().replace(" ", "_").replace("-", "_")
    if key not in PAINT_LAYER_COLOR_LABEL_MAP:
        return "none"
    return key


def create_blank_paint_pixmap(width: int, height: int, background: str = "transparent") -> QPixmap:
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


def paint_pixmap_has_visible_pixels(pixmap: QPixmap | None) -> bool:
    """Return whether a document pixmap contains at least one visible pixel."""
    if pixmap is None or pixmap.isNull():
        return False
    image = pixmap.toImage()
    if not image.hasAlphaChannel():
        return True
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    raw = bytes(rgba.constBits())
    return any(raw[3::4])


def create_checkerboard_paint_pixmap(width: int, height: int, cell: int = 16) -> QPixmap:
    safe_w = max(1, min(16384, int(width or 1)))
    safe_h = max(1, min(16384, int(height or 1)))
    tile = max(4, int(cell or 24))
    pixmap = QPixmap(safe_w, safe_h)
    pixmap.fill(QColor("#eeeeee"))
    painter = QPainter(pixmap)
    try:
        dark = QColor("#c7c7c7")
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
        default_background: str = "transparent",
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
            bg = str(background or "transparent").lower()
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
            "background": str(self.background_combo.currentData() or "transparent"),
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
    zoom_requested = Signal(str, float, float, float, float)

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
        self._brush_hardness: int = 100
        self._brush_spacing: int = 25
        self._brush_angle: int = 0
        self._brush_roundness: int = 100
        self._brush_flip_x: bool = False
        self._brush_flip_y: bool = False
        self._active_layer_id: str = "paint-layer-1"
        self._layer_visibility: dict[str, bool] = {}
        self._layer_opacity: dict[str, int] = {}
        self._layer_masks: dict[str, list[tuple[float, float]]] = {}
        self._layer_order: list[str] = []
        self._layer_wet_canvas_settings: dict[str, dict[str, object]] = {}
        self._wet_canvas_render_cache: dict[str, tuple[str, QImage]] = {}
        self._wet_canvas_reports: dict[str, dict[str, object]] = {}
        self._current_points: list[QPointF] = []  # while drawing (widget px)
        self._current_pressure: list[float] = []
        self._current_tilt: list[float] = []
        self._current_tilt_x: list[float] = []
        self._current_tilt_y: list[float] = []
        self._current_rotation: list[float] = []
        self._current_tangential_pressure: list[float] = []
        self._current_load: list[float] = []
        self._tablet_stroke_active = False
        self._path_points: list[QPointF] = []
        self._selection_points: list[tuple[float, float]] = []
        self._selection_inverted: bool = False
        self._selection_aspect_mode: str = "free"
        self._selection_combine_mode: str = "new"
        self._selection_drag_tool: str = ""
        self._selection_drag_start: QPointF | None = None
        self._selection_drag_current: QPointF | None = None
        self._selection_phase: float = 0.0
        self._quick_mask_enabled: bool = False
        self._grid_visible: bool = False
        self._snap_enabled: bool = False
        self._grid_size_px: int = 64
        self._document_size_px: tuple[int, int] = (1, 1)
        self._view_zoom_percent: int = 100
        self._pixel_grid_auto_enabled: bool = True
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
        self._painter_canvas_renderer_status: dict = {
            "renderer": "painter_canvas_qpainter_strokes_v1",
            "active": "qpainter",
            "fallback": True,
            "reason": "not_rendered_yet",
            "remote_safe": True,
        }
        self._painter_canvas_gpu_cache_key: str | None = None
        self._painter_canvas_gpu_cache_image: QImage | None = None
        self._painter_canvas_gpu_failure_key: str | None = None
        self._painter_canvas_stroke_atlas = None
        self._perspective_guides_enabled: bool = False
        self._perspective_horizon_norm: float = 0.5
        self._perspective_left_vp: tuple[float, float] = (0.08, 0.5)
        self._perspective_right_vp: tuple[float, float] = (0.92, 0.5)
        self._symmetry_guide_enabled: bool = False
        self._symmetry_guide_axis: str = "vertical"
        self._symmetry_guide_position_norm: float = 0.5

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)

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
            "zoom_in",
            "zoom_out",
            "zoom_area",
        ):
            tool = "off"
        self._tool = tool
        self._refresh_mouse_transparency()
        if tool in {"zoom_in", "zoom_out"}:
            cursor = _zoom_tool_cursor(tool)
        else:
            cursor = (
                Qt.CursorShape.CrossCursor
                if tool in (
                    "pen",
                    "eraser",
                    "path",
                    "rect_select",
                    "ellipse_select",
                    "crop",
                    "magic_select",
                    "zoom_area",
                )
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
        self._pen_style = _normalize_paint_brush_style(style)
        self.update()

    def set_brush_detail(
        self,
        *,
        hardness: int | None = None,
        spacing: int | None = None,
        angle: int | None = None,
        roundness: int | None = None,
        flip_x: bool | None = None,
        flip_y: bool | None = None,
    ) -> None:
        if hardness is not None:
            self._brush_hardness = max(1, min(100, int(hardness)))
        if spacing is not None:
            self._brush_spacing = max(1, min(200, int(spacing)))
        if angle is not None:
            self._brush_angle = max(-180, min(180, int(angle)))
        if roundness is not None:
            self._brush_roundness = max(10, min(100, int(roundness)))
        if flip_x is not None:
            self._brush_flip_x = bool(flip_x)
        if flip_y is not None:
            self._brush_flip_y = bool(flip_y)
        self.update()

    def _current_brush_detail_kwargs(self) -> dict[str, int | bool]:
        return {
            "brush_hardness": int(self._brush_hardness),
            "brush_spacing": int(self._brush_spacing),
            "brush_angle": int(self._brush_angle),
            "brush_roundness": int(self._brush_roundness),
            "brush_flip_x": bool(self._brush_flip_x),
            "brush_flip_y": bool(self._brush_flip_y),
        }

    def set_active_layer_id(self, layer_id: str | None) -> None:
        self._active_layer_id = str(layer_id or "paint-layer-1")

    def set_layer_view(
        self,
        visibility: dict[str, bool] | None = None,
        opacity: dict[str, int] | None = None,
        masks: dict[str, list[tuple[float, float]]] | None = None,
        order: list[str] | None = None,
        wet_canvas_settings: dict[str, dict[str, object]] | None = None,
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
        self._layer_order = [str(layer_id) for layer_id in list(order or [])]
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        self._layer_wet_canvas_settings = {
            str(layer_id): normalize_wet_canvas_settings(settings)
            for layer_id, settings in dict(wet_canvas_settings or {}).items()
        }
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

    def set_path_snapshot(self, points: list[tuple[float, float]] | None) -> None:
        w = max(1, self.width())
        h = max(1, self.height())
        self._path_points = [
            QPointF(
                max(0.0, min(1.0, float(point[0]))) * w,
                max(0.0, min(1.0, float(point[1]))) * h,
            )
            for point in list(points or [])
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]
        self.repaint_requested.emit()
        self.update()

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

    def set_selection_combine_mode(self, mode: str) -> None:
        value = str(mode or "new").strip().casefold()
        self._selection_combine_mode = (
            value if value in {"new", "add", "subtract", "intersect"} else "new"
        )

    def selection_combine_mode(self) -> str:
        return str(getattr(self, "_selection_combine_mode", "new") or "new")

    @staticmethod
    def _normalized_selection_path(points: list[tuple[float, float]]) -> QPainterPath:
        path = QPainterPath()
        if len(points) < 3:
            return path
        path.moveTo(float(points[0][0]), float(points[0][1]))
        for x, y in points[1:]:
            path.lineTo(float(x), float(y))
        path.closeSubpath()
        return path

    def _combine_selection(
        self,
        points: list[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        mode = self.selection_combine_mode()
        if mode == "new" or len(self._selection_points) < 3:
            return list(points)
        current = self._normalized_selection_path(self._selection_points)
        incoming = self._normalized_selection_path(points)
        if mode == "add":
            combined = current.united(incoming)
        elif mode == "subtract":
            combined = current.subtracted(incoming)
        else:
            combined = current.intersected(incoming)
        polygon = combined.toFillPolygon()
        if polygon.isEmpty():
            return []
        return [
            (max(0.0, min(1.0, float(point.x()))), max(0.0, min(1.0, float(point.y()))))
            for point in polygon
        ]

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

    def set_perspective_guides(
        self,
        *,
        enabled: bool | None = None,
        horizon: float | None = None,
        left_vp: tuple[float, float] | None = None,
        right_vp: tuple[float, float] | None = None,
    ) -> None:
        if enabled is not None:
            self._perspective_guides_enabled = bool(enabled)
        if horizon is not None:
            self._perspective_horizon_norm = max(0.02, min(0.98, float(horizon)))
        if left_vp is not None:
            self._perspective_left_vp = self._clamp_normalized_point(left_vp)
        if right_vp is not None:
            self._perspective_right_vp = self._clamp_normalized_point(right_vp)
        self.update()

    def perspective_guide_state(self) -> dict[str, object]:
        return {
            "enabled": bool(getattr(self, "_perspective_guides_enabled", False)),
            "horizon": float(getattr(self, "_perspective_horizon_norm", 0.5) or 0.5),
            "left_vp": list(getattr(self, "_perspective_left_vp", (0.08, 0.5)) or (0.08, 0.5)),
            "right_vp": list(getattr(self, "_perspective_right_vp", (0.92, 0.5)) or (0.92, 0.5)),
            "renderer": "qpainter_overlay_remote_safe_v1",
        }

    def set_symmetry_guide(
        self,
        *,
        enabled: bool | None = None,
        axis: str | None = None,
        position: float | None = None,
    ) -> None:
        if enabled is not None:
            self._symmetry_guide_enabled = bool(enabled)
        if axis is not None:
            value = str(axis or "vertical").strip().casefold()
            self._symmetry_guide_axis = value if value in {"vertical", "horizontal"} else "vertical"
        if position is not None:
            self._symmetry_guide_position_norm = max(0.02, min(0.98, float(position)))
        self.update()

    def symmetry_guide_state(self) -> dict[str, object]:
        return {
            "enabled": bool(getattr(self, "_symmetry_guide_enabled", False)),
            "axis": str(getattr(self, "_symmetry_guide_axis", "vertical") or "vertical"),
            "position": float(getattr(self, "_symmetry_guide_position_norm", 0.5) or 0.5),
            "renderer": "qpainter_overlay_remote_safe_v1",
        }

    @staticmethod
    def _clamp_normalized_point(point: tuple[float, float] | list[float]) -> tuple[float, float]:
        values = list(point or (0.5, 0.5))
        x = float(values[0]) if values else 0.5
        y = float(values[1]) if len(values) > 1 else 0.5
        return (max(-1.5, min(2.5, x)), max(0.02, min(0.98, y)))

    def set_document_size(self, width: int, height: int) -> None:
        self._document_size_px = (
            max(1, int(width or 1)),
            max(1, int(height or 1)),
        )
        self.update()

    def set_view_zoom_percent(self, percent: int) -> None:
        self._view_zoom_percent = max(25, min(PAINT_MAX_ZOOM_PERCENT, int(percent or 100)))
        self.update()

    def stable_render_size(self, width: int | None = None, height: int | None = None) -> QSize:
        """Return the unzoomed cache size used for retained stroke/material rendering."""
        display_width = max(1, int(self.width() if width is None else width))
        display_height = max(1, int(self.height() if height is None else height))
        zoom = max(
            0.25,
            min(
                PAINT_MAX_ZOOM_PERCENT / 100.0,
                float(getattr(self, "_view_zoom_percent", 100) or 100) / 100.0,
            ),
        )
        return QSize(
            max(1, int(round(display_width / zoom))),
            max(1, int(round(display_height / zoom))),
        )

    def pixel_grid_state(self) -> dict[str, int | float | bool]:
        metrics = self._pixel_grid_metrics(max(1, self.width()), max(1, self.height()))
        return {
            "auto": bool(getattr(self, "_pixel_grid_auto_enabled", True)),
            "visible": bool(metrics.get("visible", False)),
            "cell_width_px": float(metrics.get("cell_width_px", 0.0)),
            "cell_height_px": float(metrics.get("cell_height_px", 0.0)),
            "stride_x": int(metrics.get("stride_x", 0)),
            "stride_y": int(metrics.get("stride_y", 0)),
            "major_every": int(metrics.get("major_every", 0)),
        }

    def _pixel_grid_metrics(self, w: int, h: int) -> dict[str, int | float | bool]:
        if not bool(getattr(self, "_pixel_grid_auto_enabled", True)):
            return {"visible": False}
        doc_w, doc_h = tuple(getattr(self, "_document_size_px", (1, 1)))
        doc_w = max(1, int(doc_w))
        doc_h = max(1, int(doc_h))
        cell_w = float(w) / float(doc_w)
        cell_h = float(h) / float(doc_h)
        zoom_percent = int(getattr(self, "_view_zoom_percent", 100) or 100)
        min_cell = min(cell_w, cell_h)
        if zoom_percent < 400 or min_cell < 1.25:
            return {
                "visible": False,
                "cell_width_px": cell_w,
                "cell_height_px": cell_h,
            }
        stride_x = max(1, int(math.ceil(3.0 / max(0.01, cell_w))))
        stride_y = max(1, int(math.ceil(3.0 / max(0.01, cell_h))))
        visible_lines = int(math.ceil(doc_w / stride_x) + math.ceil(doc_h / stride_y))
        if visible_lines > 6000:
            scale = int(math.ceil(visible_lines / 6000.0))
            stride_x *= scale
            stride_y *= scale
        return {
            "visible": True,
            "cell_width_px": cell_w,
            "cell_height_px": cell_h,
            "stride_x": stride_x,
            "stride_y": stride_y,
            "major_every": 8,
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
        self.set_selection_snapshot(self._combine_selection(points))

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

    def _wet_canvas_layer_enabled(self, layer_id: str) -> bool:
        from app.painter_wet_canvas import wet_canvas_remaining

        settings = self._layer_wet_canvas_settings.get(str(layer_id), {})
        return bool(settings.get("enabled", False) and wet_canvas_remaining(settings) > 0.0)

    def _paint_wet_canvas_layer(
        self,
        painter: QPainter,
        strokes: list[Stroke],
        layer_id: str,
        width: int,
        height: int,
        time_ms: int,
    ) -> None:
        from app.painter_wet_canvas import (
            render_wet_layer_qimage,
            wet_canvas_signature,
        )

        layer_strokes = [
            stroke
            for stroke in strokes
            if self._stroke_layer_id(stroke) == layer_id and stroke.is_active(time_ms)
        ]
        if not layer_strokes:
            return
        opacity_scale = self._layer_opacity.get(layer_id, 100) / 100.0
        settings = self._layer_wet_canvas_settings.get(layer_id, {})
        signature = wet_canvas_signature(
            layer_strokes,
            settings,
            width=width,
            height=height,
            time_ms=time_ms,
            opacity_scale=opacity_scale,
        )
        cached = self._wet_canvas_render_cache.get(layer_id)
        if cached is not None and cached[0] == signature:
            image = cached[1]
        else:
            image, report = render_wet_layer_qimage(
                layer_strokes,
                settings=settings,
                width=width,
                height=height,
                time_ms=time_ms,
                opacity_scale=opacity_scale,
                render_stroke=lambda target, stroke, render_w, render_h, alpha: self._paint_stroke(
                    target,
                    stroke,
                    render_w,
                    render_h,
                    opacity_scale=alpha,
                ),
            )
            self._wet_canvas_render_cache[layer_id] = (signature, image)
            self._wet_canvas_reports[layer_id] = dict(report)
        painter.drawImage(0, 0, image)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = max(1, self.width())
        h = max(1, self.height())

        self._paint_grid(painter, w, h)

        t_ms = int(self._get_time_ms())
        strokes = list(self._get_strokes())
        if self._layer_order:
            layer_rank = {layer_id: index for index, layer_id in enumerate(self._layer_order)}
            strokes.sort(key=lambda stroke: layer_rank.get(self._stroke_layer_id(stroke), len(layer_rank)))
        stable_size = self.stable_render_size(w, h)
        render_w = max(1, stable_size.width())
        render_h = max(1, stable_size.height())
        painter.save()
        try:
            if render_w != w or render_h != h:
                painter.scale(float(w) / render_w, float(h) / render_h)
            if not self._paint_strokes_with_gpu_cache(
                painter,
                strokes,
                render_w,
                render_h,
                t_ms,
            ):
                painted_wet_layers: set[str] = set()
                for stroke in strokes:
                    if not stroke.is_active(t_ms):
                        continue
                    layer_id = self._stroke_layer_id(stroke)
                    if not self._layer_visibility.get(layer_id, True):
                        continue
                    if self._wet_canvas_layer_enabled(layer_id):
                        if layer_id in painted_wet_layers:
                            continue
                        mask = self._layer_masks.get(layer_id, [])
                        if len(mask) >= 3:
                            painter.save()
                            self._clip_to_layer_mask(painter, mask, render_w, render_h)
                        try:
                            self._paint_wet_canvas_layer(
                                painter,
                                strokes,
                                layer_id,
                                render_w,
                                render_h,
                                t_ms,
                            )
                        finally:
                            if len(mask) >= 3:
                                painter.restore()
                        painted_wet_layers.add(layer_id)
                        continue
                    mask = self._layer_masks.get(layer_id, [])
                    if len(mask) >= 3:
                        painter.save()
                        self._clip_to_layer_mask(painter, mask, render_w, render_h)
                    try:
                        self._paint_stroke(
                            painter,
                            stroke,
                            render_w,
                            render_h,
                            opacity_scale=self._layer_opacity.get(layer_id, 100) / 100.0,
                        )
                    finally:
                        if len(mask) >= 3:
                            painter.restore()
        finally:
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
                **self._current_brush_detail_kwargs(),
                layer_id=self._active_layer_id,
                source_tool="pen",
                point_pressure=list(self._current_pressure),
                point_tilt=list(self._current_tilt),
                point_tilt_x=list(self._current_tilt_x),
                point_tilt_y=list(self._current_tilt_y),
                point_rotation=list(self._current_rotation),
                point_tangential_pressure=list(self._current_tangential_pressure),
                point_load=list(self._current_load),
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

        self._paint_perspective_guides(painter, w, h)
        self._paint_symmetry_guide(painter, w, h)
        self._paint_pixel_grid_overlay(painter, w, h)
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
    def _qpoints_from_xy(points: list[tuple[float, float]]) -> list[QPointF]:
        return [QPointF(float(x), float(y)) for x, y in points]

    @staticmethod
    def _stroke_points_xy(stroke: Stroke, w: int, h: int) -> list[tuple[float, float]]:
        pts = [(float(p[0]) * w, float(p[1]) * h) for p in stroke.points]
        if getattr(stroke, "closed_path", False) and len(pts) >= 3:
            pts.append(pts[0])
        return pts

    @staticmethod
    def _brush_color_variant(color: QColor, alpha: int, *, light: int = 100) -> QColor:
        out = QColor(color)
        if light > 100:
            out = out.lighter(light)
        elif light < 100:
            out = out.darker(max(1, 200 - light))
        out.setAlpha(max(0, min(255, int(alpha))))
        return out

    @staticmethod
    def _oil_color_variant(
        color: QColor,
        alpha: int,
        *,
        hue_shift: float = 0.0,
        saturation_scale: float = 1.0,
        value_scale: float = 1.0,
    ) -> QColor:
        hue = color.hue()
        if hue < 0:
            hue = 0
        out = QColor.fromHsv(
            int((hue + hue_shift) % 360),
            max(0, min(255, int(round(color.saturation() * saturation_scale)))),
            max(0, min(255, int(round(color.value() * value_scale)))),
        )
        out.setAlpha(max(0, min(255, int(alpha))))
        return out

    @staticmethod
    def _draw_qt_polyline(painter: QPainter, points: list[tuple[float, float]], pen: QPen) -> None:
        qpts = DrawingCanvas._qpoints_from_xy(points)
        if len(qpts) == 1:
            painter.setPen(pen)
            painter.drawPoint(qpts[0])
        elif len(qpts) > 1:
            painter.setPen(pen)
            painter.drawPolyline(qpts)

    @staticmethod
    def _paint_rotated_dab(
        painter: QPainter,
        x: float,
        y: float,
        angle_rad: float,
        length: float,
        thickness: float,
        color: QColor,
        *,
        rounded: bool = True,
    ) -> None:
        painter.save()
        try:
            painter.translate(QPointF(x, y))
            painter.rotate(math.degrees(angle_rad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            rect = QRectF(-length / 2.0, -thickness / 2.0, length, thickness)
            if rounded:
                radius = max(1.0, min(thickness / 2.0, 9.0))
                painter.drawRoundedRect(rect, radius, radius)
            else:
                painter.drawRect(rect)
        finally:
            painter.restore()

    @staticmethod
    def _paint_textured_stroke(
        painter: QPainter,
        stroke: Stroke,
        w: int,
        h: int,
        color: QColor,
    ) -> None:
        style = _normalize_paint_brush_style(getattr(stroke, "brush_style", "round"))
        points = DrawingCanvas._stroke_points_xy(stroke, w, h)
        if not points:
            return
        width = max(1.0, float(stroke.width_px))
        alpha = max(0, min(255, color.alpha()))
        salt = _paint_style_salt(style)

        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if len(points) == 1:
                x, y = points[0]
                base = DrawingCanvas._brush_color_variant(color, alpha, light=108)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(base)
                painter.drawEllipse(QPointF(x, y), width * 0.5, width * 0.36)
                return

            profile = DESIGNER_BRUSH_RENDER_PROFILES.get(style)
            if profile is not None:
                mode = str(profile["mode"])
                body = float(profile.get("body", 1.0))
                profile_alpha = float(profile.get("alpha", 0.5))
                if mode in {"soft", "soft_flat"}:
                    layers = max(2, int(profile.get("layers", 5)))
                    for layer in range(layers, 0, -1):
                        ratio = layer / layers
                        pen = QPen(
                            DrawingCanvas._brush_color_variant(
                                color,
                                int(alpha * profile_alpha * (0.26 + (1.0 - ratio) * 0.20)),
                                light=96 + int((1.0 - ratio) * 18),
                            ),
                            max(1.0, width * body * (0.30 + ratio * 0.70)),
                        )
                        pen.setCapStyle(
                            Qt.PenCapStyle.SquareCap if mode == "soft_flat" else Qt.PenCapStyle.RoundCap
                        )
                        pen.setJoinStyle(
                            Qt.PenJoinStyle.BevelJoin if mode == "soft_flat" else Qt.PenJoinStyle.RoundJoin
                        )
                        DrawingCanvas._draw_qt_polyline(painter, points, pen)
                    return

                if mode == "flat":
                    base = QPen(
                        DrawingCanvas._brush_color_variant(color, int(alpha * profile_alpha), light=96),
                        max(1.0, width * body),
                    )
                    base.setCapStyle(Qt.PenCapStyle.SquareCap)
                    base.setJoinStyle(Qt.PenJoinStyle.BevelJoin)
                    DrawingCanvas._draw_qt_polyline(painter, points, base)
                    for lane, pos in enumerate((-0.36, 0.0, 0.36)):
                        lane_color = DrawingCanvas._brush_color_variant(
                            color,
                            int(alpha * (0.12 + lane * 0.04)),
                            light=126 if pos < 0 else 70 if pos > 0 else 104,
                        )
                        lane_pen = QPen(lane_color, max(1.0, width * 0.055))
                        lane_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                        DrawingCanvas._draw_qt_polyline(
                            painter, _offset_polyline_xy(points, pos * width * body), lane_pen
                        )
                    return

                if mode == "pixel":
                    step = max(1.0, width * float(profile.get("spacing", 0.72)))
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(DrawingCanvas._brush_color_variant(color, alpha, light=100))
                    size = max(1, int(round(width * body)))
                    for x, y, _angle, _idx in _sample_polyline_xy(points, step):
                        painter.drawRect(
                            int(round(x - size / 2)),
                            int(round(y - size / 2)),
                            size,
                            size,
                        )
                    return

                if mode in {"strands", "paint"}:
                    lanes = max(2, int(profile.get("lanes", 5)))
                    if mode == "paint":
                        under = QPen(
                            DrawingCanvas._brush_color_variant(
                                color, int(alpha * profile_alpha * 0.62), light=88
                            ),
                            max(1.0, width * body),
                        )
                        under.setCapStyle(Qt.PenCapStyle.SquareCap)
                        DrawingCanvas._draw_qt_polyline(painter, points, under)
                    for lane in range(lanes):
                        pos = 0.0 if lanes == 1 else (lane - (lanes - 1) / 2.0) / ((lanes - 1) / 2.0)
                        noise = _paint_noise(lane, salt + 131)
                        pen = QPen(
                            DrawingCanvas._brush_color_variant(
                                color,
                                int(alpha * profile_alpha * (0.32 + noise * 0.34)),
                                light=70 + int(noise * 68),
                            ),
                            max(
                                0.8,
                                width
                                * body
                                * ((0.13 + noise * 0.08) if mode == "strands" else (0.035 + noise * 0.035)),
                            ),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        if mode == "paint" and noise > 0.58:
                            pen.setDashPattern([max(2.0, width * 0.48), max(1.0, width * 0.12)])
                        DrawingCanvas._draw_qt_polyline(
                            painter,
                            _offset_polyline_xy(points, pos * width * body * 0.48),
                            pen,
                        )
                    return

                if mode == "wash":
                    under = QPen(
                        DrawingCanvas._brush_color_variant(
                            color, int(alpha * profile_alpha), light=110
                        ),
                        max(2.0, width * body),
                    )
                    under.setCapStyle(Qt.PenCapStyle.RoundCap)
                    under.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    DrawingCanvas._draw_qt_polyline(painter, points, under)
                    for pos, light in ((-0.46, 134), (0.46, 72)):
                        edge = QPen(
                            DrawingCanvas._brush_color_variant(
                                color, int(alpha * profile_alpha * 0.76), light=light
                            ),
                            max(1.0, width * 0.06),
                        )
                        edge.setCapStyle(Qt.PenCapStyle.RoundCap)
                        DrawingCanvas._draw_qt_polyline(
                            painter, _offset_polyline_xy(points, pos * width * body), edge
                        )
                    for x, y, _angle, idx in _sample_polyline_xy(points, max(8.0, width * 0.72)):
                        noise = _paint_noise(idx, salt + 149)
                        bloom = DrawingCanvas._brush_color_variant(
                            color, int(alpha * profile_alpha * (0.16 + noise * 0.20)), light=122
                        )
                        painter.setPen(Qt.PenStyle.NoPen)
                        painter.setBrush(bloom)
                        radius = width * (0.16 + noise * 0.18)
                        painter.drawEllipse(QPointF(x, y), radius, radius * 0.76)
                    return

                step = max(2.0, width * (0.16 if mode == "cloud" else 0.22))
                density = max(3, int(profile.get("density", 8)))
                samples = _sample_polyline_xy(points, step)
                for x, y, angle, idx in samples:
                    noise = _paint_noise(idx, salt + 163)
                    if mode in {"grain", "crosshatch"} and noise < 0.28:
                        continue
                    count = max(2, density // 4)
                    for dab_index in range(count):
                        grain = _paint_noise(idx * density + dab_index, salt + 179)
                        side = (grain - 0.5) * width * body * (1.50 if mode == "cloud" else 1.05)
                        along = (
                            _paint_noise(idx * density + dab_index, salt + 191) - 0.5
                        ) * width * body
                        px = x + math.cos(angle) * along + math.cos(angle + math.pi / 2.0) * side
                        py = y + math.sin(angle) * along + math.sin(angle + math.pi / 2.0) * side
                        dab_alpha = int(
                            alpha
                            * profile_alpha
                            * (0.30 + grain * 0.48)
                            * (0.46 if mode == "cloud" else 1.0)
                        )
                        dab = DrawingCanvas._brush_color_variant(
                            color, dab_alpha, light=78 + int(grain * 68)
                        )
                        if mode in {"scatter", "cloud"}:
                            painter.setPen(Qt.PenStyle.NoPen)
                            painter.setBrush(dab)
                            radius = width * body * (
                                (0.06 + grain * 0.13)
                                if mode == "scatter"
                                else (0.12 + grain * 0.24)
                            )
                            painter.drawEllipse(
                                QPointF(px, py),
                                max(0.8, radius),
                                max(0.8, radius * (0.66 + grain * 0.42)),
                            )
                        else:
                            dab_angle = angle + (grain - 0.5) * (
                                1.6 if mode == "crosshatch" else 0.8
                            )
                            DrawingCanvas._paint_rotated_dab(
                                painter,
                                px,
                                py,
                                dab_angle,
                                width * body * (0.10 + grain * 0.32),
                                max(0.8, width * body * (0.025 + grain * 0.055)),
                                dab,
                                rounded=mode != "crosshatch",
                            )
                return

            if style in {"loaded_oil", "impasto_oil", "oil_smear", "soft_oil_glaze"}:
                base_width = {
                    "loaded_oil": 0.92,
                    "impasto_oil": 1.08,
                    "oil_smear": 1.22,
                    "soft_oil_glaze": 1.46,
                }[style]
                base_alpha = {
                    "loaded_oil": 0.34,
                    "impasto_oil": 0.42,
                    "oil_smear": 0.26,
                    "soft_oil_glaze": 0.18,
                }[style]
                base_pen = QPen(
                    DrawingCanvas._oil_color_variant(
                        color,
                        int(alpha * base_alpha),
                        saturation_scale=0.92,
                        value_scale=0.78 if style == "impasto_oil" else 0.90,
                    ),
                    max(2.0, width * base_width),
                )
                base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                base_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                DrawingCanvas._draw_qt_polyline(painter, points, base_pen)

                if style == "soft_oil_glaze":
                    for lane in range(5):
                        pos = (lane - 2) / 2.0
                        noise = _paint_noise(lane, salt)
                        pen = QPen(
                            DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.08 + noise * 0.08)),
                                hue_shift=(noise - 0.5) * 10,
                                saturation_scale=0.75 + noise * 0.20,
                                value_scale=1.03 + noise * 0.18,
                            ),
                            max(1.0, width * (0.13 + noise * 0.05)),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        DrawingCanvas._draw_qt_polyline(
                            painter,
                            _offset_polyline_xy(points, pos * width * 0.40),
                            pen,
                        )
                    return

                samples = _sample_polyline_xy(
                    points,
                    max(4.0, width * (0.24 if style == "loaded_oil" else 0.30)),
                )
                for x, y, angle, idx in samples:
                    noise = _paint_noise(idx, salt)
                    side_noise = _paint_noise(idx, salt + 23)
                    side = (side_noise - 0.5) * width * (0.82 if style != "oil_smear" else 1.10)
                    px = x + math.cos(angle + math.pi / 2.0) * side
                    py = y + math.sin(angle + math.pi / 2.0) * side
                    length = width * (
                        0.72 + noise * 0.76
                        if style != "oil_smear"
                        else 1.08 + noise * 1.10
                    )
                    thickness = max(
                        1.0,
                        width * (
                            0.20 + noise * 0.18
                            if style == "loaded_oil"
                            else 0.11 + noise * 0.13
                        ),
                    )
                    dab = DrawingCanvas._oil_color_variant(
                        color,
                        int(alpha * (0.19 + noise * (0.23 if style == "impasto_oil" else 0.18))),
                        hue_shift=(noise - 0.5) * (18 if style == "loaded_oil" else 10),
                        saturation_scale=0.86 + noise * 0.28,
                        value_scale=0.76 + noise * 0.52,
                    )
                    DrawingCanvas._paint_rotated_dab(
                        painter,
                        px,
                        py,
                        angle + (noise - 0.5) * (0.34 if style == "loaded_oil" else 0.18),
                        length,
                        thickness,
                        dab,
                        rounded=style != "loaded_oil",
                    )

                    if style in {"loaded_oil", "impasto_oil"} and noise > 0.26:
                        normal = angle + math.pi / 2.0
                        hi = DrawingCanvas._oil_color_variant(
                            color,
                            int(alpha * (0.14 + noise * 0.12)),
                            hue_shift=(noise - 0.5) * 8,
                            saturation_scale=0.72,
                            value_scale=1.42,
                        )
                        sh = DrawingCanvas._oil_color_variant(
                            color,
                            int(alpha * (0.10 + noise * 0.10)),
                            hue_shift=(noise - 0.5) * 6,
                            saturation_scale=1.02,
                            value_scale=0.46,
                        )
                        ridge_len = length * (0.54 + noise * 0.28)
                        ridge_thick = max(1.0, thickness * 0.22)
                        DrawingCanvas._paint_rotated_dab(
                            painter,
                            px + math.cos(normal) * thickness * 0.32,
                            py + math.sin(normal) * thickness * 0.32,
                            angle,
                            ridge_len,
                            ridge_thick,
                            hi,
                        )
                        DrawingCanvas._paint_rotated_dab(
                            painter,
                            px - math.cos(normal) * thickness * 0.38,
                            py - math.sin(normal) * thickness * 0.38,
                            angle,
                            ridge_len * 0.82,
                            ridge_thick,
                            sh,
                        )

                if style == "impasto_oil":
                    for lane in range(11):
                        pos = (lane - 5) / 5.0
                        noise = _paint_noise(lane, salt + 61)
                        pen = QPen(
                            DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.08 + noise * 0.09)),
                                hue_shift=(noise - 0.5) * 9,
                                saturation_scale=0.90,
                                value_scale=1.22 if pos < 0 else 0.68,
                            ),
                            max(1.0, width * (0.035 + noise * 0.035)),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                        DrawingCanvas._draw_qt_polyline(
                            painter,
                            _offset_polyline_xy(points, pos * width * 0.50),
                            pen,
                        )
                return

            if style in {
                "filbert_oil",
                "flat_hog_oil",
                "fan_bristle_oil",
                "rigger_oil",
                "scumble_oil",
                "stipple_oil",
                "knife_scrape_oil",
            }:
                if style == "filbert_oil":
                    under = QPen(
                        DrawingCanvas._oil_color_variant(
                            color, int(alpha * 0.46), saturation_scale=0.94, value_scale=0.82
                        ),
                        max(2.0, width * 0.78),
                    )
                    under.setCapStyle(Qt.PenCapStyle.RoundCap)
                    under.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    DrawingCanvas._draw_qt_polyline(painter, points, under)
                    for x, y, angle, idx in _sample_polyline_xy(points, max(3.0, width * 0.20)):
                        noise = _paint_noise(idx, salt)
                        side = (_paint_noise(idx, salt + 19) - 0.5) * width * 0.42
                        normal = angle + math.pi / 2.0
                        dab = DrawingCanvas._oil_color_variant(
                            color,
                            int(alpha * (0.24 + noise * 0.20)),
                            hue_shift=(noise - 0.5) * 8,
                            saturation_scale=0.88 + noise * 0.18,
                            value_scale=0.74 + noise * 0.44,
                        )
                        DrawingCanvas._paint_rotated_dab(
                            painter,
                            x + math.cos(normal) * side,
                            y + math.sin(normal) * side,
                            angle,
                            width * (0.46 + noise * 0.48),
                            max(1.0, width * (0.14 + noise * 0.14)),
                            dab,
                            rounded=True,
                        )
                    return

                if style == "flat_hog_oil":
                    base = QPen(
                        DrawingCanvas._oil_color_variant(
                            color, int(alpha * 0.50), saturation_scale=0.92, value_scale=0.78
                        ),
                        max(2.0, width * 0.82),
                    )
                    base.setCapStyle(Qt.PenCapStyle.SquareCap)
                    base.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                    DrawingCanvas._draw_qt_polyline(painter, points, base)
                    for lane in range(15):
                        pos = (lane - 7) / 7.0
                        noise = _paint_noise(lane, salt + 31)
                        pen = QPen(
                            DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.13 + noise * 0.16)),
                                saturation_scale=0.90,
                                value_scale=1.28 if pos < 0 else 0.62,
                            ),
                            max(1.0, width * (0.028 + noise * 0.032)),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                        if noise > 0.46:
                            pen.setDashPattern([max(2.0, width * 0.62), max(1.0, width * 0.12)])
                        DrawingCanvas._draw_qt_polyline(
                            painter, _offset_polyline_xy(points, pos * width * 0.46), pen
                        )
                    return

                if style == "fan_bristle_oil":
                    for lane in range(21):
                        pos = (lane - 10) / 10.0
                        noise = _paint_noise(lane, salt + 43)
                        spread = math.copysign(abs(pos) ** 0.78, pos)
                        pen = QPen(
                            DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.12 + noise * 0.22) * (1.0 - abs(pos) * 0.24)),
                                saturation_scale=0.84 + noise * 0.22,
                                value_scale=0.68 + noise * 0.58,
                            ),
                            max(0.8, width * (0.018 + noise * 0.030)),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        pen.setDashPattern(
                            [max(2.0, width * (0.28 + noise * 0.34)), max(1.0, width * 0.16)]
                        )
                        DrawingCanvas._draw_qt_polyline(
                            painter,
                            _offset_polyline_xy(points, spread * width * 0.54),
                            pen,
                        )
                    return

                if style == "rigger_oil":
                    core = QPen(
                        DrawingCanvas._oil_color_variant(
                            color, int(alpha * 0.72), saturation_scale=0.96, value_scale=0.88
                        ),
                        max(1.0, width * 0.54),
                    )
                    core.setCapStyle(Qt.PenCapStyle.RoundCap)
                    core.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    DrawingCanvas._draw_qt_polyline(painter, points, core)
                    for lane, pos in enumerate((-0.22, 0.0, 0.22)):
                        noise = _paint_noise(lane, salt + 59)
                        pen = QPen(
                            DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.18 + noise * 0.18)),
                                value_scale=1.30 if pos < 0 else 0.68,
                            ),
                            max(0.7, width * 0.10),
                        )
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        DrawingCanvas._draw_qt_polyline(
                            painter, _offset_polyline_xy(points, pos * width), pen
                        )
                    return

                if style in {"scumble_oil", "stipple_oil"}:
                    step = max(
                        3.0,
                        width * (0.24 if style == "stipple_oil" else 0.20),
                    )
                    for x, y, angle, idx in _sample_polyline_xy(points, step):
                        noise = _paint_noise(idx, salt)
                        if style == "scumble_oil" and noise < 0.42:
                            continue
                        cluster_count = 3 if style == "stipple_oil" else 2
                        for cluster in range(cluster_count):
                            grain = _paint_noise(idx * 7 + cluster, salt + 71)
                            side = (grain - 0.5) * width * (1.0 if style == "stipple_oil" else 1.18)
                            along = (_paint_noise(idx * 11 + cluster, salt + 83) - 0.5) * width * 0.44
                            px = x + math.cos(angle) * along + math.cos(angle + math.pi / 2.0) * side
                            py = y + math.sin(angle) * along + math.sin(angle + math.pi / 2.0) * side
                            dab = DrawingCanvas._oil_color_variant(
                                color,
                                int(alpha * (0.18 + grain * 0.28)),
                                hue_shift=(grain - 0.5) * 8,
                                saturation_scale=0.88,
                                value_scale=0.72 + grain * 0.58,
                            )
                            if style == "stipple_oil":
                                painter.setPen(Qt.PenStyle.NoPen)
                                painter.setBrush(dab)
                                radius = max(1.0, width * (0.07 + grain * 0.12))
                                painter.drawEllipse(QPointF(px, py), radius, radius * (0.72 + grain * 0.3))
                            else:
                                DrawingCanvas._paint_rotated_dab(
                                    painter,
                                    px,
                                    py,
                                    angle + (grain - 0.5) * 0.34,
                                    width * (0.28 + grain * 0.55),
                                    max(1.0, width * (0.045 + grain * 0.075)),
                                    dab,
                                    rounded=False,
                                )
                    return

                base = QPen(
                    DrawingCanvas._oil_color_variant(
                        color, int(alpha * 0.24), saturation_scale=0.88, value_scale=0.72
                    ),
                    max(2.0, width * 0.62),
                )
                base.setCapStyle(Qt.PenCapStyle.SquareCap)
                base.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                DrawingCanvas._draw_qt_polyline(painter, points, base)
                for x, y, angle, idx in _sample_polyline_xy(points, max(7.0, width * 0.42)):
                    noise = _paint_noise(idx, salt + 97)
                    if noise < 0.26:
                        continue
                    side = (_paint_noise(idx, salt + 101) - 0.5) * width * 0.72
                    normal = angle + math.pi / 2.0
                    dab = DrawingCanvas._oil_color_variant(
                        color,
                        int(alpha * (0.22 + noise * 0.28)),
                        saturation_scale=0.90,
                        value_scale=0.62 + noise * 0.72,
                    )
                    DrawingCanvas._paint_rotated_dab(
                        painter,
                        x + math.cos(normal) * side,
                        y + math.sin(normal) * side,
                        angle,
                        width * (0.70 + noise * 1.10),
                        max(1.0, width * (0.055 + noise * 0.070)),
                        dab,
                        rounded=False,
                    )
                return

            if style == "palette_knife":
                base_pen = QPen(
                    DrawingCanvas._brush_color_variant(color, int(alpha * 0.72), light=105),
                    max(2.0, width * 0.78),
                )
                base_pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                base_pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                DrawingCanvas._draw_qt_polyline(painter, points, base_pen)
                for offset, light, factor in (
                    (-width * 0.28, 142, 0.42),
                    (width * 0.26, 74, 0.30),
                    (0.0, 118, 0.22),
                ):
                    pen = QPen(
                        DrawingCanvas._brush_color_variant(color, int(alpha * factor), light=light),
                        max(1.0, width * 0.13),
                    )
                    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
                    DrawingCanvas._draw_qt_polyline(painter, _offset_polyline_xy(points, offset), pen)
                for x, y, angle, idx in _sample_polyline_xy(points, max(8.0, width * 0.72)):
                    noise = _paint_noise(idx, salt)
                    dab = DrawingCanvas._brush_color_variant(
                        color,
                        int(alpha * (0.18 + noise * 0.18)),
                        light=92 + int(noise * 44),
                    )
                    DrawingCanvas._paint_rotated_dab(
                        painter,
                        x,
                        y + (noise - 0.5) * width * 0.22,
                        angle + (noise - 0.5) * 0.18,
                        width * (1.0 + noise * 0.75),
                        max(1.0, width * 0.10),
                        dab,
                        rounded=False,
                    )
                return

            if style == "real_wet_oil":
                under = QPen(
                    DrawingCanvas._brush_color_variant(color, int(alpha * 0.38), light=88),
                    max(2.0, width * 1.18),
                )
                under.setCapStyle(Qt.PenCapStyle.RoundCap)
                under.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                DrawingCanvas._draw_qt_polyline(painter, points, under)
                for lane in range(9):
                    pos = (lane - 4) / 4.0
                    noise = _paint_noise(lane, salt)
                    light = 82 + int(noise * 72) + (16 if pos < -0.15 else 0)
                    lane_alpha = int(alpha * (0.20 + 0.13 * (1.0 - abs(pos))))
                    lane_width = max(1.0, width * (0.08 + 0.045 * noise))
                    pen = QPen(
                        DrawingCanvas._brush_color_variant(color, lane_alpha, light=light),
                        lane_width,
                    )
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    offset = pos * width * (0.38 + noise * 0.12)
                    DrawingCanvas._draw_qt_polyline(painter, _offset_polyline_xy(points, offset), pen)
                for x, y, angle, idx in _sample_polyline_xy(points, max(5.0, width * 0.34)):
                    noise = _paint_noise(idx, salt + 17)
                    if noise < 0.16:
                        continue
                    dab = DrawingCanvas._brush_color_variant(
                        color,
                        int(alpha * (0.09 + noise * 0.18)),
                        light=95 + int(noise * 52),
                    )
                    side = (_paint_noise(idx, salt + 29) - 0.5) * width * 0.72
                    DrawingCanvas._paint_rotated_dab(
                        painter,
                        x + math.cos(angle + math.pi / 2.0) * side,
                        y + math.sin(angle + math.pi / 2.0) * side,
                        angle + (noise - 0.5) * 0.28,
                        width * (0.35 + noise * 0.58),
                        max(1.0, width * (0.06 + noise * 0.08)),
                        dab,
                    )
                return

            if style == "bristle_oil":
                for lane in range(13):
                    pos = (lane - 6) / 6.0
                    noise = _paint_noise(lane, salt)
                    lane_alpha = int(alpha * (0.24 + noise * 0.18))
                    pen = QPen(
                        DrawingCanvas._brush_color_variant(color, lane_alpha, light=78 + int(noise * 78)),
                        max(1.0, width * (0.055 + 0.025 * noise)),
                    )
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                    if noise > 0.58:
                        pen.setDashPattern([max(2.0, width * 0.42), max(1.0, width * 0.20)])
                    DrawingCanvas._draw_qt_polyline(
                        painter,
                        _offset_polyline_xy(points, pos * width * 0.46),
                        pen,
                    )
                return

            skip_floor = 0.34 if style == "dry_oil" else 0.22
            step = max(2.5, width * (0.26 if style == "textured_chalk" else 0.34))
            for x, y, angle, idx in _sample_polyline_xy(points, step):
                noise = _paint_noise(idx, salt)
                if noise < skip_floor:
                    continue
                side = (_paint_noise(idx, salt + 41) - 0.5) * width
                light = 78 + int(noise * 76)
                dab_alpha = int(alpha * (0.16 + noise * (0.30 if style == "dry_oil" else 0.22)))
                dab = DrawingCanvas._brush_color_variant(color, dab_alpha, light=light)
                px = x + math.cos(angle + math.pi / 2.0) * side
                py = y + math.sin(angle + math.pi / 2.0) * side
                if style == "textured_chalk":
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(dab)
                    radius = max(0.8, width * (0.06 + noise * 0.12))
                    painter.drawEllipse(QPointF(px, py), radius * 1.55, radius)
            else:
                DrawingCanvas._paint_rotated_dab(
                    painter,
                    px,
                    py,
                        angle + (noise - 0.5) * 0.7,
                        width * (0.20 + noise * 0.44),
                        max(1.0, width * (0.045 + noise * 0.08)),
                        dab,
                    )
        finally:
            painter.restore()

    @staticmethod
    def _stroke_uses_tip_detail(stroke: Stroke) -> bool:
        return any(
            (
                int(getattr(stroke, "brush_hardness", 100)) != 100,
                int(getattr(stroke, "brush_spacing", 25)) != 25,
                int(getattr(stroke, "brush_angle", 0)) != 0,
                int(getattr(stroke, "brush_roundness", 100)) != 100,
                bool(getattr(stroke, "brush_flip_x", False)),
                bool(getattr(stroke, "brush_flip_y", False)),
            )
        )

    @staticmethod
    def _paint_rotated_ellipse(
        painter: QPainter,
        x: float,
        y: float,
        angle_rad: float,
        width: float,
        height: float,
        color: QColor,
    ) -> None:
        painter.save()
        try:
            painter.translate(QPointF(x, y))
            painter.rotate(math.degrees(angle_rad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(-width / 2.0, -height / 2.0, width, height))
        finally:
            painter.restore()

    @staticmethod
    def _paint_tip_detail_stroke(
        painter: QPainter,
        stroke: Stroke,
        w: int,
        h: int,
        color: QColor,
        style: str,
    ) -> None:
        points = DrawingCanvas._stroke_points_xy(stroke, w, h)
        if not points:
            return
        width = max(1.0, float(stroke.width_px))
        alpha = max(0, min(255, int(color.alpha())))
        spacing = max(1, min(200, int(getattr(stroke, "brush_spacing", 25))))
        hardness = max(1, min(100, int(getattr(stroke, "brush_hardness", 100))))
        roundness = max(10, min(100, int(getattr(stroke, "brush_roundness", 100)))) / 100.0
        angle_offset = math.radians(max(-180, min(180, int(getattr(stroke, "brush_angle", 0)))))
        if bool(getattr(stroke, "brush_flip_x", False)):
            angle_offset = -angle_offset
        if bool(getattr(stroke, "brush_flip_y", False)):
            angle_offset += math.pi
        step = max(1.0, width * spacing / 100.0)
        samples = _sample_polyline_xy(points, step)
        if len(points) == 1 and not samples:
            samples = [(points[0][0], points[0][1], 0.0, 0)]
        painter.save()
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for x, y, tangent, idx in samples:
                if style == "dashed" and idx % 8 in {4, 5, 6, 7}:
                    continue
                dab_angle = tangent + angle_offset
                dab_width = width * (1.16 if style == "marker" else 1.0)
                dab_height = max(0.6, width * roundness)
                outer = QColor(color)
                outer.setAlpha(int(alpha * (0.10 + hardness * 0.0021)))
                inner = QColor(color)
                inner_alpha = alpha
                if style == "highlighter":
                    inner_alpha = min(inner_alpha, 122)
                    outer.setAlpha(min(80, outer.alpha()))
                inner.setAlpha(max(1, min(255, int(inner_alpha * (0.42 + hardness * 0.0058)))))
                DrawingCanvas._paint_rotated_ellipse(
                    painter,
                    x,
                    y,
                    dab_angle,
                    dab_width,
                    dab_height,
                    outer,
                )
                core_scale = 0.34 + hardness * 0.0062
                DrawingCanvas._paint_rotated_ellipse(
                    painter,
                    x,
                    y,
                    dab_angle,
                    max(0.5, dab_width * core_scale),
                    max(0.5, dab_height * core_scale),
                    inner,
                )
        finally:
            painter.restore()

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
        style = _normalize_paint_brush_style(getattr(stroke, "brush_style", "round"))
        from app.painter_brush_engine_v2 import (
            paint_bristle_v2,
            paint_dynamic_basic_stroke,
        )

        if paint_bristle_v2(painter, stroke, w, h, color):
            return
        if style in PAINT_TEXTURED_BRUSH_STYLES:
            DrawingCanvas._paint_textured_stroke(painter, stroke, w, h, color)
            return
        if DrawingCanvas._stroke_uses_tip_detail(stroke):
            DrawingCanvas._paint_tip_detail_stroke(painter, stroke, w, h, color, style)
            return
        if paint_dynamic_basic_stroke(painter, stroke, w, h, color):
            return
        pen = QPen(color, stroke.width_px)
        DrawingCanvas._configure_pen_for_style(pen, style)
        painter.setPen(pen)
        pts = [QPointF(p[0] * w, p[1] * h) for p in stroke.points]
        if len(pts) == 1:
            painter.drawPoint(pts[0])
        elif getattr(stroke, "closed_path", False) and len(pts) >= 3:
            painter.drawPolyline(pts + [pts[0]])
        else:
            painter.drawPolyline(pts)

    def _paint_strokes_with_gpu_cache(
        self,
        painter: QPainter,
        strokes: list[Stroke],
        w: int,
        h: int,
        t_ms: int,
    ) -> bool:
        if any(
            self._wet_canvas_layer_enabled(layer_id)
            for layer_id in self._layer_wet_canvas_settings
        ):
            self._painter_canvas_renderer_status = {
                "renderer": "painter_canvas_qpainter_wet_layer_v1",
                "active": "qpainter",
                "fallback": True,
                "fallback_from": "opengl",
                "reason": "wet_canvas_requires_editable_color_exchange",
                "remote_safe": True,
                "size": [int(w), int(h)],
            }
            return False
        if not strokes:
            atlas = getattr(self, "_painter_canvas_stroke_atlas", None)
            if hasattr(atlas, "clear"):
                atlas.clear()
            self._painter_canvas_gpu_cache_key = None
            self._painter_canvas_gpu_cache_image = None
            self._painter_canvas_gpu_failure_key = None
            self._painter_canvas_renderer_status = {
                "renderer": "painter_canvas_none_v1",
                "active": "none",
                "fallback": False,
                "reason": "no_strokes",
                "remote_safe": True,
                "size": [int(w), int(h)],
            }
            return True
        try:
            from app.painter_opengl import (
                PainterCanvasStrokeAtlas,
                canvas_stroke_gpu_signature,
            )

            signature = canvas_stroke_gpu_signature(
                strokes,
                width=w,
                height=h,
                time_ms=t_ms,
                layer_visibility=self._layer_visibility,
                layer_opacity=self._layer_opacity,
                layer_masks=self._layer_masks,
            )
            if signature and signature == getattr(self, "_painter_canvas_gpu_failure_key", None):
                return False
            atlas = getattr(self, "_painter_canvas_stroke_atlas", None)
            if atlas is None:
                atlas = PainterCanvasStrokeAtlas()
                self._painter_canvas_stroke_atlas = atlas
            image, report = atlas.render(
                strokes,
                width=w,
                height=h,
                time_ms=t_ms,
                layer_visibility=self._layer_visibility,
                layer_opacity=self._layer_opacity,
                layer_masks=self._layer_masks,
            )
            if image.isNull():
                raise RuntimeError("Painter canvas OpenGL returned an empty image.")
            self._painter_canvas_gpu_cache_key = signature
            self._painter_canvas_gpu_cache_image = image
            self._painter_canvas_gpu_failure_key = None
            self._painter_canvas_renderer_status = {
                **dict(report or {}),
                "remote_safe": True,
            }
            painter.drawImage(0, 0, image)
            return True
        except Exception as exc:
            try:
                from app.painter_opengl import PAINTER_CANVAS_FALLBACK_RENDERER_ID
            except Exception:
                PAINTER_CANVAS_FALLBACK_RENDERER_ID = "painter_canvas_qpainter_strokes_v1"
            self._painter_canvas_gpu_cache_key = None
            self._painter_canvas_gpu_cache_image = None
            atlas = getattr(self, "_painter_canvas_stroke_atlas", None)
            if hasattr(atlas, "clear"):
                atlas.clear()
            self._painter_canvas_renderer_status = {
                "renderer": PAINTER_CANVAS_FALLBACK_RENDERER_ID,
                "active": "qpainter",
                "fallback": True,
                "fallback_from": "opengl",
                "reason": f"{type(exc).__name__}: {exc}",
                "remote_safe": True,
                "size": [int(w), int(h)],
            }
            try:
                self._painter_canvas_gpu_failure_key = canvas_stroke_gpu_signature(
                    strokes,
                    width=w,
                    height=h,
                    time_ms=t_ms,
                    layer_visibility=self._layer_visibility,
                    layer_opacity=self._layer_opacity,
                    layer_masks=self._layer_masks,
                )
            except Exception:
                self._painter_canvas_gpu_failure_key = None
            return False

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

    def _paint_perspective_guides(self, painter: QPainter, w: int, h: int) -> None:
        if not bool(getattr(self, "_perspective_guides_enabled", False)):
            return
        horizon = max(0.02, min(0.98, float(getattr(self, "_perspective_horizon_norm", 0.5) or 0.5)))
        left_vp = getattr(self, "_perspective_left_vp", (0.08, horizon)) or (0.08, horizon)
        right_vp = getattr(self, "_perspective_right_vp", (0.92, horizon)) or (0.92, horizon)
        lpt = QPointF(float(left_vp[0]) * w, float(left_vp[1]) * h)
        rpt = QPointF(float(right_vp[0]) * w, float(right_vp[1]) * h)
        y = horizon * h
        painter.save()
        try:
            horizon_pen = QPen(QColor(120, 190, 255, 112), 1.0)
            horizon_pen.setCosmetic(True)
            horizon_pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(horizon_pen)
            painter.drawLine(QPointF(0, y), QPointF(w, y))

            ray_pen = QPen(QColor(255, 191, 120, 76), 1.0)
            ray_pen.setCosmetic(True)
            painter.setPen(ray_pen)
            anchors = [
                QPointF(0, 0),
                QPointF(w * 0.25, 0),
                QPointF(w * 0.5, 0),
                QPointF(w * 0.75, 0),
                QPointF(w, 0),
                QPointF(0, h),
                QPointF(w * 0.25, h),
                QPointF(w * 0.5, h),
                QPointF(w * 0.75, h),
                QPointF(w, h),
            ]
            for anchor in anchors:
                painter.drawLine(lpt, anchor)
                painter.drawLine(rpt, anchor)

            painter.setBrush(QColor(120, 190, 255, 80))
            painter.setPen(QPen(QColor(230, 244, 255, 130), 1.0))
            painter.drawEllipse(lpt, 4.0, 4.0)
            painter.drawEllipse(rpt, 4.0, 4.0)
        finally:
            painter.restore()

    def _paint_symmetry_guide(self, painter: QPainter, w: int, h: int) -> None:
        if not bool(getattr(self, "_symmetry_guide_enabled", False)):
            return
        axis = str(getattr(self, "_symmetry_guide_axis", "vertical") or "vertical")
        position = max(0.02, min(0.98, float(getattr(self, "_symmetry_guide_position_norm", 0.5) or 0.5)))
        painter.save()
        try:
            glow = QPen(QColor(138, 255, 208, 52), 5.0)
            glow.setCosmetic(True)
            core = QPen(QColor(214, 255, 240, 150), 1.2)
            core.setCosmetic(True)
            core.setStyle(Qt.PenStyle.DashDotLine)
            if axis == "horizontal":
                y = position * h
                painter.setPen(glow)
                painter.drawLine(QPointF(0, y), QPointF(w, y))
                painter.setPen(core)
                painter.drawLine(QPointF(0, y), QPointF(w, y))
            else:
                x = position * w
                painter.setPen(glow)
                painter.drawLine(QPointF(x, 0), QPointF(x, h))
                painter.setPen(core)
                painter.drawLine(QPointF(x, 0), QPointF(x, h))
        finally:
            painter.restore()

    def _paint_pixel_grid_overlay(self, painter: QPainter, w: int, h: int) -> None:
        metrics = self._pixel_grid_metrics(w, h)
        if not bool(metrics.get("visible", False)):
            return
        doc_w, doc_h = tuple(getattr(self, "_document_size_px", (1, 1)))
        doc_w = max(1, int(doc_w))
        doc_h = max(1, int(doc_h))
        cell_w = max(0.01, float(metrics.get("cell_width_px", 0.0) or 0.0))
        cell_h = max(0.01, float(metrics.get("cell_height_px", 0.0) or 0.0))
        stride_x = max(1, int(metrics.get("stride_x", 1) or 1))
        stride_y = max(1, int(metrics.get("stride_y", 1) or 1))
        major_every = max(1, int(metrics.get("major_every", 8) or 8))

        clip = painter.clipBoundingRect()
        if not clip.isValid() or clip.width() <= 0.0 or clip.height() <= 0.0:
            clip = QRectF(0, 0, w, h)
        clip = clip.intersected(QRectF(0, 0, w, h))
        if clip.isEmpty():
            return

        first_x = max(0, int(math.floor(clip.left() / cell_w / stride_x)) * stride_x)
        last_x = min(doc_w, int(math.ceil(clip.right() / cell_w)) + stride_x)
        first_y = max(0, int(math.floor(clip.top() / cell_h / stride_y)) * stride_y)
        last_y = min(doc_h, int(math.ceil(clip.bottom() / cell_h)) + stride_y)

        minor_pen = QPen(QColor(142, 160, 190, 56), 1.0)
        minor_pen.setCosmetic(True)
        major_pen = QPen(QColor(238, 245, 255, 84), 1.0)
        major_pen.setCosmetic(True)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for src_x in range(first_x, last_x + 1, stride_x):
            x = float(src_x) * cell_w
            painter.setPen(major_pen if src_x % major_every == 0 else minor_pen)
            painter.drawLine(QPointF(x + 0.5, clip.top()), QPointF(x + 0.5, clip.bottom()))
        for src_y in range(first_y, last_y + 1, stride_y):
            y = float(src_y) * cell_h
            painter.setPen(major_pen if src_y % major_every == 0 else minor_pen)
            painter.drawLine(QPointF(clip.left(), y + 0.5), QPointF(clip.right(), y + 0.5))
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
        elif self._selection_drag_tool == "zoom_area":
            fill = QColor(104, 190, 255, 28)
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
        style = _normalize_paint_brush_style(style)
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

    def _clear_current_stroke(self) -> None:
        self._current_points = []
        self._current_pressure = []
        self._current_tilt = []
        self._current_tilt_x = []
        self._current_tilt_y = []
        self._current_rotation = []
        self._current_tangential_pressure = []
        self._current_load = []

    def _append_current_stroke_sample(
        self,
        point: QPointF,
        sample,
        *,
        force: bool = False,
    ) -> bool:
        if self._current_points and not force:
            previous = self._current_points[-1]
            if abs(point.x() - previous.x()) + abs(point.y() - previous.y()) < 2:
                return False
        previous = self._current_points[-1] if self._current_points else None
        self._current_points.append(QPointF(point))
        self._current_pressure.append(float(sample.pressure))
        self._current_tilt.append(float(sample.tilt))
        self._current_tilt_x.append(float(sample.tilt_x))
        self._current_tilt_y.append(float(sample.tilt_y))
        self._current_rotation.append(float(sample.rotation))
        self._current_tangential_pressure.append(float(sample.tangential_pressure))
        self._current_load.append(float(sample.load))
        self._update_current_stroke_dirty(point, previous)
        return True

    def _begin_current_stroke(self, point: QPointF, sample) -> None:
        self._clear_current_stroke()
        self._append_current_stroke_sample(point, sample, force=True)

    def _finish_current_stroke(self) -> None:
        if not self._current_points:
            return
        w = max(1, self.width())
        h = max(1, self.height())
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
            **self._current_brush_detail_kwargs(),
            layer_id=self._active_layer_id,
            source_tool="pen",
            point_pressure=list(self._current_pressure),
            point_tilt=list(self._current_tilt),
            point_tilt_x=list(self._current_tilt_x),
            point_tilt_y=list(self._current_tilt_y),
            point_rotation=list(self._current_rotation),
            point_tangential_pressure=list(self._current_tangential_pressure),
            point_load=list(self._current_load),
            start_ms=int(self._get_time_ms()),
            end_ms=None,
        )
        self._clear_current_stroke()
        self.stroke_added.emit(stroke)
        self.update()

    def tabletEvent(self, event: QTabletEvent) -> None:
        if self._tool not in {"pen", "eraser"}:
            event.ignore()
            return
        from app.painter_stylus import tablet_stylus_sample

        event_type = event.type()
        point = QPointF(event.position())
        pointer_name = str(event.pointerType()).casefold()
        erasing = self._tool == "eraser" or "eraser" in pointer_name
        if event_type == QEvent.Type.TabletPress:
            self._tablet_stroke_active = True
            if erasing:
                self._try_erase_at(point.x(), point.y())
            else:
                self._begin_current_stroke(point, tablet_stylus_sample(event))
        elif event_type == QEvent.Type.TabletMove and self._tablet_stroke_active:
            if erasing:
                self._try_erase_at(point.x(), point.y())
            else:
                self._append_current_stroke_sample(point, tablet_stylus_sample(event))
        elif event_type == QEvent.Type.TabletRelease and self._tablet_stroke_active:
            if not erasing:
                self._append_current_stroke_sample(
                    point,
                    tablet_stylus_sample(event),
                    force=True,
                )
                self._finish_current_stroke()
            self._tablet_stroke_active = False
        else:
            event.ignore()
            return
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._tablet_stroke_active:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if self._tool in {"zoom_in", "zoom_out"}:
            self.zoom_requested.emit(
                self._tool,
                max(0.0, min(1.0, pos.x() / max(1, self.width()))),
                max(0.0, min(1.0, pos.y() / max(1, self.height()))),
                0.0,
                0.0,
            )
            return
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
        if self._tool in {"rect_select", "ellipse_select", "crop", "zoom_area"}:
            self._selection_drag_tool = self._tool
            snapped = self._snap_canvas_point(pos)
            self._selection_drag_start = QPointF(snapped)
            self._selection_drag_current = QPointF(snapped)
            self.update()
            return
        if self._tool == "pen":
            from app.painter_stylus import mouse_stylus_sample

            self._begin_current_stroke(pos, mouse_stylus_sample())
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
        if self._tablet_stroke_active:
            return
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
        if self._selection_drag_start is not None and self._tool in {
            "rect_select",
            "ellipse_select",
            "crop",
            "zoom_area",
        }:
            self._selection_drag_current = self._snap_canvas_point(event.position())
            self.update()
            return
        if self._tool != "pen" or not self._current_points:
            return
        pos = event.position()
        from app.painter_stylus import mouse_stylus_sample

        self._append_current_stroke_sample(pos, mouse_stylus_sample())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._tablet_stroke_active:
            return
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
        if self._selection_drag_start is not None and self._tool in {
            "rect_select",
            "ellipse_select",
            "crop",
            "zoom_area",
        }:
            self._selection_drag_current = self._snap_canvas_point(event.position())
            rect = self._selection_drag_rect()
            tool = self._selection_drag_tool or self._tool
            self._selection_drag_start = None
            self._selection_drag_current = None
            self._selection_drag_tool = ""
            if rect.width() > 1.0 and rect.height() > 1.0:
                if tool == "zoom_area":
                    self.zoom_requested.emit(
                        "zoom_area",
                        rect.left() / max(1, self.width()),
                        rect.top() / max(1, self.height()),
                        rect.width() / max(1, self.width()),
                        rect.height() / max(1, self.height()),
                    )
                else:
                    shape = "ellipse" if tool == "ellipse_select" else "rect"
                    points = self._points_from_drag_rect(rect, shape=shape)
                    self.set_selection_snapshot(self._combine_selection(points))
            self.repaint_requested.emit()
            self.update()
            return
        if self._tool != "pen" or not self._current_points:
            return
        from app.painter_stylus import mouse_stylus_sample

        self._append_current_stroke_sample(
            event.position(),
            mouse_stylus_sample(),
            force=True,
        )
        self._finish_current_stroke()

    def _update_current_stroke_dirty(self, point: QPointF, previous: QPointF | None = None) -> None:
        radius = max(8.0, float(getattr(self, "_pen_width", 6.0) or 6.0) * 1.75)
        if previous is None:
            rect = QRectF(point.x() - radius, point.y() - radius, radius * 2.0, radius * 2.0)
        else:
            left = min(point.x(), previous.x()) - radius
            top = min(point.y(), previous.y()) - radius
            right = max(point.x(), previous.x()) + radius
            bottom = max(point.y(), previous.y()) + radius
            rect = QRectF(left, top, right - left, bottom - top)
        self.update(rect.toAlignedRect().intersected(self.rect()))

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
            **self._current_brush_detail_kwargs(),
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
    style = _normalize_paint_brush_style(style)
    if len(pts) == 1:
        x, y = pts[0]
        half = max(1, stroke_w // 2)
        draw.ellipse([x - half, y - half, x + half, y + half], fill=color)
        return
    draw_pts = list(pts)
    if closed and len(draw_pts) >= 3:
        draw_pts.append(draw_pts[0])
    if style in PAINT_TEXTURED_BRUSH_STYLES:
        _draw_pil_textured_stroke(draw, draw_pts, color, stroke_w, style)
    elif style == "dashed":
        _draw_pil_dashed_polyline(draw, draw_pts, color, stroke_w)
    elif style == "highlighter":
        hl = (color[0], color[1], color[2], min(color[3], 110))
        draw.line(draw_pts, fill=hl, width=max(2, stroke_w), joint="curve")
    else:
        draw.line(draw_pts, fill=color, width=stroke_w, joint="curve")


def _pil_color_variant(
    color: tuple[int, int, int, int],
    alpha: int,
    *,
    light: int = 100,
) -> tuple[int, int, int, int]:
    r, g, b, _a = color
    if light > 100:
        factor = min(2.0, (light - 100) / 100.0)
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
    elif light < 100:
        factor = max(0.0, light / 100.0)
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
    return (
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))),
        max(0, min(255, int(alpha))),
    )


def _pil_oil_color_variant(
    color: tuple[int, int, int, int],
    alpha: int,
    *,
    hue_shift: float = 0.0,
    saturation_scale: float = 1.0,
    value_scale: float = 1.0,
) -> tuple[int, int, int, int]:
    r, g, b, _a = color
    hue, saturation, value = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    hue = (hue + hue_shift / 360.0) % 1.0
    saturation = max(0.0, min(1.0, saturation * saturation_scale))
    value = max(0.0, min(1.0, value * value_scale))
    rr, gg, bb = colorsys.hsv_to_rgb(hue, saturation, value)
    return (
        max(0, min(255, int(round(rr * 255)))),
        max(0, min(255, int(round(gg * 255)))),
        max(0, min(255, int(round(bb * 255)))),
        max(0, min(255, int(alpha))),
    )


def _draw_pil_line(
    draw,
    points: list[tuple[float, float]],
    color: tuple[int, int, int, int],
    width: float,
) -> None:
    if not points:
        return
    int_points = [(int(round(x)), int(round(y))) for x, y in points]
    if len(int_points) == 1:
        x, y = int_points[0]
        half = max(1, int(round(width / 2.0)))
        draw.ellipse([x - half, y - half, x + half, y + half], fill=color)
    else:
        draw.line(int_points, fill=color, width=max(1, int(round(width))), joint="curve")


def _draw_pil_rotated_dab(
    draw,
    x: float,
    y: float,
    angle: float,
    length: float,
    thickness: float,
    color: tuple[int, int, int, int],
) -> None:
    dx = math.cos(angle) * length / 2.0
    dy = math.sin(angle) * length / 2.0
    draw.line(
        [(x - dx, y - dy), (x + dx, y + dy)],
        fill=color,
        width=max(1, int(round(thickness))),
    )


def _draw_pil_textured_stroke(
    draw,
    pts: list[tuple[int, int]],
    color: tuple[int, int, int, int],
    stroke_w: int,
    style: str,
) -> None:
    points = [(float(x), float(y)) for x, y in pts]
    if not points:
        return
    width = max(1.0, float(stroke_w))
    alpha = max(0, min(255, int(color[3])))
    salt = _paint_style_salt(style)

    if len(points) == 1:
        x, y = points[0]
        half_w = max(1.0, width / 2.0)
        draw.ellipse([x - half_w, y - half_w * 0.72, x + half_w, y + half_w * 0.72], fill=color)
        return

    profile = DESIGNER_BRUSH_RENDER_PROFILES.get(style)
    if profile is not None:
        mode = str(profile["mode"])
        body = float(profile.get("body", 1.0))
        profile_alpha = float(profile.get("alpha", 0.5))
        if mode in {"soft", "soft_flat"}:
            layers = max(2, int(profile.get("layers", 5)))
            for layer in range(layers, 0, -1):
                ratio = layer / layers
                _draw_pil_line(
                    draw,
                    points,
                    _pil_color_variant(
                        color,
                        int(alpha * profile_alpha * (0.26 + (1.0 - ratio) * 0.20)),
                        light=96 + int((1.0 - ratio) * 18),
                    ),
                    max(1.0, width * body * (0.30 + ratio * 0.70)),
                )
            return

        if mode == "flat":
            _draw_pil_line(
                draw,
                points,
                _pil_color_variant(color, int(alpha * profile_alpha), light=96),
                max(1.0, width * body),
            )
            for lane, pos in enumerate((-0.36, 0.0, 0.36)):
                _draw_pil_line(
                    draw,
                    _offset_polyline_xy(points, pos * width * body),
                    _pil_color_variant(
                        color,
                        int(alpha * (0.12 + lane * 0.04)),
                        light=126 if pos < 0 else 70 if pos > 0 else 104,
                    ),
                    max(1.0, width * 0.055),
                )
            return

        if mode == "pixel":
            step = max(1.0, width * float(profile.get("spacing", 0.72)))
            size = max(1, int(round(width * body)))
            fill = _pil_color_variant(color, alpha, light=100)
            for x, y, _angle, _idx in _sample_polyline_xy(points, step):
                draw.rectangle(
                    [x - size / 2, y - size / 2, x + size / 2, y + size / 2],
                    fill=fill,
                )
            return

        if mode in {"strands", "paint"}:
            lanes = max(2, int(profile.get("lanes", 5)))
            if mode == "paint":
                _draw_pil_line(
                    draw,
                    points,
                    _pil_color_variant(color, int(alpha * profile_alpha * 0.62), light=88),
                    max(1.0, width * body),
                )
            for lane in range(lanes):
                pos = 0.0 if lanes == 1 else (lane - (lanes - 1) / 2.0) / ((lanes - 1) / 2.0)
                noise = _paint_noise(lane, salt + 131)
                lane_points = _offset_polyline_xy(points, pos * width * body * 0.48)
                if mode == "paint" and noise > 0.58:
                    lane_points = lane_points[::2] or lane_points
                _draw_pil_line(
                    draw,
                    lane_points,
                    _pil_color_variant(
                        color,
                        int(alpha * profile_alpha * (0.32 + noise * 0.34)),
                        light=70 + int(noise * 68),
                    ),
                    max(
                        1.0,
                        width
                        * body
                        * ((0.13 + noise * 0.08) if mode == "strands" else (0.035 + noise * 0.035)),
                    ),
                )
            return

        if mode == "wash":
            _draw_pil_line(
                draw,
                points,
                _pil_color_variant(color, int(alpha * profile_alpha), light=110),
                max(2.0, width * body),
            )
            for pos, light in ((-0.46, 134), (0.46, 72)):
                _draw_pil_line(
                    draw,
                    _offset_polyline_xy(points, pos * width * body),
                    _pil_color_variant(
                        color, int(alpha * profile_alpha * 0.76), light=light
                    ),
                    max(1.0, width * 0.06),
                )
            for x, y, _angle, idx in _sample_polyline_xy(points, max(8.0, width * 0.72)):
                noise = _paint_noise(idx, salt + 149)
                radius = width * (0.16 + noise * 0.18)
                bloom = _pil_color_variant(
                    color, int(alpha * profile_alpha * (0.16 + noise * 0.20)), light=122
                )
                draw.ellipse(
                    [x - radius, y - radius * 0.76, x + radius, y + radius * 0.76],
                    fill=bloom,
                )
            return

        step = max(2.0, width * (0.16 if mode == "cloud" else 0.22))
        density = max(3, int(profile.get("density", 8)))
        for x, y, angle, idx in _sample_polyline_xy(points, step):
            noise = _paint_noise(idx, salt + 163)
            if mode in {"grain", "crosshatch"} and noise < 0.28:
                continue
            for dab_index in range(max(2, density // 4)):
                grain = _paint_noise(idx * density + dab_index, salt + 179)
                side = (grain - 0.5) * width * body * (1.50 if mode == "cloud" else 1.05)
                along = (
                    _paint_noise(idx * density + dab_index, salt + 191) - 0.5
                ) * width * body
                px = x + math.cos(angle) * along + math.cos(angle + math.pi / 2.0) * side
                py = y + math.sin(angle) * along + math.sin(angle + math.pi / 2.0) * side
                dab = _pil_color_variant(
                    color,
                    int(
                        alpha
                        * profile_alpha
                        * (0.30 + grain * 0.48)
                        * (0.46 if mode == "cloud" else 1.0)
                    ),
                    light=78 + int(grain * 68),
                )
                if mode in {"scatter", "cloud"}:
                    radius = width * body * (
                        (0.06 + grain * 0.13) if mode == "scatter" else (0.12 + grain * 0.24)
                    )
                    draw.ellipse(
                        [
                            px - radius,
                            py - radius * (0.66 + grain * 0.42),
                            px + radius,
                            py + radius * (0.66 + grain * 0.42),
                        ],
                        fill=dab,
                    )
                else:
                    _draw_pil_rotated_dab(
                        draw,
                        px,
                        py,
                        angle + (grain - 0.5) * (1.6 if mode == "crosshatch" else 0.8),
                        width * body * (0.10 + grain * 0.32),
                        max(1.0, width * body * (0.025 + grain * 0.055)),
                        dab,
                    )
        return

    if style in {"loaded_oil", "impasto_oil", "oil_smear", "soft_oil_glaze"}:
        base_width = {
            "loaded_oil": 0.92,
            "impasto_oil": 1.08,
            "oil_smear": 1.22,
            "soft_oil_glaze": 1.46,
        }[style]
        base_alpha = {
            "loaded_oil": 0.34,
            "impasto_oil": 0.42,
            "oil_smear": 0.26,
            "soft_oil_glaze": 0.18,
        }[style]
        _draw_pil_line(
            draw,
            points,
            _pil_oil_color_variant(
                color,
                int(alpha * base_alpha),
                saturation_scale=0.92,
                value_scale=0.78 if style == "impasto_oil" else 0.90,
            ),
            width * base_width,
        )
        if style == "soft_oil_glaze":
            for lane in range(5):
                pos = (lane - 2) / 2.0
                noise = _paint_noise(lane, salt)
                _draw_pil_line(
                    draw,
                    _offset_polyline_xy(points, pos * width * 0.40),
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.08 + noise * 0.08)),
                        hue_shift=(noise - 0.5) * 10,
                        saturation_scale=0.75 + noise * 0.20,
                        value_scale=1.03 + noise * 0.18,
                    ),
                    max(1.0, width * (0.13 + noise * 0.05)),
                )
            return

        samples = _sample_polyline_xy(
            points,
            max(4.0, width * (0.24 if style == "loaded_oil" else 0.30)),
        )
        for x, y, angle, idx in samples:
            noise = _paint_noise(idx, salt)
            side_noise = _paint_noise(idx, salt + 23)
            side = (side_noise - 0.5) * width * (0.82 if style != "oil_smear" else 1.10)
            px = x + math.cos(angle + math.pi / 2.0) * side
            py = y + math.sin(angle + math.pi / 2.0) * side
            length = width * (
                0.72 + noise * 0.76
                if style != "oil_smear"
                else 1.08 + noise * 1.10
            )
            thickness = max(
                1.0,
                width * (
                    0.20 + noise * 0.18
                    if style == "loaded_oil"
                    else 0.11 + noise * 0.13
                ),
            )
            dab = _pil_oil_color_variant(
                color,
                int(alpha * (0.19 + noise * (0.23 if style == "impasto_oil" else 0.18))),
                hue_shift=(noise - 0.5) * (18 if style == "loaded_oil" else 10),
                saturation_scale=0.86 + noise * 0.28,
                value_scale=0.76 + noise * 0.52,
            )
            _draw_pil_rotated_dab(
                draw,
                px,
                py,
                angle + (noise - 0.5) * (0.34 if style == "loaded_oil" else 0.18),
                length,
                thickness,
                dab,
            )
            if style in {"loaded_oil", "impasto_oil"} and noise > 0.26:
                normal = angle + math.pi / 2.0
                hi = _pil_oil_color_variant(
                    color,
                    int(alpha * (0.14 + noise * 0.12)),
                    hue_shift=(noise - 0.5) * 8,
                    saturation_scale=0.72,
                    value_scale=1.42,
                )
                sh = _pil_oil_color_variant(
                    color,
                    int(alpha * (0.10 + noise * 0.10)),
                    hue_shift=(noise - 0.5) * 6,
                    saturation_scale=1.02,
                    value_scale=0.46,
                )
                ridge_len = length * (0.54 + noise * 0.28)
                ridge_thick = max(1.0, thickness * 0.22)
                _draw_pil_rotated_dab(
                    draw,
                    px + math.cos(normal) * thickness * 0.32,
                    py + math.sin(normal) * thickness * 0.32,
                    angle,
                    ridge_len,
                    ridge_thick,
                    hi,
                )
                _draw_pil_rotated_dab(
                    draw,
                    px - math.cos(normal) * thickness * 0.38,
                    py - math.sin(normal) * thickness * 0.38,
                    angle,
                    ridge_len * 0.82,
                    ridge_thick,
                    sh,
                )

        if style == "impasto_oil":
            for lane in range(11):
                pos = (lane - 5) / 5.0
                noise = _paint_noise(lane, salt + 61)
                _draw_pil_line(
                    draw,
                    _offset_polyline_xy(points, pos * width * 0.50),
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.08 + noise * 0.09)),
                        hue_shift=(noise - 0.5) * 9,
                        saturation_scale=0.90,
                        value_scale=1.22 if pos < 0 else 0.68,
                    ),
                    max(1.0, width * (0.035 + noise * 0.035)),
                )
        return

    if style in {
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "rigger_oil",
        "scumble_oil",
        "stipple_oil",
        "knife_scrape_oil",
    }:
        if style == "filbert_oil":
            _draw_pil_line(
                draw,
                points,
                _pil_oil_color_variant(
                    color, int(alpha * 0.46), saturation_scale=0.94, value_scale=0.82
                ),
                width * 0.78,
            )
            for x, y, angle, idx in _sample_polyline_xy(points, max(3.0, width * 0.20)):
                noise = _paint_noise(idx, salt)
                side = (_paint_noise(idx, salt + 19) - 0.5) * width * 0.42
                normal = angle + math.pi / 2.0
                _draw_pil_rotated_dab(
                    draw,
                    x + math.cos(normal) * side,
                    y + math.sin(normal) * side,
                    angle,
                    width * (0.46 + noise * 0.48),
                    max(1.0, width * (0.14 + noise * 0.14)),
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.24 + noise * 0.20)),
                        hue_shift=(noise - 0.5) * 8,
                        saturation_scale=0.88 + noise * 0.18,
                        value_scale=0.74 + noise * 0.44,
                    ),
                )
            return

        if style == "flat_hog_oil":
            _draw_pil_line(
                draw,
                points,
                _pil_oil_color_variant(
                    color, int(alpha * 0.50), saturation_scale=0.92, value_scale=0.78
                ),
                width * 0.82,
            )
            for lane in range(15):
                pos = (lane - 7) / 7.0
                noise = _paint_noise(lane, salt + 31)
                lane_points = _offset_polyline_xy(points, pos * width * 0.46)
                if noise > 0.46:
                    lane_points = lane_points[::2] or lane_points
                _draw_pil_line(
                    draw,
                    lane_points,
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.13 + noise * 0.16)),
                        saturation_scale=0.90,
                        value_scale=1.28 if pos < 0 else 0.62,
                    ),
                    max(1.0, width * (0.028 + noise * 0.032)),
                )
            return

        if style == "fan_bristle_oil":
            for lane in range(21):
                pos = (lane - 10) / 10.0
                noise = _paint_noise(lane, salt + 43)
                spread = math.copysign(abs(pos) ** 0.78, pos)
                lane_points = _offset_polyline_xy(points, spread * width * 0.54)
                if lane % 3:
                    lane_points = lane_points[::2] or lane_points
                _draw_pil_line(
                    draw,
                    lane_points,
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.12 + noise * 0.22) * (1.0 - abs(pos) * 0.24)),
                        saturation_scale=0.84 + noise * 0.22,
                        value_scale=0.68 + noise * 0.58,
                    ),
                    max(1.0, width * (0.018 + noise * 0.030)),
                )
            return

        if style == "rigger_oil":
            _draw_pil_line(
                draw,
                points,
                _pil_oil_color_variant(
                    color, int(alpha * 0.72), saturation_scale=0.96, value_scale=0.88
                ),
                max(1.0, width * 0.54),
            )
            for lane, pos in enumerate((-0.22, 0.0, 0.22)):
                noise = _paint_noise(lane, salt + 59)
                _draw_pil_line(
                    draw,
                    _offset_polyline_xy(points, pos * width),
                    _pil_oil_color_variant(
                        color,
                        int(alpha * (0.18 + noise * 0.18)),
                        value_scale=1.30 if pos < 0 else 0.68,
                    ),
                    max(1.0, width * 0.10),
                )
            return

        if style in {"scumble_oil", "stipple_oil"}:
            step = max(3.0, width * (0.24 if style == "stipple_oil" else 0.20))
            for x, y, angle, idx in _sample_polyline_xy(points, step):
                noise = _paint_noise(idx, salt)
                if style == "scumble_oil" and noise < 0.42:
                    continue
                for cluster in range(3 if style == "stipple_oil" else 2):
                    grain = _paint_noise(idx * 7 + cluster, salt + 71)
                    side = (grain - 0.5) * width * (1.0 if style == "stipple_oil" else 1.18)
                    along = (_paint_noise(idx * 11 + cluster, salt + 83) - 0.5) * width * 0.44
                    px = x + math.cos(angle) * along + math.cos(angle + math.pi / 2.0) * side
                    py = y + math.sin(angle) * along + math.sin(angle + math.pi / 2.0) * side
                    dab = _pil_oil_color_variant(
                        color,
                        int(alpha * (0.18 + grain * 0.28)),
                        hue_shift=(grain - 0.5) * 8,
                        saturation_scale=0.88,
                        value_scale=0.72 + grain * 0.58,
                    )
                    if style == "stipple_oil":
                        radius = max(1.0, width * (0.07 + grain * 0.12))
                        draw.ellipse(
                            [
                                px - radius,
                                py - radius * (0.72 + grain * 0.3),
                                px + radius,
                                py + radius * (0.72 + grain * 0.3),
                            ],
                            fill=dab,
                        )
                    else:
                        _draw_pil_rotated_dab(
                            draw,
                            px,
                            py,
                            angle + (grain - 0.5) * 0.34,
                            width * (0.28 + grain * 0.55),
                            max(1.0, width * (0.045 + grain * 0.075)),
                            dab,
                        )
            return

        _draw_pil_line(
            draw,
            points,
            _pil_oil_color_variant(
                color, int(alpha * 0.24), saturation_scale=0.88, value_scale=0.72
            ),
            width * 0.62,
        )
        for x, y, angle, idx in _sample_polyline_xy(points, max(7.0, width * 0.42)):
            noise = _paint_noise(idx, salt + 97)
            if noise < 0.26:
                continue
            side = (_paint_noise(idx, salt + 101) - 0.5) * width * 0.72
            normal = angle + math.pi / 2.0
            _draw_pil_rotated_dab(
                draw,
                x + math.cos(normal) * side,
                y + math.sin(normal) * side,
                angle,
                width * (0.70 + noise * 1.10),
                max(1.0, width * (0.055 + noise * 0.070)),
                _pil_oil_color_variant(
                    color,
                    int(alpha * (0.22 + noise * 0.28)),
                    saturation_scale=0.90,
                    value_scale=0.62 + noise * 0.72,
                ),
            )
        return

    if style == "palette_knife":
        _draw_pil_line(draw, points, _pil_color_variant(color, int(alpha * 0.72), light=105), width * 0.78)
        for offset, light, factor in (
            (-width * 0.28, 142, 0.42),
            (width * 0.26, 74, 0.30),
            (0.0, 118, 0.22),
        ):
            _draw_pil_line(
                draw,
                _offset_polyline_xy(points, offset),
                _pil_color_variant(color, int(alpha * factor), light=light),
                max(1.0, width * 0.13),
            )
        for x, y, angle, idx in _sample_polyline_xy(points, max(8.0, width * 0.72)):
            noise = _paint_noise(idx, salt)
            dab = _pil_color_variant(color, int(alpha * (0.18 + noise * 0.18)), light=92 + int(noise * 44))
            _draw_pil_rotated_dab(
                draw,
                x,
                y + (noise - 0.5) * width * 0.22,
                angle + (noise - 0.5) * 0.18,
                width * (1.0 + noise * 0.75),
                max(1.0, width * 0.10),
                dab,
            )
        return

    if style == "real_wet_oil":
        _draw_pil_line(draw, points, _pil_color_variant(color, int(alpha * 0.38), light=88), width * 1.18)
        for lane in range(9):
            pos = (lane - 4) / 4.0
            noise = _paint_noise(lane, salt)
            light = 82 + int(noise * 72) + (16 if pos < -0.15 else 0)
            lane_alpha = int(alpha * (0.20 + 0.13 * (1.0 - abs(pos))))
            _draw_pil_line(
                draw,
                _offset_polyline_xy(points, pos * width * (0.38 + noise * 0.12)),
                _pil_color_variant(color, lane_alpha, light=light),
                max(1.0, width * (0.08 + 0.045 * noise)),
            )
        for x, y, angle, idx in _sample_polyline_xy(points, max(5.0, width * 0.34)):
            noise = _paint_noise(idx, salt + 17)
            if noise < 0.16:
                continue
            side = (_paint_noise(idx, salt + 29) - 0.5) * width * 0.72
            px = x + math.cos(angle + math.pi / 2.0) * side
            py = y + math.sin(angle + math.pi / 2.0) * side
            dab = _pil_color_variant(color, int(alpha * (0.09 + noise * 0.18)), light=95 + int(noise * 52))
            _draw_pil_rotated_dab(
                draw,
                px,
                py,
                angle + (noise - 0.5) * 0.28,
                width * (0.35 + noise * 0.58),
                max(1.0, width * (0.06 + noise * 0.08)),
                dab,
            )
        return

    if style == "bristle_oil":
        for lane in range(13):
            pos = (lane - 6) / 6.0
            noise = _paint_noise(lane, salt)
            lane_alpha = int(alpha * (0.24 + noise * 0.18))
            _draw_pil_line(
                draw,
                _offset_polyline_xy(points, pos * width * 0.46),
                _pil_color_variant(color, lane_alpha, light=78 + int(noise * 78)),
                max(1.0, width * (0.055 + 0.025 * noise)),
            )
        return

    skip_floor = 0.34 if style == "dry_oil" else 0.22
    step = max(2.5, width * (0.26 if style == "textured_chalk" else 0.34))
    for x, y, angle, idx in _sample_polyline_xy(points, step):
        noise = _paint_noise(idx, salt)
        if noise < skip_floor:
            continue
        side = (_paint_noise(idx, salt + 41) - 0.5) * width
        px = x + math.cos(angle + math.pi / 2.0) * side
        py = y + math.sin(angle + math.pi / 2.0) * side
        light = 78 + int(noise * 76)
        dab_alpha = int(alpha * (0.16 + noise * (0.30 if style == "dry_oil" else 0.22)))
        dab = _pil_color_variant(color, dab_alpha, light=light)
        if style == "textured_chalk":
            radius = max(0.8, width * (0.06 + noise * 0.12))
            draw.ellipse([px - radius * 1.55, py - radius, px + radius * 1.55, py + radius], fill=dab)
        else:
            _draw_pil_rotated_dab(
                draw,
                px,
                py,
                angle + (noise - 0.5) * 0.7,
                width * (0.20 + noise * 0.44),
                max(1.0, width * (0.045 + noise * 0.08)),
                dab,
            )


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
            scaled_stroke = copy.copy(stroke)
            scaled_stroke.width_px = max(1.0, float(stroke.width_px) * width_scale)
            DrawingCanvas._paint_stroke(painter, scaled_stroke, width, height)
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
    paint_layers: list["PaintLayer"] | None = None,
):
    """Render paint overlays onto a transparent PIL RGBA image."""
    from PIL import Image

    width = max(1, int(frame_size[0]))
    height = max(1, int(frame_size[1]))
    active_strokes = [
        copy.copy(stroke)
        for stroke in list(strokes or [])
        if stroke.is_active(int(time_ms))
    ]
    for stroke in active_strokes:
        stroke.width_px = max(
            0.25,
            float(stroke.width_px)
            * max(0.001, float(stroke_width_scale or 1.0)),
        )
    layer_rows = list(paint_layers or [])
    if layer_rows:
        layer_rank = {
            str(layer.layer_id): index for index, layer in enumerate(layer_rows)
        }
        active_strokes.sort(
            key=lambda stroke: layer_rank.get(
                str(getattr(stroke, "layer_id", "") or "paint-layer-1"),
                len(layer_rank),
            )
        )
    wet_settings_by_layer = {
        str(layer.layer_id): dict(getattr(layer, "wet_canvas_settings", {}) or {})
        for layer in layer_rows
        if str(getattr(layer, "layer_type", "standard") or "standard") == "material"
    }
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    try:
        painted_wet_layers: set[str] = set()
        for stroke in active_strokes:
            layer_id = str(
                getattr(stroke, "layer_id", "") or "paint-layer-1"
            )
            wet_settings = wet_settings_by_layer.get(layer_id)
            if wet_settings:
                from app.painter_wet_canvas import (
                    render_wet_layer_qimage,
                    wet_canvas_remaining,
                )

                if wet_canvas_remaining(wet_settings) > 0.0:
                    if layer_id in painted_wet_layers:
                        continue
                    layer_strokes = [
                        candidate
                        for candidate in active_strokes
                        if str(
                            getattr(candidate, "layer_id", "")
                            or "paint-layer-1"
                        )
                        == layer_id
                    ]
                    wet_image, _report = render_wet_layer_qimage(
                        layer_strokes,
                        settings=wet_settings,
                        width=width,
                        height=height,
                        time_ms=int(time_ms),
                        opacity_scale=1.0,
                        render_stroke=lambda target, item, render_w, render_h, alpha: DrawingCanvas._paint_stroke(
                            target,
                            item,
                            render_w,
                            render_h,
                            opacity_scale=alpha,
                        ),
                    )
                    painter.drawImage(0, 0, wet_image)
                    painted_wet_layers.add(layer_id)
                    continue
            DrawingCanvas._paint_stroke(
                painter,
                stroke,
                width,
                height,
            )
    finally:
        painter.end()
    out = _qimage_to_pil_rgba(image)
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
    paint_layers: list["PaintLayer"] | None = None,
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
        paint_layers=paint_layers,
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
        "wet_canvas_layer_count": sum(
            1
            for layer in list(paint_layers or [])
            if bool(
                dict(getattr(layer, "wet_canvas_settings", {}) or {}).get(
                    "enabled",
                    False,
                )
            )
        ),
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


def _qimage_to_pil_rgba(qimage: QImage):
    from io import BytesIO

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray

    byte_array = QByteArray()
    buffer = QBuffer(byte_array)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    qimage.save(buffer, "PNG")
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

PAINT_TEXTURED_BRUSH_STYLES = frozenset(
    {
        "loaded_oil",
        "impasto_oil",
        "oil_smear",
        "soft_oil_glaze",
        "real_wet_oil",
        "bristle_oil",
        "dry_oil",
        "palette_knife",
        "filbert_oil",
        "flat_hog_oil",
        "fan_bristle_oil",
        "rigger_oil",
        "scumble_oil",
        "stipple_oil",
        "knife_scrape_oil",
        "textured_chalk",
    } | set(DESIGNER_BRUSH_STYLE_IDS)
)
PAINT_BRUSH_STYLE_IDS = frozenset(
    {"round", "marker", "highlighter", "dashed"} | set(PAINT_TEXTURED_BRUSH_STYLES)
)
BRUSH_DETAIL_SECTIONS: tuple[str, ...] = (
    "Brush Tip Shape",
    "Shape Dynamics",
    "Scattering",
    "Texture",
    "Dual Brush",
    "Color Dynamics",
    "Transfer",
    "Brush Pose",
    "Noise",
    "Wet Edges",
    "Build Up",
    "Smoothing",
    "Protect Texture",
)
BRUSH_DETAIL_ACTIVE_SECTIONS = frozenset(
    {"Brush Tip Shape", "Shape Dynamics", "Scattering", "Texture", "Transfer", "Smoothing"}
)
BRUSH_DETAIL_DEFAULTS: dict[str, int | bool] = {
    "hardness": 100,
    "spacing": 25,
    "angle": 0,
    "roundness": 100,
    "flip_x": False,
    "flip_y": False,
}
BRUSH_PRESET_ICON_SIZE = QSize(53, 25)
BRUSH_PANEL_PRESET_CELL_SIZE = QSize(60, 38)
BRUSH_POPUP_PRESET_CELL_SIZE = QSize(66, 41)


def _normalize_paint_brush_style(style: str | None) -> str:
    value = str(style or "round").strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "oil": "real_wet_oil",
        "wet_oil": "real_wet_oil",
        "real_oil": "real_wet_oil",
        "loaded": "loaded_oil",
        "loaded_oils": "loaded_oil",
        "clumpy_oil": "loaded_oil",
        "thick_oil": "impasto_oil",
        "thick_paint": "impasto_oil",
        "impasto": "impasto_oil",
        "smear_oil": "oil_smear",
        "smeary_oil": "oil_smear",
        "oil_glaze": "soft_oil_glaze",
        "glaze_oil": "soft_oil_glaze",
        "bristle": "bristle_oil",
        "oil_bristle": "bristle_oil",
        "filbert": "filbert_oil",
        "filbert_brush": "filbert_oil",
        "flat_hog": "flat_hog_oil",
        "hog_bristle": "flat_hog_oil",
        "fan": "fan_bristle_oil",
        "fan_brush": "fan_bristle_oil",
        "rigger": "rigger_oil",
        "liner": "rigger_oil",
        "scumble": "scumble_oil",
        "stipple": "stipple_oil",
        "knife_scrape": "knife_scrape_oil",
        "soft_brush": "soft_round",
        "flat_brush": "hard_flat",
        "pixel": "pixel_square",
        "pencil": "graphite_pencil",
        "graphite": "graphite_pencil",
        "charcoal": "charcoal_vine",
        "ink": "technical_ink",
        "watercolor": "watercolor_wash",
        "gouache": "gouache_flat",
        "acrylic": "acrylic_bristle",
        "airbrush": "airbrush_soft",
        "skin": "skin_blender",
        "hair": "hair_strand",
        "foliage": "foliage_scatter",
        "cloud": "cloud_smoke",
        "rock": "rock_ground",
        "grunge": "fabric_grunge",
        "splatter": "paint_splatter",
        "drybrush": "dry_oil",
        "dry_brush": "dry_oil",
        "knife": "palette_knife",
        "palette": "palette_knife",
        "chalk": "textured_chalk",
        "texture_chalk": "textured_chalk",
    }
    value = aliases.get(value, value)
    return value if value in PAINT_BRUSH_STYLE_IDS else "round"


def _paint_style_salt(style: str) -> int:
    return sum((idx + 1) * ord(char) for idx, char in enumerate(str(style or "")))


def _paint_noise(index: int, salt: int = 0) -> float:
    value = math.sin((index + 1) * 12.9898 + salt * 78.233) * 43758.5453
    return value - math.floor(value)


def _offset_polyline_xy(points: list[tuple[float, float]], offset: float) -> list[tuple[float, float]]:
    if not points:
        return []
    if len(points) == 1:
        return list(points)
    out: list[tuple[float, float]] = []
    count = len(points)
    for idx, (x, y) in enumerate(points):
        prev_x, prev_y = points[max(0, idx - 1)]
        next_x, next_y = points[min(count - 1, idx + 1)]
        dx = next_x - prev_x
        dy = next_y - prev_y
        length = math.hypot(dx, dy)
        if length <= 0.001:
            out.append((x, y))
            continue
        nx = -dy / length
        ny = dx / length
        out.append((x + nx * offset, y + ny * offset))
    return out


def _sample_polyline_xy(
    points: list[tuple[float, float]],
    step_px: float,
) -> list[tuple[float, float, float, int]]:
    if not points:
        return []
    if len(points) == 1:
        return [(points[0][0], points[0][1], 0.0, 0)]
    step = max(1.0, float(step_px or 1.0))
    samples: list[tuple[float, float, float, int]] = []
    sample_index = 0
    for ax, ay, bx, by in (
        (points[idx][0], points[idx][1], points[idx + 1][0], points[idx + 1][1])
        for idx in range(len(points) - 1)
    ):
        dx = bx - ax
        dy = by - ay
        seg_len = math.hypot(dx, dy)
        if seg_len <= 0.01:
            continue
        angle = math.atan2(dy, dx)
        count = max(1, int(math.ceil(seg_len / step)))
        for local in range(count):
            t = min(1.0, local / max(1, count))
            samples.append((ax + dx * t, ay + dy * t, angle, sample_index))
            sample_index += 1
    if points:
        tail = points[-1]
        angle = samples[-1][2] if samples else 0.0
        samples.append((tail[0], tail[1], angle, sample_index))
    return samples

PAINTER_PBR_DEFAULTS: dict[str, float | str] = {
    "normal_strength": 2.4,
    "normal_radius_px": 1.8,
    "normal_format": "unreal_directx",
    "normal_filter": "sobel",
    "height_contrast": 1.1,
    "height_blur_px": 0.35,
    "edge_aware_sensitivity": 9.0,
    "ao_strength": 0.82,
    "ao_radius_px": 8.0,
    "ao_algorithm": "heightfield_horizon",
    "ao_samples": 8.0,
    "ao_steps": 8.0,
    "ao_height_scale": 14.0,
    "cavity_strength": 0.5,
    "cavity_radius_px": 2.2,
    "curvature_strength": 1.25,
    "roughness_bias": 0.55,
    "roughness_detail": 0.34,
    "metallic_value": 0.0,
    "preview_light_elevation": 48.0,
}

BRUSH_LIBRARY_PRESETS: list[dict[str, object]] = [
    {
        "category": "Oils",
        "name": "Loaded Oil Block",
        "style": "loaded_oil",
        "width": 42,
        "opacity": 92,
        "hardness": 86,
        "spacing": 18,
        "angle": -8,
        "roundness": 54,
    },
    {
        "category": "Oils",
        "name": "Impasto Ridge",
        "style": "impasto_oil",
        "width": 34,
        "opacity": 94,
        "hardness": 94,
        "spacing": 14,
        "angle": 0,
        "roundness": 62,
    },
    {
        "category": "Oils",
        "name": "Oily Smear",
        "style": "oil_smear",
        "width": 38,
        "opacity": 72,
        "hardness": 62,
        "spacing": 12,
        "angle": -12,
        "roundness": 48,
    },
    {
        "category": "Oils",
        "name": "Soft Oil Glaze",
        "style": "soft_oil_glaze",
        "width": 48,
        "opacity": 42,
        "hardness": 28,
        "spacing": 9,
        "angle": 0,
        "roundness": 76,
    },
    {
        "category": "Oils",
        "name": "Real Wet Oil",
        "style": "real_wet_oil",
        "width": 28,
        "opacity": 88,
        "hardness": 72,
        "spacing": 12,
        "angle": 4,
        "roundness": 68,
    },
    {
        "category": "Oils",
        "name": "Bristle Landscape",
        "style": "bristle_oil",
        "width": 22,
        "opacity": 84,
        "hardness": 76,
        "spacing": 20,
        "angle": 0,
        "roundness": 42,
    },
    {
        "category": "Oils",
        "name": "Dry Impasto",
        "style": "dry_oil",
        "width": 18,
        "opacity": 78,
        "hardness": 88,
        "spacing": 34,
        "angle": 9,
        "roundness": 38,
    },
    {
        "category": "Oils",
        "name": "Palette Knife",
        "style": "palette_knife",
        "width": 30,
        "opacity": 90,
        "hardness": 96,
        "spacing": 22,
        "angle": -18,
        "roundness": 30,
    },
    {
        "category": "Pro Oils",
        "name": "Filbert Portrait",
        "style": "filbert_oil",
        "width": 28,
        "opacity": 90,
        "hardness": 82,
        "spacing": 15,
        "angle": -6,
        "roundness": 58,
    },
    {
        "category": "Pro Oils",
        "name": "Hog Flat No. 12",
        "style": "flat_hog_oil",
        "width": 36,
        "opacity": 94,
        "hardness": 91,
        "spacing": 17,
        "angle": 0,
        "roundness": 32,
    },
    {
        "category": "Pro Oils",
        "name": "Fan Foliage",
        "style": "fan_bristle_oil",
        "width": 44,
        "opacity": 78,
        "hardness": 74,
        "spacing": 28,
        "angle": 0,
        "roundness": 44,
    },
    {
        "category": "Pro Oils",
        "name": "Rigger Long Line",
        "style": "rigger_oil",
        "width": 7,
        "opacity": 92,
        "hardness": 84,
        "spacing": 8,
        "angle": 0,
        "roundness": 88,
    },
    {
        "category": "Pro Oils",
        "name": "Dry Scumble",
        "style": "scumble_oil",
        "width": 46,
        "opacity": 68,
        "hardness": 86,
        "spacing": 42,
        "angle": 12,
        "roundness": 34,
    },
    {
        "category": "Pro Oils",
        "name": "Stipple Bloom",
        "style": "stipple_oil",
        "width": 24,
        "opacity": 82,
        "hardness": 72,
        "spacing": 48,
        "angle": 0,
        "roundness": 100,
    },
    {
        "category": "Pro Oils",
        "name": "Knife Scrape",
        "style": "knife_scrape_oil",
        "width": 38,
        "opacity": 86,
        "hardness": 98,
        "spacing": 30,
        "angle": -22,
        "roundness": 22,
    },
    {
        "category": "Texture",
        "name": "Textured Chalk",
        "style": "textured_chalk",
        "width": 11,
        "opacity": 74,
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
    {
        "category": "Utility",
        "name": "Screen Paper",
        "style": "highlighter",
        "width": 28,
        "opacity": 38,
    },
] + [dict(row) for row in DESIGNER_BRUSH_PRESETS]


class PainterColorWheel(QWidget):
    colorChanged = Signal(QColor)
    BASE_SIZE = 112
    DISPLAY_SIZE = 176
    MIN_DISPLAY_SIZE = 140

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(self.DISPLAY_SIZE, self.DISPLAY_SIZE)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._hue = 0
        self._sat = 255
        self._val = 255

    def set_display_size(self, size_px: int) -> None:
        size = max(self.MIN_DISPLAY_SIZE, min(self.DISPLAY_SIZE, int(size_px)))
        if self.width() == size and self.height() == size:
            return
        self.setFixedSize(size, size)
        self.update()

    def _scale(self) -> float:
        return max(1.0, min(self.width(), self.height()) / float(self.BASE_SIZE))

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
        scale = self._scale()
        outer = min(self.width(), self.height()) / 2 - 5 * scale
        ring_width = 7.5 * scale
        ring_radius = outer - ring_width / 2
        ring_rect = QRectF(
            center.x() - ring_radius,
            center.y() - ring_radius,
            ring_radius * 2,
            ring_radius * 2,
        )
        painter.setPen(QPen(QColor("#090B10"), ring_width + 3.0 * scale))
        painter.drawEllipse(ring_rect)
        for degree in range(360):
            painter.setPen(QPen(QColor.fromHsv(degree, 242, 235), ring_width))
            painter.drawArc(ring_rect, int((90 - degree) * 16), -16)
        painter.setPen(QPen(QColor(232, 238, 248, 54), 0.8 * scale))
        painter.drawEllipse(ring_rect.adjusted(-ring_width / 2, -ring_width / 2, ring_width / 2, ring_width / 2))
        painter.setPen(QPen(QColor(0, 0, 0, 150), 0.8 * scale))
        painter.drawEllipse(ring_rect.adjusted(ring_width / 2, ring_width / 2, -ring_width / 2, -ring_width / 2))

        hue_point, white_point, black_point = self._triangle_points()
        image = QImage(self.width(), self.height(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        hue_color = QColor.fromHsv(self._hue, 245, 245)
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
        triangle = QPolygonF([hue_point, white_point, black_point])
        triangle_path = QPainterPath()
        triangle_path.addPolygon(triangle)
        painter.save()
        painter.setClipPath(triangle_path)
        painter.drawImage(0, 0, image)
        gloss = QLinearGradient(white_point, black_point)
        gloss.setColorAt(0.0, QColor(255, 255, 255, 32))
        gloss.setColorAt(0.48, QColor(255, 255, 255, 0))
        gloss.setColorAt(1.0, QColor(0, 0, 0, 46))
        painter.fillPath(triangle_path, QBrush(gloss))
        painter.restore()

        painter.setPen(QPen(QColor("#b8c6dd"), max(1.0, 0.9 * scale)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(triangle)

        angle = math.radians(self._hue)
        selector_radius = ring_radius
        hue_selector = QPointF(
            center.x() + math.cos(angle) * selector_radius,
            center.y() - math.sin(angle) * selector_radius,
        )
        painter.setPen(QPen(QColor("#05070B"), max(1.0, 1.6 * scale)))
        painter.setBrush(QColor("#E9EEF7"))
        painter.drawEllipse(hue_selector, 4.2 * scale, 4.2 * scale)
        painter.setPen(QPen(QColor(255, 255, 255, 138), 0.7 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(hue_selector, 3.3 * scale, 3.3 * scale)

        color_selector = self._selector_point()
        painter.setPen(QPen(QColor("#05070B"), max(1.0, 1.5 * scale)))
        painter.setBrush(QColor("#F3F6FB"))
        painter.drawEllipse(color_selector, 3.7 * scale, 3.7 * scale)
        painter.setPen(QPen(QColor("#C5D2EA"), 0.7 * scale))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(color_selector, 2.7 * scale, 2.7 * scale)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def _pick(self, pos: QPointF) -> None:
        center = QPointF(self.width() / 2, self.height() / 2)
        scale = self._scale()
        outer = min(self.width(), self.height()) / 2 - 6 * scale
        ring_width = 12 * scale
        distance = math.hypot(pos.x() - center.x(), pos.y() - center.y())
        if outer - ring_width <= distance <= outer + 2 * scale:
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
        radius = min(self.width(), self.height()) / 2 - 24 * self._scale()
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


class PainterPhotoshopColorField(QWidget):
    """Compact Photoshop-style saturation/value field with a vertical hue strip."""

    colorChanged = Signal(QColor)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hue = 0
        self._sat = 255
        self._val = 255
        self._drag_target = ""
        self.setMinimumSize(190, 78)
        self.setMaximumHeight(96)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def set_color(self, color: QColor) -> None:
        hue = int(color.hue())
        self._hue = 0 if hue < 0 else hue
        self._sat = max(0, min(255, int(color.saturation())))
        self._val = max(0, min(255, int(color.value())))
        self.update()

    def _field_rect(self) -> QRectF:
        return QRectF(1, 1, max(8, self.width() - 24), max(8, self.height() - 2))

    def _hue_rect(self) -> QRectF:
        return QRectF(max(1, self.width() - 18), 1, 17, max(8, self.height() - 2))

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        field = self._field_rect()
        hue_color = QColor.fromHsv(self._hue, 255, 255)

        horizontal = QLinearGradient(field.topLeft(), field.topRight())
        horizontal.setColorAt(0.0, QColor("#ffffff"))
        horizontal.setColorAt(1.0, hue_color)
        painter.fillRect(field, horizontal)
        vertical = QLinearGradient(field.topLeft(), field.bottomLeft())
        vertical.setColorAt(0.0, QColor(0, 0, 0, 0))
        vertical.setColorAt(1.0, QColor(0, 0, 0, 255))
        painter.fillRect(field, vertical)

        hue_rect = self._hue_rect()
        hue_gradient = QLinearGradient(hue_rect.topLeft(), hue_rect.bottomLeft())
        for stop, degree in (
            (0.0, 0),
            (1 / 6, 60),
            (2 / 6, 120),
            (3 / 6, 180),
            (4 / 6, 240),
            (5 / 6, 300),
            (1.0, 359),
        ):
            hue_gradient.setColorAt(stop, QColor.fromHsv(degree, 255, 255))
        painter.fillRect(hue_rect, hue_gradient)

        painter.setPen(QPen(QColor("#292929"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(field)
        painter.drawRect(hue_rect)

        selector = QPointF(
            field.left() + (self._sat / 255.0) * field.width(),
            field.top() + (1.0 - self._val / 255.0) * field.height(),
        )
        painter.setPen(QPen(QColor("#111111"), 3))
        painter.drawEllipse(selector, 4, 4)
        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawEllipse(selector, 4, 4)

        hue_y = hue_rect.top() + (self._hue / 359.0) * hue_rect.height()
        marker = QPolygonF(
            [
                QPointF(hue_rect.left() - 4, hue_y),
                QPointF(hue_rect.left(), hue_y - 3),
                QPointF(hue_rect.left(), hue_y + 3),
            ]
        )
        painter.setPen(QPen(QColor("#111111"), 1))
        painter.setBrush(QColor("#f5f5f5"))
        painter.drawPolygon(marker)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._drag_target = "hue" if self._hue_rect().contains(event.position()) else "field"
        self._pick(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._pick(event.position())

    def mouseReleaseEvent(self, _event: QMouseEvent) -> None:
        self._drag_target = ""

    def _pick(self, pos: QPointF) -> None:
        if self._drag_target == "hue":
            rect = self._hue_rect()
            ratio = (pos.y() - rect.top()) / max(1.0, rect.height())
            self._hue = max(0, min(359, int(ratio * 359)))
        else:
            rect = self._field_rect()
            sx = (pos.x() - rect.left()) / max(1.0, rect.width())
            vy = (pos.y() - rect.top()) / max(1.0, rect.height())
            self._sat = max(0, min(255, int(sx * 255)))
            self._val = max(0, min(255, int((1.0 - vy) * 255)))
        self.update()
        self.colorChanged.emit(QColor.fromHsv(self._hue, self._sat, self._val))


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
        self.setWindowTitle("Painter - Tiger Studio" if self._standalone else tr("paint.title"))
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
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
        self._selection_combine_mode = "new"
        self._quick_mask_enabled = False
        self._grid_visible = False
        self._snap_to_grid = False
        self._grid_size_px = 64
        self._magic_select_tolerance = 32
        self._mirror_x_enabled = False
        self._mirror_y_enabled = False
        self._pbr_texture_settings: dict[str, float | str | bool] = dict(PAINTER_PBR_DEFAULTS)
        self._pbr_preview_payload: dict | None = None
        self._pbr_preview_maps_cache: dict | None = None
        self._pbr_source_path: str = ""
        self._pbr_texture_lab_window = None
        self._pbr_slider_labels: dict[str, QLabel] = {}
        self._pbr_sliders: dict[str, QSlider] = {}
        from app.painter_material_paint import MATERIAL_PAINT_DEFAULTS

        self._material_paint_settings: dict[str, float] = dict(MATERIAL_PAINT_DEFAULTS)
        self._material_preview_enabled = False
        self._material_preview_light_azimuth_deg = -38.0
        self._material_preview_light_elevation_deg = 48.0
        self._material_preview_cache: dict | None = None
        self._material_control_sliders: dict[str, StudioSlider] = {}
        self._material_control_labels: dict[str, QLabel] = {}
        self._wet_canvas_control_sliders: dict[str, StudioSlider] = {}
        self._wet_canvas_control_labels: dict[str, QLabel] = {}
        self._wet_canvas_enabled_check: QCheckBox | None = None
        self._painter_reference_board: dict | None = None
        self._painter_reference_selected_id = ""
        self._painter_reference_syncing = False
        self._painter_reference_controls: dict[str, QSpinBox] = {}
        self._painter_reference_labels: dict[str, QLabel] = {}
        self._painter_3d_blockout_scene: dict | None = None
        self._painter_3d_blockout_selected_id = ""
        self._painter_3d_blockout_syncing = False
        self._painter_3d_blockout_drag: dict | None = None
        self._canvas_workspace_mode = "paint"
        self._canvas_workspace_user_generation = 0
        self._blockout_transform_mode = "move"
        self._blockout_active_axis = ""
        self._painter_3d_blockout_controls: dict[str, QSpinBox] = {}
        self._painter_3d_blockout_renderer_status: dict = {
            "renderer": "painter_blockout_qpainter_v1",
            "active": "qpainter",
            "fallback": True,
            "reason": "not_rendered_yet",
        }
        self._selected_layer_id: str | None = None
        self._paint_clipboard: dict | None = None
        self._paint_initial_color_scroll_pending = True
        self._tool_rail_collapsed = False
        self._tool_rail_full_width = 40
        self._tool_rail_collapsed_width = 24
        self._brush_preset_menu: QMenu | None = None
        self._move_refresh_pause_timer = QTimer(self)
        self._move_refresh_pause_timer.setSingleShot(True)
        self._move_refresh_pause_timer.setInterval(140)
        self._move_refresh_pause_timer.timeout.connect(self._finish_window_move_refresh_pause)
        self._move_refresh_paused = False
        self._move_refresh_pause_enabled = False
        self._paint_layer_serial = 1
        self._painter_document_path = ""
        self._painter_document_asset_root = ""
        self._painter_document_dirty = False
        self._paint_layers: list[PaintLayer] = [
            PaintLayer("paint-layer-1", "Layer 1")
        ]
        self._active_paint_layer_id = "paint-layer-1"
        self._background_layer_present = paint_pixmap_has_visible_pixels(background_pixmap)
        self._canvas_document_size = (
            max(1, int(background_pixmap.width())) if background_pixmap and not background_pixmap.isNull() else 1920,
            max(1, int(background_pixmap.height())) if background_pixmap and not background_pixmap.isNull() else 1080,
        )
        from app.painter_ui_document import create_ui_document

        self._painter_ui_document = create_ui_document(*self._canvas_document_size)

        self._configure_initial_painter_window_size(parent)

        self._pen_color = QColor(*PALETTE_COLORS[0])
        self._background_color = QColor("#FFFFFF")
        self._pen_width = 6.0
        self._pen_opacity = 255
        self._pen_style = "round"
        self._brush_detail_settings: dict[str, int | bool] = dict(BRUSH_DETAIL_DEFAULTS)
        self._brush_detail_syncing = False
        self._brush_favorites: set[str] = set()
        self._brush_recent_indices: list[int] = []
        self._brush_active_filters: set[str] = set()
        self._brush_selector_compact = False
        self._active_brush_preset_index = 0
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
        icon_px: int = 16,
    ) -> None:
        button.setText("")
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setIcon(app_icon(icon_name, size=icon_px, color="#E8E8E8"))
        button.setIconSize(icon_size(icon_px))
        button.setFixedSize(30, 26)

    def _make_tool_rail_chrome_button(self, icon_name: str, label: str) -> QPushButton:
        button = QPushButton("")
        button.setObjectName("PaintToolRailChrome")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(label)
        button.setAccessibleName(label)
        button.setIcon(app_icon(icon_name, size=11, color="#AEB8C9"))
        button.setIconSize(icon_size(11))
        button.setFixedSize(16, 16)
        return button

    def _make_tool_rail_separator(self) -> QFrame:
        line = QFrame()
        line.setObjectName("PaintToolRailSeparator")
        line.setFixedHeight(3)
        line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        return line

    def _register_painter_tool_shortcut(
        self,
        key: str,
        handler: Callable[[], None],
    ) -> None:
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.activated.connect(handler)
        self._painter_tool_shortcuts.append(shortcut)

    def _handle_painter_3d_camera_shortcut(
        self,
        key: int,
        *,
        paint_fallback: Callable[[], None] | None = None,
    ) -> None:
        if str(getattr(self, "_canvas_workspace_mode", "paint")) == "3d_place":
            focus = QApplication.focusWidget()
            if not isinstance(focus, (QLineEdit, QTextEdit, QSpinBox)):
                self._nudge_3d_blockout_camera(key)
            return
        if paint_fallback is not None:
            paint_fallback()

    def _build_tool_rail_swatch_panel(self, parent_layout: QVBoxLayout) -> None:
        panel = QFrame()
        panel.setObjectName("PaintToolSwatches")
        panel.setFixedSize(32, 40)
        panel.setToolTip("Foreground / background colors")
        self._tool_swatch_panel = panel

        self.background_swatch_btn = QPushButton(panel)
        self.background_swatch_btn.setObjectName("PaintBackgroundSwatch")
        self.background_swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.background_swatch_btn.setToolTip("Background color")
        self.background_swatch_btn.setFixedSize(21, 21)
        self.background_swatch_btn.move(9, 16)
        self.background_swatch_btn.clicked.connect(self._pick_background_color)

        self.foreground_swatch_btn = QPushButton(panel)
        self.foreground_swatch_btn.setObjectName("PaintForegroundSwatch")
        self.foreground_swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.foreground_swatch_btn.setToolTip("Foreground color")
        self.foreground_swatch_btn.setFixedSize(22, 22)
        self.foreground_swatch_btn.move(1, 4)
        self.foreground_swatch_btn.clicked.connect(self._pick_custom_color)
        self.foreground_swatch_btn.raise_()

        self.swap_swatch_btn = QPushButton("", panel)
        self.swap_swatch_btn.setObjectName("PaintSwapSwatch")
        self.swap_swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swap_swatch_btn.setToolTip("Swap foreground/background")
        self.swap_swatch_btn.setIcon(app_icon("repeat", size=11, color="#AEB8C9"))
        self.swap_swatch_btn.setIconSize(icon_size(11))
        self.swap_swatch_btn.setFixedSize(14, 14)
        self.swap_swatch_btn.move(18, 0)
        self.swap_swatch_btn.clicked.connect(self._swap_painter_foreground_background)
        self.swap_swatch_btn.raise_()

        parent_layout.addWidget(panel, 0, Qt.AlignmentFlag.AlignHCenter)
        self._refresh_toolbar_color_swatches()

    def _available_painter_geometry(self, parent: QWidget | None = None) -> QRect:
        return available_geometry_for_window(self, reference=parent)

    def _configure_initial_painter_window_size(self, parent: QWidget | None = None) -> None:
        available = self._available_painter_geometry(parent)
        max_w = max(520, int(available.width()) - 48)
        max_h = max(420, int(available.height()) - 64)
        min_w = min(760, max_w)
        min_h = min(560, max_h)
        self.setMinimumSize(min_w, min_h)
        desired_w = 1100
        desired_h = 780
        if parent is not None:
            try:
                parent_win = parent.window()
                if parent_win is not None:
                    desired_w = max(desired_w, int(parent_win.width() * 0.92))
                    desired_h = max(desired_h, int(parent_win.height() * 0.9))
            except Exception:
                pass
        self.resize(
            max(min_w, min(desired_w, max_w)),
            max(min_h, min(desired_h, max_h)),
        )

    def _fit_painter_window_to_screen(self) -> None:
        available = self._available_painter_geometry(self.parentWidget())
        max_w = max(self.minimumWidth(), int(available.width()) - 48)
        max_h = max(self.minimumHeight(), int(available.height()) - 64)
        target_w = min(self.width(), max_w)
        target_h = min(self.height(), max_h)
        if target_w != self.width() or target_h != self.height():
            self.resize(target_w, target_h)
        left = int(available.left()) + 16
        top = int(available.top()) + 16
        right = int(available.right()) - self.width() + 1
        bottom = int(available.bottom()) - self.height() + 1
        if right < left:
            right = left
        if bottom < top:
            bottom = top
        x = max(left, min(self.x(), right))
        y = max(top, min(self.y(), bottom))
        if x != self.x() or y != self.y():
            self.move(x, y)

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
        self._add_painter_menu_action(file_menu, "Open...", self._prompt_open_painter_document, "Ctrl+O")
        self._add_painter_menu_action(file_menu, "Save", self._prompt_save_painter_document, "Ctrl+S")
        self._add_painter_menu_action(
            file_menu,
            "Save As...",
            lambda: self._prompt_save_painter_document(save_as=True),
            "Ctrl+Shift+S",
        )
        file_menu.addSeparator()
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
        self._painter_view_menu = view_menu
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

        brush_menu = menu_bar.addMenu("Brush")
        self._painter_brush_menu = brush_menu
        self._add_painter_menu_action(brush_menu, "Brush Selector", self._focus_brush_selector, "F5")
        self._add_painter_menu_action(brush_menu, "Advanced Brush Controls", self._focus_brush_panel)
        brush_menu.addSeparator()
        for preset in BRUSH_LIBRARY_PRESETS:
            name = str(preset.get("name") or "Brush")
            self._add_painter_menu_action(
                brush_menu,
                name,
                lambda _checked=False, row=preset: self._apply_brush_library_preset(row),
            )

        image_menu = menu_bar.addMenu("Image")
        self._painter_image_menu = image_menu
        self._add_painter_menu_action(image_menu, "Image Size...", self._prompt_image_size)
        self._add_painter_menu_action(image_menu, "Canvas Size...", self._prompt_canvas_size)
        self._add_painter_menu_action(image_menu, "Crop To Selection", self._crop_to_selection)
        image_menu.addSeparator()
        self._add_painter_menu_action(image_menu, "Flip Canvas Horizontal", lambda: self._flip_canvas(horizontal=True))
        self._add_painter_menu_action(image_menu, "Flip Canvas Vertical", lambda: self._flip_canvas(horizontal=False))
        image_menu.addSeparator()
        self._add_painter_menu_action(image_menu, "PBR Texture Lab...", self._open_pbr_texture_lab_window)
        self._add_painter_menu_action(image_menu, "Export PBR Maps...", lambda: self._export_pbr_texture_maps(packed=True))
        image_menu.addSeparator()
        self._add_painter_menu_action(image_menu, "Channels Panel", lambda: self._show_painter_tab("channels"))
        self._add_painter_menu_action(image_menu, "Show RGB", lambda: self._set_channel_visibility("RGB", True))
        self._add_painter_menu_action(image_menu, "Hide Alpha", lambda: self._set_channel_visibility("Alpha", False))

        layer_menu = menu_bar.addMenu("Layer")
        self._add_painter_menu_action(layer_menu, "New Layer", self._new_paint_layer, "Ctrl+Shift+N")
        self._add_painter_menu_action(
            layer_menu,
            "New Material Paint Layer",
            self._new_material_paint_layer,
        )
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
        self._painter_window_menu = window_menu
        self._add_painter_menu_action(window_menu, "Layers", lambda: self._show_painter_tab("layers"))
        self._add_painter_menu_action(window_menu, "Channels", lambda: self._show_painter_tab("channels"))
        self._add_painter_menu_action(window_menu, "Paths", lambda: self._show_painter_tab("paths"))
        self._add_painter_menu_action(window_menu, "Brush", self._focus_brush_panel)
        self._add_painter_menu_action(window_menu, "Reference Board", self._focus_reference_board_panel)
        self._add_painter_menu_action(window_menu, "3D Blockout", self._focus_3d_blockout_panel)
        self._add_painter_menu_action(window_menu, "Show Tool Bar", self._show_tool_rail)
        window_menu.addSeparator()
        self._add_painter_menu_action(window_menu, "PBR Texture Lab...", self._open_pbr_texture_lab_window)

        # Match Photoshop's high-frequency menu order. Brush presets and path
        # commands stay available from the options bar and their dock panels
        # instead of occupying custom top-level menus.
        for action in list(menu_bar.actions()):
            menu_bar.removeAction(action)
        for menu in (
            file_menu,
            edit_menu,
            image_menu,
            layer_menu,
            select_menu,
            view_menu,
            window_menu,
        ):
            menu_bar.addAction(menu.menuAction())
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
            [layer.layer_id for layer in self._paint_layers],
            {
                layer.layer_id: dict(getattr(layer, "wet_canvas_settings", {}) or {})
                for layer in self._paint_layers
                if str(getattr(layer, "layer_type", "standard") or "standard")
                == "material"
            },
        )

    def _open_new_canvas_dialog(self) -> None:
        setup = NewCanvasDialog(
            self,
            default_size=self._canvas_document_size,
            default_background="transparent",
        )
        if setup.exec() != QDialog.DialogCode.Accepted:
            return
        request = setup.canvas_request()
        self._replace_canvas_document(
            int(request.get("width") or 1920),
            int(request.get("height") or 1080),
            str(request.get("background") or "transparent"),
        )

    def _replace_canvas_document(self, width: int, height: int, background: str = "transparent") -> None:
        self._push_undo_state("New canvas")
        width = max(64, min(16384, int(width or 1920)))
        height = max(64, min(16384, int(height or 1080)))
        background_text = str(background or "transparent")
        self._canvas_document_size = (width, height)
        from app.painter_ui_document import create_ui_document

        self._painter_ui_document = create_ui_document(width, height)
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
        for item in list(getattr(self, "_painter_reference_labels", {}).values()):
            item.deleteLater()
        self._bubble_items = []
        self._sticker_items = []
        self._painter_reference_labels = {}
        self._bubbles = []
        self._stickers = []
        self._painter_reference_board = None
        self._painter_reference_selected_id = ""
        self._paint_layer_serial = 1
        self._paint_layers = [PaintLayer("paint-layer-1", "Layer 1")]
        self._active_paint_layer_id = "paint-layer-1"
        self._selected_layer_id = "paint-layer-1" if self._standalone else None
        self._material_preview_enabled = False
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        if hasattr(self, "canvas"):
            self.canvas.set_strokes_snapshot([])
            self.canvas.clear_selection()
            self.canvas.clear_path_preview()
        self._canvas_pan = QPoint(0, 0)
        self._sync_canvas_layer_view()
        self._update_canvas_geometry()
        self._update_inspector_counts()
        self._sync_material_controls()

    def _show_painter_tab(self, tab: str | int) -> None:
        tabs = getattr(self, "_layer_channel_path_tabs", None)
        if tabs is None:
            return
        if isinstance(tab, int):
            index = tab
            if 0 <= index < tabs.count():
                tabs.setCurrentIndex(index)
            return
        target = str(tab or "").strip().casefold()
        if target in {"brush", "brushes", "brush_settings"}:
            self._focus_brush_panel()
            return
        if target in {"reference", "references", "reference_board", "ref"}:
            self._focus_reference_board_panel()
            return
        if target in {"3d", "blockout", "3d_blockout"}:
            self._focus_3d_blockout_panel()
            return
        names = {
            "layers": 0,
            "layer": 0,
            "channels": 1,
            "channel": 1,
            "paths": 2,
            "path": 2,
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
        self.pen_btn.setToolTip(tr("paint.btn.pen"))
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
        self.width_slider = StudioSlider("accent")
        self.width_slider.setRange(1, 60)
        self.width_slider.setValue(int(self._pen_width))
        self.width_slider.setFixedWidth(120)
        self.width_slider.valueChanged.connect(self._on_width_changed)
        toolbar.addWidget(self.width_slider)

        toolbar.addSpacing(10)
        toolbar.addWidget(QLabel(tr("paint.label.opacity")))
        self.opacity_slider = StudioSlider("accent")
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
        self._blockout_overlay_label = QLabel(canvas_host)
        self._blockout_overlay_label.setObjectName("PaintBlockoutCanvasOverlay")
        self._blockout_overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._blockout_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._blockout_overlay_label.hide()
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self.canvas.set_document_size(*self._canvas_document_size)
        self.canvas.set_view_zoom_percent(int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100)))
        self._sync_canvas_layer_view()
        self.canvas.set_tool("pen")
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_width(self._pen_width)
        self.canvas.set_pen_opacity(self._pen_opacity)
        self.canvas.set_brush_detail(**self._canvas_brush_detail_payload())
        self.canvas.stroke_added.connect(self._on_stroke_added)
        self.canvas.set_extra_paint_hook(self._paint_material_preview_overlay)
        self.canvas.zoom_requested.connect(self._handle_canvas_zoom_request)
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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._painter_menu_bar = self._build_painter_menu_bar()
        root.addWidget(self._painter_menu_bar)

        top_bar = QFrame()
        top_bar.setObjectName("PaintTopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6, 4, 8, 4)
        top_layout.setSpacing(5)

        self._active_tool_icon = QLabel()
        self._active_tool_icon.setFixedSize(22, 22)
        self._active_tool_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._active_tool_icon.setPixmap(
            app_icon("paint-brush", size=14, color="#F0F0F0").pixmap(14, 14)
        )
        top_layout.addWidget(self._active_tool_icon)
        self._active_tool_name = QLabel("Brush")
        self._active_tool_name.setObjectName("PaintActiveToolName")
        top_layout.addWidget(self._active_tool_name)

        option_separator = QFrame()
        option_separator.setObjectName("PaintOptionSeparator")
        top_layout.addWidget(option_separator)

        self._tool_options_host = QWidget(top_bar)
        self._tool_options_host.setObjectName("PaintToolOptionsHost")
        self._tool_options_layout = QHBoxLayout(self._tool_options_host)
        self._tool_options_layout.setContentsMargins(0, 0, 0, 0)
        self._tool_options_layout.setSpacing(5)
        top_layout.addWidget(self._tool_options_host, stretch=1)

        self.undo_btn = QPushButton("↶")
        self.undo_btn.setObjectName("PaintTool")
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.setToolTip("Undo (Ctrl+Z)")
        self.undo_btn.setAccessibleName("Undo")
        self.undo_btn.setFixedSize(30, 30)
        self.undo_btn.clicked.connect(self._undo)
        self.undo_btn.hide()

        self.redo_btn = QPushButton("↷")
        self.redo_btn.setObjectName("PaintTool")
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.setToolTip("Redo (Ctrl+Y)")
        self.redo_btn.setAccessibleName("Redo")
        self.redo_btn.setFixedSize(30, 30)
        self.redo_btn.clicked.connect(self._redo)
        self.redo_btn.hide()

        self.export_png_btn = QPushButton("")
        self.export_png_btn.setObjectName("PaintTool")
        self.export_png_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_png_btn.setToolTip("Export PNG")
        self.export_png_btn.setAccessibleName("Export PNG")
        self.export_png_btn.setIcon(app_icon("export", size=14, color="#EEF3FB"))
        self.export_png_btn.setIconSize(icon_size(14))
        self.export_png_btn.setFixedSize(34, 30)
        self.export_png_btn.clicked.connect(self._show_export_png_menu)
        self.export_png_btn.hide()

        self.zoom_slider = StudioSlider("neutral", self)
        self.zoom_slider.setRange(25, PAINT_MAX_ZOOM_PERCENT)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        self.zoom_slider.hide()
        self.zoom_out_btn = QPushButton("-", self)
        self.zoom_out_btn.setToolTip("Zoom out (Ctrl+-)")
        self.zoom_out_btn.hide()
        self.zoom_out_btn.clicked.connect(self._zoom_out)
        self.zoom_in_btn = QPushButton("+", self)
        self.zoom_in_btn.setToolTip("Zoom in (Ctrl++)")
        self.zoom_in_btn.hide()
        self.zoom_in_btn.clicked.connect(self._zoom_in)
        self.zoom_fit_btn = QPushButton("", self)
        self.zoom_fit_btn.setToolTip("Fit canvas (Ctrl+0)")
        self.zoom_fit_btn.setAccessibleName("Fit canvas")
        self.zoom_fit_btn.hide()
        self.zoom_fit_btn.clicked.connect(self._zoom_fit)
        self._zoom_value_label = QLabel("100%", self)
        self._zoom_value_label.setObjectName("PaintValue")
        self._zoom_value_label.hide()

        self._dialog_buttons = None
        if not self._standalone:
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
            self._dialog_buttons = buttons
            top_layout.addWidget(buttons)
        root.addWidget(top_bar)

        workspace = QHBoxLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setSpacing(0)
        root.addLayout(workspace, stretch=1)

        tool_rail = QFrame()
        tool_rail.setObjectName("PaintToolRail")
        tool_rail.setFixedWidth(int(self._tool_rail_full_width))
        tool_rail.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._tool_rail = tool_rail
        tool_layout = QVBoxLayout(tool_rail)
        tool_layout.setContentsMargins(5, 3, 5, 4)
        tool_layout.setSpacing(0)

        tool_chrome_row = QHBoxLayout()
        tool_chrome_row.setContentsMargins(0, 0, 0, 0)
        tool_chrome_row.setSpacing(2)
        self.tool_collapse_btn = self._make_tool_rail_chrome_button(
            "chevron-down",
            "Collapse toolbar",
        )
        self.tool_collapse_btn.clicked.connect(self._toggle_tool_rail_collapsed)
        self.tool_close_btn = self._make_tool_rail_chrome_button("x", "Close toolbar")
        self.tool_close_btn.clicked.connect(self._hide_tool_rail)
        self.tool_collapse_btn.hide()
        self.tool_close_btn.hide()
        tool_chrome_row.addStretch(1)
        self._tool_rail_grip = QLabel("••••")
        self._tool_rail_grip.setObjectName("PaintToolRailGrip")
        self._tool_rail_grip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tool_rail_grip.setFixedHeight(8)
        self._tool_rail_grip.setToolTip("Painter tools")
        tool_chrome_row.addWidget(self._tool_rail_grip)
        tool_chrome_row.addStretch(1)
        tool_layout.addLayout(tool_chrome_row)

        tool_button_host = QWidget(tool_rail)
        tool_button_host.setObjectName("PaintToolButtonHost")
        tool_button_host.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        self._tool_button_host = tool_button_host
        tool_buttons_layout = QVBoxLayout(tool_button_host)
        tool_buttons_layout.setContentsMargins(0, 0, 0, 0)
        tool_buttons_layout.setSpacing(0)

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

        self.fill_tool_btn = QPushButton("Fill")
        self.fill_tool_btn.setCheckable(True)
        self.fill_tool_btn.setObjectName("PaintTool")
        self.fill_tool_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.fill_tool_btn.clicked.connect(lambda: self._set_tool("fill"))

        self.zoom_fit_rail_btn = QPushButton("Zoom")
        self.zoom_fit_rail_btn.setCheckable(True)
        self.zoom_fit_rail_btn.setObjectName("PaintTool")
        self.zoom_fit_rail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._zoom_tool_mode = "zoom_in"
        self._zoom_tool_menu_opened = False
        self._zoom_tool_hold_timer = QTimer(self)
        self._zoom_tool_hold_timer.setSingleShot(True)
        self._zoom_tool_hold_timer.setInterval(420)
        self._zoom_tool_hold_timer.timeout.connect(self._show_zoom_tool_menu)
        self.zoom_fit_rail_btn.pressed.connect(self._on_zoom_tool_pressed)
        self.zoom_fit_rail_btn.released.connect(self._on_zoom_tool_released)

        self.quick_mask_rail_btn = QPushButton("Quick Mask")
        self.quick_mask_rail_btn.setCheckable(True)
        self.quick_mask_rail_btn.setObjectName("PaintTool")
        self.quick_mask_rail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quick_mask_rail_btn.clicked.connect(
            lambda checked: self._set_quick_mask_enabled(bool(checked))
        )

        self.blockout_rail_btn = QPushButton("3D")
        self.blockout_rail_btn.setObjectName("PaintTool")
        self.blockout_rail_btn.setCheckable(True)
        self.blockout_rail_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.blockout_rail_btn.clicked.connect(
            lambda: self._set_canvas_workspace_mode("3d_place")
        )

        self._configure_paint_tool_icon_button(
            self.select_btn,
            "move-tool",
            "Move / Select Objects (V)",
        )
        self._configure_paint_tool_icon_button(self.pan_btn, "hand", "Hand / Pan Canvas (H)")
        self._configure_paint_tool_icon_button(
            self.rect_select_btn,
            "marquee-rect",
            "Rectangular Marquee (M)",
        )
        self._configure_paint_tool_icon_button(
            self.ellipse_select_btn,
            "marquee-ellipse",
            "Elliptical Marquee",
        )
        self._configure_paint_tool_icon_button(
            self.magic_select_btn,
            "magic-wand",
            "Magic Select / Select by Color (W)",
        )
        self._configure_paint_tool_icon_button(self.crop_btn, "crop", "Crop Tool (C)")
        self._configure_paint_tool_icon_button(
            self.mirror_x_btn,
            "mirror-x",
            "Mirror Drawing Horizontally",
        )
        self._configure_paint_tool_icon_button(
            self.mirror_y_btn,
            "mirror-y",
            "Mirror Drawing Vertically",
        )
        self._configure_paint_tool_icon_button(self.pen_btn, "paint-brush", "Brush Tool (B)")
        self.pen_btn.setToolTip("Brush Tool (B)")
        self._configure_paint_tool_icon_button(self.eraser_btn, "eraser", "Eraser Tool (E)")
        self._configure_paint_tool_icon_button(self.path_btn, "pen-nib", "Pen / Path Tool (P)")
        self._configure_paint_tool_icon_button(self.bubble_btn, "caption", tr("bubble.add_button"))
        self._configure_paint_tool_icon_button(self.sticker_btn, "image", tr("sticker.add_button"))
        self._configure_paint_tool_icon_button(self.editor_object_btn, "layers", "Editor Object")
        self._configure_paint_tool_icon_button(self.cutout_btn, "scissors", "Cutout")
        self._configure_paint_tool_icon_button(
            self.fill_tool_btn,
            "paint-bucket",
            "Paint Bucket / Fill (G)",
        )
        self._configure_paint_tool_icon_button(
            self.zoom_fit_rail_btn,
            "zoom",
            "Zoom Tool: click to activate, hold for Zoom In / Zoom Out / Zoom Area (Z)",
        )
        self._configure_paint_tool_icon_button(
            self.quick_mask_rail_btn,
            "quick-mask",
            "Quick Mask Mode (Q)",
        )
        self._configure_paint_tool_icon_button(self.blockout_rail_btn, "box", "3D Blockout")
        self._configure_paint_tool_icon_button(self.clear_btn, "trash", tr("paint.btn.clear_all"))

        self._painter_tool_shortcuts: list[QShortcut] = []
        for key, handler in (
            ("V", lambda: self._set_tool("select")),
            (
                "W",
                lambda: self._handle_painter_3d_camera_shortcut(
                    Qt.Key.Key_W,
                    paint_fallback=lambda: self._set_tool("magic_select"),
                ),
            ),
            ("C", lambda: self._set_tool("crop")),
            ("B", lambda: self._set_tool("pen")),
            ("E", lambda: self._set_tool("eraser")),
            ("G", lambda: self._set_tool("fill")),
            ("P", lambda: self._set_tool("path")),
            ("Z", lambda: self._set_zoom_tool_mode("zoom_in")),
        ):
            self._register_painter_tool_shortcut(key, handler)
        self._blockout_camera_shortcuts: list[QShortcut] = []
        for key, qt_key in (
            ("A", Qt.Key.Key_A),
            ("S", Qt.Key.Key_S),
            ("D", Qt.Key.Key_D),
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setEnabled(False)
            shortcut.activated.connect(
                lambda value=qt_key: self._handle_painter_3d_camera_shortcut(value)
            )
            self._blockout_camera_shortcuts.append(shortcut)

        self._paint_toolbar_order = [
            "move",
            "rect_marquee",
            "ellipse_marquee",
            "magic_select",
            "crop",
            "brush",
            "eraser",
            "fill",
            "path",
            "hand",
            "zoom",
            "quick_mask",
            "mirror_x",
            "mirror_y",
            "3d_blockout",
        ]
        for group in (
            (
                self.select_btn,
                self.rect_select_btn,
                self.ellipse_select_btn,
                self.magic_select_btn,
                self.crop_btn,
            ),
            (self.pen_btn, self.eraser_btn, self.fill_tool_btn, self.path_btn),
            (self.pan_btn, self.zoom_fit_rail_btn, self.quick_mask_rail_btn),
            (self.mirror_x_btn, self.mirror_y_btn, self.blockout_rail_btn),
        ):
            if tool_buttons_layout.count():
                tool_buttons_layout.addWidget(self._make_tool_rail_separator())
            for button in group:
                tool_buttons_layout.addWidget(button)

        tool_buttons_layout.addWidget(self._make_tool_rail_separator())
        tool_buttons_layout.addWidget(self.bubble_btn)
        tool_buttons_layout.addWidget(self.sticker_btn)
        tool_buttons_layout.addWidget(self.editor_object_btn)
        tool_buttons_layout.addWidget(self.cutout_btn)
        if self._standalone:
            self.bubble_btn.hide()
            self.sticker_btn.hide()
            self.editor_object_btn.hide()
            self.cutout_btn.hide()

        tool_buttons_layout.addWidget(self.clear_btn)
        tool_layout.addWidget(tool_button_host)
        tool_layout.addStretch(1)
        self._build_tool_rail_swatch_panel(tool_layout)
        workspace.addWidget(tool_rail)

        canvas_frame = QFrame()
        canvas_frame.setObjectName("PaintCanvasFrame")
        canvas_layout = QVBoxLayout(canvas_frame)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)

        canvas_mode_bar = QWidget(canvas_frame)
        canvas_mode_bar.setObjectName("PaintCanvasModeBar")
        canvas_bar = QHBoxLayout(canvas_mode_bar)
        canvas_bar.setContentsMargins(0, 0, 0, 0)
        canvas_bar.setSpacing(2)
        canvas_title = QLabel("CANVAS")
        canvas_title.setObjectName("PaintSectionTitle")
        self._tool_status_label = QLabel("Pen")
        self._tool_status_label.setObjectName("PaintMeta")
        self._canvas_mode_paint_btn = QPushButton("Paint")
        self._canvas_mode_paint_btn.setObjectName("PaintCanvasModeButton")
        self._canvas_mode_paint_btn.setCheckable(True)
        self._canvas_mode_paint_btn.setChecked(True)
        self._canvas_mode_paint_btn.clicked.connect(
            lambda: self._set_canvas_workspace_mode("paint")
        )
        self._canvas_mode_ui_btn = QPushButton("UI Design")
        self._canvas_mode_ui_btn.setObjectName("PaintCanvasModeButton")
        self._canvas_mode_ui_btn.setCheckable(True)
        self._canvas_mode_ui_btn.clicked.connect(
            lambda: self._set_canvas_workspace_mode("ui_design")
        )
        self._canvas_mode_3d_btn = QPushButton("3D Place")
        self._canvas_mode_3d_btn.setObjectName("PaintCanvasModeButton")
        self._canvas_mode_3d_btn.setCheckable(True)
        self._canvas_mode_3d_btn.clicked.connect(
            lambda: self._set_canvas_workspace_mode("3d_place")
        )
        canvas_bar.addWidget(self._canvas_mode_paint_btn)
        canvas_bar.addWidget(self._canvas_mode_ui_btn)
        canvas_bar.addWidget(self._canvas_mode_3d_btn)
        self._ui_design_tool_host = QWidget(canvas_mode_bar)
        self._ui_design_tool_host.setObjectName("PaintUIDesignToolHost")
        ui_tool_bar = QHBoxLayout(self._ui_design_tool_host)
        ui_tool_bar.setContentsMargins(5, 0, 0, 0)
        ui_tool_bar.setSpacing(1)
        self._ui_design_tool_buttons: dict[str, QPushButton] = {}
        for label, kind, icon_name in (
            ("Select", "select", "cursor"),
            ("Frame", "frame", "ui-frame"),
            ("Rectangle", "rectangle", "rectangle"),
            ("Ellipse", "ellipse", "ellipse"),
            ("Line", "line", "line"),
            ("Text", "text", "caption"),
            ("Image", "image", "image"),
            ("Button", "button", "button"),
            ("Progress", "progress", "progress"),
        ):
            button = QPushButton("")
            button.setObjectName("PaintBlockoutModeButton")
            button.setCheckable(True)
            button.setChecked(kind == "select")
            button.setToolTip(
                "Select and move UI objects"
                if kind == "select"
                else f"Draw {label}"
            )
            button.setAccessibleName(label)
            button.setIcon(app_icon(icon_name, size=13, color="#E4E8EE"))
            button.setIconSize(icon_size(13))
            button.setFixedSize(28, 24)
            button.clicked.connect(
                lambda _checked=False, value=kind: self._set_painter_ui_tool(value)
            )
            ui_tool_bar.addWidget(button)
            self._ui_design_tool_buttons[kind] = button
        self._ui_design_snap_btn = QPushButton("")
        self._ui_design_snap_btn.setObjectName("PaintBlockoutModeButton")
        self._ui_design_snap_btn.setCheckable(True)
        self._ui_design_snap_btn.setChecked(False)
        self._ui_design_snap_btn.setToolTip("Snap position and size to an 8 px grid; rotate to 15 degrees")
        self._ui_design_snap_btn.setAccessibleName("Snap to grid")
        self._ui_design_snap_btn.setIcon(app_icon("grid", size=13, color="#E4E8EE"))
        self._ui_design_snap_btn.setIconSize(icon_size(13))
        self._ui_design_snap_btn.setFixedSize(28, 24)
        self._ui_design_snap_btn.toggled.connect(self._set_painter_ui_snap)
        ui_tool_bar.addWidget(self._ui_design_snap_btn)
        self._ui_design_view_buttons: dict[str, QPushButton] = {}
        for label, mode, icon_name in (
            ("Fit all artboards", "all", "zoom-fit"),
            ("Fit active artboard", "artboard", "fit"),
            ("Fit selection", "selection", "ui-frame"),
        ):
            button = QPushButton("")
            button.setObjectName("PaintBlockoutModeButton")
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIcon(app_icon(icon_name, size=13, color="#E4E8EE"))
            button.setIconSize(icon_size(13))
            button.setFixedSize(28, 24)
            button.clicked.connect(
                lambda _checked=False, value=mode: self._fit_painter_ui_view(value)
            )
            ui_tool_bar.addWidget(button)
            self._ui_design_view_buttons[mode] = button
        self._ui_design_view_buttons: dict[str, QPushButton] = {}
        for label, mode, icon_name in (
            ("Fit all artboards", "all", "zoom-fit"),
            ("Fit active artboard", "artboard", "fit"),
            ("Fit selection", "selection", "ui-frame"),
        ):
            button = QPushButton("")
            button.setObjectName("PaintBlockoutModeButton")
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setIcon(app_icon(icon_name, size=13, color="#E4E8EE"))
            button.setIconSize(icon_size(13))
            button.setFixedSize(28, 24)
            button.clicked.connect(
                lambda _checked=False, value=mode: self._fit_painter_ui_view(value)
            )
            ui_tool_bar.addWidget(button)
            self._ui_design_view_buttons[mode] = button
        self._ui_design_tool_host.hide()
        canvas_bar.addWidget(self._ui_design_tool_host)
        self._blockout_transform_buttons: dict[str, QPushButton] = {}
        self._blockout_transform_host = QWidget(canvas_mode_bar)
        self._blockout_transform_host.setObjectName("PaintBlockoutTransformHost")
        transform_bar = QHBoxLayout(self._blockout_transform_host)
        transform_bar.setContentsMargins(5, 0, 0, 0)
        transform_bar.setSpacing(1)
        for label, mode in (
            ("Select", "select"),
            ("Move", "move"),
            ("Rotate", "rotate"),
            ("Scale", "scale"),
        ):
            button = QPushButton(label)
            button.setObjectName("PaintBlockoutModeButton")
            button.setCheckable(True)
            button.setChecked(mode == "move")
            button.clicked.connect(
                lambda _checked=False, value=mode: self._set_3d_blockout_transform_mode(value)
            )
            transform_bar.addWidget(button)
            self._blockout_transform_buttons[mode] = button
        self._blockout_scene_menu_btn = QPushButton("Scene")
        self._blockout_scene_menu_btn.setObjectName("PaintBlockoutModeButton")
        self._blockout_scene_menu_btn.setToolTip("3D scene display, camera, and object commands")
        self._blockout_scene_menu_btn.clicked.connect(self._show_3d_blockout_scene_menu)
        transform_bar.addWidget(self._blockout_scene_menu_btn)
        canvas_bar.addWidget(self._blockout_transform_host)
        canvas_bar.addStretch(1)
        canvas_bar.addWidget(canvas_title)
        canvas_bar.addWidget(self._tool_status_label)
        self._canvas_title_label = canvas_title
        canvas_title.hide()
        self._tool_status_label.hide()
        self._blockout_transform_host.hide()

        canvas_host = QWidget()
        canvas_host.setStyleSheet("background-color: #050607; border-radius: 8px;")
        canvas_host.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        canvas_host.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        canvas_host.setAcceptDrops(True)
        canvas_host.setMouseTracking(True)
        canvas_host.installEventFilter(self)
        self._canvas_host = canvas_host
        from app.painter_ui_workspace import PainterUIDesignOverlay

        self._painter_ui_overlay = PainterUIDesignOverlay(canvas_host)
        self._painter_ui_overlay.object_selection_requested.connect(
            self._select_painter_ui_object
        )
        self._painter_ui_overlay.object_geometry_requested.connect(
            self._update_painter_ui_object_geometry
        )
        self._painter_ui_overlay.object_changes_requested.connect(
            self._update_painter_ui_object_changes
        )
        self._painter_ui_overlay.objects_changes_requested.connect(
            self._update_painter_ui_objects_batch
        )
        self._painter_ui_overlay.object_create_requested.connect(
            self._create_painter_ui_object_from_rect
        )
        self._painter_ui_overlay.key_command.connect(
            self._handle_painter_ui_key_command
        )
        self._painter_ui_overlay.artboard_activation_requested.connect(
            self._set_painter_ui_artboard
        )
        self._painter_ui_overlay.artboard_activation_requested.connect(
            self._set_painter_ui_artboard
        )
        self._painter_ui_overlay.artboard_geometry_requested.connect(
            self._update_painter_ui_artboard_position
        )
        self._painter_ui_overlay.hide()

        self._bg_label = QLabel(canvas_host)
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.setStyleSheet("background-color: #050607;")
        self._bg_label.setAcceptDrops(True)
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
        self._blockout_overlay_label = QLabel(canvas_host)
        self._blockout_overlay_label.setObjectName("PaintBlockoutCanvasOverlay")
        self._blockout_overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._blockout_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._blockout_overlay_label.hide()
        self.canvas.set_strokes_snapshot(list(initial_strokes))
        self._sync_canvas_layer_view()
        self.canvas.set_tool("pen")
        self.canvas.set_pen_color(self._pen_color)
        self.canvas.set_pen_width(self._pen_width)
        self.canvas.set_pen_opacity(self._pen_opacity)
        self.canvas.set_brush_detail(**self._canvas_brush_detail_payload())
        self.canvas.stroke_added.connect(self._on_stroke_added)
        self.canvas.set_extra_paint_hook(self._paint_material_preview_overlay)
        self.canvas.zoom_requested.connect(self._handle_canvas_zoom_request)
        self.canvas.stroke_erased_at.connect(self._erase_stroke_direct)
        self.canvas.repaint_requested.connect(self._update_path_list)
        self.canvas.selection_probe_requested.connect(self._on_canvas_selection_probe)
        self.canvas.installEventFilter(self)
        self.canvas.setAcceptDrops(True)

        canvas_layout.addWidget(canvas_mode_bar)
        canvas_layout.addWidget(canvas_host, stretch=1)
        workspace.addWidget(canvas_frame, stretch=1)

        inspector = QFrame()
        inspector.setObjectName("PaintInspector")
        inspector.setMinimumWidth(248)
        inspector.setMaximumWidth(300 if self._standalone else 330)
        inspector.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        inspector_layout.setSpacing(1)

        inspector_controls = QWidget()
        inspector_controls_layout = QVBoxLayout(inspector_controls)
        inspector_controls_layout.setContentsMargins(0, 0, 6, 0)
        inspector_controls_layout.setSpacing(4)
        inspector_controls.setMinimumWidth(0)
        inspector_controls.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self._paint_inspector_controls = inspector_controls

        inspector_controls_scroll = QScrollArea()
        inspector_controls_scroll.setObjectName("PaintInspectorScroll")
        inspector_controls_scroll.setWidgetResizable(True)
        inspector_controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        inspector_controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inspector_controls_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        if self._standalone:
            inspector_controls_scroll.setMinimumHeight(150)
            inspector_controls_scroll.setMaximumHeight(330)
        else:
            inspector_controls_scroll.setMinimumHeight(160)
            inspector_controls_scroll.setMaximumHeight(360)
        inspector_controls_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        inspector_controls_scroll.setWidget(inspector_controls)
        self._paint_inspector_controls_scroll = inspector_controls_scroll

        tool_options_title = QLabel("TOOL OPTIONS")
        tool_options_title.setObjectName("PaintSectionTitle")
        tool_options_title.hide()

        self._selection_options_widget = QWidget(self._tool_options_host)
        selection_row = QHBoxLayout(self._selection_options_widget)
        selection_row.setContentsMargins(0, 0, 0, 0)
        selection_row.setSpacing(3)
        selection_label = QLabel("Mode")
        selection_label.setObjectName("PaintMeta")
        selection_row.addWidget(selection_label)
        self._selection_mode_buttons: dict[str, QPushButton] = {}
        for mode, icon_name, tooltip in (
            ("new", "selection-new", "New selection"),
            ("add", "plus", "Add to selection"),
            ("subtract", "minus", "Subtract from selection"),
            ("intersect", "selection-intersect", "Intersect with selection"),
        ):
            button = QPushButton("")
            button.setCheckable(True)
            button.setFixedSize(24, 22)
            button.setIcon(app_icon(icon_name, size=12, color="#EEEEEE"))
            button.setIconSize(icon_size(12))
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _checked=False, value=mode: self._set_selection_combine_mode(value)
            )
            self._selection_mode_buttons[mode] = button
            selection_row.addWidget(button)
        self._selection_mode_buttons["new"].setChecked(True)
        option_separator = QFrame()
        option_separator.setObjectName("PaintOptionSeparator")
        selection_row.addWidget(option_separator)
        selection_style_label = QLabel("Style")
        selection_style_label.setObjectName("PaintMeta")
        self.selection_aspect_combo = QComboBox()
        self.selection_aspect_combo.addItem("Normal", "free")
        self.selection_aspect_combo.addItem("Fixed Ratio 1:1", "square")
        self.selection_aspect_combo.addItem("Fixed Ratio 16:9", "16:9")
        self.selection_aspect_combo.addItem("Fixed Ratio 4:3", "4:3")
        self.selection_aspect_combo.currentIndexChanged.connect(self._on_selection_aspect_changed)
        selection_row.addWidget(selection_style_label)
        selection_row.addWidget(self.selection_aspect_combo)
        self._tool_options_layout.addWidget(self._selection_options_widget)

        self._selection_action_widget = QWidget(self._tool_options_host)
        tool_action_row = QHBoxLayout(self._selection_action_widget)
        tool_action_row.setContentsMargins(0, 0, 0, 0)
        tool_action_row.setSpacing(3)
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
        self._tool_options_layout.addWidget(self._selection_action_widget)

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
        self.quick_mask_btn.hide()
        self.grid_view_btn.hide()
        self.snap_grid_btn.hide()

        self._magic_options_widget = QWidget(self._tool_options_host)
        magic_row = QHBoxLayout(self._magic_options_widget)
        magic_row.setContentsMargins(0, 0, 0, 0)
        magic_row.setSpacing(5)
        magic_label = QLabel("Tolerance")
        magic_label.setObjectName("PaintMeta")
        magic_row.addWidget(magic_label)
        self.magic_tolerance_slider = QSpinBox()
        self.magic_tolerance_slider.setRange(0, 100)
        self.magic_tolerance_slider.setValue(self._magic_select_tolerance)
        self.magic_tolerance_slider.setFixedWidth(58)
        self.magic_tolerance_slider.valueChanged.connect(self._on_magic_tolerance_changed)
        magic_row.addWidget(self.magic_tolerance_slider)
        self._magic_tolerance_value_label = QLabel(f"{self._magic_select_tolerance}")
        self._magic_tolerance_value_label.setObjectName("PaintValue")
        self._magic_tolerance_value_label.hide()
        self._tool_options_layout.addWidget(self._magic_options_widget)

        self._fill_options_widget = QWidget(self._tool_options_host)
        fill_action_row = QHBoxLayout(self._fill_options_widget)
        fill_action_row.setContentsMargins(0, 0, 0, 0)
        fill_action_row.setSpacing(3)
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
        self._tool_options_layout.addWidget(self._fill_options_widget)

        self._brush_options_widget = QWidget(self._tool_options_host)
        brush_options_row = QHBoxLayout(self._brush_options_widget)
        brush_options_row.setContentsMargins(0, 0, 0, 0)
        brush_options_row.setSpacing(5)
        self._brush_preset_button = QPushButton("Brush Selector")
        self._brush_preset_button.setObjectName("PaintBrushPresetButton")
        self._brush_preset_button.setCheckable(True)
        self._brush_preset_button.setIcon(app_icon("list", size=13, color="#EEEEEE"))
        self._brush_preset_button.setIconSize(icon_size(13))
        self._brush_preset_button.setToolTip("Show Brush Selector below")
        self._brush_preset_button.clicked.connect(self._focus_brush_selector)
        brush_options_row.addWidget(self._brush_preset_button)
        size_label = QLabel("Size")
        size_label.setObjectName("PaintMeta")
        brush_options_row.addWidget(size_label)
        self._top_brush_size_spin = QSpinBox()
        self._top_brush_size_spin.setRange(1, 60)
        self._top_brush_size_spin.setSuffix(" px")
        self._top_brush_size_spin.setValue(int(round(self._pen_width)))
        self._top_brush_size_spin.setFixedWidth(72)
        self._top_brush_size_spin.valueChanged.connect(self._on_width_changed)
        brush_options_row.addWidget(self._top_brush_size_spin)
        opacity_label = QLabel("Opacity")
        opacity_label.setObjectName("PaintMeta")
        brush_options_row.addWidget(opacity_label)
        self._top_brush_opacity_spin = QSpinBox()
        self._top_brush_opacity_spin.setRange(1, 100)
        self._top_brush_opacity_spin.setSuffix("%")
        self._top_brush_opacity_spin.setValue(100)
        self._top_brush_opacity_spin.setFixedWidth(66)
        self._top_brush_opacity_spin.valueChanged.connect(self._on_opacity_changed)
        brush_options_row.addWidget(self._top_brush_opacity_spin)
        self._material_options_button = QPushButton("Material")
        self._material_options_button.setObjectName("PaintMaterialOptionsButton")
        self._material_options_button.setIcon(app_icon("layers", size=12, color="#E7C06A"))
        self._material_options_button.setIconSize(icon_size(12))
        self._material_options_button.setToolTip(
            "Load, thickness, wetness, gloss, and roughness for Material Paint strokes"
        )
        self._material_options_button.setMenu(self._build_material_options_menu())
        brush_options_row.addWidget(self._material_options_button)
        self._material_preview_button = QPushButton("PBR")
        self._material_preview_button.setObjectName("PaintMaterialPreviewButton")
        self._material_preview_button.setCheckable(True)
        self._material_preview_button.setToolTip("Preview authored paint relief under a movable light")
        self._material_preview_button.toggled.connect(self._set_material_preview_enabled)
        brush_options_row.addWidget(self._material_preview_button)
        self._tool_options_layout.addWidget(self._brush_options_widget)

        self._paint_brush_section_title = QLabel("BRUSH")
        self._paint_brush_section_title.setObjectName("PaintSectionTitle")
        inspector_controls_layout.addWidget(self._paint_brush_section_title)
        self._paint_brush_detail_panel = self._build_brush_detail_panel()
        inspector_controls_layout.addWidget(self._paint_brush_detail_panel)
        self._paint_brush_section_title.hide()
        self._paint_brush_detail_panel.hide()

        color_title = QLabel("COLOR")
        color_title.setObjectName("PaintSectionTitle")
        self._paint_color_section_title = color_title
        color_title.hide()
        color_panel = QFrame()
        color_panel.setObjectName("PaintColorPanel")
        color_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        color_panel.setMinimumHeight(148)
        color_panel.setMaximumHeight(194)
        self._paint_color_panel = color_panel
        color_panel_layout = QVBoxLayout(color_panel)
        color_panel_layout.setContentsMargins(0, 0, 0, 0)
        color_panel_layout.setSpacing(0)

        color_tabs = QTabWidget()
        color_tabs.setObjectName("PaintColorTabs")
        color_tabs.setDocumentMode(True)
        color_tabs.tabBar().setExpanding(False)
        color_tabs.tabBar().setUsesScrollButtons(False)
        self._paint_color_tabs = color_tabs
        color_page = QWidget()
        color_page_layout = QVBoxLayout(color_page)
        color_page_layout.setContentsMargins(6, 5, 6, 6)
        color_page_layout.setSpacing(4)
        color_row = QHBoxLayout()
        color_row.setContentsMargins(0, 0, 0, 0)
        self._color_preview = QLabel()
        self._color_preview.setObjectName("PaintColorWell")
        self._color_preview.setFixedSize(20, 20)
        self._color_hex_label = QLabel("#E54646")
        self._color_hex_label.setObjectName("PaintColorHex")
        color_row.addWidget(self._color_preview)
        color_row.addWidget(self._color_hex_label)
        color_row.addStretch(1)
        self.custom_color_btn = QPushButton("...")
        self.custom_color_btn.setObjectName("PaintCustomColor")
        self.custom_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.custom_color_btn.setToolTip("Open advanced color picker")
        self.custom_color_btn.setFixedSize(24, 20)
        self.custom_color_btn.clicked.connect(self._pick_custom_color)
        color_row.addWidget(self.custom_color_btn)
        color_page_layout.addLayout(color_row)

        self.photoshop_color_field = PainterPhotoshopColorField()
        self.photoshop_color_field.colorChanged.connect(self._on_color_wheel_changed)
        color_page_layout.addWidget(self.photoshop_color_field)
        color_tabs.addTab(color_page, "Color")

        wheel_frame = QFrame()
        wheel_frame.setObjectName("PaintColorWheelFrame")
        wheel_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._paint_color_wheel_frame = wheel_frame
        wheel_row = QHBoxLayout(wheel_frame)
        wheel_row.setContentsMargins(7, 7, 7, 7)
        wheel_row.setSpacing(0)
        self.color_wheel = PainterColorWheel()
        self.color_wheel.colorChanged.connect(self._on_color_wheel_changed)
        wheel_row.addWidget(self.color_wheel, 0, Qt.AlignmentFlag.AlignCenter)
        wheel_frame.hide()
        self.color_wheel.hide()

        swatches_page = QWidget()
        swatches_layout = QVBoxLayout(swatches_page)
        swatches_layout.setContentsMargins(5, 5, 5, 5)
        swatches_layout.setSpacing(4)
        matrix_frame = QFrame()
        matrix_frame.setObjectName("PaintColorMatrixFrame")
        self._paint_color_matrix_frame = matrix_frame
        matrix_grid = QGridLayout(matrix_frame)
        matrix_grid.setContentsMargins(2, 2, 2, 2)
        matrix_grid.setHorizontalSpacing(3)
        matrix_grid.setVerticalSpacing(3)
        self._palette_btns: list[QPushButton] = []
        for idx, (rgb, label) in enumerate(self._derived_palette_colors()):
            btn = self._make_palette_button(rgb, width=44, height=18)
            btn.setToolTip(label)
            matrix_grid.addWidget(btn, idx // 4, idx % 4)
            self._palette_btns.append(btn)
        swatches_layout.addWidget(matrix_frame)

        mixer_label = QLabel("Mixer")
        mixer_label.setObjectName("PaintColorSectionLabel")
        self._paint_mixer_label = mixer_label
        self.hue_slider = QSlider(Qt.Orientation.Horizontal)
        self.hue_slider.setObjectName("PaintHueSlider")
        self.hue_slider.setRange(0, 359)
        self.hue_slider.valueChanged.connect(self._on_hue_changed)
        self.hue_slider.hide()
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setObjectName("PaintSaturationSlider")
        self.saturation_slider.setRange(0, 100)
        self.saturation_slider.valueChanged.connect(self._on_saturation_changed)
        self.saturation_slider.hide()
        self.value_slider = QSlider(Qt.Orientation.Horizontal)
        self.value_slider.setObjectName("PaintValueSlider")
        self.value_slider.setRange(12, 100)
        self.value_slider.valueChanged.connect(self._on_value_changed)
        self.value_slider.hide()

        recent_label = QLabel("Recent Colors")
        recent_label.setObjectName("PaintColorSectionLabel")
        swatches_layout.addWidget(recent_label)
        recent_row = QHBoxLayout()
        recent_row.setContentsMargins(0, 0, 0, 0)
        recent_row.setSpacing(3)
        self._recent_color_btns: list[QPushButton] = []
        for rgb in self._recent_colors:
            btn = self._make_palette_button(rgb, width=24, height=14)
            recent_row.addWidget(btn)
            self._recent_color_btns.append(btn)
        recent_row.addStretch(1)
        swatches_layout.addLayout(recent_row)
        color_tabs.addTab(swatches_page, "Swatches")

        gradients_page = QWidget()
        gradients_layout = QVBoxLayout(gradients_page)
        gradients_layout.setContentsMargins(6, 6, 6, 6)
        for label in ("Foreground to Background", "Foreground to Transparent", "Black to White"):
            button = QPushButton(label)
            button.setObjectName("PaintFlatPresetButton")
            button.clicked.connect(lambda _checked=False: self._fill_document("gradient"))
            gradients_layout.addWidget(button)
        gradients_layout.addStretch(1)
        color_tabs.addTab(gradients_page, "Gradients")

        patterns_page = QWidget()
        patterns_layout = QVBoxLayout(patterns_page)
        patterns_layout.setContentsMargins(6, 6, 6, 6)
        for label in ("Fine Grid", "Checker", "Paper"):
            button = QPushButton(label)
            button.setObjectName("PaintFlatPresetButton")
            button.clicked.connect(lambda _checked=False: self._fill_document("pattern"))
            patterns_layout.addWidget(button)
        patterns_layout.addStretch(1)
        color_tabs.addTab(patterns_page, "Patterns")

        suggested_label = QLabel("Shades")
        suggested_label.setObjectName("PaintColorSectionLabel")
        self._paint_harmony_label = suggested_label
        suggested_label.hide()

        color_panel_layout.addWidget(color_tabs)
        inspector_controls_layout.addWidget(color_panel)

        self._paint_reference_panel = self._build_reference_board_panel()
        inspector_controls_layout.addWidget(self._paint_reference_panel)
        self._paint_reference_panel.hide()

        self._paint_3d_blockout_panel = self._build_3d_blockout_panel()
        inspector_controls_layout.addWidget(self._paint_3d_blockout_panel)
        self._paint_3d_blockout_panel.hide()

        from app.painter_ui_inspector import PainterUIInspector

        self._paint_ui_inspector = PainterUIInspector()
        self._paint_ui_inspector.selection_changed.connect(
            self._set_painter_ui_selection
        )
        self._paint_ui_inspector.artboard_selected.connect(
            self._set_painter_ui_artboard
        )
        self._paint_ui_inspector.artboard_add_requested.connect(
            self._add_painter_ui_artboard_preset
        )
        self._paint_ui_inspector.artboard_layout_changed.connect(
            self._update_painter_ui_artboard_changes
        )
        self._paint_ui_inspector.geometry_changed.connect(
            self._update_painter_ui_object_changes
        )
        self._paint_ui_inspector.properties_changed.connect(
            self._update_painter_ui_object_changes
        )
        self._paint_ui_inspector.responsive_override_changed.connect(
            self._update_painter_ui_responsive_override
        )
        self._paint_ui_inspector.responsive_override_remove_requested.connect(
            self._remove_painter_ui_responsive_override
        )
        self._paint_ui_inspector.component_create_requested.connect(
            self._create_painter_ui_component
        )
        self._paint_ui_inspector.component_instantiate_requested.connect(
            self._instantiate_painter_ui_component
        )
        self._paint_ui_inspector.component_variant_create_requested.connect(
            self._create_painter_ui_component_variant
        )
        self._paint_ui_inspector.component_variant_switch_requested.connect(
            self._switch_painter_ui_component_variant
        )
        self._paint_ui_inspector.component_detach_requested.connect(
            self._detach_painter_ui_component
        )
        self._paint_ui_inspector.component_update_requested.connect(
            self._update_painter_ui_component
        )
        self._paint_ui_inspector.token_add_requested.connect(
            self._add_painter_ui_token
        )
        self._paint_ui_inspector.token_update_requested.connect(
            self._update_painter_ui_token
        )
        self._paint_ui_inspector.token_remove_requested.connect(
            self._remove_painter_ui_token
        )
        self._paint_ui_inspector.token_binding_requested.connect(
            self._bind_painter_ui_token
        )
        self._paint_ui_inspector.duplicate_requested.connect(
            self._duplicate_painter_ui_object
        )
        self._paint_ui_inspector.delete_requested.connect(
            self._delete_painter_ui_object
        )
        self._paint_ui_inspector.arrange_requested.connect(
            self._align_painter_ui_object
        )
        self._paint_ui_inspector.group_requested.connect(
            self._group_painter_ui_objects
        )
        self._paint_ui_inspector.ungroup_requested.connect(
            self._ungroup_painter_ui_object
        )
        self._paint_ui_inspector.reorder_requested.connect(
            self._reorder_painter_ui_objects
        )
        self._paint_ui_inspector.hierarchy_drop_requested.connect(
            self._move_painter_ui_hierarchy
        )
        inspector_controls_layout.addWidget(self._paint_ui_inspector, stretch=1)
        self._paint_ui_inspector.hide()

        self._layer_channel_path_tabs = QTabWidget()
        self._layer_channel_path_tabs.setObjectName("PaintLayerChannelPathTabs")
        self._layer_channel_path_tabs.setDocumentMode(True)
        self._layer_channel_path_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._layer_channel_path_tabs.setMinimumHeight(300 if self._standalone else 250)
        self._layer_channel_path_tabs.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        tab_bar = self._layer_channel_path_tabs.tabBar()
        tab_bar.setUsesScrollButtons(False)
        tab_bar.setExpanding(False)
        tab_bar.setElideMode(Qt.TextElideMode.ElideRight)

        layers_tab = QWidget()
        layers_layout = QVBoxLayout(layers_tab)
        layers_layout.setContentsMargins(4, 4, 4, 3)
        layers_layout.setSpacing(3)

        layer_controls = QFrame()
        layer_controls.setObjectName("PaintLayerControlPanel")
        layer_controls.setMinimumHeight(122)
        layer_controls.setMaximumHeight(132)
        layer_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layer_controls_layout = QVBoxLayout(layer_controls)
        layer_controls_layout.setContentsMargins(3, 3, 3, 3)
        layer_controls_layout.setSpacing(2)

        layer_filter_row = QHBoxLayout()
        layer_filter_row.setContentsMargins(0, 0, 0, 0)
        layer_filter_row.setSpacing(6)
        self.layer_filter_combo = QComboBox()
        self.layer_filter_combo.setObjectName("PaintLayerFilterCombo")
        self.layer_filter_combo.addItem(tr("paint.layer.filter_kind"), "kind")
        self.layer_filter_combo.setFixedHeight(24)
        layer_filter_row.addWidget(self.layer_filter_combo, stretch=1)
        layer_controls_layout.addLayout(layer_filter_row)

        layer_filter_icon_strip = QWidget()
        layer_filter_icon_strip.setObjectName("PaintLayerFilterStrip")
        layer_filter_icon_row = QHBoxLayout(layer_filter_icon_strip)
        layer_filter_icon_row.setContentsMargins(0, 0, 0, 0)
        layer_filter_icon_row.setSpacing(8)
        self._layer_filter_tiny_buttons: list[QPushButton] = []
        for icon_name, label in (
            ("image", "Pixel layers"),
            ("color", "Adjustment layers"),
            ("caption", "Text layers"),
            ("path-tool", "Shape paths"),
            ("layers", "Smart objects"),
            ("more", "Layer menu"),
        ):
            btn = self._make_layer_tiny_button(icon_name, label)
            self._layer_filter_tiny_buttons.append(btn)
            layer_filter_icon_row.addWidget(btn)
        layer_filter_icon_row.addStretch(1)
        self._layer_filter_icon_strip = layer_filter_icon_strip
        layer_controls_layout.addWidget(layer_filter_icon_strip)

        layer_mode_row = QHBoxLayout()
        layer_mode_row.setContentsMargins(0, 0, 0, 0)
        layer_mode_row.setSpacing(6)
        self.layer_blend_combo = QComboBox()
        self.layer_blend_combo.setObjectName("PaintLayerBlendCombo")
        self.layer_blend_combo.addItem(tr("paint.layer.blend_normal"), "normal")
        self.layer_blend_combo.addItem("Multiply", "multiply")
        self.layer_blend_combo.addItem("Screen", "screen")
        self.layer_blend_combo.addItem("Overlay", "overlay")
        self.layer_blend_combo.setFixedHeight(24)
        self.layer_blend_combo.currentIndexChanged.connect(self._on_layer_blend_changed)
        layer_opacity_text = QLabel(tr("paint.layer.opacity"))
        layer_opacity_text.setObjectName("PaintLayerControlLabel")
        layer_opacity_text.setMinimumWidth(42)
        self._layer_opacity_label = layer_opacity_text
        self._layer_opacity_value = QSpinBox()
        self._layer_opacity_value.setObjectName("PaintLayerOpacitySpin")
        self._layer_opacity_value.setRange(0, 100)
        self._layer_opacity_value.setSuffix("%")
        self._layer_opacity_value.setValue(100)
        self._layer_opacity_value.setFixedWidth(58)
        self._layer_opacity_value.valueChanged.connect(self._on_layer_opacity_changed)
        layer_mode_row.addWidget(self.layer_blend_combo, stretch=1)
        layer_mode_row.addWidget(layer_opacity_text)
        layer_mode_row.addWidget(self._layer_opacity_value)
        layer_controls_layout.addLayout(layer_mode_row)

        self.layer_opacity_slider = StudioSlider("accent")
        self.layer_opacity_slider.setRange(0, 100)
        self.layer_opacity_slider.setValue(100)
        self.layer_opacity_slider.setFixedHeight(18)
        self.layer_opacity_slider.valueChanged.connect(self._on_layer_opacity_changed)
        self.layer_opacity_slider.hide()

        layer_lock_row = QHBoxLayout()
        layer_lock_row.setContentsMargins(0, 0, 0, 0)
        layer_lock_row.setSpacing(8)
        layer_lock_label = QLabel(tr("paint.layer.lock"))
        layer_lock_label.setObjectName("PaintLayerControlLabel")
        self._layer_lock_label = layer_lock_label
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
        layer_controls_layout.addLayout(layer_lock_row)

        layer_fill_row = QHBoxLayout()
        layer_fill_row.setContentsMargins(0, 0, 0, 0)
        layer_fill_row.setSpacing(6)
        layer_fill_row.addStretch(1)
        layer_fill_label = QLabel(tr("paint.layer.fill"))
        layer_fill_label.setObjectName("PaintLayerControlLabel")
        self._layer_fill_label = layer_fill_label
        self._layer_fill_value = QLabel("100%")
        self._layer_fill_value.setObjectName("PaintValue")
        self._layer_fill_value.setFixedWidth(46)
        layer_fill_row.addWidget(layer_fill_label)
        layer_fill_row.addWidget(self._layer_fill_value)
        layer_controls_layout.addLayout(layer_fill_row)
        layers_layout.addWidget(layer_controls)

        self._layer_list = QListWidget()
        self._layer_list.setObjectName("PaintLayerList")
        self._layer_list.setMinimumHeight(126)
        self._layer_list.setIconSize(QSize(58, 30))
        self._layer_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._layer_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._layer_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._layer_list.setDragEnabled(True)
        self._layer_list.setAcceptDrops(True)
        self._layer_list.setDropIndicatorShown(True)
        self._layer_list.itemClicked.connect(self._select_layer_item)
        self._layer_list.itemDoubleClicked.connect(self._rename_layer_item)
        self._layer_list.model().rowsMoved.connect(self._on_layer_rows_moved)
        self._layer_list.viewport().installEventFilter(self)
        self._layer_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._layer_list.customContextMenuRequested.connect(self._open_layer_context_menu)
        layers_layout.addWidget(self._layer_list, stretch=1)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        self.layer_new_btn = self._make_layer_tiny_button("plus", "New Layer")
        self.layer_new_material_btn = self._make_layer_tiny_button(
            "layers",
            "New Material Paint Layer",
        )
        self.layer_duplicate_btn = self._make_layer_tiny_button("duplicate", "Duplicate Layer")
        self.layer_copy_btn = self._make_layer_tiny_button("copy", "Copy Layer")
        self.layer_paste_btn = self._make_layer_tiny_button("paste", "Paste Layer")
        self.layer_delete_btn = self._make_layer_tiny_button("trash", "Delete Layer")
        for btn, handler in (
            (self.layer_new_btn, self._new_paint_layer),
            (self.layer_new_material_btn, self._new_material_paint_layer),
            (self.layer_duplicate_btn, self._duplicate_selected_layer),
            (self.layer_copy_btn, self._copy_selected_layer),
            (self.layer_paste_btn, self._paste_layer_clipboard),
            (self.layer_delete_btn, self._delete_selected_layer),
        ):
            btn.clicked.connect(handler)
            edit_row.addWidget(btn)
        edit_row.addStretch(1)
        layers_layout.addLayout(edit_row)
        self._layer_count_labels: dict[str, QLabel] = {}
        self._layer_channel_path_tabs.addTab(layers_tab, tr("paint.tab.layers"))
        self._layer_channel_path_tabs.setTabToolTip(0, tr("paint.tab.layers"))

        channels_tab = QWidget()
        channels_layout = QVBoxLayout(channels_tab)
        channels_layout.setContentsMargins(4, 4, 4, 3)
        channels_layout.setSpacing(3)
        channel_row = QHBoxLayout()
        channel_row.setContentsMargins(0, 0, 0, 0)
        self.copy_channel_btn = self._make_layer_tiny_button("copy", "Copy selected channel image")
        self.copy_channel_btn.setToolTip("Copy the selected channel image to the system clipboard")
        self.copy_channel_btn.clicked.connect(self._copy_selected_channel_image)
        self.paste_channel_btn = self._make_layer_tiny_button("paste", "Paste image into selected channel")
        self.paste_channel_btn.setToolTip("Paste a grayscale clipboard image into the selected channel")
        self.paste_channel_btn.clicked.connect(self._paste_selected_channel_image)
        channel_row.addWidget(self.copy_channel_btn)
        channel_row.addWidget(self.paste_channel_btn)
        channel_row.addStretch(1)
        self._channel_list = QListWidget()
        self._channel_list.setObjectName("PaintLayerList")
        self._channel_list.setMinimumHeight(150)
        self._channel_list.setIconSize(QSize(58, 30))
        self._channel_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._channel_list.itemClicked.connect(self._select_channel_item)
        self._channel_list.viewport().installEventFilter(self)
        self._update_channel_list()
        channels_layout.addWidget(self._channel_list, stretch=1)
        channels_layout.addLayout(channel_row)
        self._layer_channel_path_tabs.addTab(channels_tab, tr("paint.tab.channels"))
        self._layer_channel_path_tabs.setTabToolTip(1, tr("paint.tab.channels"))

        paths_tab = QWidget()
        paths_layout = QVBoxLayout(paths_tab)
        paths_layout.setContentsMargins(4, 4, 4, 3)
        paths_layout.setSpacing(3)
        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        self.commit_path_btn = self._make_layer_tiny_button("path-tool", "Save/commit Work Path")
        self.commit_path_btn.clicked.connect(lambda: self._commit_path(False))
        self.close_path_btn = self._make_layer_tiny_button("shape", "Close Work Path")
        self.close_path_btn.clicked.connect(lambda: self._commit_path(True))
        self.path_to_selection_btn = self._make_layer_tiny_button("rect-select", "Load path as selection")
        self.path_to_selection_btn.setToolTip("Convert the selected path to a marching-ants selection")
        self.path_to_selection_btn.clicked.connect(self._make_selection_from_selected_path)
        self.path_to_mask_btn = self._make_layer_tiny_button("quick-mask", "Make layer mask from path")
        self.path_to_mask_btn.setToolTip("Convert the selected path to a layer mask")
        self.path_to_mask_btn.clicked.connect(self._mask_selected_layer_from_path)
        self.clear_path_btn = self._make_layer_tiny_button("trash", "Clear Work Path")
        self.clear_path_btn.clicked.connect(self._clear_path_preview)
        path_row.addWidget(self.commit_path_btn)
        path_row.addWidget(self.close_path_btn)
        path_row.addWidget(self.path_to_selection_btn)
        path_row.addWidget(self.path_to_mask_btn)
        path_row.addWidget(self.clear_path_btn)
        path_row.addStretch(1)
        self._path_list = QListWidget()
        self._path_list.setObjectName("PaintLayerList")
        self._path_list.setMinimumHeight(170)
        self._path_list.setIconSize(QSize(58, 30))
        self._path_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._path_list.itemClicked.connect(self._select_path_item)
        paths_layout.addWidget(self._path_list, stretch=1)
        paths_layout.addLayout(path_row)
        self._layer_channel_path_tabs.addTab(paths_tab, tr("paint.tab.paths"))
        self._layer_channel_path_tabs.setTabToolTip(2, tr("paint.tab.paths"))

        inspector_controls_layout.addStretch(1)

        layer_dock_panel = QFrame()
        layer_dock_panel.setObjectName("PaintLayerDockPanel")
        layer_dock_panel.setMinimumHeight(340 if self._standalone else 280)
        layer_dock_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._paint_layer_dock_panel = layer_dock_panel
        layer_dock_layout = QVBoxLayout(layer_dock_panel)
        layer_dock_layout.setContentsMargins(0, 0, 0, 0)
        layer_dock_layout.setSpacing(0)
        layer_dock_layout.addWidget(self._layer_channel_path_tabs, stretch=1)
        self._paint_export_note = None

        inspector_layout.addWidget(inspector_controls_scroll, stretch=1)
        inspector_layout.addWidget(layer_dock_panel, stretch=2)
        workspace.addWidget(inspector)

        status_bar = QFrame()
        status_bar.setObjectName("PaintStatusBar")
        status_bar.setFixedHeight(23)
        status_layout = QHBoxLayout(status_bar)
        status_layout.setContentsMargins(7, 1, 8, 1)
        status_layout.setSpacing(8)
        self._status_zoom_spin = QSpinBox()
        self._status_zoom_spin.setRange(25, PAINT_MAX_ZOOM_PERCENT)
        self._status_zoom_spin.setSuffix("%")
        self._status_zoom_spin.setValue(100)
        self._status_zoom_spin.setFixedWidth(58)
        self._status_zoom_spin.valueChanged.connect(self._set_zoom_percent)
        status_layout.addWidget(self._status_zoom_spin)
        status_separator = QFrame()
        status_separator.setObjectName("PaintOptionSeparator")
        status_layout.addWidget(status_separator)
        self._status_document_label = QLabel(
            f"{self._canvas_document_size[0]} x {self._canvas_document_size[1]} px"
        )
        status_layout.addWidget(self._status_document_label)
        status_layout.addStretch(1)
        self._status_layer_label = QLabel("Layer 1")
        status_layout.addWidget(self._status_layer_label)
        root.addWidget(status_bar)
        self._paint_status_bar = status_bar

        self._sync_palette_controls_from_color()
        self._highlight_selected_palette()
        self._update_brush_detail_preview()
        self._update_inspector_counts()
        self._install_edit_shortcuts()
        self._set_tool("pen")

    def _build_reference_board_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PaintReferencePanel")
        panel.setMinimumHeight(250)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("REFERENCE")
        title.setObjectName("PaintSectionTitle")
        self._reference_status_label = QLabel("0 pinned")
        self._reference_status_label.setObjectName("PaintBlockoutStatus")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._reference_status_label)
        layout.addLayout(header)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(4)
        self.reference_add_btn = QPushButton("Image")
        self.reference_clipboard_btn = QPushButton("Clip")
        self.reference_duplicate_btn = QPushButton("Dup")
        self.reference_delete_btn = QPushButton("Del")
        self.reference_bake_btn = QPushButton("Bake")
        option_row = QHBoxLayout()
        option_row.setContentsMargins(0, 0, 0, 0)
        option_row.setSpacing(4)
        self.reference_overlay_btn = QPushButton("Overlay")
        self.reference_overlay_btn.setCheckable(True)
        self.reference_overlay_btn.setChecked(True)
        self.reference_visible_btn = QPushButton("Visible")
        self.reference_visible_btn.setCheckable(True)
        self.reference_visible_btn.setChecked(True)
        self.reference_lock_btn = QPushButton("Lock")
        self.reference_lock_btn.setCheckable(True)
        self.reference_sample_btn = QPushButton("Sample")
        self.reference_palette_btn = QPushButton("Palette")
        for btn, handler in (
            (self.reference_add_btn, self._add_reference_image_from_file),
            (self.reference_clipboard_btn, self._add_reference_image_from_clipboard),
            (self.reference_duplicate_btn, self._duplicate_selected_reference_image),
            (self.reference_delete_btn, self._delete_selected_reference_image),
            (self.reference_bake_btn, self._bake_selected_reference_to_sticker),
        ):
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            action_row.addWidget(btn)
        for btn in (
            self.reference_overlay_btn,
            self.reference_visible_btn,
            self.reference_lock_btn,
            self.reference_sample_btn,
            self.reference_palette_btn,
        ):
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            option_row.addWidget(btn)
        self.reference_overlay_btn.toggled.connect(lambda _checked=False: self._refresh_reference_overlay())
        self.reference_visible_btn.toggled.connect(lambda checked=False: self._set_selected_reference_visible(bool(checked)))
        self.reference_lock_btn.toggled.connect(lambda checked=False: self._set_selected_reference_locked(bool(checked)))
        self.reference_sample_btn.clicked.connect(self._sample_selected_reference_color)
        self.reference_palette_btn.clicked.connect(self._extract_selected_reference_palette)
        layout.addLayout(action_row)
        layout.addLayout(option_row)

        self._reference_preview_label = QLabel("Drop references here")
        self._reference_preview_label.setObjectName("PaintReferencePreview")
        self._reference_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._reference_preview_label.setMinimumHeight(92)
        layout.addWidget(self._reference_preview_label)

        self._reference_list = QListWidget()
        self._reference_list.setObjectName("PaintReferenceList")
        self._reference_list.setMaximumHeight(74)
        self._reference_list.itemClicked.connect(self._select_reference_item)
        layout.addWidget(self._reference_list)

        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(6)
        controls.setVerticalSpacing(4)
        for index, spec in enumerate(
            (
                ("X", "ref_x", 0, 100, 4, "%"),
                ("Y", "ref_y", 0, 100, 4, "%"),
                ("W", "ref_w", 2, 100, 34, "%"),
                ("H", "ref_h", 2, 100, 34, "%"),
                ("Op", "ref_opacity", 5, 100, 58, "%"),
                ("Rot", "ref_rotation", -180, 180, 0, " deg"),
            )
        ):
            row, col = divmod(index, 3)
            self._add_reference_spin(controls, row, col, *spec)
        layout.addLayout(controls)
        QTimer.singleShot(0, self._refresh_reference_board_panel)
        return panel

    def _add_reference_spin(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        label_text: str,
        key: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
    ) -> None:
        label = QLabel(label_text)
        label.setObjectName("PaintMeta")
        box = QSpinBox()
        box.setObjectName("PaintLayerBlendCombo")
        box.setRange(int(minimum), int(maximum))
        box.setValue(int(value))
        box.setMinimumWidth(62)
        if suffix:
            box.setSuffix(suffix)
        box.valueChanged.connect(lambda _value, k=key: self._on_reference_spin_changed(k))
        self._painter_reference_controls[key] = box
        cell = QHBoxLayout()
        cell.setContentsMargins(0, 0, 0, 0)
        cell.setSpacing(3)
        cell.addWidget(label)
        cell.addWidget(box, stretch=1)
        host = QWidget()
        host.setLayout(cell)
        layout.addWidget(host, row, column)

    def _current_reference_board(self):
        from app.painter_reference_board import reference_board_from_dict

        return reference_board_from_dict(getattr(self, "_painter_reference_board", None))

    def _store_reference_board(self, board) -> None:
        self._painter_reference_board = board.to_dict()
        self._refresh_reference_board_panel()

    def _add_reference_image_from_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Add Reference Image",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not path:
            return
        if not self._add_reference_image_path(path):
            QMessageBox.warning(self, "Reference", "Could not load the selected image.")

    def _add_reference_image_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        image_item = self._system_clipboard_image()
        if image_item is None:
            QMessageBox.information(self, "Reference", "Clipboard does not contain an image.")
            return
        image, label = image_item
        path = self._write_reference_image_asset(image, label)
        if path is None or not self._add_reference_image_path(str(path), name="Clipboard Reference"):
            QMessageBox.warning(self, "Reference", "Could not create a reference image from the clipboard.")

    def _write_reference_image_asset(self, image: QImage, label: str = "reference") -> Path | None:
        if image.isNull():
            return None
        try:
            out_dir = PAINT_REFERENCE_IMAGE_DIR
            out_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            stem = self._safe_clipboard_image_stem(label or "reference")
            path = out_dir / f"{stem}_{stamp}.png"
            if image.save(str(path), "PNG"):
                return path.resolve()
        except Exception:
            return None
        return None

    def _add_reference_image_path(self, path: str, *, name: str = "") -> bool:
        source = Path(str(path or "")).expanduser()
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            return False
        width_norm = 0.34
        height_norm = 0.34
        if pixmap.width() > 0 and pixmap.height() > 0:
            doc_w, doc_h = getattr(self, "_canvas_document_size", (1920, 1080))
            height_norm = max(0.08, min(0.75, width_norm * (pixmap.height() / max(1, pixmap.width())) * (doc_w / max(1, doc_h))))
        from app.painter_reference_board import add_reference_image

        self._push_undo_state("Add reference")
        board = add_reference_image(
            self._current_reference_board(),
            path=str(source.resolve()),
            name=name or source.name,
            width_norm=width_norm,
            height_norm=height_norm,
        )
        rows = board.to_dict().get("references", [])
        if rows:
            self._painter_reference_selected_id = str(rows[-1].get("id") or "")
        self._store_reference_board(board)
        return True

    def _delete_selected_reference_image(self) -> None:
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        if not reference_id:
            return
        from app.painter_reference_board import delete_reference_image

        self._push_undo_state("Delete reference")
        try:
            board = delete_reference_image(self._current_reference_board(), reference_id)
        except ValueError:
            return
        rows = board.to_dict().get("references", [])
        self._painter_reference_selected_id = str(rows[-1].get("id") or "") if rows else ""
        self._store_reference_board(board)

    def _duplicate_selected_reference_image(self) -> None:
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        if not reference_id:
            return
        from app.painter_reference_board import duplicate_reference_image

        self._push_undo_state("Duplicate reference")
        try:
            board = duplicate_reference_image(self._current_reference_board(), reference_id)
        except ValueError:
            return
        rows = board.to_dict().get("references", [])
        if rows:
            self._painter_reference_selected_id = str(rows[-1].get("id") or "")
        self._store_reference_board(board)

    def _bake_selected_reference_to_sticker(self):
        reference = self._selected_reference_payload()
        if not reference:
            return None
        path = str(reference.get("path") or "")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None
        self._push_undo_state("Bake reference")
        sticker = Sticker(
            png_path=path,
            x_norm=float(reference.get("x_norm", 0.04) or 0.04),
            y_norm=float(reference.get("y_norm", 0.04) or 0.04),
            width_norm=float(reference.get("width_norm", 0.34) or 0.34),
            height_norm=float(reference.get("height_norm", 0.34) or 0.34),
            opacity=float(reference.get("opacity", 0.58) or 0.58) * 100.0,
            rotation_deg=float(reference.get("rotation_deg", 0.0) or 0.0),
            start_ms=int(getattr(self, "_time_ms", 0)),
            end_ms=-1,
            z_index=max((s.z_index for s in self._stickers), default=0) + 1,
        )
        self._stickers.append(sticker)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(sticker)
        self._update_inspector_counts()
        return {
            "schema": "tigerstudio.painter.reference_board.bake.v1",
            "reference_id": str(reference.get("id") or ""),
            "sticker_index": len(self._stickers) - 1,
            "path": path,
        }

    def _select_reference_item(self, item: QListWidgetItem) -> None:
        self._painter_reference_selected_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self._refresh_reference_board_panel()

    def _set_selected_reference_visible(self, visible: bool) -> None:
        if bool(getattr(self, "_painter_reference_syncing", False)):
            return
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        if not reference_id:
            return
        from app.painter_reference_board import update_reference_image

        self._push_undo_state("Set reference visibility")
        try:
            board = update_reference_image(self._current_reference_board(), reference_id, visible=bool(visible))
        except ValueError:
            return
        self._store_reference_board(board)

    def _set_selected_reference_locked(self, locked: bool) -> None:
        if bool(getattr(self, "_painter_reference_syncing", False)):
            return
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        if not reference_id:
            return
        from app.painter_reference_board import update_reference_image

        self._push_undo_state("Lock reference" if locked else "Unlock reference")
        try:
            board = update_reference_image(self._current_reference_board(), reference_id, locked=bool(locked))
        except ValueError:
            return
        self._store_reference_board(board)

    def _on_reference_spin_changed(self, _key: str) -> None:
        if bool(getattr(self, "_painter_reference_syncing", False)):
            return
        self._update_selected_reference_from_controls()

    def _update_selected_reference_from_controls(self) -> None:
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        if not reference_id:
            return
        controls = getattr(self, "_painter_reference_controls", {})
        if not controls:
            return
        selected = self._selected_reference_payload()
        if bool((selected or {}).get("locked", False)):
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("Reference is locked")
            self._sync_reference_control_values(selected)
            return
        from app.painter_reference_board import update_reference_image

        self._push_undo_state("Adjust reference")
        try:
            board = update_reference_image(
                self._current_reference_board(),
                reference_id,
                x_norm=controls["ref_x"].value() / 100.0,
                y_norm=controls["ref_y"].value() / 100.0,
                width_norm=controls["ref_w"].value() / 100.0,
                height_norm=controls["ref_h"].value() / 100.0,
                opacity=controls["ref_opacity"].value() / 100.0,
                rotation_deg=controls["ref_rotation"].value(),
            )
        except ValueError:
            return
        self._store_reference_board(board)

    def _sample_selected_reference_color(self) -> None:
        selected = self._selected_reference_payload()
        if not selected:
            return
        try:
            from app.painter_reference_board import sample_reference_color

            sample = sample_reference_color(str(selected.get("path") or ""))
            rgb = tuple(int(value) for value in sample.get("rgb", [255, 255, 255])[:3])
            self._apply_pen_color(QColor(*rgb), remember=True)
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(f"Reference sample {sample.get('hex', '')}".strip())
        except Exception as exc:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(f"Reference sample failed: {type(exc).__name__}")

    def _extract_selected_reference_palette(self) -> None:
        selected = self._selected_reference_payload()
        if not selected:
            return
        try:
            from app.painter_reference_board import extract_reference_palette

            payload = extract_reference_palette(str(selected.get("path") or ""), max_colors=8)
            colors = []
            for row in payload.get("colors", []) or []:
                rgb = row.get("rgb")
                if isinstance(rgb, list) and len(rgb) >= 3:
                    colors.append((int(rgb[0]), int(rgb[1]), int(rgb[2])))
            if colors:
                self._recent_colors = colors[:RECENT_COLOR_LIMIT]
                self._apply_pen_color(QColor(*colors[0]), remember=False)
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(f"Reference palette {len(colors)} colors")
        except Exception as exc:
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText(f"Reference palette failed: {type(exc).__name__}")

    def _selected_reference_payload(self) -> dict | None:
        reference_id = str(getattr(self, "_painter_reference_selected_id", "") or "")
        rows = self._current_reference_board().to_dict().get("references", [])
        return next((row for row in rows if str(row.get("id") or "") == reference_id), None)

    def _refresh_reference_board_panel(self) -> None:
        if not hasattr(self, "_reference_list"):
            return
        self._painter_reference_syncing = True
        try:
            board = self._current_reference_board()
            rows = list(board.to_dict().get("references", []) or [])
            if rows and not any(row.get("id") == self._painter_reference_selected_id for row in rows):
                self._painter_reference_selected_id = str(rows[0].get("id") or "")
            if not rows:
                self._painter_reference_selected_id = ""
            status = getattr(self, "_reference_status_label", None)
            if status is not None:
                status.setText(f"{len(rows)} pinned")
            lst = getattr(self, "_reference_list", None)
            if lst is not None:
                lst.clear()
                for row in rows:
                    path = Path(str(row.get("path") or ""))
                    item = QListWidgetItem(f"{row.get('name') or path.name}  {int(float(row.get('opacity', 0.58)) * 100)}%")
                    item.setIcon(app_icon("image", size=14, color="#DCE6F7"))
                    item.setData(Qt.ItemDataRole.UserRole, str(row.get("id") or ""))
                    lst.addItem(item)
                    if str(row.get("id") or "") == self._painter_reference_selected_id:
                        item.setSelected(True)
                        lst.setCurrentItem(item)
            selected = self._selected_reference_payload()
            self._sync_reference_control_values(selected)
            preview = getattr(self, "_reference_preview_label", None)
            if preview is not None:
                if selected:
                    pixmap = QPixmap(str(selected.get("path") or ""))
                    if not pixmap.isNull():
                        preview.setPixmap(
                            pixmap.scaled(
                                max(1, preview.width() or 220),
                                max(1, preview.height() or 92),
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation,
                            )
                        )
                    else:
                        preview.setPixmap(QPixmap())
                        preview.setText("Missing reference")
                else:
                    preview.setPixmap(QPixmap())
                    preview.setText("Drop references here")
        finally:
            self._painter_reference_syncing = False
        self._refresh_reference_overlay()
        self._update_inspector_counts()

    def _sync_reference_control_values(self, selected: dict | None) -> None:
        controls = getattr(self, "_painter_reference_controls", {})
        if not controls:
            return
        values = {
            "ref_x": int(round(float((selected or {}).get("x_norm", 0.04)) * 100)),
            "ref_y": int(round(float((selected or {}).get("y_norm", 0.04)) * 100)),
            "ref_w": int(round(float((selected or {}).get("width_norm", 0.34)) * 100)),
            "ref_h": int(round(float((selected or {}).get("height_norm", 0.34)) * 100)),
            "ref_opacity": int(round(float((selected or {}).get("opacity", 0.58)) * 100)),
            "ref_rotation": int(round(float((selected or {}).get("rotation_deg", 0.0)))),
        }
        for key, value in values.items():
            if key in controls:
                controls[key].setValue(value)
                controls[key].setEnabled(bool(selected) and not bool((selected or {}).get("locked", False)))
        if hasattr(self, "reference_visible_btn"):
            self.reference_visible_btn.setChecked(bool((selected or {}).get("visible", True)))
            self.reference_visible_btn.setEnabled(bool(selected))
        if hasattr(self, "reference_lock_btn"):
            self.reference_lock_btn.setChecked(bool((selected or {}).get("locked", False)))
            self.reference_lock_btn.setEnabled(bool(selected))
        for attr in ("reference_duplicate_btn", "reference_delete_btn", "reference_bake_btn", "reference_sample_btn", "reference_palette_btn"):
            btn = getattr(self, attr, None)
            if btn is not None:
                btn.setEnabled(bool(selected))

    def _refresh_reference_overlay(self) -> None:
        host = getattr(self, "_canvas_host", None)
        canvas = getattr(self, "canvas", None)
        if host is None or canvas is None:
            return
        labels = getattr(self, "_painter_reference_labels", {})
        rows = list(self._current_reference_board().to_dict().get("references", []) or [])
        active_ids: set[str] = set()
        overlay_enabled = bool(getattr(self, "reference_overlay_btn", None) and self.reference_overlay_btn.isChecked())
        canvas_rect = canvas.geometry()
        cw = max(1, canvas_rect.width())
        ch = max(1, canvas_rect.height())
        stable_size = canvas.stable_render_size(cw, ch)
        stable_scale_x = float(stable_size.width()) / cw
        stable_scale_y = float(stable_size.height()) / ch
        for row in rows:
            reference_id = str(row.get("id") or "")
            if not reference_id:
                continue
            active_ids.add(reference_id)
            label = labels.get(reference_id)
            if label is None:
                label = QLabel(host)
                label.setObjectName("PaintReferenceCanvasOverlay")
                label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setStyleSheet("background: transparent; border: none;")
                labels[reference_id] = label
            if not overlay_enabled or not bool(row.get("visible", True)):
                label.hide()
                continue
            source = QPixmap(str(row.get("path") or ""))
            if source.isNull():
                label.hide()
                continue
            x = int(canvas_rect.x() + float(row.get("x_norm", 0.04) or 0.04) * cw)
            y = int(canvas_rect.y() + float(row.get("y_norm", 0.04) or 0.04) * ch)
            w = int(float(row.get("width_norm", 0.34) or 0.34) * cw)
            h = int(float(row.get("height_norm", 0.34) or 0.34) * ch)
            w = max(16, min(w, canvas_rect.right() - x + 1))
            h = max(16, min(h, canvas_rect.bottom() - y + 1))
            label.setGeometry(x, y, w, h)
            label.setScaledContents(True)
            label.setPixmap(
                self._reference_pixmap_with_opacity(
                    source,
                    max(8, int(round(w * stable_scale_x))),
                    max(8, int(round(h * stable_scale_y))),
                    float(row.get("opacity", 0.58) or 0.58),
                    float(row.get("rotation_deg", 0.0) or 0.0),
                )
            )
            label.show()
            label.raise_()
        for reference_id, label in list(labels.items()):
            if reference_id not in active_ids:
                label.deleteLater()
                labels.pop(reference_id, None)
        self._painter_reference_labels = labels
        canvas.raise_()

    @staticmethod
    def _reference_pixmap_with_opacity(
        source: QPixmap,
        width: int,
        height: int,
        opacity: float,
        rotation_deg: float = 0.0,
    ) -> QPixmap:
        target = QPixmap(max(1, int(width)), max(1, int(height)))
        target.fill(Qt.GlobalColor.transparent)
        scaled = source.scaled(
            max(1, int(width)),
            max(1, int(height)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter = QPainter(target)
        try:
            painter.setOpacity(max(0.05, min(1.0, float(opacity))))
            cx = target.width() / 2.0
            cy = target.height() / 2.0
            painter.translate(cx, cy)
            painter.rotate(float(rotation_deg or 0.0))
            painter.translate(-cx, -cy)
            painter.drawPixmap((target.width() - scaled.width()) // 2, (target.height() - scaled.height()) // 2, scaled)
        finally:
            painter.end()
        return target

    def _focus_reference_board_panel(self) -> None:
        panel = getattr(self, "_paint_reference_panel", None)
        scroll = getattr(self, "_paint_inspector_controls_scroll", None)
        if panel is not None and scroll is not None:
            panel.show()
            scroll.ensureWidgetVisible(panel, 0, 12)
        self._refresh_reference_board_panel()

    def _build_3d_blockout_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PaintBlockoutPanel")
        panel.setMinimumHeight(242)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("3D BLOCKOUT")
        title.setObjectName("PaintSectionTitle")
        self._blockout_status_label = QLabel("canvas editing")
        self._blockout_status_label.setObjectName("PaintBlockoutStatus")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self._blockout_status_label)
        layout.addLayout(header)

        primitive_title = QLabel("Place Shapes")
        primitive_title.setObjectName("PaintColorSectionLabel")
        layout.addWidget(primitive_title)
        primitive_grid = QGridLayout()
        primitive_grid.setContentsMargins(0, 0, 0, 0)
        primitive_grid.setHorizontalSpacing(3)
        primitive_grid.setVerticalSpacing(3)
        self._blockout_primitive_buttons: dict[str, QPushButton] = {}
        for index, (label, kind) in enumerate(
            (
                ("Cube", "box"),
                ("Sphere", "sphere"),
                ("Cylinder", "cylinder"),
                ("Cone", "cone"),
                ("Plane", "plane"),
                ("Arch", "arch"),
            )
        ):
            button = QPushButton(label)
            button.setObjectName("PaintCustomColor")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(f"Place {label} on the Painter canvas")
            button.setProperty("blockoutShapeKind", kind)
            button.installEventFilter(self)
            button.clicked.connect(
                lambda _checked=False, value=kind: self._add_3d_blockout_primitive(value)
            )
            primitive_grid.addWidget(button, index // 3, index % 3)
            self._blockout_primitive_buttons[kind] = button
        self.blockout_add_box_btn = self._blockout_primitive_buttons["box"]
        self.blockout_add_arch_btn = self._blockout_primitive_buttons["arch"]
        layout.addLayout(primitive_grid)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        self.blockout_duplicate_btn = QPushButton("Dup")
        self.blockout_ground_btn = QPushButton("Ground")
        self.blockout_delete_btn = QPushButton("Del")
        self.blockout_bake_btn = QPushButton("Bake")
        self.blockout_overlay_btn = QPushButton("Canvas")
        self.blockout_overlay_btn.setCheckable(True)
        self.blockout_overlay_btn.setChecked(True)
        self.blockout_overlay_btn.setToolTip("Show or hide the 3D guide on the Painter canvas")
        self.blockout_snap_btn = QPushButton("Snap")
        self.blockout_snap_btn.setCheckable(True)
        self.blockout_wire_btn = QPushButton("Wire")
        self.blockout_wire_btn.setCheckable(True)
        self.blockout_wire_btn.setChecked(True)
        self.blockout_grid_btn = QPushButton("Grid")
        self.blockout_grid_btn.setCheckable(True)
        self.blockout_grid_btn.setChecked(True)
        self.blockout_floor_btn = QPushButton("Floor")
        self.blockout_floor_btn.setCheckable(True)
        self.blockout_floor_btn.setChecked(True)
        self.blockout_floor_btn.setToolTip("Toggle the world-aligned checker ground")
        for btn, handler in (
            (self.blockout_duplicate_btn, self._duplicate_selected_3d_blockout_primitive),
            (self.blockout_ground_btn, self._align_selected_3d_blockout_to_ground),
            (self.blockout_delete_btn, self._delete_selected_3d_blockout_primitive),
            (self.blockout_bake_btn, self._bake_3d_blockout_to_layer),
        ):
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            action_row.addWidget(btn)
        for btn in (
            self.blockout_overlay_btn,
            self.blockout_snap_btn,
            self.blockout_wire_btn,
            self.blockout_grid_btn,
            self.blockout_floor_btn,
        ):
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_row.addWidget(btn)
        self.blockout_overlay_btn.toggled.connect(lambda _checked=False: self._refresh_3d_blockout_overlay())
        self.blockout_snap_btn.toggled.connect(lambda checked=False: self._set_3d_blockout_snap(bool(checked)))
        self.blockout_wire_btn.toggled.connect(lambda checked=False: self._set_3d_blockout_scene_flag("show_wireframe", bool(checked)))
        self.blockout_grid_btn.toggled.connect(lambda checked=False: self._set_3d_blockout_scene_flag("show_grid", bool(checked)))
        self.blockout_floor_btn.toggled.connect(lambda checked=False: self._set_3d_blockout_scene_flag("show_floor", bool(checked)))
        layout.addLayout(action_row)

        material_row = QHBoxLayout()
        material_row.setContentsMargins(0, 0, 0, 0)
        material_row.setSpacing(4)
        self.blockout_lit_btn = QPushButton("Lit")
        self.blockout_lit_btn.setCheckable(True)
        self.blockout_lit_btn.setChecked(True)
        self.blockout_lit_btn.setToolTip("Toggle lit white material preview")
        self.blockout_shadow_btn = QPushButton("Shadow")
        self.blockout_shadow_btn.setCheckable(True)
        self.blockout_shadow_btn.setChecked(True)
        self.blockout_shadow_btn.setToolTip("Toggle directional-light ground shadows")
        self.blockout_fog_btn = QPushButton("Fog")
        self.blockout_fog_btn.setCheckable(True)
        self.blockout_fog_btn.setChecked(False)
        self.blockout_fog_btn.setToolTip("Fade distant geometry into the gray viewport")
        self.blockout_depth_btn = QPushButton("Depth")
        self.blockout_depth_btn.setCheckable(True)
        self.blockout_depth_btn.setChecked(False)
        self.blockout_depth_btn.setToolTip("Show a non-destructive grayscale camera-depth diagnostic")
        for button in (
            self.blockout_lit_btn,
            self.blockout_shadow_btn,
            self.blockout_fog_btn,
            self.blockout_depth_btn,
        ):
            button.setObjectName("PaintCustomColor")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            material_row.addWidget(button)
        self.blockout_lit_btn.toggled.connect(
            lambda checked=False: self._set_3d_blockout_scene_flag("material_lit", bool(checked))
        )
        self.blockout_shadow_btn.toggled.connect(
            lambda checked=False: self._set_3d_blockout_scene_flag("show_shadows", bool(checked))
        )
        self.blockout_fog_btn.toggled.connect(
            lambda checked=False: self._set_3d_blockout_scene_flag("show_fog", bool(checked))
        )
        self.blockout_depth_btn.toggled.connect(
            lambda checked=False: self._set_3d_blockout_scene_flag("show_depth", bool(checked))
        )
        light_specs = (
            ("Light H", "light_yaw", -180, 180, 45, "째"),
            ("Light V", "light_pitch", 5, 85, 45, "째"),
        )
        light_grid = QGridLayout()
        light_grid.setContentsMargins(0, 0, 0, 0)
        light_grid.setHorizontalSpacing(4)
        for index, spec in enumerate(light_specs):
            self._add_3d_blockout_spin(light_grid, 0, index, *spec)
        material_row.addLayout(light_grid, stretch=1)
        layout.addLayout(material_row)

        self._blockout_list = QListWidget()
        self._blockout_list.setObjectName("PaintBlockoutList")
        self._blockout_list.setMaximumHeight(86)
        self._blockout_list.itemClicked.connect(self._select_3d_blockout_item)
        layout.addWidget(self._blockout_list)

        transform_title = QLabel("Transform")
        transform_title.setObjectName("PaintColorSectionLabel")
        layout.addWidget(transform_title)
        transform_grid = QGridLayout()
        transform_grid.setContentsMargins(0, 0, 0, 0)
        transform_grid.setHorizontalSpacing(6)
        transform_grid.setVerticalSpacing(4)
        transform_specs = (
            ("X", "x", -500, 500, 0, ""),
            ("Y", "y", -500, 500, 0, ""),
            ("Z", "z", -500, 500, 0, ""),
            ("W", "sx", 10, 800, 100, "%"),
            ("H", "sy", 10, 800, 100, "%"),
            ("D", "sz", 10, 800, 100, "%"),
            ("RX", "rx", -180, 180, 0, "°"),
            ("RY", "ry", -180, 180, 0, "°"),
            ("RZ", "rz", -180, 180, 0, "°"),
        )
        for index, spec in enumerate(transform_specs):
            row, col = divmod(index, 3)
            self._add_3d_blockout_spin(transform_grid, row, col, *spec)
        layout.addLayout(transform_grid)

        camera_title = QLabel("Camera / FOV")
        camera_title.setObjectName("PaintColorSectionLabel")
        layout.addWidget(camera_title)
        camera_grid = QGridLayout()
        camera_grid.setContentsMargins(0, 0, 0, 0)
        camera_grid.setHorizontalSpacing(6)
        camera_grid.setVerticalSpacing(4)
        camera_specs = (
            ("Yaw", "cam_yaw", -180, 180, 35, "°"),
            ("Pitch", "cam_pitch", -85, 85, -18, "°"),
            ("Dist", "cam_distance", 25, 3000, 850, ""),
            ("FOV", "cam_fov", 15, 90, 42, "°"),
            ("Pan X", "cam_tx", -500, 500, 0, ""),
            ("Pan Z", "cam_tz", -500, 500, 80, ""),
        )
        for index, spec in enumerate(camera_specs):
            row, col = divmod(index, 2)
            self._add_3d_blockout_spin(camera_grid, row, col, *spec)
        layout.addLayout(camera_grid)

        camera_preset_row = QHBoxLayout()
        camera_preset_row.setContentsMargins(0, 0, 0, 0)
        camera_preset_row.setSpacing(4)
        for label, preset in (("Front", "front"), ("Side", "side"), ("Top", "top"), ("Persp", "perspective")):
            btn = QPushButton(label)
            btn.setObjectName("PaintCustomColor")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, p=preset: self._apply_3d_blockout_camera_preset(p))
            camera_preset_row.addWidget(btn)
        layout.addLayout(camera_preset_row)
        self._ensure_canvas_3d_shape_palette()
        QTimer.singleShot(0, self._refresh_3d_blockout_panel)
        return panel

    def _ensure_canvas_3d_shape_palette(self) -> QFrame | None:
        existing = getattr(self, "_blockout_canvas_shape_palette", None)
        if existing is not None:
            return existing
        host = getattr(self, "_canvas_host", None)
        if host is None:
            return None
        palette = QFrame(host)
        palette.setObjectName("PaintBlockoutPanel")
        palette.setFixedWidth(184)
        palette_layout = QVBoxLayout(palette)
        palette_layout.setContentsMargins(8, 7, 8, 8)
        palette_layout.setSpacing(5)
        title = QLabel("PLACE ACTORS")
        title.setObjectName("PaintSectionTitle")
        palette_layout.addWidget(title)
        subtitle = QLabel("Shapes")
        subtitle.setObjectName("PaintColorSectionLabel")
        palette_layout.addWidget(subtitle)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        self._blockout_canvas_shape_buttons: dict[str, QPushButton] = {}
        for index, (label, kind) in enumerate(
            (
                ("Cube", "box"),
                ("Sphere", "sphere"),
                ("Cylinder", "cylinder"),
                ("Cone", "cone"),
                ("Plane", "plane"),
                ("Arch", "arch"),
            )
        ):
            button = QPushButton(label)
            button.setObjectName("PaintCustomColor")
            button.setCursor(Qt.CursorShape.OpenHandCursor)
            button.setToolTip(f"Click or drag {label} onto the 3D canvas")
            button.setProperty("blockoutShapeKind", kind)
            button.installEventFilter(self)
            button.clicked.connect(
                lambda _checked=False, value=kind: self._add_3d_blockout_primitive(value)
            )
            grid.addWidget(button, index // 2, index % 2)
            self._blockout_canvas_shape_buttons[kind] = button
        palette_layout.addLayout(grid)
        help_text = QLabel("Drag to place on ground")
        help_text.setObjectName("PaintMeta")
        palette_layout.addWidget(help_text)
        palette.adjustSize()
        palette.move(10, 10)
        palette.hide()
        self._blockout_canvas_shape_palette = palette
        return palette

    def _add_3d_blockout_spin(
        self,
        layout: QGridLayout,
        row: int,
        column: int,
        label_text: str,
        key: str,
        minimum: int,
        maximum: int,
        value: int,
        suffix: str,
    ) -> None:
        box = QSpinBox()
        box.setRange(int(minimum), int(maximum))
        box.setValue(int(value))
        box.setObjectName("PaintLayerBlendCombo")
        box.setToolTip(label_text)
        box.setMinimumWidth(64)
        if suffix:
            box.setSuffix(suffix)
        box.valueChanged.connect(lambda new_value, k=key: self._on_3d_blockout_spin_changed(k, int(new_value)))
        self._painter_3d_blockout_controls[key] = box
        label = QLabel(label_text)
        label.setObjectName("PaintMeta")
        cell = QHBoxLayout()
        cell.setContentsMargins(0, 0, 0, 0)
        cell.setSpacing(3)
        cell.addWidget(label)
        cell.addWidget(box, stretch=1)
        host = QWidget()
        host.setLayout(cell)
        layout.addWidget(host, row, column)

    def _current_3d_blockout_scene(self):
        from app.painter_3d_blockout import blockout_scene_from_dict

        return blockout_scene_from_dict(getattr(self, "_painter_3d_blockout_scene", None))

    def _store_3d_blockout_scene(self, scene) -> None:
        self._painter_3d_blockout_scene = scene.to_dict()
        self._painter_3d_blockout_flat_cache = None
        self._refresh_3d_blockout_panel()

    def _add_3d_blockout_primitive(
        self,
        kind: str,
        *,
        world_position: tuple[float, float, float] | None = None,
    ) -> None:
        from app.painter_3d_blockout import add_blockout_primitive, align_blockout_primitive_to_ground

        self._set_canvas_workspace_mode("3d_place", focus_panel=False)
        self._push_undo_state(f"Add {kind.title()} blockout")
        self._ensure_3d_blockout_layer()
        params: dict[str, object] = {
            "kind": kind,
            "name": f"{kind.title()} {self._current_3d_blockout_scene().next_index}",
        }
        if world_position is not None:
            params.update(
                {
                    "x": float(world_position[0]),
                    "y": float(world_position[1]),
                    "z": float(world_position[2]),
                }
            )
        scene = add_blockout_primitive(self._current_3d_blockout_scene(), **params)
        rows = scene.to_dict().get("primitives", [])
        if rows:
            self._painter_3d_blockout_selected_id = str(rows[-1].get("id") or "")
            scene = align_blockout_primitive_to_ground(
                scene,
                self._painter_3d_blockout_selected_id,
            )
        self._store_3d_blockout_scene(scene)

    def _ensure_3d_blockout_layer(self) -> PaintLayer:
        layer_id = "paint-layer-3d-blockout"
        existing = self._paint_layer_by_id(layer_id)
        if existing is not None:
            self._selected_layer_id = layer_id
            self._update_layer_controls()
            return existing
        layer = PaintLayer(
            layer_id=layer_id,
            name="3D Blockout",
            visible=True,
            opacity=100,
            locked=False,
        )
        self._paint_layers.insert(0, layer)
        self._selected_layer_id = layer_id
        self._sync_canvas_layer_view()
        self._update_layer_controls()
        return layer

    def _3d_blockout_layer(self) -> PaintLayer | None:
        return self._paint_layer_by_id("paint-layer-3d-blockout")

    def _delete_selected_3d_blockout_primitive(self) -> None:
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        if not primitive_id:
            return
        from app.painter_3d_blockout import delete_blockout_primitive

        self._push_undo_state("Delete 3D blockout")
        try:
            scene = delete_blockout_primitive(self._current_3d_blockout_scene(), primitive_id)
        except ValueError:
            return
        rows = scene.to_dict().get("primitives", [])
        self._painter_3d_blockout_selected_id = str(rows[-1].get("id") or "") if rows else ""
        self._store_3d_blockout_scene(scene)

    def _duplicate_selected_3d_blockout_primitive(self) -> None:
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        if not primitive_id:
            return
        from app.painter_3d_blockout import duplicate_blockout_primitive

        self._push_undo_state("Duplicate 3D blockout")
        try:
            scene = duplicate_blockout_primitive(self._current_3d_blockout_scene(), primitive_id)
        except ValueError:
            return
        rows = scene.to_dict().get("primitives", [])
        if rows:
            self._painter_3d_blockout_selected_id = str(rows[-1].get("id") or "")
        self._store_3d_blockout_scene(scene)

    def _align_selected_3d_blockout_to_ground(self) -> None:
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        if not primitive_id:
            return
        from app.painter_3d_blockout import align_blockout_primitive_to_ground

        self._push_undo_state("Ground 3D blockout")
        try:
            scene = align_blockout_primitive_to_ground(self._current_3d_blockout_scene(), primitive_id)
        except ValueError:
            return
        self._store_3d_blockout_scene(scene)

    def _bake_3d_blockout_to_layer(self):
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return None
        from app.painter_3d_blockout import project_blockout_scene

        scene = self._current_3d_blockout_scene()
        projection = project_blockout_scene(scene, max(1, canvas.width()), max(1, canvas.height()))
        edges = list(projection.get("edges", []) or [])
        if not edges:
            return None
        self._push_undo_state("Bake 3D blockout")
        self._paint_layer_serial += 1
        layer = PaintLayer(
            layer_id=f"paint-layer-{self._paint_layer_serial}",
            name="3D Blockout Guide",
            opacity=88,
        )
        self._paint_layers.append(layer)
        self._active_paint_layer_id = layer.layer_id
        self._selected_layer_id = layer.layer_id
        viewport = projection.get("viewport", {}) if isinstance(projection.get("viewport"), dict) else {}
        width = max(1, int(viewport.get("width") or canvas.width() or 1))
        height = max(1, int(viewport.get("height") or canvas.height() or 1))
        baked: list[Stroke] = []
        for edge in edges:
            a = edge.get("a")
            b = edge.get("b")
            if not isinstance(a, (list, tuple)) or not isinstance(b, (list, tuple)) or len(a) < 2 or len(b) < 2:
                continue
            ax = max(0.0, min(1.0, float(a[0]) / width))
            ay = max(0.0, min(1.0, float(a[1]) / height))
            bx = max(0.0, min(1.0, float(b[0]) / width))
            by = max(0.0, min(1.0, float(b[1]) / height))
            if abs(ax - bx) + abs(ay - by) < 0.0005:
                continue
            baked.append(
                Stroke(
                    points=[(ax, ay), (bx, by)],
                    color=(236, 242, 255),
                    opacity=215,
                    width_px=2.0,
                    brush_style="round",
                    brush_hardness=100,
                    brush_spacing=20,
                    layer_id=layer.layer_id,
                    source_tool="3d_blockout",
                    start_ms=int(getattr(self, "_time_ms", 0)),
                    end_ms=None,
                )
            )
        if not baked:
            self._paint_layers.pop()
            self._active_paint_layer_id = self._paint_layers[-1].layer_id if self._paint_layers else "paint-layer-1"
            self._selected_layer_id = self._active_paint_layer_id
            return None
        strokes = canvas.embedded_strokes()
        strokes.extend(baked)
        canvas.set_strokes_snapshot(strokes)
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        self._show_painter_tab("layers")
        return {
            "schema": "tigerstudio.painter.3d_blockout.bake.v1",
            "layer_id": layer.layer_id,
            "layer_name": layer.name,
            "stroke_count": len(baked),
            "source_edge_count": len(edges),
            "scene": scene.to_dict(),
        }

    def _select_3d_blockout_item(self, item: QListWidgetItem) -> None:
        self._painter_3d_blockout_selected_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        self._refresh_3d_blockout_panel()

    def _set_3d_blockout_scene_flag(self, key: str, enabled: bool) -> None:
        if bool(getattr(self, "_painter_3d_blockout_syncing", False)):
            return
        from app.painter_3d_blockout import BlockoutScene

        scene = self._current_3d_blockout_scene()
        self._push_undo_state("Set 3D blockout view")
        updated = BlockoutScene(
            camera=scene.camera,
            primitives=scene.primitives,
            grid_size=scene.grid_size,
            show_grid=bool(enabled) if key == "show_grid" else scene.show_grid,
            show_wireframe=bool(enabled) if key == "show_wireframe" else scene.show_wireframe,
            show_floor=bool(enabled) if key == "show_floor" else scene.show_floor,
            material_lit=bool(enabled) if key == "material_lit" else scene.material_lit,
            show_shadows=bool(enabled) if key == "show_shadows" else scene.show_shadows,
            show_fog=bool(enabled) if key == "show_fog" else scene.show_fog,
            show_depth=bool(enabled) if key == "show_depth" else scene.show_depth,
            light_yaw_degrees=scene.light_yaw_degrees,
            light_pitch_degrees=scene.light_pitch_degrees,
            snap_to_grid=scene.snap_to_grid,
            next_index=scene.next_index,
        )
        self._store_3d_blockout_scene(updated)

    def _set_3d_blockout_snap(self, enabled: bool) -> None:
        if bool(getattr(self, "_painter_3d_blockout_syncing", False)):
            return
        from app.painter_3d_blockout import set_blockout_snap

        self._push_undo_state("Set 3D blockout snap")
        self._store_3d_blockout_scene(set_blockout_snap(self._current_3d_blockout_scene(), bool(enabled)))

    def _apply_3d_blockout_camera_preset(self, preset: str) -> None:
        from app.painter_3d_blockout import apply_blockout_camera_preset

        self._push_undo_state("Set 3D blockout camera preset")
        self._store_3d_blockout_scene(apply_blockout_camera_preset(self._current_3d_blockout_scene(), preset))

    def _on_3d_blockout_spin_changed(self, key: str, value: int) -> None:
        if bool(getattr(self, "_painter_3d_blockout_syncing", False)):
            return
        if key.startswith("cam_"):
            self._update_3d_blockout_camera_from_controls()
        elif key.startswith("light_"):
            self._update_3d_blockout_light_from_controls()
        else:
            self._update_selected_3d_blockout_transform()

    def _update_3d_blockout_light_from_controls(self) -> None:
        from dataclasses import replace

        controls = getattr(self, "_painter_3d_blockout_controls", {})
        if "light_yaw" not in controls or "light_pitch" not in controls:
            return
        self._push_undo_state("Adjust 3D blockout light")
        scene = self._current_3d_blockout_scene()
        self._store_3d_blockout_scene(
            replace(
                scene,
                light_yaw_degrees=float(controls["light_yaw"].value()),
                light_pitch_degrees=float(controls["light_pitch"].value()),
            ).normalized()
        )

    def _update_selected_3d_blockout_transform(self) -> None:
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        if not primitive_id:
            return
        from app.painter_3d_blockout import update_blockout_primitive

        controls = getattr(self, "_painter_3d_blockout_controls", {})
        params = {
            "x": controls["x"].value() / 100.0,
            "y": controls["y"].value() / 100.0,
            "z": controls["z"].value() / 100.0,
            "sx": controls["sx"].value() / 100.0,
            "sy": controls["sy"].value() / 100.0,
            "sz": controls["sz"].value() / 100.0,
            "rx": controls["rx"].value(),
            "ry": controls["ry"].value(),
            "rz": controls["rz"].value(),
        }
        self._push_undo_state("Transform 3D blockout")
        try:
            current_scene = self._current_3d_blockout_scene()
            scene = update_blockout_primitive(current_scene, primitive_id, **params)
            if current_scene.snap_to_grid:
                from app.painter_3d_blockout import snap_blockout_primitive_to_grid

                scene = snap_blockout_primitive_to_grid(scene, primitive_id)
        except ValueError:
            return
        self._store_3d_blockout_scene(scene)

    def _update_3d_blockout_camera_from_controls(self) -> None:
        from app.painter_3d_blockout import update_blockout_camera

        controls = getattr(self, "_painter_3d_blockout_controls", {})
        self._push_undo_state("Adjust 3D blockout camera")
        scene = update_blockout_camera(
            self._current_3d_blockout_scene(),
            yaw_degrees=controls["cam_yaw"].value(),
            pitch_degrees=controls["cam_pitch"].value(),
            distance=controls["cam_distance"].value() / 100.0,
            fov_degrees=controls["cam_fov"].value(),
            target_x=controls["cam_tx"].value() / 100.0,
            target_z=controls["cam_tz"].value() / 100.0,
        )
        self._store_3d_blockout_scene(scene)

    def _refresh_3d_blockout_panel(self) -> None:
        if not hasattr(self, "_blockout_list"):
            return
        self._painter_3d_blockout_syncing = True
        try:
            scene = self._current_3d_blockout_scene()
            payload = scene.to_dict()
            rows = list(payload.get("primitives", []) or [])
            if rows and not any(row.get("id") == self._painter_3d_blockout_selected_id for row in rows):
                self._painter_3d_blockout_selected_id = str(rows[0].get("id") or "")
            if not rows:
                self._painter_3d_blockout_selected_id = ""
            status = getattr(self, "_blockout_status_label", None)
            if status is not None:
                status.setText(f"{len(rows)} obj | canvas")
            lst = getattr(self, "_blockout_list", None)
            if lst is not None:
                lst.clear()
                for row in rows:
                    item = QListWidgetItem(f"{row.get('name') or row.get('kind')}  [{row.get('kind')}]")
                    item.setData(Qt.ItemDataRole.UserRole, str(row.get("id") or ""))
                    lst.addItem(item)
                    if str(row.get("id") or "") == self._painter_3d_blockout_selected_id:
                        item.setSelected(True)
                        lst.setCurrentItem(item)
            selected = next((row for row in rows if str(row.get("id") or "") == self._painter_3d_blockout_selected_id), None)
            self._sync_3d_blockout_control_values(payload, selected)
        finally:
            self._painter_3d_blockout_syncing = False
        self._refresh_3d_blockout_overlay()

    def _sync_3d_blockout_control_values(self, scene_payload: dict, selected: dict | None) -> None:
        controls = getattr(self, "_painter_3d_blockout_controls", {})
        if not controls:
            return
        if selected is not None:
            pos = list(selected.get("position") or [0.0, 0.0, 0.0])
            rot = list(selected.get("rotation") or [0.0, 0.0, 0.0])
            scale = list(selected.get("scale") or [1.0, 1.0, 1.0])
            values = {
                "x": int(round(float(pos[0]) * 100)),
                "y": int(round(float(pos[1]) * 100)),
                "z": int(round(float(pos[2]) * 100)),
                "rx": int(round(float(rot[0]))),
                "ry": int(round(float(rot[1]))),
                "rz": int(round(float(rot[2]))),
                "sx": int(round(float(scale[0]) * 100)),
                "sy": int(round(float(scale[1]) * 100)),
                "sz": int(round(float(scale[2]) * 100)),
            }
            for key, value in values.items():
                if key in controls:
                    controls[key].setValue(value)
        camera = dict(scene_payload.get("camera") or {})
        target = list(camera.get("target") or [0.0, 0.0, 0.8])
        camera_values = {
            "cam_yaw": int(round(float(camera.get("yaw_degrees", 35.0)))),
            "cam_pitch": int(round(float(camera.get("pitch_degrees", -18.0)))),
            "cam_distance": int(round(float(camera.get("distance", 8.5)) * 100)),
            "cam_fov": int(round(float(camera.get("fov_degrees", 42.0)))),
            "cam_tx": int(round(float(target[0]) * 100)),
            "cam_tz": int(round(float(target[2]) * 100)),
            "light_yaw": int(round(float(scene_payload.get("light_yaw_degrees", 45.0)))),
            "light_pitch": int(round(float(scene_payload.get("light_pitch_degrees", 45.0)))),
        }
        for key, value in camera_values.items():
            if key in controls:
                controls[key].setValue(value)
        if hasattr(self, "blockout_wire_btn"):
            self.blockout_wire_btn.setChecked(bool(scene_payload.get("show_wireframe", True)))
        if hasattr(self, "blockout_grid_btn"):
            self.blockout_grid_btn.setChecked(bool(scene_payload.get("show_grid", True)))
        if hasattr(self, "blockout_floor_btn"):
            self.blockout_floor_btn.setChecked(bool(scene_payload.get("show_floor", True)))
        if hasattr(self, "blockout_snap_btn"):
            self.blockout_snap_btn.setChecked(bool(scene_payload.get("snap_to_grid", False)))
        if hasattr(self, "blockout_lit_btn"):
            self.blockout_lit_btn.setChecked(bool(scene_payload.get("material_lit", True)))
        if hasattr(self, "blockout_shadow_btn"):
            self.blockout_shadow_btn.setChecked(bool(scene_payload.get("show_shadows", True)))
        if hasattr(self, "blockout_fog_btn"):
            self.blockout_fog_btn.setChecked(bool(scene_payload.get("show_fog", False)))
        if hasattr(self, "blockout_depth_btn"):
            self.blockout_depth_btn.setChecked(bool(scene_payload.get("show_depth", False)))

    def _refresh_3d_blockout_overlay(self) -> None:
        label = getattr(self, "_blockout_overlay_label", None)
        canvas = getattr(self, "canvas", None)
        if label is None or canvas is None:
            return
        scene = self._current_3d_blockout_scene()
        payload = scene.to_dict()
        placement_mode = str(getattr(self, "_canvas_workspace_mode", "paint")) == "3d_place"
        blockout_layer = self._3d_blockout_layer()
        if blockout_layer is not None and not blockout_layer.visible:
            label.hide()
            return
        if not bool(getattr(self, "blockout_overlay_btn", None) and self.blockout_overlay_btn.isChecked()):
            label.hide()
            return
        if int(payload.get("primitive_count", 0) or 0) <= 0 and not placement_mode:
            label.hide()
            return
        size = canvas.size()
        if size.width() <= 0 or size.height() <= 0:
            label.hide()
            return
        label.setGeometry(canvas.geometry())
        label.setScaledContents(True)
        render_size = canvas.stable_render_size(size.width(), size.height())
        content_opacity = (
            max(0.0, min(1.0, blockout_layer.opacity / 100.0))
            if blockout_layer is not None
            else 1.0
        )
        cached = getattr(self, "_painter_3d_blockout_flat_cache", None)
        if (
            not placement_mode
            and isinstance(cached, QPixmap)
            and cached.size() == render_size
        ):
            pixmap = cached
        else:
            pixmap = self._render_3d_blockout_pixmap(
                scene,
                render_size.width(),
                render_size.height(),
                include_gizmo=placement_mode,
                viewport_background=placement_mode,
                content_opacity=content_opacity,
            )
            if not placement_mode:
                self._painter_3d_blockout_flat_cache = pixmap
        label.setPixmap(pixmap)
        label.show()
        if placement_mode:
            canvas.raise_()
            label.raise_()
        else:
            label.raise_()
            canvas.raise_()
        palette = getattr(self, "_blockout_canvas_shape_palette", None)
        if palette is not None and placement_mode:
            palette.raise_()

    def _render_3d_blockout_pixmap(
        self,
        scene,
        width: int,
        height: int,
        *,
        include_gizmo: bool,
        viewport_background: bool = False,
        content_opacity: float = 1.0,
    ) -> QPixmap:
        target_w = max(1, int(width))
        target_h = max(1, int(height))
        try:
            from app.painter_opengl import PAINTER_OPENGL_RENDERER_ID, render_blockout_scene_opengl_qimage

            image = render_blockout_scene_opengl_qimage(scene, target_w, target_h)
            self._painter_3d_blockout_renderer_status = {
                "renderer": PAINTER_OPENGL_RENDERER_ID,
                "active": "opengl",
                "fallback": False,
                "size": [target_w, target_h],
                "surface": "offscreen_fbo",
            }
        except Exception as exc:
            from app.painter_3d_blockout import render_blockout_scene_qimage

            image = render_blockout_scene_qimage(scene, target_w, target_h)
            self._painter_3d_blockout_renderer_status = {
                "renderer": "painter_blockout_qpainter_v1",
                "active": "qpainter",
                "fallback": True,
                "size": [target_w, target_h],
                "fallback_from": "opengl",
                "reason": f"{type(exc).__name__}: {exc}",
            }
        opacity = max(0.0, min(1.0, float(content_opacity)))
        if opacity < 0.999:
            faded = QImage(target_w, target_h, QImage.Format.Format_ARGB32_Premultiplied)
            faded.fill(QColor(0, 0, 0, 0))
            faded_painter = QPainter(faded)
            try:
                faded_painter.setOpacity(opacity)
                faded_painter.drawImage(0, 0, image)
            finally:
                faded_painter.end()
            image = faded
        if viewport_background:
            pixmap = QPixmap(target_w, target_h)
            pixmap.fill(QColor("#3A3C3F"))
            background_painter = QPainter(pixmap)
            try:
                background_painter.drawImage(0, 0, image)
            finally:
                background_painter.end()
        else:
            pixmap = QPixmap.fromImage(image)
        if not include_gizmo:
            return pixmap
        bounds = self._selected_3d_blockout_bounds(width, height)
        if bounds is None:
            return pixmap
        painter = QPainter(pixmap)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            geometry = self._blockout_gizmo_geometry(bounds)
            center = geometry["center"]
            painter.setPen(QPen(QColor(255, 255, 255, 210), 1.4, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bounds)
            mode = str(getattr(self, "_blockout_transform_mode", "select") or "select")
            axes = geometry["axes"]
            axis_colors = {
                "x": QColor("#F04444"),
                "y": QColor("#45C96B"),
                "z": QColor("#438BFF"),
            }
            active_axis = str(getattr(self, "_blockout_active_axis", "") or "")
            if mode in {"move", "scale"}:
                for axis in ("x", "y", "z"):
                    endpoint = axes[axis]
                    color = axis_colors[axis]
                    active = axis == active_axis
                    display_color = color.lighter(155) if active else color
                    painter.setPen(QPen(display_color, 4.2 if active else 2.5))
                    painter.setBrush(display_color)
                    painter.drawLine(center, endpoint)
                    if mode == "scale":
                        painter.drawRect(QRectF(endpoint.x() - 4.5, endpoint.y() - 4.5, 9.0, 9.0))
                    else:
                        direction = endpoint - center
                        length = max(1.0, math.hypot(direction.x(), direction.y()))
                        ux, uy = direction.x() / length, direction.y() / length
                        side_x, side_y = -uy, ux
                        painter.drawPolygon(
                            QPolygonF(
                                [
                                    endpoint,
                                    QPointF(endpoint.x() - ux * 11.0 + side_x * 5.0, endpoint.y() - uy * 11.0 + side_y * 5.0),
                                    QPointF(endpoint.x() - ux * 11.0 - side_x * 5.0, endpoint.y() - uy * 11.0 - side_y * 5.0),
                                ]
                            )
                        )
            elif mode == "rotate":
                painter.setBrush(Qt.BrushStyle.NoBrush)
                for axis in ("x", "y", "z"):
                    color = axis_colors[axis]
                    active = axis == active_axis
                    painter.setPen(
                        QPen(color.lighter(155) if active else color, 4.2 if active else 2.1)
                    )
                    points = geometry["rings"].get(axis, [])
                    if len(points) >= 3:
                        painter.drawPolyline(QPolygonF(points))
            painter.setPen(QPen(QColor(255, 255, 255, 230), 1.2))
            painter.setBrush(QColor(255, 255, 255, 210))
            painter.drawEllipse(center, 4.5, 4.5)
        finally:
            painter.end()
        return pixmap

    def _selected_3d_blockout_bounds(self, width: int, height: int) -> QRectF | None:
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        if not primitive_id:
            return None
        return self._3d_blockout_bounds_for_id(primitive_id, width, height)

    def _3d_blockout_bounds_for_id(
        self,
        primitive_id: str,
        width: int,
        height: int,
    ) -> QRectF | None:
        from app.painter_3d_blockout import project_blockout_scene

        projection = project_blockout_scene(self._current_3d_blockout_scene(), max(1, int(width)), max(1, int(height)))
        points: list[tuple[float, float]] = []
        for face in projection.get("faces", []) or []:
            if str(face.get("primitive_id") or "") != primitive_id:
                continue
            points.extend((float(x), float(y)) for x, y in face.get("points", []) or [])
        for edge in projection.get("edges", []) or []:
            if str(edge.get("primitive_id") or "") != primitive_id:
                continue
            for key in ("a", "b"):
                xy = edge.get(key)
                if isinstance(xy, (list, tuple)) and len(xy) >= 2:
                    points.append((float(xy[0]), float(xy[1])))
        if not points:
            return None
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return QRectF(
            max(0.0, min(xs)),
            max(0.0, min(ys)),
            max(8.0, min(float(width), max(xs)) - max(0.0, min(xs))),
            max(8.0, min(float(height), max(ys)) - max(0.0, min(ys))),
        )

    def _3d_blockout_primitive_at(self, point: QPointF) -> str:
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return ""
        rows = list(self._current_3d_blockout_scene().to_dict().get("primitives", []) or [])
        candidates: list[tuple[float, str]] = []
        for row in reversed(rows):
            primitive_id = str(row.get("id") or "")
            bounds = self._3d_blockout_bounds_for_id(
                primitive_id,
                canvas.width(),
                canvas.height(),
            )
            if bounds is None:
                continue
            padded = QRectF(bounds)
            padded.adjust(-6.0, -6.0, 6.0, 6.0)
            if padded.contains(point):
                candidates.append((max(1.0, bounds.width() * bounds.height()), primitive_id))
        return min(candidates, default=(0.0, ""), key=lambda row: row[0])[1]

    @staticmethod
    def _blockout_scale_handle(bounds: QRectF) -> QPointF:
        return QPointF(bounds.right(), bounds.bottom())

    @staticmethod
    def _blockout_rotate_handle(bounds: QRectF) -> QPointF:
        return QPointF(bounds.center().x(), bounds.top() - 28.0)

    def _blockout_gizmo_geometry(self, bounds: QRectF) -> dict[str, object]:
        from app.painter_3d_blockout import project_blockout_world_point

        canvas = getattr(self, "canvas", None)
        scene = self._current_3d_blockout_scene()
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        primitive = next(
            (row for row in scene.primitives if row.id == primitive_id),
            None,
        )
        if canvas is None or primitive is None:
            center = bounds.center()
            return {
                "center": center,
                "axes": {
                    "x": QPointF(center.x() + 48.0, center.y() + 8.0),
                    "y": QPointF(center.x() - 36.0, center.y() + 24.0),
                    "z": QPointF(center.x(), center.y() - 52.0),
                },
                "rings": {},
            }
        width, height = max(1, canvas.width()), max(1, canvas.height())
        origin = tuple(float(value) for value in primitive.position)
        projected_origin = project_blockout_world_point(scene, origin, width, height)
        center = (
            QPointF(float(projected_origin["x"]), float(projected_origin["y"]))
            if projected_origin is not None
            else bounds.center()
        )
        axes: dict[str, QPointF] = {}
        unit_vectors = {
            "x": (1.0, 0.0, 0.0),
            "y": (0.0, 1.0, 0.0),
            "z": (0.0, 0.0, 1.0),
        }
        for axis, vector in unit_vectors.items():
            projected = project_blockout_world_point(
                scene,
                (
                    origin[0] + vector[0],
                    origin[1] + vector[1],
                    origin[2] + vector[2],
                ),
                width,
                height,
            )
            if projected is None:
                axes[axis] = center
                continue
            direction = QPointF(
                float(projected["x"]) - center.x(),
                float(projected["y"]) - center.y(),
            )
            length = max(0.001, math.hypot(direction.x(), direction.y()))
            display_length = 52.0
            axes[axis] = QPointF(
                center.x() + direction.x() * display_length / length,
                center.y() + direction.y() * display_length / length,
            )

        radius = max(0.65, max(float(value) for value in primitive.scale) * 0.72)
        rings: dict[str, list[QPointF]] = {}
        for axis in ("x", "y", "z"):
            points: list[QPointF] = []
            for index in range(49):
                angle = math.tau * index / 48.0
                c, s = math.cos(angle) * radius, math.sin(angle) * radius
                offset = (
                    (0.0, c, s)
                    if axis == "x"
                    else (c, 0.0, s)
                    if axis == "y"
                    else (c, s, 0.0)
                )
                projected = project_blockout_world_point(
                    scene,
                    (
                        origin[0] + offset[0],
                        origin[1] + offset[1],
                        origin[2] + offset[2],
                    ),
                    width,
                    height,
                )
                if projected is not None:
                    points.append(
                        QPointF(float(projected["x"]), float(projected["y"]))
                    )
            rings[axis] = points
        return {"center": center, "axes": axes, "rings": rings}

    def _blockout_gizmo_axis_points(self, bounds: QRectF) -> dict[str, QPointF]:
        return dict(self._blockout_gizmo_geometry(bounds)["axes"])

    def _canvas_local_point_from_widget(self, obj, point: QPoint) -> QPointF | None:
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return None
        host_point = self._point_in_canvas_host(obj, point)
        canvas_rect = canvas.geometry()
        return QPointF(float(host_point.x() - canvas_rect.x()), float(host_point.y() - canvas_rect.y()))

    def _blockout_drag_mode_at(self, point: QPointF) -> str | None:
        canvas = getattr(self, "canvas", None)
        if canvas is None:
            return None
        bounds = self._selected_3d_blockout_bounds(canvas.width(), canvas.height())
        if bounds is None:
            return None
        rotate = self._blockout_rotate_handle(bounds)
        scale = self._blockout_scale_handle(bounds)
        selected_mode = str(getattr(self, "_blockout_transform_mode", "select") or "select")
        geometry = self._blockout_gizmo_geometry(bounds)
        if selected_mode in {"move", "scale"}:
            center = geometry["center"]
            for axis, endpoint in geometry["axes"].items():
                vector = endpoint - center
                length = max(1.0, math.hypot(vector.x(), vector.y()))
                hit_start = QPointF(
                    center.x() + vector.x() * 10.0 / length,
                    center.y() + vector.y() * 10.0 / length,
                )
                if _distance_to_segment(point, hit_start, endpoint) <= 8.0:
                    return f"{selected_mode}_{axis}"
        if selected_mode == "rotate":
            for axis, ring in geometry["rings"].items():
                if any(
                    _distance_to_segment(point, ring[index - 1], ring[index]) <= 7.0
                    for index in range(1, len(ring))
                ):
                    return f"rotate_{axis}"
        if _distance_qpointf(point, rotate) <= 16.0:
            return "rotate"
        if _distance_qpointf(point, scale) <= 16.0:
            return "scale"
        padded = QRectF(bounds)
        padded.adjust(-10.0, -10.0, 10.0, 10.0)
        if padded.contains(point):
            mode = str(getattr(self, "_blockout_transform_mode", "select") or "select")
            return mode if mode in {"select", "move", "rotate", "scale"} else "select"
        return None

    def _begin_3d_blockout_drag(self, obj, point: QPoint) -> bool:
        if str(getattr(self, "_canvas_workspace_mode", "paint")) != "3d_place":
            return False
        if not bool(getattr(self, "blockout_overlay_btn", None) and self.blockout_overlay_btn.isChecked()):
            return False
        local = self._canvas_local_point_from_widget(obj, point)
        if local is None:
            return False
        primitive_id = str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        mode = self._blockout_drag_mode_at(local)
        if mode is None:
            hit_id = self._3d_blockout_primitive_at(local)
            if not hit_id:
                return False
            primitive_id = hit_id
            self._painter_3d_blockout_selected_id = hit_id
            self._refresh_3d_blockout_panel()
            mode = self._blockout_drag_mode_at(local)
        if mode is None:
            return False
        if mode == "select":
            if hasattr(self, "_tool_status_label"):
                self._tool_status_label.setText("3D Place: object selected")
            return True
        scene = self._current_3d_blockout_scene().to_dict()
        selected = next((row for row in scene.get("primitives", []) or [] if str(row.get("id") or "") == primitive_id), None)
        if selected is None:
            return False
        bounds = self._selected_3d_blockout_bounds(getattr(self, "canvas").width(), getattr(self, "canvas").height())
        if bounds is None:
            return False
        geometry = self._blockout_gizmo_geometry(bounds)
        rotate_tangent = QPointF(1.0, 0.0)
        if mode.startswith("rotate_"):
            axis = mode.rsplit("_", 1)[1]
            ring = list(geometry["rings"].get(axis, []) or [])
            nearest: tuple[float, QPointF] | None = None
            for index in range(1, len(ring)):
                distance = _distance_to_segment(local, ring[index - 1], ring[index])
                tangent = ring[index] - ring[index - 1]
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, tangent)
            if nearest is not None:
                rotate_tangent = nearest[1]
        self._push_undo_state(f"3D blockout {mode}")
        self._painter_3d_blockout_drag = {
            "mode": mode,
            "primitive_id": primitive_id,
            "start_point": QPointF(local),
            "start_position": list(selected.get("position") or [0.0, 0.0, 0.0]),
            "start_rotation": list(selected.get("rotation") or [0.0, 0.0, 0.0]),
            "start_scale": list(selected.get("scale") or [1.0, 1.0, 1.0]),
            "start_bounds_center": QPointF(geometry["center"]),
            "rotate_tangent": QPointF(rotate_tangent),
        }
        self._blockout_active_axis = mode.rsplit("_", 1)[1] if "_" in mode else ""
        self._refresh_3d_blockout_overlay()
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            host.setCursor(
                Qt.CursorShape.SizeAllCursor
                if mode == "move" or mode.startswith("move_")
                else Qt.CursorShape.CrossCursor
            )
        return True

    def _update_3d_blockout_drag(self, obj, point: QPoint) -> None:
        drag = getattr(self, "_painter_3d_blockout_drag", None)
        if not drag:
            return
        local = self._canvas_local_point_from_widget(obj, point)
        if local is None:
            return
        start = QPointF(drag["start_point"])
        delta = local - start
        params: dict[str, float] = {}
        mode = str(drag.get("mode") or "")
        if mode == "move":
            pos = list(drag.get("start_position") or [0.0, 0.0, 0.0])
            params["x"] = float(pos[0]) + float(delta.x()) / 100.0
            params["y"] = float(pos[1])
            params["z"] = float(pos[2]) - float(delta.y()) / 100.0
        elif mode.startswith("move_"):
            pos = list(drag.get("start_position") or [0.0, 0.0, 0.0])
            axis = mode.rsplit("_", 1)[1]
            bounds = self._selected_3d_blockout_bounds(
                getattr(self, "canvas").width(),
                getattr(self, "canvas").height(),
            )
            if bounds is None:
                return
            geometry = self._blockout_gizmo_geometry(bounds)
            endpoint = geometry["axes"][axis]
            axis_vector = endpoint - geometry["center"]
            length_squared = max(
                1.0,
                axis_vector.x() * axis_vector.x() + axis_vector.y() * axis_vector.y(),
            )
            amount = (
                delta.x() * axis_vector.x() + delta.y() * axis_vector.y()
            ) / length_squared
            params[axis] = float(pos[{"x": 0, "y": 1, "z": 2}[axis]]) + float(amount)
        elif mode == "scale":
            scale = list(drag.get("start_scale") or [1.0, 1.0, 1.0])
            params["sx"] = max(0.1, float(scale[0]) + float(delta.x()) / 100.0)
            params["sy"] = max(0.1, float(scale[1]))
            params["sz"] = max(0.1, float(scale[2]) + float(delta.y()) / 100.0)
        elif mode.startswith("scale_"):
            scale = list(drag.get("start_scale") or [1.0, 1.0, 1.0])
            axis = mode.rsplit("_", 1)[1]
            bounds = self._selected_3d_blockout_bounds(
                getattr(self, "canvas").width(),
                getattr(self, "canvas").height(),
            )
            if bounds is None:
                return
            geometry = self._blockout_gizmo_geometry(bounds)
            endpoint = geometry["axes"][axis]
            axis_vector = endpoint - geometry["center"]
            length_squared = max(
                1.0,
                axis_vector.x() * axis_vector.x() + axis_vector.y() * axis_vector.y(),
            )
            delta_value = float(
                (
                    delta.x() * axis_vector.x() + delta.y() * axis_vector.y()
                )
                / length_squared
            )
            params[f"s{axis}"] = max(0.1, float(scale[{"x": 0, "y": 1, "z": 2}[axis]]) + delta_value)
        elif mode.startswith("rotate_"):
            axis = mode.rsplit("_", 1)[1]
            rot = list(drag.get("start_rotation") or [0.0, 0.0, 0.0])
            tangent = QPointF(drag.get("rotate_tangent") or QPointF(1.0, 0.0))
            tangent_length = max(0.001, math.hypot(tangent.x(), tangent.y()))
            signed_pixels = (
                delta.x() * tangent.x() + delta.y() * tangent.y()
            ) / tangent_length
            params[f"r{axis}"] = (
                float(rot[{"x": 0, "y": 1, "z": 2}[axis]])
                + float(signed_pixels) * 0.9
            )
        elif mode == "rotate":
            center = QPointF(drag["start_bounds_center"])
            start_angle = math.degrees(math.atan2(start.y() - center.y(), start.x() - center.x()))
            current_angle = math.degrees(math.atan2(local.y() - center.y(), local.x() - center.x()))
            rot = list(drag.get("start_rotation") or [0.0, 0.0, 0.0])
            params["rz"] = float(rot[2]) + current_angle - start_angle
        if not params:
            return
        from app.painter_3d_blockout import update_blockout_primitive

        try:
            current_scene = self._current_3d_blockout_scene()
            scene = update_blockout_primitive(
                current_scene,
                str(drag.get("primitive_id") or ""),
                **params,
            )
            if current_scene.snap_to_grid:
                from app.painter_3d_blockout import snap_blockout_primitive_to_grid

                scene = snap_blockout_primitive_to_grid(scene, str(drag.get("primitive_id") or ""))
        except ValueError:
            return
        self._store_3d_blockout_scene(scene)

    def _finish_3d_blockout_drag(self) -> None:
        self._painter_3d_blockout_drag = None
        self._blockout_active_axis = ""
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            host.setCursor(Qt.CursorShape.ArrowCursor)
        self._refresh_3d_blockout_overlay()

    def _focus_3d_blockout_panel(self) -> None:
        self._set_canvas_workspace_mode("3d_place", focus_panel=False)
        panel = getattr(self, "_paint_3d_blockout_panel", None)
        if panel is not None:
            panel.hide()
        self._refresh_3d_blockout_panel()

    def _build_3d_blockout_scene_menu(self) -> QMenu:
        scene = self._current_3d_blockout_scene()
        payload = scene.to_dict()
        menu = QMenu(self)
        menu.setObjectName("PaintBlockoutSceneMenu")

        toggle_specs = (
            ("Grid", "show_grid", bool(payload.get("show_grid", True))),
            ("Floor", "show_floor", bool(payload.get("show_floor", True))),
            ("Lit", "material_lit", bool(payload.get("material_lit", True))),
            ("Shadows", "show_shadows", bool(payload.get("show_shadows", True))),
            ("Fog", "show_fog", bool(payload.get("show_fog", False))),
            ("Depth", "show_depth", bool(payload.get("show_depth", False))),
        )
        for label, key, checked in toggle_specs:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(checked)
            action.toggled.connect(
                lambda enabled=False, flag=key: self._set_3d_blockout_scene_flag(
                    flag,
                    bool(enabled),
                )
            )
        snap_action = menu.addAction("Snap to Grid")
        snap_action.setCheckable(True)
        snap_action.setChecked(bool(payload.get("snap_to_grid", False)))
        snap_action.toggled.connect(
            lambda enabled=False: self._set_3d_blockout_snap(bool(enabled))
        )

        camera_menu = menu.addMenu("Camera")
        for label, preset in (
            ("Perspective", "perspective"),
            ("Front", "front"),
            ("Side", "side"),
            ("Top", "top"),
        ):
            action = camera_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, value=preset: self._apply_3d_blockout_camera_preset(
                    value
                )
            )

        menu.addSeparator()
        duplicate_action = menu.addAction("Duplicate Selected")
        ground_action = menu.addAction("Place Selected on Ground")
        delete_action = menu.addAction("Delete Selected")
        bake_action = menu.addAction("Bake 3D Guide to Paint Layer")
        has_selection = bool(
            str(getattr(self, "_painter_3d_blockout_selected_id", "") or "")
        )
        for action in (duplicate_action, ground_action, delete_action):
            action.setEnabled(has_selection)
        duplicate_action.triggered.connect(self._duplicate_selected_3d_blockout_primitive)
        ground_action.triggered.connect(self._align_selected_3d_blockout_to_ground)
        delete_action.triggered.connect(self._delete_selected_3d_blockout_primitive)
        bake_action.setEnabled(int(payload.get("primitive_count", 0) or 0) > 0)
        bake_action.triggered.connect(self._bake_3d_blockout_to_layer)
        return menu

    def _show_3d_blockout_scene_menu(self) -> None:
        button = getattr(self, "_blockout_scene_menu_btn", None)
        if button is None:
            return
        menu = self._build_3d_blockout_scene_menu()
        self._blockout_scene_menu = menu
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _set_canvas_workspace_mode(
        self,
        mode: str,
        *,
        focus_panel: bool = True,
    ) -> str:
        requested = str(mode or "").strip().casefold()
        if requested in {"ui", "ui_design", "designer", "design"}:
            selected = "ui_design"
        elif requested in {
            "3d",
            "3d_place",
            "place",
            "placement",
            "blockout",
        }:
            selected = "3d_place"
        else:
            selected = "paint"
        self._canvas_workspace_user_generation = int(
            getattr(self, "_canvas_workspace_user_generation", 0)
        ) + 1
        self._canvas_workspace_mode = selected
        if selected == "3d_place":
            self._set_tool("3d_blockout")
            self._set_3d_blockout_transform_mode(
                str(getattr(self, "_blockout_transform_mode", "move") or "move")
            )
            if focus_panel:
                self._focus_3d_blockout_panel()
        elif selected == "ui_design":
            self._set_tool("select")
            self._canvas_workspace_mode = "ui_design"
        else:
            self._set_tool("pen")
        self._sync_canvas_workspace_mode_controls()
        self._update_canvas_geometry()
        QTimer.singleShot(0, self._update_canvas_geometry)
        self._refresh_3d_blockout_overlay()
        return selected

    def _sync_canvas_workspace_mode_controls(self) -> None:
        workspace_mode = str(getattr(self, "_canvas_workspace_mode", "paint"))
        blockout = workspace_mode == "3d_place"
        ui_design = workspace_mode == "ui_design"
        for button_name, checked in (
            ("_canvas_mode_paint_btn", not blockout and not ui_design),
            ("_canvas_mode_ui_btn", ui_design),
            ("_canvas_mode_3d_btn", blockout),
            ("blockout_rail_btn", blockout),
        ):
            button = getattr(self, button_name, None)
            if button is not None:
                button.blockSignals(True)
                button.setChecked(checked)
                button.blockSignals(False)
        host = getattr(self, "_blockout_transform_host", None)
        if host is not None:
            host.setVisible(blockout)
        ui_host = getattr(self, "_ui_design_tool_host", None)
        if ui_host is not None:
            ui_host.setVisible(ui_design)
        ui_inspector = getattr(self, "_paint_ui_inspector", None)
        if ui_inspector is not None:
            ui_inspector.setVisible(ui_design)
        color_panel = getattr(self, "_paint_color_panel", None)
        if color_panel is not None:
            color_panel.setVisible(not ui_design and not blockout)
        layer_dock = getattr(self, "_paint_layer_dock_panel", None)
        if layer_dock is not None:
            layer_dock.setVisible(not ui_design)
        for shortcut in getattr(self, "_blockout_camera_shortcuts", []):
            shortcut.setEnabled(blockout)
        panel = getattr(self, "_paint_3d_blockout_panel", None)
        if panel is not None:
            panel.hide()
        palette = self._ensure_canvas_3d_shape_palette()
        if palette is not None:
            palette.setVisible(blockout)
            if blockout:
                palette.move(10, 10)
                palette.raise_()
                canvas_host = getattr(self, "_canvas_host", None)
                if canvas_host is not None:
                    canvas_host.setFocus(Qt.FocusReason.OtherFocusReason)
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is not None:
            overlay.setVisible(ui_design)
            if ui_design:
                self._refresh_painter_ui_overlay()
                overlay.raise_()
                overlay.setFocus(Qt.FocusReason.OtherFocusReason)

    def _select_painter_ui_object(
        self,
        object_id: str,
        mode: str = "replace",
    ) -> None:
        from app.painter_ui_document import select_ui_object

        self._painter_ui_document = select_ui_object(
            getattr(self, "_painter_ui_document", None),
            str(object_id or ""),
            mode=str(mode or "replace"),
        )
        self._refresh_painter_ui_overlay()

    def _set_painter_ui_selection(
        self,
        object_ids: object,
        primary_object_id: str = "",
    ) -> None:
        from app.painter_ui_document import select_ui_objects

        values = (
            [str(value) for value in object_ids]
            if isinstance(object_ids, (list, tuple))
            else []
        )
        self._painter_ui_document = select_ui_objects(
            getattr(self, "_painter_ui_document", None),
            values,
            primary_object_id=str(primary_object_id or ""),
        )
        self._refresh_painter_ui_overlay()

    def _set_painter_ui_artboard(self, artboard_id: str) -> None:
        from app.painter_ui_document import set_active_ui_artboard

        current = getattr(self, "_painter_ui_document", None)
        if str((current or {}).get("active_artboard_id") or "") == str(artboard_id):
            return
        self._push_undo_state("Switch UI artboard")
        self._painter_ui_document = set_active_ui_artboard(current, artboard_id)
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_artboard_position(
        self,
        artboard_id: str,
        x: float,
        y: float,
    ) -> None:
        from app.painter_ui_document import update_ui_artboard

        current = getattr(self, "_painter_ui_document", None)
        row = next(
            (
                item
                for item in (current or {}).get("artboards", [])
                if item.get("id") == artboard_id
            ),
            None,
        )
        if row is None:
            return
        if (
            abs(float(row.get("x", 0.0)) - float(x)) < 0.001
            and abs(float(row.get("y", 0.0)) - float(y)) < 0.001
        ):
            return
        self._push_undo_state("Move UI artboard")
        self._painter_ui_document, _updated = update_ui_artboard(
            current,
            str(artboard_id),
            {"x": float(x), "y": float(y)},
        )
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_artboard_changes(
        self,
        artboard_id: str,
        changes: object,
    ) -> None:
        if not isinstance(changes, dict):
            return
        from app.painter_ui_document import update_ui_artboard

        current = getattr(self, "_painter_ui_document", None)
        self._push_undo_state("Update UI artboard layout")
        self._painter_ui_document, _updated = update_ui_artboard(
            current,
            str(artboard_id),
            changes,
        )
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _add_painter_ui_artboard_preset(
        self,
        name: str,
        width: int,
        height: int,
        breakpoint: str,
    ) -> None:
        from app.painter_ui_document import add_ui_artboard

        self._push_undo_state("Add UI artboard")
        self._painter_ui_document, _row = add_ui_artboard(
            getattr(self, "_painter_ui_document", None),
            name=str(name),
            width=int(width),
            height=int(height),
            breakpoint=str(breakpoint),
        )
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _set_painter_ui_tool(self, tool: str) -> str:
        requested = str(tool or "select").strip().casefold()
        selected = requested if requested in {
            "frame",
            "rectangle",
            "ellipse",
            "line",
            "text",
            "image",
            "button",
            "progress",
        } else "select"
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is not None:
            overlay.set_tool(selected)
            overlay.setFocus(Qt.FocusReason.OtherFocusReason)
        for key, button in getattr(self, "_ui_design_tool_buttons", {}).items():
            button.blockSignals(True)
            button.setChecked(key == selected)
            button.blockSignals(False)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"UI Design: {selected.title()}")
        return selected

    def _set_painter_ui_snap(self, enabled: bool) -> None:
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is not None:
            overlay.set_snap(bool(enabled), 8.0)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                "UI Design: Snap 8 px / 15 deg"
                if enabled
                else "UI Design: Free transform"
            )

    def _fit_painter_ui_view(self, mode: str = "all") -> dict:
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is None:
            return {}
        requested = str(mode or "all").strip().casefold()
        if requested == "selection":
            if not overlay.fit_selection():
                overlay.fit_artboard()
                requested = "artboard"
        elif requested == "artboard":
            overlay.fit_artboard()
        else:
            requested = "all"
            overlay.fit_all()
        overlay.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                {
                    "all": "UI Design: All artboards",
                    "artboard": "UI Design: Active artboard",
                    "selection": "UI Design: Selection",
                }[requested]
            )
        return {"mode": requested, **overlay.view_state()}

    def _fit_painter_ui_view(self, mode: str = "all") -> dict:
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is None:
            return {}
        requested = str(mode or "all").strip().casefold()
        if requested == "selection":
            if not overlay.fit_selection():
                overlay.fit_artboard()
                requested = "artboard"
        elif requested == "artboard":
            overlay.fit_artboard()
        else:
            requested = "all"
            overlay.fit_all()
        overlay.setFocus(Qt.FocusReason.OtherFocusReason)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                {
                    "all": "UI Design: All artboards",
                    "artboard": "UI Design: Active artboard",
                    "selection": "UI Design: Selection",
                }[requested]
            )
        return {"mode": requested, **overlay.view_state()}

    @staticmethod
    def _painter_ui_object_preset(kind: str) -> dict:
        presets = {
            "frame": {
                "name": "Frame",
                "width": 420.0,
                "height": 280.0,
                "style": {"fill": "#263344", "stroke": "#52657E"},
            },
            "rectangle": {
                "name": "Rectangle",
                "width": 240.0,
                "height": 140.0,
                "style": {"fill": "#40516A", "stroke": "#71839B"},
            },
            "ellipse": {
                "name": "Ellipse",
                "width": 160.0,
                "height": 160.0,
                "style": {"fill": "#40516A", "stroke": "#71839B"},
            },
            "line": {
                "name": "Line",
                "width": 240.0,
                "height": 24.0,
                "style": {"fill": "#8FA7C5", "stroke_width": 2},
            },
            "text": {
                "name": "Heading",
                "width": 360.0,
                "height": 56.0,
                "style": {"text_color": "#F4F7FC", "font_size": 16},
                "content": {"text": "Heading"},
            },
            "image": {
                "name": "Image",
                "width": 320.0,
                "height": 180.0,
                "style": {"fill": "#202A37", "stroke": "#71839B"},
            },
            "button": {
                "name": "Primary Button",
                "width": 280.0,
                "height": 56.0,
                "style": {
                    "fill": "#4C74DB",
                    "stroke": "#7091E7",
                    "radius": 6,
                },
                "content": {"text": "Continue"},
            },
            "progress": {
                "name": "Progress",
                "width": 300.0,
                "height": 20.0,
                "style": {"fill": "#263344", "accent": "#6FA0F5"},
                "content": {"value": 0.64},
            },
        }
        return dict(presets.get(str(kind), presets["rectangle"]))

    def _add_default_painter_ui_object(self, kind: str) -> None:
        from app.painter_ui_document import add_ui_object, normalize_ui_document

        document = normalize_ui_document(
            getattr(self, "_painter_ui_document", None),
            fallback_width=self._canvas_document_size[0],
            fallback_height=self._canvas_document_size[1],
        )
        active_id = document["active_artboard_id"]
        artboard = next(
            row for row in document["artboards"] if row["id"] == active_id
        )
        index = sum(
            1 for row in document["objects"] if row["artboard_id"] == active_id
        )
        preset = self._painter_ui_object_preset(kind)
        width = min(float(preset["width"]), float(artboard["width"]) * 0.72)
        height = min(float(preset["height"]), float(artboard["height"]) * 0.42)
        x = max(0.0, (float(artboard["width"]) - width) * 0.5)
        y = max(
            0.0,
            min(
                float(artboard["height"]) - height,
                72.0 + float(index) * 28.0,
            ),
        )
        updated, _row = add_ui_object(
            document,
            kind=str(kind),
            name=str(preset["name"]),
            artboard_id=active_id,
            x=x,
            y=y,
            width=width,
            height=height,
            style=dict(preset.get("style") or {}),
            content=dict(preset.get("content") or {}),
        )
        self._push_undo_state(f"Add UI {kind}")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _create_painter_ui_object_from_rect(
        self,
        kind: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        from app.painter_ui_document import add_ui_object

        preset = self._painter_ui_object_preset(kind)
        self._push_undo_state(f"Draw UI {kind}")
        updated, _row = add_ui_object(
            getattr(self, "_painter_ui_document", None),
            kind=str(kind),
            name=str(preset["name"]),
            x=max(0.0, float(x)),
            y=max(0.0, float(y)),
            width=max(1.0, float(width)),
            height=max(1.0, float(height)),
            style=dict(preset.get("style") or {}),
            content=dict(preset.get("content") or {}),
        )
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._set_painter_ui_tool("select")
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_object_geometry(
        self,
        object_id: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        self._update_painter_ui_object_changes(
            object_id,
            {
                "x": float(x),
                "y": float(y),
                "width": max(1.0, float(width)),
                "height": max(1.0, float(height)),
            },
            label="Transform UI object",
        )

    def _update_painter_ui_object_changes(
        self,
        object_id: str,
        changes: object,
        *,
        label: str = "Edit UI object",
    ) -> None:
        from app.painter_ui_constraints import (
            capture_ui_constraints,
            constraint_parent_geometry,
        )
        from app.painter_ui_document import update_ui_object

        if not isinstance(changes, dict):
            return
        current = getattr(self, "_painter_ui_document", None)
        original = next(
            (
                row
                for row in (current or {}).get("objects", [])
                if row.get("id") == object_id
            ),
            None,
        )
        if original is None:
            return
        effective_changes = dict(changes)
        if {"x", "y", "width", "height"} & effective_changes.keys():
            candidate = {**original, **effective_changes}
            effective_changes["constraints"] = capture_ui_constraints(
                candidate,
                constraint_parent_geometry(current, candidate),
                candidate.get("constraints"),
            )
        if all(
            original.get(key) == value
            for key, value in effective_changes.items()
        ):
            return
        self._push_undo_state(label)
        updated, _row = update_ui_object(
            current,
            object_id,
            effective_changes,
        )
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_responsive_override(
        self,
        object_id: str,
        breakpoint: str,
        orientation: str,
        changes: object,
    ) -> None:
        if not isinstance(changes, dict):
            return
        from app.painter_ui_responsive import set_ui_responsive_override

        current = getattr(self, "_painter_ui_document", None)
        row = next(
            (
                item
                for item in (current or {}).get("objects", [])
                if item.get("id") == object_id
            ),
            None,
        )
        if row is None:
            return
        overrides = set_ui_responsive_override(
            row,
            breakpoint=breakpoint,
            orientation=orientation,
            changes=changes,
        )
        self._update_painter_ui_object_changes(
            object_id,
            {"responsive_overrides": overrides},
            label="Edit UI responsive override",
        )

    def _remove_painter_ui_responsive_override(
        self,
        object_id: str,
        breakpoint: str,
        orientation: str,
    ) -> None:
        from app.painter_ui_responsive import remove_ui_responsive_override

        current = getattr(self, "_painter_ui_document", None)
        row = next(
            (
                item
                for item in (current or {}).get("objects", [])
                if item.get("id") == object_id
            ),
            None,
        )
        if row is None:
            return
        overrides = remove_ui_responsive_override(
            row,
            breakpoint=breakpoint,
            orientation=orientation,
        )
        self._update_painter_ui_object_changes(
            object_id,
            {"responsive_overrides": overrides},
            label="Remove UI responsive override",
        )

    def _create_painter_ui_component(
        self,
        root_object_id: str,
        name: str,
    ) -> None:
        from app.painter_ui_components import convert_ui_object_to_component

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _component = convert_ui_object_to_component(
            current,
            root_object_id=str(root_object_id),
            name=str(name),
        )
        self._push_undo_state("Create UI component")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _instantiate_painter_ui_component(
        self,
        component_id: str,
        artboard_id: str,
        x: float,
        y: float,
    ) -> None:
        from app.painter_ui_components import instantiate_ui_component

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _result = instantiate_ui_component(
            current,
            component_id=str(component_id),
            artboard_id=str(artboard_id),
            x=float(x),
            y=float(y),
        )
        self._push_undo_state("Instantiate UI component")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _create_painter_ui_component_variant(
        self,
        component_id: str,
        name: str,
    ) -> None:
        from app.painter_ui_components import create_ui_component_variant

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _variant = create_ui_component_variant(
            current,
            component_id=str(component_id),
            name=str(name),
        )
        self._push_undo_state("Create UI component variant")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _switch_painter_ui_component_variant(
        self,
        instance_root_id: str,
        component_id: str,
    ) -> None:
        from app.painter_ui_components import (
            switch_ui_component_instance_variant,
        )

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _result = switch_ui_component_instance_variant(
            current,
            instance_root_id=str(instance_root_id),
            target_component_id=str(component_id),
        )
        self._push_undo_state("Switch UI component variant")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _detach_painter_ui_component(
        self,
        instance_root_id: str,
        create_local_component: bool,
        name: str,
    ) -> None:
        from app.painter_ui_components import detach_ui_component_instance

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _result = detach_ui_component_instance(
            current,
            instance_root_id=str(instance_root_id),
            create_local_component=bool(create_local_component),
            name=str(name),
        )
        self._push_undo_state(
            (
                "Localize UI component instance"
                if create_local_component
                else "Detach UI component instance"
            )
        )
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_component(
        self,
        component_id: str,
        changes: object,
    ) -> None:
        from app.painter_ui_document import update_ui_component

        if not isinstance(changes, dict):
            return
        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _component = update_ui_component(
            current,
            str(component_id),
            changes,
        )
        self._push_undo_state("Update UI component")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _add_painter_ui_token(self, values: object) -> None:
        from app.painter_ui_document import add_ui_token

        if not isinstance(values, dict):
            return
        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _token = add_ui_token(
            current,
            name=str(values.get("name") or ""),
            kind=str(values.get("kind") or "color"),
            token_value=values.get("value"),
            theme_values=values.get("theme_values"),
            alias_token_id=str(values.get("alias_token_id") or ""),
            description=str(values.get("description") or ""),
        )
        self._push_undo_state("Add UI token")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _update_painter_ui_token(self, token_id: str, changes: object) -> None:
        from app.painter_ui_document import update_ui_token

        if not isinstance(changes, dict):
            return
        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _token = update_ui_token(current, str(token_id), changes)
        self._push_undo_state("Update UI token")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _remove_painter_ui_token(
        self,
        token_id: str,
        detach_references: bool,
    ) -> None:
        from app.painter_ui_document import remove_ui_token

        current = getattr(self, "_painter_ui_document", None)
        if not current:
            return
        updated, _result = remove_ui_token(
            current,
            str(token_id),
            detach_references=bool(detach_references),
        )
        self._push_undo_state("Remove UI token")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _bind_painter_ui_token(
        self,
        object_id: str,
        path: str,
        token_id: str,
    ) -> None:
        current = getattr(self, "_painter_ui_document", None)
        row = next(
            (
                item
                for item in (current or {}).get("objects", [])
                if item.get("id") == str(object_id)
            ),
            None,
        )
        if row is None:
            return
        bindings = dict(row.get("token_bindings") or {})
        if token_id:
            bindings[str(path)] = str(token_id)
        else:
            bindings.pop(str(path), None)
        self._update_painter_ui_object_changes(
            str(object_id),
            {"token_bindings": bindings},
            label="Bind UI token" if token_id else "Unbind UI token",
        )

    def _update_painter_ui_objects_batch(
        self,
        changes_by_id: object,
        *,
        label: str = "Transform UI objects",
    ) -> None:
        from app.painter_ui_document import update_ui_object

        if not isinstance(changes_by_id, dict) or not changes_by_id:
            return
        current = getattr(self, "_painter_ui_document", None)
        original_by_id = {
            str(row.get("id") or ""): row
            for row in (current or {}).get("objects", [])
        }
        effective: dict[str, dict[str, object]] = {}
        for raw_object_id, raw_changes in changes_by_id.items():
            object_id = str(raw_object_id or "")
            if not isinstance(raw_changes, dict) or object_id not in original_by_id:
                continue
            changes = dict(raw_changes)
            if any(
                original_by_id[object_id].get(key) != value
                for key, value in changes.items()
            ):
                effective[object_id] = changes
        if not effective:
            return
        self._push_undo_state(label)
        updated = current
        for object_id, changes in effective.items():
            updated, _row = update_ui_object(updated, object_id, changes)
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _move_painter_ui_object(
        self,
        object_id: str,
        x: float,
        y: float,
    ) -> None:
        self._update_painter_ui_object_changes(
            object_id,
            {"x": float(x), "y": float(y)},
            label="Move UI object",
        )

    def _delete_painter_ui_object(self, object_id: str = "") -> None:
        from app.painter_ui_document import remove_ui_object

        current = getattr(self, "_painter_ui_document", None)
        target = str(
            object_id
            or ((current or {}).get("selection") or {}).get("object_id")
            or ""
        )
        if not target:
            return
        self._push_undo_state("Delete UI object")
        updated, _result = remove_ui_object(current, target)
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _align_painter_ui_object(self, object_id: str, command: str) -> None:
        current = getattr(self, "_painter_ui_document", None)
        selected_ids = list(
            ((current or {}).get("selection") or {}).get("object_ids") or []
        )
        if object_id and object_id not in selected_ids:
            selected_ids = [object_id]
        rows = [
            item
            for item in (current or {}).get("objects", [])
            if item.get("id") in selected_ids and not item.get("locked")
        ]
        if not rows:
            return
        row = rows[-1]
        artboard = next(
            (
                item
                for item in (current or {}).get("artboards", [])
                if item.get("id") == row.get("artboard_id")
            ),
            None,
        )
        if artboard is None:
            return
        min_x = min(float(item["x"]) for item in rows)
        min_y = min(float(item["y"]) for item in rows)
        max_x = max(float(item["x"]) + float(item["width"]) for item in rows)
        max_y = max(float(item["y"]) + float(item["height"]) for item in rows)
        center_x = (min_x + max_x) * 0.5
        center_y = (min_y + max_y) * 0.5
        changes_by_id: dict[str, dict[str, float]] = {}
        if command in {"distribute_h", "distribute_v"} and len(rows) >= 3:
            if command == "distribute_h":
                ordered = sorted(rows, key=lambda item: float(item["x"]))
                total = sum(float(item["width"]) for item in ordered)
                gap = max(0.0, (max_x - min_x - total) / (len(ordered) - 1))
                cursor = min_x
                for item in ordered:
                    changes_by_id[item["id"]] = {"x": cursor}
                    cursor += float(item["width"]) + gap
            else:
                ordered = sorted(rows, key=lambda item: float(item["y"]))
                total = sum(float(item["height"]) for item in ordered)
                gap = max(0.0, (max_y - min_y - total) / (len(ordered) - 1))
                cursor = min_y
                for item in ordered:
                    changes_by_id[item["id"]] = {"y": cursor}
                    cursor += float(item["height"]) + gap
        else:
            for item in rows:
                changes: dict[str, float] = {}
                if command == "left":
                    changes["x"] = min_x if len(rows) > 1 else 0.0
                elif command == "hcenter":
                    changes["x"] = (
                        center_x - float(item["width"]) * 0.5
                        if len(rows) > 1
                        else max(
                            0.0,
                            (float(artboard["width"]) - float(item["width"])) * 0.5,
                        )
                    )
                elif command == "right":
                    changes["x"] = (
                        max_x - float(item["width"])
                        if len(rows) > 1
                        else max(
                            0.0,
                            float(artboard["width"]) - float(item["width"]),
                        )
                    )
                elif command == "top":
                    changes["y"] = min_y if len(rows) > 1 else 0.0
                elif command == "vcenter":
                    changes["y"] = (
                        center_y - float(item["height"]) * 0.5
                        if len(rows) > 1
                        else max(
                            0.0,
                            (float(artboard["height"]) - float(item["height"])) * 0.5,
                        )
                    )
                elif command == "bottom":
                    changes["y"] = (
                        max_y - float(item["height"])
                        if len(rows) > 1
                        else max(
                            0.0,
                            float(artboard["height"]) - float(item["height"]),
                        )
                    )
                if changes:
                    changes_by_id[item["id"]] = changes
        self._update_painter_ui_objects_batch(
            changes_by_id,
            label=f"Arrange UI objects {command}",
        )

    def _group_painter_ui_objects(self, object_ids: object) -> None:
        from app.painter_ui_document import group_ui_objects

        selected_ids = (
            [str(value) for value in object_ids]
            if isinstance(object_ids, (list, tuple))
            else []
        )
        if len(selected_ids) < 2:
            return
        self._push_undo_state("Group UI objects")
        updated, _group = group_ui_objects(
            getattr(self, "_painter_ui_document", None),
            selected_ids,
        )
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _ungroup_painter_ui_object(self, object_id: str = "") -> None:
        from app.painter_ui_document import ungroup_ui_object

        current = getattr(self, "_painter_ui_document", None)
        target = str(
            object_id
            or ((current or {}).get("selection") or {}).get("object_id")
            or ""
        )
        if not target:
            return
        self._push_undo_state("Ungroup UI objects")
        updated, _result = ungroup_ui_object(current, target)
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _reorder_painter_ui_objects(
        self,
        object_ids: object,
        command: str,
    ) -> None:
        from app.painter_ui_document import reorder_ui_objects

        selected_ids = (
            [str(value) for value in object_ids]
            if isinstance(object_ids, (list, tuple))
            else []
        )
        if not selected_ids:
            return
        self._push_undo_state(f"Reorder UI objects {command}")
        self._painter_ui_document = reorder_ui_objects(
            getattr(self, "_painter_ui_document", None),
            selected_ids,
            str(command or ""),
        )
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _move_painter_ui_hierarchy(
        self,
        object_ids: object,
        target_id: str,
        placement: str,
    ) -> None:
        from app.painter_ui_document import move_ui_objects_in_hierarchy

        selected_ids = (
            [str(value) for value in object_ids]
            if isinstance(object_ids, (list, tuple))
            else []
        )
        if not selected_ids:
            return
        target = str(target_id or "")
        operation = str(placement or "root")
        updated = move_ui_objects_in_hierarchy(
            getattr(self, "_painter_ui_document", None),
            selected_ids,
            target_parent_id=target if operation == "inside" else "",
            anchor_id=target if operation in {"before", "after"} else "",
            placement=operation,
        )
        self._push_undo_state("Move UI hierarchy")
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _duplicate_painter_ui_object(self, object_id: str = "") -> None:
        from app.painter_ui_document import add_ui_object, update_ui_object

        current = getattr(self, "_painter_ui_document", None)
        target = str(
            object_id
            or ((current or {}).get("selection") or {}).get("object_id")
            or ""
        )
        row = next(
            (
                item
                for item in (current or {}).get("objects", [])
                if item.get("id") == target
            ),
            None,
        )
        if row is None:
            return
        self._push_undo_state("Duplicate UI object")
        updated, created = add_ui_object(
            current,
            kind=row["kind"],
            name=f"{row['name']} Copy",
            artboard_id=row["artboard_id"],
            parent_id=row["parent_id"],
            x=float(row["x"]) + 12.0,
            y=float(row["y"]) + 12.0,
            width=row["width"],
            height=row["height"],
            style=row["style"],
            content=row["content"],
        )
        updated, _created = update_ui_object(
            updated,
            created["id"],
            {
                "rotation": row["rotation"],
                "opacity": row["opacity"],
                "visible": row["visible"],
                "locked": row["locked"],
                "constraints": row["constraints"],
                "layout": row["layout"],
                "accessibility": row["accessibility"],
            },
        )
        self._painter_ui_document = updated
        self._painter_document_dirty = True
        self._refresh_painter_ui_overlay()

    def _handle_painter_ui_key_command(self, command: str, coarse: bool) -> None:
        current = getattr(self, "_painter_ui_document", None)
        selected = str(
            ((current or {}).get("selection") or {}).get("object_id") or ""
        )
        if not selected:
            return
        if command == "delete":
            self._delete_painter_ui_object(selected)
            return
        if command == "duplicate":
            self._duplicate_painter_ui_object(selected)
            return
        row = next(
            (
                item
                for item in (current or {}).get("objects", [])
                if item.get("id") == selected
            ),
            None,
        )
        if row is None or row.get("locked"):
            return
        step = 10.0 if coarse else 1.0
        dx = -step if command == "left" else step if command == "right" else 0.0
        dy = -step if command == "up" else step if command == "down" else 0.0
        self._update_painter_ui_object_changes(
            selected,
            {
                "x": max(0.0, float(row["x"]) + dx),
                "y": max(0.0, float(row["y"]) + dy),
            },
            label="Nudge UI object",
        )

    def _refresh_painter_ui_overlay(self) -> None:
        overlay = getattr(self, "_painter_ui_overlay", None)
        if overlay is None:
            return
        overlay.set_document(getattr(self, "_painter_ui_document", None))
        if str(getattr(self, "_canvas_workspace_mode", "paint")) == "ui_design":
            overlay.show()
            overlay.raise_()
        inspector = getattr(self, "_paint_ui_inspector", None)
        if inspector is not None:
            inspector.set_document(getattr(self, "_painter_ui_document", None))

    def _set_3d_blockout_transform_mode(self, mode: str) -> str:
        selected = str(mode or "").strip().casefold()
        if selected not in {"select", "move", "rotate", "scale"}:
            selected = "move"
        self._blockout_transform_mode = selected
        self._blockout_active_axis = ""
        for key, button in getattr(self, "_blockout_transform_buttons", {}).items():
            button.blockSignals(True)
            button.setChecked(key == selected)
            button.blockSignals(False)
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"3D Place: {selected.title()}")
        self._refresh_3d_blockout_overlay()
        return selected

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
        slider = StudioSlider("accent")
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
            try:
                return float(
                    getattr(self, "_pbr_texture_settings", {}).get(
                        key,
                        PAINTER_PBR_DEFAULTS.get(key, 0.0),
                    )
                )
            except Exception:
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
        base_settings = getattr(self, "_pbr_texture_settings", {})
        settings = {
            "normal_strength": self._pbr_slider_value("normal_strength"),
            "normal_radius_px": self._pbr_slider_value("normal_radius_px"),
            "normal_format": str(combo.currentData() if combo is not None else "unreal_directx"),
            "normal_filter": str(base_settings.get("normal_filter", "sobel")),
            "height_contrast": self._pbr_slider_value("height_contrast"),
            "height_blur_px": self._pbr_slider_value("height_blur_px"),
            "edge_aware_smoothing": bool(base_settings.get("edge_aware_smoothing", True)),
            "edge_aware_sensitivity": self._pbr_slider_value("edge_aware_sensitivity"),
            "ao_strength": self._pbr_slider_value("ao_strength"),
            "ao_radius_px": self._pbr_slider_value("ao_radius_px"),
            "ao_algorithm": str(base_settings.get("ao_algorithm", "heightfield_horizon")),
            "ao_samples": int(self._pbr_slider_value("ao_samples")),
            "ao_steps": int(self._pbr_slider_value("ao_steps")),
            "ao_height_scale": self._pbr_slider_value("ao_height_scale"),
            "ao_multiscale": bool(base_settings.get("ao_multiscale", True)),
            "cavity_strength": self._pbr_slider_value("cavity_strength"),
            "cavity_radius_px": self._pbr_slider_value("cavity_radius_px"),
            "curvature_strength": self._pbr_slider_value("curvature_strength"),
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

    def _pbr_source_image(self, *, max_size: int | None = None):
        from PIL import Image

        bg = self._export_background_pixmap()
        target_size = _paint_export_size(bg, fallback=self._canvas_document_size)
        width, height = max(1, int(target_size[0])), max(1, int(target_size[1]))
        render_w, render_h = width, height
        if max_size:
            longest = max(width, height)
            limit = max(64, int(max_size))
            if longest > limit:
                scale = limit / float(longest)
                render_w = max(8, int(round(width * scale)))
                render_h = max(8, int(round(height * scale)))
        if bg is not None and not bg.isNull():
            base = _pixmap_to_pil_rgba(bg)
            if base.size != (render_w, render_h):
                base = base.resize((render_w, render_h), Image.LANCZOS)
        else:
            base = Image.new("RGBA", (render_w, render_h), (0, 0, 0, 0))
        width_scale = render_w / max(1, self.canvas.width())
        overlay = compose_pil_paint_overlays(
            strokes=self._visible_strokes_for_export(),
            bubbles=self._bubbles,
            stickers=self._stickers,
            time_ms=self._time_ms,
            frame_size=(render_w, render_h),
            stroke_width_scale=width_scale,
        )
        image = Image.alpha_composite(base.convert("RGBA"), overlay)
        neutral = Image.new("RGBA", image.size, (128, 128, 128, 255))
        flattened = Image.alpha_composite(neutral, image).convert("RGB")
        digest = hashlib.blake2b(digest_size=16)
        digest.update(str(flattened.size).encode("ascii"))
        digest.update(flattened.tobytes())
        report = {
            "schema": "tigerstudio.paint.pbr_source.v1",
            "mode": "in_memory_preview" if max_size else "in_memory_full",
            "width": int(render_w),
            "height": int(render_h),
            "source_width": int(width),
            "source_height": int(height),
            "max_size": int(max_size or 0),
            "fingerprint": digest.hexdigest(),
            "transparent_pixels_flattened_to": "#808080",
        }
        return flattened, report

    def _write_pbr_source_image(self, output_path: str | Path | None = None) -> dict:
        path = Path(output_path) if output_path else self._pbr_source_output_path()
        image, report = self._pbr_source_image()
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path, "PNG")
        self._pbr_source_path = str(path)
        report["pbr_source_path"] = str(path)
        return report

    def _open_pbr_texture_lab_window(self) -> None:
        from PySide6.QtWidgets import QMessageBox

        try:
            source = self._write_pbr_source_image()
            from app.ar_pbr.texture_map_lab_window import ArPbrTextureMapLabWindow

            previous = getattr(self, "_pbr_texture_lab_window", None)
            if previous is not None:
                try:
                    previous.close()
                except RuntimeError:
                    pass
            window = ArPbrTextureMapLabWindow(source["pbr_source_path"], self)
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            window.destroyed.connect(
                lambda *_args, target=window: self._clear_pbr_texture_lab_window_ref(target)
            )
            self._pbr_texture_lab_window = window
            window.show()
            window.raise_()
            window.activateWindow()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Painter PBR Texture Lab",
                f"Could not open PBR Texture Lab:\n\n{type(exc).__name__}: {exc}",
            )

    def _clear_pbr_texture_lab_window_ref(self, target) -> None:
        if getattr(self, "_pbr_texture_lab_window", None) is target:
            self._pbr_texture_lab_window = None

    def _pbr_preview_generated_maps(
        self,
        *,
        max_size: int = 512,
        settings: dict | None = None,
        allow_cpu: bool | None = None,
    ) -> tuple[dict, dict]:
        from app.ar_pbr.texture_map_lab import (
            generate_texture_maps_from_image,
            texture_lab_cpu_fallback_allowed,
            texture_map_settings_fingerprint,
        )

        source_image, source_report = self._pbr_source_image(max_size=max_size)
        payload_settings = self._pbr_texture_settings_payload(settings)
        cpu_allowed = texture_lab_cpu_fallback_allowed(False) if allow_cpu is None else bool(allow_cpu)
        generation_key = texture_map_settings_fingerprint(payload_settings)
        from app.painter_material_paint import material_paint_signature

        material_signature = material_paint_signature(
            self.canvas.embedded_strokes(),
            self._paint_layers,
            width=int(source_report.get("width", max_size) or max_size),
            height=int(source_report.get("height", max_size) or max_size),
            time_ms=self._time_ms,
            light_azimuth_deg=self._material_preview_light_azimuth_deg,
            light_elevation_deg=self._material_preview_light_elevation_deg,
        )
        cache_key = {
            "source": str(source_report.get("fingerprint") or ""),
            "settings": generation_key,
            "material": material_signature,
            "max_size": int(max_size),
            "allow_cpu": bool(cpu_allowed),
        }
        cached = getattr(self, "_pbr_preview_maps_cache", None)
        if isinstance(cached, dict) and cached.get("key") == cache_key:
            generated = cached["generated"]
            source_report = dict(source_report)
            source_report["cache_hit"] = True
            return generated, source_report
        generated = generate_texture_maps_from_image(
            source_image,
            payload_settings,
            max_size=max_size,
            source_path="painter://visible-document",
            allow_cpu=cpu_allowed,
        )
        from app.painter_material_paint import (
            has_material_strokes,
            merge_material_channels_into_generated,
            rasterize_material_channels,
        )

        if has_material_strokes(self.canvas.embedded_strokes(), self._paint_layers):
            channels = rasterize_material_channels(
                self.canvas.embedded_strokes(),
                self._paint_layers,
                width=int(source_report.get("width", max_size) or max_size),
                height=int(source_report.get("height", max_size) or max_size),
                time_ms=self._time_ms,
                light_azimuth_deg=self._material_preview_light_azimuth_deg,
                light_elevation_deg=self._material_preview_light_elevation_deg,
            )
            generated = merge_material_channels_into_generated(generated, channels)
            source_report["material_paint"] = dict(generated.get("material_paint") or {})
        self._pbr_preview_maps_cache = {"key": cache_key, "generated": generated}
        source_report = dict(source_report)
        source_report["cache_hit"] = False
        return generated, source_report

    def _refresh_pbr_texture_preview(self) -> None:
        try:
            combo = getattr(self, "pbr_preview_mode_combo", None)
            mode = str(combo.currentData() if combo is not None else "material")
            out = Path(tempfile.gettempdir()) / "tiger_painter_pbr" / f"painter_pbr_preview_{mode}.png"
            from app.ar_pbr.texture_map_lab import render_plane_preview_from_generated, texture_lab_cpu_fallback_allowed

            settings = self._pbr_texture_settings_payload()
            cpu_allowed = texture_lab_cpu_fallback_allowed(False)
            generated, source = self._pbr_preview_generated_maps(max_size=512, settings=settings, allow_cpu=cpu_allowed)
            payload = render_plane_preview_from_generated(
                generated,
                self._pbr_texture_settings_payload(),
                preview_mode=mode,
                output_path=out,
                width=512,
                source_path="painter://visible-document",
                allow_cpu_preview=cpu_allowed,
            )
            pixmap = QPixmap(str(payload["preview_path"]))
            label = getattr(self, "pbr_preview_label", None)
            if label is not None and not pixmap.isNull():
                self.pbr_preview_label.setPixmap(
                    pixmap.scaled(
                        self.pbr_preview_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self._pbr_preview_payload = payload
            if hasattr(self, "pbr_status_label"):
                backend = str(payload.get("backend", {}).get("active", "cpu"))
                cache = "cached" if source.get("cache_hit") else "rendered"
                self.pbr_status_label.setText(
                    f"{mode} | {payload['size'][0]} x {payload['size'][1]} | {backend} | {cache}"
                )
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
        preview_shape: str = "plane",
        width: int = 512,
        settings: dict | None = None,
        allow_cpu: bool | None = None,
    ) -> dict:
        from app.ar_pbr.texture_map_lab import render_plane_preview_from_generated, texture_lab_cpu_fallback_allowed

        payload_settings = self._pbr_texture_settings_payload(settings)
        cpu_allowed = texture_lab_cpu_fallback_allowed(False) if allow_cpu is None else bool(allow_cpu)
        generated, source = self._pbr_preview_generated_maps(
            max_size=int(width or 512),
            settings=payload_settings,
            allow_cpu=cpu_allowed,
        )
        payload = render_plane_preview_from_generated(
            generated,
            payload_settings,
            preview_mode=preview_mode,
            preview_shape=preview_shape,
            output_path=path,
            width=int(width or 512),
            source_path="painter://visible-document",
            allow_cpu_preview=cpu_allowed,
        )
        payload["painter_source"] = source
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
        allow_cpu: bool | None = None,
    ) -> dict:
        from app.ar_pbr.texture_map_lab import (
            DEFAULT_PACKED_LAYOUTS,
            DEFAULT_SEPARATE_MAPS,
            OPTIONAL_SUBSTRATE_MAPS,
            pack_texture_channels,
            packed_layout_metadata,
            texture_lab_cpu_fallback_allowed,
            texture_map_to_image,
        )

        cpu_allowed = texture_lab_cpu_fallback_allowed(False) if allow_cpu is None else bool(allow_cpu)
        generated, source = self._pbr_preview_generated_maps(
            max_size=max(self._canvas_document_size),
            settings=settings,
            allow_cpu=cpu_allowed,
        )
        out_dir = Path(output_dir).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        source_name = "painter_visible_document_source"
        default_maps = (
            tuple(name for name in DEFAULT_SEPARATE_MAPS if name != "metallic")
            + OPTIONAL_SUBSTRATE_MAPS
            if bool(generated["settings"].get("substrate_enabled", False))
            else DEFAULT_SEPARATE_MAPS
        )
        map_names = list(maps or default_maps)
        layout_names = list(
            packed_layouts
            if packed_layouts is not None
            else (DEFAULT_PACKED_LAYOUTS if packed else ())
        )
        files: dict[str, str] = {}
        for name in map_names:
            if name not in generated["maps"]:
                raise ValueError(f"unknown texture map: {name}")
            file_path = out_dir / f"{source_name}_{name}.png"
            texture_map_to_image(name, generated["maps"][name]).save(file_path)
            files[name] = str(file_path)
        packed_files: dict[str, str] = {}
        packed_meta: dict[str, object] = {}
        from PIL import Image

        for layout in layout_names:
            packed_map = np.asarray(
                pack_texture_channels(generated["maps"], layout),
                dtype=np.float32,
            )
            packed_image = Image.fromarray(
                np.uint8(np.clip(packed_map, 0.0, 1.0) * 255.0),
                mode="RGB",
            )
            file_path = out_dir / f"{source_name}_{layout}.png"
            packed_image.save(file_path)
            packed_files[layout] = str(file_path)
            packed_meta[layout] = packed_layout_metadata(layout)
        manifest = {
            "schema": "tigerstudio.painter.material_export.v1",
            "output_dir": str(out_dir),
            "size": list(generated.get("size") or []),
            "settings": dict(generated.get("settings") or {}),
            "files": files,
            "packed_files": packed_files,
            "packed_layouts": packed_meta,
            "material_paint": dict(generated.get("material_paint") or {}),
            "painter_source": source,
        }
        manifest_path = out_dir / f"{source_name}_pbr_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            **manifest,
            "manifest_path": str(manifest_path),
        }

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._move_refresh_pause_enabled = False
        self.setUpdatesEnabled(True)
        self._fit_painter_window_to_screen()
        self._sync_color_panel_layout()
        self._schedule_canvas_geometry_update()
        self._schedule_initial_inspector_scroll()
        QTimer.singleShot(0, self._enable_window_move_refresh_pause)
        if not self._bubble_items and self._bubbles:
            self._spawn_initial_bubbles()
        if not self._sticker_items and self._stickers:
            self._spawn_initial_stickers()

    def _enable_window_move_refresh_pause(self) -> None:
        self._move_refresh_pause_enabled = self.isVisible()

    def _schedule_canvas_geometry_update(self) -> None:
        self._sync_color_panel_layout()
        self._update_canvas_geometry()
        QTimer.singleShot(0, self._sync_color_panel_layout)
        QTimer.singleShot(0, self._update_canvas_geometry)
        QTimer.singleShot(0, self._update_brush_detail_preview)
        QTimer.singleShot(50, self._sync_color_panel_layout)
        QTimer.singleShot(50, self._update_canvas_geometry)
        QTimer.singleShot(50, self._update_brush_detail_preview)

    def _sync_color_panel_layout(self) -> None:
        wheel = getattr(self, "color_wheel", None)
        panel = getattr(self, "_paint_color_panel", None)
        wheel_frame = getattr(self, "_paint_color_wheel_frame", None)
        scroll = getattr(self, "_paint_inspector_controls_scroll", None)
        controls = getattr(self, "_paint_inspector_controls", None)
        if wheel is None or panel is None:
            return
        if scroll is not None and controls is not None:
            viewport_width = int(scroll.viewport().width() or 0)
            if viewport_width > 0 and controls.width() != viewport_width:
                controls.setFixedWidth(viewport_width)
        if hasattr(self, "photoshop_color_field"):
            panel.setMinimumHeight(148)
            panel.setMaximumHeight(194)
            return
        available_width = int(panel.width() or 0)
        if available_width <= 40 and scroll is not None:
            available_width = int(scroll.viewport().width() or 0)
        matrix_frame = getattr(self, "_paint_color_matrix_frame", None)
        if wheel_frame is not None and wheel_frame.isHidden():
            if matrix_frame is not None:
                matrix_frame.setMinimumHeight(56)
                matrix_frame.setMaximumHeight(78)
            panel.layout().activate()
            required_height = max(236, int(panel.layout().sizeHint().height()))
            if panel.minimumHeight() != required_height:
                panel.setMinimumHeight(required_height)
            return
        target_size = PainterColorWheel.DISPLAY_SIZE
        if available_width > 0:
            target_size = min(
                PainterColorWheel.DISPLAY_SIZE,
                max(PainterColorWheel.MIN_DISPLAY_SIZE, available_width - 72),
            )
        wheel.set_display_size(target_size)
        frame_height = int(target_size) + 16
        if wheel_frame is not None:
            wheel_frame.setMinimumHeight(frame_height)
            wheel_frame.setMaximumHeight(frame_height)
        panel.layout().activate()
        required_height = max(frame_height + 212, int(panel.layout().sizeHint().height()))
        if panel.minimumHeight() != required_height:
            panel.setMinimumHeight(required_height)

    def _schedule_initial_inspector_scroll(self) -> None:
        QTimer.singleShot(0, self._scroll_initial_inspector_to_color)
        QTimer.singleShot(50, self._scroll_initial_inspector_to_color)

    def _scroll_initial_inspector_to_color(self) -> None:
        if not bool(getattr(self, "_paint_initial_color_scroll_pending", False)):
            return
        if not bool(getattr(self, "_standalone", False)):
            self._paint_initial_color_scroll_pending = False
            return
        scroll = getattr(self, "_paint_inspector_controls_scroll", None)
        color_panel = getattr(self, "_paint_color_panel", None)
        if scroll is None or color_panel is None:
            return
        bar = scroll.verticalScrollBar()
        if bar is None:
            return
        target = int(color_panel.y())
        bar.setValue(max(0, min(target, int(bar.maximum()))))
        self._paint_initial_color_scroll_pending = False

    def _build_brush_detail_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("PaintBrushDetailPanel")
        panel.setMinimumHeight(470)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        tab_row = QHBoxLayout()
        tab_row.setContentsMargins(1, 0, 1, 2)
        title = QLabel("Brush Selector")
        title.setObjectName("PaintBrushPanelTitle")
        tab_row.addWidget(title)
        tab_row.addStretch(1)
        self._brush_presets_tab_btn = QPushButton()
        self._brush_presets_tab_btn.setObjectName("PaintBrushViewTool")
        self._brush_presets_tab_btn.setIcon(app_icon("list", size=13, color="#E2E2E2"))
        self._brush_presets_tab_btn.setIconSize(QSize(13, 13))
        self._brush_presets_tab_btn.setFixedSize(24, 22)
        self._brush_presets_tab_btn.setCheckable(True)
        self._brush_presets_tab_btn.setChecked(True)
        self._brush_presets_tab_btn.setToolTip("Brush Selector")
        self._brush_settings_tab_btn = QPushButton()
        self._brush_settings_tab_btn.setObjectName("PaintBrushViewTool")
        self._brush_settings_tab_btn.setIcon(app_icon("sliders", size=13, color="#E2E2E2"))
        self._brush_settings_tab_btn.setIconSize(QSize(13, 13))
        self._brush_settings_tab_btn.setFixedSize(24, 22)
        self._brush_settings_tab_btn.setCheckable(True)
        self._brush_settings_tab_btn.setChecked(False)
        self._brush_settings_tab_btn.setToolTip("Advanced Brush Controls")
        self._brush_settings_tab_btn.clicked.connect(lambda: self._set_brush_tab("settings"))
        self._brush_presets_tab_btn.clicked.connect(lambda: self._set_brush_tab("presets"))
        tab_row.addWidget(self._brush_presets_tab_btn)
        tab_row.addWidget(self._brush_settings_tab_btn)
        layout.addLayout(tab_row)

        self._brush_panel_stack = QStackedWidget(panel)
        self._brush_panel_stack.setObjectName("PaintBrushPanelStack")
        layout.addWidget(self._brush_panel_stack)

        controls_page = QWidget(self._brush_panel_stack)
        body_row = QHBoxLayout()
        controls_page.setLayout(body_row)
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(6)
        category_frame = QFrame(controls_page)
        category_frame.setObjectName("PaintBrushControlCategories")
        category_frame.setFixedWidth(106)
        category_layout = QVBoxLayout(category_frame)
        category_layout.setContentsMargins(0, 0, 0, 0)
        category_layout.setSpacing(2)
        self._brush_detail_category_buttons: dict[str, QPushButton] = {}
        for name in BRUSH_DETAIL_SECTIONS:
            button = QPushButton(name)
            button.setObjectName("PaintBrushCategory")
            button.setCheckable(True)
            button.setChecked(name in {"Brush Tip Shape", "Smoothing"})
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            if name not in BRUSH_DETAIL_ACTIVE_SECTIONS:
                button.setEnabled(False)
                button.setToolTip("Reserved for the next brush-engine pass")
            else:
                button.setToolTip(f"Toggle {name}")
            button.clicked.connect(
                lambda checked=False, section=name: self._set_brush_detail_section(section, bool(checked))
            )
            category_layout.addWidget(button)
            self._brush_detail_category_buttons[name] = button
        category_layout.addStretch(1)
        body_row.addWidget(category_frame, 0)

        control_frame = QFrame(controls_page)
        control_frame.setObjectName("PaintBrushControlValues")
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(4)

        style_row = QHBoxLayout()
        style_row.setContentsMargins(0, 0, 0, 0)
        style_label = QLabel("Style")
        style_label.setObjectName("PaintColorLabel")
        self.brush_style_combo = QComboBox()
        for label, style_id in (
            ("Round", "round"),
            ("Marker", "marker"),
            ("Highlighter", "highlighter"),
            ("Dashed", "dashed"),
            ("Loaded Oil", "loaded_oil"),
            ("Impasto Oil", "impasto_oil"),
            ("Oil Smear", "oil_smear"),
            ("Soft Oil Glaze", "soft_oil_glaze"),
            ("Real Wet Oil", "real_wet_oil"),
            ("Bristle Oil", "bristle_oil"),
            ("Dry Oil", "dry_oil"),
            ("Palette Knife", "palette_knife"),
            ("Filbert Oil", "filbert_oil"),
            ("Flat Hog Oil", "flat_hog_oil"),
            ("Fan Bristle Oil", "fan_bristle_oil"),
            ("Rigger Oil", "rigger_oil"),
            ("Scumble Oil", "scumble_oil"),
            ("Stipple Oil", "stipple_oil"),
            ("Knife Scrape Oil", "knife_scrape_oil"),
            ("Textured Chalk", "textured_chalk"),
        ):
            self.brush_style_combo.addItem(label, style_id)
        existing_styles = {
            str(self.brush_style_combo.itemData(index))
            for index in range(self.brush_style_combo.count())
        }
        for style_id in sorted(DESIGNER_BRUSH_STYLE_IDS):
            if style_id not in existing_styles:
                self.brush_style_combo.addItem(style_id.replace("_", " ").title(), style_id)
        self.brush_style_combo.currentIndexChanged.connect(self._on_brush_style_changed)
        style_row.addWidget(style_label)
        style_row.addWidget(self.brush_style_combo, stretch=1)
        control_layout.addLayout(style_row)

        self._brush_detail_value_labels: dict[str, QLabel] = {}
        self._brush_detail_sliders: dict[str, QSlider] = {}

        def add_slider(label: str, key: str, minimum: int, maximum: int, value: int, suffix: str) -> StudioSlider:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            name_label = QLabel(label)
            name_label.setObjectName("PaintColorLabel")
            name_label.setFixedWidth(68)
            value_label = QLabel(f"{value}{suffix}")
            value_label.setObjectName("PaintValue")
            value_label.setFixedWidth(62)
            row.addWidget(name_label)
            row.addWidget(value_label)
            control_layout.addLayout(row)
            slider = StudioSlider("accent")
            slider.setRange(minimum, maximum)
            slider.setValue(value)
            control_layout.addWidget(slider)
            self._brush_detail_value_labels[key] = value_label
            self._brush_detail_sliders[key] = slider
            return slider

        self.width_slider = add_slider("Size", "size", 1, 60, int(self._pen_width), " px")
        self.width_slider.valueChanged.connect(self._on_width_changed)
        self.opacity_slider = add_slider(
            "Opacity",
            "opacity",
            10,
            100,
            int(round(self._pen_opacity * 100 / 255)),
            "%",
        )
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        self.brush_hardness_slider = add_slider(
            "Hardness",
            "hardness",
            1,
            100,
            int(self._brush_detail_settings["hardness"]),
            "%",
        )
        self.brush_spacing_slider = add_slider(
            "Spacing",
            "spacing",
            1,
            200,
            int(self._brush_detail_settings["spacing"]),
            "%",
        )
        self.brush_angle_slider = add_slider(
            "Angle",
            "angle",
            -180,
            180,
            int(self._brush_detail_settings["angle"]),
            " deg",
        )
        self.brush_roundness_slider = add_slider(
            "Roundness",
            "roundness",
            10,
            100,
            int(self._brush_detail_settings["roundness"]),
            "%",
        )
        for key, slider in (
            ("hardness", self.brush_hardness_slider),
            ("spacing", self.brush_spacing_slider),
            ("angle", self.brush_angle_slider),
            ("roundness", self.brush_roundness_slider),
        ):
            slider.valueChanged.connect(
                lambda value, setting=key: self._set_brush_detail_value(setting, int(value))
            )

        flip_row = QHBoxLayout()
        flip_row.setContentsMargins(0, 0, 0, 0)
        self.brush_flip_x_btn = QPushButton("Flip X")
        self.brush_flip_x_btn.setObjectName("PaintBrushTinyButton")
        self.brush_flip_x_btn.setCheckable(True)
        self.brush_flip_x_btn.clicked.connect(
            lambda checked=False: self._set_brush_detail_toggle("flip_x", bool(checked))
        )
        self.brush_flip_y_btn = QPushButton("Flip Y")
        self.brush_flip_y_btn.setObjectName("PaintBrushTinyButton")
        self.brush_flip_y_btn.setCheckable(True)
        self.brush_flip_y_btn.clicked.connect(
            lambda checked=False: self._set_brush_detail_toggle("flip_y", bool(checked))
        )
        flip_row.addWidget(self.brush_flip_x_btn)
        flip_row.addWidget(self.brush_flip_y_btn)
        flip_row.addStretch(1)
        control_layout.addLayout(flip_row)

        self._brush_detail_preview = QLabel()
        self._brush_detail_preview.setObjectName("PaintBrushPreview")
        self._brush_detail_preview.setMinimumHeight(82)
        self._brush_detail_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        control_layout.addWidget(self._brush_detail_preview)

        body_row.addWidget(control_frame, stretch=1)
        self._brush_panel_stack.addWidget(controls_page)

        library_page = QWidget(self._brush_panel_stack)
        library_layout = QVBoxLayout(library_page)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(4)

        library_header = QHBoxLayout()
        library_header.setContentsMargins(0, 0, 0, 0)
        self._brush_library_selector = QComboBox(library_page)
        self._brush_library_selector.setObjectName("PaintBrushLibrarySelector")
        self._brush_library_selector.addItem("Tiger Studio Brushes", "tiger_studio")
        self._brush_library_selector.setToolTip("Active brush library")
        library_header.addWidget(self._brush_library_selector, stretch=1)
        self._brush_favorite_btn = QPushButton("☆")
        self._brush_favorite_btn.setObjectName("PaintBrushLibraryTool")
        self._brush_favorite_btn.setText("")
        self._brush_favorite_btn.setCheckable(True)
        self._brush_favorite_btn.setIcon(app_icon("favorite", size=13, color="#D9D9D9"))
        self._brush_favorite_btn.setIconSize(QSize(13, 13))
        self._brush_favorite_btn.setFixedSize(24, 22)
        self._brush_favorite_btn.setToolTip("Mark selected brush as favorite")
        self._brush_favorite_btn.clicked.connect(self._toggle_active_brush_favorite)
        library_header.addWidget(self._brush_favorite_btn)
        self._brush_filter_btn = QPushButton()
        self._brush_filter_btn.setObjectName("PaintBrushLibraryTool")
        self._brush_filter_btn.setIcon(app_icon("filter", size=13, color="#D9D9D9"))
        self._brush_filter_btn.setIconSize(QSize(13, 13))
        self._brush_filter_btn.setFixedSize(24, 22)
        self._brush_filter_btn.setToolTip("Filter brushes")
        self._brush_filter_menu = QMenu(self._brush_filter_btn)
        self._brush_filter_actions = {}
        for label, value in (
            ("My Favorites", "favorites"),
            ("Painter Masters", "masters"),
            ("Stamps", "stamps"),
            ("Watercolor Compatible", "watercolor"),
            ("Thick Paint Compatible", "thick_paint"),
        ):
            action = self._brush_filter_menu.addAction(label)
            action.setCheckable(True)
            action.toggled.connect(
                lambda checked=False, filter_id=value: self._set_brush_filter_enabled(
                    filter_id, bool(checked)
                )
            )
            self._brush_filter_actions[value] = action
        self._brush_filter_btn.setMenu(self._brush_filter_menu)
        library_header.addWidget(self._brush_filter_btn)
        self._brush_compact_btn = QPushButton()
        self._brush_compact_btn.setObjectName("PaintBrushLibraryTool")
        self._brush_compact_btn.setIcon(app_icon("grid", size=13, color="#D9D9D9"))
        self._brush_compact_btn.setIconSize(QSize(13, 13))
        self._brush_compact_btn.setFixedSize(24, 22)
        self._brush_compact_btn.setCheckable(True)
        self._brush_compact_btn.setToolTip("Compact Brush Selector")
        self._brush_compact_btn.toggled.connect(self._set_brush_selector_compact)
        library_header.addWidget(self._brush_compact_btn)
        library_layout.addLayout(library_header)

        self._brush_search_edit = QLineEdit(library_page)
        self._brush_search_edit.setObjectName("PaintBrushSearch")
        self._brush_search_edit.setPlaceholderText("Search brushes")
        self._brush_search_edit.setClearButtonEnabled(True)
        self._brush_search_edit.textChanged.connect(
            lambda _text: self._populate_brush_library()
        )
        library_layout.addWidget(self._brush_search_edit)

        self._brush_recent_label = QLabel("RECENT")
        self._brush_recent_label.setObjectName("PaintColorLabel")
        self._brush_recent_label.hide()
        library_layout.addWidget(self._brush_recent_label)
        self._brush_recent_list = QListWidget(library_page)
        self._brush_recent_list.setObjectName("PaintBrushRecentList")
        self._brush_recent_list.setViewMode(QListView.ViewMode.IconMode)
        self._brush_recent_list.setFlow(QListView.Flow.LeftToRight)
        self._brush_recent_list.setWrapping(False)
        self._brush_recent_list.setMovement(QListView.Movement.Static)
        self._brush_recent_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._brush_recent_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._brush_recent_list.setIconSize(BRUSH_PRESET_ICON_SIZE)
        self._brush_recent_list.setGridSize(BRUSH_PANEL_PRESET_CELL_SIZE)
        self._brush_recent_list.setFixedHeight(BRUSH_PANEL_PRESET_CELL_SIZE.height() + 8)
        self._brush_recent_list.itemClicked.connect(self._on_brush_library_item)
        self._brush_recent_list.hide()
        library_layout.addWidget(self._brush_recent_list)

        selector_body = QHBoxLayout()
        selector_body.setContentsMargins(0, 0, 0, 0)
        selector_body.setSpacing(4)
        self._brush_category_list = QListWidget(library_page)
        self._brush_category_list.setObjectName("PaintBrushCategoryList")
        self._brush_category_list.setFixedWidth(96)
        all_item = QListWidgetItem("All Brushes")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        self._brush_category_list.addItem(all_item)
        for category in sorted(
            {str(row.get("category") or "Brushes") for row in BRUSH_LIBRARY_PRESETS}
        ):
            item = QListWidgetItem(category)
            item.setData(Qt.ItemDataRole.UserRole, category)
            self._brush_category_list.addItem(item)
        self._brush_category_list.setCurrentRow(0)
        self._brush_category_list.currentItemChanged.connect(
            lambda _current, _previous: self._populate_brush_library()
        )
        selector_body.addWidget(self._brush_category_list)

        self.brush_library_list = QListWidget(library_page)
        self.brush_library_list.setObjectName("PaintBrushList")
        self.brush_library_list.setViewMode(QListView.ViewMode.ListMode)
        self.brush_library_list.setMovement(QListView.Movement.Static)
        self.brush_library_list.setResizeMode(QListView.ResizeMode.Fixed)
        self.brush_library_list.setFlow(QListView.Flow.TopToBottom)
        self.brush_library_list.setWrapping(False)
        self.brush_library_list.setUniformItemSizes(True)
        self.brush_library_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.brush_library_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.brush_library_list.setIconSize(BRUSH_PRESET_ICON_SIZE)
        self.brush_library_list.setMinimumHeight(150)
        self.brush_library_list.itemClicked.connect(self._on_brush_library_item)
        self.brush_library_list.currentItemChanged.connect(self._on_brush_library_current_item)
        selector_body.addWidget(self.brush_library_list, stretch=1)
        library_layout.addLayout(selector_body, stretch=1)

        self._brush_library_preview = QLabel(library_page)
        self._brush_library_preview.setObjectName("PaintBrushPreview")
        self._brush_library_preview.setMinimumHeight(46)
        self._brush_library_preview.setMaximumHeight(50)
        self._brush_library_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        library_layout.addWidget(self._brush_library_preview)
        self._brush_compatibility_label = QLabel(library_page)
        self._brush_compatibility_label.setObjectName("PaintBrushMeta")
        self._brush_compatibility_label.setText("Default Layer")
        library_layout.addWidget(self._brush_compatibility_label)

        self._brush_panel_stack.addWidget(library_page)
        self._brush_controls_page = controls_page
        self._brush_library_page = library_page
        self._brush_panel_stack.setCurrentWidget(library_page)
        self._populate_brush_library()
        self._populate_brush_recent_list()
        self._sync_brush_detail_controls()
        return panel

    def _set_brush_tab(self, tab: str) -> None:
        show_presets = tab == "presets"
        if hasattr(self, "_brush_settings_tab_btn"):
            self._brush_settings_tab_btn.setChecked(not show_presets)
        if hasattr(self, "_brush_presets_tab_btn"):
            self._brush_presets_tab_btn.setChecked(show_presets)
        stack = getattr(self, "_brush_panel_stack", None)
        if stack is not None:
            stack.setCurrentWidget(
                self._brush_library_page if show_presets else self._brush_controls_page
            )
        if show_presets and hasattr(self, "brush_library_list"):
            self.brush_library_list.setFocus()
        elif hasattr(self, "brush_style_combo"):
            self.brush_style_combo.setFocus()

    def _set_brush_detail_section(self, section: str, checked: bool) -> None:
        if section == "Brush Tip Shape" and not checked:
            button = getattr(self, "_brush_detail_category_buttons", {}).get(section)
            if button is not None:
                button.blockSignals(True)
                button.setChecked(True)
                button.blockSignals(False)
            return
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"Brush section: {section}")

    def _format_brush_detail_value(self, key: str, value: int | bool) -> str:
        if key == "angle":
            return f"{int(value)} deg"
        if key == "size":
            return f"{int(value)} px"
        if key == "opacity":
            return f"{int(value)}%"
        if key in {"hardness", "spacing", "roundness"}:
            return f"{int(value)}%"
        return str(value)

    def _canvas_brush_detail_payload(self) -> dict[str, int | bool]:
        return {
            "hardness": int(self._brush_detail_settings.get("hardness", 100)),
            "spacing": int(self._brush_detail_settings.get("spacing", 25)),
            "angle": int(self._brush_detail_settings.get("angle", 0)),
            "roundness": int(self._brush_detail_settings.get("roundness", 100)),
            "flip_x": bool(self._brush_detail_settings.get("flip_x", False)),
            "flip_y": bool(self._brush_detail_settings.get("flip_y", False)),
        }

    def _set_brush_detail_value(self, key: str, value: int) -> None:
        ranges = {
            "hardness": (1, 100),
            "spacing": (1, 200),
            "angle": (-180, 180),
            "roundness": (10, 100),
        }
        if key not in ranges:
            return
        minimum, maximum = ranges[key]
        clamped = max(minimum, min(maximum, int(value)))
        self._brush_detail_settings[key] = clamped
        label = getattr(self, "_brush_detail_value_labels", {}).get(key)
        if label is not None:
            label.setText(self._format_brush_detail_value(key, clamped))
        if hasattr(self, "canvas"):
            self.canvas.set_brush_detail(**self._canvas_brush_detail_payload())
        if not bool(getattr(self, "_brush_detail_syncing", False)):
            self._update_brush_detail_preview()

    def _set_brush_detail_toggle(self, key: str, enabled: bool) -> None:
        if key not in {"flip_x", "flip_y"}:
            return
        self._brush_detail_settings[key] = bool(enabled)
        button = getattr(self, "brush_flip_x_btn" if key == "flip_x" else "brush_flip_y_btn", None)
        if button is not None and button.isChecked() != bool(enabled):
            button.blockSignals(True)
            button.setChecked(bool(enabled))
            button.blockSignals(False)
        if hasattr(self, "canvas"):
            self.canvas.set_brush_detail(**self._canvas_brush_detail_payload())
        if not bool(getattr(self, "_brush_detail_syncing", False)):
            self._update_brush_detail_preview()

    def _sync_brush_detail_controls(self) -> None:
        if not hasattr(self, "_brush_detail_value_labels"):
            return
        self._brush_detail_syncing = True
        try:
            if hasattr(self, "width_slider"):
                self.width_slider.blockSignals(True)
                self.width_slider.setValue(max(1, min(60, int(round(self._pen_width)))))
                self.width_slider.blockSignals(False)
            if hasattr(self, "opacity_slider"):
                self.opacity_slider.blockSignals(True)
                self.opacity_slider.setValue(max(10, min(100, int(round(self._pen_opacity * 100 / 255)))))
                self.opacity_slider.blockSignals(False)
            if hasattr(self, "brush_style_combo"):
                self.brush_style_combo.blockSignals(True)
                index = self.brush_style_combo.findData(_normalize_paint_brush_style(self._pen_style))
                if index >= 0:
                    self.brush_style_combo.setCurrentIndex(index)
                self.brush_style_combo.blockSignals(False)
            for key in ("hardness", "spacing", "angle", "roundness"):
                slider = getattr(self, "_brush_detail_sliders", {}).get(key)
                value = int(self._brush_detail_settings.get(key, BRUSH_DETAIL_DEFAULTS[key]))
                if slider is not None:
                    slider.blockSignals(True)
                    slider.setValue(value)
                    slider.blockSignals(False)
                label = self._brush_detail_value_labels.get(key)
                if label is not None:
                    label.setText(self._format_brush_detail_value(key, value))
            for key in ("size", "opacity"):
                label = self._brush_detail_value_labels.get(key)
                if label is not None:
                    value = int(round(self._pen_width)) if key == "size" else int(round(self._pen_opacity * 100 / 255))
                    label.setText(self._format_brush_detail_value(key, value))
            self._set_brush_detail_toggle("flip_x", bool(self._brush_detail_settings.get("flip_x", False)))
            self._set_brush_detail_toggle("flip_y", bool(self._brush_detail_settings.get("flip_y", False)))
        finally:
            self._brush_detail_syncing = False
        self._update_brush_detail_preview()

    def _update_brush_detail_preview(self) -> None:
        label = getattr(self, "_brush_detail_preview", None)
        if label is None:
            return
        width = max(260, int(label.width() or 300))
        height = max(82, int(label.height() or 82))
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#505050"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            painter.fillRect(QRectF(0, 0, width, height), QColor("#505050"))
            painter.setPen(QPen(QColor(255, 255, 255, 22), 1))
            painter.drawRect(QRectF(0.5, 0.5, width - 1, height - 1))
            preview_color = QColor("#FFFFFF")
            stroke = Stroke(
                points=[
                    (0.07, 0.64),
                    (0.23, 0.38),
                    (0.42, 0.48),
                    (0.62, 0.66),
                    (0.82, 0.54),
                    (0.94, 0.40),
                ],
                color=(preview_color.red(), preview_color.green(), preview_color.blue()),
                opacity=max(1, min(255, int(self._pen_opacity))),
                width_px=max(1.0, min(48.0, float(self._pen_width))),
                brush_style=_normalize_paint_brush_style(self._pen_style),
                brush_hardness=int(self._brush_detail_settings.get("hardness", 100)),
                brush_spacing=int(self._brush_detail_settings.get("spacing", 25)),
                brush_angle=int(self._brush_detail_settings.get("angle", 0)),
                brush_roundness=int(self._brush_detail_settings.get("roundness", 100)),
                brush_flip_x=bool(self._brush_detail_settings.get("flip_x", False)),
                brush_flip_y=bool(self._brush_detail_settings.get("flip_y", False)),
            )
            DrawingCanvas._paint_stroke(painter, stroke, width, height)

            roundness = max(10, min(100, int(self._brush_detail_settings.get("roundness", 100))))
            angle = int(self._brush_detail_settings.get("angle", 0))
            hardness = max(1, min(100, int(self._brush_detail_settings.get("hardness", 100))))
            painter.save()
            painter.translate(QPointF(width - 44, height - 28))
            painter.rotate(angle)
            painter.setPen(QPen(QColor(255, 255, 255, 90), 1.2))
            fill = QColor(255, 255, 255, 45 + int(hardness * 1.45))
            painter.setBrush(fill)
            painter.drawEllipse(QRectF(-18, -18 * roundness / 100.0, 36, 36 * roundness / 100.0))
            painter.restore()
        finally:
            painter.end()
        label.setPixmap(pixmap)

    @staticmethod
    def _brush_preset_key(preset: dict[str, object]) -> str:
        return f"{preset.get('category', '')}::{preset.get('name', '')}::{preset.get('style', '')}"

    def _brush_preset_icon(
        self,
        preset: dict[str, object],
        *,
        favorite: bool = False,
    ) -> QIcon:
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
                "Oils": "#FF9A3D",
                "Pencil & Ink": "#DCE6F7",
                "Flow Map": "#6FA8C8",
                "Texture": "#A8D86F",
                "Markers": "#82A5FF",
                "Utility": "#C7A46A",
            }
            color = QColor(hue_colors.get(str(preset.get("category") or ""), "#90A9D6"))
            color.setAlpha(opacity)
            stroke = Stroke(
                points=[
                    (9 / 76, 24 / 36),
                    (19 / 76, 10 / 36),
                    (33 / 76, 27 / 36),
                    (47 / 76, 15 / 36),
                    (58 / 76, 8 / 36),
                    (68 / 76, 13 / 36),
                ],
                color=(color.red(), color.green(), color.blue()),
                opacity=color.alpha(),
                width_px=width,
                brush_style=style,
                brush_hardness=int(preset.get("hardness") or 100),
                brush_spacing=int(preset.get("spacing") or 25),
                brush_angle=int(preset.get("angle") or 0),
                brush_roundness=int(preset.get("roundness") or 100),
            )
            DrawingCanvas._paint_stroke(painter, stroke, 76, 36)
            painter.setPen(QPen(QColor(255, 255, 255, 44), 1.0))
            if style == "highlighter":
                painter.drawLine(QPointF(11, 28), QPointF(66, 28))
            elif style == "marker":
                painter.drawLine(QPointF(12, 8), QPointF(67, 8))
            elif style in PAINT_TEXTURED_BRUSH_STYLES:
                painter.drawLine(QPointF(12, 30), QPointF(67, 30))
            if favorite:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#F2B84B"))
                painter.drawEllipse(QPointF(69, 7), 3.0, 3.0)
        finally:
            painter.end()
        return QIcon(pixmap)

    def _brush_preset_matches_filter(
        self,
        preset: dict[str, object],
        filter_id: str,
    ) -> bool:
        if not filter_id:
            return True
        category = str(preset.get("category") or "")
        style = str(preset.get("style") or "")
        if filter_id == "favorites":
            return self._brush_preset_key(preset) in self._brush_favorites
        if filter_id == "masters":
            return category in {
                "Drawing",
                "Ink",
                "Oils",
                "Pro Oils",
                "Water Media",
            }
        if filter_id == "watercolor":
            return category == "Water Media" or "watercolor" in style
        if filter_id == "thick_paint":
            return category in {"Oils", "Pro Oils"} or style in {
                "gouache_flat",
                "acrylic_bristle",
            }
        if filter_id == "stamps":
            return style in {
                "pixel_square",
                "stipple_oil",
                "foliage_scatter",
                "paint_splatter",
                "rock_ground",
                "fabric_grunge",
                "textured_chalk",
            }
        return True

    def _set_brush_filter_enabled(self, filter_id: str, enabled: bool) -> None:
        filter_key = str(filter_id or "").strip().casefold()
        if not filter_key:
            return
        if enabled:
            self._brush_active_filters.add(filter_key)
        else:
            self._brush_active_filters.discard(filter_key)
        button = getattr(self, "_brush_filter_btn", None)
        if button is not None:
            button.setProperty("activeFilters", bool(self._brush_active_filters))
            button.style().unpolish(button)
            button.style().polish(button)
            button.setToolTip(
                "Filters: " + ", ".join(sorted(self._brush_active_filters))
                if self._brush_active_filters
                else "Filter brushes"
            )
        self._populate_brush_library()

    def _set_brush_filters(self, filters: list[str] | tuple[str, ...] | set[str]) -> None:
        supported = set(getattr(self, "_brush_filter_actions", {}))
        requested = {
            str(value or "").strip().casefold()
            for value in filters
            if str(value or "").strip()
        }
        unknown = requested - supported
        if unknown:
            raise ValueError(f"Painter brush filter not found: {sorted(unknown)[0]}")
        self._brush_active_filters = requested
        for filter_id, action in getattr(self, "_brush_filter_actions", {}).items():
            action.blockSignals(True)
            action.setChecked(filter_id in requested)
            action.blockSignals(False)
        button = getattr(self, "_brush_filter_btn", None)
        if button is not None:
            button.setProperty("activeFilters", bool(requested))
            button.style().unpolish(button)
            button.style().polish(button)
        self._populate_brush_library()

    def _set_brush_selector_compact(self, compact: bool) -> None:
        self._brush_selector_compact = bool(compact)
        for widget_name in (
            "_brush_library_selector",
            "_brush_category_list",
            "_brush_recent_label",
            "_brush_recent_list",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setVisible(
                    not self._brush_selector_compact
                    and (
                        widget_name not in {"_brush_recent_label", "_brush_recent_list"}
                        or bool(self._brush_recent_indices)
                    )
                )
        button = getattr(self, "_brush_compact_btn", None)
        if button is not None:
            button.setToolTip(
                "Full Brush Selector"
                if self._brush_selector_compact
                else "Compact Brush Selector"
            )

    def _populate_brush_library(self) -> None:
        if not hasattr(self, "brush_library_list"):
            return
        selected_category = ""
        category_list = getattr(self, "_brush_category_list", None)
        if category_list is not None and category_list.currentItem() is not None:
            selected_category = str(
                category_list.currentItem().data(Qt.ItemDataRole.UserRole) or ""
            )
        search_text = str(
            getattr(self, "_brush_search_edit", None).text()
            if getattr(self, "_brush_search_edit", None) is not None
            else ""
        ).strip().casefold()
        active_filters = set(getattr(self, "_brush_active_filters", set()))
        previous_index = self._active_brush_preset_index
        self.brush_library_list.clear()
        for idx, preset in enumerate(BRUSH_LIBRARY_PRESETS):
            category = str(preset["category"])
            if selected_category and category != selected_category:
                continue
            if search_text:
                haystack = " ".join(
                    (
                        category,
                        str(preset.get("name") or ""),
                        str(preset.get("style") or ""),
                    )
                ).casefold()
                if search_text not in haystack:
                    continue
            if not all(
                self._brush_preset_matches_filter(preset, filter_id)
                for filter_id in active_filters
            ):
                continue
            name = str(preset["name"])
            width = int(preset["width"])
            opacity = int(preset["opacity"])
            favorite = self._brush_preset_key(preset) in self._brush_favorites
            item = QListWidgetItem(
                self._brush_preset_icon(preset, favorite=favorite),
                name,
            )
            item.setToolTip(f"{category} | {name} | {width}px / {opacity}%")
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setSizeHint(QSize(0, 36))
            self.brush_library_list.addItem(item)
        if self.brush_library_list.count() > 0:
            selected_row = 0
            for row in range(self.brush_library_list.count()):
                item = self.brush_library_list.item(row)
                if int(item.data(Qt.ItemDataRole.UserRole)) == previous_index:
                    selected_row = row
                    break
            self.brush_library_list.setCurrentRow(selected_row)
            self._on_brush_library_current_item(
                self.brush_library_list.currentItem(),
                None,
            )
        else:
            self._update_brush_library_preview(None)

    def _populate_brush_recent_list(self) -> None:
        recent_list = getattr(self, "_brush_recent_list", None)
        if recent_list is None:
            return
        recent_list.clear()
        for idx in self._brush_recent_indices[:8]:
            if not (0 <= idx < len(BRUSH_LIBRARY_PRESETS)):
                continue
            preset = BRUSH_LIBRARY_PRESETS[idx]
            favorite = self._brush_preset_key(preset) in self._brush_favorites
            item = QListWidgetItem(
                self._brush_preset_icon(preset, favorite=favorite),
                "",
            )
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setToolTip(f"Recent | {preset.get('name', 'Brush')}")
            item.setSizeHint(BRUSH_PANEL_PRESET_CELL_SIZE)
            recent_list.addItem(item)
        visible = bool(recent_list.count()) and not bool(
            getattr(self, "_brush_selector_compact", False)
        )
        recent_list.setVisible(visible)
        recent_label = getattr(self, "_brush_recent_label", None)
        if recent_label is not None:
            recent_label.setVisible(visible)

    def _on_brush_library_current_item(
        self,
        item: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if item is None:
            self._update_brush_library_preview(None)
            return
        try:
            idx = int(item.data(Qt.ItemDataRole.UserRole))
            preset = BRUSH_LIBRARY_PRESETS[idx]
        except Exception:
            self._update_brush_library_preview(None)
            return
        self._active_brush_preset_index = idx
        self._update_brush_favorite_button()
        self._update_brush_library_preview(preset)

    def _update_brush_favorite_button(self) -> None:
        button = getattr(self, "_brush_favorite_btn", None)
        if button is None:
            return
        try:
            preset = BRUSH_LIBRARY_PRESETS[self._active_brush_preset_index]
        except Exception:
            button.setChecked(False)
            return
        favorite = self._brush_preset_key(preset) in self._brush_favorites
        button.setText("")
        button.setChecked(favorite)
        button.setIcon(
            app_icon(
                "favorite",
                size=13,
                color="#F0C66A" if favorite else "#D9D9D9",
            )
        )
        button.setToolTip(
            "Remove selected brush from favorites"
            if favorite
            else "Mark selected brush as favorite"
        )

    def _toggle_active_brush_favorite(self) -> None:
        try:
            preset = BRUSH_LIBRARY_PRESETS[self._active_brush_preset_index]
        except Exception:
            return
        key = self._brush_preset_key(preset)
        if key in self._brush_favorites:
            self._brush_favorites.remove(key)
        else:
            self._brush_favorites.add(key)
        self._update_brush_favorite_button()
        self._populate_brush_library()
        self._populate_brush_recent_list()

    def _update_brush_library_preview(
        self,
        preset: dict[str, object] | None,
    ) -> None:
        label = getattr(self, "_brush_library_preview", None)
        if label is None:
            return
        width = max(220, int(label.width() or 260))
        height = max(46, int(label.height() or 46))
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#303236"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            if preset is None:
                painter.setPen(QColor("#B8B8B8"))
                painter.drawText(QRectF(8, 8, width - 16, height - 16), "No brushes match")
            else:
                color = QColor("#F2F2F2")
                stroke = Stroke(
                    points=[
                        (0.06, 0.68),
                        (0.24, 0.34),
                        (0.45, 0.60),
                        (0.66, 0.30),
                        (0.92, 0.54),
                    ],
                    color=(color.red(), color.green(), color.blue()),
                    opacity=max(
                        1,
                        min(255, int(float(preset.get("opacity") or 100) * 2.55)),
                    ),
                    width_px=max(2.0, min(34.0, float(preset.get("width") or 8))),
                    brush_style=str(preset.get("style") or "round"),
                    brush_hardness=int(preset.get("hardness") or 100),
                    brush_spacing=int(preset.get("spacing") or 25),
                    brush_angle=int(preset.get("angle") or 0),
                    brush_roundness=int(preset.get("roundness") or 100),
                )
                DrawingCanvas._paint_stroke(painter, stroke, width, height)
                painter.setPen(QColor(255, 255, 255, 185))
                painter.drawText(QPointF(8, 15), str(preset.get("name") or "Brush"))
        finally:
            painter.end()
        label.setPixmap(pixmap)
        compatibility = getattr(self, "_brush_compatibility_label", None)
        if compatibility is not None:
            if preset is None:
                compatibility.setText("No compatible brush")
            else:
                category = str(preset.get("category") or "")
                style = str(preset.get("style") or "")
                modes = ["Default Layer"]
                if category == "Water Media" or "watercolor" in style:
                    modes.append("Watercolor Layer")
                if self._brush_preset_matches_filter(preset, "thick_paint"):
                    modes.append("Thick Paint Layer")
                compatibility.setText("  |  ".join(modes))

    def _on_brush_library_item(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.ItemDataRole.UserRole)
        try:
            preset = BRUSH_LIBRARY_PRESETS[int(idx)]
        except Exception:
            return
        self._active_brush_preset_index = int(idx)
        self._apply_brush_library_preset(preset)

    def _apply_brush_library_preset(self, preset: dict[str, object]) -> None:
        try:
            preset_index = BRUSH_LIBRARY_PRESETS.index(preset)
        except ValueError:
            preset_index = self._active_brush_preset_index
        self._active_brush_preset_index = preset_index
        if preset_index in self._brush_recent_indices:
            self._brush_recent_indices.remove(preset_index)
        self._brush_recent_indices.insert(0, preset_index)
        del self._brush_recent_indices[8:]
        style = _normalize_paint_brush_style(str(preset.get("style") or "round"))
        width = int(preset.get("width") or self._pen_width)
        opacity = int(preset.get("opacity") or 100)
        clamped_width = max(1, min(60, width))
        clamped_opacity = max(10, min(100, opacity))
        self._pen_width = float(clamped_width)
        self._pen_opacity = int(clamped_opacity * 255 / 100)
        self._pen_style = style
        for key in ("hardness", "spacing", "angle", "roundness"):
            if key in preset:
                self._brush_detail_settings[key] = int(preset[key])
        for key in ("flip_x", "flip_y"):
            if key in preset:
                self._brush_detail_settings[key] = bool(preset[key])
        if hasattr(self, "canvas"):
            self.canvas.set_pen_style(style)
            self.canvas.set_pen_width(self._pen_width)
            self.canvas.set_pen_opacity(self._pen_opacity)
            self.canvas.set_brush_detail(**self._canvas_brush_detail_payload())
        if hasattr(self, "brush_style_combo"):
            index = self.brush_style_combo.findData(style)
            if index >= 0:
                self.brush_style_combo.setCurrentIndex(index)
        if hasattr(self, "width_slider"):
            self.width_slider.setValue(clamped_width)
        if hasattr(self, "opacity_slider"):
            self.opacity_slider.setValue(clamped_opacity)
        if hasattr(self, "_width_value_label"):
            self._width_value_label.setText(f"{clamped_width} px")
        if hasattr(self, "_opacity_value_label"):
            self._opacity_value_label.setText(f"{clamped_opacity}%")
        self._sync_brush_detail_controls()
        self._populate_brush_recent_list()
        self._update_brush_favorite_button()
        self._update_brush_library_preview(preset)
        try:
            from app.painter_material_paint import brush_material_capability

            capability = brush_material_capability(style)
            if capability.get("compatible"):
                self._material_paint_settings.update(dict(capability.get("profile") or {}))
                self._sync_material_controls()
        except Exception:
            pass
        self._set_tool("pen")
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(f"Brush: {preset.get('name', 'Preset')}")

    def _build_material_options_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("PaintMaterialOptionsMenu")
        panel = QFrame(menu)
        panel.setObjectName("PaintMaterialOptionsPanel")
        panel.setFixedWidth(286)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(9, 8, 9, 9)
        layout.setSpacing(6)

        heading = QLabel("MATERIAL PAINT")
        heading.setObjectName("PaintBrushPanelTitle")
        layout.addWidget(heading)
        note = QLabel("Native stroke relief and surface response")
        note.setObjectName("PaintBrushMeta")
        layout.addWidget(note)

        self._material_control_sliders = {}
        self._material_control_labels = {}
        for title, key in (
            ("Load", "load"),
            ("Thickness", "thickness"),
            ("Wetness", "wetness"),
            ("Gloss", "gloss"),
            ("Roughness", "roughness"),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            label = QLabel(title)
            label.setObjectName("PaintMeta")
            label.setFixedWidth(66)
            slider = StudioSlider("accent", panel)
            slider.setRange(0, 100)
            slider.setValue(
                int(round(float(self._material_paint_settings.get(key, 0.0)) * 100.0))
            )
            value = QLabel(f"{slider.value()}%")
            value.setObjectName("PaintValue")
            value.setFixedWidth(44)
            slider.valueChanged.connect(
                lambda amount, setting=key: self._set_material_brush_setting(
                    setting,
                    float(amount) / 100.0,
                )
            )
            row.addWidget(label)
            row.addWidget(slider, stretch=1)
            row.addWidget(value)
            layout.addLayout(row)
            self._material_control_sliders[key] = slider
            self._material_control_labels[key] = value

        wet_heading = QLabel("WET CANVAS")
        wet_heading.setObjectName("PaintBrushPanelTitle")
        layout.addWidget(wet_heading)
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        wet_settings = normalize_wet_canvas_settings(
            getattr(self._active_paint_layer(), "wet_canvas_settings", {})
        )
        self._wet_canvas_enabled_check = QCheckBox("Enable editable wet layer")
        self._wet_canvas_enabled_check.setChecked(bool(wet_settings["enabled"]))
        self._wet_canvas_enabled_check.toggled.connect(
            lambda enabled: self._set_wet_canvas_settings({"enabled": bool(enabled)})
        )
        layout.addWidget(self._wet_canvas_enabled_check)
        self._wet_canvas_control_sliders = {}
        self._wet_canvas_control_labels = {}
        for title, key in (
            ("Mix", "mixing"),
            ("Bleed", "diffusion"),
            ("Pickup", "pickup"),
        ):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            label = QLabel(title)
            label.setObjectName("PaintMeta")
            label.setFixedWidth(66)
            slider = StudioSlider("accent", panel)
            slider.setRange(0, 100)
            slider.setValue(int(round(float(wet_settings[key]) * 100.0)))
            value = QLabel(f"{slider.value()}%")
            value.setObjectName("PaintValue")
            value.setFixedWidth(44)
            slider.valueChanged.connect(
                lambda amount, setting=key: self._set_wet_canvas_settings(
                    {setting: float(amount) / 100.0}
                )
            )
            row.addWidget(label)
            row.addWidget(slider, stretch=1)
            row.addWidget(value)
            layout.addLayout(row)
            self._wet_canvas_control_sliders[key] = slider
            self._wet_canvas_control_labels[key] = value

        dry_row = QHBoxLayout()
        dry_row.setContentsMargins(0, 0, 0, 0)
        dry_label = QLabel("Dry time")
        dry_label.setObjectName("PaintMeta")
        dry_label.setFixedWidth(66)
        dry_slider = StudioSlider("accent", panel)
        dry_slider.setRange(1, 60)
        dry_slider.setValue(
            max(1, min(60, int(round(float(wet_settings["drying_seconds"]) / 60.0))))
        )
        dry_value = QLabel(f"{dry_slider.value()} min")
        dry_value.setObjectName("PaintValue")
        dry_value.setFixedWidth(44)
        dry_slider.valueChanged.connect(
            lambda minutes: self._set_wet_canvas_settings(
                {"drying_seconds": float(minutes) * 60.0}
            )
        )
        dry_row.addWidget(dry_label)
        dry_row.addWidget(dry_slider, stretch=1)
        dry_row.addWidget(dry_value)
        layout.addLayout(dry_row)
        self._wet_canvas_control_sliders["drying_seconds"] = dry_slider
        self._wet_canvas_control_labels["drying_seconds"] = dry_value

        dry_now = QPushButton("Dry Now")
        dry_now.setObjectName("PaintSmallButton")
        dry_now.clicked.connect(self._dry_active_wet_canvas)
        layout.addWidget(dry_now)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(panel)
        menu.addAction(widget_action)
        return menu

    def _set_material_brush_setting(self, key: str, value: float) -> None:
        from app.painter_material_paint import MATERIAL_PAINT_DEFAULTS

        if key not in MATERIAL_PAINT_DEFAULTS:
            return
        self._material_paint_settings[key] = max(0.0, min(1.0, float(value)))
        label = getattr(self, "_material_control_labels", {}).get(key)
        if label is not None:
            label.setText(f"{int(round(self._material_paint_settings[key] * 100.0))}%")
        layer = self._active_paint_layer()
        if str(getattr(layer, "layer_type", "standard")) == "material":
            layer.material_settings = dict(self._material_paint_settings)
        self._material_preview_cache = None
        if hasattr(self, "canvas"):
            self.canvas.update()

    def _sync_material_controls(self) -> None:
        if not hasattr(self, "_paint_layers"):
            return
        layer = self._active_paint_layer()
        active = str(getattr(layer, "layer_type", "standard")) == "material"
        if active:
            from app.painter_material_paint import normalize_material_settings

            self._material_paint_settings = normalize_material_settings(
                getattr(layer, "material_settings", {})
            )
        for key, slider in getattr(self, "_material_control_sliders", {}).items():
            slider.blockSignals(True)
            try:
                slider.setValue(
                    int(round(float(self._material_paint_settings.get(key, 0.0)) * 100.0))
                )
            finally:
                slider.blockSignals(False)
            label = getattr(self, "_material_control_labels", {}).get(key)
            if label is not None:
                label.setText(f"{slider.value()}%")
        for name in ("_material_options_button", "_material_preview_button"):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(active)
                widget.setEnabled(active)
        preview_button = getattr(self, "_material_preview_button", None)
        if preview_button is not None:
            preview_button.blockSignals(True)
            preview_button.setChecked(bool(self._material_preview_enabled and active))
            preview_button.blockSignals(False)
        self._sync_wet_canvas_controls()

    def _sync_wet_canvas_controls(self) -> None:
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        layer = self._active_paint_layer()
        settings = normalize_wet_canvas_settings(
            getattr(layer, "wet_canvas_settings", {})
        )
        enabled_check = getattr(self, "_wet_canvas_enabled_check", None)
        if enabled_check is not None:
            enabled_check.blockSignals(True)
            enabled_check.setChecked(bool(settings["enabled"]))
            enabled_check.setEnabled(
                str(getattr(layer, "layer_type", "standard")) == "material"
            )
            enabled_check.blockSignals(False)
        for key, slider in getattr(self, "_wet_canvas_control_sliders", {}).items():
            slider.blockSignals(True)
            try:
                if key == "drying_seconds":
                    slider.setValue(
                        max(
                            1,
                            min(
                                60,
                                int(round(float(settings["drying_seconds"]) / 60.0)),
                            ),
                        )
                    )
                else:
                    slider.setValue(int(round(float(settings[key]) * 100.0)))
            finally:
                slider.blockSignals(False)
            label = getattr(self, "_wet_canvas_control_labels", {}).get(key)
            if label is not None:
                label.setText(
                    f"{slider.value()} min"
                    if key == "drying_seconds"
                    else f"{slider.value()}%"
                )

    def _set_wet_canvas_settings(
        self,
        values: dict[str, object],
        *,
        layer_id: str | None = None,
        push_undo: bool = True,
    ) -> bool:
        from app.painter_wet_canvas import (
            WET_CANVAS_DEFAULTS,
            normalize_wet_canvas_settings,
        )

        layer = self._paint_layer_by_id(layer_id) if layer_id else self._active_paint_layer()
        if layer is None or str(getattr(layer, "layer_type", "standard")) != "material":
            return False
        current = normalize_wet_canvas_settings(
            getattr(layer, "wet_canvas_settings", {})
        )
        was_enabled = bool(current["enabled"])
        changed = False
        for key in WET_CANVAS_DEFAULTS:
            if key not in values or values[key] is None:
                continue
            if key == "enabled":
                next_value = bool(values[key])
            elif key in {"drying_seconds", "elapsed_seconds"}:
                next_value = max(0.0, min(86400.0, float(values[key])))
            else:
                next_value = max(0.0, min(1.0, float(values[key])))
            if current.get(key) != next_value:
                current[key] = next_value
                changed = True
        if not changed:
            return False
        if (
            values.get("enabled") is True
            and not was_enabled
            and current["elapsed_seconds"] >= current["drying_seconds"]
        ):
            current["elapsed_seconds"] = 0.0
        if push_undo:
            self._push_undo_state("Set wet canvas")
        layer.wet_canvas_settings = normalize_wet_canvas_settings(current)
        self.canvas._wet_canvas_render_cache.pop(layer.layer_id, None)
        self._sync_canvas_layer_view()
        self._sync_wet_canvas_controls()
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        return True

    def _advance_wet_canvas(
        self,
        seconds: float,
        *,
        layer_id: str | None = None,
    ) -> bool:
        from app.painter_wet_canvas import advance_wet_canvas

        layer = self._paint_layer_by_id(layer_id) if layer_id else self._active_paint_layer()
        if layer is None or str(getattr(layer, "layer_type", "standard")) != "material":
            return False
        current = advance_wet_canvas(
            getattr(layer, "wet_canvas_settings", {}),
            max(0.0, float(seconds)),
        )
        return self._set_wet_canvas_settings(
            current,
            layer_id=layer.layer_id,
            push_undo=True,
        )

    def _dry_active_wet_canvas(self) -> bool:
        from app.painter_wet_canvas import dry_wet_canvas

        layer = self._active_paint_layer()
        if str(getattr(layer, "layer_type", "standard")) != "material":
            return False
        return self._set_wet_canvas_settings(
            dry_wet_canvas(getattr(layer, "wet_canvas_settings", {})),
            layer_id=layer.layer_id,
            push_undo=True,
        )

    def _set_material_preview_enabled(self, enabled: bool) -> None:
        active = str(getattr(self._active_paint_layer(), "layer_type", "standard")) == "material"
        self._material_preview_enabled = bool(enabled and active)
        self._material_preview_cache = None
        if hasattr(self, "canvas"):
            self.canvas.update()
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText(
                "Material PBR preview on"
                if self._material_preview_enabled
                else "Material PBR preview off"
            )

    def _paint_material_preview_overlay(self, painter: QPainter, width: int, height: int) -> None:
        if not bool(getattr(self, "_material_preview_enabled", False)):
            return
        if not hasattr(self, "canvas"):
            return
        from app.painter_material_paint import (
            has_material_strokes,
            material_paint_signature,
            material_preview_rgba,
            rasterize_material_channels,
        )

        strokes = self.canvas.embedded_strokes()
        if not has_material_strokes(strokes, self._paint_layers):
            return
        stable_size = self.canvas.stable_render_size(width, height)
        render_width = max(1, stable_size.width())
        render_height = max(1, stable_size.height())
        signature = material_paint_signature(
            strokes,
            self._paint_layers,
            width=render_width,
            height=render_height,
            time_ms=self._time_ms,
            light_azimuth_deg=self._material_preview_light_azimuth_deg,
            light_elevation_deg=self._material_preview_light_elevation_deg,
        )
        cached = getattr(self, "_material_preview_cache", None)
        if not isinstance(cached, dict) or cached.get("signature") != signature:
            channels = rasterize_material_channels(
                strokes,
                self._paint_layers,
                width=render_width,
                height=render_height,
                time_ms=self._time_ms,
                light_azimuth_deg=self._material_preview_light_azimuth_deg,
                light_elevation_deg=self._material_preview_light_elevation_deg,
            )
            rgba = np.ascontiguousarray(material_preview_rgba(channels))
            image = QImage(
                rgba.data,
                int(rgba.shape[1]),
                int(rgba.shape[0]),
                int(rgba.strides[0]),
                QImage.Format.Format_RGBA8888,
            ).copy()
            cached = {
                "signature": signature,
                "image": image,
                "channels": channels,
                "renderer": "painter_material_heightfield_preview_v1",
            }
            self._material_preview_cache = cached
        image = cached.get("image")
        if isinstance(image, QImage) and not image.isNull():
            painter.drawImage(QRectF(0, 0, width, height), image)

    def _build_brush_button_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("PaintBrushPopup")
        panel = QFrame(menu)
        panel.setObjectName("PaintBrushPopupPanel")
        panel.setFixedSize(654, 500)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(7, 6, 7, 7)
        panel_layout.setSpacing(5)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Brush Selector")
        title.setObjectName("PaintBrushPanelTitle")
        header.addWidget(title)
        header.addStretch(1)
        menu_icon = QLabel()
        menu_icon.setPixmap(app_icon("menu", size=14, color="#D8D8D8").pixmap(14, 14))
        header.addWidget(menu_icon)
        panel_layout.addLayout(header)

        notice = QFrame(panel)
        notice.setObjectName("PaintBrushPopupNotice")
        notice_layout = QHBoxLayout(notice)
        notice_layout.setContentsMargins(8, 4, 8, 4)
        notice_layout.addWidget(QLabel("New brushes added..."))
        notice_layout.addStretch(1)
        notice_layout.addWidget(QLabel("Brush Store"))
        panel_layout.addWidget(notice)

        library_row = QHBoxLayout()
        library_row.setContentsMargins(0, 0, 0, 0)
        library_row.addWidget(QLabel("Brush Library:"))
        library_combo = QComboBox(panel)
        library_combo.setObjectName("PaintBrushPopupLibrary")
        library_combo.addItem("Tiger Studio Brushes", "tiger_studio")
        library_row.addWidget(library_combo, stretch=1)
        search_edit = QLineEdit(panel)
        search_edit.setObjectName("PaintBrushPopupSearch")
        search_edit.setPlaceholderText("Search brushes")
        search_edit.setClearButtonEnabled(True)
        search_edit.setFixedWidth(190)
        library_row.addWidget(search_edit)
        panel_layout.addLayout(library_row)

        selector_body = QHBoxLayout()
        selector_body.setContentsMargins(0, 0, 0, 0)
        selector_body.setSpacing(5)

        category_list = QListWidget(panel)
        category_list.setObjectName("PaintBrushPopupCategory")
        category_list.setFixedWidth(154)
        category_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        all_item = QListWidgetItem(app_icon("brush", size=14, color="#D7D7D7"), "All Brushes")
        all_item.setData(Qt.ItemDataRole.UserRole, "")
        category_list.addItem(all_item)
        recent_item = QListWidgetItem(app_icon("history", size=14, color="#D7D7D7"), "Recent Brushes")
        recent_item.setData(Qt.ItemDataRole.UserRole, "__recent__")
        category_list.addItem(recent_item)
        for category in sorted(
            {str(row.get("category") or "Brushes") for row in BRUSH_LIBRARY_PRESETS}
        ):
            item = QListWidgetItem(app_icon("brush", size=14, color="#C7CDD7"), category)
            item.setData(Qt.ItemDataRole.UserRole, category)
            category_list.addItem(item)
        category_list.setCurrentRow(0)
        selector_body.addWidget(category_list)

        preset_list = QListWidget(panel)
        preset_list.setObjectName("PaintBrushPopupList")
        preset_list.setViewMode(QListView.ViewMode.ListMode)
        preset_list.setMovement(QListView.Movement.Static)
        preset_list.setResizeMode(QListView.ResizeMode.Fixed)
        preset_list.setFlow(QListView.Flow.TopToBottom)
        preset_list.setWrapping(False)
        preset_list.setUniformItemSizes(True)
        preset_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        preset_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        preset_list.setIconSize(QSize(118, 48))
        preset_list.setFixedWidth(292)
        selector_body.addWidget(preset_list, stretch=1)

        filter_panel = QFrame(panel)
        filter_panel.setObjectName("PaintBrushPopupFilters")
        filter_panel.setFixedWidth(182)
        filter_layout = QVBoxLayout(filter_panel)
        filter_layout.setContentsMargins(7, 7, 7, 7)
        filter_layout.setSpacing(4)
        filter_title = QLabel("FILTER BRUSHES")
        filter_title.setObjectName("PaintColorLabel")
        filter_layout.addWidget(filter_title)
        popup_filter_checks: dict[str, QCheckBox] = {}
        for label, filter_id in (
            ("My Favorites", "favorites"),
            ("Painter Masters", "masters"),
            ("Stamps", "stamps"),
            ("Watercolor Compatible", "watercolor"),
            ("Thick Paint Compatible", "thick_paint"),
        ):
            checkbox = QCheckBox(label, filter_panel)
            checkbox.setObjectName("PaintBrushPopupFilter")
            checkbox.setChecked(filter_id in self._brush_active_filters)
            popup_filter_checks[filter_id] = checkbox
            filter_layout.addWidget(checkbox)
        filter_layout.addStretch(1)
        clear_filters = QPushButton("Clear Filters")
        clear_filters.setObjectName("PaintCustomColor")
        filter_layout.addWidget(clear_filters)
        selector_body.addWidget(filter_panel)
        panel_layout.addLayout(selector_body, stretch=1)

        footer = QFrame(panel)
        footer.setObjectName("PaintBrushPopupFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(7, 5, 7, 5)
        preview = QLabel(footer)
        preview.setObjectName("PaintBrushPopupPreview")
        preview.setFixedSize(150, 52)
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_layout.addWidget(preview)
        footer_text = QVBoxLayout()
        selected_name = QLabel("Select a brush")
        selected_name.setObjectName("PaintBrushPanelTitle")
        compatibility = QLabel("Layer compatibility: Default Layer")
        compatibility.setObjectName("PaintBrushMeta")
        footer_text.addWidget(selected_name)
        footer_text.addWidget(compatibility)
        footer_layout.addLayout(footer_text, stretch=1)
        favorite_button = QPushButton()
        favorite_button.setObjectName("PaintBrushLibraryTool")
        favorite_button.setCheckable(True)
        favorite_button.setFixedSize(28, 26)
        favorite_button.setToolTip("Toggle selected brush favorite")
        footer_layout.addWidget(favorite_button)
        panel_layout.addWidget(footer)

        current_popup_index = {"value": self._active_brush_preset_index}

        def _matching_indices() -> list[int]:
            current = category_list.currentItem()
            category = str(current.data(Qt.ItemDataRole.UserRole) or "") if current is not None else ""
            search = search_edit.text().strip().casefold()
            active_filters = {
                filter_id
                for filter_id, checkbox in popup_filter_checks.items()
                if checkbox.isChecked()
            }
            if category == "__recent__":
                candidates = [
                    index
                    for index in self._brush_recent_indices
                    if 0 <= index < len(BRUSH_LIBRARY_PRESETS)
                ]
            else:
                candidates = list(range(len(BRUSH_LIBRARY_PRESETS)))
            result: list[int] = []
            for index in candidates:
                preset = BRUSH_LIBRARY_PRESETS[index]
                preset_category = str(preset.get("category") or "Brushes")
                if category and category != "__recent__" and preset_category != category:
                    continue
                haystack = " ".join(
                    (
                        preset_category,
                        str(preset.get("name") or ""),
                        str(preset.get("style") or ""),
                    )
                ).casefold()
                if search and search not in haystack:
                    continue
                if not all(
                    self._brush_preset_matches_filter(preset, filter_id)
                    for filter_id in active_filters
                ):
                    continue
                result.append(index)
            return result

        def _update_popup_footer(item: QListWidgetItem | None) -> None:
            if item is None:
                preview.clear()
                selected_name.setText("No matching brush")
                compatibility.setText("Layer compatibility: -")
                favorite_button.blockSignals(True)
                favorite_button.setChecked(False)
                favorite_button.blockSignals(False)
                return
            try:
                index = int(item.data(Qt.ItemDataRole.UserRole))
                preset = BRUSH_LIBRARY_PRESETS[index]
            except Exception:
                return
            current_popup_index["value"] = index
            selected_name.setText(str(preset.get("name") or "Brush"))
            style = str(preset.get("style") or "")
            category = str(preset.get("category") or "")
            layers = ["Default"]
            if category == "Water Media" or "watercolor" in style:
                layers.append("Watercolor")
            if self._brush_preset_matches_filter(preset, "thick_paint"):
                layers.append("Thick Paint")
            compatibility.setText("Layer compatibility: " + ", ".join(layers))
            preview.setPixmap(
                self._brush_preset_icon(
                    preset,
                    favorite=self._brush_preset_key(preset) in self._brush_favorites,
                ).pixmap(146, 50)
            )
            favorite = self._brush_preset_key(preset) in self._brush_favorites
            favorite_button.blockSignals(True)
            favorite_button.setChecked(favorite)
            favorite_button.setIcon(
                app_icon("favorite", size=14, color="#F0C66A" if favorite else "#D9D9D9")
            )
            favorite_button.blockSignals(False)

        def _populate_popup_presets() -> None:
            preset_list.clear()
            wanted_index = current_popup_index["value"]
            selected_row = -1
            for row, idx in enumerate(_matching_indices()):
                preset = BRUSH_LIBRARY_PRESETS[idx]
                category = str(preset.get("category") or "Brushes")
                name = str(preset.get("name") or f"Brush {idx + 1}")
                width = int(preset.get("width") or 1)
                opacity = int(preset.get("opacity") or 100)
                style = str(preset.get("style") or "round")
                favorite = self._brush_preset_key(preset) in self._brush_favorites
                item = QListWidgetItem(self._brush_preset_icon(preset, favorite=favorite), name)
                item.setData(Qt.ItemDataRole.UserRole, idx)
                item.setToolTip(f"{category} | {name} | {style} | {width}px / {opacity}%")
                item.setSizeHint(QSize(0, 58))
                preset_list.addItem(item)
                if idx == wanted_index:
                    selected_row = row
            if preset_list.count():
                preset_list.setCurrentRow(selected_row if selected_row >= 0 else 0)
                _update_popup_footer(preset_list.currentItem())
            else:
                _update_popup_footer(None)

        def _set_popup_filter(filter_id: str, checked: bool) -> None:
            self._set_brush_filter_enabled(filter_id, checked)
            action = getattr(self, "_brush_filter_actions", {}).get(filter_id)
            if action is not None and action.isChecked() != checked:
                action.blockSignals(True)
                action.setChecked(checked)
                action.blockSignals(False)
            _populate_popup_presets()

        def _clear_popup_filters() -> None:
            for filter_id, checkbox in popup_filter_checks.items():
                checkbox.blockSignals(True)
                checkbox.setChecked(False)
                checkbox.blockSignals(False)
                action = getattr(self, "_brush_filter_actions", {}).get(filter_id)
                if action is not None:
                    action.blockSignals(True)
                    action.setChecked(False)
                    action.blockSignals(False)
            self._brush_active_filters.clear()
            self._populate_brush_library()
            _populate_popup_presets()

        _populate_popup_presets()
        category_list.currentItemChanged.connect(
            lambda _current, _previous: _populate_popup_presets()
        )
        search_edit.textChanged.connect(lambda _text: _populate_popup_presets())
        for filter_id, checkbox in popup_filter_checks.items():
            checkbox.toggled.connect(
                lambda checked=False, value=filter_id: _set_popup_filter(value, bool(checked))
            )
        preset_list.currentItemChanged.connect(_update_popup_footer)
        clear_filters.clicked.connect(_clear_popup_filters)

        def _apply_popup_item(item: QListWidgetItem) -> None:
            try:
                index = int(item.data(Qt.ItemDataRole.UserRole))
            except Exception:
                return
            self._apply_brush_preset_by_index(index)
            menu.close()

        def _toggle_popup_favorite(checked: bool) -> None:
            index = int(current_popup_index["value"])
            if not (0 <= index < len(BRUSH_LIBRARY_PRESETS)):
                return
            preset = BRUSH_LIBRARY_PRESETS[index]
            key = self._brush_preset_key(preset)
            if checked:
                self._brush_favorites.add(key)
            else:
                self._brush_favorites.discard(key)
            self._active_brush_preset_index = index
            self._update_brush_favorite_button()
            _populate_popup_presets()

        favorite_button.toggled.connect(_toggle_popup_favorite)
        preset_list.itemClicked.connect(_apply_popup_item)

        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(panel)
        menu.addAction(widget_action)
        return menu

    def _apply_brush_preset_by_index(self, index: int) -> None:
        try:
            preset = BRUSH_LIBRARY_PRESETS[int(index)]
        except Exception:
            return
        self._apply_brush_library_preset(preset)
        if hasattr(self, "brush_library_list"):
            for row in range(self.brush_library_list.count()):
                item = self.brush_library_list.item(row)
                if int(item.data(Qt.ItemDataRole.UserRole) or -1) == int(index):
                    self.brush_library_list.setCurrentItem(item)
                    break

    def _focus_brush_panel(self) -> None:
        self._set_brush_tab("settings")
        self._show_brush_panel()
        if hasattr(self, "brush_style_combo"):
            self.brush_style_combo.setFocus()
        elif hasattr(self, "pen_btn"):
            self.pen_btn.setFocus()
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText("Advanced brush controls")

    def _focus_brush_selector(self) -> None:
        self._show_brush_button_menu()
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText("Brush Selector")

    def _show_brush_panel(self) -> None:
        panel = getattr(self, "_paint_brush_detail_panel", None)
        scroll = getattr(self, "_paint_inspector_controls_scroll", None)
        if panel is not None and scroll is not None:
            title = getattr(self, "_paint_brush_section_title", None)
            if title is not None:
                title.show()
            panel.show()
            scroll.ensureWidgetVisible(panel, 0, 12)

    def _show_brush_button_menu(self) -> None:
        button = getattr(self, "_brush_preset_button", None)
        if button is None:
            return
        existing = getattr(self, "_brush_preset_menu", None)
        if existing is not None and existing.isVisible():
            existing.close()
            button.setChecked(False)
            return
        panel = getattr(self, "_paint_brush_detail_panel", None)
        title = getattr(self, "_paint_brush_section_title", None)
        if panel is not None:
            panel.hide()
        if title is not None:
            title.hide()
        menu = self._build_brush_button_menu()
        self._brush_preset_menu = menu
        button.setChecked(True)
        menu.aboutToHide.connect(lambda b=button: b.setChecked(False))
        menu.popup(button.mapToGlobal(QPoint(0, button.height() + 4)))

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
                "border: 1px solid #f0f0f0; border-radius: 0; "
                "}"
            )
        if hasattr(self, "_color_hex_label"):
            self._color_hex_label.setText(self._rgb_to_hex(sel))
        if hasattr(self, "_palette_btns"):
            self._refresh_derived_palette_buttons(sel)
        if hasattr(self, "_recent_color_btns"):
            self._refresh_recent_color_buttons(sel)
        if hasattr(self, "foreground_swatch_btn"):
            self._refresh_toolbar_color_swatches()
        self._update_saturation_slider_style()
        self._update_value_slider_style()

    def _sync_palette_controls_from_color(self) -> None:
        if not hasattr(self, "hue_slider") or not hasattr(self, "value_slider"):
            return
        hue = self._pen_color.hue()
        if hue < 0:
            hue = 0
        saturation = max(0, min(100, round(self._pen_color.saturation() * 100 / 255)))
        value = max(12, min(100, round(self._pen_color.value() * 100 / 255)))
        self._palette_syncing = True
        try:
            self.hue_slider.setValue(hue)
            if hasattr(self, "saturation_slider"):
                self.saturation_slider.setValue(saturation)
            self.value_slider.setValue(value)
            if hasattr(self, "color_wheel"):
                self.color_wheel.set_color(self._pen_color)
            if hasattr(self, "photoshop_color_field"):
                self.photoshop_color_field.set_color(self._pen_color)
        finally:
            self._palette_syncing = False
        self._update_saturation_slider_style()
        self._update_value_slider_style()

    def _update_saturation_slider_style(self) -> None:
        if not hasattr(self, "saturation_slider"):
            return
        hue = self._pen_color.hue()
        if hue < 0:
            hue = self.hue_slider.value() if hasattr(self, "hue_slider") else 0
        value = max(80, self._pen_color.value())
        neutral = QColor.fromHsv(hue, 0, value)
        saturated = QColor.fromHsv(hue, 255, value)
        self.saturation_slider.setStyleSheet(
            "QSlider#PaintSaturationSlider::groove:horizontal { "
            "height: 3px; border-radius: 2px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 rgb({neutral.red()},{neutral.green()},{neutral.blue()}), "
            f"stop:1 rgb({saturated.red()},{saturated.green()},{saturated.blue()})); "
            "}"
            "QSlider#PaintSaturationSlider::handle:horizontal { "
            "width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; "
            "background: #6452FF; border: 1px solid #9C8EFF; "
            "}"
        )

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
            "height: 3px; border-radius: 2px; "
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, "
            f"stop:0 #111827, stop:1 rgb({bright.red()},{bright.green()},{bright.blue()})); "
            "}"
            "QSlider#PaintValueSlider::handle:horizontal { "
            "width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; "
            "background: #6452FF; border: 1px solid #9C8EFF; "
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

    def _derived_palette_colors(self) -> list[tuple[tuple[int, int, int], str]]:
        color = QColor(self._pen_color)
        hue = color.hue()
        if hue < 0:
            hue = 0
        saturation = max(24, int(color.saturation()))
        value = max(28, int(color.value()))

        def _hsv_rgb(
            hue_shift: int,
            saturation_scale: float,
            value_scale: float,
            label: str,
        ) -> tuple[tuple[int, int, int], str]:
            c = QColor.fromHsv(
                int((hue + hue_shift) % 360),
                max(0, min(255, int(round(saturation * saturation_scale)))),
                max(0, min(255, int(round(value * value_scale)))),
            )
            return (c.red(), c.green(), c.blue()), label

        return [
            _hsv_rgb(0, 0.92, 0.42, "Deep shade"),
            _hsv_rgb(0, 0.96, 0.66, "Shadow"),
            _hsv_rgb(0, 1.00, 1.00, "Current color"),
            _hsv_rgb(0, 0.72, 1.18, "Tint"),
            _hsv_rgb(0, 0.42, 1.34, "Pale highlight"),
            _hsv_rgb(-18, 1.03, 1.05, "Cool shift"),
            _hsv_rgb(20, 1.05, 1.06, "Warm shift"),
            _hsv_rgb(180, 0.72, 0.92, "Complement"),
        ]

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

    @staticmethod
    def _swatch_button_style(color: QColor, *, foreground: bool) -> str:
        border = "rgba(255, 255, 255, 205)" if foreground else "rgba(170, 180, 198, 135)"
        return (
            "QPushButton { "
            f"background-color: rgb({color.red()},{color.green()},{color.blue()}); "
            f"border: 1px solid {border}; "
            "border-radius: 3px; padding: 0; "
            "} "
            "QPushButton:hover { border-color: #ffffff; }"
        )

    def _refresh_toolbar_color_swatches(self) -> None:
        if hasattr(self, "foreground_swatch_btn"):
            fg = QColor(getattr(self, "_pen_color", QColor("#ffffff")))
            self.foreground_swatch_btn.setStyleSheet(
                self._swatch_button_style(fg, foreground=True)
            )
            self.foreground_swatch_btn.setToolTip(
                f"Foreground color | {self._rgb_to_hex((fg.red(), fg.green(), fg.blue()))}"
            )
        if hasattr(self, "background_swatch_btn"):
            bg = QColor(getattr(self, "_background_color", QColor("#ffffff")))
            self.background_swatch_btn.setStyleSheet(
                self._swatch_button_style(bg, foreground=False)
            )
            self.background_swatch_btn.setToolTip(
                f"Background color | {self._rgb_to_hex((bg.red(), bg.green(), bg.blue()))}"
            )

    def _pick_background_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(getattr(self, "_background_color", QColor("#ffffff"))),
            self,
            "Background color",
        )
        if color.isValid():
            self._background_color = QColor(color)
            self._refresh_toolbar_color_swatches()

    def _swap_painter_foreground_background(self) -> None:
        old_foreground = QColor(self._pen_color)
        old_background = QColor(getattr(self, "_background_color", QColor("#ffffff")))
        self._background_color = old_foreground
        self._apply_pen_color(old_background, remember=True)

    def _set_tool_rail_collapsed(self, collapsed: bool) -> None:
        self._tool_rail_collapsed = bool(collapsed)
        rail = getattr(self, "_tool_rail", None)
        if rail is not None:
            rail.setFixedWidth(
                int(self._tool_rail_collapsed_width if collapsed else self._tool_rail_full_width)
            )
            rail.show()
        host = getattr(self, "_tool_button_host", None)
        if host is not None:
            host.setVisible(not collapsed)
        swatches = getattr(self, "_tool_swatch_panel", None)
        if swatches is not None:
            swatches.setVisible(not collapsed)
        close_btn = getattr(self, "tool_close_btn", None)
        if close_btn is not None:
            close_btn.hide()
        collapse_btn = getattr(self, "tool_collapse_btn", None)
        if collapse_btn is not None:
            collapse_btn.hide()
            collapse_btn.setIcon(
                app_icon("chevron-right" if collapsed else "chevron-down", size=11, color="#AEB8C9")
            )
            collapse_btn.setToolTip("Expand toolbar" if collapsed else "Collapse toolbar")
        grip = getattr(self, "_tool_rail_grip", None)
        if grip is not None:
            grip.setVisible(True)

    def _toggle_tool_rail_collapsed(self) -> None:
        self._set_tool_rail_collapsed(not bool(getattr(self, "_tool_rail_collapsed", False)))

    def _hide_tool_rail(self) -> None:
        rail = getattr(self, "_tool_rail", None)
        if rail is not None:
            rail.hide()
        if hasattr(self, "_tool_status_label"):
            self._tool_status_label.setText("Tool bar hidden; use Window > Show Tool Bar")

    def _show_tool_rail(self) -> None:
        rail = getattr(self, "_tool_rail", None)
        if rail is not None:
            rail.show()
        self._set_tool_rail_collapsed(False)

    def _refresh_recent_color_buttons(self, selected: tuple[int, int, int]) -> None:
        for idx, btn in enumerate(self._recent_color_btns):
            if idx >= len(self._recent_colors):
                btn.hide()
                continue
            rgb = self._recent_colors[idx]
            btn.show()
            self._style_palette_button(btn, rgb, selected=(rgb == selected), width=32, height=16)

    def _refresh_derived_palette_buttons(self, selected: tuple[int, int, int]) -> None:
        buttons = getattr(self, "_palette_btns", [])
        for btn, (rgb, label) in zip(buttons, self._derived_palette_colors()):
            btn.show()
            self._style_palette_button(btn, rgb, selected=(rgb == selected), width=44, height=18)
            btn.setToolTip(f"{label} | {self._rgb_to_hex(rgb)}")

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
        saturation_percent = (
            self.saturation_slider.value()
            if hasattr(self, "saturation_slider")
            else round(self._pen_color.saturation() * 100 / 255)
        )
        value_percent = (
            self.value_slider.value() if hasattr(self, "value_slider") else 100
        )
        value = int(value_percent * 255 / 100)
        saturation = int(max(0, min(100, saturation_percent)) * 255 / 100)
        return QColor.fromHsv(hue, saturation, max(24, min(255, value)))

    # ---------- tool actions ----------

    def _on_zoom_tool_pressed(self) -> None:
        self._zoom_tool_menu_opened = False
        timer = getattr(self, "_zoom_tool_hold_timer", None)
        if timer is not None:
            timer.start()

    def _on_zoom_tool_released(self) -> None:
        timer = getattr(self, "_zoom_tool_hold_timer", None)
        if timer is not None and timer.isActive():
            timer.stop()
        if not bool(getattr(self, "_zoom_tool_menu_opened", False)):
            self._set_zoom_tool_mode(getattr(self, "_zoom_tool_mode", "zoom_in"))

    def _show_zoom_tool_menu(self) -> None:
        button = getattr(self, "zoom_fit_rail_btn", None)
        if button is None:
            return
        self._zoom_tool_menu_opened = True
        menu = QMenu(self)
        menu.setObjectName("PaintZoomToolMenu")
        actions: list[tuple[str, str, str]] = [
            ("Zoom In", "zoom_in", "zoom"),
            ("Zoom Out", "zoom_out", "zoom"),
            ("Zoom Area", "zoom_area", "marquee-rect"),
        ]
        for label, mode, icon_name in actions:
            action = menu.addAction(app_icon(icon_name, size=14, color="#E8EDF5"), label)
            action.setCheckable(True)
            action.setChecked(str(getattr(self, "_zoom_tool_mode", "zoom_in")) == mode)
            action.triggered.connect(
                lambda _checked=False, value=mode: self._set_zoom_tool_mode(value)
            )
        menu.addSeparator()
        fit_action = menu.addAction(
            app_icon("zoom-fit", size=14, color="#E8EDF5"),
            "Fit Canvas",
        )
        fit_action.triggered.connect(self._zoom_fit)
        self._zoom_tool_menu = menu
        menu.popup(button.mapToGlobal(button.rect().topRight()))

    def _set_zoom_tool_mode(self, mode: str) -> None:
        value = str(mode or "zoom_in")
        if value not in {"zoom_in", "zoom_out", "zoom_area"}:
            value = "zoom_in"
        self._zoom_tool_mode = value
        button = getattr(self, "zoom_fit_rail_btn", None)
        if button is not None:
            labels = {
                "zoom_in": "Zoom In Tool",
                "zoom_out": "Zoom Out Tool",
                "zoom_area": "Zoom Area Tool",
            }
            button.setToolTip(
                f"{labels[value]} (Z). Hold for Zoom In / Zoom Out / Zoom Area."
            )
        self._set_tool(value)

    def _handle_canvas_zoom_request(
        self,
        mode: str,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        value = str(mode or "zoom_in")
        current = int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100))
        if value == "zoom_area" and float(width) > 0.001 and float(height) > 0.001:
            factor = min(1.0 / float(width), 1.0 / float(height))
            target = int(round(current * factor))
            center_x = float(x) + float(width) * 0.5
            center_y = float(y) + float(height) * 0.5
        else:
            target = current + (25 if value == "zoom_in" else -25)
            center_x = float(x)
            center_y = float(y)
        self._set_zoom_percent(max(25, min(PAINT_MAX_ZOOM_PERCENT, target)))
        if hasattr(self, "canvas"):
            pan = QPoint(
                int(round(self.canvas.width() * (0.5 - center_x))),
                int(round(self.canvas.height() * (0.5 - center_y))),
            )
            self._set_canvas_pan(pan)

    def _set_tool(self, tool: str) -> None:
        self._active_ui_tool = str(tool or "select")
        previous_workspace = str(
            getattr(self, "_canvas_workspace_mode", "paint") or "paint"
        )
        if tool == "3d_blockout":
            self._canvas_workspace_mode = "3d_place"
        elif tool in {
            "select",
            "pan",
            "pen",
            "eraser",
            "path",
            "rect_select",
            "ellipse_select",
            "crop",
            "magic_select",
            "fill",
            "zoom_in",
            "zoom_out",
            "zoom_area",
        }:
            self._canvas_workspace_mode = (
                "ui_design"
                if previous_workspace == "ui_design"
                and tool in {"select", "pan", "zoom_in", "zoom_out", "zoom_area"}
                else "paint"
            )
        canvas_tool = tool if tool in (
            "pen",
            "eraser",
            "path",
            "rect_select",
            "ellipse_select",
            "crop",
            "magic_select",
            "zoom_in",
            "zoom_out",
            "zoom_area",
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
        if hasattr(self, "fill_tool_btn"):
            self.fill_tool_btn.setChecked(tool == "fill")
        if hasattr(self, "zoom_fit_rail_btn"):
            self.zoom_fit_rail_btn.setChecked(
                tool in {"zoom_in", "zoom_out", "zoom_area"}
            )
        tool_meta = {
            "select": ("Move", "move-tool"),
            "pan": ("Hand", "hand"),
            "pen": ("Brush", "paint-brush"),
            "eraser": ("Eraser", "eraser"),
            "path": ("Pen", "pen-nib"),
            "rect_select": ("Rectangular Marquee", "marquee-rect"),
            "ellipse_select": ("Elliptical Marquee", "marquee-ellipse"),
            "magic_select": ("Magic Select", "magic-wand"),
            "crop": ("Crop", "crop"),
            "fill": ("Paint Bucket", "paint-bucket"),
            "zoom_in": ("Zoom In", "zoom"),
            "zoom_out": ("Zoom Out", "zoom"),
            "zoom_area": ("Zoom Area", "marquee-rect"),
            "3d_blockout": ("3D Place", "box"),
        }
        tool_name, tool_icon = tool_meta.get(tool, ("Move", "move-tool"))
        if hasattr(self, "_active_tool_name"):
            self._active_tool_name.setText(tool_name)
        if hasattr(self, "_active_tool_icon"):
            self._active_tool_icon.setPixmap(
                app_icon(tool_icon, size=14, color="#F0F0F0").pixmap(14, 14)
            )
        host = getattr(self, "_canvas_host", None)
        if host is not None:
            if tool in {"zoom_in", "zoom_out"}:
                host.setCursor(_zoom_tool_cursor(tool))
            else:
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
                "fill": "Paint Bucket: choose a fill mode in the options bar",
                "zoom_in": "Zoom In: click the canvas",
                "zoom_out": "Zoom Out: click the canvas",
                "zoom_area": "Zoom Area: drag around the area to magnify",
                "3d_blockout": "3D Place: select or transform primitives on the canvas",
            }
            self._tool_status_label.setText(labels.get(tool, "Select / move objects"))
        self._sync_canvas_workspace_mode_controls()
        self._update_tool_option_controls()

    def _set_selection_combine_mode(self, mode: str) -> str:
        value = str(mode or "new").strip().casefold()
        selected = value if value in {"new", "add", "subtract", "intersect"} else "new"
        self._selection_combine_mode = selected
        if hasattr(self, "canvas"):
            self.canvas.set_selection_combine_mode(selected)
        for key, button in getattr(self, "_selection_mode_buttons", {}).items():
            button.blockSignals(True)
            try:
                button.setChecked(key == selected)
            finally:
                button.blockSignals(False)
        return selected

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
        if hasattr(self, "quick_mask_rail_btn"):
            self.quick_mask_rail_btn.blockSignals(True)
            try:
                self.quick_mask_rail_btn.setChecked(self._quick_mask_enabled)
            finally:
                self.quick_mask_rail_btn.blockSignals(False)
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

    def _set_perspective_guide_options(
        self,
        *,
        enabled: bool | None = None,
        horizon: float | None = None,
        left_x: float | None = None,
        left_y: float | None = None,
        right_x: float | None = None,
        right_y: float | None = None,
    ) -> dict[str, object]:
        current = (
            self.canvas.perspective_guide_state()
            if hasattr(self, "canvas") and hasattr(self.canvas, "perspective_guide_state")
            else {"horizon": 0.5, "left_vp": [0.08, 0.5], "right_vp": [0.92, 0.5]}
        )
        left = list(current.get("left_vp", [0.08, 0.5]) or [0.08, 0.5])
        right = list(current.get("right_vp", [0.92, 0.5]) or [0.92, 0.5])
        if left_x is not None:
            left[0] = float(left_x)
        if left_y is not None:
            left[1] = float(left_y)
        if right_x is not None:
            right[0] = float(right_x)
        if right_y is not None:
            right[1] = float(right_y)
        if hasattr(self, "canvas"):
            self.canvas.set_perspective_guides(
                enabled=enabled,
                horizon=horizon,
                left_vp=(float(left[0]), float(left[1])),
                right_vp=(float(right[0]), float(right[1])),
            )
        if hasattr(self, "_tool_status_label"):
            active = bool(enabled) if enabled is not None else bool(current.get("enabled", False))
            self._tool_status_label.setText(f"Perspective guide {'on' if active else 'off'}")
        return self.canvas.perspective_guide_state() if hasattr(self, "canvas") else {"enabled": False}

    def _set_symmetry_guide_options(
        self,
        *,
        enabled: bool | None = None,
        axis: str | None = None,
        position: float | None = None,
    ) -> dict[str, object]:
        if hasattr(self, "canvas"):
            self.canvas.set_symmetry_guide(
                enabled=enabled,
                axis=axis,
                position=position,
            )
        if hasattr(self, "_tool_status_label"):
            state = self.canvas.symmetry_guide_state() if hasattr(self, "canvas") else {"enabled": False}
            self._tool_status_label.setText(
                f"Symmetry guide {'on' if state.get('enabled') else 'off'}"
            )
        return self.canvas.symmetry_guide_state() if hasattr(self, "canvas") else {"enabled": False}

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
        ui_tool = str(getattr(self, "_active_ui_tool", current_tool) or current_tool)
        selection_tool = current_tool in {"rect_select", "ellipse_select"}
        for name, visible in (
            ("_selection_options_widget", selection_tool),
            ("_selection_action_widget", current_tool == "crop" or has_selection),
            ("_magic_options_widget", current_tool == "magic_select"),
            ("_fill_options_widget", ui_tool == "fill"),
            ("_brush_options_widget", current_tool in {"pen", "eraser"}),
        ):
            widget = getattr(self, name, None)
            if widget is not None:
                widget.setVisible(bool(visible))
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
        if hasattr(self, "quick_mask_rail_btn"):
            self.quick_mask_rail_btn.setChecked(bool(getattr(self, "_quick_mask_enabled", False)))
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

    def _on_saturation_changed(self, _value: int) -> None:
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
        if hasattr(self, "_top_brush_size_spin") and self.sender() is not self._top_brush_size_spin:
            self._top_brush_size_spin.blockSignals(True)
            try:
                self._top_brush_size_spin.setValue(int(value))
            finally:
                self._top_brush_size_spin.blockSignals(False)
        if hasattr(self, "_width_value_label"):
            self._width_value_label.setText(f"{value} px")
        label = getattr(self, "_brush_detail_value_labels", {}).get("size")
        if label is not None:
            label.setText(self._format_brush_detail_value("size", int(value)))
        self._update_brush_detail_preview()

    def _on_opacity_changed(self, value: int) -> None:
        self._pen_opacity = int(value * 255 / 100)
        self.canvas.set_pen_opacity(self._pen_opacity)
        if hasattr(self, "_top_brush_opacity_spin") and self.sender() is not self._top_brush_opacity_spin:
            self._top_brush_opacity_spin.blockSignals(True)
            try:
                self._top_brush_opacity_spin.setValue(int(value))
            finally:
                self._top_brush_opacity_spin.blockSignals(False)
        if hasattr(self, "_opacity_value_label"):
            self._opacity_value_label.setText(f"{value}%")
        label = getattr(self, "_brush_detail_value_labels", {}).get("opacity")
        if label is not None:
            label.setText(self._format_brush_detail_value("opacity", int(value)))
        self._update_brush_detail_preview()

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
        layer = self._active_paint_layer()
        if str(getattr(layer, "layer_type", "standard")) == "material":
            from app.painter_material_paint import normalize_material_settings

            material = normalize_material_settings(self._material_paint_settings)
            layer.material_settings = dict(material)
            point_count = len(stroke.points)
            if point_count:
                stroke.brush_engine_version = 2
                stroke.brush_seed = stroke.brush_seed or (
                    len(self.canvas.embedded_strokes()) * 7919 + point_count * 131
                )
                stroke.bristle_count = stroke.bristle_count or max(
                    7, min(36, int(round(stroke.width_px * 0.46)))
                )
                if not stroke.point_pressure:
                    stroke.point_pressure = [
                        max(
                            0.28,
                            min(
                                1.0,
                                0.68
                                + math.sin(index / max(1, point_count - 1) * math.pi)
                                * 0.26,
                            ),
                        )
                        for index in range(point_count)
                    ]
                if not stroke.point_tilt:
                    stroke.point_tilt = [0.5] * point_count
                if not stroke.point_rotation:
                    stroke.point_rotation = [0.5] * point_count
                if not stroke.point_load:
                    stroke.point_load = [material["load"]] * point_count
            stroke.material_enabled = True
            stroke.material_load = material["load"]
            stroke.material_thickness = material["thickness"]
            stroke.material_wetness = material["wetness"]
            stroke.material_gloss = material["gloss"]
            stroke.material_roughness = material["roughness"]
            from app.painter_wet_canvas import normalize_wet_canvas_settings

            wet_settings = normalize_wet_canvas_settings(
                getattr(layer, "wet_canvas_settings", {})
            )
            if wet_settings["enabled"]:
                wet_settings["elapsed_seconds"] = 0.0
                layer.wet_canvas_settings = wet_settings
            self._material_preview_cache = None
            self._pbr_preview_maps_cache = None
            self._sync_canvas_layer_view()
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
        width = max(1, min(60, int(width)))
        opacity = max(10, min(100, int(opacity)))
        self._pen_width = float(width)
        self._pen_opacity = int(opacity * 255 / 100)
        if hasattr(self, "canvas"):
            self.canvas.set_pen_width(self._pen_width)
            self.canvas.set_pen_opacity(self._pen_opacity)
        if hasattr(self, "width_slider"):
            self.width_slider.setValue(width)
        if hasattr(self, "opacity_slider"):
            self.opacity_slider.setValue(opacity)
        if hasattr(self, "_width_value_label"):
            self._width_value_label.setText(f"{width} px")
        if hasattr(self, "_opacity_value_label"):
            self._opacity_value_label.setText(f"{opacity}%")
        if opacity < 70:
            style = "highlighter"
        elif width >= 8:
            style = "marker"
        else:
            style = "round"
        self._pen_style = _normalize_paint_brush_style(style)
        if hasattr(self, "canvas"):
            self.canvas.set_pen_style(self._pen_style)
        if hasattr(self, "brush_style_combo"):
            self.brush_style_combo.setCurrentIndex(
                max(0, self.brush_style_combo.findData(self._pen_style))
            )
        self._set_tool("pen")

    def _on_brush_style_changed(self) -> None:
        combo = getattr(self, "brush_style_combo", None)
        style = combo.currentData() if combo is not None else "round"
        self._pen_style = _normalize_paint_brush_style(str(style))
        self.canvas.set_pen_style(self._pen_style)
        self._update_brush_detail_preview()

    def _commit_path(self, closed: bool) -> None:
        self.canvas.commit_path(closed=closed, make_selection=closed)
        self._update_inspector_counts()
        self._update_path_list()

    def _clear_path_preview(self) -> None:
        self.canvas.clear_path_preview()
        self._update_path_list()

    def _on_zoom_changed(self, value: int) -> None:
        value = max(25, min(PAINT_MAX_ZOOM_PERCENT, int(value or 100)))
        self._canvas_zoom = max(0.25, min(PAINT_MAX_ZOOM_PERCENT / 100.0, value / 100.0))
        if hasattr(self, "_zoom_value_label"):
            self._zoom_value_label.setText(f"{value}%")
        if hasattr(self, "_status_zoom_spin"):
            self._status_zoom_spin.blockSignals(True)
            self._status_zoom_spin.setValue(value)
            self._status_zoom_spin.blockSignals(False)
        if hasattr(self, "canvas"):
            self.canvas.set_view_zoom_percent(value)
        self._update_canvas_geometry()

    def _set_zoom_percent(self, value: int) -> None:
        value = max(25, min(PAINT_MAX_ZOOM_PERCENT, int(value)))
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
                paint_layers=self._paint_layers,
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
        layer_rank = {layer.layer_id: index for index, layer in enumerate(self._paint_layers)}
        strokes = list(self.canvas.embedded_strokes())
        strokes.sort(
            key=lambda stroke: layer_rank.get(
                str(getattr(stroke, "layer_id", "") or "paint-layer-1"),
                len(layer_rank),
            )
        )
        for stroke in strokes:
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
            copy.deepcopy(getattr(self, "_painter_reference_board", None)),
            str(getattr(self, "_painter_reference_selected_id", "")),
            copy.deepcopy(getattr(self, "_painter_3d_blockout_scene", None)),
            str(getattr(self, "_painter_3d_blockout_selected_id", "")),
            self.canvas.path_snapshot() if hasattr(self, "canvas") else [],
            copy.deepcopy(getattr(self, "_painter_ui_document", None)),
            str(getattr(self, "_canvas_workspace_mode", "paint") or "paint"),
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
        self._painter_document_dirty = True
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
        restored_work_path = copy.deepcopy(snapshot[21]) if len(snapshot) >= 22 else None
        restored_ui_document = copy.deepcopy(snapshot[22]) if len(snapshot) >= 23 else None
        restored_workspace_mode = str(snapshot[23]) if len(snapshot) >= 24 else ""
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
            if len(snapshot) >= 18:
                extra = snapshot[17]
                if len(snapshot) >= 20:
                    self._painter_reference_board = (
                        copy.deepcopy(extra) if isinstance(extra, dict) else None
                    )
                    self._painter_reference_selected_id = str(snapshot[18] or "")
                    self._painter_3d_blockout_scene = copy.deepcopy(snapshot[19])
                    if len(snapshot) >= 21:
                        self._painter_3d_blockout_selected_id = str(snapshot[20] or "")
                else:
                    self._painter_3d_blockout_scene = copy.deepcopy(extra)
                    if len(snapshot) >= 19:
                        self._painter_3d_blockout_selected_id = str(snapshot[18] or "")
            for item in list(getattr(self, "_bubble_items", [])):
                item.deleteLater()
            for item in list(getattr(self, "_sticker_items", [])):
                item.deleteLater()
            for item in list(getattr(self, "_painter_reference_labels", {}).values()):
                item.deleteLater()
            self._bubble_items = []
            self._sticker_items = []
            self._painter_reference_labels = {}
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
            if restored_work_path is not None:
                self.canvas.set_path_snapshot(restored_work_path)
            self._refresh_reference_board_panel()
            self._refresh_3d_blockout_panel()
            if restored_ui_document is not None:
                from app.painter_ui_document import normalize_ui_document

                self._painter_ui_document = normalize_ui_document(
                    restored_ui_document,
                    fallback_width=self._canvas_document_size[0],
                    fallback_height=self._canvas_document_size[1],
                )
            if restored_workspace_mode:
                self._canvas_workspace_mode = restored_workspace_mode
            self._sync_canvas_workspace_mode_controls()
            self._refresh_painter_ui_overlay()
        finally:
            self._restoring_state = False
        self._update_inspector_counts()
        self._update_channel_list()
        self._update_history_buttons()
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        self._sync_material_controls()

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
        if hasattr(self, "_status_document_label"):
            self._status_document_label.setText(
                f"{self._canvas_document_size[0]} x {self._canvas_document_size[1]} px"
            )
        if hasattr(self, "_status_layer_label"):
            layer = self._paint_layer_by_id(self._active_paint_layer_id)
            self._status_layer_label.setText(layer.name if layer is not None else "Background")

    def _paint_panel_row_icon(
        self,
        *,
        visible: bool,
        channel: str = "",
        layer_id: str = "",
        background: bool = False,
    ) -> QIcon:
        pixmap = QPixmap(58, 30)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        eye = app_icon(
            "eye" if visible else "eye-off",
            size=13,
            color="#ededed" if visible else "#858585",
        ).pixmap(13, 13)
        painter.drawPixmap(2, 8, eye)

        thumb_rect = QRect(21, 2, 35, 26)
        checker = 5
        for y in range(thumb_rect.top(), thumb_rect.bottom() + 1, checker):
            for x in range(thumb_rect.left(), thumb_rect.right() + 1, checker):
                even = ((x - thumb_rect.left()) // checker + (y - thumb_rect.top()) // checker) % 2
                painter.fillRect(
                    QRect(x, y, checker, checker),
                    QColor("#747474" if even else "#909090"),
                )

        source = getattr(self, "_bg_pixmap_source", QPixmap())
        if (channel or background) and isinstance(source, QPixmap) and not source.isNull():
            thumb = source.scaled(
                thumb_rect.size(),
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ).toImage().convertToFormat(QImage.Format.Format_ARGB32)
            if channel and channel != "RGB":
                for y in range(thumb.height()):
                    for x in range(thumb.width()):
                        pixel = thumb.pixelColor(x, y)
                        if channel == "Red":
                            level = pixel.red()
                        elif channel == "Green":
                            level = pixel.green()
                        elif channel == "Blue":
                            level = pixel.blue()
                        else:
                            level = pixel.alpha()
                        thumb.setPixelColor(x, y, QColor(level, level, level, 255))
            painter.drawImage(thumb_rect, thumb)
        elif layer_id and hasattr(self, "canvas"):
            painter.save()
            painter.setClipRect(thumb_rect)
            for stroke in self.canvas.embedded_strokes():
                if str(getattr(stroke, "layer_id", "")) != layer_id or len(stroke.points) < 1:
                    continue
                color = QColor(*stroke.color)
                color.setAlpha(max(32, min(255, int(stroke.opacity))))
                pen = QPen(color, max(1.0, min(3.0, float(stroke.width_px) * 0.18)))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                path = QPainterPath()
                first_x, first_y = stroke.points[0]
                path.moveTo(
                    thumb_rect.left() + float(first_x) * thumb_rect.width(),
                    thumb_rect.top() + float(first_y) * thumb_rect.height(),
                )
                for point_x, point_y in stroke.points[1:]:
                    path.lineTo(
                        thumb_rect.left() + float(point_x) * thumb_rect.width(),
                        thumb_rect.top() + float(point_y) * thumb_rect.height(),
                    )
                painter.drawPath(path)
            painter.restore()

        painter.setPen(QPen(QColor("#393939"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(thumb_rect)
        painter.end()
        return QIcon(pixmap)

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
                selected_special = False
                if isinstance(selected_id, str) and selected_id.startswith("sticker:"):
                    try:
                        selected_special = 0 <= int(selected_id.split(":", 1)[1]) < len(self._stickers)
                    except (TypeError, ValueError):
                        selected_special = False
                if isinstance(selected_id, str) and selected_id.startswith("bubble:"):
                    try:
                        selected_special = 0 <= int(selected_id.split(":", 1)[1]) < len(self._bubbles)
                    except (TypeError, ValueError):
                        selected_special = False
                if (
                    not self._is_paint_layer_id(selected_id)
                    and not selected_background
                    and not selected_special
                ):
                    selected_id = self._active_paint_layer_id
                    self._selected_layer_id = selected_id
                for layer in reversed(self._paint_layers):
                    color_label = _normalise_paint_layer_color_label(
                        getattr(layer, "color_label", "none")
                    )
                    color_meta = PAINT_LAYER_COLOR_LABEL_MAP[color_label]
                    accent = str(color_meta["color"] or "")
                    states: list[str] = []
                    if not layer.visible:
                        states.append("Hidden")
                    if layer.locked:
                        states.append("Locked")
                    if bool(getattr(layer, "mask_enabled", False)) and len(getattr(layer, "mask", []) or []) >= 3:
                        states.append("Mask")
                    if getattr(layer, "blend_mode", "normal") != "normal":
                        states.append(str(layer.blend_mode).title())
                    layer_type = str(getattr(layer, "layer_type", "standard") or "standard")
                    if layer_type == "material":
                        states.append("Material Paint")
                    item = QListWidgetItem(
                        f"{layer.name}  [M]" if layer_type == "material" else layer.name
                    )
                    item.setIcon(
                        self._paint_panel_row_icon(
                            visible=bool(layer.visible),
                            layer_id=layer.layer_id,
                        )
                    )
                    item.setSizeHint(QSize(0, 38))
                    item.setData(Qt.ItemDataRole.UserRole, layer.layer_id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, color_label)
                    item.setFlags(
                        item.flags()
                        | Qt.ItemFlag.ItemIsDragEnabled
                        | Qt.ItemFlag.ItemIsDropEnabled
                    )
                    if accent:
                        bg = QColor(accent)
                        bg.setAlpha(72)
                        item.setBackground(QBrush(bg))
                    item.setToolTip(
                        f"{layer.name}\n"
                        f"Visible: {'yes' if layer.visible else 'no'}\n"
                        f"Opacity: {layer.opacity}%\n"
                        f"Blend: {getattr(layer, 'blend_mode', 'normal')}\n"
                        f"Type: {layer_type}\n"
                        f"Color label: {color_meta['name']}"
                    )
                    layer_list.addItem(item)
                    if selected_id == layer.layer_id:
                        layer_list.setCurrentItem(item)
                for idx, sticker in enumerate(getattr(self, "_stickers", [])):
                    name = Path(sticker.png_path).name or "PNG sticker"
                    item = QListWidgetItem(f"Sticker {idx + 1}: {name[:24]}")
                    item.setIcon(app_icon("image", size=14, color="#DCE6F7"))
                    layer_id = f"sticker:{idx}"
                    item.setData(Qt.ItemDataRole.UserRole, layer_id)
                    layer_list.addItem(item)
                    if selected_id == layer_id:
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
                if self._background_layer_present:
                    bg_item = QListWidgetItem(tr("paint.layer.background"))
                    bg_item.setIcon(
                        self._paint_panel_row_icon(
                            visible=True,
                            background=True,
                        )
                    )
                    bg_item.setSizeHint(QSize(0, 38))
                    bg_item.setData(Qt.ItemDataRole.UserRole, "background")
                    bg_item.setFlags(
                        bg_item.flags()
                        & ~Qt.ItemFlag.ItemIsDragEnabled
                        & ~Qt.ItemFlag.ItemIsDropEnabled
                    )
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

    def _on_layer_rows_moved(self, *_args) -> None:
        if bool(getattr(self, "_syncing_layer_order", False)):
            return
        layer_list = getattr(self, "_layer_list", None)
        if layer_list is None:
            return
        visual_ids = [
            str(layer_list.item(row).data(Qt.ItemDataRole.UserRole) or "")
            for row in range(layer_list.count())
        ]
        paint_ids = [layer_id for layer_id in visual_ids if self._is_paint_layer_id(layer_id)]
        if len(paint_ids) != len(self._paint_layers):
            self._update_layer_list()
            return
        lookup = {layer.layer_id: layer for layer in self._paint_layers}
        reordered = [lookup[layer_id] for layer_id in reversed(paint_ids) if layer_id in lookup]
        if len(reordered) != len(self._paint_layers):
            self._update_layer_list()
            return
        self._push_undo_state("Reorder layers")
        self._paint_layers = reordered
        self._sync_canvas_layer_view()
        self._update_layer_list()

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
                self._layer_opacity_value.blockSignals(True)
                self._layer_opacity_value.setValue(100)
                self._layer_opacity_value.setEnabled(False)
                self._layer_opacity_value.blockSignals(False)
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
            self._layer_opacity_value.blockSignals(True)
            self._layer_opacity_value.setValue(int(layer.opacity))
            self._layer_opacity_value.setEnabled(not layer.locked)
            self._layer_opacity_value.blockSignals(False)
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
                item.setIcon(self._paint_panel_row_icon(visible=visible, channel=channel))
                item.setSizeHint(QSize(0, 38))
                item.setToolTip(
                    f"{channel} channel is {'visible' if visible else 'hidden'}. "
                    "Click the eye icon to toggle it."
                )
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
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

    def _handle_channel_list_event(self, event) -> bool:
        channel_list = getattr(self, "_channel_list", None)
        if channel_list is None:
            return False
        if event.type() != QEvent.Type.MouseButtonPress:
            return False
        try:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            point = event.position().toPoint()
        except Exception:
            return False
        item = channel_list.itemAt(point)
        if item is None:
            return False
        rect = channel_list.visualItemRect(item)
        icon_hit_width = 19
        if point.x() <= rect.left() + icon_hit_width:
            self._toggle_channel_item_visibility(item)
            event.accept()
            return True
        return False

    def _handle_layer_list_event(self, event) -> bool:
        layer_list = getattr(self, "_layer_list", None)
        if layer_list is None or event.type() != QEvent.Type.MouseButtonPress:
            return False
        try:
            if event.button() != Qt.MouseButton.LeftButton:
                return False
            point = event.position().toPoint()
        except Exception:
            return False
        item = layer_list.itemAt(point)
        if item is None:
            return False
        rect = layer_list.visualItemRect(item)
        if point.x() > rect.left() + 19:
            return False
        layer_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        layer = self._paint_layer_by_id(layer_id)
        if layer is None:
            return False
        self._set_layer_visible(layer.layer_id, not bool(layer.visible))
        event.accept()
        return True

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
        if self._selected_layer_id == "paint-layer-3d-blockout":
            self._set_canvas_workspace_mode("3d_place", focus_panel=False)
            self._update_layer_controls()
            return
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
            self._layer_opacity_value.blockSignals(True)
            self._layer_opacity_value.setValue(layer.opacity)
            self._layer_opacity_value.blockSignals(False)
        if hasattr(self, "layer_opacity_slider"):
            self.layer_opacity_slider.blockSignals(True)
            self.layer_opacity_slider.setValue(layer.opacity)
            self.layer_opacity_slider.blockSignals(False)
        self._sync_canvas_layer_view()
        self._update_layer_list()
        if layer.layer_id == "paint-layer-3d-blockout":
            self._painter_3d_blockout_flat_cache = None
            self._refresh_3d_blockout_overlay()

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

    def _new_paint_layer(
        self,
        name: str | None = None,
        *,
        layer_type: str = "standard",
    ) -> PaintLayer:
        from app.painter_material_paint import (
            normalize_layer_type,
            normalize_material_settings,
        )
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        self._push_undo_state("New layer")
        self._paint_layer_serial += 1
        if isinstance(name, bool):
            name = None
        raw_name = str(name or "").strip()
        normalized_type = normalize_layer_type(layer_type)
        layer = PaintLayer(
            layer_id=f"paint-layer-{self._paint_layer_serial}",
            name=raw_name[:80] if raw_name else f"Layer {self._paint_layer_serial}",
            layer_type=normalized_type,
            material_settings=(
                normalize_material_settings(self._material_paint_settings)
                if normalized_type == "material"
                else {}
            ),
            wet_canvas_settings=(
                normalize_wet_canvas_settings(None)
                if normalized_type == "material"
                else {}
            ),
        )
        self._paint_layers.append(layer)
        self._active_paint_layer_id = layer.layer_id
        self._selected_layer_id = layer.layer_id
        self._sync_canvas_layer_view()
        self._update_inspector_counts()
        self._sync_material_controls()
        return layer

    def _new_material_paint_layer(self, name: str | None = None) -> PaintLayer:
        if isinstance(name, bool):
            name = None
        layer = self._new_paint_layer(
            str(name or "").strip() or "Material Paint",
            layer_type="material",
        )
        self._material_preview_enabled = True
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        self._sync_material_controls()
        if hasattr(self, "canvas"):
            self.canvas.update()
        return layer

    def _toggle_selected_layer_visibility(self) -> None:
        layer = self._paint_layer_by_id(self._current_layer_id())
        if layer is None:
            return
        self._push_undo_state("Show layer" if not layer.visible else "Hide layer")
        layer.visible = not layer.visible
        self._sync_canvas_layer_view()
        self._update_layer_list()
        if layer.layer_id == "paint-layer-3d-blockout":
            self._refresh_3d_blockout_overlay()

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
        self._sync_material_controls()
        self._material_preview_cache = None
        if hasattr(self, "_status_layer_label"):
            self._status_layer_label.setText(layer.name)
        return layer

    def _set_paint_layer_type(self, layer_id: str | None, layer_type: str) -> bool:
        from app.painter_material_paint import (
            normalize_layer_type,
            normalize_material_settings,
        )
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None:
            return False
        normalized = normalize_layer_type(layer_type)
        if str(getattr(layer, "layer_type", "standard")) == normalized:
            return False
        self._push_undo_state("Set layer type")
        layer.layer_type = normalized
        layer.material_settings = (
            normalize_material_settings(
                getattr(layer, "material_settings", {}) or self._material_paint_settings
            )
            if normalized == "material"
            else {}
        )
        layer.wet_canvas_settings = (
            normalize_wet_canvas_settings(
                getattr(layer, "wet_canvas_settings", {})
            )
            if normalized == "material"
            else {}
        )
        if normalized == "material":
            self._material_preview_enabled = True
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        self._sync_material_controls()
        self._update_inspector_counts()
        if hasattr(self, "canvas"):
            self.canvas.update()
        return True

    def _set_material_settings(
        self,
        values: dict[str, object],
        *,
        layer_id: str | None = None,
    ) -> bool:
        from app.painter_material_paint import (
            MATERIAL_PAINT_DEFAULTS,
            normalize_material_settings,
        )

        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None or str(getattr(layer, "layer_type", "standard")) != "material":
            return False
        current = normalize_material_settings(getattr(layer, "material_settings", {}))
        changed = False
        for key in MATERIAL_PAINT_DEFAULTS:
            if key in values and values[key] is not None:
                current[key] = max(0.0, min(1.0, float(values[key])))
                changed = True
        if not changed:
            return False
        self._push_undo_state("Set material paint")
        layer.material_settings = normalize_material_settings(current)
        self._material_paint_settings = dict(layer.material_settings)
        self._material_preview_cache = None
        self._pbr_preview_maps_cache = None
        self._sync_material_controls()
        if hasattr(self, "canvas"):
            self.canvas.update()
        return True

    def _set_material_preview(
        self,
        *,
        enabled: bool | None = None,
        azimuth_deg: float | None = None,
        elevation_deg: float | None = None,
    ) -> dict[str, object]:
        if enabled is not None:
            self._material_preview_enabled = bool(enabled)
        if azimuth_deg is not None:
            self._material_preview_light_azimuth_deg = max(
                -180.0, min(180.0, float(azimuth_deg))
            )
        if elevation_deg is not None:
            self._material_preview_light_elevation_deg = max(
                5.0, min(85.0, float(elevation_deg))
            )
        self._material_preview_cache = None
        self._sync_material_controls()
        if hasattr(self, "canvas"):
            self.canvas.update()
        return {
            "enabled": bool(self._material_preview_enabled),
            "azimuth_deg": float(self._material_preview_light_azimuth_deg),
            "elevation_deg": float(self._material_preview_light_elevation_deg),
        }

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
        if layer.layer_id == "paint-layer-3d-blockout":
            self._refresh_3d_blockout_overlay()
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
        if layer.layer_id == "paint-layer-3d-blockout":
            self._painter_3d_blockout_flat_cache = None
            self._refresh_3d_blockout_overlay()
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

    def _set_layer_color_label(self, layer_id: str | None, color_label: str) -> bool:
        layer = self._select_paint_layer_by_id(layer_id)
        if layer is None:
            return False
        label = _normalise_paint_layer_color_label(color_label)
        if _normalise_paint_layer_color_label(getattr(layer, "color_label", "none")) == label:
            return False
        self._push_undo_state("Set layer color label")
        layer.color_label = label
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
        new_material_action = menu.addAction("New Material Paint Layer")
        visibility_action = menu.addAction("Toggle Visibility")
        menu.addSeparator()
        copy_action = menu.addAction("Copy")
        cut_action = menu.addAction("Cut")
        paste_action = menu.addAction("Paste")
        duplicate_action = menu.addAction("Duplicate")
        color_menu = menu.addMenu("Layer Color")
        color_actions: dict[object, str] = {}
        for color_key, color_name, _hex in PAINT_LAYER_COLOR_LABELS:
            action = color_menu.addAction(color_name)
            color_actions[action] = color_key
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        selected = self._current_layer_id()
        selected_background = selected == "background" and self._background_layer_present
        has_selection = selected is not None and not selected_background
        is_paint_layer = self._is_paint_layer_id(selected)
        visibility_action.setEnabled(is_paint_layer)
        copy_action.setEnabled(has_selection)
        cut_action.setEnabled(self._can_cut_layer_id(selected))
        duplicate_action.setEnabled(has_selection)
        color_menu.setEnabled(is_paint_layer)
        delete_action.setEnabled(
            selected_background
            or (has_selection and (not is_paint_layer or len(self._paint_layers) > 1))
        )
        paste_action.setEnabled(self._clipboard_has_any_pasteable_content())
        chosen = menu.exec(self._layer_list.mapToGlobal(pos))
        if chosen is new_action:
            self._new_paint_layer()
        elif chosen is new_material_action:
            self._new_material_paint_layer()
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
        elif chosen in color_actions:
            self._set_layer_color_label(selected, color_actions[chosen])
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
        if not self._can_cut_layer_id(layer_id):
            return
        payload = self._payload_for_layer(layer_id)
        if payload is None:
            return
        self._paint_clipboard = payload
        self._write_payload_to_system_clipboard(payload)
        if self._is_paint_layer_id(layer_id) and len(self._paint_layers) <= 1:
            self._push_undo_state("Cut layer")
            self.canvas.clear_strokes_direct(str(layer_id))
            self._selected_layer_id = str(layer_id)
            self._update_inspector_counts()
            return
        self._delete_layer(layer_id)

    def _duplicate_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        payload = self._payload_for_layer(self._current_layer_id())
        if payload is None:
            return
        self._paste_payload(payload)

    def _paste_layer_clipboard(self) -> None:
        if self._text_editor_has_focus() and not self._clipboard_has_any_pasteable_content():
            return
        payload = self._payload_from_system_clipboard()
        if payload is not None:
            self._paint_clipboard = payload
            self._paste_payload(payload)
            return
        if self._system_clipboard_has_image_payload() and self._paste_system_clipboard_image():
            return
        payload = self._paint_clipboard
        if payload is not None:
            self._paste_payload(payload)

    def _delete_selected_layer(self) -> None:
        if self._text_editor_has_focus():
            return
        self._delete_layer(self._current_layer_id())

    def _can_cut_layer_id(self, layer_id: str | None) -> bool:
        if not layer_id or layer_id == "background":
            return False
        if self._is_paint_layer_id(layer_id):
            layer = self._paint_layer_by_id(layer_id)
            if layer is not None and layer.locked:
                return False
            return True
        return str(layer_id).startswith(("bubble:", "sticker:", "strokes"))

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

    def _clipboard_has_any_pasteable_content(self) -> bool:
        if self._paint_clipboard is not None or self._system_clipboard_has_paint_payload():
            return True
        return self._system_clipboard_has_image_payload()

    def _system_clipboard_has_image_payload(self) -> bool:
        try:
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData() if clipboard is not None else None
            if mime is None:
                return False
            if mime.hasImage():
                return True
            if mime.hasUrls():
                for url in mime.urls():
                    if self._clipboard_image_path_from_text(url.toLocalFile()):
                        return True
            if mime.hasText():
                return self._clipboard_image_path_from_text(mime.text()) is not None
        except Exception:
            return False
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
            preview_image = self._payload_to_system_clipboard_image(payload)
            if preview_image is not None and not preview_image.isNull():
                mime.setImageData(preview_image)
            mime.setText(f"Tiger Studio Paint {document.get('kind', 'payload')}")
            QApplication.clipboard().setMimeData(mime)
        except Exception:
            return

    def _payload_to_system_clipboard_image(self, payload: dict) -> QImage | None:
        kind = str(payload.get("kind") or "")
        if kind == "paint_layer":
            return self._strokes_to_clipboard_image(payload.get("strokes") or [])
        if kind == "strokes":
            return self._strokes_to_clipboard_image(payload.get("strokes") or [])
        if kind == "sticker":
            sticker = payload.get("sticker")
            path = str(getattr(sticker, "png_path", "") or "")
            if not path:
                return None
            image = QImage(path)
            if image.isNull():
                return None
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            opacity = max(0.0, min(1.0, float(getattr(sticker, "opacity", 100.0)) / 100.0))
            if opacity >= 0.999:
                return image
            out = QImage(image.width(), image.height(), QImage.Format.Format_ARGB32)
            out.fill(0)
            painter = QPainter(out)
            try:
                painter.setOpacity(opacity)
                painter.drawImage(0, 0, image)
            finally:
                painter.end()
            return out
        if kind == "bubble":
            bubble = payload.get("bubble")
            if bubble is None:
                return None
            width, height = self._canvas_document_size
            out_path = Path(tempfile.gettempdir()) / "tiger_painter_clipboard_bubble.png"
            if render_bubble_to_png(bubble, int(width), int(height), str(out_path)):
                image = QImage(str(out_path))
                return None if image.isNull() else image
        return None

    def _strokes_to_clipboard_image(self, strokes: list["Stroke"]) -> QImage | None:
        if not strokes:
            return None
        width, height = self._canvas_document_size
        image = QImage(max(1, int(width)), max(1, int(height)), QImage.Format.Format_ARGB32)
        image.fill(0)
        width_scale = image.width() / max(1, self.canvas.width())
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        try:
            for stroke in strokes:
                scaled_stroke = copy.copy(stroke)
                scaled_stroke.width_px = max(1.0, float(stroke.width_px) * width_scale)
                DrawingCanvas._paint_stroke(painter, scaled_stroke, image.width(), image.height())
        finally:
            painter.end()
        return image

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

    def _system_clipboard_image(self) -> tuple[QImage, str] | None:
        try:
            clipboard = QApplication.clipboard()
            mime = clipboard.mimeData() if clipboard is not None else None
            if clipboard is None or mime is None:
                return None
            if mime.hasImage():
                image_data = mime.imageData()
                if isinstance(image_data, QImage) and not image_data.isNull():
                    return image_data, "clipboard"
                if isinstance(image_data, QPixmap) and not image_data.isNull():
                    return image_data.toImage(), "clipboard"
                if hasattr(image_data, "toImage"):
                    converted = image_data.toImage()
                    if isinstance(converted, QImage) and not converted.isNull():
                        return converted, "clipboard"
            image = clipboard.image()
            if not image.isNull():
                return image, "clipboard"
            for url in (mime.urls() if mime.hasUrls() else []):
                path = self._clipboard_image_path_from_text(url.toLocalFile())
                if path is None:
                    continue
                image = QImage(str(path))
                if not image.isNull():
                    return image, path.stem
            if mime.hasText():
                path = self._clipboard_image_path_from_text(mime.text())
                if path is not None:
                    image = QImage(str(path))
                    if not image.isNull():
                        return image, path.stem
        except Exception:
            return None
        return None

    @staticmethod
    def _clipboard_image_path_from_text(text: str | None) -> Path | None:
        raw = str(text or "").strip()
        if not raw:
            return None
        if raw.startswith("file:///"):
            raw = raw[8:]
        raw = raw.strip().strip('"').strip("'")
        path = Path(raw)
        try:
            if path.exists() and path.is_file():
                return path
        except Exception:
            return None
        return None

    @staticmethod
    def _safe_clipboard_image_stem(label: str) -> str:
        cleaned = "".join(
            ch if ch.isalnum() or ch in {"-", "_"} else "_"
            for ch in str(label or "clipboard").strip()
        ).strip("_")
        return cleaned[:48] or "clipboard"

    def _write_clipboard_image_asset(self, image: QImage, label: str = "clipboard") -> Path | None:
        if image.isNull():
            return None
        out_dir = PAINT_CLIPBOARD_IMAGE_DIR
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        stem = self._safe_clipboard_image_stem(label)
        out_path = out_dir / f"{stem}_{stamp}.png"
        prepared = image.convertToFormat(QImage.Format.Format_ARGB32)
        if not prepared.save(str(out_path), "PNG"):
            return None
        return out_path

    def _paste_system_clipboard_image(self) -> bool:
        image_item = self._system_clipboard_image()
        if image_item is None:
            return False
        image, label = image_item
        path = self._write_clipboard_image_asset(image, label)
        if path is None:
            return False
        pm = QPixmap(str(path))
        if pm.isNull():
            return False
        canvas_w = max(1, self.canvas.width())
        canvas_h = max(1, self.canvas.height())
        target_w = min(pm.width(), int(canvas_w * 0.35))
        aspect = pm.height() / max(1, pm.width())
        target_h = int(round(target_w * aspect))
        if target_h > int(canvas_h * 0.5):
            target_h = int(canvas_h * 0.5)
            target_w = int(round(target_h / max(0.01, aspect)))
        target_w = max(16, min(target_w, max(16, canvas_w - 2)))
        target_h = max(16, min(target_h, max(16, canvas_h - 2)))
        sticker = Sticker(
            png_path=str(path.resolve()),
            x_norm=max(0.0, min(0.95, 0.5 - (target_w / canvas_w) / 2.0)),
            y_norm=max(0.0, min(0.95, 0.5 - (target_h / canvas_h) / 2.0)),
            width_norm=max(0.01, min(1.0, target_w / canvas_w)),
            height_norm=max(0.01, min(1.0, target_h / canvas_h)),
            start_ms=self._time_ms,
            end_ms=-1,
            z_index=max((s.z_index for s in self._stickers), default=0) + 1,
        )
        self._push_undo_state("Paste image")
        self._stickers.append(sticker)
        self._selected_layer_id = f"sticker:{len(self._stickers) - 1}"
        self._spawn_sticker_item(sticker)
        self._update_inspector_counts()
        self._set_tool("select")
        return True

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
            brush_style=_normalize_paint_brush_style(str(row.get("brush_style") or "round")),
            brush_hardness=max(1, min(100, self._clipboard_int(row.get("brush_hardness"), 100))),
            brush_spacing=max(1, min(200, self._clipboard_int(row.get("brush_spacing"), 25))),
            brush_angle=max(-180, min(180, self._clipboard_int(row.get("brush_angle"), 0))),
            brush_roundness=max(10, min(100, self._clipboard_int(row.get("brush_roundness"), 100))),
            brush_flip_x=bool(row.get("brush_flip_x", False)),
            brush_flip_y=bool(row.get("brush_flip_y", False)),
            closed_path=bool(row.get("closed_path", False)),
            layer_id=str(row.get("layer_id") or "paint-layer-1"),
            source_tool=str(row.get("source_tool") or "pen"),
            brush_engine_version=max(
                1, min(2, self._clipboard_int(row.get("brush_engine_version"), 1))
            ),
            point_pressure=[
                max(0.0, min(1.0, self._clipboard_float(value, 0.82)))
                for value in (row.get("point_pressure") or [])
            ],
            point_tilt=[
                max(0.0, min(1.0, self._clipboard_float(value, 0.5)))
                for value in (row.get("point_tilt") or [])
            ],
            point_tilt_x=[
                max(-1.0, min(1.0, self._clipboard_float(value, 0.0)))
                for value in (row.get("point_tilt_x") or [])
            ],
            point_tilt_y=[
                max(-1.0, min(1.0, self._clipboard_float(value, 0.0)))
                for value in (row.get("point_tilt_y") or [])
            ],
            point_rotation=[
                max(0.0, min(1.0, self._clipboard_float(value, 0.5)))
                for value in (row.get("point_rotation") or [])
            ],
            point_tangential_pressure=[
                max(-1.0, min(1.0, self._clipboard_float(value, 0.0)))
                for value in (row.get("point_tangential_pressure") or [])
            ],
            point_load=[
                max(0.0, min(1.0, self._clipboard_float(value, 1.0)))
                for value in (row.get("point_load") or [])
            ],
            bristle_count=max(0, min(64, self._clipboard_int(row.get("bristle_count"), 0))),
            brush_seed=self._clipboard_int(row.get("brush_seed"), 0),
            load_depletion=max(
                0.0, min(1.0, self._clipboard_float(row.get("load_depletion"), 0.28))
            ),
            start_ms=self._clipboard_int(row.get("start_ms"), 0),
            end_ms=None if end_ms is None else self._clipboard_int(end_ms, 0),
            material_enabled=bool(row.get("material_enabled", False)),
            material_load=max(0.0, min(1.0, self._clipboard_float(row.get("material_load"), 0.78))),
            material_thickness=max(
                0.0, min(1.0, self._clipboard_float(row.get("material_thickness"), 0.62))
            ),
            material_wetness=max(
                0.0, min(1.0, self._clipboard_float(row.get("material_wetness"), 0.34))
            ),
            material_gloss=max(
                0.0, min(1.0, self._clipboard_float(row.get("material_gloss"), 0.28))
            ),
            material_roughness=max(
                0.0, min(1.0, self._clipboard_float(row.get("material_roughness"), 0.56))
            ),
        )

    def _paint_layer_from_clipboard_dict(self, row: dict) -> PaintLayer:
        from app.painter_material_paint import (
            normalize_layer_type,
            normalize_material_settings,
        )
        from app.painter_wet_canvas import normalize_wet_canvas_settings

        if not isinstance(row, dict):
            row = {}
        layer_type = normalize_layer_type(row.get("layer_type"))
        return PaintLayer(
            layer_id=str(row.get("layer_id") or "paint-layer-1"),
            name=str(row.get("name") or "Layer"),
            visible=bool(row.get("visible", True)),
            opacity=max(0, min(100, self._clipboard_int(row.get("opacity"), 100))),
            locked=bool(row.get("locked", False)),
            blend_mode=str(row.get("blend_mode") or "normal"),
            mask=self._normalise_path_points(row.get("mask") or []),
            mask_enabled=bool(row.get("mask_enabled", False)),
            color_label=_normalise_paint_layer_color_label(row.get("color_label")),
            layer_type=layer_type,
            material_settings=(
                normalize_material_settings(row.get("material_settings"))
                if layer_type == "material"
                else {}
            ),
            wet_canvas_settings=(
                normalize_wet_canvas_settings(row.get("wet_canvas_settings"))
                if layer_type == "material"
                else {}
            ),
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
                color_label=_normalise_paint_layer_color_label(
                    getattr(source_layer, "color_label", "none")
                ),
                layer_type=str(getattr(source_layer, "layer_type", "standard") or "standard"),
                material_settings=copy.deepcopy(
                    getattr(source_layer, "material_settings", {}) or {}
                ),
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
            self._material_preview_cache = None
            self._pbr_preview_maps_cache = None
            self._sync_material_controls()
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

    def keyPressEvent(self, event) -> None:
        if str(getattr(self, "_canvas_workspace_mode", "paint")) == "3d_place":
            key = event.key()
            if key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
                focus = QApplication.focusWidget()
                if not isinstance(focus, (QLineEdit, QTextEdit, QSpinBox)):
                    self._nudge_3d_blockout_camera(key)
                    event.accept()
                    return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event) -> bool:
        shape_kind = str(obj.property("blockoutShapeKind") or "") if isinstance(obj, QPushButton) else ""
        if shape_kind:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._blockout_shape_drag_start = QPoint(event.position().toPoint())
            elif (
                event.type() == QEvent.Type.MouseMove
                and event.buttons() & Qt.MouseButton.LeftButton
                and getattr(self, "_blockout_shape_drag_start", None) is not None
            ):
                distance = (
                    event.position().toPoint()
                    - QPoint(self._blockout_shape_drag_start)
                ).manhattanLength()
                if distance >= QApplication.startDragDistance():
                    mime = QMimeData()
                    mime.setData(PAINT_BLOCKOUT_SHAPE_MIME, shape_kind.encode("ascii", "ignore"))
                    drag = QDrag(obj)
                    drag.setMimeData(mime)
                    drag.exec(Qt.DropAction.CopyAction)
                    self._blockout_shape_drag_start = None
                    return True
        channel_list = getattr(self, "_channel_list", None)
        if channel_list is not None and obj is channel_list.viewport():
            if self._handle_channel_list_event(event):
                return True
            return super().eventFilter(obj, event)
        layer_list = getattr(self, "_layer_list", None)
        if layer_list is not None and obj is layer_list.viewport():
            if self._handle_layer_list_event(event):
                return True
            return super().eventFilter(obj, event)
        canvas_widgets = (
            getattr(self, "_canvas_host", None),
            getattr(self, "_bg_label", None),
            getattr(self, "canvas", None),
        )
        if obj not in canvas_widgets:
            return super().eventFilter(obj, event)
        event_type = event.type()
        placement_mode = str(getattr(self, "_canvas_workspace_mode", "paint")) == "3d_place"
        if event_type in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
            if event.mimeData().hasFormat(PAINT_BLOCKOUT_SHAPE_MIME):
                event.acceptProposedAction()
                return True
        if event_type == QEvent.Type.Drop and event.mimeData().hasFormat(PAINT_BLOCKOUT_SHAPE_MIME):
            kind = bytes(event.mimeData().data(PAINT_BLOCKOUT_SHAPE_MIME)).decode("ascii", "ignore")
            local = self._canvas_local_point_from_widget(obj, event.position().toPoint())
            canvas = getattr(self, "canvas", None)
            if local is not None and canvas is not None:
                from app.painter_3d_blockout import screen_to_blockout_ground

                world = screen_to_blockout_ground(
                    self._current_3d_blockout_scene(),
                    local.x(),
                    local.y(),
                    canvas.width(),
                    canvas.height(),
                )
                self._add_3d_blockout_primitive(kind, world_position=world)
                event.acceptProposedAction()
                return True
        if placement_mode and event_type == QEvent.Type.Wheel:
            self._zoom_3d_blockout_camera(event.angleDelta().y())
            event.accept()
            return True
        if placement_mode and event_type == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D):
                self._nudge_3d_blockout_camera(key)
                event.accept()
                return True
        if event_type == QEvent.Type.ContextMenu:
            try:
                self._show_canvas_context_menu(event.globalPos())
                event.accept()
                return True
            except Exception:
                return False
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            if placement_mode:
                host = getattr(self, "_canvas_host", None)
                if host is not None:
                    host.setFocus(Qt.FocusReason.MouseFocusReason)
            if self._begin_3d_blockout_drag(obj, event.position().toPoint()):
                event.accept()
                return True
        if event_type == QEvent.Type.MouseMove and getattr(self, "_painter_3d_blockout_drag", None):
            self._update_3d_blockout_drag(obj, event.position().toPoint())
            event.accept()
            return True
        if (
            event_type == QEvent.Type.MouseButtonRelease
            and event.button() == Qt.MouseButton.LeftButton
            and getattr(self, "_painter_3d_blockout_drag", None)
        ):
            self._finish_3d_blockout_drag()
            event.accept()
            return True
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

    def _zoom_3d_blockout_camera(self, wheel_delta: int) -> None:
        from app.painter_3d_blockout import update_blockout_camera

        scene = self._current_3d_blockout_scene()
        direction = -1.0 if int(wheel_delta) > 0 else 1.0
        distance = max(0.25, min(30.0, scene.camera.distance + direction * 0.45))
        self._store_3d_blockout_scene(update_blockout_camera(scene, distance=distance))

    def _nudge_3d_blockout_camera(self, key: int) -> None:
        from math import cos, radians, sin

        from app.painter_3d_blockout import update_blockout_camera

        scene = self._current_3d_blockout_scene()
        target_x, target_y, target_z = scene.camera.target
        yaw = radians(scene.camera.yaw_degrees)
        forward = (sin(yaw), cos(yaw))
        right = (cos(yaw), -sin(yaw))
        step = 0.22
        if key == Qt.Key.Key_W:
            target_x += forward[0] * step
            target_y += forward[1] * step
        elif key == Qt.Key.Key_S:
            target_x -= forward[0] * step
            target_y -= forward[1] * step
        elif key == Qt.Key.Key_D:
            target_x += right[0] * step
            target_y += right[1] * step
        elif key == Qt.Key.Key_A:
            target_x -= right[0] * step
            target_y -= right[1] * step
        self._store_3d_blockout_scene(
            update_blockout_camera(
                scene,
                target_x=target_x,
                target_y=target_y,
                target_z=target_z,
            )
        )

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
        cut_action.setEnabled(self._can_cut_layer_id(selected))
        paste_action.setEnabled(self._clipboard_has_any_pasteable_content())
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
        preserved_workspace = str(
            getattr(self, "_canvas_workspace_mode", "paint") or "paint"
        )
        workspace_generation = int(
            getattr(self, "_canvas_workspace_user_generation", 0)
        )
        super().resizeEvent(event)
        self._sync_color_panel_layout()
        self._update_canvas_geometry()
        if preserved_workspace == "3d_place":
            self._restore_3d_workspace_after_resize(
                preserved_workspace,
                workspace_generation,
            )
            QTimer.singleShot(
                80,
                lambda mode=preserved_workspace, generation=workspace_generation: (
                    self._restore_3d_workspace_after_resize(mode, generation)
                ),
            )

    def _restore_3d_workspace_after_resize(
        self,
        expected_mode: str,
        expected_generation: int,
    ) -> None:
        if str(expected_mode or "") != "3d_place":
            return
        if int(getattr(self, "_canvas_workspace_user_generation", 0)) != int(
            expected_generation
        ):
            return
        self._canvas_workspace_mode = "3d_place"
        self._active_ui_tool = "3d_blockout"
        if hasattr(self, "canvas"):
            self.canvas.set_tool("off")
        self._sync_canvas_workspace_mode_controls()
        self._refresh_3d_blockout_overlay()

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self.isVisible() or not bool(getattr(self, "_move_refresh_pause_enabled", False)):
            return
        if not bool(getattr(self, "_move_refresh_paused", False)):
            self._move_refresh_paused = True
            self.setUpdatesEnabled(False)
        timer = getattr(self, "_move_refresh_pause_timer", None)
        if timer is not None:
            timer.start()

    def _finish_window_move_refresh_pause(self) -> None:
        if not bool(getattr(self, "_move_refresh_paused", False)):
            return
        self._move_refresh_paused = False
        self.setUpdatesEnabled(True)
        self._update_canvas_geometry()
        self.update()

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
            zoom = float(getattr(self, "_canvas_zoom", 1.0) or 1.0)
            transform_mode = (
                Qt.TransformationMode.FastTransformation
                if int(round(zoom * 100.0)) >= 400
                else Qt.TransformationMode.SmoothTransformation
            )
            bg_base = display_bg.scaled(
                hw, hh,
                Qt.AspectRatioMode.KeepAspectRatio,
                transform_mode,
            )
            base_width = max(1, bg_base.width())
            base_height = max(1, bg_base.height())
        else:
            zoom = float(getattr(self, "_canvas_zoom", 1.0) or 1.0)
            bg_base = QPixmap()
            base_width = max(1, hw)
            base_height = max(1, hh)

        self._bg_label.setPixmap(bg_base)
        self._bg_label.setScaledContents(True)
        # Position the bg_label centered in the host
        bw = max(1, int(round(base_width * zoom)))
        bh = max(1, int(round(base_height * zoom)))
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
        self.canvas.set_document_size(*self._canvas_document_size)
        self.canvas.set_view_zoom_percent(int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100)))
        ui_overlay = getattr(self, "_painter_ui_overlay", None)
        if ui_overlay is not None:
            if str(getattr(self, "_canvas_workspace_mode", "paint")) == "ui_design":
                ui_overlay.setGeometry(0, 0, hw, hh)
            else:
                ui_overlay.setGeometry(bx, by, bw, bh)
            self._refresh_painter_ui_overlay()
        self._refresh_reference_overlay()
        self._refresh_3d_blockout_overlay()
        self.canvas.raise_()
        if (
            ui_overlay is not None
            and str(getattr(self, "_canvas_workspace_mode", "paint")) == "ui_design"
        ):
            ui_overlay.raise_()
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

    def _painter_background_png_bytes(self) -> bytes | None:
        pixmap = getattr(self, "_bg_pixmap_source", QPixmap())
        if pixmap is None or pixmap.isNull():
            return None
        from PySide6.QtCore import QBuffer

        data = QByteArray()
        buffer = QBuffer(data)
        if not buffer.open(QBuffer.OpenModeFlag.WriteOnly):
            return None
        try:
            if not pixmap.save(buffer, "PNG"):
                return None
        finally:
            buffer.close()
        return bytes(data)

    def _painter_document_payload(self) -> dict:
        return {
            "document": {
                "width": int(self._canvas_document_size[0]),
                "height": int(self._canvas_document_size[1]),
                "time_ms": int(self._time_ms),
                "paint_layer_serial": int(self._paint_layer_serial),
                "active_layer_id": str(self._active_paint_layer_id),
                "selected_layer_id": str(self._selected_layer_id or ""),
            },
            "background": {
                "present": bool(self._background_layer_present),
                "color": self._background_color.name(QColor.NameFormat.HexRgb),
            },
            "layers": [asdict(layer) for layer in self._paint_layers],
            "strokes": [
                asdict(stroke)
                for stroke in (
                    self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
                )
            ],
            "bubbles": [asdict(bubble) for bubble in self._bubbles],
            "stickers": [asdict(sticker) for sticker in self._stickers],
            "selection": {
                "points": (
                    self.canvas.selection_snapshot() if hasattr(self, "canvas") else []
                ),
                "inverted": bool(
                    self.canvas.selection_inverted() if hasattr(self, "canvas") else False
                ),
                "aspect_mode": str(self._selection_aspect_mode),
                "combine_mode": str(self._selection_combine_mode),
                "quick_mask": bool(self._quick_mask_enabled),
            },
            "paths": {
                "work_path": (
                    self.canvas.path_snapshot() if hasattr(self, "canvas") else []
                ),
                "selected_path_id": str(self._selected_path_item_id),
            },
            "channels": {
                "visibility": dict(self._channel_visibility),
                "selected": str(self._selected_channel),
            },
            "view": {
                "zoom": float(self._canvas_zoom),
                "pan": [int(self._canvas_pan.x()), int(self._canvas_pan.y())],
                "grid_visible": bool(self._grid_visible),
                "snap_to_grid": bool(self._snap_to_grid),
                "grid_size_px": int(self._grid_size_px),
                "mirror_x": bool(self._mirror_x_enabled),
                "mirror_y": bool(self._mirror_y_enabled),
            },
            "brush": {
                "color": self._pen_color.name(QColor.NameFormat.HexRgb),
                "width": float(self._pen_width),
                "opacity": int(self._pen_opacity),
                "style": str(self._pen_style),
                "detail": dict(self._brush_detail_settings),
                "active_preset_index": int(self._active_brush_preset_index),
            },
            "material_preview": {
                "enabled": bool(self._material_preview_enabled),
                "azimuth_deg": float(self._material_preview_light_azimuth_deg),
                "elevation_deg": float(self._material_preview_light_elevation_deg),
            },
            "pbr": {
                "settings": dict(self._pbr_texture_settings),
                "source_path": str(self._pbr_source_path or ""),
            },
            "reference_board": copy.deepcopy(self._painter_reference_board),
            "reference_selected_id": str(self._painter_reference_selected_id),
            "blockout_3d": copy.deepcopy(self._painter_3d_blockout_scene),
            "blockout_selected_id": str(self._painter_3d_blockout_selected_id),
            "ui_document": copy.deepcopy(self._painter_ui_document),
            "workspace": {
                "mode": str(self._canvas_workspace_mode),
                "transform_mode": str(self._blockout_transform_mode),
                "active_axis": str(self._blockout_active_axis),
            },
        }

    def save_document_to_path(self, path: str | Path) -> dict:
        from app.painter_document_io import save_painter_document

        report = save_painter_document(
            path,
            self._painter_document_payload(),
            background_png=self._painter_background_png_bytes(),
        )
        self._painter_document_path = str(report["path"])
        self._painter_document_dirty = False
        report["layer_count"] = len(self._paint_layers)
        report["stroke_count"] = len(self.canvas.embedded_strokes())
        report["blockout_primitive_count"] = len(
            (
                self._painter_3d_blockout_scene
                if isinstance(self._painter_3d_blockout_scene, dict)
                else {}
            ).get("primitives", [])
        )
        self.setWindowTitle(f"{Path(report['path']).name} - Tiger Studio Painter")
        return report

    def _prompt_save_painter_document(self, *, save_as: bool = False) -> dict | None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        path = "" if save_as else str(self._painter_document_path or "")
        if not path:
            try:
                from app.paths import default_save_dir

                initial = default_save_dir() / "Untitled.tspaint"
            except Exception:
                initial = Path.home() / "Untitled.tspaint"
            path, _selected = QFileDialog.getSaveFileName(
                self,
                "Save Tiger Studio Painter Document",
                str(initial),
                "Tiger Studio Painter (*.tspaint)",
            )
        if not path:
            return None
        try:
            report = self.save_document_to_path(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Save Painter Document",
                f"Save failed: {type(exc).__name__}: {exc}",
            )
            return None
        return report

    def _prompt_open_painter_document(self) -> dict | None:
        from PySide6.QtWidgets import QFileDialog, QMessageBox

        path, _selected = QFileDialog.getOpenFileName(
            self,
            "Open Tiger Studio Painter Document",
            str(Path(self._painter_document_path).parent)
            if self._painter_document_path
            else str(Path.home()),
            "Tiger Studio Painter (*.tspaint)",
        )
        if not path:
            return None
        try:
            return self.open_document_from_path(path)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Open Painter Document",
                f"Open failed: {type(exc).__name__}: {exc}",
            )
            return None

    def open_document_from_path(self, path: str | Path) -> dict:
        from app.painter_document_io import load_painter_document

        payload, report = load_painter_document(path)
        document = payload.get("document")
        if not isinstance(document, dict):
            raise ValueError("Painter document state is missing")
        layers = [
            self._paint_layer_from_clipboard_dict(row)
            for row in payload.get("layers") or []
            if isinstance(row, dict)
        ]
        if not layers:
            layers = [PaintLayer("paint-layer-1", "Layer 1")]
        strokes = self._strokes_from_clipboard_list(payload.get("strokes"))
        bubbles = [
            self._bubble_from_clipboard_dict(row)
            for row in payload.get("bubbles") or []
            if isinstance(row, dict)
        ]
        stickers = [
            self._sticker_from_clipboard_dict(row)
            for row in payload.get("stickers") or []
            if isinstance(row, dict)
        ]
        width = max(1, int(document.get("width", 1920) or 1920))
        height = max(1, int(document.get("height", 1080) or 1080))
        background = payload.get("background")
        background = background if isinstance(background, dict) else {}
        background_pixmap = QPixmap(str(background.get("asset") or ""))
        if background_pixmap.isNull():
            background_pixmap = create_blank_paint_pixmap(
                width,
                height,
                str(background.get("color") or "transparent"),
            )
        selection = payload.get("selection")
        selection = selection if isinstance(selection, dict) else {}
        channels = payload.get("channels")
        channels = channels if isinstance(channels, dict) else {}
        paths = payload.get("paths")
        paths = paths if isinstance(paths, dict) else {}
        active_layer_id = str(
            document.get("active_layer_id")
            or layers[-1].layer_id
        )
        if not any(layer.layer_id == active_layer_id for layer in layers):
            active_layer_id = layers[-1].layer_id
        snapshot = (
            strokes,
            bubbles,
            stickers,
            layers,
            active_layer_id,
            str(document.get("selected_layer_id") or active_layer_id),
            self._normalise_path_points(selection.get("points") or []),
            bool(background.get("present", False)),
            bool(selection.get("inverted", False)),
            dict(channels.get("visibility") or {}),
            str(paths.get("selected_path_id") or "work-path"),
            (width, height),
            background_pixmap,
            str(channels.get("selected") or "RGB"),
            str(selection.get("aspect_mode") or "free"),
            bool((payload.get("view") or {}).get("mirror_x", False)),
            bool((payload.get("view") or {}).get("mirror_y", False)),
            copy.deepcopy(payload.get("reference_board")),
            str(payload.get("reference_selected_id") or ""),
            copy.deepcopy(payload.get("blockout_3d")),
            str(payload.get("blockout_selected_id") or ""),
            self._normalise_path_points(paths.get("work_path") or []),
        )
        self._restore_state(snapshot)
        self._time_ms = int(document.get("time_ms", 0) or 0)
        self._paint_layer_serial = max(
            1,
            int(document.get("paint_layer_serial", len(layers)) or len(layers)),
        )
        self._background_color = QColor(str(background.get("color") or "#FFFFFF"))
        self._selection_combine_mode = str(selection.get("combine_mode") or "new")
        self._quick_mask_enabled = bool(selection.get("quick_mask", False))
        view = payload.get("view")
        view = view if isinstance(view, dict) else {}
        self._grid_visible = bool(view.get("grid_visible", False))
        self._snap_to_grid = bool(view.get("snap_to_grid", False))
        self._grid_size_px = max(2, int(view.get("grid_size_px", 64) or 64))
        self._canvas_zoom = max(0.25, min(8.0, float(view.get("zoom", 1.0) or 1.0)))
        pan = list(view.get("pan") or [0, 0])
        self._canvas_pan = QPoint(
            int(pan[0]) if len(pan) > 0 else 0,
            int(pan[1]) if len(pan) > 1 else 0,
        )
        brush = payload.get("brush")
        brush = brush if isinstance(brush, dict) else {}
        self._pen_color = QColor(str(brush.get("color") or "#EEF2F7"))
        self._pen_width = max(1.0, float(brush.get("width", 6.0) or 6.0))
        self._pen_opacity = max(0, min(255, int(brush.get("opacity", 255) or 255)))
        self._pen_style = _normalize_paint_brush_style(
            str(brush.get("style") or "round")
        )
        self._brush_detail_settings.update(dict(brush.get("detail") or {}))
        self._active_brush_preset_index = max(
            0,
            min(
                len(BRUSH_LIBRARY_PRESETS) - 1,
                int(brush.get("active_preset_index", 0) or 0),
            ),
        )
        material_preview = payload.get("material_preview")
        material_preview = (
            material_preview if isinstance(material_preview, dict) else {}
        )
        self._material_preview_enabled = bool(
            material_preview.get("enabled", False)
        )
        self._material_preview_light_azimuth_deg = float(
            material_preview.get("azimuth_deg", -38.0) or -38.0
        )
        self._material_preview_light_elevation_deg = float(
            material_preview.get("elevation_deg", 48.0) or 48.0
        )
        pbr = payload.get("pbr")
        pbr = pbr if isinstance(pbr, dict) else {}
        self._pbr_texture_settings.update(dict(pbr.get("settings") or {}))
        self._pbr_source_path = str(pbr.get("source_path") or "")
        from app.painter_ui_document import normalize_ui_document

        self._painter_ui_document = normalize_ui_document(
            payload.get("ui_document"),
            fallback_width=width,
            fallback_height=height,
        )
        workspace = payload.get("workspace")
        workspace = workspace if isinstance(workspace, dict) else {}
        self._canvas_workspace_mode = str(workspace.get("mode") or "paint")
        self._blockout_transform_mode = str(
            workspace.get("transform_mode") or "move"
        )
        self._blockout_active_axis = str(workspace.get("active_axis") or "")
        self._painter_document_path = str(Path(path).resolve())
        self._painter_document_asset_root = str(report.get("asset_root") or "")
        self._painter_document_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._undo_labels.clear()
        self._redo_labels.clear()
        self._sync_canvas_layer_view()
        self._sync_material_controls()
        self._update_canvas_geometry()
        self._sync_canvas_workspace_mode_controls()
        self.canvas.set_path_snapshot(
            self._normalise_path_points(paths.get("work_path") or [])
        )
        self._update_inspector_counts()
        self._update_history_buttons()
        self.setWindowTitle(
            f"{Path(self._painter_document_path).name} - Tiger Studio Painter"
        )
        report["layer_count"] = len(layers)
        report["stroke_count"] = len(strokes)
        report["blockout_primitive_count"] = len(
            (
                self._painter_3d_blockout_scene
                if isinstance(self._painter_3d_blockout_scene, dict)
                else {}
            ).get("primitives", [])
        )
        return report

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
            paint_layers=self._paint_layers,
        )

    def painter_action_state(self) -> dict:
        path_strokes = [
            stroke
            for stroke in (self.canvas.embedded_strokes() if hasattr(self, "canvas") else [])
            if str(getattr(stroke, "source_tool", "") or "") == "path"
        ]
        pixel_grid = (
            self.canvas.pixel_grid_state()
            if hasattr(self, "canvas") and hasattr(self.canvas, "pixel_grid_state")
            else {
                "auto": True,
                "visible": False,
                "cell_width_px": 0.0,
                "cell_height_px": 0.0,
                "stride_x": 0,
                "stride_y": 0,
                "major_every": 0,
            }
        )
        perspective_guides = (
            self.canvas.perspective_guide_state()
            if hasattr(self, "canvas") and hasattr(self.canvas, "perspective_guide_state")
            else {"enabled": False}
        )
        symmetry_guide = (
            self.canvas.symmetry_guide_state()
            if hasattr(self, "canvas") and hasattr(self.canvas, "symmetry_guide_state")
            else {"enabled": False}
        )
        try:
            from app.painter_opengl import painter_canvas_gpu_capabilities

            gpu_capabilities = painter_canvas_gpu_capabilities()
        except Exception:
            gpu_capabilities = {
                "remote_safe": True,
                "persistent_stroke_atlas": {"enabled": False, "fallback_renderer": "painter_canvas_qpainter_strokes_v1"},
            }
        from app.painter_ui_document import inspect_ui_document

        ui_design_state = inspect_ui_document(
            getattr(self, "_painter_ui_document", None)
        )
        return {
            "schema": "tigerstudio.paint.state.v1",
            "standalone": bool(self._standalone),
            "document": {
                "width": int(self._canvas_document_size[0]),
                "height": int(self._canvas_document_size[1]),
                "background_layer_present": bool(self._background_layer_present),
                "path": str(getattr(self, "_painter_document_path", "") or ""),
                "dirty": bool(getattr(self, "_painter_document_dirty", False)),
                "native_format": "tigerstudio.painter.document.v1",
                "native_extension": ".tspaint",
                "persists_3d_blockout": True,
            },
            "view": {
                "zoom_percent": int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100)),
                "pan_x": int(getattr(self, "_canvas_pan", QPoint(0, 0)).x()),
                "pan_y": int(getattr(self, "_canvas_pan", QPoint(0, 0)).y()),
                "grid_visible": bool(getattr(self, "_grid_visible", False)),
                "snap_to_grid": bool(getattr(self, "_snap_to_grid", False)),
                "grid_size_px": int(getattr(self, "_grid_size_px", 64)),
                "pixel_grid_auto": bool(pixel_grid.get("auto", True)),
                "pixel_grid_visible": bool(pixel_grid.get("visible", False)),
                "pixel_grid_cell_width_px": float(pixel_grid.get("cell_width_px", 0.0) or 0.0),
                "pixel_grid_cell_height_px": float(pixel_grid.get("cell_height_px", 0.0) or 0.0),
                "pixel_grid_stride_x": int(pixel_grid.get("stride_x", 0) or 0),
                "pixel_grid_stride_y": int(pixel_grid.get("stride_y", 0) or 0),
            },
            "layers": [
                {
                    "layer_id": layer.layer_id,
                    "name": layer.name,
                    "visible": bool(layer.visible),
                    "opacity": int(layer.opacity),
                    "locked": bool(layer.locked),
                    "blend_mode": str(getattr(layer, "blend_mode", "normal") or "normal"),
                    "layer_type": str(
                        getattr(layer, "layer_type", "standard") or "standard"
                    ),
                    "material_settings": dict(
                        getattr(layer, "material_settings", {}) or {}
                    ),
                    "wet_canvas_settings": dict(
                        getattr(layer, "wet_canvas_settings", {}) or {}
                    ),
                    "color_label": _normalise_paint_layer_color_label(
                        getattr(layer, "color_label", "none")
                    ),
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
            "workspace": {
                "mode": str(
                    getattr(self, "_canvas_workspace_mode", "paint") or "paint"
                ),
                "available_modes": ["paint", "ui_design", "3d_place"],
            },
            "ui_design": ui_design_state,
            "tool": str(getattr(self.canvas, "_tool", "off") if hasattr(self, "canvas") else "off"),
            "ui_tool": str(getattr(self, "_active_ui_tool", "select")),
            "brush": {
                "style": _normalize_paint_brush_style(
                    getattr(self.canvas, "_pen_style", getattr(self, "_pen_style", "round"))
                    if hasattr(self, "canvas")
                    else getattr(self, "_pen_style", "round")
                ),
                "width_px": float(getattr(self, "_pen_width", 0.0)),
                "opacity": int(round(float(getattr(self, "_pen_opacity", 255)) * 100.0 / 255.0)),
                "detail": dict(getattr(self, "_brush_detail_settings", BRUSH_DETAIL_DEFAULTS)),
                "library": {
                    "id": "tiger_studio",
                    "name": "Tiger Studio Brushes",
                    "preset_count": len(BRUSH_LIBRARY_PRESETS),
                    "active_preset_index": int(
                        getattr(self, "_active_brush_preset_index", 0)
                    ),
                    "favorite_count": len(getattr(self, "_brush_favorites", set())),
                    "recent_indices": list(getattr(self, "_brush_recent_indices", [])),
                    "filter": next(
                        iter(sorted(getattr(self, "_brush_active_filters", set()))),
                        "",
                    ),
                    "filters": sorted(getattr(self, "_brush_active_filters", set())),
                    "compact": bool(getattr(self, "_brush_selector_compact", False)),
                    "search": str(
                        getattr(self, "_brush_search_edit", None).text()
                        if getattr(self, "_brush_search_edit", None) is not None
                        else ""
                    ),
                },
                "engine": {
                    "version": 2,
                    "preset_thumbnail_mode": "actual_stroke_preview",
                    "active_sections": sorted(BRUSH_DETAIL_ACTIVE_SECTIONS),
                    "pressure_curve": "per_point_normalized_v2",
                    "dynamic_channels": [
                        "pressure",
                        "tilt",
                        "tilt_x",
                        "tilt_y",
                        "rotation",
                        "tangential_pressure",
                        "load",
                    ],
                    "bristle_strands": "shared_color_material_paths_v2",
                    "smoothing": "bounded_256_point_lane_resampling",
                    "texture_dynamics": "qpainter_v2_with_gpu_fallback_contract",
                    "gpu_texture_parity": gpu_capabilities.get("texture_brush_gpu_parity", {}),
                },
                "material": {
                    "settings": dict(getattr(self, "_material_paint_settings", {})),
                    "active_layer_is_material": str(
                        getattr(self._active_paint_layer(), "layer_type", "standard")
                    )
                    == "material",
                    "wet_canvas": dict(
                        getattr(
                            self._active_paint_layer(),
                            "wet_canvas_settings",
                            {},
                        )
                        or {}
                    ),
                },
            },
            "material_preview": {
                "enabled": bool(getattr(self, "_material_preview_enabled", False)),
                "azimuth_deg": float(
                    getattr(self, "_material_preview_light_azimuth_deg", -38.0)
                ),
                "elevation_deg": float(
                    getattr(self, "_material_preview_light_elevation_deg", 48.0)
                ),
                "renderer": "painter_material_heightfield_preview_v1",
                "native_channels": [
                    "height",
                    "normal",
                    "roughness",
                    "ao",
                    "direction",
                ],
                "stroke_count": sum(
                    1
                    for stroke in (
                        self.canvas.embedded_strokes() if hasattr(self, "canvas") else []
                    )
                    if bool(getattr(stroke, "material_enabled", False))
                ),
                "wet_canvas_reports": dict(
                    getattr(self.canvas, "_wet_canvas_reports", {})
                    if hasattr(self, "canvas")
                    else {}
                ),
            },
            "selection_aspect": str(getattr(self, "_selection_aspect_mode", "free")),
            "mirror": {
                "x": bool(getattr(self, "_mirror_x_enabled", False)),
                "y": bool(getattr(self, "_mirror_y_enabled", False)),
            },
            "guides": {
                "perspective": perspective_guides,
                "symmetry": symmetry_guide,
            },
            "channels": dict(self._channel_visibility),
            "selected_channel": str(getattr(self, "_selected_channel", "RGB")),
            "selection": {
                "active": bool(self.canvas.has_active_selection()) if hasattr(self, "canvas") else False,
                "point_count": int(self.canvas.selection_point_count()) if hasattr(self, "canvas") else 0,
                "inverted": bool(self.canvas.selection_inverted()) if hasattr(self, "canvas") else False,
                "quick_mask_enabled": bool(getattr(self, "_quick_mask_enabled", False)),
                "magic_tolerance": int(getattr(self, "_magic_select_tolerance", 32)),
                "combine_mode": str(getattr(self, "_selection_combine_mode", "new")),
            },
            "paths": {
                "selected_path_id": str(self._selected_path_item_id),
                "work_path_points": int(self.canvas.path_point_count()) if hasattr(self, "canvas") else 0,
                "saved_path_count": len(path_strokes),
            },
            "references": {
                **self._current_reference_board().to_dict(),
                "selected_reference_id": str(getattr(self, "_painter_reference_selected_id", "") or ""),
                "overlay_visible": bool(getattr(self, "reference_overlay_btn", None) and self.reference_overlay_btn.isChecked()),
            },
            "gpu": {
                "policy": "auto_opengl_with_qpainter_fallback",
                "remote_safe": True,
                "capabilities": gpu_capabilities,
                "blockout_renderer": dict(getattr(self, "_painter_3d_blockout_renderer_status", {}) or {}),
                "canvas_renderer": dict(
                    getattr(
                        getattr(self, "canvas", None),
                        "_painter_canvas_renderer_status",
                        getattr(self, "_painter_canvas_renderer_status", {}),
                    )
                    or {}
                ),
                "paint_canvas_renderer": "opengl_persistent_stroke_atlas_with_qpainter_fallback",
                "paint_canvas_next_gpu_target": "retained_gl_texture_display_and_textured_brush_shader_parity",
                "high_zoom": {
                    "max_zoom_percent": PAINT_MAX_ZOOM_PERCENT,
                    "current_zoom_percent": int(round(float(getattr(self, "_canvas_zoom", 1.0)) * 100)),
                    "pixel_grid_visible": bool(pixel_grid.get("visible", False)),
                    "pixel_grid_stride_x": int(pixel_grid.get("stride_x", 0) or 0),
                    "pixel_grid_stride_y": int(pixel_grid.get("stride_y", 0) or 0),
                    "dirty_region_policy": "signature_atlas_cache_plus_visible_pixel_grid_clip",
                    "display_path": "qwidget_blit_current_retained_gl_texture_next",
                },
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
