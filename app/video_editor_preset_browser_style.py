from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

from app.style import editor_scrollbar_qss


PRESET_TILE = 34
PRESET_TILE_GAP = 6


def make_pack_icon(seed: str) -> QIcon:
    """Return the compact neutral pack icon used by preset browsers."""
    _ = seed
    pix = QPixmap(22, 16)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    for idx, color in enumerate(("#464A51", "#363A42", "#282B32")):
        painter.setPen(QPen(QColor(255, 255, 255, 58), 1))
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(QRect(1 + idx * 7, 2, 7, 12), 3, 3)
    painter.end()
    return QIcon(pix)


def pack_palette_button_style(seed: str) -> str:
    """Shared compact pack button style for icon-first preset palettes."""
    _ = seed
    return (
        "QToolButton{"
        "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #40444B,stop:.54 #30343B,stop:1 #22252A);"
        "border:1px solid rgba(255,255,255,44);border-radius:7px;color:#F3F4F6;font-size:8px;font-weight:700;"
        "}"
        "QToolButton:hover{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #4B5058,stop:.54 #373C44,stop:1 #262A31);border:1px solid rgba(255,255,255,112);}"
        "QToolButton:checked{border:1px solid rgba(245,247,251,128);background:#373D46;}"
    )


def preset_scroll_grid_qss() -> str:
    return (
        "QScrollArea#PresetScrollGrid{background:#101112;border:none;border-radius:0px;}"
        "QScrollArea#PresetScrollGrid > QWidget > QWidget{background:#101112;}"
        + editor_scrollbar_qss("QScrollArea#PresetScrollGrid")
    )


def preset_search_qss() -> str:
    return (
        "QLineEdit#PresetSearch{background:#111316;border:1px solid rgba(220,225,238,22);border-radius:7px;"
        "color:#DDE1E8;padding:3px 9px;font-size:10px;}"
        "QLineEdit#PresetSearch:focus{border-color:rgba(230,235,245,84);background:#15181D;}"
    )


def preset_pack_combo_qss() -> str:
    return (
        "QComboBox#PresetPackCombo{background:#111316;border:1px solid #30363D;"
        "border-radius:6px;color:#DCE2EA;padding:3px 22px 3px 9px;font-size:10px;font-weight:650;}"
        "QComboBox#PresetPackCombo:hover{background:#15181D;border-color:#68717E;}"
        "QComboBox#PresetPackCombo::drop-down{border:none;width:20px;}"
    )


def preset_category_combo_qss() -> str:
    return (
        "QComboBox#PresetCategoryCombo{background:#111316;"
        "border:1px solid #30363D;border-radius:6px;color:#F1F3F7;"
        "padding:3px 20px 3px 9px;font-size:10px;font-weight:650;}"
        "QComboBox#PresetCategoryCombo:hover{background:#15181D;border-color:#68717E;}"
        "QComboBox#PresetCategoryCombo::drop-down{border:none;width:18px;}"
        "QComboBox#PresetCategoryCombo::down-arrow{image:none;border:none;}"
    )


def preset_category_filter_button_qss() -> str:
    return (
        "QToolButton#PresetCategoryFilterButton{background:#15181D;border:1px solid rgba(220,225,238,24);"
        "border-radius:7px;padding:0px;color:#E5E8EF;}"
        "QToolButton#PresetCategoryFilterButton:hover{background:#20252B;border-color:rgba(230,235,245,82);}"
        "QToolButton#PresetCategoryFilterButton::menu-indicator{image:none;width:0px;}"
    )


def preset_menu_qss() -> str:
    return (
        "QMenu{background:#111316;border:1px solid #30363D;border-radius:7px;color:#E8EAF1;padding:5px;}"
        "QMenu::item{padding:6px 24px 6px 9px;border-radius:5px;font-size:10px;}"
        "QMenu::item:selected{background:#20252B;color:#FFFFFF;}"
        "QMenu::indicator{width:10px;height:10px;}"
    )
