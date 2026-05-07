# =============================================================================
# Tiger Capture — Design Token System (Phase 1)
# =============================================================================
# Material Dark Elevation 7-stop scale + Tiger Orange single-accent.
# Hue accent is reserved for *signature* moments (selection stripe, focus
# rings, slider fill, primary CTA) so the chrome stays restful but the
# brand is unmistakable when it appears.

# ---- Elevation (background tones) ----
COLOR_BG_L1 = "#000000"   # video preview matte, deepest possible
COLOR_BG_L2 = "#121212"   # input fields, deep panels, timeline
COLOR_BG_L3 = "#1E1E1E"   # window body, main background
COLOR_BG_L4 = "#242424"   # play bars, section headers, toolbar
COLOR_BG_L5 = "#2E2E2E"   # buttons, combobox, interactive controls
COLOR_BG_L6 = "#383838"   # hover state (NEW)
COLOR_BG_L7 = "#424242"   # focus / active / dropdown border (NEW)

# ---- Borders ----
COLOR_BORDER_SUBTLE = "#2A2A2A"
COLOR_BORDER_DEFAULT = "#333333"
COLOR_BORDER_FOCUS = "#424242"
# Accent border = Tiger Orange (selection / focus emphasis).

# ---- Tiger Orange — single accent for the whole brand ----
COLOR_ACCENT = "#D85A30"
COLOR_ACCENT_HOVER = "#E36B40"
COLOR_ACCENT_PRESSED = "#C04A20"
COLOR_ACCENT_DISABLED = "#6A3A26"

# Legacy aliases — every old name routes to the same Tiger Orange so
# existing call sites keep their imports working unchanged.
COLOR_ACCENT_BLUE = COLOR_ACCENT
COLOR_ACCENT_BLUE_HOVER = COLOR_ACCENT_HOVER
COLOR_ACCENT_ORANGE = COLOR_ACCENT
COLOR_ACCENT_GREEN = COLOR_ACCENT
COLOR_ACCENT_RED = "#e54646"
COLOR_ACCENT_RED_HOVER = "#c43838"

# ---- Text ----
COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#C8C8C8"
COLOR_TEXT_TERTIARY = "#8A8A8A"
COLOR_TEXT_DISABLED = "#5A5A5A"

# ---- Radius scale ----
RADIUS_SM = "4px"     # small chips / indicators
RADIUS_MD = "6px"     # default widgets
RADIUS_LG = "8px"     # panels, lists, group boxes
RADIUS_XL = "12px"    # modals
RADIUS_FULL = "999px" # slider handles, toggles

# ---- Font stack ----
# Pretendard if installed locally, then Apple SD Gothic / Malgun for
# Korean fallback, Noto Sans JP for Japanese, Segoe UI for everything
# else on Windows. Qt resolves left-to-right and skips missing faces.
FONT_FAMILY = (
    '"Pretendard", "Pretendard Variable", '
    '"Apple SD Gothic Neo", "Malgun Gothic", '
    '"Noto Sans JP", "Segoe UI", system-ui, sans-serif'
)
FONT_FAMILY_MONO = (
    '"JetBrains Mono", "SF Mono", "Cascadia Mono", '
    '"Consolas", "Courier New", monospace'
)


# =============================================================================
# QSS — Phase 1 widgets
# =============================================================================

APP_QSS = f"""
/* -----------------------------------------------------------------
 * Global font + base colours.
 * ----------------------------------------------------------------- */
* {{
    font-family: {FONT_FAMILY};
    font-size: 12px;
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
    border-radius: {RADIUS_XL};
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

QLabel#SectionLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    padding-left: 2px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* -----------------------------------------------------------------
 * QPushButton — default + 5 variants via [variant="…"] property.
 * ``btn.setProperty("variant", "primary")`` switches presentation
 * without renaming or restructuring the call sites.
 * ----------------------------------------------------------------- */
QPushButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_MD};
    padding: 7px 14px;
    min-height: 22px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
}}
QPushButton:pressed {{
    background-color: {COLOR_BG_L4};
    border-color: {COLOR_BORDER_FOCUS};
}}
QPushButton:focus {{
    border: 1px solid {COLOR_ACCENT};
    outline: none;
}}
QPushButton:disabled {{
    background-color: {COLOR_BG_L3};
    border-color: {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_DISABLED};
}}
QPushButton:default {{
    border-color: {COLOR_BORDER_FOCUS};
}}

/* Primary — Tiger Orange filled. Reserve for the single most
 * important action on a screen. */
QPushButton[variant="primary"] {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    border: 1px solid {COLOR_ACCENT};
    font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton[variant="primary"]:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
    border-color: {COLOR_ACCENT_PRESSED};
}}
QPushButton[variant="primary"]:disabled {{
    background-color: {COLOR_ACCENT_DISABLED};
    border-color: {COLOR_ACCENT_DISABLED};
    color: rgba(255, 255, 255, 0.55);
}}

/* Destructive — red text + red border on transparent. */
QPushButton[variant="destructive"] {{
    background-color: transparent;
    color: {COLOR_ACCENT_RED};
    border: 1px solid {COLOR_ACCENT_RED};
    font-weight: 600;
}}
QPushButton[variant="destructive"]:hover {{
    background-color: rgba(229, 70, 70, 0.12);
    color: {COLOR_ACCENT_RED_HOVER};
    border-color: {COLOR_ACCENT_RED_HOVER};
}}
QPushButton[variant="destructive"]:pressed {{
    background-color: rgba(229, 70, 70, 0.24);
}}

/* Ghost — fully transparent, hover reveals background only. */
QPushButton[variant="ghost"] {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid transparent;
}}
QPushButton[variant="ghost"]:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton[variant="ghost"]:pressed {{
    background-color: {COLOR_BG_L4};
}}

/* Outline — neutral border, no fill. */
QPushButton[variant="outline"] {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
}}
QPushButton[variant="outline"]:hover {{
    background-color: {COLOR_BG_L5};
    border-color: {COLOR_BORDER_FOCUS};
    color: {COLOR_TEXT_PRIMARY};
}}

/* -----------------------------------------------------------------
 * Dialog buttons — descend-selector forces the same look on
 * QMessageBox / QFileDialog / QInputDialog children that ignore
 * widget-level QSS shadowing.
 * ----------------------------------------------------------------- */
QMessageBox QPushButton,
QInputDialog QPushButton,
QFileDialog QPushButton,
QDialogButtonBox QPushButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_MD};
    padding: 7px 18px;
    min-width: 80px;
    font-weight: 500;
}}
QMessageBox QPushButton:hover,
QInputDialog QPushButton:hover,
QFileDialog QPushButton:hover,
QDialogButtonBox QPushButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
}}
QMessageBox QPushButton:default,
QInputDialog QPushButton:default,
QFileDialog QPushButton:default,
QDialogButtonBox QPushButton:default {{
    background-color: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
    font-weight: 600;
}}
QMessageBox QPushButton:default:hover,
QInputDialog QPushButton:default:hover,
QFileDialog QPushButton:default:hover,
QDialogButtonBox QPushButton:default:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}

QMessageBox, QInputDialog, QFileDialog {{
    background-color: {COLOR_BG_L3};
    color: {COLOR_TEXT_SECONDARY};
}}
QMessageBox QLabel, QInputDialog QLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 12px;
}}

/* -----------------------------------------------------------------
 * QToolButton — icon-only / quick-access buttons.
 * ----------------------------------------------------------------- */
QToolButton {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: {RADIUS_MD};
    padding: 6px;
    min-width: 28px;
    min-height: 28px;
}}
QToolButton:hover {{
    background-color: {COLOR_BG_L5};
    border-color: {COLOR_BORDER_DEFAULT};
    color: {COLOR_TEXT_PRIMARY};
}}
QToolButton:pressed {{
    background-color: {COLOR_BG_L4};
}}
QToolButton:checked {{
    background-color: {COLOR_BG_L6};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_TEXT_PRIMARY};
}}
QToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
}}

/* -----------------------------------------------------------------
 * QLineEdit / QTextEdit / QPlainTextEdit / QSpinBox / QDoubleSpinBox
 * — input fields. L2 background to read as deeper than the
 * surrounding chrome. Tiger Orange on focus.
 * ----------------------------------------------------------------- */
QLineEdit, QTextEdit, QPlainTextEdit,
QSpinBox, QDoubleSpinBox {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_MD};
    padding: 7px 10px;
    selection-background-color: {COLOR_ACCENT};
    selection-color: #FFFFFF;
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {COLOR_BORDER_FOCUS};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}
QLineEdit[error="true"], QSpinBox[error="true"] {{
    border-color: {COLOR_ACCENT_RED};
}}

/* SpinBox arrows — minimal, hover Tiger Orange. */
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    background-color: transparent;
    border: none;
    width: 18px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {COLOR_TEXT_TERTIARY};
    width: 0; height: 0;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_TERTIARY};
    width: 0; height: 0;
}}
QSpinBox::up-arrow:hover, QDoubleSpinBox::up-arrow:hover {{
    border-bottom-color: {COLOR_ACCENT};
}}
QSpinBox::down-arrow:hover, QDoubleSpinBox::down-arrow:hover {{
    border-top-color: {COLOR_ACCENT};
}}

/* -----------------------------------------------------------------
 * QSlider — polished modern style: thicker groove + crisp handle.
 *
 * Horizontal (all general sliders):
 *   groove 6 px → sub-page fills Tiger Orange on the left side
 *   handle 16 × 16 px circle, white with a subtle outer ring that
 *   turns solid orange on hover / pressed
 *
 * Vertical (ColorWheel luma bars beside each wheel):
 *   same geometry rotated; sub/add pages swapped so "higher" means
 *   the orange fill grows upward.
 * ----------------------------------------------------------------- */
QSlider {{
    background: transparent;
    min-height: 20px;
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: #28282e;
    border-radius: 3px;
    border: 1px solid #1e1e24;
}}
QSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c04a22, stop:1 {COLOR_ACCENT});
    border-radius: 3px;
    height: 6px;
}}
QSlider::add-page:horizontal {{
    background: #28282e;
    border-radius: 3px;
    border: 1px solid #1e1e24;
}}
QSlider::handle:horizontal {{
    background: #f0f0f0;
    border: 2px solid #4a4a52;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #ffffff;
    border: 2px solid {COLOR_ACCENT};
    margin: -6px 0;
    width: 16px;
    height: 16px;
    border-radius: 8px;
}}
QSlider::handle:horizontal:pressed {{
    background: {COLOR_ACCENT};
    border: 2px solid #ff7a4a;
    margin: -6px 0;
}}
QSlider::handle:horizontal:disabled {{
    background: #3a3a40;
    border-color: #2a2a30;
}}

/* Vertical slider (ColorWheel luma bars). */
QSlider::groove:vertical {{
    width: 6px;
    background: #28282e;
    border-radius: 3px;
    border: 1px solid #1e1e24;
}}
QSlider::sub-page:vertical {{
    background: #28282e;
    border-radius: 3px;
}}
QSlider::add-page:vertical {{
    background: qlineargradient(x1:0, y1:1, x2:0, y2:0,
        stop:0 #c04a22, stop:1 {COLOR_ACCENT});
    border-radius: 3px;
}}
QSlider::handle:vertical {{
    background: #f0f0f0;
    border: 2px solid #4a4a52;
    width: 16px;
    height: 16px;
    margin: 0 -6px;
    border-radius: 8px;
}}
QSlider::handle:vertical:hover {{
    background: #ffffff;
    border: 2px solid {COLOR_ACCENT};
}}
QSlider::handle:vertical:pressed {{
    background: {COLOR_ACCENT};
    border: 2px solid #ff7a4a;
}}

/* -----------------------------------------------------------------
 * QCheckBox / QRadioButton — Tiger Orange filled when checked.
 * (Checkmark glyph itself stays Qt-default for now; bundling SVGs
 * comes with Phase 2.)
 * ----------------------------------------------------------------- */
QCheckBox, QRadioButton {{
    color: {COLOR_TEXT_SECONDARY};
    font-size: 12px;
    spacing: 8px;
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {COLOR_BORDER_FOCUS};
    background: {COLOR_BG_L2};
}}
QCheckBox::indicator {{
    border-radius: {RADIUS_SM};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {COLOR_ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {COLOR_ACCENT};
    border-color: {COLOR_ACCENT};
}}
QRadioButton::indicator:checked {{
    background: {COLOR_BG_L2};
    border: 5px solid {COLOR_ACCENT};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {COLOR_BG_L3};
    border-color: {COLOR_BORDER_SUBTLE};
}}

/* -----------------------------------------------------------------
 * QComboBox — L5 surface, Tiger Orange focus border.
 * ----------------------------------------------------------------- */
QComboBox {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_MD};
    padding: 6px 32px 6px 12px;
    min-width: 110px;
    font-size: 12px;
}}
QComboBox:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
}}
QComboBox:focus, QComboBox:on {{
    border: 1px solid {COLOR_ACCENT};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
    background: transparent;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLOR_TEXT_TERTIARY};
    width: 0; height: 0;
    margin-right: 8px;
}}
QComboBox::down-arrow:hover {{
    border-top-color: {COLOR_ACCENT};
}}
QComboBox QAbstractItemView {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_FOCUS};
    border-radius: {RADIUS_LG};
    selection-background-color: {COLOR_ACCENT};
    selection-color: #FFFFFF;
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: {RADIUS_SM};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
}}

/* -----------------------------------------------------------------
 * QListWidget / QListView — signature Tiger stripe on selection.
 * Left 2px Tiger Orange border on selected items is the brand
 * detail other tools don't have.
 * ----------------------------------------------------------------- */
QListWidget, QListView {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    alternate-background-color: {COLOR_BG_L3};
    padding: 4px;
    outline: none;
}}
QListWidget::item, QListView::item {{
    padding: 8px 10px;
    border-left: 2px solid transparent;
    border-radius: {RADIUS_SM};
    margin: 1px 0;
}}
QListWidget::item:hover, QListView::item:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}
QListWidget::item:selected, QListView::item:selected {{
    background-color: {COLOR_BG_L6};
    color: {COLOR_TEXT_PRIMARY};
    border-left: 2px solid {COLOR_ACCENT};
}}
QListWidget::item:selected:!active, QListView::item:selected:!active {{
    background-color: {COLOR_BG_L5};
}}

/* QTreeView/QTreeWidget shares colours with the list. */
QTreeView, QTreeWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    alternate-background-color: {COLOR_BG_L3};
    padding: 2px;
    outline: none;
}}
QTreeView::item, QTreeWidget::item {{
    padding: 4px 6px;
    border-left: 2px solid transparent;
}}
QTreeView::item:hover, QTreeWidget::item:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}
QTreeView::item:selected, QTreeWidget::item:selected {{
    background-color: {COLOR_BG_L6};
    color: {COLOR_TEXT_PRIMARY};
    border-left: 2px solid {COLOR_ACCENT};
}}

/* -----------------------------------------------------------------
 * QFrame
 * ----------------------------------------------------------------- */
QFrame#Divider {{
    background-color: {COLOR_BORDER_SUBTLE};
    max-height: 1px;
    min-height: 1px;
    border: none;
}}

/* -----------------------------------------------------------------
 * QScrollBar — minimalist rail, Tiger Orange when actively dragged.
 * ----------------------------------------------------------------- */
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BG_L6};
    border-radius: 3px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLOR_BG_L7};
}}
QScrollBar::handle:horizontal:pressed {{
    background: {COLOR_ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0; background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border: none;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BG_L6};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLOR_BG_L7};
}}
QScrollBar::handle:vertical:pressed {{
    background: {COLOR_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; background: transparent;
}}

/* -----------------------------------------------------------------
 * QMenu / QMenuBar
 * ----------------------------------------------------------------- */
QMenuBar {{
    background-color: {COLOR_BG_L3};
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
    padding: 2px 4px;
    color: {COLOR_TEXT_SECONDARY};
}}
QMenuBar::item {{
    padding: 6px 12px;
    border-radius: {RADIUS_SM};
    background: transparent;
}}
QMenuBar::item:selected, QMenuBar::item:pressed {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}

QMenu {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_FOCUS};
    border-radius: {RADIUS_LG};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 24px 7px 14px;
    border-radius: {RADIUS_SM};
    margin: 1px 0;
}}
QMenu::item:selected {{
    background-color: {COLOR_BG_L6};
    color: {COLOR_TEXT_PRIMARY};
}}
QMenu::item:disabled {{
    color: {COLOR_TEXT_DISABLED};
}}
QMenu::separator {{
    height: 1px;
    background: {COLOR_BORDER_FOCUS};
    margin: 4px 8px;
}}

/* -----------------------------------------------------------------
 * QToolTip
 * ----------------------------------------------------------------- */
QToolTip {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_FOCUS};
    padding: 6px 10px;
    border-radius: {RADIUS_MD};
    font-size: 11px;
}}

/* -----------------------------------------------------------------
 * QTabWidget / QTabBar — Tiger Orange underline on the active tab.
 * ----------------------------------------------------------------- */
QTabWidget::pane {{
    background-color: {COLOR_BG_L3};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {COLOR_TEXT_TERTIARY};
    padding: 9px 18px;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}}
QTabBar::tab:hover {{
    color: {COLOR_TEXT_PRIMARY};
}}
QTabBar::tab:selected {{
    color: {COLOR_TEXT_PRIMARY};
    border-bottom: 2px solid {COLOR_ACCENT};
    font-weight: 700;
}}

/* -----------------------------------------------------------------
 * QGroupBox
 * ----------------------------------------------------------------- */
QGroupBox {{
    background-color: {COLOR_BG_L3};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
    margin-top: 18px;
    padding: 16px 14px 14px 14px;
    color: {COLOR_TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    color: {COLOR_TEXT_TERTIARY};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* -----------------------------------------------------------------
 * QProgressBar
 * ----------------------------------------------------------------- */
QProgressBar {{
    background-color: {COLOR_BG_L2};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_MD};
    text-align: center;
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 600;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: {COLOR_ACCENT};
    border-radius: {RADIUS_MD};
}}

/* -----------------------------------------------------------------
 * QSplitter — Tiger Orange handle when hovered / dragged.
 * ----------------------------------------------------------------- */
QSplitter::handle {{
    background-color: {COLOR_BG_L2};
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}
QSplitter::handle:hover, QSplitter::handle:pressed {{
    background-color: {COLOR_ACCENT};
}}

/* -----------------------------------------------------------------
 * QStatusBar
 * ----------------------------------------------------------------- */
QStatusBar {{
    background-color: {COLOR_BG_L3};
    border-top: 1px solid {COLOR_BORDER_SUBTLE};
    color: {COLOR_TEXT_TERTIARY};
    font-size: 11px;
}}

/* =================================================================
 * Existing objectName overrides — preserved so call sites keep
 * working, just retuned to new tokens.
 * ================================================================= */
QPushButton#NewCaptureButton {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    border: 1px solid {COLOR_ACCENT};
    border-radius: {RADIUS_LG};
    padding: 14px 24px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#NewCaptureButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#NewCaptureButton:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
}}
QPushButton#NewCaptureButton:disabled {{
    background-color: {COLOR_ACCENT_DISABLED};
    border-color: {COLOR_ACCENT_DISABLED};
    color: rgba(255, 255, 255, 0.55);
}}

QPushButton[modeButton="true"] {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_LG};
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton[modeButton="true"]:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton[modeButton="true"]:checked {{
    background-color: {COLOR_BG_L6};
    border: 1px solid {COLOR_ACCENT};
    color: {COLOR_TEXT_PRIMARY};
    font-weight: 700;
}}

QPushButton#ProEditorButton,
QPushButton#SoundEditorButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_LG};
    padding: 12px 18px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#ProEditorButton:hover,
QPushButton#SoundEditorButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_ACCENT};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ProEditorButton:pressed,
QPushButton#SoundEditorButton:pressed {{
    background-color: {COLOR_BG_L4};
}}

QPushButton#IconButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: {RADIUS_MD};
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
    background-color: {COLOR_BG_L4};
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
    border-radius: {RADIUS_MD};
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#DonateButton:hover {{
    background-color: rgba(229, 70, 70, 0.12);
    border-color: {COLOR_ACCENT_RED_HOVER};
    color: {COLOR_ACCENT_RED_HOVER};
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
    border-radius: {RADIUS_MD};
}}
QWidget#RecentCard:hover {{
    border-color: {COLOR_ACCENT};
}}
QLabel#RecentThumb {{
    background-color: {COLOR_BG_L3};
    border-radius: {RADIUS_SM};
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
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: {RADIUS_MD};
    padding: 7px 13px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#ToolButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: {COLOR_BORDER_FOCUS};
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ToolButton:pressed {{
    background-color: {COLOR_BG_L4};
}}
QPushButton#ToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
}}
QPushButton#ToolButton:checked {{
    background-color: {COLOR_BG_L6};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT};
}}

QPushButton#PrimaryToolButton {{
    background-color: {COLOR_ACCENT};
    color: #FFFFFF;
    border: 1px solid {COLOR_ACCENT};
    border-radius: {RADIUS_MD};
    padding: 8px 18px;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: {COLOR_ACCENT_HOVER};
    border-color: {COLOR_ACCENT_HOVER};
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
}}

QWidget#PreviewHost {{
    background-color: {COLOR_BG_L1};
    border-radius: {RADIUS_SM};
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

QLabel#RecentEmpty {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 12px;
    padding: 20px;
}}
"""
