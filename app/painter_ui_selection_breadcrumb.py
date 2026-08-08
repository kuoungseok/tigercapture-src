"""Compact canvas-local hierarchy breadcrumb for UI Design."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QWidget

from app.icons import app_icon, icon_size
from app.painter_ui_selection_navigation import ui_selection_path


class PainterUISelectionBreadcrumb(QFrame):
    object_requested = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUISelectionBreadcrumb")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(5, 3, 5, 3)
        self._layout.setSpacing(2)
        self.setFixedHeight(30)
        self.hide()

    def set_document(self, document: Mapping[str, Any] | None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        # The inspector hands this a canonical document.
        path = ui_selection_path(document, normalize=False)
        if len(path) < 2:
            self.hide()
            return
        for index, row in enumerate(path):
            if index:
                separator = QPushButton("")
                separator.setObjectName("PainterUIBreadcrumbSeparator")
                separator.setEnabled(False)
                separator.setFixedSize(14, 22)
                separator.setIcon(
                    app_icon("chevron-right", size=10, color="#7D8998")
                )
                separator.setIconSize(icon_size(10))
                self._layout.addWidget(separator)
            button = QPushButton(str(row["name"]))
            button.setObjectName("PainterUIBreadcrumbItem")
            button.setToolTip(
                f"{row['name']} - "
                f"{str(row['kind']).replace('_', ' ').title()}"
            )
            button.setAccessibleName(button.toolTip())
            button.setFixedWidth(
                min(
                    112,
                    max(
                        44,
                        button.fontMetrics().horizontalAdvance(
                            button.text()
                        )
                        + 18,
                    ),
                )
            )
            button.clicked.connect(
                lambda _checked=False, object_id=str(row["id"]): (
                    self.object_requested.emit(object_id)
                )
            )
            self._layout.addWidget(button)
        self._layout.activate()
        width = 10 + sum(
            item.widget().width()
            for index in range(self._layout.count())
            if (item := self._layout.itemAt(index)).widget() is not None
        )
        width += max(0, self._layout.count() - 1) * self._layout.spacing()
        self.setFixedWidth(width)
        self.show()
        self.raise_()

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None or not self.isVisible():
            return
        parent_layout = parent.layout()
        if parent_layout is not None and parent_layout.indexOf(self) >= 0:
            # The canvas mode bar owns this widget in normal UI Design mode.
            # Let its layout reserve real chrome space instead of covering the
            # top edge of the artboard.
            self.raise_()
            return
        self.move(
            max(8, min(28, parent.width() - self.width() - 8)),
            27,
        )
        self.raise_()


__all__ = ["PainterUISelectionBreadcrumb"]
