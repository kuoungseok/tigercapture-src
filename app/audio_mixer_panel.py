"""Audio track mixer panel — fader + pan knob + VU meter per track."""
from __future__ import annotations

import math

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class VUMeter(QWidget):
    """Vertical stereo VU meter with peak hold."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24)
        self.setMinimumHeight(80)
        self._level_l = 0.0   # 0.0–1.0 RMS
        self._level_r = 0.0
        self._peak_l = 0.0
        self._peak_r = 0.0
        self._peak_hold = 30  # frames before decay
        self._peak_timer_l = 0
        self._peak_timer_r = 0

    def set_levels(self, left: float, right: float) -> None:
        self._level_l = max(0.0, min(1.0, left))
        self._level_r = max(0.0, min(1.0, right))
        if self._level_l >= self._peak_l:
            self._peak_l = self._level_l
            self._peak_timer_l = self._peak_hold
        elif self._peak_timer_l > 0:
            self._peak_timer_l -= 1
        else:
            self._peak_l = max(self._level_l, self._peak_l * 0.95)
        if self._level_r >= self._peak_r:
            self._peak_r = self._level_r
            self._peak_timer_r = self._peak_hold
        elif self._peak_timer_r > 0:
            self._peak_timer_r -= 1
        else:
            self._peak_r = max(self._level_r, self._peak_r * 0.95)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        bar_w = (w - 3) // 2

        for i, (level, peak) in enumerate([(self._level_l, self._peak_l),
                                            (self._level_r, self._peak_r)]):
            x = i * (bar_w + 1)
            # Background
            p.fillRect(x, 0, bar_w, h, QColor("#1a1a1a"))
            # Level bar: green -> yellow -> red
            bar_h = int(level * h)
            if bar_h > 0:
                grad = QLinearGradient(0, h - bar_h, 0, h)
                grad.setColorAt(0.0, QColor("#ff2020"))  # top = red
                grad.setColorAt(0.3, QColor("#ffcc00"))  # yellow
                grad.setColorAt(1.0, QColor("#00cc44"))  # bottom = green
                p.fillRect(x, h - bar_h, bar_w, bar_h, grad)
            # Peak line
            peak_y = int((1.0 - peak) * h)
            p.setPen(QPen(QColor("#ffffff"), 1))
            p.drawLine(x, peak_y, x + bar_w - 1, peak_y)
        p.end()


class ChannelStrip(QWidget):
    """One channel strip: label + VU meter + fader + pan."""

    volume_changed = Signal(int, float)   # track_id, volume 0.0–1.5
    pan_changed = Signal(int, float)      # track_id, pan -1.0–1.0

    def __init__(self, track_id: int, track_name: str, parent=None):
        super().__init__(parent)
        self.track_id = track_id
        self.setFixedWidth(64)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        # Label
        lbl = QLabel(track_name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size:9px; color:#aaa;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # VU meter
        self.vu = VUMeter()
        layout.addWidget(self.vu)

        # Pan slider (-100..100 -> -1.0..1.0)
        pan_lbl = QLabel("PAN")
        pan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pan_lbl.setStyleSheet("font-size:8px; color:#888;")
        layout.addWidget(pan_lbl)
        self.pan_slider = QSlider(Qt.Orientation.Horizontal)
        self.pan_slider.setRange(-100, 100)
        self.pan_slider.setValue(0)
        self.pan_slider.setFixedHeight(14)
        self.pan_slider.valueChanged.connect(
            lambda v: self.pan_changed.emit(self.track_id, v / 100.0)
        )
        layout.addWidget(self.pan_slider)

        # Volume fader (0..150 -> 0.0..1.5)
        fader_lbl = QLabel("VOL")
        fader_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fader_lbl.setStyleSheet("font-size:8px; color:#888;")
        layout.addWidget(fader_lbl)
        self.fader = QSlider(Qt.Orientation.Vertical)
        self.fader.setRange(0, 150)
        self.fader.setValue(100)
        self.fader.setMinimumHeight(60)
        self.fader.valueChanged.connect(
            lambda v: self.volume_changed.emit(self.track_id, v / 100.0)
        )
        layout.addWidget(self.fader)

        # dB label
        self.db_lbl = QLabel("0 dB")
        self.db_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_lbl.setStyleSheet("font-size:8px; color:#aaa;")
        layout.addWidget(self.db_lbl)
        self.fader.valueChanged.connect(self._update_db_label)

    def _update_db_label(self, v: int):
        vol = v / 100.0
        if vol <= 0:
            db_str = "-inf"
        else:
            db = 20 * math.log10(max(vol, 1e-6))
            db_str = f"{db:+.1f}"
        self.db_lbl.setText(f"{db_str} dB")

    def set_volume(self, vol: float):
        self.fader.blockSignals(True)
        self.fader.setValue(int(vol * 100))
        self.fader.blockSignals(False)
        self._update_db_label(int(vol * 100))

    def set_pan(self, pan: float):
        self.pan_slider.blockSignals(True)
        self.pan_slider.setValue(int(pan * 100))
        self.pan_slider.blockSignals(False)


class LUFSMeter(QWidget):
    """Real-time integrated LUFS display (BS.1770-4 simplified)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self._lufs = -70.0
        self._short_term = -70.0
        self._target = -14.0  # YouTube target
        self._samples: list[float] = []

    def push_audio_chunk(self, pcm: np.ndarray, sample_rate: int = 48000) -> None:
        """Push a chunk of PCM float32 audio [-1,1] for LUFS calculation."""
        if pcm.ndim == 1:
            pcm = pcm[:, None]
        # K-weighting: simplified (just RMS as approximation)
        rms = float(np.sqrt(np.mean(pcm ** 2) + 1e-10))
        lufs = 20 * math.log10(rms) - 0.691  # approximate BS.1770
        self._samples.append(lufs)
        if len(self._samples) > 300:
            self._samples.pop(0)
        self._short_term = float(np.mean(sorted(self._samples)[-100:])) if self._samples else -70
        self._lufs = float(np.mean(self._samples)) if self._samples else -70
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#1a1a1a"))

        # Draw integrated LUFS
        lufs_str = f"I: {max(-70, self._lufs):.1f} LUFS"
        st_str = f"S: {max(-70, self._short_term):.1f} LUFS"
        target_str = f"Target: {self._target:.0f}"

        p.setPen(QColor("#00cc44"))
        p.drawText(4, 14, lufs_str)
        p.setPen(QColor("#ffcc00"))
        p.drawText(4, 28, st_str)
        p.setPen(QColor("#888888"))
        p.drawText(w - 80, 14, target_str)

        # Indicator bar
        lufs_norm = max(0.0, min(1.0, (self._short_term + 60) / 60.0))
        bar_w = int(lufs_norm * (w - 8))
        bar_color = QColor("#00cc44") if self._short_term > -18 else QColor("#ffcc00")
        p.fillRect(4, 32, bar_w, 4, bar_color)
        p.end()


class AudioMixerPanel(QWidget):
    """Horizontal row of channel strips, one per audio track."""

    volume_changed = Signal(int, float)
    pan_changed = Signal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        title = QLabel("AUDIO MIXER")
        title.setStyleSheet(
            "font-size:10px; font-weight:bold; color:#ccc; padding:4px;"
        )
        outer.addWidget(title)

        # LUFS meter below title
        self._lufs_meter = LUFSMeter()
        outer.addWidget(self._lufs_meter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        self._strip_container = QWidget()
        self._strips_layout = QHBoxLayout(self._strip_container)
        self._strips_layout.setContentsMargins(4, 0, 4, 0)
        self._strips_layout.setSpacing(2)
        self._strips_layout.addStretch()
        scroll.setWidget(self._strip_container)

        self._strips: dict[int, ChannelStrip] = {}

        # Refresh VU meters at ~30fps
        self._vu_timer = QTimer(self)
        self._vu_timer.setInterval(33)
        self._vu_timer.timeout.connect(self._decay_vu)
        self._vu_timer.start()

    def refresh_tracks(self, audio_tracks: list) -> None:
        """Rebuild strips to match the current audio track list."""
        track_ids = {t.id for t in audio_tracks}
        # Remove strips for deleted tracks
        for tid in list(self._strips.keys()):
            if tid not in track_ids:
                strip = self._strips.pop(tid)
                self._strips_layout.removeWidget(strip)
                strip.deleteLater()
        # Add strips for new tracks
        for t in audio_tracks:
            if t.id not in self._strips:
                name = getattr(t, "label", "") or f"A{t.id}"
                strip = ChannelStrip(t.id, name)
                strip.volume_changed.connect(self.volume_changed)
                strip.pan_changed.connect(self.pan_changed)
                # Insert before the stretch
                idx = self._strips_layout.count() - 1
                self._strips_layout.insertWidget(idx, strip)
                self._strips[t.id] = strip
            # Sync current volume/pan
            strip = self._strips[t.id]
            strip.set_volume(float(getattr(t, "volume", 1.0)))
            strip.set_pan(float(getattr(t, "pan", 0.0)))

    def update_levels(self, track_id: int, left: float, right: float) -> None:
        if track_id in self._strips:
            self._strips[track_id].vu.set_levels(left, right)

    def push_lufs_chunk(self, pcm: np.ndarray, sample_rate: int = 48000) -> None:
        """Forward a PCM chunk to the integrated LUFS meter."""
        self._lufs_meter.push_audio_chunk(pcm, sample_rate)

    def _decay_vu(self) -> None:
        for strip in self._strips.values():
            strip.vu.set_levels(
                strip.vu._level_l * 0.85,
                strip.vu._level_r * 0.85,
            )
