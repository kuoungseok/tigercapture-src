"""PPT workspace media-pool panel."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QMimeData, Qt, QUrl, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from app.icons import app_icon, icon_size


class PptAssetListWidget(QListWidget):
    """List widget that drags PPT media-pool assets as local file URLs."""

    def startDrag(self, supported_actions) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole + 1) or "").strip()
        if not path:
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(path)])
        mime.setText(path)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class PptMediaPoolPanel(QFrame):
    addRequested = Signal()
    insertRequested = Signal(str)
    removeRequested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PptMediaPoolPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Media Pool", self)
        title.setObjectName("ToolbarGroupLabel")
        header.addWidget(title)
        header.addStretch(1)
        self.count_label = QLabel("0", self)
        self.count_label.setObjectName("PptPanelHint")
        header.addWidget(self.count_label)
        layout.addLayout(header)

        self.list_widget = PptAssetListWidget(self)
        self.list_widget.setObjectName("PptMediaPoolList")
        self.list_widget.setDragEnabled(True)
        self.list_widget.setMinimumHeight(96)
        self.list_widget.setMaximumHeight(150)
        self.list_widget.itemDoubleClicked.connect(self._insert_current)
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(5)
        self.add_button = self._button("Add", "plus")
        self.insert_button = self._button("Insert", "download")
        self.remove_button = self._button("Remove", "trash")
        self.add_button.clicked.connect(self.addRequested)
        self.insert_button.clicked.connect(self._insert_current)
        self.remove_button.clicked.connect(self._remove_current)
        for button in (self.add_button, self.insert_button, self.remove_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _button(self, label: str, icon_name: str) -> QPushButton:
        button = QPushButton(label, self)
        button.setObjectName("PptInsertButton")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setIcon(app_icon(icon_name, size=13, color="#D7DAE7"))
        button.setIconSize(icon_size(13))
        return button

    def set_assets(self, assets: list[dict[str, Any]], *, selected_asset_id: str = "") -> None:
        current = selected_asset_id or self.selected_asset_id()
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        selected_row = -1
        for row, asset in enumerate(assets):
            asset_id = str(asset.get("id") or "")
            kind = str(asset.get("kind") or "media")
            path = str(asset.get("path") or asset.get("source_path") or "")
            name = str(asset.get("name") or Path(path).name or kind)
            suffix = Path(path).suffix.lower()
            missing = "" if bool(asset.get("exists", False)) else " !"
            item = QListWidgetItem(f"{name}{missing}\n{kind}{(' ' + suffix) if suffix else ''}")
            item.setData(Qt.ItemDataRole.UserRole, asset_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, path)
            item.setToolTip(path)
            self.list_widget.addItem(item)
            if asset_id == current:
                selected_row = row
        if selected_row >= 0:
            self.list_widget.setCurrentRow(selected_row)
        elif assets:
            self.list_widget.setCurrentRow(0)
        self.list_widget.blockSignals(False)
        self.count_label.setText(str(len(assets)))

    def selected_asset_id(self) -> str:
        item = self.list_widget.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole) or "") if item is not None else ""

    def _insert_current(self) -> None:
        asset_id = self.selected_asset_id()
        if asset_id:
            self.insertRequested.emit(asset_id)

    def _remove_current(self) -> None:
        asset_id = self.selected_asset_id()
        if asset_id:
            self.removeRequested.emit(asset_id)


__all__ = ["PptAssetListWidget", "PptMediaPoolPanel"]
