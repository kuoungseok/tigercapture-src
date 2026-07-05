"""Audio track mixer panel — fader + pan knob + VU meter per track."""
from __future__ import annotations

import math

import numpy as np

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QRegion
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.studio_slider import StudioSlider
from app.style import editor_scrollbar_qss
from app.ux_feedback import apply_state_to_label, audio_mixer_empty_state


class VUMeter(QWidget):
    """Vertical stereo VU meter with peak hold."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(20)
        self.setMinimumHeight(64)
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
            p.fillRect(x, 0, bar_w, h, QColor("#111316"))
            # Level bar: green -> yellow -> red
            bar_h = int(level * h)
            if bar_h > 0:
                grad = QLinearGradient(0, h - bar_h, 0, h)
                grad.setColorAt(0.0, QColor("#B65A52"))  # top = red
                grad.setColorAt(0.3, QColor("#B8A46B"))  # yellow
                grad.setColorAt(1.0, QColor("#6A9A82"))  # bottom = green
                p.fillRect(x, h - bar_h, bar_w, bar_h, grad)
            # Peak line
            peak_y = int((1.0 - peak) * h)
            p.setPen(QPen(QColor("#D8DEE8"), 1))
            p.drawLine(x, peak_y, x + bar_w - 1, peak_y)
        p.end()


class ChannelStrip(QWidget):
    """One channel strip: label + VU meter + fader + pan."""

    volume_changed = Signal(int, float)   # track_id, volume 0.0–1.5
    pan_changed = Signal(int, float)      # track_id, pan -1.0–1.0

    def __init__(self, track_id: int, track_name: str, parent=None):
        super().__init__(parent)
        self.track_id = track_id
        self.setObjectName("MixerChannelStrip")
        self.setStyleSheet(
            "QWidget#MixerChannelStrip {"
            "background:#15181D; border:1px solid #2B3037; border-radius:5px;"
            "}"
            "QSlider::groove:vertical {"
            "background:#252A31; width:3px; border-radius:2px;"
            "}"
            "QSlider::add-page:vertical {"
            "background:#6F7B8C; border-radius:2px; }"
            "QSlider::sub-page:vertical { background:#252A31; border-radius:2px; }"
            "QSlider::handle:vertical {"
            "background:#DCE2EA; border:1px solid #596474; width:12px;"
            "height:12px; margin:0 -5px; border-radius:6px;"
            "}"
            "QSlider::groove:horizontal {"
            "background:#252A31; height:3px; border-radius:2px;"
            "}"
            "QSlider::sub-page:horizontal {"
            "background:#6F7B8C; border-radius:2px;"
            "}"
            "QSlider::handle:horizontal {"
            "background:#DCE2EA; border:1px solid #596474; width:10px;"
            "height:10px; margin:-4px 0; border-radius:5px;"
            "}"
        )
        self.setFixedWidth(64)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(2)

        # Label
        lbl = QLabel(track_name)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size:9px; color:#B8C0CA; font-weight:600;")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # VU meter
        self.vu = VUMeter()
        layout.addWidget(self.vu)

        # Pan slider (-100..100 -> -1.0..1.0)
        pan_lbl = QLabel("PAN")
        pan_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pan_lbl.setStyleSheet("font-size:8px; color:#858D98;")
        layout.addWidget(pan_lbl)
        self.pan_slider = StudioSlider("audio")
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
        fader_lbl.setStyleSheet("font-size:8px; color:#858D98;")
        layout.addWidget(fader_lbl)
        self.fader = QSlider(Qt.Orientation.Vertical)
        self.fader.setRange(0, 150)
        self.fader.setValue(100)
        self.fader.setMinimumHeight(48)
        self.fader.valueChanged.connect(
            lambda v: self.volume_changed.emit(self.track_id, v / 100.0)
        )
        layout.addWidget(self.fader)

        # dB label
        self.db_lbl = QLabel("0 dB")
        self.db_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.db_lbl.setStyleSheet("font-size:8px; color:#B8C0CA;")
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
        self.setFixedHeight(30)
        self._lufs = -70.0
        self._short_term = -70.0
        self._target = -14.0  # YouTube target
        self._samples: list[float] = []

    def push_audio_chunk(self, pcm: np.ndarray, sample_rate: int = 48000) -> None:
        """Push a chunk of PCM float32 audio [-1,1] for LUFS calculation."""
        from app.audio_accuracy import integrated_lufs_approx

        lufs = integrated_lufs_approx(pcm)
        self._samples.append(lufs)
        if len(self._samples) > 300:
            self._samples.pop(0)
        self._short_term = float(np.mean(sorted(self._samples)[-100:])) if self._samples else -70
        self._lufs = float(np.mean(self._samples)) if self._samples else -70
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#111316"))

        # Draw integrated LUFS
        lufs_str = f"I: {max(-70, self._lufs):.1f} LUFS"
        st_str = f"S: {max(-70, self._short_term):.1f} LUFS"
        target_str = f"Target: {self._target:.0f}"

        p.setPen(QColor("#8FA894"))
        p.drawText(4, 12, lufs_str)
        p.setPen(QColor("#B6A36E"))
        p.drawText(4, 24, st_str)
        p.setPen(QColor("#8C949F"))
        p.drawText(w - 80, 12, target_str)

        # Indicator bar
        lufs_norm = max(0.0, min(1.0, (self._short_term + 60) / 60.0))
        bar_w = int(lufs_norm * (w - 8))
        bar_color = QColor("#8FA894") if self._short_term > -18 else QColor("#B6A36E")
        p.fillRect(4, 26, bar_w, 3, bar_color)
        p.end()


class AudioMixerPanel(QWidget):
    """Horizontal row of channel strips, one per audio track."""

    volume_changed = Signal(int, float)
    pan_changed = Signal(int, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioMixerPanel")
        self.setStyleSheet(
            """
            QWidget#AudioMixerPanel {
                background: #101112;
                border: 1px solid #292E35;
                border-radius: 5px;
                color: #E6EAF2;
                font-family: "Pretendard", "Malgun Gothic", "Segoe UI", sans-serif;
                font-size: 10px;
            }
            QWidget#AudioMixerPanel QScrollArea {
                background: transparent;
                border: none;
            }
            QWidget#AudioMixerPanel QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QWidget#AudioMixerPanel QPushButton#ToolButton {
                color: #DCE2EA;
                background: #15181D;
                border: 1px solid #2B3037;
                border-radius: 5px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 650;
            }
            QWidget#AudioMixerPanel QPushButton#ToolButton:hover {
                background: #20252B;
                border-color: #68717E;
            }
            QWidget#AudioMixerPanel QDialog {
                background: #101112;
            }
            """
            + editor_scrollbar_qss("QWidget#AudioMixerPanel")
        )
        self.setMinimumHeight(172)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("AUDIO MIXER")
        self._title.setStyleSheet(
            "font-size:10px; font-weight:700; color:#E2E7EF; padding:6px 8px 3px 8px;"
        )
        outer.addWidget(self._title)
        self._routing_summary = QLabel("", self)
        self._routing_summary.setStyleSheet(
            "font-size:9px; color:#9DA7B4; padding:0 8px 4px 8px;"
        )
        self._routing_summary.setVisible(False)
        outer.addWidget(self._routing_summary)
        route_actions = QHBoxLayout()
        route_actions.setContentsMargins(6, 0, 6, 4)
        route_actions.setSpacing(5)
        self._routing_btn = QPushButton("Routing")
        self._loudness_btn = QPushButton("Loudness")
        for btn in (self._routing_btn, self._loudness_btn):
            btn.setObjectName("ToolButton")
            btn.setFixedHeight(24)
            route_actions.addWidget(btn)
        route_actions.addStretch(1)
        outer.addLayout(route_actions)
        self._routing_btn.clicked.connect(self.show_routing_matrix)
        self._loudness_btn.clicked.connect(self.show_loudness_delivery_report)

        # LUFS meter below title
        self._lufs_meter = LUFSMeter()
        outer.addWidget(self._lufs_meter)

        # Spectrum analyzer (full width)
        self._spectrum = SpectrumAnalyzer()
        outer.addWidget(self._spectrum)

        # Goniometer on the right in a row
        gonio_row = QHBoxLayout()
        gonio_row.addStretch()
        self._goniometer = GoniometerWidget()
        gonio_row.addWidget(self._goniometer)
        outer.addLayout(gonio_row)

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
        self._empty_label = QLabel("")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setStyleSheet(
            "QLabel { color:#8F98A4; background:#121417; border:1px dashed #343B44; "
            "border-radius:5px; padding:12px; font-size:10px; }"
            "QLabel[tone=\"active\"] { color:#CBD2DC; border-color:#5F6874; }"
        )
        outer.addWidget(self._empty_label)
        apply_state_to_label(self._empty_label, audio_mixer_empty_state(0))

        # Refresh VU meters at ~30fps
        self._vu_timer = QTimer(self)
        self._vu_timer.setInterval(33)
        self._vu_timer.timeout.connect(self._decay_vu)
        self._vu_timer.start()

    def refresh_tracks(self, audio_tracks: list) -> None:
        """Rebuild strips to match the current audio track list."""
        audio_tracks = list(audio_tracks or [])
        track_ids = {t.id for t in audio_tracks}
        # Remove strips for deleted tracks
        for tid in list(self._strips.keys()):
            if tid not in track_ids:
                strip = self._strips.pop(tid)
                self._strips_layout.removeWidget(strip)
                strip.deleteLater()
        # Add strips for new tracks
        for t in audio_tracks:
            name = getattr(t, "label", "") or f"A{t.id}"
            if t.id not in self._strips:
                strip = ChannelStrip(t.id, name)
                strip.volume_changed.connect(self.volume_changed.emit)
                strip.pan_changed.connect(self.pan_changed.emit)
                # Insert before the stretch
                idx = self._strips_layout.count() - 1
                self._strips_layout.insertWidget(idx, strip)
                self._strips[t.id] = strip
            # Sync current volume/pan
            strip = self._strips[t.id]
            strip.set_volume(float(getattr(t, "volume", 1.0)))
            strip.set_pan(float(getattr(t, "pan", 0.0)))
            strip.setToolTip(
                f"{name}\nVolume and pan follow this timeline audio track."
            )
        apply_state_to_label(self._empty_label, audio_mixer_empty_state(len(audio_tracks)))
        self._empty_label.setVisible(len(audio_tracks) == 0)
        self._title.setText(f"AUDIO MIXER  |  {len(audio_tracks)} TRACKS")
        routing = self.routing_matrix_payload(audio_tracks)
        sends = routing.get("sends", []) if isinstance(routing, dict) else []
        routes = routing.get("track_routes", {}) if isinstance(routing, dict) else {}
        self._routing_summary.setText(
            f"Routing: {len(routes)} tracks | {len(sends)} sends | {routing.get('channel_layout', 'stereo')}"
        )
        self._routing_summary.setVisible(len(audio_tracks) > 0)

    def routing_matrix_payload(self, audio_tracks: list | None = None) -> dict:
        """Return a Fairlight-style routing payload for current mixer tracks."""
        from app.audio_workflow import build_default_routing_matrix

        rows = []
        tracks = list(audio_tracks or [])
        if not tracks and self._strips:
            tracks = [
                {"id": tid, "label": f"A{tid}", "bus_id": "master"}
                for tid in sorted(self._strips)
            ]
        for idx, track in enumerate(tracks):
            if isinstance(track, dict):
                rows.append({
                    "id": track.get("id", idx),
                    "label": track.get("label") or track.get("name") or f"A{idx + 1}",
                    "role": track.get("role") or track.get("bus_role") or track.get("bus_id") or "",
                    "bus_id": track.get("bus_id") or "",
                })
            else:
                rows.append({
                    "id": getattr(track, "id", idx),
                    "label": getattr(track, "label", "") or getattr(track, "name", "") or f"A{idx + 1}",
                    "role": getattr(track, "role", "") or getattr(track, "bus_role", "") or getattr(track, "bus_id", ""),
                    "bus_id": getattr(track, "bus_id", ""),
                })
        return build_default_routing_matrix(rows).to_dict()

    def loudness_delivery_payload(self, measured: dict | None = None, *, target: str = "shortform") -> dict:
        """Return a delivery QA gate for current loudness and mixer routing."""
        from app.audio_workflow import audio_delivery_qa_gate

        if measured is None:
            measured = {
                "integrated_lufs": float(getattr(self._lufs_meter, "_lufs", -70.0)),
                "true_peak_db": 0.0,
                "lra": 0.0,
            }
        gate = audio_delivery_qa_gate(
            measured,
            target=target,
            routing=self.routing_matrix_payload(),
        )
        # Preserve the old flat loudness keys for callers/tests that treated
        # this as a loudness-only report before routing validation was added.
        loudness = gate.get("loudness", {}) if isinstance(gate, dict) else {}
        if isinstance(loudness, dict):
            for key, value in loudness.items():
                gate.setdefault(key, value)
        return gate

    def show_routing_matrix(self) -> None:
        payload = self.routing_matrix_payload()
        dlg = QDialog(self)
        dlg.setWindowTitle("Audio Routing Matrix")
        dlg.resize(560, 360)
        root = QVBoxLayout(dlg)
        title = QLabel("Fairlight-style routing")
        title.setStyleSheet("font-weight:900;color:#FFFFFF;")
        root.addWidget(title)
        routes = payload.get("track_routes", {}) if isinstance(payload, dict) else {}
        sends = payload.get("sends", []) if isinstance(payload, dict) else []
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Type", "Source", "Target"])
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for source, target in routes.items():
            row = table.rowCount()
            table.insertRow(row)
            for col, value in enumerate(("Track", source, target)):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        for send in sends:
            if not isinstance(send, dict):
                continue
            row = table.rowCount()
            table.insertRow(row)
            for col, value in enumerate(("Send", send.get("source_bus", ""), send.get("target_bus", ""))):
                table.setItem(row, col, QTableWidgetItem(str(value)))
        root.addWidget(table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

    def show_loudness_delivery_report(self) -> None:
        report = self.loudness_delivery_payload()
        loudness = report.get("loudness", report) if isinstance(report, dict) else {}
        dlg = QDialog(self)
        dlg.setWindowTitle("Loudness Delivery")
        dlg.resize(500, 320)
        root = QVBoxLayout(dlg)
        lines = [
            f"Delivery QA: {'OK' if report.get('ok') else 'Review'}",
            f"Target: {loudness.get('target_id', '-')}",
            f"Integrated: {loudness.get('integrated_lufs', 0):.1f} LUFS",
            f"Target LUFS: {loudness.get('target_lufs', 0):.1f}",
            f"Delta: {loudness.get('loudness_delta', 0):+.2f} LU",
            f"True peak: {loudness.get('true_peak_db', 0):.1f} dB",
            f"Routing: {int(report.get('route_count', 0) or 0)} tracks | {int(report.get('bus_count', 0) or 0)} buses",
        ]
        warnings = report.get("warnings", []) if isinstance(report, dict) else []
        if warnings:
            lines.extend(["", "Warnings:", *[f"- {issue}" for issue in warnings]])
        gates = report.get("qa_gates", []) if isinstance(report, dict) else []
        if gates:
            lines.extend(["", "QA gates:", *[f"- {gate}" for gate in gates]])
        lbl = QLabel("\n".join(lines))
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#E8EAF4;font-weight:700;")
        root.addWidget(lbl, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.reject)
        root.addWidget(buttons)
        dlg.exec()

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

    def push_spectrum_chunk(self, pcm: np.ndarray, sample_rate: int = 48000) -> None:
        self._spectrum.push_audio_chunk(pcm, sample_rate)

    def push_goniometer_chunk(self, pcm: np.ndarray) -> None:
        self._goniometer.push_audio_chunk(pcm)


class SpectrumAnalyzer(QWidget):
    _NUM_BARS = 64
    _DB_FLOOR = -80.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self.setMinimumWidth(200)
        self._bars = np.zeros(self._NUM_BARS, dtype=np.float32)

    def push_audio_chunk(self, pcm: np.ndarray, sample_rate: int = 48000) -> None:
        if pcm.ndim > 1:
            mono = pcm.mean(axis=1)
        else:
            mono = pcm.astype(np.float32)
        n = len(mono)
        if n < 2:
            return
        fft_size = 1 << (n - 1).bit_length()
        window = np.hanning(n)
        spectrum = np.abs(np.fft.rfft(mono * window, n=fft_size))
        freqs = np.fft.rfftfreq(fft_size, d=1.0 / sample_rate)

        log_min = math.log10(max(freqs[1], 20.0))
        log_max = math.log10(20000.0)
        edges = np.logspace(log_min, log_max, self._NUM_BARS + 1)

        new_bars = np.zeros(self._NUM_BARS, dtype=np.float32)
        for i in range(self._NUM_BARS):
            mask = (freqs >= edges[i]) & (freqs < edges[i + 1])
            if mask.any():
                rms = float(np.sqrt(np.mean(spectrum[mask] ** 2)) + 1e-10)
                new_bars[i] = max(self._DB_FLOOR, 20 * math.log10(rms + 1e-10))
            else:
                new_bars[i] = self._DB_FLOOR

        self._bars = self._bars * 0.7 + new_bars * 0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#0E0F10"))

        # dB grid lines at -20, -40, -60
        p.setPen(QPen(QColor("#252A31"), 1))
        for db in (-20, -40, -60):
            y = int((1.0 - db / self._DB_FLOOR) * h)
            p.drawLine(0, y, w, y)
            p.setPen(QPen(QColor("#5F6874"), 1))
            p.drawText(2, y - 1, f"{db}")
            p.setPen(QPen(QColor("#252A31"), 1))

        bar_w = max(1, w // self._NUM_BARS)
        for i, db in enumerate(self._bars):
            norm = max(0.0, min(1.0, db / self._DB_FLOOR))
            bar_h = int((1.0 - norm) * h)
            if bar_h <= 0:
                continue
            t = i / (self._NUM_BARS - 1)
            r = int(96 + t * 52)
            g = int(108 + t * 28)
            b = int(126 + (1.0 - t) * 36)
            color = QColor(r, g, b, 185)
            x = i * bar_w
            p.fillRect(x, h - bar_h, bar_w - 1, bar_h, color)
        p.end()


class GoniometerWidget(QWidget):
    _BUF = 2048

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(86, 86)
        self._samples_l = np.zeros(self._BUF, dtype=np.float32)
        self._samples_r = np.zeros(self._BUF, dtype=np.float32)
        self._count = 0

    def push_audio_chunk(self, pcm: np.ndarray) -> None:
        if pcm.ndim == 1:
            l_ch = pcm.astype(np.float32)
            r_ch = l_ch
        elif pcm.shape[1] >= 2:
            l_ch = pcm[:, 0].astype(np.float32)
            r_ch = pcm[:, 1].astype(np.float32)
        else:
            l_ch = pcm[:, 0].astype(np.float32)
            r_ch = l_ch

        n = min(len(l_ch), self._BUF)
        self._samples_l = np.roll(self._samples_l, -n)
        self._samples_r = np.roll(self._samples_r, -n)
        self._samples_l[-n:] = l_ch[-n:]
        self._samples_r[-n:] = r_ch[-n:]
        self._count = min(self._count + n, self._BUF)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        radius = min(cx, cy) - 2

        # Circular clip
        p.setClipRegion(QRegion(cx - radius, cy - radius, radius * 2, radius * 2,
                                QRegion.RegionType.Ellipse))
        p.fillRect(0, 0, w, h, QColor("#0E0F10"))

        # Axis lines at 45 degrees
        p.setPen(QPen(QColor("#252A31"), 1))
        p.drawLine(cx - radius, cy - radius, cx + radius, cy + radius)
        p.drawLine(cx - radius, cy + radius, cx + radius, cy - radius)
        p.setPen(QPen(QColor("#5F6874"), 1))
        p.drawLine(cx, cy - radius, cx, cy + radius)
        p.drawLine(cx - radius, cy, cx + radius, cy)

        # L / R labels
        p.setPen(QColor("#8C949F"))
        p.drawText(4, cy + 4, "L")
        p.drawText(w - 12, cy + 4, "R")

        # Plot samples: mid = L+R, side = L-R
        dot_color = QColor(168, 183, 202, 86)
        p.setPen(QPen(dot_color, 2))
        l = self._samples_l
        r = self._samples_r
        mid = (l + r) * 0.5
        side = (l - r) * 0.5
        scale = radius * 0.9
        xs = (cx + side * scale).astype(int)
        ys = (cy - mid * scale).astype(int)
        for x, y in zip(xs, ys):
            p.drawPoint(x, y)
        p.end()
