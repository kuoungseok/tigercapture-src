from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.icons import app_icon, icon_size
from app.studio_slider import StudioSlider
from app.style import editor_scrollbar_qss
from app.video_editor_audio_shared import _block_signals
from app.video_editor_audio_style import (
    AUDIO_AMBER,
    AUDIO_BG,
    AUDIO_BG_ALT,
    AUDIO_BORDER,
    AUDIO_BORDER_HI,
    AUDIO_GREEN,
    AUDIO_PANEL,
    AUDIO_PANEL_SOFT,
    AUDIO_RED,
    AUDIO_TEXT,
    AUDIO_TEXT_DIM,
    AUDIO_TEXT_MUTED,
    CHANNEL_SLIDER_QSS,
    MIXER_PANEL_QSS,
    MIXER_SCOPES_QSS,
    MIXER_SPLITTER_QSS,
    MIXER_TITLE_QSS,
)


class GoniometerWidget(QWidget):
    """Lissajous / stereo phase goniometer display.

    Call ``update_from_stereo(l_peaks, r_peaks)`` with numpy arrays of
    recent L/R amplitude values (float32, 0??) to refresh the display.
    """

    _DOT_RADIUS = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self._l_vals = []   # list of float
        self._r_vals = []   # list of float
        self._max_trail = 64

    # ------------------------------------------------------------------
    def update_from_stereo(self, l_peaks, r_peaks) -> None:
        """Accept numpy arrays and store (L, R) pairs for painting."""
        import numpy as _np
        l = _np.asarray(l_peaks, dtype=_np.float32).ravel()
        r = _np.asarray(r_peaks, dtype=_np.float32).ravel()
        n = min(len(l), len(r))
        if n == 0:
            return
        self._l_vals = (self._l_vals + list(l[:n]))[-self._max_trail:]
        self._r_vals = (self._r_vals + list(r[:n]))[-self._max_trail:]
        self.update()

    def clear(self) -> None:
        self._l_vals = []
        self._r_vals = []
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
        from PySide6.QtCore import Qt

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) * 0.45

        # --- background circle ---
        p.setBrush(QBrush(QColor(AUDIO_BG)))
        p.setPen(QPen(QColor(AUDIO_BORDER), 1))
        p.drawEllipse(int(cx - radius), int(cy - radius),
                      int(radius * 2), int(radius * 2))

        # --- crosshair ---
        p.setPen(QPen(QColor(AUDIO_BORDER_HI), 1))
        p.drawLine(int(cx), int(cy - radius), int(cx), int(cy + radius))
        p.drawLine(int(cx - radius), int(cy), int(cx + radius), int(cy))

        # --- dots with trail ---
        n = len(self._l_vals)
        for i, (lv, rv) in enumerate(zip(self._l_vals, self._r_vals)):
            # goniometer math: M/S conversion
            x_norm = (rv - lv) * 0.5   # side  ??horizontal
            y_norm = (lv + rv) * 0.5   # mid   ??vertical (up = loud)

            px = cx + x_norm * radius
            py = cy - y_norm * radius   # y-axis inverted in screen coords

            # colour: green if correlated (x near 0), red if anti-correlated
            corr = 1.0 - min(abs(x_norm) * 2.0, 1.0)
            r_ch = int((1.0 - corr) * 146)
            g_ch = int(corr * 154)
            alpha = int(60 + 195 * (i / max(n - 1, 1)))   # fade trail

            color = QColor(r_ch, g_ch, 92, min(alpha, 188))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            dr = self._DOT_RADIUS
            p.drawEllipse(int(px - dr), int(py - dr), dr * 2, dr * 2)

        # --- labels ---
        label_font = QFont()
        label_font.setPointSize(8)
        label_font.setBold(True)
        p.setFont(label_font)
        p.setPen(QPen(QColor(AUDIO_TEXT_DIM)))

        margin = 6
        p.drawText(int(cx - radius + margin), int(cy - radius + margin + 10), "L")
        p.drawText(int(cx + radius - margin - 10), int(cy - radius + margin + 10), "R")
        p.drawText(int(cx - 4), int(cy - radius + margin + 10), "M")
        p.drawText(int(cx - 4), int(cy + radius - margin), "S")

        p.end()


class LUFSWidget(QWidget):
    """Displays Integrated / Short-term / Momentary LUFS + True Peak."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(200)
        self.setMinimumHeight(180)
        self._integrated = None   # float LUFS or None
        self._short_term = None
        self._momentary = None
        self._true_peak = None    # dBFS

    # ------------------------------------------------------------------
    @staticmethod
    def _rms_to_lufs(arr) -> float | None:
        """Convert a 1-D float32 array of peak amplitudes to a rough LUFS value."""
        import numpy as _np
        if arr is None or len(arr) == 0:
            return None
        # Use mean-square of peak values as a proxy for power
        ms = float(_np.mean(arr.astype(_np.float32) ** 2))
        if ms <= 0.0:
            return None
        db = 10.0 * _np.log10(ms)   # dB relative to full scale (squared peaks)
        return db - 0.7             # rough K-weighting offset

    def update_from_peaks(self, l_peaks, r_peaks, full_l, full_r) -> None:
        """Compute LUFS metrics and refresh the widget.

        Parameters
        ----------
        l_peaks, r_peaks : array-like
            Recent ~400 ms window (??6 buckets) for momentary measurement.
        full_l, full_r : array-like or None
            Full waveform arrays for integrated measurement.
        """
        import numpy as _np

        def _to_f32(a):
            if a is None:
                return None
            arr = _np.asarray(a, dtype=_np.float32).ravel()
            return arr if len(arr) > 0 else None

        lp = _to_f32(l_peaks)
        rp = _to_f32(r_peaks)
        fl = _to_f32(full_l)
        fr = _to_f32(full_r)

        # Momentary (400 ms window)
        if lp is not None and rp is not None:
            combined_m = _np.concatenate([lp, rp])
            self._momentary = self._rms_to_lufs(combined_m)
        else:
            self._momentary = None

        # Short-term: use last 3 s ??120 buckets from full waveform
        if fl is not None and fr is not None:
            n120 = min(120, len(fl), len(fr))
            combined_s = _np.concatenate([fl[-n120:], fr[-n120:]])
            self._short_term = self._rms_to_lufs(combined_s)
        else:
            self._short_term = None

        # Integrated: full waveform
        if fl is not None and fr is not None:
            combined_i = _np.concatenate([fl, fr])
            self._integrated = self._rms_to_lufs(combined_i)
        else:
            self._integrated = None

        # True peak: max of full waveform
        if fl is not None and fr is not None:
            peak_val = float(_np.maximum(fl, fr[:len(fl)]).max()) if len(fl) <= len(fr) else float(_np.maximum(fl[:len(fr)], fr).max())
            self._true_peak = 20.0 * _np.log10(peak_val) if peak_val > 0 else None
        else:
            self._true_peak = None

        self.update()

    # ------------------------------------------------------------------
    @staticmethod
    def _lufs_color(val: float | None) -> "QColor":
        from PySide6.QtGui import QColor
        if val is None:
            return QColor(AUDIO_TEXT_DIM)
        if val < -14.0:
            return QColor(AUDIO_GREEN)
        if val < -9.0:
            return QColor(AUDIO_AMBER)
        return QColor(AUDIO_RED)

    @staticmethod
    def _fmt(val: float | None, suffix: str = " LUFS") -> str:
        if val is None:
            return "---"
        return f"{val:.1f}{suffix}"

    def paintEvent(self, event) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QColor, QPen, QFont, QBrush
        from PySide6.QtCore import Qt, QRect

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background
        p.fillRect(0, 0, w, h, QColor(AUDIO_BG))

        rows = [
            ("Integrated",  self._integrated, True),
            ("Short-term",  self._short_term, False),
            ("Momentary",   self._momentary,  False),
            ("True Peak",   self._true_peak,  False),
        ]

        bar_h = 24
        label_h = 14
        row_h = bar_h + label_h + 6
        top_pad = 8

        for idx, (name, val, big) in enumerate(rows):
            y = top_pad + idx * row_h
            color = self._lufs_color(val)

            # Label
            lf = QFont()
            lf.setPointSize(8)
            p.setFont(lf)
            p.setPen(QPen(QColor(AUDIO_TEXT_DIM)))
            p.drawText(QRect(8, y, w - 16, label_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       name)

            # Value text
            vf = QFont()
            vf.setPointSize(10 if big else 9)
            vf.setBold(big)
            p.setFont(vf)
            p.setPen(QPen(color))
            suffix = " dBFS" if name == "True Peak" else " LUFS"
            p.drawText(QRect(8, y + label_h, w - 16, bar_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       self._fmt(val, suffix))

        # Momentary loudness bar at the bottom
        bar_area_top = top_pad + len(rows) * row_h + 4
        bar_area_h = max(h - bar_area_top - 8, 8)
        bar_area_w = w - 16

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(AUDIO_PANEL_SOFT)))
        p.drawRect(8, bar_area_top, bar_area_w, bar_area_h)

        if self._momentary is not None:
            # Map -60..0 LUFS to 0..1
            frac = max(0.0, min(1.0, (self._momentary + 60.0) / 60.0))
            fill_w = int(bar_area_w * frac)
            p.setBrush(QBrush(self._lufs_color(self._momentary)))
            p.drawRect(8, bar_area_top, fill_w, bar_area_h)

        p.end()


class _MixerSpectrumWidget(QWidget):
    """Compact 64-bar FFT spectrum display for the AudioMixerPanel scopes column.

    Call ``update_bins(bins)`` with a float32 ndarray of shape (64,), values 0??.
    Bars use a purple?萸뷿ue?萸뻴an gradient matching the palette of DaVinci's fairlight.
    """

    _N_BARS = 64
    _SMOOTHING = 0.70   # how much of the old frame to keep (0=instant, 1=frozen)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(52)
        self.setMaximumHeight(72)
        self._bins = None   # ndarray (64,) float32 or None

    def update_bins(self, bins) -> None:
        import numpy as _np
        new = _np.asarray(bins, dtype=_np.float32).ravel()
        if len(new) != self._N_BARS:
            return
        if self._bins is None:
            self._bins = new
        else:
            self._bins = self._bins * self._SMOOTHING + new * (1.0 - self._SMOOTHING)
        self.update()

    def clear(self) -> None:
        self._bins = None
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        from PySide6.QtGui import QPainter, QColor, QLinearGradient
        from PySide6.QtCore import Qt

        p = QPainter(self)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor(AUDIO_BG))

        # frequency labels
        lf = p.font(); lf.setPixelSize(8); p.setFont(lf)
        p.setPen(QColor(AUDIO_TEXT_DIM))
        for label, frac in (("20", 0.0), ("200", 0.28), ("2k", 0.58), ("20k", 0.97)):
            lx = int(frac * (w - 4)) + 2
            p.drawText(lx, h - 1, label)
        label_h = 10

        draw_h = h - label_h - 2
        if self._bins is None or draw_h <= 0:
            p.end()
            return

        n = self._N_BARS
        gap = 1
        bar_w = max(1, (w - gap) // n - gap)
        total_bar = bar_w + gap

        for i in range(n):
            mag = float(self._bins[i])
            bar_h = max(0, int(mag * draw_h))
            bx = gap + i * total_bar
            if bx + bar_w > w:
                break
            by = label_h + draw_h - bar_h

            # Calm frequency gradient for the renewed editor chrome.
            t = i / max(n - 1, 1)
            r = int(118 + 28 * t)
            g = int(136 + 22 * t)
            b = int(128 + 32 * t)
            p.fillRect(bx, by, bar_w, bar_h, QColor(r, g, b, 176))

        p.end()


class AudioScopesPanel(QWidget):
    """Panel combining GoniometerWidget and LUFSWidget.

    Add to the timeline section and call ``update_at_position()``
    from ``_on_position_changed`` whenever audio scopes should refresh.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioScopesPanel")
        self.setStyleSheet(
            f"QWidget#AudioScopesPanel {{ background: {AUDIO_BG}; border-top: 1px solid {AUDIO_BORDER}; }}"
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setObjectName("ScopesTitleBar")
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            f"QWidget#ScopesTitleBar {{ background: {AUDIO_PANEL}; border-bottom: 1px solid {AUDIO_BORDER}; }}"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        title_lbl = QLabel("Audio Scopes")
        title_lbl.setStyleSheet(f"color: {AUDIO_TEXT_MUTED}; font-size: 11px; font-weight: 620;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch(1)

        close_btn = QPushButton("")
        close_btn.setFixedSize(20, 20)
        close_btn.setIcon(app_icon("clear", size=12, color="#8F95A8"))
        close_btn.setIconSize(icon_size(12))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #8F95A8; border: none; font-size: 10px; }"
            "QPushButton:hover { color: #DDE2EA; }"
        )
        close_btn.clicked.connect(self.hide)
        tb_layout.addWidget(close_btn)

        outer.addWidget(title_bar)

        # --- Scopes row ---
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(12)

        self._goniometer = GoniometerWidget()
        self._lufs = LUFSWidget()

        body_layout.addWidget(self._goniometer)
        body_layout.addWidget(self._lufs)
        body_layout.addStretch(1)

        outer.addWidget(body)

    # ------------------------------------------------------------------
    def update_at_position(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform data around pos_ms and refresh both scope widgets."""
        import numpy as _np
        from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC

        # Collect combined L/R peak arrays across all tracks
        momentary_l: list = []
        momentary_r: list = []
        full_l_chunks: list = []
        full_r_chunks: list = []

        _buckets_400ms = int(0.4 * WAVEFORM_BUCKETS_PER_SEC)   # ??16

        solo_active = any(bool(getattr(track, "solo", False)) for track in audio_tracks)
        for track in audio_tracks:
            if bool(getattr(track, "muted", False)):
                continue
            if solo_active and not bool(getattr(track, "solo", False)):
                continue
            vol = getattr(track, "volume", 1.0)
            for clip in getattr(track, "clips", []):
                if getattr(clip, "source_path", None) is None:
                    continue
                wf = getattr(clip, "waveform", None)
                if wf is None or (hasattr(wf, "size") and wf.size == 0):
                    continue

                wf = _np.asarray(wf, dtype=_np.float32)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)

                if is_stereo:
                    wf_l, wf_r = wf[0], wf[1]
                else:
                    wf_l = wf_r = wf.ravel()

                n = len(wf_l)

                # Full waveform for integrated LUFS
                full_l_chunks.append(wf_l * vol)
                full_r_chunks.append(wf_r * vol)

                # Window around playhead for momentary
                local_ms = pos_ms - getattr(clip, "offset_ms", 0)
                if local_ms < 0:
                    continue
                src_ms = getattr(clip, "trim_start_ms", 0) + local_ms
                center_bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                b_start = max(0, center_bucket - _buckets_400ms)
                b_end = min(n, center_bucket + 1)
                if b_start < b_end:
                    momentary_l.append(wf_l[b_start:b_end] * vol)
                    momentary_r.append(wf_r[b_start:b_end] * vol)

        if not full_l_chunks:
            # No data ??show blank / placeholder
            self._goniometer.clear()
            self._lufs.update_from_peaks(
                _np.zeros(1, _np.float32), _np.zeros(1, _np.float32),
                None, None,
            )
            return

        full_l = _np.concatenate(full_l_chunks)
        full_r = _np.concatenate(full_r_chunks)

        if momentary_l:
            mom_l = _np.concatenate(momentary_l)
            mom_r = _np.concatenate(momentary_r)
        else:
            mom_l = mom_r = _np.zeros(1, _np.float32)

        self._goniometer.update_from_stereo(mom_l, mom_r)
        self._lufs.update_from_peaks(mom_l, mom_r, full_l, full_r)


# ---------------------------------------------------------------------------
#  Audio Mixer Panel
# ---------------------------------------------------------------------------


class _VUMeterWidget(QWidget):
    """Tiny L/R bar-graph VU meter used inside a ChannelStrip."""

    _GREEN = QColor(AUDIO_GREEN)
    _YELLOW = QColor(AUDIO_AMBER)
    _RED = QColor(AUDIO_RED)
    _BG = QColor(AUDIO_BG_ALT)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._l: float = 0.0
        self._r: float = 0.0
        self.setFixedSize(16, 46)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def set_levels(self, l: float, r: float) -> None:
        self._l = max(0.0, min(1.0, l))
        self._r = max(0.0, min(1.0, r))
        self.update()

    def paintEvent(self, _ev) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        bar_w = (w - 3) // 2  # 2 bars + 1px gap
        for i, level in enumerate((self._l, self._r)):
            x = i * (bar_w + 1) + 1
            p.fillRect(x, 0, bar_w, h, self._BG)
            fill_h = int(level * h)
            if fill_h > 0:
                if level < 0.70:
                    color = self._GREEN
                elif level < 0.90:
                    color = self._YELLOW
                else:
                    color = self._RED
                p.fillRect(x, h - fill_h, bar_w, fill_h, color)
        p.end()


class _ChannelStrip(QWidget):
    """Single 70-px wide mixer channel: pan 夷?VU 夷?fader 夷?mute."""

    fader_changed = Signal(float)   # new volume 0.0??.5
    pan_changed = Signal(float)     # new pan -1.0..+1.0
    mute_changed = Signal(bool)
    solo_changed = Signal(bool)

    _STRIP_BG = AUDIO_PANEL
    _BORDER = AUDIO_BORDER
    _TITLE_COLOR = AUDIO_TEXT_MUTED
    _TRACK_COLORS = [
        "#78908A", "#8B829A", "#9A866D", "#789478", "#9A7470",
        "#77889C", "#98778C", "#87966F",
    ]

    def __init__(self, label: str, track_index: int = -1, is_master: bool = False, parent=None):
        super().__init__(parent)
        self._is_master = is_master
        self._track_index = track_index
        self._muted = False
        self._solo = False

        self.setFixedWidth(68)
        self.setStyleSheet(
            f"QWidget {{ background: {self._STRIP_BG}; }}"
            f"QWidget#ChannelStripFrame {{ border-right: 1px solid {self._BORDER}; }}"
            + CHANNEL_SLIDER_QSS
        )
        self.setObjectName("ChannelStripFrame")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(1)

        # Title. The source filename is often too long for a mixer strip, so
        # the strip uses the track id visually and keeps the full name in a tooltip.
        strip_title = "MASTER" if is_master else f"A{track_index + 1}"
        title_lbl = QLabel(strip_title)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setToolTip(label)
        title_lbl.setStyleSheet(
            f"color: {self._TITLE_COLOR}; font-size: 10px; font-weight: 620;"
            " background: transparent;"
        )
        title_lbl.setFixedHeight(14)
        layout.addWidget(title_lbl)

        # Pan control (skip for master). A slim slider keeps the renewed
        # mixer visually aligned with the reference instead of Qt's heavy dial.
        if not is_master:
            self._pan_dial = StudioSlider("audio")
            self._pan_dial.setRange(-100, 100)
            self._pan_dial.setValue(0)
            self._pan_dial.setFixedSize(44, 16)
            self._pan_dial.setToolTip("Pan: 0  (applies on export)")
            self._pan_dial.valueChanged.connect(self._on_pan_changed)
            pan_row = QWidget()
            pan_row.setStyleSheet("background: transparent;")
            pan_inner = QHBoxLayout(pan_row)
            pan_inner.setContentsMargins(0, 0, 0, 0)
            pan_inner.addStretch(1)
            pan_inner.addWidget(self._pan_dial)
            pan_inner.addStretch(1)
            layout.addWidget(pan_row)
        else:
            self._pan_dial = None
            layout.addSpacing(18)

        # VU meter
        vu_row = QWidget()
        vu_row.setStyleSheet("background: transparent;")
        vu_inner = QHBoxLayout(vu_row)
        vu_inner.setContentsMargins(0, 0, 0, 0)
        vu_inner.addStretch(1)
        self._vu = _VUMeterWidget()
        vu_inner.addWidget(self._vu)
        vu_inner.addStretch(1)
        layout.addWidget(vu_row)

        # Fader (vertical)
        self._fader = QSlider(Qt.Orientation.Vertical)
        self._fader.setRange(0, 150)
        self._fader.setValue(100)
        self._fader.setFixedHeight(58)
        self._fader.setToolTip("Volume: 1.00")
        self._fader.valueChanged.connect(self._on_fader_changed)
        fader_row = QWidget()
        fader_row.setStyleSheet("background: transparent;")
        fader_inner = QHBoxLayout(fader_row)
        fader_inner.setContentsMargins(0, 0, 0, 0)
        fader_inner.addStretch(1)
        fader_inner.addWidget(self._fader)
        fader_inner.addStretch(1)
        layout.addWidget(fader_row)

        # Volume label
        self._vol_label = QLabel("1.00")
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._vol_label.setStyleSheet(
            f"color: {AUDIO_TEXT}; font-size: 10px; font-family: Consolas, monospace; background: transparent;"
        )
        self._vol_label.setFixedHeight(13)
        layout.addWidget(self._vol_label)

        # Mute / solo buttons
        button_row = QWidget()
        button_row.setStyleSheet("background: transparent;")
        button_layout = QHBoxLayout(button_row)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)
        self._mute_btn = QPushButton("M")
        self._mute_btn.setCheckable(True)
        self._mute_btn.setFixedSize(30, 18)
        self._mute_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,7); color: {AUDIO_TEXT_DIM}; border: 1px solid {AUDIO_BORDER};"
            " border-radius: 4px; font-size: 10px; font-weight: 620; }"
            f"QPushButton:checked {{ background: #4C3533; color: {AUDIO_TEXT}; border-color: {AUDIO_RED}; }}"
            f"QPushButton:hover {{ color: {AUDIO_TEXT}; border-color:{AUDIO_BORDER_HI}; }}"
        )
        self._mute_btn.toggled.connect(self._on_mute_toggled)
        button_layout.addWidget(self._mute_btn)
        self._solo_btn = QPushButton("S")
        self._solo_btn.setCheckable(True)
        self._solo_btn.setFixedSize(30, 18)
        self._solo_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,7); color: {AUDIO_TEXT_DIM}; border: 1px solid {AUDIO_BORDER};"
            " border-radius: 4px; font-size: 10px; font-weight: 620; }"
            f"QPushButton:checked {{ background: #3B3826; color: {AUDIO_TEXT}; border-color: {AUDIO_AMBER}; }}"
            f"QPushButton:hover {{ color: {AUDIO_TEXT}; border-color:{AUDIO_BORDER_HI}; }}"
        )
        self._solo_btn.toggled.connect(self._on_solo_toggled)
        if is_master:
            self._solo_btn.setEnabled(False)
        button_layout.addWidget(self._solo_btn)
        layout.addWidget(button_row)

        # Color indicator at bottom
        color = self._TRACK_COLORS[track_index % len(self._TRACK_COLORS)] if not is_master else AUDIO_TEXT_DIM
        num_lbl = QLabel("MASTER" if is_master else "AUDIO")
        num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num_lbl.setFixedHeight(12)
        num_lbl.setStyleSheet(
            f"color: {color}; font-size: 8px; font-weight: 620; background: transparent;"
        )
        layout.addWidget(num_lbl)

        layout.addStretch(1)

    # ---- public API ----

    def set_volume(self, volume: float) -> None:
        """Set fader without firing fader_changed (for external sync)."""
        with _block_signals(self._fader):
            self._fader.setValue(int(round(volume * 100)))
        self._update_volume_label()

    def set_pan(self, pan: float) -> None:
        """Set pan dial without firing pan_changed (for external sync)."""
        if self._pan_dial is not None:
            with _block_signals(self._pan_dial):
                self._pan_dial.setValue(int(round(pan * 100)))

    def set_muted(self, muted: bool) -> None:
        self._muted = bool(muted)
        with _block_signals(self._mute_btn):
            self._mute_btn.setChecked(self._muted)
        self._update_volume_label()

    def set_solo(self, solo: bool) -> None:
        self._solo = bool(solo)
        with _block_signals(self._solo_btn):
            self._solo_btn.setChecked(self._solo)

    def set_levels(self, l: float, r: float) -> None:
        self._vu.set_levels(l, r)

    def levels(self) -> tuple[float, float]:
        return float(getattr(self._vu, "_l", 0.0)), float(getattr(self._vu, "_r", 0.0))

    def pan_value(self) -> int:
        return self._pan_dial.value() if self._pan_dial else 0

    # ---- private ----

    def _on_fader_changed(self, value: int) -> None:
        vol = value / 100.0
        self._update_volume_label()
        self.fader_changed.emit(vol)

    def _update_volume_label(self) -> None:
        vol = self._fader.value() / 100.0
        self._vol_label.setText(f"{vol:.2f} [M]" if self._muted else f"{vol:.2f}")

    def _on_pan_changed(self, value: int) -> None:
        pan = value / 100.0
        if self._pan_dial is not None:
            self._pan_dial.setToolTip(f"Pan: {value:+d}  (applies on export)")
        self.pan_changed.emit(pan)

    def _on_mute_toggled(self, muted: bool) -> None:
        self._muted = bool(muted)
        self._update_volume_label()
        self.mute_changed.emit(bool(muted))

    def _on_solo_toggled(self, solo: bool) -> None:
        self._solo = bool(solo)
        self.solo_changed.emit(bool(solo))


class AudioMixerPanel(QWidget):
    """Compact DaVinci-Fairlight-style channel strip mixer.

    One ChannelStrip per AudioTrack + one Master strip.
    A collapsible right-side scopes column (GoniometerWidget + LUFSWidget)
    lives inside this panel so no separate AudioScopesPanel is needed below
    the timeline.

    Call ``rebuild(audio_tracks)`` to refresh the strips list.
    Call ``update_levels(pos_ms, audio_tracks)`` each playhead tick.
    Call ``update_scopes(pos_ms, audio_tracks)`` to refresh scope widgets.
    Call ``set_scopes_visible(bool)`` to show/hide the scopes column.
    """

    visibility_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AudioMixerPanel")
        self.setStyleSheet(MIXER_PANEL_QSS)
        self.setFixedHeight(230)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Title bar ---
        title_bar = QWidget()
        title_bar.setObjectName("MixerTitleBar")
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(MIXER_TITLE_QSS)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(10, 0, 6, 0)
        tb_layout.setSpacing(6)

        title_lbl = QLabel("Audio Mixer")
        title_lbl.setStyleSheet(f"color: {AUDIO_TEXT_MUTED}; font-size: 11px; font-weight: 620;")
        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch(1)

        # Popout button, same icon treatment as other panels.
        self._popout_win: "QWidget | None" = None
        popout_btn = QPushButton("")
        popout_btn.setObjectName("PreviewPopoutIcon")
        popout_btn.setFixedSize(28, 24)
        popout_btn.setText("")
        popout_btn.setIcon(app_icon("popout", size=16))
        popout_btn.setIconSize(icon_size(16))
        popout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        popout_btn.setToolTip("Open mixer in a popout window")
        popout_btn.clicked.connect(self._toggle_popout)
        tb_layout.addWidget(popout_btn)

        close_btn = QPushButton("")
        close_btn.setFixedSize(20, 20)
        close_btn.setIcon(app_icon("clear", size=12, color="#8F95A8"))
        close_btn.setIconSize(icon_size(12))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #8F95A8; border: none; font-size: 10px; }"
            "QPushButton:hover { color: #DDE2EA; }"
        )
        close_btn.clicked.connect(self.hide)
        tb_layout.addWidget(close_btn)
        outer.addWidget(title_bar)

        # --- Horizontal splitter: strips (left) | scopes (right) ---
        self._body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._body_splitter.setHandleWidth(1)
        self._body_splitter.setStyleSheet(MIXER_SPLITTER_QSS)

        # --- Strips scroll area (left side) ---
        strips_scroll = QScrollArea()
        strips_scroll.setWidgetResizable(True)
        strips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        strips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        strips_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        strips_scroll.setStyleSheet(
            f"QScrollArea {{ background: {AUDIO_BG}; border: none; }}"
            + editor_scrollbar_qss()
        )

        self._strips_host = QWidget()
        self._strips_host.setStyleSheet(f"background: {AUDIO_BG};")
        self._strips_layout = QHBoxLayout(self._strips_host)
        self._strips_layout.setContentsMargins(4, 4, 4, 4)
        self._strips_layout.setSpacing(1)
        self._strips_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Master strip placeholder (always last)
        self._master_strip = _ChannelStrip("MASTER", is_master=True)
        # Master doesn't need to call external callbacks ??just keep as local state
        self._strips_layout.addStretch(1)
        self._strips_layout.addWidget(self._master_strip)

        strips_scroll.setWidget(self._strips_host)
        self._body_splitter.addWidget(strips_scroll)

        # --- Scopes column (right side, ~220 px wide) ---
        self._scopes_col = QWidget()
        self._scopes_col.setObjectName("MixerScopesCol")
        self._scopes_col.setStyleSheet(MIXER_SCOPES_QSS)
        self._scopes_col.setFixedWidth(210)
        scopes_vlay = QVBoxLayout(self._scopes_col)
        scopes_vlay.setContentsMargins(6, 6, 6, 6)
        scopes_vlay.setSpacing(4)

        self._mixer_goniometer = GoniometerWidget()
        self._mixer_goniometer.setFixedSize(108, 108)
        # Center goniometer horizontally
        gonio_row = QHBoxLayout()
        gonio_row.setContentsMargins(0, 0, 0, 0)
        gonio_row.addStretch(1)
        gonio_row.addWidget(self._mixer_goniometer)
        gonio_row.addStretch(1)
        scopes_vlay.addLayout(gonio_row)

        self._mixer_spectrum = _MixerSpectrumWidget()
        self._mixer_spectrum.setMaximumHeight(52)
        scopes_vlay.addWidget(self._mixer_spectrum)

        self._mixer_lufs = LUFSWidget()
        scopes_vlay.addWidget(self._mixer_lufs, stretch=1)

        self._body_splitter.addWidget(self._scopes_col)

        # Splitter proportions: strips stretch, scopes fixed
        self._body_splitter.setStretchFactor(0, 1)
        self._body_splitter.setStretchFactor(1, 0)

        outer.addWidget(self._body_splitter, stretch=1)

        # Internal state: track_id ??ChannelStrip
        self._track_strips: dict[int, _ChannelStrip] = {}
        # Callback set by the editor: (track_id, volume) ??None
        self._volume_callback = None
        # Callback set by the editor: (track_id, pan) ??None
        self._pan_callback = None
        self._mute_callback = None
        self._solo_callback = None
        self._window_move_suspended = False
        self._window_move_vu_was_active = True

        # VU meter decay: 30fps timer smoothly lowers meters when no new
        # level data arrives (e.g. playback stopped or clip is silent).
        from PySide6.QtCore import QTimer as _QTimer
        self._vu_decay_timer = _QTimer(self)
        self._vu_decay_timer.setInterval(33)
        self._vu_decay_timer.timeout.connect(self._decay_vu_meters)
        self._vu_decay_timer.start()

    def showEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event) -> None:  # pragma: no cover - exercised by UI QA
        super().hideEvent(event)
        self.visibility_changed.emit(False)
        self._window_move_suspended = False
        self._window_move_vu_was_active = True

    def _decay_vu_meters(self) -> None:
        """Gently decay all VU meters by 15% per frame (~30 fps fall-off)."""
        decay = 0.85
        for strip in self._track_strips.values():
            vu = strip._vu
            new_l = vu._l * decay
            new_r = vu._r * decay
            if new_l > 0.001 or new_r > 0.001:
                vu.set_levels(new_l, new_r)
        m_vu = self._master_strip._vu
        m_l = m_vu._l * decay
        m_r = m_vu._r * decay
        if m_l > 0.001 or m_r > 0.001:
            m_vu.set_levels(m_l, m_r)

    def set_window_move_suspended(self, suspended: bool) -> None:
        suspended = bool(suspended)
        if suspended == self._window_move_suspended:
            return
        self._window_move_suspended = suspended
        if suspended:
            self._window_move_vu_was_active = self._vu_decay_timer.isActive()
            if self._window_move_vu_was_active:
                self._vu_decay_timer.stop()
            return
        if self._window_move_vu_was_active and not self._vu_decay_timer.isActive():
            self._vu_decay_timer.start()
        self._window_move_vu_was_active = False

    def set_volume_callback(self, cb) -> None:
        """Register callback(track_id, volume) called when a fader moves."""
        self._volume_callback = cb

    def set_pan_callback(self, cb) -> None:
        """Register callback(track_id, pan) called when a pan dial moves."""
        self._pan_callback = cb

    def set_mute_callback(self, cb) -> None:
        self._mute_callback = cb

    def set_solo_callback(self, cb) -> None:
        self._solo_callback = cb

    # ------------------------------------------------------------------
    # Scopes column visibility

    def set_scopes_visible(self, visible: bool) -> None:
        """Show or hide the right-side scopes column (goniometer + LUFS)."""
        self._scopes_col.setVisible(visible)

    def scopes_visible(self) -> bool:
        """Return True if the scopes column is currently shown."""
        return self._scopes_col.isVisible()

    # ------------------------------------------------------------------
    # Scopes update (called each playhead tick)

    def update_scopes(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform data around pos_ms and refresh goniometer + LUFS."""
        if not self._scopes_col.isVisible():
            return
        try:
            import numpy as _np
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
        except Exception:
            return

        momentary_l: list = []
        momentary_r: list = []
        full_l_chunks: list = []
        full_r_chunks: list = []
        _buckets_400ms = int(0.4 * WAVEFORM_BUCKETS_PER_SEC)

        for track in audio_tracks:
            vol = getattr(track, "volume", 1.0)
            for clip in getattr(track, "clips", []):
                if getattr(clip, "source_path", None) is None:
                    continue
                wf = getattr(clip, "waveform", None)
                if wf is None or (hasattr(wf, "size") and wf.size == 0):
                    continue
                wf = _np.asarray(wf, dtype=_np.float32)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
                if is_stereo:
                    wf_l, wf_r = wf[0], wf[1]
                else:
                    wf_l = wf_r = wf.ravel()
                n = len(wf_l)
                full_l_chunks.append(wf_l * vol)
                full_r_chunks.append(wf_r * vol)
                local_ms = pos_ms - getattr(clip, "offset_ms", 0)
                if local_ms < 0:
                    continue
                src_ms = getattr(clip, "trim_start_ms", 0) + local_ms
                center_bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                b_start = max(0, center_bucket - _buckets_400ms)
                b_end = min(n, center_bucket + 1)
                if b_start < b_end:
                    momentary_l.append(wf_l[b_start:b_end] * vol)
                    momentary_r.append(wf_r[b_start:b_end] * vol)

        # Collect spectrum bins from first clip that has them
        spectrum_bins = None
        for track in audio_tracks:
            for clip in getattr(track, "clips", []):
                sb = getattr(clip, "spectrum_bins", None)
                if sb is not None and hasattr(sb, "size") and sb.size > 0:
                    spectrum_bins = _np.asarray(sb, dtype=_np.float32)
                    break
            if spectrum_bins is not None:
                break

        if not full_l_chunks:
            self._mixer_goniometer.clear()
            self._mixer_spectrum.clear()
            self._mixer_lufs.update_from_peaks(
                _np.zeros(1, _np.float32), _np.zeros(1, _np.float32),
                None, None,
            )
            return

        full_l = _np.concatenate(full_l_chunks)
        full_r = _np.concatenate(full_r_chunks)
        if momentary_l:
            mom_l = _np.concatenate(momentary_l)
            mom_r = _np.concatenate(momentary_r)
        else:
            mom_l = mom_r = _np.zeros(1, _np.float32)

        self._mixer_goniometer.update_from_stereo(mom_l, mom_r)
        self._mixer_lufs.update_from_peaks(mom_l, mom_r, full_l, full_r)

        # Animate spectrum: static clip bins ??current RMS level
        if spectrum_bins is not None and len(spectrum_bins) == _MixerSpectrumWidget._N_BARS:
            rms = float(_np.sqrt(_np.mean(mom_l ** 2 + mom_r ** 2) * 0.5))
            scale = min(1.0, rms * 4.0 + 0.15)   # always show a floor
            self._mixer_spectrum.update_bins(spectrum_bins * scale)
        elif spectrum_bins is not None:
            self._mixer_spectrum.update_bins(spectrum_bins)

    def _toggle_popout(self) -> None:
        """Open/close the mixer as a floating window (reparent pattern)."""
        if self._popout_win is not None:
            self._popout_win.close()
            return
        from PySide6.QtCore import QSize
        win = QWidget(None, Qt.WindowType.Window)
        win.setWindowTitle("Audio Mixer")
        win.resize(QSize(max(600, self.width()), 340))
        win.setStyleSheet(f"QWidget {{ background: {AUDIO_BG}; }}")
        lay = QVBoxLayout(win)
        lay.setContentsMargins(0, 0, 0, 0)
        # Reparent the body splitter (strips + scopes) into the floating window
        self._body_splitter.setParent(win)
        lay.addWidget(self._body_splitter)
        self._popout_win = win

        def _on_close():
            # Bring splitter back to the panel
            self._body_splitter.setParent(self)
            self.layout().addWidget(self._body_splitter)
            self._popout_win = None
            win.deleteLater()

        win.closeEvent = lambda ev, _cb=_on_close: (_cb(), ev.accept())
        win.show()
        win.raise_()

    def rebuild(self, audio_tracks: list) -> None:
        """Recreate channel strips to match current audio track list."""
        # Remove old track strips (not master)
        for strip in list(self._track_strips.values()):
            self._strips_layout.removeWidget(strip)
            strip.deleteLater()
        self._track_strips.clear()

        for i, track in enumerate(audio_tracks):
            name = track.display_name or f"Audio {i+1}"
            strip = _ChannelStrip(name, track_index=i)
            strip.set_volume(track.volume)
            strip.set_pan(getattr(track, "pan", 0.0))
            strip.set_muted(bool(getattr(track, "muted", False)))
            strip.set_solo(bool(getattr(track, "solo", False)))
            tid = track.id

            def _make_vol_cb(track_id):
                def _cb(vol):
                    if self._volume_callback:
                        self._volume_callback(track_id, vol)
                return _cb

            def _make_pan_cb(track_id):
                def _cb(pan):
                    if self._pan_callback:
                        self._pan_callback(track_id, pan)
                return _cb

            def _make_mute_cb(track_id):
                def _cb(muted):
                    if self._mute_callback:
                        self._mute_callback(track_id, bool(muted))
                return _cb

            def _make_solo_cb(track_id):
                def _cb(solo):
                    if self._solo_callback:
                        self._solo_callback(track_id, bool(solo))
                return _cb

            strip.fader_changed.connect(_make_vol_cb(tid))
            strip.pan_changed.connect(_make_pan_cb(tid))
            strip.mute_changed.connect(_make_mute_cb(tid))
            strip.solo_changed.connect(_make_solo_cb(tid))
            self._track_strips[tid] = strip
            # Insert before the stretch+master at the end
            insert_pos = self._strips_layout.count() - 2  # before stretch + master
            self._strips_layout.insertWidget(insert_pos, strip)

    def sync_track_volume(self, track_id: int, volume: float) -> None:
        """Called when a track's volume changes externally (track row slider)."""
        strip = self._track_strips.get(track_id)
        if strip is not None:
            strip.set_volume(volume)

    def sync_track_pan(self, track_id: int, pan: float) -> None:
        """Called when a track's pan changes externally (e.g. the
        per-clip sound editor's Pan knob)."""
        strip = self._track_strips.get(track_id)
        if strip is not None:
            strip.set_pan(pan)

    def sync_track_mute(self, track_id: int, muted: bool) -> None:
        strip = self._track_strips.get(track_id)
        if strip is not None:
            strip.set_muted(bool(muted))

    def sync_track_solo(self, track_id: int, solo: bool) -> None:
        strip = self._track_strips.get(track_id)
        if strip is not None:
            strip.set_solo(bool(solo))

    def mixer_state_payload(self, audio_tracks: list | None = None) -> dict:
        from app.audio_tracks import default_track_insert_slots, default_track_sends

        def _insert_slots(track: object) -> list[dict]:
            slots = getattr(track, "insert_slots", None)
            if not isinstance(slots, list):
                slots = default_track_insert_slots()
            return [dict(row) for row in slots if isinstance(row, dict)]

        def _sends(track: object) -> dict[str, float]:
            sends = default_track_sends()
            raw = getattr(track, "sends", None)
            if isinstance(raw, dict):
                for key, value in raw.items():
                    try:
                        sends[str(key)] = max(0.0, min(1.0, float(value)))
                    except Exception:
                        continue
            return sends

        tracks = list(audio_tracks or [])
        solo_active = any(bool(getattr(track, "solo", False)) for track in tracks)
        rows: list[dict] = []
        for index, track in enumerate(tracks):
            tid = int(getattr(track, "id", index + 1))
            strip = self._track_strips.get(tid)
            l_peak, r_peak = strip.levels() if strip is not None else (0.0, 0.0)
            peak_hold = min(1.0, max(float(l_peak or 0.0), float(r_peak or 0.0)) + 0.06)
            clipped = bool(float(getattr(track, "volume", 1.0) or 0.0) >= 1.18)
            lanes = getattr(track, "automation_lanes", None)
            if not isinstance(lanes, dict):
                lanes = {}
            point_count = sum(len(list(points or [])) for points in lanes.values())
            if getattr(track, "automation_points", None):
                point_count = max(point_count, len(list(getattr(track, "automation_points", []) or [])))
            rows.append(
                {
                    "id": tid,
                    "index": index,
                    "label": str(getattr(track, "display_name", "") or getattr(track, "label", "") or f"Audio {index + 1}"),
                    "volume": float(getattr(track, "volume", 1.0) or 0.0),
                    "pan": float(getattr(track, "pan", 0.0) or 0.0),
                    "muted": bool(getattr(track, "muted", False)),
                    "solo": bool(getattr(track, "solo", False)),
                    "audible": not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False))),
                    "bus_id": str(getattr(track, "bus_id", "master") or "master"),
                    "track_type": str(getattr(track, "track_type", "") or ""),
                    "insert_slots": _insert_slots(track),
                    "sends": _sends(track),
                    "automation": {
                        "read": bool(getattr(track, "automation_read", True)),
                        "write": bool(getattr(track, "automation_write", False)),
                        "point_count": point_count,
                    },
                    "meter": {
                        "track_id": tid,
                        "level_l": float(l_peak or 0.0),
                        "level_r": float(r_peak or 0.0),
                        "peak_hold": peak_hold,
                        "clip_led": clipped,
                        "audible": not bool(getattr(track, "muted", False)) and (not solo_active or bool(getattr(track, "solo", False))),
                    },
                    "clip_count": len(list(getattr(track, "clips", []) or [])),
                    "loaded": bool(getattr(track, "is_loaded", False)),
                    "level_l": l_peak,
                    "level_r": r_peak,
                }
            )
        master_l, master_r = self._master_strip.levels()
        return {
            "schema": "tigerstudio.audio.mixer.v1",
            "track_count": len(rows),
            "solo_active": solo_active,
            "snapshot_count": len(list(getattr(self, "_audio_mixer_snapshots", []) or [])),
            "tracks": rows,
            "master": {"level_l": master_l, "level_r": master_r},
        }

    def update_levels(self, pos_ms: int, audio_tracks: list) -> None:
        """Sample waveform peaks and update VU meters."""
        try:
            import numpy as _np
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
        except Exception:
            return

        master_l = master_r = 0.0
        solo_active = any(bool(getattr(track, "solo", False)) for track in audio_tracks)

        for track in audio_tracks:
            strip = self._track_strips.get(track.id)
            l_peak = r_peak = 0.0
            track_audible = not bool(getattr(track, "muted", False)) and (
                not solo_active or bool(getattr(track, "solo", False))
            )
            for clip in track.clips:
                if not track_audible:
                    continue
                if clip.source_path is None:
                    continue
                local_ms = pos_ms - clip.offset_ms
                if local_ms < 0 or local_ms > clip.effective_length_ms:
                    continue
                src_ms = clip.trim_start_ms + local_ms
                wf = clip.waveform
                if wf is None or wf.size == 0:
                    continue
                bucket = int(src_ms / 1000.0 * WAVEFORM_BUCKETS_PER_SEC)
                is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
                n = wf.shape[1] if is_stereo else len(wf)
                if 0 <= bucket < n:
                    if is_stereo:
                        l_peak = max(l_peak, float(wf[0, bucket]) * track.volume)
                        r_peak = max(r_peak, float(wf[1, bucket]) * track.volume)
                    else:
                        v = float(wf[bucket]) * track.volume
                        l_peak = max(l_peak, v)
                        r_peak = max(r_peak, v)
            if strip is not None:
                strip.set_levels(l_peak, r_peak)
            master_l = max(master_l, l_peak)
            master_r = max(master_r, r_peak)

        self._master_strip.set_levels(master_l, master_r)
