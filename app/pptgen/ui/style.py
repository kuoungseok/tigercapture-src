"""Shared QSS for the standalone PPT editor UI."""
from __future__ import annotations

from app.style import (
    COLOR_ACCENT,
    COLOR_ACCENT_HOVER,
    COLOR_APP_BG,
    COLOR_BG_L2,
    COLOR_BG_L5,
    COLOR_BG_L6,
    COLOR_BORDER_DEFAULT,
    COLOR_BORDER_FOCUS,
    COLOR_BORDER_SUBTLE,
    COLOR_PANEL_BG,
    COLOR_PANEL_BG_ALT,
    COLOR_PANEL_HEADER,
    COLOR_PANEL_RAIL,
    COLOR_TEXT_DISABLED,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_TIMELINE_BG,
    COLOR_TIMELINE_STRIPE,
    FONT_FAMILY,
    editor_scrollbar_qss,
)


PPT_EDITOR_QSS = f"""
* {{
    font-family: {FONT_FAMILY};
    letter-spacing: 0px;
}}

QWidget#PptEditorRoot {{
    background-color: {COLOR_APP_BG};
    color: {COLOR_TEXT_SECONDARY};
}}

QWidget#PptCommandBar,
QFrame#PptTextFormatBar,
QFrame#InsertToolbox,
QFrame#PptAnimationPanel,
QFrame#PptElementTools,
QWidget#PptLeftDock,
QWidget#PptRightDock,
QFrame#PptCanvasFrame {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QWidget#PptCommandBar {{
    min-height: 42px;
}}

QWidget#PptCenterWorkbench {{
    background-color: {COLOR_APP_BG};
    border: none;
}}

QWidget#PptLeftDock,
QWidget#PptRightDock {{
    background-color: {COLOR_PANEL_RAIL};
}}

QFrame#PptCanvasFrame {{
    background-color: {COLOR_PANEL_BG_ALT};
}}

QFrame#PptAnimationPanel {{
    background-color: {COLOR_PANEL_BG};
}}

QLabel#PptWindowTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 15px;
    font-weight: 800;
}}

QLabel#PptWindowSubtitle,
QLabel#PptSectionCaption {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 10px;
}}

QLabel#PptDeckTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 12px;
    font-weight: 700;
}}

QLabel#PptBadge {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 4px;
    padding: 3px 7px;
    font-size: 10px;
    font-weight: 700;
}}

QLabel#PptSectionHeader,
QLabel#ToolbarGroupLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
}}

QLabel#PptPanelHint {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 10px;
}}

QSplitter::handle {{
    background-color: {COLOR_BORDER_SUBTLE};
}}

QSplitter::handle:hover {{
    background-color: {COLOR_BORDER_FOCUS};
}}

QPushButton,
QToolButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 600;
}}

QPushButton:hover,
QToolButton:hover {{
    background-color: {COLOR_BG_L6};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_FOCUS};
}}

QPushButton:pressed,
QToolButton:pressed {{
    background-color: {COLOR_PANEL_HEADER};
}}

QPushButton:disabled,
QToolButton:disabled {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}

QPushButton#PptPrimaryButton {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    border-color: {COLOR_ACCENT};
}}

QPushButton#PptPrimaryButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}

QPushButton#PptCommandButton {{
    padding-left: 9px;
    padding-right: 10px;
}}

QPushButton#PptInsertButton {{
    min-height: 28px;
    text-align: left;
    padding-left: 10px;
}}

QPushButton#PptElementToolButton {{
    min-height: 24px;
    padding-left: 6px;
    padding-right: 6px;
    font-size: 10px;
}}

QToolButton#PptFormatToggle {{
    min-width: 28px;
    max-width: 34px;
    padding-left: 5px;
    padding-right: 5px;
}}

QToolButton#PptFormatToggle:checked {{
    background-color: #3A2C26;
    color: #FFFFFF;
    border-color: {COLOR_ACCENT};
}}

QListWidget,
QPlainTextEdit,
QComboBox,
QSpinBox,
QDoubleSpinBox,
QLineEdit,
QTableWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 5px;
    selection-background-color: #3A2C26;
    selection-color: {COLOR_TEXT_PRIMARY};
}}

QListWidget:focus,
QPlainTextEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QLineEdit:focus,
QTableWidget:focus {{
    border-color: {COLOR_ACCENT};
}}

QListWidget::item {{
    border-radius: 5px;
    padding: 7px;
    margin: 2px;
}}

QListWidget::item:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}

QListWidget::item:selected {{
    background-color: #3A2C26;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_ACCENT};
}}

QPlainTextEdit {{
    line-height: 1.35;
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QHeaderView::section {{
    background-color: {COLOR_PANEL_HEADER};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    padding: 5px;
}}

QTableWidget {{
    gridline-color: {COLOR_BORDER_DEFAULT};
    alternate-background-color: {COLOR_PANEL_BG_ALT};
}}

{editor_scrollbar_qss("QWidget#PptEditorRoot")}
"""


PPT_DIALOG_QSS = f"""
QDialog {{
    background-color: {COLOR_APP_BG};
    color: {COLOR_TEXT_SECONDARY};
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

QLabel#TemplateGalleryTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 20px;
    font-weight: 800;
}}

QLabel#TemplateGalleryCaption {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
}}

QFrame#TemplatePreviewSide {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QLabel#TemplateLargePreview {{
    background-color: {COLOR_BG_L2};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 4px;
}}

QLabel#TemplateName {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 15px;
    font-weight: 800;
}}

QLabel#TemplateCategory {{
    color: {COLOR_ACCENT_HOVER};
    font-size: 10px;
    font-weight: 800;
    text-transform: uppercase;
}}

QLabel#TemplateDescription {{
    color: {COLOR_TEXT_TERTIARY};
}}

QListWidget {{
    background-color: {COLOR_APP_BG};
    border: 0;
    outline: 0;
}}

QListWidget::item {{
    color: {COLOR_TEXT_SECONDARY};
    padding: 10px;
    border: 2px solid transparent;
    border-radius: 6px;
}}

QListWidget::item:hover {{
    background-color: {COLOR_PANEL_BG};
    border-color: {COLOR_BORDER_DEFAULT};
}}

QListWidget::item:selected {{
    background-color: {COLOR_PANEL_BG};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT};
}}

QPushButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 24px;
}}

QPushButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
}}

QSpinBox,
QTableWidget,
QLineEdit {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 5px;
    selection-background-color: #3A2C26;
    selection-color: {COLOR_TEXT_PRIMARY};
}}

QTableWidget {{
    gridline-color: {COLOR_BORDER_DEFAULT};
    alternate-background-color: {COLOR_PANEL_BG_ALT};
}}

QHeaderView::section {{
    background-color: {COLOR_PANEL_HEADER};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    padding: 5px;
}}

{editor_scrollbar_qss("QDialog")}
"""


__all__ = ["PPT_DIALOG_QSS", "PPT_EDITOR_QSS"]
