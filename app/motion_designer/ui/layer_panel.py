from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from app.motion_designer.schema import MotionComposition


class LayerPanel(QTreeWidget):
    layer_selected = Signal(str)
    layer_activated = Signal(str)
    layer_flags_changed = Signal(str, dict)
    layer_structure_changed = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderLabels(["Layer", "V", "L", "S"])
        self.setColumnWidth(0, 170)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.itemSelectionChanged.connect(self._emit_selection)
        self.itemDoubleClicked.connect(
            lambda item, _column: self.layer_activated.emit(
                str(item.data(0, Qt.UserRole) or ""),
            ),
        )
        self.itemChanged.connect(self._emit_flags)
        self._loading = False

    def set_composition(self, composition: MotionComposition) -> None:
        self._loading = True
        self.clear()
        by_id: dict[str, QTreeWidgetItem] = {}
        for layer in reversed(composition.layers):
            item = QTreeWidgetItem([layer.name, "", "", ""])
            item.setData(0, Qt.UserRole, layer.id)
            item.setFlags(item.flags() | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
            for column, checked in ((1, layer.visible), (2, layer.locked), (3, layer.solo)):
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(column, Qt.Checked if checked else Qt.Unchecked)
            by_id[layer.id] = item
        for layer in reversed(composition.layers):
            item = by_id[layer.id]
            parent = by_id.get(layer.parent_id)
            (parent.addChild if parent else self.addTopLevelItem)(item)
        self.expandAll()
        self._loading = False

    def select_layer(self, layer_id: str) -> None:
        iterator = self.findItems("*", Qt.MatchWildcard | Qt.MatchRecursive, 0)
        for item in iterator:
            if item.data(0, Qt.UserRole) == layer_id:
                self.setCurrentItem(item)
                break

    def selected_layer_ids(self) -> list[str]:
        return [
            str(item.data(0, Qt.UserRole) or "")
            for item in self.selectedItems()
            if str(item.data(0, Qt.UserRole) or "")
        ]

    def _emit_selection(self) -> None:
        if self._loading:
            return
        item = self.currentItem()
        if item:
            self.layer_selected.emit(str(item.data(0, Qt.UserRole) or ""))

    def _emit_flags(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._loading:
            return
        self.layer_flags_changed.emit(str(item.data(0, Qt.UserRole) or ""), {
            "visible": item.checkState(1) == Qt.Checked,
            "locked": item.checkState(2) == Qt.Checked,
            "solo": item.checkState(3) == Qt.Checked,
        })

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        if self._loading:
            return
        rows: list[dict[str, str]] = []

        def append_item(item: QTreeWidgetItem, parent_id: str = "") -> None:
            layer_id = str(item.data(0, Qt.UserRole) or "")
            if layer_id:
                rows.append({"id": layer_id, "parent_id": parent_id})
            for index in range(item.childCount()):
                append_item(item.child(index), layer_id)

        for index in range(self.topLevelItemCount()):
            append_item(self.topLevelItem(index))
        self.layer_structure_changed.emit(rows)
