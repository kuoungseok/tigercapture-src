from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QTransform
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QScrollArea, QSlider,
    QSplitter, QToolButton, QVBoxLayout, QWidget,
)

from app.motion_designer.schema import MotionComposition
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

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._composition: MotionComposition | None = None
        self._selected_layer_id = ""
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
        split = QSplitter(Qt.Vertical, self)
        split.addWidget(scroll)
        split.addWidget(graph_split)
        split.setSizes([150, 115])
        split.setCollapsible(0, False)
        layout.addWidget(split, 1)
        self.tracks.time_changed.connect(self.set_time_and_emit)
        self.tracks.layer_selected.connect(self.layer_selected)
        self.tracks.layer_timing_changed.connect(self.layer_timing_changed)
        self.graph_properties.currentItemChanged.connect(lambda _a, _b: self._refresh_graph())
        self.graph_editor.keyframe_changed.connect(self._emit_keyframe_change)

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
        self.tracks.set_selected_layer(layer_id)
        self._refresh_graph()

    def _refresh_graph(self) -> None:
        prop = None
        item = self.graph_properties.currentItem()
        property_name = str(item.data(Qt.UserRole) or "position") if item else "position"
        if self._composition is not None and self._selected_layer_id:
            layer = next(
                (row for row in self._composition.layers if row.id == self._selected_layer_id),
                None,
            )
            if layer is not None:
                prop = layer.transform.properties().get(property_name)
        duration_ms = self._composition.duration_ms if self._composition is not None else 1
        self.graph_editor.set_property(prop, duration_ms=duration_ms)

    def _emit_keyframe_change(self, keyframe_id: str, time_ms: int, value: object) -> None:
        item = self.graph_properties.currentItem()
        property_name = str(item.data(Qt.UserRole) or "position") if item else "position"
        if self._selected_layer_id:
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
