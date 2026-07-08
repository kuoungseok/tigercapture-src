from __future__ import annotations

from app.style import (
    COLOR_ACCENT_AUDIO,
    COLOR_ACCENT_BLUE,
    COLOR_ACCENT_BLUE_HOVER,
    COLOR_ACCENT_GREEN,
    COLOR_ACCENT_LIVE2D,
    COLOR_ACCENT_ORANGE,
    COLOR_ACCENT_SPINE,
    COLOR_ACCENT_HOVER,
    COLOR_ACCENT_PRESSED,
    COLOR_APP_BG,
    COLOR_BG_L1,
    COLOR_BG_L2,
    COLOR_BG_L3,
    COLOR_BG_L4,
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
    COLOR_TIMELINE_AUDIO_BG,
    COLOR_TIMELINE_AUDIO_STRIPE,
    COLOR_TIMELINE_BG,
    COLOR_TIMELINE_STRIPE,
    COLOR_TIMELINE_VIDEO_BG,
    COLOR_TIMELINE_VIDEO_STRIPE,
)

VIDEO_EDITOR_EXTRA_QSS = f"""
/* Global font override for editor chrome */
* {{
    font-family: "Noto Sans KR", "Noto Sans CJK KR", "Malgun Gothic",
                 "Pretendard", "Segoe UI Variable", "Segoe UI", "Arial", "Tahoma";
    letter-spacing: 0.1px;
}}

QWidget#EditorRoot {{
    background-color: {COLOR_APP_BG};
    color: {COLOR_TEXT_SECONDARY};
}}

/* Left / Right dock columns */
QWidget#CenterWorkbench {{
    background-color: {COLOR_APP_BG};
}}

QWidget#LeftDockColumn, QWidget#RightDockColumn {{
    background-color: {COLOR_PANEL_RAIL};
}}

QWidget#LeftDockColumn {{
    border-right: none;
}}

QWidget#RightDockColumn {{
    border-left: 1px solid {COLOR_BORDER_SUBTLE};
}}

QSplitter::handle {{
    background-color: {COLOR_BORDER_SUBTLE};
}}

QSplitter::handle:hover {{
    background-color: {COLOR_BORDER_FOCUS};
}}

QWidget#AppCommandBar,
QWidget#TimelineToolBar,
QWidget#TimelineEffectsBar,
QWidget#SelectionBar {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QWidget#TimelineSectionHost,
QWidget#MediaPoolSectionHost,
QWidget#ActorLibrarySectionHost,
QWidget#EffectsLibrarySectionHost,
QWidget#TitlePresetsSectionHost,
QWidget#TransitionsSectionHost,
QWidget#WorkflowPresetsSectionHost,
QWidget#WorkbenchSectionHost {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QWidget#CollapsibleSectionHeader {{
    background-color: {COLOR_PANEL_HEADER};
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    min-height: 30px;
    max-height: 30px;
}}

QPushButton#SectionDisclosure {{
    background-color: transparent;
    color: {COLOR_TEXT_TERTIARY};
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 2px 8px;
    min-height: 20px;
    font-size: 10px;
    font-weight: 700;
}}
QPushButton#SectionDisclosure:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_DEFAULT};
}}
QPushButton#SectionDisclosure:checked {{
    color: {COLOR_TEXT_PRIMARY};
}}

QToolButton#CommandMenuButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 5px 24px 5px 10px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 600;
}}
QToolButton#CommandMenuButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: #4a4a52;
}}
QToolButton#CommandMenuButton[startupTemplate="true"] {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF755D,
        stop:0.52 #9A74FF,
        stop:1 #54C8F5
    );
    color: #FFFFFF;
    border: 1px solid rgba(255, 255, 255, 150);
}}
QToolButton#CommandMenuButton[startupTemplate="true"]:hover {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8B67,
        stop:0.52 #A984FF,
        stop:1 #63D7FF
    );
    border-color: #FFFFFF;
}}
QToolButton#CommandMenuButton::menu-indicator {{
    image: none;
    subcontrol-origin: padding;
    subcontrol-position: right center;
    right: 7px;
}}

QLabel {{
    color: {COLOR_TEXT_SECONDARY};
    background: transparent;
}}

/* ToolButton: compact, professional toolbar look */
QPushButton#ToolButton {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_DEFAULT};
    border-radius: 6px;
    padding: 5px 9px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 500;
}}
QPushButton#ToolButton:hover {{
    background-color: {COLOR_BG_L6};
    border-color: #4a4a52;
    color: {COLOR_TEXT_PRIMARY};
}}
QPushButton#ToolButton:pressed {{
    background-color: {COLOR_BG_L4};
    border-color: #3a3a42;
}}
QPushButton#ToolButton:disabled {{
    color: {COLOR_TEXT_DISABLED};
    border-color: {COLOR_BORDER_SUBTLE};
    background-color: {COLOR_BG_L3};
}}
QPushButton#ToolButton:checked {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border-color: {COLOR_ACCENT_BLUE};
}}

/* PrimaryToolButton */
QPushButton#PrimaryToolButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border: 1px solid {COLOR_ACCENT_BLUE};
    border-radius: 6px;
    padding: 5px 16px;
    min-height: 24px;
    font-size: 11px;
    font-weight: 700;
}}
QPushButton#PrimaryToolButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
    border-color: {COLOR_ACCENT_BLUE_HOVER};
}}
QPushButton#PrimaryToolButton:pressed {{
    background-color: {COLOR_ACCENT_PRESSED};
    border-color: {COLOR_ACCENT_PRESSED};
}}

/* SpeedActive */
QPushButton#SpeedActive {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_ACCENT_BLUE};
    border-radius: 6px;
    padding: 5px 11px;
    font-weight: 700;
}}

/* Section headers: all variants share height / font
   Accent bar changes per panel identity (preview / timeline / subtitles).
   Height is held at 28px (line-height + padding) for vertical rhythm.    */
QLabel[sectionHeader="true"] {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 0px 12px;
    min-height: 28px;
    max-height: 28px;
    background-color: {COLOR_BG_L4};
    border-left: 3px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="preview"] {{
    border-left: 3px solid {COLOR_ACCENT_BLUE};
}}
QLabel[sectionHeader="true"][accent="timeline"] {{
    border-left: 1px solid #343434;
}}
QLabel[sectionHeader="true"][accent="subtitles"] {{
    border-left: 3px solid {COLOR_ACCENT_GREEN};
}}

/* Preview section header (custom widget wrapping label + pop-out btn) */
QWidget#PreviewSectionHeader {{
    background-color: {COLOR_PANEL_HEADER};
    border-left: 3px solid {COLOR_ACCENT_BLUE};
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    min-height: 28px;
    max-height: 28px;
}}
QLabel#PreviewSectionTitle {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    padding: 0px 12px;
    min-height: 28px;
    background: transparent;
}}
QPushButton#PreviewPopoutIcon {{
    background-color: transparent;
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid transparent;
    border-radius: 4px;
    font-size: 15px;
    padding: 0;
}}
QPushButton#PreviewPopoutIcon:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_BORDER_DEFAULT};
}}
QPushButton#PreviewPopoutIcon:pressed {{
    background-color: {COLOR_BG_L2};
}}
QPushButton#PreviewPopoutIcon[popped="true"] {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border-color: {COLOR_ACCENT_BLUE};
}}

/* Preview + play area */
QWidget#PreviewHost {{
    background-color: {COLOR_BG_L1};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-top: none;
    border-bottom-left-radius: 7px;
    border-bottom-right-radius: 7px;
}}

QWidget#PlayBar {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QWidget#ControlsBar {{
    background-color: {COLOR_PANEL_BG};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 7px;
}}

QWidget#TimelineSectionHeader,
QWidget#ColorSectionHeader {{
    background-color: {COLOR_PANEL_HEADER};
    border-bottom: 1px solid {COLOR_BORDER_SUBTLE};
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    min-height: 30px;
    max-height: 30px;
}}

QLabel#MediaPoolSearchLabel {{
    color: {COLOR_TEXT_TERTIARY};
    font-size: 10px;
    font-weight: 700;
}}

QLineEdit#MediaPoolSearch {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_PRIMARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 5px;
    padding: 5px 8px;
    min-height: 22px;
}}

QLineEdit#MediaPoolSearch:focus {{
    border-color: {COLOR_ACCENT_ORANGE};
}}

/* Mono labels (time / zoom readouts)
   JetBrains Mono -> Cascadia Code -> Consolas -> consistent digit width. */
QLabel#TimeLabel {{
    color: {COLOR_TEXT_PRIMARY};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0px;
}}
QLabel#SpeedLabel,
QPushButton#SpeedLabel {{
    color: {COLOR_ACCENT_BLUE};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    font-weight: 700;
    letter-spacing: 0px;
}}
QLabel#ZoomLabel {{
    color: {COLOR_TEXT_TERTIARY};
    font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Courier New", monospace;
    letter-spacing: 0px;
}}

QLabel#TimelineStatusChip {{
    color: {COLOR_TEXT_SECONDARY};
    background-color: {COLOR_BG_L3};
    border: 1px solid {COLOR_BG_L5};
    border-radius: 11px;
    padding: 7px 12px;
    font-size: 11px;
}}

/* Play button */
QPushButton#PlayButton {{
    background-color: {COLOR_ACCENT_BLUE};
    color: {COLOR_TEXT_PRIMARY};
    border: none;
    border-radius: 19px;
    font-size: 14px;
    font-weight: 700;
}}
QPushButton#PlayButton:hover {{
    background-color: {COLOR_ACCENT_BLUE_HOVER};
}}

/* Scroll areas + scrollbars */
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    border: none;
    margin: 1px;
}}
QScrollBar::handle:horizontal {{
    background: #38383e;
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #48484e;
}}
QScrollBar::handle:horizontal:pressed {{
    background: {COLOR_ACCENT_BLUE};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    border: none;
    margin: 1px;
}}
QScrollBar::handle:vertical {{
    background: #38383e;
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: #48484e;
}}
QScrollBar::handle:vertical:pressed {{
    background: {COLOR_ACCENT_BLUE};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: transparent;
}}

/* Separator lines
   QFrame with HLine(4)/VLine(5) shape used as dividers.                  */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: #2a2a38;
    max-height: 1px;
    border: none;
}}

/* List widget */
QListWidget {{
    background-color: {COLOR_BG_L2};
    color: {COLOR_TEXT_SECONDARY};
    border: 1px solid {COLOR_BORDER_SUBTLE};
    border-radius: 4px;
    alternate-background-color: {COLOR_BG_L3};
    outline: none;
}}
QListWidget::item {{
    padding: 4px 8px;
    border-radius: 3px;
}}
QListWidget::item:hover {{
    background-color: {COLOR_BG_L5};
    color: {COLOR_TEXT_PRIMARY};
}}
QListWidget::item:selected {{
    background-color: {COLOR_ACCENT_BLUE};
    color: #FFFFFF;
    border-left: 2px solid {COLOR_ACCENT_BLUE_HOVER};
}}

/* -----------------------------------------------------------------
 * Studio look pass: larger floating surfaces, softer borders, lower
 * contrast rails, and pill-like controls. This intentionally overrides
 * the earlier practical editor theme without changing widget behavior.
 * ----------------------------------------------------------------- */
QWidget#EditorRoot,
QWidget#CenterWorkbench {{
    background-color: #141414;
}}

QWidget#LeftDockColumn,
QWidget#RightDockColumn {{
    background-color: #141414;
    border: none;
}}

QWidget#AppCommandBar,
QWidget#PlayBar,
QWidget#TimelineToolBar,
QWidget#TimelineEffectsBar,
QWidget#SelectionBar {{
    background-color: #12141E;
    border: 1px solid #2A2D3A;
    border-radius: 14px;
}}

QWidget#MediaPoolSectionHost,
QWidget#ActorLibrarySectionHost,
QWidget#WorkbenchSectionHost,
QWidget#EffectsLibrarySectionHost,
QWidget#TitlePresetsSectionHost,
QWidget#TransitionsSectionHost,
QWidget#WorkflowPresetsSectionHost,
QWidget#TimelineSectionHost {{
    background-color: #0E1018;
    border: 1px solid #2B2F3C;
    border-radius: 16px;
}}

QWidget#CollapsibleSectionHeader,
QWidget#TimelineSectionHeader,
QWidget#ColorSectionHeader,
QWidget#PreviewSectionHeader {{
    background-color: #18191F;
    border: none;
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    min-height: 34px;
    max-height: 34px;
}}

QLabel[sectionHeader="true"],
QLabel#PreviewSectionTitle {{
    background: transparent;
    border-left: none;
    color: #F2F0EA;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.7px;
    padding-left: 14px;
}}

QWidget#PreviewHost {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #11121C,
        stop:0.46 #06070C,
        stop:1 #161221
    );
    border: 1px solid #2B3040;
    border-top: none;
    border-bottom-left-radius: 18px;
    border-bottom-right-radius: 18px;
}}

QToolButton#CommandMenuButton,
QPushButton#ToolButton {{
    background-color: rgba(255, 255, 255, 18);
    color: #D7DAE7;
    border: 1px solid #30374C;
    border-radius: 11px;
    padding: 7px 12px;
    min-height: 28px;
    font-size: 11px;
    font-weight: 600;
}}

QToolButton#CommandMenuButton:hover,
QPushButton#ToolButton:hover {{
    background-color: rgba(255, 255, 255, 30);
    color: #FFFFFF;
    border-color: #606B8D;
}}

QPushButton#ToolButton:checked {{
    background-color: #5B45FF;
    color: #FFFFFF;
    border-color: #A89CFF;
}}

QPushButton#PrimaryToolButton {{
    background-color: #F0643B;
    color: #FFFFFF;
    border: 1px solid #FF805A;
    border-radius: 12px;
    padding: 7px 18px;
    min-height: 30px;
    font-size: 11px;
    font-weight: 700;
}}

QPushButton#PrimaryToolButton:hover {{
    background-color: #FF7048;
    border-color: #FF9A78;
}}

QWidget#AppCommandBar {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20, 24, 38, 236),
        stop:0.48 rgba(12, 15, 26, 238),
        stop:1 rgba(18, 16, 30, 236)
    );
    border: 1px solid rgba(126, 141, 198, 58);
    border-radius: 18px;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton,
QWidget#AppCommandBar QPushButton#ToolButton {{
    background-color: rgba(255, 255, 255, 18);
    color: #E8EAF4;
    border: 1px solid #37405A;
    border-radius: 14px;
    padding: 0px;
    min-width: 40px;
    min-height: 38px;
    font-size: 1px;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton:hover,
QWidget#AppCommandBar QPushButton#ToolButton:hover {{
    background-color: rgba(255, 255, 255, 30);
    border-color: #7580A5;
}}

QWidget#AppCommandBar QPushButton#ToolButton:checked {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3945E8,
        stop:0.52 #7358F2,
        stop:1 #22BDE4
    );
    border-color: #C2BAFF;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton::menu-indicator {{
    image: none;
    width: 0px;
}}

QWidget#AppCommandBar QPushButton#PrimaryToolButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8057,
        stop:0.62 #F65343,
        stop:1 #E84E78
    );
    border: 1px solid #FF9A78;
    border-radius: 16px;
    padding: 0px 18px;
    min-height: 38px;
    font-size: 12px;
    font-weight: 800;
}}

QWidget#AppCommandBar QPushButton#PrimaryToolButton:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF9877,
        stop:0.62 #FF6348,
        stop:1 #F05B8C
    );
    border-color: #FFC1AA;
}}

QPushButton#PlayButton {{
    background-color: #F0643B;
    color: #FFFFFF;
    border: none;
    border-radius: 21px;
    font-size: 15px;
    font-weight: 700;
}}

QLineEdit#MediaPoolSearch,
QComboBox,
QListWidget {{
    background-color: #0B0C12;
    color: #D7DAE7;
    border: 1px solid #2A2E3C;
    border-radius: 11px;
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {{
    background: #4A4F64;
    border-radius: 4px;
}}

/* Screen-recorder palette pass: timeline command surfaces should read as
   light glass rails, while draggable timeline effects read as color swatches. */
QWidget#PlayBar,
QWidget#TimelineToolBar,
QWidget#TimelineEffectsBar,
QWidget#SelectionBar {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(24, 28, 43, 220),
        stop:0.58 rgba(13, 16, 28, 222),
        stop:1 rgba(18, 14, 28, 220)
    );
    border: 1px solid rgba(126, 141, 198, 58);
    border-radius: 16px;
}}

QWidget#PlayBar QPushButton#ToolButton {{
    background-color: rgba(255, 255, 255, 14);
    color: #E6E8F2;
    border: 1px solid rgba(126, 141, 198, 54);
    border-radius: 13px;
    padding: 0px;
    min-width: 34px;
    min-height: 32px;
    font-size: 1px;
}}

QWidget#PlayBar QPushButton#ToolButton:hover {{
    background-color: rgba(255, 255, 255, 30);
    border-color: #7580A5;
}}

QWidget#PlayBar QPushButton#ToolButton:disabled {{
    background-color: rgba(255, 255, 255, 8);
    border-color: #262C3D;
}}

QWidget#PlayBar QLabel#SpeedLabel,
QWidget#PlayBar QPushButton#SpeedLabel {{
    background-color: rgba(12, 13, 21, 190);
    color: #FFD176;
    border: 1px solid rgba(255, 193, 93, 118);
    border-radius: 12px;
    padding: 4px 8px;
    font-size: 12px;
    font-weight: 800;
}}

QWidget#TimelineEffectsBar {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #131A2A,
        stop:0.48 #111225,
        stop:1 #171122
    );
    border-color: #38425C;
}}

QLabel#PaletteHint {{
    color: #8890A8;
    background-color: rgba(255, 255, 255, 14);
    border: 1px solid #2E354B;
    border-radius: 12px;
    padding: 5px 10px;
    font-size: 11px;
    font-weight: 700;
}}

QWidget#TimelineToolBar QPushButton#ToolButton,
QWidget#SelectionBar QPushButton#ToolButton,
QWidget#TimelineToolBar QToolButton#CommandMenuButton {{
    background-color: rgba(255, 255, 255, 20);
    color: #E6E8F2;
    border: 1px solid #37405A;
    border-radius: 14px;
    padding: 7px 13px;
    min-height: 30px;
    font-size: 11px;
    font-weight: 700;
}}

QWidget#TimelineToolBar QPushButton#ToolButton:hover,
QWidget#SelectionBar QPushButton#ToolButton:hover,
QWidget#TimelineToolBar QToolButton#CommandMenuButton:hover {{
    background-color: rgba(255, 255, 255, 32);
    color: #FFFFFF;
    border-color: #65708C;
}}

QWidget#TimelineToolBar QPushButton#ToolButton:checked,
QWidget#SelectionBar QPushButton#ToolButton:checked {{
    background-color: #5B45FF;
    color: #FFFFFF;
    border-color: #A89CFF;
}}

QWidget#TimelineToolBar QPushButton#ToolButton:disabled,
QWidget#SelectionBar QPushButton#ToolButton:disabled {{
    background-color: rgba(255, 255, 255, 9);
    color: #6F7484;
    border-color: #252B3A;
}}

QLabel#TimelineStatusChip {{
    background-color: rgba(255, 255, 255, 14);
    color: #D9D6C8;
    border: 1px solid #383D4D;
    border-radius: 14px;
    padding: 7px 14px;
    font-size: 11px;
    font-weight: 700;
}}

QPushButton#PlayButton {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF7951,
        stop:1 #F05235
    );
    border: 1px solid #FF9875;
    border-radius: 22px;
    color: #FFFFFF;
}}

QPushButton#PlayButton:hover {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #FF8D69,
        stop:1 #FF623E
    );
    border-color: #FFB69C;
}}

QWidget#TimelineToolBar QToolButton#ToolTile,
QWidget#TimelineToolBar QPushButton#ToolTile {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #3945E8,
        stop:0.52 #7358F2,
        stop:1 #22BDE4
    );
    color: rgba(248, 244, 234, 0);
    border: 1px solid rgba(255, 255, 255, 66);
    border-radius: 10px;
    padding: 0px;
    font-size: 10px;
    font-weight: 800;
}}

QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="tracks"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="tracks"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #252D42, stop:0.62 #141926, stop:1 #0B0D15);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="select"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="select"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FF8057, stop:0.55 #F65368, stop:1 #755DF2);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="split"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="split"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #FFD86B, stop:0.52 #FF8B4D, stop:1 #E94F67);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="ripple"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="ripple"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #28D6F1, stop:0.54 #4F6EF2, stop:1 #8059F2);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="roll"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="roll"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6CE0A3, stop:0.54 #2CB5E8, stop:1 #4E5BE7);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slip"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slip"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #E95AB8, stop:0.50 #8860ED, stop:1 #2BC5E9);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slide"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slide"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #24D0BA, stop:0.54 #2D7DE8, stop:1 #6759EA);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="trim"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="trim"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #DC72F0, stop:0.52 #7E64F1, stop:1 #2BC3E8);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="nest"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="nest"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #66E8CE, stop:0.50 #536FE8, stop:1 #252B8C);
}}
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="mixer"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="mixer"] {{
    background-color: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2B3147, stop:0.58 #454871, stop:1 #131724);
}}

QWidget#TimelineToolBar QToolButton#ToolTile:hover,
QWidget#TimelineToolBar QPushButton#ToolTile:hover {{
    color: #F8F4EA;
    border-color: rgba(255, 255, 255, 170);
}}

QWidget#TimelineToolBar QToolButton#ToolTile:checked,
QWidget#TimelineToolBar QPushButton#ToolTile:checked {{
    color: #FFFFFF;
    border-color: #FFF2D6;
}}

QWidget#TimelineToolBar QToolButton#ToolTile::menu-indicator {{
    image: none;
    width: 0px;
}}

QWidget#TimelinePaletteBar {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 rgba(20, 23, 36, 232),
        stop:0.46 rgba(10, 12, 21, 236),
        stop:0.72 rgba(18, 16, 32, 232),
        stop:1 rgba(8, 9, 15, 238)
    );
    border: 1px solid rgba(141, 154, 210, 52);
    border-radius: 16px;
}}

QWidget#TimelinePaletteBar QWidget#TimelineToolBar,
QWidget#TimelinePaletteBar QWidget#TimelineEffectsBar {{
    background: transparent;
    border: none;
    border-radius: 0px;
}}

QWidget#TimelinePaletteBar QWidget#TimelineToolBar {{
    border: none;
    padding: 0px;
}}

QWidget#TimelinePaletteBar QWidget#TimelineEffectsBar {{
    padding: 0px;
}}

QFrame#PaletteDivider {{
    background-color: rgba(255, 255, 255, 30);
    border: none;
    max-width: 1px;
    min-width: 1px;
}}

QWidget#EditorRoot QSlider::groove:horizontal {{
    height: 3px;
    background: #292B35;
    border-radius: 2px;
    border: none;
}}

QWidget#EditorRoot QSlider::sub-page:horizontal {{
    background: #5B45FF;
    border-radius: 2px;
}}

QWidget#EditorRoot QSlider::add-page:horizontal {{
    background: #292B35;
    border-radius: 2px;
    border: none;
}}

QWidget#EditorRoot QSlider::handle:horizontal {{
    background: #6452FF;
    border: 1px solid #9C8EFF;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 7px;
}}

QWidget#EditorRoot QSlider::handle:horizontal:hover {{
    background: #7566FF;
    border-color: #D6D0FF;
}}

QWidget#EditorRoot QSlider::groove:vertical {{
    width: 3px;
    background: #292B35;
    border-radius: 2px;
    border: none;
}}

QWidget#EditorRoot QSlider::add-page:vertical {{
    background: #5B45FF;
    border-radius: 2px;
}}

QWidget#EditorRoot QSlider::sub-page:vertical {{
    background: #292B35;
    border-radius: 2px;
}}

QWidget#EditorRoot QSlider::handle:vertical {{
    background: #6452FF;
    border: 1px solid #9C8EFF;
    width: 14px;
    height: 14px;
    margin: 0 -6px;
    border-radius: 7px;
}}

QWidget#EditorRoot QCheckBox::indicator,
QWidget#EditorRoot QRadioButton::indicator {{
    width: 17px;
    height: 17px;
    border: 1px solid #303548;
    background: #11131C;
}}

QWidget#EditorRoot QCheckBox::indicator:hover,
QWidget#EditorRoot QRadioButton::indicator:hover {{
    border-color: #8A7CFF;
}}

QWidget#EditorRoot QCheckBox::indicator:checked {{
    background: #5B45FF;
    border-color: #8C82FF;
}}

QWidget#EditorRoot QComboBox {{
    background-color: #151823;
    color: #ECEFF8;
    border: 1px solid #2C3347;
    border-radius: 10px;
    padding: 6px 30px 6px 12px;
}}

QWidget#EditorRoot QComboBox:hover {{
    background-color: #1B2030;
    border-color: #566181;
}}

QWidget#EditorRoot QComboBox:focus,
QWidget#EditorRoot QComboBox:on {{
    border-color: #6E5EFF;
}}

QFrame#WorkspaceModeSwitch {{
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #101524, stop: 0.58 #14192A, stop: 1 #171129);
    border: 1px solid #2D395B;
    border-radius: 20px;
}}

QFrame#WorkspaceModeSwitch QPushButton#WorkspaceModeButton {{
    min-width: 54px;
    min-height: 30px;
    padding: 0 12px;
    border-radius: 15px;
    border: 1px solid transparent;
    background-color: transparent;
    color: #BFC8DD;
    font-weight: 900;
}}

QFrame#WorkspaceModeSwitch QPushButton#WorkspaceModeButton:hover {{
    background-color: #20263A;
    color: #FFFFFF;
}}

QFrame#WorkspaceModeSwitch QPushButton#WorkspaceModeButton:checked {{
    color: #FFFFFF;
    border-color: #9F9AFF;
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #35D4E4, stop: 0.48 #7A62FF, stop: 1 #FF725E);
}}

QLabel#CreatorAssistSummary,
QLabel#CreatorAssistDetail {{
    color: #AEB6C4;
    background-color: #101112;
    border: 1px solid #242832;
    border-radius: 7px;
    padding: 7px;
    font-size: 10px;
    font-weight: 600;
}}

QListWidget#CreatorAssistCards {{
    background-color: #101421;
    border: 1px solid #2C3347;
    border-radius: 10px;
    padding: 4px;
}}

QListWidget#CreatorAssistCards::item {{
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 7px;
    margin: 2px;
    color: #DDE2F4;
}}

QListWidget#CreatorAssistCards::item:selected {{
    background-color: rgba(122, 98, 255, 92);
    border-color: #8A7CFF;
    color: #FFFFFF;
}}

/* -----------------------------------------------------------------
 * Catalog neutral button pass.
 * The product-catalog direction keeps chrome quiet: charcoal controls,
 * thin metal borders, and color reserved for media/content indicators.
 * ----------------------------------------------------------------- */
QToolButton#CommandMenuButton,
QPushButton#ToolButton,
QWidget#AppCommandBar QToolButton#CommandMenuButton,
QWidget#AppCommandBar QPushButton#ToolButton,
QWidget#TimelineToolBar QPushButton#ToolButton,
QWidget#SelectionBar QPushButton#ToolButton,
QWidget#TimelineToolBar QToolButton#CommandMenuButton,
QWidget#PlayBar QPushButton#ToolButton {{
    background-color: #14171D;
    color: #D9DDE4;
    border: 1px solid #2B313B;
    border-radius: 12px;
    padding: 0px 12px;
    min-height: 34px;
    font-size: 11px;
    font-weight: 650;
}}

QToolButton#CommandMenuButton:hover,
QPushButton#ToolButton:hover,
QWidget#AppCommandBar QToolButton#CommandMenuButton:hover,
QWidget#AppCommandBar QPushButton#ToolButton:hover,
QWidget#TimelineToolBar QPushButton#ToolButton:hover,
QWidget#SelectionBar QPushButton#ToolButton:hover,
QWidget#TimelineToolBar QToolButton#CommandMenuButton:hover,
QWidget#PlayBar QPushButton#ToolButton:hover {{
    background-color: #1B1F27;
    color: #F4F6FA;
    border-color: #4B5668;
}}

QWidget#AppCommandBar {{
    background-color: #0C0F14;
    border: 1px solid #242A34;
    border-radius: 10px;
}}

QWidget#AppCommandBar[railMode="true"] {{
    background-color: #0E121A;
    border: 1px solid #273044;
    border-radius: 12px;
}}

QLabel#TopBrandLabel {{
    color: #E7E9ED;
    font-size: 11px;
    font-weight: 800;
    padding: 0px 8px 0px 2px;
}}

QLabel#TopBreadcrumbLabel {{
    color: #8C939F;
    font-size: 10px;
    font-weight: 600;
    padding: 0px 10px;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton {{
    background-color: transparent;
    color: #AAB1BD;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 0px;
    min-width: 24px;
    min-height: 24px;
    max-width: 24px;
    max-height: 24px;
}}

QWidget#AppCommandBar[railMode="true"] QToolButton#CommandMenuButton {{
    min-width: 26px;
    min-height: 26px;
    max-width: 26px;
    max-height: 26px;
    border-radius: 8px;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton:hover {{
    background-color: #151A22;
    border-color: #303846;
}}

QPushButton#ToolButton:checked,
QWidget#AppCommandBar QPushButton#ToolButton:checked,
QWidget#TimelineToolBar QPushButton#ToolButton:checked,
QWidget#SelectionBar QPushButton#ToolButton:checked {{
    background-color: #1D2633;
    color: #FFFFFF;
    border-color: #7B8DA8;
}}

QPushButton#PrimaryToolButton,
QWidget#AppCommandBar QPushButton#PrimaryToolButton {{
    background-color: #191D24;
    color: #F7F8FA;
    border: 1px solid #6F7F99;
    border-radius: 13px;
    padding: 0px 18px;
    min-height: 36px;
    font-size: 11px;
    font-weight: 800;
}}

QWidget#AppCommandBar[railMode="true"] QPushButton#PrimaryToolButton {{
    min-width: 28px;
    min-height: 28px;
    max-width: 28px;
    max-height: 28px;
    border-radius: 10px;
    padding: 0px;
}}

QPushButton#PrimaryToolButton:hover,
QWidget#AppCommandBar QPushButton#PrimaryToolButton:hover {{
    background-color: #202633;
    border-color: #A6B3C8;
}}

QToolButton#CommandMenuButton[startupTemplate="true"],
QToolButton#CommandMenuButton[startupTemplate="true"]:hover {{
    background-color: #1A1E26;
    color: #F0F2F5;
    border-color: #536174;
}}

QPushButton#PlayButton {{
    background-color: transparent;
    color: #F7F8FA;
    border: 1px solid transparent;
    border-radius: 6px;
}}

QWidget#ActorLibraryPanel {{
    background-color: #0B0E14;
    border: none;
}}

QWidget#PreviewSectionHeader {{
    background-color: transparent;
    border: none;
    min-height: 24px;
    max-height: 24px;
}}

QLabel#ViewerProjectBreadcrumb {{
    background: transparent;
    color: #C8CBD2;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0px;
    padding: 0px 0px 0px 10px;
    min-height: 20px;
    max-height: 20px;
}}

QLabel#PreviewSectionTitle {{
    color: #E6E8EE;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0px;
    text-transform: none;
    padding-left: 10px;
    min-height: 24px;
    max-height: 24px;
}}

QWidget#PreviewHost {{
    background-color: #101010;
    border: 1px solid #2A2A2A;
    border-radius: 8px;
}}

QPushButton#PlayButton:hover {{
    background-color: #171C24;
    border-color: #384354;
}}

QWidget#PlayBar {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QWidget#PlayBar QPushButton#ToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    min-width: 28px;
    min-height: 28px;
    max-width: 28px;
    max-height: 28px;
    padding: 0px;
}}

QWidget#PlayBar QPushButton#ToolButton:hover {{
    background-color: #171C24;
    border-color: #384354;
}}

QWidget#PlayBar QLabel#TimeLabel,
QWidget#PlayBar QLabel#SpeedLabel,
QWidget#PlayBar QPushButton#SpeedLabel {{
    color: #AAB1BD;
    font-size: 10px;
    font-weight: 600;
}}

QWidget#TimelineToolBar QToolButton#ToolTile,
QWidget#TimelineToolBar QPushButton#ToolTile {{
    background-color: #11151C;
    color: rgba(248, 244, 234, 0);
    border: 1px solid #2A313D;
    border-radius: 6px;
}}

QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="tracks"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="tracks"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="select"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="select"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="split"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="split"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="ripple"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="ripple"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="roll"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="roll"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slip"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slip"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slide"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slide"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="trim"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="trim"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="nest"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="nest"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="mixer"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="mixer"] {{
    background-color: #11151C;
    border-color: #2A313D;
}}

QWidget#TimelineToolBar QToolButton#ToolTile:hover,
QWidget#TimelineToolBar QPushButton#ToolTile:hover {{
    background-color: #171D27;
    border-color: #4D5B70;
    color: #F8F4EA;
}}

QWidget#TimelineToolBar QToolButton#ToolTile:checked,
QWidget#TimelineToolBar QPushButton#ToolTile:checked {{
    background-color: #232B38;
    color: #FFFFFF;
    border-color: #A8B5C9;
}}

QFrame#WorkspaceModeSwitch {{
    background-color: #12161D;
    border: 1px solid #2B3442;
    border-radius: 20px;
}}

QFrame#WorkspaceModeSwitch QPushButton#WorkspaceModeButton:checked {{
    color: #FFFFFF;
    border-color: #8796AD;
    background-color: #222A36;
}}

QWidget#EditorRoot QSlider::sub-page:horizontal,
QWidget#EditorRoot QSlider::add-page:vertical,
QWidget#EditorRoot QCheckBox::indicator:checked {{
    background: #6E86A7;
}}

QWidget#EditorRoot QSlider::handle:horizontal,
QWidget#EditorRoot QSlider::handle:vertical {{
    background: #93A8C3;
    border-color: #D6DEE9;
}}

QWidget#EditorRoot QComboBox:focus,
QWidget#EditorRoot QComboBox:on {{
    border-color: #7B8DA8;
}}

/* -----------------------------------------------------------------
 * UI renewal phase 1.
 * Restore the product-catalog visual direction on the real editor:
 * dark glass shell, icon-first commands, colored tool palettes, and
 * thin cinematic borders. This final pass intentionally wins over the
 * older neutral catalog pass above.
 * ----------------------------------------------------------------- */
QWidget#EditorRoot,
QWidget#CenterWorkbench {{
    background-color: #171A21;
}}

QWidget#LeftDockColumn,
QWidget#RightDockColumn {{
    background-color: #171A21;
    border: none;
}}

QWidget#MediaPoolSectionHost,
QWidget#ActorLibrarySectionHost,
QWidget#EffectsLibrarySectionHost,
QWidget#TitlePresetsSectionHost,
QWidget#TransitionsSectionHost,
QWidget#WorkflowPresetsSectionHost,
QWidget#WorkbenchSectionHost,
QWidget#TimelineSectionHost {{
    background-color: #121212;
    border: 1px solid #242424;
    border-radius: 7px;
}}

QWidget#CollapsibleSectionHeader,
QWidget#TimelineSectionHeader,
QWidget#ColorSectionHeader,
QWidget#PreviewSectionHeader {{
    background-color: #121212;
    border: none;
    border-bottom: 1px solid #242424;
    border-top-left-radius: 7px;
    border-top-right-radius: 7px;
    min-height: 24px;
    max-height: 24px;
}}

QWidget#WorkbenchHeader {{
    background-color: #101112;
    border: none;
    border-bottom: 1px solid #202225;
    min-height: 15px;
    max-height: 15px;
}}

QWidget#WorkbenchHeader QLabel[sectionHeader="true"] {{
    color: #8E949D;
    font-size: 8px;
    font-weight: 540;
    padding-left: 6px;
}}

QWidget#WorkbenchHeader QPushButton#PreviewPopoutIcon {{
    min-width: 15px;
    min-height: 13px;
    max-width: 15px;
    max-height: 13px;
}}

QWidget#WorkbenchHeader QPushButton#WorkbenchPptEntryButton {{
    background-color: #242424;
    color: #C8C8C8;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 0px 4px;
    min-width: 32px;
    min-height: 13px;
    max-width: 32px;
    max-height: 13px;
    font-size: 8px;
    font-weight: 700;
}}

QWidget#WorkbenchHeader QPushButton#WorkbenchPptEntryButton:hover {{
    background-color: #2E2E2E;
    color: #FFFFFF;
    border-color: #D85A30;
}}

QWidget#WorkbenchHeader QPushButton#WorkbenchPptEntryButton:pressed {{
    background-color: #121212;
}}

QWidget#ActorLibrarySectionHost,
QWidget#EffectsLibrarySectionHost,
QWidget#TitlePresetsSectionHost,
QWidget#TransitionsSectionHost,
QWidget#WorkflowPresetsSectionHost {{
    background-color: #151515;
    border-color: #222222;
}}

QWidget#ActorLibraryPanel,
QWidget#PresetBrowser {{
    background: transparent;
    border: none;
}}

QWidget#PreviewHost {{
    background-color: #0F0F10;
    border: 1px solid #242424;
    border-radius: 8px;
}}

QLabel#ViewerProjectBreadcrumb {{
    color: #C8CBD2;
    background: transparent;
    border: none;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 12px;
    font-weight: 500;
    letter-spacing: 0px;
    padding: 0px 0px 0px 8px;
    min-height: 20px;
    max-height: 20px;
}}

QWidget#TopWorkArea {{
    background-color: transparent;
    border: none;
}}

QWidget#ViewerColumn {{
    background-color: transparent;
    border: none;
}}

QWidget#PreviewSectionHeader {{
    background-color: transparent;
    border: none;
    min-height: 24px;
    max-height: 24px;
}}

QLabel#PreviewSectionTitle {{
    color: #E6E8EE;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 14px;
    font-weight: 600;
    letter-spacing: 0px;
    text-transform: none;
    padding: 0px 10px;
    min-height: 24px;
    max-height: 24px;
}}

QLabel[sectionHeader="true"] {{
    color: #DDE1E8;
    background: transparent;
    border: none;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 9px;
    font-weight: 560;
    letter-spacing: 0px;
    padding-left: 8px;
}}

QPushButton#SectionDisclosure {{
    background: transparent;
    border: none;
    border-radius: 5px;
    min-width: 18px;
    min-height: 18px;
    max-width: 18px;
    max-height: 18px;
    padding: 0px;
}}

QPushButton#SectionDisclosure:hover {{
    background-color: rgba(255,255,255,9);
}}

QPushButton#PreviewPopoutIcon {{
    background-color: transparent;
    border: none;
    min-width: 18px;
    min-height: 18px;
    max-width: 18px;
    max-height: 18px;
}}

QLabel#TopBrandLabel {{
    color: #F3F5FA;
    font-size: 11px;
    font-weight: 900;
    padding: 0px 10px 0px 4px;
}}

QLabel#TopBreadcrumbLabel {{
    color: #8892A4;
    font-size: 10px;
    font-weight: 650;
    padding: 0px 12px;
}}

QWidget#AppCommandBar {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton,
QWidget#AppCommandBar QPushButton#ToolButton {{
    background-color: #15181D;
    color: #E8ECF6;
    border: 1px solid #30363D;
    border-radius: 7px;
    padding: 0px;
    min-width: 32px;
    min-height: 32px;
    max-width: 32px;
    max-height: 32px;
    font-size: 0px;
    font-weight: 700;
}}

QWidget#AppCommandBar QToolButton#CommandMenuButton:hover,
QWidget#AppCommandBar QPushButton#ToolButton:hover {{
    background-color: #20252B;
    border-color: #68717E;
}}

QWidget#AppCommandBar QPushButton#ToolButton:checked {{
    background-color: #232B38;
    border-color: #A8B5C9;
}}

QWidget#AppCommandBar QPushButton#PrimaryToolButton {{
    background-color: #15181D;
    color: #F4F6FB;
    border: 1px solid #30363D;
    border-radius: 7px;
    padding: 0px;
    min-width: 42px;
    min-height: 38px;
    max-width: 42px;
    font-size: 0px;
    font-weight: 800;
}}

QWidget#AppCommandBar QPushButton#PrimaryToolButton:hover {{
    border-color: #A8B5C9;
    background-color: #20252B;
}}

QToolButton#CommandMenuButton::menu-indicator,
QWidget#AppCommandBar QToolButton#CommandMenuButton::menu-indicator,
QWidget#TimelineToolBar QToolButton#ToolTile::menu-indicator {{
    image: none;
    width: 0px;
}}

QWidget#PlayBar,
QWidget#TimelinePaletteBar {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #111722,
        stop:0.56 #090D14,
        stop:1 #14111E
    );
    border: 1px solid #2C364A;
    border-radius: 16px;
}}

QWidget#PlayBar QPushButton#ToolButton,
QPushButton#PlayButton {{
    background-color: rgba(255, 255, 255, 12);
    color: #F4F6FB;
    border: 1px solid rgba(150, 166, 205, 42);
    border-radius: 12px;
    min-width: 30px;
    min-height: 30px;
    max-width: 30px;
    max-height: 30px;
    padding: 0px;
    font-size: 0px;
}}

QPushButton#PlayButton {{
    background-color: #161D2A;
    border-color: #4B5871;
}}

QPushButton#PlayButton:hover,
QWidget#PlayBar QPushButton#ToolButton:hover {{
    background-color: #1F2838;
    border-color: #8EA0C4;
}}

QWidget#PlayBar QLabel#TimeLabel,
QWidget#PlayBar QLabel#SpeedLabel,
QWidget#PlayBar QPushButton#SpeedLabel {{
    color: #AEB7C8;
    background-color: transparent;
    border: none;
    font-size: 10px;
    font-weight: 700;
}}

QWidget#PlayBar {{
    background-color: transparent;
    border: none;
    border-radius: 0px;
}}

QWidget#PlayBar QPushButton#ToolButton,
QPushButton#PlayButton {{
    background-color: rgba(255,255,255,8);
    color: #D9DEE9;
    border: 1px solid rgba(180,190,210,30);
    border-radius: 4px;
    min-width: 20px;
    min-height: 20px;
    max-width: 20px;
    max-height: 20px;
    padding: 0px;
    font-size: 0px;
}}

QPushButton#PlayButton:hover,
QWidget#PlayBar QPushButton#ToolButton:hover {{
    background-color: rgba(255,255,255,18);
    border-color: #4A5260;
}}

QPushButton#ViewerDropdownButton,
QWidget#PlayBar QLabel#SpeedLabel,
QWidget#PlayBar QPushButton#SpeedLabel {{
    color: #AEB7C8;
    background-color: qlineargradient(
        x1:0, y1:0, x2:0, y2:1,
        stop:0 #151B26,
        stop:1 #090D14
    );
    border: 1px solid #2C364A;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 650;
    padding: 0px 6px;
    min-height: 20px;
    max-height: 20px;
}}

QPushButton#ViewerDropdownButton:hover {{
    color: #F1F4FA;
    background-color: #111722;
    border-color: #3A465B;
}}

QPushButton#ViewerDropdownButton:checked,
QPushButton#ViewerDropdownButton[active="true"] {{
    color: #FFFFFF;
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        stop:0 #29D3FF,
        stop:0.52 #7B61FF,
        stop:1 #FF6B8D
    );
    border-color: #9AB4FF;
}}

QWidget#TimelinePaletteBar QWidget#TimelineToolBar,
QWidget#TimelinePaletteBar QWidget#TimelineEffectsBar {{
    background-color: transparent;
    border: none;
}}

QWidget#TimelinePaletteBar {{
    background-color: transparent;
    border: none;
}}

QWidget#TimelinePaletteBar[collapsed="true"] {{
    background-color: transparent;
    border: none;
}}

QLabel#TimelinePaletteCollapsedLabel {{
    background-color: transparent;
    color: #BDBDBD;
    border: none;
    font-size: 10px;
    font-weight: 650;
    padding: 0px 6px 0px 1px;
    letter-spacing: 0px;
}}

QToolButton#PaletteCollapseButton {{
    background-color: rgba(36, 36, 36, 132);
    color: #B7B7B7;
    border: 1px solid rgba(180, 180, 180, 54);
    border-radius: 9px;
    min-width: 22px;
    min-height: 22px;
    max-width: 22px;
    max-height: 22px;
    padding: 0px;
}}

QToolButton#PaletteCollapseButton:hover {{
    background-color: rgba(58, 58, 58, 162);
    border-color: rgba(210, 210, 210, 110);
}}

QWidget#TimelineToolBar QToolButton#ToolTile,
QWidget#TimelineToolBar QPushButton#ToolTile {{
    color: rgba(255, 255, 255, 0);
    background-color: #15181D;
    border: 1px solid #30363D;
    border-radius: 7px;
    min-width: 30px;
    min-height: 30px;
    max-width: 30px;
    max-height: 30px;
    padding: 0px;
    font-size: 0px;
}}

QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="tracks"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="select"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="split"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="ripple"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="roll"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slip"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="slide"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="trim"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="nest"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QToolButton#ToolTile[paletteRole="mixer"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="tracks"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="select"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="blade"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="split"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="ripple"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="roll"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slip"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="slide"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="trim"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="nest"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="scopes"],
QWidget#TimelineToolBar QPushButton#ToolTile[paletteRole="mixer"] {{
    background-color: #15181D;
}}

QWidget#TimelineToolBar QToolButton#ToolTile:hover,
QWidget#TimelineToolBar QPushButton#ToolTile:hover,
QWidget#TimelineToolBar QToolButton#ToolTile:checked,
QWidget#TimelineToolBar QPushButton#ToolTile:checked {{
    color: #FFFFFF;
    background-color: #20252B;
    border-color: #A8B5C9;
}}

QLineEdit#MediaPoolSearch,
QListWidget,
QComboBox {{
    background-color: #0A0E16;
    color: #E4E8F2;
    border: 1px solid #273145;
    border-radius: 11px;
}}

QLineEdit#MediaPoolSearch:focus,
QComboBox:focus,
QComboBox:on {{
    border-color: #7C8FB5;
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {{
    background: rgba(174, 188, 220, 78);
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {{
    background: rgba(214, 224, 246, 118);
}}
"""


MEDIA_POOL_REFERENCE_QSS = """
QWidget#MediaPoolSectionHost {
    background-color: #151515;
    border: none;
    border-radius: 0px;
}

QWidget#MediaPoolCollapsibleSectionHeader {
    background: transparent;
    border: none;
    border-radius: 0px;
    min-height: 24px;
    max-height: 24px;
}

QWidget#MediaPoolCollapsibleSectionHeader QLabel[sectionHeader="true"] {
    color: #DDE1E8;
    font-family: "Segoe UI Variable", "Noto Sans KR", "Segoe UI", "Malgun Gothic";
    font-size: 9px;
    font-weight: 560;
    letter-spacing: 0px;
    padding-left: 8px;
}

QWidget#MediaPoolCollapsibleSectionHeader QPushButton#SectionDisclosure {
    background: transparent;
    border: none;
    border-radius: 5px;
    padding: 0px;
    min-width: 18px;
    max-width: 18px;
    min-height: 18px;
    max-height: 18px;
}

QWidget#MediaPoolCollapsibleSectionHeader QPushButton#SectionDisclosure:hover {
    background: rgba(255,255,255,9);
    border: none;
}
"""
