from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .catalog import (
    CATALOG,
    CATEGORY_HINTS,
    CATEGORY_LABELS,
    ITEM_DESCRIPTIONS,
)


class MotionLibraryPanel(QWidget):
    apply_requested = Signal(str, str)
    templates_requested = Signal()
    ai_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionLibraryPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(9, 10, 9, 9)
        layout.setSpacing(7)
        title = QLabel("Create", self)
        title.setObjectName("MotionPanelTitle")
        layout.addWidget(title)

        start_actions = QHBoxLayout()
        start_actions.setSpacing(6)
        self.templates_button = QPushButton("Templates", self)
        self.templates_button.setObjectName("MotionPrimaryButton")
        self.templates_button.setIcon(
            self.style().standardIcon(QStyle.SP_DirIcon)
        )
        self.ai_button = QPushButton("Create with AI", self)
        self.ai_button.setIcon(
            self.style().standardIcon(QStyle.SP_FileDialogContentsView)
        )
        start_actions.addWidget(self.templates_button)
        start_actions.addWidget(self.ai_button)
        layout.addLayout(start_actions)

        divider = QLabel("ADD TO COMPOSITION", self)
        divider.setObjectName("MotionPanelEyebrow")
        layout.addWidget(divider)
        self.search = QLineEdit(self)
        self.search.setPlaceholderText("Search objects, animation, effects")
        self.category = QComboBox(self)
        for key in CATALOG:
            self.category.addItem(CATEGORY_LABELS.get(key, key), key)
        self.category_hint = QLabel(self)
        self.category_hint.setObjectName("MotionPanelHint")
        self.items = QListWidget(self)
        self.items.setObjectName("MotionAddList")
        self.items.setViewMode(QListView.ListMode)
        self.items.setResizeMode(QListView.Adjust)
        self.items.setMovement(QListView.Static)
        self.items.setSpacing(2)
        self.items.setUniformItemSizes(True)
        self.apply_button = QPushButton("Add Object", self)
        self.apply_button.setObjectName("MotionPrimaryButton")
        self.apply_button.setEnabled(False)
        layout.addWidget(self.category)
        layout.addWidget(self.category_hint)
        layout.addWidget(self.search)
        layout.addWidget(self.items, 1)
        layout.addWidget(self.apply_button)
        self.templates_button.clicked.connect(self.templates_requested)
        self.ai_button.clicked.connect(self.ai_requested)
        self.category.currentIndexChanged.connect(self._populate)
        self.search.textChanged.connect(self._populate)
        self.items.itemSelectionChanged.connect(self._selection_changed)
        self.apply_button.clicked.connect(self._apply)
        self.items.itemDoubleClicked.connect(lambda _item: self._apply())
        self._populate()

    def _category_key(self) -> str:
        return str(self.category.currentData() or "Objects")

    def _populate(self, *_args) -> None:
        category = self._category_key()
        query = self.search.text().strip().lower()
        self.category_hint.setText(CATEGORY_HINTS.get(category, ""))
        self.items.clear()
        for label, domain, kind in CATALOG.get(category, ()):
            description = ITEM_DESCRIPTIONS.get(kind, "")
            if query and query not in f"{label} {description}".lower():
                continue
            item = QListWidgetItem(self.style().standardIcon({
                "object": QStyle.SP_FileIcon,
                "generator": QStyle.SP_ComputerIcon,
                "replicator": QStyle.SP_FileDialogListView,
                "behavior": QStyle.SP_MediaPlay,
                "effect": QStyle.SP_DialogApplyButton,
                "template": QStyle.SP_DirIcon,
                "advanced_preset": QStyle.SP_ArrowForward,
            }[domain]), f"{label}\n{description}".rstrip())
            item.setData(Qt.UserRole, (domain, kind))
            item.setData(Qt.UserRole + 1, label)
            item.setSizeHint(QSize(0, 48))
            self.items.addItem(item)
        if self.items.count():
            self.items.setCurrentRow(0)
        else:
            self.apply_button.setText("No matching items")
            self.apply_button.setEnabled(False)

    def _selection_changed(self) -> None:
        item = self.items.currentItem()
        if item is None:
            self.apply_button.setEnabled(False)
            return
        domain, _kind = item.data(Qt.UserRole)
        label = str(item.data(Qt.UserRole + 1) or "Item")
        verb = {
            "object": "Add",
            "generator": "Add",
            "replicator": "Apply",
            "behavior": "Animate with",
            "effect": "Apply",
            "template": "Use",
            "advanced_preset": "Apply",
        }.get(str(domain), "Apply")
        self.apply_button.setText(f"{verb} {label}")
        self.apply_button.setEnabled(True)

    def _apply(self) -> None:
        item = self.items.currentItem()
        if item is not None:
            domain, kind = item.data(Qt.UserRole)
            self.apply_requested.emit(str(domain), str(kind))
