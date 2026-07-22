from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QListWidget, QListWidgetItem, QStyle, QToolButton, QVBoxLayout, QWidget

from app.motion_designer.schema import MotionLayer


BEHAVIOR_PARAMS = {
    "fade": (("start_ms", 0, 600000, 10), ("end_ms", 1, 600000, 10)),
    "slide": (("distance_x", -10000, 10000, 1), ("distance_y", -10000, 10000, 1)),
    "pop": (("from", 0, 4, .05), ("overshoot", 0, 2, .02)),
    "spring": (("amplitude", 0, 1000, 1), ("frequency", 0, 30, .1), ("damping", 0, 30, .1)),
    "wiggle": (("amplitude", 0, 360, .5), ("frequency", 0, 30, .1)),
}


class BehaviorPanel(QWidget):
    add_requested = Signal(str)
    delete_requested = Signal(str)
    parameter_changed = Signal(str, str, object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: dict[str, object] = {}
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        tools = QHBoxLayout()
        self.kind = QComboBox(self)
        self.kind.addItems(BEHAVIOR_PARAMS)
        add = QToolButton(self)
        add.setIcon(self.style().standardIcon(QStyle.SP_FileDialogNewFolder))
        add.setToolTip("Add behavior")
        remove = QToolButton(self)
        remove.setIcon(self.style().standardIcon(QStyle.SP_TrashIcon))
        remove.setToolTip("Delete behavior")
        tools.addWidget(self.kind, 1)
        tools.addWidget(add)
        tools.addWidget(remove)
        self.list = QListWidget(self)
        self.params_host = QWidget(self)
        self.params = QFormLayout(self.params_host)
        root.addLayout(tools)
        root.addWidget(self.list)
        root.addWidget(self.params_host)
        root.addStretch(1)
        add.clicked.connect(lambda: self.add_requested.emit(self.kind.currentText()))
        remove.clicked.connect(self._delete)
        self.list.currentItemChanged.connect(lambda _a, _b: self._rebuild())

    def set_layer(self, layer: MotionLayer | None) -> None:
        selected = self.current_id()
        self._loading = True
        self.list.clear()
        rows = list(layer.behaviors) if layer else []
        self._items = {item.id: item for item in rows}
        for behavior in rows:
            item = QListWidgetItem(behavior.kind.title())
            item.setData(Qt.UserRole, behavior.id)
            self.list.addItem(item)
            if behavior.id == selected:
                self.list.setCurrentItem(item)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self.setEnabled(layer is not None)
        self._loading = False
        self._rebuild()

    def current_id(self) -> str:
        item = self.list.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def _clear(self) -> None:
        while self.params.rowCount():
            self.params.removeRow(0)

    def _rebuild(self) -> None:
        self._clear()
        item_id = self.current_id()
        behavior = self._items.get(item_id)
        if behavior is None:
            return
        for key, minimum, maximum, step in BEHAVIOR_PARAMS.get(behavior.kind, ()):
            spin = QDoubleSpinBox(self.params_host)
            spin.setRange(minimum, maximum)
            spin.setSingleStep(step)
            value = getattr(behavior, key, behavior.params.get(key, 0.0))
            if key == "distance_x":
                value = (behavior.params.get("distance") or [100.0, 0.0])[0]
            elif key == "distance_y":
                value = (behavior.params.get("distance") or [100.0, 0.0])[1]
            spin.setValue(float(value))
            spin.valueChanged.connect(lambda value, bid=item_id, name=key: self._emit(bid, name, value))
            self.params.addRow(key.replace("_", " ").title(), spin)

    def _emit(self, item_id: str, key: str, value: float) -> None:
        if not self._loading:
            self.parameter_changed.emit(item_id, key, value)

    def _delete(self) -> None:
        if self.current_id():
            self.delete_requested.emit(self.current_id())
