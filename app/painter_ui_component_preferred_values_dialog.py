"""Editor for Figma-style preferred values on Instance Swap properties."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_components import normalize_ui_component_property_definitions
from app.painter_ui_document import PainterUIDocumentError, normalize_ui_document


class PainterUIInstanceSwapPreferredDialog(QDialog):
    """Curate and order suggestions while keeping every component searchable."""

    def __init__(
        self,
        document: Mapping[str, Any],
        *,
        component_id: str,
        property_name: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._document = normalize_ui_document(document)
        self._component_id = str(component_id)
        self._property_name = str(property_name)
        self._syncing = False
        component = next(
            (
                row
                for row in self._document["components"]
                if row["id"] == self._component_id
            ),
            None,
        )
        if component is None:
            raise PainterUIDocumentError(
                f"UI component not found: {self._component_id}"
            )
        definitions = normalize_ui_component_property_definitions(
            component.get("property_definitions")
        )
        definition = definitions.get(self._property_name)
        if definition is None or definition.get("type") != "instance_swap":
            raise PainterUIDocumentError(
                f"Instance Swap property not found: {self._property_name}"
            )
        self._components = {
            str(row["id"]): str(row["name"])
            for row in self._document["components"]
        }
        self.setObjectName("PainterUIInstanceSwapPreferredDialog")
        self.setWindowTitle("Edit preferred instances")
        self.resize(520, 520)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        heading = QLabel(f"Preferred instances · {self._property_name}")
        heading.setObjectName("PainterUIPreferredInstancesTitle")
        root.addWidget(heading)
        hint = QLabel(
            "Preferred instances appear first when swapping. "
            "All other local components remain available through search."
        )
        hint.setObjectName("PaintMuted")
        hint.setWordWrap(True)
        root.addWidget(hint)

        root.addWidget(QLabel("Preferred order"))
        order_row = QHBoxLayout()
        self.preferred_list = QListWidget()
        self.preferred_list.setObjectName("PainterUIPreferredInstancesOrder")
        self.preferred_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.preferred_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        order_row.addWidget(self.preferred_list, 1)
        move_column = QVBoxLayout()
        self.move_up_button = QPushButton("Up")
        self.move_down_button = QPushButton("Down")
        self.remove_button = QPushButton("Remove")
        self.move_up_button.clicked.connect(lambda: self._move_current(-1))
        self.move_down_button.clicked.connect(lambda: self._move_current(1))
        self.remove_button.clicked.connect(self._remove_current)
        move_column.addWidget(self.move_up_button)
        move_column.addWidget(self.move_down_button)
        move_column.addWidget(self.remove_button)
        move_column.addStretch(1)
        order_row.addLayout(move_column)
        root.addLayout(order_row, 1)

        root.addWidget(QLabel("Available components"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search components")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._filter_candidates)
        root.addWidget(self.search_edit)
        self.available_list = QListWidget()
        self.available_list.setObjectName("PainterUIPreferredInstancesAvailable")
        self.available_list.itemChanged.connect(self._candidate_changed)
        root.addWidget(self.available_list, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._syncing = True
        for component_row in self._document["components"]:
            item = QListWidgetItem(str(component_row["name"]))
            item.setData(Qt.ItemDataRole.UserRole, str(component_row["id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.available_list.addItem(item)
        for preferred_id in definition.get("preferred_values", []):
            if str(preferred_id) in self._components:
                self._append_preferred(str(preferred_id))
        self._sync_candidate_checks()
        self._syncing = False

    def preferred_component_ids(self) -> list[str]:
        return [
            str(self.preferred_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.preferred_list.count())
        ]

    def _append_preferred(self, component_id: str) -> None:
        if component_id in self.preferred_component_ids():
            return
        item = QListWidgetItem(self._components[component_id])
        item.setData(Qt.ItemDataRole.UserRole, component_id)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
        self.preferred_list.addItem(item)

    def _sync_candidate_checks(self) -> None:
        selected = set(self.preferred_component_ids())
        previous = self._syncing
        self._syncing = True
        for index in range(self.available_list.count()):
            item = self.available_list.item(index)
            item.setCheckState(
                Qt.CheckState.Checked
                if str(item.data(Qt.ItemDataRole.UserRole)) in selected
                else Qt.CheckState.Unchecked
            )
        self._syncing = previous

    def _candidate_changed(self, item: QListWidgetItem) -> None:
        if self._syncing:
            return
        component_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if item.checkState() == Qt.CheckState.Checked:
            self._append_preferred(component_id)
        else:
            self._remove_component(component_id)

    def _remove_component(self, component_id: str) -> None:
        for index in range(self.preferred_list.count()):
            item = self.preferred_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole)) == component_id:
                self.preferred_list.takeItem(index)
                break
        self._sync_candidate_checks()

    def _remove_current(self) -> None:
        current = self.preferred_list.currentItem()
        if current is not None:
            self._remove_component(
                str(current.data(Qt.ItemDataRole.UserRole) or "")
            )

    def _move_current(self, offset: int) -> None:
        current = self.preferred_list.currentRow()
        target = current + int(offset)
        if current < 0 or target < 0 or target >= self.preferred_list.count():
            return
        item = self.preferred_list.takeItem(current)
        self.preferred_list.insertItem(target, item)
        self.preferred_list.setCurrentRow(target)

    def _filter_candidates(self, text: str) -> None:
        query = str(text or "").strip().casefold()
        for index in range(self.available_list.count()):
            item = self.available_list.item(index)
            item.setHidden(bool(query) and query not in item.text().casefold())


__all__ = ["PainterUIInstanceSwapPreferredDialog"]
