"""Figma-style Pages and Layers navigator for Painter UI Design."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text
from app.painter_ui_panel_state import PERSISTED_PANEL_MAX_WIDTH


class _NavigatorResizeHandle(QFrame):
    width_requested = Signal(int)

    def __init__(self, panel: "PainterUINavigatorPanel") -> None:
        super().__init__(panel)
        self._panel = panel
        self._press_global_x = 0.0
        self._press_width = 0
        self.setObjectName("PainterUINavigatorResizeHandle")
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setFixedWidth(5)

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._press_global_x = float(event.globalPosition().x())
        self._press_width = self._panel.width()
        self.setProperty("dragging", True)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            event.ignore()
            return
        delta = float(event.globalPosition().x()) - self._press_global_x
        self.width_requested.emit(round(self._press_width + delta))
        event.accept()

    def mouseReleaseEvent(self, event) -> None:
        self.setProperty("dragging", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()


class PainterUINavigatorPanel(QFrame):
    """Left-side document navigator that reuses the canonical Layers page."""

    page_selected = Signal(str)
    page_add_requested = Signal()
    page_remove_requested = Signal(str)
    page_rename_requested = Signal(str, str)
    collapsed_changed = Signal(bool)
    width_changed = Signal(int)
    auto_hide_changed = Signal(bool)
    dock_toggle_requested = Signal()
    pin_requested = Signal()
    temporary_close_requested = Signal()
    main_menu_requested = Signal()
    focus_mode_changed = Signal(bool)

    RAIL_WIDTH = 52
    MIN_EXPANDED_WIDTH = 190
    DEFAULT_EXPANDED_WIDTH = 248

    def __init__(
        self,
        layers_page: QWidget,
        layer_list: QListWidget,
        asset_pages: Mapping[str, QWidget] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUINavigator")
        self._expanded_width = self.DEFAULT_EXPANDED_WIDTH
        self._splitter_managed = False
        self.setMinimumWidth(self._expanded_width)
        self.setMaximumWidth(self._expanded_width)
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Expanding,
        )
        self._syncing = False
        self._collapsed = False
        self._auto_hide = False
        self._temporary_expanded = False
        self._collapse_user_override = False
        self._layer_list = layer_list

        root = QVBoxLayout(self)
        root.setContentsMargins(self.RAIL_WIDTH, 0, 0, 0)
        root.setSpacing(0)

        self.navigation_rail = QFrame(self)
        self.navigation_rail.setObjectName("PainterUINavigationRail")
        rail_layout = QVBoxLayout(self.navigation_rail)
        rail_layout.setContentsMargins(3, 6, 3, 6)
        rail_layout.setSpacing(2)
        self.logo_button = QToolButton(self.navigation_rail)
        self.logo_button.setObjectName("PainterUINavigationLogo")
        self.logo_button.setIcon(
            app_icon("tiger-painter-logo", size=22, color="#E7EEF7")
        )
        self.logo_button.setIconSize(icon_size(22))
        self.logo_button.setFixedSize(46, 40)
        self.logo_button.setToolTip(painter_text("Main menu"))
        self.logo_button.setAccessibleName(painter_text("Main menu"))
        self.logo_button.clicked.connect(self.main_menu_requested)
        rail_layout.addWidget(self.logo_button)
        rail_separator = QFrame(self.navigation_rail)
        rail_separator.setObjectName("PainterUINavigationRailSeparator")
        rail_separator.setFixedHeight(1)
        rail_layout.addWidget(rail_separator)
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.navigation_buttons: dict[str, QToolButton] = {}
        for section, label, icon_name in (
            ("file", "File", "ui-frame"),
            ("assets", "Assets", "grid"),
            ("tools", "Tools", "settings"),
            ("variables", "Variables", "keyframe"),
        ):
            button = QToolButton(self.navigation_rail)
            button.setObjectName("PainterUINavigationButton")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextUnderIcon
            )
            button.setText(painter_text(label))
            button.setToolTip(painter_text(label))
            button.setAccessibleName(painter_text(label))
            button.setIcon(app_icon(icon_name, size=16, color="#C8D1DC"))
            button.setIconSize(icon_size(16))
            button.setFixedSize(46, 52)
            button.clicked.connect(
                lambda _checked=False, value=section: self.select_section(
                    value,
                    user_initiated=True,
                )
            )
            self.navigation_group.addButton(button)
            self.navigation_buttons[section] = button
            rail_layout.addWidget(button)
        rail_layout.addStretch(1)

        header = QFrame()
        header.setObjectName("PainterUINavigatorHeader")
        header.setFixedHeight(26)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 2, 4, 2)
        title = QLabel(painter_text("Untitled"))
        title.setObjectName("PainterUINavigatorTitle")
        self.title_label = title
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        self.focus_mode_button = QPushButton("")
        self.focus_mode_button.setObjectName("PainterUIPanelCollapse")
        self.focus_mode_button.setCheckable(True)
        self.focus_mode_button.setFixedSize(24, 22)
        self.focus_mode_button.setIcon(
            app_icon("figma-full-mode", size=14, color="#B8C4D3")
        )
        self.focus_mode_button.setIconSize(icon_size(14))
        self.focus_mode_button.setToolTip(painter_text("Focus canvas"))
        self.focus_mode_button.setAccessibleName(
            painter_text("Focus canvas")
        )
        self.focus_mode_button.toggled.connect(self.focus_mode_changed)
        header_layout.addWidget(self.focus_mode_button)
        self.collapse_button = QPushButton("")
        self.collapse_button.setObjectName("PainterUIPanelCollapse")
        self.collapse_button.setFixedSize(20, 20)
        self.collapse_button.setToolTip("Collapse navigator")
        self.collapse_button.clicked.connect(self._on_collapse_clicked)
        header_layout.addWidget(self.collapse_button)
        self.pin_button = QPushButton("")
        self.pin_button.setObjectName("PainterUIPanelCollapse")
        self.pin_button.setFixedSize(20, 20)
        self.pin_button.setIcon(app_icon("pin", size=12, color="#B8C4D3"))
        self.pin_button.setIconSize(icon_size(12))
        self.pin_button.setToolTip(painter_text("Pin navigator"))
        self.pin_button.clicked.connect(self.pin_requested)
        self.pin_button.hide()
        header_layout.addWidget(self.pin_button)
        self.dock_button = QPushButton("")
        self.dock_button.setObjectName("PainterUIPanelCollapse")
        self.dock_button.setFixedSize(20, 20)
        self.dock_button.setIcon(
            app_icon("popout", size=12, color="#B8C4D3")
        )
        self.dock_button.setIconSize(icon_size(12))
        self.dock_button.setToolTip(painter_text("Detach navigator"))
        self.dock_button.clicked.connect(self.dock_toggle_requested)
        header_layout.addWidget(self.dock_button)
        root.addWidget(header)

        self.content_scroll = QScrollArea()
        self.content_scroll.setObjectName("PainterUINavigatorScroll")
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.content_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.content_widget = QWidget()
        self.content_widget.setObjectName("PainterUINavigatorContent")
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("PainterUINavigatorSearch")
        self.search_edit.setFixedHeight(22)
        self.search_edit.setPlaceholderText("Search pages and layers")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(
            app_icon("search", size=12, color="#96A2B1"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_edit.textChanged.connect(self._apply_filter)
        # Search is a panel-level command. Keeping it above the document
        # header avoids visually placing it between the title and page list.
        root.insertWidget(0, self.search_edit)

        pages_header = QLabel(painter_text("PAGES"))
        pages_header.setObjectName("PainterUINavigatorSection")
        self.pages_header = pages_header
        content_layout.addWidget(pages_header)
        self.page_list = QListWidget()
        self.page_list.setObjectName("PainterUIPageList")
        self.page_list.setAccessibleName(painter_text("PAGES"))
        self.page_list.setIconSize(icon_size(13))
        self.page_list.setMaximumHeight(66)
        self.page_list.itemSelectionChanged.connect(
            self._emit_page_selection
        )
        self.page_list.itemChanged.connect(self._emit_page_rename)
        content_layout.addWidget(self.page_list)
        page_actions = QFrame()
        page_actions.setObjectName("PainterUIPageActions")
        page_actions_layout = QHBoxLayout(page_actions)
        page_actions_layout.setContentsMargins(3, 1, 3, 3)
        page_actions_layout.setSpacing(2)
        page_actions_layout.addStretch(1)
        self.page_add_button = QPushButton("")
        self.page_add_button.setObjectName("PainterUIPageAction")
        self.page_add_button.setFixedSize(22, 20)
        self.page_add_button.setIcon(
            app_icon("plus", size=12, color="#B8C4D3")
        )
        self.page_add_button.setToolTip(painter_text("New Page"))
        self.page_add_button.clicked.connect(self.page_add_requested)
        page_actions_layout.addWidget(self.page_add_button)
        self.page_remove_button = QPushButton("")
        self.page_remove_button.setObjectName("PainterUIPageAction")
        self.page_remove_button.setFixedSize(22, 20)
        self.page_remove_button.setIcon(
            app_icon("trash", size=12, color="#B8C4D3")
        )
        self.page_remove_button.setToolTip(painter_text("Delete Page"))
        self.page_remove_button.clicked.connect(
            self._request_current_page_removal
        )
        page_actions_layout.addWidget(self.page_remove_button)
        content_layout.addWidget(page_actions)
        self.page_actions = page_actions

        self.mode_tabs = QTabWidget()
        self.mode_tabs.setObjectName("PainterUINavigatorTabs")
        self.mode_tabs.setDocumentMode(True)
        self.mode_tabs.tabBar().setExpanding(True)
        self.mode_tabs.tabBar().setUsesScrollButtons(False)

        layers_host = QWidget()
        layers_host.setObjectName("PainterUINavigatorLayersHost")
        layers_host_layout = QVBoxLayout(layers_host)
        layers_host_layout.setContentsMargins(0, 0, 0, 0)
        layers_host_layout.setSpacing(0)
        self.layers_header = QLabel(painter_text("Layers"))
        self.layers_header.setObjectName("PainterUINavigatorSection")
        self.layers_header.setAccessibleName(painter_text("Layers"))
        layers_host_layout.addWidget(self.layers_header)
        layers_page.setObjectName("PainterUILayersPage")
        layers_host_layout.addWidget(layers_page, 1)
        layers_page.show()
        self.file_host = layers_host
        self.mode_tabs.addTab(layers_host, painter_text("File"))

        self.assets_host = QWidget()
        self.assets_host.setObjectName("PainterUIAssetsHost")
        assets_layout = QVBoxLayout(self.assets_host)
        assets_layout.setContentsMargins(0, 0, 0, 0)
        assets_layout.setSpacing(0)
        self.asset_tabs = QTabWidget()
        self.asset_tabs.setObjectName("PainterUIAssetTabs")
        self.asset_tabs.setDocumentMode(True)
        self.asset_tabs.tabBar().setExpanding(True)
        self.asset_tabs.tabBar().setUsesScrollButtons(False)
        variable_widget = None
        for label, widget in (asset_pages or {}).items():
            if str(label) == "Tokens":
                variable_widget = widget
                continue
            self.asset_tabs.addTab(widget, str(label))
        assets_layout.addWidget(self.asset_tabs, 1)
        self.mode_tabs.addTab(self.assets_host, painter_text("Assets"))

        self.tools_host = QWidget()
        self.tools_host.setObjectName("PainterUIToolsHost")
        tools_layout = QVBoxLayout(self.tools_host)
        tools_layout.setContentsMargins(8, 8, 8, 8)
        tools_layout.setSpacing(7)
        tools_title = QLabel(painter_text("Tools"))
        tools_title.setObjectName("PainterUINavigatorPanelTitle")
        tools_layout.addWidget(tools_title)
        self.tools_search_edit = QLineEdit()
        self.tools_search_edit.setObjectName("PainterUINavigatorSearch")
        self.tools_search_edit.setPlaceholderText(
            painter_text("Search tools")
        )
        self.tools_search_edit.setClearButtonEnabled(True)
        self.tools_search_edit.addAction(
            app_icon("search", size=12, color="#96A2B1"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        tools_layout.addWidget(self.tools_search_edit)
        tools_summary = QLabel(
            painter_text("Plugins, widgets and extensions appear here.")
        )
        tools_summary.setObjectName("PainterUINavigatorEmptyText")
        tools_summary.setWordWrap(True)
        tools_layout.addWidget(tools_summary)
        tools_empty = QLabel(painter_text("No tools installed"))
        tools_empty.setObjectName("PainterUINavigatorEmptyState")
        tools_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tools_layout.addWidget(tools_empty, 1)
        self.mode_tabs.addTab(self.tools_host, painter_text("Tools"))

        self.variables_host = QWidget()
        self.variables_host.setObjectName("PainterUIVariablesHost")
        variables_layout = QVBoxLayout(self.variables_host)
        variables_layout.setContentsMargins(0, 0, 0, 0)
        variables_layout.setSpacing(0)
        if variable_widget is not None:
            variables_layout.addWidget(variable_widget, 1)
        else:
            variables_empty = QLabel(painter_text("No variables"))
            variables_empty.setObjectName("PainterUINavigatorEmptyState")
            variables_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            variables_layout.addWidget(variables_empty, 1)
        self.variable_widget = variable_widget
        self.mode_tabs.addTab(
            self.variables_host,
            painter_text("Variables"),
        )
        self.mode_tabs.tabBar().hide()
        self.mode_tabs.setMinimumHeight(180)
        content_layout.addWidget(self.mode_tabs, 1)
        self.content_scroll.setWidget(self.content_widget)
        root.addWidget(self.content_scroll, 1)
        self._collapsible_widgets = (
            self.search_edit,
            header,
            self.content_scroll,
        )
        self.resize_handle = _NavigatorResizeHandle(self)
        self.resize_handle.width_requested.connect(
            lambda width: self.set_expanded_width(
                width,
                user_initiated=True,
            )
        )
        self._active_section = "file"
        self.select_section("file")
        self._sync_collapse_button()

    def set_collapsed(
        self,
        collapsed: bool,
        *,
        user_initiated: bool = False,
    ) -> None:
        value = bool(collapsed)
        if user_initiated:
            self._collapse_user_override = True
        if self._collapsed == value:
            return
        self._collapsed = value
        for widget in self._collapsible_widgets:
            widget.setVisible(not value)
        self.title_label.setVisible(not value)
        self.pin_button.hide()
        self.dock_button.setVisible(not value)
        if value:
            self.setMinimumWidth(self.RAIL_WIDTH)
            self.setMaximumWidth(self.RAIL_WIDTH)
            self.resize_handle.hide()
        else:
            if self._splitter_managed:
                self.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
                self.setMaximumWidth(PERSISTED_PANEL_MAX_WIDTH)
            else:
                self.setMinimumWidth(self._expanded_width)
                self.setMaximumWidth(self._expanded_width)
            self.resize_handle.setVisible(
                not self._splitter_managed
            )
        self._sync_collapse_button()
        self.collapsed_changed.emit(value)

    def set_auto_hide(
        self,
        auto_hide: bool,
        *,
        user_initiated: bool = False,
    ) -> None:
        value = bool(auto_hide)
        changed = self._auto_hide != value
        if not changed and self._collapsed == value:
            return
        self._auto_hide = value
        self.set_collapsed(value, user_initiated=user_initiated)
        if changed:
            self.auto_hide_changed.emit(value)

    def is_auto_hide(self) -> bool:
        return bool(self._auto_hide)

    def set_temporary_expanded(self, expanded: bool) -> None:
        value = bool(expanded)
        if self._temporary_expanded == value:
            return
        self._temporary_expanded = value
        for widget in self._collapsible_widgets:
            widget.setVisible(value or not self._collapsed)
        self.title_label.setVisible(value or not self._collapsed)
        self.pin_button.setVisible(value)
        self.dock_button.setVisible(not value and not self._collapsed)
        if value:
            self.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
            self.setMaximumWidth(PERSISTED_PANEL_MAX_WIDTH)
        elif self._collapsed:
            self.setMinimumWidth(self.RAIL_WIDTH)
            self.setMaximumWidth(self.RAIL_WIDTH)
        self._sync_collapse_button()

    def is_temporary_expanded(self) -> bool:
        return bool(self._temporary_expanded)

    def set_detached(self, detached: bool) -> None:
        value = bool(detached)
        self.dock_button.setToolTip(
            painter_text(
                "Dock navigator" if value else "Detach navigator"
            )
        )
        self.dock_button.setIcon(
            app_icon(
                "relink" if value else "popout",
                size=12,
                color="#B8C4D3",
            )
        )

    def set_expanded_width(
        self,
        width: int,
        *,
        user_initiated: bool = False,
    ) -> int:
        value = max(
            self.MIN_EXPANDED_WIDTH,
            int(width),
        )
        if user_initiated:
            self._collapse_user_override = True
        if value == self._expanded_width:
            return value
        self._expanded_width = value
        if not self._collapsed:
            if not self._splitter_managed:
                self.setMinimumWidth(value)
                self.setMaximumWidth(value)
            self.updateGeometry()
        self.width_changed.emit(value)
        return value

    def reveal_asset(self, label: str, asset_id: str = "") -> bool:
        target_label = str(label or "")
        if target_label == "Tokens":
            if self._collapsed and not self._temporary_expanded:
                self.set_auto_hide(False, user_initiated=True)
            self.select_section("variables")
            widget = self.variable_widget
            if widget is not None and hasattr(widget, "select_token"):
                widget.select_token(str(asset_id or ""))
            return widget is not None
        target_index = next(
            (
                index
                for index in range(self.asset_tabs.count())
                if self.asset_tabs.tabText(index) == target_label
            ),
            -1,
        )
        if target_index < 0:
            return False
        if self._collapsed and not self._temporary_expanded:
            self.set_collapsed(False, user_initiated=True)
        self.select_section("assets")
        self.asset_tabs.setCurrentIndex(target_index)
        widget = self.asset_tabs.widget(target_index)
        if target_label == "Components" and hasattr(
            widget,
            "select_component",
        ):
            widget.select_component(str(asset_id or ""))
        return True

    def adopt_expanded_width(
        self,
        width: int,
        *,
        emit_signal: bool = True,
    ) -> int:
        """Record a width chosen by the containing workspace splitter."""
        value = max(
            self.MIN_EXPANDED_WIDTH,
            int(width),
        )
        if value == self._expanded_width:
            return value
        self._expanded_width = value
        if emit_signal:
            self.width_changed.emit(value)
        return value

    def set_splitter_managed(self, managed: bool) -> None:
        self._splitter_managed = bool(managed)
        if self._collapsed:
            self.setMinimumWidth(self.RAIL_WIDTH)
            self.setMaximumWidth(self.RAIL_WIDTH)
        elif self._splitter_managed:
            self.setMinimumWidth(self.MIN_EXPANDED_WIDTH)
            self.setMaximumWidth(PERSISTED_PANEL_MAX_WIDTH)
        else:
            self.setMinimumWidth(self._expanded_width)
            self.setMaximumWidth(self._expanded_width)
        self.resize_handle.setVisible(
            not self._collapsed and not self._splitter_managed
        )

    def expanded_width(self) -> int:
        return self._expanded_width

    def is_collapsed(self) -> bool:
        return self._collapsed

    def restore_state(
        self,
        width: int,
        collapsed: bool,
        *,
        user_override: bool = False,
    ) -> None:
        self.set_expanded_width(width)
        self.set_collapsed(bool(collapsed))
        self._collapse_user_override = bool(user_override)

    def has_user_collapse_override(self) -> bool:
        return bool(self._collapse_user_override)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.navigation_rail.setGeometry(
            0,
            0,
            self.RAIL_WIDTH,
            self.height(),
        )
        self.resize_handle.setGeometry(
            max(0, self.width() - self.resize_handle.width()),
            26,
            self.resize_handle.width(),
            max(0, self.height() - 26),
        )
        if not self._collapsed:
            self.resize_handle.raise_()
        self.navigation_rail.raise_()

    def active_section(self) -> str:
        return str(self._active_section)

    def select_section(
        self,
        section: str,
        *,
        user_initiated: bool = False,
    ) -> str:
        requested = str(section or "file").strip().casefold()
        selected = requested if requested in {
            "file",
            "assets",
            "tools",
            "variables",
        } else "file"
        if user_initiated and self._collapsed:
            self.set_auto_hide(False, user_initiated=True)
        self._active_section = selected
        index_by_section = {
            "file": self.mode_tabs.indexOf(self.file_host),
            "assets": self.mode_tabs.indexOf(self.assets_host),
            "tools": self.mode_tabs.indexOf(self.tools_host),
            "variables": self.mode_tabs.indexOf(self.variables_host),
        }
        self.mode_tabs.setCurrentIndex(index_by_section[selected])
        file_visible = selected == "file"
        for widget in (
            self.search_edit,
            self.pages_header,
            self.page_list,
            self.page_actions,
        ):
            widget.setVisible(file_visible)
        labels = {
            "file": "File",
            "assets": "Assets",
            "tools": "Tools",
            "variables": "Variables",
        }
        button = self.navigation_buttons[selected]
        button.setChecked(True)
        return selected

    def set_document_title(self, title: str) -> None:
        self.title_label.setText(
            str(title or "").strip() or painter_text("Untitled")
        )

    def set_focus_mode(self, enabled: bool) -> None:
        value = bool(enabled)
        if self.focus_mode_button.isChecked() == value:
            return
        self.focus_mode_button.blockSignals(True)
        self.focus_mode_button.setChecked(value)
        self.focus_mode_button.blockSignals(False)

    def _sync_collapse_button(self) -> None:
        self.collapse_button.setIcon(
            app_icon(
                (
                    "x"
                    if self._temporary_expanded
                    else "chevron-right"
                    if self._collapsed
                    else "chevron-left"
                ),
                size=12,
                color="#B8C4D3",
            )
        )
        self.collapse_button.setIconSize(icon_size(12))
        self.collapse_button.setToolTip(
            painter_text(
                "Close navigator"
                if self._temporary_expanded
                else "Show navigator"
                if self._collapsed
                else "Auto-hide navigator"
            )
        )

    def _on_collapse_clicked(self) -> None:
        if self._temporary_expanded:
            self.temporary_close_requested.emit()
            return
        self.set_auto_hide(
            not self._collapsed,
            user_initiated=True,
        )

    def set_document(self, document: Mapping[str, Any] | None) -> None:
        value = dict(document) if isinstance(document, Mapping) else {}
        pages = [
            dict(row)
            for row in value.get("pages", [])
            if isinstance(row, Mapping)
        ]
        active_id = str(value.get("active_page_id") or "")
        self._syncing = True
        try:
            self.page_list.clear()
            for row in pages:
                page_id = str(row.get("id") or "")
                label = str(row.get("name") or page_id or "Page")
                item = QListWidgetItem(
                    app_icon("ui-frame", size=12, color="#AAB6C5"),
                    label,
                )
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsEditable
                )
                item.setData(Qt.ItemDataRole.UserRole, page_id)
                self.page_list.addItem(item)
                if page_id == active_id:
                    item.setSelected(True)
                    self.page_list.setCurrentItem(item)
            self.page_remove_button.setEnabled(len(pages) > 1)
        finally:
            self._syncing = False
        self._apply_filter(self.search_edit.text())

    def _emit_page_selection(self) -> None:
        if self._syncing:
            return
        item = self.page_list.currentItem()
        page_id = str(
            item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        )
        if page_id:
            self.page_selected.emit(page_id)

    def _emit_page_rename(self, item: QListWidgetItem) -> None:
        if self._syncing:
            return
        page_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        name = str(item.text() or "").strip()
        if page_id and name:
            self.page_rename_requested.emit(page_id, name)

    def _request_current_page_removal(self) -> None:
        item = self.page_list.currentItem()
        page_id = str(
            item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        )
        if page_id and self.page_list.count() > 1:
            self.page_remove_requested.emit(page_id)

    def _apply_filter(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for index in range(self.page_list.count()):
            item = self.page_list.item(index)
            item.setHidden(bool(query and query not in item.text().casefold()))
        for index in range(self._layer_list.count()):
            item = self._layer_list.item(index)
            item.setHidden(bool(query and query not in item.text().casefold()))


__all__ = ["PainterUINavigatorPanel"]
