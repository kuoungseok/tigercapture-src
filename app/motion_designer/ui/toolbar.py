from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QStyle, QToolBar, QToolButton

from app.icons import app_icon

from .catalog import BEHAVIOR_ITEMS, FILTER_ITEMS, OBJECT_ITEMS


class MotionToolbar(QToolBar):
    add_layer_requested = Signal(str)
    behavior_requested = Signal(str)
    effect_requested = Signal(str)
    delete_requested = Signal()
    duplicate_requested = Signal()
    undo_requested = Signal()
    redo_requested = Signal()
    ai_toggled = Signal(bool)
    output_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__("Motion Tools", parent)
        self.setMovable(False)
        style = self.style()
        undo = QAction(style.standardIcon(QStyle.SP_ArrowBack), "Undo", self)
        redo = QAction(style.standardIcon(QStyle.SP_ArrowForward), "Redo", self)
        undo.setShortcut("Ctrl+Z")
        redo.setShortcut("Ctrl+Shift+Z")
        undo.triggered.connect(self.undo_requested)
        redo.triggered.connect(self.redo_requested)
        self.addAction(undo)
        self.addAction(redo)
        duplicate = QAction("Duplicate", self)
        duplicate.setShortcut("Ctrl+D")
        duplicate.triggered.connect(self.duplicate_requested)
        delete = QAction(style.standardIcon(QStyle.SP_TrashIcon), "Delete", self)
        delete.setShortcut("Delete")
        delete.triggered.connect(self.delete_requested)
        self.addAction(duplicate)
        self.addAction(delete)
        self.addSeparator()
        self.addWidget(self._menu_button(
            "Add Object", QStyle.SP_FileIcon, OBJECT_ITEMS, self.add_layer_requested,
        ))
        self.addWidget(self._menu_button(
            "Behaviors", QStyle.SP_MediaPlay, BEHAVIOR_ITEMS, self.behavior_requested,
        ))
        self.addWidget(self._menu_button(
            "Filters", QStyle.SP_DialogApplyButton, FILTER_ITEMS, self.effect_requested,
        ))
        self.addSeparator()
        self.ai_action = QAction(
            app_icon("ai-script", size=18, color="#d9dde3"), "AI", self,
        )
        self.ai_action.setCheckable(True)
        self.ai_action.setChecked(True)
        self.ai_action.setToolTip("Show or hide the multimodal AI workspace")
        self.ai_action.toggled.connect(self.ai_toggled)
        self.addAction(self.ai_action)
        self.addSeparator()
        output = QAction(style.standardIcon(QStyle.SP_DialogSaveButton), "Export", self)
        output.setToolTip("Open Motion delivery and color settings")
        output.triggered.connect(self.output_requested)
        self.addAction(output)

    def set_ai_visible(self, visible: bool) -> None:
        self.ai_action.blockSignals(True)
        self.ai_action.setChecked(bool(visible))
        self.ai_action.blockSignals(False)

    def _menu_button(self, label: str, icon: QStyle.StandardPixmap, rows, signal) -> QToolButton:
        button = QToolButton(self)
        button.setText(label)
        button.setIcon(self.style().standardIcon(icon))
        button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for title, value in rows:
            action = menu.addAction(title)
            action.triggered.connect(lambda _checked=False, item=value: signal.emit(item))
        button.setMenu(menu)
        return button
