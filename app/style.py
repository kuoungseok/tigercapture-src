# --- Dark-mode palette (shared across all editor + main windows) ---
# Material Dark elevation tones — neutral greys, no blue cast. Each
# tier corresponds to a notional surface elevation, matching how
# Material Dark layers cards above the base. Keeping the palette
# strictly grey (instead of the previous slightly blue-tinted greys)
# makes the single brand accent read more cleanly.
COLOR_BG_L5 = "#2E2E2E"  # interactive controls / toolbars (08dp)
COLOR_BG_L4 = "#242424"  # play bars, section header backgrounds (03dp)
COLOR_BG_L3 = "#1E1E1E"  # generic window body, controls bar (01dp)
COLOR_BG_L2 = "#121212"  # timeline area, deep panels (00dp)
COLOR_BG_L1 = "#000000"  # video preview matte

# Single brand accent — TigerCapture orange. The whole UI funnels
# through these three values for primary actions, selection, and
# focus rings. The legacy "BLUE / GREEN / ORANGE" aliases below all
# resolve here so existing callers keep working but every accent on
# screen reads as one coherent brand colour.
COLOR_ACCENT = "#D85A30"
COLOR_ACCENT_HOVER = "#ff7a4a"
COLOR_ACCENT_PRESSED = "#b04722"
COLOR_ACCENT_DISABLED = "#6a3a26"

# Legacy aliases — every multi-accent name maps to the same orange
# so the old multi-colour palette collapses into one. Red is kept
# distinct because destructive / donate UI universally uses red.
COLOR_ACCENT_BLUE = COLOR_ACCENT
COLOR_ACCENT_BLUE_HOVER = COLOR_ACCENT_HOVER
COLOR_ACCENT_ORANGE = COLOR_ACCENT
COLOR_ACCENT_GREEN = COLOR_ACCENT
COLOR_ACCENT_RED = "#e54646"

COLOR_TEXT_PRIMARY = "#ffffff"
COLOR_TEXT_SECONDARY = "#c8c8c8"
COLOR_TEXT_TERTIARY = "#8a8a8a"
COLOR_TEXT_DISABLED = "#5a5a5a"
COLOR_BORDER_DEFAULT = "#3a3a3a"
COLOR_BORDER_SUBTLE = "#2a2a2a"


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
/* Default dialog button — emphasis comes from a brighter neutral
 * surface, not a hue. Same grey family as the rest of the chrome,
 * just one elevation step up. Keeps the surface monochromatic. */
QPushButton:default {{
    background-color: #4a4a4a;
    border: 1px solid #5a5a5a;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton:default:hover {{
    background-color: #5a5a5a;
    border-color: #6a6a6a;
}}
QPushButton:default:pressed {{
    background-color: #3a3a3a;
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
    background-color: #4a4a4a;
    border: 1px solid #5a5a5a;
    color: {COLOR_TEXT_PRIMARY};
}}
QMessageBox QPushButton:default:hover,
QInputDialog QPushButton:default:hover,
QFileDialog QPushButton:default:hover,
QDialogButtonBox QPushButton:default:hover {{
    background-color: #5a5a5a;
    border-color: #6a6a6a;
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
    background-color: #5a5a5a;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #6a6a6a;
    border-radius: 8px;
    padding: 14px 24px;
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#NewCaptureButton:hover {{
    background-color: #6a6a6a;
    border-color: #7a7a7a;
}}
QPushButton#NewCaptureButton:pressed {{
    background-color: #4a4a4a;
}}
QPushButton#NewCaptureButton:disabled {{
    background-color: {COLOR_BORDER_DEFAULT};
    color: {COLOR_TEXT_DISABLED};
}}

QPushButton[modeButton="true"] {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton[modeButton="true"]:hover {{
    background-color: #383838;
    border-color: #4a4a4a;
    color: {COLOR_TEXT_PRIMARY};
}}
/* Selected state — same grey family, brighter. White label, brighter
 * border. No hue accent: the elevation step is the affordance. */
QPushButton[modeButton="true"]:checked {{
    background-color: #4a4a4a;
    border: 1px solid #6a6a6a;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 700;
}}

/* Pro video editor + Sound editor shortcuts — neutral surface,
 * elevation-step brighter than the surrounding chrome to read as
 * interactive. White label. Distinguished by icon, not hue. */
QPushButton#ProEditorButton,
QPushButton#SoundEditorButton {{
    background-color: #3a3a3a;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #4a4a4a;
    border-radius: 8px;
    padding: 12px 18px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#ProEditorButton:hover,
QPushButton#SoundEditorButton:hover {{
    background-color: #4a4a4a;
    border-color: #5a5a5a;
}}
QPushButton#ProEditorButton:pressed,
QPushButton#SoundEditorButton:pressed {{
    background-color: #2e2e2e;
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
    selection-background-color: #4a4a4a;
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
    background: #6a6a6a;
    border-color: #8a8a8a;
}}

QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #4a4a4a;
    selection-color: {COLOR_TEXT_PRIMARY};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: #7a7a7a;
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
    border-color: #6a6a6a;
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
    background-color: #4a4a4a;
    color: {COLOR_TEXT_PRIMARY};
    border-color: #6a6a6a;
}}

QPushButton#PrimaryToolButton {{
    background-color: #4a4a4a;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #5a5a5a;
    border-radius: 6px;
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 700;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: #5a5a5a;
    border-color: #6a6a6a;
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: #3a3a3a;
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
    background-color: #4a4a4a;
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
    background-color: #4a4a4a;
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
