"""Timeline ruler widget.

Extracted from ``video_editor_window.py`` so that 12k-line file
keeps shrinking — the ruler is a self-contained scrub-zone widget
that doesn't depend on track state, only on its own playhead /
duration / px-per-sec settings plus an optional subtitle layer for
the marker strip.

The ruler is laid out as the first item in the tracks scroll
viewport so its tick marks line up with ``TrackRow`` content using
the shared ``MARGIN`` constant.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.i18n import tr
from app.studio_theme import (
    STUDIO_CUT,
    STUDIO_RULER_BG,
    paint_studio_playhead,
)
from app.style import (
    COLOR_BORDER_DEFAULT,
    COLOR_TEXT_TERTIARY,
)


# Shared with TrackRow — defaults are duplicated here so the ruler
# can be imported without pulling in video_editor_window.py.
DEFAULT_PX_PER_SEC = 52.0
MIN_PX_PER_SEC = 4.0
MAX_PX_PER_SEC = 300.0
MIN_TRACK_WIDTH = 300


class TimelineRuler(QWidget):
    """Horizontal time ruler shared by all tracks. Uses the same MARGIN as
    ``TrackRow`` so tick marks line up exactly with track contents. Scrolls
    horizontally with the track list (sits at the top of the same scroll
    viewport).

    Also acts as the scrub zone — click/drag on the ruler to seek the
    project playhead. Emits ``scrub_requested(project_ms)``.
    """

    scrub_requested = Signal(int)   # project_ms
    marker_delete_requested = Signal(int)  # index into markers list

    HEIGHT = 26
    MARGIN = 180  # matches TrackRow.MARGIN
    BASELINE_DURATION_MS = 30_000  # ruler width when no tracks are loaded

    def __init__(self) -> None:
        super().__init__()
        self._px_per_sec: float = DEFAULT_PX_PER_SEC
        self._duration_ms: int = 0
        self._playhead_ms: int = 0
        self._scrubbing: bool = False
        # Phase 5 Step A: optional SubtitleLayer reference for the
        # subtitle marker strip. Set via ``set_subtitle_layer`` once
        # the editor finishes building the panel; until then the
        # marker pass is a no-op.
        self._subtitle_layer = None
        # Option C: project-level IN / OUT markers. ``-1`` means
        # unset. Painted as flag-shaped indicators above the ruler;
        # the bracketed range tints the row to make export-window
        # boundaries obvious.
        self._global_in_ms: int = -1
        self._global_out_ms: int = -1
        # Project timeline markers — colored triangles drawn on the ruler.
        # Each entry: {"ms": int, "color": str, "label": str}
        self._timeline_markers: list[dict] = []
        # Pixel tolerance for marker hit-test on right-click.
        self._MARKER_HIT_PX = 8
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.SplitHCursor)
        self.setToolTip(tr("veditor.ruler.hint"))
        self._recalc_width()

    def set_global_markers(self, in_ms: int, out_ms: int) -> None:
        """Project-level IN / OUT markers. Pass ``-1`` to unset."""
        self._global_in_ms = int(in_ms)
        self._global_out_ms = int(out_ms)
        self.update()

    def set_timeline_markers(self, markers: list[dict]) -> None:
        """Update the list of project timeline markers.

        Each marker: ``{"ms": int, "color": str, "label": str}``.
        Right-clicking a marker triangle emits ``marker_delete_requested``
        with its index so the editor can remove it.
        """
        self._timeline_markers = list(markers)
        self.update()

    def set_subtitle_layer(self, layer) -> None:
        """Bind the project SubtitleLayer so the ruler can paint
        per-subtitle markers. Re-paints once on every change so the
        markers stay current as the user adds/edits/deletes."""
        self._subtitle_layer = layer
        if layer is not None:
            # Chain the layer's change hook with whatever was already
            # registered (the panel uses ``on_change`` for its own
            # list refresh). Keep both fired.
            prior = layer.on_change

            def _composite():
                self.update()
                if prior is not None:
                    try:
                        prior()
                    except Exception:
                        pass
            layer.on_change = _composite
        self.update()

    def _x_to_project_ms(self, x: int) -> int:
        if self._px_per_sec <= 0:
            return 0
        return max(0, int((x - self.MARGIN) / self._px_per_sec * 1000))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        x = event.position().toPoint().x()
        # Right-click near a marker triangle → delete it.
        if event.button() == Qt.MouseButton.RightButton:
            for i, m in enumerate(self._timeline_markers):
                mx = int(self.MARGIN + m["ms"] / 1000.0 * self._px_per_sec)
                if abs(x - mx) <= self._MARKER_HIT_PX:
                    self.marker_delete_requested.emit(i)
                    return
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._scrubbing = True
        self.scrub_requested.emit(self._x_to_project_ms(x))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._scrubbing:
            self.scrub_requested.emit(self._x_to_project_ms(event.position().toPoint().x()))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._scrubbing = False

    def set_px_per_sec(self, px: float) -> None:
        self._px_per_sec = max(MIN_PX_PER_SEC, min(MAX_PX_PER_SEC, float(px)))
        self._recalc_width()
        self.update()

    def set_project_duration(self, ms: int) -> None:
        self._duration_ms = max(0, int(ms))
        self._recalc_width()
        self.update()

    def set_playhead(self, ms: int) -> None:
        self._playhead_ms = max(0, int(ms))
        self.update()

    def desired_width(self) -> int:
        span_ms = max(self._duration_ms, self.BASELINE_DURATION_MS)
        return int(span_ms / 1000.0 * self._px_per_sec) + 2 * self.MARGIN

    def _recalc_width(self) -> None:
        self.setFixedWidth(max(MIN_TRACK_WIDTH, self.desired_width()))

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(STUDIO_RULER_BG))
        painter.fillRect(0, 0, self.MARGIN - 1, self.HEIGHT, QColor("#151515"))
        painter.setPen(QColor("#2B2B2B"))
        painter.drawLine(self.MARGIN - 1, 0, self.MARGIN - 1, self.HEIGHT)
        header_font = painter.font()
        header_font.setPixelSize(12)
        header_font.setBold(False)
        header_font.setWeight(QFont.Weight.DemiBold)
        header_font.setFamily("Segoe UI Variable")
        painter.setFont(header_font)
        painter.setPen(QColor("#C9CDD3"))
        painter.drawText(
            QRect(12, 0, self.MARGIN - 24, self.HEIGHT),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Timeline",
        )

        painter.setPen(QColor("#272727"))
        painter.drawLine(0, 0, self.width(), 0)

        if self._px_per_sec <= 0:
            return
        # Paint ticks up to the widget's actual right edge — the ruler now
        # gets stretched to host width by the editor, so this extends across
        # the whole viewport at any zoom level.
        visible_s = max(0.0, (self.width() - 2 * self.MARGIN) / self._px_per_sec)
        baseline_s = self.BASELINE_DURATION_MS / 1000.0
        duration_s = self._duration_ms / 1000.0
        total_s = max(visible_s, baseline_s, duration_s)

        # Pick a "nice" tick interval so major labels don't overlap.
        target_px = 76
        raw = target_px / self._px_per_sec
        nice_steps = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        interval_s = next((n for n in nice_steps if raw <= n), 600)
        minor_s = interval_s / 5.0

        # Layout: tick marks on top, labels directly below.
        tick_top = 3
        tick_bot = tick_top + 3
        major_tick_bot = tick_top + 6
        label_baseline = self.HEIGHT - 6

        # Minor ticks
        painter.setPen(QColor("#343434"))
        t = 0.0
        while t <= total_s + 1e-6:
            x = int(self.MARGIN + t * self._px_per_sec)
            painter.drawLine(x, tick_top, x, tick_bot)
            t += minor_s

        # Major ticks
        painter.setPen(QColor("#55585E"))
        t = 0.0
        while t <= total_s + 1e-6:
            x = int(self.MARGIN + t * self._px_per_sec)
            painter.drawLine(x, tick_top, x, major_tick_bot)
            t += interval_s

        # Time labels (centered under each major tick)
        painter.setPen(QColor("#9A9EA6"))
        font = painter.font()
        font.setPixelSize(9)
        font.setBold(False)
        font.setFamily("Segoe UI Variable")
        painter.setFont(font)
        fm = painter.fontMetrics()
        t = 0.0
        while t <= total_s + 1e-6:
            x = int(self.MARGIN + t * self._px_per_sec)
            if interval_s >= 1.0:
                m, s = divmod(int(round(t)), 60)
                label = f"{m}:{s:02d}"
            else:
                label = f"{t:.1f}s"
            tw = fm.horizontalAdvance(label)
            painter.drawText(x - tw // 2, label_baseline, label)
            t += interval_s

        # Option C: global IN / OUT markers — flag indicators above
        # the time labels, plus a tinted band between them so the
        # export window is visible at a glance. Drawn BEFORE the
        # subtitle markers so subtitle ribbons stay on top.
        if self._global_in_ms >= 0 and self._global_out_ms >= 0:
            x_in = int(self.MARGIN + self._global_in_ms / 1000.0 * self._px_per_sec)
            x_out = int(self.MARGIN + self._global_out_ms / 1000.0 * self._px_per_sec)
            if x_out > x_in:
                painter.fillRect(
                    x_in, 0, x_out - x_in, self.HEIGHT,
                    QColor(91, 75, 255, 34),
                )
        for ms, kind in (
            (self._global_in_ms, "in"),
            (self._global_out_ms, "out"),
        ):
            if ms < 0:
                continue
            x = int(self.MARGIN + ms / 1000.0 * self._px_per_sec)
            painter.setPen(QPen(QColor(STUDIO_CUT), 2))
            painter.drawLine(x, 0, x, self.HEIGHT)
            # Small flag triangle on the appropriate side.
            painter.setBrush(QColor(STUDIO_CUT))
            painter.setPen(Qt.PenStyle.NoPen)
            if kind == "in":
                flag = QPolygon([
                    QPoint(x, 0),
                    QPoint(x + 8, 4),
                    QPoint(x, 8),
                ])
            else:
                flag = QPolygon([
                    QPoint(x, 0),
                    QPoint(x - 8, 4),
                    QPoint(x, 8),
                ])
            painter.drawPolygon(flag)

        # Phase 5 Step A: subtitle markers — small Tiger Orange
        # rectangles spanning each subtitle's project-time window. The
        # strip lives just above the time labels (rows 14–22) so it
        # never collides with the major-tick text.
        if self._subtitle_layer is not None:
            marker_top = 14
            marker_h = 6
            for sub in self._subtitle_layer.items():
                s_x = int(self.MARGIN + sub.start_ms / 1000.0 * self._px_per_sec)
                e_x = int(self.MARGIN + sub.end_ms / 1000.0 * self._px_per_sec)
                w = max(2, e_x - s_x)
                painter.fillRect(
                    s_x, marker_top, w, marker_h,
                    QColor(216, 90, 48, 200),
                )
                painter.setPen(QColor("#ff7a4a"))
                painter.drawRect(s_x, marker_top, w, marker_h)

        # Project timeline markers — colored downward triangles near the
        # bottom of the ruler so they're visually distinct from the
        # global IN/OUT flags at the top.
        for m in self._timeline_markers:
            mx = int(self.MARGIN + m["ms"] / 1000.0 * self._px_per_sec)
            mc = QColor(m.get("color", "#f0a030"))
            # Thin vertical line
            painter.setPen(QPen(mc, 1))
            painter.drawLine(mx, 12, mx, self.HEIGHT)
            # Downward triangle (apex at bottom, base at top of the strip)
            painter.setBrush(mc)
            painter.setPen(Qt.PenStyle.NoPen)
            tri = QPolygon([
                QPoint(mx - 5, 12),
                QPoint(mx + 5, 12),
                QPoint(mx, 20),
            ])
            painter.drawPolygon(tri)

        # Playhead — orange with glow + diamond handle
        px = int(self.MARGIN + self._playhead_ms / 1000.0 * self._px_per_sec)
        paint_studio_playhead(painter, px, 0, self.HEIGHT, handle_top=2)
        return
