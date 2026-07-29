"""Compact selection-driven Prototype authoring panel."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.painter_ui_document import (
    UI_INTERACTION_ACTIONS,
    UI_INTERACTION_TRIGGERS,
    normalize_ui_document,
)
from app.painter_ui_prototype_authoring import (
    UI_PROTOTYPE_TRANSITIONS,
    inspect_ui_prototype_authoring,
)


class PainterUIPrototypePanel(QWidget):
    connection_add_requested = Signal(object)
    connection_remove_requested = Signal(str)
    transition_set_requested = Signal(str, object)
    flow_add_requested = Signal(object)
    flow_activate_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIPrototypePanel")
        self._document = normalize_ui_document(None)
        self._object_id = ""
        self.setStyleSheet(
            """
            QWidget#PainterUIPrototypePanel { background:#111720; color:#DDE5EF; }
            QWidget#PainterUIPrototypePanel QLabel { color:#AEB9C8; }
            QWidget#PainterUIPrototypePanel QComboBox,
            QWidget#PainterUIPrototypePanel QSpinBox,
            QWidget#PainterUIPrototypePanel QListWidget {
                background:#0C1118; color:#E7EDF5; border:1px solid #2B3543;
                border-radius:4px; selection-background-color:#284B72;
            }
            QWidget#PainterUIPrototypePanel QPushButton {
                min-height:24px; background:#192230; color:#DDE5EF;
                border:1px solid #303C4C; border-radius:4px; padding:1px 7px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.status_label = QLabel("Select one UI object to add interactions")
        self.status_label.setFixedHeight(24)
        layout.addWidget(self.status_label)

        flow_row = QHBoxLayout()
        self.flow_combo = QComboBox()
        self.flow_combo.currentIndexChanged.connect(self._emit_flow_activate)
        self.flow_add_button = QPushButton("+ Flow")
        self.flow_add_button.clicked.connect(self._emit_flow_add)
        flow_row.addWidget(self.flow_combo, 1)
        flow_row.addWidget(self.flow_add_button)
        layout.addLayout(flow_row)

        self.connection_list = QListWidget()
        self.connection_list.setFixedHeight(112)
        self.connection_list.currentItemChanged.connect(self._sync_connection)
        layout.addWidget(self.connection_list)

        connection_row = QHBoxLayout()
        self.trigger_combo = QComboBox()
        for value in sorted(UI_INTERACTION_TRIGGERS):
            self.trigger_combo.addItem(value.replace("_", " ").title(), value)
        self.action_combo = QComboBox()
        for value in sorted(UI_INTERACTION_ACTIONS):
            self.action_combo.addItem(value.replace("_", " ").title(), value)
        connection_row.addWidget(self.trigger_combo)
        connection_row.addWidget(self.action_combo)
        layout.addLayout(connection_row)

        target_row = QHBoxLayout()
        self.target_combo = QComboBox()
        self.add_button = QPushButton("Connect")
        self.add_button.clicked.connect(self._emit_add)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._emit_remove)
        target_row.addWidget(self.target_combo, 1)
        target_row.addWidget(self.add_button)
        target_row.addWidget(self.remove_button)
        layout.addLayout(target_row)

        transition_row = QHBoxLayout()
        self.transition_combo = QComboBox()
        for value in UI_PROTOTYPE_TRANSITIONS:
            self.transition_combo.addItem(value.replace("_", " ").title(), value)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 10000)
        self.duration_spin.setSuffix(" ms")
        self.transition_button = QPushButton("Set")
        self.transition_button.clicked.connect(self._emit_transition)
        transition_row.addWidget(self.transition_combo, 1)
        transition_row.addWidget(self.duration_spin)
        transition_row.addWidget(self.transition_button)
        layout.addLayout(transition_row)

    def set_document(self, value: Mapping[str, Any]) -> None:
        self._document = normalize_ui_document(value)
        self._object_id = str(self._document["selection"]["object_id"] or "")
        report = inspect_ui_prototype_authoring(
            self._document,
            object_id=self._object_id,
        )
        self.flow_combo.blockSignals(True)
        self.flow_combo.clear()
        for flow in report["flows"]:
            self.flow_combo.addItem(flow["name"], flow["id"])
        index = self.flow_combo.findData(report["active_flow_id"])
        self.flow_combo.setCurrentIndex(index)
        self.flow_combo.blockSignals(False)
        self.target_combo.clear()
        for artboard in self._document["artboards"]:
            self.target_combo.addItem(artboard["name"], artboard["id"])
        self.connection_list.clear()
        for row in report["interactions"]:
            smart_animate = dict(row.get("smart_animate") or {})
            smart_status = str(smart_animate.get("status") or "")
            suffix = (
                f"  [{smart_status}]"
                if smart_status in {"partial", "fallback", "blocked"}
                else ""
            )
            item = QListWidgetItem(
                f"{row['trigger'].replace('_', ' ')} -> "
                f"{row['action'].replace('_', ' ')}{suffix}"
            )
            item.setData(Qt.ItemDataRole.UserRole, row)
            if suffix:
                item.setToolTip(
                    ", ".join(smart_animate.get("fallback_reasons") or [])
                )
            self.connection_list.addItem(item)
        enabled = bool(self._object_id)
        self.status_label.setText(
            f"{report['interaction_count']} interactions"
            if enabled
            else "Select one UI object to add interactions"
        )
        for widget in (
            self.trigger_combo,
            self.action_combo,
            self.target_combo,
            self.add_button,
            self.flow_add_button,
        ):
            widget.setEnabled(enabled)
        self._sync_connection(self.connection_list.currentItem())

    def _selected_interaction(self) -> dict[str, Any]:
        item = self.connection_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else {}
        return dict(value) if isinstance(value, Mapping) else {}

    def _sync_connection(self, current, _previous=None) -> None:
        row = self._selected_interaction()
        enabled = bool(row)
        self.remove_button.setEnabled(enabled)
        self.transition_button.setEnabled(enabled)
        if not row:
            return
        transition = row["transition"]
        self.transition_combo.setCurrentIndex(
            self.transition_combo.findData(transition["kind"])
        )
        self.duration_spin.setValue(int(transition["duration_ms"]))

    def _emit_add(self) -> None:
        if not self._object_id:
            return
        target_artboard_id = str(self.target_combo.currentData() or "")
        self.connection_add_requested.emit(
            {
                "source_object_id": self._object_id,
                "trigger": str(self.trigger_combo.currentData()),
                "action": str(self.action_combo.currentData()),
                "target_artboard_id": target_artboard_id,
                "target_object_id": (
                    self._object_id
                    if str(self.action_combo.currentData())
                    in {"change_state", "change_variant"}
                    else ""
                ),
            }
        )

    def _emit_remove(self) -> None:
        row = self._selected_interaction()
        if row:
            self.connection_remove_requested.emit(str(row["id"]))

    def _emit_transition(self) -> None:
        row = self._selected_interaction()
        if row:
            self.transition_set_requested.emit(
                str(row["id"]),
                {
                    "kind": str(self.transition_combo.currentData()),
                    "duration_ms": self.duration_spin.value(),
                    "easing": "ease_out",
                },
            )

    def _emit_flow_add(self) -> None:
        if self._object_id:
            self.flow_add_requested.emit(
                {
                    "name": f"Flow {self.flow_combo.count() + 1}",
                    "artboard_id": self._document["active_artboard_id"],
                    "start_object_id": self._object_id,
                }
            )

    def _emit_flow_activate(self) -> None:
        flow_id = str(self.flow_combo.currentData() or "")
        if flow_id:
            self.flow_activate_requested.emit(flow_id)


__all__ = ["PainterUIPrototypePanel"]
