# --- Dark-mode palette (shared across all editor + main windows) ---
COLOR_BG_L5 = "#36363c"  # title / toolbars (brightest — interactive controls)
COLOR_BG_L4 = "#2a2a30"  # play bars, section header backgrounds
COLOR_BG_L3 = "#1c1c22"  # generic window body, controls bar
COLOR_BG_L2 = "#0f0f14"  # timeline area, deep panels
COLOR_BG_L1 = "#000000"  # video preview matte
COLOR_ACCENT_BLUE = "#378ADD"
COLOR_ACCENT_BLUE_HOVER = "#4a9bee"
COLOR_ACCENT_ORANGE = "#D85A30"
COLOR_ACCENT_GREEN = "#5DCAA5"
COLOR_ACCENT_RED = "#e54646"
COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#c8c8d0"
COLOR_TEXT_TERTIARY = "#8a8a92"
COLOR_TEXT_DISABLED = "#5a5a62"
COLOR_BORDER_DEFAULT = "#4a4a52"
COLOR_BORDER_SUBTLE = "#3a3a42"


APP_QSS = f"""
* {{
    font-family: "Segoe UI", "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", system-ui, sans-serif;
    font-size: 13px;
}}

QMainWindow, QWidget#Central {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}

QWidget {{
    color: {COLOR_TEXT_SECONDARY};
}}

QDialog {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}

/* -----------------------------------------------------------------
 * Default QPushButton — covers every button that doesn't set its
 * own objectName / property (i.e. QMessageBox OK/Cancel, QFileDialog
 * Open/Cancel, QInputDialog, QDialogButtonBox). Without this, Qt
 * falls back to its platform style which paints a near-white button
 * against our dark dialog chrome — unreadable on every dialog in
 * the app. Any QPushButton#Foo defined below still overrides this
 * because the objectName selector has higher specificity.
 * ----------------------------------------------------------------- */
QPushButton {{
    background-color: #4e4e56;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #7a7a84;
    border-radius: 6px;
    padding: 7px 18px;
    min-width: 84px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: #5f5f68;
    border-color: #9a9aa4;
}}
QPushButton:pressed {{
    background-color: #3a3a40;
}}
QPushButton:disabled {{
    background-color: {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}
/* Primary / default dialog button (Enter-activated) gets the accent
 * blue so the affirmative action is obvious. Qt marks the default
 * button automatically in message boxes and QDialogButtonBox. */
QPushButton:default {{
    background-color: {COLOR_ACCENT_BLUE};
    border-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton:default:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
    border-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton:default:pressed {{
    background-color: #2a6fb4;
}}

/* Force the same look on descendants of modal dialogs. The generic
 * QPushButton rule above normally suffices, but widget-level
 * stylesheets (e.g. VIDEO_EDITOR_EXTRA_QSS on VideoEditorWindow) can
 * shadow it for message boxes that spawn from those windows. The
 * descendant selector raises specificity so the rule wins regardless. */
QMessageBox QPushButton,
QInputDialog QPushButton,
QFileDialog QPushButton,
QDialogButtonBox QPushButton {{
    background-color: #4e4e56;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #7a7a84;
    border-radius: 6px;
    padding: 7px 18px;
    min-width: 88px;
    font-weight: 600;
}}
QMessageBox QPushButton:hover,
QInputDialog QPushButton:hover,
QFileDialog QPushButton:hover,
QDialogButtonBox QPushButton:hover {{
    background-color: #5f5f68;
    border-color: #9a9aa4;
}}
QMessageBox QPushButton:default,
QInputDialog QPushButton:default,
QFileDialog QPushButton:default,
QDialogButtonBox QPushButton:default {{
    background-color: {COLOR_ACCENT_BLUE};
    border-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
}}
QMessageBox QPushButton:default:hover,
QInputDialog QPushButton:default:hover,
QFileDialog QPushButton:default:hover,
QDialogButtonBox QPushButton:default:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
    border-color: {COLOR_ACCENT_BLUE_HOVER};
}}

/* Dialog body + labels */
QMessageBox, QInputDialog, QFileDialog {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}
QMessageBox QLabel, QInputDialog QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

QLabel#SectionLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
    font-weight: 700;
    padding-left: 2px;
    letter-spacing: 1.2px;
    text-transform: uppercase;
}}

QPushButton#NewCaptureButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#NewCaptureButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton#NewCaptureButton:pressed {{
    background-color: #2a6fb4;
}}
QPushButton#NewCaptureButton:disabled {{
    background-color: {COLOR_BORDER_DEFAULT};
    color: {COLOR_TEXT_DISABLED};
}}

QPushButton[modeButton="true"] {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton[modeButton="true"]:hover {{
    background-color: #44444a;
    border-color: #6a6a72;
}}
QPushButton[modeButton="true"]:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    border-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 700;
}}

/* Pro video editor shortcut — distinct violet accent so it reads as the
   "power-user" entry point, separate from the blue primary actions. */
QPushButton#ProEditorButton {{
    background-color: #6a3cb5;
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 8px;
    padding: 12px 18px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#ProEditorButton:hover {{
    background-color: #7b4ac9;
}}
QPushButton#ProEditorButton:pressed {{
    background-color: #552a97;
}}

QComboBox {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    min-width: 110px;
    font-size: 12px;
}}
QComboBox:hover {{
    border-color: #5a5a62;
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    selection-background-color: {COLOR_ACCENT_BLUE};
    selection-color: {COLOR_TEXT_PRIMARY};
}}

QCheckBox {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 3px;
    background: {COLOR_BG_L2};
}}
QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT_BLUE};
    border-color: {COLOR_ACCENT_BLUE};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {COLOR_ACCENT_BLUE};
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLOR_ACCENT_BLUE};
}}

QFrame#Divider {{
    background-color: {COLOR_BORDER_SUBTLE};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

QLabel#RecentEmpty {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 12px;
    padding: 20px;
}}

QPushButton#IconButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 14px;
    min-width: 28px;
    min-height: 28px;
    color: {COLOR_TEXT_SECONDARY};
}}
QPushButton#IconButton:hover {{
    background-color: {COLOR_BG_L5};
    border-color: {COLOR_BORDER_DEFAULT};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#IconButton:pressed {{
    background-color: {COLOR_BG_L2};
}}

QLabel#AppTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 13px;
    font-weight: 700;
}}

QPushButton#DonateButton {{
    background-color: transparent;
    color: {COLOR_ACCENT_RED};
    border: 1px solid {COLOR_ACCENT_RED};
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#DonateButton:hover {{
    background-color: rgba(229, 70, 70, 0.12);
    border-color: #ff6b6b;
    color: #ff6b6b;
}}
QPushButton#DonateButton:pressed {{
    background-color: rgba(229, 70, 70, 0.24);
}}

QLabel#CreditFooter {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 700;
    padding-top: 4px;
    letter-spacing: 0.5px;
}}

QScrollArea#RecentStrip {{
    background-color: transparent;
    border: none;
}}
QWidget#RecentStripContainer {{
    background-color: transparent;
}}
QWidget#RecentCard {{
    background-color: {COLOR_BG_L2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 6px;
}}
QWidget#RecentCard:hover {{
    border-color: {COLOR_ACCENT_BLUE};
}}
QLabel#RecentThumb {{
    background-color: {COLOR_BG_L3};
    border-radius: 4px;
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#RecentThumb[videoPlaceholder="true"] {{
    background-color: {COLOR_BG_L1};
    color: {COLOR_TEXT_PRIMARY};
}}
QLabel#RecentName {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 11px;
}}
QLabel#RecentMeta {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 10px;
}}

QPushButton#ToolButton {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 7px 13px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#ToolButton:hover {{
    background-color: {COLOR_BG_L5};
    border-color: #5a5a62;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ToolButton:pressed {{
    background-color: #0a0a0e;
}}
QPushButton#ToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}
QPushButton#ToolButton:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT_BLUE};
}}

QPushButton#PrimaryToolButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: #2a6fb4;
}}

QWidget#PreviewHost {{
    background-color: {COLOR_BG_L1};
    border-radius: 4px;
}}

QLabel#StatusLabel {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
}}

QLabel#QuickPasteTarget {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
    padding-left: 4px;
}}

QScrollBar:horizontal {{
    background: {COLOR_BG_L2};
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER_DEFAULT};
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #5a5a62;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: transparent;
}}
QScrollBar:vertical {{
    background: {COLOR_BG_L2};
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER_DEFAULT};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #5a5a62;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

QListWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 4px;
    alternate-background-color: {COLOR_BG_L3};
}}
QListWidget::item {{
    padding: 4px 8px;
}}
QListWidget::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
}}

QMenu {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
}}
QMenu::item {{
    padding: 6px 20px;
}}
QMenu::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
}}
QMenu::separator {{
    height: 1px;
    background: {COLOR_BORDER_SUBTLE};
    margin: 4px 8px;
}}

QToolTip {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    padding: 4px 8px;
    border-radius: 4px;
}}
"""
