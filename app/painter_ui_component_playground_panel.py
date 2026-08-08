"""Transient component property playground for Painter UI Design."""
from __future__ import annotations

import copy
from typing import Any, Mapping

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.painter_i18n import painter_text
from app.painter_ui_component_playground import build_ui_component_playground
from app.painter_ui_workspace import PainterUIDesignOverlay


class PainterUIComponentPlaygroundPanel(QDialog):
    """Edit preview-only component properties beside the production renderer."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PainterUIComponentPlaygroundPanel")
        self.setWindowTitle(painter_text("Component Playground"))
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.resize(780, 520)
        self._document: dict[str, Any] = {}
        self._component_id = ""
        self._property_values: dict[str, Any] = {}
        self._report: dict[str, Any] = {}
        self._controls: dict[str, QWidget] = {}
        self.setStyleSheet(
            """
            QDialog#PainterUIComponentPlaygroundPanel {
                background: #10151D;
                border: 1px solid #2C3746;
            }
            QDialog#PainterUIComponentPlaygroundPanel QLabel {
                color: #DCE5F0;
            }
            QDialog#PainterUIComponentPlaygroundPanel QLabel#PaintMuted {
                color: #97A5B7;
            }
            QFrame#PainterUIPlaygroundControls {
                background: #151C26;
                border: 1px solid #2A3442;
            }
            QScrollArea, QWidget#PainterUIPlaygroundProperties {
                background: #151C26;
                border: none;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                min-height: 25px;
                color: #DCE5F0;
                background: #0F151D;
                border: 1px solid #334154;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QCheckBox {
                color: #DCE5F0;
                spacing: 6px;
            }
            QPushButton {
                min-height: 27px;
                color: #DCE5F0;
                background: #18212C;
                border: 1px solid #334154;
                border-radius: 4px;
                padding: 2px 7px;
            }
            QPushButton:hover {
                background: #233044;
                border-color: #55739A;
            }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        title_row = QHBoxLayout()
        self.title_label = QLabel(painter_text("Component Playground"))
        self.title_label.setObjectName("PainterUIInspectorTitle")
        self.summary_label = QLabel(
            painter_text("Preview only - document is unchanged")
        )
        self.summary_label.setObjectName("PaintMuted")
        close_button = QPushButton()
        close_button.setObjectName("PainterUIInspectorIconButton")
        close_button.setIcon(app_icon("x", size=12, color="#B8C4D3"))
        close_button.setIconSize(icon_size(12))
        close_button.setToolTip(painter_text("Close"))
        close_button.clicked.connect(self.close)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.summary_label, 1)
        title_row.addWidget(close_button)
        root.addLayout(title_row)

        body = QHBoxLayout()
        body.setSpacing(6)
        self.preview = PainterUIDesignOverlay(self)
        self.preview.setEnabled(False)
        self.preview.set_rulers_visible(False)
        self.preview.set_artboard_labels_visible(False)
        body.addWidget(self.preview, 1)

        controls_frame = QFrame(self)
        controls_frame.setObjectName("PainterUIPlaygroundControls")
        controls_frame.setFixedWidth(250)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(7, 7, 7, 7)
        controls_layout.setSpacing(5)
        controls_title = QLabel(painter_text("Component Properties"))
        controls_title.setObjectName("PaintSectionTitle")
        controls_layout.addWidget(controls_title)
        scroll = QScrollArea(controls_frame)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.properties_host = QWidget(scroll)
        self.properties_host.setObjectName("PainterUIPlaygroundProperties")
        self.properties_form = QFormLayout(self.properties_host)
        self.properties_form.setContentsMargins(0, 0, 0, 0)
        self.properties_form.setSpacing(5)
        scroll.setWidget(self.properties_host)
        controls_layout.addWidget(scroll, 1)
        reset_button = QPushButton(painter_text("Reset All"))
        reset_button.clicked.connect(self._reset_values)
        controls_layout.addWidget(reset_button)
        body.addWidget(controls_frame)
        root.addLayout(body, 1)

    def set_component(
        self,
        document: Mapping[str, Any] | None,
        component_id: str,
    ) -> None:
        self._document = copy.deepcopy(dict(document or {}))
        self._component_id = str(component_id)
        _preview, report = build_ui_component_playground(
            self._document,
            component_id=self._component_id,
        )
        self._property_values = copy.deepcopy(report["property_values"])
        self._rebuild_controls(report)
        self._refresh_preview()

    def _clear_controls(self) -> None:
        while self.properties_form.rowCount():
            self.properties_form.removeRow(0)
        self._controls.clear()

    def _rebuild_controls(self, report: Mapping[str, Any]) -> None:
        self._clear_controls()
        components = {
            str(row["id"]): str(row["name"])
            for row in self._document.get("components", [])
        }
        for name, definition in report["property_definitions"].items():
            property_type = str(definition.get("type") or "text")
            value = self._property_values.get(name)
            if property_type == "boolean":
                control = QCheckBox()
                control.setChecked(bool(value))
                control.toggled.connect(
                    lambda checked, key=name: self._set_property(key, checked)
                )
            elif property_type in {"enum", "instance_swap"}:
                control = QComboBox()
                choices = (
                    list(definition.get("values") or [])
                    if property_type == "enum"
                    else [
                        *[
                            item
                            for item in definition.get("preferred_values", [])
                            if item in components
                        ],
                        *[
                            item
                            for item in components
                            if item not in definition.get("preferred_values", [])
                        ],
                    ]
                )
                for choice in choices:
                    control.addItem(
                        components.get(str(choice), str(choice)),
                        choice,
                    )
                control.setCurrentIndex(max(0, control.findData(value)))
                control.currentIndexChanged.connect(
                    lambda _index, key=name, widget=control: self._set_property(
                        key,
                        widget.currentData(),
                    )
                )
            elif property_type == "number":
                control = QDoubleSpinBox()
                control.setRange(-100000.0, 100000.0)
                control.setDecimals(2)
                control.setValue(float(value or 0.0))
                control.valueChanged.connect(
                    lambda number, key=name: self._set_property(key, number)
                )
            else:
                control = QLineEdit(str(value or ""))
                control.editingFinished.connect(
                    lambda key=name, widget=control: self._set_property(
                        key,
                        widget.text(),
                    )
                )
            self._controls[name] = control
            self.properties_form.addRow(str(name), control)

    def _set_property(self, name: str, value: Any) -> None:
        self._property_values[str(name)] = copy.deepcopy(value)
        self._refresh_preview()

    def _reset_values(self) -> None:
        self.set_component(self._document, self._component_id)

    def _refresh_preview(self) -> None:
        preview, report = build_ui_component_playground(
            self._document,
            component_id=self._component_id,
            property_values=self._property_values,
        )
        self._report = report
        self.preview.set_document(preview)
        self.title_label.setText(
            f"{painter_text('Component Playground')} · "
            f"{report['component_name']}"
        )
        QTimer.singleShot(0, self.preview.fit_artboard)

    def report(self) -> dict[str, Any]:
        return copy.deepcopy(self._report)


__all__ = ["PainterUIComponentPlaygroundPanel"]
