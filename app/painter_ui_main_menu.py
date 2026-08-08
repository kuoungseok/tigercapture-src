"""Figma-class cascading main menu for Painter UI Design."""
from __future__ import annotations

from collections.abc import Callable, Mapping

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

from app.icons import app_icon
from app.painter_i18n import painter_text


_MENU_QSS = """
QMenu {
    background-color: #1d1d1f;
    color: #f4f4f5;
    border: 1px solid #343438;
    border-radius: 10px;
    padding: 8px;
    font-size: 12px;
}
QMenu::item {
    min-width: 238px;
    min-height: 27px;
    padding: 3px 28px 3px 10px;
    border-radius: 5px;
}
QMenu::item:selected {
    background-color: #3a3a3d;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #74747a;
}
QMenu::separator {
    height: 1px;
    background-color: #36363a;
    margin: 7px 0;
}
QMenu::right-arrow {
    width: 7px;
    height: 10px;
}
"""


def _action(
    menu: QMenu,
    label: str,
    callback: Callable[[], None] | None,
    shortcut: str = "",
    *,
    icon_name: str = "",
    enabled: bool | None = None,
    checked: bool | None = None,
) -> QAction:
    action = QAction(painter_text(label), menu)
    if icon_name:
        action.setIcon(app_icon(icon_name, size=14, color="#D9D9DE"))
    if shortcut:
        action.setShortcut(QKeySequence(shortcut))
        action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        action.setShortcutVisibleInContextMenu(True)
    action.setEnabled(callable(callback) and enabled is not False)
    if checked is not None:
        action.setCheckable(True)
        action.setChecked(bool(checked))
    if callable(callback):
        action.triggered.connect(callback)
    menu.addAction(action)
    return action


def _submenu(parent: QMenu, label: str) -> QMenu:
    menu = QMenu(painter_text(label), parent)
    parent.addMenu(menu)
    menu.setObjectName("PainterUICascadeMenu")
    menu.setStyleSheet(_MENU_QSS)
    return menu


def _copy_actions(source: QMenu | None, target: QMenu) -> None:
    if source is None:
        return
    for source_action in source.actions():
        if source_action.isSeparator():
            target.addSeparator()
        else:
            target.addAction(source_action)


def build_painter_ui_main_menu(
    parent: QWidget,
    *,
    callbacks: Mapping[str, Callable[[], None]],
    source_menus: Mapping[str, QMenu | None],
    state: Mapping[str, bool] | None = None,
) -> QMenu:
    """Build the global logo menu while reusing canonical Painter actions."""
    menu_state = dict(state or {})
    has_selection = bool(menu_state.get("has_selection", True))
    multi_selection = bool(menu_state.get("multi_selection", True))
    three_selection = bool(menu_state.get("three_selection", True))
    text_selection = bool(menu_state.get("text_selection", True))
    menu = QMenu(parent)
    menu.setObjectName("PainterUINavigationMainMenu")
    menu.setStyleSheet(_MENU_QSS)

    _action(
        menu,
        "Actions...",
        callbacks.get("quick_actions"),
        "Ctrl+K",
        icon_name="search",
    )
    menu.addSeparator()

    file_menu = _submenu(menu, "File")
    _action(file_menu, "New Design...", callbacks.get("new_design"), "Ctrl+N")
    new_menu = _submenu(file_menu, "New")
    _action(new_menu, "Blank UI Design...", callbacks.get("new_design"))
    _action(new_menu, "From Template...", callbacks.get("templates"))
    _action(new_menu, "Paint Canvas...", callbacks.get("new_paint_canvas"))
    file_menu.addSeparator()
    _action(
        file_menu,
        "Place Image...",
        callbacks.get("place_image"),
        "Ctrl+Shift+K",
    )
    _action(file_menu, "Open...", callbacks.get("open"), "Ctrl+O")
    file_menu.addSeparator()
    _action(file_menu, "Save", callbacks.get("save"), "Ctrl+S")
    _action(file_menu, "Save Local Copy...", callbacks.get("save_as"), "Ctrl+Alt+S")
    _action(file_menu, "Save to version history...", callbacks.get("version_save"))
    _action(file_menu, "View version history", callbacks.get("version_history"))
    file_menu.addSeparator()
    _action(file_menu, "Export...", callbacks.get("export_png"), "Ctrl+Shift+E")
    _action(file_menu, "Export frames to PDF...", callbacks.get("export_pdf"))
    file_menu.addSeparator()
    _action(file_menu, "Create branch...", callbacks.get("create_branch"))

    edit_menu = _submenu(menu, "Edit")
    _action(edit_menu, "Undo", callbacks.get("undo"), "Ctrl+Z", enabled=menu_state.get("can_undo", True))
    _action(edit_menu, "Redo", callbacks.get("redo"), "Ctrl+Y", enabled=menu_state.get("can_redo", True))
    edit_menu.addSeparator()
    copy_format = _submenu(edit_menu, "Copy format")
    _action(copy_format, "Copy properties", callbacks.get("copy_properties"), "Ctrl+Alt+C", enabled=has_selection)
    _action(copy_format, "Paste properties", callbacks.get("paste_properties"), "Ctrl+Alt+V", enabled=bool(menu_state.get("has_clipboard", True)) and has_selection)
    _action(edit_menu, "Paste over selection", callbacks.get("paste_in_place"), "Ctrl+Shift+V", enabled=bool(menu_state.get("has_clipboard", True)))
    _action(edit_menu, "Paste to replace", callbacks.get("paste_replace"), "Ctrl+Shift+R", enabled=bool(menu_state.get("has_clipboard", True)) and has_selection)
    _action(edit_menu, "Duplicate", callbacks.get("duplicate"), "Ctrl+D", enabled=has_selection)
    _action(edit_menu, "Delete", callbacks.get("delete"), "Del", enabled=has_selection)
    edit_menu.addSeparator()
    _action(edit_menu, "Find", callbacks.get("find"), "Ctrl+F")
    _action(edit_menu, "Find next", callbacks.get("find_next"), "Ctrl+Shift+F")
    _action(edit_menu, "Find previous", callbacks.get("find_previous"), "Ctrl+Shift+D")
    _action(edit_menu, "Find and replace...", callbacks.get("find_replace"))
    edit_menu.addSeparator()
    _action(edit_menu, "Select all", callbacks.get("select_all"), "Ctrl+A")
    _action(edit_menu, "Select matching layers", callbacks.get("select_same_kind"), "Ctrl+Alt+A", enabled=has_selection)
    _action(edit_menu, "Select none", callbacks.get("select_none"), "Esc", enabled=has_selection)
    _action(edit_menu, "Invert selection", callbacks.get("select_inverse"), "Ctrl+Shift+A")

    view_menu = _submenu(menu, "View")
    _action(view_menu, "Pixel grid", callbacks.get("toggle_pixel_grid"), "Shift+'", checked=menu_state.get("pixel_grid", False))
    _action(view_menu, "Layout guides", callbacks.get("toggle_layout_guides"), "Shift+G", checked=menu_state.get("layout_guides", True))
    _action(view_menu, "Rulers", callbacks.get("toggle_guides"), "Shift+R", checked=menu_state.get("guides_visible", True))
    _action(view_menu, "Pixel preview", callbacks.get("toggle_pixel_preview"), "Ctrl+Shift+P", checked=menu_state.get("pixel_preview", False))
    outlines_menu = _submenu(view_menu, "Outlines")
    _action(outlines_menu, "Show outlines", callbacks.get("toggle_layer_outlines"), "Ctrl+Shift+O", checked=menu_state.get("layer_outlines", False))
    _action(outlines_menu, "Include hidden layers", callbacks.get("toggle_outline_hidden"), checked=menu_state.get("outline_include_hidden", False))
    _action(outlines_menu, "Include object bounds", callbacks.get("toggle_outline_bounds"), checked=menu_state.get("outline_include_bounds", False))
    _action(
        view_menu,
        "UMG Widget View",
        callbacks.get("toggle_umg_widget_view"),
        checked=menu_state.get("umg_widget_view", False),
    )
    view_menu.addSeparator()
    _action(view_menu, "Show navigator", callbacks.get("toggle_navigator"), "Ctrl+\\", checked=menu_state.get("navigator_visible", True))
    _action(view_menu, "Show inspector", callbacks.get("toggle_inspector"), "Ctrl+Alt+\\", checked=menu_state.get("inspector_visible", True))
    view_menu.addSeparator()
    _action(view_menu, "Zoom in", callbacks.get("zoom_in"), "Ctrl++")
    _action(view_menu, "Zoom out", callbacks.get("zoom_out"), "Ctrl+-")
    _action(view_menu, "Zoom to 100%", callbacks.get("zoom_100"), "Ctrl+0")
    _action(view_menu, "Fit to screen", callbacks.get("fit_all"), "Shift+1")
    _action(view_menu, "Zoom to selection", callbacks.get("fit_selection"), "Shift+2", enabled=has_selection)

    object_menu = _submenu(menu, "Object")
    _action(object_menu, "Select parent", callbacks.get("select_parent"), "Ctrl+Alt+G", enabled=has_selection)
    _action(object_menu, "Group selection", callbacks.get("group"), "Ctrl+G", enabled=multi_selection)
    _action(object_menu, "Ungroup selection", callbacks.get("ungroup"), "Ctrl+Shift+G", enabled=bool(menu_state.get("group_selection", False)))
    object_menu.addSeparator()
    _action(object_menu, "Wrap in new section", callbacks.get("wrap_section"), "Ctrl+S", enabled=has_selection)
    _action(object_menu, "Create component", callbacks.get("component"), "Ctrl+Alt+K", enabled=has_selection)
    _action(object_menu, "Reset instance", callbacks.get("reset_instance"), enabled=bool(menu_state.get("instance_selection", False)))
    _action(object_menu, "Detach instance", callbacks.get("detach_instance"), "Ctrl+Alt+B", enabled=bool(menu_state.get("instance_selection", False)))
    object_menu.addSeparator()
    _action(object_menu, "Bring to front", callbacks.get("front"), "]", enabled=has_selection)
    _action(object_menu, "Bring forward", callbacks.get("forward"), "Ctrl+]", enabled=has_selection)
    _action(object_menu, "Send backward", callbacks.get("backward"), "Ctrl+[", enabled=has_selection)
    _action(object_menu, "Send to back", callbacks.get("back"), "[", enabled=has_selection)
    object_menu.addSeparator()
    _action(object_menu, "Flip horizontal", callbacks.get("flip_h"), "Shift+H", enabled=has_selection)
    _action(object_menu, "Flip vertical", callbacks.get("flip_v"), "Shift+V", enabled=has_selection)

    text_menu = _submenu(menu, "Text")
    _action(text_menu, "Bold", callbacks.get("bold"), "Ctrl+B", enabled=text_selection)
    _action(text_menu, "Italic", callbacks.get("italic"), "Ctrl+I", enabled=text_selection)
    _action(text_menu, "Underline", callbacks.get("underline"), "Ctrl+U", enabled=text_selection)
    _action(text_menu, "Strikethrough", callbacks.get("strike"), "Ctrl+Shift+X", enabled=text_selection)
    text_menu.addSeparator()
    text_align = _submenu(text_menu, "Alignment")
    _action(text_align, "Left", callbacks.get("text_left"), enabled=text_selection)
    _action(text_align, "Center", callbacks.get("text_center"), enabled=text_selection)
    _action(text_align, "Right", callbacks.get("text_right"), enabled=text_selection)
    text_case = _submenu(text_menu, "Letter case")
    _action(text_case, "Uppercase", callbacks.get("uppercase"), enabled=text_selection)
    _action(text_case, "Lowercase", callbacks.get("lowercase"), enabled=text_selection)
    _action(text_menu, "Text Tool", callbacks.get("text_tool"), "T")

    arrange_menu = _submenu(menu, "Arrange")
    _action(arrange_menu, "Tidy up", callbacks.get("tidy"), enabled=multi_selection)
    arrange_menu.addSeparator()
    _action(arrange_menu, "Align left", callbacks.get("align_left"), "Alt+A", enabled=has_selection)
    _action(arrange_menu, "Align horizontal centers", callbacks.get("align_hcenter"), "Alt+H", enabled=has_selection)
    _action(arrange_menu, "Align right", callbacks.get("align_right"), "Alt+D", enabled=has_selection)
    _action(arrange_menu, "Align top", callbacks.get("align_top"), "Alt+W", enabled=has_selection)
    _action(arrange_menu, "Align vertical centers", callbacks.get("align_vcenter"), "Alt+V", enabled=has_selection)
    _action(arrange_menu, "Align bottom", callbacks.get("align_bottom"), "Alt+S", enabled=has_selection)
    arrange_menu.addSeparator()
    _action(arrange_menu, "Distribute horizontal spacing", callbacks.get("distribute_h"), "Alt+Shift+H", enabled=three_selection)
    _action(arrange_menu, "Distribute vertical spacing", callbacks.get("distribute_v"), "Alt+Shift+V", enabled=three_selection)

    vector_menu = _submenu(menu, "Vector")
    boolean_menu = _submenu(vector_menu, "Boolean operation")
    _action(boolean_menu, "Union selection", callbacks.get("boolean_union"), "Alt+Shift+U", enabled=multi_selection)
    _action(boolean_menu, "Subtract selection", callbacks.get("boolean_subtract"), "Alt+Shift+S", enabled=multi_selection)
    _action(boolean_menu, "Intersect selection", callbacks.get("boolean_intersect"), "Alt+Shift+I", enabled=multi_selection)
    _action(boolean_menu, "Exclude selection", callbacks.get("boolean_exclude"), "Alt+Shift+E", enabled=multi_selection)
    _action(vector_menu, "Flatten", callbacks.get("boolean_flatten"), "Alt+Shift+F", enabled=bool(menu_state.get("boolean_group_selection", False)))
    _action(vector_menu, "Convert to vector", callbacks.get("convert_vector"), enabled=has_selection)

    menu.addSeparator()
    plugins_menu = _submenu(menu, "Plugins")
    _action(
        plugins_menu,
        "Manage local Figma plugins...",
        callbacks.get("figma_plugin_manager"),
    )

    preferences_menu = _submenu(menu, "Preferences")
    _action(preferences_menu, "Snap to geometry", callbacks.get("toggle_snap"), checked=menu_state.get("snap_enabled", True))
    preferences_menu.addSeparator()
    _action(preferences_menu, "Highlight layers on hover", callbacks.get("pref_highlight_layers"), checked=menu_state.get("pref_highlight_layers", True))
    _action(preferences_menu, "Rename duplicated layers", callbacks.get("pref_rename_duplicates"), checked=menu_state.get("pref_rename_duplicates", True))
    _action(preferences_menu, "Show object dimensions", callbacks.get("pref_show_dimensions"), checked=menu_state.get("pref_show_dimensions", True))
    _action(preferences_menu, "Use smart quotes", callbacks.get("pref_smart_quotes"), checked=menu_state.get("pref_smart_quotes", True))
    preferences_menu.addSeparator()
    _action(preferences_menu, "Use scroll wheel to zoom", callbacks.get("pref_scroll_zoom"), checked=menu_state.get("pref_scroll_zoom", False))
    _action(preferences_menu, "Right-click and drag to pan", callbacks.get("pref_right_drag_pan"), checked=menu_state.get("pref_right_drag_pan", False))
    preferences_menu.addSeparator()
    _action(
        preferences_menu,
        "Keyboard Shortcuts...",
        callbacks.get("shortcuts"),
    )
    _action(
        preferences_menu,
        "Locale and Font Audit...",
        callbacks.get("locale_audit"),
    )
    libraries_menu = _submenu(menu, "Libraries")
    _action(libraries_menu, "Open Libraries", callbacks.get("libraries"))

    menu.addSeparator()
    help_menu = _submenu(menu, "Help and account")
    _action(help_menu, "Keyboard Shortcuts...", callbacks.get("shortcuts"))
    _action(help_menu, "UI / Action Parity...", callbacks.get("action_parity"))

    menu._painter_file_menu = file_menu
    menu._painter_new_menu = new_menu
    menu._painter_outlines_menu = outlines_menu
    menu._painter_plugins_menu = plugins_menu
    return menu


__all__ = ["build_painter_ui_main_menu"]
