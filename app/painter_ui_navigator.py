"""Figma-style Pages and Layers navigator for Painter UI Design."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

    MIN_EXPANDED_WIDTH = 112
    DEFAULT_EXPANDED_WIDTH = 168

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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("PainterUINavigatorHeader")
        header.setFixedHeight(26)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(5, 2, 4, 2)
        title = QLabel("Document")
        title.setObjectName("PainterUINavigatorTitle")
        self.title_label = title
        header_layout.addWidget(title)
        header_layout.addStretch(1)
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
        content_layout.addWidget(self.search_edit)

        pages_header = QLabel("PAGES")
        pages_header.setObjectName("PainterUINavigatorSection")
        content_layout.addWidget(pages_header)
        self.page_list = QListWidget()
        self.page_list.setObjectName("PainterUIPageList")
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
        layers_page.setObjectName("PainterUILayersPage")
        layers_host_layout.addWidget(layers_page, 1)
        layers_page.show()
        self.mode_tabs.addTab(layers_host, "Layers")

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
        for label, widget in (asset_pages or {}).items():
            self.asset_tabs.addTab(widget, str(label))
        assets_layout.addWidget(self.asset_tabs, 1)
        self.mode_tabs.addTab(self.assets_host, "Assets")
        self.mode_tabs.setMinimumHeight(180)
        content_layout.addWidget(self.mode_tabs, 1)
        self.content_scroll.setWidget(self.content_widget)
        root.addWidget(self.content_scroll, 1)
        self._collapsible_widgets = (
            self.search_edit,
            pages_header,
            self.page_list,
            self.page_actions,
            self.mode_tabs,
        )
        self.resize_handle = _NavigatorResizeHandle(self)
        self.resize_handle.width_requested.connect(
            lambda width: self.set_expanded_width(
                width,
                user_initiated=True,
            )
        )
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
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
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
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
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
        self.mode_tabs.setCurrentWidget(self.assets_host)
        self.asset_tabs.setCurrentIndex(target_index)
        widget = self.asset_tabs.widget(target_index)
        if target_label == "Tokens" and hasattr(widget, "select_token"):
            widget.select_token(str(asset_id or ""))
        elif target_label == "Components" and hasattr(
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
            self.setMinimumWidth(0)
            self.setMaximumWidth(0)
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
        self.resize_handle.setGeometry(
            max(0, self.width() - self.resize_handle.width()),
            26,
            self.resize_handle.width(),
            max(0, self.height() - 26),
        )
        if not self._collapsed:
            self.resize_handle.raise_()

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
