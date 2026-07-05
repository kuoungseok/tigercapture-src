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

# ---- Professional editor chrome ----
# These sit slightly above the legacy elevation scale and are used by
# media-editor surfaces where panel boundaries need to read instantly.
COLOR_APP_BG = "#101114"
COLOR_PANEL_BG = "#15161B"
COLOR_PANEL_BG_ALT = "#191B21"
COLOR_PANEL_HEADER = "#20222A"
COLOR_PANEL_RAIL = "#111217"
COLOR_TIMELINE_BG = "#222431"
COLOR_TIMELINE_STRIPE = "#2D3040"
COLOR_TIMELINE_VIDEO_BG = "#272936"
COLOR_TIMELINE_VIDEO_STRIPE = "#333647"
COLOR_TIMELINE_AUDIO_BG = "#202B32"
COLOR_TIMELINE_AUDIO_STRIPE = "#2A3A42"
COLOR_ACCENT_AUDIO = "#5DCAA5"
COLOR_ACCENT_SPINE = "#A06BD0"
COLOR_ACCENT_LIVE2D = "#4A9BEE"

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
    '"Noto Sans CJK KR", "Noto Sans KR", '
    '"Apple SD Gothic Neo", "Malgun Gothic", '
    '"Noto Sans CJK JP", "Noto Sans JP", '
    '"Microsoft YaHei UI", "Segoe UI Variable", "Segoe UI", '
    '"Arial", "Tahoma"'
)
FONT_FAMILY_MONO = (
    '"JetBrains Mono", "SF Mono", "Cascadia Mono", '
    '"Consolas", "Courier New", monospace'
)


# =============================================================================
# QSS — Phase 1 widgets
# =============================================================================

def editor_scrollbar_qss(scope: str = "") -> str:
    """Thin editor scrollbars with a wider invisible hit area."""
    prefix = f"{scope.strip()} " if scope and scope.strip() else ""
    return f"""
{prefix}QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    border: none;
    margin: 6px 6px 2px 6px;
}}
{prefix}QScrollBar:horizontal:hover {{
    margin: 3px 6px 2px 6px;
}}
{prefix}QScrollBar::handle:horizontal {{
    background: rgba(214, 220, 235, 38);
    border-radius: 2px;
    min-width: 36px;
}}
{prefix}QScrollBar::handle:horizontal:hover {{
    background: rgba(214, 220, 235, 112);
    border-radius: 4px;
}}
{prefix}QScrollBar::handle:horizontal:pressed {{
    background: rgba(238, 242, 250, 168);
}}
{prefix}QScrollBar::add-line:horizontal,
{prefix}QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
}}
{prefix}QScrollBar::add-page:horizontal,
{prefix}QScrollBar::sub-page:horizontal {{
    background: transparent;
}}
{prefix}QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    border: none;
    margin: 6px 2px 6px 6px;
}}
{prefix}QScrollBar:vertical:hover {{
    margin: 6px 2px 6px 3px;
}}
{prefix}QScrollBar::handle:vertical {{
    background: rgba(214, 220, 235, 38);
    border-radius: 2px;
    min-height: 36px;
}}
{prefix}QScrollBar::handle:vertical:hover {{
    background: rgba(214, 220, 235, 112);
    border-radius: 4px;
}}
{prefix}QScrollBar::handle:vertical:pressed {{
    background: rgba(238, 242, 250, 168);
}}
{prefix}QScrollBar::add-line:vertical,
{prefix}QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}
{prefix}QScrollBar::add-page:vertical,
{prefix}QScrollBar::sub-page:vertical {{
    background: transparent;
}}
"""


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

QWidget#ProPanel,
QWidget[proPanel="true"] {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: {RADIUS_LG};
}}

QWidget#ProPanelHeader,
QWidget[proHeader="true"] {{
    background-color: {COLOR_PANEL_HEADER};
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
    min-height: 30px;
}}

QLabel[proTitle="true"] {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0px;
    padding-left: 10px;
}}

QFrame[proDivider="true"] {{
    background-color: {COLOR_BORDER_SUBTLE};
    border: none;
    max-height: 1px;
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
    min-height: 18px;
}}
QSlider::groove:horizontal {{
    height: 3px;
    background: #292B35;
    border-radius: 2px;
    border: none;
}}
QSlider::sub-page:horizontal {{
    background: #5B45FF;
    border-radius: 2px;
    height: 3px;
}}
QSlider::add-page:horizontal {{
    background: #292B35;
    border-radius: 2px;
    border: none;
}}
QSlider::handle:horizontal {{
    background: #6452FF;
    border: 1px solid #9C8EFF;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}
QSlider::handle:horizontal:hover {{
    background: #7566FF;
    border: 1px solid #D6D0FF;
    margin: -6px 0;
    width: 14px;
    height: 14px;
    border-radius: 7px;
}}
QSlider::handle:horizontal:pressed {{
    background: #897CFF;
    border: 1px solid #FFFFFF;
    margin: -6px 0;
}}
QSlider::handle:horizontal:disabled {{
    background: #3a3a40;
    border-color: #2a2a30;
}}

/* Vertical slider (ColorWheel luma bars). */
QSlider::groove:vertical {{
    width: 3px;
    background: #292B35;
    border-radius: 2px;
    border: none;
}}
QSlider::sub-page:vertical {{
    background: #292B35;
    border-radius: 2px;
}}
QSlider::add-page:vertical {{
    background: #5B45FF;
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: #6452FF;
    border: 1px solid #9C8EFF;
    width: 14px;
    height: 14px;
    margin: 0 -6px;
    border-radius: 7px;
}}
QSlider::handle:vertical:hover {{
    background: #7566FF;
    border: 1px solid #D6D0FF;
}}
QSlider::handle:vertical:pressed {{
    background: #897CFF;
    border: 1px solid #FFFFFF;
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
    width: 17px;
    height: 17px;
    border: 1px solid #303548;
    background: #11131C;
}}
QCheckBox::indicator {{
    border-radius: {RADIUS_SM};
}}
QRadioButton::indicator {{
    border-radius: 8px;
}}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: #8A7CFF;
}}
QCheckBox::indicator:checked {{
    background: #5B45FF;
    border-color: #8C82FF;
}}
QRadioButton::indicator:checked {{
    background: #11131C;
    border: 5px solid #6E5EFF;
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {COLOR_BG_L3};
    border-color: {COLOR_BORDER_SUBTLE};
}}

/* -----------------------------------------------------------------
 * QComboBox — L5 surface, Tiger Orange focus border.
 * ----------------------------------------------------------------- */
QComboBox {{
    background-color: #151823;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #2C3347;
    border-radius: 10px;
    padding: 6px 30px 6px 12px;
    min-width: 110px;
    font-size: 12px;
}}
QComboBox:hover {{
    background-color: #1B2030;
    border-color: #566181;
}}
QComboBox:focus, QComboBox:on {{
    border: 1px solid #6E5EFF;
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
    border-top-color: #8A7CFF;
}}
QComboBox QAbstractItemView {{
    background-color: #151823;
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid #566181;
    border-radius: {RADIUS_LG};
    selection-background-color: #5B45FF;
    selection-color: #FFFFFF;
    padding: 4px;
    outline: none;
}}
QComboBox QAbstractItemView::item {{
    padding: 6px 10px;
    border-radius: {RADIUS_SM};
}}
QComboBox QAbstractItemView::item:selected {{
    background-color: #5B45FF;
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

/* -----------------------------------------------------------------
 * Studio-wide Qt chrome pass.
 * This late block intentionally overrides the older neutral Qt defaults
 * so dialogs, secondary editors, menus, tables, tabs, and utility panels
 * share the same Screen-Studio-like glass vocabulary as the timeline.
 * ----------------------------------------------------------------- */
QMainWindow,
QDialog,
QMessageBox,
QInputDialog,
QFileDialog,
QProgressDialog {{
    background-color: #0B0D16;
    color: #E6E8F2;
}}

QFrame,
QGroupBox,
QTabWidget::pane,
QToolBox::tab,
QDockWidget {{
    background-color: rgba(18, 21, 34, 232);
    border: 1px solid rgba(126, 141, 198, 48);
    border-radius: 14px;
}}

QPushButton,
QToolButton,
QCommandLinkButton {{
    background-color: rgba(255, 255, 255, 18);
    color: #E8EAF4;
    border: 1px solid #37405A;
    border-radius: 13px;
    padding: 7px 13px;
    min-height: 26px;
    font-weight: 700;
}}
QPushButton:hover,
QToolButton:hover,
QCommandLinkButton:hover {{
    background-color: rgba(255, 255, 255, 30);
    color: #FFFFFF;
    border-color: #7580A5;
}}
QPushButton:pressed,
QToolButton:pressed,
QCommandLinkButton:pressed {{
    background-color: rgba(255, 255, 255, 24);
    border-color: #A79EFF;
}}
QPushButton:checked,
QToolButton:checked {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3945E8,
        stop:0.52 #7358F2,
        stop:1 #22BDE4
    );
    border-color: #C2BAFF;
    color: #FFFFFF;
}}
QPushButton:disabled,
QToolButton:disabled,
QCommandLinkButton:disabled {{
    background-color: rgba(255, 255, 255, 7);
    border-color: #252B3A;
    color: #6F7484;
}}
QPushButton:default,
QPushButton[variant="primary"],
QPushButton#PrimaryToolButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.62 #F65343,
        stop:1 #E84E78
    );
    border-color: #FF9A78;
    color: #FFFFFF;
    font-weight: 800;
}}
QPushButton:default:hover,
QPushButton[variant="primary"]:hover,
QPushButton#PrimaryToolButton:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF9877,
        stop:0.62 #FF6348,
        stop:1 #F05B8C
    );
    border-color: #FFC1AA;
}}
QPushButton[variant="destructive"] {{
    background-color: rgba(229, 70, 70, 20);
    color: #FF7B7B;
    border-color: rgba(255, 123, 123, 150);
}}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QTimeEdit,
QDateTimeEdit,
QComboBox {{
    background-color: rgba(255, 255, 255, 13);
    color: #EEF0F8;
    border: 1px solid #30384F;
    border-radius: 13px;
    padding: 7px 11px;
    selection-background-color: #6F5CFF;
    selection-color: #FFFFFF;
}}
QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QDateEdit:hover,
QTimeEdit:hover,
QDateTimeEdit:hover,
QComboBox:hover {{
    background-color: rgba(255, 255, 255, 22);
    border-color: #7580A5;
}}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QTimeEdit:focus,
QDateTimeEdit:focus,
QComboBox:focus,
QComboBox:on {{
    border-color: #8A7CFF;
    background-color: rgba(255, 255, 255, 18);
}}
QComboBox {{
    padding-right: 28px;
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
    border-top: 5px solid #A7ADC2;
    width: 0px;
    height: 0px;
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: #131724;
    color: #EEF0F8;
    border: 1px solid #4F5B7C;
    border-radius: 12px;
    padding: 5px;
    outline: none;
    selection-background-color: #6F5CFF;
    selection-color: #FFFFFF;
}}
QSpinBox::up-button,
QSpinBox::down-button,
QDoubleSpinBox::up-button,
QDoubleSpinBox::down-button,
QDateEdit::up-button,
QDateEdit::down-button,
QTimeEdit::up-button,
QTimeEdit::down-button,
QDateTimeEdit::up-button,
QDateTimeEdit::down-button {{
    background: transparent;
    border: none;
    width: 18px;
}}

QCheckBox,
QRadioButton {{
    color: #D7DAE7;
    spacing: 8px;
}}
QCheckBox::indicator,
QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid #3A435D;
    background-color: rgba(255, 255, 255, 12);
}}
QCheckBox::indicator {{
    border-radius: 5px;
}}
QRadioButton::indicator {{
    border-radius: 9px;
}}
QCheckBox::indicator:hover,
QRadioButton::indicator:hover {{
    border-color: #8A7CFF;
}}
QCheckBox::indicator:checked {{
    background-color: #6F5CFF;
    border-color: #C2BAFF;
}}
QRadioButton::indicator:checked {{
    background-color: #0F1320;
    border: 5px solid #7E6BFF;
}}

QTabBar::tab {{
    background-color: rgba(255, 255, 255, 10);
    color: #A7ADC2;
    border: 1px solid transparent;
    border-radius: 12px;
    padding: 8px 15px;
    margin: 2px 3px;
    font-weight: 700;
}}
QTabBar::tab:hover {{
    background-color: rgba(255, 255, 255, 22);
    color: #FFFFFF;
    border-color: #4A5575;
}}
QTabBar::tab:selected {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.54 #F65368,
        stop:1 #755DF2
    );
    color: #FFFFFF;
    border-color: #FFF0D8;
}}

QListWidget,
QListView,
QTreeView,
QTreeWidget,
QTableView,
QTableWidget,
QColumnView {{
    background-color: rgba(10, 12, 21, 220);
    color: #D7DAE7;
    border: 1px solid #30384F;
    border-radius: 14px;
    alternate-background-color: rgba(255, 255, 255, 8);
    outline: none;
}}
QListWidget::item,
QListView::item,
QTreeView::item,
QTreeWidget::item,
QTableView::item,
QTableWidget::item {{
    color: #D7DAE7;
    border-radius: 8px;
    padding: 5px 7px;
}}
QListWidget::item:hover,
QListView::item:hover,
QTreeView::item:hover,
QTreeWidget::item:hover,
QTableView::item:hover,
QTableWidget::item:hover {{
    background-color: rgba(255, 255, 255, 26);
    color: #FFFFFF;
}}
QListWidget::item:selected,
QListView::item:selected,
QTreeView::item:selected,
QTreeWidget::item:selected,
QTableView::item:selected,
QTableWidget::item:selected {{
    background-color: #6F5CFF;
    color: #FFFFFF;
}}
QHeaderView::section {{
    background-color: rgba(255, 255, 255, 12);
    color: #C9CEDC;
    border: none;
    border-right: 1px solid #2A3144;
    border-bottom: 1px solid #2A3144;
    padding: 7px 9px;
    font-weight: 800;
}}
QTableCornerButton::section {{
    background-color: rgba(255, 255, 255, 12);
    border: none;
}}

QMenuBar {{
    background-color: #0B0D16;
    color: #D7DAE7;
    border-bottom: 1px solid rgba(126, 141, 198, 38);
}}
QMenuBar::item {{
    background: transparent;
    border-radius: 10px;
    padding: 6px 10px;
}}
QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background-color: rgba(255, 255, 255, 22);
    color: #FFFFFF;
}}
QMenu {{
    background-color: #131724;
    color: #E8EAF4;
    border: 1px solid #4F5B7C;
    border-radius: 14px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 26px 8px 14px;
    border-radius: 9px;
    margin: 1px 0px;
}}
QMenu::item:selected {{
    background-color: #6F5CFF;
    color: #FFFFFF;
}}
QMenu::item:checked {{
    background-color: rgba(111, 92, 255, 90);
    color: #FFFFFF;
}}
QMenu::item:disabled {{
    color: #6F7484;
}}
QMenu::separator {{
    height: 1px;
    background-color: #30384F;
    margin: 5px 8px;
}}

QScrollBar:horizontal,
QScrollBar:vertical {{
    background: transparent;
    border: none;
    margin: 2px;
}}
QScrollBar:horizontal {{
    height: 10px;
}}
QScrollBar:vertical {{
    width: 10px;
}}
QScrollBar::handle:horizontal,
QScrollBar::handle:vertical {{
    background-color: rgba(255, 255, 255, 38);
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover,
QScrollBar::handle:vertical:hover {{
    background-color: rgba(255, 255, 255, 70);
}}
QScrollBar::handle:horizontal:pressed,
QScrollBar::handle:vertical:pressed {{
    background-color: #7E6BFF;
}}
QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {{
    background: transparent;
    border: none;
    width: 0px;
    height: 0px;
}}

QProgressBar {{
    background-color: rgba(255, 255, 255, 12);
    color: #EEF0F8;
    border: 1px solid #30384F;
    border-radius: 10px;
    min-height: 16px;
    text-align: center;
    font-weight: 800;
}}
QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF8057,
        stop:0.45 #F65368,
        stop:1 #755DF2
    );
    border-radius: 9px;
}}

QToolBar,
QStatusBar {{
    background-color: rgba(12, 15, 26, 238);
    color: #C9CEDC;
    border: 1px solid rgba(126, 141, 198, 36);
}}
QToolBar::separator {{
    background-color: #30384F;
    width: 1px;
    margin: 6px;
}}
QSplitter::handle {{
    background-color: rgba(126, 141, 198, 34);
}}
QSplitter::handle:hover {{
    background-color: rgba(126, 141, 198, 86);
}}
QSizeGrip {{
    background: transparent;
}}
QToolTip {{
    background-color: #171B2A;
    color: #F8F4EA;
    border: 1px solid #7580A5;
    border-radius: 10px;
    padding: 7px 10px;
}}

/* -----------------------------------------------------------------
 * Startup launcher. This is the first impression of the app, so it
 * uses the same Screen-Studio-like glass vocabulary as the editor while
 * staying compact and action-first.
 * ----------------------------------------------------------------- */
QWidget#Central {{
    background-color: #090B13;
}}
QScrollArea#LauncherScroll,
QWidget#LauncherScrollContent {{
    background-color: transparent;
    border: none;
}}
QLabel#LauncherBrand {{
    color: #F8F4EA;
    font-size: 13px;
    font-weight: 900;
    padding: 5px 11px;
    border: 1px solid rgba(255, 255, 255, 38);
    border-radius: 14px;
    background-color: rgba(255, 255, 255, 12);
}}
QLabel#SectionLabel,
QLabel#LauncherEyebrow,
QLabel#AppTitle,
QLabel#LauncherSubtitle,
QLabel#LauncherOptionLabel,
QLabel#LauncherDropTitle,
QLabel#LauncherDropBody,
QLabel#CreditFooter {{
    background: transparent;
    border: none;
}}
QFrame#LauncherHero {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #161A2A,
        stop:0.62 #101421,
        stop:1 #171224
    );
    border: 1px solid rgba(126, 141, 198, 44);
    border-radius: 20px;
}}
QLabel#LauncherEyebrow {{
    color: #9EA6C7;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 0px;
}}
QLabel#AppTitle {{
    color: #FFFFFF;
    font-size: 24px;
    font-weight: 950;
}}
QLabel#LauncherSubtitle {{
    color: #AEB5CA;
    font-size: 12px;
    font-weight: 650;
}}
QFrame#LauncherPanel,
QFrame#LauncherQuickPanel,
QFrame#LauncherTemplatePanel,
QFrame#LauncherOptions,
QFrame#LauncherSettingsPanel,
QFrame#LauncherDropZone {{
    background-color: rgba(18, 21, 34, 226);
    border: 1px solid rgba(126, 141, 198, 44);
    border-radius: 18px;
}}
QFrame#LauncherQuickPanel {{
    background-color: rgba(13, 16, 27, 180);
    border: 1px solid rgba(126, 141, 198, 40);
    border-radius: 18px;
}}
QFrame#LauncherWorkspaceSwitch {{
    background-color: rgba(255, 255, 255, 6);
    border: 1px solid rgba(126, 141, 198, 26);
    border-radius: 15px;
}}
QPushButton#LauncherWorkspaceToggle {{
    background-color: transparent;
    border: none;
    padding: 0;
}}
QPushButton#LauncherWorkspaceButton {{
    background-color: transparent;
    color: #AEB7D3;
    border: 1px solid transparent;
    border-radius: 13px;
    padding: 5px 12px;
    min-height: 26px;
    min-width: 62px;
    font-size: 10px;
    font-weight: 900;
}}
QPushButton#LauncherWorkspaceButton:hover {{
    background-color: rgba(255, 255, 255, 18);
    color: #FFFFFF;
}}
QPushButton#LauncherWorkspaceButton:checked {{
    color: #FFFFFF;
    border-color: rgba(255, 255, 255, 105);
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.48 #7358F2,
        stop:1 #2ECBE7
    );
}}
QFrame#LauncherSettingsPanel {{
    background-color: rgba(255, 255, 255, 8);
    border: 1px solid rgba(126, 141, 198, 28);
    border-radius: 16px;
}}
QFrame#LauncherDelayStrip {{
    background-color: rgba(255, 255, 255, 10);
    border: 1px solid rgba(126, 141, 198, 34);
    border-radius: 13px;
}}
QPushButton[delayButton="true"] {{
    background-color: transparent;
    color: #AEB7D3;
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 900;
}}
QPushButton[delayButton="true"]:hover {{
    background-color: rgba(255, 255, 255, 18);
    color: #FFFFFF;
}}
QPushButton[delayButton="true"]:checked {{
    color: #FFFFFF;
    border-color: rgba(255, 255, 255, 98);
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.48 #7358F2,
        stop:1 #2ECBE7
    );
}}
QFrame#LauncherPanel[density="quiet"] {{
    background-color: rgba(18, 21, 34, 176);
    border-color: rgba(126, 141, 198, 34);
}}
QFrame#LauncherTemplatePanel {{
    background-color: rgba(13, 16, 27, 142);
    border: 1px solid rgba(126, 141, 198, 30);
    border-radius: 16px;
}}
QFrame#LauncherDropZone {{
    border-style: dashed;
    background-color: rgba(255, 255, 255, 8);
}}
QLabel#LauncherOptionLabel,
QLabel#LauncherDropTitle {{
    color: #F4F6FF;
    font-size: 12px;
    font-weight: 850;
}}
QLabel#LauncherBusyLabel {{
    color: #F4F6FF;
    font-size: 11px;
    font-weight: 850;
    background: transparent;
    border: none;
}}
QLabel#LauncherHint {{
    color: #8E96B2;
    font-size: 10px;
    font-weight: 700;
    background: transparent;
    border: none;
}}
QLabel#LauncherDropBody {{
    color: #8E96B2;
    font-size: 11px;
    font-weight: 650;
}}
QFrame#LauncherBusy {{
    background-color: rgba(255, 128, 87, 24);
    border: 1px solid rgba(255, 154, 120, 122);
    border-radius: 15px;
}}
QProgressBar#LauncherProgress {{
    background-color: rgba(255, 255, 255, 16);
    border: 1px solid rgba(255, 255, 255, 24);
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
}}
QProgressBar#LauncherProgress::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF8057,
        stop:0.52 #F65368,
        stop:1 #755DF2
    );
    border-radius: 4px;
}}
QPushButton#NewCaptureButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.62 #F65343,
        stop:1 #E84E78
    );
    color: #FFFFFF;
    border: 1px solid #FFAB8E;
    border-radius: 15px;
    padding: 9px 15px;
    font-size: 13px;
    font-weight: 950;
}}
QPushButton#NewCaptureButton:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF9877,
        stop:0.62 #FF6348,
        stop:1 #F05B8C
    );
    border-color: #FFD0C0;
}}
QPushButton[modeButton="true"] {{
    background-color: rgba(255, 255, 255, 13);
    color: #CBD1E2;
    border: 1px solid #30384F;
    border-radius: 16px;
    padding: 9px 12px;
    font-size: 12px;
    font-weight: 800;
}}
QPushButton[modeButton="true"][compact="true"] {{
    border-radius: 13px;
    padding: 6px 9px;
    font-size: 11px;
    min-height: 30px;
}}
QPushButton[modeButton="true"]:hover {{
    background-color: rgba(255, 255, 255, 24);
    border-color: #7580A5;
    color: #FFFFFF;
}}
QPushButton[modeButton="true"]:checked {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3945E8,
        stop:0.52 #7358F2,
        stop:1 #22BDE4
    );
    border-color: #C2BAFF;
    color: #FFFFFF;
}}
QPushButton#ProEditorButton,
QPushButton#SoundEditorButton {{
    background-color: rgba(255, 255, 255, 14);
    color: #F2F4FF;
    border: 1px solid #37405A;
    border-radius: 17px;
    padding: 12px 15px;
    font-size: 13px;
    font-weight: 900;
    text-align: left;
}}
QPushButton#ProEditorButton:hover,
QPushButton#SoundEditorButton:hover {{
    background-color: rgba(255, 255, 255, 27);
    border-color: #8F99C9;
}}
QPushButton#LauncherMiniCard {{
    background-color: rgba(255, 255, 255, 12);
    color: #F2F4FF;
    border: 1px solid #30384F;
    border-radius: 14px;
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 850;
    text-align: left;
}}
QPushButton#LauncherMiniCard[density="compact"] {{
    background-color: rgba(255, 255, 255, 9);
    border-color: rgba(126, 141, 198, 36);
    border-radius: 14px;
    padding: 5px 10px;
    font-size: 10px;
}}
QPushButton#LauncherMiniCard:hover {{
    background-color: rgba(255, 255, 255, 24);
    border-color: #8F99C9;
}}
QPushButton#LauncherMiniCard:disabled {{
    color: #8189A2;
    background-color: rgba(255, 255, 255, 7);
    border-color: rgba(126, 141, 198, 28);
}}
QPushButton#LauncherMiniCard[tone="project"] {{
    background-color: rgba(255, 255, 255, 10);
    border-color: rgba(151, 144, 255, 82);
}}
QPushButton#LauncherMiniCard[tone="video"],
QPushButton#LauncherMiniCard[tone="gif"] {{
    background-color: rgba(255, 128, 87, 16);
    border-color: rgba(255, 171, 142, 72);
}}
QPushButton#LauncherMiniCard[tone="image"] {{
    background-color: rgba(103, 232, 201, 13);
    border-color: rgba(103, 232, 201, 62);
}}
QPushButton#LauncherMiniCard[tone="template0"] {{
    background-color: rgba(255, 255, 255, 10);
    border-color: rgba(255, 255, 255, 50);
}}
QPushButton#LauncherMiniCard[tone="template1"] {{
    background-color: rgba(255, 255, 255, 10);
    border-color: rgba(255, 255, 255, 50);
}}
QPushButton#LauncherMiniCard[tone="template2"] {{
    background-color: rgba(255, 255, 255, 10);
    border-color: rgba(255, 255, 255, 50);
}}
QPushButton#LauncherStartCard {{
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 46);
    border-radius: 16px;
    padding: 8px 11px;
    font-size: 11px;
    font-weight: 950;
    text-align: left;
}}
QPushButton#LauncherStartCard:hover {{
    border-color: rgba(255, 255, 255, 112);
}}
QPushButton#LauncherStartCard[tone="record"] {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.58 #F65368,
        stop:1 #7358F2
    );
}}
QPushButton#LauncherStartCard[tone="record"]:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF9877,
        stop:0.58 #FF6376,
        stop:1 #897CFF
    );
}}
QPushButton#LauncherStartCard[tone="edit"] {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #2ECBE7,
        stop:0.50 #5B68F6,
        stop:1 #8B78FF
    );
}}
QPushButton#LauncherStartCard[tone="edit"]:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #58DDF2,
        stop:0.50 #6F78FF,
        stop:1 #9C8EFF
    );
}}
QPushButton#LauncherStartCard[tone="template"] {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FFB85B,
        stop:0.48 #FF7CB8,
        stop:1 #7E6BFF
    );
}}
QPushButton#LauncherStartCard[tone="template"]:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FFD083,
        stop:0.48 #FF8EC4,
        stop:1 #9182FF
    );
}}
QPushButton#LauncherGhostButton {{
    background-color: transparent;
    color: #9EA6C7;
    border: 1px solid rgba(126, 141, 198, 28);
    border-radius: 13px;
    padding: 5px 10px;
    min-height: 30px;
    font-size: 10px;
    font-weight: 850;
}}
QPushButton#LauncherGhostButton:hover {{
    background-color: rgba(255, 255, 255, 13);
    color: #FFFFFF;
    border-color: rgba(126, 141, 198, 70);
}}
QPushButton#DonateButton {{
    background-color: rgba(255, 255, 255, 9);
    color: #FF9A78;
    border: 1px solid rgba(255, 154, 120, 120);
    border-radius: 13px;
    padding: 5px 11px;
    font-weight: 850;
}}
QPushButton#IconButton {{
    background-color: rgba(255, 255, 255, 9);
    border: 1px solid rgba(255, 255, 255, 24);
    border-radius: 13px;
    padding: 4px 8px;
}}
"""


LOCAL_STUDIO_CHROME_QSS = f"""
/* Studio chrome patch for widgets/windows that set their own QSS. */
QWidget {{
    background-color: #0B0D16;
    color: #E6E8F2;
    font-family: {FONT_FAMILY};
}}
QDialog {{
    background-color: #0B0D16;
    color: #E6E8F2;
    font-family: {FONT_FAMILY};
}}
QFrame,
QGroupBox {{
    background-color: rgba(18, 21, 34, 232);
    border: 1px solid rgba(126, 141, 198, 48);
    border-radius: 14px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0px 8px;
    color: #A7ADC2;
    font-size: 10px;
    font-weight: 800;
}}
QPushButton,
QPushButton#ToolButton,
QPushButton#IconButton,
QDialogButtonBox QPushButton,
QToolButton {{
    background-color: rgba(255, 255, 255, 18);
    color: #E8EAF4;
    border: 1px solid #37405A;
    border-radius: 13px;
    padding: 7px 13px;
    min-height: 24px;
    font-weight: 700;
}}
QPushButton:hover,
QPushButton#ToolButton:hover,
QPushButton#IconButton:hover,
QDialogButtonBox QPushButton:hover,
QToolButton:hover {{
    background-color: rgba(255, 255, 255, 30);
    color: #FFFFFF;
    border-color: #7580A5;
}}
QPushButton:pressed,
QPushButton#ToolButton:pressed,
QPushButton#IconButton:pressed,
QDialogButtonBox QPushButton:pressed,
QToolButton:pressed {{
    background-color: rgba(255, 255, 255, 24);
    border-color: #A79EFF;
}}
QPushButton:checked,
QPushButton#ToolButton:checked,
QPushButton#IconButton:checked,
QToolButton:checked {{
    background-color: #6F5CFF;
    color: #FFFFFF;
    border-color: #C2BAFF;
}}
QPushButton:default,
QDialogButtonBox QPushButton:default,
QPushButton[variant="primary"] {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.62 #F65343,
        stop:1 #E84E78
    );
    color: #FFFFFF;
    border-color: #FF9A78;
    font-weight: 800;
}}
QPushButton:disabled,
QToolButton:disabled {{
    background-color: rgba(255, 255, 255, 7);
    border-color: #252B3A;
    color: #6F7484;
}}
QLineEdit,
QTextEdit,
QPlainTextEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {{
    background-color: rgba(255, 255, 255, 13);
    color: #EEF0F8;
    border: 1px solid #30384F;
    border-radius: 13px;
    padding: 7px 11px;
    selection-background-color: #6F5CFF;
    selection-color: #FFFFFF;
}}
QLineEdit:hover,
QTextEdit:hover,
QPlainTextEdit:hover,
QSpinBox:hover,
QDoubleSpinBox:hover,
QComboBox:hover {{
    background-color: rgba(255, 255, 255, 22);
    border-color: #7580A5;
}}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus,
QComboBox:on {{
    border-color: #8A7CFF;
}}
QListWidget,
QListView,
QTreeWidget,
QTreeView,
QTableWidget,
QTableView,
QScrollArea {{
    background-color: rgba(10, 12, 21, 220);
    color: #D7DAE7;
    border: 1px solid #30384F;
    border-radius: 14px;
    outline: none;
}}
QListWidget::item:hover,
QListView::item:hover,
QTreeWidget::item:hover,
QTreeView::item:hover {{
    background-color: rgba(255, 255, 255, 26);
    color: #FFFFFF;
}}
QListWidget::item:selected,
QListView::item:selected,
QTreeWidget::item:selected,
QTreeView::item:selected {{
    background-color: #6F5CFF;
    color: #FFFFFF;
}}
QMenu {{
    background-color: #131724;
    color: #E8EAF4;
    border: 1px solid #4F5B7C;
    border-radius: 14px;
    padding: 6px;
}}
QMenu::item {{
    padding: 8px 26px 8px 14px;
    border-radius: 9px;
}}
QMenu::item:selected {{
    background-color: #6F5CFF;
    color: #FFFFFF;
}}
QSlider::groove:horizontal {{
    background: #292B35;
    height: 3px;
    border-radius: 2px;
}}
QSlider::sub-page:horizontal {{
    background: #5B45FF;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: #6452FF;
    border: 1px solid #9C8EFF;
    width: 14px;
    height: 14px;
    margin: -6px 0px;
    border-radius: 7px;
}}
QScrollBar:horizontal,
QScrollBar:vertical {{
    background: transparent;
    border: none;
    margin: 2px;
}}
QScrollBar:horizontal {{
    height: 10px;
}}
QScrollBar:vertical {{
    width: 10px;
}}
QScrollBar::handle:horizontal,
QScrollBar::handle:vertical {{
    background-color: rgba(255, 255, 255, 38);
    border-radius: 4px;
}}
QScrollBar::handle:horizontal:hover,
QScrollBar::handle:vertical:hover {{
    background-color: rgba(255, 255, 255, 70);
}}
QSplitter::handle {{
    background-color: rgba(126, 141, 198, 60);
}}

/* Catalog neutral button pass. Keep generated-style chrome subdued:
 * dark controls, thin borders, and color reserved for content/state. */
QPushButton,
QToolButton,
QCommandLinkButton {{
    background-color: #14171D;
    color: #D9DDE4;
    border: 1px solid #2B313B;
    border-radius: 12px;
    padding: 7px 13px;
    min-height: 26px;
    font-weight: 650;
}}
QPushButton:hover,
QToolButton:hover,
QCommandLinkButton:hover {{
    background-color: #1B1F27;
    color: #F4F6FA;
    border-color: #4B5668;
}}
QPushButton:pressed,
QToolButton:pressed,
QCommandLinkButton:pressed {{
    background-color: #202633;
    border-color: #8796AD;
}}
QPushButton:checked,
QToolButton:checked {{
    background-color: #232B38;
    border-color: #A8B5C9;
    color: #FFFFFF;
}}
QPushButton:default,
QPushButton[variant="primary"],
QPushButton#PrimaryToolButton {{
    background-color: #191D24;
    border-color: #6F7F99;
    color: #F7F8FA;
    font-weight: 800;
}}
QPushButton:default:hover,
QPushButton[variant="primary"]:hover,
QPushButton#PrimaryToolButton:hover {{
    background-color: #202633;
    border-color: #A6B3C8;
}}
QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus,
QComboBox:on {{
    border-color: #7B8DA8;
}}
QListWidget::item:selected,
QListView::item:selected,
QTreeWidget::item:selected,
QTreeView::item:selected,
QMenu::item:selected {{
    background-color: #232B38;
    color: #FFFFFF;
}}
QSlider::sub-page:horizontal {{
    background: #6E86A7;
}}
QSlider::handle:horizontal {{
    background: #93A8C3;
    border-color: #D6DEE9;
}}
QToolTip {{
    background-color: #171B2A;
    color: #F8F4EA;
    border: 1px solid #7580A5;
    border-radius: 10px;
    padding: 7px 10px;
}}
"""


def studio_chrome_qss(base: str = "") -> str:
    """Append studio Qt chrome after a local widget QSS block."""
    return f"{base or ''}\n{LOCAL_STUDIO_CHROME_QSS}"
