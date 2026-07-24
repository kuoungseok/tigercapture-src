from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QComboBox, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QStyle, QVBoxLayout, QWidget

from .catalog import CATALOG


class MotionLibraryPanel(QWidget):
    apply_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionLibraryPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search")
        self.category = QComboBox(self)
        self.category.addItems(CATALOG)
        self.items = QListWidget(self)
        self.items.setViewMode(QListWidget.IconMode)
        self.items.setResizeMode(QListWidget.Adjust)
        self.items.setGridSize(QSize(104, 72))
        self.items.setSpacing(4)
        self.items.setUniformItemSizes(True)
        self.apply_button = QPushButton("Apply", self)
        self.apply_button.setObjectName("MotionPrimaryButton")
        layout.addWidget(self.search)
        layout.addWidget(self.category)
        layout.addWidget(self.items, 1)
        layout.addWidget(self.apply_button)
        self.category.currentTextChanged.connect(self._populate)
        self.search.textChanged.connect(lambda _text: self._populate(self.category.currentText()))
        self.apply_button.clicked.connect(self._apply)
        self.items.itemDoubleClicked.connect(lambda _item: self._apply())
        self._populate(self.category.currentText())

    def _populate(self, category: str) -> None:
        query = self.search.text().strip().lower()
        self.items.clear()
        for label, domain, kind in CATALOG.get(category, ()):
            if query and query not in label.lower():
                continue
            item = QListWidgetItem(self.style().standardIcon({
                "object": QStyle.SP_FileIcon,
                "behavior": QStyle.SP_MediaPlay,
                "effect": QStyle.SP_DialogApplyButton,
                "template": QStyle.SP_DirIcon,
                "advanced_preset": QStyle.SP_ArrowForward,
            }[domain]), label)
            item.setData(Qt.UserRole, (domain, kind))
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            self.items.addItem(item)
        if self.items.count():
            self.items.setCurrentRow(0)

    def _apply(self) -> None:
        item = self.items.currentItem()
        if item is not None:
            domain, kind = item.data(Qt.UserRole)
            self.apply_requested.emit(str(domain), str(kind))
