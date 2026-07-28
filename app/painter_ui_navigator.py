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
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size


class PainterUINavigatorPanel(QFrame):
    """Left-side document navigator that reuses the canonical Layers page."""

    artboard_selected = Signal(str)

    def __init__(
        self,
        layers_page: QWidget,
        layer_list: QListWidget,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUINavigator")
        self.setMinimumWidth(196)
        self.setMaximumWidth(224)
        self._syncing = False
        self._layer_list = layer_list

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("PainterUINavigatorHeader")
        header.setFixedHeight(32)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 5, 8, 5)
        title = QLabel("Document")
        title.setObjectName("PainterUINavigatorTitle")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        root.addWidget(header)

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("PainterUINavigatorSearch")
        self.search_edit.setFixedHeight(28)
        self.search_edit.setPlaceholderText("Search pages and layers")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.addAction(
            app_icon("search", size=12, color="#96A2B1"),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self.search_edit.textChanged.connect(self._apply_filter)
        root.addWidget(self.search_edit)

        pages_header = QLabel("PAGES")
        pages_header.setObjectName("PainterUINavigatorSection")
        root.addWidget(pages_header)
        self.page_list = QListWidget()
        self.page_list.setObjectName("PainterUIPageList")
        self.page_list.setIconSize(icon_size(13))
        self.page_list.setMaximumHeight(112)
        self.page_list.itemSelectionChanged.connect(
            self._emit_artboard_selection
        )
        root.addWidget(self.page_list)

        layers_header = QLabel("LAYERS")
        layers_header.setObjectName("PainterUINavigatorSection")
        root.addWidget(layers_header)
        layers_page.setObjectName("PainterUILayersPage")
        root.addWidget(layers_page, 1)
        layers_page.show()

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
