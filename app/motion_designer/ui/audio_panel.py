"""Compact Motion Designer audio source and reactive binding panel."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from app.motion_designer.audio_analysis import AUDIO_CHANNELS, AudioAnalysisCache
from app.motion_designer.audio_reactive import AudioReactiveBinding, layer_bindings
from app.motion_designer.schema import MotionComposition, MotionLayer


class AudioEnvelopeView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.cache: AudioAnalysisCache | None = None
        self.setMinimumHeight(72)

    def set_cache(self, cache: AudioAnalysisCache | None) -> None:
        self.cache = cache
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#14171c"))
        painter.setPen(QPen(QColor("#303741"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
        if self.cache is None or not self.cache.samples:
            painter.setPen(QColor("#6f7884"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No analysis")
            return
        samples = self.cache.samples
        width = max(1, self.width() - 2)
        height = max(1, self.height() - 8)
        painter.setRenderHint(QPainter.Antialiasing, True)
        duration = max(1, self.cache.duration_ms)
        painter.setPen(QPen(QColor(211, 154, 85, 115), 1))
        last_beat_x = -4.0
        for marker in self.cache.beat_markers:
            local = marker - self.cache.timeline_start_ms
            x = 1.0 + max(0.0, min(1.0, local / duration)) * width
            if x - last_beat_x < 3.0:
                continue
            painter.drawLine(int(x), 2, int(x), self.height() - 2)
            last_beat_x = x
        path = QPainterPath()
        display_count = min(len(samples), max(2, int(width)))
        for index in range(display_count):
            start = int(index * len(samples) / display_count)
            end = max(start + 1, int((index + 1) * len(samples) / display_count))
            amplitude = sum(float(sample.amplitude) for sample in samples[start:end]) / max(1, end - start)
            x = 1.0 + index * width / max(1, display_count - 1)
            y = 4.0 + (1.0 - amplitude) * height
            if index == 0:
                path.moveTo(QPointF(x, y))
            else:
                path.lineTo(QPointF(x, y))
        painter.setPen(QPen(QColor("#62b2ca"), 1.5))
        painter.drawPath(path)


class AudioReactivePanel(QWidget):
    analyze_requested = Signal(str)
    bind_requested = Signal(object)
    bake_requested = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MotionAudioPanel")
        self._composition: MotionComposition | None = None
        self._layer: MotionLayer | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(5)

        source_tools = QHBoxLayout()
        self.open_button = QPushButton("Analyze...", self)
        self.open_button.setObjectName("MotionPrimaryButton")
        self.status = QLabel("Ready", self)
        self.status.setObjectName("MotionAudioStatus")
        source_tools.addWidget(self.open_button)
        source_tools.addWidget(self.status, 1)
        root.addLayout(source_tools)
        self.sources = QListWidget(self)
        self.sources.setMaximumHeight(88)
        root.addWidget(self.sources)
        self.envelope = AudioEnvelopeView(self)
        root.addWidget(self.envelope)

        scroll = QScrollArea(self)
        scroll.setObjectName("MotionAudioScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget(scroll)
        content.setObjectName("MotionAudioContent")
        form = QFormLayout(content)
        form.setContentsMargins(0, 2, 0, 2)
        form.setSpacing(4)
        self.channel = QComboBox(content)
        self.channel.addItems(AUDIO_CHANNELS)
        self.property_name = QComboBox(content)
        self.property_name.addItems(("scale", "position", "rotation", "opacity", "anchor"))
        self.mode = QComboBox(content)
        self.mode.addItems(("multiply", "add", "replace"))
        self.minimum = QDoubleSpinBox(content)
        self.maximum = QDoubleSpinBox(content)
        for spin in (self.minimum, self.maximum):
            spin.setRange(-10000.0, 10000.0)
            spin.setDecimals(3)
        self.minimum.setValue(1.0)
        self.maximum.setValue(1.25)
        self.smoothing = QSpinBox(content)
        self.attack = QSpinBox(content)
        self.release = QSpinBox(content)
        for spin in (self.smoothing, self.attack, self.release):
            spin.setRange(0, 5000)
            spin.setSuffix(" ms")
        self.smoothing.setValue(60)
        self.attack.setValue(30)
        self.release.setValue(140)
        self.invert = QCheckBox("Invert", content)
        form.addRow("Channel", self.channel)
        form.addRow("Property", self.property_name)
        form.addRow("Mode", self.mode)
        form.addRow("Output Min", self.minimum)
        form.addRow("Output Max", self.maximum)
        form.addRow("Smoothing", self.smoothing)
        form.addRow("Attack", self.attack)
        form.addRow("Release", self.release)
        form.addRow("", self.invert)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self.bindings = QListWidget(self)
        self.bindings.setMaximumHeight(82)
        root.addWidget(self.bindings)
        actions = QHBoxLayout()
        self.bind_button = QPushButton("Bind", self)
        self.bind_button.setObjectName("MotionPrimaryButton")
        self.bake_button = QPushButton("Bake", self)
        actions.addWidget(self.bind_button)
        actions.addWidget(self.bake_button)
        root.addLayout(actions)

        self.open_button.clicked.connect(self._choose_source)
        self.sources.currentItemChanged.connect(lambda _a, _b: self._update_envelope())
        self.bind_button.clicked.connect(self._request_bind)
        self.bake_button.clicked.connect(lambda: self.bake_requested.emit(0.0))
        self.set_layer(None)

    def set_composition(self, composition: MotionComposition) -> None:
        selected = self.current_analysis_id()
        self._composition = composition
        self.sources.clear()
        caches = composition.metadata.get("audio_analysis") or {}
        for analysis_id, row in caches.items():
            if not isinstance(row, Mapping):
                continue
            cache = AudioAnalysisCache.from_dict(row)
            item = QListWidgetItem(f"{Path(cache.source_path).name}  {cache.duration_ms / 1000.0:.1f}s")
            item.setData(Qt.UserRole, str(analysis_id))
            self.sources.addItem(item)
            if str(analysis_id) == selected:
                self.sources.setCurrentItem(item)
        if self.sources.currentItem() is None and self.sources.count():
            self.sources.setCurrentRow(0)
        self._update_envelope()

    def set_layer(self, layer: MotionLayer | None) -> None:
        self._layer = layer
        self.bindings.clear()
        for binding in layer_bindings(layer) if layer else []:
            self.bindings.addItem(f"{binding.channel} -> {binding.property_name} ({binding.mode})")
        enabled = layer is not None
        self.bind_button.setEnabled(enabled and bool(self.current_analysis_id()))
        self.bake_button.setEnabled(enabled and bool(layer_bindings(layer) if layer else []))

    def set_busy(self, busy: bool, message: str = "") -> None:
        self.open_button.setEnabled(not busy)
        self.status.setText(message or ("Analyzing..." if busy else "Ready"))

    def current_analysis_id(self) -> str:
        item = self.sources.currentItem()
        return str(item.data(Qt.UserRole) or "") if item else ""

    def select_analysis(self, analysis_id: str) -> None:
        for index in range(self.sources.count()):
            item = self.sources.item(index)
            if str(item.data(Qt.UserRole) or "") == str(analysis_id):
                self.sources.setCurrentItem(item)
                break

    def _cache(self) -> AudioAnalysisCache | None:
        if self._composition is None:
            return None
        row = (self._composition.metadata.get("audio_analysis") or {}).get(self.current_analysis_id())
        return AudioAnalysisCache.from_dict(row) if isinstance(row, Mapping) else None

    def _update_envelope(self) -> None:
        self.envelope.set_cache(self._cache())
        self.bind_button.setEnabled(self._layer is not None and bool(self.current_analysis_id()))

    def _choose_source(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Analyze audio", "",
            "Audio and Video (*.wav *.mp3 *.flac *.m4a *.aac *.ogg *.mp4 *.mov *.mkv *.webm);;All Files (*)",
        )
        if path:
            self.analyze_requested.emit(path)

    def _request_bind(self) -> None:
        analysis_id = self.current_analysis_id()
        if not analysis_id or self._layer is None:
            return
        self.bind_requested.emit({
            "analysis_id": analysis_id, "channel": self.channel.currentText(),
            "property_name": self.property_name.currentText(), "mode": self.mode.currentText(),
            "output_min": self.minimum.value(), "output_max": self.maximum.value(),
            "smoothing_ms": self.smoothing.value(), "attack_ms": self.attack.value(),
            "release_ms": self.release.value(), "invert": self.invert.isChecked(),
        })


__all__ = ["AudioEnvelopeView", "AudioReactivePanel"]
