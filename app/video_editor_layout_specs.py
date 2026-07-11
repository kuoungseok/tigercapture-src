from __future__ import annotations

from app.style import editor_scrollbar_qss


TOP_WORK_MIN_HEIGHT = 390
TOP_WORK_MAX_HEIGHT = 580
MAIN_DOCK_MIN_HEIGHT = 410
MAIN_DOCK_MAX_HEIGHT = 600
EDITOR_RESIZABLE_PANE_MAX_HEIGHT = 16777215
PREVIEW_HOST_MIN_HEIGHT = 270
MAIN_DOCK_SPLITTER_SETTINGS_KEY = "video_editor/main_dock_splitter_state"
COLOR_TIMELINE_SPLITTER_SETTINGS_KEY = "video_editor/color_timeline_splitter_state"
LEFT_DOCK_MIN_WIDTH = 180
WORKBENCH_SLOT_MIN_WIDTH = 390
VIEWER_COLUMN_MIN_WIDTH = 320
VIEWER_TOP_STRETCH = 6
WORKBENCH_TOP_STRETCH = 5
LEFT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH = 5
LEFT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY = "video_editor/left_dock_sections_splitter_state"
RIGHT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH = 5
RIGHT_DOCK_SECTIONS_SPLITTER_SETTINGS_KEY = "video_editor/right_dock_sections_splitter_state"
TOP_WORKBENCH_SPLITTER_HANDLE_WIDTH = 5
TOP_WORKBENCH_SPLITTER_SETTINGS_KEY = "video_editor/top_workbench_splitter_state"
EDITOR_VERTICAL_SPLITTER_HANDLE_WIDTH = 6
EDITOR_VERTICAL_SPLITTER_SETTINGS_KEY = "video_editor/main_vertical_splitter_state"


def main_dock_splitter_qss() -> str:
    return (
        "QSplitter#MainDockSplitter::handle{background:rgba(214,220,235,8);}"
        "QSplitter#MainDockSplitter::handle:horizontal{width:1px;margin:0;}"
        "QSplitter#MainDockSplitter::handle:hover{background:rgba(214,220,235,38);}"
    )


def left_dock_sections_splitter_qss() -> str:
    return (
        "QSplitter#LeftDockSectionsSplitter::handle{"
        "background:rgba(214,220,235,12);"
        "}"
        "QSplitter#LeftDockSectionsSplitter::handle:vertical{"
        f"height:{LEFT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH}px;margin:0;"
        "}"
        "QSplitter#LeftDockSectionsSplitter::handle:hover,"
        "QSplitter#LeftDockSectionsSplitter::handle:pressed{"
        "background:rgba(214,220,235,52);"
        "}"
    )


def right_dock_sections_splitter_qss() -> str:
    return (
        "QSplitter#RightDockSectionsSplitter::handle{"
        "background:rgba(214,220,235,12);"
        "}"
        "QSplitter#RightDockSectionsSplitter::handle:vertical{"
        f"height:{RIGHT_DOCK_SECTIONS_SPLITTER_HANDLE_WIDTH}px;margin:0;"
        "}"
        "QSplitter#RightDockSectionsSplitter::handle:hover,"
        "QSplitter#RightDockSectionsSplitter::handle:pressed{"
        "background:rgba(214,220,235,52);"
        "}"
    )


def top_workbench_splitter_qss() -> str:
    return (
        "QSplitter#TopWorkbenchSplitter::handle{"
        "background:rgba(214,220,235,14);"
        "}"
        "QSplitter#TopWorkbenchSplitter::handle:horizontal{"
        f"width:{TOP_WORKBENCH_SPLITTER_HANDLE_WIDTH}px;margin:0;"
        "}"
        "QSplitter#TopWorkbenchSplitter::handle:hover,"
        "QSplitter#TopWorkbenchSplitter::handle:pressed{"
        "background:rgba(214,220,235,54);"
        "}"
    )


def editor_vertical_splitter_qss() -> str:
    return (
        "QSplitter#EditorVerticalSplitter::handle{"
        "background:rgba(214,220,235,14);"
        "}"
        "QSplitter#EditorVerticalSplitter::handle:vertical{"
        f"height:{EDITOR_VERTICAL_SPLITTER_HANDLE_WIDTH}px;margin:0;"
        "}"
        "QSplitter#EditorVerticalSplitter::handle:hover,"
        "QSplitter#EditorVerticalSplitter::handle:pressed{"
        "background:rgba(214,220,235,58);"
        "}"
    )


def thin_scroll_area_qss(scope: str, *, child_background: str = "transparent") -> str:
    return (
        f"{scope}{{background:transparent;border:none;}}"
        f"{scope} > QWidget > QWidget{{background:{child_background};}}"
        + editor_scrollbar_qss(scope)
    )


def left_dock_scroll_qss() -> str:
    return (
        thin_scroll_area_qss("QScrollArea#LeftDockScroll", child_background="#141414")
        + "QScrollArea#LeftDockScroll QScrollBar:vertical{"
        "width:2px;margin:8px 0 8px 0;background:transparent;border:none;"
        "}"
        "QScrollArea#LeftDockScroll QScrollBar:vertical:hover{"
        "width:7px;margin:8px 0 8px 0;"
        "}"
        "QScrollArea#LeftDockScroll QScrollBar::handle:vertical{"
        "background:rgba(214,220,235,22);border-radius:1px;min-height:34px;"
        "}"
        "QScrollArea#LeftDockScroll QScrollBar::handle:vertical:hover{"
        "background:rgba(214,220,235,96);border-radius:4px;"
        "}"
        "QScrollArea#LeftDockScroll QScrollBar::add-line:vertical,"
        "QScrollArea#LeftDockScroll QScrollBar::sub-line:vertical{height:0;background:transparent;}"
    )


def right_dock_scroll_qss() -> str:
    return (
        thin_scroll_area_qss("QScrollArea#RightDockScroll")
        + "QScrollArea#RightDockScroll QScrollBar:vertical{"
        "background:transparent;width:4px;margin:6px 0 6px 1px;"
        "}"
        "QScrollArea#RightDockScroll QScrollBar:vertical:hover{width:8px;margin:6px 0;}"
        "QScrollArea#RightDockScroll QScrollBar::handle:vertical{"
        "background:rgba(214,220,235,34);border-radius:2px;min-height:30px;"
        "}"
        "QScrollArea#RightDockScroll QScrollBar::handle:vertical:hover{"
        "background:rgba(214,220,235,112);border-radius:4px;"
        "}"
        "QScrollArea#RightDockScroll QScrollBar::add-line:vertical,"
        "QScrollArea#RightDockScroll QScrollBar::sub-line:vertical{height:0;}"
    )


def horizontal_tool_scroll_qss(scope: str) -> str:
    return (
        f"{scope}{{background:transparent;border:none;}}"
        f"{scope} > QWidget > QWidget{{background:transparent;}}"
        "QScrollBar:horizontal{background:transparent;height:7px;margin:0 14px 0 14px;}"
        "QScrollBar::handle:horizontal{background:rgba(255,255,255,42);border-radius:3px;min-width:42px;}"
        "QScrollBar::handle:horizontal:hover{background:rgba(255,255,255,82);}"
        "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}"
        + editor_scrollbar_qss(scope)
    )
