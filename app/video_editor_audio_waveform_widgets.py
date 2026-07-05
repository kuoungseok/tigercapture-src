from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QThread, Signal
from PySide6.QtGui import QColor, QLinearGradient, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.audio_tracks import get_cached_spectrum, store_cached_spectrum
from app.i18n import tr
from app.style import COLOR_ACCENT_ORANGE, COLOR_BG_L4, COLOR_TEXT_TERTIARY
from app.video_editor_audio_style import (
    AUDIO_AMBER,
    AUDIO_BG,
    AUDIO_BLUE,
    AUDIO_BORDER,
    AUDIO_GREEN,
    AUDIO_RED,
    AUDIO_TEXT_DIM,
)


class ClipWaveformView(QWidget):
    """Interactive waveform renderer for a single AudioClip.

    Renders the effective trim range stretched across the widget width,
    with cuts as dark overlays, fade segments as orange gradients,
    markers as cyan dots, selection as a translucent blue band, and a
    vertical playhead when driven by the sound editor's player.

    Inputs:
    - click (anywhere)   ??scrub the playhead (``scrub_requested``)
    - shift + drag       ??build a selection range (``selection_changed``)
    - double-click       ??clear the current selection
    - right-click on a marker ??``marker_right_clicked``
    """

    scrub_requested = Signal(int)                   # source_ms
    selection_changed = Signal(int, int)            # start_ms, end_ms (source)
    selection_cleared = Signal()
    marker_right_clicked = Signal(int, QPoint)      # marker_idx, global_pos

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self.setMinimumHeight(160)
        self.setStyleSheet(
            f"background-color: {AUDIO_BG}; border-radius: 6px;"
        )
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Playback position in clip-local source ms (i.e. ms from the
        # start of the source file, not the project timeline). -1 when
        # nothing is playing.
        self._playhead_source_ms: int = -1
        # Selection stored in source-ms (same domain as clip.trim_*).
        # -1 means "no selection".
        self._selection_start_ms: int = -1
        self._selection_end_ms: int = -1
        # In-progress drag state.
        self._dragging_selection: bool = False
        self._drag_start_source_ms: int = 0

    # ---- public API ----

    def refresh(self) -> None:
        self.update()

    def set_playhead_source_ms(self, source_ms: int) -> None:
        self._playhead_source_ms = int(source_ms)
        self.update()

    def clear_playhead(self) -> None:
        self._playhead_source_ms = -1
        self.update()

    def selection(self) -> tuple[int, int] | None:
        if self._selection_start_ms >= 0 and self._selection_end_ms > self._selection_start_ms:
            return (self._selection_start_ms, self._selection_end_ms)
        return None

    def set_selection(self, start_ms: int, end_ms: int) -> None:
        if end_ms > start_ms:
            self._selection_start_ms = int(start_ms)
            self._selection_end_ms = int(end_ms)
            self.selection_changed.emit(self._selection_start_ms, self._selection_end_ms)
        else:
            self._selection_start_ms = -1
            self._selection_end_ms = -1
            self.selection_cleared.emit()
        self.update()

    def clear_selection(self) -> None:
        self.set_selection(0, 0)

    # ---- coordinate helpers ----

    def _content_rect(self) -> QRect:
        return self.rect().adjusted(8, 8, -8, -8)

    def _x_to_source_ms(self, x: int) -> int:
        rect = self._content_rect()
        if rect.width() <= 0:
            return self.clip.trim_start_ms
        eff = max(1, self.clip.effective_length_ms)
        local_ms = (x - rect.left()) / rect.width() * eff
        return self.clip.trim_start_ms + max(0, min(eff, int(round(local_ms))))

    def _source_ms_to_x(self, source_ms: int) -> int:
        rect = self._content_rect()
        eff = max(1, self.clip.effective_length_ms)
        local_ms = source_ms - self.clip.trim_start_ms
        return rect.left() + int(round(local_ms / eff * rect.width()))

    # ---- mouse ----

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            # Right-click on a marker ??notify the window.
            idx = self._marker_index_at_x(event.position().toPoint().x())
            if idx is not None:
                self.marker_right_clicked.emit(idx, event.globalPosition().toPoint())
                event.accept()
                return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        src_ms = self._x_to_source_ms(event.position().toPoint().x())
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ShiftModifier:
            # Start building a selection without seeking.
            self._dragging_selection = True
            self._drag_start_source_ms = src_ms
            self._selection_start_ms = src_ms
            self._selection_end_ms = src_ms
            self.update()
            event.accept()
            return
        # Plain click = seek + also start a potential drag-selection if
        # the user proceeds to drag. We seed the drag anchor but only
        # commit a selection when the cursor actually moves.
        self._dragging_selection = True
        self._drag_start_source_ms = src_ms
        self._selection_start_ms = -1
        self._selection_end_ms = -1
        self.scrub_requested.emit(src_ms)
        self.update()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging_selection:
            return
        src_ms = self._x_to_source_ms(event.position().toPoint().x())
        if abs(src_ms - self._drag_start_source_ms) < 20:
            return  # too-small drag ??keep as a click
        start = min(self._drag_start_source_ms, src_ms)
        end = max(self._drag_start_source_ms, src_ms)
        self._selection_start_ms = start
        self._selection_end_ms = end
        self.selection_changed.emit(start, end)
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._dragging_selection = False
        # If we only clicked (no drag), leave selection cleared.
        if (
            self._selection_start_ms >= 0
            and self._selection_end_ms == self._selection_start_ms
        ):
            self._selection_start_ms = -1
            self._selection_end_ms = -1
            self.selection_cleared.emit()
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clear_selection()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    # ---- markers ----

    def _marker_index_at_x(self, x: int) -> int | None:
        markers = getattr(self.clip, "_se_markers", None) or []
        for i, m_ms in enumerate(markers):
            mx = self._source_ms_to_x(int(m_ms))
            if abs(mx - x) <= 5:
                return i
        return None

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(8, 8, -8, -8)
        painter.fillRect(self.rect(), QColor(AUDIO_BG))
        painter.setPen(QPen(QColor(AUDIO_BORDER), 1))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))

        clip = self.clip
        eff_len = max(1, clip.effective_length_ms)
        mid_y = rect.top() + rect.height() // 2

        # --- waveform ---
        wf = clip.waveform
        if wf is not None and wf.size > 0:
            import numpy as _np
            from PySide6.QtCore import QPointF
            from PySide6.QtGui import QPolygonF
            from app.audio_tracks import WAVEFORM_BUCKETS_PER_SEC
            is_stereo = (wf.ndim == 2 and wf.shape[0] == 2)
            n = wf.shape[1] if is_stereo else len(wf)
            # Merge stereo to mono for the large single-canvas view
            mono = (wf[0] + wf[1]) * 0.5 if is_stereo else wf
            trim_start_s = clip.trim_start_ms / 1000.0
            half_h = (rect.height() - 10) // 2
            px_per_sec = rect.width() / (eff_len / 1000.0)
            xs = _np.arange(rect.left() + 2, rect.right() - 1, dtype=_np.float64)
            src_s = trim_start_s + (xs - rect.left()) / max(px_per_sec, 0.001)
            buckets = (src_s * WAVEFORM_BUCKETS_PER_SEC).astype(_np.int32)
            valid = (buckets >= 0) & (buckets < n)
            bc = _np.clip(buckets, 0, n - 1)
            m_raw = _np.where(valid, mono[bc], 0.0)
            peak_max = max(float(m_raw.max()), 0.005)
            m_h = (m_raw / peak_max) ** 0.6 * half_h * 0.88
            pts_top = [QPointF(float(xs[i]), float(mid_y - m_h[i])) for i in range(len(xs))]
            pts_bot = [QPointF(float(xs[i]), float(mid_y + m_h[i])) for i in range(len(xs) - 1, -1, -1)]
            poly_pts = [QPointF(float(xs[0]), float(mid_y))] + pts_top + [QPointF(float(xs[-1]), float(mid_y))] + pts_bot
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(184, 197, 180, 86))
            painter.drawPolygon(QPolygonF(poly_pts))
            painter.setBrush(Qt.BrushStyle.NoBrush)
        else:
            painter.setPen(QColor(COLOR_TEXT_TERTIARY))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter,
                tr("veditor.sound_editor.waveform_loading"),
            )

        # --- cuts (clip-local ms ??rect.x) ---
        for cut in clip.cuts:
            x1 = rect.left() + int(cut.start_ms / eff_len * rect.width())
            x2 = rect.left() + int(cut.end_ms / eff_len * rect.width())
            painter.fillRect(
                x1, rect.top(), max(1, x2 - x1), rect.height(),
                QColor(30, 30, 30, 200),
            )

        # --- fade segments (source-ms ??clip-local) ---
        from PySide6.QtGui import QLinearGradient
        for fade in clip.fades:
            local_start = fade.start_ms - clip.trim_start_ms
            local_end = fade.end_ms - clip.trim_start_ms
            if local_end <= 0 or local_start >= eff_len:
                continue
            fx1 = rect.left() + int(max(0, local_start) / eff_len * rect.width())
            fx2 = rect.left() + int(min(eff_len, local_end) / eff_len * rect.width())
            kind = getattr(fade, "kind", "both")
            painter.save()
            painter.setClipRect(rect)
            if kind == "in":
                g = QLinearGradient(fx1, 0, fx2, 0)
                g.setColorAt(0.0, QColor(0, 0, 0, 180))
                g.setColorAt(1.0, QColor(216, 90, 48, 0))
                painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), g)
            elif kind == "out":
                g = QLinearGradient(fx1, 0, fx2, 0)
                g.setColorAt(0.0, QColor(216, 90, 48, 0))
                g.setColorAt(1.0, QColor(0, 0, 0, 180))
                painter.fillRect(fx1, rect.top(), fx2 - fx1, rect.height(), g)
            else:
                mid = (fx1 + fx2) // 2
                g1 = QLinearGradient(fx1, 0, mid, 0)
                g1.setColorAt(0.0, QColor(216, 90, 48, 0))
                g1.setColorAt(1.0, QColor(0, 0, 0, 180))
                painter.fillRect(fx1, rect.top(), mid - fx1, rect.height(), g1)
                g2 = QLinearGradient(mid, 0, fx2, 0)
                g2.setColorAt(0.0, QColor(0, 0, 0, 180))
                g2.setColorAt(1.0, QColor(216, 90, 48, 0))
                painter.fillRect(mid, rect.top(), fx2 - mid, rect.height(), g2)
            painter.restore()
            painter.setPen(QPen(QColor(COLOR_ACCENT_ORANGE), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(fx1, rect.top(), max(1, fx2 - fx1), rect.height())

        # --- selection band (source-ms range) ---
        if (
            self._selection_start_ms >= 0
            and self._selection_end_ms > self._selection_start_ms
        ):
            sx1 = self._source_ms_to_x(self._selection_start_ms)
            sx2 = self._source_ms_to_x(self._selection_end_ms)
            sel_rect = QRect(sx1, rect.top(), max(1, sx2 - sx1), rect.height())
            painter.fillRect(sel_rect, QColor(143, 156, 173, 54))
            pen = QPen(QColor(AUDIO_BLUE))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(sel_rect)

        # --- markers (clip._se_markers, source-ms) ---
        markers = getattr(clip, "_se_markers", None) or []
        if markers:
            painter.setPen(Qt.PenStyle.NoPen)
            marker_color = QColor(AUDIO_AMBER)
            for m_ms in markers:
                if m_ms < clip.trim_start_ms or m_ms > clip.effective_trim_end_ms:
                    continue
                mx = self._source_ms_to_x(int(m_ms))
                # Vertical guide line
                painter.setPen(QPen(QColor(130, 146, 133, 120), 1, Qt.PenStyle.DashLine))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(mx, rect.top() + 6, mx, rect.bottom() - 2)
                # Triangle flag at the top
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(marker_color)
                from PySide6.QtCore import QPoint as _QP2
                from PySide6.QtGui import QPolygon as _QPoly2
                painter.drawPolygon(
                    _QPoly2([
                        _QP2(mx - 4, rect.top()),
                        _QP2(mx + 4, rect.top()),
                        _QP2(mx, rect.top() + 7),
                    ])
                )

        # --- playhead ---
        if self._playhead_source_ms >= 0:
            local_ms = self._playhead_source_ms - clip.trim_start_ms
            if 0 <= local_ms <= eff_len:
                px = rect.left() + int(local_ms / eff_len * rect.width())
                pen = QPen(QColor(AUDIO_AMBER))
                pen.setWidth(2)
                painter.setPen(pen)
                painter.drawLine(px, rect.top(), px, rect.bottom())
                painter.setBrush(QColor(AUDIO_AMBER))
                painter.setPen(QColor(AUDIO_AMBER))
                from PySide6.QtCore import QPoint as _QP
                from PySide6.QtGui import QPolygon
                painter.drawPolygon(
                    QPolygon([
                        _QP(px, rect.top()),
                        _QP(px + 5, rect.top() + 6),
                        _QP(px, rect.top() + 12),
                        _QP(px - 5, rect.top() + 6),
                    ])
                )



class SpectrumExtractor(QThread):
    """Background FFT-based spectrum analyser.

    Extracts 8192 PCM samples from the middle of the audio file at 44100 Hz,
    applies a real FFT, and maps the result to 64 log-spaced magnitude bins
    spanning 20 Hz ??20 kHz (normalised 0-1).  Emits ``ready(bins)`` where
    *bins* is a ``numpy.ndarray`` of shape ``(64,)`` and dtype ``float32``,
    or ``ready(None)`` on failure / no audio stream.
    """

    ready = Signal(object)  # np.ndarray float32 shape (64,) or None

    def __init__(self, path: "Path") -> None:
        super().__init__()
        self._path = Path(path)

    def run(self) -> None:  # noqa: C901
        import sys
        try:
            cached = get_cached_spectrum(self._path)
            if cached is not None:
                self.ready.emit(cached)
                return

            try:
                from imageio_ffmpeg import get_ffmpeg_exe

                from app.native_worker import native_audio_spectrum

                bins = native_audio_spectrum(
                    self._path,
                    ffmpeg_path=get_ffmpeg_exe(),
                    sample_rate=44100,
                    samples=8192,
                    bins=64,
                )
                if bins is not None:
                    store_cached_spectrum(self._path, bins)
                    self.ready.emit(bins)
                    return
            except Exception:
                pass

            import subprocess

            import numpy as np
            from imageio_ffmpeg import get_ffmpeg_exe
            from app.subprocess_utils import hidden_subprocess_kwargs

            ffmpeg = get_ffmpeg_exe()
            target_sr = 44100
            n_samples = 8192

            # ---- probe duration so we can seek to the middle ----
            # Use -v info so stream info (including "Audio:") appears in stderr.
            probe_cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "info",
                "-i", str(self._path),
            ]
            probe = subprocess.run(
                probe_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_subprocess_kwargs(),
            )
            stderr_txt = probe.stderr or ""
            if "Audio:" not in stderr_txt:
                self.ready.emit(None)
                return

            import re
            dur_m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr_txt)
            duration_s = 0.0
            if dur_m:
                h, mn, s = int(dur_m.group(1)), int(dur_m.group(2)), float(dur_m.group(3))
                duration_s = h * 3600 + mn * 60 + s

            # Seek to the middle (but not closer than 0.5 s before end).
            seek_s = max(0.0, min(duration_s / 2.0, duration_s - n_samples / target_sr - 0.1))

            # ---- extract raw PCM ----
            cmd = [
                ffmpeg,
                "-nostdin",
                "-v", "error",
                "-ss", f"{seek_s:.3f}",
                "-i", str(self._path),
                "-map", "0:a:0",
                "-ac", "1",                # mono
                "-ar", str(target_sr),
                "-f", "f32le",
                "-acodec", "pcm_f32le",
                "-t", f"{n_samples / target_sr:.6f}",
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **hidden_subprocess_kwargs(),
            )
            raw, _ = proc.communicate()
            if not raw:
                self.ready.emit(None)
                return

            pcm = np.frombuffer(raw, dtype=np.float32)
            if pcm.size == 0:
                self.ready.emit(None)
                return

            # Zero-pad or truncate to exactly n_samples for a clean FFT.
            if pcm.size < n_samples:
                pcm = np.pad(pcm, (0, n_samples - pcm.size))
            else:
                pcm = pcm[:n_samples]

            # Apply Hann window to reduce spectral leakage.
            window = np.hanning(n_samples).astype(np.float32)
            pcm = pcm * window

            # Real FFT ??only positive frequencies.
            fft_out = np.fft.rfft(pcm)
            magnitude = np.abs(fft_out).astype(np.float32)

            # Frequency axis for each FFT bin.
            freqs = np.fft.rfftfreq(n_samples, d=1.0 / target_sr).astype(np.float32)

            # Map into 64 log-spaced bins from 20 Hz to 20 kHz.
            n_bins = 64
            f_min, f_max = 20.0, 20000.0
            bin_edges = np.logspace(np.log10(f_min), np.log10(f_max), n_bins + 1)

            out_bins = np.zeros(n_bins, dtype=np.float32)
            for i in range(n_bins):
                mask = (freqs >= bin_edges[i]) & (freqs < bin_edges[i + 1])
                if mask.any():
                    out_bins[i] = magnitude[mask].mean()

            # Normalise to 0-1 (avoid div-by-zero on silence).
            peak = out_bins.max()
            if peak > 0:
                out_bins /= peak

            store_cached_spectrum(self._path, out_bins)
            self.ready.emit(out_bins)

        except Exception:
            self.ready.emit(None)



class SpectrumView(QWidget):
    """Displays 64 log-spaced magnitude bars (20 Hz ??20 kHz).

    While analysis is pending, shows a gray placeholder with Korean status
    text.  Bar colours follow the DaVinci Resolve convention:
      0 ??60 %  ?? green
      60 ??80 % ?? yellow
      80 ??100 % ??red
    Frequency labels (20 Hz / 1 kHz / 20 kHz) are shown on the bottom axis.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(90)
        self._bins = None  # type: None | object  # np.ndarray or None sentinel

    def set_bins(self, bins) -> None:
        """Slot connected to SpectrumExtractor.ready."""
        self._bins = bins  # may be None (failed) or ndarray
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        bg = QColor(AUDIO_BG)
        painter.fillRect(self.rect(), bg)

        w, h = self.width(), self.height()
        label_h = 14  # pixels reserved at bottom for freq labels
        bar_area_h = h - label_h

        try:
            import numpy as np
            bins_available = (
                self._bins is not None
                and isinstance(self._bins, np.ndarray)
                and self._bins.size > 0
            )
        except ImportError:
            bins_available = False

        if not bins_available:
            # ---- placeholder ----
            painter.setPen(QColor(AUDIO_TEXT_DIM))
            font = painter.font()
            font.setPointSize(9)
            painter.setFont(font)
            text = "遺꾩꽍 以?.." if self._bins is None else "?ㅻ뵒???놁쓬"
            text = "Analyzing spectrum..." if self._bins is None else "No audio spectrum"
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
            painter.end()
            return

        n = len(self._bins)
        if n == 0:
            painter.end()
            return

        bar_w = max(1, w / n)
        gap = max(0, bar_w - max(1, bar_w * 0.8))

        for i, val in enumerate(self._bins):
            val = float(val)
            bar_h = int(val * bar_area_h)
            if bar_h < 1:
                continue
            x = int(i * bar_w)
            y = bar_area_h - bar_h

            if val <= 0.6:
                color = QColor(AUDIO_GREEN)   # low
            elif val <= 0.8:
                color = QColor(AUDIO_AMBER)   # mid
            else:
                color = QColor(AUDIO_RED)     # hot

            painter.fillRect(int(x), y, max(1, int(bar_w - gap)), bar_h, color)

        # ---- frequency axis labels ----
        painter.setPen(QColor(AUDIO_TEXT_DIM))
        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)

        import math as _math
        f_min, f_max = 20.0, 20000.0
        label_info = [
            (20.0,    "20Hz"),
            (1000.0,  "1kHz"),
            (20000.0, "20kHz"),
        ]
        log_range = _math.log10(f_max) - _math.log10(f_min)
        for freq, lbl in label_info:
            ratio = (_math.log10(freq) - _math.log10(f_min)) / log_range
            lx = int(ratio * w)
            painter.drawText(lx - 16, bar_area_h, 32, label_h,
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                             lbl)

        painter.end()



class _EqCurveView(QWidget):
    """Simple magnitude-response preview for the 3-band EQ. Computes
    the summed response of three biquads (low-shelf / peak / high-
    shelf) on a log frequency grid and paints it as a filled curve.
    Not meant as a 1:1 match for ffmpeg's ``equalizer`` ??it's a
    visual indicator of shape, same as every DAW does."""

    def __init__(self, clip: "AudioClip", parent=None) -> None:
        super().__init__(parent)
        self.clip = clip
        self.setStyleSheet(
            f"background-color: #000; border: 1px solid {COLOR_BG_L4}; border-radius: 6px;"
        )

    def refresh(self) -> None:
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(6, 6, -6, -6)
        if rect.width() < 10 or rect.height() < 10:
            return
        eq = self.clip.effects.get("eq") or {}

        # Grid lines at 0 dB center + 吏? dB
        mid_y = rect.center().y()
        painter.setPen(QPen(QColor(40, 40, 48), 1))
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        painter.setPen(QPen(QColor(30, 30, 38), 1, Qt.PenStyle.DashLine))
        painter.drawLine(rect.left(), mid_y - rect.height() // 4, rect.right(), mid_y - rect.height() // 4)
        painter.drawLine(rect.left(), mid_y + rect.height() // 4, rect.right(), mid_y + rect.height() // 4)

        # Log-frequency axis (20 Hz ??20 kHz)
        import math
        f_min, f_max = 20.0, 20000.0
        log_min, log_max = math.log10(f_min), math.log10(f_max)
        w = rect.width()
        h = rect.height()

        # Compute the summed response (dB) across the range.
        def band_response(freq: float, f0: float, gain_db: float, q: float, kind: str) -> float:
            """Approximate biquad magnitude at ``freq`` in dB."""
            if abs(gain_db) < 0.05:
                return 0.0
            # Use a Gaussian bell around f0 for peak; slope for shelves.
            # This is a rough visual approximation, not textbook biquad.
            if kind == "peak":
                sigma = f0 / max(q, 0.1) * 0.6
                dist = freq - f0
                weight = math.exp(-(dist * dist) / (2 * sigma * sigma + 1e-9))
                return gain_db * weight
            if kind == "lowshelf":
                # Full gain below f0, rolls off above
                if freq <= f0:
                    return gain_db
                roll = math.exp(-(math.log(freq / f0)) ** 2 / 0.5)
                return gain_db * roll
            if kind == "highshelf":
                if freq >= f0:
                    return gain_db
                roll = math.exp(-(math.log(f0 / freq)) ** 2 / 0.5)
                return gain_db * roll
            return 0.0

        low = eq.get("low") or {"freq": 80, "gain": 0, "q": 0.7}
        mid = eq.get("mid") or {"freq": 1000, "gain": 0, "q": 1.0}
        high = eq.get("high") or {"freq": 10000, "gain": 0, "q": 0.7}

        # Sample the response
        samples = 120
        points: list[tuple[int, float]] = []
        for i in range(samples + 1):
            t = i / samples
            freq = 10 ** (log_min + t * (log_max - log_min))
            resp_db = (
                band_response(freq, low["freq"], low["gain"], low["q"], "lowshelf")
                + band_response(freq, mid["freq"], mid["gain"], mid["q"], "peak")
                + band_response(freq, high["freq"], high["gain"], high["q"], "highshelf")
            )
            x = rect.left() + int(t * w)
            # 吏?2 dB spans 吏퉔/2 ish; clamp.
            y = mid_y - int((resp_db / 12.0) * (h / 2 - 4))
            y = max(rect.top(), min(rect.bottom(), y))
            points.append((x, y))

        # Fill under the curve
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.moveTo(points[0][0], mid_y)
        for x, y in points:
            path.lineTo(x, y)
        path.lineTo(points[-1][0], mid_y)
        path.closeSubpath()
        painter.fillPath(path, QColor(255, 122, 74, 60))

        # Curve line
        painter.setPen(QPen(QColor("#ff7a4a"), 2))
        for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
            painter.drawLine(x1, y1, x2, y2)
