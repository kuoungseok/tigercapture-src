"""Compact selection-driven Prototype authoring panel."""
from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
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
    connection_reorder_requested = Signal(str, int)
    transition_set_requested = Signal(str, object)
    flow_add_requested = Signal(object)
    flow_activate_requested = Signal(str)
    preview_changed = Signal(bool)
    preview_reset_requested = Signal()
    device_changed = Signal(object)
    background_changed = Signal(str)

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
            QWidget#PainterUIPrototypePanel QComboBox QAbstractItemView {
                background:#1E1E1E; color:#F3F3F3; border:1px solid #3C4148;
                selection-background-color:#343434; padding:6px;
                outline:0;
            }
            QWidget#PainterUIPrototypePanel QPushButton {
                min-height:24px; background:#192230; color:#DDE5EF;
                border:1px solid #303C4C; border-radius:4px; padding:1px 7px;
            }
            QWidget#PainterUIPrototypePanel QPushButton:checked {
                background:#0D78D8; color:#FFFFFF; border-color:#2494F3;
            }
            QFrame#PainterUIPrototypeSettingsHost { background:#111720; border:none; }
            QLabel#PainterUIPrototypeSettingsTitle,
            QLabel#PainterUIPrototypeInstructionTitle {
                color:#F2F5F9; font-size:12px; font-weight:650;
            }
            QComboBox#PainterUIPrototypeDeviceCombo {
                min-height:30px; padding:0 8px; font-size:11px;
            }
            QFrame#PainterUIPrototypeBackgroundRow {
                background:#20242A; border-radius:5px;
            }
            QLabel#PainterUIPrototypeBackgroundSwatch {
                background:#000000; border:1px solid #515A67; border-radius:3px;
            }
            QLineEdit#PainterUIPrototypeBackgroundEdit {
                background:transparent; color:#F2F5F9; border:none; font-size:11px;
            }
            QFrame#PainterUIPrototypeInstructionCard {
                background:transparent; border-top:1px solid #303741;
            }
            QLabel#PainterUIPrototypeInstructionBody {
                color:#C3CCD8; font-size:11px;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.settings_host = QFrame()
        self.settings_host.setObjectName("PainterUIPrototypeSettingsHost")
        settings_layout = QVBoxLayout(self.settings_host)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(8)
        settings_title = QLabel("프로토타입 설정")
        settings_title.setObjectName("PainterUIPrototypeSettingsTitle")
        settings_layout.addWidget(settings_title)
        self.device_combo = QComboBox()
        self.device_combo.setObjectName("PainterUIPrototypeDeviceCombo")
        for label, width, height, family in (
            ("기기 없음", 0, 0, "none"),
            ("iPhone 17", 402, 874, "iphone"),
            ("iPhone 17 Pro", 402, 874, "iphone"),
            ("iPhone 17 Pro Max", 440, 956, "iphone"),
            ("iPhone Air", 420, 912, "iphone"),
            ("iPhone 16", 393, 852, "iphone"),
            ("iPhone 16 Pro", 402, 874, "iphone"),
            ("iPhone 16 Pro Max", 440, 956, "iphone"),
            ("iPhone 16 Plus", 430, 932, "iphone"),
            ("iPhone 15", 393, 852, "iphone"),
            ("iPhone 15 Pro", 393, 852, "iphone"),
            ("iPhone 15 Pro Max", 430, 932, "iphone"),
            ("iPhone 15 플러스", 430, 932, "iphone"),
            ("iPhone 14 플러스", 428, 926, "iphone"),
            ("iPhone 14 Pro Max", 430, 932, "iphone"),
            ("iPhone 14 Pro", 393, 852, "iphone"),
            ("iPhone 14", 390, 844, "iphone"),
            ("Android 컴팩트", 412, 917, "android"),
            ("Android 미디엄", 700, 840, "android"),
            ("iPad mini 8.3", 744, 1133, "ipad"),
            ("iPad 11", 834, 1194, "ipad"),
            ("iPad Pro 13", 1032, 1376, "ipad"),
            ("프레젠테이션", 0, 0, "presentation"),
            ("사용자 지정", 0, 0, "custom"),
        ):
            suffix = f"    {width}×{height}" if width and height else ""
            self.device_combo.addItem(
                f"{label}{suffix}",
                {
                    "name": label,
                    "width": width,
                    "height": height,
                    "family": family,
                },
            )
        self.device_combo.setMaxVisibleItems(18)
        self.device_combo.currentIndexChanged.connect(self._emit_device)
        settings_layout.addWidget(self.device_combo)
        self.orientation_row = QWidget()
        orientation_layout = QHBoxLayout(self.orientation_row)
        orientation_layout.setContentsMargins(0, 0, 0, 0)
        orientation_layout.setSpacing(4)
        self.orientation_group = QButtonGroup(self)
        self.orientation_group.setExclusive(True)
        self.portrait_button = QPushButton("세로")
        self.landscape_button = QPushButton("가로")
        for button, value in (
            (self.portrait_button, "portrait"),
            (self.landscape_button, "landscape"),
        ):
            button.setCheckable(True)
            button.setProperty("orientation", value)
            self.orientation_group.addButton(button)
            orientation_layout.addWidget(button, 1)
            button.clicked.connect(self._emit_device)
        self.portrait_button.setChecked(True)
        self.orientation_row.hide()
        settings_layout.addWidget(self.orientation_row)
        background_row = QFrame()
        background_row.setObjectName("PainterUIPrototypeBackgroundRow")
        background_layout = QHBoxLayout(background_row)
        background_layout.setContentsMargins(6, 4, 6, 4)
        self.background_swatch = QLabel("")
        self.background_swatch.setObjectName(
            "PainterUIPrototypeBackgroundSwatch"
        )
        self.background_swatch.setFixedSize(20, 20)
        self.background_edit = QLineEdit("000000")
        self.background_edit.setObjectName(
            "PainterUIPrototypeBackgroundEdit"
        )
        self.background_edit.editingFinished.connect(
            self._emit_background
        )
        self.background_swatch.setStyleSheet(
            "background-color: #000000; border-radius: 3px;"
        )
        background_layout.addWidget(self.background_swatch)
        background_layout.addWidget(self.background_edit, 1)
        settings_layout.addWidget(background_row)
        settings_layout.addWidget(
            self._instruction_card(
                "연결 생성하기",
                "프레임 또는 프레임 내의 개체를 선택하고 연결 노드를 사용하여 다른 프레임으로 드래그합니다.",
                "link",
            )
        )
        settings_layout.addWidget(
            self._instruction_card(
                "프로토타입 실행하기",
                "툴바의 재생 메뉴에서 프레젠테이션 또는 미리보기를 실행할 수 있습니다.",
                "play",
            )
        )
        layout.addWidget(self.settings_host)

        self.authoring_host = QWidget()
        authoring_layout = QVBoxLayout(self.authoring_host)
        authoring_layout.setContentsMargins(0, 0, 0, 0)
        authoring_layout.setSpacing(4)
        layout.addWidget(self.authoring_host)
        self.status_label = QLabel("Select one UI object to add interactions")
        self.status_label.setFixedHeight(24)
        authoring_layout.addWidget(self.status_label)

        flow_row = QHBoxLayout()
        self.flow_combo = QComboBox()
        self.flow_combo.currentIndexChanged.connect(self._emit_flow_activate)
        self.flow_add_button = QPushButton("+ Flow")
        self.flow_add_button.clicked.connect(self._emit_flow_add)
        flow_row.addWidget(self.flow_combo, 1)
        flow_row.addWidget(self.flow_add_button)
        authoring_layout.addLayout(flow_row)

        preview_row = QHBoxLayout()
        self.preview_check = QCheckBox("Play")
        self.preview_check.setToolTip("Preview interactions on canvas")
        self.preview_check.toggled.connect(self.preview_changed)
        self.preview_reset_button = QPushButton("Reset")
        self.preview_reset_button.setFixedWidth(48)
        self.preview_reset_button.clicked.connect(
            self.preview_reset_requested
        )
        self.preview_state_label = QLabel("Preview is off")
        self.preview_state_label.setMinimumWidth(0)
        self.preview_state_label.setFixedHeight(24)
        self.preview_state_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        preview_row.addWidget(self.preview_check)
        preview_row.addWidget(self.preview_reset_button)
        preview_row.addWidget(self.preview_state_label, 1)
        authoring_layout.addLayout(preview_row)

        self.connection_list = QListWidget()
        self.connection_list.setFixedHeight(112)
        self.connection_list.currentItemChanged.connect(self._sync_connection)
        authoring_layout.addWidget(self.connection_list)

        connection_row = QHBoxLayout()
        self.trigger_combo = QComboBox()
        for value in sorted(UI_INTERACTION_TRIGGERS):
            self.trigger_combo.addItem(value.replace("_", " ").title(), value)
        self.action_combo = QComboBox()
        for value in sorted(UI_INTERACTION_ACTIONS):
            self.action_combo.addItem(value.replace("_", " ").title(), value)
        self.action_combo.currentIndexChanged.connect(
            self._sync_target_options
        )
        self.action_combo.currentIndexChanged.connect(
            self._sync_state_management_visibility
        )
        connection_row.addWidget(self.trigger_combo)
        connection_row.addWidget(self.action_combo)
        authoring_layout.addLayout(connection_row)

        target_row = QHBoxLayout()
        self.target_combo = QComboBox()
        self.add_button = QPushButton("Connect")
        self.add_button.clicked.connect(self._emit_add)
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self._emit_remove)
        self.move_up_button = QPushButton("↑")
        self.move_up_button.setToolTip("Move interaction earlier")
        self.move_up_button.clicked.connect(lambda: self._emit_reorder(-1))
        self.move_down_button = QPushButton("↓")
        self.move_down_button.setToolTip("Move interaction later")
        self.move_down_button.clicked.connect(lambda: self._emit_reorder(1))
        target_row.addWidget(self.target_combo, 1)
        target_row.addWidget(self.add_button)
        target_row.addWidget(self.remove_button)
        target_row.addWidget(self.move_up_button)
        target_row.addWidget(self.move_down_button)
        authoring_layout.addLayout(target_row)

        self.reset_component_state_check = QCheckBox("Reset component state")
        self.reset_component_state_check.setToolTip(
            "Reset interactive components to their original canvas variants after navigation"
        )
        self.reset_component_state_check.setVisible(False)
        authoring_layout.addWidget(self.reset_component_state_check)

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
        authoring_layout.addLayout(transition_row)

    @staticmethod
    def _instruction_card(title: str, body: str, icon_name: str) -> QFrame:
        from app.icons import app_icon, icon_size

        card = QFrame()
        card.setObjectName("PainterUIPrototypeInstructionCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(6, 7, 6, 7)
        row.setSpacing(9)
        icon = QLabel("")
        icon.setPixmap(app_icon(icon_name, size=18, color="#DDE5EF").pixmap(icon_size(18)))
        icon.setFixedSize(24, 24)
        row.addWidget(icon)
        copy_host = QWidget()
        copy_layout = QVBoxLayout(copy_host)
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(3)
        heading = QLabel(title)
        heading.setObjectName("PainterUIPrototypeInstructionTitle")
        description = QLabel(body)
        description.setObjectName("PainterUIPrototypeInstructionBody")
        description.setWordWrap(True)
        copy_layout.addWidget(heading)
        copy_layout.addWidget(description)
        row.addWidget(copy_host, 1)
        return card

    def _emit_device(self, *_args) -> None:
        value = dict(self.device_combo.currentData() or {})
        has_screen = bool(value.get("width") and value.get("height"))
        self.orientation_row.setVisible(has_screen)
        orientation = (
            "landscape" if self.landscape_button.isChecked() else "portrait"
        )
        if orientation == "landscape" and has_screen:
            value["width"], value["height"] = (
                value["height"],
                value["width"],
            )
        value["orientation"] = orientation
        self.device_changed.emit(value)

    def _emit_background(self) -> None:
        value = self.background_edit.text().strip().lstrip("#").upper()
        if len(value) not in {6, 8} or any(
            char not in "0123456789ABCDEF" for char in value
        ):
            value = "000000"
        self.background_edit.setText(value)
        self.background_swatch.setStyleSheet(
            f"background-color: #{value[:6]}; border-radius: 3px;"
        )
        self.background_changed.emit(f"#{value}")

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
        self._sync_target_options()
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
        self.settings_host.setVisible(not enabled)
        self.authoring_host.setVisible(enabled)
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

    def set_preview_state(
        self,
        state: Mapping[str, Any] | None,
        *,
        enabled: bool | None = None,
    ) -> None:
        if enabled is not None:
            self.preview_check.blockSignals(True)
            self.preview_check.setChecked(bool(enabled))
            self.preview_check.blockSignals(False)
        if not self.preview_check.isChecked():
            self.preview_state_label.setText("Preview is off")
            return
        runtime = dict(state) if isinstance(state, Mapping) else {}
        artboard_id = str(runtime.get("artboard_id") or "-")
        variables = dict(runtime.get("variables") or {})
        events = list(runtime.get("events") or [])
        last_event = (
            str(events[-1].get("action") or "")
            if events and isinstance(events[-1], Mapping)
            else ""
        )
        summary = f"{artboard_id} | {len(variables)} vars"
        if last_event:
            summary += f" | {last_event}"
        self.preview_state_label.setText(summary)
        self.preview_state_label.setToolTip(
            f"Current artboard: {artboard_id}\n"
            f"Variables: {variables}\n"
            f"Last event: {last_event or '-'}"
        )

    def _selected_interaction(self) -> dict[str, Any]:
        item = self.connection_list.currentItem()
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else {}
        return dict(value) if isinstance(value, Mapping) else {}

    def _sync_connection(self, current, _previous=None) -> None:
        row = self._selected_interaction()
        enabled = bool(row)
        self.remove_button.setEnabled(enabled)
        self.move_up_button.setEnabled(enabled)
        self.move_down_button.setEnabled(enabled)
        self.transition_button.setEnabled(enabled)
        if not row:
            return
        self.trigger_combo.setCurrentIndex(
            max(0, self.trigger_combo.findData(row["trigger"]))
        )
        self.action_combo.setCurrentIndex(
            max(0, self.action_combo.findData(row["action"]))
        )
        self._sync_target_options()
        target_id = (
            str(row.get("component_id") or "")
            if row["action"] == "change_variant"
            else str(row.get("target_artboard_id") or "")
        )
        self.target_combo.setCurrentIndex(
            max(0, self.target_combo.findData(target_id))
        )
        transition = row["transition"]
        self.transition_combo.setCurrentIndex(
            self.transition_combo.findData(transition["kind"])
        )
        self.duration_spin.setValue(int(transition["duration_ms"]))
        self.reset_component_state_check.setChecked(
            bool((row.get("parameters") or {}).get("reset_component_state", False))
        )

    def _emit_add(self) -> None:
        if not self._object_id:
            return
        action = str(self.action_combo.currentData())
        target_id = str(self.target_combo.currentData() or "")
        parameters = (
            {"preserve_overrides": True}
            if action == "change_variant"
            else {}
        )
        if self.reset_component_state_check.isVisible() and (
            self.reset_component_state_check.isChecked()
        ):
            parameters["reset_component_state"] = True
        self.connection_add_requested.emit(
            {
                "source_object_id": self._object_id,
                "trigger": str(self.trigger_combo.currentData()),
                "action": action,
                "target_artboard_id": (
                    "" if action == "change_variant" else target_id
                ),
                "target_object_id": (
                    self._object_id
                    if action in {"change_state", "change_variant"}
                    else ""
                ),
                "component_id": target_id if action == "change_variant" else "",
                "parameters": parameters,
            }
        )

    def _sync_state_management_visibility(self, *_args) -> None:
        action = str(self.action_combo.currentData() or "")
        visible = action in {
            "navigate",
            "back",
            "open_overlay",
            "close_overlay",
            "swap_overlay",
        }
        self.reset_component_state_check.setVisible(visible)
        if not visible:
            self.reset_component_state_check.setChecked(False)

    def _sync_target_options(self, *_args) -> None:
        current = self.target_combo.currentData()
        self.target_combo.clear()
        if str(self.action_combo.currentData() or "") != "change_variant":
            for artboard in self._document.get("artboards", []):
                self.target_combo.addItem(artboard["name"], artboard["id"])
        else:
            selected = next(
                (
                    row
                    for row in self._document.get("objects", [])
                    if row["id"] == self._object_id
                ),
                None,
            )
            component_id = str((selected or {}).get("component_id") or "")
            components = {
                str(row["id"]): row
                for row in self._document.get("components", [])
            }
            component = components.get(component_id)
            family_id = str(
                (component or {}).get("base_component_id")
                or component_id
            )
            family = components.get(family_id)
            family_ids = (
                [family_id, *family.get("variant_ids", [])]
                if family is not None
                else []
            )
            for candidate_id in family_ids:
                candidate = components.get(str(candidate_id))
                if candidate is None or candidate_id == component_id:
                    continue
                metadata = candidate.get("metadata")
                metadata = metadata if isinstance(metadata, Mapping) else {}
                variant_properties = metadata.get("variant_properties")
                if isinstance(variant_properties, Mapping) and variant_properties:
                    label = ", ".join(
                        f"{name}={value}"
                        for name, value in variant_properties.items()
                    )
                else:
                    label = str(candidate["name"])
                self.target_combo.addItem(label, candidate_id)
        index = self.target_combo.findData(current)
        if index >= 0:
            self.target_combo.setCurrentIndex(index)
        enabled = bool(self._object_id and self.target_combo.count())
        self.target_combo.setEnabled(enabled)
        self.add_button.setEnabled(enabled)

    def _emit_remove(self) -> None:
        row = self._selected_interaction()
        if row:
            self.connection_remove_requested.emit(str(row["id"]))

    def _emit_reorder(self, direction: int) -> None:
        row = self._selected_interaction()
        if row:
            self.connection_reorder_requested.emit(
                str(row["id"]),
                int(direction),
            )

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
