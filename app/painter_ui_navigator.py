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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size


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

    artboard_selected = Signal(str)
    collapsed_changed = Signal(bool)
    width_changed = Signal(int)

    MIN_EXPANDED_WIDTH = 136
    MAX_EXPANDED_WIDTH = 320
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
        self.setMinimumWidth(self._expanded_width)
        self.setMaximumWidth(self._expanded_width)
        self._syncing = False
        self._collapsed = False
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
        self.collapse_button.clicked.connect(
            lambda: self.set_collapsed(
                not self._collapsed,
                user_initiated=True,
            )
        )
        header_layout.addWidget(self.collapse_button)
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
            self._emit_artboard_selection
        )
        content_layout.addWidget(self.page_list)

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
        if value:
            self.setMinimumWidth(34)
            self.setMaximumWidth(34)
            self.resize_handle.hide()
        else:
            self.setMinimumWidth(self._expanded_width)
            self.setMaximumWidth(self._expanded_width)
            self.resize_handle.show()
        self._sync_collapse_button()
        self.collapsed_changed.emit(value)

    def set_expanded_width(
        self,
        width: int,
        *,
        user_initiated: bool = False,
    ) -> int:
        value = max(
            self.MIN_EXPANDED_WIDTH,
            min(self.MAX_EXPANDED_WIDTH, int(width)),
        )
        if user_initiated:
            self._collapse_user_override = True
        if value == self._expanded_width:
            return value
        self._expanded_width = value
        if not self._collapsed:
            self.setMinimumWidth(value)
            self.setMaximumWidth(value)
            self.updateGeometry()
        self.width_changed.emit(value)
        return value

    def expanded_width(self) -> int:
        return self._expanded_width

    def is_collapsed(self) -> bool:
        return self._collapsed

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
                "chevron-right" if self._collapsed else "chevron-left",
                size=12,
                color="#B8C4D3",
            )
        )
        self.collapse_button.setIconSize(icon_size(12))
        self.collapse_button.setToolTip(
            "Expand navigator" if self._collapsed else "Collapse navigator"
        )

    def set_document(self, document: Mapping[str, Any] | None) -> None:
        value = dict(document) if isinstance(document, Mapping) else {}
        artboards = [
            dict(row)
            for row in value.get("artboards", [])
            if isinstance(row, Mapping)
        ]
        active_id = str(value.get("active_artboard_id") or "")
        self._syncing = True
        try:
            self.page_list.clear()
            for row in artboards:
                artboard_id = str(row.get("id") or "")
                label = str(row.get("name") or artboard_id or "Artboard")
                item = QListWidgetItem(
                    app_icon("ui-frame", size=12, color="#AAB6C5"),
                    label,
                )
                item.setData(Qt.ItemDataRole.UserRole, artboard_id)
                item.setToolTip(
                    f"{int(row.get('width') or 0)} x "
                    f"{int(row.get('height') or 0)}"
                )
                self.page_list.addItem(item)
                if artboard_id == active_id:
                    item.setSelected(True)
                    self.page_list.setCurrentItem(item)
        finally:
            self._syncing = False
        self._apply_filter(self.search_edit.text())

    def _emit_artboard_selection(self) -> None:
        if self._syncing:
            return
        item = self.page_list.currentItem()
        artboard_id = str(
            item.data(Qt.ItemDataRole.UserRole) if item is not None else ""
        )
        if artboard_id:
            self.artboard_selected.emit(artboard_id)

    def _apply_filter(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for index in range(self.page_list.count()):
            item = self.page_list.item(index)
            item.setHidden(bool(query and query not in item.text().casefold()))
        for index in range(self._layer_list.count()):
            item = self._layer_list.item(index)
            item.setHidden(bool(query and query not in item.text().casefold()))


__all__ = ["PainterUINavigatorPanel"]
