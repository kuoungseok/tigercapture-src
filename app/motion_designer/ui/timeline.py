from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSlider, QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from app.motion_designer.schema import AnimatedProperty, MotionComposition
from app.icons import app_icon

from .graph_editor import GraphEditor
from .timeline_tracks import LayerTimelineView


class MotionTimeline(QWidget):
    time_changed = Signal(int)
    play_toggled = Signal(bool)
    playback_requested = Signal(int)
    loop_changed = Signal(bool)
    layer_selected = Signal(str)
    layer_timing_changed = Signal(str, int, int)
    keyframe_changed = Signal(str, str, str, int, object)
    rig_keyframe_changed = Signal(str, str, str, str, int, object)
    puppet_keyframe_changed = Signal(str, str, str, str, int, object)
    keyframe_tangent_requested = Signal(str, str, str, str)
    keyframe_spatial_tangent_requested = Signal(str, str, str, str)
    keyframe_roving_requested = Signal(str, str, str)
    keyframe_tangent_value_requested = Signal(
        str, str, str, str, object,
    )
    expression_link_requested = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._composition: MotionComposition | None = None
        self._selected_layer_id = ""
        self._selected_rig_id = ""
        self._selected_bone_id = ""
        self._selected_puppet_pin_id = ""
        self._selected_graph_keyframe_id = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 4)
        transport = QHBoxLayout()
        transport.setSpacing(5)
        transport_controls = QWidget(self)
        transport_controls.setObjectName("MotionTransport")
        transport_buttons = QHBoxLayout(transport_controls)
        transport_buttons.setContentsMargins(3, 2, 3, 2)
        transport_buttons.setSpacing(1)
        self.to_start = QToolButton(self)
        self._prepare_transport_button(self.to_start, app_icon("previous", size=16), "Go to start")
        self.to_start.setToolTip("Go to start")
        self.reverse_button = QToolButton(self)
        self._prepare_transport_button(
            self.reverse_button, self._reverse_icon(), "Reverse playback (J)", checkable=True,
        )
        self.reverse_button.setShortcut("J")
        self.stop_button = QToolButton(self)
        self._prepare_transport_button(self.stop_button, app_icon("stop", size=15), "Stop (K)")
        self.stop_button.setShortcut("K")
        self.play_button = QToolButton(self)
        self._prepare_transport_button(
            self.play_button, app_icon("play", size=16), "Play / pause (L)", checkable=True,
        )
        self.play_button.setShortcut("L")
        self.loop_button = QToolButton(self)
        self._prepare_transport_button(
            self.loop_button, app_icon("repeat", size=16), "Loop playback (Ctrl+L)", checkable=True,
        )
        self.loop_button.setShortcut("Ctrl+L")
        self.to_end = QToolButton(self)
        self._prepare_transport_button(self.to_end, app_icon("next", size=16), "Go to end")
        self.time_label = QLabel("00:00.000")
        self.time_label.setObjectName("MotionTimecode")
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.valueChanged.connect(self._time)
        self.play_button.toggled.connect(self._play)
        self.reverse_button.toggled.connect(self._reverse)
        self.stop_button.clicked.connect(lambda: self.set_playback_direction(0, emit=True))
        self.loop_button.toggled.connect(self.loop_changed)
        self.to_start.clicked.connect(lambda: self.set_time_and_emit(0))
        self.to_end.clicked.connect(lambda: self.set_time_and_emit(self.slider.maximum()))
        for button in (
            self.to_start, self.reverse_button, self.stop_button,
            self.play_button, self.loop_button, self.to_end,
        ):
            transport_buttons.addWidget(button)
        transport.addWidget(transport_controls)
        transport.addWidget(self.time_label)
        transport.addWidget(self.slider, 1)
        layout.addLayout(transport)

        self.tracks = LayerTimelineView(self)
        self.dope_sheet = self.tracks
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.tracks)
        self.graph_properties = QListWidget(self)
        self.graph_properties.setObjectName("MotionGraphProperties")
        self.graph_properties.setFixedWidth(LayerTimelineView.LABEL_WIDTH)
        for key, label in (
            ("position", "Position"), ("scale", "Scale"),
            ("rotation", "Rotation"), ("opacity", "Opacity"),
            ("anchor", "Anchor Point"),
            ("time_remap", "Source Time"),
            ("source:tilt_x", "Image Tilt X"),
            ("source:tilt_y", "Image Tilt Y"),
            ("source:perspective", "Image Perspective"),
            ("rig:rotation", "Bone Rotation"),
            ("rig:translation", "Bone Translation"),
            ("puppet:position", "Pin Position"),
            ("puppet:rotation", "Pin Bend"),
        ):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.graph_properties.addItem(item)
        self.graph_properties.setCurrentRow(0)
        self.graph_editor = GraphEditor(self)
        graph_split = QSplitter(Qt.Horizontal, self)
        graph_split.addWidget(self.graph_properties)
        graph_split.addWidget(self.graph_editor)
        graph_split.setSizes([LayerTimelineView.LABEL_WIDTH, 700])
        graph_split.setCollapsible(0, False)
        graph_container = QWidget(self)
        graph_layout = QVBoxLayout(graph_container)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(2)
        graph_controls = QHBoxLayout()
        self.graph_mode = QComboBox(self)
        self.graph_mode.addItems(["Value", "Speed"])
        graph_controls.addWidget(self.graph_mode)
        for label, mode in (
            ("Auto", "standard_auto"),
            ("Continuous", "continuous"),
            ("Broken", "broken"),
            ("Tiger Smooth", "tiger_smooth"),
            ("Linear", "linear"),
            ("Hold", "hold"),
        ):
            button = QPushButton(label, self)
            if mode == "tiger_smooth":
                button.setToolTip(
                    "Legacy Tiger temporal Bezier preset retained for old projects."
                )
            elif mode == "standard_auto":
                button.setToolTip(
                    "Neighbor-derived monotone temporal tangent using adjacent key times and values."
                )
            button.clicked.connect(
                lambda _checked=False, value=mode: self._request_tangent(value),
            )
            graph_controls.addWidget(button)
        for label, mode in (
            ("Path Auto", "auto"),
            ("Path Continuous", "continuous"),
            ("Path Broken", "broken"),
        ):
            button = QPushButton(label, self)
            button.setToolTip(
                "Edit Position's spatial Bezier path independently of temporal easing."
            )
            button.clicked.connect(
                lambda _checked=False, value=mode: self._request_spatial_tangent(value),
            )
            graph_controls.addWidget(button)
        rove = QPushButton("Rove", self)
        rove.clicked.connect(self._request_roving)
        graph_controls.addWidget(rove)
        link = QPushButton("Link...", self)
        link.setToolTip("Pick-whip this property to another layer property")
        link.clicked.connect(self._request_expression_link)
        graph_controls.addWidget(link)
        graph_controls.addStretch(1)
        graph_layout.addLayout(graph_controls)
        graph_layout.addWidget(graph_split, 1)
        split = QSplitter(Qt.Vertical, self)
        split.addWidget(scroll)
        split.addWidget(graph_container)
        split.setSizes([150, 115])
        split.setCollapsible(0, False)
        layout.addWidget(split, 1)
        self.tracks.time_changed.connect(self.set_time_and_emit)
        self.tracks.layer_selected.connect(self.layer_selected)
        self.tracks.layer_timing_changed.connect(self.layer_timing_changed)
        self.graph_properties.currentItemChanged.connect(lambda _a, _b: self._refresh_graph())
        self.graph_editor.keyframe_changed.connect(self._emit_keyframe_change)
        self.graph_editor.keyframe_selected.connect(self._select_graph_keyframe)
        self.graph_editor.tangent_changed.connect(self._emit_tangent_change)
        self.graph_mode.currentTextChanged.connect(self.graph_editor.set_mode)

    @staticmethod
    def _prepare_transport_button(
        button: QToolButton, icon: QIcon, tooltip: str, *, checkable: bool = False,
    ) -> None:
        button.setObjectName("MotionTransportButton")
        button.setIcon(icon)
        button.setIconSize(QSize(16, 16))
        button.setFixedSize(27, 25)
        button.setCheckable(checkable)
        button.setToolTip(tooltip)
        button.setCursor(Qt.PointingHandCursor)

    @staticmethod
    def _reverse_icon() -> QIcon:
        pixmap = app_icon("play", size=16).pixmap(16, 16)
        return QIcon(pixmap.transformed(QTransform().scale(-1.0, 1.0)))

    def set_duration(self, duration_ms: int) -> None:
        self.slider.setRange(0, max(1, int(duration_ms)))

    def set_composition(self, composition: MotionComposition, time_ms: int = 0) -> None:
        self._composition = composition
        self.set_duration(composition.duration_ms)
        self.tracks.set_state(composition, time_ms)
        self._refresh_graph()

    def set_selected_layer(self, layer_id: str) -> None:
        self._selected_layer_id = str(layer_id or "")
        self._selected_rig_id = ""
        self._selected_bone_id = ""
        self._selected_puppet_pin_id = ""
        self.tracks.set_selected_layer(layer_id)
        self._refresh_graph()

    def set_selected_rig_bone(self, rig_id: str, bone_id: str) -> None:
        self._selected_rig_id = str(rig_id or "")
        self._selected_bone_id = str(bone_id or "")
        target = "rig:rotation"
        for index in range(self.graph_properties.count()):
            item = self.graph_properties.item(index)
            if str(item.data(Qt.UserRole) or "") == target:
                self.graph_properties.setCurrentItem(item)
                break
        self._refresh_graph()

    def set_selected_puppet_pin(self, layer_id: str, pin_id: str) -> None:
        self._selected_layer_id = str(layer_id or "")
        self._selected_rig_id = ""
        self._selected_bone_id = ""
        self._selected_puppet_pin_id = str(pin_id or "")
        for index in range(self.graph_properties.count()):
            item = self.graph_properties.item(index)
            if str(item.data(Qt.UserRole) or "") == "puppet:position":
                self.graph_properties.setCurrentItem(item)
                break
        self._refresh_graph()

    def _refresh_graph(self) -> None:
        prop = None
        item = self.graph_properties.currentItem()
        property_name = str(item.data(Qt.UserRole) or "position") if item else "position"
        if (
            self._composition is not None
            and property_name.startswith("puppet:")
            and self._selected_layer_id
            and self._selected_puppet_pin_id
        ):
            from app.motion_designer.puppet_mesh import layer_puppet_mesh

            layer = next(
                (
                    row
                    for row in self._composition.layers
                    if row.id == self._selected_layer_id
                ),
                None,
            )
            mesh = layer_puppet_mesh(layer) if layer is not None else None
            pin = next(
                (
                    row
                    for row in mesh.pins
                    if row.id == self._selected_puppet_pin_id
                ),
                None,
            ) if mesh is not None else None
            if pin is not None:
                prop = (
                    pin.position
                    if property_name == "puppet:position"
                    else pin.rotation
                )
        elif (
            self._composition is not None
            and property_name.startswith("rig:")
            and self._selected_rig_id
            and self._selected_bone_id
        ):
            from app.motion_designer.rigging import composition_rigs

            rig = next(
                (
                    row
                    for row in composition_rigs(self._composition)
                    if row.id == self._selected_rig_id
                ),
                None,
            )
            bone = next(
                (
                    row
                    for row in rig.bones
                    if row.id == self._selected_bone_id
                ),
                None,
            ) if rig is not None else None
            if bone is not None:
                prop = (
                    bone.rotation
                    if property_name == "rig:rotation"
                    else bone.translation
                )
        elif self._composition is not None and self._selected_layer_id:
            layer = next(
                (row for row in self._composition.layers if row.id == self._selected_layer_id),
                None,
            )
            if layer is not None:
                if property_name == "time_remap":
                    from app.motion_designer.time_remap import layer_time_remap

                    prop = layer_time_remap(layer)
                elif property_name.startswith("source:") and layer.layer_type == "image":
                    source_name = property_name.split(":", 1)[1]
                    current = layer.source.params.get(source_name)
                    if isinstance(current, dict) and (
                        "default" in current or "keyframes" in current
                    ):
                        prop = AnimatedProperty.from_dict(current)
                else:
                    prop = layer.transform.properties().get(property_name)
        duration_ms = self._composition.duration_ms if self._composition is not None else 1
        self.graph_editor.set_property(prop, duration_ms=duration_ms)

    def _select_graph_keyframe(self, keyframe_id: str) -> None:
        self._selected_graph_keyframe_id = str(keyframe_id or "")

    def _request_tangent(self, mode: str) -> None:
        item = self.graph_properties.currentItem()
        property_name = (
            str(item.data(Qt.UserRole) or "position")
            if item is not None
            else "position"
        )
        if (
            self._selected_layer_id
            and self._selected_graph_keyframe_id
            and not property_name.startswith(("rig:", "puppet:"))
        ):
            self.keyframe_tangent_requested.emit(
                self._selected_layer_id,
                property_name,
                self._selected_graph_keyframe_id,
                str(mode),
            )

    def _request_roving(self) -> None:
        item = self.graph_properties.currentItem()
        property_name = (
            str(item.data(Qt.UserRole) or "position")
            if item is not None
            else "position"
        )
        if (
            self._selected_layer_id
            and self._selected_graph_keyframe_id
            and not property_name.startswith(("rig:", "puppet:"))
        ):
            self.keyframe_roving_requested.emit(
                self._selected_layer_id,
                property_name,
                self._selected_graph_keyframe_id,
            )

    def _request_spatial_tangent(self, mode: str) -> None:
        item = self.graph_properties.currentItem()
        property_name = (
            str(item.data(Qt.UserRole) or "position")
            if item is not None
            else "position"
        )
        if (
            self._selected_layer_id
            and self._selected_graph_keyframe_id
            and property_name == "position"
        ):
            self.keyframe_spatial_tangent_requested.emit(
                self._selected_layer_id,
                property_name,
                self._selected_graph_keyframe_id,
                str(mode),
            )

    def _emit_tangent_change(
        self,
        keyframe_id: str,
        side: str,
        value: object,
    ) -> None:
        item = self.graph_properties.currentItem()
        property_name = (
            str(item.data(Qt.UserRole) or "position")
            if item is not None
            else "position"
        )
        if (
            self._selected_layer_id
            and not property_name.startswith(("rig:", "puppet:"))
        ):
            self.keyframe_tangent_value_requested.emit(
                self._selected_layer_id,
                property_name,
                str(keyframe_id),
                str(side),
                value,
            )

    def _request_expression_link(self) -> None:
        item = self.graph_properties.currentItem()
        property_name = (
            str(item.data(Qt.UserRole) or "position")
            if item is not None
            else "position"
        )
        if (
            self._selected_layer_id
            and property_name in {
                "position", "scale", "rotation", "opacity", "anchor",
            }
        ):
            self.expression_link_requested.emit(
                self._selected_layer_id,
                property_name,
            )

    def _emit_keyframe_change(self, keyframe_id: str, time_ms: int, value: object) -> None:
        item = self.graph_properties.currentItem()
        property_name = str(item.data(Qt.UserRole) or "position") if item else "position"
        if (
            property_name.startswith("puppet:")
            and self._selected_layer_id
            and self._selected_puppet_pin_id
        ):
            self.puppet_keyframe_changed.emit(
                self._selected_layer_id,
                self._selected_puppet_pin_id,
                property_name.split(":", 1)[1],
                keyframe_id,
                int(time_ms),
                value,
            )
        elif (
            property_name.startswith("rig:")
            and self._selected_rig_id
            and self._selected_bone_id
        ):
            self.rig_keyframe_changed.emit(
                self._selected_rig_id,
                self._selected_bone_id,
                property_name.split(":", 1)[1],
                keyframe_id,
                int(time_ms),
                value,
            )
        elif self._selected_layer_id:
            self.keyframe_changed.emit(
                self._selected_layer_id, property_name, keyframe_id, int(time_ms), value,
            )

    def set_time(self, time_ms: int) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(int(time_ms))
        self.slider.blockSignals(False)
        self._update_label(int(time_ms))
        if self._composition is not None:
            self.tracks.set_state(self._composition, int(time_ms))

    def set_time_and_emit(self, time_ms: int) -> None:
        self.set_time(int(time_ms))
        self.time_changed.emit(int(time_ms))

    def _time(self, value: int) -> None:
        self.set_time(value)
        self.time_changed.emit(value)

    def _play(self, checked: bool) -> None:
        if self.play_button.signalsBlocked():
            return
        self.set_playback_direction(1 if checked else 0, emit=True)

    def _reverse(self, checked: bool) -> None:
        if self.reverse_button.signalsBlocked():
            return
        self.set_playback_direction(-1 if checked else 0, emit=True)

    def set_playback_direction(self, direction: int, *, emit: bool = False) -> None:
        direction = -1 if int(direction) < 0 else (1 if int(direction) > 0 else 0)
        for button, checked in (
            (self.reverse_button, direction < 0),
            (self.play_button, direction > 0),
        ):
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)
        self.play_button.setIcon(app_icon("pause" if direction > 0 else "play", size=16))
        self.play_button.setToolTip("Pause (K)" if direction > 0 else "Play / pause (L)")
        self.reverse_button.setToolTip("Pause reverse playback (K)" if direction < 0 else "Reverse playback (J)")
        if emit:
            self.playback_requested.emit(direction)
            self.play_toggled.emit(direction != 0)

    def set_loop_enabled(self, enabled: bool) -> None:
        self.loop_button.blockSignals(True)
        self.loop_button.setChecked(bool(enabled))
        self.loop_button.blockSignals(False)

    def _update_label(self, value: int) -> None:
        seconds, millis = divmod(max(0, int(value)), 1000)
        minutes, seconds = divmod(seconds, 60)
        self.time_label.setText(f"{minutes:02d}:{seconds:02d}.{millis:03d}")
