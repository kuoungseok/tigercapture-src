"""Pick-whip style property-link dialog for structured expressions."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from app.motion_designer.graph_editing import layer_graph_property
from app.motion_designer.schema import MotionComposition


class ExpressionLinkDialog(QDialog):
    def __init__(
        self,
        composition: MotionComposition,
        target_layer_id: str,
        target_property: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Property")
        self._composition = composition
        self._target_layer_id = str(target_layer_id)
        self._target_property = str(target_property)
        self._target = next(
            (
                row for row in composition.layers
                if row.id == self._target_layer_id
            ),
            None,
        )
        target_prop = (
            layer_graph_property(self._target, self._target_property)
            if self._target is not None
            else None
        )
        self._value_type = target_prop.value_type if target_prop else ""
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"{self._target.name if self._target else 'Layer'}"
            f" / {self._target_property}",
            self,
        ))
        form = QFormLayout()
        self.source_layer = QComboBox(self)
        for layer in composition.layers:
            if layer.id == self._target_layer_id:
                continue
            self.source_layer.addItem(layer.name, layer.id)
        self.source_property = QComboBox(self)
        form.addRow("Source Layer", self.source_layer)
        form.addRow("Source Property", self.source_property)
        layout.addLayout(form)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.source_layer.currentIndexChanged.connect(
            self._refresh_properties,
        )
        self._refresh_properties()

    @property
    def source_layer_id(self) -> str:
        return str(self.source_layer.currentData(Qt.ItemDataRole.UserRole) or "")

    @property
    def source_property_name(self) -> str:
        return str(
            self.source_property.currentData(Qt.ItemDataRole.UserRole) or "",
        )

    def _refresh_properties(self) -> None:
        self.source_property.clear()
        source_id = self.source_layer_id
        layer = next(
            (row for row in self._composition.layers if row.id == source_id),
            None,
        )
        if layer is None:
            self.buttons.button(
                QDialogButtonBox.StandardButton.Ok,
            ).setEnabled(False)
            return
        for name in ("position", "scale", "rotation", "opacity", "anchor"):
            prop = layer_graph_property(layer, name)
            if prop is not None and prop.value_type == self._value_type:
                self.source_property.addItem(name.title(), name)
        self.buttons.button(
            QDialogButtonBox.StandardButton.Ok,
        ).setEnabled(self.source_property.count() > 0)


__all__ = ["ExpressionLinkDialog"]
